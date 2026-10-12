"""Castle yard props for town_kit.glb (exec'd by town_kit.py after village_huts.py, so the whole
toolkit is in scope):

  gate_brazier    a forged iron fire basket (cresset) on a splayed three-legged stand, banded
                  bowl of flat bars, split logs and charred coals heaped in it, an ash spill and a
                  few stones at the feet. Bowl rim at y ~1.18; the live flame (flame_fx.rs) sits
                  on the coals at y ~1.08.
  training_dummy  a straw-stuffed sacking pell on a stout post rammed into beaten earth: rope
                  bound waist and neck, straw bursting at the seams and the arm ends, a cross arm,
                  a battered plank shield hung on one arm, trampled straw round the foot.
"""


def gate_brazier(rng):
    b = Builder()
    g = G(b)
    IRON = (0.3, 0.29, 0.28)
    RUST = (0.42, 0.3, 0.22)
    # Three splayed legs meeting under the basket, a ring tying them halfway.
    for k in range(3):
        a = 2 * math.pi * k / 3 + 0.3
        foot = V(math.cos(a) * 0.42, -0.02, math.sin(a) * 0.42)
        top = V(math.cos(a) * 0.12, 0.86, math.sin(a) * 0.12)
        tube(g, [foot + V(math.cos(a) * 0.06, 0.0, math.sin(a) * 0.06), foot, foot.lerp(top, 0.5), top],
             [0.022, 0.024, 0.022, 0.02], 6, M_IRON, IRON, tile=0.3)
        stone(g, foot + V(0, -0.02, 0), (0.09, 0.05, 0.08), rng, mat=M_ROCK, detail=1, rough=0.12,
              col_fn=rock_col((0.72, 0.7, 0.66), moss=0.1), tile=0.5)
    ring = [V(math.cos(2 * math.pi * k / 10) * 0.27, 0.43, math.sin(2 * math.pi * k / 10) * 0.27) for k in range(11)]
    tube(g, ring, [0.014] * 11, 5, M_IRON, IRON, tile=0.3, cap=False)
    tube(g, [V(0, 0.8, 0), V(0, 0.95, 0)], [0.05, 0.05], 8, M_IRON, IRON, tile=0.3)
    # The basket: flat bars curving out from a bottom ring to a wider rim, two bands round it.
    nb = 10
    for k in range(nb):
        a = 2 * math.pi * k / nb
        pts = [V(math.cos(a) * r, y, math.sin(a) * r) for r, y in ((0.1, 0.92), (0.22, 0.98), (0.32, 1.08), (0.38, 1.2),
                                                                  (0.41, 1.26))]
        tube(g, pts, [0.016] * 5, 4, M_IRON, scale(RUST if k % 3 == 0 else IRON, rng.uniform(0.9, 1.1)), tile=0.3)
    for r, y in ((0.12, 0.93), (0.33, 1.1), (0.405, 1.24)):
        tube(g, [V(math.cos(2 * math.pi * k / 16) * r, y, math.sin(2 * math.pi * k / 16) * r) for k in range(17)],
             [0.02] * 17, 5, M_IRON, IRON, tile=0.3, cap=False)
    # Fuel: charred split logs leaning in the basket, black coals with ember-orange cracks.
    for k in range(6):
        a = 2 * math.pi * k / 6 + rng.uniform(-0.2, 0.2)
        p0 = V(math.cos(a) * 0.28, 1.0, math.sin(a) * 0.28)
        p1 = V(math.cos(a + 2.6) * 0.1, 1.25 + rng.uniform(-0.03, 0.05), math.sin(a + 2.6) * 0.1)
        pole(g, p0, p1, 0.045, 0.035, rng, col=scale((0.32, 0.26, 0.2), rng.uniform(0.6, 1.0)), sides=6, segs=2)
    for k in range(12):
        a = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(0.0, 0.25)
        stone(g, V(math.cos(a) * r, 1.02 + 0.06 * (1 - r / 0.3), math.sin(a) * r), (0.06, 0.04, 0.05), rng,
              mat=M_ROCK, detail=1, rough=0.2, col_fn=lambda p, n: (0.95, 0.38, 0.12) if n.y < 0.2 else (0.12, 0.1, 0.09),
              tile=0.3)
    # Ash spilt round the feet.
    mound(g, (0.05, 0.0, 0.02), 0.5, 0.45, 0.03, rng, mat=M_EARTH, col_fn=lambda p, n: (0.42, 0.4, 0.38), rings=3,
          seg=14, rough=0.1)
    return b


def training_dummy(rng):
    b = Builder()
    g = G(b)
    WOOD = (0.7, 0.56, 0.4)
    SACK = (0.86, 0.74, 0.55)
    STRAW = (1.15, 0.96, 0.6)
    # Post rammed into a trampled earth patch, with wedges at the foot.
    mound(g, (0.0, -0.02, 0.0), 0.75, 0.7, 0.04, rng, mat=M_EARTH, col_fn=lambda p, n: (0.62, 0.52, 0.42), rings=3,
          seg=16, rough=0.1)
    pole(g, V(0, -0.3, 0), V(0.01, 1.62, -0.01), 0.075, 0.065, rng, col=WOOD, sides=8, segs=3)
    for k in range(3):
        a = 2 * math.pi * k / 3 + 0.4
        p = V(math.cos(a) * 0.1, 0.0, math.sin(a) * 0.1)
        lbox(g, p + V(0, 0.04, 0), (0.1, 0.12, 0.05), quat_y(-a) @ quat_z(0.4), M_TIMBER, scale(WOOD, 0.8), tile=0.3)
    pole(g, V(-0.55, 1.18, 0.0), V(0.55, 1.2, 0.0), 0.04, 0.038, rng, col=WOOD, sides=6, segs=1)
    # Torso: a stuffed sack, fatter at the chest, tied off at waist and neck with rope.
    prof = [(0.62, 0.15), (0.7, 0.21), (0.85, 0.24), (1.05, 0.25), (1.25, 0.22), (1.38, 0.15), (1.42, 0.07)]
    pts = [V(0, y, 0) for y, _ in prof]
    tube(g, pts, [r for _, r in prof], 12, M_CLOTH, SACK, tile=0.35)
    for y, r in ((0.7, 0.21), (1.36, 0.16)):
        tube(g, [V(math.cos(2 * math.pi * k / 12) * (r + 0.01), y + 0.01 * math.sin(k), math.sin(2 * math.pi * k / 12) *
                   (r + 0.01)) for k in range(13)], [0.014] * 13, 4, M_CLOTH, ROPE, tile=0.2, cap=False)
    # Straw bursting out: below the waist tie, at the neck, at a split seam, at the arm ends.
    for k in range(28):
        a = 2 * math.pi * k / 28
        p = V(math.cos(a) * 0.17, 0.66, math.sin(a) * 0.17)
        tube(g, [p, p + V(math.cos(a) * 0.08, -0.14 - rng.uniform(0, 0.08), math.sin(a) * 0.08)], [0.014, 0.004], 4,
             M_THATCH, STRAW, tile=0.3)
    for k in range(7):
        a = 2 * math.pi * k / 7
        p = V(math.cos(a) * 0.05, 1.42, math.sin(a) * 0.05)
        tube(g, [p, p + V(math.cos(a) * 0.1, 0.1 + rng.uniform(0, 0.06), math.sin(a) * 0.1)], [0.012, 0.004], 4,
             M_THATCH, STRAW, tile=0.3)
    for sx in (-1, 1):
        for k in range(5):
            a = 2 * math.pi * k / 5
            p = V(sx * 0.55, 1.19, 0)
            tube(g, [p, p + V(sx * 0.12, 0.05 * math.cos(a), 0.06 * math.sin(a))], [0.012, 0.004], 4, M_THATCH, STRAW,
                 tile=0.3)
    seam = V(0.18, 1.0, 0.14)
    for k in range(5):
        tube(g, [seam, seam + V(0.07 + 0.02 * k, rng.uniform(-0.06, 0.06), 0.05)], [0.012, 0.004], 4, M_THATCH, STRAW,
             tile=0.3)
    # Head: a smaller sack with a straw topknot and a charcoal cross for a face.
    stone(g, V(0, 1.58, 0), (0.13, 0.15, 0.12), rng, mat=M_CLOTH, detail=1, rough=0.06, cuts=0,
          col_fn=lambda p, n: SACK, tile=0.3)
    for d in (-1, 1):
        tube(g, [V(-0.05, 1.6 + d * 0.04, 0.122), V(0.05, 1.6 - d * 0.04, 0.122)], [0.008, 0.008], 4, M_CLOTH,
             (0.08, 0.07, 0.06), tile=0.2)
    # Hacked plank shield hung on the left arm.
    sc = V(-0.42, 1.0, 0.12)
    for k in range(3):
        board(g, sc + V(0, 0, 0.005 * k) + V((k - 1) * 0.13, 0, 0), (0, 1, 0), (0, 0, 1), 0.5 - 0.05 * abs(k - 1), 0.125,
              0.03, mat=M_PLANK, col=scale((0.9, 0.7, 0.5), rng.uniform(0.75, 0.9)), rng=rng)
    tube(g, [sc + V(0.05, 0.25, -0.02), V(-0.42, 1.19, 0.03)], [0.008, 0.008], 4, M_CLOTH, ROPE, tile=0.2)
    # Trampled straw round the foot.
    mound(g, (0.1, 0.0, 0.05), 0.42, 0.36, 0.035, rng, mat=M_THATCH, col_fn=lambda p, n: STRAW, rings=2, seg=12,
          rough=0.3)
    return b
