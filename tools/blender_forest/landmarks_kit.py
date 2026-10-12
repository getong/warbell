"""The biome signature landmarks as real models -> landmarks.glb (src/ruins.rs populate_landmarks).

Each replaces the static low-poly body of a `landmark_models.rs` set-piece; the animated parts
(glows, wisps, smoke, the orbiting ice splinters, the sun-disc) stay procedural and keep their
anchors, so every model keeps the original's footprint, heights and the faces those parts sit on.
Authored in the landmark's MODEL-LOCAL game units (the spawn scales it 1.4-1.5) through geo.py,
reusing wayside_models.py's primitives. Each biome keeps its own material palette:

  lm_witch_hut       swamp  - rotted oak stilts in a peat hummock, nailed-board cabin under a sodden
                              reed thatch, a fieldstone flue, an iron cauldron on its fire ring, bones.
  lm_frozen_spire    snow   - a blade of old blue ice punched up through a frost tor, burst floe
                              slabs heaved round it, drifted snow (`ice`: untextured, vertex colour).
  lm_sunken_pyramid  desert - six worn sandstone tiers (s_ashlar tinted ochre) drowning in a dune,
                              the processional stair, the summit shrine with its cracked turquoise
                              tiles, a toppled obelisk and a colossus head buried to the chin.
  lm_standing_stones rocky  - six lichened granite monoliths and their lintel, the fallen seventh,
                              the altar, waystones, cairns and talus.
  lm_keystone        rocky  - the cracked block hovering over the altar (an animated part).
  lm_mill_vane       forest - the Old Mill's iron weathervane (an animated part).

    blender -b --factory-startup --python tools/blender_forest/landmarks_kit.py
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
                            M_FRUIT, M_TIMBER, V, beam, board, bounds, lbox, mix, mound, pole, rock_col, scale,
                            slab, smooth_mesh, smoothstep, stone, tube, Noise)

M_SNOW = len(W.MATS)
M_ICE = M_SNOW + 1
M_ASHLAR = M_SNOW + 2
M_RUBBLE = M_SNOW + 3
MATS = W.MATS + ["s_snow", "ice", "s_ashlar", "s_rubble"]
M_PLASTER = len(MATS)
MATS += ["s_plaster"]

BONE = (0.86, 0.8, 0.66)
IRON = (0.36, 0.34, 0.33)
SNOW = (0.93, 0.95, 1.0)


def lathe(g, profile, sides, centre, mat, col_fn, tile=0.8):
    """Surface of revolution from a (radius, y) profile (bottom -> top, outside then lip/inside)."""
    c = Vector(centre)
    grid = []
    for r, y in profile:
        row = []
        for s in range(sides + 1):
            a = 2 * math.pi * s / sides
            row.append(c + Vector((math.cos(a) * r, y, math.sin(a) * r)))
        grid.append(row)
    n = len(profile) - 1

    def cf(u, v):  # sheet hands (profile t, around t): rebuild a point + a rough outward normal
        k = min(int(round(u * n)), n)
        a = 2 * math.pi * v
        r, y = profile[k]
        return col_fn(c + Vector((math.cos(a) * r, y, math.sin(a) * r)), Vector((math.cos(a), 0.3, math.sin(a))).normalized())
    sheet(g, grid, mat, cf, tile=tile, double=True)


# ─────────────────────────────────────────────────────────────── swamp: the witch's hut
def lm_witch_hut(rng):
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 1.5)
    peat = lambda p, n: scale((0.42, 0.36, 0.3), (0.8 + 0.2 * nz(p * 2.0)) * (0.75 + 0.25 * smoothstep(0.0, 0.25, p.y)))
    # The hummock the stilts stand in: black peat, wetter (darker) at the rim.
    mound(g, (0.0, -0.08, 0.0), 2.5, 2.25, 0.22, rng, mat=M_EARTH, col_fn=peat, tile=1.4, rings=6, seg=22, skirt=0.2)
    mound(g, (1.75, -0.05, 1.3), 0.9, 0.8, 0.12, rng, mat=M_EARTH, col_fn=lambda p, n: (0.3, 0.28, 0.26), tile=1.0,
          rings=3, seg=14)

    rot_wood = W.weathered((0.62, 0.56, 0.5), damp=0.35, top=1.0)
    # ── Stilts: six crooked oak posts, splayed feet sunk in the mire, tops under the joists.
    feet = [(-1.0, -0.85, 0.1, 0.3), (0.95, -0.9, -0.08, 1.2), (-1.05, 0.8, 0.12, 2.4), (1.0, 0.85, -0.1, 3.6),
            (0.0, -0.95, 0.06, 4.2), (0.05, 0.9, -0.07, 5.1)]
    for x, z, tilt, yaw in feet:
        lean = V(math.cos(yaw) * tilt, 0, math.sin(yaw) * tilt)
        pole(g, V(x, -0.35, z) + lean * 1.4, V(x, 1.3, z), 0.11, 0.09, rng, sides=8, wobble=0.02,
             col_fn=rot_wood, tile=0.8)
    # Cross-braces stilt to stilt, lashed.
    beam(g, [V(-1.0, 0.1, -0.88), V(0.95, 1.15, -0.9)], 0.08, 0.07, col=(0.55, 0.5, 0.45), rng=rng)
    beam(g, [V(0.98, 0.15, 0.85), V(0.98, 1.1, -0.88)], 0.08, 0.07, col=(0.55, 0.5, 0.45), rng=rng)
    beam(g, [V(-1.03, 1.05, 0.8), V(-1.02, 0.2, -0.85)], 0.08, 0.07, col=(0.5, 0.46, 0.42), rng=rng)
    # ── Joists + plank deck with a drunken cant.
    for x in (-1.0, 0.0, 0.97):
        beam(g, [V(x, 1.27, -1.1), V(x, 1.3 + x * 0.03, 1.12)], 0.14, 0.12, col=(0.58, 0.52, 0.46), rng=rng)
    for i in range(7):
        z = -1.0 + i * 0.335
        ln = 2.55 + rng.uniform(-0.12, 0.1)
        c = scale((0.7, 0.64, 0.56), rng.uniform(0.8, 1.05))
        board(g, (rng.uniform(-0.05, 0.05), 1.39 + z * -0.01, z), (1, rng.uniform(-0.03, 0.03), 0), (0, 1, 0), ln,
              0.32, 0.055, mat=M_PLANK, col=c, rng=rng)
    # Ladder up the front (+Z), two rails + rungs, one rung missing.
    for x in (-0.28, 0.28):
        pole(g, V(x, -0.2, 2.0), V(x, 1.45, 1.42), 0.045, 0.04, rng, col=(0.6, 0.55, 0.48), sides=6)
    for r in range(4):
        if r == 2:
            continue
        t = 0.25 + r * 0.35
        zz = 2.0 - (t + 0.2) / 1.65 * 0.58
        pole(g, V(-0.31, t, zz), V(0.31, t, zz), 0.03, 0.03, rng, col=(0.62, 0.57, 0.5), sides=6)

    # ── Cabin: vertical nailed boards on a squared frame. x -1.0..0.9, z -0.9..0.7, y 1.42..2.9.
    x0, x1, z0, z1, y0, y1 = -1.0, 0.9, -0.9, 0.7, 1.42, 2.9
    wall = lambda: scale((0.66, 0.6, 0.53), rng.uniform(0.72, 1.0))
    door = (0.07, 0.57, 1.45, 2.42)  # x0, x1, y0, y1 of the door hole on the front wall
    win_f = (-0.73, -0.37, 2.13, 2.47)  # front window (glow pane at -0.55, 2.3)
    for face, (a0, a1) in (("front", (x0, x1)), ("back", (x0, x1)), ("left", (z0, z1)), ("right", (z0, z1))):
        n = max(2, int((a1 - a0) / 0.22))
        w = (a1 - a0) / n
        for k in range(n):
            u = a0 + (k + 0.5) * w
            top = y1 - rng.uniform(0.0, 0.06)
            spans = [(y0, top)]
            if face == "front" and door[0] - 0.02 < u < door[1] + 0.02:
                spans = [(door[3], top)]
            if face == "front" and win_f[0] < u < win_f[1]:
                spans = [(y0, win_f[2]), (win_f[3], top)]
            if face == "left" and -0.43 < u < -0.07:
                spans = [(y0, 2.02), (2.38, top)]
            for s0, s1 in spans:
                if s1 - s0 < 0.04:
                    continue
                if face in ("front", "back"):
                    zf = z1 if face == "front" else z0
                    c = V(u, (s0 + s1) / 2, zf)
                    nrm = (0, 0, 1 if face == "front" else -1)
                else:
                    xf = x0 if face == "left" else x1
                    c = V(xf, (s0 + s1) / 2, u)
                    nrm = (-1 if face == "left" else 1, 0, 0)
                board(g, c, (0, 1, 0), nrm, s1 - s0, w * 0.97, 0.05, mat=M_PLANK, col=wall(), rng=rng)
    # Corner posts + sill / plate beams.
    for x, z in ((x0, z1), (x1, z1), (x0, z0), (x1, z0)):
        beam(g, [V(x, y0 - 0.02, z), V(x, y1 + 0.04, z)], 0.14, 0.14, col=(0.5, 0.45, 0.4), rng=rng)
    for y in (y0 + 0.03, y1):
        for p, q in (((x0, z1), (x1, z1)), ((x0, z0), (x1, z0)), ((x0, z0), (x0, z1)), ((x1, z0), (x1, z1))):
            beam(g, [V(p[0], y, p[1]), V(q[0], y, q[1])], 0.1, 0.12, col=(0.5, 0.46, 0.41), rng=rng)
    # The door: dark ledged boards, recessed, a crooked lintel and a bone fetish nailed above it.
    for k in range(3):
        board(g, (door[0] + 0.083 + k * 0.167, (door[2] + door[3]) / 2, z1 - 0.06), (0, 1, 0), (0, 0, 1),
              door[3] - door[2], 0.16, 0.04, mat=M_PLANK, col=scale((0.4, 0.34, 0.28), rng.uniform(0.8, 1.0)), rng=rng)
    beam(g, [V(door[0] - 0.08, door[3] + 0.04, z1 + 0.04), V(door[1] + 0.08, door[3] + 0.08, z1 + 0.04)], 0.12, 0.1,
         col=(0.45, 0.4, 0.35), rng=rng)
    tube(g, [V(0.32, 2.56, z1 + 0.09), V(0.32, 2.75, z1 + 0.09)], [0.025, 0.02], 5, M_FRUIT, BONE, tile=0.3)
    stone(g, (0.32, 2.79, z1 + 0.1), (0.07, 0.06, 0.07), rng, mat=M_FRUIT, detail=1, rough=0.1,
          col_fn=lambda p, n: BONE, tile=0.3)
    # Window frames + a hanging shutter.
    for (cx, cy, cz, nrm) in ((-0.55, 2.3, z1 + 0.02, "z"), (x0 - 0.02, 2.2, -0.25, "x")):
        for d in (-0.19, 0.19):
            if nrm == "z":
                beam(g, [V(cx + d, cy - 0.21, cz), V(cx + d, cy + 0.21, cz)], 0.05, 0.05, col=(0.42, 0.38, 0.33), rng=rng)
                beam(g, [V(cx - 0.22, cy + d, cz), V(cx + 0.22, cy + d, cz)], 0.05, 0.05, col=(0.42, 0.38, 0.33), rng=rng)
            else:
                beam(g, [V(cx, cy - 0.21, cz + d), V(cx, cy + 0.21, cz + d)], 0.05, 0.05, col=(0.42, 0.38, 0.33), rng=rng)
                beam(g, [V(cx, cy + d, cz - 0.22), V(cx, cy + d, cz + 0.22)], 0.05, 0.05, col=(0.42, 0.38, 0.33), rng=rng)
    board(g, (-0.92, 2.22, z1 + 0.06), (0.15, 1, 0), (0, 0, 1), 0.4, 0.2, 0.03, mat=M_PLANK, col=(0.5, 0.45, 0.4),
          rng=rng)

    # ── Roof: a heavy reed thatch, two sagging slopes, moss in the hollows, a ridge roll.
    ridge = (-0.05, 3.74)
    for side, eave in ((-1, (-1.45, 2.86)), (1, (1.38, 2.9))):
        dx, dy = ridge[0] - eave[0], ridge[1] - eave[1]
        length = math.hypot(dx, dy)
        ang = math.atan2(dy, dx) if side < 0 else math.atan2(-dy, -dx)
        # Three overlapping courses, each a touch steeper toward the ridge -> a sag in the slope.
        for k in range(3):
            f0, f1 = k / 3 - 0.02, (k + 1) / 3 + 0.08
            cx = eave[0] + dx * (f0 + f1) / 2
            cy = eave[1] + dy * (f0 + f1) / 2 + 0.06 * k
            moss = (0.55, 0.6, 0.38) if k == 0 else (0.72, 0.66, 0.5)
            lbox(g, V(cx, cy, -0.1 + rng.uniform(-0.02, 0.02)), (length * (f1 - f0) + 0.05, 0.2, 2.45 - k * 0.04),
                 quat_z(ang + side * 0.03 * k), M_THATCH, [scale(moss, 0.8), None, (0.78, 0.72, 0.56)], tile=0.9,
                 grain=0)
    tube(g, [V(ridge[0], ridge[1] + 0.12, -1.3), V(ridge[0] + 0.02, ridge[1] + 0.16, -0.1), V(ridge[0], ridge[1] + 0.1, 1.1)],
         [0.15, 0.17, 0.14], 8, M_THATCH, (0.6, 0.6, 0.42), tile=0.6)
    for x, y, z, r in ((-0.9, 3.12, 0.5, 0.32), (0.75, 3.2, -0.6, 0.28), (-0.5, 3.42, -0.75, 0.24), (0.3, 3.55, 0.35, 0.22)):
        mound(g, (x, y, z), r, r * 1.2, 0.07, rng, mat=M_THATCH, col_fn=lambda p, n: (0.38, 0.46, 0.22), tile=0.5,
              rings=3, seg=10, skirt=0.04)
    # Fieldstone flue through the thatch, its mouth at (-0.66, 4.02, -0.72).
    sc = rock_col((0.72, 0.7, 0.66), moss=0.4, noise=nz)
    for k in range(7):
        y = 2.95 + k * 0.16
        for j in range(5):
            a = j * 2 * math.pi / 5 + k * 0.6
            r = 0.2 - k * 0.006
            stone(g, (-0.68 + math.cos(a) * r, y, -0.72 + math.sin(a) * r), (0.11, 0.08, 0.1), rng, detail=1,
                  col_fn=sc, tile=0.5, cuts=1)
    stone(g, (-0.66, 3.98, -0.72), (0.25, 0.04, 0.24), rng, detail=1, col_fn=lambda p, n: (0.2, 0.19, 0.18), tile=0.5)
    # Lantern bracket over the door (the glowing lantern hangs from (0.78, 2.6, 0.78)).
    beam(g, [V(0.78, 2.64, z1 + 0.02), V(0.78, 2.64, 0.84)], 0.03, 0.03, mat=M_IRON, col=IRON, rng=rng, mode="bark")
    # Charm hooks under the eaves (the charms sway from y 3.05).
    for x, z in ((-1.35, 0.95), (1.25, 0.9), (1.3, -1.0), (-0.2, 1.05)):
        tube(g, [V(x, 3.05, z), V(x, 3.12, z)], [0.012, 0.012], 4, M_CLOTH, (0.5, 0.42, 0.3), tile=0.2)

    # ── Yard: the cauldron on its fire ring (brew surface rides at y 0.94, r 0.31).
    cx, cz = 1.75, 1.3
    ash = lambda p, n: scale((0.22, 0.21, 0.2), 0.8 + 0.3 * nz(p * 4))
    mound(g, (cx, -0.02, cz), 0.62, 0.62, 0.06, rng, mat=M_EARTH, col_fn=ash, tile=0.6, rings=3, seg=14)
    for i in range(7):
        a = i * 2 * math.pi / 7 + 0.2
        stone(g, (cx + math.cos(a) * 0.55, 0.04, cz + math.sin(a) * 0.55), (0.14, 0.1, 0.12), rng, detail=1,
              col_fn=rock_col((0.6, 0.58, 0.55), dark_below=0.5), tile=0.5)
    iron_c = lambda p, n: scale(IRON, 0.75 + 0.25 * smoothstep(0.2, 0.9, n.y + 0.5) + 0.1 * nz(p * 6))
    lathe(g, [(0.08, 0.14), (0.26, 0.18), (0.4, 0.34), (0.44, 0.55), (0.41, 0.78), (0.35, 0.92), (0.37, 0.97),
              (0.33, 0.99), (0.31, 0.93)], 16, (cx, 0, cz), M_IRON, iron_c, tile=0.6)
    for i in range(3):
        a = i * 2 * math.pi / 3 + 0.5
        beam(g, [V(cx + math.cos(a) * 0.3, 0.3, cz + math.sin(a) * 0.3), V(cx + math.cos(a) * 0.36, -0.05, cz + math.sin(a) * 0.36)],
             0.05, 0.05, mat=M_IRON, col=IRON, rng=rng, mode="bark")
    for k in range(4):
        a = rng.uniform(0, 6.28)
        p0 = V(cx + math.cos(a) * 0.2, 0.05, cz + math.sin(a) * 0.2)
        pole(g, p0, p0 + V(math.cos(a + 1.6) * 0.5, 0.02, math.sin(a + 1.6) * 0.5), 0.04, 0.035, rng,
             col_fn=lambda t: mix((0.12, 0.1, 0.09), (0.5, 0.42, 0.35), t), sides=6)
    # Skull stake at the yard's edge, a jawbone at its foot.
    pole(g, V(-1.7, -0.2, 1.5), V(-1.68, 0.98, 1.52), 0.045, 0.035, rng, col=(0.5, 0.45, 0.4), sides=6)
    stone(g, (-1.69, 1.05, 1.53), (0.12, 0.11, 0.14), rng, mat=M_FRUIT, detail=2, rough=0.06, cuts=1,
          col_fn=lambda p, n: scale(BONE, 0.85 + 0.15 * n.y), tile=0.3)
    for k in range(3):
        a = rng.uniform(0, 6.28)
        p0 = V(-1.6 + math.cos(a) * 0.3, 0.03, 1.4 + math.sin(a) * 0.3)
        tube(g, [p0, p0 + V(math.cos(a) * 0.22, 0.01, math.sin(a) * 0.22)], [0.02, 0.016], 5, M_FRUIT, BONE, tile=0.3)
    # Bog toadstools in three clumps.
    for x, z, s in ((-1.35, -0.5, 1.0), (1.3, 0.4, 0.75), (-0.6, 1.25, 0.6)):
        for k in range(3):
            a = k * 2.1 + x
            mx, mz = x + math.cos(a) * 0.14 * s, z + math.sin(a) * 0.14 * s
            h = (0.14 + k * 0.06) * s
            frustum(g, 0.04 * s, 0.03 * s, -0.02, h, 6, M_FRUIT, (0.82, 0.78, 0.68), tile=0.3, centre=(mx, 0, mz))
            mound(g, (mx, h - 0.02, mz), 0.1 * s, 0.1 * s, 0.07 * s, rng, mat=M_FRUIT,
                  col_fn=lambda p, n: (0.45, 0.24, 0.32), tile=0.3, rings=2, seg=8, skirt=0.02)
    # Firewood stacked under the deck.
    for k in range(5):
        y = 0.08 + (k // 3) * 0.13
        zz = -0.6
        x = 0.42 + (k % 3) * 0.15 + (k // 3) * 0.07
        pole(g, V(x, y, zz - 0.38), V(x + 0.03, y, zz + 0.38), 0.07, 0.065, rng, col=(0.62, 0.56, 0.48), sides=7)
    return b


# ─────────────────────────────────────────────────────────────── snow: the frozen spire
def ice_col(nz, deep=0.0):
    body, abyss, rime = (0.3, 0.55, 0.8), (0.07, 0.18, 0.42), (0.8, 0.9, 0.98)

    def f(p, n):
        k = nz(p * 1.3)
        c = mix(body, abyss, min(1.0, max(0.0, deep + 0.35 * k + 0.25)))
        c = mix(c, rime, smoothstep(0.55, 0.95, n.y) * 0.8)  # frost on the up-facing facets
        return mix(c, (0.5, 0.52, 0.55), 0.35 * (1.0 - smoothstep(-0.1, 0.35, p.y)))  # grimy foot
    return f


def facets(g, verts, tris, mat, col_fn, tile):
    """Triangles with FLAT face normals (cleaved crystal faces catch the light as planes)."""
    for a, b_, c in tris:
        pa, pb, pc = verts[a], verts[b_], verts[c]
        n = (pb - pa).cross(pc - pa)
        if n.length < 1e-12:
            continue
        n.normalize()
        ax = max(range(3), key=lambda k: abs(n[k]))
        uv = [((p.z, p.y) if ax == 0 else (p.x, p.z) if ax == 1 else (p.x, p.y)) for p in (pa, pb, pc)]
        g.poly([pa, pb, pc], [(u / tile, v / tile) for u, v in uv], [n, n, n], [col_fn(p, n) for p in (pa, pb, pc)], mat)


def shard(g, base, height, w, d, tilt, yaw, rng, deep=0.0, taper=0.88, cuts=2):
    """An ice crystal standing on `base` (its foot sunk below it), tipped by `tilt` (rad) toward
    `yaw`: an irregular six-sided prism, a waist ring, then a cleaved pyramidal point, flat facets."""
    rot = quat_y(yaw) @ quat_z(-tilt)
    o = Vector(base)
    sides = 6
    phase = rng.uniform(0, 6.28)
    rings = []
    for y_f, r_f in ((-0.06, 1.0), (0.55, 1.0 - taper * 0.25), (0.8, 1.0 - taper * 0.55)):
        ring = []
        for k in range(sides):
            a = phase + k * 2 * math.pi / sides + rng.uniform(-0.18, 0.18)
            rr = r_f * rng.uniform(0.82, 1.12)
            ring.append(o + rot @ V(math.cos(a) * w * 0.5 * rr, height * y_f + rng.uniform(-0.04, 0.04) * height,
                                    math.sin(a) * d * 0.5 * rr))
        rings.append(ring)
    tip = o + rot @ V(rng.uniform(-0.1, 0.1) * w, height, rng.uniform(-0.1, 0.1) * d)
    verts = [p for ring in rings for p in ring] + [tip]
    tris = []
    for r in range(len(rings) - 1):
        for k in range(sides):
            a0, a1 = r * sides + k, r * sides + (k + 1) % sides
            b0, b1 = a0 + sides, a1 + sides
            tris += [(a0, a1, b1), (a0, b1, b0)]
    t = len(verts) - 1
    top0 = (len(rings) - 1) * sides
    tris += [(top0 + k, top0 + (k + 1) % sides, t) for k in range(sides)]
    cen = o + rot @ V(0, height * 0.4, 0)
    fixed = []
    for a, b_, c in tris:  # wind every face outward
        n = (verts[b_] - verts[a]).cross(verts[c] - verts[a])
        fixed.append((a, b_, c) if n.dot((verts[a] + verts[b_] + verts[c]) / 3 - cen) >= 0 else (a, c, b_))
    facets(g, verts, fixed, M_ICE, ice_col(Noise(rng, 3, 1.4), deep), 1.4)


def lm_frozen_spire(rng):
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 1.4)
    frost = lambda p, n: mix(rock_col((0.62, 0.64, 0.68), noise=nz, ground=0.0)(p, n), (0.9, 0.93, 0.98),
                             smoothstep(0.45, 0.85, n.y) * 0.85)
    # Frost tor: three dark boulders the ice tore up through.
    stone(g, (0.0, 0.2, 0.0), (1.1, 0.6, 0.95), rng, col_fn=frost, tile=1.2, rough=0.18, cuts=3)
    stone(g, (0.75, 0.35, -0.45), (0.65, 0.55, 0.55), rng, col_fn=frost, tile=1.0, rough=0.16, cuts=2)
    stone(g, (-0.75, 0.3, 0.45), (0.6, 0.5, 0.55), rng, col_fn=frost, tile=1.0, rough=0.16, cuts=2)
    # Drifted snow banked in a ring, deeper on the windward (-X) side.
    snow = lambda p, n: mix(SNOW, (0.72, 0.8, 0.96), (1.0 - smoothstep(0.1, 0.8, n.y)) * 0.7)
    mound(g, (0.0, -0.18, 0.0), 2.4, 2.2, 0.5, rng, mat=M_SNOW, col_fn=snow, tile=2.0, rings=6, seg=24, skirt=0.25,
          edge=0.3, power=1.3)
    for x, z, r, h in ((-1.3, -0.4, 1.0, 0.45), (0.95, 0.75, 0.8, 0.35), (0.2, -1.2, 0.75, 0.3), (-0.6, 1.1, 0.7, 0.32)):
        mound(g, (x, 0.1, z), r, r * 0.8, h, rng, mat=M_SNOW, col_fn=snow, tile=1.6, rings=4, seg=14, skirt=0.12)
    # The blade: one great flattened crystal (the heart glows on its face at (0.38, 2.35, 0.52)),
    # a darker core shard behind it, a snapped tip leaning off true, flanking splinters.
    shard(g, (0.05, -0.2, 0.05), 6.0, 1.45, 1.05, 0.03, 0.85, rng, deep=0.1, taper=0.9, cuts=2)
    shard(g, (-0.15, 0.0, -0.15), 4.6, 1.0, 0.9, -0.05, 0.4, rng, deep=0.6, taper=0.8)
    shard(g, (0.1, 4.9, 0.05), 1.3, 0.38, 0.3, 0.25, 2.2, rng, deep=0.0, taper=0.85, cuts=1)
    for x, z, h, w, t, yaw, dp in ((0.95, -0.4, 2.7, 0.62, 0.22, 0.4, 0.4), (-0.9, 0.5, 2.2, 0.55, 0.26, 3.5, 0.2),
                                   (-0.55, -0.75, 1.6, 0.45, 0.3, 2.3, -0.1), (0.5, 0.75, 1.3, 0.4, 0.34, -0.9, 0.3),
                                   (0.45, -0.95, 1.1, 0.32, 0.42, 1.0, 0.0)):
        shard(g, (x, 0.0, z), h, w, w * 0.75, t, yaw, rng, deep=dp)
    # Burst ring: floe slabs heaved up and outward, snow on their upper edges.
    for i in range(8):
        a = i * 2 * math.pi / 8 + 0.27
        r = 1.8 + rng.uniform(0.0, 0.45)
        h = 0.55 + rng.uniform(0.0, 0.6)
        rot = quat_y(-(a + math.pi / 2)) @ quat_x(rng.uniform(0.45, 0.75))
        c = V(math.cos(a) * r, h * 0.3 - 0.12, math.sin(a) * r)
        slab(g, tuple(c), (0.85 + rng.uniform(0, 0.3), h, 0.16), rot, rng, mat=M_ICE,
             col_fn=ice_col(Noise(rng, 3, 2.0), rng.uniform(-0.1, 0.4)), tile=1.2, res=(4, 3, 1), round_r=0.03,
             rough=0.03, cuts=1)
    # Shed chips and two icicle spears in the drift.
    for x, z, r in ((1.3, 1.15, 0.13), (-1.2, -1.05, 0.11), (1.5, -0.8, 0.1), (-1.5, 0.7, 0.12), (2.2, 0.3, 0.09)):
        stone(g, (x, 0.08, z), (r, r * 0.6, r * 0.8), rng, mat=M_ICE, detail=1, rough=0.05, cuts=2,
              col_fn=ice_col(nz, -0.2), tile=0.6)
    shard(g, (0.9, -0.1, -1.3), 0.85, 0.14, 0.12, 0.35, 0.3, rng, taper=0.95, cuts=0)
    shard(g, (-1.05, -0.1, 1.25), 0.7, 0.12, 0.1, -0.3, 1.2, rng, taper=0.95, cuts=0)
    return b


# ─────────────────────────────────────────────────────────────── desert: the sunken pyramid
SANDSTONE = (0.86, 0.68, 0.46)
SAND = (0.9, 0.78, 0.56)
TURQ = (0.42, 0.72, 0.7)


def sandstone_col(nz, k=1.0):
    def f(p, n):
        c = scale(SANDSTONE, k * (0.88 + 0.12 * nz(p * 1.5)))
        c = mix(c, (1.0, 0.9, 0.72), smoothstep(0.6, 0.95, n.y) * 0.35)  # wind-scoured sunlit tops
        c = mix(c, (0.68, 0.48, 0.32), 0.4 * smoothstep(0.3, 0.9, -nz(p * 0.6)))  # iron-stained courses
        return mix(c, SAND, 0.4 * (1.0 - smoothstep(-0.1, 0.4, p.y)))  # sand-blasted foot
    return f


def lm_sunken_pyramid(rng):
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 0.9)
    th = 0.6
    # ── Six worn tiers (half-width 2.35 -> 0.62), each sunk 0.12 into the one below.
    for i in range(6):
        w = 2.35 + (0.62 - 2.35) * (i / 5.0)
        y = i * th
        # Rubble core (shows dark through the mortar joints), paved top.
        slab(g, (0, y + th - 0.37, 0), (w * 2 - 0.12, 0.72, w * 2 - 0.12), quat_y(0), rng, mat=M_PLASTER,
             col_fn=sandstone_col(nz, 0.55), tile=1.2, res=(6, 1, 6), round_r=0.02, rough=0.002)
        # Two courses of dressed blocks round the face, joints staggered, a few robbed or slumped.
        for c in range(2):
            yc = y + c * 0.3 + 0.15 - (0.06 if i == 0 and c == 0 else 0.0)
            for side in range(4):
                ax = side % 2  # 0: blocks run along X (front/back faces), 1: along Z
                sgn = 1 if side < 2 else -1
                span = 2 * w if ax == 0 else 2 * w - 0.52
                a = -span / 2
                first = True
                while a < span / 2 - 0.05:
                    ln = rng.uniform(0.55, 0.9) * (0.5 if first and (c + side) % 2 else 1.0)
                    first = False
                    ln = min(ln, span / 2 - a)
                    mid = a + ln / 2
                    a += ln
                    if rng.uniform() < 0.035 and i > 0:
                        continue  # a robbed block: the core shows through
                    slump = rng.uniform(-0.012, 0.012)
                    out = w - 0.13 + rng.uniform(-0.015, 0.02)
                    pos = (mid, yc + slump, sgn * out) if ax == 0 else (sgn * out, yc + slump, mid)
                    size = (ln - 0.03, 0.285, 0.26) if ax == 0 else (0.26, 0.285, ln - 0.03)
                    slab(g, pos, size, quat_y(rng.uniform(-0.02, 0.02)), rng, mat=M_PLASTER,
                         col_fn=sandstone_col(nz, rng.uniform(0.88, 1.08)), tile=0.9, res=(2, 1, 1), round_r=0.035,
                         rough=0.01, cuts=1 if rng.uniform() < 0.25 else 0)
        # Fallen blocks at the tier's foot, tipped and half in the sand.
        for k in range(2):
            ang = rng.uniform(0, 6.28)
            r = w + rng.uniform(0.2, 0.6)
            px, pz = math.cos(ang) * r, math.sin(ang) * r
            if pz > 1.5 and abs(px) < 0.8:
                continue  # keep the stair clear
            slab(g, (px, max(0.0, y - 0.6) + 0.06, pz), (rng.uniform(0.5, 0.75), 0.28, 0.26),
                 quat_y(rng.uniform(0, 3.14)) @ quat_z(rng.uniform(-0.3, 0.3)), rng, mat=M_PLASTER,
                 col_fn=sandstone_col(nz, 0.9), tile=0.9, res=(2, 1, 1), round_r=0.035, rough=0.015, cuts=2)
    # ── The processional stair up +Z: worn treads, a few cracked or missing.
    for s in range(12):
        y = s * 0.3
        wh = 2.35 + (0.62 - 2.35) * (y / 3.6)
        if s == 7:
            continue
        slab(g, (rng.uniform(-0.02, 0.02), y + 0.1, wh + 0.14), (0.95 - y * 0.04, 0.4, 0.62),
             quat_y(rng.uniform(-0.03, 0.03)), rng, mat=M_PLASTER, col_fn=sandstone_col(nz, 1.05), tile=1.2,
             res=(4, 2, 3), round_r=0.05, rough=0.006, crown=0.05 if s % 3 == 0 else 0.0)
    stone(g, (0.1, 2.12, 2.75 - 0.35), (0.28, 0.12, 0.2), rng, mat=M_PLASTER, col_fn=sandstone_col(nz), detail=1, cuts=2)
    # ── Summit shrine: floor slab, four drum pillars, two lintels, the altar with its turquoise tiles.
    top = 6 * th
    slab(g, (0, top + 0.02, 0), (1.5, 0.2, 1.5), quat_y(0.0), rng, mat=M_PLASTER, col_fn=sandstone_col(nz, 1.05),
         tile=1.0, res=(4, 1, 4), round_r=0.04, rough=0.004)
    for x, z in ((-0.52, -0.52), (0.52, -0.52), (-0.52, 0.52), (0.52, 0.52)):
        for d in range(3):
            frustum(g, 0.12 - d * 0.005, 0.115 - d * 0.005, top + 0.12 + d * 0.26, 0.255, 10, M_PLASTER,
                    scale(SANDSTONE, 0.95 - 0.04 * d), tile=0.8, centre=(x + rng.uniform(-0.01, 0.01), 0, z), cap_top=True)
        slab(g, (x, top + 0.94, z), (0.3, 0.1, 0.3), quat_y(0), rng, mat=M_PLASTER, col_fn=sandstone_col(nz, 0.9),
             tile=0.8, res=(2, 1, 2), round_r=0.02, rough=0.004)
    for z in (-0.52, 0.52):
        slab(g, (0, top + 1.06, z), (1.4, 0.15, 0.34), quat_z(0.015 * (1 if z > 0 else -1)), rng, mat=M_PLASTER,
             col_fn=sandstone_col(nz, 0.85), tile=1.0, res=(5, 1, 2), round_r=0.03, rough=0.006, cuts=1)
    slab(g, (0, top + 0.29, 0), (0.46, 0.34, 0.46), quat_y(0.0), rng, mat=M_PLASTER, col_fn=sandstone_col(nz, 1.0),
         tile=0.8, res=(2, 2, 2), round_r=0.03, rough=0.004)
    # Cracked turquoise faience tiles round the altar band (a few fallen).
    for k in range(12):
        a = k * 2 * math.pi / 12
        if k in (3, 8):
            continue
        r = 0.236
        rot = quat_y(-a + math.pi / 2)
        lbox(g, V(math.cos(a) * r, top + 0.33, math.sin(a) * r), (0.1, 0.1, 0.012), rot, M_STONE,
             scale(TURQ, rng.uniform(0.75, 1.05)), tile=0.4)
    for k in range(2):
        lbox(g, V(rng.uniform(0.3, 0.6), top + 0.13, rng.uniform(-0.4, 0.4)), (0.1, 0.012, 0.1), quat_y(rng.uniform(0, 3)),
             M_STONE, scale(TURQ, 0.8), tile=0.4)
    # Dark doorway into the top tier's +Z face.
    lbox(g, V(0, top - 0.28, 0.62 + 0.02), (0.5, 0.42, 0.1), quat_y(0), M_ROCK, (0.12, 0.1, 0.08), tile=0.5)
    # ── The dune eating the -X/-Z quarter, ripples on its back.
    sand = lambda p, n: scale(SAND, (0.92 + 0.08 * nz(p * 3.0)) * (0.9 + 0.1 * n.y))
    # One long wind-built dune banked up the -X/-Z faces: low, wide, tapering into the desert floor.
    for x, z, rx, rz, h in ((-2.4, -1.8, 3.8, 3.0, 1.05), (-0.6, -3.1, 2.8, 1.7, 0.5), (-3.7, 0.7, 2.0, 2.6, 0.45)):
        mound(g, (x, -0.25, z), rx, rz, h, rng, mat=M_PLASTER, col_fn=sand, tile=2.6, rings=8, seg=28, skirt=0.3,
              rough=0.04, power=2.6, edge=0.3)
    # ── The colossus head buried to the chin in the +X sand, face turned to the stair.
    head = V(3.0, 0.32, 1.9)
    hr = quat_y(-2.25) @ quat_z(0.12)
    pale = lambda p, n: scale((0.97, 0.86, 0.68), 0.85 + 0.15 * nz(p * 2.0))
    stone(g, tuple(head), (0.5, 0.56, 0.54), rng, mat=M_PLASTER, col_fn=pale, tile=1.0, detail=2, rough=0.04, cuts=0,
          rot=hr)
    slab(g, tuple(head + hr @ V(0, 0.44, -0.05)), (0.82, 0.16, 0.62), hr, rng, mat=M_PLASTER,
         col_fn=sandstone_col(nz, 0.8), tile=1.0, res=(4, 1, 3), round_r=0.05, rough=0.01, cuts=1)
    for sx in (-0.5, 0.5):
        slab(g, tuple(head + hr @ V(sx, 0.02, -0.06)), (0.14, 0.62, 0.48), hr, rng, mat=M_PLASTER,
             col_fn=sandstone_col(nz, 0.8), tile=1.0, res=(1, 4, 3), round_r=0.04, rough=0.01, taper=0.2)
    slab(g, tuple(head + hr @ V(0, 0.17, 0.45)), (0.5, 0.09, 0.14), hr, rng, mat=M_PLASTER, col_fn=pale, tile=0.6,
         res=(3, 1, 1), round_r=0.03, rough=0.01)
    slab(g, tuple(head + hr @ V(0, 0.0, 0.5)), (0.12, 0.22, 0.14), hr @ quat_x(0.14), rng, mat=M_PLASTER, col_fn=pale,
         tile=0.6, res=(1, 2, 1), round_r=0.03, rough=0.02, cuts=1)
    slab(g, tuple(head + hr @ V(0, -0.2, 0.47)), (0.3, 0.07, 0.1), hr, rng, mat=M_PLASTER, col_fn=pale, tile=0.6,
         res=(2, 1, 1), round_r=0.02, rough=0.01)
    mound(g, (head.x, -0.15, head.z), 1.2, 1.1, 0.42, rng, mat=M_PLASTER, col_fn=sand, tile=1.6, rings=5, seg=18,
          power=1.6, edge=0.25)
    # ── Obelisks at the stair foot: one standing, one toppled and broken.
    ob = V(1.15, 0, 3.15)
    slab(g, tuple(ob + V(0, 0.06, 0)), (0.5, 0.2, 0.5), quat_y(0.1), rng, mat=M_PLASTER, col_fn=sandstone_col(nz, 0.85),
         tile=0.8, res=(2, 1, 2), round_r=0.03, rough=0.01)
    slab(g, tuple(ob + V(0, 0.9, 0)), (0.32, 1.6, 0.32), quat_y(0.1), rng, mat=M_PLASTER, col_fn=sandstone_col(nz, 0.75),
         tile=0.8, res=(2, 6, 2), round_r=0.02, rough=0.008, taper=0.35)
    W.tube(g, [ob + V(0, 1.68, 0), ob + V(0, 1.92, 0)], [0.1, 0.005], 4, M_PLASTER, scale(SANDSTONE, 0.7), tile=0.4)
    ob2 = V(-1.25, 0, 3.0)
    slab(g, tuple(ob2 + V(0, 0.05, 0)), (0.48, 0.18, 0.48), quat_y(0.4), rng, mat=M_PLASTER,
         col_fn=sandstone_col(nz, 0.85), tile=0.8, res=(2, 1, 2), round_r=0.03, rough=0.01)
    slab(g, tuple(ob2 + V(0, 0.32, 0)), (0.32, 0.5, 0.32), quat_y(0.4), rng, mat=M_PLASTER, col_fn=sandstone_col(nz, 0.75),
         tile=0.8, res=(2, 2, 2), round_r=0.02, rough=0.01, cuts=1)
    slab(g, tuple(ob2 + V(-0.6, 0.14, -0.45)), (0.3, 1.15, 0.3), quat_y(0.7) @ quat_z(1.5), rng, mat=M_PLASTER,
         col_fn=sandstone_col(nz, 0.75), tile=0.8, res=(2, 5, 2), round_r=0.02, rough=0.01, taper=0.2, cuts=1)
    # Column drums + blocks round the base, half in the sand.
    for p, r in (((2.6, 0.12, -1.4), 0.0), ((3.15, 0.12, -1.15), 0.5)):
        rot = quat_y(r) @ quat_z(math.pi / 2)
        c = V(*p)
        ax = rot @ V(0, 1, 0)
        W.tube(g, [c - ax * 0.27, c + ax * 0.27], [0.21, 0.2], 10, M_PLASTER, scale(SANDSTONE, 0.85), tile=0.8)
    slab(g, (-2.3, 0.12, 2.5), (0.42, 0.3, 0.36), quat_y(0.8), rng, mat=M_PLASTER, col_fn=sandstone_col(nz, 0.9),
         tile=0.8, res=(2, 1, 2), round_r=0.03, rough=0.02, cuts=1)
    for k in range(6):
        a = rng.uniform(0, 6.28)
        r = rng.uniform(2.6, 3.4)
        stone(g, (math.cos(a) * r, 0.02, math.sin(a) * r), (0.14, 0.09, 0.12), rng, mat=M_PLASTER,
              col_fn=sandstone_col(nz, 0.85), detail=1, cuts=2, tile=0.8)
    return b


# ─────────────────────────────────────────────────────────────── rocky: the standing stones
RING_R = 2.9
STONES = [(1.19, 3.25), (1.95, 3.25), (2.85, 2.6), (3.75, 2.4), (4.65, 2.8), (5.5, 2.55)]
FALLEN = (0.22, 3.35)
GRANITE = (0.8, 0.8, 0.82)
LICHENS = [(0.85, 0.6, 0.28), (0.62, 0.66, 0.42)]


def lm_standing_stones(rng):
    b = Builder()
    g = G(b)
    for i, (a, h) in enumerate(STONES):
        x, z = math.cos(a) * RING_R, math.sin(a) * RING_R
        yaw = -(a + math.pi / 2)
        lean = (rng.uniform(0, 1) - 0.5) * 0.09
        nzk = Noise(rng, 4, 1.8)
        tint = scale(GRANITE, rng.uniform(0.88, 1.0))
        col = rock_col(tint, moss=0.6, noise=nzk, lichen=LICHENS[i % 2], var=0.16)
        rot = quat_y(yaw) @ quat_z(lean)
        # One worked monolith: tapered, crowned, a fracture or two; inner face at r ~ 2.66.
        slab(g, (x, (h - 0.35) / 2, z), (0.76, h + 0.35, 0.5), rot, rng, res=(6, 16, 4), round_r=0.08, rough=0.035,
             taper=0.28, crown=0.3, cuts=2, lean_top=(lean * 0.6, 0.0), col_fn=col, tile=1.1)
        for j in range(3):
            o = rot @ V(rng.uniform(-0.45, 0.45), 0, (1 if j % 2 else -1) * rng.uniform(0.3, 0.42))
            rr = rng.uniform(0.08, 0.14)
            stone(g, (x + o.x, 0.0, z + o.z), (rr, rr * 0.6, rr * 0.8), rng, detail=1, col_fn=col, tile=0.5)
    # The gate lintel over the first pair (+Z, toward the road spur).
    (a1, h1), (a2, _) = STONES[0], STONES[1]
    mid = (a1 + a2) / 2
    lx, lz = (math.cos(a1) + math.cos(a2)) / 2 * RING_R, (math.sin(a1) + math.sin(a2)) / 2 * RING_R
    nzl = Noise(rng, 4, 1.8)
    slab(g, (lx, h1 + 0.2, lz), (2.55, 0.46, 0.56), quat_y(-(mid + math.pi / 2)) @ quat_z(0.015), rng, res=(14, 3, 4),
         round_r=0.08, rough=0.03, cuts=1, col_fn=rock_col(GRANITE, moss=0.75, noise=nzl, lichen=LICHENS[1]), tile=1.1)
    # The fallen seventh, snapped in two where it landed, half in the turf.
    fx, fz = math.cos(FALLEN[0]) * FALLEN[1], math.sin(FALLEN[0]) * FALLEN[1]
    fy = -(FALLEN[0] + math.pi / 2)
    colf = rock_col(scale(GRANITE, 0.92), moss=0.8, noise=nzl, lichen=LICHENS[0])
    slab(g, (fx - 0.35, 0.18, fz - 0.2), (0.66, 1.6, 0.44), quat_y(fy + 0.15) @ quat_z(math.pi / 2 * 0.95), rng,
         res=(4, 10, 3), round_r=0.07, rough=0.04, cuts=1, col_fn=colf, tile=1.1)
    slab(g, (fx + 0.9, 0.16, fz + 0.38), (0.6, 0.95, 0.42), quat_y(fy - 0.35) @ quat_z(math.pi / 2 * 1.05), rng,
         res=(4, 6, 3), round_r=0.07, rough=0.05, cuts=2, col_fn=colf, tile=1.1)
    stone(g, (fx + 0.25, 0.05, fz + 0.1), (0.2, 0.12, 0.18), rng, col_fn=colf, tile=0.5)
    # The altar: three squat legs, two stacked slabs, a dark worn bowl.
    cola = rock_col(scale(GRANITE, 0.85), moss=0.3, noise=nzl)
    for i in range(3):
        a = i * 2 * math.pi / 3 + 0.4
        slab(g, (math.cos(a) * 0.42, 0.18, math.sin(a) * 0.42), (0.3, 0.5, 0.3), quat_y(a), rng, res=(2, 3, 2),
             round_r=0.05, rough=0.04, col_fn=cola, tile=0.8)
    slab(g, (0, 0.52, 0), (1.32, 0.18, 1.0), quat_y(0.2), rng, res=(6, 1, 5), round_r=0.06, rough=0.03, col_fn=cola,
         tile=0.9)
    slab(g, (0, 0.68, 0), (1.05, 0.14, 0.8), quat_y(0.32), rng, res=(5, 1, 4), round_r=0.05, rough=0.02,
         col_fn=rock_col(scale(GRANITE, 0.95), moss=0.1, noise=nzl), tile=0.9)
    lathe(g, [(0.18, 0.74), (0.19, 0.8), (0.15, 0.81), (0.1, 0.775), (0.0, 0.77)], 12, (0, 0, 0), M_ROCK,
          lambda p, n: (0.25, 0.22, 0.2), tile=0.4)
    # Ring dressing: flat waystones between the monoliths, two cairns, talus.
    for i in range(6):
        a = STONES[i][0] + 0.45
        stone(g, (math.cos(a) * RING_R * 0.97, -0.02, math.sin(a) * RING_R * 0.97), (0.28, 0.08, 0.22), rng, detail=1,
              col_fn=cola, tile=0.6, flat_y=0.6)
    for a, r in ((2.4, 4.3), (5.1, 4.1)):
        cx, cz = math.cos(a) * r, math.sin(a) * r
        for s in range(4):
            rr = 0.36 - s * 0.07
            stone(g, (cx + rng.uniform(-0.04, 0.04), 0.05 + s * 0.14, cz + rng.uniform(-0.04, 0.04)), (rr, 0.09, rr * 0.8),
                  rng, detail=1, col_fn=rock_col(GRANITE, moss=0.6, noise=nzl, lichen=LICHENS[s % 2]), tile=0.6,
                  flat_y=0.55)
    for k in range(10):
        a = rng.uniform(0, 6.28)
        r = rng.uniform(1.3, 3.8)
        rr = rng.uniform(0.07, 0.15)
        stone(g, (math.cos(a) * r, 0.0, math.sin(a) * r), (rr, rr * 0.55, rr * 0.8), rng, detail=1, col_fn=cola, tile=0.5)
    return b


def lm_keystone(rng):
    """The cracked keystone (part-local, centred on the origin, r ~ 0.4): two halves of one block
    split along a seam the amber light leaks from."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 2.0)
    col = rock_col(scale(GRANITE, 0.9), moss=0.25, noise=nz, ground=-5.0, lichen=LICHENS[0])
    slab(g, (0.04, 0.05, 0.02), (0.72, 0.62, 0.66), quat_y(0.3) @ quat_z(0.06), rng, res=(4, 4, 4), round_r=0.08,
         rough=0.05, cuts=2, col_fn=col, tile=0.7)
    slab(g, (-0.18, -0.1, -0.08), (0.42, 0.5, 0.5), quat_y(0.3) @ quat_z(-0.2), rng, res=(3, 3, 3), round_r=0.07,
         rough=0.06, cuts=1, col_fn=col, tile=0.7)
    return b


def lm_mill_vane(rng):
    """The Old Mill's weathervane (part-local, base at the origin): an iron rod, a forged arrow
    with a cut-sheet cockerel tail, a collar."""
    b = Builder()
    g = G(b)
    iron = (0.3, 0.27, 0.25)
    tube(g, [V(0, -0.05, 0), V(0, 0.5, 0)], [0.018, 0.014], 6, M_IRON, iron, tile=0.3)
    tube(g, [V(-0.26, 0.42, 0), V(0.3, 0.42, 0)], [0.012, 0.012], 5, M_IRON, iron, tile=0.3)
    W.tube(g, [V(0.27, 0.42, 0), V(0.4, 0.42, 0)], [0.05, 0.002], 4, M_IRON, iron, tile=0.2)
    lbox(g, V(-0.25, 0.44, 0), (0.14, 0.17, 0.01), quat_z(0.15), M_IRON, scale(iron, 1.15), tile=0.3)
    frustum(g, 0.035, 0.03, 0.0, 0.05, 8, M_IRON, iron, tile=0.2, centre=(0, 0.3, 0))
    return b


# ─────────────────────────────────────────────────────────────── treasure chests (src/chest.rs)
# Body 0.70 x 0.40 x 0.50 resting on y = 0; the lid is its own model built forward (+Z) of the
# hinge origin (the body's back-top edge, (0, 0.40, -0.25) in chest space), underside on y = 0, so
# the hinge animation in chest.rs keeps working. Wood: weathered nailed boards, black iron bands
# and corner brackets, a bronze lock plate. Relic: dark oiled wood, gilt bronze straps and studs,
# a cut gem (the `glow` material: a faint cold light) in the lid and the lock.
M_BRONZE = M_SNOW + 4
M_GLOW = M_SNOW + 5
MATS += ["bronze", "glow"]
GILT = (1.0, 0.78, 0.4)
BRASS = (0.85, 0.66, 0.36)
GEM = (0.08, 0.42, 0.48)


def chest_body(rng, relic):
    b = Builder()
    g = G(b)
    wood = (0.5, 0.38, 0.3) if relic else (0.78, 0.66, 0.54)
    band_m, band_c = (M_BRONZE, GILT) if relic else (M_IRON, IRON)
    hw, hd, top = 0.35, 0.25, 0.4
    # Side boards (three horizontal per face), end boards, bottom.
    for k in range(3):
        y = 0.07 + k * 0.115
        for zf in (hd, -hd):
            board(g, (0, y + 0.0575, zf), (1, 0, 0), (0, 0, 1 if zf > 0 else -1), 0.7, 0.112, 0.03, mat=M_PLANK,
                  col=scale(wood, rng.uniform(0.82, 1.05)), rng=rng)
        for xf in (hw, -hw):
            board(g, (xf, y + 0.0575, 0), (0, 0, 1), (1 if xf > 0 else -1, 0, 0), 0.5, 0.112, 0.03, mat=M_PLANK,
                  col=scale(wood, rng.uniform(0.82, 1.05)), rng=rng)
    lbox(g, V(0, 0.08, 0), (0.68, 0.03, 0.48), quat_y(0), M_PLANK, scale(wood, 0.7), tile=0.6)
    # Banding: two vertical straps wrapping the front, sides of the base rim, corner brackets.
    for x in (-0.24, 0.24):
        for zf in (hd + 0.018, -hd - 0.018):
            lbox(g, V(x, 0.235, zf), (0.06, 0.34, 0.012), quat_y(0), band_m, band_c, tile=0.4)
    for xs in (-1, 1):
        for zs in (-1, 1):
            lbox(g, V(xs * (hw + 0.012), 0.235, zs * (hd - 0.03)), (0.012, 0.34, 0.07), quat_y(0), band_m,
                 scale(band_c, 0.9), tile=0.4)
            lbox(g, V(xs * (hw - 0.03), 0.235, zs * (hd + 0.012)), (0.07, 0.34, 0.012), quat_y(0), band_m,
                 scale(band_c, 0.9), tile=0.4)
    lbox(g, V(0, top - 0.015, 0), (0.72, 0.03, 0.52), quat_y(0), band_m, band_c, tile=0.4)
    # Nail heads along the straps.
    for x in (-0.24, 0.24):
        for k in range(4):
            stone(g, (x, 0.12 + k * 0.08, hd + 0.03), (0.012, 0.012, 0.008), rng, mat=band_m, detail=1, rough=0.0,
                  cuts=0, col_fn=lambda p, n: scale(band_c, 1.15), tile=0.2)
    # Lock plate + hasp staple (+ the relic's gem).
    lbox(g, V(0, 0.28, hd + 0.022), (0.17, 0.19, 0.014), quat_y(0), M_BRONZE, GILT if relic else BRASS, tile=0.3)
    lbox(g, V(0, 0.25, hd + 0.031), (0.03, 0.06, 0.006), quat_y(0), M_IRON, (0.08, 0.07, 0.06), tile=0.3)
    if relic:
        stone(g, (0, 0.33, hd + 0.034), (0.025, 0.025, 0.012), rng, mat=M_GLOW, detail=1, rough=0.0, cuts=0,
              col_fn=lambda p, n: GEM, tile=0.2)
    # Stub feet.
    for xs in (-1, 1):
        for zs in (-1, 1):
            lbox(g, V(xs * 0.28, 0.035, zs * 0.18), (0.1, 0.075, 0.1), quat_y(0), band_m if relic else M_PLANK,
                 band_c if relic else scale(wood, 0.6), tile=0.4)
    return b


def chest_lid(rng, relic):
    b = Builder()
    g = G(b)
    wood = (0.5, 0.38, 0.3) if relic else (0.82, 0.7, 0.58)
    band_m, band_c = (M_BRONZE, GILT) if relic else (M_IRON, IRON)
    # A shallow barrel vault from z 0 (hinge) to z 0.5 (front), staves running along X.
    n = 6
    arc = lambda t: (0.5 * t, 0.03 + 0.15 * math.sin(math.pi * t))
    for k in range(n):
        z0, y0 = arc(k / n)
        z1, y1 = arc((k + 1) / n)
        mid = V(0, (y0 + y1) / 2, (z0 + z1) / 2)
        nrm = Vector((0, z1 - z0, -(y1 - y0))).normalized()
        board(g, mid, (1, 0, 0), nrm, 0.72, math.hypot(z1 - z0, y1 - y0) + 0.004, 0.03, mat=M_PLANK,
              col=scale(wood, rng.uniform(0.82, 1.05)), rng=rng)
    # End caps (the vault's gable boards).
    for xs in (-0.355, 0.355):
        pts = [V(xs, 0.0, 0.0)] + [V(xs, arc(t)[1], arc(t)[0]) for t in np.linspace(0, 1, 9)] + [V(xs, 0.0, 0.5)]
        pts = pts if xs > 0 else pts[::-1]
        c = sum(pts, Vector((0, 0, 0))) / len(pts)
        for k in range(len(pts)):  # fan of triangles (an n-gon breaks the exporter's tangents)
            g.flat([c, pts[k], pts[(k + 1) % len(pts)]], M_PLANK, scale(wood, 0.85), 0.5)
    lbox(g, V(0, 0.015, 0.25), (0.7, 0.03, 0.5), quat_y(0), M_PLANK, scale(wood, 0.7), tile=0.6)
    # Straps following the vault + a front clasp hanging over the lock.
    for x in (-0.24, 0.24):
        pts = [V(x, arc(t)[1] + 0.02, arc(t)[0]) for t in np.linspace(0, 1, 9)]
        beam(g, pts, 0.06, 0.012, mat=band_m, col=band_c, mode="bark", rng=rng, chamfer=0.05)
    lbox(g, V(0, -0.03, 0.512), (0.12, 0.12, 0.014), quat_y(0), M_BRONZE, GILT if relic else BRASS, tile=0.3)
    if relic:
        stone(g, (0, 0.21, 0.25), (0.06, 0.05, 0.06), rng, mat=M_GLOW, detail=1, rough=0.0, cuts=3,
              col_fn=lambda p, n: GEM, tile=0.2)
        lbox(g, V(0, 0.185, 0.25), (0.16, 0.02, 0.16), quat_y(0.785), M_BRONZE, GILT, tile=0.3)
    return b


MODELS = {
    "lm_witch_hut": lm_witch_hut,
    "lm_frozen_spire": lm_frozen_spire,
    "lm_sunken_pyramid": lm_sunken_pyramid,
    "lm_standing_stones": lm_standing_stones,
    "lm_keystone": lm_keystone,
    "lm_mill_vane": lm_mill_vane,
    "chest_wood_body": lambda rng: chest_body(rng, False),
    "chest_wood_lid": lambda rng: chest_lid(rng, False),
    "chest_relic_body": lambda rng: chest_body(rng, True),
    "chest_relic_lid": lambda rng: chest_lid(rng, True),
}

if __name__ == "__main__":
    clear_scene()
    objs = []
    report = {}
    for i, (name, fn) in enumerate(MODELS.items()):
        b = fn(np.random.default_rng(6100 + i))
        report[name] = bounds(b)
        objs.append(b.build(name, MATS))
    export_glb(OUT / "landmarks.glb", objs)
    for k, v in report.items():
        print(f"{k}: {v}")
    print("LANDMARKS_DONE")
