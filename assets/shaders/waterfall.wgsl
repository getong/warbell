// The gorge WATERFALL (`src/vista.rs`) — four blended, PBR-lit water surfaces sharing one
// FRAGMENT override of `ExtendedMaterial<StandardMaterial, FallsExt>`. All motion is
// `globals.time` in here: no per-frame system, no material / mesh writes.
//   kind 0  SHEET  — the falling water, a ribbon draped down the head wall (uv.x = 0..1 across the
//                    core sheet, 2..3 across the wider spray veil; uv.y = metres fallen). Streaks
//                    advect with the parcel's free-fall clock `tau = sqrt(2·fallen/g)`, so they
//                    start slow and stretch as they accelerate, exactly like real falling water.
//   kind 1  MIST   — spray shells over the plunge pool: billowing noise rising off the water,
//                    faded by view-facing so the shell's silhouette never shows.
//   kind 2  FOAM   — the plunge-pool foam disc: a churning core and radial foam streaks drifting
//                    outward.
//   kind 3  STREAM — the feeder brook on the plateau above the lip: dark clear water with white
//                    riffles running toward the lip (uv.x across, uv.y = metres downstream).

#import bevy_pbr::{
    pbr_fragment::pbr_input_from_standard_material,
    pbr_functions::{apply_pbr_lighting, main_pass_post_lighting_processing},
    forward_io::{VertexOutput, FragmentOutput},
    mesh_view_bindings::{globals, view},
}

struct FallsParams {
    // x = kind, y = mist base y (kind 1), z = mist height (kind 1), w = seed
    p: vec4<f32>,
};
@group(#{MATERIAL_BIND_GROUP}) @binding(100) var<uniform> falls: FallsParams;

fn hash2(p: vec2<f32>) -> f32 {
    return fract(sin(dot(p, vec2<f32>(127.1, 311.7))) * 43758.5453);
}

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
    return vnoise(p) * 0.52 + vnoise(p * 2.07 + vec2<f32>(5.2, 1.3)) * 0.30 + vnoise(p * 4.31 + vec2<f32>(9.1, 3.7)) * 0.18;
}

@fragment
fn fragment(in: VertexOutput, @builtin(front_facing) is_front: bool) -> FragmentOutput {
    let t = globals.time;
    let kind = u32(falls.p.x + 0.5);
    let seed = falls.p.w;
    let wp = in.world_position.xyz;

    var albedo = vec3<f32>(0.90, 0.94, 0.96);
    var a = 0.0;
    var rough = 0.45;
    var glow = 0.0; // forward-scattered skylight: white water stays bright in the gorge's shade

    if kind == 0u {
        // ── SHEET ──
        let veil = in.uv.x > 1.5;
        let u = select(in.uv.x, in.uv.x - 2.0, veil);
        let fallen = max(in.uv.y, 0.0);
        // Free-fall clock (+0.5 m head start: the water leaves the lip already moving, and the
        // pattern doesn't pinch to infinite frequency at the very top).
        let tau = sqrt(2.0 * (fallen + 0.5) / 7.5);
        let s = tau - t * 0.85;
        // Ribbons: coarse across-sheet structure that drifts slowly (the jets wander), plus fine
        // streaks that race down at the parcel speed.
        let jets = fbm(vec2<f32>(u * 5.0 + seed + t * 0.07, tau * 0.6));
        let streak = fbm(vec2<f32>(u * 11.0 + jets * 1.7 + seed, s * 5.0));
        let fine = vnoise(vec2<f32>(u * 41.0 + seed * 3.0, s * 9.0));
        // Frayed edges: the sheet's sides tear into separate strands as it falls.
        let fray = (vnoise(vec2<f32>(s * 2.6, u * 3.0 + 7.0)) - 0.5) * (0.10 + 0.12 * min(fallen / 10.0, 1.0));
        let e = smoothstep(0.0, 0.16, u + fray) * smoothstep(1.0, 0.84, u - fray);
        if veil {
            // The spray veil: a thin, wind-torn curtain of droplets wrapping the core.
            let mist = smoothstep(0.35, 0.80, fbm(vec2<f32>(u * 6.0 + seed, s * 1.6)));
            a = e * mist * 0.32 * smoothstep(0.5, 3.0, fallen);
            albedo = vec3<f32>(0.93, 0.96, 0.98);
            rough = 0.8;
            glow = 0.35;
        } else {
            // Dense white aerated core, thinner glassy gaps between the jets showing the rock, and
            // falling water PACKETS (short clumps racing down) so it never reads as a static
            // striped texture.
            let body = smoothstep(0.22, 0.72, jets * 0.55 + streak * 0.45);
            let packets = smoothstep(0.45, 0.85, vnoise(vec2<f32>(u * 7.0 + seed * 1.3, s * 7.5)));
            let white = clamp(body * 0.6 + packets * 0.35 + smoothstep(0.55, 0.85, fine) * 0.3, 0.0, 1.0);
            // Near the lip the water is still a smooth glassy tongue; it aerates as it falls.
            let aer = smoothstep(0.2, 2.5, fallen);
            let w = mix(white * 0.35, white, aer);
            albedo = mix(vec3<f32>(0.32, 0.42, 0.44), vec3<f32>(0.93, 0.96, 0.97), w);
            a = e * mix(0.55, 0.97, w);
            rough = mix(0.12, 0.65, w);
            glow = 0.28 * w;
        }
    } else if kind == 1u {
        // ── MIST ──
        let n = normalize(in.world_normal);
        let v = normalize(view.world_position.xyz - wp);
        // Steep view-facing falloff: the shell's limb must vanish, or the mist reads as a slab.
        let facing = pow(abs(dot(n, v)), 3.0);
        let h = clamp((wp.y - falls.p.y) / max(falls.p.z, 0.1), 0.0, 1.0);
        // Billows rise and thin out; two crossed lattices so nothing reads as a scrolling tile.
        let rise = wp.y * 0.42 - t * 0.55;
        let b1 = fbm(vec2<f32>(dot(wp.xz, vec2<f32>(0.62, 0.78)) * 0.42 + seed, rise));
        let b2 = fbm(vec2<f32>(dot(wp.xz, vec2<f32>(-0.78, 0.62)) * 0.37 - seed, rise * 0.8 + 11.0));
        let puff = smoothstep(0.30, 0.78, b1 * 0.6 + b2 * 0.4);
        a = facing * puff * (1.0 - smoothstep(0.05, 0.85, h)) * 0.72;
        albedo = vec3<f32>(0.92, 0.95, 0.97);
        rough = 0.9;
        glow = 0.45;
    } else if kind == 2u {
        // ── PLUNGE-POOL FOAM ──
        let c = in.uv - vec2<f32>(0.5);
        let r = length(c) * 2.0;
        let dir = c / max(length(c), 1e-4);
        // Foam streaks drift outward from the impact and slow down as they spread.
        let drift = sqrt(r) * 3.0 - t * 0.32;
        let n1 = fbm(dir * 2.3 + vec2<f32>(drift * 1.7, seed));
        let n2 = vnoise(c * 13.0 + dir * 3.0 + vec2<f32>(drift * 4.0, seed * 2.0));
        let lace = smoothstep(0.46, 0.72, n1 * 0.7 + n2 * 0.3);
        // The boil right under the falls: churning, almost solid white.
        let boil_n = fbm(c * 9.0 + vec2<f32>(t * 0.9, -t * 0.7));
        let boil = (1.0 - smoothstep(0.08, 0.38, r + (boil_n - 0.5) * 0.15));
        a = max(lace * (1.0 - smoothstep(0.30, 1.0, r)) * 0.85, boil * 0.95);
        albedo = vec3<f32>(0.90, 0.94, 0.95);
        rough = 0.6;
        glow = 0.2;
    } else {
        // ── FEEDER STREAM ──
        let u = in.uv.x;
        let along = in.uv.y;
        let f = along - t * 1.9;
        let rif = fbm(vec2<f32>(u * 4.5 + seed, f * 1.25));
        let rif2 = vnoise(vec2<f32>(u * 11.0, f * 3.4 + 3.0));
        let white = smoothstep(0.52, 0.80, rif * 0.7 + rif2 * 0.3);
        let fray = (vnoise(vec2<f32>(along * 1.3, 4.0)) - 0.5) * 0.18;
        let e = smoothstep(0.0, 0.22, u + fray) * smoothstep(1.0, 0.78, u - fray);
        // Spring at the source: the brook seeps out of the scree over its first metre or two.
        let src = smoothstep(0.0, 2.0, along);
        albedo = mix(vec3<f32>(0.10, 0.15, 0.16), vec3<f32>(0.88, 0.92, 0.93), white);
        a = e * src * mix(0.78, 0.95, white);
        rough = mix(0.06, 0.55, white);
        glow = 0.15 * white;
    }

    var out: FragmentOutput;
    var pbr_input = pbr_input_from_standard_material(in, is_front);
    pbr_input.material.base_color = vec4<f32>(albedo, 1.0);
    pbr_input.material.perceptual_roughness = rough;
    pbr_input.material.metallic = 0.0;
    // Light it twice: once as the surface faces, once as if it faced the light straight on, and
    // lean toward the latter by `glow` — thin water scatters the sun through itself, so a sheet
    // in the gorge's shade still reads as luminous white, not grey card.
    var lit = apply_pbr_lighting(pbr_input);
    if glow > 0.001 {
        var lit_in = pbr_input;
        lit_in.N = normalize(view.world_position.xyz - wp);
        lit_in.V = lit_in.N;
        let lit2 = apply_pbr_lighting(lit_in);
        lit = vec4<f32>(mix(lit.rgb, max(lit.rgb, lit2.rgb), glow), lit.a);
    }
    lit = main_pass_post_lighting_processing(pbr_input, vec4<f32>(lit.rgb, 1.0));
    out.color = vec4<f32>(lit.rgb, clamp(a, 0.0, 1.0));
    return out;
}
