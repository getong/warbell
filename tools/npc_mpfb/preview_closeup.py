"""Close-up contact sheet of an exported npc_<name>.glb.

    blender -b --factory-startup --python preview_closeup.py -- <export_dir> <npc> <out.png> [clips] [mode]

Env: FULL=1 (whole body) TW/TH (tile px) VIEWS=0,40,90 (deg) ZC/DIST (fractions of height).
rows = clips (first row 'REST' = bind pose), columns = (frame 25%, 60%) x (front, 3/4, side).
mode: tex (baked maps) | diag (body flat red, cloth grey) | skin (body emissive red, cloth textured: any red
      outside face/hands/shins = poke-through) | bodyonly / clothonly (drop the other material's faces).
"""
import bpy, sys, os, math
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
D, NPC, OUTP = argv[0], argv[1], argv[2]
CLIPS = argv[3].split(",") if len(argv) > 3 and argv[3] else ["Idle_FoldArms_Loop", "Idle_Talking_Loop", "Yes", "Walk_Loop"]
MODE = argv[4] if len(argv) > 4 else "tex"
FULL = os.environ.get("FULL") == "1"
TW, TH = int(os.environ.get("TW", 300)), int(os.environ.get("TH", 400))

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=os.path.join(D, f"npc_{NPC}.glb"))
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
body = next(o for o in bpy.data.objects if o.type == 'MESH')


if MODE in ("bodyonly", "clothonly"):
    import bmesh
    drop = "npc_cloth" if MODE == "bodyonly" else "npc_body"
    idx = {i for i, m in enumerate(body.data.materials) if m and m.name.startswith(drop)}
    bm = bmesh.new(); bm.from_mesh(body.data)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index in idx], context='FACES')
    bm.to_mesh(body.data); bm.free()
    MODE = "tex"


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
    if MODE == "skin" and kind == "body":
        b.inputs['Base Color'].default_value = (1.0, 0.0, 0.0, 1); b.inputs['Emission Color'].default_value = (1, 0, 0, 1)
        b.inputs['Emission Strength'].default_value = 2.0
        continue
    if MODE == "diag" and kind in ("body", "cloth"):
        b.inputs['Base Color'].default_value = (0.8, 0.02, 0.02, 1) if kind == "body" else (0.7, 0.7, 0.7, 1)
        b.inputs['Roughness'].default_value = 0.8
        continue
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
        p = os.path.join(D, f"npc_{NPC}_{kind}.png")
        if os.path.exists(p):
            a = tex(nt, p)
            nt.links.new(a.outputs[0], b.inputs['Base Color'])
            nt.links.new(a.outputs[1], b.inputs['Alpha'])
        b.inputs['Roughness'].default_value = 0.65
        try:
            m.surface_render_method = 'DITHERED'
        except Exception:
            pass

sc = bpy.context.scene
eng = bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items
sc.render.engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in eng else 'BLENDER_EEVEE'
sc.render.resolution_x, sc.render.resolution_y = TW, TH
sc.render.film_transparent = False
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes['Background'].inputs[0].default_value = (0.45, 0.5, 0.58, 1)
w.node_tree.nodes['Background'].inputs[1].default_value = 0.9
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", 'SUN')); sc.collection.objects.link(sun)
sun.data.energy = 3.5; sun.rotation_euler = (math.radians(50), 0, math.radians(25))
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
cam.data.lens = 50 if FULL else 70
cam.data.sensor_fit = 'VERTICAL'; cam.data.sensor_height = 24
h = max((body.matrix_world @ v.co).z for v in body.data.vertices)
ZC = h * float(os.environ.get("ZC", 0.5 if FULL else 0.72))
DIST = h * float(os.environ.get("DIST", 2.2 if FULL else 0.95))

VIEWS = [int(x) for x in os.environ.get("VIEWS", "0,40,90").split(",")]  # degrees around Z; 0 = in front of the character (character faces -Y)


def place(az):
    a = math.radians(az)
    pos = Vector((math.sin(a) * DIST, -math.cos(a) * DIST, ZC + 0.05))
    cam.location = pos
    d = Vector((0, 0, ZC)) - pos
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


tmp = os.path.join(os.path.dirname(os.path.abspath(OUTP)), "_tiles")
os.makedirs(tmp, exist_ok=True)
rows = []


def shoot(tag):
    row = []
    for az in VIEWS:
        place(az)
        p = os.path.join(tmp, f"{tag}_{az}.png")
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
        im = bpy.data.images.load(p)
        a = np.array(im.pixels[:], dtype=np.float32).reshape(TH, TW, 4)
        bpy.data.images.remove(im)
        row.append(a)
    return row


arm.animation_data_create()
arm.animation_data.action = None
for pb in arm.pose.bones:
    pb.location = (0, 0, 0); pb.rotation_quaternion = (1, 0, 0, 0); pb.scale = (1, 1, 1)
sc.frame_set(0)
rows.append(shoot("REST") + [np.zeros((TH, TW, 4), np.float32)] * len(VIEWS))
for clip in CLIPS:
    act = next((a for a in bpy.data.actions if a.name == clip or a.name.startswith(clip + "_") or a.name.startswith("NPC_" + clip)), None)
    if act is None:
        print("no clip", clip); continue
    arm.animation_data.action = act
    if hasattr(arm.animation_data, "action_slot") and act.slots:
        arm.animation_data.action_slot = act.slots[0]
    f0, f1 = act.frame_range
    row = []
    for fr in (0.25, 0.6):
        sc.frame_set(int(f0 + (f1 - f0) * fr))
        row += shoot(f"{clip}_{fr}")
    rows.append(row)

sheet = np.concatenate([np.concatenate(r, axis=1) for r in reversed(rows)], axis=0)
H, W = sheet.shape[:2]
out = bpy.data.images.new("sheet", W, H, alpha=False)
out.pixels.foreach_set(sheet.ravel())
out.filepath_raw = OUTP; out.file_format = 'PNG'; out.save()
print("SHEET", OUTP, W, H)
