"""Environmental-storytelling set-pieces for the cold biomes -> stories_cold.glb (src/stories_cold.rs).

No text, no interaction: each scene explains itself.
SNOW:  story_lost_camp      - an expedition that never came back: collapsed tent half under a drift,
                              a sled with lashed crates, a cold fire ring, skis + poles still stuck
                              upright, a pickaxe against a crate.
       story_buried_cabin   - an avalanche took the cabin: a snow mound with the caved roof and
                              beams jutting out of it, the stone chimney still standing.
       story_frozen_memorial - a battle no one came back from: a cairn topped with a helmet, a tattered
                              banner on a leaning pole, broken shields and spears in the snow.
ROCKY: story_mine_head      - a timber headframe over an open shaft, a tipped ore cart at the end of
                              a short rail run, spilled ore and a lantern on a post.
       story_rockfall_wagon - a rockfall caught a wagon on the track: boulders on the crushed bed,
                              a splintered wheel, spilled sacks.
       story_quarry         - a half-cut monolith in a small quarry, wedges still in the cut, a blank
                              on log rollers, the masons' tools dropped where they stood.

Real scale (hero ~1.8u). Authored in game coordinates through geo.py like wayside_models.py, whose
primitives it reuses. Ground-contact parts run below y=0 so a piece on a slightly uneven spot never
floats. Materials by name: the s_* PBR sets + bark_oak, and `s_snow` (untextured, vertex colour =
the snow's tint; the game binds a matte snow material to it).

    blender -b --factory-startup --python tools/blender_forest/stories_cold.py
"""
import json
import math
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402
from common import OUT, clear_scene, export_glb  # noqa: E402
from geo import G, frustum, quat_x, quat_y, quat_z, sheet  # noqa: E402
from meshkit import Builder  # noqa: E402
import wayside_models as W  # noqa: E402
from wayside_models import (M_BARK, M_PLANK, M_STONE, M_HIDE, M_THATCH, M_CLOTH, M_IRON, M_ROCK, M_EARTH,  # noqa: E402
                            V, beam, board, bounds, charred, lashing, lbox, mix, mound, pole, rock_col, scale,
                            slab, smooth_mesh, smoothstep, stone, tube, Noise)

M_SNOW = len(W.MATS)
MATS = W.MATS + ["s_snow"]

SNOW = (0.93, 0.95, 1.0)
WOOD = (0.82, 0.72, 0.6)
OLD_WOOD = (0.62, 0.6, 0.58)
IRON = (0.42, 0.4, 0.38)
CANVAS = (0.68, 0.65, 0.58)
ROCKY = (0.78, 0.74, 0.68)


# ─────────────────────────────────────────────────────────────── helpers
def snow_fn(nz, blue=0.04):
    """Tint over the s_snow scan (snow_02): near-white on the sky-facing crowns, a cool blue in the
    steep / undercut drift folds (sky light only, no sun), slightly greyed where it meets the ground."""
    def f(p, n):
        k = 0.95 + 0.05 * nz(p * 1.7)
        fold = 1.0 - smoothstep(0.05, 0.75, n.y)
        c = mix((SNOW[0] * (1 - blue), SNOW[1], SNOW[2]), (0.7, 0.8, 0.98), fold * 0.8)
        foot = 1.0 - 0.12 * (1.0 - smoothstep(-0.1, 0.12, p.y))
        return scale(c, k * foot)
    return f


def drift(g, centre, rx, rz, h, rng, power=0.9, skirt=0.18, rings=5, seg=18, edge=0.18):
    nz = Noise(rng, 4, 1.2)
    mound(g, centre, rx, rz, h, rng, mat=M_SNOW, col_fn=snow_fn(nz), tile=2.2, rings=rings, seg=seg, skirt=skirt,
          rough=0.1, edge=edge, power=power)


def snow_cap(g, centre, rx, rz, h, rng):
    """A pillow of settled snow on a flat top (crate lid, beam, shelf)."""
    nz = Noise(rng, 3, 3.0)
    mound(g, centre, rx, rz, h, rng, mat=M_SNOW, col_fn=snow_fn(nz), tile=1.6, rings=3, seg=12, skirt=0.0,
          rough=0.08, edge=0.1, power=0.6)


def dusted(base, amount=0.75):
    """Rock / stone tint with snow whitening the up-facing faces (s_rock is grey enough to read as frost)."""
    def f(p, n):
        return mix(base, (1.0, 1.0, 1.0), amount * smoothstep(0.35, 0.85, n.y))
    return f


def disc(g, centre, rot, r, h, sides, mat, col, tile=0.8, col_rim=None):
    """A short cylinder (shield board, wheel hub, barrel lid) along its local Y, oriented by `rot`."""
    c = Vector(centre)
    top, bot = [], []
    for s in range(sides):
        a = 2 * math.pi * s / sides
        top.append(c + rot @ V(math.cos(a) * r, h / 2, math.sin(a) * r))
        bot.append(c + rot @ V(math.cos(a) * r, -h / 2, math.sin(a) * r))
    up = rot @ V(0, 1, 0)
    for ring, nrm in ((top, up), (bot[::-1], -up)):
        ctr = sum(ring, Vector((0, 0, 0))) / sides
        for s in range(sides):
            tri = [ring[s], ring[(s + 1) % sides], ctr]
            if (tri[1] - tri[0]).cross(tri[2] - tri[0]).dot(nrm) < 0:
                tri = tri[::-1]
            uv = [((p - ctr).dot(rot @ V(1, 0, 0)) / tile + 0.5, (p - ctr).dot(rot @ V(0, 0, 1)) / tile + 0.5) for p in tri]
            g.poly(tri, uv, [nrm] * 3, [col] * 3, mat)
    rc = col_rim or scale(col, 0.85)
    for s in range(sides):
        k = (s + 1) % sides
        quad = [bot[s], bot[k], top[k], top[s]]
        out = (bot[s] + bot[k]) / 2 - c
        n = (quad[1] - quad[0]).cross(quad[3] - quad[0])
        if n.dot(out) < 0:
            quad = quad[::-1]
            n = -n
        uv = [(s / sides * 2 * math.pi * r / tile, 0), ((s + 1) / sides * 2 * math.pi * r / tile, 0),
              ((s + 1) / sides * 2 * math.pi * r / tile, h / tile), (s / sides * 2 * math.pi * r / tile, h / tile)]
        g.poly(quad, uv, [n.normalized()] * 4, [rc] * 4, mat)


def dome(g, centre, r, rot, mat, col_fn, tile=0.5, rings=5, seg=12, squash=1.0, flare=0.0):
    """Half sphere (helmet bowl, ore heap) on its local XZ plane; `flare` widens the rim."""
    c = Vector(centre)
    verts = [c + rot @ V(0, r * squash, 0)]
    for j in range(1, rings + 1):
        phi = (j / rings) * math.pi / 2
        rr = math.sin(phi) * r * (1 + flare * (j / rings) ** 4)
        y = math.cos(phi) * r * squash
        for i in range(seg):
            a = 2 * math.pi * i / seg
            verts.append(c + rot @ V(math.cos(a) * rr, y, math.sin(a) * rr))
    tris = [(0, 1 + (i + 1) % seg, 1 + i) for i in range(seg)]
    for j in range(rings - 1):
        r0, r1 = 1 + j * seg, 1 + (j + 1) * seg
        for i in range(seg):
            a, b = r0 + i, r0 + (i + 1) % seg
            tris += [(a, b, r1 + (i + 1) % seg), (a, r1 + (i + 1) % seg, r1 + i)]
    smooth_mesh(g, verts, tris, mat, col_fn, tile, inside=c + rot @ V(0, -r, 0))


def wheel(g, centre, axis_rot, r, rng, spokes=8, broken=0, col=WOOD):
    """A spoked cart wheel in its local XZ plane (axle along local Y). `broken` snaps that many spokes
    and opens the rim into a splintered gap."""
    c = Vector(centre)
    gap = int(rng.integers(spokes)) if broken else -1
    n = 14
    for part in range(2 if broken else 1):
        if broken:
            a0 = (gap + 0.75) / spokes * 2 * math.pi if part == 0 else 0
            span = 2 * math.pi - 1.5 / spokes * 2 * math.pi
            pts = [c + axis_rot @ V(math.cos(a0 + span * t / n) * r, 0, math.sin(a0 + span * t / n) * r) for t in range(n + 1)]
            if part == 1:
                break
            tube(g, pts, [0.045] * len(pts), 6, M_PLANK, col, tile=0.6)
        else:
            pts = [c + axis_rot @ V(math.cos(2 * math.pi * t / n) * r, 0, math.sin(2 * math.pi * t / n) * r) for t in range(n + 1)]
            tube(g, pts, [0.045] * len(pts), 6, M_PLANK, col, tile=0.6, cap=False)
    # Iron tyre (a thin ring just outside the felloe).
    if not broken:
        pts = [c + axis_rot @ V(math.cos(2 * math.pi * t / n) * (r + 0.035), 0, math.sin(2 * math.pi * t / n) * (r + 0.035))
               for t in range(n + 1)]
        tube(g, pts, [0.018] * len(pts), 4, M_IRON, IRON, tile=0.3, cap=False)
    disc(g, c, axis_rot, 0.09, 0.2, 10, M_PLANK, scale(col, 0.85), tile=0.4)
    for s in range(spokes):
        a = (s + 0.5) / spokes * 2 * math.pi
        d = axis_rot @ V(math.cos(a), 0, math.sin(a))
        if broken and s in (gap, (gap + 1) % spokes):
            beam(g, [c + d * 0.08, c + d * (r * rng.uniform(0.3, 0.55))], 0.04, 0.03, up=tuple(axis_rot @ V(0, 1, 0)),
                 mat=M_PLANK, col=col, rng=rng, jag=(0, 0.06))
            continue
        beam(g, [c + d * 0.08, c + d * (r - 0.02)], 0.04, 0.03, up=tuple(axis_rot @ V(0, 1, 0)), mat=M_PLANK, col=col,
             rng=rng)


def crate(g, centre, size, rot, rng, col=WOOD, lid=True):
    c = Vector(centre)
    lbox(g, c, size, rot, M_PLANK, [scale(col, 0.7), None, col], tile=1.0, grain=0)
    hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
    for sx in (-1, 1):
        for sz in (-1, 1):
            beam(g, [c + rot @ V(sx * (hx + 0.01), -hy, sz * (hz + 0.01)), c + rot @ V(sx * (hx + 0.01), hy, sz * (hz + 0.01))],
                 0.045, 0.045, up=tuple(rot @ V(0, 0, 1)), mat=M_PLANK, col=scale(col, 0.8), rng=rng)


def sack(g, centre, rot, s, rng, col=(0.7, 0.62, 0.48)):
    sc = Vector(centre)
    stone(g, tuple(sc), (0.2 * s, 0.17 * s, 0.15 * s), rng, mat=M_CLOTH, detail=1, rough=0.1, cuts=1, flat_y=0.7, rot=rot,
          col_fn=lambda p, n: mix(scale(col, 0.7), col, smoothstep(sc.y - 0.15, sc.y + 0.1, p.y)), tile=0.35)
    neck = sc + rot @ V(0, 0.15 * s, 0)
    tube(g, [neck, neck + rot @ V(0, 0.08 * s, 0), neck + rot @ V(0.04, 0.12 * s, 0)], [0.06 * s, 0.035 * s, 0.05 * s], 8,
         M_CLOTH, scale(col, 0.9), tile=0.3)


def pickaxe(g, grip, head, rng, col=WOOD):
    grip, head = Vector(grip), Vector(head)
    tube(g, [grip, head + (head - grip).normalized() * 0.05], [0.02, 0.022], 6, M_PLANK, col, tile=0.3)
    ax = (head - grip).normalized()
    side = ax.cross(V(0, 1, 0))
    if side.length < 1e-3:
        side = V(1, 0, 0)
    side.normalize()
    bend = ax.cross(side).normalized()
    for sgn in (1, -1):
        beam(g, [head, head + side * sgn * 0.18 + bend * 0.02, head + side * sgn * 0.3 - ax * 0.06], 0.035, 0.03,
             up=tuple(ax), mat=M_IRON, mode="bark", col=IRON, rng=rng, point=0.05 if sgn > 0 else 0.0, chamfer=0.2)


def spear(g, foot, tip, rng, broken=False, col=OLD_WOOD):
    foot, tip = Vector(foot), Vector(tip)
    d = (tip - foot).normalized()
    if broken:
        tip = foot + (tip - foot) * rng.uniform(0.45, 0.65)
        beam(g, [foot, tip], 0.03, 0.03, up=(0, 1, 0) if abs(d.y) < 0.9 else (1, 0, 0), mat=M_PLANK, col=col, rng=rng,
             jag=(0, 0.08), chamfer=0.4)
        return
    tube(g, [foot, tip - d * 0.22], [0.016, 0.014], 6, M_PLANK, col, tile=0.3)
    tube(g, [tip - d * 0.24, tip - d * 0.2, tip], [0.02, 0.028, 0.002], 6, M_IRON, IRON, tile=0.2)


def shield(g, centre, rot, r, rng, broken=False, paint=(0.45, 0.12, 0.1)):
    """A round board shield: planks (painted, flaking), iron boss and rim. `broken` = only part of it."""
    c = Vector(centre)
    planks = 5
    w = 2 * r / planks
    for k in range(planks):
        if broken and k >= 3:
            continue
        x = -r + w * (k + 0.5)
        half = math.sqrt(max(r * r - x * x, 0.01)) * (rng.uniform(0.55, 0.9) if broken and k == 2 else 1.0)
        tint = mix(paint, WOOD, 0.3 + 0.4 * rng.uniform())
        board(g, c + rot @ V(x, 0, 0), rot @ V(0, 0, 1), rot @ V(0, 1, 0), 2 * half, w * 0.96, 0.03, mat=M_PLANK,
              col=tint, rng=rng, jag=(0.04, 0.06) if broken else (0, 0))
    dome(g, c + rot @ V(0, 0.015, 0), 0.075, rot, M_IRON, lambda p, n: IRON, tile=0.2, rings=3, seg=10, squash=0.8)
    if not broken:
        n = 18
        pts = [c + rot @ V(math.cos(2 * math.pi * t / n) * r, 0, math.sin(2 * math.pi * t / n) * r) for t in range(n + 1)]
        tube(g, pts, [0.016] * len(pts), 4, M_IRON, IRON, tile=0.3, cap=False)


def rubble(g, rng, n, cx, cz, spread, rmin, rmax, col_fn, y=0.0, detail=0):
    for _ in range(n):
        r = rng.uniform(rmin, rmax)
        stone(g, (cx + rng.uniform(-spread, spread), y + r * 0.25, cz + rng.uniform(-spread, spread)),
              (r, r * rng.uniform(0.55, 0.8), r * rng.uniform(0.7, 1.0)), rng, detail=detail, col_fn=col_fn, tile=0.6)


# ─────────────────────────────────────────────────────────────── SNOW
def story_lost_camp(rng):
    """Footprint r <= 2.6; masses: the drift + tent (local -0.6, 0.2, 1.4 x 1.0), the sled (1.2, -0.6)."""
    b = Builder()
    g = G(b)
    # The drift that buried the tent's windward side.
    drift(g, (-0.9, 0.0, 0.3), 1.5, 1.05, 0.55, rng, power=1.2)
    drift(g, (0.6, 0.0, 0.9), 0.9, 0.6, 0.18, rng)
    # Collapsed A-frame tent: the front pole snapped, the canvas slumped over the ridge pole, its
    # windward half under the drift.
    tx, tz = -0.5, 0.2
    pole(g, V(tx + 0.0, -0.2, tz - 0.9), V(tx + 0.05, 1.05, tz - 0.9), 0.03, 0.026, rng, col=WOOD, sides=6)
    pole(g, V(tx, -0.2, tz + 0.95), V(tx + 0.1, 0.42, tz + 0.95), 0.03, 0.028, rng, col=WOOD, sides=6)
    beam(g, [V(tx + 0.1, 0.42, tz + 0.95), V(tx + 0.35, 0.12, tz + 1.25)], 0.05, 0.05, mat=M_PLANK, mode="bark",
         col=WOOD, rng=rng, jag=(0.06, 0.0))
    pole(g, V(tx + 0.05, 1.02, tz - 0.95), V(tx + 0.1, 0.4, tz + 1.0), 0.026, 0.026, rng, col=WOOD, sides=6)
    ni, nj = 9, 15
    for sx in (-1, 1):
        grid = []
        for i in range(ni):
            u = i / (ni - 1)
            row = []
            for j in range(nj):
                v = j / (nj - 1)
                z = tz - 1.0 + 2.05 * v
                ridge = 1.02 + (0.4 - 1.02) * v  # the ridge drops to the snapped front pole
                x = tx + sx * (0.04 + u * 0.75)
                y = ridge * (1 - u) - 0.05 * u
                sag = 0.18 * math.sin(math.pi * u) * (0.5 + 0.5 * math.sin(math.pi * v)) + 0.03 * math.sin(v * 11 + u * 5)
                y -= sag
                if sx > 0 and v > 0.6:
                    y -= 0.2 * (v - 0.6) * u  # flapping loose, lying flat on the snow
                    x += 0.25 * (v - 0.6) * u
                row.append((x, max(y, 0.02), z))
            grid.append(row)

        def col(u, v):
            k = 0.85 + 0.1 * math.sin(u * 7 + v * 11)
            return mix(scale(CANVAS, k), (0.55, 0.5, 0.42), smoothstep(0.7, 1.0, u) * 0.5)
        sheet(g, grid, M_CLOTH, col, tile=0.6, double=True)
        # Thickness at the edges: a rolled hem along the foot and the loose front edge.
        tube(g, [V(*grid[ni - 1][j]) + V(0, 0.03, 0) for j in range(nj)], [0.045] * nj, 6, M_CLOTH, scale(CANVAS, 0.7),
             tile=0.4)
        tube(g, [V(*grid[i][nj - 1]) for i in range(ni)], [0.03] * ni, 5, M_CLOTH, scale(CANVAS, 0.75), tile=0.4)
        # Snow settled on the canvas: the windward slope is mostly buried, the lee one dusted at the top.
        reach = 8 if sx < 0 else 4
        sgrid = [[(p[0] - sx * 0.01, p[1] + 0.07 * (1 - 0.4 * i / reach), p[2]) for p in grid[i]] for i in range(reach)]
        sheet(g, sgrid, M_SNOW, lambda u, v: mix((0.95, 0.96, 1.0), (0.8, 0.86, 1.0), 0.4 * u), tile=1.4)
    # Snow loaded on the windward slope, drifted over its foot.
    drift(g, (tx - 0.55, 0.15, tz - 0.1), 0.45, 0.9, 0.35, rng, skirt=0.25)
    snow_cap(g, (tx - 0.22, 0.55, tz - 0.4), 0.22, 0.45, 0.06, rng)
    # Sled: two runners curling up at the front, slats, two crates + a bundle lashed on, half tipped.
    sq = quat_y(0.35) @ quat_z(0.08)
    sc = V(1.15, 0.0, -0.75)
    for sz in (-0.32, 0.32):
        pts = [sc + sq @ V(-0.95, 0.06, sz), sc + sq @ V(0.6, 0.06, sz), sc + sq @ V(0.92, 0.12, sz), sc + sq @ V(1.08, 0.3, sz),
               sc + sq @ V(1.05, 0.42, sz)]
        beam(g, pts, 0.04, 0.06, up=tuple(sq @ V(0, 0, 1)), mat=M_PLANK, col=OLD_WOOD, rng=rng)
        for x in (-0.7, -0.1, 0.5):
            beam(g, [sc + sq @ V(x, 0.06, sz), sc + sq @ V(x, 0.22, sz)], 0.035, 0.035, mat=M_PLANK, col=OLD_WOOD, rng=rng)
    for k in range(6):
        x = -0.85 + k * 0.3
        board(g, sc + sq @ V(x, 0.24, 0), sq @ V(0, 0, 1), sq @ V(0, 1, 0), 0.78, 0.2, 0.03, mat=M_PLANK, col=OLD_WOOD,
              rng=rng)
    crate(g, sc + sq @ V(-0.45, 0.47, 0.0), (0.55, 0.42, 0.5), sq @ quat_y(0.08), rng)
    crate(g, sc + sq @ V(0.2, 0.43, 0.02), (0.45, 0.36, 0.44), sq @ quat_y(-0.1), rng, col=(0.75, 0.65, 0.52))
    snow_cap(g, sc + sq @ V(-0.45, 0.69, 0.0), 0.25, 0.22, 0.07, rng)
    snow_cap(g, sc + sq @ V(0.2, 0.62, 0.02), 0.2, 0.2, 0.06, rng)
    for x in (-0.45, 0.2):
        lashing(g, sc + sq @ V(x, 0.47, 0.0), tuple(sq @ V(1, 0, 0)), 0.3, rng, turns=2)
    tube(g, [sc + sq @ V(0.62, 0.3, -0.25), sc + sq @ V(0.66, 0.3, 0.0), sc + sq @ V(0.6, 0.3, 0.25)], [0.11, 0.12, 0.11], 8,
         M_HIDE, (0.55, 0.42, 0.32), tile=0.4)
    # Tow rope trailing into the snow.
    rp = sc + sq @ V(1.05, 0.42, 0.0)
    tube(g, [rp, rp + V(0.08, -0.3, -0.12), rp + V(-0.05, -0.42, -0.35), rp + V(-0.25, -0.4, -0.5)], [0.012] * 4, 4, M_CLOTH,
         W.ROPE, tile=0.3)
    drift(g, (sc.x - 0.3, 0.0, sc.z - 0.35), 0.8, 0.35, 0.16, rng)
    # Pickaxe leaning on the sled.
    pickaxe(g, sc + sq @ V(-1.2, 0.0, 0.42), sc + sq @ V(-0.9, 0.75, 0.42), rng)
    # Cold fire ring: blackened stones, charred logs, snow already drifting into it.
    fc = V(0.85, 0.0, 0.75)
    nzf = Noise(rng, 3, 3.0)
    mound(g, tuple(fc), 0.32, 0.32, 0.03, rng, col_fn=lambda p, n: mix((0.08, 0.08, 0.09), (0.32, 0.34, 0.38),
                                                                     0.5 + 0.5 * nzf(p * 6.0)), tile=0.6, rings=3, seg=14)
    for k in range(9):
        a = k / 9 * 2 * math.pi + rng.uniform(-0.15, 0.15)
        r = rng.uniform(0.07, 0.1)
        stone(g, (fc.x + math.cos(a) * 0.4, 0.0, fc.z + math.sin(a) * 0.4), (r, r * 0.7, r * 0.85), rng, detail=1,
              col_fn=dusted((0.5, 0.48, 0.46), 0.9), tile=0.5)
    for k in range(3):
        a = k / 3 * math.pi + 0.3
        d = V(math.cos(a), 0, math.sin(a))
        tube(g, [fc + d * -0.28 + V(0, 0.04, 0), fc + V(0, 0.07, 0), fc + d * 0.26 + V(0, 0.04, 0)], [0.03, 0.04, 0.025], 7,
             M_BARK, charred(rng), tile=0.5)
    snow_cap(g, (fc.x + 0.12, 0.05, fc.z - 0.1), 0.18, 0.14, 0.04, rng)
    # Skis + poles stuck upright in the snow, a little apart (whoever planted them meant to come back).
    for k, (x, z) in enumerate(((1.95, 0.25), (2.1, 0.12))):
        yaw = quat_y(0.3 + k * 0.15) @ quat_z(rng.uniform(-0.06, 0.06))
        base = V(x, -0.3, z)
        pts = [base, base + yaw @ V(0, 1.2, 0), base + yaw @ V(0, 1.6, 0), base + yaw @ V(-0.06, 1.72, 0)]
        beam(g, pts, 0.075, 0.025, up=tuple(yaw @ V(1, 0, 0)), mat=M_PLANK, col=(0.7, 0.5, 0.36), rng=rng, chamfer=0.3)
    for k, (x, z) in enumerate(((1.9, 0.55), (2.15, 0.48))):
        foot = V(x, -0.2, z)
        top = foot + V(rng.uniform(-0.1, 0.1), 1.45, rng.uniform(-0.08, 0.08))
        tube(g, [foot, top], [0.013, 0.012], 5, M_PLANK, (0.5, 0.4, 0.3), tile=0.3)
        disc(g, foot + V(0, 0.32, 0), quat_x(0.0), 0.07, 0.015, 8, M_HIDE, (0.4, 0.3, 0.22), tile=0.3)
    drift(g, (2.02, 0.0, 0.35), 0.4, 0.35, 0.16, rng)
    # The party's marker: a tall pole with a rag of a pennant, so the camp shows from afar.
    mp = V(-1.75, -0.3, -0.9)
    mt = mp + V(0.12, 3.1, 0.05)
    tube(g, [mp, mp.lerp(mt, 0.5), mt], [0.035, 0.03, 0.022], 6, M_PLANK, OLD_WOOD, tile=0.4)
    sheet(g, [[tuple(mt + V(0.0, -0.05 - 0.38 * v, 0.0) + V(0.62 * u, -0.12 * u * u, 0.04 * math.sin(u * 5)))
               for v in (0.0, 0.5, 1.0 - 0.4 * u)] for u in (0.0, 0.25, 0.5, 0.75, 1.0)],
          M_CLOTH, lambda u, v: mix((0.45, 0.14, 0.1), (0.3, 0.24, 0.2), u), tile=0.5, double=True)
    return b


def crest(g, centre, normal, up, s=1.0):
    """The old royal crest painted on a crate face: a faded blue field, a gold ring and a crown of
    three points (vertex colour on thin plates, no text)."""
    c, n, u = Vector(centre), Vector(normal).normalized(), Vector(up).normalized()
    r = u.cross(n).normalized()
    field = (0.16, 0.22, 0.42)
    gold = (0.78, 0.6, 0.26)
    quad = [c - r * 0.16 * s - u * 0.13 * s, c + r * 0.16 * s - u * 0.13 * s, c + r * 0.16 * s + u * 0.13 * s,
            c - r * 0.16 * s + u * 0.13 * s]
    q2 = [p + n * 0.004 for p in quad]
    if (q2[1] - q2[0]).cross(q2[3] - q2[0]).dot(n) < 0:
        q2 = q2[::-1]
    g.poly(q2, [(0, 0), (1, 0), (1, 1), (0, 1)], [n] * 4, [field] * 4, M_CLOTH)
    ring = [c + n * 0.008 + (r * math.cos(a) + u * math.sin(a)) * 0.075 * s - u * 0.02 * s
            for a in np.linspace(0, 2 * math.pi, 13)]
    tube(g, ring, [0.01 * s] * 13, 4, M_IRON, gold, tile=0.2, cap=False)
    for k in (-1, 0, 1):
        base = c + n * 0.009 + u * 0.065 * s + r * k * 0.05 * s
        tri = [base - r * 0.018 * s, base + r * 0.018 * s, base + u * (0.06 if k == 0 else 0.045) * s]
        if (tri[1] - tri[0]).cross(tri[2] - tri[0]).dot(n) < 0:
            tri = tri[::-1]
        g.poly(tri, [(0, 0), (1, 0), (0.5, 1)], [n] * 3, [gold] * 3, M_IRON)


def wagon_bed(g, rng, centre, rot, length=2.2, width=1.1, sides=True, broken_side=False, col=WOOD):
    """A wagon's box: plank floor on two sills + side boards. Returns nothing; `rot` orients it."""
    c = Vector(centre)
    for k in range(8):
        x = -length / 2 + (k + 0.5) * length / 8
        board(g, c + rot @ V(x, 0.0, 0), rot @ V(0, 0, 1), rot @ V(0, 1, 0), width, length / 8 * 0.95, 0.04, mat=M_PLANK,
              col=mix(col, (0.45, 0.4, 0.35), rng.uniform(0, 0.35)), rng=rng)
    for z in (-width * 0.38, width * 0.38):
        beam(g, [c + rot @ V(-length / 2 - 0.05, -0.07, z), c + rot @ V(length / 2 + 0.05, -0.07, z)], 0.1, 0.11,
             up=tuple(rot @ V(0, 0, 1)), mat=M_PLANK, col=OLD_WOOD, rng=rng)
    if sides:
        for sz in (-1, 1):
            if broken_side and sz > 0:
                continue
            for h in (0.14, 0.34):
                board(g, c + rot @ V(0, h, sz * width / 2), rot @ V(1, 0, 0), rot @ V(0, 0, sz), length, 0.19, 0.035,
                      mat=M_PLANK, col=col, rng=rng)
            for x in (-length / 2 + 0.06, 0.0, length / 2 - 0.06):
                beam(g, [c + rot @ V(x, -0.05, sz * (width / 2 + 0.03)), c + rot @ V(x, 0.46, sz * (width / 2 + 0.03))],
                     0.06, 0.05, up=tuple(rot @ V(0, 0, 1)), mat=M_PLANK, col=OLD_WOOD, rng=rng)


BRONZE = (0.42, 0.27, 0.13)
VERDIGRIS = (0.27, 0.45, 0.37)


def bronze_fn(nz):
    """Old bronze: a dark warm body, verdigris bloom on the sky-facing and sheltered faces."""
    def f(p, n):
        k = smoothstep(0.0, 0.85, n.y) * 0.7 + 0.3 * nz(p * 2.5)
        return scale(mix(BRONZE, VERDIGRIS, min(1.0, max(0.0, k))), 0.9 + 0.1 * nz(p * 6.0))
    return f


def lathe(profile, seg, centre, rot):
    """Revolve `(r, y)` profile points about the local Y axis -> (verts, tris)."""
    c = Vector(centre)
    verts, tris, idx = [], [], []
    for r, y in profile:
        idx.append((len(verts), r < 1e-4))
        if r < 1e-4:
            verts.append(c + rot @ V(0, y, 0))
        else:
            for i in range(seg):
                a = 2 * math.pi * i / seg
                verts.append(c + rot @ V(math.cos(a) * r, y, math.sin(a) * r))
    for (i0, p0), (i1, p1) in zip(idx, idx[1:]):
        for i in range(seg):
            j = (i + 1) % seg
            if p0:
                tris.append((i0, i1 + i, i1 + j))
            elif p1:
                tris.append((i0 + i, i1, i0 + j))
            else:
                tris += [(i0 + i, i1 + i, i1 + j), (i0 + i, i1 + j, i0 + j)]
    return verts, tris


def orient(verts, tris, axis_c, axis_d, outward):
    """Wind every triangle so its normal points away from (outward) / toward the bell's axis."""
    out = []
    for a, b, d in tris:
        n = (verts[b] - verts[a]).cross(verts[d] - verts[a])
        m = (verts[a] + verts[b] + verts[d]) / 3
        rel = m - axis_c
        radial = rel - axis_d * rel.dot(axis_d)
        if radial.length < 0.05:
            radial = axis_d * rel.dot(axis_d)
        out.append((a, b, d) if (n.dot(radial) > 0) == outward else (a, d, b))
    return out


def bell(g, rng, lip_centre, rot, h=1.3, r=0.62, seg=20):
    """A cast bronze bell, mouth at local y=0 (`lip_centre`), crown up local +Y: thick sound bow,
    a raised band at the shoulder, the hanging loops (canons) on the crown. Smooth outer + inner shell."""
    nz = Noise(rng, 3, 1.5)
    c = Vector(lip_centre)
    axis = rot @ V(0, 1, 0)
    outer = [(r, -0.02), (r * 1.04, 0.06), (r * 0.99, 0.14), (r * 0.86, 0.3), (r * 0.76, 0.5), (r * 0.7, 0.72),
             (r * 0.68, 0.86), (r * 0.72, 0.9), (r * 0.72, 0.95), (r * 0.66, 0.98), (r * 0.6, 1.07),
             (r * 0.45, 1.15), (r * 0.22, 1.19), (0.0, 1.2)]
    outer = [(rr, y * h / 1.2) for rr, y in outer]
    v, t = lathe(outer, seg, c, rot)
    smooth_mesh(g, v, orient(v, t, c, axis, True), M_IRON, bronze_fn(nz), 0.5)
    inner = [(r * 0.9, -0.02), (r * 0.78, 0.25), (r * 0.62, 0.62), (r * 0.55, 0.95), (r * 0.3, 1.08), (0.0, 1.1)]
    inner = [(rr, y * h / 1.2) for rr, y in inner]
    v, t = lathe(inner, seg, c, rot)
    smooth_mesh(g, v, orient(v, t, c, axis, False), M_IRON, lambda p, n: scale(BRONZE, 0.45), 0.5)
    for i in range(seg):
        a, b2 = 2 * math.pi * i / seg, 2 * math.pi * (i + 1) / seg
        quad = [c + rot @ V(math.cos(a) * r, -0.02, math.sin(a) * r), c + rot @ V(math.cos(b2) * r, -0.02, math.sin(b2) * r),
                c + rot @ V(math.cos(b2) * r * 0.9, -0.02, math.sin(b2) * r * 0.9),
                c + rot @ V(math.cos(a) * r * 0.9, -0.02, math.sin(a) * r * 0.9)]
        nn = -axis
        if (quad[1] - quad[0]).cross(quad[3] - quad[0]).dot(nn) < 0:
            quad = quad[::-1]
        g.poly(quad, [(0, 0), (1, 0), (1, 1), (0, 1)], [nn] * 4, [scale(BRONZE, 0.8)] * 4, M_IRON)
    # Canons: two crossed loops on the crown.
    top = c + axis * (h * 1.19 / 1.2)
    for ang in (0.0, math.pi / 2):
        sdir = rot @ V(math.cos(ang), 0, math.sin(ang))
        pts = [top + sdir * 0.13 * math.cos(u) + axis * 0.17 * math.sin(u) for u in np.linspace(0, math.pi, 7)]
        tube(g, pts, [0.045] * 7, 6, M_IRON, scale(BRONZE, 0.9), tile=0.3, cap=False)


def bell_crest(g, centre, normal, up, s=1.0):
    """The Crown's arms cast in relief on the bell: a raised ring round a three-pointed crown on its
    band, a shade brighter than the patina around them."""
    c, n, u = Vector(centre), Vector(normal).normalized(), Vector(up).normalized()
    r = u.cross(n).normalized()
    u = n.cross(r).normalized()
    gold = (0.74, 0.54, 0.25)
    ring = [c + n * 0.012 + (r * math.cos(a) + u * math.sin(a)) * 0.17 * s for a in np.linspace(0, 2 * math.pi, 15)]
    tube(g, ring, [0.024 * s] * 15, 4, M_IRON, gold, tile=0.2, cap=False)
    tube(g, [c + n * 0.016 - r * 0.1 * s - u * 0.04 * s, c + n * 0.016 + r * 0.1 * s - u * 0.04 * s], [0.024 * s] * 2, 4,
         M_IRON, gold, tile=0.2)
    for k in (-1, 0, 1):
        base = c + n * 0.018 - u * 0.03 * s + r * k * 0.075 * s
        tip = base + u * (0.14 if k == 0 else 0.1) * s + r * k * 0.015 * s
        tube(g, [base, tip], [0.026 * s, 0.006 * s], 4, M_IRON, gold, tile=0.2, cap=False)


def story_wrecked_convoy(rng):
    """Footprint r <= 3.6, long axis along local X (= the trail direction), the trail on local -Z.
    The Crown was hauling a war bell up the pass: the lead wagon's front axle broke under it, its
    timber bell-cradle snapped, and the bronze bell rolled out and lies on its side in a drift, mouth
    to the trail, the Crown cast on its flank, snow on top, haul ropes trailing, the clapper flung
    clear. The second wagon lies thrown on its side behind it; the ox is under the snow.
    Masses: the bell (0.25, -1.4), the bell wagon (1.55, 0.55), the overturned wagon (-1.75, 0.35),
    the ox's drift (-0.1, 1.95)."""
    b = Builder()
    g = G(b)
    drift(g, (0.0, 0.0, 0.0), 3.3, 2.0, 0.22, rng, power=0.7, rings=6, seg=20)
    # ── the bell, tipped out on its side: axis nearly level, mouth turned toward the trail (-Z) and a
    # little down the pass, the lip and flank sunk a hand into the snow.
    rot_b = quat_y(1.1) @ quat_x(math.pi / 2 + 0.12)
    axis = rot_b @ V(0, 1, 0)
    lip = V(-0.4, 0.55, -1.7)
    bell(g, rng, lip, rot_b, h=1.32, r=0.62)
    side = axis.cross(V(0, 1, 0)).normalized()
    up_side = side.cross(axis).normalized()
    if up_side.y < 0:
        up_side = -up_side
    # The Crown in relief on the flank turned to the trail and the sky.
    to_trail = V(0, 0, -1) - axis * V(0, 0, -1).dot(axis)
    cn = (to_trail.normalized() + up_side * 0.8).normalized()
    crest_c = lip + axis * 0.62 + cn * (0.62 * 0.74)
    bell_crest(g, crest_c, cn, axis, s=1.0)
    # Snow lying along the bell's top and banked against its crown (the mouth and flank stay clear).
    snow_cap(g, tuple(lip + axis * 0.95 + up_side * 0.42 - cn * 0.12), 0.24, 0.3, 0.07, rng)
    drift(g, tuple(lip + axis * 1.8), 0.75, 0.7, 0.42, rng, power=1.0, rings=5, seg=14)
    drift(g, tuple(V(lip.x, 0.0, lip.z) + axis * 0.7), 0.8, 0.6, 0.14, rng, power=0.8, rings=4, seg=14)
    # ── the bell wagon: a heavy flatbed, front axle snapped so its nose sits in the snow, tilted
    # toward the trail where the bell went over the side.
    qw = quat_y(0.05) @ quat_x(-0.16) @ quat_z(-0.17)
    cw = V(1.6, 0.42, 0.6)
    wagon_bed(g, rng, cw, qw, length=2.3, width=1.2, sides=False)
    rear = cw + qw @ V(-0.85, -0.25, 0.0)
    beam(g, [rear + qw @ V(0, 0, -0.66), rear + qw @ V(0, 0, 0.66)], 0.1, 0.1, mat=M_PLANK, col=OLD_WOOD, rng=rng)
    for sz in (-0.66, 0.66):
        wheel(g, rear + qw @ V(0, 0, sz), qw @ quat_x(math.pi / 2), 0.58, rng)
    front = cw + qw @ V(0.9, -0.28, 0.0)
    beam(g, [front + V(0, 0, -0.62), front + V(0.06, -0.06, 0.05)], 0.1, 0.1, mat=M_PLANK, col=OLD_WOOD, rng=rng,
         jag=(0.0, 0.14))  # the snapped front axle
    wheel(g, V(3.0, 0.08, 1.45), quat_y(0.4) @ quat_x(0.08), 0.58, rng, broken=2)  # flung flat
    # The cradle: two A-frame trestles on the bed with a headstock between them. The rear trestle
    # still stands; the front one snapped at the knees and the headstock fell across toward the bell.
    ra = cw + qw @ V(-0.7, 0.04, 0.0)
    apex_r = ra + qw @ V(0, 1.35, 0)
    for sz in (-0.52, 0.52):
        beam(g, [ra + qw @ V(0, 0, sz), apex_r], 0.12, 0.12, mat=M_PLANK, col=OLD_WOOD, rng=rng)
    beam(g, [ra + qw @ V(0, 0.55, -0.32), ra + qw @ V(0, 0.55, 0.32)], 0.08, 0.08, mat=M_PLANK, col=OLD_WOOD, rng=rng)
    fa = cw + qw @ V(0.75, 0.04, 0.0)
    for sz, ln in ((-0.52, 0.42), (0.52, 0.3)):
        beam(g, [fa + qw @ V(0, 0, sz), fa + qw @ V(0, ln, sz * (1 - ln / 1.35))], 0.12, 0.12, mat=M_PLANK, col=OLD_WOOD,
             rng=rng, jag=(0.0, 0.16))
    head_end = V(1.55, 0.12, -0.7)
    beam(g, [apex_r + qw @ V(0.0, 0.05, 0.0), head_end], 0.16, 0.16, mat=M_PLANK, col=OLD_WOOD, rng=rng, jag=(0.0, 0.2))
    snow_cap(g, tuple(apex_r.lerp(head_end, 0.45) + V(0, 0.1, 0)), 0.16, 0.12, 0.04, rng)
    # The thrown front trestle leg in the snow.
    beam(g, [V(2.95, 0.07, -0.45), V(2.25, 0.1, -1.35)], 0.12, 0.12, mat=M_PLANK, col=OLD_WOOD, rng=rng, jag=(0.18, 0.0))
    # Haul ropes: one still knotted round the headstock, snapped short and hanging; one trailing from
    # the bed across the snow to the bell's crown loop; a frayed end out toward the trail.
    rope = (0.6, 0.52, 0.38)
    hp = apex_r.lerp(head_end, 0.35)
    tube(g, [hp, hp + V(0.02, -0.4, -0.05), hp + V(0.08, -0.7, -0.02)], [0.03, 0.028, 0.012], 5, M_HIDE, rope, tile=0.3)
    crown_loop = lip + axis * 1.48
    pts = [cw + qw @ V(-1.05, 0.02, -0.45), V(1.0, 0.06, -0.3), V(0.85, 0.05, -0.5), crown_loop + V(0, -0.05, 0)]
    tube(g, [Vector(p) for p in pts], [0.03] * 4, 5, M_HIDE, rope, tile=0.3, cap=False)
    tube(g, [V(0.35, 0.05, -0.75), V(-0.2, 0.04, -0.55), V(-0.55, 0.05, -0.8)], [0.03, 0.03, 0.01], 5, M_HIDE, rope,
         tile=0.3)
    # The iron clapper, flung clear, lying in the snow toward the trail.
    clc = (0.4, 0.38, 0.37)
    k0, k1 = V(-1.75, 0.09, -2.3), V(-1.05, 0.1, -2.75)
    tube(g, [k0, k1], [0.035, 0.045], 6, M_IRON, clc, tile=0.2)
    stone(g, tuple(k1 + (k1 - k0).normalized() * 0.1), (0.13, 0.11, 0.11), rng, mat=M_IRON, detail=1, rough=0.02, cuts=0,
          col_fn=lambda p, n: mix(clc, (1, 1, 1), 0.5 * smoothstep(0.5, 0.95, n.y)), tile=0.2)
    tube(g, [k0 - (k1 - k0).normalized() * 0.08, k0], [0.06, 0.06], 6, M_IRON, clc, tile=0.2)
    # ── the second wagon, thrown on its side behind: bed vertical, floor toward the trail; the top
    # pair of wheels in the air (the bottom pair is under the drift), its tongue jutting at the sky.
    qa = quat_y(0.12) @ quat_x(math.pi / 2)
    ca = V(-1.75, 0.56, 0.5)
    wagon_bed(g, rng, ca, qa, broken_side=True)
    for k, x in enumerate((-0.75, 0.75)):
        beam(g, [ca + qa @ V(x, -0.2, -0.66), ca + qa @ V(x, -0.2, 0.3)], 0.08, 0.08, mat=M_PLANK, col=OLD_WOOD, rng=rng)
        wheel(g, ca + qa @ V(x, -0.2, -0.64), quat_y(0.12), 0.55, rng, broken=1 if k == 1 else 0)
    drift(g, (ca.x, 0.0, ca.z + 0.6), 1.45, 0.6, 0.4, rng, power=0.9, rings=4, seg=14)
    t0 = ca + qa @ V(-0.75, -0.25, -0.2)
    t1 = t0 + V(-0.75, 1.9, -0.4)
    beam(g, [t0, t1], 0.09, 0.08, mat=M_PLANK, col=OLD_WOOD, rng=rng, jag=(0.0, 0.2))
    snow_cap(g, t0.lerp(t1, 0.35) + V(0, 0.06, 0), 0.12, 0.1, 0.035, rng)
    # The ox, under the snow: a long drift with a horn and a few ribs breaking the surface.
    drift(g, (-0.1, 0.0, 2.0), 1.15, 0.55, 0.42, rng, power=1.0, rings=4, seg=14)
    bone = (0.82, 0.78, 0.68)
    for k in range(4):
        x = -0.5 + k * 0.22
        tube(g, [V(x, 0.18, 1.85), V(x + 0.03, 0.5, 2.0), V(x + 0.05, 0.42, 2.23)], [0.025, 0.022, 0.015], 4, M_ROCK, bone,
             tile=0.3)
    tube(g, [V(0.9, 0.3, 2.2), V(1.1, 0.48, 2.3), V(1.15, 0.65, 2.2)], [0.035, 0.025, 0.006], 5, M_ROCK, bone, tile=0.3)
    # Two crested Crown crates and a sack, spilled.
    for (x, y, z), yaw, size in (((-1.0, 0.2, -0.8), 0.5, (0.5, 0.4, 0.42)), ((2.75, 0.17, -1.15), -0.3, (0.44, 0.34, 0.4))):
        q = quat_y(yaw)
        crate(g, (x, y, z), size, q, rng, col=(0.7, 0.6, 0.48))
        crest(g, V(x, y, z) + q @ V(0, 0.0, -size[2] / 2 - 0.012), q @ V(0, 0, -1), (0, 1, 0))
        snow_cap(g, (x, y + size[1] / 2 + 0.02, z), size[0] * 0.45, size[2] * 0.45, 0.05, rng)
    sack(g, (2.2, 0.1, 1.55), quat_y(1.9) @ quat_z(1.35), 1.0, rng)
    return b


FIELDSTONE = (0.88, 0.9, 0.93)  # light, cool, desaturated grey over s_rock


def course_wall(g, rng, axis, fixed, a0, a1, top, depth=0.3, double=False, lean=0.0):
    """A dry-stone wall laid in HORIZONTAL COURSES of individual fieldstones (one rough slab each,
    the way `wayside_cairn` lays its stones), along X at z=`fixed` (`axis` 'x') or along Z at
    x=`fixed`, from a0 to a1. Joints stagger course to course; `top(t)` (t = 0..1 along the wall)
    is the ragged crown height — stones above it are left out, a few more go missing at random, and
    every stone with nothing laid on it gets a snow cap. `double` = two stones thick (the gable);
    `lean` shifts each course outward with height (+ along the wall's normal)."""
    nz = Noise(rng, 4, 3.0)
    y, ci = -0.1, 0
    peak = max(top(t / 20) for t in range(21))
    while y < peak:
        h = rng.uniform(0.18, 0.28)
        pos = a0 - (rng.uniform(0.12, 0.26) if ci % 2 else rng.uniform(0.0, 0.06))
        shift = lean * max(y, 0.0)
        while pos < a1 - 0.05:
            ln = rng.uniform(0.3, 0.55)
            s0, s1 = max(pos, a0), min(pos + ln, a1)
            pos += ln
            if s1 - s0 < 0.14:
                continue
            mid = (s0 + s1) / 2
            crown = top((mid - a0) / (a1 - a0))
            if y + h * 0.5 > crown or (y > 0.5 and rng.random() < 0.05):
                continue
            capped = y + h + 0.1 > crown
            for lay in ((-0.5, 0.5) if double else (0.0,)):
                d = depth * rng.uniform(0.85, 1.05)
                across = fixed + lay * depth + shift + rng.uniform(-0.02, 0.02)
                tint = scale(FIELDSTONE, rng.uniform(0.9, 1.04))
                col = rock_col(tint, moss=0.08, ground=0.0, dark_below=0.85, noise=nz, var=0.08)
                rot = quat_y(rng.uniform(-0.07, 0.07)) @ quat_z(rng.uniform(-0.04, 0.04)) @ quat_x(rng.uniform(-0.04, 0.04))
                if axis == 'x':
                    c, size = (mid, y + h / 2, across), (s1 - s0 - 0.02, h * rng.uniform(0.9, 1.0), d)
                else:
                    c, size = (across, y + h / 2, mid), (d, h * rng.uniform(0.9, 1.0), s1 - s0 - 0.02)
                slab(g, c, size, rot, rng, res=(2, 1, 1) if axis == 'x' else (1, 1, 2), round_r=0.035, rough=0.08,
                     cuts=int(rng.integers(1, 3)), col_fn=col, tile=0.5)
                if capped:
                    rx, rz = (size[0] * 0.42, size[2] * 0.4) if axis == 'x' else (size[0] * 0.4, size[2] * 0.42)
                    mound(g, (c[0], y + h - 0.02, c[2]), rx, rz, 0.06, rng, mat=M_SNOW, col_fn=snow_fn(nz), tile=1.6,
                          rings=1, seg=6, skirt=0.0, rough=0.08, edge=0.1, power=0.6)
        y += h
        ci += 1


def story_hermitage(rng):
    """Footprint r <= 3.4. Masses: the chapel walls (local 0, 0, 1.45 x 1.05 box), the graves
    (-2.4, 1.15). Anselm's hermitage: a ruined dry-stone chapel cell of cool grey fieldstone, the
    walls broken and stepped (1.0–2.1u), the north one leaning; the west gable rises into a bell-cote
    whose open arch stands EMPTY against the sky (~4.1u, the tall mark), a stub of the bell beam in
    it; the roof fallen in as charred beams over a drift in the nave; the writing slope and a shelf
    inside; two snow-mounded graves with crude crosses; rubble at the wall feet."""
    b = Builder()
    g = G(b)
    W2, D2, T = 1.4, 1.0, 0.34
    grey = rock_col(FIELDSTONE, moss=0.08, ground=0.0, dark_below=0.85)
    # South wall (still standing), north wall (broken down to a gap, leaning out), east wall with
    # the door gap, west gable stepping up to the bell-cote.
    gx = -W2 + 0.28  # the gable is two stones thick
    jag = lambda t, k: 0.12 * math.sin(t * 17.0 + k) * math.sin(t * 7.3 + 2 * k)  # noqa: E731
    # South wall, still standing, stepping down eastward; north wall broken to a gap and leaning out;
    # east wall either side of the door; the west gable rising to the bell-cote.
    course_wall(g, rng, 'x', -D2 + 0.16, gx + 0.28, W2, lambda t: 2.05 - 0.5 * t + jag(t, 0.0), depth=0.32)
    course_wall(g, rng, 'x', D2 - 0.16, gx + 0.28, W2,
                lambda t: 1.75 - 1.15 * math.exp(-((t - 0.55) / 0.2) ** 2) - 0.35 * t + jag(t, 1.0), depth=0.32,
                lean=0.045)
    course_wall(g, rng, 'z', W2 - 0.16, -D2 + 0.32, -0.38, lambda t: 1.72 - 0.15 * t + jag(t, 2.0), depth=0.32)
    course_wall(g, rng, 'z', W2 - 0.16, 0.38, D2 - 0.32, lambda t: 1.2 + 0.2 * t + jag(t, 3.0), depth=0.32)
    course_wall(g, rng, 'z', gx, -D2, D2, lambda t: 2.15 + 0.75 * (1.0 - abs(2 * t - 1.0)) + 0.6 * jag(t, 4.0),
                depth=0.28, double=True)
    # The door's lintel, fallen across the threshold.
    slab(g, (W2 + 0.25, 0.1, 0.05), (0.34, 0.2, 1.0), quat_y(0.25), rng, res=(2, 1, 4), round_r=0.04, rough=0.05,
         col_fn=grey, tile=0.6)
    # Bell-cote: two piers and an arch of voussoirs, the opening EMPTY; a little pitched cap on top.
    for z in (-0.36, 0.36):
        slab(g, (gx, 2.98, z), (T, 1.02, 0.22), quat_y(0.0), rng, res=(2, 3, 2), round_r=0.03, rough=0.05,
             col_fn=grey, tile=0.6)
    ac, ar = V(gx, 3.47, 0.0), 0.36
    for k in range(7):
        t = math.pi * (k + 0.5) / 7
        p = ac + V(0.0, math.sin(t) * ar, math.cos(t) * ar)
        slab(g, tuple(p), (T, 0.15, 0.2), quat_x(-(t - math.pi / 2)), rng, res=(2, 1, 2), round_r=0.025,
             rough=0.04, col_fn=grey, tile=0.5)
    slab(g, (gx, 3.94, 0.0), (T + 0.06, 0.13, 1.0), quat_y(0.0), rng, res=(2, 1, 4), round_r=0.03, rough=0.04,
         col_fn=grey, tile=0.6)
    for sgn in (-1, 1):
        slab(g, (gx, 4.07, sgn * 0.22), (T + 0.02, 0.08, 0.52), quat_x(sgn * 0.55), rng, res=(2, 1, 3), round_r=0.02,
             rough=0.03, col_fn=grey, tile=0.6)
    snow_cap(g, (gx, 4.12, 0.0), 0.2, 0.36, 0.05, rng)
    snow_cap(g, (gx, 2.82, 0.0), 0.2, 0.46, 0.06, rng)
    # A stub of the bell beam still in the north pier, its end broken off — nothing hangs from it.
    beam(g, [V(gx, 3.36, 0.3), V(gx, 3.34, 0.07)], 0.09, 0.08, mat=M_PLANK, col=OLD_WOOD, rng=rng, jag=(0.0, 0.08))
    # The roof, fallen in: charred grey beams down into the nave, one rafter still leaning on the
    # south wall, a few boards; snow drifted in over it all.
    char = lambda k: mix((0.24, 0.22, 0.21), (0.46, 0.45, 0.44), k)  # noqa: E731
    for p0, p1, k in (((-1.15, 2.55, 0.05), (1.05, 0.12, 0.35), 0.2), ((-0.75, 1.95, -0.7), (0.55, 0.15, 0.5), 0.5),
                      ((0.9, 1.6, -0.72), (0.15, 0.1, 0.55), 0.1), ((-0.9, 0.12, 0.6), (0.45, 0.62, -0.35), 0.35)):
        beam(g, [V(*p0), V(*p1)], 0.11, 0.1, mat=M_PLANK, col=char(k), rng=rng, jag=(0.1, 0.12))
    beam(g, [V(-0.35, 1.98, -0.72), V(-0.32, 2.55, -0.15)], 0.1, 0.09, mat=M_PLANK, col=char(0.4), rng=rng, jag=(0.0, 0.14))
    for k in range(4):
        x = -0.6 + k * 0.42
        board(g, V(x, 0.2 + 0.05 * k, 0.1 - 0.12 * k), V(0.3, 0.0, 1.0), V(0.0, 1.0, 0.15), 0.9, 0.3, 0.035,
              mat=M_PLANK, col=char(rng.uniform(0.1, 0.6)), rng=rng, jag=(0.0, 0.1))
    drift(g, (0.15, 0.0, 0.3), 1.0, 0.6, 0.48, rng, rings=5, seg=16)
    # Writing slope against the south wall + a shelf with a clay jar and a book block.
    ls = V(-0.35, 0.0, -0.5)
    beam(g, [ls + V(0, -0.1, 0), ls + V(0, 0.95, 0)], 0.08, 0.08, mat=M_PLANK, col=OLD_WOOD, rng=rng)
    board(g, ls + V(0.0, 1.02, 0.05), V(1, 0, 0), V(0, 0.8, 0.6), 0.55, 0.42, 0.03, mat=M_PLANK, col=WOOD, rng=rng)
    lbox(g, ls + V(0.0, 1.07, 0.04), (0.3, 0.04, 0.22), quat_x(-0.64), M_HIDE, (0.42, 0.28, 0.2), tile=0.3)
    board(g, V(0.55, 1.15, -D2 + T + 0.12), V(1, 0, 0), V(0, 1, 0), 0.8, 0.24, 0.04, mat=M_PLANK, col=WOOD, rng=rng)
    frustum(g, 0.06, 0.04, 1.17, 0.18, 9, M_EARTH, (0.62, 0.42, 0.3), tile=0.3, centre=(0.35, 0, -D2 + T + 0.12))
    lbox(g, (0.7, 1.24, -D2 + T + 0.12), (0.2, 0.16, 0.14), quat_y(0.1), M_HIDE, (0.35, 0.22, 0.15), tile=0.3)
    # Rubble at the wall feet — fallen courses, half in the snow.
    for cx, cz, n in ((0.2, 1.45, 4), (-0.4, 1.35, 2), (1.85, 0.6, 2), (1.75, -0.8, 2), (-2.0, -0.75, 2)):
        rubble(g, rng, n, cx, cz, 0.35, 0.12, 0.2, grey, y=-0.03)
    # Drifts banked against the walls.
    drift(g, (-1.95, 0.0, -0.3), 0.5, 1.1, 0.42, rng, rings=4, seg=14)
    drift(g, (0.2, 0.0, -1.45), 1.45, 0.42, 0.4, rng, rings=4, seg=14)
    drift(g, (1.85, 0.0, 0.55), 0.48, 0.6, 0.3, rng, rings=4, seg=14)
    drift(g, (0.0, 0.0, 1.5), 1.2, 0.45, 0.32, rng, rings=4, seg=14)
    # Two graves outside the west gable: low mounds under the snow, crude lashed crosses (one leaning).
    for k, (x, z) in enumerate(((-2.35, 0.6), (-2.5, 1.75))):
        drift(g, (x, 0.0, z), 0.4, 0.72, 0.26, rng, power=1.2, rings=4, seg=14)
        foot = V(x, -0.25, z - 0.68)
        lean = V(0.0, 0.0, 0.0) if k == 0 else V(0.32, 0.0, -0.18)
        top = foot + V(0.03, 1.3, 0.0) + lean
        beam(g, [foot, top], 0.07, 0.06, mat=M_PLANK, col=OLD_WOOD, rng=rng)
        arm = foot.lerp(top, 0.78)
        beam(g, [arm + V(0, 0, -0.26), arm + V(0, 0, 0.26)], 0.06, 0.05, mat=M_PLANK, col=OLD_WOOD, rng=rng)
        lashing(g, arm, tuple(top - foot), 0.05, rng, turns=2)
        snow_cap(g, top + V(0, 0.02, 0), 0.05, 0.05, 0.03, rng)
    return b


def story_old_ones_ring(rng):
    """Footprint r <= 3.6. Masses: 6 stones on a 2.8 ring + the totem at the centre.
    The Old Ones' ring: carved standing stones, each with concentric circles cut into its face (a
    bell's voice, spreading), the tallest ~3.3u; the orks' offerings at the centre — a frozen
    totem pole hung with tusks and bone fetishes, tusks laid on a flat stone."""
    b = Builder()
    g = G(b)
    drift(g, (0.0, 0.0, 0.0), 3.4, 3.2, 0.2, rng, power=0.6, rings=8, seg=28)
    heights = [3.3, 2.1, 2.6, 1.8, 2.4, 2.0]
    for k, h in enumerate(heights):
        a = k / 6 * 2 * math.pi + 0.2
        c = V(math.cos(a) * 2.8, h / 2 - 0.3, math.sin(a) * 2.8)
        face = -V(math.cos(a), 0, math.sin(a))  # carvings face the centre
        rot = quat_y(-a + math.pi / 2) @ quat_z(rng.uniform(-0.05, 0.05))
        w = 0.7 if k == 0 else rng.uniform(0.5, 0.65)
        slab(g, tuple(c), (w, h + 0.6, 0.38), rot, rng, res=(3, 8, 2), round_r=0.08, taper=0.25, rough=0.05,
             col_fn=dusted((0.58, 0.58, 0.6), 0.85), tile=1.0, crown=0.15)
        snow_cap(g, tuple(c + V(0, (h + 0.6) / 2 - 0.05, 0)), w * 0.3, 0.14, 0.05, rng)
        # Concentric rings, cut dark into the face.
        cy = c.y + h * 0.18
        right = V(0, 1, 0).cross(face).normalized()
        for rr in (0.08, 0.15, 0.22):
            ring = [V(c.x, cy, c.z) + face * 0.205 + (right * math.cos(t) + V(0, 1, 0) * math.sin(t)) * rr * (w / 0.6)
                    for t in np.linspace(0, 2 * math.pi, 15)]
            tube(g, ring, [0.012] * 15, 4, M_ROCK, (0.18, 0.18, 0.2), tile=0.2, cap=False)
    # The centre: a flat offering stone, tusks and bones on it, the totem behind.
    slab(g, (0.0, 0.05, 0.4), (1.0, 0.3, 0.7), quat_y(0.3), rng, res=(3, 1, 2), round_r=0.06, rough=0.04,
         col_fn=dusted((0.5, 0.5, 0.52), 0.5), tile=0.8)
    ivory = (0.86, 0.8, 0.66)
    for k in range(4):
        a = 0.3 + k * 0.5
        p = V(-0.3 + k * 0.2, 0.24, 0.3 + (k % 2) * 0.2)
        d = V(math.cos(a), 0, math.sin(a))
        tube(g, [p, p + d * 0.2 + V(0, 0.05, 0), p + d * 0.32 + V(0, 0.14, 0)], [0.04, 0.03, 0.006], 6, M_ROCK, ivory, tile=0.2)
    tc = V(0.0, -0.3, -0.35)
    tube(g, [tc, tc + V(0.02, 1.4, 0.0), tc + V(0.0, 2.8, 0.02)], [0.16, 0.14, 0.12], 8, M_BARK, (0.45, 0.4, 0.36), tile=0.6)
    for k, (y, s) in enumerate(((0.9, 0.24), (1.6, 0.22), (2.3, 0.2))):
        lbox(g, tc + V(0, y, 0), (s * 1.6, s * 1.3, s * 1.6), quat_y(k * 0.7), M_PLANK, (0.42, 0.36, 0.3), tile=0.5)
        snow_cap(g, tc + V(0, y + s * 0.67, 0), s * 0.7, s * 0.7, 0.04, rng)
    for sgn in (-1, 1):  # tusks lashed to the top block, curving out
        base = tc + V(sgn * 0.18, 2.35, 0.1)
        tube(g, [base, base + V(sgn * 0.25, 0.2, 0.08), base + V(sgn * 0.32, 0.5, 0.0)], [0.05, 0.035, 0.006], 6, M_ROCK,
             ivory, tile=0.2)
    snow_cap(g, tc + V(0, 2.52, 0), 0.13, 0.13, 0.05, rng)
    for k in range(5):  # bone fetishes hanging on cords
        a = k / 5 * 2 * math.pi
        top = tc + V(math.cos(a) * 0.2, 1.95, math.sin(a) * 0.2)
        low = top + V(math.cos(a) * 0.08, -0.45, math.sin(a) * 0.08)
        tube(g, [top, low], [0.005, 0.005], 3, M_CLOTH, W.ROPE, tile=0.2)
        tube(g, [low, low + V(0, -0.16, 0)], [0.02, 0.014], 5, M_ROCK, ivory, tile=0.2)
        lashing(g, low, (0, 1, 0), 0.025, rng, turns=1)
    # A ring of small ork stakes with skull-white knobs, and frost-split bones at the stones' feet.
    for k in range(7):
        a = k / 7 * 2 * math.pi + 0.5
        p = V(math.cos(a) * 1.35, -0.2, math.sin(a) * 1.35)
        tube(g, [p, p + V(0, 0.75, 0)], [0.03, 0.025], 5, M_BARK, (0.4, 0.35, 0.3), tile=0.3)
        stone(g, tuple(p + V(0, 0.82, 0)), (0.07, 0.07, 0.07), rng, mat=M_ROCK, detail=1, rough=0.05, cuts=0,
              col_fn=lambda q, n: ivory, tile=0.2)
    return b


def story_ruined_homestead(rng):
    """Footprint r <= 3.0; masses: the burned log house (local -0.6, 0.2, 1.3 x 1.05), the well
    (1.55, -0.95, r 0.6), the palisade stub (1.7, 1.5), the hand-cart (-2.0, -1.35). A first-colony
    steading out past the chapel bell's reach: the log house burned and fell in, its charred roof
    beams jutting from the drift; a few courses of the walls still stand at two corners; a short run
    of sharpened palisade stakes, half of them snapped or leaning out; the stone well with its winch
    fallen across it; a hand-cart left tipped on its nose; a barrel and a broken wheel by the door."""
    b = Builder()
    g = G(b)
    char = (0.2, 0.18, 0.17)
    log = (0.58, 0.53, 0.48)
    drift(g, (0.0, 0.0, 0.0), 2.8, 2.35, 0.2, rng, power=0.7, rings=5, seg=20)
    # ── the log house: two standing corners of notched logs (the rest burned down to the sill),
    # a drift filling the inside, charred rafters and the ridge beam jutting out of it.
    hx, hz = -0.6, 0.2
    w, d = 2.4, 1.9
    for k in range(5):
        y = 0.12 + k * 0.21
        col = mix(log, char, 0.15 + 0.15 * k)
        # back-left corner: two walls of falling length
        tube(g, [V(hx - w / 2 - 0.12, y, hz + d / 2), V(hx - w / 2 + 1.5 - k * 0.27, y, hz + d / 2)], [0.11, 0.1], 7,
             M_BARK, col, tile=0.7)
        tube(g, [V(hx - w / 2, y + 0.1, hz + d / 2 + 0.12), V(hx - w / 2, y + 0.1, hz + d / 2 - 1.2 + k * 0.2)], [0.11, 0.1],
             7, M_BARK, col, tile=0.7)
        if k < 3:  # front-right corner, lower
            tube(g, [V(hx + w / 2 + 0.12, y, hz - d / 2), V(hx + w / 2 - 1.1 + k * 0.3, y, hz - d / 2)], [0.11, 0.1], 7,
                 M_BARK, mix(col, char, 0.3), tile=0.7)
            tube(g, [V(hx + w / 2, y + 0.1, hz - d / 2 - 0.12), V(hx + w / 2, y + 0.1, hz - d / 2 + 0.9 - k * 0.25)],
                 [0.11, 0.1], 7, M_BARK, mix(col, char, 0.3), tile=0.7)
    # sill logs along the burned-down walls, just showing through the snow
    for p0, p1 in (((hx + w / 2, 0.05, hz + d / 2), (hx - w / 2 + 1.0, 0.07, hz + d / 2)),
                   ((hx - w / 2, 0.05, hz - d / 2), (hx + w / 2 - 1.2, 0.06, hz - d / 2)),
                   ((hx + w / 2, 0.06, hz + d / 2), (hx + w / 2, 0.05, hz - d / 2 + 0.9))):
        tube(g, [V(*p0), V(*p1)], [0.11, 0.1], 6, M_BARK, char, tile=0.7)
    drift(g, (hx + 0.1, 0.0, hz), 1.35, 1.05, 0.55, rng, power=0.9, rings=5, seg=16)
    cf = charred(rng)
    for p0, p1, r in (((hx - 0.9, 0.35, hz + 0.6), (hx + 0.7, 1.55, hz - 0.1), 0.1),  # the ridge beam, fallen in
                      ((hx - 0.3, 0.3, hz - 0.5), (hx - 0.9, 1.25, hz - 1.35), 0.075),
                      ((hx + 0.4, 0.3, hz - 0.4), (hx + 0.2, 1.05, hz - 1.45), 0.07),
                      ((hx + 0.1, 0.3, hz + 0.5), (hx + 0.8, 1.15, hz + 1.3), 0.07),
                      ((hx - 0.6, 0.25, hz + 0.1), (hx - 1.7, 0.85, hz - 0.3), 0.07)):
        beam(g, [V(*p0), V(*p1)], r * 1.8, r * 1.6, mat=M_PLANK, mode="timber", col=cf, rng=rng, jag=(0.0, 0.22))
    snow_cap(g, (hx - 0.6, 1.2, hz + 0.95), 0.25, 0.14, 0.05, rng)
    # A charred door, fallen flat in front of the house.
    lbox(g, V(hx + 0.5, 0.05, hz - d / 2 - 0.65), (0.8, 0.05, 1.2), quat_y(0.25) @ quat_z(0.06), M_PLANK,
         mix(OLD_WOOD, char, 0.5), tile=1.0)
    # ── the palisade stub: sharpened stakes, a few leaning out or snapped, on a buried rail.
    for k in range(7):
        t = k / 6
        x, z = 0.95 + t * 1.55, 1.15 + 0.55 * math.sin(t * 2.2)
        hgt = rng.uniform(1.3, 1.65)
        lean = V(rng.uniform(-0.08, 0.08), 0, rng.uniform(0.05, 0.25) if k in (2, 5) else rng.uniform(-0.05, 0.05))
        top = V(x, hgt, z) + lean * hgt
        if k in (1, 4):  # snapped
            top = V(x, 0.0, z).lerp(top, rng.uniform(0.35, 0.5))
            beam(g, [V(x, -0.1, z), top], 0.15, 0.14, mat=M_PLANK, mode="timber", col=OLD_WOOD, rng=rng, jag=(0.0, 0.12))
            continue
        pole(g, V(x, -0.15, z), top, 0.085, 0.075, rng, col=(0.66, 0.6, 0.53), sides=6)
        tube(g, [top, top + (top - V(x, 0, z)).normalized() * 0.22], [0.075, 0.004], 6, M_PLANK, (0.72, 0.64, 0.52),
             tile=0.3, cap=False)
    tube(g, [V(0.9, 0.75, 1.1), V(1.75, 0.8, 1.7)], [0.05, 0.05], 5, M_BARK, (0.6, 0.55, 0.5), tile=0.7)
    tube(g, [V(1.75, 0.06, 2.0), V(2.05, 0.3, 2.35)], [0.07, 0.07], 6, M_BARK, (0.6, 0.55, 0.5), tile=0.7)  # a toppled stake
    drift(g, (1.75, 0.0, 1.6), 1.1, 0.45, 0.35, rng, power=1.0, rings=4, seg=14)
    # ── the well: two courses of dressed fieldstones in a ring, frost on top; one winch post still
    # standing, the other down; the windlass roller lying across the mouth with its rope.
    wx, wz = 1.55, -0.95
    for course in range(2):
        for k in range(10):
            a = (k + 0.5 * course) / 10 * 2 * math.pi
            c = V(wx + math.cos(a) * 0.5, 0.12 + course * 0.22, wz + math.sin(a) * 0.5)
            stone_col = mix((0.62, 0.62, 0.62), (0.5, 0.48, 0.45), rng.uniform())
            lbox(g, c, (0.24, 0.21, 0.3), quat_y(-a), M_STONE, [scale(stone_col, 0.75), None, mix(stone_col, SNOW, 0.6)],
                 tile=0.8)
    disc(g, (wx, 0.1, wz), quat_y(0.0), 0.38, 0.02, 10, M_STONE, (0.05, 0.05, 0.06), tile=1.0)  # the dark shaft
    beam(g, [V(wx - 0.62, -0.1, wz), V(wx - 0.62, 1.25, wz)], 0.12, 0.12, mat=M_PLANK, mode="timber", col=OLD_WOOD, rng=rng)
    beam(g, [V(wx + 0.7, 0.08, wz + 0.2), V(wx + 1.4, 0.12, wz + 0.6)], 0.12, 0.12, mat=M_PLANK, mode="timber",
         col=OLD_WOOD, rng=rng, jag=(0.12, 0.0))
    roll0, roll1 = V(wx - 0.6, 0.55, wz + 0.1), V(wx + 0.55, 0.38, wz - 0.35)
    tube(g, [roll0, roll1], [0.08, 0.08], 7, M_BARK, (0.55, 0.5, 0.45), tile=0.6)
    tube(g, [roll1, roll1 + V(0.0, 0.0, -0.22), roll1 + V(0.0, -0.18, -0.25)], [0.025] * 3, 4, M_IRON, IRON, tile=0.2,
         cap=False)  # the crank
    tube(g, [roll0.lerp(roll1, 0.5), roll0.lerp(roll1, 0.5) + V(0.1, -0.2, 0.0), V(wx + 0.15, 0.05, wz - 0.65),
             V(wx + 0.1, 0.03, wz - 0.95)], [0.02] * 4, 4, M_HIDE, (0.6, 0.52, 0.38), tile=0.3, cap=False)
    # its bucket, on its side in the snow
    tube(g, [V(wx + 0.05, 0.15, wz - 1.05), V(wx + 0.3, 0.13, wz - 1.2)], [0.15, 0.17], 8, M_PLANK, OLD_WOOD, tile=0.5)
    snow_cap(g, (wx - 0.62, 1.27, wz), 0.08, 0.08, 0.04, rng)
    # ── the hand-cart, tipped onto its nose and left.
    qc = quat_y(0.7) @ quat_z(0.32)
    cc = V(-2.0, 0.42, -1.35)
    wagon_bed(g, rng, cc, qc, length=1.2, width=0.75)
    for sz in (-0.33, 0.33):
        beam(g, [cc + qc @ V(-0.55, -0.05, sz), cc + qc @ V(-1.25, -0.02, sz * 0.85)], 0.06, 0.06, mat=M_PLANK,
             col=OLD_WOOD, rng=rng)
    wheel(g, cc + qc @ V(0.15, -0.3, 0.48), qc @ quat_x(math.pi / 2), 0.42, rng, spokes=6)
    snow_cap(g, tuple(cc + qc @ V(0.0, 0.08, 0.0)), 0.45, 0.28, 0.07, rng)
    # ── by the door: a staved barrel and a broken wheel against the wall.
    bc = V(hx + 1.55, 0.0, hz - d / 2 - 0.4)
    prof = [0.0, 0.32, 0.62, 0.72]
    tube(g, [bc + V(0, y, 0) for y in prof], [0.23, 0.27, 0.27, 0.23], 10, M_PLANK, (0.6, 0.5, 0.4), tile=0.5)
    for y in (0.1, 0.62):
        tube(g, [bc + V(0.27 * math.cos(a), y, 0.27 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 11)],
             [0.015] * 11, 3, M_IRON, IRON, tile=0.2, cap=False)
    snow_cap(g, tuple(bc + V(0, 0.74, 0)), 0.2, 0.2, 0.05, rng)
    wheel(g, V(hx + w / 2 + 0.25, 0.35, hz + 0.1), quat_z(1.25) @ quat_y(0.3), 0.5, rng, broken=1)
    return b


MODELS_EXTRA = {
    "story_wrecked_convoy": story_wrecked_convoy,
    "story_hermitage": story_hermitage,
    "story_old_ones_ring": story_old_ones_ring,
    "story_ruined_homestead": story_ruined_homestead,
}


def story_buried_cabin(rng):
    """Footprint r <= 3.1; masses: the avalanche mound (local 0, 0, 2.2 x 1.7), the chimney (-1.9, -0.6)."""
    b = Builder()
    g = G(b)
    # The avalanche mound over the cabin.
    drift(g, (0.1, 0.0, 0.0), 2.6, 2.0, 1.25, rng, power=0.8, rings=7, seg=22, edge=0.22)
    drift(g, (1.6, 0.0, 1.0), 1.1, 0.9, 0.45, rng)
    # Caved-in roof: two pitches of planks folded down into the mound, one still on its ridge beam.
    rq = quat_y(0.12)
    ridge0, ridge1 = V(-1.6, 1.55, -0.55), V(1.2, 0.95, -0.15)
    beam(g, [ridge0, ridge1], 0.16, 0.16, mat=M_PLANK, mode="timber", col=OLD_WOOD, rng=rng, jag=(0.0, 0.25))
    for k in range(9):
        t = k / 8
        top = ridge0.lerp(ridge1, t)
        foot = top + rq @ V(0.05, -0.95 - 0.2 * t, 1.25)
        board(g, (top + foot) / 2 + V(0, 0.05, 0), foot - top, rq @ V(0, 0.8, 0.6), (foot - top).length, 0.3, 0.035,
              mat=M_PLANK, col=mix(OLD_WOOD, (0.4, 0.35, 0.3), rng.uniform(0, 0.4)), rng=rng,
              jag=(0.0, 0.15 if k % 3 == 1 else 0.0))
    snow_cap(g, ridge0.lerp(ridge1, 0.3) + rq @ V(0, -0.35, 0.55), 0.55, 0.4, 0.1, rng)
    # Rafters and wall logs jutting out of the snow at broken angles.
    for p0, p1, r in (((-0.6, 0.3, -1.3), (0.4, 1.7, -1.9), 0.09), ((0.9, 0.2, -1.1), (1.9, 1.3, -1.7), 0.08),
                      ((1.4, 0.4, 0.2), (2.7, 0.9, 0.5), 0.1), ((-0.2, 0.5, 1.2), (0.7, 1.1, 2.2), 0.085),
                      ((-1.1, 0.1, 1.0), (-2.2, 0.8, 1.9), 0.1)):
        beam(g, [V(*p0), V(*p1)], r * 1.8, r * 1.6, mat=M_PLANK, mode="timber", col=OLD_WOOD, rng=rng, jag=(0.0, 0.2))
    # The cabin's back wall corner: a few courses of logs still standing out of the mound's flank.
    for k in range(4):
        y = 0.15 + k * 0.22
        tube(g, [V(-1.55, y, -1.25), V(0.2 - k * 0.3, y, -1.45)], [0.11, 0.1], 8, M_BARK, (0.6, 0.55, 0.5), tile=0.7)
    # A shuttered window frame half out of the snow.
    lbox(g, V(0.9, 0.55, 1.55), (0.7, 0.6, 0.06), quat_y(0.4) @ quat_x(-0.35), M_PLANK, OLD_WOOD, tile=1.0)
    # The stone chimney, still standing, its foot buried, with a cap of snow.
    sc = (0.8, 0.79, 0.77)
    cx, cz = -1.9, -0.6
    lbox(g, (cx, 0.9, cz), (0.85, 2.2, 0.85), quat_y(0.05), M_STONE, [scale(sc, 0.7), None, sc], tile=1.2)
    lbox(g, (cx, 2.45, cz), (0.62, 0.95, 0.62), quat_y(0.05), M_STONE, [scale(sc, 0.75), None, sc], tile=1.2, v0=0.3)
    lbox(g, (cx, 2.98, cz), (0.72, 0.1, 0.72), quat_y(0.05), M_STONE, scale(sc, 0.65), tile=1.2)
    snow_cap(g, (cx, 3.03, cz), 0.38, 0.38, 0.09, rng)
    snow_cap(g, (cx + 0.2, 2.0, cz), 0.18, 0.4, 0.06, rng)
    drift(g, (cx - 0.1, 0.0, cz + 0.1), 0.85, 0.8, 0.6, rng)
    # Snow chunks broken off the slide.
    for k in range(6):
        r = rng.uniform(0.12, 0.28)
        a = rng.uniform(0, 6.28)
        d = rng.uniform(2.1, 2.7)
        stone(g, (math.cos(a) * d, 0.0, math.sin(a) * d * 0.8), (r, r * 0.7, r * 0.9), rng, mat=M_SNOW, detail=1,
              col_fn=snow_fn(Noise(rng, 2, 2.0)), tile=0.8)
    return b


def story_frozen_memorial(rng):
    """Footprint r <= 2.3; masses: the cairn (local 0, 0, r 0.6), the banner pole foot (0.55, -0.35)."""
    b = Builder()
    g = G(b)
    drift(g, (0.0, 0.0, 0.0), 2.0, 1.7, 0.22, rng, power=0.7)
    # The cairn: a rough cone of fieldstones, a helmet on top.
    rows = [(0.55, 6, 0.2), (0.42, 5, 0.17), (0.28, 4, 0.15), (0.12, 2, 0.13)]
    y = 0.05
    for rr, n, s in rows:
        for k in range(n):
            a = k / n * 2 * math.pi + rng.uniform(-0.2, 0.2) + y
            stone(g, (math.cos(a) * rr, y, math.sin(a) * rr), (s * rng.uniform(1.0, 1.3), s * 0.75, s), rng, detail=1,
                  col_fn=dusted((0.62, 0.6, 0.58), 0.8), tile=0.6)
        y += s * 1.15
    stone(g, (0.0, y - 0.05, 0.0), (0.2, 0.12, 0.18), rng, detail=1, col_fn=dusted((0.6, 0.58, 0.56)), tile=0.6)
    hq = quat_z(0.12) @ quat_x(-0.08)
    hc = V(0.0, y + 0.05, 0.0)
    dome(g, hc, 0.17, hq, M_IRON, lambda p, n: mix(scale(IRON, 0.8), (0.5, 0.36, 0.25), 0.3 + 0.3 * smoothstep(0.2, 0.9, n.y)),
         tile=0.25, rings=5, seg=14, squash=1.05, flare=0.15)
    beam(g, [hc + hq @ V(0, 0.02, 0.165), hc + hq @ V(0, -0.15, 0.175)], 0.03, 0.012, up=tuple(hq @ V(0, 0, 1)),
         mat=M_IRON, mode="bark", col=IRON, rng=rng)
    snow_cap(g, hc + hq @ V(-0.02, 0.17, 0.0), 0.1, 0.09, 0.03, rng)
    # Banner on a leaning pole, a tattered cloth hanging dead in the cold.
    bf = V(0.55, -0.3, -0.35)
    bt = bf + V(0.25, 2.55, -0.12)
    tube(g, [bf, bf.lerp(bt, 0.5) + V(0.01, 0, 0.01), bt], [0.025, 0.024, 0.02], 6, M_PLANK, OLD_WOOD, tile=0.4)
    cross0, cross1 = bt + V(-0.02, -0.1, -0.35), bt + V(0.02, -0.12, 0.35)
    tube(g, [cross0, cross1], [0.016, 0.016], 5, M_PLANK, OLD_WOOD, tile=0.3)
    ni, nj = 9, 7
    grid = []
    for i in range(ni):
        u = i / (ni - 1)
        row = []
        for j in range(nj):
            v = j / (nj - 1)
            top = cross0.lerp(cross1, v)
            length = 1.15 * (1 - 0.35 * abs(math.sin(v * 9.0 + 1.0))) * (0.75 if v > 0.7 else 1.0)
            p = top + V(0.05 * math.sin(u * 5 + v * 3) + 0.08 * u, -u * length, 0.02 * math.sin(u * 7))
            row.append(tuple(p))
        grid.append(row)
    sheet(g, grid, M_CLOTH, lambda u, v: mix((0.42, 0.1, 0.09), (0.3, 0.22, 0.18), smoothstep(0.5, 1.0, u)), tile=0.5,
          double=True)
    lashing(g, bt + V(-0.01, -0.11, 0.0), (0, 0, 1), 0.03, rng, turns=2)
    # Broken shields + spears in the snow around the cairn.
    for k, (x, z, broken, paint) in enumerate(((-1.0, 0.6, False, (0.45, 0.12, 0.1)), (1.15, 0.55, True, (0.2, 0.28, 0.4)),
                                               (-0.6, -1.15, True, (0.45, 0.12, 0.1)), (0.9, -1.2, False, (0.5, 0.42, 0.2)))):
        rot = quat_y(rng.uniform(0, 6.28)) @ quat_x(rng.uniform(-0.55, 0.55) if k % 2 else 1.25)
        shield(g, (x, 0.12 if k % 2 else 0.3, z), rot, 0.34, rng, broken=broken, paint=paint)
    for (fx, fz, tx, ty, tz, br) in ((-1.5, -0.2, -1.65, 1.6, -0.45, False), (1.6, -0.3, 1.9, 1.3, -0.1, False),
                                     (-0.3, 1.4, -0.45, 1.2, 1.75, True), (1.4, 1.2, 1.55, 0.9, 1.45, True),
                                     (0.2, -1.6, 0.1, 1.5, -1.95, False)):
        spear(g, (fx, -0.25, fz), (tx, ty, tz), rng, broken=br)
    # A fallen spear lying in the snow.
    spear(g, (-1.4, 0.05, 1.1), (-0.2, 0.08, 1.85), rng)
    for x, z in ((-1.2, 0.8), (1.0, -1.0)):
        drift(g, (x, 0.0, z), 0.45, 0.35, 0.13, rng)
    return b


# ─────────────────────────────────────────────────────────────── ROCKY
def story_mine_head(rng):
    """Footprint r <= 3.0; masses: the headframe legs (local 0, 0, 1.15 x 0.95 box), the cart (1.9, 0.6)."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 2.0)
    # Spoil heap + trodden ground.
    mound(g, (0.3, 0.0, 0.2), 2.7, 2.3, 0.08, rng, col_fn=lambda p, n: mix((0.42, 0.38, 0.33), (0.6, 0.55, 0.48),
                                                                           0.5 + 0.5 * nz(p * 2.0)), tile=1.2, rings=6, seg=24)
    mound(g, (-1.9, 0.0, 1.2), 1.0, 0.8, 0.45, rng, mat=M_ROCK, col_fn=rock_col((0.55, 0.52, 0.48), noise=nz), tile=0.7)
    # Shaft collar: a square timber frame around a black hole, cribbing going down.
    s = 0.62
    for k in range(4):
        a = k * math.pi / 2
        d = V(math.cos(a), 0, math.sin(a))
        side = V(-d.z, 0, d.x)
        beam(g, [d * s + side * (s + 0.14) + V(0, 0.08, 0), d * s - side * (s + 0.14) + V(0, 0.08, 0)], 0.2, 0.2,
             mat=M_PLANK, col=OLD_WOOD, rng=rng)
        q = [d * (s - 0.1) + side * (s - 0.1) + V(0, 0.0, 0), d * (s - 0.1) - side * (s - 0.1) + V(0, 0.0, 0),
             d * (s - 0.1) - side * (s - 0.1) + V(0, -1.2, 0), d * (s - 0.1) + side * (s - 0.1) + V(0, -1.2, 0)]
        g.flat(q[::-1] if (q[1] - q[0]).cross(q[3] - q[0]).dot(-d) < 0 else q, M_PLANK, [(0.25, 0.22, 0.2), (0.25, 0.22, 0.2),
                                                                                       (0.02, 0.02, 0.02), (0.02, 0.02, 0.02)], 1.0)
    g.flat([V(-0.6, -1.2, 0.6), V(0.6, -1.2, 0.6), V(0.6, -1.2, -0.6), V(-0.6, -1.2, -0.6)][::-1], M_EARTH, (0.01, 0.01, 0.01),
           1.0)
    # Headframe: four raking legs to a cap over the shaft, braces, the sheave wheel.
    top_y = 4.1
    legs = [((-1.05, -0.9), (-0.32, -0.28)), ((1.05, -0.9), (0.32, -0.28)), ((-1.05, 0.9), (-0.32, 0.28)),
            ((1.05, 0.9), (0.32, 0.28))]
    for (bx_, bz), (tx_, tz) in legs:
        beam(g, [V(bx_, -0.3, bz), V(tx_, top_y, tz)], 0.2, 0.2, mat=M_PLANK, col=weathered_col(rng), rng=rng)
    for y, f in ((1.3, 0.3), (2.6, 0.62)):
        for (i0, i1) in ((0, 1), (2, 3), (0, 2), (1, 3)):
            (b0x, b0z), (t0x, t0z) = legs[i0]
            (b1x, b1z), (t1x, t1z) = legs[i1]
            p0 = V(b0x + (t0x - b0x) * f, y, b0z + (t0z - b0z) * f)
            p1 = V(b1x + (t1x - b1x) * f, y, b1z + (t1z - b1z) * f)
            beam(g, [p0, p1], 0.14, 0.14, mat=M_PLANK, col=OLD_WOOD, rng=rng)
    for (i0, i1) in ((0, 1), (2, 3)):
        (b0x, b0z), (t0x, t0z) = legs[i0]
        (b1x, b1z), (t1x, t1z) = legs[i1]
        beam(g, [V(b0x + (t0x - b0x) * 0.3, 1.3, b0z + (t0z - b0z) * 0.3), V(b1x + (t1x - b1x) * 0.62, 2.6, b1z + (t1z - b1z) * 0.62)],
             0.1, 0.1, mat=M_PLANK, col=OLD_WOOD, rng=rng)
    for z in (-0.3, 0.3):
        beam(g, [V(-0.55, top_y, z), V(0.55, top_y, z)], 0.22, 0.2, mat=M_PLANK, col=OLD_WOOD, rng=rng)
    beam(g, [V(0, top_y + 0.12, -0.45), V(0, top_y + 0.12, 0.45)], 0.12, 0.12, mat=M_PLANK, col=OLD_WOOD, rng=rng)
    wheel(g, V(0.0, top_y + 0.55, 0.0), quat_x(math.pi / 2), 0.45, rng, spokes=6, col=(0.55, 0.5, 0.45))
    # Rope from the sheave down the shaft, frayed and slack.
    tube(g, [V(0.45, top_y + 0.55, 0.0), V(0.42, 2.0, 0.02), V(0.38, -1.0, 0.0)], [0.02] * 3, 5, M_CLOTH, W.ROPE, tile=0.3)
    tube(g, [V(-0.45, top_y + 0.55, 0.0), V(-0.8, 3.0, 0.3), V(-1.3, 1.2, 0.9), V(-1.45, 0.05, 1.2), V(-1.0, 0.04, 1.6)],
         [0.02] * 5, 5, M_CLOTH, W.ROPE, tile=0.3)
    # Rail run: sleepers + two rails leading out to +X, ending in the tipped cart.
    for k in range(7):
        x = 0.85 + k * 0.34
        beam(g, [V(x, 0.03, -0.4), V(x, 0.03, 0.4)], 0.12, 0.08, mat=M_PLANK, col=(0.5, 0.45, 0.4), rng=rng)
    for z in (-0.25, 0.25):
        beam(g, [V(0.75, 0.1, z), V(3.0, 0.1, z)], 0.04, 0.05, mat=M_IRON, mode="bark", col=IRON, rng=rng, chamfer=0.1)
    cq = quat_y(0.2) @ quat_x(1.15)
    cc = V(2.15, 0.42, 0.85)
    lbox(g, cc, (0.95, 0.55, 0.6), cq, M_PLANK, [scale(WOOD, 0.6), None, scale(WOOD, 0.9)], tile=1.0, grain=0)
    for x in (-0.4, 0.4):
        beam(g, [cc + cq @ V(x, -0.28, -0.31), cc + cq @ V(x, 0.28, -0.31), cc + cq @ V(x, 0.28, 0.31)], 0.05, 0.02,
             mat=M_IRON, mode="bark", col=IRON, rng=rng, chamfer=0.1)
    for x in (-0.33, 0.33):
        for z in (-0.33, 0.33):
            disc(g, cc + cq @ V(x, -0.3, z), cq @ quat_x(math.pi / 2), 0.13, 0.05, 10, M_IRON, IRON, tile=0.3)
    # Ore spilled out of it.
    for k in range(14):
        r = rng.uniform(0.06, 0.14)
        stone(g, (2.0 + rng.uniform(-0.5, 0.5), r * 0.3, 1.45 + rng.uniform(-0.3, 0.45)), (r, r * 0.7, r * 0.85), rng,
              detail=1, col_fn=rock_col((0.42, 0.36, 0.32), noise=nz), tile=0.4)
    # Lantern on a post by the collar.
    lp = V(-1.0, -0.2, -1.05)
    beam(g, [lp, lp + V(0, 1.75, 0)], 0.1, 0.1, mat=M_PLANK, col=OLD_WOOD, rng=rng)
    beam(g, [lp + V(0, 1.7, 0), lp + V(0.42, 1.7, 0)], 0.06, 0.06, mat=M_PLANK, col=OLD_WOOD, rng=rng)
    lc = lp + V(0.38, 1.38, 0)
    tube(g, [lc + V(0, 0.32, 0), lc + V(0, 0.18, 0)], [0.006, 0.006], 4, M_IRON, IRON, tile=0.2)
    lbox(g, lc + V(0, 0.08, 0), (0.12, 0.18, 0.12), quat_y(0.3), M_IRON, (0.3, 0.27, 0.22), tile=0.3)
    dome(g, lc + V(0, 0.17, 0), 0.075, quat_y(0.0), M_IRON, lambda p, n: (0.3, 0.27, 0.22), tile=0.2, rings=2, seg=8)
    # Rubble + a dropped shovel.
    rubble(g, rng, 7, -1.5, -0.2, 0.5, 0.08, 0.2, rock_col(ROCKY, noise=nz))
    tube(g, [V(-0.9, 0.05, 1.3), V(-0.15, 0.06, 1.75)], [0.018, 0.018], 6, M_PLANK, WOOD, tile=0.3)
    lbox(g, V(-0.06, 0.04, 1.8), (0.2, 0.02, 0.26), quat_y(-0.55), M_IRON, IRON, tile=0.3)
    return b


def weathered_col(rng):
    return mix(OLD_WOOD, (0.48, 0.42, 0.36), rng.uniform(0, 0.5))


def story_rockfall_wagon(rng):
    """Footprint r <= 2.9; masses: the wagon under the boulders (local 0, 0, 1.5 x 0.9 box)."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 2.0)
    # Track ruts (trodden earth strip) under everything.
    mound(g, (0.0, 0.0, 0.0), 2.8, 1.1, 0.03, rng, col_fn=lambda p, n: mix((0.36, 0.32, 0.27), (0.55, 0.5, 0.43),
                                                                         0.5 + 0.5 * nz(p * 2.5)), tile=1.0, rings=4, seg=22)
    # The wagon bed, crushed and broken-backed under the boulders.
    wq = quat_y(0.0) @ quat_z(-0.1)
    for k in range(9):
        x = -1.1 + k * 0.27
        tilt = quat_z(-0.35 if x > 0.25 else -0.05) @ quat_x(rng.uniform(-0.08, 0.08))
        board(g, V(x, 0.35 - (0.2 if x > 0.25 else 0.0) + (x - 0.25) * 0.25 * (x > 0.25), 0), tilt @ V(0, 0, 1), tilt @ V(0, 1, 0),
              1.05, 0.25, 0.035, mat=M_PLANK, col=mix(WOOD, (0.45, 0.4, 0.35), rng.uniform(0, 0.4)), rng=rng,
              jag=(0.0, 0.1) if k in (4, 5) else (0, 0))
    for z in (-0.5, 0.5):
        beam(g, [V(-1.25, 0.28, z), V(0.2, 0.3, z)], 0.1, 0.12, mat=M_PLANK, col=OLD_WOOD, rng=rng, jag=(0, 0.15))
        beam(g, [V(0.35, 0.22, z), V(1.25, -0.05, z)], 0.1, 0.12, mat=M_PLANK, col=OLD_WOOD, rng=rng, jag=(0.15, 0))
    # Side board, one still up, one knocked flat.
    board(g, V(-0.5, 0.55, -0.55), V(1, 0, 0), V(0, 0, 1), 1.4, 0.32, 0.04, mat=M_PLANK, col=WOOD, rng=rng)
    board(g, V(-0.3, 0.05, 0.95), V(1, 0, 0.15), V(0, 1, 0), 1.3, 0.3, 0.04, mat=M_PLANK, col=WOOD, rng=rng, jag=(0, 0.2))
    # Wheels: the rear pair still on, one leaning; the front one splintered on the ground.
    wheel(g, V(-0.85, 0.42, -0.62), quat_x(math.pi / 2), 0.42, rng)
    wheel(g, V(-0.85, 0.4, 0.66), quat_x(math.pi / 2 - 0.25), 0.42, rng)
    wheel(g, V(1.35, 0.05, 1.05), quat_y(0.4) @ quat_x(0.05), 0.42, rng, broken=2)
    beam(g, [V(-0.85, 0.42, -0.7), V(-0.85, 0.42, 0.72)], 0.08, 0.08, mat=M_PLANK, col=OLD_WOOD, rng=rng)
    # Shaft/tongue snapped off, lying out front.
    beam(g, [V(1.3, 0.08, -0.15), V(2.5, 0.05, -0.55)], 0.08, 0.08, mat=M_PLANK, col=OLD_WOOD, rng=rng, jag=(0.18, 0))
    # The boulders that came down.
    rc = rock_col((0.72, 0.68, 0.62), ground=0.0, noise=nz, moss=0.15, lichen=(0.6, 0.6, 0.45))
    stone(g, (0.55, 0.55, -0.05), (0.85, 0.7, 0.75), rng, detail=2, col_fn=rc, tile=1.0, cuts=3)
    stone(g, (-0.3, 0.72, 0.15), (0.55, 0.42, 0.5), rng, detail=2, col_fn=rc, tile=0.9, cuts=2)
    stone(g, (1.55, 0.3, -0.95), (0.6, 0.45, 0.55), rng, detail=2, col_fn=rc, tile=0.9, cuts=2)
    stone(g, (-1.8, 0.2, -0.85), (0.45, 0.35, 0.4), rng, detail=1, col_fn=rc, tile=0.8)
    rubble(g, rng, 12, 0.3, -0.6, 1.6, 0.06, 0.18, rc)
    # Spilled sacks, one burst open into a little heap of grain.
    for k, (x, z, a) in enumerate(((-1.55, 0.55, 0.4), (-1.2, 1.05, 1.6), (0.05, 1.2, -0.7))):
        sack(g, (x, 0.12, z), quat_y(a) @ quat_z(1.35), 1.0, rng)
    mound(g, (0.3, 0.0, 1.45), 0.35, 0.25, 0.07, rng, mat=M_EARTH, col_fn=lambda p, n: (0.85, 0.72, 0.45), tile=0.4,
          rings=3, seg=12, skirt=0.02)
    return b


def story_quarry(rng):
    """Footprint r <= 2.9; masses: the bedrock + half-cut block (local -0.4, 0, 1.4 x 0.95), the blank (1.4, 0.6)."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 5, 1.6)
    rc = rock_col((0.82, 0.78, 0.72), noise=nz, moss=0.1, lichen=(0.62, 0.6, 0.45), var=0.08)
    cut = rock_col((0.92, 0.9, 0.86), noise=nz, var=0.04)
    # Stone dust + chips underfoot.
    mound(g, (0.0, 0.0, 0.0), 2.8, 2.3, 0.04, rng, col_fn=lambda p, n: mix((0.6, 0.57, 0.52), (0.8, 0.77, 0.72),
                                                                         0.5 + 0.5 * nz(p * 3.0)), tile=1.0, rings=4, seg=22)
    # Bedrock shelf with a stepped face where blocks have already come out.
    slab(g, (-0.6, 0.15, -0.4), (2.6, 0.9, 1.8), quat_y(0.08), rng, res=(8, 3, 6), round_r=0.12, rough=0.05,
         col_fn=rc, tile=1.2, crown=0.3)
    slab(g, (-1.5, 0.75, -0.9), (1.0, 0.6, 1.0), quat_y(0.1), rng, res=(3, 2, 3), round_r=0.1, rough=0.06, col_fn=rc,
         tile=1.2, cuts=1)
    # The half-cut block: sawn faces still clean, the channel cut on two sides, iron wedges in the line.
    bq = quat_y(0.08)
    slab(g, (0.0, 1.05, -0.25), (0.95, 0.95, 0.85), bq, rng, res=(3, 3, 3), round_r=0.02, rough=0.01, col_fn=cut,
         tile=1.0)
    for k in range(4):
        x = -0.38 + k * 0.25
        p = V(0.0, 1.55, -0.25) + bq @ V(x, 0.0, 0.45)
        lbox(g, p, (0.05, 0.12, 0.04), bq @ quat_x(0.1), M_IRON, IRON, tile=0.2)
    lbox(g, V(0.0, 0.65, -0.25) + bq @ V(0.0, 0.0, 0.44), (0.95, 0.04, 0.03), bq, M_EARTH, (0.05, 0.05, 0.05), tile=1.0)
    # A monolith blank on log rollers, ready to be dragged off and never moved.
    mq = quat_y(0.6)
    mc = V(1.25, 0.55, 0.9)
    for t in (-0.9, 0.0, 0.85):
        a = mc + mq @ V(t, -0.38, 0)
        pole(g, a + mq @ V(0, 0, -0.55), a + mq @ V(0, 0, 0.55), 0.09, 0.09, rng, col=(0.62, 0.56, 0.5), sides=8)
    slab(g, tuple(mc + V(0, 0.08, 0)), (2.3, 0.6, 0.62), mq, rng, res=(8, 2, 2), round_r=0.03, rough=0.015, col_fn=cut,
         tile=1.1, taper=0.0)
    # Tools: a pick, a mallet, chisels, a bucket, a lever pole leaning on the bedrock.
    pickaxe(g, (0.9, 0.0, -1.45), (1.35, 0.6, -1.25), rng)
    mal = V(-0.2, 0.08, 1.15)
    tube(g, [mal + V(-0.4, 0.0, -0.1), mal], [0.02, 0.022], 6, M_PLANK, WOOD, tile=0.3)
    lbox(g, mal + V(0.05, 0.02, 0.01), (0.12, 0.13, 0.24), quat_y(0.25), M_PLANK, (0.6, 0.5, 0.4), tile=0.4)
    for k in range(3):
        a = rng.uniform(0, 6.28)
        c = V(0.25 + k * 0.12, 0.02, 1.35 + rng.uniform(-0.1, 0.1))
        beam(g, [c, c + V(math.cos(a) * 0.22, 0.0, math.sin(a) * 0.22)], 0.025, 0.02, mat=M_IRON, mode="bark", col=IRON,
             rng=rng, point=0.03)
    frustum(g, 0.14, 0.17, -0.02, 0.28, 12, M_PLANK, (0.6, 0.5, 0.4), tile=0.6, centre=(-0.75, 0, 1.15))
    tube(g, [V(-0.75 + 0.17 * math.cos(a), 0.28 + 0.1 * math.sin(a), 1.15) for a in np.linspace(0.1, math.pi - 0.1, 7)],
         [0.006] * 7, 4, M_IRON, IRON, tile=0.2)
    pole(g, V(-2.2, -0.1, 0.3), V(-1.2, 1.7, -0.1), 0.05, 0.04, rng, col=(0.7, 0.62, 0.52), sides=7)
    # Chips around the block.
    rubble(g, rng, 16, 0.4, 0.5, 1.1, 0.04, 0.12, cut)
    rubble(g, rng, 5, -2.0, -1.2, 0.5, 0.15, 0.3, rc)
    return b


MODELS = {
    "story_lost_camp": story_lost_camp,
    "story_buried_cabin": story_buried_cabin,
    "story_frozen_memorial": story_frozen_memorial,
    "story_mine_head": story_mine_head,
    "story_rockfall_wagon": story_rockfall_wagon,
    "story_quarry": story_quarry,
    **MODELS_EXTRA,
}

if __name__ == "__main__":
    clear_scene()
    objs = []
    report = {}
    only = set(sys.argv[sys.argv.index("--") + 1:]) if "--" in sys.argv else set()
    for i, (name, fn) in enumerate(MODELS.items()):
        b = fn(np.random.default_rng(4100 + i))
        report[name] = bounds(b)
        objs.append(b.build(name, MATS))
    export_glb(OUT / "stories_cold.glb", objs)
    for k, v in report.items():
        print(f"{k}: {v}")
    print("STORIES_COLD_DONE")
