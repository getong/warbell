// Far-tree IMPOSTORS (`realforest::impostor`), main pass. One camera-facing quad per tree, merged
// into per-region chunk meshes; the fragment stage picks the 4 nearest of the N x N baked
// hemi-octahedral views (`tools/blender_forest/impostors.py`), re-projects the eye ray onto each
// view's own plane with one depth-parallax step, blends them, alpha-tests and lights the result with
// the stock PBR path (sun + IBL + shadows + fog), so a far tree turns and shades like the real mesh.
//
// Vertex data (per corner): POSITION = tree base + model centre + corner offset (so the chunk AABB
// is right), UV_0 = corner (-1|1, -1|1), UV_1 = (scale, yaw), COLOR = (layer, snow, 0, 0).
// Per-tree data rides the stock varyings: color = (centre, radius), uv = (yaw, layer),
// uv_b = (snow, far fade). `impostor_prepass.wesl` mirrors all of this (keep the two in sync).

import bevy_pbr::{
    render::mesh_functions,
    render::forward_io::{Vertex, VertexOutput, FragmentOutput, decompress_vertex},
    render::view_transformations::position_world_to_clip,
    render::mesh_view_bindings::view,
    render::mesh_bindings::mesh,
    render::pbr_types,
    render::pbr_functions,
};
@if(SCREEN_SPACE_AMBIENT_OCCLUSION)
import bevy_pbr::render::mesh_view_bindings::screen_space_ambient_occlusion_texture;
@if(SCREEN_SPACE_AMBIENT_OCCLUSION)
import bevy_pbr::ssao::utils::ssao_multibounce;

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
    // Near hand-off: the impostor thins IN over the band where the LOD0 crown thins OUT
    // (`foliage::dissolve` on the tree canopy), so the swap is a clump-by-clump cross-fade.
    let fade = min(1.0 - smoothstep(ip.far.x, ip.far.y, d), smoothstep(ip.cfg.z, ip.cfg.z + IMP_FADE_IN, d));
    out.world_position = vec4<f32>(wp, 1.0);
    out.position = position_world_to_clip(wp);
    if d < ip.cfg.z || d > ip.far.y {
        out.position = vec4<f32>(0.0, 0.0, -1.0, 1.0);
    }
    out.world_normal = dir;
    out.color = vec4<f32>(centre, rs);
    out.uv = vec2<f32>(yaw, f32(layer));
    out.uv_b = vec2<f32>(v.color.y, fade);
@if(VERTEX_OUTPUT_INSTANCE_INDEX)
    out.instance_index = v.instance_index;
    return out;
}

// Width of the LOD0 -> impostor cross-fade (world units). Keep in sync with
// `realforest::impostor::IMP_FADE_IN`.
const IMP_FADE_IN: f32 = 10.0;

struct Imp {
    albedo: vec3<f32>,
    alpha: f32,
    // coverage of the dominant view alone: what the alpha test reads (see `impostor_keep`)
    cov: f32,
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

    var acc = Imp(vec3<f32>(0.0), 0.0, 0.0, vec3<f32>(0.0), vec3<f32>(0.0));
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
            acc.cov = a.a;
        }
    }
    acc.n = normalize(acc.n + vec3<f32>(0.0, 1e-4, 0.0));
    acc.surf = centre + rot_y(acc.surf, yaw) * rs;
    return acc;
}

/// The alpha test runs on the DOMINANT view's coverage, not the 4-view blend: the crown mass is
/// the same in every view but the gaps aren't, so averaging then thresholding filled the holes and
/// a far tree read fuller than the real crown it replaces (the "LOD pops thinner" swap).
/// The alpha test, with the far-band dissolve: past the fade start whole leaf clumps (object-space
/// value noise, not a screen pattern) drop out as `fade` falls to 0.
fn impostor_keep(alpha: f32, fade: f32, surf: vec3<f32>, centre: vec3<f32>, rs: f32) -> bool {
    let lp = (surf - centre) / rs;
    let n = ip_noise(lp.xy * 5.0 + lp.z * 3.1) * 0.7 + ip_noise(lp.zy * 13.0) * 0.3;
    return alpha >= ip.cfg.y && n < fade * 1.02;
}

@fragment
fn fragment(in: VertexOutput, @builtin(front_facing) is_front: bool) -> FragmentOutput {
    let centre = in.color.xyz;
    let rs = in.color.w;
    let yaw = in.uv.x;
    let layer = i32(in.uv.y + 0.5);
    // No alpha test here: the prepass wrote the exact alpha-tested depth and this pass draws with
    // an EQUAL depth test (`ImpostorExt::specialize`), so only visible texels are shaded at all.
    let im = impostor(in.world_position.xyz, centre, rs, yaw, layer, true);
@if(IMPOSTOR_ALPHA_TEST) {
    // No prepass (low presets): do the alpha test + far dissolve here, as the prepass would have.
    if !impostor_keep(im.cov, in.uv_b.y, im.surf, centre, rs) {
        discard;
    }
}
    var col = im.albedo / max(im.alpha, 1e-3);
    // Crown colour variety, as `foliage_wind.wesl` tints the real crowns (same per-tree hash on the
    // tree base, so the swap doesn't shift a tree's green). Green texels only (bark stays put).
    let base = centre - rot_y(ip.models[layer].xyz * (rs / ip.models[layer].w), yaw);
    let nv = clamp(ip_hash(floor(base.xz * 2.0)) * 0.6
        + (sin(im.surf.x * 0.071) * sin(im.surf.z * 0.053)) * 0.4 + 0.2, 0.0, 1.0);
    let tint = mix(vec3<f32>(1.10, 1.05, 0.78), vec3<f32>(0.80, 0.93, 0.88), nv);
    let leafy = clamp((col.g - col.r) * 8.0, 0.0, 1.0) * ip.far.z;
    col *= mix(vec3<f32>(1.0), tint, leafy);
    let nw = normalize(rot_y(im.n, yaw));
    // Snow-dusted twins (snow biome): powder on the sky-facing texels.
    let snow = in.uv_b.x;
    if snow > 0.0 {
        let s = smoothstep(0.35, 0.85, nw.y) * snow;
        col = mix(col, vec3<f32>(0.80, 0.84, 0.90), s);
    }

    var pbr = pbr_types::pbr_input_new();
    pbr.flags = mesh[in.instance_index].flags;
    pbr.is_orthographic = is_ortho();
    pbr.frag_coord = in.position;
    pbr.world_position = vec4<f32>(im.surf, 1.0);
    pbr.V = pbr_functions::calculate_view(pbr.world_position, pbr.is_orthographic);
    pbr.world_normal = nw;
    pbr.N = nw;
    pbr.material.base_color = vec4<f32>(col, 1.0);
    pbr.material.perceptual_roughness = 0.66;
    pbr.material.reflectance = vec3<f32>(0.3);
    pbr.material.metallic = 0.0;
    pbr.material.flags = pbr_types::STANDARD_MATERIAL_FLAGS_FOG_ENABLED_BIT | pbr_types::STANDARD_MATERIAL_FLAGS_ALPHA_MODE_MASK;
@if(SCREEN_SPACE_AMBIENT_OCCLUSION) {
    let ssao = textureLoad(screen_space_ambient_occlusion_texture, vec2<i32>(in.position.xy - view.viewport.xy), 0i).r;
    pbr.diffuse_occlusion = vec3<f32>(min(1.0, ssao_multibounce(ssao, col).x));
}
    var out: FragmentOutput;
    out.color = pbr_functions::apply_pbr_lighting(pbr);
    out.color = pbr_functions::main_pass_post_lighting_processing(pbr, out.color);
    return out;
}
