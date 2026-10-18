// Combat GROUND MARKS (`combat_marks.rs`) — every ring / pool the fight paints on the ground, as
// one procedural decal shader over a single flat quad: the soft-lock target ring, the kill / slam
// dust shockwave, fresh and dried blood pools, and shaman-bolt scorches. Replaces the old flat
// `Annulus` / `Circle` meshes, whose 12–40 hard facets read as low-poly stamps next to the PBR
// forest. Everything here is analytic + feathered (no polygon edge anywhere) and seeded per mark,
// so no two pools are the same stamped disc.
//
// Two pipelines share this file (two material instances, picked by alpha mode):
//   • BLEND_MULTIPLY — blood + scorch. Multiplies the ground it lies on, so a stain is lit by
//     exactly the sun / moon / torchlight the ground already has (never a glowing or pitch-black
//     cut-out at night). Unlit, no fog: the ground under it was already fogged.
//   • premultiplied — target ring + shockwave. Runs the stock PBR lighting on a pale matte
//     "chalk/dust" albedo, so the marks sit IN the scene's light like the ground does, plus a
//     faint dark halo (premultiplied alpha lets one quad both darken and lighten the ground).
//
// Per-mark state rides the instance `MeshTag` (packed by `combat_marks::tag`), so all marks of a
// kind share one material and instance into one draw; a fade only rewrites a u32.
//   bits  0..7   strength / alpha (0..255)
//   bits  8..11  kind (see KIND_*)
//   bits 12..19  seed (shape variation)
//   bits 20..27  aux (shockwave: age 0..255)

import bevy_pbr::{
    render::pbr_fragment::pbr_input_from_standard_material,
    render::pbr_functions::{apply_pbr_lighting, main_pass_post_lighting_processing},
    render::forward_io::{VertexOutput, FragmentOutput},
    render::mesh_functions,
    render::mesh_view_bindings::lights,
};

const KIND_RING: u32 = 0u;
const KIND_SHOCK: u32 = 1u;
const KIND_BLOOD: u32 = 2u;
const KIND_BLOOD_DRY: u32 = 3u;
const KIND_SCORCH: u32 = 4u;
const KIND_RUNE: u32 = 5u;    // guardian-trial rune circle (aux = hold progress)
const KIND_PLOT: u32 = 6u;    // surveyed build plot (aux ≥ 0.5 = the targeted plot)
const KIND_ORDER: u32 = 7u;   // RTS move-order click-mark (aux = age)
const KIND_ORDER_ATK: u32 = 9u; // RTS attack-order click-mark (aux = age)
const KIND_SELECT: u32 = 8u;  // RTS selected-unit ring (aux ≥ 0.5 = rival side)
const KIND_BOOT: u32 = 10u;   // boot print (aux = bit field, see `combat_marks::boot_tag`)

const TAU: f32 = 6.28318530718;

fn hash2(p: vec2<f32>) -> f32 {
    return fract(sin(dot(p, vec2<f32>(127.1, 311.7))) * 43758.5453);
}

// Bilinear value noise, [0,1].
fn vnoise(p: vec2<f32>) -> f32 {
    let i = floor(p);
    let f = fract(p);
    let u = f * f * (3.0 - 2.0 * f);
    let a = hash2(i);
    let b = hash2(i + vec2<f32>(1.0, 0.0));
    let c = hash2(i + vec2<f32>(0.0, 1.0));
    let d = hash2(i + vec2<f32>(1.0, 1.0));
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

fn fbm(p: vec2<f32>) -> f32 {
    return vnoise(p) * 0.55 + vnoise(p * 2.13 + vec2<f32>(5.2, 1.3)) * 0.3 + vnoise(p * 4.37 + vec2<f32>(9.1, 3.7)) * 0.15;
}

// Noise sampled around the circle (period-safe: walks a circle in noise space, no seam at ±π).
fn ring_noise(dir: vec2<f32>, freq: f32, seed: f32) -> f32 {
    return fbm(dir * freq + vec2<f32>(seed * 7.31, seed * 3.17));
}

// Gaussian line profile.
fn line(r: f32, r0: f32, w: f32) -> f32 {
    let x = (r - r0) / w;
    return exp(-x * x);
}

// An irregular soaked pool: noisy-edged main body, a darker drying rim, and a few seeded satellite
// droplets thrown off it. Returns density 0..1 (0 = untouched ground). `p` spans [-1, 1].
fn pool(p: vec2<f32>, seed: f32, dried: bool) -> f32 {
    let r = length(p);
    let dir = p / max(r, 1.0e-4);
    // Main body: a lumpy, slightly lopsided edge (low + mid frequency around the rim).
    let edge = 0.56 + (ring_noise(dir, 1.6, seed) - 0.5) * 0.30 + (ring_noise(dir, 4.5, seed + 3.0) - 0.5) * 0.10;
    let feather = 0.05;
    var body = 1.0 - smoothstep(edge - feather, edge + feather * 0.6, r);
    // Soaked-in interior: density mottles a little; the rim pools darker as blood dries at its edge.
    let mottle = 0.80 + 0.20 * fbm(p * 5.0 + vec2<f32>(seed * 1.7, seed * 2.9));
    let rim = smoothstep(edge - 0.16, edge - 0.02, r) * body;
    body = body * mottle + rim * select(0.18, 0.30, dried);
    // Satellite droplets (3, seeded angle + distance), each a soft blot that shrinks with distance.
    var drops = 0.0;
    for (var i = 0; i < 3; i = i + 1) {
        let fi = f32(i);
        let a = hash2(vec2<f32>(seed, fi * 3.7)) * TAU;
        let dist = 0.66 + hash2(vec2<f32>(fi * 1.9, seed + 2.0)) * 0.26;
        let rad = 0.035 + hash2(vec2<f32>(seed + fi, 7.7)) * 0.05;
        let c = vec2<f32>(cos(a), sin(a)) * dist;
        let dd = length(p - c);
        drops = max(drops, 1.0 - smoothstep(rad * 0.55, rad, dd));
    }
    return clamp(max(body, drops * 0.85), 0.0, 1.0);
}

fn smin(a: f32, b: f32, k: f32) -> f32 {
    let h = clamp(0.5 + 0.5 * (b - a) / k, 0.0, 1.0);
    return mix(b, a, h) - k * h * (1.0 - h);
}

// Uneven capsule (iq's round cone, 2D): a stroke from `a` (radius r1) to `b` (radius r2).
fn sd_round_cone(p: vec2<f32>, a: vec2<f32>, b: vec2<f32>, r1: f32, r2: f32) -> f32 {
    let ba = b - a;
    let l2 = dot(ba, ba);
    let rr = r1 - r2;
    let a2 = l2 - rr * rr;
    let il2 = 1.0 / l2;
    let pa = p - a;
    let y = dot(pa, ba);
    let z = y - l2;
    let xv = pa * l2 - ba * y;
    let x2 = dot(xv, xv);
    let y2 = y * y * l2;
    let z2 = z * z * l2;
    let k = sign(rr) * rr * rr * x2;
    if sign(z) * a2 * z2 > k {
        return sqrt(x2 + z2) * il2 - r2;
    }
    if sign(y) * a2 * y2 < k {
        return sqrt(x2 + y2) * il2 - r1;
    }
    return (sqrt(x2 * a2 * il2) + y * rr) * il2 - r1;
}

// Sole of a RIGHT boot as a signed distance in BOOT space: metres at the design size (the quad
// is 0.2 x 0.36, so `w` spans +-0.1 across x +-0.18 along), +x = the inner / arch side, +y = toe.
// A rounded heel swelling into a broad ball and a blunt, slightly in-turned toe, with the arch
// bitten out of the inner waist. ~0.30 long x 0.10 wide.
fn boot_sd(w: vec2<f32>) -> f32 {
    let body = sd_round_cone(w, vec2<f32>(-0.004, -0.108), vec2<f32>(0.006, 0.052), 0.039, 0.050);
    let toe = length((w - vec2<f32>(0.008, 0.100)) / vec2<f32>(1.0, 1.15)) - 0.043;
    var d = smin(body, toe, 0.03);
    // The arch: a soft bite out of the inner edge between heel and ball.
    let arch = length((w - vec2<f32>(0.060, -0.030)) / vec2<f32>(1.0, 1.9)) - 0.026;
    d = -smin(-d, arch, 0.02);
    return d;
}

// Print height (normalised: -1 = full depth, + = spoil pushed up round the rim) at boot-space `w`.
// `ground` 0 mud / 1 sand / 2 snow / 3 packed earth / 4 grass sward; `sprint` digs the toe in and
// throws the spoil back.
fn boot_height(w: vec2<f32>, seed: f32, ground: u32, sprint: bool) -> f32 {
    let sd = boot_sd(w);
    // Wall width (m): snow cuts crisp, mud slumps a little, dry sand pours back in.
    // Packed earth takes a shallow scuff with soft walls; on the sward it's crushed blades, not a cut.
    var wall = select(select(0.010, 0.022, ground == 1u), 0.006, ground == 2u);
    if ground == 3u {
        wall = 0.014;
    } else if ground == 4u {
        wall = 0.030;
    }
    let inside = 1.0 - smoothstep(-wall, 0.001, sd);
    // Weight distribution: the heel strikes deepest, the ball next, the arch barely touches.
    let heel_w = 1.0 - smoothstep(-0.10, -0.04, w.y);
    let ball_w = smoothstep(0.0, 0.04, w.y) * (1.0 - smoothstep(0.10, 0.14, w.y));
    var press = 0.62 + 0.38 * heel_w + 0.30 * ball_w;
    if sprint {
        press = 0.50 + 0.15 * heel_w + 0.60 * smoothstep(0.02, 0.10, w.y);
    }
    // A worn leather sole is not a stamp: soft unevenness across the floor of the print.
    let floor_n = 0.88 + 0.12 * fbm(w * 40.0 + vec2<f32>(seed * 1.3, seed * 0.7));
    var h = -inside * min(press, 1.0) * floor_n;
    // Spoil pushed up round the rim (more behind the push-off when sprinting), broken by noise.
    var lip_amt = select(select(0.30, 0.20, ground == 1u), 0.40, ground == 2u);
    if ground == 3u {
        lip_amt = 0.12;
    } else if ground == 4u {
        lip_amt = 0.0;
    }
    if sprint {
        lip_amt = lip_amt * (0.7 + 1.2 * (1.0 - smoothstep(-0.14, -0.04, w.y)));
    }
    let lip_n = 0.55 + 0.9 * fbm(w * 60.0 + vec2<f32>(seed * 2.1, 3.0));
    let x = (sd - 0.010) / 0.009;
    h = h + exp(-x * x) * lip_amt * lip_n;
    return h;
}

@fragment
fn fragment(in: VertexOutput, @builtin(front_facing) is_front: bool) -> FragmentOutput {
    let tag = mesh_functions::get_tag(in.instance_index);
    let strength = f32(tag & 0xffu) / 255.0;
    let kind = (tag >> 8u) & 0xfu;
    let seed = f32((tag >> 12u) & 0xffu) / 255.0 * 61.0 + 1.0;
    let aux = f32((tag >> 20u) & 0xffu) / 255.0;

    let p = (in.uv - vec2<f32>(0.5)) * 2.0; // [-1, 1] across the quad
    let r = length(p);

    var out: FragmentOutput;

@if(BLEND_MULTIPLY) {
    // ── Stains: multiply the lit ground (premultiplied: dst * (c·a + 1 − a)) ──
    var c = vec3<f32>(1.0);
    var a = 0.0;
    if kind == KIND_BOOT {
        // ── Boot print: a pressed height field, shaded against the sun as relief ──
        let bits = (tag >> 20u) & 0xffu;
        let ground = (bits & 3u) | ((bits >> 2u) & 4u);
        let left = (bits & 4u) != 0u;
        let sprint = (bits & 8u) != 0u;
        var q = p * vec2<f32>(0.1, 0.18); // boot space (metres at the design size)
        if left {
            q.x = -q.x; // mirror the sole: the arch always sits on the inner side
        }
        // A few degrees of seeded toe-out so a trail isn't a row of stamps.
        let ang = (fract(seed * 0.61) - 0.5) * 0.14;
        q = vec2<f32>(q.x * cos(ang) - q.y * sin(ang), q.x * sin(ang) + q.y * cos(ang));
        // Ground: depth (m at the design size), wall-occlusion strength, cavity tint, lip lift.
        var amp = 0.022;
        var tint_deep = vec3<f32>(0.42, 0.40, 0.37); // wet mud: dark, a touch cool where water seeps in
        var lip_lift = 0.07;                           // the pushed-up rim dries paler
        if ground == 1u {
            amp = 0.016;
            tint_deep = vec3<f32>(0.74, 0.70, 0.64); // dry sand: the relief does most of the work
            lip_lift = 0.10;
        } else if ground == 2u {
            amp = 0.040;
            tint_deep = vec3<f32>(0.68, 0.76, 0.92); // snow: a blue shadowed plug
            lip_lift = 0.04;
        } else if ground == 3u {
            amp = 0.010;
            tint_deep = vec3<f32>(0.74, 0.66, 0.58); // packed earth: a dusty, darker scuff
            lip_lift = 0.05;
        } else if ground == 4u {
            amp = 0.006;
            tint_deep = vec3<f32>(0.80, 0.84, 0.64); // crushed sward: bruised, a touch yellower
            lip_lift = 0.0;
        }
        let e = 0.003;
        let h = boot_height(q, seed, ground, sprint);
        var gx = (boot_height(q + vec2<f32>(e, 0.0), seed, ground, sprint) - h) / e * amp;
        let gz = (boot_height(q + vec2<f32>(0.0, e), seed, ground, sprint) - h) / e * amp;
        if left {
            gx = -gx; // back into the quad's own (unmirrored) x
        }
        // The quad's world axes, to put the slope in world space.
        let model = mesh_functions::get_world_from_local(in.instance_index);
        let axn = normalize(model[0].xyz);
        let azn = normalize(model[2].xyz);
        let up = normalize(cross(azn, axn));
        var grad = axn * gx + azn * gz;
        let gl = length(grad);
        if gl > 1.6 {
            grad = grad * (1.6 / gl);
        }
        // Relief lit from the sun's AZIMUTH (not its elevation, so a noon sun still reads the
        // walls): the wall facing the sun brightens, the wall with its back to it falls into
        // shadow — what makes a print look pressed IN rather than painted on. HDR multiply, so > 1
        // lightens.
        var l = vec3<f32>(0.6, 0.6, 0.5);
        if lights.n_directional_lights > 0u {
            l = lights.directional_lights[0].direction_to_light;
        }
        var lh = l - up * dot(l, up);
        if length(lh) < 0.05 {
            lh = axn + azn;
        }
        lh = normalize(lh);
        let relief = clamp(1.0 - 0.48 * dot(grad, lh), 0.45, 1.5);
        let depth = clamp(-h, 0.0, 1.0);
        let lip = clamp(h, 0.0, 1.0);
        // Occlusion pooled along the foot of the walls.
        let sd = boot_sd(q);
        let band = exp(-pow((sd + 0.006) / 0.010, 2.0));
        let ao = 1.0 - 0.22 * band;
        let tint = mix(vec3<f32>(1.0), tint_deep, pow(depth, 0.85)) * (1.0 + lip_lift * lip);
        c = tint * relief * ao;
        // Coverage feathers out past the spoil rim so the quad's edge never shows.
        a = 1.0 - smoothstep(0.016, 0.034, sd);
    } else if kind == KIND_SCORCH {
        let dir = p / max(r, 1.0e-4);
        let edge = 0.62 + (ring_noise(dir, 2.2, seed) - 0.5) * 0.28;
        let body = 1.0 - smoothstep(edge - 0.22, edge + 0.04, r);
        let core = 1.0 - smoothstep(0.0, edge * 0.85, r);
        let grain = 0.75 + 0.25 * fbm(p * 7.0 + vec2<f32>(seed));
        // Charred black core fading out through a warm singed-earth margin.
        c = mix(vec3<f32>(0.62, 0.50, 0.40), vec3<f32>(0.10, 0.085, 0.075), core);
        a = body * grain * 0.9;
    } else {
        let dried = kind == KIND_BLOOD_DRY;
        let d = pool(p, seed, dried);
        // Fresh: a deep, still-wet crimson. Dried: browner, darker, less saturated.
        c = select(vec3<f32>(0.40, 0.055, 0.045), vec3<f32>(0.30, 0.10, 0.07), dried);
        a = d * select(0.92, 0.85, dried);
    }
    a = a * strength;
    out.color = vec4<f32>(c * a, a);
}
@else {
    // ── Light marks: lit pale matte albedo + a dark halo, premultiplied ──
    var albedo = vec3<f32>(0.0);
    var light_a = 0.0; // coverage of the pale line
    var dark_a = 0.0;  // coverage of the darkening halo
    var ember = 0.0;   // rune circle only: smouldering-glyph glow (emissive, 0..1)
    if kind == KIND_RING {
        // Soft-lock target ring: a thin feathered line broken into four arcs (soft-ended gaps on
        // the diagonals) with a short inward tick at each arc's centre — a quiet focus mark, not
        // a glowing hoop. The quad spins slowly (CPU side) so the ticks drift.
        let ang = atan2(p.y, p.x);
        let q = fract(ang / (TAU * 0.25) + 0.5) - 0.5;           // -0.5..0.5 within each quarter
        let gap = smoothstep(0.30, 0.42, abs(q));                 // 1 inside the diagonal gaps
        let arc = (1.0 - gap) * line(r, 0.80, 0.018);
        // Ticks at the arc centres: a short radial dash just inside the line.
        let tick_w = abs(q) * TAU * 0.25 * r;                     // arc-length from the centre line
        let tick = (1.0 - smoothstep(0.006, 0.016, tick_w)) * smoothstep(0.66, 0.70, r) * (1.0 - smoothstep(0.76, 0.79, r));
        light_a = max(arc, tick * 0.9);
        // A broad, faint shadow just outside the line grounds it (reads pressed INTO the earth).
        dark_a = line(r, 0.84, 0.07) * 0.22 + line(r, 0.80, 0.03) * 0.12;
        albedo = vec3<f32>(0.80, 0.74, 0.62); // pale bone / chalk
    } else if kind == KIND_RUNE {
        // Guardian-trial rune circle: two thin chalk-and-ash lines framing a band of scratched,
        // seeded rune glyphs, over a faint scorched wash — a worn ritual circle cut into the
        // ground, not a neon hoop. `aux` (the hold meter) kindles the glyphs one by one into a dim
        // ember glow, sweeping round from the north, so progress reads in the world too.
        // Scale: the disc's half-width is RUNE_R / 0.865 ≈ 9.25u, so 0.001 in `p` ≈ 1cm.
        let ang = atan2(p.y, p.x);
        let u = fract(ang / TAU + 0.25);                         // 0..1 round the circle
        // Worn / broken chalk: patchy, with whole stretches scuffed away.
        let wear = smoothstep(0.30, 0.62, fbm(p * 11.0 + vec2<f32>(seed))) * 0.85 + 0.15;
        // The hold line itself (r = RUNE_R) and a fainter outer line ~0.6m beyond it.
        let lines = line(r, 0.865, 0.0032) * 0.8 + line(r, 0.93, 0.0024) * 0.45;
        // Glyph band between the two lines: 54 cells (~1m apart), each a small seeded rune — a
        // stem plus a slanted branch — about 40cm tall, scratched ~3cm wide.
        let cells = 54.0;
        let cu = u * cells;
        let ci = floor(cu);
        let cf = fract(cu) - 0.5;                                 // -0.5..0.5 across the cell
        let rb = (r - 0.8975) / 0.020;                            // -1..1 across the band
        let h1 = hash2(vec2<f32>(ci, seed));
        let h2 = hash2(vec2<f32>(ci * 1.7, seed + 4.0));
        let x_px = cf * (TAU * r / cells);                        // arc-length across the cell (p units)
        let band = 1.0 - smoothstep(0.8, 1.0, abs(rb));
        let stem = (1.0 - smoothstep(0.0018, 0.0042, abs(x_px - (h1 - 0.5) * 0.02))) * band;
        let slope = select(-1.0, 1.0, h2 > 0.5);
        let diag_x = x_px - slope * rb * 0.012 * (0.6 + h2);
        let diag = (1.0 - smoothstep(0.0016, 0.0038, abs(diag_x))) * (1.0 - smoothstep(0.3, 0.8, abs(rb - (h1 - 0.5))));
        let glyph = clamp(stem + diag * 0.85, 0.0, 1.0) * step(0.15, h2);
        light_a = clamp(lines + glyph * 0.85, 0.0, 1.0) * wear * 0.8;
        // Scorched earth along the band + a very faint ash wash over the whole floor.
        dark_a = (1.0 - smoothstep(0.01, 0.07, abs(r - 0.8975))) * (0.18 + 0.22 * fbm(p * 6.0 + vec2<f32>(seed)))
            + (1.0 - smoothstep(0.70, 0.96, r)) * 0.06 * fbm(p * 4.0 + vec2<f32>(seed * 2.0));
        albedo = vec3<f32>(0.60, 0.57, 0.51); // ash / old chalk
        // Kindled glyphs: those whose angle is behind the hold meter smoulder like banked embers.
        let lit_cell = 1.0 - smoothstep(aux - 0.002, aux + 0.002, (ci + 0.5) / cells);
        ember = (glyph + lines * 0.4) * lit_cell * wear;
    } else if kind == KIND_PLOT {
        // Surveyed building plot: a dashed chalk line (pegged + strung) round a softly trampled pad.
        let ang = atan2(p.y, p.x);
        let dash = smoothstep(0.18, 0.30, abs(fract(ang / TAU * 28.0) - 0.5) * 2.0);
        let sel = step(0.5, aux);
        let wear = 0.6 + 0.4 * fbm(p * 8.0 + vec2<f32>(seed));
        light_a = line(r, 0.86, 0.012) * dash * wear * mix(0.7, 1.0, sel);
        // Four survey pegs at the quarter points.
        let q = fract(ang / (TAU * 0.25) + 0.5) - 0.5;
        let peg = (1.0 - smoothstep(0.012, 0.024, abs(q) * TAU * 0.25 * r)) * line(r, 0.86, 0.035);
        light_a = max(light_a, peg);
        // The targeted plot also gets a faint inner line, so "this one" reads without a glow.
        light_a = max(light_a, line(r, 0.78, 0.008) * sel * 0.6 * wear);
        dark_a = (1.0 - smoothstep(0.55, 0.90, r)) * 0.10 * fbm(p * 3.0) * sel + line(r, 0.88, 0.03) * 0.18;
        albedo = vec3<f32>(0.80, 0.76, 0.66);
    } else if kind == KIND_ORDER || kind == KIND_ORDER_ATK {
        // RTS order confirmation: four short inward chevrons, a centre dot, chalk (move) or a
        // muted rust (attack) — a quiet "heard you, here", not a neon hoop.
        let ang = atan2(p.y, p.x);
        let q = fract(ang / (TAU * 0.25) + 0.5) - 0.5;
        let chev_r = 0.62 + abs(q) * 0.9;
        let chev = line(r, chev_r, 0.025) * (1.0 - smoothstep(0.16, 0.22, abs(q)));
        light_a = chev + line(r, 0.0, 0.08) * 0.6;
        dark_a = chev * 0.25;
        albedo = select(vec3<f32>(0.80, 0.77, 0.68), vec3<f32>(0.62, 0.26, 0.20), kind == KIND_ORDER_ATK);
    } else if kind == KIND_SELECT {
        // Selected unit: a thin, slightly worn line + soft contact shadow (muted side tint).
        light_a = line(r, 0.84, 0.03) * (0.75 + 0.25 * fbm(p * 6.0 + vec2<f32>(seed)));
        dark_a = line(r, 0.90, 0.06) * 0.25;
        albedo = mix(vec3<f32>(0.70, 0.74, 0.76), vec3<f32>(0.62, 0.30, 0.22), step(0.5, aux));
    } else {
        // Kill / slam shockwave: a ring of thrown dust that rushes out (CPU scale) and frays as it
        // goes — soft and broken by noise, with darker scuffed earth along its leading edge.
        let dir = p / max(r, 1.0e-4);
        let fray = ring_noise(dir, 5.0, seed);
        let width = mix(0.05, 0.13, aux);
        let r0 = 0.80 + (fray - 0.5) * 0.08;
        light_a = line(r, r0, width) * (0.45 + 0.55 * fray) * (1.0 - smoothstep(0.92, 1.0, r));
        dark_a = line(r, r0 + width * 0.9, width * 0.7) * 0.35;
        albedo = vec3<f32>(0.62, 0.56, 0.47); // dust
    }
    light_a = clamp(light_a, 0.0, 1.0) * strength;
    dark_a = clamp(dark_a, 0.0, 1.0) * strength;

    // Light the pale albedo exactly like the ground around it (sun / moon / IBL / torches, shadows),
    // then fog it as an opaque surface and premultiply by hand — fogging a premultiplied colour
    // would paint the transparent corners of the quad with haze.
    var pbr_input = pbr_input_from_standard_material(in, is_front);
    pbr_input.material.base_color = vec4<f32>(albedo, 1.0);
    // Banked-ember glow on kindled rune glyphs: a low, deep orange (no white core) so bloom only
    // kisses it — legible at night without turning the circle into a light source.
    pbr_input.material.emissive = vec4<f32>(vec3<f32>(2.4, 0.80, 0.22) * ember * strength, 1.0);
    light_a = max(light_a, ember * 0.9 * strength);
    var lit = apply_pbr_lighting(pbr_input);
    lit = main_pass_post_lighting_processing(pbr_input, vec4<f32>(lit.rgb, 1.0));
    let total_a = clamp(light_a + dark_a * (1.0 - light_a), 0.0, 1.0);
    out.color = vec4<f32>(lit.rgb * light_a, total_a);
}
    return out;
}
