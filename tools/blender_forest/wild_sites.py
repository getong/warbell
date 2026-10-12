"""Hidden discovery sites of the SWAMP and the ROCKY mountains -> wild_sites.glb (src/wild_sites.rs).

Design: docs/superpowers/specs/2026-10-12-wyspa-opowiada-design.md (SKALY "the iron voice",
BAGNO "the end and the other shore") under the campaign plan 2026-10-10-kampania-fabula-design.md.
No text, no interaction: each scene explains itself. Each biome has its OWN palette and kind of place:

ROCKY  (granite, slate, black iron, red ochre, lichen, rope)
  site_clan_gong        - the Old Ones' iron voice: a black-iron gong hung on an iron bar between two
                          lichen-crusted menhirs (ochre bands, carved rings), a ring of boundary stones,
                          offerings at its foot (tusks, boar skulls, ochre bowls) and the stone maul
                          laid on the altar stone, never lifted. Nobody camps here.
  site_signal_tower     - the first colony's dry-slate signal tower on a spur: top broken off, one
                          flank slumped into a scree of slate, the outside stair fallen mid-flight,
                          the iron fire basket tipped on the parapet. Under a flat stone at the foot
                          of the stair: a journal page (Anselm, stage 3).
  site_rope_bridge      - the colony's rope bridge to the east, CUT in the war: two anchor posts in a
                          slate pier at a brink, one main rope sliced clean, the other hanging down
                          the drop with planks still lashed to it, an axe left in the post.
  site_old_ones_door    - a door cut by the Old Ones into a granite face: jambs, a lintel carved with
                          rings, the door slab sealed; rune slabs set in an arc in front of it.
  site_scree_battlefield- the first war in a gully: a scree fan with colony kettle helmets and ork
                          cleavers sticking out of it, a snapped pike, a rotted shield boss, bones.
SWAMP  (black water, rotten timber, rust, lichen, peat, bone, reed thatch)
  site_mission_chapel   - the colony's MISSION chapel at the swamp edge, listing into the peat: roof
                          gone but a few rafters, black water inside, the bell-cote EMPTY (a frayed
                          rope end under the yoke), the stone cross fallen; on the lectern in the
                          water the drowned book - Anselm's last page - and a loose sheet with the
                          SKETCH OF THE BELL, its inscription band drawn under the shoulder.
  site_ork_barrows      - an ork burial ground: long peat mounds, the old ones grassed over, two
                          FRESH ones black and soft; grave posts hung with tusks and bone charms,
                          bowls of fish, a cleaver laid on a fresh grave, a ring-carved post.
  site_eel_weir         - an ork eel weir: a V of wattle on stakes running out into the water,
                          funnel traps at its mouth, a drying rack of eels on the bank.
  site_colony_causeway  - the colony's plank causeway on piles, running out from the bank and ENDING
                          in open water: the last piles leaning, planks broken off and floating, a
                          rusted lantern still on its post.
  site_peat_cutting     - a peat cutting: the stepped cut face of a peat bank, black water in the
                          trench, rickles of drying peat, two slanes stuck in the bank, a sledge.

Real scale (hero ~1.8u), authored in game coordinates through geo.py (base y=0, contact parts run
below 0; the water-side scenes face local -Z toward the water). Materials by name: the kit's s_* sets
plus this script's own (wild_set.sh): s_granite, s_slate, s_chapel, s_peat, s_rotwood, s_rust, and
`bogwater` (untextured glossy black water, colour = vertex colour).

    blender -b --factory-startup --python tools/blender_forest/wild_sites.py
"""
import json
import math
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
from mathutils import Matrix, Quaternion, Vector  # noqa: E402
from common import OUT, clear_scene, export_glb  # noqa: E402
from geo import G, frustum, quat_x, quat_y, quat_z, sheet  # noqa: E402
from meshkit import Builder  # noqa: E402
import wayside_models as W  # noqa: E402
from wayside_models import (M_BARK, M_PLANK, M_STONE, M_HIDE, M_THATCH, M_CLOTH, M_IRON, M_ROCK, M_EARTH,  # noqa: E402
                            V, beam, board, bounds, lashing, lbox, mix, mound, pole, rock_col, scale, slab,
                            smooth_mesh, smoothstep, stone, tube, Noise)
import stories_cold as SC  # noqa: E402
from stories_cold import disc, dome  # noqa: E402

M_GRANITE = len(SC.MATS)
M_SLATE = M_GRANITE + 1
M_CHAPEL = M_GRANITE + 2
M_PEAT = M_GRANITE + 3
M_ROT = M_GRANITE + 4
M_RUST = M_GRANITE + 5
M_WATER = M_GRANITE + 6
M_PAPER = M_GRANITE + 7
M_RUBBLE = M_GRANITE + 8
M_SHINGLE = M_GRANITE + 9
M_CARDS = M_GRANITE + 10
MATS = SC.MATS + ["s_granite", "s_slate", "s_chapel", "s_peat", "s_rotwood", "s_rust", "bogwater", "s_plaster",
                  "s_rubble", "s_shingle", "swamp_cards"]
# swamp_cards atlas cells (swamp_flora.py CELLS -> scell): u0, v0, u1, v1.
UV_CATTAIL = (0.75, 0.5, 1.0, 1.0)
UV_LILY = (0.75, 0.0, 1.0, 0.5)
# weathered_planks: ~10 boards across the tile -> beams sample inside one board.
W.BOARD_CENTRES[M_ROT] = [k * 0.1 + 0.05 for k in range(10)]

ROPE = (0.78, 0.66, 0.46)
BLACK_IRON = (0.1, 0.095, 0.09)
OCHRE = (0.62, 0.2, 0.1)
IVORY = (0.86, 0.8, 0.66)
BONE = (0.8, 0.76, 0.66)
PARCH = (1.0, 0.9, 0.7)
INK = (0.14, 0.11, 0.09)
ROT_WOOD = (0.95, 0.95, 0.9)
WATER = (0.035, 0.045, 0.03)


# ─────────────────────────────────────────────────────────────── helpers
class TG(G):
    """A G that transforms everything drawn through it (a tilted / listing structure)."""

    def __init__(self, g, rot, off=(0, 0, 0)):
        super().__init__(g.b)
        self.rot = rot
        self.off = Vector(off)

    def poly(self, pts, uvs, nrms, cols, mat):
        G.poly(self, [self.rot @ Vector(p) + self.off for p in pts], uvs, [self.rot @ Vector(n) for n in nrms], cols, mat)


def rot_beam(g, pts, w, h, rng, col=ROT_WOOD, jag=(0.0, 0.0), col_fn=None, up=(0, 1, 0)):
    """A rotting timber in s_rotwood: one board of the scan per face, grain along the member."""
    beam(g, pts, w, h, up=up, mat=M_ROT, col=col, mode="plank", tile=max(w, h) / 0.075, rng=rng, jag=jag,
         col_fn=col_fn, chamfer=0.22, rough=0.06)


def damp_wood(base=ROT_WOOD, wet=0.45, green=0.25):
    """Timber tint along a member: black-green and wet at the low end, grey-dry higher up."""
    def f(t):
        k = smoothstep(0.0, 0.45, t)
        c = mix(scale((0.55, 0.62, 0.42), wet), base, k)
        return mix(c, scale(base, 0.8), green * (1 - k) * 0.3)
    return f


def stone_fn(base, rng, moss=0.0, damp_h=0.5, lichen=(0.78, 0.8, 0.62), moss_col=(0.42, 0.5, 0.22), var=0.14,
             ochre=None, y0=0.0):
    """Masonry / rock tint: damp-dark toward the ground, moss on up-facing faces, pale lichen blotches
    on the rest; `ochre(p, n) -> 0..1` paints red ochre over it."""
    nz = Noise(rng, 4, 2.4)

    def f(p, n):
        k = 0.55 + 0.45 * smoothstep(y0 - 0.1, y0 + damp_h, p.y)
        c = scale(base, k * (1.0 + var * nz(p * 2.0)))
        lich = smoothstep(0.35, 0.75, nz(p * 4.3 + Vector((3.0, 1.0, 2.0)))) * 0.55
        c = mix(c, scale(lichen, k), lich)
        m = moss * (smoothstep(0.2, 0.8, n.y) + 0.35 * (1 - smoothstep(y0, y0 + 0.6, p.y))) * (0.6 + 0.4 * nz(p * 6.0))
        c = mix(c, scale(moss_col, k), max(0.0, min(m, 1.0)))
        if ochre is not None:
            c = mix(c, OCHRE, ochre(p, n))
        return c
    return f


def panel(g, a, b, y0, top, thick, mat, col_fn, tile=1.6, steps=12, inward=None):
    """A solid wall along ground segment a->b (game x, z), `thick` deep, from y0 up to the ragged crown
    `top(s)` (s = 0..1 along it). Front / back / crown / end faces; masonry UVs run level."""
    a, b = Vector((a[0], 0, a[1])), Vector((b[0], 0, b[1]))
    t = (b - a)
    L = t.length
    t.normalize()
    n = Vector((0, 1, 0)).cross(t).normalized()  # wall normal (left of a->b)
    hw = thick / 2
    cols = []
    for i in range(steps + 1):
        s = i / steps
        p = a.lerp(b, s)
        cols.append((p, top(s), s * L))
    for i in range(steps):
        (p0, h0, u0), (p1, h1, u1) = cols[i], cols[i + 1]
        for side in (1, -1):
            o = n * hw * side
            q = [p0 + o + V(0, y0, 0), p1 + o + V(0, y0, 0), p1 + o + V(0, h1, 0), p0 + o + V(0, h0, 0)]
            uv = [(u0 / tile, y0 / tile), (u1 / tile, y0 / tile), (u1 / tile, h1 / tile), (u0 / tile, h0 / tile)]
            nn = n * side
            if (q[1] - q[0]).cross(q[3] - q[0]).dot(nn) < 0:
                q, uv = q[::-1], uv[::-1]
            g.poly(q, uv, [nn] * 4, [col_fn(x, nn) for x in q], mat)
        # crown
        q = [p0 + n * hw + V(0, h0, 0), p1 + n * hw + V(0, h1, 0), p1 - n * hw + V(0, h1, 0), p0 - n * hw + V(0, h0, 0)]
        fn = (q[1] - q[0]).cross(q[3] - q[0])
        up = fn.normalized() if fn.y > 0 else -fn.normalized()
        if fn.y < 0:
            q = q[::-1]
        g.poly(q, [(x.x / tile, x.z / tile) for x in q], [up] * 4, [col_fn(x, up) for x in q], mat)
    for (p, h, _), sgn in ((cols[0], -1), (cols[-1], 1)):
        nn = t * sgn
        q = [p - n * hw + V(0, y0, 0), p + n * hw + V(0, y0, 0), p + n * hw + V(0, h, 0), p - n * hw + V(0, h, 0)]
        if (q[1] - q[0]).cross(q[3] - q[0]).dot(nn) < 0:
            q = q[::-1]
        g.poly(q, [((x - p).dot(n) / tile, x.y / tile) for x in q], [nn] * 4, [col_fn(x, nn) for x in q], mat)


def masonry(g, a, b, y0, top, thick, mat, col_fn, rng, course=0.22, lmin=0.28, lmax=0.55, sides=(1, -1),
            tile=1.6, steps=12, missing=0.04, mortar=0.42, depth=0.16):
    """A wall built stone by stone: a recessed core (dark mortar / rubble fill, `panel`) with a skin of
    individual rough-dressed stones laid in courses on each face in `sides`, joints staggered, every
    stone chipped (`slab` with a little noise) and tinted on its own; the crown follows `top(s)`
    stone by stone (a stone whose top would stand above it is left out) and a few go missing."""
    A, B = Vector((a[0], 0, a[1])), Vector((b[0], 0, b[1]))
    t = B - A
    L = t.length
    t.normalize()
    n = Vector((0, 1, 0)).cross(t).normalized()
    yaw = math.atan2(-t.z, t.x)
    core = lambda p, nn: scale(col_fn(p, nn), mortar)  # noqa: E731
    panel(g, a, b, y0, lambda s_: top(s_) - 0.06, thick - 2 * depth + 0.06, mat, core, tile=tile, steps=steps)
    for side in sides:
        y = y0
        row = 0
        while True:
            h = course * rng.uniform(0.8, 1.2)
            u = -rng.uniform(0.0, lmax) if row % 2 else 0.0
            while u < L:
                ln = rng.uniform(lmin, lmax)
                u0, u1 = max(u, 0.0), min(u + ln, L)
                u = u + ln
                if u1 - u0 < 0.08:
                    continue
                sc = (u0 + u1) / 2 / L
                if y + h > top(sc) + 0.02 or rng.uniform() < missing:
                    continue
                k = rng.uniform(0.82, 1.15)
                c = A + t * ((u0 + u1) / 2) + n * side * (thick / 2 - depth / 2) + V(0, y + h / 2, 0)
                slab(g, tuple(c), (u1 - u0 - 0.025, h - 0.025, depth + rng.uniform(-0.02, 0.03)),
                     quat_y(yaw) @ quat_z(rng.uniform(-0.03, 0.03)), rng, mat=mat, res=(2, 1, 1), round_r=0.03,
                     rough=0.05, col_fn=lambda p, nn, k=k: scale(col_fn(p, nn), k), tile=tile)
            y += h
            row += 1
            if y > max(top(i / 8) for i in range(9)):
                break


def water_disc(g, centre, rx, rz, y, rng, seg=22, col=WATER):
    """A flat sheet of still black water (bogwater), slightly irregular outline."""
    nz = Noise(rng, 3, 1.5)
    c = Vector(centre)
    ring = []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        e = 1.0 + 0.12 * nz(Vector((math.cos(a), 0.0, math.sin(a))) * 1.7)
        ring.append(Vector((c.x + math.cos(a) * rx * e, y, c.z + math.sin(a) * rz * e)))
    ctr = Vector((c.x, y, c.z))
    up = Vector((0, 1, 0))
    for i in range(seg):
        tri = [ctr, ring[(i + 1) % seg], ring[i]]
        if (tri[1] - tri[0]).cross(tri[2] - tri[0]).y < 0:
            tri = tri[::-1]
        g.poly(tri, [(p.x, p.z) for p in tri], [up] * 3, [col] * 3, M_WATER)


def water_quad(g, pts, y, col=WATER):
    q = [Vector((p[0], y, p[1])) for p in pts]
    if (q[1] - q[0]).cross(q[2] - q[0]).y < 0:
        q = q[::-1]
    g.poly(q, [(p.x, p.z) for p in q], [V(0, 1, 0)] * len(q), [col] * len(q), M_WATER)


def peat_fn(rng, base=(1.0, 0.95, 0.9), wet=0.6, grass=0.0, grass_col=(0.62, 0.66, 0.36)):
    nz = Noise(rng, 4, 1.8)

    def f(p, n):
        k = 1.0 + 0.15 * nz(p * 2.0)
        c = scale(base, k * (wet + (1 - wet) * smoothstep(-0.05, 0.35, p.y)))
        g_ = grass * smoothstep(0.4, 0.9, n.y) * (0.6 + 0.4 * nz(p * 3.0 + Vector((2, 0, 1))))
        return mix(c, grass_col, max(0.0, min(g_, 1.0)))
    return f


def sedge(g, c, rng, n=9, h=0.7, col=(0.4, 0.42, 0.2)):
    """A tuft of sedge / rush blades (thin tapered tubes, bent over at the tips)."""
    c = Vector(c)
    for _ in range(n):
        a = rng.uniform(0, 2 * math.pi)
        lean = rng.uniform(0.1, 0.45)
        hh = h * rng.uniform(0.6, 1.1)
        d = V(math.cos(a), 0, math.sin(a))
        base = c + d * rng.uniform(0, 0.08)
        pts = [base, base + d * lean * hh * 0.25 + V(0, hh * 0.55, 0), base + d * lean * hh * 0.8 + V(0, hh * 0.92, 0),
               base + d * lean * hh * 1.25 + V(0, hh * 0.98, 0)]
        tube(g, pts, [0.009, 0.007, 0.004, 0.0015], 3, M_THATCH, scale(col, rng.uniform(0.7, 1.15)), tile=0.4, cap=False)


def rope(g, pts, r=0.018, col=ROPE):
    tube(g, pts, [r] * len(pts), 5, M_CLOTH, col, tile=0.12, cap=True)


def catenary(p0, p1, sag, n=10):
    p0, p1 = Vector(p0), Vector(p1)
    return [p0.lerp(p1, i / n) - V(0, sag * 4 * (i / n) * (1 - i / n), 0) for i in range(n + 1)]


def chain(g, p0, p1, link=0.09, r=0.012, col=BLACK_IRON):
    """A hanging chain of alternating oval links (s_iron)."""
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    L = d.length
    t = d.normalized()
    side = t.orthogonal().normalized()
    n = max(2, int(L / (link * 0.8)))
    for i in range(n):
        c = p0 + t * (L * (i + 0.5) / n)
        s = side if i % 2 == 0 else t.cross(side).normalized()
        ring = [c + t * math.cos(a) * link * 0.55 + s * math.sin(a) * link * 0.3 for a in np.linspace(0, 2 * math.pi, 9)]
        tube(g, ring, [r] * 9, 4, M_IRON, col, tile=0.1, cap=False)


def tusk(g, base, d, rng, length=0.32, r=0.035, col=IVORY):
    base, d = Vector(base), Vector(d).normalized()
    side = d.cross(V(0, 1, 0))
    if side.length < 1e-3:
        side = V(1, 0, 0)
    side.normalize()
    curl = d.cross(side).normalized()
    pts = [base + d * length * f + curl * length * 0.35 * f * f for f in (0, 0.33, 0.66, 1.0)]
    tube(g, pts, [r, r * 0.8, r * 0.5, r * 0.08], 6, M_STONE, col, tile=0.2)


def skull(g, c, rot, rng, s=1.0, col=BONE):
    """A boar skull: a long tapered snout block, the cranium dome, two tusks curling up."""
    c = Vector(c)
    stone(g, tuple(c), (0.13 * s, 0.1 * s, 0.12 * s), rng, mat=M_STONE, detail=1, rough=0.06, cuts=1, rot=rot,
          col_fn=lambda p, n: scale(col, 0.75 + 0.25 * smoothstep(-0.5, 0.8, n.y)), tile=0.25)
    sn = c + rot @ V(0, -0.02 * s, -0.17 * s)
    tube(g, [c + rot @ V(0, 0, -0.06 * s), sn, sn + rot @ V(0, -0.02 * s, -0.08 * s)],
         [0.07 * s, 0.05 * s, 0.035 * s], 7, M_STONE, scale(col, 0.9), tile=0.2)
    for sx in (-1, 1):
        tusk(g, sn + rot @ V(sx * 0.04 * s, -0.01, 0.02), rot @ V(sx * 0.6, 0.6, -0.3), rng, length=0.14 * s, r=0.016 * s)
    # dark eye sockets
    for sx in (-1, 1):
        stone(g, tuple(c + rot @ V(sx * 0.085 * s, 0.03 * s, -0.05 * s)), (0.028 * s, 0.024 * s, 0.024 * s), rng,
              mat=M_STONE, detail=0, rough=0.05, cuts=0, col_fn=lambda p, n: (0.12, 0.1, 0.08), tile=0.2)


def bowl(g, c, r, rng, col=(0.62, 0.42, 0.3), fill=None):
    """A clay bowl (s_earth), optionally filled with something (fill colour) at the brim."""
    c = Vector(c)
    frustum(g, r * 0.55, r, c.y, r * 0.55, 10, M_EARTH, col, tile=0.3, centre=(c.x, 0, c.z))
    if fill:
        stone(g, (c.x, c.y + r * 0.45, c.z), (r * 0.85, r * 0.18, r * 0.85), rng, mat=M_EARTH, detail=1, rough=0.1,
              cuts=0, col_fn=lambda p, n: fill, tile=0.2)


def fish(g, c, d, rng, s=1.0):
    c, d = Vector(c), Vector(d).normalized()
    pts = [c - d * 0.16 * s, c - d * 0.05 * s, c + d * 0.08 * s, c + d * 0.17 * s]
    tube(g, pts, [0.008 * s, 0.04 * s, 0.035 * s, 0.006 * s], 6, M_HIDE, (0.55, 0.58, 0.55), tile=0.15)
    tail = c - d * 0.17 * s
    side = d.cross(V(0, 1, 0)).normalized()
    g.flat([tail, tail - d * 0.07 * s + side * 0.04 * s + V(0, 0.01, 0), tail - d * 0.07 * s - side * 0.04 * s + V(0, 0.01, 0)],
           M_HIDE, (0.4, 0.42, 0.38), 0.2)


def ink_lines(u, v, rows, v0, v1, fade=1.0, seed=0.0):
    """Hand-written lines (dark dashes in rows) inside v0..v1 of a page; `fade` < 1 = water-washed."""
    if not (v0 < v < v1) or not (0.1 < u < 0.9):
        return 0.0
    f = (v - v0) / (v1 - v0) * rows
    row = int(f)
    in_line = abs(f - row - 0.5) < 0.17
    word = math.sin(u * 61.0 + row * 2.7 + seed) > -0.35
    end = u < 0.9 - 0.25 * ((row * 37 + int(seed * 10)) % 7) / 7.0 * (row == rows - 1)
    return fade if (in_line and word and end) else 0.0


def page(g, c, rot, w, h, ink_fn, n=(14, 18), curl=0.0, wet=0.0, stain_seed=0.0):
    """A sheet of parchment (s_plaster, parchment tint) w x h in its local XZ plane, its writing /
    drawing painted by `ink_fn(u, v) -> 0..1` into the vertex colours; `wet` adds tide-mark stains."""
    c = Vector(c)
    grid = []
    for i in range(n[0] + 1):
        row = []
        for j in range(n[1] + 1):
            u, v = i / n[0], j / n[1]
            x, z = (u - 0.5) * w, (v - 0.5) * h
            y = curl * ((2 * u - 1) ** 2 * 0.6 + (2 * v - 1) ** 4 * 0.4) + 0.004 * math.sin(u * 13 + v * 7)
            row.append(c + rot @ V(x, y, z))
        grid.append(row)

    def col(u, v):
        base = PARCH
        if wet:
            s = 0.5 + 0.5 * math.sin(u * 9.0 + stain_seed) * math.cos(v * 7.0 - stain_seed * 0.7)
            base = mix(base, (0.72, 0.56, 0.36), wet * smoothstep(0.55, 0.85, s))
            edge = min(u, 1 - u, v, 1 - v)
            base = mix(base, (0.55, 0.42, 0.28), wet * (1 - smoothstep(0.0, 0.08, edge)))
        return mix(base, INK, ink_fn(u, v))
    sheet(g, grid, M_PAPER, col, tile=0.3, double=True)


def bell_sketch(u, v):
    """The bell drawn on Anselm's loose sheet: outline, lip, crown loop, and the INSCRIPTION band
    (a row of tiny letters) under the shoulder - the same band the fort's bell carries. The
    middle of the sheet is washed out by the water; two lines of writing survive top and bottom."""
    x = u - 0.5
    ink = 0.0
    if 0.3 < v < 0.72:
        f = (0.72 - v) / 0.42
        hw = 0.1 + 0.19 * f ** 1.8
        if abs(abs(x) - hw) < 0.014:
            ink = 1.0
        # inscription band: a double rule with letters between
        if abs(x) < hw - 0.02 and (abs(v - 0.62) < 0.005 or abs(v - 0.585) < 0.005):
            ink = 0.9
        if abs(x) < hw - 0.03 and 0.592 < v < 0.613 and math.sin(u * 140.0) > 0.1:
            ink = 0.85
    if abs(v - 0.3) < 0.008 and abs(x) < 0.3:
        ink = 1.0  # the lip
    if 0.72 <= v < 0.78 and abs(math.hypot(x, v - 0.735) - 0.035) < 0.01:
        ink = 1.0  # crown loop
    ink = max(ink, ink_lines(u, v, 2, 0.84, 0.95, 0.9, 1.3), ink_lines(u, v, 2, 0.06, 0.18, 0.75, 4.1))
    return ink


# ─────────────────────────────────────────────────────────────── SWAMP
def basis_q(xa, ya, za):
    """Quaternion of the frame whose local x / y / z axes are xa / ya / za (orthonormal)."""
    return Matrix((tuple(xa), tuple(ya), tuple(za))).transposed().to_quaternion()


def lily_raft(g, c, size, y, rng):
    """Lily pads + duckweed floating on the water (the swamp flora's card, seen from above)."""
    c = Vector(c)
    u0, v0, u1, v1 = UV_LILY
    for i in range(2):
        a = rng.uniform(0, 2 * math.pi)
        s_ = size * (1.0 if i == 0 else 0.65)
        o = c + V(rng.normal() * size * 0.25, 0.004 * i, rng.normal() * size * 0.25)
        ax, az = V(math.cos(a), 0, math.sin(a)) * s_ * 0.5, V(-math.sin(a), 0, math.cos(a)) * s_ * 0.5
        q = [o - ax - az, o + ax - az, o + ax + az, o - ax + az]
        uv = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
        if (q[1] - q[0]).cross(q[3] - q[0]).y < 0:
            q, uv = q[::-1], uv[::-1]
        q = [V(p.x, y + 0.004 * i, p.z) for p in q]
        g.poly(q, uv, [V(0, 1, 0)] * 4, [(0.9, 0.95, 0.85)] * 4, M_CARDS)


def cattails(g, c, rng, size=1.2, n=3, tint=(0.95, 1.0, 0.9)):
    """A clump of cattails + sedge: crossed upright cards from the swamp flora atlas."""
    c = Vector(c)
    u0, v0, u1, v1 = UV_CATTAIL
    a0 = rng.uniform(0, math.pi)
    for i in range(n):
        a = a0 + i * math.pi / n + rng.uniform(-0.2, 0.2)
        w, h = size * rng.uniform(0.85, 1.05), size * rng.uniform(0.85, 1.1)
        side = V(math.cos(a), 0, math.sin(a)) * w * 0.5
        fn = V(-math.sin(a), 0, math.cos(a))
        lean = fn * h * 0.3 * rng.uniform(0.3, 1.0) * (1 if i % 2 else -1)
        q = [c - side - V(0, 0.05, 0), c + side - V(0, 0.05, 0), c + side + V(0, h, 0) + lean, c - side + V(0, h, 0) + lean]
        cb = scale(tint, 0.55)
        nn = (fn * 0.3 + V(0, 0.7, 0)).normalized()
        g.poly(q, [(u0, v0), (u1, v0), (u1, v1), (u0, v1)], [nn] * 4, [cb, cb, tint, tint], M_CARDS)


def gravestone(g, c, rot, rng, col_fn, w=0.5, h=1.1, t=0.15, cross=True):
    """A headstone of the colony graveyard: a rough slab with a narrower rounded cap and an incised
    cross on its face, drawn upright about `c` (its foot) then turned by `rot`."""
    c = Vector(c)
    slab(g, tuple(c + rot @ V(0, h * 0.45, 0)), (w, h * 0.9, t), rot, rng, mat=M_RUBBLE, res=(2, 4, 1), round_r=0.04,
         rough=0.03, col_fn=col_fn, tile=0.8, taper=0.06)
    slab(g, tuple(c + rot @ V(0, h * 0.92, 0)), (w * 0.72, h * 0.12, t * 0.95), rot, rng, mat=M_RUBBLE, res=(2, 1, 1),
         round_r=0.05, rough=0.03, col_fn=col_fn, tile=0.8)
    if cross:
        f = c + rot @ V(0, h * 0.68, -t / 2 - 0.004)
        lbox(g, tuple(f), (0.04, h * 0.32, 0.012), rot, M_RUBBLE, (0.2, 0.21, 0.18), tile=0.3)
        lbox(g, tuple(f + rot @ V(0, h * 0.06, 0)), (w * 0.42, 0.04, 0.012), rot, M_RUBBLE, (0.2, 0.21, 0.18), tile=0.3)


def site_mission_chapel(rng):
    """Footprint r <= 4.4. Masses: the nave walls (local 0, 0.2, 2.0 x 3.0 box). The colony's
    MISSION chapel, DROWNED: a pale lichen-crusted fieldstone nave 3.6 x 6 listing ~10 deg to its
    right and ~5 deg forward, sunk into black bog water up to its window sills (the door arch half
    under). The front gable still carries the EMPTY bell-cote (the iron yoke in the arch, a frayed
    rope end). Half the roof is gone - bare rafters against the sky on the right - the other half
    sags in a belly of moss-grey shingles with holes in it. Through the gap: the lectern on its
    stone step standing out of the water with the drowned book and the loose SKETCH OF THE BELL.
    Around it: duckweed rafts, reeds, the colony's headstones tilting out of the water, a fallen
    cross-slab, peat hummocks fringing the pool."""
    b = Builder()
    base = G(b)
    WL = 0.04  # the water surface (untilted, base coords)
    tilt = quat_x(-0.08) @ quat_z(-0.17)
    off = Vector((0.15, -1.15, 0.15))
    g = TG(base, tilt, off)
    rm = tilt.to_matrix()

    def above_water(p):  # local (tilted) point -> height above the water line
        return (rm @ Vector(p)).y + off.y - WL

    lich = stone_fn((0.93, 0.93, 0.88), rng, moss=0.18, damp_h=1.6, y0=0.4, lichen=(1.0, 1.0, 0.86),
                    moss_col=(0.5, 0.56, 0.3), var=0.12)

    def stn(p, n):
        """Pale lichen above, a dark green-black tide band just above the water, slime below it."""
        c = lich(p, n)
        d = above_water(p)
        c = mix(c, (0.3, 0.33, 0.22), 1 - smoothstep(0.0, 0.32, d))
        return mix(c, (0.62, 0.64, 0.5), 0.35 * smoothstep(0.35, 0.5, d) * (1 - smoothstep(0.5, 0.9, d)))

    XW, Z0, Z1, T = 1.8, -3.0, 3.0, 0.45
    jag = lambda s, k: 0.18 * math.sin(s * 19.0 + k) * math.sin(s * 7.1 + 2 * k)  # noqa: E731
    Y0 = 0.25  # walls start here (local) - everything lower is deep under the water
    # Side walls: the lower walls (to the sills, 1.25) run the whole length; window piers above.
    # Left (-x) wall stands to the eaves under the surviving roof half; the right one is broken.
    for sx, k in ((-1, 0.0), (1, 1.7)):
        x = sx * (XW - T / 2)
        masonry(g, (x, Z0 + T), (x, Z1 - T), Y0, lambda s, k=k, sx=sx: 1.25 - (0.5 if sx > 0 else 0.25) *
                smoothstep(0.7, 1.0, s) + jag(s, k) * 0.6, T, M_RUBBLE, stn, rng, tile=2.0, steps=14)
        piers = ((Z0 + T, -1.9, 3.1), (-1.45, -0.2, 3.05), (0.25, 1.15, 3.0), (1.6, Z1 - T, 2.4)) if sx < 0 else \
                ((Z0 + T, -1.9, 3.1), (-1.45, -0.2, 2.55), (0.25, 1.1, 1.9))
        for z0, z1, top in piers:
            flat_top = sx < 0 and top > 2.9
            masonry(g, (x, z0), (x, z1), 1.25, lambda s, top=top, k=k, ft=flat_top: top + (0.0 if ft else jag(s, k + 3.0) - 0.25 * s),
                    T, M_RUBBLE, stn, rng, tile=2.0, steps=5)
        # Lintels over the lancet windows (the left wall keeps all three, the right only the first).
        for zc in ((-1.67, -0.0, 1.38) if sx < 0 else (-1.67,)):
            slab(g, (x, 2.62, zc + (0.02 if zc == -0.0 else 0)), (T + 0.04, 0.22, 0.42 if zc > 1 else 0.7), quat_y(0.0), rng,
                 mat=M_RUBBLE, res=(2, 1, 3), round_r=0.03, rough=0.03, col_fn=stn, tile=1.0)
        # Sill stones.
        for zc in (-1.67, 0.02, 1.38):
            slab(g, (x + sx * 0.05, 1.27, zc), (T + 0.14, 0.08, 0.5), quat_y(0.0), rng, mat=M_RUBBLE, res=(2, 1, 2),
                 round_r=0.02, rough=0.03, col_fn=stn, tile=1.0)
    # Back wall: a ragged stump (sticks out of the water - the chapel lists forward).
    masonry(g, (-XW, Z1 - T / 2), (XW, Z1 - T / 2), Y0, lambda s: 1.5 + 0.9 * (1 - s) + 0.3 * math.sin(s * 3.0) + jag(s, 5.0),
            T, M_RUBBLE, stn, rng, tile=2.0, steps=12)
    # Front gable with the door (gap |x| < 0.55, up to 2.1) and the gable peak at 4.4.
    zf = Z0 + T / 2
    gable = lambda x: 3.2 + 1.2 * (1.0 - abs(x) / XW)  # noqa: E731
    masonry(g, (-XW, zf), (-0.55, zf), Y0, lambda s: gable(-XW + s * (XW - 0.55)), T, M_RUBBLE, stn, rng, tile=2.0, steps=6)
    masonry(g, (0.55, zf), (XW, zf), Y0, lambda s: gable(0.55 + s * (XW - 0.55)), T, M_RUBBLE, stn, rng, tile=2.0, steps=6)
    masonry(g, (-0.55, zf), (0.55, zf), 2.35, lambda s: gable(-0.55 + s * 1.1), T, M_RUBBLE, stn, rng, tile=2.0, steps=4)
    # Door arch voussoirs + jamb quoins (the arch springs a hand above the water).
    ac, ar = V(0.0, 1.95, zf), 0.62
    for k in range(9):
        t = math.pi * (k + 0.5) / 9
        p = ac + V(math.cos(t) * ar, math.sin(t) * ar * 0.6, 0.0)
        slab(g, tuple(p), (0.2, 0.17, T + 0.06), quat_z(t - math.pi / 2), rng, mat=M_RUBBLE, res=(2, 1, 2), round_r=0.025,
             rough=0.03, col_fn=stn, tile=0.7)
    for sx in (-1, 1):
        for k in range(4):
            slab(g, (sx * 0.66, 1.0 + k * 0.26, zf - 0.02), (0.24 if k % 2 else 0.32, 0.24, T + 0.08), quat_y(0.0), rng,
                 mat=M_RUBBLE, res=(2, 1, 2), round_r=0.03, rough=0.03, col_fn=stn, tile=0.7)
    # Coping stones up the gable rakes.
    for sx in (-1, 1):
        for k in range(6):
            f = (k + 0.5) / 6
            x = sx * XW * (1 - f)
            slab(g, (x, gable(x) + 0.08, zf), (0.36, 0.14, T + 0.12), quat_z(-sx * math.atan2(1.2, XW)), rng, mat=M_RUBBLE,
                 res=(2, 1, 2), round_r=0.03, rough=0.03, col_fn=stn, tile=0.8)
    # The bell-cote on the apex: two piers + an arch + a capstone, EMPTY. The iron yoke still spans
    # the opening, a frayed rope end hanging from it.
    for x in (-0.42, 0.42):
        slab(g, (x, 4.85, zf), (0.24, 1.1, T), quat_y(0.0), rng, mat=M_RUBBLE, res=(2, 4, 2), round_r=0.03, rough=0.03,
             col_fn=stn, tile=0.8)
    bc, br = V(0.0, 5.38, zf), 0.42
    for k in range(7):
        t = math.pi * (k + 0.5) / 7
        p = bc + V(math.cos(t) * br, math.sin(t) * br * 0.7, 0)
        slab(g, tuple(p), (0.17, 0.15, T), quat_z(t - math.pi / 2), rng, mat=M_RUBBLE, res=(2, 1, 2), round_r=0.02,
             rough=0.03, col_fn=stn, tile=0.6)
    slab(g, (0.0, 5.82, zf), (1.2, 0.14, T + 0.1), quat_y(0.0), rng, mat=M_RUBBLE, res=(4, 1, 2), round_r=0.03,
         rough=0.03, col_fn=stn, tile=0.8)
    tube(g, [V(-0.32, 5.2, zf), V(0.32, 5.2, zf)], [0.035, 0.035], 6, M_RUST, (0.8, 0.75, 0.7), tile=0.2)
    for x in (-0.07, 0.07):
        tube(g, [V(x, 5.2, zf - 0.03), V(x * 1.3, 5.05, zf - 0.03), V(x * 1.3, 4.98, zf)], [0.02, 0.018, 0.016], 5, M_RUST,
             (0.75, 0.7, 0.65), tile=0.15)
    rope(g, [V(0.0, 5.2, zf + 0.02), V(0.01, 4.95, zf + 0.03), V(0.03, 4.62, zf + 0.04), V(0.05, 4.48, zf + 0.06)], 0.016,
         (0.5, 0.44, 0.33))
    for k in range(4):
        a = k * 1.6
        rope(g, [V(0.05, 4.5, zf + 0.06), V(0.05 + math.cos(a) * 0.035, 4.36 - 0.03 * k, zf + 0.06 + math.sin(a) * 0.035)],
             0.005, (0.5, 0.44, 0.33))
    # ── Roof. Ridge 4.25, eaves 3.05. The ridge beam sags and is snapped behind the last pair.
    RZ0, RZ1 = Z0 + 0.35, 1.55
    sag = lambda z: 0.1 + 0.32 * math.sin(math.pi * max(0.0, min(1.0, (z - RZ0) / (RZ1 - RZ0))))  # noqa: E731
    ridge = lambda z: V(0, 4.25 - 0.55 * sag(z) + 0.05, z)  # noqa: E731
    rot_beam(g, [ridge(Z0 + 0.15), ridge(-1.4), ridge(0.0), ridge(RZ1), ridge(RZ1) + V(0.05, -0.5, 0.55),
                 V(0.1, 1.1, 2.3)], 0.16, 0.15, rng, jag=(0.0, 0.2), col_fn=damp_wood(wet=0.8))
    zs = [RZ0 + i * (RZ1 - RZ0) / 6 for i in range(7)]
    for i, z in enumerate(zs):
        top = ridge(z) + V(0, -0.05, 0)
        # left half: rafters bowed with the sag of the roof
        foot = V(-(XW - 0.05), 3.05, z)
        mid = foot.lerp(top, 0.5) + V(0, -sag(z) * 0.6, 0)
        rot_beam(g, [foot + V(-0.25, -0.18, 0), foot, mid, top], 0.12, 0.1, rng, col_fn=damp_wood(wet=0.75))
        # right half: bare rafters against the sky, some snapped off short, one fallen in
        foot = V(XW - 0.05, 3.05 if z < -0.6 else 2.55 - 0.15 * i, z)
        if i in (3, 5):
            rot_beam(g, [top, top.lerp(foot, 0.38 + 0.12 * (i == 5))], 0.12, 0.1, rng, jag=(0.0, 0.2),
                     col_fn=damp_wood(wet=0.75))
        elif i == 4:
            rot_beam(g, [V(0.6, 0.75, z - 0.4), V(1.35, 2.35, z + 0.2)], 0.12, 0.1, rng, jag=(0.15, 0.15),
                     col_fn=damp_wood(wet=0.9))
        else:
            rot_beam(g, [top, foot, foot + V(0.25, -0.18, 0)], 0.12, 0.1, rng, col_fn=damp_wood(wet=0.75))
    # Left half: battens and a sagging skin of shingles, moss-grey, with holes; ragged at the back.
    def roof_pt(f, z):
        foot = V(-(XW + 0.15), 2.97, z)
        top = ridge(z)
        return foot.lerp(top, f) + V(0, -sag(z) * 0.6 * math.sin(math.pi * f) * (1.0 if f < 0.5 else 0.8), 0)
    Ls = (roof_pt(1.0, 0.0) - roof_pt(0.0, 0.0)).length
    for f in (0.12, 0.4, 0.68, 0.93):
        pts = [roof_pt(f, z) + V(0, 0.06, 0) for z in (RZ0 - 0.1, (RZ0 + RZ1) / 2, RZ1 + 0.1)]
        rot_beam(g, pts, 0.07, 0.04, rng, col_fn=damp_wood(wet=0.5))
    shg = Noise(rng, 3, 1.3)
    rows = int(Ls / 0.24)
    for r in range(rows):
        f0, f1 = r * 0.24 / Ls, (r * 0.24 + 0.4) / Ls
        z = RZ0 - 0.15 + (0.11 if r % 2 else 0.0)
        z_end = RZ1 + 0.2 - (0.9 * max(0.0, shg(V(r * 0.7, 0, 0))) if r > 2 else 0.0)
        while z < z_end:
            w = rng.uniform(0.17, 0.24)
            zc = z + w / 2
            z += w
            hole = (-0.45 < zc < 0.6 and 0.45 < f0 < 0.9) or rng.uniform() < 0.07
            if hole or f0 > 0.97:
                continue
            p0, p1 = roof_pt(f0, zc), roof_pt(min(f1, 1.02), zc)
            za = (p1 - p0).normalized()
            xa = V(0, 0, -1)
            ya = za.cross(xa).normalized()
            q = basis_q(xa, ya, za) @ quat_x(-0.07)
            c = (p0 + p1) / 2 + ya * (0.1 + 0.012 * (r % 2))
            k = rng.uniform(0.7, 1.0)
            m = max(0.0, min(1.0, 0.5 + shg(c * 1.8)))
            col = mix(scale((0.72, 0.74, 0.66), k), scale((0.52, 0.6, 0.32), k), 0.6 * m)
            lbox(g, tuple(c), (w - 0.015, 0.025, 0.42), q, M_SHINGLE, [scale(col, 0.75), None, col], tile=0.4, grain=2)
    # A drift of slipped shingles on the water inside and below the eaves.
    for k in range(14):
        p = V(rng.uniform(-1.3, 1.3), WL + 0.01, rng.uniform(-1.9, 1.9)) if k < 8 else \
            V(rng.uniform(-3.0, -2.3), WL + 0.01, rng.uniform(-2.0, 1.5))
        lbox(base, tuple(p), (0.2, 0.025, 0.4), quat_y(rng.uniform(0, 3)) @ quat_x(rng.uniform(-0.05, 0.05)), M_SHINGLE,
             scale((0.6, 0.62, 0.52), rng.uniform(0.7, 1.0)), tile=0.4, grain=2)
    # ── The lectern on the chancel step, out of the water under the open half of the roof:
    # the drowned book (swollen boards, its pages run with ink), the loose sketch of the bell.
    L0 = V(0.45, 0.0, 1.55)
    for k, (s, y) in enumerate(((1.1, 0.2), (0.75, 0.55))):
        slab(g, tuple(L0 + V(0, y, 0.15 * k)), (s, 0.36, s * 0.8), quat_y(0.05 * k), rng, mat=M_RUBBLE, res=(2, 1, 2),
             round_r=0.05, rough=0.03, col_fn=stn, tile=0.8)
    rot_beam(g, [L0 + V(0, 0.72, 0.1), L0 + V(0.0, 1.62, 0.1)], 0.12, 0.12, rng, col_fn=damp_wood(wet=0.4))
    for a in (0.0, 2.1, 4.2):
        rot_beam(g, [L0 + V(0, 0.95, 0.1), L0 + V(math.cos(a) * 0.3, 0.73, 0.1 + math.sin(a) * 0.3)], 0.06, 0.06, rng)
    top_rot = quat_y(math.pi) @ quat_x(-0.55)
    lc = L0 + V(0, 1.7, 0.12)
    lbox(g, tuple(lc), (0.62, 0.05, 0.46), top_rot, M_ROT, scale(ROT_WOOD, 0.8), tile=0.4)
    lbox(g, tuple(lc + top_rot @ V(0, 0.0, 0.25)), (0.62, 0.06, 0.04), top_rot, M_ROT, scale(ROT_WOOD, 0.7), tile=0.3)
    for sx in (-1, 1):
        bc_ = lc + top_rot @ V(sx * 0.14, 0.05, 0.0)
        lbox(g, tuple(bc_), (0.27, 0.04, 0.36), top_rot @ quat_z(sx * 0.08), M_HIDE, (0.3, 0.2, 0.14), tile=0.3)
        page(g, bc_ + top_rot @ V(0, 0.03, 0), top_rot @ quat_z(sx * 0.1), 0.25, 0.34,
             lambda u, v, s=sx: ink_lines(u, v, 9, 0.08, 0.92, 0.55, 2.0 + s), n=(8, 10), curl=0.02, wet=0.9,
             stain_seed=1.0 + sx)
    page(g, lc + top_rot @ V(0.05, 0.075, -0.04), top_rot @ quat_y(0.25), 0.26, 0.36, bell_sketch, n=(24, 32),
         curl=0.008, wet=0.7, stain_seed=2.4)
    # Pew backs breaking the surface (drawn tilted with the floor).
    for p0, p1 in (((-1.1, 1.05, -1.5), (0.35, 1.0, -1.4)), ((-1.15, 0.95, -0.4), (0.2, 1.05, -0.5))):
        board(g, V(*p0).lerp(V(*p1), 0.5), V(*p1) - V(*p0), V(0, 0.2, 1.0), (V(*p1) - V(*p0)).length, 0.28, 0.06,
              mat=M_ROT, col=scale(ROT_WOOD, 0.7), rng=rng, jag=(0.05, 0.1))
    # ── The pool: black water over the whole footprint, the chapel sunk in it.
    water_disc(base, (0.0, 0, 0.0), 4.0, 4.2, WL, rng, seg=32)
    # Peat hummocks fringing it (open toward the front so the water reads), grass and sedge on them.
    pf = peat_fn(rng, base=(0.6, 0.52, 0.4), wet=0.8, grass=1.7, grass_col=(0.42, 0.55, 0.22))
    for a, r, rx, rz, h in ((0.3, 3.9, 1.1, 0.8, 0.42), (1.0, 3.8, 1.0, 0.9, 0.38), (1.6, 4.0, 1.2, 0.8, 0.45),
                            (2.25, 3.8, 1.0, 0.9, 0.4), (2.9, 3.9, 1.1, 0.75, 0.36), (3.5, 4.0, 0.8, 0.7, 0.3),
                            (5.9, 4.0, 0.8, 0.7, 0.3)):
        c = (math.cos(a) * r, -0.15, math.sin(a) * r)
        mound(base, c, rx, rz, h, rng, mat=M_EARTH, col_fn=pf, tile=1.2, rings=5, seg=18, skirt=0.25, edge=0.2,
              power=0.6, rough=0.2)
        cattails(base, (c[0] * 0.92, -0.05, c[2] * 0.92), rng, size=rng.uniform(1.0, 1.35))
    # Lily pads and duckweed rafts outside and inside (caught against the walls).
    for c, sz in (((-2.6, 0, -2.6), 1.5), ((2.7, 0, -2.2), 1.3), ((3.1, 0, 1.2), 1.1), ((-3.0, 0, 1.6), 1.2),
                  ((1.2, 0, -3.9), 1.4), ((-1.0, 0, 0.6), 1.1), ((0.8, 0, -1.2), 0.9), ((-1.7, 0, -4.0), 1.0),
                  ((0.2, 0, -2.4), 0.8), ((-0.6, 0, 2.2), 0.9)):
        lily_raft(base, c, sz, WL + 0.006, rng)
    # The colony's headstones tilting out of the water to either side, and a fallen cross-slab.
    gs = stone_fn((0.9, 0.9, 0.86), rng, moss=0.3, damp_h=0.8, y0=0.0, lichen=(1.0, 1.0, 0.86))
    for p, yaw, lean, roll, h in (((2.75, -0.55, -1.2), 0.2, 0.32, 0.1, 1.05), ((3.2, -0.5, 0.35), -0.3, -0.2, 0.28, 0.95),
                                  ((2.6, -0.5, 1.9), 0.5, 0.15, -0.35, 1.1), ((-2.85, -0.5, -1.0), -0.15, 0.25, -0.22, 1.0),
                                  ((-3.3, -0.55, 0.7), 0.35, -0.3, 0.15, 1.0), ((2.3, -0.6, -3.2), 0.1, 0.45, 0.2, 1.1)):
        gravestone(base, p, quat_y(yaw) @ quat_x(lean) @ quat_z(roll), rng, gs, h=h)
    xs = TG(base, quat_y(0.5) @ quat_x(0.28) @ quat_z(0.08), (-1.45, -0.02, -3.75))
    slab(xs, (0, 0, 0), (0.75, 0.16, 1.7), quat_y(0), rng, mat=M_RUBBLE, res=(3, 1, 5), round_r=0.04, rough=0.03, col_fn=gs,
         tile=0.9, taper=0.1)
    for size, off in (((0.1, 0.05, 1.2), (0, 0.09, -0.05)), ((0.55, 0.05, 0.1), (0, 0.09, -0.32))):
        slab(xs, off, size, quat_y(0), rng, mat=M_RUBBLE, res=(2, 1, 2), round_r=0.02, rough=0.02, col_fn=gs, tile=0.6)
    # The gable cross itself, fallen into the water by the door, one arm above the surface.
    cg = TG(base, quat_y(0.9) @ quat_x(1.3), (1.4, -0.1, -3.7))
    slab(cg, (0, 0.0, 0), (0.24, 1.3, 0.2), quat_y(0), rng, mat=M_RUBBLE, res=(2, 5, 2), round_r=0.03, rough=0.03,
         col_fn=gs, tile=0.6)
    slab(cg, (0, 0.28, 0), (0.75, 0.22, 0.2), quat_y(0), rng, mat=M_RUBBLE, res=(3, 1, 2), round_r=0.03, rough=0.03,
         col_fn=gs, tile=0.6)
    # Fallen wall stones breaking the surface round the wall feet.
    for k in range(16):
        side = rng.choice([-1, 1])
        p = V(side * rng.uniform(2.05, 2.7), rng.uniform(-0.12, 0.0), rng.uniform(-2.4, 2.8))
        slab(base, tuple(p), (rng.uniform(0.25, 0.45), rng.uniform(0.16, 0.24), rng.uniform(0.14, 0.2)),
             quat_y(rng.uniform(0, 3)) @ quat_x(rng.uniform(-0.4, 0.4)) @ quat_z(rng.uniform(-0.3, 0.3)), rng, mat=M_RUBBLE,
             res=(2, 1, 1), round_r=0.03, rough=0.06, col_fn=gs, tile=1.6)
    # Reeds: stands in the water against the walls and along the hummocks.
    for p, n, h in (((-2.4, -0.1, -1.8), 14, 1.2), ((2.35, -0.1, 0.7), 14, 1.25), ((-2.2, -0.1, 2.4), 12, 1.1),
                    ((1.9, -0.1, 3.4), 12, 1.0), ((-0.9, -0.1, -3.4), 10, 1.0), ((3.6, 0.1, -0.6), 12, 1.0),
                    ((-3.7, 0.1, 0.0), 12, 1.0), ((0.5, -0.1, 3.6), 14, 1.2), ((-3.3, 0.1, -2.3), 10, 1.0),
                    ((3.4, 0.1, 2.6), 10, 0.9), ((2.0, -0.1, -2.9), 9, 1.0)):
        sedge(base, p, rng, n=n, h=h, col=(0.5, 0.5, 0.26))
        if n >= 12:
            cattails(base, (p[0] + 0.3, -0.05, p[2] - 0.2), rng, size=1.1)
    return b


TURF = (0.36, 0.52, 0.18)


def turf_fn(rng):
    """Turf over an old barrow: grass on the slopes, browner toward the foot."""
    return peat_fn(rng, base=(0.6, 0.52, 0.4), wet=0.8, grass=1.7, grass_col=TURF)


def kerb(g, c, rx, rz, rng, col_fn, n=16, gap=None, s=1.0):
    """A kerb ring of individual stones set round a barrow's foot (`gap` = (a0, a1) left unlaid)."""
    c = Vector(c)
    for i in range(n):
        a = 2 * math.pi * (i + rng.uniform(-0.2, 0.2)) / n
        if gap and gap[0] < a < gap[1]:
            continue
        p = c + V(math.cos(a) * rx * 1.03, 0.02, math.sin(a) * rz * 1.03)
        stone(g, tuple(p), (0.2 * s * rng.uniform(0.8, 1.2), 0.17 * s * rng.uniform(0.8, 1.3), 0.15 * s), rng,
              mat=M_GRANITE, detail=1, rough=0.12, cuts=2, rot=quat_y(-a + rng.uniform(-0.2, 0.2)), col_fn=col_fn, tile=0.7)


def grave_post(g, p, h, rng, k, col=(0.92, 0.88, 0.8), lean=(0.0, 0.0)):
    """A carved ork grave post: a split log with a notched crown, grooved bands cut round it, a
    crude face (two gouged eyes, a slot mouth) and charms hung on cords - a tusk, finger bones,
    a raven feather."""
    p = Vector(p)
    top = p + V(lean[0], h, lean[1])
    pole(g, p + V(0, -0.45, 0), top, 0.12, 0.1, rng, mat=M_ROT, col=col, sides=8, tile=0.45)
    d = (top - p).normalized()
    side = d.cross(V(0, 0, 1)).normalized()
    fwd = side.cross(d).normalized()
    at = lambda f: p.lerp(top, f)  # noqa: E731
    for j in range(3):  # notched crown: three teeth
        a = j * 2 * math.pi / 3 + k
        o = side * math.cos(a) * 0.06 + fwd * math.sin(a) * 0.06
        tube(g, [top + o - d * 0.02, top + o + d * 0.14], [0.045, 0.012], 5, M_ROT, scale(col, 0.95), tile=0.2)
    for f in (0.55, 0.6, 0.86):  # grooved bands, cut in dark
        c = at(f)
        ring = [c + (side * math.cos(t) + fwd * math.sin(t)) * 0.108 for t in np.linspace(0, 2 * math.pi, 11)]
        tube(g, ring, [0.012] * 11, 4, M_ROT, (0.16, 0.13, 0.1), tile=0.15, cap=False)
    for j in range(3):  # chevron notches between the bands, on both faces
        for sf in (-1, 1):
            c = at(0.66 + 0.06 * j) + fwd * 0.105 * sf
            tube(g, [c - side * 0.06 + d * 0.03, c, c + side * 0.06 + d * 0.03], [0.009] * 3, 3, M_ROT, (0.18, 0.14, 0.1),
                 tile=0.1, cap=False)
    for sf in (-1, 1):  # the face under the crown (both sides, so it reads from the path)
        fc = at(0.76) + fwd * 0.1 * sf
        for sx in (-1, 1):
            stone(g, tuple(fc + side * sx * 0.04 + d * 0.03), (0.024, 0.02, 0.016), rng, mat=M_ROT, detail=0, rough=0.0,
                  cuts=0, col_fn=lambda q, n: (0.08, 0.06, 0.05), tile=0.2)
        lbox(g, tuple(fc - d * 0.045), (0.07, 0.014, 0.012), basis_q(side, (fwd * sf).cross(side), fwd * sf),
             M_ROT, (0.08, 0.06, 0.05), tile=0.2)
    for j in range(3):  # charms on cords from the upper band
        a = j * 2.2 + k
        hang = at(0.86) + (side * math.cos(a) + fwd * math.sin(a)) * 0.12
        end = hang + V(0, -0.22 - 0.06 * j, 0)
        rope(g, [hang, end], 0.005, (0.4, 0.33, 0.24))
        if j == 0:
            tusk(g, end, V(math.cos(a) * 0.3, -1.0, math.sin(a) * 0.3), rng, length=0.15, r=0.018)
        elif j == 1:
            for m in range(3):
                tube(g, [end + V(0.012 * m, -0.01 * m, 0), end + V(0.012 * m, -0.07 - 0.01 * m, 0)], [0.008, 0.007], 4,
                     M_STONE, BONE, tile=0.1)
        else:
            q = [end, end + V(0.02, -0.18, 0.01), end + V(-0.03, -0.17, -0.01)]
            g.flat(q, M_HIDE, (0.06, 0.06, 0.07), 0.2)
            g.flat(q[::-1], M_HIDE, (0.06, 0.06, 0.07), 0.2)


def long_bone(g, a, b_, r=0.02, col=BONE):
    a, b_ = Vector(a), Vector(b_)
    tube(g, [a, a.lerp(b_, 0.15), a.lerp(b_, 0.85), b_], [r * 1.9, r, r, r * 1.9], 6, M_STONE, col, tile=0.15)


def site_ork_barrows(rng):
    """Footprint r <= 3.8. Masses: the barrow group (local 0, 0.3, 2.6 x 1.6 box), the ring-carved
    post (-2.7, -1.4). An ork burial ground: three old round barrows, turfed and grassed, each in a
    kerb ring of set stones with a carved grave post at its head hung with charms; one FRESH barrow
    of dark raw earth, its kerb half laid (the rest of the stones still heaped), a spear planted in
    it and a round shield leaning on the spear; bones and offering bowls at the post feet; the
    Old Ones' ring-carved post standing apart."""
    b = Builder()
    g = G(b)
    ks = stone_fn((0.85, 0.85, 0.8), rng, moss=0.6, damp_h=0.3, y0=-0.1, lichen=(0.9, 0.9, 0.78))
    # A low turfed rise under the whole group, blended out into the ground.
    mound(g, (0.0, -0.08, 0.1), 3.6, 3.0, 0.16, rng, mat=M_EARTH, col_fn=turf_fn(rng), tile=1.4, rings=6, seg=26,
          skirt=0.25, power=0.5)
    olds = [((-1.65, 0.0, 0.85), 1.15, 1.05, 0.62), ((1.45, 0.0, 1.55), 1.0, 0.95, 0.5), ((-0.95, 0.0, -1.75), 0.85, 0.8, 0.42)]
    for k, (c, rx, rz, h) in enumerate(olds):
        mound(g, c, rx, rz, h, rng, mat=M_EARTH, col_fn=turf_fn(rng), tile=1.0, rings=6, seg=22, skirt=0.15, edge=0.08,
              power=0.75, rough=0.08)
        kerb(g, c, rx, rz, rng, ks, n=int(15 + rx * 4), gap=(1.0 + k, 1.5 + k) if k == 2 else None)
        for j in range(3):
            a = rng.uniform(0, 2 * math.pi)
            sedge(g, (c[0] + math.cos(a) * rx * 0.5, h * 0.7, c[2] + math.sin(a) * rz * 0.5), rng, n=7, h=0.45,
                  col=(0.58, 0.58, 0.32))
        hp = V(c[0] + 0.1, 0.0, c[2] - rz - 0.35)
        grave_post(g, hp, 1.35 + 0.3 * k, rng, k, col=(1.0, 0.86, 0.68), lean=(0.05 * (k - 1), -0.06 * k))
        bowl(g, (hp.x + 0.3, 0.02, hp.z - 0.12), 0.1, rng, fill=(0.28, 0.3, 0.26) if k else (0.55, 0.28, 0.14))
        long_bone(g, hp + V(-0.35, 0.03, -0.05), hp + V(-0.05, 0.03, -0.25))
    skull(g, V(-1.55, 0.02, -0.5), quat_y(0.4), rng, s=1.0)
    # The FRESH barrow: raw dark earth, clods, the kerb half laid and the rest heaped beside it.
    fc = (1.35, 0.0, -1.15)
    pfresh = peat_fn(rng, base=(0.72, 0.62, 0.5), wet=0.55)
    mound(g, fc, 0.95, 0.9, 0.55, rng, mat=M_PEAT, col_fn=pfresh, tile=0.8, rings=6, seg=20, skirt=0.15, edge=0.1,
          power=0.8, rough=0.18)
    for _ in range(16):
        a = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(0.2, 1.0)
        p = V(fc[0] + math.cos(a) * r * 0.95, 0.55 * max(0.0, 1 - r * r) ** 0.8 + 0.03, fc[2] + math.sin(a) * r * 0.9)
        stone(g, tuple(p), (0.08, 0.06, 0.07), rng, mat=M_PEAT, detail=1, rough=0.2, cuts=2, tile=0.4, col_fn=pfresh)
    kerb(g, fc, 0.95, 0.9, rng, ks, n=16, gap=(0.2, 3.4))
    for k in range(7):
        stone(g, (2.65 + rng.uniform(-0.25, 0.25), 0.08 + 0.12 * (k > 4), -0.35 + rng.uniform(-0.3, 0.3)),
              (0.19, 0.16, 0.15), rng, mat=M_GRANITE, detail=1, rough=0.12, cuts=2, rot=quat_y(rng.uniform(0, 3)), col_fn=ks,
              tile=0.7)
    # The spear planted at its head, the shield leaning on it.
    sp = V(fc[0] - 0.1, 0.45, fc[2] - 0.55)
    st = sp + V(0.12, 1.75, -0.08)
    pole(g, sp + V(-0.02, -0.4, 0.02), st, 0.028, 0.024, rng, mat=M_ROT, col=(0.85, 0.78, 0.66), sides=6, tile=0.4)
    d = (st - sp).normalized()
    sd = d.cross(V(0, 0, 1)).normalized()
    blade = [st, st + d * 0.1 + sd * 0.055, st + d * 0.33, st + d * 0.1 - sd * 0.055]
    g.flat(blade, M_RUST, (0.62, 0.58, 0.55), 0.3)
    g.flat(blade[::-1], M_RUST, (0.62, 0.58, 0.55), 0.3)
    tube(g, [st - d * 0.06, st + d * 0.02], [0.03, 0.026], 6, M_RUST, (0.5, 0.45, 0.4), tile=0.1)
    tube(g, [st - d * 0.1, st - d * 0.15 + V(0.05, -0.2, 0.02)], [0.006, 0.004], 4, M_CLOTH, (0.55, 0.12, 0.08), tile=0.1)
    shc = sp + V(0.38, 0.18, 0.1)
    srot = quat_y(-1.2) @ quat_x(-1.25)
    r_ = 0.42
    for j in range(5):
        x = -r_ + (j + 0.5) * 2 * r_ / 5
        ln = 2 * math.sqrt(max(0.0, r_ * r_ - x * x)) - 0.02
        board(g, shc + srot @ V(x, 0, 0), srot @ V(0, 0, 1), srot @ V(0, 1, 0), ln, 2 * r_ / 5 - 0.01, 0.03, mat=M_ROT,
              col=scale((0.75, 0.62, 0.48), 0.9 + 0.1 * (j % 2)), rng=rng)
    ring = [shc + srot @ V(math.cos(t) * r_, 0.02, math.sin(t) * r_) for t in np.linspace(0, 2 * math.pi, 17)]
    tube(g, ring, [0.016] * 17, 4, M_HIDE, (0.3, 0.2, 0.13), tile=0.15, cap=False)
    dome(g, shc + srot @ V(0, 0.02, 0), 0.1, srot, M_RUST, lambda p, n: (0.55, 0.48, 0.42), rings=3, seg=10, squash=0.7)
    # Bones and bowls on the fresh grave.
    bowl(g, (fc[0] - 0.65, 0.05, fc[2] - 0.3), 0.11, rng, fill=(0.3, 0.32, 0.3))
    fish(g, (fc[0] - 0.63, 0.13, fc[2] - 0.3), V(1, 0.1, 0.3), rng, s=0.8)
    long_bone(g, (fc[0] - 0.2, 0.52, fc[2] + 0.1), (fc[0] + 0.2, 0.5, fc[2] + 0.3))
    for j in range(4):
        a0 = V(fc[0] + 0.4, 0.4 - 0.03 * j, fc[2] + 0.35 + 0.07 * j)
        tube(g, [a0, a0 + V(0.12, 0.06, 0.02), a0 + V(0.24, -0.02, 0.03)], [0.012, 0.011, 0.008], 4, M_STONE, BONE, tile=0.1)
    # The ring-carved post (the Old Ones' sign), black with age, apart from the graves.
    cp = V(-2.7, 0.0, -1.4)
    pole(g, cp + V(0, -0.5, 0), cp + V(0.05, 1.9, 0.02), 0.16, 0.13, rng, mat=M_ROT, col=scale(ROT_WOOD, 0.55), sides=8,
         tile=0.5)
    for k, y in enumerate((1.1, 1.35, 1.6)):
        ring = [cp + V(0.02 + math.cos(t) * (0.14 - 0.005 * k), y, math.sin(t) * (0.14 - 0.005 * k)) for t in
                np.linspace(0, 2 * math.pi, 13)]
        tube(g, ring, [0.018] * 13, 4, M_IRON, BLACK_IRON, tile=0.15, cap=False)
    skull(g, cp + V(0.05, 1.98, 0.02), quat_y(-0.6), rng, s=1.0)
    for p in ((3.0, 0, 0.0), (-3.1, 0, 1.4), (2.7, 0, 2.6), (0.2, 0, 2.9), (-3.0, 0, -0.3), (0.3, 0, -2.9)):
        sedge(g, p, rng, n=11, h=0.8)
    for p in ((3.2, 0.0, -1.2), (-2.4, 0.0, 2.6)):
        cattails(g, p, rng, size=1.1)
    return b


def site_eel_weir(rng):
    """Footprint r <= 3.4 (long axis local Z, the water at -Z). Masses: the drying rack (1.6, 1.9),
    the trap pile (-1.5, 2.2). An ork eel weir: two lines of wattle on stakes converging out into
    the water into a V, three funnel traps of withy lashed at its mouth (one hauled up on a stake),
    a drying rack of split eels on the bank, a stack of spare traps."""
    b = Builder()
    g = G(b)
    mound(g, (0.0, -0.05, 2.0), 3.0, 1.6, 0.18, rng, mat=M_PEAT, col_fn=peat_fn(rng, grass=0.6), tile=1.2, rings=5,
          seg=20, skirt=0.3)
    water_disc(g, (0.0, 0, -1.6), 3.0, 2.2, -0.42, rng)
    mouth = V(0.0, 0.0, -2.6)
    for sx in (-1, 1):
        p0 = V(sx * 2.4, 0.0, 0.7)
        p1 = mouth + V(sx * 0.35, 0, 0)
        L = (p1 - p0).length
        n = int(L / 0.32)
        stakes = []
        for i in range(n + 1):
            p = p0.lerp(p1, i / n)
            h = 0.85 + 0.15 * math.sin(i * 1.3)
            pole(g, p + V(0, -1.6, 0), p + V(rng.uniform(-0.02, 0.02), h, rng.uniform(-0.02, 0.02)), 0.035, 0.025, rng,
                 mat=M_ROT, col=ROT_WOOD, sides=5, segs=2, col_fn=None)
            stakes.append(p)
        for r in range(7):
            y = -0.35 + r * 0.16
            pts = []
            for i, s in enumerate(stakes):
                off = 0.035 * (1 if (i + r) % 2 else -1)
                perp = V(0, 1, 0).cross((p1 - p0).normalized())
                pts.append(s + perp * off + V(0, y, 0))
            tube(g, pts, [0.016] * len(pts), 4, M_BARK, scale((0.62, 0.55, 0.42), rng.uniform(0.7, 1.0)), tile=0.5, cap=False)
    # Funnel traps: a woven cone (rings of withy + staves), mouth toward the weir.
    def trap(c, d, s=1.0):
        c, d = Vector(c), Vector(d).normalized()
        side = d.cross(V(0, 1, 0)).normalized()
        up = side.cross(d).normalized()
        L = 1.1 * s
        for k in range(6):
            f = k / 5
            r = (0.28 - 0.2 * f) * s
            ring = [c + d * L * f + (side * math.cos(t) + up * math.sin(t)) * r for t in np.linspace(0, 2 * math.pi, 11)]
            tube(g, ring, [0.012] * 11, 4, M_BARK, (0.62, 0.54, 0.38), tile=0.3, cap=False)
        for k in range(9):
            t = 2 * math.pi * k / 9
            o = side * math.cos(t) + up * math.sin(t)
            tube(g, [c + o * 0.28 * s, c + d * L * 0.5 + o * 0.18 * s, c + d * L + o * 0.08 * s], [0.01] * 3, 3, M_BARK,
                 (0.55, 0.48, 0.34), tile=0.3, cap=False)
    trap(mouth + V(0, -0.25, 0.1), V(0, -0.05, -1))
    trap(mouth + V(0.7, -0.3, -0.1), V(0.4, -0.1, -1), 0.85)
    trap(V(1.0, 0.75, 0.9), V(0.3, -0.95, 0.1), 0.9)  # hauled up on a stake to dry
    pole(g, V(1.05, -0.4, 0.95), V(1.08, 0.95, 0.92), 0.04, 0.03, rng, mat=M_ROT, col=ROT_WOOD, sides=5)
    # Drying rack on the bank: two forked posts, a pole, split eels hanging.
    rc = V(1.6, 0, 1.9)
    for dx in (-0.7, 0.7):
        pole(g, rc + V(dx, -0.3, 0), rc + V(dx, 1.35, 0), 0.05, 0.04, rng, mat=M_ROT, col=ROT_WOOD, sides=6)
    pole(g, rc + V(-0.8, 1.3, 0), rc + V(0.8, 1.32, 0), 0.03, 0.03, rng, mat=M_ROT, col=ROT_WOOD, sides=5)
    for k in range(7):
        x = -0.6 + k * 0.2
        top = rc + V(x, 1.3, 0)
        pts = [top + V(0, -f * 0.75, 0.02 * math.sin(f * 6 + k)) for f in (0, 0.3, 0.6, 1.0)]
        tube(g, pts, [0.02, 0.022, 0.016, 0.006], 5, M_HIDE, (0.24, 0.22, 0.17), tile=0.15)
    # Spare traps stacked by the bank.
    trap(V(-1.4, 0.25, 2.0), V(1, 0.05, 0.2), 0.8)
    trap(V(-1.7, 0.25, 2.5), V(0.9, 0.05, -0.3), 0.8)
    trap(V(-1.55, 0.55, 2.25), V(1, 0.0, 0.0), 0.75)
    for p in ((2.6, 0, 0.6), (-2.7, 0, 0.8), (2.4, 0, 2.8), (-0.4, 0, 2.9)):
        sedge(g, p, rng, n=11, h=0.85)
    return b


def site_colony_causeway(rng):
    """Footprint r <= 4.6 (long axis local Z: the bank at +Z, open water at -Z). Masses: the
    abutment (0, 3.3). The first colony's plank causeway on paired piles, running from a stone
    abutment on the bank out over the water and ENDING there: the last bents leaning, the deck
    broken off, planks floating, a rusted lantern still hanging from its post halfway."""
    b = Builder()
    g = G(b)
    mound(g, (0.0, -0.05, 3.4), 2.0, 1.4, 0.3, rng, mat=M_EARTH, col_fn=turf_fn(rng), tile=1.2, rings=5, seg=18,
          skirt=0.3)
    water_disc(g, (0.0, 0, -1.7), 2.3, 3.3, -0.42, rng)
    stn = stone_fn((0.9, 0.9, 0.86), rng, moss=0.5, damp_h=0.8, y0=-0.4)
    for k in range(6):
        slab(g, (rng.uniform(-0.8, 0.8), 0.0 + 0.1 * (k % 2), 3.2 + rng.uniform(-0.3, 0.3)), (0.55, 0.32, 0.4),
             quat_y(rng.uniform(0, 3)), rng, mat=M_CHAPEL, res=(2, 1, 2), round_r=0.05, rough=0.05, col_fn=stn, tile=0.6)
    deck_y = 0.32
    bents = [2.7, 1.55, 0.4, -0.75, -1.9, -3.0]
    for i, z in enumerate(bents):
        lean = 0.0 if i < 4 else (0.18 if i == 4 else 0.42)
        for sx in (-1, 1):
            x = sx * 0.65
            top = V(x + lean * 0.4 * sx, deck_y + 0.15 - lean * 0.6, z - lean)
            rot_beam(g, [V(x, -2.0, z), top], 0.16, 0.16, rng, col_fn=damp_wood(wet=0.9, green=0.6))
        if i < 5:
            rot_beam(g, [V(-0.8, deck_y - 0.08 - (0.15 if i == 4 else 0), z), V(0.8, deck_y - 0.08, z - 0.05 * i)], 0.12, 0.1,
                     rng, col_fn=damp_wood(wet=0.6))
    # Stringers + deck planks as far as bent 4, the end broken; a few planks floating beyond.
    for sx in (-1, 1):
        rot_beam(g, [V(sx * 0.45, deck_y, 3.2), V(sx * 0.45, deck_y, -0.75), V(sx * 0.42, deck_y - 0.12, -1.5 - 0.3 * (sx > 0))],
                 0.12, 0.12, rng, jag=(0.0, 0.2), col_fn=damp_wood(wet=0.5))
    z = 3.15
    k = 0
    while z > -1.35:
        miss = k in (6, 11, 12)
        if not miss:
            w = rng.uniform(0.2, 0.28)
            sag = -0.05 if z < -0.8 else 0.0
            board(g, V(rng.uniform(-0.03, 0.03), deck_y + 0.09 + sag, z), V(1, 0, rng.uniform(-0.06, 0.06)),
                  V(0, 1, rng.uniform(-0.05, 0.05)), 1.25 - (0.35 if z < -0.9 else 0.0) * rng.uniform(0, 1), w, 0.05,
                  mat=M_ROT, col=scale(ROT_WOOD, rng.uniform(0.95, 1.15)), rng=rng, jag=(0.0, 0.08 if z < -0.8 else 0.0))
        z -= 0.3
        k += 1
    for p, a in (((0.9, -0.4, -2.4), 0.6), ((-0.6, -0.4, -3.6), -0.4), ((0.2, -0.38, -4.3), 1.3)):
        board(g, V(*p), V(math.cos(a), 0, math.sin(a)), V(0, 1, 0), 1.1, 0.24, 0.05, mat=M_ROT, col=scale(ROT_WOOD, 0.6),
              rng=rng, jag=(0.05, 0.1))
    # Beyond the end the line of the road goes on as pile stumps in the open water, rotted off
    # at the surface, the last ones barely breaking it.
    for i, z in enumerate((-4.05, -4.6)):
        for sx in (-1, 1):
            top = -0.42 + (0.35 if i == 0 else 0.14) * (1.0 if sx < 0 else 0.6)
            rot_beam(g, [V(sx * 0.66 + 0.05 * i, -2.0, z), V(sx * 0.66 + 0.06 * i, top, z + 0.03)], 0.16, 0.16, rng, jag=(0.0, 0.1),
                     col_fn=damp_wood(wet=0.9, green=0.6))
    # The lantern post on bent 2: a crooked arm, a rusted lantern, its glass long gone.
    lp = V(0.78, 0.0, 0.4)
    rot_beam(g, [lp + V(0, deck_y, 0), lp + V(0.02, 2.2, 0)], 0.1, 0.1, rng, col_fn=damp_wood(wet=0.3))
    rot_beam(g, [lp + V(0, 2.1, 0), lp + V(-0.45, 2.15, -0.05)], 0.07, 0.07, rng)
    lh = lp + V(-0.42, 2.12, -0.05)
    tube(g, [lh, lh + V(0, -0.12, 0)], [0.008, 0.008], 4, M_RUST, (0.8, 0.75, 0.7), tile=0.1)
    lc = lh + V(0, -0.36, 0)
    for sx in (-1, 1):
        for sz in (-1, 1):
            tube(g, [lc + V(sx * 0.08, -0.12, sz * 0.08), lc + V(sx * 0.08, 0.12, sz * 0.08)], [0.008, 0.008], 4, M_RUST,
                 (0.8, 0.72, 0.65), tile=0.1)
    lbox(g, tuple(lc + V(0, -0.14, 0)), (0.2, 0.03, 0.2), quat_y(0), M_RUST, (0.8, 0.72, 0.65), tile=0.2)
    frustum(g, 0.13, 0.03, lc.y + 0.12, 0.1, 8, M_RUST, (0.78, 0.7, 0.62), tile=0.2, centre=(lc.x, 0, lc.z))
    for p in ((1.5, 0, 3.0), (-1.4, 0, 2.6), (1.4, -0.35, 1.6), (-1.3, -0.35, -0.2), (1.2, -0.4, -2.0)):
        sedge(g, p, rng, n=12, h=0.9)
    return b


def site_peat_cutting(rng):
    """Footprint r <= 3.4. Masses: the peat bank (0.4, 1.3, 2.0 x 0.9 box), the sledge (-1.9, -1.3),
    the stack (2.55, -1.95). A peat cutting: a raised bank with a green turf top cut back on its
    -Z side into a STEPPED face of three benches - the layers banded from pale fibrous peat under
    the turf down to black - black water filling the trench below; a row of rickles drying on
    the flat beyond and one big built stack of dried bricks; two slanes stuck in the bank's top,
    a sledge half-loaded with bricks, its rope trailing."""
    b = Builder()
    g = G(b)
    turf = turf_fn(rng)
    # A low turfed skirt under the site so its ground reads lighter than the bog round it.
    mound(g, (0.2, -0.06, 0.0), 3.4, 3.1, 0.1, rng, mat=M_EARTH, col_fn=turf, tile=1.4, rings=5, seg=24, skirt=0.2,
          power=0.5)
    # The bank: a long hump with a green turf top; its -Z side cut back in three benches.
    mound(g, (0.4, -0.1, 2.15), 2.9, 1.45, 1.08, rng, mat=M_EARTH, col_fn=turf, tile=1.2, rings=7, seg=24, skirt=0.3,
          edge=0.12, power=0.3)

    def band(y, k):
        """Cut-peat colour by depth below the turf: pale fibrous brown on top, black at the foot."""
        f = smoothstep(-0.05, 0.95, y)
        c = mix((0.24, 0.17, 0.12), (0.78, 0.58, 0.4), f)
        return scale(c, k * (0.92 + 0.08 * math.sin(y * 41.0)))
    benches = ((0.72, 0.95, -1.75, 2.6), (0.38, 0.6, -1.55, 2.4), (0.04, 0.3, -1.35, 2.2))
    for step, (z, h, x0, x1) in enumerate(benches):
        rows = int(round(h / 0.15))
        for row in range(rows):
            y = -0.06 + row * 0.15
            x = x0 + (0.14 if row % 2 else 0.0)
            while x < x1:
                w = rng.uniform(0.24, 0.32)
                if rng.uniform() > 0.05:
                    k = rng.uniform(0.85, 1.1)
                    lbox(g, (x + w / 2, y + 0.07, z + rng.uniform(-0.02, 0.02)), (w - 0.02, 0.13, 0.34),
                         quat_y(rng.uniform(-0.03, 0.03)), M_EARTH, [band(y, k), None, band(y + 0.13, k)], tile=0.5, grain=1)
                x += w
        # the bench tread: a strip of trodden wet peat in front of the next face up
        if step > 0:
            mound(g, ((x0 + x1) / 2, h - 0.08, z + 0.22), (x1 - x0) / 2 + 0.05, 0.26, 0.06, rng, mat=M_PEAT,
                  col_fn=peat_fn(rng, base=(0.62, 0.5, 0.38), wet=0.7), tile=1.0, rings=3, seg=14, skirt=0.04)
    # Turf overhang lip along the top of the face.
    for k in range(9):
        x = -1.6 + k * 0.48
        lbox(g, (x, 0.98 + rng.uniform(-0.03, 0.03), 0.8), (0.5, 0.09, 0.22), quat_y(rng.uniform(-0.05, 0.05)) @ quat_x(-0.12),
             M_EARTH, [(0.5, 0.42, 0.3), None, scale(TURF, 1.1)], tile=0.5, grain=1)
    # The trench, full of black water, and a ridge of spoil.
    water_quad(g, [(-1.9, -0.15), (2.6, -0.15), (2.6, -0.95), (-1.9, -0.95)], -0.06)
    mound(g, (0.4, -0.05, -1.3), 2.4, 0.35, 0.16, rng, mat=M_PEAT, col_fn=peat_fn(rng, base=(0.8, 0.7, 0.56), wet=0.6,
          grass=0.5, grass_col=TURF), tile=1.0, rings=4, seg=16, skirt=0.1)
    # Rickles: open cones of bricks leaning together to dry - pale grey-brown, sun-dried.
    def rickle(c, rot, s=1.0):
        c = Vector(c)
        dry = (0.7, 0.56, 0.44)
        for k in range(11):
            a = k / 11 * 2 * math.pi
            lean = quat_y(a) @ quat_x(0.42)
            lbox(g, tuple(c + rot @ V(math.cos(a) * 0.2 * s, 0.2 * s, math.sin(a) * 0.2 * s)), (0.12 * s, 0.38 * s, 0.09 * s),
                 rot @ lean, M_EARTH, [scale(dry, 0.7), None, dry], tile=0.3, grain=1)
        for k in range(3):
            lbox(g, tuple(c + rot @ V(0, (0.42 + 0.06 * k) * s, 0)), (0.32 * s, 0.07 * s, 0.12 * s), rot @ quat_y(k * 1.1),
                 M_EARTH, dry, tile=0.3)
    for c, s in (((1.3, -0.05, -2.05), 1.1), ((0.2, -0.05, -2.35), 1.0), ((-0.9, -0.05, -2.45), 1.15),
                 ((2.85, -0.05, -0.75), 1.0), ((3.0, -0.05, 0.55), 0.95)):
        rickle(c, quat_y(rng.uniform(0, 3)), s)
    # The stack: dried bricks built into a neat clamp, herringbone-laid, a turf cap.
    st, sr = V(2.45, -0.04, -2.0), quat_y(0.5)
    for lay in range(5):
        for i in range(5 - (lay > 2)):
            for j in range(2):
                p = st + sr @ V(-0.55 + i * 0.27 + 0.06 * (lay % 2) + 0.06 * (lay > 2), 0.07 + lay * 0.13, -0.17 + j * 0.34)
                lbox(g, tuple(p), (0.25, 0.12, 0.32), sr @ quat_y(0.04 * rng.uniform(-1, 1) + (math.pi / 2 if lay % 2 else 0) * 0),
                     M_EARTH, [(0.45, 0.36, 0.28), None, (0.7, 0.57, 0.45)], tile=0.3, grain=1)
    lbox(g, tuple(st + sr @ V(-0.05, 0.72, 0.0)), (1.2, 0.08, 0.72), sr @ quat_z(0.04), M_EARTH,
         [(0.5, 0.42, 0.3), None, scale(TURF, 1.1)], tile=0.5, grain=1)
    # Two slanes stuck in the bank's top: a long shaft with a T grip, a narrow iron blade with a wing.
    for p, a in (((-0.6, 1.05, 1.2), 0.15), ((1.6, 1.05, 1.35), -0.3)):
        p = V(*p)
        d = V(math.sin(a) * 0.2, 1.0, -0.15).normalized()
        rot_beam(g, [p, p + d * 1.15], 0.045, 0.045, rng)
        rot_beam(g, [p + d * 1.15 + V(-0.13, 0, 0), p + d * 1.15 + V(0.13, 0, 0)], 0.04, 0.04, rng)
        lbox(g, tuple(p - d * 0.16), (0.11, 0.3, 0.02), quat_y(a), M_RUST, (0.75, 0.68, 0.6), tile=0.3)
        lbox(g, tuple(p - d * 0.16 + V(0.065, 0, 0)), (0.02, 0.28, 0.09), quat_y(a), M_RUST, (0.72, 0.65, 0.58), tile=0.3)
    # The sledge: two curved runners, cross-slats, half a load of bricks; a rope trailing.
    sc = V(-1.95, 0.0, -1.35)
    sr = quat_y(0.35)
    for sx in (-1, 1):
        pts = [sc + sr @ V(sx * 0.42, 0.05, z) for z in (-0.9, 0.5)] + [sc + sr @ V(sx * 0.42, 0.25, 0.8)]
        rot_beam(g, pts, 0.08, 0.12, rng, col_fn=damp_wood(wet=0.6))
    for k in range(6):
        board(g, sc + sr @ V(0, 0.17, -0.75 + k * 0.26), sr @ V(1, 0, 0), V(0, 1, 0), 1.0, 0.18, 0.04, mat=M_ROT,
              col=scale(ROT_WOOD, 0.8), rng=rng)
    for k in range(9):
        i, j, lay = k % 3, (k // 3) % 2, k // 6
        lbox(g, tuple(sc + sr @ V(-0.25 + i * 0.25, 0.27 + lay * 0.1, -0.6 + j * 0.32)), (0.22, 0.09, 0.3),
             sr @ quat_y(rng.uniform(-0.1, 0.1)), M_EARTH, (0.62, 0.5, 0.4), tile=0.3)
    rope(g, [sc + sr @ V(0.0, 0.3, 0.85), sc + sr @ V(0.1, 0.05, 1.2), sc + sr @ V(-0.3, 0.02, 1.6),
             sc + sr @ V(-0.2, 0.02, 2.0)], 0.014, (0.55, 0.46, 0.32))
    for p in ((-2.8, 0, 0.4), (3.2, 0, 1.6), (-0.5, 0, -3.0), (-2.9, 0, -2.4)):
        sedge(g, p, rng, n=9, h=0.7)
    return b


# ─────────────────────────────────────────────────────────────── ROCKY
GRANITE = (0.95, 0.96, 1.0)
SLATE = (0.78, 0.78, 0.76)


def ochre_band(c, face, y0, y1, zig=True):
    """Red ochre painted on one face of a stone: a zig-zag band between y0..y1 (faded)."""
    face = Vector(face).normalized()
    right = V(0, 1, 0).cross(face).normalized()

    def f(p, n):
        if n.dot(face) < 0.45:
            return 0.0
        s = (p - Vector(c)).dot(right)
        mid = (y0 + y1) / 2 + ((abs((s * 3.2) % 1.0 - 0.5) - 0.25) * (y1 - y0) * 1.2 if zig else 0.0)
        return 0.75 * (1.0 - smoothstep(0.03, 0.07, abs(p.y - mid)))
    return f


def carved_rings(g, c, face, radii, depth=0.012, col=(0.16, 0.16, 0.17), mat=M_GRANITE):
    face = Vector(face).normalized()
    right = V(0, 1, 0).cross(face).normalized()
    for rr in radii:
        ring = [Vector(c) + (right * math.cos(t) + V(0, 1, 0) * math.sin(t)) * rr for t in np.linspace(0, 2 * math.pi, 17)]
        tube(g, ring, [depth] * 17, 4, mat, col, tile=0.2, cap=False)


def site_clan_gong(rng):
    """Footprint r <= 3.7. Masses: the two menhirs (+-1.55, 0), the gong between them (0, 0), the
    altar stone (0, 1.5). The clans' iron voice: two lichen-crusted granite menhirs (3.9 / 3.5u) with
    ochre zig-zags and carved rings, an iron bar laid across their notched tops, the great black-iron
    gong (d 1.8) hanging from it on chains, its boss and hammered rings dull and rust-streaked; a ring
    of small boundary stones; tusks, boar skulls and ochre bowls heaped at its foot (front, -Z), and
    on a flat altar stone behind it the stone-headed maul, laid down and never lifted."""
    b = Builder()
    g = G(b)
    mound(g, (0, -0.05, 0), 3.4, 3.0, 0.16, rng, mat=M_EARTH, col_fn=peat_fn(rng, base=(0.5, 0.48, 0.42), grass=0.6),
          tile=1.6, rings=6, seg=26, skirt=0.2, power=0.6)
    for sx, h in ((-1, 3.9), (1, 3.5)):
        c = V(sx * 1.55, h / 2 - 0.45, 0.0)
        och = ochre_band(c, V(0, 0, -1), 1.5, 1.85)
        fn = stone_fn(GRANITE, rng, moss=0.15, damp_h=0.5, y0=-0.3, ochre=och)
        slab(g, tuple(c), (1.15, h + 0.9, 0.55), quat_y(sx * 0.12) @ quat_z(sx * 0.025), rng, mat=M_GRANITE,
             res=(6, 14, 3), round_r=0.06, taper=0.3, rough=0.05, col_fn=fn, tile=1.6, crown=0.25, cuts=2)
        carved_rings(g, V(sx * 1.55, 2.45, -0.33), V(0, 0, -1), (0.09, 0.17, 0.25))
    # The iron bar across the tops, lashed down with iron bands.
    bar_y = 3.32
    tube(g, [V(-1.95, 3.42, 0.0), V(-1.2, bar_y, 0.0), V(1.2, bar_y, 0.0), V(1.85, 3.0, 0.0)], [0.065] * 4, 8, M_IRON,
         BLACK_IRON, tile=0.3)
    for x in (-1.55, 1.55):
        y = 3.4 if x < 0 else 3.07
        ring = [V(x + 0.05 * math.cos(t), y + 0.12 * math.sin(t), 0.12 * math.cos(t)) for t in np.linspace(0, 2 * math.pi, 9)]
        tube(g, ring, [0.025] * 9, 4, M_IRON, BLACK_IRON, tile=0.2, cap=False)
    # The gong: a thick black disc facing -Z, raised boss, hammered rings, a rolled rim.
    gc = V(0.0, 1.95, 0.0)
    face = quat_x(math.pi / 2)  # disc local Y -> game -Z
    iron_fn = lambda p, n: mix(BLACK_IRON, (0.42, 0.24, 0.14), 0.5 * smoothstep(1.4, 1.05, p.y))  # noqa: E731
    disc(g, tuple(gc), face, 0.9, 0.05, 40, M_IRON, BLACK_IRON, tile=0.8, col_rim=(0.16, 0.15, 0.14))
    rim = [gc + V(math.cos(t) * 0.9, math.sin(t) * 0.9, 0.0) for t in np.linspace(0, 2 * math.pi, 41)]
    tube(g, rim, [0.04] * 41, 6, M_IRON, (0.17, 0.16, 0.15), tile=0.3, cap=False)
    dome(g, tuple(gc + V(0, 0, -0.02)), 0.22, quat_x(-math.pi / 2), M_IRON, iron_fn, tile=0.3, rings=4, seg=16, squash=0.45)
    for rr in (0.36, 0.5, 0.66):
        ring = [gc + V(math.cos(t) * rr, math.sin(t) * rr, -0.03) for t in np.linspace(0, 2 * math.pi, 33)]
        tube(g, ring, [0.012] * 33, 4, M_IRON, (0.12, 0.11, 0.1), tile=0.2, cap=False)
    # rust weeping down the face from the hanging holes
    for x in (-0.45, 0.45):
        pts = [gc + V(x, 0.76 - f * 0.7, -0.027) for f in (0, 0.5, 1.0)]
        tube(g, pts, [0.03, 0.025, 0.004], 4, M_RUST, (0.85, 0.6, 0.45), tile=0.2, cap=False)
    for x in (-0.45, 0.45):
        chain(g, V(x * 1.5, bar_y - 0.05, 0.0), gc + V(x, 0.78, 0.0), link=0.1, r=0.013)
    # Boundary ring: small stones on a 3.1u circle, gaps at front and back.
    stn = stone_fn(GRANITE, rng, moss=0.3, damp_h=0.2, y0=-0.1)
    for k in range(16):
        a = k / 16 * 2 * math.pi + 0.1
        if abs(math.sin(a)) > 0.93:
            continue
        stone(g, (math.cos(a) * 3.15, 0.08, math.sin(a) * 2.8), (0.2, 0.17, 0.18), rng, mat=M_GRANITE, detail=1, rough=0.12,
              cuts=2, col_fn=stn, tile=0.6)
    # Offerings heaped at the foot, in front.
    for k in range(9):
        a = rng.uniform(-1.2, 1.2)
        p = V(rng.uniform(-0.7, 0.7), 0.06, -0.55 - rng.uniform(0, 0.4))
        tusk(g, p, V(math.sin(a), 0.25, -math.cos(a)), rng, length=rng.uniform(0.22, 0.38), r=0.03)
    skull(g, V(-0.45, 0.12, -0.9), quat_y(0.4), rng, s=1.2)
    skull(g, V(0.5, 0.12, -0.75), quat_y(-0.5), rng, s=1.0)
    skull(g, V(0.05, 0.3, -0.62), quat_y(0.1) @ quat_x(-0.2), rng, s=0.9)
    bowl(g, (-0.9, 0.0, -0.35), 0.12, rng, fill=OCHRE)
    bowl(g, (0.95, 0.0, -0.45), 0.1, rng, fill=(0.5, 0.15, 0.08))
    # The altar stone behind, and the maul laid on it: a bound stone head on a black haft.
    slab(g, (0.0, 0.12, 1.45), (1.2, 0.36, 0.7), quat_y(0.05), rng, mat=M_GRANITE, res=(4, 1, 3), round_r=0.06, rough=0.03,
         col_fn=stn, tile=0.9)
    mh = V(0.25, 0.38, 1.42)
    tube(g, [mh + V(-0.95, 0.0, 0.05), mh], [0.03, 0.035], 7, M_ROT, (0.4, 0.38, 0.36), tile=0.3)
    stone(g, tuple(mh + V(0.12, 0.05, 0)), (0.2, 0.14, 0.15), rng, mat=M_GRANITE, detail=1, rough=0.06, cuts=2, flat_y=0.8,
          col_fn=stn, tile=0.4)
    lashing(g, mh + V(0.06, 0.04, 0), (1, 0, 0), 0.06, rng, turns=3)
    for p in ((-2.6, 0, 1.4), (2.5, 0, -1.6), (2.2, 0, 2.0)):
        sedge(g, p, rng, n=8, h=0.45, col=(0.6, 0.58, 0.42))
    return b


def site_signal_tower(rng):
    """Footprint r <= 3.5. Masses: the tower (0, 0.3, r 1.35), the scree (1.8, 1.2). The first
    colony's signal tower: a round dry-laid slate tower (d 2.7), its top broken off at ~5.2u, its
    east flank slumped into a scree; the outside stair of projecting slabs climbing round it, fallen
    mid-flight (steps lie in the scree); the iron fire basket tipped on the broken parapet with old
    charcoal; at the foot of the stair, a journal page pinned under a flat stone."""
    b = Builder()
    g = G(b)
    sl = stone_fn(SLATE, rng, moss=0.1, damp_h=0.6, y0=-0.3, lichen=(0.82, 0.84, 0.7))
    C = V(0.0, 0.0, 0.3)
    R, T = 1.35, 0.42
    n = 20
    for k in range(n):
        a0, a1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
        top = lambda s, k=k: 5.2 + 0.25 * math.sin(k * 1.9 + s * 2.0) - (3.4 * smoothstep(0.75, 1.0, math.cos((k + s) / n * 2 * math.pi - 0.3)))  # noqa: E731
        p0 = (C.x + math.cos(a0) * (R - T / 2), C.z + math.sin(a0) * (R - T / 2))
        p1 = (C.x + math.cos(a1) * (R - T / 2), C.z + math.sin(a1) * (R - T / 2))
        if k == 15:  # the door
            masonry(g, p0, p1, 1.9, top, T, M_SLATE, sl, rng, tile=2.2, steps=2, course=0.16, lmin=0.2, lmax=0.42, sides=(1,), depth=0.14)
            continue
        masonry(g, p0, p1, -0.25, top, T, M_SLATE, sl, rng, tile=2.2, steps=2, course=0.16, lmin=0.2, lmax=0.42, sides=(1,), depth=0.14)
    # Door lintel.
    a = 2 * math.pi * 15.5 / n
    slab(g, (C.x + math.cos(a) * (R - 0.2), 1.98, C.z + math.sin(a) * (R - 0.2)), (0.85, 0.18, 0.5), quat_y(-a + math.pi / 2),
         rng, mat=M_SLATE, res=(3, 1, 2), round_r=0.03, rough=0.03, col_fn=sl, tile=0.8)
    # The stair: slabs spiralling up the outside from the door, gone after the 9th.
    for k in range(13):
        a = 2 * math.pi * (15.0 - k * 0.75) / n
        y = 0.18 + k * 0.32
        if k > 8:
            continue
        p = V(C.x + math.cos(a) * (R + 0.32), y, C.z + math.sin(a) * (R + 0.32))
        slab(g, tuple(p), (0.62, 0.12, 0.5), quat_y(-a + math.pi / 2) @ quat_x(0.04 * (k == 8)), rng, mat=M_SLATE,
             res=(3, 1, 2), round_r=0.02, rough=0.04, col_fn=sl, tile=0.6)
    # The scree on the slumped flank: slate rubble cone + fallen stair slabs in it.
    mound(g, (1.75, -0.05, 1.15), 1.5, 1.3, 0.75, rng, mat=M_SLATE, col_fn=sl, tile=0.9, rings=5, seg=18, skirt=0.15,
          rough=0.3)
    for _ in range(26):
        p = V(1.75 + rng.uniform(-1.3, 1.3), 0.0, 1.15 + rng.uniform(-1.1, 1.1))
        d = (p - V(1.75, 0, 1.15)).length
        p.y = max(0.05, 0.7 * (1 - (d / 1.4) ** 2))
        slab(g, tuple(p), (rng.uniform(0.2, 0.5), rng.uniform(0.06, 0.12), rng.uniform(0.15, 0.35)),
             quat_y(rng.uniform(0, 3)) @ quat_x(rng.uniform(-0.4, 0.4)), rng, mat=M_SLATE, res=(2, 1, 2), round_r=0.02,
             rough=0.05, col_fn=sl, tile=0.6)
    for k in range(3):
        slab(g, (2.4 + 0.3 * k, 0.12 + 0.1 * (k == 1), 0.0 - 0.3 * k), (0.62, 0.12, 0.5), quat_y(0.4 + k) @ quat_z(0.3),
             rng, mat=M_SLATE, res=(3, 1, 2), round_r=0.02, rough=0.04, col_fn=sl, tile=0.6)
    # The fire basket: an iron cresset on three legs, tipped on the parapet's high side.
    fb = V(-0.75, 5.35, 0.0)
    tilt = quat_z(0.5) @ quat_x(0.2)
    for k in range(10):
        t = 2 * math.pi * k / 10
        tube(g, [fb + tilt @ V(math.cos(t) * 0.14, 0, math.sin(t) * 0.14), fb + tilt @ V(math.cos(t) * 0.32, 0.45, math.sin(t) * 0.32)],
             [0.014, 0.014], 4, M_IRON, BLACK_IRON, tile=0.2)
    for y, r in ((0.15, 0.2), (0.45, 0.32)):
        ring = [fb + tilt @ V(math.cos(t) * r, y, math.sin(t) * r) for t in np.linspace(0, 2 * math.pi, 15)]
        tube(g, ring, [0.016] * 15, 4, M_IRON, BLACK_IRON, tile=0.2, cap=False)
    stone(g, tuple(fb + tilt @ V(0, 0.25, 0)), (0.2, 0.08, 0.2), rng, mat=M_EARTH, detail=1, rough=0.3, cuts=0,
          col_fn=lambda p, n: (0.08, 0.075, 0.07), tile=0.3)
    # Charcoal spilled down the wall into the stair's foot.
    for _ in range(10):
        stone(g, (rng.uniform(-1.9, -1.4), 0.04, rng.uniform(-0.6, 0.6)), (0.05, 0.035, 0.04), rng, mat=M_EARTH, detail=0,
              rough=0.2, cuts=1, col_fn=lambda p, n: (0.07, 0.065, 0.06), tile=0.2)
    # A stack of signal-fire wood by the door, grey and split with age.
    for k in range(7):
        y = 0.08 + (k // 4) * 0.12
        z = -0.4 + (k % 4) * 0.13 + (k // 4) * 0.06
        beam(g, [V(-2.0, y, z - 0.4) + V(0, 0, 0.0), V(-1.95, y, z + 0.55)], 0.11, 0.11, mat=M_PLANK,
             col=(0.62, 0.6, 0.57), rng=rng, jag=(0.03, 0.03))
    # The page under its stone at the stair foot (the stair starts at the door, angle ~270 deg).
    a = 2 * math.pi * 15.0 / n
    pp = V(C.x + math.cos(a) * (R + 0.95), 0.05, C.z + math.sin(a) * (R + 0.95) - 0.1)
    page(g, pp, quat_y(0.4) @ quat_x(0.04), 0.22, 0.3,
         lambda u, v: ink_lines(u, v, 10, 0.06, 0.94, 0.9, 7.0), n=(10, 12), curl=0.02, wet=0.25, stain_seed=0.5)
    slab(g, tuple(pp + V(0.06, 0.06, 0.05)), (0.28, 0.08, 0.22), quat_y(0.9), rng, mat=M_SLATE, res=(2, 1, 2), round_r=0.02,
         rough=0.03, col_fn=sl, tile=0.4)
    return b


def bridge_posts(g, rng, sl, xs=0.8, h=1.85):
    """Two squared anchor posts with the main ropes wound round them (shared by both anchors)."""
    posts = []
    for sx in (-1, 1):
        p = V(sx * xs, 0.0, -0.05)
        beam(g, [p + V(0, -0.6, 0), p + V(0, h, 0)], 0.24, 0.24, mat=M_PLANK, col=(0.5, 0.47, 0.43), rng=rng, jag=(0, 0.04))
        posts.append(p)
        for y in (1.25, 1.36, 1.47):
            ring = [p + V(math.cos(t) * 0.15, y + 0.02 * math.sin(t), math.sin(t) * 0.15) for t in np.linspace(0, 2 * math.pi, 9)]
            rope(g, ring, 0.026)
        # a stay from the post top back to a stake behind it
        st = p + V(sx * 0.2, 0.0, 1.3)
        pole(g, st + V(0, -0.4, 0), st + V(0, 0.35, 0.05), 0.05, 0.04, rng, mat=M_PLANK, col=(0.55, 0.5, 0.45), sides=6)
        rope(g, [p + V(0, 1.7, 0.1), st + V(0, 0.3, 0)], 0.018)
    # dry-laid slate footing round the posts
    for k in range(9):
        x = -1.2 + k * 0.3
        slab(g, (x, 0.05 + 0.08 * (k % 2), 0.0 + rng.uniform(-0.15, 0.15)), (0.36, 0.14, 0.5), quat_y(rng.uniform(-0.3, 0.3)),
             rng, mat=M_SLATE, res=(2, 1, 2), round_r=0.02, rough=0.04, col_fn=sl, tile=0.7)
    return posts


def frayed_end(g, p, d, rng, col=(0.95, 0.85, 0.65)):
    """A cut rope end: the bright cut face and a few loose strands splaying out of it."""
    p, d = Vector(p), Vector(d).normalized()
    tube(g, [p, p + d * 0.03], [0.03, 0.03], 5, M_CLOTH, col, tile=0.1)
    side = d.orthogonal().normalized()
    for k in range(5):
        a = k * 1.3
        o = (side * math.cos(a) + d.cross(side) * math.sin(a)) * 0.02
        tube(g, [p + d * 0.02 + o, p + d * 0.1 + o * 2.5 + V(0, -0.03, 0)], [0.006, 0.003], 3, M_CLOTH, col, tile=0.1)


def site_rope_bridge(rng):
    """Footprint r <= 2.2 (the gap at local -Z: the ground falls away past z ~ -1.6; the far anchor
    `site_rope_bridge_far` stands across it). Masses: the posts + pier (0, 0.2, 1.4 x 0.6). The near
    anchor of the colony's rope bridge to the east, CUT from this side in the war: two squared posts
    in a slate footing, the main ropes and hand ropes all sliced through a hand's breadth past the
    posts (bright cut ends, frayed strands), the axe left bitten in the right post, two deck planks
    still lashed at the brink."""
    b = Builder()
    g = G(b)
    sl = stone_fn(SLATE, rng, moss=0.15, damp_h=0.5, y0=-0.3)
    mound(g, (0.0, -0.05, 0.5), 1.9, 1.5, 0.18, rng, mat=M_EARTH, col_fn=peat_fn(rng, base=(0.75, 0.7, 0.62), grass=0.7),
          tile=1.4, rings=5, seg=20, skirt=0.3)
    posts = bridge_posts(g, rng, sl)
    # Main ropes (at the deck) and hand ropes (at the post tops): each cut short past the post,
    # the stub sagging over the brink toward the far side.
    for p in posts:
        for y, ln in ((1.36, 0.9), (1.75, 0.55)):
            a = p + V(0.0, y, -0.12)
            e = a + V(0.0, -0.35 - 0.3 * (y < 1.5), -ln)
            rope(g, [a, a.lerp(e, 0.5) + V(0, -0.06, 0), e], 0.028 if y < 1.5 else 0.02)
            frayed_end(g, e, e - a, rng)
    # Deck stub at the brink: the first planks, still lashed to the cut main ropes, broken off.
    for k, (z, l) in enumerate(((-0.62, 1.6), (-0.92, 1.5), (-1.24, 1.1))):
        board(g, V(0.05 * k, 0.86 - 0.12 * k, z), V(1, 0, 0.05 * k), V(0, 1, 0.2 * k), l, 0.26, 0.05, mat=M_PLANK,
              col=(0.66, 0.64, 0.6), rng=rng, jag=(0.12, 0.12))
    # The axe bitten into the right post: an iron head (rusted), a grey haft.
    ap = posts[1] + V(-0.12, 1.0, -0.13)
    lbox(g, tuple(ap), (0.16, 0.12, 0.03), quat_y(0.6) @ quat_z(-0.2), M_IRON, (0.4, 0.3, 0.25), tile=0.2)
    tube(g, [ap + V(-0.06, 0.02, -0.05), ap + V(-0.55, -0.3, -0.45)], [0.022, 0.02], 6, M_PLANK, (0.62, 0.6, 0.55), tile=0.3)
    # Brink rocks.
    for k in range(7):
        x = -1.5 + k * 0.5
        stone(g, (x + rng.uniform(-0.1, 0.1), 0.0, -1.45 + rng.uniform(-0.2, 0.2)), (0.3, 0.2, 0.26), rng, mat=M_SLATE,
              detail=1, rough=0.12, cuts=2, col_fn=sl, tile=0.7)
    return b


def site_rope_bridge_far(rng):
    """Footprint r <= 1.6 (the gap at local -Z, facing back across it). Masses: the posts (0, 0,
    1.1 x 0.45). The far anchor of the cut rope bridge: two posts in a slate footing, and the
    whole bridge hanging from them down the far wall of the gap - two main ropes running over the
    lip and straight down with the deck planks still lashed between them like a ladder (some
    gone, some hanging by one end), the hand ropes tangled beside them, the cut ends frayed at
    the bottom, 7u down."""
    b = Builder()
    g = G(b)
    sl = stone_fn(SLATE, rng, moss=0.2, damp_h=0.5, y0=-0.3)
    mound(g, (0.0, -0.05, 0.4), 1.5, 1.2, 0.16, rng, mat=M_EARTH, col_fn=peat_fn(rng, base=(0.75, 0.7, 0.62), grass=0.7),
          tile=1.4, rings=5, seg=18, skirt=0.3)
    posts = bridge_posts(g, rng, sl, h=1.75)
    # The hanging run (shared by both main ropes): over the lip, then down the face.
    run = [(0.0, 1.36, -0.12), (0.0, 0.55, -0.85), (0.0, 0.06, -1.3), (0.0, -0.6, -1.5), (0.0, -2.0, -1.75),
           (0.0, -3.6, -2.0), (0.0, -5.2, -2.2), (0.0, -6.8, -2.35)]
    mains = []
    for k, p in enumerate(posts):
        sx = -1 if k == 0 else 1
        pts = [V(p.x * (1.0 if i < 2 else 0.62) + 0.04 * math.sin(i * 1.7 + k), y + (0.08 * k if i > 2 else 0), z) for i, (_, y, z)
               in enumerate(run)]
        pts[0] = p + V(0, 1.36, -0.12)
        rope(g, pts, 0.03)
        frayed_end(g, pts[-1], pts[-1] - pts[-2], rng)
        mains.append(pts)
        # hand rope: off the post top, tangled down beside the main one
        hp = p + V(0, 1.7, -0.12)
        hand = [hp, hp + V(0, -0.6, -0.6), V(sx * 0.9, 0.12, -1.32), V(sx * 1.0, -1.1, -1.55), V(sx * 0.7, -2.4, -1.8),
                V(sx * 0.95, -3.4, -1.95), V(sx * 0.85, -4.3, -2.1)]
        rope(g, hand, 0.02)
        frayed_end(g, hand[-1], hand[-1] - hand[-2], rng)
    # Lip planks lying over the edge, then the deck hanging as a ladder down the face.
    for k, (z, y) in enumerate(((-0.75, 0.62), (-1.05, 0.32))):
        board(g, V(0, y, z), V(1, 0, 0), V(0, 0.8, -0.55), 1.15, 0.26, 0.05, mat=M_PLANK, col=(0.66, 0.64, 0.6), rng=rng)

    def on_rope(pts, y):
        for a, c in zip(pts[2:], pts[3:]):
            if c.y <= y <= a.y:
                return a.lerp(c, (a.y - y) / max(a.y - c.y, 1e-4))
        return pts[-1]
    y = -0.35
    k = 0
    while y > -6.4:
        l, r = on_rope(mains[0], y), on_rope(mains[1], y + (0.25 if k == 6 else 0.0))
        k += 1
        y -= rng.uniform(0.36, 0.46)
        if k in (4, 9, 10):
            continue  # fallen out
        if k == 7:  # hanging by its left end only
            c = l + V(0.08, -0.4, -0.03)
            board(g, c, V(0.12, -1, 0.02), V(0, 0, -1), 0.95, 0.24, 0.045, mat=M_PLANK, col=(0.6, 0.58, 0.55), rng=rng,
                  jag=(0.0, 0.12))
            continue
        c = (l + r) / 2 + V(0, 0, -0.05)
        d = (r - l).normalized()
        board(g, c, d, V(0, 0, -1),
              (r - l).length + 0.25, 0.24, 0.045, mat=M_PLANK, col=scale((0.66, 0.64, 0.6), rng.uniform(0.8, 1.0)), rng=rng,
              jag=(0.04, 0.06))
        for e in (l, r):  # lashings
            ring = [e + V(math.cos(t) * 0.05, 0.0, math.sin(t) * 0.05) + V(0, 0.04 * math.sin(2 * t), 0) for t in
                    np.linspace(0, 2 * math.pi, 7)]
            rope(g, ring, 0.008, (0.65, 0.55, 0.38))
    for k in range(5):
        x = -1.2 + k * 0.6
        stone(g, (x + rng.uniform(-0.1, 0.1), 0.0, -1.2 + rng.uniform(-0.15, 0.15)), (0.28, 0.2, 0.25), rng, mat=M_SLATE,
              detail=1, rough=0.12, cuts=2, col_fn=sl, tile=0.7)
    return b


def site_old_ones_door(rng):
    """Footprint r <= 3.7 (the rock face at local +Z, backed into the slope). Masses: the outcrop
    (0, 2.0, 3.0 x 1.2). A door the Old Ones cut into a granite face: the face itself a heap of huge
    lichen-crusted blocks; a tall recessed door frame (jambs + a lintel carved with rings and an
    ochre zig-zag), the door one sealed slab; five rune slabs set in an arc on the ground before it,
    each cut with its own sign."""
    b = Builder()
    g = G(b)
    fn = stone_fn(GRANITE, rng, moss=0.25, damp_h=0.6, y0=-0.3)
    # The outcrop: big rounded blocks heaped behind the door.
    for c, s in (((-1.9, 1.3, 2.2), (1.6, 3.0, 1.4)), ((1.9, 1.1, 2.1), (1.5, 2.6, 1.3)), ((0.0, 2.6, 2.5), (2.6, 1.6, 1.4)),
                 ((-2.9, 0.5, 1.4), (0.9, 1.3, 1.0)), ((2.9, 0.4, 1.3), (0.9, 1.0, 1.0)), ((0.0, 1.2, 2.9), (2.0, 2.6, 1.0))):
        slab(g, c, s, quat_y(rng.uniform(-0.1, 0.1)) @ quat_x(rng.uniform(-0.05, 0.05)), rng, mat=M_GRANITE, res=(6, 7, 4),
             round_r=0.3, rough=0.09, col_fn=fn, tile=2.0, cuts=2)
    # Door frame: two jambs, the lintel (ochre zig-zag, carved rings), the sealed slab recessed.
    for sx in (-1, 1):
        slab(g, (sx * 0.78, 1.15, 1.25), (0.42, 2.7, 0.55), quat_y(0), rng, mat=M_GRANITE, res=(2, 8, 2), round_r=0.05,
             rough=0.015, col_fn=fn, tile=1.2)
    och = ochre_band(V(0, 2.75, 1.0), V(0, 0, -1), 2.6, 2.92)
    slab(g, (0.0, 2.72, 1.22), (2.1, 0.5, 0.62), quat_y(0), rng, mat=M_GRANITE, res=(7, 2, 2), round_r=0.05, rough=0.015,
         col_fn=stone_fn(GRANITE, rng, moss=0.2, damp_h=0.6, y0=-0.3, ochre=och), tile=1.2)
    for x in (-0.6, 0.6):
        carved_rings(g, V(x, 2.72, 0.905), V(0, 0, -1), (0.06, 0.12, 0.18))
    slab(g, (0.0, 1.15, 1.42), (1.15, 2.4, 0.3), quat_y(0), rng, mat=M_GRANITE, res=(4, 8, 2), round_r=0.03, rough=0.01,
         col_fn=stone_fn((0.8, 0.82, 0.86), rng, moss=0.1, damp_h=0.6, y0=-0.3), tile=1.2)
    # The door's sign: a big ring and a vertical stroke - the iron voice - cut into the slab.
    carved_rings(g, V(0.0, 1.45, 1.26), V(0, 0, -1), (0.2, 0.32), depth=0.016)
    tube(g, [V(0, 0.45, 1.26), V(0, 1.1, 1.26)], [0.016, 0.016], 4, M_GRANITE, (0.15, 0.15, 0.16), tile=0.2)
    # Threshold.
    slab(g, (0.0, 0.0, 1.0), (1.9, 0.25, 0.6), quat_y(0), rng, mat=M_GRANITE, res=(5, 1, 2), round_r=0.04, rough=0.02,
         col_fn=fn, tile=1.0)
    # Rune slabs in an arc in front, each with its own sign (rings / strokes / a gong-and-bar).
    signs = [(0.07, 0.14), (0.1,), (0.05, 0.1, 0.15), (0.12,), (0.08, 0.16)]
    for k, rr in enumerate(signs):
        a = math.pi * (0.2 + 0.15 * k) + math.pi
        p = V(math.cos(a) * 2.4, 0.04, 0.6 + math.sin(a) * 2.2)
        rot = quat_y(-a - math.pi / 2)
        slab(g, tuple(p), (0.7, 0.16, 0.55), rot, rng, mat=M_GRANITE, res=(3, 1, 3), round_r=0.04, rough=0.02,
             col_fn=stone_fn(GRANITE, rng, moss=0.4, damp_h=0.2, y0=-0.1), tile=0.8)
        top = p + V(0, 0.085, 0)
        for r in rr:
            ring = [top + rot @ V(math.cos(t) * r * 1.4, 0, math.sin(t) * r) for t in np.linspace(0, 2 * math.pi, 15)]
            tube(g, ring, [0.012] * 15, 4, M_GRANITE, (0.15, 0.15, 0.16), tile=0.2, cap=False)
        if k % 2:
            tube(g, [top + rot @ V(-0.25, 0, 0), top + rot @ V(0.25, 0, 0)], [0.012, 0.012], 4, M_GRANITE,
                 (0.15, 0.15, 0.16), tile=0.2)
    for p in ((-2.6, 0, -0.8), (2.5, 0, -1.0), (-1.2, 0, -2.6), (1.4, 0, -2.4)):
        sedge(g, p, rng, n=8, h=0.45, col=(0.6, 0.58, 0.42))
    return b


def helmet(g, c, rot, rng, s=1.0):
    """A colony kettle helmet: a bowl with a wide flat brim, rusted."""
    c = Vector(c)
    rf = lambda p, n: mix((0.55, 0.5, 0.46), (0.75, 0.45, 0.28), 0.5 + 0.5 * math.sin(p.x * 23 + p.z * 17))  # noqa: E731
    dome(g, tuple(c), 0.16 * s, rot, M_RUST, rf, tile=0.3, rings=4, seg=14, squash=0.85)
    ring = [c + rot @ V(math.cos(t) * 0.25 * s, 0.0, math.sin(t) * 0.25 * s) for t in np.linspace(0, 2 * math.pi, 19)]
    tube(g, ring, [0.012 * s] * 19, 4, M_RUST, (0.6, 0.5, 0.42), tile=0.2, cap=False)
    for k in range(18):
        t0, t1 = 2 * math.pi * k / 18, 2 * math.pi * (k + 1) / 18
        q = [c + rot @ V(math.cos(t0) * 0.15 * s, 0, math.sin(t0) * 0.15 * s), c + rot @ V(math.cos(t1) * 0.15 * s, 0, math.sin(t1) * 0.15 * s),
             c + rot @ V(math.cos(t1) * 0.25 * s, -0.01, math.sin(t1) * 0.25 * s), c + rot @ V(math.cos(t0) * 0.25 * s, -0.01, math.sin(t0) * 0.25 * s)]
        nn = rot @ V(0, 1, 0)
        if (q[1] - q[0]).cross(q[3] - q[0]).dot(nn) < 0:
            q = q[::-1]
        g.poly(q, [(p.x * 3, p.z * 3) for p in q], [nn] * 4, [(0.58, 0.48, 0.4)] * 4, M_RUST)
        g.poly(q[::-1], [(p.x * 3, p.z * 3) for p in q[::-1]], [-nn] * 4, [(0.45, 0.38, 0.32)] * 4, M_RUST)


def cleaver(g, grip, d, rng, s=1.0):
    """An ork cleaver: a wide, crude, notched blade (black iron) on a bound haft."""
    grip, d = Vector(grip), Vector(d).normalized()
    side = d.cross(V(0, 1, 0))
    if side.length < 1e-3:
        side = V(1, 0, 0)
    side.normalize()
    tube(g, [grip, grip + d * 0.3 * s], [0.025 * s, 0.028 * s], 6, M_HIDE, (0.28, 0.2, 0.14), tile=0.2)
    c = grip + d * (0.3 + 0.32) * s
    nrm = d.cross(side).normalized()
    pts = [grip + d * 0.3 * s + side * 0.03 * s, c + d * 0.3 * s + side * 0.02 * s, c + d * 0.32 * s - side * 0.22 * s,
           c - d * 0.1 * s - side * 0.25 * s, grip + d * 0.3 * s - side * 0.12 * s]
    for sgn in (1, -1):
        q = [p + nrm * 0.012 * sgn for p in pts]
        if (q[1] - q[0]).cross(q[2] - q[0]).dot(nrm * sgn) < 0:
            q = q[::-1]
        for i in range(1, len(q) - 1):
            tri = [q[0], q[i], q[i + 1]]
            g.poly(tri, [(p.dot(d) * 3, p.dot(side) * 3) for p in tri], [nrm * sgn] * 3, [(0.3, 0.27, 0.25)] * 3, M_IRON)
    for i in range(len(pts)):
        a, bb = pts[i], pts[(i + 1) % len(pts)]
        q = [a + nrm * 0.012, bb + nrm * 0.012, bb - nrm * 0.012, a - nrm * 0.012]
        out = ((a + bb) / 2 - sum(pts, Vector()) / len(pts)).normalized()
        if (q[1] - q[0]).cross(q[3] - q[0]).dot(out) < 0:
            q = q[::-1]
        g.poly(q, [(0, 0), (1, 0), (1, 0.05), (0, 0.05)], [out] * 4, [(0.38, 0.34, 0.3)] * 4, M_IRON)


def site_scree_battlefield(rng):
    """Footprint r <= 3.6 (the scree falls from local +Z). Masses: the scree core (0, 1.4, 2.0 x 1.2).
    The first war, under the scree in a gully: a fan of slate and granite rubble with colony kettle
    helmets half-buried in it, ork cleavers and a snapped pike sticking out, a shield's iron boss and
    rim (the boards long rotted), a few bones; a rusted helmet set on a pike butt as a marker."""
    b = Builder()
    g = G(b)
    sl = stone_fn(SLATE, rng, moss=0.08, damp_h=0.4, y0=-0.2)
    gr = stone_fn(GRANITE, rng, moss=0.15, damp_h=0.4, y0=-0.2)
    mound(g, (0.0, -0.1, 1.6), 3.1, 2.1, 0.55, rng, mat=M_SLATE, col_fn=sl, tile=0.8, rings=6, seg=22, skirt=0.2,
          rough=0.35, power=0.7, edge=0.3)
    mound(g, (0.3, -0.05, -0.6), 2.6, 1.5, 0.3, rng, mat=M_SLATE, col_fn=sl, tile=1.0, rings=5, seg=20, skirt=0.15,
          rough=0.3)
    for _ in range(110):
        p = V(rng.uniform(-2.8, 2.8), 0.0, rng.uniform(-1.8, 3.2))
        h = 0.55 * max(0.0, 1 - ((p.x / 3.1) ** 2 + ((p.z - 1.6) / 2.1) ** 2)) ** 0.7
        h = max(h, 0.3 * max(0.0, 1 - ((p.x - 0.3) / 2.6) ** 2 - ((p.z + 0.6) / 1.5) ** 2))
        r = rng.uniform(0.1, 0.38)
        stone(g, (p.x, h + r * 0.2, p.z), (r, r * rng.uniform(0.5, 0.8), r * rng.uniform(0.7, 1.0)), rng,
              mat=M_SLATE if rng.uniform() < 0.6 else M_GRANITE, detail=1, rough=0.12, cuts=2,
              col_fn=sl if rng.uniform() < 0.6 else gr, tile=0.6)
    helmet(g, (-0.8, 0.36, 0.3), quat_x(0.5) @ quat_z(0.3), rng)
    helmet(g, (1.1, 0.25, -0.6), quat_x(-0.3) @ quat_z(-0.6), rng)
    helmet(g, (0.2, 0.6, 1.6), quat_x(0.9) @ quat_z(0.1), rng)
    cleaver(g, V(-1.5, 0.45, 1.5), V(0.5, 0.65, -0.4), rng, s=1.2)
    cleaver(g, V(0.6, 0.12, -1.1), V(0.9, 0.15, 0.5), rng)
    cleaver(g, V(1.6, 0.42, 1.2), V(-0.2, 0.9, -0.3), rng, s=1.1)
    # The snapped pike, the colony marker: a pike butt planted, a helmet hung on it.
    pk = V(-1.9, 0.0, -0.4)
    pole(g, pk + V(0, -0.4, 0), pk + V(0.12, 1.55, 0.04), 0.03, 0.026, rng, mat=M_PLANK, col=(0.6, 0.58, 0.55), sides=6)
    helmet(g, pk + V(0.2, 1.48, 0.04), quat_z(-1.1) @ quat_x(0.2), rng, s=0.95)
    tube(g, [V(0.9, 0.35, 0.3), V(2.2, 0.45, 1.3)], [0.028, 0.026], 6, M_PLANK, (0.55, 0.53, 0.5), tile=0.3)
    lbox(g, (2.3, 0.47, 1.38), (0.04, 0.03, 0.28), quat_y(-0.9), M_RUST, (0.6, 0.5, 0.42), tile=0.2)
    # Shield: the iron boss and a bent rim lying flat.
    sc = V(-0.3, 0.12, -1.0)
    dome(g, tuple(sc), 0.1, quat_x(0.1), M_RUST, lambda p, n: (0.55, 0.42, 0.32), tile=0.2, rings=3, seg=12, squash=0.7)
    rim = [sc + V(math.cos(t) * 0.42, -0.04 + 0.04 * math.sin(3 * t), math.sin(t) * 0.38) for t in np.linspace(0, 1.6 * math.pi, 17)]
    tube(g, rim, [0.012] * 17, 4, M_RUST, (0.55, 0.45, 0.38), tile=0.2, cap=False)
    # Bones: a long bone and rib arcs between the stones.
    tube(g, [V(0.5, 0.42, 0.6), V(0.95, 0.45, 0.75)], [0.03, 0.028], 6, M_STONE, BONE, tile=0.2)
    for k in range(3):
        p = V(-0.4 + k * 0.12, 0.3, 0.9)
        tube(g, [p, p + V(0.1, 0.12, 0.05), p + V(0.25, 0.1, 0.08)], [0.012, 0.012, 0.008], 4, M_STONE, BONE, tile=0.2)
    for p in ((-2.6, 0, -1.6), (2.7, 0, -1.4), (-2.9, 0, 2.2)):
        sedge(g, p, rng, n=7, h=0.4, col=(0.6, 0.58, 0.42))
    return b


MODELS = {
    "site_mission_chapel": site_mission_chapel,
    "site_ork_barrows": site_ork_barrows,
    "site_eel_weir": site_eel_weir,
    "site_colony_causeway": site_colony_causeway,
    "site_peat_cutting": site_peat_cutting,
    "site_clan_gong": site_clan_gong,
    "site_signal_tower": site_signal_tower,
    "site_rope_bridge": site_rope_bridge,
    "site_old_ones_door": site_old_ones_door,
    "site_scree_battlefield": site_scree_battlefield,
    "site_rope_bridge_far": site_rope_bridge_far,
}

if __name__ == "__main__":
    clear_scene()
    objs = []
    report = {}
    only = set(sys.argv[sys.argv.index("--") + 1:]) if "--" in sys.argv else set()
    for i, (name, fn) in enumerate(MODELS.items()):
        if only and name not in only:
            continue
        b = fn(np.random.default_rng(6100 + i))
        report[name] = bounds(b)
        objs.append(b.build(name, MATS))
    export_glb(OUT / "wild_sites.glb", objs)
    (OUT / "wild_sites_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    for k, v in report.items():
        print(f"{k}: {v}")
    print("WILD_SITES_DONE")
