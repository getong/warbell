"""The regional wardens (src/boss) as realistic sculpts on the scanned PBR sets -> wardens.glb.

The bosses were flat-shaded primitive stacks on the creature material. Here each is sculpted from
displaced, noise-gnarled tubes and fractured stones on the same scans the forest kit uses (oak bark,
field rock, trodden earth, rusted iron, cloth, hide, the undergrowth atlas), with the vertex colour
carrying the weathering (moss, lichen, rust, wet mud, soot in the creases):

    treant    Old Bramblewood: a gnarled oak trunk with a face grown into its bark (sunken knot
              eyes with a green glow deep inside, a split-bark mouth), root legs splaying into the
              ground, bough arms ending in twig claws, moss and bracket fungus, a broken crown of
              antler boughs and ferns.
    golem     Karngor: stacked fractured field rock with lichen, molten seams glowing in the cracks
              between the stones and a molten heart in the chest fissure (as the old design had).
    revenant  The Sand Revenant: a gaunt undead knight in rusted mail and a dented breastplate,
              a tattered surcoat in rags, a bare skull under an open bascinet, cold eyes, a notched
              rusted longsword in the right hand.
    hag       Mabworm: a hunched mass of bog mud wrapped in rags and reeds, long knobbly arms with
              talons, a hooked nose, glowing eyes, matted weed-hair.

Each warden ships as rig pieces in the boss rig contract (boss::models::kit_parts): a static
`_torso` in root space, and `_head` / `_arm_r` / `_arm_l` / `_leg` each built around its pivot
(authored in root space and shifted by the pivot). The pivots are the procedural BossSpec's, so
boss::boss_limbs swings legs and arms about X and yaws the head about Y exactly as before. Built
facing +Z, feet at y=0 (roots and toes run a little below), before the boss root scale.

    blender -b --factory-startup --python tools/blender_forest/wardens.py
"""
import json
import math
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402
from common import OUT, clear_scene, export_glb  # noqa: E402
from geo import G, bl, quat_x, quat_y, quat_z, sheet  # noqa: E402
from meshkit import Builder  # noqa: E402
from wayside_models import Noise, bounds, icosphere, mix, scale, smoothstep  # noqa: E402

# Tileable scans only (prop_rock_* are scanned models' UV atlases - islands on a flat background).
MATS = ["bark_oak", "s_rock", "s_earth", "s_hide", "s_cloth", "s_iron", "s_plaster", "undergrowth", "glow"]
M_BARK, M_ROCK, M_EARTH, M_HIDE, M_CLOTH, M_IRON, M_BONE, M_CARD, M_GLOW = range(len(MATS))
M_SROCK = M_ROCK

LAYOUT = json.loads((OUT / "foliage_layout.json").read_text(encoding="utf-8"))["undergrowth"]
AW, AH = LAYOUT["size"]


def V(x, y, z):
    return Vector((x, y, z))


def clamp01(x):
    return min(max(x, 0.0), 1.0)


# ─────────────────────────────────────────────────────────────── primitives
def _frames(pts, ref):
    """Parallel-transported (t, a, b) frames along a polyline; `a` starts as `ref` made orthogonal."""
    out = []
    a_prev = None
    for i in range(len(pts)):
        if i == 0:
            t = (pts[1] - pts[0]).normalized()
        elif i == len(pts) - 1:
            t = (pts[-1] - pts[-2]).normalized()
        else:
            t = (pts[i + 1] - pts[i - 1]).normalized()
        if a_prev is None:
            r = Vector(ref)
            if abs(r.normalized().dot(t)) > 0.95:
                r = Vector((0.0, 0.0, 1.0)) if abs(t.z) < 0.9 else Vector((0.0, 1.0, 0.0))
            a = (r - t * r.dot(t)).normalized()
        else:
            a = (a_prev - t * a_prev.dot(t)).normalized()
        a_prev = a
        out.append((t, a, t.cross(a)))
    return out


def sculpt(g, pts, radii, mat, col_fn, sides=16, disp=None, tile=0.9, caps=(True, True), ref=(1.0, 0.0, 0.0),
           tip=0.5):
    """An organic tube: rings along `pts` (radius scalar or (ra, rb) for an elliptic section, `ra`
    along the frame's `ref`-side axis), each vertex pushed out by `disp(p, d, t)` (d = radial dir,
    t = 0..1 along) - gnarls, ridges, sockets. Smooth grid normals, cylindrical world-scaled UVs,
    per-vertex `col_fn(p, n)`. Ends close in a shallow dome (`tip` x radius)."""
    pts = [Vector(p) for p in pts]
    fr = _frames(pts, ref)
    n = len(pts)
    P = []
    D = []
    for i in range(n):
        t, a, b = fr[i]
        r = radii[i]
        ra, rb = (r, r) if not isinstance(r, (tuple, list)) else r
        ring, dring = [], []
        for s in range(sides):
            th = 2 * math.pi * s / sides
            d = a * math.cos(th) + b * math.sin(th)
            p = pts[i] + a * (ra * math.cos(th)) + b * (rb * math.sin(th))
            if disp is not None:
                p = p + d * disp(p, d, i / (n - 1))
            ring.append(p)
            dring.append(d)
        P.append(ring)
        D.append(dring)
    # end domes
    tips = []
    for end, sgn in ((0, -1), (n - 1, 1)):
        t = fr[end][0]
        r = radii[end]
        rr = max(r) if isinstance(r, (tuple, list)) else r
        tips.append(pts[end] + t * sgn * rr * tip)
    N = [[None] * sides for _ in range(n)]
    for i in range(n):
        for s in range(sides):
            du = P[i][(s + 1) % sides] - P[i][(s - 1) % sides]
            if 0 < i < n - 1:
                dv = P[i + 1][s] - P[i - 1][s]
            elif i == 0:
                dv = P[1][s] - (tips[0] if caps[0] else P[0][s] - (P[1][s] - P[0][s]))
            else:
                dv = (tips[1] if caps[1] else P[i][s] + (P[i][s] - P[i - 1][s])) - P[i - 1][s]
            nn = du.cross(dv)
            if nn.length < 1e-12:
                nn = D[i][s].copy()
            nn.normalize()
            if nn.dot(D[i][s]) < 0:
                nn = -nn
            N[i][s] = nn
    # UVs: u around (world-scaled by the mean girth), v = arc length
    girth = 0.0
    for i in range(n):
        girth += sum((P[i][(s + 1) % sides] - P[i][s]).length for s in range(sides))
    girth /= n
    urep = max(1.0, round(girth / tile))
    vacc = [0.0]
    for i in range(1, n):
        vacc.append(vacc[-1] + (pts[i] - pts[i - 1]).length / tile)
    C = [[col_fn(P[i][s], N[i][s]) for s in range(sides)] for i in range(n)]
    for i in range(n - 1):
        for s in range(sides):
            s1 = (s + 1) % sides
            u0, u1 = s / sides * urep, (s + 1) / sides * urep
            q = [P[i][s], P[i + 1][s], P[i + 1][s1], P[i][s1]]
            uv = [(u0, vacc[i]), (u0, vacc[i + 1]), (u1, vacc[i + 1]), (u1, vacc[i])]
            ns = [N[i][s], N[i + 1][s], N[i + 1][s1], N[i][s1]]
            cs = [C[i][s], C[i + 1][s], C[i + 1][s1], C[i][s1]]
            # outward winding
            fn = (q[1] - q[0]).cross(q[2] - q[0])
            if fn.dot(ns[0] + ns[2]) < 0:
                q, uv, ns, cs = q[::-1], uv[::-1], ns[::-1], cs[::-1]
            g.poly(q, uv, ns, cs, mat)
    for k, (end, sgn) in enumerate(((0, -1), (n - 1, 1))):
        if not caps[k]:
            continue
        tp = tips[k]
        tn = fr[end][0] * sgn
        tc = col_fn(tp, tn)
        for s in range(sides):
            s1 = (s + 1) % sides
            tri = [P[end][s], P[end][s1], tp]
            ns = [N[end][s].lerp(tn, 0.5).normalized(), N[end][s1].lerp(tn, 0.5).normalized(), tn]
            cs = [C[end][s], C[end][s1], tc]
            uv = [(s / sides * urep, vacc[end]), ((s + 1) / sides * urep, vacc[end]),
                  ((s + 0.5) / sides * urep, vacc[end] + sgn * 0.3)]
            fn = (tri[1] - tri[0]).cross(tri[2] - tri[0])
            if fn.dot(tn + (P[end][s] - pts[end]).normalized()) < 0:
                tri, ns, cs, uv = tri[::-1], ns[::-1], cs[::-1], uv[::-1]
            g.poly(tri, uv, ns, cs, mat)


def curve(p0, p1, bend=(0.0, 0.0, 0.0), n=8, wob=0.0, rng=None):
    """n+1 points from p0 to p1 bowed by `bend` at the middle, with optional wobble."""
    p0, p1, bend = Vector(p0), Vector(p1), Vector(bend)
    out = []
    for k in range(n + 1):
        t = k / n
        p = p0.lerp(p1, t) + bend * (4 * t * (1 - t))
        if wob and rng is not None and 0 < k < n:
            p += Vector(rng.normal(size=3)) * wob
        out.append(p)
    return out


def lump(g, centre, radii, rng, mat, col_fn, rough=0.12, cuts=2, detail=3, rot=None, tile=0.7, freq=1.4,
         flat_lo=None, cut=(0.6, 0.85)):
    """A displaced icosphere with planar fracture cuts - stones, burls, mud clots, skulls."""
    verts, faces = icosphere(detail)
    nz = Noise(rng, 4, freq)
    planes = []
    for _ in range(cuts):
        d = Vector(rng.normal(size=3)).normalized()
        planes.append((d, rng.uniform(*cut)))
    rot = rot or quat_y(rng.uniform(0, 6.283))
    out = []
    for v in verts:
        p = v * (1.0 + rough * nz(v))
        for d, c in planes:
            e = p.dot(d) - c
            if e > 0:
                p = p - d * e * 0.92
        if flat_lo is not None and p.y < -flat_lo:
            p.y = -flat_lo + (p.y + flat_lo) * 0.1
        out.append(Vector(centre) + rot @ Vector((p.x * radii[0], p.y * radii[1], p.z * radii[2])))
    c0 = Vector(centre)
    tris = list(faces)
    for i, (a, b, d) in enumerate(tris):
        fn = (out[b] - out[a]).cross(out[d] - out[a])
        if fn.dot((out[a] + out[b] + out[d]) / 3 - c0) < 0:
            tris[i] = (a, d, b)
    vn = [Vector((0, 0, 0)) for _ in out]
    fns = []
    for a, b, d in tris:
        fn = (out[b] - out[a]).cross(out[d] - out[a])
        fns.append(fn)
        for i in (a, b, d):
            vn[i] += fn
    vn = [x.normalized() if x.length > 1e-12 else Vector((0, 1, 0)) for x in vn]
    cols = [col_fn(out[i], vn[i]) for i in range(len(out))]
    for (a, b, d), fn in zip(tris, fns):
        if fn.length < 1e-14:
            continue
        ax = max(range(3), key=lambda k: abs(fn[k]))
        uvs = []
        for i in (a, b, d):
            p = out[i]
            u, w = (p.z, p.y) if ax == 0 else ((p.x, p.z) if ax == 1 else (p.x, p.y))
            uvs.append((u / tile, w / tile))
        g.poly([out[a], out[b], out[d]], uvs, [vn[a], vn[b], vn[d]], [cols[a], cols[b], cols[d]], mat)


def glow(g, centre, radii, col, rng, rot=None):
    """An emissive bead (the `glow` material: unlit, vertex colour x HDR gain -> bloom)."""
    lump(g, centre, radii, rng, M_GLOW, lambda p, n: col, rough=0.05, cuts=0, detail=2, rot=rot or quat_y(0.0))


def card(g, rect, base, up, side, h, w, tint, bend=0.25, segs=3):
    """A bent alpha card from the undergrowth atlas: `rect` (x, y, w, h px) rooted at `base`,
    rising along `up` and drooping by `bend`, `side` = its width axis."""
    x, y, rw, rh = rect
    u0, u1 = x / AW, (x + rw) / AW
    vb, vt = 1 - (y + rh) / AH, 1 - y / AH
    up, side = Vector(up).normalized(), Vector(side).normalized()
    nrm = side.cross(up).normalized()
    rows = []
    for k in range(segs + 1):
        t = k / segs
        c = Vector(base) + up * (h * t) - Vector((0, 1, 0)) * (bend * h * t * t)
        rows.append(c)
    for k in range(segs):
        t0, t1 = k / segs, (k + 1) / segs
        a0, a1 = rows[k] - side * (w / 2), rows[k] + side * (w / 2)
        b0, b1 = rows[k + 1] - side * (w / 2), rows[k + 1] + side * (w / 2)
        c0 = scale(tint, 0.6 + 0.4 * t0)
        c1 = scale(tint, 0.6 + 0.4 * t1)
        vv0, vv1 = vb + (vt - vb) * t0, vb + (vt - vb) * t1
        g.poly([a0, a1, b1, b0], [(u0, vv0), (u1, vv0), (u1, vv1), (u0, vv1)], [nrm] * 4, [c0, c0, c1, c1], M_CARD)


def rag(g, rng, top, side, down, width, length, mat, col, cols=7, rows=7, sway=0.04, ragged=0.45, fold=0.03,
        outward=None):
    """A hanging strip of cloth / hide from the line `top` +- side*width/2, falling along `down`,
    with a torn, uneven hem (`ragged` = fraction of length the tatters vary) and soft folds."""
    side, down = Vector(side).normalized(), Vector(down).normalized()
    nrm = Vector(outward) if outward is not None else side.cross(down)
    lens = [length * (1.0 - ragged * rng.uniform() ** 0.7) for _ in range(cols + 1)]
    for j in range(1, cols):  # tatters: alternate long and short tongues
        if rng.uniform() < 0.4:
            lens[j] *= rng.uniform(0.55, 0.8)
    grid = []
    ph = rng.uniform(0, 6.28)
    for j in range(cols + 1):
        u = j / cols - 0.5
        col_pts = []
        for i in range(rows + 1):
            t = i / rows
            p = Vector(top) + side * (u * width) + down * (lens[j] * t)
            p += nrm * (fold * math.sin(u * 13.0 + ph + 2.0 * t) + sway * t * t)
            col_pts.append(p)
        grid.append(col_pts)
    sheet(g, grid, mat, lambda a, b: scale(col, 0.75 + 0.25 * (1 - b) * (0.85 + 0.3 * rng.uniform())), tile=0.6,
          double=True)


def shift(b, pivot):
    """Re-centre a piece authored in root space on its pivot (the Builder stores Blender coords)."""
    o = bl(pivot)
    b.verts = [(x - o.x, y - o.y, z - o.z) for (x, y, z) in b.verts]
    return b


# ─────────────────────────────────────────────────────────────── shared colour helpers
def bark_col(rng, base=(0.45, 0.39, 0.33), moss=(0.16, 0.22, 0.05), moss_amt=0.7, ground=0.0):
    nz = Noise(rng, 4, 2.2)
    fine = Noise(rng, 3, 9.0)

    def f(p, n):
        k = 0.9 + 0.12 * fine(p)
        k *= 1.0 - 0.35 * (1.0 - smoothstep(ground - 0.05, ground + 0.35, p.y))  # damp, earthy feet
        c = scale(base, k)
        # moss on up-facing and north/back-facing bark, in patches
        m = moss_amt * smoothstep(-0.1, 0.7, n.y * 0.8 - n.z * 0.4 + 0.25 * nz(p * 1.5)) * smoothstep(-0.2, 0.5, nz(p))
        return mix(c, scale(moss, 0.8 + 0.3 * fine(p * 0.7)), clamp01(m))
    return f


def rock_col(rng, base=(0.78, 0.76, 0.72), lichen=(0.62, 0.64, 0.38), amt=0.6, soot=None):
    nz = Noise(rng, 4, 2.0)
    fine = Noise(rng, 3, 8.0)

    def f(p, n):
        k = 0.85 + 0.15 * nz(p * 1.3) + 0.06 * fine(p)
        c = scale(base, k)
        lic = amt * smoothstep(0.25, 0.85, n.y + 0.2 * nz(p * 2.0)) * smoothstep(-0.1, 0.4, fine(p * 0.5))
        c = mix(c, lichen, clamp01(lic))
        if soot is not None:  # scorched toward the molten seams
            c = scale(c, 1.0 - 0.45 * soot(p))
        return c
    return f


# ─────────────────────────────────────────────────────────────── Forest: the treant
T_PIV = {"leg_r": V(-0.26, 0.72, 0.0), "leg_l": V(0.26, 0.72, 0.0), "arm_r": V(0.6, 1.78, 0.0),
         "arm_l": V(-0.6, 1.78, 0.0), "head": V(0.0, 1.86, 0.06)}
T_GLOW = (0.55, 1.0, 0.2)
FERN = LAYOUT["fern"]
GRASS = LAYOUT["grass"]
STALKS = LAYOUT["stalks"]


def gnarl(rng, amp=0.03, ridge=0.022, twist=1.2, freq=1.8, ridges=9, big=0.0):
    """Bark-trunk displacement: lumpy gnarls + twisted vertical furrows (+ `big` low bulges)."""
    nz = Noise(rng, 4, freq)
    fine = Noise(rng, 3, 6.0)
    low = Noise(rng, 3, 0.9)

    def d(p, dr, t):
        th = math.atan2(dr.z, dr.x)
        fur = abs(math.sin(th * ridges * 0.5 + p.y * twist + 1.4 * fine(p * 0.6)))
        return amp * nz(p) + ridge * (fur ** 0.5 - 0.6) + big * low(p)
    return d


def treant_face(p, dr, t):
    """The face grown into the upper trunk (front, +Z): brow ridge, sunken knot sockets, a ridge of
    nose, cheek burls and a split-bark mouth gash."""
    front = smoothstep(0.25, 0.75, dr.z)
    if front <= 0.0:
        return 0.0
    x, y = p.x, p.y
    e = 0.0
    for sx in (-1, 1):
        e -= 0.15 * math.exp(-(((x - sx * 0.14) / 0.075) ** 2 + ((y - 1.57) / 0.065) ** 2))  # sockets
        # brow: a heavy ridge slanting down to the middle (a scowl)
        by = 1.69 - 0.07 * (0.22 - min(abs(x), 0.22)) / 0.22
        e += 0.09 * math.exp(-(((x - sx * 0.13) / 0.12) ** 2 + ((y - by) / 0.04) ** 2))
        e += 0.06 * math.exp(-(((x - sx * 0.19) / 0.08) ** 2 + ((y - 1.42) / 0.07) ** 2))  # cheek burls
    e += 0.1 * math.exp(-((x / 0.045) ** 2 + ((y - 1.5) / 0.09) ** 2))  # long nose ridge
    e += 0.07 * math.exp(-((x / 0.06) ** 2 + ((y - 1.42) / 0.035) ** 2))  # nose knot
    my = 1.29 - 0.6 * x * x  # a downturned split
    e -= 0.13 * math.exp(-((x / 0.2) ** 6 + ((y - my) / 0.035) ** 2))  # mouth gash
    e += 0.04 * math.exp(-((x / 0.2) ** 6 + ((y - my - 0.06) / 0.025) ** 2))  # lip of bark over it
    return e * front


def treant_torso(rng):
    b = Builder()
    g = G(b)
    base_col = bark_col(rng, moss_amt=0.75)
    gn = gnarl(rng, amp=0.035, ridge=0.035, ridges=7, big=0.05)

    def col(p, n):  # the face's hollows darken to wet heartwood
        c = base_col(p, n)
        f = treant_face(p, n, 0.0)
        return scale(c, 1.0 - 0.8 * smoothstep(0.02, 0.1, -f)) if f < 0 else c

    def trunk_disp(p, dr, t):
        calm = smoothstep(0.3, 0.8, dr.z) * smoothstep(1.2, 1.4, p.y) * (1.0 - smoothstep(1.72, 1.85, p.y))
        return gn(p, dr, t) * (1.0 - 0.7 * calm) + treant_face(p, dr, t)

    # Trunk: from the hip mass up through a waisted belly to broad shoulders, round at the top
    # (the head's crown sits on it and yaws - a round collar hides the joint).
    prof = [(0.36, (0.3, 0.26), 0.0), (0.5, (0.4, 0.33), 0.0), (0.62, (0.42, 0.34), 0.0), (0.8, (0.4, 0.33), 0.01), (0.98, (0.36, 0.31), 0.02),
            (1.16, (0.38, 0.33), 0.03), (1.34, (0.42, 0.36), 0.04), (1.52, (0.43, 0.36), 0.05),
            (1.66, (0.42, 0.34), 0.05), (1.78, (0.36, 0.31), 0.06), (1.9, (0.3, 0.29), 0.06)]
    pts, radii = [], []
    for k in range(len(prof) - 1):
        for s in range(4):
            f = s / 4
            y0, r0, z0 = prof[k]
            y1, r1, z1 = prof[k + 1]
            pts.append(V(0.0, y0 + (y1 - y0) * f, z0 + (z1 - z0) * f))
            radii.append((r0[0] + (r1[0] - r0[0]) * f, r0[1] + (r1[1] - r0[1]) * f))
    pts.append(V(0.0, prof[-1][0], prof[-1][2]))
    radii.append(prof[-1][1])
    sculpt(g, pts, radii, M_BARK, col, sides=48, disp=trunk_disp, tile=0.8, caps=(True, True), ref=(1, 0, 0), tip=0.3)
    # Shoulder burls the boughs grow out of.
    for sx in (-1, 1):
        lump(g, V(sx * 0.44, 1.66, -0.02), (0.2, 0.19, 0.2), rng, M_BARK, base_col, rough=0.25, cuts=0, detail=3,
             tile=0.8)
    # Splintered heartwood teeth in the split of the mouth.
    for k in range(7):
        x = -0.15 + 0.3 * k / 6
        my = 1.29 - 0.6 * x * x
        for up in (1, -1):
            if (k + (up > 0)) % 2:
                continue
            root = V(x, my + up * 0.04, 0.33)
            sculpt(g, [root, V(x + rng.uniform(-0.01, 0.01), my + up * 0.005, 0.355)], [0.016, 0.003], M_BARK,
                   lambda p, n: (0.72, 0.62, 0.46), sides=5, tile=0.15)
    # A sickly glow deep in each knot socket.
    for sx in (-1, 1):
        glow(g, V(sx * 0.14, 1.57, 0.27), (0.036, 0.026, 0.02), T_GLOW, rng)
    # Gnarled side roots / bark ribs climbing the trunk.
    for a0, h0, h1 in ((2.3, 0.55, 1.5), (3.6, 0.6, 1.3), (-0.6, 0.55, 1.1), (4.4, 0.7, 1.6)):
        pts = []
        for k in range(10):
            t = k / 9
            y = h0 + (h1 - h0) * t
            a = a0 + 0.5 * t
            pts.append(V(math.cos(a) * 0.4 * (1.0 - 0.1 * t), y, math.sin(a) * 0.34 * (1.0 - 0.1 * t) + 0.03))
        sculpt(g, pts, [0.05 * (1 - 0.6 * t / 9) for t in range(10)], M_BARK, col, sides=8,
               disp=gnarl(rng, amp=0.012, ridge=0.006), tile=0.6)
    # Bracket fungus shelves stepping up the flank and back.
    fungus(g, rng, [(V(-0.4, 1.02, 0.1), -1.3), (V(-0.36, 0.86, 0.2), -1.0),
                    (V(0.34, 1.24, -0.2), 1.0), (V(0.05, 0.9, -0.33), 3.0)])
    # Ferns and moss sprigs out of the crotches.
    for p, az in ((V(-0.44, 1.8, 0.0), -1.8), (V(0.47, 1.8, -0.05), 1.6), (V(-0.2, 0.75, 0.28), -0.6)):
        for k in range(3):
            a = az + (k - 1) * 0.7
            up = V(math.cos(a) * 0.8, 0.9, math.sin(a) * 0.8)
            card(g, FERN[k % len(FERN)], p, up, V(-math.sin(a), 0, math.cos(a)), 0.32, 0.12, (0.55, 0.7, 0.4), 0.3)
    return b


def fungus(g, rng, spots):
    """Bracket fungus: shelves of flattened half-discs, ochre on top, pale beneath."""
    for p, az in spots:
        out = V(math.sin(az), 0.0, math.cos(az))
        for k in range(rng.integers(1, 3)):
            s = rng.uniform(0.07, 0.11) * (1 - 0.3 * k)
            c = p + V(0, -0.09 * k, 0) + out * (s * 0.55)
            lump(g, c, (s * 1.3, s * 0.38, s), rng, M_HIDE,
                 lambda q, n: mix((0.82, 0.76, 0.62), (0.42, 0.32, 0.22), smoothstep(-0.2, 0.5, n.y)),
                 rough=0.25, cuts=1, detail=2, rot=quat_y(az) @ quat_x(0.15), tile=0.3)


def treant_leg(rng, sx):
    b = Builder()
    g = G(b)
    col = bark_col(rng, base=(0.36, 0.31, 0.26), moss_amt=0.5)
    piv = T_PIV["leg_r" if sx < 0 else "leg_l"]
    # A short gnarled trunk-thigh that flares into roots gripping the ground.
    pts = curve(piv + V(-sx * 0.04, 0.2, 0), V(piv.x * 1.15, 0.12, 0.02), bend=(sx * 0.03, 0, 0.03), n=10)
    sculpt(g, pts, [0.19 - 0.04 * math.sin(math.pi * k / 10) + 0.04 * (k / 10) ** 3 for k in range(11)], M_BARK, col,
           sides=20, disp=gnarl(rng, amp=0.02, ridge=0.012), tile=0.7, caps=(True, False))
    foot = V(piv.x * 1.15, 0.1, 0.02)
    for k, az in enumerate((-0.2, 0.45, 1.1, 2.6, 3.4 + sx * 0.4)):
        a = az if sx > 0 else math.pi - az
        d = V(math.sin(a), 0.0, math.cos(a))
        ln = rng.uniform(0.32, 0.5) if k < 3 else rng.uniform(0.2, 0.3)
        p0 = foot + V(0, 0.06, 0) + d * 0.05
        p1 = foot + d * ln + V(0, -0.14, 0)
        pts = curve(p0, p1, bend=(0, 0.06, 0), n=8, wob=0.012, rng=rng)
        sculpt(g, pts, [0.1 * (1 - k2 / 8) ** 0.8 + 0.012 for k2 in range(9)], M_BARK, col, sides=10,
               disp=gnarl(rng, amp=0.012, ridge=0.006), tile=0.6)
    return shift(b, piv)


def treant_arm(rng, sx):
    b = Builder()
    g = G(b)
    col = bark_col(rng, base=(0.36, 0.31, 0.26), moss_amt=0.8)
    piv = T_PIV["arm_r" if sx > 0 else "arm_l"]
    sh = piv + V(-sx * 0.08, 0.04, 0.0)
    elbow = piv + V(sx * 0.14, -0.5, -0.02)
    wrist = piv + V(sx * 0.1, -0.98, 0.16)
    pts = curve(sh, elbow, bend=(sx * 0.05, 0, 0), n=8) + curve(elbow, wrist, bend=(sx * 0.03, 0, -0.03), n=8)[1:]
    nn = len(pts)
    sculpt(g, pts, [0.13 * (1 - 0.45 * k / (nn - 1)) + 0.02 * math.exp(-((k - 8) / 2.0) ** 2) for k in range(nn)],
           M_BARK, col, sides=16, disp=gnarl(rng, amp=0.02, ridge=0.012, freq=2.5), tile=0.6)
    lump(g, elbow + V(0, 0.02, -0.02), (0.11, 0.12, 0.11), rng, M_BARK, col, rough=0.2, cuts=0, detail=2)
    # A broken side branch off the elbow.
    sp = curve(elbow, elbow + V(sx * 0.28, 0.12, -0.12), bend=(0, 0.04, 0), n=5)
    sculpt(g, sp, [0.045 * (1 - k / 5) + 0.008 for k in range(6)], M_BARK, col, sides=7, tile=0.4)
    # Twig claws: five crooked fingers curling forward.
    hand_d = (wrist - elbow).normalized()
    for k in range(5):
        a = (k - 2) * 0.32
        d = (quat_z(sx * a * 0.8) @ quat_x(-0.35 + rng.uniform(-0.15, 0.15)) @ hand_d).normalized()
        ln = rng.uniform(0.24, 0.36) * (0.75 if k in (0, 4) else 1.0)
        tipp = wrist + d * ln + V(0, 0, 0.1)
        fp = curve(wrist - hand_d * 0.03, tipp, bend=(0, 0.02, 0.05), n=6, wob=0.008, rng=rng)
        sculpt(g, fp, [0.035 * (1 - j / 6) ** 0.8 + 0.004 for j in range(7)], M_BARK, col, sides=7, tile=0.35)
    # Hanging moss beard off the forearm.
    for k in range(4):
        p = elbow.lerp(wrist, 0.2 + 0.2 * k) + V(0, -0.06, -0.02)
        card(g, GRASS[k % len(GRASS)], p, V(0, -1, 0.1), V(1, 0, 0), 0.16, 0.12, (0.38, 0.5, 0.2), bend=-0.1)
    return shift(b, piv)


def treant_head(rng):
    """The crown: the broken top of the trunk sprouting antler boughs, ferns and moss."""
    b = Builder()
    g = G(b)
    col = bark_col(rng, base=(0.36, 0.31, 0.26), moss_amt=1.0)
    piv = T_PIV["head"]
    # A collar of bark over the trunk top (round, so the yaw never opens a seam).
    pts = [piv + V(0, -0.1 + 0.05 * k, 0) for k in range(6)]
    sculpt(g, pts, [0.31, 0.32, 0.3, 0.27, 0.22, 0.14], M_BARK, col, sides=32, disp=gnarl(rng, amp=0.03, ridge=0.03),
           tile=0.7, caps=(False, True), tip=0.4)
    # Antler boughs: thick, forking, crooked.
    def bough(p0, d, ln, r, depth):
        p1 = p0 + d * ln
        pts = curve(p0, p1, bend=Vector(rng.normal(size=3)) * ln * 0.12, n=6)
        sculpt(g, pts, [r * (1 - 0.55 * k / 6) for k in range(7)], M_BARK, col, sides=max(6, int(12 * r / 0.08)),
               disp=gnarl(rng, amp=0.008, ridge=0.006, freq=3.0), tile=0.45)
        if depth > 0:
            for s in (-1, 1):
                nd = (quat_z(s * rng.uniform(0.35, 0.6)) @ quat_x(rng.uniform(-0.4, 0.4)) @ d).normalized()
                bough(p1 - d * 0.02, (nd + V(0, 0.25, 0)).normalized(), ln * rng.uniform(0.5, 0.7), r * 0.5, depth - 1)
    for sx, sz in ((-1, 0.2), (1, -0.1), (-0.3, -0.9), (0.4, 0.8)):
        d = V(sx * 0.7, 1.0, sz * 0.5).normalized()
        bough(piv + V(sx * 0.12, 0.12, sz * 0.1), d, rng.uniform(0.3, 0.42), 0.075, 2)
    # Ferns crowning it.
    for k in range(9):
        a = k / 7 * 6.283 + rng.uniform(-0.3, 0.3)
        up = V(math.cos(a) * 0.7, 1.0, math.sin(a) * 0.7)
        card(g, FERN[k % len(FERN)], piv + V(math.cos(a) * 0.1, 0.16, math.sin(a) * 0.1), up,
             V(-math.sin(a), 0, math.cos(a)), rng.uniform(0.32, 0.45), 0.14, (0.5, 0.68, 0.35), 0.35)
    return shift(b, piv)


# ─────────────────────────────────────────────────────────────── Rocky: the golem
G_PIV = {"leg_r": V(-0.3, 0.74, 0.0), "leg_l": V(0.3, 0.74, 0.0), "arm_r": V(0.66, 1.6, 0.0),
         "arm_l": V(-0.66, 1.6, 0.0), "head": V(0.0, 1.78, 0.06)}
MOLTEN = (1.0, 0.32, 0.05)


def seam(g, rng, pts, r=0.018):
    """A molten seam glowing out of a crack between stones (a thin, slightly wavy glow tube)."""
    pts = [Vector(p) for p in pts]
    sculpt(g, pts, [r * (0.6 + 0.4 * math.sin(math.pi * k / (len(pts) - 1))) + 0.004 for k in range(len(pts))],
           M_GLOW, lambda p, n: MOLTEN, sides=6, tile=0.3)


def golem_rock(g, rng, c, r, rot=None, mat=M_ROCK, lichen=0.6, cuts=3, rough=0.1, soot=None):
    """A fractured field boulder: many planar breaks (angular, not a ball), low-frequency roughness."""
    lump(g, c, r, rng, mat, rock_col(rng, amt=lichen, soot=soot), rough=0.06, cuts=cuts + 4, detail=3 if max(r) >= 0.22 else 2,
         rot=rot or quat_y(rng.uniform(0, 6.28)) @ quat_x(rng.uniform(-0.2, 0.2)), tile=0.9, freq=1.6,
         cut=(0.5, 0.78))


def golem_torso(rng):
    b = Builder()
    g = G(b)
    core = V(0.0, 1.16, 0.27)
    soot = lambda p: math.exp(-((p - core).length / 0.22) ** 2)  # noqa: E731
    # Pelvis, belly, two chest slabs split by the molten fissure, back slab, shoulder crags, neck.
    golem_rock(g, rng, V(0.0, 0.62, 0.0), (0.44, 0.24, 0.34), rot=quat_y(0.2))
    golem_rock(g, rng, V(0.02, 0.88, 0.04), (0.38, 0.22, 0.32), mat=M_SROCK, rot=quat_y(-0.4))
    for sx in (-1, 1):
        golem_rock(g, rng, V(sx * 0.28, 1.24, 0.02), (0.3, 0.4, 0.36), rot=quat_y(sx * 0.3) @ quat_z(sx * 0.12),
                   soot=soot)
        golem_rock(g, rng, V(sx * 0.48, 1.56, -0.04), (0.28, 0.22, 0.28), rot=quat_y(sx * 0.6) @ quat_z(-sx * 0.3),
                   mat=M_SROCK, lichen=0.9)
    golem_rock(g, rng, V(0.0, 1.22, -0.26), (0.46, 0.42, 0.24), mat=M_SROCK, rot=quat_x(0.15))
    golem_rock(g, rng, V(0.0, 1.6, -0.04), (0.26, 0.14, 0.24))
    # Small wedge stones jammed into the joints.
    for p in (V(-0.3, 0.76, 0.24), V(0.32, 0.8, 0.2), V(0.4, 1.0, -0.15), V(-0.42, 1.05, -0.1), V(0.0, 1.46, 0.24)):
        golem_rock(g, rng, p, (0.09, 0.07, 0.08), cuts=2, rough=0.15)
    # The molten heart in the chest fissure and its seams out along the cracks.
    lump(g, core + V(0, 0, -0.13), (0.09, 0.22, 0.12), rng, M_GLOW, lambda p, n: (1.0, 0.4, 0.08), rough=0.15,
         cuts=0, detail=2)
    seam(g, rng, [V(-0.42, 0.98, 0.15), V(-0.3, 0.86, 0.22), V(-0.12, 0.8, 0.27), V(0.12, 0.82, 0.26),
                  V(0.32, 0.88, 0.21)], 0.014)
    seam(g, rng, [V(0.0, 1.42, 0.24), V(0.22, 1.5, 0.22), V(0.42, 1.44, 0.14)], 0.012)
    return b


def golem_head(rng):
    b = Builder()
    g = G(b)
    piv = G_PIV["head"]
    golem_rock(g, rng, piv + V(0, 0.08, -0.02), (0.27, 0.24, 0.26), rot=quat_y(0.15), cuts=4, lichen=0.9)
    # A heavy brow shelf, a jutting jaw stone, a broken crag off the crown.
    golem_rock(g, rng, piv + V(0, 0.15, 0.17), (0.25, 0.07, 0.12), rot=quat_x(-0.15), cuts=2, lichen=0.8)
    golem_rock(g, rng, piv + V(0, -0.08, 0.12), (0.2, 0.1, 0.14), mat=M_SROCK, cuts=2, lichen=0.2)
    golem_rock(g, rng, piv + V(-0.15, 0.3, -0.08), (0.12, 0.1, 0.1), rot=quat_z(0.6), cuts=2)
    # Molten eye slits glaring from under the brow, a seam of a mouth.
    for sx in (-1, 1):
        glow(g, piv + V(sx * 0.1, 0.07, 0.235), (0.05, 0.022, 0.02), MOLTEN, rng, rot=quat_z(sx * 0.25))
    seam(g, rng, [piv + V(-0.1, -0.02, 0.24), piv + V(0, -0.01, 0.26), piv + V(0.1, -0.03, 0.24)], 0.01)
    return shift(b, piv)


def golem_arm(rng, sx):
    b = Builder()
    g = G(b)
    piv = G_PIV["arm_r" if sx > 0 else "arm_l"]
    golem_rock(g, rng, piv + V(sx * 0.04, -0.02, 0.0), (0.24, 0.22, 0.24), lichen=0.9)
    golem_rock(g, rng, piv + V(sx * 0.06, -0.3, 0.0), (0.18, 0.22, 0.18), mat=M_SROCK)
    golem_rock(g, rng, piv + V(sx * 0.07, -0.53, 0.04), (0.16, 0.1, 0.16), cuts=2)
    golem_rock(g, rng, piv + V(sx * 0.06, -0.74, 0.07), (0.19, 0.2, 0.19), mat=M_SROCK)
    golem_rock(g, rng, piv + V(sx * 0.06, -1.0, 0.12), (0.26, 0.23, 0.26), cuts=4, lichen=0.3)  # boulder fist
    for k in range(3):
        golem_rock(g, rng, piv + V(sx * 0.06 + (k - 1) * 0.11, -0.96, 0.32), (0.07, 0.08, 0.07), cuts=2, lichen=0.1)
    # Glow in the joints between the stones.
    for y in (-0.44, -0.62):
        seam(g, rng, [piv + V(sx * 0.07 + 0.14 * math.cos(a), y + 0.02 * math.sin(3 * a), 0.04 + 0.14 * math.sin(a))
                      for a in np.linspace(-0.4, 3.3, 7)], 0.014)
    return shift(b, piv)


def golem_leg(rng, sx):
    b = Builder()
    g = G(b)
    piv = G_PIV["leg_l" if sx > 0 else "leg_r"]
    golem_rock(g, rng, piv + V(sx * 0.02, -0.16, 0.0), (0.22, 0.24, 0.22), mat=M_SROCK)
    golem_rock(g, rng, piv + V(sx * 0.03, -0.46, 0.02), (0.19, 0.22, 0.2))
    golem_rock(g, rng, V(piv.x + sx * 0.04, 0.08, 0.08), (0.25, 0.13, 0.33), cuts=3, lichen=0.3)  # boulder foot
    seam(g, rng, [piv + V(sx * 0.03 + 0.15 * math.cos(a), -0.3, 0.02 + 0.15 * math.sin(a))
                  for a in np.linspace(-0.3, 3.4, 7)], 0.013)
    return shift(b, piv)


# ─────────────────────────────────────────────────────────────── Desert: the revenant
R_PIV = {"leg_r": V(-0.18, 0.5, 0.0), "leg_l": V(0.18, 0.5, 0.0), "arm_r": V(0.5, 1.7, 0.0),
         "arm_l": V(-0.5, 1.7, 0.0), "head": V(0.0, 1.82, 0.04)}
SPECTRE = (0.45, 0.9, 1.0)
SURCOAT = (0.11, 0.035, 0.025)  # a faded, sun-rotted red (linear)
BONE = (0.62, 0.55, 0.4)


def rust_col(rng, base=(0.62, 0.6, 0.58), rust=(0.16, 0.07, 0.03), amt=0.65, dust=(0.36, 0.3, 0.2)):
    nz = Noise(rng, 4, 3.0)
    fine = Noise(rng, 3, 11.0)

    def f(p, n):
        r = amt * smoothstep(0.0, 0.6, nz(p) + 0.4 * fine(p))
        c = mix(scale(base, 0.3 * (0.85 + 0.15 * fine(p))), rust, clamp01(r))
        return mix(c, dust, 0.3 * smoothstep(0.5, 0.95, n.y))  # sand settled on the tops
    return f


def revenant_torso(rng):
    b = Builder()
    g = G(b)
    mail = rust_col(rng, base=(0.5, 0.48, 0.46), amt=0.75)
    plate = rust_col(rng, base=(0.66, 0.64, 0.62), amt=0.55)
    # The hauberk: a gaunt mail body, the skirt flaring to the knees.
    prof = [(0.36, (0.32, 0.28)), (0.52, (0.29, 0.25)), (0.72, (0.25, 0.2)), (0.95, (0.2, 0.16)),
            (1.12, (0.22, 0.17)), (1.34, (0.27, 0.2)), (1.52, (0.31, 0.21)), (1.64, (0.3, 0.2)),
            (1.74, (0.2, 0.15)), (1.82, (0.09, 0.08))]
    pts = [V(0.0, y, 0.0) for y, _ in prof]
    nz = Noise(rng, 3, 4.0)
    sculpt(g, pts, [r for _, r in prof], M_IRON, mail, sides=28, tile=0.35,
           disp=lambda p, d, t: 0.006 * nz(p) + 0.004 * math.sin(p.y * 160.0), caps=(False, True))
    # Dented breastplate and fauld, pauldrons of stacked lames, a cracked leather belt.
    lump(g, V(0.0, 1.36, 0.05), (0.26, 0.24, 0.18), rng, M_IRON, plate, rough=0.05, cuts=2, detail=3, tile=0.5,
         rot=quat_y(0.0), cut=(0.8, 0.95))
    for sx in (-1, 1):
        for k in range(3):
            lump(g, V(sx * (0.36 + 0.03 * k), 1.66 - 0.07 * k, 0.0), (0.17 - 0.015 * k, 0.09, 0.17 - 0.01 * k), rng,
                 M_IRON, plate, rough=0.04, cuts=0, detail=3, tile=0.5, rot=quat_z(-sx * (0.35 + 0.12 * k)))
    ring = [V(0.24 * math.cos(a), 0.98 + 0.02 * math.sin(2 * a), 0.18 * math.sin(a)) for a in np.linspace(0, 6.283, 25)]
    sculpt(g, ring, [0.03] * 25, M_HIDE, lambda p, n: (0.35, 0.25, 0.18), sides=6, tile=0.3, caps=(False, False))
    # The surcoat: a front and back panel rotted to tatters, a side flap, and a torn cloak.
    rag(g, rng, V(0.0, 1.52, 0.22), (1, 0, 0), (0, -1, 0.06), 0.34, 1.25, M_CLOTH, SURCOAT, cols=9, rows=9,
        outward=(0, 0, 1))
    rag(g, rng, V(0.0, 1.5, -0.2), (1, 0, 0), (0, -1, -0.05), 0.36, 1.2, M_CLOTH, SURCOAT, cols=9, rows=9,
        outward=(0, 0, -1))
    rag(g, rng, V(0.0, 1.72, -0.2), (1, 0, 0), (0, -1, -0.12), 0.7, 1.55, M_CLOTH, (0.3, 0.26, 0.2), cols=12,
        rows=10, sway=0.08, ragged=0.55, outward=(0, 0, -1))
    return b


def revenant_head(rng):
    b = Builder()
    g = G(b)
    piv = R_PIV["head"]
    eyes = [piv + V(sx * 0.055, 0.02, 0.12) for sx in (-1, 1)]

    def skull_col(p, n):
        c = BONE
        for e in eyes:
            c = scale(c, 1.0 - 0.85 * math.exp(-((p - e).length / 0.045) ** 2))
        c = scale(c, 1.0 - 0.7 * math.exp(-(((p.x - piv.x) / 0.025) ** 2 + ((p.y - piv.y + 0.05) / 0.03) ** 2)))
        return mix(c, (0.55, 0.45, 0.32), 0.3 * smoothstep(-0.2, -0.8, n.y))
    lump(g, piv + V(0, 0.03, 0.01), (0.115, 0.14, 0.135), rng, M_BONE, skull_col, rough=0.04, cuts=0, detail=3,
         tile=0.3)
    lump(g, piv + V(0, -0.1, 0.055), (0.085, 0.05, 0.08), rng, M_BONE, skull_col, rough=0.05, cuts=1, detail=2,
         tile=0.3)  # the jaw, hanging slack
    for e in eyes:  # deep black sockets with a cold spark in each
        lump(g, e + V(0, 0.0, 0.0), (0.042, 0.038, 0.03), rng, M_BONE, lambda p, n: (0.03, 0.03, 0.03), rough=0.1,
             cuts=0, detail=2)
        glow(g, e + V(0, 0, 0.022), (0.016, 0.012, 0.008), SPECTRE, rng)
    lump(g, piv + V(0, -0.035, 0.135), (0.022, 0.03, 0.02), rng, M_BONE, lambda p, n: (0.04, 0.035, 0.03),
         rough=0.1, cuts=0, detail=1)  # nasal cavity
    for k in range(6):  # a row of teeth along the upper jaw
        x = -0.05 + 0.02 * k
        lump(g, piv + V(x, -0.075, 0.125 - 0.25 * x * x), (0.009, 0.014, 0.008), rng, M_BONE,
             lambda p, n: (0.8, 0.74, 0.6), rough=0.05, cuts=0, detail=1)
    # An open bascinet over the cranium, and a mail collar under the jaw.
    plate = rust_col(rng, base=(0.6, 0.58, 0.56), amt=0.7)
    pts = [piv + V(0, 0.07 + 0.045 * k, -0.01 - 0.012 * k) for k in range(6)]
    sculpt(g, pts, [0.152, 0.155, 0.148, 0.128, 0.09, 0.03], M_IRON, plate, sides=24, tile=0.4, caps=(False, True),
           tip=0.6)
    pts = [piv + V(0, -0.1 - 0.05 * k, -0.02) for k in range(4)]
    sculpt(g, pts, [(0.1, 0.1), (0.13, 0.12), (0.18, 0.15), (0.24, 0.18)], M_IRON,
           rust_col(rng, base=(0.48, 0.46, 0.44), amt=0.8), sides=20, tile=0.3, caps=(False, False))
    return shift(b, piv)


def revenant_arm(rng, sx):
    b = Builder()
    g = G(b)
    piv = R_PIV["arm_r" if sx > 0 else "arm_l"]
    mail = rust_col(rng, base=(0.5, 0.48, 0.46), amt=0.75)
    plate = rust_col(rng, base=(0.64, 0.62, 0.6), amt=0.6)
    elbow = piv + V(sx * 0.06, -0.46, -0.02)
    wrist = piv + V(sx * 0.04, -0.86, 0.14)
    sculpt(g, curve(piv + V(-sx * 0.04, 0.05, 0), elbow, n=6), [0.068, 0.06, 0.054, 0.05, 0.048, 0.047, 0.046],
           M_IRON, mail, sides=12, tile=0.3)  # a gaunt mail sleeve
    sculpt(g, curve(elbow, wrist, n=6), [0.04, 0.048, 0.05, 0.048, 0.044, 0.04, 0.036], M_IRON, plate, sides=12,
           tile=0.35)  # vambrace
    lump(g, elbow, (0.07, 0.07, 0.07), rng, M_IRON, plate, rough=0.05, cuts=1, detail=2, tile=0.3)
    rag(g, rng, piv + V(sx * 0.05, -0.05, 0.0), (0, 0, 1), (sx * 0.2, -1, 0), 0.16, 0.45, M_CLOTH, SURCOAT, cols=4,
        rows=5, outward=(sx, 0, 0))
    hand_d = (wrist - elbow).normalized()
    bone = lambda p, n: scale(BONE, 0.85)  # noqa: E731
    if sx > 0:
        # Knuckles of bone round a leather grip; a notched, rust-eaten longsword swept forward.
        grip = wrist + hand_d * 0.06
        blade_d = V(0.0, -0.42, 0.9).normalized()
        for k in range(4):
            a = 6.283 * k / 4
            lump(g, grip + V(0.035 * math.cos(a), 0.02 * (k - 1.5), 0.035 * math.sin(a)), (0.022, 0.02, 0.022), rng,
                 M_BONE, bone, rough=0.05, cuts=0, detail=1)
        sculpt(g, [grip - blade_d * 0.12, grip + blade_d * 0.06], [0.02, 0.02], M_HIDE, lambda p, n: (0.3, 0.22, 0.15),
               sides=8, tile=0.2)
        lump(g, grip - blade_d * 0.14, (0.03, 0.03, 0.03), rng, M_IRON, plate, rough=0.05, cuts=0, detail=2)
        guard = grip + blade_d * 0.07
        sculpt(g, [guard + V(-0.12, 0.0, 0.0), guard + V(0.12, 0.0, 0.0)], [0.016, 0.016], M_IRON, plate, sides=6,
               tile=0.2)
        nz = Noise(rng, 3, 9.0)
        bl_pts = [guard + blade_d * (0.95 * k / 10) for k in range(11)]
        sculpt(g, bl_pts, [(0.036 * (1 - 0.6 * (k / 10) ** 2) + 0.003, 0.008) for k in range(11)], M_IRON,
               rust_col(rng, base=(0.7, 0.68, 0.66), amt=0.55), sides=8, tile=0.25, ref=(1, 0, 0),
               disp=lambda p, d, t: -0.012 * max(0.0, nz(p)) * abs(d.x), tip=1.2)
    else:
        for k in range(4):
            a = (k - 1.5) * 0.28
            d = (quat_z(sx * a) @ quat_x(-0.4) @ hand_d).normalized()
            fp = curve(wrist, wrist + d * 0.2, bend=(0, 0, 0.03), n=4)
            sculpt(g, fp, [0.014, 0.013, 0.012, 0.01, 0.007], M_BONE, bone, sides=6, tile=0.2)
    return shift(b, piv)


def revenant_leg(rng, sx):
    b = Builder()
    g = G(b)
    piv = R_PIV["leg_l" if sx > 0 else "leg_r"]
    plate = rust_col(rng, base=(0.62, 0.6, 0.58), amt=0.65)
    sculpt(g, curve(piv + V(0, 0.15, 0), V(piv.x, 0.1, 0.0), n=6), [0.07, 0.075, 0.07, 0.062, 0.055, 0.05, 0.05],
           M_IRON, plate, sides=12, tile=0.3)
    lump(g, piv + V(0, -0.1, 0.05), (0.07, 0.07, 0.06), rng, M_IRON, plate, rough=0.05, cuts=1, detail=2)  # poleyn
    lump(g, V(piv.x, 0.05, 0.06), (0.065, 0.05, 0.13), rng, M_IRON, plate, rough=0.05, cuts=1, detail=2,
         rot=quat_y(0.0), flat_lo=0.6)  # sabaton
    return shift(b, piv)


# ─────────────────────────────────────────────────────────────── Swamp: the bog hag
H_PIV = {"leg_r": V(-0.26, 0.5, 0.0), "leg_l": V(0.26, 0.5, 0.0), "arm_r": V(0.56, 1.5, 0.06),
         "arm_l": V(-0.56, 1.5, 0.06), "head": V(0.0, 1.62, 0.1)}
HAG_EYE = (1.0, 0.78, 0.15)
RAGS = (0.06, 0.058, 0.035)


def mud_col(rng, base=(0.13, 0.1, 0.075), wet=(0.04, 0.032, 0.024), algae=(0.06, 0.075, 0.025)):
    nz = Noise(rng, 4, 2.4)
    fine = Noise(rng, 3, 9.0)

    def f(p, n):
        c = mix(base, wet, clamp01(0.5 + 0.6 * nz(p) - 0.4 * n.y))  # drier crust on top, wet below
        c = mix(c, algae, 0.5 * smoothstep(0.2, 0.7, fine(p * 0.4) + 0.3 * nz(p * 2.0)))
        return scale(c, 0.9 + 0.12 * fine(p))
    return f


def skin_col(rng):
    nz = Noise(rng, 3, 5.0)
    return lambda p, n: scale(mix((0.13, 0.15, 0.09), (0.06, 0.06, 0.04), clamp01(0.5 + 0.7 * nz(p))), 0.95)


def hag_torso(rng):
    b = Builder()
    g = G(b)
    mud = mud_col(rng)
    lumps = Noise(rng, 4, 2.6)
    # A hunched mass of bog mud: the spine bows back into a hump and the shoulders roll forward.
    spine = curve(V(0.0, 0.42, 0.0), V(0.0, 1.5, 0.08), bend=(0.0, 0.0, -0.2), n=12)
    rr = [(0.3, 0.26), (0.36, 0.31), (0.4, 0.34), (0.41, 0.35), (0.4, 0.36), (0.39, 0.37), (0.38, 0.37),
          (0.37, 0.36), (0.36, 0.33), (0.34, 0.3), (0.3, 0.26), (0.22, 0.2), (0.14, 0.13)]
    sculpt(g, spine, rr, M_EARTH, mud, sides=32, tile=0.6, disp=lambda p, d, t: 0.05 * lumps(p), caps=(True, True),
           tip=0.15)
    for sx in (-1, 1):  # rounded shoulders out to the arm pivots
        lump(g, V(sx * 0.44, 1.44, 0.04), (0.17, 0.14, 0.16), rng, M_EARTH, mud, rough=0.2, cuts=0, detail=3, tile=0.5)
    lump(g, V(0.0, 1.38, -0.22), (0.3, 0.26, 0.24), rng, M_EARTH, mud, rough=0.18, cuts=0, detail=3, tile=0.6)  # hump
    for p, r in ((V(-0.26, 1.0, 0.24), 0.1), (V(0.28, 0.82, 0.22), 0.09), (V(0.2, 1.26, -0.3), 0.12),
                 (V(-0.3, 1.2, -0.2), 0.11)):
        lump(g, p, (r, r * 0.85, r), rng, M_EARTH, mud, rough=0.25, cuts=0, detail=2, tile=0.5)
    # Mud dripping off the belly.
    for k in range(6):
        a = -0.9 + 1.8 * k / 5
        top = V(math.sin(a) * 0.36, 0.7 + 0.05 * math.cos(3 * a), math.cos(a) * 0.3)
        ln = rng.uniform(0.08, 0.2)
        sculpt(g, [top, top + V(0, -ln * 0.6, 0.01), top + V(0, -ln, 0.0)], [0.035, 0.025, 0.012], M_EARTH, mud,
               sides=6, tile=0.3)
    # Rags: a shawl over the shoulders and a tattered skirt.
    for a in np.linspace(-2.6, 2.6, 7):
        top = V(math.sin(a) * 0.3, 1.46 - 0.05 * abs(a), math.cos(a) * 0.24 - 0.04)
        out = V(math.sin(a), 0.0, math.cos(a))
        rag(g, rng, top, V(math.cos(a), 0, -math.sin(a)), out * 0.35 + V(0, -1, 0), 0.32, rng.uniform(0.45, 0.7),
            M_CLOTH, scale(RAGS, rng.uniform(0.8, 1.15)), cols=5, rows=6, outward=out, ragged=0.6)
    for a in np.linspace(-3.0, 3.0, 9):
        top = V(math.sin(a) * 0.38, 0.86, math.cos(a) * 0.32)
        out = V(math.sin(a), 0.0, math.cos(a))
        rag(g, rng, top, V(math.cos(a), 0, -math.sin(a)), out * 0.2 + V(0, -1, 0), 0.3, rng.uniform(0.5, 0.75),
            M_CLOTH, scale((0.05, 0.06, 0.03), rng.uniform(0.8, 1.2)), cols=5, rows=6, outward=out, ragged=0.65)
    # Reeds and sedge stuck in the mud of the hump and the hips.
    for k in range(14):
        a = rng.uniform(-3.1, 3.1)
        hump = k < 9
        base = (V(math.sin(a) * 0.22, 1.42, -0.22 + math.cos(a) * 0.15) if hump else
                V(math.sin(a) * 0.36, 0.86, math.cos(a) * 0.3))
        up = V(math.sin(a) * 0.5, 1.0, (-0.6 if hump else math.cos(a) * 0.4))
        rect = STALKS[0] if k % 3 == 0 else GRASS[k % len(GRASS)]
        card(g, rect, base, up, V(math.cos(a), 0, -math.sin(a)), rng.uniform(0.35, 0.6), rng.uniform(0.18, 0.3),
             (0.4, 0.38, 0.2), bend=0.2)
    return b


def hag_head(rng):
    b = Builder()
    g = G(b)
    piv = H_PIV["head"]
    skin = skin_col(rng)
    eyes = [piv + V(sx * 0.085, 0.05, 0.19) for sx in (-1, 1)]

    def face_col(p, n):
        c = skin(p, n)
        for e in eyes:
            c = scale(c, 1.0 - 0.75 * math.exp(-((p - e).length / 0.05) ** 2))
        return c
    lump(g, piv + V(0, 0.04, 0.02), (0.19, 0.2, 0.2), rng, M_HIDE, face_col, rough=0.1, cuts=0, detail=3, tile=0.3)
    lump(g, piv + V(0, -0.1, 0.1), (0.15, 0.08, 0.12), rng, M_HIDE, face_col, rough=0.1, cuts=0, detail=2, tile=0.3)
    lump(g, piv + V(0, 0.11, 0.15), (0.17, 0.05, 0.08), rng, M_HIDE, face_col, rough=0.15, cuts=0, detail=2,
         tile=0.3)  # heavy brow
    for e in eyes:
        glow(g, e, (0.026, 0.016, 0.014), HAG_EYE, rng)
    # The long hooked nose, warted.
    nose = [piv + V(0, 0.07, 0.19), piv + V(0, 0.02, 0.27), piv + V(0, -0.04, 0.32), piv + V(0, -0.1, 0.32),
            piv + V(0, -0.13, 0.29)]
    sculpt(g, nose, [0.04, 0.038, 0.032, 0.022, 0.01], M_HIDE, skin, sides=10, tile=0.2)
    lump(g, piv + V(0.03, -0.01, 0.29), (0.014, 0.014, 0.014), rng, M_HIDE, skin, rough=0.1, cuts=0, detail=1)
    # A dark mouth with a few broken teeth.
    lump(g, piv + V(0, -0.1, 0.19), (0.09, 0.022, 0.03), rng, M_HIDE, lambda p, n: (0.08, 0.05, 0.04), rough=0.1,
         cuts=0, detail=2)
    for k, x in enumerate((-0.05, -0.015, 0.03, 0.06)):
        tp = piv + V(x, -0.09, 0.21)
        sculpt(g, [tp, tp + V(0, -0.035 - 0.01 * (k % 2), 0.005)], [0.011, 0.003], M_BONE,
               lambda p, n: (0.7, 0.62, 0.42), sides=5, tile=0.1)
    # Matted, weedy hair hanging off the crown down over the shoulders and back.
    hair = lambda p, n: scale((0.03, 0.028, 0.02), 0.8 + 0.3 * max(0.0, n.y))  # noqa: E731
    for k in range(22):
        a = rng.uniform(0.5, 5.8)  # skip the face
        root = piv + V(math.sin(a) * 0.16, 0.16 + 0.04 * math.cos(a), math.cos(a) * 0.16 - 0.02)
        out = V(math.sin(a), 0.0, math.cos(a))
        ln = rng.uniform(0.35, 0.7)
        pts = [root + out * (0.06 * math.sin(math.pi * min(t, 0.5))) + V(0, -ln * t, 0) + out * (0.08 * t)
               + V(*rng.normal(size=3)) * 0.01 for t in np.linspace(0, 1, 7)]
        sculpt(g, pts, [0.035 * (1 - 0.7 * t) + 0.006 for t in np.linspace(0, 1, 7)], M_EARTH, hair, sides=7,
               tile=0.2)
    lump(g, piv + V(0, 0.14, -0.03), (0.2, 0.1, 0.2), rng, M_EARTH, hair, rough=0.2, cuts=0, detail=2, tile=0.2)
    return shift(b, piv)


def hag_arm(rng, sx):
    b = Builder()
    g = G(b)
    piv = H_PIV["arm_r" if sx > 0 else "arm_l"]
    skin = skin_col(rng)
    mud = mud_col(rng)
    elbow = piv + V(sx * 0.14, -0.5, -0.04)
    wrist = piv + V(sx * 0.08, -1.0, 0.18)
    lumpy = Noise(rng, 3, 6.0)
    pts = curve(piv + V(-sx * 0.05, 0.04, 0), elbow, n=6) + curve(elbow, wrist, bend=(0, 0, 0.03), n=6)[1:]
    sculpt(g, pts, [0.085, 0.08, 0.07, 0.062, 0.058, 0.058, 0.064, 0.056, 0.048, 0.044, 0.042, 0.04, 0.038],
           M_EARTH, mud, sides=12, tile=0.35, disp=lambda p, d, t: 0.012 * lumpy(p))
    lump(g, elbow, (0.07, 0.075, 0.07), rng, M_HIDE, skin, rough=0.2, cuts=0, detail=2)
    rag(g, rng, piv + V(sx * 0.06, -0.08, 0.0), (0, 0, 1), (sx * 0.2, -1, 0), 0.18, 0.4, M_CLOTH, RAGS, cols=4, rows=5,
        outward=(sx, 0, 0))
    hand = wrist + (wrist - elbow).normalized() * 0.04
    lump(g, hand, (0.05, 0.06, 0.045), rng, M_HIDE, skin, rough=0.15, cuts=0, detail=2)
    hand_d = (wrist - elbow).normalized()
    for k in range(4):
        a = (k - 1.5) * 0.3
        d = (quat_z(sx * a) @ quat_x(-0.5) @ hand_d).normalized()
        knuckle = hand + d * 0.14
        tipp = knuckle + (d + V(0, -0.2, 0.5)).normalized() * 0.12
        sculpt(g, [hand, hand.lerp(knuckle, 0.5), knuckle], [0.018, 0.016, 0.015], M_HIDE, skin, sides=6, tile=0.15)
        sculpt(g, [knuckle, knuckle.lerp(tipp, 0.5), tipp], [0.013, 0.009, 0.002], M_BONE,
               lambda p, n: (0.42, 0.36, 0.26), sides=6, tile=0.1)  # talons
    return shift(b, piv)


def hag_leg(rng, sx):
    b = Builder()
    g = G(b)
    piv = H_PIV["leg_l" if sx > 0 else "leg_r"]
    mud = mud_col(rng)
    knee = piv + V(sx * 0.04, -0.24, 0.1)
    ankle = V(piv.x + sx * 0.02, 0.08, -0.02)
    pts = curve(piv + V(0, 0.08, 0), knee, n=4) + curve(knee, ankle, n=4)[1:]
    sculpt(g, pts, [0.13, 0.12, 0.11, 0.1, 0.09, 0.075, 0.068, 0.065, 0.065], M_EARTH, mud, sides=12, tile=0.4)
    lump(g, V(ankle.x, 0.04, 0.08), (0.11, 0.05, 0.17), rng, M_EARTH, mud, rough=0.15, cuts=0, detail=2, flat_lo=0.5)
    for k in range(3):
        a = (k - 1) * 0.35
        d = V(math.sin(a), -0.15, math.cos(a)).normalized()
        p0 = V(ankle.x, 0.03, 0.18) + V(math.sin(a) * 0.05, 0, 0)
        sculpt(g, [p0, p0 + d * 0.06, p0 + d * 0.1], [0.018, 0.012, 0.002], M_BONE, lambda p, n: (0.4, 0.34, 0.25),
               sides=6, tile=0.1)
    return shift(b, piv)


MODELS = {
    "warden_treant_torso": treant_torso,
    "warden_treant_head": treant_head,
    "warden_treant_arm_r": lambda rng: treant_arm(rng, 1.0),
    "warden_treant_arm_l": lambda rng: treant_arm(rng, -1.0),
    "warden_treant_leg_r": lambda rng: treant_leg(rng, -1.0),
    "warden_treant_leg_l": lambda rng: treant_leg(rng, 1.0),
    "warden_golem_torso": golem_torso,
    "warden_golem_head": golem_head,
    "warden_golem_arm_r": lambda rng: golem_arm(rng, 1.0),
    "warden_golem_arm_l": lambda rng: golem_arm(rng, -1.0),
    "warden_golem_leg_r": lambda rng: golem_leg(rng, -1.0),
    "warden_golem_leg_l": lambda rng: golem_leg(rng, 1.0),
    "warden_revenant_torso": revenant_torso,
    "warden_revenant_head": revenant_head,
    "warden_revenant_arm_r": lambda rng: revenant_arm(rng, 1.0),
    "warden_revenant_arm_l": lambda rng: revenant_arm(rng, -1.0),
    "warden_revenant_leg_r": lambda rng: revenant_leg(rng, -1.0),
    "warden_revenant_leg_l": lambda rng: revenant_leg(rng, 1.0),
    "warden_hag_torso": hag_torso,
    "warden_hag_head": hag_head,
    "warden_hag_arm_r": lambda rng: hag_arm(rng, 1.0),
    "warden_hag_arm_l": lambda rng: hag_arm(rng, -1.0),
    "warden_hag_leg_r": lambda rng: hag_leg(rng, -1.0),
    "warden_hag_leg_l": lambda rng: hag_leg(rng, 1.0),
}

if __name__ == "__main__":
    clear_scene()
    objs = []
    report = {}
    only = [a for a in sys.argv[sys.argv.index("--") + 1:]] if "--" in sys.argv else []
    for i, (name, fn) in enumerate(MODELS.items()):
        b = fn(np.random.default_rng(7100 + i))
        report[name] = bounds(b)
        objs.append(b.build(name, MATS))
    export_glb(OUT / "wardens.glb", objs)
    for k, v in report.items():
        print(f"{k}: {v}")
    print("WARDENS_DONE")
