"""Ork folk outside the camps (src/war_party.rs) -> exported INTO ork_camps.glb by ork_camps.py.

    ork_outcast_niche  ROCKY  The Unanswering's niche: a cold fire ring of grey ash (never lit), his
                              own gong hammer snapped across the shaft and laid down, a thin hide
                              bedroll, fish bones picked clean, a back of fallen boulders.
    ork_outcast_sign   ROCKY  The sign he scratches in the dirt for meat: a ring (a camp), three
                              strokes (a warband) and a line running off toward it; the stick lies
                              where he dropped it. Spawned only after a gift.
    ork_war_post       ANY    A war-trail post: a stake daubed with ochre bands, a skull on top, cords
                              of bones and feathers; packed stones at its foot. They stand along the
                              trail the night comes by.

Authored around the origin, Y up, base at y=0 (ground parts sink below). Uses the ork_camps MATS.

    (built by) blender -b --factory-startup --python tools/blender_forest/ork_camps.py
"""
import math

import numpy as np  # noqa: F401
from mathutils import Vector
from geo import G, quat_x, quat_y, quat_z  # noqa: F401
from meshkit import Builder
from wayside_models import (M_BARK, M_PLANK, M_STONE, M_HIDE, M_CLOTH, M_IRON, M_ROCK, M_EARTH, M_TIMBER,  # noqa: F401
                            V, beam, lashing, lbox, mix, mound, pole, rock_col, scale, slab, smoothstep, stone,
                            tube, Noise)


def _c():
    # Late import: ork_camps imports this module at load time.
    import ork_camps as C
    return C


def outcast_niche(rng):
    C = _c()
    b = Builder()
    g = G(b)
    nz = Noise(rng, 3, 1.2)
    C.ground_patch(g, rng, (0, 0, 0), 2.4, 2.0, (0.5, 0.46, 0.42))
    # The back: a few fallen limestone blocks under the overhang he chose (lichen on the tops).
    for (x, z, sx, sy, sz) in ((-1.6, -1.7, 1.0, 0.9, 0.8), (0.2, -2.1, 1.3, 1.25, 0.9), (1.8, -1.5, 0.8, 0.7, 0.7),
                               (-2.4, -0.4, 0.6, 0.5, 0.6)):
        stone(g, (x, sy * 0.45, z), (sx, sy, sz), rng, detail=2,
              col_fn=rock_col((0.82, 0.8, 0.76), moss=0.45, noise=nz), tile=0.9)
    # The cold fire: a ring of stones round grey ash, no charcoal glow, a few unburnt sticks.
    fc = V(0.3, 0, 0.5)
    for k in range(8):
        a = k / 8 * 2 * math.pi + rng.uniform(-0.1, 0.1)
        s = rng.uniform(0.09, 0.13)
        stone(g, tuple(fc + V(math.cos(a) * 0.38, s * 0.3, math.sin(a) * 0.38)), (s, s * 0.7, s * 0.85), rng, detail=1,
              col_fn=lambda p, n: mix((0.6, 0.58, 0.55), (0.3, 0.29, 0.28), 0.4 * smoothstep(0.1, 0.0, p.y)), tile=0.4)
    mound(g, tuple(fc + V(0, -0.02, 0)), 0.32, 0.32, 0.05, rng, mat=M_EARTH,
          col_fn=lambda p, n: mix((0.55, 0.54, 0.52), (0.36, 0.35, 0.34), 0.4 + 0.3 * nz(p * 7)), tile=0.4, rings=3, seg=12,
          skirt=0.03)
    for k in range(3):
        a = rng.uniform(0, 6.28)
        p0 = fc + V(math.cos(a) * 0.25, 0.04, math.sin(a) * 0.25)
        tube(g, [p0, p0 + V(math.cos(a + 0.4) * 0.35, 0.03, math.sin(a + 0.4) * 0.35)], [0.02, 0.016], 5, M_BARK,
             (0.5, 0.45, 0.4), tile=0.3)
    # The gong hammer, HIS: a heavy iron-shod maul head bound to a thick shaft, the shaft snapped
    # across (fresh pale splinters) and the two halves laid side by side, not thrown.
    hp = V(-0.9, 0.0, 0.9)
    head_rot = quat_y(0.4)
    lbox(g, hp + V(0, 0.14, 0), (0.42, 0.26, 0.26), head_rot, M_TIMBER, (0.55, 0.45, 0.36), tile=0.4)
    for sx in (-1, 1):
        lbox(g, hp + head_rot @ V(sx * 0.2, 0.14, 0), (0.05, 0.3, 0.3), head_rot, M_IRON, (0.32, 0.29, 0.27), tile=0.3)
    sd = head_rot @ V(0, 0, 1)
    s0 = hp + V(0, 0.07, 0) + sd * 0.14
    s1 = s0 + sd * 0.55
    beam(g, [s0, s1], 0.055, 0.055, mat=M_PLANK, col=(0.62, 0.5, 0.38), rng=rng, jag=(0.0, 0.06), chamfer=0.3)
    tip = s1 + V(0.0, 0.0, 0.0)
    for k in range(5):
        a = k / 5 * 6.28
        tube(g, [tip + V(math.cos(a) * 0.02, 0.0, math.sin(a) * 0.02), tip + sd * rng.uniform(0.04, 0.09)
                 + V(math.cos(a) * 0.025, 0.0, math.sin(a) * 0.025)], [0.008, 0.001], 3, M_TIMBER, (0.92, 0.8, 0.62),
             tile=0.2)
    side = head_rot @ V(1, 0, 0)
    o0 = s1 + side * 0.16 - sd * 0.1
    o1 = o0 + sd * 0.62
    beam(g, [o0, o1], 0.055, 0.055, mat=M_PLANK, col=(0.6, 0.48, 0.37), rng=rng, jag=(0.06, 0.0), chamfer=0.3)
    lashing(g, o1 - sd * 0.12, sd, 0.04, rng, turns=3)
    # His bedroll: a thin worn hide against the rocks, and a rolled one for a pillow.
    grid = []
    for i in range(6):
        row = []
        for j in range(5):
            x = -1.3 + i * 0.32
            z = -0.95 + j * 0.2
            row.append((x, 0.03 + 0.02 * math.sin(i * 1.3 + j), z))
        grid.append(row)
    from geo import sheet
    sheet(g, grid, M_HIDE, lambda u, v: scale((0.6, 0.5, 0.4), 0.8 + 0.2 * math.sin(u * 9 + v * 4)), tile=0.7)
    tube(g, [V(-1.45, 0.09, -0.9), V(-1.45, 0.09, -0.15)], [0.09, 0.09], 8, M_HIDE, (0.5, 0.42, 0.34), tile=0.4)
    # Fish bones picked clean beside the fire (he eats what the lake gives).
    for k in range(3):
        p = fc + V(0.7 + k * 0.12, 0.012, -0.2 + k * 0.18)
        a = rng.uniform(0, 6.28)
        d = V(math.cos(a), 0, math.sin(a))
        n = V(-d.z, 0, d.x)
        tube(g, [p - d * 0.13, p + d * 0.13], [0.006, 0.004], 3, M_STONE, C.BONE, tile=0.2)
        for r in range(7):
            q = p - d * 0.1 + d * r * 0.03
            for s in (-1, 1):
                tube(g, [q, q + n * s * 0.045 - d * 0.015], [0.002, 0.001], 3, M_STONE, C.BONE, tile=0.2, cap=False)
        C.skull(g, p + d * 0.15 + V(0, 0.01, 0), 0.25, rng, yaw=a)
    return b


def outcast_sign(rng):
    """Scratched in the dirt: a ring (a camp), three strokes (a warband), a line with a barb leading
    off toward it — the stick dropped beside."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 3, 3.0)
    mound(g, (0, 0, 0), 0.75, 0.6, 0.02, rng, mat=M_EARTH,
          col_fn=lambda p, n: scale((0.58, 0.5, 0.42), 0.9 + 0.1 * nz(p * 5)), tile=0.5, rings=3, seg=16, skirt=0.04)
    groove = (0.18, 0.14, 0.11)
    ridge = (0.72, 0.64, 0.54)

    def scratch(a, b_, w=0.025):
        a, b_ = V(*a), V(*b_)
        d = (b_ - a)
        L = d.length
        d.normalize()
        rot = quat_y(math.atan2(d.x, d.z))
        lbox(g, (a + b_) / 2 + V(0, 0.022, 0), (w, 0.008, L), rot, M_EARTH, groove, tile=0.3)
        for s in (-1, 1):
            n = V(-d.z, 0, d.x) * s * (w * 0.9)
            lbox(g, (a + b_) / 2 + n + V(0, 0.026, 0), (w * 0.6, 0.012, L * 0.95), rot, M_EARTH, ridge, tile=0.3)

    n = 12
    c = (-0.25, 0.0, 0.0)
    pts = [(c[0] + math.cos(2 * math.pi * k / n) * 0.22, 0, c[2] + math.sin(2 * math.pi * k / n) * 0.22) for k in range(n + 1)]
    for a, b_ in zip(pts, pts[1:]):
        scratch(a, b_)
    for k in range(3):
        x = -0.32 + k * 0.08
        scratch((x, 0, -0.07), (x, 0, 0.07), 0.02)
    scratch((-0.02, 0, 0.0), (0.52, 0, 0.0))
    scratch((0.52, 0, 0.0), (0.42, 0, 0.09))
    scratch((0.52, 0, 0.0), (0.42, 0, -0.09))
    tube(g, [V(0.25, 0.02, 0.32), V(0.75, 0.03, 0.18)], [0.012, 0.008], 5, M_BARK, (0.55, 0.48, 0.4), tile=0.3)
    return b


def war_post(rng):
    """A war-trail stake: ochre bands, a skull on top, cords of bones and feathers."""
    C = _c()
    b = Builder()
    g = G(b)
    top = V(rng.uniform(-0.04, 0.04), 2.15, rng.uniform(-0.04, 0.04))

    def col(t):
        band = 1.0 if (0.45 < t < 0.52 or 0.62 < t < 0.68 or 0.78 < t < 0.83) else 0.0
        return mix(scale((0.6, 0.52, 0.44), 0.7 + 0.3 * t), C.OCHRE, band * 0.85)
    pole(g, V(0, -0.35, 0), top, 0.07, 0.05, rng, col=(0.6, 0.52, 0.44), sides=8, col_fn=col)
    C.skull(g, top + V(0, 0.03, 0), 1.5, rng, horns=0.8, yaw=rng.uniform(-0.4, 0.4))
    for k in range(3):
        a = k / 3 * 6.28 + 0.4
        t0 = top + V(math.cos(a) * 0.05, -0.25, math.sin(a) * 0.05)
        bot = C.cord(g, t0, rng.uniform(0.35, 0.6), rng, col=C.RAWHIDE)
        if k == 1:
            C.feather(g, bot, rng)
        else:
            C.bone(g, bot, bot + V(0.02, -0.14, 0.01), 0.01, rng)
    for k in range(7):
        a = k / 7 * 6.28
        s = rng.uniform(0.09, 0.14)
        stone(g, (math.cos(a) * 0.22, s * 0.2, math.sin(a) * 0.22), (s, s * 0.6, s * 0.8), rng, detail=1,
              col_fn=rock_col((0.72, 0.7, 0.66), moss=0.3), tile=0.4)
    # Ochre handprint smears at chest height (the warband touches the post as it passes).
    for k in range(2):
        a = rng.uniform(0, 6.28)
        lbox(g, V(math.cos(a) * 0.065, 1.2 + k * 0.17, math.sin(a) * 0.065), (0.08, 0.1, 0.01), quat_y(-a + math.pi / 2),
             M_CLOTH, scale(C.OCHRE, 0.8), tile=0.2)
    return b


MODELS = {
    "ork_outcast_niche": outcast_niche,
    "ork_outcast_sign": outcast_sign,
    "ork_war_post": war_post,
}
