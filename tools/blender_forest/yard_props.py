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


def lift_timber(fn, floor=0.78, gain_max=1.6, hue=(1.0, 0.9, 0.76), grey=0.4):
    """Per-model timber tint fix (the wood read too dark in game): wrap a model fn so every
    plank / timber / bark face corner of ITS builder is lifted toward weathered grey-brown oak —
    luminance raised to at least `floor` (by at most `gain_max`, so deliberately shadowed bits
    stay darker), then the hue pulled `grey` of the way to `hue`. The tint multiplies a scanned
    wood albedo, so ~0.4-0.6 tints read near-black at noon; this lands them ~0.75-0.9. Local to
    the wrapped models: the shared materials are untouched."""
    hl = 0.3 * hue[0] + 0.59 * hue[1] + 0.11 * hue[2]
    hn = tuple(h / hl for h in hue)

    def lift(c):
        lum = max(0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2], 1e-4)
        k = min(max(floor / lum, 1.0), gain_max)
        c = tuple(x * k for x in c[:3])
        lum *= k
        return tuple(x + (lum * h - x) * grey for x, h in zip(c, hn))

    def wrapped(rng):
        b = fn(rng)
        wood = (M_PLANK, M_TIMBER, M_BARK)
        b.faces = [(f[0], f[1], f[2], [lift(c) for c in f[3]], f[4]) if f[4] in wood else f for f in b.faces]
        return b
    wrapped.__name__ = fn.__name__
    return wrapped


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


def crate_box(g, rng, c, size, yaw_a=0.0, col=(0.95, 0.72, 0.48)):
    """A nailed slat crate: a dark inner box, slats on every side, corner battens, a slatted lid."""
    c = Vector(c)
    q = quat_y(yaw_a)
    sx, sy, sz = size
    lbox(g, c, (sx - 0.04, sy - 0.04, sz - 0.04), q, M_TIMBER, scale(col, 0.45), tile=0.5)
    n = max(2, int(sy / 0.13))
    for k in range(n):
        y = -sy / 2 + (k + 0.5) * sy / n
        for along_x in (True, False):
            w, d = (sx, sz) if along_x else (sz, sx)
            for sd in (-1, 1):
                off = V(0, y, sd * d / 2) if along_x else V(sd * d / 2, y, 0)
                rot = q if along_x else q @ quat_y(math.pi / 2)
                lbox(g, c + q @ off, (w, sy / n - 0.02, 0.02), rot, M_TIMBER, scale(col, rng.uniform(0.8, 1.0)),
                     tile=0.4)
    for x in (-1, 1):
        for z in (-1, 1):
            lbox(g, c + q @ V(x * (sx / 2 - 0.02), 0, z * (sz / 2 - 0.02)), (0.05, sy + 0.01, 0.05), q, M_TIMBER,
                 scale(col, 0.7), tile=0.3)
    for k in range(3):
        lbox(g, c + q @ V(0, sy / 2 - 0.01, -sz / 2 + (k + 0.5) * sz / 3), (sx, 0.02, sz / 3 - 0.02), q, M_TIMBER,
             scale(col, rng.uniform(0.85, 1.0)), tile=0.4)


def town_merchant_shop(rng):
    """The merchant booth by the west-gate market (3.0 x 1.9, open front +Z, base y=0): hewn
    corner posts on stone pads, board-and-batten back and side walls, a board-covered gable roof
    with a ridge board, a red-and-cream striped awning sagging off the front eave on two poles, a
    plank counter (merchant stands behind it at z ~ -0.2), a goods shelf with jars and cloth bolts,
    scales and coin stacks on the counter, crates, sacks and a barrel round it, a hanging sign with a
    gilt coin on an iron bracket."""
    b = Builder()
    g = G(b)
    WOOD = (1.0, 0.72, 0.46)
    POST = (0.88, 0.66, 0.46)
    HW, HD, EAVE = 1.5, 0.95, 2.05
    for px, pz in ((-HW, HD), (HW, HD), (-HW, -HD), (HW, -HD)):
        stone(g, V(px, 0.02, pz), (0.17, 0.08, 0.17), rng, mat=M_ROCK, detail=1, rough=0.1,
              col_fn=rock_col((0.8, 0.78, 0.74), moss=0.2), tile=0.5)
        lbox(g, V(px, EAVE / 2 + 0.05, pz), (0.16, EAVE - 0.05, 0.16), quat_y(rng.uniform(-0.03, 0.03)), M_TIMBER,
             scale(POST, rng.uniform(0.85, 1.0)), tile=0.6)
    for pz in (HD, -HD):
        lbox(g, V(0, EAVE, pz), (2 * HW + 0.3, 0.14, 0.16), quat_y(0.0), M_TIMBER, scale(POST, 0.9), tile=0.6)
    for px in (-HW, HW):
        lbox(g, V(px, EAVE, 0), (0.15, 0.13, 2 * HD + 0.1), quat_y(0.0), M_TIMBER, scale(POST, 0.85), tile=0.6)

    def boards(a, bb, y0, y1):
        a, bb = Vector(a), Vector(bb)
        t = (bb - a).normalized()
        nrm = t.cross(UP)
        L = (bb - a).length
        k = max(1, int(L / 0.22))
        for i in range(k):
            s = (i + 0.5) * L / k
            board(g, a + t * s + UP * ((y0 + y1) / 2), (0, 1, 0), tuple(nrm), y1 - y0 - rng.uniform(0, 0.03),
                  L / k - 0.015, 0.03, mat=M_TIMBER, col=scale(WOOD, rng.uniform(0.75, 0.95)), rng=rng)
            if i:
                board(g, a + t * (s - L / k / 2) + UP * ((y0 + y1) / 2) + nrm * 0.025, (0, 1, 0), tuple(nrm),
                      y1 - y0 - 0.02, 0.05, 0.02, mat=M_TIMBER, col=scale(POST, 0.7), rng=rng)

    boards(V(HW - 0.08, 0, -HD), V(-HW + 0.08, 0, -HD), 0.06, EAVE - 0.07)
    boards(V(-HW, 0, -HD + 0.08), V(-HW, 0, HD - 0.35), 0.06, 1.2)
    boards(V(HW, 0, HD - 0.35), V(HW, 0, -HD + 0.08), 0.06, 1.2)
    # Gable roof of boards running down the slopes (ridge along X), rafters, a ridge board.
    ridge_y, over = EAVE + 0.75, 0.35
    n = int((2 * HW + 0.5) / 0.2)
    for sz in (-1, 1):
        ez = sz * (HD + over)
        ey = EAVE - over * 0.75 / HD
        for i in range(n):
            x = -HW - 0.25 + (i + 0.5) * (2 * HW + 0.5) / n
            a_, e_ = V(x, ridge_y, 0.02 * sz), V(x, ey, ez)
            d = (e_ - a_).normalized()
            up_n = V(1, 0, 0).cross(d) * (-sz)
            if up_n.y < 0:
                up_n = -up_n
            board(g, (a_ + e_) / 2 + up_n * (0.012 * (i % 2)), tuple(d), tuple(up_n), (e_ - a_).length +
                  rng.uniform(-0.04, 0.04), (2 * HW + 0.5) / n + 0.03, 0.03, mat=M_TIMBER,
                  col=scale((0.85, 0.66, 0.5), rng.uniform(0.6, 0.85)), rng=rng)
        for x in (-HW + 0.3, 0.0, HW - 0.3):
            pole(g, V(x, ridge_y - 0.07, 0), V(x, EAVE + 0.02, sz * HD), 0.045, 0.045, rng, col=POST, sides=6, segs=1)
    board(g, V(0, ridge_y + 0.04, 0), (1, 0, 0), (0, 1, 0), 2 * HW + 0.55, 0.16, 0.05, mat=M_TIMBER, col=scale(POST, 0.8),
          rng=rng)
    for sx in (-1, 1):
        for k in range(4):
            y0 = EAVE + 0.06
            h = (ridge_y - y0) * (1 - (k + 0.5) / 4.6)
            board(g, V(sx * HW, y0 + h / 2, -0.1 - k * 0.2), (0, 1, 0), (sx, 0, 0), h, 0.19, 0.03, mat=M_TIMBER,
                  col=scale(WOOD, 0.8), rng=rng)
    # Striped awning sagging off the front eave to two poles, a scalloped valance.
    for sx in (-1, 1):
        pole(g, V(sx * 1.45, -0.15, HD + 1.05), V(sx * 1.45, 1.74, HD + 1.05), 0.035, 0.03, rng, col=POST, sides=6,
             segs=2)
    RED, CREAM = (0.62, 0.1, 0.08), (0.95, 0.88, 0.72)
    rows = []
    for i in range(9):
        f = i / 8
        x = -1.55 + 3.1 * f
        row = []
        for j in range(4):
            u = j / 3
            p = V(x, EAVE - 0.05, HD + 0.1).lerp(V(x, 1.72, HD + 1.1), u)
            p.y -= 0.1 * math.sin(u * math.pi) * (0.6 + 0.4 * math.sin(f * math.pi))
            row.append(p)
        rows.append(row)
    sheet(g, rows, M_CLOTH, lambda u, v: RED if int(u * 7.999) % 2 == 0 else CREAM, tile=0.6, double=True)
    for i in range(8):
        x = -1.55 + 3.1 * (i + 0.5) / 8
        c = RED if i % 2 == 0 else CREAM
        sheet(g, [[V(x - 0.19, 1.72, HD + 1.11), V(x - 0.17, 1.58, HD + 1.12)],
                  [V(x, 1.72, HD + 1.11), V(x, 1.52, HD + 1.13)],
                  [V(x + 0.19, 1.72, HD + 1.11), V(x + 0.17, 1.58, HD + 1.12)]], M_CLOTH, lambda u, v, c=c: c,
              tile=0.5, double=True)
    # Counter: plank front + top board; a two-tier goods shelf along the back wall.
    boards(V(-HW + 0.1, 0, HD - 0.25), V(HW - 0.1, 0, HD - 0.25), 0.05, 0.9)
    board(g, V(0, 0.93, HD - 0.33), (1, 0, 0), (0, 1, 0), 2 * HW - 0.1, 0.36, 0.05, mat=M_TIMBER, col=scale(WOOD, 0.9),
          rng=rng)
    for y in (1.05, 1.5):
        board(g, V(0, y, -HD + 0.17), (1, 0, 0), (0, 1, 0), 2 * HW - 0.3, 0.26, 0.04, mat=M_TIMBER,
              col=scale(WOOD, 0.85), rng=rng)
    cloth = [(0.3, 0.42, 0.7), (0.75, 0.6, 0.25), (0.45, 0.6, 0.3), (0.58, 0.12, 0.1)]
    for i, x in enumerate(np.linspace(-1.15, 1.15, 9)):
        x = float(x)
        if i % 3 == 0:
            lathe(g, (x, 1.07, -HD + 0.17), (0, 1, 0), [(h * 0.45, r * 0.45) for h, r in ((0.0, 0.08), (0.08, 0.17), (0.25, 0.22), (0.42, 0.16), (0.52, 0.08), (0.58, 0.09))], 10, M_EARTH, scale((0.85, 0.5, 0.32), rng.uniform(0.85, 1.05)), tile=0.4)
        elif i % 3 == 1:
            tube(g, [V(x - 0.12, 1.15, -HD + 0.17), V(x + 0.12, 1.15, -HD + 0.17)], [0.075, 0.075], 8, M_CLOTH,
                 cloth[i % 4], tile=0.3)
        lathe(g, (x, 1.52, -HD + 0.16), (0, 1, 0), [(0.0, 0.05), (0.08, 0.07), (0.16, 0.045), (0.2, 0.03)], 8,
              M_EARTH, scale((0.85, 0.5, 0.32), rng.uniform(0.8, 1.05)), tile=0.3)
    # Counter-top: a balance, coin stacks, a cloth bolt, a small crate of wares.
    sc = V(0.55, 0.955, HD - 0.33)
    BRASS = (0.75, 0.58, 0.3)
    pole(g, sc, sc + UP * 0.32, 0.012, 0.01, rng, mat=M_IRON, col=BRASS, sides=5, segs=1, wobble=0.0)
    pole(g, sc + V(-0.16, 0.32, 0), sc + V(0.16, 0.32, 0), 0.008, 0.008, rng, mat=M_IRON, col=BRASS, sides=4, segs=1,
         wobble=0.0)
    for sx in (-1, 1):
        lathe(g, tuple(sc + V(sx * 0.16, 0.15, 0)), (0, 1, 0), [(0.0, 0.004), (0.02, 0.06), (0.03, 0.065)], 8, M_IRON,
              BRASS, tile=0.2)
        pole(g, sc + V(sx * 0.16, 0.32, 0), sc + V(sx * 0.16, 0.18, 0), 0.004, 0.004, rng, mat=M_IRON, col=BRASS, sides=3,
             segs=1, wobble=0.0)
    for k, (x, nn) in enumerate(((0.95, 5), (1.06, 3), (1.0, 2))):
        for j in range(nn):
            lathe(g, (x, 0.955 + j * 0.012, HD - 0.3 + 0.08 * k), (0, 1, 0), [(0.0, 0.03), (0.011, 0.03)], 10, M_IRON,
                  (1.0, 0.78, 0.3), tile=0.2)
    crate_box(g, rng, V(-0.85, 1.07, HD - 0.33), (0.36, 0.22, 0.26), 0.1, col=(0.85, 0.6, 0.4))
    tube(g, [V(-0.3, 1.02, HD - 0.33), V(0.05, 1.02, HD - 0.3)], [0.07, 0.07], 8, M_CLOTH, (0.58, 0.12, 0.1), tile=0.3)
    # Goods round the booth.
    crate_box(g, rng, V(-1.95, 0.22, HD + 0.2), (0.5, 0.44, 0.44), 0.2)
    crate_box(g, rng, V(-1.95, 0.6, HD + 0.18), (0.42, 0.32, 0.36), -0.15)
    barrel(g, rng, (1.95, 0.0, HD + 0.1), s=1.1)
    sack(g, rng, V(1.9, 0.25, HD + 0.75))
    sack(g, rng, V(-1.55, 0.18, HD + 0.85), lying=True)
    # Hanging sign: an iron bracket off the right front post, a board with a gilt coin both sides.
    IRONC = (0.3, 0.29, 0.28)
    br = V(HW + 0.05, 1.95, HD)
    pole(g, br, br + V(0.6, 0, 0.25), 0.02, 0.02, rng, mat=M_IRON, col=IRONC, sides=5, segs=1, wobble=0.0)
    pole(g, br + V(0.0, -0.25, 0), br + V(0.35, 0, 0.15), 0.015, 0.015, rng, mat=M_IRON, col=IRONC, sides=5, segs=1,
         wobble=0.0)
    sg = br + V(0.42, -0.32, 0.18)
    dirx = V(1, 0, 0.4).normalized()
    nn_ = V(-0.37, 0, 0.93).normalized()
    for sx in (-1, 1):
        tube(g, [sg + dirx * (sx * 0.16) + UP * 0.33, sg + dirx * (sx * 0.16) + UP * 0.19], [0.006, 0.006], 4, M_IRON,
             IRONC, tile=0.2)
    board(g, sg, tuple(dirx), tuple(nn_), 0.5, 0.38, 0.04, mat=M_TIMBER, col=(0.62, 0.42, 0.28), rng=rng)
    for sd in (-1, 1):
        lathe(g, tuple(sg + nn_ * (sd * 0.02)), tuple(nn_ * sd), [(0.0, 0.12), (0.012, 0.11), (0.016, 0.0)], 14, M_IRON,
              (1.0, 0.78, 0.3), tile=0.2)
    return b


def cart_wheel(g, rng, c, axis, r=0.48, col=(0.85, 0.64, 0.44)):
    """A spoked cart wheel: felloe ring of six segments, an iron tyre, a turned hub, 8 spokes."""
    c, ax = Vector(c), Vector(axis).normalized()
    up = UP if abs(ax.dot(UP)) < 0.9 else V(1, 0, 0)
    e1 = ax.cross(up).normalized()
    e2 = ax.cross(e1).normalized()
    ring = [c + (e1 * math.cos(2 * math.pi * k / 24) + e2 * math.sin(2 * math.pi * k / 24)) * r for k in range(25)]
    tube(g, ring, [0.045] * 25, 6, M_TIMBER, col, tile=0.4, cap=False)
    tyre = [c + (e1 * math.cos(2 * math.pi * k / 24) + e2 * math.sin(2 * math.pi * k / 24)) * (r + 0.035)
            for k in range(25)]
    tube(g, tyre, [0.018] * 25, 5, M_IRON, (0.32, 0.3, 0.29), tile=0.4, cap=False)
    lathe(g, tuple(c - ax * 0.12), tuple(ax), [(0.0, 0.05), (0.04, 0.085), (0.18, 0.085), (0.24, 0.05)], 10, M_TIMBER,
          scale(col, 0.85), tile=0.3)
    for k in range(8):
        a = 2 * math.pi * k / 8 + 0.2
        d = e1 * math.cos(a) + e2 * math.sin(a)
        pole(g, c + d * 0.08, c + d * (r - 0.03), 0.022, 0.018, rng, mat=M_TIMBER, col=col, sides=5, segs=1, wobble=0.0)


def meadow_hay_cart(rng):
    """Two-wheeled hay wain, shafts resting on the ground, a heaped and roped load of loose hay
    spilling over the rails, a hay fork leaning on it."""
    b = Builder()
    g = G(b)
    WOOD = (0.95, 0.7, 0.46)
    tilt = math.atan2(0.55 - 0.08, 2.4)
    q = quat_x(-tilt)
    piv = V(0, 0.55, 0.4)

    def P(x, y, z):
        return piv + q @ V(x, y - 0.55, z - 0.4)
    for sx in (-1, 1):
        cart_wheel(g, rng, V(sx * 0.82, 0.52, 0.4), (1, 0, 0), r=0.5, col=WOOD)
    pole(g, V(-0.95, 0.52, 0.4), V(0.95, 0.52, 0.4), 0.04, 0.04, rng, mat=M_TIMBER, col=scale(WOOD, 0.8), sides=6,
         segs=1, wobble=0.0)
    # Bed: side beams running forward into the shafts, cross boards, rails with stakes.
    for sx in (-1, 1):
        pole(g, P(sx * 0.55, 0.62, -0.9), P(sx * 0.42, 0.62, 2.5), 0.045, 0.04, rng, mat=M_TIMBER, col=WOOD, sides=6,
             segs=2)
        for z in np.linspace(-0.85, 1.25, 6):
            pole(g, P(sx * 0.6, 0.62, float(z)), P(sx * 0.66, 1.05, float(z)), 0.022, 0.02, rng, mat=M_TIMBER,
                 col=scale(WOOD, 0.9), sides=5, segs=1)
        pole(g, P(sx * 0.66, 1.02, -0.9), P(sx * 0.66, 1.02, 1.3), 0.025, 0.025, rng, mat=M_TIMBER, col=WOOD, sides=5,
             segs=1)
    for z in np.linspace(-0.85, 1.25, 10):
        board(g, P(0, 0.66, float(z)), (1, 0, 0), tuple(q @ UP), 1.2, 0.2, 0.035, mat=M_TIMBER,
              col=scale(WOOD, rng.uniform(0.75, 0.95)), rng=rng)
    # The load: a hay loaf over the bed, straw hanging off the sides, two ropes over it.
    slab(g, P(0, 1.08, 0.2), (1.45, 0.9, 2.3), q, rng, mat=M_THATCH, res=(5, 4, 7), round_r=0.3, rough=0.25, crown=0.4,
         col_fn=lambda p, n: scale((1.25, 1.08, 0.72), 0.85 + 0.15 * max(n.y, 0.0)), tile=0.5)
    for k in range(18):
        sx = rng.choice([-1, 1])
        z = rng.uniform(-0.8, 1.2)
        a_ = P(sx * 0.72, 1.0 + rng.uniform(-0.1, 0.15), z)
        tube(g, [a_, a_ + V(sx * 0.08, -0.25 - rng.uniform(0, 0.15), rng.uniform(-0.05, 0.05))], [0.03, 0.005], 4,
             M_THATCH, (1.2, 1.02, 0.66), tile=0.3)
    for z in (-0.3, 0.8):
        pts = [P(-0.7, 0.95, z), P(-0.6, 1.45, z), P(0, 1.6, z), P(0.6, 1.45, z), P(0.7, 0.95, z)]
        tube(g, pts, [0.014] * 5, 4, M_CLOTH, ROPE, tile=0.2)
    # Hay fork against the wheel, loose hay on the ground.
    pole(g, V(1.1, 0.0, -0.3), V(1.2, 1.55, 0.25), 0.02, 0.018, rng, mat=M_TIMBER, col=(0.8, 0.66, 0.48), sides=5, segs=1)
    for d in (-0.05, 0.05):
        tube(g, [V(1.2, 1.55, 0.25), V(1.21 + d, 1.72, 0.3), V(1.21 + d * 1.3, 1.85, 0.26)], [0.01, 0.01, 0.006], 4,
             M_TIMBER, (0.8, 0.66, 0.48), tile=0.2)
    mound(g, (0.2, 0.0, -1.2), 0.9, 0.6, 0.06, rng, mat=M_THATCH, col_fn=lambda p, n: (1.15, 0.98, 0.64), rings=3,
          seg=14, rough=0.3)
    return b


def meadow_bale(rng):
    b = Builder()
    g = G(b)
    bale(g, rng, (0.0, 0.3, 0.0), (1.0, 0.6, 0.6), 0.0)
    mound(g, (0.0, 0.0, 0.0), 0.75, 0.55, 0.04, rng, mat=M_THATCH, col_fn=lambda p, n: (1.1, 0.94, 0.64), rings=3,
          seg=12, rough=0.3)
    return b


def meadow_scarecrow(rng):
    """A ragged scarecrow on a cross of poles: stuffed sack head, a straw hat, a torn shirt with
    straw at the cuffs, a crow perched on one arm."""
    b = Builder()
    g = G(b)
    POSTC_ = (0.7, 0.6, 0.48)
    sc = V(0, 0, 0)
    pole(g, sc - UP * 0.3, sc + UP * 1.75, 0.035, 0.03, rng, col=POSTC_, sides=6, segs=2)
    pole(g, sc + V(-0.6, 1.3, 0.02), sc + V(0.6, 1.33, -0.02), 0.026, 0.024, rng, col=POSTC_, sides=5, segs=1)
    stone(g, sc + UP * 1.68, (0.13, 0.15, 0.12), rng, mat=M_CLOTH, detail=1, rough=0.08, cuts=0,
          col_fn=lambda p, n: (0.85, 0.72, 0.52))
    frustum(g, 0.24, 0.12, 1.79, 0.05, 12, M_THATCH, (1.0, 0.85, 0.55), tile=0.4, centre=tuple(sc), jitter=0.03, rng=rng)
    frustum(g, 0.12, 0.05, 1.84, 0.14, 10, M_THATCH, (1.0, 0.85, 0.55), tile=0.4, centre=tuple(sc))
    rows = []
    for i in range(6):
        x = -0.55 + 1.1 * i / 5
        row = []
        for j in range(4):
            v_ = j / 3
            w = 1.0 - 0.45 * v_ * (1 - abs(x) / 0.55) if abs(x) < 0.3 else 1.0
            y = 1.36 - v_ * (0.25 if abs(x) > 0.3 else 0.62 + 0.08 * rng.uniform(-1, 1))
            row.append(sc + V(x * w, y, 0.06 + 0.04 * math.sin(i * 1.7 + j)))
        rows.append(row)
    sheet(g, rows, M_CLOTH, lambda u, v: (0.5, 0.42, 0.36) if v < 0.7 else (0.42, 0.36, 0.3), tile=0.5, double=True)
    for sx in (-1, 1):
        for k in range(5):
            a = 2 * math.pi * k / 5
            p = sc + V(sx * 0.58, 1.31, 0)
            tube(g, [p, p + V(sx * 0.1, -0.06 + 0.05 * math.cos(a), 0.05 * math.sin(a))], [0.012, 0.004], 4, M_THATCH,
                 (1.15, 0.96, 0.6), tile=0.3)
    # A crow on the right arm.
    cw = sc + V(0.42, 1.38, 0)
    stone(g, cw + V(0, 0.07, 0), (0.09, 0.06, 0.05), rng, mat=M_HIDE, detail=1, rough=0.05, cuts=0,
          col_fn=lambda p, n: (0.08, 0.08, 0.09))
    stone(g, cw + V(0.08, 0.13, 0), (0.035, 0.035, 0.03), rng, mat=M_HIDE, detail=1, rough=0.03, cuts=0,
          col_fn=lambda p, n: (0.08, 0.08, 0.09))
    tube(g, [cw + V(0.11, 0.13, 0), cw + V(0.16, 0.12, 0)], [0.012, 0.002], 4, M_IRON, (0.2, 0.18, 0.16), tile=0.2)
    tube(g, [cw + V(-0.07, 0.07, 0), cw + V(-0.16, 0.05, 0)], [0.03, 0.005], 4, M_HIDE, (0.08, 0.08, 0.09), tile=0.2)
    return b


def meadow_beehive(rng):
    """A coiled-straw bee skep on a split-log bench, a straw hackle over it, a dark entrance."""
    b = Builder()
    g = G(b)
    for x in (-0.18, 0.18):
        pole(g, V(x, -0.1, 0), V(x, 0.42, 0), 0.05, 0.045, rng, col=(0.7, 0.58, 0.44), sides=7, segs=1)
    board(g, V(0, 0.45, 0), (1, 0, 0), (0, 1, 0), 0.62, 0.42, 0.06, mat=M_TIMBER, col=(0.8, 0.62, 0.44), rng=rng)
    base = V(0, 0.48, 0)
    rings = 9
    for k in range(rings):
        f = k / rings
        r = 0.22 * math.sqrt(max(0.0, 1 - (f * 0.95) ** 2)) + 0.02
        y = base.y + 0.05 + f * 0.42
        pts = [V(math.cos(2 * math.pi * j / 16) * r, y, math.sin(2 * math.pi * j / 16) * r) for j in range(17)]
        tube(g, pts, [0.03] * 17, 5, M_THATCH, scale((1.1, 0.9, 0.58), rng.uniform(0.85, 1.0)), tile=0.25, cap=False)
    lathe(g, (0, base.y + 0.02, 0), (0, 1, 0), [(0.0, 0.2), (0.25, 0.19), (0.4, 0.1), (0.47, 0.0)], 12, M_THATCH,
          (0.8, 0.66, 0.42), tile=0.4)
    face(g, [V(-0.05, base.y + 0.01, 0.235), V(0.05, base.y + 0.01, 0.235), V(0.04, base.y + 0.07, 0.228),
             V(-0.04, base.y + 0.07, 0.228)], V(0, 0, 1), M_EARTH, VOID)
    # Hackle: a straw hood tied at the top.
    frustum(g, 0.3, 0.02, base.y + 0.36, 0.3, 12, M_THATCH, (1.0, 0.86, 0.56), tile=0.3, jitter=0.03, rng=rng)
    return b


def meadow_firewood_rack(rng):
    """A firewood rack: two X-frame ends on a sill, split logs stacked between, bark out, a
    board lid weighted with a stone, chips and a chopping block with an axe beside it."""
    b = Builder()
    g = G(b)
    L, H = 1.8, 1.0
    COL = (0.85, 0.66, 0.46)
    for sx in (-1, 1):
        x = sx * L / 2
        for d in (-1, 1):
            pole(g, V(x, 0.0, d * 0.32), V(x, H + 0.15, -d * 0.32), 0.035, 0.03, rng, col=COL, sides=6, segs=1)
    for z in (-0.25, 0.25):
        pole(g, V(-L / 2 - 0.1, 0.06, z), V(L / 2 + 0.1, 0.06, z), 0.05, 0.05, rng, col=scale(COL, 0.8), sides=6, segs=1)
    rows = int(H / 0.16)
    for r in range(rows):
        y = 0.16 + r * 0.155
        n = int(L / 0.17)
        for k in range(n):
            x = -L / 2 + 0.12 + k * (L - 0.24) / (n - 1) + (0.04 if r % 2 else 0.0)
            c = V(x, y, 0)
            rr = rng.uniform(0.08, 0.095)
            sides = int(rng.choice([5, 6, 7]))
            pole(g, c - V(0, 0, 0.3), c + V(rng.uniform(-0.02, 0.02), 0, 0.3), rr, rr, rng,
                 col=scale((0.78, 0.6, 0.42), rng.uniform(0.75, 1.0)), sides=sides, segs=1, wobble=0.004)
    board(g, V(0, H + 0.2, 0), (1, 0, 0), (0, 1, 0), L + 0.3, 0.8, 0.04, mat=M_TIMBER, col=scale(COL, 0.7), rng=rng)
    stone(g, V(0.3, H + 0.3, 0.05), (0.13, 0.08, 0.1), rng, mat=M_ROCK, detail=1, rough=0.12,
          col_fn=rock_col((0.75, 0.73, 0.7), moss=0.3), tile=0.5)
    blk = V(1.35, 0, 0.55)
    pole(g, blk, blk + UP * 0.42, 0.21, 0.2, rng, col=(0.8, 0.64, 0.46), sides=10, segs=1)
    pole(g, blk + V(0.05, 0.4, 0.0), blk + V(0.25, 0.75, 0.25), 0.018, 0.016, rng, mat=M_TIMBER, col=(0.82, 0.68, 0.5),
         sides=5, segs=1)
    lbox(g, blk + V(0.04, 0.42, -0.02), (0.14, 0.08, 0.02), quat_y(-0.8), M_IRON, (0.4, 0.38, 0.36), tile=0.2)
    mound(g, (blk.x, 0.0, blk.z), 0.55, 0.45, 0.03, rng, mat=M_EARTH, col_fn=lambda p, n: (0.85, 0.7, 0.5), rings=3,
          seg=12, rough=0.2)
    return b


def meadow_crates(rng):
    """A supply drop: stacked slat crates, a barrel, sacks."""
    b = Builder()
    g = G(b)
    crate_box(g, rng, V(-0.3, 0.25, 0.0), (0.6, 0.5, 0.5), 0.05)
    crate_box(g, rng, V(0.36, 0.22, 0.05), (0.52, 0.44, 0.44), -0.12)
    crate_box(g, rng, V(-0.25, 0.7, 0.02), (0.48, 0.4, 0.42), 0.2)
    barrel(g, rng, (0.95, 0.0, -0.1), s=1.0)
    sack(g, rng, V(0.4, 0.22, 0.6))
    sack(g, rng, V(-0.5, 0.17, 0.62), lying=True)
    return b


# The wooden yard / meadow pieces get the per-model timber lift (the brazier keeps its charred
# logs dark).
training_dummy = lift_timber(training_dummy)
town_merchant_shop = lift_timber(town_merchant_shop)
meadow_hay_cart = lift_timber(meadow_hay_cart)
meadow_scarecrow = lift_timber(meadow_scarecrow)
meadow_beehive = lift_timber(meadow_beehive)
meadow_firewood_rack = lift_timber(meadow_firewood_rack)
meadow_crates = lift_timber(meadow_crates)
