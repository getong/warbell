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

#import bevy_pbr::{
    pbr_fragment::pbr_input_from_standard_material,
    pbr_functions::{apply_pbr_lighting, main_pass_post_lighting_processing},
    forward_io::{VertexOutput, FragmentOutput},
    mesh_functions,
}

const KIND_RING: u32 = 0u;
const KIND_SHOCK: u32 = 1u;
const KIND_BLOOD: u32 = 2u;
const KIND_BLOOD_DRY: u32 = 3u;
const KIND_SCORCH: u32 = 4u;

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

#ifdef BLEND_MULTIPLY
    // ── Stains: multiply the lit ground (premultiplied: dst * (c·a + 1 − a)) ──
    var c = vec3<f32>(1.0);
    var a = 0.0;
    if kind == KIND_SCORCH {
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
#else
    // ── Light marks: lit pale matte albedo + a dark halo, premultiplied ──
    var albedo = vec3<f32>(0.0);
    var light_a = 0.0; // coverage of the pale line
    var dark_a = 0.0;  // coverage of the darkening halo
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
    var lit = apply_pbr_lighting(pbr_input);
    lit = main_pass_post_lighting_processing(pbr_input, vec4<f32>(lit.rgb, 1.0));
    let total_a = clamp(light_a + dark_a * (1.0 - light_a), 0.0, 1.0);
    out.color = vec4<f32>(lit.rgb * light_a, total_a);
#endif
    return out;
}
