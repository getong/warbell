"""Environmental-storytelling set-pieces for the WARM biomes -> stories_warm.glb (src/stories_warm.rs).

No text, no interaction: each one is a scene that explains itself.
  Desert: story_caravan  - an overturned wagon, its ox's skeleton still in the traces, spilled
                           amphorae and crates, the torn canopy half under the sand.
          story_ribs     - the bleached ribcage of some giant beast arching out of a dune, a spear
                           still lodged between the ribs.
          story_oasis    - a dead oasis: dry well with a collapsed windlass, dead palms, abandoned
                           water skins on a cracked clay pan.
  Swamp:  story_boat     - a half-sunken punt beside a collapsed stilt hut, nets still on the rack.
          story_shrine   - a drowned shrine: tilted stone idol, guttered candles, offerings, rag posts.
  Forest: story_hunter   - a hunter's camp: lean-to, hide-drying rack, cold fire, antlers on a stump.
          story_woodcut  - an abandoned woodcutters' site: felled log stack, sawhorse with the saw
                           still in the cut, an axe left in the stump.

Built with the wayside_models.py toolkit (beam / pole / tube / stone / slab / mound / sheet ...),
game coordinates (Y up), base at y = 0, ground-contact parts sink below it. Each model stays inside
the visual radius `FOOT` its placement reserves in stories_warm.rs, and its solid masses sit under
the blocker boxes registered there. Materials by name (the existing kit sets, vertex colour tints).

    blender -b --factory-startup --python tools/blender_forest/stories_warm.py
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.append(str(HERE))
# Reuse wayside_models' helpers (everything above its MODELS table) without running its export.
_src = (HERE / "wayside_models.py").read_text(encoding="utf-8")
exec(compile(_src[:_src.index("\nMODELS = {")], str(HERE / "wayside_models.py"), "exec"))

SAND = (1.0, 0.86, 0.64)
BONE = (0.84, 0.78, 0.66)
MUD = (0.13, 0.11, 0.08)
# Bleached bone: the untextured vertex-colour material (s_rock read as grey stone, not bone).
M_BONE = M_FRUIT
CLAY = (0.95, 0.55, 0.36)
WOOD = (0.82, 0.72, 0.58)
GREY_WOOD = (0.78, 0.76, 0.72)
WAX = (0.9, 0.84, 0.66)


def ngon(g, pts, mat, col, tile):
    """A flat polygon as a triangle fan (the exporter's tangent pass rejects n-gons)."""
    pts = [Vector(p) for p in pts]
    c = sum(pts, Vector((0, 0, 0))) / len(pts)
    for k in range(len(pts)):
        g.flat([pts[k], pts[(k + 1) % len(pts)], c], mat, col, tile)


def bez(p0, p1, p2, n):
    p0, p1, p2 = Vector(p0), Vector(p1), Vector(p2)
    out = []
    for k in range(n):
        t = k / (n - 1)
        out.append(p0 * (1 - t) ** 2 + p1 * (2 * t * (1 - t)) + p2 * (t * t))
    return out


def lathe(g, base, axis, profile, sides, mat, col, tile=0.5, col_fn=None):
    """A turned vessel / candle: `profile` = [(height along axis, radius)]."""
    a = Vector(axis).normalized()
    pts = [Vector(base) + a * h for h, _ in profile]
    tube(g, pts, [max(r, 0.003) for _, r in profile], sides, mat, col, tile=tile, col_fn=col_fn)


def amphora(g, base, axis, rng, s=1.0, col=CLAY):
    prof = [(0.0, 0.02), (0.05, 0.07), (0.18, 0.15), (0.34, 0.165), (0.47, 0.12), (0.55, 0.05), (0.62, 0.042),
            (0.66, 0.058)]
    k = rng.uniform(0.85, 1.05)
    lathe(g, base, axis, [(h * s, r * s) for h, r in prof], 10, M_EARTH, scale(col, k), tile=0.4,
          col_fn=lambda t: mix(scale(col, k), scale(SAND, 0.9), smoothstep(0.35, 0.0, t) * 0.5))


def sand_col(nz, base=SAND):
    def f(p, n):
        k = 0.9 + 0.1 * nz(p * 1.7)
        return scale(base, k)
    return f


def crate(g, c, rot, size, rng, col=WOOD, open_top=False):
    c = Vector(c)
    lbox(g, c, size, rot, M_PLANK, scale(col, rng.uniform(0.8, 1.0)), tile=1.0, grain=0)
    hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
    for sx in (-1, 1):
        for sz in (-1, 1):
            beam(g, [c + rot @ V(sx * (hx + 0.005), -hy, sz * (hz + 0.005)), c + rot @ V(sx * (hx + 0.005), hy, sz * (hz + 0.005))],
                 0.035, 0.035, up=tuple(rot @ V(0, 0, 1)), mat=M_PLANK, rng=rng, col=scale(col, 0.7))


def wheel(g, c, axis, r, rng, broken=0, col=GREY_WOOD):
    """Spoked cart wheel centred at `c`, axle along `axis`. `broken`: spokes / rim arc missing."""
    c, ax = Vector(c), Vector(axis).normalized()
    a0 = ax.orthogonal().normalized()
    b0 = ax.cross(a0)
    n = 18
    keep = n - broken * 3
    rim = [c + (a0 * math.cos(2 * math.pi * k / n) + b0 * math.sin(2 * math.pi * k / n)) * r for k in range(keep + 1)]
    tube(g, rim, [0.035] * len(rim), 5, M_BARK, scale(col, 0.8), tile=0.4, cap=broken > 0)
    if not broken:
        pass
    hub_a, hub_b = c - ax * 0.09, c + ax * 0.09
    tube(g, [hub_a, hub_b], [0.07, 0.07], 8, M_PLANK, scale(col, 0.75), tile=0.3)
    for k in range(10):
        if broken and k in (3, 4, 5):
            continue
        a = 2 * math.pi * k / 10
        d = a0 * math.cos(a) + b0 * math.sin(a)
        beam(g, [c + d * 0.06, c + d * (r - 0.02)], 0.035, 0.03, up=tuple(ax), mat=M_PLANK, rng=rng, col=col)
    # iron tyre band
    tube(g, rim, [0.038] * len(rim), 5, M_IRON, (0.42, 0.36, 0.32), tile=0.3, cap=broken > 0)


def skull(g, c, fwd, s, rng, horns=True, col=BONE):
    """A large-animal skull: cranium + snout, dark sockets, optional curving horns."""
    c, f = Vector(c), Vector(fwd).normalized()
    side = Vector((0, 1, 0)).cross(f).normalized()
    nz = Noise(rng, 3, 3.0)
    yaw = math.atan2(f.x, f.z)

    def bone(p, n):
        k = 0.85 + 0.15 * nz(p * 6.0)
        socket = 0.0
        for sg in (-1, 1):
            e = c + f * (0.18 * s) + side * (sg * 0.13 * s) + Vector((0, 0.06 * s, 0))
            socket = max(socket, smoothstep(0.075 * s, 0.035 * s, (p - e).length))
        nose = smoothstep(0.06 * s, 0.025 * s, (p - (c + f * 0.55 * s + Vector((0, 0.02 * s, 0)))).length)
        return mix(scale(col, k), (0.12, 0.1, 0.08), max(socket, nose))
    stone(g, tuple(c), (0.2 * s, 0.17 * s, 0.24 * s), rng, mat=M_BONE, detail=2, rough=0.06, cuts=1, rot=quat_y(yaw),
          col_fn=bone, tile=0.4)
    stone(g, tuple(c + f * 0.36 * s - Vector((0, 0.04 * s, 0))), (0.11 * s, 0.09 * s, 0.26 * s), rng, mat=M_BONE,
          detail=1, rough=0.05, cuts=0, rot=quat_y(yaw), col_fn=bone, tile=0.4)
    if horns:
        for sg in (-1, 1):
            r0 = c + side * (sg * 0.16 * s) + Vector((0, 0.1 * s, 0)) - f * 0.05 * s
            pts = bez(r0, r0 + side * (sg * 0.28 * s) + Vector((0, 0.05 * s, 0)), r0 + side * (sg * 0.36 * s) + Vector((0, 0.3 * s, 0)) + f * 0.12 * s, 6)
            tube(g, pts, [0.05 * s, 0.045 * s, 0.038 * s, 0.03 * s, 0.02 * s, 0.006 * s], 6, M_BONE,
                 (0.55, 0.5, 0.42), tile=0.3)


def long_bone(g, p0, p1, r, rng, col=BONE):
    p0, p1 = Vector(p0), Vector(p1)
    tube(g, [p0, p0.lerp(p1, 0.12), p0.lerp(p1, 0.5), p0.lerp(p1, 0.88), p1], [r * 1.7, r * 1.1, r, r * 1.1, r * 1.6],
         6, M_BONE, scale(col, rng.uniform(0.85, 1.0)), tile=0.3)


# ─────────────────────────────────────────────────────────────── desert
def story_caravan(rng):
    """FOOT 2.9. Wagon on its side centred (-0.4, -0.3) (collider half 1.2 x 0.55, yaw 0.25), the
    open bed facing +Z where the cargo spilled; the ox skeleton in front along +X; a wheel lying off."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 1.5)
    mound(g, (0.1, 0, 0.2), 2.8, 2.3, 0.12, rng, col_fn=sand_col(nz), tile=1.4, rings=6, seg=24, skirt=0.15, edge=0.1)
    roll = quat_x(math.radians(78))
    yaw = quat_y(0.25)
    W0 = V(-0.4, 0.5, -0.3)

    def T(p):
        return W0 + yaw @ (roll @ Vector(p))

    def R(d):
        return yaw @ (roll @ Vector(d))
    wc = (0.86, 0.76, 0.62)
    # Floor boards (along X), side boards (3 high), end boards.
    for k in range(5):
        z = -0.44 + k * 0.22
        board(g, T((0, 0.0, z)), R((1, 0, 0)), R((0, 1, 0)), 2.3, 0.21, 0.04, mat=M_PLANK,
              col=scale(wc, rng.uniform(0.75, 1.0)), rng=rng)
    for sz in (-1, 1):
        for k in range(3):
            if sz < 0 and k == 2:
                continue  # one top board of the upper side split off
            board(g, T((0, 0.1 + k * 0.14, sz * 0.56)), R((1, 0, 0)), R((0, 0, 1)), 2.3, 0.13, 0.035, mat=M_PLANK,
                  col=scale(wc, rng.uniform(0.7, 0.95)), rng=rng)
        for x in (-1.1, -0.35, 0.4, 1.1):
            beam(g, [T((x, -0.02, sz * 0.58)), T((x, 0.46, sz * 0.58))], 0.05, 0.05, up=tuple(R((0, 0, 1))),
                 mat=M_PLANK, rng=rng, col=scale(wc, 0.7))
    for sx in (-1, 1):
        for k in range(3):
            board(g, T((sx * 1.16, 0.1 + k * 0.14, 0)), R((0, 0, 1)), R((1, 0, 0)), 1.12, 0.13, 0.035, mat=M_PLANK,
                  col=scale(wc, rng.uniform(0.7, 0.9)), rng=rng)
    # Under-frame: axles + the upper wheels (horizontal now, up in the air), one smashed.
    for x in (-0.75, 0.75):
        beam(g, [T((x, -0.14, -0.72)), T((x, -0.14, 0.62))], 0.09, 0.09, mat=M_PLANK, rng=rng, col=scale(wc, 0.6))
        wheel(g, T((x, -0.14, -0.7)), R((0, 0, 1)), 0.42, rng, broken=1 if x > 0 else 0)
    # Drawbar, snapped, the ox yoke still on it.
    beam(g, [T((1.15, -0.1, 0)), T((1.9, -0.1, 0.05))], 0.08, 0.08, mat=M_PLANK, rng=rng, col=scale(wc, 0.65), jag=(0, 0.1))
    # Canopy hoops (one snapped) and the torn canvas spilling onto the sand on +Z.
    for x, brk in ((-0.8, False), (0.0, True)):
        arc = [T((x, 0.46 + 0.62 * math.sin(a), 0.56 * math.cos(a))) for a in np.linspace(0.0, math.pi * (0.55 if brk else 1.0), 8)]
        tube(g, arc, [0.02] * len(arc), 5, M_BARK, GREY_WOOD, tile=0.3)
    ni, nj = 9, 12
    grid = []
    for i in range(ni):
        u = i / (ni - 1)
        row = []
        for j in range(nj):
            v = j / (nj - 1)
            x = -1.55 + 2.1 * v
            z = 0.25 + u * 1.75
            y = 0.95 * (1 - u) ** 2.2 + 0.05 * math.sin(v * 9 + u * 5) - 0.02
            torn = u > 0.6 and (math.sin(v * 17.0) > 0.55 - 0.5 * (u - 0.6))
            if u > 0.85:
                y -= 0.12 * (u - 0.85) / 0.15  # the far edge sinks into the sand
            row.append((x + 0.15 * u * math.sin(v * 5), y if not torn else y - 0.15, z + (0.1 if torn else 0.0) * u))
        grid.append(row)

    def canvas(u, v):
        k = 0.85 + 0.1 * math.sin(u * 9 + v * 13)
        return mix(scale((0.93, 0.86, 0.7), k), scale(SAND, 0.85), smoothstep(0.55, 1.0, u) * 0.7)
    sheet(g, grid, M_CLOTH, canvas, tile=0.5, double=True)
    # Spilled cargo: amphorae (one standing, two lying, one smashed), crates (one burst).
    amphora(g, V(0.75, -0.05, 0.75), (0, 1, 0), rng, 1.0)
    amphora(g, V(0.3, 0.13, 1.15), (0.9, 0.05, 0.35), rng, 0.95)
    amphora(g, V(-1.55, 0.12, 0.7), (-0.4, 0.06, 0.9), rng, 0.9)
    lathe(g, V(1.15, 0.1, 1.35), (0.2, 0.1, 1.0), [(0.0, 0.11), (0.12, 0.15), (0.22, 0.14)], 10, M_EARTH, CLAY, tile=0.4)
    for k in range(6):
        a = rng.uniform(0, 6.28)
        p = V(1.3 + math.cos(a) * 0.3, 0.015, 1.1 + math.sin(a) * 0.25)
        slab(g, tuple(p), (rng.uniform(0.08, 0.14), 0.02, rng.uniform(0.06, 0.1)), quat_y(a) @ quat_x(rng.uniform(-0.3, 0.3)),
             rng, mat=M_EARTH, res=(2, 1, 2), round_r=0.005, rough=0.01, col_fn=lambda q, n: CLAY, tile=0.3)
    crate(g, V(-0.9, 0.18, 1.05), quat_y(0.7) @ quat_z(0.15), (0.42, 0.36, 0.38), rng)
    crate(g, V(-0.2, 0.15, 1.6), quat_y(-0.35) @ quat_x(0.5), (0.4, 0.32, 0.34), rng)
    # Ox skeleton lying in front of the wagon (+X), still near the yoke.
    sp = bez(V(1.0, 0.1, 0.55), V(1.6, 0.16, 0.45), V(2.2, 0.08, 0.75), 7)
    tube(g, sp, [0.045, 0.05, 0.05, 0.048, 0.042, 0.035, 0.03], 6, M_BONE, BONE, tile=0.3)
    for k in range(6):
        s = sp[1] + (sp[4] - sp[1]) * (k / 5)
        h = 0.42 - abs(k - 2.5) * 0.05
        broken = k in (1, 4)
        pts = bez(s, s + V(0.0, h, 0.15), s + V(0.05 * k - 0.1, 0.05, 0.5), 6)
        if broken:
            pts = pts[:4]
        tube(g, pts, [0.022, 0.02, 0.018, 0.016, 0.013, 0.01][:len(pts)], 5, M_BONE, scale(BONE, rng.uniform(0.85, 1.0)),
             tile=0.3)
    skull(g, V(2.25, 0.13, 0.92), (0.6, -0.1, 0.8), 0.95, rng)
    stone(g, (0.92, 0.1, 0.62), (0.2, 0.08, 0.17), rng, mat=M_BONE, detail=1, rough=0.1, col_fn=lambda p, n: BONE, tile=0.4)
    long_bone(g, V(0.6, 0.03, 0.15), V(1.15, 0.04, -0.15), 0.028, rng)
    long_bone(g, V(1.8, 0.03, 0.05), V(2.15, 0.03, -0.35), 0.026, rng)
    long_bone(g, V(1.5, 0.04, 1.2), V(1.95, 0.03, 1.45), 0.025, rng)
    # The lost wheel lying flat in the sand, half buried.
    wheel(g, V(-1.2, 0.03, -1.75), (0.05, 1.0, 0.1), 0.42, rng)
    return b


def story_ribs(rng):
    """FOOT 3.0. A giant beast's ribcage arching out of a dune: spine buried along X (-1.8..1.6),
    six rib pairs up to ~2.6u tall closing over the centreline, skull at +X, a spear lodged in a rib.
    Collider: the cage, half 1.7 x 1.25 at the origin."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 1.2)
    mound(g, (-0.6, 0, 0.0), 2.9, 2.0, 0.42, rng, col_fn=sand_col(nz), tile=1.6, rings=7, seg=26, skirt=0.2, edge=0.14)
    mound(g, (-2.0, 0, 0.3), 1.0, 1.1, 0.55, rng, col_fn=sand_col(nz), tile=1.6, rings=5, seg=18, skirt=0.2)
    bone = scale(BONE, 0.95)
    spine = bez(V(-2.0, 0.0, 0.05), V(0.0, 0.42, 0.0), V(1.9, 0.12, -0.05), 9)
    tube(g, spine, [0.12, 0.15, 0.17, 0.17, 0.16, 0.15, 0.14, 0.12, 0.1], 8, M_BONE, bone, tile=0.5)
    for k in range(9):
        p = spine[1] + (spine[7] - spine[1]) * (k / 8)
        p = bez(V(-2.0, 0.0, 0.05), V(0.0, 0.42, 0.0), V(1.9, 0.12, -0.05), 17)[2 + k * 1]
        stone(g, tuple(p + V(0, 0.15, 0)), (0.07, 0.12, 0.06), rng, mat=M_BONE, detail=1, rough=0.1,
              col_fn=lambda q, n: bone, tile=0.4)
    xs = [-1.45, -0.95, -0.42, 0.1, 0.6, 1.08]
    for i, x in enumerate(xs):
        f = math.sin(math.pi * (i + 0.8) / (len(xs) + 0.6))
        H = 0.8 + 1.8 * f
        Wd = 0.55 + 0.75 * f
        base_y = 0.25 + 0.15 * f
        for sg in (-1, 1):
            broken = (i, sg) in ((0, 1), (4, -1), (5, 1))
            p0 = V(x, base_y - 0.3, sg * 0.18)
            pts = bez(p0, V(x - 0.1, H * 0.95, sg * (Wd + 0.55)), V(x - 0.25, H, sg * 0.22), 11)
            if broken:
                pts = pts[:6 + (i % 3)]
            n = len(pts)
            radii = [0.12 - 0.075 * (k / 10) for k in range(n)]
            tube(g, pts, radii, 7, M_BONE, scale(bone, rng.uniform(0.88, 1.0)), tile=0.5,
                 col_fn=lambda t: mix(scale(SAND, 0.8), bone, smoothstep(0.0, 0.25, t)))
    # A fallen rib half in the sand.
    tube(g, bez(V(1.4, 0.0, 1.0), V(1.9, 0.25, 1.4), V(2.3, 0.02, 0.9), 8), [0.08, 0.075, 0.07, 0.065, 0.06, 0.05, 0.045, 0.035],
         6, M_BONE, bone, tile=0.5)
    # Skull, half buried, at the head end.
    skull(g, V(2.15, 0.2, -0.25), (0.8, -0.15, -0.5), 2.4, rng, horns=True)
    # The spear that didn't help: a broken shaft jammed between two ribs.
    tube(g, [V(-0.3, 0.05, 1.0), V(0.05, 1.3, 0.55)], [0.025, 0.022], 6, M_BARK, GREY_WOOD, tile=0.3, cap=True)
    tube(g, [V(0.05, 1.3, 0.55), V(0.12, 1.55, 0.46)], [0.03, 0.002], 4, M_IRON, (0.45, 0.33, 0.25), tile=0.2)
    return b


def story_oasis(rng):
    """FOOT 2.7. Cracked clay pan; the dry well at (0.2, -0.2) r 0.62 (collider 0.65 box); a dead palm
    standing at (-1.4, -1.0), another snapped at (1.6, 1.1) with its crown on the ground; water skins."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 5, 2.4)

    def pan(p, n):
        crack = abs(nz(p * 2.2))
        k = 0.9 + 0.1 * nz(p * 0.7)
        c = scale((0.95, 0.8, 0.62), k)
        return mix(c, (0.35, 0.27, 0.2), smoothstep(0.08, 0.02, crack) * 0.8)
    mound(g, (0, 0, 0), 2.6, 2.4, 0.05, rng, col_fn=pan, tile=1.0, rings=7, seg=26, skirt=0.12, edge=0.1)
    # The well: coursed stone drum, a ring of cap stones, the black mouth.
    wc = V(0.2, 0, -0.2)
    frustum(g, 0.64, 0.6, -0.2, 0.92, 16, M_STONE, (0.92, 0.84, 0.72), tile=1.0, centre=tuple(wc), segs=2)
    ngon(g, [wc + V(0.5 * math.cos(a), 0.7, 0.5 * math.sin(a)) for a in np.linspace(2 * math.pi, 0, 16, endpoint=False)],
           M_EARTH, (0.04, 0.035, 0.03), 1.0)
    for k in range(11):
        a = 2 * math.pi * k / 11 + rng.uniform(-0.05, 0.05)
        if k == 7:
            continue  # one cap stone has fallen in
        slab(g, tuple(wc + V(0.6 * math.cos(a), 0.76, 0.6 * math.sin(a))), (0.3, 0.13, 0.2), quat_y(-a + math.pi / 2), rng,
             res=(3, 2, 2), round_r=0.03, rough=0.04, col_fn=rock_col((0.9, 0.82, 0.7)), tile=0.6)
    slab(g, tuple(wc + V(0.95, 0.05, 0.5)), (0.3, 0.13, 0.2), quat_y(0.5) @ quat_z(0.3), rng, res=(3, 2, 2), round_r=0.03,
         rough=0.04, col_fn=rock_col((0.9, 0.82, 0.7)), tile=0.6)
    # Windlass: one post still up, the other and the crank beam fallen across the pan.
    beam(g, [wc + V(-0.78, -0.2, 0.0), wc + V(-0.8, 1.45, 0.02)], 0.1, 0.1, up=(0, 0, 1), mat=M_PLANK, rng=rng,
         col_fn=weathered(GREY_WOOD, 0.7))
    beam(g, [wc + V(0.85, 0.05, 0.35), wc + V(1.9, 0.06, -0.55)], 0.1, 0.1, mat=M_PLANK, rng=rng, col=scale(GREY_WOOD, 0.85), jag=(0.12, 0))
    pole(g, wc + V(-0.75, 1.32, 0.0), wc + V(0.2, 0.82, 0.55), 0.05, 0.05, rng, col=GREY_WOOD, sides=7)
    # The rope coil + the bucket, dropped where the last one gave up.
    for k in range(4):
        ring = [V(-0.45 + 0.17 * math.cos(a), 0.03 + 0.02 * k, 0.75 + 0.15 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 11)]
        tube(g, ring, [0.016] * len(ring), 4, M_CLOTH, ROPE, tile=0.25, cap=False)
    lathe(g, V(-0.95, 0.12, 0.45), (0.95, 0.1, 0.3), [(0.0, 0.13), (0.28, 0.16)], 10, M_PLANK, WOOD, tile=0.6)
    # Water skins: deflated, slumped, one with its cord.
    for p, yw in ((V(0.75, 0.05, 0.85), 0.4), (V(1.05, 0.05, 0.55), 1.7), (V(-0.2, 0.05, 1.25), 2.6)):
        rot = quat_y(yw)
        stone(g, tuple(p), (0.24, 0.07, 0.15), rng, mat=M_HIDE, detail=2, rough=0.18, cuts=1, rot=rot,
              col_fn=lambda q, n: (0.34, 0.24, 0.16), tile=0.3)
        neck = p + rot @ V(0.24, 0.02, 0)
        tube(g, [neck, neck + rot @ V(0.1, 0.03, 0.02)], [0.035, 0.025], 6, M_HIDE, (0.3, 0.2, 0.14), tile=0.2)
    # Dead palm, standing: ringed grey trunk, a skirt of dead fronds hanging.
    def palm(base, top_off, h, rad, fronds, fallen=False):
        base = Vector(base)
        top = base + Vector(top_off)
        pts = bez(base + V(0, -0.2, 0), base.lerp(top, 0.5) + V(0, 0, 0) + (V(0.25, 0, 0.1) if not fallen else V(0, 0.15, 0)), top, 9)
        tube(g, pts, [rad * (1.25 - 0.4 * k / 8) for k in range(9)], 8, M_BARK, (0.72, 0.68, 0.62), tile=0.35,
             col_fn=lambda t: scale((0.75, 0.7, 0.64), 0.85 + 0.15 * math.sin(t * 60.0)))
        tdir = (pts[-1] - pts[-2]).normalized()
        for k in range(fronds):
            a = 2 * math.pi * k / fronds + rng.uniform(-0.2, 0.2)
            d = V(math.cos(a), 0, math.sin(a))
            if fallen:
                d = (d - tdir * d.dot(tdir)).normalized()
            p0 = pts[-1]
            droop = rng.uniform(0.9, 1.4)
            if fallen:
                tip = p0 + d * 0.9 + tdir * 0.6
                tip.y = 0.02
                mid = p0 + d * 0.5 + tdir * 0.3
                mid.y = max(mid.y, 0.1)
            else:
                tip = p0 + d * 0.45 + V(0, -droop, 0)
                mid = p0 + d * 0.35 + V(0, 0.05, 0)
            rach = bez(p0, mid, tip, 6)
            tube(g, rach, [0.02, 0.018, 0.015, 0.012, 0.009, 0.005], 4, M_BARK, (0.55, 0.45, 0.32), tile=0.3, cap=False)
            # The dead leaflets as a narrow drooping strip of straw-coloured blade.
            side = d.cross(V(0, 1, 0)).normalized()
            if side.length < 0.1:
                side = V(1, 0, 0)
            grid = [[tuple(q + side * w * 0.14 * math.sin(math.pi * j / 5) + V(0, -abs(w) * 0.05, 0)) for j, q in enumerate(rach)]
                    for w in (-1.0, 0.0, 1.0)]
            sheet(g, grid, M_THATCH, lambda u, v: mix((0.62, 0.5, 0.33), (0.42, 0.33, 0.22), v), tile=0.3, double=True)
    palm(V(-1.45, 0, -1.0), (0.35, 3.0, -0.2), 3.0, 0.14, 7)
    beam(g, [V(1.6, -0.2, 1.1), V(1.62, 1.05, 1.08)], 0.22, 0.22, up=(0, 0, 1), mat=M_BARK, mode="bark", rng=rng,
         col=(0.7, 0.66, 0.6), jag=(0, 0.25), chamfer=0.4)
    palm(V(1.25, 0.1, 1.35), (-1.85, 0.0, 0.35), 2.0, 0.12, 6, fallen=True)
    return b


# ─────────────────────────────────────────────────────────────── swamp
def story_boat(rng):
    """FOOT 2.8. Mud flat; a punt half-sunk stern-first at (0.9, 0.5) yaw 0.45 (collider half 1.2 x 0.5);
    the collapsed stilt hut at (-1.0, -0.8) (collider half 0.8 x 0.7); a net rack at (1.2, -1.5)."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 1.8)

    def mud(p, n):
        k = 0.5 + 0.5 * nz(p * 1.5)
        wet = smoothstep(0.6, 1.6, math.hypot(p.x - 0.9, p.z - 0.5))
        return mix(scale(MUD, 0.55 + 0.25 * k), scale(MUD, 1.0 + 0.2 * k), wet)
    mound(g, (0, 0, 0), 2.7, 2.5, 0.06, rng, col_fn=mud, tile=1.0, rings=7, seg=26, skirt=0.15, edge=0.1)
    # The punt: a hull sheet (double sided so the inside shows), ribs, gunwales, a thwart, an oar.
    bc = V(0.9, -0.18, 0.5)
    rot = quat_y(0.45) @ quat_z(math.radians(-11)) @ quat_x(math.radians(16))
    L, Wd, D = 1.35, 0.52, 0.4
    ni, nj = 11, 9
    grid = []
    for i in range(ni):
        u = -1 + 2 * i / (ni - 1)
        w = Wd * (1 - abs(u) ** 2.4) ** 0.6 + 0.03
        d = D * (1 - 0.35 * u * u)
        row = []
        for j in range(nj):
            phi = -math.pi / 2 + math.pi * j / (nj - 1)
            row.append(tuple(bc + rot @ V(u * L, D * 0.5 - d * math.cos(phi) ** 0.8, w * math.sin(phi))))
        grid.append(row)

    def hull(u, v):
        k = 0.8 + 0.1 * math.sin(v * 25.0)
        return mix(scale((0.52, 0.47, 0.4), k), scale(MUD, 0.7), smoothstep(0.4, 0.0, u) * 0.6)
    sheet(g, grid, M_PLANK, hull, tile=0.8, double=True)
    for side in (0, nj - 1):
        edge = [Vector(grid[i][side]) for i in range(ni)]
        tube(g, edge, [0.035] * ni, 5, M_PLANK, (0.45, 0.4, 0.34), tile=0.4)
    for i in (3, 5, 7):
        rib = [Vector(grid[i][j]) + (rot @ V(0, 0.02, 0)) for j in range(nj)]
        tube(g, rib, [0.022] * nj, 4, M_PLANK, (0.42, 0.37, 0.3), tile=0.3)
    board(g, bc + rot @ V(0.35, 0.12, 0), rot @ V(0, 0, 1), rot @ V(0, 1, 0), 1.0, 0.18, 0.04, mat=M_PLANK,
          col=(0.5, 0.44, 0.36), rng=rng)
    pole(g, V(-0.1, 0.04, 1.35), V(1.8, 0.03, 1.55), 0.025, 0.025, rng, col=(0.62, 0.56, 0.48), sides=6)
    board(g, V(1.95, 0.035, 1.57), (1, 0, 0.1), (0, 1, 0), 0.4, 0.14, 0.03, mat=M_PLANK, col=(0.6, 0.54, 0.46), rng=rng)
    # The stilt hut: two stilts still up, two snapped; its platform slid into the mud, roof after it.
    hc = V(-1.0, 0, -0.8)
    for (x, z, h, snapped) in ((-0.65, -0.55, 1.75, False), (0.65, -0.55, 1.7, False), (-0.65, 0.55, 0.55, True),
                               (0.65, 0.55, 0.4, True)):
        beam(g, [hc + V(x, -0.3, z), hc + V(x, h, z)], 0.11, 0.11, up=(0, 0, 1), mat=M_BARK, mode="bark", rng=rng,
             col_fn=weathered((0.6, 0.56, 0.48), 0.55), jag=(0, 0.15 if snapped else 0), chamfer=0.4)
    tilt = quat_x(math.radians(-38))
    pc = hc + V(0, 0.62, 0.1)
    for k in range(7):
        x = -0.6 + k * 0.2
        if k == 4:
            continue  # a missing board
        board(g, pc + tilt @ V(x, 0, 0), tilt @ V(0, 0, 1), tilt @ V(0, 1, 0), 1.25 - (0.3 if k == 6 else 0.0), 0.19, 0.04,
              mat=M_PLANK, col=scale((0.55, 0.5, 0.42), rng.uniform(0.8, 1.0)), rng=rng)
    # The back wall still hanging off the standing stilts.
    for k in range(4):
        board(g, hc + V(-0.05 + rng.uniform(-0.03, 0.03), 1.0 + k * 0.17, -0.6), (1, rng.uniform(-0.05, 0.05), 0),
              (0, 0, 1), 1.3 - (0.5 if k == 3 else 0.0), 0.16, 0.035, mat=M_PLANK, col=scale((0.5, 0.46, 0.4), 0.9), rng=rng)
    beam(g, [hc + V(-0.75, 1.7, -0.55), hc + V(0.75, 1.65, -0.55)], 0.09, 0.09, mat=M_BARK, mode="bark", rng=rng,
         col=(0.55, 0.5, 0.44))
    # The thatched roof slumped down in front, one corner in the mud.
    rq = quat_y(0.15) @ quat_x(math.radians(52))
    lbox(g, hc + V(0.05, 0.42, 0.75), (1.6, 0.16, 1.0), rq, M_THATCH, [scale((0.55, 0.48, 0.34), 0.6), None,
                                                                     (0.62, 0.55, 0.4)], tile=0.8, grain=2)
    # Net rack: two posts + a crossbar, the net sagging off it, a fish trap at its foot.
    nc = V(1.25, 0, -1.5)
    for x in (-0.7, 0.7):
        pole(g, nc + V(x, -0.3, 0), nc + V(x * 1.02, 1.45, 0.02), 0.04, 0.035, rng, col=(0.6, 0.56, 0.48), sides=6)
    pole(g, nc + V(-0.78, 1.4, 0.0), nc + V(0.78, 1.38, 0.02), 0.03, 0.03, rng, col=(0.6, 0.56, 0.48), sides=6)
    net = (0.3, 0.27, 0.22)
    cols_n, rows_n = 9, 7

    def npt(i, j):
        x = -0.65 + 1.3 * i / (cols_n - 1)
        t = j / (rows_n - 1)
        sag = 0.25 * math.sin(math.pi * i / (cols_n - 1)) * t
        return nc + V(x + 0.05 * math.sin(j * 1.3), 1.38 - t * 1.15 - sag, 0.04 + 0.12 * t * t)
    for i in range(cols_n):
        tube(g, [npt(i, j) for j in range(rows_n)], [0.006] * rows_n, 3, M_CLOTH, net, tile=0.2, cap=False)
    for j in range(1, rows_n):
        tube(g, [npt(i, j) for i in range(cols_n)], [0.006] * cols_n, 3, M_CLOTH, net, tile=0.2, cap=False)
    for k in range(5):
        stone(g, tuple(npt(k * 2, rows_n - 1) - V(0, 0.03, 0)), (0.03, 0.025, 0.03), rng, mat=M_ROCK, detail=1, cuts=0,
              col_fn=lambda q, n: (0.5, 0.48, 0.45), tile=0.2)
    frustum(g, 0.2, 0.08, 0.0, 0.55, 10, M_THATCH, (0.55, 0.47, 0.33), tile=0.4, centre=(0.3, 0, -1.0), segs=2)
    return b


def story_shrine(rng):
    """FOOT 1.9. A drowned shrine: tilted stone idol at (0, -0.35) (collider half 0.35 x 0.25), guttered
    candles on a flat stone at its feet, clay offering bowls, a small skull, three rotten rag posts."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 2.0)

    def mud(p, n):
        k = 0.5 + 0.5 * nz(p * 2.0)
        return scale(MUD, 0.5 + 0.35 * k + 0.35 * smoothstep(0.6, 1.6, math.hypot(p.x, p.z)))
    mound(g, (0, 0, 0), 1.8, 1.7, 0.05, rng, col_fn=mud, tile=0.9, rings=6, seg=22, skirt=0.12, edge=0.1)
    iq = quat_y(0.12) @ quat_x(math.radians(-13)) @ quat_z(math.radians(9))
    ic = V(0.0, 0.55, -0.35)
    sc = rock_col((0.7, 0.72, 0.66), moss=0.65, lichen=(0.32, 0.4, 0.2), ground=-0.1, noise=nz)
    slab(g, tuple(ic), (0.46, 1.5, 0.32), iq, rng, res=(4, 10, 3), round_r=0.08, taper=0.22, rough=0.04, crown=0.4,
         col_fn=sc, tile=0.7)
    # A face worn almost smooth: brow ridge, nose, and the hollow eyes.
    fc = ic + iq @ V(0, 0.48, 0.17)
    slab(g, tuple(fc), (0.3, 0.05, 0.06), iq, rng, res=(3, 1, 1), round_r=0.02, rough=0.02, col_fn=sc, tile=0.5)
    slab(g, tuple(fc + iq @ V(0, -0.11, 0.02)), (0.06, 0.15, 0.06), iq, rng, res=(1, 2, 1), round_r=0.02, rough=0.02,
         col_fn=sc, tile=0.5)
    for sx in (-1, 1):
        stone(g, tuple(fc + iq @ V(sx * 0.08, -0.05, -0.005)), (0.04, 0.03, 0.02), rng, mat=M_ROCK, detail=1, cuts=0,
              col_fn=lambda q, n: (0.05, 0.05, 0.04), tile=0.3)
    slab(g, tuple(ic + iq @ V(0, -0.3, 0.18)), (0.36, 0.06, 0.05), iq, rng, res=(3, 1, 1), round_r=0.02, rough=0.02,
         col_fn=sc, tile=0.5)
    # Altar stone + guttered candles + wax runs.
    slab(g, (0.05, 0.06, 0.25), (0.62, 0.16, 0.4), quat_y(0.1), rng, res=(4, 2, 3), round_r=0.04, rough=0.04,
         crown=0.05, col_fn=rock_col((0.6, 0.62, 0.56), moss=0.4, lichen=(0.3, 0.38, 0.2), noise=nz), tile=0.6)
    for k, (x, z, h) in enumerate(((-0.18, 0.2, 0.14), (-0.06, 0.32, 0.07), (0.08, 0.18, 0.2), (0.2, 0.3, 0.05), (0.26, 0.15, 0.1))):
        r = 0.028 + 0.008 * (k % 2)
        base = V(x, 0.13, z)
        lathe(g, base, (0, 1, 0), [(0.0, r * 1.8), (0.02, r * 1.2), (h, r), (h + 0.01, r * 0.8)], 8, M_FRUIT,
              scale(WAX, rng.uniform(0.85, 1.0)), tile=0.2)
        tube(g, [base + V(0, h, 0), base + V(0.003, h + 0.025, 0)], [0.004, 0.002], 3, M_FRUIT, (0.05, 0.04, 0.03), tile=0.1,
             cap=False)
        for d in range(2):
            a = rng.uniform(0, 6.28)
            p = base + V(math.cos(a) * r, h * rng.uniform(0.3, 0.8), math.sin(a) * r)
            tube(g, [p, p - V(0, h * 0.4, 0) + V(math.cos(a), 0, math.sin(a)) * 0.006], [0.007, 0.009], 4, M_FRUIT,
                 scale(WAX, 0.9), tile=0.1)
    # Offerings: clay bowls (one with dark dregs), a small skull, a bead string trailing off the altar.
    for (x, z, s) in ((0.45, 0.55, 1.0), (-0.42, 0.62, 0.8)):
        lathe(g, V(x, -0.01, z), (0, 1, 0), [(0.0, 0.05 * s), (0.04 * s, 0.1 * s), (0.08 * s, 0.11 * s)], 10, M_EARTH,
              (0.7, 0.45, 0.3), tile=0.3)
        ngon(g, [V(x + 0.09 * s * math.cos(a), 0.06 * s, z + 0.09 * s * math.sin(a)) for a in np.linspace(2 * math.pi, 0, 10, endpoint=False)],
               M_EARTH, (0.1, 0.06, 0.04), 0.3)
    skull(g, V(-0.3, 0.08, 0.35), (0.6, 0, 0.8), 0.32, rng, horns=False)
    beads = bez(V(0.3, 0.14, 0.35), V(0.42, 0.1, 0.4), V(0.5, 0.0, 0.25), 7)
    for p in beads:
        stone(g, tuple(p), (0.014, 0.014, 0.014), rng, mat=M_FRUIT, detail=1, cuts=0, rough=0.02,
              col_fn=lambda q, n: (0.55, 0.12, 0.08), tile=0.1)
    # Rotten rag posts leaning round it.
    for k, a in enumerate((2.1, 3.9, 5.6)):
        base = V(math.cos(a) * 1.25, -0.25, math.sin(a) * 1.15)
        top = base + V(rng.uniform(-0.15, 0.15), 1.25 + 0.2 * (k % 2), rng.uniform(-0.15, 0.15))
        beam(g, [base, top], 0.09, 0.09, up=(0, 0, 1), mat=M_BARK, mode="bark", rng=rng, jag=(0, 0.18), chamfer=0.5,
             col_fn=weathered((0.45, 0.42, 0.36), 0.5))
        p0 = base.lerp(top, 0.85)
        d = V(math.cos(a + 1.3), 0, math.sin(a + 1.3))
        grid = [[tuple(p0 + d * (0.02 + 0.03 * w) + V(0.02 * math.sin(j * 1.7 + w), -0.12 * j, 0.02 * j * w)) for j in range(5)]
                for w in (-1.0, 0.0, 1.0)]
        rag = [(0.45, 0.12, 0.08), (0.62, 0.58, 0.44), (0.3, 0.32, 0.25)][k]
        sheet(g, grid, M_CLOTH, lambda u, v, rag=rag: scale(rag, 1.0 - 0.4 * v), tile=0.3, double=True)
        lashing(g, p0, (top - base), 0.05, rng, turns=2)
    return b


# ─────────────────────────────────────────────────────────────── forest
def story_hunter(rng):
    """FOOT 2.3. A hunter's camp: lean-to at (-0.6, -0.8) opening to +Z (collider half 0.9 x 0.45),
    cold fire at (0.15, 0.55), hide-drying rack at (1.25, -0.55) (collider half 0.65 x 0.25), deer
    antlers on a stump at (1.3, 0.95)."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 2.0)
    pc = (0.85, 0.8, 0.72)
    lc = V(-0.6, 0, -0.8)
    # Lean-to: forked uprights, ridge pole, rafters to the ground behind, hides + boughs over it.
    for x in (-0.85, 0.85):
        pole(g, lc + V(x, -0.2, 0.25), lc + V(x, 1.3, 0.25), 0.045, 0.035, rng, col=pc, sides=6)
        pole(g, lc + V(x, 1.15, 0.25), lc + V(x + 0.12 * (1 if x > 0 else -1), 1.42, 0.25), 0.025, 0.018, rng, col=pc, sides=5)
    pole(g, lc + V(-1.0, 1.28, 0.25), lc + V(1.0, 1.27, 0.25), 0.04, 0.04, rng, col=pc, sides=7)
    for k in range(7):
        x = -0.8 + k * (1.6 / 6)
        pole(g, lc + V(x, 1.32, 0.3), lc + V(x + rng.uniform(-0.05, 0.05), -0.05, -0.55), 0.028, 0.03, rng, col=pc, sides=5)
    ni, nj = 6, 9
    grid = []
    for i in range(ni):
        u = i / (ni - 1)
        grid.append([tuple(lc + V(-0.92 + 1.84 * j / (nj - 1), 1.36 - 1.38 * u, 0.32 - 0.88 * u)
                           + V(0, 0.04 + 0.03 * math.sin(j * 1.9 + u * 4), 0) * (1 - abs(2 * u - 1))) for j in range(nj)])
        grid[-1] = [(p[0], max(p[1], -0.02), p[2]) for p in grid[-1]]

    def hidecol(u, v):
        patch = 0.5 + 0.5 * math.sin(v * 7.0 + u * 3.0)
        return mix((0.3, 0.22, 0.16), (0.36, 0.28, 0.2), patch)
    sheet(g, grid, M_HIDE, hidecol, tile=0.6, double=True)
    for k in range(6):
        x = rng.uniform(-0.8, 0.8)
        pole(g, lc + V(x, 1.33, 0.36), lc + V(x + rng.uniform(-0.2, 0.2), 0.05, -0.5), 0.012, 0.008, rng, mat=M_BARK,
             col=(0.4, 0.42, 0.3), sides=4)
    # Bedding inside: a fur.
    stone(g, tuple(lc + V(0, 0.03, -0.05)), (0.6, 0.04, 0.3), rng, mat=M_HIDE, detail=2, rough=0.2, cuts=0,
          col_fn=lambda q, n: (0.26, 0.2, 0.15), tile=0.4)
    # Cold fire: ash, ring stones, charred ends.
    fc = V(0.15, 0, 0.55)

    def ash(p, n):
        return mix((0.08, 0.08, 0.09), (0.38, 0.4, 0.42), 0.5 + 0.5 * nz(p * 6.0))
    mound(g, tuple(fc), 0.32, 0.32, 0.04, rng, col_fn=ash, tile=0.6, rings=4, seg=14, skirt=0.06)
    for k in range(8):
        a = 2 * math.pi * k / 8 + rng.uniform(-0.15, 0.15)
        r = rng.uniform(0.08, 0.1)
        stone(g, tuple(fc + V(math.cos(a) * 0.4, 0, math.sin(a) * 0.4)), (r, r * 0.7, r * 0.85), rng, detail=1,
              col_fn=rock_col((0.8, 0.78, 0.74), moss=0.2), tile=0.5)
    for k in range(3):
        a = k * 2.1 + 0.3
        d = V(math.cos(a), 0, math.sin(a))
        tube(g, [fc + d * -0.25 + V(0, 0.04, 0), fc + d * 0.25 + V(0, 0.05, 0)], [0.035, 0.025], 6, M_BARK, charred(rng), tile=0.5)
    # Drying rack: two A-frames + a crossbar; a hide stretched in a lashed frame leaning on it, one draped over.
    rc = V(1.25, 0, -0.55)
    for x in (-0.6, 0.6):
        for s in (-1, 1):
            pole(g, rc + V(x, -0.15, s * 0.3), rc + V(x, 1.3, -s * 0.05), 0.03, 0.025, rng, col=pc, sides=5)
    pole(g, rc + V(-0.7, 1.22, 0.0), rc + V(0.7, 1.22, 0.0), 0.03, 0.03, rng, col=pc, sides=6)
    grid = []
    for i in range(6):
        u = i / 5
        grid.append([tuple(rc + V(-0.45 + 0.9 * j / 6, 1.24 - 0.04 * math.sin(math.pi * j / 6), 0.0)
                           + V(0, -0.0, 0) + V(0, -u * 0.75, (0.12 if u < 0.5 else -0.1) * math.sin(math.pi * u)))
                     for j in range(7)])
    sheet(g, grid, M_HIDE, lambda u, v: mix((0.38, 0.28, 0.2), (0.3, 0.22, 0.16), u), tile=0.6, double=True)
    fq = quat_x(math.radians(-24))
    fo = rc + V(0.0, 0.52, 0.62)
    fr = [fo + fq @ V(sx * 0.42, sy * 0.5, 0) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    for k in range(4):
        pole(g, fr[k], fr[(k + 1) % 4], 0.022, 0.022, rng, col=pc, sides=5, segs=1)
    grid = [[tuple(fo + fq @ V(-0.36 + 0.72 * j / 4, -0.44 + 0.88 * i / 4, -0.01 + 0.015 * math.sin(math.pi * j / 4) * math.sin(math.pi * i / 4)))
             for j in range(5)] for i in range(5)]
    sheet(g, grid, M_HIDE, lambda u, v: (0.5, 0.42, 0.32), tile=0.5, double=True)
    for k in range(4):
        lashing(g, fr[k], fr[(k + 1) % 4] - fr[k], 0.03, rng, turns=2)
    # Stump with a stag's skull + antlers on it.
    sc = V(1.3, 0, 0.95)
    tube(g, [sc + V(0, -0.2, 0), sc + V(0, 0.42, 0)], [0.26, 0.22], 10, M_BARK, (0.7, 0.62, 0.52), tile=0.5)
    ngon(g, [sc + V(0.21 * math.cos(a), 0.43, 0.21 * math.sin(a)) for a in np.linspace(2 * math.pi, 0, 10, endpoint=False)],
           M_PLANK, (0.95, 0.85, 0.65), 0.6)
    skull(g, sc + V(0, 0.52, 0), (0.3, -0.2, 0.9), 0.42, rng, horns=False)
    fwd = Vector((0.3, 0.0, 0.9)).normalized()
    side = Vector((0, 1, 0)).cross(fwd).normalized()
    for sg in (-1, 1):
        root = sc + V(0, 0.6, 0) + side * sg * 0.06
        main = bez(root, root + side * sg * 0.3 + V(0, 0.25, 0) - fwd * 0.1, root + side * sg * 0.28 + V(0, 0.72, 0) + fwd * 0.12, 7)
        tube(g, main, [0.025, 0.022, 0.02, 0.017, 0.014, 0.01, 0.004], 5, M_ROCK, (0.7, 0.6, 0.45), tile=0.3)
        for t in (2, 4, 5):
            p = main[t]
            tube(g, [p, p + fwd * 0.16 + V(0, 0.08, 0) + side * sg * 0.02], [0.013, 0.003], 4, M_ROCK, (0.75, 0.65, 0.5), tile=0.2)
    return b


def story_woodcut(rng):
    """FOOT 2.4. Abandoned woodcutters' site: felled-log stack along X at (-0.5, -0.95) (collider half
    1.25 x 0.45), a sawhorse with a half-sawn log at (0.95, 0.55) (collider half 0.75 x 0.3), the
    stump with the axe at (-0.65, 0.8) (collider half 0.3 x 0.3), chips and split billets."""
    b = Builder()
    g = G(b)
    bark = (0.78, 0.72, 0.64)
    endc = (0.98, 0.86, 0.62)

    def log(p0, p1, r, rng):
        p0, p1 = Vector(p0), Vector(p1)
        tube(g, [p0, p0.lerp(p1, 0.5) + V(0, 0.005, 0), p1], [r, r * 0.97, r * 0.93], 10, M_BARK,
             scale(bark, rng.uniform(0.85, 1.0)), tile=0.6, cap=False)
        d = (p1 - p0).normalized()
        for p, sg, rr in ((p0, -1, r), (p1, 1, r * 0.93)):
            a0 = d.orthogonal().normalized()
            b0 = d.cross(a0)
            ring = [p + (a0 * math.cos(2 * math.pi * k / 10) + b0 * math.sin(2 * math.pi * k / 10)) * rr for k in range(10)]
            if sg < 0:
                ring = ring[::-1]
            ngon(g, ring, M_PLANK, scale(endc, rng.uniform(0.85, 1.0)), 0.5)
    lc = V(-0.5, 0, -0.95)
    R = 0.2
    for row, n in enumerate((3, 2, 1)):
        for k in range(n):
            z = (k - (n - 1) / 2) * 2 * R
            y = R * 0.9 + row * R * 1.72
            off = rng.uniform(-0.12, 0.12)
            log(lc + V(-1.15 + off, y, z), lc + V(1.15 + off, y + rng.uniform(-0.02, 0.02), z), R * rng.uniform(0.9, 1.05), rng)
    for x in (-0.9, 0.9):
        for sg in (-1, 1):
            beam(g, [lc + V(x, -0.25, sg * 0.66), lc + V(x, 0.62, sg * 0.6)], 0.07, 0.07, up=(1, 0, 0), mat=M_PLANK, rng=rng,
                 col_fn=weathered(WOOD, 0.6), point=0.1)
    # Sawhorse: X-legs at both ends, a top beam; a log on it, the bucksaw still in the cut.
    hc = V(0.95, 0, 0.55)
    hq = quat_y(-0.3)
    for x in (-0.55, 0.55):
        for sg in (-1, 1):
            beam(g, [hc + hq @ V(x, -0.15, sg * 0.32), hc + hq @ V(x, 0.78, -sg * 0.1)], 0.07, 0.07, up=tuple(hq @ V(1, 0, 0)),
                 mat=M_PLANK, rng=rng, col=scale(WOOD, 0.85))
    beam(g, [hc + hq @ V(-0.7, 0.6, 0), hc + hq @ V(0.7, 0.6, 0)], 0.09, 0.09, mat=M_PLANK, rng=rng, col=scale(WOOD, 0.8))
    l0, l1 = hc + hq @ V(-0.72, 0.84, 0.05), hc + hq @ V(0.72, 0.82, 0.05)
    log(l0, l1, 0.17, rng)
    cut = hc + hq @ V(0.2, 0.84, 0.05)
    blade_dir = hq @ V(0, 0, 1)
    box(g, tuple(cut + V(0, 0.08, 0)), (0.008, 0.08, 0.75), hq, M_IRON, (0.5, 0.48, 0.46), tile=0.3)
    for sg in (-1, 1):
        pole(g, cut + blade_dir * (sg * 0.4) + V(0, 0.0, 0), cut + blade_dir * (sg * 0.4) + V(0, 0.42, 0), 0.02, 0.02, rng,
             col=(0.7, 0.58, 0.42), sides=5, segs=1)
    pole(g, cut + blade_dir * -0.4 + V(0, 0.38, 0), cut + blade_dir * 0.4 + V(0, 0.38, 0), 0.016, 0.016, rng,
         col=(0.7, 0.58, 0.42), sides=5, segs=1)
    # The stump, the axe bitten into it, chips everywhere.
    sc = V(-0.65, 0, 0.8)
    tube(g, [sc + V(0, -0.2, 0), sc + V(0, 0.2, 0), sc + V(0, 0.45, 0)], [0.36, 0.3, 0.28], 12, M_BARK, bark, tile=0.6, cap=False)
    ngon(g, [sc + V(0.28 * math.cos(a), 0.45 + 0.01 * math.sin(3 * a), 0.28 * math.sin(a)) for a in np.linspace(2 * math.pi, 0, 12, endpoint=False)],
           M_PLANK, endc, 0.6)
    ah = sc + V(0.05, 0.5, 0.0)
    box(g, tuple(ah), (0.16, 0.1, 0.025), quat_y(0.6) @ quat_z(0.25), M_IRON, (0.42, 0.4, 0.38), tile=0.3)
    tube(g, [ah + V(0.02, 0.02, 0.0), ah + V(0.36, 0.42, -0.25)], [0.02, 0.018], 6, M_PLANK, (0.75, 0.6, 0.42), tile=0.3)
    for k in range(18):
        a = rng.uniform(0, 6.28)
        r = rng.uniform(0.35, 0.95)
        p = sc + V(math.cos(a) * r, 0.01, math.sin(a) * r)
        box(g, tuple(p), (rng.uniform(0.05, 0.11), 0.012, rng.uniform(0.03, 0.05)), quat_y(rng.uniform(0, 6.28)), M_PLANK,
            scale(endc, rng.uniform(0.75, 1.0)), tile=0.3)
    # A few split billets stacked by the stump.
    for k in range(5):
        p = sc + V(0.55 + (k % 3) * 0.13, 0.06 + (k // 3) * 0.11, -0.45 + rng.uniform(-0.02, 0.02))
        box(g, tuple(p), (0.1, 0.1, 0.42), quat_y(0.15) @ quat_z(0.785 + rng.uniform(-0.1, 0.1)), M_PLANK,
            scale(endc, rng.uniform(0.75, 0.9)), tile=0.5)
    return b


def bounds(builder):
    """Extents in GAME coordinates (the Builder stores Blender (x, -z, y)); radius = above-ground reach."""
    v = np.array(builder.verts) if builder.verts else np.zeros((1, 3))
    gx, gy, gz = v[:, 0], v[:, 2], -v[:, 1]
    above = gy > 0.02
    r = np.hypot(gx[above], gz[above]).max() if above.any() else 0.0
    return {"tris": builder.tris(), "radius": round(float(r), 3), "y": [round(float(gy.min()), 3), round(float(gy.max()), 3)]}


MODELS = {
    "story_caravan": story_caravan,
    "story_ribs": story_ribs,
    "story_oasis": story_oasis,
    "story_boat": story_boat,
    "story_shrine": story_shrine,
    "story_hunter": story_hunter,
    "story_woodcut": story_woodcut,
}

clear_scene()
objs = []
report = {}
for i, (name, fn) in enumerate(MODELS.items()):
    bld = fn(np.random.default_rng(4100 + i))
    report[name] = bounds(bld)
    objs.append(bld.build(name, MATS))
export_glb(OUT / "stories_warm.glb", objs)
(OUT / "stories_warm_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
for k, v in report.items():
    print(f"{k}: {v}")
print("STORIES_WARM_DONE")
