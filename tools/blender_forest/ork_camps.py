"""The five ork camps, each its own place -> ork_camps.glb (src/camps.rs).

One camp per wilderness biome, and no two alike (docs/superpowers/specs/2026-10-12-wyspa-opowiada-design.md
§1 rule 6): the old template (tents + campfire + banner + skull spikes + cage) is gone.

    ork_camp_shaman   FOREST  the shamans' ritual ground: a bone circle round the ritual fire, carved
                              totems, a dead oak hung with charms, the great drum, the shaman's hide
                              hut and an offering slab. No cages.
    ork_camp_raiders  DESERT  raiders squatting in a ruined caravanserai: broken sandstone courses, the
                              arched iwan with the last turquoise tiles, a stolen-rug awning over the
                              loot of the Pasha's caravans (rolled rugs, bales, jars), a goat on the spit.
    ork_camp_cave     ROCKY   a warband living in a cave mouth under a limestone overhang. On the inner
                              wall rows of tally strokes: an old scratched column of hundreds that stops
                              mid-row, and a fresh column in charcoal beside it.
    ork_camp_stilts   SWAMP   the cage camp: a lashed deck on stilts over the bog water, a reed lean-to
                              roof, food bowls set out in front of the cages, a gibbet cage over the
                              water; on the bank a smudge fire, a fish rack, a dugout, eel traps.
    ork_camp_hunters  SNOW    a winter hunters' camp: two hide yurts, drying racks with a stretched hide
                              and meat strips, a frozen pond with fishing holes, an elk carcass hanging
                              from a tripod. A people, not a horde.

The cages themselves are NOT in these models: camps.rs spawns the gameplay cage (`ork_cage` +
hinged door + captives) at the anchor each camp's layout names, so the rescue keeps working.
Camp-local coordinates: the camp centre is the origin, Y up; the anchors here (fire, cages, flag
pole, blocker boxes, warband spots) are mirrored in camps.rs `LAYOUTS` — change both together.
Ground-contact parts run below y=0 so a camp on slightly uneven ground never floats.

    blender -b --factory-startup --python tools/blender_forest/ork_camps.py [-- name ...]
"""
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
                            V, beam, board, bounds, lashing, lbox, mix, mound, pole, rock_col, scale, slab,
                            smooth_mesh, smoothstep, stone, tube, Noise)
import ork_folk  # noqa: E402
from stories_cold import (M_SNOW, MATS as COLD_MATS, crate, disc, dome, lathe, orient, snow_fn,  # noqa: E402
                          shield, spear)

WIND_YAW = 0.6  # the camp's prevailing wind (drifts build their crest + lee lip along it)


def drift(g, centre, rx, rz, h, rng, power=None, **_):
    """A WIND-SCULPTED drift (replaces the round snow mound): a long windward ramp scored with
    sastrugi ripples, a crest, and a sharp leeward lip that curls over a steep lee face. `rx` is the
    half-length along the wind, `rz` the half-width; the rim sinks under the ground."""
    c = Vector(centre)
    rq = quat_y(WIND_YAW + rng.uniform(-0.25, 0.25))
    nz = Noise(rng, 4, 1.4)
    uc = rng.uniform(0.35, 0.55)
    nu, nv = 18, 10
    verts, idx = [], {}
    for i in range(nu + 1):
        u = -1 + 2 * i / nu
        for j in range(nv + 1):
            v = -1 + 2 * j / nv
            across = max(0.0, 1 - abs(v) ** 1.8) ** 0.7 * (1 + 0.12 * math.sin(v * 3.3 + u))
            if u <= uc:
                prof = ((u + 1) / (uc + 1)) ** 1.5
                rip = 0.07 * math.sin(v * rz * 14.0 + u * 2.0 + nz(V(u, v, 0)) * 2.0) * smoothstep(-1.0, -0.3, u)
            else:
                prof = max(0.0, 1 - ((u - uc) / (1 - uc)) ** 0.42)
                rip = 0.0
            y = h * (prof * across + rip * across) - 0.14 * (max(abs(u), abs(v)) ** 6)
            x = u * rx
            # The cornice: the crest's top curls a little past the lee face.
            if prof > 0.75 and u > uc - 0.1:
                x += 0.18 * h * smoothstep(0.75, 1.0, prof) * across
            idx[(i, j)] = len(verts)
            verts.append(c + rq @ V(x, y, v * rz))
    tris = []
    for i in range(nu):
        for j in range(nv):
            a, b2, c2, d2 = idx[(i, j)], idx[(i + 1, j)], idx[(i + 1, j + 1)], idx[(i, j + 1)]
            for t in ((a, b2, c2), (a, c2, d2)):
                n = (verts[t[1]] - verts[t[0]]).cross(verts[t[2]] - verts[t[0]])
                tris.append(t if n.y >= 0 else (t[0], t[2], t[1]))
    smooth_mesh(g, verts, tris, M_SNOW, snow_fn(nz), 1.8)


M_PLASTER = len(COLD_MATS)
M_ASHLAR = M_PLASTER + 1
MATS = COLD_MATS + ["s_plaster", "s_ashlar"]

BONE = (1.22, 1.15, 0.98)
OLD_BONE = (1.0, 0.94, 0.8)
ROPE = (0.9, 0.76, 0.52)
RAWHIDE = (0.95, 0.8, 0.58)
SOOT = (0.08, 0.075, 0.07)
OCHRE = (0.62, 0.2, 0.1)
HIDE = (0.72, 0.6, 0.48)
DARK_HIDE = (0.46, 0.38, 0.3)
TIMBER = (0.78, 0.68, 0.56)
EARTH = (0.6, 0.52, 0.44)


# ─────────────────────────────────────────────────────────────── shared pieces
def ground_patch(g, rng, c, rx, rz, col, h=0.035, mat=M_EARTH, tile=1.0):
    """Trodden ground / ash bed: a very low disc whose rim sinks under the terrain."""
    nz = Noise(rng, 3, 1.6)
    cc = Vector(c)

    def f(p, n):
        d = math.hypot((p.x - cc.x) / rx, (p.z - cc.z) / rz)
        return scale(col, (0.85 + 0.15 * nz(p * 2.0)) * (0.82 + 0.18 * smoothstep(0.0, 0.9, d)))
    mound(g, tuple(c), rx, rz, h, rng, mat=mat, col_fn=f, tile=tile, rings=4, seg=22, skirt=0.12, rough=0.3, edge=0.16,
          power=0.5)


def firepit(g, rng, c, r=0.45, n=9, stone_col=(0.78, 0.76, 0.72)):
    """Stone ring, ash bed, charred logs leaning into a cone (the flame is the game's)."""
    c = Vector(c)
    nz = Noise(rng, 3, 2.0)
    for k in range(n):
        a = k / n * 2 * math.pi + rng.uniform(-0.12, 0.12)
        s = rng.uniform(0.1, 0.15)
        p = c + V(math.cos(a) * r, s * 0.35, math.sin(a) * r)
        blk = lambda q, nn, p=p: mix(scale(stone_col, 0.95 + 0.1 * nz(q * 4)), SOOT, 0.55 * smoothstep(0.0, -1.0, (q - c).normalized().dot((p - c).normalized()) - 0.9))
        stone(g, tuple(p), (s, s * 0.75, s * 0.9), rng, detail=1, col_fn=blk, tile=0.4)
    mound(g, tuple(c + V(0, -0.02, 0)), r * 0.85, r * 0.85, 0.06, rng, mat=M_EARTH,
          col_fn=lambda p, nn: mix((0.16, 0.15, 0.14), (0.42, 0.4, 0.38), 0.3 + 0.3 * nz(p * 6)), tile=0.5, rings=3, seg=14,
          skirt=0.04)
    for k in range(4):
        a = k / 4 * 2 * math.pi + rng.uniform(0.2, 0.6)
        base = c + V(math.cos(a) * r * 0.8, 0.05, math.sin(a) * r * 0.8)
        tip = c + V(math.cos(a) * 0.05, 0.32, math.sin(a) * 0.05)
        tube(g, [base, tip], [0.05, 0.035], 6, M_BARK, (0.3, 0.27, 0.25), tile=0.6,
             col_fn=lambda t: mix((0.34, 0.3, 0.27), (0.05, 0.045, 0.04), t))


def bone(g, a, b, r, rng, col=BONE):
    """A long bone: shaft with knobbed ends."""
    a, b = Vector(a), Vector(b)
    d = (b - a).normalized()
    tube(g, [a, a + (b - a) * 0.15, a + (b - a) * 0.85, b], [r * 1.5, r, r * 0.95, r * 1.4], 6, M_STONE, col, tile=0.25)
    for e in (a, b):
        stone(g, tuple(e + d * (0.01 if e is b else -0.01)), (r * 1.7, r * 1.4, r * 1.7), rng, mat=M_STONE, detail=0,
              col_fn=lambda p, n: col, tile=0.2, cuts=0)


def skull(g, p, s, rng, col=BONE, horns=0.0, yaw=0.0):
    """A beast skull facing local +Z (rotated by `yaw`): cranium, muzzle, dark sockets, optional horns."""
    p = Vector(p)
    rq = quat_y(yaw)
    nz = Noise(rng, 3, 3.0)
    cf = lambda q, n: scale(col, 0.85 + 0.12 * nz(q * 9) + 0.08 * n.y)
    stone(g, tuple(p + rq @ V(0, 0.05 * s, 0)), (0.1 * s, 0.085 * s, 0.11 * s), rng, mat=M_STONE, detail=1, col_fn=cf,
          tile=0.3, rough=0.08, cuts=1, rot=rq)
    stone(g, tuple(p + rq @ V(0, 0.0, 0.12 * s)), (0.055 * s, 0.05 * s, 0.09 * s), rng, mat=M_STONE, detail=1,
          col_fn=cf, tile=0.3, rough=0.06, cuts=1, rot=rq)
    for sx in (-1, 1):
        stone(g, tuple(p + rq @ V(sx * 0.045 * s, 0.065 * s, 0.085 * s)), (0.026 * s,) * 3, rng, mat=M_STONE, detail=0,
              col_fn=lambda q, n: SOOT, tile=0.3, cuts=0)
        if horns:
            base = p + rq @ V(sx * 0.08 * s, 0.1 * s, 0.0)
            pts = [base + rq @ V(sx * horns * 0.25 * t * 1.2, horns * (0.25 * t - 0.12 * t * t), -horns * 0.1 * t * t)
                   for t in np.linspace(0, 1.4, 6)]
            tube(g, pts, [0.03 * s * (1 - 0.8 * k / 5) + 0.004 for k in range(6)], 6, M_STONE, scale(col, 0.75), tile=0.2)


def antlers(g, base, s, rng, yaw=0.0, col=OLD_BONE):
    """A pair of elk antlers rising from `base` (palmate-ish beams with tines)."""
    base = Vector(base)
    rq = quat_y(yaw)
    for sx in (-1, 1):
        pts = [base + rq @ V(sx * (0.05 + 0.5 * t * s), 0.08 + 0.55 * t * s - 0.12 * t * t * s, -0.15 * t * s)
               for t in np.linspace(0, 1, 6)]
        tube(g, pts, [0.03 * s + 0.01 * (1 - t) for t in np.linspace(0, 1, 6)], 6, M_STONE, col, tile=0.2)
        for k in (2, 3, 4, 5):
            q = pts[k]
            tip = q + rq @ V(sx * 0.05 * s, (0.2 + 0.04 * k) * s, rng.uniform(-0.06, 0.08) * s)
            tube(g, [q, q.lerp(tip, 0.5) + V(0, 0.02, 0), tip], [0.022 * s, 0.015 * s, 0.004], 5, M_STONE, col, tile=0.2)


def cord(g, top, length, rng, col=ROPE, r=0.008):
    """A hanging thong: slight curve, returns the bottom point."""
    top = Vector(top)
    bot = top + V(rng.uniform(-0.02, 0.02), -length, rng.uniform(-0.02, 0.02))
    tube(g, [top, top.lerp(bot, 0.5) + V(0.01, 0, 0), bot], [r, r, r], 4, M_CLOTH, col, tile=0.2, cap=False)
    return bot


def feather(g, p, rng, col=(0.2, 0.18, 0.16)):
    p = Vector(p)
    a = rng.uniform(0, 6.28)
    d = V(math.cos(a) * 0.15, -0.95, math.sin(a) * 0.15).normalized()
    side = V(-math.sin(a), 0, math.cos(a))
    L = rng.uniform(0.16, 0.24)
    pts = []
    for i in range(5):
        t = i / 4
        w = 0.028 * math.sin(math.pi * min(t * 1.2, 1.0)) + 0.002
        pts.append([tuple(p + d * L * t - side * w), tuple(p + d * L * t + side * w)])
    sheet(g, pts, M_CLOTH, lambda u, v: scale(col, 0.8 + 0.4 * v), tile=0.2, double=True)


def stakes_ring(g, rng, c, r, n, h, col=TIMBER):
    for k in range(n):
        a = k / n * 2 * math.pi
        p = Vector(c) + V(math.cos(a) * r, -0.1, math.sin(a) * r)
        pole(g, p, p + V(rng.uniform(-0.03, 0.03), h, rng.uniform(-0.03, 0.03)), 0.03, 0.025, rng, col=col, sides=5)


def jar(g, rng, c, h, r, col=(0.95, 0.62, 0.42), tilt=None, broken=False):
    """A clay storage jar (lathe), mouth up; `tilt` lays it over."""
    prof = [(0.0, 0.0), (r * 0.45, 0.0), (r * 0.85, h * 0.12), (r, h * 0.42), (r * 0.82, h * 0.72), (r * 0.42, h * 0.86),
            (r * 0.36, h * 0.95), (r * 0.45, h)]
    if broken:
        prof = prof[:5]
    rot = tilt or quat_y(rng.uniform(0, 6.28))
    verts, tris = lathe(prof, 14, c, rot)
    axis = rot @ V(0, 1, 0)
    tris = orient(verts, tris, Vector(c), axis, True)
    nz = Noise(rng, 3, 3.0)
    cc = Vector(c)

    def f(p, n):
        y = (p - cc).dot(axis) / h
        k = 0.85 + 0.12 * nz(p * 6)
        band = 0.75 if 0.62 < y < 0.68 else 1.0  # a painted band
        dust = smoothstep(0.3, 0.0, y) * 0.25
        return mix(scale(col, k * band), (0.95, 0.82, 0.62), dust)
    smooth_mesh(g, verts, tris, M_PLASTER, f, 0.4)
    # Inside of the mouth: a dark disc.
    if not broken:
        disc(g, cc + axis * (h - 0.01), rot, r * 0.4, 0.01, 10, M_EARTH, (0.08, 0.06, 0.05), tile=0.3)


def striped(palette, stripes=7, phase=0.0):
    """Woven-rug colour: bands across the length + a fringe-dark border."""
    def f(u, v):
        k = int((u * stripes + phase) % len(palette))
        edge = 0.7 if (u < 0.06 or u > 0.94) else 1.0
        return scale(palette[k], edge * (0.92 + 0.08 * math.sin(v * 31.0)))
    return f


RUG_PALETTES = [
    [(0.62, 0.12, 0.08), (0.75, 0.55, 0.3), (0.18, 0.16, 0.32), (0.62, 0.12, 0.08), (0.85, 0.75, 0.55)],
    [(0.2, 0.22, 0.4), (0.72, 0.5, 0.22), (0.55, 0.1, 0.1), (0.8, 0.72, 0.55), (0.2, 0.22, 0.4)],
    [(0.55, 0.32, 0.14), (0.85, 0.72, 0.48), (0.22, 0.38, 0.36), (0.55, 0.32, 0.14)],
]


def rug_flat(g, rng, c, w, l, yaw, palette, lift=0.015):
    """A rug thrown on the ground, rucked a little."""
    c = Vector(c)
    rq = quat_y(yaw)
    grid = []
    ni, nj = 8, 5
    for i in range(ni):
        row = []
        for j in range(nj):
            u, v = i / (ni - 1), j / (nj - 1)
            ruck = 0.04 * max(0.0, math.sin(u * 7.0 + 1.0)) * math.sin(math.pi * v) * rng.uniform(0.5, 1.0)
            row.append(tuple(c + rq @ V((v - 0.5) * w, lift + ruck, (u - 0.5) * l)))
        grid.append(row)
    sheet(g, grid, M_CLOTH, striped(palette, 9, rng.uniform(0, 3)), tile=0.5, double=True)


def rug_roll(g, rng, a, b, r, palette):
    a, b = Vector(a), Vector(b)
    pal = palette
    tube(g, [a, a.lerp(b, 0.5) + V(0, 0.01, 0), b], [r, r * 1.03, r], 10, M_CLOTH, pal[0], tile=0.4,
         col_fn=lambda t: scale(pal[int(t * 6) % len(pal)], 0.9))
    for t in (0.22, 0.78):
        lashing(g, a.lerp(b, t), b - a, r + 0.012, rng, turns=2)


def bale(g, rng, c, size, yaw, col=(0.78, 0.68, 0.5)):
    """A wrapped trade bale (cloth over a hard core) with rope crossings."""
    c = Vector(c)
    rq = quat_y(yaw)
    nz = Noise(rng, 3, 3.0)
    slab(g, tuple(c), size, rq, rng, mat=M_CLOTH, res=(4, 3, 3), round_r=0.08, rough=0.03, tile=0.5,
         col_fn=lambda p, n: scale(col, 0.85 + 0.12 * nz(p * 5) - 0.12 * (1 - smoothstep(-0.2, 0.3, p.y - c.y))))
    hx, hy, hz = size[0] / 2 + 0.012, size[1] / 2 + 0.012, size[2] / 2 + 0.012
    for along in (-0.25, 0.25):
        ring = [c + rq @ V(along * size[0], y, z) for y, z in ((-hy, -hz), (hy, -hz), (hy, hz), (-hy, hz), (-hy, -hz))]
        tube(g, ring, [0.011] * 5, 4, M_CLOTH, ROPE, tile=0.2, cap=False)
    ring = [c + rq @ V(x, y, 0) for x, y in ((-hx, -hy), (-hx, hy), (hx, hy), (hx, -hy), (-hx, -hy))]
    tube(g, ring, [0.011] * 5, 4, M_CLOTH, ROPE, tile=0.2, cap=False)


def wicker_trap(g, rng, c, d, L=0.9, r=0.22):
    """A conical eel/fish trap of withies: hoops + staves."""
    c, d = Vector(c), Vector(d).normalized()
    side = d.cross(V(0, 1, 0)).normalized()
    up = side.cross(d).normalized()
    for k in range(4):
        t = k / 3
        rr = r * (1 - 0.75 * t) + 0.02
        o = c + d * L * t
        ring = [o + (side * math.cos(a) + up * math.sin(a)) * rr for a in np.linspace(0, 2 * math.pi, 11)]
        tube(g, ring, [0.012] * 11, 4, M_BARK, (0.75, 0.66, 0.5), tile=0.3, cap=False)
    for s in range(9):
        a = s / 9 * 2 * math.pi
        dd = side * math.cos(a) + up * math.sin(a)
        tube(g, [c + dd * (r + 0.02), c + d * L + dd * (r * 0.25 + 0.02), c + d * (L + 0.12)], [0.008] * 3, 4, M_BARK,
             (0.7, 0.62, 0.46), tile=0.3, cap=False)


# ─────────────────────────────────────────────────────────────── FOREST: the ritual ground
def totem(g, rng, base, h, yaw, beast="elk"):
    """A carved, ochre-banded totem: stacked faces with brows, sockets and tusks, a beast skull on top,
    hide strips and feathers tied below it, stones packed round the foot."""
    base = Vector(base)
    rq = quat_y(yaw)
    w = 0.34

    def col(t):
        y = t * h
        band = (int(y / 0.42) % 3)
        c = [mix(TIMBER, SOOT, 0.35), mix(TIMBER, OCHRE, 0.55), scale(TIMBER, 0.8)][band]
        return scale(c, 0.6 + 0.4 * smoothstep(0.0, 0.25, t))
    beam(g, [base + V(0, -0.35, 0), base + V(0.02, h * 0.5, 0.0), base + V(0.0, h, 0.02)], w, w * 0.9,
         up=tuple(rq @ V(0, 0, 1)), mat=M_PLANK, col_fn=col, rng=rng, rough=0.06, chamfer=0.3)
    fwd = rq @ V(0, 0, 1)
    side = rq @ V(1, 0, 0)
    n_faces = int(h / 0.85)
    for k in range(n_faces):
        y = 0.55 + k * 0.85
        fc = base + V(0, y, 0) + fwd * (w * 0.45)
        # Brow ridge, nose, jaw with tusks.
        lbox(g, fc + V(0, 0.18, 0.02) + fwd * 0.03, (w * 1.05, 0.08, 0.1), rq, M_PLANK, scale(TIMBER, 0.7), tile=0.4)
        lbox(g, fc + V(0, 0.05, 0) + fwd * 0.05, (0.07, 0.14, 0.08), rq @ quat_x(-0.15), M_PLANK, scale(TIMBER, 0.75),
             tile=0.4)
        for sx in (-1, 1):
            stone(g, tuple(fc + side * sx * 0.085 + V(0, 0.1, 0) + fwd * 0.01), (0.045, 0.035, 0.03), rng, mat=M_STONE,
                  detail=0, col_fn=lambda p, n: SOOT, tile=0.3, cuts=0)
            tusk_b = fc + side * sx * 0.09 + V(0, -0.12, 0) + fwd * 0.04
            tube(g, [tusk_b, tusk_b + fwd * 0.05 + V(0, 0.06, 0), tusk_b + fwd * 0.06 + side * sx * 0.02 + V(0, 0.14, 0)],
                 [0.022, 0.015, 0.003], 5, M_STONE, BONE, tile=0.2)
        lbox(g, fc + V(0, -0.16, 0) + fwd * 0.02, (w * 0.95, 0.07, 0.08), rq, M_PLANK, mix(TIMBER, OCHRE, 0.7), tile=0.4)
    top = base + V(0, h, 0)
    skull(g, top + V(0, 0.02, 0) + fwd * 0.04, 2.1, rng, horns=0.0 if beast == "elk" else 1.0, yaw=yaw)
    if beast == "elk":
        antlers(g, top + V(0, 0.18, 0), 1.25, rng, yaw=yaw)
    lashing(g, top - V(0, 0.18, 0), (0, 1, 0), w * 0.62, rng, turns=3)
    for k in range(6):
        a = k / 6 * 2 * math.pi + rng.uniform(0, 0.4)
        p = top - V(0, 0.2, 0) + V(math.cos(a), 0, math.sin(a)) * w * 0.6
        if k % 2:
            feather(g, p, rng)
        else:
            bot = cord(g, p, rng.uniform(0.35, 0.6), rng, col=DARK_HIDE, r=0.014)
            stone(g, tuple(bot), (0.02, 0.035, 0.02), rng, mat=M_STONE, detail=0, col_fn=lambda q, n: OLD_BONE, cuts=0)
    for k in range(7):
        a = k / 7 * 2 * math.pi
        r = rng.uniform(0.09, 0.15)
        stone(g, tuple(base + V(math.cos(a) * 0.32, r * 0.3, math.sin(a) * 0.32)), (r, r * 0.7, r), rng, detail=1,
              col_fn=rock_col((0.8, 0.78, 0.72), moss=0.5, ground=base.y), tile=0.4)


def charm_tree(g, rng, base):
    """A dead oak hung with the shamans' charms: bone bundles, small skulls, feathers, stone discs."""
    base = Vector(base)
    col_fn = lambda t: mix((0.5, 0.46, 0.42), (0.78, 0.74, 0.7), t)
    trunk = [base + V(0, -0.3, 0), base + V(0.05, 1.2, 0.02), base + V(0.18, 2.4, -0.06), base + V(0.12, 3.4, 0.0)]
    tube(g, trunk, [0.32, 0.25, 0.19, 0.08], 10, M_BARK, (0.7, 0.66, 0.6), tile=1.0, col_fn=col_fn)
    # Root flare.
    for k in range(5):
        a = k / 5 * 2 * math.pi + 0.3
        d = V(math.cos(a), 0, math.sin(a))
        tube(g, [base + V(0, 0.35, 0) + d * 0.1, base + d * 0.45 + V(0, 0.05, 0), base + d * 0.75 + V(0, -0.12, 0)],
             [0.14, 0.09, 0.04], 6, M_BARK, (0.55, 0.5, 0.45), tile=0.8)
    limbs = []
    for k, (y, a, L) in enumerate(((1.7, 0.4, 1.7), (2.1, 2.5, 1.5), (2.6, 4.3, 1.4), (2.9, 1.4, 1.1), (2.3, 5.6, 1.2))):
        d = V(math.cos(a), 0, math.sin(a))
        p0 = base + V(0.1, y, 0)
        pts = [p0, p0 + d * L * 0.4 + V(0, 0.35, 0), p0 + d * L * 0.75 + V(0, 0.55, 0), p0 + d * L + V(0, 0.6, 0)]
        tube(g, pts, [0.11, 0.075, 0.045, 0.015], 7, M_BARK, (0.68, 0.64, 0.58), tile=0.8)
        limbs.append(pts)
        # A twig or two.
        q = pts[2]
        tube(g, [q, q + d * 0.3 + V(0, 0.35, 0.1)], [0.025, 0.006], 5, M_BARK, (0.65, 0.6, 0.55), tile=0.5)
    for k, pts in enumerate(limbs):
        for t in (0.35, 0.65, 0.9)[: 2 + k % 2]:
            i = int(t * (len(pts) - 1))
            p = pts[i].lerp(pts[min(i + 1, len(pts) - 1)], t * (len(pts) - 1) - i) - V(0, 0.06, 0)
            bot = cord(g, p, rng.uniform(0.3, 0.75), rng, col=ROPE)
            kind = (k * 3 + int(t * 10)) % 4
            if kind == 0:
                skull(g, bot - V(0, 0.08, 0), 0.7, rng)
            elif kind == 1:
                for j in range(3):
                    a = j * 1.1 + rng.uniform(0, 0.4)
                    bone(g, bot + V(math.cos(a) * 0.04, -0.02, math.sin(a) * 0.04),
                         bot + V(-math.cos(a) * 0.05, -0.24, -math.sin(a) * 0.05), 0.012, rng)
            elif kind == 2:
                disc(g, bot - V(0, 0.06, 0), quat_x(math.pi / 2) @ quat_z(rng.uniform(-0.3, 0.3)), 0.06, 0.02, 10, M_STONE,
                     (0.62, 0.6, 0.56), tile=0.2)
            else:
                for j in range(3):
                    feather(g, bot + V(0, 0.01 * j, 0), rng, col=(0.16, 0.15, 0.14) if j else (0.6, 0.5, 0.4))


def great_drum(g, rng, c):
    """The war-and-ritual drum: a hollowed log on three stakes, rawhide head laced down the shell."""
    c = Vector(c)
    y0, y1 = 0.3, 1.05
    frustum(g, 0.5, 0.56, y0, y1 - y0, 18, M_BARK, (0.55, 0.42, 0.32), tile=1.0, centre=tuple(c), segs=3,
            col_fn=lambda t: mix((0.3, 0.24, 0.2), (0.62, 0.5, 0.38), t))
    frustum(g, 0.44, 0.44, y0 + 0.05, y1 - y0 - 0.05, 18, M_BARK, (0.15, 0.12, 0.1), tile=1.0, centre=tuple(c))
    # Head: a slightly domed hide, pale where the hands strike.
    dome(g, c + V(0, y1 - 0.02, 0), 0.6, quat_y(0), M_HIDE,
         lambda p, n: mix((0.95, 0.84, 0.66), (0.62, 0.5, 0.38), smoothstep(0.1, 0.55, math.hypot(p.x - c.x, p.z - c.z))),
         tile=0.5, rings=4, seg=18, squash=0.06)
    tube(g, [c + V(math.cos(a) * 0.6, y1 - 0.04, math.sin(a) * 0.6) for a in np.linspace(0, 2 * math.pi, 19)],
         [0.025] * 19, 5, M_HIDE, RAWHIDE, tile=0.3, cap=False)
    # Zig-zag lacing down to a rawhide band.
    n = 12
    for k in range(n):
        a0 = k / n * 2 * math.pi
        a1 = (k + 0.5) / n * 2 * math.pi
        p0 = c + V(math.cos(a0) * 0.6, y1 - 0.05, math.sin(a0) * 0.6)
        p1 = c + V(math.cos(a1) * 0.545, y0 + 0.25, math.sin(a1) * 0.545)
        p2 = c + V(math.cos(a0 + 2 * math.pi / n) * 0.6, y1 - 0.05, math.sin(a0 + 2 * math.pi / n) * 0.6)
        tube(g, [p0, p1, p2], [0.009] * 3, 4, M_HIDE, RAWHIDE, tile=0.2, cap=False)
    tube(g, [c + V(math.cos(a) * 0.55, y0 + 0.24, math.sin(a) * 0.55) for a in np.linspace(0, 2 * math.pi, 19)],
         [0.022] * 19, 5, M_HIDE, RAWHIDE, tile=0.3, cap=False)
    for k in range(3):
        a = k / 3 * 2 * math.pi + 0.5
        p = c + V(math.cos(a) * 0.52, 0, math.sin(a) * 0.52)
        pole(g, p + V(0, -0.2, 0), p + V(0, y0 + 0.35, 0), 0.05, 0.04, rng, col=(0.7, 0.62, 0.52), sides=6)
    # Two beaters with hide-wrapped knobs resting on the head.
    for sx in (-1, 1):
        a = c + V(sx * 0.12, y1 + 0.03, -0.35)
        b = c + V(sx * 0.2, y1 + 0.05, 0.22)
        tube(g, [a, b], [0.018, 0.02], 6, M_PLANK, TIMBER, tile=0.3)
        stone(g, tuple(b + V(0, 0.02, 0.02)), (0.05, 0.045, 0.055), rng, mat=M_HIDE, detail=1,
              col_fn=lambda p, n: DARK_HIDE, cuts=0, tile=0.2)


def hide_hut(g, rng, c, r, door_yaw):
    """A shaman's dome hut: bent withy ribs under overlapping hides, a smoke-blackened crown and a
    hide door flap facing `door_yaw` (+Z rotated)."""
    c = Vector(c)
    nz = Noise(rng, 4, 1.5)
    rq = quat_y(door_yaw)
    door = rq @ V(0, 0, 1)

    def col(p, n):
        y = (p.y - c.y) / (r * 0.8)
        k = 0.82 + 0.16 * nz(p * 2.5)
        seam = 0.82 if (int((math.atan2(p.z - c.z, p.x - c.x) + 3.2) * 2.6) % 2) else 1.0
        soot = smoothstep(0.75, 1.0, y) * 0.75
        return mix(scale(HIDE, k * seam * (0.75 + 0.25 * smoothstep(0.0, 0.3, y))), SOOT, soot)
    dome(g, c + V(0, -0.05, 0), r, quat_y(rng.uniform(0, 6)), M_HIDE, col, tile=0.9, rings=6, seg=20, squash=0.8)
    for k in range(5):
        a = k / 5 * math.pi + 0.3
        d = quat_y(door_yaw) @ V(math.cos(a), 0, math.sin(a))
        pts = [c - d * (r + 0.03) + V(0, -0.1, 0)]
        for t in np.linspace(0.15, 0.85, 5):
            ang = math.pi * t
            pts.append(c + d * (-math.cos(ang) * (r + 0.03)) + V(0, math.sin(ang) * (r * 0.8 + 0.03), 0))
        pts.append(c + d * (r + 0.03) + V(0, -0.1, 0))
        tube(g, pts, [0.03] * len(pts), 5, M_BARK, (0.62, 0.56, 0.48), tile=0.6, cap=False)
    # Door: a dark opening + a hide flap tied half back.
    dp = c + door * (r * 0.93)
    sheet(g, [[tuple(dp + rq @ V(-0.32, y, 0.02 + 0.04 * math.sin(y * 2))), tuple(dp + rq @ V(0.32, y, 0.02))]
              for y in np.linspace(0.0, 0.95, 4)], M_HIDE, lambda u, v: (0.07, 0.06, 0.05), tile=0.5, double=True)
    sheet(g, [[tuple(dp + rq @ V(0.1 + 0.25 * u, y, 0.08 + 0.05 * u)) for u in (0.0, 1.0)]
              for y in np.linspace(0.0, 1.05, 5)], M_HIDE, lambda u, v: scale(DARK_HIDE, 0.9 + 0.2 * v), tile=0.5,
          double=True)
    # A rock or two holding the hide hem down.
    for k in range(7):
        a = rng.uniform(0, 6.28)
        d = V(math.cos(a), 0, math.sin(a))
        if d.dot(door) > 0.6:
            continue
        s = rng.uniform(0.08, 0.14)
        stone(g, tuple(c + d * (r + 0.05) + V(0, s * 0.3, 0)), (s, s * 0.7, s), rng, detail=1,
              col_fn=rock_col((0.78, 0.76, 0.7), moss=0.4), tile=0.4)


def camp_shaman(rng):
    b = Builder()
    g = G(b)
    ground_patch(g, rng, (0, 0, 0), 3.6, 3.4, (0.55, 0.47, 0.4))
    ground_patch(g, rng, (0, 0.01, 0), 1.4, 1.4, (0.3, 0.27, 0.25), h=0.03)  # the ash-trodden dancing floor
    firepit(g, rng, (0, 0, 0), r=0.52, n=11)
    # The bone circle (r 2.5): upright long bones and ribs, beast skulls on flat stones between them.
    n = 16
    for k in range(n):
        a = k / n * 2 * math.pi + 0.1
        d = V(math.cos(a), 0, math.sin(a))
        p = d * 2.5
        if k % 2 == 0:
            h = rng.uniform(0.5, 0.8)
            top = p + d * 0.12 + V(0, h, 0)
            bone(g, p + V(0, -0.15, 0), top, 0.03, rng, col=scale(BONE, rng.uniform(0.85, 1.0)))
            if k % 4 == 0:
                lashing(g, top - V(0, 0.15, 0), (0, 1, 0), 0.045, rng, turns=2)
                feather(g, top - V(0, 0.15, 0), rng)
        else:
            slab(g, tuple(p + V(0, 0.04, 0)), (0.36, 0.1, 0.3), quat_y(-a), rng, res=(2, 1, 2), round_r=0.03,
                 col_fn=rock_col((0.8, 0.78, 0.72), moss=0.5), tile=0.5)
            skull(g, p + V(0, 0.12, 0), 1.4, rng, horns=1.0 if k % 4 == 1 else 0.0, yaw=-a - math.pi / 2)
    # An inner ring of white pebbles and bone splinters.
    for k in range(30):
        a = k / 30 * 2 * math.pi + rng.uniform(-0.05, 0.05)
        s = rng.uniform(0.03, 0.06)
        stone(g, (math.cos(a) * 2.12, s * 0.2, math.sin(a) * 2.12), (s, s * 0.6, s * 0.8), rng, mat=M_STONE, detail=0,
              col_fn=lambda p, nn: OLD_BONE, tile=0.2, cuts=1)
    # Ochre handprints / smears on the ground stones are too small to read; the totems carry the colour.
    totem(g, rng, (-3.3, 0, -1.9), 3.1, 0.95, beast="elk")
    totem(g, rng, (3.2, 0, -2.2), 2.6, -1.0, beast="ox")
    totem(g, rng, (0.4, 0, 3.75), 2.2, math.pi, beast="ox")
    charm_tree(g, rng, V(-3.7, 0, 2.5))
    great_drum(g, rng, V(2.45, 0, 1.75))
    hide_hut(g, rng, V(-0.5, 0, -4.3), 1.5, 0.0)
    # The offering slab: a capstone on two stones, bowls of blood and ash, a skull, a fan of bones.
    alt = V(1.75, 0, -3.5)
    for sx in (-1, 1):
        stone(g, tuple(alt + V(sx * 0.42, 0.18, 0)), (0.2, 0.26, 0.24), rng, detail=1,
              col_fn=rock_col((0.75, 0.73, 0.68), moss=0.5), tile=0.5)
    slab(g, tuple(alt + V(0, 0.48, 0)), (1.35, 0.16, 0.7), quat_y(0.15), rng, res=(5, 1, 3), round_r=0.04, rough=0.04,
         col_fn=lambda p, nn: mix(rock_col((0.78, 0.76, 0.7), moss=0.3)(p, nn), (0.32, 0.06, 0.04),
                                  0.6 * smoothstep(0.3, 0.0, abs(p.x - alt.x - 0.1)) * smoothstep(0.5, 0.9, nn.y)),
         tile=0.6)
    for k, dx in enumerate((-0.4, 0.42)):
        bc = alt + V(dx, 0.56, 0.05)
        frustum(g, 0.09, 0.13, 0.0, 0.08, 10, M_PLANK, (0.55, 0.42, 0.3), tile=0.3, centre=tuple(bc))
        disc(g, bc + V(0, 0.065, 0), quat_y(0), 0.11, 0.01, 10, M_EARTH, (0.2, 0.03, 0.02) if k == 0 else (0.25, 0.24, 0.23),
             tile=0.2)
    skull(g, alt + V(0.05, 0.6, -0.1), 1.6, rng, horns=1.2, yaw=0.15)
    for k in range(4):
        a = -0.6 + k * 0.4
        bone(g, alt + V(0.0, 0.58, 0.18), alt + V(math.sin(a) * 0.45, 0.58, 0.18 + math.cos(a) * 0.2), 0.016, rng)
    # Banner staff (the faction flag hangs from (-2.0, 2.5, -3.2)): a crooked staff with a skull crown.
    sb = V(-2.0, 0, -3.2)
    pole(g, sb + V(0, -0.3, 0), sb + V(0.04, 3.0, 0.02), 0.055, 0.04, rng, col=(0.7, 0.62, 0.55), sides=7)
    skull(g, sb + V(0.04, 3.03, 0.02), 1.1, rng, horns=0.9)
    # Seats: logs dragged round the circle's outside, a hide thrown over one.
    for a, L in ((0.75, 1.1), (2.1, 1.0), (4.0, 1.2)):
        d = V(math.cos(a), 0, math.sin(a))
        t = V(-d.z, 0, d.x)
        c = d * 3.05 + V(0, 0.14, 0)
        pole(g, c - t * L / 2, c + t * L / 2, 0.17, 0.15, rng, col=(0.75, 0.68, 0.6), sides=9, segs=2)
    # Scattered offerings: antler, bone shards, a cold ember bowl.
    antlers(g, V(-1.6, 0.0, 2.95), 0.9, rng, yaw=0.4)
    for k in range(10):
        p = V(rng.uniform(-3.2, 3.2), 0.01, rng.uniform(-3.0, 3.0))
        if p.length < 2.7:
            continue
        bone(g, p, p + V(rng.uniform(-0.2, 0.2), 0.02, rng.uniform(-0.2, 0.2)), 0.013, rng, col=OLD_BONE)
    return b


# ─────────────────────────────────────────────────────────────── DESERT: raiders in the caravanserai
SAND = (1.06, 0.86, 0.62)
SANDSTONE = (1.02, 0.84, 0.64)


def dressed_wall(g, rng, p0, p1, top, depth=0.55):
    """A ruined sandstone wall of squared courses from p0 to p1 (XZ), ragged crown `top(t)`, a few blocks
    fallen out; wind-scoured, darker at the foot."""
    p0, p1 = Vector(p0), Vector(p1)
    L = (p1 - p0).length
    d = (p1 - p0).normalized()
    yaw = math.atan2(d.x, d.z) - math.pi / 2
    rq = quat_y(yaw)
    nrm = V(-d.z, 0, d.x)
    nz = Noise(rng, 4, 2.0)
    y, ci = -0.12, 0
    peak = max(top(t / 20) for t in range(21))
    while y < peak:
        h = rng.uniform(0.26, 0.34)
        pos = -(rng.uniform(0.2, 0.35) if ci % 2 else rng.uniform(0.0, 0.08))
        while pos < L - 0.05:
            ln = rng.uniform(0.45, 0.7)
            s0, s1 = max(pos, 0.0), min(pos + ln, L)
            pos += ln
            if s1 - s0 < 0.18:
                continue
            mid = (s0 + s1) / 2
            if y + h * 0.5 > top(mid / L) or (y > 0.4 and rng.random() < 0.06):
                continue
            c = p0 + d * mid + V(0, y + h / 2, 0) + nrm * rng.uniform(-0.03, 0.03)
            tint = scale(SANDSTONE, rng.uniform(0.86, 1.04))

            def col(p, n, tint=tint):
                k = 0.7 + 0.3 * smoothstep(-0.1, 0.6, p.y)
                return scale(tint, k * (0.92 + 0.1 * nz(p * 3.0)))
            slab(g, tuple(c), (s1 - s0 - 0.025, h - 0.02, depth * rng.uniform(0.92, 1.0)),
                 rq @ quat_y(rng.uniform(-0.03, 0.03)), rng, mat=M_ASHLAR, res=(2, 1, 1), round_r=0.05, rough=0.05,
                 cuts=int(rng.integers(0, 2)), col_fn=col, tile=1.2)
        y += h
        ci += 1


def sand_drift(g, rng, c, rx, rz, h):
    nz = Noise(rng, 3, 1.5)
    mound(g, tuple(c), rx, rz, h, rng, mat=M_EARTH, col_fn=lambda p, n: scale(SAND, 0.9 + 0.1 * nz(p * 2) + 0.05 * n.y),
          tile=1.2, rings=5, seg=18, skirt=0.15, rough=0.15, edge=0.25, power=1.2)


def camp_raiders(rng):
    b = Builder()
    g = G(b)
    ground_patch(g, rng, (0, 0, -0.5), 4.6, 4.2, (0.9, 0.74, 0.55), h=0.03)
    # The caravanserai: back wall with the iwan arch, the west range, a stub of the east range.
    bw = -4.6
    dressed_wall(g, rng, (-5.3, 0, bw), (-1.55, 0, bw), lambda t: 0.9 + 1.6 * smoothstep(0.0, 0.7, t) - 0.3 * math.sin(t * 9))
    dressed_wall(g, rng, (1.55, 0, bw), (4.7, 0, bw), lambda t: 2.5 - 1.3 * smoothstep(0.4, 1.0, t) + 0.2 * math.sin(t * 7))
    dressed_wall(g, rng, (-5.3, 0, bw + 0.3), (-5.3, 0, 2.2), lambda t: 1.9 - 1.5 * smoothstep(0.3, 1.0, t))
    dressed_wall(g, rng, (4.7, 0, bw + 0.3), (4.7, 0, -2.2), lambda t: 1.4 - 0.7 * t)
    # Iwan: two piers, a pointed arch of voussoirs, a band of glazed turquoise tiles (half fallen).
    for sx in (-1, 1):
        slab(g, (sx * 1.25, 1.35, bw), (0.6, 2.9, 0.7), quat_y(0), rng, mat=M_ASHLAR, res=(2, 6, 2), round_r=0.04,
             rough=0.03, col_fn=lambda p, n: scale(SANDSTONE, 0.75 + 0.25 * smoothstep(-0.1, 1.0, p.y)), tile=1.2)
    nv = 11
    for k in range(nv):
        t0, t1 = k / nv, (k + 1) / nv
        ang0 = math.pi * (1 - t0)
        ang1 = math.pi * (1 - t1)
        q0 = V(math.cos(ang0) * 0.98, 2.78 + math.sin(ang0) * 0.95 * (1 + 0.25 * (1 - abs(math.cos(ang0)))), bw)
        q1 = V(math.cos(ang1) * 0.98, 2.78 + math.sin(ang1) * 0.95 * (1 + 0.25 * (1 - abs(math.cos(ang1)))), bw)
        if k == 7:
            continue  # a voussoir has dropped out — the arch still stands, just
        mid = (q0 + q1) / 2
        dirv = (q1 - q0).normalized()
        out = (mid - V(0, 2.78, bw)).normalized()
        yaw_r = quat_z(math.atan2(dirv.y, dirv.x))
        slab(g, tuple(mid + out * 0.16), ((q1 - q0).length + 0.03, 0.36, 0.66), yaw_r, rng, mat=M_ASHLAR, res=(1, 1, 1),
             round_r=0.04, rough=0.04, col_fn=lambda p, n: scale(SANDSTONE, 0.95), tile=1.2)
        if k % 2 == 0 or k in (3,):
            tc = mid + out * 0.42 + V(0, 0, 0.33)
            lbox(g, tc, (0.16, 0.16, 0.025), yaw_r, M_PLASTER,
                 mix((0.2, 0.55, 0.58), (0.9, 0.85, 0.7), 0.15 + 0.25 * rng.random()), tile=0.3)
    # Spandrel blocks either side of the arch up to the wall crown.
    for sx in (-1, 1):
        slab(g, (sx * 1.25, 3.25, bw), (0.65, 0.7, 0.66), quat_y(0), rng, mat=M_ASHLAR, res=(2, 2, 1), round_r=0.04,
             rough=0.05, col_fn=lambda p, n: scale(SANDSTONE, 0.92), tile=1.2)
    # Fallen blocks and tile shards under the arch, sand drifted into every corner.
    for k in range(9):
        p = V(rng.uniform(-1.5, 1.5) + (2.6 if k > 5 else 0) * (1 if k % 2 else -1), 0.12, bw + rng.uniform(0.4, 1.0))
        slab(g, tuple(p), (rng.uniform(0.35, 0.6), rng.uniform(0.22, 0.32), rng.uniform(0.3, 0.5)),
             quat_y(rng.uniform(0, 3)) @ quat_x(rng.uniform(-0.3, 0.3)), rng, mat=M_ASHLAR, res=(1, 1, 1), round_r=0.05,
             rough=0.06, cuts=1, col_fn=lambda q, n: scale(SANDSTONE, 0.85), tile=1.2)
    for k in range(6):
        lbox(g, V(rng.uniform(-1, 1), 0.02, bw + rng.uniform(0.6, 1.4)), (0.12, 0.02, 0.1), quat_y(rng.uniform(0, 3)),
             M_PLASTER, (0.22, 0.55, 0.56), tile=0.3)
    sand_drift(g, rng, (-4.7, 0, bw + 0.8), 1.3, 1.0, 0.55)
    sand_drift(g, rng, (4.2, 0, bw + 0.7), 1.0, 0.9, 0.4)
    sand_drift(g, rng, (-5.0, 0, 1.8), 0.9, 1.5, 0.45)
    sand_drift(g, rng, (0.0, 0, bw - 0.9), 2.4, 0.8, 0.5)
    # The awning: a stolen rug stretched from the wall crown to two spears, over the loot.
    for sx in (-1, 1):
        pole(g, V(sx * 1.9, -0.2, -2.0), V(sx * 1.85, 2.05, -2.0), 0.035, 0.03, rng, col=(0.7, 0.6, 0.48), sides=6)
        tube(g, [V(sx * 1.85, 2.0, -2.0), V(sx * 2.4, 1.0, -1.2), V(sx * 2.7, 0.03, -0.7)], [0.01] * 3, 4, M_CLOTH, ROPE,
             tile=0.2, cap=False)
    grid = []
    for i in range(8):
        u = i / 7
        row = []
        for j in range(6):
            v = j / 5
            x = (v - 0.5) * 3.9
            z = bw + 0.35 + u * (2.6 - 0.35 + 0.0)
            y = 2.25 - 0.2 * u - 0.22 * math.sin(math.pi * u) * (0.6 + 0.4 * math.sin(math.pi * v))
            row.append((x, y, z))
        grid.append(row)
    sheet(g, grid, M_CLOTH, striped(RUG_PALETTES[0], 11), tile=0.6, double=True)
    # Loot of the Pasha's caravans under it: rolled rugs, bales, jars, a brass tray, an opened chest.
    for k in range(5):
        y = 0.16 + (0.3 if k >= 3 else 0.0)
        x0 = -1.7 + (k % 3) * 0.32 + (0.15 if k >= 3 else 0.0)
        rug_roll(g, rng, V(x0, y, -4.15), V(x0 + 0.08, y, -2.75), 0.15, RUG_PALETTES[k % 3])
    for k, (x, z, s) in enumerate(((0.4, -3.7, 1.0), (1.1, -3.6, 0.9), (0.75, -3.65, 0.85))):
        y = 0.28 if k < 2 else 0.78
        bale(g, rng, V(x, y, z), (0.7 * s, 0.55 * s, 0.6 * s), rng.uniform(-0.2, 0.2))
    for k, (x, z, h) in enumerate(((1.65, -3.4, 0.75), (1.95, -3.1, 0.6), (1.6, -2.85, 0.5), (-0.35, -2.7, 0.65))):
        jar(g, rng, V(x, -0.03, z), h, h * 0.42)
    jar(g, rng, V(0.6, 0.18, -2.25), 0.6, 0.25, tilt=quat_z(1.45) @ quat_y(0.4))  # spilled
    jar(g, rng, V(-0.9, 0.0, -1.6), 0.55, 0.24, broken=True)
    for k in range(5):
        lbox(g, V(-0.9 + rng.uniform(-0.4, 0.4), 0.02, -1.6 + rng.uniform(-0.4, 0.4)), (0.12, 0.02, 0.09),
             quat_y(rng.uniform(0, 3)) @ quat_x(rng.uniform(-0.3, 0.3)), M_PLASTER, (0.95, 0.62, 0.42), tile=0.3)
    disc(g, V(-0.2, 0.05, -2.3), quat_x(0.12), 0.3, 0.025, 20, M_IRON, (1.25, 0.95, 0.5), tile=0.3)  # brass tray
    crate(g, V(2.6, 0.24, -3.4), (0.75, 0.48, 0.5), quat_y(0.3), rng, col=(0.9, 0.72, 0.52))
    # Rugs on the ground round the fire; the raiders' seats are saddle bales.
    rug_flat(g, rng, V(-1.3, 0, 0.9), 1.4, 2.0, 0.4, RUG_PALETTES[1])
    rug_flat(g, rng, V(2.0, 0, 0.0), 1.2, 1.8, -0.7, RUG_PALETTES[2])
    firepit(g, rng, (0.9, 0, 0.7), r=0.42, stone_col=(0.95, 0.8, 0.6))
    # A goat leg on a spit between two forked sticks.
    fc = V(0.9, 0, 0.7)
    for sx in (-1, 1):
        p = fc + V(sx * 0.62, -0.15, 0)
        tube(g, [p, p + V(0, 0.85, 0)], [0.025, 0.02], 5, M_PLANK, TIMBER, tile=0.3)
        tube(g, [p + V(0, 0.68, 0), p + V(sx * 0.06, 0.82, 0.03)], [0.015, 0.008], 4, M_PLANK, TIMBER, tile=0.3)
        tube(g, [p + V(0, 0.68, 0), p + V(-sx * 0.05, 0.84, -0.03)], [0.015, 0.008], 4, M_PLANK, TIMBER, tile=0.3)
    tube(g, [fc + V(-0.8, 0.7, 0), fc + V(0.85, 0.7, 0)], [0.016, 0.016], 5, M_PLANK, scale(TIMBER, 0.6), tile=0.3)
    stone(g, tuple(fc + V(0.05, 0.68, 0)), (0.28, 0.11, 0.12), rng, mat=M_HIDE, detail=1, rough=0.12, cuts=0,
          col_fn=lambda p, n: mix((0.45, 0.2, 0.1), (0.18, 0.09, 0.05), 0.5 + 0.4 * n.y), tile=0.3)
    # Bales dragged up as seats.
    for x, z, yaw in ((-0.4, 1.9, 0.3), (2.2, 1.8, -0.4)):
        bale(g, rng, V(x, 0.22, z), (0.75, 0.45, 0.5), yaw, col=(0.7, 0.58, 0.42))
    # The raiders' standard (flag from (3.0, 2.5, -1.2)): a spear mast with a horse-tail and skulls.
    sb = V(3.0, 0, -1.2)
    pole(g, sb + V(0, -0.3, 0), sb + V(0.03, 3.0, 0.0), 0.045, 0.035, rng, col=(0.6, 0.5, 0.4), sides=7)
    tube(g, [sb + V(0.03, 3.0, 0), sb + V(0.03, 3.35, 0)], [0.025, 0.002], 5, M_IRON, (0.5, 0.48, 0.45), tile=0.2)
    for k in range(5):
        bot = cord(g, sb + V(0.03, 2.95, 0) + V(math.cos(k) * 0.04, 0, math.sin(k) * 0.04), rng.uniform(0.5, 0.75), rng,
                   col=(0.15, 0.12, 0.1), r=0.018)
    skull(g, sb + V(0.03, 2.3, 0.04), 1.1, rng, horns=0.8, yaw=0.0)
    for sx in (-1, 1):
        stone(g, tuple(sb + V(sx * 0.2, 0.08, rng.uniform(-0.1, 0.1))), (0.14, 0.11, 0.13), rng, detail=1,
              col_fn=lambda p, n: scale(SANDSTONE, 0.8), tile=0.4)
    # Tracks of the caravan they took: a broken wheel half under the sand outside the west wall.
    return b


# ─────────────────────────────────────────────────────────────── ROCKY: the cave
LIME = (0.92, 0.9, 0.85)
CAVE_X = 2.65       # half-width of the mouth (inner faces of the side masses)
CAVE_ROOF = 3.0     # underside of the roof slab
CAVE_BACK = -6.6    # back wall face
TALLY_C = V(-2.15, 1.45, -4.35)   # centre of the tally wall
TALLY_YAW = -0.4                 # the wall faces +X turned out toward the mouth (+Z)


def cave_col(nz):
    def f(p, n):
        inside = smoothstep(-2.2, -3.4, p.z) * smoothstep(CAVE_X + 0.6, CAVE_X - 0.6, abs(p.x)) * \
            smoothstep(CAVE_ROOF + 0.6, CAVE_ROOF - 0.4, p.y)
        lip_soot = smoothstep(0.2, -0.8, n.y) * smoothstep(-1.2, -2.6, p.z) * smoothstep(2.4, 3.2, p.y)
        base = rock_col(LIME, moss=0.12, ground=0.0, noise=nz, var=0.16, lichen=(0.6, 0.62, 0.42))(p, n)
        # Pale bedded limestone like the rock range round it (the mass read as a dark boulder).
        k = (1.0 - 0.6 * inside) * 1.32
        streak = 0.92 + 0.08 * nz(V(p.x * 6.0, p.y * 0.6, p.z * 6.0))
        return mix(scale(base, k * streak), SOOT, min(1.0, lip_soot * 0.9 + inside * 0.25))
    return f


def tally_wall(g, rng):
    """The count. A smoothed limestone face just inside the mouth: an OLD column of scratched
    five-bar gates, row after row (hundreds), that breaks off mid-row; beside it a NEW column in
    charcoal, fresh and black. Nothing explains it."""
    rq = quat_y(TALLY_YAW)
    nrm = rq @ V(1, 0, 0)
    along = rq @ V(0, 0, -1)  # u axis on the face (into the cave)
    c = TALLY_C
    nz = Noise(rng, 3, 2.0)
    slab(g, tuple(c - nrm * 0.18), (0.4, 2.6, 2.9), rq, rng, res=(1, 8, 8), round_r=0.12, rough=0.012,
         col_fn=lambda p, n: scale(LIME, 0.62 + 0.08 * nz(p * 3)), tile=1.0)
    face = c + nrm * 0.022

    def stroke(u, v, ang, length, col, w=0.013, depth=0.004):
        p = face + along * u + V(0, v, 0)
        r = rq @ quat_x(ang)
        lbox(g, p + nrm * depth, (depth * 2, length, w), r, M_ROCK, col, tile=0.2)

    def gate(u0, v0, n, col, rng, jitter=0.012):
        for s in range(min(n, 4)):
            stroke(u0 + s * 0.035 + rng.uniform(-jitter, jitter) * 0.4, v0 + rng.uniform(-jitter, jitter),
                   rng.uniform(-0.08, 0.08), 0.1 + rng.uniform(-0.01, 0.01), col)
        if n >= 5:
            stroke(u0 + 0.053, v0, 0.98 + rng.uniform(-0.1, 0.1), 0.15, col)

    # OLD: 13 rows x 5 gates = 325, + a last row of two gates and three strokes = 338 strokes.
    u_l = -1.3
    rows = 13
    for r in range(rows + 1):
        v = 1.12 - r * 0.15
        n_gates = 5 if r < rows else 3
        for k in range(n_gates):
            n = 5 if (r < rows or k < 2) else 3
            fade = rng.uniform(0.0, 0.45) + 0.25 * (r < 4)
            col = mix((1.45, 1.42, 1.34), scale(LIME, 0.62), fade)
            gate(u_l + k * 0.21, v, n, col, rng)
    # NEW, in charcoal: a narrower column beside it — three full rows and a fourth begun.
    u_n = u_l + 5 * 0.21 + 0.16
    for r in range(4):
        v = 1.12 - r * 0.16
        for k in range(2 if r < 3 else 1):
            n = 5 if r < 3 else 4
            gate(u_n + k * 0.22, v, n, (0.025, 0.022, 0.02), rng, jitter=0.02)
    # A charcoal smear where the stick was tried, and the stick itself on the ledge below.
    lbox(g, face + along * (u_n + 0.5) + V(0, 1.1, 0) + nrm * 0.003, (0.004, 0.06, 0.12), rq @ quat_x(0.4), M_ROCK,
         (0.08, 0.075, 0.07), tile=0.2)
    sp = c + nrm * 0.25 + along * (u_n + 0.1) + V(0, -1.33, 0)
    tube(g, [sp, sp + along * 0.16 + V(0.0, 0.01, 0.0)], [0.012, 0.01], 5, M_BARK, (0.05, 0.045, 0.04), tile=0.2)


def camp_cave(rng):
    b = Builder()
    g = G(b)
    nz = Noise(rng, 5, 0.6)
    cf = cave_col(nz)
    # The rock: ONE natural cliff face (the massif's own bedded limestone) with an irregular arch
    # opening, a tunnel narrowing back into darkness, an overhanging brow above the mouth, and a
    # talus fan of fallen blocks at its foot. Beds run level across the face (ledges + recessed
    # partings), vertical joints break it into blocks.
    arch_w, arch_h, face_z = CAVE_X + 0.15, CAVE_ROOF + 0.4, -2.55
    nzf = Noise(rng, 5, 0.7)
    nzj = Noise(rng, 3, 0.35)

    def arch_half(y, d=0.0):
        """Half-width of the opening at height y (d = depth fraction into the tunnel)."""
        s = 1.0 - 0.18 * d
        t = max(0.0, 1.0 - (max(y, 0.0) / (arch_h * s)) ** 2.4)
        wob = 1.0 + 0.1 * math.sin(y * 3.1 + 1.0) + 0.06 * math.sin(y * 7.3)
        return arch_w * s * t ** 0.5 * wob

    def bed(y):
        """Bedding relief: each 0.55u bed juts at its top and is recessed at its parting."""
        f = (y + 0.2) / 0.55 % 1.0
        return 0.12 * smoothstep(0.0, 0.25, f) - 0.1 * smoothstep(0.85, 1.0, f)

    def joint(x):
        """Vertical joints: sharp grooves at irregular spacing."""
        j = 0.0
        for jx in (-5.6, -3.7, 3.6, 5.2, 6.8, -6.9):
            j -= 0.22 * math.exp(-((x - jx - 0.3 * nzj(V(0, x, 0))) / 0.12) ** 2)
        return j

    def face_z_at(x, y):
        z = face_z + bed(y) + joint(x) + 0.28 * nzf(V(x * 0.6, y * 0.25, 0.0))
        z += 0.85 * smoothstep(arch_h - 0.4, arch_h + 0.9, y) * smoothstep(5.5, 1.0, abs(x))  # the brow
        z -= 1.7 * smoothstep(arch_h + 1.2, 8.6, y)   # the face lays back above the brow
        z -= 2.6 * smoothstep(5.8, 8.0, abs(x))       # flanks swing back into the mountain
        return z

    # ONE closed solid (signed distance field -> surface nets), not a face sheet + a tunnel + slabs:
    # the old single-sided sheet left gaps round the mouth (the tunnel ring never met the cut
    # outline) and showed nothing from behind or above, so the sky shone through it, and the
    # rounded slab on top read as a dome glued on. Rock = behind the bedded face, under a top that
    # steps back in ledges and sinks below ground ~12u back (the massif's own slope takes over), out
    # to flanks that swing back into the mountain; minus the tunnel, whose mouth IS the face outline.
    import sdfkit
    h = 0.2
    xs = np.arange(-10.0, 10.0 + 1e-6, h)
    ys = np.arange(-1.2, 9.8 + 1e-6, h)
    zs = np.arange(-16.0, 1.6 + 1e-6, h)
    nzt = Noise(rng, 4, 0.45)
    FZ = np.array([[face_z_at(float(x), float(y)) for y in ys] for x in xs])            # (nx, ny)

    def top_y(x, z):
        ledge = 0.32 * smoothstep(0.6, 0.9, (-z * 0.42 + 0.15 * nzt(V(x * 0.3, 0, z * 0.3))) % 1.0)
        # A broken skyline (big low-frequency lumps + a notch or two), never a straight block edge.
        return (6.1 + 1.1 * nzt(V(x * 0.22, 1.0, z * 0.22)) + 0.45 * nzt(V(x * 0.7, 2.0, z * 0.7))
                - 0.22 * max(0.0, -4.0 - z) - ledge
                - 3.6 * smoothstep(4.5, 9.4, abs(x)) - 9.0 * smoothstep(-5.0, -11.0, z))
    def roof_y(x, z):
        # Never thinner than ~1.3u of rock over the tunnel (its crown is ~3.4u at the mouth).
        cap = 4.8 * smoothstep(5.2, 3.6, abs(x)) * smoothstep(CAVE_BACK - 1.6, CAVE_BACK - 0.6, z)
        return max(top_y(x, z), cap)
    YT = np.array([[roof_y(float(x), float(z)) for z in zs] for x in xs])                # (nx, nz)
    tun_len = face_z - CAVE_BACK
    D = np.clip((face_z - zs) / tun_len, 0.0, 1.0)                                      # (nz,)

    def half_w(y, d):
        sc = 1.0 - 0.18 * d
        crown = arch_h * sc
        if y > crown:
            return -(y - crown)
        # Behind the mouth the cave opens into a wider chamber (the tally wall stands in it).
        return arch_half(y, d) * (1.0 + 0.32 * smoothstep(0.05, 0.4, d))
    AH = np.array([[half_w(float(y), float(d)) for d in D] for y in ys])                # (ny, nz)
    X, Y, Z = np.meshgrid(xs, ys, zs, indexing="ij")
    P = np.stack([X, Y, Z], -1)

    def vnoise(nz_, P, k=1.0):
        out = np.zeros(P.shape[:-1])
        for d_, f_, ph, amp in nz_.w:
            out += amp * np.sin((P @ np.array([d_.x, d_.y, d_.z])) * f_ * k + ph)
        return out / nz_.norm
    rough = 0.16 * vnoise(Noise(rng, 4, 0.9), P)
    f_front = Z - FZ[:, :, None]
    f_top = Y - YT[:, None, :]
    side_n = 0.7 * vnoise(Noise(rng, 3, 0.25), P)
    f_side = np.abs(X) - (9.0 - 0.3 * np.maximum(Y, 0.0) + side_n - 1.2 * np.clip((-Z - 6.0) / 6.0, 0.0, 1.0))
    f_back = -10.2 - Z      # the mass ends (underground) before its top skin thins into flaps
    body = np.maximum(np.maximum(np.maximum(f_front, f_top), f_side), f_back) + rough
    # The tunnel: the arch outline swept back, narrowing; its end rounds into a rough back wall.
    end = CAVE_BACK + 0.25 * vnoise(Noise(rng, 3, 1.2), P)
    tunnel = np.maximum(np.abs(X) - AH[None, :, :], end - Z)
    tunnel = np.maximum(tunnel, -0.45 - Y)            # rock floor just under the camp ground
    F = np.maximum(body, -tunnel)
    verts_np, quads = sdfkit.surface_nets(F, np.array([xs[0], ys[0], zs[0]]), h)
    verts = [V(float(a_), float(b_), float(c_)) for a_, b_, c_ in verts_np]
    tris = []
    for q in quads:
        tris += [(int(q[0]), int(q[1]), int(q[2])), (int(q[0]), int(q[2]), int(q[3]))]
    smooth_mesh(g, verts, tris, M_ROCK, cf, 2.2)
    # Talus fan: blocks fallen from the beds, then rubble and gravel spreading out from the foot.
    tal = lambda p, n: scale(rock_col(LIME, moss=0.25, noise=nz, var=0.2)(p, n), 0.95)
    for k in range(7):
        sx = -1 if k % 2 else 1
        p = V(sx * rng.uniform(2.9, 6.0), 0.0, rng.uniform(-2.3, -0.8))
        s = rng.uniform(0.35, 0.8)
        slab(g, (p.x, s * 0.3, p.z), (s * 1.6, s, s * 1.2), quat_y(rng.uniform(0, 3)) @ quat_x(rng.uniform(-0.3, 0.3)), rng,
             res=(2, 2, 2), round_r=0.06, rough=0.06, cuts=2, col_fn=tal, tile=1.0)
    for k in range(70):
        sx = -1 if k % 2 else 1
        r = rng.uniform(0, 1) ** 0.6
        p = V(sx * (2.7 + r * 4.0) + rng.uniform(-0.6, 0.6), 0.0, -2.2 + r * 2.6 * rng.uniform(0.3, 1.0))
        s = rng.uniform(0.06, 0.22) * (1.2 - r * 0.6)
        stone(g, (p.x, s * 0.2, p.z), (s, s * 0.6, s * 0.85), rng, detail=0, rough=0.1, cuts=2, col_fn=tal, tile=0.5)
    for sx in (-1, 1):
        mound(g, (sx * 4.4, 0.0, -1.9), 2.6, 1.4, 0.32, rng, mat=M_ROCK,
              col_fn=lambda p, n: scale(LIME, 0.62 + 0.15 * nz(p * 4)), tile=0.6, rings=4, seg=16, skirt=0.15,
              rough=0.25, edge=0.3, power=1.1)
    # Cave floor: packed dirt and ash, hides for bedding at the back, a bone midden by the left wall.
    ground_patch(g, rng, (0, 0, -4.4), CAVE_X + 0.2, 2.4, (0.42, 0.38, 0.34), h=0.04)
    ground_patch(g, rng, (0.3, 0, -0.6), 3.4, 2.6, (0.6, 0.55, 0.5), h=0.03)
    for k, (x, z, yaw) in enumerate(((-1.2, -5.9, 0.2), (0.2, -6.1, -0.1), (-1.9, -5.0, 1.4))):
        grid = []
        for i in range(5):
            row = []
            for j in range(4):
                u, v = i / 4, j / 3
                row.append(tuple(V(x, 0.05 + 0.04 * math.sin(u * 5 + k) * math.sin(math.pi * v), z) +
                                 quat_y(yaw) @ V((v - 0.5) * 1.0, 0, (u - 0.5) * 1.5)))
            grid.append(row)
        sheet(g, grid, M_HIDE, lambda u, v, k=k: scale([DARK_HIDE, HIDE, (0.32, 0.28, 0.24)][k], 0.85 + 0.2 * v), tile=0.6,
              double=True)
    for k in range(18):
        p = V(-1.6 + rng.uniform(-0.4, 0.5), 0.02, -2.9 + rng.uniform(-0.5, 0.4))
        bone(g, p, p + V(rng.uniform(-0.25, 0.25), rng.uniform(0.0, 0.1), rng.uniform(-0.25, 0.25)), 0.018, rng,
             col=scale(OLD_BONE, rng.uniform(0.7, 1.0)))
    skull(g, V(-1.3, 0.08, -3.2), 1.5, rng, horns=1.0, yaw=0.6)
    tally_wall(g, rng)
    # Weapon rack outside the mouth: a lashed rail with cleavers, spears and a shield.
    wr = V(2.9, 0, -0.9)
    for dz in (-0.7, 0.7):
        pole(g, wr + V(0, -0.2, dz), wr + V(0, 1.25, dz), 0.05, 0.045, rng, col=(0.62, 0.55, 0.47), sides=6)
    tube(g, [wr + V(0, 1.15, -0.85), wr + V(0, 1.15, 0.85)], [0.04, 0.04], 6, M_BARK, (0.62, 0.55, 0.47), tile=0.5)
    for dz in (-0.7, 0.7):
        lashing(g, wr + V(0, 1.15, dz), (0, 0, 1), 0.06, rng)
    for k in range(4):
        dz = -0.5 + k * 0.33
        spear(g, wr + V(0.35, 0.0, dz), wr + V(-0.05, 1.75, dz + 0.05), rng, col=(0.55, 0.47, 0.38))
    for k in range(2):
        cl = wr + V(0.12, 0.0, -0.15 + k * 0.45)
        tube(g, [cl + V(0, 0.0, 0), cl + V(-0.05, 0.6, 0)], [0.025, 0.022], 5, M_PLANK, (0.5, 0.42, 0.34), tile=0.3)
        lbox(g, cl + V(-0.07, 0.8, 0.05), (0.03, 0.42, 0.24), quat_z(0.08), M_IRON, (0.42, 0.38, 0.35), tile=0.3)
    # Skull spikes at the approach — this is the war country.
    for x, z in ((-2.2, 1.9), (2.0, 2.3)):
        top = V(x, 1.25, z)
        tube(g, [V(x, -0.2, z), top, top + V(0, 0.18, 0)], [0.05, 0.04, 0.004], 7, M_BARK, (0.7, 0.64, 0.58), tile=0.6,
             cap=False)
        skull(g, top - V(0, 0.05, 0), 1.35, rng, horns=1.1 if x > 0 else 0.0, yaw=math.pi * 0.0)
        lashing(g, top - V(0, 0.25, 0), (0, 1, 0), 0.05, rng)
    # Fire under the lip (smoke-blackened above), log seats, a cauldron.
    firepit(g, rng, (0.2, 0, -1.0), r=0.48, stone_col=(0.85, 0.83, 0.78))
    for a, L in ((0.3, 1.2), (2.6, 1.0)):
        d = V(math.cos(a), 0, math.sin(a))
        t = V(-d.z, 0, d.x)
        cc = V(0.2, 0.16, -1.0) + d * 1.25
        pole(g, cc - t * L / 2, cc + t * L / 2, 0.18, 0.16, rng, col=(0.7, 0.62, 0.54), sides=9, segs=2)
    frustum(g, 0.24, 0.3, 0.0, 0.34, 14, M_IRON, (0.32, 0.3, 0.28), tile=0.4, centre=(-1.2, 0, -1.6))
    # Banner pole (flag from (-3.1, 2.5, -0.4)).
    sb = V(-3.1, 0, -0.4)
    pole(g, sb + V(0, -0.3, 0), sb + V(0.03, 3.0, 0.02), 0.055, 0.04, rng, col=(0.66, 0.6, 0.52), sides=7)
    skull(g, sb + V(0.03, 3.03, 0.02), 1.15, rng, horns=1.1)
    for k in range(5):
        a = k / 5 * 2 * math.pi
        s = rng.uniform(0.12, 0.2)
        stone(g, tuple(sb + V(math.cos(a) * 0.22, s * 0.3, math.sin(a) * 0.22)), (s, s * 0.7, s), rng, detail=1,
              col_fn=cf, tile=0.5)
    return b


# ─────────────────────────────────────────────────────────────── SWAMP: the cage deck on stilts
DECK_Y = 0.6        # deck top (cages stand on it)
DECK_X = 3.6        # half-width
DECK_Z0, DECK_Z1 = 2.4, 7.2


def camp_stilts(rng):
    b = Builder()
    g = G(b)
    wet = lambda t: mix((0.22, 0.2, 0.17), (0.66, 0.6, 0.52), smoothstep(0.35, 0.6, t))
    # Stilts: 4 x 3 driven posts, foot deep in the bog, cross-braced, lashed.
    xs = [-DECK_X + 0.15, -1.2, 1.2, DECK_X - 0.15]
    zs = [DECK_Z0 + 0.15, (DECK_Z0 + DECK_Z1) / 2, DECK_Z1 - 0.15]
    for x in xs:
        for z in zs:
            top = DECK_Y - 0.12 if not (x == xs[0] or x == xs[-1]) or z == zs[1] else DECK_Y + 0.9
            pole(g, V(x, -2.2, z), V(x + rng.uniform(-0.04, 0.04), top, z + rng.uniform(-0.04, 0.04)), 0.11, 0.09, rng,
                 col=(0.7, 0.64, 0.56), sides=8, col_fn=wet, segs=4)
        for z0, z1 in zip(zs, zs[1:]):
            beam(g, [V(x, -0.5, z0), V(x, DECK_Y - 0.25, z1)], 0.07, 0.07, mat=M_BARK, mode="bark",
                 col=(0.55, 0.5, 0.44), rng=rng)
    # Bearers across the posts, joists along, then the plank deck (gaps, a few short boards).
    for z in zs:
        beam(g, [V(-DECK_X - 0.1, DECK_Y - 0.17, z), V(DECK_X + 0.1, DECK_Y - 0.17, z)], 0.14, 0.12, mat=M_BARK, mode="bark",
             col=(0.62, 0.56, 0.48), rng=rng)
        for x in xs:
            lashing(g, V(x, DECK_Y - 0.17, z), (1, 0, 0), 0.12, rng)
    x = -DECK_X + 0.12
    while x < DECK_X - 0.05:
        w = rng.uniform(0.2, 0.28)
        z0 = DECK_Z0 + (rng.uniform(0, 0.3) if rng.random() < 0.15 else 0.0)
        board(g, V(x + w / 2, DECK_Y - 0.03, (z0 + DECK_Z1) / 2), (0, 0, 1), (0, 1, 0), DECK_Z1 - z0, w - 0.02, 0.06,
              mat=M_PLANK, col=mix((0.72, 0.64, 0.54), (0.42, 0.4, 0.34), rng.uniform(0, 0.5)), rng=rng)
        x += w
    # The gangway from the bank.
    for sx in (-0.28, 0.28):
        beam(g, [V(sx, -0.08, 0.3), V(sx, DECK_Y - 0.03, DECK_Z0 + 0.15)], 0.08, 0.06, mat=M_PLANK, col=TIMBER, rng=rng)
    for k in range(7):
        t = k / 6
        z = 0.45 + t * (DECK_Z0 - 0.45)
        y = -0.02 + t * (DECK_Y + 0.02)
        board(g, V(0, y + 0.03, z), (1, 0, 0), (0, 1, 0), 0.75, 0.2, 0.04, mat=M_PLANK, col=TIMBER, rng=rng)
    # Rope rail along the water edges between the tall corner posts.
    for a, bb in ((V(-DECK_X + 0.15, DECK_Y + 0.8, DECK_Z1 - 0.15), V(DECK_X - 0.15, DECK_Y + 0.8, DECK_Z1 - 0.15)),
                  (V(DECK_X - 0.15, DECK_Y + 0.8, DECK_Z0 + 0.15), V(DECK_X - 0.15, DECK_Y + 0.8, DECK_Z1 - 0.15)),
                  (V(-DECK_X + 0.15, DECK_Y + 0.8, DECK_Z0 + 0.15), V(-DECK_X + 0.15, DECK_Y + 0.8, DECK_Z1 - 0.15))):
        tube(g, [a, a.lerp(bb, 0.5) - V(0, 0.12, 0), bb], [0.014] * 3, 4, M_CLOTH, ROPE, tile=0.2, cap=False)
    # Reed lean-to roof over the back half of the deck (the cages stand in its shade, not under it).
    rz0, rz1 = 5.6, DECK_Z1 + 0.35
    for x in (-DECK_X + 0.15, 0.0, DECK_X - 0.15):
        pole(g, V(x, DECK_Y - 0.1, DECK_Z1 - 0.15), V(x, DECK_Y + 2.0, DECK_Z1 - 0.15), 0.07, 0.06, rng,
             col=(0.66, 0.6, 0.52), sides=7)
        pole(g, V(x, DECK_Y - 0.1, rz0), V(x, DECK_Y + 1.55, rz0), 0.06, 0.055, rng, col=(0.66, 0.6, 0.52), sides=7)
    rq = quat_x(-math.atan2(0.45, rz1 - rz0))
    lbox(g, V(0, DECK_Y + 1.85, (rz0 + rz1) / 2), (2 * DECK_X + 0.6, 0.2, (rz1 - rz0) + 0.5), rq, M_THATCH,
         [(0.5, 0.46, 0.38), None, (0.72, 0.66, 0.52)], tile=1.2, grain=2)
    # Food set out for the captives: bowls of gruel and fish, a water gourd, a ladle in the pot.
    for cx in (-1.6, 1.7):
        for k in range(2):
            bc = V(cx - 0.35 + k * 0.6, DECK_Y, 3.05 + rng.uniform(-0.05, 0.05))
            frustum(g, 0.1, 0.15, 0.0, 0.08, 12, M_PLANK, (0.62, 0.48, 0.34), tile=0.3, centre=tuple(bc))
            disc(g, bc + V(0, 0.065, 0), quat_y(0), 0.13, 0.01, 12, M_EARTH, (0.78, 0.7, 0.55), tile=0.2)
            if k:
                stone(g, tuple(bc + V(0, 0.09, 0)), (0.1, 0.025, 0.03), rng, mat=M_HIDE, detail=1, cuts=0,
                      col_fn=lambda p, n: (0.5, 0.5, 0.46), tile=0.2)
        gourd = V(cx + 0.55, DECK_Y + 0.12, 3.2)
        stone(g, tuple(gourd), (0.1, 0.13, 0.1), rng, mat=M_HIDE, detail=2, cuts=0, rough=0.05,
              col_fn=lambda p, n: (0.66, 0.5, 0.3), tile=0.3)
        tube(g, [gourd + V(0, 0.1, 0), gourd + V(0.01, 0.2, 0)], [0.035, 0.03], 6, M_HIDE, (0.6, 0.45, 0.28), tile=0.2)
    pot = V(0.0, DECK_Y, 2.85)
    frustum(g, 0.17, 0.22, 0.0, 0.28, 14, M_IRON, (0.34, 0.31, 0.28), tile=0.4, centre=tuple(pot))
    disc(g, pot + V(0, 0.25, 0), quat_y(0), 0.19, 0.01, 12, M_EARTH, (0.62, 0.55, 0.4), tile=0.2)
    tube(g, [pot + V(0.05, 0.22, 0), pot + V(0.2, 0.55, 0.05)], [0.012, 0.012], 4, M_PLANK, TIMBER, tile=0.2)
    # The gibbet: an arm off the east corner post, a small empty hanging cage over the water.
    gp = V(DECK_X - 0.15, DECK_Y + 0.9, DECK_Z1 - 0.15)
    pole(g, gp, gp + V(0, 1.6, 0), 0.08, 0.07, rng, col=(0.62, 0.56, 0.48), sides=7)
    arm_end = gp + V(1.5, 1.45, 0.2)
    beam(g, [gp + V(0, 1.45, 0), arm_end], 0.1, 0.1, mat=M_BARK, mode="bark", col=(0.6, 0.55, 0.47), rng=rng)
    beam(g, [gp + V(0, 0.8, 0), gp + V(0.7, 1.42, 0.1)], 0.07, 0.07, mat=M_BARK, mode="bark", col=(0.6, 0.55, 0.47), rng=rng)
    lashing(g, gp + V(0, 1.45, 0), (0, 1, 0), 0.1, rng)
    hc = arm_end + V(0, -1.25, 0)
    tube(g, [arm_end, hc + V(0, 0.75, 0)], [0.015, 0.015], 4, M_IRON, (0.35, 0.3, 0.27), tile=0.2)
    for ring_y in (0.0, 0.7):
        tube(g, [hc + V(math.cos(a) * 0.38, ring_y, math.sin(a) * 0.38) for a in np.linspace(0, 2 * math.pi, 13)],
             [0.025] * 13, 5, M_BARK, (0.55, 0.5, 0.42), tile=0.3, cap=False)
    for k in range(9):
        a = k / 9 * 2 * math.pi
        if k == 3:
            continue  # a bar torn out
        d = V(math.cos(a) * 0.38, 0, math.sin(a) * 0.38)
        tube(g, [hc + d + V(0, -0.05, 0), hc + d + V(0, 0.75, 0)], [0.022, 0.02], 5, M_BARK, (0.55, 0.5, 0.42), tile=0.3)
    for k in range(4):
        tube(g, [hc + V(math.cos(k * 1.57) * 0.38, 0.7, math.sin(k * 1.57) * 0.38), hc + V(0, 0.85, 0)], [0.015] * 2, 4,
             M_BARK, (0.5, 0.45, 0.38), tile=0.3)
    # The bank: smudge fire, a fish-drying rack, the dugout, eel traps, a reed lean-to.
    ground_patch(g, rng, (0, 0, -1.2), 4.2, 3.0, (0.36, 0.32, 0.26), h=0.03)
    firepit(g, rng, (0.6, 0, -1.4), r=0.42, stone_col=(0.6, 0.58, 0.52))
    rk = V(-2.7, 0, -2.0)
    for dz in (-0.8, 0.8):
        for dx in (-0.25, 0.25):
            pole(g, rk + V(dx, -0.2, dz), rk + V(-dx * 0.4, 1.5, dz), 0.04, 0.035, rng, col=(0.66, 0.6, 0.52), sides=6)
    for y in (1.35, 1.0):
        tube(g, [rk + V(0, y, -0.95), rk + V(0, y, 0.95)], [0.03, 0.03], 6, M_BARK, (0.66, 0.6, 0.52), tile=0.4)
        for k in range(7):
            p = rk + V(0, y - 0.02, -0.75 + k * 0.25)
            bot = cord(g, p, 0.06, rng, r=0.006)
            stone(g, tuple(bot + V(0, -0.15, 0)), (0.035, 0.16, 0.055), rng, mat=M_HIDE, detail=1, cuts=0,
                  col_fn=lambda q, n: mix((0.32, 0.3, 0.26), (0.62, 0.55, 0.4), 0.5 + 0.5 * n.x), tile=0.2)
    # Dugout canoe pulled up the bank (bow into the shallows), paddle across it.
    cq = quat_y(0.35)
    cc = V(-3.5, 0.1, 1.1)
    verts, tris = [], []
    L, Wd, H = 3.0, 0.32, 0.3
    seg = 10
    for i in range(seg + 1):
        t = i / seg
        z = (t - 0.5) * L
        taper = math.sin(math.pi * min(max(t, 0.04), 0.96)) ** 0.5
        for j in range(7):
            a = math.pi * j / 6
            x = -math.cos(a) * Wd * taper
            y = -math.sin(a) * H * taper + H * 0.55 + (0.12 * (abs(t - 0.5) * 2) ** 3)
            verts.append(cc + cq @ V(x, y, z))
    for i in range(seg):
        for j in range(6):
            a0, a1 = i * 7 + j, i * 7 + j + 1
            b0, b1 = (i + 1) * 7 + j, (i + 1) * 7 + j + 1
            tris += [(a0, b0, b1), (a0, b1, a1)]
    smooth_mesh(g, verts, tris, M_BARK, lambda p, n: mix((0.22, 0.18, 0.15), (0.55, 0.48, 0.4), smoothstep(-0.5, 0.5, n.y)),
                0.6)
    tube(g, [cc + cq @ V(-0.5, 0.42, -0.4), cc + cq @ V(0.45, 0.4, 0.6)], [0.02, 0.02], 5, M_PLANK, TIMBER, tile=0.3)
    lbox(g, cc + cq @ V(0.55, 0.39, 0.72), (0.14, 0.02, 0.32), cq @ quat_y(0.8), M_PLANK, TIMBER, tile=0.3)
    for k, (x, z, yaw) in enumerate(((2.4, 0.6, 0.4), (2.9, 0.2, 1.3), (2.6, 0.95, 2.6))):
        wicker_trap(g, rng, V(x, 0.22 + (0.32 if k == 2 else 0.0), z), (math.cos(yaw), -0.05, math.sin(yaw)))
    # Reed lean-to on the bank where they sleep.
    lt = V(-3.0, 0, -4.0)
    for dx in (-1.1, 1.1):
        pole(g, lt + V(dx, -0.2, 0.7), lt + V(dx, 1.6, 0.7), 0.05, 0.045, rng, col=(0.62, 0.56, 0.48), sides=6)
    lqr = quat_x(math.atan2(1.6, 1.6))
    lbox(g, lt + V(0, 0.82, -0.05), (2.5, 0.18, 2.3), lqr, M_THATCH, [(0.48, 0.44, 0.36), None, (0.7, 0.64, 0.5)],
         tile=1.2, grain=2)
    for k in range(3):
        grid = [[tuple(lt + V(-0.9 + k * 0.6 + v * 0.55, 0.04 + 0.02 * math.sin(u * 4), -0.2 + u * 0.8)) for v in (0, 1)]
                for u in np.linspace(0, 1, 4)]
        sheet(g, grid, M_HIDE, lambda u, v: DARK_HIDE, tile=0.6, double=True)
    # Banner on the near corner post (flag from (3.45, 2.5, 2.55)).
    pole(g, V(DECK_X - 0.15, DECK_Y + 0.85, DECK_Z0 + 0.15), V(DECK_X - 0.12, 3.05, DECK_Z0 + 0.17), 0.06, 0.045, rng,
         col=(0.66, 0.6, 0.52), sides=7)
    skull(g, V(DECK_X - 0.12, 3.08, DECK_Z0 + 0.17), 1.1, rng, horns=0.9, yaw=math.pi)
    # Reeds / bog-cotton at the stilt feet are the swamp scatter's; mud slicks on the bank.
    for k in range(5):
        ground_patch(g, rng, (rng.uniform(-3, 3), 0.0, rng.uniform(1.0, 2.2)), rng.uniform(0.4, 0.8), rng.uniform(0.3, 0.6),
                     (0.2, 0.18, 0.15), h=0.015)
    return b


# ─────────────────────────────────────────────────────────────── SNOW: the hunters' winter camp
def yurt(g, rng, c, r, door_yaw, wall_h=1.25, crown_h=2.35, pole_top=None):
    """Felt-and-hide yurt: lattice wall under hides with rope girths, conical roof to a crown ring
    with the roof poles poking through, snow on the roof and banked round the wall, a door frame
    with a hide flap toward `door_yaw`."""
    c = Vector(c)
    nz = Noise(rng, 4, 1.4)
    rq = quat_y(door_yaw)
    door = rq @ V(0, 0, 1)

    def wall_col(t):
        return scale(HIDE, 0.6 + 0.35 * t)
    frustum(g, r, r * 1.01, -0.1, wall_h + 0.1, 22, M_HIDE, HIDE, tile=0.9, centre=tuple(c), segs=3, col_fn=wall_col,
            jitter=0.012, rng=rng)
    for y in (0.35, wall_h - 0.12):
        tube(g, [c + V(math.cos(a) * (r + 0.025), y, math.sin(a) * (r + 0.025)) for a in np.linspace(0, 2 * math.pi, 23)],
             [0.016] * 23, 4, M_CLOTH, ROPE, tile=0.2, cap=False)
    # Roof: hides from the wall top to the crown, soot round the smoke hole.
    roof_col = lambda t: mix(scale(DARK_HIDE, 1.1), SOOT, smoothstep(0.7, 1.0, t) * 0.8)
    frustum(g, r * 1.06, 0.3, wall_h - 0.02, crown_h - wall_h, 22, M_HIDE, DARK_HIDE, tile=0.9, centre=tuple(c), segs=4,
            col_fn=roof_col)
    tube(g, [c + V(math.cos(a) * 0.3, crown_h + 0.02, math.sin(a) * 0.3) for a in np.linspace(0, 2 * math.pi, 13)],
         [0.04] * 13, 5, M_PLANK, TIMBER, tile=0.3, cap=False)
    for k in range(10):
        a = k / 10 * 2 * math.pi + 0.15
        d = V(math.cos(a), 0, math.sin(a))
        p0 = c + d * (r * 1.0) + V(0, wall_h + 0.03, 0)
        p1 = c + d * 0.26 + V(0, crown_h + 0.04, 0)
        tube(g, [p1, p1 + (p1 - p0).normalized() * 0.18], [0.025, 0.02], 5, M_BARK, (0.66, 0.6, 0.52), tile=0.3)
    # Snow: a crust on the roof (thinner toward the warm crown), banked against the wall.
    frustum(g, r * 1.0, 0.55, wall_h + 0.06, (crown_h - wall_h) * 0.72, 22, M_SNOW, (0.95, 0.96, 1.0), tile=1.4,
            centre=tuple(c), segs=3, col_fn=lambda t: mix((0.97, 0.98, 1.0), (0.82, 0.84, 0.88), t))
    for k in range(7):
        a = k / 7 * 2 * math.pi + rng.uniform(0, 0.4)
        d = V(math.cos(a), 0, math.sin(a))
        if d.dot(door) > 0.75:
            continue
        drift(g, tuple(c + d * (r + 0.35)), 1.0, 0.55, rng.uniform(0.3, 0.45), rng)
    # Door frame and flap.
    dp = c + door * (r + 0.02)
    side = rq @ V(1, 0, 0)
    for sx in (-1, 1):
        beam(g, [dp + side * sx * 0.38 + V(0, -0.05, 0), dp + side * sx * 0.38 + V(0, 1.1, 0)], 0.08, 0.06,
             up=tuple(door), mat=M_PLANK, col=mix(TIMBER, OCHRE, 0.35), rng=rng)
    beam(g, [dp - side * 0.46 + V(0, 1.12, 0), dp + side * 0.46 + V(0, 1.12, 0)], 0.08, 0.08, up=tuple(door), mat=M_PLANK,
         col=mix(TIMBER, OCHRE, 0.35), rng=rng)
    sheet(g, [[tuple(dp + door * (0.04 + 0.03 * math.sin(y * 3)) + side * (sx * 0.34)) for sx in (-1, 1)]
              for y in np.linspace(1.08, 0.0, 4)], M_HIDE, lambda u, v: scale(DARK_HIDE, 0.75 + 0.2 * u), tile=0.6,
          double=True)
    if pole_top:
        pole(g, c + V(0, crown_h - 0.4, 0), c + V(0.02, pole_top, 0.0), 0.05, 0.04, rng, col=(0.62, 0.56, 0.48), sides=7)
        skull(g, c + V(0.02, pole_top + 0.03, 0), 1.0, rng)
        antlers(g, c + V(0.02, pole_top + 0.12, 0), 0.8, rng)


def stretched_hide(g, rng, c, yaw, w=1.2, h=1.4, col=(0.78, 0.62, 0.44)):
    """A hide laced into a square frame of poles to dry, leaning back on a prop."""
    c = Vector(c)
    rq = quat_y(yaw) @ quat_x(-0.25)
    corners = [c + rq @ V(sx * w / 2, y, 0) for sx, y in ((-1, 0.0), (1, 0.0), (1, h), (-1, h))]
    for a, bb in zip(corners, corners[1:] + corners[:1]):
        e = (bb - a).normalized()
        pole(g, a - e * 0.12, bb + e * 0.12, 0.035, 0.03, rng, col=(0.66, 0.6, 0.52), sides=6)
    nz = Noise(rng, 3, 4.0)
    grid = []
    for i in range(6):
        row = []
        for j in range(6):
            u, v = i / 5, j / 5
            x = (u - 0.5) * (w - 0.25) * (1 - 0.12 * math.sin(math.pi * v))
            y = 0.12 + v * (h - 0.24)
            row.append(tuple(c + rq @ V(x, y, 0.02)))
        grid.append(row)
    sheet(g, grid, M_HIDE, lambda u, v: scale(col, 0.85 + 0.15 * math.sin(u * 7 + v * 3) - 0.15 * smoothstep(0.6, 1.0, abs(u - 0.5) * 2)),
          tile=0.6, double=True)
    for k in range(10):
        t = k / 9
        p_in = c + rq @ V((t - 0.5) * (w - 0.3), 0.14, 0.02)
        tube(g, [p_in, c + rq @ V((t - 0.5) * w, 0.0, 0.0)], [0.006] * 2, 3, M_CLOTH, RAWHIDE, tile=0.2, cap=False)
        p_in = c + rq @ V((t - 0.5) * (w - 0.3), h - 0.14, 0.02)
        tube(g, [p_in, c + rq @ V((t - 0.5) * w, h, 0.0)], [0.006] * 2, 3, M_CLOTH, RAWHIDE, tile=0.2, cap=False)
    prop = c + rq @ V(0, h * 0.8, 0)
    pole(g, prop, c + quat_y(yaw) @ V(0, -0.1, -0.85), 0.03, 0.03, rng, col=(0.66, 0.6, 0.52), sides=6)


def camp_hunters(rng):
    b = Builder()
    g = G(b)
    nzs = Noise(rng, 4, 1.0)
    # Trampled snow + bare earth around the fire.
    mound(g, (0, 0, 0), 3.0, 2.8, 0.03, rng, mat=M_SNOW,
          col_fn=lambda p, n: mix((0.78, 0.8, 0.84), (0.55, 0.52, 0.5), 0.35 + 0.3 * nzs(p * 2.0)), tile=1.6, rings=4, seg=22,
          skirt=0.1, rough=0.3, edge=0.2, power=0.5)
    ground_patch(g, rng, (0, 0.01, 0), 1.1, 1.0, (0.34, 0.3, 0.27), h=0.03)
    firepit(g, rng, (0, 0, 0), r=0.46, stone_col=(0.72, 0.72, 0.74))
    # Cook pot on a tripod over the fire.
    for k in range(3):
        a = k / 3 * 2 * math.pi + 0.3
        tube(g, [V(math.cos(a) * 0.75, -0.1, math.sin(a) * 0.75), V(0, 1.35, 0)], [0.03, 0.022], 5, M_BARK,
             (0.6, 0.55, 0.48), tile=0.4)
    tube(g, [V(0, 1.33, 0), V(0, 0.75, 0)], [0.008, 0.008], 4, M_IRON, (0.3, 0.28, 0.26), tile=0.2)
    frustum(g, 0.17, 0.2, 0.42, 0.3, 14, M_IRON, (0.3, 0.28, 0.27), tile=0.4)
    # Two yurts, doors to the fire; a banner pole rises through the big one's crown (flag at y 3.2).
    yurt(g, rng, (-3.2, 0, -2.6), 1.75, math.atan2(3.2, 2.6), pole_top=3.7)
    yurt(g, rng, (3.1, 0, -3.0), 1.4, math.atan2(-3.1, 3.0), wall_h=1.1, crown_h=2.05)
    # Drying racks: meat strips and split fish on rails; a stretched elk hide beside them.
    rk = V(-3.9, 0, 1.4)
    for dz in (-1.0, 1.0):
        for dx in (-0.22, 0.22):
            pole(g, rk + V(dx, -0.3, dz), rk + V(-dx * 0.5, 1.75, dz), 0.045, 0.04, rng, col=(0.62, 0.56, 0.48), sides=6)
    for y in (1.62, 1.2):
        tube(g, [rk + V(0, y, -1.15), rk + V(0, y, 1.15)], [0.03, 0.03], 6, M_BARK, (0.62, 0.56, 0.48), tile=0.4)
        for k in range(9):
            p = rk + V(0, y - 0.02, -0.9 + k * 0.22)
            if (k + int(y * 10)) % 3 == 0:
                stone(g, tuple(p + V(0, -0.2, 0)), (0.03, 0.2, 0.07), rng, mat=M_HIDE, detail=1, cuts=0,
                      col_fn=lambda q, n: mix((0.55, 0.52, 0.48), (0.35, 0.3, 0.26), 0.5 + 0.5 * n.x), tile=0.2)
            else:
                lbox(g, p + V(0, -0.22, 0), (0.03, 0.42, 0.06), quat_x(rng.uniform(-0.1, 0.1)), M_HIDE,
                     mix((0.36, 0.08, 0.06), (0.16, 0.06, 0.05), rng.uniform(0, 1)), tile=0.2)
    stretched_hide(g, rng, V(-2.2, 0, 2.9), 2.4)
    # The frozen pond: grey-blue ice, wind-scoured, snow drifted on its rim; two fishing holes with
    # chipped ice heaped round them, lines on stick tripods, the catch frozen to the ice.
    pc = V(2.6, 0, 2.5)
    nzi = Noise(rng, 4, 0.8)
    mound(g, tuple(pc + V(0, 0.0, 0)), 2.4, 2.0, 0.035, rng, mat=M_SNOW,
          col_fn=lambda p, n: mix((0.5, 0.6, 0.7), (0.78, 0.84, 0.9), smoothstep(-0.3, 0.6, nzi(p * 1.5))), tile=2.4,
          rings=5, seg=26, skirt=0.06, rough=0.05, edge=0.18, power=0.25)
    for k in range(9):
        a = k / 9 * 2 * math.pi + rng.uniform(0, 0.3)
        drift(g, tuple(pc + V(math.cos(a) * 2.5, 0, math.sin(a) * 2.1)), 1.2, 0.5, rng.uniform(0.15, 0.3), rng)
    for k, hc in enumerate((pc + V(-0.7, 0, -0.3), pc + V(0.8, 0, 0.5))):
        disc(g, hc + V(0, 0.03, 0), quat_y(0), 0.24, 0.02, 14, M_EARTH, (0.015, 0.02, 0.03), tile=0.3)
        for j in range(9):
            a = j / 9 * 2 * math.pi + rng.uniform(0, 0.4)
            s = rng.uniform(0.04, 0.09)
            stone(g, tuple(hc + V(math.cos(a) * 0.33, 0.04, math.sin(a) * 0.33)), (s, s * 0.6, s * 0.8), rng,
                  mat=M_SNOW, detail=0, col_fn=lambda p, n: (0.72, 0.8, 0.88), tile=0.3, cuts=1)
        top = hc + V(0.25, 0.75, 0.1)
        for j in range(3):
            a = j / 3 * 2 * math.pi
            tube(g, [hc + V(math.cos(a) * 0.45, 0.0, math.sin(a) * 0.45), top], [0.018, 0.012], 4, M_BARK,
                 (0.6, 0.55, 0.48), tile=0.3)
        tube(g, [top, hc + V(0.02, 0.02, 0.0), hc + V(0, -0.3, 0)], [0.003] * 3, 3, M_CLOTH, (0.3, 0.28, 0.25), tile=0.2,
             cap=False)
        for j in range(2 + k):
            fp = hc + V(rng.uniform(-0.9, 0.9), 0.06, rng.uniform(0.45, 0.9) * (1 if j % 2 else -1))
            stone(g, tuple(fp), (0.04, 0.035, 0.17), rng, mat=M_HIDE, detail=1, cuts=0, rot=quat_y(rng.uniform(0, 3)),
                  col_fn=lambda q, n: mix((0.42, 0.44, 0.42), (0.7, 0.7, 0.66), 0.5 + 0.5 * n.y), tile=0.2)
    # A hide-padded stump stool and an ice pick by the near hole.
    st = pc + V(-1.3, 0, 0.2)
    pole(g, st + V(0, -0.1, 0), st + V(0, 0.38, 0), 0.17, 0.16, rng, col=(0.62, 0.56, 0.5), sides=9, segs=1)
    dome(g, st + V(0, 0.38, 0), 0.2, quat_y(0), M_HIDE, lambda p, n: DARK_HIDE, tile=0.3, rings=3, seg=10, squash=0.3)
    spear(g, pc + V(-1.0, 0.03, -0.9), pc + V(-0.2, 0.06, -1.1), rng, col=(0.55, 0.48, 0.4))
    # The elk: carcass hung by the hocks from a tripod gambrel, opened, ribs showing; the hide spread
    # fur-down on the snow, the antlered head beside it, blood frozen in the trampled snow.
    tp = V(-0.4, 0, -4.1)
    apex = tp + V(0, 3.0, 0)
    for k in range(3):
        a = k / 3 * 2 * math.pi + 0.5
        tube(g, [tp + V(math.cos(a) * 1.2, -0.25, math.sin(a) * 1.2), apex + V(0, 0.25, 0)], [0.07, 0.05], 7, M_BARK,
             (0.62, 0.56, 0.48), tile=0.7)
    lashing(g, apex, (0, 1, 0), 0.12, rng)
    gam = apex + V(0, -0.35, 0)
    tube(g, [gam + V(-0.35, 0, 0), gam + V(0.35, 0, 0)], [0.03, 0.03], 5, M_PLANK, TIMBER, tile=0.3)
    tube(g, [apex, gam], [0.012, 0.012], 4, M_CLOTH, ROPE, tile=0.2)
    flesh = lambda p, n: mix((0.48, 0.12, 0.09), (0.28, 0.07, 0.06), 0.5 + 0.5 * nzs(p * 7))
    body_c = gam + V(0, -1.05, 0)
    for sx in (-1, 1):
        tube(g, [gam + V(sx * 0.3, 0, 0), gam + V(sx * 0.22, -0.4, 0.02), body_c + V(sx * 0.16, 0.35, 0)],
             [0.05, 0.07, 0.13], 7, M_HIDE, (0.45, 0.12, 0.09), tile=0.3)
    stone(g, tuple(body_c), (0.33, 0.72, 0.27), rng, mat=M_HIDE, detail=2, rough=0.06, cuts=0, col_fn=flesh, tile=0.4)
    stone(g, tuple(body_c + V(0, -0.85, 0.04)), (0.18, 0.28, 0.16), rng, mat=M_HIDE, detail=2, rough=0.06, cuts=0,
          col_fn=flesh, tile=0.4)
    for k in range(7):
        y = 0.3 - k * 0.11
        pts = [body_c + V(0.28 * math.cos(a), y - 0.03 * math.sin(a), 0.24 * math.sin(a) + 0.05) for a in
               np.linspace(-0.2, math.pi + 0.2, 6)]
        tube(g, pts, [0.016] * 6, 4, M_STONE, (1.1, 0.95, 0.85), tile=0.2, cap=False)
    grid = []
    hcen = V(1.3, 0.03, -2.4)
    for i in range(6):
        row = []
        for j in range(5):
            u, v = i / 5, j / 4
            w_ = 0.75 * (1 - 0.35 * abs(u - 0.5) * 2) + 0.12 * (abs(u - 0.2) < 0.12 or abs(u - 0.82) < 0.12)
            row.append(tuple(hcen + quat_y(0.6) @ V((v - 0.5) * 2 * w_, 0.02 * math.sin(u * 9), (u - 0.5) * 2.2)))
        grid.append(row)
    sheet(g, grid, M_HIDE, lambda u, v: mix((0.42, 0.3, 0.2), (0.62, 0.32, 0.24), 0.4), tile=0.7, double=True)
    head = V(0.6, 0.12, -3.3)
    skull(g, head, 2.0, rng, col=(0.45, 0.36, 0.28), yaw=2.4)
    antlers(g, head + V(0, 0.15, 0), 1.3, rng, yaw=2.4)
    for k in range(6):
        p = V(-0.4, 0.03, -4.1) + V(rng.uniform(-0.6, 0.6), 0, rng.uniform(-0.4, 0.6))
        disc(g, p, quat_y(rng.uniform(0, 3)), rng.uniform(0.08, 0.2), 0.008, 9, M_SNOW, (0.35, 0.05, 0.05), tile=0.3)
    # Log seats with furs; snowshoes and a spare bow-stave leaning on the small yurt.
    for a, L in ((0.9, 1.2), (2.4, 1.1), (4.6, 1.0)):
        d = V(math.cos(a), 0, math.sin(a))
        t = V(-d.z, 0, d.x)
        cc = d * 1.35 + V(0, 0.15, 0)
        pole(g, cc - t * L / 2, cc + t * L / 2, 0.17, 0.15, rng, col=(0.66, 0.6, 0.52), sides=9, segs=2)
        sheet(g, [[tuple(cc + t * (s * L * 0.35) + d * (dd * 0.22) + V(0, 0.15 - 0.12 * abs(dd), 0)) for dd in (-1, 0, 1)]
                  for s in (-1, 0, 1)], M_HIDE, lambda u, v: scale(DARK_HIDE, 0.9 + 0.2 * v), tile=0.5, double=True)
    for k in range(2):
        sc = V(1.8 + k * 0.3, 0.55, -1.75)
        ring = [sc + V(0.0, math.sin(a) * 0.45, math.cos(a) * 0.17) for a in np.linspace(0, 2 * math.pi, 13)]
        tube(g, ring, [0.016] * 13, 4, M_BARK, (0.6, 0.52, 0.42), tile=0.3, cap=False)
        for y in (-0.2, 0.0, 0.2):
            tube(g, [sc + V(0, y, -0.15), sc + V(0, y, 0.15)], [0.006] * 2, 3, M_CLOTH, RAWHIDE, tile=0.2, cap=False)
    # Drifts round the camp's edge (the camp is dug out of them).
    for k in range(8):
        a = k / 8 * 2 * math.pi + 0.2
        p = V(math.cos(a) * 4.6, 0, math.sin(a) * 4.4)
        drift(g, tuple(p), rng.uniform(1.6, 2.4), rng.uniform(0.6, 0.9), rng.uniform(0.35, 0.6), rng)
    return b


# ═══════════════════════════════════════════════════════════════ WP1: five more camps (indexes 5-9)
# The five camps of the "living island" pass (docs/superpowers/specs/2026-10-13-zywa-wyspa-design.md
# §2 A): each a different JOB in the war, told by what lies on the ground.
#   ork_camp_ram     FOREST  the Ram Yard: oaks felled for a ram, debarked logs, chips, trestles, a
#                            bark lean-to. The ram itself is its own model (ork_camp_ram_beam), shown
#                            always in its yard; ork_camp_ram_burnt the day after "Fire the ram".
#   ork_camp_pitch   DESERT  the Pitch Seep: black bitumen oozing from a wadi bank, kettles of pitch on
#                            the fire, sheaves of torches drying, tar-black ground and glossy pools.
#   ork_camp_reeds   GRASS   the Reed Hide: scouts' screen of bundled reeds, sleeping mats, and on the
#                            ground a clay model of OUR fort with pebble orks circling to a side gate.
#   ork_camp_eyrie   ROCKY   the Eyrie: a lookout crag with a plank perch, a rope ladder, a war horn on
#                            a post at its foot, heaps of throwing stones.
#   ork_camp_ring    SNOW    Skarn's Ring: a trampled fighting ring fenced with skull spears, a log
#                            bench, a weapon rack, the red-hand standard of Skarn.
PALE_WOOD = (0.98, 0.86, 0.66)   # fresh debarked oak
CHIPS = (0.95, 0.8, 0.58)
PITCH = (0.025, 0.022, 0.02)
CLAY = (0.78, 0.5, 0.34)
REED = (1.35, 1.18, 0.78)
CHAR_COL = (0.1, 0.09, 0.085)


def stump(g, rng, c, r=0.42, h=0.55, axe=True):
    """A fresh-felled oak stump: bark collar, root flares, a pale axed top with a torn hinge lip."""
    c = Vector(c)
    pole(g, c + V(0, -0.2, 0), c + V(0, h, 0), r * 1.08, r, rng, col=(0.85, 0.8, 0.74), sides=11, segs=2)
    for k in range(5):
        a = k / 5 * 2 * math.pi + rng.uniform(-0.3, 0.3)
        d = V(math.cos(a), 0, math.sin(a))
        tube(g, [c + d * r * 0.7 + V(0, h * 0.35, 0), c + d * (r + 0.35) + V(0, -0.05, 0), c + d * (r + 0.6) + V(0, -0.2, 0)],
             [r * 0.35, r * 0.2, 0.03], 6, M_BARK, (0.8, 0.75, 0.7), tile=0.6)
    tilt = quat_x(rng.uniform(-0.12, 0.12)) @ quat_z(rng.uniform(-0.12, 0.12))
    disc(g, c + V(0, h + 0.005, 0), tilt, r * 0.96, 0.02, 14, W.M_TIMBER, PALE_WOOD, tile=0.5,
         col_rim=scale(PALE_WOOD, 0.8))
    if axe:
        lbox(g, c + V(0, h + 0.06, -r * 0.55), (r * 1.3, 0.12, 0.06), quat_x(0.2), W.M_TIMBER, scale(PALE_WOOD, 0.9), tile=0.3)


def debarked_log(g, rng, a, b, r, col=PALE_WOOD, charred_k=0.0):
    a, b = Vector(a), Vector(b)
    cf = lambda t: mix(scale(col, 0.92 + 0.08 * math.sin(t * 17.0)), (0.08, 0.07, 0.06), charred_k)
    tube(g, [a, a.lerp(b, 0.5) + V(0, rng.uniform(-0.02, 0.02), 0), b], [r, r * 0.95, r * 0.88], 12, W.M_TIMBER, col,
         tile=0.8, col_fn=cf)
    # Strips of bark still clinging here and there.
    d = (b - a).normalized()
    up = V(0, 1, 0)
    side = d.cross(up).normalized()
    for k in range(3):
        p = a.lerp(b, rng.uniform(0.15, 0.85))
        ang = rng.uniform(0, 6.28)
        off = (up * math.cos(ang) + side * math.sin(ang)) * r * 1.01
        L = rng.uniform(0.2, 0.5)
        tube(g, [p + off - d * L / 2, p + off + d * L / 2], [0.03, 0.03], 4, M_BARK,
             mix((0.55, 0.5, 0.45), (0.06, 0.05, 0.05), charred_k), tile=0.4)


def trestle(g, rng, c, yaw, span=1.6):
    """A sawbuck: two X-legs and a stretcher."""
    c = Vector(c)
    rq = quat_y(yaw)
    for sx in (-1, 1):
        e = c + rq @ V(sx * span / 2, 0, 0)
        for sz in (-1, 1):
            tube(g, [e + rq @ V(0, -0.15, sz * 0.42), e + rq @ V(0, 0.95, -sz * 0.22)], [0.05, 0.045], 6, M_BARK,
                 (0.8, 0.74, 0.66), tile=0.5)
        lashing(g, e + V(0, 0.62, 0), rq @ V(1, 0, 0), 0.07, rng, turns=2)
    tube(g, [c + rq @ V(-span / 2, 0.3, 0), c + rq @ V(span / 2, 0.3, 0)], [0.04, 0.04], 6, M_BARK, (0.78, 0.72, 0.64),
         tile=0.5)


def felling_axe(g, rng, grip, head_at, edge_dir):
    grip, head_at = Vector(grip), Vector(head_at)
    tube(g, [grip, head_at], [0.022, 0.02], 6, M_PLANK, (0.6, 0.48, 0.36), tile=0.3)
    e = Vector(edge_dir).normalized()
    lbox(g, head_at + e * 0.06, (0.05, 0.12, 0.2), quat_y(math.atan2(e.x, e.z)), M_IRON, (0.4, 0.38, 0.36), tile=0.2)



# ─────────────────────────────────────────────── grounded clutter (shared by the role camps)
def firewood(g, rng, c, yaw, n=9, L=0.9, col=(0.55, 0.48, 0.4)):
    """Split firewood stacked crib-wise, the bottom course sunk into the ground."""
    c = Vector(c)
    rq = quat_y(yaw)
    k = 0
    for layer in range(3):
        cnt = max(1, 4 - layer)
        for j in range(cnt):
            if k >= n:
                return
            x = (j - (cnt - 1) / 2) * 0.17
            y = -0.03 + layer * 0.13
            a = c + rq @ V(x + rng.uniform(-0.02, 0.02), y + 0.07, -L / 2)
            bb = c + rq @ V(x + rng.uniform(-0.03, 0.03), y + 0.07, L / 2 + rng.uniform(-0.1, 0.1))
            r = rng.uniform(0.055, 0.08)
            tube(g, [a, bb], [r, r * 0.95], 6, M_BARK, scale(col, rng.uniform(0.75, 1.05)), tile=0.4)
            k += 1


def scatter_bones(g, rng, c, r, n, skulls=0):
    """Gnawed bones dropped round a fire, half trodden into the dirt."""
    c = Vector(c)
    for k in range(n):
        a = rng.uniform(0, 6.28)
        d = rng.uniform(0.2, r)
        p = c + V(math.cos(a) * d, -0.004, math.sin(a) * d)
        t = rng.uniform(0, 6.28)
        ln = rng.uniform(0.12, 0.3)
        e = V(math.cos(t), rng.uniform(-0.05, 0.02), math.sin(t)) * ln
        bone(g, p - e * 0.5, p + e * 0.5, rng.uniform(0.012, 0.02), rng, col=scale(BONE, rng.uniform(0.7, 0.95)))
    for k in range(skulls):
        a = rng.uniform(0, 6.28)
        p = c + V(math.cos(a) * r * 0.8, -0.03, math.sin(a) * r * 0.8)
        skull(g, p, rng.uniform(0.7, 0.95), rng, col=OLD_BONE, horns=rng.uniform(0, 0.8), yaw=rng.uniform(0, 6.28))


def sunk_stones(g, rng, c, r, n, col=(0.62, 0.6, 0.56), big=0.22):
    """Field stones bedded in the ground: centre below the surface, only the crowns showing."""
    c = Vector(c)
    for k in range(n):
        a = rng.uniform(0, 6.28)
        d = r * math.sqrt(rng.uniform(0.05, 1.0))
        s = rng.uniform(0.05, big)
        p = c + V(math.cos(a) * d, -s * 0.45, math.sin(a) * d)
        stone(g, tuple(p), (s, s * 0.75, s * rng.uniform(0.7, 1.1)), rng, detail=1,
              col_fn=lambda q, nn, cc=scale(col, rng.uniform(0.8, 1.05)): cc, tile=0.5)


def ash_bed(g, rng, c, r):
    """Ash and charcoal raked out of a fire: a ragged, barely-raised smear sunk into the dirt."""
    c = Vector(c)
    nz = Noise(rng, 3, 2.0)
    mound(g, tuple(c + V(0, -0.025, 0)), r, r * rng.uniform(0.75, 0.95), 0.035, rng, mat=M_EARTH,
          col_fn=lambda p, n: mix((0.09, 0.085, 0.08), (0.42, 0.4, 0.37), smoothstep(-0.2, 0.7, nz(p * 2.5) + 0.6 * math.hypot(p.x - c.x, p.z - c.z) / r - 0.3)),
          tile=0.4, rings=3, seg=16, skirt=0.05, edge=0.45)
    for k in range(10):
        a = rng.uniform(0, 6.28)
        d = rng.uniform(0.1, r * 1.1)
        p = c + V(math.cos(a) * d, 0.0, math.sin(a) * d)
        tube(g, [p, p + V(math.cos(a + 1.3), 0.01, math.sin(a + 1.3)) * rng.uniform(0.08, 0.22)], [0.02, 0.016], 5, M_BARK,
             CHAR_COL, tile=0.2)


def barrel(g, rng, c, h=0.8, r=0.3, stain=0.6, lying=False, yaw=0.0):
    """A stave barrel with iron hoops, its lower half and one side soaked black with pitch."""
    c = Vector(c)
    prof = [(0.0, 0.0), (r * 0.86, 0.0), (r, h * 0.3), (r * 1.06, h * 0.5), (r, h * 0.7), (r * 0.86, h), (0.0, h)]
    rot = quat_y(yaw) @ quat_x(math.pi / 2) if lying else quat_y(yaw)
    verts, tris = lathe(prof, 16, c, rot)
    tris = orient(verts, tris, c + rot @ V(0, h / 2, 0), V(0, 1, 0), True)
    nzb = Noise(rng, 3, 3.0)

    def f(p, n):
        lp = rot.inverted() @ (p - c)
        a = math.atan2(lp.z, lp.x)
        y = lp.y / h
        stave = 0.88 + 0.12 * math.sin(a * 16 / 2 * 2)
        base = scale(mix((0.5, 0.36, 0.24), (0.36, 0.26, 0.18), nzb(p * 4)), stave)
        soak = smoothstep(0.55, 0.15, y + 0.25 * math.sin(a * 3 + 1.0)) * stain + smoothstep(0.86, 1.0, y) * stain * 0.8
        hoop = any(abs(y - hy) < 0.035 for hy in (0.12, 0.3, 0.7, 0.88))
        if hoop:
            return (0.16, 0.15, 0.14)
        return mix(base, PITCH, min(1.0, soak))
    smooth_mesh(g, verts, tris, M_PLANK, f, 0.4)


def tall_grass(g, rng, c, r, n, h, col=(0.62, 0.66, 0.38)):
    """Rank tall grass: fine arching blades, a few seed heads."""
    c = Vector(c)
    for k in range(n):
        a = rng.uniform(0, 6.28)
        d = r * math.sqrt(rng.uniform(0, 1))
        foot = c + V(math.cos(a) * d, -0.05, math.sin(a) * d)
        hh = h * rng.uniform(0.55, 1.05)
        t = rng.uniform(0, 6.28)
        arch = V(math.cos(t), 0, math.sin(t)) * hh * rng.uniform(0.15, 0.4)
        tip = foot + V(0, hh, 0) + arch
        tube(g, [foot, foot + V(0, hh * 0.6, 0) + arch * 0.3, tip - V(0, hh * 0.08, 0)], [0.009, 0.007, 0.002], 3, M_CLOTH,
             mix(col, (0.9, 0.82, 0.55), rng.uniform(0.0, 0.5)), tile=0.4, cap=False)


def flattened_reeds(g, rng, c, yaw, w, L, n):
    """Reeds trodden flat into a gap: stems lying along the way through, broken and crossed."""
    c = Vector(c)
    rq = quat_y(yaw)
    for k in range(n):
        x = rng.uniform(-w / 2, w / 2)
        z = rng.uniform(-L / 2, L / 2)
        t = rng.uniform(-0.5, 0.5)
        d = rq @ V(math.sin(t), 0, math.cos(t))
        a = c + rq @ V(x, 0.0, z)
        ln = rng.uniform(0.5, 1.2)
        tube(g, [a, a + d * ln * 0.5 + V(0, 0.02, 0), a + d * ln], [0.011, 0.009, 0.003], 4, M_CLOTH,
             mix(REED, (0.55, 0.5, 0.36), rng.uniform(0.2, 0.7)), tile=0.4, cap=False)


def woven_mat(g, rng, c, yaw, w=0.8, l=1.85, col=(0.78, 0.66, 0.42)):
    """A thick woven reed mat: a padded core, over-under weave strips, bound edges, a curled corner."""
    c = Vector(c)
    rq = quat_y(yaw)
    lbox(g, c + V(0, 0.035, 0), (w, 0.05, l), rq, M_THATCH, scale(col, 0.82), tile=0.4)
    nw = 9
    for i in range(nw):
        x = (i - (nw - 1) / 2) * w / nw
        for j in range(8):
            z = (j - 3.5) * l / 8
            up = (i + j) % 2
            lbox(g, c + rq @ V(x, 0.064 + 0.006 * up, z), (w / nw * 0.92, 0.012, l / 8 * 0.95), rq, M_THATCH,
                 scale(col, 0.88 + 0.14 * up + rng.uniform(-0.04, 0.04)), tile=0.2)
    for sx in (-1, 1):
        tube(g, [c + rq @ V(sx * w / 2, 0.05, -l / 2), c + rq @ V(sx * w / 2, 0.05, l / 2)], [0.022, 0.022], 5, M_THATCH,
             scale(col, 0.7), tile=0.3)
    grid = [[tuple(c + rq @ V((i - 1) * w / 2, 0.075 + 0.12 * (j / 3) ** 2 * (i == 2), l / 2 + j * 0.06)) for j in range(4)]
            for i in range(3)]
    sheet(g, grid, M_THATCH, lambda u, v: scale(col, 0.9), tile=0.3, double=True)


def camp_ram(rng):
    b = Builder()
    g = G(b)
    # (The trampled ground is baked into the terrain mask — camps.rs `ground_wear`.)
    ash_bed(g, rng, (-1.4, 0, 2.4), 0.95)
    scatter_bones(g, rng, (-1.4, 0, 2.4), 1.6, 9, skulls=1)
    firewood(g, rng, (-2.6, 0, 3.3), 0.4, n=9)
    sunk_stones(g, rng, (0, 0, 0), 5.2, 26, col=(0.6, 0.58, 0.54))
    # Chips everywhere the axes worked: a pale carpet thickest round the trestle and the ram bed.
    for (cx, cz, n, sp) in ((-1.2, -3.4, 70, 1.3), (1.2, 0.5, 90, 1.6), (-3.6, 0.6, 40, 1.2), (3.4, 2.3, 20, 0.8)):
        for k in range(n):
            p = V(cx + rng.normal() * sp * 0.5, 0.012, cz + rng.normal() * sp * 0.7)
            s = rng.uniform(0.03, 0.09)
            lbox(g, p, (s, 0.012, s * rng.uniform(1.4, 2.6)), quat_y(rng.uniform(0, 3.14)) @ quat_x(rng.uniform(-0.3, 0.3)),
                 W.M_TIMBER, scale(CHIPS, rng.uniform(0.75, 1.05)), tile=0.2)
    # The ram's bed: three rollers, the drag ruts running off toward the walls (+Z).
    for z in (-1.8, 0.4, 2.6):
        debarked_log(g, rng, V(0.4, 0.13, z), V(2.0, 0.13, z + 0.05), 0.13)
    for sx in (0.85, 1.55):
        mound(g, (sx, -0.005, 4.4), 0.12, 0.85, 0.02, rng, mat=M_EARTH,
              col_fn=lambda p, n: (0.32, 0.27, 0.22), tile=0.4, rings=2, seg=10, skirt=0.03)
    # The trestles with a log half-worked on them, a felling axe bitten into it.
    trestle(g, rng, V(-1.2, 0, -3.4), 0.0, span=1.9)
    debarked_log(g, rng, V(-2.5, 0.98, -3.4), V(0.2, 0.98, -3.38), 0.22)
    felling_axe(g, rng, V(-0.55, 1.6, -3.1), V(-0.7, 1.14, -3.38), (0, 0, 1))
    # The log pile: oaks stripped and stacked on skids.
    for k, (x, y) in enumerate(((-3.95, 0.25), (-3.3, 0.25), (-3.62, 0.72), (-4.6, 0.22))):
        debarked_log(g, rng, V(x, y, -1.2 + rng.uniform(-0.2, 0.2)), V(x + rng.uniform(-0.1, 0.1), y, 2.3), 0.24 + 0.03 * (k % 2))
    for z in (-0.6, 1.6):
        tube(g, [V(-4.9, 0.03, z), V(-2.9, 0.03, z)], [0.07, 0.07], 6, M_BARK, (0.6, 0.55, 0.5), tile=0.5)
    # The stripped bark, heaped in curls beside the pile.
    for k in range(9):
        c = V(-2.65 + rng.uniform(-0.3, 0.3), 0.05, -0.6 + k * 0.32)
        a = rng.uniform(0, 6.28)
        d = V(math.cos(a), 0, math.sin(a))
        nrm = V(-d.z, 0, d.x)
        grid = [[tuple(c + d * (u - 0.5) * 0.9 + nrm * 0.12 * math.cos(v * 2.6) + V(0, 0.1 * math.sin(v * 2.6) + 0.02 * (k % 3), 0))
                 for v in np.linspace(0, 1, 4)] for u in np.linspace(0, 1, 4)]
        sheet(g, grid, M_BARK, lambda u, v: (0.62, 0.56, 0.5), tile=0.6, double=True)
    # Three stumps of the oaks that went into it, one with the axe left in the cut.
    stump(g, rng, (-4.3, 0, -3.3), 0.46, 0.5)
    stump(g, rng, (4.3, 0, 2.3), 0.4, 0.62)
    stump(g, rng, (-3.9, 0, 3.8), 0.5, 0.45)
    felling_axe(g, rng, V(4.0, 1.15, 2.5), V(4.15, 0.68, 2.35), (1, 0, 0))
    # The bark lean-to: a ridge on two forks, slabs of oak bark down it, a hide bed under it.
    lt = V(3.4, 0, -3.6)
    for sx in (-1.15, 1.15):
        pole(g, lt + V(sx, -0.25, 0.6), lt + V(sx, 1.55, 0.6), 0.05, 0.045, rng, col=(0.8, 0.74, 0.66), sides=6)
    pole(g, lt + V(-1.35, 1.5, 0.6), lt + V(1.35, 1.5, 0.6), 0.05, 0.05, rng, col=(0.8, 0.74, 0.66), sides=6)
    for k in range(7):
        x = -1.05 + k * 0.35
        top = lt + V(x, 1.52, 0.66)
        bot = lt + V(x + rng.uniform(-0.05, 0.05), 0.0, -0.75)
        grid = [[tuple(top.lerp(bot, u) + V(w * 0.19, 0.03 * math.cos(w * 1.5), 0)) for w in (-1, 0, 1)] for u in np.linspace(0, 1, 4)]
        sheet(g, grid, M_BARK, lambda u, v: scale((0.6, 0.55, 0.5), 0.85 + 0.15 * v), tile=0.7, double=True)
    grid = [[(lt.x + x, 0.04, lt.z + z) for z in np.linspace(-0.4, 0.5, 3)] for x in np.linspace(-0.8, 0.8, 4)]
    sheet(g, grid, M_HIDE, lambda u, v: DARK_HIDE, tile=0.6)
    # The cook fire (flame at (-1.4, 0, 2.4)) with a spit on forked sticks.
    firepit(g, rng, (-1.4, 0, 2.4), r=0.42)
    for sx in (-1, 1):
        for sz in (-1, 1):
            tube(g, [V(-1.4 + sx * 0.5, -0.1, 2.4 + sz * 0.12), V(-1.4 + sx * 0.5, 0.75, 2.4 - sz * 0.08)], [0.025, 0.02], 5,
                 M_BARK, (0.62, 0.56, 0.48), tile=0.3)
    tube(g, [V(-2.0, 0.72, 2.4), V(-0.8, 0.72, 2.4)], [0.015, 0.015], 5, M_PLANK, TIMBER, tile=0.3)
    stone(g, (-1.4, 0.6, 2.4), (0.22, 0.12, 0.12), rng, mat=M_HIDE, detail=1, cuts=0,
          col_fn=lambda p, n: mix((0.42, 0.18, 0.1), (0.2, 0.1, 0.06), 0.5 + 0.5 * n.y), tile=0.3)
    # The banner pole (flag at (3.9, 2.5, 0.2)): an oak sapling, a skull lashed under the top.
    sb = V(3.9, 0, 0.2)
    pole(g, sb + V(0, -0.3, 0), sb + V(0.03, 2.95, 0.0), 0.06, 0.04, rng, col=(0.82, 0.76, 0.68), sides=7)
    skull(g, sb + V(0.03, 2.2, 0.06), 1.3, rng, horns=0.8, yaw=0.0)
    return b


def ram_beam(rng, burnt=False):
    """The ram on its rollers (camp-local: along +Z at x 1.2, head toward the walls): one great oak,
    debarked, the head shod in a riveted iron cap, iron hoops, carrying-rope loops, and the start of
    a roof — two rafter pairs and a ridge over the tail, more rafters lying ready beside it.
    `burnt`: charred through, the roof fallen in, ash under it."""
    b = Builder()
    g = G(b)
    ck = 0.85 if burnt else 0.0
    x0 = 1.2
    tail, head = V(x0, 0.6, -2.9), V(x0, 0.6, 3.8)
    debarked_log(g, rng, tail, head, 0.36, charred_k=ck)
    iron = mix((0.36, 0.33, 0.31), (0.12, 0.1, 0.09), ck * 0.6)
    tube(g, [head + V(0, 0, -0.35), head + V(0, 0, 0.02), head + V(0, 0, 0.32)], [0.39, 0.4, 0.2], 14, M_IRON, iron, tile=0.4)
    for k in range(10):
        a = k / 10 * 2 * math.pi
        stone(g, tuple(head + V(math.cos(a) * 0.39, math.sin(a) * 0.39, -0.2)), (0.025,) * 3, rng, mat=M_IRON, detail=0,
              col_fn=lambda p, n: scale(iron, 0.8), tile=0.2, cuts=0)
    for z in (-2.2, 0.0, 2.2):
        ring = [V(x0 + math.cos(a) * 0.375, 0.6 + math.sin(a) * 0.375, z) for a in np.linspace(0, 2 * math.pi, 17)]
        tube(g, ring, [0.03] * 17, 4, M_IRON, iron, tile=0.3, cap=False)
    for z in np.linspace(-2.4, 2.8, 6):
        for sx in (-1, 1):
            p = V(x0 + sx * 0.36, 0.62, z)
            loop = [p + V(sx * 0.12 * math.sin(t), -0.25 * math.sin(t * 0.5) ** 2, 0.1 * math.cos(t)) for t in np.linspace(0, math.pi, 6)]
            tube(g, loop, [0.016] * 6, 4, M_CLOTH, mix(ROPE, (0.05, 0.05, 0.05), ck), tile=0.2, cap=False)
    wood = mix((0.8, 0.74, 0.66), (0.08, 0.07, 0.06), ck)
    if not burnt:
        for z in (-2.5, -1.1):
            for sx in (-1, 1):
                pole(g, V(x0 + sx * 1.0, -0.2, z), V(x0, 2.1, z), 0.06, 0.05, rng, col=wood, sides=6)
            lashing(g, V(x0, 2.0, z), (0, 0, 1), 0.08, rng, turns=2)
        pole(g, V(x0, 2.05, -2.8), V(x0, 2.05, -0.8), 0.05, 0.05, rng, col=wood, sides=6)
        for k in range(4):
            x = 2.45 + k * 0.17
            y = 0.06 + 0.1 * (k % 2)
            pole(g, V(x, y, -1.6), V(x + 0.05, y, 1.0), 0.06, 0.05, rng, col=wood, sides=6)
    else:
        for k in range(5):
            a = V(x0 + rng.uniform(-1.4, 1.4), 0.05, rng.uniform(-2.8, 0.0))
            bb = a + V(rng.uniform(-0.6, 0.6), rng.uniform(0.1, 0.6), rng.uniform(0.6, 1.4))
            beam(g, [a, bb], 0.08, 0.08, mat=M_BARK, col=CHAR_COL, rng=rng, jag=(0.05, 0.1), chamfer=0.4, mode="bark")
        mound(g, (x0, -0.01, 0.4), 1.4, 3.8, 0.04, rng, mat=M_EARTH,
              col_fn=lambda p, n: mix((0.12, 0.11, 0.1), (0.42, 0.41, 0.4), 0.3 + 0.3 * math.sin(p.z * 3 + p.x * 5)),
              tile=0.6, rings=4, seg=18, skirt=0.04)
    return b


def camp_ram_beam(rng):
    return ram_beam(rng, burnt=False)


def camp_ram_burnt(rng):
    return ram_beam(rng, burnt=True)


# ─────────────────────────────────────────────────────────────── DESERT: the Pitch Seep
def kettle(g, rng, c, r=0.42, h=0.55):
    """A riveted iron kettle full to the lip of pitch, dribbles down its sides, on three stones."""
    c = Vector(c)
    prof = [(0.0, 0.0), (r * 0.6, 0.0), (r * 0.92, h * 0.2), (r, h * 0.55), (r * 0.96, h * 0.92), (r * 1.04, h)]
    verts, tris = lathe(prof, 18, c, quat_y(0))
    tris = orient(verts, tris, c, V(0, 1, 0), True)
    nzk = Noise(rng, 3, 4.0)

    def f(p, n):
        y = (p.y - c.y) / h
        a = math.atan2(p.z - c.z, p.x - c.x)
        drip = smoothstep(0.75, 1.0, math.sin(a * 7 + 1.3) * 0.5 + 0.5) * smoothstep(0.1, 0.9, y)
        return mix(scale((0.3, 0.27, 0.25), 0.85 + 0.15 * nzk(p * 5)), PITCH, 0.35 + 0.65 * drip)
    smooth_mesh(g, verts, tris, M_IRON, f, 0.5)
    disc(g, c + V(0, h - 0.05, 0), quat_y(0), r * 0.98, 0.02, 18, M_IRON, PITCH, tile=0.3)
    for k in range(3):
        a = k / 3 * 2 * math.pi + 0.4
        stone(g, tuple(c + V(math.cos(a) * r * 0.85, -0.06, math.sin(a) * r * 0.85)), (0.16, 0.14, 0.15), rng, detail=1,
              col_fn=lambda p, n: mix((0.82, 0.68, 0.52), SOOT, 0.6), tile=0.4)
    for sx in (-1, 1):
        ring = [c + V(sx * (r + 0.02), h - 0.02 + 0.08 * math.sin(t), 0.08 * math.cos(t)) for t in np.linspace(0, math.pi, 6)]
        tube(g, ring, [0.012] * 6, 4, M_IRON, (0.25, 0.23, 0.22), tile=0.2, cap=False)


def torch_stave(g, rng, foot, top, wrapped=True):
    foot, top = Vector(foot), Vector(top)
    d = (top - foot).normalized()
    tube(g, [foot, top - d * 0.3], [0.022, 0.02], 5, M_PLANK, (0.62, 0.5, 0.38), tile=0.3)
    if wrapped:
        tube(g, [top - d * 0.34, top - d * 0.22, top - d * 0.05, top], [0.032, 0.05, 0.047, 0.03], 7, M_CLOTH,
             mix(PITCH, (0.3, 0.24, 0.18), rng.uniform(0.0, 0.25)), tile=0.2)


def tar_pool(g, rng, c, rx, rz):
    """A glossy pitch pool: an iron-material (smooth, dark) lens inside a matte tar rim sinking in."""
    c = Vector(c)
    mound(g, tuple(c + V(0, 0.0, 0)), rx * 1.25, rz * 1.25, 0.02, rng, mat=M_EARTH,
          col_fn=lambda p, n: (0.06, 0.05, 0.045), tile=0.5, rings=3, seg=16, skirt=0.04, edge=0.25)
    mound(g, tuple(c + V(0, 0.012, 0)), rx, rz, 0.018, rng, mat=M_IRON,
          col_fn=lambda p, n: PITCH, tile=0.8, rings=3, seg=18, skirt=0.0, edge=0.2, rough=0.0, power=0.3)


def camp_pitch(rng):
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 0.9)
    # (The trampled ground is baked into the terrain mask — camps.rs `ground_wear`.)
    # Tar-stained sand: ragged blots soaked dark round the seep and the pools, sunk flush with the
    # ground and fraying out to the sand colour at their rims (no hard-edged sheet).
    for (x, z, rx, rz) in ((-0.8, -2.7, 1.7, 1.0), (1.4, -1.5, 0.9, 0.7), (-2.2, -1.0, 0.8, 0.9), (0.2, -0.4, 0.9, 0.7),
                           (2.6, 0.8, 0.6, 0.6), (3.2, -2.1, 0.8, 0.6), (-1.0, 0.5, 0.6, 0.5)):
        cx, cz = x, z
        mound(g, (x, -0.02, z), rx, rz, 0.03, rng, mat=M_EARTH,
              col_fn=lambda p, n, cx=cx, cz=cz, rx=rx: mix((0.07, 0.06, 0.05), (0.62, 0.5, 0.38),
                                                           smoothstep(-0.15, 0.55, nz(p * 1.8) * 0.8 + math.hypot(p.x - cx, p.z - cz) / rx - 0.55)),
              tile=0.6, rings=4, seg=20, skirt=0.04, edge=0.45, power=0.5)
    # The seep: pitch welling from the bank's foot runs in a glossy tongue down into the low dip.
    for (a, bb, r) in (((-0.9, -3.9), (-0.85, -3.3), 0.22), ((-0.85, -3.3), (-0.3, -2.6), 0.16), ((0.4, -3.95), (0.1, -3.2), 0.1)):
        A, B = V(a[0], 0.02, a[1]), V(bb[0], 0.01, bb[1])
        tube(g, [A, A.lerp(B, 0.5) + V(0.06, 0.0, 0), B], [r, r * 0.8, r * 0.5], 8, M_IRON, PITCH, tile=0.3)
    for (x, y, z) in ((-1.4, 0.55, -4.0), (-0.9, 0.7, -4.15), (0.3, 0.5, -3.95), (1.7, 0.45, -3.85), (-3.0, 0.5, -3.65)):
        tube(g, [V(x, y, z - 0.05), V(x + 0.03, y * 0.5, z + 0.08), V(x + 0.02, 0.02, z + 0.25)], [0.05, 0.04, 0.06], 6,
             M_IRON, PITCH, tile=0.2)
    # The wadi bank at the back: sandstone ledges, pitch bleeding out of a bedding seam down the face.
    for (x, z, sx, sy, sz, yaw) in ((-3.2, -4.4, 2.4, 1.5, 1.2, 0.1), (-0.6, -4.8, 2.2, 1.9, 1.2, -0.05),
                                     (2.0, -4.5, 2.0, 1.3, 1.1, 0.15), (4.1, -3.6, 1.2, 0.9, 1.0, 0.5)):
        def rc(p, n, sy=sy):
            seam = smoothstep(0.07, 0.0, abs(p.y - sy * 0.35)) * smoothstep(0.5, 0.0, n.y)
            drip = smoothstep(0.82, 0.97, math.sin(p.x * 9.0 + 0.7 * math.sin(p.y * 3.0)) * 0.5 + 0.5)
            run = smoothstep(sy * 0.36, 0.0, p.y) * (1.0 if n.z > 0.2 else 0.0) * drip
            base = rock_col((1.18, 0.98, 0.74), ground=0.0, noise=nz)(p, n)
            return mix(base, PITCH, min(1.0, seam * 0.85 + 0.9 * run))
        slab(g, (x, sy * 0.3, z), (sx, sy, sz), quat_y(yaw), rng, res=(8, 6, 4), round_r=0.32, rough=0.12, cuts=2,
             col_fn=rc, tile=1.2)
    # The seep: a dug basin under the bank, brimming; a plank to stand on, a tarry bucket.
    tar_pool(g, rng, (-0.8, 0, -3.25), 1.1, 0.55)
    board(g, V(-0.6, 0.08, -2.5), (1, 0, 0.1), (0, 1, 0), 1.6, 0.26, 0.04, mat=M_PLANK, col=mix(TIMBER, PITCH, 0.5), rng=rng)
    frustum(g, 0.13, 0.15, 0.0, 0.24, 12, M_PLANK, mix(TIMBER, PITCH, 0.6), tile=0.3, centre=(0.4, 0.04, -2.75))
    disc(g, V(0.4, 0.25, -2.75), quat_y(0), 0.13, 0.01, 12, M_IRON, PITCH, tile=0.2)
    for (x, z, rx, rz) in PITCH_POOLS:
        tar_pool(g, rng, (x, 0, z), rx, rz)
    # The kettles on the fire (flame at (0.8, 0, -0.6)); a second one cold, a ladle across it.
    firepit(g, rng, (0.8, 0, -0.6), r=0.55, n=8, stone_col=(0.82, 0.68, 0.52))
    kettle(g, rng, V(0.8, 0.32, -0.6), r=0.46, h=0.6)
    firepit(g, rng, (-1.9, 0, 0.6), r=0.45, n=7, stone_col=(0.82, 0.68, 0.52))
    ash_bed(g, rng, (-1.9, 0, 0.6), 0.7)
    kettle(g, rng, V(-1.9, 0.26, 0.6), r=0.36, h=0.48)
    for k in range(3):
        a = k / 3 * 6.28 + 0.5
        tube(g, [V(-1.9 + math.cos(a) * 0.65, -0.1, 0.6 + math.sin(a) * 0.65), V(-1.9, 1.15, 0.6)], [0.03, 0.022], 5, M_BARK,
             mix((0.5, 0.42, 0.34), PITCH, 0.4), tile=0.3)
    cord(g, V(-1.9, 1.12, 0.6), 0.32, rng)
    ash_bed(g, rng, (0.8, 0, -0.6), 0.85)
    # Stained barrels: a stood row by the bank, one on its side oozing, staves black where it spilt.
    for (x, z, h_, st) in ((2.45, -3.55, 0.82, 0.55), (3.05, -3.35, 0.78, 0.75), (1.0, -3.75, 0.7, 0.4)):
        barrel(g, rng, V(x, -0.04, z), h=h_, r=0.29, stain=st, yaw=rng.uniform(0, 6.28))
    barrel(g, rng, V(2.2, 0.27, -2.75), h=0.78, r=0.28, stain=0.9, lying=True, yaw=-2.2)
    tar_pool(g, rng, (1.3, 0, -3.0), 0.38, 0.26)
    # Torches stacked log-fashion in a crib, dipped heads all one way.
    for layer in range(4):
        for j in range(7 - layer):
            x = -4.6 + (j - (6 - layer) / 2) * 0.1
            y = 0.05 + layer * 0.08
            torch_stave(g, rng, V(x, y, -1.2 + 0.05 * (layer % 2)), V(x + 0.02, y, -0.05))
    firewood(g, rng, (-0.6, 0, 1.8), 1.2, n=8, col=(0.6, 0.5, 0.4))
    scatter_bones(g, rng, (0.8, 0, -0.6), 1.5, 7)
    sunk_stones(g, rng, (0, 0, 0), 5.0, 18, col=(0.86, 0.72, 0.56))
    tube(g, [V(-2.3, 0.6, 0.4), V(-1.5, 0.58, 0.8), V(-1.3, 0.55, 0.9)], [0.018, 0.018, 0.02], 5, M_PLANK,
         mix(TIMBER, PITCH, 0.5), tile=0.3)
    # Torch sheaves: staves wrapped and dipped, standing to dry against a rail; more bundled and tied.
    rk = V(-3.0, 0, -2.0)
    for sx in (-1.2, 1.2):
        pole(g, rk + V(sx, -0.25, 0), rk + V(sx, 1.25, 0), 0.04, 0.035, rng, col=(0.7, 0.6, 0.5), sides=6)
    pole(g, rk + V(-1.35, 1.2, 0), rk + V(1.35, 1.2, 0), 0.035, 0.035, rng, col=(0.7, 0.6, 0.5), sides=6)
    for k in range(14):
        x = -1.1 + k * 0.17 + rng.uniform(-0.03, 0.03)
        torch_stave(g, rng, rk + V(x, 0.0, 0.45 + rng.uniform(-0.05, 0.05)), rk + V(x * 0.98, 1.38, -0.04))
    for k in range(2):
        bc = V(-3.2 + k * 0.9, 0.12, 0.9 + k * 0.4)
        a = 0.3 + k * 0.5
        d = V(math.cos(a), 0, math.sin(a))
        for j in range(9):
            o = V(-d.z, 0, d.x) * ((j % 3) - 1) * 0.05 + V(0, (j // 3) * 0.045, 0)
            torch_stave(g, rng, bc + o - d * 0.55, bc + o + d * 0.55)
        for t in (-0.25, 0.2):
            lashing(g, bc + d * t + V(0, 0.05, 0), d, 0.11, rng, turns=2)
    # Pitch jars, one cracked and bled out.
    for k, (x, z) in enumerate(((2.8, -2.3), (3.3, -1.9), (3.0, -1.4), (3.6, -2.6))):
        jar(g, rng, V(x, -0.03, z), rng.uniform(0.5, 0.7), rng.uniform(0.2, 0.26), col=mix((0.9, 0.6, 0.4), PITCH, 0.35),
            broken=(k == 3))
    tar_pool(g, rng, (3.8, 0, -2.2), 0.3, 0.2)
    # A tarred-hide shade on four poles over the bundles, sagging.
    sh = V(-2.9, 0, 1.2)
    for sx in (-1, 1):
        for sz in (-1, 1):
            c = sh + V(sx * 1.1, 0, sz * 0.9)
            pole(g, c + V(0, -0.25, 0), c + V(0, 1.75, 0), 0.04, 0.035, rng, col=(0.7, 0.6, 0.5), sides=6)
    grid = [[tuple(sh + V(x, 1.72 - 0.12 * math.sin(math.pi * (x + 1.1) / 2.2) * math.sin(math.pi * (z + 0.9) / 1.8), z))
             for z in np.linspace(-0.9, 0.9, 5)] for x in np.linspace(-1.1, 1.1, 6)]
    sheet(g, grid, M_HIDE, lambda u, v: mix((0.45, 0.36, 0.28), (0.1, 0.08, 0.07), 0.35 + 0.3 * u), tile=0.7, double=True)
    # The banner pole (flag at (3.6, 2.5, 2.4)), a goat skull painted black.
    sb = V(3.6, 0, 2.4)
    pole(g, sb + V(0, -0.3, 0), sb + V(0.02, 2.95, 0.0), 0.055, 0.04, rng, col=(0.66, 0.56, 0.46), sides=7)
    skull(g, sb + V(0.02, 3.0, 0.0), 1.2, rng, col=(0.25, 0.22, 0.2), horns=1.1)
    return b


# Pitch pools in camp-local (x, z, rx, rz) — mirrored by camps.rs PITCH_POOLS (they burn once lit).
PITCH_POOLS = ((1.6, -1.6, 0.45, 0.3), (-2.4, -1.2, 0.35, 0.5), (-1.1, 0.4, 0.3, 0.22), (2.6, 0.9, 0.25, 0.35))


# ─────────────────────────────────────────────────────────────── GRASS SEAM: the Reed Hide
def reed_clump(g, rng, c, r, n, h, lean=0.0, yaw=0.0):
    c = Vector(c)
    for k in range(n):
        a = rng.uniform(0, 6.28)
        d = rng.uniform(0, r)
        foot = c + V(math.cos(a) * d, -0.08, math.sin(a) * d)
        hh = h * rng.uniform(0.7, 1.1)
        bend = V(math.sin(yaw) * lean + rng.uniform(-0.08, 0.08), 0, math.cos(yaw) * lean + rng.uniform(-0.08, 0.08))
        tip = foot + V(0, hh, 0) + bend * hh * 0.25
        tube(g, [foot, foot.lerp(tip, 0.6) + bend * 0.04, tip], [0.014, 0.011, 0.003], 4, M_CLOTH,
             mix(REED, (0.75, 0.82, 0.45), rng.uniform(0.0, 0.45)), tile=0.5, cap=False)
        if k % 5 == 0:
            tube(g, [tip - V(0, 0.18, 0), tip + V(0, 0.02, 0)], [0.018, 0.006], 4, M_CLOTH, (0.42, 0.3, 0.2), tile=0.2)


def camp_reeds(rng):
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 1.0)
    # (The trampled floor is baked into the terrain mask — camps.rs `ground_wear`.) The hide sits
    # IN a reedbed: a thick wall of reeds and rank grass all round, broken only where feet go.
    gaps = (0.0, math.pi * 0.62, math.pi * 1.32)  # +Z the spy slot / way out, a side run, the back path
    for k in range(64):
        a = k / 64 * 2 * math.pi + rng.uniform(-0.03, 0.03)
        gd = min(abs(math.atan2(math.sin(a - q), math.cos(a - q))) for q in gaps)
        if gd < 0.17:
            continue
        rr = rng.uniform(4.3, 5.4)
        p = V(math.sin(a) * rr, 0, math.cos(a) * rr)
        if k % 2:
            reed_clump(g, rng, p, 0.55, 24, rng.uniform(1.7, 2.3), lean=0.12, yaw=a + math.pi)
        else:
            tall_grass(g, rng, p, 0.6, 40, rng.uniform(0.9, 1.3))
    for q in gaps:
        flattened_reeds(g, rng, V(math.sin(q) * 4.7, 0, math.cos(q) * 4.7), q, 0.9, 2.0, 26)
    for k in range(10):
        a = rng.uniform(0, 6.28)
        tall_grass(g, rng, V(math.sin(a) * rng.uniform(2.0, 3.2), 0, math.cos(a) * rng.uniform(2.0, 3.2)), 0.25, 10, 0.45)
    # The screen: bundled reeds on two rails, an arc facing the walls (+Z), crouch height, with a
    # slot left open to watch through.
    R = 3.4
    for k in range(-13, 14):
        a = k * 0.085
        if abs(k) <= 1:
            continue  # the spy slot
        p = V(math.sin(a) * R, 0, math.cos(a) * R)
        reed_clump(g, rng, p, 0.12, 9, 1.35, lean=0.05, yaw=a)
        if k % 4 == 0:
            pole(g, p + V(0, -0.25, 0), p + V(0, 1.2, 0), 0.03, 0.025, rng, col=(0.66, 0.58, 0.46), sides=5)
    for y in (0.45, 0.95):
        pts = [V(math.sin(k * 0.085) * (R - 0.08), y, math.cos(k * 0.085) * (R - 0.08)) for k in range(-13, 14)]
        tube(g, pts, [0.02] * len(pts), 5, M_BARK, (0.66, 0.58, 0.46), tile=0.5, cap=False)
    # Wild reeds thick all round the back: the hide is IN the reedbed.
    for (x, z, r, n) in ((-4.3, -1.5, 0.8, 60), (-3.4, -3.8, 1.0, 70), (-0.8, -4.6, 1.0, 70), (2.0, -4.3, 1.0, 70),
                         (4.2, -2.4, 0.8, 60), (4.6, 0.6, 0.6, 40), (-4.6, 1.0, 0.6, 40)):
        reed_clump(g, rng, (x, 0, z), r, n, 1.9, lean=0.1, yaw=rng.uniform(0, 6.28))
    # THE MODEL OF OUR FORT, pressed out of clay on a smoothed patch: square curtain with corner
    # towers and the keep, the gate gap toward the scouts, a stick palisade round it. Black pebbles
    # (orks) march in a column at the gate and a second line curls round to the west side gate; a
    # few white pebbles (defenders) stand at the front. Scored arrows mark the flank; a pointer lies by.
    fc = V(0.0, 0.0, 0.9)
    mound(g, tuple(fc + V(0, -0.01, 0)), 1.25, 1.05, 0.05, rng, mat=M_EARTH,
          col_fn=lambda p, n: scale((0.66, 0.54, 0.42), 0.92 + 0.08 * nz(p * 6)), tile=0.4, rings=3, seg=20, skirt=0.04)
    W_, H_ = 0.5, 0.42
    wall_h = 0.11
    for (a, bb) in ((V(-W_, 0, -H_), V(W_, 0, -H_)), (V(W_, 0, -H_), V(W_, 0, H_)), (V(-W_, 0, H_), V(-0.07, 0, H_)),
                    (V(0.07, 0, H_), V(W_, 0, H_)), (V(-W_, 0, -H_), V(-W_, 0, -0.06)), (V(-W_, 0, 0.06), V(-W_, 0, H_))):
        d = bb - a
        lbox(g, fc + (a + bb) / 2 + V(0, 0.045 + wall_h / 2, 0), (0.05, wall_h, d.length), quat_y(math.atan2(d.x, d.z)),
             M_EARTH, scale(CLAY, rng.uniform(0.88, 1.0)), tile=0.3)
    # Merlons pinched up along every wall top.
    for (a, bb) in ((V(-W_, 0, -H_), V(W_, 0, -H_)), (V(W_, 0, -H_), V(W_, 0, H_)), (V(-W_, 0, -H_), V(-W_, 0, H_)),
                    (V(-W_, 0, H_), V(W_, 0, H_))):
        for t in np.linspace(0.08, 0.92, 9):
            p = a.lerp(bb, t)
            if abs(p.z - H_) < 0.01 and abs(p.x) < 0.1:
                continue
            if abs(p.x + W_) < 0.01 and abs(p.z) < 0.07:
                continue
            lbox(g, fc + p + V(0, 0.045 + wall_h + 0.016, 0), (0.035, 0.032, 0.035), quat_y(0.0), M_EARTH,
                 scale(CLAY, rng.uniform(0.85, 1.0)), tile=0.2)
    # Corner towers (round, crenellated rims) and two gate towers flanking the front gap.
    for (tx, tz, tr) in ((-W_, -H_, 0.075), (W_, -H_, 0.075), (-W_, H_, 0.075), (W_, H_, 0.075), (-0.12, H_, 0.055), (0.12, H_, 0.055)):
        tc = fc + V(tx, 0, tz)
        frustum(g, tr, tr * 0.85, 0.04, 0.2, 10, M_EARTH, scale(CLAY, 0.95), tile=0.3, centre=tuple(tc))
        for j in range(5):
            a = j / 5 * 6.28
            lbox(g, tc + V(math.cos(a) * tr * 0.8, 0.25, math.sin(a) * tr * 0.8), (0.025, 0.03, 0.025), quat_y(a), M_EARTH,
                 scale(CLAY, 0.9), tile=0.2)
    # The gate: a bark-chip leaf hanging half open, a lintel of twig over it.
    lbox(g, fc + V(-0.04, 0.1, H_ + 0.03), (0.07, 0.09, 0.008), quat_y(0.6), M_BARK, (0.42, 0.3, 0.2), tile=0.1)
    tube(g, [fc + V(-0.12, 0.2, H_), fc + V(0.12, 0.2, H_)], [0.008, 0.008], 4, M_BARK, (0.5, 0.42, 0.32), tile=0.1)
    # The keep: a tall block, a stepped top, a twig flagstaff with a scrap of red rag.
    kc = fc + V(0.1, 0, -0.1)
    lbox(g, kc + V(0, 0.16, 0), (0.22, 0.24, 0.2), quat_y(0.0), M_EARTH, scale(CLAY, 0.9), tile=0.3)
    lbox(g, kc + V(0, 0.3, 0), (0.16, 0.06, 0.14), quat_y(0.0), M_EARTH, scale(CLAY, 0.86), tile=0.3)
    for (dx, dz) in ((-0.1, -0.09), (0.1, -0.09), (-0.1, 0.09), (0.1, 0.09), (0, -0.09), (0, 0.09)):
        lbox(g, kc + V(dx, 0.3, dz), (0.03, 0.035, 0.03), quat_y(0.0), M_EARTH, scale(CLAY, 0.82), tile=0.2)
    tube(g, [kc + V(0, 0.32, 0), kc + V(0, 0.52, 0)], [0.004, 0.003], 3, M_BARK, (0.5, 0.42, 0.32), tile=0.1)
    lbox(g, kc + V(0.03, 0.49, 0), (0.06, 0.035, 0.004), quat_y(0.0), M_CLOTH, (0.6, 0.08, 0.05), tile=0.1)
    # The bell tower in the yard (a stub with a pebble bell) and a hall against the west wall.
    frustum(g, 0.04, 0.03, 0.04, 0.22, 8, M_EARTH, scale(CLAY, 0.92), tile=0.3, centre=tuple(fc + V(-0.22, 0, 0.12)))
    lbox(g, fc + V(-0.32, 0.1, -0.15), (0.14, 0.1, 0.32), quat_y(0.0), M_EARTH, scale(CLAY, 0.88), tile=0.3)
    for k in range(34):
        a = k / 34 * 2 * math.pi
        p = fc + V(math.cos(a) * 0.82, 0.03, math.sin(a) * 0.7)
        tube(g, [p, p + V(0, 0.08, 0)], [0.006, 0.005], 3, M_BARK, (0.5, 0.42, 0.32), tile=0.1)

    def pebble(p, white=False):
        s = rng.uniform(0.026, 0.038)
        stone(g, tuple(p + V(0, 0.05, 0)), (s, s * 0.7, s), rng, mat=M_STONE, detail=0,
              col_fn=lambda q, n: (0.85, 0.84, 0.8) if white else (0.08, 0.075, 0.07), tile=0.1, cuts=1)
    for k in range(9):
        pebble(fc + V(rng.uniform(-0.05, 0.05), 0, 0.5 + k * 0.06))
    for k in range(8):
        t = k / 7
        a = math.pi * 0.5 + t * 1.5
        pebble(fc + V(-math.cos(a) * 0.62 - 0.05 * t, 0, math.sin(a) * 0.55 - 0.1))
    for k in range(5):
        pebble(fc + V(rng.uniform(-0.15, 0.15), 0, 0.28 + rng.uniform(-0.04, 0.03)), white=True)
    # Sticks laid as arrows of attack: shafts with two-twig heads, pointing at the gate and round the west.
    def arrow(x0, z0, x1, z1):
        a, bb = fc + V(x0, 0.055, z0), fc + V(x1, 0.055, z1)
        d = (bb - a).normalized()
        sd = V(-d.z, 0, d.x)
        tube(g, [a, bb], [0.009, 0.008], 4, M_BARK, (0.45, 0.36, 0.26), tile=0.1)
        for sg in (-1, 1):
            tube(g, [bb, bb - d * 0.11 + sd * sg * 0.07], [0.008, 0.007], 4, M_BARK, (0.45, 0.36, 0.26), tile=0.1)
    arrow(0.22, 1.2, 0.1, 0.62)
    arrow(-1.0, 0.75, -0.95, 0.15)
    arrow(-0.95, 0.15, -0.62, 0.0)
    arrow(0.85, 1.0, 0.55, 0.55)
    tube(g, [fc + V(0.6, 0.06, 0.95), fc + V(1.3, 0.08, 1.35)], [0.012, 0.009], 4, M_BARK, (0.55, 0.47, 0.38), tile=0.3)
    # Sleeping mats at the back (reed mats under hides), a small dug-in fire (flame at (-2.3, 0, -1.6)),
    # water skins on a stake.
    for k, (x, z, yaw) in enumerate(((-1.2, -2.3, 0.2), (0.2, -2.6, -0.1), (1.6, -2.2, -0.35))):
        rq = quat_y(yaw)
        woven_mat(g, rng, V(x, -0.01, z), yaw)
        grid = [[tuple(V(x, 0.1 + 0.03 * math.sin(i + j), z) + rq @ V((i - 1.5) * 0.22, 0, (j - 2) * 0.32))
                 for j in range(5)] for i in range(4)]
        hc = DARK_HIDE if k % 2 else HIDE
        sheet(g, grid, M_HIDE, lambda u, v, hc=hc: scale(hc, 0.85 + 0.15 * v), tile=0.5)
    firepit(g, rng, (-2.3, 0, -1.6), r=0.32, n=7)
    ash_bed(g, rng, (-2.3, 0, -1.6), 0.6)
    # The fire is covered: a low reed hood on four forked sticks, so no glow shows over the screen.
    fh = V(-2.3, 0, -1.6)
    for sx in (-1, 1):
        for sz in (-1, 1):
            tube(g, [fh + V(sx * 0.62, -0.1, sz * 0.5), fh + V(sx * 0.58, 0.85 + 0.12 * sz, sz * 0.48)], [0.022, 0.018], 5,
                 M_BARK, (0.55, 0.48, 0.38), tile=0.3)
    for k in range(16):
        z = -0.55 + k * 0.073
        tube(g, [fh + V(-0.72, 0.8 + 0.12 * z, z), fh + V(0.0, 0.92 + 0.12 * z, z + 0.02), fh + V(0.72, 0.8 + 0.12 * z, z)],
             [0.02, 0.022, 0.02], 4, M_THATCH, mix(REED, (0.3, 0.26, 0.2), 0.35 + 0.25 * (k % 2)), tile=0.4)
    firewood(g, rng, (-3.2, 0, -0.7), 0.9, n=6, col=(0.55, 0.48, 0.38))
    # Gear: packs and a rolled hide by the mats, a shield face-down, spears stacked on a forked rest.
    for (x, z) in ((-2.6, -2.8), (-1.9, -3.4)):
        stone(g, (x, 0.18, z), (0.24, 0.2, 0.18), rng, mat=M_HIDE, detail=1, cuts=0,
              col_fn=lambda p, n: scale(HIDE, 0.8), tile=0.3)
        cord(g, V(x, 0.36, z), 0.12, rng)
    tube(g, [V(1.4, 0.12, -3.75), V(2.0, 0.12, -3.55)], [0.12, 0.12], 8, M_HIDE, DARK_HIDE, tile=0.3)
    shield(g, V(-1.9, 0.06, -0.5), quat_x(math.pi / 2), 0.38, rng)
    rest = V(1.3, 0, -0.4)
    for sx in (-0.45, 0.45):
        tube(g, [rest + V(sx, -0.1, 0), rest + V(sx, 0.75, 0)], [0.025, 0.02], 5, M_BARK, (0.55, 0.48, 0.38), tile=0.3)
    for k in range(5):
        y = 0.72 + 0.03 * (k % 2)
        spear(g, rest + V(-0.9, 0.02, -0.06 + k * 0.03), rest + V(0.95, y, -0.06 + k * 0.03), rng, col=(0.55, 0.48, 0.38))
    scatter_bones(g, rng, (-2.3, 0, -1.6), 1.1, 6)
    sunk_stones(g, rng, (0, 0, 0), 3.4, 10, col=(0.5, 0.5, 0.46), big=0.14)
    sk = V(2.6, 0, -1.3)
    pole(g, sk + V(0, -0.2, 0), sk + V(0, 1.3, 0), 0.03, 0.025, rng, col=(0.62, 0.55, 0.45), sides=5)
    for k in range(2):
        stone(g, tuple(sk + V(0.12 * (k * 2 - 1), 0.95 - 0.12 * k, 0.05)), (0.09, 0.15, 0.07), rng, mat=M_HIDE, detail=1,
              cuts=0, col_fn=lambda p, n: (0.5, 0.38, 0.26), tile=0.2)
    for a in (-0.75, -0.6, 0.62):
        foot = V(math.sin(a) * (R - 0.5), 0.0, math.cos(a) * (R - 0.5))
        spear(g, foot, foot + V(math.sin(a) * 0.4, 1.9, math.cos(a) * 0.4), rng, col=(0.55, 0.48, 0.38))
    # Banner pole (flag at (2.9, 2.5, -2.6)): a reed-tufted stave.
    sb = V(2.9, 0, -2.6)
    pole(g, sb + V(0, -0.3, 0), sb + V(0.02, 2.95, 0.0), 0.05, 0.035, rng, col=(0.66, 0.58, 0.46), sides=7)
    reed_clump(g, rng, sb + V(0, 2.4, 0), 0.04, 8, 0.6)
    return b


# ─────────────────────────────────────────────────────────────── ROCKY: the Eyrie
def camp_eyrie(rng):
    b = Builder()
    g = G(b)
    nz = Noise(rng, 5, 0.5)
    cf = rock_col((0.86, 0.84, 0.8), moss=0.25, ground=0.0, noise=nz)
    # (The trampled ground is baked into the terrain mask — camps.rs `ground_wear`.)
    ash_bed(g, rng, (-1.6, 0, 1.4), 0.8)
    scatter_bones(g, rng, (-1.6, 0, 1.4), 1.4, 8, skulls=1)
    firewood(g, rng, (-3.0, 0, 0.6), 1.3, n=7, col=(0.6, 0.55, 0.48))
    sunk_stones(g, rng, (0, 0, 0.6), 4.4, 30, col=(0.72, 0.7, 0.66), big=0.28)
    # The crag: jointed blocks, sheer on the camp side, its top a flat perch at ~3.75.
    stone(g, (0.0, 1.5, -3.2), (2.9, 2.4, 1.9), rng, detail=3, rough=0.1, cuts=3, col_fn=cf, tile=1.6, flat_y=0.95)
    slab(g, (-0.3, 3.4, -3.3), (3.6, 0.7, 2.6), quat_y(0.08), rng, res=(6, 2, 4), round_r=0.15, rough=0.04, cuts=1,
         col_fn=cf, tile=1.4)
    stone(g, (-2.6, 0.9, -2.4), (1.2, 1.3, 1.1), rng, detail=2, col_fn=cf, tile=1.2)
    stone(g, (2.7, 0.7, -2.6), (1.1, 1.0, 1.0), rng, detail=2, col_fn=cf, tile=1.2)
    for k in range(10):
        p = V(rng.uniform(-3.5, 3.5), 0.05, rng.uniform(-1.2, -0.5))
        s = rng.uniform(0.12, 0.35)
        stone(g, tuple(p), (s, s * 0.6, s * 0.8), rng, detail=1, col_fn=cf, tile=0.6)
    # The perch: planks pegged on top, a wattle breastwork on the camp edge, a hide to lie on.
    top_y = 3.75
    for k in range(8):
        x = -1.2 + k * 0.3
        board(g, V(x, top_y, -3.0), (0, 0, 1), (0, 1, 0), 1.6, 0.28, 0.05, mat=M_PLANK, col=TIMBER, rng=rng)
    for k in range(7):
        x = -1.2 + k * 0.38
        pole(g, V(x, top_y - 0.1, -2.15), V(x, top_y + 0.7, -2.15), 0.025, 0.02, rng, col=(0.6, 0.54, 0.46), sides=5)
    for y in (top_y + 0.25, top_y + 0.45, top_y + 0.62):
        tube(g, [V(-1.25, y, -2.15), V(1.1, y, -2.15)], [0.018, 0.018], 4, M_BARK, (0.6, 0.54, 0.46), tile=0.4)
    grid = [[(x, top_y + 0.04, z) for z in np.linspace(-3.6, -2.5, 3)] for x in np.linspace(-1.0, 0.6, 4)]
    sheet(g, grid, M_HIDE, lambda u, v: DARK_HIDE, tile=0.6)
    # The rope ladder down the sheer face: two ropes and lashed rungs.
    lx, lz = 0.9, -1.25
    for sx in (-0.22, 0.22):
        tube(g, [V(lx + sx, top_y + 0.05, -2.05), V(lx + sx, top_y - 0.1, lz - 0.05), V(lx + sx * 1.05, 0.0, lz + 0.05)],
             [0.014] * 3, 4, M_CLOTH, ROPE, tile=0.2, cap=False)
    for k in range(11):
        y = 0.3 + k * 0.32
        tube(g, [V(lx - 0.24, y, lz), V(lx + 0.24, y, lz)], [0.02, 0.02], 5, M_BARK, (0.62, 0.55, 0.45), tile=0.3)
    # The war horn on its post at the ladder foot (camps.rs EYRIE_HORN = (2.6, 0.6)): a great curved
    # horn bound with rawhide, hanging mouth-down from a crossbar.
    hp = V(2.6, 0, 0.6)
    pole(g, hp + V(0, -0.3, 0), hp + V(0, 2.3, 0), 0.07, 0.06, rng, col=(0.66, 0.6, 0.52), sides=7)
    tube(g, [hp + V(-0.5, 2.05, 0), hp + V(0.55, 2.05, 0)], [0.04, 0.04], 6, M_BARK, (0.66, 0.6, 0.52), tile=0.4)
    lashing(g, hp + V(0, 2.05, 0), (1, 0, 0), 0.08, rng, turns=2)
    hb = hp + V(0.45, 1.85, 0)
    pts = [hb + V(-0.05 * t - 0.25 * t * t, -0.25 * t + 0.35 * t * t, 0.1 * t) for t in np.linspace(0, 1.6, 8)]
    radii = [0.035 + 0.075 * (k / 7) ** 1.6 for k in range(8)]
    tube(g, pts, radii, 10, M_STONE, (1.05, 0.95, 0.78), tile=0.3,
         col_fn=lambda t: mix((1.05, 0.95, 0.78), (0.35, 0.28, 0.22), smoothstep(0.4, 0.0, t)))
    for k in (2, 4, 6):
        lashing(g, pts[k], (pts[k + 1] - pts[k - 1]).normalized(), radii[k] + 0.012, rng, turns=2)
    for e, x in ((pts[1], 0.45), (pts[6], -0.35)):
        tube(g, [hp + V(x, 2.03, 0), e], [0.008] * 2, 3, M_CLOTH, RAWHIDE, tile=0.2, cap=False)
    # Throwing stones heaped by the post and up on the perch.
    for (c, n) in ((V(1.7, 0, 1.3), 22), (V(-0.9, top_y, -3.4), 10)):
        for k in range(n):
            s = rng.uniform(0.07, 0.13)
            p = c + V(rng.normal() * 0.22, s * 0.6 + 0.08 * (k // 7), rng.normal() * 0.18)
            stone(g, tuple(p), (s, s * 0.8, s * 0.9), rng, detail=1, col_fn=cf, tile=0.3)
    # The scouts' fire (flame at (-1.6, 0, 1.4)), a hide shelter tucked under the crag.
    firepit(g, rng, (-1.6, 0, 1.4), r=0.38, n=8)
    sh = V(-2.4, 0, -0.9)
    for sx in (-0.8, 0.8):
        pole(g, sh + V(sx, -0.2, 0.6), sh + V(sx * 0.6, 1.25, -0.3), 0.035, 0.03, rng, col=(0.62, 0.55, 0.46), sides=6)
    grid = [[tuple(sh + V(x, 1.22 * (1 - u), 0.6 * u - 0.3 * (1 - u))) for x in np.linspace(-0.85, 0.85, 4)]
            for u in np.linspace(0, 1, 4)]
    sheet(g, grid, M_HIDE, lambda u, v: scale(HIDE, 0.8 + 0.2 * u), tile=0.6, double=True)
    # Banner pole planted up on the perch (flag at (-1.25, 6.2, -3.6)).
    sb = V(-1.25, top_y, -3.6)
    pole(g, sb + V(0, -0.3, 0), sb + V(0.02, 2.75, 0.0), 0.05, 0.035, rng, col=(0.66, 0.6, 0.52), sides=7)
    feather(g, sb + V(0.02, 2.55, 0.0), rng)
    return b


# ─────────────────────────────────────────────────────────────── SNOW: Skarn's Ring
def red_hand_banner(g, rng, base, yaw):
    """A tall standard: crossbar, a long hide hanging from it, a red hand daubed on it."""
    base = Vector(base)
    rq = quat_y(yaw)
    pole(g, base + V(0, -0.35, 0), base + V(0, 3.6, 0), 0.07, 0.05, rng, col=(0.62, 0.55, 0.47), sides=8)
    tube(g, [base + rq @ V(-0.55, 3.25, 0.05), base + rq @ V(0.55, 3.25, 0.05)], [0.035, 0.035], 6, M_BARK,
         (0.62, 0.55, 0.47), tile=0.4)
    skull(g, base + V(0, 3.62, 0), 1.4, rng, horns=1.3, yaw=yaw)
    Wd, Hd = 1.0, 1.8
    grid = []
    for i in range(13):
        row = []
        for j in range(17):
            u, v = i / 12, j / 16
            x = (u - 0.5) * Wd * (1 - 0.08 * v)
            y = 3.22 - v * Hd
            z = 0.07 + 0.04 * math.sin(v * 5 + u * 2) + (0.06 * math.sin(u * 13) if v > 0.9 else 0)
            row.append(tuple(base + rq @ V(x, y, z)))
        grid.append(row)

    def hand(u, v):
        # Hand in banner UV (u across, v down): palm + four fingers up + thumb, dripping below.
        x, y = (u - 0.5) * 2.0, (v - 0.45) * 2.0
        palm = (x / 0.42) ** 2 + ((y - 0.2) / 0.36) ** 2 < 1.0
        fingers = any(abs(x - fx) < 0.085 and -0.55 + abs(fx) * 0.35 < y < 0.0 for fx in (-0.27, -0.09, 0.09, 0.27))
        thumb = x < -0.3 and abs((x + 0.42) - (y - 0.25) * 0.6) < 0.09 and -0.05 < y < 0.4
        drip = any(abs(x - dx) < 0.03 and 0.5 < y < 0.5 + dl for dx, dl in ((-0.2, 0.3), (0.05, 0.45), (0.25, 0.2)))
        if palm or fingers or thumb or drip:
            return (0.5, 0.05, 0.03)
        return scale((0.72, 0.62, 0.5), 0.8 + 0.2 * math.sin(u * 9 + v * 4))
    sheet(g, grid, M_HIDE, hand, tile=0.5, double=True)


def camp_ring(rng):
    b = Builder()
    g = G(b)
    nzs = Noise(rng, 4, 1.0)
    # Deep clean snow all round, the ring trampled down to dirty packed snow and frozen mud.
    mound(g, (0, 0, 0), 4.9, 4.7, 0.05, rng, mat=M_SNOW,
          col_fn=lambda p, n: mix((0.9, 0.92, 0.96), (0.66, 0.66, 0.68), smoothstep(4.0, 3.0, math.hypot(p.x, p.z))),
          tile=1.8, rings=5, seg=26, skirt=0.12, rough=0.25, edge=0.12, power=0.5)
    mound(g, (0, 0.01, 0), 3.15, 3.15, 0.03, rng, mat=M_EARTH,
          col_fn=lambda p, n: mix((0.36, 0.32, 0.28), (0.66, 0.66, 0.68), smoothstep(-0.2, 0.6, nzs(p * 1.6))), tile=1.0,
          rings=5, seg=28, skirt=0.06, edge=0.06, power=0.3)
    for k in range(40):
        a = rng.uniform(0, 6.28)
        d = rng.uniform(0.3, 2.9)
        lbox(g, V(math.cos(a) * d, 0.035, math.sin(a) * d), (0.13, 0.008, 0.3), quat_y(rng.uniform(0, 3.14)), M_EARTH,
             (0.24, 0.21, 0.19), tile=0.2)
    for k in range(7):
        p = V(rng.uniform(-2, 2), 0.04, rng.uniform(-2, 2))
        disc(g, p, quat_y(rng.uniform(0, 3)), rng.uniform(0.06, 0.16), 0.006, 9, M_SNOW, (0.3, 0.04, 0.04), tile=0.3)
    # The fence: spears driven in at r 3.6, crowned with skulls or antlers, thongs strung between
    # them hung with bones. A gap to the north (-Z) is the way in.
    R = 3.6
    n = 18
    tops = []
    for k in range(n):
        a = k / n * 2 * math.pi
        if abs(math.sin(a) + 1) < 0.08:
            tops.append(None)
            continue
        foot = V(math.cos(a) * R, -0.3, math.sin(a) * R)
        top = foot + V(math.cos(a) * 0.12, 2.0 + 0.2 * math.sin(k * 2.3), math.sin(a) * 0.12)
        spear(g, foot, top + V(0, 0.3, 0), rng, col=(0.55, 0.48, 0.38))
        if k % 3 == 0:
            antlers(g, top - V(0, 0.15, 0), 0.8, rng, yaw=-a + math.pi / 2)
        else:
            skull(g, top - V(0, 0.12, 0), 1.25, rng, horns=1.0 if k % 3 == 1 else 0.0, yaw=-a - math.pi / 2)
        tops.append(top - V(0, 0.45, 0))
    for k in range(n):
        a_, b_ = tops[k], tops[(k + 1) % n]
        if a_ is None or b_ is None:
            continue
        mid = a_.lerp(b_, 0.5) - V(0, 0.25, 0)
        tube(g, [a_, mid, b_], [0.007] * 3, 3, M_CLOTH, RAWHIDE, tile=0.2, cap=False)
        if k % 2 == 0:
            bot = cord(g, mid, 0.18, rng, col=RAWHIDE, r=0.005)
            bone(g, bot, bot + V(0.0, -0.1, 0.01), 0.008, rng)
    for k in range(10):
        a = k / 10 * 2 * math.pi + 0.3
        drift(g, (math.cos(a) * 4.4, 0, math.sin(a) * 4.3), rng.uniform(1.1, 1.6), rng.uniform(0.5, 0.7), rng.uniform(0.25, 0.4), rng)
    ash_bed(g, rng, (2.2, 0, -3.6), 0.75)
    scatter_bones(g, rng, (0, 0, 0), 2.6, 14, skulls=1)
    firewood(g, rng, (3.4, 0, -2.6), 0.4, n=8, col=(0.58, 0.52, 0.45))
    # The bench of logs on stump legs just outside the ring (south-east), furs on it.
    bc = V(2.6, 0, 3.75)
    rq = quat_y(-0.62)
    for sx in (-0.9, 0.9):
        pole(g, bc + rq @ V(sx, -0.2, 0), bc + rq @ V(sx, 0.38, 0), 0.17, 0.16, rng, col=(0.66, 0.6, 0.52), sides=9, segs=1)
    pole(g, bc + rq @ V(-1.3, 0.48, 0), bc + rq @ V(1.3, 0.48, 0), 0.2, 0.19, rng, col=(0.66, 0.6, 0.52), sides=10, segs=2)
    sheet(g, [[tuple(bc + rq @ V(s * 0.5 - 0.3, 0.68 - 0.15 * abs(dd), dd * 0.26)) for dd in (-1, 0, 1)] for s in (-1, 0, 1)],
          M_HIDE, lambda u, v: scale((0.3, 0.26, 0.22), 0.9 + 0.2 * v), tile=0.5, double=True)
    # The weapon rack (south-west): a log frame, axes and studded clubs hung on it.
    wr = V(-3.0, 0, 3.4)
    rq = quat_y(0.7)
    for sx in (-0.85, 0.85):
        pole(g, wr + rq @ V(sx, -0.25, 0), wr + rq @ V(sx, 1.35, 0), 0.05, 0.045, rng, col=(0.62, 0.55, 0.47), sides=6)
    for y in (0.55, 1.25):
        pole(g, wr + rq @ V(-1.0, y, 0), wr + rq @ V(1.0, y, 0), 0.04, 0.04, rng, col=(0.62, 0.55, 0.47), sides=6)
    for k in range(5):
        x = -0.65 + k * 0.32
        grip = wr + rq @ V(x, 0.15, 0.12)
        head = wr + rq @ V(x + 0.03, 1.3, 0.08)
        if k % 2 == 0:
            felling_axe(g, rng, grip, head, rq @ V(0, 0, 1))
        else:
            tube(g, [grip, head - V(0, 0.25, 0), head], [0.025, 0.045, 0.06], 7, M_PLANK, (0.5, 0.4, 0.3), tile=0.3)
            for j in range(4):
                stone(g, tuple(head - V(0, 0.08 + j * 0.05, 0) + rq @ V(0.05 * (j % 2 * 2 - 1), 0, 0.05)), (0.02, 0.04, 0.02),
                      rng, mat=M_IRON, detail=0, col_fn=lambda p, nn: (0.35, 0.33, 0.31), tile=0.2, cuts=0)
    # A whetstone on a stump, a broken shield thrown down at the ring's edge.
    stone(g, (-3.9, 0.45, 2.0), (0.22, 0.1, 0.12), rng, detail=1, col_fn=lambda p, n: (0.5, 0.5, 0.52), tile=0.3)
    pole(g, V(-3.9, -0.1, 2.0), V(-3.9, 0.36, 2.0), 0.2, 0.19, rng, col=(0.62, 0.56, 0.5), sides=9, segs=1)
    shield(g, V(1.8, 0.06, -2.1), quat_x(0.08) @ quat_y(0.6), 0.38, rng, broken=True, paint=(0.4, 0.06, 0.04))
    # Skarn's standard at the ring's head (north, by the gap); the brazier fire (flame at (2.2, 0, -3.6)).
    red_hand_banner(g, rng, V(-1.4, 0, -3.95), 0.0)
    firepit(g, rng, (2.2, 0, -3.6), r=0.42, stone_col=(0.72, 0.72, 0.74))
    # The banner pole for the faction flag (flag at (4.2, 2.5, -1.4)).
    sb = V(4.2, 0, -1.4)
    pole(g, sb + V(0, -0.3, 0), sb + V(0.02, 2.95, 0.0), 0.055, 0.04, rng, col=(0.62, 0.55, 0.47), sides=7)
    return b


MODELS = {
    "ork_camp_shaman": camp_shaman,
    "ork_camp_raiders": camp_raiders,
    "ork_camp_cave": camp_cave,
    "ork_camp_stilts": camp_stilts,
    "ork_camp_hunters": camp_hunters,
    # WP1 (camps.rs indexes 5-9, appended so the seeds of the first five never move).
    "ork_camp_ram": camp_ram,
    "ork_camp_pitch": camp_pitch,
    "ork_camp_reeds": camp_reeds,
    "ork_camp_eyrie": camp_eyrie,
    "ork_camp_ring": camp_ring,
    "ork_camp_ram_beam": camp_ram_beam,
    "ork_camp_ram_burnt": camp_ram_burnt,
}
MODELS.update(ork_folk.MODELS)  # outcast niche + sign, war-trail post (src/war_party.rs)

if __name__ == "__main__":
    clear_scene()
    objs = []
    only = set(sys.argv[sys.argv.index("--") + 1:]) if "--" in sys.argv else set()
    for i, (name, fn) in enumerate(MODELS.items()):
        if only and name not in only:
            continue
        b = fn(np.random.default_rng(7300 + i))
        print(f"{name}: {bounds(b)}")
        objs.append(b.build(name, MATS))
    export_glb(OUT / ("ork_camps.glb" if not only else "ork_camps_partial.glb"), objs)
    print("ORK_CAMPS_DONE")
