// Alpine terrain layers (`crate::alpine`) — imported by `terrain.wgsl`, which calls
// `alpine_apply` once per fragment after its own ground layers.
//
// Four scanned PBR layers in one texture array (`examples/pack_forest_textures.rs`):
//   0 snow    Poly Haven snow_02, sampled at two scales so the repeat never shows
//   1 meadow  alpine meadow turf (straw grass, soil, stones) under and around the snow line
//             (`tools/blender_forest/alpine.py`)
//   2 scree   Poly Haven gray_rocks — talus at the feet of the walls
//   3 rock    Poly Haven rock_face, graded cold grey — TRIPLANAR on cliff faces and steep slopes
//
// Cost budget (main pass): only the near fine snow and the rock use anisotropic (Grad) fetches;
// the macro snow, far snow and the meadow means are trilinear at an explicit LOD, triplanar rock
// skips negligible projections, and the noise terms only run where their mask can show them.
// placed by an RGBA8 mask baked per map (`alpine::bake_mask`):
//   R snow cover target (altitude-driven), G meadow zone, B mountain (snow + rock biomes),
//   A wall foot (drifts and talus pile up there).
//
// The splat follows the standard terrain recipe (slope + altitude + height-blend):
//   - snow holds on ground flatter than ~55 degrees, its edge broken by noise into patches that
//     fill the HOLLOWS of the ground texture first (height blend), thicker in wall-foot drifts;
//   - rock takes cliff faces (the mesher's negative vertex-alpha flag) and any steep slope inside
//     the mountains, sampled triplanar so walls never stretch;
//   - scree gathers at the wall feet, meadow covers what's left of the alpine zone.
// Snow sparkle: a sparse set of ~5 cm "crystal" cells get a tilted micro-normal and a glossy
// roughness, so the regular (shadowed) sun specular glints off them — no emissive hack, and glints
// vanish in shadow like real ones. Faded out with distance (sub-pixel cells would only shimmer).

#define_import_path warbell::alpine

#import bevy_pbr::{
    pbr_types::PbrInput,
    mesh_view_bindings::{view, lights},
}

struct AlpineParams {
    // x = 1 when the layers + mask are bound; y = sparkle strength; z = snow-cover bias
    on: vec4<f32>,
    // mask world -> uv: xy = world min corner, zw = 1 / extent
    region: vec4<f32>,
};

@group(#{MATERIAL_BIND_GROUP}) @binding(111) var<uniform> alp: AlpineParams;
@group(#{MATERIAL_BIND_GROUP}) @binding(112) var alp_albedo: texture_2d_array<f32>;
@group(#{MATERIAL_BIND_GROUP}) @binding(113) var alp_normal: texture_2d_array<f32>;
@group(#{MATERIAL_BIND_GROUP}) @binding(114) var alp_ormh: texture_2d_array<f32>;
@group(#{MATERIAL_BIND_GROUP}) @binding(115) var alp_samp: sampler;
@group(#{MATERIAL_BIND_GROUP}) @binding(116) var alp_mask: texture_2d<f32>;
@group(#{MATERIAL_BIND_GROUP}) @binding(117) var alp_mask_samp: sampler;

// World units per repeat (different on purpose so the repeats never line up).
const T_SNOW: f32 = 5.6;
const T_SNOW_MACRO: f32 = 21.0;
const T_MEADOW: f32 = 4.3;
const T_SCREE: f32 = 3.9;
const T_ROCK: f32 = 5.2;

fn a_hash(p: vec2<f32>) -> f32 {
    var p3 = fract(vec3<f32>(p.x, p.y, p.x) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

fn a_hash2(p: vec2<f32>) -> vec2<f32> {
    var p3 = fract(vec3<f32>(p.x, p.y, p.x) * vec3<f32>(0.1031, 0.1030, 0.0973));
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.xx + p3.yz) * p3.zy);
}

fn a_noise(p: vec2<f32>) -> f32 {
    let i = floor(p);
    let f = fract(p);
    let u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
    let a = a_hash(i);
    let b = a_hash(i + vec2<f32>(1.0, 0.0));
    let c = a_hash(i + vec2<f32>(0.0, 1.0));
    let d = a_hash(i + vec2<f32>(1.0, 1.0));
    return mix(a, b, u.x) + (c - a) * u.y * (1.0 - u.x) + (d - b) * u.x * u.y;
}

struct ALayer {
    alb: vec3<f32>,
    // tangent-space normal (OpenGL, planar XZ frame) or, for the triplanar rock, world-space
    n: vec3<f32>,
    // AO, roughness, metal, height
    orm: vec4<f32>,
};

// One planar layer at world-XZ uv `u` (already divided by the repeat), explicit gradients.
fn a_planar(layer: i32, u: vec2<f32>, gx: vec2<f32>, gy: vec2<f32>) -> ALayer {
    var o: ALayer;
    o.alb = textureSampleGrad(alp_albedo, alp_samp, u, layer, gx, gy).rgb;
    o.n = textureSampleGrad(alp_normal, alp_samp, u, layer, gx, gy).xyz * 2.0 - 1.0;
    o.orm = textureSampleGrad(alp_ormh, alp_samp, u, layer, gx, gy);
    return o;
}

// Triplanar rock (Golus "whiteout" normal blend, as `reskin.wgsl`), world-space normal out.
// Projections whose blend weight is negligible are SKIPPED (each costs three anisotropic
// fetches): the weights are pushed down by `cut` and renormalised, so a wall facing one axis pays
// for one projection, an edge or slope for two, and only true corners for all three. `cut` is
// larger on the Low lane (≈ biplanar). Continuous: a weight reaches 0 before its fetch is dropped.
fn a_rock(p: vec3<f32>, n: vec3<f32>, dpx: vec3<f32>, dpy: vec3<f32>, cut: f32) -> ALayer {
    var w = pow(abs(n), vec3<f32>(4.0));
    w /= (w.x + w.y + w.z);
    w = max(w - cut, vec3<f32>(0.0));
    w /= (w.x + w.y + w.z);
    var o: ALayer;
    o.alb = vec3<f32>(0.0);
    o.orm = vec4<f32>(0.0);
    var nn = vec3<f32>(0.0);
    if w.x > 0.0 {
        let u = p.zy / T_ROCK;
        let gx = dpx.zy / T_ROCK;
        let gy = dpy.zy / T_ROCK;
        o.alb += textureSampleGrad(alp_albedo, alp_samp, u, 3, gx, gy).rgb * w.x;
        o.orm += textureSampleGrad(alp_ormh, alp_samp, u, 3, gx, gy) * w.x;
        let t = textureSampleGrad(alp_normal, alp_samp, u, 3, gx, gy).xyz * 2.0 - 1.0;
        nn += vec3<f32>(t.xy * 1.3 + n.zy, abs(t.z) * n.x).zyx * w.x;
    }
    if w.y > 0.0 {
        let u = p.xz / T_ROCK + vec2<f32>(0.31, 0.57);
        let gx = dpx.xz / T_ROCK;
        let gy = dpy.xz / T_ROCK;
        o.alb += textureSampleGrad(alp_albedo, alp_samp, u, 3, gx, gy).rgb * w.y;
        o.orm += textureSampleGrad(alp_ormh, alp_samp, u, 3, gx, gy) * w.y;
        let t = textureSampleGrad(alp_normal, alp_samp, u, 3, gx, gy).xyz * 2.0 - 1.0;
        nn += vec3<f32>(t.xy * 1.3 + n.xz, abs(t.z) * n.y).xzy * w.y;
    }
    if w.z > 0.0 {
        let u = p.xy / T_ROCK + vec2<f32>(0.63, 0.17);
        let gx = dpx.xy / T_ROCK;
        let gy = dpy.xy / T_ROCK;
        o.alb += textureSampleGrad(alp_albedo, alp_samp, u, 3, gx, gy).rgb * w.z;
        o.orm += textureSampleGrad(alp_ormh, alp_samp, u, 3, gx, gy) * w.z;
        let t = textureSampleGrad(alp_normal, alp_samp, u, 3, gx, gy).xyz * 2.0 - 1.0;
        nn += vec3<f32>(t.xy * 1.3 + n.xy, abs(t.z) * n.z) * w.z;
    }
    o.n = normalize(nn);
    return o;
}

// Explicit LOD for the cheap (trilinear, non-anisotropic) fetches of the 1024² layers: the
// geometric mean of the two footprint axes, a middle ground between a blurry max-axis LOD and an
// aliasing min-axis one (TAA resolves the rest).
fn a_lod(gx: vec2<f32>, gy: vec2<f32>) -> f32 {
    return max(0.25 * log2(max(dot(gx, gx), 1e-12) * max(dot(gy, gy), 1e-12)) + 10.0, 0.0);
}

// Splat the alpine layers into `pbr` (after terrain.wgsl's own ground). `cliff` = the mesher's
// cliff-face flag, `skip` = coverage already owned by the forest floor, `road` = the baked road
// strength (trails stay the ground's own trodden earth), `dpx`/`dpy` = world-position derivatives
// (taken in uniform control flow by the caller), `q` = ground quality (0 Low .. 2 Ultra).
// Returns the alpine coverage written (0 = untouched), so the caller can keep its own later
// ground-specific tweaks (grass sheen, marsh wetness) off the snow.
fn alpine_apply(pbr: ptr<function, PbrInput>, p: vec3<f32>, gn_in: vec3<f32>, cliff: f32, skip: f32, road: f32, dpx: vec3<f32>, dpy: vec3<f32>, q: f32) -> f32 {
    if alp.on.x < 0.5 {
        return 0.0;
    }
    let gn = normalize(gn_in);
    let muv = (p.xz - alp.region.xy) * alp.region.zw;
    let m = textureSampleLevel(alp_mask, alp_mask_samp, muv, 0.0);
    let up = gn.y;
    // Nothing alpine here (most of the island): skip the breakup noise and every fetch below.
    if m.r + m.g + m.b + cliff + max(alp.on.z, 0.0) < 1e-3 {
        return 0.0;
    }
    let dist = distance(view.world_position.xyz, p);

    // Broad + fine breakup noise (rotated lattices), shared by every edge below.
    let nb = a_noise(vec2<f32>(0.82 * p.x - 0.57 * p.z, 0.57 * p.x + 0.82 * p.z) * 0.12 + 7.0) * 0.62
           + a_noise(vec2<f32>(0.34 * p.x + 0.94 * p.z, -0.94 * p.x + 0.34 * p.z) * 0.47 + 3.0) * 0.38;

    // ── weights ──
    // Snow: the mask's altitude target, deepened in wall-foot drifts, held only below ~55 degrees.
    let cover = clamp(m.r * (1.0 + 0.35 * m.a) + alp.on.z, 0.0, 1.0);
    // Snow holds below ~55 degrees on open ground, but on a cliff face only on near-level ledges
    // (otherwise the fluted lip rows frost in alternating stripes — a picket fence of white).
    // (The edge is broken by the noise so the snow / rock line never traces a slope contour.)
    let hold = smoothstep(mix(0.58, 0.80, cliff), mix(0.86, 0.97, cliff), up + (nb - 0.5) * 0.12);
    // Trodden trails: the road keeps the ground's own earth track (a muddy rut through the snow),
    // with a ragged packed-snow margin.
    let trail = smoothstep(0.30, 0.75, road + (nb - 0.5) * 0.35);
    let lim = 0.52 + (nb - 0.5) * 0.75;
    var snow = smoothstep(lim - 0.10, lim + 0.10, cover) * hold * (1.0 - trail * 0.9);
    // (No noise-driven "wind scour" any more: its ~25u talus blotches read as grey stains on
    // the massif. Bare ground up high now comes only from the terrain itself — steep slopes.)
    // Rock: cliff faces anywhere, steep ground inside the mountains, and — high in the snow —
    // whatever the snow leaves bare on any real slope (> ~22 deg), so the massif shows dark ribs
    // on its crests and gully walls instead of olive turf or gravel under thin snow.
    // High in the snow the snow / rock line is CRISP (a few degrees wide, wandering with the
    // noise): a soft slope ramp smeared dark rock into the snow as brown smudges.
    let steep = 1.0 - smoothstep(0.50, 0.78, up);
    let hi = m.b * smoothstep(0.60, 0.90, m.r);
    // (Bare from ~37°: slopes the hero can't climb anyway read as rock, not as walkable snow.)
    let bare_hi = hi * smoothstep(0.42, 0.58, 1.0 - smoothstep(0.71, 0.89, up + (nb - 0.5) * 0.22));
    snow *= 1.0 - bare_hi;
    var rock = clamp(max(cliff * 1.3, max(steep * m.b * (1.0 - hi), bare_hi)), 0.0, 1.0) * (1.0 - snow);
    // Scree: talus at the (real) wall feet in the mountains (patchy), less where the snow lies deep.
    var scree = m.a * m.b * smoothstep(0.30, 0.62, nb + 0.18 * (1.0 - m.r)) * (1.0 - snow) * (1.0 - rock);
    // Meadow: whatever the alpine zone leaves uncovered (top faces only) — on the low apron and
    // the margin around the biome, not up on the mountain.
    var mead = m.g * hold * (1.0 - snow) * (1.0 - rock) * (1.0 - scree) * (1.0 - trail) * (1.0 - smoothstep(0.55, 0.85, m.r));
    scree *= 1.0 - trail;
    // The meadow fades in over the zone edge rather than replacing the procedural lawn wholesale.
    let cov = clamp(snow + rock + scree + mead, 0.0, 1.0) * (1.0 - skip);
    if cov < 0.003 {
        return 0.0;
    }

    let dx = dpx.xz;
    let dy = dpy.xz;

    // ── height-blend the planar layers (snow fills the hollows of the ground under it) ──
    var hm = 0.0;
    var hc = 0.0;
    var s0: ALayer;
    var s1: ALayer;
    var l1: ALayer;
    var l2: ALayer;
    let snow_on = snow > 0.004;
    // Fine snow detail fades with distance: its normal is gone by SNOW_FINE_FAR, past which the
    // anisotropic (Grad) fetches are traded for cheap trilinear ones at an explicit LOD.
    let snow_far = smoothstep(16.0, 28.0, dist);
    if snow_on {
        let su = p.xz / T_SNOW;
        let sgx = dx / T_SNOW;
        let sgy = dy / T_SNOW;
        if snow_far < 1.0 {
            s0 = a_planar(0, su, sgx, sgy);
            s0.n = vec3<f32>(s0.n.xy * (1.0 - snow_far), s0.n.z);
        } else {
            let l = a_lod(sgx, sgy);
            s0.alb = textureSampleLevel(alp_albedo, alp_samp, su, 0, l).rgb;
            s0.orm = textureSampleLevel(alp_ormh, alp_samp, su, 0, l);
            s0.n = vec3<f32>(0.0, 0.0, 1.0);
        }
        // Macro snow: a slower, rotated second scale so the drifts wander instead of tiling.
        // Broad albedo / normal drift only (no ORM), trilinear at an explicit LOD; off on Low.
        s1.alb = s0.alb;
        s1.n = vec3<f32>(0.0, 0.0, 1.0);
        if q >= 1.0 {
            let r = vec2<f32>(0.6 * p.x - 0.8 * p.z, 0.8 * p.x + 0.6 * p.z) / T_SNOW_MACRO + vec2<f32>(0.41, 0.13);
            let rdx = vec2<f32>(0.6 * dpx.x - 0.8 * dpx.z, 0.8 * dpx.x + 0.6 * dpx.z);
            let rdy = vec2<f32>(0.6 * dpy.x - 0.8 * dpy.z, 0.8 * dpy.x + 0.6 * dpy.z);
            let l = a_lod(rdx / T_SNOW_MACRO, rdy / T_SNOW_MACRO);
            s1.alb = textureSampleLevel(alp_albedo, alp_samp, r, 0, l).rgb;
            s1.n = textureSampleLevel(alp_normal, alp_samp, r, 0, l).xyz * 2.0 - 1.0;
        }
    }
    // Meadow: past ~40u the turf is fully faded to its mean (see the combine) — skip its fetches.
    let far_m = smoothstep(14.0, 40.0, dist);
    if mead > 0.004 {
        if far_m < 1.0 {
            l1 = a_planar(1, p.xz / T_MEADOW + vec2<f32>(0.37, 0.61), dx / T_MEADOW, dy / T_MEADOW);
        } else {
            l1.alb = vec3<f32>(0.0);
            l1.n = vec3<f32>(0.0, 0.0, 1.0);
            l1.orm = vec4<f32>(0.0, 0.0, 0.0, 0.5);
        }
        hm = l1.orm.a;
    }
    if scree > 0.004 {
        l2 = a_planar(2, p.xz / T_SCREE + vec2<f32>(0.73, 0.19), dx / T_SCREE, dy / T_SCREE);
        hc = l2.orm.a;
    }
    // Snow vs. the ground under it: snow wins in the ground's LOW texels first, so a thin cover
    // reads as snow caught between grass tufts and stones rather than a soft cross-fade.
    let under = (mead * (1.0 - hm) + scree * (1.0 - hc)) / max(mead + scree, 1e-3);
    let wsnow = snow + under * 0.45 * snow * (1.0 - snow) * 4.0;
    var w = vec3<f32>(wsnow, mead + hm * 0.35 * mead, scree + hc * 0.35 * scree);
    let wm = max(w.x, max(w.y, w.z));
    w = max(w - (wm - 0.30), vec3<f32>(0.0));
    let wsum = w.x + w.y + w.z;
    if wsum > 1e-4 {
        w = w / wsum * (1.0 - rock);
    }

    // ── combine ──
    let tx = normalize(vec3<f32>(1.0, 0.0, 0.0) - gn * gn.x);
    let bz = cross(gn, tx);
    var alb = vec3<f32>(0.0);
    var nw = vec3<f32>(0.0);
    var orm = vec3<f32>(0.0);
    if snow_on && w.x > 0.0 {
        // Two snow scales: macro albedo drift + fine/macro normal blend (whiteout), kept soft.
        let sa = mix(s0.alb, s1.alb, 0.35);
        let sn = vec3<f32>((s0.n.xy + s1.n.xy * 0.8) * 0.7, s0.n.z * s1.n.z);
        let ns = normalize(tx * sn.x + bz * sn.y + gn * max(sn.z, 0.25));
        alb += w.x * sa * 0.96;
        nw += w.x * ns;
        // (The snow_02 scan's roughness runs ~0.8; pull it toward wind-crust gloss a little.)
        orm += w.x * vec3<f32>(mix(s0.orm.r, 1.0, 0.3), mix(s0.orm.g, 0.6, 0.4), 0.0);
    }
    if mead > 0.004 && w.y > 0.0 {
        let nfade = 1.5 * (1.0 - far_m * 0.92);
        let nm = normalize(tx * l1.n.x * nfade + bz * l1.n.y * nfade + gn * max(l1.n.z, 0.2));
        // Alpine sward: the scanned turf pushed toward a cool olive green (the raw scan reads as
        // dry straw under the warm sun), fresher in broad lush patches, sun-dried and paler in
        // the last stretch below the snow line.
        // Past ~20u the turf's own blotches (and its normal map) repeat every T_MEADOW into a
        // dashed moire; fade both fully to the layer's mean (its 1x1 mip) / the geometric normal
        // and let the broad noise tint below carry the variety.
        var mmean = vec3<f32>(0.0);
        var omean = vec3<f32>(0.0);
        if far_m > 0.0 {
            mmean = textureSampleLevel(alp_albedo, alp_samp, vec2<f32>(0.5), 1, 12.0).rgb;
            omean = textureSampleLevel(alp_ormh, alp_samp, vec2<f32>(0.5), 1, 12.0).rgb;
        }
        let mal = mix(l1.alb, mmean, far_m);
        let ml = dot(mal, vec3<f32>(0.2126, 0.7152, 0.0722));
        var ma = mix(vec3<f32>(ml), mal, 1.35) * vec3<f32>(0.80, 1.04, 0.66);
        let lush = smoothstep(0.35, 0.75, nb);
        ma = mix(ma, ma * vec3<f32>(0.82, 1.06, 0.78), lush * 0.6);
        ma = mix(ma, vec3<f32>(ml) * vec3<f32>(1.10, 1.02, 0.80), smoothstep(0.20, 0.55, m.r) * 0.45);
        alb += w.y * ma;
        nw += w.y * nm;
        // The AO / roughness tile too (AO darkens the turf's hollows in the same dashed rows).
        orm += w.y * mix(l1.orm.rgb, omean, far_m);
    }
    if scree > 0.004 && w.z > 0.0 {
        let nc = normalize(tx * l2.n.x * 1.6 + bz * l2.n.y * 1.6 + gn * max(l2.n.z, 0.2));
        alb += w.z * l2.alb;
        nw += w.z * nc;
        orm += w.z * l2.orm.rgb;
    }
    if rock > 0.004 {
        let r = a_rock(p, gn, dpx, dpy, select(0.06, 0.25, q < 1.0));
        // Keep a whisper of the biome hue (sandstone desert walls vs. grey granite vs. snow crags):
        // the vertex colour's chroma only, not its value.
        let base = (*pbr).material.base_color.rgb;
        let tint = clamp(base / max(dot(base, vec3<f32>(0.3333)), 1e-3), vec3<f32>(0.75), vec3<f32>(1.3));
        var ra = r.alb * mix(vec3<f32>(1.0), tint, 0.45);
        // Up in the snow the crags are cold grey granite: the scan's warm cast read as dirt / mud
        // smeared on the snow from afar.
        let rl = dot(ra, vec3<f32>(0.2126, 0.7152, 0.0722));
        ra = mix(ra, vec3<f32>(rl) * vec3<f32>(0.90, 0.96, 1.06), m.r * 0.75);
        // Snow caught on the rock up in the snow zone: it fills the texture's low texels (cracks,
        // ledges) and the more level facets first, so a crag reads as relief — dark ribs with
        // white in every hollow — rather than one flat grey stain.
        let lodge = smoothstep(0.55, 0.85, (1.0 - r.orm.a) * 1.1 + up * 0.55 - 0.30 + (nb - 0.5) * 0.25);
        ra = mix(ra, vec3<f32>(0.82, 0.86, 0.92), m.r * lodge * 0.85);
        // Snow streaks down the faces (couloirs / spindrift): a noise stretched along Y, so a
        // snow-zone crag reads as dark rock laced with white instead of one slate band from afar.
        if m.r > 0.0 {
            let along = dot(p.xz, vec2<f32>(0.707, 0.707)) * 0.85 + nb * 1.3;
            let streak = smoothstep(0.52, 0.80, a_noise(vec2<f32>(along, p.y * 0.16 + 3.0)));
            ra = mix(ra, vec3<f32>(0.78, 0.81, 0.86), m.r * streak * 0.4 * smoothstep(-0.2, 0.4, up));
        }
        let lodged = m.r * lodge * 0.85;
        alb += rock * ra;
        nw += rock * normalize(mix(r.n, gn, lodged * 0.6));
        orm += rock * vec3<f32>(mix(r.orm.r, 1.0, lodged), mix(r.orm.g, 0.62, lodged), 0.0);
    }
    // Broad value drift so no layer reads as a printed repeat from a distance.
    alb *= 0.90 + 0.20 * nb;

    let k = cov;
    let base = (*pbr).material.base_color;
    (*pbr).material.base_color = vec4<f32>(mix(base.rgb, alb, k), base.a);
    (*pbr).N = normalize(mix((*pbr).N, normalize(nw), k));
    (*pbr).material.perceptual_roughness = mix((*pbr).material.perceptual_roughness, clamp(orm.g, 0.3, 1.0), k);
    // Dielectric, default F0 — whatever the underlying ground material carried.
    (*pbr).material.metallic = mix((*pbr).material.metallic, 0.0, k);
    (*pbr).material.reflectance = mix((*pbr).material.reflectance, vec3<f32>(0.5), k);
    (*pbr).diffuse_occlusion *= vec3<f32>(mix(1.0, orm.r, k * 0.75));

    // ── snow sparkle ──
    let sparkle = alp.on.y * w.x * k;
    if sparkle > 0.05 && q >= 1.0 {
        let fade = 1.0 - smoothstep(14.0, 32.0, dist);
        if fade > 0.0 {
            let cell = floor(p.xz * 19.0);
            let h = a_hash2(cell + vec2<f32>(17.0, 3.0));
            // ~1 cell in 4 holds a crystal — a small round facet at a random spot in its cell, not
            // the whole square (whole-cell facets tiled the near snow into a visible pixel mosaic,
            // half the squares tilted away from the sun and darkened).
            let spot = 1.0 - smoothstep(0.10, 0.20, length(fract(p.xz * 19.0) - (0.25 + 0.5 * h.yx)));
            if a_hash(cell * 1.37 + vec2<f32>(5.0, 11.0)) < 0.26 && spot > 0.0 {
                let tilt = (h - 0.5) * 0.62;
                let micro = normalize(gn + tx * tilt.x + bz * tilt.y);
                let g = sparkle * fade * spot;
                (*pbr).N = normalize(mix((*pbr).N, micro, g));
                (*pbr).material.perceptual_roughness = mix((*pbr).material.perceptual_roughness, 0.14, g);
                (*pbr).material.reflectance = mix((*pbr).material.reflectance, vec3<f32>(0.9), g);
            }
        }
    }
    return k;
}
