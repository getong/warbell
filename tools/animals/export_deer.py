"""Export one of CDmir's CC0 red deer (OpenGameArt "Old Deer Male" `deer1.blend` / "Deer Female"
`doe.blend`) as a game GLB: skinned body + PBR materials + the clip set `src/animal_skin.rs` plays.

    blender -b <deer1.blend|doe.blend> --python export_deer.py -- <out.glb> <hip_height_m>

The source rig is an old IK rig (foot / hip / spine / head IK handles driving the deform chain) and
ships idle / look-around / eat / run / die clips but NO walk, so a walk is authored here: a four-beat
lateral-sequence walk (left hind, left fore, right hind, right fore a quarter cycle apart, ~65 % duty)
keyed on the foot IK handles, with the hips dipping twice a stride and the head nodding with the fore
feet. The exporter samples every clip with constraints evaluated, which bakes the IK into the plain
bone transforms the game plays. Materials (old Blender-Internal, no nodes) are rebuilt as Principled
from the packed texture images. Scaled so the hip (croup) stands `hip_height_m` metres, feet at y=0.
"""
import bpy, math, os, sys
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:]
OUT, HIP_M = argv[0], float(argv[1])
FPS = 24
WALK_FRAMES = 22          # one full stride, ~0.92 s at 1x
WALK_STRIDE_K = 1.0       # ground per stride, in hip heights (a red deer walks ~1.1-1.3 m a stride)
CLIPS = {                 # game clip name -> source action
    "Run": "Run",
    "Idle": "Idle.000",
    "Idle2": "Idle.001",
    "LookAround": "LookAround.000",
    "Eat": "Eat.001",
    "Die": "Die.000",
}


def log(*a):
    print("[deer]", *a, flush=True)


scene = bpy.context.scene
scene.render.fps = FPS
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
for o in list(bpy.data.objects):
    if o is not arm and o.parent is not arm:
        bpy.data.objects.remove(o, do_unlink=True)
meshes = [o for o in bpy.data.objects if o.type == 'MESH']

# ---------------------------------------------------------------- materials
imgs = {i.filepath.lower(): i for i in bpy.data.images if i.filepath}


def find_img(stem, normal):
    for path, img in imgs.items():
        name = path.replace("\\", "/").split("/")[-1]   # (`//x.png` reads as a UNC root to ntpath)
        if stem in name and (("normal" in name) == normal):
            return img
    return None


for mat in bpy.data.materials:
    key = mat.name.lower()
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    bsdf.inputs["Roughness"].default_value = 0.85
    bsdf.inputs["Specular IOR Level"].default_value = 0.3
    if key == "eye":
        bsdf.inputs["Base Color"].default_value = (0.02, 0.015, 0.012, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.15
        continue
    stem = {"antlers": "antlers"}.get(key, key)  # body / head (deer-body.png, doe-body.png …)
    base = find_img(stem, False)
    nrm = find_img(stem, True)
    log(f"material {mat.name}: base {base and base.name}, normal {nrm and nrm.name}")
    if base:
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = base
        nt.links.new(t.outputs["Color"], bsdf.inputs["Base Color"])
    if nrm:
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = nrm
        t.image.colorspace_settings.name = "Non-Color"
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nm.inputs["Strength"].default_value = 0.8
        nt.links.new(t.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    if key == "antlers":
        bsdf.inputs["Roughness"].default_value = 0.6

# ---------------------------------------------------------------- the walk
pb = arm.pose.bones
WALK_STRIDE = WALK_STRIDE_K * (arm.matrix_world @ arm.data.bones["Hip"].head_local).z
for p in pb:
    p.rotation_mode = 'QUATERNION'
names = {b.name for b in arm.data.bones}
# (IK handle, hoof bone, phase, lift): lateral-sequence walk, LH → LF → RH → RF
FEET = [
    ("IK-Backleg_L", "Backleg_L.002", 0.00, 0.40),
    ("IK-Fronleg_L" if "IK-Fronleg_L" in names else "IK-Frontleg_L", "Frontleg_L.002", 0.25, 0.50),
    ("IK-Backleg_R", "Backleg_R.002", 0.50, 0.40),
    ("IK-Frontleg_R", "Frontleg_R.002", 0.75, 0.50),
]
DUTY = 0.64
FWD = Vector((0.0, -1.0, 0.0))   # the deer faces -Y
UP = Vector((0.0, 0.0, 1.0))


def smooth(x):
    return x * x * (3.0 - 2.0 * x)


def set_offset(name, offset):
    """Key bone `name` at its rest pose shifted by `offset` (armature space)."""
    b = arm.data.bones[name]
    pb[name].matrix = Matrix.Translation(offset) @ b.matrix_local
    pb[name].keyframe_insert("location")


ad = arm.animation_data_create()
ad.action = bpy.data.actions.new("Walk")
for f in range(WALK_FRAMES + 1):
    scene.frame_set(f)
    p = f / WALK_FRAMES
    for p_bone in pb:   # everything else at rest
        p_bone.location = (0, 0, 0)
        p_bone.rotation_quaternion = (1, 0, 0, 0)
    for ik, hoof, ph, lift in FEET:
        q = (p - ph) % 1.0
        if q < DUTY:      # planted: slides back under the body
            along, up, flex = 0.5 - q / DUTY, 0.0, 0.0
        else:             # swing: lifted and carried forward
            s = (q - DUTY) / (1.0 - DUTY)
            along, up, flex = -0.5 + smooth(s), lift * math.sin(math.pi * s), math.sin(math.pi * s)
        set_offset(ik, FWD * (along * WALK_STRIDE) + UP * up)
        pb[hoof].rotation_quaternion = Matrix.Rotation(-0.55 * flex, 4, 'X').to_quaternion()
        pb[hoof].keyframe_insert("rotation_quaternion")
    # hips dip at each hind footfall, the back follows; the head nods forward with each fore stride
    dip = -0.05 * (0.5 + 0.5 * math.cos(4.0 * math.pi * p))
    set_offset("IK-Hip", UP * dip)
    set_offset("IK-Backbone", UP * dip * 0.6)
    nod = 0.5 + 0.5 * math.cos(4.0 * math.pi * (p - 0.3))
    set_offset("IK-Head", FWD * (0.10 * nod) + UP * (-0.06 * nod))
    for k in ("rotation_quaternion",):
        for nme in ("IK-Hip", "IK-Backbone", "IK-Head"):
            pb[nme].keyframe_insert(k)
walk = ad.action
for fc in walk.fcurves:
    for kp in fc.keyframe_points:
        kp.interpolation = 'LINEAR'
log(f"walk authored: {WALK_FRAMES} frames, stride {WALK_STRIDE} rig units")

# ---------------------------------------------------------------- scale + clips
hip_z = (arm.matrix_world @ arm.data.bones["Hip"].head_local).z
s = HIP_M / hip_z
arm.location = arm.location * s
arm.scale = (s, s, s)
arm.name = arm.data.name = "Rig"
log(f"hip {hip_z:.3f} rig units -> {HIP_M} m (x{s:.4f}); walk native {WALK_STRIDE * s * FPS / WALK_FRAMES:.3f} m/s")

ad.action = None
for tr in list(ad.nla_tracks):
    ad.nla_tracks.remove(tr)
todo = dict(CLIPS, Walk="Walk")
for clip, src in todo.items():
    a = bpy.data.actions.get(src)
    if a is None:
        log(f"MISSING action {src}")
        continue
    tr = ad.nla_tracks.new()
    tr.name = clip
    st = tr.strips.new(clip, int(a.frame_range[0]), a)
    if hasattr(st, "action_slot") and len(getattr(a, "slots", [])):
        st.action_slot = a.slots[0]
    tr.mute = True

for x in bpy.context.scene.objects:
    x.select_set(x is arm or x.parent is arm)
bpy.context.view_layer.objects.active = arm
os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
bpy.ops.export_scene.gltf(
    filepath=OUT, export_format='GLB', use_selection=True,
    export_apply=False, export_materials='EXPORT', export_image_format='AUTO',
    export_skins=True, export_def_bones=False, export_rest_position_armature=True,
    export_animations=True, export_animation_mode='NLA_TRACKS', export_force_sampling=True,
    export_optimize_animation_size=True, export_anim_slide_to_zero=True, export_reset_pose_bones=True,
    export_frame_range=False, export_yup=True, export_cameras=False, export_lights=False,
)
log(f"DONE {OUT}: clips {sorted(todo)}")
