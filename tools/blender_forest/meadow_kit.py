"""The working meadow under the castle walls (living-island spec 2026-10-13 §2 D) -> meadow_kit.glb.

Common Pasture & Sheepfold (`src/pasture.rs`): a wattle-hurdle fold with a hurdle gate, a hewn
log water trough, and the SHEEP themselves — sculpted signed-distance parts (sdfkit, the
animals.py bake: region / cavity / coat tone / tint in the vertex colour, a fur-flow UV0) so the
fleece reads as lumpy, dirty, lanolin-yellowed wool on a creature-material coat:
  sheep_body (fleece barrel, ground-origin frame), sheep_head (pivot at the neck root),
  sheep_leg / sheep_hind (LEFT legs, pivot at the hip; the game mirrors the right ones).
Militia Butts (`src/drill_yard.rs`): an earth butt with a straw target, a hacked pell post, a
spear rack, a split-log bench. South Watch Beacon (`src/watch_beacon.rs`): an earth mound with a
lashed tripod, an iron fire basket stacked with pitch billets, a leaning ladder and a pitch keg.

Game coordinates (Y up, +Z forward), base at y=0 with ground-contact parts sunk ~0.1-0.25u so a
piece on uneven grass never floats. 1u ~ 1.35 m (hero ~1.3u). Materials by name (the s_* sets).

    blender -b --factory-startup --python tools/blender_forest/meadow_kit.py
"""
import json
import math
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402
from common import OUT, clear_scene, export_glb  # noqa: E402
from geo import G, frustum, quat_x, quat_y, quat_z  # noqa: E402
from meshkit import Builder  # noqa: E402
from wayside_models import (  # noqa: E402
    M_BARK, M_CLOTH, M_EARTH, M_IRON, M_PLANK, M_ROCK, M_THATCH, M_TIMBER, MATS as WAYSIDE_MATS, Noise, V,
    beam, bounds, lashing, lbox, mound, pole, rock_col, scale, slab, smooth_mesh, stone, tube, wattle, weathered,
)
import animals  # noqa: E402  (importable: the sdf bake for the sheep)
from sdfkit import Cone, Ellipsoid, Sphere, Tufts, smoothstep as np_smooth, v3  # noqa: E402

M_WATER = len(WAYSIDE_MATS)
M_MOSSROCK = M_WATER + 1
MATS = WAYSIDE_MATS + ["bogwater", "s_mossrock"]

GREY_WOOD = (0.86, 0.8, 0.7)
HAZEL = (0.92, 0.84, 0.68)


# ─────────────────────────────────────────────────────────────── pasture
def mk_fold(rng):
    """A wattle sheepfold, 7 x 5 (x -3.5..3.5, z -2.5..2.5), hurdles ~0.72 high, the gate gap on
    the -X side (z -0.75..0.75) with the hurdle gate swung open outward. Straw trodden inside."""
    b = Builder()
    g = G(b)
    hx, hz, gap = 3.5, 2.5, 0.75
    posts = [(-hx, -hz), (hx, -hz), (hx, hz), (-hx, hz), (-hx, -gap), (-hx, gap), (0.0, -hz), (0.0, hz), (hx, 0.0)]
    for x, z in posts:
        pole(g, V(x, -0.28, z), V(x + rng.uniform(-0.02, 0.02), 0.86 + rng.uniform(0, 0.06), z), 0.055, 0.045, rng,
             col=(0.82, 0.76, 0.66), sides=7, col_fn=weathered((0.85, 0.78, 0.68), damp=0.55))
    runs = [((-hx + 0.06, -hz), (-0.06, -hz)), ((0.06, -hz), (hx - 0.06, -hz)),
            ((-hx + 0.06, hz), (-0.06, hz)), ((0.06, hz), (hx - 0.06, hz)),
            ((hx, -hz + 0.06), (hx, -0.06)), ((hx, 0.06), (hx, hz - 0.06)),
            ((-hx, -hz + 0.06), (-hx, -gap - 0.06)), ((-hx, gap + 0.06), (-hx, hz - 0.06))]
    for a, c in runs:
        wattle(g, V(a[0], 0.0, a[1]), V(c[0], 0.0, c[1]), rng, h=0.7, stake_gap=0.26)
    # Hurdle gate: a framed panel hung on the north gap post, swung ~70 deg outward (-X).
    hinge = V(-hx, 0.0, gap)
    q = quat_y(-1.2)
    p0, p1 = hinge + q @ V(0, 0, -0.06), hinge + q @ V(0, 0, -1.4)
    wattle(g, p0 + V(0, 0.05, 0), p1 + V(0, 0.05, 0), rng, h=0.62, stake_gap=0.3)
    for y in (0.12, 0.64):
        beam(g, [p0 + V(0, y, 0), p1 + V(0, y, 0)], 0.05, 0.05, mat=M_TIMBER, rng=rng, col=GREY_WOOD)
    # Rope loop hasp on the far gate post.
    lashing(g, V(-hx, 0.62, -gap), (0, 1, 0), 0.06, rng, turns=2)
    # Trodden straw bedding inside: low tufted pads (thatch) scattered over the ground.
    for _ in range(26):
        x, z = rng.uniform(-hx + 0.4, hx - 0.4), rng.uniform(-hz + 0.35, hz - 0.35)
        r = rng.uniform(0.25, 0.55)
        frustum(g, r, r * 0.7, -0.04, rng.uniform(0.05, 0.09), 9, M_THATCH,
                scale((0.95, 0.86, 0.66), rng.uniform(0.62, 0.9)), tile=0.5, centre=(x, 0, z), jitter=0.25, rng=rng,
                cap_top=True)
    # A hay manger against the east hurdle: slatted V rack on two legs, hay heaped in it.
    mc = V(hx - 0.42, 0.0, 1.2)
    for dz in (-0.55, 0.55):
        pole(g, mc + V(0.12, -0.15, dz), mc + V(0.12, 0.75, dz), 0.035, 0.03, rng, col=GREY_WOOD, sides=6)
        pole(g, mc + V(-0.2, -0.15, dz), mc + V(-0.05, 0.75, dz), 0.035, 0.03, rng, col=GREY_WOOD, sides=6)
    for k in range(7):
        t = k / 6
        a = mc + V(-0.2 + 0.15 * t, 0.3 + 0.45 * t, -0.6)
        c = mc + V(-0.2 + 0.15 * t, 0.3 + 0.45 * t, 0.6)
        pole(g, a, c, 0.016, 0.016, rng, col=HAZEL, sides=5, segs=1)
    frustum(g, 0.3, 0.2, 0.42, 0.34, 12, M_THATCH, (0.98, 0.9, 0.7), tile=0.6, centre=(mc.x - 0.02, 0, mc.z),
            jitter=0.15, rng=rng, cap_top=True)
    return b


def mk_trough(rng):
    """A hewn half-log water trough (~1.9 long along X) on two stone chocks, water standing in it."""
    b = Builder()
    g = G(b)
    L, R = 0.95, 0.27
    sides = 14
    # Outer half-cylinder shell + inner hollow, as one lofted tube along X with an open top.
    for x in (-L, L):
        stone(g, (x * 0.72, 0.05, 0.0), (0.2, 0.14, 0.24), rng, col_fn=rock_col((0.9, 0.88, 0.84), moss=0.4, ground=0.0))
    bark = (0.75, 0.66, 0.56)
    ring_out = []
    ring_in = []
    for s in range(sides + 1):
        a = math.pi + math.pi * s / sides
        ring_out.append((math.cos(a) * R, math.sin(a) * R * 0.9))
        ring_in.append((math.cos(a) * (R - 0.055), math.sin(a) * (R - 0.06) * 0.9))
    yb = 0.2 + R * 0.9
    for xs in range(8):
        x0, x1 = -L + 2 * L * xs / 8, -L + 2 * L * (xs + 1) / 8
        for s in range(sides):
            for ring, flip, mat, col in ((ring_out, False, M_BARK, bark), (ring_in, True, M_TIMBER, (0.7, 0.62, 0.5))):
                (u0, v0), (u1, v1) = ring[s], ring[s + 1]
                q = [V(x0, yb + v0, u0), V(x0, yb + v1, u1), V(x1, yb + v1, u1), V(x1, yb + v0, u0)]
                n0 = V(0, v0, u0).normalized()
                n1 = V(0, v1, u1).normalized()
                ns = [n0, n1, n1, n0]
                if flip:
                    q = q[::-1]
                    ns = [-n for n in ns[::-1]]
                uv = [(x0 / 0.6, s / sides * 1.2), (x0 / 0.6, (s + 1) / sides * 1.2), (x1 / 0.6, (s + 1) / sides * 1.2),
                      (x1 / 0.6, s / sides * 1.2)]
                g.poly(q, uv, ns, [col] * 4, mat)
    # Rim (cut faces) + end walls.
    for z0, z1 in ((-R, -(R - 0.055)), (R - 0.055, R)):
        g.flat([V(-L, yb, z0), V(L, yb, z0), V(L, yb, z1), V(-L, yb, z1)][::(1 if z0 < 0 else 1)], M_TIMBER,
               (0.8, 0.72, 0.6), 0.5)
    for x in (-L, L):
        pts = [V(x, yb + v, u) for u, v in ring_out]
        if x > 0:
            pts = pts[::-1]
        fan(g, pts, M_TIMBER, (0.72, 0.62, 0.5), 0.5)
    # Water surface, a little below the rim.
    wy = yb - 0.07
    wr = R - 0.07
    g.flat([V(-L + 0.05, wy, -wr), V(-L + 0.05, wy, wr), V(L - 0.05, wy, wr), V(L - 0.05, wy, -wr)], M_WATER,
           (0.16, 0.2, 0.2), 1.0)
    # Mud slop + a few splashed stones at the drinking side.
    for _ in range(5):
        stone(g, (rng.uniform(-1.0, 1.0), -0.02, rng.uniform(0.35, 0.6)), (0.06, 0.04, 0.07), rng,
              col_fn=rock_col((0.7, 0.66, 0.6)))
    return b


# ─────────────────────────────────────────────────────────────── the sheep (sdf, creature coat)
# Region order = pasture.rs palette: WOOL (coat ramp), FACE/SKIN, HOOF, EYE.
WOOL, SKIN, HOOF, EYE = range(4)
S_BODY_Y = 0.43
HIP_F = (0.095, 0.33, 0.21)
HIP_H = (0.095, 0.33, -0.25)
NECK = (0.0, 0.5, 0.3)


def sheep_parts():
    P = lambda x, y, z: v3((x, y, z))  # noqa: E731
    fleece_big = Tufts(38.0, (0, -1, 0), seed=11, n=12, stretch=0.4)
    fleece_fine = Tufts(105.0, (0, -1, 0), seed=12, n=12, stretch=0.3)
    # Body: a woolly barrel, deeper at the chest, rounded rump, a short docked tail.
    body = animals.Body(h=0.0075, budget=5200)
    body.add(Ellipsoid(P(0, S_BODY_Y, -0.02), (0.185, 0.175, 0.34)), WOOL)
    body.add(Ellipsoid(P(0, S_BODY_Y + 0.01, 0.17), (0.175, 0.18, 0.17)), WOOL, k=0.08)
    body.add(Ellipsoid(P(0, S_BODY_Y + 0.02, -0.24), (0.175, 0.165, 0.15)), WOOL, k=0.08)
    body.add(Ellipsoid(P(0, S_BODY_Y - 0.01, -0.39), (0.06, 0.07, 0.05)), WOOL, k=0.04)  # docked tail
    body.add(Ellipsoid(P(0, S_BODY_Y + 0.05, 0.29), (0.11, 0.11, 0.09)), WOOL, k=0.06)  # neck wool root
    # Fleece: big lumpy staples + fine crimp everywhere but the belly midline.
    shag_mask = Ellipsoid(P(0, S_BODY_Y + 0.06, -0.02), (0.3, 0.26, 0.5))
    body.shag(shag_mask, 0.032, fleece_big, soft=0.06)
    body.shag(shag_mask, 0.01, fleece_fine, soft=0.06)
    # Head: neck from the pivot up/forward, a long narrow skull, roman-nosed muzzle, sideways ears,
    # a wool cap on the poll.
    head = animals.Body(h=0.004, budget=2600)
    nk = v3(NECK)
    skull = nk + P(0, 0.12, 0.2)
    head.add(Cone(nk + P(0, -0.02, -0.03), skull + P(0, -0.02, -0.07), 0.085, 0.06), WOOL)
    head.add(Ellipsoid(skull, (0.058, 0.07, 0.085)), SKIN, k=0.04)
    head.add(Cone(skull + P(0, -0.005, 0.04), skull + P(0, -0.045, 0.16), 0.05, 0.034), SKIN, k=0.03)
    head.add(Ellipsoid(skull + P(0, -0.05, 0.165), (0.033, 0.026, 0.03)), SKIN, k=0.015)
    for sx in (-1, 1):
        ear = skull + P(sx * 0.06, 0.035, -0.035)
        head.add(Ellipsoid(ear + P(sx * 0.045, -0.01, 0.0), (0.05, 0.012, 0.024), rot=None), SKIN, k=0.01)
        head.add(Sphere(skull + P(sx * 0.047, 0.018, 0.035), 0.011), EYE)
    head.add(Ellipsoid(skull + P(0, 0.05, -0.04), (0.06, 0.04, 0.06)), WOOL, k=0.02)
    head.shag(Ellipsoid(nk + P(0, 0.02, 0.04), (0.11, 0.12, 0.15)), 0.02, fleece_big, soft=0.04)
    # Legs (left, +X): thin, knobbly at the knee / hock, dark cloven hoof; the top hides in the fleece.
    def leg(hip, front):
        lb = animals.Body(h=0.0035, budget=900)
        h = v3(hip)
        knee = h + P(0.0, -0.17, 0.012 if front else -0.03)
        foot = P(h[0], 0.03, h[2] + (0.01 if front else 0.0))
        lb.add(Cone(h + P(0, 0.06, 0), knee, 0.05, 0.03), WOOL)
        lb.add(Cone(knee, foot, 0.022, 0.018), SKIN, k=0.012)
        lb.add(Sphere(knee, 0.026), SKIN, k=0.01)
        lb.add(Cone(foot + P(0, 0.0, 0.005), foot + P(0, -0.03, 0.02), 0.022, 0.026), HOOF, k=0.006)
        return lb
    return {"body": body, "head": head, "leg": leg(HIP_F, True), "hind": leg(HIP_H, False)}


def sheep_coat(ps, n, joint):
    """Tone: cream fleece, sun-bleached on the back, dirtier toward the belly / breech; tint:
    lanolin-yellow + mud on the lower legs and rump."""
    y = ps[:, 1]
    tone = 0.62 + 0.25 * np.clip(n[:, 1], -1, 1) - 0.25 * np_smooth(S_BODY_Y, S_BODY_Y - 0.2, y)
    tint = 0.35 * np_smooth(S_BODY_Y + 0.05, S_BODY_Y - 0.18, y) + 0.25 * np_smooth(-0.1, -0.4, ps[:, 2])
    return np.clip(tone, 0, 1), np.clip(tint, 0, 0.85)


def build_sheep():
    parts = sheep_parts()
    frames = {"body": (np.eye(3), v3((0, 0, 0))), "head": (np.eye(3), v3(NECK)),
              "leg": (np.eye(3), v3(HIP_F)), "hind": (np.eye(3), v3(HIP_H))}
    axes = {"body": [(0, S_BODY_Y, 0.4), (0, S_BODY_Y, -0.45)], "head": [(0, 0.66, 0.68), v3(NECK)],
            "leg": [HIP_F, (HIP_F[0], 0.0, HIP_F[2])], "hind": [HIP_H, (HIP_H[0], 0.0, HIP_H[2])]}

    def whole(q):
        d = np.full(len(q), 1e9)
        for k, bd in parts.items():
            d = np.minimum(d, bd.eval(q))
            if k in ("leg", "hind"):
                d = np.minimum(d, bd.eval(q * np.array([-1.0, 1.0, 1.0])))
        return d

    objs = []
    for k, bd in parts.items():
        part = animals.Part("head" if k == "head" else ("spine" if k == "body" else "leg_upper"), [bd], axes[k])
        part.uv_scale *= 2.6  # dense crimp
        nb = [parts["body"].eval] if k != "body" else []
        ob = animals.build_object(f"sheep_{k}", part, frames[k], whole, sheep_coat, nb)
        print(f"  sheep_{k}: {len(ob.data.polygons)} faces")
        objs.append(ob)
    return objs


# ─────────────────────────────────────────────────────────────── militia butts
def mk_butt(rng):
    """An earth archery butt: a turfed bank ~2.6 wide (X), 1.5 high, facing +Z, a straw boss on a
    stake leaning against its face, spent arrows in the bank and the boss."""
    b = Builder()
    g = G(b)
    turf = lambda p, n: (0.42, 0.46, 0.3) if n.y > 0.55 else (0.62, 0.52, 0.42)  # noqa: E731
    mound(g, (0, 0.0, -0.2), 1.45, 0.75, 1.25, rng, col_fn=turf, rings=8, seg=26, rough=0.08, edge=0.08, power=0.55)
    # Turf sods stacked along the crest.
    for k in range(6):
        x = -1.0 + k * 0.4 + rng.uniform(-0.05, 0.05)
        slab(g, (x, 1.13 + rng.uniform(-0.04, 0.02), -0.2 + rng.uniform(-0.08, 0.08)), (0.42, 0.16, 0.34),
             quat_y(rng.uniform(-0.2, 0.2)), rng, mat=M_EARTH, res=(3, 2, 3), round_r=0.05,
             col_fn=lambda p, n: (0.44, 0.5, 0.3) if n.y > 0.4 else (0.55, 0.47, 0.38), tile=0.6)
    # The straw boss: a thick coiled disc, painted rings, leaning back on a stake.
    c = V(0.0, 0.78, 0.42)
    lean = quat_x(-0.28)
    rings_col = [(0.95, 0.92, 0.82), (0.25, 0.22, 0.2), (0.95, 0.92, 0.82), (0.7, 0.18, 0.12)]
    R = 0.5
    for k in range(4):
        r1 = R * (1 - k / 4)
        r0 = R * (1 - (k + 1) / 4)
        pts_o = [c + lean @ V(math.cos(a) * r1, math.sin(a) * r1, 0.13) for a in np.linspace(0, 2 * math.pi, 25)]
        pts_i = [c + lean @ V(math.cos(a) * r0, math.sin(a) * r0, 0.13 + 0.01 * k) for a in np.linspace(0, 2 * math.pi, 25)]
        nrm = lean @ V(0, 0, 1)
        for s in range(24):
            q = [pts_i[s], pts_o[s], pts_o[s + 1], pts_i[s + 1]]
            if (q[1] - q[0]).cross(q[3] - q[0]).dot(nrm) < 0:
                q = q[::-1]
            uv = [((p - c).x / 0.6, (p - c).y / 0.6) for p in q]
            g.poly(q, uv, [nrm] * 4, [rings_col[k]] * 4, M_THATCH)
    # Coiled straw rim + back.
    rim = [c + lean @ V(math.cos(a) * R, math.sin(a) * R, 0.05) for a in np.linspace(0, 2 * math.pi, 29)]
    tube(g, rim, [0.085] * len(rim), 9, M_THATCH, (0.92, 0.84, 0.62), tile=0.4, cap=False)
    back = [c + lean @ V(math.cos(a) * R * 0.95, math.sin(a) * R * 0.95, -0.02) for a in np.linspace(0, 2 * math.pi, 25)]
    for s in range(24):
        g.flat([c + lean @ V(0, 0, -0.03), back[s + 1], back[s]], M_THATCH, (0.8, 0.72, 0.55), 0.6)
    pole(g, V(0.0, -0.2, 0.22), c + lean @ V(0, 0.2, -0.05), 0.035, 0.03, rng, col=GREY_WOOD, sides=6)
    # Arrows: in the boss and stuck in the bank (missed shots), shaft + fletching.
    def arrow(tip, d):
        d = Vector(d).normalized()
        tail = tip - d * 0.62
        pole(g, tip, tail, 0.008, 0.008, rng, col=(0.9, 0.82, 0.66), sides=4, segs=1)
        for k in range(3):
            a = 2 * math.pi * k / 3
            side = d.orthogonal().normalized()
            side = quat_from_axis(d, a) @ side
            g.flat([tail + d * 0.02, tail + d * 0.14, tail + d * 0.12 + side * 0.035, tail + d * 0.02 + side * 0.03],
                   M_CLOTH, (0.85, 0.82, 0.78), 0.2)
    for _ in range(5):
        a, r = rng.uniform(0, 2 * math.pi), rng.uniform(0.0, 0.42)
        tip = c + lean @ V(math.cos(a) * r, math.sin(a) * r, 0.05)
        arrow(tip, lean @ V(rng.uniform(-0.08, 0.08), rng.uniform(-0.05, 0.12), -1))
    for _ in range(4):
        x = rng.uniform(-1.2, 1.2)
        arrow(V(x, rng.uniform(0.25, 0.9), 0.15), (rng.uniform(-0.1, 0.1), rng.uniform(0.0, 0.25), -1))
    return b


def fan(g, pts, mat, col, tile):
    """An n-gon as a triangle fan round its centroid (the glTF tangent pass rejects n-gons)."""
    c = sum(pts, Vector((0, 0, 0))) / len(pts)
    for k in range(len(pts)):
        g.flat([pts[k], pts[(k + 1) % len(pts)], c], mat, col, tile)


def quat_from_axis(axis, ang):
    from mathutils import Quaternion
    return Quaternion(Vector(axis).normalized(), ang)


def mk_pell(rng):
    """A pell: a stout post sunk in a stone-packed foot, hacked and splintered at sword height."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 3.0)
    pts = [V(0, -0.3, 0), V(0.0, 0.5, 0), V(0.01, 1.0, 0.0), V(0.0, 1.55, 0.01)]
    beam(g, pts, 0.2, 0.2, mat=M_TIMBER, chamfer=0.22, rng=rng, rough=0.06, jag=(0.0, 0.05),
         col_fn=lambda t: scale((0.82, 0.74, 0.62), 0.55 + 0.45 * smoothstep_f(0.0, 0.3, t)))
    # Hack marks: pale fresh notches round the striking band.
    for _ in range(14):
        y = rng.uniform(0.75, 1.3)
        a = rng.uniform(0, 2 * math.pi)
        d = V(math.cos(a), 0, math.sin(a))
        c = V(0, y, 0) + d * 0.1
        t = V(-d.z, rng.uniform(-0.3, 0.3), d.x).normalized()
        g.flat([c - t * 0.05, c + t * 0.05, c + t * 0.04 + d * 0.012 + V(0, -0.02, 0)], M_TIMBER, (1.05, 0.95, 0.78), 0.3)
    # Straw rope band (the "body") and the packed foot stones.
    for y in (0.95, 1.08):
        ring = [V(math.cos(a) * 0.128, y + 0.01 * math.sin(3 * a), math.sin(a) * 0.128) for a in np.linspace(0, 2 * math.pi, 13)]
        tube(g, ring, [0.03] * len(ring), 6, M_THATCH, (0.9, 0.8, 0.58), tile=0.3, cap=False)
    for k in range(6):
        a = k / 6 * 2 * math.pi + rng.uniform(-0.3, 0.3)
        stone(g, (math.cos(a) * 0.22, 0.0, math.sin(a) * 0.22), (0.11, 0.07, 0.1), rng,
              col_fn=rock_col((0.85, 0.83, 0.78), moss=0.3, noise=nz))
    # Splinter chips in the grass.
    for _ in range(10):
        a, r = rng.uniform(0, 2 * math.pi), rng.uniform(0.25, 0.7)
        p = V(math.cos(a) * r, 0.01, math.sin(a) * r)
        q = quat_y(rng.uniform(0, 6.3))
        lbox(g, p, (0.07, 0.012, 0.025), q, M_TIMBER, (1.0, 0.9, 0.74), tile=0.3)
    return b


def smoothstep_f(a, b_, x):
    t = min(max((x - a) / (b_ - a), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def mk_rack(rng):
    """A weapon rack: two forked uprights + a notched rail, practice spears and staves leaning in it,
    a wooden waster and a battered buckler hung off the end."""
    b = Builder()
    g = G(b)
    for x in (-0.85, 0.85):
        pole(g, V(x, -0.25, 0), V(x, 1.15, 0), 0.05, 0.042, rng, col=GREY_WOOD, col_fn=weathered((0.86, 0.8, 0.7)))
        pole(g, V(x, 1.15, 0), V(x + 0.08, 1.32, 0), 0.03, 0.02, rng, col=GREY_WOOD, sides=5, segs=1)
        pole(g, V(x, 1.15, 0), V(x - 0.08, 1.3, 0), 0.03, 0.02, rng, col=GREY_WOOD, sides=5, segs=1)
    beam(g, [V(-1.0, 1.16, 0), V(1.0, 1.16, 0)], 0.07, 0.06, mat=M_TIMBER, rng=rng, col=GREY_WOOD)
    beam(g, [V(-0.9, 0.18, 0.18), V(0.9, 0.18, 0.18)], 0.06, 0.05, mat=M_TIMBER, rng=rng, col=(0.7, 0.64, 0.55))
    for k in range(6):
        x = -0.68 + k * 0.27 + rng.uniform(-0.03, 0.03)
        foot = V(x, 0.02, 0.24)
        top = V(x + rng.uniform(-0.05, 0.05), 1.95 + rng.uniform(-0.1, 0.1), -0.12)
        spear = k % 3 != 2
        pole(g, foot, top, 0.018, 0.016, rng, col=(0.88, 0.78, 0.6), sides=6, segs=2)
        if spear:
            d = (top - foot).normalized()
            tip = top + d * 0.22
            side = d.cross(V(0, 0, 1)).normalized() * 0.03
            for s in (1, -1):
                g.flat([top, tip, top + side * s + d * 0.05], M_IRON, (0.55, 0.52, 0.5), 0.3)
                g.flat([top + side * s + d * 0.05, tip, top][::1 if s < 0 else -1], M_IRON, (0.5, 0.48, 0.46), 0.3)
            lashing(g, top - d * 0.02, d, 0.022, rng, turns=2)
    # Wooden waster (practice sword) hung by its grip.
    wa = V(0.98, 1.12, 0.06)
    beam(g, [wa, wa + V(0.0, -0.8, 0.02)], 0.05, 0.022, mat=M_TIMBER, rng=rng, col=(0.95, 0.85, 0.66), point=0.06)
    beam(g, [wa + V(-0.09, -0.12, 0.02), wa + V(0.09, -0.12, 0.02)], 0.03, 0.03, mat=M_TIMBER, rng=rng,
         col=(0.7, 0.6, 0.48))
    # Buckler leaning at the foot.
    bc = V(-1.05, 0.26, 0.12)
    q = quat_x(-0.35) @ quat_y(0.4)
    frustum_disc(g, bc, q, 0.25, 0.03, M_PLANK, (0.8, 0.7, 0.58))
    frustum_disc(g, bc + q @ V(0, 0, 0.035), q, 0.07, 0.03, M_IRON, (0.5, 0.48, 0.45))
    return b


def frustum_disc(g, c, q, r, t, mat, col, sides=16):
    n = q @ V(0, 0, 1)
    ring_f = [c + q @ V(math.cos(a) * r, math.sin(a) * r, t) for a in np.linspace(0, 2 * math.pi, sides + 1)]
    ring_b = [c + q @ V(math.cos(a) * r, math.sin(a) * r, 0) for a in np.linspace(0, 2 * math.pi, sides + 1)]
    cf = c + q @ V(0, 0, t * 1.4)
    for s in range(sides):
        tri = [ring_f[s], ring_f[s + 1], cf]
        if (tri[1] - tri[0]).cross(tri[2] - tri[0]).dot(n) < 0:
            tri = tri[::-1]
        g.flat(tri, mat, col, 0.5)
        quad = [ring_b[s], ring_b[s + 1], ring_f[s + 1], ring_f[s]]
        out = (ring_b[s] + ring_b[s + 1]) / 2 - c
        if (quad[1] - quad[0]).cross(quad[3] - quad[0]).dot(out) < 0:
            quad = quad[::-1]
        g.flat(quad, mat, scale(col, 0.8), 0.5)


def mk_bench(rng):
    """A split-log bench (~1.7 long along X) on two sawn stumps sunk in the grass."""
    b = Builder()
    g = G(b)
    for x in (-0.62, 0.62):
        pole(g, V(x, -0.2, 0), V(x, 0.36, 0), 0.15, 0.14, rng, mat=M_BARK, col=(0.8, 0.72, 0.62), sides=9, segs=2)
    # Half-log seat: flat top, round underside.
    L, R = 0.88, 0.16
    pts = []
    for s in range(9):
        a = math.pi + math.pi * s / 8
        pts.append((math.cos(a) * R, math.sin(a) * R * 0.75))
    y0 = 0.36 + R * 0.75
    for s in range(8):
        (u0, v0), (u1, v1) = pts[s], pts[s + 1]
        q = [V(-L, y0 + v0, u0), V(L, y0 + v0, u0), V(L, y0 + v1, u1), V(-L, y0 + v1, u1)]
        n0 = V(0, v0, u0).normalized()
        n1 = V(0, v1, u1).normalized()
        if (q[1] - q[0]).cross(q[3] - q[0]).dot(n0 + n1) < 0:
            q = q[::-1]
            ns = [n1, n1, n0, n0]
        else:
            ns = [n0, n0, n1, n1]
        g.poly(q, [(0, s / 8), (2 * L / 0.6, s / 8), (2 * L / 0.6, (s + 1) / 8), (0, (s + 1) / 8)], ns,
               [(0.78, 0.7, 0.6)] * 4, M_BARK)
    g.flat([V(-L, y0, -R), V(-L, y0, R), V(L, y0, R), V(L, y0, -R)], M_TIMBER, (0.95, 0.86, 0.72), 0.5)
    for x in (-L, L):
        cap = [V(x, y0 + v, u) for u, v in pts]
        fan(g, cap if x < 0 else cap[::-1], M_TIMBER, (0.8, 0.7, 0.56), 0.4)
    return b


# ─────────────────────────────────────────────────────────────── watch beacon
BASKET_Y = 3.15


def mk_beacon(rng):
    """South Watch Beacon: earth mound (r ~1.9, 0.75 high) with a stone kerb, a three-pole tripod
    lashed at the head, an iron fire basket (top at ~3.6) stacked with pitch billets, a ladder
    leaning on the south leg, a pitch keg at the foot. The fire itself is the game's flame card at
    (0, BASKET_Y + 0.35, 0)."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 2.2)
    turf = lambda p, n: (0.45, 0.48, 0.32) if n.y > 0.6 else (0.6, 0.52, 0.42)  # noqa: E731
    mound(g, (0, 0.0, 0), 1.95, 1.85, 0.75, rng, col_fn=turf, rings=8, seg=28, rough=0.06, power=0.7)
    for k in range(13):
        a = k / 13 * 2 * math.pi + rng.uniform(-0.1, 0.1)
        stone(g, (math.cos(a) * 1.85, 0.02, math.sin(a) * 1.75), (0.2, 0.12, 0.16), rng,
              col_fn=rock_col((0.85, 0.83, 0.78), moss=0.5, noise=nz))
    top = V(0, 3.3, 0)
    feet = [V(math.cos(a) * 1.05, 0.45, math.sin(a) * 1.05) for a in (0.3, 0.3 + 2.094, 0.3 + 4.189)]
    for f in feet:
        tip = top + (top - f).normalized() * 0.35
        pole(g, f + (f - top).normalized() * 0.4, tip, 0.075, 0.055, rng, col=(0.8, 0.72, 0.62),
             col_fn=weathered((0.8, 0.72, 0.62), damp=0.6))
    for k in range(3):
        lashing(g, top + V(0, -0.05 - 0.04 * k, 0), (0, 1, 0), 0.1, rng, turns=2)
    # Iron basket: ring hoops + vertical straps, flaring up, sat on the tripod head.
    by = BASKET_Y
    for y, r in ((by - 0.05, 0.22), (by + 0.2, 0.34), (by + 0.45, 0.42)):
        ring = [V(math.cos(a) * r, y, math.sin(a) * r) for a in np.linspace(0, 2 * math.pi, 17)]
        tube(g, ring, [0.018] * len(ring), 5, M_IRON, (0.38, 0.33, 0.3), tile=0.3, cap=False)
    for k in range(8):
        a = k / 8 * 2 * math.pi
        pts = [V(math.cos(a) * 0.2, by - 0.12, math.sin(a) * 0.2), V(math.cos(a) * 0.34, by + 0.2, math.sin(a) * 0.34),
               V(math.cos(a) * 0.45, by + 0.52, math.sin(a) * 0.45)]
        tube(g, pts, [0.016] * 3, 4, M_IRON, (0.36, 0.3, 0.27), tile=0.3)
    # Pitch billets stacked crosswise inside (charred, tarry).
    for layer in range(3):
        y = by + 0.04 + layer * 0.12
        for k in range(4):
            off = -0.2 + k * 0.13
            a0 = (layer % 2) * math.pi / 2
            d = V(math.cos(a0), 0, math.sin(a0))
            s = V(-d.z, 0, d.x)
            r = 0.22 + layer * 0.06
            pole(g, s * off + d * -r + V(0, y, 0), s * off + d * r + V(0, y, 0), 0.04, 0.04, rng, mat=M_BARK,
                 col=(0.3, 0.25, 0.2), sides=6, segs=1)
    # Ladder leaning on the south leg.
    l0, l1 = V(0.1, 0.25, 1.75), V(0.05, 3.0, 0.42)
    d = (l1 - l0).normalized()
    s = d.cross(V(1, 0, 0)).normalized()
    side = V(1, 0, 0)
    for sx in (-0.2, 0.2):
        pole(g, l0 + side * sx, l1 + side * sx, 0.03, 0.026, rng, col=(0.85, 0.78, 0.66), sides=6)
    n_r = 9
    for k in range(n_r):
        p = l0.lerp(l1, (k + 0.6) / (n_r + 0.4))
        pole(g, p - side * 0.21, p + side * 0.21, 0.018, 0.018, rng, col=(0.9, 0.82, 0.68), sides=5, segs=1)
    # Pitch keg + a spare torch bundle at the foot.
    kc = (1.1, 0.0, 1.35)
    frustum(g, 0.2, 0.2, -0.05, 0.48, 12, M_PLANK, (0.55, 0.45, 0.36), tile=0.6, centre=kc, segs=2)
    for y in (0.06, 0.38):
        ring = [V(kc[0] + math.cos(a) * 0.215, y, kc[2] + math.sin(a) * 0.215) for a in np.linspace(0, 2 * math.pi, 15)]
        tube(g, ring, [0.012] * len(ring), 4, M_IRON, (0.3, 0.28, 0.26), tile=0.3, cap=False)
    fan(g, [V(kc[0] + math.cos(a) * 0.19, 0.44, kc[2] + math.sin(a) * 0.19) for a in np.linspace(2 * math.pi, 0, 13)[:-1]],
        M_WATER, (0.03, 0.025, 0.02), 0.5)
    for k in range(4):
        a = rng.uniform(-0.3, 0.3)
        p0 = V(-1.15 + k * 0.05, 0.0, 1.3)
        p1 = p0 + V(0.2 + a * 0.2, 0.75, -0.3)
        pole(g, p0, p1, 0.022, 0.03, rng, col=(0.75, 0.66, 0.5), sides=6, segs=1)
        tube(g, [p1 - (p1 - p0).normalized() * 0.12, p1 + (p1 - p0).normalized() * 0.02], [0.04, 0.04], 6, M_CLOTH,
             (0.2, 0.17, 0.14), tile=0.3)
    return b


MODELS = {
    "meadow_fold": mk_fold,
    "meadow_trough": mk_trough,
    "drill_butt": mk_butt,
    "drill_pell": mk_pell,
    "drill_rack": mk_rack,
    "drill_bench": mk_bench,
    "beacon_tripod": mk_beacon,
}


if __name__ == "__main__":
    clear_scene()
    objs = []
    report = {}
    only = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    for i, (name, fn) in enumerate(MODELS.items()):
        if only and name not in only:
            continue
        bld = fn(np.random.default_rng(4100 + i))
        report[name] = bounds(bld)
        objs.append(bld.build(name, MATS))
    if not only or "sheep" in only:
        objs += build_sheep()
    export_glb(OUT / "meadow_kit.glb", objs)
    for k, v in report.items():
        print(f"{k}: {v}")
    print("MEADOW_KIT_DONE")
