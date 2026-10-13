"""Scanned small props: Poly Haven CC0 models decimated + assembled into kit pieces -> scanned_props.glb.

Every piece here REPLACES a procedural piece of the same name in an older kit GLB (the game loads
`scanned_props.glb` after them and a later model of the same name wins in `Kit::by_name`), so the
placement code (`meadow.rs`, `market.rs`) is untouched. The old pieces' footprints are kept:

  bush_a_lod0/1  shrub_02 variants a + d + b  (3 saplings, 5-9k tris each -> ~2.7k; lod1 ~0.45k)  was 211 / 56
  bush_b_lod0/1  shrub_02 variants c + b + d  (likewise)
  market_barrels wine_barrel_01 x3 (BAKED onto a ~450-tri lathe, see below) + wooden_crate_02 + _01   was 744
  meadow_crates  wooden_crate_02 + _01 x2 + wine_barrel_01 + the old piece's sacks                  was 1080

Same recipe as props.py: collapse-decimate keeping the scan's UVs (the 1k normal map carries the
detail the triangles lose), real metres -> game units (1u = 1.35 m), base at Z = 0, white vertex
colour, material named after its texture set (`ph_<id>`, packed by materials.py).
`bush_*` get a vertex-colour leaf tint; the retained sacks keep their old vertex colours.
Pieces are in the kit's frame: game front = +Z = Blender -Y, height = Blender Z.
"""
import json
import math
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
import bmesh  # noqa: E402
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402
from common import OUT, PH, clear_scene, export_glb, load, name_material, save  # noqa: E402

M_TO_UNITS = 1 / 1.35


def tri_count(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def import_model(mid, only=None):
    """Import a Poly Haven glTF; returns its mesh objects with transforms baked (optionally only
    the nodes whose names are in `only`)."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(next((PH / "models" / mid).glob("*.gltf"))))
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH" and (only is None or o.name in only)]
    for o in new:
        if o not in meshes and o.type != "MESH":
            continue
        if o not in meshes:
            bpy.data.objects.remove(o)
    bpy.ops.object.select_all(action="DESELECT")
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    for o in new:
        if o.type != "MESH" and o.name in bpy.data.objects:
            bpy.data.objects.remove(o)
    return meshes


def join(objs):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    return bpy.context.view_layer.objects.active


def decimate(ob, target):
    if tri_count(ob) > target:
        mod = ob.modifiers.new("dec", "DECIMATE")
        mod.ratio = target / tri_count(ob)
        mod.use_collapse_triangulate = True
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.modifier_apply(modifier="dec")


def bbox(ob):
    vs = [v.co for v in ob.data.vertices]
    lo = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
    hi = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
    return lo, hi


def finish(ob, name, mat, target, tint=(1.0, 1.0, 1.0), centre=True):
    """Decimate to `target`, convert to game units, base at Z=0 (and footprint-centred), one
    material, smooth shading, a single UV set + a flat-tinted `Col` layer."""
    ob.name = name
    ob.data.name = name
    decimate(ob, target)
    me = ob.data
    lo, hi = bbox(ob)
    c = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z)) if centre else Vector((0, 0, lo.z))
    for v in me.vertices:
        v.co = (v.co - c) * M_TO_UNITS
    me.materials.clear()
    me.materials.append(name_material(mat))
    for p in me.polygons:
        p.material_index = 0
        p.use_smooth = True
    set_vcol(me, tint)
    while len(me.uv_layers) > 1:
        me.uv_layers.remove(me.uv_layers[-1])
    me.uv_layers[0].name = "UVMap"
    return ob


def set_vcol(me, tint):
    while me.color_attributes:
        me.color_attributes.remove(me.color_attributes[0])
    col = me.color_attributes.new("Col", "FLOAT_COLOR", "CORNER")
    col.data.foreach_set("color", [tint[0], tint[1], tint[2], 1.0] * len(me.loops))
    me.color_attributes.active_color = me.color_attributes["Col"]


def inst(tpl, x, gz, yaw=0.0, s=1.0, z=0.0, tint=None):
    """A placed copy of template `tpl`: game (x, gz) ground position, yaw about the vertical."""
    ob = tpl.copy()
    ob.data = tpl.data.copy()
    bpy.context.scene.collection.objects.link(ob)
    ob.rotation_euler = (0, 0, yaw)
    ob.scale = (s, s, s)
    ob.location = (x, -gz, z)
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    if tint is not None:
        set_vcol(ob.data, tint)
    return ob


def assemble(name, parts, extra=()):
    parts = list(parts) + list(extra)
    ob = join(parts)
    ob.name = name
    ob.data.name = name
    return ob


def old_sacks(piece):
    """The s_cloth part (sacks) of an old town_kit.glb piece, in the piece's own frame, with its
    vertex colours converted to the kit's `Col` layer."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(OUT / "town_kit.glb"))
    new = [o for o in bpy.data.objects if o not in before]
    keep = next(o for o in new if o.type == "MESH" and o.name == piece)
    for o in new:
        if o is not keep and o.name in bpy.data.objects:
            bpy.data.objects.remove(o)
    bpy.ops.object.select_all(action="DESELECT")
    keep.select_set(True)
    bpy.context.view_layer.objects.active = keep
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.separate(type="MATERIAL")
    bpy.ops.object.mode_set(mode="OBJECT")
    parts = [o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith(piece)]
    sacks = next(o for o in parts if o.data.materials and o.data.materials[0].name.split(".")[0] == "s_cloth")
    for o in parts:
        if o is not sacks:
            bpy.data.objects.remove(o)
    bpy.context.view_layer.objects.active = sacks
    bpy.ops.geometry.color_attribute_convert(domain="CORNER", data_type="FLOAT_COLOR")
    me = sacks.data
    me.color_attributes[0].name = "Col"
    me.color_attributes.active_color = me.color_attributes["Col"]
    me.materials[0].name  # keep the original name (s_cloth)
    while len(me.uv_layers) > 1:
        me.uv_layers.remove(me.uv_layers[-1])
    me.uv_layers[0].name = "UVMap"
    return sacks


# --- barrel: bake the scan onto a clean lathe -----------------------------------------------------
# wine_barrel_01 is built of ~560 loose islands (staves, hoops in several pieces); collapse-decimating
# it shreds the hoops at any budget under ~5k tris. So instead its look is BAKED (albedo / tangent
# normal / roughness / AO, 1k) onto a ~450-tri lathe with the barrel's measured stave profile and a
# hand-laid UV atlas (body strip on top, the two end caps below).
BARREL_SEG = 20
BARREL_RINGS = 12
BARREL_ATLAS = 1024


def barrel_profile(high, n_rings=BARREL_RINGS):
    """(z, radius) per ring bottom -> top, metres: the STAVE surface (hoops removed by a rolling
    min), found by casting rays at the scan; plus the rim height."""
    dg = bpy.context.evaluated_depsgraph_get()
    bvh = BVHTree.FromObject(high, dg)
    zs = [i * 0.005 for i in range(int(high.dimensions.z / 0.005) + 1)]
    cx = sum(c.x for c in (high.matrix_world @ Vector(b) for b in high.bound_box)) / 8
    cy = sum(c.y for c in (high.matrix_world @ Vector(b) for b in high.bound_box)) / 8
    rs = []
    for z in zs:
        hits = []
        for k in range(24):
            a = k / 24 * math.tau
            d = Vector((-math.cos(a), -math.sin(a), 0))
            o = Vector((cx + math.cos(a) * 0.8, cy + math.sin(a) * 0.8, z))
            loc, _n, _i, _dist = bvh.ray_cast(o, d)
            if loc is not None:
                hits.append(math.hypot(loc.x - cx, loc.y - cy))
        rs.append(float(np.median(hits)) if hits else 0.0)
    rs = np.array(rs)
    keep = rs > 0.05
    zs, rs = np.array(zs)[keep], rs[keep]
    win = 8  # +-4 cm: wider than a hoop band
    smooth = np.array([rs[max(0, i - win):i + win + 1].min() for i in range(len(rs))])
    top = float(zs[-1])
    ring_z = np.array([top * (0.5 - 0.5 * math.cos(math.pi * i / (n_rings - 1))) for i in range(n_rings)])  # denser at the ends
    ring_z[0] = float(zs[0])
    return [(float(z), float(np.interp(z, zs, smooth)) - 0.004) for z in ring_z], top


def lathe_barrel(profile, name="barrel_low"):
    seg = BARREL_SEG
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    h = profile[-1][0]
    rings = [[bm.verts.new((math.cos(j / seg * math.tau) * r, math.sin(j / seg * math.tau) * r, z)) for j in range(seg)]
             for z, r in profile]
    for i in range(len(rings) - 1):
        for j in range(seg):
            j2 = (j + 1) % seg
            f = bm.faces.new((rings[i][j], rings[i][j2], rings[i + 1][j2], rings[i + 1][j]))
            f.smooth = True
            us = (j / seg, (j + 1) / seg, (j + 1) / seg, j / seg)
            vs = [0.5 + 0.5 * profile[i][0] / h] * 2 + [0.5 + 0.5 * profile[i + 1][0] / h] * 2
            for loop, u, v in zip(f.loops, us, vs):
                loop[uv].uv = (u, v)
    for end, z, r, cu in ((0, profile[0][0], profile[0][1], 0.25), (-1, profile[-1][0], profile[-1][1], 0.75)):
        ring = [bm.verts.new((math.cos(j / seg * math.tau) * r, math.sin(j / seg * math.tau) * r, z)) for j in range(seg)]
        c = bm.verts.new((0, 0, z))
        for j in range(seg):
            j2 = (j + 1) % seg
            tri = (c, ring[j2], ring[j]) if end == 0 else (c, ring[j], ring[j2])
            f = bm.faces.new(tri)
            f.smooth = False
            for loop in f.loops:
                p = loop.vert.co
                loop[uv].uv = (cu + p.x / r * 0.245 * (1 if end == 0 else -1), 0.25 + p.y / r * 0.245)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def bake_pass(low, high, kind, name, size=BARREL_ATLAS, **kw):
    """Bake `kind` (selected-to-active) into a fresh image bound to the low mesh's material."""
    mat = low.data.materials[0]
    nt = mat.node_tree
    img = bpy.data.images.new(f"bake_{name}", size, size, alpha=False)
    img.colorspace_settings.name = "sRGB" if kind == "DIFFUSE" else "Non-Color"
    node = nt.nodes.new("ShaderNodeTexImage")
    node.image = img
    nt.nodes.active = node
    bpy.ops.object.select_all(action="DESELECT")
    high.select_set(True)
    low.select_set(True)
    bpy.context.view_layer.objects.active = low
    bpy.ops.object.bake(type=kind, use_selected_to_active=True, cage_extrusion=0.05, margin=12, margin_type="EXTEND", **kw)
    nt.nodes.remove(node)
    return img


def make_barrel_set(set_name):
    """Import wine_barrel_01, bake its look onto a lathe barrel, write `<set>_{albedo,normal,ormh}.png`;
    returns the (metre-scale) low-poly object."""
    meshes = import_model("wine_barrel_01")
    high = join(meshes)
    high.name = "barrel_high"
    for m in high.data.materials:  # diffuse bake of a metal material is black: bake colour only
        for n in m.node_tree.nodes:
            if n.type == "BSDF_PRINCIPLED":
                for l in list(n.inputs["Metallic"].links):
                    m.node_tree.links.remove(l)
                n.inputs["Metallic"].default_value = 0.0
    profile, top = barrel_profile(high)
    low = lathe_barrel(profile)
    mat = bpy.data.materials.new(set_name)
    mat.use_nodes = True
    low.data.materials.append(mat)
    scn = bpy.context.scene
    scn.render.engine = "CYCLES"
    scn.cycles.device = "CPU"
    scn.cycles.samples = 24
    scn.cycles.use_denoising = False
    scn.render.bake.use_clear = True
    out = {}
    for key, kind, kw in (("albedo", "DIFFUSE", dict(pass_filter={"COLOR"})), ("normal", "NORMAL", dict(normal_space="TANGENT")),
                          ("rough", "ROUGHNESS", {}), ("ao", "AO", {})):
        img = bake_pass(low, high, kind, f"{set_name}_{key}", **kw)
        path = OUT / f"{set_name}_{key}.png"
        img.filepath_raw = str(path)
        img.file_format = "PNG"
        img.save()
        out[key] = path
        print("baked", key, path.name)
    rough = load(out["rough"], 3)[:, :, 0]
    ao = load(out["ao"], 3)[:, :, 0]
    save(np.stack([ao, rough, np.zeros_like(rough), np.full_like(rough, 0.5)], -1), OUT / f"{set_name}_ormh.png")
    for k in ("rough", "ao"):
        out[k].unlink()
    bpy.data.objects.remove(high)
    low.data.materials.clear()
    return low


clear_scene()
templates, final, report = [], [], {}


def template(mid, name, mat, target, only=None, **kw):
    ob = finish(join(import_model(mid, only)), name, mat, target, **kw)
    templates.append(ob)
    return ob


# --- bushes: two shrub_02 saplings per piece ------------------------------------------------------
# The scan's leaves are olive / russet; a gentle green vertex tint brings them to the meadow's palette.
LEAF = (0.80, 0.93, 0.66)
variants = {}
for o in import_model("shrub_02"):
    v = o.name[-1]
    variants[v] = finish(o, f"shrub_{v}", "ph_shrub_02", {"a": 1000, "b": 900, "c": 1000, "d": 800}[v], tint=LEAF)
    templates.append(variants[v])

for piece, mix in {
    "bush_a": (("a", -0.30, 0.10, 0.4, 1.0), ("d", 0.30, -0.12, 2.3, 0.95), ("b", 0.02, 0.38, 4.1, 0.9)),
    "bush_b": (("c", -0.26, -0.10, 1.2, 1.0), ("b", 0.32, 0.10, 3.4, 1.0), ("d", -0.04, 0.34, 5.2, 0.9)),
}.items():
    big = assemble(f"{piece}_lod0", [inst(variants[v], x, z, yaw, sc) for v, x, z, yaw, sc in mix])
    lod1 = big.copy()
    lod1.data = big.data.copy()
    bpy.context.scene.collection.objects.link(lod1)
    lod1.name = lod1.data.name = f"{piece}_lod1"
    decimate(lod1, 450)
    final += [big, lod1]

# --- barrels + crates ----------------------------------------------------------------------------
barrel = finish(make_barrel_set("ph_wine_barrel_01"), "t_barrel", "ph_wine_barrel_01", 100000)
templates.append(barrel)
chest_a = template("wooden_crate_01", "t_chest_a", "ph_wooden_crate_01", 650)
chest_b = template("wooden_crate_02", "t_chest_b", "ph_wooden_crate_02", 600)
hb = (bbox(chest_b)[1].z)  # chest_b height, game units
ha = (bbox(chest_a)[1].z)

final.append(assemble("market_barrels", [
    inst(barrel, 0.0, 0.0, 0.5),
    inst(barrel, 0.62, 0.10, 2.0),
    inst(barrel, 0.30, -0.54, 4.1, 0.92),
    inst(chest_b, -0.62, 0.0, 1.45),
    inst(chest_a, -0.60, 0.04, 1.2, z=hb),
]))

sacks = old_sacks("meadow_crates")
final.append(assemble("meadow_crates", [
    inst(chest_b, -0.30, 0.0, 0.05),
    inst(chest_a, 0.36, 0.08, -0.12),
    inst(chest_a, -0.25, 0.02, 0.2, z=hb),
    inst(barrel, 0.95, -0.12, 1.0),
], extra=[sacks]))

for ob in final:
    report[ob.name] = tri_count(ob)
for t in templates:
    bpy.data.objects.remove(t)
export_glb(OUT / "scanned_props.glb", final)
(OUT / "scanned_props_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
print(report)
print("SCANNED_DONE")
