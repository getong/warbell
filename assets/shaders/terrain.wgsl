// Forest ground vision shader — a forest-only port of the TS `vision.ts`
// `onBeforeCompile` fragment injection, wired as
// `ExtendedMaterial<StandardMaterial, TerrainExtension>`.
//
// The base StandardMaterial carries the forest grass base colour (mesh
// ATTRIBUTE_COLOR) + roughness. THIS shader runs the original's three world-space
// layers on the base colour BEFORE lighting:
//   (1) a fine 3-octave value mottle,
//   (2) a large-scale analytic hue + value drift (cure for flat green),
//   (3) the grass detail-texture imprint on up-facing fragments, normalised by the
//       texture's mean luminance.
// Params (detailScale, detailStrength, variation, mean) come in one vec4 uniform.

#import bevy_pbr::{
    pbr_fragment::pbr_input_from_standard_material,
    pbr_functions::{apply_pbr_lighting, main_pass_post_lighting_processing, visibility_range_dither},
    pbr_types::STANDARD_MATERIAL_FLAGS_UNLIT_BIT,
    forward_io::{VertexOutput, FragmentOutput},
    mesh_view_bindings::{view, lights},
}
#import warbell::alpine::alpine_apply

struct ForestParams {
    // x=detailScale, y=detailStrength, z=variation, w=meanLuminance
    params: vec4<f32>,
    // x=bump_strength, y=quality (0=Low,1=High,2=Ultra), z=macro_variety, w=reserved
    params2: vec4<f32>,
    // Wheel-rut mask world→UV mapping: xy = world min corner, zw = 1/extent (0 = disabled).
    rut_region: vec4<f32>,
    // Realistic forest floor: x = 1 when the scanned layers + mask are bound (`realforest`).
    pbr: vec4<f32>,
    // Forest/road mask world→UV mapping (same contract as rut_region).
    pbr_region: vec4<f32>,
};

@group(#{MATERIAL_BIND_GROUP}) @binding(100) var<uniform> forest: ForestParams;
@group(#{MATERIAL_BIND_GROUP}) @binding(101) var detail_tex: texture_2d<f32>;
@group(#{MATERIAL_BIND_GROUP}) @binding(102) var detail_samp: sampler;
// Ground masks (RG8, `worldmap::ground_mask_image`): R = cart-wheel ruts (`roads::bake_rut_mask`,
// twin grooves beside artery centrelines), G = eroded-bank weight (`worldmap::bank_profile`).
// Fragment-resolution because ~0.5u grooves are far below the 1u vertex-colour grid.
@group(#{MATERIAL_BIND_GROUP}) @binding(103) var rut_tex: texture_2d<f32>;
@group(#{MATERIAL_BIND_GROUP}) @binding(104) var rut_samp: sampler;
// Realistic forest floor (`realforest`): three scanned layers as 2D arrays - 0 litter, 1 moss,
// 2 path - sRGB albedo, OpenGL normal, and linear AO / roughness / metal / HEIGHT (alpha).
@group(#{MATERIAL_BIND_GROUP}) @binding(105) var fp_albedo: texture_2d_array<f32>;
@group(#{MATERIAL_BIND_GROUP}) @binding(106) var fp_normal: texture_2d_array<f32>;
@group(#{MATERIAL_BIND_GROUP}) @binding(107) var fp_ormh: texture_2d_array<f32>;
@group(#{MATERIAL_BIND_GROUP}) @binding(108) var fp_samp: sampler;
// RGBA8 mask: R = forest weight (soft-edged tile mask), G = road strength, B = contact darkening
// around trunks / solid props.
@group(#{MATERIAL_BIND_GROUP}) @binding(109) var fp_mask: texture_2d<f32>;
@group(#{MATERIAL_BIND_GROUP}) @binding(110) var fp_mask_samp: sampler;

// World units covered by one repeat of each forest-floor layer (different on purpose so the
// three repeats never line up), and the deepest parallax displacement in world units.
// The layers are 2048² composites, so one repeat covers a wider patch at the same texel density.
const FP_T0: f32 = 4.6;
const FP_T1: f32 = 5.3;
const FP_T2: f32 = 4.2;
const FP_DEPTH: f32 = 0.20;
// The water plane (`worldmap::SEA_Y`): every river, lake and pool surface sits at this height.
const SEA_Y: f32 = -0.4;

fn fp_uv0(p: vec2<f32>) -> vec2<f32> { return p / FP_T0; }
fn fp_uv1(p: vec2<f32>) -> vec2<f32> { return p / FP_T1 + vec2<f32>(0.37, 0.61); }
fn fp_uv2(p: vec2<f32>) -> vec2<f32> { return p / FP_T2 + vec2<f32>(0.73, 0.19); }

// Per-layer height (ormh.a) at world XZ `p`, explicit gradients so it is legal inside the
// parallax loop / weight branches. Layers with ~0 weight are skipped (returned as 0).
fn fp_heights(p: vec2<f32>, w: vec3<f32>, dx: vec2<f32>, dy: vec2<f32>) -> vec3<f32> {
    var h = vec3<f32>(0.0);
    if w.x > 0.01 { h.x = textureSampleGrad(fp_ormh, fp_samp, fp_uv0(p), 0, dx / FP_T0, dy / FP_T0).a; }
    if w.y > 0.01 { h.y = textureSampleGrad(fp_ormh, fp_samp, fp_uv1(p), 1, dx / FP_T1, dy / FP_T1).a; }
    if w.z > 0.01 { h.z = textureSampleGrad(fp_ormh, fp_samp, fp_uv2(p), 2, dx / FP_T2, dy / FP_T2).a; }
    return h;
}

// Ploughed field strips — a mirror of `castle_ground::FIELDS` (kept in sync by the
// `field_table_matches_shader` test): xy = centre, zw = half extents (x along the furrows when
// it is the longer one), and (yaw, plough). The rows are analytic here: the 2 texel/u masks
// could only carry soft blobs, never straight, evenly spaced ridges.
const FIELD_A = array<vec4<f32>, 6>(
    vec4<f32>(-11.0, 31.0, 6.0, 2.1),
    vec4<f32>(-11.5, 35.6, 6.0, 2.1),
    vec4<f32>(11.5, 33.5, 5.5, 2.2),
    vec4<f32>(-9.5, -33.5, 6.0, 2.2),
    vec4<f32>(16.0, -32.0, 5.0, 2.1),
    vec4<f32>(41.0, 0.0, 2.2, 6.0),
);
const FIELD_B = array<vec2<f32>, 6>(
    vec2<f32>(0.04, 1.0),
    vec2<f32>(0.04, 0.55),
    vec2<f32>(-0.05, 0.85),
    vec2<f32>(-0.03, 0.7),
    vec2<f32>(0.06, 1.0),
    vec2<f32>(0.0, 0.8),
);
// Ridge-to-ridge spacing of the plough rows (world units).
const FURROW_P: f32 = 0.78;

struct FieldHit {
    // 1 within ~1u of a strip (the shader's soil / rows replace the mask's soft blob there).
    zone: f32,
    // Ploughed-soil coverage: the strip with a near-straight edge (a grassy headland outside).
    soil: f32,
    // Row height 0 (furrow) .. 1 (ridge crest), already faded out on the headlands.
    ridge: f32,
    // World-XZ gradient of the row height (per unit), for the relief normal.
    grad: vec2<f32>,
    // Row strength (0 on the headland / outside, `plough` inside).
    rows: f32,
};

fn field_sample(p: vec2<f32>) -> FieldHit {
    var o: FieldHit;
    o.zone = 0.0; o.soil = 0.0; o.ridge = 0.5; o.grad = vec2<f32>(0.0); o.rows = 0.0;
    for (var i = 0u; i < 6u; i = i + 1u) {
        let a = FIELD_A[i];
        let b = FIELD_B[i];
        let d = p - a.xy;
        let sn = sin(b.x);
        let cs = cos(b.x);
        // Same local frame as `castle_ground::field_at`.
        let l = vec2<f32>(cs * d.x - sn * d.y, sn * d.x + cs * d.y);
        let e = max(abs(l.x) - a.z, abs(l.y) - a.w);
        if e > 1.3 {
            continue;
        }
        let long_x = a.z >= a.w;
        let across = select(l.x, l.y, long_x);
        let along = select(l.y, l.x, long_x);
        let half_along = select(a.w, a.z, long_x);
        let half_across = select(a.z, a.w, long_x);
        // A slight hand-ploughed wobble on the edge, never a blob.
        let wob = (ter_noise(p * 1.3 + vec2<f32>(7.0, 3.0)) - 0.5) * 0.18;
        o.zone = 1.0 - smoothstep(0.8, 1.3, e);
        o.soil = 1.0 - smoothstep(-0.12, 0.12, e + wob);
        // Rows stop short of the ends (the headland where the team turned) and of the sides.
        let rows = (1.0 - smoothstep(-0.95, -0.55, abs(along) - half_along + wob))
                 * (1.0 - smoothstep(-0.30, -0.05, abs(across) - half_across + wob));
        // A slight sideways meander so the rows are hand-drawn, not ruled.
        let ac = across + (ter_noise(vec2<f32>(along * 0.35, f32(i) * 7.0)) - 0.5) * 0.10;
        let ph = ac * (6.2831853 / FURROW_P);
        let c = cos(ph);
        // Rounded ridge, narrower furrow: lift the cosine before squaring the profile.
        let r = 0.5 + 0.5 * c;
        let rr = r * r * (3.0 - 2.0 * r);
        let dr = -0.5 * sin(ph) * (6.2831853 / FURROW_P) * 6.0 * r * (1.0 - r);
        o.rows = rows * b.y;
        o.ridge = mix(0.5, rr, o.rows);
        // d/d(across) in local, back to world (inverse of the frame above).
        let gl = select(vec2<f32>(dr, 0.0), vec2<f32>(0.0, dr), long_x) * o.rows;
        o.grad = vec2<f32>(cs * gl.x + sn * gl.y, -sn * gl.x + cs * gl.y);
        break;
    }
    return o;
}

// 2D value-noise hash. The original `fract(sin(p.x*127.1 + p.y*311.7)*43758)` is effectively
// a 1D hash of the dot product `p·(127.1,311.7)`, so cells along that fixed diagonal get
// CORRELATED values — which the bump lighting reveals as straight parallel "ruts" across the
// ground. This is the sine-free Hoskins `hash12`: a genuine 2D hash with no directional
// correlation (and no large-coordinate `sin` precision breakdown).
fn ter_hash(p: vec2<f32>) -> f32 {
    var p3 = fract(vec3<f32>(p.x, p.y, p.x) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

fn ter_noise(p: vec2<f32>) -> f32 {
    let i = floor(p);
    let f = fract(p);
    let a = ter_hash(i);
    let b = ter_hash(i + vec2<f32>(1.0, 0.0));
    let c = ter_hash(i + vec2<f32>(0.0, 1.0));
    let d = ter_hash(i + vec2<f32>(1.0, 1.0));
    // Quintic (C2) interpolation, not the cubic smoothstep. The cubic still has a
    // discontinuous 2nd derivative at every cell edge, which reads as a faint axis-aligned
    // quilt — invisible-ish in albedo but GLARING once the noise drives a normal (the
    // bump), because shading amplifies the gradient kink. Quintic is C2 → smooth gradients,
    // no grid in the lit relief.
    let u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
    return mix(a, b, u.x) + (c - a) * u.y * (1.0 - u.x) + (d - b) * u.x * u.y;
}

// Value noise whose lattice is ROTATED off the world axes. Value noise is built on an
// integer grid, so its features line up with X/Z and stack into a visible square grid
// when several octaves share that alignment. Rotating each octave by a different non-axis
// angle scatters the cells so nothing reinforces into a lattice.
fn ter_noise_rot(p: vec2<f32>, c: f32, s: f32) -> f32 {
    return ter_noise(vec2<f32>(c * p.x - s * p.y, s * p.x + c * p.y));
}

// Pseudo micro-relief height in world XZ for the bump-shading gradient. Tuned to the
// VISIBLE clump scale (periods ~0.5–3 world units) — the very-fine albedo octaves
// (>5/unit) are deliberately left out: at gameplay distance they're sub-pixel and only
// alias/shimmer the normal. Ultra adds one finer octave for crisp near-camera grain.
fn terrain_h(p: vec2<f32>) -> f32 {
    // Each octave on its own rotated lattice (≈19°, 47°, 73°, 101°) so the relief never
    // stacks into an axis-aligned grid.
    var h = ter_noise_rot(p * 0.35, 0.946, 0.326) * 0.50   // broad mounds (~2.8u)
          + ter_noise_rot(p * 0.90, 0.682, 0.731) * 0.35   // clumps      (~1.1u)
          + ter_noise_rot(p * 2.20, 0.292, 0.956) * 0.22;  // fine clumps  (~0.45u)
    if forest.params2.y >= 2.0 {
        h += ter_noise_rot(p * 4.0, -0.191, 0.982) * 0.12; // ultra: near-camera grain
    }
    return h;
}

// Rock/erosion relief for the terrace WALLS, sampled in the face plane: `along` is the
// horizontal tangent down the wall (world X for Z-facing walls, world Z for X-facing) and
// `wy` is world Y. Features run VERTICALLY (erosion runnels): higher frequency along the
// horizontal axis than the vertical one, so the grooves streak top-to-bottom — the look that
// is NATURAL on a cliff (and the exact streak artifact we banned on flat ground).
fn rock_h(along: f32, wy: f32) -> f32 {
    return ter_noise(vec2<f32>(along * 2.2, wy * 0.7)) * 0.6
         + ter_noise(vec2<f32>(along * 5.0, wy * 1.6)) * 0.4;
}

// Lightly de-tiled detail-texture sample. The detail image is a Repeat texture sampled at
// `wp * scale`, wrapping every `1/scale` world units (~5.6u). Now that the texture is fine
// ISOTROPIC grain (no broad blobs, no directional streaks — see `terrain::detail_image`),
// that repeat is invisible on its own; a small low-frequency UV domain-warp finishes the job
// by bending any residual periodic line into a wavy one. A SINGLE sample — the earlier
// rotated second octave was what turned the texture's (then anisotropic) streaks into a
// diagonal crosshatch, so it's gone.
fn sample_detail(wp: vec2<f32>, scale: f32) -> vec3<f32> {
    let warp = vec2<f32>(ter_noise(wp * 0.06 + 4.0), ter_noise(wp * 0.06 + 19.0)) - 0.5;
    return textureSample(detail_tex, detail_samp, wp * scale + warp * 0.4).rgb;
}

// Distance from point `p` to the line segment a→b (analytic capsule SDF core).
fn seg_dist(p: vec2<f32>, a: vec2<f32>, b: vec2<f32>) -> f32 {
    let pa = p - a;
    let ba = b - a;
    let h = clamp(dot(pa, ba) / max(dot(ba, ba), 1e-5), 0.0, 1.0);
    return length(pa - ba * h);
}

// Scattered fallen-twig field in world XZ, baked into the floor texture so the ground reads
// littered EVERYWHERE, not only under a 3D litter prop. One short twig per cell on a ~1.25u
// lattice, each with an INDEPENDENT random position / angle / length — localised segments at
// every orientation, NOT a world-spanning anisotropic streak (the banned flat-ground artifact
// was a single global directional lattice tiling into diagonal bands; random per-cell sticks
// never reinforce into one). Scans the 3×3 neighbourhood so a twig straddling a cell border
// still draws.
//
// A clean SDF segment reads as a flat painted DASH — geometric, "immature", out of place on
// the noisy ground. So this is deliberately organic: the query point is DOMAIN-WARPED (a low
// + high freq pair) so each stick bends and frays instead of running dead straight; the width
// TAPERS to thin ends like a real twig (not a constant-width dash); the edge is softened by a
// noisy band so it's ragged, not vector-crisp. Returns coverage `x` plus an along-stick tone
// `y` (0..1) so the caller can vary the bark colour down its length.
fn twig_field(wp: vec2<f32>, seedoff: f32, base_w: f32) -> vec2<f32> {
    // Bend (low-freq) + fray (high-freq) domain warp.
    let warp = (vec2<f32>(ter_noise(wp * 0.8 + seedoff + 8.0), ter_noise(wp * 0.8 + seedoff + 30.0)) - 0.5) * 1.7
             + (vec2<f32>(ter_noise(wp * 2.6 + seedoff + 3.0), ter_noise(wp * 2.6 + seedoff + 21.0)) - 0.5) * 0.7;
    let q = wp + warp * 0.10;
    let cell = 1.25;
    let ci = floor(q / cell);
    var best_d = 1e9;
    var best_h = 0.0;
    var best_seed = 0.0;
    for (var dy = -1; dy <= 1; dy += 1) {
        for (var dx = -1; dx <= 1; dx += 1) {
            let c = ci + vec2<f32>(f32(dx), f32(dy));
            let r1 = ter_hash(c + seedoff);
            // ~45% of cells carry a twig — sparse, like a real forest floor.
            if (r1 < 0.45) {
                let r2 = ter_hash(c + seedoff + 17.3);
                let r3 = ter_hash(c + seedoff + 41.7);
                let r4 = ter_hash(c + seedoff + 71.1);
                let center = (c + vec2<f32>(r2, r3)) * cell;
                let ang = r4 * 6.28318;
                let dir = vec2<f32>(cos(ang), sin(ang));
                let len = (0.20 + r1 * 0.55) * cell;   // ~0.25–0.8u sticks
                let a = center - dir * len * 0.5;
                let ba = dir * len;
                let pa = q - a;
                let h = clamp(dot(pa, ba) / max(dot(ba, ba), 1e-5), 0.0, 1.0);
                let d = length(pa - ba * h);
                if (d < best_d) {
                    best_d = d;
                    best_h = h;
                    best_seed = r2;
                }
            }
        }
    }
    // Taper: full width mid-stick, thinning to a point at both ends.
    let w = base_w * (0.30 + 0.70 * (1.0 - pow(abs(best_h * 2.0 - 1.0), 1.7)));
    // Ragged, noisy soft edge (not a crisp vector line).
    let edge = 0.008 + 0.014 * ter_noise(wp * 9.0 + seedoff);
    let cov = 1.0 - smoothstep(w, w + edge, best_d);
    let tone = ter_noise(vec2<f32>(best_h * 4.0, best_seed * 13.0));
    return vec2<f32>(cov, tone);
}

@fragment
fn fragment(
    in: VertexOutput,
    @builtin(front_facing) is_front: bool,
) -> FragmentOutput {
    // LOD crossfade discard — MUST come first, exactly as `bevy_pbr::pbr.wgsl` does it.
    // `ForestExtension` overrides only `fragment_shader()`, so this main pass replaces
    // pbr.wgsl wholesale while the depth PREPASS still falls through to `pbr_prepass.wgsl`,
    // which DOES dither. Without this line the two terrain LODs both drew fully in the
    // `TERRAIN_LOD..+BAND` ring while the prepass wrote a 4×4 checkerboard of the two — so
    // `depth_compare: GreaterEqual` resolved to a per-pixel nearest-of-both, and the coarse
    // drape's straight ramp over a mesa tier punched through the cliff walls: the
    // "terrain shows through the mountains" bug. Also the reason `spawn_terrain_sheet`'s
    // "dithered crossfade" comment was aspirational — the dither was never wired.
#ifdef VISIBILITY_RANGE_DITHER
    visibility_range_dither(in.position, in.visibility_range_dither);
#endif

    var pbr_input = pbr_input_from_standard_material(in, is_front);

    let wp = in.world_position.xz;
    let detail_scale = forest.params.x;
    let detail_strength = forest.params.y;
    let variation = forest.params.z;
    let mean = forest.params.w;

    var rgb = pbr_input.material.base_color.rgb;

    // Cliff-face weight. Terrain cliff-wall vertices carry a NEGATIVE alpha "cliffness"
    // (`worldmap::build_terrain_chunk::cliff_wall`); flat ground stays 0 and marsh wetness
    // stays positive, so `-a` cleanly isolates the crag faces for the rock layers below.
    let cliff = clamp(-pbr_input.material.base_color.a, 0.0, 1.0);

    // How green-dominant the base ground is (1 = grass/forest floor, 0 = snow / sand /
    // dirt cliff). The world island runs ONE of these materials over every biome's
    // vertex colours, so the hue-bearing grass layers below must fade out where the
    // ground isn't green — the warm yellow-green drift + green blade imprint were
    // reading as dirt smears on snowfields and cliff walls. Value-only layers stay.
    let green = clamp((rgb.g - max(rgb.r, rgb.b)) * 6.0 + 0.30, 0.0, 1.0);

    // The original vision.ts ground texture — a SUBTLE low-opacity gradient, three layers:
    // (1) fine value mottle (three octaves), amplitude softened a touch from the original.
    //     Each octave on its own rotated lattice (≈19°/47°/73°) so the value-noise cells
    //     don't line up into the axis-aligned brightness grid that read as square "tiles".
    // Coarse mottle (one cheap low-freq octave) always; the two FINER octaves only on High/Ultra.
    // `params2.y` (ground quality lane: Low 0 / High 1 / Ultra 2) is a UNIFORM, so this branch is
    // coherent across the whole draw — on Low the GPU genuinely skips the two extra noise evals.
    // The fine octaves are high-freq grain that's sub-perceptible on the weak GPUs Low targets, but
    // they (and the detail tap below) are the bulk of the per-fragment ground cost there.
    var ter_m = ter_noise_rot(wp * 0.5, 0.946, 0.326) * 0.55;
    if forest.params2.y >= 1.0 {
        ter_m += ter_noise_rot(wp * 1.7, 0.682, 0.731) * 0.30
               + ter_noise_rot(wp * 5.5, 0.292, 0.956) * 0.15;
    }
    rgb *= 0.83 + ter_m * 0.34;

    // (2) large-scale analytic hue + value drift — the soft cloudy patches (cure for
    //     flat green): broad areas drift warm yellow-green ↔ cool deep-green + lighten.
    //     The hue push is gated to green ground; the value drift applies everywhere.
    let ter_big = ter_noise(wp * 0.05) * 0.6 + ter_noise(wp * 0.14) * 0.4;
    let ter_hue = ter_noise(wp * 0.028 + vec2<f32>(11.0, 11.0));
    rgb += (ter_big - 0.5) * variation * vec3<f32>(0.10, 0.09, -0.05) * green;
    rgb *= 1.0 + (ter_hue - 0.5) * variation * 0.40;

    // (2b) cart-wheel ruts (map-character overhaul pass 2): twin darker grooves pressed either
    // side of every road artery, from the baked fragment-resolution mask. A textureSample must
    // stay in UNIFORM control flow, so sample unconditionally (the 1×1 dummy + zero region make
    // this a no-op on roadless grounds); a broken-wear noise keeps the grooves from reading as
    // two ruler lines.
    let rut_uv = (wp - forest.rut_region.xy) * forest.rut_region.zw;
    let rut_in = f32(forest.rut_region.z > 0.0
        && rut_uv.x > 0.0 && rut_uv.x < 1.0 && rut_uv.y > 0.0 && rut_uv.y < 1.0);
    let gmask = textureSample(rut_tex, rut_samp, rut_uv).rg * rut_in;
    // The fields' own analytic rows replace the rut mask's soft furrow blobs.
    let fld = field_sample(wp);
    let fld_on = fld.zone * f32(forest.pbr.x > 0.5) * f32(forest.rut_region.z > 0.0);
    let rut = gmask.r * (1.0 - fld_on);
    let rut_wear = 0.65 + 0.35 * ter_noise(wp * 0.9 + vec2<f32>(31.0, 7.0));
    // 0.55: tuned by A/B shots — 0.22 and even 0.38 drowned under the ±0.17 ground mottle +
    // midday haze/bloom (verification: "ruts invisible"); a 1.0 debug pass proved the sampling
    // chain and read as mud trenches. 0.55·wear ≈ 0.36–0.55 darkening keeps two legible worn
    // grooves without going black.
    rgb *= 1.0 - 0.55 * rut * rut_wear;

    // ── Cliff-rock albedo (the "tekstura urwiska") on flagged crag faces: warped
    //    near-horizontal SEDIMENTARY STRATA + soft-edged FRACTURE PLATES over a
    //    stone-greyed base. Greying keeps a whisper of the vertex-colour biome hue
    //    (sandstone / granite / snow-blue), so desert mesas and snow crags still differ.
    //    Cheap (4 noise evals, no texture tap) and gated per-vertex, so it runs at every
    //    quality tier — the geometry facets need the albedo to read as rock even on Low.
    if cliff > 0.004 {
        let wy = in.world_position.y;
        // Strata bands: high frequency in Y, very low along XZ, undulated by a broad
        // world-space warp so the layers never run ruler-straight.
        let cwarp = (ter_noise(wp * 0.30) - 0.5) * 2.6;
        let strata = ter_noise(vec2<f32>(wy * 1.5 + cwarp, dot(wp, vec2<f32>(0.35, 0.27))));
        // Fracture plates: coarse noise quantised to a few tones with softened edges —
        // the chiseled-slab patchwork of a real crag face.
        let pl = ter_noise(vec2<f32>(dot(wp, vec2<f32>(0.85, 0.62)) + 13.0, wy * 0.85)) * 3.0;
        let plate = (floor(pl) + smoothstep(0.30, 0.70, fract(pl))) / 3.0;
        let clum = dot(rgb, vec3<f32>(0.299, 0.587, 0.114));
        let stone = mix(rgb, vec3<f32>(clum) * vec3<f32>(1.03, 1.0, 0.95), 0.55);
        let rockc = stone * (0.80 + strata * 0.30) * (0.82 + plate * 0.30);
        rgb = mix(rgb, rockc, cliff * 0.88);
    }

    // (3)+(4) only on High/Ultra — same coherent `params2.y` lane as the fine mottle above.
    // (3) is a TEXTURE tap + a domain-warp noise pair (the single most expensive ground op) and
    // (4) is two more low-freq noise evals; both are skipped wholesale on Low, where the weak GPU
    // this preset targets can't afford them and the subtle imprint/scuff variety reads as flat
    // green anyway. The base colour + coarse mottle + drift keep the ground from looking bald.
    if forest.params2.y >= 1.0 {
        // (3) soft grass detail imprint on up-facing fragments, normalised by mean luminance.
        //     Off-grass the imprint collapses to its luminance so snow keeps the blade-scale
        //     value texture without picking up the green cast.
        // Soft slope fade, NOT a hard `step(0.5, …)`. The chamfered terrace lip rolls its
        // normal from ~0.92 (top edge) to ~0.37 (base) across ONE facet, so a hard step cut
        // the grass imprint along a line mid-triangle → a crisp green "wedge" on the cliff
        // lip. `smoothstep` fades the imprint down the lip instead (band matches `topw`
        // above), so the lip keeps grass but melts into the dirt wall with no triangle.
        let top_face = smoothstep(0.35, 0.80, in.world_normal.y);
        let det = sample_detail(wp, detail_scale) / max(mean, 0.01);
        let det_l = dot(det, vec3<f32>(0.2126, 0.7152, 0.0722));
        let det_c = mix(vec3<f32>(det_l), det, green);
        rgb *= mix(vec3<f32>(1.0), det_c, detail_strength * top_face);

        // (4) macro albedo-variety: broad low-freq patches so the field reads as a living meadow
        //     of mottled greens — worn dirt, damp moss, sun-dried gold, lush deep-green — instead
        //     of one flat tone. All green-gated + preset-scaled (`macro_variety`); each on its own
        //     noise offset/frequency so they overlap into organic patches, not a regular quilt.
        //     Kept under ~0.4 mix so it's varied, not camo.
        let variety = forest.params2.z;
        // Worn sun-bleached dirt scuffs (bald spots / trodden paths) — warm + desaturated.
        // Lower thresholds widen each patch and stronger mixes raise the contrast between
        // them, so the field reads as a genuinely varied meadow rather than one flat tone.
        // (Toned down 2026-07-03, player: "ta biała tekstura gruntu mi się nie podoba" — the
        // broad ~50u worn patches + pale soil blotches below washed whole meadows/forest floors
        // toward chalky white under bloom. Rarer, smaller, warmer.)
        let worn = smoothstep(0.66, 0.90, ter_noise(wp * 0.020 + vec2<f32>(5.0, 9.0)));
        rgb = mix(rgb, rgb * vec3<f32>(0.80, 0.70, 0.52), worn * 0.20 * green * variety);
        // Damp moss hollows — cool, rich, slightly darker green.
        let moss = smoothstep(0.52, 0.86, ter_noise(wp * 0.040 + vec2<f32>(19.0, 2.0)));
        rgb = mix(rgb, rgb * vec3<f32>(0.66, 0.90, 0.56), moss * 0.44 * green * variety);
        // Sun-dried golden sweeps — drier grass catching the light (a brighter warm push).
        let dry = smoothstep(0.70, 0.93, ter_noise(wp * 0.015 + vec2<f32>(33.0, 7.0)));
        rgb = mix(rgb, rgb * vec3<f32>(1.06, 1.02, 0.80), dry * 0.10 * green * variety);
        // Lush well-watered patches — deep saturated green.
        let lush = smoothstep(0.56, 0.89, ter_noise(wp * 0.030 + vec2<f32>(2.0, 27.0)));
        rgb = mix(rgb, rgb * vec3<f32>(0.70, 1.03, 0.66), lush * 0.42 * green * variety);

        // ── Forest-floor debris baked into the texture (the "patyki + szare placki"): scattered
        //    twigs and bare-earth / lichen patches, so the floor reads littered EVERYWHERE, not
        //    only where a 3D litter prop happens to sit. Top-faces only (`topd`) + green-gated so
        //    it never smears onto cliff walls / snow / sand; preset-scaled by `variety`.
        let topd = smoothstep(0.35, 0.80, in.world_normal.y);
        let debris_w = topd * green * variety;
        // (a) Bare-earth / lichen blotches — the "szare placki": broad low-freq blobs drifting
        //     the green toward a desaturated grey-tan soil. One main blob field thresholded so
        //     patches are clearly readable, broken up by a finer octave so their edges are ragged
        //     (organic), not clean ovals; a faint grain keeps them from looking painted.
        // Rarer + a warm humus BROWN, not the old grey-tan (0.45,0.44,0.41) that read as bald
        // white patches in the meadow and the forest floor.
        let soil = smoothstep(0.68, 0.84, ter_noise(wp * 0.06 + vec2<f32>(61.0, 13.0)));
        let soil_edge = soil * (0.70 + 0.30 * ter_noise(wp * 0.28 + vec2<f32>(7.0, 51.0)));
        let earth = vec3<f32>(0.34, 0.27, 0.19) * (0.90 + ter_m * 0.20);
        rgb = mix(rgb, earth, soil_edge * 0.48 * debris_w);
        // (b) Scattered twigs (organic — warped/tapered/soft, see `twig_field`): a brown-bark
        //     pass + a sparser, greyer driftwood pass (offset seed so they don't coincide).
        //     Bark colour drifts dark↔mid down each stick (`.y`) so it's not a flat fill.
        let tb = twig_field(wp, 0.0, 0.024);
        let bark = mix(vec3<f32>(0.28, 0.19, 0.11), vec3<f32>(0.45, 0.34, 0.21), tb.y);
        rgb = mix(rgb, bark, tb.x * 0.66 * debris_w);
        let tg = twig_field(wp, 123.4, 0.018);
        let drift = mix(vec3<f32>(0.38, 0.35, 0.30), vec3<f32>(0.55, 0.52, 0.46), tg.y);
        rgb = mix(rgb, drift, tg.x * 0.48 * debris_w);
    }

    // ── Riverbank (`worldmap::bank_profile`) ── the ground mask's G: 1 on the eroded slope, 0 on
    //    the land above its rounded lip. The grass / forest floor rolls over the lip and thins
    //    down the face into bare earth (sooner where the pitch is steep — a cut bank is almost all
    //    earth), and the last few decimetres above the waterline are dark damp soil. All ground
    //    away from inland water (and grounds without the mask) reads bank = 0: a no-op.
    let bank = gmask.g;
    var bank_soil = 0.0;
    var bank_damp = 0.0;
    // Per-channel tint the bank earth carries relative to the forest humus (also applied to the
    // scanned path layer below): sandy loam on a desert brook, grey silt by snow, humus elsewhere.
    var bank_tint = vec3<f32>(1.0);
    var bank_sandy = 0.0;
    if bank > 0.001 {
        let hy = in.world_position.y - SEA_Y;
        let bn = ter_noise(wp * 0.9 + vec2<f32>(13.0, 77.0)) * 0.65 + ter_noise(wp * 2.6 + vec2<f32>(41.0, 5.0)) * 0.35;
        let steep = 1.0 - smoothstep(0.62, 0.96, in.world_normal.y);
        // Ragged grass edge partway down the face; steep pitches go bare at once.
        bank_soil = clamp(smoothstep(0.30, 0.85, bank + (bn - 0.5) * 0.7) * (0.40 + 0.60 * steep)
            + steep * 0.6 * bank, 0.0, 1.0);
        // Capillary wet line: ~0.15–0.4u above the water, wavering with the noise.
        bank_damp = (1.0 - smoothstep(0.02, 0.14 + 0.26 * bn, hy)) * smoothstep(0.0, 0.25, bank);
        bank_soil = max(bank_soil, bank_damp);
        // Bright, non-green ground (sand, snow) lends the soil its own colour, darkened like wet
        // sand; green ground keeps the brown humus.
        let base = pbr_input.material.base_color.rgb;
        let base_l = dot(base, vec3<f32>(0.299, 0.587, 0.114));
        let sandy = smoothstep(0.22, 0.45, base_l) * (1.0 - green) * 0.8;
        bank_sandy = sandy;
        let humus = vec3<f32>(0.29, 0.225, 0.16);
        let earth_c = mix(humus, base * 0.55, sandy);
        bank_tint = earth_c / humus;
        let earth = earth_c * (0.80 + 0.40 * bn);
        rgb = mix(rgb, earth, bank_soil);
        rgb *= 1.0 - 0.48 * bank_damp;
    }

    // ── Realistic forest floor (`realforest`) ── scanned litter / moss / path layers splatted over
    //    the forest by the baked mask, height-blended (pebbles and leaves poke through the moss
    //    instead of a soft cross-fade), with parallax occlusion mapping near the camera so the
    //    litter reads as real depth at grazing angles. Everything here uses explicit-gradient /
    //    explicit-level taps so it stays legal inside the weight branches and the march loop.
    let wp_dx = dpdx(wp);
    let wp_dy = dpdy(wp);
    let fmask_uv = (wp - forest.pbr_region.xy) * forest.pbr_region.zw;
    let fmask4 = textureSampleLevel(fp_mask, fp_mask_samp, fmask_uv, 0.0);
    let fmask = fmask4.rgb;
    // Mask A = the grove field (`biome::forest_grove`): 0 in an open glade, 1 in a dense stand.
    // The 1x1 placeholder mask has no alpha channel worth reading, but it's only bound while the
    // forest floor is off (fp_w = 0), so its value never matters.
    let glade = 1.0 - smoothstep(0.08, 0.40, fmask4.a);
    var fp_w = 0.0;
    var fp_nw = vec3<f32>(0.0, 1.0, 0.0);
    var fp_rough = 1.0;
    var fp_ao = 1.0;
    // Bank earth drawn with the scanned PATH layer (real soil + pebbles) wherever the slope is
    // gentle enough for the planar mapping not to stretch; steeper cut faces keep the procedural
    // earth above plus the wall relief below.
    var bank_fp = 0.0;
    // The forest's own share of the floor: parallax + self-shadow follow it alone, so bank soil
    // off the forest is a flat scanned layer (no ray march) — the march is the floor's big cost.
    var fp_forest = 0.0;
    if forest.pbr.x > 0.5 {
        let edge_n = ter_noise(wp * 0.21 + vec2<f32>(3.0, 41.0)) - 0.5;
        // On a bank the slope gate relaxes, so the forest floor rolls over the lip with the ground
        // instead of fading to bare vertex green there.
        let slope_gate = mix(smoothstep(0.55, 0.85, in.world_normal.y), smoothstep(0.40, 0.70, in.world_normal.y),
            smoothstep(0.0, 0.2, bank));
        fp_w = smoothstep(0.25, 0.75, fmask.r + edge_n * 0.45) * slope_gate * (1.0 - cliff);
        fp_forest = fp_w;
        // The scanned soil is woodland earth with leaf litter in it: only the forest / meadow banks
        // (mask R) take it. Off them — swamp pools, the Blight, rocky / snow / desert brooks — the
        // bank keeps its own procedural earth / wet sand (it used to coat every bank on the map
        // with the forest path, which read as a forest trail laid round the bog pools).
        let bank_scan = smoothstep(0.15, 0.55, fmask.r);
        bank_fp = bank_soil * smoothstep(0.40, 0.70, in.world_normal.y) * (1.0 - cliff) * bank_scan;
        fp_w = max(fp_w, bank_fp);
    }
    if fp_w > 0.002 {
        // Layer weights: trails -> path, broad damp patches -> moss, the rest -> leaf litter.
        // Ragged trail edge: two noise octaves wobble the road mask so the litter eats into the
        // path in tongues instead of along the mask's straight iso-line.
        let edge = (ter_noise(wp * 0.45 + vec2<f32>(17.0, 3.0)) - 0.5) * 0.45
                 + (ter_noise(wp * 1.7 + vec2<f32>(4.0, 29.0)) - 0.5) * 0.25;
        // (No "grass strip between the ruts" carved out of the road field any more: it keyed on a
        // thin G band (0.88-0.97) that also runs just OUTSIDE every rut and along the castle lanes'
        // centrelines, so it drew hairline grass slivers with texel-stepped edges down every road —
        // the stray thin lines on the ground. The kit's clutter still plants tufts between ruts.)
        // Trampled verges: the sward beside a track is worn through to soil in broken patches.
        let verge = smoothstep(0.04, 0.30, fmask.g) * (1.0 - smoothstep(0.55, 0.85, fmask.g))
                  * smoothstep(0.50, 0.78, ter_noise(wp * 0.33 + vec2<f32>(57.0, 11.0)) * 0.7 + ter_noise(wp * 1.1 + vec2<f32>(3.0, 91.0)) * 0.3);
        // Bank earth claims its share of the floor as path (all of it off the forest mask).
        var path = max(max(smoothstep(0.36, 0.86, fmask.g + edge), verge * glade * 0.75), bank_fp / fp_w);
        // Field strips: the soil is the straight-edged strip itself (the mask only knew a frayed
        // blob); a road beside one keeps its own track (road G > any field's 0.84).
        path = mix(path, max(fld.soil, smoothstep(0.86, 0.95, fmask.g) * path), fld_on);
        let mossn = ter_noise_rot(wp * 0.05, 0.946, 0.326) * 0.65 + ter_noise(wp * 0.19 + vec2<f32>(5.0, 9.0)) * 0.35;
        // Moss/grass is the dominant floor (it sits under the green carpet and IS the carpet past
        // its draw range); leaf litter keeps the drier hollows.
        // Glades open to the sun: the grass/moss layer takes over there, litter keeps the groves.
        let moss = clamp(smoothstep(0.30, 0.55, mossn) + glade * 0.7 - (1.0 - glade) * 0.08, 0.0, 1.0);
        var w = vec3<f32>((1.0 - moss) * (1.0 - path), moss * (1.0 - path), path);
        // Height blend: the taller texel of the competing layers wins across a narrow band.
        let h0 = fp_heights(wp, w, wp_dx, wp_dy);
        let hb = w + h0 * 0.6;
        let hm = max(hb.x, max(hb.y, hb.z));
        w = max(hb - (hm - 0.32), vec3<f32>(0.0));
        w = w / max(w.x + w.y + w.z, 1e-4);

        // Parallax occlusion mapping: march the view ray down through the height field
        // (linear search + one secant refine). High: 10 steps to 16u; Ultra: 18 steps to 26u.
        var pw = wp;
        var hit_h = dot(w, h0);
        var shift = vec2<f32>(0.0);
        let q = forest.params2.y;
        let dist = distance(view.world_position.xyz, in.world_position.xyz);
        let pom_far = select(0.0, select(16.0, 26.0, q >= 2.0), q >= 1.0);
        let depth = FP_DEPTH * fp_forest * (1.0 - smoothstep(pom_far * 0.55, pom_far, dist));
        if depth > 0.002 {
            let vdir = normalize(view.world_position.xyz - in.world_position.xyz);
            shift = -vdir.xz / max(vdir.y, 0.2) * depth;
            let steps = select(10, 18, q >= 2.0);
            var prev_d = 0.0;
            var prev_diff = 1.0 - dot(w, h0);
            var hit = 1.0;
            for (var i = 1; i <= steps; i += 1) {
                let d = f32(i) / f32(steps);
                let diff = (1.0 - dot(w, fp_heights(wp + shift * d, w, wp_dx, wp_dy))) - d;
                if diff <= 0.0 {
                    hit = mix(prev_d, d, prev_diff / max(prev_diff - diff, 1e-4));
                    break;
                }
                prev_d = d;
                prev_diff = diff;
            }
            pw = wp + shift * hit;
            hit_h = 1.0 - hit;
        }

        // Height-field self-shadowing toward the sun: march from the parallax hit up the light
        // direction; any texel standing above the ray shades this one. This is what makes the
        // litter / pebbles throw their own tiny shadows (the RDR2 "every leaf has depth" read)
        // instead of a lit decal. Same distance fade as the parallax; 6 taps.
        var self_shadow = 0.0;
        if depth > 0.002 && lights.n_directional_lights > 0u {
            let ldir = lights.directional_lights[0].direction_to_light;
            if ldir.y > 0.05 {
                let lstep = ldir.xz / max(ldir.y, 0.25) * depth;
                for (var k = 1; k <= 6; k += 1) {
                    let t = f32(k) / 6.0;
                    let ray_h = hit_h + t * (1.0 - hit_h);
                    let hk = dot(w, fp_heights(pw + lstep * t * (1.0 - hit_h), w, wp_dx, wp_dy));
                    self_shadow = max(self_shadow, (hk - ray_h) * 7.0);
                }
                self_shadow = clamp(self_shadow, 0.0, 1.0) * (depth / (FP_DEPTH * fp_forest + 1e-4));
            }
        }

        // Final layer taps at the displaced position.
        var alb = vec3<f32>(0.0);
        var nts = vec3<f32>(0.0);
        var orm = vec3<f32>(0.0);
        if w.x > 0.01 {
            let u = fp_uv0(pw);
            let gx = wp_dx / FP_T0;
            let gy = wp_dy / FP_T0;
            alb += w.x * textureSampleGrad(fp_albedo, fp_samp, u, 0, gx, gy).rgb;
            nts += w.x * (textureSampleGrad(fp_normal, fp_samp, u, 0, gx, gy).rgb * 2.0 - 1.0);
            orm += w.x * textureSampleGrad(fp_ormh, fp_samp, u, 0, gx, gy).rgb;
        }
        if w.y > 0.01 {
            let u = fp_uv1(pw);
            let gx = wp_dx / FP_T1;
            let gy = wp_dy / FP_T1;
            var a1 = textureSampleGrad(fp_albedo, fp_samp, u, 1, gx, gy).rgb;
            var n1 = textureSampleGrad(fp_normal, fp_samp, u, 1, gx, gy).rgb * 2.0 - 1.0;
            var o1 = textureSampleGrad(fp_ormh, fp_samp, u, 1, gx, gy).rgb;
            // Open ground (the castle meadow, the village, forest glades) is one wide sheet of this
            // layer, and its bare-soil blotches repeat every FP_T1 into a polka-dot grid. Break it:
            // a second tap on a rotated (~37 deg), rescaled lattice, cross-faded in broad patches...
            if glade > 0.01 {
                let rot = mat2x2<f32>(0.80, 0.60, -0.60, 0.80);
                let k = 1.0 / (FP_T1 * 1.37);
                let ru = rot * pw * k + vec2<f32>(0.21, 0.47);
                let rgx = rot * wp_dx * k;
                let rgy = rot * wp_dy * k;
                let t = smoothstep(0.30, 0.70, ter_noise(wp * 0.16 + vec2<f32>(7.0, 3.0))) * glade;
                a1 = mix(a1, textureSampleGrad(fp_albedo, fp_samp, ru, 1, rgx, rgy).rgb, t);
                n1 = mix(n1, textureSampleGrad(fp_normal, fp_samp, ru, 1, rgx, rgy).rgb * 2.0 - 1.0, t);
                o1 = mix(o1, textureSampleGrad(fp_ormh, fp_samp, ru, 1, rgx, rgy).rgb, t);
                // ...and past mid range, where even two lattices read as a dotted moire, fade to the
                // layer's mean (its last mip) and the flat normal; the broad drifts below carry it.
                let far = smoothstep(14.0, 40.0, dist) * glade * 0.7;
                if far > 0.0 {
                    a1 = mix(a1, textureSampleLevel(fp_albedo, fp_samp, vec2<f32>(0.5), 1, 12.0).rgb, far);
                    n1 = mix(n1, vec3<f32>(0.0, 0.0, 1.0), far);
                    o1 = mix(o1, textureSampleLevel(fp_ormh, fp_samp, vec2<f32>(0.5), 1, 12.0).rgb, far);
                }
            }
            alb += w.y * a1;
            nts += w.y * n1;
            orm += w.y * o1;
        }
        if w.z > 0.01 {
            let u = fp_uv2(pw);
            let gx = wp_dx / FP_T2;
            let gy = wp_dy / FP_T2;
            alb += w.z * textureSampleGrad(fp_albedo, fp_samp, u, 2, gx, gy).rgb;
            nts += w.z * (textureSampleGrad(fp_normal, fp_samp, u, 2, gx, gy).rgb * 2.0 - 1.0);
            orm += w.z * textureSampleGrad(fp_ormh, fp_samp, u, 2, gx, gy).rgb;
        }
        // Broad value drift so the repeats never read as a grid from a distance.
        alb *= 0.84 + 0.32 * (ter_noise(wp * 0.07 + vec2<f32>(9.0, 2.0)) * 0.6 + ter_noise(wp * 0.23) * 0.4);
        // Broad hue drift (cure for the uniform ochre floor): sun-dried gold <-> fresh green
        // patches, fresher in the glades; the trail itself keeps its earth tone.
        let hue_n = ter_noise(wp * 0.031 + vec2<f32>(23.0, 61.0));
        let fresh = clamp(hue_n * 0.8 + glade * 0.35 - 0.05, 0.0, 1.0) * (1.0 - w.z);
        alb *= mix(vec3<f32>(1.0, 0.95, 0.85), vec3<f32>(0.80, 1.0, 0.76), fresh);
        // Pull the scanned floor's mustard back toward olive / earth (it read garish in low sun).
        alb = mix(vec3<f32>(dot(alb, vec3<f32>(0.3, 0.59, 0.11))), alb, 0.85);
        // Open meadow (the castle meadow, the village, glades): the scanned grass/clover layer reads
        // as dry straw-mustard on its own; pull it toward a living sward green (luminance kept, so it
        // stays a photo texture, never the old flat neon lawn), lusher in broad patches.
        let sward = glade * (1.0 - w.z);
        if sward > 0.01 {
            let al = dot(alb, vec3<f32>(0.2126, 0.7152, 0.0722));
            let lushn = smoothstep(0.30, 0.75, ter_noise(wp * 0.045 + vec2<f32>(3.0, 17.0)));
            // Late-summer meadow: mixed green with straw-gold highlights, not one mustard sheet.
            // Damp (deep green, a touch darker): broad lush patches, low ground near water, the
            // shade of the wood edge. Dry (straw-gold, paler): broad sun-baked swells, slopes.
            let dryn = smoothstep(0.40, 0.80, ter_noise_rot(wp * 0.022, 0.682, 0.731) * 0.7
                                              + ter_noise(wp * 0.085 + vec2<f32>(11.0, 2.0)) * 0.3);
            let low = 1.0 - smoothstep(0.3, 1.8, in.world_position.y - SEA_Y);
            let damp = clamp(lushn * 0.7 + (1.0 - glade) * 0.55 + low * 0.6 - dryn * 0.6
                             - (1.0 - in.world_normal.y) * 2.0, 0.0, 1.0);
            var tint = mix(vec3<f32>(0.74, 1.0, 0.50), vec3<f32>(0.62, 1.0, 0.44), damp);
            tint = mix(tint, vec3<f32>(1.0, 0.90, 0.58), dryn * (1.0 - damp) * 0.75);
            // Straw-gold tufts at the clump scale: seed heads and dry blades catching the sun.
            let straw = smoothstep(0.58, 0.86, ter_noise_rot(wp * 0.75, 0.292, 0.956)) * (1.0 - damp * 0.7);
            tint = mix(tint, vec3<f32>(1.0, 0.88, 0.58), straw * 0.45);
            let lumw = vec3<f32>(0.2126, 0.7152, 0.0722);
            let sw = mix(vec3<f32>(al) * tint / dot(tint, lumw), alb, 0.15)
                   * mix(0.98, 0.80, damp) * (1.0 + 0.10 * straw);
            alb = mix(alb, sw, sward * 0.92);
        }
        // Micro self-shadow (above), contact darkening where roots / stones meet the floor (mask
        // B), and the cart-wheel ruts pressed back into the scanned path as damp, darker grooves
        // (the procedural rut tint applied earlier is overwritten by this mix).
        alb *= 1.0 - 0.4 * self_shadow;
        alb *= 1.0 - 0.35 * fmask.b;
        // Plough furrows (`castle_ground::field_at`, fields carry G ~0.3-0.84, roads ~1 at their ruts):
        // deeper, darker furrows and sun-dried pale ridges, so the strips read as ploughed rows.
        alb *= 1.0 - 0.45 * rut * rut_wear;
        // Plough rows: damp dark furrow bottoms, sun-dried crumbly crests.
        let frow = fld.rows * fld_on * fld.soil;
        alb *= mix(1.0, mix(0.38, 1.25, fld.ridge), frow);
        // Wet mud + puddles on the trail: the path layer darkens toward damp earth, and water
        // pools in its LOW texels (height below a noise-varied water line, deeper in the ruts).
        // Puddles are near-black, glassy and flat, so the IBL sky and sun glint off them.
        let damp = w.z * (0.45 + 0.55 * ter_noise(wp * 0.11 + vec2<f32>(41.0, 7.0)));
        alb *= 1.0 - 0.22 * damp;
        alb *= mix(vec3<f32>(1.0), bank_tint, bank_fp / fp_w) * (1.0 - 0.48 * bank_damp);
        // Small, scattered puddles: mostly IN the ruts, occasionally in a dip — never a flooded track.
        let pocket = smoothstep(0.62, 0.85, ter_noise(wp * 0.33 + vec2<f32>(71.0, 5.0)));
        let water_line = smoothstep(0.70, 0.92, ter_noise(wp * 0.16 + vec2<f32>(13.0, 57.0))) * 0.35 + rut * 0.32 * pocket;
        // No puddles standing on a bank slope (the bank's own damp band handles the wet look).
        let puddle = clamp((water_line - hit_h) * 10.0, 0.0, 1.0) * w.z * smoothstep(0.5, 0.8, path)
            * (1.0 - smoothstep(0.0, 0.2, bank));
        alb = mix(alb, alb * 0.16, puddle);
        rgb = mix(rgb, alb, fp_w);
        // Tangent frame of the planar XZ mapping: u runs along +X, v along +Z, and an OpenGL
        // normal map's +Y (image up = decreasing v) therefore points toward -Z.
        let gn = normalize(in.world_normal);
        // +X projected off the normal — degenerate (normalize(0) = NaN) on a face whose normal IS ±X
        // (an X-facing bank / terrace wall), which drew those wall slivers as black stair-step lines;
        // fall back to +Z there.
        let tx = select(normalize(vec3<f32>(1.0, 0.0, 0.0) - gn * gn.x),
                       normalize(cross(vec3<f32>(0.0, 0.0, 1.0), gn)), abs(gn.x) > 0.98);
        let bz = cross(gn, tx);
        let n_ts = vec3<f32>(nts.xy * 1.7, max(nts.z, 0.2));
        var rut_tilt = vec3<f32>(0.0);
        if rut > 0.003 {
            let ro = 0.22 * forest.rut_region.zw;
            let rgx = textureSampleLevel(rut_tex, rut_samp, rut_uv + vec2<f32>(ro.x, 0.0), 0.0).r
                    - textureSampleLevel(rut_tex, rut_samp, rut_uv - vec2<f32>(ro.x, 0.0), 0.0).r;
            let rgz = textureSampleLevel(rut_tex, rut_samp, rut_uv + vec2<f32>(0.0, ro.y), 0.0).r
                    - textureSampleLevel(rut_tex, rut_samp, rut_uv - vec2<f32>(0.0, ro.y), 0.0).r;
            // Height = -0.12 * rut  ->  N ~ (0.12 * drut/dx, 1, 0.12 * drut/dz); the taps are 0.44u apart.
            rut_tilt = vec3<f32>(rgx, 0.0, rgz) * (0.12 / 0.44) * 2.2 * rut_in;
        }
        // Row relief: ~0.16u ridges, so the sun rakes light/dark bands along every row.
        rut_tilt -= vec3<f32>(fld.grad.x, 0.0, fld.grad.y) * 0.16 * fld_on * fld.soil;
        fp_nw = normalize(mix(tx * n_ts.x + bz * n_ts.y + gn * n_ts.z + rut_tilt, gn, puddle));
        fp_ao = orm.r;
        // Dry packed earth is matte: keep the trail rough so only real puddles glint.
        fp_rough = mix(max(orm.g, 0.82 * w.z) * mix(1.0, 0.85, rut * rut_wear), 0.04, puddle);
    }

    // Clamp alpha ≥ 0 on write-back: the negative cliffness flag has served its purpose and
    // must not leak into lighting/wetness (the wet gate below reads this same channel).
    pbr_input.material.base_color = vec4<f32>(max(rgb, vec3<f32>(0.0)), max(pbr_input.material.base_color.a, 0.0));

    // ── Normal perturbation (bump) — the cure for "flat". The ground geometry is dead-flat,
    //    so every fragment was lit at the same angle. Build a height field from the same
    //    noise the colour uses, take its world-XZ gradient (finite difference), and tilt the
    //    shading normal `pbr_input.N` by it. Now grass clumps catch the sun on one side and
    //    shadow on the other → relief. Weighted to near-flat ground (`topw`) so vertical
    //    cliff faces keep their true normal. SHADOWS still sample the flat `world_normal`
    //    (lighting uses `N`), so there are no fake self-shadow artifacts.
    // `bump` is a uniform, so this branch is coherent across the draw: when the preset
    // disables relief (Low → bump 0) the 4 height taps are skipped entirely — the relief is
    // free on weak GPUs while the cheap anti-grid colour fixes above still apply. `N` keeps
    // its default (flat `world_normal`) in that case.
    let bump = forest.params2.x;
    if bump > 0.001 {
        let gn = normalize(in.world_normal);
        let topw = smoothstep(0.35, 0.80, gn.y);
        // Small offset so the finite difference resolves the clump-scale octaves (a large
        // offset spans whole noise cells and cancels the gradient → flat). The RAW difference
        // (not the true 1/2e gradient) is deliberately kept: the true gradient of these
        // octaves is ~2, which tilts the normal ~70° and catches cool sky-ambient
        // (washed-out); the raw diff at this small offset stays a tame ~0.2 → gentle relief.
        let e = 0.18;
        let hx = terrain_h(wp + vec2<f32>(e, 0.0)) - terrain_h(wp - vec2<f32>(e, 0.0));
        let hz = terrain_h(wp + vec2<f32>(0.0, e)) - terrain_h(wp - vec2<f32>(0.0, e));
        var n2 = normalize(gn + vec3<f32>(-hx, 0.0, -hz) * bump * topw * 1.35);

        // Side-face rock relief on the terrace WALLS. The top relief above is an XZ height
        // field — meaningless across a near-vertical face (XZ barely moves down a wall), so
        // walls got nothing and read as flat painted blocks. Give them their own relief in
        // the face plane (horizontal tangent + world Y) so the bevelled/sloped terrace faces
        // read as eroded rock/dirt. `sidew` is 1 on walls, 0 on tops; with `bump` it's free
        // on Low. Composes on top of `n2` so the bevel keeps a touch of the top relief.
        let sidew = 1.0 - smoothstep(0.30, 0.72, gn.y);
        if sidew > 0.001 {
            let wy = in.world_position.y;
            var along = wp.x;                  // Z-facing wall runs along world X
            var tang = vec3<f32>(1.0, 0.0, 0.0);
            if abs(gn.x) > abs(gn.z) {
                along = wp.y;                  // X-facing wall runs along world Z (wp = world.xz)
                tang = vec3<f32>(0.0, 0.0, 1.0);
            }
            let e2 = 0.18;
            let dha = rock_h(along + e2, wy) - rock_h(along - e2, wy);
            let dhy = rock_h(along, wy + e2) - rock_h(along, wy - e2);
            // Flagged crag faces get a stronger relief push — the displaced facet geometry
            // plus deeper runnels is what sells the rock; plain dirt banks keep the old 0.7.
            n2 = normalize(n2 - (tang * dha + vec3<f32>(0.0, 1.0, 0.0) * dhy) * bump * (0.7 + cliff * 0.5) * sidew);
            // Subtle crevice darkening so the relief reads in albedo too, not only in shading.
            let crev = rock_h(along, wy);
            let dk = mix(1.0, 0.82 + crev * 0.30, sidew);
            pbr_input.material.base_color = vec4<f32>(pbr_input.material.base_color.rgb * dk, pbr_input.material.base_color.a);
        }

        // ── Cavity ambient occlusion — the depth cue normal-tilt alone CAN'T give, and the
        //    single biggest reason a flat ground "fakes 3D". A tilted shading normal still
        //    catches ambient from every direction, so under the bright sky-ambient here the
        //    raised clumps read shaded-on-one-side but never DEEP. Baking soft self-shadow
        //    into the hollows of the SAME height field (so albedo + relief agree) carves the
        //    grooves the eye reads as real geometry — exactly what gives a photo-relief
        //    root/dirt texture its depth, but procedural (no baked map, biome-agnostic).
        //    Top faces only (`topw`); value-only so it's safe on grass/dirt/snow with no hue
        //    cast; entirely inside the `bump` branch so it's free on Low (relief off there).
        let h0 = terrain_h(wp);
        // (a) broad mound AO: darken the low ground BETWEEN clumps. Wide range + a low floor
        //     so hollows go genuinely deep (~0.46×), not a faint tint.
        let mound = smoothstep(0.10, 0.82, h0);
        // (b) crease network: three rotated octaves (≈36°/53°/73°) so the grooves are dense
        //     and read at both the clump scale and crisp near-camera detail, never lining up
        //     into an axis grid.
        let crease = ter_noise_rot(wp * 1.7, 0.81, 0.59) * 0.34
                   + ter_noise_rot(wp * 3.3, 0.60, 0.80) * 0.40
                   + ter_noise_rot(wp * 6.7, 0.29, 0.957) * 0.26;
        let groove = smoothstep(0.32, 0.70, crease);
        // Deepest where a broad hollow AND a fine groove coincide; strong sun-kissed crowns on
        // the mound tops so the relief pops both ways (bright peaks ↔ dark pits).
        let ao = mix(0.56, 1.0, mound) * mix(0.72, 1.0, groove);
        let crown = 1.0 + smoothstep(0.62, 1.0, h0) * 0.20;
        // The scanned forest floor brings its own baked AO - don't stack the procedural cavity on it.
        let shade = mix(mix(1.0, ao * crown, topw), 1.0, fp_w);
        pbr_input.material.base_color = vec4<f32>(pbr_input.material.base_color.rgb * shade, pbr_input.material.base_color.a);

        pbr_input.N = n2;
    }

    // Forest floor: its normal map + AO + roughness replace the procedural relief.
    if fp_w > 0.002 {
        pbr_input.N = normalize(mix(pbr_input.N, fp_nw, fp_w));
        pbr_input.diffuse_occlusion *= vec3<f32>(mix(1.0, fp_ao, fp_w * 0.6));
        pbr_input.material.perceptual_roughness = mix(pbr_input.material.perceptual_roughness, fp_rough, fp_w);
    }

    // Alpine terrain: snow / meadow / scree / rock over the mountains and the snow line
    // (`alpine.wgsl`, a no-op until `alpine::patch_terrain` binds its layers).
    let wp3_dx = dpdx(in.world_position.xyz);
    let wp3_dy = dpdy(in.world_position.xyz);
    let alp_road = select(0.0, fmask.g, forest.pbr.x > 0.5);
    // Open grass (and glades) under the scanned floor still take the alpine meadow where its zone
    // reaches (the apron round the snow biome); only the wooded floor skips it, as before.
    let alp_skip = select(fp_w, fp_w * (1.0 - glade), forest.pbr.x > 0.5);
    let alp_k = alpine_apply(&pbr_input, in.world_position.xyz, in.world_normal, cliff, alp_skip, alp_road, wp3_dx, wp3_dy, forest.params2.y);

    // ── Wet ground (marsh) — the vertex-colour ALPHA carries a per-vertex wetness (0 = dry … 1 =
    //    standing bog), which `worldmap::ground_color` feathers over the biome BLEND band. Lower the
    //    roughness toward a damp sheen by it, so the marsh catches a broad specular highlight AND the
    //    wet look blends smoothly across the swamp↔grass boundary instead of switching per material
    //    sheet (the tile-square "kwadraty" a player saw where the swamp begins). Every terrain sheet
    //    runs this identically, so a shared boundary vertex resolves the SAME roughness from either
    //    side — no seam. A no-op (wet≈0) on all dry ground, so grass/sand/snow are unaffected.
    //    The swamp also gets its OWN floor here (not the forest's litter): dark peaty mud mottled
    //    with wet moss, and shallow standing water in the low hollows — near-black, glassy, flat —
    //    so only the water glints; the mud / moss stay matte (a 0.40 sheen mirrored the bright
    //    foggy sky off the dark peat at grazing angles - the whole bog read pale sage-grey).
    let wet = clamp(pbr_input.material.base_color.a, 0.0, 1.0) * (1.0 - alp_k) * (1.0 - fp_w);
    if wet > 0.001 {
        let sp = in.world_position.xz;
        let mott = ter_noise_rot(sp * 0.13, 0.81, 0.59) * 0.6 + ter_noise_rot(sp * 0.41, 0.29, 0.957) * 0.4;
        let grain = ter_noise_rot(sp * 2.1, 0.60, 0.80);
        // Blackwater peat: darker than the forest's leaf litter (it reads pale under the swamp's
        // thick fog + lifted fill otherwise).
        let mud = vec3<f32>(0.036, 0.028, 0.020);
        let wmoss = vec3<f32>(0.030, 0.044, 0.017);
        let mossk = smoothstep(0.45, 0.66, mott);
        let floor_c = mix(mud, wmoss, mossk) * (0.78 + 0.44 * grain);
        let src = pbr_input.material.base_color.rgb;
        // Keep a little of the vertex colour's own variation (and the bank / shore tints).
        var swamp_rgb = mix(src, mix(floor_c, src * 0.3, 0.15), smoothstep(0.0, 0.6, wet));
        // Open-marsh blackwater: broad standing sheets between the reed beds (lower frequency +
        // a higher cut than the "smaller, rarer" pass — the swamp proper is mostly water now).
        // `wet` is already faded to 0 over the Blight, so its trampled mud stays dry.
        // The fine octave only frays the shoreline (a strong one strewed tiny black puddle specks).
        let pool_n = ter_noise_rot(sp * 0.22, 0.95, 0.31) * 0.82 + ter_noise_rot(sp * 0.9, 0.47, 0.88) * 0.18;
        let standing = (1.0 - smoothstep(0.37, 0.43, pool_n)) * smoothstep(0.55, 0.9, wet)
            * smoothstep(0.90, 0.98, in.world_normal.y) * (1.0 - cliff);
        // Darken FIRST, gloss LAST: with both on the same ramp the half-dark, half-glossy shoreline
        // band mirrored the bright sky as a white outline round every sheet.
        swamp_rgb = mix(swamp_rgb, swamp_rgb * 0.22 + vec3<f32>(0.004, 0.006, 0.004), sqrt(standing));
        pbr_input.material.base_color = vec4<f32>(swamp_rgb, pbr_input.material.base_color.a);
        let rw = pbr_input.material.perceptual_roughness;
        let gloss = standing * standing;
        pbr_input.material.perceptual_roughness = mix(mix(rw, 0.88, wet), 0.05, gloss);
        pbr_input.N = normalize(mix(pbr_input.N, normalize(in.world_normal), gloss));
    }

    // Damp bank soil just above the waterline: a soft wet sheen, glossiest at the water's edge.
    if bank_damp > 0.001 {
        let rb = pbr_input.material.perceptual_roughness;
        pbr_input.material.perceptual_roughness = mix(rb, 0.34, bank_damp);
    }

    // Ultra grass sheen: drop roughness a touch on green ground so the sun throws a lush,
    // slightly specular highlight across the new relief. Subtle; green-gated.
    if forest.params2.y >= 2.0 {
        let r0 = pbr_input.material.perceptual_roughness;
        pbr_input.material.perceptual_roughness = mix(r0, r0 * 0.82, green * (1.0 - alp_k));
    }

    var out: FragmentOutput;
    // NaN backstop: a degenerate normal (normalize of a zero blend) or albedo must never reach the
    // lighting — one bad fragment draws as a crisp black hairline. Checked on the bits, so a
    // fast-math compiler can't fold the test away.
    let n_bad = any((bitcast<vec3<u32>>(pbr_input.N) & vec3<u32>(0x7fffffffu)) >= vec3<u32>(0x7f800000u))
        || dot(pbr_input.N, pbr_input.N) < 0.25;
    let c_bad = any((bitcast<vec4<u32>>(pbr_input.material.base_color) & vec4<u32>(0x7fffffffu)) >= vec4<u32>(0x7f800000u));
    pbr_input.N = select(pbr_input.N, normalize(in.world_normal), n_bad);
    pbr_input.material.base_color = select(pbr_input.material.base_color, vec4<f32>(0.25, 0.22, 0.16, 0.0), c_bad);
    if (pbr_input.material.flags & STANDARD_MATERIAL_FLAGS_UNLIT_BIT) == 0u {
        out.color = apply_pbr_lighting(pbr_input);
    } else {
        out.color = pbr_input.material.base_color;
    }
    out.color = main_pass_post_lighting_processing(pbr_input, out.color);
    // Terrain is opaque, but this shader hijacks base_color.a as a DATA channel (per-vertex
    // wetness ≥ 0, negative = cliff flag), and unlike stock pbr.wgsl it never runs
    // `alpha_discard`, whose Opaque branch is what forces a back to 1.0. Without this, all
    // dry ground writes a≈0 into the HDR target and every alpha-preserving downstream pass
    // (DoF/godrays/atmospherics/outline forward `scene.a` verbatim) delivers a see-through
    // ground to any alpha-aware consumer (upscale blit, screenshots, compositors).
    out.color.a = 1.0;
    return out;
}
