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
from stories_cold import (M_SNOW, M_BRONZE, BRONZE, VERDIGRIS, disc, dome, wheel, sack, lathe, orient)  # noqa: E402

M_SAND = M_BRONZE + 1       # s_sandstone
M_TILE = M_BRONZE + 2       # s_tile
M_MOSSWOOD = M_BRONZE + 3   # s_mosswood
M_CLAY = M_BRONZE + 4       # s_clay
M_MOSSROCK = M_BRONZE + 5   # s_mossrock
M_PLASTER = M_BRONZE + 6    # s_plaster (salt, bleached bone, paper)
MATS = W.MATS + ["s_snow", "bronze", "s_sandstone", "s_tile", "s_mosswood", "s_clay", "s_mossrock", "s_plaster"]

# Desert palette (multiplies the scans).
SAND = (0.97, 0.9, 0.78)             # loose drift sand over s_sandstone
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
DUNE = (0.82, 0.62, 0.31)            # wind-laid sand over the (cool, bright) s_snow grain scan -> the terrain's sand
INK = (0.12, 0.1, 0.09)


# ─────────────────────────────────────────────────────────────── shared helpers
def sand_drift(g, centre, rx, rz, h, rng, power=0.9, skirt=0.15, rings=5, seg=18, edge=0.2):
    """A drift / dune of loose sand: the fine s_snow grain scan tinted to the desert's sand."""
    nz = Noise(rng, 4, 1.4)
    mound(g, centre, rx, rz, h, rng, mat=M_SNOW, col_fn=sand_col(nz), tile=1.6, rings=rings, seg=seg, skirt=skirt,
          rough=0.06, edge=edge, power=power)


def forest_mound(g, centre, rx, rz, h, rng, moss=0.7, base=DAMP_EARTH, power=0.8, rings=5, seg=18, skirt=0.15):
    nz = Noise(rng, 4, 2.0)

    def f(p, n):
        m = moss * smoothstep(0.2, 0.8, n.y) * (0.6 + 0.4 * nz(p * 2.5))
        return mix(scale(base, 0.85 + 0.15 * nz(p * 4)), MOSS, max(0.0, min(m, 1.0)))
    mound(g, centre, rx, rz, h, rng, mat=M_EARTH, col_fn=f, tile=1.0, rings=rings, seg=seg, skirt=skirt, rough=0.1,
          power=power)


def sun_rock(base=SANDSTONE, varnish=0.0, sand=0.35, nz=None):
    """Sandstone tint: sun-bleached crowns, desert varnish streaking down the vertical faces (in runs,
    not a coat), sand-dusted toward the foot."""
    def f(p, n):
        k = 0.9 + (0.1 * nz(p * 3.0) if nz else 0.0)
        c = scale(base, k)
        streak = 0.55 + 0.45 * math.sin(p.x * 9.0 + p.z * 7.0 + (2.0 * nz(p * 1.5) if nz else 0.0)) if nz else 1.0
        c = mix(c, VARNISH, varnish * streak * (1.0 - smoothstep(0.2, 0.7, abs(n.y))))
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


def carve_line(g, pts, col, r=0.012, mat=M_ROCK, proj=None):
    """`proj`: maps each point onto a curved face (so pecked lines follow the rock)."""
    pts = [Vector(p) for p in pts]
    if proj is not None:
        pts = [proj(p) for p in pts]
    tube(g, pts, [r] * len(pts), 4, mat, col, tile=0.2, cap=False)


def ring_on(g, c, face, up, rr, col, r=0.012, mat=M_ROCK, n=15, arc=(0.0, 2 * math.pi), proj=None):
    face, up = Vector(face).normalized(), Vector(up).normalized()
    right = up.cross(face).normalized()
    up = face.cross(right).normalized()
    pts = [Vector(c) + (right * math.cos(t) + up * math.sin(t)) * rr for t in np.linspace(arc[0], arc[1], n)]
    carve_line(g, pts, col, r, mat, proj)


def tusk_figure(g, c, face, up, s, col, mat=M_ROCK, arms_up=True, proj=None):
    """A pecked stick figure with tusks: head ring, body, arms raised (or out), legs."""
    face, up = Vector(face).normalized(), Vector(up).normalized()
    right = up.cross(face).normalized()
    c = Vector(c)
    head = c + up * 0.32 * s
    ring_on(g, head, face, up, 0.05 * s, col, r=0.018, mat=mat, n=9, proj=proj)
    body = [c + up * 0.26 * s, c + up * 0.05 * s]
    carve_line(g, body, col, 0.02, mat, proj)
    for sg in (-1, 1):
        sh = c + up * 0.2 * s
        hand = sh + right * sg * 0.13 * s + up * (0.14 if arms_up else -0.02) * s
        carve_line(g, [sh, sh + right * sg * 0.09 * s + up * 0.02 * s, hand], col, 0.018, mat, proj)
        carve_line(g, [c + up * 0.05 * s, c + right * sg * 0.07 * s - up * 0.16 * s], col, 0.018, mat, proj)
        t0 = head - up * 0.035 * s + right * sg * 0.025 * s
        carve_line(g, [t0, t0 + right * sg * 0.03 * s + up * 0.045 * s], col, 0.008, mat, proj)


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


def shelf_fungus(g, rng, p, out, s=0.12, col=(0.85, 0.72, 0.5)):
    out = Vector(out).normalized()
    rot = quat_y(math.atan2(out.x, out.z))
    dome(g, Vector(p) + out * s * 0.3, s, rot @ quat_x(0.0), M_CLAY,
         lambda q, n: mix(scale(col, 0.6), col, smoothstep(-0.2, 0.6, n.y)), tile=0.2, rings=3, seg=9, squash=0.35)



# ─────────────────────────────────────────────────────────────── construction parts
def cut_block(g, rng, c, size, rot, nz, mat=M_SAND, col=SANDSTONE, varnish=0.25, sand=0.3, chip=1, round_r=0.022,
              tile=0.9):
    """One dressed block: crisp bevelled edges, a chipped corner or two, its own tone."""
    k = rng.uniform(0.86, 1.06)
    res = (max(2, int(size[0] / 0.18)), max(2, int(size[1] / 0.18)), max(2, int(size[2] / 0.18)))
    slab(g, tuple(c), size, rot, rng, mat=mat, res=res, round_r=round_r, rough=0.012, cuts=chip,
         col_fn=sun_rock(base=scale(col, k), varnish=varnish, sand=sand, nz=nz) if mat == M_SAND else
         (lambda p, n, kk=k: scale(col, kk)), tile=tile)


def coursed_wall(g, rng, a, b, y0, course_h, depth, nz, top_fn, skip_fn=None, mat=M_SAND, col=SANDSTONE, varnish=0.3,
                 gap=0.018, lmin=0.34, lmax=0.58, mortar=(0.42, 0.33, 0.25), drop=0.04):
    """A dry-laid / lime-pointed wall of coursed blocks from XZ point `a` to `b`: running bond, a ragged
    ruined top (`top_fn(t)` = wall height at distance t along it), openings (`skip_fn(t, y)` True =
    leave out), a block missing here and there, a dark mortar core showing in the joints."""
    a, b = Vector((a[0], 0, a[1])), Vector((b[0], 0, b[1]))
    L = (b - a).length
    d = (b - a) / L
    yaw = math.atan2(-d.z, d.x)
    rot = quat_y(yaw)
    y = y0
    row = 0
    while True:
        t = -rng.uniform(0.0, lmax * 0.5) if row % 2 else 0.0
        placed = False
        while t < L - 0.05:
            ln = min(rng.uniform(lmin, lmax), L - max(t, 0.0))
            t0, t1 = max(t, 0.0), min(t + ln, L)
            tm = (t0 + t1) / 2
            yc = y + course_h / 2
            if t1 - t0 > 0.12 and y + course_h * 0.5 < top_fn(tm) and not (skip_fn and skip_fn(tm, yc)) \
                    and rng.uniform() > drop:
                c = a + d * tm + Vector((0, yc, 0))
                cut_block(g, rng, c, (t1 - t0 - gap, course_h - gap, depth * rng.uniform(0.94, 1.0)),
                          rot @ quat_z(rng.uniform(-0.012, 0.012)) @ quat_y(rng.uniform(-0.02, 0.02)), nz, mat=mat,
                          col=col, varnish=varnish, chip=1 if rng.uniform() < 0.25 else 0)
                lbox(g, c, (t1 - t0 + gap * 1.5, course_h + gap * 1.2, depth * 0.8), rot, M_SAND if mat == M_SAND else mat,
                     mortar, tile=0.5)
                placed = True
            t += ln
        y += course_h
        row += 1
        if not placed and y > y0 + course_h * 3 or y > 6.0:
            break


def voussoir_arch(g, rng, centre, half_span, spring, depth, rot, nz, n=9, ring=0.32, missing=(), col=SANDSTONE):
    """The arch ring over an opening: `n` wedge voussoirs with joints, a proud keystone, impost blocks."""
    c = Vector(centre)
    for k in range(n):
        if k in missing:
            continue
        a0, a1 = math.pi * k / n, math.pi * (k + 1) / n
        am = (a0 + a1) / 2
        rr = half_span + ring / 2
        key = k == n // 2
        p = c + rot @ V(-math.cos(am) * rr, spring + math.sin(am) * rr + (0.04 if key else 0.0), 0)
        sz = (ring * (1.18 if key else 1.0), rr * (a1 - a0) - 0.02, depth + (0.04 if key else 0.0))
        cut_block(g, rng, p, sz, rot @ quat_z(math.pi - am), nz, col=col, varnish=0.35, chip=0)
    for sg in (-1, 1):   # imposts
        cut_block(g, rng, c + rot @ V(sg * (half_span + 0.12), spring - 0.07, 0), (0.42, 0.14, depth + 0.08), rot, nz,
                  col=scale(col, 0.95), varnish=0.3, chip=1)


def fallen_blocks(g, rng, n, cx, cz, spread, nz, size=(0.45, 0.28, 0.4), y=0.0, col=SANDSTONE, mat=M_SAND):
    for _ in range(n):
        s = rng.uniform(0.75, 1.1)
        c = V(cx + rng.uniform(-spread[0], spread[0]), y + size[1] * s * 0.32, cz + rng.uniform(-spread[1], spread[1]))
        cut_block(g, rng, c, (size[0] * s, size[1] * s, size[2] * s),
                  quat_y(rng.uniform(0, 6.28)) @ quat_x(rng.uniform(-0.35, 0.35)) @ quat_z(rng.uniform(-0.35, 0.35)), nz,
                  mat=mat, col=col, varnish=0.2, chip=2)


def chips(g, rng, n, cx, cz, spread, col_fn, mat=M_SAND, rmin=0.03, rmax=0.1, y=0.0):
    for _ in range(n):
        r = rng.uniform(rmin, rmax)
        stone(g, (cx + rng.uniform(-spread, spread), y + r * 0.2, cz + rng.uniform(-spread, spread)),
              (r, r * rng.uniform(0.45, 0.75), r * rng.uniform(0.7, 1.0)), rng, mat=mat, detail=0, rough=0.1, cuts=2,
              col_fn=col_fn, tile=0.4)


def sand_wedge(g, rng, a, b, depth, h, side, power=1.3):
    """A drift banked against a wall along a->b (XZ), on the `side` (+1/-1 along the wall normal)."""
    a, b = Vector((a[0], 0, a[1])), Vector((b[0], 0, b[1]))
    d = (b - a).normalized()
    nrm = Vector((-d.z, 0, d.x)) * side
    L = (b - a).length
    nzn = Noise(rng, 3, 1.6)
    nu, nv = max(3, int(L / 0.3)), 5
    verts, tris = [], []
    for i in range(nu + 1):
        u = i / nu
        hh = h * (math.sin(u * math.pi) ** 0.6) * (0.75 + 0.25 * nzn(a + d * L * u))
        for j in range(nv + 1):
            v = j / nv
            p = a + d * (L * u) + nrm * (0.02 + depth * v)
            verts.append(Vector((p.x, hh * (1 - v) ** power - 0.06 * v, p.z)))
    for i in range(nu):
        for j in range(nv):
            k = i * (nv + 1) + j
            tris += [(k, k + nv + 1, k + nv + 2), (k, k + nv + 2, k + 1)]
    out = []
    for t in tris:
        n = (verts[t[1]] - verts[t[0]]).cross(verts[t[2]] - verts[t[0]])
        out.append(t if n.y > 0 else (t[0], t[2], t[1]))
    smooth_mesh(g, verts, out, M_SNOW, sand_col(nzn), 1.5)


def sand_col(nzn):
    def f(p, n):
        k = 0.94 + 0.06 * nzn(p * 2.3)
        lee = 0.92 + 0.08 * smoothstep(0.3, 0.95, n.y)
        return scale(DUNE, k * lee)
    return f


def wind_dune(g, rng, centre, rx, rz, h, yaw, nu=40, nv=18, wave=0.34, amp=0.022, crest=0.3):
    """A wind-built dune (local +X = downwind, turned by `yaw`): a long windward ramp scored with ripples
    running across the wind, a sharp brink, a straight steep slip face; the rim sinks below the ground.
    Ripple crests catch light, troughs hold darker grains; the slip face is smooth."""
    c = Vector(centre)
    rq = quat_y(yaw)
    inv = rq.inverted()
    nz = Noise(rng, 4, 1.2)
    uc = crest + rng.uniform(-0.05, 0.05)

    def phase(u, v):
        return u * rx * 2 * math.pi / wave + 0.8 * math.sin(v * rz * 1.4) + 1.8 * nz(V(u * 0.7, v * 0.7, 0))

    def rip_w(u):
        return smoothstep(-1.0, -0.6, u) * smoothstep(uc, uc - 0.12, u)

    verts = []
    for i in range(nu + 1):
        u = -1 + 2 * i / nu
        for j in range(nv + 1):
            v = -1 + 2 * j / nv
            across = max(0.0, 1 - abs(v) ** 1.7) ** 0.55 * (1 + 0.1 * math.sin(v * 2.7 + u * 1.3))
            if u <= uc:
                sw = (u + 1) / (uc + 1)
                prof = sw ** 1.3 * (1.3 - 0.3 * sw)
            else:
                prof = max(0.0, 1 - (u - uc) / (1 - uc)) ** 1.1
            y = h * prof * across + amp * math.sin(phase(u, v)) * rip_w(u) * min(1.0, across * 3)
            y -= 0.3 * max(abs(u), abs(v)) ** 6
            verts.append(c + rq @ V(u * rx, y, v * rz))
    tris = []
    for i in range(nu):
        for j in range(nv):
            a, b2, c2, d2 = i * (nv + 1) + j, (i + 1) * (nv + 1) + j, (i + 1) * (nv + 1) + j + 1, i * (nv + 1) + j + 1
            for t in ((a, b2, c2), (a, c2, d2)):
                if max(verts[q].y for q in t) < -0.08:
                    continue
                n = (verts[t[1]] - verts[t[0]]).cross(verts[t[2]] - verts[t[0]])
                tris.append(t if n.y >= 0 else (t[0], t[2], t[1]))

    def col(p, n):
        q = inv @ (p - c)
        u, v = q.x / rx, q.z / rz
        k = 0.93 + 0.07 * nz(p * 2.3)
        r = math.sin(phase(u, v)) * rip_w(u)
        k *= 1.0 + 0.07 * r                                  # light crests, dark troughs
        if u > uc:
            k *= 0.97                                        # the slip face: a smooth fresh fall
        k *= 0.9 + 0.1 * smoothstep(-0.2, 0.15, p.y)         # damp-dark grains at the toe
        return scale(DUNE, k)
    smooth_mesh(g, verts, tris, M_SNOW, col, 1.6)


def heightfield(g, x0, x1, z0, z1, step, hfn, col_fn, mat=M_EARTH, tile=1.0, cull=None):
    """A height grid; `cull`: drop triangles lying wholly below that height (buried ground)."""
    nx, nzc = max(2, int((x1 - x0) / step)), max(2, int((z1 - z0) / step))
    verts, tris = [], []
    for i in range(nx + 1):
        for j in range(nzc + 1):
            x, z = x0 + (x1 - x0) * i / nx, z0 + (z1 - z0) * j / nzc
            verts.append(Vector((x, hfn(x, z), z)))
    for i in range(nx):
        for j in range(nzc):
            k = i * (nzc + 1) + j
            for t in ((k, k + nzc + 1, k + nzc + 2), (k, k + nzc + 2, k + 1)):
                if cull is not None and max(verts[q].y for q in t) < cull:
                    continue
                n = (verts[t[1]] - verts[t[0]]).cross(verts[t[2]] - verts[t[0]])
                tris.append(t if n.y > 0 else (t[0], t[2], t[1]))
    smooth_mesh(g, verts, tris, mat, col_fn, tile)


def rect_dist(x, z, cx, cz, hx, hz):
    """Signed distance to a rectangle: square inside (the cut walls), rounded outside (the bank's toe)."""
    dx, dz = abs(x - cx) - hx, abs(z - cz) - hz
    if dx < 0 and dz < 0:
        return max(dx, dz)
    return math.hypot(max(dx, 0.0), max(dz, 0.0))


def pit_bank(hx, hz, h, plateau, slope, nzn, cx=0.0, cz=0.0):
    """Height of a heaped spoil bank round a rectangular pit (inner half extents hx, hz): the cut inner
    wall, a lumpy rounded crest of thrown-out clods (heaps and saddles along it, never a flat shelf), an
    outer slope whose toe wanders in lobes and bays and sinks below 0."""
    w = plateau + slope
    tc = 0.55 * plateau / w

    def f(x, z):
        d = rect_dist(x, z, cx, cz, hx, hz)
        p = Vector((x, 0, z))
        if d < -0.04:
            return -0.02 + 0.03 * nzn(p * 3)
        lip = h * (1.0 + 0.05 * nzn(Vector((x, 5, z)) * 1.1))
        heap = 0.1 + 0.2 * nzn(p * 0.8) + 0.08 * nzn(Vector((z, 2, x)) * 1.7)    # heaps and saddles
        clods = 0.05 * nzn(Vector((x, 7, z)) * 2.4) + 0.03 * nzn(Vector((z, 9, x)) * 3.6)
        if d < 0.06:
            return -0.02 + (lip + clods + 0.02) * smoothstep(-0.04, 0.06, d)
        t = (d - 0.06) / w * (1.0 + 0.24 * nzn(Vector((x, 3, z)) * 1.2))      # lobed toe
        if t < tc:
            prof = 1.0 + heap * math.sin(0.5 * math.pi * t / tc) ** 0.7
        else:
            e = (t - tc) / (1.0 - tc)
            top = 1.0 + heap
            prof = top * (1.0 - smoothstep(0.0, 1.0, e) ** 0.85) if e < 1.0 else 0.0
        y = lip * prof + clods * min(1.0, prof * 3.0)
        e2 = (t - tc) / (1.0 - tc)
        return y - 0.14 * smoothstep(0.85, 1.1, e2)
    return f


def nail(g, p, nrm, r=0.012):
    p, nrm = Vector(p), Vector(nrm).normalized()
    disc(g, p + nrm * 0.004, Vector((0, 1, 0)).rotation_difference(nrm), r, 0.008, 6, M_IRON, (0.22, 0.17, 0.14))


def strap(g, a, b, nrm, w=0.04, nails_n=3):
    """A flat iron strap from a to b on a surface with normal `nrm`, nailed."""
    a, b, nrm = Vector(a), Vector(b), Vector(nrm).normalized()
    beam(g, [a + nrm * 0.006, b + nrm * 0.006], w, 0.008, up=tuple(nrm), mat=M_IRON, mode="bark", col=(0.28, 0.2, 0.15),
         chamfer=0.1)
    for k in range(nails_n):
        nail(g, a.lerp(b, (k + 0.5) / nails_n) + nrm * 0.008, nrm, 0.01)


def plank_wall(g, rng, a, b, y0, n, w, thick, nrm, col=ROT_WOOD, mat=M_MOSSWOOD, missing=()):
    """Horizontal planks stacked edge-on from y0 along a->b (3D points at y=0), faces toward `nrm`."""
    a, b = Vector(a), Vector(b)
    L = (b - a).length
    d = (b - a) / L
    for k in range(n):
        if k in missing:
            continue
        c = (a + b) / 2 + Vector((0, y0 + w * (k + 0.5), 0)) + Vector(nrm) * rng.uniform(-0.01, 0.01)
        board(g, c, d, nrm, L * rng.uniform(0.96, 1.0), w * 0.94, thick, mat=mat,
              col=scale(col, rng.uniform(0.85, 1.05)), rng=rng)
        for e in (0.08, 0.92):
            nail(g, a.lerp(b, e) + Vector((0, y0 + w * (k + 0.5), 0)) + Vector(nrm) * (thick / 2 + 0.002), nrm, 0.009)


def strata_outcrop(g, rng, layers, back_z, nz, mat=M_SAND, joints=3):
    """A natural sandstone outcrop: horizontal beds stacked up, each its own tone and set-back (weak
    beds recessed, hard beds projecting as ledges), split by vertical joints into jointed blocks with
    ragged ends. `layers`: (y_bottom, thickness, front_z, x0, x1, colour, rough)."""
    for (yb, th, fz, x0, x1, col, rough) in layers:
        depth = back_z - fz
        cuts = sorted(rng.uniform(x0 + 0.4, x1 - 0.4, size=joints - 1)) if joints > 1 else []
        xs = [x0] + list(cuts) + [x1]
        for i in range(len(xs) - 1):
            a_, b_ = xs[i] + 0.03, xs[i + 1] - 0.03
            if b_ - a_ < 0.25:
                continue
            fz_i = fz + (0.0 if rough < 0.01 else rng.uniform(-0.06, 0.06))
            c = V((a_ + b_) / 2, yb + th / 2 + rng.uniform(-0.02, 0.02), (fz_i + back_z) / 2)
            slab(g, tuple(c), (b_ - a_, th, back_z - fz_i), quat_y(rng.uniform(-0.03, 0.03)) @ quat_z(rng.uniform(-0.015, 0.015)),
                 rng, mat=mat, res=(max(3, int((b_ - a_) / 0.25)), 2, max(2, int(depth / 0.3))), round_r=0.05,
                 rough=rough, cuts=1 if rough < 0.01 else 2, col_fn=sun_rock(base=scale(col, rng.uniform(0.94, 1.04)), varnish=0.55, sand=0.25, nz=nz),
                 tile=1.1)


def turf_sod(g, rng, p, nrm, s=1.0):
    nrm = Vector(nrm).normalized()
    rot = Vector((0, 1, 0)).rotation_difference(nrm) @ quat_y(rng.uniform(0, 6.28))
    k = rng.uniform(0.75, 1.05)
    slab(g, tuple(Vector(p) + nrm * 0.03), (0.36 * s, 0.07, 0.28 * s), rot, rng, mat=M_EARTH, res=(2, 1, 2), round_r=0.025,
         rough=0.06, col_fn=lambda q, n: mix(scale(DAMP_EARTH, 0.8 * k), scale(MOSS, k), smoothstep(0.0, 0.7, n.dot(nrm))),
         tile=0.6)


def charcoal_heap(g, rng, cx, cz, r, n, y=0.0):
    for _ in range(n):
        a, rr = rng.uniform(0, 6.28), r * math.sqrt(rng.uniform(0, 1))
        s = rng.uniform(0.025, 0.06)
        h = (1 - rr / r) * r * 0.35
        stone(g, (cx + math.cos(a) * rr, y + h, cz + math.sin(a) * rr), (s * 1.6, s, s), rng, mat=M_ROCK, detail=0,
              rough=0.1, cuts=2, col_fn=lambda p, nn: (0.05, 0.048, 0.046), tile=0.3)


def brick_ring(g, rng, c, r, y0, courses, top_fn, skip_fn=None, brick=(0.23, 0.075, 0.11)):
    """A round furnace shell of fired bricks in running bond (header-out), each brick its own burn
    colour, clay daub in the joints; `top_fn(angle)` = broken top height."""
    c = Vector(c)
    n = max(8, int(2 * math.pi * r / (brick[2] + 0.012)))
    for k in range(courses):
        y = y0 + k * (brick[1] + 0.012) + brick[1] / 2
        for i in range(n):
            a = (i + 0.5 * (k % 2)) / n * 2 * math.pi
            if y > top_fn(a) or (skip_fn and skip_fn(a, y)):
                continue
            p = c + V(math.cos(a) * (r + brick[0] / 2), y, math.sin(a) * (r + brick[0] / 2))
            burn = rng.uniform(0, 1)
            col = mix(FIRED, (0.25, 0.14, 0.1), burn * 0.6 * (1 - smoothstep(0.0, 0.6, y - y0)))
            slab(g, tuple(p), (brick[0], brick[1], brick[2]), quat_y(-a), rng, mat=M_CLAY, res=(2, 1, 2), round_r=0.012,
                 rough=0.01, cuts=int(rng.integers(0, 2)), col_fn=lambda q, nn, cc=col: cc, tile=0.3)
    # clay daub lining (inner shell) up to the lowest broken point
    lo = min(top_fn(2 * math.pi * i / 24) for i in range(24))
    v_, t_ = lathe([(r + 0.01, y0), (r + 0.01, lo)], 18, c, quat_y(0.0))
    smooth_mesh(g, v_, orient(v_, t_, c, V(0, 1, 0), False), M_CLAY, lambda p, nn: (0.12, 0.09, 0.08), 0.4)


def log_dog(g, p, d, s=0.25):
    """An iron log dog (staple) driven across a joint."""
    p, d = Vector(p), Vector(d).normalized()
    tube(g, [p - d * s / 2 - V(0, 0.08, 0), p - d * s / 2, p + d * s / 2, p + d * s / 2 - V(0, 0.08, 0)], [0.015] * 4, 5,
         M_IRON, (0.25, 0.18, 0.13), tile=0.2)


def half_log(g, rng, a, b, r, side, col=OAK, sawn=(0.92, 0.8, 0.6)):
    """One half of a log split lengthwise by a vertical saw cut (side +1/-1 along Z): bark round the
    back, a pale flat sawn face, end grain at both ends."""
    a, b = Vector(a), Vector(b)
    n = 9
    rings = []
    for t in (0.0, 1.0):
        base = a.lerp(b, t)
        ring = [base + V(0, r * math.cos(math.pi * k / (n - 1)), side * (0.008 + r * math.sin(math.pi * k / (n - 1))))
                for k in range(n)]
        rings.append(ring)
    L = (b - a).length
    for k in range(n - 1):
        q = [rings[0][k], rings[0][k + 1], rings[1][k + 1], rings[1][k]]
        out = ((q[0] + q[1]) / 2 - a)
        out.x = 0
        nrm = (q[1] - q[0]).cross(q[3] - q[0])
        if nrm.dot(out) < 0:
            q = q[::-1]
        u0, u1 = k / (n - 1) * math.pi * r / 0.9, (k + 1) / (n - 1) * math.pi * r / 0.9
        g.poly(q, [(u0, 0), (u1, 0), (u1, L / 0.9), (u0, L / 0.9)] if nrm.dot(out) >= 0 else
               [(u0, L / 0.9), (u1, L / 0.9), (u1, 0), (u0, 0)],
               [out.normalized()] * 4, [col] * 4, M_BARK)
    face = [rings[0][0], rings[1][0], rings[1][-1], rings[0][-1]]
    fn = V(0, 0, -side)
    if (face[1] - face[0]).cross(face[3] - face[0]).dot(fn) < 0:
        face = face[::-1]
    g.flat(face, M_PLANK, sawn, 0.6)
    for ring, sgn in ((rings[0], -1), (rings[1], 1)):
        ctr = sum(ring, Vector((0, 0, 0))) / n
        en = (b - a).normalized() * sgn
        for k in range(n - 1):
            tri = [ring[k], ring[k + 1], ctr]
            if (tri[1] - tri[0]).cross(tri[2] - tri[0]).dot(en) < 0:
                tri = tri[::-1]
            g.flat(tri, M_PLANK, scale(sawn, 0.85), 0.4)



# ─────────────────────────────────────────────────────────────── DESERT
def stone_weights(g, rng, x0, y, z, nz):
    """Graded dressed stone weights (cube-ish, bevelled) + two bronze ones turned on a lathe."""
    x = x0
    for k, s in enumerate((0.15, 0.12, 0.095, 0.075, 0.06, 0.045)):
        cut_block(g, rng, V(x, y + s * 0.42, z + rng.uniform(-0.02, 0.02)), (s, s * 0.85, s * 0.9), quat_y(rng.uniform(-0.3, 0.3)),
                  nz, mat=M_STONE, col=(0.48, 0.45, 0.42), chip=1, round_r=0.008)
        x += s * 0.9 + 0.04
    for k, s in enumerate((0.05, 0.035)):
        v_, t_ = lathe([(0.0, 0.0), (s, 0.0), (s * 1.05, s * 0.5), (s * 0.7, s), (s * 0.25, s * 1.1), (0.0, s * 1.15)], 12,
                       V(x + 0.05 + k * 0.1, y, z), quat_y(0.0))
        smooth_mesh(g, v_, t_, M_BRONZE, lambda p, n: mix(BRASS, VERDIGRIS, 0.25), 0.3, inside=V(x + 0.05 + k * 0.1, y + s * 0.5, z))


def site_trading_stones(rng):
    """Footprint r <= 3.0. Masses: the table (0, 0) ~1.1 x 0.65, the two stelae (+-2.0, 0.4),
    the salt stack (-1.3, -0.9)."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 1.5)
    # The table: a dressed slab on two plinths of coursed blocks, its top worn hollow in the middle.
    for x in (-0.62, 0.62):
        for k, (h, w) in enumerate(((0.3, 0.5), (0.26, 0.44))):
            cut_block(g, rng, V(x + rng.uniform(-0.02, 0.02), -0.1 + 0.3 * k + h / 2, 0.0), (w, h - 0.015, 0.62 - 0.05 * k),
                      quat_y(rng.uniform(-0.05, 0.05)), nz, varnish=0.35, chip=2)
    slab(g, (0.0, 0.58, 0.0), (2.0, 0.16, 1.1), quat_y(0.02), rng, mat=M_SAND, res=(10, 2, 6), round_r=0.025, rough=0.008,
         crown=-0.3, cuts=2, col_fn=sun_rock(nz=nz, varnish=0.25, sand=0.0), tile=0.9)
    sand_wedge(g, rng, (-1.0, 0.33), (1.0, 0.33), 0.7, 0.32, 1)        # windward drift banked on the +Z side
    top = 0.66
    # The brass balance: a stepped foot, the upright, the beam, one pan hanging, one dropped.
    v_, t_ = lathe([(0.0, 0.0), (0.1, 0.0), (0.1, 0.02), (0.06, 0.035), (0.03, 0.06), (0.0, 0.06)], 14, V(0.1, top, 0.05), quat_y(0.0))
    smooth_mesh(g, v_, t_, M_BRONZE, lambda p, n: BRASS, 0.3, inside=V(0.1, top + 0.02, 0.05))
    tube(g, [V(0.1, top + 0.05, 0.05), V(0.1, top + 0.62, 0.05)], [0.016, 0.012], 8, M_BRONZE, BRASS, tile=0.3)
    beam_a, beam_b = V(-0.28, top + 0.66, 0.05), V(0.48, top + 0.56, 0.05)
    tube(g, [beam_a, V(0.1, top + 0.62, 0.05), beam_b], [0.01, 0.014, 0.01], 6, M_BRONZE, BRASS, tile=0.3)
    for k in range(3):
        a = k / 3 * 2 * math.pi
        tube(g, [beam_a, beam_a + V(math.cos(a) * 0.1, -0.32, math.sin(a) * 0.1)], [0.003] * 2, 3, M_CLOTH, W.ROPE, tile=0.2,
             cap=False)
    disc(g, beam_a + V(0, -0.34, 0), quat_x(0.0), 0.11, 0.012, 16, M_BRONZE, mix(BRASS, VERDIGRIS, 0.3))
    disc(g, V(0.75, top + 0.035, 0.25), quat_x(0.5) @ quat_z(0.2), 0.11, 0.012, 16, M_BRONZE, BRASS)
    for k in range(2):   # its cords, trailing off the table edge
        tube(g, [V(0.75, top + 0.02, 0.25), V(0.95 + 0.05 * k, top - 0.02, 0.45), V(1.0 + 0.05 * k, top - 0.3, 0.6)],
             [0.003] * 3, 3, M_CLOTH, W.ROPE, tile=0.2, cap=False)
    stone_weights(g, rng, -0.9, top, -0.3, nz)
    # Salt (the caravans' side): cut slabs stacked crosswise, one split, crumbs round the stack.
    for k in range(4):
        slab(g, (-1.35 + rng.uniform(-0.04, 0.04), 0.06 + k * 0.14, -0.95), (0.6, 0.13, 0.36),
             quat_y(0.3 + (k % 2) * 1.4 + rng.uniform(-0.1, 0.1)), rng, mat=M_PLASTER, res=(3, 1, 2), round_r=0.015,
             rough=0.02, col_fn=lambda p, n: scale(SALT, 0.9 + 0.1 * n.y), tile=0.5, cuts=1)
    for k in range(2):
        slab(g, (-1.9 + k * 0.25, 0.04, -0.5 - k * 0.3), (0.3, 0.1, 0.22), quat_y(1.2 + k) @ quat_z(0.15), rng,
             mat=M_PLASTER, res=(2, 1, 2), round_r=0.015, col_fn=lambda p, n: SALT, tile=0.5, cuts=2)
    chips(g, rng, 14, -1.5, -0.8, 0.5, lambda p, n: SALT, mat=M_PLASTER, rmin=0.015, rmax=0.04)
    # Iron (the orks' side): bloom bars, hammered square, laid in crossed layers.
    for k in range(9):
        layer = k // 3
        a = 0.2 + layer * 1.5
        off = (k % 3 - 1) * 0.1
        c = V(1.32 + math.cos(a + 1.57) * off, 0.03 + layer * 0.055, -0.9 + math.sin(a + 1.57) * off)
        d = V(math.cos(a), 0, math.sin(a)) * 0.28
        beam(g, [c - d, c + d], 0.06, 0.05, mat=M_IRON, mode="bark", col=(0.32, 0.24, 0.19), rng=rng, rough=0.12, chamfer=0.25)
    # The two stelae, dressed and chipped, each cut with its people's sign, facing the table.
    for sg, ang in ((-1, 0.1), (1, -0.1)):
        c = V(sg * 2.0, 0.55, 0.4)
        slab(g, tuple(c), (0.5, 1.4, 0.26), quat_y(ang) @ quat_z(sg * 0.04), rng, mat=M_SAND, res=(3, 7, 2),
             round_r=0.03, taper=0.22, rough=0.012, crown=0.25, cuts=2, col_fn=sun_rock(nz=nz, varnish=0.5), tile=0.9)
        cut_block(g, rng, c - V(0, 0.62, 0), (0.7, 0.18, 0.46), quat_y(ang), nz, varnish=0.3, chip=2)
        face, up = V(-sg, 0, -0.15).normalized(), V(0, 1, 0)
        fc = c + V(0, 0.3, 0) + face * 0.265
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
            k = c + V(0, 0.55, 0)
            tube(g, [k + V(math.cos(t) * 0.2, 0.02 * math.sin(3 * t), math.sin(t) * 0.11) for t in np.linspace(0, 6.3, 13)],
                 [0.022] * 13, 5, M_CLOTH, (0.62, 0.32, 0.3), tile=0.2, cap=False)
            grid = [[k + V(0.2, 0.0, -0.05), k + V(0.25, -0.35, -0.12)], [k + V(0.24, 0.0, 0.05), k + V(0.3, -0.33, 0.0)]]
            sheet(g, grid, M_CLOTH, lambda u, v: (0.66, 0.36, 0.32), tile=0.3, double=True)
        sand_wedge(g, rng, (c.x - 0.4, c.z + 0.16), (c.x + 0.4, c.z + 0.16), 0.5, 0.25, 1)
    # The shade awning came down: a pole standing (lashed crossbar), one fallen, guy ropes and pegs,
    # the faded cloth torn and lying on the sand.
    pole(g, V(-0.3, -0.2, 1.45), V(-0.35, 2.0, 1.5), 0.045, 0.035, rng, mat=M_PLANK, col=BLEACHED, sides=8)
    W.lashing(g, V(-0.35, 1.9, 1.5), (0, 1, 0), 0.05, rng)
    pole(g, V(1.6, 0.04, 1.2), V(0.1, 0.12, 2.3), 0.045, 0.035, rng, mat=M_PLANK, col=BLEACHED, sides=8)
    cloth_drape(g, rng, V(0.6, -0.02, 1.75), quat_y(0.15), 2.0, 1.1, (0.72, 0.5, 0.36), sag=0.06, lift=0.25, fade=0.55, slashed=True)
    for p_ in (V(-1.2, 0.0, 2.4), V(0.6, 0.0, 2.75)):
        beam(g, [p_ - V(0, 0.15, 0), p_ + V(0.04, 0.18, 0)], 0.04, 0.04, mat=M_PLANK, col=BLEACHED, rng=rng, point=0.0)
    tube(g, [V(-0.35, 1.95, 1.5), V(-0.8, 1.0, 1.95), V(-1.2, 0.16, 2.4)], [0.007] * 3, 3, M_CLOTH, W.ROPE, tile=0.2, cap=False)
    tube(g, [V(-0.35, 1.95, 1.5), V(0.2, 0.6, 2.3), V(0.6, 0.15, 2.75)], [0.007] * 3, 3, M_CLOTH, W.ROPE, tile=0.2, cap=False)
    # A cold hearth of three stones, a smashed jar, sherds, a coil of rope, chips.
    for k in range(3):
        a = k / 3 * 6.28
        stone(g, (1.5 + math.cos(a) * 0.2, 0.06, 0.9 + math.sin(a) * 0.2), (0.11, 0.09, 0.1), rng, mat=M_SAND, detail=1, cuts=2,
              col_fn=sun_rock(base=(0.4, 0.33, 0.27), nz=nz), tile=0.4)
    charcoal_heap(g, rng, 1.5, 0.9, 0.16, 10)
    jar(g, rng, V(-1.95, -0.02, -1.55), quat_x(1.5) @ quat_z(0.4), h=0.55, broken=0.45)
    shards(g, rng, 16, 0.2, -1.2, 1.6, TERRACOTTA)
    tube(g, [V(1.0 + 0.12 * math.cos(t), 0.02 + 0.003 * t, 1.6 + 0.12 * math.sin(t)) for t in np.linspace(0, 12.5, 30)],
         [0.012] * 30, 4, M_CLOTH, W.ROPE, tile=0.2)
    chips(g, rng, 16, 0.0, 0.0, 2.6, sun_rock(nz=nz, varnish=0.3), rmin=0.03, rmax=0.08)
    return b


def site_survey_line(rng):
    """Footprint r <= 3.0. Local +Z points at the buried pyramid. Masses: the cairn (0, -1.6) r 0.6."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 1.5)
    # The cairn: flat sandstone slabs dry-laid in rings, stepping in, the Crown stone set in its face.
    for k, (n_, r_, y) in enumerate(((9, 0.5, 0.05), (8, 0.44, 0.19), (7, 0.37, 0.33), (6, 0.3, 0.47), (5, 0.22, 0.61),
                                     (4, 0.14, 0.75))):
        for i in range(n_):
            a = i / n_ * 2 * math.pi + k * 0.35
            if k < 3 and abs(math.atan2(math.sin(a + math.pi / 2), math.cos(a + math.pi / 2))) < 0.45:
                continue   # the Crown stone sits here
            s = rng.uniform(0.2, 0.26) * (1 - k * 0.08)
            cut_block(g, rng, V(math.cos(a) * r_, y, -1.6 + math.sin(a) * r_), (s * 1.3, 0.13, s),
                      quat_y(-a) @ quat_x(rng.uniform(-0.08, 0.08)), nz, varnish=0.5, chip=2, round_r=0.02)
    cut_block(g, rng, V(0.0, 0.88, -1.6), (0.22, 0.16, 0.2), quat_y(0.5), nz, varnish=0.4, chip=2)
    cs = V(0.0, 0.3, -2.05)
    slab(g, tuple(cs), (0.5, 0.56, 0.14), quat_x(-0.1), rng, mat=M_STONE, res=(3, 3, 1), round_r=0.02, rough=0.01,
         col_fn=lambda p, n: (0.8, 0.72, 0.6), tile=0.6, cuts=1)
    face, up = V(0, 0.1, -1).normalized(), V(0, 1, 0.1).normalized()
    fc = cs + face * 0.075 + up * 0.06
    cut = (0.3, 0.22, 0.16)
    ring_on(g, fc, face, up, 0.15, cut, r=0.012)
    r = up.cross(face).normalized()
    carve_line(g, [fc - r * 0.08 - up * 0.045, fc + r * 0.08 - up * 0.045], cut, 0.012)
    for k in (-1, 0, 1):
        base_ = fc - up * 0.045 + r * k * 0.065
        carve_line(g, [base_, base_ + up * (0.12 if k == 0 else 0.08) + r * k * 0.015], cut, 0.011)
    carve_line(g, [cs + face * 0.075 - up * 0.19 - r * 0.2, cs + face * 0.075 - up * 0.19 + r * 0.2], cut, 0.009)
    for k in range(3):   # a tally of notches under the line
        carve_line(g, [cs + face * 0.075 - up * 0.23 + r * (k * 0.05 - 0.05), cs + face * 0.075 - up * 0.27 + r * (k * 0.05 - 0.05)],
                   cut, 0.008)
    sand_wedge(g, rng, (-0.6, -1.25), (0.6, -1.25), 0.8, 0.35, 1)
    chips(g, rng, 14, 0.0, -1.6, 1.0, sun_rock(nz=nz, varnish=0.4), rmin=0.04, rmax=0.1)
    # The stake line along +Z: squared stakes notched with their count, rag tags, leaning further out.
    rag = (0.7, 0.36, 0.3)
    leans = [(0.0, 0.02), (0.05, -0.04), (-0.12, 0.08)]
    for k, z in enumerate((-0.55, 0.55, 1.65)):
        stake(g, rng, V(0.0, 0.0, z), 1.25 - 0.1 * k, lean=leans[k], rag=rag if k != 1 else None)
        for m in range(k + 1):
            carve_line(g, [V(-0.036, 0.75 + m * 0.06, z - 0.01), V(-0.036, 0.75 + m * 0.06, z + 0.03)], (0.25, 0.2, 0.15),
                       0.006, M_PLANK)
        sand_wedge(g, rng, (-0.25, z + 0.05), (0.25, z + 0.05), 0.45, 0.16, 1)
    beam(g, [V(0.15, 0.05, 2.35), V(-0.1, 0.03, 3.0)], 0.07, 0.07, mat=M_PLANK, col=BLEACHED, rng=rng, chamfer=0.25)
    sand_wedge(g, rng, (-0.3, 2.5), (0.3, 2.8), 0.5, 0.18, 1)
    for k in range(3):   # a three-stone marker further on
        stone(g, (0.5 + k * 0.12, 0.06, 2.4 + (k % 2) * 0.1), (0.09, 0.07, 0.08), rng, mat=M_SAND, detail=1, cuts=2,
              col_fn=sun_rock(nz=nz, varnish=0.5), tile=0.4)
    tube(g, [V(0.0, 1.2, -0.55), V(0.02, 0.85, 0.0), V(0.05, 1.1, 0.55)], [0.006] * 3, 3, M_CLOTH, W.ROPE, tile=0.2, cap=False)
    tube(g, [V(0.05, 1.1, 0.55), V(0.2, 0.5, 0.8), V(0.35, 0.02, 0.95)], [0.006] * 3, 3, M_CLOTH, W.ROPE, tile=0.2, cap=False)
    # The surveyor's chain, dropped in loops: iron links with a brass tally tag every few.
    pts = [V(0.45 + 0.35 * math.sin(t * 0.9), 0.012, -0.4 + t * 0.16) for t in np.linspace(0, 9, 40)]
    for k in range(len(pts) - 1):
        m = (pts[k] + pts[k + 1]) / 2
        d = (pts[k + 1] - pts[k]).normalized()
        sd = d.cross(V(0, 1, 0)) if k % 2 else V(0, 1, 0)
        ring = [m + d * 0.03 * math.cos(t) + sd * 0.012 * math.sin(t) for t in np.linspace(0, 6.28, 7)]
        tube(g, ring, [0.004] * 7, 3, M_IRON, (0.3, 0.2, 0.14), tile=0.1, cap=False)
        if k % 8 == 4:
            disc(g, m + V(0, 0.01, 0), quat_x(0.0), 0.022, 0.006, 8, M_BRONZE, BRASS)
    # The measuring rod (banded paint all but gone) and a bronze plumb bob on its cord.
    a, bb = V(-0.9, 0.05, -1.0), V(-0.75, 0.04, 0.8)
    for k in range(6):
        p0, p1 = a.lerp(bb, k / 6), a.lerp(bb, (k + 1) / 6)
        beam(g, [p0, p1], 0.05, 0.03, mat=M_PLANK, col=(0.8, 0.5, 0.42) if k % 2 else BLEACHED, rng=rng, chamfer=0.2,
             cap=(k == 0, k == 5))
    v_, t_ = lathe([(0.0, 0.0), (0.035, 0.05), (0.03, 0.08), (0.0, 0.09)], 10, V(0.7, 0.03, -0.6), quat_z(1.4))
    smooth_mesh(g, v_, t_, M_BRONZE, lambda p, n: mix(BRASS, VERDIGRIS, 0.5), 0.3, inside=V(0.66, 0.03, -0.6))
    tube(g, [V(0.62, 0.03, -0.6), V(0.4, 0.02, -0.4), V(0.3, 0.02, -0.1)], [0.004] * 3, 3, M_CLOTH, W.ROPE, tile=0.2, cap=False)
    chips(g, rng, 12, 0.0, 0.8, 2.0, sun_rock(nz=nz, varnish=0.3), rmin=0.03, rmax=0.07)
    return b


def site_drowned_outpost(rng):
    """Footprint r <= 3.5. Masses: the dune (2.0, 0.4) 1.7 x 1.4, the arcade wall along z = -0.3
    (x -2.7..1.6), the side wall stub x = -2.55, the cistern (-1.6, -1.8) r 0.95."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 1.4)
    arches = [-1.55, 0.25, 2.05]
    hs, spring, ring = 0.55, 1.25, 0.3

    def opening(t, y):
        x = -2.7 + t
        for cx in arches:
            if abs(x - cx) < hs + 0.02 and y < spring:
                return True
            r = math.hypot(x - cx, y - spring)
            if y >= spring and r < hs + ring + 0.03:
                return True
        return False

    def top(t):
        x = -2.7 + t
        base = 2.35 + 0.18 * nz(V(x * 0.9, 0, 0))
        if -2.75 < x < -2.0:
            base = 2.42                                        # under the bell-arch, intact
        base -= 1.25 * smoothstep(0.35, 0.05, abs(x - 0.95))     # the collapsed bay
        base -= 0.6 * smoothstep(-0.2, 0.3, x - 0.0) * smoothstep(0.6, 0.1, abs(x - 0.25))
        return base
    coursed_wall(g, rng, (-2.7, -0.3), (2.6, -0.3), -0.15, 0.3, 0.48, nz, top, opening, varnish=0.35)
    voussoir_arch(g, rng, V(-1.55, 0, -0.3), hs, spring, 0.48, quat_y(0.0), nz)
    voussoir_arch(g, rng, V(0.25, 0, -0.3), hs, spring, 0.48, quat_y(0.0), nz, missing=(5, 6, 7))
    voussoir_arch(g, rng, V(2.05, 0, -0.3), hs, spring, 0.48, quat_y(0.0), nz)
    # The bell-arch on the end pier: two short piers of blocks, a little arch, an iron bracket — empty.
    bx, by = -2.35, 2.42
    for sg in (-1, 1):
        for k in range(3):
            cut_block(g, rng, V(bx + sg * 0.3, by + 0.13 + k * 0.25, -0.3), (0.2, 0.24, 0.36), quat_y(0.0), nz, varnish=0.4)
    voussoir_arch(g, rng, V(bx, 0, -0.3), 0.2, by + 0.75, 0.36, quat_y(0.0), nz, n=5, ring=0.2)
    hook = V(bx, by + 0.86, -0.3)
    tube(g, [hook + V(-0.1, 0, 0), hook + V(-0.1, -0.1, 0), hook + V(0.1, -0.1, 0), hook + V(0.1, 0, 0)], [0.016] * 4, 5,
         M_IRON, (0.3, 0.2, 0.14), tile=0.2)
    tube(g, [hook + V(0, -0.1, 0), hook + V(0, -0.18, 0), hook + V(0.035, -0.22, 0)], [0.011] * 3, 5, M_IRON, (0.3, 0.2, 0.14), tile=0.2)
    # The side wall that fell: a low ragged stub along Z, its blocks fanned out on the sand.
    coursed_wall(g, rng, (-2.55, -0.05), (-2.55, 1.9), -0.15, 0.3, 0.44, nz,
                 lambda t: 1.1 - 0.75 * smoothstep(0.3, 1.6, t) + 0.15 * nz(V(t, 2, 0)), varnish=0.3)
    fallen_blocks(g, rng, 9, -1.7, 1.25, (0.7, 0.6), nz)
    fallen_blocks(g, rng, 7, 0.95, -1.05, (0.45, 0.5), nz)     # the collapsed bay's blocks, out front
    fallen_blocks(g, rng, 2, 0.25, -0.95, (0.25, 0.2), nz, size=(0.3, 0.32, 0.48))   # its voussoirs
    # A wind-scoured lintel beam, iron-strapped, half buried.
    lb = [V(-2.3, 0.08, 0.9), V(-1.1, 0.13, 1.8)]
    beam(g, lb, 0.2, 0.16, mat=M_PLANK, col=BLEACHED, rng=rng, rough=0.06, jag=(0, 0.2))
    strap(g, lb[0].lerp(lb[1], 0.15) + V(0, 0.08, 0), lb[0].lerp(lb[1], 0.25) + V(0, 0.08, 0), V(0, 1, 0))
    # The dune that drowned it: piled against the east end, spilling through the arches and banked on
    # the windward (+Z) face along the whole arcade.
    # The wind comes from +Z: a rippled windward ramp climbs from behind, its brink sits on the wall and
    # a straight slip face pours over / through the east bay toward the front.
    wind_dune(g, rng, (2.1, -0.05, 0.2), 1.9, 1.75, 1.55, math.pi / 2, crest=0.12)
    sand_wedge(g, rng, (-2.4, -0.05), (1.6, -0.05), 1.3, 0.75, 1)
    for cx in arches[:2]:   # tongues of sand blown through the open arches, slip faces to the front
        wind_dune(g, rng, (cx, -0.04, -0.62), 0.55, 0.5, 0.24, math.pi / 2, nu=14, nv=10, wave=0.3, amp=0.012, crest=-0.25)
    # The cistern: two courses of cut blocks round a sand-choked shaft, a band of turquoise tiles,
    # coping slabs, a broken winch frame with its rope.
    cc = V(-1.6, 0.0, -1.85)
    for k in range(2):
        n = 15
        for i in range(n):
            a = (i + 0.5 * k) / n * 2 * math.pi
            cut_block(g, rng, cc + V(math.cos(a) * 0.82, -0.08 + 0.26 * k + 0.12, math.sin(a) * 0.82),
                      (0.22, 0.24, 2 * math.pi * 0.82 / n - 0.02), quat_y(-a), nz, varnish=0.2, chip=1)
    for i in range(12):
        a = i / 12 * 2 * math.pi
        if i in (4, 9):
            continue   # coping stones gone
        cut_block(g, rng, cc + V(math.cos(a) * 0.84, 0.53, math.sin(a) * 0.84), (0.34, 0.09, 2 * math.pi * 0.84 / 12 - 0.02),
                  quat_y(-a), nz, varnish=0.1, chip=2)
    tile_band(g, rng, cc, 0.945, 26, 0.33, h=0.1, drop=0.25)
    mound(g, (cc.x, 0.18, cc.z), 0.72, 0.72, 0.05, rng, mat=M_SNOW, col_fn=sand_col(nz), tile=1.2, rings=3, seg=14, skirt=0.0,
          power=0.5)
    for sg in (-1, 1):
        beam(g, [cc + V(sg * 1.0, -0.2, 0), cc + V(sg * 1.0, 1.05 if sg < 0 else 0.6, 0)], 0.1, 0.1, mat=M_PLANK, col=BLEACHED,
             rng=rng, jag=(0, 0.0 if sg < 0 else 0.15))
    beam(g, [cc + V(-1.0, 1.0, 0), cc + V(0.9, 0.08, 0.35)], 0.09, 0.09, mat=M_PLANK, col=BLEACHED, rng=rng)
    tube(g, [cc + V(-0.1, 0.56, 0.18), cc + V(0.0, 0.3, 0.1), cc + V(0.05, 0.25, 0.0)], [0.012] * 3, 4, M_CLOTH, W.ROPE,
         tile=0.2, cap=False)
    stone(g, tuple(cc + V(1.2, 0.12, -0.5)), (0.16, 0.12, 0.13), rng, mat=M_HIDE, detail=1, rough=0.1, cuts=1, flat_y=0.7,
          col_fn=lambda p, n: (0.42, 0.3, 0.2), tile=0.3)     # a cracked leather bucket
    for k in range(10):
        a = rng.uniform(0, 6.28)
        lbox(g, cc + V(math.cos(a) * rng.uniform(1.05, 1.6), 0.012, math.sin(a) * rng.uniform(1.05, 1.6)), (0.15, 0.018, 0.12),
             quat_y(a) @ quat_x(rng.uniform(-0.15, 0.15)), M_TILE, scale(TURQ if k % 3 else OCHRE_GLAZE, 0.85), tile=0.25)
    chips(g, rng, 30, 0.0, -0.6, 2.7, sun_rock(nz=nz, varnish=0.3), rmin=0.03, rmax=0.1)
    return b


def site_glyph_wall(rng):
    """Footprint r <= 3.0. Masses: the outcrop along X at z = 0.2, 4.4 x 1.0."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 5, 1.2)
    cream, ochre, rust, pale = (0.98, 0.86, 0.72), (0.95, 0.68, 0.44), (0.74, 0.42, 0.3), (1.0, 0.92, 0.8)
    # ONE outcrop: a single continuous rock surface. For each x a cross-section runs up the front face,
    # over a weathered rounded crown and down the back; it tapers into the ground at both ends. The
    # strata are only shallow relief in that one skin (hard beds stand out a few cm as ledges, weak beds
    # weather back) plus colour banding; vertical joints cut the hard beds.
    x0, x1, htop, back, dip = -2.45, 2.35, 2.6, 0.8, 0.035
    beds = [  # top of bed (bedding coordinate), relief (-: projects toward -Z), colour
        (0.15, 0.0, cream), (0.63, -0.03, ochre),      # the lower panel (figures)
        (0.85, 0.08, rust),                             # a weak bed, weathered back
        (1.57, -0.05, pale),                            # the main panel (the rings)
        (1.83, 0.07, rust), (2.25, -0.2, ochre),        # a hard bed: the overhanging ledge
        (9.0, -0.03, cream)]
    joints = ((-1.98, 0.85, 2.3), (-0.62, -0.3, 0.66), (0.83, 0.85, 1.6), (1.78, -0.3, 0.66), (-0.08, 1.83, 2.3),
              (0.62, -0.3, 0.2))
    xm, half = (x0 + x1) / 2, (x1 - x0) / 2

    def env(x):
        return max(0.0, 1.0 - abs((x - xm) / half) ** 2.6) ** 0.6

    def step(x, a, b_, wa=0.12, wb=0.12):
        return smoothstep(a - wa, a + wa, x) * smoothstep(b_ + wb, b_ - wb, x)

    def height(x):
        """Stepped skyline: each hard bed eroded back further than the one under it, the ends sinking
        into the sand in a long taper."""
        e, f = 0.06 * nz(V(x * 1.3, 0, 5)), 0.14 * nz(V(x * 0.9, 3, 1))
        return (-0.25 + 0.88 * step(x, -2.35 + e, 2.25 + e, 0.3, 0.3) + 0.94 * step(x, -2.0 - e, 1.9 + e, 0.14, 0.1)
                + 0.68 * step(x, -1.6 + f, 1.42 - e, 0.2, 0.12) + (0.35 + f) * step(x, -0.65 - e, 0.75 + f, 0.3, 0.12)
                + 0.04 * nz(V(x * 2.1, 0, 9)))

    def strata(yb):
        """(relief, colour, hardness) at bedding height yb, beds blended over a few cm."""
        off, col, hard = beds[0][1], beds[0][2], 1.0 if beds[0][1] <= 0 else 0.0
        for k in range(1, len(beds)):
            t = smoothstep(beds[k - 1][0] - 0.03, beds[k - 1][0] + 0.03, yb)
            off = off + (beds[k][1] - beds[k - 1][1]) * t
            col = mix(col, beds[k][2], smoothstep(beds[k - 1][0] - 0.015, beds[k - 1][0] + 0.015, yb))
            hard = hard + ((1.0 if beds[k][1] <= 0 else 0.0) - (1.0 if beds[k - 1][1] <= 0 else 0.0)) * t
        return off, col, hard

    def groove(x, yb=None):
        """Vertical joints: each cuts only its own bed(s), offset bed to bed."""
        return max(math.exp(-((x - xj) / 0.022) ** 2) * (1.0 if yb is None else smoothstep(lo - 0.04, lo + 0.04, yb) *
                                                        smoothstep(hi + 0.04, hi - 0.04, yb)) for xj, lo, hi in joints)

    def zf(x, y):
        """Depth of the front face at (x, y)."""
        off, _, hard = strata(y + dip * x)
        z = -0.45 + off + 0.045 * nz(V(x * 0.7, y * 0.35, 3)) + 0.012 * nz(V(x * 3.1, y * 2.7, 7))
        z += (1.0 - env(x)) * 0.45 + 0.05 * (1.0 - smoothstep(-0.1, 0.22, y))   # ends recede; sand-blasted foot
        return z + 0.035 * groove(x, y + dip * x) * hard

    def zb(x, y, yt):
        return back + (yt - y) * 0.3 - (1.0 - env(x)) * 0.3 + 0.04 * nz(V(x * 0.9, y * 0.5, 11))

    xs = sorted(set([round(x, 4) for x in np.linspace(x0, x1, 34)] +
                    [round(j[0] + d, 4) for j in joints for d in (-0.035, 0.0, 0.035)]))
    rows = sorted(set([round(y, 4) for y in np.arange(-0.3, 2.45, 0.1)] +
                      [round(bt + d, 4) for bt, _, _ in beds[:-1] for d in (-0.03, 0.03)]))
    ncap, nback = 7, 5
    verts, cols_n = [], 0
    for x in xs:
        H = height(x)
        rc = min(0.16, max(0.06, (H + 0.3) * 0.2))
        yt = max(-0.3, H - rc)
        H = max(H, yt + 0.02)
        col_pts = []
        for yb in rows:
            y = min(yb - dip * x, yt) if yb > -0.3 else -0.3
            col_pts.append(V(x, y, zf(x, y)))
        zft, zbt = zf(x, yt), zb(x, yt, yt)
        for i in range(1, ncap):
            th = math.pi * i / ncap
            col_pts.append(V(x, yt + (H - yt) * math.sin(th) ** 0.35 + 0.025 * nz(V(x * 2, th, 13)) * math.sin(th),
                             zft + (zbt - zft) * (1 - math.cos(th)) / 2))
        for i in range(nback + 1):
            y = yt + (-0.3 - yt) * i / nback
            col_pts.append(V(x, y, zb(x, y, yt)))
        verts += col_pts
        cols_n = len(col_pts)
    tris = []
    for i in range(len(xs) - 1):
        for k in range(cols_n - 1):
            a_, b_, c_, d_ = i * cols_n + k, (i + 1) * cols_n + k, (i + 1) * cols_n + k + 1, i * cols_n + k + 1
            tris += [(a_, d_, c_), (a_, c_, b_)]

    def rock(p, n):
        yb = p.y + dip * p.x
        _, c, hard = strata(yb)
        c = scale(c, (0.92 + 0.08 * nz(p * 3.0)) * (0.95 + 0.05 * math.sin(yb * 58 + 3 * nz(p * 0.8))))   # laminae
        vert = 1.0 - smoothstep(0.25, 0.7, abs(n.y))
        streak = smoothstep(0.35, 0.9, 0.5 + 0.5 * math.sin(p.x * 9.7 + 2.6 * nz(V(p.x * 0.8, 0, 1))) * (0.6 + 0.4 * nz(V(p.x * 2.3, p.y * 0.4, 2))))
        panel = 0.35 * (smoothstep(0.17, 0.25, yb) * smoothstep(0.62, 0.55, yb) + smoothstep(0.87, 0.95, yb) * smoothstep(1.56, 1.48, yb))
        c = mix(c, VARNISH, min(0.9, vert * (0.8 * streak * smoothstep(0.1, 1.0, p.y) + panel)) * (n.z < 0.3))
        c = mix(c, scale(VARNISH, 0.8), 0.6 * groove(p.x, yb) * vert)                       # the joints
        c = mix(c, (1.0, 0.94, 0.82), 0.35 * smoothstep(0.55, 0.9, n.y))                   # bleached crown
        ledge = smoothstep(0.55, 0.85, n.y) * (1.0 - smoothstep(1.9, 2.3, p.y))            # sand on the ledges
        c = mix(c, scale(SAND, 0.95), 0.6 * ledge)
        return mix(c, SAND, 0.4 * (1.0 - smoothstep(0.0, 0.35, p.y)))
    smooth_mesh(g, verts, tris, M_SAND, rock, 1.1)

    def proj(p):
        return V(p.x, p.y, zf(p.x, p.y) - 0.006)
    # Petroglyphs pecked pale through the varnish: a great ring spreading on the main panel, tusked
    # figures on the lower panel with their arms raised toward it, a spiral, a count of dots.
    face, up = V(0, 0, -1), V(0, 1, 0)
    peck = (1.0, 0.9, 0.74)
    rc_ = V(0.3, 1.21, -0.525)
    for rr in (0.06, 0.13, 0.2, 0.27, 0.33):
        ring_on(g, rc_, face, up, rr, scale(peck, 1.0 - rr * 0.3), r=0.018, n=25, mat=M_SAND, proj=proj)
    for k, x in enumerate((-1.75, -1.3, -0.85, -0.4)):
        tusk_figure(g, V(x, 0.22 + 0.02 * k, -0.475), face, up, 0.85, peck, mat=M_SAND, arms_up=True, proj=proj)
    for k, x in enumerate((1.05, 1.45)):
        tusk_figure(g, V(x, 0.2, -0.475), face, up, 0.8, peck, mat=M_SAND, arms_up=k == 0, proj=proj)
    sp = V(-1.25, 1.2, -0.525)
    carve_line(g, [sp + V(math.cos(t) * 0.022 * t, math.sin(t) * 0.022 * t, 0) for t in np.linspace(0.3, 12.5, 32)], peck, 0.016,
               M_SAND, proj)
    for k in range(9):
        x = -0.3 + k * 0.1
        stone(g, tuple(proj(V(x, 0.55, 0))), (0.018, 0.018, 0.008), rng, mat=M_SAND, detail=1, rough=0, cuts=0,
              col_fn=lambda p, n: peck, tile=0.2)
    # Beds that broke off the face and fell, scree, a drift banked at the foot and a dune behind.
    for k, (x, z, a) in enumerate(((-1.6, -1.0, 0.3), (0.9, -1.15, -0.4), (1.9, -0.7, 0.9))):
        slab(g, (x, 0.1, z), (rng.uniform(0.7, 1.0), 0.3, rng.uniform(0.5, 0.7)), quat_y(a) @ quat_x(rng.uniform(-0.25, 0.25)),
             rng, mat=M_SAND, res=(4, 2, 3), round_r=0.04, rough=0.03, cuts=3,
             col_fn=sun_rock(base=[cream, ochre, rust][k], nz=nz, varnish=0.4), tile=1.0)
    chips(g, rng, 34, 0.0, -0.9, 2.4, sun_rock(base=ochre, nz=nz, varnish=0.3), rmin=0.04, rmax=0.15)
    sand_wedge(g, rng, (-2.3, -0.4), (2.2, -0.4), 0.8, 0.28, -1)
    wind_dune(g, rng, (0.0, -0.06, 1.75), 1.15, 2.5, 1.0, math.pi / 2, nu=30, nv=16, crest=0.55)   # ramped up the back
    # An ork offering at the foot: two tusks on a flat stone.
    slab(g, (0.25, 0.05, -1.0), (0.55, 0.1, 0.4), quat_y(0.2), rng, mat=M_SAND, res=(3, 1, 2), round_r=0.02, cuts=1,
         col_fn=sun_rock(nz=nz, varnish=0.2), tile=0.7)
    for sg in (-1, 1):
        p = V(0.25 + sg * 0.12, 0.13, -1.0)
        tube(g, [p, p + V(sg * 0.08, 0.02, -0.12), p + V(sg * 0.06, 0.1, -0.26)], [0.035, 0.025, 0.005], 6, M_PLASTER,
             (0.9, 0.84, 0.68), tile=0.2)
    return b


def site_looted_caravan(rng):
    """Footprint r <= 3.0. Masses: the cart (0, 0) 1.2 x 0.7, the burned bale (1.5, 0.9)."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 1.5)
    rot = quat_y(0.15) @ quat_x(-0.22)
    from stories_cold import wagon_bed
    wagon_bed(g, rng, V(0.0, 0.55, 0.0), rot, length=2.1, width=1.2, broken_side=True, col=(0.86, 0.66, 0.46))
    for x in (-0.9, 0.0, 0.9):   # iron straps on the bed's side boards
        strap(g, V(x, 0.5, -0.66), V(x, 0.92, -0.62), V(0, 0, -1))
    wheel(g, V(0.0, 0.62, -0.68), quat_x(math.pi / 2), 0.62, rng, spokes=10, col=(0.8, 0.62, 0.42))
    wheel(g, V(0.9, 0.06, 0.95), quat_y(0.6) @ quat_z(0.06), 0.62, rng, spokes=10, broken=3, col=(0.8, 0.62, 0.42))
    for sg in (-1, 1):
        beam(g, [V(-1.05, 0.7, sg * 0.35), V(-2.3, 1.55, sg * 0.4)], 0.08, 0.08, mat=M_PLANK, col=(0.8, 0.62, 0.44), rng=rng)
    beam(g, [V(-2.2, 1.48, -0.42), V(-2.2, 1.5, 0.42)], 0.06, 0.06, mat=M_PLANK, col=(0.8, 0.62, 0.44), rng=rng)
    # Slashed bolts of dyed cloth strewn downwind, still bright: madder red, indigo, saffron.
    for col, c, a, ln in (((0.75, 0.12, 0.1), V(-0.6, 0.0, -1.6), 0.4, 1.8), ((0.16, 0.2, 0.55), V(1.1, 0.0, -1.4), -0.5, 1.5),
                          ((0.95, 0.68, 0.12), V(0.4, 0.0, 1.9), 1.2, 1.3)):
        cloth_drape(g, rng, c, quat_y(a), 0.55, ln, col, sag=0.04, folds=2, slashed=True, nx=6, nz=7)
        tube(g, [c + quat_y(a) @ V(-0.25, 0.09, -ln / 2 - 0.06), c + quat_y(a) @ V(0.25, 0.09, -ln / 2 - 0.06)],
             [0.09, 0.09], 12, M_CLOTH, scale(col, 0.8), tile=0.3)
    # A carpet half unrolled out of the cart (woven bands), roped bales tumbled off.
    c0 = V(-1.6, 0.0, 0.5)
    tube(g, [c0 + V(0, 0.11, -0.6), c0 + V(0, 0.11, 0.6)], [0.11, 0.11], 12, M_CLOTH, (0.5, 0.14, 0.1), tile=0.3)
    grid = [[c0 + V(-0.1 - 1.2 * j / 5, 0.02 + 0.03 * math.sin(j * 1.7), -0.6 + 1.2 * i / 5) for j in range(6)] for i in range(6)]
    sheet(g, grid, M_CLOTH, lambda u, v: (0.55, 0.12, 0.1) if int(u * 9) % 3 else (0.85, 0.65, 0.3), tile=0.4, double=True)
    for k, (p, a) in enumerate(((V(0.8, 0.2, -0.9), 0.3), (V(-0.7, 0.2, -0.95), -0.6))):
        slab(g, tuple(p), (0.6, 0.38, 0.42), quat_y(a), rng, mat=M_CLOTH, res=(3, 2, 2), round_r=0.12, rough=0.05,
             col_fn=lambda q, n, kk=k: [(0.78, 0.7, 0.55), (0.55, 0.42, 0.3)][kk], tile=0.4)
        for o in (-0.15, 0.15):
            ring = [p + quat_y(a) @ V(o, 0.2 * math.cos(t), 0.22 * math.sin(t)) for t in np.linspace(0, 6.28, 11)]
            tube(g, ring, [0.012] * 11, 4, M_CLOTH, W.ROPE, tile=0.2, cap=False)
    # Smashed crates: boards prised off, nails and all; spilled grain.
    for k in range(6):
        p = V(rng.uniform(-1.4, 0.2), 0.03, rng.uniform(1.0, 1.9))
        a = rng.uniform(0, 3.1)
        board(g, p, V(math.cos(a), 0, math.sin(a)), V(0, 1, 0.1), rng.uniform(0.4, 0.7), 0.14, 0.025, mat=M_PLANK,
              col=(0.8, 0.66, 0.5), rng=rng, jag=(0, 0.05))
    from stories_cold import crate
    crate(g, V(-0.7, 0.2, 1.3), (0.5, 0.4, 0.42), quat_y(0.4) @ quat_z(0.35), rng, col=(0.82, 0.66, 0.5))
    mound(g, (-0.4, -0.02, 1.55), 0.45, 0.3, 0.07, rng, mat=M_EARTH, col_fn=lambda p, n: (0.95, 0.85, 0.6), tile=0.3)
    sack(g, V(-0.9, 0.12, -1.3), quat_y(0.6) @ quat_z(1.2), 1.1, rng, col=(0.78, 0.7, 0.55))
    # Smashed jars, a brass tray, a burned bale on its ash.
    jar(g, rng, V(0.6, 0.0, -0.5), quat_x(1.45) @ quat_z(0.3), h=0.6, broken=0.35)
    jar(g, rng, V(-0.4, -0.05, 1.2), quat_z(0.0), h=0.55, broken=0.55)
    jar(g, rng, V(1.55, -0.04, -0.3), quat_x(0.1), h=0.45, r=0.18, col=(0.9, 0.82, 0.68), glaze=TURQ)
    shards(g, rng, 24, 0.2, 0.0, 1.8, TERRACOTTA)
    disc(g, V(-1.0, 0.06, -0.8), quat_x(0.25), 0.3, 0.02, 20, M_BRONZE, BRASS)
    mound(g, (1.55, -0.02, 0.95), 0.7, 0.6, 0.08, rng, mat=M_EARTH, col_fn=lambda p, n: (0.16, 0.14, 0.13), tile=0.8)
    stone(g, (1.55, 0.18, 0.95), (0.42, 0.25, 0.32), rng, mat=M_CLOTH, detail=2, rough=0.15, cuts=2,
          col_fn=lambda p, n: mix((0.12, 0.1, 0.09), (0.6, 0.3, 0.2), smoothstep(0.1, 0.35, p.y) * 0.4), tile=0.4)
    charcoal_heap(g, rng, 1.55, 0.95, 0.5, 18)
    # Ork arrows in the boards and the sand: black shafts, black fletching. Drag marks in the sand.
    for k in range(9):
        foot = V(rng.uniform(-1.6, 1.8), 0.0, rng.uniform(-1.8, 1.6)) if k > 2 else V(-0.3 + k * 0.45, 0.85, 0.25)
        d = V(rng.uniform(-0.4, 0.4), 1.0, rng.uniform(-0.4, 0.4)).normalized()
        tail = foot + d * 0.7
        tube(g, [foot - d * 0.1, tail], [0.008, 0.008], 4, M_PLANK, (0.2, 0.17, 0.15), tile=0.2)
        for f in range(3):
            a = f / 3 * 2 * math.pi
            off = V(math.cos(a), 0, math.sin(a)) * 0.035
            g.flat([tail - d * 0.16, tail - d * 0.02, tail - d * 0.04 + off, tail - d * 0.16 + off * 0.6], M_HIDE,
                   (0.08, 0.07, 0.07), 0.2)
    sand_wedge(g, rng, (-1.1, 0.75), (1.1, 0.75), 0.8, 0.22, 1)
    chips(g, rng, 14, 0.0, 0.0, 2.6, sun_rock(nz=nz, varnish=0.3), rmin=0.03, rmax=0.08)
    return b


def mule_skeleton(g, rng, c, yaw):
    """A pack mule's bones lying on their side: skull, a vertebral chain, ribs fallen flat on one side,
    the pelvis, scattered long bones and hooves; half drifted over."""
    rot = quat_y(yaw)
    c = Vector(c)
    P = lambda x, y, z: c + rot @ V(x, y, z)  # noqa: E731
    spine = [P(-0.75 + 0.1 * k, 0.07 + 0.02 * math.sin(k * 0.6), 0.03 * math.sin(k * 0.9)) for k in range(16)]
    for k, p in enumerate(spine):
        stone(g, tuple(p), (0.045, 0.04, 0.04), rng, mat=M_PLASTER, detail=1, rough=0.1, cuts=1, col_fn=lambda q, n: BONE, tile=0.3)
        if 3 <= k <= 10:   # spinous processes
            tube(g, [p, p + rot @ V(-0.02, 0.09, 0.0)], [0.012, 0.006], 4, M_PLASTER, BONE, tile=0.2)
    tube(g, spine, [0.016] * len(spine), 5, M_PLASTER, scale(BONE, 0.9), tile=0.3)
    for k in range(4, 12):   # ribs fallen flat toward +z, a few broken
        if k in (7, 10):
            continue
        base = spine[k]
        pts = [base + rot @ V(0.03 * u, -0.05 * u, 0.42 * math.sin(u * 1.4) * (1 - 0.05 * k)) for u in np.linspace(0, 1, 6)]
        tube(g, pts, [0.016, 0.015, 0.013, 0.012, 0.011, 0.009], 5, M_PLASTER, scale(BONE, rng.uniform(0.9, 1.0)), tile=0.3,
             cap=False)
    skull(g, rng, P(-1.05, 0.08, 0.1), rot @ quat_y(0.4) @ quat_x(1.35), 1.05)
    for sg in (-1, 1):   # pelvis wings
        stone(g, tuple(P(0.82, 0.06, sg * 0.12)), (0.14, 0.04, 0.1), rng, mat=M_PLASTER, detail=1, rough=0.08, cuts=1,
              col_fn=lambda q, n: BONE, tile=0.3)
    for a, bb in (((0.85, 0.03, 0.2), (1.35, 0.03, 0.45)), ((1.35, 0.03, 0.45), (1.75, 0.03, 0.4)), ((0.8, 0.03, -0.2), (1.2, 0.02, -0.55)),
                  ((-0.45, 0.03, 0.25), (-0.4, 0.03, 0.75)), ((-0.4, 0.03, 0.75), (-0.55, 0.02, 1.1)), ((-0.5, 0.03, -0.3), (-0.2, 0.02, -0.7))):
        bone(g, P(*a), P(*bb), 0.022, rng)
    for p in ((1.78, 0.03, 0.42), (-0.57, 0.03, 1.13)):
        stone(g, tuple(P(*p)), (0.05, 0.035, 0.045), rng, mat=M_HIDE, detail=1, cuts=1, col_fn=lambda q, n: (0.2, 0.17, 0.14), tile=0.2)


def sawbuck_saddle(g, rng, c, rot):
    """A wooden pack saddle: two X-crosses of planks joined by side bars, leather girth straps."""
    c = Vector(c)
    for z in (-0.22, 0.22):
        for sg in (-1, 1):
            a, bb = c + rot @ V(-0.28 * sg, 0.0, z), c + rot @ V(0.2 * sg, 0.42, z)
            beam(g, [a, bb], 0.07, 0.03, up=tuple(rot @ V(0, 0, 1)), mat=M_PLANK, col=BLEACHED, rng=rng, chamfer=0.2)
    for sg in (-1, 1):
        board(g, c + rot @ V(sg * 0.2, 0.14, 0.0), rot @ V(0, 0, 1), rot @ V(sg, 0.6, 0), 0.62, 0.16, 0.03, mat=M_PLANK,
              col=BLEACHED, rng=rng)
        nail(g, c + rot @ V(sg * 0.22, 0.16, 0.2), rot @ V(sg, 0.6, 0), 0.01)
    for k in range(2):
        a = c + rot @ V(0.25, 0.1, -0.1 + 0.2 * k)
        g.flat([a, a + rot @ V(0.03, 0, 0.05), a + rot @ V(0.45, -0.12, 0.08), a + rot @ V(0.42, -0.12, 0.02)], M_HIDE,
               (0.36, 0.24, 0.15), 0.3)
        g.flat([a + rot @ V(0.42, -0.12, 0.02), a + rot @ V(0.45, -0.12, 0.08), a + rot @ V(0.03, 0, 0.05), a], M_HIDE,
               (0.36, 0.24, 0.15), 0.3)


def site_anselm_desert(rng):
    """Footprint r <= 2.5. Masses: the outcrop (0, 1.15) 3.4 x 1.4 (the overhang shelter in its face)."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 5, 1.3)
    cream, ochre, rust = (0.98, 0.86, 0.72), (0.95, 0.72, 0.5), (0.82, 0.52, 0.38)
    back = 1.9
    layers = [
        (-0.35, 0.45, 0.45, -1.6, 1.5, ochre, 0.03),
        (0.1, 0.5, 0.65, -1.5, 1.4, rust, 0.05),        # the soft bed the wind scooped into a shelter
        (0.6, 0.42, 0.3, -1.6, 1.6, cream, 0.03),
        (1.02, 0.45, -0.75, -1.8, 1.7, ochre, 0.02),     # the hard roof bed, cantilevered out
        (1.47, 0.36, -0.45, -1.5, 1.3, cream, 0.03),
        (1.83, 0.3, 0.1, -1.0, 0.9, rust, 0.04),
    ]
    strata_outcrop(g, rng, layers, back, nz)
    sand_drift(g, (0.0, -0.06, 0.3), 1.3, 0.55, 0.22, rng, power=0.7)       # sand blown into the shelter
    sand_drift(g, (0.2, -0.08, 2.4), 2.0, 0.9, 0.9, rng, power=0.8)        # the windward dune behind
    chips(g, rng, 24, 0.0, -0.3, 2.1, sun_rock(base=ochre, nz=nz, varnish=0.3), rmin=0.03, rmax=0.13)
    # The mule, dead in the shade's edge, the pack saddle slipped off beside it.
    mule_skeleton(g, rng, V(0.15, 0.0, -0.95), 0.12)
    sand_wedge(g, rng, (-0.8, -0.6), (1.2, -0.55), 0.5, 0.16, 1)
    sawbuck_saddle(g, rng, V(-1.15, 0.05, -0.25), quat_y(0.5) @ quat_z(1.35))
    # In the shelter: the satchel spilled, the page held down by a stone at the mouth, others loose.
    sc = V(-0.35, 0.12, 0.25)
    stone(g, tuple(sc), (0.22, 0.12, 0.16), rng, mat=M_HIDE, detail=2, rough=0.08, cuts=1, flat_y=0.7, rot=quat_y(0.4),
          col_fn=lambda p, n: (0.5, 0.34, 0.22), tile=0.4)
    g.flat([sc + V(0.12, 0.1, -0.12), sc + V(0.3, 0.01, -0.22), sc + V(0.42, 0.01, -0.0), sc + V(0.2, 0.11, 0.08)], M_HIDE,
           (0.45, 0.3, 0.2), 0.4)
    g.flat([sc + V(0.2, 0.11, 0.08), sc + V(0.42, 0.01, -0.0), sc + V(0.3, 0.01, -0.22), sc + V(0.12, 0.1, -0.12)], M_HIDE,
           (0.45, 0.3, 0.2), 0.4)
    tube(g, [sc + V(-0.2, 0.05, 0), sc + V(-0.4, 0.0, -0.2), sc + V(-0.3, -0.1, -0.5)], [0.012] * 3, 4, M_HIDE, (0.4, 0.27, 0.17),
         tile=0.2)
    page(g, V(0.15, 0.0, -0.25), quat_y(0.3))
    stone(g, (0.17, 0.06, -0.22), (0.075, 0.05, 0.065), rng, mat=M_SAND, detail=1, rough=0.05, cuts=2, col_fn=sun_rock(nz=nz),
          tile=0.3)
    page(g, V(-0.05, 0.02, 0.05), quat_y(1.1) @ quat_x(0.1), curl=0.02, col=scale(PAPER, 0.9))
    page(g, V(0.45, 0.01, 0.15), quat_y(-0.4), lines=False, col=scale(PAPER, 0.85))
    v_, t_ = lathe([(0.0, 0.0), (0.03, 0.0), (0.035, 0.06), (0.018, 0.08), (0.0, 0.08)], 10, V(0.3, 0.0, 0.35), quat_z(1.5))
    smooth_mesh(g, v_, t_, M_BRONZE, lambda p, n: BRASS, 0.3, inside=V(0.26, 0.03, 0.35))
    tube(g, [V(0.35, 0.01, 0.25), V(0.55, 0.01, 0.15)], [0.004, 0.003], 4, M_PLANK, (0.75, 0.65, 0.45), tile=0.2)
    stone(g, (0.75, 0.08, 0.3), (0.2, 0.08, 0.12), rng, mat=M_HIDE, detail=1, rough=0.2, cuts=1, flat_y=0.5,
          col_fn=lambda p, n: (0.35, 0.24, 0.16), tile=0.3)      # a dried-out waterskin
    return b



# ─────────────────────────────────────────────────────────────── FOREST
DUG = (0.36, 0.31, 0.26)              # thrown-out spoil over the (warm) s_earth scan: forest brown, not terracotta
DUG_CLAY = (0.5, 0.44, 0.36)          # paler subsoil clods
LITTER = (0.36, 0.29, 0.2)           # forest-floor leaf litter
DAMP_FOOT = (0.22, 0.16, 0.11)


def bank_col(nzn, cx, cz, hx, hz, h=0.5):
    """Spoil-bank tint: bare dug earth on the cut faces and slopes (paler subsoil clods in it, dark and
    damp toward every foot), leaf litter on the old crest with moss in patches only."""
    def f(p, n):
        d = rect_dist(p.x, p.z, cx, cz, hx, hz)
        if d < -0.03:
            return scale((0.13, 0.105, 0.085), 0.85 + 0.25 * nzn(p * 4))
        c = mix(DUG, scale(DUG, 0.78), 0.5 + 0.5 * nzn(p * 2.6))
        c = mix(c, DUG_CLAY, 0.55 * smoothstep(0.25, 0.75, nzn(Vector((p.z, p.x, 1.0)) * 4.5)))
        flat = smoothstep(0.5, 0.85, n.y)
        old = flat * smoothstep(0.3 * h, 0.7 * h, p.y) * smoothstep(-0.55, 0.05, nzn(p * 1.3))
        c = mix(c, scale(LITTER, 0.9 + 0.15 * nzn(p * 5)), 0.85 * old)
        moss = old * smoothstep(0.3, 0.65, nzn(Vector((p.x, 4.0, p.z)) * 1.9))
        c = mix(c, scale(MOSS, 0.8 + 0.2 * nzn(p * 6)), 0.8 * moss)
        toe = (1.0 - smoothstep(0.0, 0.3 * h, p.y)) * smoothstep(0.3, 0.6, d)   # the outer toe: litter creeping up
        c = mix(c, scale(LITTER, 0.9 + 0.15 * nzn(p * 4)), 0.8 * toe)
        damp = 1.0 - smoothstep(-0.05, 0.28 * h, p.y)
        inner = 1.0 - smoothstep(0.02, 0.12, d)
        return mix(c, DAMP_FOOT, max(0.65 * damp, 0.45 * inner * (1.0 - smoothstep(0.0, h, p.y))))
    return f


def bank_roots(g, rng, root_pt, n):
    """Roots torn through by the spade: tapering tubes sticking out of a cut face, drooping."""
    for _ in range(n):
        p0, out = root_pt()
        out = (out + V(rng.uniform(-0.3, 0.3), 0, rng.uniform(-0.3, 0.3))).normalized()
        L = rng.uniform(0.18, 0.45)
        r0 = rng.uniform(0.012, 0.03)
        pts = [p0 - out * 0.1, p0 + out * 0.05 + V(0, 0.01, 0), p0 + out * (0.05 + L * 0.5) - V(0, L * 0.25, 0),
               p0 + out * (0.05 + L * 0.8) - V(0, L * 0.7, 0)]
        tube(g, pts, [r0, r0 * 0.8, r0 * 0.45, 0.003], 5, M_BARK, (0.42, 0.33, 0.24), tile=0.2,
             col_fn=lambda t: mix((0.36, 0.27, 0.19), (0.62, 0.52, 0.4), t))


def shored_pit(g, rng, cx, cz, hx, hz, h, plateau, slope, posts_x=2, missing=None, fallen=True, step=0.1, clods=12,
               roots=8, stones=8):
    """A dug pit read at eye level: a heaped spoil bank round a rectangular hole with a dark floor, the inner
    walls shored with nailed planks between corner / middle posts; turf sods cut off the top thrown on the
    spoil (some tipped over), raw clods, stones turned up, roots sticking out of the cut. Returns the bank's
    height function so props can sit on it."""
    nzn = Noise(rng, 4, 1.8)
    w = plateau + slope
    ext_x, ext_z = hx + 0.06 + 1.3 * w + 0.1, hz + 0.06 + 1.3 * w + 0.1
    hfn = pit_bank(hx, hz, h, plateau, slope, nzn, cx, cz)
    heightfield(g, cx - ext_x, cx + ext_x, cz - ext_z, cz + ext_z, step, hfn, bank_col(nzn, cx, cz, hx, hz, h), mat=M_EARTH,
                tile=0.9, cull=-0.1)

    def bank_pt(dmin, dmax):
        """A random point on the bank: (position on the surface, outward horizontal direction)."""
        side = int(rng.integers(0, 4))
        t = rng.uniform(-1.0, 1.0)
        d = rng.uniform(dmin, dmax)
        if side < 2:
            sg = -1 if side == 0 else 1
            x, z, out = cx + t * hx, cz + sg * (hz + d), V(0, 0, sg)
        else:
            sg = -1 if side == 2 else 1
            x, z, out = cx + sg * (hx + d), cz + t * hz, V(sg, 0, 0)
        return V(x, hfn(x, z), z), out

    # Turf cut off the top before digging, thrown up on the spoil: most grass-up, some tipped over.
    for k in range(clods):
        p, out = bank_pt(0.1, plateau + 0.3 * slope)
        if k % 3 == 2:
            nrm = (out * rng.uniform(0.6, 1.2) + V(0, rng.uniform(-0.9, -0.2), 0)).normalized()   # tipped
        else:
            nrm = V(rng.uniform(-0.3, 0.3), 1.0, rng.uniform(-0.3, 0.3)).normalized()
        turf_sod(g, rng, p - V(0, 0.05, 0), nrm, rng.uniform(0.55, 0.85))
    # Raw clods of spoil and paler subsoil, heaped on the crest and rolled down the slope.
    for k in range(clods + 2):
        p, out = bank_pt(0.08, w * 0.9)
        r = rng.uniform(0.05, 0.13)
        c = DUG_CLAY if k % 4 == 0 else scale(DUG, rng.uniform(0.75, 1.0))
        stone(g, tuple(p - V(0, r * 0.35, 0)), (r, r * rng.uniform(0.55, 0.8), r * rng.uniform(0.7, 1.0)), rng, mat=M_EARTH,
              detail=1 if r > 0.1 else 0, rough=0.22, cuts=1, col_fn=lambda q, nn, c=c: mix(scale(c, 0.7), c, smoothstep(-0.3, 0.8, nn.y)),
              tile=0.5)
    # Stones the spade turned up, half buried in the spoil.
    for k in range(stones):
        p, out = bank_pt(0.05, w)
        r = rng.uniform(0.06, 0.16)
        stone(g, tuple(p - V(0, r * 0.4, 0)), (r, r * rng.uniform(0.5, 0.75), r * rng.uniform(0.7, 1.0)), rng, mat=M_ROCK,
              detail=1 if r > 0.12 else 0, rough=0.12, cuts=2,
              col_fn=rock_col((0.62, 0.6, 0.55), moss=0.25 if k % 2 else 0.0, ground=p.y - r * 0.4), tile=0.5)

    # Roots sticking out of the cut over the shoring, and out of the outer slope where it was trimmed.
    def lip_root():
        p, out = bank_pt(0.02, 0.08)
        p.y -= rng.uniform(0.03, 0.14)
        return p, -out
    bank_roots(g, rng, lip_root, roots)

    def slope_root():
        p, out = bank_pt(plateau * 0.6, plateau + slope * 0.5)
        return p - V(0, 0.05, 0), out
    bank_roots(g, rng, slope_root, 2)
    nw = int(h / 0.17 + 0.5)
    walls = [((cx - hx, cz - hz), (cx + hx, cz - hz), (0, 0, 1)), ((cx + hx, cz + hz), (cx - hx, cz + hz), (0, 0, -1)),
             ((cx - hx, cz + hz), (cx - hx, cz - hz), (1, 0, 0)), ((cx + hx, cz - hz), (cx + hx, cz + hz), (-1, 0, 0))]
    for k, (a, b_, nrm) in enumerate(walls):
        A = V(a[0], 0, a[1]) + V(*nrm) * 0.03
        B = V(b_[0], 0, b_[1]) + V(*nrm) * 0.03
        plank_wall(g, rng, A, B, -0.02, nw, 0.17, 0.035, nrm, missing=(missing or {}).get(k, ()))
        n_posts = posts_x if k < 2 else 1
        for i in range(n_posts + 1):
            p = A.lerp(B, i / n_posts) + V(*nrm) * 0.06
            beam(g, [p - V(0, 0.15, 0), p + V(0, h + 0.12, 0)], 0.1, 0.1, mat=M_MOSSWOOD, col=ROT_WOOD, rng=rng, jag=(0, 0.04))
        for mk in (missing or {}).get(k, ()):   # roots hanging out of the bare cut behind a lost plank
            for q in (0.3, 0.65):
                c = A.lerp(B, q) - V(*nrm) * 0.05 + V(0, 0.17 * (mk + 0.5), 0)
                bank_roots(g, rng, lambda c=c, nrm=nrm: (c.copy(), V(*nrm)), 1)
    if fallen:   # a plank sprung off the wall, leaning into the pit
        board(g, V(cx - hx * 0.4, 0.22, cz - hz + 0.25), V(1, 0, 0.1), V(0.1, 0.6, -1).normalized(), 1.1, 0.16, 0.035,
              mat=M_MOSSWOOD, col=ROT_WOOD, rng=rng)
    return hfn


def site_bell_pit(rng):
    """Footprint r <= 3.2. Masses: the spoil bank ring is walkable; the furnace (-1.55, 1.25) r 0.55, the
    core (0.45, -0.35) r 0.45."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 1.6)
    cx, cz, hx, hz = 0.25, -0.15, 1.05, 0.85
    hb = shored_pit(g, rng, cx, cz, hx, hz, 0.55, 0.45, 0.85, missing={3: (2,)}, clods=12, roots=9, stones=9)
    # In the pit: the clay core the mould was built over, cracked; the cope broken off it in shells
    # (one band of mirrored letters); the iron bands that held the cope; the bronze spill and slag.
    core = V(0.45, -0.03, -0.35)
    v_, t_ = lathe([(0.0, 0.0), (0.46, 0.0), (0.44, 0.18), (0.35, 0.48), (0.31, 0.7), (0.18, 0.82), (0.0, 0.84)], 18, core, quat_z(0.1))
    smooth_mesh(g, v_, t_, M_CLAY, lambda p, n: mix(RAW_CLAY, (0.22, 0.18, 0.15), 0.45 * smoothstep(0.25, 0.8, p.y) +
                                                   0.15 * nz(p * 6)), 0.35, inside=core + V(0, 0.3, 0))
    for a0 in (0.4, 2.2, 4.1):   # cracks down the core
        pts = [core + V(math.cos(a0 + 0.1 * k) * (0.47 - 0.05 * k), 0.05 + 0.13 * k, math.sin(a0 + 0.1 * k) * (0.47 - 0.05 * k))
               for k in range(6)]
        tube(g, pts, [0.007] * 6, 3, M_CLAY, (0.06, 0.05, 0.05), tile=0.2, cap=False)
    mould_shard(g, rng, V(-0.25, -0.05, -0.55), quat_y(0.6) @ quat_x(0.2), 0.6, 1.1, 0.2, 2.0, 0.05, 0.75, letters=True)
    mould_shard(g, rng, V(0.95, 0.05, 0.25), quat_x(-1.4) @ quat_y(1.5), 0.6, 1.1, 2.4, 3.6, 0.2, 0.7)
    mould_shard(g, rng, V(-0.3, 0.0, 0.35), quat_z(1.3) @ quat_y(0.2), 0.6, 1.1, 4.0, 4.9, 0.1, 0.5)
    mould_shard(g, rng, V(1.0, 0.0, -0.7), quat_z(-1.4) @ quat_y(2.2), 0.6, 1.1, 5.2, 6.0, 0.45, 0.9)
    shards(g, rng, 22, cx, cz, 0.8, FIRED, size=(0.05, 0.13))
    for k, (c, a) in enumerate(((V(-0.55, 0.03, -0.1), 0.3), (V(0.9, 0.03, -0.25), 1.4))):
        pts = [c + quat_y(a) @ V(0.5 * math.cos(t), 0.0, 0.5 * math.sin(t)) for t in np.linspace(0.2, 3.6 + k, 12)]
        tube(g, pts, [0.016] * 12, 4, M_IRON, (0.3, 0.2, 0.14), tile=0.2)
    sp = []
    for i in range(16):
        a = i / 16 * 2 * math.pi
        rr = 0.42 * (1 + 0.3 * nz(V(math.cos(a), 0, math.sin(a)) * 2))
        sp.append(V(0.05 + math.cos(a) * rr, 0.0, -0.05 + math.sin(a) * rr * 0.7))
    sp.append(V(0.05, 0.03, -0.05))
    smooth_mesh(g, sp, [(16, (i + 1) % 16, i) for i in range(16)], M_BRONZE, bronze_spill(nz), 0.4, inside=V(0.05, -1.0, -0.05))
    for k in range(10):
        stone(g, (rng.uniform(-0.6, 0.9), 0.03, rng.uniform(-0.8, 0.4)), (0.06, 0.04, 0.05), rng, mat=M_ROCK, detail=0, cuts=2,
              col_fn=lambda p, n, kk=rng.uniform(0, 0.4): mix((0.08, 0.1, 0.08), VERDIGRIS, kk), tile=0.3)
    # The furnace on the bank: fired bricks in running bond round a clay-lined shaft, the top broken,
    # the stoke hole facing the pit, the flue standing broken behind; bricks tumbled down the bank.
    fc = V(-1.55, hb(-1.55, 1.25) - 0.1, 1.25)
    to_pit = math.atan2(cz - fc.z, cx - fc.x)

    def ftop(a):
        d = abs(math.atan2(math.sin(a - to_pit), math.cos(a - to_pit)))
        return fc.y + 0.95 - 0.45 * smoothstep(1.2, 0.2, d) + 0.08 * nz(V(math.cos(a), 0, math.sin(a)) * 3)
    brick_ring(g, rng, fc, 0.36, fc.y, 12, ftop,
               lambda a, y: abs(math.atan2(math.sin(a - to_pit), math.cos(a - to_pit))) < 0.32 and y < fc.y + 0.3)
    disc(g, fc + V(0, 0.02, 0), quat_x(0.0), 0.37, 0.02, 14, M_ROCK, (0.04, 0.035, 0.033))
    charcoal_heap(g, rng, fc.x, fc.z, 0.3, 14, y=fc.y)
    back = fc + V(-math.cos(to_pit) * 0.55, 0.0, -math.sin(to_pit) * 0.55)
    brick_ring(g, rng, back, 0.1, fc.y, 18, lambda a: fc.y + 1.55 - 0.3 * smoothstep(-1, 1, math.sin(a * 2)), brick=(0.12, 0.075, 0.1))
    for k in range(14):
        a = rng.uniform(-1.4, 1.4) + to_pit + math.pi
        rr = rng.uniform(0.6, 1.3)
        p = fc + V(math.cos(a) * rr, 0.0, math.sin(a) * rr)
        p.y = hb(p.x, p.z) + 0.01
        slab(g, tuple(p), (0.23, 0.075, 0.11), quat_y(rng.uniform(0, 6.28)) @ quat_x(rng.uniform(-0.5, 0.5)), rng, mat=M_CLAY,
             res=(2, 1, 2), round_r=0.012, cuts=1, col_fn=lambda q, n, kk=rng.uniform(0.5, 1.0): scale(FIRED, kk), tile=0.3)
    for k in range(4):   # clay daub patches on the shell
        a = to_pit + 1.2 + k * 0.9
        stone(g, tuple(fc + V(math.cos(a) * 0.6, 0.25 + 0.15 * k, math.sin(a) * 0.6)), (0.12, 0.1, 0.03), rng, mat=M_CLAY,
              detail=1, rough=0.2, cuts=0, rot=quat_y(-a + math.pi / 2), col_fn=lambda q, n: RAW_CLAY, tile=0.3)
    # The bellows beside it: two pear-shaped boards on a hinge block, the leather rotted to rags, an
    # iron nozzle aimed at the tuyere.
    side = to_pit + math.pi / 2
    bc = fc + V(math.cos(side) * 0.95, -0.02, math.sin(side) * 0.95)
    d = V(math.cos(to_pit), 0, math.sin(to_pit))
    for k, (y, tilt) in enumerate(((0.05, 0.0), (0.2, 0.25))):
        board(g, bc + V(0, y, 0), d, V(0, 1, 0) + d * tilt, 0.75, 0.42, 0.035, mat=M_MOSSWOOD, col=ROT_WOOD, rng=rng,
              jag=(0, 0.06) if k else (0, 0))
    lbox(g, bc + d * 0.42 + V(0, 0.12, 0), (0.14, 0.16, 0.14), quat_y(-to_pit), M_MOSSWOOD, ROT_WOOD, tile=0.3)
    tube(g, [bc + d * 0.48 + V(0, 0.12, 0), bc + d * 0.8 + V(0, 0.2, 0)], [0.03, 0.022], 6, M_IRON, (0.25, 0.18, 0.13), tile=0.2)
    cloth_drape(g, rng, bc + V(0, 0.08, 0), quat_y(-to_pit + math.pi / 2), 0.45, 0.6, (0.28, 0.22, 0.16), sag=0.04, folds=2)
    # Charcoal heaped on the bank, a raw-clay pile and a trough on the far side.
    charcoal_heap(g, rng, -0.55, 0.95, 0.35, 45, y=hb(-0.55, 0.95) - 0.04)
    mound(g, (1.6, hb(1.6, 0.45) - 0.06, 0.45), 0.35, 0.3, 0.2, rng, mat=M_CLAY, col_fn=lambda p, n: scale(RAW_CLAY, 0.8 + 0.2 * n.y), tile=0.4)
    ty = max(hb(1.6 + dx_, z_) for dx_ in (-0.15, 0.15) for z_ in (-0.7, -0.35, 0.0)) - 0.02
    for sg in (-1, 1):
        board(g, V(1.6 + sg * 0.15, ty + 0.08, -0.35), V(0, 0, 1), V(sg, 0.3, 0), 0.7, 0.2, 0.03, mat=M_MOSSWOOD, col=ROT_WOOD, rng=rng)
    board(g, V(1.6, ty, -0.35), V(0, 0, 1), V(0, 1, 0), 0.7, 0.3, 0.03, mat=M_MOSSWOOD, col=ROT_WOOD, rng=rng)
    # The lifting tripod over the pit: two legs standing lashed at the apex, the third fallen; the
    # chain still hangs, the hook empty.
    apex = V(cx + 0.15, 3.0, cz + 0.05)
    for f in (V(cx + 1.75, hb(cx + 1.75, cz - 1.15) - 0.05, cz - 1.15), V(cx - 1.45, hb(cx - 1.45, cz - 1.3) - 0.05, cz - 1.3)):
        pole(g, f - V(0, 0.2, 0), apex + (apex - f).normalized() * 0.18, 0.08, 0.06, rng, mat=M_MOSSWOOD, col=ROT_WOOD, sides=9)
    W.lashing(g, apex, (0, 1, 0), 0.11, rng, turns=4)
    pole(g, V(cx - 0.7, hb(cx - 0.7, cz + 1.4) + 0.05, cz + 1.4), V(cx + 2.0, max(0.04, hb(cx + 2.0, cz + 2.0) + 0.05), cz + 2.0), 0.08, 0.06, rng, mat=M_MOSSWOOD, col=ROT_WOOD, sides=9)
    links = [apex + V(0, -0.05 - 0.11 * k, 0) for k in range(11)]
    for k in range(len(links) - 1):
        m = (links[k] + links[k + 1]) / 2
        sd = V(1, 0, 0) if k % 2 else V(0, 0, 1)
        tube(g, [m + V(0, 0.055 * math.cos(t), 0) + sd * 0.025 * math.sin(t) for t in np.linspace(0, 6.28, 7)], [0.009] * 7, 4,
             M_IRON, (0.28, 0.18, 0.12), tile=0.15, cap=False)
    hk = links[-1]
    tube(g, [hk, hk + V(0, -0.15, 0), hk + V(0.07, -0.22, 0), hk + V(0.1, -0.12, 0)], [0.025] * 4, 5, M_IRON, (0.28, 0.18, 0.12),
         tile=0.15)
    for k in range(4):   # windfall twigs and leaf litter on the bank
        a = rng.uniform(0, 6.28)
        p = V(cx + math.cos(a) * 1.9, 0.0, cz + math.sin(a) * 1.6)
        p.y = max(0.02, hb(p.x, p.z) + 0.02)
        e = p + V(math.cos(a + 1.4) * 0.8, 0.0, math.sin(a + 1.4) * 0.8)
        e.y = max(0.02, hb(e.x, e.z) + 0.02)
        log(g, rng, p, e, 0.035, col=OAK, moss=0.5, sides=6)
    return b


def site_charcoal_kiln(rng):
    """Footprint r <= 2.9. Masses: the clamp (0, 0) r 1.6, the turf hut (1.6, 1.75), the cordwood (-1.6, 1.6)."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 1.8)
    R, H = 1.75, 1.3
    gap_c, gap_w = -math.pi / 2, 0.55

    def height(r):
        return H * (1 - (r / R) ** 1.25) - 0.12 * smoothstep(0.85, 1.0, r / R)

    def in_gap(a):
        return abs(math.atan2(math.sin(a - gap_c), math.cos(a - gap_c))) < gap_w
    # The clamp: a cone of earth, the gap in its front where the burners broke it open.
    seg, rings = 40, 9
    verts, grid = [], {}
    for j in range(rings + 1):
        r = R * j / rings
        for i in range(seg + 1 if j else 1):
            a = gap_c + gap_w + (2 * math.pi - 2 * gap_w) * i / seg
            e = 1 + 0.05 * nz(V(math.cos(a), 0, math.sin(a)) * 2)
            grid[(j, i)] = len(verts)
            verts.append(V(math.cos(a) * r * e, height(r) * (1 + 0.04 * nz(V(r, a, 0))), math.sin(a) * r * e))
    tris = []
    for i in range(seg):
        tris.append((grid[(0, 0)], grid[(1, i + 1)], grid[(1, i)]))
    for j in range(1, rings):
        for i in range(seg):
            a, b_, c, d = grid[(j, i)], grid[(j, i + 1)], grid[(j + 1, i + 1)], grid[(j + 1, i)]
            tris += [(a, b_, c), (a, c, d)]
    tris = [t if (verts[t[1]] - verts[t[0]]).cross(verts[t[2]] - verts[t[0]]).y > 0 else (t[0], t[2], t[1]) for t in tris]
    smooth_mesh(g, verts, tris, M_EARTH, lambda p, n: mix(scale(DAMP_EARTH, 0.7), MOSS, 0.55 + 0.3 * nz(p * 2.5)), 0.9)
    for sgn in (1, -1):   # the cut faces of the earth skin along the gap
        a = gap_c + sgn * gap_w
        for j in range(rings):
            r0, r1 = R * j / rings, R * (j + 1) / rings
            q = [V(math.cos(a) * r0, height(r0), math.sin(a) * r0), V(math.cos(a) * r1, height(r1), math.sin(a) * r1),
                 V(math.cos(a) * r1, height(r1) - 0.18, math.sin(a) * r1), V(math.cos(a) * r0, height(r0) - 0.18, math.sin(a) * r0)]
            g.flat(q, M_EARTH, (0.2, 0.15, 0.11), 0.6)
            g.flat(q[::-1], M_EARTH, (0.2, 0.15, 0.11), 0.6)
    # Inside the gap: the billets stacked on end leaning to the chimney, charred black at the top.
    r = 0.25
    while r < R - 0.15:
        n = max(2, int(2 * gap_w * r / 0.12))
        for i in range(n):
            a = gap_c - gap_w * 0.92 + 2 * gap_w * 0.92 * (i + 0.5) / n + rng.uniform(-0.02, 0.02)
            foot = V(math.cos(a) * r, -0.1, math.sin(a) * r)
            top = V(math.cos(a) * (r - 0.12), height(r) - 0.12 - rng.uniform(0.0, 0.15), math.sin(a) * (r - 0.12))
            if top.y < 0.08:
                continue
            log(g, rng, foot, top, rng.uniform(0.04, 0.06), col=mix(OAK, (0.07, 0.06, 0.06), 0.8 if r < 1.0 else 0.4), sides=6)
        r += 0.13
    tube(g, [V(0.0, height(0.0) - 0.15, 0.0), V(0.0, height(0.0) + 0.06, 0.0)], [0.16, 0.18], 12, M_EARTH, (0.06, 0.055, 0.05),
         tile=0.5, cap=False)    # the chimney vent
    for k in range(70):   # turf sods laid over the skin
        a = rng.uniform(0, 6.28)
        if in_gap(a):
            continue
        rr = R * math.sqrt(rng.uniform(0.04, 0.92))
        p = V(math.cos(a) * rr, height(rr), math.sin(a) * rr)
        slope_ = (height(rr + 0.05) - height(rr - 0.05)) / 0.1
        nrm = V(-math.cos(a) * slope_, 1.0, -math.sin(a) * slope_).normalized()
        turf_sod(g, rng, p, nrm, rng.uniform(0.8, 1.1))
    # Charcoal raked out in front, a rake and a shovel, the ladder against the clamp.
    charcoal_heap(g, rng, 0.0, -2.05, 0.55, 60)
    charcoal_heap(g, rng, -0.6, -1.7, 0.3, 18)
    beam(g, [V(-0.9, 0.04, -2.3), V(0.6, 0.06, -2.55)], 0.04, 0.04, mat=M_MOSSWOOD, col=ROT_WOOD, rng=rng)
    rh = V(0.6, 0.06, -2.55)
    beam(g, [rh + V(-0.05, 0, -0.25), rh + V(0.05, 0, 0.25)], 0.06, 0.05, mat=M_MOSSWOOD, col=ROT_WOOD, rng=rng)
    for k in range(6):
        p = rh + V(-0.04 + 0.016 * k, 0, -0.2 + 0.08 * k)
        beam(g, [p, p + V(0.12, -0.05, 0)], 0.02, 0.02, mat=M_IRON, mode="bark", col=(0.28, 0.2, 0.15), rng=rng)
    for sg in (-1, 1):
        beam(g, [V(2.05, -0.15, sg * 0.24), V(0.95, 1.0, sg * 0.2)], 0.06, 0.05, mat=M_MOSSWOOD, col=ROT_WOOD, rng=rng)
    for k in range(5):
        f = (k + 0.7) / 6
        a_ = V(2.05, -0.15, -0.24).lerp(V(0.95, 1.0, -0.2), f)
        beam(g, [a_, a_ + V(0, 0, 0.44)], 0.035, 0.035, mat=M_MOSSWOOD, col=ROT_WOOD, rng=rng)
    board(g, V(-1.6, 0.35, -1.2), V(0.3, 1, 0.1), V(0.8, -0.2, -0.6), 0.4, 0.22, 0.03, mat=M_MOSSWOOD, col=ROT_WOOD, rng=rng)
    beam(g, [V(-1.55, 0.55, -1.15), V(-1.2, 1.35, -0.85)], 0.035, 0.035, mat=M_MOSSWOOD, col=ROT_WOOD, rng=rng)
    # The burners' turf hut: forked posts, a ridge pole, rafters, turf sods in rows, door end open.
    hc = V(1.55, 0.0, 1.75)
    ridge = [hc + V(-0.65, 1.2, 0.0), hc + V(0.65, 1.15, 0.0)]
    for p in ridge:
        pole(g, V(p.x, -0.2, p.z), p + V(0, 0.08, 0), 0.06, 0.05, rng, mat=M_MOSSWOOD, col=ROT_WOOD, sides=7)
        for sg in (-1, 1):
            tube(g, [p, p + V(0, 0.12, sg * 0.08)], [0.03, 0.02], 5, M_MOSSWOOD, ROT_WOOD, tile=0.3)
    pole(g, ridge[0] + V(-0.15, 0, 0), ridge[1] + V(0.15, 0, 0), 0.05, 0.045, rng, mat=M_MOSSWOOD, col=ROT_WOOD, sides=7)
    for sg in (-1, 1):
        for k in range(5):
            x = -0.6 + 0.3 * k
            pole(g, hc + V(x, 1.15, 0), hc + V(x, -0.1, sg * 0.85), 0.035, 0.03, rng, mat=M_MOSSWOOD, col=ROT_WOOD, sides=6)
        slope_n = V(0, 0.85, sg * 1.2).normalized()
        for row in range(4):
            f = (row + 0.5) / 4
            for k in range(4):
                if sg > 0 and row == 0 and k == 1:
                    continue   # a hole in the roof
                p = hc + V(-0.5 + 0.33 * k + rng.uniform(-0.03, 0.03), 1.15 - 1.15 * f, sg * 0.8 * f)
                turf_sod(g, rng, p + slope_n * 0.04, slope_n, 0.95)
    # Cordwood: a stack between stakes and a tumbled heap, mossed, shelf fungus on the old ends.
    for row in range(3):
        for k in range(6 - row):
            y = 0.1 + row * 0.15
            z = 1.25 + (5 - row) * 0.075 - k * 0.15 + 0.5
            log(g, rng, V(-2.25, y, z - 0.5), V(-1.45, y, z - 0.5 + rng.uniform(-0.04, 0.04)), 0.07, col=OAK,
                moss=0.6 if row == 2 else 0.2)
    for z in (0.75, 2.05):
        pole(g, V(-1.85, -0.2, z - 0.5 + 0.0), V(-1.85, 0.75, z - 0.5), 0.04, 0.035, rng, mat=M_MOSSWOOD, col=ROT_WOOD, sides=6)
    shelf_fungus(g, rng, V(-2.3, 0.4, 1.4), V(-1, 0.2, 0), s=0.09)
    for k in range(5):
        a = rng.uniform(0, 3.1)
        p = V(-1.4 + rng.uniform(-0.3, 0.4), 0.07, -0.2 + rng.uniform(-0.4, 0.3))
        log(g, rng, p, p + V(math.cos(a) * 0.75, 0.02, math.sin(a) * 0.75), 0.065, col=OAK, moss=0.7)
    return b


def site_sawpit(rng):
    """Footprint r <= 3.0. Masses: the trunk on its skids along X (x -2.2..1.9), the bank is walkable."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 1.8)
    cx, cz, hx, hz, h = 0.0, 0.0, 1.5, 0.42, 0.5
    hb = shored_pit(g, rng, cx, cz, hx, hz, h, 0.35, 0.6, posts_x=3, fallen=False, clods=8, roots=7, stones=6)
    # Sawdust heaped on the pit floor under the cut and along it.
    for k, (x, r_, hh) in enumerate(((0.45, 0.4, 0.2), (0.9, 0.3, 0.12), (-0.2, 0.25, 0.08))):
        mound(g, (x, -0.04, 0.0), r_, 0.3, hh, rng, mat=M_EARTH, col_fn=lambda p, n: mix((0.86, 0.72, 0.52), MOSS,
              0.15 * nz(p * 6) + 0.05), tile=0.4)
    # Two squared skids across the pit, the trunk dogged to them with iron staples.
    for x in (-0.85, 0.95):
        beam(g, [V(x, h + 0.08, -0.85), V(x, h + 0.08, 0.85)], 0.17, 0.17, mat=M_MOSSWOOD, col=ROT_WOOD, rng=rng, rough=0.04)
        for zs in (-0.68, 0.68):   # each skid end bedded on a packing block dug into the spoil
            by = hb(x, zs)
            top = h - 0.005
            if top - by > -0.02:
                slab(g, (x, (top + by - 0.08) / 2, zs), (0.24, top - by + 0.08, 0.2), quat_y(rng.uniform(-0.2, 0.2)), rng,
                     mat=M_MOSSWOOD, res=(2, 1, 2), round_r=0.015, cuts=1, col_fn=lambda q, n: scale(ROT_WOOD, 0.8), tile=0.3)
        log_dog(g, V(x + 0.12, h + 0.2, 0.25), V(1, 0.6, 0))
    y0 = h + 0.17 + 0.3
    log(g, rng, V(-2.2, y0, 0.0), V(0.32, y0, 0.0), 0.3, col=OAK, moss=0.3, cap=False, sides=14)
    disc(g, V(-2.2, y0, 0.0), quat_z(math.pi / 2), 0.3, 0.02, 14, M_PLANK, (0.8, 0.64, 0.46))      # end grain
    for k in range(5):
        ring_on(g, V(-2.212, y0, 0.0), V(-1, 0, 0), V(0, 1, 0), 0.05 + 0.05 * k, (0.55, 0.4, 0.28), r=0.004, mat=M_PLANK, n=17)
    # From x = 0.32 on, the kerf: the trunk is two halves, pale sawn faces, end grain at the far end.
    for side in (1, -1):
        half_log(g, rng, V(0.32, y0, 0.0), V(1.9, y0, 0.0), 0.3, side)
    for x in (1.3, 1.7):   # wedges driven into the kerf
        slab(g, (x, y0 + 0.28, 0.0), (0.14, 0.16, 0.03), quat_z(0.15), rng, mat=M_PLANK, res=(2, 2, 1), round_r=0.005,
             taper=0.7, col_fn=lambda p, n: (0.7, 0.62, 0.5), tile=0.3)
    # The pit saw left in the cut: a long blade standing in the kerf, tiller on top, box handle below.
    sx = 0.36
    lbox(g, V(sx, 1.1, 0.0), (0.14, 2.1, 0.006), quat_y(0.0), M_IRON, (0.32, 0.24, 0.18), tile=0.5, grain=1)
    for k in range(40):
        y = 0.08 + k * 0.052
        g.flat([V(sx - 0.07, y, 0.004), V(sx - 0.07, y + 0.045, 0.004), V(sx - 0.095, y + 0.01, 0.004)], M_IRON, (0.28, 0.2, 0.15), 0.2)
        g.flat([V(sx - 0.095, y + 0.01, -0.004), V(sx - 0.07, y + 0.045, -0.004), V(sx - 0.07, y, -0.004)], M_IRON, (0.28, 0.2, 0.15), 0.2)
    lbox(g, V(sx, 2.2, 0.0), (0.1, 0.16, 0.08), quat_y(0.0), M_MOSSWOOD, ROT_WOOD, tile=0.3)
    tube(g, [V(sx, 2.22, -0.4), V(sx, 2.22, 0.4)], [0.03, 0.03], 8, M_MOSSWOOD, ROT_WOOD, tile=0.3)
    for z in (-0.12, 0.12):
        tube(g, [V(sx, 0.08, z), V(sx, -0.1, z)], [0.02, 0.02], 6, M_MOSSWOOD, ROT_WOOD, tile=0.3)
    tube(g, [V(sx, -0.1, -0.2), V(sx, -0.1, 0.2)], [0.025, 0.025], 6, M_MOSSWOOD, ROT_WOOD, tile=0.3)
    # The first slab cut off (bark on its back) and sawn boards stacked on stickers on the bank.
    half_log(g, rng, V(-1.4, hb(-1.4, 0.82) + 0.05, 0.82), V(0.4, hb(0.4, 0.78) + 0.05, 0.78), 0.12, 1)
    sb = max(hb(x_, z_) for x_ in np.linspace(-1.15, 1.05, 7) for z_ in (-0.9, -0.64)) - 0.02   # the board stack's footing
    for k in range(3):
        y = sb + 0.03 + k * 0.08
        for x in (-1.0, 0.0, 0.9):
            if k:
                beam(g, [V(x, y - 0.03, -0.92), V(x, y - 0.03, -0.62)], 0.04, 0.03, mat=M_MOSSWOOD, col=ROT_WOOD, rng=rng)
        board(g, V(-0.05, y + 0.02, -0.77), V(1, 0, rng.uniform(-0.02, 0.02)), V(0, 1, 0), 2.2, 0.26, 0.045, mat=M_PLANK,
              col=mix((0.9, 0.78, 0.6), MOSS, 0.2 * k), rng=rng)
    for k in range(5):   # windfall and old bark on the bank
        a = rng.uniform(0, 6.28)
        p = V(math.cos(a) * 2.1, 0.0, math.sin(a) * 1.0)
        p.y = max(0.02, hb(p.x, p.z) + 0.02)
        e = p + V(math.cos(a + 1.5) * 0.7, 0.0, math.sin(a + 1.5) * 0.5)
        e.y = max(0.02, hb(e.x, e.z) + 0.02)
        log(g, rng, p, e, 0.035, col=OAK, moss=0.5, sides=6)
    return b


def site_rooted_pillar(rng):
    """Footprint r <= 3.0. Masses: the oak's root flare (0.6, 1.45) r 1.05, the pillar (-0.5, -0.35). The
    game plants the kit's dead oak (dead_a, scaled) on the flare."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 5, 1.5)
    tc = V(0.6, 0.0, 1.45)
    # The root flare: buttress lobes running down into the ground; the kit's dead oak stands on top.
    ys = [-0.35, -0.05, 0.25, 0.6, 1.0, 1.45, 1.7]
    rs = [1.35, 1.12, 0.92, 0.75, 0.66, 0.62, 0.6]
    seg = 28
    verts = []
    for y, r_ in zip(ys, rs):
        f = smoothstep(1.45, -0.35, y)
        for i in range(seg):
            a = i / seg * 2 * math.pi
            lobe = 1 + 0.22 * f * max(0.0, math.cos(5 * a + 0.7)) ** 2 - 0.06 * f
            rr = r_ * lobe * (1 + 0.04 * nz(V(math.cos(a) * 2, y, math.sin(a) * 2)))
            verts.append(tc + V(math.cos(a) * rr, y, math.sin(a) * rr))
    tris = []
    for j in range(len(ys) - 1):
        for i in range(seg):
            a, b_ = j * seg + i, j * seg + (i + 1) % seg
            tris += [(a, b_, b_ + seg), (a, b_ + seg, a + seg)]
    tris = orient(verts, tris, tc, V(0, 1, 0), True)
    smooth_mesh(g, verts, tris, M_BARK, lambda p, n: mix((0.5, 0.46, 0.4), MOSS, 0.5 * smoothstep(0.9, -0.2, p.y)), 0.9)
    # The Old Ones' pillar: a squared, chamfered shaft, heaved over by the roots; rings cut in bands,
    # a zigzag between them, lichen on its crown.
    pc = V(-0.5, 1.2, -0.35)
    prot = quat_z(0.13) @ quat_x(-0.09)
    slab(g, tuple(pc), (0.56, 2.9, 0.46), prot, rng, mat=M_MOSSROCK, res=(3, 12, 3), round_r=0.035, taper=0.22, rough=0.006,
         crown=0.2, cuts=1, col_fn=mossy((0.8, 0.78, 0.72), 0.75, nz, wet=0.6), tile=0.9)
    face, up = prot @ V(0, 0, -1), prot @ V(0, 1, 0)
    right = up.cross(face).normalized()
    cut = (0.2, 0.21, 0.17)
    for k, y in enumerate((-0.15, 0.5, 1.05)):
        c = pc + up * y + face * 0.245
        for rr in (0.05, 0.1, 0.15):
            ring_on(g, c, face, up, rr - 0.012 * k, cut, r=0.012, mat=M_MOSSROCK)
    for y in (0.18, 0.78):
        zz = [pc + up * (y + (0.05 if i % 2 else -0.05)) + face * 0.245 + right * (-0.2 + 0.05 * i) for i in range(9)]
        carve_line(g, zz, cut, 0.011, M_MOSSROCK)
    # Roots: buttresses radiating into the ground, and two that grip the pillar — one wrapped round
    # its foot, one round its waist — and a rootlet draped over its crown.
    for k in range(7):
        a = 0.7 + k * 0.85
        if 3.3 < a % (2 * math.pi) < 4.4:
            continue   # toward the pillar: the gripping roots take that side
        p0 = tc + V(math.cos(a) * 0.9, 0.55, math.sin(a) * 0.9)
        pts = [p0, tc + V(math.cos(a) * 1.45, 0.12, math.sin(a) * 1.45), tc + V(math.cos(a + 0.15) * 2.0, 0.0, math.sin(a + 0.15) * 2.0),
               tc + V(math.cos(a + 0.25) * 2.5, -0.12, math.sin(a + 0.25) * 2.5)]
        tube(g, pts, [0.3, 0.2, 0.14, 0.09], 9, M_BARK, (0.5, 0.46, 0.4), tile=0.8,
             col_fn=lambda t: mix((0.5, 0.46, 0.4), MOSS, 0.6 * smoothstep(0.2, 1.0, t)))
    base = pc - up * 1.45
    for k, (hh, a0, a1, sgn) in enumerate(((0.35, 0.5, 4.6, 1), (0.95, 0.2, 3.9, -1))):
        r_ = 0.36 + 0.08 * k
        start = tc + V(-0.75, 0.6 + 0.2 * k, -0.55)
        wrap = []
        for t in np.linspace(0, 1, 10):
            a = a0 + (a1 - a0) * t
            c = base + up * (hh - 0.25 * t)
            wrap.append(c + (right * math.cos(a * sgn) + face * math.sin(a * sgn)) * r_)
        end = wrap[-1] + V(0, -0.5, 0) + (wrap[-1] - wrap[-2]).normalized() * 0.4
        pts = [start] + wrap + [end]
        radii = [0.2] + [0.11 - 0.005 * i for i in range(10)] + [0.05]
        tube(g, pts, radii, 8, M_BARK, (0.48, 0.44, 0.38), tile=0.7,
             col_fn=lambda t: mix((0.48, 0.44, 0.38), MOSS, 0.3 + 0.3 * t))
    top = pc + up * 1.45
    tube(g, [tc + V(-0.6, 1.4, -0.5), top + V(0.05, 0.1, 0.05), top - up * 0.6 - face * 0.28, top - up * 1.4 - face * 0.3 + V(0, -0.3, 0)],
         [0.07, 0.045, 0.035, 0.025], 6, M_BARK, (0.45, 0.42, 0.36), tile=0.5)
    # Moss humps over the root bases, shelf fungus on the flare, mushrooms, the dead tree's fallen limbs.
    for k in range(6):
        a = rng.uniform(0, 6.28)
        forest_mound(g, (tc.x + math.cos(a) * 1.4, -0.08, tc.z + math.sin(a) * 1.4), 0.5, 0.4, 0.18, rng, moss=0.9, rings=3, seg=12)
    for k in range(8):
        a = 2.4 + k * 0.4
        y = 0.4 + (k % 4) * 0.28
        p = tc + V(math.cos(a) * 0.82, y, math.sin(a) * 0.82)
        shelf_fungus(g, rng, p, V(math.cos(a), 0, math.sin(a)), s=rng.uniform(0.1, 0.17))
    for k in range(12):
        p = V(rng.uniform(-1.8, 1.8), 0.12, rng.uniform(-1.8, -0.6))
        tube(g, [p - V(0, 0.15, 0), p + V(0, 0.05, 0)], [0.012, 0.01], 5, M_CLAY, (0.9, 0.86, 0.78), tile=0.2)
        dome(g, p + V(0, 0.04, 0), 0.04, quat_y(0.0), M_CLAY, lambda q, n: (0.62, 0.36, 0.2), tile=0.2, rings=2, seg=8, squash=0.6)
    for k, (a_, b_) in enumerate(((V(-2.2, 0.08, 0.6), V(-0.8, 0.2, 1.9)), (V(1.4, 0.1, -1.6), V(2.5, 0.05, -0.2)))):
        log(g, rng, a_, b_, 0.13 - 0.03 * k, col=(0.55, 0.5, 0.44), moss=0.6, sides=9)
        for f in (0.3, 0.7):
            p = a_.lerp(b_, f)
            log(g, rng, p, p + V(0.3, 0.35, -0.2), 0.04, col=(0.55, 0.5, 0.44), sides=5)
    return b


def oriented(verts, tris, want):
    """Wind each triangle so its normal agrees with `want(centroid)`."""
    out = []
    for t in tris:
        n = (verts[t[1]] - verts[t[0]]).cross(verts[t[2]] - verts[t[0]])
        c = (verts[t[0]] + verts[t[1]] + verts[t[2]]) / 3
        out.append(t if n.dot(want(c)) >= 0 else (t[0], t[2], t[1]))
    return out


def grave_mound(g, rng, c, rx, rz, h, yaw, nz, sunk=0.35):
    """An old grave: a low long hump of settled turf, its middle sunk where the coffin gave way (leaf
    litter and damp collect there), the rim melting into the forest floor."""
    c, rq = Vector(c), quat_y(yaw)
    rings, seg = 5, 16

    def hgt(r, a):
        y = h * (1 - r ** 2.4) - h * sunk * math.exp(-(r / 0.5) ** 2) + 0.018 * nz(c + V(math.cos(a) * r, 0, math.sin(a) * r) * 3)
        return y - 0.07 * smoothstep(0.85, 1.0, r)
    verts = [c + V(0, hgt(0.0, 0.0), 0)]
    for j in range(1, rings + 2):
        r = j / rings
        for i in range(seg):
            a = i / seg * 2 * math.pi
            wob = 1 + 0.08 * nz(c + V(math.cos(a), 2, math.sin(a)) * 1.7)
            y = hgt(min(r, 1.0), a) - (0.08 if r > 1.0 else 0.0)
            verts.append(c + rq @ V(math.cos(a) * rx * r * wob, y, math.sin(a) * rz * r * wob))
    tris = [(0, 1 + i, 1 + (i + 1) % seg) for i in range(seg)]
    for j in range(rings):
        for i in range(seg):
            a_, b_ = 1 + j * seg + i, 1 + j * seg + (i + 1) % seg
            tris += [(a_, a_ + seg, b_ + seg), (a_, b_ + seg, b_)]
    tris = oriented(verts, tris, lambda q: V(0, 1, 0))
    inv = rq.inverted()

    def col(p, n):
        q = inv @ (p - c)
        r = math.hypot(q.x / rx, q.z / rz)
        dip = math.exp(-(r / 0.5) ** 2)
        turf = mix(scale(MOSS, 0.75 + 0.2 * nz(p * 5)), scale(LITTER, 0.95), 0.6 * smoothstep(0.1, 0.6, nz(p * 2.2)))
        turf = mix(turf, scale(LITTER, 0.8), 0.45 * dip)                  # litter and damp in the sunk middle
        return mix(turf, scale(LITTER, 0.85), smoothstep(0.75, 1.0, r))   # the rim: forest floor
    smooth_mesh(g, verts, tris, M_EARTH, col, 0.8)


def rot_col(t, k=1.0):
    """Rotten grave wood: grey, moss creeping up from the ground end (t = 0)."""
    return mix(scale(MOSS, 0.7), scale((0.5, 0.48, 0.44), k), smoothstep(0.0, 0.35, t))


def site_anselm_forest(rng):
    """Footprint r <= 3.0. Masses: the hollow oak stump (1.6, 0.5) r 0.75; the graves are low mounds."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 1.8)
    # Five graves in a row (+ one small one): settled, sunk turf mounds; rotten crosses leaning every way,
    # one fallen across its grave, the child's a split board; a kerb of fieldstones round two of them.
    for k, (x, z, s) in enumerate(((-1.9, -0.3, 1.0), (-1.1, -0.35, 1.0), (-0.3, -0.3, 1.0), (0.45, -0.4, 1.0),
                                   (-1.5, 0.95, 0.55), (-0.6, 0.95, 1.0))):
        grave_mound(g, rng, (x, -0.02, z), 0.36 * s, 0.85 * s, 0.15 * s, rng.uniform(-0.08, 0.08), nz)
        if k in (1, 5):
            for i in range(9):
                a = i / 9 * 2 * math.pi + rng.uniform(-0.1, 0.1)
                if rng.uniform() < 0.2:
                    continue   # stones gone, sunk out of sight
                r = rng.uniform(0.07, 0.11)
                stone(g, (x + math.cos(a) * 0.42 * s, -r * 0.35, z + math.sin(a) * 0.92 * s), (r, r * 0.7, r * 0.85), rng,
                      mat=M_MOSSROCK, detail=0, rough=0.12, cuts=1, col_fn=mossy((0.66, 0.64, 0.6), 0.7, nz), tile=0.4)
        cz = z - 0.8 * s
        if k == 3:   # the cross fallen across its grave, its arm come off beside it
            beam(g, [V(x - 0.12, 0.08, cz + 0.15), V(x + 0.18, 0.06, z + 0.45)], 0.08, 0.06, mat=M_MOSSWOOD, col=ROT_WOOD,
                 rng=rng, jag=(0.05, 0), col_fn=lambda t: rot_col(1 - t, 0.9))
            beam(g, [V(x - 0.3, 0.05, z - 0.05), V(x + 0.22, 0.04, z + 0.12)], 0.07, 0.05, mat=M_MOSSWOOD, col=ROT_WOOD,
                 rng=rng, col_fn=lambda t: rot_col(0.5, 0.85))
            disc(g, V(x - 0.1, 0.0, cz), quat_x(0.0), 0.06, 0.02, 7, M_EARTH, (0.12, 0.09, 0.07))   # the hole it stood in
            continue
        foot = V(x, -0.25, cz)
        if k == 4:   # the child's grave: a small board, split down the middle, one half leaning off
            for sg, lean in ((-1, 0.05), (1, 0.32)):
                rq = quat_z(-sg * lean) @ quat_x(rng.uniform(-0.1, 0.1))
                board(g, foot + V(sg * 0.07, 0.42, 0), rq @ V(0, 1, 0), V(0, 0, -1), 0.8, 0.13, 0.03, mat=M_MOSSWOOD,
                      col=ROT_WOOD, rng=rng, jag=(0, 0.06), col_fn=lambda t: rot_col(t))
            continue
        h = 1.0 * s
        rot = quat_x(rng.uniform(-0.28, 0.2)) @ quat_z(rng.uniform(-0.22, 0.22))
        kk = rng.uniform(0.8, 1.0)
        beam(g, [foot, foot + rot @ V(0, h + 0.25, 0)], 0.09, 0.07, mat=M_MOSSWOOD, col=ROT_WOOD, rng=rng, jag=(0, 0.03),
             col_fn=lambda t, kk=kk: rot_col(t, kk))
        arm = foot + rot @ V(0, h * 0.85, 0)
        ar = rot @ quat_z(rng.uniform(-0.25, 0.25) if k in (0, 2) else 0.0)     # arms slipped on their pegs
        beam(g, [arm - ar @ V(0.28 * s, 0, 0), arm + ar @ V(0.28 * s, 0, 0)], 0.07, 0.06, mat=M_MOSSWOOD, col=ROT_WOOD,
             rng=rng, jag=(0.03, 0.03), col_fn=lambda t: rot_col(0.6, 0.9))
        tube(g, [arm + rot @ V(0.05 * math.cos(t), 0.05 * math.sin(t), 0.045) for t in np.linspace(0, 6.3, 7)],
             [0.007] * 7, 3, M_CLOTH, scale(W.ROPE, 0.45), tile=0.2, cap=False)
        for m in range(int(rng.integers(1, 3))):   # mushrooms in the grave turf
            q = V(x + rng.uniform(-0.2, 0.2), 0.07, z + rng.uniform(-0.45, 0.45))
            tube(g, [q - V(0, 0.08, 0), q + V(0, 0.04, 0)], [0.01, 0.008], 5, M_CLAY, (0.9, 0.86, 0.78), tile=0.2)
            dome(g, q + V(0, 0.03, 0), 0.035, quat_y(0.0), M_CLAY, lambda qq, n: (0.75, 0.6, 0.42), tile=0.2, rings=2,
                 seg=8, squash=0.5)
    # A rotten paling once round the plot: stubs and one fallen section.
    for k in range(9):
        x = -2.5 + k * 0.48
        if k in (3, 4):
            continue
        hh = rng.uniform(0.25, 0.7)
        beam(g, [V(x, -0.2, -1.75), V(x + rng.uniform(-0.08, 0.08), hh, -1.75 + rng.uniform(-0.06, 0.06))], 0.06, 0.05,
             mat=M_MOSSWOOD, col=ROT_WOOD, rng=rng, jag=(0, 0.06), col_fn=lambda t: rot_col(t))
    beam(g, [V(-1.1, 0.04, -2.0), V(-0.1, 0.03, -2.3)], 0.06, 0.04, mat=M_MOSSWOOD, col=ROT_WOOD, rng=rng,
         col_fn=lambda t: rot_col(0.3))
    # The hollow oak: a gnarled broken trunk, buttress lobes and burls, flaring into roots; the bark rolls in
    # round a tall dark hollow that opens toward the graves (-X), its broken top splintered.
    tc = V(1.65, 0.0, 0.5)
    seg, ys = 26, [-0.15, 0.0, 0.18, 0.4, 0.65, 0.95, 1.25, 1.55, None]
    mtop = 1.1

    def mouth_w(y):
        if y <= -0.1 or y >= mtop:
            return 0.0
        return 0.5 * max(0.0, 1 - (max(y, 0.0) / mtop) ** 2.4) ** 0.5 * smoothstep(-0.1, 0.0, y)

    def top_h(a):
        d = math.atan2(math.sin(a - 0.7), math.cos(a - 0.7))
        return 1.75 + 0.3 * math.sin(a * 2 + 1) + 0.14 * math.sin(a * 5 + 0.3) + 0.6 * math.exp(-(d / 0.35) ** 2)

    def rad(a, y):
        fl = smoothstep(0.9, -0.2, y)
        r = 0.6 + 0.3 * math.exp(-(y + 0.02) / 0.2)
        r *= 1 + 0.32 * (fl + 0.2) * max(0.0, math.cos(5 * a + 0.7)) ** 2 + 0.05 * nz(V(math.cos(a) * 2, y * 1.5, math.sin(a) * 2))
        for ab, yb, k in ((0.3, 0.85, 0.12), (4.6, 1.3, 0.09), (2.0, 0.5, 0.08)):   # burls
            da = math.atan2(math.sin(a - ab), math.cos(a - ab))
            r *= 1 + k * math.exp(-(da / 0.3) ** 2 - ((y - yb) / 0.2) ** 2)
        return r
    outer, inner = [], []
    for y0 in ys:
        ro, ri = [], []
        w = 0.0 if y0 is None else mouth_w(y0)
        for i in range(seg + 1):
            a = math.pi + w + (2 * math.pi - 2 * w) * i / seg
            y = top_h(a) if y0 is None else min(y0, top_h(a) - 0.1)
            r = rad(a, y)
            ro.append(tc + V(math.cos(a) * r, y, math.sin(a) * r))
            yi = max(y, 0.12)
            ri_ = (min(r * 0.74, 0.5) if y0 is not None else r * 0.74) * (1 + 0.04 * nz(V(a, yi * 3, 0)))
            ri.append(tc + V(math.cos(a) * ri_, yi, math.sin(a) * ri_))
        outer.append(ro)
        inner.append(ri)

    def grid(rows):
        verts = [p for row in rows for p in row]
        n = seg + 1
        tris = []
        for j in range(len(rows) - 1):
            for i in range(seg):
                a_, b_ = j * n + i, j * n + i + 1
                tris += [(a_, b_, b_ + n), (a_, b_ + n, a_ + n)]
        return verts, tris
    vo, to = grid(outer)
    n_wall = len(to)
    for side in (0, seg):   # the lips: bark rolled in round the mouth
        for j in range(len(ys) - 1):
            base = len(vo)
            vo += [outer[j][side], inner[j][side], inner[j + 1][side], outer[j + 1][side]]
            to += [(base, base + 1, base + 2), (base, base + 2, base + 3)]
    n_lips = len(to)
    for i in range(seg):   # the splintered rim
        base = len(vo)
        vo += [outer[-1][i], outer[-1][i + 1], inner[-1][i + 1], inner[-1][i]]
        to += [(base, base + 1, base + 2), (base, base + 2, base + 3)]
    to = (oriented(vo, to[:n_wall], lambda c_: V(c_.x - tc.x, 0, c_.z - tc.z)) +
          oriented(vo, to[n_wall:n_lips], lambda c_: tc + V(-0.7, c_.y, 0) - c_) +
          oriented(vo, to[n_lips:], lambda c_: V(0, 1, 0)))

    def bark(p, n):
        c = scale((0.56, 0.5, 0.43), 0.85 + 0.2 * nz(p * 3))
        c = mix(c, scale(MOSS, 0.85), 0.75 * smoothstep(0.7, -0.1, p.y) * (0.6 + 0.4 * nz(p * 4)))       # moss up from the roots
        c = mix(c, scale(MOSS, 0.9), 0.5 * smoothstep(0.2, 0.8, n.z) * smoothstep(0.0, 0.5, nz(p * 2)))    # the damp side
        c = mix(c, (0.68, 0.7, 0.58), 0.4 * smoothstep(0.45, 0.8, nz(p * 6.5)))                           # lichen
        return mix(c, (0.4, 0.3, 0.22), 0.6 * smoothstep(0.5, 0.95, n.y))                                 # rotten top
    smooth_mesh(g, vo, to, M_BARK, bark, 0.8)
    vi, ti = grid(inner)
    ti = oriented(vi, ti, lambda c_: V(tc.x - c_.x, 0, tc.z - c_.z))
    smooth_mesh(g, vi, ti, M_MOSSWOOD, lambda p, n: mix((0.07, 0.05, 0.04), (0.36, 0.27, 0.19), smoothstep(0.2, 2.0, p.y)), 0.5)
    disc(g, tc + V(0, 0.12, 0), quat_x(0.0), 0.5, 0.03, 12, M_EARTH, (0.1, 0.075, 0.06))   # the hollow's floor of punk and leaves
    for k in range(7):   # the roots, flaring into the ground (none across the mouth), kept inside the footprint
        a = 0.2 + k * 0.78
        if abs(math.atan2(math.sin(a - math.pi), math.cos(a - math.pi))) < 0.55:
            continue
        d = V(math.cos(a), 0, math.sin(a))
        reach = 2.0
        while (tc + d * (0.95 + reach)).length > 2.85 and reach > 0.5:
            reach -= 0.1
        pts = [tc + d * 0.55 + V(0, 0.22, 0), tc + d * 0.95 + V(0, 0.04, 0), tc + d * (0.95 + reach * 0.45) + V(0, -0.03, 0),
               tc + d * (0.95 + reach) + V(0, -0.12, 0)]
        tube(g, pts, [0.2, 0.11, 0.065, 0.03], 8, M_BARK, (0.52, 0.47, 0.4), tile=0.7,
             col_fn=lambda t: mix((0.52, 0.47, 0.4), MOSS, 0.4 + 0.4 * t))
    for k in range(6):   # bracket fungus up the trunk
        a = 0.4 + k * 0.75
        y = 0.45 + k * 0.22
        shelf_fungus(g, rng, tc + V(math.cos(a) * rad(a, y) * 0.95, y, math.sin(a) * rad(a, y) * 0.95), V(math.cos(a), 0, math.sin(a)),
                     s=rng.uniform(0.09, 0.15))
    # In the hollow: the journal's cover on the floor of rotted wood, a page tucked upright into a crack of
    # the inner wall where it caught the light, a flat stone laid on the cover against the wet.
    lbox(g, tc + V(-0.18, 0.16, 0.08), (0.24, 0.035, 0.3), quat_y(0.4) @ quat_z(0.12), M_HIDE, (0.3, 0.19, 0.12), tile=0.3)
    page(g, tc + V(-0.3, 0.42, -0.22), quat_y(-0.9) @ quat_z(math.pi / 2 - 0.15), w=0.2, l=0.27, curl=0.02)
    slab(g, tuple(tc + V(-0.16, 0.2, 0.1)), (0.18, 0.05, 0.14), quat_y(0.7), rng, mat=M_MOSSROCK, res=(2, 1, 2),
         round_r=0.015, col_fn=mossy((0.7, 0.7, 0.66), 0.3, nz), tile=0.4)
    # A limb the oak dropped, rotting in the litter, and its broken top's splinters.
    log(g, rng, V(2.45, 0.1, -0.9), V(0.9, 0.08, -1.55), 0.13, col=(0.52, 0.47, 0.4), moss=0.6, sides=9)
    log(g, rng, V(1.6, 0.09, -1.25), V(1.85, 0.35, -1.75), 0.05, col=(0.52, 0.47, 0.4), moss=0.4, sides=6)
    for k in range(4):
        q = tc + V(rng.uniform(-0.2, 0.9), 0.04, rng.uniform(-1.1, -0.7))
        beam(g, [q, q + V(rng.uniform(-0.4, 0.4), 0.03, rng.uniform(-0.3, 0.3))], 0.05, 0.03, mat=M_MOSSWOOD, col=(0.4, 0.33, 0.26),
             rng=rng, jag=(0.04, 0.04))
    # Forest floor: drifts of leaf litter against the roots and the graves, loose leaves, twigs, mossy stones.
    for k, (x, z, r_) in enumerate(((0.75, 0.2, 0.45), (1.2, 1.35, 0.5), (-2.4, 0.4, 0.4), (0.1, 0.6, 0.35), (-1.6, -1.3, 0.4),
                                    (2.3, -0.2, 0.35))):
        forest_mound(g, (x, -0.05, z), r_, r_ * 0.75, 0.08, rng, moss=0.25, base=LITTER, rings=3, seg=10)
    leaf_cols = [(0.55, 0.36, 0.18), (0.45, 0.3, 0.16), (0.62, 0.45, 0.22), (0.35, 0.26, 0.17)]
    for k in range(60):
        a, rr = rng.uniform(0, 6.28), rng.uniform(0.3, 2.8)
        q = V(math.cos(a) * rr, 0.012, math.sin(a) * rr)
        if (q - tc).length < 0.8:
            continue
        rq = quat_y(rng.uniform(0, 6.28)) @ quat_x(rng.uniform(-0.25, 0.25))
        sz = rng.uniform(0.04, 0.07)
        g.flat([q + rq @ V(-sz * 0.45, 0.004, 0), q + rq @ V(0, 0, sz), q + rq @ V(sz * 0.45, 0.004, 0), q + rq @ V(0, 0, -sz)],
               M_EARTH, leaf_cols[k % 4], 0.2)
    for k in range(7):
        q = V(rng.uniform(-2.6, 2.4), 0.02, rng.uniform(-2.2, 1.6))
        a = rng.uniform(0, 6.28)
        log(g, rng, q, q + V(math.cos(a) * 0.5, 0.0, math.sin(a) * 0.5), 0.015, col=(0.45, 0.38, 0.3), sides=4)
    for k, (x, z, r_) in enumerate(((-2.5, 1.2, 0.18), (0.95, -0.5, 0.14), (2.4, 1.1, 0.2), (-0.1, -1.3, 0.12))):
        stone(g, (x, r_ * 0.15, z), (r_, r_ * 0.6, r_ * 0.8), rng, mat=M_MOSSROCK, detail=1, rough=0.12, cuts=2,
              col_fn=mossy((0.66, 0.64, 0.6), 0.8, nz), tile=0.5)
    # A rough wooden marker board at the head of the row: scratched lines (names), weathered illegible.
    mc = V(-2.55, 0.0, -0.9)
    beam(g, [mc - V(0, 0.2, 0), mc + V(0.06, 0.95, 0)], 0.08, 0.06, mat=M_MOSSWOOD, col=ROT_WOOD, rng=rng, col_fn=lambda t: rot_col(t))
    board(g, mc + V(0.07, 0.7, -0.05), V(1, -0.12, 0), V(0, 0, -1), 0.6, 0.3, 0.035, mat=M_MOSSWOOD, col=ROT_WOOD, rng=rng,
          jag=(0, 0.05), col_fn=lambda t: rot_col(0.5 + 0.5 * t))
    for k in range(4):
        y = 0.79 - k * 0.06
        carve_line(g, [mc + V(-0.18, y + 0.02, -0.075), mc + V(0.12 + 0.08 * (k % 2), y - 0.02 - 0.01 * (k % 2), -0.075)],
                   (0.2, 0.17, 0.14), 0.006, M_MOSSWOOD)
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
