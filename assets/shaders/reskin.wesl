// Structure re-skin (`realforest::reskin`): world-space triplanar wood / stone / cloth scans laid
// over a low-poly building's vertex colours. The layer is picked per fragment from the colour
// (warm + saturated = wood, desaturated = stone, other = cloth); the albedo detail is normalised to
// a 0.5 mean, so `colour * detail * 2` keeps the authored colour while adding the scan's grain.

import bevy_pbr::{
    render::pbr_fragment::pbr_input_from_standard_material,
    render::pbr_functions::{apply_pbr_lighting, main_pass_post_lighting_processing},
    render::pbr_types::STANDARD_MATERIAL_FLAGS_UNLIT_BIT,
    render::forward_io::{VertexOutput, FragmentOutput},
};
@if(VISIBILITY_RANGE_DITHER)
import bevy_pbr::render::pbr_functions::visibility_range_dither;

struct ReskinParams {
    // x = wood, y = stone, z = cloth world units per repeat; w = detail strength.
    tile: vec4<f32>,
};

@group(constants::MATERIAL_BIND_GROUP) @binding(100) var<uniform> rs: ReskinParams;
@group(constants::MATERIAL_BIND_GROUP) @binding(101) var rs_albedo: texture_2d_array<f32>;
@group(constants::MATERIAL_BIND_GROUP) @binding(102) var rs_normal: texture_2d_array<f32>;
@group(constants::MATERIAL_BIND_GROUP) @binding(103) var rs_ormh: texture_2d_array<f32>;
@group(constants::MATERIAL_BIND_GROUP) @binding(104) var rs_samp: sampler;

struct Tri {
    albedo: vec3<f32>,
    orm: vec4<f32>,
    n: vec3<f32>,
};

// One layer, triplanar (Golus "whiteout" normal blend), world position p / normal n.
fn tri(layer: i32, p: vec3<f32>, n: vec3<f32>, w: vec3<f32>, tile: f32) -> Tri {
    let uvx = p.zy / tile;
    let uvy = p.xz / tile + vec2<f32>(0.31, 0.57);
    let uvz = p.xy / tile + vec2<f32>(0.63, 0.17);
    var t: Tri;
    t.albedo = textureSample(rs_albedo, rs_samp, uvx, layer).rgb * w.x
        + textureSample(rs_albedo, rs_samp, uvy, layer).rgb * w.y
        + textureSample(rs_albedo, rs_samp, uvz, layer).rgb * w.z;
    t.orm = textureSample(rs_ormh, rs_samp, uvx, layer) * w.x
        + textureSample(rs_ormh, rs_samp, uvy, layer) * w.y
        + textureSample(rs_ormh, rs_samp, uvz, layer) * w.z;
    var tx = textureSample(rs_normal, rs_samp, uvx, layer).xyz * 2.0 - 1.0;
    var ty = textureSample(rs_normal, rs_samp, uvy, layer).xyz * 2.0 - 1.0;
    var tz = textureSample(rs_normal, rs_samp, uvz, layer).xyz * 2.0 - 1.0;
    tx = vec3<f32>(tx.xy + n.zy, abs(tx.z) * n.x);
    ty = vec3<f32>(ty.xy + n.xz, abs(ty.z) * n.y);
    tz = vec3<f32>(tz.xy + n.xy, abs(tz.z) * n.z);
    t.n = normalize(tx.zyx * w.x + ty.xzy * w.y + tz.xyz * w.z);
    return t;
}

@fragment
fn fragment(in: VertexOutput, @builtin(front_facing) is_front: bool) -> FragmentOutput {
@if(VISIBILITY_RANGE_DITHER)
    visibility_range_dither(in.position, in.visibility_range_dither);
    var pbr_input = pbr_input_from_standard_material(in, is_front);
    let c = pbr_input.material.base_color.rgb;
    let mx = max(c.r, max(c.g, c.b));
    let mn = min(c.r, min(c.g, c.b));
    let sat = (mx - mn) / max(mx, 1e-3);
    let warm = smoothstep(1.05, 1.35, c.r / max(c.b, 1e-3)) * step(c.g, c.r * 1.15);
    var wood = smoothstep(0.18, 0.32, sat) * warm;
    var stone = 1.0 - smoothstep(0.12, 0.26, sat);
    var cloth = max(1.0 - wood - stone, 0.0);
    let ws = max(wood + stone + cloth, 1e-3);
    wood /= ws;
    stone /= ws;
    cloth /= ws;

    let n = normalize(pbr_input.N);
    var w = pow(abs(n), vec3<f32>(4.0));
    w /= (w.x + w.y + w.z);
    let p = in.world_position.xyz;

    // Only sample the layers that matter here (most fragments are a single material).
    var albedo = vec3<f32>(0.0);
    var orm = vec4<f32>(0.0);
    var nn = vec3<f32>(0.0);
    if wood > 0.01 {
        let t = tri(0, p, n, w, rs.tile.x);
        albedo += t.albedo * wood; orm += t.orm * wood; nn += t.n * wood;
    }
    if stone > 0.01 {
        let t = tri(1, p, n, w, rs.tile.y);
        albedo += t.albedo * stone; orm += t.orm * stone; nn += t.n * stone;
    }
    if cloth > 0.01 {
        let t = tri(2, p, n, w, rs.tile.z);
        albedo += t.albedo * cloth; orm += t.orm * cloth; nn += t.n * cloth;
    }
    let k = rs.tile.w;
    pbr_input.material.base_color = vec4<f32>(c * mix(vec3<f32>(1.0), albedo * 2.0, k), pbr_input.material.base_color.a);
    pbr_input.material.perceptual_roughness = mix(pbr_input.material.perceptual_roughness, clamp(orm.g, 0.35, 1.0), k);
    pbr_input.diffuse_occlusion *= mix(1.0, orm.r, 0.8 * k);
    pbr_input.N = normalize(mix(n, normalize(nn), k));

    var out: FragmentOutput;
    if (pbr_input.material.flags & STANDARD_MATERIAL_FLAGS_UNLIT_BIT) == 0u {
        out.color = apply_pbr_lighting(pbr_input);
    } else {
        out.color = pbr_input.material.base_color;
    }
    out.color = main_pass_post_lighting_processing(pbr_input, out.color);
    return out;
}
