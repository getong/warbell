"""The Salt Caravan's gear (living-island spec 2026-10-13 §2 E.16, `src/caravan.rs`) -> caravan.glb.

  caravan_pack   — a mule's pack load in the HORSE rig's spine-joint frame (quadruped.rs: origin =
                   body centre, +Z forward, body half-height 0.14): a padded wooden pack saddle
                   (two crossed bucks), a striped saddle blanket, two hide-wrapped salt panniers
                   hanging at the flanks, a roped bedroll on top. Rides the Spine joint.
  caravan_goods  — the trade spread at the market stop: a striped wool rug pegged on the grass,
                   grey rock-salt loaves stacked in a crate, slumped sacks, clay jars, a set of scales.

    blender -b --factory-startup --python tools/blender_forest/caravan.py
"""
import math
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
from common import OUT, clear_scene, export_glb  # noqa: E402
from geo import G, frustum, quat_x, quat_y, quat_z  # noqa: E402
from meshkit import Builder  # noqa: E402
from wayside_models import (  # noqa: E402
    M_BARK, M_CLOTH, M_HIDE, M_IRON, M_PLANK, M_TIMBER, MATS as WAYSIDE_MATS, V, beam, bounds, lashing, lbox, pole,
    scale, slab, smooth_mesh, tube,
)

M_CLAY = len(WAYSIDE_MATS)
M_SALT = M_CLAY + 1
MATS = WAYSIDE_MATS + ["s_clay", "s_sandstone"]
STRIPES = [(0.62, 0.16, 0.12), (0.86, 0.74, 0.5), (0.2, 0.26, 0.42), (0.86, 0.74, 0.5)]


def sack(g, c, r, h, rng, col=(0.86, 0.78, 0.62), squash=1.0, rot=None):
    """A slumped cloth sack: a lumpy squashed blob, tied neck on top."""
    rot = rot or quat_y(rng.uniform(0, 6.28))
    verts, faces = [], []
    seg, rings = 14, 9
    for j in range(rings + 1):
        t = j / rings
        y = h * t
        bulge = math.sin(math.pi * min(1.0, t * 1.15)) ** 0.6
        rr = r * (0.55 + 0.45 * bulge) * (1.0 - 0.55 * max(0.0, t - 0.8) / 0.2)
        for i in range(seg):
            a = 2 * math.pi * i / seg
            w = 1 + 0.08 * math.sin(3 * a + j) + rng.uniform(-0.03, 0.03)
            verts.append(V(c[0], c[1], c[2]) + rot @ V(math.cos(a) * rr * w * squash, y * (0.9 + 0.1 * bulge),
                                                         math.sin(a) * rr * w / squash))
    for j in range(rings):
        for i in range(seg):
            a, b = j * seg + i, j * seg + (i + 1) % seg
            faces += [(a, b, b + seg), (a, b + seg, a + seg)]
    top = len(verts)
    verts.append(V(c[0], c[1], c[2]) + rot @ V(0, h * 1.02, 0))
    for i in range(seg):
        faces.append((rings * seg + i, rings * seg + (i + 1) % seg, top))
    smooth_mesh(g, verts, faces, M_CLOTH, lambda p, n: scale(col, 0.8 + 0.2 * max(n.y, 0)), 0.5,
                inside=(c[0], c[1] + h * 0.4, c[2]))
    neck = V(c[0], c[1], c[2]) + rot @ V(0, h * 0.86, 0)
    lashing(g, neck, rot @ V(0, 1, 0), r * 0.3, rng, turns=2)


def mk_pack(rng):
    b = Builder()
    g = G(b)
    y0 = 0.135  # top of the horse spine body
    # Saddle blanket draped over the back (striped wool), hanging down both flanks.
    for k in range(10):
        z0, z1 = -0.2 + k * 0.045, -0.2 + (k + 1) * 0.045
        col = STRIPES[(k // 2) % len(STRIPES)]
        prof = [(math.sin(a) * 0.19, y0 - 0.02 + math.cos(a) * 0.05 - (abs(math.sin(a)) ** 3) * 0.2)
                for a in np.linspace(-1.45, 1.45, 11)]
        for s in range(10):
            (x0, ya), (x1, yb) = prof[s], prof[s + 1]
            q = [V(x0, ya, z0), V(x1, yb, z0), V(x1, yb, z1), V(x0, ya, z1)]
            n = V(-(yb - ya), x1 - x0, 0).normalized()
            if (q[1] - q[0]).cross(q[3] - q[0]).dot(n) < 0:
                q = q[::-1]
            g.poly(q, [(x0 * 3, z0 * 3), (x1 * 3, z0 * 3), (x1 * 3, z1 * 3), (x0 * 3, z1 * 3)], [n] * 4, [col] * 4, M_CLOTH)
    # Sawbuck pack saddle: two crossed-timber bucks joined by side bars.
    for z in (-0.12, 0.12):
        for sx in (-1, 1):
            beam(g, [V(sx * 0.13, y0 + 0.02, z), V(-sx * 0.03, y0 + 0.2, z)], 0.035, 0.035, mat=M_TIMBER, rng=rng,
                 col=(0.7, 0.6, 0.48))
    for sx in (-1, 1):
        beam(g, [V(sx * 0.11, y0 + 0.04, -0.2), V(sx * 0.11, y0 + 0.04, 0.2)], 0.05, 0.03, mat=M_TIMBER, rng=rng,
             col=(0.66, 0.56, 0.45))
    # Salt panniers: hide-wrapped bales slung on each flank.
    for sx in (-1, 1):
        c = V(sx * 0.25, y0 - 0.12, 0.0)
        slab(g, (c.x, c.y, c.z), (0.11, 0.24, 0.3), quat_z(sx * 0.12), rng, mat=M_HIDE, res=(3, 4, 4), round_r=0.05,
             rough=0.05, col_fn=lambda p, n: (0.62, 0.5, 0.38), tile=0.4)
        for z in (-0.09, 0.09):
            ring = [c + V(math.cos(a) * 0.075, math.sin(a) * 0.14, z) for a in np.linspace(0, 2 * math.pi, 11)]
            tube(g, ring, [0.009] * len(ring), 4, M_CLOTH, (0.86, 0.74, 0.5), tile=0.2, cap=False)
        tube(g, [V(sx * 0.12, y0 + 0.06, -0.09), c + V(sx * -0.02, 0.12, -0.09)], [0.009, 0.009], 4, M_CLOTH,
             (0.86, 0.74, 0.5), tile=0.2)
        tube(g, [V(sx * 0.12, y0 + 0.06, 0.09), c + V(sx * -0.02, 0.12, 0.09)], [0.009, 0.009], 4, M_CLOTH,
             (0.86, 0.74, 0.5), tile=0.2)
    # Top load: a roped bedroll + a small sack.
    tube(g, [V(-0.14, y0 + 0.2, 0.02), V(0.14, y0 + 0.2, 0.02)], [0.055, 0.055], 10, M_CLOTH, (0.45, 0.38, 0.3),
         tile=0.3)
    for x in (-0.08, 0.08):
        lashing(g, V(x, y0 + 0.2, 0.02), (1, 0, 0), 0.06, rng, turns=1)
    sack(g, (0.0, y0 + 0.16, -0.12), 0.07, 0.13, rng, col=(0.8, 0.72, 0.58), squash=1.2, rot=quat_x(1.3))
    # Girth strap under the belly.
    girth = [V(math.sin(a) * 0.17, math.cos(a) * 0.15, 0.06) for a in np.linspace(-2.2, 2.2, 13)]
    tube(g, girth, [0.012] * len(girth), 4, M_HIDE, (0.38, 0.28, 0.2), tile=0.2, cap=False)
    return b


def mk_goods(rng):
    b = Builder()
    g = G(b)
    # Striped rug (~2.2 x 1.5), slightly rumpled, pegged at the corners.
    nx, nz = 12, 8
    W, D = 1.1, 0.75
    pts = {}
    for i in range(nx + 1):
        for j in range(nz + 1):
            x, z = -W + 2 * W * i / nx, -D + 2 * D * j / nz
            pts[i, j] = V(x, 0.03 + 0.015 * math.sin(x * 4.1 + z * 2.3) + rng.uniform(0, 0.006), z)
    for i in range(nx):
        col = STRIPES[(i // 2) % len(STRIPES)]
        for j in range(nz):
            q = [pts[i, j], pts[i, j + 1], pts[i + 1, j + 1], pts[i + 1, j]]
            g.poly(q, [(p.x * 2, p.z * 2) for p in q], [V(0, 1, 0)] * 4, [col] * 4, M_CLOTH)
    for x, z in ((-W, -D), (W, -D), (-W, D), (W, D)):
        pole(g, V(x, -0.1, z), V(x, 0.06, z), 0.012, 0.01, rng, col=(0.8, 0.7, 0.55), sides=4, segs=1)
    # A crate of grey rock-salt loaves.
    cc = V(-0.55, 0.0, -0.2)
    for dx, dz, w, d in ((0, -0.2, 0.5, 0.03), (0, 0.2, 0.5, 0.03), (-0.25, 0, 0.03, 0.4), (0.25, 0, 0.03, 0.4)):
        lbox(g, cc + V(dx, 0.14, dz), (w, 0.24, d), quat_y(0), M_PLANK, (0.72, 0.62, 0.5), tile=0.8, grain=0)
    for k in range(6):
        p = cc + V(-0.13 + (k % 3) * 0.13, 0.2 + (k // 3) * 0.05, -0.08 + (k // 3) * 0.12)
        slab(g, (p.x, p.y, p.z), (0.12, 0.09, 0.15), quat_y(rng.uniform(-0.3, 0.3)), rng, mat=M_SALT, res=(2, 2, 2),
             round_r=0.025, rough=0.06, col_fn=lambda p, n: (0.82, 0.8, 0.78), tile=0.3)
    # Slumped sacks + clay jars.
    sack(g, (0.25, 0.02, -0.35), 0.2, 0.42, rng, col=(0.84, 0.76, 0.6))
    sack(g, (0.62, 0.02, -0.25), 0.18, 0.36, rng, col=(0.78, 0.7, 0.55))
    for k, (x, z) in enumerate(((0.5, 0.35), (0.72, 0.3), (0.6, 0.52))):
        h = 0.32 + 0.06 * k
        frustum(g, 0.08, 0.12, 0.02, h * 0.5, 12, M_CLAY, (0.8, 0.56, 0.42), tile=0.4, centre=(x, 0, z), segs=2)
        frustum(g, 0.12, 0.06, 0.02 + h * 0.5, h * 0.45, 12, M_CLAY, (0.8, 0.56, 0.42), tile=0.4, centre=(x, 0, z),
                segs=2)
        frustum(g, 0.06, 0.07, 0.02 + h * 0.95, 0.05, 12, M_CLAY, (0.72, 0.5, 0.38), tile=0.4, centre=(x, 0, z),
                cap_top=True)
    # A hand balance lying on the rug: beam + two pans.
    beam(g, [V(-0.2, 0.06, 0.45), V(0.25, 0.06, 0.42)], 0.015, 0.015, mat=M_IRON, rng=rng, col=(0.55, 0.45, 0.3))
    for x in (-0.22, 0.27):
        frustum(g, 0.07, 0.09, 0.03, 0.02, 12, M_IRON, (0.6, 0.48, 0.3), tile=0.3, centre=(x, 0, 0.5), cap_top=True)
    return b


MODELS = {"caravan_pack": mk_pack, "caravan_goods": mk_goods}

if __name__ == "__main__":
    clear_scene()
    objs = []
    for i, (name, fn) in enumerate(MODELS.items()):
        bld = fn(np.random.default_rng(5200 + i))
        print(name, bounds(bld))
        objs.append(bld.build(name, MATS))
    export_glb(OUT / "caravan.glb", objs)
    print("CARAVAN_DONE")
