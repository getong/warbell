"""Export kenchoo's "Grey Wolf Rebuilt" (Sketchfab, CC-BY 4.0) as the game wolf GLB: skinned body + its
PBR material + the clip set `src/animal_skin.rs` plays.

    blender -b --python export_wolf.py -- <grey_wolf_rebuilt.glb> <out.glb> <withers_m>

The download ships one 11 s idle and a rig whose leg IK did not survive the glTF trip (the foot bones
are free children of the root). The IK is rebuilt here — each lower leg aims its tail at a helper bone
riding the foot, so the rest pose is solved exactly — and the gaits are authored on the feet like the
deer's walk (`export_deer.py`): a lateral four-beat Walk, a diagonal Trot, a rotary-gallop Run, a
bite lunge (Attack) and the source idle (Idle). The exporter samples every clip with the constraints
evaluated, which bakes the IK into plain bone transforms. Scaled so the withers stand `withers_m`.
"""
import bpy, math, sys
from mathutils import Matrix, Quaternion, Vector

argv = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT, WITHERS_M = argv[0], argv[1], float(argv[2])
FPS = 24


def log(*a):
    print("[wolf]", *a, flush=True)


bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
scene = bpy.context.scene
scene.render.fps = FPS
arm = next(o for o in scene.objects if o.type == 'ARMATURE')
for o in list(scene.objects):   # a stray helper sphere rides along in the download
    if o.type == 'MESH' and o.parent is not arm:
        bpy.data.objects.remove(o, do_unlink=True)
top = arm
while top.parent:
    top = top.parent
idle = arm.animation_data.action
idle.name = "Idle"

MW = arm.matrix_world.copy()
TO_ARM = MW.to_3x3().inverted()        # world direction / offset -> armature space
FWD_W, UP_W = Vector((0, -1, 0)), Vector((0, 0, 1))   # the wolf faces -Y
FWD, UP = TO_ARM @ FWD_W, TO_ARM @ UP_W
bones = arm.data.bones
WITHERS = (MW @ bones["Torso3_14"].head_local).z
log(f"withers {WITHERS:.3f} scene units")

# ---------------------------------------------------------------- IK rebuild
LEGS = {   # foot (IK) bone -> (lower leg, chain length)
    "IKFrontLeg.L_48": ("FrontLowerLeg.L_15", 2),
    "IKFrontLeg.R_52": ("FrontLowerLeg.R_18", 2),
    "IKBackLeg.L_46": ("BackLowerLeg.L_23", 3),
    "IKBackLeg.R_50": ("BackLowerLeg.R_27", 3),
}
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')
eb = arm.data.edit_bones
for foot, (lower, _) in LEGS.items():
    t = eb.new("tgt_" + foot)
    t.head = eb[lower].tail
    t.tail = eb[lower].tail + Vector((0, 0, 0.05)) / MW.to_scale().x
    t.parent = eb[foot]
    t.use_deform = False
bpy.ops.object.mode_set(mode='POSE')
pb = arm.pose.bones
for foot, (lower, n) in LEGS.items():
    c = pb[lower].constraints.new('IK')
    c.target, c.subtarget, c.chain_count = arm, "tgt_" + foot, n
for p in pb:
    p.rotation_mode = 'QUATERNION'


def smooth(x):
    return x * x * (3.0 - 2.0 * x)


def rest_all():
    for p in pb:
        p.location = (0, 0, 0)
        p.rotation_quaternion = (1, 0, 0, 0)


def key_offset(name, off_world):
    """Key bone `name` (a child of the root) at rest shifted by a WORLD offset."""
    b = bones[name]
    pb[name].matrix = Matrix.Translation(TO_ARM @ off_world) @ b.matrix_local
    pb[name].keyframe_insert("location")
    pb[name].keyframe_insert("rotation_quaternion")


def key_turn(name, axis_world, ang):
    """Key bone `name` rotated `ang` about a WORLD axis (through its head), in its own frame."""
    b = bones[name]
    ax = (b.matrix_local.to_3x3().inverted() @ (TO_ARM @ axis_world)).normalized()
    pb[name].rotation_quaternion = Quaternion(ax, ang)
    pb[name].keyframe_insert("rotation_quaternion")


SIDE = Vector((1, 0, 0))   # world +X: pitch axis (nose down = +ang about +X for a -Y facing body)
FEET = ["IKBackLeg.L_46", "IKFrontLeg.L_48", "IKBackLeg.R_50", "IKFrontLeg.R_52"]


def gait(name, frames, stride_k, phases, duty, lift_k, bob_k, pitch, nod, stretch=0.0):
    """Author a looping gait on the four feet. `phases` = (LH, LF, RH, RF) footfall phase."""
    stride = stride_k * WITHERS
    ad = arm.animation_data
    ad.action = bpy.data.actions.new(name)
    for f in range(frames + 1):
        scene.frame_set(f)
        p = f / frames
        rest_all()
        for foot, ph in zip(FEET, phases):
            q = (p - ph) % 1.0
            front = "Front" in foot
            # A planted foot slides back under the body at the body's own speed, so it covers only
            # `duty` of the stride (the rest of the stride the body travels while it is in the air).
            if q < duty:   # planted
                along, up = duty * (0.5 - q / duty), 0.0
            else:          # swing: lifted and carried forward
                s = (q - duty) / (1.0 - duty)
                along, up = duty * (-0.5 + smooth(s)), lift_k * WITHERS * math.sin(math.pi * s) * (1.0 if front else 0.85)
            # a galloping back gathers (feet together) and stretches (fore reach out)
            reach = stretch * WITHERS * math.cos(2 * math.pi * (p - ph)) * (1 if front else -1)
            key_offset(foot, FWD_W * (along * stride + reach) + UP_W * up)
        k = 2.0 if stretch == 0.0 else 1.0   # walk / trot bob twice a stride, the gallop once
        bob = -bob_k * WITHERS * (0.5 + 0.5 * math.cos(2 * math.pi * k * p))
        key_offset("Body_44", UP_W * bob)
        key_turn("Back_39", SIDE, pitch * math.sin(2 * math.pi * p))
        key_turn("Neck2_12", SIDE, nod * math.cos(2 * math.pi * k * (p - 0.2)))
        key_turn("Tail2_37", SIDE, 0.06 * math.sin(2 * math.pi * k * p))
    act = ad.action
    for fc in act.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
    speed = stride * FPS / frames
    log(f"{name}: {frames} frames, native {speed:.3f} scene u/s")
    return act, speed


acts = {"Idle": idle}
acts["Walk"], walk_v = gait("Walk", 18, 1.4, (0.0, 0.25, 0.5, 0.75), 0.62, 0.10, 0.025, 0.0, 0.05)
acts["Trot"], trot_v = gait("Trot", 12, 2.2, (0.0, 0.5, 0.5, 0.0), 0.45, 0.14, 0.03, 0.0, 0.03)
acts["Run"], run_v = gait("Run", 10, 3.0, (0.0, 0.42, 0.1, 0.52), 0.32, 0.20, 0.06, 0.07, 0.06, stretch=0.07)

# bite lunge: gather back, spring the chest forward + head down-and-in, snap, recover (feet planted)
ad = arm.animation_data
ad.action = bpy.data.actions.new("Attack")
N = 14
for f in range(N + 1):
    scene.frame_set(f)
    p = f / N
    rest_all()
    if p < 0.3:
        u = smooth(p / 0.3)
        lunge, head, hop = -0.10 * u, -0.25 * u, 0.0          # coil back, head up
    elif p < 0.55:
        u = smooth((p - 0.3) / 0.25)
        lunge, head, hop = -0.10 + 0.45 * u, -0.25 + 0.80 * u, math.sin(math.pi * u)   # spring + bite
    else:
        u = smooth((p - 0.55) / 0.45)
        lunge, head, hop = 0.35 * (1 - u), 0.55 * (1 - u), 0.0
    for foot in FEET:
        if "Front" in foot:   # the fore feet hop forward with the spring
            key_offset(foot, FWD_W * max(lunge, 0.0) * 0.9 * WITHERS + UP_W * 0.18 * hop * WITHERS)
        else:
            key_offset(foot, Vector())
    key_offset("Body_44", FWD_W * lunge * WITHERS + UP_W * (0.06 * hop - 0.04 * abs(lunge)) * WITHERS)
    key_turn("Neck2_12", SIDE, head * 0.9)
    key_turn("Head_2", SIDE, -head * 0.35)
for fc in ad.action.fcurves:
    for kp in fc.keyframe_points:
        kp.interpolation = 'LINEAR'
acts["Attack"] = ad.action

# ---------------------------------------------------------------- scale + clips
s = WITHERS_M / WITHERS
top.scale = top.scale * s
k = s * FPS  # (logged speeds in metres)
log(f"scale x{s:.4f}; walk {walk_v * s:.3f} m/s, trot {trot_v * s:.3f} m/s, run {run_v * s:.3f} m/s")
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
