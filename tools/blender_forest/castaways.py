"""The castaways' snow-house -> stories_castaways.glb (src/stories_cold.rs scene `story_castaways`).

A longboat from the wrecked ship drifted north in the storm and grounded on the snow coast. Its crew
dug in: a snow-block igloo (real cut blocks laid in a rising spiral, an entrance tunnel vaulted with
leaning blocks, one side fallen in), the boat hauled up and overturned as a windbreak, its lee
gunwale propped on a cask, a tarred sailcloth hung off it, the ship's lantern on an oar planted by
the door, a second oar scratched with a day tally, empty casks, and footprints + sled runners
leading inland. No bodies: what came for them stays out of frame.

Model-local: origin = scene centre, Y up, local -Z faces the sea (the planner turns it so), the
tracks run inland toward +Z. Masses mirrored in stories_cold.rs `SCENES` (solids). Snow is never a
flat white blob: every snow part is cut blocks, a wind-sculpted drift, a banked skirt or the
trodden track, all in `s_snow` with fold-shaded tints.

    blender -b --factory-startup --python tools/blender_forest/castaways.py
"""
import math
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402
from common import OUT, clear_scene, export_glb  # noqa: E402
from geo import G, quat_x, quat_y, quat_z, sheet  # noqa: E402
from meshkit import Builder  # noqa: E402
from wayside_models import (M_BARK, M_PLANK, M_CLOTH, M_IRON, M_HIDE, M_ROCK, V, beam, board, bounds,  # noqa: E402
                            lashing, lbox, mix, pole, rock_col, scale, slab, smooth_mesh, smoothstep, stone, tube,
                            Noise, BOARD_CENTRES)
from stories_cold import M_SNOW, MATS, SNOW, disc, lathe, orient, snow_fn  # noqa: E402
import ork_camps  # noqa: E402

ork_camps.WIND_YAW = math.pi  # the wind comes off the land along +X -> -X: windward ramps face +X

TAR = (0.25, 0.2, 0.16)
WORN_TAR = (0.46, 0.38, 0.3)
OAK = (0.8, 0.68, 0.54)
RUST = (0.58, 0.38, 0.27)
IRON_DARK = (0.3, 0.29, 0.28)
SAIL = (0.3, 0.26, 0.21)
SHADOW_SNOW = (0.62, 0.72, 0.94)

IGLOO_C = V(-0.5, 0.0, 0.3)
R0, H = 1.25, 1.72          # wall centreline radius at the floor, crown height
BLOCK_H, BLOCK_T = 0.3, 0.26
DOOR_A = 1.5 * math.pi      # the door faces -Z (the sea)
FALL_A = math.pi            # the side that fell in faces -X
BOAT_C = V(2.7, -0.04, 0.4)
BOAT_L, BOAT_B, BOAT_D = 4.4, 1.3, 0.62
TILT = -0.39                # the lee (-X) gunwale lifted ~0.5u onto a cask


def ang_dist(a, b):
    d = (a - b) % (2 * math.pi)
    return min(d, 2 * math.pi - d)


def frame_quat(x, y, z):
    """Quaternion taking local X/Y/Z to the given orthonormal (right-handed) world axes."""
    return Matrix((x, y, z)).transposed().to_quaternion()


def block_col(rng):
    """Per-block tint: sawn snow blocks differ a little (wind-packed vs. softer cuts)."""
    k = rng.uniform(0.9, 1.02)
    nz = Noise(rng, 2, 3.0)
    base = snow_fn(nz, blue=rng.uniform(0.03, 0.08))
    return lambda p, n: scale(base(p, n), k)


def snow_block(g, rng, c, size, rot, cuts=0):
    """A sawn snow block: crisp flat faces (an intact block) or a snapped, rough lump (`cuts`)."""
    if cuts:
        slab(g, c, size, rot, rng, mat=M_SNOW, col_fn=block_col(rng), tile=0.9, res=(3, 2, 2), round_r=0.02,
             rough=0.03, cuts=cuts)
        return
    k = rng.uniform(0.93, 1.03)
    hi = scale(mix(SNOW, (0.86, 0.9, 1.0), rng.uniform(0.0, 0.5)), k)
    lo = scale(mix(SNOW, SHADOW_SNOW, rng.uniform(0.1, 0.3)), k)
    lbox(g, c, size, rot, M_SNOW, [lo, None, hi], tile=0.9, grain=1, u0=rng.uniform(0, 2), v0=rng.uniform(0, 2))


# ─────────────────────────────────────────────────────────────── the igloo
def r_at(y):
    return R0 * max(0.0, 1 - (y / H) ** 1.5) ** 0.55


def dr_at(y):
    e = 1e-3
    return (r_at(min(y + e, H)) - r_at(max(y - e, 0))) / (2 * e)


def igloo(g, rng):
    """The spiral of cut blocks: one continuous rising course (the first round ramps up from the
    floor, as the builders cut it), blocks leaning in along the dome, a door gap, the -X side
    fallen in (jagged break, the crown gone)."""
    nz = Noise(rng, 3, 1.5)
    theta = 0.35
    placed = 0
    while True:
        y_mid_guess = min(BLOCK_H * theta / (2 * math.pi), H * 0.95)
        r = max(r_at(y_mid_guess), 0.3)
        blen = min(0.58, max(0.34, 0.4 + 0.12 * r))
        dth = blen / r
        tc = theta + dth / 2
        top = BLOCK_H * tc / (2 * math.pi)
        bot = max(0.0, top - BLOCK_H)
        theta += dth
        if top - bot < 0.06:
            continue
        ym = (top + bot) / 2
        if ym > H * 0.9:
            break
        a = tc % (2 * math.pi)
        # The door: no blocks low on the -Z side (the tunnel runs out from here).
        if ang_dist(a, DOOR_A) < 0.33 and bot < 0.72:
            continue
        # The fallen side: a jagged break line rising away from FALL_A; the crown is gone with it.
        d = ang_dist(a, FALL_A)
        brk = 0.42 + 0.18 * nz(V(a * 2.0, 0, 0)) + 2.0 * smoothstep(0.35, 1.15, d)
        if (ym > H * 0.76 and d < 1.45) or bot > brk:
            continue
        broken = top > brk
        if broken:
            top = brk
            if top - bot < 0.07:
                continue
            ym = (top + bot) / 2
        r = r_at(ym)
        dr = dr_at(ym)
        c, s = math.cos(a), math.sin(a)
        n = V(c, -dr, s).normalized()
        u = V(dr * c, 1.0, dr * s).normalized()
        x = u.cross(n).normalized()
        rot = frame_quat(x, u, n)
        ctr = IGLOO_C + V(c * r, ym - 0.05, s * r)
        # Courses settle: a hair of jitter in lean + spin so the seams read as hand-cut.
        rot = rot @ quat_x(rng.uniform(-0.03, 0.03)) @ quat_y(rng.uniform(-0.03, 0.03))
        h_len = (top - bot) / max(u.y, 0.45)
        snow_block(g, rng, ctr, (dth * r - 0.025, h_len - 0.02, BLOCK_T), rot,
                   cuts=2 if broken else 0)
        placed += 1
    # Banked skirt round the wall foot (snow shovelled up to chink the lowest course), not a dome.
    prof = [(R0 + 0.78, -0.1), (R0 + 0.5, 0.06), (R0 + 0.28, 0.22), (R0 + 0.14, 0.3), (R0 + 0.05, 0.12)]
    verts, tris = lathe(prof, 30, IGLOO_C, quat_y(0.0))
    nzs = Noise(rng, 3, 2.0)
    verts = [p + V(0, 0.06 * nzs(p * 1.3), 0) if p.y > -0.05 else p for p in verts]
    smooth_mesh(g, verts, tris, M_SNOW, snow_fn(nzs), 1.6, inside=IGLOO_C + V(0, -2.0, 0))
    # Trodden floor inside (grey-blue, packed) and the sleeping bench along the back (+Z) wall.
    floor = [IGLOO_C + V(0, 0.015, 0)]
    for i in range(24):
        aa = 2 * math.pi * i / 24
        floor.append(IGLOO_C + V(math.cos(aa) * (R0 - 0.08), -0.02, math.sin(aa) * (R0 - 0.08)))
    ftris = [(0, 1 + (i + 1) % 24, 1 + i) for i in range(24)]
    smooth_mesh(g, floor, ftris, M_SNOW, lambda p, n: (0.74, 0.77, 0.85), 1.4, inside=IGLOO_C + V(0, -1, 0))
    for k in range(4):
        aa = 0.25 * math.pi + k * 0.42
        p = IGLOO_C + V(math.cos(aa) * 0.78, 0.15, math.sin(aa) * 0.78)
        snow_block(g, rng, p, (0.5, 0.34, 0.5), quat_y(-aa + rng.uniform(-0.05, 0.05)))
    # A hide blanket thrown back off the bench, a sea chest standing open and empty, a tin cup.
    grid = []
    for i in range(7):
        row = []
        for j in range(6):
            aa = 0.3 * math.pi + i * 0.17
            rr = 0.6 + j * 0.09
            y = 0.33 + 0.03 * math.sin(i * 1.9 + j) - (0.25 * smoothstep(0.75, 1.0, j / 5))
            row.append(IGLOO_C + V(math.cos(aa) * rr, y, math.sin(aa) * rr))
        grid.append(row)
    if (Vector(grid[1][0]) - Vector(grid[0][0])).cross(Vector(grid[0][1]) - Vector(grid[0][0])).y < 0:
        grid = grid[::-1]
    sheet(g, grid, M_HIDE, lambda a, b: mix((0.5, 0.4, 0.3), (0.66, 0.55, 0.42), b), tile=0.6)
    chest = IGLOO_C + V(0.55, 0.0, -0.35)
    cq = quat_y(0.5)
    lbox(g, chest + V(0, 0.17, 0), (0.62, 0.34, 0.38), cq, M_PLANK, [scale(OAK, 0.55), None, scale(OAK, 0.8)], tile=1.0,
         grain=0)
    lbox(g, chest + cq @ V(0, 0.36, 0.3), (0.62, 0.05, 0.38), cq @ quat_x(-1.9), M_PLANK, scale(OAK, 0.75), tile=1.0)
    lbox(g, chest + V(0, 0.33, 0), (0.56, 0.02, 0.32), cq, M_PLANK, scale(OAK, 0.25), tile=1.0)  # the dark empty inside
    for sx in (-1, 1):
        lbox(g, chest + cq @ V(sx * 0.32, 0.18, 0), (0.02, 0.3, 0.4), cq, M_IRON, RUST, tile=0.4)
    cup_v, cup_t = lathe([(0.0, 0.0), (0.045, 0.0), (0.05, 0.09), (0.046, 0.09), (0.04, 0.008), (0.0, 0.008)], 10,
                         IGLOO_C + V(-0.05, 0.0, 0.72), quat_x(1.35))
    smooth_mesh(g, cup_v, cup_t, M_IRON, lambda p, n: (0.62, 0.6, 0.58), 0.3)


def fallen_blocks(g, rng):
    """The blocks of the fallen side: some whole, some snapped, tumbled in on the floor and out
    over the skirt, half sunk; crumbs of broken snow round them."""
    for k in range(13):
        a = FALL_A + rng.uniform(-0.75, 0.75)
        d = rng.uniform(0.35, 1.0) if k < 5 else rng.uniform(1.45, 2.1)
        p = IGLOO_C + V(math.cos(a) * d, 0.0, math.sin(a) * d)
        size = (rng.uniform(0.28, 0.55), rng.uniform(0.2, 0.3), BLOCK_T * rng.uniform(0.8, 1.05))
        rot = quat_y(rng.uniform(0, 6.28)) @ quat_x(rng.uniform(-0.6, 0.6)) @ quat_z(rng.uniform(-0.8, 0.8))
        p.y = size[1] * 0.25 + (0.12 if k < 5 else 0.0)
        snow_block(g, rng, p, size, rot, cuts=2 if rng.uniform() < 0.5 else 0)
    for k in range(9):
        a = FALL_A + rng.uniform(-0.9, 0.9)
        d = rng.uniform(1.3, 2.3)
        r = rng.uniform(0.06, 0.13)
        stone(g, IGLOO_C + V(math.cos(a) * d, 0.0, math.sin(a) * d), (r, r * 0.6, r * 0.85), rng, mat=M_SNOW, detail=1,
              col_fn=snow_fn(Noise(rng, 2, 2.0)), tile=0.8)


def tunnel(g, rng):
    """The cold-trap entrance: two courses of blocks a side, vaulted with blocks leant together."""
    zin, zout = IGLOO_C.z - R0 * 0.88, IGLOO_C.z - R0 - 1.05
    n = 3
    step = (zin - zout) / n
    for k in range(n):
        zc = zout + step * (k + 0.5)
        for sx in (-1, 1):
            for course in range(2):
                y = 0.1 + course * 0.24
                off = (0.25 if course else -0.25) * step * 0.4
                snow_block(g, rng, V(IGLOO_C.x + sx * 0.42, y, zc + off), (0.22, 0.23, step * 0.97),
                           quat_y(rng.uniform(-0.04, 0.04)) @ quat_z(sx * 0.04))
            # The vault: a block from each wall top leant to meet over the passage.
            if k == 0 and sx > 0:
                continue  # the outermost east vault block lies broken in the mouth instead
            snow_block(g, rng, V(IGLOO_C.x + sx * 0.215, 0.6, zc), (0.5, 0.15, step * 0.97), quat_z(-sx * 0.6))
    snow_block(g, rng, V(IGLOO_C.x + 0.15, 0.08, zout + 0.1), (0.38, 0.15, 0.26), quat_y(0.7) @ quat_z(0.35), cuts=2)
    # Packed floor down the passage.
    lbox(g, V(IGLOO_C.x, -0.0, (zin + zout) / 2), (0.62, 0.03, zin - zout), quat_y(0.0), M_SNOW, (0.72, 0.76, 0.86),
         tile=1.4)


# ─────────────────────────────────────────────────────────────── the longboat
def hull_point(t, s, side, off=0.0):
    """Upright boat-local point: `t` -1..1 bow to stern (along Z), `s` 0 keel .. 1 gunwale, `side`
    +-1, `off` along the outward normal. Double-ended clinker longboat."""
    hb = BOAT_B / 2 * max(0.0, 1 - abs(t) ** 2.4) ** 0.55
    D = BOAT_D * (1 - 0.3 * t * t)
    sheer = 0.22 * t ** 4
    w = 1 - s
    x = side * hb * (1 - w * w)
    y = sheer - D * w ** 0.8
    p = V(x, y, t * BOAT_L / 2)
    if off:
        e = 1e-3
        w2 = max(w - e, 0.0)
        p2 = V(side * hb * (1 - w2 * w2), sheer - D * w2 ** 0.8, t * BOAT_L / 2)
        tang = p2 - p
        nrm = V(tang.y, -tang.x, 0)
        if nrm.length < 1e-12:
            nrm = V(side, 0, 0)
        if nrm.dot(p - V(0, sheer - D * 0.45, p.z)) < 0:
            nrm = -nrm
        p = p + nrm.normalized() * off
    return p


def boat_xf(p):
    """Upright boat-local -> model space: turned keel-up, lee (-X) gunwale lifted onto its prop."""
    q = V(p.x, -p.y, p.z)
    pivot = V(BOAT_B / 2, 0, 0)
    q = pivot + quat_z(TILT) @ (q - pivot)
    return BOAT_C + q


def boat_axis(t):
    return boat_xf(V(0, -BOAT_D * 0.45, t * BOAT_L / 2))


def quad(g, pts, uvs, cols, mat, away_from):
    n = (pts[1] - pts[0]).cross(pts[3] - pts[0])
    if n.length < 1e-12:
        n = (pts[2] - pts[1]).cross(pts[0] - pts[1])
    if n.length < 1e-12:
        return
    if n.dot((pts[0] + pts[2]) / 2 - away_from) < 0:
        pts, uvs, cols = pts[::-1], uvs[::-1], cols[::-1]
        n = -n
    g.poly(pts, uvs, [n.normalized()] * 4, cols, mat)


def tar_col(rng, nz, p, t):
    worn = smoothstep(0.1, 0.6, nz(p * 1.7)) * 0.7
    return mix(TAR, WORN_TAR, worn)


def longboat(g, rng):
    nz = Noise(rng, 4, 1.0)
    NT, STRAKES = 26, 6
    ts = [-1 + 2 * i / NT for i in range(NT + 1)]
    ts = [math.copysign(abs(t) ** 0.8, t) * 0.985 for t in ts]
    centres = BOARD_CENTRES[M_PLANK]
    for side in (-1, 1):
        for k in range(STRAKES):
            s0, s1 = max(0.0, k / STRAKES - 0.025), (k + 1) / STRAKES
            vc = centres[(k + (side > 0) * 2) % 5]
            for i in range(NT):
                t0, t1 = ts[i], ts[i + 1]
                ax = boat_axis((t0 + t1) / 2)
                # Outer face: proud at its lower edge (the clinker lap), flush where the next laps on.
                a = boat_xf(hull_point(t0, s0, side, 0.03))
                b = boat_xf(hull_point(t1, s0, side, 0.03))
                c = boat_xf(hull_point(t1, s1, side, 0.012))
                d = boat_xf(hull_point(t0, s1, side, 0.012))
                u0, u1 = t0 * BOAT_L / 2 / 1.1, t1 * BOAT_L / 2 / 1.1
                uvs = [(u0, vc - 0.07), (u1, vc - 0.07), (u1, vc + 0.07), (u0, vc + 0.07)]
                cols = [tar_col(rng, nz, p, 0) for p in (a, b, c, d)]
                cols[0] = scale(cols[0], 0.8)
                cols[1] = scale(cols[1], 0.8)
                quad(g, [a, b, c, d], uvs, cols, M_PLANK, ax)
                # The lap's lower edge, stepping back to the strake below.
                if k > 0:
                    e = boat_xf(hull_point(t0, s0, side, 0.0))
                    f = boat_xf(hull_point(t1, s0, side, 0.0))
                    quad(g, [e, f, b, a], [(u0, vc - 0.08), (u1, vc - 0.08), (u1, vc - 0.07), (u0, vc - 0.07)],
                         [scale(TAR, 0.6)] * 4, M_PLANK, ax)
                # Inside skin (raw oak, darkened by bilge and age), seen under the lifted gunwale.
                ia = boat_xf(hull_point(t0, s0, side, -0.005))
                ib = boat_xf(hull_point(t1, s0, side, -0.005))
                ic = boat_xf(hull_point(t1, s1, side, -0.005))
                id_ = boat_xf(hull_point(t0, s1, side, -0.005))
                n = (ib - ia).cross(id_ - ia)
                inner_cols = [mix(scale(OAK, 0.45), scale(OAK, 0.7), s0)] * 2 + [mix(scale(OAK, 0.45), scale(OAK, 0.7), s1)] * 2
                pts = [ia, ib, ic, id_]
                if n.length > 1e-12:
                    if n.dot((ia + ic) / 2 - ax) > 0:
                        pts, inner_cols = pts[::-1], inner_cols[::-1]
                        n = -n
                    g.poly(pts, [(u0, vc - 0.07), (u1, vc - 0.07), (u1, vc + 0.07), (u0, vc + 0.07)][::1 if pts[0] is ia else -1],
                           [n.normalized()] * 4, inner_cols, M_PLANK)
    # Keel + stem and stern posts (along the keel line, curling up at the ends).
    keel = [boat_xf(hull_point(t, 0.0, 1, 0.0) + V(0, -0.04, 0)) for t in [-0.985 + 1.97 * i / 12 for i in range(13)]]
    beam(g, keel, 0.08, 0.09, up=(0, 1, 0), mat=M_PLANK, col=scale(TAR, 1.2), rng=rng)
    for sgn in (-1, 1):
        stem = [boat_xf(V(0, 0.22 * f ** 2 - BOAT_D * 0.7 * (1 - f) ** 1.5, sgn * (BOAT_L / 2 * 0.985 + 0.06 * f)))
                for f in [i / 5 for i in range(6)]]
        beam(g, stem, 0.08, 0.1, up=(1, 0, 0), mat=M_PLANK, col=scale(TAR, 1.1), rng=rng)
    # Gunwale rails, ribs and thwarts (visible under the lifted lee side).
    for side in (-1, 1):
        rail = [boat_xf(hull_point(t, 1.0, side, 0.02) + V(0, -0.02, 0)) for t in [-0.95 + 1.9 * i / 14 for i in range(15)]]
        beam(g, rail, 0.06, 0.06, mat=M_PLANK, col=scale(OAK, 0.6), rng=rng)
    for t in (-0.72, -0.48, -0.24, 0.0, 0.24, 0.48, 0.72):
        rib = [boat_xf(hull_point(t, abs(f), 1 if f >= 0 else -1, -0.035)) for f in [-1 + 2 * i / 10 for i in range(11)]]
        beam(g, rib, 0.045, 0.05, mat=M_PLANK, col=scale(OAK, 0.55), rng=rng)
    for t in (-0.42, 0.05, 0.5):
        y = 0.22 * t ** 4 - 0.2
        hb = BOAT_B / 2 * max(0.0, 1 - abs(t) ** 2.4) ** 0.55 * 0.94
        a, b = boat_xf(V(-hb, y, t * BOAT_L / 2)), boat_xf(V(hb, y, t * BOAT_L / 2))
        board(g, (a + b) / 2, b - a, boat_xf(V(0, 1, t * BOAT_L / 2)) - boat_xf(V(0, 0, t * BOAT_L / 2)), (b - a).length, 0.22,
              0.04, mat=M_PLANK, col=scale(OAK, 0.7), rng=rng)
    # Snow settled on the upturned bottom: thickest along the keel and the lee planking that now
    # faces the sky, thinning to nothing at its edges (never a slab laid on top).
    grid = []
    for i in range(17):
        t = -0.9 + 1.8 * i / 16
        row = []
        for j in range(9):
            f = -0.55 + 0.75 * j / 8  # -: lee (-X) side, +: windward
            side = -1 if f < 0 else 1
            s = min(abs(f), 1.0)
            env = math.sin(math.pi * (j / 8)) ** 0.8 * (1 - abs(t) ** 3)
            thick = 0.035 + 0.075 * env * (0.8 + 0.4 * math.sin(t * 7.0 + j))
            row.append(boat_xf(hull_point(t, s, side, 0.02 + thick * env)))
        grid.append(row)
    g0 = Vector(grid[0][0])
    if (Vector(grid[1][0]) - g0).cross(Vector(grid[0][1]) - g0).y < 0:
        grid = grid[::-1]
    sheet(g, grid, M_SNOW, lambda a, b: scale(SNOW, 0.95 + 0.05 * math.sin(a * 13 + b * 5)), tile=1.5)


# ─────────────────────────────────────────────────────────────── the props
def cask(g, rng, base, rot, h=0.62, r=0.24, staves=16, head="whole", missing=(), col=OAK):
    """A coopered cask: bellied staves, four rusted iron hoops. `head`: 'whole', 'open' (the head
    knocked out: the empty dark inside shows) or 'stove' (head driven in, sitting askew low inside)."""
    base = Vector(base)
    sw = 2 * math.pi * r / staves
    for i in range(staves):
        if i in missing:
            continue
        a = 2 * math.pi * (i + 0.5) / staves
        pts = []
        for k in range(6):
            y = h * k / 5
            rr = r * (0.84 + 0.16 * math.sin(math.pi * y / h))
            pts.append(base + rot @ V(math.cos(a) * rr, y, math.sin(a) * rr))
        out = rot @ V(math.cos(a), 0, math.sin(a))
        beam(g, pts, sw * 1.02, 0.024, up=tuple(out), mat=M_PLANK, mode="plank",
             col=mix(scale(col, 0.62), col, rng.uniform(0.2, 1.0)), rng=rng, chamfer=0.25)
    for f in (0.1, 0.24, 0.76, 0.9):
        y = h * f
        rr = r * (0.84 + 0.16 * math.sin(math.pi * f)) + 0.012
        ring = [base + rot @ V(math.cos(2 * math.pi * k / 18) * rr, y, math.sin(2 * math.pi * k / 18) * rr) for k in range(19)]
        tube(g, ring, [0.009] * 19, 4, M_IRON, mix(RUST, IRON_DARK, rng.uniform(0, 0.5)), tile=0.3, cap=False)
    disc(g, base + rot @ V(0, 0.04, 0), rot, r * 0.85, 0.025, 14, M_PLANK, scale(col, 0.35))
    if head == "whole":
        disc(g, base + rot @ V(0, h * 0.94, 0), rot, r * 0.86, 0.03, 14, M_PLANK, scale(col, 0.8))
    elif head == "stove":
        disc(g, base + rot @ V(0.03, h * 0.55, 0), rot @ quat_x(0.5), r * 0.8, 0.03, 14, M_PLANK, scale(col, 0.6))


def oar(g, rng, grip, tip, col=OAK, tally=0, tally_face=None):
    """A ship's oar from the grip to the blade tip; `tally` day-scratches cut across the loom in
    groups of five (four strokes + a strike), on the face toward `tally_face`."""
    grip, tip = Vector(grip), Vector(tip)
    d = (tip - grip).normalized()
    L = (tip - grip).length
    neck = tip - d * 0.68
    pole(g, grip, grip + d * 0.16, 0.022, 0.024, rng, mat=M_PLANK, col=scale(col, 0.7), sides=8, wobble=0.0, tile=0.6)
    pole(g, grip + d * 0.16, neck, 0.034, 0.03, rng, mat=M_PLANK, col=col, sides=9, wobble=0.0, tile=0.8)
    face = Vector(tally_face) if tally_face is not None else V(0, 1, 0)
    nf = (face - d * face.dot(d)).normalized()
    side = d.cross(nf).normalized()
    board(g, (neck + tip) / 2, d, nf, 0.7, 0.14, 0.022, mat=M_PLANK, col=scale(col, 0.85), rng=rng)
    if not tally:
        return
    rot = frame_quat(side, d, nf)
    f0 = 0.3
    k = 0
    pos = f0 * L
    while k < tally:
        group = min(5, tally - k)
        start = pos
        for m in range(min(group, 4)):
            c = grip + d * pos + nf * 0.031
            lbox(g, c, (0.05, 0.006, 0.008), rot @ quat_z(rng.uniform(-0.12, 0.12)), M_PLANK, (0.1, 0.085, 0.07), tile=0.2)
            pos += 0.028
        if group == 5:
            mid = grip + d * (start + 0.042) + nf * 0.033
            lbox(g, mid, (0.006, 0.13, 0.008), rot @ quat_z(0.55), M_PLANK, (0.1, 0.085, 0.07), tile=0.2)
        k += group
        pos += 0.05


def lantern(g, rng, hang):
    """The ship's lantern hanging by its bail: iron base and hood, four guard bars, horn panes."""
    hang = Vector(hang)
    top = hang - V(0, 0.07, 0)
    body_top = top - V(0, 0.09, 0)
    body_bot = body_top - V(0, 0.2, 0)
    disc(g, body_bot, quat_y(0.0), 0.085, 0.03, 10, M_IRON, IRON_DARK)
    disc(g, body_bot - V(0, 0.03, 0), quat_y(0.0), 0.07, 0.03, 10, M_IRON, scale(IRON_DARK, 0.8))
    hood_v, hood_t = lathe([(0.095, 0.0), (0.06, 0.06), (0.03, 0.09), (0.0, 0.09)], 10, body_top, quat_y(0.0))
    smooth_mesh(g, hood_v, orient(hood_v, hood_t, body_top, V(0, 1, 0), True), M_IRON, lambda p, n: mix(RUST, IRON_DARK, 0.5), 0.3)
    disc(g, body_top + V(0, 0.1, 0), quat_y(0.0), 0.035, 0.02, 8, M_IRON, IRON_DARK)
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        o = V(math.cos(a) * 0.075, 0, math.sin(a) * 0.075)
        beam(g, [body_bot + o, body_top + o], 0.012, 0.012, mat=M_IRON, col=IRON_DARK, rng=rng)
        pa = math.pi / 2 * k
        pc = (body_bot + body_top) / 2 + V(math.cos(pa) * 0.066, 0, math.sin(pa) * 0.066)
        lbox(g, pc, (0.006, 0.19, 0.09), quat_y(-pa), M_CLOTH, (0.62, 0.48, 0.28), tile=0.2)  # horn pane
    bail = [top + V(math.cos(math.pi * f) * 0.06, math.sin(math.pi * f) * 0.06 - 0.05, 0) for f in [i / 8 for i in range(9)]]
    tube(g, bail, [0.006] * 9, 4, M_IRON, IRON_DARK, tile=0.3, cap=False)
    tube(g, [hang + V(0, 0.01, 0), top + V(0, 0.01, 0)], [0.006, 0.006], 4, M_CLOTH, (0.85, 0.72, 0.5), tile=0.3)


def sailcloth(g, rng):
    """The tarred sail hung off the lifted lee gunwale and pegged down toward the igloo — a lean-to
    curtain, weighted at its foot with snow blocks; one corner torn loose and folded back."""
    grid = []
    NI, NJ = 15, 9
    for i in range(NI):
        t = -0.7 + 1.35 * i / (NI - 1)
        top = boat_xf(hull_point(t, 1.0, -1, 0.05)) + V(0, -0.03, 0)
        foot = V(top.x - 1.35 - 0.1 * math.sin(i * 0.9), -0.03, top.z + 0.06 * math.sin(i * 1.7))
        row = []
        for j in range(NJ):
            f = j / (NJ - 1)
            p = top.lerp(foot, f)
            p.y -= 0.14 * math.sin(math.pi * f) * (0.8 + 0.3 * math.sin(i * 1.3))
            p.x += 0.05 * math.sin(i * 1.75 + 0.6) * math.sin(math.pi * f)
            if i >= NI - 3 and f > 0.55:  # the torn corner folds back on itself
                p.y += 0.12 * (f - 0.55) * (i - NI + 4)
                p.x += 0.25 * (f - 0.55)
            row.append(p)
        grid.append(row)
    g0 = Vector(grid[0][0])
    if (Vector(grid[1][0]) - g0).cross(Vector(grid[0][1]) - g0).y < 0:
        grid = grid[::-1]
    nz = Noise(rng, 3, 2.5)
    sheet(g, grid, M_CLOTH, lambda a, b: mix(SAIL, (0.5, 0.45, 0.36), smoothstep(0.2, 0.8, 0.5 + 0.5 * math.sin(a * 9 + b * 4))
                                          * 0.6), tile=0.7, double=True)
    for i in (2, 7, 11):
        p = grid[i][-1] if grid[0][0].x > grid[0][-1].x else grid[i][0]
        snow_block(g, rng, V(p.x, 0.07, p.z), (0.42, 0.2, BLOCK_T), quat_y(rng.uniform(-0.4, 0.4)) @ quat_z(rng.uniform(-0.2, 0.2)))


def track(g, rng, path):
    """Sled runners and footprints along `path` (model XZ points) — no flat ribbon: each runner is a
    pair of low ridges of snow it shoved aside, each print a pressed oval (blue-shadowed floor inside
    a raised rim), so they sit in the ground snow wherever its height wanders. The hauler walked
    between the runners, a second walker beside; the far prints soften (wind-filled) and fade."""
    pts = [V(x, 0, z) for x, z in path]
    seg = [(pts[i + 1] - pts[i]).length for i in range(len(pts) - 1)]
    L = sum(seg)

    def at(u):
        for i, s in enumerate(seg):
            if u <= s or i == len(seg) - 1:
                f = min(u / s, 1.0)
                p = pts[i].lerp(pts[i + 1], f)
                d = (pts[i + 1] - pts[i]).normalized()
                if i + 1 < len(seg) and f > 0.7:
                    d = d.lerp((pts[i + 2] - pts[i + 1]).normalized(), (f - 0.7) / 0.6).normalized()
                if i > 0 and f < 0.3:
                    d = (pts[i] - pts[i - 1]).normalized().lerp(d, 0.5 + f / 0.6).normalized()
                return p, d
            u -= s
        return pts[-1], (pts[-1] - pts[-2]).normalized()

    snow_rim = scale(SNOW, 0.98)
    # Runner ridges: snow shoved up either side of each runner's groove.
    for c in (-0.26, 0.26):
        for o in (-0.055, 0.055):
            line, radii = [], []
            n = int(L / 0.25)
            for i in range(n + 1):
                u = L * i / n
                p, d = at(u)
                side = V(-d.z, 0, d.x)
                fade = smoothstep(0.0, 0.8, u) * smoothstep(L, L - 1.6, u)
                q = p + side * (c + o)
                q.y = 0.02 + 0.045 * fade
                line.append(q)
                radii.append(0.015 + 0.03 * fade)
            tube(g, line, radii, 5, M_SNOW, snow_rim, tile=1.2, cap=False)
        # The groove floor between, in its own blue shadow.
        line = []
        n = int(L / 0.25)
        for i in range(n + 1):
            u = L * i / n
            p, d = at(u)
            q = p + V(-d.z, 0, d.x) * c
            q.y = 0.045
            line.append(q)
        tube(g, line, [0.04] * len(line), 4, M_SNOW, SHADOW_SNOW, tile=1.2, cap=False)

    def print_(u, v, depth):
        p, d = at(u)
        side = V(-d.z, 0, d.x)
        c = p + side * v
        yaw = math.atan2(d.x, d.z) + rng.uniform(-0.15, 0.15)
        rq = quat_y(yaw)
        a, b = 0.13, 0.055
        ring = [c + rq @ V(math.sin(2 * math.pi * k / 12) * b * 1.15, 0.0, math.cos(2 * math.pi * k / 12) * a * 1.12)
                for k in range(13)]
        for q in ring:
            q.y = 0.05 + 0.015 * depth
        tube(g, ring, [0.008 + 0.011 * depth] * 13, 5, M_SNOW, snow_rim, tile=0.6, cap=False)
        floor = [c + V(0, 0.05 + 0.012 * depth, 0)] + [c + rq @ V(math.sin(2 * math.pi * k / 12) * b,
                                                                     0.05 + 0.012 * depth, math.cos(2 * math.pi * k / 12) * a)
                                                          for k in range(12)]
        tris = [(0, 1 + (k + 1) % 12, 1 + k) for k in range(12)]
        smooth_mesh(g, floor, tris, M_SNOW, lambda p, n: scale(SHADOW_SNOW, 0.92), 0.6, inside=c + V(0, -1, 0))

    u, k = 0.5, 0
    while u < L - 0.8:
        print_(u, 0.08 * (1 if k % 2 else -1), 1.0 - 0.6 * smoothstep(L * 0.4, L, u))
        u += rng.uniform(0.58, 0.68)
        k += 1
    u, k = 1.1, 0
    while u < L - 1.4:
        print_(u, 0.52 + 0.06 * (1 if k % 2 else -1), 1.0 - 0.7 * smoothstep(L * 0.3, L, u))
        u += rng.uniform(0.66, 0.76)
        k += 1


def driftwood(g, rng):
    """Wreck wood the sea threw up with them: a sun-greyed spar and a broken strake."""
    grey = (0.62, 0.6, 0.58)
    pole(g, V(-3.0, 0.05, -2.1), V(-1.6, 0.08, -3.05), 0.07, 0.055, rng, mat=M_BARK, col=grey, sides=8)
    board(g, V(1.55, 0.04, -2.6), V(1, 0, 0.35), V(0.05, 1, 0), 1.3, 0.2, 0.03, mat=M_PLANK, col=scale(TAR, 1.4),
          rng=rng, jag=(0.0, 0.25))


def story_castaways(rng):
    """Footprint r <= 3.6. Masses (model-local, mirrored in stories_cold.rs): the igloo (-0.5, 0.3,
    r 1.35), the tunnel (-0.5, -1.4), the boat (2.7, 0.4, 0.7 x 2.25), the lantern oar (0.35, -2.7)."""
    b = Builder()
    g = G(b)
    igloo(g, rng)
    fallen_blocks(g, rng)
    tunnel(g, rng)
    longboat(g, rng)
    sailcloth(g, rng)
    # The lee gunwale's prop: an empty cask at the bow end; a snapped oar shaft wedged at the stern.
    cask(g, rng, V(2.08, -0.02, -0.95), quat_y(0.3), h=0.46, r=0.2, head="whole")
    pole(g, V(2.0, -0.02, 1.55), V(2.12, 0.48, 1.62), 0.032, 0.03, rng, mat=M_PLANK, col=OAK, sides=8)
    # Empty casks: one on its side by the tunnel mouth (head stove in), one standing open.
    cask(g, rng, V(1.05, 0.2, -2.15), quat_y(0.9) @ quat_x(math.pi / 2) @ quat_y(0.0), head="stove", missing=(4,))
    for k, (x, z, yaw) in enumerate(((1.25, -1.95, 0.2), (1.38, -2.05, 1.1))):
        board(g, V(x, 0.02, z), V(math.cos(yaw), 0, math.sin(yaw)), V(0, 1, 0.1), 0.6, 0.07, 0.02, mat=M_PLANK,
              col=scale(OAK, 0.6), rng=rng)
    cask(g, rng, V(1.35, -0.03, 1.95), quat_y(2.2), head="open")
    ork_camps.drift(g, (1.4, 0.0, 2.15), 0.35, 0.4, 0.22, rng)
    # The ship's lantern on the oar planted blade-up by the door; the tally oar leant on the tunnel.
    oar(g, rng, V(0.35, -0.45, -2.7), V(0.31, 2.05, -2.66))
    lashing(g, V(0.33, 1.55, -2.68), (0, 1, 0), 0.04, rng, turns=2)
    tube(g, [V(0.33, 1.53, -2.68), V(0.42, 1.48, -2.72), V(0.46, 1.36, -2.74)], [0.006] * 3, 4, M_CLOTH,
         (0.85, 0.72, 0.5), tile=0.3, cap=False)
    lantern(g, rng, V(0.46, 1.36, -2.74))
    oar(g, rng, V(-0.98, 0.62, -0.75), V(-1.12, 0.03, -3.05), tally=23, tally_face=(-1, 0.3, 0))
    # Wind-sculpted drifts: banked on the boat's windward flank, behind the igloo, and half over the
    # tunnel's east wall.
    ork_camps.drift(g, (3.75, 0.0, 0.4), 0.7, 2.3, 0.5, rng)
    ork_camps.drift(g, (0.2, 0.0, 1.75), 0.95, 0.75, 0.38, rng)
    ork_camps.drift(g, (0.3, 0.0, -1.6), 0.45, 0.6, 0.3, rng)
    # Tracks: out of the tunnel mouth, round the fallen side, and away inland (+Z).
    track(g, rng, [(-0.5, -2.75), (-1.6, -2.55), (-2.6, -1.4), (-2.85, 0.4), (-2.6, 2.4), (-2.0, 4.2), (-1.5, 5.6)])
    driftwood(g, rng)
    return b


MODELS = {"story_castaways": story_castaways}

if __name__ == "__main__":
    clear_scene()
    objs = []
    for i, (name, fn) in enumerate(MODELS.items()):
        b = fn(np.random.default_rng(9100 + i))
        print(f"{name}: {bounds(b)}")
        objs.append(b.build(name, MATS))
    export_glb(OUT / "stories_castaways.glb", objs)
    print("CASTAWAYS_DONE")
