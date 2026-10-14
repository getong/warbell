"""Retarget Mixamo FBX clips onto the MPFB 'game_engine' rig and swap them into a copy of the anims blend.

blender -b npc_anims.blend --python bake_mixamo.py -- <fbx_dir> <out.blend>

Every `<fbx_dir>/<Clip>.fbx` (Mixamo export: FBX, without skin, 30 fps, in place) becomes action
`NPC_<Clip>`, replacing the UAL clip of that name (or adding a new one). Same world-space swing
retarget as `bake_anims.py`: each limb's rest direction is aligned, then the source bone's world
rotation delta is applied to the target's rest; the hips carry the (in-place) pelvis translation.

Mixamo's licence lets the clips ship inside the game but NOT be redistributed as files, so neither
the FBXs nor the blend / GLBs baked from them are committed: they live outside the repo
(`downloads/mixamo/`) and in the gitignored `assets/npc_private/` (see `src/npc_skin.rs`).
"""
import bpy, sys, os, glob
from mathutils import Matrix

argv = sys.argv[sys.argv.index('--') + 1:]
SRC_DIR, OUT = argv[0], argv[1]

tgt = bpy.data.objects['REF_RIG']
for pb in tgt.pose.bones:
    pb.rotation_mode = 'QUATERNION'
bpy.context.view_layer.update()


def mixamo_map(prefix):
    m = {'pelvis': 'Hips', 'spine_01': 'Spine', 'spine_02': 'Spine1', 'spine_03': 'Spine2', 'neck_01': 'Neck', 'head': 'Head'}
    for s, S in (('l', 'Left'), ('r', 'Right')):
        m.update({f'clavicle_{s}': f'{S}Shoulder', f'upperarm_{s}': f'{S}Arm', f'lowerarm_{s}': f'{S}ForeArm',
                  f'hand_{s}': f'{S}Hand', f'thigh_{s}': f'{S}UpLeg', f'calf_{s}': f'{S}Leg',
                  f'foot_{s}': f'{S}Foot', f'ball_{s}': f'{S}ToeBase'})
        for f, F in (('index', 'Index'), ('middle', 'Middle'), ('ring', 'Ring'), ('pinky', 'Pinky'), ('thumb', 'Thumb')):
            for i in (1, 2, 3):
                m[f'{f}_0{i}_{s}'] = f'{S}Hand{F}{i}'
    return {t: prefix + s for t, s in m.items()}


SWING = {'clavicle', 'upperarm', 'lowerarm', 'hand', 'thigh', 'calf', 'foot', 'ball'}
FINGERS = ('index', 'middle', 'pinky', 'ring', 'thumb')


def rest_rot(arm, bone):
    return arm.matrix_world.to_3x3() @ bone.matrix_local.to_3x3()


def rest_dir(arm, bone):
    return (arm.matrix_world.to_3x3() @ (bone.tail_local - bone.head_local)).normalized()


def retarget(path):
    clip = os.path.splitext(os.path.basename(path))[0]
    before, before_a = set(bpy.data.objects), set(bpy.data.actions)
    bpy.ops.import_scene.fbx(filepath=path, automatic_bone_orientation=False, ignore_leaf_bones=True)
    new = set(bpy.data.objects) - before
    acts = list(set(bpy.data.actions) - before_a)
    src = next(o for o in new if o.type == 'ARMATURE')
    act = acts[0]
    sd, td = src.data.bones, tgt.data.bones
    prefix = next((b.name.split('Hips')[0] for b in sd if b.name.endswith('Hips')), 'mixamorig:')
    mp = {t: s for t, s in mixamo_map(prefix).items() if t in td and s in sd}
    q = {}
    hand_q = {}
    for t in mp:
        base = t.rsplit('_', 1)[0]
        if base in SWING:
            q[t] = rest_dir(tgt, td[t]).rotation_difference(rest_dir(src, sd[mp[t]])).to_matrix()
            if base == 'hand':
                hand_q[t[-1]] = q[t]
    for t in mp:
        if t not in q:
            q[t] = hand_q.get(t[-1], Matrix.Identity(3)) if t.startswith(FINGERS) else Matrix.Identity(3)
    order = sorted(mp, key=lambda n: len(td[n].parent_recursive))
    scale = td['thigh_l'].head_local.z / (src.matrix_world @ sd[mp['thigh_l']].head_local).z

    src.animation_data_create().action = act
    if hasattr(src.animation_data, 'action_slot') and len(act.slots):
        src.animation_data.action_slot = act.slots[0]
    f0, f1 = int(act.frame_range[0]), int(act.frame_range[1])
    frames = list(range(f0, f1 + 1))
    data = {t: [] for t in order}
    hips = []
    sw = src.matrix_world.to_3x3()
    for f in frames:
        bpy.context.scene.frame_set(f)
        pw = {}
        for t in order:
            sp = src.pose.bones[mp[t]]
            D = (sw @ sp.matrix.to_3x3()) @ rest_rot(src, sd[mp[t]]).inverted()
            pw[t] = D @ q[t] @ rest_rot(tgt, td[t])
        for t in order:
            tb = td[t]
            Rb = rest_rot(tgt, tb)
            if tb.parent:
                Rp = rest_rot(tgt, tb.parent)
                loc = Rb.inverted() @ Rp @ pw.get(tb.parent.name, Rp).inverted() @ pw[t]
            else:
                loc = Rb.inverted() @ pw[t]
            data[t].append(loc.to_quaternion())
        hs = src.pose.bones[mp['pelvis']]
        d = (src.matrix_world @ hs.head) - (src.matrix_world @ sd[mp['pelvis']].head_local)
        d_arm = tgt.matrix_world.to_3x3().inverted() @ (d * scale)
        hips.append(td['pelvis'].matrix_local.to_3x3().inverted() @ d_arm)
    for qs in data.values():
        for i in range(1, len(qs)):
            if qs[i].dot(qs[i - 1]) < 0:
                qs[i] = -qs[i]

    name = 'NPC_' + clip
    if name in bpy.data.actions:
        bpy.data.actions.remove(bpy.data.actions[name])
    out = bpy.data.actions.new(name)
    out.use_fake_user = True

    def curve(path, idx, group, vals):
        fc = out.fcurves.new(path, index=idx, action_group=group)
        fc.keyframe_points.add(len(vals))
        co = []
        for fr, v in zip(frames, vals):
            co += [fr - f0 + 1, v]
        fc.keyframe_points.foreach_set('co', co)
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
        fc.update()

    for t, qs in data.items():
        for i in range(4):
            curve(f'pose.bones["{t}"].rotation_quaternion', i, t, [v[i] for v in qs])
    for i in range(3):
        curve('pose.bones["pelvis"].location', i, 'pelvis', [h[i] for h in hips])
    out['frames'] = len(frames)
    out['src'] = 'mixamo'
    # drop the import
    for o in new:
        bpy.data.objects.remove(o)
    for a in acts:
        bpy.data.actions.remove(a)
    print(f"P mixamo {clip}: {len(frames)} frames, {len(mp)} bones")


for p in sorted(glob.glob(os.path.join(SRC_DIR, '*.fbx'))):
    retarget(p)
for arm in [o for o in bpy.data.armatures if o.users == 0]:
    bpy.data.armatures.remove(arm)
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("P done")
