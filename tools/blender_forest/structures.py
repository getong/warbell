"""Realistic replacements for the forest's hand-built gameplay structures -> structures.glb.

Ork camp: hide tent, prisoner cage (+ hinged door), skull stakes, banner mast, fire pit.
Forest landmark: the old smock mill (body + the spinning sail cross).

Every model keeps the footprint, heights and anchor points of the low-poly original it replaces
(camps.rs / ork_fortress.rs / landmark_models.rs), so collisions, the cage door hinge, captive
seats, the flag mount, the mill's sail hub, door and lit window all still line up. Authored in game
coordinates via geo.py; materials by name (bark_oak + the s_* structure PBR sets, materials.py).
"""
import json
import math
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402
from common import OUT, clear_scene, export_glb  # noqa: E402
from geo import G, box, frustum, quat_x, quat_y, quat_z, rock, sheet, tube  # noqa: E402
from meshkit import Builder  # noqa: E402

# Material slots (order = index used below).
M_BARK, M_PLANK, M_STONE, M_HIDE, M_THATCH, M_CLOTH, M_IRON = range(7)
MATS = ["bark_oak", "s_planks", "s_stone", "s_hide", "s_thatch", "s_cloth", "s_iron"]

WHITE = (1.0, 1.0, 1.0)
BONE = (1.25, 1.18, 1.0)
ROPE = (0.85, 0.72, 0.5)
CHAR = (0.22, 0.2, 0.19)


def tint(c, k):
    return tuple(min(x * k, 4.0) for x in c)


def lean_line(base, h, rng, lean=0.04):
    top = Vector(base) + Vector((rng.uniform(-lean, lean) * h, h, rng.uniform(-lean, lean) * h))
    return [Vector(base), Vector(base).lerp(top, 0.5) + Vector((rng.normal() * 0.01, 0, rng.normal() * 0.01)), top]


def lashing(g, p, axis_a, r, rng):
    """A few turns of rope around a joint."""
    a = Vector(axis_a).normalized()
    side = a.orthogonal().normalized()
    for k in range(3):
        o = Vector(p) + a * (k - 1) * 0.035
        ring = []
        for s in range(9):
            ang = 2 * math.pi * s / 8
            ring.append(o + (side * math.cos(ang) + a.cross(side) * math.sin(ang)) * r)
        tube(g, ring, [0.012] * len(ring), 4, M_HIDE, ROPE, tile=0.3, cap=False)


# ─────────────────────────────────────────────────────────────── ork camp
def ork_tent(rng):
    """Hide A-frame (authored at the fortress size; the camp spawns it at 0.7x). Ridge 2.2, ground
    half-width 1.8, half-depth 1.5, door mouth toward -Z like the original."""
    b = Builder()
    g = G(b)
    h, w, d = 2.2, 1.8, 1.5
    # Crossed pole pairs, tips poking past the ridge, + the ridge log.
    for sz in (-1, 1):
        for sx in (-1, 1):
            base = Vector((sx * w * 1.0, 0.0, sz * d * 0.94))
            tip = Vector((-sx * 0.25, h + 0.32, sz * d * 0.94))
            pts = [base, base.lerp(tip, 0.5) + Vector((0, 0.03, 0)), tip]
            tube(g, pts, [0.075, 0.065, 0.05], 7, M_BARK, (0.85, 0.82, 0.78), tile=1.0, uv_phase=rng.uniform(0, 1))
        lashing(g, Vector((0, h + 0.05, sz * d * 0.94)), (0, 0, 1), 0.09, rng)
    tube(g, [Vector((0, h + 0.08, -d * 1.15)), Vector((0, h + 0.1, 0)), Vector((0, h + 0.08, d * 1.15))],
         [0.08, 0.085, 0.08], 7, M_BARK, (0.9, 0.86, 0.8), tile=1.0)
    # Two hide slopes: sag between the pole pairs, a lift where they rest on the frame, ragged hem.
    ni, nj = 9, 12
    for sx in (-1, 1):
        grid = []
        for i in range(ni):
            u = i / (ni - 1)  # 0 ridge .. 1 hem
            row = []
            for j in range(nj):
                vz = j / (nj - 1)
                z = (-1 + 2 * vz) * d * 1.05
                x = sx * (0.04 + u * w * 0.98)
                y = h + 0.12 - u * (h + 0.05)
                sag = 0.13 * math.sin(math.pi * u) * (0.6 + 0.4 * math.sin(math.pi * vz) ** 2)
                x -= sx * sag * 0.55
                y -= sag * 0.8
                if i == ni - 1:
                    y += abs(rng.normal()) * 0.07 + 0.03 * math.sin(j * 2.3)
                    x += sx * rng.uniform(-0.04, 0.06)
                row.append((x, max(y, 0.0), z))
            grid.append(row)
        base_t = rng.uniform(0.8, 1.0)

        def col(u, v, base_t=base_t):
            n = 0.9 + 0.12 * math.sin(u * 9.0 + v * 5.0) + 0.08 * math.sin(v * 17.0)
            soot = 1.0 - 0.25 * max(0.0, 1.0 - u * 3.0)  # smoke-stained near the ridge
            mud = 1.0 - 0.3 * max(0.0, u - 0.8) * 5.0  # muddy hem
            k = base_t * n * soot * max(mud, 0.6)
            return (k, k * 0.95, k * 0.88)
        sheet(g, grid, M_HIDE, col, tile=0.9, double=True)
        # A stitched-on patch of a different hide.
        pu, pv = rng.uniform(0.3, 0.6), rng.uniform(0.2, 0.7)
        patch = []
        for i in range(3):
            row = []
            for j in range(3):
                u = pu + i * 0.12
                vz = pv + j * 0.12
                z = (-1 + 2 * vz) * d * 1.05
                x = sx * (0.04 + u * w * 0.98)
                y = h + 0.12 - u * (h + 0.05)
                sag = 0.13 * math.sin(math.pi * u) * (0.6 + 0.4 * math.sin(math.pi * vz) ** 2)
                row.append((x - sx * sag * 0.55 + sx * 0.012, y - sag * 0.8 + 0.01, z))
            patch.append(row)
        sheet(g, patch, M_HIDE, lambda u, v: (0.62, 0.55, 0.48), tile=0.5, double=True)
    # Back wall (+Z): a triangle of hide laced to the poles.
    back = []
    for i in range(6):
        u = i / 5
        row = []
        for j in range(7):
            vx = -1 + 2 * j / 6
            yy = (h + 0.05) * (1 - u)
            xx = vx * (0.04 + u * w * 0.95)
            row.append((xx, yy, d * 1.0 + 0.04 * math.sin(math.pi * (j / 6)) * math.sin(math.pi * u)))
        back.append(row)
    sheet(g, back, M_HIDE, lambda u, v: (0.78, 0.72, 0.64), tile=0.9, double=True)
    # Door mouth (-Z): two flaps tied back to the poles.
    for sx in (-1, 1):
        flap = []
        for i in range(5):
            u = i / 4
            row = []
            for j in range(4):
                v = j / 3
                yy = (h + 0.05) * (1 - u)
                x_edge = sx * (0.04 + u * w * 0.95)
                xx = x_edge * (0.55 + 0.45 * v) + sx * 0.05 * math.sin(math.pi * u)
                row.append((xx, yy, -d * 1.02 - 0.08 * v * math.sin(math.pi * u)))
            flap.append(row)
        sheet(g, flap, M_HIDE, lambda u, v: (0.7, 0.64, 0.56), tile=0.9, double=True)
    # Guy ropes + stakes from the pole tips.
    for sz in (-1, 1):
        for sx in (-1, 1):
            top = Vector((sx * 0.15, h + 0.25, sz * d * 0.94))
            stake = Vector((sx * w * 1.55, 0.05, sz * d * 1.35))
            tube(g, [top, top.lerp(stake, 0.5) - Vector((0, 0.06, 0)), stake], [0.012] * 3, 4, M_HIDE, ROPE, tile=0.4)
            tube(g, [stake - Vector((0, 0.05, 0)), stake + Vector((sx * 0.05, 0.22, sz * 0.03))], [0.03, 0.022], 5,
                 M_BARK, (0.9, 0.85, 0.8), tile=0.5)
    # Bedding roll + a crude pot by the door.
    tube(g, [Vector((-0.6, 0.12, -d * 0.4)), Vector((0.2, 0.12, -d * 0.45))], [0.12, 0.12], 8, M_HIDE, (0.6, 0.5, 0.4), tile=0.5)
    frustum(g, 0.16, 0.2, 0.0, 0.26, 9, M_IRON, (0.5, 0.45, 0.42), tile=0.4, centre=(0.95, 0, -d * 1.25))
    return b


def ork_cage(rng):
    """Prisoner cage 2.2 x 2.2, 1.8 tall, open on +X (the door). Straw beds on CAGE_SEATS."""
    b = Builder()
    g = G(b)
    W, H = 2.2, 1.8
    hw = W / 2
    # Plank floor on two sleepers.
    for z in (-0.75, 0.75):
        box(g, (0, 0.06, z), (W + 0.2, 0.12, 0.16), quat_y(rng.uniform(-0.03, 0.03)), M_BARK, (0.8, 0.75, 0.7), tile=1.0)
    x = -hw - 0.05
    while x < hw:
        pw = rng.uniform(0.2, 0.28)
        box(g, (x + pw / 2, 0.135, rng.uniform(-0.03, 0.03)), (pw - 0.015, 0.035, W + rng.uniform(0.0, 0.12)),
            quat_y(rng.uniform(-0.02, 0.02)), M_PLANK, tint(WHITE, rng.uniform(0.7, 0.95)), tile=1.2)
        x += pw
    # Corner posts with root ends, lashed at the head.
    for sx, sz in ((-hw, -hw), (hw, -hw), (-hw, hw), (hw, hw)):
        pts = lean_line((sx, 0.0, sz), H + rng.uniform(0.05, 0.2), rng)
        tube(g, pts, [0.1, 0.085, 0.075], 8, M_BARK, (0.9, 0.86, 0.8), tile=1.0, uv_phase=rng.uniform(0, 1))
        lashing(g, Vector((sx, H - 0.08, sz)), (0, 1, 0), 0.1, rng)
    # Top rails on all four sides, mid rails on the closed faces.
    def rail(a, bpt, r, c=(0.88, 0.84, 0.78)):
        mid = Vector(a).lerp(Vector(bpt), 0.5) + Vector((0, -0.02, 0))
        tube(g, [Vector(a), mid, Vector(bpt)], [r, r * 1.05, r], 6, M_BARK, c, tile=1.0, uv_phase=rng.uniform(0, 1))
    rail((-hw - 0.08, H - 0.05, -hw), (hw + 0.08, H - 0.03, -hw), 0.055)
    rail((-hw - 0.08, H - 0.02, hw), (hw + 0.08, H - 0.06, hw), 0.055)
    rail((-hw, H - 0.04, -hw - 0.08), (-hw, H - 0.05, hw + 0.08), 0.055)
    rail((hw, H - 0.07, -hw - 0.08), (hw, H - 0.04, hw + 0.08), 0.055)
    rail((-hw, 0.95, -hw), (hw, 0.93, -hw), 0.04, (0.75, 0.7, 0.65))
    rail((-hw, 0.9, hw), (hw, 0.92, hw), 0.04, (0.75, 0.7, 0.65))
    rail((-hw, 0.92, -hw), (-hw, 0.9, hw), 0.04, (0.75, 0.7, 0.65))
    # Sapling bars on N / S / W (pale, debarked-looking: bark tinted light).
    for o in (-0.72, -0.24, 0.24, 0.72):
        for face in range(3):
            jo = o + rng.uniform(-0.05, 0.05)
            hh = H - 0.12 + rng.uniform(-0.06, 0.06)
            if face == 0:
                base = (jo, 0.12, -hw)
            elif face == 1:
                base = (jo, 0.12, hw)
            else:
                base = (-hw, 0.12, jo)
            pts = lean_line(base, hh, rng, 0.025)
            r = rng.uniform(0.03, 0.042)
            tube(g, pts, [r, r * 0.95, r * 0.85], 6, M_BARK, (1.35, 1.25, 1.1), tile=0.8, uv_phase=rng.uniform(0, 1))
            lashing(g, Vector((base[0], 0.93, base[2])), (0, 1, 0), r + 0.015, rng)
    # Straw beds at the captive seats.
    for sx, sz, _ in [(-0.52, 0.30, 1.25), (0.28, -0.48, 2.0), (0.05, 0.62, 0.7)]:
        rock(g, (sx, 0.15, sz), (0.36, 0.07, 0.32), 1.0, rng, M_THATCH, (1.6, 1.35, 0.8), tile=0.5, detail=2)
    return b


def ork_cage_door(rng):
    """Door panel, HINGE at the local origin, extending toward -Z across the +X face."""
    b = Builder()
    g = G(b)
    H = 1.8
    span = 2.2 - 0.16
    for y in (0.42, H - 0.38):
        tube(g, [Vector((0, y, -0.04)), Vector((0, y + 0.01, -span / 2)), Vector((0, y, -span - 0.04))],
             [0.045, 0.048, 0.045], 6, M_BARK, (0.88, 0.84, 0.78), tile=1.0, uv_phase=rng.uniform(0, 1))
    tube(g, [Vector((0, 0.42, -0.1)), Vector((0, H - 0.38, -span + 0.05))], [0.035, 0.035], 6, M_BARK,
         (0.75, 0.7, 0.65), tile=1.0)
    for z in (-0.30, -0.75, -1.20, -1.65):
        hh = H - 0.2 + rng.uniform(-0.05, 0.06)
        pts = lean_line((0, 0.12, z + rng.uniform(-0.04, 0.04)), hh, rng, 0.02)
        r = rng.uniform(0.032, 0.042)
        tube(g, pts, [r, r * 0.95, r * 0.85], 6, M_BARK, (1.35, 1.25, 1.1), tile=0.8, uv_phase=rng.uniform(0, 1))
        for y in (0.42, H - 0.38):
            lashing(g, Vector((0, y, pts[0].z)), (1, 0, 0), r + 0.02, rng)
    tube(g, [Vector((0, 0.1, -1.97)), Vector((0, H - 0.02, -1.97))], [0.05, 0.045], 7, M_BARK, (0.9, 0.86, 0.8), tile=1.0)
    for y in (0.42, H - 0.38):
        lashing(g, Vector((0, y, -0.06)), (0, 0, 1), 0.07, rng)
    return b


def skull(g, p, s, rng):
    """A rough bone skull: cranium + muzzle + dark eye sockets."""
    rock(g, (p[0], p[1] + 0.05 * s, p[2]), (0.09 * s, 0.08 * s, 0.1 * s), 1.0, rng, M_STONE, BONE, tile=0.3, detail=1)
    rock(g, (p[0], p[1] - 0.01 * s, p[2] + 0.08 * s), (0.06 * s, 0.05 * s, 0.06 * s), 1.0, rng, M_STONE, BONE, tile=0.3, detail=1)
    for sx in (-1, 1):
        rock(g, (p[0] + sx * 0.035 * s, p[1] + 0.05 * s, p[2] + 0.085 * s), (0.022 * s,) * 3, 1.0, rng, M_STONE, CHAR,
             tile=0.3, detail=0)


def ork_spikes(rng):
    """Two sharpened stakes with skulls, at the original camp-local spots."""
    b = Builder()
    g = G(b)
    for x, z, rot in ((-0.9, 1.4, 0.4), (1.6, 1.2, -0.6)):
        top = Vector((x + rng.uniform(-0.06, 0.06), 0.95, z + rng.uniform(-0.06, 0.06)))
        base = Vector((x, -0.05, z))
        tube(g, [base, base.lerp(top, 0.6), top, top + (top - base).normalized() * 0.16], [0.045, 0.04, 0.036, 0.004],
             7, M_BARK, (0.8, 0.76, 0.72), tile=0.8, cap=False)
        skull(g, top - Vector((0, 0.06, 0)), 1.25, rng)
        lashing(g, top - Vector((0, 0.22, 0)), (0, 1, 0), 0.05, rng)
        # A rag tied under it.
        tube(g, [top - Vector((0, 0.25, 0)), top - Vector((-0.05, 0.45, 0.03))], [0.02, 0.01], 4, M_CLOTH, (0.45, 0.12, 0.08), tile=0.3)
    return b


def ork_banner(rng):
    """Banner mast at camp-local (0, 0, -1.4), 3.0 tall; the cloth flag hangs from (0, 2.5, -1.4)."""
    b = Builder()
    g = G(b)
    base = Vector((0, -0.05, -1.4))
    top = Vector((0.02, 3.0, -1.38))
    tube(g, [base, base.lerp(top, 0.5), top], [0.06, 0.05, 0.04], 8, M_BARK, (0.85, 0.8, 0.76), tile=1.0)
    tube(g, [Vector((-0.45, 2.55, -1.4)), Vector((0.45, 2.55, -1.4))], [0.03, 0.03], 6, M_BARK, (0.8, 0.76, 0.7), tile=0.8)
    lashing(g, Vector((0.02, 2.55, -1.4)), (0, 1, 0), 0.06, rng)
    skull(g, Vector((0.02, 3.05, -1.38)), 1.1, rng)
    # Bone + feather danglers off the crossbar.
    for x in (-0.38, 0.38):
        tube(g, [Vector((x, 2.53, -1.4)), Vector((x + 0.02, 2.2, -1.39))], [0.008, 0.008], 4, M_HIDE, ROPE, tile=0.3)
        rock(g, (x + 0.02, 2.15, -1.39), (0.025, 0.06, 0.025), 1.0, rng, M_STONE, BONE, tile=0.2, detail=1)
    # Stones packed round the foot.
    for k in range(5):
        a = k / 5 * 2 * math.pi + rng.uniform(0, 0.5)
        rock(g, (math.cos(a) * 0.17, 0.04, -1.4 + math.sin(a) * 0.17), (0.09, 0.07, 0.08), 1.0, rng, M_STONE,
             tint(WHITE, rng.uniform(0.7, 0.95)), tile=0.5, detail=1)
    return b


def ork_firepit(rng):
    """Stone ring (r 0.42) + ash bed + crossed charred logs, centred at the origin (camp spawns at
    the fire point)."""
    b = Builder()
    g = G(b)
    n = 9
    for k in range(n):
        a = k / n * 2 * math.pi + rng.uniform(-0.1, 0.1)
        r = rng.uniform(0.11, 0.15)
        c = tint((0.75, 0.73, 0.7), rng.uniform(0.8, 1.0))
        rock(g, (math.cos(a) * 0.44, r * 0.45, math.sin(a) * 0.44), (r, r * 0.8, r * 0.9), 1.0, rng, M_STONE, c,
             tile=0.5, detail=1)
    # Ash bed: a low lumpy disc of charred stone.
    rock(g, (0, 0.0, 0), (0.36, 0.05, 0.36), 1.0, rng, M_STONE, (0.16, 0.15, 0.15), tile=0.5, detail=2)
    # Charred logs leaning into a cone.
    for k in range(4):
        a = k / 4 * 2 * math.pi + 0.4
        base = Vector((math.cos(a) * 0.36, 0.04, math.sin(a) * 0.36))
        tip = Vector((math.cos(a) * 0.05, 0.3, math.sin(a) * 0.05))
        tube(g, [base, tip], [0.05, 0.04], 6, M_BARK, (0.3, 0.27, 0.25), tile=0.6,
             col_fn=lambda t: (0.32 - 0.22 * t, 0.29 - 0.21 * t, 0.27 - 0.2 * t))
    # A spare log and a bone by the ring.
    tube(g, [Vector((0.7, 0.07, -0.3)), Vector((0.75, 0.07, 0.35))], [0.07, 0.065], 7, M_BARK, (0.85, 0.8, 0.75), tile=0.8)
    tube(g, [Vector((-0.65, 0.03, 0.25)), Vector((-0.45, 0.03, 0.4))], [0.02, 0.025], 5, M_STONE, BONE, tile=0.3)
    return b


# ──────────────────────────────────────────────────────────────── the mill
MILL_HUB = Vector((0.0, 4.75, 1.58))
SAIL_LEN = 2.3


def mill_body(rng):
    """Smock mill: fieldstone footing (r 1.75 -> 1.5, 0.6 tall), eight-sided boarded tower
    (r 1.42 -> 0.95 up to y 4.2), thatched cap to ~5.7. Door on +Z, shuttered window on -X."""
    b = Builder()
    g = G(b)
    # Footing: mortared drum + a course of boulders.
    frustum(g, 1.78, 1.52, 0.0, 0.62, 18, M_STONE, (0.88, 0.86, 0.82), tile=1.6, segs=2, jitter=0.02, rng=rng)
    frustum(g, 1.52, 1.44, 0.62, 0.0001, 18, M_STONE, (0.8, 0.78, 0.74), tile=1.6, cap_top=True)
    for k in range(13):
        a = k / 13 * 2 * math.pi + 0.23
        r = rng.uniform(0.2, 0.32)
        rock(g, (math.cos(a) * 1.72, r * 0.5, math.sin(a) * 1.72), (r * 1.2, r * 0.8, r), 1.0, rng, M_STONE,
             tint(WHITE, rng.uniform(0.7, 0.95)), tile=0.8, detail=1)
    # Tower: 8 sides of vertical boards. Each side is a few board strips with small offsets so the
    # silhouette and the lighting show the boarding.
    sides = 8
    y0, y1 = 0.6, 4.2
    r0, r1 = 1.42, 0.95
    for s in range(sides):
        a0 = (s / sides) * 2 * math.pi
        a1 = ((s + 1) / sides) * 2 * math.pi
        nb = 4
        for k in range(nb):
            f0, f1 = k / nb, (k + 1) / nb
            out = rng.uniform(0.0, 0.018)
            shade = rng.uniform(0.62, 0.95)

            def P(f, y, out=out):
                r = r0 + (r1 - r0) * (y - y0) / (y1 - y0) + out
                a = a0 + (a1 - a0) * f
                # chord between the two corners of this side
                ca = Vector((math.cos(a0), 0, math.sin(a0)))
                cb = Vector((math.cos(a1), 0, math.sin(a1)))
                c = ca.lerp(cb, f) * r
                return Vector((c.x, y, c.z))
            ytop = y1 - rng.uniform(0.0, 0.06)
            pts = [P(f0, y0), P(f1, y0), P(f1, ytop), P(f0, ytop)]
            n = (pts[1] - pts[0]).cross(pts[3] - pts[0]).normalized()
            if n.dot(Vector((pts[0].x, 0, pts[0].z))) < 0:
                pts = pts[::-1]
                n = -n
            w = (pts[1] - pts[0]).length
            u0 = rng.uniform(0, 4)
            g.poly(pts, [(u0, y0 / 1.4), (u0 + w / 1.4, y0 / 1.4), (u0 + w / 1.4, ytop / 1.4), (u0, ytop / 1.4)],
                   [n] * 4, [tint(WHITE, shade * 0.95), tint(WHITE, shade * 0.95), tint(WHITE, shade), tint(WHITE, shade)],
                   M_PLANK)
    # Weather bands + corner staves.
    for y, r in ((1.55, 1.32), (2.55, 1.2), (3.55, 1.07)):
        frustum(g, r + 0.05, r + 0.03, y - 0.06, 0.13, 8, M_PLANK, (0.45, 0.4, 0.36), tile=1.0)
    for s in range(sides):
        a = (s / sides) * 2 * math.pi
        p0 = Vector((math.cos(a) * (r0 + 0.02), y0, math.sin(a) * (r0 + 0.02)))
        p1 = Vector((math.cos(a) * (r1 + 0.02), y1, math.sin(a) * (r1 + 0.02)))
        tube(g, [p0, p1], [0.045, 0.04], 5, M_PLANK, (0.5, 0.44, 0.4), tile=1.2)
    # Door on +Z: recess, jambs, lintel, boarded leaf, iron straps, step.
    box(g, (0, 0.92, 1.43), (0.66, 1.2, 0.08), quat_x(0.0), M_PLANK, (0.12, 0.1, 0.09), tile=1.0)
    box(g, (0, 0.92, 1.47), (0.58, 1.14, 0.05), quat_x(-0.06), M_PLANK, (0.55, 0.48, 0.42), tile=0.8)
    for y in (0.6, 1.25):
        box(g, (0, y, 1.5), (0.6, 0.05, 0.02), quat_x(-0.06), M_IRON, (0.55, 0.5, 0.48), tile=0.4)
    for sx in (-1, 1):
        box(g, (sx * 0.42, 0.9, 1.5), (0.14, 1.28, 0.2), quat_z(sx * -0.04), M_PLANK, (0.4, 0.35, 0.3), tile=1.0)
    box(g, (0, 1.55, 1.48), (0.98, 0.17, 0.25), quat_z(0.03), M_PLANK, (0.4, 0.35, 0.3), tile=1.0)
    rock(g, (0, 0.06, 1.88), (0.48, 0.08, 0.3), 1.0, rng, M_STONE, (0.75, 0.73, 0.7), tile=0.8, detail=1)
    # Shuttered window on -X (the lit casement is a separate glowing quad in-game at +X/+Z).
    box(g, (-1.23, 2.5, 0.3), (0.12, 0.44, 0.36), quat_y(0.25), M_PLANK, (0.42, 0.37, 0.32), tile=0.6)
    # Window frame for the lit casement (game puts the glow quad at (0.57, 3.1, 0.88), yaw 0.57).
    for dx, dy, sx_, sy_ in ((0, 0.2, 0.36, 0.05), (0, -0.2, 0.36, 0.05), (-0.16, 0, 0.05, 0.42), (0.16, 0, 0.05, 0.42)):
        c = Vector((0.57, 3.1, 0.88)) + quat_y(0.57) @ Vector((dx, dy, 0.03))
        box(g, tuple(c), (sx_, sy_, 0.06), quat_y(0.57), M_PLANK, (0.35, 0.3, 0.26), tile=0.5)
    # Cap: curb ring, thatch skirt, dome, finial.
    frustum(g, 1.26, 1.12, 4.18, 0.09, 12, M_PLANK, (0.4, 0.35, 0.3), tile=1.0)
    frustum(g, 1.3, 0.8, 4.24, 0.56, 16, M_THATCH, (0.9, 0.85, 0.75), tile=1.0, segs=3, jitter=0.03, rng=rng,
            col_fn=lambda t: (0.8 + 0.1 * t, 0.76 + 0.09 * t, 0.66 + 0.08 * t))
    frustum(g, 0.8, 0.32, 4.8, 0.5, 16, M_THATCH, (0.85, 0.8, 0.7), tile=1.0, segs=3, jitter=0.03, rng=rng)
    frustum(g, 0.32, 0.02, 5.3, 0.38, 12, M_THATCH, (0.75, 0.7, 0.62), tile=0.8, segs=2)
    tube(g, [Vector((0, 5.6, 0)), Vector((0, 5.72, 0))], [0.05, 0.08], 6, M_PLANK, (0.35, 0.3, 0.26), tile=0.4)
    # Windshaft stub out to the hub.
    tube(g, [Vector((0, 4.72, 0.6)), Vector((0, 4.75, 1.45))], [0.12, 0.12], 8, M_PLANK, (0.45, 0.4, 0.35), tile=1.0)
    # Ivy on the shaded -Z/-X quarter (leafy clumps -> thatch tinted green reads as foliage mass).
    for x, y, z, r in ((-0.95, 0.55, -1.15, 0.42), (-1.25, 1.1, -0.65, 0.34), (-1.05, 1.75, -0.85, 0.3),
                       (-1.2, 2.4, -0.35, 0.26), (-0.55, 0.4, -1.45, 0.3)):
        rad = math.hypot(x, z)
        wall = 1.44 - y * 0.13
        rock(g, (x / rad * wall, y, z / rad * wall), (r * 0.9, r, r * 0.4), 1.0, rng, M_THATCH, (0.28, 0.42, 0.14),
             tile=0.4, detail=1)
    # Yard: leaning millstone, grain sacks, a broken cart wheel.
    ms = Vector((1.62, 0.56, 0.95))
    rot = quat_y(0.5) @ quat_x(1.32)
    ring_pts = []
    for k in range(2):
        pass
    frustum_pts = 14
    for k in range(frustum_pts):
        a0 = k / frustum_pts * 2 * math.pi
        a1 = (k + 1) / frustum_pts * 2 * math.pi
        for (ra, rb_) in ((0.58, 0.14),):
            for side in (-1, 1):
                p = [Vector((math.cos(a0) * ra, side * 0.08, math.sin(a0) * ra)),
                     Vector((math.cos(a1) * ra, side * 0.08, math.sin(a1) * ra)),
                     Vector((math.cos(a1) * rb_, side * 0.08, math.sin(a1) * rb_)),
                     Vector((math.cos(a0) * rb_, side * 0.08, math.sin(a0) * rb_))]
                p = [ms + rot @ q for q in (p if side > 0 else p[::-1])]
                g.flat(p, M_STONE, (0.8, 0.78, 0.74), 0.8)
        rim = [Vector((math.cos(a0) * 0.58, -0.08, math.sin(a0) * 0.58)), Vector((math.cos(a1) * 0.58, -0.08, math.sin(a1) * 0.58)),
               Vector((math.cos(a1) * 0.58, 0.08, math.sin(a1) * 0.58)), Vector((math.cos(a0) * 0.58, 0.08, math.sin(a0) * 0.58))]
        g.flat([ms + rot @ q for q in rim[::-1]], M_STONE, (0.72, 0.7, 0.66), 0.8)
    # Sacks stacked against the east wall, well clear of the door path (+Z, |x| < 0.7).
    for x, z, r in ((2.15, 0.25, 0.3), (2.25, -0.38, 0.26), (1.98, -0.85, 0.22)):
        rock(g, (x, r * 0.7, z), (r, r * 0.95, r * 0.85), 1.0, rng, M_CLOTH, (0.95, 0.88, 0.72), tile=0.4, detail=2)
        tube(g, [Vector((x, r * 1.55, z)), Vector((x, r * 1.75, z))], [r * 0.25, r * 0.1], 6, M_CLOTH, (0.9, 0.83, 0.68), tile=0.3)
    wc = Vector((-1.55, 0.42, 1.05))
    wrot = quat_y(-0.4) @ quat_x(1.25)
    rim = []
    for k in range(17):
        a = k / 16 * 2 * math.pi * 0.8  # a broken wheel: 80% of the rim
        rim.append(wc + wrot @ Vector((math.cos(a) * 0.42, 0, math.sin(a) * 0.42)))
    tube(g, rim, [0.045] * len(rim), 5, M_PLANK, (0.5, 0.44, 0.38), tile=0.6)
    for k in range(5):
        a = k / 6 * 2 * math.pi
        tube(g, [wc, wc + wrot @ Vector((math.cos(a) * 0.4, 0, math.sin(a) * 0.4))], [0.025, 0.02], 4, M_PLANK,
             (0.45, 0.4, 0.34), tile=0.5)
    frustum(g, 0.08, 0.08, -0.07, 0.14, 8, M_PLANK, (0.35, 0.3, 0.26), tile=0.3, centre=(0, 0, 0))
    # Flagstone path from the door.
    for i, (x, z) in enumerate(((0.0, 2.5), (0.35, 3.1), (-0.25, 3.65))):
        rock(g, (x, 0.02, z), (0.34 - i * 0.03, 0.05, 0.28), 1.0, rng, M_STONE, (0.78, 0.76, 0.72), tile=0.8, detail=1)
    return b


def mill_sails(rng):
    """The sail cross about the hub (origin), arms in the local XY plane, spinning about +Z. One
    arm's canvas hangs short (the mill is old)."""
    b = Builder()
    g = G(b)
    tube(g, [Vector((0, 0, -0.25)), Vector((0, 0, 0.25))], [0.17, 0.17], 10, M_PLANK, (0.4, 0.35, 0.3), tile=0.6)
    tube(g, [Vector((0, 0, 0.25)), Vector((0, 0, 0.36))], [0.12, 0.05], 8, M_IRON, (0.5, 0.46, 0.44), tile=0.3)
    for k in range(4):
        rot = quat_z(k * math.pi / 2)
        torn = k == 2
        # Stock (main spar), slightly tapered.
        tube(g, [rot @ Vector((0, 0.1, 0.05)), rot @ Vector((0, SAIL_LEN, 0.05))], [0.06, 0.04], 6, M_PLANK,
             (0.5, 0.44, 0.38), tile=1.0)
        # Lattice: two long whips + crossbars.
        for x in (0.03, 0.6):
            tube(g, [rot @ Vector((x, 0.75, 0.04)), rot @ Vector((x, SAIL_LEN - 0.05, 0.04))], [0.022, 0.02], 4,
                 M_PLANK, (0.45, 0.4, 0.35), tile=1.0)
        bars = 3 if torn else 7
        for i in range(bars):
            y = 0.8 + i * (SAIL_LEN - 0.9) / 6
            tube(g, [rot @ Vector((0.0, y, 0.04)), rot @ Vector((0.62, y, 0.04))], [0.016, 0.016], 4, M_PLANK,
                 (0.42, 0.37, 0.32), tile=0.6)
        # Canvas: slight billow, double-sided.
        top = SAIL_LEN - 0.1
        bot = top - (0.75 if torn else 1.55)
        grid = []
        for i in range(5):
            u = i / 4
            row = []
            for j in range(6):
                vv = j / 5
                x = 0.05 + u * 0.53
                y = bot + vv * (top - bot)
                zb = 0.06 + 0.06 * math.sin(math.pi * u) * math.sin(math.pi * vv)
                if torn and j == 0:
                    y += rng.uniform(-0.08, 0.05)
                row.append(tuple(rot @ Vector((x, y, zb))))
            grid.append(row)
        c = (0.75, 0.7, 0.6) if torn else (0.95, 0.9, 0.8)
        sheet(g, grid, M_CLOTH, lambda u, v, c=c: tuple(x * (0.9 + 0.1 * math.sin(u * 7 + v * 5)) for x in c),
              tile=0.6, double=True)
    return b


MODELS = {
    "ork_tent": ork_tent,
    "ork_cage": ork_cage,
    "ork_cage_door": ork_cage_door,
    "ork_spikes": ork_spikes,
    "ork_banner": ork_banner,
    "ork_firepit": ork_firepit,
    "mill_body": mill_body,
    "mill_sails": mill_sails,
}

clear_scene()
objs = []
report = {}
for i, (name, fn) in enumerate(MODELS.items()):
    b = fn(np.random.default_rng(1000 + i))
    objs.append(b.build(name, MATS))
    report[name] = b.tris()
export_glb(OUT / "structures.glb", objs)
(OUT / "structures_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
for k, v in report.items():
    print(f"{k}: {v} tris")
print("STRUCTURES_DONE")
