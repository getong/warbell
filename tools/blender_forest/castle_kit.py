"""Fortification kit for the castle rework (phase 3c) -> castle_kit.glb (src/castle_kit.rs).

The architecture tells the story without words, in three layers:
  1. OLD COLONY STONE - grey, mossy, broken; only the BELL TOWER stands whole.
  2. OUR FRESH TIMBER - peeled logs, thatch, mud ramparts, lashings.
  3. CROWN colours   - another agent's set (not here).
Realism reference: KCD2 / Witcher 3 forts. Scale: hero ~1.17u, so 1u ~ 1.5 m.

PIVOT CONVENTION: ground at y=0, each piece centred on its footprint (wall pieces on the wall
line), +X runs along the wall, the OUTER (enemy) face looks toward -Z, the courtyard is +Z.
Foundations sink to y=-0.3. Wall modules are 4u and tile at x = +-2 (palisade, timber gate,
curtain; merlons period 1.0, UVs whole every 2u). Corner pieces (corner tower, curtain corner) are
centred on the crossing of two wall lines, outer faces -Z/-X; turn -90 deg about Y for the other end. The gatehouse is 6.4u on the wall line; its turrets project to -Z.
The palisade's ditch is only implied (muddy berm at z -1.5..-2.2); cut it into the terrain at
integration if a real ditch is wanted.

MANIFEST (bounding footprint x-range * z-range, top height; all in u):
  ck_bell_tower      x +-1.96, z -1.96..+3.98 (platform+ladder +Z)  cap 8.5, spike 8.96
                     shaft 3.2 wide on a stepped battered plinth, open belfry 5.2-7.55 with the
                     bronze bell on a timber frame, raised door + Pip's platform at 3.0, rope, ladder
  ck_ruin_keep       x -3.8..5.3, z -4.3..3.3 (rubble spill to +X/-Z)   6.3   roofless shell
                     (7.6 x 6.6, walls 0.9): broken W gable, collapsed SE corner, charred joists
  ck_ruin_wall_a     x +-3.1, z -2.4..0.8 (spill on -Z)               3.2   curtain fragment, breach
  ck_ruin_wall_b     x -2.0..2.6, z +-1.7                             2.3   low stump, fallen blocks
  ck_rubble          x +-1.7, z +-1.3                                 0.6   rubble pile
  ck_palisade        x +-2.0, z +-2.2 (rampart)                       3.0   logs (z -0.2) on a 0.45 bank,
                     inner walkway at 1.65 (+Z), muddy ditch berm (-Z)
  ck_timber_gate     x +-2.1, z -0.7..2.7                             4.3   2.8w x 2.7h opening, closed
                     leaves, fighting platform at 3.2, ladder +Z
  ck_watchtower      x +-1.65, z +-1.65                               5.5   platform 3.0, thatch cap
  ck_curtain         x +-2.0, z -1.2..0.84 (body 1.4 thick, batter)   3.96  walk 3.0, irregular merlons
                     ~3.9 with copings, sloped batter, spouts + stains; UVs repeat every 2u (seamless)
  ck_curtain_corner  x -0.95..0.7, z -0.95..0.7                       3.93  outer faces -Z and -X
  ck_stone_tower     x +-2.8, z -2.8..2.55 (batter + spouts)          6.41  mural tower 4.2: walk 5.4,
                     corbelled crenellated parapet, spouts with stains, put-log holes
  ck_corner_tower    x +-3.62, z +-3.62 (hoarding + roof eaves)       9.97  corner tower 4.6 on the
                     wall-line crossing (curtains attach on +X/+Z), timber hoarding on beams, plank roof
  ck_gatehouse       x +-4.0, z -3.7..2.34 (body 6.4 x 4.6)           6.98  passage along Z 2.8w x 2.7h,
                     segmental arch, portcullis half down, turrets to 6.98, gate merlons 6.68
  ck_keep_t1         x -4.05..4.25, z -4.4..3.9                       8.06  ruin shell + timber infill,
                     thatched roof (ridge 7.6), scaffolding on -Z
  ck_keep_t2         x -3.85..4.6, z -3.35..4.7 (stair turret NE)     9.48 (turret cap 11.15)  donjon
                     7 x 6, walk 8.6, first-floor door + timber stair on +Z

    blender -b --factory-startup --python tools/blender_forest/castle_kit.py
"""
import math
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402
from common import OUT, clear_scene, export_glb  # noqa: E402
from geo import G, frustum, quat_x, quat_y, quat_z  # noqa: E402
from meshkit import Builder  # noqa: E402
import wayside_models as W  # noqa: E402
from wayside_models import (M_BARK, M_PLANK, M_STONE, M_THATCH, M_CLOTH, M_IRON, M_ROCK, M_EARTH,  # noqa: E402
                            V, beam, board, bounds, charred, lashing, lbox, mix, mound, pole, rock_col, scale,
                            slab, smoothstep, stone, tube, Noise)
import stories_cold as SC  # noqa: E402  (aged-bronze bell recipe; same material table)

MATS = SC.MATS + ["s_masonry"]  # W.MATS + s_snow + bronze (the bell's M_BRONZE index) + masonry
Q0 = quat_y(0.0)

# Masonry is the mossy_rock scan, brightened (s_masonry), with the coursing drawn as joint strips —
# the mossy_stone_wall scan (s_stone) and plain s_rock read near-black on walls in game.
M_MASON = len(SC.MATS)  # "s_masonry": the s_rock scan lifted x2.1 in realforest (pale grey)
# Layer 1: old colony stone (cool grey, mossy and damp at the foot).
OLD_TOP = (0.97, 0.99, 1.0)
OLD_FOOT = (0.56, 0.62, 0.46)
# Our fresh stone tier: the same ruin stone re-dressed — paler, warmer, barely any moss.
NEW_TOP = (1.0, 0.96, 0.88)
NEW_FOOT = (0.6, 0.58, 0.47)
LOG = (0.92, 0.84, 0.72)        # fresh peeled bark_oak logs
TIMBER = (0.95, 0.86, 0.72)     # fresh hewn timber
OLD_TIMBER = (0.6, 0.58, 0.55)
MUD = (0.62, 0.52, 0.42)
THATCH = (0.95, 0.86, 0.66)
DARK = (0.08, 0.075, 0.07)      # openings / put-log holes
IRON = (0.4, 0.38, 0.36)


def old_col(y):
    return mix(OLD_FOOT, OLD_TOP, smoothstep(-0.2, 2.4, y))


def new_col(y):
    return mix(NEW_FOOT, NEW_TOP, smoothstep(-0.2, 1.6, y))


def sbox(g, x0, x1, y0, y1, z0, z1, colf=old_col, mat=M_MASON, tile=1.6):
    """Masonry box between bounds (game coords): stone courses level, the colour graded by height.
    UVs are offset to world position (u0 = cx + cz, v0 = cy) so neighbouring boxes of one wall run
    share the texture's courses instead of restarting at every box."""
    c = V((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
    lbox(g, c, (x1 - x0, y1 - y0, z1 - z0), Q0, mat, [colf(y0), None, colf(y1)], tile=tile, grain=1,
         u0=c.x + c.z, v0=c.y)


def flat(g, pts, mat, col, tile=1.5):
    g.flat([Vector(p) for p in pts], mat, col, tile)


def _ragged(g, rng, a0, a1, t0, t1, top, colf, gaps, along_x, course=0.4, cell=0.3):
    """A ruined wall built in HORIZONTAL COURSES (never columns): the wall runs a0..a1 along its
    length (X when `along_x`, else Z), t0..t1 thick. `top(u)` is the broken crown height along the
    length (jittered per cell, so the masonry breaks off in stair-steps along course lines).
    `gaps` = [(ua, ub, ya, yb)] openings (windows / a breach) left empty."""
    n = max(1, int(round((a1 - a0) / cell)))
    w = (a1 - a0) / n
    tops = [top(a0 + (i + 0.5) * w) + rng.uniform(-0.22, 0.22) for i in range(n)]
    hmax = max(tops)
    ya = -0.3
    first = True
    while ya < hmax - 0.05:
        yb = ya + (0.6 if first else course * rng.uniform(0.85, 1.15))
        first = False
        # cells where this course still stands (its whole height, or most of it)
        keep = [tops[i] >= yb - course * 0.35 for i in range(n)]
        for i in range(n):
            u = a0 + (i + 0.5) * w
            for ua, ub, gya, gyb in gaps:
                if ua < u < ub and ya < gyb and yb > gya:
                    keep[i] = False
        i = 0
        while i < n:
            if not keep[i]:
                i += 1
                continue
            j = i
            while j + 1 < n and keep[j + 1]:
                j += 1
            ua, ub = a0 + i * w, a0 + (j + 1) * w
            # Ragged ends: a stone sticks out or falls short where the course breaks off.
            if i > 0:
                ua += rng.uniform(-0.08, 0.1)
            if j < n - 1:
                ub += rng.uniform(-0.1, 0.08)
            if ub - ua > 0.12:
                if along_x:
                    sbox(g, ua, ub, ya, yb, t0, t1, colf)
                else:
                    sbox(g, t0, t1, ya, yb, ua, ub, colf)
            i = j + 1
        ya = yb


def ragged_wall(g, rng, x0, x1, z0, z1, top, colf=old_col, step=0.3, gaps=()):
    """A ruined wall along X (z0..z1 thick), built in courses — see `_ragged`."""
    _ragged(g, rng, x0, x1, z0, z1, top, colf, gaps, True, cell=step)


def ragged_wall_z(g, rng, z0, z1, x0, x1, top, colf=old_col, step=0.3, gaps=()):
    """`ragged_wall` running along Z (x0..x1 = thickness)."""
    _ragged(g, rng, z0, z1, x0, x1, top, colf, gaps, False, cell=step)


def rubble_spill(g, rng, cx, cz, rx, rz, n, colf=old_col, big=0.32):
    """A spill of fallen masonry: an earthy rubble mound with blocks and fieldstones on it."""
    mound(g, (cx, 0.0, cz), rx, rz, 0.45 * min(rx, rz), rng, mat=M_ROCK,
          col_fn=lambda p, nn: mix(OLD_FOOT, (0.7, 0.68, 0.62), smoothstep(0.0, 0.6, p.y)), tile=1.2, rings=4, seg=14)
    for _ in range(n):
        a = rng.uniform(0, 6.283)
        r = math.sqrt(rng.uniform(0, 1))
        x, z = cx + math.cos(a) * rx * r, cz + math.sin(a) * rz * r
        y = 0.45 * min(rx, rz) * (1 - r * r) * 0.8
        s = rng.uniform(0.45, 1.0) * big
        if rng.random() < 0.55:
            slab(g, (x, y + s * 0.3, z), (s * 1.6, s * 0.8, s * 1.1),
                 quat_y(rng.uniform(0, 6.28)) @ quat_x(rng.uniform(-0.3, 0.3)) @ quat_z(rng.uniform(-0.3, 0.3)), rng,
                 mat=M_MASON, res=(2, 1, 2), round_r=0.03, rough=0.05, cuts=1,
                 col_fn=lambda p, nn, yy=y: old_col(yy + 0.6), tile=1.6)
        else:
            stone(g, (x, y + s * 0.25, z), (s, s * 0.6, s * 0.8), rng, detail=1, cuts=1, tile=0.8,
                  col_fn=rock_col((0.8, 0.8, 0.78), moss=0.2, ground=0.0))


def charred_stub(g, rng, p0, p1):
    beam(g, [V(*p0), V(*p1)], 0.22, 0.22, mat=M_PLANK, col=charred(rng), rng=rng, jag=(0.0, 0.18), mode="timber")


def _merlon_jit(rng, colf):
    """Hand-laid irregularity for one merlon: (height delta, width delta, colour fn)."""
    if rng is None:
        return 0.0, 0.0, colf
    t = rng.uniform(0.9, 1.06)
    return rng.uniform(-0.08, 0.04), rng.uniform(-0.05, 0.03), (lambda y, c=colf, t=t: scale(c(y), t))


def merlons_x(g, x0, x1, z0, z1, y0, y1, colf, period=1.0, merlon=0.6, phase=0.0, rng=None, tile=1.6):
    """Merlons along X between x0..x1 (centres every `period`, offset `phase`), each with a coping
    stone; `rng` makes them irregular (worn, re-laid)."""
    k = math.floor((x0 - phase) / period) - 1
    while True:
        cxm = phase + k * period + period / 2
        dh, dw, cf = _merlon_jit(rng, colf)
        a, b = max(x0, cxm - merlon / 2 - dw), min(x1, cxm + merlon / 2 + dw)
        if cxm - merlon / 2 > x1:
            break
        if b - a > 0.05:
            sbox(g, a, b, y0, y1 + dh, z0, z1, cf, tile=tile)
            sbox(g, a - 0.04, b + 0.04, y1 + dh, y1 + dh + 0.08, z0 - 0.04, z1 + 0.04, cf, tile=1.2)  # coping
        k += 1


def merlons_z(g, z0, z1, x0, x1, y0, y1, colf, period=1.0, merlon=0.6, phase=0.0, rng=None, tile=1.6):
    k = math.floor((z0 - phase) / period) - 1
    while True:
        czm = phase + k * period + period / 2
        dh, dw, cf = _merlon_jit(rng, colf)
        a, b = max(z0, czm - merlon / 2 - dw), min(z1, czm + merlon / 2 + dw)
        if czm - merlon / 2 > z1:
            break
        if b - a > 0.05:
            sbox(g, x0, x1, y0, y1 + dh, a, b, cf, tile=tile)
            sbox(g, x0 - 0.04, x1 + 0.04, y1 + dh, y1 + dh + 0.08, a - 0.04, b + 0.04, cf, tile=1.2)  # coping
        k += 1


def quoins(g, rng, cx, cz, hx, hz, y0, y1, colf, h=0.34, long=0.58, short=0.34, proud=0.025):
    """Dressed corner stones up every corner of a block (cx, cz, half sizes hx, hz), alternating
    long / short faces course by course, a touch proud and lighter than the walling."""
    for sx in (-1, 1):
        for sz in (-1, 1):
            px, pz = cx + sx * (hx + proud), cz + sz * (hz + proud)
            y, k = y0, 0
            while y < y1 - 0.06:
                yy = min(y + h, y1)
                lx, lz = (long, short) if (k + (sx * sz > 0)) % 2 == 0 else (short, long)
                xa, xb = sorted((px, px - sx * lx))
                za, zb = sorted((pz, pz - sz * lz))
                tint = rng.uniform(1.02, 1.14)
                sbox(g, xa, xb, y + 0.012, yy - 0.012, za, zb, lambda q, t=tint: scale(colf(q), t), tile=1.2)
                y, k = yy, k + 1


def face_stones(g, rng, axis, fixed, sgn, a0, a1, y0, y1, colf, n, holes=0.35):
    """Weathering on a flat face: single stones a little proud (lighter or darker) and shadowed gaps
    where a stone has fallen out. axis "z": the face lies at z = fixed (outward normal sgn * Z) and
    spans x in a0..a1; axis "x": at x = fixed spanning z in a0..a1."""
    for _ in range(n):
        w, h = rng.uniform(0.32, 0.62), rng.uniform(0.16, 0.26)
        u = rng.uniform(a0 + w / 2 + 0.05, a1 - w / 2 - 0.05)
        y = rng.uniform(y0 + h, y1 - h)
        hole = rng.random() < holes
        d = 0.012 if hole else rng.uniform(0.025, 0.05)
        col = scale(colf(y), 0.42) if hole else scale(colf(y), rng.uniform(0.82, 1.14))
        f0, f1 = sorted((fixed, fixed + sgn * d))
        if axis == "z":
            sbox(g, u - w / 2, u + w / 2, y - h / 2, y + h / 2, f0, f1, lambda q, c=col: c, tile=1.2)
        else:
            sbox(g, f0, f1, y - h / 2, y + h / 2, u - w / 2, u + w / 2, lambda q, c=col: c, tile=1.2)


def joints(g, rng, cx, cz, hx, hz, y0, y1, colf, faces="nsew", course=0.42, unit=(0.55, 0.95), rubble=False):
    """Mortar joints drawn on the faces of a block (cx, cz, half sizes hx, hz) between y0 and y1:
    a dark bed-joint strip every course and staggered head joints, so a plain box reads as coursed
    masonry. faces: n = +Z, s = -Z, e = +X, w = -X."""
    d, t = 0.008, 0.035
    for f in faces:
        sgn = 1 if f in "ne" else -1
        along_x = f in "ns"
        fixed = (cz + sgn * hz) if along_x else (cx + sgn * hx)
        a0, a1 = (cx - hx, cx + hx) if along_x else (cz - hz, cz + hz)
        f0, f1 = sorted((fixed - sgn * 0.004, fixed + sgn * d))
        y = y0 + course * rng.uniform(0.6, 1.0)
        while y < y1 - 0.08:
            c = scale(colf(y), 0.5)
            if along_x:
                sbox(g, a0, a1, y - t / 2, y + t / 2, f0, f1, lambda q, c=c: c, tile=2.0)
            else:
                sbox(g, f0, f1, y - t / 2, y + t / 2, a0, a1, lambda q, c=c: c, tile=2.0)
            step = rng.uniform(0.2, 0.38) if rubble else course
            yn = min(y + step, y1)
            u = a0 + rng.uniform(0.1, unit[1])
            while u < a1 - 0.15:
                if along_x:
                    sbox(g, u - t / 2, u + t / 2, y, yn, f0, f1, lambda q, c=c: c, tile=2.0)
                else:
                    sbox(g, f0, f1, y, yn, u - t / 2, u + t / 2, lambda q, c=c: c, tile=2.0)
                u += rng.uniform(*unit)
            y = yn


def batter(g, x0, x1, z0, z1, y0, y1, colf, out=(0.4, 0.4, 0.4, 0.4), tile=2.0):
    """A sloped (battered) plinth: the wall footprint x0..x1, z0..z1 at the top (y1), each side
    flaring out at the foot (y0) by out = (-Z, +X, +Z, -X), with a projecting plinth course on top."""
    oS, oE, oN, oW = out
    bot = [V(x0 - oW, y0, z0 - oS), V(x1 + oE, y0, z0 - oS), V(x1 + oE, y0, z1 + oN), V(x0 - oW, y0, z1 + oN)]
    top = [V(x0, y1, z0), V(x1, y1, z0), V(x1, y1, z1), V(x0, y1, z1)]
    c = V((x0 + x1) / 2, 0, (z0 + z1) / 2)
    for i in range(4):
        j = (i + 1) % 4
        q = [bot[i], bot[j], top[j], top[i]]
        mid = (bot[i] + bot[j]) / 2
        if (q[1] - q[0]).cross(q[3] - q[0]).dot(V(mid.x - c.x, 0, mid.z - c.z)) < 0:
            q = q[::-1]
        cols = [colf(p.y) for p in q]
        g.flat(q, M_MASON, cols, tile)
    # plinth course (not past an end with no flare, so wall modules butt cleanly)
    ex = [0.05 if o > 0 else 0.0 for o in out]
    sbox(g, x0 - ex[3], x1 + ex[1], y1 - 0.02, y1 + 0.12, z0 - ex[0], z1 + ex[2], colf, tile=tile)


def streak(g, axis, fixed, sgn, u, y_top, length, colf, width=0.22, dark=0.45):
    """A rain / damp streak running down a face from y_top (dark) fading into the wall below."""
    d = 0.006
    f0, f1 = sorted((fixed, fixed + sgn * d))
    y0 = y_top - length
    col = [colf(y0), None, scale(colf(y_top), dark)]
    if axis == "z":
        lbox(g, V(u, (y0 + y_top) / 2, (f0 + f1) / 2), (width, length, f1 - f0), Q0, M_MASON, col, tile=2.0)
    else:
        lbox(g, V((f0 + f1) / 2, (y0 + y_top) / 2, u), (f1 - f0, length, width), Q0, M_MASON, col, tile=2.0)


def spout(g, axis, fixed, sgn, u, y, colf, reach=0.5, streak_len=1.6, wall=None):
    """A stone drain spout (plain gargoyle) poking out of a face at height y, a dark channel in its
    top, and the water stain it leaves down the wall."""
    w = 0.2
    f0, f1 = sorted((fixed, fixed + sgn * reach))
    if axis == "z":
        sbox(g, u - w / 2, u + w / 2, y - 0.1, y + 0.08, f0, f1, colf, tile=1.2)
        sbox(g, u - w / 2 - 0.04, u + w / 2 + 0.04, y - 0.22, y - 0.1, *sorted((fixed, fixed + sgn * reach * 0.45)), colf, tile=1.2)
        lbox(g, V(u, y + 0.081, (f0 + f1) / 2 + sgn * 0.05), (0.08, 0.004, reach - 0.1), Q0, M_STONE, DARK, tile=2.0)
    else:
        sbox(g, f0, f1, y - 0.1, y + 0.08, u - w / 2, u + w / 2, colf, tile=1.2)
        sbox(g, *sorted((fixed, fixed + sgn * reach * 0.45)), y - 0.22, y - 0.1, u - w / 2 - 0.04, u + w / 2 + 0.04, colf, tile=1.2)
        lbox(g, V((f0 + f1) / 2 + sgn * 0.05, y + 0.081, u), (reach - 0.1, 0.004, 0.08), Q0, M_STONE, DARK, tile=2.0)
    streak(g, axis, fixed if wall is None else wall, sgn, u, y - 0.22, streak_len, colf, width=0.26)


def dark_patch(g, c, size):
    """A recessed opening / put-log hole: a near-black box sunk into the face."""
    lbox(g, c, size, Q0, M_STONE, DARK, tile=2.0)


def arch_x(g, rng, cx, cy, r, z0, z1, colf, n=7, block=0.24, t0=0.0):
    """An arch of voussoirs in the XY plane about centre (cx, cy), depth z0..z1. t0 = 0 gives a round
    arch springing at cy; t0 > 0 a segmental arch over angles t0..pi-t0."""
    for k in range(n):
        t = t0 + (math.pi - 2 * t0) * (k + 0.5) / n
        p = (cx + math.cos(t) * (r + block / 2), cy + math.sin(t) * (r + block / 2), (z0 + z1) / 2)
        slab(g, p, (block * 1.15, block, z1 - z0), quat_z(t + math.pi / 2), rng, mat=M_MASON, res=(2, 1, 2),
             round_r=0.02, rough=0.03, col_fn=lambda q, nn: colf(q.y), tile=1.6)


def arch_z(g, rng, cz, cy, r, x0, x1, colf, n=7, block=0.24):
    """A round arch in the ZY plane (passage along X), depth x0..x1."""
    for k in range(n):
        t = math.pi * (k + 0.5) / n
        p = ((x0 + x1) / 2, cy + math.sin(t) * (r + block / 2), cz + math.cos(t) * (r + block / 2))
        slab(g, p, (x1 - x0, block, block * 1.15), quat_x(-(t + math.pi / 2)), rng, mat=M_MASON, res=(2, 1, 2),
             round_r=0.02, rough=0.03, col_fn=lambda q, nn: colf(q.y), tile=1.6)


def ladder(g, rng, foot, top, w=0.45, col=TIMBER):
    f, t = Vector(foot), Vector(top)
    side = V(1, 0, 0)
    for s in (-1, 1):
        beam(g, [f + side * s * w / 2, t + side * s * w / 2], 0.07, 0.06, mat=M_PLANK, col=col, rng=rng)
    n = int((t - f).length / 0.33)
    for k in range(1, n):
        p = f.lerp(t, k / n)
        beam(g, [p - side * w / 2, p + side * w / 2], 0.045, 0.045, mat=M_PLANK, col=col, rng=rng)


def railing(g, rng, pts, h=0.95, col=TIMBER):
    """Posts at each point + a top rail and a mid rail."""
    pts = [Vector(p) for p in pts]
    for p in pts:
        beam(g, [p, p + V(0, h, 0)], 0.09, 0.09, mat=M_PLANK, col=col, rng=rng)
    for yy in (h, h * 0.5):
        beam(g, [p + V(0, yy, 0) for p in pts], 0.07, 0.06, mat=M_PLANK, col=col, rng=rng)


# ─────────────────────────────────────────────────────────────── 1. THE OLD BELL TOWER

def ck_bell_tower(rng):
    """The one thing still standing: a square old-colony stone tower (3.2 wide shaft, cap at 8.5),
    battered stepped plinth, string courses, slit windows, an OPEN BELFRY (a round arch on each face
    between corner piers) with the bronze bell on a timber bell-frame, a low stone pyramid cap with
    an iron spike. The only way in is the raised door on the courtyard face (+Z): Pip's wooden
    platform on brackets at 3.0, a ladder from the ground, the bell rope hanging down to it."""
    b = Builder()
    g = G(b)
    H = 1.6  # half width of the shaft
    # Battered plinth: three receding steps, then the shaft.
    sbox(g, -H - 0.32, H + 0.32, -0.3, 0.55, -H - 0.32, H + 0.32)
    sbox(g, -H - 0.17, H + 0.17, 0.55, 0.9, -H - 0.17, H + 0.17)
    sbox(g, -H - 0.07, H + 0.07, 0.9, 1.1, -H - 0.07, H + 0.07)
    sbox(g, -H, H, 1.1, 5.0, -H, H)
    sbox(g, -H - 0.06, H + 0.06, 2.85, 2.98, -H - 0.06, H + 0.06, tile=1.2)       # string course
    quoins(g, rng, 0.0, 0.0, H, H, 1.1, 5.0, old_col)
    joints(g, rng, 0.0, 0.0, H, H, 1.1, 5.0, old_col, unit=(0.28, 0.62), rubble=True)
    for nx, nz in ((0, -1), (1, 0), (-1, 0)):  # damp streaks under the belfry sill
        for u in (-0.9, 0.7):
            streak(g, "z" if nz else "x", (nz or nx) * (H + 0.0), nz or nx, u + rng.uniform(-0.2, 0.2), 5.0,
                   rng.uniform(1.0, 2.2), old_col, width=rng.uniform(0.18, 0.34), dark=0.55)
    for sgn in (-1, 1):
        face_stones(g, rng, "z", sgn * H, sgn, -H + 0.4, H - 0.4, 1.2, 4.9, old_col, 9)
        face_stones(g, rng, "x", sgn * H, sgn, -H + 0.4, H - 0.4, 1.2, 4.9, old_col, 9)
    sbox(g, -H - 0.12, H + 0.12, 5.0, 5.2, -H - 0.12, H + 0.12, tile=1.2)         # belfry sill course
    # Belfry: four corner piers to the band; a round arch (r 1.0, springing 6.3) on every face.
    P, D, R, SP = 0.6, 0.45, 1.0, 6.3
    for sx in (-1, 1):
        for sz in (-1, 1):
            x0, x1 = (H - P, H) if sx > 0 else (-H, -H + P)
            z0, z1 = (H - P, H) if sz > 0 else (-H, -H + P)
            sbox(g, x0, x1, 5.2, 7.55, z0, z1)
    for s in (-1, 1):
        f0, f1 = (s * H - D, s * H + 0.04) if s > 0 else (s * H - 0.04, s * H + D)
        w0, w1 = (s * H - D, s * H) if s > 0 else (s * H, s * H + D)
        arch_x(g, rng, 0.0, SP, R, f0, f1, old_col, n=7, block=0.22)
        arch_z(g, rng, 0.0, SP, R, f0, f1, old_col, n=7, block=0.22)
        for q in (-1, 1):  # spandrels between the arch and the piers
            a0, a1 = sorted((q * 0.5, q * 1.0))
            sbox(g, a0, a1, 6.95, 7.55, w0, w1)
            sbox(g, w0, w1, 6.95, 7.55, a0, a1)
        r0, r1 = (w0 + 0.04, w1 - 0.04)
        sbox(g, -0.5, 0.5, 7.25, 7.55, r0, r1)     # crown filler, recessed behind the voussoirs
        sbox(g, r0, r1, 7.25, 7.55, -0.5, 0.5)
    sbox(g, -H - 0.05, H + 0.05, 7.55, 7.75, -H - 0.05, H + 0.05)
    sbox(g, -H - 0.18, H + 0.18, 7.75, 7.92, -H - 0.18, H + 0.18, tile=1.2)       # cornice
    apex = V(0, 8.5, 0)
    e = H + 0.12
    corners = [V(-e, 7.92, -e), V(e, 7.92, -e), V(e, 7.92, e), V(-e, 7.92, e)]
    for i in range(4):
        a, c = corners[i], corners[(i + 1) % 4]
        tri = [a, apex, c] if (apex - a).cross(c - a).y > 0 else [a, c, apex]
        flat(g, tri, M_MASON, [scale(OLD_TOP, 0.82)] * 3, tile=1.2)
    pole(g, apex - V(0, 0.05, 0), apex + V(0, 0.45, 0), 0.06, 0.02, rng, mat=M_IRON, col=IRON, sides=6, segs=1)
    # Slit windows on the outer and side faces.
    for y in (2.2, 3.9):
        for nx, nz in ((0, -1), (1, 0), (-1, 0)):
            c = V(nx * (H + 0.005), y, nz * (H + 0.005))
            dark_patch(g, c, (0.06 if nx else 0.15, 0.7, 0.15 if nx else 0.06))
    dark_patch(g, V(0.0, 3.9, H + 0.005), (0.15, 0.7, 0.06))
    # The raised door at platform level (x = 0.35), round-headed, old planks.
    py = 3.0
    dx = 0.35
    dark_patch(g, V(dx, py + 0.75, H + 0.005), (0.76, 1.5, 0.06))
    arch_x(g, rng, dx, py + 1.15, 0.38, H - 0.06, H + 0.08, old_col, n=5, block=0.18)
    for k in range(3):
        board(g, V(dx - 0.24 + k * 0.24, py + 0.62, H + 0.015), V(0, 1, 0), V(0, 0, 1), 1.24, 0.23, 0.04,
              mat=M_PLANK, col=OLD_TIMBER, rng=rng)
    # The bell frame on the belfry floor: two trestles, a headstock, the bronze bell + clapper.
    for x in (-0.9, 0.9):
        for z in (-0.55, 0.55):
            beam(g, [V(x, 5.2, z), V(x, 6.85, 0.0)], 0.16, 0.16, mat=M_PLANK, col=OLD_TIMBER, rng=rng)
        beam(g, [V(x, 5.25, -0.7), V(x, 5.25, 0.7)], 0.16, 0.14, mat=M_PLANK, col=OLD_TIMBER, rng=rng)
    beam(g, [V(-1.05, 6.97, 0.0), V(1.05, 6.97, 0.0)], 0.26, 0.28, mat=M_PLANK, col=OLD_TIMBER, rng=rng)
    SC.bell(g, rng, (0.0, 5.82, 0.0), Q0, h=0.95, r=0.52, seg=20)
    tube(g, [V(0, 6.6, 0), V(0, 5.95, 0.02)], [0.03, 0.03], 6, SC.M_BRONZE, scale(SC.BRONZE, 0.7), tile=0.3)
    stone(g, (0.0, 5.92, 0.02), (0.08, 0.1, 0.08), rng, mat=SC.M_BRONZE, detail=1, cuts=0, rough=0.05, tile=0.3,
          col_fn=lambda p, n: scale(SC.BRONZE, 0.8))
    # The rope: off the bell wheel, out over the courtyard arch sill and down beside the door.
    rp = [V(-0.3, 6.75, 0.25), V(-0.38, 6.15, 1.0), V(-0.42, 5.32, H + 0.24), V(-0.45, 4.6, H + 0.27),
          V(-0.45, 3.85, H + 0.3)]
    tube(g, rp, [0.024] * len(rp), 5, M_CLOTH, W.ROPE, tile=0.25)
    # Pip's platform: joists into the wall on raking struts, plank deck, rails, ladder from the ground.
    zf, zb = H, H + 1.3
    for x in (-1.0, 0.1, 1.15):
        beam(g, [V(x, py - 0.1, zf - 0.15), V(x, py - 0.1, zb)], 0.15, 0.17, mat=M_PLANK, col=TIMBER, rng=rng)
        beam(g, [V(x, py - 1.3, zf + 0.02), V(x, py - 0.18, zb - 0.2)], 0.12, 0.12, mat=M_PLANK, col=TIMBER, rng=rng)
    for k in range(4):
        board(g, V(0.05, py, zf + 0.17 + k * 0.33), V(1, 0, 0), V(0, 1, 0), 2.6, 0.32, 0.05, mat=M_PLANK,
              col=mix(TIMBER, OLD_TIMBER, rng.uniform(0, 0.3)), rng=rng)
    railing(g, rng, [V(-0.4, py, zb - 0.02), V(0.45, py, zb - 0.02), V(1.3, py, zb - 0.02)], h=0.9)
    railing(g, rng, [V(1.3, py, zf + 0.12), V(1.3, py, zb - 0.02)], h=0.9)
    railing(g, rng, [V(-1.2, py, zf + 0.12), V(-1.2, py, zb - 0.45)], h=0.9)
    ladder(g, rng, V(-0.8, -0.05, H + 2.35), V(-0.8, py + 0.85, zb + 0.02))
    # Moss on the plinth ledges and the sill course.
    for s in range(4):
        a = s * math.pi / 2
        for rr, y, w in ((H + 0.24, 0.55, 0.7), (H + 0.11, 0.9, 0.45)):
            c = (math.cos(a) * rr + rng.uniform(-0.6, 0.6) * abs(math.sin(a)), y,
                 math.sin(a) * rr + rng.uniform(-0.6, 0.6) * abs(math.cos(a)))
            mound(g, c, w if abs(math.sin(a)) > 0.5 else 0.12, 0.12 if abs(math.sin(a)) > 0.5 else w, 0.05, rng,
                  mat=M_ROCK, col_fn=lambda p, n: (0.34, 0.45, 0.22), tile=1.0, rings=2, seg=8, skirt=0.0)
    return b


# ─────────────────────────────────────────────────────────────── 2. RUINS OF THE OLD FORT

def keep_shell(g, rng, roofless=True):
    """The old keep's shell: 7.6 x 6.6 outside, walls 0.9 thick. The west gable stands highest and
    broken, the SE corner has collapsed into a rubble spill, charred joist stubs in the walls."""
    X, Z, T = 3.8, 3.3, 0.9
    # South (outer, -Z) wall: high in the west, collapsing toward the SE corner.
    ragged_wall(g, rng, -X, X, -Z, -Z + T, lambda x: 4.6 - 3.6 * smoothstep(0.6, 3.6, x),
                gaps=[(-2.2, -1.5, 2.0, 3.2), (-0.2, 0.5, 2.0, 3.2)])
    # North wall: standing to ~4.8 with windows; its east end broken down.
    ragged_wall(g, rng, -X, X, Z - T, Z, lambda x: 4.8 - 1.8 * smoothstep(2.2, 3.8, x),
                gaps=[(-1.8, -1.1, 2.2, 3.4), (0.6, 1.3, 2.2, 3.4), (2.3, 3.0, 0.0, 2.3)])
    # West gable: rises to a broken peak (~6.4).
    ragged_wall_z(g, rng, -Z + T, Z - T, -X, -X + T, lambda z: 4.6 + 1.8 * (1 - abs(z) / Z) - (0.9 if z > 0.6 else 0.0),
                  gaps=[(-0.4, 0.3, 3.0, 4.2)])
    # East wall: mostly fallen.
    ragged_wall_z(g, rng, -Z + T, Z - T, X - T, X, lambda z: 2.2 + 0.8 * smoothstep(-2.0, 2.0, z) - (1.4 if z < -0.8 else 0.0))
    # Charred joist stubs where the floor burnt out (in the N and S walls at the first-floor line).
    for x in (-2.6, -1.0, 0.4, 1.8):
        charred_stub(g, rng, (x, 2.75, Z - T - 0.02), (x + rng.uniform(-0.1, 0.1), 2.7, Z - T - 0.55))
        if x < 1.0:
            charred_stub(g, rng, (x, 2.75, -Z + T + 0.02), (x, 2.68, -Z + T + 0.4 + rng.uniform(0, 0.3)))
    return X, Z, T


def ck_ruin_keep(rng):
    """Roofless ruined keep shell (tier 0) + the rubble spill out of its collapsed SE corner and a few
    fallen charred beams inside."""
    b = Builder()
    g = G(b)
    X, Z, T = keep_shell(g, rng)
    rubble_spill(g, rng, X - 0.4, -Z + 0.4, 1.9, 1.5, 14)
    rubble_spill(g, rng, 0.5, 0.6, 1.6, 1.3, 6, big=0.26)
    for p0, p1 in (((-2.4, 0.15, -1.6), (0.6, 1.4, 1.9)), ((1.4, 0.12, -0.6), (-0.6, 0.2, 1.5))):
        beam(g, [V(*p0), V(*p1)], 0.22, 0.22, mat=M_PLANK, col=charred(rng), rng=rng, jag=(0.15, 0.15))
    return b


def ck_ruin_wall_a(rng):
    """Old curtain fragment, 6u along X, 1.3 thick: two stretches to ~3.4 with a breach between,
    a fallen-block spill out of the breach on the outer side."""
    b = Builder()
    g = G(b)
    ragged_wall(g, rng, -3.0, 3.0, -0.65, 0.65,
                lambda x: 3.3 - 2.9 * math.exp(-((x - 0.4) / 0.9) ** 2) - 0.6 * smoothstep(2.0, 3.0, x))
    sbox(g, -3.1, 3.1, -0.3, 0.45, -0.8, 0.8)  # footing
    rubble_spill(g, rng, 0.4, -1.4, 1.5, 0.9, 9)
    return b


def ck_ruin_wall_b(rng):
    """A low stump of old curtain (4u, ~1.2–2.4) with its blocks tumbled on both sides."""
    b = Builder()
    g = G(b)
    ragged_wall(g, rng, -2.0, 2.0, -0.65, 0.65, lambda x: 1.9 + 0.5 * math.sin(x * 1.7) - 0.6 * smoothstep(0.8, 2.0, x),)
    rubble_spill(g, rng, 1.6, 0.9, 1.0, 0.7, 6, big=0.28)
    rubble_spill(g, rng, -1.0, -1.1, 1.1, 0.6, 5, big=0.28)
    return b


def ck_rubble(rng):
    b = Builder()
    g = G(b)
    rubble_spill(g, rng, 0.0, 0.0, 1.6, 1.3, 14)
    return b


# ─────────────────────────────────────────────────────────────── 3. TIMBER TIER

def rampart(g, x0, x1, rng):
    """Earth rampart along X: inner foot z=+2.2, crest 0.45 high at z -0.6..+0.4, outer slope to a
    muddy ditch berm at z -2.2 (the ditch itself is cut into the terrain at integration)."""
    prof = [(2.2, -0.15), (1.2, 0.2), (0.4, 0.45), (-0.6, 0.45), (-1.5, 0.05), (-1.9, -0.12), (-2.2, -0.2)]
    for (za, ya), (zb, yb) in zip(prof, prof[1:]):
        pts = [V(x0, ya, za), V(x1, ya, za), V(x1, yb, zb), V(x0, yb, zb)]
        ca, cb = (mix(MUD, (0.55, 0.62, 0.4), 0.35) if ya > 0.3 else MUD), (MUD if yb < 0.1 else mix(MUD, (0.55, 0.62, 0.4), 0.35))
        if zb < -1.4:
            ca, cb = scale(MUD, 0.7), scale(MUD, 0.55)
        n = (pts[1] - pts[0]).cross(pts[3] - pts[0])
        if n.y < 0:
            pts = pts[::-1]
        g.flat(pts, M_EARTH, [ca, ca, cb, cb] if n.y >= 0 else [cb, cb, ca, ca], 1.6)
        for x, sgn in ((x0, -1), (x1, 1)):  # end caps (hidden when modules abut)
            q = [V(x, ya, za), V(x, yb, zb), V(x, -0.3, zb), V(x, -0.3, za)]
            if (q[1] - q[0]).cross(q[2] - q[0]).x * sgn < 0:
                q = q[::-1]
            g.flat(q, M_EARTH, scale(MUD, 0.8), 1.6)


def ck_palisade(rng):
    """Palisade module, 4u along X: sharpened oak logs (~2.4 above the crest, tops 2.85) set in an
    earth rampart, two lashed inner rails, a plank walkway on posts on the inside (+Z) at 1.65."""
    b = Builder()
    g = G(b)
    rampart(g, -2.0, 2.0, rng)
    n = 13
    for k in range(n):
        x = -2.0 + (k + 0.5) * 4.0 / n
        r = rng.uniform(0.13, 0.155)
        top = 2.6 + rng.uniform(-0.1, 0.1)
        z = -0.2 + rng.uniform(-0.02, 0.02)
        pole(g, (x, 0.0, z), (x + rng.uniform(-0.02, 0.02), top, z), r, r * 0.92, rng, mat=M_BARK,
             col_fn=lambda t: mix(scale(LOG, 0.6), LOG, smoothstep(0.05, 0.45, t)), sides=7, segs=2)
        frustum(g, r * 0.92, 0.012, top, 0.32, 7, M_PLANK, TIMBER, tile=0.5, centre=(x, 0, z))
    for y in (1.05, 2.15):
        beam(g, [V(-2.0, y, 0.0), V(2.0, y, 0.0)], 0.14, 0.12, mat=M_PLANK, col=TIMBER, rng=rng)
        for x in (-1.4, 0.6):
            lashing(g, V(x, y, -0.06), (0, 1, 0), 0.17, rng, turns=2)
    # Walkway: posts, joists, deck boards.
    for x in (-1.5, 0.0, 1.5):
        beam(g, [V(x, 0.0, 1.05), V(x, 1.6, 1.05)], 0.16, 0.16, mat=M_PLANK, col=TIMBER, rng=rng)
        beam(g, [V(x, 1.58, 0.1), V(x, 1.58, 1.15)], 0.12, 0.14, mat=M_PLANK, col=TIMBER, rng=rng)
    for k in range(3):
        board(g, V(0.0, 1.68, 0.25 + k * 0.33), V(1, 0, 0), V(0, 1, 0), 4.0, 0.32, 0.05, mat=M_PLANK,
              col=mix(TIMBER, OLD_TIMBER, rng.uniform(0, 0.25)), rng=rng)
    return b


def ck_timber_gate(rng):
    """Timber gate module (4u along X): two big oak gateposts, a lintel, closed double leaves of
    planks on Z-braces (opening 2.8 wide x 2.7 high), a fighting platform over the gate with a
    log breastwork on the outer side and a ladder down inside."""
    b = Builder()
    g = G(b)
    for s in (-1, 1):
        pole(g, (s * 1.62, -0.3, 0.0), (s * 1.62, 4.0, 0.0), 0.24, 0.21, rng, mat=M_BARK, col=LOG, sides=8)
        frustum(g, 0.21, 0.02, 4.0, 0.3, 8, M_PLANK, TIMBER, tile=0.5, centre=(s * 1.62, 0, 0.0))
        pole(g, (s * 1.95, -0.3, 0.05), (s * 1.95, 3.3, 0.05), 0.15, 0.14, rng, mat=M_BARK, col=LOG, sides=7)
    beam(g, [V(-1.9, 2.85, 0.0), V(1.9, 2.85, 0.0)], 0.3, 0.3, mat=M_PLANK, col=TIMBER, rng=rng)
    # Leaves (closed), planks vertical, Z-brace on the inner side.
    for s in (-1, 1):
        x0, x1 = (0.0, 1.38) if s > 0 else (-1.38, 0.0)
        for k in range(5):
            x = x0 + (k + 0.5) * (x1 - x0) / 5
            board(g, V(x, 1.35, -0.02), V(0, 1, 0), V(0, 0, 1), 2.7, (x1 - x0) / 5 * 0.97, 0.08, mat=M_PLANK,
                  col=mix(TIMBER, OLD_TIMBER, rng.uniform(0, 0.2)), rng=rng)
        for y in (0.45, 2.25):
            beam(g, [V(x0 + 0.06, y, 0.08), V(x1 - 0.06, y, 0.08)], 0.16, 0.06, mat=M_PLANK, col=TIMBER, rng=rng)
        beam(g, [V(x0 + 0.1, 0.5, 0.08), V(x1 - 0.1, 2.2, 0.08)] if s > 0 else [V(x1 - 0.1, 0.5, 0.08), V(x0 + 0.1, 2.2, 0.08)],
             0.14, 0.06, mat=M_PLANK, col=TIMBER, rng=rng)
        tube(g, [V(s * 0.12, 1.3, -0.08), V(s * 0.12, 1.5, -0.12), V(s * 0.12, 1.7, -0.08)], [0.018] * 3, 5, M_IRON,
             IRON, tile=0.2)
    # Fighting platform over the gate: joists on the lintel + a rear beam on posts, deck, breastwork.
    for s in (-1, 1):
        pole(g, (s * 1.6, -0.3, 1.25), (s * 1.6, 3.0, 1.25), 0.13, 0.12, rng, mat=M_BARK, col=LOG, sides=7)
    beam(g, [V(-1.9, 2.95, 1.25), V(1.9, 2.95, 1.25)], 0.2, 0.2, mat=M_PLANK, col=TIMBER, rng=rng)
    for x in (-1.6, -0.55, 0.55, 1.6):
        beam(g, [V(x, 3.08, -0.5), V(x, 3.08, 1.4)], 0.13, 0.14, mat=M_PLANK, col=TIMBER, rng=rng)
    for k in range(6):
        board(g, V(0.0, 3.18, -0.4 + k * 0.32), V(1, 0, 0), V(0, 1, 0), 3.9, 0.31, 0.05, mat=M_PLANK,
              col=mix(TIMBER, OLD_TIMBER, rng.uniform(0, 0.25)), rng=rng)
    for k in range(13):
        x = -1.95 + (k + 0.5) * 3.9 / 13
        r = rng.uniform(0.11, 0.13)
        pole(g, (x, 2.9, -0.55), (x, 4.15 + rng.uniform(-0.08, 0.08), -0.55), r, r * 0.9, rng, mat=M_BARK, col=LOG,
             sides=6, segs=1)
    beam(g, [V(-2.0, 3.75, -0.42), V(2.0, 3.75, -0.42)], 0.12, 0.1, mat=M_PLANK, col=TIMBER, rng=rng)
    ladder(g, rng, V(1.0, -0.05, 2.65), V(1.0, 4.0, 1.42))
    return b


def ck_watchtower(rng):
    """Timber watchtower (~5.6u): four splayed log legs (2.6 apart at the foot, 2.1 at the deck), X
    braces, a plank platform at 3.0 behind a plank breastwork to 4.0, four roof posts carrying a
    thatched pyramid cap (eaves 4.3, apex 5.4), an inner ladder up through a hatch."""
    b = Builder()
    g = G(b)
    fy, ey, ty = 3.0, 4.45, 5.4

    def leg(y):
        return 1.3 - 0.25 * (y + 0.3) / (fy + 0.3)

    for sx in (-1, 1):
        for sz in (-1, 1):
            pole(g, (sx * 1.3, -0.3, sz * 1.3), (sx * leg(fy), fy - 0.05, sz * leg(fy)), 0.17, 0.15, rng, mat=M_BARK,
                 col_fn=lambda t: mix(scale(LOG, 0.6), LOG, smoothstep(0.0, 0.3, t)), sides=7)
    sides = [((-1, -1), (1, -1)), ((1, -1), (1, 1)), ((1, 1), (-1, 1)), ((-1, 1), (-1, -1))]
    for (ax, az), (bx, bz) in sides:
        for y0, y1 in ((0.3, 1.6), (1.6, 2.85)):
            f0, f1 = leg(y0), leg(y1)
            beam(g, [V(ax * f0, y0, az * f0), V(bx * f1, y1, bz * f1)], 0.1, 0.1, mat=M_PLANK, col=TIMBER, rng=rng)
            beam(g, [V(bx * f0, y0, bz * f0), V(ax * f1, y1, az * f1)], 0.1, 0.1, mat=M_PLANK, col=TIMBER, rng=rng)
    for s in (-1, 1):
        beam(g, [V(-1.3, fy - 0.12, s * 1.03), V(1.3, fy - 0.12, s * 1.03)], 0.16, 0.18, mat=M_PLANK, col=TIMBER, rng=rng)
    for k in range(9):
        board(g, V(-1.28 + (k + 0.5) * 0.284, fy, 0.0), V(0, 0, 1), V(0, 1, 0), 2.6, 0.28, 0.05, mat=M_PLANK,
              col=mix(TIMBER, OLD_TIMBER, rng.uniform(0, 0.25)), rng=rng)
    # Plank breastwork, three boards high, on all four sides.
    for side in range(4):
        a = side * math.pi / 2
        d, nrm = V(-math.sin(a), 0, math.cos(a)), V(math.cos(a), 0, math.sin(a))
        for k in range(3):
            board(g, nrm * 1.28 + V(0, fy + 0.2 + k * 0.29, 0), d, nrm, 2.62, 0.28, 0.05, mat=M_PLANK,
                  col=mix(TIMBER, OLD_TIMBER, rng.uniform(0, 0.3)), rng=rng)
    # Roof posts at the corners + thatch pyramid (two shells: top faces up, underside faces down).
    for sx in (-1, 1):
        for sz in (-1, 1):
            beam(g, [V(sx * 1.1, fy - 0.1, sz * 1.1), V(sx * 1.1, ey, sz * 1.1)], 0.13, 0.13, mat=M_PLANK, col=TIMBER,
                 rng=rng)
    e = 1.65
    for off, up in ((0.14, True), (0.0, False)):
        apex = V(0, ty + off, 0)
        cs = [V(-e, ey - 0.12 + off, -e), V(e, ey - 0.12 + off, -e), V(e, ey - 0.12 + off, e), V(-e, ey - 0.12 + off, e)]
        for i in range(4):
            a, c = cs[i], cs[(i + 1) % 4]
            tri = [a, apex, c] if ((apex - a).cross(c - a).y > 0) == up else [a, c, apex]
            flat(g, tri, M_THATCH, scale(THATCH, 0.9 if up else 0.55), tile=1.2)
    for i in range(4):  # the eave edge band joining the two shells
        a, c = cs[i], cs[(i + 1) % 4]
        q = [a, c, c + V(0, 0.14, 0), a + V(0, 0.14, 0)]
        mid = (a + c) / 2
        if (q[1] - q[0]).cross(q[3] - q[0]).dot(V(mid.x, 0, mid.z)) < 0:
            q = q[::-1]
        flat(g, q, M_THATCH, scale(THATCH, 0.7), tile=0.6)
    ladder(g, rng, V(0.5, -0.05, 0.05), V(0.5, fy + 0.85, 0.7), w=0.42)
    return b


# ─────────────────────────────────────────────────────────────── 4. STONE TIER

def putlogs_x(g, x0, x1, z, ys, step=1.0, phase=0.5):
    x = x0 + phase
    while x < x1 - 0.1:
        for y in ys:
            dark_patch(g, V(x, y, z), (0.16, 0.16, 0.06))
        x += step


def ck_curtain(rng):
    """Curtain module 4u along X, tiling seamlessly on straight runs (UVs repeat whole every 2u,
    merlons period 1.0 centred +-0.5 / +-1.5): body 1.4 thick (z -0.7..+0.7) on a sloped battered
    plinth (outer flare 0.4), coursed ashlar, wall-walk at 3.0, an outer breastwork (-Z) to 3.35 and
    irregular merlons with copings to ~3.9, a string course under the walk, two drain spouts with
    their water stains, put-log holes, a low inner kerb."""
    b = Builder()
    g = G(b)
    T = 2.0
    batter(g, -2.0, 2.0, -0.7, 0.7, -0.3, 0.95, new_col, out=(0.4, 0.0, 0.14, 0.0), tile=T)
    sbox(g, -2.0, 2.0, 0.95, 3.0, -0.7, 0.7, new_col, tile=T)
    joints(g, rng, 0.0, 0.0, 2.0, 0.7, 1.07, 2.86, new_col, faces="ns")
    sbox(g, -2.0, 2.0, 3.0, 3.35, -0.7, -0.25, new_col, tile=T)       # breastwork
    merlons_x(g, -2.0, 2.0, -0.7, -0.25, 3.35, 3.85, new_col, rng=rng, tile=T)
    sbox(g, -2.0, 2.0, 3.0, 3.18, 0.5, 0.7, new_col, tile=T)          # inner kerb
    sbox(g, -2.0, 2.0, 2.86, 3.0, -0.78, -0.7, new_col, tile=1.0)     # string course at the walk
    putlogs_x(g, -2.0, 2.0, -0.705, (1.6, 2.4))
    for x in (-1.0, 1.0):  # drain spouts through the breastwork, stains down the outer face
        spout(g, "z", -0.7, -1, x, 3.06, new_col, reach=0.5, streak_len=1.7)
    for x in (-1.6, 0.3):
        streak(g, "z", -0.7, -1, x + rng.uniform(-0.15, 0.15), 2.84, rng.uniform(0.6, 1.2), new_col,
               width=rng.uniform(0.3, 0.5), dark=0.7)
    face_stones(g, rng, "z", -0.7, -1, -1.9, 1.9, 1.1, 2.8, new_col, 6, holes=0.0)
    face_stones(g, rng, "z", 0.7, 1, -1.9, 1.9, 1.1, 2.8, new_col, 4, holes=0.0)
    return b


def ck_curtain_corner(rng):
    """Corner block 1.4 x 1.4 where two curtains meet at a right angle; its outer faces (-Z and -X)
    run flush with the curtains' outer faces: wall-walk 3.0, breastwork + merlons on both outer
    sides, the battered foot wrapping the corner."""
    b = Builder()
    g = G(b)
    sbox(g, -0.95, 0.7, -0.3, 0.7, -0.95, 0.7, new_col)
    sbox(g, -0.7, 0.7, 0.7, 3.0, -0.7, 0.7, new_col)
    sbox(g, -0.7, 0.7, 3.0, 3.35, -0.7, -0.25, new_col)
    sbox(g, -0.7, -0.25, 3.0, 3.35, -0.25, 0.7, new_col)
    sbox(g, -0.7, 0.2, 3.35, 3.85, -0.7, -0.25, new_col)     # corner merlon (L-shaped)
    sbox(g, -0.7, -0.25, 3.35, 3.85, -0.25, 0.2, new_col)
    sbox(g, -0.74, 0.24, 3.85, 3.93, -0.74, -0.21, new_col, tile=1.2)    # coping
    sbox(g, -0.74, -0.21, 3.85, 3.93, -0.21, 0.24, new_col, tile=1.2)
    return b


def ck_corner_tower(rng):
    """Corner tower 4.6 x 4.6 centred on the meeting point of two wall lines; the curtains abut its
    +X and +Z faces (their outer faces -Z / -X run 1.6 inside the tower's), so it projects out of
    both walls. Sloped batter, coursed ashlar with quoins, slits at two levels on the outer faces,
    doors onto both wall-walks (3.0), a corbelled stone parapet at 6.2 carrying a TIMBER HOARDING
    gallery: beams projecting through put-log holes, plank walls with drop slots, and a steep
    weathered-plank pyramid roof to ~9.4."""
    b = Builder()
    g = G(b)
    H = 2.3
    batter(g, -H, H, -H, H, -0.3, 1.3, new_col, out=(0.5, 0.25, 0.25, 0.5))
    sbox(g, -H, H, 1.3, 6.2, -H, H, new_col)
    quoins(g, rng, 0.0, 0.0, H, H, 1.42, 6.2, new_col, h=0.38, long=0.66, short=0.38)
    joints(g, rng, 0.0, 0.0, H, H, 1.42, 6.1, new_col, course=0.46, unit=(0.6, 1.05))
    sbox(g, -H - 0.07, H + 0.07, 3.0, 3.16, -H - 0.07, H + 0.07, new_col, tile=1.0)
    for f, axis, sgn in (("s", "z", -1), ("w", "x", -1)):
        face_stones(g, rng, axis, sgn * H, sgn, -H + 0.5, H - 0.5, 1.5, 6.0, new_col, 7, holes=0.0)
        for y in (2.1, 4.4):
            for u in (-0.9, 0.9):
                c = V(u, y, -H - 0.005) if axis == "z" else V(-H - 0.005, y, u)
                dark_patch(g, c, (0.13, 0.85, 0.06) if axis == "z" else (0.06, 0.85, 0.13))
        streak(g, axis, sgn * H, sgn, rng.uniform(-1.2, 1.2), 6.1, 2.8, new_col, width=0.5, dark=0.6)
        streak(g, axis, sgn * H, sgn, rng.uniform(-1.2, 1.2), 6.1, 1.6, new_col, width=0.3, dark=0.65)
    # Doors onto the two wall-walks (+X and +Z faces, on the wall lines where the walks arrive).
    dark_patch(g, V(H + 0.005, 3.16 + 0.85, 0.12), (0.06, 1.7, 0.8))
    arch_z(g, rng, 0.12, 3.16 + 1.25, 0.4, H - 0.06, H + 0.08, new_col, n=5, block=0.18)
    dark_patch(g, V(0.12, 3.16 + 0.85, H + 0.005), (0.8, 1.7, 0.06))
    arch_x(g, rng, 0.12, 3.16 + 1.25, 0.4, H - 0.06, H + 0.08, new_col, n=5, block=0.18)
    # Corbel table + low stone parapet (the hoarding sits on it).
    for side in range(4):
        for k in range(6):
            t = -H + 0.35 + k * (2 * H - 0.7) / 5
            if side == 0:
                sbox(g, t - 0.12, t + 0.12, 5.95, 6.2, -H - 0.22, -H, new_col, tile=1.2)
            elif side == 1:
                sbox(g, t - 0.12, t + 0.12, 5.95, 6.2, H, H + 0.22, new_col, tile=1.2)
            elif side == 2:
                sbox(g, -H - 0.22, -H, 5.95, 6.2, t - 0.12, t + 0.12, new_col, tile=1.2)
            else:
                sbox(g, H, H + 0.22, 5.95, 6.2, t - 0.12, t + 0.12, new_col, tile=1.2)
    O = H + 0.22
    sbox(g, -O, O, 6.2, 6.45, -O, O, new_col)
    # Hoarding: beams cantilevered 0.75 out on every side, a plank floor ring, posts, plank walls
    # with drop slots, a wall plate; weathered (not fresh) timber.
    HT = mix(OLD_TIMBER, TIMBER, 0.45)
    E = O + 0.75
    for k in range(5):
        t = -O + 0.25 + k * (2 * O - 0.5) / 4
        for a, b2 in (((t, -E), (t, -O + 0.6)), ((t, O - 0.6), (t, E))):
            beam(g, [V(a[0], 6.52, a[1]), V(b2[0], 6.52, b2[1])], 0.16, 0.16, mat=M_PLANK, col=HT, rng=rng)
            beam(g, [V(a[1], 6.52, a[0]), V(b2[1], 6.52, b2[0])], 0.16, 0.16, mat=M_PLANK, col=HT, rng=rng)
        putlogs_x(g, -H, H, -H - 0.006, (5.75,), step=10.0, phase=H + t)
    for sgn in (-1, 1):
        board(g, V(0, 6.62, sgn * (E - 0.36)), V(1, 0, 0), V(0, 1, 0), 2 * E, 0.7, 0.05, mat=M_PLANK, col=HT, rng=rng)
        board(g, V(sgn * (E - 0.36), 6.625, 0), V(0, 0, 1), V(0, 1, 0), 2 * E - 1.4, 0.7, 0.05, mat=M_PLANK, col=HT,
              rng=rng)
    wall_top = 7.75
    for sx in (-1, 1):
        for sz in (-1, 1):
            beam(g, [V(sx * (E - 0.06), 6.6, sz * (E - 0.06)), V(sx * (E - 0.06), wall_top, sz * (E - 0.06))], 0.14, 0.14,
                 mat=M_PLANK, col=HT, rng=rng)
    for side in range(4):
        a = side * math.pi / 2
        d, nrm = V(-math.sin(a), 0, math.cos(a)), V(math.cos(a), 0, math.sin(a))
        n = 9
        for k in range(n):
            u = -E + 0.12 + (k + 0.5) * (2 * E - 0.24) / n
            if k in (2, 6):
                continue  # drop slots / loopholes between boards
            board(g, nrm * (E - 0.03) + d * u + V(0, (6.65 + wall_top) / 2, 0), V(0, 1, 0), nrm, wall_top - 6.65,
                  (2 * E - 0.24) / n * 0.96, 0.05, mat=M_PLANK, col=mix(HT, OLD_TIMBER, rng.uniform(0, 0.5)), rng=rng)
        beam(g, [nrm * (E - 0.03) + d * (-E) + V(0, wall_top, 0), nrm * (E - 0.03) + d * E + V(0, wall_top, 0)], 0.14,
             0.14, mat=M_PLANK, col=HT, rng=rng)
    # Steep pyramid roof of weathered planks (two shells + eave band), a finial post.
    ry, eo = 9.4, E + 0.35
    for off, up in ((0.1, True), (0.0, False)):
        apex = V(0, ry + off, 0)
        cs = [V(-eo, wall_top - 0.25 + off, -eo), V(eo, wall_top - 0.25 + off, -eo), V(eo, wall_top - 0.25 + off, eo),
              V(-eo, wall_top - 0.25 + off, eo)]
        for i in range(4):
            a, c = cs[i], cs[(i + 1) % 4]
            tri = [a, apex, c] if ((apex - a).cross(c - a).y > 0) == up else [a, c, apex]
            flat(g, tri, M_PLANK, scale(OLD_TIMBER, 0.95 if up else 0.5), tile=0.9)
    for i in range(4):
        a, c = cs[i], cs[(i + 1) % 4]
        q = [a, c, c + V(0, 0.1, 0), a + V(0, 0.1, 0)]
        mid = (a + c) / 2
        if (q[1] - q[0]).cross(q[3] - q[0]).dot(V(mid.x, 0, mid.z)) < 0:
            q = q[::-1]
        flat(g, q, M_PLANK, scale(OLD_TIMBER, 0.6), tile=0.6)
    pole(g, (0, ry - 0.1, 0), (0, ry + 0.55, 0), 0.07, 0.05, rng, mat=M_PLANK, col=OLD_TIMBER, sides=6, segs=1)
    return b


def ck_stone_tower(rng):
    """Square stone tower 4.2 x 4.2 (projects outward, -Z): battered base, string course, arrow
    slits, a walk at 5.4 behind a corbelled parapet with merlons to 6.3, a door at wall-walk level
    on +Z and a ground door."""
    b = Builder()
    g = G(b)
    H = 2.1
    batter(g, -H, H, -H, H, -0.3, 1.1, new_col, out=(0.45, 0.45, 0.45, 0.45))
    sbox(g, -H, H, 1.1, 5.2, -H, H, new_col)
    quoins(g, rng, 0.0, 0.0, H, H, 1.2, 5.2, new_col)
    joints(g, rng, 0.0, 0.0, H, H, 0.9, 4.95, new_col)
    for sgn in (-1, 1):
        face_stones(g, rng, "z", sgn * H, sgn, -H + 0.4, H - 0.4, 1.0, 5.0, new_col, 6, holes=0.0)
        face_stones(g, rng, "x", sgn * H, sgn, -H + 0.4, H - 0.4, 1.0, 5.0, new_col, 6, holes=0.0)
    sbox(g, -H - 0.08, H + 0.08, 3.0, 3.18, -H - 0.08, H + 0.08, new_col, tile=1.2)
    # Corbels, then the parapet (overhanging 0.2) with merlons.
    for side in range(4):
        for k in range(5):
            t = -H + 0.42 + k * (2 * H - 0.84) / 4
            if side == 0:
                sbox(g, t - 0.12, t + 0.12, 4.95, 5.2, -H - 0.2, -H, new_col)
            elif side == 1:
                sbox(g, t - 0.12, t + 0.12, 4.95, 5.2, H, H + 0.2, new_col)
            elif side == 2:
                sbox(g, -H - 0.2, -H, 4.95, 5.2, t - 0.12, t + 0.12, new_col)
            else:
                sbox(g, H, H + 0.2, 4.95, 5.2, t - 0.12, t + 0.12, new_col)
    O = H + 0.2
    sbox(g, -O, O, 5.2, 5.4, -O, O, new_col)
    for (x0, x1, z0, z1) in ((-O, O, -O, -O + 0.4), (-O, O, O - 0.4, O), (-O, -O + 0.4, -O + 0.4, O - 0.4),
                             (O - 0.4, O, -O + 0.4, O - 0.4)):
        sbox(g, x0, x1, 5.4, 5.8, z0, z1, new_col)
    merlons_x(g, -O, O, -O, -O + 0.4, 5.8, 6.3, new_col, phase=0.0, rng=rng)
    merlons_x(g, -O, O, O - 0.4, O, 5.8, 6.3, new_col, phase=0.0, rng=rng)
    merlons_z(g, -O + 0.4, O - 0.4, -O, -O + 0.4, 5.8, 6.3, new_col, phase=0.0, rng=rng)
    merlons_z(g, -O + 0.4, O - 0.4, O - 0.4, O, 5.8, 6.3, new_col, phase=0.0, rng=rng)
    spout(g, "z", -O, -1, 1.2, 5.3, new_col, streak_len=2.4, wall=-H)
    spout(g, "x", -O, -1, -1.0, 5.3, new_col, streak_len=2.0, wall=-H)
    spout(g, "x", O, 1, 0.9, 5.3, new_col, streak_len=2.6, wall=H)
    putlogs_x(g, -H, H, -H - 0.005, (2.6, 4.4), step=1.4, phase=0.7)
    for y in (1.8, 3.9):
        for c, s in ((V(0, y, -H - 0.005), (0.14, 0.8, 0.06)), (V(-H - 0.005, y, 0), (0.06, 0.8, 0.14)),
                     (V(H + 0.005, y, 0), (0.06, 0.8, 0.14))):
            dark_patch(g, c, s)
    for y0, h in ((0.9, 1.9), (3.18, 1.7)):
        dark_patch(g, V(0, y0 + h / 2, H + 0.005), (0.9, h, 0.06))
        arch_x(g, rng, 0.0, y0 + h - 0.45, 0.45, H - 0.05, H + 0.1, new_col, n=5, block=0.2)
    return b


def ck_gatehouse(rng):
    """Gatehouse 6.4 (X) x 4.6 (Z) on the wall line, two turrets projecting outward (-Z, to z -3.5).
    The passage runs along Z: 2.8 wide x 2.7 high under a segmental arch (springing 2.0); the
    portcullis half lowered in its slot behind the outer arch; the body to 5.6 with merlons over the
    gate to 6.6, the turrets to 6.9; plank doors stand open inward on the courtyard side."""
    b = Builder()
    g = G(b)
    X, Z = 3.2, 2.3
    ow = 1.4  # half opening
    spring, crown = 2.0, 2.7
    R = (ow * ow + (crown - spring) ** 2) / (2 * (crown - spring))
    cy = crown - R
    t0 = math.atan2(spring - cy, ow)
    for s in (-1, 1):
        x0, x1 = (ow, X) if s > 0 else (-X, -ow)
        sbox(g, x0 - (0.25 if s < 0 else 0.0), x1 + (0.25 if s > 0 else 0.0), -0.3, 0.8, -Z - 0.25, Z, new_col)
        sbox(g, x0, x1, 0.8, 5.6, -Z, Z, new_col)
        # haunches between the springing and the crown (behind the voussoirs, stepped inside)
        hx0, hx1 = sorted((s * 0.8, s * ow))
        sbox(g, hx0, hx1, 2.3, crown + 0.02, -Z, Z, new_col)
        hx0, hx1 = sorted((s * 1.15, s * ow))
        sbox(g, hx0, hx1, spring, 2.3, -Z, Z, new_col)
    sbox(g, -ow, ow, crown, 5.6, -Z, Z, new_col)  # over the passage
    for f0, f1 in ((-Z - 0.04, -Z + 0.5), (Z - 0.5, Z + 0.04)):
        arch_x(g, rng, 0.0, cy, R, f0, f1, new_col, n=9, block=0.26, t0=t0)
    lbox(g, V(0, crown - 0.01, 0), (2 * ow - 0.2, 0.03, 2 * Z - 1.1), Q0, M_STONE, scale(NEW_FOOT, 0.4), tile=1.6)
    # Projecting outer turrets with slits, a parapet and merlons.
    for s in (-1, 1):
        x0, x1 = (ow + 0.2, X + 0.6) if s > 0 else (-X - 0.6, -ow - 0.2)
        sbox(g, x0 - 0.2, x1 + 0.2, -0.3, 0.9, -Z - 1.4, -Z + 0.2, new_col)
        sbox(g, x0, x1, 0.9, 6.0, -Z - 1.2, -Z + 0.2, new_col)
        quoins(g, rng, (x0 + x1) / 2, -Z - 0.5, (x1 - x0) / 2, 0.7, 0.9, 6.0, new_col)
        joints(g, rng, (x0 + x1) / 2, -Z - 0.5, (x1 - x0) / 2, 0.7, 0.9, 6.0, new_col, faces="swe")
        sbox(g, x0, x1, 6.0, 6.4, -Z - 1.2, -Z - 0.85, new_col)
        sbox(g, (x0 if s < 0 else x1 - 0.35), (x0 + 0.35 if s < 0 else x1), 6.0, 6.4, -Z - 0.85, -Z + 0.2, new_col)
        merlons_x(g, x0, x1, -Z - 1.2, -Z - 0.85, 6.4, 6.9, new_col, phase=0.0, rng=rng)
        streak(g, "z", -Z - 1.2, -1, (x0 + x1) / 2 + 0.5, 6.0, 2.2, new_col, width=0.4, dark=0.6)
        for y in (2.0, 4.0):
            dark_patch(g, V((x0 + x1) / 2, y, -Z - 1.205), (0.14, 0.75, 0.06))
            dark_patch(g, V(x1 + 0.005 if s > 0 else x0 - 0.005, y + 0.6, -Z - 0.5), (0.06, 0.75, 0.14))
    # Parapet over the gate passage on the outer side.
    sbox(g, -ow - 0.2, ow + 0.2, 5.6, 6.05, -Z, -Z + 0.45, new_col)
    merlons_x(g, -ow - 0.2, ow + 0.2, -Z, -Z + 0.45, 6.05, 6.6, new_col, phase=0.0, rng=rng)
    spout(g, "z", -Z, -1, -0.8, 5.65, new_col, streak_len=1.4)
    # Portcullis: oak grid with iron-shod points, half lowered (points at 1.08) in its slot.
    zp = -Z + 0.62
    for k in range(7):
        x = -ow + 0.2 + k * (2 * ow - 0.4) / 6
        beam(g, [V(x, 1.3, zp), V(x, crown + 0.1, zp)], 0.11, 0.11, mat=M_PLANK, col=OLD_TIMBER, rng=rng)
        frustum(g, 0.005, 0.05, 1.08, 0.22, 4, M_IRON, IRON, tile=0.3, centre=(x, 0, zp))
    for y in (1.6, 2.2):
        beam(g, [V(-ow + 0.05, y, zp + 0.06), V(ow - 0.05, y, zp + 0.06)], 0.1, 0.1, mat=M_PLANK, col=OLD_TIMBER, rng=rng)
    # Inner doors, open inward against the passage walls.
    for s in (-1, 1):
        for k in range(4):
            board(g, V(s * (ow - 0.08), 1.25, Z - 0.42 - k * 0.32), V(0, 1, 0), V(1, 0, 0), 2.5, 0.31, 0.08,
                  mat=M_PLANK, col=mix(TIMBER, OLD_TIMBER, rng.uniform(0, 0.25)), rng=rng)
    putlogs_x(g, -ow - 0.2, ow + 0.2, -Z - 0.005, (3.6, 4.8), phase=0.3, step=0.75)
    return b


# ─────────────────────────────────────────────────────────────── 5. KEEP TIERS

def ck_keep_t1(rng):
    """Tier 1: the ruin shell taken back. The collapsed SE corner walled up in fresh timber framing
    and planks, a new thatched gable roof (ridge along X at 7.6) on fresh rafters and wall-plates,
    planked gable triangles above the broken stone gables, scaffolding on the south face."""
    b = Builder()
    g = G(b)
    X, Z, T = keep_shell(g, rng)
    for x in (1.6, 2.5, 3.4):
        beam(g, [V(x, -0.1, -Z + 0.45), V(x, 4.3, -Z + 0.45)], 0.2, 0.2, mat=M_PLANK, col=TIMBER, rng=rng)
    for z in (-1.4, -0.2, 1.0):
        beam(g, [V(X - 0.45, -0.1, z), V(X - 0.45, 4.3, z)], 0.2, 0.2, mat=M_PLANK, col=TIMBER, rng=rng)
    for y in (1.4, 2.9, 4.3):
        beam(g, [V(0.9, y, -Z + 0.45), V(X - 0.45, y, -Z + 0.45), V(X - 0.45, y, Z - 0.6)], 0.18, 0.18,
             mat=M_PLANK, col=TIMBER, rng=rng)
    for k in range(9):
        board(g, V(1.0 + k * 0.32, 2.15, -Z + 0.36), V(0, 1, 0), V(0, 0, -1), 4.3, 0.31, 0.06, mat=M_PLANK,
              col=mix(TIMBER, (0.85, 0.75, 0.6), rng.uniform(0, 0.4)), rng=rng)
    for k in range(13):
        board(g, V(X - 0.36, 2.15, -Z + 0.6 + k * 0.32), V(0, 1, 0), V(1, 0, 0), 4.3, 0.31, 0.06, mat=M_PLANK,
              col=mix(TIMBER, (0.85, 0.75, 0.6), rng.uniform(0, 0.4)), rng=rng)
    ey, ry = 4.4, 7.6
    for s in (-1, 1):
        beam(g, [V(-X + 0.4, ey, s * (Z - 0.45)), V(X - 0.2, ey, s * (Z - 0.45))], 0.22, 0.2, mat=M_PLANK, col=TIMBER,
             rng=rng)
    for k in range(8):
        x = -X + 0.6 + k * (2 * X - 0.9) / 7
        beam(g, [V(x, ey, -Z - 0.3), V(x, ry, 0.0), V(x, ey, Z + 0.3)], 0.14, 0.16, mat=M_PLANK, col=TIMBER, rng=rng)
    beam(g, [V(-X + 0.3, ry, 0.0), V(X, ry, 0.0)], 0.2, 0.2, mat=M_PLANK, col=TIMBER, rng=rng)
    slope = math.atan2(ry - ey, Z + 0.3)
    run = math.hypot(ry - ey, Z + 0.3)
    for s in (-1, 1):
        c = V(0.1, (ey + ry) / 2 + 0.2, s * (Z + 0.3) / 2)
        lbox(g, c, (2 * X + 0.7, 0.35, run + 0.4), quat_x(s * slope), M_THATCH, [scale(THATCH, 0.8), None, THATCH],
             tile=1.4, grain=2)
    # Planked gable triangles (both faces) at each end, above the stone.
    for x in (-X + 0.45, X - 0.3):
        tri = [V(x, ey - 0.1, -Z - 0.1), V(x, ry - 0.1, 0.0), V(x, ey - 0.1, Z + 0.1)]
        for t in (tri, tri[::-1]):
            flat(g, t, M_PLANK, mix(TIMBER, OLD_TIMBER, 0.2), tile=1.3)
    # Scaffolding on the south face: standards, ledgers, putlogs into the wall, plank lifts, a brace.
    for x in (-3.4, -1.6, 0.2):
        pole(g, (x, -0.3, -Z - 1.0), (x, 5.4, -Z - 1.0), 0.07, 0.06, rng, mat=M_BARK, col=LOG, sides=6)
    for y in (2.0, 3.8):
        beam(g, [V(-3.6, y, -Z - 1.0), V(0.4, y, -Z - 1.0)], 0.08, 0.08, mat=M_PLANK, col=TIMBER, rng=rng)
        for x in (-3.0, -1.0):
            beam(g, [V(x, y + 0.08, -Z - 1.1), V(x, y + 0.08, -Z + 0.1)], 0.08, 0.08, mat=M_PLANK, col=TIMBER, rng=rng)
        for k in range(2):
            board(g, V(-1.6, y + 0.16, -Z - 0.85 + k * 0.33), V(1, 0, 0), V(0, 1, 0), 3.8, 0.31, 0.05, mat=M_PLANK,
                  col=TIMBER, rng=rng)
        for x in (-3.4, -1.6):
            lashing(g, V(x, y, -Z - 1.0), (0, 1, 0), 0.09, rng, turns=2)
    beam(g, [V(-3.4, 0.3, -Z - 1.0), V(0.2, 3.6, -Z - 1.0)], 0.07, 0.07, mat=M_PLANK, col=TIMBER, rng=rng)
    return b


def ck_keep_t2(rng):
    """Tier 2: the stone donjon (7 x 6, parapet walk 8.6, merlons to 9.4) on a battered base,
    corbelled parapet, paired round-headed windows, a round stair turret on the NE corner under a
    conical grey cap (to ~11.1), a first-floor door reached by a timber stair on the courtyard side."""
    b = Builder()
    g = G(b)
    X, Z = 3.5, 3.0
    sbox(g, -X - 0.35, X + 0.35, -0.3, 1.1, -Z - 0.35, Z + 0.35, new_col)
    sbox(g, -X, X, 1.1, 8.3, -Z, Z, new_col)
    quoins(g, rng, 0.0, 0.0, X, Z, 1.1, 8.05, new_col)
    joints(g, rng, 0.0, 0.0, X, Z, 1.1, 8.05, new_col, course=0.5)
    for sgn in (-1, 1):
        face_stones(g, rng, "z", sgn * Z, sgn, -X + 0.4, X - 0.4, 1.2, 8.0, new_col, 10, holes=0.0)
        face_stones(g, rng, "x", sgn * X, sgn, -Z + 0.4, Z - 0.4, 1.2, 8.0, new_col, 8, holes=0.0)
    for y in (3.4, 6.0):
        sbox(g, -X - 0.08, X + 0.08, y, y + 0.18, -Z - 0.08, Z + 0.08, new_col, tile=1.2)
    O = 0.22
    for side in range(4):
        n = 7 if side < 2 else 6
        for k in range(n):
            if side < 2:
                t = -X + 0.4 + k * (2 * X - 0.8) / (n - 1)
                zz = (-Z - O, -Z) if side == 0 else (Z, Z + O)
                sbox(g, t - 0.13, t + 0.13, 8.05, 8.3, zz[0], zz[1], new_col)
            else:
                t = -Z + 0.4 + k * (2 * Z - 0.8) / (n - 1)
                xx = (-X - O, -X) if side == 2 else (X, X + O)
                sbox(g, xx[0], xx[1], 8.05, 8.3, t - 0.13, t + 0.13, new_col)
    ex, ez = X + O, Z + O
    sbox(g, -ex, ex, 8.3, 8.6, -ez, ez, new_col)
    for (x0, x1, z0, z1) in ((-ex, ex, -ez, -ez + 0.4), (-ex, ex, ez - 0.4, ez), (-ex, -ex + 0.4, -ez + 0.4, ez - 0.4),
                             (ex - 0.4, ex, -ez + 0.4, ez - 0.4)):
        sbox(g, x0, x1, 8.6, 8.95, z0, z1, new_col)
    merlons_x(g, -ex, ex, -ez, -ez + 0.4, 8.95, 9.4, new_col, phase=0.0, rng=rng)
    merlons_x(g, -ex, ex, ez - 0.4, ez, 8.95, 9.4, new_col, phase=0.0, rng=rng)
    merlons_z(g, -ez + 0.4, ez - 0.4, -ex, -ex + 0.4, 8.95, 9.4, new_col, phase=0.0, rng=rng)
    merlons_z(g, -ez + 0.4, ez - 0.4, ex - 0.4, ex, 8.95, 9.4, new_col, phase=0.0, rng=rng)
    tc = (X - 0.2, Z - 0.2)
    frustum(g, 1.25, 1.05, -0.3, 10.2, 14, M_MASON, None, tile=1.6, centre=(tc[0], 0, tc[1]),
            col_fn=lambda t: new_col(-0.3 + 10.2 * t), segs=2)
    frustum(g, 1.3, 0.02, 9.85, 1.3, 14, M_ROCK, (0.52, 0.54, 0.58), tile=1.0, centre=(tc[0], 0, tc[1]))
    for y in (2.2, 4.6, 7.0):
        a = 0.4 + y * 0.12
        dark_patch(g, V(tc[0] + math.cos(a) * 1.16, y, tc[1] + math.sin(a) * 1.16), (0.12, 0.6, 0.12))
    for y in (4.4, 6.8):
        for x in (-1.6, 1.2):
            for dx in (-0.22, 0.22):
                dark_patch(g, V(x + dx, y, -Z - 0.005), (0.3, 1.0, 0.06))
            arch_x(g, rng, x, y + 0.35, 0.42, -Z - 0.1, -Z + 0.1, new_col, n=5, block=0.18)
        for z in (-1.2, 1.0):
            dark_patch(g, V(-X - 0.005, y, z), (0.06, 1.0, 0.5))
            dark_patch(g, V(X + 0.005, y, z - 0.6), (0.06, 1.0, 0.5))
    # First-floor door (x 0.9) on the courtyard face + a timber stair rising from the west.
    landing = 3.0
    dark_patch(g, V(0.9, landing + 1.0, Z + 0.005), (1.0, 2.0, 0.06))
    arch_x(g, rng, 0.9, landing + 1.5, 0.5, Z - 0.1, Z + 0.12, new_col, n=5, block=0.2)
    for x in (0.2, 1.6):
        beam(g, [V(x, -0.1, Z + 1.55), V(x, landing - 0.1, Z + 1.55)], 0.2, 0.2, mat=M_PLANK, col=TIMBER, rng=rng)
    beam(g, [V(0.05, landing - 0.12, Z + 1.55), V(1.75, landing - 0.12, Z + 1.55)], 0.16, 0.18, mat=M_PLANK, col=TIMBER,
         rng=rng)
    for k in range(5):
        board(g, V(0.9, landing, Z + 0.22 + k * 0.33), V(1, 0, 0), V(0, 1, 0), 1.75, 0.32, 0.06, mat=M_PLANK, col=TIMBER,
              rng=rng)
    sx0, sx1 = -2.6, 0.05
    for s in (-1, 1):
        beam(g, [V(sx0, 0.0, Z + 1.0 + s * 0.45), V(sx1, landing, Z + 1.0 + s * 0.45)], 0.22, 0.08, mat=M_PLANK,
             col=TIMBER, rng=rng)
    n = 9
    for k in range(n):
        f = (k + 0.5) / n
        board(g, V(sx0 + (sx1 - sx0) * f, landing * f + 0.05, Z + 1.0), V(0, 0, 1), V(0, 1, 0), 1.0, 0.3, 0.05,
              mat=M_PLANK, col=TIMBER, rng=rng)
    railing(g, rng, [V(sx0, 0.0, Z + 1.5), V(sx1, landing, Z + 1.5), V(1.7, landing, Z + 1.5)], h=0.9)
    return b


MODELS = {
    "ck_bell_tower": ck_bell_tower,
    "ck_ruin_keep": ck_ruin_keep,
    "ck_ruin_wall_a": ck_ruin_wall_a,
    "ck_ruin_wall_b": ck_ruin_wall_b,
    "ck_rubble": ck_rubble,
    "ck_palisade": ck_palisade,
    "ck_timber_gate": ck_timber_gate,
    "ck_watchtower": ck_watchtower,
    "ck_curtain": ck_curtain,
    "ck_curtain_corner": ck_curtain_corner,
    "ck_stone_tower": ck_stone_tower,
    "ck_corner_tower": ck_corner_tower,
    "ck_gatehouse": ck_gatehouse,
    "ck_keep_t1": ck_keep_t1,
    "ck_keep_t2": ck_keep_t2,
}

if __name__ == "__main__":
    clear_scene()
    objs = []
    report = {}
    for i, (name, fn) in enumerate(MODELS.items()):
        b = fn(np.random.default_rng(7300 + i))
        report[name] = bounds(b)
        objs.append(b.build(name, MATS))
    export_glb(OUT / "castle_kit.glb", objs)
    total = 0
    for k, v in report.items():
        total += v["tris"]
        print(f"{k}: tris {v['tris']}  x {v['x']}  y {v['y']}  z {v['z']}")
    print(f"TOTAL tris {total}")
    print("CASTLE_KIT_DONE")
