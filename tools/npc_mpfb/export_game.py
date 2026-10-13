"""Bake + export ONE townsfolk character from npc_cast.blend into a game-ready skinned GLB.

    blender -b npc_cast.blend --python export_game.py -- <npc> <out_dir> [anims.blend]

Writes into <out_dir>:
  npc_<npc>.glb          mesh (body / cloth / hair / brow / lash / beard primitives) + 53-bone skin
                         + the game's clip set baked onto THIS character's rig (pelvis travel scaled
                         to its height), no images (the game builds the materials itself)
  npc_<npc>_albedo.png   body + eyes + garments atlas (TEXCOORD_0), sRGB
  npc_<npc>_normal.png   tangent-space normals of the atlas (OpenGL +Y)
  npc_<npc>_orm.png      R = baked AO, G = roughness, B = metallic (0)
  npc_<npc>_<kind>.png   hair / brow / lash / beard cards (RGBA, alpha = coverage) on their own UVs
  npc_<npc>.json         height, pelvis rest, material list

Everything the game needs is decided here so the runtime stays a plain glTF skin:
  - MASK modifiers (MakeHuman helper geometry + skin hidden under garments) are APPLIED, so the body
    can't poke through clothes; SUBSURF is dropped; body / garments are decimated to a game budget.
  - All parts are joined into one skinned mesh, weights limited to 4 and normalised.
  - Body / eyes / garments get a fresh packed atlas UV; card parts keep their own UVs and textures.
"""
import bpy, bmesh, os, sys, json, math
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
NPC = argv[0]
OUT = argv[1]
ANIMS = argv[2] if len(argv) > 2 else os.path.join(os.path.dirname(bpy.data.filepath), "npc_anims.blend")
os.makedirs(OUT, exist_ok=True)

ATLAS = int(os.environ.get("NPC_ATLAS", "2048"))
CARD_RES = {"hair": 1024, "beard": 512, "brow": 256, "lash": 256}
BUDGET = {"body": 9000, "cloth": 2600, "boots": 1400}   # triangle targets per part
REF_PELVIS_Z = 0.8851                                   # REF_RIG pelvis head height (npc_anims.blend)

# Clips the game drives (see src/npc_skin.rs). Names are the UAL clip names without the NPC_ prefix.
CLIPS = [
    "Idle_Loop", "Walk_Loop", "Walk_Formal_Loop", "Jog_Fwd_Loop", "Sprint_Loop", "Walk_Carry_Loop",
    "Push_Loop", "Crouch_Idle_Loop", "Farm_PlantSeed", "Farm_Harvest", "Farm_Watering",
    "TreeChopping_Loop", "Fixing_Kneeling", "Interact", "PickUp_Table", "Chest_Open",
    "Sitting_Enter", "Sitting_Idle_Loop", "Sitting_Talking_Loop", "Sitting_Exit",
    "Idle_Talking_Loop", "Idle_FoldArms_Loop", "Idle_Rail_Call", "Idle_Rail_Loop", "Idle_No_Loop",
    "Yes", "Dance_Loop", "Idle_Lantern_Loop", "Idle_Torch_Loop", "Consume", "LayToIdle",
    "Sword_Idle", "Sword_Attack", "Sword_Regular_A", "Sword_Regular_B", "Sword_Regular_C",
    "Sword_Block", "Idle_Shield_Loop", "Punch_Jab", "Punch_Cross", "OverhandThrow",
    "Spell_Simple_Idle_Loop", "Spell_Simple_Shoot", "Hit_Chest", "Hit_Head", "Hit_Knockback",
    "Death01", "Roll",
]
# Extra hand-authored clips living in the anims blend (tools/npc_mpfb/author_clips.py), if present.
EXTRA_PREFIX = "NPC_X_"


def log(*a):
    print("[export_game]", *a, flush=True)


# ---------------------------------------------------------------- external image paths
def fix_paths():
    appdata = os.environ.get("APPDATA", "")
    mpfb = os.path.join(appdata, "Blender Foundation", "Blender", "4.5", "extensions", ".user", "user_default", "mpfb", "data")
    codex = os.path.abspath(os.path.join(os.path.dirname(bpy.data.filepath), ".."))
    missing = 0
    for im in bpy.data.images:
        if im.source != 'FILE':
            continue
        p = im.filepath.replace("/", "\\")
        low = p.lower()
        new = None
        if "mpfb\\data\\" in low:
            new = os.path.join(mpfb, p[low.index("mpfb\\data\\") + len("mpfb\\data\\"):])
        elif "polyhaven_src\\" in low:
            new = os.path.join(codex, p[low.index("polyhaven_src\\"):])
        if new:
            if not os.path.exists(new):
                new = new.replace("\\.user\\", "\\")
            im.filepath = new
        path = bpy.path.abspath(im.filepath)
        if not os.path.exists(path):
            missing += 1
            log("MISSING image", im.name, path)
        else:
            im.reload()
    log("images fixed, missing:", missing)


# ---------------------------------------------------------------- scene isolation
def isolate():
    arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE' and o.get("npc") == NPC)
    keep = {arm} | {c for c in bpy.data.objects if c.parent == arm}
    for o in list(bpy.data.objects):
        if o not in keep:
            bpy.data.objects.remove(o, do_unlink=True)
    arm.location = (0.0, 0.0, 0.0)
    arm.rotation_euler = (0.0, 0.0, 0.0)
    return arm


def activate(o):
    for x in bpy.context.scene.objects:
        x.select_set(False)
    bpy.context.view_layer.objects.active = o
    o.select_set(True)


def apply_first(o, mod):
    activate(o)
    with bpy.context.temp_override(object=o, active_object=o):
        bpy.ops.object.modifier_move_to_index(modifier=mod.name, index=0)
        bpy.ops.object.modifier_apply(modifier=mod.name)


def tris(o):
    return sum(len(p.vertices) - 2 for p in o.data.polygons)


# ---------------------------------------------------------------- part classification
def image_paths(mat):
    out = []
    if mat and mat.use_nodes:
        stack = [mat.node_tree]
        while stack:
            nt = stack.pop()
            for n in nt.nodes:
                if n.type == 'TEX_IMAGE' and n.image:
                    out.append(n.image.filepath.lower().replace("/", "\\"))
                elif n.type == 'GROUP' and n.node_tree:
                    stack.append(n.node_tree)
    return out


def kind_of(o):
    n = o.name.lower()
    imgs = " ".join(p for m in o.data.materials for p in image_paths(m))
    if o.name == NPC or "body" in " ".join(m.name.lower() for m in o.data.materials if m):
        return "body"
    if "eyebrow" in n:
        return "brow"
    if "eyelash" in n:
        return "lash"
    if "beard" in n or "beard" in imgs:
        return "beard"
    if "high-poly" in n or "\\eyes\\" in imgs:
        return "eyes"
    if "\\hair\\" in imgs:
        return "hair"
    if "boot" in n or "shoe" in n:
        return "boots"
    return "cloth"


# ---------------------------------------------------------------- geometry prep
def prep_parts(arm):
    parts = [c for c in bpy.data.objects if c.parent == arm and c.type == 'MESH']
    kinds = {}
    for o in parts:
        k = kind_of(o)
        kinds[o.name] = k
        activate(o)
        if o.data.shape_keys:
            with bpy.context.temp_override(object=o, active_object=o):
                bpy.ops.object.shape_key_remove(all=True, apply_mix=True)
        for m in list(o.modifiers):
            if m.type == 'SUBSURF':
                o.modifiers.remove(m)
        for m in [m for m in o.modifiers if m.type == 'MASK']:
            apply_first(o, m)
        if k == "body":
            # genitals / nipples are always under clothes; drop them outright
            me = o.data
            bad = {i for i, m in enumerate(me.materials) if m and any(s in m.name.lower() for s in ("genital", "nipple"))}
            if bad:
                bm = bmesh.new(); bm.from_mesh(me)
                bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index in bad], context='FACES')
                bm.to_mesh(me); bm.free()
        budget = BUDGET.get(k)
        t = tris(o)
        if budget and t > budget * 1.1:
            d = o.modifiers.new("dec", 'DECIMATE')
            d.ratio = budget / t
            d.use_collapse_triangulate = True
            apply_first(o, d)
        log(f"part {o.name:40s} {k:6s} tris {t} -> {tris(o)}")
    return parts, kinds


def join(arm, parts, kinds):
    body = next(o for o in parts if kinds[o.name] == "body")
    # remember each material's kind before the join merges slots
    mat_kind = {}
    for o in parts:
        for m in o.data.materials:
            if m:
                mat_kind[m.name] = "cloth" if kinds[o.name] == "boots" else kinds[o.name]
    for x in bpy.context.scene.objects:
        x.select_set(False)
    for o in parts:
        o.select_set(True)
    bpy.context.view_layer.objects.active = body
    with bpy.context.temp_override(active_object=body, selected_editable_objects=parts, selected_objects=parts):
        bpy.ops.object.join()
    body.name = "Body"
    bones = {b.name for b in arm.data.bones}
    for vg in list(body.vertex_groups):
        if vg.name not in bones:
            body.vertex_groups.remove(vg)
    activate(body)
    with bpy.context.temp_override(object=body, active_object=body):
        bpy.ops.object.vertex_group_limit_total(group_select_mode='ALL', limit=4)
        bpy.ops.object.vertex_group_normalize_all(group_select_mode='ALL', lock_active=False)
    for p in body.data.polygons:
        p.use_smooth = True
    return body, mat_kind


# ---------------------------------------------------------------- atlas UV
ATLAS_KINDS = ("body", "eyes", "cloth")


def make_atlas(body, mat_kind):
    me = body.data
    src = me.uv_layers[0]
    src.name = "UVMap"
    atlas = me.uv_layers.new(name="atlas")
    me.uv_layers.active = atlas
    src.active_render = True
    face_kind = [mat_kind.get(me.materials[p.material_index].name, "cloth") for p in me.polygons]
    bpy.context.scene.tool_settings.use_uv_select_sync = True
    activate(body)
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(me)
    bm.faces.ensure_lookup_table()
    for f in bm.faces:
        f.select = face_kind[f.index] in ATLAS_KINDS
    bmesh.update_edit_mesh(me)
    bpy.ops.uv.average_islands_scale()
    # faces matter more than shins: give the head 1.8x texel density before packing
    bm = bmesh.from_edit_mesh(me)
    deform = bm.verts.layers.deform.active
    head_groups = {body.vertex_groups[n].index for n in ("head", "neck_01") if n in body.vertex_groups}
    uvl = bm.loops.layers.uv["atlas"]
    head_faces = []
    for f in bm.faces:
        if not f.select or face_kind[f.index] not in ("body", "eyes"):
            continue
        w = sum(sum(v[deform].get(g, 0.0) for g in head_groups) for v in f.verts) / len(f.verts)
        if w > 0.5:
            head_faces.append(f)
    if head_faces:
        # scale each head face's UVs about the centroid of its connected UV island
        islands = uv_islands(head_faces, uvl)
        for isl in islands:
            loops = [l for f in isl for l in f.loops]
            c = sum((l[uvl].uv for l in loops), start=type(loops[0][uvl].uv)((0.0, 0.0))) / len(loops)
            for l in loops:
                l[uvl].uv = c + (l[uvl].uv - c) * 1.8
    bmesh.update_edit_mesh(me)
    bpy.ops.uv.pack_islands(udim_source='CLOSEST_UDIM', rotate=True, margin_method='FRACTION', margin=0.006)
    bpy.ops.object.mode_set(mode='OBJECT')
    return face_kind


def uv_islands(faces, uvl):
    """Connected UV islands among `faces` (an edge joins two faces when both its UV ends match)."""
    fs = set(faces)
    same = lambda p, q: (p[uvl].uv - q[uvl].uv).length < 1e-5
    seen, out = set(), []
    for f0 in faces:
        if f0 in seen:
            continue
        isl, stack = [], [f0]
        seen.add(f0)
        while stack:
            f = stack.pop()
            isl.append(f)
            for l in f.loops:
                for m in l.edge.link_loops:
                    g = m.face
                    if g is f or g not in fs or g in seen:
                        continue
                    # m runs the shared edge in the opposite direction
                    if same(l, m.link_loop_next) and same(l.link_loop_next, m):
                        seen.add(g); stack.append(g)
        out.append(isl)
    return out


# ---------------------------------------------------------------- baking
def new_img(name, res, color, alpha=False):
    if name in bpy.data.images:
        bpy.data.images.remove(bpy.data.images[name])
    im = bpy.data.images.new(name, res, res, alpha=alpha, float_buffer=False)
    im.colorspace_settings.name = 'sRGB' if color else 'Non-Color'
    im.generated_color = (0.5, 0.5, 0.5, 1.0)
    return im


def set_targets(body, targets):
    """targets: kind -> image. Every material gets an active image node pointing at its kind's image."""
    for m in body.data.materials:
        nt = m.node_tree
        node = nt.nodes.get("__bake")
        if node is None:
            node = nt.nodes.new('ShaderNodeTexImage'); node.name = "__bake"
        node.image = targets[MATK[m.name]]
        for n in nt.nodes:
            n.select = False
        node.select = True
        nt.nodes.active = node


def bake(body, typ, **kw):
    activate(body)
    log("bake", typ)
    bpy.ops.object.bake(type=typ, uv_layer="atlas", margin=12, margin_type='EXTEND', use_clear=True, **kw)


def principled(m):
    return [n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED']


def to_emission(m, socket_name, fallback):
    """Rewire a material so its Principled `socket_name` drives an emission shader (for EMIT bakes)."""
    nt = m.node_tree
    out = next((n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output), None) or \
        next((n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'), None)
    if out is None:
        out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    ps = principled(m)
    sock = ps[0].inputs[socket_name] if ps else None
    if sock is not None and sock.is_linked:
        nt.links.new(sock.links[0].from_socket, em.inputs['Color'])
    else:
        v = sock.default_value if sock is not None else fallback
        em.inputs['Color'].default_value = (v, v, v, 1.0)
    for l in list(out.inputs['Surface'].links):
        nt.links.remove(l)
    nt.links.new(em.outputs[0], out.inputs['Surface'])


def px(im):
    a = np.empty(im.size[0] * im.size[1] * 4, dtype=np.float32)
    im.pixels.foreach_get(a)
    return a.reshape(im.size[1], im.size[0], 4)


def save(arr, name, res, color, alpha):
    im = new_img(name, arr.shape[0], color, alpha)
    im.pixels.foreach_set(np.ascontiguousarray(arr, dtype=np.float32).ravel())
    if arr.shape[0] != res:
        im.scale(res, res)
    im.filepath_raw = os.path.join(OUT, name + ".png")
    im.file_format = 'PNG'
    im.save()
    log("wrote", im.filepath_raw)


MATK = {}


def bake_all(body, mat_kind):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences
        for dev in ('OPTIX', 'CUDA', 'HIP', 'ONEAPI'):
            try:
                prefs.compute_device_type = dev
                prefs.get_devices()
                if any(d.type == dev for d in prefs.devices):
                    for d in prefs.devices:
                        d.use = d.type == dev
                    sc.cycles.device = 'GPU'
                    log("cycles device", dev)
                    break
            except TypeError:
                continue
    except Exception as e:  # noqa
        log("GPU setup failed, CPU bake:", e)
    sc.cycles.samples = 8
    sc.cycles.use_denoising = False
    MATK.update({m.name: mat_kind.get(m.name, "cloth") for m in body.data.materials})
    kinds_present = set(MATK.values())
    card_kinds = [k for k in CARD_RES if k in kinds_present]
    junk = new_img("__junk", 64, False)

    def targets(atlas_img, card_imgs=None):
        t = {k: atlas_img for k in ATLAS_KINDS}
        for k in CARD_RES:
            t[k] = (card_imgs or {}).get(k, junk)
        return t

    # hair reads glossy with MakeHuman's stock roughness: floor it before the roughness bake
    for m in body.data.materials:
        if MATK[m.name] in CARD_RES:
            for p in principled(m):
                s = p.inputs['Roughness']
                if s.is_linked:
                    nt = m.node_tree
                    nt.links.remove(s.links[0])
                s.default_value = max(s.default_value, 0.62)

    alb = new_img("alb", ATLAS, True)
    cards = {k: new_img("card_" + k, CARD_RES[k], True) for k in card_kinds}
    set_targets(body, targets(alb, cards))
    bake(body, 'DIFFUSE', pass_filter={'COLOR'})
    A = px(alb)
    card_rgb = {k: px(cards[k]) for k in card_kinds}

    rough = new_img("rough", ATLAS, False)
    set_targets(body, targets(rough))
    bake(body, 'ROUGHNESS')
    R = px(rough)

    nrm = new_img("nrm", ATLAS, False)
    nrm.generated_color = (0.5, 0.5, 1.0, 1.0)
    set_targets(body, targets(nrm))
    bake(body, 'NORMAL', normal_space='TANGENT')
    N = px(nrm)

    ao = new_img("ao", ATLAS, False)
    ao.generated_color = (1, 1, 1, 1)
    set_targets(body, targets(ao))
    sc.cycles.samples = 64
    sc.world = sc.world or bpy.data.worlds.new("w")
    # local creases only (armpits, collar, folds): Blender's default 10 m AO reach blackens the
    # whole body inside its garments and every face under a hair cap
    sc.world.light_settings.distance = 0.05
    bake(body, 'AO')
    O = px(ao)
    sc.cycles.samples = 8

    # alpha: rewire every material's Principled alpha into emission, bake EMIT into the card images
    calpha = {k: new_img("calpha_" + k, CARD_RES[k], False) for k in card_kinds}
    for m in body.data.materials:
        to_emission(m, 'Alpha', 1.0)
    set_targets(body, targets(junk, calpha))
    if card_kinds:
        bake(body, 'EMIT')

    # ---- compose + write
    base = f"npc_{NPC}"
    alb_out = A.copy(); alb_out[..., 3] = 1.0
    save(alb_out, base + "_albedo", ATLAS, True, False)
    save(N, base + "_normal", ATLAS, False, False)
    orm = np.ones_like(R)
    orm[..., 0] = 0.35 + 0.65 * O[..., 0]   # soften baked AO (the game has SSAO on top)
    orm[..., 1] = np.clip(R[..., 0], 0.35, 1.0)
    orm[..., 2] = 0.0
    save(orm, base + "_orm", ATLAS // 2, False, False)
    for k in card_kinds:
        c = card_rgb[k].copy()
        c[..., 3] = px(calpha[k])[..., 0]
        save(c, f"{base}_{k}", CARD_RES[k], True, True)
    return card_kinds


# ---------------------------------------------------------------- export materials
def export_materials(body, face_kind):
    me = body.data
    names = []
    for k in ("body", "cloth", "eyes", "hair", "beard", "brow", "lash"):
        if k in face_kind:
            names.append(k)
    idx = {}
    me.materials.clear()
    for k in names:
        target = "body" if k == "eyes" else k   # eyes share the body atlas + opaque material
        if target in idx:
            continue
        m = bpy.data.materials.get("npc_" + target) or bpy.data.materials.new("npc_" + target)
        m.use_backface_culling = target == "body"
        idx[target] = len(me.materials)
        me.materials.append(m)
    for p, k in zip(me.polygons, face_kind):
        p.material_index = idx["body" if k == "eyes" else k]
    # drop the source UV: TEXCOORD_0 must be the atlas (card faces already carry their own UVs there)
    me.uv_layers.remove(me.uv_layers["UVMap"])
    return list(idx)


# ---------------------------------------------------------------- animations
def load_clips(arm):
    want = {"NPC_" + c for c in CLIPS}
    with bpy.data.libraries.load(ANIMS, link=False) as (src, dst):
        dst.actions = [a for a in src.actions if a in want or a.startswith(EXTRA_PREFIX)]
    k = arm.data.bones["pelvis"].head_local.z / REF_PELVIS_Z
    got = []
    for a in bpy.data.actions:
        if not a.name.startswith("NPC_"):
            continue
        a.use_fake_user = True
        for fc in a.fcurves:
            if fc.data_path == 'pose.bones["pelvis"].location':
                for kp in fc.keyframe_points:
                    kp.co.y *= k
                    kp.handle_left.y *= k
                    kp.handle_right.y *= k
        got.append(a.name)
    missing = sorted(want - set(got))
    if missing:
        log("MISSING clips:", missing)
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    # one muted NLA track per clip -> the exporter's NLA_TRACKS mode writes one glTF animation each
    ad = arm.animation_data_create()
    ad.action = None
    for name in got:
        a = bpy.data.actions[name]
        tr = ad.nla_tracks.new()
        tr.name = name[4:]
        st = tr.strips.new(tr.name, int(a.frame_range[0]), a)
        if hasattr(st, "action_slot") and len(a.slots):
            st.action_slot = a.slots[0]
        tr.mute = True
    log(f"clips: {len(got)}  pelvis scale {k:.3f}")
    return got


def main():
    bpy.context.scene.render.fps = 30
    fix_paths()
    arm = isolate()
    parts, kinds = prep_parts(arm)
    body, mat_kind = join(arm, parts, kinds)
    face_kind = make_atlas(body, mat_kind)
    card_kinds = bake_all(body, mat_kind)
    mats = export_materials(body, face_kind)
    arm.name = "Rig"
    arm.data.name = "Rig"
    clips = load_clips(arm)
    for x in bpy.context.scene.objects:
        x.select_set(False)
    arm.select_set(True); body.select_set(True)
    bpy.context.view_layer.objects.active = arm
    glb = os.path.join(OUT, f"npc_{NPC}.glb")
    bpy.ops.export_scene.gltf(
        filepath=glb, export_format='GLB', use_selection=True,
        export_apply=False, export_texcoords=True, export_normals=True, export_tangents=True,
        export_materials='EXPORT', export_image_format='NONE', export_vertex_color='NONE', export_attributes=False,
        export_skins=True, export_all_influences=False, export_def_bones=False, export_rest_position_armature=True,
        export_morph=False, export_animations=True, export_animation_mode='NLA_TRACKS', export_force_sampling=True,
        export_optimize_animation_size=True, export_anim_slide_to_zero=True, export_reset_pose_bones=True,
        export_frame_range=False, export_yup=True, export_cameras=False, export_lights=False,
    )
    rest = arm.data.bones["pelvis"].head_local
    meta = {
        "npc": NPC,
        "height_m": max(v.co.z for v in body.data.vertices),
        "pelvis_z": rest.z,
        "tris": tris(body),
        "materials": mats,
        "cards": card_kinds,
        "clips": [c[4:] for c in clips],
    }
    with open(os.path.join(OUT, f"npc_{NPC}.json"), "w") as f:
        json.dump(meta, f, indent=1)
    log("DONE", glb, meta["tris"], "tris")


main()
