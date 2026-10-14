"""Export Andrey's "Brown Bear (animated)" (Sketchfab, CC-BY 4.0) as the game bear GLB: skinned body +
PBR materials + the clip set `src/animal_skin.rs` plays.

    blender -b --python export_bear.py -- <brown_bear_animated.glb> <out.glb> <withers_m> <tris> [brown|polar]

The download is a Cinema 4D joint rig (Cyrillic joint names, mangled; addressed here by their unique
numeric suffix) with one in-place walk. Imported with the TEMPERANCE bone heuristic so every bone
points at its child, then each leg gets an IK control at the ankle / wrist (two-bone IK + the paw
copying the control's rotation, so a planted paw stays flat). The source walk keeps the IK off; the
authored Idle / Run / Attack drive the controls the way `export_wolf.py` drives the wolf. The coat is
warmed from near-black to a brown-bear brown, the body decimated to ~`tris` triangles, the whole
scaled so the withers stand `withers_m`. `polar` re-dyes the coat a creamy white instead (the polar
bear), keeping the source's light-and-shade so the nose, lips and claws stay dark.
"""
import bpy, math, sys
import numpy as np
from mathutils import Matrix, Quaternion, Vector

argv = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT, WITHERS_M, TRIS = argv[0], argv[1], float(argv[2]), int(argv[3])
COAT = argv[4] if len(argv) > 4 else "brown"
FPS = 24


def log(*a):
    print("[bear]", *a, flush=True)


bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC, bone_heuristic='TEMPERANCE')
scene = bpy.context.scene
scene.render.fps = FPS
arm = next(o for o in scene.objects if o.type == 'ARMATURE')
top = arm
while top.parent:
    top = top.parent
walk = arm.animation_data.action
walk.name = "Amble"   # the source clip: a slow ~0.4 m/s amble
bones = arm.data.bones


def by_suffix(sfx):
    hits = [b.name for b in bones if b.name.endswith(sfx)]
    assert len(hits) == 1, (sfx, hits)
    return hits[0]


MW = arm.matrix_world.copy()
TO_ARM = MW.to_3x3().inverted()
FWD_W, UP_W, SIDE = Vector((0, -1, 0)), Vector((0, 0, 1)), Vector((1, 0, 0))   # faces -Y
meshes = [o for o in scene.objects if o.type == 'MESH']
bpy.context.view_layer.update()
GROUND = min((o.matrix_world @ Vector(c)).z for o in meshes for c in o.bound_box)
BODY, SPINE_MID, NECK, HEAD = by_suffix("_01"), by_suffix("_018"), by_suffix("_040"), by_suffix("_055")
WITHERS = (MW @ bones[by_suffix("_020")].head_local).z - GROUND
log(f"ground {GROUND:.3f}, withers {WITHERS:.3f} scene units")

# (IK bone whose tail is the ankle / wrist, chain, ankle / wrist bone) per leg
LEGS = [(by_suffix(a), 2, by_suffix(b)) for a, b in (("_08", "_09"), ("_013", "_014"), ("_030", "_031"), ("_036", "_037"))]


# ---------------------------------------------------------------- measure the source walk
def world_head(name):
    return arm.matrix_world @ arm.pose.bones[name].head


lo, hi = [int(v) for v in walk.frame_range]
paw = LEGS[0][2]
track = []
for f in range(lo, hi + 1):
    scene.frame_set(f)
    track.append(world_head(paw))
zs = [p.z for p in track]
zmin = min(zs)
planted = [i for i in range(len(track) - 1) if track[i].z < zmin + 0.02 * WITHERS and track[i + 1].z < zmin + 0.02 * WITHERS]
vs = [-(track[i + 1].y - track[i].y) * FPS * -1 for i in planted]   # planted paw slides +Y (backward)
walk_v = float(np.median(vs)) if vs else 0.0
log(f"walk: frames {lo}-{hi}, planted samples {len(planted)}, native {walk_v:.3f} scene u/s")

# ---------------------------------------------------------------- coat + decimate
for img in bpy.data.images:
    if img.size[0] == 0:
        continue
    n = img.name.lower()
    log(f"image {img.name} {tuple(img.size)} cs {img.colorspace_settings.name}")
for mat in bpy.data.materials:
    if not mat.use_nodes:
        continue
    bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if not bsdf or not bsdf.inputs["Base Color"].is_linked:
        continue
    src = bsdf.inputs["Base Color"].links[0].from_node
    if src.type != 'TEX_IMAGE' or src.image is None or src.image.get("warmed"):
        continue
    img = src.image
    px = np.empty(img.size[0] * img.size[1] * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(-1, 4)
    mean = px[:, :3].mean(axis=0)
    # warm, lift the near-black coat to a brown bear's brown (linear-ish gain on sRGB values)
    if COAT == "polar":
        # cream white with the source's relative light and shade (dark nose / lips / claws stay dark)
        lum = px[:, :3] @ np.array([0.3, 0.59, 0.11], dtype=np.float32)
        detail = np.sqrt(np.clip(lum / max(float(lum.mean()), 1e-4), 0, 2.5))
        px[:, :3] = np.clip(np.outer(detail * 0.78, np.array([0.95, 0.92, 0.84], dtype=np.float32)), 0, 1)
    else:
        px[:, :3] = np.clip(px[:, :3] * np.array([1.45, 1.22, 1.0], dtype=np.float32) + np.array([0.012, 0.006, 0.0], dtype=np.float32), 0, 1)
    img.pixels.foreach_set(px.ravel())
    img["warmed"] = True
    img.update()
    img.pack()
    log(f"warmed {img.name} (mean {mean.round(3)} -> {px[:, :3].mean(axis=0).round(3)})")

for img in bpy.data.images:   # 4K maps are wasted on a critter: 2K
    if img.size[0] > 2048:
        img.scale(2048, 2048)
        img.pack()
        log(f"downscaled {img.name}")
for o in meshes:
    tri = sum(len(p.vertices) - 2 for p in o.data.polygons)
    if tri < 4000:
        continue
    ratio = min(1.0, TRIS / max(1, sum(sum(len(p.vertices) - 2 for p in m.data.polygons) for m in meshes)))
    m = o.modifiers.new("dec", 'DECIMATE')
    m.ratio = ratio
    bpy.context.view_layer.objects.active = o
    while o.modifiers[0].name != "dec":
        bpy.ops.object.modifier_move_up(modifier="dec")
    bpy.ops.object.modifier_apply(modifier="dec")
    log(f"decimated {o.name}: {tri} -> {sum(len(p.vertices) - 2 for p in o.data.polygons)} tris")

# ---------------------------------------------------------------- IK controls
bpy.context.view_layer.objects.active = arm
for o in scene.objects:
    o.select_set(o is arm)
bpy.ops.object.mode_set(mode='EDIT')
eb = arm.data.edit_bones
root_name = bones[0].name if bones[0].parent is None else next(b.name for b in bones if b.parent is None)
CTL = []
for ik, n, ankle in LEGS:
    c = eb.new("ctl_" + ankle[-4:])
    c.head, c.tail, c.roll = eb[ankle].head.copy(), eb[ankle].tail.copy(), eb[ankle].roll
    c.parent = eb[root_name]
    c.use_deform = False
    CTL.append(c.name)
bpy.ops.object.mode_set(mode='POSE')
pb = arm.pose.bones
for (ik, n, ankle), ctl in zip(LEGS, CTL):
    k = pb[ik].constraints.new('IK')
    k.name = "IK"
    k.target, k.subtarget, k.chain_count = arm, ctl, n
    r = pb[ankle].constraints.new('COPY_ROTATION')
    r.name = "PAW"
    r.target, r.subtarget = arm, ctl
for p in pb:
    p.rotation_mode = 'QUATERNION'


def key_influence(v):
    for (ik, n, ankle) in LEGS:
        for b, c in ((ik, "IK"), (ankle, "PAW")):
            con = pb[b].constraints[c]
            con.influence = v
            con.keyframe_insert("influence")


ad = arm.animation_data
ad.action = walk
scene.frame_set(lo)
key_influence(0.0)
for fr in (lo, hi):   # the walk keeps the IK off for its whole length
    for (ik, n, ankle) in LEGS:
        for b, c in ((ik, "IK"), (ankle, "PAW")):
            pb[b].constraints[c].influence = 0.0
            pb[b].constraints[c].keyframe_insert("influence", frame=fr)


def smooth(x):
    return x * x * (3.0 - 2.0 * x)


def rest_all():
    for p in pb:
        p.location = (0, 0, 0)
        p.rotation_quaternion = (1, 0, 0, 0)


def key_offset(name, off_world, rot=None):
    b = bones[name]
    m = Matrix.Translation(TO_ARM @ off_world) @ b.matrix_local
    if rot is not None:
        m = Matrix.Translation(m.to_translation()) @ rot.to_matrix().to_4x4() @ Matrix.Translation(-m.to_translation()) @ m
    pb[name].matrix = m
    pb[name].keyframe_insert("location")
    pb[name].keyframe_insert("rotation_quaternion")


def key_turn(name, axis_world, ang):
    b = bones[name]
    ax = (b.matrix_local.to_3x3().inverted() @ (TO_ARM @ axis_world)).normalized()
    pb[name].rotation_quaternion = Quaternion(ax, ang)
    pb[name].keyframe_insert("rotation_quaternion")


def new_action(name):
    ad.action = bpy.data.actions.new(name)
    scene.frame_set(0)
    key_influence(1.0)
    return ad.action


def linear(act):
    for fc in act.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'


FRONT = [False, False, True, True]
SIDEX = [(MW @ bones[a].head_local).x for _, _, a in LEGS]
acts = {"Amble": walk}

# Idle: weight on all fours, slow breathing, the head swinging low to sniff and coming up to look
act = new_action("Idle")
N = 120
for f in range(N + 1):
    scene.frame_set(f)
    p = f / N
    rest_all()
    for ctl in CTL:
        key_offset(ctl, Vector())
    breathe = 0.008 * WITHERS * math.sin(2 * math.pi * 3 * p)
    key_offset(BODY, UP_W * breathe)
    key_turn(NECK, UP_W, 0.22 * math.sin(2 * math.pi * p))
    key_turn(HEAD, SIDE, 0.12 * math.sin(2 * math.pi * 2 * p + 0.6) + 0.05)
acts["Idle"] = act

# Walk: a lateral four-beat walk (hind, fore, hind, fore a quarter apart), the head bobbing with the fores
act = new_action("Walk")
N, STRIDE_K, DUTY = 26, 1.1, 0.65
PH = {(False, True): 0.0, (True, True): 0.25, (False, False): 0.5, (True, False): 0.75}
stride = STRIDE_K * WITHERS
for f in range(N + 1):
    scene.frame_set(f)
    p = f / N
    rest_all()
    for (ik, n, ankle), ctl, front, x in zip(LEGS, CTL, FRONT, SIDEX):
        q = (p - PH[(front, x > 0)]) % 1.0
        if q < DUTY:
            along, up = DUTY * (0.5 - q / DUTY), 0.0
        else:
            s = (q - DUTY) / (1.0 - DUTY)
            along, up = DUTY * (-0.5 + smooth(s)), 0.10 * WITHERS * math.sin(math.pi * s)
        key_offset(ctl, FWD_W * along * stride + UP_W * up)
    key_offset(BODY, UP_W * (-0.015 * WITHERS * (0.5 + 0.5 * math.cos(4 * math.pi * p))) + SIDE * 0.015 * WITHERS * math.sin(2 * math.pi * p))
    key_turn(SPINE_MID, UP_W, 0.04 * math.sin(2 * math.pi * p))
    key_turn(NECK, SIDE, 0.06 * math.cos(4 * math.pi * (p - 0.3)))
linear(act)
acts["Walk"] = act
walk2_v = stride * FPS / N

# Run: a bear's transverse gallop — hinds a beat apart, then the fores; the back flexes with it
act = new_action("Run")
N, STRIDE_K, DUTY = 14, 2.0, 0.36
PH = {(False, True): 0.0, (False, False): 0.12, (True, True): 0.48, (True, False): 0.60}
stride = STRIDE_K * WITHERS
for f in range(N + 1):
    scene.frame_set(f)
    p = f / N
    rest_all()
    for (ik, n, ankle), ctl, front, x in zip(LEGS, CTL, FRONT, SIDEX):
        q = (p - PH[(front, x > 0)]) % 1.0
        if q < DUTY:
            along, up = DUTY * (0.5 - q / DUTY), 0.0
        else:
            s = (q - DUTY) / (1.0 - DUTY)
            along, up = DUTY * (-0.5 + smooth(s)), 0.16 * WITHERS * math.sin(math.pi * s)
        key_offset(ctl, FWD_W * along * stride + UP_W * up)
    key_offset(BODY, UP_W * (-0.05 * WITHERS * (0.5 + 0.5 * math.cos(2 * math.pi * (p - 0.3)))))
    key_turn(SPINE_MID, SIDE, 0.10 * math.sin(2 * math.pi * p))
    key_turn(NECK, SIDE, 0.08 * math.cos(2 * math.pi * (p - 0.2)))
linear(act)
acts["Run"] = act
run_v = stride * FPS / N

# Attack: rear back onto the haunches, lunge and swat with the right fore, bite, settle
act = new_action("Attack")
N = 20
for f in range(N + 1):
    scene.frame_set(f)
    p = f / N
    rest_all()
    if p < 0.35:
        u = smooth(p / 0.35)
        lunge, rear, swat = -0.12 * u, 0.22 * u, 0.0
    elif p < 0.6:
        u = smooth((p - 0.35) / 0.25)
        lunge, rear, swat = -0.12 + 0.42 * u, 0.22 * (1 - u), math.sin(math.pi * u)
    else:
        u = smooth((p - 0.6) / 0.4)
        lunge, rear, swat = 0.30 * (1 - u), 0.0, 0.0
    for (ik, n, ankle), ctl, front, x in zip(LEGS, CTL, FRONT, SIDEX):
        if front:
            lift = rear * 1.0 + (0.25 * swat if x < 0 else 0.05 * swat)
            key_offset(ctl, FWD_W * (max(lunge, 0.0) * 0.9 + (0.18 * swat if x < 0 else 0.0)) * WITHERS + UP_W * lift * WITHERS)
        else:
            key_offset(ctl, Vector())
    key_offset(BODY, FWD_W * lunge * WITHERS + UP_W * rear * 0.6 * WITHERS)
    key_turn(SPINE_MID, SIDE, -0.5 * rear)
    key_turn(NECK, SIDE, 0.35 * swat - 0.2 * rear)
linear(act)
acts["Attack"] = act

# ---------------------------------------------------------------- scale + export
s = WITHERS_M / WITHERS
top.scale = top.scale * s
top.location.z -= GROUND * s   # the soles at y = 0 (the source origin sits mid-body)
log(f"scale x{s:.5f}; amble {walk_v * s:.3f} m/s, walk {walk2_v * s:.3f} m/s, run {run_v * s:.3f} m/s")
ad.action = None
for tr in list(ad.nla_tracks):
    ad.nla_tracks.remove(tr)
for clip, a in acts.items():
    tr = ad.nla_tracks.new()
    tr.name = clip
    st = tr.strips.new(clip, int(a.frame_range[0]), a)
    if hasattr(st, "action_slot") and len(getattr(a, "slots", [])):
        st.action_slot = a.slots[0]
    tr.mute = True
bpy.ops.object.mode_set(mode='OBJECT')
for x in scene.objects:
    x.select_set(True)
bpy.ops.export_scene.gltf(
    filepath=OUT, export_format='GLB', use_selection=True,
    export_apply=False, export_materials='EXPORT', export_image_format='AUTO',
    export_skins=True, export_def_bones=False, export_rest_position_armature=True,
    export_animations=True, export_animation_mode='NLA_TRACKS', export_force_sampling=True,
    export_optimize_animation_size=True, export_anim_slide_to_zero=True, export_reset_pose_bones=True,
    export_frame_range=False, export_yup=True, export_cameras=False, export_lights=False,
)
log(f"DONE {OUT}: clips {sorted(acts)}")
