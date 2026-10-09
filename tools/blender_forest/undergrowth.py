"""Forest-floor plants on the undergrowth atlas (foliage.py) -> undergrowth.glb.

  fern_a..c   6-8 arching frond strips (scanned `fern_02` fronds), ~40-60 tris
  grass_a..d  three crossed clump cards (scanned `grass_medium_01` tufts), 6 tris
  stalks_a    two crossed seed-head cards, 4 tris
  litter_a..d fallen leaves + twigs lying on the floor (curled 3x3 sheet), 8 tris

Everything shares ONE material (`undergrowth`) so the game merges a whole 16u chunk of
floor plants into a single draw. Normals lean toward +Z (up) - the usual grass trick that
keeps thin cards from flipping dark/bright as the camera orbits - and vertex colour darkens
toward the roots for contact occlusion.
"""
import json
import math
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402
from common import OUT, clear_scene, export_glb  # noqa: E402
from meshkit import Builder  # noqa: E402

LAYOUT = json.loads((OUT / "foliage_layout.json").read_text(encoding="utf-8"))["undergrowth"]
W, H = LAYOUT["size"]
UP = Vector((0, 0, 1))


def rect_uv(r):
    x, y, w, h = r
    return x / W, 1 - (y + h) / H, (x + w) / W, 1 - y / H  # u0, v_bottom, u1, v_top


def frond(b, rng, rect, az, length, elev, root_off, tint):
    u0, vb, u1, vt = rect_uv(rect)
    aspect = rect[2] / rect[3]
    width = length * aspect * 1.25
    d_h = Vector((math.cos(az), math.sin(az), 0))
    side = Vector((-math.sin(az), math.cos(az), 0))
    segs = 4
    pts = []
    p = d_h * root_off
    ang = elev
    step = length / segs
    for i in range(segs + 1):
        pts.append(p.copy())
        d = d_h * math.cos(ang) + UP * math.sin(ang)
        p = p + d * step
        ang -= rng.uniform(0.28, 0.42)  # arch over
    rows = []
    for i, p in enumerate(pts):
        t = i / segs
        w = width * (0.35 + 0.65 * math.sin(min(t * 1.15, 1.0) * math.pi * 0.5 + 0.2))
        # Pinnae droop: outer edges sit a touch lower than the rachis.
        droop = -UP * width * 0.12 * t
        v = vb + (vt - vb) * t
        col = tuple(c * (0.55 + 0.45 * min(t * 1.6, 1.0)) for c in tint)
        tangent = (pts[min(i + 1, segs)] - pts[max(i - 1, 0)]).normalized()
        n = side.cross(tangent).normalized()
        if n.z < 0:
            n = -n
        n = (n * 0.45 + UP * 0.55).normalized()
        rows.append([(b.v(p - side * w * 0.5 + droop), (u0, v), n, col),
                     (b.v(p), ((u0 + u1) * 0.5, v), (n + side * 0.15).normalized(), col),
                     (b.v(p + side * w * 0.5 + droop), (u1, v), n, col)])
    for i in range(segs):
        for j in range(2):
            a, c = rows[i][j], rows[i][j + 1]
            d, e = rows[i + 1][j + 1], rows[i + 1][j]
            b.face((a[0], c[0], d[0], e[0]), [a[1], c[1], d[1], e[1]], [a[2], c[2], d[2], e[2]],
                   [a[3], c[3], d[3], e[3]], 0)


def fern(seed):
    rng = np.random.default_rng(seed)
    b = Builder()
    n = rng.integers(6, 9)
    az0 = rng.uniform(0, 6.3)
    for i in range(n):
        az = az0 + i * 2 * math.pi / n + rng.uniform(-0.25, 0.25)
        rect = LAYOUT["fern"][rng.integers(len(LAYOUT["fern"]))]
        g = rng.uniform(0, 1)
        frond(b, rng, rect, az, rng.uniform(0.55, 0.78), rng.uniform(0.95, 1.25), 0.03,
              (0.92 + 0.1 * g, 1.0, 0.85 + 0.1 * g))
    return b


def crossed(b, rng, rects, width, n_cards, tint, sink=0.02, up_bias=0.7):
    a0 = rng.uniform(0, math.pi)
    for i in range(n_cards):
        rect = rects[rng.integers(len(rects))]
        u0, vb, u1, vt = rect_uv(rect)
        h = width * rect[3] / rect[2]
        a = a0 + i * math.pi / n_cards + rng.uniform(-0.15, 0.15)
        side = Vector((math.cos(a), math.sin(a), 0)) * width * 0.5
        off = Vector((rng.normal(), rng.normal(), 0)) * width * 0.08
        face_n = Vector((-math.sin(a), math.cos(a), 0))
        lean = face_n * rng.uniform(-0.12, 0.12) * h
        p = [off - side - UP * sink, off + side - UP * sink, off + side + UP * h + lean, off - side + UP * h + lean]
        uvs = [(u0, vb), (u1, vb), (u1, vt), (u0, vt)]
        cb = tuple(c * 0.55 for c in tint)
        ct = tint
        ns = [(face_n * (1 - up_bias) + UP * up_bias).normalized()] * 4
        b.face(tuple(b.v(q) for q in p), uvs, ns, [cb, cb, ct, ct], 0)


def litter(seed, rect_i):
    """A patch of fallen leaves + twigs LYING on the floor: a 3x3-vertex sheet with a little
    random lift so leaf edges catch light and cast contact shadow on the ground texture."""
    rng = np.random.default_rng(seed)
    b = Builder()
    u0, vb, u1, vt = rect_uv(LAYOUT["litter"][rect_i])
    size = rng.uniform(0.75, 1.0)
    grid = {}
    for i in range(3):
        for j in range(3):
            x = (i / 2 - 0.5) * size
            y = (j / 2 - 0.5) * size
            lift = 0.01 + (0.025 * rng.uniform(0.3, 1.0) if (i, j) != (1, 1) else 0.015)
            grid[(i, j)] = (Vector((x, y, lift)), (u0 + (u1 - u0) * i / 2, vb + (vt - vb) * j / 2))
    for i in range(2):
        for j in range(2):
            q = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]
            b.face(tuple(b.v(grid[k][0]) for k in q), [grid[k][1] for k in q], [UP] * 4,
                   [(1.0, 1.0, 1.0)] * 4, 0)
    return b


def grass(seed):
    rng = np.random.default_rng(seed)
    b = Builder()
    crossed(b, rng, LAYOUT["grass"], rng.uniform(0.5, 0.65), 3, (1.0, 1.0, 0.95))
    return b


def stalks(seed):
    rng = np.random.default_rng(seed)
    b = Builder()
    crossed(b, rng, LAYOUT["stalks"], 0.42, 2, (1.0, 0.98, 0.9), up_bias=0.55)
    return b


clear_scene()
objs, report = [], {}
for name, fn, seed in [("fern_a", fern, 1), ("fern_b", fern, 2), ("fern_c", fern, 3),
                       ("grass_a", grass, 4), ("grass_b", grass, 5), ("grass_c", grass, 6),
                       ("grass_d", grass, 7), ("stalks_a", stalks, 8),
                       ("litter_a", lambda s: litter(s, 0), 9), ("litter_b", lambda s: litter(s, 1), 10),
                       ("litter_c", lambda s: litter(s, 2), 11), ("litter_d", lambda s: litter(s, 3), 12)]:
    b = fn(seed)
    objs.append(b.build(name, ["undergrowth"]))
    report[name] = b.tris()
export_glb(OUT / "undergrowth.glb", objs)
(OUT / "undergrowth_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
print(report)
print("UNDERGROWTH_DONE")
