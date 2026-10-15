"""Bake hemi-octahedral IMPOSTOR atlases for the kit trees (far-LOD billboards, `realforest::impostor`).

    blender -b --factory-startup --python tools/blender_forest/impostors.py [-- name ...]

For every tree model that has a `_lod0`/`_lod1` pair in trees.glb / swamp_flora.glb / alpine_flora.glb,
renders the LOD0 mesh from N x N view directions spread over the upper hemisphere (hemi-octahedral
mapping, the same encode/decode as `assets/shaders/impostor.wesl`) into two atlases:

- `impostor_<name>_albedo.png`  sRGB base colour (texture x vertex colour), alpha = card coverage
- `impostor_<name>_nd.png`      linear: rgb = model-space normal (game axes, *0.5+0.5),
                                a = depth along the view direction in bounding-sphere radii (*0.5+0.5)

All N*N views are ONE render per pass: N*N linked copies of the tree, each rotated so its frame's view
direction faces the (orthographic, top-down) camera, laid out on the atlas grid. Geometry only: the
emission-only materials need no lights.

Writes the PNGs to IMPOSTOR_OUT (default target/impostors, not tracked) and the per-model bounds
to assets/forest_pbr/impostors.json; then `PACK_ONLY=impostor cargo run --release --example
pack_forest_textures` packs them into the two BC7 array DDS files the game loads.
"""
import json
import math
import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402
from common import OUT, REPO, clear_scene, load, save  # noqa: E402

N = int(os.environ.get("IMPOSTOR_FRAMES", 8))
FRAME = int(os.environ.get("IMPOSTOR_FRAME_PX", 128))
SS = 2  # supersampling factor of the render over the atlas
CUTOFF = 0.42  # the kit's card alpha-test cutoff (`realforest::CARD_CUTOFF`)
GLBS = ["trees.glb", "swamp_flora.glb", "alpine_flora.glb"]
SKIP = ("bush_",)
CARDS = ("canopy", "swamp_cards", "undergrowth")
DST = Path(os.environ.get("IMPOSTOR_OUT", REPO / "target" / "impostors"))

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def g2b(v):
    """Game (Y-up) -> Blender (Z-up), the glTF importer's axis swap."""
    return Vector((v[0], -v[2], v[1]))


def b2g(v):
    return Vector((v[0], v[2], -v[1]))


def oct_decode(gx, gy):
    """Hemi-octahedral grid coords in [-1,1]^2 -> unit view direction (game space, y >= 0)."""
    x = (gx + gy) * 0.5
    z = (gx - gy) * 0.5
    y = 1.0 - abs(x) - abs(z)
    return Vector((x, y, z)).normalized()


def frame_basis(d):
    """(right, up) of the frame seen from direction `d` (camera at +d looking at the centre)."""
    r = Vector((0, 1, 0)).cross(d)
    r = Vector((1, 0, 0)) if r.length < 1e-4 else r.normalized()
    return r, d.cross(r)


def tex(nt, name, non_color):
    n = nt.nodes.new("ShaderNodeTexImage")
    n.image = bpy.data.images.load(str(OUT / name), check_existing=True)
    n.image.colorspace_settings.name = "Non-Color" if non_color else "sRGB"
    n.interpolation = "Linear"
    return n


def build(mat, mode, uv_name, col_name):
    """Emission-only material for one bake pass: 'albedo' | 'normal' | 'depth'."""
    base = mat.name.split(".")[0]
    card = base in CARDS
    has_tex = (OUT / f"{base}_albedo.dds").exists()
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    L = nt.links.new
    outn = nt.nodes.new("ShaderNodeOutputMaterial")
    emit = nt.nodes.new("ShaderNodeEmission")
    transp = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    L(transp.outputs[0], mix.inputs[1])
    L(emit.outputs[0], mix.inputs[2])
    L(mix.outputs[0], outn.inputs[0])
    uv = nt.nodes.new("ShaderNodeUVMap")
    uv.uv_map = uv_name
    alb = None
    if has_tex:
        alb = tex(nt, f"{base}_albedo.dds", False)
        L(uv.outputs[0], alb.inputs[0])
    # Hard alpha test at the game's cutoff (cards only; everything else is solid).
    if card and alb is not None:
        gt = nt.nodes.new("ShaderNodeMath")
        gt.operation = "GREATER_THAN"
        gt.inputs[1].default_value = CUTOFF
        L(alb.outputs[1], gt.inputs[0])
        L(gt.outputs[0], mix.inputs[0])
    else:
        mix.inputs[0].default_value = 1.0
    if mode == "albedo":
        vc = nt.nodes.new("ShaderNodeVertexColor")
        vc.layer_name = col_name
        if alb is not None:
            mul = nt.nodes.new("ShaderNodeMix")
            mul.data_type = "RGBA"
            mul.blend_type = "MULTIPLY"
            mul.inputs[0].default_value = 1.0
            L(alb.outputs[0], mul.inputs[6])
            L(vc.outputs[0], mul.inputs[7])
            L(mul.outputs[2], emit.inputs[0])
        else:
            L(vc.outputs[0], emit.inputs[0])
        return
    if mode == "normal":
        geo = nt.nodes.new("ShaderNodeNewGeometry")
        if has_tex and (OUT / f"{base}_normal.dds").exists():
            nm = tex(nt, f"{base}_normal.dds", True)
            L(uv.outputs[0], nm.inputs[0])
            nmap = nt.nodes.new("ShaderNodeNormalMap")
            nmap.uv_map = uv_name
            L(nm.outputs[0], nmap.inputs[1])
            n_out = nmap.outputs[0]
        else:
            n_out = geo.outputs["Normal"]
        # Blender flips the shading normal on back faces; the game draws the cards single-normal
        # (crown-outward bent normals on both faces), so flip it back.
        sgn = nt.nodes.new("ShaderNodeMath")
        sgn.operation = "MULTIPLY_ADD"
        sgn.inputs[1].default_value = -2.0
        sgn.inputs[2].default_value = 1.0
        L(geo.outputs["Backfacing"], sgn.inputs[0])
        flip = nt.nodes.new("ShaderNodeVectorMath")
        flip.operation = "SCALE"
        L(n_out, flip.inputs[0])
        L(sgn.outputs[0], flip.inputs["Scale"])
        vt = nt.nodes.new("ShaderNodeVectorTransform")
        vt.vector_type = "NORMAL"
        vt.convert_from = "WORLD"
        vt.convert_to = "OBJECT"
        L(flip.outputs[0], vt.inputs[0])
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        L(vt.outputs[0], sep.inputs[0])
        neg = nt.nodes.new("ShaderNodeMath")
        neg.operation = "MULTIPLY"
        neg.inputs[1].default_value = -1.0
        L(sep.outputs[1], neg.inputs[0])
        comb = nt.nodes.new("ShaderNodeCombineXYZ")  # game axes: (x, z, -y)
        L(sep.outputs[0], comb.inputs[0])
        L(sep.outputs[2], comb.inputs[1])
        L(neg.outputs[0], comb.inputs[2])
        enc = nt.nodes.new("ShaderNodeVectorMath")
        enc.operation = "MULTIPLY_ADD"
        enc.inputs[1].default_value = (0.5, 0.5, 0.5)
        enc.inputs[2].default_value = (0.5, 0.5, 0.5)
        L(comb.outputs[0], enc.inputs[0])
        L(enc.outputs[0], emit.inputs[0])
        return
    # depth: world Z (toward the camera) in radii, every copy's sphere centre sits at z = 0.
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    L(geo.outputs["Position"], sep.inputs[0])
    m = nt.nodes.new("ShaderNodeMath")
    m.operation = "MULTIPLY_ADD"
    m.inputs[1].default_value = 0.5 / build.radius
    m.inputs[2].default_value = 0.5
    m.use_clamp = True
    L(sep.outputs[2], m.inputs[0])
    L(m.outputs[0], emit.inputs[0])


build.radius = 1.0


def render(path, raw):
    scene = bpy.context.scene
    scene.view_settings.view_transform = "Raw" if raw else "Standard"
    scene.view_settings.look = "None"
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    return load(path)


def downsample(img, srgb):
    """SSxSS area average, alpha-weighted (premultiplied), linear-light for sRGB colour."""
    h, w = img.shape[:2]
    rgb = img[:, :, :3].copy()
    a = img[:, :, 3:4]
    if srgb:
        rgb = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    pm = np.concatenate([rgb * a, a], axis=2)
    pm = pm.reshape(h // SS, SS, w // SS, SS, 4).mean(axis=(1, 3))
    out_a = pm[:, :, 3:4]
    out_rgb = pm[:, :, :3] / np.maximum(out_a, 1e-6)
    if srgb:
        out_rgb = np.where(out_rgb <= 0.0031308, out_rgb * 12.92, 1.055 * np.clip(out_rgb, 0, None) ** (1 / 2.4) - 0.055)
    return np.concatenate([np.clip(out_rgb, 0, 1), out_a], axis=2)


def dilate(rgb, mask, iters=12):
    """Push valid texels' colour outward into the transparent area (no dark halos in the mips)."""
    rgb = rgb.copy()
    m = mask.astype(np.float32)
    for _ in range(iters):
        acc = np.zeros_like(rgb)
        cnt = np.zeros_like(m)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                acc += np.roll(np.roll(rgb * m[..., None], dy, 0), dx, 1)
                cnt += np.roll(np.roll(m, dy, 0), dx, 1)
        fill = (m == 0) & (cnt > 0)
        rgb[fill] = acc[fill] / cnt[fill][:, None]
        m = np.where(fill, 1.0, m)
    if (m == 0).any() and (m > 0).any():
        rgb[m == 0] = rgb[m > 0].mean(axis=0)
    return rgb


def bake(obj, name):
    me = obj.data
    uv_name = me.uv_layers[0].name if me.uv_layers else ""
    col_name = me.color_attributes[0].name if me.color_attributes else ""
    # Bounds in game space (the model's own frame: base at y=0).
    vs = [b2g(v.co) for v in me.vertices]
    lo = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
    hi = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
    c = (lo + hi) * 0.5
    R = max((v - c).length for v in vs) * 1.01
    build.radius = R
    scene = bpy.context.scene
    # N*N rotated copies on the atlas grid.
    copies = []
    obj.hide_render = True
    for j in range(N):
        for i in range(N):
            d = oct_decode((i + 0.5) / N * 2 - 1, (j + 0.5) / N * 2 - 1)
            r, u = frame_basis(d)
            rot = Matrix((g2b(r), g2b(u), g2b(d))).to_4x4()
            cell = Vector(((i + 0.5 - N / 2) * 2 * R, (N / 2 - j - 0.5) * 2 * R, 0))
            cp = obj.copy()
            scene.collection.objects.link(cp)
            cp.hide_render = False
            cp.matrix_world = Matrix.Translation(cell) @ rot @ Matrix.Translation(-g2b(c))
            copies.append(cp)
    cam = scene.camera
    cam.data.ortho_scale = N * 2 * R
    cam.location = (0, 0, 4 * R + 10)
    cam.data.clip_end = 8 * R + 40
    tmp = DST / "_tmp.png"
    passes = {}
    for mode in ("albedo", "normal", "depth"):
        for slot in obj.material_slots:
            if slot.material:
                build(slot.material, mode, uv_name, col_name)
        passes[mode] = downsample(render(tmp, mode != "albedo"), mode == "albedo")
    for cp in copies:
        bpy.data.objects.remove(cp)
    alb = passes["albedo"]
    mask = alb[:, :, 3] > 0.02
    albedo = np.concatenate([dilate(alb[:, :, :3], mask), alb[:, :, 3:4]], axis=2)
    nd = np.concatenate([passes["normal"][:, :, :3], passes["depth"][:, :, :1]], axis=2)
    nd = dilate(nd, mask)
    save(albedo, DST / f"impostor_{name}_albedo.png")
    save(nd, DST / f"impostor_{name}_nd.png")
    cover = float(mask.mean())
    print(f"IMPOSTOR {name}: R={R:.3f} c=({c.x:.3f},{c.y:.3f},{c.z:.3f}) coverage={cover:.3f}")
    return {"name": name, "center": [c.x, c.y, c.z], "radius": R}


def main():
    clear_scene()
    scene = bpy.context.scene
    for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = eng
            break
        except TypeError:
            pass
    side = N * FRAME * SS
    scene.render.resolution_x = scene.render.resolution_y = side
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.filter_size = 1.0
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "16"
    try:
        scene.eevee.taa_render_samples = 8
    except AttributeError:
        pass
    world = bpy.data.worlds.new("w")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.0
    scene.world = world
    cam = bpy.data.cameras.new("cam")
    cam.type = "ORTHO"
    co = bpy.data.objects.new("cam", cam)
    scene.collection.objects.link(co)
    scene.camera = co
    for g in GLBS:
        bpy.ops.import_scene.gltf(filepath=str(OUT / g))
    objs = {o.name: o for o in scene.objects if o.type == "MESH"}
    for o in objs.values():
        o.hide_render = True
        # The importer may parent under an empty; bake in the mesh's own frame.
        o.parent = None
        o.matrix_world = Matrix.Identity(4)
    names = sorted(n[: -len("_lod0")] for n in objs if n.endswith("_lod0") and n[:-5] + "_lod1" in objs)
    names = [n for n in names if not n.startswith(SKIP)]
    if argv:
        names = [n for n in names if n in argv]
    DST.mkdir(parents=True, exist_ok=True)
    print("IMPOSTOR models:", names)
    print("IMPOSTOR materials:", sorted({m.name for m in bpy.data.materials}))
    models = [bake(objs[n + "_lod0"], n) for n in names]
    if not argv:
        meta = {"frames": N, "frame_px": FRAME, "cutoff": CUTOFF, "models": models}
        (OUT / "impostors.json").write_text(json.dumps(meta, indent=1))
        print("IMPOSTOR wrote", OUT / "impostors.json")


main()
