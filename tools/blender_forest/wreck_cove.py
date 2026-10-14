"""Wreck Cove set-pieces -> wreck_cove.glb (src/wreck_cove.rs).

The Crown ship that brought the hero to the island, driven onto the sand spit of Wreck Cove in the
storm the night before the game opens (campaign master spec §6.1). A FRESH wreck, not a skeleton:
a carvel-built two-masted carrack heeled over on her port bilge, bow run up the sand, stern settled
in the shallows. The reef stove in her starboard bilge (a ragged breach, frames and the dark hold
showing); the mainmast snapped at the partners and went over the port side, yard and sail with it,
and lies half in the surf; the foremast still stands, raked with the hull, its yard askew and the
foresail in rags. Crimson sheer strake and a gilt crown on the sterncastle front: a Crown ship.

    cove_wreck    the ship. Model-local origin = the keel amidships after the heel, y = 0 the sand
                  line (the lowest bilge is buried ~0.5); bow toward +Z, the deck (port side down)
                  faces -X, so the planner turns -X toward the beach.
    cove_boat     the ship's boat, beached upright and half full of sand, an oar across the thwarts.
    cove_spill_a  cargo thrown up by the sea: casks, a burst crate, a coil of hawser, a torn sail.
    cove_spill_b  a broken spar, a sea chest burst open, planks, a lantern, a cask on its side.

Real scale (hero ~1.3u, 1u ~ 1.35 m): the ship is ~17u (23 m) stem to stern.

    blender -b --factory-startup --python tools/blender_forest/wreck_cove.py
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
from wayside_models import (M_CLOTH, M_IRON, M_PLANK, M_TIMBER, V, beam, board, bounds, lashing, lbox, mix, pole,  # noqa: E402
                            scale, smoothstep, tube, Noise, BOARD_CENTRES)
from stories_cold import MATS, crate, disc  # noqa: E402
from castaways import cask, lantern, oar  # noqa: E402

TAR = (0.3, 0.24, 0.19)
OAK = (0.8, 0.66, 0.5)
OAK_RAW = (0.95, 0.84, 0.68)
CRIMSON = (0.66, 0.13, 0.09)
GOLD = (0.95, 0.72, 0.3)
ROPE_TAR = (0.32, 0.26, 0.2)
ROPE = (0.82, 0.7, 0.5)
SAIL = (1.0, 0.95, 0.84)
IRON = (0.32, 0.3, 0.29)
RUST = (0.55, 0.36, 0.25)
WEED = (0.22, 0.27, 0.14)
HOLD = (0.06, 0.05, 0.045)


# ─────────────────────────────────────────────────────────────── hull
class Hull:
    """A round-bilged carvel hull in its own upright frame (keel amidships at the origin, bow +Z,
    up +Y); `xf` maps it into model space (heel / pitch / settle)."""

    def __init__(self, L, B, D, sheer=(0.7, 1.0), rocker=(0.5, 0.3), fullness=(2.2, 3.0), rake=(1.4, 0.5),
                 stern_top=None, transom=-1.0, xf=lambda p: p):
        self.L, self.B, self.D = L, B, D
        self.sheer, self.rocker, self.full, self.rake = sheer, rocker, fullness, rake
        # Aft, the upper sections are fuller than the run below (`stern_top` exponent at the sheer),
        # so the hull ends in a broad flat TRANSOM at t = `transom` over a fine tuck.
        self.stern_top = stern_top if stern_top is not None else fullness[1]
        self.transom = transom
        self.xf = xf

    def hb(self, t, u=1.0):
        if t > 0:
            p = self.full[0]
        else:
            p = self.full[1] + (self.stern_top - self.full[1]) * u * u
        return self.B / 2 * max(0.0, 1 - abs(t) ** p) ** 0.5

    def ykeel(self, t):
        return self.rocker[0] * max(0.0, t) ** 3 + self.rocker[1] * max(0.0, -t) ** 3

    def ysheer(self, t):
        return self.D + self.sheer[0] * max(0.0, t) ** 2 + self.sheer[1] * max(0.0, -t) ** 2

    def local(self, t, u, side):
        th = u * math.pi / 2
        yk, ys = self.ykeel(t), self.ysheer(t)
        x = side * self.hb(t, u) * math.sin(th) ** 0.75
        y = yk + (ys - yk) * (1 - math.cos(th))
        rk = self.rake[0] if t > 0 else self.rake[1]
        z = t * self.L / 2 + math.copysign(rk * u ** 1.5 * abs(t) ** 3, t)
        return V(x, y, z)

    def normal(self, t, u, side):
        e = 1e-3
        p = self.local(t, u, side)
        dt = self.local(min(t + e, 1.0), u, side) - self.local(max(t - e, -1.0), u, side)
        du = self.local(t, min(u + e, 1.0), side) - self.local(t, max(u - e, 0.0), side)
        n = dt.cross(du)
        if n.length < 1e-12:
            return V(side, 0, 0)
        n.normalize()
        if n.dot(p - V(0, (self.ykeel(t) + self.ysheer(t)) * 0.5, p.z)) < 0:
            n = -n
        return n

    def at(self, t, u, side, off=0.0):
        """Upright-frame point pushed `off` along the outward normal."""
        return self.local(t, u, side) + self.normal(t, u, side) * off

    def u_at_height(self, t, y):
        """Girth parameter where the side reaches upright height `y`."""
        yk, ys = self.ykeel(t), self.ysheer(t)
        f = max(0.0, min(1.0, (y - yk) / max(ys - yk, 1e-6)))
        return math.acos(1 - f) / (math.pi / 2)


def quad(g, pts, uvs, cols, mat, outward):
    n = (pts[1] - pts[0]).cross(pts[3] - pts[0])
    if n.length < 1e-12:
        n = (pts[2] - pts[1]).cross(pts[0] - pts[1])
    if n.length < 1e-12:
        return
    if n.dot(outward) < 0:
        pts, uvs, cols = pts[::-1], uvs[::-1], cols[::-1]
        n = -n
    g.poly(pts, uvs, [n.normalized()] * 4, cols, mat)


def wet(col, y, line=0.35, weed=0.0):
    """Darken + green a colour below the high-water line (model-space y)."""
    w = 1.0 - smoothstep(line - 0.4, line + 0.15, y)
    c = scale(col, 1.0 - 0.45 * w)
    return mix(c, WEED, w * weed)


def plank_hull(g, rng, h, ts, nstrake, col_fn, hole=None, inner=True, thick=0.07, inner_col=None):
    """Carvel planking over `h` on t-stations `ts` and `nstrake` strakes per side. `col_fn(t, u, side,
    p_model)` colours the outside; `hole(t, u, side)` -> True punches a cell out. Returns the set of
    holed cells (for splinters / frames)."""
    nz = Noise(rng, 3, 0.9)
    centres = BOARD_CENTRES[M_TIMBER]
    holed = set()
    for side in (-1, 1):
        for k in range(nstrake):
            u0, u1 = k / nstrake, (k + 1) / nstrake
            vc = centres[(k * 2 + (side > 0)) % 5]
            shade = 1.0 + rng.uniform(-0.07, 0.07)
            for i in range(len(ts) - 1):
                t0, t1 = ts[i], ts[i + 1]
                tm, um = (t0 + t1) / 2, (u0 + u1) / 2
                if hole is not None and hole(tm, um, side):
                    holed.add((i, k, side))
                    continue
                corners = [(t0, u0), (t1, u0), (t1, u1), (t0, u1)]
                pts = [h.xf(h.at(t, u, side, 0.0)) for t, u in corners]
                out_n = h.xf(h.at(tm, um, side, 1.0)) - h.xf(h.at(tm, um, side, 0.0))
                uvs = [(vc + (u - um) * nstrake * 0.16, t * h.L / 2 / 4.5) for t, u in corners]
                cols = []
                for (t, u), p in zip(corners, pts):
                    c = scale(col_fn(t, u, side, p), shade * (1.0 + 0.08 * nz(p)))
                    # Carvel seam: each plank's lower edge a touch darker (caulked seam).
                    if u == u0:
                        c = scale(c, 0.82)
                    cols.append(c)
                quad(g, pts, uvs, cols, M_TIMBER, out_n)
                if inner:
                    ipts = [h.xf(h.at(t, u, side, -thick)) for t, u in corners]
                    ic = inner_col(um) if inner_col else scale(OAK, 0.4)
                    quad(g, ipts, uvs, [ic] * 4, M_TIMBER, -out_n)
    return holed


# ─────────────────────────────────────────────────────────────── the ship
HEEL = 0.13      # rad, port side down (kept walkable: the deck is a play space)
PITCH = 0.035    # rad, bow up
SHIP = dict(L=16.5, B=5.6, D=3.0, sheer=(0.95, 0.9), rocker=(0.6, 0.4), fullness=(2.0, 2.4), rake=(1.7, 0.0),
            stern_top=9.0, transom=-0.93)
STERN_RISE = 2.05  # sterncastle: headroom for the great cabin under it (hero ~1.3u)
DECK_DROP = 0.6  # main deck below the sheer (the bulwark height)
NSTRAKE = 15


def ship_rot(p):
    q = quat_x(-PITCH) @ quat_z(HEEL)
    return q @ Vector(p)


def make_ship_xf():
    h = Hull(**SHIP)
    lo = min(ship_rot(h.local(t / 20, u / 10, s)).y for t in range(-18, 21) for u in range(11) for s in (-1, 1))
    shift = V(0, -lo - 0.55, 0)
    print(f"SHIP_SHIFT_Y {shift.y:.4f}")
    return lambda p: ship_rot(p) + shift


def t_stations(n, t0=-1.0):
    ts = [-1 + 2 * i / n for i in range(n + 1)]
    ts = [math.copysign(abs(t) ** 0.85, t) * 0.992 for t in ts]
    return sorted(set([t0] + [t for t in ts if t > t0 + 0.01]))


def ship_col(h):
    def f(t, u, side, p):
        if u < 0.5:
            c = mix(TAR, scale(TAR, 1.5), 0.3)
        elif u < 0.83:
            c = OAK
        else:
            c = mix(CRIMSON, scale(CRIMSON, 0.7), 0.3)
        return wet(c, p.y, line=0.45, weed=0.6 if u < 0.6 else 0.25)
    return f


def breach(t, u, side):
    """The reef's work: a ragged hole low in the starboard bilge, just abaft amidships."""
    if side < 0:
        return False
    d = ((t + 0.08) / 0.2) ** 2 + ((u - 0.33) / 0.2) ** 2
    rag = 0.25 * math.sin(t * 41.0 + u * 13.0) + 0.18 * math.sin(u * 29.0 - t * 17.0)
    return d + rag < 1.0


def port_bulwark_gone(t, u, side):
    """Where the falling mainmast took the port bulwark away."""
    return side < 0 and -0.1 < t < 0.12 and u > 0.86


def deck(g, rng, h, ts, y_drop, t0, t1, skip, col=OAK_RAW):
    """Deck planking between stations t0..t1 at `y_drop` below the sheer; `skip(t, x)` leaves a
    gap (hatch / broken boards). Boards run fore-and-aft."""
    lanes = 10
    for i in range(len(ts) - 1):
        a, b = ts[i], ts[i + 1]
        if b <= t0 or a >= t1:
            continue
        a, b = max(a, t0), min(b, t1)
        ya, yb = h.ysheer(a) - y_drop, h.ysheer(b) - y_drop
        wa = abs(h.local(a, h.u_at_height(a, ya), 1).x)
        wb = abs(h.local(b, h.u_at_height(b, yb), 1).x)
        za, zb = h.local(a, 1, 1).z, h.local(b, 1, 1).z
        za, zb = a * h.L / 2, b * h.L / 2
        for j in range(lanes):
            fa, fb = -1 + 2 * j / lanes, -1 + 2 * (j + 1) / lanes
            tm, xm = (a + b) / 2, (fa + fb) / 2 * (wa + wb) / 2
            if skip(tm, xm):
                continue
            pts = [V(fa * wa, ya, za), V(fb * wa, ya, za), V(fb * wb, yb, zb), V(fa * wb, yb, zb)]
            mp = [h.xf(p) for p in pts]
            k = 1.0 + 0.09 * math.sin(j * 2.3 + i * 0.7)
            c = scale(col, k)
            uvs = [(BOARD_CENTRES[M_PLANK][j % 5] + (q.x - xm) * 0.4, q.z / 1.8) for q in pts]
            up = h.xf(V(0, 1, 0)) - h.xf(V(0, 0, 0))
            quad(g, mp, uvs, [wet(c, p.y, 0.3) for p in mp], M_PLANK, up)


def castle(g, rng, h, ts, t0, t1, rise, front_t, door=False, crown=False):
    """A raised castle deck over t0..t1: planked walls from the sheer up `rise`, a platform on top,
    a front bulkhead at `front_t` (optionally with a door and the gilt crown), a rail of posts."""
    sel = [t for t in ts if t0 <= t <= t1]
    sel = sorted(set([t0] + sel + [t1]))
    for side in (-1, 1):
        for i in range(len(sel) - 1):
            a, b = sel[i], sel[i + 1]
            pa, pb = h.at(a, 1.0, side, 0.0), h.at(b, 1.0, side, 0.0)
            pts = [pa, pb, pb + V(0, rise, 0), pa + V(0, rise, 0)]
            mp = [h.xf(p) for p in pts]
            uvs = [((p.y - pa.y) * 0.4, p.z / 4.5) for p in pts]
            col = [CRIMSON, CRIMSON, scale(CRIMSON, 1.15), scale(CRIMSON, 1.15)]
            quad(g, mp, uvs, col, M_TIMBER, h.xf(V(side, 0, 0)) - h.xf(V(0, 0, 0)))
            quad(g, [h.xf(p - V(side * 0.07, 0, 0)) for p in pts], uvs, [scale(OAK, 0.5)] * 4, M_TIMBER,
                 h.xf(V(-side, 0, 0)) - h.xf(V(0, 0, 0)))
        rail = [h.xf(h.at(t, 1.0, side, 0.0) + V(-side * 0.03, rise + 0.05, 0)) for t in sel]
        beam(g, rail, 0.12, 0.1, mat=M_PLANK, col=scale(OAK, 0.8), rng=rng)
        # Open rail above: posts and a top rail.
        for t in sel[::2]:
            p = h.at(t, 1.0, side, 0.0) + V(-side * 0.03, rise, 0)
            beam(g, [h.xf(p), h.xf(p + V(0, 0.55, 0))], 0.07, 0.07, mat=M_PLANK, col=OAK, rng=rng)
        top = [h.xf(h.at(t, 1.0, side, 0.0) + V(-side * 0.03, rise + 0.58, 0)) for t in sel]
        beam(g, top, 0.09, 0.07, mat=M_PLANK, col=OAK, rng=rng)
    # Platform.
    for i in range(len(sel) - 1):
        a, b = sel[i], sel[i + 1]
        wa, wb = h.hb(a) * 0.98, h.hb(b) * 0.98
        ya, yb = h.ysheer(a) + rise, h.ysheer(b) + rise
        za, zb = h.at(a, 1.0, 1).z, h.at(b, 1.0, 1).z
        for j in range(6):
            fa, fb = -1 + j / 3, -1 + (j + 1) / 3
            pts = [V(fa * wa, ya, za), V(fb * wa, ya, za), V(fb * wb, yb, zb), V(fa * wb, yb, zb)]
            uvs = [(BOARD_CENTRES[M_PLANK][j % 5] + q.x * 0.3, q.z / 1.8) for q in pts]
            quad(g, [h.xf(p) for p in pts], uvs, [scale(OAK_RAW, 0.9 + 0.05 * (j % 2))] * 4, M_PLANK,
                 h.xf(V(0, 1, 0)) - h.xf(V(0, 0, 0)))
    # Front bulkhead (faces amidships): from the main deck up to the platform.
    w = h.hb(front_t) * 0.98
    y0 = h.ysheer(front_t) - DECK_DROP
    y1 = h.ysheer(front_t) + rise
    z = h.at(front_t, 1.0, 1).z
    face = V(0, 0, 1 if front_t < 0 else -1)
    nb = 9
    for j in range(nb):
        x0, x1 = -w + 2 * w * j / nb, -w + 2 * w * (j + 1) / nb
        if door and j == nb // 2:
            # Door: a dark opening, its leaf hanging open on one hinge.
            pts = [V(x0, y0, z), V(x1, y0, z), V(x1, y0 + 1.25, z), V(x0, y0 + 1.25, z)]
            quad(g, [h.xf(p - face * 0.05) for p in pts], [(0, 0)] * 4, [HOLD] * 4, M_PLANK, h.xf(face) - h.xf(V(0, 0, 0)))
            pts = [V(x0, y0 + 1.25, z), V(x1, y0 + 1.25, z), V(x1, y1, z), V(x0, y1, z)]
            hinge = V(x0, y0, z)
            leaf = h.xf(hinge + V(0, 0.62, 0) + quat_y(-1.9 * face.z) @ V((x1 - x0) / 2, 0, 0))
            lbox(g, leaf, (x1 - x0, 1.2, 0.06), quat_x(-PITCH) @ quat_z(HEEL) @ quat_y(-1.9 * face.z), M_PLANK,
                 scale(OAK, 0.8), tile=1.0)
        else:
            pts = [V(x0, y0, z), V(x1, y0, z), V(x1, y1, z), V(x0, y1, z)]
        uvs = [(BOARD_CENTRES[M_PLANK][j % 5] + (q.x - (x0 + x1) / 2) * 0.4, q.y / 1.6) for q in pts]
        quad(g, [h.xf(p) for p in pts], uvs, [scale(OAK, 0.95 + 0.06 * math.sin(j * 1.9))] * 4, M_PLANK,
             h.xf(face) - h.xf(V(0, 0, 0)))
    if crown:
        # A gilt crown carved over the door: a band and five points.
        c = V(0, y1 - 0.38, z) + face * 0.06
        q = quat_x(-PITCH) @ quat_z(HEEL)
        lbox(g, h.xf(c), (0.7, 0.14, 0.05), q, M_IRON, GOLD, tile=0.5)
        for k in range(5):
            x = -0.3 + 0.15 * k
            hk = 0.22 if k % 2 == 0 else 0.15
            lbox(g, h.xf(c + V(x, 0.07 + hk / 2, 0)), (0.07, hk, 0.05), q, M_IRON, GOLD, tile=0.5)
        lbox(g, h.xf(c - V(0, 0.16, 0)), (0.9, 0.09, 0.04), q, M_IRON, scale(GOLD, 0.8), tile=0.5)


def transom(g, rng, h):
    """The flat stern: the hull section at `h.transom` closed with horizontal planking (tar below the
    wale, oak, the crimson strake), a sternpost down its middle, and above the sheer the back wall
    of the great cabin with three leaded stern windows, one stove in."""
    tt = h.transom
    out = h.xf(V(0, 0, -1)) - h.xf(V(0, 0, 0))
    col = ship_col(h)
    for k in range(NSTRAKE):
        u0, u1 = k / NSTRAKE, (k + 1) / NSTRAKE
        pts = [h.at(tt, u0, -1), h.at(tt, u0, 1), h.at(tt, u1, 1), h.at(tt, u1, -1)]
        mp = [h.xf(p) for p in pts]
        uvs = [(BOARD_CENTRES[M_PLANK][k % 5] + (p.y - pts[0].y) * 0.4, p.x / 4.5) for p in pts]
        cols = [scale(col(tt, u, 1, q), 0.92 if u == u0 else 1.0) for u, q in zip((u0, u0, u1, u1), mp)]
        quad(g, mp, uvs, cols, M_TIMBER, out)
    sp = [h.xf(V(0, h.ykeel(tt) + (h.ysheer(tt) - h.ykeel(tt)) * f / 6, h.local(tt, 0.0, 1).z - 0.1)) for f in range(7)]
    beam(g, sp, 0.22, 0.2, up=tuple(out), mat=M_PLANK, col=scale(TAR, 1.3), rng=rng)
    # Great-cabin back wall over the sheer.
    w = h.hb(tt) * 0.98
    y0, y1 = h.ysheer(tt), h.ysheer(tt) + STERN_RISE
    z = h.at(tt, 1.0, 1).z
    wins = [(-1.15, 0.0), (0.0, 0.0), (1.15, 1.0)]  # (x, broken)
    nb = 12
    for j in range(nb):
        x0, x1 = -w + 2 * w * j / nb, -w + 2 * w * (j + 1) / nb
        rows = [(y0, y0 + 0.75), (y0 + 1.55, y1)]
        if not any(abs((x0 + x1) / 2 - wx) < 0.42 for wx, _ in wins):
            rows = [(y0, y1)]
        for (ya, yb) in rows:
            pts = [V(x0, ya, z), V(x1, ya, z), V(x1, yb, z), V(x0, yb, z)]
            uvs = [((p.y - ya) * 0.4, p.x / 4.5) for p in pts]
            quad(g, [h.xf(p) for p in pts], uvs, [mix(CRIMSON, OAK, 0.35)] * 4, M_TIMBER, out)
    q = quat_x(-PITCH) @ quat_z(HEEL)
    for wx, broken in wins:
        c = V(wx, y0 + 1.15, z)
        quad(g, [h.xf(c + V(-0.42, -0.4, 0.06)), h.xf(c + V(0.42, -0.4, 0.06)), h.xf(c + V(0.42, 0.4, 0.06)),
                 h.xf(c + V(-0.42, 0.4, 0.06))], [(0, 0)] * 4, [HOLD] * 4, M_PLANK, out)
        for dy in (-0.42, 0.42):
            lbox(g, h.xf(c + V(0, dy, -0.03)), (0.98, 0.1, 0.12), q, M_PLANK, scale(OAK, 0.6), tile=0.6)
        for dx in (-0.45, 0.45):
            lbox(g, h.xf(c + V(dx, 0, -0.03)), (0.1, 0.9, 0.12), q, M_PLANK, scale(OAK, 0.6), tile=0.6)
        if not broken:
            # Leading: a lattice of thin cames across the dark glazing.
            for k in range(-2, 3):
                lbox(g, h.xf(c + V(k * 0.16, 0, -0.01)), (0.02, 0.78, 0.02), q, M_IRON, IRON, tile=0.3)
                lbox(g, h.xf(c + V(0, k * 0.16, -0.01)), (0.82, 0.02, 0.02), q, M_IRON, IRON, tile=0.3)
    # Gilt moulding along the top of the stern.
    rail = [h.xf(V(-w + 2 * w * k / 8, y1 + 0.04, z - 0.03)) for k in range(9)]
    beam(g, rail, 0.12, 0.1, mat=M_IRON, col=scale(GOLD, 0.8), rng=rng)


def cove_wreck(rng):
    xf = make_ship_xf()
    h = Hull(**SHIP, xf=xf)
    ts = t_stations(40, h.transom)
    up = lambda: h.xf(V(0, 1, 0)) - h.xf(V(0, 0, 0))  # noqa: E731
    b = Builder()
    g = G(b)

    def hole(t, u, side):
        return breach(t, u, side) or port_bulwark_gone(t, u, side)

    def inner_col(u):
        return scale(OAK, 0.18 + 0.3 * u)

    holed = plank_hull(g, rng, h, ts, NSTRAKE, ship_col(h), hole=hole, inner_col=inner_col)

    # Wale: a heavy tarred rubbing strake along each side.
    for side in (-1, 1):
        wale = [h.xf(h.at(t, 0.84, side, 0.06)) for t in [-0.97 + 1.94 * i / 24 for i in range(25)]]
        beam(g, wale, 0.18, 0.12, mat=M_PLANK, col=scale(TAR, 1.2), rng=rng)
        cap = []
        for t in [-0.97 + 1.94 * i / 24 for i in range(25)]:
            if port_bulwark_gone(t, 0.95, side):
                if cap:
                    beam(g, cap, 0.14, 0.08, mat=M_PLANK, col=OAK, rng=rng, jag=(0.0, 0.4))
                cap = []
                continue
            cap.append(h.xf(h.at(t, 1.0, side, -0.02) + V(0, 0.04, 0)))
        if len(cap) > 1:
            beam(g, cap, 0.14, 0.08, mat=M_PLANK, col=OAK, rng=rng, jag=(0.4, 0.0) if side < 0 else (0.0, 0.0))
    # Keel, stem and sternpost.
    keel = [h.xf(h.at(t, 0.0, 1, 0.0) - V(0, 0.08, 0)) for t in [-0.99 + 1.98 * i / 16 for i in range(17)]]
    beam(g, keel, 0.22, 0.2, up=tuple(h.xf(V(1, 0, 0)) - h.xf(V(0, 0, 0))), mat=M_PLANK, col=wet(TAR, -1, weed=0.5), rng=rng)
    post = [h.xf(h.local(0.995, f / 8, 1) + V(0, 0, 0.08)) for f in range(9)]
    post.append(post[-1] + (post[-1] - post[-2]).normalized() * 0.45)
    beam(g, post, 0.2, 0.24, up=tuple(h.xf(V(1, 0, 0)) - h.xf(V(0, 0, 0))), mat=M_PLANK, col=scale(TAR, 1.3), rng=rng)
    transom(g, rng, h)

    # Frames showing in the breach, and splintered plank ends around it.
    for t in [-0.3 + 0.045 * k for k in range(11)]:
        us = [f / 12 for f in range(1, 13)]
        rib = [h.xf(h.at(t, u, 1, -0.12)) for u in us if u < 0.8]
        beam(g, rib, 0.13, 0.15, mat=M_PLANK, col=scale(OAK, 0.45), rng=rng)
    for (i, k, side) in holed:
        if side < 0:
            continue
        for di in (-1, 1):
            j = i + di
            if 0 <= j < len(ts) - 1 and (j, k, side) not in holed:
                # The plank on the hole's edge breaks off ragged, sprung outward.
                t_edge = ts[i + 1] if di < 0 else ts[i]
                um = (k + 0.5) / NSTRAKE
                p0 = h.xf(h.at(t_edge, um, side, 0.0))
                d = h.xf(h.at(t_edge - di * 0.06, um, side, 0.1 + rng.uniform(0, 0.15))) - p0
                n = h.xf(h.at(t_edge, um, side, 1.0)) - p0
                board(g, p0 + d * 0.5, d, n, d.length, 0.22, 0.06, col=wet(TAR, p0.y, weed=0.5), rng=rng,
                      jag=(0.0, 0.5))
    # The hold seen through the breach: ballast stones and a stove cask on the bilge.
    for k in range(9):
        t = -0.2 + rng.uniform(0, 0.25)
        p = h.xf(V(rng.uniform(-0.6, 0.9), h.ykeel(t) + 0.25, t * h.L / 2))
        lbox(g, p, (rng.uniform(0.3, 0.5), 0.25, rng.uniform(0.3, 0.5)), quat_y(rng.uniform(0, 3)), M_PLANK, HOLD, tile=0.5)

    # Main deck with its hatch, and the boards the mast tore up.
    def deck_skip(t, x):
        if -0.16 < t < 0.0 and abs(x) < 0.8:
            return True  # main hatch
        if -0.06 < t < 0.14 and x < -0.6 and math.sin(x * 9 + t * 40) > -0.2:
            return True  # boards torn up where the mast went over the side
        return False

    deck(g, rng, h, ts, DECK_DROP, h.transom, 0.74, deck_skip)
    # Hatch coaming and the black hold under it.
    for (a, b2) in (((-0.16, -0.8), (0.0, -0.8)), ((-0.16, 0.8), (0.0, 0.8)), ((-0.16, -0.8), (-0.16, 0.8)),
                    ((0.0, -0.8), (0.0, 0.8))):
        pa = V(a[1], h.ysheer(a[0]) - DECK_DROP + 0.12, a[0] * h.L / 2)
        pb = V(b2[1], h.ysheer(b2[0]) - DECK_DROP + 0.12, b2[0] * h.L / 2)
        beam(g, [h.xf(pa), h.xf(pb)], 0.14, 0.24, mat=M_PLANK, col=scale(OAK, 0.7), rng=rng)
    hy = h.ysheer(-0.08) - DECK_DROP - 1.4
    pts = [V(-0.8, hy, -0.16 * h.L / 2), V(0.8, hy, -0.16 * h.L / 2), V(0.8, hy, 0.0), V(-0.8, hy, 0.0)]
    quad(g, [h.xf(p) for p in pts], [(0, 0)] * 4, [HOLD] * 4, M_PLANK, up())
    # Hatch cover boards, thrown about the deck.
    for k in range(3):
        c = h.xf(V(rng.uniform(0.4, 1.4), h.ysheer(0.2) - DECK_DROP + 0.05, (0.15 + 0.08 * k) * h.L / 2))
        board(g, c, h.xf(quat_y(rng.uniform(-0.5, 0.5)) @ V(0, 0, 1)) - h.xf(V(0, 0, 0)), up(), 1.5, 0.45, 0.06,
              col=scale(OAK, 0.85), rng=rng)

    castle(g, rng, h, ts, h.transom, -0.55, STERN_RISE, -0.55, door=True, crown=True)
    castle(g, rng, h, ts, 0.74, 0.97, 1.15, 0.74)

    # Mainmast: snapped a man's height above the deck, splintered.
    deck_y = h.ysheer(0.0) - DECK_DROP
    mb = h.xf(V(0, h.ykeel(0) + 0.3, 0.0))
    mt = h.xf(V(0, deck_y + 1.9, 0.0))
    pole(g, mb, mt, 0.27, 0.25, rng, mat=M_PLANK, col=scale(OAK, 0.85), sides=12, wobble=0.0, tile=1.2)
    for k in range(5):
        a = 2 * math.pi * k / 5 + rng.uniform(-0.3, 0.3)
        o = h.xf(V(math.cos(a) * 0.14, deck_y + 1.85, math.sin(a) * 0.14)) - h.xf(V(0, deck_y + 1.85, 0))
        tip = h.xf(V(math.cos(a) * 0.1, deck_y + 1.9 + rng.uniform(0.35, 0.8), math.sin(a) * 0.1))
        beam(g, [mt + o, tip], 0.1, 0.08, mat=M_PLANK, col=OAK_RAW, rng=rng, point=0.8)
    lbox(g, h.xf(V(0, deck_y + 0.1, 0.0)), (0.9, 0.2, 0.9), quat_x(-PITCH) @ quat_z(HEEL), M_PLANK, scale(OAK, 0.6))

    # Mainmast top section, gone over the port side: heel on the torn bulwark, top in the surf.
    m0 = h.xf(V(-h.B / 2 + 0.2, h.ysheer(0.02) + 0.15, 0.3))
    m1 = V(m0.x - 9.5, -0.3, m0.z + 2.2)
    m0b = m0 + (m1 - m0).normalized() * -0.4
    pole(g, m0b, m1, 0.24, 0.13, rng, mat=M_PLANK, col=scale(OAK, 0.8), sides=11, wobble=0.0, tile=1.4,
         col_fn=None)
    beam(g, [m0b, m0b - (m1 - m0).normalized() * 0.5], 0.22, 0.2, mat=M_PLANK, col=OAK_RAW, rng=rng, point=0.6)
    # Its yard, across the spar near the top, and the mainsail dragged under it into the shallows.
    yc = m0.lerp(m1, 0.72)
    yd = Vector((0.25, 0.0, 1.0)).normalized()
    y0, y1 = yc - yd * 3.4 + V(0, 0.05, 0), yc + yd * 3.2 + V(0, -0.1, 0)
    y0.y = max(y0.y, -0.25)
    y1.y = max(y1.y, -0.3)
    pole(g, y0, y1, 0.11, 0.09, rng, mat=M_PLANK, col=scale(OAK, 0.75), sides=9, wobble=0.0)
    grid = []
    NI, NJ = 13, 8
    for i in range(NI):
        f = i / (NI - 1)
        top = y0.lerp(y1, f)
        row = []
        for j in range(NJ):
            v = j / (NJ - 1)
            # Spread seaward (+X model -> away from the hull's heel side) and lying in folds.
            p = top + V(2.6 * v + 0.3 * math.sin(f * 7 + v * 3), 0, 0.5 * v * math.sin(f * 5.0))
            p.y = max(-0.33, top.y * (1 - v) - 0.36 * v) + 0.12 * math.sin(f * 11 + v * 6) * v * (1 - v) * 4
            if v > 0.65 and (math.sin(f * 23.0) > 0.4):
                p.x -= 0.6 * (v - 0.65)  # ragged foot
            row.append(p)
        grid.append(row)
    if (grid[1][0] - grid[0][0]).cross(grid[0][1] - grid[0][0]).y < 0:
        grid = grid[::-1]
    sheet(g, grid, M_CLOTH, lambda a, c: wet(mix(SAIL, scale(SAIL, 0.75), 0.5 + 0.5 * math.sin(a * 17 + c * 5)),
                                          -0.3 + 0.6 * (1 - c), 0.0, weed=0.2), tile=1.2, double=True)
    # Shrouds of the fallen mast trailing from the stump to it.
    for k in range(4):
        a = h.xf(h.at(0.05 + 0.04 * k, 1.0, -1, 0.15))
        bpt = m0.lerp(m1, 0.55 + 0.08 * k)
        mid = a.lerp(bpt, 0.5) - V(0, 0.6, 0)
        mid.y = max(mid.y, -0.32)
        tube(g, [a, mid, bpt], [0.025] * 3, 4, M_CLOTH, ROPE_TAR, tile=0.4, cap=False)

    # Foremast: still standing, raked with the hull; its yard canted and the foresail in rags.
    ft = 0.6
    fz = ft * h.L / 2
    fdeck = h.ysheer(ft) - DECK_DROP
    f0 = h.xf(V(0, h.ykeel(ft) + 0.4, fz))
    f1 = h.xf(V(0, fdeck + 8.2, fz))
    pole(g, f0, f1, 0.22, 0.12, rng, mat=M_PLANK, col=scale(OAK, 0.85), sides=11, wobble=0.0, tile=1.6)
    lbox(g, h.xf(V(0, fdeck + 6.9, fz)), (0.9, 0.12, 0.9), quat_x(-PITCH) @ quat_z(HEEL), M_PLANK, scale(OAK, 0.7))
    yq = quat_x(-PITCH) @ quat_z(HEEL)
    ya = h.xf(V(-2.9, fdeck + 6.3, fz)) + yq @ V(0, -0.9, 0)
    yb = h.xf(V(2.9, fdeck + 6.3, fz)) + yq @ V(0, 0.6, 0)
    pole(g, ya, yb, 0.09, 0.09, rng, mat=M_PLANK, col=scale(OAK, 0.8), sides=8, wobble=0.0)
    # Foresail rags hanging off the yard (head still bent on, the rest blown out).
    grid = []
    NI, NJ = 12, 6
    for i in range(NI):
        f = i / (NI - 1)
        top = ya.lerp(yb, f) + V(0, -0.05, 0)
        drop = 1.2 + 2.3 * (0.5 + 0.5 * math.sin(f * 9.0 + 1.0)) * (0.35 + 0.65 * math.sin(math.pi * f))
        row = []
        for j in range(NJ):
            v = j / (NJ - 1)
            p = top + V(0.25 * math.sin(v * 3 + f * 6) * v, -drop * v, 0.35 * v * v)
            row.append(p)
        grid.append(row)
    if (grid[1][0] - grid[0][0]).cross(grid[0][1] - grid[0][0]).z > 0:
        grid = grid[::-1]
    sheet(g, grid, M_CLOTH, lambda a, c: mix(SAIL, scale(SAIL, 0.7), 0.4 + 0.4 * math.sin(a * 13 + c * 4)), tile=1.3,
          double=True)
    # Fore shrouds: three a side to the channels; the starboard aftmost parted and hanging.
    for side in (-1, 1):
        for k in range(3):
            a = h.xf(V(0, fdeck + 6.8, fz))
            bt = ft - 0.1 + 0.07 * k
            bpt = h.xf(h.at(bt, 0.97, side, 0.2))
            if side > 0 and k == 0:
                mid = a.lerp(bpt, 0.5)
                tube(g, [a, a.lerp(mid, 0.5) + V(0.1, -0.4, 0), a.lerp(mid, 0.6) + V(0.2, -2.2, 0)], [0.022] * 3, 4,
                     M_CLOTH, ROPE_TAR, tile=0.4, cap=False)
                continue
            tube(g, [a, bpt], [0.022, 0.022], 4, M_CLOTH, ROPE_TAR, tile=0.4, cap=False)
            lbox(g, bpt, (0.16, 0.16, 0.16), yq, M_PLANK, scale(OAK, 0.5), tile=0.3)  # deadeye block
    # Bowsprit and the forestay.
    bs0 = h.xf(V(0, h.ysheer(0.9) - 0.2, 0.86 * h.L / 2))
    bs1 = h.xf(V(0, h.ysheer(1.0) + 1.7, h.L / 2 + 3.8))
    pole(g, bs0, bs1, 0.17, 0.09, rng, mat=M_PLANK, col=scale(OAK, 0.8), sides=9, wobble=0.0)
    tube(g, [h.xf(V(0, fdeck + 7.6, fz)), bs1.lerp(bs0, 0.08)], [0.03, 0.03], 4, M_CLOTH, ROPE_TAR, tile=0.4, cap=False)
    # Rudder, unshipped from its lower pintle and swung hard over, hanging off the sternpost.
    tt = h.transom
    zs = h.local(tt, 0.0, 1).z - 0.12
    y_lo, y_hi = h.ykeel(tt) + 0.1, h.ysheer(tt) - 0.4
    rq = quat_x(-PITCH) @ quat_z(HEEL) @ quat_y(0.5)
    hinge = V(0, (y_lo + y_hi) / 2, zs)
    lbox(g, h.xf(hinge) + rq @ V(0, 0, -0.42), (0.16, y_hi - y_lo, 0.85), rq, M_PLANK,
         [wet(scale(TAR, 1.2), -1, weed=0.6), None, scale(TAR, 1.4)], tile=1.0, grain=1)
    # Bower anchor: let go too late, its cable from the hawse to the anchor half in the sand.
    hawse = h.xf(h.at(0.9, 0.82, -1, 0.05))
    an = V(hawse.x - 2.6, -0.12, hawse.z + 4.2)
    cable = [hawse, hawse.lerp(an, 0.35) + V(0, -0.55, 0), hawse.lerp(an, 0.7) + V(0, -0.85, 0), an + V(0.2, 0.08, -0.3)]
    for p in cable[1:]:
        p.y = max(p.y, -0.2)
    tube(g, cable, [0.06] * 4, 6, M_CLOTH, ROPE_TAR, tile=0.5, cap=False)
    aq = quat_y(0.6) @ quat_z(1.25)
    beam(g, [an + aq @ V(0, -0.2, 0), an + aq @ V(0, 1.9, 0)], 0.12, 0.12, mat=M_IRON, col=RUST, rng=rng)  # shank
    for s in (-1, 1):
        arm = [an + aq @ V(0, -0.2, 0), an + aq @ V(s * 0.5, -0.05, 0), an + aq @ V(s * 0.85, 0.4, 0)]
        beam(g, arm, 0.1, 0.1, mat=M_IRON, col=RUST, rng=rng, point=0.5)
    beam(g, [an + aq @ V(0, 1.7, -0.9), an + aq @ V(0, 1.7, 0.9)], 0.16, 0.16, mat=M_PLANK, col=scale(OAK, 0.6), rng=rng)  # stock
    # The survivors' gangway: two hatch boards laid from the torn port bulwark down to the sand,
    # cleated across, lashed at the top (the deck is a play space - src/wreck_cove.rs walks it).
    r0, r1 = ramp_ends(h)
    d = (r1 - r0).normalized()
    side = d.cross(V(0, 1, 0)).normalized()
    nrm = side.cross(d).normalized()
    if nrm.y < 0:
        nrm = -nrm
    for o in (-0.24, 0.24):
        board(g, (r0 + r1) / 2 + side * o + nrm * 0.03, d, nrm, (r1 - r0).length + 0.3, 0.46, 0.07,
              col=scale(OAK, 0.8 + 0.1 * o), rng=rng)
    for k in range(1, 8):
        c = r0.lerp(r1, k / 8) + nrm * 0.09
        board(g, c, side, nrm, 1.0, 0.07, 0.05, col=scale(OAK, 0.6), rng=rng)
    lashing(g, r0 + nrm * 0.05, tuple(side), 0.09, rng, turns=3)
    print(f"RAMP {r0.x:.3f},{r0.y:.3f},{r0.z:.3f} -> {r1.x:.3f},{r1.y:.3f},{r1.z:.3f}")
    return b


RAMP_T = -0.05  # station of the gangway in the torn port bulwark (forward of it, the fallen mast)


def ramp_ends(h):
    """Model-space ends of the gangway: top on the deck just inside the torn port bulwark, foot on
    the sand 4.6u out."""
    y = h.ysheer(RAMP_T) - DECK_DROP
    w = abs(h.local(RAMP_T, h.u_at_height(RAMP_T, y), 1).x)
    top = h.xf(V(-w + 0.35, y + 0.02, RAMP_T * h.L / 2))
    foot = V(top.x - 4.6, 0.02, top.z - 0.3)
    return top, foot


# ─────────────────────────────────────────────────────────────── the ship's boat
def cove_boat(rng):
    """The ship's boat, beached upright on the sand, half full of it, an oar across the thwarts.
    Bow +Z, base y = 0 the sand line."""
    h = Hull(L=4.6, B=1.55, D=0.75, sheer=(0.25, 0.15), rocker=(0.12, 0.05), fullness=(2.2, 2.6), rake=(0.25, 0.1))
    roll, pitch = 0.12, -0.04

    def xf(p):
        return quat_x(pitch) @ quat_z(roll) @ Vector(p) + V(0, -0.22, 0)

    h.xf = xf
    b = Builder()
    g = G(b)
    ts = t_stations(22)

    def col(t, u, side, p):
        c = OAK if u > 0.75 else mix(TAR, OAK, 0.35)
        return scale(c, 0.9) if u > 0.75 else c

    plank_hull(g, rng, h, ts, 7, col, inner_col=lambda u: scale(OAK, 0.45 + 0.25 * u), thick=0.04)
    for side in (-1, 1):
        rail = [h.xf(h.at(t, 1.0, side, -0.01) + V(0, 0.02, 0)) for t in [-0.95 + 1.9 * i / 12 for i in range(13)]]
        beam(g, rail, 0.07, 0.06, mat=M_PLANK, col=scale(OAK, 0.75), rng=rng)
    keel = [h.xf(h.at(t, 0.0, 1, 0.0) - V(0, 0.04, 0)) for t in [-0.98 + 1.96 * i / 10 for i in range(11)]]
    beam(g, keel, 0.08, 0.09, mat=M_PLANK, col=scale(TAR, 1.2), rng=rng)
    for t in (-0.6, -0.3, 0.0, 0.3, 0.6):
        rib = [h.xf(h.at(t, abs(f), 1 if f >= 0 else -1, -0.05)) for f in [-1 + 2 * i / 10 for i in range(11)]]
        beam(g, rib, 0.05, 0.05, mat=M_PLANK, col=scale(OAK, 0.6), rng=rng)
    for t in (-0.45, 0.1, 0.55):
        y = h.ysheer(t) - 0.22
        w = abs(h.local(t, h.u_at_height(t, y), 1).x) * 0.97
        a, c = h.xf(V(-w, y, t * h.L / 2)), h.xf(V(w, y, t * h.L / 2))
        board(g, (a + c) / 2, c - a, h.xf(V(0, 1, 0)) - h.xf(V(0, 0, 0)), (c - a).length, 0.24, 0.05, col=scale(OAK, 0.8),
              rng=rng)
    # Sand blown and washed in: a low drift over the bottom boards, banked toward the bow.
    nz = Noise(rng, 3, 1.3)
    grid = []
    for i in range(11):
        t = -0.8 + 1.6 * i / 10
        y = h.ykeel(t) + 0.28 + 0.1 * smoothstep(-0.8, 0.8, t)
        w = abs(h.local(t, h.u_at_height(t, y), 1).x) * 0.99
        row = []
        for j in range(7):
            x = -w + 2 * w * j / 6
            p = V(x, y + 0.04 * math.sin(i * 1.7 + j), t * h.L / 2)
            row.append(h.xf(p))
        grid.append(row)
    if (grid[1][0] - grid[0][0]).cross(grid[0][1] - grid[0][0]).y < 0:
        grid = grid[::-1]
    sheet(g, grid, M_PLANK, lambda a, c: scale((0.78, 0.68, 0.5), 0.92 + 0.08 * nz(V(a * 3, 0, c * 3))), tile=1.5)
    oar(g, rng, h.xf(V(-1.0, h.ysheer(0.1) + 0.05, 0.6)), h.xf(V(1.6, h.ysheer(-0.3) - 0.05, -1.2)))
    oar(g, rng, V(1.3, 0.04, 1.6), V(2.1, 0.03, -0.9))
    return b


# ─────────────────────────────────────────────────────────────── spill
def hawser_coil(g, rng, c, r=0.45, turns=5):
    pts, radii = [], []
    for k in range(turns * 16 + 1):
        a = 2 * math.pi * k / 16
        rr = r * (1 - 0.13 * k / (turns * 16))
        pts.append(V(c.x + math.cos(a) * rr, c.y + 0.06 + 0.05 * (k / 16) % 1 * 0 + 0.045 * (k // 16), c.z + math.sin(a) * rr))
        radii.append(0.05)
    tube(g, pts, radii, 6, M_CLOTH, ROPE_TAR, tile=0.4, cap=True)


def sail_scrap(g, rng, c, w, d, yaw):
    q = quat_y(yaw)
    grid = []
    for i in range(9):
        row = []
        for j in range(6):
            x, z = -w / 2 + w * i / 8, -d / 2 + d * j / 5
            y = 0.03 + 0.09 * max(0.0, math.sin(i * 1.3 + j * 0.9)) * (1 if (i + j) % 3 else 0.4)
            row.append(Vector(c) + q @ V(x, y, z))
        grid.append(row)
    if (grid[1][0] - grid[0][0]).cross(grid[0][1] - grid[0][0]).y < 0:
        grid = grid[::-1]
    sheet(g, grid, M_CLOTH, lambda a, b: mix(SAIL, scale(SAIL, 0.7), 0.5 + 0.5 * math.sin(a * 9 + b * 5)), tile=1.0)


def cove_spill_a(rng):
    b = Builder()
    g = G(b)
    cask(g, rng, V(0.0, -0.04, 0.0), quat_y(0.4), h=0.85, r=0.33)
    cask(g, rng, V(0.95, 0.31, 0.35), quat_y(1.2) @ quat_x(math.pi / 2), h=0.85, r=0.33, head="stove", missing=(3, 4))
    cask(g, rng, V(-0.8, -0.04, 0.85), quat_y(2.2), h=0.6, r=0.25, head="open")
    crate(g, V(-0.9, 0.28, -0.6), (0.9, 0.6, 0.65), quat_y(0.5) @ quat_z(0.12), rng, col=(0.66, 0.54, 0.4))
    # A burst crate: three sides, its lid a yard off, a spill of sacks.
    q = quat_y(-0.7)
    c = V(0.6, 0.0, -1.3)
    for (o, s) in ((V(0, 0.25, -0.33), (0.9, 0.5, 0.05)), (V(-0.43, 0.25, 0), (0.05, 0.5, 0.66)), (V(0, 0.02, 0), (0.9, 0.04, 0.66))):
        lbox(g, c + q @ o, s, q, M_PLANK, (0.62, 0.5, 0.37), tile=1.0, grain=0)
    lbox(g, V(1.6, 0.03, -1.9), (0.92, 0.04, 0.68), quat_y(0.3) @ quat_x(0.05), M_PLANK, (0.6, 0.48, 0.36), tile=1.0, grain=0)
    from stories_cold import sack
    sack(g, c + q @ V(0.1, 0.17, 0.05), quat_y(1.0) @ quat_z(1.3), 1.0, rng)
    sack(g, c + q @ V(0.6, 0.12, 0.45), quat_y(2.0) @ quat_z(1.5), 0.9, rng)
    hawser_coil(g, rng, V(-1.9, 0.0, -0.2))
    sail_scrap(g, rng, V(-0.4, 0.0, 2.2), 2.6, 1.6, 0.3)
    return b


def cove_spill_b(rng):
    b = Builder()
    g = G(b)
    # A broken spar, its end splintered, a tangle of line on it.
    sp0, sp1 = V(-2.6, 0.12, -0.4), V(1.9, 0.1, 0.5)
    pole(g, sp0, sp1, 0.14, 0.12, rng, mat=M_PLANK, col=scale(OAK, 0.8), sides=9, wobble=0.0)
    beam(g, [sp1, sp1 + (sp1 - sp0).normalized() * 0.45], 0.16, 0.14, mat=M_PLANK, col=OAK_RAW, rng=rng, point=0.7)
    tube(g, [sp0.lerp(sp1, 0.3) + V(0, 0.12, 0), V(-0.4, 0.04, 0.9), V(0.6, 0.03, 1.4), V(1.2, 0.03, 1.1)],
         [0.025] * 4, 4, M_CLOTH, ROPE_TAR, tile=0.4, cap=False)
    # A sea chest burst open: iron-bound, lid thrown back, its contents gone.
    cq = quat_y(0.35)
    cc = V(0.4, 0.0, -1.2)
    lbox(g, cc + cq @ V(0, 0.3, 0), (1.0, 0.6, 0.55), cq, M_PLANK, [scale(CRIMSON, 0.8), None, CRIMSON], tile=1.0, grain=1)
    lbox(g, cc + cq @ V(0, 0.61, 0), (0.86, 0.02, 0.42), cq, M_PLANK, HOLD, tile=1.0)
    lq = cq @ quat_x(-1.95)
    lbox(g, cc + cq @ V(0, 0.62, 0.3) + lq @ V(0, 0.0, -0.28), (1.02, 0.08, 0.56), lq, M_PLANK, CRIMSON, tile=1.0)
    for x in (-0.38, 0.38):
        lbox(g, cc + cq @ V(x, 0.3, 0), (0.05, 0.62, 0.57), cq, M_IRON, IRON, tile=0.4)
    # Planks the sea broke off her.
    for k in range(4):
        c = V(rng.uniform(-2.0, 1.6), 0.03, rng.uniform(0.8, 2.2))
        d = quat_y(rng.uniform(0, math.pi)) @ V(1, 0, 0)
        board(g, c, d, V(0.02, 1, 0), rng.uniform(1.2, 2.4), 0.24, 0.06, col=mix(TAR, OAK, rng.uniform(0.2, 0.9)), rng=rng,
              jag=(0.0, 0.5))
    cask(g, rng, V(-1.4, 0.3, -1.4), quat_y(0.8) @ quat_x(math.pi / 2), h=0.8, r=0.3, head="whole")
    lantern(g, rng, V(1.2, 0.36, -0.15))
    return b


MODELS = {"cove_wreck": cove_wreck, "cove_boat": cove_boat, "cove_spill_a": cove_spill_a, "cove_spill_b": cove_spill_b}

if __name__ == "__main__":
    clear_scene()
    objs = []
    for i, (name, fn) in enumerate(MODELS.items()):
        bld = fn(np.random.default_rng(7700 + i))
        print(f"{name}: {bounds(bld)} tris {bld.tris()}")
        objs.append(bld.build(name, MATS))
    export_glb(OUT / "wreck_cove.glb", objs)
    print("WRECK_COVE_DONE")
