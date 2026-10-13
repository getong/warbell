"""Downloaded creature models -> assets/forest_pbr/dl_creatures.glb.

The script-built SDF creatures read as cartoons next to the scanned world, so where a realistic,
openly licensed model exists we take it instead of sculpting (CLAUDE.md "Assets: download first").
Sources (see assets/CREDITS.md; each downloaded into its own folder under DL, never executed):

  raven  OpenGameArt "Raven" (raven_0.blend), CC0       -> the carrion VULTURE (oddities.rs) and the
                                                           crows circling the Hold (poi.rs)
  rabbit OpenGameArt "Rabbit" by CDmir (rabbit.blend), CC0 -> the wild rabbit (critters.rs)
  esox   OpenGameArt "Esox - Animated Fish" by CDmir, CC0  -> the pond / river fish (fish.rs)

The game animates creatures as RIGID PARTS (a mesh per limb, posed about a pivot), not skinned
meshes, so each rigged download is evaluated in its rest pose and split by its dominant skin bone
into the game's parts (body / wing / legs, torso / head / four legs, body / tail). Every part is
subdivided once (smooths the game-res silhouette) and its painted texture is baked into the
per-corner vertex colour the creature pipeline reads:

  * coat parts (vulture): R = region/16, G = cavity, B = coat TONE (the texture's luminance,
    normalised), A = tint -> `Kit::coat_part` walks the vulture's own coat ramp, so the raven's
    painted feather barring comes out in the griffon's browns (black -> buff), bare head grey.
  * raw parts (rabbit, fish, crow): linear RGB straight from the (lightly graded) texture; the game
    adds the surface code / material.

Game coords (Y up, +Z forward = the face). Pivots each part was cut at are printed as Rust consts.

    blender -b -Y --factory-startup --python tools/blender_forest/creatures_dl.py
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import kdtree  # noqa: E402
from common import OUT, export_glb, name_material  # noqa: E402

DL = Path("C:/Users/skibi/Documents/Codex/downloads")
MAIN, SKIN, DETAIL, EYE, ACCENT, HORN = range(6)


# ─────────────────────────────────────────────────────────────── extraction (Blender coords)
def grab(blend, mesh_name, images, uv_name="UVMap"):
    """Open `blend` (autoexec off), evaluate `mesh_name` in its armature's REST pose with all
    modifiers, and return verts (world), polys, per-loop UVs, per-vertex dominant bone, bone heads
    and the texture(s) as float arrays (row 0 = bottom, like UV v)."""
    bpy.ops.wm.open_mainfile(filepath=str(blend), load_ui=False)
    ob = bpy.data.objects[mesh_name]
    arm = ob.parent if ob.parent and ob.parent.type == "ARMATURE" else None
    if arm:
        if arm.animation_data:
            arm.animation_data.action = None
        for pb in arm.pose.bones:
            pb.matrix_basis.identity()
    for m in ob.modifiers:
        if m.type == "EDGE_SPLIT":
            m.show_viewport = False
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    mw = ob.matrix_world
    verts = np.array([tuple(mw @ v.co) for v in me.vertices])
    names = {i: g.name for i, g in enumerate(ob.vertex_groups)}
    dom = [names.get(max(v.groups, key=lambda g: g.weight).group, "") if v.groups else "" for v in me.vertices]
    uvl = me.uv_layers.get(uv_name) or me.uv_layers.active
    polys, uvs = [], []
    for p in me.polygons:
        polys.append(list(p.vertices))
        uvs.append([tuple(uvl.data[li].uv) for li in p.loop_indices])
    bones = {}
    if arm:
        for b in arm.data.bones:
            bones[b.name] = np.array(tuple(arm.matrix_world @ b.head_local))
    texs = []
    for path in images:
        im = bpy.data.images.load(str(path))
        w, h = im.size
        px = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)[:, :, :3]
        # Box-blur down to ~256 px: the bake is per vertex, so sample the texture's local mean.
        f = max(1, w // 256)
        px = px[: h - h % f, : w - w % f].reshape(h // f, f, w // f, f, 3).mean((1, 3))
        texs.append(px)
    return dict(verts=verts, polys=polys, uvs=uvs, dom=dom, bones=bones, texs=texs)


def sample(texs, u, v):
    """sRGB texel at UV (UDIM tiles 1001.. when `texs` has several)."""
    tile = int(np.clip(np.floor(u), 0, len(texs) - 1))
    t = texs[tile]
    h, w, _ = t.shape
    x = int(np.clip((u - tile) * w, 0, w - 1))
    y = int(np.clip((v - np.floor(v)) * h, 0, h - 1))
    return t[y, x]


def lin(c):
    c = np.asarray(c, dtype=np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


# ─────────────────────────────────────────────────────────────── building (game coords)
def to_game(p, flip):
    """Blender world -> game (Y up, +Z forward). `flip` turns a +Y-facing model around."""
    p = np.atleast_2d(p).astype(np.float64)
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    if flip:
        x, y = -x, -y
    return np.stack([x, z, -y], 1)


def part(name, src, sel, xf, origin, colour, subdiv=1):
    """Mesh the polys of `src` whose verts are all in `sel` (vertex mask), in game coords moved so
    `origin` (game) is the part pivot; subdivide; bake per-corner colour via `colour(rgb, u, v,
    region_bone, p_game)`; link + return the object."""
    keep = [i for i, poly in enumerate(src["polys"]) if 2 * sum(bool(sel[k]) for k in poly) >= len(poly)]
    used = sorted({k for i in keep for k in src["polys"][i]})
    remap = {k: j for j, k in enumerate(used)}
    g = xf(src["verts"][used]) - np.asarray(origin)
    me = bpy.data.meshes.new(name)
    faces = [[remap[k] for k in src["polys"][i]] for i in keep]
    me.from_pydata([tuple((x, -z, y)) for x, y, z in g], [], faces)
    uvl = me.uv_layers.new(name="UVMap")
    flat = [uv for i in keep for uv in src["uvs"][i]]
    uvl.data.foreach_set("uv", [c for uv in flat for c in uv])
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    # Bone of the nearest source vertex (survives the subdivision).
    tree = kdtree.KDTree(len(used))
    for j, k in enumerate(used):
        tree.insert(tuple(me.vertices[j].co), j)
    tree.balance()
    doms = [src["dom"][k] for k in used]
    if subdiv:
        m = ob.modifiers.new("sub", "SUBSURF")
        m.levels = subdiv
        m.uv_smooth = "PRESERVE_BOUNDARIES"
        dg = bpy.context.evaluated_depsgraph_get()
        dme = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
        ob.modifiers.clear()
        ob.data = dme
        bpy.data.meshes.remove(me)
        me = dme
        me.name = name
    me.materials.clear()
    me.materials.append(name_material("creature"))
    uvl = me.uv_layers.active
    cols = []
    for poly in me.polygons:
        poly.use_smooth = True
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            _, j, _ = tree.find(co)
            u, v = uvl.data[li].uv
            pg = np.array((co.x, co.z, -co.y))
            cols += list(colour(sample(src["texs"], u, v), u, v, doms[j], pg))
    me.color_attributes.new("Col", "FLOAT_COLOR", "CORNER")
    me.color_attributes["Col"].data.foreach_set("color", cols)
    me.color_attributes.active_color = me.color_attributes["Col"]
    print(f"{name}: {len(me.polygons)} faces, {len(me.vertices)} verts")
    return ob


def raw_colour(grade=1.0, sat=1.0):
    def f(rgb, u, v, bone, p):
        c = lin(rgb) * grade
        l = c.mean()
        c = l + (c - l) * sat
        return (*np.clip(c, 0, 1), 1.0)
    return f


def rust_vec(name, p):
    print(f"RUST const {name}: Vec3 = Vec3::new({p[0]:.3f}, {p[1]:.3f}, {p[2]:.3f});")


# ───────────────────────────────────────────────────────────────── raven -> vulture + crow
def raven():
    src = grab(DL / "raven/raven_0.blend", "raven_mesh", [])
    im = bpy.data.images["raven"]
    w, h = im.size
    src["texs"] = [np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)[:, :, :3]]
    return src


def vulture(src):
    """Griffon-sized: span ~2.1u. Left wing = game +X (the mirrored "_R" bones after the flip)."""
    bz = src["verts"][:, 2]
    legs = np.array([d.startswith(("leg", "toe")) for d in src["dom"]])
    ground = bz[legs].min()
    span = np.ptp(src["verts"][:, 0])
    s = 2.1 / span

    def xf(p):
        q = np.atleast_2d(p).copy()
        q[:, 2] -= ground
        return to_game(q * s, flip=True)

    g = xf(src["verts"])
    wing = np.array([d.startswith("Bone.001_") for d in src["dom"]])
    shoulder = xf(src["bones"]["Bone.001_R"])[0]
    shoulder[0] = abs(shoulder[0])
    left = g[:, 0] > 0.0
    # Tone: the texture's luminance, normalised over the whole bird (black -> coat dark,
    # barring highlights -> buff).
    allpx = src["texs"][0].reshape(-1, 3).mean(1)
    lo, hi = np.percentile(allpx, 4), np.percentile(allpx, 97)

    def coat(rgb, u, v, bone, p):
        t = float(np.clip((np.mean(rgb) - lo) / max(hi - lo, 1e-3), 0, 1))
        region = MAIN
        if bone == "Bone":
            region = SKIN  # bare head
        elif bone == "beak":
            region = HORN
        elif bone == "Bone.001":
            region = ACCENT  # the ruff round the neck base
        elif bone.startswith(("leg", "toe")):
            region = SKIN
        tone = 0.12 + 0.8 * t
        cav = 0.8 + 0.2 * t
        return (region / 16.0 + 1.0 / 32.0, cav, tone, 0.15 * (1 - t))

    body = part("dl_vulture_body", src, ~wing & ~legs, xf, (0, 0, 0), coat)
    wing_l = part("dl_vulture_wing", src, wing & left, xf, shoulder, coat)
    leg = part("dl_vulture_legs", src, legs, xf, (0, 0, 0), coat)
    rust_vec("DL_SHOULDER", shoulder)
    return [body, wing_l, leg]


def crow(src):
    """The whole raven, wings spread, body centred at the origin; span 1.3u (seen at 14u up)."""
    span = np.ptp(src["verts"][:, 0])
    s = 1.3 / span
    c = src["verts"].mean(0)

    def xf(p):
        return to_game((np.atleast_2d(p) - c) * s, flip=True)

    allv = np.ones(len(src["verts"]), bool)
    return [part("dl_crow", src, allv, xf, (0, 0, 0), raw_colour(1.0, 0.6))]


# ───────────────────────────────────────────────────────────────── rabbit
def rabbit():
    src = grab(DL / "rabbit/rabbit.blend", "Rabbit", [])
    im = bpy.data.images["rabbot-skinn"]
    w, h = im.size
    px = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)[:, :, :3]
    f = w // 256
    src["texs"] = [px.reshape(h // f, f, w // f, f, 3).mean((1, 3))]
    V = src["verts"]
    ground = V[:, 2].min()
    # Same footprint as the old box rabbit: ~0.5u nose to tail (the game scales it by 0.65).
    s = 0.56 / np.ptp(V[:, 1])

    def xf(p):
        q = np.atleast_2d(p).copy()
        q[:, 2] -= ground
        return to_game(q * s, flip=False)

    dom = src["dom"]
    head = np.array([d in ("Head", "Ear_L", "Ear_R", "Neck") for d in dom])
    groups = {
        "fl": ("FrontUpLeg_L", "FrontLeg_L", "FrontPaw_L"),
        "fr": ("FrontUpLeg_R", "FrontLeg_R", "FrontPaw_R"),
        "bl": ("BackUpLeg_L", "BackLeg_L", "BackLeg_L.001", "BackPaw_L"),
        "br": ("BackUpLeg_R", "BackLeg_R", "BackLeg_R.001", "BackPaw_R"),
    }
    objs = []
    taken = head.copy()
    colour = raw_colour(0.78, 1.15)  # the painted coat reads washed-out in game light: wild-brown it
    piv = xf(src["bones"]["Neck"])[0]
    objs.append(part("dl_rabbit_head", src, head, xf, piv, colour))
    rust_vec("RABBIT_HEAD", piv)
    for k, bones in groups.items():
        sel = np.array([d in bones for d in dom])
        taken |= sel
        piv = xf(src["bones"][bones[0]])[0]
        objs.append(part(f"dl_rabbit_leg_{k}", src, sel, xf, piv, colour))
        rust_vec(f"RABBIT_LEG_{k.upper()}", piv)
    objs.append(part("dl_rabbit_torso", src, ~taken, xf, (0, 0, 0), colour))
    return objs


# ───────────────────────────────────────────────────────────────── pike
def pike():
    tiles = [DL / f"esox/x/tex/ESOX-V2.100{i}.png" for i in range(1, 5)]
    # Only tile 1001 is the colour map (UVMap.001); the other tiles are normal / spec maps.
    src = grab(DL / "esox/x/esoxV2-wip2.blend", "Esox-Lucios", tiles[:1], uv_name="UVMap.001")
    V = src["verts"]
    split_y = src["bones"]["Spine.003"][1]
    # fish.rs hangs the tail child at z = -0.29: scale so the split lands there, 0.62u long.
    s = 0.62 / np.ptp(V[:, 1])
    zc = (V[:, 2].max() + V[:, 2].min()) / 2

    def xf(p):
        q = np.atleast_2d(p).copy()
        q[:, 1] -= split_y
        q[:, 2] -= zc
        g = to_game(q * s, flip=False)
        g[:, 2] -= 0.29
        return g

    tail_bones = ("Spine.003", "Caudal_Fin.001", "Caudal_Fin.002", "Caudal_Fin.003", "Dorsal_Fin.003",
                  "Anal_Fin.002", "Anal_Fin.003")
    tail = np.array([d in tail_bones for d in src["dom"]])
    colour = raw_colour(1.0, 0.85)
    return [
        part("dl_pike_body", src, ~tail, xf, (0, 0, 0), colour),
        part("dl_pike_tail", src, tail, xf, (0, 0, -0.29), colour),
    ]


if __name__ == "__main__":
    # Each source opens as a new main file (which drops every other datablock), so build each
    # source's parts, write them to a scratch .blend, then append all into one scene to export.
    import os
    tmp = Path(os.environ.get("TEMP", ".")) / "warbell_dl_parts"
    tmp.mkdir(exist_ok=True)
    parts = []
    for i, fn in enumerate([lambda: (lambda r: vulture(r) + crow(r))(raven()), rabbit, pike]):
        objs = fn()
        lib = tmp / f"p{i}.blend"
        bpy.data.libraries.write(str(lib), set(objs) | {o.data for o in objs})
        parts.append((lib, [o.name for o in objs]))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    out = []
    for lib, names in parts:
        with bpy.data.libraries.load(str(lib), link=False) as (src, dst):
            dst.objects = names
        for o in dst.objects:
            bpy.context.scene.collection.objects.link(o)
            out.append(o)
    # Each scratch library brought its own "creature" (-> creature.001, ...): rebind them all to
    # the one name the kit's material table knows.
    mat = bpy.data.materials.get("creature") or bpy.data.materials.new("creature")
    for o in out:
        o.data.materials.clear()
        o.data.materials.append(mat)
    export_glb(OUT / "dl_creatures.glb", out, tangents=False)
    print("wrote", OUT / "dl_creatures.glb")
