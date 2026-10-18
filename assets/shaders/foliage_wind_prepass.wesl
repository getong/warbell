// Foliage wind, PREPASS (depth / normal / motion vectors / shadow maps). The vertex stage must bend
// exactly like `foliage_wind.wgsl`, and also evaluates last frame's offset so TAA gets true
// motion vectors for the swaying leaves instead of ghosting them.
//
// RANGE DISSOLVE (undergrowth chunks, `fw.tint.z` = band width in world units, 0 = off): instead of
// popping whole 16u chunks at their `VisibilityRange` ends, a chunk thins out tuft by tuft over the
// last `band` units before its cull distance (and a ring that starts at a distance thins IN over the
// first `band`), keyed on a world-locked hash so the dropped tufts stay put while the camera moves.
// The vertex stage turns the chunk's own (render-distance-scaled) range into a keep fraction
// (`uv_b.x`); the fragment stage discards tufts above it. The main pass draws grass with an EQUAL
// depth test against this prepass (`foliage.rs` `specialize`), so it inherits the dissolve.

import bevy_pbr::{
    render::mesh_functions,
    prepass::io::{Vertex, VertexOutput, decompress_vertex},
    render::view_transformations::position_world_to_clip,
    render::mesh_view_bindings::{view, visibility_ranges},
    render::mesh_bindings::mesh,
    render::{pbr_prepass_functions, pbr_bindings, pbr_types, pbr_functions},
};
import bevy_render::globals::Globals;
import bevy_render::bindless::{bindless_samplers_filtering, bindless_textures_2d};
@if(BINDLESS)
import bevy_pbr::render::pbr_bindings::material_indices;
@if(PREPASS_FRAGMENT)
import bevy_pbr::prepass::io::FragmentOutput;

// The prepass / shadow view layout carries Globals at binding 1 (bevy_pbr `prepass_view_layout_*`)
// but `prepass_bindings` doesn't declare it, so bind it here. Wind clock = `globals.time`, same as
// the main pass (see `foliage_wind.wgsl` for why it isn't a material field).
@group(0) @binding(1) var<uniform> fw_globals: Globals;

struct FoliageWind {
    wind: vec4<f32>,
    tint: vec4<f32>,
};
@group(constants::MATERIAL_BIND_GROUP) @binding(100) var<uniform> fw: FoliageWind;

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

// ── Grass underfoot (`grass_trample.rs`) — undergrowth only (`fw.wind.y` = 1) ──
// [0] = grid (min x, min z, cell, cells per side), [1..=8] = pushers (xyz, radius), then the
// trample cells packed 4 per vec4 (0 = upright, >= 1 = flat). Keep in sync with the Rust side.
@group(constants::MATERIAL_BIND_GROUP) @binding(101) var<storage, read> trample: array<vec4<f32>>;

fn trample_cell(ix: i32, iz: i32, n: i32) -> f32 {
    if ix < 0 || iz < 0 || ix >= n || iz >= n {
        return 0.0;
    }
    let i = iz * n + ix;
    return trample[9 + i / 4][i % 4];
}

/// Lean of an undergrowth vertex at world `wp` (wind freedom `w`) from the people walking through
/// it: blades part round each pusher's legs and lie over where feet came down. Modelled as a rigid
/// bend about the blade root (the vertex keeps its length), the height above the root estimated
/// from `w` (`foliage::bake_weights`: ~0.8·(h/top)^1.4) for a ~0.45 u tuft.
fn trample_offset(wp: vec3<f32>, w: f32) -> vec3<f32> {
    if fw.wind.y < 0.5 || w <= 0.001 {
        return vec3<f32>(0.0);
    }
    var lean = vec2<f32>(0.0);
    for (var i = 1; i <= 8; i++) {
        let p = trample[i];
        if p.w <= 0.0 {
            continue;
        }
        let d = wp.xz - p.xz;
        let dist = length(d);
        if dist >= p.w || abs(wp.y - p.y) > 1.6 {
            continue;
        }
        let k = 1.0 - dist / p.w;
        lean += d / max(dist, 0.04) * (k * k * (3.0 - 2.0 * k)) * 1.15;
    }
    let g = trample[0];
    let n = i32(g.w);
    let c = (wp.xz - g.xy) / g.z - 0.5;
    let c0 = floor(c);
    let f = c - c0;
    let ix = i32(c0.x);
    let iz = i32(c0.y);
    let t = clamp(mix(mix(trample_cell(ix, iz, n), trample_cell(ix + 1, iz, n), f.x),
                      mix(trample_cell(ix, iz + 1, n), trample_cell(ix + 1, iz + 1, n), f.x), f.y), 0.0, 1.0);
    if t > 0.0 {
        // Trodden blades lie over along a slowly wandering direction (a pressed patch, not a comb).
        let a = (sin(wp.x * 1.3 + wp.z * 0.4) + sin(wp.z * 1.1 - wp.x * 0.7)) * 3.1416;
        lean += vec2<f32>(cos(a), sin(a)) * t * 1.05;
    }
    // Bent over, never flat: a blade laid at the ground vanishes into it and reads as mown.
    let ang = min(length(lean), 1.15);
    if ang < 0.001 {
        return vec3<f32>(0.0);
    }
    let dir = lean / max(length(lean), 1e-4);
    let h = 0.45 * pow(clamp(w / 0.8, 0.0, 1.0), 0.714);
    let s = sin(ang) * h;
    return vec3<f32>(dir.x * s, -(1.0 - cos(ang)) * h, dir.y * s);
}

/// Keep fraction (0..1) of this chunk's tufts for its visibility range at the current distance.
fn dissolve_keep(instance_index: u32, origin: vec3<f32>) -> f32 {
    let band = fw.tint.z;
    if band <= 0.0 {
        return 1.0;
    }
@if(AVAILABLE_STORAGE_BUFFER_BINDINGS__GE_6)
    let len = arrayLength(&visibility_ranges);
@else
    let len = VISIBILITY_RANGE_UNIFORM_BUFFER_SIZE;
    let idx = mesh[instance_index].flags & 0xffffu;
    if idx >= len {
        return 1.0;
    }
    let r = visibility_ranges[idx];
    let d = distance(view.lod_view_world_position, origin);
    var keep = 1.0;
    if r.y > 0.0 {
        keep = smoothstep(r.y, r.y + band, d);
    }
    if r.z < 1.0e5 {
        keep = min(keep, 1.0 - smoothstep(r.z - band, r.z, d));
    }
    return keep;
}

@vertex
fn vertex(vertex_in: Vertex) -> VertexOutput {
    var out: VertexOutput;
    let vertex = decompress_vertex(vertex_in, vertex_in.instance_index);
    let world_from_local = mesh_functions::get_world_from_local(vertex.instance_index);
    let origin = world_from_local[3].xyz;
    var w = 0.0;
@if(VERTEX_UVS_B) {
    w = vertex.uv_b.x;
    // uv_b.x leaves the vertex stage as the range-dissolve keep fraction (see the header).
    out.uv_b = vec2<f32>(dissolve_keep(vertex.instance_index, origin), 0.0);
}

    let wp = mesh_functions::mesh_position_local_to_world(world_from_local, vec4<f32>(vertex.position, 1.0)).xyz;
    out.world_position = vec4<f32>(wp + wind_offset(wp, origin, w, fw_globals.time) + trample_offset(wp, w), 1.0);
    out.position = position_world_to_clip(out.world_position.xyz);
@if(UNCLIPPED_DEPTH_ORTHO_EMULATION) {
    out.unclipped_depth = out.position.z;
    out.position.z = min(out.position.z, 1.0);
}

@if(VERTEX_UVS_A)
    out.uv = vertex.uv;

@if(NORMAL_PREPASS_OR_DEFERRED_PREPASS) {
@if(VERTEX_NORMALS) {
    // Same up-lean as the main pass (SSAO reads these normals).
    let nrm = mesh_functions::mesh_normal_local_to_world(vertex.normal, vertex.instance_index);
    let nroot = 1.0 - smoothstep(0.0, 0.55, w);
    out.world_normal = normalize(mix(nrm, vec3<f32>(0.0, 1.0, 0.0), fw.tint.w * (0.4 + 0.6 * nroot)));
}
@if(VERTEX_TANGENTS)
    out.world_tangent = mesh_functions::mesh_tangent_local_to_world(world_from_local, vertex.tangent, vertex.instance_index);
}

@if(VERTEX_COLORS)
    out.color = vertex.color;

@if(MOTION_VECTOR_PREPASS) {
    let prev_model = mesh_functions::get_previous_world_from_local(vertex.instance_index);
    let pwp = mesh_functions::mesh_position_local_to_world(prev_model, vec4<f32>(vertex.position, 1.0)).xyz;
    out.previous_world_position = vec4<f32>(pwp + wind_offset(pwp, prev_model[3].xyz, w, fw_globals.time - fw_globals.delta_time)
        + trample_offset(pwp, w), 1.0);
}

@if(VERTEX_OUTPUT_INSTANCE_INDEX)
    out.instance_index = vertex.instance_index;
@if(VISIBILITY_RANGE_DITHER)
    out.visibility_range_dither = mesh_functions::get_visibility_range_dither_level(vertex.instance_index, world_from_local[3]);
    return out;
}

fn dissolve_hash(p: vec3<f32>) -> f32 {
    return fract(sin(dot(p, vec3<f32>(12.9898, 78.233, 37.719))) * 43758.547);
}

// Fragment: bevy_pbr's `pbr_prepass.wesl` (non-meshlet path), plus the range dissolve.
@if(PREPASS_FRAGMENT)
@fragment
fn fragment(in: VertexOutput, @builtin(front_facing) is_front: bool) -> FragmentOutput {
@if(BINDLESS)
    let slot = mesh[in.instance_index].material_and_lightmap_bind_group_slot & 0xffffu;
@if(BINDLESS)
    let flags = pbr_bindings::material_array[material_indices[slot].material].flags;
@if(BINDLESS)
    let uv_transform = pbr_bindings::material_array[material_indices[slot].material].uv_transform;
@if(!BINDLESS)
    let flags = pbr_bindings::material.flags;
@if(!BINDLESS)
    let uv_transform = pbr_bindings::material.uv_transform;

@if(VISIBILITY_RANGE_DITHER)
    pbr_functions::visibility_range_dither(in.position, in.visibility_range_dither);

    pbr_prepass_functions::prepass_sample_color_and_alpha_discard(in);
@if(VERTEX_UVS_B) {
    if in.uv_b.x < 1.0 && dissolve_hash(floor(in.world_position.xyz * 3.0)) >= in.uv_b.x {
        discard;
    }
}

    var out: FragmentOutput;

@if(UNCLIPPED_DEPTH_ORTHO_EMULATION)
    out.frag_depth = in.unclipped_depth;

@if(NORMAL_PREPASS)
    if (flags & pbr_types::STANDARD_MATERIAL_FLAGS_UNLIT_BIT) == 0u {
        let double_sided = (flags & pbr_types::STANDARD_MATERIAL_FLAGS_DOUBLE_SIDED_BIT) != 0u;
        let mesh_flags = mesh[in.instance_index].flags;
        let is_logically_front = pbr_functions::winding_corrected_front_facing(mesh_flags, is_front);
        let world_normal = pbr_functions::prepare_world_normal(in.world_normal, double_sided, is_logically_front);
        var normal = world_normal;
@if(VERTEX_UVS) {
@if(VERTEX_TANGENTS) {
@if(STANDARD_MATERIAL_NORMAL_MAP) {
@if(STANDARD_MATERIAL_NORMAL_MAP_UV_B)
        let uv = (uv_transform * vec3(in.uv_b, 1.0)).xy;
@else
        let uv = (uv_transform * vec3(in.uv, 1.0)).xy;
@if(BINDLESS)
        let texture = bindless_textures_2d[material_indices[slot].normal_map_texture];
@else
        let texture = pbr_bindings::normal_map_texture;
@if(BINDLESS)
        let sampler_ = bindless_samplers_filtering[material_indices[slot].normal_map_sampler];
@else
        let sampler_ = pbr_bindings::normal_map_sampler;
        let Nt = textureSampleBias(texture, sampler_, uv, view.mip_bias).rgb;
        let TBN = pbr_functions::calculate_tbn_mikktspace(normal, in.world_tangent);
        normal = pbr_functions::apply_normal_mapping(flags, TBN, double_sided, is_logically_front, Nt);
}
}
}
        out.normal = vec4(normal * 0.5 + vec3(0.5), 1.0);
    } else {
        out.normal = vec4(in.world_normal * 0.5 + vec3(0.5), 1.0);
    }

@if(MOTION_VECTOR_PREPASS)
    out.motion_vector = pbr_prepass_functions::calculate_motion_vector(in.world_position, in.previous_world_position);

    return out;
}
@else
@fragment
fn fragment(in: VertexOutput) {
    pbr_prepass_functions::prepass_sample_color_and_alpha_discard(in);
@if(VERTEX_UVS_B) {
    if in.uv_b.x < 1.0 && dissolve_hash(floor(in.world_position.xyz * 3.0)) >= in.uv_b.x {
        discard;
    }
}
}
