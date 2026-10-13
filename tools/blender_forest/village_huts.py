"""The poor village outside the walls: peasant huts and cottages (exec'd by town_kit.py, shares its
namespace, replaces town_house_a..d and town_street_house_a/b under the SAME node names).

The settlers outside the walls were poor: small cottages and huts under thick, shaggy, weathered
thatch (hipped, a sagging ridge weighted by crossed riders or pinned with hazel spars, rounded
ragged eaves that come down to shoulder height), walls of clay daub over wattle (patches fallen
off to show the weave) or rough grey logs with saddle-notched corners, all on a fieldstone footing.
Tiny shuttered window holes (no glass), low plank doors (~1.15u ~ 1.75 m), a smoke hole under a
gablet or a crude clay chimney, lean-tos, woodpiles, hurdles, a byre end with its muck heap.

Scale: people ~1.17u, 1u ~ 1.5 m. Pivot = ground under the footprint centre, door / front to +Z.

  node                 footprint x*z   collider half   variant
  town_house_a         5.2 x 3.0       2.55 x 1.55     daub cottage + a thatched lean-to on -X
  town_house_b         6.0 x 3.2       2.95 x 1.65     log longhouse, byre end (+X) with wide door
  town_house_c         3.4 x 2.8       1.75 x 1.45     tiny one-room daub hut, smoke-hole gablet
  town_house_d         4.0 x 3.0       2.2 x 1.7       hovel half dug-in: earth bank, low walls
  town_street_house_a  4.0 x 7.2       2.1 x 3.7       long daub cottage, ridge along Z, door +Z
  town_street_house_b  4.4 x 6.6       2.3 x 3.4       log cottage, shutter folded down into a
                                                       counter (wares) on the +Z end, clay chimney
(Roof eaves overhang the footprint by ~0.45; yard props reach a little further.)
"""

from geo import bl, bn  # noqa: E402

CLAY = (0.86, 0.72, 0.56)          # bare clay daub (s_earth)
LIME_OLD = (0.86, 0.82, 0.74)      # old, dirty limewash over the daub (s_plaster)
LOGC = (0.74, 0.7, 0.64)           # weathered grey logs (s_timber)
POSTC = (0.66, 0.6, 0.52)
THATCH_N = (0.98, 0.86, 0.66)      # weathered straw (on the grey-brown thatch scan)
THATCH_FRESH = (1.18, 0.98, 0.64)  # a newer patch
THATCH_MOSS = (0.5, 0.58, 0.34)
DAUB_HOLE = (0.3, 0.24, 0.19)

# Per-hut paint, set by `settler_hut` while it builds and cleared after (the older huts read the
# defaults): wall finish colour, log tone, door and shutter colours.
PAINT = {}


def _stadium(L, Rx, Rz, nS, nC):
    """Contour samples round a stadium (ridge segment -L..L, hip radius Rx, side radius Rz):
    (fn(t) -> base point at contour scale t, outward XZ unit normal)."""
    out = []

    def side(sz, f):
        x = (-L + 2 * L * f) if sz > 0 else (L - 2 * L * f)
        return (lambda t, x=x: V(x, 0, sz * Rz * t)), V(0, 0, sz)

    def cap(sx, a):
        n = V(math.cos(a) / Rx, 0, math.sin(a) / Rz).normalized()
        return (lambda t, a=a: V(sx * L + Rx * t * math.cos(a), 0, Rz * t * math.sin(a))), n

    for k in range(nS):
        out.append(side(1, k / nS))
    for k in range(nC):
        out.append(cap(1, math.pi / 2 - math.pi * k / nC))
    for k in range(nS):
        out.append(side(-1, k / nS))
    for k in range(nC):
        out.append(cap(-1, -math.pi / 2 - math.pi * k / nC))
    return out


def shell(g, P, mat, col_fn, tile, ref):
    """Closed-in-i quad grid P[i][j] -> smooth mesh; each quad wound so its normal faces away
    from `ref(p)` (a point "inside"). UV: u along i (arc length), v along j (arc length)."""
    ni, nj = len(P), len(P[0])
    Vv = [[0.0] * nj for _ in range(ni)]
    for i in range(ni):
        for j in range(1, nj):
            Vv[i][j] = Vv[i][j - 1] + (P[i][j] - P[i][j - 1]).length
    U = [[0.0] * nj for _ in range(ni + 1)]
    for j in range(nj):
        for i in range(1, ni + 1):
            U[i][j] = U[i - 1][j] + (P[i % ni][j] - P[i - 1][j]).length
    N = [[None] * nj for _ in range(ni)]
    for i in range(ni):
        for j in range(nj):
            du = P[(i + 1) % ni][j] - P[i - 1][j]
            dv = P[i][min(j + 1, nj - 1)] - P[i][max(j - 1, 0)]
            n = du.cross(dv)
            N[i][j] = n.normalized() if n.length > 1e-9 else V(0, 1, 0)
    # One orientation for the whole (continuous) grid, fixed at a sample: top, roll and soffit
    # then all face the right way (the soffit down).
    i0, j0 = 0, 1
    sgn = 1.0 if N[i0][j0].dot(P[i0][j0] - ref(P[i0][j0])) > 0 else -1.0
    N = [[n * sgn for n in row] for row in N]
    C = [[col_fn(P[i][j], N[i][j], i, j) for j in range(nj)] for i in range(ni)]
    for i in range(ni):
        i2 = (i + 1) % ni
        for j in range(nj - 1):
            q = [(i, j, i), (i2, j, i + 1), (i2, j + 1, i + 1), (i, j + 1, i)]
            pts = [P[a][b] for a, b, _ in q]
            uvs = [(U[c][b] / tile, Vv[a][b] / tile) for a, b, c in q]
            ns = [N[a][b] for a, b, _ in q]
            cs = [C[a][b] for a, b, _ in q]
            fn = (pts[2] - pts[0]).cross(pts[3] - pts[1])
            if fn.dot(ns[0] + ns[1] + ns[2] + ns[3]) < 0:
                pts, uvs, ns, cs = pts[::-1], uvs[::-1], ns[::-1], cs[::-1]
            g.poly(pts, uvs, ns, cs, mat)


def thatch_roof(g, rng, W, D, ye, yr, over=0.48, thick=0.3, hip=0.8, sag=0.09, moss=0.6, fresh=0.3, smoke=0,
                ridge="riders", tone=1.0):
    """Hipped thatch over a W x D wall rectangle (centred, ridge along X). Wall plate at `ye`,
    ridge top `yr`; the eaves overhang by `over` with a thick, rounded, ragged lip. `smoke` = -1/+1
    opens a smoke-hole gablet at that hip end. `ridge`: "riders" (crossed poles weighting the ridge,
    the Slavic way) or "spars" (a bound ridge roll pinned with hazel spars)."""
    Dz = D / 2
    Dx = Dz * hip
    L = max(0.06, W / 2 - Dx)
    Rz = Dz + over
    tw = Dz / Rz
    Rx = Dx / tw
    dlt = (yr - ye - thick) / tw
    nzl = Noise(rng, 4, 0.8)
    nzh = Noise(rng, 3, 4.0)
    nzc = Noise(rng, 4, 1.1)
    span = L + Rx

    def sagv(x):
        f = min(abs(x) / span, 1.0)
        return sag * (1.0 - f * f)

    def ytop(p, t):
        lump = 0.045 * nzl(p * 1.0) + 0.015 * nzh(p * 1.0)
        return yr - dlt * t - sagv(p.x) * (1.0 - 0.5 * t) + lump * min(1.0, t * 3)

    nS = max(4, int(2 * L / 0.22))
    con = _stadium(L, Rx, Rz, nS, 16)
    t0 = 0.1
    tops = [t0 + (1 - t0) * (k / 10) ** 0.92 for k in range(11)]
    unders = [1.0, 0.94, (1 + tw) / 2, tw - 0.03]
    r0 = thick / 2
    P = []
    meta = []
    for fn, nout in con:
        e = fn(1.0)
        rag = 0.05 * nzh(e * 2.3) + rng.uniform(-0.02, 0.02)
        rr = r0 * (1.0 + 0.18 * nzh(e * 1.7 + V(5, 0, 0)))
        col_pts = []
        for t in tops:
            b = fn(t)
            col_pts.append(b + V(0, ytop(b, t), 0))
        yt1 = col_pts[-1].y
        droop = max(0.0, 0.05 * nzl(e * 1.3 + V(0, 2, 0)))
        for k in range(1, 7):
            a = math.pi * k / 7
            s = math.sin(a) ** 0.7
            col_pts.append(e + nout * (rr * s * 1.1 + rag * smoothstep(0.0, 0.6, k / 7)) +
                           V(0, yt1 - rr - droop * (k / 7) + rr * math.cos(a), 0))
        ybot = yt1 - 2 * rr - droop
        for t in unders:
            b = fn(t)
            y = ytop(b, t) - 2 * rr - droop * smoothstep(tw, 1.0, t)
            if t >= 0.999:
                y = ybot
                b = b + nout * (rag * 0.8)
            col_pts.append(b + V(0, y, 0))
        P.append(col_pts)
        meta.append(nout)
    jr = len(tops)
    sm = V(smoke * (L + Rx * 0.16), yr, 0)

    def col_fn(p, n, i, j):
        nout = meta[i]
        t = tops[j] if j < jr else 1.0
        c = mix(scale(THATCH_N, 1.06), scale(THATCH_N, 0.82), smoothstep(0.2, 1.0, t))
        f = smoothstep(0.3, 0.62, nzc(p * 0.7 + V(9, 0, 3))) * fresh
        c = mix(c, THATCH_FRESH, f * (1.0 - smoothstep(0.85, 1.0, t)))
        back = smoothstep(-0.2, -0.9, nout.z) * moss + 0.25 * moss
        m = back * smoothstep(0.45, 1.0, t) * (0.55 + 0.45 * nzl(p * 2.1 + V(1, 1, 1)))
        c = mix(c, THATCH_MOSS, max(0.0, min(m, 0.85)))
        if j >= jr + 5:
            c = scale(c, 0.42 if j > jr + 6 else 0.6)
        if smoke:
            c = mix(c, (0.2, 0.18, 0.16), 0.75 * (1 - smoothstep(0.2, 1.1, (p - sm).length)))
        c = scale(c, tone * (0.9 + 0.12 * nzh(p * 3.0)))
        st = PAINT.get("straw")
        return tuple(c[i] * st[i] for i in range(3)) if st else c

    shell(g, P, M_THATCH, col_fn, 0.9, lambda p: V(p.x * 0.3, p.y - 3.0, p.z * 0.3))

    # Ridge: a fat bound straw roll.
    ex = L + Rx * t0 * 0.6
    xs = [-ex - 0.05, -ex + 0.1, -L * 0.5, 0.0, L * 0.5, ex - 0.1, ex + 0.05]
    pts = [V(x, ytop(V(x, 0, 0), 0.02) + 0.02, 0) for x in xs]
    rm = min(0.22, 0.1 + 0.12 * ex)   # a short ridge gets a slimmer roll (no 'ball' on the hip)
    rad = [0.06, rm * 0.9, rm, rm, rm, rm * 0.9, 0.06]
    tube(g, pts, rad, 10, M_THATCH, scale(THATCH_N, 0.72 * tone), tile=0.6, uv_phase=rng.uniform(0, 2))
    if ridge == "riders":
        n = max(2, int((2 * ex) / 0.85))
        for x in np.linspace(-ex + 0.25, ex - 0.25, n):
            x = float(x) + rng.uniform(-0.06, 0.06)
            yb = ytop(V(x, 0, 0), 0.0)
            for sz in (-1, 1):
                foot = V(x, 0, sz * Rz * 0.42)
                foot.y = ytop(foot, 0.42) + 0.05
                top = V(x + rng.uniform(-0.04, 0.04), yb + 0.38, -sz * 0.24)
                pole(g, foot, top, 0.035, 0.03, rng, col=(0.62, 0.55, 0.45), sides=5, segs=2, wobble=0.008)
    else:
        for x in np.linspace(-ex + 0.2, ex - 0.2, max(3, int(2 * ex / 0.55))):
            for sz in (-1, 1):
                a_ = V(float(x), ytop(V(float(x), 0, 0), 0.0) + 0.12, sz * 0.14)
                tube(g, [a_, a_ + V(0.0, -0.1, sz * 0.24)], [0.012, 0.012], 4, M_BARK, (0.85, 0.78, 0.66), tile=0.3)
        for sz in (-1, 1):
            pts = [V(x, ytop(V(x, 0, 0), 0.0) + 0.11, sz * 0.17) for x in (-ex + 0.15, 0.0, ex - 0.15)]
            tube(g, pts, [0.014] * 3, 4, M_BARK, (0.8, 0.72, 0.6), tile=0.4)
    if smoke:
        # Smoke-hole gablet: a dark triangular vent at the hip end under a hood of straw.
        xs_ = smoke * (L + Rx * 0.12)
        yb = yr - dlt * 0.2 - 0.02
        ap = V(xs_, yr - 0.03, 0)
        bl_, br_ = V(xs_ + smoke * 0.08, yb, -0.26), V(xs_ + smoke * 0.08, yb, 0.26)
        face(g, [bl_, br_, ap], V(smoke, 0.3, 0), M_EARTH, VOID)
        for sz in (-1, 1):
            a_ = V(xs_ - smoke * 0.2, yr + 0.1, 0)
            e_ = V(xs_ + smoke * 0.16, yb - 0.04, sz * 0.36)
            tube(g, [a_, a_.lerp(e_, 0.5) + V(0, 0.03, 0), e_], [0.12, 0.11, 0.07], 8, M_THATCH,
                 scale(THATCH_N, 0.55), tile=0.6)
    return dict(L=L, Rx=Rx, Rz=Rz, tw=tw, dlt=dlt)


def _walls(W, D):
    return [((-W / 2, D / 2), (W / 2, D / 2)), ((W / 2, D / 2), (W / 2, -D / 2)),
            ((W / 2, -D / 2), (-W / 2, -D / 2)), ((-W / 2, -D / 2), (-W / 2, D / 2))]


def _pieces(L, y0, y1, ops):
    """Wall rectangles (s0, s1, ya, yb) around the openings."""
    ops = sorted(ops, key=lambda o: o["s"])
    out, s = [], 0.0
    for o in ops:
        a, b = o["s"] - o["w"] / 2, o["s"] + o["w"] / 2
        if a > s + 0.02:
            out.append((s, a, y0, y1))
        if o["y0"] > y0 + 0.05:
            out.append((a, b, y0, o["y0"]))
        if o["y1"] < y1 - 0.05:
            out.append((a, b, o["y1"], y1))
        s = b
    if s < L - 0.02:
        out.append((s, L, y0, y1))
    return out


def footing(g, rng, W, D, y_top=0.22, gap=0.3, skip=()):
    """A course of fieldstones under the walls, half sunk."""
    nz = Noise(rng, 3, 2.0)
    for wi, (a, b) in enumerate(_walls(W, D)):
        A, B = V(a[0], 0, a[1]), V(b[0], 0, b[1])
        t = (B - A).normalized()
        L = (B - A).length
        n = max(2, int(L / gap))
        for k in range(n + 1):
            s = L * k / n + rng.uniform(-0.05, 0.05)
            if any(wi == w and lo < s < hi for w, lo, hi in skip):
                continue
            rx, ry, rz = rng.uniform(0.16, 0.22), rng.uniform(0.1, 0.15), rng.uniform(0.13, 0.18)
            c = A + t * s + t.cross(UP) * rng.uniform(0.0, 0.05) + UP * (y_top - ry * 1.1)
            stone(g, c, (rx, ry, rz), rng, mat=M_ROCK, detail=1, rough=0.12, rot=yaw(t) @ quat_y(rng.uniform(-0.3, 0.3)),
                  col_fn=rock_col(scale((0.82, 0.8, 0.75), rng.uniform(0.75, 0.95)), moss=0.45, ground=0.0, noise=nz),
                  tile=0.6)


def opening_dress(g, rng, A, t, n, T, o, mat_void=M_EARTH, jamb=True):
    """Door / window furniture in a wall from A along t (outward n): jambs + lintel, the dark
    interior, a door leaf (ajar) or a hanging shutter, a threshold stone."""
    s0, s1 = o["s"] - o["w"] / 2, o["s"] + o["w"] / 2
    y0, y1 = o["y0"], o["y1"]
    P = lambda s, y, off=0.0: A + t * s + UP * y + n * off
    face(g, [P(s0, y0, -T / 2 + 0.02), P(s1, y0, -T / 2 + 0.02), P(s1, y1, -T / 2 + 0.02), P(s0, y1, -T / 2 + 0.02)],
         n, mat_void, VOID)
    if jamb:
        for s in (s0 - 0.04, s1 + 0.04):
            pole(g, P(s, y0 - 0.25 if o["kind"] == "door" else y0 - 0.08, T * 0.3),
                 P(s, y1 + 0.1, T * 0.3), 0.05, 0.045, rng, col=POSTC, sides=6, segs=2)
        pole(g, P(s0 - 0.22, y1 + 0.06, T * 0.35), P(s1 + 0.22, y1 + 0.06 + rng.uniform(-0.02, 0.02), T * 0.35),
             0.055, 0.05, rng, col=scale(POSTC, 0.9), sides=6, segs=2)
    if o["kind"] == "door":
        hinge = P(s0 + 0.02, y0, T / 2 - 0.08)
        door_leaf(g, rng, hinge, t, n, o["w"] - 0.04, y1 - y0 - 0.03, o.get("ajar", 0.5), col=PAINT.get("door", (0.56, 0.5, 0.42)))
        slab(g, P(o["s"], -0.02, T / 2 + 0.22), (o["w"] + 0.2, 0.1, 0.4), yaw(t) @ quat_y(rng.uniform(-0.08, 0.08)),
             rng, res=(3, 1, 2), round_r=0.04, rough=0.08, col_fn=rock_col((0.78, 0.76, 0.72), moss=0.2), tile=0.6)
    else:
        # A single plank shutter hung from the top, propped half open, or swung aside.
        h = y1 - y0
        if o.get("prop", True):
            ang = rng.uniform(0.9, 1.2)
            top = P(o["s"], y1 + 0.02, T / 2 + 0.02)
            d = (n * math.sin(ang) - UP * math.cos(ang)).normalized()
            board(g, top + d * (h / 2), t, d.cross(t), o["w"] + 0.06, h + 0.04, 0.035, mat=M_PLANK,
                  col=scale(PAINT.get("shutter", (0.58, 0.52, 0.44)), rng.uniform(0.8, 1.0)), rng=rng)
            pole(g, P(o["s"] + 0.1, y0 - 0.02, T / 2 + 0.02), top + d * (h * 0.9), 0.012, 0.012, rng,
                 col=(0.7, 0.62, 0.5), sides=4, segs=1)
        else:
            ang = rng.uniform(1.6, 2.2)
            hinge = P(s1 + 0.02, y0, T / 2 + 0.02)
            d = (-t * math.cos(math.pi - ang) + n * math.sin(math.pi - ang)).normalized()
            board(g, hinge + d * (o["w"] / 2) + UP * (h / 2), (0, 1, 0), d.cross(UP), h + 0.04, o["w"] + 0.04, 0.035,
                  mat=M_PLANK, col=scale(PAINT.get("shutter", (0.58, 0.52, 0.44)), rng.uniform(0.8, 1.0)), rng=rng)


def daub_walls(g, rng, W, D, y0, ye, ops, T=0.18, finish="clay", patches=3, posts=True):
    """Clay daub over wattle between rough posts: lumpy slabs around the openings, a few patches
    where the daub fell off and the weave shows; corner posts + a round wall plate crossing at the
    corners. finish "clay" (bare, s_earth) or "lime" (old dirty limewash, s_plaster)."""
    nz = Noise(rng, 4, 1.6)
    mat = M_EARTH if finish == "clay" else M_PLASTER
    base = PAINT.get("wall") or (CLAY if finish == "clay" else LIME_OLD)
    walls = _walls(W, D)
    holes = []
    for wi, (a, b) in enumerate(walls):
        A, B = V(a[0], 0, a[1]), V(b[0], 0, b[1])
        t = (B - A).normalized()
        n = t.cross(UP)
        L = (B - A).length
        pcs = _pieces(L, y0, ye, ops[wi])
        tall = [p for p in pcs if p[3] - p[2] > ye - y0 - 0.1 and p[1] - p[0] > 0.8]
        for _ in range(patches + 1 if tall else 0):
            p = tall[rng.integers(len(tall))]
            s = rng.uniform(p[0] + 0.35, p[1] - 0.35)
            y = rng.uniform(y0 + 0.3, ye - 0.3)
            holes.append((A + t * s + UP * y + n * (T / 2), t, n, rng.uniform(0.16, 0.3), rng.uniform(0.12, 0.22)))

        def col_fn(p, nn, base=base):
            k = 0.88 + 0.16 * nz(p * 1.5)
            c = scale(base, k)
            c = mix(scale((0.55, 0.47, 0.38), 0.9), c, smoothstep(y0, y0 + 0.5, p.y))
            c = mix(c, (0.42, 0.38, 0.34), 0.35 * smoothstep(ye - 0.45, ye, p.y))
            for hc, ht, hn, rx, ry in holes:
                d = p - hc
                e = (d.dot(ht) / (rx * 1.35)) ** 2 + (d.y / (ry * 1.35)) ** 2
                if e < 1.0 and abs(d.dot(hn)) < 0.08:
                    c = mix(c, DAUB_HOLE, smoothstep(1.0, 0.55, e))
            return c

        for s0, s1, ya, yb in pcs:
            Lp, h = s1 - s0, yb - ya
            c = A + t * ((s0 + s1) / 2) + UP * ((ya + yb) / 2)
            slab(g, c, (Lp + 0.02, h, T), yaw(t), rng, mat=mat, col_fn=col_fn, tile=1.1,
                 res=(max(2, int(Lp / 0.28)), max(2, int(h / 0.28)), 1), round_r=0.02, rough=0.2)
        # Rough studs through the daub every ~1.1 (skipping the openings) and a sill pole.
        k = max(1, int(L / 1.1))
        for i in range(1, k):
            s = L * i / k
            if any(abs(s - o["s"]) < o["w"] / 2 + 0.15 for o in ops[wi]):
                continue
            pole(g, A + t * s + n * (T * 0.42) + UP * (y0 - 0.05), A + t * s + n * (T * 0.42) + UP * (ye - 0.02),
                 0.06, 0.055, rng, col=scale(POSTC, rng.uniform(0.8, 1.0)), sides=6, segs=2)
        pole(g, A + n * (T * 0.4) + UP * (y0 + 0.02), A + t * L + n * (T * 0.4) + UP * (y0 + 0.02), 0.07, 0.065, rng,
             col=scale(POSTC, 0.75), sides=6, segs=3)
        for o in ops[wi]:
            opening_dress(g, rng, A, t, n, T, o)
    # The exposed wattle where the daub fell away.
    for hc, ht, hn, rx, ry in holes:
        for k in range(-1, 2):
            s = hc + ht * (k * rx * 0.55) + hn * 0.005
            pole(g, s - UP * ry * 1.1, s + UP * ry * 1.1, 0.014, 0.014, rng, col=(0.62, 0.55, 0.44), sides=4, segs=1)
        for r in range(4):
            y = -ry * 0.8 + r * ry * 0.53
            pts = [hc + ht * (x * rx) + UP * y + hn * (0.012 if (r + q) % 2 else -0.004)
                   for q, x in enumerate((-1.0, -0.5, 0.0, 0.5, 1.0))]
            tube(g, pts, [0.011] * 5, 4, M_BARK, (0.85, 0.76, 0.6), tile=0.4, cap=False)
    if posts:
        for x, z in ((-W / 2, D / 2), (W / 2, D / 2), (W / 2, -D / 2), (-W / 2, -D / 2)):
            pole(g, V(x, -0.15, z), V(x + rng.uniform(-0.02, 0.02), ye + 0.05, z), 0.11, 0.09, rng, col=POSTC,
                 sides=7, segs=3, col_fn=weathered(POSTC, 0.62))
        for a, b in walls:
            A, B = V(a[0], ye + 0.02, a[1]), V(b[0], ye + 0.02, b[1])
            t = (B - A).normalized()
            pole(g, A - t * 0.18, B + t * 0.18, 0.075, 0.07, rng, col=scale(POSTC, 0.85), sides=6, segs=3)


def log_walls(g, rng, W, D, y0, ye, ops, r=0.12):
    """Rough grey logs, saddle-notched corners overhanging, moss chinking between the courses;
    openings framed with split jamb boards."""
    step = 2 * r * 0.9
    n = max(3, int(round((ye - y0) / step)))
    step = (ye - y0) / n
    for wi, (a, b) in enumerate(_walls(W, D)):
        A, B = V(a[0], 0, a[1]), V(b[0], 0, b[1])
        t = (B - A).normalized()
        nn = t.cross(UP)
        L = (B - A).length
        off = 0.0 if wi % 2 == 0 else step / 2
        for k in range(-(wi % 2), n):
            y = y0 + r + k * step + off
            if y - r > ye - 0.02:
                continue
            segs = [(-0.26, L + 0.26)]
            for o in ops[wi]:
                if o["y0"] - 0.02 < y < o["y1"] + r * 0.6:
                    cut = []
                    for s0, s1 in segs:
                        a_, b_ = o["s"] - o["w"] / 2 - 0.04, o["s"] + o["w"] / 2 + 0.04
                        if b_ <= s0 or a_ >= s1:
                            cut.append((s0, s1))
                            continue
                        if a_ > s0 + 0.1:
                            cut.append((s0, a_))
                        if b_ < s1 - 0.1:
                            cut.append((b_, s1))
                    segs = cut
            for s0, s1 in segs:
                rr = r * rng.uniform(0.88, 1.08)
                p0 = A + t * (s0 + rng.uniform(-0.04, 0.04)) + UP * y
                p1 = A + t * (s1 + rng.uniform(-0.04, 0.04)) + UP * (y + rng.uniform(-0.015, 0.015))
                pole(g, p0, p1, rr, rr * 0.9, rng, mat=M_TIMBER, col=scale(PAINT.get("log", LOGC), rng.uniform(0.78, 1.0)), sides=9,
                     segs=3, wobble=0.012, tile=0.8)
                if k > 0:
                    a_, b_ = max(s0, 0.1), min(s1, L - 0.1)
                    if b_ - a_ > 0.2:
                        tube(g, [A + t * a_ + UP * (y - step / 2) + nn * (r * 0.45),
                                 A + t * b_ + UP * (y - step / 2) + nn * (r * 0.45)],
                             [r * 0.32, r * 0.32], 5, M_EARTH, (0.5, 0.52, 0.36), tile=0.5)
        for o in ops[wi]:
            for s in (o["s"] - o["w"] / 2 - 0.05, o["s"] + o["w"] / 2 + 0.05):
                board(g, A + t * s + UP * ((o["y0"] + o["y1"]) / 2 - 0.05) + nn * (r * 0.75), (0, 1, 0), nn,
                      o["y1"] - o["y0"] + 0.4, 0.13, 0.06, mat=M_PLANK, col=(0.6, 0.55, 0.47), rng=rng)
            opening_dress(g, rng, A, t, nn, 2 * r, o, jamb=False)
    # A wall plate log on top, crossing at the corners.
    for a, b in _walls(W, D)[0::2]:
        A, B = V(a[0], ye + 0.05, a[1]), V(b[0], ye + 0.05, b[1])
        t = (B - A).normalized()
        pole(g, A - t * 0.3, B + t * 0.3, r * 0.95, r * 0.85, rng, mat=M_TIMBER, col=scale(PAINT.get("log", LOGC), 0.8), sides=9, segs=3)


def muck_heap(g, rng, c, rx=0.9, rz=0.7, h=0.45):
    mound(g, c, rx, rz, h, rng, mat=M_EARTH, col_fn=lambda p, n: (0.36, 0.3, 0.24), rings=5, seg=16, rough=0.2)
    for _ in range(5):
        p = V(c[0] + rng.uniform(-rx, rx) * 0.5, h * 0.7, c[2] + rng.uniform(-rz, rz) * 0.5)
        frustum(g, 0.25, 0.05, p.y - 0.12, 0.18, 7, M_THATCH, (0.8, 0.7, 0.5), tile=0.5, centre=(p.x, 0, p.z),
                jitter=0.05, rng=rng)


def firewood(g, rng, c, yaw_a, L=1.2, rows=3):
    """Split logs stacked against a wall (no frame)."""
    q = quat_y(yaw_a)
    C = Vector(c)
    for r in range(rows):
        k = int(L / 0.2) - r
        for i in range(k):
            x = -L / 2 + (i + 0.5 + r * 0.5) * L / (k + r)
            p = C + q @ V(x, 0.09 + r * 0.16, 0)
            pole(g, p + q @ V(0, 0, -0.24), p + q @ V(0, 0, 0.24), 0.085, 0.085, rng, col=(0.72, 0.62, 0.5), sides=5,
                 segs=1, wobble=0.0)


def wattle_hurdle(g, rng, p0, p1, h=0.75):
    hurdle(g, rng, Vector(p0), Vector(p1), h=h, gap=0.36, rods=7)


def _ops(*walls):
    return [list(w) for w in walls]


def DOOR(s, w=0.78, h=1.16, ajar=0.5):
    return dict(s=s, w=w, y0=0.12, y1=0.12 + h, kind="door", ajar=ajar)


def WIN(s, w=0.4, y0=0.72, h=0.32, prop=True):
    return dict(s=s, w=w, y0=y0, y1=y0 + h, kind="window", prop=prop)


def rotate_tail(b, v0, f0, a):
    """Turn every vertex / normal added since (v0, f0) by `a` about game +Y."""
    q = quat_y(a)
    for i in range(v0, len(b.verts)):
        x, y, z = b.verts[i]
        p = q @ V(x, z, -y)
        b.verts[i] = tuple(bl(p))
    for k in range(f0, len(b.faces)):
        idx, uvs, nrms, cols, mat = b.faces[k]
        out = []
        for n in nrms:
            x, y, z = n
            p = q @ V(x, z, -y)
            out.append(tuple(bn(p)))
        b.faces[k] = (idx, uvs, out, cols, mat)


# ─────────────────────────────────────────────────────────────── the four lane cottages

def town_house_c(rng):
    """Tiny one-room hut: bare clay daub, smoke hole, riders on the ridge; a bench, a bucket and a
    hurdle pen by the door."""
    b = Builder()
    g = G(b)
    W, D, ye = 3.4, 2.8, 1.32
    ops = _ops([DOOR(1.15, ajar=0.9), WIN(2.55)], [WIN(1.4, prop=False)], [], [])
    footing(g, rng, W, D, skip=[(0, 0.65, 1.65)])
    daub_walls(g, rng, W, D, 0.16, ye, ops, finish="clay", patches=2)
    thatch_roof(g, rng, W, D, ye, 3.05, over=0.46, hip=0.85, smoke=-1, ridge="riders", moss=0.7, fresh=0.15,
                tone=0.92)
    bench(g, rng, V(2.0 - W / 2 + 0.35, 0.0, D / 2 + 0.45), 0.0, L=0.9)
    bucket(g, (-W / 2 + 0.55, 0.0, D / 2 + 0.5))
    hurdle(g, rng, V(W / 2 + 0.35, 0, D / 2 + 1.2), V(W / 2 + 0.35, 0, -D / 2 + 0.2), h=0.7)
    hurdle(g, rng, V(W / 2 + 0.35, 0, D / 2 + 1.2), V(W / 2 - 0.9, 0, D / 2 + 1.2), h=0.7)
    firewood(g, rng, (-W / 2 - 0.32, 0.0, -0.4), math.pi / 2, L=1.2, rows=3)
    return b


def town_house_b(rng):
    """Log longhouse: the family at the west end, the byre (+X) behind a wide door, its muck heap
    out front; a bound ridge with spars; a clay-and-wattle smoke hole at the dwelling end."""
    b = Builder()
    g = G(b)
    W, D, ye = 6.0, 3.2, 1.38
    ops = _ops([DOOR(1.4, ajar=0.35), WIN(2.45), DOOR(4.75, w=1.15, h=1.2, ajar=1.2)], [WIN(1.6, prop=False)],
               [WIN(4.2)], [])
    footing(g, rng, W, D, y_top=0.2, skip=[(0, 0.95, 1.85), (0, 4.1, 5.4)])
    log_walls(g, rng, W, D, 0.18, ye, ops, r=0.12)
    thatch_roof(g, rng, W, D, ye + 0.1, 3.35, over=0.5, hip=0.75, smoke=-1, ridge="spars", moss=0.55, fresh=0.35,
                sag=0.14)
    muck_heap(g, rng, (W / 2 - 0.3, 0.0, D / 2 + 1.35), rx=0.95, rz=0.6, h=0.42)
    pole(g, V(W / 2 + 0.1, 0.3, D / 2 + 1.2), V(W / 2 + 0.7, 1.4, D / 2 + 1.5), 0.025, 0.022, rng, col=(0.7, 0.6, 0.48),
         sides=5, segs=2)  # pitchfork stuck in the muck
    for k in range(3):
        tube(g, [V(W / 2 + 0.68 + 0.04 * (k - 1), 1.38, D / 2 + 1.49), V(W / 2 + 0.75 + 0.05 * (k - 1), 1.62, D / 2 + 1.6)],
             [0.008, 0.006], 4, M_IRON, IRON_D, tile=0.2)
    firewood(g, rng, (-W / 2 - 0.32, 0.0, 0.1), math.pi / 2, L=1.6, rows=4)
    chopping_block(g, rng, (-W / 2 - 1.0, 0.0, D / 2 + 0.6))
    barrel(g, rng, (0.4, 0.0, D / 2 + 0.45))
    return b


def town_house_a(rng):
    """Daub cottage (old limewash) with a thatched lean-to on its west end: firewood, a ladder,
    a hay fork; a crude clay chimney through the thatch, a bench by the door."""
    b = Builder()
    g = G(b)
    W, D, ye = 3.9, 3.0, 1.34
    ox = 0.65   # main body shifted east so body + lean-to centre on the pivot
    v0, f0 = len(b.verts), len(b.faces)
    ops = _ops([WIN(0.8), DOOR(2.1, ajar=0.45)], [WIN(1.5)], [WIN(2.3, prop=False)], [])
    footing(g, rng, W, D, skip=[(0, 1.6, 2.6)])
    daub_walls(g, rng, W, D, 0.17, ye, ops, finish="lime", patches=3)
    info = thatch_roof(g, rng, W, D, ye, 3.2, over=0.46, hip=0.8, ridge="riders", moss=0.5, fresh=0.4)
    # Clay-daubed wattle chimney stack poking through the east slope near the ridge.
    cx_, cz_ = 0.7, -0.35
    yb = 3.2 - info["dlt"] * (abs(cz_) / info["Rz"]) - 0.2
    slab(g, V(cx_, yb + 0.45, cz_), (0.46, 1.0, 0.42), quat_y(0.05), rng, mat=M_EARTH, res=(2, 4, 2), round_r=0.06,
         rough=0.3, taper=0.18, col_fn=lambda p, n: mix((0.62, 0.52, 0.42), (0.16, 0.14, 0.12), smoothstep(yb + 0.6, yb + 1.0, p.y)),
         tile=0.8)
    for k in range(3):
        stone(g, V(cx_ + rng.uniform(-0.12, 0.12), yb + 0.98, cz_ + rng.uniform(-0.1, 0.1)), (0.1, 0.06, 0.08), rng,
              detail=1, rough=0.1, col_fn=rock_col((0.5, 0.48, 0.45)))
    # Lean-to on -X: three posts, a thatched pent roof down from under the main eave.
    x_out = -W / 2 - 1.35
    for z in (-D / 2 + 0.1, 0.0, D / 2 - 0.1):
        pole(g, V(x_out, -0.15, z), V(x_out + rng.uniform(-0.03, 0.03), 0.7, z), 0.07, 0.06, rng, col=POSTC, sides=6)
    pole(g, V(x_out, 0.7, -D / 2 - 0.25), V(x_out, 0.68, D / 2 + 0.25), 0.065, 0.06, rng, col=POSTC, sides=6)
    yt, yo = 0.92, 0.66
    th = math.atan2(yt - yo, 1.35)
    q = quat_z(th)
    cc = V((-W / 2 + x_out) / 2 - 0.15, (yt + yo) / 2 + 0.12, 0.0)
    slab(g, cc, (1.75, 0.22, D + 0.6), q, rng, mat=M_THATCH, res=(4, 1, 6), round_r=0.09, rough=0.35,
         col_fn=lambda p, n: mix(scale(THATCH_N, 0.95), THATCH_MOSS, 0.3 * smoothstep(-0.6, -1.0, p.x / 2.6)), tile=0.9)
    firewood(g, rng, (-W / 2 - 0.45, 0.0, -0.45), math.pi / 2, L=1.6, rows=4)
    firewood(g, rng, (-W / 2 - 1.0, 0.0, 0.55), math.pi / 2, L=1.0, rows=3)
    ladder(g, rng, V(-W / 2 + 0.9, 0.0, D / 2 + 0.55), V(-W / 2 + 0.75, 2.05, D / 2 - 0.05), width=0.4)
    bench(g, rng, V(1.05, 0.0, D / 2 + 0.45), 0.0, L=1.0)
    chopping_block(g, rng, (-W / 2 - 0.6, 0.0, D / 2 + 0.95))
    for i in range(v0, len(b.verts)):
        x, y, z = b.verts[i]
        b.verts[i] = (x + ox, y, z)
    return b


def town_house_d(rng):
    """Hovel half dug-in: an earth bank heaped against low clay walls, the thatch sweeping down
    almost to the bank, a stone-lined entry with the low door; turf patches on the bank."""
    b = Builder()
    g = G(b)
    W, D, ye = 4.0, 3.0, 1.26
    ops = _ops([DOOR(2.0, w=0.76, h=1.12, ajar=0.7)], [WIN(1.5, y0=0.78, h=0.28)], [], [])
    daub_walls(g, rng, W, D, 0.1, ye, ops, finish="clay", patches=1)
    thatch_roof(g, rng, W, D, ye, 2.95, over=0.62, thick=0.34, hip=0.9, smoke=1, ridge="riders", moss=0.9,
                fresh=0.1, sag=0.12, tone=0.86)
    nz = Noise(rng, 4, 1.2)
    # The bank: a ring of earth around the walls, up to ~0.6, broken at the entry.
    def bank_col(p, n):
        c = mix((0.42, 0.36, 0.28), (0.4, 0.5, 0.26), smoothstep(0.4, 0.95, n.y) * (0.6 + 0.4 * nz(p * 2)))
        return scale(c, 0.9 + 0.15 * nz(p * 4))
    segs = []
    perim = [(-W / 2 - 0.35, D / 2 + 0.35), (W / 2 + 0.35, D / 2 + 0.35), (W / 2 + 0.35, -D / 2 - 0.35),
             (-W / 2 - 0.35, -D / 2 - 0.35)]
    for k in range(4):
        a, c = V(perim[k][0], 0, perim[k][1]), V(perim[(k + 1) % 4][0], 0, perim[(k + 1) % 4][1])
        L = (c - a).length
        n = int(L / 0.55)
        for i in range(n + 1):
            p = a.lerp(c, i / n)
            if k == 0 and abs(p.x - (-W / 2 + 2.0)) < 0.8:
                continue
            segs.append(p)
    for p in segs:
        mound(g, (p.x, 0.0, p.z), 0.62, 0.62, rng.uniform(0.5, 0.62), rng, col_fn=bank_col, rings=4, seg=10,
              rough=0.15)
    # The entry: stone cheeks either side of the door, a step down (dark).
    for sx in (-1, 1):
        for k in range(3):
            stone(g, V(-W / 2 + 2.0 + sx * (0.58 + 0.05 * k), 0.14 + 0.2 * k, D / 2 + 0.25 + 0.18 * k - 0.1 * k),
                  (0.2, 0.13, 0.18), rng, detail=1, rough=0.12, col_fn=rock_col((0.78, 0.76, 0.7), moss=0.4))
    pole(g, V(W / 2 + 0.2, -0.1, D / 2 + 0.9), V(W / 2 + 0.25, 1.0, D / 2 + 0.95), 0.04, 0.035, rng, col=POSTC, sides=5)
    firewood(g, rng, (W / 2 + 0.9, 0.0, 0.2), math.pi / 2, L=1.0, rows=2)
    bucket(g, (-W / 2 + 1.1, 0.0, D / 2 + 0.75))
    return b


# ─────────────────────────────────────────────────────────────── the street cottages
# Ridge along Z (the gable / hip end + door to the road at +Z). Built with the ridge along X, the
# road end at +X, then turned a quarter (+X -> +Z).

def town_street_house_a(rng):
    """Long daub cottage, door + window on the road end, a back door to the yard, a byre-end at the
    back with a hay loft hatch, smoke hole over the hearth, bench + bucket by the door."""
    b = Builder()
    g = G(b)
    W, D, ye = 7.2, 4.0, 1.4
    v0, f0 = len(b.verts), len(b.faces)
    # walls: 0 = -Z long side (ends up -X... after the turn: front(+Z local) -> -X world)
    ops = _ops([WIN(2.0), WIN(5.0, prop=False)], [DOOR(1.6, ajar=0.6), WIN(3.0)], [WIN(3.6)],
               [DOOR(2.6, w=0.95, ajar=0.2)])
    footing(g, rng, W, D, skip=[(1, 1.1, 2.1), (3, 2.0, 3.2)])
    daub_walls(g, rng, W, D, 0.17, ye, ops, finish="clay", patches=3)
    thatch_roof(g, rng, W, D, ye, 3.65, over=0.5, hip=0.7, smoke=1, ridge="riders", moss=0.6, fresh=0.35, sag=0.15)
    bench(g, rng, V(W / 2 + 0.45, 0.0, -0.9), math.pi / 2, L=1.1)
    bucket(g, (W / 2 + 0.55, 0.0, 1.35))
    firewood(g, rng, (0.5, 0.0, -D / 2 - 0.35), 0.0, L=2.2, rows=4)
    chopping_block(g, rng, (-1.4, 0.0, -D / 2 - 0.9))
    rotate_tail(b, v0, f0, -math.pi / 2)
    return b


def town_street_house_b(rng):
    """Log cottage of a craftsman who sells at his window: the road-end shutter folded down into a
    counter (pots, a cloth, loaves), the upper one propped as an awning; clay chimney; barrel."""
    b = Builder()
    g = G(b)
    W, D, ye = 6.6, 4.4, 1.42
    v0, f0 = len(b.verts), len(b.faces)
    shop = dict(s=2.95, w=1.3, y0=0.66, y1=1.18, kind="window", prop=True)
    ops = _ops([WIN(2.2)], [DOOR(1.0, ajar=0.4), shop], [WIN(4.0, prop=False)], [DOOR(2.2, w=0.9, ajar=0.15)])
    footing(g, rng, W, D, y_top=0.2, skip=[(1, 0.5, 1.5)])
    log_walls(g, rng, W, D, 0.18, ye, ops, r=0.125)
    info = thatch_roof(g, rng, W, D, ye + 0.1, 3.6, over=0.5, hip=0.72, ridge="spars", moss=0.45, fresh=0.45, sag=0.1)
    # Counter: the lower shutter folded down on two legs (wall 1 = +X end, outward +X).
    x0 = W / 2 + 0.13
    zc = D / 2 - 2.95
    board(g, V(x0 + 0.28, 0.68, zc), (0, 0, 1), (0, 1, 0), 1.36, 0.5, 0.05, mat=M_PLANK, col=(0.6, 0.53, 0.44), rng=rng)
    for dz in (-0.55, 0.55):
        pole(g, V(x0 + 0.45, -0.1, zc + dz), V(x0 + 0.45, 0.66, zc + dz), 0.03, 0.028, rng, col=POSTC, sides=5, segs=1)
    for k, dz in enumerate((-0.42, -0.1, 0.25)):
        lathe(g, (x0 + 0.3, 0.71, zc + dz), (0, 1, 0), [(0.0, 0.06), (0.1, 0.1), (0.2, 0.075), (0.24, 0.08)], 9, M_EARTH,
              scale((0.85, 0.55, 0.38), 0.9 + 0.1 * k), tile=0.3)
    stone(g, V(x0 + 0.25, 0.75, zc + 0.5), (0.12, 0.06, 0.09), rng, mat=M_EARTH, detail=1, rough=0.1,
          col_fn=lambda p, n: (0.85, 0.66, 0.42), cuts=0)
    lbox(g, V(x0 + 0.28, 0.715, zc - 0.05), (0.42, 0.02, 0.5), quat_y(0.1), M_CLOTH, (0.62, 0.66, 0.78), tile=0.4)
    # Clay chimney through the slope near the ridge.
    cz_ = -0.4
    yb = 3.6 - info["dlt"] * (abs(cz_) / info["Rz"]) - 0.25
    slab(g, V(-0.9, yb + 0.5, cz_), (0.5, 1.1, 0.46), quat_y(-0.04), rng, mat=M_EARTH, res=(2, 4, 2), round_r=0.06,
         rough=0.3, taper=0.16, col_fn=lambda p, n: mix((0.64, 0.54, 0.44), (0.15, 0.13, 0.12), smoothstep(yb + 0.7, yb + 1.1, p.y)),
         tile=0.8)
    barrel(g, rng, (W / 2 + 0.45, 0.0, -1.85))
    firewood(g, rng, (-W / 2 - 0.35, 0.0, 0.0), math.pi / 2, L=2.4, rows=4)
    rotate_tail(b, v0, f0, -math.pi / 2)
    return b


# ─────────────────────────────────────────────────────────────── the producer yards
# town.rs plots (world units, pivot = plot centre, no yaw): the building on the -X half (collider
# centre x -1.28, half 1.42 x 1.28), the working yard on the +X half stays walkable (low props).

BX = -1.28


def shift_tail(b, v0, dx):
    for i in range(v0, len(b.verts)):
        x, y, z = b.verts[i]
        b.verts[i] = (x + dx, y, z)


def stook(g, rng, c, h=0.62):
    """A wheat stook: sheaves leaned together, ears up."""
    C = Vector(c)
    for k in range(6):
        a = 2 * math.pi * k / 6 + rng.uniform(-0.2, 0.2)
        foot = C + V(math.cos(a) * 0.2, -0.04, math.sin(a) * 0.2)
        top = C + V(math.cos(a) * 0.04, h, math.sin(a) * 0.04)
        tube(g, [foot, foot.lerp(top, 0.55), top, top + V(math.cos(a) * 0.08, 0.1, math.sin(a) * 0.08)],
             [0.075, 0.055, 0.065, 0.03], 6, M_THATCH, scale((1.25, 1.02, 0.6), rng.uniform(0.85, 1.0)), tile=0.4)


M_TMATTE = len(MATS)
MATS = MATS + ["s_timber_matte"]   # matte twin of s_timber (no sky sheen on the barn boards)
BOARD_CENTRES[M_TMATTE] = BOARD_CENTRES[M_TIMBER]


def plank_walls(g, rng, W, D, y0, ye, ops, T=0.14):
    """Board-and-batten barn walls: a squared sill beam on the footing, squared corner and door
    posts, a wall plate, vertical weathered boards (uneven bottoms, a few gaps) with battens over the
    joints; the openings dressed like the huts'."""
    cols = [scale((1.0, 0.72, 0.46), rng.uniform(0.88, 1.0)) for _ in range(9)]
    for wi, (a, b) in enumerate(_walls(W, D)):
        A, B = V(a[0], 0, a[1]), V(b[0], 0, b[1])
        t = (B - A).normalized()
        n = t.cross(UP)
        L = (B - A).length
        q = yaw(t)
        lbox(g, A + t * (L / 2) + UP * (y0 + 0.07), (L + 0.24, 0.14, T + 0.04), q, M_TIMBER, scale(POSTC, 0.72),
             tile=0.6)
        lbox(g, A + t * (L / 2) + UP * (ye - 0.06), (L + 0.24, 0.13, T + 0.06), q, M_TIMBER, scale(POSTC, 0.8),
             tile=0.6)
        lbox(g, A + UP * ((y0 + ye) / 2), (0.16, ye - y0, 0.16), q, M_TIMBER, scale(POSTC, 0.75), tile=0.6)
        for o in ops[wi]:
            if o["kind"] == "door":
                for s in (o["s"] - o["w"] / 2 - 0.07, o["s"] + o["w"] / 2 + 0.07):
                    lbox(g, A + t * s + UP * ((y0 + ye) / 2), (0.13, ye - y0, T + 0.02), q, M_TIMBER,
                         scale(POSTC, 0.78), tile=0.6)
        for s0, s1, ya, yb in _pieces(L, y0 + 0.14, ye - 0.12, ops[wi]):
            nb = max(1, int(round((s1 - s0) / 0.22)))
            bw = (s1 - s0) / nb
            for k in range(nb):
                s = s0 + (k + 0.5) * bw
                lo = ya + (rng.uniform(-0.03, 0.04) if ya < y0 + 0.2 else 0.0)
                hgt = yb - lo
                if hgt < 0.06:
                    continue
                board(g, A + t * s + UP * (lo + hgt / 2) + n * (T / 2 - 0.02), (0, 1, 0), tuple(n), hgt,
                      bw - (0.018 if rng.random() < 0.85 else 0.04), 0.035, mat=M_TMATTE,
                      col=cols[int(rng.integers(0, len(cols)))], rng=rng)
                if k > 0:
                    board(g, A + t * (s - bw / 2) + UP * (lo + hgt / 2) + n * (T / 2 + 0.02), (0, 1, 0), tuple(n),
                          hgt - 0.02, 0.06, 0.025, mat=M_TMATTE, col=scale(POSTC, 0.62), rng=rng)
                # Inside face, so the open door shows a planked interior.
                face(g, [A + t * (s - bw / 2) + UP * lo - n * 0.02, A + t * (s + bw / 2) + UP * lo - n * 0.02,
                         A + t * (s + bw / 2) + UP * yb - n * 0.02, A + t * (s - bw / 2) + UP * yb - n * 0.02],
                     -n, M_PLANK, scale(POSTC, 0.4))
        for o in ops[wi]:
            opening_dress(g, rng, A, t, n, T, o, jamb=False)


def hay_barrack(g, rng, c, hw=0.55, H=2.6, roof_y=2.25):
    """A hay barrack: four tall pegged poles carrying a sliding pyramid roof of thatch over a
    loaf of loose hay."""
    c = Vector(c)
    corners = [c + V(sx * hw, 0, sz * hw) for sx, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    for p in corners:
        pole(g, p - UP * 0.25, p + UP * H + V(rng.uniform(-0.02, 0.02), 0, rng.uniform(-0.02, 0.02)), 0.05, 0.04, rng,
             col=POSTC, sides=6, segs=3)
        for y in np.arange(0.9, H - 0.1, 0.3):
            pole(g, p + UP * float(y) - V(0.06, 0, 0), p + UP * float(y) + V(0.06, 0, 0), 0.01, 0.01, rng,
                 col=scale(POSTC, 0.7), sides=4, segs=1, wobble=0.0)
    # Roof frame (square of poles resting on pegs) and a 4-sided thatch pyramid with a ragged eave.
    o = hw + 0.28
    E = [c + V(sx * o, roof_y, sz * o) for sx, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    apex = c + UP * (roof_y + 0.62)
    for i in range(4):
        a_, b_ = E[i], E[(i + 1) % 4]
        rows = []
        for k in range(6):
            f = k / 5
            row = []
            for j in range(5):
                u = j / 4
                p = a_.lerp(b_, f).lerp(apex, u)
                p = p + UP * (0.03 * math.sin(u * math.pi) + 0.02 * rng.uniform(-1, 1) * (1 - u))
                row.append(p)
            rows.append(row)
        sheet(g, rows, M_THATCH, lambda u, v: scale(THATCH_N, 0.95 - 0.15 * v), tile=0.5, double=True)
        pts = [a_.lerp(b_, k / 6) + UP * 0.03 + (a_.lerp(b_, k / 6) - V(c.x, roof_y, c.z)).normalized() * 0.02
               for k in range(7)]
        tube(g, pts, [0.06 + 0.02 * rng.uniform(0, 1) for _ in pts], 7, M_THATCH, scale(THATCH_N, 0.82), tile=0.4)
        pole(g, corners[i] + UP * (roof_y - 0.04), corners[(i + 1) % 4] + UP * (roof_y - 0.04), 0.035, 0.035, rng,
             col=scale(POSTC, 0.85), sides=5, segs=1)
    tube(g, [apex - UP * 0.1, apex + UP * 0.12], [0.08, 0.02], 6, M_THATCH, scale(THATCH_N, 0.7), tile=0.3)
    # The hay loaf under it.
    slab(g, c + UP * 0.62, (2 * hw + 0.1, 1.24, 2 * hw + 0.1), quat_y(0.1), rng, mat=M_THATCH, res=(4, 5, 4),
         round_r=0.25, rough=0.3, taper=-0.05, crown=0.35,
         col_fn=lambda p, n: scale((1.3, 1.12, 0.74), 0.9 + 0.12 * max(n.y, 0.0)), tile=0.45)
    mound(g, (c.x, 0.0, c.z), hw + 0.45, hw + 0.4, 0.07, rng, mat=M_THATCH, col_fn=lambda p, n: (1.1, 0.94, 0.64),
          rings=3, seg=14)


def threshing_floor(g, rng, c, r=0.85):
    """A round threshing floor of beaten clay ringed with set stones, straw and grain spread on it,
    a flail and a wooden shovel left lying, a winnowing basket."""
    c = Vector(c)
    mound(g, (c.x, -0.02, c.z), r, r * 0.95, 0.06, rng, mat=M_EARTH, col_fn=lambda p, n: (0.72, 0.6, 0.46), rings=4,
          seg=20, rough=0.04)
    for k in range(18):
        a = 2 * math.pi * k / 18 + rng.uniform(-0.05, 0.05)
        p = c + V(math.cos(a) * (r + 0.04), 0.0, math.sin(a) * (r + 0.04) * 0.95)
        stone(g, p, (rng.uniform(0.09, 0.13), rng.uniform(0.05, 0.08), rng.uniform(0.07, 0.1)), rng, mat=M_ROCK,
              detail=1, rough=0.12, rot=quat_y(-a), col_fn=rock_col((0.78, 0.76, 0.72), moss=0.25), tile=0.5)
    mound(g, (c.x + 0.15, 0.03, c.z - 0.05), r * 0.62, r * 0.5, 0.06, rng, mat=M_THATCH,
          col_fn=lambda p, n: (1.15, 0.98, 0.64), rings=3, seg=14, rough=0.3)
    # Flail: a handle and a short swingle joined by a leather link.
    h0 = c + V(-0.3, 0.06, 0.45)
    h1 = h0 + V(0.95, 0.04, -0.2)
    pole(g, h0, h1, 0.022, 0.02, rng, col=(0.76, 0.66, 0.5), sides=6, segs=1, wobble=0.0)
    pole(g, h1 + V(0.04, 0, 0.0), h1 + V(0.5, 0.0, 0.3), 0.03, 0.028, rng, col=(0.7, 0.6, 0.46), sides=6, segs=1,
         wobble=0.0)
    # Wooden shovel.
    s0 = c + V(0.2, 0.05, -0.55)
    pole(g, s0, s0 + V(-0.8, 0.02, 0.2), 0.018, 0.018, rng, col=(0.74, 0.64, 0.5), sides=6, segs=1, wobble=0.0)
    board(g, s0 + V(0.13, 0.0, -0.03), (1, 0, -0.25), (0, 1, 0), 0.28, 0.22, 0.025, mat=M_PLANK, col=(0.7, 0.6, 0.48),
          rng=rng)
    # Winnowing basket at the edge, half full of grain.
    bc = c + V(r + 0.28, 0.0, 0.85)
    lathe(g, tuple(bc), (0, 1, 0), [(0.0, 0.18), (0.06, 0.26), (0.14, 0.3), (0.16, 0.3)], 12, M_THATCH,
          (0.82, 0.68, 0.48), tile=0.3)
    mound(g, (bc.x, 0.08, bc.z), 0.24, 0.24, 0.05, rng, mat=M_FRUIT, col_fn=lambda p, n: (0.9, 0.72, 0.4), rings=2,
          seg=10, rough=0.05)


def town_farm(rng):
    """Farm: a small board-and-batten barn under a long hipped thatch (bound ridge pinned with
    spars, wide door ajar, hay spilt at the door), a beaten-clay threshing floor with a flail and a
    winnowing basket, a hay barrack, stooks along a hurdle."""
    b = Builder()
    g = G(b)
    W, D, ye = 2.6, 2.2, 1.6
    v0 = len(b.verts)
    ops = _ops([DOOR(1.3, w=1.2, h=1.32, ajar=1.1)], [WIN(1.1, y0=1.0, h=0.3, prop=False)], [], [])
    footing(g, rng, W, D, y_top=0.2, skip=[(0, 0.6, 2.0)])
    plank_walls(g, rng, W, D, 0.16, ye, ops)
    thatch_roof(g, rng, W, D, ye + 0.04, 2.9, over=0.42, hip=0.32, ridge="spars", moss=0.55, fresh=0.35, sag=0.06)
    mound(g, (0.25, 0.0, D / 2 + 0.25), 0.55, 0.35, 0.08, rng, mat=M_THATCH, col_fn=lambda p, n: (1.1, 0.92, 0.6),
          rings=3, seg=12)
    shift_tail(b, v0, BX)
    threshing_floor(g, rng, V(1.3, 0, 0.6), r=0.8)
    hay_barrack(g, rng, V(1.75, 0, -1.02), hw=0.45)
    for x, z in ((2.55, 0.05), (2.5, 0.62)):
        stook(g, rng, (x, 0.04, z), h=rng.uniform(0.55, 0.66))
    wattle_hurdle(g, rng, V(2.85, 0, -1.6), V(2.85, 0, 1.55), h=0.7)
    for k in range(2):
        sack(g, rng, V(0.32 + k * 0.32, 0.22, 1.42), lying=bool(k))
    return b


def town_woodcutter(rng):
    """Woodcutter: an open shed of four rough posts under a board pent roof weighted with stones
    over a sawpit (a log on the pit's bearers, a frame saw in the cut), the log stack, a sawhorse
    with a log on it, the chopping stump with the axe, chips everywhere."""
    b = Builder()
    g = G(b)
    x0, x1, z0, z1 = BX - 1.25, BX + 1.25, -1.1, 1.1
    for x in (x0, x1):
        for z, h in ((z0, 1.75), (z1, 1.5)):
            pole(g, V(x, -0.2, z), V(x + rng.uniform(-0.03, 0.03), h, z), 0.08, 0.07, rng, col=POSTC, sides=7, segs=2,
                 col_fn=weathered(POSTC, 0.6))
    for z, h in ((z0, 1.72), (z1, 1.47)):
        pole(g, V(x0 - 0.25, h, z), V(x1 + 0.25, h + 0.02, z), 0.07, 0.065, rng, col=scale(POSTC, 0.9), sides=6, segs=2)
    th = math.atan2(0.25, z1 - z0)
    zc = (z0 + z1) / 2
    for i in range(10):
        x = x0 - 0.3 + (i + 0.5) * (x1 - x0 + 0.6) / 10
        board(g, V(x, 1.6 + 0.08 + rng.uniform(-0.01, 0.01), zc), (0, -math.sin(th), math.cos(th)),
              (0, math.cos(th), math.sin(th)), z1 - z0 + 0.7, (x1 - x0 + 0.6) / 10 * 1.04, 0.04, mat=M_PLANK,
              col=scale((0.55, 0.5, 0.44), rng.uniform(0.75, 1.0)), rng=rng)
    for k in range(5):
        x = x0 + 0.2 + k * (x1 - x0 - 0.4) / 4
        zz = rng.uniform(-0.6, 0.6)
        stone(g, V(x, 1.6 - (zz - zc) * math.tan(th) + 0.16, zz), (0.13, 0.08, 0.11), rng, detail=1, rough=0.12,
              col_fn=rock_col((0.7, 0.68, 0.64), moss=0.4))
    # Sawpit: a dark slot with board-lined lips, two bearers and a log across them, frame saw.
    face(g, [V(BX - 0.75, 0.03, -0.3), V(BX + 0.75, 0.03, -0.3), V(BX + 0.75, 0.03, 0.3), V(BX - 0.75, 0.03, 0.3)],
         UP, M_EARTH, VOID)
    for z in (-0.36, 0.36):
        board(g, V(BX, 0.04, z), (1, 0, 0), (0, 1, 0), 1.7, 0.16, 0.05, mat=M_PLANK, col=(0.6, 0.52, 0.42), rng=rng)
    for x in (-0.55, 0.55):
        pole(g, V(BX + x, 0.1, -0.6), V(BX + x, 0.1, 0.6), 0.07, 0.07, rng, col=(0.6, 0.52, 0.42), sides=6, segs=1)
    pole(g, V(BX - 1.1, 0.33, 0.02), V(BX + 1.1, 0.33, -0.02), 0.16, 0.15, rng, mat=M_BARK, col=(0.72, 0.64, 0.54),
         sides=9, segs=2)
    lathe(g, (BX + 1.11, 0.33, -0.02), (1, 0, 0), [(0.0, 0.15), (0.001, 0.0)], 9, M_TIMBER, (0.95, 0.8, 0.58), tile=0.2)
    sx = BX + 0.3
    for y in (-0.15, 1.15):
        beam(g, [V(sx, y, -0.3), V(sx, y, 0.3)], 0.04, 0.04, mat=M_TIMBER, col=(0.62, 0.52, 0.4), rng=rng)
    for z in (-0.26, 0.26):
        beam(g, [V(sx, -0.18, z), V(sx, 1.18, z)], 0.04, 0.04, mat=M_TIMBER, col=(0.62, 0.52, 0.4), rng=rng)
    lbox(g, V(sx, 0.5, 0.0), (0.004, 1.3, 0.05), quat_y(0.0), M_IRON, (0.6, 0.6, 0.62), tile=0.2)
    mound(g, (BX + 0.2, 0.0, 0.75), 0.7, 0.3, 0.04, rng, mat=M_THATCH, col_fn=lambda p, n: (1.05, 0.88, 0.62), rings=3,
          seg=12)
    # Log stack in the yard along Z, held by stakes.
    for z in (-1.15, 1.15):
        for x in (0.5, 1.75):
            pole(g, V(x, -0.2, z), V(x, 0.95, z), 0.04, 0.035, rng, col=POSTC, sides=5, segs=1)
    for r in range(3):
        for k in range(5 - r):
            x = 0.62 + (k + r * 0.5) * 0.27
            y = 0.13 + r * 0.24
            pole(g, V(x, y, -1.12), V(x, y, 1.12), 0.13, 0.12, rng, mat=M_BARK,
                 col=scale((0.75, 0.66, 0.55), rng.uniform(0.85, 1.0)), sides=8, segs=1, wobble=0.0)
            for zz in (-1.13, 1.13):
                lathe(g, (x, y, zz), (0, 0, 1 if zz > 0 else -1), [(0.0, 0.12), (0.001, 0.0)], 8,
                      M_TIMBER, (0.95, 0.8, 0.58), tile=0.2)
    trestle(g, rng, V(2.3, 0, 0.4), 0.0)
    pole(g, V(2.3, 0.72, -0.5), V(2.3, 0.72, 1.2), 0.11, 0.1, rng, mat=M_BARK, col=(0.72, 0.64, 0.54), sides=8, segs=1)
    chopping_block(g, rng, (2.2, 0.0, -0.9))
    for _ in range(14):
        p = V(rng.uniform(1.6, 2.8), 0.015, rng.uniform(-1.4, -0.3))
        lbox(g, p, (rng.uniform(0.06, 0.14), 0.02, rng.uniform(0.03, 0.06)), quat_y(rng.uniform(0, 6.28)), M_TIMBER,
             (0.95, 0.82, 0.6), tile=0.2)
    return b


def town_mine(rng):
    """Stone mine: a shaft mouth in a ring of grey spoil, a log curb, A-frame headgear with a
    windlass drum + crank, the rope down to a bucket; cut blocks and rubble in the yard, a
    hand-barrow with a stone on it, a pick."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 1.3)

    def spoil(p, n):
        c = mix((0.5, 0.48, 0.44), (0.42, 0.46, 0.3), 0.3 * smoothstep(0.6, 1.0, n.y))
        return scale(c, 0.85 + 0.2 * nz(p * 3))

    for a in np.linspace(0.6, 5.7, 7):
        c = (BX + math.cos(a) * 1.05, 0.0, math.sin(a) * 0.95)
        mound(g, c, 0.75, 0.55, rng.uniform(0.12, 0.2), rng, mat=M_ROCK, col_fn=spoil, rings=4, seg=12, rough=0.35)
    for _ in range(40):
        a = rng.uniform(0, 6.28)
        r_ = rng.uniform(0.75, 1.6)
        s_ = rng.uniform(0.05, 0.15)
        stone(g, V(BX + math.cos(a) * r_, 0.08, math.sin(a) * r_ * 0.9), (s_, s_ * 0.8, s_), rng, detail=1,
              rough=0.15, col_fn=rock_col((0.72, 0.7, 0.66), moss=0.15))
    face(g, [V(BX - 0.5, 0.04, -0.45), V(BX + 0.5, 0.04, -0.45), V(BX + 0.5, 0.04, 0.45), V(BX - 0.5, 0.04, 0.45)], UP,
         M_EARTH, VOID)
    for z in (-0.52, 0.52):
        pole(g, V(BX - 0.75, 0.12, z), V(BX + 0.75, 0.12, z), 0.11, 0.1, rng, mat=M_TIMBER, col=LOGC, sides=8, segs=1)
    for x in (-0.6, 0.6):
        pole(g, V(BX + x, 0.3, -0.75), V(BX + x, 0.3, 0.75), 0.11, 0.1, rng, mat=M_TIMBER, col=LOGC, sides=8, segs=1)
    # A-frames at either end of the windlass (axle along Z over the shaft).
    yh = 1.55
    for z in (-0.72, 0.72):
        for sx in (-1, 1):
            pole(g, V(BX + sx * 0.7, -0.15, z), V(BX + sx * 0.06, yh + 0.12, z), 0.07, 0.06, rng, col=POSTC, sides=6,
                 segs=2)
        pole(g, V(BX - 0.45, 0.65, z), V(BX + 0.45, 0.65, z), 0.045, 0.04, rng, col=POSTC, sides=5, segs=1)
    tube(g, [V(BX, yh, -0.85), V(BX, yh, 0.85)], [0.05, 0.05], 8, M_TIMBER, (0.6, 0.52, 0.42), tile=0.4)
    tube(g, [V(BX, yh, -0.5), V(BX, yh, 0.5)], [0.15, 0.15], 10, M_TIMBER, (0.7, 0.6, 0.48), tile=0.5)
    for k in range(4):
        y_ = yh + 0.152 * math.sin(k * 1.4)
        x_ = BX + 0.152 * math.cos(k * 1.4)
        tube(g, [V(x_, y_, -0.45 + k * 0.03), V(x_, y_, 0.45)], [0.012, 0.012], 4, M_CLOTH, ROPE, tile=0.2)
    for z, s in ((-0.85, -1), (0.85, 1)):
        tube(g, [V(BX, yh, z), V(BX + 0.3, yh - 0.18, z), V(BX + 0.3, yh - 0.18, z + s * 0.22)], [0.025] * 3, 5,
             M_TIMBER, (0.55, 0.48, 0.38), tile=0.3)
    tube(g, [V(BX + 0.15, yh, 0.1), V(BX + 0.15, 0.62, 0.1)], [0.013, 0.013], 4, M_CLOTH, ROPE, tile=0.3)
    lathe(g, (BX + 0.15, 0.32, 0.1), (0, 1, 0), [(0.0, 0.14), (0.28, 0.17)], 9, M_TIMBER, (0.55, 0.46, 0.36), tile=0.4)
    tube(g, [V(BX - 0.02, 0.6, 0.1), V(BX + 0.15, 0.66, 0.1), V(BX + 0.32, 0.6, 0.1)], [0.01] * 3, 4,
         M_IRON, IRON_D, tile=0.2)
    # Yard: cut blocks, a rubble heap, the hand-barrow, a pick.
    for x, z, yy in ((0.9, -0.9, 0.0), (1.45, -0.9, 0.0), (1.15, -0.9, 0.38), (2.2, 0.9, 0.0), (2.2, 0.35, 0.0)):
        slab(g, V(x, yy + 0.19, z), (0.5, 0.38, 0.42), quat_y(rng.uniform(-0.15, 0.15)), rng, res=(2, 2, 2),
             round_r=0.03, rough=0.06, col_fn=rock_col((0.8, 0.78, 0.72), moss=0.05), tile=0.6)
    for _ in range(10):
        s_ = rng.uniform(0.1, 0.17)
        stone(g, V(2.2 + rng.uniform(-0.35, 0.35), 0.1, -0.85 + rng.uniform(-0.35, 0.35)), (s_, s_ * 0.8, s_),
              rng, detail=1, rough=0.15, col_fn=rock_col((0.76, 0.74, 0.7)))
    bq = quat_y(0.3)
    bc = V(1.3, 0.0, 0.55)
    for dz in (-0.22, 0.22):
        pole(g, bc + bq @ V(-0.8, 0.32, dz), bc + bq @ V(0.8, 0.32, dz), 0.03, 0.03, rng, col=(0.62, 0.54, 0.44), sides=5,
             segs=1)
        for dx in (-0.35, 0.35):
            pole(g, bc + bq @ V(dx, -0.02, dz), bc + bq @ V(dx, 0.32, dz), 0.025, 0.025, rng, col=(0.62, 0.54, 0.44),
                 sides=5, segs=1)
    for k in range(4):
        board(g, bc + bq @ V(-0.3 + k * 0.2, 0.35, 0), bq @ V(0, 0, 1), (0, 1, 0), 0.5, 0.18, 0.03, mat=M_PLANK,
              col=(0.6, 0.53, 0.44), rng=rng)
    stone(g, bc + V(0.0, 0.45, 0.0), (0.14, 0.1, 0.12), rng, detail=1, rough=0.12, col_fn=rock_col((0.75, 0.73, 0.68)))
    pk = V(0.75, 0.0, 0.05)
    pole(g, pk, pk + V(0.18, 0.82, 0.12), 0.022, 0.02, rng, col=(0.62, 0.54, 0.44), sides=5, segs=1)
    tube(g, [pk + V(0.1, 0.84, -0.12), pk + V(0.18, 0.84, 0.12), pk + V(0.24, 0.8, 0.34)], [0.02, 0.03, 0.012], 5,
         M_IRON, IRON_D, tile=0.2)
    return b


# ─────────────────────────────────────────────────────────────── the castle yard corners
# castle.rs WOOD_YARD / HAY_CORNER / CART_CORNER + the courtyard well (same local layouts and
# footprints as the procedural clusters they replace, so register_yard_blockers still fits).

def yard_wood(rng):
    """Chopping block with the axe in it at the origin, a log pyramid along X at z -0.9, chips."""
    b = Builder()
    g = G(b)
    chopping_block(g, rng, (0.0, 0.0, 0.0))
    for r, n in ((0, 3), (1, 2), (2, 1)):
        for k in range(n):
            z = -0.9 + (k - (n - 1) / 2) * 0.25
            y = 0.11 + r * 0.2
            pole(g, V(-0.75, y, z), V(0.75, y, z + rng.uniform(-0.03, 0.03)), 0.11, 0.1, rng, mat=M_BARK,
                 col=scale((0.75, 0.66, 0.55), rng.uniform(0.85, 1.0)), sides=8, segs=1, wobble=0.0)
            for sx in (-1, 1):
                lathe(g, (sx * 0.755, y, z), (sx, 0, 0), [(0.0, 0.1), (0.001, 0.0)], 8, M_TIMBER, (0.95, 0.8, 0.58),
                      tile=0.2)
    for _ in range(10):
        p = V(rng.uniform(-0.6, 0.7), 0.012, rng.uniform(-0.3, 0.6))
        lbox(g, p, (rng.uniform(0.06, 0.14), 0.02, rng.uniform(0.03, 0.06)), quat_y(rng.uniform(0, 6.28)), M_TIMBER,
             (0.95, 0.82, 0.6), tile=0.2)
    return b


def bale(g, rng, c, size, yaw_a):
    q = quat_y(yaw_a)
    slab(g, Vector(c), size, q, rng, mat=M_THATCH, res=(4, 3, 3), round_r=0.08, rough=0.35,
         col_fn=lambda p, n: scale((1.12, 0.96, 0.66), 0.9 + 0.1 * max(n.y, 0.0)), tile=0.5)
    for x in (-size[0] * 0.28, size[0] * 0.28):
        pts = []
        for k in range(9):
            a = 2 * math.pi * k / 8
            pts.append(Vector(c) + q @ V(x, math.sin(a) * (size[1] / 2 + 0.012), math.cos(a) * (size[2] / 2 + 0.012)))
        tube(g, pts, [0.012] * 9, 4, M_CLOTH, ROPE, tile=0.2, cap=False)


def yard_hay(rng):
    """Two roped straw bales stacked, loose straw, two grain sacks at the base (+X)."""
    b = Builder()
    g = G(b)
    bale(g, rng, (0.0, 0.27, 0.0), (0.9, 0.55, 0.55), 0.03)
    bale(g, rng, (0.03, 0.81, 0.05), (0.9, 0.53, 0.55), -0.06)
    mound(g, (0.1, 0.0, 0.1), 0.85, 0.65, 0.05, rng, mat=M_THATCH, col_fn=lambda p, n: (1.1, 0.94, 0.64), rings=3, seg=12)
    sack(g, rng, V(0.72, 0.25, 0.24))
    sack(g, rng, V(0.8, 0.2, -0.22), lying=True)
    return b


def yard_cart(rng):
    """A two-wheeled hand-cart (shafts to +X resting on the ground) with two barrels beside it."""
    b = Builder()
    g = G(b)
    tq = quat_z(-0.08)
    bed = V(0.0, 0.5, 0.0)
    for k in range(5):
        board(g, bed + tq @ V(-0.55 + k * 0.27, 0, 0), tq @ V(0, 0, 1), tq @ V(0, 1, 0), 0.72, 0.26, 0.04, mat=M_PLANK,
              col=scale((0.62, 0.55, 0.46), rng.uniform(0.85, 1.0)), rng=rng)
    for sz in (-0.36, 0.36):
        board(g, bed + tq @ V(0.0, 0.12, sz), tq @ V(1, 0, 0), (0, 0, 1), 1.35, 0.2, 0.04, mat=M_PLANK,
              col=(0.58, 0.5, 0.42), rng=rng)
        beam(g, [bed + tq @ V(-0.6, -0.05, sz * 0.8), bed + tq @ V(1.45, -0.05, sz * 0.8) + V(0, -0.33, 0)], 0.06, 0.06,
             mat=M_TIMBER, col=(0.6, 0.52, 0.42), rng=rng)
    tube(g, [V(-0.2, 0.32, -0.5), V(-0.2, 0.32, 0.5)], [0.035, 0.035], 6, M_IRON, (0.35, 0.34, 0.33), tile=0.3)
    for sz in (-0.45, 0.45):
        cart_wheel(g, rng, (-0.2, 0.32, sz), (0, 0, 1), r=0.32)
    barrel(g, rng, (0.95, 0.0, -0.6))
    barrel(g, rng, (1.2, 0.0, -0.3), s=0.9)
    return b


def yard_well(rng):
    """Fieldstone well curb, two forked posts carrying a windlass with a crank, a shingle hood,
    the bucket on the rim; trodden mud round it."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 3, 2.0)
    for ring, (r_, y_) in enumerate(((0.56, 0.1), (0.55, 0.28), (0.53, 0.44))):
        n = 11
        for k in range(n):
            a = 2 * math.pi * (k + 0.5 * ring) / n
            stone(g, V(math.cos(a) * r_, y_, math.sin(a) * r_), (0.17, 0.1, 0.13), rng, detail=1, rough=0.1,
                  rot=quat_y(-a), col_fn=rock_col((0.78, 0.76, 0.7), moss=0.35, noise=nz), tile=0.6)
    lathe(g, (0, 0.38, 0), (0, 1, 0), [(0.0, 0.42), (0.001, 0.0)], 14, M_EARTH, (0.04, 0.05, 0.05), tile=0.5)
    for sx in (-1, 1):
        pole(g, V(sx * 0.62, -0.2, 0.0), V(sx * 0.6, 1.25, 0.0), 0.06, 0.05, rng, col=POSTC, sides=6, segs=2)
    tube(g, [V(-0.75, 1.08, 0), V(0.75, 1.08, 0)], [0.07, 0.07], 8, M_TIMBER, (0.65, 0.56, 0.44), tile=0.4)
    tube(g, [V(0.75, 1.08, 0), V(0.85, 0.88, 0), V(0.85, 0.88, 0.18)], [0.02] * 3, 5, M_IRON, (0.35, 0.34, 0.33),
         tile=0.2)
    tube(g, [V(0.1, 1.06, 0.05), V(0.1, 0.62, 0.05)], [0.012, 0.012], 4, M_CLOTH, ROPE, tile=0.2)
    for sz in (-1, 1):
        th = 0.6
        q = quat_x(sz * th)
        board(g, V(0.0, 1.42 - 0.0, sz * 0.24), (1, 0, 0), q @ V(0, 1, 0), 1.6, 0.62, 0.04, mat=M_PLANK,
              col=(0.5, 0.45, 0.4), rng=rng)
    bucket(g, (0.0, 0.47, 0.42))
    mound(g, (0, -0.05, 0), 1.0, 1.0, 0.06, rng, mat=M_EARTH, col_fn=lambda p, n: (0.5, 0.42, 0.34), rings=3, seg=14)
    return b


# ─────────────────────────────────────────────────────────────── castle furniture (castle_decor.rs)

def decor_notice_board(rng):
    """Two rough posts, a plank board under a little board hood, notices pinned (one torn)."""
    b = Builder()
    g = G(b)
    for sx in (-0.58, 0.58):
        pole(g, V(sx, -0.25, 0), V(sx + rng.uniform(-0.02, 0.02), 1.42, 0), 0.055, 0.05, rng, col=POSTC, sides=6, segs=2,
             col_fn=weathered(POSTC, 0.6))
    for k in range(4):
        board(g, V(0, 0.78 + k * 0.155, 0.04), (1, 0, 0), (0, 0, 1), 1.3, 0.15, 0.035, mat=M_PLANK,
              col=scale((0.6, 0.53, 0.44), rng.uniform(0.85, 1.0)), rng=rng)
    for sz in (-1, 1):
        q = quat_x(sz * 0.75)
        board(g, V(0, 1.47, 0.04 + sz * 0.11), (1, 0, 0), q @ V(0, 1, 0), 1.5, 0.3, 0.03, mat=M_PLANK,
              col=(0.48, 0.44, 0.4), rng=rng)
    for x, y, w, h, a in ((-0.33, 1.05, 0.22, 0.28, 0.05), (0.03, 0.98, 0.24, 0.2, -0.04), (0.36, 1.08, 0.2, 0.26, 0.08),
                          (-0.05, 1.24, 0.16, 0.12, 0.0)):
        lbox(g, V(x, y, 0.065), (w, h, 0.004), quat_z(a), M_CLOTH, scale((1.05, 1.0, 0.86), rng.uniform(0.85, 1.0)),
             tile=0.3)
        lbox(g, V(x, y + h / 2 - 0.03, 0.07), (0.02, 0.02, 0.01), quat_y(0.0), M_IRON, (0.3, 0.3, 0.3), tile=0.2)
    lbox(g, V(0.36, 0.94, 0.07), (0.05, 0.05, 0.005), quat_z(0.3), M_CLOTH, CRIMSON, tile=0.2)
    return b


def decor_trough(rng):
    """A hollowed log trough on two stones, dark water in it, wet mud round the foot."""
    b = Builder()
    g = G(b)
    pole(g, V(-0.58, 0.3, 0), V(0.58, 0.3, 0), 0.24, 0.23, rng, mat=M_BARK, col=(0.62, 0.56, 0.48), sides=10, segs=2,
         wobble=0.0)
    lbox(g, V(0, 0.47, 0), (1.0, 0.03, 0.3), quat_y(0.0), M_EARTH, (0.05, 0.06, 0.06), tile=0.5)
    for sx in (-1, 1):
        lathe(g, (sx * 0.585, 0.3, 0), (sx, 0, 0), [(0.0, 0.23), (0.001, 0.0)], 10, M_TIMBER, (0.82, 0.7, 0.54), tile=0.3)
        stone(g, V(sx * 0.4, 0.04, 0), (0.18, 0.1, 0.2), rng, detail=1, rough=0.1, col_fn=rock_col((0.78, 0.76, 0.7), moss=0.4))
    mound(g, (0, -0.04, 0), 0.85, 0.5, 0.05, rng, mat=M_EARTH, col_fn=lambda p, n: (0.36, 0.3, 0.25), rings=3, seg=12)
    return b


def decor_bench(rng):
    """A split-log bench on four splayed stick legs."""
    b = Builder()
    g = G(b)
    slab(g, V(0, 0.42, 0), (1.2, 0.08, 0.3), quat_y(0.0), rng, mat=M_TIMBER, res=(4, 1, 2), round_r=0.03, rough=0.08,
         col_fn=lambda p, n: (0.7, 0.6, 0.48) if n.y > 0.5 else (0.6, 0.52, 0.42), tile=0.6)
    pole(g, V(-0.6, 0.3, 0.0), V(0.6, 0.3, 0.0), 0.1, 0.1, rng, mat=M_BARK, col=(0.66, 0.58, 0.48), sides=8, segs=1,
         wobble=0.0)
    for sx in (-0.45, 0.45):
        for sz in (-1, 1):
            pole(g, V(sx * 1.08, -0.05, sz * 0.17), V(sx, 0.36, sz * 0.05), 0.03, 0.028, rng, col=POSTC, sides=5, segs=1)
    return b


# ─────────────────────────────────────────────────────────────── the settlers' huts (Oct 2026)
# User feedback: the cottages above read too massive, too alike and all grey-brown. The twelve
# village homes are now SMALL settler huts, each its own: 3.0-4.0 x 2.6-3.1 walls, eaves at
# shoulder height, low roofs; limewash in white / ochre / rose, clay daub or warm / grey logs;
# golden or aged thatch, natural, moss-grey or muted-red shingles; painted doors and shutters.
# Shared layout contract with src/castle.rs `HUTS` + src/village_life.rs (keep in sync): pivot =
# footprint centre, front (+Z) faces the road, the door centred on the front wall, a porch bench
# (L 0.9) at x -1.0, z D/2 + 0.45, nothing else within 0.6 in front of the door.

M_SHINGLE = len(MATS)
MATS = MATS + ["s_shingle"]   # weathered split shingles (castle_kit's roof_slates_02 set)

LIME_W = (0.95, 0.92, 0.85)
LIME_OCHRE = (0.95, 0.78, 0.5)
LIME_ROSE = (0.93, 0.76, 0.68)
LOG_WARM = (1.0, 0.74, 0.5)
LOG_HONEY = (1.08, 0.86, 0.58)
SH_NAT = (0.8, 0.7, 0.6)
SH_RED = (0.8, 0.38, 0.28)
SH_MOSS = (0.66, 0.72, 0.56)
DOOR_RED = (0.56, 0.22, 0.17)
DOOR_GREEN = (0.3, 0.44, 0.38)
DOOR_BLUE = (0.3, 0.4, 0.54)
DOOR_OCHRE = (0.74, 0.55, 0.28)
DOOR_NAT = (0.6, 0.52, 0.42)


def shingle_roof(g, rng, W, D, ye, yr, col, over=0.36, verge=0.28, thick=0.07):
    """Gable roof of split shingles, ridge along X: two slopes, a course lip every ~0.22 (each
    course a shade off the next), verge boards and a board ridge cap."""
    th = math.atan2(yr - ye, D / 2)
    run = D / 2 + over
    Ls = (run + 0.1) / math.cos(th)
    Wx = W + 2 * verge
    for sz in (-1, 1):
        q = quat_x(sz * th)
        nrm = V(0, math.cos(th), sz * math.sin(th))
        zm = sz * (run - 0.1) / 2
        ym = yr - (sz * zm) * math.tan(th)
        lbox(g, V(0, ym, zm) + nrm * (thick / 2), (Wx, thick, Ls), q, M_SHINGLE,
             [col, None, scale(col, 0.78)], tile=1.6, grain=2, u0=sz * 0.37)
        k = int(Ls / 0.22)
        for i in range(1, k + 1):
            f = i / (k + 0.3)
            zz = -sz * 0.1 + (sz * run + sz * 0.1) * f
            p = V(0, yr - (sz * zz) * math.tan(th), zz) + nrm * (thick + 0.008)
            c = scale(col, rng.uniform(0.74, 0.92) * (1.0 - 0.12 * f))
            lbox(g, p, (Wx, 0.022, 0.045), q, M_SHINGLE, c, tile=1.6, grain=0)
        ez, ey = sz * run, ye - over * math.tan(th)
        for sx in (-1, 1):
            a_ = V(sx * (Wx / 2), yr + 0.1 * math.tan(th), -sz * 0.1) + nrm * 0.03
            e_ = V(sx * (Wx / 2), ey, ez) + nrm * 0.03
            beam(g, [a_, e_], 0.16, 0.04, up=(sx, 0, 0), mat=M_PLANK, col=scale(BOARD, 0.85), rng=rng, mode="plank")
    ry = yr + thick / math.cos(th) * 0.7
    for sz in (-1, 1):
        p = V(0, ry - 0.02, sz * 0.08)
        beam(g, [p - V(Wx / 2 + 0.04, 0, 0), p + V(Wx / 2 + 0.04, 0, 0)], 0.035, 0.2,
             up=(0, math.cos(th), sz * math.sin(th)), mat=M_PLANK, col=scale(col, 0.62), rng=rng)


def clay_chimney(g, rng, x, z, y_top, w=0.42):
    """A crude clay-daubed stack, sooty at the lip."""
    slab(g, V(x, y_top - 0.55, z), (w, 1.1, w * 0.9), quat_y(rng.uniform(-0.08, 0.08)), rng, mat=M_EARTH,
         res=(2, 4, 2), round_r=0.06, rough=0.3, taper=0.16,
         col_fn=lambda p, n: mix((0.66, 0.55, 0.44), (0.16, 0.14, 0.12), smoothstep(y_top - 0.2, y_top + 0.05, p.y)),
         tile=0.8)


def settler_hut(P):
    """One small settler hut from a spec dict (see HUT_SPECS)."""
    def build(rng):
        b = Builder()
        g = G(b)
        W, D, ye = P["W"], P["D"], P["ye"]
        PAINT.clear()
        PAINT.update(wall=P.get("wall"), log=P.get("log", LOGC), door=P["door"], shutter=P.get("shutter", P["door"]),
                     straw=P.get("straw", (1.0, 0.86, 0.58)))
        side = [WIN(D / 2 + P["side_win"], prop=False)] if P.get("side_win") is not None else []
        back = [WIN(W / 2 + P["back_win"], prop=False)] if P.get("back_win") is not None else []
        ops = _ops([DOOR(W / 2, ajar=P.get("ajar", 0.5)), WIN(W / 2 + P.get("win", 0.95))], side, back, [])
        footing(g, rng, W, D, skip=[(0, W / 2 - 0.55, W / 2 + 0.55)])
        if P["walls"] == "logs":
            log_walls(g, rng, W, D, 0.18, ye, ops, r=0.115)
        else:
            daub_walls(g, rng, W, D, 0.17, ye, ops, finish=P["walls"], patches=P.get("patches", 1))
        if P["roof"] == "thatch":
            ytop = ye + P.get("rise", 1.45)
            thatch_roof(g, rng, W, D, ye, ytop, over=0.4, thick=0.24, hip=P.get("hip", 0.5), sag=0.07,
                        moss=P.get("moss", 0.4), fresh=P.get("fresh", 0.4), smoke=P.get("smoke", 0),
                        ridge=P.get("ridge", "spars"), tone=P.get("tone", 1.0) * 1.22)
        else:
            ytop = ye + P.get("rise", 1.25)
            shingle_roof(g, rng, W, D, ye, ytop, P["roof_col"])
            gs = "boards" if P["walls"] in ("logs", "clay") else "plaster"
            tint = tuple(P["wall"][i] / PLW[i] for i in range(3)) if P.get("wall") else None
            R = quat_y(0.0)
            for sx in (-1, 1):
                gable(g, rng, (0, 0, 0), R, sx * W / 2, sx, D, ye, ytop, style=gs, tint=tint)
        if P.get("chimney"):
            cx, cz = P["chimney"]
            clay_chimney(g, rng, cx, cz, ytop + 0.35)
        bench(g, rng, V(-1.0, 0.0, D / 2 + 0.45), 0.0, L=0.9)
        for kind, x, z, a in P.get("props", ()):
            if kind == "wood":
                firewood(g, rng, (x, 0.0, z), a, L=1.1, rows=3)
            elif kind == "barrel":
                barrel(g, rng, (x, 0.0, z))
            elif kind == "bucket":
                bucket(g, (x, 0.0, z))
            elif kind == "block":
                chopping_block(g, rng, (x, 0.0, z))
            elif kind == "pots":
                for k in range(3):
                    lathe(g, (x + 0.22 * k, 0.0, z + 0.05 * (k % 2)), (0, 1, 0),
                          [(0.0, 0.07), (0.12, 0.11), (0.24, 0.08), (0.28, 0.09)], 9, M_EARTH,
                          scale((0.82, 0.52, 0.36), 0.9 + 0.08 * k), tile=0.3)
        PAINT.clear()
        return b
    return build


# Twelve homes, no two alike (index k = `town_hut_k`, assigned to the sites in castle.rs).
HUT_SPECS = [
    dict(W=3.4, D=2.8, ye=1.42, walls="lime", wall=LIME_W, roof="thatch", fresh=0.7, tone=1.12, door=DOOR_GREEN,
         side_win=0.0, chimney=(0.6, -0.3), props=[("wood", 1.95, 0.0, math.pi / 2)]),
    dict(W=3.8, D=3.0, ye=1.45, walls="logs", log=LOG_WARM, roof="shingle", roof_col=SH_RED, door=DOOR_OCHRE,
         back_win=-0.7, chimney=(-0.9, -0.35), props=[("barrel", 1.5, 1.9, 0), ("block", 2.4, 0.8, 0)]),
    dict(W=3.2, D=2.7, ye=1.38, walls="lime", wall=LIME_OCHRE, roof="thatch", fresh=0.3, tone=0.95, moss=0.6,
         door=DOOR_BLUE, smoke=-1, props=[("bucket", 1.15, 1.85, 0)]),
    dict(W=4.0, D=3.0, ye=1.45, walls="clay", roof="shingle", roof_col=SH_NAT, door=DOOR_RED, side_win=-0.3,
         chimney=(1.1, 0.35), props=[("wood", -2.35, -0.2, math.pi / 2), ("pots", 1.2, 1.85, 0)]),
    dict(W=3.5, D=2.9, ye=1.42, walls="lime", wall=LIME_ROSE, roof="shingle", roof_col=SH_MOSS, door=DOOR_GREEN,
         back_win=0.5, props=[("barrel", -2.1, 0.9, 0)]),
    dict(W=3.6, D=2.8, ye=1.4, walls="logs", log=LOG_HONEY, roof="thatch", fresh=0.6, tone=1.08,
         door=DOOR_RED, side_win=0.2, props=[("wood", 2.2, -0.1, math.pi / 2), ("block", 1.5, 1.95, 0)]),
    dict(W=3.0, D=2.6, ye=1.36, walls="clay", roof="thatch", fresh=0.2, tone=0.9, moss=0.7, smoke=1, door=DOOR_NAT,
         props=[("bucket", 1.0, 1.75, 0)]),
    dict(W=3.9, D=3.1, ye=1.48, walls="lime", wall=LIME_W, roof="shingle", roof_col=SH_RED, door=DOOR_BLUE,
         side_win=0.0, back_win=-0.4, chimney=(-1.0, -0.4), props=[("pots", 1.15, 1.95, 0)]),
    dict(W=3.4, D=2.8, ye=1.4, walls="logs", log=LOGC, roof="shingle", roof_col=SH_NAT, door=DOOR_GREEN,
         props=[("wood", -2.1, 0.0, math.pi / 2), ("barrel", 1.45, 1.85, 0)]),
    dict(W=3.7, D=3.0, ye=1.44, walls="lime", wall=LIME_OCHRE, roof="shingle", roof_col=SH_RED, door=DOOR_NAT,
         back_win=0.6, chimney=(0.9, -0.35), props=[("bucket", 1.25, 1.95, 0)]),
    dict(W=3.3, D=2.7, ye=1.38, walls="lime", wall=LIME_ROSE, roof="thatch", fresh=0.5, tone=1.04,
         door=DOOR_OCHRE, side_win=0.0, props=[("wood", 2.0, 0.0, math.pi / 2)]),
    dict(W=3.8, D=2.9, ye=1.44, walls="logs", log=LOG_WARM, roof="thatch", fresh=0.35, tone=0.96, smoke=-1,
         door=DOOR_BLUE, back_win=0.3, props=[("block", -2.3, 1.2, 0), ("wood", -2.25, -0.3, math.pi / 2)]),
]

SETTLER_HUTS = {f"town_hut_{k}": settler_hut(P) for k, P in enumerate(HUT_SPECS)}
