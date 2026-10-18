// Foliage wind + crown tint, main-pass VERTEX stage (`realforest::foliage`). A copy of
// bevy_pbr's mesh.wgsl vertex (no morph / skin — kit foliage has neither) that bends each vertex
// by a cheap analytic wind field and varies the crown colour. The fragment stage is the stock PBR
// one. `foliage_wind_prepass.wgsl` applies the identical offset in the depth / shadow / motion-
// vector prepass so depth, shadows and TAA all agree with what is drawn.
//
// Per-vertex wind weight comes in UV_1.x (0 = rooted: blade base / twig, 1 = free tip), written
// by the kit loader from each model's height.
//
// The wind clock is Bevy's `globals.time`, NOT a material field: writing the time into the
// material every frame marked every foliage material modified, which made Bevy re-specialize
// every foliage mesh for the main pass, the prepass and each shadow cascade every frame (~10 ms
// of CPU on the 1.5x map).

import bevy_pbr::{
    render::mesh_functions,
    render::forward_io::{Vertex, VertexOutput, decompress_vertex},
    render::view_transformations::position_world_to_clip,
    render::mesh_view_bindings::globals,
};

struct FoliageWind {
    // x = blade-root ground match (undergrowth only), y = 1 on undergrowth (reacts to feet,
    // `trample_offset`; the wind clock is `globals.time`, see the header), z = amplitude (world units at weight 1), w = ripple
    wind: vec4<f32>,
    // x = crown tint strength (0..1); y = snow amount (`alpine::snowkit` twins); z unused;
    // w = shading-normal lean toward world up
    tint: vec4<f32>,
};
@group(constants::MATERIAL_BIND_GROUP) @binding(100) var<uniform> fw: FoliageWind;

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

@vertex
fn vertex(vertex_in: Vertex) -> VertexOutput {
    var out: VertexOutput;
    let vertex = decompress_vertex(vertex_in, vertex_in.instance_index);
    let world_from_local = mesh_functions::get_world_from_local(vertex.instance_index);
    let origin = world_from_local[3].xyz;

    var w = 0.0;
@if(VERTEX_UVS_B) {
    w = vertex.uv_b.x;
    out.uv_b = vertex.uv_b;
}
    // 1 at a blade's rooted base, 0 from mid-blade up.
    let root = 1.0 - smoothstep(0.0, 0.55, w);

@if(VERTEX_NORMALS) {
    // Undergrowth cards shade like the ground they stand on: the normal leans to world up (fully
    // at the root), so crossed cards don't print hard light/dark planes where they meet the sward.
    let nrm = mesh_functions::mesh_normal_local_to_world(vertex.normal, vertex.instance_index);
    out.world_normal = normalize(mix(nrm, vec3<f32>(0.0, 1.0, 0.0), fw.tint.w * (0.4 + 0.6 * root)));
}
    out.world_position = mesh_functions::mesh_position_local_to_world(world_from_local, vec4<f32>(vertex.position, 1.0));
    out.world_position = vec4<f32>(out.world_position.xyz + wind_offset(out.world_position.xyz, origin, w, globals.time)
        + trample_offset(out.world_position.xyz, w), 1.0);
    out.position = position_world_to_clip(out.world_position.xyz);

@if(VERTEX_UVS_A)
    out.uv = vertex.uv;
@if(VERTEX_TANGENTS)
    out.world_tangent = mesh_functions::mesh_tangent_local_to_world(world_from_local, vertex.tangent, vertex.instance_index);
@if(VERTEX_COLORS) {
    // Crown colour variety: each tree (its own origin) leans yellow-green, mid or deep blue-green,
    // and merged undergrowth chunks drift in broad patches — no more one-green forest.
    let n = clamp(fw_hash(floor(origin.xz * 2.0)) * 0.6
        + (sin(out.world_position.x * 0.071) * sin(out.world_position.z * 0.053)) * 0.4 + 0.2, 0.0, 1.0);
    let warm = vec3<f32>(1.10, 1.05, 0.78);
    let cool = vec3<f32>(0.80, 0.93, 0.88);
    let tint = mix(vec3<f32>(1.0), mix(warm, cool, n), fw.tint.x);
    // Lift the dark (0.55x) blade root toward the ground's own straw-olive so a clump fades into
    // the terrain instead of starting with a dark green cut line (the fragment grade then pulls
    // the remaining green toward olive).
    let ground = vec3<f32>(1.4, 1.12, 1.0);
    let rgb = mix(vertex.color.rgb * tint, ground, root * fw.wind.x);
    out.color = vec4<f32>(rgb, vertex.color.a);
}
@if(VERTEX_OUTPUT_INSTANCE_INDEX)
    out.instance_index = vertex.instance_index;
@if(VISIBILITY_RANGE_DITHER)
    out.visibility_range_dither = mesh_functions::get_visibility_range_dither_level(vertex.instance_index, world_from_local[3]);
    return out;
}
