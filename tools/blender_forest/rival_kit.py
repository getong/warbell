"""The rival Pasha's desert stronghold (src/rival.rs) -> rival_kit.glb.

A different culture from our timber-and-thatch: Levantine mud brick under an earthen render over
sandstone rubble footings, battered (sloping) wall feet, stepped merlons, palm-trunk beam ends
(vigas) poking out under the roofs, small dark arched openings, reed awnings on poles, water jars,
crimson cloth. Render is the s_plaster set tinted ochre / sand; the footings and quoins are s_rock
tinted sand; vertex colour carries the rain streaks under the merlons, the dust at the foot and the
patches where the render has fallen off the brick.

Units = rival.rs local units (the fort is built at world scale; people ~1.17u). Pivot = the
ground under the footprint centre, front / gate toward +Z.

  node            footprint          top    notes
  rival_keep      6.6 x 6.6 (base)   ~13.2  three battered tiers (4.0 / 7.2 / 9.7) + stepped merlons,
                                            beam ends, arched door +Z, crimson banner on top.
                                            Collider stays the 3.1 half box.
  rival_walls     ring +-12 (centre  ~3.4   the whole curtain: wall runs T 0.7, H 1.5 (+ merlons),
                  lines), towers 2.8        four corner towers (H 3.1) with pennants, the S gate gap
                                            (|x| < 3.5) between two pylons under a timber lintel at
                                            2.3, the leaves swung open inside. Same layout as
                                            rival.rs wall_parts / register_wall_blockers.
  rival_house_a   2.6 x 2.4          ~2.3   flat-roofed mud-brick dwelling, parapet, beam ends, reed
                                            awning on poles over the door, jars.
  rival_house_b   2.6 x 2.4          ~2.6   same block + a little roof dome, a ladder to the roof,
                                            a clay bread oven (tannur) and a water jar by the door.

    blender -b --factory-startup --python tools/blender_forest/rival_kit.py
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.append(str(HERE))
_src = (HERE / "wayside_models.py").read_text(encoding="utf-8")
exec(compile(_src[:_src.index("\nMODELS = {")], str(HERE / "wayside_models.py"), "exec"))

M_PLASTER = len(MATS)
MATS = MATS + ["s_plaster"]
UP = V(0, 1, 0)
VOID = (0.03, 0.027, 0.025)
MUD = (0.95, 0.74, 0.5)           # ochre earthen render (on the off-white plaster scan)
MUD_PALE = (1.0, 0.86, 0.66)
SANDST = (0.98, 0.82, 0.6)        # sandstone footing (on the grey rock scan)
BRICK = (0.72, 0.5, 0.34)         # exposed mud brick where the render fell off
BEAMC = (0.62, 0.5, 0.38)
CRIMSON = (0.6, 0.06, 0.07)
TERRA = (0.85, 0.5, 0.32)


def lathe(g, base, axis, profile, sides, mat, col, tile=0.5):
    a = Vector(axis).normalized()
    pts = [Vector(base) + a * h for h, _ in profile]
    tube(g, pts, [max(r, 0.003) for _, r in profile], sides, mat, col, tile=tile)


def render_col(rng, y0, y1, base=MUD, patches=()):
    nz = Noise(rng, 4, 1.2)
    nzs = Noise(rng, 3, 6.0)

    def f(p, n):
        c = scale(base, 0.9 + 0.12 * nz(p * 0.8))
        # Rain streaks: vertical darker runs below the top, stronger high up.
        streak = max(0.0, nzs(V(p.x * 3.0, 0.0, p.z * 3.0)))
        c = scale(c, 1.0 - 0.18 * streak * smoothstep(y0, y1, p.y))
        # Dust / splash at the foot.
        c = mix(scale((0.78, 0.64, 0.48), 0.85), c, smoothstep(y0, y0 + 0.6, p.y))
        for pc, rx, ry in patches:
            d = p - pc
            e = (d.x * d.x + d.z * d.z) / (rx * rx) + (d.y * d.y) / (ry * ry)
            if e < 1.0:
                c = mix(c, BRICK, smoothstep(1.0, 0.6, e))
        return c
    return f


def merlon(g, rng, c, yaw_a, col_fn, s=1.0):
    """A stepped (two-tier) merlon on a wall top at c."""
    q = quat_y(yaw_a)
    slab(g, V(c.x, c.y + 0.17 * s, c.z), (0.5 * s, 0.34 * s, 0.42 * s), q, rng, mat=M_PLASTER, res=(2, 2, 2),
         round_r=0.05, rough=0.12, col_fn=col_fn, tile=1.0)
    slab(g, V(c.x, c.y + 0.44 * s, c.z), (0.28 * s, 0.22 * s, 0.34 * s), q, rng, mat=M_PLASTER, res=(2, 2, 2),
         round_r=0.05, rough=0.12, col_fn=col_fn, tile=1.0)


def footing_run(g, rng, a, b, T, h=0.42):
    """Sandstone rubble footing under a wall from a to b (ground points)."""
    a, b = Vector(a), Vector(b)
    t = (b - a).normalized()
    L = (b - a).length
    n = max(1, int(L / 2.2))
    for k in range(n):
        c = a.lerp(b, (k + 0.5) / n)
        slab(g, V(c.x, h / 2 - 0.12, c.z), (L / n + 0.05, h + 0.24, T + 0.18), yaw_q(t), rng, mat=M_ROCK,
             res=(max(2, int(L / n / 0.5)), 2, 2), round_r=0.06, rough=0.2,
             col_fn=rock_col(SANDST, ground=0.0, dark_below=0.6), tile=0.9)


def yaw_q(t):
    return quat_y(math.atan2(-t.z, t.x))


def wall_run(g, rng, a, b, T=0.7, H=1.5, merlons=True, mer_side=0.0):
    """A rendered mud-brick curtain run from a to b (ground points), battered foot, rounded top,
    stepped merlons along it."""
    a, b = Vector(a), Vector(b)
    t = (b - a).normalized()
    L = (b - a).length
    nrm = t.cross(UP)
    patches = []
    for _ in range(int(L / 3)):
        s = rng.uniform(0.6, L - 0.6)
        side = rng.choice([-1, 1])
        patches.append((a + t * s + nrm * side * (T / 2) + UP * rng.uniform(0.5, 1.2), rng.uniform(0.25, 0.5),
                        rng.uniform(0.15, 0.3)))
    col = render_col(rng, 0.0, H + 0.5, patches=patches)
    footing_run(g, rng, a, b, T)
    n = max(1, int(L / 3.0))
    for k in range(n):
        c = a.lerp(b, (k + 0.5) / n)
        Lk = L / n + 0.06
        slab(g, V(c.x, H / 2 + 0.1, c.z), (Lk, H - 0.2 + 0.02, T), yaw_q(t), rng, mat=M_PLASTER,
             res=(max(2, int(Lk / 0.45)), 4, 2), round_r=0.08, rough=0.12, taper=0.12, col_fn=col, tile=1.4)
    # Wall-walk cap, slightly overhanging.
    for k in range(n):
        c = a.lerp(b, (k + 0.5) / n)
        slab(g, V(c.x, H + 0.04, c.z), (L / n + 0.06, 0.16, T * 0.92), yaw_q(t), rng, mat=M_PLASTER,
             res=(max(2, int(L / n / 0.6)), 1, 2), round_r=0.05, rough=0.12, col_fn=col, tile=1.4)
    if merlons:
        m = int(L / 0.9)
        for i in range(m):
            s = (i + 0.5) * L / m
            merlon(g, rng, a + t * s + nrm * mer_side + UP * (H + 0.1), math.atan2(-t.z, t.x), col)
    # Drain spouts (palm-trunk gutters) through the wall top every few metres.
    for s in np.arange(2.0, L - 1.0, 4.5):
        for sd in (-1,):
            p = a + t * float(s) + UP * (H - 0.05)
            pole(g, p, p + nrm * sd * (T / 2 + 0.3) - UP * 0.04, 0.05, 0.045, rng, mat=M_BARK, col=BEAMC, sides=6, segs=1)


def tower(g, rng, c, w=2.8, H=3.1, banner=True):
    c = Vector(c)
    col = render_col(rng, 0.0, H + 0.5, patches=[(c + V(w / 2, 1.2, 0.3), 0.4, 0.3)])
    slab(g, V(c.x, 0.1, c.z), (w + 0.25, 0.5, w + 0.25), quat_y(0.0), rng, mat=M_ROCK, res=(4, 2, 4), round_r=0.08,
         rough=0.2, col_fn=rock_col(SANDST, dark_below=0.6), tile=0.9)
    slab(g, V(c.x, H / 2 + 0.15, c.z), (w, H - 0.3, w), quat_y(0.0), rng, mat=M_PLASTER, res=(5, 6, 5), round_r=0.1,
         rough=0.1, taper=0.1, col_fn=col, tile=1.4)
    slab(g, V(c.x, H + 0.05, c.z), (w * 0.94, 0.2, w * 0.94), quat_y(0.0), rng, mat=M_PLASTER, res=(4, 1, 4),
         round_r=0.06, rough=0.1, col_fn=col, tile=1.4)
    hw = w * 0.94 / 2 - 0.2
    for i in range(4):
        f = -hw + i * 2 * hw / 3
        for x, z, a in ((f, -hw, 0.0), (f, hw, 0.0), (-hw, f, math.pi / 2), (hw, f, math.pi / 2)):
            merlon(g, rng, c + V(x, H + 0.15, z), a, col, s=0.9)
    # Beam ends under the top + a dark arrow loop on the outer faces.
    for sx, sz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nrm = V(sx, 0, sz)
        tng = V(-sz, 0, sx)
        for k in (-1, 0, 1):
            p = c + nrm * (w / 2 * 0.92) + tng * (k * 0.8) + UP * (H - 0.35)
            pole(g, p - nrm * 0.2, p + nrm * 0.2, 0.07, 0.065, rng, mat=M_BARK, col=BEAMC, sides=6, segs=1)
        p = c + nrm * (w / 2 * 0.955 + 0.005) + UP * 1.8
        pts = [p + tng * 0.08 - UP * 0.35, p + tng * 0.08 + UP * 0.2, p + UP * 0.32, p - tng * 0.08 + UP * 0.2,
               p - tng * 0.08 - UP * 0.35]
        face_w(g, pts, nrm, M_PLASTER, VOID)
    if banner:
        pennant(g, rng, c + UP * (H + 0.15), 1.7, 0.7)


def face_w(g, pts, want, mat, col):
    pts = [Vector(p) for p in pts]
    from mathutils.geometry import tessellate_polygon
    for tri in tessellate_polygon([pts]):
        q = [pts[i] for i in tri]
        n = (q[1] - q[0]).cross(q[2] - q[0])
        if n.length < 1e-12:
            continue
        if n.dot(Vector(want)) < 0:
            q = q[::-1]
        g.flat(q, mat, col, 1.0)


def pennant(g, rng, base, h, lw):
    pole(g, base, base + UP * h, 0.05, 0.04, rng, mat=M_BARK, col=BEAMC, sides=6, segs=2)
    top = base + UP * (h - 0.08)
    grid = []
    for i in range(5):
        f = i / 4
        x = f * lw
        sag = 0.06 * math.sin(f * 3.0)
        drop = 0.45 * (1 - 0.6 * f)
        grid.append([(top + V(x, -sag, 0.05 * math.sin(f * 5))).to_tuple(),
                     (top + V(x, -sag - drop, 0.05 * math.sin(f * 5 + 1))).to_tuple()])
    sheet(g, grid, M_CLOTH, lambda u, v: CRIMSON, tile=0.5, double=True)
    lathe(g, tuple(base + UP * h), (0, 1, 0), [(0.0, 0.06), (0.1, 0.05), (0.18, 0.0)], 8, M_IRON, (0.7, 0.55, 0.3),
          tile=0.2)


def arched_opening(g, c, nrm, w, h, spring=None, mat=M_PLASTER):
    """A dark round-headed opening on a face (centre-bottom c, outward nrm)."""
    tng = UP.cross(nrm).normalized()
    spring = spring if spring is not None else h - w / 2
    pts = [c - tng * (w / 2), c + tng * (w / 2), c + tng * (w / 2) + UP * spring]
    for k in range(1, 8):
        a = math.pi * k / 8
        pts.append(c + UP * spring + tng * (w / 2 * math.cos(a)) + UP * (w / 2 * math.sin(a)))
    pts.append(c - tng * (w / 2) + UP * spring)
    face_w(g, pts, nrm, mat, VOID)


def rival_keep(rng):
    b = Builder()
    g = G(b)
    col = render_col(rng, 0.0, 10.5, patches=[(V(3.0, 2.5, 1.0), 0.6, 0.4), (V(-1.0, 6.0, 2.3), 0.5, 0.35),
                                              (V(-2.3, 5.2, -0.8), 0.4, 0.3)])
    # Tier 1: battered sandstone base (ashlar-ish), render above 1.4.
    slab(g, V(0, 0.7, 0), (6.7, 1.6, 6.7), quat_y(0.0), rng, mat=M_ROCK, res=(8, 3, 8), round_r=0.12, rough=0.12,
         taper=0.06, col_fn=rock_col(SANDST, dark_below=0.7), tile=1.0)
    slab(g, V(0, 2.65, 0), (6.1, 2.7, 6.1), quat_y(0.0), rng, mat=M_PLASTER, res=(8, 4, 8), round_r=0.12, rough=0.08,
         taper=0.05, col_fn=col, tile=1.6)
    slab(g, V(0, 4.05, 0), (6.3, 0.22, 6.3), quat_y(0.0), rng, mat=M_PLASTER, res=(6, 1, 6), round_r=0.06, rough=0.1,
         col_fn=col, tile=1.6)
    slab(g, V(0, 5.65, 0), (4.6, 3.1, 4.6), quat_y(0.0), rng, mat=M_PLASTER, res=(6, 5, 6), round_r=0.12, rough=0.08,
         taper=0.06, col_fn=col, tile=1.6)
    slab(g, V(0, 7.25, 0), (4.85, 0.22, 4.85), quat_y(0.0), rng, mat=M_PLASTER, res=(5, 1, 5), round_r=0.06, rough=0.1,
         col_fn=col, tile=1.6)
    slab(g, V(0, 8.5, 0), (3.4, 2.3, 3.4), quat_y(0.0), rng, mat=M_PLASTER, res=(5, 4, 5), round_r=0.1, rough=0.08,
         taper=0.05, col_fn=col, tile=1.6)
    slab(g, V(0, 9.72, 0), (3.6, 0.2, 3.6), quat_y(0.0), rng, mat=M_PLASTER, res=(4, 1, 4), round_r=0.05, rough=0.1,
         col_fn=col, tile=1.6)
    # Stepped merlons on each tier's terrace edge.
    for hw, y, s in ((3.0, 4.15, 1.0), (2.28, 7.35, 0.95), (1.62, 9.82, 0.9)):
        m = max(3, int(2 * hw / 0.9))
        for i in range(m + 1):
            f = -hw + i * 2 * hw / m
            for x, z, a in ((f, -hw, 0.0), (f, hw, 0.0), (-hw, f, math.pi / 2), (hw, f, math.pi / 2)):
                if abs(x) == hw and abs(z) == hw and a:
                    continue
                merlon(g, rng, V(x, y, z), a, col, s=s)
    # Beam ends (vigas) under each terrace, the arched door, windows and loops.
    for hw, y in ((3.05, 3.75), (2.3, 6.95), (1.7, 9.45)):
        for sx, sz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nrm, tng = V(sx, 0, sz), V(-sz, 0, sx)
            for k in np.linspace(-hw + 0.5, hw - 0.5, max(3, int(hw * 2 / 0.9))):
                p = nrm * (hw - 0.05) + tng * float(k) + UP * y
                pole(g, p - nrm * 0.2, p + nrm * 0.28, 0.08, 0.07, rng, mat=M_BARK, col=BEAMC, sides=6, segs=1)
    arched_opening(g, V(0, 0.0, 3.36), V(0, 0, 1), 1.3, 2.3)
    for sx in (-1, 1):
        lbox(g, V(sx * 0.62, 1.05, 3.25), (0.08, 2.1, 0.26), quat_y(0.0), M_TIMBER, BEAMC, tile=0.6)
    board(g, V(0, 2.12, 3.42), (1, 0, 0), (0, 0, 1), 1.5, 0.18, 0.12, mat=M_PLANK, col=BEAMC, rng=rng)
    # Steps up to the door.
    for k in range(2):
        slab(g, V(0, 0.08 + k * 0.16 - 0.08, 3.65 + 0.32 - k * 0.3), (2.0 - k * 0.3, 0.2, 0.42), quat_y(0.0), rng,
             mat=M_ROCK, res=(3, 1, 2), round_r=0.04, rough=0.1, col_fn=rock_col(SANDST), tile=0.8)
    for sx, sz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nrm, tng = V(sx, 0, sz), V(-sz, 0, sx)
        for k in (-1, 1):
            arched_opening(g, nrm * (2.312 - 0.01) + tng * (k * 0.9) + UP * 5.1, nrm, 0.42, 0.85)
        arched_opening(g, nrm * 1.725 + UP * 8.1, nrm, 0.36, 0.7)
        if sz != 1:
            arched_opening(g, nrm * 3.06 + UP * 2.4, nrm, 0.22, 0.75)
    # A wooden balcony (mashrabiya-like box) on the second tier front.
    bc = V(0, 5.0, 2.55)
    lbox(g, bc, (1.3, 0.1, 0.55), quat_y(0.0), M_PLANK, BEAMC, tile=0.6)
    for x in np.linspace(-0.6, 0.6, 7):
        lbox(g, bc + V(float(x), 0.45, 0.25), (0.05, 0.8, 0.05), quat_y(0.0), M_TIMBER, scale(BEAMC, 0.8), tile=0.4)
    lbox(g, bc + V(0, 0.88, 0.0), (1.35, 0.1, 0.6), quat_y(0.0), M_PLANK, scale(BEAMC, 0.9), tile=0.6)
    for x in (-0.55, 0.55):
        pole(g, bc + V(x, -0.05, 0.2), bc + V(x * 0.6, -0.55, -0.25), 0.04, 0.04, rng, mat=M_BARK, col=BEAMC, sides=5,
             segs=1)
    # The crowning banner.
    pole(g, V(0, 9.8, 0), V(0, 13.0, 0), 0.08, 0.06, rng, mat=M_BARK, col=BEAMC, sides=7, segs=2)
    grid = []
    for i in range(6):
        f = i / 5
        x = 0.1 + f * 1.4
        grid.append([(V(x, 12.85 - 0.1 * math.sin(f * 2.5), 0.08 * math.sin(f * 6))).to_tuple(),
                     (V(x, 12.85 - 1.75 + 0.25 * f - 0.1 * math.sin(f * 2.5), 0.1 * math.sin(f * 6 + 1))).to_tuple()])
    sheet(g, grid, M_CLOTH, lambda u, v: scale(CRIMSON, 1.0 - 0.25 * v), tile=0.6, double=True)
    lathe(g, (0, 13.0, 0), (0, 1, 0), [(0.0, 0.1), (0.16, 0.08), (0.3, 0.0)], 8, M_IRON, (0.75, 0.58, 0.3), tile=0.2)
    return b


WALL_HALF, WALL_T, WALL_H, GATE_HALF = 12.0, 0.7, 1.5, 3.5


def rival_walls(rng):
    b = Builder()
    g = G(b)
    h = WALL_HALF
    ti = 1.45   # stop the runs at the tower faces
    wall_run(g, rng, V(-h + ti, 0, -h), V(h - ti, 0, -h))
    wall_run(g, rng, V(h, 0, -h + ti), V(h, 0, h - ti))
    wall_run(g, rng, V(-h, 0, h - ti), V(-h, 0, -h + ti))
    wall_run(g, rng, V(-h + ti, 0, h), V(-GATE_HALF - 0.75, 0, h))
    wall_run(g, rng, V(GATE_HALF + 0.75, 0, h), V(h - ti, 0, h))
    for sx in (-1, 1):
        for sz in (-1, 1):
            tower(g, rng, V(sx * h, 0, sz * h))
    # Gate: two pylons flanking the gap, a palm-trunk lintel + render over it, open leaves inside.
    col = render_col(rng, 0.0, 3.5)
    for sx in (-1, 1):
        x = sx * (GATE_HALF + 0.7)
        slab(g, V(x, 0.05, h), (1.6, 0.5, 1.4), quat_y(0.0), rng, mat=M_ROCK, res=(3, 2, 3), round_r=0.06, rough=0.2,
             col_fn=rock_col(SANDST, dark_below=0.6), tile=0.9)
        slab(g, V(x, 1.65, h), (1.4, 3.1, 1.2), quat_y(0.0), rng, mat=M_PLASTER, res=(3, 6, 3), round_r=0.08, rough=0.1,
             taper=0.08, col_fn=col, tile=1.4)
        for dz in (-0.35, 0.35):
            merlon(g, rng, V(x - 0.3, 3.2, h + dz), 0.0, col, s=0.85)
            merlon(g, rng, V(x + 0.3, 3.2, h + dz), 0.0, col, s=0.85)
        # Leaf swung open inside, against the wall (hinged at the jamb).
        hx = sx * GATE_HALF
        for k in range(4):
            board(g, V(hx - sx * 0.12, 1.1, h - 0.5 - 0.17 - k * 0.3), (0, 1, 0), (sx, 0, 0), 2.2, 0.29, 0.07,
                  mat=M_PLANK, col=scale(BEAMC, rng.uniform(0.8, 1.0)), rng=rng)
        for y in (0.35, 1.85):
            lbox(g, V(hx - sx * 0.17, y, h - 1.1), (0.02, 0.07, 1.2), quat_y(0.0), M_IRON, (0.3, 0.3, 0.31), tile=0.3)
    for k in range(3):
        pole(g, V(-GATE_HALF - 0.6, 2.42, h - 0.35 + k * 0.35), V(GATE_HALF + 0.6, 2.42, h - 0.35 + k * 0.35), 0.13,
             0.12, rng, mat=M_BARK, col=BEAMC, sides=8, segs=2)
    slab(g, V(0, 2.95, h), (2 * GATE_HALF + 0.4, 0.8, 1.15), quat_y(0.0), rng, mat=M_PLASTER, res=(8, 2, 2),
         round_r=0.08, rough=0.1, col_fn=col, tile=1.4)
    for i in range(8):
        merlon(g, rng, V(-GATE_HALF + 0.2 + i * (2 * GATE_HALF - 0.4) / 7, 3.35, h + 0.2), 0.0, col, s=0.85)
    for sx in (-1, 1):
        pennant(g, rng, V(sx * (GATE_HALF + 0.7), 3.3, h), 1.9, 0.8)
    return b


def jar(g, rng, c, s=1.0):
    prof = [(0.0, 0.08), (0.08, 0.17), (0.25, 0.22), (0.42, 0.16), (0.52, 0.08), (0.58, 0.09)]
    lathe(g, c, (0, 1, 0), [(h * s, r * s) for h, r in prof], 10, M_EARTH, scale(TERRA, rng.uniform(0.85, 1.05)), tile=0.4)


def desert_house(rng, variant):
    b = Builder()
    g = G(b)
    W, D, H = 2.6, 2.4, 1.95
    col = render_col(rng, 0.0, H + 0.4, base=MUD_PALE if variant else MUD,
                     patches=[(V(-W / 2, 1.0, 0.4), 0.35, 0.25), (V(0.8, 0.5, D / 2), 0.3, 0.2)])
    slab(g, V(0, 0.08, 0), (W + 0.12, 0.36, D + 0.12), quat_y(0.0), rng, mat=M_ROCK, res=(4, 1, 4), round_r=0.06,
         rough=0.2, col_fn=rock_col(SANDST, dark_below=0.6), tile=0.9)
    slab(g, V(0, H / 2 + 0.05, 0), (W, H - 0.1, D), quat_y(0.0), rng, mat=M_PLASTER, res=(5, 4, 5), round_r=0.09,
         rough=0.12, taper=0.05, col_fn=col, tile=1.3)
    # Parapet rim round the flat roof.
    for x, z, sx, sz in ((0, D / 2 - 0.06, W, 0.14), (0, -D / 2 + 0.06, W, 0.14), (W / 2 - 0.06, 0, 0.14, D),
                         (-W / 2 + 0.06, 0, 0.14, D)):
        slab(g, V(x, H + 0.12, z), (sx, 0.3, sz), quat_y(0.0), rng, mat=M_PLASTER, res=(4, 1, 1), round_r=0.05,
             rough=0.15, col_fn=col, tile=1.3)
    slab(g, V(0, H - 0.02, 0), (W - 0.2, 0.06, D - 0.2), quat_y(0.0), rng, mat=M_EARTH, res=(3, 1, 3), round_r=0.02,
         rough=0.1, col_fn=lambda p, n: (0.66, 0.54, 0.4), tile=0.8)
    # Beam ends along the front and back, a spout.
    for z in (D / 2, -D / 2):
        for x in np.linspace(-W / 2 + 0.3, W / 2 - 0.3, 5):
            p = V(float(x), H - 0.22, z)
            pole(g, p - V(0, 0, 0.15) * (1 if z > 0 else -1), p + V(0, 0, 0.18) * (1 if z > 0 else -1), 0.055, 0.05, rng,
                 mat=M_BARK, col=BEAMC, sides=6, segs=1)
    pole(g, V(W / 2 - 0.05, H + 0.02, -0.5), V(W / 2 + 0.35, H - 0.03, -0.5), 0.05, 0.045, rng, mat=M_BARK, col=BEAMC,
         sides=6, segs=1)
    # Door: dark arched opening with a plank leaf ajar; a small high window.
    dx = -0.45 if variant else 0.35
    arched_opening(g, V(dx, 0.08, D / 2 + 0.01), V(0, 0, 1), 0.7, 1.3)
    hinge = V(dx - 0.33, 0.1, D / 2 - 0.06)
    dd = V(math.cos(1.2), 0, -math.sin(1.2))
    for k in range(3):
        board(g, hinge + dd * (0.11 + k * 0.22) + UP * 0.55, (0, 1, 0), dd.cross(UP), 1.1, 0.21, 0.04, mat=M_PLANK,
              col=scale(BEAMC, rng.uniform(0.8, 1.0)), rng=rng)
    board(g, V(dx, 1.28, D / 2 + 0.06), (1, 0, 0), (0, 0, 1), 0.95, 0.12, 0.1, mat=M_PLANK, col=BEAMC, rng=rng)
    arched_opening(g, V(-dx * 1.6, 1.15, D / 2 + 0.01), V(0, 0, 1), 0.3, 0.42)
    arched_opening(g, V(W / 2 + 0.01, 1.2, 0.3), V(1, 0, 0), 0.28, 0.4)
    if not variant:
        # Reed awning on four poles over the door.
        for x in (dx - 0.7, dx + 0.7):
            pole(g, V(x, -0.1, D / 2 + 1.0), V(x, 1.62, D / 2 + 1.0), 0.04, 0.035, rng, mat=M_BARK, col=BEAMC, sides=5)
        pole(g, V(dx - 0.85, 1.6, D / 2 + 1.0), V(dx + 0.85, 1.6, D / 2 + 1.0), 0.04, 0.04, rng, mat=M_BARK, col=BEAMC,
             sides=5, segs=1)
        th = math.atan2(0.15, 1.0)
        lbox(g, V(dx, 1.72, D / 2 + 0.5), (1.75, 0.05, 1.15), quat_x(th), M_THATCH, (1.0, 0.85, 0.62), tile=0.6, grain=2)
        for k, x in enumerate((dx + 0.9, dx + 1.15, -1.0)):
            jar(g, rng, (x, 0.0, D / 2 + 0.3 + (0.25 if k == 2 else 0.0)), s=1.0 + 0.15 * (k == 1))
        lbox(g, V(-0.6, 0.2, D / 2 + 0.45), (0.9, 0.06, 0.35), quat_y(0.05), M_PLANK, BEAMC, tile=0.5)
    else:
        # A little dome over the roof's back corner, a ladder, the bread oven and a jar.
        lathe(g, (0.55, H - 0.05, -0.45), (0, 1, 0),
              [(0.0, 0.62), (0.18, 0.6), (0.35, 0.52), (0.5, 0.38), (0.6, 0.2), (0.64, 0.0)], 14, M_PLASTER,
              scale(MUD_PALE, 0.95), tile=1.0)
        ladder(g, rng, V(W / 2 + 0.55, -0.05, 0.6), V(W / 2 + 0.05, H + 0.6, 0.6))
        lathe(g, (W / 2 + 0.7, 0.0, -0.6), (0, 1, 0), [(0.0, 0.42), (0.35, 0.38), (0.62, 0.22), (0.72, 0.12)], 12,
              M_EARTH, (0.66, 0.5, 0.38), tile=0.5)
        face_w(g, [V(W / 2 + 0.7 - 0.15, 0.08, -0.6 + 0.39), V(W / 2 + 0.7 + 0.15, 0.08, -0.6 + 0.39),
                   V(W / 2 + 0.7, 0.33, -0.6 + 0.35)], V(0, 0, 1), M_EARTH, VOID)
        jar(g, rng, (dx + 0.75, 0.0, D / 2 + 0.3), s=1.2)
    return b


def ladder(g, rng, foot, top, width=0.4):
    d = top - foot
    side = d.cross(UP).normalized()
    for s in (-1, 1):
        pole(g, foot + side * s * width / 2, top + side * s * width / 2, 0.03, 0.026, rng, mat=M_BARK, col=BEAMC, sides=5,
             segs=2)
    n = max(2, int(d.length / 0.34))
    for k in range(1, n + 1):
        p = foot.lerp(top, k / (n + 0.6))
        pole(g, p - side * (width / 2 + 0.03), p + side * (width / 2 + 0.03), 0.018, 0.018, rng, mat=M_BARK, col=BEAMC,
             sides=5, wobble=0.0, segs=1)


def rival_house_a(rng):
    return desert_house(rng, 0)


def rival_house_b(rng):
    return desert_house(rng, 1)


def bounds(builder):
    v = np.array(builder.verts) if builder.verts else np.zeros((1, 3))
    gx, gy, gz = v[:, 0], v[:, 2], -v[:, 1]
    return {"tris": builder.tris(), "x": [round(float(gx.min()), 2), round(float(gx.max()), 2)],
            "z": [round(float(gz.min()), 2), round(float(gz.max()), 2)], "y": [round(float(gy.min()), 2), round(float(gy.max()), 2)]}


MODELS = {
    "rival_keep": rival_keep,
    "rival_walls": rival_walls,
    "rival_house_a": rival_house_a,
    "rival_house_b": rival_house_b,
}

clear_scene()
objs = []
report = {}
for i, (name, fn) in enumerate(MODELS.items()):
    bld = fn(np.random.default_rng(9100 + i))
    report[name] = bounds(bld)
    objs.append(bld.build(name, MATS))
export_glb(OUT / "rival_kit.glb", objs)
for k, v in report.items():
    print(f"{k}: {v}")
print("RIVAL_KIT_DONE", sum(v["tris"] for v in report.values()))
