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
from mathutils import Quaternion

HERE = Path(__file__).resolve().parent
sys.path.append(str(HERE))
_src = (HERE / "wayside_models.py").read_text(encoding="utf-8")
exec(compile(_src[:_src.index("\nMODELS = {")], str(HERE / "wayside_models.py"), "exec"))

M_PLASTER = len(MATS)
MATS = MATS + ["s_plaster"]
M_TMATTE = len(MATS)
MATS = MATS + ["s_timber_matte"]   # matte twin of s_timber: the gate leaves (no slate-grey sky sheen)
BOARD_CENTRES[M_TMATTE] = BOARD_CENTRES[M_TIMBER]
UP = V(0, 1, 0)
VOID = (0.03, 0.027, 0.025)
MUD = (0.98, 0.78, 0.56)           # ochre earthen render (on the off-white plaster scan)
MUD_PALE = (0.98, 0.88, 0.74)
SANDST = (0.98, 0.82, 0.6)        # sandstone footing (on the grey rock scan)
BRICK = (0.72, 0.5, 0.34)         # exposed mud brick where the render fell off
BEAMC = (0.8, 0.6, 0.42)
PALM = (0.7, 0.6, 0.48)
SAND = (1.0, 0.86, 0.64)
ROPE = (0.72, 0.62, 0.45)
CRIMSON = (0.6, 0.06, 0.07)
TERRA = (0.85, 0.5, 0.32)


_slab = slab


def slab(g, centre, size, rot, rng, rough=0.1, round_r=0.07, **kw):
    """Crisp mud-brick / ashlar mass: `rough` becomes an absolute bump of ~rough * 0.2 u (the
    toolkit scales it by the block's half-size, which melted the big masses into blobs)."""
    m = max(1e-3, min(size[0], size[2]) / 2 * 2)
    return _slab(g, centre, size, rot, rng, rough=rough * 0.2 / m * 0.6, round_r=min(round_r, 0.04), **kw)


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
    """A hand-made mud-brick merlon: a slightly tapered block with a rounded, crowned top, each one
    a little different (lean, width, height)."""
    q = quat_y(yaw_a + rng.uniform(-0.06, 0.06))
    w, hgt, d = 0.46 * s * rng.uniform(0.92, 1.08), 0.56 * s * rng.uniform(0.9, 1.1), 0.4 * s
    _slab(g, V(c.x, c.y + hgt / 2, c.z), (w, hgt, d), q, rng, mat=M_PLASTER, res=(2, 3, 2), round_r=0.12 * s,
          rough=0.05, taper=0.1, crown=0.22, col_fn=col_fn, tile=1.0)


def deep_opening(g, rng, c, nrm, w, h, depth=0.16, col=None, grille=False, lintel=True):
    """A window / loop with depth: a dark round-headed opening set back behind a rendered reveal
    standing proud of the face, a sandstone sill and a palm-trunk lintel; optional wooden grille."""
    col = col or MUD
    tng = UP.cross(nrm).normalized()
    spring = h - w / 2
    ctr = c + UP * spring
    outline = [c - tng * (w / 2), c + tng * (w / 2), c + tng * (w / 2) + UP * spring]
    for k in range(1, 8):
        a = math.pi * k / 8
        outline.append(ctr + tng * (w / 2 * math.cos(a)) + UP * (w / 2 * math.sin(a)))
    outline.append(c - tng * (w / 2) + UP * spring)
    face_w(g, outline, nrm, M_PLASTER, VOID)
    rc = scale(col, 0.7)
    n = len(outline)
    mid_c = c + UP * (h * 0.5)
    for i in range(1, n):
        p0, p1 = outline[i], outline[(i + 1) % n]
        q = [p0, p1, p1 + nrm * depth, p0 + nrm * depth]
        face_w(g, q, mid_c - (p0 + p1) / 2, M_PLASTER, rc)
    # A plaster surround standing proud of the face.
    for i in range(1, n):
        p0, p1 = outline[i], outline[(i + 1) % n]
        d0 = (p0 - ctr).normalized() if i > 2 else (tng if (p0 - c).dot(tng) > 0 else -tng)
        d1 = (p1 - ctr).normalized() if (i + 1) % n > 2 and (i + 1) % n != 0 else (tng if (p1 - c).dot(tng) > 0 else -tng)
        face_w(g, [p0 + nrm * depth, p1 + nrm * depth, p1 + d1 * 0.09 + nrm * depth, p0 + d0 * 0.09 + nrm * depth],
               nrm, M_PLASTER, scale(col, 1.04))
        o0, o1 = p0 + d0 * 0.09, p1 + d1 * 0.09
        face_w(g, [o0, o1, o1 + nrm * depth, o0 + nrm * depth], (o0 + o1) / 2 - mid_c, M_PLASTER, scale(col, 0.92))
    slab(g, c + nrm * (depth * 0.6) - UP * 0.05, (w + 0.28, 0.1, depth + 0.18), yaw_q(tng), rng, mat=M_STONE,
         res=(2, 1, 1), round_r=0.02, rough=0.1, col_fn=rock_col(SANDST), tile=0.8)
    if lintel:
        y = h + 0.13
        pole(g, c + UP * y - tng * (w / 2 + 0.24) + nrm * (depth * 0.6),
             c + UP * y + tng * (w / 2 + 0.24) + nrm * (depth * 0.6), 0.065, 0.06, rng, mat=M_BARK, col=PALM,
             sides=7, segs=1)
    if grille:
        for k in range(1, 4):
            x = -w / 2 + k * w / 4
            pole(g, c + tng * x + nrm * 0.03, c + tng * x + UP * (spring + 0.05) + nrm * 0.03, 0.016, 0.016, rng,
                 mat=M_TIMBER, col=scale(BEAMC, 0.7), sides=5, segs=1)
        pole(g, c - tng * (w / 2) + UP * (spring * 0.5) + nrm * 0.03, c + tng * (w / 2) + UP * (spring * 0.5) + nrm * 0.03,
             0.016, 0.016, rng, mat=M_TIMBER, col=scale(BEAMC, 0.7), sides=5, segs=1)


def arch_door(g, rng, c, nrm, w, h, studs=True, ring=True):
    """A closed round-headed plank door (centre-bottom c on the face, outward nrm): vertical planks
    cut to the arch, ledges, rows of iron studs, a ring pull; a ring of sandstone voussoirs and
    alternating jamb blocks round it, a threshold slab."""
    tng = UP.cross(nrm).normalized()
    r = w / 2
    spring = h - r
    ctr = c + UP * spring
    face_w(g, [c - tng * r, c + tng * r, ctr + tng * r, ctr - tng * r], nrm, M_PLASTER, VOID)
    n_pl = max(3, int(w / 0.2))
    for i in range(n_pl):
        x = -r + (i + 0.5) * w / n_pl
        top = spring + math.sqrt(max(0.0, r * r - x * x)) - 0.03
        board(g, c + tng * x + UP * (top / 2) + nrm * 0.02, (0, 1, 0), tuple(nrm), top, w / n_pl - 0.012, 0.06,
              mat=M_TIMBER, col=scale((1.0, 0.7, 0.44), rng.uniform(0.9, 1.0)), rng=rng)
    for y in (0.35, spring * 0.55, spring - 0.05):
        lbox(g, c + UP * y + nrm * 0.065, (w - 0.1, 0.11, 0.035), yaw_q(tng), M_TIMBER, scale(BEAMC, 0.6), tile=0.5)
        if studs:
            for i in range(max(3, int(w / 0.16))):
                x = -r + 0.1 + i * (w - 0.2) / max(2, int(w / 0.16) - 1)
                lathe(g, tuple(c + tng * x + UP * y + nrm * 0.08), tuple(nrm),
                      [(0.0, 0.026), (0.012, 0.022), (0.022, 0.0)], 6, M_IRON, (0.32, 0.3, 0.29), tile=0.2)
    if ring:
        lathe(g, tuple(c + UP * (spring * 0.62) + tng * 0.18 + nrm * 0.08), tuple(nrm),
              [(0.0, 0.05), (0.02, 0.04), (0.03, 0.0)], 8, M_IRON, (0.3, 0.29, 0.28), tile=0.2)
        tube(g, [c + UP * (spring * 0.62 - 0.02 - 0.09 * math.cos(a)) + tng * (0.18 + 0.09 * math.sin(a)) + nrm * 0.1
                 for a in np.linspace(0, 2 * math.pi, 9)], [0.012] * 9, 5, M_IRON, (0.3, 0.29, 0.28), tile=0.2,
             cap=False)
    # Voussoirs round the head, jamb blocks, threshold.
    m = max(7, int(math.pi * r / 0.24) | 1)
    for k in range(m):
        a = math.pi * (k + 0.5) / m
        rad = UP * math.sin(a) + tng * math.cos(a)
        deep = 0.36 if k == m // 2 else 0.3
        pc = ctr + rad * (r + deep / 2 + 0.01) + nrm * 0.06
        ang = math.atan2(rad.dot(tng), rad.dot(UP))
        lbox(g, pc, (math.pi * (r + deep / 2) / m - 0.025, deep, 0.2), Quaternion(nrm, -ang) @ yaw_q(tng), M_PLASTER,
             scale(SANDST, rng.uniform(0.85, 1.0)), tile=0.5)
    for sd in (-1, 1):
        y = 0.0
        k = 0
        while y < spring - 0.05:
            hgt = min(rng.uniform(0.3, 0.42), spring - y)
            wd = 0.34 if k % 2 else 0.24
            lbox(g, c + tng * (sd * (r + wd / 2 + 0.01)) + UP * (y + hgt / 2) + nrm * 0.06, (wd, hgt - 0.02, 0.2),
                 yaw_q(tng), M_PLASTER, scale(SANDST, rng.uniform(0.8, 0.95)), tile=0.5)
            y += hgt
            k += 1
    slab(g, c + nrm * 0.2 - UP * 0.04, (w + 0.6, 0.12, 0.5), yaw_q(tng), rng, mat=M_STONE, res=(2, 1, 1), round_r=0.03,
         rough=0.1, col_fn=rock_col(SANDST), tile=0.8)


def sand_drift(g, rng, a, b, nrm):
    """Wind-blown sand heaped along a wall foot (ground points a -> b, the face outward normal nrm)."""
    a, b = V(a.x, 0, a.z), V(b.x, 0, b.z)
    L = (b - a).length
    q = (b - a).normalized()
    along_x = abs(q.x) > abs(q.z)
    k = max(1, int(L / 1.8))
    for i in range(k):
        if rng.random() < 0.3:
            continue
        c = a.lerp(b, (i + rng.uniform(0.25, 0.75)) / k) + nrm * rng.uniform(0.2, 0.45)
        rx = rng.uniform(0.8, 1.4)
        mound(g, (c.x, -0.05, c.z), rx if along_x else 0.5, 0.5 if along_x else rx, rng.uniform(0.15, 0.28), rng,
              mat=M_EARTH, col_fn=lambda p_, n_: SAND, rings=4, seg=14, rough=0.08)


def rope_ladder(g, rng, top, nrm, h):
    tng = UP.cross(nrm).normalized()
    k = max(3, int(h / 0.32))
    for sd in (-1, 1):
        pts = [top + tng * (sd * 0.2) + nrm * (0.04 + 0.1 * math.sin(f / 4 * math.pi) + 0.06 * f / 4) - UP * (h * f / 4)
               for f in range(5)]
        tube(g, pts, [0.016] * 5, 5, M_CLOTH, ROPE, tile=0.3)
    for i in range(1, k):
        f = i / k
        p = top + nrm * (0.04 + 0.1 * math.sin(f * math.pi) + 0.06 * f) - UP * (h * f)
        pole(g, p - tng * 0.22, p + tng * 0.22, 0.022, 0.022, rng, mat=M_TIMBER, col=BEAMC, sides=5, segs=1)


def shade(g, rng, A, B, nrm, reach=1.8, h_out=1.75, col=(0.86, 0.8, 0.66), stripe=None):
    """A cloth sun-shade hung off the wall at A..B (game coords), out to two palm poles, sagging."""
    A, B = V(A.x, A.y, A.z), V(B.x, B.y, B.z)
    for P in (A, B):
        foot = V(P.x, 0, P.z) + nrm * reach
        pole(g, foot - UP * 0.2, foot + UP * (h_out + 0.08), 0.04, 0.032, rng, mat=M_BARK, col=PALM, sides=6, segs=2)
    rows = []
    for i in range(6):
        f = i / 5
        P = A.lerp(B, f)
        row = []
        for j in range(4):
            u = j / 3
            out = V(P.x, h_out, P.z) + nrm * reach
            qq = P.lerp(out, u) - UP * (0.16 * math.sin(u * math.pi) + 0.07 * math.sin(f * math.pi))
            row.append(qq)
        rows.append(row)
    cf = (lambda u, v: stripe if (stripe and int(v * 6) % 2) else col)
    sheet(g, rows, M_CLOTH, cf, tile=0.6, double=True)


def footing_run(g, rng, a, b, T, h=0.42):
    """Sandstone rubble footing under a wall from a to b (ground points)."""
    a, b = Vector(a), Vector(b)
    t = (b - a).normalized()
    L = (b - a).length
    n = max(1, int(L / 2.2))
    for k in range(n):
        c = a.lerp(b, (k + 0.5) / n)
        slab(g, V(c.x, h / 2 - 0.12, c.z), (L / n + 0.05, h + 0.24, T + 0.18), yaw_q(t), rng, mat=M_STONE,
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
    for _ in range(int(L / 2.2) + 1):
        s = rng.uniform(0.6, L - 0.6)
        side = rng.choice([-1, 1])
        patches.append((a + t * s + nrm * side * (T / 2) + UP * rng.uniform(0.5, 1.2), rng.uniform(0.25, 0.5),
                        rng.uniform(0.15, 0.3)))
    col = render_col(rng, 0.0, H + 0.5, patches=patches)
    for pc, rx, ry in patches:
        side = 1 if (pc - a).dot(nrm) > 0 else -1
        for r in range(int(ry * 2 / 0.11)):
            y = pc.y - ry * 0.8 + r * 0.11
            off = 0.0 if r % 2 else 0.14
            for k in range(int(rx * 1.6 / 0.28)):
                s = -rx * 0.8 + off + k * 0.28
                if (s / rx) ** 2 + ((y - pc.y) / ry) ** 2 > 0.75:
                    continue
                lbox(g, pc + t * s + UP * (y - pc.y) + nrm * side * 0.01, (0.26, 0.09, 0.05), yaw_q(t), M_EARTH,
                     scale(BRICK, rng.uniform(0.85, 1.1)), tile=0.4)
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
    # Palm-trunk beam ends (vigas) through both faces under the wall walk; sand drifted at the feet.
    for s_ in np.arange(0.6, L - 0.3, 1.3):
        p = a + t * float(s_) + UP * (H - 0.3 + rng.uniform(-0.03, 0.03))
        pole(g, p - nrm * (T / 2 + 0.2), p + nrm * (T / 2 + 0.2), 0.06, 0.055, rng, mat=M_BARK, col=PALM, sides=6,
             segs=1)
    sand_drift(g, rng, a, b, nrm)
    sand_drift(g, rng, a, b, -nrm)
    # Drain spouts (palm-trunk gutters) through the wall top every few metres.
    for s in np.arange(2.0, L - 1.0, 4.5):
        for sd in (-1,):
            p = a + t * float(s) + UP * (H - 0.05)
            pole(g, p, p + nrm * sd * (T / 2 + 0.42) - UP * 0.06, 0.07, 0.06, rng, mat=M_BARK, col=PALM, sides=6,
                 segs=1)
            # A dark wet streak run down the render under the spout.
            q0 = p + nrm * sd * (T / 2 + 0.005) - UP * 0.1
            face_w(g, [q0 - t * 0.07, q0 + t * 0.07, q0 + t * 0.11 - UP * 0.9, q0 - t * 0.09 - UP * 1.05],
                   nrm * sd, M_PLASTER, scale(MUD, 0.62))


def tower(g, rng, c, w=2.8, H=3.1, banner=True):
    c = Vector(c)
    col = render_col(rng, 0.0, H + 0.5, patches=[(c + V(w / 2, 1.2, 0.3), 0.4, 0.3)])
    slab(g, V(c.x, 0.1, c.z), (w + 0.25, 0.5, w + 0.25), quat_y(0.0), rng, mat=M_STONE, res=(4, 2, 4), round_r=0.08,
         rough=0.2, col_fn=rock_col(SANDST, dark_below=0.6), tile=1.3)
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
        deep_opening(g, rng, c + nrm * (w / 2 * 0.95) + UP * 1.45, nrm, 0.22, 0.66, depth=0.12, lintel=False)
        sand_drift(g, rng, c + nrm * (w / 2 + 0.1) - tng * (w / 2), c + nrm * (w / 2 + 0.1) + tng * (w / 2), nrm)
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
    slab(g, V(0, 0.7, 0), (6.7, 1.6, 6.7), quat_y(0.0), rng, mat=M_STONE, res=(8, 3, 8), round_r=0.12, rough=0.12,
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
    slab(g, V(0, 1.75, 3.3), (2.5, 3.5, 0.6), quat_y(0.0), rng, mat=M_PLASTER, res=(3, 4, 2), round_r=0.06,
         rough=0.08, taper=0.03, col_fn=col, tile=1.6)
    arch_door(g, rng, V(0, 0.06, 3.61), V(0, 0, 1), 1.3, 2.35)
    for k in range(2):
        pole(g, V(-1.15, 3.05 + k * 0.17, 3.68), V(1.15, 3.05 + k * 0.17, 3.68), 0.085, 0.08, rng, mat=M_BARK,
             col=PALM, sides=8, segs=1)
    shade(g, rng, V(-1.2, 3.42, 3.62), V(1.2, 3.42, 3.62), V(0, 0, 1), reach=1.6, h_out=2.45, col=(0.88, 0.83, 0.7),
          stripe=(0.55, 0.12, 0.1))
    # Steps up to the door.
    for k in range(2):
        slab(g, V(0, 0.08 + k * 0.16 - 0.08, 3.95 + 0.32 - k * 0.3), (2.0 - k * 0.3, 0.2, 0.42), quat_y(0.0), rng,
             mat=M_STONE, res=(3, 1, 2), round_r=0.04, rough=0.1, col_fn=rock_col(SANDST), tile=0.8)
    for sx, sz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nrm, tng = V(sx, 0, sz), V(-sz, 0, sx)
        for k in (-1, 1):
            deep_opening(g, rng, nrm * 2.2 + tng * (k * 0.95) + UP * 4.95, nrm, 0.46, 0.9, depth=0.18, grille=True)
        deep_opening(g, rng, nrm * 1.62 + UP * 8.0, nrm, 0.4, 0.75, depth=0.16, grille=sz == 0)
        if sz != 1:
            deep_opening(g, rng, nrm * 2.98 + UP * 2.3, nrm, 0.24, 0.8, depth=0.14, lintel=False)
        sand_drift(g, rng, nrm * 3.45 - tng * 3.0, nrm * 3.45 + tng * 3.0, nrm)
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
    # Gatehouse: two battered pylons, a segmental sandstone arch over the 7 u gap with rendered
    # spandrels and a soffit through the wall depth, studded plank leaves swung inward.
    col = render_col(rng, 0.0, 5.0, patches=[(V(-4.6, 1.6, h + 0.8), 0.35, 0.3), (V(2.2, 3.9, h + 0.62), 0.45, 0.25)])
    PH, PD, top = 4.6, 1.7, 4.3
    for sx in (-1, 1):
        x = sx * (GATE_HALF + 0.8)
        slab(g, V(x, 0.15, h), (1.85, 0.7, PD + 0.25), quat_y(0.0), rng, mat=M_STONE, res=(3, 2, 3), round_r=0.06,
             rough=0.15, col_fn=rock_col(SANDST, dark_below=0.6), tile=1.3)
        slab(g, V(x, PH / 2 + 0.2, h), (1.6, PH - 0.2, PD), quat_y(0.0), rng, mat=M_PLASTER, res=(3, 7, 3),
             round_r=0.06, rough=0.1, taper=0.07, col_fn=col, tile=1.4)
        for dz in (-0.5, 0.0, 0.5):
            for dx in (-0.45, 0.45):
                merlon(g, rng, V(x + dx, PH + 0.28, h + dz), 0.0, col, s=0.9)
        for k in (-1, 1):
            p = V(x + k * 0.4, PH - 0.35, h)
            pole(g, p - V(0, 0, PD / 2 + 0.2), p + V(0, 0, PD / 2 + 0.25), 0.07, 0.065, rng, mat=M_BARK, col=PALM,
                 sides=6, segs=1)
        deep_opening(g, rng, V(x, 2.6, h + PD / 2 - 0.04), V(0, 0, 1), 0.2, 0.6, depth=0.12, lintel=False)
        sand_drift(g, rng, V(x - 1.0, 0, h + PD / 2 + 0.1), V(x + 1.0, 0, h + PD / 2 + 0.1), V(0, 0, 1))
    # Segmental arch: span 2*GATE_HALF, springing at 2.5, rise 1.05.
    sp, rise, hs = 2.5, 1.05, GATE_HALF
    R = (hs * hs + rise * rise) / (2 * rise)
    cy = sp + rise - R
    th0 = math.asin(hs / R)
    N = 14
    intr = [V(R * math.sin(-th0 + 2 * th0 * i / N), cy + R * math.cos(-th0 + 2 * th0 * i / N), 0) for i in range(N + 1)]
    for zf, nz in ((h + PD / 2 - 0.08, 1), (h - PD / 2 + 0.08, -1)):
        poly = [V(p.x, p.y, zf) for p in intr] + [V(hs + 0.02, top, zf), V(-hs - 0.02, top, zf)]
        face_w(g, poly, V(0, 0, nz), M_PLASTER, scale(MUD, 0.97))
        m = 11
        for k in range(m):
            th = -th0 + 2 * th0 * (k + 0.5) / m
            radial = V(math.sin(th), math.cos(th), 0)
            deep = 0.5 if k == m // 2 else 0.4
            pc = V(0, cy, 0) + radial * (R + deep / 2) + V(0, 0, zf + nz * 0.07)
            lbox(g, pc, (2 * th0 * (R + deep / 2) / m - 0.03, deep, 0.22), quat_z(-th), M_PLASTER,
                 scale(SANDST, rng.uniform(0.8, 0.95)), tile=0.5)
    zf0, zf1 = h - PD / 2 + 0.08, h + PD / 2 - 0.08
    for i in range(N):
        p0, p1 = intr[i], intr[i + 1]
        face_w(g, [V(p0.x, p0.y, zf0), V(p1.x, p1.y, zf0), V(p1.x, p1.y, zf1), V(p0.x, p0.y, zf1)],
               V(0, cy, 0) - (p0 + p1) / 2, M_PLASTER, scale(MUD, 0.7))
    # Spandrel top: a cap, a crenellated parapet, a palm-pole hoarding beam.
    slab(g, V(0, top + 0.1, h), (2 * hs + 0.2, 0.26, PD - 0.1), quat_y(0.0), rng, mat=M_PLASTER, res=(6, 1, 2),
         round_r=0.05, rough=0.1, col_fn=col, tile=1.4)
    for i in range(8):
        merlon(g, rng, V(-hs + 0.35 + i * (2 * hs - 0.7) / 7, top + 0.22, h + PD / 2 - 0.3), 0.0, col, s=0.9)
    for x in np.linspace(-hs + 0.4, hs - 0.4, 6):
        p = V(float(x), top - 0.2, h)
        pole(g, p - V(0, 0, PD / 2 + 0.2), p + V(0, 0, PD / 2 + 0.3), 0.065, 0.06, rng, mat=M_BARK, col=PALM, sides=6,
             segs=1)
    # Leaves: swung 90 deg inward against the arch line, planks cut to the arch, ledges, studs.
    for sx in (-1, 1):
        hx = sx * (hs - 0.1)
        zh = h - PD / 2 + 0.12
        n_pl = 12
        lw = hs - 0.15
        for i in range(n_pl):
            d = (i + 0.5) * lw / n_pl
            xa = hs - d
            ya = cy + math.sqrt(max(0.0, R * R - xa * xa)) - 0.08
            board(g, V(hx, ya / 2 + 0.04, zh - d), (0, 1, 0), (-sx, 0, 0), ya - 0.04, lw / n_pl - 0.01, 0.07,
                  mat=M_TMATTE, col=scale((1.0, 0.7, 0.44), rng.uniform(0.9, 1.0)), rng=rng)
        for y in (0.5, 1.45, 2.35):
            lbox(g, V(hx - sx * 0.07, y, zh - lw / 2), (0.04, 0.13, lw - 0.15), quat_y(0.0), M_TIMBER,
                 scale(BEAMC, 0.55), tile=0.5)
            for j in range(11):
                lathe(g, (hx - sx * 0.09, y, zh - 0.15 - j * (lw - 0.3) / 10), (-sx, 0, 0),
                      [(0.0, 0.03), (0.014, 0.025), (0.026, 0.0)], 6, M_IRON, (0.32, 0.3, 0.29), tile=0.2)
        for y in (0.3, 2.2):
            lathe(g, (hx, y, zh + 0.02), (0, 1, 0), [(-0.1, 0.06), (0.1, 0.06)], 8, M_IRON, (0.3, 0.29, 0.28), tile=0.2)
    # Outside: a striped awning against the wall by the gate, rope ladders and shades inside.
    shade(g, rng, V(5.4, 1.75, h + WALL_T / 2), V(8.2, 1.75, h + WALL_T / 2), V(0, 0, 1), reach=1.9, h_out=1.55,
          col=(0.86, 0.8, 0.66), stripe=(0.42, 0.22, 0.12))
    for i in range(3):
        jar(g, rng, (5.9 + i * 0.55, 0.0, h + 1.1 + (i % 2) * 0.3), s=1.0 + 0.2 * (i % 2))
    shade(g, rng, V(-7.5, 1.7, -h + WALL_T / 2), V(-4.5, 1.7, -h + WALL_T / 2), V(0, 0, 1), reach=1.8, h_out=1.6)
    shade(g, rng, V(h - WALL_T / 2, 1.7, -2.0), V(h - WALL_T / 2, 1.7, 1.2), V(-1, 0, 0), reach=1.8, h_out=1.6,
          col=(0.82, 0.7, 0.55), stripe=(0.6, 0.06, 0.07))
    rope_ladder(g, rng, V(-h + WALL_T / 2, WALL_H + 0.05, 4.0), V(1, 0, 0), WALL_H + 0.05)
    rope_ladder(g, rng, V(6.0, WALL_H + 0.05, -h + WALL_T / 2), V(0, 0, 1), WALL_H + 0.05)
    rope_ladder(g, rng, V(-8.0, WALL_H + 0.05, h - WALL_T / 2), V(0, 0, -1), WALL_H + 0.05)
    for sx in (-1, 1):
        pennant(g, rng, V(sx * (GATE_HALF + 0.8), PH + 0.25, h - 0.5), 1.9, 0.8)
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
    # A shallow rendered door surround standing proud of the wall, the round-headed plank door with
    # its studs and ring, sandstone voussoirs and threshold; a palm-trunk lintel over it all.
    slab(g, V(dx, 0.72, D / 2 + 0.06), (1.25, 1.6, 0.16), quat_y(0.0), rng, mat=M_PLASTER, res=(2, 3, 1),
         round_r=0.04, rough=0.08, col_fn=col, tile=1.3)
    arch_door(g, rng, V(dx, 0.08, D / 2 + 0.145), V(0, 0, 1), 0.7, 1.3)
    pole(g, V(dx - 0.62, 1.66, D / 2 + 0.2), V(dx + 0.62, 1.66, D / 2 + 0.2), 0.06, 0.055, rng, mat=M_BARK, col=PALM,
         sides=7, segs=1)
    deep_opening(g, rng, V(-dx * 1.6, 1.1, D / 2 - 0.02), V(0, 0, 1), 0.3, 0.46, depth=0.1, grille=True)
    deep_opening(g, rng, V(W / 2 - 0.02, 1.15, 0.3), V(1, 0, 0), 0.28, 0.44, depth=0.1, lintel=False)
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


# ─────────────────────────────── the Pasha's producers (farm / palm-wood yard / sandstone pit)
# Same culture as the houses: rendered mud brick on sandstone footings, palm-trunk beams, shade
# cloth on palm poles. Pivot = ground under the building; +Z faces OUT from the fort (rival.rs
# turns each producer so its yard looks away from the walls). Each keeps its solid mass inside the
# 1.5 x 1.4 collision half box; the yard pieces in front (+Z) are walk-through or low.
GREEN = (0.42, 0.55, 0.22)
WET = (0.36, 0.27, 0.2)


def mud_block(g, rng, c, W, D, H, col, beams=True):
    """A rendered mud-brick block on a sandstone footing: battered walls, parapet, earth roof and
    palm-trunk beam ends along front and back. `c` = ground point under its centre."""
    slab(g, V(c.x, 0.08, c.z), (W + 0.12, 0.36, D + 0.12), quat_y(0.0), rng, mat=M_ROCK, res=(4, 1, 4), round_r=0.06,
         rough=0.2, col_fn=rock_col(SANDST, dark_below=0.6), tile=0.9)
    slab(g, V(c.x, H / 2 + 0.05, c.z), (W, H - 0.1, D), quat_y(0.0), rng, mat=M_PLASTER, res=(5, 4, 5), round_r=0.09,
         rough=0.12, taper=0.05, col_fn=col, tile=1.3)
    for x, z, sx, sz in ((0, D / 2 - 0.06, W, 0.14), (0, -D / 2 + 0.06, W, 0.14), (W / 2 - 0.06, 0, 0.14, D),
                         (-W / 2 + 0.06, 0, 0.14, D)):
        slab(g, V(c.x + x, H + 0.1, c.z + z), (sx, 0.26, sz), quat_y(0.0), rng, mat=M_PLASTER, res=(4, 1, 1),
             round_r=0.05, rough=0.15, col_fn=col, tile=1.3)
    slab(g, V(c.x, H - 0.02, c.z), (W - 0.2, 0.06, D - 0.2), quat_y(0.0), rng, mat=M_EARTH, res=(3, 1, 3),
         round_r=0.02, rough=0.1, col_fn=lambda p, n: (0.66, 0.54, 0.4), tile=0.8)
    if beams:
        for z in (D / 2, -D / 2):
            sgn = 1 if z > 0 else -1
            for x in np.linspace(-W / 2 + 0.28, W / 2 - 0.28, max(3, int(W / 0.5))):
                p = V(c.x + float(x), H - 0.2, c.z + z)
                pole(g, p - V(0, 0, 0.15 * sgn), p + V(0, 0, 0.17 * sgn), 0.05, 0.045, rng, mat=M_BARK, col=BEAMC,
                     sides=6, segs=1)


def palm_trunk(g, rng, a, b, r=0.15, col=PALM):
    """A date-palm trunk (or log): the ringed leaf-base scars swell and pinch along it."""
    a, b = Vector(a), Vector(b)
    n = max(4, int((b - a).length / 0.09))
    pts = [a.lerp(b, k / n) for k in range(n + 1)]
    radii = [r * (1.0 + (0.1 if k % 2 else -0.04)) * (1.0 - 0.12 * k / n) for k in range(n + 1)]
    tube(g, pts, radii, 9, M_BARK, col, tile=0.5)


def frond(g, rng, base, d, L=1.6, col=(0.62, 0.55, 0.34)):
    """A dried palm frond lying on the ground: a midrib with stiff leaflets fanned along it."""
    d = Vector(d).normalized()
    side = d.cross(UP).normalized()
    tip = base + d * L + UP * 0.02
    tube(g, [base, base.lerp(tip, 0.5) + UP * 0.04, tip], [0.02, 0.014, 0.004], 4, M_BARK, col, tile=0.4)
    for k in range(1, 11):
        f = k / 11
        p = base.lerp(tip, f) + UP * 0.03
        ln = 0.42 * math.sin(f * math.pi) + 0.08
        for s in (-1, 1):
            q = p + side * s * ln + d * 0.12 + UP * rng.uniform(-0.01, 0.03)
            lbox(g, (p + q) / 2, ((q - p).length, 0.008, 0.045), yaw_q((q - p).normalized()), M_THATCH,
                 scale(col, rng.uniform(0.85, 1.05)), tile=0.4)


def shade_cloth(g, rng, x0, x1, z0, z1, h=2.05, col=(0.9, 0.84, 0.7), stripe=(0.62, 0.12, 0.1)):
    """A free-standing shade cloth on four palm poles, sagging between them."""
    for x in (x0, x1):
        for z in (z0, z1):
            pole(g, V(x, -0.2, z), V(x, h + 0.1, z), 0.045, 0.035, rng, mat=M_BARK, col=PALM, sides=6, segs=2)
    rows = []
    for i in range(6):
        u = i / 5
        rows.append([V(x0 + (x1 - x0) * u, h - 0.2 * math.sin(u * math.pi) * math.sin(v / 3 * math.pi) -
                       0.05 * math.sin(u * math.pi), z0 + (z1 - z0) * v / 3) for v in range(4)])
    sheet(g, rows, M_CLOTH, lambda u, v: stripe if int(u * 7) % 2 else col, tile=0.6, double=True)
    for x in (x0, x1):  # guy ropes to pegs
        for z, sz in ((z0, -1), (z1, 1)):
            tube(g, [V(x, h + 0.05, z), V(x + 0.0, 0.0, z + sz * 0.9)], [0.01, 0.01], 4, M_CLOTH, ROPE, tile=0.3)


def basket(g, rng, c, r=0.22, h=0.26, fill=None):
    lathe(g, c, (0, 1, 0), [(0.0, r * 0.75), (h * 0.5, r), (h, r * 1.05), (h + 0.02, r * 0.95)], 12, M_THATCH,
          (0.8, 0.66, 0.44), tile=0.3)
    if fill:
        mound(g, (c[0], c[1] + h - 0.04, c[2]), r * 0.9, r * 0.9, 0.08, rng, mat=M_EARTH,
              col_fn=lambda p, n: fill, rings=3, seg=10, rough=0.2)


def rival_farm(rng):
    """The Pasha's date garden: a mud-brick store with a beehive granary, a shaduf well-sweep over a
    stone cistern, irrigated beds of green crops between earth channels, a palm-frond shade."""
    b = Builder()
    g = G(b)
    col = render_col(rng, 0.0, 2.0, base=MUD, patches=[(V(-1.4, 0.9, -0.2), 0.3, 0.22)])
    mud_block(g, rng, V(-0.45, 0, -0.35), 1.9, 1.9, 1.75, col)
    arch_door(g, rng, V(-0.45, 0.08, 0.6 + 0.02), V(0, 0, 1), 0.66, 1.24)
    pole(g, V(-1.05, 1.56, 0.68), V(0.15, 1.56, 0.68), 0.055, 0.05, rng, mat=M_BARK, col=PALM, sides=7, segs=1)
    deep_opening(g, rng, V(-1.4 - 0.02, 1.05, -0.4), V(-1, 0, 0), 0.26, 0.4, depth=0.09, grille=True)
    # Beehive granary: a mud dome with a hatch near the top and a ladder to it.
    gx, gz = 0.95, -0.55
    lathe(g, (gx, -0.05, gz), (0, 1, 0), [(0.0, 0.66), (0.4, 0.68), (0.9, 0.6), (1.3, 0.44), (1.62, 0.22),
                                          (1.76, 0.0)], 16, M_PLASTER, scale(MUD_PALE, 0.92), tile=1.0)
    face_w(g, [V(gx - 0.14, 1.1, gz + 0.56), V(gx + 0.14, 1.1, gz + 0.56), V(gx + 0.12, 1.36, gz + 0.48),
               V(gx - 0.12, 1.36, gz + 0.48)], V(0, 0.4, 1), M_EARTH, VOID)
    ladder(g, rng, V(gx + 0.05, -0.05, gz + 1.15), V(gx, 1.3, gz + 0.6), width=0.34)
    # Irrigated beds in front: dark wet earth ridges with crop rows, a channel down the middle.
    for k, x in enumerate((-1.25, -0.65, 0.65, 1.25)):
        mound(g, (x, -0.06, 2.55), 0.26, 1.05, 0.13, rng, mat=M_EARTH, col_fn=lambda p, n: WET, rings=3, seg=14,
              rough=0.1)
        for j in range(7):
            z = 1.7 + j * 0.28 + rng.uniform(-0.03, 0.03)
            c = V(x + rng.uniform(-0.04, 0.04), 0.05, z)
            for s in range(5):
                a = s / 5 * math.tau + rng.uniform(-0.3, 0.3)
                L = rng.uniform(0.16, 0.26)
                tip = c + V(math.cos(a) * L * 0.55, L, math.sin(a) * L * 0.55)
                tube(g, [c, c.lerp(tip, 0.6) + UP * 0.02, tip], [0.018, 0.012, 0.002], 4, M_THATCH,
                     scale(GREEN, rng.uniform(0.8, 1.15)), tile=0.3)
    # The channel: a shallow sunk strip of water between low earth lips, fed from the cistern.
    lbox(g, V(0, -0.015, 2.5), (0.22, 0.03, 2.3), quat_y(0.0), M_EARTH, (0.12, 0.13, 0.12), tile=0.5)
    for s in (-1, 1):
        mound(g, (s * 0.2, -0.05, 2.5), 0.09, 1.15, 0.07, rng, mat=M_EARTH, col_fn=lambda p, n: WET, rings=2, seg=12)
    # Cistern (stone ring, dark water) + the shaduf: a palm pole see-sawing on a crossbar between
    # two mud pillars, a mud counterweight at the short end, a rope and leather bucket over the water.
    cx, cz = -1.85, 1.35
    for k in range(9):
        a = k / 9 * math.tau
        slab(g, V(cx + math.cos(a) * 0.48, 0.12, cz + math.sin(a) * 0.48), (0.34, 0.36, 0.2), quat_y(-a + math.pi / 2),
             rng, mat=M_STONE, res=(2, 1, 1), round_r=0.03, rough=0.2, col_fn=rock_col(SANDST, dark_below=0.6), tile=0.8)
    lathe(g, (cx, 0.1, cz), (0, 1, 0), [(0.0, 0.4), (0.01, 0.4)], 12, M_EARTH, (0.05, 0.06, 0.06), tile=0.5)
    for s in (-1, 1):
        slab(g, V(cx + 0.95 + s * 0.3, 0.75, cz - 0.25), (0.26, 1.6, 0.3), quat_y(0.0), rng, mat=M_PLASTER, res=(1, 3, 1),
             round_r=0.05, rough=0.2, taper=0.12, col_fn=col, tile=1.0)
    pole(g, V(cx + 0.6, 1.5, cz - 0.25), V(cx + 1.3, 1.5, cz - 0.25), 0.04, 0.04, rng, mat=M_BARK, col=BEAMC, sides=6, segs=1)
    piv = V(cx + 0.95, 1.55, cz - 0.25)
    d = (V(cx, 2.15, cz) - piv).normalized()
    short = piv - d * 1.1
    pole(g, short, V(cx, 2.15, cz) + d * 0.1, 0.05, 0.035, rng, mat=M_BARK, col=PALM, sides=6, segs=3)
    mound(g, tuple(short + V(0, -0.12, 0)), 0.2, 0.2, 0.22, rng, mat=M_EARTH, col_fn=lambda p, n: (0.6, 0.47, 0.34),
          rings=3, seg=10, skirt=0.0)
    tube(g, [V(cx, 2.15, cz), V(cx, 0.75, cz)], [0.01, 0.01], 4, M_CLOTH, ROPE, tile=0.3)
    lathe(g, (cx, 0.5, cz), (0, 1, 0), [(0.0, 0.08), (0.12, 0.14), (0.25, 0.15)], 10, M_HIDE, (0.45, 0.32, 0.22), tile=0.3)
    # Palm-frond shade (arish) over the granary side of the yard, fronds laid on a palm-pole frame.
    for x in (0.45, 1.7):
        for z in (0.5, 1.45):
            pole(g, V(x, -0.15, z), V(x, 1.7, z), 0.045, 0.038, rng, mat=M_BARK, col=PALM, sides=6, segs=2)
    for z in (0.5, 1.45):
        pole(g, V(0.35, 1.7, z), V(1.8, 1.7, z), 0.04, 0.04, rng, mat=M_BARK, col=PALM, sides=6, segs=1)
    for k in range(6):
        x = 0.45 + k * 0.25
        frond(g, rng, V(x, 1.76, 0.25), V(0.05, 0.0, 1.0), L=1.45)
    for k, (x, z) in enumerate(((1.1, 1.0), (1.45, 1.15), (0.75, 1.2))):
        basket(g, rng, (x, 0.0, z), fill=[(0.42, 0.2, 0.1), (0.5, 0.26, 0.12), GREEN][k])
    jar(g, rng, (-1.55, 0.0, 0.75), s=1.1)
    jar(g, rng, (-1.2, 0.0, 0.85))
    sand_drift(g, rng, V(-1.4, 0, -1.3), V(0.5, 0, -1.3), V(0, 0, -1))
    return b


def rival_lumber(rng):
    """The palm-wood yard: palm trunks are the only timber in the dunes. A striped shade cloth over
    a sawing trestle with a trunk on it, the stack of felled trunks, a heap of stripped fronds, the
    chopping block, and a low mud-brick store at the back."""
    b = Builder()
    g = G(b)
    col = render_col(rng, 0.0, 1.4, base=MUD_PALE)
    mud_block(g, rng, V(0.0, 0, -0.85), 2.6, 1.1, 1.3, col)
    deep_opening(g, rng, V(0.6, 0.0, -0.3 + 0.02), V(0, 0, 1), 0.6, 1.05, depth=0.1, lintel=True)
    # Trunk stack against the store's west end: three below, two above, ringed bark, sawn ends.
    for k, (x, y, z) in enumerate(((-0.9, 0.14, 0.35), (-0.9, 0.14, 0.68), (-0.9, 0.14, 1.01), (-0.9, 0.42, 0.52),
                                   (-0.9, 0.42, 0.85))):
        L = 2.1 + rng.uniform(-0.2, 0.2)
        palm_trunk(g, rng, V(x - L / 2 + 0.6, y, z), V(x + L / 2 + 0.6, y + rng.uniform(-0.02, 0.02), z), r=0.16)
    for s in (-1, 1):
        pole(g, V(-1.4 + s * 0.0, -0.2, 0.15 + (s + 1) * 0.5), V(-1.4, 0.75, 0.15 + (s + 1) * 0.5), 0.04, 0.035, rng,
             mat=M_BARK, col=BEAMC, sides=5, segs=1)
    # The sawing trestle: two X-frames under a trunk, a two-man frame saw left in the cut.
    tx, tz = 0.55, 1.35
    for dx in (-0.55, 0.55):
        for s in (-1, 1):
            pole(g, V(tx + dx, -0.1, tz - s * 0.32), V(tx + dx, 0.82, tz + s * 0.18), 0.04, 0.035, rng, mat=M_TIMBER,
                 col=BEAMC, sides=5, segs=1)
    palm_trunk(g, rng, V(tx - 1.15, 0.86, tz - 0.07), V(tx + 1.2, 0.86, tz - 0.07), r=0.14)
    lbox(g, V(tx + 0.25, 0.86, tz - 0.07), (0.02, 0.5, 0.9), quat_x(0.15), M_TIMBER, BEAMC, tile=0.4)
    lbox(g, V(tx + 0.25, 0.62, tz - 0.07), (0.006, 0.08, 0.8), quat_x(0.15), M_IRON, IRON, tile=0.3)
    # Sawdust under the cut and chips.
    mound(g, (tx + 0.25, -0.03, tz), 0.45, 0.35, 0.06, rng, mat=M_EARTH, col_fn=lambda p, n: (0.85, 0.7, 0.5), rings=3,
          seg=12, rough=0.25)
    # Shade cloth over the saw.
    shade_cloth(g, rng, tx - 0.95, tx + 0.95, tz - 0.6, tz + 0.65, h=2.0)
    # Chopping block with an axe in it, a heap of stripped fronds, a basket of fibre.
    lathe(g, (1.55, -0.05, 0.3), (0, 1, 0), [(0.0, 0.24), (0.5, 0.22), (0.52, 0.0)], 10, M_BARK, PALM, tile=0.4)
    pole(g, V(1.55, 0.5, 0.3), V(1.3, 0.95, 0.4), 0.02, 0.018, rng, mat=M_TIMBER, col=BEAMC, sides=5, segs=1)
    lbox(g, V(1.55, 0.52, 0.31), (0.16, 0.1, 0.02), quat_z(0.6), M_IRON, IRON, tile=0.3)
    for k in range(7):
        a = rng.uniform(-0.5, 0.5) + math.pi
        frond(g, rng, V(-1.1 + rng.uniform(-0.2, 0.2), 0.02 + k * 0.025, 2.3 + rng.uniform(-0.2, 0.2)),
              V(math.cos(a), 0, math.sin(a) * 0.3 + 0.2), L=1.5)
    basket(g, rng, (1.6, 0.0, -0.05), fill=(0.55, 0.42, 0.28))
    jar(g, rng, (-0.35, 0.0, -0.15))
    sand_drift(g, rng, V(-1.3, 0, -1.45), V(1.3, 0, -1.45), V(0, 0, -1))
    return b


def rival_mine(rng):
    """The sandstone pit: a shaft collared with dressed sandstone, a palm-wood windlass over it on
    forked posts with a rope down to a hanging basket, a shade cloth for the windlass men, the spoil
    heap, cut blocks stacked for the fort's walls, ore baskets and a pick."""
    b = Builder()
    g = G(b)
    sx, sz = 0.0, 0.0
    # Spoil + collar: a low ring mound of pale spoil, sandstone blocks round the lip, black shaft.
    for k in range(6):
        a = k / 6 * math.tau + 0.3
        mound(g, (sx + math.cos(a) * 1.15, -0.08, sz + math.sin(a) * 1.15), 0.55, 0.55, 0.26, rng, mat=M_EARTH,
              col_fn=lambda p, n: SAND, rings=4, seg=14, rough=0.15)
    for k in range(10):
        a = k / 10 * math.tau
        slab(g, V(sx + math.cos(a) * 0.8, 0.12, sz + math.sin(a) * 0.8), (0.5, 0.42, 0.32), quat_y(-a + math.pi / 2), rng,
             mat=M_STONE, res=(2, 1, 1), round_r=0.03, rough=0.18, col_fn=rock_col(SANDST, dark_below=0.6), tile=0.8)
    # The shaft mouth: a dark disc sunk inside the collar (its stones hide the rim).
    lathe(g, (sx, -0.25, sz), (0, 1, 0), [(0.0, 0.6), (0.3, 0.6), (0.31, 0.0)], 14, M_EARTH, VOID, tile=0.5)
    # Windlass: two forked palm posts, a drum with a crank, rope down the shaft to a basket.
    for s in (-1, 1):
        pole(g, V(sx + s * 0.95, -0.2, sz), V(sx + s * 0.95, 1.15, sz), 0.07, 0.06, rng, mat=M_BARK, col=PALM, sides=7,
             segs=2)
        for f in (-1, 1):
            pole(g, V(sx + s * 0.95, 1.1, sz), V(sx + s * 0.95, 1.32, sz + f * 0.1), 0.03, 0.025, rng, mat=M_BARK,
                 col=PALM, sides=5, segs=1)
    palm_trunk(g, rng, V(sx - 1.05, 1.18, sz), V(sx + 1.05, 1.18, sz), r=0.11, col=BEAMC)
    tube(g, [V(sx - 0.2, 1.18, sz), V(sx + 0.2, 1.18, sz)], [0.135, 0.135], 10, M_CLOTH, ROPE, tile=0.3)
    pole(g, V(sx + 1.05, 1.18, sz), V(sx + 1.2, 1.18, sz), 0.02, 0.02, rng, mat=M_IRON, col=IRON, sides=5, segs=1)
    pole(g, V(sx + 1.2, 1.18, sz), V(sx + 1.2, 0.85, sz), 0.02, 0.02, rng, mat=M_IRON, col=IRON, sides=5, segs=1)
    tube(g, [V(sx, 1.05, sz + 0.12), V(sx, 0.62, sz + 0.12)], [0.012, 0.012], 4, M_CLOTH, ROPE, tile=0.3)
    basket(g, rng, (sx, 0.36, sz + 0.12), r=0.2, h=0.24, fill=(0.85, 0.68, 0.45))
    # Shade cloth over the windlass.
    shade_cloth(g, rng, sx - 1.3, sx + 1.3, sz - 0.95, sz + 0.95, h=2.2, col=(0.82, 0.74, 0.6), stripe=(0.3, 0.22, 0.4))
    # Cut sandstone blocks stacked for the walls (front-left), quarry marks on their faces.
    for k, (x, y, z, yaw) in enumerate(((-1.75, 0.18, 1.35, 0.05), (-1.15, 0.18, 1.4, -0.04), (-1.45, 0.52, 1.37, 0.1),
                                        (-1.7, 0.18, 1.95, 0.0))):
        slab(g, V(x, y, z), (0.56, 0.34, 0.4), quat_y(yaw), rng, mat=M_STONE, res=(2, 1, 2), round_r=0.03, rough=0.1,
             col_fn=rock_col(SANDST, dark_below=0.3), tile=0.8)
    # Spoil heap off to the right with fallen lumps, and baskets of broken stone + a pick.
    mound(g, (1.75, -0.1, 1.5), 0.9, 0.7, 0.55, rng, mat=M_EARTH, col_fn=lambda p, n: scale(SAND, 0.93), rings=5,
          seg=18, rough=0.25)
    for k in range(9):
        stone(g, (1.75 + rng.uniform(-0.9, 0.9), 0.05, 1.5 + rng.uniform(-0.7, 0.8)),
              (rng.uniform(0.08, 0.18), rng.uniform(0.06, 0.12), rng.uniform(0.08, 0.16)), rng, detail=1,
              col_fn=rock_col(SANDST, dark_below=0.5), tile=0.5)
    for x, z in ((0.55, 1.5), (0.95, 1.75)):
        basket(g, rng, (x, 0.0, z), fill=(0.8, 0.62, 0.42))
    pole(g, V(0.3, 0.03, 2.0), V(-0.4, 0.06, 2.25), 0.022, 0.02, rng, mat=M_TIMBER, col=BEAMC, sides=5, segs=1)
    lbox(g, V(-0.42, 0.08, 2.25), (0.04, 0.05, 0.42), quat_y(0.33), M_IRON, IRON, tile=0.3)
    jar(g, rng, (1.4, 0.0, -0.9), s=1.15)
    return b


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
    "rival_farm": rival_farm,
    "rival_lumber": rival_lumber,
    "rival_mine": rival_mine,
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
