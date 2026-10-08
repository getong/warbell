"""Game-ready forest trees + bushes, grown procedurally in Blender and exported to trees.glb.

Each tree is a branching skeleton swept into tapered bark tubes (tileable bark scans wrapped
with world-scaled UVs) plus foliage cards carrying the canopy atlas (foliage.py). Every
species ships two LODs as separate objects, `<variant>_lod0` and `<variant>_lod1`:

  lod0  ~2-3k triangles: full skeleton, ~150 V-folded cards (near: < ~40 units)
  lod1  ~0.6-1k triangles: trunk + main limbs, ~50 larger cards (far: to the 180u cull)

Foliage normals are bent toward "outward from the crown centre" - the standard trick that
makes a cloud of flat cards shade like one volumetric crown instead of a pile of planes.
Vertex colour carries crown self-occlusion (darker inside / underneath) and per-tree tint.

Units are game units (hero ~1.3u tall); base at the origin, Blender Z-up (exported Y-up).
Materials are exported by NAME only: bark_oak / bark_beech / bark_pine / canopy.
"""
import json
import math
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Quaternion, Vector  # noqa: E402
from common import OUT, clear_scene, export_glb  # noqa: E402
from meshkit import Builder  # noqa: E402

LAYOUT = json.loads((OUT / "foliage_layout.json").read_text(encoding="utf-8"))
CW, CH = LAYOUT["canopy"]["size"]
BARK_TILE = 1.1  # world units covered by one bark texture repeat (vertically)


def cell_uv(cell):
    x, y, w, h = cell
    # glTF/Bevy UV origin is top-left; Blender's is bottom-left (the exporter flips V).
    # 5th element: the cell's width/height, so cards keep the spray's proportions.
    return (x / CW, 1 - (y + h) / CH, (x + w) / CW, 1 - y / CH, w / h)


UV_BROAD = cell_uv(LAYOUT["canopy"]["broadleaf"])
UV_CONIFER = cell_uv(LAYOUT["canopy"]["conifer"])


# ------------------------------------------------------------------ skeleton
class Limb:
    def __init__(self, pts, radii, depth):
        self.pts = [Vector(p) for p in pts]
        self.radii = radii
        self.depth = depth


def grow_path(start, direction, length, segs, rng, bend=0.15, gravity=0.0, curl=None):
    pts = [Vector(start)]
    d = Vector(direction).normalized()
    step = length / segs
    for _ in range(segs):
        jitter = Vector((rng.normal(), rng.normal(), rng.normal())) * bend
        d = (d + jitter + Vector((0, 0, gravity))).normalized()
        if curl is not None:
            d = (d + curl * 0.15).normalized()
        pts.append(pts[-1] + d * step)
    return pts


def frames(pts):
    """Parallel-transport frames along a polyline: (tangent, normal, binormal) per point."""
    out = []
    t_prev = (pts[1] - pts[0]).normalized()
    n = t_prev.orthogonal().normalized()
    for i in range(len(pts)):
        if i == 0:
            t = (pts[1] - pts[0]).normalized()
        elif i == len(pts) - 1:
            t = (pts[-1] - pts[-2]).normalized()
        else:
            t = (pts[i + 1] - pts[i - 1]).normalized()
        axis = t_prev.cross(t)
        if axis.length > 1e-6:
            ang = math.asin(min(axis.length, 1.0))
            n = Quaternion(axis.normalized(), ang) @ n
        n = (n - t * n.dot(t)).normalized()
        out.append((t, n, t.cross(n)))
        t_prev = t
    return out


def tube(b, limb, sides, mat, tint, flare=0.0, uv_phase=0.0):
    """Sweep a tapered tube along `limb` with world-scaled bark UVs."""
    fr = frames(limb.pts)
    rings = []
    vacc = uv_phase
    r0 = limb.radii[0]
    u_rep = max(1, round(2 * math.pi * r0 / BARK_TILE * 1.6))
    for i, (p, (t, n, bn)) in enumerate(zip(limb.pts, fr)):
        if i > 0:
            vacc += (limb.pts[i] - limb.pts[i - 1]).length / BARK_TILE
        r = limb.radii[i]
        if flare and i == 0:
            r *= 1.0 + flare
        ring = []
        for s in range(sides + 1):
            a = 2 * math.pi * (s % sides) / sides
            dirv = n * math.cos(a) + bn * math.sin(a)
            # Lumpy root flare on the trunk base ring.
            rr = r * (1.0 + (0.18 * flare * math.sin(a * 5 + 1.3) if i == 0 else 0.0))
            ring.append((b.v(p + dirv * rr), dirv, (s / sides * u_rep, vacc)))
        rings.append(ring)
    for i in range(len(rings) - 1):
        h0 = limb.pts[i].z
        h1 = limb.pts[i + 1].z
        # Ground-contact darkening (moss/soil wicking) on the first 0.6u of trunk.
        c0 = tuple(tint[k] * (0.85 + 0.15 * min(h0 / 0.6, 1.0)) for k in range(3))
        c1 = tuple(tint[k] * (0.85 + 0.15 * min(h1 / 0.6, 1.0)) for k in range(3))
        for s in range(sides):
            a, bb = rings[i][s], rings[i][s + 1]
            c, d = rings[i + 1][s + 1], rings[i + 1][s]
            b.face((a[0], bb[0], c[0], d[0]),
                   [a[2], bb[2], c[2], d[2]],
                   [a[1], bb[1], c[1], d[1]],
                   [c0, c0, c1, c1], mat)
    # Cap the tip so thin twigs don't show a hole.
    tip = rings[-1]
    centre = b.v(limb.pts[-1] + fr[-1][0] * limb.radii[-1] * 0.5)
    for s in range(sides):
        a, bb = tip[s], tip[s + 1]
        b.face((a[0], bb[0], centre), [a[2], bb[2], (0.5, tip[0][2][1])],
               [a[1], bb[1], fr[-1][0]], [tint] * 3, mat)


def card(b, base, up, normal, size, uvr, mat, crown_c, crown_r, tint, rng, fold=0.35, bend_w=0.7):
    """A V-folded foliage card: twig end at `base`, extending along `up`.
    Normals blend the card's own facing with the outward crown direction."""
    up = Vector(up).normalized()
    nrm = Vector(normal)
    nrm = (nrm - up * nrm.dot(up)).normalized()
    side = up.cross(nrm).normalized()
    u0, v0, u1, v1, aspect = uvr
    w = size * 0.5 * aspect
    h = size
    um = (u0 + u1) * 0.5
    ridge = nrm * (w * fold)
    pts = [base - side * w, base + ridge, base + side * w,
           base - side * w + up * h, base + ridge + up * h, base + side * w + up * h]
    uvs = [(u0, v0), (um, v0), (u1, v0), (u0, v1), (um, v1), (u1, v1)]
    ns, cs = [], []
    for p in pts:
        out = Vector(((p.x - crown_c.x) / crown_r.x, (p.y - crown_c.y) / crown_r.y,
                      (p.z - crown_c.z) / crown_r.z))
        depth = min(out.length, 1.2)
        o = out.normalized() if out.length > 1e-4 else Vector((0, 0, 1))
        ns.append((o * bend_w + nrm * (1 - bend_w)).normalized())
        # Crown self-occlusion: inner + lower cards darker; a little random leaf-to-leaf value.
        under = 0.82 + 0.18 * max(min(o.z * 0.5 + 0.5, 1.0), 0.0)
        ao = (0.50 + 0.50 * min(depth, 1.0) ** 1.4) * under
        cs.append(tuple(tint[k] * ao for k in range(3)))
    jit = 0.9 + 0.2 * rng.random()
    cs = [tuple(c * jit for c in cc) for cc in cs]
    idx = [b.v(p) for p in pts]
    for q in ((0, 1, 4, 3), (1, 2, 5, 4)):
        b.face(tuple(idx[i] for i in q), [uvs[i] for i in q], [ns[i] for i in q], [cs[i] for i in q], mat)


# ------------------------------------------------------------------ species
def taper(n, r0, r1, power=1.0):
    return [r0 + (r1 - r0) * (i / (n - 1)) ** power for i in range(n)]


def broadleaf(seed, lod, height, trunk_r, crown_w, bark, leaf_tint, bark_tint, n_limbs,
              crown_base=0.38, leafy=True, cards_near=70, cards_far=26, upright=0.55):
    rng = np.random.default_rng(seed)
    b = Builder()
    mats = [bark, "canopy"]
    trunk_len = height * 0.92
    tsegs = 7 if lod == 0 else 4
    trunk = Limb(grow_path((0, 0, 0), (0, 0, 1), trunk_len, tsegs, rng, bend=0.05),
                 taper(tsegs + 1, trunk_r, trunk_r * 0.22, 0.8), 0)
    limbs = [trunk]
    golden = 2.39996
    az0 = rng.uniform(0, 2 * math.pi)
    for i in range(n_limbs):
        t = crown_base + (0.88 - crown_base) * (i + rng.uniform(0, 0.6)) / n_limbs
        k = min(int(t * tsegs), tsegs - 1)
        f = t * tsegs - k
        p = trunk.pts[k].lerp(trunk.pts[k + 1], f)
        az = az0 + i * golden + rng.uniform(-0.3, 0.3)
        elev = rng.uniform(0.35, 0.75) * upright + (1 - upright) * 0.25 + t * 0.25
        d = Vector((math.cos(az) * math.cos(elev), math.sin(az) * math.cos(elev), math.sin(elev)))
        L = crown_w * rng.uniform(0.45, 0.62) * (1.15 - 0.55 * (t - crown_base))
        segs = 4 if lod == 0 else 2
        pts = grow_path(p, d, L, segs, rng, bend=0.12, gravity=0.06)
        r_base = trunk.radii[k] * rng.uniform(0.42, 0.55)
        limbs.append(Limb(pts, taper(segs + 1, r_base, r_base * 0.25), 1))
    if lod == 0:
        for lm in list(limbs[1:]):
            for j in range(rng.integers(2, 4)):
                t = rng.uniform(0.35, 0.85)
                k = min(int(t * (len(lm.pts) - 1)), len(lm.pts) - 2)
                p = lm.pts[k].lerp(lm.pts[k + 1], 0.5)
                dir0 = (lm.pts[k + 1] - lm.pts[k]).normalized()
                side = dir0.cross(Vector((0, 0, 1))).normalized() * (1 if j % 2 else -1)
                d = (dir0 + side * rng.uniform(0.5, 1.0) + Vector((0, 0, rng.uniform(0.0, 0.5)))).normalized()
                L = (lm.pts[-1] - lm.pts[0]).length * rng.uniform(0.35, 0.5)
                pts = grow_path(p, d, L, 2, rng, bend=0.15, gravity=0.05)
                r = lm.radii[k] * 0.55
                limbs.append(Limb(pts, taper(3, r, r * 0.3), 2))
    for lm in limbs:
        sides = {0: 9 if lod == 0 else 6, 1: 6 if lod == 0 else 4, 2: 4}[lm.depth]
        tube(b, lm, sides, 0, bark_tint, flare=0.55 if lm.depth == 0 else 0.0,
             uv_phase=rng.uniform(0, 1))
    if leafy:
        tips = []
        for lm in limbs[1:]:
            w = 1.0 if lm.depth == 2 or lod == 1 else 0.6
            for t in np.linspace(0.35, 1.0, 4):
                k = min(int(t * (len(lm.pts) - 1)), len(lm.pts) - 2)
                f = t * (len(lm.pts) - 1) - k
                p = lm.pts[k].lerp(lm.pts[k + 1], min(f, 1.0))
                tips.append((p, (lm.pts[k + 1] - lm.pts[k]).normalized(), w))
        tips.append((trunk.pts[-1], Vector((0, 0, 1)), 1.0))
        pos = np.array([tuple(t[0]) for t in tips])
        cen = pos.mean(axis=0)
        spread = np.maximum(np.abs(pos - cen).max(axis=0), 0.5) * 1.15
        crown_c = Vector(tuple(cen)) + Vector((0, 0, spread[2] * 0.1))
        crown_r = Vector(tuple(spread))
        n_cards = cards_near if lod == 0 else cards_far
        size = crown_w * (0.38 if lod == 0 else 0.62)
        weights = np.array([t[2] for t in tips])
        weights /= weights.sum()
        for _ in range(n_cards):
            p, d, _w = tips[rng.choice(len(tips), p=weights)]
            p = p + Vector((rng.normal(), rng.normal(), rng.normal())) * size * 0.25
            out = (p - crown_c)
            out = out.normalized() if out.length > 1e-4 else Vector((0, 0, 1))
            up = (d * 0.5 + out * 0.6 + Vector((0, 0, 0.35)) +
                  Vector((rng.normal(), rng.normal(), rng.normal())) * 0.35).normalized()
            nrm = (out + Vector((rng.normal(), rng.normal(), rng.normal())) * 0.6).normalized()
            if abs(nrm.dot(up)) > 0.95:
                nrm = up.orthogonal()
            s = size * rng.uniform(0.8, 1.2)
            card(b, p - up * s * 0.15, up, nrm, s, UV_BROAD, 1, crown_c, crown_r, leaf_tint, rng)
    return b, mats


def conifer(seed, lod, height, trunk_r, skirt, leaf_tint, bark_tint):
    rng = np.random.default_rng(seed)
    b = Builder()
    mats = ["bark_pine", "canopy"]
    tsegs = 8 if lod == 0 else 4
    trunk = Limb(grow_path((0, 0, 0), (0, 0, 1), height, tsegs, rng, bend=0.025),
                 taper(tsegs + 1, trunk_r, trunk_r * 0.12, 0.9), 0)
    tube(b, trunk, 8 if lod == 0 else 5, 0, bark_tint, flare=0.35, uv_phase=rng.uniform(0, 1))
    crown_c = Vector((0, 0, height * 0.55))
    crown_r = Vector((skirt, skirt, height * 0.5))
    whorl_h = 0.42 if lod == 0 else 0.62
    z = height * 0.36
    golden = 2.39996
    az = rng.uniform(0, 6.3)
    while z < height * 0.97:
        t = (z - height * 0.36) / (height * 0.64)
        reach = skirt * (1.0 - t) ** 0.9 + 0.18
        n = 6 if lod == 0 else 4
        for i in range(n):
            az += golden + rng.uniform(-0.2, 0.2)
            droop = -rng.uniform(0.15, 0.4) * (1 - t) + 0.12 * t
            d = Vector((math.cos(az), math.sin(az), droop)).normalized()
            p0 = Vector((0, 0, z))
            L = reach * rng.uniform(0.85, 1.1)
            if lod == 0:
                pts = grow_path(p0, d, L, 2, rng, bend=0.06, gravity=-0.08)
                r = trunk_r * 0.14 * (1 - t * 0.6)
                tube(b, Limb(pts, taper(3, r, r * 0.3), 1), 3, 0, bark_tint)
            else:
                pts = [p0, p0 + d * L]
            # Needle cards along the branch: a flat-ish spray (seen from below / above) plus a
            # smaller upright one crossing it (seen side-on), so a limb never reads as a bare spoke.
            ncards = max(2, int(L / (0.46 if lod == 0 else 0.7)) + 1)
            for c in range(ncards):
                f = c / max(ncards, 1)
                base = p0 + (pts[-1] - p0) * (0.05 + f * 0.8)
                up = ((pts[-1] - p0).normalized() + Vector((0, 0, rng.uniform(-0.1, 0.15)))).normalized()
                flat = (Vector((0, 0, 1)) + up.cross(Vector((0, 0, 1))) * rng.uniform(-0.6, 0.6)).normalized()
                s = (1.0 if lod == 0 else 1.3) * min(1.0, L * 0.8 + 0.45) * rng.uniform(0.85, 1.1)
                card(b, base, up, flat, s, UV_CONIFER, 1, crown_c, crown_r, leaf_tint, rng,
                     fold=0.18, bend_w=0.6)
                if c % 2 == 0 and (lod == 0 or c == 0):
                    side = up.cross(flat).normalized()
                    card(b, base, up, side, s * 0.75, UV_CONIFER, 1, crown_c, crown_r, leaf_tint, rng,
                         fold=0.1, bend_w=0.6)
        z += whorl_h * rng.uniform(0.85, 1.15)
    # Leader tuft: two crossed upright cards.
    top = trunk.pts[-1]
    for a in (0.0, math.pi / 2):
        card(b, top - Vector((0, 0, 0.5)), Vector((0, 0, 1)), Vector((math.cos(a), math.sin(a), 0)),
             0.85, UV_CONIFER, 1, crown_c, crown_r, leaf_tint, rng, fold=0.1, bend_w=0.5)
    return b, mats


def bush(seed, lod, size, leaf_tint):
    rng = np.random.default_rng(seed)
    b = Builder()
    mats = ["bark_oak", "canopy"]
    stems = []
    for i in range(5 if lod == 0 else 3):
        a = rng.uniform(0, 6.3)
        d = Vector((math.cos(a) * 0.5, math.sin(a) * 0.5, 1)).normalized()
        pts = grow_path((0, 0, 0), d, size * rng.uniform(0.6, 0.9), 2, rng, bend=0.15)
        stems.append(Limb(pts, taper(3, 0.035, 0.012), 2))
        if lod == 0:
            tube(b, stems[-1], 3, 0, (0.8, 0.8, 0.8))
    crown_c = Vector((0, 0, size * 0.45))
    crown_r = Vector((size * 0.6, size * 0.6, size * 0.45))
    for _ in range(34 if lod == 0 else 14):
        st = stems[rng.integers(len(stems))]
        p = st.pts[-1].lerp(st.pts[1], rng.uniform(0, 0.8)) + Vector(
            (rng.normal(), rng.normal(), rng.normal() * 0.6)) * size * 0.18
        out = (p - crown_c).normalized()
        up = (out + Vector((0, 0, 0.6)) + Vector((rng.normal(), rng.normal(), rng.normal())) * 0.4).normalized()
        nrm = (out + Vector((rng.normal(), rng.normal(), rng.normal())) * 0.6).normalized()
        if abs(nrm.dot(up)) > 0.95:
            nrm = up.orthogonal()
        s = size * rng.uniform(0.45, 0.65) * (1.0 if lod == 0 else 1.4)
        card(b, p - up * s * 0.2, up, nrm, s, UV_BROAD, 1, crown_c, crown_r, leaf_tint, rng)
    return b, mats


SPECIES = {
    # name: (builder, kwargs)
    "oak_a": (broadleaf, dict(seed=11, height=4.4, trunk_r=0.20, crown_w=3.4, bark="bark_oak", n_limbs=8,
                              leaf_tint=(0.92, 0.95, 0.85), bark_tint=(0.95, 0.95, 0.95))),
    "oak_b": (broadleaf, dict(seed=23, height=4.0, trunk_r=0.22, crown_w=3.8, bark="bark_oak", n_limbs=9,
                              leaf_tint=(0.85, 0.92, 0.80), bark_tint=(0.90, 0.88, 0.85), crown_base=0.32)),
    "oak_c": (broadleaf, dict(seed=37, height=4.8, trunk_r=0.19, crown_w=3.0, bark="bark_oak", n_limbs=7,
                              leaf_tint=(1.0, 0.97, 0.80), bark_tint=(1.0, 0.97, 0.93), crown_base=0.42)),
    "beech_a": (broadleaf, dict(seed=41, height=5.4, trunk_r=0.15, crown_w=2.6, bark="bark_beech", n_limbs=7,
                                leaf_tint=(1.05, 1.08, 0.90), bark_tint=(1.0, 1.0, 1.0), crown_base=0.48,
                                upright=0.9, cards_near=64, cards_far=24)),
    "beech_b": (broadleaf, dict(seed=53, height=5.0, trunk_r=0.14, crown_w=2.3, bark="bark_beech", n_limbs=6,
                                leaf_tint=(1.1, 1.05, 0.78), bark_tint=(0.95, 0.97, 0.95), crown_base=0.5,
                                upright=0.95, cards_near=58, cards_far=22)),
    "pine_a": (conifer, dict(seed=61, height=5.6, trunk_r=0.15, skirt=1.35,
                             leaf_tint=(1.0, 1.0, 1.0), bark_tint=(1.0, 1.0, 1.0))),
    "pine_b": (conifer, dict(seed=67, height=6.2, trunk_r=0.16, skirt=1.2,
                             leaf_tint=(0.9, 0.95, 0.92), bark_tint=(0.95, 0.92, 0.9))),
    "pine_c": (conifer, dict(seed=71, height=4.8, trunk_r=0.13, skirt=1.45,
                             leaf_tint=(1.05, 1.03, 0.95), bark_tint=(1.0, 1.0, 1.0))),
    "dead_a": (broadleaf, dict(seed=83, height=3.9, trunk_r=0.18, crown_w=2.8, bark="bark_oak", n_limbs=6,
                               leaf_tint=(1, 1, 1), bark_tint=(0.72, 0.70, 0.68), leafy=False)),
    "bush_a": (bush, dict(seed=91, size=1.1, leaf_tint=(0.85, 0.95, 0.80))),
    "bush_b": (bush, dict(seed=97, size=0.85, leaf_tint=(0.95, 1.0, 0.82))),
}

clear_scene()
objs = []
report = {}
for name, (fn, kw) in SPECIES.items():
    for lod in (0, 1):
        b, mats = fn(lod=lod, **kw)
        ob = b.build(f"{name}_lod{lod}", mats)
        objs.append(ob)
        report[f"{name}_lod{lod}"] = b.tris()
export_glb(OUT / "trees.glb", objs)
(OUT / "trees_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
for k, v in report.items():
    print(f"{k}: {v} tris")
print("TREES_DONE")
