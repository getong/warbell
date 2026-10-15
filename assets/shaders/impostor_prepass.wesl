// Far-tree IMPOSTORS, PREPASS (depth / normal / motion vectors / shadow maps). A copy of
// `impostor.wesl`'s vertex stage and sampling (keep the two in sync — the main pass relies on the
// prepass having written the identical alpha-tested depth). In a directional-light shadow view the
// quad faces the LIGHT and picks the light-facing views, so the cast shadow is the tree's
// silhouette from the sun.

import bevy_pbr::{
    render::mesh_functions,
    prepass::io::{Vertex, VertexOutput, decompress_vertex},
    render::view_transformations::position_world_to_clip,
    render::mesh_view_bindings::view,
};
@if(MOTION_VECTOR_PREPASS)
import bevy_pbr::render::pbr_prepass_functions::calculate_motion_vector;
@if(PREPASS_FRAGMENT)
import bevy_pbr::prepass::io::FragmentOutput;

struct ImpostorParams {
    // x = frames per side N, y = alpha cutoff, z = impostor start distance, w = quad push toward eye (radii)
    cfg: vec4<f32>,
    // x = far fade start, y = far end, z = crown tint strength, w = parallax on (1) / off (0)
    far: vec4<f32>,
    // per atlas layer: xyz = model-space sphere centre, w = radius (model units)
    models: array<vec4<f32>, 32>,
};
@group(constants::MATERIAL_BIND_GROUP) @binding(100) var<uniform> ip: ImpostorParams;
@group(constants::MATERIAL_BIND_GROUP) @binding(101) var albedo_tex: texture_2d_array<f32>;
@group(constants::MATERIAL_BIND_GROUP) @binding(102) var albedo_smp: sampler;
@group(constants::MATERIAL_BIND_GROUP) @binding(103) var nd_tex: texture_2d_array<f32>;
@group(constants::MATERIAL_BIND_GROUP) @binding(104) var nd_smp: sampler;

fn rot_y(v: vec3<f32>, a: f32) -> vec3<f32> {
    let c = cos(a);
    let s = sin(a);
    return vec3<f32>(c * v.x + s * v.z, v.y, -s * v.x + c * v.z);
}

fn oct_decode(g: vec2<f32>) -> vec3<f32> {
    let x = (g.x + g.y) * 0.5;
    let z = (g.x - g.y) * 0.5;
    return normalize(vec3<f32>(x, 1.0 - abs(x) - abs(z), z));
}

fn frame_right(d: vec3<f32>) -> vec3<f32> {
    let r = cross(vec3<f32>(0.0, 1.0, 0.0), d);
    return select(normalize(r), vec3<f32>(1.0, 0.0, 0.0), length(r) < 1e-4);
}

fn is_ortho() -> bool {
    return view.clip_from_view[3].w == 1.0;
}

fn ip_hash(p: vec2<f32>) -> f32 {
    return fract(sin(dot(p, vec2<f32>(127.1, 311.7))) * 43758.547);
}

fn ip_noise(p: vec2<f32>) -> f32 {
    let i = floor(p);
    let f = fract(p);
    let u = f * f * (3.0 - 2.0 * f);
    return mix(mix(ip_hash(i), ip_hash(i + vec2<f32>(1.0, 0.0)), u.x),
               mix(ip_hash(i + vec2<f32>(0.0, 1.0)), ip_hash(i + vec2<f32>(1.0, 1.0)), u.x), u.y);
}

@vertex
fn vertex(vertex_in: Vertex) -> VertexOutput {
    var out: VertexOutput;
    let v = decompress_vertex(vertex_in, vertex_in.instance_index);
    let world_from_local = mesh_functions::get_world_from_local(v.instance_index);
    let corner = v.uv;
    let s = v.uv_b.x;
    let yaw = v.uv_b.y;
    let layer = i32(v.color.x + 0.5);
    let m = ip.models[layer];
    let rs = m.w * s;
    let cw = rot_y(m.xyz * s, yaw);
    let p = mesh_functions::mesh_position_local_to_world(world_from_local, vec4<f32>(v.position, 1.0)).xyz;
    let base = p - cw - vec3<f32>(corner.x * rs, corner.y * rs, corner.x * rs);
    let centre = base + cw;

    var dir: vec3<f32>;
    var push = 0.0;
    if is_ortho() {
        dir = normalize(view.world_from_view[2].xyz);
    } else {
        dir = normalize(view.world_position.xyz - centre);
        push = ip.cfg.w;
    }
    let r = frame_right(dir);
    let u = cross(dir, r);
    let wp = centre + (r * corner.x + u * corner.y) * rs + dir * (push * rs);

    let d = distance(view.lod_view_world_position, base);
    let fade = 1.0 - smoothstep(ip.far.x, ip.far.y, d);
    out.world_position = vec4<f32>(wp, 1.0);
    out.position = position_world_to_clip(wp);
    if d < ip.cfg.z || d > ip.far.y {
        out.position = vec4<f32>(0.0, 0.0, -1.0, 1.0);
    }
@if(UNCLIPPED_DEPTH_ORTHO_EMULATION) {
    out.unclipped_depth = out.position.z;
    out.position.z = min(out.position.z, 1.0);
}
@if(NORMAL_PREPASS_OR_DEFERRED_PREPASS)
    out.world_normal = dir;
@if(MOTION_VECTOR_PREPASS)
    out.previous_world_position = out.world_position;
    out.color = vec4<f32>(centre, rs);
    out.uv = vec2<f32>(yaw, f32(layer));
    out.uv_b = vec2<f32>(v.color.y, fade);
@if(VERTEX_OUTPUT_INSTANCE_INDEX)
    out.instance_index = v.instance_index;
    return out;
}

struct Imp {
    albedo: vec3<f32>,
    alpha: f32,
    // model-space normal (game axes)
    n: vec3<f32>,
    // reconstructed surface point, world space
    surf: vec3<f32>,
};

/// Sample the impostor for the eye ray through world point `wp`. `full` = the main pass's colour +
/// normal blend; otherwise only what the alpha test needs (and, in a shadow view, just the one
/// nearest view with no parallax — a light's-eye silhouette).
fn impostor(wp: vec3<f32>, centre: vec3<f32>, rs: f32, yaw: f32, layer: i32, full: bool) -> Imp {
    let N = ip.cfg.x;
    var ro: vec3<f32>;
    var rd: vec3<f32>;
    var vdir: vec3<f32>;
    if is_ortho() {
        rd = -normalize(view.world_from_view[2].xyz);
        vdir = rot_y(-rd, -yaw);
    } else {
        rd = normalize(wp - view.world_position.xyz);
        vdir = normalize(rot_y(view.world_position.xyz - centre, -yaw));
    }
    let q = rot_y(wp - centre, -yaw) / rs;
    let dl = rot_y(rd, -yaw);
    vdir = normalize(vec3<f32>(vdir.x, max(vdir.y, 0.0), vdir.z));

    // Hemi-octahedral encode of the view direction -> fractional frame coords.
    let d1 = vdir / (abs(vdir.x) + abs(vdir.y) + abs(vdir.z));
    let uvo = vec2<f32>(d1.x + d1.z, d1.x - d1.z) * 0.5 + 0.5;
    let gp = uvo * N - 0.5;
    let f0 = floor(gp);
    let t = clamp(gp - f0, vec2<f32>(0.0), vec2<f32>(1.0));
    let i0 = clamp(f0, vec2<f32>(0.0), vec2<f32>(N - 1.0));
    let i1 = clamp(f0 + 1.0, vec2<f32>(0.0), vec2<f32>(N - 1.0));

    // Mip from the screen footprint of one atlas texel (frames are `frame_px` across 2 radii).
    let dist = select(distance(wp, view.world_position.xyz), 1.0, is_ortho());
    let world_px = 2.0 * dist / (view.clip_from_view[1][1] * view.viewport.w);
    let frame_px = f32(textureDimensions(albedo_tex).x) / N;
    let lod = clamp(log2(max(frame_px / (2.0 * rs) * world_px, 1e-4)), 0.0, 4.0);

    var acc = Imp(vec3<f32>(0.0), 0.0, vec3<f32>(0.0), vec3<f32>(0.0));
    var best = -1.0;
    let shadow = is_ortho() && !full;
    let count = select(4, 1, shadow);
    for (var k = 0; k < count; k++) {
        var fx = select(i0.x, i1.x, (k & 1) == 1);
        var fy = select(i0.y, i1.y, (k & 2) == 2);
        var w = select(1.0 - t.x, t.x, (k & 1) == 1) * select(1.0 - t.y, t.y, (k & 2) == 2);
        if shadow {
            fx = select(i0.x, i1.x, t.x > 0.5);
            fy = select(i0.y, i1.y, t.y > 0.5);
            w = 1.0;
        }
        let dk = oct_decode((vec2<f32>(fx, fy) + 0.5) / N * 2.0 - 1.0);
        let rk = frame_right(dk);
        let uk = cross(dk, rk);
        var den = dot(dl, dk);
        den = select(den, -0.05, den > -0.05);
        let qd = dot(q, dk);
        var h = q - dl * (qd / den);
        var fuv = vec2<f32>(dot(h, rk), -dot(h, uk)) * 0.5 + 0.5;
        let cell = vec2<f32>(fx, fy);
        var nd = vec4<f32>(0.5, 1.0, 0.5, 0.5);
        if ip.far.w > 0.5 && !shadow {
            let a0 = (cell + clamp(fuv, vec2<f32>(0.002), vec2<f32>(0.998))) / N;
            nd = textureSampleLevel(nd_tex, nd_smp, a0, layer, lod);
            let depth = nd.a * 2.0 - 1.0;
            h = q + dl * ((depth - qd) / den);
            fuv = vec2<f32>(dot(h, rk), -dot(h, uk)) * 0.5 + 0.5;
        }
        let inside = all(fuv > vec2<f32>(0.0)) && all(fuv < vec2<f32>(1.0));
        let auv = (cell + clamp(fuv, vec2<f32>(0.002), vec2<f32>(0.998))) / N;
        let a = textureSampleLevel(albedo_tex, albedo_smp, auv, layer, lod);
        if full {
            nd = textureSampleLevel(nd_tex, nd_smp, auv, layer, lod);
        }
        let wa = select(0.0, w, inside);
        acc.albedo += a.rgb * wa;
        acc.alpha += a.a * wa;
        acc.n += (nd.rgb * 2.0 - 1.0) * wa;
        if wa > best {
            best = wa;
            acc.surf = h;
        }
    }
    acc.n = normalize(acc.n + vec3<f32>(0.0, 1e-4, 0.0));
    acc.surf = centre + rot_y(acc.surf, yaw) * rs;
    return acc;
}

/// The alpha test, with the far-band dissolve: past the fade start whole leaf clumps (object-space
/// value noise, not a screen pattern) drop out as `fade` falls to 0.
fn impostor_keep(alpha: f32, fade: f32, surf: vec3<f32>, centre: vec3<f32>, rs: f32) -> bool {
    let lp = (surf - centre) / rs;
    let n = ip_noise(lp.xy * 5.0 + lp.z * 3.1) * 0.7 + ip_noise(lp.zy * 13.0) * 0.3;
    return alpha >= ip.cfg.y && n < fade * 1.02;
}

@if(PREPASS_FRAGMENT)
@fragment
fn fragment(in: VertexOutput) -> FragmentOutput {
    let centre = in.color.xyz;
    let rs = in.color.w;
    let yaw = in.uv.x;
    let im = impostor(in.world_position.xyz, centre, rs, yaw, i32(in.uv.y + 0.5), false);
    if !impostor_keep(im.alpha, in.uv_b.y, im.surf, centre, rs) {
        discard;
    }
    var out: FragmentOutput;
@if(UNCLIPPED_DEPTH_ORTHO_EMULATION)
    out.frag_depth = in.unclipped_depth;
@if(NORMAL_PREPASS)
    out.normal = vec4<f32>(normalize(rot_y(im.n, yaw)) * 0.5 + vec3<f32>(0.5), 1.0);
@if(MOTION_VECTOR_PREPASS)
    out.motion_vector = calculate_motion_vector(in.world_position, in.previous_world_position);
    return out;
}
@else
@fragment
fn fragment(in: VertexOutput) {
    let centre = in.color.xyz;
    let rs = in.color.w;
    let im = impostor(in.world_position.xyz, centre, rs, in.uv.x, i32(in.uv.y + 0.5), false);
    if !impostor_keep(im.alpha, in.uv_b.y, im.surf, centre, rs) {
        discard;
    }
}
