"""Organic HUMAN bodies for the shared biped rig -> people.glb (GPU-skinned townsfolk).

Round 2. The round-1 townsfolk were one rigid mesh per rig joint, so every shoulder, elbow and
knee read as a separate peg (and the outline pass inked the seam). Now a person is ONE skinned
mesh on the same biped joint entities (`biped::spawn_biped` frames and pivots are unchanged, so
every clip keeps working): the game assembles it from the pieces below and binds it to the
joints with smooth weights, so limbs bend at the joints and skirts follow the thighs.

Shapes are signed-distance models (sdfkit.py, like the animals): tapered round-cone chains and
smooth unions, so limbs taper naturally, muscles blend, and clothing is the body surface pushed
out (`offset`) and clipped by masks — it always hugs the body.

FRAMES. Body pieces are authored in the RIG's rest space (game coords: Y up, +Z forward, the
`rig` entity's origin; joints at their `spawn_biped` rest offsets, all rotations identity, legs
at +-HDX, shoulders at +-SDX). Head pieces (`hu_head_*`, `hu_hair_*`, `hu_beard_*`, `hu_hat_*`)
are authored in the HEAD joint's frame, unscaled; the game places them at the head pivot and
scales them by the head scale, lerped by the head weight so the neck stub stays body-sized.

BAKED DATA
  vertex colour  R = region / 16 + 1/32 (palette slot: skin, lip, eye, hair, tunic ...)
                 G = cavity / ambient occlusion (from the whole default body's SDF)
                 B = weathering amount (ruddy skin, grimy hems, dusty boots — the game tints by region)
  UV0, UV1       skin weights: each component = joint + 0.005 + weight * 0.98 (4 influences;
                 joint order = `JOINTS`, the order `biped::spawn_biped` binds them in)

Tools (`hu_tool_*`) stay rigid metaball props on the `Sword` / `Shield` pivots.

    blender -b --factory-startup --python tools/blender_forest/people.py [-- "out.png|pose|yaw|cx,cz,width|looks" ...]
    Each arg renders one posed Workbench lineup (LBS in numpy, like the game): pose = rest | walk |
    run | sit, yaw in degrees, an ortho camera centre + width, looks = '+'-separated indices of the
    preview lineup. PEOPLE_ONLY=prefix,... builds a subset (no export), PEOPLE_NO_EXPORT=1 skips the
    glb, PEOPLE_VERBOSE=1 prints per-body decimation, PEOPLE_PREVIEW_RES="w,h".
"""
import math
import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from common import OUT, clear_scene, export_glb, name_material  # noqa: E402
from creatures import Part, make_metaball  # noqa: E402
from sdfkit import (  # noqa: E402
    Body, Chain, Cone, Ellipsoid, Prim, RBox, Sphere, Squash, Tufts, ambient_occlusion, gradient,
    mesh_body, norm, rot_x, rot_y, rot_z, smoothstep, v3,
)

# Region codes (<= 16). Keep in sync with `peasant_model::kit_peasant_meshes` (palette order).
(SKIN, LIP, EYE, HAIR, TUNIC, TRIM, TROUSER, LEATHER, BOOT, METAL, HEADCLOTH, BAND, TABARD, FLETCH,
 CLOAK, HELM) = range(16)

# Skin joints, in the order the game binds them (`biped::SKIN_JOINTS`).
JOINTS = ("hips", "torso", "neck", "head", "sh_l", "el_l", "sh_r", "el_r", "hip_l", "knee_l", "foot_l",
          "hip_r", "knee_r", "foot_r")
HIPS, TORSO, NECK, HEAD, SH_L, EL_L, SH_R, EL_R, HIP_L, KNEE_L, FOOT_L, HIP_R, KNEE_R, FOOT_R = range(14)

SDX = 0.2  # authored shoulder joint half-span (`peasant_model::KIT_SHOULDER_DX`; the game reshapes per build)
HDX = 0.1  # hip joint half-span (`peasant_model::KIT_HIP_DX`)
HEAD_Y = 1.63  # head pivot in the rig (hips 1.05 + torso 0.15 + neck 0.35 + head 0.08)
HEAD_SCALE = 1.06 * 1.1  # adult head scale the body is proportioned for (kids: per build, `peasant_model::kit_build`)
HEAD_FRAME = ("hu_head", "hu_hair", "hu_beard", "hu_hat")


def P(x, y, z):
    return v3((x, y, z))


def ss(e0, e1, x):
    return smoothstep(e0, e1, x)


# ───────────────────────────────────────────────────────────────── extra SDF pieces
BIG = 10.0


class Fn(Prim):
    """Any callable SDF with explicit bounds."""

    def __init__(self, fn, lo, hi):
        self.fn, self.lo, self.hi = fn, v3(lo), v3(hi)

    def d(self, p):
        return self.fn(p)

    def bounds(self):
        return self.lo, self.hi


def offset(body, t):
    """`body`'s surface pushed out by `t` (a solid that contains the body)."""
    lo, hi = body.bounds()
    return Fn(lambda p: body.eval(p) - t, lo - t, hi + t)


def layer(body, inner, outer):
    """A closed skin between `body` pushed out by `inner` and by `outer` (bands, belts, sashes):
    no open edges, so it decimates cleanly and needs no culling."""
    lo, hi = body.bounds()

    def fn(p):
        d = body.eval(p)
        return np.maximum(d - outer, inner - d)
    return Fn(fn, lo - outer, hi + outer)


def half(c, n):
    """Half-space keeping (p - c) . n >= 0 (for `Body.cut`)."""
    c, n = v3(c), v3(n) / np.linalg.norm(n)
    return Fn(lambda p: (c - p) @ n, (-BIG,) * 3, (BIG,) * 3)


def slab(axis, lo, hi, c=(0, 0, 0)):
    """Keep lo <= (p - c) . axis <= hi."""
    a, c = v3(axis) / np.linalg.norm(axis), v3(c)
    return Fn(lambda p: np.maximum(lo - (p - c) @ a, (p - c) @ a - hi), (-BIG,) * 3, (BIG,) * 3)


class CappedCone(Prim):
    """Flat-ended cone frustum from `a` (radius ra) to `b` (radius rb) — exact (iq)."""

    def __init__(self, a, b, ra, rb):
        self.a, self.b, self.ra, self.rb = v3(a), v3(b), float(ra), float(rb)

    def d(self, p):
        a, b, ra, rb = self.a, self.b, self.ra, self.rb
        rba = rb - ra
        ba = b - a
        baba = float(ba @ ba)
        pa = p - a
        papa = (pa * pa).sum(1)
        paba = (pa @ ba) / baba
        x = np.sqrt(np.maximum(papa - paba * paba * baba, 0.0))
        cax = np.maximum(0.0, x - np.where(paba < 0.5, ra, rb))
        cay = np.abs(paba - 0.5) - 0.5
        k = rba * rba + baba
        f = np.clip((rba * (x - ra) + paba * baba) / k, 0.0, 1.0)
        cbx = x - ra - f * rba
        cby = paba - f
        s = np.where((cbx < 0.0) & (cay < 0.0), -1.0, 1.0)
        return s * np.sqrt(np.minimum(cax * cax + cay * cay * baba, cbx * cbx + cby * cby * baba))

    def bounds(self):
        r = max(self.ra, self.rb)
        return np.minimum(self.a, self.b) - r, np.maximum(self.a, self.b) + r


def armholes(x0, y0, y1):
    """Keep |x| < x0 above the armpit (blending in from y0 to y1); no cut lower down."""
    return Fn(lambda p: np.abs(p[:, 0]) - (x0 + 0.4 * (1.0 - smoothstep(y0, y1, p[:, 1]))), (-BIG,) * 3, (BIG,) * 3)


def over_shoulder(tb, x_of, phis, lift=0.005, axis_y=1.42, axis_z=-0.005):
    """Knots on the trunk surface along a strap from the chest over the shoulder to the back:
    rays toward a horizontal axis along X (phi 0 = front, pi/2 = top, pi = back)."""
    org, dirs = [], []
    for ph in phis:
        d = np.array([0.0, math.sin(ph), math.cos(ph)])
        org.append(np.array([x_of(ph), axis_y, axis_z]) + d * 0.3)
        dirs.append(-d)
    pts = hit(tb.eval, org, dirs, t1=0.3)
    return [P(*(q - dd * lift)) for q, dd in zip(pts, dirs)]


def ring(points_r, closed=True):
    """A Chain through (point, radius) knots, closed into a loop."""
    k = list(points_r)
    if closed:
        k.append(k[0])
    return Chain(k)


class PBody(Body):
    """A Body whose meshing grid can be clipped to a box (shells of big reference bodies)."""

    def __init__(self, h=0.004, budget=1000, clip=None):
        super().__init__(h=h, budget=budget)
        self.clip = clip

    def bounds(self):
        lo, hi = super().bounds()
        if self.clip is not None:
            lo = np.maximum(lo, v3(self.clip[0]))
            hi = np.minimum(hi, v3(self.clip[1]))
        return lo, hi


class Folds:
    """Vertical drape folds round a vertical axis: 0..1, deeper toward `y_deep`."""

    def __init__(self, n, seed=0.0, y_top=1.06, y_deep=0.88, cx=0.0, cz=0.0, power=1.4):
        self.n, self.seed, self.y0, self.y1, self.cx, self.cz, self.pw = n, seed, y_top, y_deep, cx, cz, power

    def __call__(self, p):
        th = np.arctan2(p[:, 0] - self.cx, p[:, 2] - self.cz)
        s = np.sin(self.n * th + 1.3 * np.sin(2 * th + self.seed) + 0.6 * np.sin(3 * th + 2.1 * self.seed))
        return ((0.5 + 0.5 * s) ** self.pw) * smoothstep(self.y0, self.y1, p[:, 1])


class Creases:
    """Horizontal creases round a vertical limb (sleeve / trouser bunching): 0..1."""

    def __init__(self, freq, cx, cz, seed=0.0):
        self.f, self.cx, self.cz, self.seed = freq, cx, cz, seed

    def __call__(self, p):
        th = np.arctan2(p[:, 0] - self.cx, p[:, 2] - self.cz)
        s = np.sin(self.f * p[:, 1] + 1.6 * np.sin(th + self.seed) + 0.7 * np.sin(2.3 * th))
        return np.clip(s, 0.0, 1.0) ** 1.5


def hit(fn, origin, direction, t1=0.3, steps=40):
    """First outside->inside zero crossing of `fn` along origin + t * dir (rows batched)."""
    o = np.atleast_2d(np.asarray(origin, float))
    d = np.atleast_2d(np.asarray(direction, float))
    d = d / np.linalg.norm(d, axis=1, keepdims=True)
    ts = np.linspace(0.0, t1, steps)
    vals = np.stack([fn(o + t * d) for t in ts])  # (steps, N)
    inside = vals < 0
    first = np.where(inside.any(0), inside.argmax(0), steps - 1)
    lo = ts[np.maximum(first - 1, 0)]
    hi = ts[first]
    for _ in range(14):
        mid = (lo + hi) / 2
        v = fn(o + mid[:, None] * d)
        lo = np.where(v >= 0, mid, lo)
        hi = np.where(v >= 0, hi, mid)
    return o + ((lo + hi) / 2)[:, None] * d


def surface_ring(fn, cx, cz, y_of, rad=0.3, n=28, embed=0.0, tube=0.005, tilt=None):
    """Knots of a band hugging the surface of `fn` round the vertical axis (cx, cz): at angle a
    (0 = +Z front, +90deg = +X) the height is `y_of(a)`. `embed` > 0 sinks the tube in."""
    angs = np.linspace(0, 2 * math.pi, n, endpoint=False)
    org = np.array([[cx + rad * math.sin(a), y_of(a), cz + rad * math.cos(a)] for a in angs])
    dirs = np.array([[-math.sin(a), 0.0, -math.cos(a)] for a in angs])
    pts = hit(fn, org, dirs, t1=rad)
    out = pts + dirs * (embed - tube)
    return [(P(*q), tube) for q in out]


# ───────────────────────────────────────────────────────────────── skin weights
def skin_weights(p, kind):
    """(N, 14) joint weights for rest positions `p` of a piece of skin `kind`:
    trunk | arm_l | arm_r | leg_l | leg_r | head (head-local coords)."""
    x, y = p[:, 0], p[:, 1]
    W = np.zeros((len(p), len(JOINTS)))
    if kind == "trunk":
        t = ss(1.13, 1.27, y)  # hips -> torso (torso joint 1.2)
        hd = ss(1.52, 1.566, y)  # torso -> head (collar -> jaw)
        leg = ss(1.04, 0.93, y)  # hips -> thighs below the hip joints (1.0)
        sr = ss(-0.055, 0.055, x)  # left / right thigh (a skirt's centre takes both)
        arm_l = ss(1.50, 1.40, y) * ss(0.125, 0.185, -x)  # the shoulder cap rides the deltoid
        arm_r = ss(1.50, 1.40, y) * ss(0.125, 0.185, x)
        kw = ss(0.66, 0.565, y)  # a long skirt's hem round the knee follows the shin a little
        W[:, HIPS] = (1 - t) * (1 - leg)
        W[:, HIP_L] = (1 - t) * leg * (1 - sr) * (1 - kw)
        W[:, HIP_R] = (1 - t) * leg * sr * (1 - kw)
        W[:, KNEE_L] = (1 - t) * leg * (1 - sr) * kw
        W[:, KNEE_R] = (1 - t) * leg * sr * kw
        up = t * (1 - hd)
        W[:, TORSO] = up * (1 - arm_l - arm_r)
        W[:, SH_L] = up * arm_l
        W[:, SH_R] = up * arm_r
        W[:, HEAD] = t * hd
    elif kind in ("arm_l", "arm_r"):
        sh, el = (SH_L, EL_L) if kind == "arm_l" else (SH_R, EL_R)
        up = ss(1.50, 1.40, y)  # torso -> upper arm round the shoulder pivot (1.47)
        fo = ss(1.205, 1.135, y)  # upper arm -> forearm round the elbow (1.17)
        W[:, TORSO] = 1 - up
        W[:, sh] = up * (1 - fo)
        W[:, el] = up * fo
    elif kind in ("leg_l", "leg_r"):
        hp, kn, ft = (HIP_L, KNEE_L, FOOT_L) if kind == "leg_l" else (HIP_R, KNEE_R, FOOT_R)
        th = ss(1.04, 0.93, y)  # hips -> thigh (hip joint 1.0)
        kw = ss(0.635, 0.565, y)  # thigh -> shin (knee 0.6)
        fw = ss(0.19, 0.12, y)  # shin -> foot (ankle 0.15)
        W[:, HIPS] = 1 - th
        W[:, hp] = th * (1 - kw)
        W[:, kn] = kw * (1 - fw)
        W[:, ft] = fw
    elif kind == "head":
        hw = ss(-0.11, -0.055, y)  # head-local: neck stub -> skull
        W[:, HEAD] = hw
        W[:, TORSO] = 1 - hw
    else:
        raise KeyError(kind)
    return W


def encode_weights(W):
    """Top-4 influences -> (uv0, uv1) per vertex: joint + 0.005 + weight * 0.98."""
    order = np.argsort(-W, axis=1)[:, :4]
    w = np.take_along_axis(W, order, 1)
    w = np.where(w < 0.004, 0.0, w)
    w = w / np.maximum(w.sum(1, keepdims=True), 1e-9)
    enc = order + 0.005 + w * 0.98
    enc = np.where(w > 0, enc, 0.005)
    return enc[:, 0:2], enc[:, 2:4]


# ───────────────────────────────────────────────────────────────── pieces
class Piece:
    """One exported mesh: closed SDF bodies (each decimated to its own budget), a skin kind,
    the frame it is authored in, and a weathering (vertex B) function."""

    def __init__(self, name, skin, frame="rig"):
        self.name, self.skin, self.frame = name, skin, frame
        self.bodies = []  # (body, cull_fn, cull_depth)
        self.weather = None  # fn(p, n, region) -> 0..1
        # Optional hooks for other rigs built with these tools (orks.py): `weights(p, kind)` replaces
        # `skin_weights` (another frame's joint spans), `extra(p, n, region)` -> 0..1 fills vertex
        # colour A (left at 1 by the townsfolk), `regions(face_centres, regions)` repaints faces
        # (decals with no relief: war paint).
        self.weights = None
        self.extra = None
        self.regions = None
        # Mirror-symmetric decimation (a body can override with its own `sym`).
        self.sym = frame == "head" or skin == "trunk"

    def add(self, body, cull=None, depth=0.003):
        """`cull`: an SDF; faces whose centre lies deeper than `depth` inside it are dropped (the
        hidden inner caps of a clipped clothing shell)."""
        self.bodies.append((body, cull, depth))
        return body


def bl(p):
    """Game (Y up, +Z fwd) -> Blender (Z up)."""
    return np.stack([p[:, 0], -p[:, 2], p[:, 1]], 1)


def gm(p):
    """Blender -> game."""
    return np.stack([p[:, 0], p[:, 2], -p[:, 1]], 1)


def _clean(me, h):
    """Merge the near-duplicate vertices / slivers the surface-nets projection can leave (they
    block edge collapses, so a thin band would stall far above its budget)."""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=h * 0.08)
    bmesh.ops.dissolve_degenerate(bm, dist=h * 0.02, edges=bm.edges)
    bm.to_mesh(me)
    bm.free()


def _tris(me):
    return sum(len(f.vertices) - 2 for f in me.polygons)


def _decimate(ob, budget, sym=False):
    """Collapse-decimate `ob` to ~`budget` tris. With `sym`, try a mirror-symmetric pass first
    (cleaner faces / hats); if it cannot pair enough of the mesh to reach the budget, fall back.
    A pass that stalls short of the budget is repeated."""
    if _tris(ob.data) <= budget:
        return
    for use_sym in ((True, False) if sym else (False,)):
        src = ob.data
        out = None
        for _ in range(3):
            tris = _tris(src if out is None else out)
            if tris <= budget * 1.05:
                break
            tmp = bpy.data.objects.new("dec_tmp", out or src.copy())
            bpy.context.scene.collection.objects.link(tmp)
            m = tmp.modifiers.new("dec", "DECIMATE")
            m.ratio = budget / tris
            if use_sym:
                m.use_symmetry = True
                m.symmetry_axis = "X"
            dg = bpy.context.evaluated_depsgraph_get()
            dme = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg))
            old = tmp.data
            bpy.data.objects.remove(tmp)
            bpy.data.meshes.remove(old)
            out = dme
        got = _tris(out)
        if use_sym and got > budget * 1.08:
            bpy.data.meshes.remove(out)
            continue
        ob.data = out
        bpy.data.meshes.remove(src)
        return


BUDGET_SCALE = 1.0


def build_piece(piece, ao_fn):
    """Mesh, decimate, region-colour, AO-bake and skin-weight one piece -> a Blender object."""
    verts, faces, owner = [], [], []
    for bi, (body, cull, depth) in enumerate(piece.bodies):
        body.sym = getattr(body, "sym", piece.sym)
        v, q = mesh_body(body, np.eye(3), np.zeros(3))
        if len(q) == 0:
            continue
        if cull is not None:
            cen = v[q].mean(1)
            keep = cull(cen) > -depth
            q = q[keep]
            used = np.unique(q)
            remap = -np.ones(len(v), np.int64)
            remap[used] = np.arange(len(used))
            v, q = v[used], remap[q]
        me = bpy.data.meshes.new(f"{piece.name}_b{bi}")
        me.from_pydata(bl(v).tolist(), [], q.tolist())
        ob = bpy.data.objects.new(f"{piece.name}_b{bi}", me)
        bpy.context.scene.collection.objects.link(ob)
        raw = len(q) * 2
        _clean(ob.data, body.h)
        _decimate(ob, int(body.budget * BUDGET_SCALE), body.sym)
        me = ob.data
        if os.environ.get("PEOPLE_VERBOSE"):
            print(f"  {piece.name} body {bi}: {raw} -> {sum(len(f.vertices) - 2 for f in me.polygons)} (budget {body.budget})")
        base = len(verts)
        verts += [tuple(x.co) for x in me.vertices]
        for poly in me.polygons:
            faces.append([base + i for i in poly.vertices])
            owner.append(bi)
        bpy.data.objects.remove(ob)
        bpy.data.meshes.remove(me)
    me = bpy.data.meshes.new(piece.name)
    me.from_pydata(verts, [], faces)
    me.materials.append(name_material("creature"))
    ob = bpy.data.objects.new(piece.name, me)
    bpy.context.scene.collection.objects.link(ob)
    for poly in me.polygons:
        poly.use_smooth = True

    ps = gm(np.array(verts))
    owner = np.array(owner)
    vowner = np.zeros(len(ps), np.int64)
    for fi, f in enumerate(faces):
        vowner[f] = owner[fi]
    nrm = np.zeros_like(ps)
    for bi, (body, _, _) in enumerate(piece.bodies):
        sel = vowner == bi
        if sel.any():
            g = gradient(body.eval, ps[sel])
            nrm[sel] = g / np.maximum(norm(g), 1e-9)[:, None]

    own = [b for b, _, _ in piece.bodies]

    def ao_field(q):
        d = ao_fn(q)
        for b in own:
            d = np.minimum(d, b.eval(q))
        return d
    ao = ambient_occlusion(ao_field, ps + nrm * 0.0015, nrm, step=0.009, k=1.7)
    cav = 0.58 + 0.42 * ao
    cen = np.array([ps[f].mean(0) for f in faces])
    freg = np.zeros(len(faces), np.int64)
    for bi, (body, _, _) in enumerate(piece.bodies):
        sel = owner == bi
        if sel.any():
            _, rg = body.eval(cen[sel], want_region=True)
            freg[sel] = rg
    if piece.regions:
        freg = piece.regions(cen, freg)
    # Vertex region (for the weathering fn): the region of any face using it.
    vreg = np.zeros(len(ps), np.int64)
    for fi, f in enumerate(faces):
        vreg[f] = freg[fi]
    wth = piece.weather(ps, nrm, vreg) if piece.weather else np.zeros(len(ps))
    wth = np.clip(wth, 0.0, 1.0)
    W = (piece.weights or skin_weights)(ps, piece.skin)
    ext = np.clip(piece.extra(ps, nrm, vreg), 0.0, 1.0) if piece.extra else np.ones(len(ps))
    uv0, uv1 = encode_weights(W)

    me.uv_layers.new(name="UVMap")
    me.uv_layers.new(name="UV1")
    me.color_attributes.new("Col", "FLOAT_COLOR", "CORNER")
    cols, u0, u1 = [], [], []
    for poly in me.polygons:
        rg = freg[poly.index]
        for li in poly.loop_indices:
            vi = me.loops[li].vertex_index
            cols += [rg / 16.0 + 1.0 / 32.0, cav[vi], wth[vi], ext[vi]]
            # The glTF exporter flips V (v -> 1 - v): pre-flip so the file holds the code.
            u0 += [uv0[vi, 0], 1.0 - uv0[vi, 1]]
            u1 += [uv1[vi, 0], 1.0 - uv1[vi, 1]]
    me.uv_layers["UVMap"].data.foreach_set("uv", u0)
    me.uv_layers["UV1"].data.foreach_set("uv", u1)
    me.color_attributes["Col"].data.foreach_set("color", cols)
    me.color_attributes.active_color = me.color_attributes["Col"]
    # Keep the decoded data for the preview poser.
    ob["skin"] = piece.skin
    ob["frame"] = piece.frame
    return ob, W


# ───────────────────────────────────────────────────────────────── the trunk
def trunk_core(h=0.004, budget=950):
    """Tunic over a slim, real chest: pectorals, shoulder blades, sloping traps, a waist cinched by
    the belt, the tunic blousing over it and flaring into a short skirt with drape folds."""
    b = PBody(h=h, budget=budget)
    T = TUNIC
    b.add(Ellipsoid(P(0, 0.99, -0.012), (0.146, 0.1, 0.108)), T)  # pelvis + seat
    b.add(Ellipsoid(P(0, 1.145, 0.002), (0.13, 0.11, 0.092)), T, 0.045)  # waist / belly (the tunic hangs loose)
    b.add(Ellipsoid(P(0, 1.33, -0.008), (0.136, 0.162, 0.096)), T, 0.05)  # ribcage
    b.add(Ellipsoid(P(0, 1.37, 0.012), (0.13, 0.065, 0.076)), T, 0.035)  # chest: one broad, flat mass
    for sx in (-1, 1):
        b.add(Ellipsoid(P(sx * 0.074, 1.39, -0.056), (0.062, 0.078, 0.046)), T, 0.035)  # shoulder blades
        b.add(Ellipsoid(P(sx * 0.105, 1.27, -0.022), (0.036, 0.1, 0.058)), T, 0.04)  # lats
        b.add(Cone(P(sx * 0.03, 1.512, -0.018), P(sx * 0.165, 1.482, -0.006), 0.036, 0.03), T, 0.04)  # traps
        b.add(Sphere(P(sx * 0.162, 1.456, 0.004), 0.039), T, 0.035)  # shoulder joint cap
    b.add(Cone(P(0, 1.46, -0.01), P(0, 1.56, -0.006), 0.062, 0.05), T, 0.025)  # neck root -> collar
    b.add(Ellipsoid(P(0, 1.124, 0.008), (0.128, 0.026, 0.094)), T, 0.02)  # blousing over the belt
    b.add(Squash(CappedCone(P(0, 1.075, 0), P(0, 0.86, 0), 0.14, 0.165), P(0, 0, -0.006), (1, 1, 0.8)), T, 0.03)
    b.cut(half(P(0, 0.874, 0), (0, 1, 0)))  # hem line
    # Collar: trim the neck root under a shallow bowl so the head's neck rises out of it.
    b.cut(Fn(lambda p: p[:, 1] - (1.528 + 1.6 * (p[:, 0] ** 2 + (0.8 * p[:, 2]) ** 2)), (-1,) * 3, (1,) * 3))
    b.shag(Ellipsoid(P(0, 0.93, -0.005), (0.21, 0.085, 0.17)), 0.0055, Folds(9, 0.7, 1.05, 0.88), soft=0.04)
    return b


_TRUNK = None


def trunk():
    global _TRUNK
    if _TRUNK is None:
        _TRUNK = trunk_core()
    return _TRUNK


def skirt_long(hem=0.66, flare=0.2):
    """Reference: the tunic skirt continued down to `hem` — what aprons / tabards / robes hang on."""
    b = PBody(h=0.004, budget=0)
    b.add(Ellipsoid(P(0, 0.99, -0.012), (0.146, 0.1, 0.108)), TUNIC)
    b.add(Ellipsoid(P(0, 1.145, 0.0), (0.124, 0.11, 0.088)), TUNIC, 0.045)
    b.add(Squash(CappedCone(P(0, 1.075, 0), P(0, hem, 0), 0.138, flare), P(0, 0, -0.006), (1, 1, 0.8)), TUNIC, 0.03)
    return b


def trunk_weather(p, n, reg):
    y = p[:, 1]
    hem = ss(0.95, 0.875, y) * 0.55  # grime toward the hem
    pits = ss(1.42, 1.34, y) * ss(0.1, 0.135, np.abs(p[:, 0])) * 0.35  # sweat under the arms
    return hem + pits


def piece_trunk():
    pc = Piece("hu_trunk", "trunk")
    tb = trunk()
    pc.add(tb)
    tfn = tb.eval
    # Belt (cinched over the tunic), buckle, a strap end and a small pouch.
    belt = PBody(h=0.0025, budget=130, clip=((-0.22, 1.06, -0.2), (0.22, 1.12, 0.2)))
    belt.add(layer(tb, -0.001, 0.0065), LEATHER).cut(slab((0, 1, 0), 1.072, 1.1))
    pc.add(belt)
    zf = hit(tfn, [[0, 1.086, 0.3]], [[0, 0, -1]])[0][2]
    bits = PBody(h=0.0016, budget=110)
    bits.sym = False
    bits.add(RBox(P(0, 1.086, zf + 0.009), (0.017, 0.016, 0.004), 0.003), METAL)
    bits.sub(RBox(P(0, 1.086, zf + 0.012), (0.009, 0.008, 0.004), 0.002), METAL)
    bits.add(Cone(P(0.012, 1.086, zf + 0.009), P(0.0, 1.086, zf + 0.012), 0.0022, 0.0022), METAL, 0.001)  # tongue
    z2 = hit(tfn, [[0.034, 1.04, 0.3]], [[0, 0, -1]])[0][2]
    bits.add(Cone(P(0.03, 1.08, zf + 0.004), P(0.036, 1.03, z2 + 0.004), 0.0062, 0.0055), LEATHER, 0.002)
    pc.add(bits)
    pouch = PBody(h=0.002, budget=80)
    pouch.sym = False
    xp = hit(tfn, [[-0.3, 1.03, 0.06]], [[1, 0, 0]])[0]
    pouch.add(Ellipsoid(P(xp[0] - 0.014, 1.035, 0.06), (0.016, 0.034, 0.03), rot_z(-0.12)), LEATHER)
    pouch.add(Ellipsoid(P(xp[0] - 0.02, 1.066, 0.06), (0.015, 0.01, 0.031)), LEATHER, 0.004)  # flap
    pc.add(pouch)
    # Neckline band, hem band.
    col = PBody(h=0.0018, budget=80)
    angs = np.linspace(0, 2 * math.pi, 28, endpoint=False)
    org = [[0.06 * math.sin(a), 1.7, -0.004 + 0.057 * math.cos(a)] for a in angs]
    pts = hit(tfn, org, [[0, -1, 0]] * len(org), t1=0.3)
    col.add(ring([(P(q[0], q[1] + 0.002, q[2]), 0.0055) for q in pts]), TRIM)
    pc.add(col)
    hemb = PBody(h=0.0025, budget=120, clip=((-0.25, 0.86, -0.2), (0.25, 0.905, 0.2)))
    hemb.add(layer(tb, -0.02, 0.0035), TRIM).cut(slab((0, 1, 0), 0.874, 0.893))
    pc.add(hemb)
    pc.weather = trunk_weather
    return pc


# ───────────────────────────────────────────────────────────────── arms + hands
def fist(b, sx, gx, gy, gz, k=0.006):
    """Gripping hand round the tool haft (an axis along Z through the grip point G). The back of
    the hand faces out, the palm in; fingers curl under the haft and close on its inner side, the
    thumb wraps over the front."""
    S = SKIN
    X = lambda d: gx + sx * d  # noqa: E731  (+ = lateral)
    # Wrist into the back of the hand (flatter side to side than front to back).
    b.add(Squash(Cone(P(0, 0.092, 0), P(0, 0.058, 0), 0.02, 0.0195), P(X(0.01), gy, gz + 0.004), (1.0, 1.0, 1.32)),
          S, 0.012)
    # Back of the hand / palm (metacarpals) — lateral of the haft.
    b.add(RBox(P(X(0.024), gy + 0.03, gz + 0.004), (0.0112, 0.034, 0.033), 0.0105), S, 0.012)
    b.add(Ellipsoid(P(X(0.012), gy + 0.034, gz + 0.022), (0.012, 0.022, 0.014)), S, 0.008)  # thenar pad
    # Four fingers, index forward (thumb side) to little finger back, curled round the haft.
    for i, (z, s) in enumerate(((0.025, 1.0), (0.008, 1.04), (-0.009, 0.98), (-0.024, 0.86))):
        r = 0.0084 * s
        knots = [(P(X(0.026), gy - 0.004, gz + z), r * 1.08),  # knuckle
                 (P(X(0.013), gy - 0.03 * s, gz + z * 1.02), r),  # proximal phalanx under the haft
                 (P(X(-0.016), gy - 0.026 * s, gz + z * 1.03), r * 0.92),  # middle phalanx
                 (P(X(-0.026), gy - 0.004, gz + z * 1.03), r * 0.82)]  # tip pressed on the haft
        b.add(Chain(knots), S, k)
        b.add(Sphere(P(X(0.027), gy - 0.002, gz + z), r * 1.12), S, k)  # knuckle bump
    # Thumb: from the thenar over the top of the haft, in front of the index finger.
    b.add(Chain([(P(X(0.012), gy + 0.044, gz + 0.03), 0.0105), (P(X(-0.006), gy + 0.03, gz + 0.042), 0.0088),
                 (P(X(-0.02), gy + 0.018, gz + 0.04), 0.0076)]), S, k)


def arm_bodies(sx, sleeve):
    """(cloth body, skin body, extra bodies) of one arm in the rig frame."""
    ax, az = sx * SDX, 0.01
    X = lambda d: ax + sx * d  # noqa: E731
    T = TUNIC
    cl = PBody(h=0.002, budget=250 if sleeve else 170)
    cl.add(Ellipsoid(P(X(-0.004), 1.438, az - 0.002), (0.046, 0.066, 0.05)), T)  # deltoid
    upper = [(P(X(0.0), 1.43, az), 0.045), (P(X(0.001), 1.33, az + 0.003), 0.043), (P(X(0.0), 1.235, az), 0.038)]
    cl.add(Ellipsoid(P(X(0.0), 1.318, az + 0.022), (0.031, 0.058, 0.022)), T, 0.02)  # biceps
    cl.add(Ellipsoid(P(X(0.002), 1.335, az - 0.016), (0.033, 0.072, 0.026)), T, 0.02)  # triceps
    sk = PBody(h=0.0017, budget=290 if not sleeve else 200)
    extra = []
    if sleeve:
        cl.add(Chain(upper + [(P(X(0.0), 1.17, az - 0.004), 0.0375)]), T, 0.025)
        cl.add(Sphere(P(X(0.0), 1.168, az - 0.012), 0.033), T, 0.015)  # elbow point
        cl.add(Chain([(P(X(0.0), 1.17, az - 0.002), 0.037), (P(X(0.002), 1.115, az + 0.006), 0.038),
                      (P(X(0.0), 1.05, az + 0.003), 0.0335)]), T, 0.02)
        cl.add(CappedCone(P(X(0.0), 1.06, az + 0.003), P(X(0.0), 0.997, az + 0.002), 0.0335, 0.031), T, 0.01)
        # Folds: bunching inside the elbow, a couple of loose creases on the forearm.
        cl.shag(Ellipsoid(P(X(0.0), 1.175, az + 0.03), (0.05, 0.05, 0.03)), 0.0045,
                Creases(150.0, ax, az, seed=sx), soft=0.02)
        cl.shag(Ellipsoid(P(X(0.0), 1.06, az), (0.05, 0.05, 0.05)), 0.0025, Creases(110.0, ax, az, 1.0 + sx), soft=0.02)
        cl.shag(Ellipsoid(P(X(0.0), 1.36, az), (0.06, 0.09, 0.06)), 0.002, Creases(70.0, ax, az, 2.0), soft=0.03)
        cuff = PBody(h=0.0016, budget=80)
        cuff.add(CappedCone(P(X(0.0), 1.012, az + 0.002), P(X(0.0), 0.997, az + 0.002), 0.035, 0.0335), TRIM)
        extra.append(cuff)
        # Wrist out of the cuff.
        sk.add(Squash(Cone(P(0, 1.03, 0), P(0, 0.975, 0), 0.0205, 0.02), P(X(0.002), 0, az + 0.006), (1.0, 1.0, 1.25)),
               SKIN)
    else:
        cl.add(Chain(upper + [(P(X(0.0), 1.218, az), 0.0385)]), T, 0.025)
        cl.add(CappedCone(P(X(0.0), 1.25, az), P(X(0.0), 1.214, az), 0.039, 0.0395), T, 0.01)
        cl.shag(Ellipsoid(P(X(0.0), 1.36, az), (0.06, 0.09, 0.06)), 0.002, Creases(70.0, ax, az, 2.0), soft=0.03)
        # Rolled-up sleeve: a soft doubled roll at the hem.
        roll = PBody(h=0.0016, budget=110)
        roll.add(ring([(P(ax + 0.0415 * math.sin(a), 1.224, az + 0.0425 * math.cos(a)), 0.0085)
                       for a in np.linspace(0, 2 * math.pi, 18, endpoint=False)]), T)
        roll.add(ring([(P(ax + 0.0405 * math.sin(a), 1.212, az + 0.0415 * math.cos(a)), 0.0065)
                       for a in np.linspace(0, 2 * math.pi, 18, endpoint=False)]), T, 0.004)
        roll.shag(Sphere(P(ax, 1.22, az), 0.07), 0.002, Tufts(160, (1, 0, 0), seed=3 + sx), soft=0.02)
        extra.append(roll)
        # Bare forearm: elbow, a muscular upper forearm tapering to a flat wrist.
        sk.add(Chain([(P(X(0.0), 1.245, az), 0.034), (P(X(0.0), 1.17, az - 0.002), 0.0355)]), SKIN)
        sk.add(Sphere(P(X(0.001), 1.168, az - 0.019), 0.019), SKIN, 0.012)  # olecranon
        sk.add(Ellipsoid(P(X(0.004), 1.118, az + 0.01), (0.036, 0.06, 0.035)), SKIN, 0.02)  # flexor / extensor mass
        sk.add(Ellipsoid(P(X(0.012), 1.13, az + 0.018), (0.022, 0.05, 0.02)), SKIN, 0.015)  # brachioradialis
        sk.add(Chain([(P(X(0.002), 1.15, az + 0.004), 0.033), (P(X(0.002), 1.06, az + 0.007), 0.026)]), SKIN, 0.02)
        sk.add(Squash(Cone(P(0, 1.06, 0), P(0, 0.975, 0), 0.022, 0.0205), P(X(0.002), 0, az + 0.006), (1.0, 1.0, 1.28)),
               SKIN, 0.02)
        sk.add(Sphere(P(X(0.014), 1.0, az - 0.012), 0.0065), SKIN, 0.006)  # wrist bone
    fist(sk, sx, ax, 0.92, az)
    return cl, sk, extra


def arm_weather(p, n, reg):
    # Ruddy knuckles / backs of the hands; grime on the sleeve ends.
    hand = ss(0.98, 0.93, p[:, 1]) * (reg == SKIN) * 0.45
    cuff = ss(1.03, 1.0, p[:, 1]) * (reg != SKIN) * 0.4
    return hand + cuff


def piece_arm(sx, sleeve):
    side = "l" if sx < 0 else "r"
    pc = Piece(f"hu_arm_{'sleeve' if sleeve else 'bare'}_{side}", f"arm_{side}")
    cl, sk, extra = arm_bodies(sx, sleeve)
    pc.add(cl)
    pc.add(sk)
    for e in extra:
        pc.add(e)
    pc.weather = arm_weather
    return pc


# ───────────────────────────────────────────────────────────────── legs + feet
def leg_bodies(sx, desert):
    x0 = sx * HDX
    X = lambda d: x0 + sx * d  # noqa: E731
    bodies = []
    tr = PBody(h=0.0026, budget=270 if not desert else 240)
    loose = 0.006 if desert else 0.0
    # Thigh (trousers): wide at the hip, a quadriceps front and a hamstring back, tapering to the knee.
    # (The femur angles in from the hip, so the thigh top sits a little medial of the joint.)
    tr.add(Chain([(P(X(-0.016), 1.05, -0.006), 0.054 + loose), (P(X(-0.01), 0.95, 0.0), 0.06 + loose),
                  (P(X(-0.005), 0.82, 0.006), 0.057 + loose), (P(X(0.0), 0.68, 0.006), 0.049 + loose),
                  (P(X(0.0), 0.62, 0.004), 0.046 + loose)]), TROUSER)
    tr.add(Ellipsoid(P(X(-0.004), 0.79, 0.024), (0.046, 0.12, 0.038)), TROUSER, 0.03)  # quadriceps
    tr.add(Ellipsoid(P(X(0.008), 0.82, 0.0), (0.04, 0.085, 0.046)), TROUSER, 0.03)  # vastus lateralis
    tr.add(Ellipsoid(P(X(-0.022), 0.69, 0.012), (0.028, 0.055, 0.03)), TROUSER, 0.025)  # vastus medialis
    tr.add(Ellipsoid(P(X(-0.004), 0.8, -0.022), (0.048, 0.11, 0.036)), TROUSER, 0.03)  # hamstrings
    # Knee: joint mass + kneecap.
    tr.add(Sphere(P(X(0.0), 0.6, 0.0), 0.045 + loose * 0.6), TROUSER, 0.025)
    tr.add(Ellipsoid(P(X(0.0), 0.597, 0.034), (0.024, 0.029, 0.016)), TROUSER, 0.012)
    # Shin + calf.
    shin_end, r_end = (0.42, 0.04) if desert else (0.335, 0.038)
    tr.add(Chain([(P(X(0.0), 0.6, 0.0), 0.044 + loose), (P(X(0.0), 0.5, -0.004), 0.042 + loose),
                  (P(X(0.0), shin_end, 0.0), r_end + loose)]), TROUSER, 0.02)
    tr.add(Ellipsoid(P(X(0.008), 0.485, -0.022), (0.04, 0.075, 0.038)), TROUSER, 0.03)  # calf, outer head
    tr.add(Ellipsoid(P(X(-0.01), 0.465, -0.02), (0.036, 0.075, 0.036)), TROUSER, 0.03)  # calf, inner head (lower)
    # Cloth: creases behind the knee and a few long drape lines on the thigh.
    tr.shag(Ellipsoid(P(X(0.0), 0.6, -0.04), (0.06, 0.05, 0.04)), 0.004, Creases(170.0, x0, 0.0, sx), soft=0.02)
    tr.shag(Ellipsoid(P(X(0.0), 0.8, 0.0), (0.08, 0.17, 0.08)), 0.0025, Folds(5, 1.3 + sx, 0.97, 0.7, x0, 0.0), soft=0.03)
    bodies.append(tr)
    if not desert:
        bt = PBody(h=0.002, budget=260)
        bt.add(Chain([(P(X(0.0), 0.375, 0.0), 0.0445), (P(X(0.0), 0.3, 0.002), 0.0405), (P(X(0.0), 0.2, 0.0), 0.0355),
                      (P(X(0.0), 0.14, -0.006), 0.0375)]), BOOT)
        bt.add(Sphere(P(X(0.0), 0.105, -0.034), 0.04), BOOT, 0.02)  # heel
        bt.add(Chain([(P(X(0.0), 0.11, -0.025), 0.041), (P(X(0.002), 0.098, 0.05), 0.043),
                      (P(X(0.0), 0.09, 0.115), 0.037), (P(X(-0.002), 0.088, 0.152), 0.03)]), BOOT, 0.02)
        bt.add(Ellipsoid(P(X(-0.002), 0.088, 0.128), (0.04, 0.03, 0.04)), BOOT, 0.015)  # toe box
        bt.add(Ellipsoid(P(X(0.0), 0.135, 0.065), (0.033, 0.03, 0.05), rot_x(0.5)), BOOT, 0.02)  # instep
        bt.cut(half(P(0, 0.064, 0), (0, 1, 0)))
        # Turned-down cuff, hollow at the top.
        bt.add(CappedCone(P(X(0.0), 0.392, 0.0), P(X(0.0), 0.35, 0.0), 0.049, 0.046), BOOT)
        bt.sub(CappedCone(P(X(0.0), 0.4, 0.0), P(X(0.0), 0.36, 0.0), 0.043, 0.041), BOOT, 0.002)
        bt.shag(Ellipsoid(P(X(0.0), 0.24, 0.0), (0.06, 0.08, 0.06)), 0.003, Creases(120.0, x0, 0.0, 2 + sx), soft=0.02)
        bodies.append(bt)
        sole = PBody(h=0.0018, budget=90, clip=((-0.3, 0.05, -0.2), (0.3, 0.085, 0.3)))
        sole.add(offset(bt, 0.0035), LEATHER).cut(slab((0, 1, 0), 0.06, 0.074))
        bodies.append((sole, bt.eval))
    else:
        wr = PBody(h=0.0018, budget=170)
        wr.add(Chain([(P(X(0.0), 0.45, 0.0), 0.0515), (P(X(0.0), 0.3, 0.002), 0.0405), (P(X(0.0), 0.2, 0.0), 0.0325),
                      (P(X(0.0), 0.165, -0.004), 0.031)]), BAND)
        wr.add(ring([(P(x0 + 0.052 * math.sin(a), 0.452, 0.052 * math.cos(a)), 0.006)
                     for a in np.linspace(0, 2 * math.pi, 20, endpoint=False)]), BAND, 0.004)
        wr.add(Ellipsoid(P(X(0.004), 0.46, -0.016), (0.042, 0.06, 0.035)), BAND, 0.02)
        # Spiral wrap edges.
        knots = []
        for i in range(60):
            t = i / 59
            yy = 0.43 - t * 0.26
            a = t * 2 * math.pi * 5.0
            rr = 0.0502 - t * 0.0175
            knots.append((P(x0 + rr * math.sin(a), yy - 0.008 * math.cos(a), rr * math.cos(a)), 0.0035))
        wr.add(Chain(knots), BAND, 0.003)
        bodies.append(wr)
        ft = PBody(h=0.0016, budget=185)
        ft.add(Chain([(P(X(0.0), 0.18, -0.004), 0.029), (P(X(0.0), 0.13, -0.012), 0.031)]), SKIN)
        for d in (-1, 1):
            ft.add(Sphere(P(X(0.022 * d), 0.135, -0.008 + 0.006 * d), 0.011), SKIN, 0.01)  # ankle bones
        ft.add(Sphere(P(X(0.0), 0.1, -0.032), 0.034), SKIN, 0.02)  # heel
        ft.add(Chain([(P(X(0.0), 0.1, -0.02), 0.035), (P(X(0.004), 0.092, 0.05), 0.033),
                      (P(X(0.002), 0.082, 0.1), 0.028)]), SKIN, 0.02)
        ft.add(Ellipsoid(P(X(0.0), 0.11, 0.05), (0.03, 0.026, 0.05), rot_x(0.35)), SKIN, 0.02)
        # Toes: big toe medial, four small ones.
        tz = [(-0.018, 0.0105, 0.155), (-0.002, 0.0078, 0.15), (0.01, 0.0074, 0.145), (0.02, 0.0068, 0.137),
              (0.029, 0.0062, 0.127)]
        for dx, r, z in tz:
            ft.add(Chain([(P(X(dx * 0.8), 0.08, z - 0.035), r * 1.1), (P(X(dx), 0.077, z), r)]), SKIN, 0.006)
        ft.cut(half(P(0, 0.07, 0), (0, 1, 0)))
        bodies.append(ft)
        sd = PBody(h=0.0018, budget=110)
        sd.add(Squash(CappedCone(P(0, 0.074, 0), P(0, 0.06, 0), 0.05, 0.05), P(X(0.004), 0, 0.06), (1.0, 1.0, 2.5)), LEATHER)
        # Straps: across the toes, round the ankle and down the instep.
        sfn = ft.eval
        org = [[X(0.0) + 0.1 * math.sin(a), 0.098, 0.1 + 0.1 * math.cos(a)] for a in np.linspace(-1.4, 1.4, 9)]
        pts = hit(sfn, org, [[-math.sin(a), 0, -math.cos(a)] for a in np.linspace(-1.4, 1.4, 9)], t1=0.12)
        sd.add(Chain([(P(*q), 0.0045) for q in pts]), BAND, 0.002)
        sd.add(ring(surface_ring(sfn, X(0.0), -0.01, lambda a: 0.145, rad=0.1, n=18, tube=0.0045)), BAND, 0.002)
        bodies.append(sd)
    return bodies


def leg_weather(p, n, reg):
    y = p[:, 1]
    knee = np.exp(-((y - 0.6) / 0.05) ** 2) * ss(-0.02, 0.03, p[:, 2]) * 0.55  # worn knees
    dust = ss(0.3, 0.07, y) * 0.65
    return knee + dust


def piece_leg(sx, desert):
    side = "l" if sx < 0 else "r"
    pc = Piece(f"hu_leg_{'wrap_' if desert else ''}{side}", f"leg_{side}")
    for b in leg_bodies(sx, desert):
        if isinstance(b, tuple):
            pc.add(b[0], cull=b[1], depth=0.002)
        else:
            pc.add(b)
    pc.weather = leg_weather
    return pc


# ───────────────────────────────────────────────────────────────── heads
# Head-local frame: the head pivot (level with the ears) at the origin, face toward +Z, unscaled.
def skull(b):
    """Elements every face shares above the brow (the hair / headgear reference surface)."""
    b.add(Ellipsoid(P(0, 0.07, -0.016), (0.073, 0.087, 0.094)), SKIN)  # cranium
    b.add(Ellipsoid(P(0, 0.058, 0.026), (0.064, 0.064, 0.064)), SKIN, 0.03)  # forehead / upper face
    b.add(Ellipsoid(P(0, -0.012, -0.048), (0.05, 0.05, 0.046)), SKIN, 0.03)  # occiput -> nape


def scalp_body():
    b = PBody(h=0.002, budget=0)
    skull(b)
    return b


FACES = {
    "a": dict(w=1.0, jaw=1.0, nose=1.0, eye=1.0, chin=1.0, lip=1.0, cheek=1.0, brow=1.0),
    "b": dict(w=1.05, jaw=1.14, nose=1.14, eye=0.95, chin=1.12, lip=1.05, cheek=1.12, brow=1.15),
    "c": dict(w=0.95, jaw=0.88, nose=0.92, eye=1.04, chin=0.9, lip=0.95, cheek=0.9, brow=0.9, hook=1.0),
    # A child: a rounder, softer face — small snub nose, small jaw and chin, big eyes, full cheeks,
    # no brow ridge.
    "kid": dict(w=1.04, jaw=0.74, nose=0.6, eye=1.28, chin=0.74, lip=0.86, cheek=1.32, brow=0.5, kid=True),
    # A woman: finer jaw and nose, fuller lips, a smooth brow, no larynx.
    "w": dict(w=0.96, jaw=0.86, nose=0.84, eye=1.1, chin=0.88, lip=1.1, cheek=1.06, brow=0.55, soft=True),
}


def ear(b, sx, w):
    c = P(sx * 0.071 * w, 0.028, -0.012)
    R = rot_y(sx * 0.42) @ rot_x(0.16)
    b.add(Ellipsoid(c, (0.0072, 0.03, 0.019), R), SKIN, 0.008)  # pinna
    b.sub(Ellipsoid(c + P(sx * 0.006, 0.002, 0.001), (0.004, 0.017, 0.011), R), SKIN, 0.004)  # concha bowl
    b.add(ring([(c + R @ P(sx * 0.003, 0.028 * math.cos(a), 0.017 * math.sin(a)), 0.003)
                for a in np.linspace(-0.3, 3.5, 12)], closed=False), SKIN, 0.003)  # helix rim
    b.add(Sphere(c + P(sx * 0.001, -0.025, 0.004), 0.0062), SKIN, 0.004)  # lobe


def face(b, f):
    """Everything below the brow: brow ridge, eye sockets + lids, cheekbones, nose, mouth, jaw,
    chin, ears and the neck. Proportions vary by face shape."""
    w, j, n, ch = f["w"], f["jaw"], f["nose"], f["chin"]
    kid = f.get("kid", False)
    S = SKIN
    br = f["brow"]
    b.add(Cone(P(-0.034 * w, 0.06, 0.078), P(0.034 * w, 0.06, 0.078), 0.012 * br, 0.012 * br), S, 0.018)  # brow ridge
    b.add(Ellipsoid(P(0, 0.008, 0.046), (0.054 * w, 0.05, 0.05)), S, 0.025)  # maxilla / midface
    for sx in (-1, 1):
        b.add(Ellipsoid(P(sx * 0.046 * w, 0.026, 0.058), np.array((0.021, 0.013, 0.019)) * f["cheek"]), S, 0.02)
        b.add(Ellipsoid(P(sx * 0.038 * w, 0.0, 0.058), np.array((0.024, 0.024, 0.02)) * (1.15 if kid else 1.0)), S, 0.025)
    # Mandible: angle -> chin -> angle, the rami up to the ears.
    gx, gy, gz = 0.05 * w * j, -0.03, 0.004
    b.add(Chain([(P(-gx, gy, gz), 0.016 * j), (P(-0.032 * w * j, -0.044, 0.056), 0.017),
                 (P(0, -0.047, 0.076), 0.018 * ch), (P(0.032 * w * j, -0.044, 0.056), 0.017),
                 (P(gx, gy, gz), 0.016 * j)]), S, 0.022)
    for sx in (-1, 1):
        b.add(Cone(P(sx * gx, gy, gz), P(sx * 0.058 * w, 0.018, -0.006), 0.014, 0.012), S, 0.02)
    b.add(Sphere(P(0, -0.041, 0.081 + 0.004 * (ch - 1)), 0.015 * ch), S, 0.012)  # chin pad
    b.add(Ellipsoid(P(0, -0.016, 0.079), (0.029, 0.026, 0.021)), S, 0.016)  # muzzle (teeth)
    # Lips + mouth line + philtrum.
    lp = f["lip"]
    b.add(Ellipsoid(P(0, -0.0168, 0.0965), (0.0185 * lp, 0.0058, 0.0078), rot_x(-0.25)), LIP, 0.004)
    b.add(Ellipsoid(P(0, -0.0272, 0.0935), (0.0162 * lp, 0.0066, 0.0078), rot_x(0.25)), LIP, 0.004)
    b.sub(Ellipsoid(P(0, -0.0222, 0.103), (0.0185 * lp, 0.0011, 0.0072)), LIP, 0.0015)
    b.sub(Ellipsoid(P(0, -0.008, 0.1), (0.0035, 0.006, 0.002)), S, 0.002)  # philtrum
    b.sub(Ellipsoid(P(0, -0.036, 0.094), (0.012, 0.0035, 0.004)), S, 0.004)  # under-lip groove
    # Nose: bridge -> tip, alae, nostrils.
    hook = f.get("hook", 0.0)
    b.add(Cone(P(0, 0.05, 0.087), P(0, 0.008, 0.106 + 0.006 * n + 0.002 * hook), 0.0072 * n, 0.0092 * n), S, 0.008)
    b.add(Sphere(P(0, 0.023, 0.099 + 0.004 * hook), 0.0075 * n), S, 0.006)  # dorsum hump (hook nose)
    b.add(Sphere(P(0, 0.0015, 0.105 + 0.006 * n), 0.0105 * n), S, 0.006)  # tip
    for sx in (-1, 1):
        b.add(Sphere(P(sx * 0.0122 * n, -0.002, 0.0955), 0.0082 * n), S, 0.006)  # alae
        b.sub(Ellipsoid(P(sx * 0.0068 * n, -0.0085, 0.1015), (0.0038, 0.0024, 0.0045)), S, 0.002)  # nostrils
    # Eye sockets under the brow; the eyeball and lids go in (`eyes`).
    e = f["eye"]
    for sx in (-1, 1):
        b.sub(Ellipsoid(P(sx * 0.0305, 0.042, 0.088), (0.0185 * e, 0.0115 * e, 0.015)), S, 0.008)
    for sx in (-1, 1):
        ear(b, sx, w)
    # Neck: from under the skull down into the tunic collar; a throat in front.
    b.add(Cone(P(0, -0.022, -0.026), P(0, -0.135, -0.014), 0.043, 0.049), S, 0.02)
    b.add(Cone(P(0, -0.052, 0.024), P(0, -0.128, 0.026), 0.022, 0.024), S, 0.02)
    if not kid and not f.get("soft"):
        b.add(Sphere(P(0, -0.07, 0.042), 0.0085), S, 0.008)  # larynx
        for sx in (-1, 1):  # sternocleidomastoids
            b.add(Cone(P(sx * 0.045, -0.02, -0.006), P(sx * 0.012, -0.13, 0.04), 0.011, 0.011), S, 0.012)


def eyes_body(f):
    e = f["eye"]
    b = PBody(h=0.0011, budget=120)
    for sx in (-1, 1):
        b.add(Sphere(P(sx * 0.0305, 0.0415, 0.0705), 0.0118 * e), EYE)
    return b


def lids_body(f, headb):
    """Upper / lower lids over the eyeballs and the brows (HAIR), snapped onto the face."""
    e = f["eye"]
    b = PBody(h=0.0011, budget=100)
    for sx in (-1, 1):
        cx = sx * 0.0305
        b.add(Ellipsoid(P(cx, 0.0499, 0.0742), (0.0152 * e, 0.0054 * e, 0.0108 * e), rot_x(-0.35)), SKIN)  # upper lid
        b.add(Ellipsoid(P(cx, 0.0338, 0.0748), (0.0138 * e, 0.0036 * e, 0.0096 * e), rot_x(0.3)), SKIN, 0.002)  # lower lid
    brows = PBody(h=0.0011, budget=80)
    for sx in (-1, 1):
        xs = [sx * 0.012, sx * 0.025, sx * 0.038, sx * 0.047]
        ys = [0.058, 0.062, 0.062, 0.057]
        pts = hit(headb.eval, [[x, y, 0.2] for x, y in zip(xs, ys)], [[0, 0, -1]] * 4, t1=0.2)
        rs = [0.0042, 0.0045, 0.004, 0.003]
        brows.add(Chain([(P(q[0], q[1], q[2] - 0.0012), r * f["brow"] ** 0.5) for q, r in zip(pts, rs)]), HAIR)
    return b, brows


def head_weather(p, n, reg, eye=1.0):
    """Ruddy cheeks, nose tip and ear rims (skin); on the eyeballs (the EYE region is the dark
    iris) the WHITES: the corners away from each gaze axis, which the game lightens to off-white."""
    cheek = sum(np.exp(-(((p[:, 0] - sx * 0.042) ** 2 + (p[:, 1] - 0.012) ** 2 + (p[:, 2] - 0.07) ** 2) / 0.00045))
                for sx in (-1, 1))
    nose = np.exp(-((p[:, 0] ** 2 + (p[:, 1] - 0.004) ** 2 + (p[:, 2] - 0.11) ** 2) / 0.00012))
    ears = ss(0.06, 0.075, np.abs(p[:, 0])) * ss(-0.03, 0.0, p[:, 1])
    skin = (cheek * 0.5 + nose * 0.55 + ears * 0.35) * (reg == SKIN)
    r = 0.0118 * eye
    white = np.zeros(len(p))
    for sx in (-1, 1):
        cx = sx * 0.0305 - sx * 0.0012  # the gaze converges a touch
        d = np.sqrt((p[:, 0] - cx) ** 2 + (p[:, 1] - 0.0415) ** 2)
        near = np.abs(p[:, 0] - sx * 0.0305) < 1.2 * r
        white = np.maximum(white, ss(0.5 * r, 0.82 * r, d) * near)
    return skin + white * (reg == EYE)


_HEADS = {}


def head_body(variant):
    if variant not in _HEADS:
        f = FACES[variant]
        b = PBody(h=0.0014, budget=880 if variant != "kid" else 800)
        skull(b)
        face(b, f)
        _HEADS[variant] = b
    return _HEADS[variant]


def piece_head(variant):
    f = FACES[variant]
    pc = Piece(f"hu_head_{variant}", "head", "head")
    hb = head_body(variant)
    pc.add(hb)
    pc.add(eyes_body(f))
    lids, brows = lids_body(f, hb)
    pc.add(lids)
    pc.add(brows)
    pc.weather = lambda p, n, reg: head_weather(p, n, reg, f["eye"])  # noqa: E731
    return pc


# ───────────────────────────────────────────────────────────────── hair + beards
def hairline(front_y, nape_y):
    """Keep above a plane from the forehead hairline (0, front_y, 0.09) to the nape (0, nape_y, -0.11)."""
    a = np.array([0, front_y, 0.09])
    bb = np.array([0, nape_y, -0.11])
    d = (bb - a) / np.linalg.norm(bb - a)
    no = np.array([0, -d[2], d[1]])
    if no[1] < 0:
        no = -no
    return half(a, no)


def ears_clear(b, w=1.0):
    for sx in (-1, 1):
        b.sub(Ellipsoid(P(sx * 0.074 * w, 0.028, -0.012), (0.016, 0.034, 0.024)), HAIR, 0.006)


def piece_hair(style):
    pc = Piece(f"hu_hair_{style}", "head", "head")
    sc = scalp_body()
    b = PBody(h=0.0016, budget=260 if style in ("crop", "bald", "bowl") else 360)
    b.sym = style != "shag"  # (the shag's fringe falls to one side)
    if style == "crop":
        b.add(offset(sc, 0.0055), HAIR).cut(hairline(0.104, -0.012))
        ears_clear(b)
        b.shag(Sphere(P(0, 0.07, -0.01), 0.14), 0.0022, Tufts(260, (0, -0.4, -1), seed=1), soft=0.02)
    elif style == "shag":
        b.add(offset(sc, 0.01), HAIR).cut(hairline(0.094, -0.05))
        for sx in (-1, 1):
            b.add(Ellipsoid(P(sx * 0.064, 0.03, -0.044), (0.022, 0.045, 0.044)), HAIR, 0.02)  # over the ears
        b.add(Ellipsoid(P(0, 0.0, -0.08), (0.058, 0.048, 0.03)), HAIR, 0.02)  # nape
        b.add(Ellipsoid(P(0.012, 0.11, 0.076), (0.054, 0.017, 0.022), rot_z(0.12)), HAIR, 0.015)  # fringe
        b.shag(Sphere(P(0, 0.06, -0.01), 0.16), 0.0055, Tufts(150, (0, -1, -0.3), seed=2), soft=0.02)
    elif style == "long":
        b.add(offset(sc, 0.008), HAIR).cut(hairline(0.106, -0.02))
        b.add(Ellipsoid(P(0, -0.02, -0.088), (0.064, 0.105, 0.032)), HAIR, 0.025)  # falls to the shoulders
        for sx in (-1, 1):
            b.add(Ellipsoid(P(sx * 0.07, 0.02, -0.04), (0.019, 0.07, 0.034)), HAIR, 0.02)
        b.add(Cone(P(0, -0.1, -0.1), P(0, -0.19, -0.094), 0.019, 0.014), HAIR, 0.012)  # tied tail
        b.add(Ellipsoid(P(0, -0.098, -0.1), (0.022, 0.01, 0.022)), BAND, 0.003)  # tie
        b.shag(Sphere(P(0, 0.0, -0.04), 0.2), 0.0045, Tufts(140, (0, -1, 0), seed=3), soft=0.02)
    elif style == "bald":
        b.add(offset(sc, 0.0055), HAIR).cut(hairline(0.09, -0.012)).cut(half(P(0, 0.11, -0.03), (0, -1, -0.45)))
        ears_clear(b)
        b.shag(Sphere(P(0, 0.05, -0.04), 0.14), 0.0025, Tufts(240, (0, -1, -0.3), seed=4), soft=0.02)
    elif style == "bowl":
        b.add(offset(sc, 0.013), HAIR).cut(hairline(0.08, 0.008))
        ears_clear(b)
        b.shag(Sphere(P(0, 0.08, 0.0), 0.14), 0.003, Tufts(200, (0, -1, 0.1), seed=5), soft=0.02)
    pc.add(b)
    return pc


def piece_beard(style, fv):
    """Beards are the face pushed out (`offset`) and SMOOTHLY clipped by a rounded zone along the
    jaw (sideburns -> jaw -> chin), so the edges feather instead of ending on hard planes; the
    mouth, nose and ears are carved clear, clumps come from directional tufts. Every style has a
    moustache snapped onto the upper lip."""
    pc = Piece(f"hu_beard_{style}_{fv}", "head", "head")
    f = FACES[fv]
    w, jw = f["w"], f["jaw"]
    hb = head_body(fv)
    b = PBody(h=0.0013, budget=230 if style == "full" else 190 if style == "short" else 110,
              clip=((-0.1, -0.11, -0.04), (0.1, 0.05, 0.14)))
    if style in ("full", "short"):
        full = style == "full"
        t = 0.0105 if full else 0.0042
        r = 0.032 if full else 0.025
        zone = []
        for sx in (-1, 1):
            zone.append([(P(sx * 0.061 * w, 0.03, -0.008), r * 0.45), (P(sx * 0.056 * w * jw, -0.008, 0.012), r * 0.8),
                         (P(sx * 0.046 * w * jw, -0.034, 0.04), r), (P(sx * 0.026 * w, -0.05, 0.07), r)])
        mask = Chain(zone[0] + [(P(0, -0.054, 0.08), r * 1.05)] + zone[1][::-1])
        b.add(offset(hb, t), HAIR)
        b.cut(mask, 0.009)
        b.sub(Ellipsoid(P(0, -0.0225, 0.1), (0.0175, 0.0085, 0.03)), HAIR, 0.005)  # mouth
        b.sub(Ellipsoid(P(0, 0.006, 0.106), (0.021, 0.018, 0.026)), HAIR, 0.005)  # nose
        for sx in (-1, 1):
            b.sub(Ellipsoid(P(sx * 0.074 * w, 0.028, -0.012), (0.014, 0.032, 0.022)), HAIR, 0.005)  # ears
        if full:
            b.add(Ellipsoid(P(0, -0.064, 0.074), (0.03, 0.03, 0.024)), HAIR, 0.016)  # chin tuft
        b.shag(Sphere(P(0, -0.03, 0.05), 0.12), 0.0042 if full else 0.0014, Tufts(220, (0, -1, 0.2), seed=6), soft=0.02)
    # Moustache over the upper lip (every style).
    pts = hit(hb.eval, [[x, y, 0.2] for x, y in ((-0.026, -0.016), (-0.012, -0.011), (0.0, -0.011), (0.012, -0.011),
                                                  (0.026, -0.016))], [[0, 0, -1]] * 5, t1=0.2)
    if style == "moustache":
        rs = [0.0045, 0.0068, 0.0058, 0.0068, 0.0045]
        b.add(Chain([(P(q[0], q[1], q[2] + 0.001), r) for q, r in zip(pts, rs)]), HAIR)
        for sx in (-1, 1):
            q = hit(hb.eval, [[sx * 0.03, -0.032, 0.2]], [[0, 0, -1]], t1=0.2)[0]
            b.add(Cone(P(*pts[0 if sx < 0 else 4]), P(q[0], q[1], q[2] + 0.001), 0.0045, 0.0032), HAIR, 0.003)
    else:
        rs = [0.004, 0.0058, 0.005, 0.0058, 0.004]
        b.add(Chain([(P(q[0], q[1], q[2] + 0.0008), r) for q, r in zip(pts, rs)]), HAIR, 0.004)
    pc.add(b)
    return pc


# ───────────────────────────────────────────────────────────────── headgear
def piece_hat(kind):
    pc = Piece(f"hu_hat_{kind}", "head", "head")
    sc = scalp_body()
    if kind == "hood":
        # Cloth hood: a shell of the skull, a smooth cowl draping round the neck onto the shoulders
        # (one tapered skirt, no lumps at the throat), the face opening carved as an oval.
        b = PBody(h=0.002, budget=360)
        b.add(offset(sc, 0.021), HEADCLOTH)
        b.add(Squash(CappedCone(P(0, -0.03, 0), P(0, -0.15, 0), 0.082, 0.128), P(0, 0, -0.012), (1, 1, 0.9)),
              HEADCLOTH, 0.035)
        b.add(Cone(P(0, 0.11, -0.085), P(0, 0.02, -0.15), 0.03, 0.012), HEADCLOTH, 0.02)  # the hood's point
        b.sub(Ellipsoid(P(0, 0.018, 0.105), (0.062, 0.088, 0.075)), HEADCLOTH, 0.012)  # face opening
        b.shag(Ellipsoid(P(0, -0.1, 0.0), (0.15, 0.06, 0.14)), 0.005, Folds(11, 0.4, -0.05, -0.14), soft=0.03)
        pc.add(b)
        rim = PBody(h=0.0016, budget=100)
        knots = []
        for a in np.linspace(0, 2 * math.pi, 26, endpoint=False):
            q = P(0.062 * math.sin(a) * 1.03, 0.018 + 0.088 * math.cos(a) * 1.0, 0.0)
            q[2] = hit(b.eval, [[q[0], q[1], 0.25]], [[0, 0, -1]], t1=0.25)[0][2]
            knots.append((q + P(0, 0, -0.002), 0.0045))
        rim.add(ring(knots), HEADCLOTH)
        pc.add(rim)
    elif kind == "cap":
        # Felt cap pulled over the crown with a slouched top and a rolled brim.
        b = PBody(h=0.0018, budget=260)
        b.sym = False  # slouched top
        b.add(offset(sc, 0.011), HEADCLOTH).cut(half(P(0, 0.083, 0), (0, 1, 0.22)))
        b.add(Ellipsoid(P(0.016, 0.155, -0.04), (0.05, 0.035, 0.06), rot_z(-0.4)), HEADCLOTH, 0.03)
        pc.add(b)
        br = PBody(h=0.0016, budget=110)
        br.add(layer(sc, -0.01, 0.017), BAND).cut(slab((0, 1, 0.22), 0.077, 0.097))
        pc.add(br)
    elif kind == "straw":
        b = PBody(h=0.002, budget=330)
        b.add(offset(sc, 0.024), HEADCLOTH).cut(half(P(0, 0.1, 0), (0, 1, 0)))
        b.add(Ellipsoid(P(0, 0.152, -0.012), (0.07, 0.05, 0.084)), HEADCLOTH, 0.02)  # raised crown
        b.sub(Ellipsoid(P(0, 0.2, -0.012), (0.03, 0.012, 0.05)), HEADCLOTH, 0.012)  # crown dent
        # Wide brim drooping at front and back.
        b.add(Fn(lambda p: np.maximum(np.sqrt((p[:, 0] / 1.0) ** 2 + ((p[:, 2] + 0.012) / 0.97) ** 2) - 0.185,
                                      np.abs(p[:, 1] - (0.108 - 0.6 * (p[:, 2] + 0.012) ** 2 - 0.25 * p[:, 0] ** 2)) - 0.004),
                 (-0.2, 0.05, -0.21), (0.2, 0.13, 0.19)), HEADCLOTH, 0.01)
        b.shag(Fn(lambda p: np.abs(np.sqrt(p[:, 0] ** 2 + (p[:, 2] + 0.012) ** 2) - 0.14) - 0.05, (-1,) * 3, (1,) * 3),
               0.0018, Tufts(300, (1, 0, 0), seed=7), soft=0.01)
        pc.add(b)
        band = PBody(h=0.0016, budget=100)
        band.add(layer(sc, -0.01, 0.028), BAND).cut(slab((0, 1, 0), 0.112, 0.13))
        pc.add(band)
    elif kind == "miner":
        b = PBody(h=0.0018, budget=290)
        b.add(offset(sc, 0.015), METAL).cut(half(P(0, 0.086, 0), (0, 1, 0)))
        b.add(Ellipsoid(P(0, 0.15, -0.012), (0.06, 0.04, 0.075)), METAL, 0.02)
        b.add(Squash(CappedCone(P(0, 0.093, 0), P(0, 0.083, 0), 0.098, 0.098), P(0, 0, 0.0), (1.0, 1.0, 1.265)), METAL, 0.006)
        b.add(ring([(P(0.098 * math.sin(a), 0.088, 0.124 * math.cos(a)), 0.0055) for a in np.linspace(0, 2 * math.pi, 28, endpoint=False)]),
              METAL, 0.003)  # rolled brim edge
        pc.add(b)
        q = hit(b.eval, [[0, 0.122, 0.3]], [[0, 0, -1]], t1=0.3)[0]
        lamp = PBody(h=0.0012, budget=110)
        lamp.add(CappedCone(P(0, 0.122, q[2] - 0.004), P(0, 0.124, q[2] + 0.016), 0.019, 0.021), LEATHER)
        lamp.add(CappedCone(P(0, 0.124, q[2] + 0.014), P(0, 0.124, q[2] + 0.019), 0.015, 0.015), FLETCH, 0.0)
        pc.add(lamp)
    elif kind == "helm":
        # Nasal helm: a steel dome with a rolled rim on the brow, a riveted band, nose guard and crest.
        b = PBody(h=0.0018, budget=300)
        b.add(offset(sc, 0.015), HELM).cut(half(P(0, 0.066, 0), (0, 1, -0.12)))
        b.add(Fn(lambda p: np.maximum(np.abs(p[:, 0]) - 0.004, offset(sc, 0.019).d(p)), (-0.01, 0.07, -0.13),
                 (0.01, 0.18, 0.11)), HELM, 0.004)  # crest ridge
        b.cut(half(P(0, 0.066, 0), (0, 1, -0.12)))
        pc.add(b)
        band = PBody(h=0.0016, budget=140)
        # The brow band, rounded top and bottom: the helm's rolled rim.
        band.add(layer(sc, -0.01, 0.021), METAL).cut(slab((0, 1, -0.12), 0.062, 0.084), 0.006)
        pc.add(band)
        nose = PBody(h=0.0012, budget=70)
        hb = head_body("a")
        top = hit(offset(hb, 0.004).d, [[0, 0.08, 0.3]], [[0, 0, -1]], t1=0.3)[0]
        bot = hit(offset(hb, 0.007).d, [[0, 0.028, 0.3]], [[0, 0, -1]], t1=0.3)[0]
        mid = (top + bot) / 2
        nose.add(Squash(Cone(top + P(0, 0.004, 0.0) - mid, bot - mid, 0.0068, 0.0058), mid, (1.25, 1.0, 0.7)), HELM)
        pc.add(nose)
    elif kind in ("archer", "headwrap"):
        # Close leather (archer) / cloth (desert) hood with a neck drape, a band and a feather.
        b = PBody(h=0.0018, budget=260)
        b.add(offset(sc, 0.012), HEADCLOTH)
        b.add(Squash(CappedCone(P(0, -0.02, -0.02), P(0, -0.12, -0.03), 0.07, 0.1), P(0, 0, 0), (1, 1, 0.85)),
              HEADCLOTH, 0.03)
        b.sub(Ellipsoid(P(0, 0.016, 0.1), (0.06, 0.082, 0.07)), HEADCLOTH, 0.01)
        b.cut(half(P(0, 0, 0.11), (0, 0, -1)))
        pc.add(b)
        band = PBody(h=0.0016, budget=110)
        band.add(layer(sc, -0.01, 0.0165), BAND).cut(slab((0, 1, 0.25), 0.082, 0.1))
        pc.add(band)
        fe = PBody(h=0.0012, budget=90)
        fe.sym = False
        fe.add(Cone(P(0.072, 0.11, -0.05), P(0.105, 0.23, -0.09), 0.0028, 0.0015), FLETCH)
        fe.add(Ellipsoid(P(0.094, 0.19, -0.076), (0.0035, 0.05, 0.014), rot_x(0.32) @ rot_z(-0.26)), FLETCH, 0.003)
        pc.add(fe)
    elif kind == "turban":
        b = PBody(h=0.0018, budget=330)
        b.sym = False  # the tuck knot
        b.add(offset(sc, 0.028), HEADCLOTH).cut(half(P(0, 0.064, 0), (0, 1, 0.22)))
        b.add(Ellipsoid(P(0, 0.162, -0.012), (0.074, 0.05, 0.088)), HEADCLOTH, 0.02)
        # Wound layers: tilted rolls round the head.
        for i, (y, tilt, r) in enumerate(((0.085, 0.22, 0.0105), (0.11, -0.12, 0.01), (0.135, 0.18, 0.0095))):
            n = np.array([0, 1, tilt])
            n /= np.linalg.norm(n)
            knots = surface_ring(offset(sc, 0.026).d, 0.0, -0.012, lambda a, y=y, t=tilt: y - t * 0.1 * math.cos(a),
                                 rad=0.2, n=28, tube=r, embed=0.002)
            b.add(ring(knots), HEADCLOTH, 0.006)
        b.add(Sphere(P(0.07, 0.15, -0.024), 0.03), HEADCLOTH, 0.01)  # tuck knot
        b.shag(Sphere(P(0, 0.12, 0), 0.15), 0.002, Tufts(220, (1, 0, 0), seed=8), soft=0.02)
        pc.add(b)
        band = PBody(h=0.0016, budget=100)
        band.add(layer(sc, -0.01, 0.034), BAND).cut(slab((0, 1, 0.22), 0.062, 0.078))
        pc.add(band)
        dr = PBody(h=0.002, budget=130)
        dr.add(Ellipsoid(P(0, -0.035, -0.083), (0.078, 0.095, 0.03)), CLOAK)
        dr.cut(half(P(0, 0.07, 0), (0, -1, 0)))
        dr.shag(Sphere(P(0, -0.04, -0.09), 0.12), 0.004, Folds(8, 0.2, 0.05, -0.12, 0.0, 0.0), soft=0.03)
        pc.add(dr, cull=sc.eval, depth=0.004)
    elif kind == "warhelm":
        # Saracen war-helm: a bronze cone over a turban band, a rolled rim, a neck drape.
        b = PBody(h=0.0018, budget=200)
        b.add(layer(sc, -0.01, 0.026), HEADCLOTH).cut(slab((0, 1, 0), 0.055, 0.115))
        pc.add(b)
        hm = PBody(h=0.0018, budget=180)
        hm.add(Cone(P(0, 0.105, -0.012), P(0, 0.27, -0.012), 0.086, 0.006), HELM)
        hm.add(Sphere(P(0, 0.275, -0.012), 0.009), HELM, 0.006)
        hm.cut(half(P(0, 0.1, 0), (0, 1, 0)))
        hm.add(ring([(P(0.088 * math.sin(a), 0.104, -0.012 + 0.098 * math.cos(a)), 0.006)
                     for a in np.linspace(0, 2 * math.pi, 28, endpoint=False)]), HELM, 0.003)
        pc.add(hm)
        dr = PBody(h=0.002, budget=130)
        dr.add(Ellipsoid(P(0, -0.035, -0.083), (0.078, 0.095, 0.03)), CLOAK)
        dr.cut(half(P(0, 0.07, 0), (0, -1, 0)))
        dr.shag(Sphere(P(0, -0.04, -0.09), 0.12), 0.004, Folds(8, 0.2, 0.05, -0.12, 0.0, 0.0), soft=0.03)
        pc.add(dr, cull=sc.eval, depth=0.004)
    return pc


# ───────────────────────────────────────────────────────────────── trade / faction add-ons
def piece_apron():
    """The farmer's apron: one panel from the chest to below the tunic hem, neck straps, waist ties.
    Its skirt half is weighted to the thighs like the tunic, so it parts in the stride."""
    pc = Piece("hu_apron", "trunk")
    tb = trunk()
    sk = skirt_long(0.72, 0.19)
    b = PBody(h=0.0026, budget=330, clip=((-0.14, 0.7, 0.0), (0.14, 1.4, 0.2)))
    b.add(offset(tb, 0.013), TABARD)
    b.add(offset(sk, 0.015), TABARD, 0.01)
    b.cut(half(P(0, 0, 0.045), (0, 0, 1))).cut(slab((1, 0, 0), -0.105, 0.105)).cut(slab((0, 1, 0), 0.72, 1.38))
    b.cut(Fn(lambda p: np.abs(p[:, 0]) - (0.105 - 0.03 * ss(1.15, 1.3, p[:, 1])), (-1,) * 3, (1,) * 3))  # bib narrower
    b.shag(Ellipsoid(P(0, 0.8, 0.1), (0.12, 0.1, 0.1)), 0.004, Folds(4, 0.3, 0.98, 0.74), soft=0.03)
    ref = lambda p: np.minimum(tb.eval(p), sk.eval(p))  # noqa: E731
    pc.add(b, cull=ref, depth=0.003)
    st = PBody(h=0.0018, budget=140)
    for sx in (-1, 1):
        # Neck straps from the bib corners up over the trapezius and down the back.
        pts = over_shoulder(tb, lambda ph, sx=sx: sx * (0.072 - 0.014 * min(1.0, max(0.0, ph / 1.6))),
                            np.linspace(-0.3, math.pi + 0.3, 13), lift=0.008)
        st.add(Chain([(q, 0.0055) for q in pts]), LEATHER, 0.003)
    # Waist ties at the back.
    z = hit(tb.eval, [[0, 1.088, -0.3]], [[0, 0, 1]], t1=0.3)[0][2]
    for sx in (-1, 1):
        st.add(Cone(P(0, 1.088, z - 0.012), P(sx * 0.03, 1.02, z - 0.022), 0.006, 0.004), TABARD, 0.003)
    st.add(Sphere(P(0, 1.088, z - 0.014), 0.011), TABARD, 0.003)
    pc.add(st)
    pc.weather = lambda p, n, reg: ss(0.9, 0.73, p[:, 1]) * 0.6 + 0.15  # noqa: E731
    return pc


def piece_guard():
    """The guard's breastplate + backplate (rolled bottom edge and neckline, a keel), the livery
    tabard over it front and back down to mid-thigh, shoulder straps and a sword belt."""
    pc = Piece("hu_guard", "trunk")
    tb = trunk()
    sk = skirt_long(0.7, 0.18)
    pl = PBody(h=0.0026, budget=300, clip=((-0.23, 1.08, -0.23), (0.23, 1.56, 0.23)))
    # Plate only where it shows: the flanks either side of the tabard (its centre is covered).
    pl.add(offset(tb, 0.01), METAL).cut(slab((0, 1, 0), 1.1, 1.47)).cut(armholes(0.128, 1.32, 1.43))
    pl.cut(Fn(lambda p: 0.06 - np.abs(p[:, 0]), (-BIG,) * 3, (BIG,) * 3))
    pc.add(pl, cull=tb.eval, depth=0.003)
    rims = PBody(h=0.0018, budget=100)
    plate = offset(tb, 0.01)
    rims.add(ring(surface_ring(plate.d, 0.0, -0.004, lambda a: 1.104, rad=0.3, n=32, tube=0.0052)), METAL)
    for a0 in (0.0, math.pi):  # rolled neckline on the flanks, front and back
        for sg in (-1, 1):
            angs = a0 + sg * np.linspace(0.45, 1.05, 5)
            org = [[0.3 * math.sin(a), 1.462, -0.004 + 0.3 * math.cos(a)] for a in angs]
            pts = hit(plate.d, org, [[-math.sin(a), 0, -math.cos(a)] for a in angs], t1=0.3)
            rims.add(Chain([(P(*q), 0.0048) for q in pts]), METAL, 0.002)
    pc.add(rims)
    tab = PBody(h=0.0026, budget=260, clip=((-0.1, 0.68, -0.2), (0.1, 1.5, 0.2)))
    tab.add(offset(tb, 0.021), TABARD)
    tab.add(offset(sk, 0.022), TABARD, 0.01)
    tab.cut(slab((1, 0, 0), -0.078, 0.078)).cut(slab((0, 1, 0), 0.7, 1.455))
    tab.shag(Ellipsoid(P(0, 0.8, 0.0), (0.1, 0.12, 0.2)), 0.0035, Folds(5, 0.9, 1.0, 0.72), soft=0.03)
    pc.add(tab, cull=lambda p: np.minimum(tb.eval(p), sk.eval(p)) - 0.013, depth=0.003)
    for sx in (-1, 1):  # shoulder straps buckling the plates together
        st = PBody(h=0.0018, budget=90)
        pts = over_shoulder(tb, lambda ph, sx=sx: sx * 0.098, np.linspace(0.2, math.pi - 0.2, 9), lift=0.016)
        st.add(Chain([(q, 0.0065) for q in pts]), LEATHER)
        pc.add(st)
    bt = PBody(h=0.0022, budget=110, clip=((-0.22, 1.06, -0.2), (0.22, 1.12, 0.2)))
    bt.add(layer(tb, -0.01, 0.024), LEATHER).cut(slab((0, 1, 0), 1.072, 1.098))
    pc.add(bt)
    pc.weather = lambda p, n, reg: ss(0.85, 0.7, p[:, 1]) * 0.5  # noqa: E731
    return pc


def piece_pauldron(sx):
    """A steel shoulder plate over the deltoid with a ROLLED rim and one lame below it."""
    side = "l" if sx < 0 else "r"
    pc = Piece(f"hu_pauldron_{side}", f"arm_{side}")
    cl, _, _ = arm_bodies(sx, True)
    ax, az = sx * SDX, 0.01
    b = PBody(h=0.0018, budget=170, clip=((ax - 0.09, 1.36, az - 0.09), (ax + 0.09, 1.56, az + 0.09)))
    b.add(offset(cl, 0.012), METAL)
    b.cut(Fn(lambda p: (1.405 + 0.06 * ss(0.17, 0.12, np.abs(p[:, 0]))) - p[:, 1], (-1,) * 3, (1,) * 3))
    b.cut(Fn(lambda p: 0.14 - np.abs(p[:, 0]), (-1,) * 3, (1,) * 3))
    pc.add(b, cull=cl.eval, depth=0.004)
    rim = PBody(h=0.0014, budget=100)
    knots = []
    for a in np.linspace(-0.6 * math.pi, 0.6 * math.pi, 19):
        # Round the outside of the arm (a = 0 lateral), following the plate's lower edge.
        dirx, dirz = sx * math.cos(a), math.sin(a)
        y = 1.405 + 0.06 * ss(0.17, 0.12, abs(ax + dirx * 0.05))
        q = hit(offset(cl, 0.012).d, [[ax + dirx * 0.2, y + 0.003, az + dirz * 0.2]], [[-dirx, 0, -dirz]], t1=0.2)[0]
        knots.append((P(*q) + P(dirx * 0.002, 0.0, dirz * 0.002), 0.0062))
    rim.add(Chain(knots), METAL)
    pc.add(rim)
    lame = PBody(h=0.0018, budget=90, clip=((ax - 0.09, 1.33, az - 0.09), (ax + 0.09, 1.42, az + 0.09)))
    lame.add(offset(cl, 0.009), METAL).cut(slab((0, 1, 0), 1.355, 1.395))
    lame.cut(Fn(lambda p: 0.16 - np.abs(p[:, 0]), (-1,) * 3, (1,) * 3))
    pc.add(lame, cull=cl.eval, depth=0.004)
    for a in (-0.5, 0.0, 0.5):
        dirx, dirz = sx * math.cos(a), math.sin(a)
        q = hit(offset(cl, 0.012).d, [[ax + dirx * 0.2, 1.44, az + dirz * 0.2]], [[-dirx, 0, -dirz]], t1=0.2)[0]
        rim.add(Sphere(P(*q), 0.0035), METAL, 0.001)
    return pc


def piece_archer():
    """Sleeveless leather jerkin laced up the front, a baldric, and a back quiver of arrows."""
    pc = Piece("hu_archer", "trunk")
    tb = trunk()
    j = PBody(h=0.0026, budget=340, clip=((-0.23, 0.86, -0.23), (0.23, 1.56, 0.23)))
    j.add(offset(tb, 0.012), LEATHER).cut(slab((0, 1, 0), 0.9, 1.48))
    j.cut(armholes(0.125, 1.3, 1.42))
    pc.add(j, cull=tb.eval, depth=0.003)
    la = PBody(h=0.0012, budget=120)
    for i, y in enumerate(np.linspace(1.0, 1.36, 4)):
        pts = hit(offset(tb, 0.0135).d, [[-0.012, y, 0.3], [0.012, y + 0.04, 0.3]], [[0, 0, -1]] * 2, t1=0.3)
        la.add(Cone(P(*pts[0]), P(*pts[1]), 0.0022, 0.0022), BAND)
        pts = hit(offset(tb, 0.0135).d, [[0.012, y, 0.3], [-0.012, y + 0.04, 0.3]], [[0, 0, -1]] * 2, t1=0.3)
        la.add(Cone(P(*pts[0]), P(*pts[1]), 0.0022, 0.0022), BAND)
    pc.add(la)
    bd = PBody(h=0.0022, budget=120, clip=((-0.23, 0.95, -0.23), (0.23, 1.56, 0.23)))
    bd.sym = False
    a2, b2 = np.array([-0.13, 1.02]), np.array([0.12, 1.47])
    d = (b2 - a2) / np.linalg.norm(b2 - a2)
    nn = np.array([d[1], -d[0]])
    c2 = (a2 + b2) / 2
    bd.add(offset(tb, 0.016), BAND).cut(Fn(lambda p: np.abs((p[:, 0] - c2[0]) * nn[0] + (p[:, 1] - c2[1]) * nn[1]) - 0.018,
                                                 (-1,) * 3, (1,) * 3)).cut(slab((0, 1, 0), 0.97, 1.5), 0.004)
    pc.add(bd, cull=tb.eval, depth=0.006)
    q = PBody(h=0.0018, budget=300)
    q.sym = False
    a, bb = P(0.04, 1.1, -0.15), P(0.15, 1.5, -0.15)
    q.add(Cone(a, bb, 0.036, 0.042), LEATHER)
    q.cut(Fn(lambda p, a=a, bb=bb: (p - bb) @ ((bb - a) / np.linalg.norm(bb - a)), (-1,) * 3, (1,) * 3))
    dd = (bb - a) / np.linalg.norm(bb - a)
    for t, r in ((0.97, 0.046), (0.2, 0.041)):
        c = a + (bb - a) * t
        u = np.cross(dd, P(0, 0, 1))
        u /= np.linalg.norm(u)
        vv = np.cross(dd, u)
        q.add(ring([(c + r * (math.cos(s) * u + math.sin(s) * vv), 0.004) for s in np.linspace(0, 2 * math.pi, 16, endpoint=False)]),
              BAND, 0.002)
    for k, (ox, oz) in enumerate(((0.0, 0.0), (0.016, 0.014), (-0.015, 0.012), (0.004, -0.016))):
        base = bb + P(ox, -0.01, oz)
        tip = base + dd * (0.11 + 0.012 * k)
        q.add(Cone(base, tip, 0.0035, 0.0035), BAND, 0.001)
        fu = np.cross(dd, P(1, 0, 0))
        fu /= np.linalg.norm(fu)
        q.add(Ellipsoid(tip - dd * 0.022, (0.003, 0.03, 0.011), np.stack([np.cross(fu, dd), dd, fu], 1)), FLETCH, 0.002)
    pc.add(q)
    return pc


def piece_cloak():
    """Desert cloak draped down the back from the shoulders to mid-thigh, tied at the throat."""
    pc = Piece("hu_cloak", "trunk")
    tb = trunk()
    b = PBody(h=0.0026, budget=330, clip=((-0.24, 0.78, -0.24), (0.24, 1.58, 0.06)))
    b.add(offset(tb, 0.017), CLOAK)
    # The hanging part is narrower than the shoulders so it falls behind the arms.
    b.add(Squash(CappedCone(P(0, 1.25, 0.0), P(0, 0.8, 0.0), 0.146, 0.172), P(0, 0, -0.035), (1, 1, 0.74)), CLOAK, 0.05)
    b.cut(Fn(lambda p: p[:, 2] - (0.02 - 0.08 * ss(1.4, 1.53, p[:, 1])), (-1,) * 3, (1,) * 3))  # back half
    b.cut(half(P(0, 0.8, 0), (0, 1, 0))).cut(Fn(lambda p: p[:, 1] - (1.53 + 1.6 * p[:, 0] ** 2), (-1,) * 3, (1,) * 3))
    b.shag(Ellipsoid(P(0, 0.95, -0.12), (0.25, 0.25, 0.15)), 0.007, Folds(8, 1.1, 1.3, 0.85, 0.0, 0.05), soft=0.04)
    pc.add(b, cull=tb.eval, depth=0.004)
    cd = PBody(h=0.0016, budget=80)
    cd.add(ring(surface_ring(offset(tb, 0.019).d, 0.0, -0.004, lambda a: 1.51 - 0.02 * max(0.0, math.cos(a)), rad=0.25,
                             n=28, tube=0.0048)), BAND)
    pc.add(cd)
    pc.weather = lambda p, n, reg: ss(0.95, 0.8, p[:, 1]) * 0.6  # noqa: E731
    return pc


def piece_sash():
    pc = Piece("hu_sash", "trunk")
    tb = trunk()
    b = PBody(h=0.0024, budget=180, clip=((-0.23, 0.95, -0.23), (0.23, 1.56, 0.23)))
    b.sym = False
    a2, b2 = np.array([0.13, 1.0]), np.array([-0.13, 1.46])
    d = (b2 - a2) / np.linalg.norm(b2 - a2)
    nn = np.array([d[1], -d[0]])
    c2 = (a2 + b2) / 2
    b.add(offset(tb, 0.015), BAND).cut(Fn(lambda p: np.abs((p[:, 0] - c2[0]) * nn[0] + (p[:, 1] - c2[1]) * nn[1]) - 0.03,
                                                (-1,) * 3, (1,) * 3)).cut(slab((0, 1, 0), 0.97, 1.5), 0.004)
    pc.add(b, cull=tb.eval, depth=0.006)
    return pc


def piece_robe():
    """Desert thobe skirt from the belt to above the knee, flared, with deep folds. Weighted to the
    thighs like the tunic skirt, so each leg carries its half through the stride."""
    pc = Piece("hu_robe", "trunk")
    tb = trunk()
    b = PBody(h=0.003, budget=380, clip=((-0.3, 0.62, -0.3), (0.3, 1.12, 0.3)))
    b.add(Squash(CappedCone(P(0, 1.09, 0), P(0, 0.86, 0), 0.142, 0.158), P(0, 0, -0.008), (1, 1, 0.84)), CLOAK)
    b.add(Squash(CappedCone(P(0, 0.88, 0), P(0, 0.64, 0), 0.157, 0.198), P(0, 0, -0.008), (1, 1, 0.84)), CLOAK, 0.03)
    b.add(offset(tb, 0.012), CLOAK, 0.02)
    b.cut(slab((0, 1, 0), 0.64, 1.1))
    b.shag(Ellipsoid(P(0, 0.78, 0.0), (0.3, 0.2, 0.25)), 0.009, Folds(10, 2.2, 0.95, 0.65), soft=0.05)
    pc.add(b, cull=tb.eval, depth=0.004)
    hm = PBody(h=0.0022, budget=130, clip=((-0.3, 0.62, -0.3), (0.3, 0.69, 0.3)))
    hm.add(offset(b, 0.003), BAND).cut(slab((0, 1, 0), 0.64, 0.665))
    pc.add(hm, cull=b.eval, depth=0.004)
    pc.weather = lambda p, n, reg: ss(0.8, 0.65, p[:, 1]) * 0.6  # noqa: E731
    return pc


def piece_bracer():
    """The archer's laced leather bow-arm guard on the bare left forearm."""
    pc = Piece("hu_bracer_l", "arm_l")
    _, sk, _ = arm_bodies(-1, False)
    b = PBody(h=0.0016, budget=150, clip=((-0.3, 1.0, -0.1), (-0.1, 1.16, 0.12)))
    b.add(offset(sk, 0.007), LEATHER).cut(slab((0, 1, 0), 1.008, 1.135))
    pc.add(b, cull=sk.eval, depth=0.004)
    la = PBody(h=0.0012, budget=90)
    for y in (1.03, 1.065, 1.1):
        la.add(ring(surface_ring(offset(sk, 0.0085).d, -SDX, 0.012, lambda a, y=y: y, rad=0.12, n=16, tube=0.0026)), BAND)
    pc.add(la)
    return pc


# ───────────────────────────────────────────────────────────────── children
# A child is its own body, authored in the same rig frame (same joints, same skin kinds) so every
# clip and spawn site keeps working; the game shortens the limbs and sizes the child
# (`peasant_model::kit_build`). Soft, unmuscled shapes: a round belly, no pecs / lats / shoulder
# blades, slim smooth limbs, a plain smock to the knee, bare shins and simple turnshoes.
def kid_trunk_core():
    b = PBody(h=0.004, budget=820)
    T = TUNIC
    b.add(Ellipsoid(P(0, 0.99, -0.01), (0.14, 0.1, 0.104)), T)  # pelvis
    b.add(Ellipsoid(P(0, 1.16, 0.016), (0.128, 0.13, 0.104)), T, 0.06)  # round child's belly
    b.add(Ellipsoid(P(0, 1.33, -0.004), (0.128, 0.15, 0.09)), T, 0.06)  # soft ribcage
    for sx in (-1, 1):
        b.add(Cone(P(sx * 0.03, 1.506, -0.016), P(sx * 0.162, 1.474, -0.004), 0.033, 0.03), T, 0.05)  # sloped shoulder
        b.add(Sphere(P(sx * 0.16, 1.452, 0.004), 0.04), T, 0.045)
    b.add(Cone(P(0, 1.46, -0.01), P(0, 1.56, -0.006), 0.056, 0.046), T, 0.03)
    # The smock: one loose bell from the chest to just above the knee, gathered at the yoke.
    b.add(Squash(CappedCone(P(0, 1.16, 0), P(0, 0.68, 0), 0.136, 0.19), P(0, 0, -0.004), (1, 1, 0.82)), T, 0.05)
    b.cut(half(P(0, 0.68, 0), (0, 1, 0)))
    b.cut(Fn(lambda p: p[:, 1] - (1.528 + 1.6 * (p[:, 0] ** 2 + (0.8 * p[:, 2]) ** 2)), (-1,) * 3, (1,) * 3))
    # Gathers falling from the yoke + loose drape folds toward the hem.
    b.shag(Ellipsoid(P(0, 1.3, 0.06), (0.12, 0.09, 0.06)), 0.0025, Folds(14, 0.2, 1.36, 1.22), soft=0.03)
    b.shag(Ellipsoid(P(0, 0.82, -0.004), (0.24, 0.17, 0.2)), 0.006, Folds(9, 1.7, 1.08, 0.7), soft=0.04)
    return b


_KID_TRUNK = None


def kid_trunk():
    global _KID_TRUNK
    if _KID_TRUNK is None:
        _KID_TRUNK = kid_trunk_core()
    return _KID_TRUNK


def piece_kid_trunk():
    pc = Piece("hu_kid_trunk", "trunk")
    tb = kid_trunk()
    pc.add(tb)
    # A cord tied loosely round the waist (no buckle, no pouch), the knot's tails at one hip.
    cord = PBody(h=0.0018, budget=110)
    cord.sym = False
    cord.add(ring(surface_ring(tb.eval, 0.0, 0.0, lambda a: 1.1 + 0.012 * math.cos(a), rad=0.3, n=30, tube=0.005)), BAND)
    xk = hit(tb.eval, [[0.3, 1.1, 0.04]], [[-1, 0, 0]])[0][0]
    cord.add(Sphere(P(xk + 0.004, 1.1, 0.04), 0.009), BAND, 0.003)
    for dz in (-0.01, 0.012):
        cord.add(Cone(P(xk + 0.004, 1.095, 0.04 + dz), P(xk + 0.012, 1.0, 0.045 + dz * 2), 0.004, 0.003), BAND, 0.002)
    pc.add(cord)
    # Rough neckline + a turned hem.
    col = PBody(h=0.0018, budget=70)
    angs = np.linspace(0, 2 * math.pi, 26, endpoint=False)
    org = [[0.058 * math.sin(a), 1.7, -0.004 + 0.055 * math.cos(a)] for a in angs]
    col.add(ring([(P(q[0], q[1] + 0.002, q[2]), 0.005) for q in hit(tb.eval, org, [[0, -1, 0]] * len(org), t1=0.3)]), TRIM)
    pc.add(col)
    hem = PBody(h=0.0025, budget=110, clip=((-0.3, 0.67, -0.3), (0.3, 0.71, 0.3)))
    hem.add(layer(tb, -0.02, 0.003), TRIM).cut(slab((0, 1, 0), 0.68, 0.698))
    pc.add(hem)
    pc.weather = lambda p, n, reg: ss(0.86, 0.69, p[:, 1]) * 0.6 + ss(1.36, 1.28, p[:, 1]) * 0.15  # noqa: E731
    return pc


def piece_kid_arm(sx):
    """A loose smock sleeve to the wrist (no biceps / forearm masses) and a small soft hand."""
    side = "l" if sx < 0 else "r"
    pc = Piece(f"hu_kid_arm_{side}", f"arm_{side}")
    ax, az = sx * SDX, 0.01
    X = lambda d: ax + sx * d  # noqa: E731
    cl = PBody(h=0.002, budget=220)
    cl.add(Ellipsoid(P(X(-0.004), 1.44, az), (0.044, 0.06, 0.047)), TUNIC)
    cl.add(Chain([(P(X(0.0), 1.43, az), 0.043), (P(X(0.0), 1.3, az + 0.002), 0.04), (P(X(0.0), 1.17, az - 0.002), 0.038),
                  (P(X(0.0), 1.06, az + 0.004), 0.039), (P(X(0.0), 1.01, az + 0.004), 0.037)]), TUNIC, 0.03)
    cl.add(CappedCone(P(X(0.0), 1.03, az + 0.004), P(X(0.0), 0.995, az + 0.004), 0.038, 0.036), TUNIC, 0.01)
    cl.shag(Ellipsoid(P(X(0.0), 1.17, az + 0.02), (0.05, 0.06, 0.04)), 0.004, Creases(120.0, ax, az, seed=sx), soft=0.02)
    cl.shag(Ellipsoid(P(X(0.0), 1.04, az), (0.05, 0.05, 0.05)), 0.003, Creases(140.0, ax, az, 1.0 + sx), soft=0.02)
    pc.add(cl)
    sk = PBody(h=0.0017, budget=240)
    sk.add(Squash(Cone(P(0, 1.02, 0), P(0, 0.975, 0), 0.019, 0.0185), P(X(0.002), 0, az + 0.006), (1.0, 1.0, 1.2)), SKIN)
    fist(sk, sx, ax, 0.92, az, k=0.008)
    pc.add(sk)
    pc.weather = lambda p, n, reg: ss(0.98, 0.93, p[:, 1]) * (reg == SKIN) * 0.35  # noqa: E731
    return pc


def piece_kid_leg(sx):
    """A bare child's leg (smooth, no muscle heads) under the smock and a soft leather turnshoe."""
    side = "l" if sx < 0 else "r"
    pc = Piece(f"hu_kid_leg_{side}", f"leg_{side}")
    x0 = sx * HDX
    X = lambda d: x0 + sx * d  # noqa: E731
    lg = PBody(h=0.0024, budget=260)
    lg.add(Chain([(P(X(-0.014), 1.04, -0.006), 0.056), (P(X(-0.008), 0.9, 0.0), 0.055), (P(X(0.0), 0.72, 0.004), 0.046),
                  (P(X(0.0), 0.6, 0.004), 0.041)]), SKIN)
    lg.add(Sphere(P(X(0.0), 0.6, 0.012), 0.038), SKIN, 0.03)  # round knee
    lg.add(Chain([(P(X(0.0), 0.6, 0.0), 0.039), (P(X(0.0), 0.47, -0.006), 0.038), (P(X(0.0), 0.3, -0.002), 0.031),
                  (P(X(0.0), 0.17, -0.004), 0.027)]), SKIN, 0.03)
    lg.add(Ellipsoid(P(X(0.004), 0.45, -0.018), (0.032, 0.07, 0.03)), SKIN, 0.03)  # soft calf
    pc.add(lg)
    sh = PBody(h=0.0018, budget=210)
    sh.add(Chain([(P(X(0.0), 0.17, -0.006), 0.034), (P(X(0.0), 0.12, -0.01), 0.036)]), BOOT)
    sh.add(Sphere(P(X(0.0), 0.1, -0.03), 0.038), BOOT, 0.02)  # heel
    sh.add(Chain([(P(X(0.0), 0.105, -0.022), 0.038), (P(X(0.002), 0.094, 0.05), 0.039), (P(X(-0.002), 0.088, 0.12), 0.031)]),
           BOOT, 0.022)
    sh.add(Ellipsoid(P(X(-0.002), 0.088, 0.112), (0.036, 0.028, 0.038)), BOOT, 0.015)  # rounded toe
    sh.cut(half(P(0, 0.064, 0), (0, 1, 0)))
    sh.sub(CappedCone(P(X(0.0), 0.2, -0.008), P(X(0.0), 0.165, -0.008), 0.029, 0.027), BOOT, 0.004)  # open throat
    sh.shag(Ellipsoid(P(X(0.0), 0.11, 0.03), (0.05, 0.05, 0.08)), 0.0025, Creases(160.0, x0, 0.0, 3 + sx), soft=0.02)
    pc.add(sh, cull=lg.eval, depth=0.003)
    tie = PBody(h=0.0012, budget=60)
    tie.add(ring(surface_ring(offset(sh, 0.002).d, x0, -0.008, lambda a: 0.15, rad=0.1, n=16, tube=0.0028)), BAND)
    pc.add(tie)
    pc.weather = lambda p, n, reg: ss(0.32, 0.06, p[:, 1]) * 0.7 + np.exp(-((p[:, 1] - 0.6) / 0.05) ** 2) * 0.4  # noqa: E731
    return pc


# ───────────────────────────────────────────────────────────────── women
def dress_core():
    """A woman's kirtle: a fitted bodice (a bust, a narrower waist), the skirt falling from the
    girdle to the ankle with deep drape folds. Same trunk frame / weights as the tunic, so the
    skirt halves follow the thighs and shins through a stride."""
    b = PBody(h=0.0045, budget=1150)
    T = TUNIC
    b.add(Ellipsoid(P(0, 0.99, -0.014), (0.15, 0.1, 0.11)), T)  # hips
    b.add(Ellipsoid(P(0, 1.15, 0.0), (0.115, 0.1, 0.085)), T, 0.04)  # waist
    b.add(Ellipsoid(P(0, 1.33, -0.012), (0.122, 0.15, 0.088)), T, 0.05)  # ribcage
    for sx in (-1, 1):
        b.add(Sphere(P(sx * 0.052, 1.335, 0.052), 0.05), T, 0.04)  # bust
        b.add(Cone(P(sx * 0.03, 1.505, -0.018), P(sx * 0.158, 1.478, -0.006), 0.032, 0.028), T, 0.04)
        b.add(Sphere(P(sx * 0.158, 1.454, 0.004), 0.037), T, 0.035)
    b.add(Cone(P(0, 1.46, -0.01), P(0, 1.56, -0.006), 0.056, 0.046), T, 0.025)
    # Skirt: girdle -> knee -> ankle, flaring, a touch longer at the back.
    b.add(Squash(CappedCone(P(0, 1.1, 0), P(0, 0.6, 0), 0.142, 0.205), P(0, 0, -0.008), (1, 1, 0.84)), T, 0.04)
    b.add(Squash(CappedCone(P(0, 0.62, 0), P(0, 0.12, 0), 0.205, 0.255), P(0, 0, -0.01), (1, 1, 0.86)), T, 0.03)
    b.cut(half(P(0, 0.115, 0), (0, 1, 0.08)))
    b.cut(Fn(lambda p: p[:, 1] - (1.528 + 1.6 * (p[:, 0] ** 2 + (0.8 * p[:, 2]) ** 2)), (-1,) * 3, (1,) * 3))
    b.shag(Ellipsoid(P(0, 0.5, -0.01), (0.32, 0.45, 0.3)), 0.009, Folds(11, 0.8, 1.02, 0.2, power=1.2), soft=0.05)
    return b


_DRESS = None


def dress():
    global _DRESS
    if _DRESS is None:
        _DRESS = dress_core()
    return _DRESS


def dress_weights(p, kind):
    """A long skirt is one tube round both legs: the tunic split (each half riding its own thigh
    and shin) tears it into trousers mid-stride. Below the hips it half-follows the pelvis, the
    thighs share the rest over a wide left/right blend, and the knees do not pull the hem."""
    W = skin_weights(p, kind)
    x, y = p[:, 0], p[:, 1]
    t = ss(1.13, 1.27, y)
    leg = ss(1.04, 0.93, y) * (1 - t)
    sr = ss(-0.16, 0.16, x)
    share = 0.55
    for j in (HIP_L, HIP_R, KNEE_L, KNEE_R):
        W[:, j] = 0.0
    W[:, HIPS] = (1 - t) - leg * share
    W[:, HIP_L] = leg * share * (1 - sr)
    W[:, HIP_R] = leg * share * sr
    return W


def piece_dress():
    pc = Piece("hu_dress", "trunk")
    pc.weights = dress_weights
    db = dress()
    pc.add(db)
    # Girdle: a narrow leather belt low on the waist, its long end hanging down the front, a purse.
    gd = PBody(h=0.0022, budget=150, clip=((-0.22, 1.05, -0.2), (0.22, 1.12, 0.2)))
    gd.add(layer(db, -0.001, 0.006), LEATHER).cut(slab((0, 1, 0), 1.074, 1.094))
    pc.add(gd)
    zf = hit(db.eval, [[0.0, 1.084, 0.3]], [[0, 0, -1]])[0][2]
    bits = PBody(h=0.0016, budget=140)
    bits.sym = False
    bits.add(RBox(P(0.0, 1.084, zf + 0.008), (0.012, 0.012, 0.004), 0.003), METAL)
    z2 = hit(db.eval, [[0.02, 0.86, 0.3]], [[0, 0, -1]])[0][2]
    bits.add(Cone(P(0.008, 1.08, zf + 0.006), P(0.02, 0.86, z2 + 0.005), 0.006, 0.005), LEATHER, 0.002)  # strap end
    xp = hit(db.eval, [[0.3, 1.02, 0.03]], [[-1, 0, 0]])[0]
    bits.add(Ellipsoid(P(xp[0] + 0.012, 1.02, 0.03), (0.016, 0.03, 0.026), rot_z(0.12)), LEATHER)  # purse
    bits.add(Cone(P(xp[0] + 0.006, 1.08, 0.03), P(xp[0] + 0.012, 1.05, 0.03), 0.003, 0.003), BAND, 0.002)
    pc.add(bits)
    col = PBody(h=0.0018, budget=80)
    angs = np.linspace(0, 2 * math.pi, 28, endpoint=False)
    org = [[0.064 * math.sin(a), 1.7, -0.004 + 0.06 * math.cos(a)] for a in angs]
    col.add(ring([(P(q[0], q[1] + 0.002, q[2]), 0.005) for q in hit(db.eval, org, [[0, -1, 0]] * len(org), t1=0.3)]), TRIM)
    pc.add(col)
    hem = PBody(h=0.0028, budget=150, clip=((-0.35, 0.1, -0.35), (0.35, 0.17, 0.35)))
    hem.add(layer(db, -0.022, 0.0035), TRIM).cut(slab((0, 1, 0), 0.12, 0.15))
    pc.add(hem)
    pc.weather = lambda p, n, reg: ss(0.45, 0.13, p[:, 1]) * 0.7 + ss(1.42, 1.34, p[:, 1]) * ss(0.09, 0.12, np.abs(p[:, 0])) * 0.3  # noqa: E731
    return pc


def piece_coif():
    """A linen kerchief over the hair, knotted at the nape, a fold framing the face."""
    pc = Piece("hu_hat_coif", "head", "head")
    sc = scalp_body()
    b = PBody(h=0.0018, budget=330)
    b.add(offset(sc, 0.014), HEADCLOTH).cut(half(P(0, -0.02, 0.0), (0, 1, -0.55)))
    for sx in (-1, 1):
        b.add(Ellipsoid(P(sx * 0.072, 0.02, -0.03), (0.018, 0.05, 0.045)), HEADCLOTH, 0.02)  # over the ears
    b.sub(Ellipsoid(P(0, 0.02, 0.1), (0.062, 0.09, 0.06)), HEADCLOTH, 0.01)  # face opening
    b.add(Ellipsoid(P(0, -0.035, -0.094), (0.03, 0.022, 0.02)), HEADCLOTH, 0.012)  # the knot
    for sx in (-1, 1):
        b.add(Cone(P(sx * 0.01, -0.04, -0.1), P(sx * 0.03, -0.12, -0.11), 0.012, 0.007), HEADCLOTH, 0.01)  # tails
    b.shag(Sphere(P(0, 0.05, -0.04), 0.15), 0.003, Folds(9, 2.0, 0.16, -0.04), soft=0.03)
    pc.add(b)
    rim = PBody(h=0.0015, budget=90)
    knots = []
    for a in np.linspace(0, 2 * math.pi, 24, endpoint=False):
        q = P(0.062 * math.sin(a) * 1.02, 0.02 + 0.09 * math.cos(a), 0.0)
        q[2] = hit(b.eval, [[q[0], q[1], 0.25]], [[0, 0, -1]], t1=0.25)[0][2]
        knots.append((q + P(0, 0, -0.002), 0.0042))
    rim.add(ring(knots), HEADCLOTH)
    pc.add(rim)
    return pc


# ───────────────────────────────────────────────────────────────── AO references
def rig_reference():
    """The default person (sleeved arms, plain legs, a head blob) for baking AO into rig pieces."""
    tb = trunk()
    arms = [arm_bodies(sx, True) for sx in (-1, 1)]
    legs = [leg_bodies(sx, False) for sx in (-1, 1)]
    head = Ellipsoid(P(0, HEAD_Y + 0.02, 0.0), (0.085, 0.11, 0.1))
    neck = Cone(P(0, 1.5, -0.015), P(0, 1.62, -0.02), 0.05, 0.048)

    def fn(p):
        d = np.minimum(tb.eval(p), np.minimum(head.d(p), neck.d(p)))
        for cl, sk, _ in arms:
            d = np.minimum(d, np.minimum(cl.eval(p), sk.eval(p)))
        for lb in legs:
            d = np.minimum(d, lb[0].eval(p))
            d = np.minimum(d, lb[1].eval(p))
        return d
    return fn


def head_reference():
    hb = head_body("a")
    return hb.eval


# ───────────────────────────────────────────────────────────────── trade tools (rigid props)
# Same frames and dimensions as the box props in `peasant_model::peasant_tools`: hand tools on the
# `Sword` pivot, built +Y from the grip at the origin; the shield faces +Z, the bow's stave arcs in
# the Y-Z plane with the string at -Z. Tools use their OWN palette (`peasant_model::kit_tool`).
T_WOOD, T_IRON, T_LEATHER, T_ACCENT, T_BRONZE, T_STRING = range(6)


def _rot_z(a):
    from mathutils import Quaternion, Vector
    return Quaternion(Vector((0, -1, 0)), a)


def _poly(name, specs, res):
    ob = make_metaball(name, specs, res)
    ob.data.render_resolution = res
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob)
    return me


def build_meta(part, target_tris, res=0.0025):
    """Metaball prop -> one mesh with region (R) + a cavity term (G) per corner."""
    from mathutils import Vector
    verts, faces, regs = [], [], []
    for region, specs in part.groups.items():
        me = _poly(f"{part.name}_{region}", specs, res)
        base = len(verts)
        verts += [v.co.copy() for v in me.vertices]
        for p in me.polygons:
            faces.append([base + i for i in p.vertices])
            regs.append(region)
        bpy.data.meshes.remove(me)
    me = bpy.data.meshes.new(part.name)
    me.from_pydata(verts, [], faces)
    me.materials.append(name_material("creature"))
    me.attributes.new("reg", "FLOAT", "FACE").data.foreach_set("value", [float(r) for r in regs])
    ob = bpy.data.objects.new(part.name, me)
    bpy.context.scene.collection.objects.link(ob)
    _decimate(ob, target_tris)
    me = ob.data
    me.materials.clear()
    me.materials.append(name_material("creature"))
    for p in me.polygons:
        p.use_smooth = True
    face_reg = [0.0] * len(me.polygons)
    reg_attr = me.attributes.get("reg")
    if reg_attr is not None:
        reg_attr.data.foreach_get("value", face_reg)
    nb = [[] for _ in me.vertices]
    for e in me.edges:
        a, b = e.vertices
        nb[a].append(b)
        nb[b].append(a)
    cav = []
    for i, v in enumerate(me.vertices):
        if not nb[i]:
            cav.append(1.0)
            continue
        avg = sum((me.vertices[j].co for j in nb[i]), Vector()) / len(nb[i])
        conc = (avg - v.co).dot(v.normal)
        cav.append(max(0.66, min(1.0, 1.0 - conc * 10.0)))
    me.color_attributes.new("Col", "FLOAT_COLOR", "CORNER")
    cols = []
    for p in me.polygons:
        r = int(round(face_reg[p.index]))
        for li in p.loop_indices:
            vi = me.loops[li].vertex_index
            cols += [r / 16.0 + 1.0 / 32.0, cav[vi], 0.0, 1.0]
    me.color_attributes["Col"].data.foreach_set("color", cols)
    me.color_attributes.active_color = me.color_attributes["Col"]
    return ob


def tool(kind):
    p = Part(f"hu_tool_{kind}")
    # Work tools are full-size (the two-handed strokes in `toolwork.rs` grip them with both fists):
    # the haft runs +Y from the butt (-0.05), the right fist's grip at the origin, and the cutting
    # edge / blade faces +X. Keep the head heights in step with `toolwork::Tool`'s spec.
    if kind == "axe":
        p.cap(T_WOOD, (0, -0.05, 0), (0, 0.765, 0), 0.019)
        p.cap(T_LEATHER, (0, -0.04, 0), (0, 0.07, 0), 0.023)  # grip wrap
        p.ell(T_IRON, (0.035, 0.722, 0), (0.05, 0.036, 0.018))  # eye / cheeks
        p.ell(T_IRON, (0.12, 0.72, 0), (0.06, 0.045, 0.01))  # blade body
        p.ell(T_IRON, (0.175, 0.718, 0), (0.016, 0.075, 0.008))  # flared bit
        p.ball(T_IRON, (-0.03, 0.722, 0), 0.02)  # poll
    elif kind == "hoe":
        # A long-handled chopping hoe: a flat iron blade ~16 cm wide (along Z) on a short neck,
        # canted 15 deg back toward the hands, so it bites the soil and draws flat on the pull.
        p.cap(T_WOOD, (0, -0.05, 0), (0, 1.2, 0), 0.018)
        p.ell(T_IRON, (0.012, 1.205, 0), (0.026, 0.032, 0.024))  # socket
        p.ell(T_IRON, (0.098, 1.192, 0), (0.075, 0.007, 0.078), rot=_rot_z(-0.26))  # blade
    elif kind == "pick":
        p.cap(T_WOOD, (0, -0.05, 0), (0, 0.79, 0), 0.018)
        p.ell(T_IRON, (0, 0.745, 0), (0.026, 0.04, 0.024))  # socket
        pts = [(-0.24, 0.70), (-0.12, 0.748), (0.0, 0.762), (0.12, 0.748), (0.24, 0.70)]
        rads = [0.006, 0.015, 0.021, 0.015, 0.006]
        for (a, ra), (b, rb) in zip(zip(pts, rads), zip(pts[1:], rads[1:])):
            p.cap(T_IRON, (a[0], a[1], 0), (b[0], b[1], 0), (ra + rb) / 2)
    elif kind == "sword":
        p.cap(T_LEATHER, (0, -0.1, 0), (0, 0.04, 0), 0.016)  # grip
        p.ball(T_IRON, (0, -0.115, 0), 0.023)  # pommel
        p.cap(T_IRON, (-0.088, 0.058, 0), (0.088, 0.058, 0), 0.013)  # crossguard
        p.ell(T_IRON, (0, 0.31, 0), (0.026, 0.25, 0.0065))  # blade
        p.ell(T_IRON, (0, 0.56, 0), (0.02, 0.08, 0.006))  # point
    elif kind == "scimitar":
        p.cap(T_LEATHER, (0, -0.1, 0), (0, 0.04, 0), 0.016)
        p.ball(T_BRONZE, (0, -0.115, 0), 0.023)
        p.cap(T_BRONZE, (-0.075, 0.075, 0), (0.075, 0.075, 0), 0.016)
        for (x, y, a, w) in ((0.007, 0.165, -0.11, 0.026), (0.036, 0.291, -0.34, 0.03),
                             (0.092, 0.407, -0.56, 0.033), (0.173, 0.508, -0.79, 0.031)):
            p.ell(T_IRON, (x, y, 0), (w, 0.08, 0.0065), rot=_rot_z(a))
        p.ell(T_IRON, (0.245, 0.572, 0), (0.02, 0.055, 0.006), rot=_rot_z(-0.95))
    elif kind == "arrow":
        p.cap(T_WOOD, (0, -0.07, 0), (0, 0.44, 0), 0.0065)
        p.ell(T_IRON, (0, 0.465, 0), (0.013, 0.036, 0.0065))  # bodkin
        p.ell(T_ACCENT, (0, -0.02, 0), (0.02, 0.05, 0.004))  # fletching vanes
        p.ell(T_ACCENT, (0, -0.02, 0), (0.004, 0.05, 0.02))
    elif kind == "shield":
        p.ell(T_WOOD, (0, 0, 0), (0.24, 0.24, 0.02))  # planks
        # Painted livery field (steep edge) — on the face only: centred forward of the planks so
        # it never shows through the back, where the fist holds the grip.
        p.ell(T_ACCENT, (0, 0, 0.008), (0.165, 0.165, 0.026))
        for k in range(20):  # leather-bound rim
            a, b = k / 20 * 2 * math.pi, (k + 1) / 20 * 2 * math.pi
            p.cap(T_LEATHER, (math.cos(a) * 0.238, math.sin(a) * 0.238, 0), (math.cos(b) * 0.238, math.sin(b) * 0.238, 0), 0.013)
        p.ball(T_IRON, (0, 0, 0.022), 0.045)  # boss
    elif kind == "bow":
        tip_y, tip_z, belly_z = 0.5, -0.12, 0.11

        def bez(t):
            u = 1 - t
            return (0.0, (t * t - u * u) * tip_y, (u * u + t * t) * tip_z + 2 * u * t * belly_z)
        n = 10
        for i in range(n):
            a, b = bez(i / n), bez((i + 1) / n)
            mid = abs((i + 0.5) / n - 0.5) * 2  # 0 at the grip .. 1 at a tip
            p.cap(T_WOOD, a, b, 0.017 - 0.008 * mid)
        p.cap(T_STRING, (0, -tip_y, tip_z), (0, tip_y, tip_z), 0.004)
        p.cap(T_LEATHER, (0, -0.07, -0.004), (0, 0.07, -0.004), 0.02)  # grip wrap
    return p, 320 if kind in ("shield", "bow", "scimitar") else 220


TOOLS = ("axe", "hoe", "pick", "sword", "scimitar", "arrow", "shield", "bow")
BEARDS = ("full", "short", "moustache")
ADULT_FACES = ("a", "b", "c")
HATS = ("hood", "cap", "straw", "miner", "helm", "archer", "turban", "warhelm", "headwrap")
HAIRS = ("crop", "shag", "long", "bald", "bowl")


def all_pieces():
    out = [piece_trunk]
    out += [(lambda sx=sx, s=s: piece_arm(sx, s)) for sx in (-1, 1) for s in (False, True)]
    out += [(lambda sx=sx, d=d: piece_leg(sx, d)) for sx in (-1, 1) for d in (False, True)]
    out += [(lambda v=v: piece_head(v)) for v in FACES]
    out += [(lambda s=s: piece_hair(s)) for s in HAIRS]
    out += [(lambda s=s, f=f: piece_beard(s, f)) for s in BEARDS for f in ADULT_FACES]
    out += [(lambda k=k: piece_hat(k)) for k in HATS]
    out += [piece_apron, piece_guard, piece_archer, piece_cloak, piece_sash, piece_robe, piece_bracer]
    out += [(lambda sx=sx: piece_pauldron(sx)) for sx in (-1, 1)]
    out += [piece_kid_trunk] + [(lambda sx=sx: piece_kid_arm(sx)) for sx in (-1, 1)]
    out += [(lambda sx=sx: piece_kid_leg(sx)) for sx in (-1, 1)]
    out += [piece_dress, piece_coif]
    return out


# ───────────────────────────────────────────────────────────────── preview (posed Workbench lineup)
PREVIEW_COLS = {
    SKIN: (0.85, 0.62, 0.48), LIP: (0.62, 0.36, 0.33), EYE: (0.08, 0.06, 0.05), HAIR: (0.25, 0.16, 0.1),
    TUNIC: (0.35, 0.5, 0.7), TRIM: (0.2, 0.3, 0.42), TROUSER: (0.3, 0.24, 0.18), LEATHER: (0.32, 0.23, 0.17),
    BOOT: (0.18, 0.13, 0.1), METAL: (0.72, 0.74, 0.78), HEADCLOTH: (0.55, 0.45, 0.3), BAND: (0.3, 0.22, 0.15),
    TABARD: (0.2, 0.3, 0.6), FLETCH: (0.9, 0.8, 0.4), CLOAK: (0.75, 0.65, 0.45), HELM: (0.7, 0.72, 0.76),
}


def rest_frames(head_scale=HEAD_SCALE):
    """Rest-pose joint transforms (4x4, rig space) in `JOINTS` order — `spawn_biped`'s layout."""
    def T(x, y, z, s=1.0):
        m = np.eye(4)
        m[:3, :3] *= s
        m[:3, 3] = (x, y, z)
        return m
    hips = T(0, 1.05, 0)
    torso = hips @ T(0, 0.15, 0)
    neck = torso @ T(0, 0.35, 0)
    head = neck @ T(0, 0.08, 0, head_scale)
    f = {"hips": hips, "torso": torso, "neck": neck, "head": head}
    for s, sx in (("l", -1), ("r", 1)):
        f[f"sh_{s}"] = torso @ T(sx * SDX, 0.27, 0.01)
        f[f"el_{s}"] = f[f"sh_{s}"] @ T(0, -0.3, 0)
        f[f"hip_{s}"] = hips @ T(sx * HDX, -0.05, 0)
        f[f"knee_{s}"] = f[f"hip_{s}"] @ T(0, -0.4, 0)
        f[f"foot_{s}"] = f[f"knee_{s}"] @ T(0, -0.45, 0)
    return f


PARENT = {"torso": "hips", "neck": "torso", "head": "neck", "sh_l": "torso", "el_l": "sh_l", "sh_r": "torso",
          "el_r": "sh_r", "hip_l": "hips", "knee_l": "hip_l", "foot_l": "knee_l", "hip_r": "hips",
          "knee_r": "hip_r", "foot_r": "knee_r"}


def euler(x, y, z):
    """glam EulerRot::XYZ: Rx * Ry * Rz."""
    cx, sx_, cy, sy, cz, sz = math.cos(x), math.sin(x), math.cos(y), math.sin(y), math.cos(z), math.sin(z)
    Rx = np.array([[1, 0, 0], [0, cx, -sx_], [0, sx_, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Rx @ Ry @ Rz


def pose_rot(name, c):
    """A few of the game's clips (`player::anim`) at gait phase `c`: joint -> (euler, hips y)."""
    if name == "walk":
        l, r = c, c + math.pi
        return {"hips": (euler(0, math.cos(c) * 0.08, math.sin(c) * 0.045), 1.04 + math.sin(2 * c) * 0.028),
                "torso": euler(0.05, -math.cos(c) * 0.11, -math.sin(c) * 0.035),
                "hip_l": euler(math.sin(l) * 0.6, 0, 0), "hip_r": euler(math.sin(r) * 0.6, 0, 0),
                "knee_l": euler(max(0.0, -math.cos(l)) * 1.1, 0, 0), "knee_r": euler(max(0.0, -math.cos(r)) * 1.1, 0, 0),
                "foot_l": euler(-math.sin(l) * 0.6 + max(0.0, -math.sin(l)) * 0.25, 0, 0),
                "foot_r": euler(-math.sin(r) * 0.6 + max(0.0, -math.sin(r)) * 0.25, 0, 0),
                "sh_l": euler(math.sin(r) * 0.11, 0, -0.04), "el_l": euler(-0.3 + min(0.0, math.sin(r)) * 0.08, 0, 0),
                "sh_r": euler(math.sin(l) * 0.16, 0, 0.04), "el_r": euler(-0.22 + min(0.0, math.sin(l)) * 0.11, 0, 0)}
    if name == "run":
        l, r = c, c + math.pi
        a = abs(math.sin(c))
        return {"hips": (euler(0, math.cos(c) * 0.1, math.sin(c) * 0.04), 1.0 + a * 0.06),
                "torso": euler(0.18 + a * 0.04, -math.cos(c) * 0.12, -math.sin(c) * 0.035),
                "head": euler(-0.1 - a * 0.04, 0, 0),
                "hip_l": euler(math.sin(l) * 0.8, 0, max(0.0, math.sin(l)) * 0.02),
                "hip_r": euler(math.sin(r) * 0.8, 0, -max(0.0, math.sin(r)) * 0.02),
                "knee_l": euler(max(0.0, -math.cos(l)) * 1.3 + 0.12, 0, 0),
                "knee_r": euler(max(0.0, -math.cos(r)) * 1.3 + 0.12, 0, 0),
                "foot_l": euler(-math.sin(l) * 0.4 + 0.14, 0, 0), "foot_r": euler(-math.sin(r) * 0.4 + 0.14, 0, 0),
                "sh_l": euler(math.sin(r) * 0.15, 0, -0.14), "el_l": euler(-1.15 + min(0.0, math.sin(r)) * 0.2, 0, 0),
                "sh_r": euler(math.sin(l) * 0.12, 0, 0.14), "el_r": euler(-1.25 + min(0.0, math.sin(l)) * 0.15, 0, 0)}
    if name == "sit":
        return {"hips": (euler(0.1, 0, 0), 0.6725), "torso": euler(0.2, 0, 0), "head": euler(-0.1, 0, 0),
                "hip_l": euler(-0.78, 0.38, -0.18), "hip_r": euler(-0.78, -0.38, 0.18),
                "knee_l": euler(1.95, 0, 0), "knee_r": euler(1.95, 0, 0), "foot_l": euler(-0.55, 0, 0),
                "foot_r": euler(-0.55, 0, 0), "sh_l": euler(0.15, 0.15, 0.45), "el_l": euler(-0.9, 0, 0),
                "sh_r": euler(0.1, -0.2, -0.3), "el_r": euler(-1.0, 0, 0)}
    return {}


def skin_matrices(pose, head_scale):
    rest = rest_frames(head_scale)
    rot = pose_rot(*pose) if pose else {}
    glob = {}
    for j in JOINTS:
        local = np.linalg.inv(rest[PARENT[j]]) @ rest[j] if j in PARENT else rest[j].copy()
        r = rot.get(j)
        if j == "hips" and r is not None:
            R, hy = r
            local[:3, :3] = local[:3, :3] @ R
            local[1, 3] = hy
        elif r is not None:
            local[:3, :3] = local[:3, :3] @ r
        glob[j] = glob[PARENT[j]] @ local if j in PARENT else local
    return [glob[j] @ np.linalg.inv(rest[j]) for j in JOINTS]


def preview(objs, weights, out_png, pose_name="rest", yaw=None, cam=None, looks_sel=None):
    by = {o.name: o for o in objs}
    for o in list(bpy.data.objects):
        if o.get("preview_dup"):
            bpy.data.objects.remove(o)
        elif o.type == "MESH":
            o.hide_render = True
    looks = [
        ("Unemployed", "a", "crop", "short", None, "bare", False),
        ("Unemployed", "b", "shag", "full", "hood", "sleeve", False),
        ("Farmer", "b", "bald", "full", "straw", "bare", False),
        ("Woodcutter", "c", "crop", "full", "cap", "bare", False),
        ("Miner", "a", "crop", "moustache", "miner", "bare", False),
        ("Guard", "a", "crop", None, "helm", "sleeve", False),
        ("Archer", "c", "shag", None, "archer", "bare", False),
        ("Farmer", "b", "crop", "short", "turban", "sleeve", True),
        ("Guard", "a", "crop", "short", "warhelm", "sleeve", True),
        ("Unemployed", "kid", "bowl", None, None, "bare", False),
        ("Woman", "w", "crop", None, "coif", "sleeve", False),
    ]
    if looks_sel:
        looks = [looks[i] for i in looks_sel]
    scene = bpy.context.scene
    phase = {"walk": 0.9, "run": 1.2}.get(pose_name, 0.0)
    pose = (pose_name, phase) if pose_name != "rest" else None
    for i, (kind, fv, hair, beard, hat, fore, desert) in enumerate(looks):
        x0 = (i - (len(looks) - 1) / 2) * 0.75
        kid = fv == "kid"
        hs = (1.55 if kid else 1.06) * 1.1
        root_s = 0.55 / 0.81 if kid else 1.0
        names = ["hu_trunk", f"hu_arm_{fore}_l", f"hu_arm_{fore}_r", f"hu_leg_{'wrap_' if desert else ''}l",
                 f"hu_leg_{'wrap_' if desert else ''}r", f"hu_head_{fv}"]
        if kid:  # the child's own body
            names = ["hu_kid_trunk", "hu_kid_arm_l", "hu_kid_arm_r", "hu_kid_leg_l", "hu_kid_leg_r", "hu_head_kid"]
        if kind == "Woman":
            names[0] = "hu_dress"
        if hat not in ("hood", "archer", "turban", "headwrap", "warhelm", "helm", "coif"):
            names.append(f"hu_hair_{hair}")
        if beard:
            names.append(f"hu_beard_{beard}_{fv}")
        if hat:
            names.append(f"hu_hat_{hat}")
        if kind == "Farmer" and not desert:
            names.append("hu_apron")
        if kind == "Guard":
            names += ["hu_guard", "hu_pauldron_l", "hu_pauldron_r"]
        if kind == "Archer":
            names += ["hu_archer", "hu_bracer_l"]
        if desert:
            names += ["hu_cloak"] + (["hu_sash", "hu_robe"] if kind != "Guard" else [])
        M = skin_matrices(pose, hs)
        for nm in names:
            src = by.get(nm)
            if src is None:
                print("preview: missing", nm)
                continue
            W = weights[nm]
            me = src.data.copy()
            co = np.array([v.co[:] for v in me.vertices])
            pg = gm(co)
            if src["frame"] == "head":
                s = 1.0 + (hs - 1.0) * W[:, HEAD]
                pg = pg * s[:, None] + np.array([0.0, HEAD_Y, 0.0])
            ph = np.concatenate([pg, np.ones((len(pg), 1))], 1)
            out = np.zeros((len(pg), 3))
            for j in range(len(JOINTS)):
                wj = W[:, j]
                if wj.max() <= 0:
                    continue
                out += wj[:, None] * (ph @ M[j].T)[:, :3]
            out *= root_s
            out[:, 0] += x0
            me.vertices.foreach_set("co", bl(out).ravel())
            me.update()
            dup = bpy.data.objects.new(nm + f"_p{i}", me)
            dup["preview_dup"] = 1
            scene.collection.objects.link(dup)
            src_c = me.color_attributes["Col"]
            vals = np.zeros(len(src_c.data) * 4)
            src_c.data.foreach_get("color", vals)
            vals = vals.reshape(-1, 4)
            disp = me.color_attributes.new("Disp", "FLOAT_COLOR", "CORNER")
            outc = []
            for c in vals:
                col = PREVIEW_COLS[min(15, int(c[0] * 16))]
                outc += [col[0] * c[1], col[1] * c[1], col[2] * c[1], 1.0]
            disp.data.foreach_set("color", outc)
            me.color_attributes.active_color = disp
    cam_ob = bpy.data.objects.get("cam")
    if cam_ob is None:
        cam_data = bpy.data.cameras.new("cam")
        cam_data.type = "ORTHO"
        cam_ob = bpy.data.objects.new("cam", cam_data)
        scene.collection.objects.link(cam_ob)
    cx, cz, ow = 0.0, 1.0, 7.6
    if cam or os.environ.get("PEOPLE_PREVIEW_CAM"):
        cx, cz, ow = (float(t) for t in (cam or os.environ["PEOPLE_PREVIEW_CAM"]).split(","))
    cam_ob.data.ortho_scale = ow
    a = math.radians(float(yaw if yaw is not None else os.environ.get("PEOPLE_PREVIEW_YAW", "20")))
    cam_ob.location = (cx + math.sin(a) * 10, -math.cos(a) * 10, cz)
    cam_ob.rotation_euler = (math.radians(90), 0, a)
    scene.camera = cam_ob
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "VERTEX"
    w, h = (int(t) for t in os.environ.get("PEOPLE_PREVIEW_RES", "2400,1000").split(","))
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.render.filepath = str(out_png)
    bpy.ops.render.render(write_still=True)
    print(f"PREVIEW {out_png}")


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    only = os.environ.get("PEOPLE_ONLY")  # comma list of piece-name prefixes (iteration speed)
    clear_scene()
    objs, weights = [], {}
    rig_ao = None
    head_ao = None
    for fn in all_pieces():
        pc = fn()
        if only and not pc.name.startswith(tuple(only.split(","))):
            continue
        if pc.frame == "head":
            head_ao = head_ao or head_reference()
            ao = head_ao
        else:
            rig_ao = rig_ao or rig_reference()
            ao = rig_ao
        ob, W = build_piece(pc, ao)
        objs.append(ob)
        weights[ob.name] = W
        print(f"{ob.name}: {sum(len(p.vertices) - 2 for p in ob.data.polygons)} tris", flush=True)
    tool_objs = []
    if not only:
        for k in TOOLS:
            part, budget = tool(k)
            ob = build_meta(part, budget)
            tool_objs.append(ob)
            print(f"{ob.name}: {sum(len(p.vertices) - 2 for p in ob.data.polygons)} tris")
    if os.environ.get("PEOPLE_NO_EXPORT") != "1" and not only:  # a subset must never replace the glb
        export_glb(OUT / "people.glb", objs + tool_objs, tangents=False)
    if argv:
        # Each arg: png[:pose[:yaw[:cx,cz,width[:look indices]]]]  (looks = 0-9, '+'-separated)
        for spec in argv:
            parts = spec.split("|")
            sel = [int(t) for t in parts[4].split("+")] if len(parts) > 4 and parts[4] else None
            preview(objs, weights, Path(parts[0]).resolve(), parts[1] if len(parts) > 1 else "rest",
                    float(parts[2]) if len(parts) > 2 and parts[2] else None, parts[3] if len(parts) > 3 and parts[3] else None, sel)
    print("PEOPLE_DONE")
