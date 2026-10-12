"""The castle town kit (zamek v2, phase 3d) -> town_kit.glb (src/town_kit.rs).

The town tells the story without words (docs/superpowers/specs/2026-10-11-zamek-v2-design.md
§3/§4): our fresh layer is whitewashed wattle-and-daub in dark oak timber framing on a fieldstone
plinth, thatch, plank, mud and straw, with the tools left out where they were last used; the
Crown's layer (Ch.7+) is crimson cloth, painted crates, soldiers' tents and the gallows. No church.

Scale: the hero is ~1.17u, 1u ~ 1.5 m. Houses: eaves ~2.0, ridge ~3.5, doors ~1.4 high.
Every piece: pivot on the ground (y = 0) at the centre of its footprint, front / door toward +Z.
(Exception: crown_banner_wall, origin on the wall face at the bracket, hangs down from y = 0.)
Footprint = x / z extent of the main body (props around it can reach a little further, see
town_kit_report.json, written next to the glb: tris + bounds per node). Heights are the top of the
geometry.

  node                 footprint x*z     top   notes
  town_granary         3.2 x 4.2         5.2   on 9 mushroom staddle stones, floor 0.84, eaves 2.9,
                                               ridge (along Z) 4.85; plank walls, thatch, loft door
                                               + hoist beam (sack on the rope) over the door gable,
                                               ladder up to the door, sacks / spilt grain / shovel,
                                               a thatcher's ladder on the east eave. Burns in Ch.8.
  town_smithy          4.6 x 3.4         4.3   open-front forge (front +Z open, plank roof, eaves
                                               2.25, ridge 3.55), stone hearth + hood + chimney at
                                               the back-left, bellows + lever, anvil on a stump,
                                               quench tub, workbench, weapon rack outside right
                                               (+X, z ~ 2.6), hanging anvil sign off the front-left
                                               post (x -2.3, board at y 1.45..1.9, z 2.0..2.6).
  town_tavern          6.4 x 4.6(+0.3)   6.6   "The Drowned Squire": two storeys, jettied upper
                                               floor (+0.3 over the front), eaves 4.1, ridge 6.0,
                                               stone chimney on the east gable; bracket sign (squire's helm
                                               sinking in waves, painted both faces) perpendicular
                                               to the facade on an iron arm at x -2.2: board 1.68 x
                                               1.29 at y 1.65..2.94, z 2.8..4.48; benches, a trestle
                                               table, barrels + tankards out front.
  town_maud_house      5.2 x 3.8         3.75  Maud's house; EDICT BOARD (pinned notices, the
                                               red-sealed edict) right of the door at x 1.9, z 2.45;
                                               tax chest + bench by the door.
  town_infirmary       7.2 x 3.6         3.3   low long house, eaves 1.85, ridge 3.2, open shutters,
                                               4 cots inside (no dark "void" panels: you see in),
                                               herb bundles under the eave; fenced herb garden
                                               x 3.9..7.0, z -1.6..1.6 (3 raised beds).
  town_firepit         r ~ 2.4           1.4   ring of stones, ash, charred logs, tripod + cauldron,
                                               three log benches.
  town_grave           1.4 x 2.6         1.5   the EMPTY grave of the drowned squire: fresh mound,
                                               edging stones, marker post (no cross) at the head
                                               (-Z) with a squire's helm hung on it, wildflowers,
                                               the gravedigger's spade left in the dirt.
  crown_banner_wall    0.95 wide         0     iron bracket + crimson gonfalon with a gold crown,
                                               hangs to y -2.1, cloth at z 0.12..0.3 (wall face z=0).
  crown_banner_pole    0.6 x 0.6         4.4   free-standing pole, crossbar banner, gilt finial.
  crown_crates         1.9 x 1.3         1.25  crimson-painted crates with gold crowns, a barrel.
  crown_tent           2.4 x 2.9         2.05  soldiers' ridge tent (ridge along Z, flaps tied open
                                               to +Z), crimson / linen stripes, pennant, guy ropes.
  crown_gallows        2.2 x 1.6         3.3   the wayside gallows + a nailed Crown edict and a
                                               crimson rag on the crossbeam.
  crown_depot          3.2 x 2.4         2.6   plank depot shed, open front, lean-to roof, crates,
                                               sacks, a crimson banner over the front beam.
  town_house_a         4.6 x 3.4         3.6   timber-frame cottage, thatch; woodpile + chopping
                                               block (left, -X).
  town_house_b         5.6 x 3.6         3.8   longer, plank gables; lean-to log store on +X, a tub.
  town_house_c         3.8 x 3.2         3.5   small cottage, board gables; bench, bucket, hurdle.
  town_house_d         4.8 x 3.6         3.7   cottage with a stone chimney on -X, washing line.
  town_carpenter       3.0 x 2.0         1.1   two trestles with a half-sawn log + frame saw, plank
                                               stack, shavings, an axe in a stump.
  town_archery         3.4 x 1.4         1.65  two straw butts on stands, painted rings, arrows.

  Spec v3 §2 (only castle buildings inside the walls; the podgrodzie grows outside the W gate on
  burgage plots). Street-gable houses: ridge along Z, the GABLE END + door to +Z = the road.
  town_street_house_a  4.4 x 7.6         4.85  thatch, boarded front gable with a loft door, front
                                               door + window, back door to the yard; bench, bucket.
  town_street_house_b  4.8 x 7.0         4.65  SHOP: plaster front gable, plank roof; shop window
                                               x 0.75..2.35 (from the left corner), its lower shutter
                                               folded down into a counter (y 0.75, out to z 4.12, two
                                               legs) with pots / cloth / loaves, the upper one
                                               propped up as an awning; barrel on +X.
  town_fence_wattle    3.0 (x -1.5..1.5) 1.1   woven hurdle between two stakes, along X.
  town_fence_wattle_gate                       same module, gap x 0.25..1.45, rod gate hung on the
                                               east post swung open into the plot (-Z).
  town_fence_picket    3.0               1.1   three posts, two rails, pointed pickets on +Z.
  town_fence_picket_gate                       ledged + braced picket gate, gap x 0.25..1.45, open -Z.
  town_garden          3.2 x 2.6         1.85  three beds along Z: cabbages, onions, bean tepee; hoe.
  town_woodpile        2.2 x 0.8         1.1   log stack under a plank pent, chopping block at +Z.
  town_shed            2.4 x 1.8         2.05  open-front plank shed, mono-pitch, BACK FLAT at -Z.
  town_coop            1.3 x 1.0         1.3   hen house on legs, ramp to +Z, two hens.
  town_outhouse        1.0 x 1.0         2.15  the privy, door ajar to +Z.
  town_dung            2.0 x 1.6         1.55  dung heap, straw on top, pitchfork stuck in.
  town_hayrick         r 1.25            3.3   beehive rick round a pole, ladder on +X.

  Lean-tos for INSIDE the walls: back face flat in the plane z = -D/2 (nothing behind it) to butt
  onto the curtain, mono-pitch plank roof from the back (high, under the 3.4 wall-walk) down to the
  front post line z = +D/2 (+0.45 eave), board side walls, open front toward +Z (the courtyard).
  castle_stable        7.2 x 3.4         3.05  back 3.0 / front 2.15; three stalls, plank
                                               partitions, hay racks + mangers, straw, a saddle.
  castle_barracks      7.6 x 3.6         3.15  back 3.1 / front 2.25; half-open front (plank parapet
                                               1.0, doorway x -1.3..0), three two-tier bunks, table +
                                               bench, shields + helms; spear rack outside +X.
  castle_store         5.6 x 3.2         2.95  back 2.9 / front 2.1; crates, sacks, barrels.
  castle_cartshed      6.4 x 3.8         3.05  back 3.0 / front 2.3; two-wheeled cart (shafts down
                                               to +Z), spare wheel, horse collar, sacks.

Built with the wayside_models.py toolkit (game coordinates, Y up). Materials by name: the kit's
scanned sets (s_timber framing, s_planks boards, s_thatch, s_stone plinths, s_cloth, s_hide,
s_iron, s_earth) + the new s_plaster whitewash (tools/blender_forest/plaster_set.sh). Vertex colour
carries the grime: splash-back at the wall feet, soot under the eaves, mossy old thatch at the
eaves, the painted signs / Crown colours.

    blender -b --factory-startup --python tools/blender_forest/town_kit.py
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.append(str(HERE))
_src = (HERE / "wayside_models.py").read_text(encoding="utf-8")
exec(compile(_src[:_src.index("\nMODELS = {")], str(HERE / "wayside_models.py"), "exec"))

from mathutils.geometry import tessellate_polygon  # noqa: E402

M_PLASTER = len(MATS)
MATS = MATS + ["s_plaster"]

UP = V(0, 1, 0)
TF = (0.5, 0.41, 0.32)          # dark oak framing
WOOD = (0.82, 0.74, 0.62)
BOARD = (0.7, 0.63, 0.54)       # weathered plank cladding
PLW = (1.0, 1.0, 1.0)           # limewash (the s_plaster albedo is already off-white, ~#d8d1c2)
GRIME = (0.76, 0.69, 0.6)       # a little splash-back mud at the wall foot
SOOT = (0.86, 0.83, 0.79)       # a breath of smoke under the eaves
THATCH = (0.9, 0.84, 0.72)
THATCH_OLD = (0.64, 0.62, 0.5)  # mossy, rotting eave
VOID = (0.03, 0.027, 0.025)     # dark interior seen through an opening
STONE_C = (0.84, 0.82, 0.78)
HESSIAN = (0.78, 0.66, 0.46)
IRON_D = (0.3, 0.3, 0.31)
CRIMSON = (0.6, 0.06, 0.07)
GOLD = (0.98, 0.74, 0.26)
LINEN = (1.02, 0.98, 0.88)
PAPER = (1.05, 1.0, 0.86)


# ─────────────────────────────────────────────────────────────── helpers
def yaw(t):
    """Rotation about Y taking local +X onto the horizontal direction t."""
    return quat_y(math.atan2(-t.z, t.x))


def face(g, pts, want, mat, col, tile=1.0):
    """Planar polygon whose winding (and so its front face) points along `want`."""
    pts = [Vector(p) for p in pts]
    cols = col if isinstance(col, list) else [col] * len(pts)
    if len(pts) > 4:
        # Triangulate (concave shapes too) so the exporter can build tangents.
        for tri in tessellate_polygon([pts]):
            face(g, [pts[i] for i in tri], want, mat, [cols[i] for i in tri], tile)
        return
    n = (pts[1] - pts[0]).cross(pts[2] - pts[0])
    if n.length < 1e-12:
        return
    if n.dot(Vector(want)) < 0:
        pts, cols = pts[::-1], cols[::-1]
    g.flat(pts, mat, cols, tile)


def decal(g, origin, u, v, n, pts2d, col, mat=M_FRUIT, off=0.004, tile=0.5):
    """A painted flat shape on a board face: 2D points in the (u, v) frame, lifted `off` along n."""
    O, U, Vv, N = Vector(origin), Vector(u), Vector(v), Vector(n)
    face(g, [O + U * a + Vv * b + N * off for a, b in pts2d], N, mat, col, tile)


def ellipse(cx, cy, rx, ry, a0, a1, k):
    return [(cx + rx * math.cos(a0 + (a1 - a0) * i / k), cy + ry * math.sin(a0 + (a1 - a0) * i / k)) for i in range(k + 1)]


def lathe(g, base, axis, profile, sides, mat, col, tile=0.5, col_fn=None, cap=True):
    a = Vector(axis).normalized()
    pts = [Vector(base) + a * h for h, _ in profile]
    tube(g, pts, [max(r, 0.003) for _, r in profile], sides, mat, col, tile=tile, col_fn=col_fn, cap=cap)


def wall_col(y, y0, y1, tint=None):
    c = mix(GRIME, PLW, smoothstep(y0, y0 + 0.45, y))
    c = mix(c, SOOT, 0.3 * smoothstep(y1 - 0.5, y1, y))
    return tuple(c[i] * tint[i] for i in range(3)) if tint else c


def barrel(g, rng, base, s=1.0, band=None):
    prof = [(0.0, 0.2), (0.12, 0.235), (0.3, 0.255), (0.48, 0.235), (0.6, 0.2)]
    lathe(g, base, (0, 1, 0), [(h * s, r * s) for h, r in prof], 10, M_TIMBER, scale((0.62, 0.5, 0.38), rng.uniform(0.85, 1.0)), tile=0.6)
    for h in (0.07, 0.3, 0.53):
        r = (0.22 if h != 0.3 else 0.258) * s
        pts = [V(base[0], base[1] + h * s, base[2]), V(base[0], base[1] + (h + 0.03) * s, base[2])]
        tube(g, pts, [r + 0.006, r + 0.006], 10, M_IRON, band if (band and h == 0.3) else (0.42, 0.4, 0.38), tile=0.4, cap=False)
    lathe(g, (base[0], base[1] + 0.6 * s - 0.01, base[2]), (0, 1, 0), [(0.0, 0.2 * s), (0.015, 0.0)], 10, M_TIMBER, (0.55, 0.45, 0.35), tile=0.5)


def sack(g, rng, c, lying=False):
    r = (0.24, 0.17, 0.2) if lying else (0.2, 0.27, 0.17)
    stone(g, c, r, rng, mat=M_CLOTH, detail=1, rough=0.1, cuts=0, flat_y=0.86, rot=quat_y(rng.uniform(0, 6.28)),
          col_fn=lambda p, n: scale(HESSIAN, 0.78 + 0.22 * max(n.y, 0.0)), tile=0.5)


def ladder(g, rng, foot, top, width=0.42, col=(0.72, 0.64, 0.52)):
    foot, top = Vector(foot), Vector(top)
    d = top - foot
    side = d.cross(UP).normalized()
    for s in (-1, 1):
        pole(g, foot + side * s * width / 2, top + side * s * width / 2, 0.03, 0.026, rng, col=col, sides=6, segs=2)
    n = max(2, int(d.length / 0.34))
    for k in range(1, n + 1):
        p = foot.lerp(top, k / (n + 0.6))
        pole(g, p - side * (width / 2 + 0.03), p + side * (width / 2 + 0.03), 0.018, 0.018, rng, col=scale(col, 0.92),
             sides=5, wobble=0.002, segs=1)


def door_leaf(g, rng, hinge, t, n, w, h, ang, col=(0.6, 0.5, 0.38)):
    """Plank door hinged at `hinge` (its foot), closed along +t; `ang` > 0 swings it in (toward -n)."""
    d = t * math.cos(ang) - n * math.sin(ang)
    nl = d.cross(UP)
    k = max(3, round(w / 0.22))
    bw = w / k
    for i in range(k):
        c = hinge + d * (bw * (i + 0.5)) + UP * (h / 2)
        board(g, c, (0, 1, 0), nl, h, bw * 0.97, 0.045, mat=M_PLANK, col=scale(col, rng.uniform(0.85, 1.05)), rng=rng,
              chamfer=0.0)
    for y in (0.22, h - 0.26):
        c = hinge + d * (w / 2) + UP * y + nl * 0.035
        beam(g, [c - d * (w / 2 - 0.04), c + d * (w / 2 - 0.04)], 0.12, 0.03, up=tuple(nl), mat=M_PLANK, rng=rng,
             col=scale(col, 0.8))


def shutters(g, rng, P, t, n, o, o_t, col=(0.58, 0.5, 0.4)):
    s0, s1 = o["s"] - o["w"] / 2, o["s"] + o["w"] / 2
    h = o["y1"] - o["y0"] - 0.02
    hw = o["w"] / 2
    for side, s in ((-1, s0), (1, s1)):
        a_ = o.get("swing", 2.25) + rng.uniform(-0.3, 0.15)
        d = t * (-side) * math.cos(a_) + n * math.sin(a_)
        hinge = P(s + side * 0.02, o["y0"] + 0.01, o_t + 0.1)
        nl = d.cross(UP)
        for k in range(2):
            c = hinge + d * (hw * (k + 0.5) / 2) + UP * (h / 2)
            board(g, c, (0, 1, 0), nl, h, hw / 2 * 0.96, 0.03, mat=M_PLANK, col=scale(col, rng.uniform(0.85, 1.05)), rng=rng,
                  chamfer=0.0)
        c = hinge + d * (hw / 2) + UP * (h * 0.5)
        beam(g, [c - d * (hw / 2 - 0.03), c + d * (hw / 2 - 0.03)], 0.09, 0.025, up=tuple(nl), mat=M_PLANK, rng=rng,
             col=scale(col, 0.78))


def wall(g, rng, a, b, y0, y1, ops=(), stud=1.0, rail=None, T=0.15, infill="plaster", brace=True, tcol=TF,
         ends=(True, False), bw=0.27, tint=None, bcol=BOARD):
    """A straight wall from ground point a=(x, z) to b, foot y0 (top of the plinth), wall plate y1.
    Outward = +n = t x up (walk a closed footprint clockwise seen from above: front left->right).
    Plaster infill sits in an oak frame (sill, plate, mid rail, studs <= `stud` apart, corner
    braces); "boards" clads it in vertical planks instead. `ops`: openings {s (centre along the
    wall), w, y0, y1, kind door|window|open, ajar, void, shutters}."""
    a = V(a[0], 0, a[1])
    b = V(b[0], 0, b[1])
    d = b - a
    L = d.length
    t = d / L
    n = t.cross(UP)
    q = yaw(t)

    def P(s, y, o=0.0):
        return a + t * s + UP * y + n * o

    rail = y0 + 0.95 if rail is None else rail
    ops = sorted(ops, key=lambda o: o["s"])
    xs = sorted({0.0, L} | {o["s"] - o["w"] / 2 for o in ops} | {o["s"] + o["w"] / 2 for o in ops})

    def op_at(s):
        for o in ops:
            if o["s"] - o["w"] / 2 < s < o["s"] + o["w"] / 2:
                return o
        return None

    u_off = a.x * 0.37 + a.z * 0.61
    for s0, s1 in zip(xs, xs[1:]):
        if s1 - s0 < 1e-3:
            continue
        o = op_at((s0 + s1) / 2)
        ys = [(y0, y1)] if o is None else [(y0, o["y0"]), (o["y1"], y1)]
        # Run past the corner INTO the neighbour wall's infill (its outer face is at +0.065), not
        # flush with it: a flush end cap is coplanar with that face and z-fights at every corner.
        e0 = -0.055 if s0 == 0.0 else 0.0
        e1 = 0.055 if s1 == L else 0.0
        sm = (s0 + e0 + s1 + e1) / 2
        for ya, yb in ys:
            if yb - ya < 0.02:
                continue
            if infill == "plaster":
                cuts = [ya, rail, yb] if ya < rail < yb else [ya, yb]
                for lo, hi in zip(cuts, cuts[1:]):
                    # Tuck the panel's top / bottom 1 cm inside the plates (their faces are at y0 / y1).
                    lo = lo + 0.01 if lo == y0 else lo
                    hi = hi - 0.01 if hi == y1 else hi
                    lbox(g, P(sm, (lo + hi) / 2, -0.01), (s1 + e1 - s0 - e0, hi - lo, T), q, M_PLASTER,
                         [wall_col(lo, y0, y1, tint), None, wall_col(hi, y0, y1, tint)], tile=1.7, grain=1,
                         u0=sm + u_off, v0=(lo + hi) / 2)
            else:
                lbox(g, P(sm, (ya + yb) / 2, -0.03), (s1 + e1 - s0 - e0, yb - ya, 0.05), q, M_PLANK, (0.22, 0.19, 0.16),
                     tile=1.0, grain=1)
                k = max(1, round((s1 - s0) / bw))
                w = (s1 - s0) / k
                for i in range(k):
                    s = s0 + w * (i + 0.5)
                    board(g, P(s, (ya + yb) / 2, 0.02), (0, 1, 0), n, yb - ya, w * 0.97, 0.035, mat=M_PLANK, rng=rng,
                          chamfer=0.0, col_fn=weathered(scale(bcol, rng.uniform(0.82, 1.05)), 0.7))

    def tb(p0, p1, w=0.16, h=0.15, fn=None):
        beam(g, [p0, p1], w, h, up=tuple(n), mat=M_TIMBER, col=scale(tcol, rng.uniform(0.82, 1.05)), col_fn=fn,
             chamfer=0.0, rng=rng)

    o_t = 0.03 if infill == "plaster" else 0.06
    tb(P(-0.08, y0 + 0.085, o_t), P(L + 0.08, y0 + 0.085, o_t), 0.17, 0.17)
    tb(P(-0.08, y1 - 0.085, o_t), P(L + 0.08, y1 - 0.085, o_t), 0.17, 0.17)
    post_fn = weathered(tcol, 0.72)
    if ends[0]:
        tb(P(-0.03, y0 + 0.17, o_t), P(-0.03, y1 - 0.17, o_t), 0.2, 0.2, post_fn)
    if ends[1]:
        tb(P(L + 0.03, y0 + 0.17, o_t), P(L + 0.03, y1 - 0.17, o_t), 0.2, 0.2, post_fn)
    jambs = []
    for o in ops:
        jambs += [o["s"] - o["w"] / 2 - 0.08, o["s"] + o["w"] / 2 + 0.08]
    fixed = sorted([0.0, L] + jambs)
    studs = []
    if stud:
        for p0, p1 in zip(fixed, fixed[1:]):
            k = int((p1 - p0) / stud + 0.85)
            for i in range(1, k):
                s = p0 + (p1 - p0) * i / k
                if op_at(s) is None:
                    studs.append(s)
    for s in jambs + studs:
        tb(P(s, y0 + 0.17, o_t), P(s, y1 - 0.17, o_t), 0.15, 0.16, post_fn)
    if infill == "plaster":
        cur = 0.0
        for o in ops:
            if o["y0"] < rail < o["y1"]:
                tb(P(cur, rail, o_t - 0.005), P(o["s"] - o["w"] / 2 - 0.08, rail, o_t - 0.005), 0.13, 0.14)
                cur = o["s"] + o["w"] / 2 + 0.08
        tb(P(cur, rail, o_t - 0.005), P(L, rail, o_t - 0.005), 0.13, 0.14)
        if brace:
            inner = sorted(jambs + studs)
            for corner, nxt in ((0.0, inner[0] if inner else L), (L, inner[-1] if inner else 0.0)):
                span = abs(nxt - corner)
                if span < 0.45 or op_at((corner + nxt) / 2) is not None:
                    continue
                sg = 1 if nxt > corner else -1
                tb(P(nxt - sg * 0.05, y0 + 0.2, o_t + 0.005),
                   P(corner + sg * 0.1, min(y0 + 0.2 + span * 1.2, y1 - 0.25), o_t + 0.005), 0.12, 0.14)
    for o in ops:
        s0, s1 = o["s"] - o["w"] / 2, o["s"] + o["w"] / 2
        # Head + sill timbers overlap the opening by 2 cm, so neither face lies in the plane of the
        # infill's reveal (y = o.y1 / o.y0): the old sill's top WAS that plane and z-fought through
        # the window.
        if o["y1"] < y1 - 0.2:
            tb(P(s0 - 0.13, o["y1"] + 0.055, o_t + 0.005), P(s1 + 0.13, o["y1"] + 0.055, o_t + 0.005), 0.15, 0.18)
        if o["y0"] > y0 + 0.2:
            tb(P(s0 - 0.13, o["y0"] - 0.04, o_t + 0.01), P(s1 + 0.13, o["y0"] - 0.04, o_t + 0.01), 0.12, 0.2)
        kind = o.get("kind", "window")
        if o.get("void", True):
            depth = -0.9 if kind == "door" else -0.1
            wid = o["w"] + (1.2 if kind == "door" else 0.04)
            lbox(g, P(o["s"], (o["y0"] + o["y1"]) / 2, depth), (wid, o["y1"] - o["y0"] + 0.04, 0.02), q, M_PLASTER, VOID,
                 tile=2.0)
        if kind == "door":
            door_leaf(g, rng, P(s0 + 0.01, o["y0"], -0.02), t, n, o["w"] - 0.02, o["y1"] - o["y0"] - 0.02,
                      o.get("ajar", 0.5))
        elif kind == "window":
            if o.get("shutters", True):
                shutters(g, rng, P, t, n, o, o_t)
            tb(P(o["s"], o["y0"] + 0.01, -0.02), P(o["s"], o["y1"] - 0.01, -0.02), 0.06, 0.07)
    return P, t, n, q, L


def plinth(g, rng, segs, h=0.25, T=0.3):
    """Fieldstone footing under the sill beams, damp-dark at the foot."""
    # Every other run owns the corners (L + T); the runs between stop 1 cm inside them (L - T + 0.02).
    # When every run reached past both corners, each end cap lay in the plane of the neighbour's
    # outer face and the two overlapping tops shared y = h: both z-fought at every corner.
    for i, (a, b) in enumerate(segs):
        a = V(a[0], 0, a[1])
        b = V(b[0], 0, b[1])
        d = b - a
        L = d.length
        t = d / L
        run = L + T if i % 2 == 0 else L - T + 0.02
        lbox(g, (a + b) / 2 + UP * (h / 2 - 0.1), (run, h + 0.2, T), yaw(t), M_STONE,
             [scale(STONE_C, 0.5), None, scale(STONE_C, 0.82)], tile=1.2, grain=1, u0=a.x + a.z, v0=0.0)


def loop(pts):
    return [(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]


def roof(g, rng, c, R, W, D, ye, yr, over=0.42, verge=0.32, thick=0.26, style="thatch", col_top=THATCH,
         col_eave=THATCH_OLD, spars=True):
    """Gable roof, ridge along local X (W long), slopes down to local +-Z (D wide between the wall
    lines) from the ridge yr to the eave ye at the wall line, overhanging by `over` / `verge`."""
    C = Vector(c)

    def X(x, y, z):
        return C + R @ V(x, y, z)

    th = math.atan2(yr - ye, D / 2)
    run = D / 2 + over
    Ls = (run + 0.12) / math.cos(th)
    Wx = W + 2 * verge
    plank = style == "boards"
    if plank:
        thick = 0.08
    for sz in (-1, 1):
        q = R @ quat_x(sz * th)
        nrm = R @ V(0, math.cos(th), sz * math.sin(th))
        zm = sz * (run - 0.12) / 2
        ym = yr - (sz * zm) * math.tan(th)
        cen = X(0, ym, zm) + nrm * (thick / 2)
        cl = [col_top, None, col_eave] if sz > 0 else [col_eave, None, col_top]
        lbox(g, cen, (Wx, thick, Ls), q, M_PLANK if plank else M_THATCH, cl, tile=0.85 if not plank else 1.2, grain=2,
             u0=sz * 0.37)
        ez = sz * run
        ey = ye - over * math.tan(th)
        if plank:
            # Overlapping board courses: a lip every ~0.4 down the slope.
            k = int(Ls / 0.4)
            for i in range(1, k + 1):
                f = i / (k + 0.3)
                zz = -sz * 0.12 + (ez + sz * 0.12) * f
                p = X(0, yr - (sz * zz) * math.tan(th), zz) + nrm * (thick + 0.012)
                lbox(g, p, (Wx, 0.03, 0.06), q, M_PLANK, scale(mix(col_top, col_eave, f), 0.8), tile=1.2, grain=0)
            for sx in (-1, 1):
                a_ = X(sx * (Wx / 2), yr + 0.12 * math.tan(th), -sz * 0.12) + nrm * 0.02
                e_ = X(sx * (Wx / 2), ey, ez) + nrm * 0.02
                beam(g, [a_, e_], 0.2, 0.04, up=tuple(R @ V(sx, 0, 0)), mat=M_PLANK, col=scale(col_top, 0.85), rng=rng,
                     mode="plank")
            continue
        e = X(0, ey, ez) + nrm * (thick * 0.42)
        xs = (-Wx / 2 - 0.04, -Wx / 2 + 0.06, -Wx / 2 + 0.32, Wx / 2 - 0.32, Wx / 2 - 0.06, Wx / 2 + 0.04)
        tube(g, [e + R @ V(x, 0, 0) for x in xs], [0.04, thick * 0.45, thick * 0.55, thick * 0.55, thick * 0.45, 0.04], 8,
             M_THATCH, col_eave, tile=0.7, uv_phase=rng.uniform(0, 2))
        for sx in (-1, 1):
            a_ = X(sx * (Wx / 2 - 0.03), yr + 0.12 * math.tan(th), -sz * 0.12) + nrm * (thick * 0.5)
            e_ = X(sx * (Wx / 2 - 0.03), ey, ez) + nrm * (thick * 0.5)
            tube(g, [a_, a_.lerp(e_, 0.1), a_.lerp(e_, 0.9), e_], [0.08, 0.13, 0.13, 0.08], 7, M_THATCH,
                 mix(col_top, col_eave, 0.4), tile=0.7)
    ry = yr + thick / math.cos(th) * (0.6 if plank else 0.85)
    if plank:
        for sz in (-1, 1):
            p = X(0, ry - 0.02, sz * 0.09)
            beam(g, [p - R @ V(Wx / 2 + 0.05, 0, 0), p + R @ V(Wx / 2 + 0.05, 0, 0)], 0.04, 0.22,
                 up=tuple(R @ V(0, math.cos(th), sz * math.sin(th))), mat=M_PLANK, col=scale(col_top, 0.75), rng=rng)
        return
    tube(g, [X(x, ry, 0) for x in (-Wx / 2 - 0.02, -Wx / 2 + 0.12, 0, Wx / 2 - 0.12, Wx / 2 + 0.02)],
         [0.05, 0.17, 0.19, 0.17, 0.05], 10, M_THATCH, scale(col_top, 0.86), tile=0.6)
    if spars:
        for x in np.linspace(-Wx / 2 + 0.3, Wx / 2 - 0.3, max(3, int(Wx / 0.9))):
            for sz in (-1, 1):
                a_ = X(x, ry + 0.05, sz * 0.08)
                tube(g, [a_, a_ + R @ V(0.0, -0.13, sz * 0.2)], [0.012, 0.012], 4, M_BARK, (0.85, 0.78, 0.66), tile=0.3)


def gable(g, rng, c, R, x, sx, D, ye, yr, T=0.15, style="plaster", tcol=TF, tint=None, loft=None, bcol=BOARD):
    """Gable triangle in the plane local x (outward local sx), base local z -D/2..D/2 at ye."""
    C = Vector(c)

    def X(x_, y, z):
        return C + R @ V(x_, y, z)

    nx = R @ V(sx, 0, 0)
    if style == "plaster":
        for off, want in ((T / 2 - 0.01, 1), (-T / 2 - 0.01, -1)):
            xx = x + sx * off
            top = wall_col(ye + 1.0, ye - 1.0, ye + 1.0, tint)
            face(g, [X(xx, ye - 0.02, -D / 2 - 0.06), X(xx, ye - 0.02, D / 2 + 0.06), X(xx, yr + 0.05, 0)], nx * want,
                 M_PLASTER, [wall_col(ye + 0.3, ye - 1, ye + 3, tint)] * 2 + [top], tile=1.7)
        xo = x + sx * 0.03
        up_ = tuple(nx)
        yc = ye + (yr - ye) * 0.45
        zc = (D / 2) * (yr - yc) / (yr - ye) - 0.1
        for p0, p1, w in (((xo, ye + 0.15, 0), (xo, yr - 0.12, 0), 0.15), ((xo, yc, -zc), (xo, yc, zc), 0.13),
                          ((xo, ye + 0.15, -D / 4), (xo, ye + (yr - ye) * 0.5 - 0.12, -D / 4), 0.13),
                          ((xo, ye + 0.15, D / 4), (xo, ye + (yr - ye) * 0.5 - 0.12, D / 4), 0.13)):
            beam(g, [X(*p0), X(*p1)], w, 0.15, up=up_, mat=M_TIMBER, col=scale(tcol, rng.uniform(0.82, 1.0)), rng=rng,
                 chamfer=0.0)
    else:
        for off, want in ((0.0, 1), (-0.06, -1)):
            xx = x + sx * off
            face(g, [X(xx, ye - 0.02, -D / 2 - 0.05), X(xx, ye - 0.02, D / 2 + 0.05), X(xx, yr + 0.04, 0)], nx * want,
                 M_PLANK, (0.2, 0.17, 0.14), tile=1.0)
        k = max(4, int(D / 0.26))
        for i in range(k):
            z = -D / 2 + (i + 0.5) * D / k
            if loft and abs(z - loft["z"]) < loft["w"] / 2:
                for ya, yb in ((ye, loft["y0"]), (loft["y1"], yr - abs(z) * (yr - ye) / (D / 2) + 0.02)):
                    if yb - ya > 0.04:
                        board(g, X(x + sx * 0.03, (ya + yb) / 2, z), (0, 1, 0), nx, yb - ya, D / k * 0.96, 0.035,
                              mat=M_PLANK, rng=rng, col=scale(bcol, rng.uniform(0.8, 1.02)), chamfer=0.0)
                continue
            ytop = yr - abs(z) * (yr - ye) / (D / 2) + 0.02
            board(g, X(x + sx * 0.03, (ye + ytop) / 2, z), (0, 1, 0), nx, ytop - ye, D / k * 0.96, 0.035, mat=M_PLANK,
                  rng=rng, col=scale(bcol, rng.uniform(0.8, 1.02)), chamfer=0.0)
    if loft:
        lz, lw, ly0, ly1 = loft["z"], loft["w"], loft["y0"], loft["y1"]
        lbox(g, X(x - sx * 0.06, (ly0 + ly1) / 2, lz), (0.02, ly1 - ly0, lw), R, M_PLASTER, VOID, tile=2.0)
        for y in (ly0 - 0.05, ly1 + 0.05):
            beam(g, [X(x + sx * 0.07, y, lz - lw / 2 - 0.1), X(x + sx * 0.07, y, lz + lw / 2 + 0.1)], 0.1, 0.12,
                 up=tuple(nx), mat=M_TIMBER, col=TF, rng=rng)
        # Loft door swung right out against the gable.
        hinge = X(x + sx * 0.1, ly0, lz + lw / 2)
        tdir = R @ V(0, 0, -1)
        door_leaf(g, rng, hinge, tdir, nx, lw - 0.04, ly1 - ly0 - 0.03, -2.6, col=(0.55, 0.47, 0.37))


def chimney(g, rng, base_xz, y_top, w=0.7, d=0.6, y0=0.0):
    x, z = base_xz
    lbox(g, V(x, (y0 + y_top) / 2, z), (w, y_top - y0, d), quat_y(0.0), M_STONE,
         [scale(STONE_C, 0.62), None, scale((0.55, 0.52, 0.5), 0.8)], tile=1.2, grain=1, u0=x, v0=0.0)
    slab(g, (x, y_top + 0.04, z), (w + 0.14, 0.09, d + 0.14), quat_y(rng.uniform(-0.05, 0.05)), rng, res=(2, 1, 2),
         round_r=0.02, rough=0.03, col_fn=rock_col((0.42, 0.4, 0.38)), tile=0.6)


def hurdle(g, rng, p0, p1, h=0.55, gap=0.42, rods=5):
    """A light woven hurdle (the toolkit's `wattle`, at a quarter of the triangles)."""
    p0, p1 = Vector(p0), Vector(p1)
    t = (p1 - p0).normalized()
    perp = UP.cross(t).normalized()
    n = max(2, round((p1 - p0).length / gap))
    stakes = [p0.lerp(p1, i / n) for i in range(n + 1)]
    for s_ in stakes:
        pole(g, s_ - UP * 0.15, s_ + UP * (h + rng.uniform(0.02, 0.06)), 0.024, 0.02, rng, col=(0.85, 0.78, 0.66), sides=4,
             wobble=0.004, segs=1)
    for r in range(rods):
        y = 0.08 + r * (h - 0.1) / (rods - 1)
        pts = [s_ + perp * (0.024 * (1 if (i + r) % 2 else -1)) + UP * y for i, s_ in enumerate(stakes)]
        tube(g, pts, [0.016] * len(pts), 3, M_BARK, scale((1.1, 1.0, 0.82), rng.uniform(0.75, 1.0)), tile=0.5, cap=False,
             uv_phase=rng.uniform(0, 3))


def bench(g, rng, c, yaw_a, L=1.3, h=0.42):
    q = quat_y(yaw_a)
    C = Vector(c)
    board(g, C + UP * h, q @ V(1, 0, 0), (0, 1, 0), L, 0.3, 0.06, mat=M_PLANK, col=scale(WOOD, rng.uniform(0.75, 0.9)), rng=rng)
    for sx in (-1, 1):
        for sz in (-1, 1):
            p = C + q @ V(sx * (L / 2 - 0.15), 0, sz * 0.09)
            pole(g, p + q @ V(sx * 0.05, -0.02, sz * 0.04), p + UP * (h - 0.02), 0.03, 0.028, rng, col=(0.62, 0.54, 0.44),
                 sides=5, segs=1)


def tankard(g, c, col=(0.6, 0.48, 0.36)):
    lathe(g, c, (0, 1, 0), [(0.0, 0.045), (0.12, 0.05), (0.13, 0.0)], 8, M_TIMBER, col, tile=0.3)


def crown_shape(cx, cy, s):
    pts = [(-0.22, -0.12), (0.22, -0.12), (0.24, 0.13), (0.11, 0.0), (0.0, 0.17), (-0.11, 0.0), (-0.24, 0.13)]
    return [(cx + x * s, cy + y * s) for x, y in pts]


def painted_crate(g, rng, c, size, yaw_a):
    q = quat_y(yaw_a)
    lbox(g, c, size, q, M_PLANK, scale(CRIMSON, rng.uniform(1.0, 1.25)), tile=0.6)
    for sy in (-1, 1):
        lbox(g, Vector(c) + q @ V(0, sy * (size[1] / 2 - 0.03), 0), (size[0] + 0.02, 0.06, size[2] + 0.02), q, M_PLANK,
             (0.42, 0.3, 0.22), tile=0.6)
    for sz in (-1, 1):
        o = Vector(c) + q @ V(0, 0, sz * size[2] / 2)
        decal(g, o, q @ V(sz, 0, 0), UP, q @ V(0, 0, sz), crown_shape(0, 0, min(size[0], size[1]) * 1.4), GOLD, off=0.012)


def banner_sheet(g, rng, top_l, top_r, drop, folds=0.05, swallow=True, crest=True, stripe=True):
    """A hanging crimson gonfalon from the bar top_l..top_r (cloth faces +Z / -Z), gilt crown +
    border; folds grow toward the hem."""
    A, B = Vector(top_l), Vector(top_r)
    wdt = (B - A).length
    ni, nj = 9, 7
    ph = rng.uniform(0, 3)
    grid = []
    for i in range(ni):
        u = i / (ni - 1)
        row = []
        for j in range(nj):
            v = j / (nj - 1)
            x = A.lerp(B, v)
            hem = drop * (1.0 - (0.22 * (1 - abs(2 * v - 1)) if swallow and u > 0.85 else 0.0))
            y = -hem * u
            if swallow and u == 1.0:
                y = -drop * (0.82 if 0.3 < v < 0.7 else 1.0) - (0.0 if abs(v - 0.5) > 0.2 else 0.0)
            zf = folds * (u ** 1.3) * math.sin(v * 9.0 + ph) + 0.02 * u
            row.append((x.x, x.y + y, x.z + zf))
        grid.append(row)
    sheet(g, grid, M_CLOTH, lambda u, v: scale(CRIMSON, 0.85 + 0.25 * (1 - u)), tile=0.6, double=True)
    mid = A.lerp(B, 0.5)
    if crest:
        for sz in (-1, 1):
            decal(g, mid + V(0, -drop * 0.3, 0), V(sz, 0, 0), UP, V(0, 0, sz), crown_shape(0, 0, wdt * 1.25), GOLD,
                  off=0.03 if sz > 0 else 0.03)
    if stripe:
        for sz in (-1, 1):
            for yy in (-drop * 0.08, -drop * 0.62):
                decal(g, mid + V(0, yy, 0), V(sz, 0, 0), UP, V(0, 0, sz),
                      [(-wdt / 2 + 0.02, -0.025), (wdt / 2 - 0.02, -0.025), (wdt / 2 - 0.02, 0.025), (-wdt / 2 + 0.02, 0.025)],
                      GOLD, off=0.03)


# ─────────────────────────────────────────────────────────────── 1. granary
def town_granary(rng):
    """Granary on staddle stones: ridge along Z, the door gable to +Z."""
    b = Builder()
    g = G(b)
    HX, HZ = 1.6, 2.1
    FL, YE, YR = 0.84, 2.9, 4.85
    for x in (-1.45, 0.0, 1.45):
        for z in (-1.8, 0.0, 1.8):
            frustum(g, 0.17, 0.11, -0.1, 0.62, 7, M_STONE, scale(STONE_C, rng.uniform(0.6, 0.72)), tile=0.8,
                    centre=(x, 0, z), jitter=0.012, rng=rng)
            stone(g, (x, 0.555, z), (0.32, 0.085, 0.32), rng, mat=M_STONE, detail=1, rough=0.05, cuts=0, flat_y=0.62,
                  col_fn=rock_col(scale(STONE_C, rng.uniform(0.72, 0.85)), moss=0.35), tile=0.8)
    for z in (-1.8, 0.0, 1.8):
        beam(g, [V(-1.78, 0.685, z), V(1.78, 0.685, z)], 0.2, 0.15, mat=M_TIMBER, col=scale(TF, 0.85), rng=rng)
    lbox(g, V(0, 0.795, 0), (2 * HX + 0.26, 0.09, 2 * HZ + 0.26), quat_y(0.0), M_PLANK, scale(WOOD, 0.7), tile=0.9, grain=2)
    pts = [(-HX, HZ), (HX, HZ), (HX, -HZ), (-HX, -HZ)]
    door = dict(s=HX, w=0.92, y0=FL, y1=FL + 1.42, kind="door", ajar=0.95)
    for i, (a, b_) in enumerate(loop(pts)):
        wall(g, rng, a, b_, FL, YE, [door] if i == 0 else [], stud=None, brace=False, infill="boards", bcol=BOARD)
    R = quat_y(math.pi / 2)
    roof(g, rng, (0, 0, 0), R, 2 * HZ, 2 * HX, YE, YR, over=0.5, verge=0.42)
    loft = dict(z=0.0, w=0.74, y0=3.08, y1=3.82)
    gable(g, rng, (0, 0, 0), R, -HZ, -1, 2 * HX, YE, YR, style="boards", loft=loft)
    gable(g, rng, (0, 0, 0), R, HZ, 1, 2 * HX, YE, YR, style="boards")
    # Hoist beam out of the door gable under the ridge, a pulley and a sack on the rope.
    beam(g, [V(0, 4.38, HZ - 0.5), V(0, 4.38, HZ + 1.05)], 0.17, 0.19, mat=M_TIMBER, col=scale(TF, 0.95), rng=rng)
    lbox(g, V(0, 4.2, HZ + 0.92), (0.1, 0.16, 0.16), quat_y(0.0), M_TIMBER, (0.42, 0.36, 0.3), tile=0.4)
    tube(g, [V(-0.04, 4.2, HZ + 0.92), V(0.04, 4.2, HZ + 0.92)], [0.075, 0.075], 10, M_PLANK, (0.5, 0.42, 0.34), tile=0.4)
    tube(g, [V(0, 4.13, HZ + 0.99), V(0.01, 3.2, HZ + 1.0), V(0, 2.42, HZ + 1.0)], [0.016] * 3, 5, M_CLOTH, ROPE, tile=0.3)
    tube(g, [V(0, 4.13, HZ + 0.85), V(0.05, 3.6, HZ + 0.4), V(0.1, 3.25, HZ + 0.12)], [0.016] * 3, 5, M_CLOTH, ROPE, tile=0.3)
    stone(g, (0, 2.12, HZ + 1.0), (0.2, 0.3, 0.17), rng, mat=M_CLOTH, detail=1, rough=0.1, cuts=0, flat_y=0.85,
          col_fn=lambda p, n: scale(HESSIAN, 0.8 + 0.2 * max(n.y, 0.0)), tile=0.5)
    lashing(g, V(0, 2.42, HZ + 1.0), (0, 1, 0), 0.07, rng, turns=2)
    # Ladder up to the door; a long thatcher's ladder against the east eave.
    ladder(g, rng, V(0.0, -0.03, HZ + 0.86), V(0.0, FL + 0.32, HZ + 0.1), width=0.5)
    ladder(g, rng, V(HX + 1.05, -0.03, 0.75), V(HX + 0.32, YE + 0.25, 0.55), width=0.44)
    # Sacks at the ladder foot, one in the doorway; spilt grain; a grain shovel; a barrel.
    for p, lying in (((0.78, 0.25, HZ + 0.62), False), ((1.15, 0.25, HZ + 0.38), False), ((0.95, 0.17, HZ + 1.0), True),
                     ((0.98, 0.52, HZ + 0.58), True), ((-0.22, FL + 0.26, HZ - 0.35), False)):
        sack(g, rng, p, lying)
    mound(g, (0.45, -0.02, HZ + 1.05), 0.55, 0.34, 0.05, rng, mat=M_EARTH, col_fn=lambda p, n: (0.92, 0.78, 0.48),
          rings=3, seg=12)
    mound(g, (0.0, -0.03, 0.2), 1.3, 1.7, 0.07, rng, mat=M_THATCH, col_fn=lambda p, n: (0.82, 0.74, 0.55), rings=3, seg=14)
    sh0, sh1 = V(-1.15, -0.02, HZ + 0.12), V(-1.32, 1.25, HZ + 0.02)
    pole(g, sh0 + V(0, 0.35, 0), sh1, 0.022, 0.02, rng, col=(0.72, 0.62, 0.5), sides=5, segs=1)
    lbox(g, sh0 + V(0, 0.17, 0.0), (0.24, 0.36, 0.03), quat_y(0.1) @ quat_x(0.1), M_PLANK, (0.66, 0.58, 0.48), tile=0.5)
    barrel(g, rng, (-0.95, 0.0, HZ + 0.78))
    return b


# ─────────────────────────────────────────────────────────────── 2. smithy
def anvil(g, rng, top, yaw_a=0.0):
    q = quat_y(yaw_a)
    T = Vector(top)
    lbox(g, T + q @ V(0, -0.16, 0), (0.2, 0.12, 0.17), q, M_IRON, IRON_D, tile=0.3)
    lbox(g, T + q @ V(0, -0.05, 0), (0.46, 0.11, 0.17), q, M_IRON, IRON_D, tile=0.3)
    lbox(g, T + q @ V(0, -0.22, 0), (0.32, 0.05, 0.24), q, M_IRON, scale(IRON_D, 0.85), tile=0.3)
    lbox(g, T + q @ V(-0.27, -0.03, 0), (0.1, 0.07, 0.13), q, M_IRON, IRON_D, tile=0.3)
    tube(g, [T + q @ V(0.22, -0.04, 0), T + q @ V(0.36, -0.03, 0), T + q @ V(0.48, -0.0, 0)], [0.07, 0.04, 0.01], 8, M_IRON,
         IRON_D, tile=0.3)


def town_smithy(rng):
    """Open-front forge: back + side walls timber-frame, the front (+Z) open on posts."""
    b = Builder()
    g = G(b)
    HX, HZ = 2.3, 1.7
    Y0, YE, YR = 0.22, 2.25, 3.55
    sooty = (0.92, 0.89, 0.84)
    pts = [(-HX, HZ), (HX, HZ), (HX, -HZ), (-HX, -HZ)]
    plinth(g, rng, loop(pts)[1:])
    win_r = dict(s=1.9, w=0.7, y0=1.0, y1=1.62)
    win_b = dict(s=1.0, w=0.62, y0=1.05, y1=1.6)
    wall(g, rng, pts[1], pts[2], Y0, YE, [win_r], tint=sooty)
    wall(g, rng, pts[2], pts[3], Y0, YE, [win_b], tint=sooty)
    wall(g, rng, pts[3], pts[0], Y0, YE, [], tint=sooty, ends=(True, True))
    # Open front: plate on two posts + knee braces, stone pads.
    for x in (-0.78, 0.78):
        slab(g, (x, 0.04, HZ), (0.34, 0.16, 0.34), quat_y(rng.uniform(0, 1)), rng, res=(2, 1, 2), round_r=0.03,
             rough=0.04, col_fn=rock_col(scale(STONE_C, 0.7)), tile=0.6)
        beam(g, [V(x, 0.1, HZ + 0.03), V(x, YE - 0.17, HZ + 0.03)], 0.2, 0.2, up=(0, 0, 1), mat=M_TIMBER,
             col_fn=weathered(TF, 0.7), rng=rng)
        for sx in (-1, 1):
            beam(g, [V(x, YE - 0.75, HZ + 0.03), V(x + sx * 0.55, YE - 0.17, HZ + 0.03)], 0.12, 0.14, up=(0, 0, 1),
                 mat=M_TIMBER, col=TF, rng=rng)
    beam(g, [V(-HX - 0.1, YE - 0.085, HZ + 0.03), V(HX + 0.1, YE - 0.085, HZ + 0.03)], 0.17, 0.17, up=(0, 0, 1),
         mat=M_TIMBER, col=scale(TF, 0.9), rng=rng)
    roof(g, rng, (0, 0, 0), quat_y(0.0), 2 * HX, 2 * HZ, YE, YR, over=0.45, verge=0.35, style="boards",
         col_top=(0.62, 0.55, 0.47), col_eave=(0.4, 0.36, 0.32))
    for x, sx in ((HX, 1), (-HX, -1)):
        gable(g, rng, (0, 0, 0), quat_y(0.0), x, sx, 2 * HZ, YE, YR, tint=sooty)
    # Hearth against the back wall, fire bed + embers, plastered hood, stone chimney through the roof.
    hx, hz = -0.75, -HZ + 0.62
    lbox(g, V(hx, 0.39, hz), (1.5, 0.78, 1.05), quat_y(0.0), M_STONE, [scale(STONE_C, 0.5), None, scale(STONE_C, 0.66)],
         tile=1.0, grain=1)
    mound(g, (hx, 0.77, hz + 0.05), 0.48, 0.32, 0.09, rng, mat=M_EARTH, col_fn=lambda p, n: (0.1, 0.09, 0.085), rings=3,
          seg=12)
    for k in range(6):
        stone(g, (hx + rng.uniform(-0.25, 0.25), 0.84, hz + rng.uniform(-0.12, 0.18)), (0.07, 0.04, 0.06), rng,
              mat=M_FRUIT, detail=0, rough=0.1, cuts=0, col_fn=lambda p, n: (1.0, 0.42, 0.08), tile=0.3)
    yh0, yh1 = 1.55, 2.4
    bot = [V(hx - 0.72, yh0, hz - 0.5), V(hx + 0.72, yh0, hz - 0.5), V(hx + 0.72, yh0, hz + 0.55), V(hx - 0.72, yh0, hz + 0.55)]
    top = [V(hx - 0.3, yh1, hz - 0.5), V(hx + 0.3, yh1, hz - 0.5), V(hx + 0.3, yh1, hz - 0.05), V(hx - 0.3, yh1, hz - 0.05)]
    ctr = V(hx, 2.0, hz)
    for i in range(4):
        quad = [bot[i], bot[(i + 1) % 4], top[(i + 1) % 4], top[i]]
        mid = (quad[0] + quad[1] + quad[2] + quad[3]) / 4
        face(g, quad, mid - ctr, M_PLASTER, [scale(SOOT, 0.7)] * 2 + [scale(SOOT, 0.45)] * 2, tile=1.4)
    chimney(g, rng, (hx, hz - 0.25), YR + 0.75, w=0.62, d=0.5, y0=yh1 - 0.05)
    # Bellows (left of the hearth, nozzle into its side) + lever on a post.
    bx0, bx1, by, bz = -2.15, -1.52, 0.78, hz + 0.05
    for x in (bx0 + 0.08, bx1 - 0.06):
        for z in (bz - 0.18, bz + 0.18):
            beam(g, [V(x, -0.05, z), V(x, by - 0.03, z)], 0.07, 0.07, mat=M_TIMBER, col=TF, rng=rng)
    lbox(g, V((bx0 + bx1) / 2, by, bz), (bx1 - bx0, 0.04, 0.48), quat_y(0.0), M_PLANK, (0.55, 0.47, 0.38), tile=0.5)
    tq = quat_z(-0.24)
    hinge = V(bx1, by + 0.03, bz)
    lbox(g, hinge + tq @ V(-(bx1 - bx0) / 2, 0.0, 0), (bx1 - bx0, 0.04, 0.48), tq, M_PLANK, (0.55, 0.47, 0.38), tile=0.5)
    tail = hinge + tq @ V(-(bx1 - bx0), 0, 0)
    for sz in (-1, 1):
        face(g, [V(bx1, by + 0.02, bz + sz * 0.22), V(bx0, by + 0.02, bz + sz * 0.22), V(tail.x, tail.y, bz + sz * 0.22)],
             (0, 0, sz), M_HIDE, (0.5, 0.36, 0.25), tile=0.5)
        face(g, [V(bx1, by + 0.02, bz + sz * 0.21), V(bx0, by + 0.02, bz + sz * 0.21), V(tail.x, tail.y, bz + sz * 0.21)],
             (0, 0, -sz), M_HIDE, (0.4, 0.3, 0.22), tile=0.5)
    tube(g, [V(bx1, by + 0.03, bz), V(-1.42, by + 0.02, bz)], [0.05, 0.035], 6, M_IRON, IRON_D, tile=0.3)
    beam(g, [V(-2.18, -0.05, bz + 0.5), V(-2.18, 1.62, bz + 0.5)], 0.1, 0.1, mat=M_TIMBER, col=TF, rng=rng)
    pole(g, V(-2.18, 1.66, bz - 0.15), V(-2.18, 1.72, bz + 1.15), 0.035, 0.03, rng, col=(0.66, 0.57, 0.46), sides=6)
    tube(g, [V(-2.18, 1.66, bz - 0.12), V(tail.x + 0.05, tail.y + 0.03, bz)], [0.012, 0.012], 4, M_CLOTH, ROPE, tile=0.3)
    tube(g, [V(-2.18, 1.72, bz + 1.12), V(-2.17, 1.2, bz + 1.13)], [0.012, 0.012], 4, M_CLOTH, ROPE, tile=0.3)
    # Coal heap.
    mound(g, (-1.85, -0.02, -HZ + 1.55), 0.42, 0.32, 0.26, rng, mat=M_EARTH, col_fn=lambda p, n: (0.11, 0.1, 0.095),
          rings=3, seg=12)
    # Anvil on a stump, hammer on it, tongs leaning; quench tub.
    ax, az = 0.35, 0.15
    pole(g, V(ax, -0.06, az), V(ax, 0.48, az), 0.27, 0.24, rng, mat=M_BARK, col=(0.72, 0.62, 0.52), sides=9, segs=2)
    lbox(g, V(ax, 0.481, az), (0.4, 0.004, 0.4), quat_y(0.3), M_TIMBER, (0.75, 0.62, 0.48), tile=0.4)
    anvil(g, rng, (ax, 0.78, az), 0.25)
    pole(g, V(ax - 0.05, 0.8, az + 0.02), V(ax + 0.22, 0.8, az + 0.18), 0.016, 0.014, rng, mat=M_TIMBER,
         col=(0.6, 0.5, 0.4), sides=5, segs=1)
    lbox(g, V(ax - 0.07, 0.83, az + 0.0), (0.06, 0.06, 0.13), quat_y(-0.55), M_IRON, IRON_D, tile=0.2)
    for s in (-0.02, 0.02):
        tube(g, [V(ax + 0.28, 0.0, az - 0.12 + s), V(ax + 0.22, 0.42, az - 0.2 + s), V(ax + 0.21, 0.5, az - 0.2)],
             [0.01] * 3, 4, M_IRON, IRON_D, tile=0.2)
    tx, tz = 1.2, -0.55
    lathe(g, (tx, 0.0, tz), (0, 1, 0), [(0.0, 0.3), (0.2, 0.32), (0.42, 0.33)], 10, M_TIMBER, (0.5, 0.42, 0.34), tile=0.5,
          cap=False)
    tube(g, [V(tx, 0.05, tz), V(tx, 0.4, tz)], [0.29, 0.31], 10, M_TIMBER, (0.35, 0.3, 0.25), tile=0.5, cap=False)
    tube(g, [V(tx, 0.3, tz), V(tx, 0.33, tz)], [0.335, 0.335], 10, M_IRON, IRON_D, tile=0.3, cap=False)
    face(g, [V(tx + 0.31 * math.cos(a), 0.37, tz + 0.31 * math.sin(a)) for a in np.linspace(0, 6.283, 11)[:-1]], UP, M_IRON,
         (0.07, 0.09, 0.1), tile=0.5)
    # Workbench along the east wall with tools on it.
    wx = HX - 0.42
    lbox(g, V(wx, 0.82, 0.2), (0.5, 0.07, 1.4), quat_y(0.0), M_PLANK, (0.6, 0.5, 0.4), tile=0.7, grain=2)
    for z in (-0.4, 0.8):
        for x in (wx - 0.18, wx + 0.18):
            beam(g, [V(x, -0.05, z), V(x, 0.79, z)], 0.07, 0.07, mat=M_TIMBER, col=TF, rng=rng)
    for k in range(4):
        z = -0.25 + k * 0.28
        lbox(g, V(wx - 0.05 + rng.uniform(-0.05, 0.05), 0.87, z), (0.26, 0.03, 0.05), quat_y(rng.uniform(-0.4, 0.4)),
             M_IRON, IRON_D, tile=0.2)
    # Weapon rack outside on the right: an A-trestle rail with spears, swords, an axe and a shield.
    rz = HZ + 0.95
    for x in (0.95, 2.25):
        for sz in (-1, 1):
            beam(g, [V(x, -0.05, rz + sz * 0.35), V(x, 1.08, rz)], 0.07, 0.07, mat=M_TIMBER, col=TF, rng=rng)
    beam(g, [V(0.85, 1.05, rz), V(2.35, 1.05, rz)], 0.07, 0.08, mat=M_TIMBER, col=TF, rng=rng)
    for x in (1.05, 1.3):
        p0, p1 = V(x, -0.02, rz + 0.42), V(x + 0.04, 2.05, rz - 0.06)
        pole(g, p0, p1, 0.022, 0.018, rng, mat=M_TIMBER, col=(0.62, 0.52, 0.4), sides=5, segs=2)
        dd = (p1 - p0).normalized()
        tube(g, [p1, p1 + dd * 0.08, p1 + dd * 0.28], [0.02, 0.045, 0.004], 4, M_IRON, (0.6, 0.6, 0.62), tile=0.2)
    for x in (1.6, 1.85):
        base = V(x, 0.02, rz + 0.33)
        tip_up = V(x + 0.02, 1.1, rz - 0.02)
        dd = (tip_up - base).normalized()
        q = Vector((0, 1, 0)).rotation_difference(dd)
        lbox(g, base + dd * 0.44, (0.055, 0.82, 0.012), q, M_IRON, (0.66, 0.66, 0.68), tile=0.3)
        lbox(g, base + dd * 0.86, (0.24, 0.035, 0.04), q, M_IRON, IRON_D, tile=0.2)
        tube(g, [base + dd * 0.88, base + dd * 1.04], [0.02, 0.02], 5, M_HIDE, (0.35, 0.24, 0.16), tile=0.2)
        lathe(g, base + dd * 1.04, tuple(dd), [(0.0, 0.035), (0.04, 0.035), (0.05, 0.0)], 6, M_IRON, IRON_D, tile=0.2)
    hp0, hp1 = V(2.1, -0.02, rz + 0.3), V(2.12, 1.02, rz + 0.02)
    pole(g, hp0, hp1, 0.024, 0.022, rng, mat=M_TIMBER, col=(0.6, 0.5, 0.4), sides=5, segs=1)
    lbox(g, hp1 + V(0.08, -0.07, 0.0), (0.2, 0.18, 0.025), quat_y(0.0), M_IRON, (0.6, 0.6, 0.62), tile=0.2)
    sc = V(2.45, 0.42, rz + 0.08)
    sq = quat_x(-0.25)
    tube(g, [sc + sq @ V(0, 0, -0.02), sc + sq @ V(0, 0, 0.02)], [0.36, 0.36], 12, M_PLANK, (0.55, 0.35, 0.22), tile=0.5)
    lathe(g, sc + sq @ V(0, 0, 0.02), tuple(sq @ V(0, 0, 1)), [(0.0, 0.08), (0.04, 0.05), (0.05, 0.0)], 8, M_IRON, IRON_D,
          tile=0.2)
    # The sign: a bracket off the front-left post, a painted board (anvil + hammer) hanging on rings.
    bxs, by_ = -HX - 0.06, 2.05
    beam(g, [V(bxs, by_, HZ), V(bxs, by_, HZ + 0.92)], 0.08, 0.08, mat=M_TIMBER, col=TF, rng=rng)
    beam(g, [V(bxs, by_ - 0.5, HZ + 0.02), V(bxs, by_ - 0.03, HZ + 0.5)], 0.06, 0.06, mat=M_TIMBER, col=TF, rng=rng)
    zc, yc = HZ + 0.52, 1.66
    for z in (zc - 0.22, zc + 0.22):
        tube(g, [V(bxs, by_ - 0.04, z), V(bxs, yc + 0.24, z)], [0.008, 0.008], 4, M_IRON, IRON_D, tile=0.2)
    lbox(g, V(bxs, yc, zc), (0.04, 0.46, 0.62), quat_y(0.0), M_PLASTER, (0.9, 0.82, 0.62), tile=0.6)
    lbox(g, V(bxs, yc + 0.24, zc), (0.06, 0.04, 0.66), quat_y(0.0), M_TIMBER, TF, tile=0.4)
    lbox(g, V(bxs, yc - 0.24, zc), (0.06, 0.04, 0.66), quat_y(0.0), M_TIMBER, TF, tile=0.4)
    anvil2d = [(-0.19, 0.04), (0.08, 0.04), (0.2, 0.02), (0.08, -0.02), (0.05, -0.06), (0.1, -0.13), (-0.12, -0.13),
               (-0.07, -0.06), (-0.1, -0.02), (-0.19, 0.0)]
    for sx in (-1, 1):
        o = V(bxs + sx * 0.02, yc, zc)
        uz = V(0, 0, -sx)
        decal(g, o, uz, UP, V(sx, 0, 0), anvil2d, (0.08, 0.08, 0.09))
        decal(g, o + V(0, 0.08, 0), uz, UP, V(sx, 0, 0), [(-0.02, 0.0), (0.02, 0.0), (0.0, 0.0), (0.12, 0.13), (0.09, 0.15)],
              (0.08, 0.08, 0.09))
        decal(g, o, uz, UP, V(sx, 0, 0), [(0.05, 0.1), (0.2, 0.16), (0.22, 0.12), (0.07, 0.06)], (0.08, 0.08, 0.09))
        decal(g, o, uz, UP, V(sx, 0, 0), [(0.17, 0.06), (0.25, 0.1), (0.21, 0.19), (0.13, 0.15)], (0.08, 0.08, 0.09))
    return b


# ─────────────────────────────────────────────────────────────── 3. tavern
def town_tavern(rng):
    """The Drowned Squire: two storeys, the upper one jettied out over the front."""
    b = Builder()
    g = G(b)
    HX, HZ = 3.2, 2.3
    J = 0.3
    Y0, Y1, Y2, YE, YR = 0.25, 2.15, 2.3, 4.1, 6.0
    pts = [(-HX, HZ), (HX, HZ), (HX, -HZ), (-HX, -HZ)]
    plinth(g, rng, loop(pts))
    door = dict(s=2.4, w=1.0, y0=Y0, y1=Y0 + 1.48, kind="door", ajar=0.75)
    ground_ops = [
        [door, dict(s=0.95, w=0.8, y0=0.95, y1=1.6), dict(s=4.5, w=0.95, y0=0.95, y1=1.62)],
        [dict(s=2.3, w=0.7, y0=1.0, y1=1.6)],
        [dict(s=1.6, w=0.6, y0=1.05, y1=1.55, shutters=False), dict(s=4.8, w=0.9, y0=Y0, y1=Y0 + 1.42, kind="door", ajar=0.0)],
        [dict(s=2.3, w=0.7, y0=1.0, y1=1.6)],
    ]
    for i, (a, b_) in enumerate(loop(pts)):
        wall(g, rng, a, b_, Y0, Y1, ground_ops[i])
    # Floor frame between the storeys: a rim beam on every wall line from inside the ground floor's
    # wall plate (Y1) up into the upper sill (Y2), set 3 cm behind the plates' faces. Without it the
    # 0.15 band between the plate and the upper sill was open all round: from the back and the
    # gables the upper storey floated over a slot of sky. On the front it blocks between the joists.
    for a, b_ in loop(pts):
        A, B = V(a[0], 0, a[1]), V(b_[0], 0, b_[1])
        t_ = (B - A).normalized()
        n_ = t_.cross(UP)
        yc = (Y1 + Y2) / 2 + 0.005
        beam(g, [A - t_ * 0.06 + UP * yc + n_ * 0.01, B + t_ * 0.06 + UP * yc + n_ * 0.01], Y2 - Y1 + 0.05, 0.15,
             up=tuple(n_), mat=M_TIMBER, col=scale(TF, 0.9), chamfer=0.0, rng=rng)
    # Jetty: joist ends + soffit, then the upper storey (front +J).
    for x in np.linspace(-HX + 0.1, HX - 0.1, 11):
        beam(g, [V(x, Y1 + 0.075, HZ - 0.3), V(x, Y1 + 0.075, HZ + J + 0.06)], 0.13, 0.15, mat=M_TIMBER, col=scale(TF, 0.85),
             rng=rng)
    lbox(g, V(0, Y1 + 0.005, HZ + J / 2), (2 * HX + 0.1, 0.02, J + 0.1), quat_y(0.0), M_PLANK, (0.4, 0.35, 0.3), tile=0.8)
    up = [(-HX, HZ + J), (HX, HZ + J), (HX, -HZ), (-HX, -HZ)]
    upper_ops = [
        [dict(s=0.9, w=0.75, y0=2.85, y1=3.5), dict(s=3.2, w=0.75, y0=2.85, y1=3.5, swing=2.6),
         dict(s=5.5, w=0.75, y0=2.85, y1=3.5)],
        [dict(s=2.5, w=0.7, y0=2.9, y1=3.45)],
        [dict(s=3.2, w=0.7, y0=2.9, y1=3.45, shutters=False)],
        [dict(s=1.8, w=0.7, y0=2.9, y1=3.45, swing=1.4)],
    ]
    for i, (a, b_) in enumerate(loop(up)):
        wall(g, rng, a, b_, Y2, YE, upper_ops[i], rail=Y2 + 0.85)
    D = 2 * HZ + J
    cz = J / 2
    roof(g, rng, (0, 0, cz), quat_y(0.0), 2 * HX, D, YE, YR, over=0.48, verge=0.38)
    for x, sx in ((HX, 1), (-HX, -1)):
        gable(g, rng, (0, 0, cz), quat_y(0.0), x, sx, D, YE, YR)
    chimney(g, rng, (HX + 0.38, -0.6), YR + 0.55, w=0.72, d=0.8)
    # The sign: a bracket sign PERPENDICULAR to the facade (the board in the YZ plane, painted on both
    # faces) so it reads down the street from either side: an iron arm with a scroll + strut off the
    # upper front at x = -2.2, a 1.68 x 1.29 board on rings. High-contrast paint on a pale ground: a
    # pale steel kettle helm (dark outline, red plume) going under dark blue-green waves.
    S = 1.5
    sx_ = -2.2
    zw = HZ + J + 0.06
    by_ = 3.08
    bw_, bh_ = 1.12 * S, 0.86 * S
    tube(g, [V(sx_, by_, zw - 0.05), V(sx_, by_, zw + bw_ + 0.3)], [0.03, 0.026], 6, M_IRON, IRON_D, tile=0.3)
    tube(g, [V(sx_, by_ - 0.85, zw), V(sx_, by_ - 0.45, zw + 0.42), V(sx_, by_ - 0.02, zw + 1.05)], [0.022] * 3, 5, M_IRON,
         IRON_D, tile=0.3)
    scroll = [V(sx_, by_ + 0.02 + 0.12 * math.sin(a), zw + bw_ + 0.2 + 0.12 * math.cos(a)) for a in np.linspace(-1.2, 3.6, 7)]
    tube(g, scroll, [0.016] * 7, 4, M_IRON, IRON_D, tile=0.2, cap=False)
    zc, yc = zw + 0.14 + bw_ / 2, by_ - 0.14 - bh_ / 2
    for z in (zc - 0.4 * S, zc + 0.4 * S):
        tube(g, [V(sx_, by_ - 0.02, z), V(sx_, yc + bh_ / 2 + 0.02, z)], [0.014, 0.014], 4, M_IRON, IRON_D, tile=0.2)
    lbox(g, V(sx_, yc, zc), (0.05, bh_, bw_), quat_y(0.0), M_FRUIT, (0.92, 0.87, 0.74), tile=0.8)
    for dy, dz, sy, sz in ((bh_ / 2, 0, 0.06, bw_ + 0.08), (-bh_ / 2, 0, 0.06, bw_ + 0.08), (0, bw_ / 2, bh_, 0.06),
                           (0, -bw_ / 2, bh_, 0.06)):
        lbox(g, V(sx_, yc + dy, zc + dz), (0.08, sy, sz), quat_y(0.0), M_TIMBER, (0.26, 0.2, 0.16), tile=0.4)
    hw, hh = bw_ / 2 - 0.035, bh_ / 2 - 0.035

    def rot(pts, dx=0.0, dy=0.0, k=S):
        c_, s_ = math.cos(0.3), math.sin(0.3)
        return [((x * c_ - y * s_ + dx) * k, (x * s_ + y * c_ + dy) * k) for x, y in pts]

    for s in (-1, 1):
        o = V(sx_ + s * 0.025, yc, zc)
        u = V(0, 0, -s)
        n_ = V(s, 0, 0)
        dark = (0.06, 0.065, 0.075)
        decal(g, o, u, UP, n_, rot(ellipse(0.05, -0.02, 0.335, 0.325, 0.0, math.pi, 12)), dark, off=0.002)
        decal(g, o, u, UP, n_, rot(ellipse(0.05, -0.02, 0.3, 0.29, 0.0, math.pi, 12)), (0.74, 0.77, 0.82), off=0.003)
        decal(g, o, u, UP, n_, rot(ellipse(0.0, 0.0, 0.06, 0.16, 0.3, 2.6, 5), -0.04, 0.04), (0.97, 0.98, 1.0), off=0.0035)
        decal(g, o, u, UP, n_, rot([(-0.44, -0.08), (0.46, -0.11), (0.5, -0.0), (-0.46, 0.02)], 0.05, -0.02), dark, off=0.004)
        decal(g, o, u, UP, n_, rot([(-0.035, 0.22), (0.035, 0.22), (0.035, 0.31), (-0.035, 0.31)], 0.05, -0.02), dark,
              off=0.0045)
        plume = [(-0.06, 0.24), (0.0, 0.3), (-0.12, 0.4), (-0.34, 0.43), (-0.24, 0.34)]
        decal(g, o, u, UP, n_, [((x * 1.2 + 0.08) * S, (y * 1.1 - 0.02) * S) for x, y in plume], (0.8, 0.05, 0.035),
              off=0.005)
        # Three bands of waves over the lower half, pointed crests, darkest at the bottom; foam lines.
        for k, (base_y, amp, colw, ph) in enumerate(((-0.06, 0.07, (0.07, 0.32, 0.34), 0.0),
                                                     (-0.2, 0.06, (0.04, 0.23, 0.26), 1.4),
                                                     (-0.33, 0.05, (0.02, 0.14, 0.17), 0.6))):
            m = 9
            topl = []
            for j in range(m + 1):
                x = -hw + 2 * hw * j / m
                cr = abs(math.sin((x / S * 5.6 + ph)))
                topl.append((x, (base_y + amp * (cr ** 0.6) - amp * 0.4) * S))
            for j in range(m):
                (x0, y0), (x1, y1) = topl[j], topl[j + 1]
                decal(g, o, u, UP, n_, [(x0, -hh), (x1, -hh), (x1, y1), (x0, y0)], colw, off=0.006 + k * 0.001)
                decal(g, o, u, UP, n_, [(x0, y0 - 0.018), (x1, y1 - 0.018), (x1, y1 + 0.008), (x0, y0 + 0.008)],
                      (0.95, 0.97, 0.98), off=0.0065 + k * 0.001)
        for bx, by, r in ((0.32, 0.18, 0.028), (0.36, 0.27, 0.02), (0.3, 0.34, 0.015)):
            decal(g, o, u, UP, n_, ellipse(bx * S, by * S, r * S, r * S, 0, 2 * math.pi, 7)[:-1], (0.9, 0.95, 0.98), off=0.004)
    # Outside: benches against the front, a trestle table with benches, barrels, tankards.
    bench(g, rng, V(-1.6, 0.0, HZ + 0.45), 0.0, L=1.6)
    tq = quat_y(0.08)
    tc = V(1.15, 0.0, HZ + 1.45)
    lbox(g, tc + UP * 0.78, (1.7, 0.06, 0.7), tq, M_PLANK, scale(WOOD, 0.82), tile=0.7, grain=0)
    for sx in (-1, 1):
        for a in (-1, 1):
            p = tc + tq @ V(sx * 0.65, 0, 0)
            beam(g, [p + tq @ V(0, -0.02, a * 0.28), p + tq @ V(0, 0.76, 0)], 0.07, 0.07, mat=M_TIMBER, col=TF, rng=rng)
    bench(g, rng, tc + tq @ V(0, 0, 0.62), 0.08, L=1.6)
    bench(g, rng, tc + tq @ V(0, 0, -0.6), 0.08, L=1.6)
    for p in (tc + tq @ V(-0.4, 0.81, 0.1), tc + tq @ V(0.15, 0.81, -0.12), tc + tq @ V(0.55, 0.81, 0.15)):
        tankard(g, p)
    barrel(g, rng, (-3.0, 0.0, HZ + 0.62))
    barrel(g, rng, (-2.45, 0.0, HZ + 0.7))
    barrel(g, rng, (-2.75, 0.6, HZ + 0.66), 0.92)
    tankard(g, V(-2.75, 1.15, HZ + 0.66))
    mound(g, (1.2, -0.03, HZ + 1.3), 1.6, 1.0, 0.04, rng, mat=M_THATCH, col_fn=lambda p, n: (0.8, 0.72, 0.52), rings=3, seg=14)
    return b


# ─────────────────────────────────────────────────────────────── houses
def house(g, rng, W, D, ye, yr, ops, gstyle=("plaster", "plaster"), roof_style="thatch", tint=None, over=0.42,
          stud=1.0, plinth_h=0.25):
    HX, HZ = W / 2, D / 2
    pts = [(-HX, HZ), (HX, HZ), (HX, -HZ), (-HX, -HZ)]
    plinth(g, rng, loop(pts))
    for i, (a, b_) in enumerate(loop(pts)):
        wall(g, rng, a, b_, plinth_h, ye, ops[i], stud=stud, tint=tint)
    R = quat_y(0.0)
    roof(g, rng, (0, 0, 0), R, W, D, ye, yr, over=over, style=roof_style)
    gable(g, rng, (0, 0, 0), R, HX, 1, D, ye, yr, style=gstyle[1], tint=tint)
    gable(g, rng, (0, 0, 0), R, -HX, -1, D, ye, yr, style=gstyle[0], tint=tint)


def woodpile(g, rng, c, L=1.6, rows=4):
    C = Vector(c)
    for x in (-L / 2 - 0.05, L / 2 + 0.05):
        pole(g, C + V(x, -0.2, 0), C + V(x, 0.95, 0), 0.04, 0.035, rng, col=(0.7, 0.62, 0.5), sides=5, segs=1)
    for r in range(rows):
        n = int(L / 0.21)
        for k in range(n):
            x = -L / 2 + (k + 0.5) * L / n + (0.05 if r % 2 else 0.0)
            if abs(x) > L / 2:
                continue
            p = C + V(x, 0.1 + r * 0.17, 0)
            pole(g, p + V(0, 0, -0.22), p + V(0, 0, 0.22), 0.09, 0.09, rng, col=(0.7, 0.6, 0.48), sides=5, segs=1,
                 wobble=0.0)
            face(g, [p + V(0.075 * math.cos(a), 0.075 * math.sin(a), 0.226) for a in np.linspace(0, 6.283, 6)[:-1]],
                 (0, 0, 1), M_TIMBER, (0.95, 0.8, 0.6), tile=0.2)


def chopping_block(g, rng, c):
    C = Vector(c)
    pole(g, C + V(0, -0.05, 0), C + V(0, 0.42, 0), 0.24, 0.22, rng, mat=M_BARK, col=(0.72, 0.62, 0.52), sides=8, segs=1)
    lbox(g, C + V(0, 0.421, 0), (0.36, 0.004, 0.36), quat_y(0.6), M_TIMBER, (0.8, 0.68, 0.52), tile=0.4)
    p0 = C + V(0.02, 0.43, 0.03)
    pole(g, p0, p0 + V(0.38, 0.38, 0.12), 0.018, 0.016, rng, mat=M_TIMBER, col=(0.62, 0.52, 0.4), sides=5, segs=1)
    lbox(g, p0 + V(-0.02, 0.0, 0.0), (0.16, 0.1, 0.02), quat_y(-0.3) @ quat_z(0.8), M_IRON, (0.55, 0.55, 0.57), tile=0.2)
    for k in range(3):
        pole(g, C + V(0.4 + k * 0.12, 0.06, -0.3 + k * 0.1), C + V(0.45 + k * 0.1, 0.07, 0.0 + k * 0.1), 0.05, 0.05, rng,
             mat=M_TIMBER, col=(0.85, 0.74, 0.58), sides=4, segs=1)


def bucket(g, c):
    lathe(g, c, (0, 1, 0), [(0.0, 0.13), (0.28, 0.16)], 8, M_TIMBER, (0.6, 0.5, 0.4), tile=0.4)
    tube(g, [Vector(c) + V(0, 0.2, 0), Vector(c) + V(0, 0.22, 0)], [0.165, 0.165], 8, M_IRON, IRON_D, tile=0.3, cap=False)


def town_house_a(rng):
    b = Builder()
    g = G(b)
    W, D = 4.6, 3.4
    house(g, rng, W, D, 2.05, 3.55, [
        [dict(s=1.5, w=0.9, y0=0.25, y1=1.65, kind="door", ajar=0.4), dict(s=3.3, w=0.8, y0=0.95, y1=1.55)],
        [dict(s=1.7, w=0.65, y0=1.0, y1=1.55)], [dict(s=2.3, w=0.65, y0=1.0, y1=1.55)], []])
    woodpile(g, rng, (-W / 2 - 0.38, 0.0, 0.0), L=1.8, rows=3)
    chopping_block(g, rng, (-W / 2 - 0.9, 0.0, D / 2 + 0.7))
    bench(g, rng, V(0.4, 0.0, D / 2 + 0.38), 0.0, L=1.1)
    return b


def town_house_b(rng):
    b = Builder()
    g = G(b)
    W, D = 5.6, 3.6
    house(g, rng, W, D, 2.1, 3.7, [
        [dict(s=1.1, w=0.75, y0=0.95, y1=1.55), dict(s=2.8, w=0.95, y0=0.25, y1=1.68, kind="door", ajar=0.0),
         dict(s=4.5, w=0.75, y0=0.95, y1=1.55, shutters=False)],
        [], [dict(s=2.8, w=0.65, y0=1.0, y1=1.55)], [dict(s=1.8, w=0.6, y0=1.0, y1=1.5)]],
        gstyle=("boards", "boards"))
    # Lean-to log store on the east end: posts, a plank pent roof, a stack of logs.
    x0 = W / 2 + 0.1
    for z in (-1.4, 1.4):
        beam(g, [V(x0 + 1.1, -0.05, z), V(x0 + 1.1, 1.45, z)], 0.12, 0.12, mat=M_TIMBER, col_fn=weathered(TF, 0.7), rng=rng)
    beam(g, [V(x0 + 1.1, 1.42, -1.55), V(x0 + 1.1, 1.42, 1.55)], 0.12, 0.12, mat=M_TIMBER, col=TF, rng=rng)
    pq = quat_z(-0.36)
    lbox(g, V(x0 + 0.62, 1.68, 0.0), (1.42, 0.07, 3.3), pq, M_PLANK, (0.5, 0.45, 0.4), tile=1.2, grain=0)
    for r in range(2):
        for k in range(7):
            z = -1.15 + k * 0.38 + (0.17 if r % 2 else 0)
            p = V(x0 + 0.55, 0.11 + r * 0.2, z)
            pole(g, p + V(-0.35, 0, 0), p + V(0.35, 0, 0), 0.1, 0.1, rng, col=(0.7, 0.6, 0.48), sides=5, segs=1, wobble=0.0)
    lathe(g, (-1.9, 0.0, D / 2 + 0.55), (0, 1, 0), [(0.0, 0.32), (0.28, 0.36)], 10, M_TIMBER, (0.55, 0.46, 0.36), tile=0.5,
          cap=False)
    tube(g, [V(-1.9, 0.04, D / 2 + 0.55), V(-1.9, 0.24, D / 2 + 0.55)], [0.31, 0.34], 10, M_TIMBER, (0.25, 0.22, 0.2),
         tile=0.5)
    barrel(g, rng, (W / 2 + 0.45, 0.0, D / 2 + 0.55))
    return b


def town_house_c(rng):
    b = Builder()
    g = G(b)
    W, D = 3.8, 3.2
    house(g, rng, W, D, 1.98, 3.45, [
        [dict(s=1.25, w=0.88, y0=0.25, y1=1.62, kind="door", ajar=1.1), dict(s=2.85, w=0.6, y0=1.0, y1=1.5)],
        [dict(s=1.6, w=0.55, y0=1.0, y1=1.5)], [], []], gstyle=("boards", "plaster"))
    bench(g, rng, V(2.35, 0.0, D / 2 + 0.45), 0.0, L=1.0)
    bucket(g, (0.15, 0.0, D / 2 + 0.55))
    hurdle(g, rng, V(-W / 2 - 0.2, 0, D / 2 + 1.4), V(-W / 2 - 0.2, 0, D / 2 + 0.1))
    hurdle(g, rng, V(-W / 2 + 1.0, 0, D / 2 + 1.4), V(-W / 2 - 0.2, 0, D / 2 + 1.4))
    return b


def town_house_d(rng):
    b = Builder()
    g = G(b)
    W, D = 4.8, 3.6
    house(g, rng, W, D, 2.08, 3.6, [
        [dict(s=1.0, w=0.75, y0=0.95, y1=1.55), dict(s=2.6, w=0.92, y0=0.25, y1=1.66, kind="door", ajar=0.6),
         dict(s=4.0, w=0.7, y0=0.95, y1=1.55)],
        [dict(s=1.8, w=0.6, y0=1.0, y1=1.5)], [dict(s=2.4, w=0.6, y0=1.0, y1=1.5)], []])
    chimney(g, rng, (-W / 2 - 0.36, -0.3), 4.15, w=0.62, d=0.82)
    # Washing line from the house corner to a forked pole, linen + a shirt drying.
    p0, p1 = V(W / 2 + 0.05, 1.75, D / 2 + 0.05), V(W / 2 + 2.0, 1.7, D / 2 + 1.0)
    pole(g, V(p1.x, -0.2, p1.z), p1 + V(0, 0.1, 0), 0.035, 0.03, rng, col=(0.75, 0.66, 0.52), sides=5, segs=2)
    tube(g, [p0, p0.lerp(p1, 0.5) - V(0, 0.12, 0), p1], [0.008] * 3, 4, M_CLOTH, ROPE, tile=0.3)
    for f, w_, h_, col in ((0.25, 0.42, 0.5, LINEN), (0.6, 0.36, 0.55, (0.62, 0.66, 0.78))):
        a_ = p0.lerp(p1, f - 0.08) - V(0, 0.1, 0)
        c_ = p0.lerp(p1, f + 0.08) - V(0, 0.1, 0)
        grid = [[(a_.lerp(c_, j / 3)).to_tuple() for j in range(4)]]
        grid.append([(a_.lerp(c_, j / 3) - V(0, h_, 0) + V(0, 0, 0.03 * math.sin(j))).to_tuple() for j in range(4)])
        sheet(g, grid, M_CLOTH, lambda u, v, c=col: c, tile=0.5, double=True)
    return b


# ─────────────────────────────────────────────────────────────── 4. Maud's house
def town_maud_house(rng):
    b = Builder()
    g = G(b)
    W, D = 5.2, 3.8
    house(g, rng, W, D, 2.12, 3.75, [
        [dict(s=0.9, w=0.75, y0=0.95, y1=1.58), dict(s=2.4, w=0.95, y0=0.25, y1=1.68, kind="door", ajar=0.35),
         dict(s=4.3, w=0.75, y0=0.95, y1=1.58)],
        [dict(s=1.9, w=0.65, y0=1.0, y1=1.55)], [dict(s=2.6, w=0.65, y0=1.0, y1=1.55)], [dict(s=1.9, w=0.65, y0=1.0, y1=1.55)]])
    # Edict board right of the door: two posts, a pent cap, pinned notices, the red-sealed edict.
    ex, ez = 1.9, D / 2 + 0.62
    for x in (ex - 0.62, ex + 0.62):
        beam(g, [V(x, -0.25, ez), V(x, 2.0, ez)], 0.11, 0.11, mat=M_TIMBER, col_fn=weathered(TF, 0.7), rng=rng)
    lbox(g, V(ex, 1.32, ez + 0.02), (1.3, 0.8, 0.05), quat_y(0.0), M_PLANK, (0.62, 0.54, 0.44), tile=0.8, grain=0)
    for sz in (-1, 1):
        lbox(g, V(ex, 2.02 + 0.03, ez + sz * 0.13), (1.55, 0.04, 0.3), quat_x(sz * 0.55), M_PLANK, (0.5, 0.44, 0.38),
             tile=0.8, grain=0)
    notes = [(-0.38, 1.42, 0.34, 0.44, 0.08, PAPER), (0.08, 1.38, 0.42, 0.56, -0.02, (1.08, 1.04, 0.92)),
             (0.45, 1.5, 0.26, 0.32, -0.12, (0.98, 0.9, 0.72)), (0.42, 1.12, 0.3, 0.24, 0.1, PAPER),
             (-0.4, 1.08, 0.28, 0.22, -0.06, (0.95, 0.88, 0.7))]
    zf = ez + 0.05
    for k, (x, y, w_, h_, rot, col) in enumerate(notes):
        q = quat_z(rot)
        c = V(ex + x, y, zf + 0.004 * k)
        lbox(g, c, (w_, h_, 0.006), q, M_PLASTER, col, tile=0.6)
        lbox(g, c + q @ V(0, h_ / 2 - 0.03, 0.006), (0.025, 0.025, 0.012), q, M_IRON, IRON_D, tile=0.2)
        for r in range(int(h_ / 0.07) - 1):
            yy = h_ / 2 - 0.09 - r * 0.065
            ww = w_ * (0.75 if r % 3 else 0.6)
            lbox(g, c + q @ V(-w_ / 2 + 0.04 + ww / 2, yy, 0.0045), (ww, 0.012, 0.002), q, M_PLASTER, (0.15, 0.12, 0.1), tile=0.3)
    sq = quat_z(-0.02)
    seal = V(ex + 0.08, 1.38 - 0.2, zf + 0.012)
    tube(g, [seal, seal + V(0, 0, 0.02)], [0.05, 0.048], 10, M_FRUIT, (0.62, 0.06, 0.05), tile=0.2)
    for dx in (-0.02, 0.025):
        face(g, [seal + V(dx - 0.012, -0.03, 0.006), seal + V(dx + 0.012, -0.03, 0.006), seal + V(dx * 2.5 + 0.012, -0.16, 0.006),
                 seal + V(dx * 2.5 - 0.012, -0.16, 0.006)], (0, 0, 1), M_CLOTH, (0.6, 0.08, 0.08), tile=0.2)
    # Iron-bound tax chest and a bench by the door.
    cc = V(3.3, 0.22, D / 2 + 0.45)
    lbox(g, cc, (0.7, 0.42, 0.44), quat_y(-0.1), M_PLANK, (0.55, 0.45, 0.35), tile=0.6)
    for dx in (-0.25, 0.25):
        lbox(g, cc + quat_y(-0.1) @ V(dx, 0.0, 0), (0.05, 0.44, 0.46), quat_y(-0.1), M_IRON, IRON_D, tile=0.3)
    lbox(g, cc + quat_y(-0.1) @ V(0, 0.08, 0.225), (0.08, 0.1, 0.02), quat_y(-0.1), M_IRON, IRON_D, tile=0.2)
    bench(g, rng, V(0.8, 0.0, D / 2 + 0.4), 0.0, L=1.2)
    return b


# ─────────────────────────────────────────────────────────────── 5. infirmary + herb garden
def cot(g, rng, c, yaw_a):
    q = quat_y(yaw_a)
    C = Vector(c)
    for sx in (-1, 1):
        beam(g, [C + q @ V(sx * 0.3, 0.32, -0.62), C + q @ V(sx * 0.3, 0.32, 0.62)], 0.06, 0.07, mat=M_TIMBER, col=TF, rng=rng)
        for sz in (-1, 1):
            beam(g, [C + q @ V(sx * 0.3, 0.0, sz * 0.58), C + q @ V(sx * 0.3, 0.36, sz * 0.58)], 0.06, 0.06, mat=M_TIMBER,
                 col=TF, rng=rng)
    lbox(g, C + q @ V(0, 0.39, 0), (0.6, 0.1, 1.22), q, M_THATCH, (0.9, 0.82, 0.62), tile=0.6, grain=2)
    lbox(g, C + q @ V(0, 0.45, 0.12), (0.64, 0.04, 0.95), q, M_CLOTH, LINEN, tile=0.6)
    stone(g, tuple(C + q @ V(0, 0.48, -0.47)), (0.2, 0.06, 0.1), rng, mat=M_CLOTH, detail=1, rough=0.05, cuts=0,
          rot=q, col_fn=lambda p, n: LINEN, tile=0.4)


def town_infirmary(rng):
    b = Builder()
    g = G(b)
    W, D = 7.2, 3.6
    ye, yr = 1.85, 3.2
    wins = [dict(s=s, w=0.95, y0=0.72, y1=1.42, void=False, swing=2.5) for s in (2.6, 4.1, 5.6)]
    house(g, rng, W, D, ye, yr, [
        [dict(s=1.1, w=0.95, y0=0.25, y1=1.6, kind="door", ajar=1.35, void=False)] + wins,
        [dict(s=1.8, w=0.8, y0=0.75, y1=1.4, void=False)], [dict(s=s, w=0.7, y0=0.8, y1=1.35) for s in (1.6, 5.6)],
        [dict(s=1.8, w=0.8, y0=0.75, y1=1.4, void=False)]], stud=0.95)
    lbox(g, V(0, 0.22, 0), (W - 0.2, 0.04, D - 0.2), quat_y(0.0), M_EARTH, (0.5, 0.44, 0.38), tile=1.0)
    for x in (-2.35, -0.75, 0.85, 2.45):
        cot(g, rng, (x, 0.24, -0.82), 0.0)
    bucket(g, (-1.6, 0.24, -1.2))
    lbox(g, V(1.65, 0.6, -1.45), (0.5, 0.05, 0.35), quat_y(0.0), M_PLANK, (0.6, 0.5, 0.4), tile=0.5)
    for x in (1.45, 1.85):
        beam(g, [V(x, 0.24, -1.45), V(x, 0.58, -1.45)], 0.05, 0.05, mat=M_TIMBER, col=TF, rng=rng)
    for k, x in enumerate((1.5, 1.68, 1.8)):
        lathe(g, (x, 0.625, -1.45 + 0.05 * (k - 1)), (0, 1, 0), [(0.0, 0.04), (0.08, 0.045), (0.12, 0.02), (0.15, 0.025)], 7,
              M_FRUIT, (0.55, 0.32, 0.2) if k != 1 else (0.3, 0.45, 0.35), tile=0.3)
    # Herb bundles drying on a pole under the front eave.
    hp0, hp1 = V(-W / 2 + 0.3, 1.68, D / 2 + 0.3), V(-W / 2 + 2.6, 1.7, D / 2 + 0.3)
    tube(g, [hp0, hp1], [0.02, 0.02], 5, M_BARK, (0.75, 0.66, 0.52), tile=0.3)
    for k in range(7):
        p = hp0.lerp(hp1, (k + 0.5) / 7)
        col = [(0.38, 0.5, 0.28), (0.5, 0.48, 0.3), (0.55, 0.42, 0.55), (0.42, 0.55, 0.35)][k % 4]
        lathe(g, p, (0, -1, 0), [(0.0, 0.02), (0.08, 0.05), (0.3, 0.075), (0.36, 0.02)], 6, M_FRUIT, col, tile=0.3)
    # Fenced herb garden on the east side: wattle fence with a gap, three raised beds.
    gx0, gx1, gz = W / 2 + 0.35, W / 2 + 3.4, 1.6
    for x, z in ((gx0, -gz), (gx1, -gz), (gx1, gz), (gx0, gz)):
        pole(g, V(x, -0.2, z), V(x, 0.72, z), 0.045, 0.04, rng, col=(0.85, 0.8, 0.72))
    hurdle(g, rng, V(gx0 + 0.05, 0, -gz), V(gx1 - 0.05, 0, -gz))
    hurdle(g, rng, V(gx1, 0, -gz + 0.05), V(gx1, 0, gz - 0.05))
    hurdle(g, rng, V(gx0 + 1.1, 0, gz), V(gx1 - 0.05, 0, gz))
    herbs = [(0.42, 0.55, 0.38), (0.3, 0.52, 0.24), (0.58, 0.48, 0.7), (0.5, 0.58, 0.45), (0.92, 0.62, 0.18)]
    for k, x in enumerate((gx0 + 0.6, gx0 + 1.5, gx0 + 2.4)):
        lbox(g, V(x, 0.11, -0.1), (0.62, 0.22, 2.4), quat_y(0.0), M_PLANK, (0.5, 0.42, 0.34), tile=0.8, grain=2)
        lbox(g, V(x, 0.225, -0.1), (0.56, 0.01, 2.34), quat_y(0.0), M_EARTH, (0.4, 0.32, 0.25), tile=0.8)
        for j in range(6):
            col = herbs[(k * 2 + j // 2) % len(herbs)]
            z = -1.05 + j * 0.38
            for dx in (-0.12, 0.12):
                stone(g, (x + dx + rng.uniform(-0.03, 0.03), 0.3, z + rng.uniform(-0.05, 0.05)),
                      (0.13, rng.uniform(0.09, 0.15), 0.13), rng, mat=M_FRUIT, detail=0, rough=0.25, cuts=0,
                      col_fn=lambda p, n, c=col: scale(c, 0.7 + 0.35 * max(n.y, 0.0)), tile=0.3)
    return b


# ─────────────────────────────────────────────────────────────── 6. fire pit + empty grave
def town_firepit(rng):
    b = Builder()
    g = G(b)
    for k in range(8):
        a = k * 2 * math.pi / 8 + rng.uniform(-0.1, 0.1)
        stone(g, (0.72 * math.cos(a), 0.06, 0.72 * math.sin(a)), (0.23, 0.15, 0.19), rng, mat=M_STONE,
              detail=1 if k in (0, 3, 6) else 0, cuts=1,
              col_fn=rock_col(scale(STONE_C, rng.uniform(0.55, 0.75)), dark_below=0.4), tile=0.6)
    mound(g, (0, -0.02, 0), 0.62, 0.62, 0.08, rng, mat=M_EARTH, col_fn=lambda p, n: (0.26, 0.24, 0.22), rings=3, seg=12)
    for k in range(4):
        a = k * math.pi / 4 + 0.3
        d = V(math.cos(a), 0, math.sin(a))
        pole(g, d * -0.4 + V(0, 0.08, 0), d * 0.4 + V(0, 0.16, 0), 0.06, 0.05, rng, mat=M_BARK, col=charred(rng), sides=6,
             segs=1)
    # Tripod + cauldron.
    top = V(0, 1.38, 0)
    for k in range(3):
        a = k * 2 * math.pi / 3 + 0.4
        pole(g, V(1.0 * math.cos(a), -0.05, 1.0 * math.sin(a)), top, 0.035, 0.03, rng, col=(0.7, 0.62, 0.5), sides=5, segs=2)
    lashing(g, top - V(0, 0.06, 0), (0, 1, 0), 0.07, rng, turns=1)
    tube(g, [top - V(0, 0.08, 0), V(0, 0.7, 0)], [0.012, 0.012], 4, M_IRON, IRON_D, tile=0.2)
    lathe(g, (0, 0.38, 0), (0, 1, 0), [(0.0, 0.05), (0.06, 0.2), (0.18, 0.25), (0.3, 0.24), (0.33, 0.25)], 8, M_IRON,
          (0.18, 0.17, 0.17), tile=0.4)
    tube(g, [V(-0.24, 0.7, 0), V(0, 0.79, 0), V(0.24, 0.7, 0)], [0.01] * 3, 4, M_IRON, IRON_D, tile=0.2, cap=False)
    # Three log benches round it (split logs on stump legs).
    for k in range(3):
        a = k * 2 * math.pi / 3 + 1.0
        c = V(2.05 * math.cos(a), 0, 2.05 * math.sin(a))
        t = V(-math.sin(a), 0, math.cos(a))
        for s in (-0.5, 0.5):
            pole(g, c + t * s - V(0, 0.05, 0), c + t * s + V(0, 0.24, 0), 0.13, 0.12, rng, mat=M_BARK, col=(0.7, 0.62, 0.52),
                 sides=6, segs=1)
        pole(g, c - t * 0.8 + V(0, 0.36, 0), c + t * 0.8 + V(0, 0.36, 0), 0.17, 0.16, rng, mat=M_BARK, col=(0.72, 0.64, 0.54),
             sides=7, segs=1)
    return b


def kettle_helm(g, rng, c, tilt=(0.0, 0.0), s=1.0, col=(0.55, 0.56, 0.6)):
    """A squire's kettle hat: dome + broad brim, tilted."""
    q = quat_x(tilt[0]) @ quat_z(tilt[1])
    C = Vector(c)
    ax = q @ V(0, 1, 0)
    lathe(g, C, tuple(ax), [(0.0, 0.13 * s), (0.06 * s, 0.13 * s), (0.13 * s, 0.1 * s), (0.18 * s, 0.05 * s), (0.2 * s, 0.0)],
          10, M_IRON, col, tile=0.3)
    lathe(g, C - ax * 0.012, tuple(ax), [(0.0, 0.25 * s), (0.02 * s, 0.24 * s)], 12, M_IRON, scale(col, 0.85), tile=0.3)


def town_grave(rng):
    b = Builder()
    g = G(b)
    mound(g, (0, -0.04, 0.05), 0.55, 1.08, 0.3, rng, mat=M_EARTH, col_fn=lambda p, n: (0.42, 0.33, 0.25), rings=5, seg=16,
          rough=0.18)
    for k in range(8):
        a = k * 2 * math.pi / 8 + rng.uniform(-0.15, 0.15)
        stone(g, (0.66 * math.cos(a), 0.04, 0.05 + 1.2 * math.sin(a)), (0.12, 0.08, 0.1), rng, mat=M_STONE,
              detail=1 if k % 3 == 0 else 0, cuts=1, col_fn=rock_col(scale(STONE_C, rng.uniform(0.6, 0.8))), tile=0.5)
    # Marker post at the head (-Z): a squared post, notched, the helm hung on its top.
    beam(g, [V(0, -0.3, -1.3), V(0.0, 1.12, -1.28)], 0.13, 0.13, up=(0, 0, 1), mat=M_TIMBER, col_fn=weathered((0.72, 0.62, 0.5), 0.75),
         rng=rng)
    lbox(g, V(0, 0.8, -1.215), (0.1, 0.02, 0.005), quat_y(0.0), M_PLASTER, (0.2, 0.17, 0.14), tile=0.3)
    lbox(g, V(0, 0.75, -1.215), (0.06, 0.02, 0.005), quat_y(0.0), M_PLASTER, (0.2, 0.17, 0.14), tile=0.3)
    kettle_helm(g, rng, (0.0, 1.07, -1.28), tilt=(0.12, -0.22), s=0.95)
    # Wildflowers at the foot of the post, a spade left stuck in the dirt.
    for k in range(5):
        p = V(rng.uniform(-0.25, 0.25), 0.02, -1.05 + rng.uniform(-0.08, 0.1))
        pole(g, p, p + V(rng.uniform(-0.05, 0.05), 0.18, 0.04), 0.006, 0.005, rng, mat=M_FRUIT, col=(0.3, 0.45, 0.2), sides=3,
             segs=1)
        stone(g, (p.x, 0.21, p.z + 0.04), (0.03, 0.02, 0.03), rng, mat=M_FRUIT, detail=0, cuts=0,
              col_fn=lambda q_, n, c=[(0.95, 0.85, 0.3), (0.9, 0.9, 0.95), (0.6, 0.5, 0.85)][k % 3]: c, tile=0.2)
    sp = V(0.75, 0.0, 0.55)
    pole(g, sp + V(0, 0.2, 0), sp + V(0.08, 1.05, -0.05), 0.02, 0.018, rng, mat=M_TIMBER, col=(0.6, 0.5, 0.38), sides=5, segs=1)
    lbox(g, sp + V(0.0, 0.08, 0.0), (0.2, 0.28, 0.02), quat_y(0.3) @ quat_z(-0.08), M_IRON, (0.42, 0.4, 0.38), tile=0.3)
    mound(g, (0.95, -0.02, 0.3), 0.32, 0.4, 0.12, rng, mat=M_EARTH, col_fn=lambda p, n: (0.4, 0.32, 0.25), rings=2, seg=10)
    return b


# ─────────────────────────────────────────────────────────────── 7. Crown set
def crown_banner_wall(rng):
    b = Builder()
    g = G(b)
    tube(g, [V(0, 0, -0.05), V(0, 0, 0.32)], [0.02, 0.018], 5, M_IRON, IRON_D, tile=0.2)
    tube(g, [V(0, -0.3, 0.0), V(0, -0.02, 0.28)], [0.014, 0.014], 4, M_IRON, IRON_D, tile=0.2)
    pole(g, V(-0.52, 0.0, 0.22), V(0.52, 0.0, 0.22), 0.022, 0.022, rng, mat=M_TIMBER, col=(0.4, 0.3, 0.24), sides=6, segs=1)
    for x in (-0.52, 0.52):
        lathe(g, (x, 0.0, 0.22), (1 if x > 0 else -1, 0, 0), [(0.0, 0.03), (0.04, 0.035), (0.07, 0.0)], 6, M_IRON, GOLD,
              tile=0.2)
    banner_sheet(g, rng, (-0.46, -0.02, 0.22), (0.46, -0.02, 0.22), 2.05, folds=0.04)
    return b


def crown_banner_pole(rng):
    b = Builder()
    g = G(b)
    slab(g, (0, 0.05, 0), (0.5, 0.18, 0.5), quat_y(0.3), rng, res=(2, 1, 2), round_r=0.03, rough=0.04,
         col_fn=rock_col(scale(STONE_C, 0.7)), tile=0.6)
    pole(g, V(0, -0.3, 0), V(0, 4.25, 0), 0.055, 0.045, rng, mat=M_TIMBER, col=(0.42, 0.32, 0.25), sides=7, segs=2)
    pole(g, V(-0.55, 3.98, 0.06), V(0.55, 3.98, 0.06), 0.025, 0.025, rng, mat=M_TIMBER, col=(0.42, 0.32, 0.25), sides=6, segs=1)
    lathe(g, (0, 4.25, 0), (0, 1, 0), [(0.0, 0.05), (0.06, 0.07), (0.14, 0.03), (0.22, 0.0)], 8, M_IRON, GOLD, tile=0.2)
    tube(g, [V(0.0, 4.2, 0.0), V(-0.53, 4.0, 0.06)], [0.008, 0.008], 4, M_CLOTH, ROPE, tile=0.2)
    tube(g, [V(0.0, 4.2, 0.0), V(0.53, 4.0, 0.06)], [0.008, 0.008], 4, M_CLOTH, ROPE, tile=0.2)
    banner_sheet(g, rng, (-0.48, 3.96, 0.08), (0.48, 3.96, 0.08), 2.2, folds=0.05)
    return b


def crown_crates(rng):
    b = Builder()
    g = G(b)
    painted_crate(g, rng, V(-0.45, 0.25, 0.0), (0.62, 0.5, 0.5), 0.05)
    painted_crate(g, rng, V(0.25, 0.25, 0.1), (0.62, 0.5, 0.5), -0.12)
    painted_crate(g, rng, V(-0.15, 0.73, 0.02), (0.58, 0.46, 0.48), 0.2)
    painted_crate(g, rng, V(-0.55, 0.2, -0.55), (0.5, 0.4, 0.4), 0.4)
    barrel(g, rng, (0.8, 0.0, -0.3), band=CRIMSON)
    sack(g, rng, (0.9, 0.17, 0.35), True)
    return b


def crown_tent(rng):
    b = Builder()
    g = G(b)
    H, HW, HL = 1.8, 1.15, 1.35
    for z in (-HL, HL):
        pole(g, V(0, -0.2, z), V(0, H + 0.12, z), 0.035, 0.03, rng, mat=M_TIMBER, col=(0.5, 0.42, 0.34), sides=6, segs=1)
    pole(g, V(0, H, -HL - 0.1), V(0, H, HL + 0.1), 0.03, 0.03, rng, mat=M_TIMBER, col=(0.5, 0.42, 0.34), sides=6, segs=1)
    ni, nj = 13, 7
    grid = []
    for i in range(ni):
        u = i / (ni - 1)
        row = []
        for j in range(nj):
            v = j / (nj - 1)
            z = -HL + 2 * HL * v
            x = -HW + 2 * HW * u
            y = H * (1 - abs(2 * u - 1)) - 0.06 * math.sin(math.pi * v) * (1 - abs(2 * u - 1)) * 1.2
            row.append((x, max(y, 0.0) + 0.02, z))
        grid.append(row)
    for k in range(6):
        sub = grid[2 * k:2 * k + 3]
        c = CRIMSON if k in (2, 3) else LINEN
        sheet(g, sub, M_CLOTH, lambda u, v, c=c: scale(c, 0.9 + 0.1 * v), tile=0.7, double=True)
    face(g, [V(-HW, 0.02, -HL), V(HW, 0.02, -HL), V(0, H + 0.02, -HL)], (0, 0, -1), M_CLOTH, LINEN, tile=0.7)
    face(g, [V(-HW + 0.05, 0.02, -HL + 0.02), V(HW - 0.05, 0.02, -HL + 0.02), V(0, H - 0.04, -HL + 0.02)], (0, 0, 1), M_CLOTH,
         scale(VOID, 3.0), tile=0.7)
    # Front flaps tied back (rolled), a dark inside.
    for sx in (-1, 1):
        face(g, [V(sx * HW, 0.02, HL), V(sx * 0.55, 0.02, HL + 0.05), V(sx * 0.2, H * 0.82, HL)], (0, 0, 1), M_CLOTH, LINEN,
             tile=0.7)
        face(g, [V(sx * HW, 0.02, HL), V(sx * 0.55, 0.02, HL + 0.05), V(sx * 0.2, H * 0.82, HL)], (0, 0, -1), M_CLOTH,
             scale(LINEN, 0.7), tile=0.7)
        tube(g, [V(sx * 0.5, 0.25, HL + 0.06), V(sx * 0.32, 1.05, HL + 0.05), V(sx * 0.18, 1.5, HL + 0.03)], [0.06, 0.07, 0.05],
             6, M_CLOTH, LINEN, tile=0.4)
    # Pennant on the front pole, guy ropes + pegs.
    pq = [V(0, H + 0.1, HL), V(0, H + 0.3, HL), V(0.0, H + 0.2, HL + 0.55)]
    face(g, pq, (1, 0, 0), M_CLOTH, CRIMSON, tile=0.4)
    face(g, pq, (-1, 0, 0), M_CLOTH, CRIMSON, tile=0.4)
    for z in (-HL, HL):
        for p in (V(0, -0.02, z + (0.75 if z > 0 else -0.75)), V(0.5, -0.02, z + (0.6 if z > 0 else -0.6)),
                  V(-0.5, -0.02, z + (0.6 if z > 0 else -0.6))):
            tube(g, [V(0, H + 0.08, z), p + V(0, 0.12, 0)], [0.007, 0.007], 3, M_CLOTH, ROPE, tile=0.2)
            pole(g, p - V(0, 0.1, 0), p + V(0, 0.14, 0), 0.02, 0.018, rng, mat=M_TIMBER, col=(0.7, 0.6, 0.48), sides=4, segs=1)
    for x in (-1.1, 1.1):
        for z in (-0.7, 0.0, 0.7):
            pole(g, V(x * 1.12, -0.1, z), V(x * 1.12, 0.12, z), 0.018, 0.016, rng, mat=M_TIMBER, col=(0.7, 0.6, 0.48), sides=4,
                 segs=1)
    return b


def crown_gallows(rng):
    b = poi_gallows(rng)
    g = G(b)
    # A Crown edict nailed to the upright, a crimson rag knotted on the crossbeam.
    lbox(g, V(-0.85, 1.6, 0.105), (0.26, 0.34, 0.006), quat_z(0.05), M_PLASTER, PAPER, tile=0.4)
    tube(g, [V(-0.85, 1.43, 0.11), V(-0.85, 1.43, 0.125)], [0.03, 0.03], 8, M_FRUIT, (0.62, 0.06, 0.05), tile=0.2)
    for r in range(4):
        lbox(g, V(-0.87, 1.7 - r * 0.05, 0.11), (0.17, 0.01, 0.002), quat_z(0.05), M_PLASTER, (0.15, 0.12, 0.1), tile=0.3)
    grid = [[(-0.55 + 0.25 * j / 3, 3.0, 0.09) for j in range(4)],
            [(-0.55 + 0.25 * j / 3 + 0.02, 2.65 - 0.05 * j, 0.11) for j in range(4)],
            [(-0.55 + 0.25 * j / 3 + 0.05, 2.35 - 0.08 * j, 0.1) for j in range(4)]]
    sheet(g, grid, M_CLOTH, lambda u, v: scale(CRIMSON, 0.9), tile=0.4, double=True)
    tube(g, [V(-0.58, 3.12, 0.09), V(-0.28, 3.12, 0.09)], [0.09, 0.09], 6, M_CLOTH, CRIMSON, tile=0.3, cap=False)
    return b


def crown_depot(rng):
    b = Builder()
    g = G(b)
    HX, HZ = 1.6, 1.2
    yf, yb = 2.35, 1.85
    for (a, b_), y1 in (((( HX, HZ), (HX, -HZ)), yb), (((HX, -HZ), (-HX, -HZ)), yb), (((-HX, -HZ), (-HX, HZ)), yb)):
        wall(g, rng, a, b_, 0.05, y1, [], stud=None, brace=False, infill="boards", ends=(True, True), bcol=(0.62, 0.55, 0.47))
    # Side walls rise to the front: triangles of boards.
    for x, sx in ((HX, 1), (-HX, -1)):
        for i in range(9):
            z = -HZ + (i + 0.5) * 2 * HZ / 9
            ytop = yb + (yf - yb) * (z + HZ) / (2 * HZ)
            board(g, V(x + sx * 0.02, (yb - 0.1 + ytop) / 2, z), (0, 1, 0), (sx, 0, 0), ytop - yb + 0.1, 2 * HZ / 9 * 0.96, 0.035,
                  mat=M_PLANK, col=scale((0.62, 0.55, 0.47), rng.uniform(0.85, 1.0)), rng=rng)
    for x in (-HX, HX):
        beam(g, [V(x, -0.05, HZ + 0.02), V(x, yf, HZ + 0.02)], 0.16, 0.16, up=(0, 0, 1), mat=M_TIMBER, col_fn=weathered(TF, 0.7),
             rng=rng)
    beam(g, [V(-HX - 0.1, yf - 0.08, HZ + 0.02), V(HX + 0.1, yf - 0.08, HZ + 0.02)], 0.16, 0.16, up=(0, 0, 1), mat=M_TIMBER,
         col=TF, rng=rng)
    th = math.atan2(yf - yb, 2 * HZ)
    lbox(g, V(0, (yf + yb) / 2 + 0.1, 0.1), (2 * HX + 0.5, 0.07, 2 * HZ / math.cos(th) + 0.7), quat_x(th), M_PLANK,
         [(0.45, 0.4, 0.36), None, (0.6, 0.54, 0.46)], tile=1.2, grain=0)
    lbox(g, V(0, 0.07, 0), (2 * HX - 0.1, 0.06, 2 * HZ - 0.1), quat_y(0.0), M_PLANK, (0.45, 0.4, 0.34), tile=0.8)
    painted_crate(g, rng, V(-0.9, 0.35, -0.6), (0.62, 0.5, 0.5), 0.0)
    painted_crate(g, rng, V(-0.25, 0.35, -0.62), (0.62, 0.5, 0.5), 0.05)
    painted_crate(g, rng, V(-0.6, 0.83, -0.6), (0.58, 0.46, 0.48), -0.08)
    barrel(g, rng, (0.55, 0.1, -0.6), band=CRIMSON)
    barrel(g, rng, (1.1, 0.1, -0.5), band=CRIMSON)
    for p, lying in (((0.85, 0.35, 0.2), False), ((1.15, 0.27, 0.45), True), ((-1.1, 0.35, 0.3), False)):
        sack(g, rng, p, lying)
    banner_sheet(g, rng, (-0.4, yf - 0.18, HZ + 0.14), (0.4, yf - 0.18, HZ + 0.14), 1.2, folds=0.02, stripe=False)
    return b


# ─────────────────────────────────────────────────────────────── 8. carpenter + archery
def trestle(g, rng, c, yaw_a):
    q = quat_y(yaw_a)
    C = Vector(c)
    beam(g, [C + q @ V(-0.45, 0.62, 0), C + q @ V(0.45, 0.62, 0)], 0.1, 0.1, mat=M_TIMBER, col=(0.7, 0.6, 0.48), rng=rng)
    for sx in (-0.35, 0.35):
        for sz in (-1, 1):
            beam(g, [C + q @ V(sx, -0.02, sz * 0.28), C + q @ V(sx, 0.6, 0)], 0.06, 0.06, mat=M_TIMBER, col=(0.65, 0.56, 0.45),
                 rng=rng)


def town_carpenter(rng):
    b = Builder()
    g = G(b)
    trestle(g, rng, V(-0.75, 0, 0), math.pi / 2)
    trestle(g, rng, V(0.75, 0, 0), math.pi / 2)
    pole(g, V(-1.4, 0.82, 0.0), V(1.4, 0.84, 0.02), 0.17, 0.15, rng, mat=M_BARK, col=(0.72, 0.64, 0.54), sides=8, segs=2)
    lathe(g, (1.41, 0.84, 0.02), (1, 0, 0), [(0.0, 0.15), (0.001, 0.0)], 8, M_TIMBER, (0.9, 0.76, 0.56), tile=0.2)
    # Frame saw standing in the cut.
    sx = 0.15
    for y in (0.62, 1.38):
        beam(g, [V(sx, y, -0.35), V(sx, y, 0.35)], 0.04, 0.04, mat=M_TIMBER, col=(0.62, 0.52, 0.4), rng=rng)
    for z in (-0.3, 0.3):
        beam(g, [V(sx, 0.58, z), V(sx, 1.42, z)], 0.04, 0.04, mat=M_TIMBER, col=(0.62, 0.52, 0.4), rng=rng)
    lbox(g, V(sx, 0.75, 0.0), (0.004, 0.06, 0.6), quat_y(0.0), M_IRON, (0.6, 0.6, 0.62), tile=0.2)
    tube(g, [V(sx, 1.0, 0.0), V(sx, 1.38, 0.0)], [0.008, 0.008], 3, M_CLOTH, ROPE, tile=0.2)
    lbox(g, V(sx + 0.002, 0.84, 0.0), (0.005, 0.2, 0.36), quat_y(0.0), M_TIMBER, (0.95, 0.82, 0.6), tile=0.2)
    # Plank stack, shavings, an axe in a stump.
    for k in range(5):
        board(g, V(0.1, 0.06 + k * 0.055, -1.0 + rng.uniform(-0.03, 0.03)), (1, 0, 0), (0, 1, 0), 2.2, 0.28, 0.045, mat=M_PLANK,
              col=scale((0.9, 0.8, 0.64), rng.uniform(0.85, 1.0)), rng=rng)
    for x in (-0.8, 0.9):
        lbox(g, V(x, 0.02, -1.0), (0.08, 0.06, 0.4), quat_y(0.0), M_TIMBER, (0.5, 0.42, 0.34), tile=0.3)
    mound(g, (0.2, -0.02, 0.15), 1.1, 0.6, 0.05, rng, mat=M_THATCH, col_fn=lambda p, n: (1.0, 0.86, 0.62), rings=3, seg=12)
    chopping_block(g, rng, (-1.25, 0.0, 0.8))
    return b


def butt(g, rng, c, yaw_a):
    q = quat_y(yaw_a)
    C = Vector(c)
    ctr = C + V(0, 1.05, 0)
    tq = q @ quat_x(-0.18)
    nrm = tq @ V(0, 0, 1)
    # Flat-faced straw boss (the toolkit tube domes its caps), painted rings on the front.
    tube(g, [ctr - nrm * 0.14, ctr + nrm * 0.14], [0.5, 0.5], 14, M_THATCH, (0.92, 0.85, 0.68), tile=0.5, cap=False)
    for sgn in (-1, 1):
        face(g, [ctr + nrm * (sgn * 0.14) + tq @ V(0.5 * math.cos(a), 0.5 * math.sin(a), 0)
                 for a in np.linspace(0, 2 * math.pi, 15)[:-1]], nrm * sgn, M_THATCH, (0.92, 0.85, 0.68), tile=0.5)
    for k, (r, col) in enumerate(((0.42, (0.9, 0.88, 0.8)), (0.3, (0.12, 0.12, 0.13)), (0.18, (0.25, 0.4, 0.62)),
                                  (0.07, (0.85, 0.65, 0.2)))):
        face(g, [ctr + nrm * (0.145 + 0.003 * k) + tq @ V(r * math.cos(a), r * math.sin(a), 0)
                 for a in np.linspace(0, 2 * math.pi, 15)[:-1]], nrm, M_FRUIT, col, tile=0.5)
    for sx in (-1, 1):
        beam(g, [C + q @ V(sx * 0.4, -0.05, -0.25), C + q @ V(sx * 0.32, 1.2, 0.05)], 0.07, 0.07, mat=M_TIMBER, col=(0.62, 0.52, 0.4),
             rng=rng)
    beam(g, [C + q @ V(0, -0.05, -0.65), C + q @ V(0, 1.2, -0.1)], 0.07, 0.07, mat=M_TIMBER, col=(0.62, 0.52, 0.4), rng=rng)
    for k in range(3):
        p = C + V(0, 1.05, 0) + q @ V(rng.uniform(-0.25, 0.25), rng.uniform(-0.25, 0.25), 0.15)
        d = q @ V(rng.uniform(-0.15, 0.15), rng.uniform(-0.1, 0.1), 1.0)
        tube(g, [p, p + d.normalized() * 0.55], [0.008, 0.008], 3, M_TIMBER, (0.75, 0.65, 0.5), tile=0.2)
        face(g, [p + d.normalized() * 0.5, p + d.normalized() * 0.58 + V(0, 0.04, 0), p + d.normalized() * 0.58 - V(0, 0.04, 0)],
             q @ V(1, 0, 0), M_CLOTH, (0.9, 0.9, 0.88), tile=0.2)


def town_archery(rng):
    b = Builder()
    g = G(b)
    butt(g, rng, V(-1.0, 0, 0), 0.06)
    butt(g, rng, V(1.0, 0, 0), -0.08)
    lathe(g, (0.0, 0.0, 0.55), (0, 1, 0), [(0.0, 0.12), (0.4, 0.14)], 8, M_THATCH, (0.8, 0.66, 0.42), tile=0.3, cap=False)
    for k in range(7):
        a = k * 0.9
        p = V(0.0 + 0.06 * math.cos(a), 0.15, 0.55 + 0.06 * math.sin(a))
        tube(g, [p, p + V(0.05 * math.cos(a), 0.6, 0.05 * math.sin(a))], [0.008, 0.008], 3, M_TIMBER, (0.75, 0.65, 0.5), tile=0.2)
    return b


# ─────────────────────────────────────────────────────────────── 9. podgrodzie: street-gable houses
def street_house(g, rng, HX, HZ, ye, yr, front, east, back, west, gstyle="boards", loft=None, roof_style="thatch",
                 stud=1.25):
    """A narrow burgage house, ridge along Z, the GABLE END (+ door) to +Z, the street."""
    pts = [(-HX, HZ), (HX, HZ), (HX, -HZ), (-HX, -HZ)]
    plinth(g, rng, loop(pts))
    for (a, b_), ops in zip(loop(pts), (front, east, back, west)):
        wall(g, rng, a, b_, 0.25, ye, ops, stud=stud)
    R = quat_y(math.pi / 2)
    roof(g, rng, (0, 0, 0), R, 2 * HZ, 2 * HX, ye, yr, over=0.4, verge=0.38, style=roof_style)
    gable(g, rng, (0, 0, 0), R, -HZ, -1, 2 * HX, ye, yr, style=gstyle, loft=loft)
    gable(g, rng, (0, 0, 0), R, HZ, 1, 2 * HX, ye, yr, style="plaster")


def town_street_house_a(rng):
    """Street-gable cottage: boarded front gable with a loft door, thatch, back door to the yard."""
    b = Builder()
    g = G(b)
    HX, HZ = 2.2, 3.8
    street_house(g, rng, HX, HZ, 2.1, 4.35,
                 [dict(s=1.25, w=0.9, y0=0.25, y1=1.65, kind="door", ajar=0.5), dict(s=3.25, w=0.72, y0=0.95, y1=1.55)],
                 [dict(s=2.0, w=0.65, y0=1.0, y1=1.55), dict(s=5.4, w=0.65, y0=1.0, y1=1.55)],
                 [dict(s=2.9, w=0.85, y0=0.25, y1=1.6, kind="door", ajar=0.0)],
                 [dict(s=3.6, w=0.6, y0=1.0, y1=1.5)],
                 loft=dict(z=0.0, w=0.7, y0=2.55, y1=3.2))
    bench(g, rng, V(1.15, 0.0, HZ + 0.42), 0.0, L=1.0)
    bucket(g, (-1.75, 0.0, HZ + 0.4))
    return b


def town_street_house_b(rng):
    """Street-gable shop house: plaster front gable, a shop window whose lower shutter folds down
    into a counter (on two legs) and whose upper shutter props up as an awning; plank roof."""
    b = Builder()
    g = G(b)
    HX, HZ = 2.4, 3.5
    s0, sw, y0, y1 = 3.15, 1.6, 0.78, 1.66
    street_house(g, rng, HX, HZ, 2.15, 4.45,
                 [dict(s=0.85, w=0.9, y0=0.25, y1=1.68, kind="door", ajar=0.9),
                  dict(s=s0, w=sw, y0=y0, y1=y1, kind="open", shutters=False)],
                 [dict(s=3.6, w=0.65, y0=1.0, y1=1.55)],
                 [dict(s=1.6, w=0.85, y0=0.25, y1=1.6, kind="door", ajar=0.0), dict(s=3.6, w=0.6, y0=1.0, y1=1.5)],
                 [dict(s=2.4, w=0.6, y0=1.0, y1=1.5), dict(s=5.2, w=0.6, y0=1.0, y1=1.5)],
                 gstyle="plaster", roof_style="boards")
    cx = -HX + s0
    zf = HZ + 0.1
    sc = (0.62, 0.52, 0.4)
    # Counter: the lower leaf hinged at the sill, folded down flat, on two legs + knee braces.
    cl = 0.52
    lbox(g, V(cx, y0 - 0.03, zf + cl / 2), (sw + 0.04, 0.05, cl), quat_y(0.0), M_PLANK, scale(sc, 1.05), tile=0.8, grain=0)
    for sx in (-1, 1):
        x = cx + sx * (sw / 2 - 0.1)
        beam(g, [V(x, -0.03, zf + cl - 0.06), V(x, y0 - 0.06, zf + cl - 0.06)], 0.06, 0.06, mat=M_TIMBER, col=scale(sc, 0.8),
             rng=rng, chamfer=0.0)
        beam(g, [V(x, y0 - 0.5, zf + 0.02), V(x, y0 - 0.07, zf + cl - 0.1)], 0.05, 0.05, mat=M_TIMBER, col=scale(sc, 0.75),
             rng=rng, chamfer=0.0)
    # Awning: the upper leaf hinged at the head, propped up and out on two sticks.
    al, ang = 0.62, 1.05
    hinge = V(cx, y1 + 0.03, zf)
    d = V(0, math.cos(ang), math.sin(ang))
    lbox(g, hinge + d * (al / 2) + V(0, 0, 0.02), (sw + 0.08, al, 0.05), quat_x(ang), M_PLANK, scale(sc, 0.95), tile=0.8,
         grain=1)
    tip = hinge + d * (al - 0.04)
    for sx in (-1, 1):
        pole(g, V(cx + sx * (sw / 2 - 0.08), y0, zf + cl - 0.12), tip + V(sx * (sw / 2 - 0.08), -0.03, 0), 0.018, 0.016,
             rng, col=(0.7, 0.62, 0.5), sides=4, segs=1)
    # Wares on the counter: pots, a bowl, a bolt of blue cloth, loaves.
    top = y0 - 0.005
    for k, x in enumerate((-0.6, -0.38, -0.15)):
        lathe(g, (cx + x, top, zf + 0.25 + 0.08 * (k % 2)), (0, 1, 0), [(0.0, 0.06), (0.1, 0.09), (0.2, 0.06), (0.24, 0.07)],
              7, M_FRUIT, [(0.6, 0.36, 0.22), (0.5, 0.3, 0.2), (0.62, 0.42, 0.26)][k], tile=0.3)
    lathe(g, (cx + 0.12, top, zf + 0.32), (0, 1, 0), [(0.0, 0.05), (0.07, 0.13)], 8, M_TIMBER, (0.7, 0.58, 0.44), tile=0.3)
    tube(g, [V(cx + 0.3, top + 0.07, zf + 0.15), V(cx + 0.68, top + 0.07, zf + 0.17)], [0.07, 0.07], 7, M_CLOTH,
         (0.42, 0.52, 0.66), tile=0.4)
    for k in range(3):
        stone(g, (cx + 0.38 + 0.15 * k, top + 0.04, zf + 0.38), (0.07, 0.045, 0.055), rng, mat=M_FRUIT, detail=0, rough=0.1,
              cuts=0, col_fn=lambda p, n: (0.78, 0.55, 0.3), tile=0.3)
    barrel(g, rng, (HX + 0.4, 0.0, HZ - 0.4))
    return b


# ─────────────────────────────────────────────────────────────── 10. plot dressing
POST_C = (0.68, 0.6, 0.5)


def town_fence_wattle(rng, gate=False):
    """3u wattle module along X (posts at +-1.5); the gate version hangs a rod gate (gap x 0.25..1.45)
    swung open into the plot (-Z)."""
    b = Builder()
    g = G(b)
    L = 3.0
    for x in ([-L / 2, L / 2] if not gate else [-L / 2, 0.25, 1.45]):
        pole(g, V(x, -0.15, 0), V(x, 1.02 + rng.uniform(0, 0.06), 0), 0.055, 0.045, rng, col=POST_C, sides=5, segs=1)
    if not gate:
        hurdle(g, rng, V(-L / 2 + 0.06, 0, 0), V(L / 2 - 0.06, 0, 0), h=0.9, gap=0.38, rods=11)
        return b
    hurdle(g, rng, V(-L / 2 + 0.06, 0, 0), V(0.19, 0, 0), h=0.9, gap=0.38, rods=11)
    ang = 1.2
    hinge = V(1.4, 0.0, -0.03)
    d = V(-math.cos(ang), 0, -math.sin(ang))
    w_, h_ = 1.08, 0.88
    for f in (0.03, 0.97):
        p = hinge + d * (w_ * f)
        pole(g, p + V(0, 0.06, 0), p + V(0, h_, 0), 0.025, 0.022, rng, col=POST_C, sides=4, segs=1)
    for y in (0.15, 0.5, 0.84):
        pole(g, hinge + V(0, y, 0), hinge + d * w_ + V(0, y, 0), 0.022, 0.022, rng, col=POST_C, sides=4, segs=1)
    pole(g, hinge + V(0, 0.15, 0), hinge + d * w_ + V(0, 0.84, 0), 0.02, 0.02, rng, col=POST_C, sides=4, segs=1)
    for k in range(5):
        p = hinge + d * (0.2 + 0.17 * k)
        pole(g, p + V(0, 0.1, 0), p + V(0, 0.86, 0), 0.012, 0.012, rng, mat=M_BARK, col=(1.0, 0.92, 0.76), sides=3, segs=1,
             wobble=0.0)
    tube(g, [V(1.45, 0.92, 0.05), V(1.45, 0.82, 0.08), V(1.45, 0.72, 0.05)], [0.01] * 3, 3, M_CLOTH, ROPE, tile=0.2,
         cap=False)
    return b


def town_fence_wattle_gate(rng):
    return town_fence_wattle(rng, gate=True)


def picket_run(g, rng, x0, x1, h=1.0, gap=0.17):
    n = max(2, int((x1 - x0) / gap))
    for k in range(n):
        x = x0 + (k + 0.5) * (x1 - x0) / n
        hh = h + rng.uniform(-0.05, 0.03)
        beam(g, [V(x, -0.04, 0.05), V(x, hh, 0.05)], 0.1, 0.025, up=(0, 0, 1), mat=M_PLANK, mode="plank", chamfer=0.0,
             point=0.07, col=scale((0.8, 0.72, 0.6), rng.uniform(0.75, 1.0)), rng=rng)


def town_fence_picket(rng, gate=False):
    """3u picket module along X (posts at +-1.5, pickets on the +Z face); the gate version swings a
    ledged-and-braced picket gate (gap x 0.25..1.45) open into the plot (-Z)."""
    b = Builder()
    g = G(b)
    L = 3.0
    for x in ([-L / 2, 0.0, L / 2] if not gate else [-L / 2, 0.25, 1.45]):
        beam(g, [V(x, -0.15, 0), V(x, 1.08, 0)], 0.11, 0.11, mat=M_TIMBER, col_fn=weathered((0.66, 0.58, 0.48), 0.65),
             rng=rng, chamfer=0.0)
    for a_, c_ in ([(-L / 2, L / 2)] if not gate else [(-L / 2, 0.25)]):
        for y in (0.25, 0.78):
            beam(g, [V(a_, y, 0.0), V(c_, y, 0.0)], 0.07, 0.05, up=(0, 0, 1), mat=M_TIMBER, col=(0.6, 0.53, 0.44), rng=rng,
                 chamfer=0.0)
        picket_run(g, rng, a_ + 0.06, c_ - 0.06)
    if gate:
        ang = 1.15
        hinge = V(1.39, 0.0, -0.05)
        d = V(-math.cos(ang), 0, -math.sin(ang))
        n = d.cross(UP)
        w_ = 1.06
        for y in (0.22, 0.75):
            beam(g, [hinge + V(0, y, 0), hinge + d * w_ + V(0, y, 0)], 0.08, 0.045, up=tuple(n), mat=M_TIMBER,
                 col=(0.6, 0.53, 0.44), rng=rng, chamfer=0.0)
        beam(g, [hinge + V(0, 0.22, 0), hinge + d * w_ + V(0, 0.75, 0)], 0.07, 0.045, up=tuple(n), mat=M_TIMBER,
             col=(0.6, 0.53, 0.44), rng=rng, chamfer=0.0)
        for k in range(6):
            p = hinge + d * (0.09 + k * 0.176) + n * 0.04
            beam(g, [p + V(0, 0.05, 0), p + V(0, 0.98, 0)], 0.1, 0.025, up=tuple(n), mat=M_PLANK, mode="plank", chamfer=0.0,
                 point=0.07, col=scale((0.8, 0.72, 0.6), rng.uniform(0.8, 1.0)), rng=rng)
    return b


def town_fence_picket_gate(rng):
    return town_fence_picket(rng, gate=True)


def town_garden(rng):
    """Kitchen garden, 3.2 x 2.6: three beds (cabbages, onions, a bean tepee), a hoe, a clay pot."""
    b = Builder()
    g = G(b)
    beds = [(-1.05, (0.36, 0.5, 0.3)), (0.0, (0.46, 0.58, 0.32)), (1.05, (0.3, 0.46, 0.26))]
    for k, (x, col) in enumerate(beds):
        mound(g, (x, -0.04, 0.0), 0.42, 1.25, 0.16, rng, mat=M_EARTH, col_fn=lambda p, n: (0.42, 0.33, 0.25), rings=2, seg=10,
              rough=0.05)
        if k == 0:
            for j in range(6):
                for dx in (-0.16, 0.16):
                    stone(g, (x + dx, 0.17, -0.95 + j * 0.38), (0.13, 0.1, 0.13), rng, mat=M_FRUIT, detail=0, rough=0.2,
                          cuts=0, col_fn=lambda p, n, c=col: scale(c, 0.7 + 0.45 * max(n.y, 0.0)), tile=0.3)
        elif k == 1:
            for j in range(9):
                for dx in (-0.15, 0.0, 0.15):
                    p = V(x + dx, 0.12, -1.0 + j * 0.25)
                    tri = [p + V(-0.03, 0, 0), p + V(0.03, 0, 0), p + V(rng.uniform(-0.04, 0.04), 0.26, 0.02)]
                    for want in ((0, 0, 1), (0, 0, -1)):
                        face(g, tri, want, M_FRUIT, col, tile=0.2)
        else:
            top = V(x, 1.85, 0.15)
            for a in (0.4, 2.0, 3.6, 5.2):
                pole(g, V(x + 0.38 * math.cos(a), -0.1, 0.15 + 0.38 * math.sin(a)), top, 0.02, 0.016, rng, col=POST_C, sides=4,
                     segs=1)
                for h in (0.45, 0.95, 1.4):
                    f = h / 1.85
                    stone(g, (x + 0.38 * math.cos(a) * (1 - f), h, 0.15 + 0.38 * math.sin(a) * (1 - f)), (0.12, 0.16, 0.12),
                          rng, mat=M_FRUIT, detail=0, rough=0.25, cuts=0,
                          col_fn=lambda p, n, c=col: scale(c, 0.65 + 0.4 * max(n.y, 0.0)), tile=0.3)
            for j in range(3):
                stone(g, (x + rng.uniform(-0.15, 0.15), 0.15, -0.65 - j * 0.3), (0.14, 0.09, 0.14), rng, mat=M_FRUIT, detail=0,
                      rough=0.2, cuts=0, col_fn=lambda p, n: (0.4, 0.55, 0.28), tile=0.3)
    pole(g, V(1.5, -0.02, -0.4), V(1.2, 1.35, 0.1), 0.018, 0.016, rng, col=(0.72, 0.62, 0.5), sides=4, segs=1)
    lbox(g, V(1.52, 0.05, -0.45), (0.2, 0.1, 0.02), quat_y(0.4), M_IRON, IRON_D, tile=0.2)
    lathe(g, (-1.6, 0.0, 1.1), (0, 1, 0), [(0.0, 0.1), (0.12, 0.15), (0.26, 0.11), (0.3, 0.06)], 8, M_FRUIT, (0.62, 0.36, 0.22),
          tile=0.3)
    return b


def town_woodpile(rng):
    b = Builder()
    g = G(b)
    woodpile(g, rng, (0.0, 0.0, 0.0), L=1.8, rows=4)
    lbox(g, V(0, 1.02, 0.0), (2.2, 0.05, 0.8), quat_x(0.18), M_PLANK, (0.5, 0.45, 0.4), tile=1.0, grain=0)
    chopping_block(g, rng, (0.4, 0.0, 0.95))
    return b


def mono_roof(g, rng, W, z0, z1, y0, y1, over=0.35, verge=0.2, t=0.07, col=(0.55, 0.49, 0.42), lips=True):
    """Mono-pitch plank roof whose UNDERSIDE runs from (z0, y0) at the high back to (z1, y1) at the
    front wall line, overhanging the front by `over`; nothing reaches behind z0."""
    D = z1 - z0
    th = math.atan2(y0 - y1, D)
    Ls = (D + over) / math.cos(th)
    zm = z0 + (D + over) / 2
    ym = y0 - (zm - z0) * math.tan(th)
    n = V(0, math.cos(th), math.sin(th))
    s = V(0, -math.sin(th), math.cos(th))
    c = V(0, ym, zm) + n * (t / 2)
    q = quat_x(th)
    Wx = W + 2 * verge
    lbox(g, c, (Wx, t, Ls), q, M_PLANK, [scale(col, 0.75), None, col], tile=1.2, grain=0)
    if lips:
        k = int(Ls / 0.42)
        for i in range(1, k + 1):
            p = c - s * (Ls / 2) + s * (Ls * i / (k + 0.3)) + n * (t / 2 + 0.012)
            lbox(g, p, (Wx, 0.03, 0.06), q, M_PLANK, scale(col, 0.82), tile=1.2, grain=0)
    return th


def board_side(g, rng, x, sx, z0, z1, ytop, k=None, col=(0.62, 0.55, 0.47), y0=-0.03):
    """A side wall of vertical boards in the plane x, from z0 to z1, each board up to ytop(z)."""
    k = k or max(3, int((z1 - z0) / 0.3))
    for i in range(k):
        z = z0 + (i + 0.5) * (z1 - z0) / k
        yt = ytop(z)
        board(g, V(x + sx * 0.02, (y0 + yt) / 2, z), (0, 1, 0), (sx, 0, 0), yt - y0, (z1 - z0) / k * 0.97, 0.035, mat=M_PLANK,
              col=scale(col, rng.uniform(0.8, 1.02)), rng=rng, chamfer=0.0)


def town_shed(rng):
    """Garden shed: plank walls on three sides, open front, mono-pitch roof, back flat at -Z so it
    can stand against a house or fence; tools, a barrel, a scythe."""
    b = Builder()
    g = G(b)
    HX, HZ = 1.2, 0.9
    yb, yf = 2.0, 1.6
    th = mono_roof(g, rng, 2 * HX, -HZ, HZ, yb, yf, over=0.35, verge=0.18, lips=False)
    ytop = lambda z: yb - (z + HZ) * math.tan(th)  # noqa: E731
    lbox(g, V(0, yb / 2, -HZ + 0.03), (2 * HX, yb, 0.06), quat_y(0.0), M_PLANK, (0.55, 0.49, 0.41), tile=1.0)
    for x, sx in ((-HX, -1), (HX, 1)):
        board_side(g, rng, x, sx, -HZ + 0.06, HZ, ytop, k=5)
        beam(g, [V(x, -0.05, HZ - 0.05), V(x, yf, HZ - 0.05)], 0.11, 0.11, mat=M_TIMBER, col_fn=weathered(TF, 0.7), rng=rng,
             chamfer=0.0)
    beam(g, [V(-HX - 0.1, yf - 0.06, HZ - 0.05), V(HX + 0.1, yf - 0.06, HZ - 0.05)], 0.11, 0.12, mat=M_TIMBER, col=TF, rng=rng,
         chamfer=0.0)
    lbox(g, V(0, 0.03, 0), (2 * HX - 0.1, 0.06, 2 * HZ - 0.1), quat_y(0.0), M_EARTH, (0.4, 0.34, 0.28), tile=0.8)
    for x, top in ((-0.75, 1.55), (-0.5, 1.45)):
        pole(g, V(x, 0.02, -HZ + 0.12), V(x + 0.05, top, -HZ + 0.1), 0.018, 0.016, rng, col=(0.72, 0.62, 0.5), sides=4, segs=1)
    lbox(g, V(-0.75, 1.55, -HZ + 0.12), (0.36, 0.04, 0.05), quat_y(0.0), M_TIMBER, (0.6, 0.52, 0.42), tile=0.2)
    lbox(g, V(-0.49, 0.12, -HZ + 0.14), (0.18, 0.24, 0.02), quat_y(0.0), M_IRON, IRON_D, tile=0.2)
    pole(g, V(0.0, 1.5, -HZ + 0.1), V(0.9, 1.25, -HZ + 0.1), 0.02, 0.018, rng, col=(0.72, 0.62, 0.5), sides=4, segs=1)
    face(g, [V(0.85, 1.25, -HZ + 0.11), V(0.3, 0.95, -HZ + 0.11), V(0.8, 1.15, -HZ + 0.11)], (0, 0, 1), M_IRON,
         (0.5, 0.5, 0.52), tile=0.2)
    barrel(g, rng, (0.7, 0.06, -0.3))
    sack(g, rng, (0.15, 0.27, -0.45))
    return b


def hen(g, rng, c, yaw_a, col):
    q = quat_y(yaw_a)
    stone(g, c + V(0, 0.16, 0), (0.12, 0.1, 0.16), rng, mat=M_FRUIT, detail=1, rough=0.05, cuts=0, rot=q,
          col_fn=lambda p, n: scale(col, 0.8 + 0.25 * max(n.y, 0.0)), tile=0.3)
    stone(g, c + q @ V(0, 0.3, 0.13), (0.055, 0.065, 0.06), rng, mat=M_FRUIT, detail=0, rough=0.02, cuts=0,
          col_fn=lambda p, n: col, tile=0.3)
    lbox(g, c + q @ V(0, 0.37, 0.12), (0.015, 0.04, 0.05), q, M_FRUIT, (0.8, 0.1, 0.08), tile=0.1)
    lbox(g, c + q @ V(0, 0.3, 0.19), (0.02, 0.02, 0.04), q, M_FRUIT, (0.9, 0.62, 0.15), tile=0.1)
    face(g, [c + q @ V(0, 0.2, -0.12), c + q @ V(0, 0.36, -0.2), c + q @ V(0, 0.22, -0.2)], q @ V(1, 0, 0), M_FRUIT,
         scale(col, 0.75), tile=0.1)


def town_coop(rng):
    """Hen house on legs: plank box, mono-pitch roof, a slatted ramp, two hens."""
    b = Builder()
    g = G(b)
    HX, HZ = 0.65, 0.5
    fl, yb, yf = 0.45, 1.25, 1.05
    for x in (-HX + 0.05, HX - 0.05):
        for z in (-HZ + 0.05, HZ - 0.05):
            beam(g, [V(x, -0.05, z), V(x, fl, z)], 0.07, 0.07, mat=M_TIMBER, col=(0.55, 0.48, 0.4), rng=rng, chamfer=0.0)
    lbox(g, V(0, fl + 0.02, 0), (2 * HX, 0.04, 2 * HZ), quat_y(0.0), M_PLANK, (0.55, 0.48, 0.4), tile=0.6)
    ytop = lambda z: yb - (z + HZ) * (yb - yf) / (2 * HZ)  # noqa: E731
    for x, sx in ((-HX, -1), (HX, 1)):
        board_side(g, rng, x, sx, -HZ, HZ, ytop, k=3, y0=fl)
    for z, sz, yt in ((HZ, 1, yf), (-HZ, -1, yb)):
        lbox(g, V(0, (fl + yt) / 2, z + sz * 0.02), (2 * HX, yt - fl, 0.04), quat_y(0.0), M_PLANK, (0.6, 0.53, 0.44), tile=0.6)
    lbox(g, V(0.25, fl + 0.2, HZ + 0.045), (0.22, 0.28, 0.01), quat_y(0.0), M_PLASTER, VOID, tile=0.3)
    mono_roof(g, rng, 2 * HX, -HZ - 0.04, HZ, yb + 0.02, yf + 0.02, over=0.15, verge=0.1, t=0.05, lips=False)
    a, c_ = V(0.25, fl + 0.06, HZ + 0.05), V(0.25, 0.0, HZ + 0.75)
    lbox(g, a.lerp(c_, 0.5), (0.22, 0.03, (c_ - a).length), quat_x(math.atan2(a.y - c_.y, c_.z - a.z)), M_PLANK,
         (0.6, 0.53, 0.44), tile=0.5)
    for k in range(4):
        p = a.lerp(c_, (k + 0.5) / 4) + V(0, 0.025, 0)
        lbox(g, p, (0.22, 0.02, 0.025), quat_y(0.0), M_TIMBER, (0.5, 0.44, 0.36), tile=0.2)
    for p, yaw_a, col in (((-0.55, 0.0, 0.75), 0.6, (0.95, 0.92, 0.85)), ((0.8, 0.0, 0.55), -1.2, (0.62, 0.4, 0.24))):
        hen(g, rng, V(*p), yaw_a, col)
    return b


def town_outhouse(rng):
    """The privy at the bottom of the plot: plank booth, mono-pitch roof, door ajar."""
    b = Builder()
    g = G(b)
    H = 0.5
    yb, yf = 1.85, 2.05
    ytop = lambda z: yb + (z + H) * (yf - yb) / (2 * H)  # noqa: E731
    for x, sx in ((-H, -1), (H, 1)):
        board_side(g, rng, x, sx, -H, H, ytop, k=4)
    lbox(g, V(0, yb / 2, -H - 0.02), (2 * H + 0.08, yb, 0.04), quat_y(0.0), M_PLANK, (0.58, 0.51, 0.43), tile=0.8)
    for x in (-H, H):
        beam(g, [V(x, -0.05, H), V(x, yf, H)], 0.09, 0.09, mat=M_TIMBER, col_fn=weathered(TF, 0.7), rng=rng, chamfer=0.0)
    beam(g, [V(-H - 0.05, yf - 0.06, H), V(H + 0.05, yf - 0.06, H)], 0.09, 0.1, mat=M_TIMBER, col=TF, rng=rng, chamfer=0.0)
    th = math.atan2(yf - yb, 2 * H)
    lbox(g, V(0, (yf + yb) / 2 + 0.06, 0.1), (2 * H + 0.35, 0.05, 2 * H / math.cos(th) + 0.5), quat_x(-th), M_PLANK,
         [(0.45, 0.4, 0.36), None, (0.55, 0.5, 0.43)], tile=0.8, grain=0)
    lbox(g, V(0, 0.5, -0.15), (2 * H - 0.08, 0.06, 0.6), quat_y(0.0), M_PLANK, (0.6, 0.52, 0.42), tile=0.4)
    lbox(g, V(0, 0.25, 0.14), (2 * H - 0.08, 0.5, 0.03), quat_y(0.0), M_PLANK, (0.55, 0.48, 0.4), tile=0.4)
    lbox(g, V(0, 0.95, -0.4), (2 * H - 0.08, 1.9, 0.02), quat_y(0.0), M_PLASTER, VOID, tile=0.4)
    door_leaf(g, rng, V(-H + 0.06, 0.0, H + 0.02), V(1, 0, 0), V(0, 0, 1), 2 * H - 0.12, 1.7, -0.7, col=(0.58, 0.5, 0.4))
    return b


def town_dung(rng):
    """Dung heap behind the byre: dark mound, fresh straw on top, a pitchfork stuck in."""
    b = Builder()
    g = G(b)
    mound(g, (0, -0.05, 0), 1.0, 0.8, 0.55, rng, mat=M_EARTH, col_fn=lambda p, n: (0.3, 0.24, 0.18), rings=4, seg=14,
          rough=0.25)
    mound(g, (0.15, 0.3, -0.1), 0.6, 0.45, 0.2, rng, mat=M_THATCH, col_fn=lambda p, n: (0.72, 0.6, 0.4), rings=3, seg=12,
          rough=0.3)
    p0, p1 = V(-0.35, 0.25, 0.2), V(-0.6, 1.55, 0.45)
    pole(g, p0, p1, 0.02, 0.018, rng, col=(0.72, 0.62, 0.5), sides=4, segs=1)
    d = (p1 - p0).normalized()
    side = d.cross(V(0, 0, 1)).normalized()
    for k in (-1, 0, 1):
        tube(g, [p0 + side * (k * 0.07), p0 + side * (k * 0.07) - d * 0.3], [0.008, 0.006], 3, M_IRON, IRON_D, tile=0.2,
             cap=False)
    tube(g, [p0 - side * 0.08, p0 + side * 0.08], [0.012, 0.012], 3, M_IRON, IRON_D, tile=0.2, cap=False)
    return b


def town_hayrick(rng):
    """A hay rick: a beehive stack round a central pole on a straw skirt, a ladder against it."""
    b = Builder()
    g = G(b)
    pole(g, V(0, -0.1, 0), V(0.02, 3.3, 0.01), 0.06, 0.045, rng, col=(0.7, 0.62, 0.5), sides=5, segs=2)
    prof = [(0.0, 1.05), (0.4, 1.2), (1.1, 1.22), (1.8, 1.02), (2.35, 0.62), (2.75, 0.22), (2.9, 0.05)]
    lathe(g, (0, -0.05, 0), (0, 1, 0), prof, 12, M_THATCH, (0.92, 0.82, 0.55), tile=0.7)
    mound(g, (0, -0.04, 0), 1.45, 1.45, 0.12, rng, mat=M_THATCH, col_fn=lambda p, n: (0.82, 0.72, 0.48), rings=2, seg=14)
    ladder(g, rng, V(1.75, -0.03, 0.4), V(0.85, 2.1, 0.2), width=0.42)
    return b


# ─────────────────────────────────────────────────────────────── 11. lean-tos inside the walls
def leanto(g, rng, W, D, yb, yf, posts, parapet=None, col=(0.6, 0.53, 0.45)):
    """Lean-to against the curtain: back flat in the plane z = -D/2 (plank back panel, nothing
    behind it), mono-pitch plank roof from yb at the back down to yf at the front post line z = D/2,
    board side walls, front posts at `posts` (x) under a plate, open front (or a plank parapet up
    to `parapet` with a doorway gap {x0, x1})."""
    HX, HZ = W / 2, D / 2
    th = mono_roof(g, rng, W, -HZ, HZ, yb, yf, over=0.45, verge=0.22)
    ytop = lambda z: yb - (z + HZ) * math.tan(th)  # noqa: E731
    lbox(g, V(0, yb / 2, -HZ + 0.03), (W + 0.1, yb, 0.06), quat_y(0.0), M_PLANK, scale(col, 0.85), tile=1.2)
    for x, sx in ((-HX, -1), (HX, 1)):
        board_side(g, rng, x, sx, -HZ + 0.06, HZ - 0.06, ytop, col=col)
    for x in posts:
        beam(g, [V(x, -0.05, HZ), V(x, yf - 0.2, HZ)], 0.17, 0.17, mat=M_TIMBER, col_fn=weathered(TF, 0.7), rng=rng,
             chamfer=0.0)
    beam(g, [V(-HX - 0.12, yf - 0.1, HZ), V(HX + 0.12, yf - 0.1, HZ)], 0.17, 0.2, mat=M_TIMBER, col=TF, rng=rng, chamfer=0.0)
    beam(g, [V(-HX, yb - 0.12, -HZ + 0.14), V(HX, yb - 0.12, -HZ + 0.14)], 0.15, 0.16, mat=M_TIMBER, col=TF, rng=rng,
         chamfer=0.0)
    for x in posts:
        beam(g, [V(x, yb - 0.24, -HZ + 0.15), V(x, yf - 0.14, HZ)], 0.12, 0.12, mat=M_TIMBER, col=scale(TF, 0.9), rng=rng,
             chamfer=0.0)
        for sx in (-1, 1):
            if abs(x + sx * 0.5) < HX:
                beam(g, [V(x, yf - 0.75, HZ), V(x + sx * 0.5, yf - 0.2, HZ)], 0.1, 0.1, mat=M_TIMBER, col=TF, rng=rng,
                     chamfer=0.0)
    if parapet:
        h, gaps = parapet
        xs = sorted(posts)
        for a_, c_ in zip(xs, xs[1:]):
            for g0, g1 in gaps:
                if a_ >= g0 and c_ <= g1:
                    break
            else:
                lbox(g, V((a_ + c_) / 2, h / 2, HZ - 0.03), (c_ - a_ - 0.17, h, 0.05), quat_y(0.0), M_PLANK, col, tile=1.0,
                     grain=1)
                beam(g, [V(a_, h, HZ), V(c_, h, HZ)], 0.1, 0.08, mat=M_TIMBER, col=TF, rng=rng, chamfer=0.0)
    lbox(g, V(0, 0.015, 0.0), (W - 0.1, 0.03, D - 0.1), quat_y(0.0), M_EARTH, (0.42, 0.36, 0.3), tile=1.0)
    return ytop


def hay_rack(g, rng, x0, x1, z, y0=1.15, y1=1.75):
    beam(g, [V(x0, y1, z + 0.4), V(x1, y1, z + 0.4)], 0.07, 0.07, mat=M_TIMBER, col=TF, rng=rng, chamfer=0.0)
    beam(g, [V(x0, y0, z + 0.05), V(x1, y0, z + 0.05)], 0.07, 0.07, mat=M_TIMBER, col=TF, rng=rng, chamfer=0.0)
    n = int((x1 - x0) / 0.16)
    for k in range(n + 1):
        x = x0 + (x1 - x0) * k / n
        pole(g, V(x, y0, z + 0.05), V(x, y1, z + 0.4), 0.014, 0.014, rng, mat=M_TIMBER, col=(0.6, 0.52, 0.42), sides=3, segs=1,
             wobble=0.0)
    mound(g, ((x0 + x1) / 2, y0 + 0.05, z + 0.2), (x1 - x0) / 2 - 0.05, 0.2, 0.35, rng, mat=M_THATCH,
          col_fn=lambda p, n: (0.8, 0.72, 0.48), rings=2, seg=10)


def castle_stable(rng):
    """Stable lean-to, three stalls open to the yard: plank partitions, hay racks + mangers on the
    back wall, straw bedding, a bucket and a pitchfork, a saddle over a partition."""
    b = Builder()
    g = G(b)
    W, D = 7.2, 3.4
    HZ = D / 2
    leanto(g, rng, W, D, 3.0, 2.15, (-3.6, -1.2, 1.2, 3.6))
    for x in (-1.2, 1.2):
        beam(g, [V(x, -0.05, -HZ + 0.1), V(x, 1.5, -HZ + 0.1)], 0.12, 0.12, mat=M_TIMBER, col=TF, rng=rng, chamfer=0.0)
        for y in (0.35, 0.75, 1.15):
            board(g, V(x, y, -0.05), (0, 0, 1), (1, 0, 0), D - 0.25, 0.32, 0.05, mat=M_PLANK,
                  col=scale((0.6, 0.52, 0.42), rng.uniform(0.85, 1.0)), rng=rng, chamfer=0.0)
    for k, x in enumerate((-2.4, 0.0, 2.4)):
        hay_rack(g, rng, x - 0.85, x + 0.85, -HZ + 0.06)
        lbox(g, V(x, 0.42, -HZ + 0.32), (1.5, 0.3, 0.42), quat_y(0.0), M_PLANK, (0.5, 0.43, 0.35), tile=0.6)
        lbox(g, V(x, 0.575, -HZ + 0.32), (1.4, 0.01, 0.32), quat_y(0.0), M_THATCH, (0.78, 0.68, 0.45), tile=0.4)
        mound(g, (x, -0.02, 0.1), 1.0, 1.3, 0.1, rng, mat=M_THATCH, col_fn=lambda p, n: (0.8, 0.7, 0.46), rings=2, seg=10)
    bucket(g, (2.0, 0.0, 1.3))
    pole(g, V(3.4, -0.02, 1.25), V(3.15, 1.6, 1.5), 0.02, 0.018, rng, col=(0.72, 0.62, 0.5), sides=4, segs=1)
    # Saddle over the first partition.
    lathe(g, (-1.2, 1.25, 0.6), (0, 0, 1), [(0.0, 0.18), (0.25, 0.2), (0.5, 0.17)], 8, M_HIDE, (0.48, 0.3, 0.18), tile=0.3)
    return b


def bunk(g, rng, c, L=1.6, Dp=0.75):
    C = Vector(c)
    for sx in (-1, 1):
        for sz in (-1, 1):
            beam(g, [C + V(sx * L / 2, -0.03, sz * Dp / 2), C + V(sx * L / 2, 1.85, sz * Dp / 2)], 0.08, 0.08, mat=M_TIMBER,
                 col=(0.55, 0.47, 0.38), rng=rng, chamfer=0.0)
    for y in (0.38, 1.3):
        lbox(g, C + V(0, y, 0), (L, 0.06, Dp), quat_y(0.0), M_PLANK, (0.58, 0.5, 0.4), tile=0.6)
        lbox(g, C + V(0, y + 0.08, 0), (L - 0.1, 0.1, Dp - 0.1), quat_y(0.0), M_CLOTH, scale(HESSIAN, 0.95), tile=0.5)
        lbox(g, C + V(0.25, y + 0.14, 0.02), (L * 0.55, 0.03, Dp - 0.06), quat_y(0.0), M_CLOTH, (0.42, 0.4, 0.5), tile=0.5)


def round_shield(g, c, n, r, col_a, col_b):
    C, N = Vector(c), Vector(n).normalized()
    u = N.cross(UP).normalized()
    v = u.cross(N)
    k = 12
    ring = [C + (u * math.cos(2 * math.pi * i / k) + v * math.sin(2 * math.pi * i / k)) * r for i in range(k)]
    face(g, ring, N, M_PLANK, col_a, tile=0.5)
    face(g, [p - N * 0.03 for p in ring], -N, M_PLANK, (0.4, 0.33, 0.26), tile=0.5)
    half = [C + N * 0.004 + (u * math.cos(math.pi * i / 6) + v * math.sin(math.pi * i / 6)) * (r * 0.98) for i in range(7)]
    face(g, half, N, M_FRUIT, col_b, tile=0.5)
    lathe(g, C, N, [(0.0, 0.07), (0.05, 0.05), (0.07, 0.0)], 6, M_IRON, IRON_D, tile=0.2)


def castle_barracks(rng):
    """Barracks lean-to, half-open front (plank parapet ~1.0 high, a doorway): three two-tier bunks
    on the back wall, a table and bench, shields + helmets on pegs, a spear rack outside (+X end)."""
    b = Builder()
    g = G(b)
    W, D = 7.6, 3.6
    HX, HZ = W / 2, D / 2
    leanto(g, rng, W, D, 3.1, 2.25, (-3.8, -2.6, -1.3, 0.0, 1.3, 2.6, 3.8), parapet=(1.0, [(-1.3, 0.0)]))
    for x in (-2.6, 0.55, 2.65):
        bunk(g, rng, (x, 0.0, -HZ + 0.45))
    lbox(g, V(-1.8, 0.72, 0.6), (1.5, 0.06, 0.7), quat_y(0.05), M_PLANK, (0.62, 0.54, 0.44), tile=0.6)
    for sx in (-1, 1):
        for sz in (-1, 1):
            beam(g, [V(-1.8 + sx * 0.62, -0.02, 0.6 + sz * 0.25), V(-1.8 + sx * 0.6, 0.7, 0.6 + sz * 0.25)], 0.06, 0.06,
                 mat=M_TIMBER, col=(0.55, 0.47, 0.38), rng=rng, chamfer=0.0)
    bench(g, rng, V(-1.8, 0.0, 1.2), 0.05, L=1.4)
    tankard(g, (-1.6, 0.75, 0.55))
    # Shields + kettle helms on the side walls (inside).
    for z, ca, cb in ((-0.35, (0.2, 0.32, 0.6), (0.95, 0.92, 0.85)), (0.55, (0.95, 0.92, 0.85), (0.2, 0.32, 0.6))):
        round_shield(g, (-HX + 0.12, 1.75, z), (1, 0, 0), 0.36, ca, cb)
    for z in (-0.6, 0.2):
        kettle_helm(g, rng, (HX - 0.25, 1.62, z), tilt=(0.0, 0.25), s=0.9)
    # Spear rack outside the +X end.
    x0 = HX + 0.55
    for z in (-0.6, 0.9):
        beam(g, [V(x0, -0.05, z), V(x0, 1.25, z)], 0.08, 0.08, mat=M_TIMBER, col=(0.55, 0.47, 0.38), rng=rng, chamfer=0.0)
    for y in (0.25, 1.15):
        beam(g, [V(x0, y, -0.7), V(x0, y, 1.0)], 0.06, 0.06, mat=M_TIMBER, col=(0.55, 0.47, 0.38), rng=rng, chamfer=0.0)
    for k in range(5):
        z = -0.45 + k * 0.3
        p0, p1 = V(x0 - 0.06, 0.05, z), V(x0 + 0.12, 2.35, z + 0.05)
        pole(g, p0, p1, 0.018, 0.016, rng, col=(0.7, 0.6, 0.46), sides=4, segs=1)
        d = (p1 - p0).normalized()
        face(g, [p1 - V(0, 0, 0.04), p1 + V(0, 0, 0.04), p1 + d * 0.22], (1, 0, 0), M_IRON, (0.6, 0.6, 0.62), tile=0.2)
        face(g, [p1 - V(0, 0, 0.04), p1 + V(0, 0, 0.04), p1 + d * 0.22], (-1, 0, 0), M_IRON, (0.6, 0.6, 0.62), tile=0.2)
    return b


def castle_store(rng):
    """Store shed lean-to, open front: stacked crates, sacks, barrels, a sack barrow."""
    b = Builder()
    g = G(b)
    W, D = 5.6, 3.2
    HZ = D / 2
    leanto(g, rng, W, D, 2.9, 2.1, (-2.8, 0.0, 2.8))
    for p, s_, a in (((-2.0, 0.3, -1.0), (0.7, 0.6, 0.6), 0.0), ((-1.25, 0.3, -1.05), (0.7, 0.6, 0.6), 0.04),
                     ((-1.65, 0.88, -1.0), (0.66, 0.56, 0.56), -0.06), ((-2.1, 0.25, -0.2), (0.6, 0.5, 0.5), 0.3),
                     ((1.9, 0.3, -1.05), (0.7, 0.6, 0.6), -0.03)):
        lbox(g, V(*p), s_, quat_y(a), M_PLANK, scale((0.72, 0.62, 0.5), rng.uniform(0.85, 1.0)), tile=0.6)
        for sy in (-1, 1):
            lbox(g, V(*p) + V(0, sy * (s_[1] / 2 - 0.03), 0), (s_[0] + 0.02, 0.06, s_[2] + 0.02), quat_y(a), M_TIMBER,
                 (0.42, 0.34, 0.26), tile=0.4)
    for k in range(3):
        barrel(g, rng, (0.0 + 0.55 * k, 0.03, -HZ + 0.4))
    barrel(g, rng, (0.27, 0.62, -HZ + 0.4))
    for p, lying in (((-0.5, 0.3, -0.3), False), ((-0.8, 0.3, 0.05), False), ((-0.55, 0.2, 0.4), True),
                     ((1.9, 0.75, -1.05), True), ((2.1, 0.3, -0.2), False)):
        sack(g, rng, p, lying)
    return b


def cart_wheel(g, rng, c, axis, r=0.55):
    C, A = Vector(c), Vector(axis).normalized()
    u = A.cross(UP).normalized() if abs(A.y) < 0.9 else V(1, 0, 0)
    v = A.cross(u).normalized()
    k = 14
    ring = [C + (u * math.cos(2 * math.pi * i / k) + v * math.sin(2 * math.pi * i / k)) * r for i in range(k + 1)]
    tube(g, ring, [0.045] * (k + 1), 4, M_TIMBER, (0.5, 0.42, 0.34), tile=0.5, cap=False)
    for i in range(6):
        a = 2 * math.pi * i / 6
        pole(g, C, C + (u * math.cos(a) + v * math.sin(a)) * (r - 0.03), 0.02, 0.018, rng, mat=M_TIMBER,
             col=(0.55, 0.46, 0.36), sides=4, segs=1, wobble=0.0)
    lathe(g, C - A * 0.1, A, [(0.0, 0.06), (0.2, 0.07)], 6, M_TIMBER, (0.45, 0.38, 0.3), tile=0.2)


def castle_cartshed(rng):
    """Cart shed lean-to, two open bays: a two-wheeled cart with its shafts down, a spare wheel
    against the side wall, a horse collar on a peg, a pile of sacks."""
    b = Builder()
    g = G(b)
    W, D = 6.4, 3.8
    HX, HZ = W / 2, D / 2
    leanto(g, rng, W, D, 3.0, 2.3, (-3.2, 0.0, 3.2))
    # Cart in the -X bay, tail to the back wall, shafts out to the yard and resting on the ground.
    cx, cz = -1.55, -0.2
    yb = 0.78
    lbox(g, V(cx, yb, cz), (1.3, 0.06, 2.0), quat_y(0.0), M_PLANK, (0.62, 0.53, 0.42), tile=0.8)
    for sx in (-1, 1):
        lbox(g, V(cx + sx * 0.63, yb + 0.2, cz), (0.05, 0.36, 2.0), quat_y(0.0), M_PLANK, (0.58, 0.5, 0.4), tile=0.8)
        beam(g, [V(cx + sx * 0.45, yb - 0.08, cz - 1.0), V(cx + sx * 0.45, 0.06, cz + 2.4)], 0.08, 0.1, mat=M_TIMBER,
             col=(0.55, 0.47, 0.38), rng=rng, chamfer=0.0)
        cart_wheel(g, rng, (cx + sx * 0.82, 0.55, cz + 0.1), (1, 0, 0))
    beam(g, [V(cx - 0.9, 0.55, cz + 0.1), V(cx + 0.9, 0.55, cz + 0.1)], 0.08, 0.08, mat=M_TIMBER, col=(0.45, 0.38, 0.3),
         rng=rng, chamfer=0.0)
    sack(g, rng, (cx - 0.25, yb + 0.25, cz - 0.4))
    sack(g, rng, (cx + 0.25, yb + 0.18, cz - 0.1), True)
    # Spare wheel against the +X wall, collar on a peg, a stack of sacks + a barrel in the +X bay.
    cart_wheel(g, rng, (HX - 0.18, 0.56, -0.4), (1, 0, 0.25))
    tube(g, [V(HX - 0.12, 1.55, 0.6 + 0.25 * math.cos(a)) + V(0, 0.32 * math.sin(a), 0) for a in np.linspace(0, 2 * math.pi, 9)],
         [0.06] * 9, 6, M_HIDE, (0.4, 0.27, 0.17), tile=0.3, cap=False)
    for p, lying in (((1.2, 0.3, -1.25), False), ((1.6, 0.3, -1.3), False), ((1.4, 0.55, -1.25), True)):
        sack(g, rng, p, lying)
    barrel(g, rng, (0.7, 0.03, -1.3))
    return b


def bounds(builder):
    v = np.array(builder.verts) if builder.verts else np.zeros((1, 3))
    gx, gy, gz = v[:, 0], v[:, 2], -v[:, 1]
    return {"tris": builder.tris(), "x": [round(float(gx.min()), 2), round(float(gx.max()), 2)],
            "z": [round(float(gz.min()), 2), round(float(gz.max()), 2)], "y": [round(float(gy.min()), 2), round(float(gy.max()), 2)]}


# The poor village outside the walls (user feedback: the cottages above read as modern): hipped
# shaggy thatch, clay daub / grey logs on fieldstone footings; same node names, see village_huts.py.
_vh = HERE / "village_huts.py"
exec(compile(_vh.read_text(encoding="utf-8"), str(_vh), "exec"))
_yp = HERE / "yard_props.py"
exec(compile(_yp.read_text(encoding="utf-8"), str(_yp), "exec"))


MODELS = {
    "town_granary": town_granary,
    "town_smithy": town_smithy,
    "town_tavern": town_tavern,
    "town_maud_house": town_maud_house,
    "town_infirmary": town_infirmary,
    "town_firepit": town_firepit,
    "town_grave": town_grave,
    "crown_banner_wall": crown_banner_wall,
    "crown_banner_pole": crown_banner_pole,
    "crown_crates": crown_crates,
    "crown_tent": crown_tent,
    "crown_gallows": crown_gallows,
    "crown_depot": crown_depot,
    "town_house_a": town_house_a,
    "town_house_b": town_house_b,
    "town_house_c": town_house_c,
    "town_house_d": town_house_d,
    "town_carpenter": town_carpenter,
    "town_archery": town_archery,
    # v3 (spec §2): the podgrodzie outside the W gate + the lean-tos against the curtain.
    "town_street_house_a": town_street_house_a,
    "town_street_house_b": town_street_house_b,
    "town_fence_wattle": town_fence_wattle,
    "town_fence_wattle_gate": town_fence_wattle_gate,
    "town_fence_picket": town_fence_picket,
    "town_fence_picket_gate": town_fence_picket_gate,
    "town_garden": town_garden,
    "town_woodpile": town_woodpile,
    "town_shed": town_shed,
    "town_coop": town_coop,
    "town_outhouse": town_outhouse,
    "town_dung": town_dung,
    "town_hayrick": town_hayrick,
    "castle_stable": castle_stable,
    "castle_barracks": castle_barracks,
    "castle_store": castle_store,
    "castle_cartshed": castle_cartshed,
    # The producer yards on the town build plots (village_huts.py; town.rs spawn_building).
    "town_farm": town_farm,
    "town_woodcutter": town_woodcutter,
    "town_mine": town_mine,
    # The castle yard corners + the courtyard well (castle.rs; same layouts as the old clusters).
    "yard_wood": yard_wood,
    "yard_hay": yard_hay,
    "yard_cart": yard_cart,
    "yard_well": yard_well,
    # Day-one castle furniture (castle_decor.rs).
    "decor_notice_board": decor_notice_board,
    "decor_trough": decor_trough,
    "decor_bench": decor_bench,
    "gate_brazier": gate_brazier,
    "training_dummy": training_dummy,
    "town_merchant_shop": town_merchant_shop,
    "meadow_hay_cart": meadow_hay_cart,
    "meadow_bale": meadow_bale,
    "meadow_scarecrow": meadow_scarecrow,
    "meadow_beehive": meadow_beehive,
    "meadow_firewood_rack": meadow_firewood_rack,
    "meadow_crates": meadow_crates,
}

ONLY = [a for a in sys.argv[sys.argv.index("--") + 1:]] if "--" in sys.argv else []
clear_scene()
objs = []
report = {}
for i, (name, fn) in enumerate(MODELS.items()):
    if ONLY and name not in ONLY:
        continue
    bld = fn(np.random.default_rng(7300 + i))
    report[name] = bounds(bld)
    objs.append(bld.build(name, MATS))
export_glb(OUT / "town_kit.glb", objs)
(OUT / "town_kit_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
for k, v in report.items():
    print(f"{k}: {v}")
print("TOWN_KIT_DONE", sum(v["tris"] for v in report.values()))
