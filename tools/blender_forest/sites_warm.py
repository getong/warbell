"""Unique story sites for the DESERT and the FOREST -> sites_warm.glb (src/sites_warm.rs).

Each biome is its own chapter (docs/superpowers/specs/2026-10-12-wyspa-opowiada-design.md) with its
own palette. No text, no interaction: each scene explains itself.

DESERT ("the others" - sun-bleached sandstone, cracked turquoise glaze, salt, faded dye, brass, bone):
  site_trading_stones   - the neutral trade ground of orks and the Pasha's caravans: a sandstone
                          table with a brass balance and graded weights, salt slabs on one side, iron
                          bars on the other, a marker stone for each people, the shade awning down.
  site_survey_line      - the first colony's surveyors: a cairn with the Crown's mark and a line of
                          weathered stakes with rag tags running off toward the buried pyramid.
  site_drowned_outpost  - the colony's southern post drowned by a dune: sandstone arches, an EMPTY
                          bell-arch with its iron bracket, a tiled cistern full of sand.
  site_glyph_wall       - the Old Ones' petroglyph wall: desert-varnished sandstone pecked with
                          spreading rings and tusked figures, arms raised toward them.
  site_looted_caravan   - present day: the Pasha's cart plundered days ago - bright cloth slashed and
                          strewn, smashed jars, a half-burned bale, ork arrows in the boards.
  site_anselm_desert    - Brother Anselm's journal: a dead pack-mule's bones under a rock overhang,
                          the satchel spilled, a page held down by a stone.
FOREST ("the beginning" - oak, moss, lichen, wet stone, fungus, roots):
  site_bell_pit         - the colony's bell-casting pit: earth berm, slumped clay furnace, shards of
                          the broken mould (one band of mirrored letters), a bronze spill, the lifting
                          tripod with its empty hook. NO bell.
  site_charcoal_kiln    - an overgrown charcoal mound split open on its charred billets, cordwood.
  site_sawpit           - a sawpit with an oak trunk half sawn, the pit saw still in the kerf.
  site_rooted_pillar    - an Old Ones' ringed pillar swallowed by the roots of a giant dead oak.
  site_anselm_forest    - the colony's first graves and a hollow oak with a journal page in it.

Real scale (hero ~1.3-1.8u), base y=0, local -Z = the side the story faces. Contact parts sink
below y=0. Materials by name (W.MATS + s_snow/bronze from stories_cold, then the new sets of
biome_sites_set.sh: s_sandstone, s_tile, s_mosswood, s_clay, s_mossrock).

    blender -b --factory-startup --python tools/blender_forest/sites_warm.py
"""
import math
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402
from common import OUT, clear_scene, export_glb  # noqa: E402
from geo import G, quat_x, quat_y, quat_z, sheet  # noqa: E402
from meshkit import Builder  # noqa: E402
import wayside_models as W  # noqa: E402
from wayside_models import (M_BARK, M_PLANK, M_STONE, M_HIDE, M_CLOTH, M_IRON, M_ROCK, M_EARTH,  # noqa: E402
                            V, beam, board, bounds, charred, lbox, mix, mound, pole, rock_col, scale, slab,
                            smooth_mesh, smoothstep, stone, tube, Noise)
from stories_cold import (M_BRONZE, BRONZE, VERDIGRIS, disc, dome, wheel, sack, lathe, orient)  # noqa: E402

M_SAND = M_BRONZE + 1       # s_sandstone
M_TILE = M_BRONZE + 2       # s_tile
M_MOSSWOOD = M_BRONZE + 3   # s_mosswood
M_CLAY = M_BRONZE + 4       # s_clay
M_MOSSROCK = M_BRONZE + 5   # s_mossrock
M_PLASTER = M_BRONZE + 6    # s_plaster (salt, bleached bone, paper)
MATS = W.MATS + ["s_snow", "bronze", "s_sandstone", "s_tile", "s_mosswood", "s_clay", "s_mossrock", "s_plaster"]

# Desert palette (multiplies the scans).
SAND = (0.98, 0.86, 0.66)            # loose drift sand over s_earth
SANDSTONE = (0.92, 0.8, 0.68)
VARNISH = (0.36, 0.23, 0.15)          # desert varnish on old rock faces
BLEACHED = (0.86, 0.8, 0.7)          # sun-bleached wood
BONE = (0.95, 0.92, 0.82)
SALT = (0.95, 0.94, 0.9)
TURQ = (0.32, 0.78, 0.76)
OCHRE_GLAZE = (0.95, 0.72, 0.32)
BRASS = (0.42, 0.3, 0.1)
TERRACOTTA = (0.95, 0.55, 0.36)
# Forest palette.
MOSS = (0.36, 0.5, 0.18)
DAMP_EARTH = (0.42, 0.34, 0.26)
OAK = (0.62, 0.55, 0.47)
ROT_WOOD = (0.75, 0.75, 0.7)
FIRED = (0.85, 0.5, 0.34)
RAW_CLAY = (0.62, 0.55, 0.48)
PAPER = (0.92, 0.88, 0.76)
INK = (0.12, 0.1, 0.09)


# ─────────────────────────────────────────────────────────────── shared helpers
def sand_drift(g, centre, rx, rz, h, rng, power=0.9, skirt=0.15, rings=5, seg=18, edge=0.2):
    nz = Noise(rng, 4, 1.4)

    def f(p, n):
        k = 0.92 + 0.08 * nz(p * 2.3)
        lee = 1.0 - 0.12 * (1.0 - smoothstep(0.2, 0.9, n.y))   # the steeper lee faces a shade warmer/darker
        return scale((SAND[0], SAND[1] * (0.98 + 0.02 * lee), SAND[2] * lee), k)
    mound(g, centre, rx, rz, h, rng, mat=M_EARTH, col_fn=f, tile=1.6, rings=rings, seg=seg, skirt=skirt, rough=0.06,
          edge=edge, power=power)


def forest_mound(g, centre, rx, rz, h, rng, moss=0.7, base=DAMP_EARTH, power=0.8, rings=5, seg=18, skirt=0.15):
    nz = Noise(rng, 4, 2.0)

    def f(p, n):
        m = moss * smoothstep(0.2, 0.8, n.y) * (0.6 + 0.4 * nz(p * 2.5))
        return mix(scale(base, 0.85 + 0.15 * nz(p * 4)), MOSS, max(0.0, min(m, 1.0)))
    mound(g, centre, rx, rz, h, rng, mat=M_EARTH, col_fn=f, tile=1.0, rings=rings, seg=seg, skirt=skirt, rough=0.1,
          power=power)


def sun_rock(base=SANDSTONE, varnish=0.0, sand=0.35, nz=None):
    """Sandstone tint: sun-bleached crowns, darker desert varnish down the vertical faces, sand-dusted
    toward the foot."""
    def f(p, n):
        k = 0.9 + (0.1 * nz(p * 3.0) if nz else 0.0)
        c = scale(base, k)
        c = mix(c, VARNISH, varnish * (1.0 - smoothstep(0.2, 0.7, abs(n.y))))
        c = mix(c, (1.0, 0.95, 0.85), 0.25 * smoothstep(0.5, 0.95, n.y))
        return mix(c, SAND, sand * (1.0 - smoothstep(0.0, 0.35, p.y)))
    return f


def mossy(base, moss=0.6, nz=None, wet=0.65):
    """Forest stone / wood tint: moss on the up faces, damp-dark at the foot."""
    def f(p, n):
        k = wet + (1 - wet) * smoothstep(-0.05, 0.5, p.y)
        c = scale(base, k * (0.9 + (0.12 * nz(p * 3.0) if nz else 0.0)))
        m = moss * smoothstep(0.25, 0.85, n.y) * (0.65 + (0.35 * nz(p * 5.0) if nz else 0.35))
        return mix(c, MOSS, max(0.0, min(m, 1.0)))
    return f


def carve_line(g, pts, col, r=0.012, mat=M_ROCK):
    tube(g, [Vector(p) for p in pts], [r] * len(pts), 4, mat, col, tile=0.2, cap=False)


def ring_on(g, c, face, up, rr, col, r=0.012, mat=M_ROCK, n=15, arc=(0.0, 2 * math.pi)):
    face, up = Vector(face).normalized(), Vector(up).normalized()
    right = up.cross(face).normalized()
    up = face.cross(right).normalized()
    pts = [Vector(c) + (right * math.cos(t) + up * math.sin(t)) * rr for t in np.linspace(arc[0], arc[1], n)]
    carve_line(g, pts, col, r, mat)


def tusk_figure(g, c, face, up, s, col, mat=M_ROCK, arms_up=True):
    """A pecked stick figure with tusks: head ring, body, arms raised (or out), legs."""
    face, up = Vector(face).normalized(), Vector(up).normalized()
    right = up.cross(face).normalized()
    c = Vector(c)
    head = c + up * 0.32 * s
    ring_on(g, head, face, up, 0.05 * s, col, r=0.01 * s / 0.5 if s < 0.5 else 0.011, mat=mat, n=9)
    body = [c + up * 0.26 * s, c + up * 0.05 * s]
    carve_line(g, body, col, 0.011, mat)
    for sg in (-1, 1):
        sh = c + up * 0.2 * s
        hand = sh + right * sg * 0.13 * s + up * (0.14 if arms_up else -0.02) * s
        carve_line(g, [sh, sh + right * sg * 0.09 * s + up * 0.02 * s, hand], col, 0.01, mat)
        carve_line(g, [c + up * 0.05 * s, c + right * sg * 0.07 * s - up * 0.16 * s], col, 0.01, mat)
        t0 = head - up * 0.035 * s + right * sg * 0.025 * s
        carve_line(g, [t0, t0 + right * sg * 0.03 * s + up * 0.045 * s], col, 0.008, mat)


def shards(g, rng, n, cx, cz, spread, col, mat=M_CLAY, size=(0.05, 0.12), y=0.0):
    """Potsherds: thin curved fragments lying flat-ish."""
    for _ in range(n):
        s = rng.uniform(*size)
        c = V(cx + rng.uniform(-spread, spread), y + 0.01, cz + rng.uniform(-spread, spread))
        rot = quat_y(rng.uniform(0, 6.28)) @ quat_x(rng.uniform(-0.25, 0.25))
        slab(g, tuple(c), (s * 1.6, s * 0.18, s), rot, rng, mat=mat, res=(2, 1, 2), round_r=0.01, rough=0.04,
             col_fn=lambda p, nn, k=rng.uniform(0.85, 1.05): scale(col, k), tile=0.3, crown=-0.6, cuts=1)


def jar(g, rng, base, rot, h=0.55, r=0.22, col=TERRACOTTA, broken=0.0, glaze=None):
    """A wheel-thrown clay jar (amphora-ish) on its local Y. `broken` cuts the top fraction off with a
    jagged lip."""
    prof = [(0.0, 0.0), (r * 0.45, 0.0), (r * 0.8, 0.08), (r, 0.3), (r * 0.95, 0.55), (r * 0.6, 0.82), (r * 0.32, 0.9),
            (r * 0.3, 1.0), (r * 0.38, 1.04)]
    prof = [(rr, y * h) for rr, y in prof]
    if broken:
        top = h * (1 - broken)
        prof = [p for p in prof if p[1] < top] + [(r * 0.9, top)]
    v, t = lathe(prof, 12, base, rot)
    if broken:   # jag the cut rim
        for i in range(len(v) - 12, len(v)):
            v[i] = v[i] + (rot @ V(0, 1, 0)) * rng.uniform(-0.07, 0.03) * h
    c = Vector(base)
    axis = rot @ V(0, 1, 0)

    def f(p, n):
        hh = (p - c).dot(axis) / h
        cc = scale(col, 0.85 + 0.15 * smoothstep(0.1, 0.6, hh))
        if glaze and hh > 0.45:
            cc = glaze
        return cc
    smooth_mesh(g, v, orient(v, t, c, axis, True), M_CLAY, f, 0.35)
    if broken:   # the dark inside visible through the break
        vi, ti = lathe([(rr * 0.9, y) for rr, y in prof[1:]], 12, base, rot)
        smooth_mesh(g, vi, orient(vi, ti, c, axis, False), M_CLAY, lambda p, n: scale(col, 0.45), 0.35)


def page(g, centre, rot, w=0.2, l=0.27, curl=0.03, lines=True, col=PAPER):
    """A journal page: a slightly curled paper sheet (s_plaster), ink lines along it."""
    c = Vector(centre)
    grid = []
    for i in range(5):
        row = []
        for j in range(4):
            x = -w / 2 + w * i / 4
            z = -l / 2 + l * j / 3
            y = curl * ((2 * i / 4 - 1) ** 2) + 0.004
            row.append(c + rot @ V(x, y, z))
        grid.append(row)
    sheet(g, grid, M_PLASTER, lambda u, v: col, tile=0.4, double=True)
    if lines:
        for k in range(7):
            z = -l / 2 + l * (k + 1.2) / 8.5
            x0, x1 = -w * 0.38, w * (0.38 if k % 3 else 0.15)
            pts = [c + rot @ V(x, curl * ((2 * (x + w / 2) / w - 1) ** 2) + 0.007, z) for x in np.linspace(x0, x1, 4)]
            tube(g, pts, [0.0025] * 4, 3, M_PLASTER, INK, tile=0.2, cap=False)


def bone(g, a, b, r, rng, col=BONE):
    a, b = Vector(a), Vector(b)
    d = b - a
    tube(g, [a, a + d * 0.12, a + d * 0.5, a + d * 0.88, b], [r * 1.6, r, r * 0.85, r, r * 1.6], 6, M_PLASTER, col,
         tile=0.3)


def ribcage(g, rng, c, length, r, rot, col=BONE, missing=()):
    """A spine along local X with rib arcs, half-sunk (the lower ends run below y=0)."""
    c = Vector(c)
    spine = [c + rot @ V(-length / 2 + length * k / 7, 0.0, 0.0) for k in range(8)]
    tube(g, spine, [r * 0.12] * 8, 6, M_PLASTER, col, tile=0.3)
    for k in range(1, 7):
        if k in missing:
            continue
        x = -length / 2 + length * k / 7
        for sg in (-1, 1):
            pts = [c + rot @ V(x + 0.02 * u, r * math.cos(u * 1.6) * 0.9 - r * 0.05, sg * r * math.sin(u * 1.6))
                   for u in np.linspace(0, 1, 6)]
            tube(g, pts, [0.018, 0.016, 0.014, 0.013, 0.012, 0.01], 5, M_PLASTER, scale(col, rng.uniform(0.9, 1.0)),
                 tile=0.3, cap=False)


def skull(g, rng, c, rot, s=1.0, col=BONE):
    """A long equine skull lying on its side."""
    c = Vector(c)
    stone(g, tuple(c), (0.14 * s, 0.09 * s, 0.1 * s), rng, mat=M_PLASTER, detail=2, rough=0.05, cuts=0, rot=rot,
          col_fn=lambda p, n: col, tile=0.3)
    stone(g, tuple(c + rot @ V(0.24 * s, -0.02 * s, 0)), (0.2 * s, 0.06 * s, 0.065 * s), rng, mat=M_PLASTER, detail=2,
          rough=0.05, cuts=0, rot=rot, col_fn=lambda p, n: col, tile=0.3)
    for sg in (-1, 1):   # dark eye sockets
        stone(g, tuple(c + rot @ V(0.04 * s, 0.03 * s, sg * 0.08 * s)), (0.035 * s, 0.03 * s, 0.02 * s), rng,
              mat=M_PLASTER, detail=1, rough=0.0, cuts=0, rot=rot, col_fn=lambda p, n: (0.18, 0.15, 0.12), tile=0.3)


def cloth_drape(g, rng, c, rot, w, l, col, sag=0.08, lift=0.0, folds=3, nx=7, nz=6, fade=0.0, slashed=False):
    """A cloth sheet lying over the ground (folds + a lifted edge), local X across, Z along."""
    c = Vector(c)
    nzn = Noise(rng, 3, 2.0)
    grid = []
    for i in range(nx):
        row = []
        for j in range(nz):
            u, v = i / (nx - 1), j / (nz - 1)
            x = (u - 0.5) * w
            z = (v - 0.5) * l
            y = 0.02 + sag * abs(math.sin(u * math.pi * folds)) + lift * smoothstep(0.6, 1.0, v) + 0.02 * nzn(V(x, 0, z) * 3)
            if slashed and 0.45 < u < 0.55:
                y += 0.03
            row.append(c + rot @ V(x, y, z))
        grid.append(row)
    sheet(g, grid, M_CLOTH, lambda u, v: mix(col, (0.9, 0.84, 0.72), fade * (0.5 + 0.5 * v)), tile=0.6, double=True)


def stake(g, rng, foot, h, lean=(0.0, 0.0), col=BLEACHED, rag=None, r=0.035):
    foot = Vector(foot)
    top = foot + V(lean[0] * h, h, lean[1] * h)
    beam(g, [foot - V(0, 0.3, 0), top], r * 2, r * 2, mat=M_PLANK, col=col, rng=rng, point=0.0, chamfer=0.3,
         jag=(0, 0.04))
    if rag:
        k = foot.lerp(top, 0.88)
        sway = rng.uniform(-0.3, 0.3)
        grid = [[k + V(0.0, -0.08 * j, r), k + V(0.1 + 0.05 * j, -0.1 * j - 0.02, r + sway * 0.1 * j)] for j in range(4)]
        grid = [list(x) for x in zip(*grid)]
        sheet(g, grid, M_CLOTH, lambda u, v: scale(rag, 1 - 0.25 * v), tile=0.3, double=True)


# ─────────────────────────────────────────────────────────────── DESERT
def site_trading_stones(rng):
    """Footprint r <= 3.0. Masses: the table (0, 0) ~1.1 x 0.65, the two marker stones (+-2.0, 0.4),
    the salt stack (-1.3, -0.9), the fallen awning pole lies on the ground (walkable)."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 1.5)
    sand_drift(g, (0.0, -0.02, 0.0), 2.9, 2.5, 0.08, rng, power=0.5, rings=6, seg=26)
    # The table: a dressed sandstone slab on two block plinths, worn hollow in the middle.
    for x in (-0.6, 0.6):
        slab(g, (x, 0.22, 0.0), (0.42, 0.62, 0.6), quat_y(rng.uniform(-0.05, 0.05)), rng, mat=M_SAND, res=(3, 3, 3),
             round_r=0.05, rough=0.03, col_fn=sun_rock(nz=nz, varnish=0.2), tile=0.8)
    slab(g, (0.0, 0.6, 0.0), (2.0, 0.2, 1.1), quat_y(0.02), rng, mat=M_SAND, res=(8, 2, 4), round_r=0.04, rough=0.02,
         crown=-0.25, col_fn=sun_rock(nz=nz, varnish=0.1, sand=0.0), tile=0.9)
    sand_drift(g, (-0.6, 0.0, -0.35), 0.5, 0.3, 0.16, rng)
    sand_drift(g, (0.62, 0.0, 0.38), 0.55, 0.32, 0.2, rng)
    # The brass balance: an upright on a foot, the beam, one pan hanging, the other dropped on the slab.
    top = 0.7
    lbox(g, V(0.1, top + 0.02, 0.05), (0.2, 0.04, 0.16), quat_y(0.0), M_BRONZE, BRASS, tile=0.3)
    tube(g, [V(0.1, top, 0.05), V(0.1, top + 0.62, 0.05)], [0.022, 0.018], 8, M_BRONZE, BRASS, tile=0.3)
    beam_a, beam_b = V(-0.28, top + 0.66, 0.05), V(0.48, top + 0.56, 0.05)
    tube(g, [beam_a, V(0.1, top + 0.62, 0.05), beam_b], [0.012, 0.016, 0.012], 6, M_BRONZE, BRASS, tile=0.3)
    for k in range(3):
        a = k / 3 * 2 * math.pi
        tube(g, [beam_a, beam_a + V(math.cos(a) * 0.1, -0.32, math.sin(a) * 0.1)], [0.003] * 2, 3, M_CLOTH, W.ROPE,
             tile=0.2, cap=False)
    disc(g, beam_a + V(0, -0.34, 0), quat_x(0.0), 0.11, 0.012, 14, M_BRONZE, mix(BRASS, VERDIGRIS, 0.3))
    disc(g, V(0.7, top + 0.035, 0.22), quat_x(0.5) @ quat_z(0.2), 0.11, 0.012, 14, M_BRONZE, BRASS)
    # Graded weights: duck-shaped stone weights in a row, biggest to smallest, and a bronze one.
    for k, s in enumerate((0.16, 0.13, 0.1, 0.08, 0.06, 0.045)):
        stone(g, (-0.85 + k * 0.17, top + s * 0.35, -0.3), (s * 0.7, s * 0.45, s * 0.5), rng, mat=M_STONE, detail=2,
              rough=0.02, cuts=0, flat_y=0.6, rot=quat_y(0.1), col_fn=lambda p, n: (0.42, 0.4, 0.38), tile=0.3)
    # Salt (the caravans' side): stacked cut slabs, one cracked off.
    for k in range(3):
        slab(g, (-1.35 + rng.uniform(-0.04, 0.04), 0.09 + k * 0.17, -0.95), (0.62, 0.15, 0.4), quat_y(0.3 + rng.uniform(-0.1, 0.1)),
             rng, mat=M_PLASTER, res=(3, 1, 2), round_r=0.03, rough=0.04, col_fn=lambda p, n: scale(SALT, 0.92 + 0.08 * n.y),
             tile=0.5, cuts=1)
    slab(g, (-1.85, 0.04, -0.55), (0.4, 0.12, 0.3), quat_y(1.2) @ quat_z(0.15), rng, mat=M_PLASTER, res=(2, 1, 2),
         round_r=0.03, col_fn=lambda p, n: SALT, tile=0.5, cuts=2)
    # Iron (the orks' side): rough bloom bars crossed in a pile.
    for k in range(6):
        y = 0.04 + (k // 3) * 0.06
        a = 0.2 + (k // 3) * 1.4 + (k % 3) * 0.05
        c = V(1.3 + (k % 3) * 0.08 * math.cos(a + 1.5), y, -0.9 + (k % 3) * 0.08 * math.sin(a + 1.5))
        d = V(math.cos(a), 0, math.sin(a)) * 0.3
        beam(g, [c - d, c + d], 0.07, 0.05, mat=M_IRON, mode="bark", col=(0.36, 0.28, 0.22), rng=rng, rough=0.15)
    # The two marker stones, each cut with its people's sign, facing the table.
    for sg, ang in ((-1, 0.1), (1, -0.1)):
        c = V(sg * 2.0, 0.55, 0.4)
        slab(g, tuple(c), (0.55, 1.4, 0.3), quat_y(ang) @ quat_z(sg * 0.04), rng, mat=M_SAND, res=(3, 6, 2),
             round_r=0.07, taper=0.25, rough=0.05, crown=0.2, col_fn=sun_rock(nz=nz, varnish=0.5), tile=0.9)
        face, up = V(-sg, 0, -0.15).normalized(), V(0, 1, 0)
        fc = c + V(0, 0.3, 0) + face * 0.29
        light = (0.98, 0.86, 0.7)
        if sg < 0:   # the orks': two crossed tusks under a ring
            for s2 in (-1, 1):
                r = up.cross(face).normalized()
                carve_line(g, [fc + r * s2 * 0.14 - up * 0.1, fc + r * s2 * 0.02 + up * 0.04, fc - r * s2 * 0.1 + up * 0.18],
                           light, 0.016, M_SAND)
            ring_on(g, fc + up * 0.32, face, up, 0.08, light, r=0.014, mat=M_SAND)
        else:        # the desert people's: a sun disc inside a crescent
            ring_on(g, fc + up * 0.1, face, up, 0.07, light, r=0.014, mat=M_SAND)
            ring_on(g, fc + up * 0.1, face, up, 0.16, light, r=0.014, mat=M_SAND, arc=(0.6, math.pi * 2 - 0.6), n=13)
            # a faded dyed rag tied round the stone's neck
            k = c + V(0, 0.55, 0)
            tube(g, [k + V(math.cos(t) * 0.22, 0.02 * math.sin(3 * t), math.sin(t) * 0.12) for t in np.linspace(0, 6.3, 13)],
                 [0.025] * 13, 5, M_CLOTH, (0.62, 0.32, 0.3), tile=0.2, cap=False)
            grid = [[k + V(0.2, 0.0, -0.05), k + V(0.25, -0.35, -0.12)], [k + V(0.24, 0.0, 0.05), k + V(0.3, -0.33, 0.0)]]
            sheet(g, grid, M_CLOTH, lambda u, v: (0.66, 0.36, 0.32), tile=0.3, double=True)
    # The shade awning came down: one pole still standing, one fallen, the faded cloth on the sand.
    pole(g, V(-0.3, -0.2, 1.45), V(-0.35, 2.0, 1.5), 0.045, 0.035, rng, mat=M_PLANK, col=BLEACHED, sides=7)
    pole(g, V(1.6, 0.04, 1.2), V(0.1, 0.12, 2.3), 0.045, 0.035, rng, mat=M_PLANK, col=BLEACHED, sides=7)
    cloth_drape(g, rng, V(0.6, -0.02, 1.75), quat_y(0.15), 2.0, 1.1, (0.72, 0.5, 0.36), sag=0.06, lift=0.25, fade=0.55)
    tube(g, [V(-0.35, 1.95, 1.5), V(0.0, 1.0, 1.6), V(0.25, 0.25, 1.7)], [0.008] * 3, 3, M_CLOTH, W.ROPE, tile=0.2,
         cap=False)
    shards(g, rng, 10, 0.2, -1.2, 1.4, TERRACOTTA)
    return b


def site_survey_line(rng):
    """Footprint r <= 3.2. Local +Z points at the buried pyramid (the game turns it so). Masses: the
    cairn (0, -1.6) r 0.6; the stakes are thin (walk-through)."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 1.5)
    sand_drift(g, (0.0, -0.02, -1.0), 1.5, 1.2, 0.12, rng, power=0.6)
    # The cairn: dry-laid sandstone, the dressed Crown stone set in its face (facing -Z).
    for k, (n_, r_, y) in enumerate(((7, 0.48, 0.14), (6, 0.38, 0.4), (5, 0.27, 0.64), (3, 0.15, 0.85))):
        for i in range(n_):
            a = i / n_ * 2 * math.pi + k * 0.4
            s = rng.uniform(0.16, 0.22) * (1 - k * 0.12)
            stone(g, (math.cos(a) * r_, y, -1.6 + math.sin(a) * r_), (s, s * 0.7, s * 0.9), rng, mat=M_SAND, detail=1,
                  rough=0.08, cuts=2, col_fn=sun_rock(nz=nz, varnish=0.4), tile=0.6)
    stone(g, (0.0, 1.0, -1.6), (0.14, 0.12, 0.13), rng, mat=M_SAND, detail=1, cuts=2, col_fn=sun_rock(nz=nz), tile=0.6)
    cs = V(0.0, 0.5, -2.1)
    slab(g, tuple(cs), (0.62, 0.66, 0.16), quat_x(-0.12), rng, mat=M_STONE, res=(3, 3, 1), round_r=0.03, rough=0.02,
         col_fn=lambda p, n: (0.82, 0.74, 0.62), tile=0.6)
    # The Crown's mark: a ring round a three-pointed crown, cut dark, with a level line and a number.
    face, up = V(0, 0.12, -1).normalized(), V(0, 1, 0.12).normalized()
    fc = cs + face * 0.085 + up * 0.06
    cut = (0.3, 0.22, 0.16)
    ring_on(g, fc, face, up, 0.17, cut, r=0.013)
    r = up.cross(face).normalized()
    carve_line(g, [fc - r * 0.09 - up * 0.05, fc + r * 0.09 - up * 0.05], cut, 0.013)
    for k in (-1, 0, 1):
        base_ = fc - up * 0.05 + r * k * 0.07
        carve_line(g, [base_, base_ + up * (0.13 if k == 0 else 0.09) + r * k * 0.015], cut, 0.012)
    carve_line(g, [cs + face * 0.085 - up * 0.22 - r * 0.24, cs + face * 0.085 - up * 0.22 + r * 0.24], cut, 0.01)
    # The stake line, running off along +Z: weathered, leaning more the farther they go, rag tags.
    rag = (0.7, 0.36, 0.3)
    leans = [(0.0, 0.02), (0.05, -0.04), (-0.12, 0.08), (0.0, 0.0)]
    for k, z in enumerate((-0.55, 0.55, 1.65, 2.75)):
        if k == 3:   # the last one blown down, half under sand
            beam(g, [V(0.15, 0.05, z - 0.4), V(-0.1, 0.03, z + 0.55)], 0.07, 0.07, mat=M_PLANK, col=BLEACHED, rng=rng,
                 chamfer=0.3)
            sand_drift(g, (0.0, -0.02, z + 0.1), 0.55, 0.4, 0.12, rng)
            continue
        stake(g, rng, V(0.0, 0.0, z), 1.25 - 0.1 * k, lean=leans[k], rag=rag if k != 1 else None)
        sand_drift(g, (0.0, -0.02, z), 0.3, 0.25, 0.1, rng)
    # The cord between them, sagging and broken after the second stake.
    tube(g, [V(0.0, 1.2, -0.55), V(0.02, 0.85, 0.0), V(0.05, 1.1, 0.55)], [0.006] * 3, 3, M_CLOTH, W.ROPE, tile=0.2,
         cap=False)
    tube(g, [V(0.05, 1.1, 0.55), V(0.2, 0.5, 0.8), V(0.35, 0.02, 0.95)], [0.006] * 3, 3, M_CLOTH, W.ROPE, tile=0.2,
         cap=False)
    # The surveyor's rod lying by the cairn: banded paint all but gone.
    a, bb = V(-0.9, 0.05, -1.0), V(-0.75, 0.04, 0.8)
    for k in range(6):
        p0, p1 = a.lerp(bb, k / 6), a.lerp(bb, (k + 1) / 6)
        beam(g, [p0, p1], 0.05, 0.03, mat=M_PLANK, col=(0.8, 0.5, 0.42) if k % 2 else BLEACHED, rng=rng, chamfer=0.2,
             cap=(k == 0, k == 5))
    # A bronze plumb bob on its cord, dropped.
    v_, t_ = lathe([(0.0, 0.0), (0.035, 0.05), (0.03, 0.08), (0.0, 0.09)], 10, V(0.7, 0.03, -0.6), quat_z(1.4))
    smooth_mesh(g, v_, t_, M_BRONZE, lambda p, n: mix(BRASS, VERDIGRIS, 0.5), 0.3, inside=V(0.66, 0.03, -0.6))
    tube(g, [V(0.62, 0.03, -0.6), V(0.4, 0.02, -0.4), V(0.3, 0.02, -0.1)], [0.004] * 3, 3, M_CLOTH, W.ROPE, tile=0.2,
         cap=False)
    return b


def arch(g, rng, cx, cz, span, h, depth, rot, nz, buried=0.0, broken=0):
    """A sandstone arch of blocks: two piers + a voussoir ring. `broken` drops that many voussoirs."""
    c = V(cx, 0, cz)
    hw = span / 2
    for sg in (-1, 1):
        for k in range(int(h / 0.38)):
            y = 0.19 + k * 0.38 - buried
            slab(g, tuple(c + rot @ V(sg * (hw + 0.2), y, 0)), (0.42, 0.36, depth), rot @ quat_y(rng.uniform(-0.03, 0.03)),
                 rng, mat=M_SAND, res=(2, 2, 2), round_r=0.05, rough=0.04, col_fn=sun_rock(nz=nz, varnish=0.25), tile=0.8)
    spring = h - buried
    nv = 9
    for k in range(nv):
        if broken and k in (4, 5)[:broken]:
            continue
        a0 = math.pi * k / nv
        a1 = math.pi * (k + 1) / nv
        am = (a0 + a1) / 2
        rr = hw + 0.2
        p = c + rot @ V(-math.cos(am) * rr, spring + math.sin(am) * rr, 0)
        slab(g, tuple(p), (0.4, rr * (a1 - a0) * 0.96, depth), rot @ quat_z(math.pi - am), rng, mat=M_SAND,
             res=(2, 2, 2), round_r=0.04, rough=0.04, col_fn=sun_rock(nz=nz, varnish=0.3, sand=0.0), tile=0.8)


def tile_band(g, rng, centre, r, n, y, h=0.12, glaze=TURQ, drop=0.2):
    """A band of glazed tiles round a cistern lip: some missing, some cracked off-colour."""
    for i in range(n):
        if rng.uniform() < drop:
            continue
        a = i / n * 2 * math.pi
        c = V(centre[0] + math.cos(a) * r, y, centre[2] + math.sin(a) * r)
        col = glaze if rng.uniform() > 0.25 else OCHRE_GLAZE
        col = scale(col, rng.uniform(0.75, 1.0))
        lbox(g, c, (0.03, h, 2 * math.pi * r / n * 0.92), quat_y(-a) @ quat_z(rng.uniform(-0.06, 0.06)), M_TILE, col,
             tile=0.25, grain=1)


def site_drowned_outpost(rng):
    """Footprint r <= 3.6. Masses: the dune (1.2, 0.6) 2.2 x 1.6, the arcade piers along z = -0.4,
    the cistern (-1.7, -1.4) r 0.95."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 1.4)
    # The arcade: three arches in a row along X, sinking into the dune toward +X.
    rot = quat_y(0.0)
    arch(g, rng, -1.4, -0.4, 1.3, 1.6, 0.5, rot, nz, buried=0.0)
    arch(g, rng, 0.3, -0.4, 1.3, 1.6, 0.5, rot, nz, buried=0.45, broken=1)
    arch(g, rng, 2.0, -0.4, 1.3, 1.6, 0.5, rot, nz, buried=1.1)
    # The bell-arch over the first arch: a little gable with an empty opening and an iron bracket.
    top = V(-1.4, 2.42, -0.4)
    for sg in (-1, 1):
        slab(g, tuple(top + V(sg * 0.38, 0.45, 0)), (0.2, 0.9, 0.42), quat_z(0.0), rng, mat=M_SAND, res=(2, 3, 2),
             round_r=0.04, rough=0.03, col_fn=sun_rock(nz=nz, varnish=0.35, sand=0.0), tile=0.8)
    slab(g, tuple(top + V(0, 1.02, 0)), (1.0, 0.24, 0.46), quat_z(0.0), rng, mat=M_SAND, res=(3, 2, 2), round_r=0.05,
         crown=0.4, rough=0.03, col_fn=sun_rock(nz=nz, varnish=0.35, sand=0.0), tile=0.8)
    slab(g, tuple(top + V(0, 0.02, 0)), (1.1, 0.14, 0.5), quat_z(0.0), rng, mat=M_SAND, res=(3, 1, 2), round_r=0.04,
         rough=0.03, col_fn=sun_rock(nz=nz, sand=0.0), tile=0.8)
    hook = top + V(0, 0.9, 0)
    tube(g, [hook + V(-0.12, 0, 0), hook + V(-0.12, -0.12, 0), hook + V(0.12, -0.12, 0), hook + V(0.12, 0, 0)],
         [0.018] * 4, 5, M_IRON, (0.3, 0.2, 0.14), tile=0.2)
    tube(g, [hook + V(0, -0.12, 0), hook + V(0, -0.2, 0), hook + V(0.04, -0.25, 0)], [0.012] * 3, 5, M_IRON,
         (0.3, 0.2, 0.14), tile=0.2)
    # The dune that took it: piled against the arcade's +X end and spilling through the arches.
    sand_drift(g, (1.5, -0.05, 0.3), 2.2, 1.7, 1.5, rng, power=0.7, rings=7, seg=26, edge=0.25)
    sand_drift(g, (0.3, -0.05, -0.4), 1.0, 0.7, 0.55, rng)
    sand_drift(g, (-0.3, -0.05, 0.6), 1.6, 1.0, 0.3, rng, power=0.5)
    # The cistern: a round sandstone curb, turquoise-tiled lip, choked with sand.
    cc = (-1.75, 0.0, -1.55)
    for k in range(14):
        a = k / 14 * 2 * math.pi
        slab(g, (cc[0] + math.cos(a) * 0.85, 0.22, cc[2] + math.sin(a) * 0.85), (0.24, 0.5, 0.39), quat_y(-a), rng,
             mat=M_SAND, res=(2, 2, 2), round_r=0.04, rough=0.03, col_fn=sun_rock(nz=nz, varnish=0.15), tile=0.8)
    tile_band(g, rng, cc, 0.99, 22, 0.36)
    mound(g, (cc[0], 0.3, cc[2]), 0.78, 0.78, 0.06, rng, mat=M_EARTH, col_fn=lambda p, n: scale(SAND, 0.92), tile=1.0,
          rings=3, seg=14, skirt=0.0, power=0.5)
    # Fallen voussoirs and loose tiles, a wind-scoured lintel beam.
    for k in range(4):
        slab(g, (rng.uniform(-0.6, 1.0), 0.12, rng.uniform(-1.9, -1.2)), (0.4, 0.3, 0.45), quat_y(rng.uniform(0, 3)) @
             quat_z(rng.uniform(-0.3, 0.3)), rng, mat=M_SAND, res=(2, 2, 2), round_r=0.05, rough=0.05,
             col_fn=sun_rock(nz=nz, varnish=0.2), tile=0.8, cuts=1)
    for k in range(7):
        a = rng.uniform(0, 6.28)
        lbox(g, V(-1.0 + rng.uniform(-0.8, 0.8), 0.015, -2.4 + rng.uniform(-0.4, 0.4)), (0.18, 0.02, 0.14),
             quat_y(a) @ quat_x(rng.uniform(-0.15, 0.15)), M_TILE, scale(TURQ if k % 3 else OCHRE_GLAZE, 0.85), tile=0.25)
    beam(g, [V(-2.9, 0.06, 0.4), V(-1.6, 0.14, 1.3)], 0.2, 0.16, mat=M_PLANK, col=BLEACHED, rng=rng, rough=0.08, jag=(0, 0.2))
    return b


def site_glyph_wall(rng):
    """Footprint r <= 3.2. Masses: the outcrop wall along X at z = 0.3, 4.4 x 1.0."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 5, 1.2)
    sand_drift(g, (0.0, -0.03, -0.3), 3.0, 1.6, 0.1, rng, power=0.5)
    # Three wind-scoured sandstone masses, leaning together; the -Z face is the varnished panel.
    for x, w, h, lean in ((-1.4, 1.6, 2.2, 0.05), (0.2, 1.9, 2.7, -0.02), (1.8, 1.3, 1.8, -0.08)):
        slab(g, (x, h / 2 - 0.25, 0.35), (w, h, 1.0), quat_y(rng.uniform(-0.08, 0.08)) @ quat_z(lean), rng, mat=M_SAND,
             res=(8, 10, 4), round_r=0.12, rough=0.16, crown=0.15, taper=0.2, cuts=3,
             col_fn=sun_rock(nz=nz, varnish=0.9, sand=0.5), tile=1.2)
    sand_drift(g, (0.3, -0.05, -0.25), 2.4, 0.7, 0.35, rng, power=0.8)
    sand_drift(g, (1.6, -0.05, 1.0), 1.2, 0.8, 0.5, rng)
    # Petroglyphs, pecked pale through the varnish: a great ring spreading, figures facing it.
    face, up = V(0, 0, -1), V(0, 1, 0)
    pale = (0.8, 0.64, 0.48)
    rc = V(0.25, 1.45, -0.18)
    for rr in (0.08, 0.17, 0.27, 0.38, 0.5):
        ring_on(g, rc, face, up, rr, scale(pale, 1.0 - rr * 0.4), r=0.016, n=21, mat=M_SAND)
    for k, x in enumerate((-1.9, -1.45, -1.0)):
        tusk_figure(g, V(x, 0.75 + 0.05 * k, -0.12), face, up, 0.9 + 0.1 * k, pale, mat=M_SAND, arms_up=True)
    for k, x in enumerate((1.1, 1.5)):
        tusk_figure(g, V(x, 0.7, -0.1), face, up, 0.85, pale, mat=M_SAND, arms_up=k == 0)
    # A spiral and a row of dots beneath (a count? a calendar?).
    sp = V(-1.3, 1.65, -0.13)
    pts = [sp + V(math.cos(t) * 0.025 * t, math.sin(t) * 0.025 * t, 0) for t in np.linspace(0.3, 12, 30)]
    carve_line(g, pts, pale, 0.012, M_SAND)
    for k in range(9):
        stone(g, (-0.35 + k * 0.11, 0.48, -0.17), (0.02, 0.02, 0.008), rng, mat=M_SAND, detail=1, rough=0, cuts=0,
              col_fn=lambda p, n: pale, tile=0.2)
    # Fallen scree at the foot, and an ork's offering: two tusks and a flat stone.
    for k in range(8):
        s = rng.uniform(0.12, 0.3)
        stone(g, (rng.uniform(-2.3, 2.3), s * 0.2, rng.uniform(-0.75, -0.3)), (s, s * 0.6, s * 0.8), rng, mat=M_SAND,
              detail=1, rough=0.08, cuts=2, col_fn=sun_rock(nz=nz, varnish=0.3), tile=0.6)
    slab(g, (0.25, 0.06, -0.85), (0.6, 0.12, 0.45), quat_y(0.2), rng, mat=M_SAND, res=(3, 1, 2), round_r=0.04,
         col_fn=sun_rock(nz=nz, varnish=0.2), tile=0.7)
    for sg in (-1, 1):
        p = V(0.25 + sg * 0.12, 0.15, -0.85)
        tube(g, [p, p + V(sg * 0.08, 0.02, -0.12), p + V(sg * 0.06, 0.1, -0.26)], [0.035, 0.025, 0.005], 6, M_PLASTER,
             (0.9, 0.84, 0.68), tile=0.2)
    return b


def site_looted_caravan(rng):
    """Footprint r <= 3.2. Masses: the cart (0, 0) 1.2 x 0.7 tilted, the burned bale (1.5, 0.9)."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 1.5)
    sand_drift(g, (0.0, -0.02, 0.0), 3.0, 2.6, 0.05, rng, power=0.4, rings=5, seg=24)
    # The two-wheeled cart, dropped on its broken side, shafts up in the air.
    rot = quat_y(0.15) @ quat_x(-0.22)
    from stories_cold import wagon_bed
    wagon_bed(g, rng, V(0.0, 0.55, 0.0), rot, length=2.1, width=1.2, broken_side=True, col=(0.86, 0.66, 0.46))
    wheel(g, V(0.0, 0.62, -0.68), quat_x(math.pi / 2) @ quat_z(0.0), 0.62, rng, spokes=10, col=(0.8, 0.62, 0.42))
    wheel(g, V(0.9, 0.06, 0.95), quat_y(0.6) @ quat_z(0.06), 0.62, rng, spokes=10, broken=3, col=(0.8, 0.62, 0.42))
    for sg in (-1, 1):
        beam(g, [V(-1.05, 0.7, sg * 0.35), V(-2.3, 1.55, sg * 0.4)], 0.08, 0.08, mat=M_PLANK, col=(0.8, 0.62, 0.44),
             rng=rng)
    # Slashed bolts of dyed cloth strewn downwind, still bright: madder red, indigo, saffron.
    for k, (col, c, a, ln) in enumerate(((((0.75, 0.12, 0.1)), V(-0.6, 0.0, -1.6), 0.4, 1.8),
                                         ((0.16, 0.2, 0.55), V(1.1, 0.0, -1.4), -0.5, 1.5),
                                         ((0.95, 0.68, 0.12), V(0.4, 0.0, 1.9), 1.2, 1.3))):
        cloth_drape(g, rng, c, quat_y(a), 0.55, ln, col, sag=0.04, folds=2, slashed=True, nx=6, nz=7)
        tube(g, [c + quat_y(a) @ V(0, 0.08, -ln / 2 - 0.05), c + quat_y(a) @ V(0.02, 0.08, -ln / 2 - 0.08)],
             [0.09, 0.09], 10, M_CLOTH, scale(col, 0.8), tile=0.3)   # the rest of the roll
    # A carpet half unrolled out of the cart (woven bands).
    c0 = V(-1.6, 0.0, 0.5)
    tube(g, [c0 + V(0, 0.11, -0.6), c0 + V(0, 0.11, 0.6)], [0.11, 0.11], 12, M_CLOTH, (0.5, 0.14, 0.1), tile=0.3)
    grid = []
    for i in range(6):
        row = []
        for j in range(6):
            row.append(c0 + V(-0.1 - 1.2 * j / 5, 0.02 + 0.03 * math.sin(j * 1.7), -0.6 + 1.2 * i / 5))
        grid.append(row)
    sheet(g, grid, M_CLOTH, lambda u, v: (0.55, 0.12, 0.1) if int(u * 9) % 3 else (0.85, 0.65, 0.3), tile=0.4, double=True)
    # Smashed jars, a brass tray tipped, a burned bale.
    jar(g, rng, V(0.6, 0.0, -0.5), quat_x(1.45) @ quat_z(0.3), h=0.6, broken=0.35)
    jar(g, rng, V(-0.4, -0.05, 1.2), quat_z(0.0), h=0.55, broken=0.55)
    jar(g, rng, V(1.55, -0.04, -0.3), quat_x(0.1), h=0.45, r=0.18, col=(0.9, 0.82, 0.68), glaze=TURQ)
    shards(g, rng, 18, 0.2, 0.0, 1.7, TERRACOTTA)
    disc(g, V(-1.0, 0.06, -0.8), quat_x(0.25), 0.3, 0.02, 20, M_BRONZE, BRASS)
    mound(g, (1.55, -0.02, 0.95), 0.7, 0.6, 0.12, rng, mat=M_EARTH, col_fn=lambda p, n: (0.16, 0.14, 0.13), tile=0.8)
    stone(g, (1.55, 0.18, 0.95), (0.42, 0.25, 0.32), rng, mat=M_CLOTH, detail=1, rough=0.15, cuts=2,
          col_fn=lambda p, n: mix((0.12, 0.1, 0.09), (0.6, 0.3, 0.2), smoothstep(0.1, 0.35, p.y) * 0.4), tile=0.4)
    # Ork arrows in the boards and the sand: black shafts, crude black fletching.
    for k in range(7):
        foot = V(rng.uniform(-1.6, 1.8), 0.0, rng.uniform(-1.8, 1.6)) if k > 2 else V(-0.3 + k * 0.45, 0.85, 0.25)
        d = V(rng.uniform(-0.4, 0.4), 1.0, rng.uniform(-0.4, 0.4)).normalized()
        tail = foot + d * 0.7
        tube(g, [foot - d * 0.1, tail], [0.008, 0.008], 4, M_PLANK, (0.2, 0.17, 0.15), tile=0.2)
        for f in range(3):
            a = f / 3 * 2 * math.pi
            off = V(math.cos(a), 0, math.sin(a)) * 0.035
            g.flat([tail - d * 0.16, tail - d * 0.02, tail - d * 0.04 + off, tail - d * 0.16 + off * 0.6], M_HIDE,
                   (0.08, 0.07, 0.07), 0.2)
    sack(g, V(-0.9, 0.12, -1.3), quat_y(0.6) @ quat_z(1.2), 1.1, rng, col=(0.78, 0.7, 0.55))
    return b


def site_anselm_desert(rng):
    """Footprint r <= 2.6. Masses: the overhang rock (0, 0.8) 2.2 x 0.9; the mule's bones (walk-over)."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 5, 1.3)
    sand_drift(g, (0.0, -0.03, 0.0), 2.5, 2.2, 0.08, rng, power=0.5)
    # The overhang: a slab of sandstone cantilevered off a boulder pile, deep shade beneath.
    stone(g, (0.0, 0.5, 1.05), (1.3, 0.9, 0.7), rng, mat=M_SAND, detail=2, rough=0.1, cuts=2,
          col_fn=sun_rock(nz=nz, varnish=0.7, sand=0.4), tile=1.0)
    stone(g, (-1.15, 0.35, 0.6), (0.6, 0.6, 0.6), rng, mat=M_SAND, detail=2, rough=0.1, cuts=2,
          col_fn=sun_rock(nz=nz, varnish=0.6), tile=1.0)
    slab(g, (0.1, 1.42, 0.35), (2.6, 0.45, 1.7), quat_y(0.1) @ quat_x(0.1), rng, mat=M_SAND, res=(6, 2, 4), round_r=0.18,
         rough=0.08, crown=0.2, cuts=1, col_fn=sun_rock(nz=nz, varnish=0.8, sand=0.0), tile=1.1)
    sand_drift(g, (0.2, -0.05, 0.6), 1.5, 0.7, 0.3, rng)
    # The mule: ribcage half under the sand, skull, a foreleg, the pack saddle slipped off.
    ribcage(g, rng, V(0.3, 0.05, -0.35), 1.0, 0.3, quat_y(0.25), missing=(5,))
    skull(g, rng, V(-0.55, 0.08, -0.65), quat_y(0.5) @ quat_x(1.3), 1.0)
    bone(g, V(0.9, 0.04, -0.75), V(1.35, 0.04, -1.25), 0.025, rng)
    bone(g, V(0.75, 0.04, -0.1), V(1.3, 0.03, 0.2), 0.022, rng)
    sand_drift(g, (0.6, -0.04, -0.2), 0.6, 0.4, 0.14, rng)
    # Pack saddle frame (two crossed boards) and the leather satchel spilled under the overhang.
    for sg in (-1, 1):
        board(g, V(-0.2 + sg * 0.15, 0.12, 0.25), V(0.3, 0.6, 1), V(sg * 0.8, 0.5, 0), 0.55, 0.12, 0.03, mat=M_PLANK,
              col=BLEACHED, rng=rng)
    sc = V(-0.55, 0.12, 0.2)
    stone(g, tuple(sc), (0.22, 0.12, 0.16), rng, mat=M_HIDE, detail=2, rough=0.08, cuts=1, flat_y=0.7, rot=quat_y(0.4),
          col_fn=lambda p, n: (0.5, 0.34, 0.22), tile=0.4)
    g.flat([sc + V(0.12, 0.1, -0.12), sc + V(0.3, 0.01, -0.22), sc + V(0.42, 0.01, -0.0), sc + V(0.2, 0.11, 0.08)],
           M_HIDE, (0.45, 0.3, 0.2), 0.4)   # the flap thrown open
    # The pages: one under a stone at the overhang's mouth, two more slid out of the satchel.
    page(g, V(-0.1, 0.0, -0.15), quat_y(0.3))
    stone(g, (-0.08, 0.06, -0.12), (0.07, 0.05, 0.06), rng, mat=M_SAND, detail=1, rough=0.05, cuts=1,
          col_fn=sun_rock(nz=nz), tile=0.3)
    page(g, V(-0.38, 0.02, 0.0), quat_y(1.1) @ quat_x(0.1), curl=0.02, col=scale(PAPER, 0.9))
    page(g, V(-0.25, 0.14, 0.32), quat_y(-0.4) @ quat_z(0.4), lines=False, col=scale(PAPER, 0.85))
    # A brass inkhorn and a reed pen.
    v_, t_ = lathe([(0.0, 0.0), (0.03, 0.0), (0.035, 0.06), (0.018, 0.08), (0.0, 0.08)], 10, V(0.05, 0.0, 0.2),
                   quat_z(1.5))
    smooth_mesh(g, v_, t_, M_BRONZE, lambda p, n: BRASS, 0.3, inside=V(0.01, 0.03, 0.2))
    tube(g, [V(0.12, 0.01, 0.1), V(0.3, 0.01, 0.0)], [0.004, 0.003], 4, M_PLANK, (0.75, 0.65, 0.45), tile=0.2)
    return b


# ─────────────────────────────────────────────────────────────── FOREST
def ring_berm(g, rng, centre, r_in, r_out, h, floor=-0.02, seg=26, col_fn=None):
    """A pit read from above: a raised earth ring round a low dark floor (the terrain can't be dug)."""
    nz = Noise(rng, 4, 2.0)
    cx, cy, cz = centre
    radii = [0.0, r_in * 0.5, r_in * 0.85, r_in, (r_in + r_out) * 0.5, r_out * 0.85, r_out]
    prof = [floor, floor, floor + 0.02, h * 0.55, h, h * 0.45, -0.12]
    verts = []
    for j, (rr, y) in enumerate(zip(radii, prof)):
        n = 1 if rr == 0 else seg
        for i in range(n):
            a = 2 * math.pi * i / seg
            e = 1.0 + 0.12 * nz(V(math.cos(a), 0, math.sin(a)) * 1.5)
            yy = y * (1 + 0.25 * nz(V(math.cos(a) * 3, 1, math.sin(a) * 3))) if j > 2 else y
            verts.append(V(cx + math.cos(a) * rr * e, cy + yy, cz + math.sin(a) * rr * e))
    tris = [(0, 1 + (i + 1) % seg, 1 + i) for i in range(seg)]
    for j in range(len(radii) - 2):
        r0, r1 = 1 + j * seg, 1 + (j + 1) * seg
        for i in range(seg):
            a, b_ = r0 + i, r0 + (i + 1) % seg
            tris += [(a, b_, r1 + (i + 1) % seg), (a, r1 + (i + 1) % seg, r1 + i)]
    # Wind every face upward (it's a height field).
    out = []
    for a, b_, d in tris:
        n = (verts[b_] - verts[a]).cross(verts[d] - verts[a])
        out.append((a, b_, d) if n.y > 0 else (a, d, b_))
    smooth_mesh(g, verts, out, M_EARTH, col_fn or (lambda p, n: DAMP_EARTH), 1.0)


def mould_shard(g, rng, c, rot, r, h, a0, a1, y0, y1, letters=False):
    """A curved shard of the bell's clay mould (a cope fragment): a thick shell between the angles
    `a0..a1` and heights `y0..y1` of a bell profile, fired orange outside, black-glazed inside where
    the bronze ran. `letters`: a band of mirrored raised letters on the inner face."""
    c = Vector(c)

    def rad(t):
        return r * (1.0 - 0.38 * smoothstep(0.0, 0.7, t) + 0.05 * smoothstep(0.85, 1.0, t))
    nu, nv = 6, 5
    for side, th in ((1, 0.07), (-1, 0.0)):
        verts, tris = [], []
        for j in range(nv + 1):
            t = y0 + (y1 - y0) * j / nv
            for i in range(nu + 1):
                a = a0 + (a1 - a0) * i / nu
                rr = rad(t) + th + rng.uniform(-0.004, 0.004)
                verts.append(c + rot @ V(math.cos(a) * rr, t * h, math.sin(a) * rr))
        for j in range(nv):
            for i in range(nu):
                k = j * (nu + 1) + i
                tris += [(k, k + 1, k + nu + 2), (k, k + nu + 2, k + nu + 1)]
        col = (lambda p, n: scale(FIRED, 0.9)) if side > 0 else (lambda p, n: (0.14, 0.12, 0.11))
        tris = orient(verts, tris, c, rot @ V(0, 1, 0), side > 0)
        smooth_mesh(g, verts, tris, M_CLAY, col, 0.4)
    # Broken edges: thin strips joining the two shells along the rim.
    for (aa, tt) in ((a0, None), (a1, None)):
        pts_o = [c + rot @ V(math.cos(aa) * (rad(y0 + (y1 - y0) * j / nv) + 0.07), (y0 + (y1 - y0) * j / nv) * h,
                             math.sin(aa) * (rad(y0 + (y1 - y0) * j / nv) + 0.07)) for j in range(nv + 1)]
        pts_i = [c + rot @ V(math.cos(aa) * rad(y0 + (y1 - y0) * j / nv), (y0 + (y1 - y0) * j / nv) * h,
                             math.sin(aa) * rad(y0 + (y1 - y0) * j / nv)) for j in range(nv + 1)]
        for j in range(nv):
            q = [pts_o[j], pts_o[j + 1], pts_i[j + 1], pts_i[j]]
            g.flat(q, M_CLAY, scale(FIRED, 0.7), 0.3)
            g.flat(q[::-1], M_CLAY, scale(FIRED, 0.7), 0.3)
    if letters:
        # The inscription band (mirrored: a mould carries the letters reversed), raised on the
        # inside face where they'd have pressed into the bronze.
        tb = y0 + (y1 - y0) * 0.55
        for k in range(9):
            a = a1 - (a1 - a0) * (k + 0.8) / 10.5
            rr = rad(tb) - 0.012
            base_ = c + rot @ V(math.cos(a) * rr, tb * h, math.sin(a) * rr)
            tang = rot @ V(-math.sin(a), 0, math.cos(a))
            upv = rot @ V(0, 1, 0)
            s = 0.045
            kind = k % 4
            if kind == 0:
                strokes = [[base_ - upv * s, base_ + upv * s], [base_ + upv * s, base_ + upv * s - tang * s * 0.8]]
            elif kind == 1:
                strokes = [[base_ - upv * s - tang * s * 0.4, base_ + upv * s, base_ - upv * s + tang * s * 0.4],
                           [base_ - tang * s * 0.25, base_ + tang * s * 0.25]]
            elif kind == 2:
                strokes = [[base_ - upv * s, base_ + upv * s], [base_ - upv * s, base_ - upv * s + tang * s * 0.7]]
            else:
                strokes = [[base_ - upv * s - tang * s * 0.3, base_ + upv * s - tang * s * 0.3],
                           [base_ - upv * s + tang * s * 0.3, base_ + upv * s + tang * s * 0.3],
                           [base_ - tang * s * 0.3, base_ + tang * s * 0.3]]
            for st in strokes:
                tube(g, st, [0.007] * len(st), 4, M_CLAY, (0.2, 0.17, 0.15), tile=0.2, cap=False)


def site_bell_pit(rng):
    """Footprint r <= 3.4. Masses: the furnace (-1.6, 0.9) r 0.7, the tripod feet (thin), the berm is
    walkable. The pit floor centre (0.3, -0.2)."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 1.6)
    pc = (0.3, 0.0, -0.2)

    def pit_col(p, n):
        d = math.hypot(p.x - pc[0], p.z - pc[2])
        c = mix((0.2, 0.17, 0.15), DAMP_EARTH, smoothstep(0.9, 1.6, d))   # scorched floor, damp berm
        m = 0.75 * smoothstep(0.3, 0.9, n.y) * smoothstep(1.3, 2.0, d) * (0.6 + 0.4 * nz(p * 3))
        return mix(c, MOSS, m)
    ring_berm(g, rng, pc, 1.35, 2.7, 0.32, col_fn=pit_col)
    # The bronze spill: a flat glassy puddle in the pit, a runner channel to the mould's place.
    v, t = [], []
    for i in range(14):
        a = i / 14 * 2 * math.pi
        rr = 0.45 * (1 + 0.3 * nz(V(math.cos(a), 0, math.sin(a)) * 2))
        v.append(V(pc[0] + 0.2 + math.cos(a) * rr, 0.0, pc[2] + 0.25 + math.sin(a) * rr * 0.7))
    v.append(V(pc[0] + 0.2, 0.03, pc[2] + 0.25))
    t = [(14, (i + 1) % 14, i) for i in range(14)]
    smooth_mesh(g, v, t, M_BRONZE, bronze_spill(nz), 0.4, inside=V(pc[0] + 0.2, -1.0, pc[2] + 0.25))
    tube(g, [V(-1.2, 0.02, 0.5), V(-0.5, 0.0, 0.2), V(0.15, 0.0, 0.05)], [0.05, 0.045, 0.04], 6, M_BRONZE,
         mix(BRONZE, VERDIGRIS, 0.6), tile=0.3, cap=False)
    # Mould shards: a cope broken open in the pit, the big piece with the mirrored letters.
    mould_shard(g, rng, V(0.0, -0.05, -0.3), quat_y(0.4) @ quat_x(0.15), 0.62, 1.15, 0.2, 2.0, 0.05, 0.75, letters=True)
    mould_shard(g, rng, V(0.9, 0.05, 0.4), quat_x(-1.4) @ quat_y(1.5), 0.62, 1.15, 2.4, 3.6, 0.2, 0.7)
    mould_shard(g, rng, V(-0.4, 0.0, 0.7), quat_z(1.3) @ quat_y(0.2), 0.62, 1.15, 4.0, 4.9, 0.1, 0.5)
    shards(g, rng, 14, 0.3, -0.1, 1.0, FIRED, size=(0.06, 0.15))
    # The core: the clay false-bell the mould was built over, slumped and cracked in the middle.
    v_, t_ = lathe([(0.0, 0.0), (0.5, 0.0), (0.46, 0.2), (0.36, 0.5), (0.32, 0.72), (0.18, 0.84), (0.0, 0.86)], 14,
                   V(0.55, -0.05, -0.75), quat_z(0.12))
    smooth_mesh(g, v_, t_, M_CLAY, lambda p, n: mix(RAW_CLAY, (0.25, 0.2, 0.17), 0.4 * smoothstep(0.3, 0.8, p.y)), 0.4,
                inside=V(0.55, 0.3, -0.75))
    # The furnace: a slumped clay-and-stone dome, its mouth to the pit, a cracked chimney stub.
    fc = V(-1.6, 0.0, 0.9)
    dome(g, fc, 0.75, quat_y(0.3), M_CLAY, lambda p, n: mix(scale(FIRED, 0.7), (0.12, 0.1, 0.09),
                                                            0.5 * (1 - smoothstep(0.0, 0.5, p.y))), tile=0.5,
         squash=0.75, rings=5, seg=14)
    for k in range(9):
        a = rng.uniform(0, 6.28)
        stone(g, (fc.x + math.cos(a) * 0.8, 0.1, fc.z + math.sin(a) * 0.75), (0.16, 0.11, 0.13), rng, mat=M_MOSSROCK,
              detail=1, rough=0.1, cuts=2, col_fn=mossy((0.7, 0.68, 0.62), 0.5, nz), tile=0.6)
    tube(g, [fc + V(0.1, 0.4, 0.15), fc + V(0.13, 0.95, 0.18)], [0.2, 0.15], 10, M_CLAY,
         scale(FIRED, 0.55), tile=0.4, cap=False)
    g.flat([fc + V(0.55, 0.0, -0.4), fc + V(0.3, 0.0, -0.65), fc + V(0.3, 0.32, -0.6), fc + V(0.5, 0.32, -0.38)],
           M_CLAY, (0.05, 0.04, 0.04), 0.4)   # the dark mouth
    # Collapsed bellows: two rotten boards, the leather gone to rags.
    for sg in (-1, 1):
        board(g, fc + V(0.95, 0.06 + 0.06 * (sg + 1), -0.65 + sg * 0.05), V(1, 0, 0.6), V(0, 1, sg * 0.15), 0.8, 0.35,
              0.035, mat=M_MOSSWOOD, col=ROT_WOOD, rng=rng)
    stone(g, tuple(fc + V(0.95, 0.12, -0.65)), (0.3, 0.06, 0.16), rng, mat=M_HIDE, detail=1, rough=0.2, cuts=2,
          col_fn=lambda p, n: (0.3, 0.24, 0.18), tile=0.3)
    # The lifting tripod over the pit: three poles, one fallen; the chain still hangs, the hook empty.
    apex = V(pc[0] + 0.1, 2.9, pc[2] + 0.05)
    feet = [V(pc[0] + 1.9, -0.15, pc[2] - 0.8), V(pc[0] - 1.5, -0.15, pc[2] - 1.4)]
    for f in feet:
        pole(g, f, apex, 0.08, 0.06, rng, mat=M_MOSSWOOD, col=ROT_WOOD, sides=8)
    pole(g, V(pc[0] - 0.7, 0.06, pc[2] + 1.9), V(pc[0] + 1.6, 0.12, pc[2] + 2.6), 0.08, 0.06, rng, mat=M_MOSSWOOD,
         col=ROT_WOOD, sides=8)
    links = [apex + V(0, -0.05 - 0.12 * k, 0) for k in range(9)]
    tube(g, links, [0.02] * len(links), 5, M_IRON, (0.28, 0.18, 0.12), tile=0.15, cap=False)
    hk = links[-1]
    tube(g, [hk, hk + V(0, -0.15, 0), hk + V(0.07, -0.22, 0), hk + V(0.1, -0.12, 0)], [0.025] * 4, 5, M_IRON,
         (0.28, 0.18, 0.12), tile=0.15)
    return b


def bronze_spill(nz):
    def f(p, n):
        k = smoothstep(-0.1, 0.4, nz(p * 4))
        return scale(mix(BRONZE, VERDIGRIS, 0.35 + 0.5 * k), 0.9)
    return f


def log(g, rng, a, b_, r, mat=M_BARK, col=OAK, moss=0.0, cap=True, sides=9):
    nz = Noise(rng, 3, 2.0)
    a, b_ = Vector(a), Vector(b_)
    d = b_ - a
    pts = [a + d * (k / 4) + V(0, rng.uniform(-0.01, 0.01), 0) for k in range(5)]
    tube(g, pts, [r * rng.uniform(0.95, 1.05) for _ in pts], sides, mat, col, tile=0.8, cap=cap,
         col_fn=(lambda t: mix(col, MOSS, moss * (0.6 + 0.4 * nz(V(t * 3, 0, 0))))) if moss else None)


def site_charcoal_kiln(rng):
    """Footprint r <= 3.0. Masses: the kiln mound (0, 0) r 1.7, the cordwood stack (2.1, -0.6)."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 1.8)
    # The mound: turf-covered, mossed over, a vent at the crown; the -Z flank caved in on black billets.
    cx = V(0.0, 0.0, 0.0)

    def kiln_col(p, n):
        burnt = smoothstep(-0.6, -1.3, p.z) * smoothstep(1.0, 0.2, p.y)
        c = mix(DAMP_EARTH, MOSS, 0.75 * smoothstep(0.2, 0.8, n.y) * (0.6 + 0.4 * nz(p * 3)))
        return mix(c, (0.09, 0.08, 0.075), burnt)
    mound(g, (0.0, -0.05, 0.25), 1.7, 1.55, 1.05, rng, mat=M_EARTH, col_fn=kiln_col, tile=1.0, rings=7, seg=24, power=0.6)
    # The collapsed flank: charred billets stacked on end, tumbled, a black ash fan.
    mound(g, (0.0, -0.05, -1.3), 1.1, 0.8, 0.14, rng, mat=M_EARTH, col_fn=lambda p, n: (0.08, 0.075, 0.07), tile=0.8)
    for k in range(16):
        a = -math.pi / 2 + rng.uniform(-0.9, 0.9)
        rr = rng.uniform(0.8, 1.35)
        p = V(math.cos(a) * rr, 0.0, 0.25 + math.sin(a) * rr)
        tilt = V(rng.uniform(-0.3, 0.3), 1.0, rng.uniform(-0.6, 0.2)).normalized()
        ln = rng.uniform(0.35, 0.7) if k < 10 else 0.5
        if k >= 10:
            tilt = V(rng.uniform(-1, 1), 0.1, rng.uniform(-1, 1)).normalized()
            p = V(rng.uniform(-0.9, 0.9), 0.05, rng.uniform(-1.9, -1.1))
        log(g, rng, p, p + tilt * ln, rng.uniform(0.04, 0.07), mat=M_BARK, col=charred(rng), sides=6)
    # The vent at the crown and the turf sods slid off.
    tube(g, [V(0.05, 0.85, 0.3), V(0.05, 1.12, 0.3)], [0.15, 0.17], 10, M_EARTH, (0.1, 0.09, 0.085), tile=0.5, cap=False)
    # Cordwood: one stack standing between stakes, one tumbled; mossed over with shelf fungus.
    for row in range(3):
        for k in range(6 - row):
            y = 0.1 + row * 0.15
            z = -0.4 - (5 - row) * 0.075 + k * 0.15
            log(g, rng, V(1.85, y, z), V(2.65, y, z + rng.uniform(-0.04, 0.04)), 0.07, col=OAK, moss=0.6 if row == 2 else 0.2)
    for z in (-1.0, 0.45):
        pole(g, V(2.25, -0.2, z), V(2.25, 0.75, z), 0.04, 0.035, rng, mat=M_MOSSWOOD, col=ROT_WOOD, sides=6)
    for k in range(6):
        a = rng.uniform(0, 3.1)
        p = V(1.3 + rng.uniform(-0.3, 0.6), 0.07, 1.4 + rng.uniform(-0.4, 0.5))
        log(g, rng, p, p + V(math.cos(a) * 0.8, 0.02, math.sin(a) * 0.8), 0.07, col=OAK, moss=0.7)
    # The burners' tools: a long rake and a wooden shovel leaning on the mound.
    beam(g, [V(-1.6, -0.1, -0.6), V(-0.9, 1.2, -0.1)], 0.045, 0.045, mat=M_MOSSWOOD, col=ROT_WOOD, rng=rng)
    for k in range(5):
        p = V(-1.62, 0.0, -0.65) + V(0.06 * (k - 2), 0.0, -0.05)
        beam(g, [p, p + V(0.0, -0.18, 0.05)], 0.025, 0.025, mat=M_MOSSWOOD, col=ROT_WOOD, rng=rng)
    board(g, V(-1.55, 0.25, 0.9), V(0.35, 1, -0.2), V(0.8, -0.3, 0.5), 0.45, 0.22, 0.03, mat=M_MOSSWOOD, col=ROT_WOOD,
          rng=rng)
    beam(g, [V(-1.45, 0.45, 0.85), V(-1.0, 1.4, 0.6)], 0.035, 0.035, mat=M_MOSSWOOD, col=ROT_WOOD, rng=rng)
    return b


def site_sawpit(rng):
    """Footprint r <= 3.0. Masses: the trunk on its trestles along X at z = 0 (3.8 x 0.35); the pit
    under it is the berm ring (walkable)."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 1.8)
    # The pit: a long low berm of spoil round a dark trench, its rim shored with rotten planks.
    for sg in (-1, 1):
        forest_mound(g, (0.0, -0.08, sg * 1.0), 2.3, 0.42, 0.28, rng, moss=0.7, rings=4, seg=22)
    for sx in (-1, 1):
        forest_mound(g, (sx * 2.15, -0.08, 0.0), 0.4, 1.0, 0.22, rng, moss=0.7, rings=4, seg=14)
    mound(g, (0.0, -0.08, 0.0), 2.2, 0.65, 0.04, rng, mat=M_EARTH, col_fn=lambda p, n: (0.16, 0.13, 0.11), tile=0.8)
    for sg in (-1, 1):
        board(g, V(0.0, 0.04, sg * 0.66), V(1, 0, 0), V(0, 0.2, sg), 4.0, 0.22, 0.05, mat=M_MOSSWOOD, col=ROT_WOOD,
              rng=rng)
    # Two cross-trestles over the pit.
    for x in (-1.2, 1.0):
        beam(g, [V(x, 0.3, -1.1), V(x, 0.3, 1.1)], 0.16, 0.16, mat=M_MOSSWOOD, col=ROT_WOOD, rng=rng, rough=0.05)
        for sg in (-1, 1):
            beam(g, [V(x, -0.15, sg * 1.05), V(x, 0.3, sg * 1.05)], 0.12, 0.12, mat=M_MOSSWOOD, col=ROT_WOOD, rng=rng)
    # The oak trunk: whole bark at the -X end; from x = 0.2 on it is split by the kerf, the top half
    # sawn off as a thick plank still joined at the root of the cut.
    y0 = 0.3 + 0.08 + 0.32
    log(g, rng, V(-2.0, y0, 0.0), V(0.2, y0, 0.0), 0.32, col=OAK, moss=0.35, cap=True, sides=12)
    for half, dy in ((1, 0.17), (-1, -0.17)):
        c0 = V(0.2, y0 + dy, 0.0)
        pts = [c0, c0 + V(0.6, 0.02 * half, 0.0), c0 + V(1.2, 0.05 * half, 0.0), c0 + V(1.75, 0.08 * half, 0.0)]
        for i in range(len(pts) - 1):
            beam(g, [pts[i], pts[i + 1]], 0.6, 0.3, mat=M_BARK if i else M_BARK, mode="bark", col=OAK, rng=rng,
                 chamfer=0.45, cap=(i == 0, i == len(pts) - 2))
        # The pale sawn faces inside the kerf.
        e = pts[-1]
        lbox(g, V(1.1, y0 + dy * 0.45 + 0.06 * half * 0.5, 0.0), (1.6, 0.012, 0.5), quat_z(0.05 * half), M_PLANK,
             (0.95, 0.82, 0.62), tile=0.6, grain=0)
    # The pit saw stuck in the kerf at x = 0.25: a long blade with a tiller on top, a box handle below.
    sx = 0.25
    lbox(g, V(sx, y0, 0.0), (0.09, 2.1, 0.01), quat_z(0.06), M_IRON, (0.3, 0.2, 0.15), tile=0.4, grain=1)
    tube(g, [V(sx + 0.06, y0 + 1.05, -0.35), V(sx + 0.06, y0 + 1.05, 0.35)], [0.03, 0.03], 7, M_MOSSWOOD, ROT_WOOD,
         tile=0.3)
    tube(g, [V(sx - 0.06, y0 - 1.0, -0.2), V(sx - 0.06, y0 - 1.0, 0.2)], [0.025, 0.025], 7, M_MOSSWOOD, ROT_WOOD, tile=0.3)
    # Wedges in the kerf behind the saw.
    for x in (1.2, 1.7):
        stone(g, (x, y0 + 0.02, 0.0), (0.05, 0.12, 0.08), rng, mat=M_PLANK, detail=1, rough=0.0, cuts=0,
              col_fn=lambda p, n: ROT_WOOD, tile=0.3)
    # Sawdust heap under the cut, and sawn planks stacked to one side, mossed.
    mound(g, (0.3, -0.04, 0.0), 0.6, 0.45, 0.16, rng, mat=M_EARTH, col_fn=lambda p, n: mix((0.82, 0.68, 0.5), MOSS,
                                                                                       0.25 * nz(p * 6) + 0.1), tile=0.5)
    for k in range(4):
        board(g, V(-0.6 + rng.uniform(-0.05, 0.05), 0.05 + k * 0.055, 1.65), V(1, 0, rng.uniform(-0.05, 0.05)), V(0, 1, 0),
              2.0, 0.3, 0.05, mat=M_MOSSWOOD, col=ROT_WOOD, rng=rng)
    beam(g, [V(-1.6, 0.04, 1.6), V(-1.62, 0.04, 2.05)], 0.1, 0.08, mat=M_MOSSWOOD, col=ROT_WOOD, rng=rng)
    beam(g, [V(0.5, 0.04, 1.6), V(0.52, 0.04, 2.05)], 0.1, 0.08, mat=M_MOSSWOOD, col=ROT_WOOD, rng=rng)
    return b


def shelf_fungus(g, rng, p, out, s=0.12, col=(0.85, 0.72, 0.5)):
    out = Vector(out).normalized()
    rot = quat_y(math.atan2(out.x, out.z))
    dome(g, Vector(p) + out * s * 0.3, s, rot @ quat_x(0.0), M_CLAY,
         lambda q, n: mix(scale(col, 0.6), col, smoothstep(-0.2, 0.6, n.y)), tile=0.2, rings=3, seg=9, squash=0.35)


def site_rooted_pillar(rng):
    """Footprint r <= 3.2. Masses: the oak's trunk base (0.3, 0.8) r 1.0, the pillar (−0.5, −0.3)."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 5, 1.5)
    forest_mound(g, (0.2, -0.05, 0.4), 2.6, 2.4, 0.35, rng, moss=0.8, power=0.6)
    # The Old Ones' pillar: tall, tapering, leaning out of the root mass, rings cut down its face.
    pc = V(-0.45, 1.15, -0.4)
    prot = quat_x(-0.12) @ quat_z(0.1)
    slab(g, tuple(pc), (0.6, 2.9, 0.5), prot, rng, mat=M_MOSSROCK, res=(3, 10, 2), round_r=0.08, taper=0.3, rough=0.04,
         crown=0.25, col_fn=mossy((0.78, 0.76, 0.7), 0.85, nz, wet=0.55), tile=1.0)
    face = prot @ V(0, 0, -1)
    up = prot @ V(0, 1, 0)
    for k, y in enumerate((-0.1, 0.55, 1.1)):
        c = pc + up * y + face * 0.26
        for rr in (0.06, 0.12, 0.18 - k * 0.02):
            ring_on(g, c, face, up, rr, (0.2, 0.22, 0.17), r=0.012, mat=M_MOSSROCK)
    # The giant oak: a dead hollow snag, broken at ~4u, its roots poured over and around the pillar.
    tc = V(0.45, 0.0, 0.85)
    pts = [tc + V(0, -0.3, 0), tc + V(0.0, 0.25, 0.0), tc + V(0.0, 0.8, 0.02), tc + V(-0.05, 2.0, 0.06),
           tc + V(-0.12, 3.0, 0.1), tc + V(-0.2, 4.1, 0.14)]
    tube(g, pts, [1.5, 1.15, 0.92, 0.78, 0.72, 0.66], 18, M_BARK, (0.55, 0.5, 0.44), tile=1.2,
         col_fn=lambda t: mix((0.55, 0.5, 0.44), MOSS, 0.45 * (1 - t)), cap=False)
    # The jagged broken top: a dark hollow ring of splinters.
    top = pts[-1]
    for k in range(14):
        a = k / 14 * 2 * math.pi
        h = rng.uniform(0.1, 0.7)
        base_ = top + V(math.cos(a) * 0.6, 0, math.sin(a) * 0.6)
        beam(g, [base_ - V(0, 0.05, 0), base_ + V(math.cos(a) * 0.05, h, math.sin(a) * 0.05)], 0.22, 0.1, mat=M_BARK,
             mode="bark", col=(0.5, 0.45, 0.4), rng=rng, point=0.1, up=(math.cos(a), 0, math.sin(a)))
    disc(g, top + V(0, 0.02, 0), quat_x(0.0), 0.58, 0.04, 14, M_EARTH, (0.06, 0.05, 0.05))
    # Roots: thick, snaking down into the ground; two wrap in front of the pillar's foot.
    roots = [
        [V(0.0, 0.6, 0.3), V(-0.5, 0.35, -0.05), V(-0.95, 0.2, -0.55), V(-1.2, -0.1, -1.0)],
        [V(0.2, 0.55, 0.2), V(-0.1, 0.4, -0.45), V(-0.3, 0.3, -0.75), V(-0.75, 0.05, -0.9), V(-1.0, -0.15, -0.7)],
        [V(1.1, 0.5, 0.6), V(1.7, 0.2, 0.2), V(2.2, -0.15, -0.3)],
        [V(1.0, 0.5, 1.4), V(1.6, 0.2, 2.0), V(2.0, -0.15, 2.4)],
        [V(-0.3, 0.5, 1.3), V(-1.0, 0.25, 1.8), V(-1.7, -0.15, 2.0)],
        [V(-0.4, 0.55, 0.7), V(-1.2, 0.3, 0.6), V(-1.9, 0.05, 0.3), V(-2.4, -0.15, 0.1)],
        [V(0.6, 0.5, 0.0), V(0.7, 0.3, -0.7), V(0.5, 0.1, -1.4), V(0.3, -0.15, -1.9)],
    ]
    for k, rp in enumerate(roots):
        rr = [0.32 * (1 - 0.7 * i / (len(rp) - 1)) + 0.03 for i in range(len(rp))]
        if k < 2:
            rr = [x * 0.6 for x in rr]
        tube(g, rp, rr, 9, M_BARK, (0.5, 0.46, 0.4), tile=0.8,
             col_fn=lambda t: mix((0.5, 0.46, 0.4), MOSS, 0.55 * smoothstep(0.2, 1.0, t)), cap=True)
    # Shelf fungus in tiers up the trunk, and a few mushrooms in the moss.
    for k in range(7):
        a = 2.2 + k * 0.35
        y = 1.0 + k * 0.32
        p = tc + V(math.cos(a) * 0.85, y, math.sin(a) * 0.85)
        shelf_fungus(g, rng, p, V(math.cos(a), 0, math.sin(a)), s=rng.uniform(0.1, 0.18))
    for k in range(9):
        p = V(rng.uniform(-1.8, 1.8), 0.15, rng.uniform(-1.6, -0.6))
        tube(g, [p - V(0, 0.15, 0), p + V(0, 0.06, 0)], [0.012, 0.01], 5, M_CLAY, (0.9, 0.86, 0.78), tile=0.2)
        dome(g, p + V(0, 0.05, 0), 0.04, quat_y(0.0), M_CLAY, lambda q, n: (0.62, 0.36, 0.2), tile=0.2, rings=2, seg=8,
             squash=0.6)
    return b


def site_anselm_forest(rng):
    """Footprint r <= 3.0. Masses: the hollow oak stump (1.6, 0.5) r 0.75; the graves are low mounds."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 1.8)
    forest_mound(g, (0.0, -0.06, 0.0), 2.8, 2.5, 0.08, rng, moss=0.5, power=0.4)
    # Five graves in a row (+ one small one): sunken moss-grown mounds, rough-hewn crosses.
    for k, (x, z, s) in enumerate(((-1.9, -0.3, 1.0), (-1.1, -0.35, 1.0), (-0.3, -0.3, 1.0), (0.45, -0.4, 1.0),
                                   (-1.5, 0.95, 0.55), (-0.6, 0.95, 1.0))):
        forest_mound(g, (x, -0.06, z), 0.36 * s, 0.85 * s, 0.17 * s, rng, moss=0.85, rings=4, seg=14)
        cz = z - 0.8 * s
        lean = rng.uniform(-0.15, 0.15)
        if k == 3:   # one cross fallen across its grave
            beam(g, [V(x - 0.1, 0.12, cz + 0.2), V(x + 0.15, 0.1, z + 0.4)], 0.08, 0.06, mat=M_MOSSWOOD, col=ROT_WOOD,
                 rng=rng, jag=(0.05, 0))
            continue
        h = 1.0 * s
        rot = quat_x(lean) @ quat_z(rng.uniform(-0.1, 0.1))
        foot = V(x, -0.2, cz)
        beam(g, [foot, foot + rot @ V(0, h + 0.2, 0)], 0.09, 0.07, mat=M_MOSSWOOD, col=ROT_WOOD, rng=rng)
        arm = foot + rot @ V(0, h * 0.82, 0)
        beam(g, [arm - rot @ V(0.28 * s, 0, 0), arm + rot @ V(0.28 * s, 0, 0)], 0.07, 0.06, mat=M_MOSSWOOD, col=ROT_WOOD,
             rng=rng)
        tube(g, [arm + rot @ V(0.05 * math.cos(t), 0.05 * math.sin(t), 0.045) for t in np.linspace(0, 6.3, 7)],
             [0.007] * 7, 3, M_CLOTH, scale(W.ROPE, 0.5), tile=0.2, cap=False)
        for m in range(int(rng.integers(0, 3))):   # mushrooms on the mound
            p = V(x + rng.uniform(-0.2, 0.2), 0.1, z + rng.uniform(-0.4, 0.4))
            tube(g, [p - V(0, 0.08, 0), p + V(0, 0.05, 0)], [0.01, 0.008], 5, M_CLAY, (0.9, 0.86, 0.78), tile=0.2)
            dome(g, p + V(0, 0.04, 0), 0.035, quat_y(0.0), M_CLAY, lambda q, n: (0.75, 0.6, 0.42), tile=0.2, rings=2,
                 seg=8, squash=0.5)
    # A rotten paling once round the plot: stubs and one fallen section.
    for k in range(9):
        x = -2.5 + k * 0.48
        if k in (3, 4):
            continue
        h = rng.uniform(0.25, 0.7)
        beam(g, [V(x, -0.2, -1.75), V(x + rng.uniform(-0.05, 0.05), h, -1.75)], 0.06, 0.05, mat=M_MOSSWOOD, col=ROT_WOOD,
             rng=rng, jag=(0, 0.06))
    beam(g, [V(-1.1, 0.05, -2.0), V(-0.1, 0.05, -2.3)], 0.06, 0.04, mat=M_MOSSWOOD, col=ROT_WOOD, rng=rng)
    # The hollow oak stump, its open side toward the graves; the journal page wedged in the hollow.
    tc = V(1.65, 0.0, 0.5)
    n_, rows = 24, 5
    mouth = (2.35, 3.75)          # the hollow's mouth faces -X (the graves)

    def top_h(a):
        return 1.35 + 0.3 * math.sin(a * 2 + 1) + 0.12 * math.sin(a * 5 + 0.3)

    for k in range(n_):
        a0, a1 = k / n_ * 2 * math.pi, (k + 1) / n_ * 2 * math.pi
        if mouth[0] < (a0 + a1) / 2 < mouth[1]:
            continue
        for wall, r_, sgn in ((0, 0.78, 1), (1, 0.62, -1)):
            for j in range(rows):
                f0, f1 = j / rows, (j + 1) / rows
                quad, nrm, cols = [], [], []
                for a, f in ((a0, f0), (a1, f0), (a1, f1), (a0, f1)):
                    hh = -0.2 + (top_h(a) + 0.2) * f
                    rr = r_ * (1.0 + 0.25 * (1 - f) ** 3) if wall == 0 else r_
                    quad.append(tc + V(math.cos(a) * rr, hh, math.sin(a) * rr))
                    nrm.append(V(math.cos(a) * sgn, 0.1, math.sin(a) * sgn).normalized())
                    cols.append(mix(OAK, MOSS, 0.55 * (1 - f)) if wall == 0 else (0.3, 0.24, 0.18))
                uvs = [(a0 * 0.78 / 0.9, quad[0].y / 0.9), (a1 * 0.78 / 0.9, quad[1].y / 0.9),
                       (a1 * 0.78 / 0.9, quad[2].y / 0.9), (a0 * 0.78 / 0.9, quad[3].y / 0.9)]
                if wall == 1:
                    quad, uvs, nrm, cols = quad[::-1], uvs[::-1], nrm[::-1], cols[::-1]
                g.poly(quad, uvs, nrm, cols, M_BARK if wall == 0 else M_MOSSWOOD)
        # the rotten rim between the walls
        o0, o1 = (tc + V(math.cos(a) * 0.78, top_h(a), math.sin(a) * 0.78) for a in (a0, a1))
        i0, i1 = (tc + V(math.cos(a) * 0.62, top_h(a), math.sin(a) * 0.62) for a in (a0, a1))
        g.flat([o0, o1, i1, i0], M_MOSSWOOD, ROT_WOOD, 0.4)
        g.flat([i0, i1, o1, o0], M_MOSSWOOD, ROT_WOOD, 0.4)
    for a in mouth:   # the mouth's cut edges
        q = [tc + V(math.cos(a) * 0.78, -0.2, math.sin(a) * 0.78), tc + V(math.cos(a) * 0.62, -0.2, math.sin(a) * 0.62),
             tc + V(math.cos(a) * 0.62, top_h(a), math.sin(a) * 0.62), tc + V(math.cos(a) * 0.78, top_h(a), math.sin(a) * 0.78)]
        g.flat(q, M_MOSSWOOD, ROT_WOOD, 0.4)
        g.flat(q[::-1], M_MOSSWOOD, ROT_WOOD, 0.4)
    disc(g, tc + V(0, 0.06, 0), quat_x(0.0), 0.62, 0.04, 14, M_EARTH, (0.2, 0.16, 0.12))
    for k in range(5):   # shelf fungus on the stump
        a = 0.3 + k * 0.6
        shelf_fungus(g, rng, tc + V(math.cos(a) * 0.74, 0.5 + k * 0.2, math.sin(a) * 0.74), V(math.cos(a), 0, math.sin(a)),
                     s=0.12)
    # The page and the journal's cover, wedged upright in the hollow's mouth, a stone to keep the rain off.
    pp = tc + V(-0.45, 0.45, -0.05)
    page(g, pp, quat_z(math.pi / 2 - 0.25) @ quat_y(0.1), w=0.2, l=0.28, curl=0.02)
    lbox(g, tc + V(-0.35, 0.38, 0.12), (0.04, 0.32, 0.24), quat_z(-0.25), M_HIDE, (0.32, 0.2, 0.13), tile=0.3)
    slab(g, tuple(tc + V(-0.3, 0.6, 0.0)), (0.32, 0.07, 0.4), quat_z(0.2), rng, mat=M_MOSSROCK, res=(2, 1, 2),
         round_r=0.02, col_fn=mossy((0.7, 0.7, 0.66), 0.4, nz), tile=0.4)
    # A rough wooden marker board at the head of the row: scratched lines (names), weathered illegible.
    mc = V(-2.55, 0.0, -0.9)
    beam(g, [mc - V(0, 0.2, 0), mc + V(0.02, 0.95, 0)], 0.08, 0.06, mat=M_MOSSWOOD, col=ROT_WOOD, rng=rng)
    board(g, mc + V(0.05, 0.7, -0.05), V(1, 0.05, 0), V(0, 0, -1), 0.6, 0.3, 0.035, mat=M_MOSSWOOD, col=ROT_WOOD, rng=rng)
    for k in range(4):
        y = 0.79 - k * 0.06
        carve_line(g, [mc + V(-0.18, y, -0.075), mc + V(0.12 + 0.08 * (k % 2), y, -0.075)], (0.2, 0.17, 0.14), 0.006,
                   M_MOSSWOOD)
    return b


MODELS = {
    "site_trading_stones": site_trading_stones,
    "site_survey_line": site_survey_line,
    "site_drowned_outpost": site_drowned_outpost,
    "site_glyph_wall": site_glyph_wall,
    "site_looted_caravan": site_looted_caravan,
    "site_anselm_desert": site_anselm_desert,
    "site_bell_pit": site_bell_pit,
    "site_charcoal_kiln": site_charcoal_kiln,
    "site_sawpit": site_sawpit,
    "site_rooted_pillar": site_rooted_pillar,
    "site_anselm_forest": site_anselm_forest,
}

if __name__ == "__main__":
    clear_scene()
    objs = []
    report = {}
    only = set(sys.argv[sys.argv.index("--") + 1:]) if "--" in sys.argv else set()
    for i, (name, fn) in enumerate(MODELS.items()):
        b = fn(np.random.default_rng(5200 + i))
        report[name] = (bounds(b), b.tris())
        objs.append(b.build(name, MATS))
    export_glb(OUT / "sites_warm.glb", objs)
    for k, v in report.items():
        print(f"{k}: {v}")
    print("SITES_WARM_DONE")
