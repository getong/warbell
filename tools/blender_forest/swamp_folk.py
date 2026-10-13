"""The swamp's living folk -> swamp_folk.glb (src/witch.rs, src/ork_graveyard.rs).

Design: docs/superpowers/specs/2026-10-13-zywa-wyspa-design.md §2 items 6-7 (Old Seffa, the Field of
the Answered). Seffa herself is a townsperson body (people.glb, `peasant_model`) on the shared biped
rig; this script only makes her things and her yard, plus the ork graveyard's rows. Same palette and
helpers as wild_sites.py (scanned s_* sets, peat, rotten wood, rust, bone).

SEFFA'S YARD (world units, base y=0, front = local -Z = the visitor's side)
  sf_trade_stone   - the silent-trade stone outside her wattle fence: a squat granite block sunk in
                     peat, a hollow worn in its top, pebbles stacked on its shoulder; the fence runs
                     behind it (z +0.8) with a gap for the wicket at x -0.6..0.6.
  sf_wicket        - the hurdle wicket for that gap, hinged at its origin, the panel running to -X
                     (the game swings it open once she trades with you).
  sf_offer_herbs   - an ingredient left on the stone: a tied bundle of marsh herbs (base y=0).
  sf_brew_jar      - what lies there at dawn: a stoppered clay jar, a rag tied over the bung.
  sf_herb_rack     - a drying rack: two forked posts, a pole, herb bundles hung head-down, a basket.
  sf_goat_stake    - a tether stake, a trodden ring of mud, a hay pile and a water trough.
HER HAND PROPS (RIG units: the townsfolk rig is scaled ~0.74, so these are drawn that much larger)
  sf_staff         - a gnarled blackthorn staff, the grip at the origin, the foot at y -0.9.
  sf_basket        - a wicker basket hanging from its handle apex (origin), the body below (-Y).
THE FIELD OF THE ANSWERED (world units)
  og_long_barrow   - an old long barrow, turfed and grassed, kerbed with set stones, a notched
                     iron stone at its head (local -Z end).
  og_iron_stone    - a lone notched iron grave stone: a black-iron slab in a granite footing, tally
                     cuts down both edges, rust bleeding into the stone; pebbles laid round it.
  og_fresh_mound_a - a fresh grave: raw black peat, clods, an iron stone at the head, a bowl of fish.
  og_fresh_mound_b - a fresh grave: a cleaver laid on it, a stake with a bone charm, a bowl.
  og_fish_bowl     - a clay bowl with two fish, set down on the ground.

    blender -b --factory-startup --python tools/blender_forest/swamp_folk.py
"""
import json
import math
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
from common import OUT, clear_scene, export_glb  # noqa: E402
from geo import G, frustum, quat_x, quat_y, quat_z  # noqa: E402
from meshkit import Builder  # noqa: E402
import wild_sites as WS  # noqa: E402
from wild_sites import (M_GRANITE, M_PEAT, M_ROT, M_RUST, MATS, BONE, BLACK_IRON, ROT_WOOD, bowl, cleaver,  # noqa: E402
                        fish, kerb, peat_fn, rope, sedge, skull, stone_fn, turf_fn, tusk)
from wayside_models import (M_BARK, M_CLOTH, M_EARTH, M_HIDE, M_IRON, M_STONE, M_THATCH, V, beam, bounds,  # noqa: E402
                            lashing, lbox, mix, mound, pole, scale, smoothstep, stone, tube, wattle, Noise)
from landmarks_kit import lathe  # noqa: E402

CLAY = (0.66, 0.46, 0.33)
TWINE = (0.7, 0.6, 0.42)
HERB = (0.42, 0.48, 0.24)
HERB_DRY = (0.56, 0.52, 0.3)
RAG = (0.62, 0.55, 0.42)
WICKER = (0.78, 0.62, 0.4)


# ─────────────────────────────────────────────────────────────── small pieces
def herb_bundle(g, top, d, rng, n=9, length=0.32, col=HERB, flower=None):
    """A bunch of herb stems tied at `top`, running along `d` (leafy ends spread at the far end)."""
    top, d = V(*top), V(*d).normalized()
    side = d.cross(V(0, 1, 0))
    if side.length < 1e-3:
        side = V(1, 0, 0)
    side.normalize()
    up = side.cross(d).normalized()
    for _ in range(n):
        a = rng.uniform(0, 2 * math.pi)
        spread = rng.uniform(0.02, 0.07)
        ln = length * rng.uniform(0.75, 1.1)
        tip = top + d * ln + (side * math.cos(a) + up * math.sin(a)) * spread
        mid = top + d * ln * 0.45 + (side * math.cos(a) + up * math.sin(a)) * spread * 0.35
        c = scale(col, rng.uniform(0.75, 1.15))
        tube(g, [top, mid, tip], [0.006, 0.005, 0.003], 3, M_THATCH, c, tile=0.3, cap=False)
        # leaves: small flattened stones along the outer half
        for f in (0.55, 0.75, 0.95):
            p = top.lerp(tip, f)
            stone(g, tuple(p), (0.022, 0.006, 0.012), rng, mat=M_THATCH, detail=0, rough=0.05, cuts=0,
                  rot=quat_y(a), col_fn=lambda q, nn, c=c: scale(c, 0.9), tile=0.2)
        if flower and rng.uniform(0, 1) < 0.5:
            stone(g, tuple(tip), (0.014, 0.012, 0.014), rng, mat=M_THATCH, detail=0, rough=0.1, cuts=0,
                  col_fn=lambda q, nn: flower, tile=0.2)
    # the tie
    ring = [top + d * 0.03 + (side * math.cos(t) + up * math.sin(t)) * 0.022 for t in np.linspace(0, 2 * math.pi, 9)]
    tube(g, ring, [0.006] * 9, 4, M_CLOTH, TWINE, tile=0.1, cap=False)


def clay_jar(g, c, s, rng, rag=True):
    """A stoppered clay jar (s_earth), a rag tied over the bung with twine."""
    nz = Noise(rng, 3, 3.0)
    col = lambda p, n: scale(CLAY, (0.82 + 0.18 * smoothstep(0.0, 0.2 * s, p.y - c[1])) * (0.92 + 0.12 * nz(p * 8)))
    prof = [(0.0, 0.0), (0.06, 0.0), (0.085, 0.03), (0.1, 0.09), (0.095, 0.15), (0.06, 0.2), (0.042, 0.215),
            (0.048, 0.235), (0.04, 0.245), (0.03, 0.24)]
    lathe(g, [(r * s, y * s) for r, y in prof], 14, c, M_EARTH, col, tile=0.3)
    cx, cy, cz = c
    stone(g, (cx, cy + 0.245 * s, cz), (0.034 * s, 0.022 * s, 0.034 * s), rng, mat=M_BARK, detail=1, rough=0.05, cuts=0,
          col_fn=lambda p, n: (0.55, 0.42, 0.3), tile=0.2)
    if rag:
        top = V(cx, cy + 0.255 * s, cz)
        for k in range(6):
            a = k * math.pi / 3 + rng.uniform(-0.2, 0.2)
            o = V(math.cos(a), 0, math.sin(a))
            q = [top + o * 0.005, top + o * 0.05 * s + V(0, -0.012 * s, 0), top + o * 0.055 * s + V(0, -0.05 * s, 0)]
            tube(g, q, [0.018 * s, 0.014 * s, 0.006 * s], 3, M_CLOTH, scale(RAG, rng.uniform(0.8, 1.0)), tile=0.15, cap=False)
        ring = [V(cx, cy + 0.222 * s, cz) + V(math.cos(t), 0, math.sin(t)) * 0.046 * s for t in np.linspace(0, 2 * math.pi, 11)]
        tube(g, ring, [0.004 * s] * 11, 4, M_CLOTH, TWINE, tile=0.1, cap=False)


def iron_stone(g, c, yaw, rng, h=0.85, w=0.42, notches=7, lean=0.0):
    """A notched black-iron grave slab set into a granite footing; tally cuts down both edges, rust
    bleeding down the slab and stained onto the footing."""
    c = V(*c)
    rot = quat_y(yaw) @ quat_z(lean)
    nz = Noise(rng, 3, 4.0)
    ks = stone_fn((0.85, 0.85, 0.8), rng, moss=0.5, damp_h=0.25, y0=-0.05)
    stone(g, tuple(c + V(0, 0.04, 0)), (w * 0.85, 0.16, 0.26), rng, mat=M_GRANITE, detail=1, rough=0.12, cuts=2,
          rot=quat_y(yaw + rng.uniform(-0.2, 0.2)), col_fn=lambda p, n: mix(ks(p, n), (0.42, 0.22, 0.12),
                                                                          0.35 * smoothstep(0.1, 0.2, p.y - c.y)),
          tile=0.6)
    rust = lambda p, n: mix(BLACK_IRON, (0.42, 0.2, 0.1), max(0.0, min(1.0, 0.25 + 0.6 * nz(p * 3) - 0.4 * (p.y - c.y) / h)))
    th = 0.05
    # the slab, a touch narrower toward the top
    pts = []
    for k in range(notches + 1):
        f = k / notches
        y = 0.1 + (h - 0.1) * f
        ww = w * (1.0 - 0.18 * f) * 0.5
        cut = 0.045 if (k % 2 == 1 and k < notches) else 0.0
        pts.append((ww - cut, y))
    right = [rot @ V(x, y, 0) + c for x, y in pts]
    left = [rot @ V(-x, y, 0) + c for x, y in pts]
    for sgn in (1, -1):
        off = rot @ V(0, 0, th * 0.5 * sgn)
        poly = [p + off for p in right] + [p + off for p in left[::-1]]
        n = rot @ V(0, 0, sgn)
        cen = sum(poly, V(0, 0, 0)) / len(poly)
        for i in range(len(poly)):
            a, b_ = poly[i], poly[(i + 1) % len(poly)]
            tri = [cen, a, b_] if sgn > 0 else [cen, b_, a]
            g.poly(tri, [(p.x * 2, p.y * 2) for p in tri], [n] * 3, [rust(p, n) for p in tri], M_IRON)
    # the edges
    ring = right + left[::-1]
    for i in range(len(ring)):
        a, b_ = ring[i], ring[(i + 1) % len(ring)]
        mid = (a + b_) * 0.5
        out = (mid - (c + V(0, h * 0.5, 0)))
        out.y *= 0.3
        out.normalize()
        q = [a + rot @ V(0, 0, th * 0.5), b_ + rot @ V(0, 0, th * 0.5), b_ - rot @ V(0, 0, th * 0.5), a - rot @ V(0, 0, th * 0.5)]
        if (q[1] - q[0]).cross(q[3] - q[0]).dot(out) < 0:
            q = q[::-1]
        g.poly(q, [(0, 0), (1, 0), (1, 0.05), (0, 0.05)], [out] * 4, [rust(p, out) for p in q], M_IRON)
    # a ring punched near the top (the answered's mark)
    rc = c + rot @ V(0, h * 0.78, th * 0.55)
    ring = [rc + rot @ V(math.cos(t) * 0.07, math.sin(t) * 0.07, 0) for t in np.linspace(0, 2 * math.pi, 13)]
    tube(g, ring, [0.009] * 13, 4, M_RUST, (0.3, 0.16, 0.08), tile=0.1, cap=False)


def pebbles(g, c, r, rng, n=10):
    c = V(*c)
    for _ in range(n):
        a = rng.uniform(0, 2 * math.pi)
        rr = r * rng.uniform(0.7, 1.05)
        stone(g, tuple(c + V(math.cos(a) * rr, 0.015, math.sin(a) * rr)), (0.05, 0.03, 0.04), rng, mat=M_GRANITE, detail=1,
              rough=0.1, cuts=1, col_fn=lambda p, n: scale((0.8, 0.79, 0.74), rng.uniform(0.6, 1.0)), tile=0.3)


def clods(g, c, rx, rz, h, rng, col_fn, n=14):
    for _ in range(n):
        a = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(0.15, 1.0)
        p = V(c[0] + math.cos(a) * r * rx * 0.95, h * max(0.0, 1 - r * r) ** 0.8 + 0.02, c[2] + math.sin(a) * r * rz * 0.9)
        stone(g, tuple(p), (0.07, 0.05, 0.06), rng, mat=M_PEAT, detail=1, rough=0.2, cuts=2, tile=0.4, col_fn=col_fn)


# ─────────────────────────────────────────────────────────────── Seffa's yard
def sf_trade_stone(rng):
    """Footprint r <= 3.3. Masses: the stone (0, 0, 0.45 x 0.35), the fence runs along z +0.8."""
    b = Builder()
    g = G(b)
    ks = stone_fn((0.82, 0.82, 0.78), rng, moss=0.35, damp_h=0.3, y0=-0.05, lichen=(0.88, 0.9, 0.78))
    pf = peat_fn(rng, base=(0.62, 0.55, 0.45), wet=0.6, grass=1.2, grass_col=(0.38, 0.46, 0.2))
    mound(g, (0.0, -0.06, 0.2), 3.3, 1.6, 0.08, rng, mat=M_EARTH, col_fn=pf, tile=1.2, rings=5, seg=24, skirt=0.2,
          power=0.5)
    # The stone: squat, flat-topped, sunk; the hollow in its top worn dark by years of things left.
    stone(g, (0.0, 0.15, 0.0), (0.5, 0.62, 0.38), rng, mat=M_GRANITE, detail=2, rough=0.1, cuts=2, rot=quat_y(0.3),
          col_fn=ks, tile=0.7, flat_y=0.4)
    stone(g, (0.02, 0.405, -0.02), (0.18, 0.012, 0.14), rng, mat=M_GRANITE, detail=1, rough=0.04, cuts=0,
          col_fn=lambda p, n: (0.2, 0.19, 0.17), tile=0.4)
    # A little stack of pebbles on its shoulder: one for each thing taken.
    for k in range(4):
        stone(g, (0.36 - 0.02 * k, 0.36 + 0.055 * k, 0.12), (0.07 - 0.012 * k, 0.03, 0.06 - 0.01 * k), rng, mat=M_GRANITE,
              detail=1, rough=0.06, cuts=1, col_fn=lambda p, n: (0.82, 0.8, 0.74), tile=0.3)
    # The wattle fence behind it, a gap for the wicket; the gate posts are stouter, a crossbar on top.
    wattle(g, V(-3.2, 0, 0.85), V(-0.62, 0, 0.8), rng, h=0.95, stake_gap=0.3)
    wattle(g, V(0.62, 0, 0.8), V(3.1, 0, 0.95), rng, h=0.95, stake_gap=0.3)
    for x in (-0.6, 0.6):
        pole(g, V(x, -0.35, 0.8), V(x + rng.uniform(-0.02, 0.02), 1.25, 0.8), 0.055, 0.045, rng, col=(0.7, 0.64, 0.55),
             sides=7)
    # charms on the left gate post: a bundle of rowan, a tied bone, a scrap of red cloth
    rope(g, [V(-0.6, 1.12, 0.74), V(-0.6, 0.95, 0.74)], r=0.006, col=TWINE)
    herb_bundle(g, (-0.6, 0.95, 0.74), (0, -1, 0), rng, n=6, length=0.2, col=(0.4, 0.36, 0.2), flower=(0.62, 0.14, 0.08))
    rope(g, [V(0.6, 1.15, 0.74), V(0.6, 1.0, 0.74)], r=0.006, col=TWINE)
    tube(g, [V(0.6, 1.0, 0.74), V(0.62, 0.86, 0.74)], [0.016, 0.012], 5, M_STONE, BONE, tile=0.1)
    tube(g, [V(0.62, 1.08, 0.73), V(0.66, 0.9, 0.72)], [0.018, 0.004], 3, M_CLOTH, (0.55, 0.14, 0.08), tile=0.1, cap=False)
    # A worn path through the wicket (bare trodden mud).
    mound(g, (0.0, -0.03, 0.4), 0.55, 1.3, 0.04, rng, mat=M_PEAT, col_fn=peat_fn(rng, base=(0.55, 0.48, 0.4), wet=0.5),
          tile=0.6, rings=3, seg=14, skirt=0.06)
    for p, n, h in (((-1.4, 0, -0.5), 9, 0.5), ((1.7, 0, -0.4), 8, 0.45), ((-2.6, 0, 0.4), 7, 0.55), ((2.6, 0, 0.5), 8, 0.5),
                    ((0.7, 0, -0.35), 5, 0.3)):
        sedge(g, p, rng, n=n, h=h, col=(0.55, 0.55, 0.3))
    return b


def sf_wicket(rng):
    """The hurdle wicket, hinged at the origin, the panel running to -X (1.18 long)."""
    b = Builder()
    g = G(b)
    wattle(g, V(-0.06, 0.08, 0), V(-1.12, 0.08, 0), rng, h=0.82, stake_gap=0.24)
    # two withy hinge rings round the post line + a latch loop
    for y in (0.3, 0.8):
        ring = [V(math.cos(t) * 0.06, y, math.sin(t) * 0.06) for t in np.linspace(0, 2 * math.pi, 9)]
        tube(g, ring, [0.01] * 9, 4, M_BARK, (0.62, 0.55, 0.4), tile=0.2, cap=False)
    ring = [V(-1.14 + math.cos(t) * 0.05, 0.6, math.sin(t) * 0.05) for t in np.linspace(0, 2 * math.pi, 9)]
    tube(g, ring, [0.008] * 9, 4, M_CLOTH, TWINE, tile=0.2, cap=False)
    return b


def sf_offer_herbs(rng):
    b = Builder()
    g = G(b)
    herb_bundle(g, (-0.14, 0.03, 0.0), (1, 0.05, 0.12), rng, n=11, length=0.3, col=HERB, flower=(0.85, 0.82, 0.6))
    herb_bundle(g, (-0.1, 0.05, 0.05), (1, 0.08, -0.25), rng, n=6, length=0.26, col=(0.36, 0.42, 0.22))
    return b


def sf_brew_jar(rng):
    b = Builder()
    g = G(b)
    clay_jar(g, (0.0, 0.0, 0.0), 1.0, rng)
    # a sprig tucked under the twine: the brew's mark
    herb_bundle(g, (0.05, 0.2, 0.02), (0.4, -0.2, 0.5), rng, n=4, length=0.12, col=(0.32, 0.4, 0.2))
    return b


def sf_herb_rack(rng):
    """Footprint r <= 1.3: two forked posts 1.5 apart (x), a pole, bundles hung head-down."""
    b = Builder()
    g = G(b)
    col = (0.72, 0.66, 0.56)
    for x in (-0.75, 0.75):
        pole(g, V(x, -0.35, 0), V(x + rng.uniform(-0.03, 0.03), 1.45, 0), 0.05, 0.04, rng, col=col, sides=7)
        for s in (-1, 1):  # the fork
            pole(g, V(x, 1.38, 0), V(x + s * 0.09, 1.6, rng.uniform(-0.03, 0.03)), 0.03, 0.022, rng, col=col, sides=5)
    pole(g, V(-0.95, 1.5, 0.0), V(0.95, 1.52, 0.02), 0.03, 0.028, rng, col=(0.66, 0.6, 0.5), sides=6)
    for x in (-0.75, 0.75):
        lashing(g, V(x, 1.5, 0.0), V(1, 0, 0), 0.04, rng)
    cols = [HERB_DRY, HERB, (0.5, 0.42, 0.26), (0.38, 0.44, 0.24), HERB_DRY, (0.46, 0.38, 0.3), HERB]
    flowers = [None, (0.55, 0.42, 0.62), None, (0.82, 0.7, 0.3), None, None, (0.8, 0.78, 0.66)]
    for k in range(7):
        x = -0.6 + k * 0.2 + rng.uniform(-0.03, 0.03)
        drop = rng.uniform(0.08, 0.16)
        rope(g, [V(x, 1.5, 0.0), V(x, 1.5 - drop, 0.0)], r=0.005, col=TWINE)
        herb_bundle(g, (x, 1.5 - drop, 0.0), (rng.uniform(-0.1, 0.1), -1, rng.uniform(-0.1, 0.1)), rng, n=8,
                    length=rng.uniform(0.3, 0.42), col=cols[k], flower=flowers[k])
    # a flat basket of cut herbs at the foot + a few fallen stems
    bc = V(0.25, 0.0, 0.42)
    frustum(g, 0.2, 0.27, 0.0, 0.11, 14, M_BARK, WICKER, tile=0.25, centre=(bc.x, 0, bc.z))
    for k in range(3):
        herb_bundle(g, (bc.x - 0.15 + 0.1 * k, 0.1, bc.z - 0.05), (1, 0.1, 0.3 - 0.2 * k), rng, n=6, length=0.22, col=HERB)
    mound(g, (0.0, -0.04, 0.1), 1.2, 0.8, 0.05, rng, mat=M_PEAT, col_fn=peat_fn(rng, base=(0.58, 0.5, 0.42), wet=0.5,
                                                                                  grass=0.8), tile=0.7, rings=3, seg=14)
    return b


def sf_goat_stake(rng):
    """Footprint r <= 1.6: a tether stake in a trodden ring, a hay pile, a hollowed-log trough."""
    b = Builder()
    g = G(b)
    mud = peat_fn(rng, base=(0.55, 0.46, 0.38), wet=0.5)
    mound(g, (0.0, -0.04, 0.0), 1.5, 1.4, 0.05, rng, mat=M_PEAT, col_fn=mud, tile=0.7, rings=4, seg=18, skirt=0.08)
    pole(g, V(0, -0.3, 0), V(0.03, 0.55, 0.0), 0.045, 0.035, rng, col=(0.7, 0.64, 0.55), sides=6)
    rope(g, [V(0.03, 0.5, 0), V(0.4, 0.2, 0.3), V(0.75, 0.02, 0.55), V(1.0, 0.03, 0.4)], r=0.012, col=TWINE)
    # hay
    for k in range(70):
        a = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(0, 0.38)
        p = V(-0.75 + math.cos(a) * r, 0.02 + 0.22 * (1 - r / 0.4) * rng.uniform(0.3, 1.0), -0.5 + math.sin(a) * r)
        d = V(math.cos(a + rng.uniform(-1.4, 1.4)), rng.uniform(-0.2, 0.3), math.sin(a + rng.uniform(-1.4, 1.4))).normalized()
        tube(g, [p - d * 0.12, p + d * 0.12], [0.004, 0.003], 3, M_THATCH, scale((0.82, 0.72, 0.45), rng.uniform(0.7, 1.0)),
             tile=0.2, cap=False)
    # trough: a split log hollowed out, dark water in it
    tc = V(0.55, 0.0, -0.75)
    pole(g, tc + V(-0.45, 0.13, 0), tc + V(0.45, 0.14, 0.05), 0.15, 0.14, rng, mat=M_ROT, col=(0.8, 0.74, 0.62), sides=9)
    lbox(g, tc + V(0, 0.255, 0.02), (0.8, 0.02, 0.17), quat_y(-0.05), WS.M_WATER, WS.WATER)
    for x in (-0.38, 0.38):
        stone(g, tuple(tc + V(x, 0.03, 0)), (0.1, 0.07, 0.12), rng, mat=M_GRANITE, detail=1, rough=0.1, cuts=1,
              col_fn=lambda p, n: (0.6, 0.6, 0.56), tile=0.4)
    for k in range(9):  # droppings
        a = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(0.3, 1.1)
        stone(g, (math.cos(a) * r, 0.01, math.sin(a) * r), (0.018, 0.014, 0.018), rng, mat=M_PEAT, detail=0, rough=0.1,
              cuts=0, col_fn=lambda p, n: (0.16, 0.13, 0.1), tile=0.2)
    return b


# ─────────────────────────────────────────────────────────────── her hand props (rig units)
def sf_staff(rng):
    """Grip at the origin; foot at y -0.9, the knotted head at +0.58."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 3, 5.0)
    bark = lambda t: mix((0.3, 0.24, 0.2), (0.62, 0.52, 0.42), 0.35 + 0.4 * t)
    pts = [V(0.0, -0.9, 0.0), V(0.012, -0.45, 0.006), V(-0.008, -0.05, -0.004), V(0.01, 0.3, 0.008), V(0.04, 0.55, 0.0)]
    for i in range(len(pts) - 1):
        pole(g, pts[i], pts[i + 1], 0.026 - 0.001 * i, 0.025 - 0.001 * i, rng, col_fn=bark, sides=7, wobble=0.004, segs=2)
    # thorn knots + the gnarled head, smoothed by use where the hand goes
    for k in range(6):
        y = rng.uniform(-0.8, 0.4)
        if -0.12 < y < 0.1:
            continue
        a = rng.uniform(0, 2 * math.pi)
        p = V(0.0, y, 0.0)
        stone(g, tuple(p + V(math.cos(a) * 0.024, 0, math.sin(a) * 0.024)), (0.014, 0.02, 0.014), rng, mat=M_BARK, detail=0,
              rough=0.2, cuts=0, col_fn=lambda q, n: (0.28, 0.22, 0.18), tile=0.2)
    stone(g, (0.045, 0.6, 0.0), (0.05, 0.06, 0.045), rng, mat=M_BARK, detail=1, rough=0.25, cuts=1,
          col_fn=lambda q, n: scale((0.42, 0.34, 0.26), 0.8 + 0.3 * nz(q * 9)), tile=0.2)
    # the grip wrapped in old leather
    for k in range(5):
        y = -0.08 + k * 0.035
        ring = [V(math.cos(t) * 0.029, y + 0.006 * math.sin(t), math.sin(t) * 0.029) for t in np.linspace(0, 2 * math.pi, 9)]
        tube(g, ring, [0.008] * 9, 4, M_HIDE, (0.32, 0.22, 0.15), tile=0.1, cap=False)
    # a charm on a thong under the head: a tusk tip and a feather
    rope(g, [V(0.03, 0.5, 0.0), V(0.06, 0.36, 0.02)], r=0.004, col=(0.3, 0.22, 0.15))
    tusk(g, V(0.06, 0.36, 0.02), V(0.1, -1, 0.1), rng, length=0.07, r=0.009)
    q = [V(0.04, 0.42, -0.01), V(0.075, 0.27, -0.03), V(0.05, 0.27, -0.035)]
    g.flat(q, M_HIDE, (0.12, 0.11, 0.1), 0.2)
    g.flat(q[::-1], M_HIDE, (0.12, 0.11, 0.1), 0.2)
    return b


def sf_basket(rng):
    """Handle apex at the origin; the oval wicker body hangs below (rim at y -0.2, foot at -0.36)."""
    b = Builder()
    g = G(b)
    rim_y, foot_y = -0.2, -0.36
    rx, rz = 0.19, 0.13
    # woven body: stacked rings of withy, each a touch wider
    rows = 8
    for r in range(rows):
        f = r / (rows - 1)
        y = foot_y + (rim_y - foot_y) * f
        k = 0.82 + 0.18 * f
        ring = [V(math.cos(t) * rx * k, y + 0.006 * math.sin(7 * t + r), math.sin(t) * rz * k) for t in np.linspace(0, 2 * math.pi, 19)]
        tube(g, ring, [0.012] * 19, 4, M_BARK, scale(WICKER, rng.uniform(0.75, 1.0)), tile=0.3, cap=False)
    # stakes
    for i in range(14):
        t = i * 2 * math.pi / 14
        tube(g, [V(math.cos(t) * rx * 0.8, foot_y, math.sin(t) * rz * 0.8), V(math.cos(t) * rx, rim_y + 0.01, math.sin(t) * rz)],
             [0.007, 0.007], 3, M_BARK, scale(WICKER, 0.7), tile=0.2, cap=False)
    stone(g, (0.0, foot_y + 0.005, 0.0), (rx * 0.82, 0.012, rz * 0.82), rng, mat=M_BARK, detail=1, rough=0.02, cuts=0,
          col_fn=lambda p, n: scale(WICKER, 0.65), tile=0.3)
    # handle arc
    arc = [V(math.cos(t) * rx * 0.95, rim_y + math.sin(t) * 0.2, 0.0) for t in np.linspace(0.0, math.pi, 11)]
    tube(g, arc, [0.014] * 11, 5, M_BARK, scale(WICKER, 0.85), tile=0.3)
    # herbs and a toadstool or two sticking out
    herb_bundle(g, (-0.08, rim_y - 0.04, 0.02), (0.6, 0.6, 0.1), rng, n=7, length=0.16, col=HERB)
    herb_bundle(g, (0.06, rim_y - 0.04, -0.02), (-0.3, 0.7, -0.3), rng, n=5, length=0.13, col=HERB_DRY, flower=(0.86, 0.84, 0.7))
    return b


# ─────────────────────────────────────────────────────────────── the Field of the Answered
def old_turf_fn(rng):
    """Turf on an old grave: patchy grass, bare brown where it slumped, darker at the wet foot."""
    nz = Noise(rng, 4, 1.6)
    grass = (0.27, 0.35, 0.14)
    dry = (0.44, 0.43, 0.25)
    bare = (0.33, 0.27, 0.2)

    def f(p, n):
        k = nz(p * 1.7)
        c = mix(grass, dry, smoothstep(-0.2, 0.6, nz(p * 3.1 + V(4, 0, 1))))
        c = mix(c, bare, smoothstep(0.25, 0.7, k) * (1 - smoothstep(0.6, 0.95, n.y)) * 0.9)
        return scale(c, 0.7 + 0.3 * smoothstep(-0.12, 0.2, p.y))
    return f


def og_long_barrow(rng):
    """Footprint 1.8 x 1.0 (half extents), laid along X (mound x -1.6..1.6, the iron stone at x -1.95).
    An old grave long settled: low, broad, lopsided where one end slumped, sunk into the ground, grown
    over with patchy turf and rushes; its kerb half-buried."""
    b = Builder()
    g = G(b)
    ks = stone_fn((0.85, 0.85, 0.8), rng, moss=0.7, damp_h=0.3, y0=-0.1, lichen=(0.9, 0.9, 0.78))
    tf = old_turf_fn(rng)
    mound(g, (0.0, -0.14, 0.0), 1.7, 0.85, 0.46, rng, mat=M_EARTH, col_fn=tf, tile=1.0, rings=8, seg=28,
          skirt=0.18, edge=0.22, power=0.5, rough=0.32)
    # the higher head end and a slumped foot break the pill outline
    mound(g, (-0.7, -0.12, rng.uniform(-0.1, 0.1)), 0.85, 0.7, 0.42, rng, mat=M_EARTH, col_fn=tf, tile=1.0, rings=5,
          seg=18, skirt=0.1, edge=0.25, power=0.55, rough=0.3)
    mound(g, (1.05, -0.1, rng.uniform(-0.2, 0.2)), 0.8, 0.75, 0.16, rng, mat=M_EARTH, col_fn=tf, tile=1.0, rings=4,
          seg=16, skirt=0.08, edge=0.3, power=0.7, rough=0.3)
    kerb(g, (0.0, -0.1, 0.0), 1.7, 0.85, rng, ks, n=18, s=0.85, gap=(4.6, 5.4))
    iron_stone(g, (-1.95, -0.08, 0.0), math.pi / 2, rng, h=0.8, notches=7, lean=rng.uniform(-0.12, 0.12))
    for j in range(18):
        a = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(0.2, 1.05)
        x, z = math.cos(a) * r * 1.5, math.sin(a) * r * 0.75
        sedge(g, (x, 0.3 * max(0.0, 1 - r * r) - 0.04, z), rng, n=rng.integers(5, 10), h=rng.uniform(0.25, 0.5),
              col=(0.55, 0.56, 0.3))
    bowl(g, (-2.15, 0.0, 0.35), 0.1, rng, fill=(0.3, 0.32, 0.28))
    return b


def og_iron_stone(rng):
    b = Builder()
    g = G(b)
    iron_stone(g, (0.0, 0.0, 0.0), 0.0, rng, h=rng.uniform(0.7, 0.95), notches=9, lean=0.06)
    pebbles(g, (0.0, 0.0, 0.0), 0.42, rng, n=11)
    mound(g, (0.0, -0.04, -0.6), 0.5, 0.75, 0.12, rng, mat=M_EARTH, col_fn=turf_fn(rng), tile=0.8, rings=3, seg=12, skirt=0.06)
    sedge(g, (0.35, 0.0, 0.2), rng, n=5, h=0.35, col=(0.58, 0.58, 0.32))
    return b


def raw_soil_fn(rng):
    """Fresh-dug grave earth: black peat turned up with streaks of grey clay and rusty sand, wetter
    at the foot."""
    nz = Noise(rng, 4, 2.4)
    peat = (0.3, 0.25, 0.2)
    clay = (0.52, 0.49, 0.44)
    sand = (0.6, 0.45, 0.3)

    def f(p, n):
        k = nz(p * 2.6)
        c = mix(peat, clay, smoothstep(0.35, 0.75, k) * 0.8)
        c = mix(c, sand, smoothstep(0.45, 0.85, nz(p * 4.3 + V(3, 1, 0))) * 0.6)
        return scale(c, (0.75 + 0.35 * smoothstep(-0.1, 0.25, p.y)) * (0.85 + 0.2 * nz(p * 9.0)))
    return f


def fresh_mound(rng, variant):
    """A fresh grave along X: raw heaped soil x -1.0..1.0, sunk at its edges, the head at x -1.2."""
    b = Builder()
    g = G(b)
    rf = raw_soil_fn(rng)
    # the heap: three overlapping shovel-loads, none quite in line -> lumpy, not a loaf
    mound(g, (0.0, -0.1, 0.0), 1.0, 0.48, 0.34, rng, mat=M_PEAT, col_fn=rf, tile=0.7, rings=7, seg=24, skirt=0.12,
          edge=0.28, power=0.55, rough=0.45)
    for x in (-0.5, 0.05, 0.55):
        mound(g, (x + rng.uniform(-0.1, 0.1), -0.06, rng.uniform(-0.08, 0.08)), rng.uniform(0.32, 0.45),
              rng.uniform(0.26, 0.36), rng.uniform(0.12, 0.2), rng, mat=M_PEAT, col_fn=rf, tile=0.7, rings=4, seg=12,
              skirt=0.05, edge=0.35, power=0.6, rough=0.5)
    # spoil trodden flat round its foot
    mound(g, (0.0, -0.08, 0.0), 1.5, 0.95, 0.09, rng, mat=M_PEAT, col_fn=rf, tile=0.8, rings=3, seg=20, skirt=0.06,
          edge=0.35)
    # clods and turned-up turf sods of every size, a few lying off the heap
    for _ in range(40):
        a = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(0.1, 1.15)
        h = 0.36 * max(0.0, 1 - r * r) ** 0.6 - 0.04
        sz = rng.uniform(0.03, 0.09)
        stone(g, (math.cos(a) * r * 1.0, h, math.sin(a) * r * 0.5), (sz, sz * 0.6, sz * 0.85), rng, mat=M_PEAT,
              detail=1, rough=0.35, cuts=2, tile=0.4, col_fn=rf)
    for _ in range(3):
        a = rng.uniform(0, 2 * math.pi)
        stone(g, (math.cos(a) * 1.15, 0.0, math.sin(a) * 0.7), (0.12, 0.05, 0.09), rng, mat=M_PEAT, detail=1,
              rough=0.2, cuts=1, tile=0.4, col_fn=old_turf_fn(rng))
    if variant == 0:
        iron_stone(g, (-1.3, -0.06, 0.0), math.pi / 2, rng, h=0.6, w=0.34, notches=5, lean=rng.uniform(-0.12, 0.12))
        bowl(g, (-1.15, 0.0, 0.5), 0.11, rng, fill=(0.3, 0.32, 0.3))
        fish(g, (-1.13, 0.08, 0.5), V(1, 0.1, 0.3), rng, s=0.8)
        fish(g, (-1.17, 0.09, 0.47), V(0.8, 0.1, -0.5), rng, s=0.7)
    else:
        # a stake at the head with a bone charm, a cleaver laid along the top
        pole(g, V(-1.3, -0.3, 0.0), V(-1.27, 0.75, 0.02), 0.04, 0.032, rng, mat=M_ROT, col=(0.9, 0.82, 0.7), sides=6)
        rope(g, [V(-1.27, 0.68, 0.04), V(-1.25, 0.52, 0.06)], r=0.005, col=(0.35, 0.28, 0.2))
        tusk(g, V(-1.25, 0.52, 0.06), V(0.2, -1, 0.1), rng, length=0.11, r=0.014)
        cleaver(g, V(-0.45, 0.27, -0.05), V(1, -0.25, 0.08), rng, s=0.9)
        bowl(g, (-1.1, 0.0, -0.5), 0.1, rng, fill=(0.45, 0.24, 0.12))
    return b


def og_fresh_mound_a(rng):
    return fresh_mound(rng, 0)


def og_fresh_mound_b(rng):
    return fresh_mound(rng, 1)


def og_fish_bowl(rng):
    b = Builder()
    g = G(b)
    bowl(g, (0.0, 0.0, 0.0), 0.13, rng, fill=(0.3, 0.32, 0.28))
    fish(g, (0.01, 0.09, 0.0), V(1, 0.1, 0.2), rng, s=0.95)
    fish(g, (-0.02, 0.1, 0.03), V(0.7, 0.12, -0.6), rng, s=0.85)
    return b


def sf_hut_clutter(rng):
    """Hut-model-local (unscaled, the landmark spawns it x1.4): what an old woman keeps on her stilt
    porch -- jars and dark bottles along the deck left of the ladder, a sill with two bottles under
    the front window, a bucket and a sack right of the door, herbs drying head-down under the
    right-hand eave. The ladder top (x -0.3..0.3) and the door (x 0.07..0.57) stay clear."""
    b = Builder()
    g = G(b)
    deck = 1.42
    for x, k in ((-1.15, 0.75), (-0.98, 0.6), (-0.84, 0.85)):
        clay_jar(g, (x + rng.uniform(-0.02, 0.02), deck, 0.95 + rng.uniform(-0.04, 0.04)), k, rng, rag=rng.uniform() < 0.6)
    glass = [(0.16, 0.22, 0.14), (0.24, 0.16, 0.1), (0.14, 0.17, 0.2)]

    def bottle(c, h, col):
        tint = lambda p, n: scale(col, 0.8 + 0.4 * smoothstep(0.3, 0.95, n.y + 0.4))
        lathe(g, [(0.0, 0.0), (0.045 * h, 0.0), (0.05 * h, 0.12 * h), (0.045 * h, 0.2 * h), (0.017 * h, 0.27 * h),
                  (0.016 * h, 0.34 * h), (0.0, 0.345 * h)], 10, c, M_IRON, tint, tile=0.2)
        tube(g, [V(c[0], c[1] + 0.33 * h, c[2]), V(c[0], c[1] + 0.37 * h, c[2])], [0.014 * h, 0.012 * h], 6, M_BARK,
             (0.55, 0.45, 0.32), tile=0.1)
    for x, z, h in ((-0.7, 1.0, 1.0), (-0.62, 0.9, 0.8), (-0.53, 1.02, 1.15)):
        bottle((x, deck, z), h, glass[rng.integers(0, 3)])
    # the sill under the front window, two bottles on it
    lbox(g, V(-0.55, 2.1, 0.76), (0.48, 0.035, 0.1), quat_y(0.0), M_STONE, [(0.45, 0.4, 0.34), None, (0.4, 0.35, 0.3)],
         tile=0.3, grain=0)
    bottle((-0.66, 2.12, 0.77), 0.7, glass[0])
    bottle((-0.47, 2.12, 0.76), 0.6, glass[1])
    # bucket + sack right of the door
    wood = lambda p, n: scale((0.5, 0.42, 0.33), 0.8 + 0.2 * smoothstep(-0.3, 0.6, n.y))
    lathe(g, [(0.0, 0.0), (0.12, 0.0), (0.14, 0.22), (0.125, 0.22), (0.11, 0.03), (0.0, 0.03)], 12,
          (0.8, deck, 0.92), M_BARK, wood, tile=0.3)
    for y in (0.05, 0.17):
        tube(g, [V(0.8 + 0.135 * math.cos(a), deck + y, 0.92 + 0.135 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 13)],
             [0.008] * 13, 4, M_IRON, (0.25, 0.24, 0.22), tile=0.1, cap=False)
    stone(g, (1.08, deck + 0.13, 0.86), (0.15, 0.17, 0.12), rng, mat=M_CLOTH, detail=2, rough=0.12, cuts=1,
          col_fn=lambda p, n: scale(RAG, 0.75 + 0.25 * n.y), tile=0.4, rot=quat_y(0.4))
    # herbs drying head-down from a pole under the right-hand eave
    pole(g, V(1.18, 2.72, -0.85), V(1.18, 2.74, 0.75), 0.022, 0.02, rng, col=(0.55, 0.48, 0.38), sides=6)
    for k in range(7):
        z = -0.75 + k * 0.24 + rng.uniform(-0.03, 0.03)
        rope(g, [V(1.18, 2.72, z), V(1.18, 2.6, z)], r=0.005, col=TWINE)
        herb_bundle(g, (1.18, 2.6, z), (rng.uniform(-0.1, 0.1), -1, rng.uniform(-0.1, 0.1)), rng, n=7,
                    length=rng.uniform(0.22, 0.32), col=HERB if k % 3 else HERB_DRY,
                    flower=(0.62, 0.5, 0.7) if k % 4 == 1 else None)
    return b


MODELS = {
    "sf_hut_clutter": sf_hut_clutter,
    "sf_trade_stone": sf_trade_stone,
    "sf_wicket": sf_wicket,
    "sf_offer_herbs": sf_offer_herbs,
    "sf_brew_jar": sf_brew_jar,
    "sf_herb_rack": sf_herb_rack,
    "sf_goat_stake": sf_goat_stake,
    "sf_staff": sf_staff,
    "sf_basket": sf_basket,
    "og_long_barrow": og_long_barrow,
    "og_iron_stone": og_iron_stone,
    "og_fresh_mound_a": og_fresh_mound_a,
    "og_fresh_mound_b": og_fresh_mound_b,
    "og_fish_bowl": og_fish_bowl,
}

if __name__ == "__main__":
    clear_scene()
    objs = []
    report = {}
    only = set(sys.argv[sys.argv.index("--") + 1:]) if "--" in sys.argv else set()
    for i, (name, fn) in enumerate(MODELS.items()):
        if only and name not in only:
            continue
        b = fn(np.random.default_rng(7300 + i))
        report[name] = bounds(b)
        objs.append(b.build(name, MATS))
    export_glb(OUT / "swamp_folk.glb", objs)
    (OUT / "swamp_folk_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    for k, v in report.items():
        print(f"{k}: {v}")
    print("SWAMP_FOLK_DONE")
