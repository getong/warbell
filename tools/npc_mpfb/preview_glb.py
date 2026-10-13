"""Render an exported npc_<name>.glb (+ its PNG maps) in a few clips, to check bake/skin/clips.

    blender -b --factory-startup --python preview_glb.py -- <export_dir> <npc> <out.png> [clip,clip,...]

Writes one contact sheet row per clip (frames at 0 / 33 / 66 %), front-3/4 view, plain lighting.
"""
import bpy, sys, os, math

argv = sys.argv[sys.argv.index("--") + 1:]
D, NPC, OUTP = argv[0], argv[1], argv[2]
CLIPS = argv[3].split(",") if len(argv) > 3 else ["Idle_Loop", "Walk_Loop", "TreeChopping_Loop", "Sitting_Idle_Loop"]

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=os.path.join(D, f"npc_{NPC}.glb"))
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
body = next(o for o in bpy.data.objects if o.type == 'MESH')


def tex(nt, path, nc=False):
    t = nt.nodes.new('ShaderNodeTexImage')
    t.image = bpy.data.images.load(path)
    if nc:
        t.image.colorspace_settings.name = 'Non-Color'
    return t


for m in body.data.materials:
    m.use_nodes = True
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    kind = m.name.replace("npc_", "")
    if kind in ("body", "cloth"):
        a = tex(nt, os.path.join(D, f"npc_{NPC}_albedo.png"))
        nt.links.new(a.outputs[0], b.inputs['Base Color'])
        n = tex(nt, os.path.join(D, f"npc_{NPC}_normal.png"), True)
        nm = nt.nodes.new('ShaderNodeNormalMap')
        nt.links.new(n.outputs[0], nm.inputs['Color'])
        nt.links.new(nm.outputs[0], b.inputs['Normal'])
        o = tex(nt, os.path.join(D, f"npc_{NPC}_orm.png"), True)
        sp = nt.nodes.new('ShaderNodeSeparateColor')
        nt.links.new(o.outputs[0], sp.inputs[0])
        nt.links.new(sp.outputs[1], b.inputs['Roughness'])
    else:
        a = tex(nt, os.path.join(D, f"npc_{NPC}_{kind}.png"))
        nt.links.new(a.outputs[0], b.inputs['Base Color'])
        nt.links.new(a.outputs[1], b.inputs['Alpha'])
        b.inputs['Roughness'].default_value = 0.65
        m.blend_method = 'HASHED' if hasattr(m, "blend_method") else None

sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items else 'BLENDER_EEVEE'
sc.render.resolution_x, sc.render.resolution_y = 360, 520
sc.render.film_transparent = False
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes['Background'].inputs[0].default_value = (0.45, 0.5, 0.58, 1)
w.node_tree.nodes['Background'].inputs[1].default_value = 0.8
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", 'SUN')); sc.collection.objects.link(sun)
sun.data.energy = 3.5; sun.rotation_euler = (math.radians(50), 0, math.radians(35))
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
cam.data.lens = 50
h = max((body.matrix_world @ v.co).z for v in body.data.vertices)
cam.location = (2.6, -3.9, h * 0.62)
cam.rotation_euler = (math.radians(86), 0, math.radians(34))
cam.location = (2.6 * h / 1.75 * 1.4, -3.9 * h / 1.75 * 1.4, h * 0.55)

tiles = []
for clip in CLIPS:
    act = next((a for a in bpy.data.actions if a.name == clip or a.name.startswith(clip + "_") or a.name.startswith("NPC_" + clip)), None)
    if act is None:
        print("no clip", clip); continue
    arm.animation_data_create(); arm.animation_data.action = act
    if hasattr(arm.animation_data, "action_slot") and act.slots:
        arm.animation_data.action_slot = act.slots[0]
    f0, f1 = act.frame_range
    for i, fr in enumerate((0.0, 0.33, 0.66)):
        sc.frame_set(int(f0 + (f1 - f0) * fr))
        p = os.path.join(os.path.dirname(OUTP), f"_tile_{clip}_{i}.png")
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
        tiles.append(p)
print("TILES", ";".join(tiles))
