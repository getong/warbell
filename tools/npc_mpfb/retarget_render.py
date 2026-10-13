"""Retarget Quaternius UAL clips onto the Bartender rig and render frames.

blender -b --factory-startup bartender-IK.blend --python retarget_render.py -- OUTDIR MODE [clip ...]
  MODE = test  -> one frame (middle) per clip      MODE = full -> every frame of each clip (loops repeated)
  clip = ual1:Walk_Loop | ual2:Farm_Harvest
"""
import bpy, sys, math, os
from mathutils import Matrix, Vector, Quaternion

argv = sys.argv[sys.argv.index('--') + 1:]
OUT, MODE, CLIPS = argv[0], argv[1], argv[2:]
D = "C:/Users/skibi/Documents/Codex/downloads/"
SRC = {
    'ual1': D + "ual1/x/Animation Library[Standard]/Godot/AnimationLibrary_Godot_Standard.glb",
    'ual2': D + "ual2/x/Universal Animation Library 2 [Standard]/Unreal-Godot/UAL2_Standard.glb",
}
TEX = "C:/Users/skibi/AppData/Local/Temp/claude/C--Users-skibi-Documents-Codex-warbell/d20dbeee-b64c-418e-bc22-46a2bdca17e6/scratchpad/tex/"

tgt = bpy.data.objects['Armatue']
mesh = bpy.data.objects['Bartender']

# ---- clean the target: no IK/constraints/animation, single armature modifier
for pb in tgt.pose.bones:
    for c in list(pb.constraints):
        pb.constraints.remove(c)
    pb.rotation_mode = 'QUATERNION'
tgt.animation_data_clear()
for m in list(mesh.modifiers):
    if m.type == 'ARMATURE' and m.object is None:
        mesh.modifiers.remove(m)
for o in list(bpy.data.objects):
    if o.type in ('LIGHT', 'CAMERA'):
        bpy.data.objects.remove(o)

# ---- materials (the legacy texture slots were dropped on load): rebuild as PBR nodes
def load(name):
    return bpy.data.images.load(TEX + name, check_existing=True)

def build_mat(name, albedo, normal=None, alpha=False, rough=0.62, spec=0.35, uvname='UVMap'):
    m = bpy.data.materials[name]
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Roughness'].default_value = rough
    bsdf.inputs['Specular IOR Level'].default_value = spec
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    uv = nt.nodes.new('ShaderNodeUVMap'); uv.uv_map = uvname
    a = nt.nodes.new('ShaderNodeTexImage'); a.image = load(albedo)
    nt.links.new(uv.outputs[0], a.inputs[0])
    nt.links.new(a.outputs['Color'], bsdf.inputs['Base Color'])
    if alpha:
        nt.links.new(a.outputs['Alpha'], bsdf.inputs['Alpha'])
        m.blend_method = 'HASHED' if hasattr(m, 'blend_method') else None
    if normal:
        n = nt.nodes.new('ShaderNodeTexImage'); n.image = load(normal); n.image.colorspace_settings.name = 'Non-Color'
        nm = nt.nodes.new('ShaderNodeNormalMap')
        nt.links.new(uv.outputs[0], n.inputs[0])
        nt.links.new(n.outputs['Color'], nm.inputs['Color'])
        nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
    return m

build_mat('Body', 'body-skin.png', 'body-norm.png', rough=0.8, spec=0.2, uvname='UVmap')
build_mat('Head', 'head-skin.png', 'head-norm.png', rough=0.55, spec=0.4)
hair = build_mat('Hair', 'hair-skin.png', None, alpha=True, rough=0.45, spec=0.5)

# ---- import the animation sources
src_arms = {}
for key in sorted({c.split(':')[0] for c in CLIPS}):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=SRC[key])
    new = set(bpy.data.objects) - before
    arm = next(o for o in new if o.type == 'ARMATURE')
    for o in new:
        if o.type == 'MESH':
            bpy.data.objects.remove(o)
    src_arms[key] = arm
    arm.hide_render = True
    arm.animation_data_create()
    for tr in list(arm.animation_data.nla_tracks):
        arm.animation_data.nla_tracks.remove(tr)

# ---- bone maps (target -> source)
FING = ['index', 'middle', 'pinky', 'ring']
def map_ual1():
    m = {'Hips': 'DEF-hips', 'ToSpine': 'DEF-spine.001', 'Spine': 'DEF-spine.002', 'Spine1': 'DEF-spine.003',
         'Neck': 'DEF-neck', 'Head': 'DEF-head'}
    for s, S in (('L', 'L'), ('R', 'R')):
        m.update({f'Shoulder_{s}': f'DEF-shoulder.{S}', f'Arm_{s}': f'DEF-upper_arm.{S}', f'ForeArm_{s}': f'DEF-forearm.{S}',
                  f'Hand_{s}': f'DEF-hand.{S}', f'UpLeg_{s}': f'DEF-thigh.{S}', f'Leg_{s}': f'DEF-shin.{S}',
                  f'Foot_{s}': f'DEF-foot.{S}', f'ToeBase_{s}': f'DEF-toe.{S}'})
        for f in FING:
            for i in (1, 2, 3):
                m[f'f_{f}.0{i}.{s}'] = f'DEF-f_{f}.0{i}.{S}'
        for i in (1, 2, 3):
            m[f'thumb.0{i}.{s}'] = f'DEF-thumb.0{i}.{S}'
    return m

def map_ual2():
    m = {'Hips': 'pelvis', 'ToSpine': 'spine_01', 'Spine': 'spine_02', 'Spine1': 'spine_03', 'Neck': 'neck_01', 'Head': 'Head'}
    for s in ('L', 'R'):
        l = s.lower()
        m.update({f'Shoulder_{s}': f'clavicle_{l}', f'Arm_{s}': f'upperarm_{l}', f'ForeArm_{s}': f'lowerarm_{l}',
                  f'Hand_{s}': f'hand_{l}', f'UpLeg_{s}': f'thigh_{l}', f'Leg_{s}': f'calf_{l}',
                  f'Foot_{s}': f'foot_{l}', f'ToeBase_{s}': f'ball_{l}'})
        for f in FING:
            for i in (1, 2, 3):
                m[f'f_{f}.0{i}.{s}'] = f'{f}_0{i}_{l}'
        for i in (1, 2, 3):
            m[f'thumb.0{i}.{s}'] = f'thumb_0{i}_{l}'
    return m

MAPS = {'ual1': map_ual1(), 'ual2': map_ual2()}
SWING = {'Shoulder', 'Arm', 'ForeArm', 'Hand', 'UpLeg', 'Leg', 'Foot', 'ToeBase'}

def rest_rot(arm, bone):
    return (arm.matrix_world.to_3x3() @ bone.matrix_local.to_3x3())

def rest_dir(arm, bone):
    return (arm.matrix_world.to_3x3() @ (bone.tail_local - bone.head_local)).normalized()

class Retarget:
    def __init__(self, key):
        self.src = src_arms[key]
        self.map = MAPS[key]
        sd, td = self.src.data.bones, tgt.data.bones
        self.q = {}
        hand_q = {}
        for t, s in self.map.items():
            tb, sb = td[t], sd[s]
            base = t.split('_')[0]
            side = t[-1]
            if base in SWING:
                q = rest_dir(tgt, tb).rotation_difference(rest_dir(self.src, sb)).to_matrix()
                if base == 'Hand':
                    hand_q[side] = q
                self.q[t] = q
        for t in self.map:
            if t not in self.q:
                self.q[t] = hand_q.get(t[-1], Matrix.Identity(3)) if (t.startswith('f_') or t.startswith('thumb')) else Matrix.Identity(3)
        self.order = [b.name for b in td if b.name in self.map]  # parents precede children in bone collection order? sort by depth
        depth = lambda n: len(td[n].parent_recursive)
        self.order.sort(key=depth)
        hz_t = td['UpLeg_L'].head_local.z
        hz_s = (self.src.matrix_world @ sd[self.map['UpLeg_L']].head_local).z
        self.scale = hz_t / hz_s

    def apply(self, frame_action, frame):
        src = self.src
        src.animation_data.action = frame_action
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()
        sw = src.matrix_world.to_3x3()
        td, sd = tgt.data.bones, src.data.bones
        pose_world = {}
        for t in self.order:
            sp = src.pose.bones[self.map[t]]
            Rs_pose = sw @ sp.matrix.to_3x3()
            Rs_rest = rest_rot(src, sd[self.map[t]])
            Rt_rest = rest_rot(tgt, td[t])
            D = Rs_pose @ Rs_rest.inverted()
            pose_world[t] = D @ self.q[t] @ Rt_rest
        for t in self.order:
            tb = td[t]
            pb = tgt.pose.bones[t]
            Rb = rest_rot(tgt, tb)
            if tb.parent:
                Rp = rest_rot(tgt, tb.parent)
                Pp = pose_world.get(tb.parent.name, Rp)
                loc = Rb.inverted() @ Rp @ Pp.inverted() @ pose_world[t]
            else:
                loc = Rb.inverted() @ pose_world[t]
            pb.rotation_quaternion = loc.to_quaternion()
        # hips translation
        hs = self.src.pose.bones[self.map['Hips']]
        d_src = (src.matrix_world @ hs.head) - (src.matrix_world @ sd[self.map['Hips']].head_local)
        d_arm = tgt.matrix_world.to_3x3().inverted() @ (d_src * self.scale)
        pb = tgt.pose.bones['Hips']
        pb.location = Rest_inv(td['Hips']) @ d_arm

def Rest_inv(b):
    return b.matrix_local.to_3x3().inverted()

# ---- scene: studio
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE_NEXT'
scene.render.resolution_x, scene.render.resolution_y = 1280, 720
scene.render.resolution_percentage = int(os.environ.get('RES_PCT','100'))
scene.render.fps = 30
scene.view_settings.view_transform = 'AgX'
scene.view_settings.look = 'AgX - Base Contrast'
scene.eevee.taa_render_samples = int(os.environ.get('SAMPLES','24'))
scene.eevee.use_raytracing = False

world = bpy.data.worlds.new('W'); scene.world = world; world.use_nodes = True
bg = world.node_tree.nodes['Background']
bg.inputs[0].default_value = (0.20, 0.23, 0.27, 1); bg.inputs[1].default_value = 0.9

bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 0, 0.0))
floor = bpy.context.active_object
fm = bpy.data.materials.new('Floor'); fm.use_nodes = True
fb = fm.node_tree.nodes['Principled BSDF']; fb.inputs['Base Color'].default_value = (0.13, 0.15, 0.13, 1); fb.inputs['Roughness'].default_value = 0.9
floor.data.materials.append(fm)

def add_light(kind, loc, energy, rot, size=None, color=(1, 1, 1)):
    l = bpy.data.lights.new(kind, kind)
    l.energy = energy; l.color = color
    if size: l.size = size
    o = bpy.data.objects.new(kind, l); scene.collection.objects.link(o)
    o.location = loc; o.rotation_euler = [math.radians(a) for a in rot]
    return o
add_light('SUN', (0, 0, 20), 3.2, (50, 0, -35), color=(1.0, 0.93, 0.82)).data.angle = math.radians(4)
add_light('AREA', (-18, -20, 14), 9000, (65, 0, -40), size=14, color=(0.75, 0.85, 1.0))
add_light('AREA', (14, 16, 12), 5000, (-110, 0, 150), size=14, color=(1.0, 0.85, 0.7))

cam_d = bpy.data.cameras.new('Cam'); cam_d.lens = 55
cam = bpy.data.objects.new('Cam', cam_d); scene.collection.objects.link(cam); scene.camera = cam
def aim(az_deg, dist=44, height=7.6, target_z=7.3):
    a = math.radians(az_deg)
    cam.location = (math.sin(a) * dist, -math.cos(a) * dist, height)
    d = Vector((0, 0, target_z)) - cam.location
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()

os.makedirs(OUT, exist_ok=True)
rts = {}
def get_rt(key):
    if key not in rts: rts[key] = Retarget(key)
    return rts[key]

for ci, spec in enumerate(CLIPS):
    key, name = spec.split(':')
    rt = get_rt(key)
    act = bpy.data.actions[name]
    f0, f1 = int(act.frame_range[0]), int(act.frame_range[1])
    src_arms[key].animation_data_create()
    is_loop = name.endswith('_Loop') or name.startswith('Idle')
    if MODE == 'test':
        frames = [(f0 + f1) // 2]
    else:
        n = f1 - f0 + 1
        total = n + 15
        frames = [f0 + (i % n if is_loop else min(i, n - 1)) for i in range(total)]
        if is_loop: frames = [f0 + (i % n) for i in range(int(math.ceil(66 / n)) * n)]
    for i, f in enumerate(frames):
        rt.apply(act, f)
        aim(18 + (i * 0.0 if MODE == 'test' else 14 * math.sin(i / max(len(frames), 1) * math.pi)))
        scene.render.filepath = f"{OUT}/{ci + int(os.environ.get('CLIP_BASE','0')):02d}_{name}_{i:04d}.png"
        bpy.ops.render.render(write_still=True)
print("DONE")
