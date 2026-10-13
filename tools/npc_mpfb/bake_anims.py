"""Bake every Quaternius UAL clip (UAL1 + UAL2, CC0) onto the MPFB 'game_engine' rig as Blender Actions.

blender -b --factory-startup --python bake_anims.py -- OUT.blend [clip clip ...]
All cast characters share the same rig, so the actions are reusable on any of them.
"""
import bpy, sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mathutils import Matrix, Vector
from mpfb_cast import build

argv = sys.argv[sys.argv.index('--') + 1:]
OUT = argv[0]; ONLY = set(argv[1:])
D = "C:/Users/skibi/Documents/Codex/downloads/"
SRC = {
    'ual1': D + "ual1/x/Animation Library[Standard]/Godot/AnimationLibrary_Godot_Standard.glb",
    'ual2': D + "ual2/x/Universal Animation Library 2 [Standard]/Unreal-Godot/UAL2_Standard.glb",
}

# ---- reference human on the game_engine rig (neutral adult body, no clothes needed)
hm, tgt, _ = build(dict(gender=0.5, age=0.5, muscle=0.5, weight=0.5, height=0.5, skin='young_caucasian_male', name='ref'))
tgt.name = 'REF_RIG'
for pb in tgt.pose.bones: pb.rotation_mode = 'QUATERNION'
bpy.context.view_layer.update()

FING = ['index', 'middle', 'pinky', 'ring']
def map_ual1():
    m = {'pelvis': 'DEF-hips', 'spine_01': 'DEF-spine.001', 'spine_02': 'DEF-spine.002', 'spine_03': 'DEF-spine.003',
         'neck_01': 'DEF-neck', 'head': 'DEF-head'}
    for s in ('l', 'r'):
        S = s.upper()
        m.update({f'clavicle_{s}': f'DEF-shoulder.{S}', f'upperarm_{s}': f'DEF-upper_arm.{S}', f'lowerarm_{s}': f'DEF-forearm.{S}',
                  f'hand_{s}': f'DEF-hand.{S}', f'thigh_{s}': f'DEF-thigh.{S}', f'calf_{s}': f'DEF-shin.{S}',
                  f'foot_{s}': f'DEF-foot.{S}', f'ball_{s}': f'DEF-toe.{S}'})
        for f in FING:
            for i in (1, 2, 3): m[f'{f}_0{i}_{s}'] = f'DEF-f_{f}.0{i}.{S}'
        for i in (1, 2, 3): m[f'thumb_0{i}_{s}'] = f'DEF-thumb.0{i}.{S}'
    return m

def map_ual2():
    m = {b.name: b.name for b in tgt.data.bones}
    m['head'] = 'Head'
    return m

MAPS = {'ual1': map_ual1(), 'ual2': map_ual2()}
SWING = {'clavicle', 'upperarm', 'lowerarm', 'hand', 'thigh', 'calf', 'foot', 'ball'}

def rest_rot(arm, bone): return arm.matrix_world.to_3x3() @ bone.matrix_local.to_3x3()
def rest_dir(arm, bone): return (arm.matrix_world.to_3x3() @ (bone.tail_local - bone.head_local)).normalized()

class RT:
    def __init__(self, key):
        self.key = key
        before = set(bpy.data.objects); before_a = set(bpy.data.actions)
        bpy.ops.import_scene.gltf(filepath=SRC[key])
        new = set(bpy.data.objects) - before
        self.actions = set(bpy.data.actions) - before_a
        self.src = next(o for o in new if o.type == 'ARMATURE')
        for o in new:
            if o.type == 'MESH': bpy.data.objects.remove(o)
        self.src.animation_data_create()
        for tr in list(self.src.animation_data.nla_tracks): self.src.animation_data.nla_tracks.remove(tr)
        sd, td = self.src.data.bones, tgt.data.bones
        mp = {t: s for t, s in MAPS[key].items() if t in td and s in sd}
        self.map = mp
        hand_q = {}; self.q = {}
        for t in mp:
            base = t.rsplit('_', 1)[0]
            if base in SWING:
                q = rest_dir(tgt, td[t]).rotation_difference(rest_dir(self.src, sd[mp[t]])).to_matrix()
                self.q[t] = q
                if base == 'hand': hand_q[t[-1]] = q
        for t in mp:
            if t not in self.q:
                self.q[t] = hand_q.get(t[-1], Matrix.Identity(3)) if any(t.startswith(p) for p in ('index', 'middle', 'pinky', 'ring', 'thumb')) else Matrix.Identity(3)
        self.order = sorted(mp, key=lambda n: len(td[n].parent_recursive))
        self.scale = td['thigh_l'].head_local.z / (self.src.matrix_world @ sd[mp['thigh_l']].head_local).z

    def frame(self, f):
        """-> ({bone: quat}, hips_loc) for source frame f"""
        bpy.context.scene.frame_set(f)
        sw = self.src.matrix_world.to_3x3(); sd, td = self.src.data.bones, tgt.data.bones
        pw = {}
        for t in self.order:
            sp = self.src.pose.bones[self.map[t]]
            D = (sw @ sp.matrix.to_3x3()) @ rest_rot(self.src, sd[self.map[t]]).inverted()
            pw[t] = D @ self.q[t] @ rest_rot(tgt, td[t])
        out = {}
        for t in self.order:
            tb = td[t]; Rb = rest_rot(tgt, tb)
            if tb.parent:
                Rp = rest_rot(tgt, tb.parent); Pp = pw.get(tb.parent.name, Rp)
                loc = Rb.inverted() @ Rp @ Pp.inverted() @ pw[t]
            else:
                loc = Rb.inverted() @ pw[t]
            out[t] = loc.to_quaternion()
        hs = self.src.pose.bones[self.map['pelvis']]
        d = (self.src.matrix_world @ hs.head) - (self.src.matrix_world @ sd[self.map['pelvis']].head_local)
        d_arm = tgt.matrix_world.to_3x3().inverted() @ (d * self.scale)
        return out, td['pelvis'].matrix_local.to_3x3().inverted() @ d_arm

rts = {k: RT(k) for k in SRC}

def bake(rt, act):
    f0, f1 = int(act.frame_range[0]), int(act.frame_range[1])
    rt.src.animation_data.action = act
    name = 'NPC_' + act.name
    new = bpy.data.actions.new(name); new.use_fake_user = True
    frames = list(range(f0, f1 + 1))
    data = {t: [] for t in rt.order}; hips = []
    for f in frames:
        q, loc = rt.frame(f)
        for t, v in q.items(): data[t].append(v)
        hips.append(loc)
    for t, qs in data.items():
        for i in range(1, len(qs)):
            if qs[i].dot(qs[i - 1]) < 0: qs[i] = -qs[i]
    def curve(path, idx, group, vals):
        fc = new.fcurves.new(path, index=idx, action_group=group)
        fc.keyframe_points.add(len(vals))
        co = []
        for fr, v in zip(frames, vals): co += [fr - f0 + 1, v]
        fc.keyframe_points.foreach_set('co', co)
        for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
        fc.update()
    for t, qs in data.items():
        for i in range(4):
            curve(f'pose.bones["{t}"].rotation_quaternion', i, t, [q[i] for q in qs])
    for i in range(3):
        curve('pose.bones["pelvis"].location', i, 'pelvis', [h[i] for h in hips])
    new['frames'] = len(frames); new['src'] = rt.key
    return new

n = 0
for key, rt in rts.items():
    for act in sorted(rt.actions, key=lambda a: a.name):
        if act.name.startswith('A_TPose') or (ONLY and act.name not in ONLY): continue
        bake(rt, act); n += 1
        print("P baked", key, act.name)
# strip everything but the reference rig + actions
for o in list(bpy.data.objects):
    if o.name not in ('REF_RIG',) and o.type == 'ARMATURE' and o.name != 'REF_RIG': bpy.data.objects.remove(o)
for a in list(bpy.data.actions):
    if not a.name.startswith('NPC_'): bpy.data.actions.remove(a)
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("P done", n)
