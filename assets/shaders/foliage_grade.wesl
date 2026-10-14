// Foliage main-pass FRAGMENT (`realforest::foliage`): the stock PBR fragment plus an optional olive
// meadow grade for the undergrowth cards (`fw.tint.z`, 0 = off — canopy / swamp cards pass straight
// through). The scanned and painted grass greens read neon / near-black against the olive sward
// they stand in; the grade pulls only GREEN-dominant texels toward olive (red lifted toward the
// green, luminance kept), so white daisies, yellow and purple flowers and straw seed stalks keep
// their own hue — a blanket vertex-colour multiply turned the daisies pink and the stalks rust.

import bevy_pbr::{
    render::pbr_fragment::pbr_input_from_standard_material,
    render::pbr_functions::{alpha_discard, apply_pbr_lighting, main_pass_post_lighting_processing},
    render::pbr_types::STANDARD_MATERIAL_FLAGS_UNLIT_BIT,
    render::forward_io::{VertexOutput, FragmentOutput},
};
@if(VISIBILITY_RANGE_DITHER)
import bevy_pbr::render::pbr_functions::visibility_range_dither;

struct FoliageWind {
    wind: vec4<f32>,
    // z = olive meadow grade strength
    tint: vec4<f32>,
};
@group(constants::MATERIAL_BIND_GROUP) @binding(100) var<uniform> fw: FoliageWind;

@fragment
fn fragment(in: VertexOutput, @builtin(front_facing) is_front: bool) -> FragmentOutput {
@if(VISIBILITY_RANGE_DITHER)
    visibility_range_dither(in.position, in.visibility_range_dither);
    var pbr_input = pbr_input_from_standard_material(in, is_front);
    pbr_input.material.base_color = alpha_discard(pbr_input.material.flags, pbr_input.material.alpha_cutoff, pbr_input.material.base_color);

    let grade = fw.tint.z;
    if grade > 0.0 {
        let c = pbr_input.material.base_color.rgb;
        // 0 for neutral / yellow / purple / white texels, 1 for a clearly green one.
        let green = clamp((c.g - max(c.r, c.b)) / max(c.g, 1e-4) * 1.6, 0.0, 1.0);
        // Olive: red brought up toward the green, green eased a touch, blue kept.
        let olive = vec3<f32>(c.g * 0.82, c.g * 0.94, c.b);
        let rgb = mix(c, olive, green * grade);
        pbr_input.material.base_color = vec4<f32>(rgb, pbr_input.material.base_color.a);
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
