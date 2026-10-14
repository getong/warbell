"""Export a downloaded rigged quadruped (goat / dog / camel) as a game animal GLB: skinned body + PBR
materials + the clip set `src/animal_skin.rs` plays.

    blender -b --python export_quad.py -- <src.glb> <out.glb> <goat|dog|camel>

One exporter for the three CC-BY Sketchfab downloads (credits in `assets/CREDITS.md`); everything
model-specific lives in its `PROFILES` entry. The pipeline is `export_bear.py`'s, generalised:

* **Re-rest** (dog, camel): their glTF rest pose is junk (the dog's 3ds Max Biped lies on its side,
  the camel's root sits 158 units up) and only the clips stand them up. Every source clip is baked to
  armature-space bone matrices, the meshes are frozen in a standing frame (the frame whose feet sit
  most squarely under the hips / shoulders), that pose is applied as the new rest, and the baked
  clips are re-keyed against it.
* **Face -Y**, ground the soles at 0, scale the standing height to `height_m`.
* **Leg IK**: per leg a control bone copying the ankle (two/three-bone IK onto a helper riding the
  control at the IK bone's tail, so the rest pose is solved exactly, plus the ankle copying the
  control's rotation). Kept source clips run with the IK off; authored clips key it on.
* **Authored clips** on the controls like `export_wolf.py`: gaits (planted foot slides back over
  duty × stride — see `gait`), a head-down `Graze`, an `Idle` where the source has none.
* Decimate past `tris`, downscale textures to `tex`, drop unwanted meshes (the camel's blanket).
"""
import bpy, math, sys
import numpy as np
from mathutils import Matrix, Quaternion, Vector

argv = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT, NAME = argv[0], argv[1], argv[2]
FPS = 24

# gait phase tables keyed (front, left): when in the cycle each foot lifts off
LATERAL_WALK = {(False, True): 0.0, (True, True): 0.25, (False, False): 0.5, (True, False): 0.75}
TROT = {(False, True): 0.0, (True, False): 0.0, (False, False): 0.5, (True, True): 0.5}
PACE = {(False, True): 0.0, (True, True): 0.0, (False, False): 0.5, (True, False): 0.5}
GALLOP = {(False, True): 0.0, (False, False): 0.12, (True, True): 0.48, (True, False): 0.60}

PROFILES = {
    # GerardoA400's goat (Auto-Rig Pro export): rest pose is fine; its one clip is an idle.
    "goat": dict(
        height_m=1.02, tris=22000, tex=1024, drop=[], rerest=None,
        keep={"rigAction": "Idle"},
        body="root.x_30", spine="spine_02.x_4", neck=["c_subneck_1.x_2", "neck.x_1"], head="head.x_0",
        withers="c_subneck_1.x_2", tail=[],
        legs=[("leg_stretch_dupli_002.l_10", 2, "foot_dupli_002.l_8"), ("leg_stretch_dupli_002.r_28", 2, "foot_dupli_002.r_26"),
              ("leg_stretch_dupli_001.l_16", 2, "foot_dupli_001.l_14"), ("leg_stretch_dupli_001.r_22", 2, "foot_dupli_001.r_20")],
        gaits=[dict(name="Walk", n=20, stride=1.3, ph=LATERAL_WALK, duty=0.62, lift=0.10, bob=0.02, bumps=2, nod=0.05),
               dict(name="Run", n=10, stride=2.8, ph=GALLOP, duty=0.32, lift=0.20, bob=0.05, bumps=1, nod=0.08, flex=0.08)],
        graze=0.95, idle=False,
    ),
    # MAXDESIGN-3D's dog (3ds Max Biped): one 8 s walk, junk rest.
    "dog": dict(
        height_m=0.62, tris=14000, tex=1024, drop=[], rerest="Take 001",
        keep={"Take 001": "Stroll"},
        body="Bip001-Pelvis_00", spine="Bip001-Spine1_02", neck=["Bip001-Neck_04"], head="Bip001-Head_05",
        withers="Bip001-Spine2_03", tail=["Bip001-Tail_034", "Bip001-Tail1_035", "Bip001-Tail2_036"],
        legs=[("Bip001-L-Forearm_012", 2, "Bip001-L-Hand_013"), ("Bip001-R-Forearm_018", 2, "Bip001-R-Hand_019"),
              ("Bip001-L-HorseLink_026", 3, "Bip001-L-Foot_027"), ("Bip001-R-HorseLink_031", 3, "Bip001-R-Foot_032")],
        gaits=[dict(name="Walk", n=18, stride=1.4, ph=LATERAL_WALK, duty=0.62, lift=0.10, bob=0.025, bumps=2, nod=0.05),
               dict(name="Trot", n=12, stride=2.2, ph=TROT, duty=0.45, lift=0.14, bob=0.03, bumps=2, nod=0.03),
               dict(name="Run", n=10, stride=3.0, ph=GALLOP, duty=0.32, lift=0.20, bob=0.06, bumps=1, nod=0.06, flex=0.07)],
        graze=0.7, idle=True,
    ),
    # E.A.Cornell's camel: idles + a walk cycle, junk rest, a saddle blanket we don't want.
    "camel": dict(
        height_m=2.15, tris=30000, tex=2048, drop=["Camel_Coat"], rerest="Armature|Idle_01",
        keep={"Armature|Idle_01": "Idle", "Armature|Idle_02": "Idle2", "Armature|WalkCycle": "Walk"},
        body="Back.001_02", spine="Back.002_03",
        neck=["Neck.001_00", "Neck.002_013", "Neck.003_014", "Neck.004_015", "Neck.005_016", "Neck.006_017"], head="Head_018",
        withers="Back.002_03", tail=["Tail.001_067", "Tail.002_068"],
        legs=[("FrontLeg.002_L_06", 2, "FrontFoot_R_07"), ("FrontLeg.002_R_011", 2, "FrontFoot_L_012"),
              ("BackLeg.002_L_061", 2, "BackFoot_L_062"), ("BackLeg.002_R_065", 2, "BackFoot_R_066")],
        gaits=[dict(name="Run", n=16, stride=1.6, ph=PACE, duty=0.40, lift=0.10, bob=0.025, bumps=2, nod=0.05, roll=0.04)],
        graze=1.1, idle=False,
    ),
}
P = PROFILES[NAME]


def log(*a):
    print(f"[{NAME}]", *a, flush=True)


bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC, bone_heuristic='TEMPERANCE')
scene = bpy.context.scene
scene.render.fps = FPS
arm = next(o for o in scene.objects if o.type == 'ARMATURE')
for o in list(scene.objects):   # stray helpers / the camel blanket
    if o.type == 'MESH' and (o.parent is not arm or any(m and m.name in P["drop"] for m in o.data.materials)):
        log(f"dropped mesh {o.name}")
        bpy.data.objects.remove(o, do_unlink=True)
top = arm
while top.parent:
    top = top.parent
bones = arm.data.bones
pb = arm.pose.bones
ad = arm.animation_data
meshes = [o for o in scene.objects if o.type == 'MESH']
src_actions = [a for a in bpy.data.actions if a.name in P["keep"]]
LEGS = P["legs"]
for n in [P["body"], P["spine"], P["head"], P["withers"], *P["neck"], *P["tail"], *[x for l in LEGS for x in (l[0], l[2])]]:
    assert n in bones, n


def frames_of(a):
    lo, hi = a.frame_range
    return int(math.floor(lo)), int(math.ceil(hi))


def select_only(o):
    for x in scene.objects:
        x.select_set(x is o)
    bpy.context.view_layer.objects.active = o


# ---------------------------------------------------------------- re-rest
baked = {}
for a in src_actions:
    ad.action = a
    lo, hi = frames_of(a)
    fr = []
    for f in range(lo, hi + 1):
        scene.frame_set(f)
        fr.append({p.name: p.matrix.copy() for p in pb})
    baked[a.name] = fr
    log(f"baked {a.name}: {len(fr)} frames")

if P["rerest"]:
    frs = baked[P["rerest"]]
    # the standing frame: feet squarest under their hips / shoulders and all four down
    def top_of(ik, n):
        b = bones[ik]
        for _ in range(n - 1):
            b = b.parent
        return b.name
    tops = [top_of(ik, n) for ik, n, _ in LEGS]
    W = arm.matrix_world.copy()   # world is Z-up even where the armature space is not
    zmin = [min((W @ m[ank].translation).z for m in frs) for _, _, ank in LEGS]
    def score(m):
        off = [W.to_3x3() @ (m[ank].translation - m[t].translation) for (_, _, ank), t in zip(LEGS, tops)]
        lift = sum((W @ m[ank].translation).z - z for (_, _, ank), z in zip(LEGS, zmin))
        # fore-aft spread of the feet relative to their hips / shoulders (the long axis is whichever
        # of world x / y the legs spread along, so take the larger spread)
        sx = [o.x for o in off]
        sy = [o.y for o in off]
        return max(max(sx) - min(sx), max(sy) - min(sy)) + 3.0 * lift
    best = min(range(len(frs)), key=lambda i: score(frs[i]))
    log(f"re-rest at {P['rerest']} frame {best} (score {score(frs[best]):.3f}, worst {max(score(m) for m in frs):.3f})")
    ad.action = bpy.data.actions[P["rerest"]]
    scene.frame_set(frames_of(ad.action)[0] + best)
    for o in meshes:   # freeze the meshes in that pose, then re-bind
        select_only(o)
        mod = next(m for m in o.modifiers if m.type == 'ARMATURE')
        while o.modifiers[0].name != mod.name:
            bpy.ops.object.modifier_move_up(modifier=mod.name)
        bpy.ops.object.modifier_apply(modifier=mod.name)
        m = o.modifiers.new("Armature", 'ARMATURE')
        m.object = arm
    select_only(arm)
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.armature_apply(selected=False)
    bpy.ops.object.mode_set(mode='OBJECT')

# re-key every kept clip from its baked armature-space matrices against the (possibly new) rest
ad.action = None
for p in pb:
    p.rotation_mode = 'QUATERNION'
    p.location, p.rotation_quaternion, p.scale = (0, 0, 0), (1, 0, 0, 0), (1, 1, 1)
acts = {}
for a in src_actions:
    clip = P["keep"][a.name]
    na = bpy.data.actions.new(clip + "_src")
    ad.action = na
    for i, mats in enumerate(baked[a.name]):
        for p in pb:
            b = p.bone
            if b.parent is None:
                basis = b.matrix_local.inverted() @ mats[p.name]
            else:
                rel = b.parent.matrix_local.inverted() @ b.matrix_local
                basis = rel.inverted() @ mats[b.parent.name].inverted() @ mats[p.name]
            loc, rot, scl = basis.decompose()
            p.location, p.rotation_quaternion, p.scale = loc, rot, scl
            p.keyframe_insert("location", frame=i)
            p.keyframe_insert("rotation_quaternion", frame=i)
            p.keyframe_insert("scale", frame=i)
    acts[clip] = na
for a in src_actions:
    bpy.data.actions.remove(a)
for clip, a in acts.items():
    a.name = clip
ad.action = None
for p in pb:
    p.location, p.rotation_quaternion, p.scale = (0, 0, 0), (1, 0, 0, 0), (1, 1, 1)
bpy.context.view_layer.update()

# ---------------------------------------------------------------- face -Y
def world_rest(name):
    return arm.matrix_world @ bones[name].head_local

fwd = world_rest(P["head"]) - world_rest(P["body"])
yaw = math.atan2(fwd.x, -fwd.y)   # angle from -Y to the head direction (about +Z)
if abs(yaw) > 0.05:
    top.matrix_world = Matrix.Rotation(-yaw, 4, 'Z') @ top.matrix_world
    bpy.context.view_layer.update()
    log(f"turned {math.degrees(-yaw):.1f} deg to face -Y")

MW = arm.matrix_world.copy()
TO_ARM = MW.to_3x3().inverted()
FWD_W, UP_W, SIDE = Vector((0, -1, 0)), Vector((0, 0, 1)), Vector((1, 0, 0))


def mesh_bounds():
    dg = bpy.context.evaluated_depsgraph_get()
    lo, hi = Vector((1e9,) * 3), Vector((-1e9,) * 3)
    for o in meshes:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        for v in me.vertices:
            p = o.matrix_world @ v.co
            lo, hi = Vector(map(min, lo, p)), Vector(map(max, hi, p))
        ev.to_mesh_clear()
    return lo, hi


lo_b, hi_b = mesh_bounds()
GROUND, HEIGHT = lo_b.z, hi_b.z - lo_b.z
WITHERS = (MW @ bones[P["withers"]].head_local).z - GROUND
log(f"ground {GROUND:.3f}, height {HEIGHT:.3f}, withers {WITHERS:.3f} scene units; length {hi_b.y - lo_b.y:.3f}")

# ---------------------------------------------------------------- decimate + textures
total = sum(sum(len(p.vertices) - 2 for p in m.data.polygons) for m in meshes)
if total > P["tris"]:
    big = [o for o in meshes if sum(len(p.vertices) - 2 for p in o.data.polygons) > 8000]
    big_t = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in big)
    ratio = max(0.1, (P["tris"] - (total - big_t)) / big_t)
    for o in big:
        t0 = sum(len(p.vertices) - 2 for p in o.data.polygons)
        select_only(o)
        m = o.modifiers.new("dec", 'DECIMATE')
        m.ratio = ratio
        while o.modifiers[0].name != "dec":
            bpy.ops.object.modifier_move_up(modifier="dec")
        bpy.ops.object.modifier_apply(modifier="dec")
        log(f"decimated {o.name}: {t0} -> {sum(len(p.vertices) - 2 for p in o.data.polygons)} tris")
for img in bpy.data.images:
    if img.size[0] > P["tex"] or img.size[1] > P["tex"]:
        k = P["tex"] / max(img.size)
        img.scale(max(1, int(img.size[0] * k)), max(1, int(img.size[1] * k)))
        img.pack()
        log(f"downscaled {img.name} -> {tuple(img.size)}")

# ---------------------------------------------------------------- IK controls
select_only(arm)
bpy.ops.object.mode_set(mode='EDIT')
eb = arm.data.edit_bones
root_name = next(b.name for b in bones if b.parent is None)
CTL, TGT = [], []
for ik, n, ankle in LEGS:
    c = eb.new("ctl_" + ankle)
    c.head, c.tail, c.roll = eb[ankle].head.copy(), eb[ankle].tail.copy(), eb[ankle].roll
    c.parent = eb[root_name]
    c.use_deform = False
    t = eb.new("tgt_" + ankle)
    t.head = eb[ik].tail.copy()
    t.tail = t.head + (eb[ik].tail - eb[ik].head).normalized() * 0.05 * (eb[ik].tail - eb[ik].head).length
    t.parent = c
    t.use_deform = False
    CTL.append(c.name)
    TGT.append(t.name)
bpy.ops.object.mode_set(mode='POSE')
for (ik, n, ankle), ctl, tgt in zip(LEGS, CTL, TGT):
    k = pb[ik].constraints.new('IK')
    k.name = "IK"
    k.target, k.subtarget, k.chain_count = arm, tgt, n
    r = pb[ankle].constraints.new('COPY_ROTATION')
    r.name = "PAW"
    r.target, r.subtarget = arm, ctl
for p in pb:
    p.rotation_mode = 'QUATERNION'


def key_influence(v, frame):
    for (ik, n, ankle) in LEGS:
        for b, c in ((ik, "IK"), (ankle, "PAW")):
            con = pb[b].constraints[c]
            con.influence = v
            con.keyframe_insert("influence", frame=frame)


for clip, a in acts.items():   # the kept source clips keep the IK off
    ad.action = a
    lo, hi = frames_of(a)
    key_influence(0.0, lo)
    key_influence(0.0, hi)


def smooth(x):
    return x * x * (3.0 - 2.0 * x)


def rest_all():
    for p in pb:
        p.location = (0, 0, 0)
        p.rotation_quaternion = (1, 0, 0, 0)
        p.scale = (1, 1, 1)
    bpy.context.view_layer.update()   # pose.matrix setters below read the parents' evaluated pose


def key_offset(name, off_world):
    pb[name].matrix = Matrix.Translation(TO_ARM @ off_world) @ bones[name].matrix_local
    pb[name].keyframe_insert("location")
    pb[name].keyframe_insert("rotation_quaternion")


def key_turn(name, axis_world, ang):
    b = bones[name]
    ax = (b.matrix_local.to_3x3().inverted() @ (TO_ARM @ axis_world)).normalized()
    pb[name].rotation_quaternion = Quaternion(ax, ang)
    pb[name].keyframe_insert("rotation_quaternion")


def key_neck(ang_down, ang_side=0.0):
    nk = P["neck"]
    for n in nk:
        b = bones[n]
        q = Quaternion((b.matrix_local.to_3x3().inverted() @ (TO_ARM @ SIDE)).normalized(), ang_down / len(nk))
        q = Quaternion((b.matrix_local.to_3x3().inverted() @ (TO_ARM @ UP_W)).normalized(), ang_side / len(nk)) @ q
        pb[n].rotation_quaternion = q
        pb[n].keyframe_insert("rotation_quaternion")


def key_tail(ang):
    for i, n in enumerate(P["tail"]):
        key_turn(n, UP_W, ang * (0.6 + 0.4 * i))


def new_action(name):
    ad.action = bpy.data.actions.new(name)
    key_influence(1.0, 0)
    return ad.action


def linear(act):
    for fc in act.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'


centre_y = sum((MW @ bones[a].head_local).y for _, _, a in LEGS) / 4
FRONT = [(MW @ bones[a].head_local).y < centre_y for _, _, a in LEGS]
LEFT = [(MW @ bones[a].head_local).x > 0 for _, _, a in LEGS]   # facing -Y, the animal's left is +X
assert sorted(zip(FRONT, LEFT)) == sorted([(True, True), (True, False), (False, True), (False, False)]), (FRONT, LEFT)


def gait(g):
    """Planted foot: slides back over duty × stride at body speed; swing: lifts and returns."""
    act = new_action(g["name"])
    N, stride, duty = g["n"], g["stride"] * WITHERS, g["duty"]
    for f in range(N + 1):
        scene.frame_set(f)
        p = f / N
        rest_all()
        for ctl, front, left in zip(CTL, FRONT, LEFT):
            q = (p - g["ph"][(front, left)]) % 1.0
            if q < duty:
                along, up = duty * (0.5 - q / duty), 0.0
            else:
                s = (q - duty) / (1.0 - duty)
                along, up = duty * (-0.5 + smooth(s)), g["lift"] * WITHERS * math.sin(math.pi * s)
            key_offset(ctl, FWD_W * along * stride + UP_W * up)
        bump = 0.5 + 0.5 * math.cos(2 * math.pi * g["bumps"] * p)
        sway = SIDE * g.get("roll", 0.012) * WITHERS * math.sin(2 * math.pi * p)
        key_offset(P["body"], UP_W * (-g["bob"] * WITHERS * bump) + sway)
        key_turn(P["spine"], SIDE, g.get("flex", 0.0) * math.sin(2 * math.pi * p))
        key_neck(g["nod"] * math.cos(2 * math.pi * g["bumps"] * (p - 0.3)))
        if P["tail"]:
            key_tail(0.25 * math.sin(2 * math.pi * p))
    linear(act)
    acts[g["name"]] = act
    return stride * FPS / N


speeds = {}
for g in P["gaits"]:
    speeds[g["name"]] = gait(g)

# Graze: the head goes down to the ground and stays, chewing; a slow look-up halfway
act = new_action("Graze")
N = 96
for f in range(0, N + 1, 4):
    scene.frame_set(f)
    p = f / N
    rest_all()
    for ctl in CTL:
        key_offset(ctl, Vector())
    look = smooth(max(0.0, 1.0 - abs(p - 0.55) / 0.12)) if 0.43 < p < 0.67 else 0.0
    down = P["graze"] * (1.0 - 0.55 * look)
    key_offset(P["body"], UP_W * (-0.01 * WITHERS) + FWD_W * 0.02 * WITHERS)
    key_neck(down, 0.10 * math.sin(2 * math.pi * p))
    key_turn(P["head"], SIDE, 0.25 * P["graze"] * (1 - look) + 0.05 * math.sin(2 * math.pi * 8 * p))
    if P["tail"]:
        key_tail(0.15 * math.sin(2 * math.pi * 3 * p))
acts["Graze"] = act

if P["idle"]:
    # Idle: weight shifting, breathing, the head looking about, the tail swinging
    act = new_action("Idle")
    N = 120
    for f in range(0, N + 1, 3):
        scene.frame_set(f)
        p = f / N
        rest_all()
        for ctl in CTL:
            key_offset(ctl, Vector())
        key_offset(P["body"], UP_W * 0.008 * WITHERS * math.sin(2 * math.pi * 4 * p) + SIDE * 0.01 * WITHERS * math.sin(2 * math.pi * p))
        key_neck(-0.08 + 0.10 * math.sin(2 * math.pi * 2 * p + 0.6), 0.45 * math.sin(2 * math.pi * p))
        key_turn(P["head"], UP_W, 0.15 * math.sin(2 * math.pi * p + 0.4))
        if P["tail"]:
            key_tail(0.3 * math.sin(2 * math.pi * 3 * p))
    acts["Idle"] = act

# ---------------------------------------------------------------- measure kept clips (walk speed, root drift)
for clip, a in acts.items():
    if clip not in P["keep"].values():
        continue
    ad.action = a
    lo, hi = frames_of(a)
    paws = {ank: [] for _, _, ank in LEGS}
    body = []
    for f in range(lo, hi + 1):
        scene.frame_set(f)
        for ank in paws:
            paws[ank].append(arm.matrix_world @ pb[ank].head)
        body.append(arm.matrix_world @ pb[P["body"]].head)
    vs = []
    for tr in paws.values():
        zmin = min(p.z for p in tr)
        vs += [(tr[i + 1].y - tr[i].y) * FPS for i in range(len(tr) - 1)
               if tr[i].z < zmin + 0.02 * WITHERS and tr[i + 1].z < zmin + 0.02 * WITHERS]
    v = float(np.median(vs)) if vs else 0.0
    speeds[clip] = v
    log(f"source {clip}: frames {lo}-{hi}, planted samples {len(vs)}, paw slide {v:.3f} u/s, body drift {(body[-1] - body[0]).length:.3f}")

# ---------------------------------------------------------------- scale + export
s = P["height_m"] / HEIGHT
top.scale = top.scale * s
top.location = top.location * s
top.location.z -= GROUND * s
bpy.context.view_layer.update()
log(f"scale x{s:.5f}, withers {WITHERS * s:.3f} m; speeds m/s: " + ", ".join(f"{k} {v * s:.3f}" for k, v in speeds.items()))
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
