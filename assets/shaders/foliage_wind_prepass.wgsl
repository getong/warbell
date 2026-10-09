// Foliage wind, PREPASS vertex stage (depth / normal / motion vectors / shadow maps). Must bend
// exactly like `foliage_wind.wgsl`, and also evaluates last frame's offset so TAA gets true
// motion vectors for the swaying leaves instead of ghosting them.

#import bevy_pbr::{
    mesh_functions,
    prepass_io::{Vertex, VertexOutput},
    view_transformations::position_world_to_clip,
}

struct FoliageWind {
    wind: vec4<f32>,
    tint: vec4<f32>,
};
@group(#{MATERIAL_BIND_GROUP}) @binding(100) var<uniform> fw: FoliageWind;

fn fw_hash(p: vec2<f32>) -> f32 {
    return fract(sin(dot(p, vec2<f32>(127.1, 311.7))) * 43758.547);
}

fn wind_offset(wp: vec3<f32>, origin: vec3<f32>, w: f32, t: f32) -> vec3<f32> {
    let ph = fw_hash(floor(origin.xz * 4.0)) * 6.283 + dot(wp.xz, vec2<f32>(0.9, 1.3)) * fw.wind.w;
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
    var w = 0.0;
#ifdef VERTEX_UVS_B
    w = vertex.uv_b.x;
    out.uv_b = vertex.uv_b;
#endif

    let wp = mesh_functions::mesh_position_local_to_world(world_from_local, vec4<f32>(vertex.position, 1.0)).xyz;
    out.world_position = vec4<f32>(wp + wind_offset(wp, origin, w, fw.wind.x), 1.0);
    out.position = position_world_to_clip(out.world_position.xyz);
#ifdef UNCLIPPED_DEPTH_ORTHO_EMULATION
    out.unclipped_depth = out.position.z;
    out.position.z = min(out.position.z, 1.0);
#endif

#ifdef VERTEX_UVS_A
    out.uv = vertex.uv;
#endif

#ifdef NORMAL_PREPASS_OR_DEFERRED_PREPASS
#ifdef VERTEX_NORMALS
    out.world_normal = mesh_functions::mesh_normal_local_to_world(vertex.normal, vertex.instance_index);
#endif
#ifdef VERTEX_TANGENTS
    out.world_tangent = mesh_functions::mesh_tangent_local_to_world(world_from_local, vertex.tangent, vertex.instance_index);
#endif
#endif

#ifdef VERTEX_COLORS
    out.color = vertex.color;
#endif

#ifdef MOTION_VECTOR_PREPASS
    let prev_model = mesh_functions::get_previous_world_from_local(vertex.instance_index);
    let pwp = mesh_functions::mesh_position_local_to_world(prev_model, vec4<f32>(vertex.position, 1.0)).xyz;
    out.previous_world_position = vec4<f32>(pwp + wind_offset(pwp, prev_model[3].xyz, w, fw.wind.y), 1.0);
#endif

#ifdef VERTEX_OUTPUT_INSTANCE_INDEX
    out.instance_index = vertex.instance_index;
#endif
#ifdef VISIBILITY_RANGE_DITHER
    out.visibility_range_dither = mesh_functions::get_visibility_range_dither_level(vertex.instance_index, world_from_local[3]);
#endif
    return out;
}
