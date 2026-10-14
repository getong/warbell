"""Export an ANIMATION-ONLY GLB of one townsfolk look: the look's own rig + the clips of an anims blend.

    blender -b npc_cast.blend --python export_anims.py -- <npc> <out.glb> <anims.blend>

Used for the Mixamo clips (`bake_mixamo.py`), which may ship inside the game but not as files in a public
repo: the output goes to the gitignored `assets/npc_private/npc_<npc>_anims.glb`, and `src/npc_skin.rs`
plays its clips in place of the committed look GLB's clips of the same name. Only actions tagged
`src = "mixamo"` are exported. The rig is renamed "Rig" and exported from the look's own armature (same
bone rests / offsets, pelvis travel scaled to its height exactly like `export_game.py::load_clips`), so the
clips' AnimationTargetIds (node-name paths under "Rig") match the look GLB's skeleton one-to-one.
"""
import bpy, os, sys

argv = sys.argv[sys.argv.index("--") + 1:]
NPC, OUT, ANIMS = argv[0], argv[1], argv[2]
REF_PELVIS_Z = 0.8851

arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE' and o.get("npc") == NPC)
for o in list(bpy.data.objects):
    if o is not arm:
        bpy.data.objects.remove(o, do_unlink=True)
arm.location = (0.0, 0.0, 0.0)
arm.rotation_euler = (0.0, 0.0, 0.0)
arm.name = arm.data.name = "Rig"
bpy.context.scene.render.fps = 30

for a in list(bpy.data.actions):
    bpy.data.actions.remove(a)
with bpy.data.libraries.load(ANIMS, link=False) as (src, dst):
    dst.actions = [a for a in src.actions if a.startswith("NPC_")]
k = arm.data.bones["pelvis"].head_local.z / REF_PELVIS_Z
for pb in arm.pose.bones:
    pb.rotation_mode = 'QUATERNION'
ad = arm.animation_data_create()
ad.action = None
for tr in list(ad.nla_tracks):
    ad.nla_tracks.remove(tr)
got = []
for a in list(bpy.data.actions):
    if a.get("src") != "mixamo":
        bpy.data.actions.remove(a)
        continue
    for fc in a.fcurves:
        if fc.data_path == 'pose.bones["pelvis"].location':
            for kp in fc.keyframe_points:
                kp.co.y *= k
                kp.handle_left.y *= k
                kp.handle_right.y *= k
    tr = ad.nla_tracks.new()
    tr.name = a.name[4:]
    st = tr.strips.new(tr.name, int(a.frame_range[0]), a)
    if hasattr(st, "action_slot") and len(a.slots):
        st.action_slot = a.slots[0]
    tr.mute = True
    got.append(tr.name)

for x in bpy.context.scene.objects:
    x.select_set(False)
arm.select_set(True)
bpy.context.view_layer.objects.active = arm
os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(
    filepath=OUT, export_format='GLB', use_selection=True,
    export_apply=False, export_materials='NONE', export_skins=True, export_def_bones=False,
    export_rest_position_armature=True, export_morph=False, export_animations=True,
    export_animation_mode='NLA_TRACKS', export_force_sampling=True, export_optimize_animation_size=True,
    export_anim_slide_to_zero=True, export_reset_pose_bones=True, export_frame_range=False, export_yup=True,
    export_cameras=False, export_lights=False,
)
print(f"P anims {NPC}: {len(got)} clips, pelvis scale {k:.3f} -> {OUT}")
