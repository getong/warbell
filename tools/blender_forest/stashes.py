"""Biome stashes, the wolverine's den and Tobin's sea-grotto -> stashes.glb (src/stashes.rs,
src/oddities.rs, src/castaway.rs).

Ten small hidden caches, two per biome, each its own model (a find is never a repeat):

  forest  stash_hollow_log    a hollow windfall, a bundle tied in oilcloth pushed into its mouth
          stash_snare_line    a poacher's snare line on a game run: stakes, cord nooses, a bent-sapling
                              spring snare, a bundle of skins hung on a forked stake
  desert  stash_buried_jar    a clay jar buried to the shoulder beside a little marker cairn
          stash_camel_pack    a camel's saddle-bags and broken pack frame half under a sand drift
  rocky   stash_niche_cairn   a waist-high cairn with a niche, a wrapped bundle inside
          stash_miner_sack    a miner's sack and pick pushed under a leaning slab
  snow    stash_frozen_bundle a bundle lashed on a pair of short skis, half drifted over
          stash_boat_crate    a ship's crate with rope beckets, lid sprung, by a snapped oar
  swamp   stash_sunken_crate  a crate lashed to a leaning pile, its lower half in the black water
          stash_fish_basket   a fisherman's creel and a willow fish trap by a stake in the reeds

plus `den_wolverine` (a burrow under a boulder in the snow with the thief's hoard: gnawed bones, a
torn sack, the castaways' little water cask), `castaway_grotto` (a rock overhang on the snow coast
with a boat sail rigged across its mouth, a bough bed and a dead fire) and `sled_runner` (a broken
sled runner lying in the snow). Real scale, base y=0, contact parts sunk below 0.

    blender -b --factory-startup --python tools/blender_forest/stashes.py
"""
import math
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402
from common import OUT, clear_scene, export_glb  # noqa: E402
from geo import G, quat_x, quat_y, quat_z  # noqa: E402
from meshkit import Builder  # noqa: E402
from wayside_models import (M_BARK, M_PLANK, M_CLOTH, M_IRON, M_HIDE, M_ROCK, M_EARTH, M_THATCH, M_TIMBER,  # noqa: E402
                            V, beam, board, bounds, lashing, lbox, mix, mound, pole, rock_col, scale, smoothstep,
                            stone, tube, Noise)
import stories_cold as SC  # noqa: E402
from stories_cold import M_SNOW, crate, sack, drift, snow_cap, disc, dome  # noqa: E402


def dusted(fn, amount=0.75):
    """Rock tint fn with snow whitening the up-facing faces."""
    def f(p, n):
        return mix(fn(p, n), (1.0, 1.0, 1.0), amount * smoothstep(0.35, 0.85, n.y))
    return f
import sites_warm as SW  # noqa: E402
from sites_warm import M_CLAY, M_SAND, M_MOSSWOOD, M_MOSSROCK  # noqa: E402
import castaways as CA  # noqa: E402
from wild_sites import sedge, rope  # noqa: E402
from rival_kit import basket as RB  # noqa: E402

MATS = SW.MATS + ["s_granite", "s_slate", "s_peat", "s_rotwood", "s_rust"]
M_GRANITE, M_SLATE, M_PEAT, M_ROT, M_RUST = range(len(SW.MATS), len(SW.MATS) + 5)

SAND = (1.0, 0.86, 0.64)
BONE = (0.86, 0.82, 0.72)
OILCLOTH = (0.42, 0.38, 0.28)
WOOD = (0.78, 0.66, 0.52)


def sand_fn(nz):
    def f(p, n):
        return scale(SAND, 0.92 + 0.08 * nz(p * 2.0) - 0.12 * (1 - smoothstep(0.2, 0.9, n.y)))
    return f


def bundle(g, c, rot, rng, s=1.0, col=OILCLOTH):
    """A cloth bundle, rope-tied crosswise."""
    c = Vector(c)
    stone(g, tuple(c), (0.2 * s, 0.13 * s, 0.15 * s), rng, mat=M_CLOTH, detail=1, rough=0.12, cuts=1, flat_y=0.6, rot=rot,
          col_fn=lambda p, n: mix(scale(col, 0.7), col, smoothstep(c.y - 0.1, c.y + 0.1, p.y)), tile=0.35)
    for a in (0.0, math.pi / 2):
        r = rot @ quat_y(a)
        ring = [c + r @ V(math.cos(t) * 0.205 * s, math.sin(t) * 0.135 * s, 0) for t in np.linspace(0, math.tau, 13)]
        tube(g, ring, [0.009] * 13, 4, M_CLOTH, CA.ROPE if hasattr(CA, "ROPE") else (0.8, 0.68, 0.5), tile=0.2, cap=False)


# ─────────────────────────────────────────────────────────────── forest
def stash_hollow_log(rng):
    b = Builder()
    g = G(b)
    moss = lambda t: mix((0.72, 0.62, 0.5), (0.55, 0.6, 0.36), 0.5 * t)  # noqa: E731
    p0, p1 = V(-1.3, 0.2, 0.05), V(1.15, 0.27, -0.08)
    pole(g, p0, p1, 0.36, 0.3, rng, mat=M_BARK, sides=12, wobble=0.02, segs=4, col_fn=moss, tile=0.8)
    # The rotten mouth: a dark hollow + a ragged rim of punk wood.
    disc(g, (1.16, 0.27, -0.08), quat_z(math.pi / 2) @ quat_x(0.03), 0.24, 0.02, 12, M_ROT, (0.1, 0.08, 0.06), tile=0.4)
    for k in range(9):
        a = k * math.tau / 9
        q = V(1.17, 0.27 + math.sin(a) * 0.27, -0.08 + math.cos(a) * 0.27)
        tube(g, [q, q + V(0.06 + rng.uniform(0, 0.06), math.sin(a) * 0.03, math.cos(a) * 0.03)], [0.035, 0.008], 4, M_ROT,
             (0.55, 0.42, 0.3), tile=0.3)
    disc(g, (-1.31, 0.2, 0.05), quat_z(math.pi / 2), 0.33, 0.04, 12, M_ROT, (0.55, 0.45, 0.33), tile=0.5)
    bundle(g, (1.18, 0.23, -0.02), quat_z(0.1) @ quat_y(0.3), rng, s=0.9)
    # Bedded in the litter: leaf mould heaped along the flanks, a stub branch, ferny tufts.
    mound(g, (0.0, 0.0, 0.0), 1.6, 0.6, 0.12, rng, mat=M_EARTH, col_fn=lambda p, n: (0.55, 0.45, 0.33), tile=0.9, skirt=0.08)
    pole(g, V(-0.3, 0.45, 0.2), V(-0.5, 0.95, 0.55), 0.06, 0.025, rng, mat=M_BARK, col_fn=moss)
    for p in ((0.4, 0, 0.55), (-0.9, 0, -0.5), (1.5, 0, 0.4)):
        sedge(g, p, rng, n=7, h=0.45, col=(0.42, 0.48, 0.24))
    return b


def stash_snare_line(rng):
    b = Builder()
    g = G(b)
    stakes = [V(-1.2, 0, 0.1), V(-0.4, 0, -0.05), V(0.4, 0, 0.08), V(1.2, 0, -0.02)]
    for i, s in enumerate(stakes):
        pole(g, s + V(0, -0.25, 0), s + V(rng.uniform(-0.04, 0.04), 0.42 + 0.06 * i, 0), 0.025, 0.018, rng, mat=M_BARK, sides=6)
        # A cord noose hung from each stake over the run.
        top = s + V(0, 0.3, 0)
        loop = [top + V(0.08 + 0.09 * math.cos(t), -0.12 + 0.1 * math.sin(t), 0.06 * math.sin(t)) for t in np.linspace(0, math.tau, 11)]
        tube(g, [top, top + V(0.08, -0.02, 0)] + loop, [0.006] * (len(loop) + 2), 4, M_CLOTH, (0.62, 0.55, 0.4), tile=0.2, cap=False)
    # The cord run between the stakes.
    for a, c in zip(stakes[:-1], stakes[1:]):
        tube(g, [a + V(0, 0.36, 0), (a + c) / 2 + V(0, 0.3, 0), c + V(0, 0.36, 0)], [0.005] * 3, 4, M_CLOTH, (0.62, 0.55, 0.4),
             tile=0.2, cap=False)
    # A bent-sapling spring snare.
    pts = [V(1.6, -0.1, 0.5), V(1.62, 0.6, 0.5), V(1.45, 1.05, 0.38), V(1.15, 1.2, 0.2), V(0.95, 1.12, 0.1)]
    tube(g, pts, [0.03, 0.025, 0.018, 0.012, 0.008], 6, M_BARK, (0.8, 0.75, 0.6), tile=0.6)
    tube(g, [pts[-1], V(0.95, 0.4, 0.05)], [0.005, 0.005], 4, M_CLOTH, (0.62, 0.55, 0.4), tile=0.2)
    # Forked stake with a bundle of skins.
    f = V(-1.7, 0, -0.4)
    pole(g, f + V(0, -0.2, 0), f + V(0, 0.9, 0), 0.035, 0.03, rng, mat=M_BARK, sides=6)
    pole(g, f + V(0, 0.8, 0), f + V(0.12, 1.08, 0.02), 0.025, 0.015, rng, mat=M_BARK, sides=5)
    pole(g, f + V(0, 0.8, 0), f + V(-0.1, 1.06, -0.03), 0.025, 0.015, rng, mat=M_BARK, sides=5)
    for k in range(3):
        stone(g, (-1.7 + 0.03 * k, 0.62 - 0.08 * k, -0.33), (0.13, 0.22, 0.04), rng, mat=M_HIDE, detail=1, rough=0.1, cuts=0,
              col_fn=lambda p, n, k=k: scale((0.62, 0.48, 0.34), 0.8 + 0.1 * k), tile=0.4, rot=quat_z(0.1 * k))
    tube(g, [f + V(-0.05, 0.86, 0.02), V(-1.7, 0.78, -0.33)], [0.008, 0.008], 4, M_CLOTH, (0.62, 0.55, 0.4), tile=0.2)
    mound(g, (0, 0, 0), 2.0, 0.5, 0.04, rng, mat=M_EARTH, col_fn=lambda p, n: (0.5, 0.42, 0.32), tile=0.9, skirt=0.06)
    for p in ((-0.8, 0, 0.6), (0.8, 0, -0.6), (0.0, 0, 0.7)):
        sedge(g, p, rng, n=6, h=0.35, col=(0.45, 0.5, 0.26))
    return b


# ─────────────────────────────────────────────────────────────── desert
def stash_buried_jar(rng):
    b = Builder()
    g = G(b)
    nz = Noise(rng, 3, 1.5)
    SW.jar(g, rng, V(0, -0.36, 0), quat_x(0.12) @ quat_z(0.08), h=0.62, r=0.24)
    disc(g, (0.03, 0.27, 0.04), quat_x(0.12), 0.075, 0.02, 10, M_CLAY, (0.5, 0.42, 0.34), tile=0.2)  # clay stopper
    mound(g, (0, 0, 0), 0.75, 0.7, 0.16, rng, mat=M_EARTH, col_fn=sand_fn(nz), tile=1.2, skirt=0.1)
    # The marker cairn: four flat stones stacked beside it.
    y = 0.0
    for k, s in enumerate((0.2, 0.16, 0.13, 0.09)):
        stone(g, (0.75 + 0.02 * k, y + s * 0.4, 0.2), (s, s * 0.45, s * 0.85), rng, mat=M_SAND, detail=1, rough=0.1, cuts=1,
              col_fn=rock_col((0.9, 0.78, 0.62), dark_below=0.6), tile=0.5, rot=quat_y(rng.uniform(0, 3)))
        y += s * 0.82
    for k in range(4):
        a = rng.uniform(0, math.tau)
        stone(g, (math.cos(a) * 1.1, 0.03, math.sin(a) * 1.1), (0.07, 0.05, 0.06), rng, mat=M_SAND, detail=1,
              col_fn=rock_col((0.9, 0.78, 0.62)), tile=0.4)
    return b


def stash_camel_pack(rng):
    b = Builder()
    g = G(b)
    nz = Noise(rng, 3, 1.5)
    # Two leather saddle-bags joined by a strap, one dug out, one still under the drift.
    for sx, y, rot in ((-0.35, 0.12, quat_z(0.35)), (0.35, 0.02, quat_z(-0.5) @ quat_x(0.2))):
        stone(g, (sx, y, 0.0), (0.26, 0.2, 0.15), rng, mat=M_HIDE, detail=1, rough=0.08, cuts=1, flat_y=0.5, rot=rot,
              col_fn=lambda p, n: (0.62, 0.42, 0.26), tile=0.4)
    tube(g, [V(-0.35, 0.3, 0.0), V(0.0, 0.42, 0.0), V(0.35, 0.22, 0.0)], [0.025] * 3, 4, M_HIDE, (0.45, 0.3, 0.18), tile=0.3)
    # The broken pack-saddle frame: two arched boards and a snapped rail.
    for z in (-0.25, 0.25):
        pts = [V(-0.55, -0.05, z), V(-0.3, 0.45, z), V(0.05, 0.55, z * 0.9), V(0.3, 0.4, z)]
        beam(g, pts, 0.07, 0.04, up=(0, 0, 1), mat=M_PLANK, col=WOOD, rng=rng)
    beam(g, [V(-0.25, 0.48, -0.32), V(-0.25, 0.48, 0.32), V(-0.2, 0.46, 0.55)], 0.045, 0.045, mat=M_PLANK, col=WOOD, rng=rng,
         jag=(0.0, 0.06))
    drift_c = V(0.45, 0, 0.05)
    mound(g, tuple(drift_c), 0.95, 0.75, 0.32, rng, mat=M_EARTH, col_fn=sand_fn(nz), tile=1.2, skirt=0.12, power=1.1)
    mound(g, (-0.3, 0, 0.1), 1.1, 0.9, 0.08, rng, mat=M_EARTH, col_fn=sand_fn(nz), tile=1.2, skirt=0.1)
    rope(g, [V(-0.6, 0.05, 0.3), V(-0.9, 0.03, 0.6), V(-1.2, 0.02, 0.55)], r=0.012)
    return b


# ─────────────────────────────────────────────────────────────── rocky
def stash_niche_cairn(rng):
    b = Builder()
    g = G(b)
    gr = rock_col((0.72, 0.7, 0.66), moss=0.35, dark_below=0.6, noise=Noise(rng, 3, 2.0))
    y = 0.0
    for k in range(6):
        r = 0.42 - k * 0.055
        n = max(1, 5 - k)
        for i in range(n):
            a = i * math.tau / n + k * 0.7
            off = 0.0 if n == 1 else r * 0.62
            c = (math.cos(a) * off, y + 0.09, math.sin(a) * off)
            if k < 2 and abs(a % math.tau - 4.71) < 0.7:
                continue  # leave the niche on the front (-Z) side open
            stone(g, c, (0.17, 0.1, 0.14), rng, mat=M_GRANITE, detail=1, rough=0.12, cuts=1, col_fn=gr, tile=0.5,
                  rot=quat_y(rng.uniform(0, 3)))
        y += 0.17
    slab = rock_col((0.68, 0.66, 0.62), moss=0.2, dark_below=0.8)
    stone(g, (0.0, 0.36, -0.2), (0.3, 0.05, 0.22), rng, mat=M_SLATE, detail=1, rough=0.05, cuts=1, col_fn=slab, tile=0.5)
    disc(g, (0.0, 0.08, -0.26), quat_x(0.0), 0.16, 0.01, 8, M_ROCK, (0.1, 0.1, 0.1), tile=0.4)  # the dark niche floor
    bundle(g, (0.0, 0.15, -0.25), quat_y(0.4), rng, s=0.7, col=(0.55, 0.32, 0.2))
    for k in range(6):
        a = rng.uniform(0, math.tau)
        stone(g, (math.cos(a) * 0.8, 0.03, math.sin(a) * 0.8), (0.09, 0.05, 0.07), rng, mat=M_GRANITE, detail=1, col_fn=gr)
    return b


def stash_miner_sack(rng):
    b = Builder()
    g = G(b)
    gr = rock_col((0.7, 0.68, 0.64), moss=0.25, dark_below=0.55, noise=Noise(rng, 3, 2.0))
    stone(g, (0.55, 0.32, 0.25), (0.5, 0.42, 0.45), rng, mat=M_GRANITE, detail=2, rough=0.14, cuts=2, col_fn=gr, tile=0.5)
    stone(g, (-0.65, 0.22, 0.3), (0.35, 0.3, 0.32), rng, mat=M_GRANITE, detail=2, rough=0.14, cuts=2, col_fn=gr, tile=0.5)
    # The leaning slab roofing the gap between them.
    stone(g, (0.0, 0.68, 0.12), (0.95, 0.09, 0.55), rng, mat=M_SLATE, detail=2, rough=0.06, cuts=1,
          col_fn=rock_col((0.62, 0.62, 0.6), moss=0.4), tile=0.6, rot=quat_z(-0.12) @ quat_x(0.15))
    sack(g, (-0.05, 0.16, 0.05), quat_z(0.3), 1.2, rng, col=(0.62, 0.55, 0.42))
    SC.pickaxe(g, V(0.3, 0.03, -0.45), V(0.15, 0.12, -0.05), rng)
    for k in range(10):
        a = rng.uniform(-1.2, 1.2)
        r = rng.uniform(0.6, 1.2)
        stone(g, (math.sin(a) * r, 0.03, -math.cos(a) * r * 0.8), (0.08, 0.05, 0.07), rng, mat=M_SLATE, detail=1,
              col_fn=rock_col((0.6, 0.6, 0.58)), tile=0.4)
    return b


# ─────────────────────────────────────────────────────────────── snow
def stash_frozen_bundle(rng):
    b = Builder()
    g = G(b)
    for x in (-0.13, 0.13):
        pts = [V(x, 0.04, -0.75), V(x, 0.04, 0.55), V(x, 0.1, 0.72), V(x, 0.2, 0.8)]
        beam(g, pts, 0.1, 0.022, mat=M_PLANK, col=(0.7, 0.58, 0.44), rng=rng, mode="plank")
    stone(g, (0.0, 0.22, -0.05), (0.24, 0.17, 0.4), rng, mat=M_HIDE, detail=1, rough=0.08, cuts=1, flat_y=0.5,
          col_fn=lambda p, n: mix((0.55, 0.42, 0.3), (0.9, 0.92, 0.95), 0.6 * smoothstep(0.4, 0.9, n.y)), tile=0.4)
    for z in (-0.3, 0.2):
        lashing(g, V(0, 0.22, z), (0, 0, 1), 0.27, rng, turns=2)
    drift(g, (0.15, 0, -0.35), 0.75, 0.6, 0.32, rng)
    drift(g, (-0.2, 0, 0.3), 0.5, 0.45, 0.12, rng)
    snow_cap(g, (0.0, 0.38, 0.05), 0.2, 0.3, 0.05, rng)
    pole(g, V(0.5, -0.2, 0.6), V(0.62, 1.15, 0.7), 0.018, 0.014, rng, mat=M_BARK, sides=5)  # a ski pole stuck in
    disc(g, (0.6, 0.18, 0.69), quat_x(0.05), 0.07, 0.01, 8, M_HIDE, (0.4, 0.3, 0.2), tile=0.2)
    return b


def stash_boat_crate(rng):
    b = Builder()
    g = G(b)
    rot = quat_y(0.25) @ quat_z(0.06)
    crate(g, (0.0, 0.22, 0.0), (0.85, 0.52, 0.55), rot, rng, col=(0.62, 0.55, 0.46))
    # Lid sprung on one side, rope beckets at the ends.
    board(g, (0.02, 0.53, 0.05), (1, 0, 0), (0, 1, -0.25), 0.88, 0.58, 0.04, mat=M_PLANK, col=(0.58, 0.52, 0.45), rng=rng)
    for sx in (-1, 1):
        c = Vector((0, 0.3, 0)) + rot @ V(sx * 0.46, 0, 0)
        loop = [c + rot @ V(sx * 0.03 * math.sin(t), 0.06 * math.cos(t), 0.1 * math.sin(t) + 0.0) for t in np.linspace(-1.6, 1.6, 7)]
        tube(g, loop, [0.016] * 7, 4, M_CLOTH, (0.75, 0.66, 0.5), tile=0.2, cap=True)
    drift(g, (0.1, 0, 0.2), 0.95, 0.75, 0.3, rng)
    snow_cap(g, (0.1, 0.56, 0.0), 0.35, 0.22, 0.05, rng)
    # The snapped oar.
    beam(g, [V(-0.9, 0.05, 0.6), V(0.3, 0.12, 0.95)], 0.05, 0.05, mat=M_PLANK, col=(0.7, 0.6, 0.48), rng=rng, jag=(0.0, 0.08))
    board(g, (-1.15, 0.05, 0.52), (1, 0.05, 0.3), (0, 1, 0), 0.5, 0.14, 0.025, mat=M_PLANK, col=(0.7, 0.6, 0.48), rng=rng)
    return b


# ─────────────────────────────────────────────────────────────── swamp
def stash_sunken_crate(rng):
    b = Builder()
    g = G(b)
    pile = V(0.0, 0, 0.0)
    pole(g, pile + V(0, -0.6, 0), pile + V(0.12, 1.35, 0.05), 0.09, 0.075, rng, mat=M_ROT, sides=8,
         col_fn=lambda t: mix((0.25, 0.22, 0.18), (0.55, 0.5, 0.4), smoothstep(0.3, 0.6, t)), tile=0.8)
    rot = quat_y(0.4) @ quat_x(0.12) @ quat_z(-0.1)
    crate(g, (0.42, 0.12, 0.05), (0.6, 0.42, 0.45), rot, rng, col=(0.42, 0.4, 0.34))
    lashing(g, V(0.12, 0.25, 0.04), (0, 1, 0), 0.12, rng, turns=3)
    tube(g, [V(0.12, 0.3, 0.04), V(0.3, 0.32, 0.05), V(0.5, 0.36, 0.06)], [0.012] * 3, 4, M_CLOTH, (0.45, 0.4, 0.3), tile=0.2)
    # The black water skin over the crate's lower half + its slick.
    disc(g, (0.2, 0.02, 0.0), quat_x(0.0), 0.95, 0.01, 18, M_PEAT, (0.12, 0.1, 0.08), tile=1.0)
    for p in ((-0.6, 0, -0.4), (0.9, 0, -0.5), (-0.4, 0, 0.7), (1.0, 0, 0.6)):
        sedge(g, p, rng, n=9, h=0.75, col=(0.42, 0.44, 0.22))
    return b


def stash_fish_basket(rng):
    b = Builder()
    g = G(b)
    stake = V(-0.45, 0, -0.1)
    pole(g, stake + V(0, -0.4, 0), stake + V(0.03, 1.05, 0.02), 0.04, 0.03, rng, mat=M_ROT, sides=6)
    # The creel (lidded wicker basket) on a strap from the stake.
    RB(g, rng, V(0.15, 0.0, 0.05), r=0.24, h=0.3)
    dome(g, (0.15, 0.31, 0.05), 0.24, quat_x(0.15), M_THATCH, lambda p, n: (0.72, 0.6, 0.4), tile=0.3, rings=3, seg=12, squash=0.3)
    tube(g, [stake + V(0.02, 0.85, 0.02), V(0.0, 0.6, 0.05), V(0.15, 0.36, 0.05)], [0.012] * 3, 4, M_HIDE, (0.4, 0.3, 0.2), tile=0.2)
    # The willow fish trap: a long funnel of withies on its side.
    ax0, ax1 = V(0.35, 0.16, 0.55), V(1.25, 0.12, 0.9)
    for k in range(10):
        a = k * math.tau / 10
        off = lambda r: V(0, math.sin(a) * r, math.cos(a) * r)  # noqa: E731
        tube(g, [ax0 + off(0.17), ax0.lerp(ax1, 0.5) + off(0.14), ax1 + off(0.04)], [0.006] * 3, 3, M_THATCH, (0.7, 0.58, 0.38),
             tile=0.3, cap=False)
    for t in (0.0, 0.35, 0.7):
        c = ax0.lerp(ax1, t)
        r = 0.17 - 0.12 * t
        ring = [c + V(0, math.sin(s) * r, math.cos(s) * r) for s in np.linspace(0, math.tau, 11)]
        tube(g, ring, [0.006] * 11, 3, M_THATCH, (0.6, 0.5, 0.32), tile=0.3, cap=False)
    mound(g, (0.2, 0, 0.3), 1.2, 0.9, 0.05, rng, mat=M_PEAT, col_fn=lambda p, n: (0.42, 0.36, 0.28), tile=1.0, skirt=0.06)
    for p in ((-0.9, 0, 0.3), (0.6, 0, -0.6), (1.4, 0, 0.3), (-0.2, 0, 0.9)):
        sedge(g, p, rng, n=10, h=0.85, col=(0.45, 0.46, 0.22))
    return b


# ─────────────────────────────────────────────────────────────── den, grotto, runner
def den_wolverine(rng):
    b = Builder()
    g = G(b)
    gr = dusted(rock_col((0.6, 0.6, 0.6), dark_below=0.5), 0.8)
    stone(g, (0.0, 0.5, 0.3), (1.0, 0.65, 0.8), rng, mat=M_GRANITE, detail=2, rough=0.14, cuts=2, col_fn=gr, tile=0.6)
    stone(g, (0.95, 0.25, -0.2), (0.4, 0.3, 0.35), rng, mat=M_GRANITE, detail=2, rough=0.14, cuts=1, col_fn=gr, tile=0.6)
    # The burrow mouth: a dark scooped hollow under the boulder's front lip, spoil fanned out.
    dome(g, (0.0, -0.05, -0.45), 0.42, quat_x(-1.45), M_EARTH, lambda p, n: (0.05, 0.045, 0.04), tile=0.5, rings=3, seg=12, squash=0.7)
    mound(g, (0.0, 0, -0.95), 0.7, 0.45, 0.1, rng, mat=M_EARTH, col_fn=lambda p, n: (0.45, 0.38, 0.3), tile=0.8, skirt=0.06)
    drift(g, (-0.9, 0, -0.1), 0.7, 0.9, 0.35, rng)
    drift(g, (0.8, 0, 0.7), 0.8, 0.6, 0.3, rng)
    # The hoard: the castaways' water cask, a torn sack, gnawed bones, fur.
    CA.cask(g, rng, V(-0.55, 0.12, -0.95), quat_z(1.45) @ quat_y(0.3), h=0.42, r=0.15, staves=12)
    sack(g, (0.45, 0.1, -1.05), quat_z(1.2), 0.8, rng, col=(0.6, 0.52, 0.4))
    for k in range(5):
        a = rng.uniform(-0.8, 0.8)
        c = V(math.sin(a) * 0.9, 0.03, -0.8 - math.cos(a) * 0.4)
        d = V(math.cos(a * 3), 0.0, math.sin(a * 3)) * rng.uniform(0.12, 0.22)
        tube(g, [c, c + d], [0.018, 0.014], 5, M_ROCK, BONE, tile=0.2)
        stone(g, tuple(c + d), (0.025, 0.022, 0.025), rng, mat=M_ROCK, detail=1, col_fn=lambda p, n: BONE, tile=0.2)
    stone(g, (-0.1, 0.03, -1.2), (0.14, 0.03, 0.1), rng, mat=M_HIDE, detail=1, col_fn=lambda p, n: (0.3, 0.22, 0.16), tile=0.3)
    return b


def castaway_grotto(rng):
    b = Builder()
    g = G(b)
    gr = dusted(rock_col((0.55, 0.56, 0.58), moss=0.15, dark_below=0.45, noise=Noise(rng, 3, 1.5)), 0.7)
    # Two buttress rocks and a great roof slab: a shallow overhang open to the -Z (sea) side.
    stone(g, (-1.5, 0.75, 0.5), (0.8, 0.95, 1.4), rng, mat=M_GRANITE, detail=2, rough=0.16, cuts=2, col_fn=gr, tile=0.6)
    stone(g, (1.55, 0.7, 0.4), (0.75, 0.9, 1.3), rng, mat=M_GRANITE, detail=2, rough=0.16, cuts=2, col_fn=gr, tile=0.6)
    stone(g, (0.0, 1.0, 1.25), (1.5, 1.05, 0.6), rng, mat=M_GRANITE, detail=2, rough=0.16, cuts=2, col_fn=gr, tile=0.6)
    stone(g, (0.0, 1.85, 0.5), (2.3, 0.35, 1.45), rng, mat=M_GRANITE, detail=2, rough=0.1, cuts=2,
          col_fn=dusted(rock_col((0.5, 0.52, 0.55)), 0.95), tile=0.6, rot=quat_x(-0.12))
    snow_cap(g, (0.0, 2.15, 0.6), 1.9, 1.1, 0.18, rng)
    # The boat's sail rigged across the mouth from an oar wedged between the rocks.
    beam(g, [V(-1.3, 1.45, -0.6), V(1.35, 1.5, -0.65)], 0.05, 0.05, mat=M_PLANK, col=(0.7, 0.6, 0.48), rng=rng)
    pts = []
    for i in range(7):
        x = -1.25 + 2.5 * i / 6
        u = i / 6
        sag = 0.3 * math.sin(math.pi * u)
        # The right third is hauled aside and lashed, leaving a gap to crawl through.
        hem = 0.25 + 0.05 * (i % 2) + 0.75 * max(0.0, u - 0.62) / 0.38
        pts.append([V(x, 1.45 - sag * 0.25, -0.62), V(x, 0.95 - sag * 0.6, -0.95 - sag),
                    V(x - 0.25 * max(0.0, u - 0.62), hem, -1.2 - 0.12 * math.sin(7.0 * u))])
    for i in range(6):
        for j in range(2):
            q = [pts[i][j], pts[i + 1][j], pts[i + 1][j + 1], pts[i][j + 1]]
            n = (q[1] - q[0]).cross(q[3] - q[0]).normalized()
            col = mix((0.86, 0.8, 0.68), (0.66, 0.58, 0.46), 0.5 * j)  # salt-bleached sailcloth, stained low
            g.poly(q, [(i / 6, j / 2), ((i + 1) / 6, j / 2), ((i + 1) / 6, (j + 1) / 2), (i / 6, (j + 1) / 2)], [n] * 4, [col] * 4,
                   M_CLOTH)
            g.poly(q[::-1], [(i / 6, (j + 1) / 2), ((i + 1) / 6, (j + 1) / 2), ((i + 1) / 6, j / 2), (i / 6, j / 2)], [-n] * 4,
                   [scale(col, 0.7)] * 4, M_CLOTH)
    # Bough bed, a dead fire ring, a tin cup.
    for k in range(14):
        a = rng.uniform(-0.5, 0.5)
        c = V(rng.uniform(-0.7, 0.7), 0.06, rng.uniform(0.0, 0.7))
        tube(g, [c, c + V(math.sin(a) * 0.5, 0.03, math.cos(a) * 0.3)], [0.03, 0.01], 4, M_THATCH, (0.35, 0.42, 0.25), tile=0.3)
    for k in range(8):
        a = k * math.tau / 8
        stone(g, (0.9 + math.cos(a) * 0.3, 0.05, -0.4 + math.sin(a) * 0.3), (0.09, 0.07, 0.08), rng, mat=M_ROCK, detail=1,
              col_fn=rock_col((0.4, 0.38, 0.36)), tile=0.4)
    disc(g, (0.9, 0.02, -0.4), quat_x(0.0), 0.22, 0.02, 10, M_EARTH, (0.12, 0.11, 0.1), tile=0.4)
    drift(g, (-2.2, 0, -0.6), 1.0, 0.8, 0.35, rng)
    drift(g, (2.2, 0, -0.5), 1.0, 0.8, 0.3, rng)
    return b


def sled_runner(rng):
    b = Builder()
    g = G(b)
    pts = [V(-0.9, 0.02, 0.0), V(0.5, 0.03, 0.02), V(0.75, 0.09, 0.03), V(0.9, 0.24, 0.03), V(0.86, 0.36, 0.02)]
    beam(g, pts, 0.03, 0.07, up=(0, 0, 1), mat=M_PLANK, col=(0.66, 0.56, 0.45), rng=rng)
    for x in (-0.6, -0.1, 0.35):
        beam(g, [V(x, 0.02, 0.0), V(x + 0.02, 0.2, 0.0)], 0.035, 0.03, mat=M_PLANK, col=(0.6, 0.52, 0.42), rng=rng, jag=(0.0, 0.05))
    drift(g, (-0.4, 0, 0.1), 0.6, 0.3, 0.07, rng)
    return b


MODELS = {
    "stash_hollow_log": stash_hollow_log,
    "stash_snare_line": stash_snare_line,
    "stash_buried_jar": stash_buried_jar,
    "stash_camel_pack": stash_camel_pack,
    "stash_niche_cairn": stash_niche_cairn,
    "stash_miner_sack": stash_miner_sack,
    "stash_frozen_bundle": stash_frozen_bundle,
    "stash_boat_crate": stash_boat_crate,
    "stash_sunken_crate": stash_sunken_crate,
    "stash_fish_basket": stash_fish_basket,
    "den_wolverine": den_wolverine,
    "castaway_grotto": castaway_grotto,
    "sled_runner": sled_runner,
}

if __name__ == "__main__":
    clear_scene()
    objs = []
    for i, (name, fn) in enumerate(MODELS.items()):
        bld = fn(np.random.default_rng(8800 + i))
        print(name, bounds(bld))
        objs.append(bld.build(name, MATS))
    export_glb(OUT / "stashes.glb", objs)
    print("STASHES_DONE")
