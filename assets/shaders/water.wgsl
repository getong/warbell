// Realistic water — FRAGMENT override of `ExtendedMaterial<StandardMaterial, WaterExt>`: the ONE
// opaque material for the sea, rivers, lake and bog pools (see `src/water.rs`). Single pass, no
// extra render targets, six ripple-map taps + three field taps per fragment:
//   1. NORMAL from the baked tileable slope map (`water::ripple_map`) in three layers — broad swell
//      (open water only), mid chop, fine capillaries — at unrelated scales and rotations so the
//      tile never reads. River layers are FLOW-MAPPED along the baked current (two-phase, Valve's
//      Portal 2 scheme); still water only drifts. The mips' slope variance is folded into the GGX
//      roughness, so distant water widens the sun into a glitter path instead of shimmering.
//   2. BODY by Beer–Lambert absorption over a depth SYNTHESISED from the baked bank distance (the
//      terrain has no underwater geometry, so the depth prepass can't measure it): the silty bed
//      shows through at the banks, deep water converges on its in-scattered colour — clear teal
//      sea / lake, greener silty rivers, tannin-brown bog.
//   3. REFLECTION is Bevy's own PBR: F0 ≈ 0.02 Fresnel of the environment map + GGX sun / moon
//      glints. This shader only OCCLUDES it — a two-tap march of the bank field along the
//      reflected ray darkens the sky where the far bank would be mirrored (the dark treeline band
//      every real lake has), and night dims the baked daytime environment map.
//   4. A thin, broken foam line hugging the bank (none on the bog).
// Fog, haze, DoF and tonemapping all apply as on any opaque surface — the water is in the prepass.

#import bevy_pbr::{
    pbr_fragment::pbr_input_from_standard_material,
    pbr_functions::{apply_pbr_lighting, main_pass_post_lighting_processing},
    forward_io::{VertexOutput, FragmentOutput},
    mesh_view_bindings::{globals, lights},
}

struct WaterParams {
    // x = ripple strength (normal-tilt multiplier, 1 = as authored), y = river flow speed (world
    // units/s at a baked flow of 1), z = shore-foam strength, w = unused
    params: vec4<f32>,
    // Water-field mapping: xy = world-space min corner, zw = 1 / world extent.
    region: vec4<f32>,
};

@group(#{MATERIAL_BIND_GROUP}) @binding(100) var<uniform> water: WaterParams;
// RGBA8 water field (`worldmap::bake_water_field`, linear-filtered): R = signed distance to the
// bank (−SHORE_LAND … +SHORE_MAX world units), G = bog mask, BA = river flow (0.5-biased XZ).
@group(#{MATERIAL_BIND_GROUP}) @binding(101) var field_tex: texture_2d<f32>;
@group(#{MATERIAL_BIND_GROUP}) @binding(102) var field_samp: sampler;
// Tileable slope map (`water::ripple_map`, repeat + mipmapped + anisotropic): RG = slope
// (0.5-biased), B = the slope std-dev a mip averaged away, A = height.
@group(#{MATERIAL_BIND_GROUP}) @binding(103) var ripple_tex: texture_2d<f32>;
@group(#{MATERIAL_BIND_GROUP}) @binding(104) var ripple_samp: sampler;

// Keep in sync with `worldmap::SHORE_MAX` / `worldmap::SHORE_LAND`.
const SHORE_MAX: f32 = 8.0;
const SHORE_LAND: f32 = 1.0;

struct Field {
    shore: f32,
    bog: f32,
    flow: vec2<f32>,
};

fn water_field(p: vec2<f32>) -> Field {
    var f: Field;
    let uv = (p - water.region.xy) * water.region.zw;
    // Outside the baked square = open ocean: deep, still, clear. (Clamp-to-edge would smear the
    // border texels across the whole off-texture sea — "the white stripe through the map".)
    if any(uv < vec2<f32>(0.0)) || any(uv > vec2<f32>(1.0)) {
        f.shore = SHORE_MAX;
        f.bog = 0.0;
        f.flow = vec2<f32>(0.0);
        return f;
    }
    let s = textureSampleLevel(field_tex, field_samp, uv, 0.0);
    f.shore = s.r * (SHORE_LAND + SHORE_MAX) - SHORE_LAND;
    f.bog = s.g;
    f.flow = (s.ba * 255.0 - 128.0) / 127.0; // 128 = still
    return f;
}

// One ripple-map tap at world `p`, layer rotation `cs` = (cos, sin), `scale` = world units per
// tile. Returns (world-XZ slope, slope std-dev, height).
fn ripple(p: vec2<f32>, cs: vec2<f32>, scale: f32) -> vec4<f32> {
    let uv = vec2<f32>(cs.x * p.x - cs.y * p.y, cs.y * p.x + cs.x * p.y) / scale;
    let c = textureSample(ripple_tex, ripple_samp, uv);
    let g = c.rg * 2.0 - 1.0;
    // Rotate the slope back into world XZ (transpose of the uv rotation).
    return vec4<f32>(cs.x * g.x + cs.y * g.y, cs.x * g.y - cs.y * g.x, c.b, c.a);
}

// Flow-mapped layer: two taps half a cycle apart, each advected along `flow` and snapped back
// while its weight is zero, blended variance-preserving so the chop doesn't pulse flatter
// mid-cycle. With zero flow both taps sit still and only `drift` moves them.
fn flowed(p: vec2<f32>, drift: vec2<f32>, flow: vec2<f32>, cs: vec2<f32>, scale: f32, cycle: f32, t: f32) -> vec4<f32> {
    let ph0 = fract(t / cycle);
    let ph1 = fract(t / cycle + 0.5);
    let a = ripple(p + drift - flow * (ph0 * cycle), cs, scale);
    // Offset the second tap's pattern so the two phases don't show the same waves.
    let b = ripple(p + drift - flow * (ph1 * cycle) + vec2<f32>(0.37, 0.71) * scale, cs, scale);
    let w0 = 1.0 - abs(2.0 * ph0 - 1.0);
    let w1 = 1.0 - w0;
    let k = inverseSqrt(w0 * w0 + w1 * w1);
    return vec4<f32>((a.xy * w0 + b.xy * w1) * k, sqrt(a.z * a.z * w0 + b.z * b.z * w1), a.w * w0 + b.w * w1);
}

@fragment
fn fragment(
    in: VertexOutput,
    @builtin(front_facing) is_front: bool,
) -> FragmentOutput {
    var pbr_input = pbr_input_from_standard_material(in, is_front);

    let t = globals.time;
    let p = in.world_position.xz;
    let V = pbr_input.V;

    let fld = water_field(p);
    let shore = max(fld.shore, 0.0);
    let bog = fld.bog;
    let flow_amt = min(length(fld.flow), 1.0);
    let river = smoothstep(0.05, 0.35, flow_amt) * (1.0 - bog);
    let flow = fld.flow * water.params.y;
    // 0 in channels / at the banks → 1 on the open sea and mid-lake: a swell needs fetch.
    let open = smoothstep(2.0, 7.0, shore) * (1.0 - bog);

    // ── 1. Normal ───────────────────────────────────────────────────────────────
    let wind = vec2<f32>(0.81, 0.59);
    let l0 = ripple(p + wind * (t * 0.35), vec2<f32>(0.6216, 0.7833), 23.0);
    let l1 = flowed(p, wind * (t * 0.12), flow, vec2<f32>(0.9394, 0.3429), 6.0, 2.2, t);
    let l2 = flowed(p, vec2<f32>(-0.45, 0.89) * (t * 0.09), flow * 1.3, vec2<f32>(-0.5474, 0.8369), 1.9, 1.3, t);
    // Tilt per layer. The bog lies nearly flat; a river's current roughens its chop.
    let k = water.params.x * mix(1.0, 0.25, bog);
    let k0 = 0.12 * open * k;
    let k1 = mix(0.16, 0.22, river) * k;
    let k2 = 0.11 * k;
    let slope = l0.xy * k0 + l1.xy * k1 + l2.xy * k2;
    let N = normalize(vec3<f32>(-slope.x, 1.0, -slope.y));
    // Slope variance the mips filtered out → extra GGX width (Toksvig / LEAN-style): far water
    // spreads the sun into a soft glitter path; the calm floor keeps near glints sharp.
    let sv = vec3<f32>(l0.z * k0, l1.z * k1, l2.z * k2);
    let alpha = sqrt(0.03 * 0.03 + dot(sv, sv));

    // ── 2. Body: Beer–Lambert over the synthesised depth ───────────────────────
    // Gently shelving: ~0.8 u deep a unit out, ~2.3 at three, levelling off near 5 mid-lake — a
    // broad shallow band where the bed shows through, not a cliff-edged pit.
    let depth = 5.0 * (1.0 - exp(-shore / 6.0));
    // Refracted path down to the bed and back up (Snell, n = 1.33), from the flat view angle.
    let cos_i = clamp(V.y, 0.0, 1.0);
    let cos_t = sqrt(1.0 - (1.0 - cos_i * cos_i) / 1.769);
    let path = depth * (1.0 + 1.0 / cos_t);
    // Absorption (1/world unit) and in-scattered colour per water type: clear sea / lake (red goes
    // first → teal), lightly silted river (green), tannin bog (blue goes first → brown-black).
    let sigma = mix(mix(vec3<f32>(0.50, 0.17, 0.13), vec3<f32>(0.90, 0.30, 0.38), river),
        vec3<f32>(2.4, 2.9, 3.8), bog);
    let scat = mix(mix(vec3<f32>(0.006, 0.050, 0.062), vec3<f32>(0.020, 0.055, 0.045), river),
        vec3<f32>(0.012, 0.010, 0.005), bog);
    let trans = exp(-sigma * path);
    // Bed: mottled silt / sand (static — the bed doesn't drift), wobbled by refraction; dark peat
    // under the bog.
    let mott = textureSample(ripple_tex, ripple_samp, (p + N.xz * (min(depth, 2.0) * 0.35)) / 7.3).a;
    let bed = mix(mix(vec3<f32>(0.15, 0.13, 0.09), vec3<f32>(0.28, 0.24, 0.17), mott),
        vec3<f32>(0.045, 0.035, 0.022), bog);
    var body = bed * trans + scat * (1.0 - trans);

    // Foam: a thin broken line right at the bank, a little wider on open water and in the current.
    let lively = max(open, river);
    let edge = 1.0 - smoothstep(0.0, mix(0.3, 0.5, lively), shore);
    let breakup = smoothstep(0.45, 0.8, l1.w * 0.6 + l2.w * 0.4 + edge * 0.25);
    let foam = edge * breakup * water.params.z * mix(0.35, 0.6, lively) * (1.0 - bog);
    body = mix(body, vec3<f32>(0.60, 0.63, 0.62), foam);

    // What the surface reflects isn't transmitted: weight the body by (1 − Fresnel).
    let n_dot_v = max(dot(N, V), 1e-4);
    let fres = 0.02 + 0.98 * pow(1.0 - n_dot_v, 5.0);
    body *= 1.0 - fres * (1.0 - foam);

    // ── 3. Reflection occlusion ─────────────────────────────────────────────────
    // A bank ~2.5 u tall at horizontal distance d hides the sky from reflected rays rising slower
    // than 2.5/d — so probe the bank field twice along the reflected ray's ground track within that
    // reach. Uses the rippled normal, so the mirrored bank wobbles with the water.
    let R = reflect(-V, N);
    let r_len = max(length(R.xz), 1e-3);
    let reach = clamp(2.5 * r_len / max(R.y, 0.02), 0.5, 22.0);
    let dir = R.xz / r_len;
    let o1 = water_field(p + dir * (reach * 0.35)).shore;
    let o2 = water_field(p + dir * (reach * 0.85)).shore;
    let occ = 1.0 - smoothstep(-0.5, 0.5, min(o1, o2));

    // Day factor from the brightest directional light. Bevy premultiplies ONLY illuminance into
    // `.color` (lux-scale, no exposure): the day sun peaks ≈13k; the night moon + the sun's
    // readability floor stay under ≈4.5k. The environment map is a baked DAYTIME sky (only dimmed
    // to ~70 % after dark), so mirroring it at full strength would turn night water into a pale
    // sheet — keep a dim sky + the moon glint instead.
    var sun_lum = 0.0;
    let nd = min(lights.n_directional_lights, 4u);
    for (var i = 0u; i < nd; i = i + 1u) {
        let c = lights.directional_lights[i].color.rgb;
        sun_lum = max(sun_lum, dot(c, vec3<f32>(0.299, 0.587, 0.114)));
    }
    let day_f = smoothstep(3500.0, 9000.0, sun_lum);

    pbr_input.N = N;
    pbr_input.material.base_color = vec4<f32>(body, 1.0);
    pbr_input.material.perceptual_roughness = mix(sqrt(alpha), 0.6, foam);
    pbr_input.material.metallic = 0.0;
    // Replaces Bevy's SSAO-derived estimate (the bank wall beside the waterline is exactly what the
    // march above accounts for; SSAO would double it). The mirrored bank is lit vegetation and
    // earth, not a void, so it only halves the sky. By day the gain goes ABOVE 1: the baked
    // environment cubemap (`scene::gradient_env_cubemap` × `IBL_INTENSITY`) is ~2× dimmer than the
    // Atmosphere sky actually drawn on screen, and a water mirror must match the sky above it.
    pbr_input.specular_occlusion = (1.0 - 0.5 * occ) * mix(0.2, 2.2, day_f);

    var out: FragmentOutput;
    out.color = apply_pbr_lighting(pbr_input);
    out.color = main_pass_post_lighting_processing(pbr_input, out.color);
    return out;
}
