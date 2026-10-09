// Foliage wind + crown tint, main-pass VERTEX stage (`realforest::foliage`). A copy of
// bevy_pbr's mesh.wgsl vertex (no morph / skin — kit foliage has neither) that bends each vertex
// by a cheap analytic wind field and varies the crown colour. The fragment stage is the stock PBR
// one. `foliage_wind_prepass.wgsl` applies the identical offset in the depth / shadow / motion-
// vector prepass so depth, shadows and TAA all agree with what is drawn.
//
// Per-vertex wind weight comes in UV_1.x (0 = rooted: blade base / twig, 1 = free tip), written
// by the kit loader from each model's height.

#import bevy_pbr::{
    mesh_functions,
    forward_io::{Vertex, VertexOutput},
    view_transformations::position_world_to_clip,
}

struct FoliageWind {
    // x = time (s), y = previous frame's time, z = amplitude (world units at weight 1), w = ripple
    wind: vec4<f32>,
    // x = crown tint strength (0..1), yzw reserved
    tint: vec4<f32>,
};
@group(#{MATERIAL_BIND_GROUP}) @binding(100) var<uniform> fw: FoliageWind;

fn fw_hash(p: vec2<f32>) -> f32 {
    return fract(sin(dot(p, vec2<f32>(127.1, 311.7))) * 43758.547);
}

fn wind_offset(wp: vec3<f32>, origin: vec3<f32>, w: f32, t: f32) -> vec3<f32> {
    let ph = fw_hash(floor(origin.xz * 4.0)) * 6.283 + dot(wp.xz, vec2<f32>(0.9, 1.3)) * fw.wind.w;
    // Broad gust fronts rolling across the forest, then each plant's own sway + a faster flutter.
    let gust = 0.55 + 0.45 * sin(t * 0.45 - dot(wp.xz, vec2<f32>(0.035, 0.021)) * 6.283);
    let s = sin(t * 1.55 + ph) * 0.7 + sin(t * 3.1 + ph * 1.9) * 0.3;
    let a = fw.wind.z * w * gust;
    let dir = vec2<f32>(0.86, 0.5);
    return vec3<f32>(dir.x * s * a, -abs(s) * a * 0.12, dir.y * s * a);
}

@vertex
fn vertex(vertex: Vertex) -> VertexOutput {
    var out: VertexOutput;
    let world_from_local = mesh_functions::get_world_from_local(vertex.instance_index);
    let origin = world_from_local[3].xyz;

#ifdef VERTEX_NORMALS
    out.world_normal = mesh_functions::mesh_normal_local_to_world(vertex.normal, vertex.instance_index);
#endif

    var w = 0.0;
#ifdef VERTEX_UVS_B
    w = vertex.uv_b.x;
    out.uv_b = vertex.uv_b;
#endif
    out.world_position = mesh_functions::mesh_position_local_to_world(world_from_local, vec4<f32>(vertex.position, 1.0));
    out.world_position = vec4<f32>(out.world_position.xyz + wind_offset(out.world_position.xyz, origin, w, fw.wind.x), 1.0);
    out.position = position_world_to_clip(out.world_position.xyz);

#ifdef VERTEX_UVS_A
    out.uv = vertex.uv;
#endif
#ifdef VERTEX_TANGENTS
    out.world_tangent = mesh_functions::mesh_tangent_local_to_world(world_from_local, vertex.tangent, vertex.instance_index);
#endif
#ifdef VERTEX_COLORS
    // Crown colour variety: each tree (its own origin) leans yellow-green, mid or deep blue-green,
    // and merged undergrowth chunks drift in broad patches — no more one-green forest.
    let n = clamp(fw_hash(floor(origin.xz * 2.0)) * 0.6
        + (sin(out.world_position.x * 0.071) * sin(out.world_position.z * 0.053)) * 0.4 + 0.2, 0.0, 1.0);
    let warm = vec3<f32>(1.10, 1.05, 0.78);
    let cool = vec3<f32>(0.80, 0.93, 0.88);
    let tint = mix(vec3<f32>(1.0), mix(warm, cool, n), fw.tint.x);
    out.color = vec4<f32>(vertex.color.rgb * tint, vertex.color.a);
#endif
#ifdef VERTEX_OUTPUT_INSTANCE_INDEX
    out.instance_index = vertex.instance_index;
#endif
#ifdef VISIBILITY_RANGE_DITHER
    out.visibility_range_dither = mesh_functions::get_visibility_range_dither_level(vertex.instance_index, world_from_local[3]);
#endif
    return out;
}
