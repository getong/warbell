"""Scanned forest props: Poly Haven CC0 models decimated to game budgets -> props.glb.

  stump_a     tree_stump_01           (~41k tris -> ~1k)
  log_a       dead_tree_trunk         (~102k -> ~1.4k)  fallen trunk
  branches_a  dry_branches_medium_01  (~17k -> ~0.7k)   floor deadfall
  rock_*      rock_moss_set_01 / _02  (each rock -> ~350)

Collapse decimation keeps the scan's UVs, so the original 1k normal maps (packed by
materials.py as prop_* sets) still carry the high-frequency detail the triangles lost.
Real-world metres are converted to game units (hero ~1.3u ~ 1.75m -> 1u ~ 1.35m), each
object is re-centred on its footprint with its base at Z=0, and given a white vertex
colour layer so every forest mesh shares one attribute set when the game merges chunks.
"""
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402
from common import OUT, PH, clear_scene, export_glb, name_material  # noqa: E402

M_TO_UNITS = 1 / 1.35

JOBS = [
    # (model id, output name or None for "one per object", material, target tris, extra scale, sink)
    ("tree_stump_01", "stump_a", "prop_stump", 1000, 1.0, 0.04),
    ("dead_tree_trunk", "log_a", "prop_log", 1400, 1.0, 0.06),
    ("dry_branches_medium_01", "branches_a", "prop_branches", 700, 1.0, 0.01),
    ("rock_moss_set_01", None, "prop_rock_a", 350, 1.0, 0.08),
    ("rock_moss_set_02", None, "prop_rock_b", 350, 1.0, 0.08),
]


def tri_count(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def import_model(mid):
    before = set(bpy.data.objects)
    gltf = next((PH / "models" / mid).glob("*.gltf"))
    bpy.ops.import_scene.gltf(filepath=str(gltf))
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH"]
    # Bake parent transforms so every mesh stands on its own.
    bpy.ops.object.select_all(action="DESELECT")
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    for o in new:
        if o.type != "MESH":
            bpy.data.objects.remove(o)
    return meshes


def finish(ob, name, mat, target, scale, sink):
    ob.name = name
    ob.data.name = name
    if tri_count(ob) > target:
        mod = ob.modifiers.new("dec", "DECIMATE")
        mod.ratio = target / tri_count(ob)
        mod.use_collapse_triangulate = True
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.modifier_apply(modifier="dec")
    me = ob.data
    s = M_TO_UNITS * scale
    lo = Vector((min(v.co.x for v in me.vertices), min(v.co.y for v in me.vertices), min(v.co.z for v in me.vertices)))
    hi = Vector((max(v.co.x for v in me.vertices), max(v.co.y for v in me.vertices), max(v.co.z for v in me.vertices)))
    centre = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
    for v in me.vertices:
        v.co = (v.co - centre) * s - Vector((0, 0, sink))
    me.materials.clear()
    me.materials.append(name_material(mat))
    for p in me.polygons:
        p.material_index = 0
        p.use_smooth = True
    while me.color_attributes:
        me.color_attributes.remove(me.color_attributes[0])
    col = me.color_attributes.new("Col", "FLOAT_COLOR", "CORNER")
    col.data.foreach_set("color", [1.0] * (len(me.loops) * 4))
    me.color_attributes.active_color = me.color_attributes["Col"]
    while len(me.uv_layers) > 1:
        me.uv_layers.remove(me.uv_layers[-1])
    return ob


clear_scene()
objs, report = [], {}
for mid, name, mat, target, scale, sink in JOBS:
    meshes = import_model(mid)
    if name:
        bpy.ops.object.select_all(action="DESELECT")
        for o in meshes:
            o.select_set(True)
        bpy.context.view_layer.objects.active = meshes[0]
        if len(meshes) > 1:
            bpy.ops.object.join()
        ob = finish(bpy.context.view_layer.objects.active, name, mat, target, scale, sink)
        objs.append(ob)
        report[name] = tri_count(ob)
    else:
        base = mid.replace("rock_moss_set_", "rock_")
        for i, o in enumerate(sorted(meshes, key=lambda o: o.name)):
            ob = finish(o, f"{base}_{chr(97 + i)}", mat, target, scale, sink)
            objs.append(ob)
            report[ob.name] = tri_count(ob)
export_glb(OUT / "props.glb", objs)
(OUT / "props_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
print(report)
print("PROPS_DONE")
