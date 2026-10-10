// Snow-dusted forest kit (`alpine::snowkit`): the stock PBR fragment of the kit's materials, with
// snow settled on every sky-facing surface — pine needle cards, the tops of branches, rock caps,
// grass tips. The vertex stage is the shared `foliage_wind.wgsl` (same uniform at binding 100);
// `fw.tint.y` is the snow amount. Snow lands by the GEOMETRIC normal (where the surface faces the
// sky) broken up by a world-space noise, and softens the mapped normal + raises roughness so it
// reads as powder, not paint.

#import bevy_pbr::{
    pbr_fragment::pbr_input_from_standard_material,
    pbr_functions::{alpha_discard, apply_pbr_lighting, main_pass_post_lighting_processing, visibility_range_dither},
    pbr_types::STANDARD_MATERIAL_FLAGS_UNLIT_BIT,
    forward_io::{VertexOutput, FragmentOutput},
    mesh_view_bindings::view,
}

struct FoliageWind {
    wind: vec4<f32>,
    // x = crown tint strength, y = snow amount 0..1
    tint: vec4<f32>,
};
@group(#{MATERIAL_BIND_GROUP}) @binding(100) var<uniform> fw: FoliageWind;

fn sk_hash(p: vec2<f32>) -> f32 {
    var p3 = fract(vec3<f32>(p.x, p.y, p.x) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

fn sk_noise(p: vec2<f32>) -> f32 {
    let i = floor(p);
    let f = fract(p);
    let u = f * f * (3.0 - 2.0 * f);
    let a = sk_hash(i);
    let b = sk_hash(i + vec2<f32>(1.0, 0.0));
    let c = sk_hash(i + vec2<f32>(0.0, 1.0));
    let d = sk_hash(i + vec2<f32>(1.0, 1.0));
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

@fragment
fn fragment(in: VertexOutput, @builtin(front_facing) is_front: bool) -> FragmentOutput {
#ifdef VISIBILITY_RANGE_DITHER
    visibility_range_dither(in.position, in.visibility_range_dither);
#endif
    var pbr_input = pbr_input_from_standard_material(in, is_front);
    pbr_input.material.base_color = alpha_discard(pbr_input.material, pbr_input.material.base_color);

    let amount = fw.tint.y;
    if amount > 0.0 {
        let wp = in.world_position.xyz;
        let gn = normalize(in.world_normal);
        let n = normalize(pbr_input.N);
        // Sky-facing: the mapped normal decides the fine pattern, the geometric one the broad
        // placement (a card's bent normal alone would frost the underside of a crown).
        let up = min(n.y * 0.65 + gn.y * 0.55, 1.0);
        let br = sk_noise(wp.xz * 2.7 + vec2<f32>(wp.y * 1.9, wp.y * -1.3)) * 0.6
               + sk_noise(wp.xz * 9.0 - wp.y * 3.0) * 0.4;
        // From afar a snowy conifer reads as a DARK crown with white highlights (the needles
        // self-shadow and the snow sits on the outer tips), not a white skeleton: the far LODs'
        // cards are mostly sky-facing, so thin the frosting with distance.
        let far = smoothstep(22.0, 70.0, distance(view.world_position.xyz, wp));
        let s = smoothstep(0.18, 0.62, up + (br - 0.5) * 0.55 + (amount - 0.5) * 0.6) * min(amount * 1.6, 1.0)
              * (1.0 - 0.45 * far);
        // Slightly blue in the deeper (less sky-facing) snow, near-white on top.
        let snow_col = mix(vec3<f32>(0.66, 0.72, 0.82), vec3<f32>(0.86, 0.89, 0.93), clamp(up, 0.0, 1.0));
        let base = pbr_input.material.base_color;
        pbr_input.material.base_color = vec4<f32>(mix(base.rgb, snow_col, s), base.a);
        pbr_input.material.perceptual_roughness = mix(pbr_input.material.perceptual_roughness, 0.72, s);
        pbr_input.material.metallic = mix(pbr_input.material.metallic, 0.0, s);
        pbr_input.N = normalize(mix(n, normalize(n + vec3<f32>(0.0, 1.2, 0.0)), s * 0.6));
    }

    var out: FragmentOutput;
    if (pbr_input.material.flags & STANDARD_MATERIAL_FLAGS_UNLIT_BIT) == 0u {
        out.color = apply_pbr_lighting(pbr_input);
    } else {
        out.color = pbr_input.material.base_color;
    }
    out.color = main_pass_post_lighting_processing(pbr_input, out.color);
    return out;
}
