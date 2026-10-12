"""Gnashfang Hold + the Blight dressing -> ork_hold.glb (src/ork_fortress.rs).

The Hold is the same people as the five camps (ork_camps.py): hide, bone, rough bark timber,
black iron, lashings — only bigger and meaner. Every piece is built from its real parts:
sharpened split logs packed into an earth berm, notched log cribs, hide roofs held down by
rope-and-stone weights, iron straps with nail heads, horned skulls. Ground-contact parts run
below y=0 so nothing floats on the Blight's uneven mud.

    hold_wall_a/b        palisade run, 4.2 long along X, centred (stretched per ring segment)
    hold_gate_frame      gate posts + lintel + skull row (the gap is 6.2 wide, centred)
    hold_gate_leaf_l/r   the two hinged leaves; hinge at the origin, leaf runs to -X (l) / +X (r)
    hold_tower           leaning watchtower (platform 4.55, banner pole on the axis to 7.0)
    hold_hall            great hall, door on -Z (spawned x1.25); ridge 5.95, eaves 2.45
    hold_spire           crooked crib-log spire; brazier at (0.45, 12.05, -0.3), flag pole x=-0.8
    hold_longhouse       log barracks 3.8 x 5.8, long axis Z, door on -Z
    hold_forge           dry-stone hearth (coal bed at (0, 0.75, -0.35)), bellows, anvil, barrel
    hold_pen             boar pen, post-and-rail with a gap on -Z, churned mud, log trough
    hold_drum            the great war drum
    hold_rack            weapon rack: spears, clubs, cleavers, a shield
    hold_totem           war totem (horned), faces +Z
    blight_shroom_a/b/c  warp toadstool clusters (on a rotten log / a mud hummock / a ring)
    blight_gibbet        gibbet with a chained iron cage and its remains
    blight_effigy        hide-draped warning effigy with a horned skull
    blight_ribcage       a titanic beast's ribs arcing out of the mud
    blight_tarpit        glossy black tar pool with bones breaking the surface

    blender -b --factory-startup --python tools/blender_forest/ork_hold.py
"""
import math
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402
from common import OUT, clear_scene, export_glb  # noqa: E402
from geo import G, frustum, quat_x, quat_y, quat_z, sheet  # noqa: E402
from meshkit import Builder  # noqa: E402
import ork_camps as OC  # noqa: E402
from ork_camps import (BONE, OLD_BONE, ROPE, RAWHIDE, SOOT, OCHRE, HIDE, DARK_HIDE, TIMBER, EARTH, bone, cord,  # noqa: E402
                       feather, great_drum, skull, totem)
from wayside_models import (M_BARK, M_PLANK, M_STONE, M_HIDE, M_CLOTH, M_IRON, M_ROCK, M_EARTH, V, beam, board,  # noqa: E402
                            bounds, lashing, lbox, mix, mound, pole, rock_col, scale, slab, smooth_mesh, smoothstep,
                            stone, tube, Noise)
from stories_cold import dome, spear  # noqa: E402
from landmarks_kit import lathe  # noqa: E402

M_TAR = len(OC.MATS)
MATS = OC.MATS + ["ice"]  # "ice" = the glossy low-roughness set: near-black vertex colour reads as wet tar

BARK = (0.66, 0.6, 0.53)
HEWN = (0.86, 0.74, 0.58)
IRON = (0.32, 0.31, 0.3)
MUD = (0.42, 0.36, 0.3)
WARP = (0.34, 0.48, 0.16)


def earth_fn(rng, base=EARTH, wet=0.0):
    nz = Noise(rng, 4, 1.6)
    return lambda p, n: scale(mix(base, (0.25, 0.21, 0.17), wet), 0.78 + 0.22 * nz(p * 1.7))


def stake(g, rng, base, h, r, lean=(0.0, 0.0), col=BARK, tip=0.38):
    """A sharpened log: bark body sunk into the ground, a hewn pale point."""
    base = Vector(base)
    d = V(lean[0], 1.0, lean[1]).normalized()
    top = base + d * h
    cut = top - d * tip
    pole(g, base, cut, r, r * 0.93, rng, col=scale(col, rng.uniform(0.85, 1.08)), sides=7)
    tube(g, [cut, cut + d * tip * 0.55, top], [r * 0.93, r * 0.48, 0.012], 7, M_PLANK,
         scale(HEWN, rng.uniform(0.75, 0.95)), tile=0.4)
    return top


def footing_stones(g, rng, c, rx, rz, n, rmin=0.08, rmax=0.18):
    c = Vector(c)
    for _ in range(n):
        a = rng.uniform(0, 2 * math.pi)
        k = rng.uniform(0.75, 1.1)
        r = rng.uniform(rmin, rmax)
        stone(g, tuple(c + V(math.cos(a) * rx * k, r * 0.25, math.sin(a) * rz * k)), (r, r * 0.7, r * 1.1), rng,
              detail=1, col_fn=rock_col((0.74, 0.72, 0.68), moss=0.2, ground=c.y), tile=0.4)


def hide_col(nz, cells=(6, 4), soot_top=None):
    """Patchwork hide colour for sheets: patches of HIDE / DARK_HIDE / RAWHIDE with darker seams."""
    shades = [HIDE, DARK_HIDE, scale(RAWHIDE, 0.85), scale(HIDE, 0.8), mix(HIDE, OCHRE, 0.2)]

    def f(u, v):
        iu, iv = int(u * cells[0]), int(v * cells[1])
        c = shades[(iu * 7 + iv * 3 + iu * iv) % len(shades)]
        fu, fv = u * cells[0] - iu, v * cells[1] - iv
        seam = 0.72 if min(fu, 1 - fu, fv, 1 - fv) < 0.06 else 1.0
        k = seam * (0.85 + 0.15 * nz(V(u * 5, v * 5, 0)))
        out = scale(c, k)
        if soot_top is not None:
            out = mix(out, SOOT, soot_top(u, v))
        return out
    return f


# ─────────────────────────────────────────────────────────────── palisade
def hold_wall(rng):
    b = Builder()
    g = G(b)
    n = 8
    for k in range(n):
        x = -2.1 + (k + 0.5) * 4.2 / n + rng.uniform(-0.04, 0.04)
        r = rng.uniform(0.13, 0.17)
        h = rng.uniform(3.05, 3.6)
        base = V(x, -0.7, rng.uniform(-0.05, 0.05))
        lean = (rng.uniform(-0.025, 0.025), rng.uniform(-0.03, 0.03))
        if rng.uniform() < 0.1:
            # A stake snapped and replaced short — the jagged stump of the old one beside it.
            top = stake(g, rng, base, h * 0.82, r, lean)
        else:
            top = stake(g, rng, base, h, r, lean)
        if rng.uniform() < 0.14:
            skull(g, top - V(0, 0.08, 0), 2.0, rng, horns=0.6 if rng.uniform() < 0.5 else 0.0,
                  yaw=math.pi + rng.uniform(-0.4, 0.4))
        for ry_ in (1.0, 1.95):
            lashing(g, V(x, ry_ - 0.7 + 0.7, base.z), (0, 1, 0), r + 0.025, rng, turns=2)
    # Two rails on the inner face (+Z), the ends left long and rough.
    for y in (1.0, 1.95):
        beam(g, [V(-2.2, y + rng.uniform(-0.04, 0.04), 0.21), V(2.2, y + rng.uniform(-0.04, 0.04), 0.21)], 0.13, 0.16,
             mat=M_PLANK, rng=rng, col=scale(TIMBER, rng.uniform(0.75, 0.9)), rough=0.06, jag=(0.06, 0.06))
    # The earth berm the stakes are rammed into, stones packed against the foot.
    mound(g, (0, -0.06, 0), 2.45, 0.95, 0.4, rng, col_fn=earth_fn(rng, EARTH, 0.3), rings=5, seg=22, edge=0.18)
    footing_stones(g, rng, (0, 0, 0), 2.2, 0.6, 12)
    # A hide rag tied to one stake, a bone or two in the ditch.
    if rng.uniform() < 0.6:
        x = rng.uniform(-1.6, 1.6)
        sheet(g, [[tuple(V(x - 0.25 + 0.5 * u, 1.9 - 0.75 * t + 0.08 * math.sin(u * 3 + t * 2), -0.17 - 0.04 * t))
                   for u in (0.0, 0.5, 1.0)] for t in np.linspace(0, 1, 4)], M_HIDE,
              lambda u, v: scale(DARK_HIDE, 0.85 + 0.2 * v), tile=0.6, double=True)
    for _ in range(2):
        x = rng.uniform(-1.8, 1.8)
        z = -rng.uniform(0.7, 1.0)
        bone(g, V(x, 0.03, z), V(x + rng.uniform(-0.4, 0.4), 0.05, z - rng.uniform(0.1, 0.3)), 0.025, rng,
             col=OLD_BONE)
    return b


# ─────────────────────────────────────────────────────────────── gate
def hold_gate_frame(rng):
    b = Builder()
    g = G(b)
    for sx in (-1, 1):
        x = sx * 3.1
        stake(g, rng, V(x, -0.9, 0), 5.05, 0.3, (0.0, 0.0), tip=0.55)
        for y in (0.35, 1.3, 2.4):
            tube(g, [V(x + math.cos(a) * 0.315, y, math.sin(a) * 0.315) for a in np.linspace(0, 2 * math.pi, 13)],
                 [0.022] * 13, 4, M_IRON, IRON, tile=0.3, cap=False)
        # Knee brace up to the lintel, lashed.
        beam(g, [V(x, 2.25, 0.12), V(sx * 2.15, 3.15, 0.12)], 0.14, 0.16, mat=M_PLANK, rng=rng,
             col=scale(TIMBER, 0.82), rough=0.05)
        lashing(g, V(x, 2.3, 0.0), (0, 1, 0), 0.33, rng, turns=3)
        mound(g, (x, -0.05, 0), 0.95, 0.85, 0.35, rng, col_fn=earth_fn(rng, EARTH, 0.25), rings=4, seg=16)
        footing_stones(g, rng, (x, 0, 0), 0.7, 0.6, 8, 0.1, 0.22)
    beam(g, [V(-3.75, 3.35, 0), V(3.75, 3.38, 0)], 0.5, 0.46, mat=M_PLANK, rng=rng, col=scale(TIMBER, 0.78),
         rough=0.08, jag=(0.08, 0.08))
    beam(g, [V(-3.3, 3.78, 0.05), V(3.3, 3.76, 0.05)], 0.26, 0.3, mat=M_BARK, mode="bark", rng=rng, col=BARK,
         rough=0.06)
    for sx in (-1, 1):
        lashing(g, V(sx * 3.1, 3.36, 0), (0, 1, 0), 0.35, rng, turns=4)
    for k, x in enumerate((-1.6, 0.0, 1.6)):
        skull(g, V(x, 3.95 + (0.06 if k == 1 else 0), -0.12), 3.2 if k == 1 else 2.6, rng, horns=1.4 if k == 1 else 0.8,
              yaw=math.pi)
    # Bone charms hanging off the lintel's outer face.
    for x in (-2.6, -0.85, 0.85, 2.6):
        bot = cord(g, V(x, 3.12, -0.2), rng.uniform(0.35, 0.7), rng, col=DARK_HIDE, r=0.014)
        for j in range(3):
            a = j * 2.1
            bone(g, bot + V(math.cos(a) * 0.03, 0, math.sin(a) * 0.03), bot + V(-math.cos(a) * 0.04, -0.26, 0), 0.014,
                 rng)
    # The gateway churned to mud by feet and carts: ruts, puddle-dark low spots.
    mound(g, (0, -0.06, 0), 3.0, 2.6, 0.1, rng, col_fn=earth_fn(rng, MUD, 0.5), rings=5, seg=20, edge=0.2)
    for sx in (-1, 1):
        tube(g, [V(sx * 0.75, 0.035, z) for z in np.linspace(-2.4, 2.4, 6)], [0.07] * 6, 5, M_EARTH,
             (0.24, 0.2, 0.16), tile=0.5)
    return b


def hold_gate_leaf(rng, sign):
    """sign +1 = leaf runs to -X from the hinge at the origin (the west leaf); -1 runs to +X."""
    b = Builder()
    g = G(b)
    run = -sign
    n = 7
    w = 2.95 / n
    for k in range(n):
        x = run * (w * (k + 0.5))
        L = 3.0 + rng.uniform(-0.12, 0.12) + (0.15 if k % 2 else 0.0)
        board(g, V(x, 0.05 + L / 2, 0), (0, 1, 0), (0, 0, 1), L, w * 0.97, 0.11, mat=M_PLANK, rng=rng,
              col=scale(TIMBER, rng.uniform(0.7, 0.92)), point=0.22)
    # Hinge stile: a round pole the straps wrap round.
    pole(g, V(0, 0.0, 0), V(0, 3.15, 0), 0.12, 0.11, rng, col=BARK, sides=8)
    # Inside (+Z): two ledgers and the Z-brace.
    xs = (run * 0.1, run * 2.85)
    for y in (0.6, 2.45):
        beam(g, [V(xs[0], y, 0.12), V(xs[1], y, 0.12)], 0.16, 0.12, mat=M_PLANK, rng=rng, col=scale(TIMBER, 0.8),
             rough=0.04)
    beam(g, [V(run * 0.25, 0.72, 0.13), V(run * 2.7, 2.32, 0.13)], 0.14, 0.1, mat=M_PLANK, rng=rng,
         col=scale(TIMBER, 0.75), rough=0.04)
    # Outside (-Z): black iron straps wrapping the hinge stile, nail heads down each strap.
    for y in (0.7, 2.25):
        lbox(g, V(run * 1.4, y, -0.075), (2.75, 0.13, 0.025), quat_y(0), M_IRON, IRON, tile=0.5)
        tube(g, [V(math.cos(a) * 0.135, y, math.sin(a) * 0.135) for a in np.linspace(0, 2 * math.pi, 11)],
             [0.03] * 11, 4, M_IRON, IRON, tile=0.3, cap=False)
        for k in range(7):
            dome(g, V(run * (0.25 + k * 0.4), y, -0.09), 0.028, quat_x(-math.pi / 2), M_IRON, lambda p, n: IRON,
                 tile=0.2, rings=2, seg=6, squash=0.7)
    skull(g, V(run * 1.5, 1.55, -0.2), 2.4, rng, horns=1.0, yaw=math.pi)
    return b


# ─────────────────────────────────────────────────────────────── watchtower
def hold_tower(rng):
    b = Builder()
    g = G(b)
    corners = [(-1, -1), (1, -1), (-1, 1), (1, 1)]
    tops = {}
    for sx, sz in corners:
        p0 = V(sx * 0.82, -0.7, sz * 0.82)
        p1 = V(sx * 0.6, 4.62, sz * 0.6)
        pole(g, p0, p1, 0.17, 0.14, rng, col=scale(BARK, rng.uniform(0.9, 1.05)), sides=8, segs=4)
        tops[(sx, sz)] = (p0, p1)
        mound(g, (sx * 0.82, -0.05, sz * 0.82), 0.5, 0.5, 0.22, rng, col_fn=earth_fn(rng), rings=3, seg=12)
    at = lambda c, t: tops[c][0].lerp(tops[c][1], t)
    faces = [((-1, -1), (1, -1)), ((1, -1), (1, 1)), ((1, 1), (-1, 1)), ((-1, 1), (-1, -1))]
    for a, c in faces:
        for t0, t1 in ((0.18, 0.5), (0.5, 0.82)):
            beam(g, [at(a, t0), at(c, t1)], 0.08, 0.1, mat=M_PLANK, rng=rng, col=scale(TIMBER, 0.78), rough=0.05)
            beam(g, [at(c, t0), at(a, t1)], 0.08, 0.1, mat=M_PLANK, rng=rng, col=scale(TIMBER, 0.72), rough=0.05)
        beam(g, [at(a, 0.5), at(c, 0.5)], 0.1, 0.12, mat=M_PLANK, rng=rng, col=scale(TIMBER, 0.8))
        for t in (0.5, 0.82):
            lashing(g, at(a, t), (0, 1, 0), 0.18, rng, turns=2)
    # Ladder up the -Z face.
    lb, lt = V(0, -0.1, -1.55), V(0, 4.6, -0.78)
    for s in (-0.24, 0.24):
        pole(g, lb + V(s, 0, 0), lt + V(s, 0, 0), 0.045, 0.04, rng, col=BARK, sides=6)
    for k in range(13):
        p = lb.lerp(lt, 0.05 + k * 0.074)
        pole(g, p - V(0.27, 0, 0), p + V(0.27, 0, 0), 0.025, 0.025, rng, col=scale(BARK, 0.9), sides=5, wobble=0.003)
    # Platform: joists then planks, ends ragged.
    for z in (-0.75, 0.0, 0.75):
        beam(g, [V(-1.15, 4.5, z), V(1.15, 4.5, z)], 0.12, 0.14, mat=M_PLANK, rng=rng, col=scale(TIMBER, 0.75))
    for k in range(10):
        x = -1.05 + k * 0.233
        if k in (4, 5):
            # The trapdoor gap the ladder comes through.
            board(g, V(x, 4.62, 0.45), (0, 0, 1), (0, 1, 0), 1.3, 0.22, 0.05, mat=M_PLANK, rng=rng,
                  col=scale(TIMBER, rng.uniform(0.7, 0.9)))
            continue
        board(g, V(x, 4.62, rng.uniform(-0.05, 0.05)), (0, 0, 1), (0, 1, 0), 2.25 + rng.uniform(-0.1, 0.1), 0.22,
              0.05, mat=M_PLANK, rng=rng, col=scale(TIMBER, rng.uniform(0.7, 0.92)))
    # Parapet: a ring of short sharpened stakes lashed to a rail (gap over the ladder).
    for sx, sz in ((0, -1), (0, 1), (-1, 0), (1, 0)):
        for k in range(8):
            t = -0.95 + k * 0.27
            x, z = (t, sz * 1.08) if sx == 0 else (sx * 1.08, t)
            if sz == -1 and abs(t) < 0.3:
                continue
            stake(g, rng, V(x, 4.45, z), rng.uniform(1.05, 1.25), 0.055, tip=0.16)
        a = V(-1.1, 5.1, sz * 1.08) if sx == 0 else V(sx * 1.08, 5.1, -1.1)
        c = V(1.1, 5.1, sz * 1.08) if sx == 0 else V(sx * 1.08, 5.1, 1.1)
        pole(g, a, c, 0.045, 0.04, rng, col=BARK, sides=6)
    # Lean-to hide roof over the back half; the banner pole stands on the axis in front of it.
    for sx in (-1, 1):
        pole(g, V(sx * 1.0, 4.6, 1.02), V(sx * 1.0, 6.5, 1.02), 0.05, 0.045, rng, col=BARK, sides=6)
        pole(g, V(sx * 1.0, 4.6, 0.2), V(sx * 1.0, 6.05, 0.2), 0.05, 0.045, rng, col=BARK, sides=6)
    nz = Noise(rng, 3, 2.0)
    sheet(g, [[tuple(V(-1.25 + 2.5 * u, 6.0 + 0.55 * t - 0.06 * math.sin(math.pi * u) * math.sin(math.pi * t),
                       0.05 + 1.1 * t)) for u in np.linspace(0, 1, 6)] for t in np.linspace(0, 1, 4)], M_HIDE,
          hide_col(nz, (3, 2)), tile=0.9, double=True)
    pole(g, V(0, 4.55, 0), V(0.02, 7.0, 0.0), 0.05, 0.04, rng, col=BARK, sides=6)
    skull(g, V(0, 5.2, -1.16), 2.2, rng, horns=1.0, yaw=math.pi)
    footing_stones(g, rng, (0, 0, 0), 1.0, 1.0, 10)
    return b


# ─────────────────────────────────────────────────────────────── great hall
def roof_side(g, rng, sx, x_eave, y_eave, y_ridge, z0, z1, nz, soot=True):
    """One hide roof slope from ridge (x=0) to the eave, sagging between the rafters."""
    grid = []
    nzs = 14
    for i in range(nzs + 1):
        z = z0 + (z1 - z0) * i / nzs
        row = []
        for j in range(7):
            t = j / 6
            x = sx * x_eave * t
            y = y_ridge + (y_eave - y_ridge) * t
            sag = 0.09 * abs(math.sin(math.pi * (z - z0) / 1.2)) * math.sin(math.pi * t)
            y += 0.07 * nz(V(x, 0, z) * 0.8) - sag
            row.append(tuple(V(x, y, z)))
        grid.append(row)
    sheet(g, grid, M_HIDE, hide_col(nz, (5, 3), (lambda u, v: 0.35 * smoothstep(0.15, 0.0, v)) if soot else None),
          tile=1.2, double=True)


def roof_weights(g, rng, x_eave, y_eave, y_ridge, z0, z1, n):
    """Ropes over the ridge with stones hanging at both eaves (holding the hides down)."""
    for k in range(n):
        z = z0 + (z1 - z0) * (k + 0.5) / n + rng.uniform(-0.1, 0.1)
        pts = [V(-x_eave * 1.02, y_eave + 0.03, z), V(-x_eave * 0.5, (y_eave + y_ridge) / 2 + 0.06, z),
               V(0, y_ridge + 0.1, z), V(x_eave * 0.5, (y_eave + y_ridge) / 2 + 0.06, z), V(x_eave * 1.02, y_eave + 0.03, z)]
        tube(g, pts, [0.018] * 5, 4, M_CLOTH, ROPE, tile=0.3, cap=False)
        for sx in (-1, 1):
            top = V(sx * x_eave * 1.02, y_eave + 0.02, z)
            bot = top + V(sx * 0.05, -0.35, 0)
            tube(g, [top, bot], [0.016, 0.016], 4, M_CLOTH, ROPE, tile=0.2, cap=False)
            r = rng.uniform(0.11, 0.16)
            stone(g, tuple(bot - V(0, r * 0.6, 0)), (r, r * 0.85, r), rng, detail=1,
                  col_fn=rock_col((0.72, 0.7, 0.66), moss=0.15), tile=0.4)


def log_wall_vertical(g, rng, a, b, h, r=0.16, gap=None, col=BARK):
    a, b = Vector(a), Vector(b)
    L = (b - a).length
    n = max(2, int(L / (2 * r * 0.95)))
    for k in range(n):
        p = a.lerp(b, (k + 0.5) / n)
        if gap and gap(p):
            continue
        hh = h + rng.uniform(-0.12, 0.12)
        pole(g, p - V(0, 0.25, 0), p + V(rng.uniform(-0.02, 0.02), hh, rng.uniform(-0.02, 0.02)), r, r * 0.92, rng,
             col=scale(col, rng.uniform(0.82, 1.06)), sides=6, segs=2)


def hold_hall(rng):
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 1.2)
    HX, HZ, WH = 5.5, 4.0, 2.75
    YR, YE, XE = 5.95, 2.45, 5.95
    # Raised earth floor + a fieldstone footing course all round.
    mound(g, (0, -0.25, 0), 6.6, 5.1, 0.55, rng, col_fn=earth_fn(rng, EARTH, 0.2), rings=6, seg=28, power=0.4)
    for k in range(64):
        t = k / 64
        per = 2 * (2 * HX + 2 * HZ)
        s = t * per
        if s < 2 * HX:
            p = V(-HX + s, 0, -HZ)
        elif s < 2 * HX + 2 * HZ:
            p = V(HX, 0, -HZ + s - 2 * HX)
        elif s < 4 * HX + 2 * HZ:
            p = V(HX - (s - 2 * HX - 2 * HZ), 0, HZ)
        else:
            p = V(-HX, 0, HZ - (s - 4 * HX - 2 * HZ))
        if p.z < -HZ + 0.01 and abs(p.x) < 1.2:
            continue
        r = rng.uniform(0.2, 0.3)
        out = V(math.copysign(0.12, p.x) if abs(abs(p.x) - HX) < 0.01 else 0, 0,
                math.copysign(0.12, p.z) if abs(abs(p.z) - HZ) < 0.01 else 0)
        stone(g, tuple(p + out + V(0, r * 0.3, 0)), (r * 1.2, r * 0.7, r), rng, detail=1,
              col_fn=rock_col((0.74, 0.72, 0.68), moss=0.25, ground=0.0), tile=0.45)
    door = lambda p: p.z < -HZ + 0.01 and abs(p.x) < 1.2
    log_wall_vertical(g, rng, V(-HX, 0, -HZ), V(HX, 0, -HZ), WH, gap=door)
    log_wall_vertical(g, rng, V(-HX, 0, HZ), V(HX, 0, HZ), WH)
    log_wall_vertical(g, rng, V(-HX, 0, -HZ), V(-HX, 0, HZ), WH)
    log_wall_vertical(g, rng, V(HX, 0, -HZ), V(HX, 0, HZ), WH)
    # Wall plates + corner posts.
    for z in (-HZ, HZ):
        beam(g, [V(-HX - 0.3, WH, z), V(HX + 0.3, WH, z)], 0.24, 0.24, mat=M_PLANK, rng=rng, col=scale(TIMBER, 0.75),
             rough=0.05)
    for x in (-HX, HX):
        beam(g, [V(x, WH + 0.2, -HZ - 0.3), V(x, WH + 0.2, HZ + 0.3)], 0.24, 0.24, mat=M_PLANK, rng=rng,
             col=scale(TIMBER, 0.72), rough=0.05)
    for sx in (-1, 1):
        for sz in (-1, 1):
            stake(g, rng, V(sx * HX, -0.5, sz * HZ), WH + 1.25, 0.26, tip=0.4)
    # Rafters: crossed pairs, the front and back pairs run past the ridge as horned finials.
    for k, z in enumerate(np.linspace(-HZ - 0.3, HZ + 0.3, 8)):
        ext = 0.9 if k in (0, 7) else 0.12
        for sx in (-1, 1):
            e = V(sx * (XE + 0.15), YE - 0.3, z)
            r_ = V(0, YR - 0.32, z)
            d = (r_ - e).normalized()
            pole(g, e, r_ + d * ext, 0.11, 0.08, rng, col=BARK, sides=6, segs=3)
        if k in (0, 7):
            lashing(g, V(0, YR - 0.05, z), (0, 0, 1), 0.16, rng, turns=3)
    pole(g, V(0, YR - 0.05, -HZ - 0.5), V(0, YR - 0.05, HZ + 0.5), 0.15, 0.13, rng, col=BARK, sides=8)
    for sx in (-1, 1):
        roof_side(g, rng, sx, XE, YE, YR, -HZ - 0.55, HZ + 0.55, nz)
    roof_weights(g, rng, XE, YE, YR, -HZ - 0.3, HZ + 0.3, 6)
    # Gables: horizontal split boards stepping in under the roof slope.
    for z, sgn in ((-HZ - 0.02, -1), (HZ + 0.02, 1)):
        y = WH + 0.15
        while y < YR - 0.25:
            half = XE * (YR - y) / (YR - YE) - 0.15
            board(g, V(0, y, z), (1, 0, 0), (0, 0, sgn), 2 * half, 0.3, 0.06, mat=M_PLANK, rng=rng,
                  col=scale(TIMBER, rng.uniform(0.6, 0.8)), jag=(0.04, 0.04))
            y += 0.29
    skull(g, V(0, 4.75, -HZ - 0.25), 5.2, rng, horns=1.6, yaw=math.pi)
    for sx in (-1, 1):
        tube(g, [V(sx * 0.7, 4.35, -HZ - 0.15), V(sx * 1.2, 4.0, -HZ - 0.4), V(sx * 1.35, 3.55, -HZ - 0.55)],
             [0.07, 0.05, 0.008], 6, M_STONE, BONE, tile=0.3)  # a pair of great tusks under it
    # Doorway: posts, lintel, a dark mouth, the hide curtain tied back, a threshold slab.
    for sx in (-1, 1):
        pole(g, V(sx * 1.3, -0.3, -HZ - 0.08), V(sx * 1.3, 2.95, -HZ - 0.08), 0.16, 0.15, rng, col=BARK, sides=8)
    beam(g, [V(-1.65, 2.95, -HZ - 0.1), V(1.65, 2.95, -HZ - 0.1)], 0.3, 0.26, mat=M_PLANK, rng=rng,
         col=scale(TIMBER, 0.7), rough=0.05)
    # No painted black mouth: the doorway opens into the real hall. Inside, a stone-ringed hearth
    # (its fire + light are spawned by ork_fortress.rs at HALL_HEARTH), a smoke-blackened hide
    # partition behind it that the firelight picks out, roof posts, a bench, hides on the walls.
    hc = V(0, 0, -1.3)
    for k in range(11):
        a = k / 11 * 2 * math.pi
        r = rng.uniform(0.16, 0.22)
        stone(g, tuple(hc + V(math.cos(a) * 0.72, 0.05, math.sin(a) * 0.72)), (r * 1.2, r * 0.7, r), rng, detail=1,
              col_fn=rock_col((0.42, 0.38, 0.34), moss=0.0, ground=0.0), tile=0.45)
    mound(g, (hc.x, -0.02, hc.z), 0.62, 0.62, 0.08, rng, col_fn=lambda p_, n_: scale((0.09, 0.075, 0.065), 0.8 + 0.4 * nz(p_ * 5)),
          rings=3, seg=14, power=0.6)
    for k in range(5):
        a = rng.uniform(0, 6.28)
        pole(g, hc + V(math.cos(a) * 0.5, 0.05, math.sin(a) * 0.5), hc + V(math.cos(a) * 0.08, 0.22, math.sin(a) * 0.08),
             0.06, 0.05, rng, col=(0.12, 0.1, 0.09), sides=6, segs=1)
    for x in np.linspace(-3.2, 3.2, 9):   # the partition: hides hung on a pole between the roof posts
        board(g, V(x, 1.5, 1.4 + 0.06 * math.sin(x * 3)), (1, 0, 0), (0, 0, -1), 0.82, 2.9, 0.04, mat=M_HIDE, rng=rng,
              col=scale(DARK_HIDE, rng.uniform(0.85, 1.15)), jag=(0.0, 0.12))
    pole(g, V(-3.6, 2.95, 1.4), V(3.6, 2.95, 1.4), 0.08, 0.07, rng, col=BARK, sides=6)
    for sx in (-1, 1):
        for z in (-1.9, 1.4):
            pole(g, V(sx * 2.6, -0.2, z), V(sx * 2.6, YE + 1.4, z), 0.17, 0.15, rng, col=scale(BARK, 0.8), sides=8)
        beam(g, [V(sx * 3.4, 0.42, -3.3), V(sx * 3.4, 0.42, 0.6)], 0.32, 0.12, mat=M_PLANK, rng=rng,
             col=scale(TIMBER, 0.7), rough=0.05)   # benches along the side walls
        for z in (-3.0, 0.3):
            pole(g, V(sx * 3.4, -0.1, z), V(sx * 3.4, 0.36, z), 0.07, 0.07, rng, col=BARK, sides=6, segs=1)
        for z in (-2.6, -0.4):
            board(g, V(sx * (HX - 0.25), 1.6, z), (0, 0, 1), (-sx, 0, 0), 1.1, 1.4, 0.03, mat=M_HIDE, rng=rng,
                  col=scale(HIDE, rng.uniform(0.75, 1.0)), jag=(0.06, 0.1))
    sheet(g, [[tuple(V(-1.15 + 0.55 * u - 0.15 * t * u, 2.85 - 2.6 * t, -HZ - 0.02 - 0.05 * u))
               for u in (0.0, 0.5, 1.0)] for t in np.linspace(0, 1, 5)], M_HIDE,
          lambda u, v: scale(DARK_HIDE, 0.8 + 0.25 * u), tile=0.6, double=True)
    slab(g, (0, 0.05, -HZ - 0.55), (2.4, 0.22, 0.8), quat_y(0.04), rng, mat=M_ROCK,
         col_fn=rock_col((0.7, 0.68, 0.64), moss=0.1), round_r=0.05)
    # Banner pole on the ridge (the flag rides (0, 7.3, 3.2)).
    pole(g, V(0, YR - 0.2, 3.2), V(0.02, 7.65, 3.2), 0.07, 0.055, rng, col=BARK, sides=6)
    lashing(g, V(0, YR + 0.05, 3.2), (0, 1, 0), 0.09, rng, turns=3)
    # Life against the walls: a firewood stack, a barrel, hides on a frame, bones.
    for k in range(4):
        for j in range(6 - k):
            z = -2.6 + j * 0.3 + k * 0.15
            pole(g, V(HX + 0.35, 0.12 + k * 0.24, z), V(HX + 1.1, 0.12 + k * 0.24, z + rng.uniform(-0.05, 0.05)),
                 0.12, 0.11, rng, col=scale(BARK, rng.uniform(0.8, 1.0)), sides=6, segs=1)
    frustum(g, 0.32, 0.3, -0.05, 0.85, 12, M_PLANK, scale(TIMBER, 0.7), tile=0.6, centre=(-HX - 0.5, 0, -2.6))
    for y in (0.15, 0.65):
        tube(g, [V(-HX - 0.5 + math.cos(a) * 0.33, y, -2.6 + math.sin(a) * 0.33) for a in np.linspace(0, 6.283, 13)],
             [0.018] * 13, 4, M_IRON, IRON, tile=0.3, cap=False)
    for k in range(5):
        x = rng.uniform(-4.5, 4.5)
        bone(g, V(x, 0.04, HZ + rng.uniform(0.6, 1.2)), V(x + rng.uniform(-0.4, 0.4), 0.06, HZ + rng.uniform(0.8, 1.5)),
             0.03, rng, col=OLD_BONE)
    return b


# ─────────────────────────────────────────────────────────────── spire
def crib(g, rng, c, w, y0, h, twist, rl=0.15, col=BARK):
    """A notched log crib: courses alternating X / Z, ends overhanging (the corner notches)."""
    rq = quat_y(twist)
    n = int(h / rl)
    for k in range(n):
        y = y0 + rl + k * rl
        along_x = k % 2 == 0
        for s in (-1, 1):
            off = s * (w / 2 - rl)
            ov = w / 2 + rng.uniform(0.18, 0.32)
            if along_x:
                a, b2 = V(-ov, y, off), V(ov, y, off)
            else:
                a, b2 = V(off, y, -ov), V(off, y, ov)
            pole(g, c + rq @ a, c + rq @ b2, rl, rl * 0.9, rng, col=scale(col, rng.uniform(0.78, 1.05)), sides=7,
                 segs=2, wobble=0.01)


def hold_spire(rng):
    b = Builder()
    g = G(b)
    mound(g, (0, -0.2, 0), 2.6, 2.6, 0.55, rng, col_fn=earth_fn(rng), rings=5, seg=20)
    footing_stones(g, rng, (0, 0, 0), 2.0, 2.0, 16, 0.14, 0.3)
    tiers = [(2.6, 2.4), (2.15, 2.3), (1.75, 2.2), (1.4, 2.1), (1.1, 2.0)]
    y = 0.4
    twist = 0.0
    goal = V(0.35, 0, -0.22)
    for i, (w, h) in enumerate(tiers):
        twist += rng.uniform(0.1, 0.2)
        c = goal * (i / (len(tiers) - 1)) + V(0, 0, 0)
        crib(g, rng, c, w, y - 0.1, h, twist)
        rq = quat_y(twist)
        # A plank deck between tiers, plank ends sticking out unevenly.
        for k in range(int((w + 0.5) / 0.24)):
            x = -(w + 0.5) / 2 + 0.12 + k * 0.24
            board(g, c + rq @ V(x, h - 0.02, 0) + V(0, y, 0), rq @ V(0, 0, 1), (0, 1, 0),
                  w + 0.35 + rng.uniform(0, 0.35), 0.22, 0.05, mat=M_PLANK, rng=rng,
                  col=scale(TIMBER, rng.uniform(0.62, 0.85)), jag=(0.03, 0.05))
        if i % 2 == 1:
            # A jutting beam stub with a skull swinging on a thong.
            d = quat_y(twist + 0.5) @ V(0, 0, 1)
            p0 = c + V(0, y + h * 0.6, 0)
            beam(g, [p0, p0 + d * (w / 2 + 0.9)], 0.13, 0.13, mat=M_PLANK, rng=rng, col=scale(TIMBER, 0.75),
                 jag=(0, 0.08))
            bot = cord(g, p0 + d * (w / 2 + 0.75), 0.5, rng, col=DARK_HIDE, r=0.015)
            skull(g, bot - V(0, 0.12, 0), 1.8, rng, horns=0.8, yaw=rng.uniform(0, 6))
        y += h
    # Raking props from the ground up to the first tier.
    for k in range(4):
        a = k / 4 * 2 * math.pi + 0.785
        d = V(math.cos(a), 0, math.sin(a))
        pole(g, d * 2.3 + V(0, -0.4, 0), d * 1.25 + V(0, 1.9, 0), 0.13, 0.11, rng, col=BARK, sides=7)
        lashing(g, d * 1.3 + V(0, 1.8, 0), (0, 1, 0), 0.15, rng, turns=2)
    top = V(goal.x, y, goal.z)
    # Crow platform + the iron crown, the brazier at (0.45, 12.05, -0.3).
    rq = quat_y(twist)
    for k in range(8):
        x = -0.85 + k * 0.243
        board(g, top + rq @ V(x, 0.06, 0), rq @ V(0, 0, 1), (0, 1, 0), 1.9, 0.23, 0.06, mat=M_PLANK, rng=rng,
              col=scale(TIMBER, rng.uniform(0.6, 0.8)))
    for k in range(7):
        a = k / 7 * 2 * math.pi + 0.3
        p = top + V(math.cos(a) * 0.9, 0.0, math.sin(a) * 0.9)
        tip = p + V(math.cos(a) * 0.12, rng.uniform(0.55, 0.85), math.sin(a) * 0.12)
        tube(g, [p - V(0, 0.15, 0), p.lerp(tip, 0.5), tip], [0.05, 0.035, 0.005], 6, M_IRON, IRON, tile=0.3)
    tube(g, [top + V(math.cos(a) * 0.9, 0.12, math.sin(a) * 0.9) for a in np.linspace(0, 6.283, 17)], [0.035] * 17, 5,
         M_IRON, IRON, tile=0.3, cap=False)
    bz = V(0.45, 12.05, -0.3)
    for k in range(3):
        a = k / 3 * 2 * math.pi
        tube(g, [V(bz.x + math.cos(a) * 0.42, top.y + 0.08, bz.z + math.sin(a) * 0.42), bz + V(0, -0.32, 0)],
             [0.03, 0.025], 5, M_IRON, IRON, tile=0.3)
    lathe(g, [(0.08, bz.y - 0.35), (0.34, bz.y - 0.2), (0.44, bz.y - 0.02), (0.4, bz.y - 0.04), (0.3, bz.y - 0.12),
              (0.0, bz.y - 0.12)], 14, (bz.x, 0, bz.z), M_IRON, lambda p, n: IRON, tile=0.4)
    for k in range(6):
        stone(g, tuple(bz + V(rng.uniform(-0.2, 0.2), -0.1, rng.uniform(-0.2, 0.2))), (0.09, 0.06, 0.09), rng,
              mat=M_STONE, detail=0, col_fn=lambda p, n: (0.06, 0.055, 0.05), cuts=0)
    # Flag pole lashed up the top tier's west side (the cloth rides (-0.8, 10.4, 0)).
    pole(g, V(-0.8, 9.0, 0), V(-0.8, 11.2, 0.02), 0.06, 0.05, rng, col=BARK, sides=6)
    for yy in (9.4, 10.0):
        lashing(g, V(-0.8, yy, 0), (0, 1, 0), 0.08, rng, turns=2)
    skull(g, top + V(0, 0.2, 0), 3.0, rng, horns=1.8, yaw=math.pi)
    return b


# ─────────────────────────────────────────────────────────────── longhouse
def hold_longhouse(rng):
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 1.4)
    HX, HZ, WH = 1.7, 2.7, 1.9
    mound(g, (0, -0.2, 0), 2.6, 3.5, 0.35, rng, col_fn=earth_fn(rng), rings=5, seg=22, power=0.4)
    rl = 0.14
    for k in range(int(WH / rl)):
        y = rl * 0.6 + k * rl
        if k % 2 == 0:
            for sx in (-1, 1):
                pole(g, V(sx * HX, y, -HZ - 0.3), V(sx * HX, y, HZ + 0.3), rl, rl * 0.92, rng,
                     col=scale(BARK, rng.uniform(0.8, 1.05)), sides=6, segs=2)
        else:
            for sz in (-1, 1):
                if sz == -1 and y < 1.55:
                    for a, c in ((-HX - 0.3, -0.5), (0.5, HX + 0.3)):
                        pole(g, V(a, y, sz * HZ), V(c, y, sz * HZ), rl, rl * 0.92, rng,
                             col=scale(BARK, rng.uniform(0.8, 1.05)), sides=6, segs=1)
                    continue
                pole(g, V(-HX - 0.3, y, sz * HZ), V(HX + 0.3, y, sz * HZ), rl, rl * 0.92, rng,
                     col=scale(BARK, rng.uniform(0.8, 1.05)), sides=6, segs=2)
    YR, YE, XE = 3.6, 1.75, 2.2
    for k, z in enumerate(np.linspace(-HZ - 0.2, HZ + 0.2, 6)):
        ext = 0.6 if k in (0, 5) else 0.08
        for sx in (-1, 1):
            e = V(sx * (XE + 0.1), YE - 0.24, z)
            r_ = V(0, YR - 0.26, z)
            pole(g, e, r_ + (r_ - e).normalized() * ext, 0.08, 0.06, rng, col=BARK, sides=6)
    pole(g, V(0, YR - 0.05, -HZ - 0.45), V(0, YR - 0.05, HZ + 0.45), 0.11, 0.1, rng, col=BARK, sides=7)
    for sx in (-1, 1):
        roof_side(g, rng, sx, XE, YE, YR, -HZ - 0.45, HZ + 0.45, nz)
    roof_weights(g, rng, XE, YE, YR, -HZ - 0.2, HZ + 0.2, 4)
    for z, sgn in ((-HZ - 0.02, -1), (HZ + 0.02, 1)):
        y = WH + 0.1
        while y < YR - 0.2:
            half = XE * (YR - y) / (YR - YE) - 0.1
            board(g, V(0, y, z), (1, 0, 0), (0, 0, sgn), 2 * half, 0.26, 0.05, mat=M_PLANK, rng=rng,
                  col=scale(TIMBER, rng.uniform(0.58, 0.78)))
            y += 0.25
    lbox(g, V(0, 0.8, -HZ + 0.1), (1.0, 1.6, 0.08), quat_y(0), M_HIDE, SOOT, tile=1.0)
    sheet(g, [[tuple(V(-0.5 + 0.5 * u, 1.55 - 1.5 * t, -HZ - 0.12 - 0.04 * u)) for u in (0.0, 0.5, 1.0)]
              for t in np.linspace(0, 1, 4)], M_HIDE, lambda u, v: scale(DARK_HIDE, 0.85 + 0.2 * u), tile=0.6,
          double=True)
    skull(g, V(0, 2.25, -HZ - 0.12), 2.6, rng, horns=1.2, yaw=math.pi)
    for k in range(3):
        bone(g, V(rng.uniform(-1.5, 1.5), 0.04, -HZ - rng.uniform(0.6, 1.2)),
             V(rng.uniform(-1.5, 1.5), 0.05, -HZ - rng.uniform(0.6, 1.4)), 0.025, rng, col=OLD_BONE)
    return b


# ─────────────────────────────────────────────────────────────── forge
def hold_forge(rng):
    b = Builder()
    g = G(b)
    mound(g, (0, -0.06, 0), 2.1, 1.8, 0.1, rng, col_fn=earth_fn(rng, (0.3, 0.27, 0.24), 0.3), rings=5, seg=20)
    # Dry-stone hearth: three courses of rough blocks round a coal bed.
    hc = V(0, 0, -0.35)
    for course in range(3):
        y = 0.14 + course * 0.25
        for k in range(14):
            t = (k + 0.5 * (course % 2)) / 14
            per = 2 * (1.5 + 1.1)
            s = t * per
            if s < 1.5:
                p = V(-0.75 + s, y, -0.55)
            elif s < 2.6:
                p = V(0.75, y, -0.55 + s - 1.5)
            elif s < 4.1:
                p = V(0.75 - (s - 2.6), y, 0.55)
            else:
                p = V(-0.75, y, 0.55 - (s - 4.1))
            slab(g, tuple(hc + p), (0.34, 0.24, 0.26), quat_y(rng.uniform(-0.2, 0.2)), rng, mat=M_ROCK,
                 col_fn=rock_col(scale((0.7, 0.68, 0.64), 0.8 - 0.25 * course), moss=0.0), round_r=0.05, cuts=1, res=(3, 3, 3))
    mound(g, tuple(hc + V(0, 0.55, 0)), 0.6, 0.42, 0.14, rng, mat=M_STONE,
          col_fn=lambda p, n: (0.05, 0.045, 0.04), rings=3, seg=14)
    for k in range(12):
        stone(g, tuple(hc + V(rng.uniform(-0.45, 0.45), 0.66, rng.uniform(-0.3, 0.3))), (0.07, 0.05, 0.07), rng,
              mat=M_STONE, detail=0, col_fn=lambda p, n: (0.09, 0.07, 0.06), cuts=1)
    # Stone chimney stub at the back corner, soot-black at the lip.
    for k in range(6):
        y = 0.85 + k * 0.22
        for a in range(4):
            q = quat_y(a * math.pi / 2 + k * 0.4)
            slab(g, tuple(V(-0.45, y, -0.6 - 0.35) + q @ V(0.18, 0, 0)), (0.16, 0.22, 0.36), q, rng, mat=M_ROCK,
                 col_fn=rock_col(mix((0.62, 0.6, 0.56), SOOT, 0.15 * k), moss=0.0), round_r=0.04, res=(3, 3, 3))
    # Bellows: two boards and a hide bag, nozzle into the hearth side.
    bc = V(1.25, 0.55, -0.35)
    for dy in (-0.14, 0.14):
        board(g, bc + V(0, dy, 0), (1, 0, 0), (0, 1, 0), 0.8, 0.45, 0.04, mat=M_PLANK, rng=rng, col=scale(TIMBER, 0.7))
    dome(g, bc + V(0, -0.12, 0), 0.24, quat_z(0), M_HIDE, lambda p, n: DARK_HIDE, tile=0.4, rings=3, seg=10,
         squash=1.1)
    tube(g, [bc + V(-0.4, 0, 0), bc + V(-0.6, -0.05, 0)], [0.05, 0.035], 6, M_IRON, IRON, tile=0.2)
    pole(g, bc + V(0.4, 0.14, 0), bc + V(0.9, 0.35, 0), 0.025, 0.025, rng, col=TIMBER, sides=5)
    # Anvil on its stump.
    ac = V(0.95, 0, 0.6)
    pole(g, ac + V(0, -0.3, 0), ac + V(0, 0.5, 0), 0.3, 0.27, rng, col=BARK, sides=10, segs=2)
    lbox(g, ac + V(0, 0.62, 0), (0.55, 0.2, 0.26), quat_y(0.2), M_IRON, IRON, tile=0.4)
    lbox(g, ac + V(0, 0.52, 0), (0.3, 0.12, 0.18), quat_y(0.2), M_IRON, IRON, tile=0.4)
    tube(g, [ac + quat_y(0.2) @ V(0.27, 0.66, 0), ac + quat_y(0.2) @ V(0.5, 0.64, 0)], [0.08, 0.01], 6, M_IRON, IRON,
         tile=0.2)
    tube(g, [ac + V(-0.1, 0.75, 0.05), ac + V(0.2, 0.74, 0.25)], [0.015, 0.015], 5, M_PLANK, TIMBER, tile=0.2)
    lbox(g, ac + V(-0.12, 0.76, 0.03), (0.14, 0.07, 0.07), quat_y(0.6), M_IRON, IRON, tile=0.2)
    # Quench barrel: staves, two iron hoops, black water.
    qc = (-1.15, 0, 0.5)
    frustum(g, 0.29, 0.31, -0.05, 0.68, 14, M_PLANK, scale(TIMBER, 0.65), tile=0.5, centre=qc)
    for y in (0.12, 0.52):
        tube(g, [V(qc[0] + math.cos(a) * 0.32, y, qc[2] + math.sin(a) * 0.32) for a in np.linspace(0, 6.283, 15)],
             [0.016] * 15, 4, M_IRON, IRON, tile=0.3, cap=False)
    lathe(g, [(0.0, 0.58), (0.28, 0.58)], 14, qc, M_TAR, lambda p, n: (0.03, 0.035, 0.035), tile=0.4)
    # Scrap iron and bar stock dumped by the hearth.
    for k in range(6):
        a = rng.uniform(0, 6.28)
        p = V(rng.uniform(-1.4, -0.6), 0.04 + 0.03 * k, rng.uniform(-1.3, -0.8))
        lbox(g, p, (rng.uniform(0.3, 0.7), 0.04, 0.06), quat_y(a), M_IRON, scale(IRON, rng.uniform(0.8, 1.2)), tile=0.3)
    return b


# ─────────────────────────────────────────────────────────────── pen / drum / rack / totem
def hold_pen(rng):
    b = Builder()
    g = G(b)
    HW = 2.3
    mound(g, (0.3, -0.06, 0.2), 2.3, 2.2, 0.12, rng, col_fn=earth_fn(rng, MUD, 0.65), rings=5, seg=22, edge=0.2)
    for k in range(9):
        r = rng.uniform(0.25, 0.6)
        mound(g, (rng.uniform(-1.6, 1.6), -0.02, rng.uniform(-1.6, 1.6)), r, r * 0.8, 0.06, rng,
              col_fn=earth_fn(rng, MUD, 0.85), rings=3, seg=10)
    posts = []
    for side in range(4):
        for i in range(5):
            if side == 0 and i in (2, 3):
                continue
            t = i / 4 * 2 - 1
            x, z = [(t * HW, -HW), (t * HW, HW), (-HW, t * HW), (HW, t * HW)][side]
            h = rng.uniform(1.0, 1.25)
            pole(g, V(x, -0.4, z), V(x + rng.uniform(-0.05, 0.05), h, z), 0.08, 0.07, rng, col=BARK, sides=6)
            posts.append((x, z))
    for y in (0.42, 0.85):
        runs = [(V(-HW, y, HW), V(HW, y, HW)), (V(-HW, y, -HW), V(-HW, y, HW)), (V(HW, y, -HW), V(HW, y, HW)),
                (V(-HW, y, -HW), V(-HW * 0.25, y, -HW)), (V(HW * 0.25, y, -HW), V(HW, y, -HW))]
        for a, c in runs:
            pole(g, a + V(0, rng.uniform(-0.04, 0.04), 0), c + V(0, rng.uniform(-0.04, 0.04), 0), 0.05, 0.045, rng,
                 col=scale(BARK, 0.9), sides=6)
        for x, z in posts:
            lashing(g, V(x, y, z), (0, 1, 0), 0.1, rng, turns=2)
    # Hollowed-log trough.
    tc = V(0.6, 0, 1.6)
    pole(g, tc + V(-0.6, 0.16, 0), tc + V(0.6, 0.16, 0), 0.2, 0.2, rng, col=BARK, sides=10, segs=1)
    lbox(g, tc + V(0, 0.34, 0), (1.05, 0.03, 0.26), quat_y(0), M_EARTH, (0.2, 0.17, 0.13), tile=0.5)
    return b


def hold_drum(rng):
    b = Builder()
    g = G(b)
    great_drum(g, rng, V(0, 0, 0))
    footing_stones(g, rng, (0, 0, 0), 0.75, 0.75, 5)
    return b


def hold_rack(rng):
    b = Builder()
    g = G(b)
    for sx in (-1, 1):
        pole(g, V(sx * 0.8, -0.4, 0), V(sx * 0.8, 1.55, 0), 0.075, 0.065, rng, col=BARK, sides=7)
        lashing(g, V(sx * 0.8, 1.42, 0), (0, 1, 0), 0.09, rng, turns=3)
        footing_stones(g, rng, (sx * 0.8, 0, 0), 0.2, 0.2, 3, 0.06, 0.1)
    pole(g, V(-1.0, 1.42, 0), V(1.0, 1.42, 0), 0.05, 0.05, rng, col=scale(BARK, 0.9), sides=6)
    for k in range(5):
        x = -0.62 + k * 0.31
        kind = k % 3
        foot = V(x + rng.uniform(-0.05, 0.05), 0.0, 0.35)
        if kind == 0:
            spear(g, foot, V(x, 1.95, -0.08), rng)
        elif kind == 1:
            top = V(x, 1.5, -0.05)
            tube(g, [foot, foot.lerp(top, 0.6), top], [0.03, 0.05, 0.09], 7, M_PLANK, scale(TIMBER, 0.75), tile=0.3)
            for j in range(4):
                a = j * 1.57
                p = foot.lerp(top, 0.9) + V(math.cos(a) * 0.08, 0, math.sin(a) * 0.08)
                tube(g, [p, p + V(math.cos(a) * 0.08, 0.02, math.sin(a) * 0.08)], [0.015, 0.002], 4, M_IRON, IRON,
                     tile=0.2)
        else:
            top = V(x, 1.35, -0.04)
            tube(g, [foot, top], [0.025, 0.025], 6, M_PLANK, scale(TIMBER, 0.7), tile=0.3)
            d = (top - foot).normalized()
            lbox(g, top + d * 0.3 + V(0.06, 0, 0), (0.22, 0.6, 0.02), quat_x(-math.atan2(d.z, d.y)), M_IRON,
                 scale(IRON, 1.2), tile=0.4)
    # A round shield leaning on the left post.
    rq = quat_x(-1.25) @ quat_y(0.3)
    disc_c = V(-1.15, 0.45, 0.25)
    for k in range(4):
        xx = -0.3 + 0.2 * (k + 0.5)
        half = math.sqrt(max(0.09 - xx * xx, 0.01))
        board(g, disc_c + rq @ V(xx, 0, 0), rq @ V(0, 0, 1), rq @ V(0, 1, 0), 2 * half, 0.19, 0.03, mat=M_PLANK,
              col=mix(DARK_HIDE, OCHRE, 0.3 * (k % 2)), rng=rng)
    dome(g, disc_c + rq @ V(0, 0.015, 0), 0.07, rq, M_IRON, lambda p, n: IRON, tile=0.2, rings=3, seg=10, squash=0.8)
    return b


def hold_totem(rng):
    b = Builder()
    g = G(b)
    totem(g, rng, V(0, 0, 0), 4.2, 0.0, beast="boar")
    mound(g, (0, -0.05, 0), 0.7, 0.7, 0.18, rng, col_fn=earth_fn(rng), rings=3, seg=12)
    return b


# ─────────────────────────────────────────────────────────────── the Blight
def toadstool(g, rng, foot, h, r, lean, cap_col, kind=0):
    foot = Vector(foot)
    top = foot + V(lean[0] * h, h, lean[1] * h)
    mid = foot.lerp(top, 0.5) + V(lean[0] * 0.15 * h, 0, lean[1] * 0.15 * h)
    stem = (0.78, 0.75, 0.62)
    tube(g, [foot - V(0, 0.05, 0), mid, top], [r * 0.32, r * 0.24, r * 0.2], 7, M_STONE, stem, tile=0.2,
         col_fn=lambda t: mix(scale(stem, 0.6), stem, t))
    nz = Noise(rng, 3, 4.0)
    ch = r * (0.75 if kind == 0 else 0.35)
    prof = [(r * 0.15, -0.02), (r * 0.7, -0.03), (r, 0.0), (r * 0.92, ch * 0.45), (r * 0.6, ch * 0.88), (0.0, ch)]

    def col(p, n):
        y = (p.y - top.y) / max(ch, 1e-3)
        if y < 0.0:
            return (0.5, 0.45, 0.36)  # gills
        wart = 1.0 if nz(p * 30) > 0.42 else 0.0
        c = mix(scale(cap_col, 0.65), cap_col, smoothstep(0.0, 0.7, y))
        return mix(c, (0.86, 0.84, 0.72), wart * 0.8)
    lathe(g, prof, 12, tuple(top), M_STONE, col, tile=0.2)


def blight_shroom(rng, variant):
    b = Builder()
    g = G(b)
    caps = [(0.38, 0.44, 0.24), (0.46, 0.38, 0.22), (0.3, 0.36, 0.26)]
    if variant == 0:
        # On a rotten log, half sunk in the mud, moss-dark.
        pole(g, V(-0.9, 0.05, -0.1), V(0.9, 0.12, 0.15), 0.22, 0.18, rng, col=(0.38, 0.34, 0.28), sides=9, segs=3,
             wobble=0.03)
        mound(g, (0, -0.05, 0), 1.2, 0.7, 0.1, rng, col_fn=earth_fn(rng, MUD, 0.6), rings=3, seg=14)
        for k in range(9):
            x = rng.uniform(-0.8, 0.8)
            z = 0.02 + rng.choice([-1, 1]) * rng.uniform(0.15, 0.3)
            toadstool(g, rng, V(x, 0.15, z), rng.uniform(0.12, 0.35), rng.uniform(0.06, 0.13),
                      (rng.uniform(-0.2, 0.2), (z) * 0.6), caps[k % 3], kind=k % 2)
    elif variant == 1:
        mound(g, (0, -0.05, 0), 0.75, 0.65, 0.22, rng, col_fn=earth_fn(rng, MUD, 0.5), rings=4, seg=14)
        for k in range(6):
            a = rng.uniform(0, 6.28)
            d = rng.uniform(0.0, 0.5)
            p = V(math.cos(a) * d, 0.2 - d * 0.3, math.sin(a) * d)
            toadstool(g, rng, p, rng.uniform(0.25, 0.6), rng.uniform(0.12, 0.24),
                      (math.cos(a) * 0.25, math.sin(a) * 0.25), caps[k % 3], kind=1)
    else:
        n = 11
        for k in range(n):
            a = k / n * 2 * math.pi + rng.uniform(-0.15, 0.15)
            d = 0.75 + rng.uniform(-0.1, 0.1)
            toadstool(g, rng, V(math.cos(a) * d, 0.0, math.sin(a) * d), rng.uniform(0.1, 0.3),
                      rng.uniform(0.05, 0.12), (rng.uniform(-0.15, 0.15), rng.uniform(-0.15, 0.15)), caps[k % 3],
                      kind=k % 2)
        bone(g, V(-0.2, 0.03, 0.1), V(0.3, 0.05, -0.15), 0.03, rng, col=OLD_BONE)
    return b


def blight_gibbet(rng):
    b = Builder()
    g = G(b)
    lean = rng.uniform(0.02, 0.05)
    base = V(0, -0.8, 0)
    top = V(-lean * 3, 3.25, 0)
    pole(g, base, top, 0.13, 0.11, rng, col=BARK, sides=8, segs=4)
    mound(g, (0, -0.05, 0), 0.75, 0.7, 0.22, rng, col_fn=earth_fn(rng), rings=3, seg=12)
    footing_stones(g, rng, (0, 0, 0), 0.45, 0.45, 7, 0.1, 0.18)
    arm0 = top + V(-0.15, -0.15, 0)
    arm1 = arm0 + V(1.6, 0.05, 0)
    beam(g, [arm0, arm1], 0.13, 0.15, mat=M_PLANK, rng=rng, col=scale(TIMBER, 0.72), rough=0.05, jag=(0, 0.06))
    beam(g, [top + V(0.0, -0.95, 0), arm0 + V(0.75, -0.05, 0)], 0.09, 0.1, mat=M_PLANK, rng=rng,
         col=scale(TIMBER, 0.68), rough=0.05)
    lashing(g, arm0 + V(0.12, 0, 0), (0, 1, 0), 0.15, rng, turns=3)
    # Chain: alternating links.
    hang = arm1 + V(-0.2, -0.08, 0)
    cy = 1.95
    y = hang.y
    k = 0
    while y > cy + 0.42:
        rot = quat_y(0.0 if k % 2 == 0 else math.pi / 2)
        pts = [V(hang.x, y, 0) + rot @ V(math.sin(a) * 0.035, -math.cos(a) * 0.06 - 0.06, 0)
               for a in np.linspace(0, 2 * math.pi, 9)]
        tube(g, pts, [0.011] * 9, 4, M_IRON, IRON, tile=0.2, cap=False)
        y -= 0.11
        k += 1
    # The cage: hoops and bars, bulging, and what is left inside.
    cc = V(hang.x, cy, 0)
    for yy, rr in ((0.42, 0.18), (0.0, 0.3), (-0.42, 0.24)):
        tube(g, [cc + V(math.cos(a) * rr, yy, math.sin(a) * rr) for a in np.linspace(0, 6.283, 15)], [0.016] * 15, 4,
             M_IRON, IRON, tile=0.3, cap=False)
    for j in range(8):
        a = j / 8 * 2 * math.pi
        pts = [cc + V(math.cos(a) * rr, yy, math.sin(a) * rr) for yy, rr in ((0.5, 0.05), (0.42, 0.18), (0.0, 0.3),
                                                                            (-0.42, 0.24), (-0.5, 0.0))]
        tube(g, pts, [0.014] * 5, 4, M_IRON, IRON, tile=0.3, cap=False)
    skull(g, cc + V(0.05, -0.05, 0.05), 1.0, rng, col=OLD_BONE, yaw=rng.uniform(0, 6))
    for j in range(5):
        a = j * 0.5 - 1.0
        bone(g, cc + V(-0.1, -0.15 - j * 0.05, -0.05), cc + V(0.15 * math.cos(a), -0.3 - j * 0.03, 0.15 * math.sin(a)),
             0.009, rng, col=OLD_BONE)
    bone(g, cc + V(0.2, -0.35, 0.1), cc + V(0.32, -0.95, 0.15), 0.015, rng, col=OLD_BONE)
    for j in range(4):
        x = cc.x + rng.uniform(-0.5, 0.5)
        z = rng.uniform(-0.5, 0.5)
        bone(g, V(x, 0.03, z), V(x + rng.uniform(-0.3, 0.3), 0.04, z + rng.uniform(-0.3, 0.3)), 0.016, rng,
             col=OLD_BONE)
    return b


def blight_effigy(rng):
    b = Builder()
    g = G(b)
    lean = (rng.uniform(-0.05, 0.05), rng.uniform(-0.04, 0.04))
    base = V(0, -0.6, 0)
    d = V(lean[0], 1, lean[1]).normalized()
    top = base + d * 2.9
    pole(g, base, top, 0.08, 0.065, rng, col=BARK, sides=7)
    cb = base + d * 2.2
    beam(g, [cb + V(-0.78, 0.05, 0), cb + V(0.78, -0.05, 0)], 0.08, 0.09, mat=M_PLANK, rng=rng,
         col=scale(TIMBER, 0.7), rough=0.06)
    lashing(g, cb, (0, 1, 0), 0.1, rng, turns=3)
    # Hides draped over the crossbar, ragged hems.
    nz = Noise(rng, 3, 2.0)
    grid = []
    for t in np.linspace(0, 1, 6):
        row = []
        for u in np.linspace(0, 1, 7):
            x = -0.72 + 1.44 * u
            drop = 0.05 + 1.25 * t * (0.8 + 0.25 * math.sin(u * 9.0 + rng.uniform(0, 0.3)))
            z = 0.1 * math.sin(math.pi * u) * t + 0.06 * nz(V(u * 4, t * 4, 0)) + 0.08
            row.append(tuple(cb + V(x * (1 - 0.25 * t), -drop, z * (1 if u > 0.5 else -1) * 0.5 + 0.04)))
        grid.append(row)
    sheet(g, grid, M_HIDE, hide_col(nz, (3, 2)), tile=0.7, double=True)
    skull(g, top + V(0, 0.08, 0), 2.6, rng, horns=1.3, yaw=rng.uniform(-0.3, 0.3))
    # War-paint band round the pole.
    tube(g, [cb + V(math.cos(a) * 0.075, -0.45, math.sin(a) * 0.075) for a in np.linspace(0, 6.283, 11)],
         [0.03] * 11, 4, M_CLOTH, WARP, tile=0.2, cap=False)
    for sx in (-1, 1):
        bot = cord(g, cb + V(sx * 0.7, 0.0, 0.0), rng.uniform(0.3, 0.5), rng, col=DARK_HIDE, r=0.012)
        for j in range(3):
            a = j * 2.1
            bone(g, bot + V(math.cos(a) * 0.03, 0, math.sin(a) * 0.03), bot + V(-math.cos(a) * 0.04, -0.22, 0), 0.012,
                 rng)
        feather(g, cb + V(sx * 0.6, -0.02, 0.05), rng)
    mound(g, (0, -0.05, 0), 0.5, 0.5, 0.16, rng, col_fn=earth_fn(rng), rings=3, seg=12)
    footing_stones(g, rng, (0, 0, 0), 0.32, 0.32, 6, 0.08, 0.14)
    return b


def blight_ribcage(rng):
    b = Builder()
    g = G(b)
    mound(g, (0, -0.12, 0.3), 1.7, 2.6, 0.32, rng, col_fn=earth_fn(rng, MUD, 0.55), rings=5, seg=22, edge=0.2)
    n = 7
    for k in range(n):
        z = -0.9 + k * 0.48
        stone(g, (0.0, 0.14, z), (0.16, 0.12, 0.2), rng, mat=M_STONE, detail=1,
              col_fn=lambda p, nn: scale(OLD_BONE, 0.8), cuts=1, tile=0.3)
        tube(g, [V(0, 0.2, z), V(0, 0.42, z + 0.05)], [0.05, 0.015], 5, M_STONE, scale(OLD_BONE, 0.8), tile=0.2)
        size = math.sin(math.pi * (k + 1) / (n + 1))
        for sx in (-1, 1):
            if rng.uniform() < 0.15:
                continue  # gone
            span = 1.0 + 0.6 * size
            hgt = 1.2 + 1.0 * size
            pts = [V(sx * 0.12, 0.12, z), V(sx * span * 0.75, hgt * 0.55, z + 0.05),
                   V(sx * span * 0.85, hgt * 0.9, z + 0.12), V(sx * span * 0.45, hgt * 1.05, z + 0.2)]
            if rng.uniform() < 0.3:
                pts = pts[:3]  # snapped
            rad = [0.07, 0.065, 0.055, 0.035][:len(pts)]
            tube(g, pts, rad, 7, M_STONE, OLD_BONE, tile=0.3,
                 col_fn=lambda t: mix(scale(OLD_BONE, 0.55), OLD_BONE, smoothstep(0.0, 0.3, t)))
    skull(g, V(0.1, 0.2, -1.65), 6.0, rng, col=OLD_BONE, horns=1.8, yaw=math.pi + 0.3)
    for k in range(4):
        x = rng.uniform(-1.4, 1.4)
        z = rng.uniform(-1.6, 2.4)
        bone(g, V(x, 0.03, z), V(x + rng.uniform(-0.5, 0.5), 0.05, z + rng.uniform(-0.5, 0.5)), 0.04, rng,
             col=OLD_BONE)
    return b


def blight_tarpit(rng):
    b = Builder()
    g = G(b)
    mound(g, (0, -0.03, 0), 1.65, 1.35, 0.16, rng, col_fn=earth_fn(rng, (0.32, 0.28, 0.24), 0.5), rings=5, seg=22,
          edge=0.22)
    nz = Noise(rng, 4, 1.5)
    # The tar: an irregular glossy sheet just under the rim's crest, faint slow ripples.
    verts = [V(0, 0.105, 0)]
    rings, seg = 5, 22
    for j in range(1, rings + 1):
        f = j / rings
        for i in range(seg):
            a = 2 * math.pi * i / seg
            e = 1.0 + 0.18 * nz(V(math.cos(a), 0, math.sin(a)) * 1.3)
            x, z = math.cos(a) * 1.15 * f * e, math.sin(a) * 0.92 * f * e
            y = 0.105 + 0.006 * math.sin(f * 9) - 0.05 * f ** 4
            verts.append(V(x, y, z))
    tris = [(0, 1 + (i + 1) % seg, 1 + i) for i in range(seg)]
    for j in range(rings - 1):
        r0, r1 = 1 + j * seg, 1 + (j + 1) * seg
        for i in range(seg):
            tris += [(r0 + i, r0 + (i + 1) % seg, r1 + (i + 1) % seg), (r0 + i, r1 + (i + 1) % seg, r1 + i)]
    smooth_mesh(g, verts, tris, M_TAR, lambda p, n: (0.022, 0.02, 0.018), 0.8, inside=(0, -10, 0))
    for k in range(5):
        a = rng.uniform(0, 6.28)
        d = rng.uniform(0.1, 0.7)
        dome(g, V(math.cos(a) * d, 0.09, math.sin(a) * d * 0.8), rng.uniform(0.03, 0.08), quat_y(0), M_TAR,
             lambda p, n: (0.03, 0.028, 0.025), tile=0.2, rings=3, seg=8, squash=0.7)
    # Bones breaking the surface: a rib arc, a half-sunk skull, a shank.
    tube(g, [V(-0.4, 0.05, -0.2), V(-0.25, 0.45, -0.15), V(0.05, 0.55, -0.1), V(0.25, 0.3, -0.05)],
         [0.04, 0.035, 0.03, 0.02], 6, M_STONE, OLD_BONE, tile=0.3,
         col_fn=lambda t: mix((0.08, 0.07, 0.06), OLD_BONE, smoothstep(0.0, 0.35, t)))
    skull(g, V(0.45, 0.07, 0.3), 2.4, rng, col=scale(OLD_BONE, 0.85), horns=0.9, yaw=rng.uniform(0, 6))
    bone(g, V(-0.6, 0.06, 0.45), V(-0.3, 0.3, 0.6), 0.03, rng, col=OLD_BONE)
    # A dead branch, tar-blackened at the waterline.
    pole(g, V(0.7, 0.05, -0.4), V(1.2, 0.6, -0.75), 0.05, 0.02, rng, col=(0.4, 0.36, 0.3), sides=6)
    return b


MODELS = {
    "hold_wall_a": hold_wall,
    "hold_wall_b": hold_wall,
    "hold_gate_frame": hold_gate_frame,
    "hold_gate_leaf_l": lambda rng: hold_gate_leaf(rng, 1.0),
    "hold_gate_leaf_r": lambda rng: hold_gate_leaf(rng, -1.0),
    "hold_tower": hold_tower,
    "hold_hall": hold_hall,
    "hold_spire": hold_spire,
    "hold_longhouse": hold_longhouse,
    "hold_forge": hold_forge,
    "hold_pen": hold_pen,
    "hold_drum": hold_drum,
    "hold_rack": hold_rack,
    "hold_totem": hold_totem,
    "blight_shroom_a": lambda rng: blight_shroom(rng, 0),
    "blight_shroom_b": lambda rng: blight_shroom(rng, 1),
    "blight_shroom_c": lambda rng: blight_shroom(rng, 2),
    "blight_gibbet": blight_gibbet,
    "blight_effigy": blight_effigy,
    "blight_ribcage": blight_ribcage,
    "blight_tarpit": blight_tarpit,
}

if __name__ == "__main__":
    clear_scene()
    objs = []
    only = set(sys.argv[sys.argv.index("--") + 1:]) if "--" in sys.argv else set()
    for i, (name, fn) in enumerate(MODELS.items()):
        if only and name not in only:
            continue
        bld = fn(np.random.default_rng(8800 + i))
        print(f"{name}: {bounds(bld)} tris={bld.tris()}")
        objs.append(bld.build(name, MATS))
    export_glb(OUT / ("ork_hold.glb" if not only else "ork_hold_partial.glb"), objs)
    print("ORK_HOLD_DONE")
