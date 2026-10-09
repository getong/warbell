"""Realistic quadrupeds for the shared quadruped rig (quadruped.rs) -> animals.glb.

One mesh per joint (spine, neck, head, tail, front + hind upper / lower leg and paw), each in its
joint's local frame, laid out on the joint positions of `quad_config` in quadruped.rs (the rest
pose). Shapes are signed-distance models (sdfkit.py): exact tapered limbs and smooth muscle
blends instead of metaballs, which ballooned at every joint. All anatomy is authored in the
rest-pose SPINE frame (Y up, +Z forward, origin = body centre at height `root_y`).

Legs are exported for the LEFT side (+X); the game mirrors them for the right legs, so inner /
outer sides can differ (pale inner legs, the elbow tucked to the chest).

Baked per-vertex data (see sdfkit.py): region (R), cavity / AO (G), coat tone (B), coat tint (A)
and a fur-flow UV. The game maps tone / tint onto each species' coat colours (dark, base, light,
tint) — the polar bear reuses the bear mesh with a white coat.

    blender -b --factory-startup --python tools/blender_forest/animals.py [-- preview.png]
"""
import math
import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from common import OUT, clear_scene, export_glb, name_material  # noqa: E402
from sdfkit import (  # noqa: E402
    Body, Chain, Cone, Ellipsoid, RBox, Sphere, Squash, Tufts, ambient_occlusion, axis_uv,
    gradient, mesh_body, norm, rot_x, rot_y, rot_z, smoothstep, v3,
)

# Regions (vertex colour R): the game's palette order (quadruped.rs `kit_quad_meshes`).
FUR, SKIN, DETAIL, EYE, ACCENT, HORN = range(6)

# Rig dimensions — MUST mirror `quad_config` in src/quadruped.rs (joint layout only).
RIG = {
    "dog": dict(root_y=0.42, body=(0.26, 0.26, 0.55), chest_z=0.25, neck_h=0.25, neck_angle=0.6,
                lu=0.24, ll=0.12, spread=0.11, tail_angle=0.5),
    "wolf": dict(root_y=0.48, body=(0.24, 0.22, 0.62), chest_z=0.28, neck_h=0.24, neck_angle=0.95,
                 lu=0.27, ll=0.13, spread=0.09, tail_angle=0.45),
    "horse": dict(root_y=0.68, body=(0.3, 0.28, 0.72), chest_z=0.32, neck_h=0.38, neck_angle=0.45,
                  lu=0.33, ll=0.21, spread=0.13, tail_angle=0.3),
    "deer": dict(root_y=0.55, body=(0.2, 0.2, 0.58), chest_z=0.26, neck_h=0.22, neck_angle=0.5,
                 lu=0.28, ll=0.16, spread=0.08, tail_angle=0.6),
    "camel": dict(root_y=0.72, body=(0.28, 0.26, 0.7), chest_z=0.3, neck_h=0.42, neck_angle=0.75,
                  lu=0.34, ll=0.24, spread=0.12, tail_angle=0.4),
    "bear": dict(root_y=0.52, body=(0.46, 0.42, 0.78), chest_z=0.26, neck_h=0.12, neck_angle=0.8,
                 lu=0.2, ll=0.11, spread=0.18, tail_angle=0.3),
}


def P(x, y, z):
    return v3((x, y, z))


def frames(r):
    """Rest-pose joint frames (R, t) in the spine frame, as spawn_quad lays them out."""
    bw, bh, bl = r["body"]
    cz = r["chest_z"]
    leg_y = -bh / 2 + 0.05
    eye = np.eye(3)
    neck_t = P(0, bh * 0.15, cz * 1.35)
    neck_R = rot_x(r["neck_angle"])
    head_t = neck_t + neck_R @ P(0, r["neck_h"], 0)
    fj = P(r["spread"], leg_y, cz * 1.35)
    bj = P(r["spread"], leg_y, -bl / 2 + 0.15)
    lu, ll = r["lu"], r["ll"]
    return {
        "spine": (eye, P(0, 0, 0)),
        "neck": (neck_R, neck_t),
        "head": (eye, head_t),
        "tail": (rot_x(r["tail_angle"]), P(0, bh * 0.3, -bl / 2 + 0.05)),
        "leg_upper": (eye, fj),
        "leg_lower": (eye, fj - P(0, lu, 0)),
        "paw": (eye, fj - P(0, lu + ll, 0)),
        "hind_upper": (eye, bj),
        "hind_lower": (eye, bj - P(0, lu, 0)),
        "hind_paw": (eye, bj - P(0, lu + ll, 0)),
    }


LEGS = ("leg_upper", "leg_lower", "paw", "hind_upper", "hind_lower", "hind_paw")


def Tuft(freq, flow=(0, 0, -1), seed=1):
    """Fur clump noise for `Body.shag`; `freq` in the old units (x3 = clumps of ~3-8 cm)."""
    return Tufts(freq * 3.0, flow, seed=seed)


class Part:
    """A joint's mesh: bodies (closed surfaces) + the fur-flow axis (root -> tip of the hair)."""

    def __init__(self, joint, bodies, axis, up=(0, 1, 0)):
        self.joint, self.bodies, self.axis, self.up = joint, bodies, axis, up
        # Short hair on legs and face: a finer clump scale than the body's guard hair.
        self.uv_scale = 1.8 if joint in LEGS else 2.2 if joint == "head" else 1.0


class Coat:
    """Tone / tint painting: a base function of (p, n) plus soft-masked overrides in order."""

    def __init__(self, base):
        self.base = base
        self.ops = []

    def tone(self, mask, value, soft=0.02, k=1.0):
        self.ops.append((0, mask, value, soft, k))
        return self

    def tint(self, mask, value, soft=0.02, k=1.0):
        self.ops.append((1, mask, value, soft, k))
        return self

    def __call__(self, p, n, part):
        tone, tint = self.base(p, n, part)
        for ch, mask, value, soft, k in self.ops:
            w = smoothstep(soft, -soft, mask.d(p)) * k
            if ch == 0:
                tone = tone * (1 - w) + value * w
            else:
                tint = tint * (1 - w) + value * w
        return np.clip(tone, 0, 1), np.clip(tint, 0, 1)


def ground_cut(body, ground_y):
    """Flatten a paw's sole on the ground plane."""
    return body.cut(RBox(P(0, ground_y + 1.0, 0), P(5, 1.0, 5)))


# ───────────────────────────────────────────────────────────────── canines
def canine(name, r, opt):
    """Wolf / dog: deep narrow keel-shaped chest, tucked waist, slim legs (elbows against the
    chest, a real hock angle behind), thick neck (a ruff on the wolf), long muzzle."""
    F = frames(r)
    g = -r["root_y"]  # ground height in the spine frame
    s = opt["scale"]  # overall bulk (dog stockier)
    bw, bh, bl = r["body"]
    top = bh * 0.55  # withers height above the body centre
    keel = opt["keel"]  # brisket depth below the centre
    zc = r["chest_z"] * 1.35  # shoulder / neck-base z
    zh = -bl / 2 + 0.15  # hip z
    parts = {}

    # Torso
    b = Body(h=0.005, budget=2300)
    w = bw * 0.42 * s
    b.add(Ellipsoid(P(0, top * 0.29, zc - 0.178), (w * 0.94, top * 0.78, 0.19)), FUR)  # ribcage
    b.add(Ellipsoid(P(0, keel * 0.38, zc - 0.108), (w * 0.67, -keel * 0.62, 0.13)), FUR, 0.05)  # keel
    b.add(Ellipsoid(P(0, keel * 0.24, zc - 0.008), (w * 0.71, -keel * 0.53, 0.07)), FUR, 0.04)  # brisket
    b.add(Ellipsoid(P(0, top * 0.62, zc - 0.088), (w * 0.74, top * 0.45, 0.11)), FUR, 0.05)  # withers
    for sx in (-1, 1):
        b.add(Ellipsoid(P(sx * w * 0.7, top * 0.25, zc - 0.048), (0.026 * s, 0.08, 0.05), rot_x(-0.7)), FUR, 0.04)
    b.add(Ellipsoid(P(0, top * 0.33, (zc + zh) * 0.5 - 0.089), (w * 0.71, top * 0.62, 0.17)), FUR, 0.06)  # loin
    b.add(Ellipsoid(P(0, top * 0.29, zh - 0.04), (w * 0.84, top * 0.73, 0.115)), FUR, 0.05)  # croup
    for sx in (-1, 1):
        b.add(Ellipsoid(P(sx * w * 0.55, -0.035, zh - 0.03), (w * 0.62, top * 0.8, 0.088)), FUR, 0.04)  # haunch
    b.add(Sphere(P(0, top * 0.08, zh - 0.12), 0.062 * s), FUR, 0.05)  # buttocks
    b.add(Ellipsoid(P(0, top * 0.58, zc + 0.012), (w * 0.7, 0.07, 0.07)), FUR, 0.05)  # neck root
    # Belly fringe + a coarse shag over the back (clumped coat edge on the silhouette).
    b.shag(Ellipsoid(P(0, keel * 0.85, zc - 0.13), (w * 0.8, 0.05, 0.16)), 0.008 * opt["shag"],
           Tuft(55, (0, -1, -0.4), seed=3))
    b.shag(Ellipsoid(P(0, top, -0.02), (w * 1.2, 0.07, 0.4)), 0.005 * opt["shag"], Tuft(45, (0, 0, -1), seed=4))
    b.shag(Ellipsoid(P(0, -0.04, zh - 0.08), (w * 1.1, 0.07, 0.07)), 0.007 * opt["shag"],
           Tuft(55, (0, -1, -0.2), seed=12))  # breeches
    parts["spine"] = Part("spine", [b], [P(0, 0.02, zc + 0.12), P(0, 0.02, zh - 0.25)])

    # Neck (thick, with a ruff on wolves)
    nt = F["neck"][1]
    ht = F["head"][1]
    b = Body(h=0.0045, budget=1700)
    b.add(Chain([(nt + P(0, 0.02, -0.06), 0.068 * s), ((nt + ht) / 2 + P(0, 0.005, -0.015), 0.058 * s),
                 (ht + P(0, -0.008, -0.038), 0.042 * s)]), FUR)
    b.add(Cone(P(0, keel * 0.18, zc + 0.05), ht + P(0, -0.045, 0.02), 0.042 * s, 0.03 * s), FUR, 0.05)  # throat
    b.add(Ellipsoid(nt + P(0, 0.04, -0.07), (0.06 * s, 0.06, 0.08)), FUR, 0.05)  # crest onto the withers
    if opt["ruff"]:
        b.add(Ellipsoid((nt + ht) / 2 + P(0, -0.005, -0.01), (0.074, 0.088, 0.08), rot_x(-0.6)), FUR, 0.04)
        b.shag(Sphere((nt + ht) / 2, 0.13), 0.012, Tuft(38, (0, -0.6, -0.8), seed=5), soft=0.04)
    else:
        b.shag(Sphere((nt + ht) / 2, 0.1), 0.005, Tuft(45, (0, -0.6, -0.8), seed=5), soft=0.03)
    bodies = [b]
    if opt.get("collar"):
        A = (ht - nt) / np.linalg.norm(ht - nt)
        U = np.cross(A, P(1, 0, 0))
        U /= np.linalg.norm(U)
        V = np.cross(A, U)
        C = nt + (ht - nt) * 0.58
        rr = opt["collar"]
        ring = [(C + rr * (math.cos(t) * U + math.sin(t) * V), 0.0075) for t in np.linspace(0, 2 * math.pi, 25)]
        col = Body(h=0.0025, budget=320)
        col.add(Chain(ring), ACCENT)
        bodies.append(col)
    parts["neck"] = Part("neck", bodies, [ht + P(0, 0.0, 0.0), nt + P(0, -0.04, -0.06)])

    # Head
    parts["head"] = Part("head", canine_head(ht, opt), [ht + P(0, 0.0, 0.2), ht + P(0, 0.0, -0.06)],
                         up=(0, 1, 0))

    # Tail: wolf hangs bushy toward the hocks; dog carries it up in a curve.
    tt = F["tail"][1]
    b = Body(h=0.004, budget=750)
    knots = [(tt + P(0, 0.0, -0.02), 0.026)] + [(tt + P(*o), rr) for o, rr in opt["tail"]]
    b.add(Chain(knots), FUR)
    b.shag(Chain(knots), 0.013 * opt["tail_shag"], Tuft(55, v3(knots[-1][0]) - v3(knots[1][0]), seed=6), soft=0.02)
    parts["tail"] = Part("tail", [b], [k for k, _ in knots], up=(0, 1, 0))

    # Front leg (left, +X): shoulder point + upper arm half-buried in the chest, the elbow tucked
    # against it, a slim straight forearm to the carpus (rig elbow), pastern, oval paw.
    J = F["leg_upper"][1]
    W = F["leg_lower"][1]
    Pw = F["paw"][1]
    lw = opt["leg"]
    ox = opt["tuck"]  # the whole leg column sits this far inside the joint (narrow track)
    o = P(ox, 0, 0)
    b = Body(h=0.0035, budget=900)
    b.add(Cone(J + o + P(0.0, 0.01, 0.006), J + o + P(-0.004, -0.1, -0.035), 0.03 * s, 0.023 * lw), FUR)  # humerus
    b.add(Ellipsoid(J + o + P(-0.002, -0.06, -0.028), (0.023 * s, 0.048, 0.03)), FUR, 0.015)  # triceps
    b.add(Sphere(J + o + P(-0.005, -0.108, -0.045), 0.016 * lw), FUR, 0.01)  # elbow point
    b.add(Chain([(J + o + P(-0.005, -0.1, -0.026), 0.022 * lw), (J + o + P(-0.002, -0.19, -0.004), 0.0175 * lw),
                 (W + o, 0.015 * lw)]), FUR, 0.015)  # forearm
    b.add(Ellipsoid(J + o + P(-0.002, -0.15, -0.002), (0.019 * lw, 0.05, 0.022 * lw)), FUR, 0.015)
    b.shag(Cone(J + o + P(0, -0.1, -0.045), W + o + P(0, 0.04, -0.025), 0.026, 0.018), 0.004 * opt["shag"],
           Tuft(70, (0, -1, -0.3), seed=8), soft=0.012)  # feathering behind the forearm
    pf = P(W[0] + ox, g, W[2] + 0.014)
    axis = [J + o + P(0, 0.1, 0), W + o, pf]  # shared by the leg's three parts: strands run on
    parts["leg_upper"] = Part("leg_upper", [b], axis, up=(0, 0, 1))
    b = Body(h=0.003, budget=480)
    # Starts a little above the joint, just inside the forearm's end: no cap ring at the carpus.
    b.add(Chain([(W + o + P(0, 0.01, 0), 0.0146 * lw), (W + o, 0.0146 * lw), (W + o + P(0, -0.075, 0.008), 0.0135 * lw),
                 (P(W[0] + ox, g + 0.04, W[2] + 0.014), 0.0135 * lw)]), FUR)
    b.add(Sphere(W + o + P(0, -0.014, -0.013 * lw), 0.007 * lw), FUR, 0.005)  # carpal pad
    parts["leg_lower"] = Part("leg_lower", [b], axis, up=(0, 0, 1))
    parts["paw"] = Part("paw", [canine_paw(pf, opt["paw"], front=True)], axis, up=(0, 0, 1))

    # Hind leg: thigh around the hip (mostly inside the haunch), stifle forward, gaskin sloping
    # back to the hock (rig knee) with the Achilles tendon behind, vertical metatarsus.
    H = F["hind_upper"][1]
    K = F["hind_lower"][1]
    lu = r["lu"]
    oh = P(opt["tuck"] * 0.7, 0, 0)
    b = Body(h=0.0035, budget=950)
    b.add(Sphere(H + oh + P(-0.004, 0.008, -0.004), 0.036 * s), FUR)
    b.add(Ellipsoid(H + oh + P(-0.002, -0.06, 0.005), (0.033 * s, 0.075, 0.054 * s), rot_x(-0.3)), FUR, 0.03)  # thigh
    b.add(Sphere(H + oh + P(0, -lu * 0.42, 0.03), 0.023 * s), FUR, 0.025)  # stifle
    b.add(Chain([(H + oh + P(0, -lu * 0.4, 0.02), 0.027 * s), (H + oh + P(0, -lu * 0.74, -0.018), 0.018 * lw),
                 (K + oh, 0.0155 * lw)]), FUR, 0.025)  # gaskin
    b.add(Cone(H + oh + P(0, -lu * 0.63, -0.036), K + oh + P(0, 0.006, -0.024), 0.0105 * lw, 0.0095 * lw), FUR, 0.012)
    b.shag(Ellipsoid(H + oh + P(0, -0.07, -0.045), (0.045, 0.075, 0.035)), 0.005 * opt["shag"],
           Tuft(60, (0, -1, -0.2), seed=9), soft=0.02)  # breeches
    ph = P(K[0] + oh[0], g, K[2] + 0.006)
    axis = [H + oh + P(0, 0.1, 0), K + oh, ph]
    parts["hind_upper"] = Part("hind_upper", [b], axis, up=(0, 0, 1))
    b = Body(h=0.003, budget=480)
    b.add(Chain([(K + oh + P(0, 0.01, 0), 0.015 * lw), (K + oh, 0.015 * lw), (K + oh + P(0, -0.07, 0.003), 0.0135 * lw),
                 (P(K[0] + oh[0], g + 0.04, K[2] + 0.006), 0.0135 * lw)]), FUR)
    b.add(Sphere(K + oh + P(0, 0.0, -0.022), 0.0098 * lw), FUR, 0.01)  # point of hock
    parts["hind_lower"] = Part("hind_lower", [b], axis, up=(0, 0, 1))
    parts["hind_paw"] = Part("hind_paw", [canine_paw(ph, opt["paw"] * 0.93, front=False)], axis, up=(0, 0, 1))
    return parts


def canine_head(ht, opt):
    hs = opt["head"]
    ml = opt["muzzle"]  # muzzle length
    b = Body(h=0.0032, budget=1500)
    c = lambda x, y, z: ht + P(x * hs, y * hs, z * hs)  # noqa: E731
    b.add(Ellipsoid(c(0, 0.014, 0.0), (0.062 * hs, 0.052 * hs, 0.064 * hs)), FUR)  # cranium
    for sx in (-1, 1):
        b.add(Ellipsoid(c(sx * 0.044, -0.01, 0.032), (0.028 * hs, 0.028 * hs, 0.038 * hs)), FUR, 0.02)  # cheekbone
    b.add(Ellipsoid(c(0, 0.036, 0.052), (0.042 * hs, 0.024 * hs, 0.036 * hs)), FUR, 0.018)  # brow / stop
    zm = 0.072 * hs
    tip = zm + ml
    b.add(Squash(Cone(P(0, 0, 0), P(0, -0.006, ml), 0.031 * hs, 0.018 * hs), ht + P(0, -0.014 * hs, zm),
                 (0.82, 1.05, 1.0)), FUR, 0.022)  # muzzle
    b.add(Cone(c(0, 0.016, 0.07), ht + P(0, 0.002 * hs, tip - 0.012), 0.02 * hs, 0.013 * hs), FUR, 0.016)  # nose bridge
    b.add(Cone(c(0, -0.036, 0.045), ht + P(0, -0.038 * hs, tip - 0.018), 0.026 * hs, 0.012 * hs), FUR, 0.02)  # jaw
    nz = tip + 0.003
    b.add(RBox(ht + P(0, -0.004 * hs, nz), (0.014 * hs, 0.011 * hs, 0.009 * hs), 0.0075 * hs), SKIN, 0.004)  # nose
    for sx in (-1, 1):
        b.sub(Sphere(ht + P(sx * 0.006 * hs, -0.006 * hs, nz + 0.008 * hs), 0.004 * hs), SKIN, 0.002)  # nostril
        # Lip line: a dark seam along the muzzle side.
        b.add(Cone(ht + P(sx * 0.016 * hs, -0.031 * hs, zm + 0.01), ht + P(sx * 0.01 * hs, -0.03 * hs, tip - 0.012),
                   0.0045 * hs, 0.0035 * hs), SKIN, 0.003)
        # Almond eyes set obliquely, slightly sunk.
        e = c(sx * 0.031, 0.017, 0.074)
        b.sub(Sphere(e + P(sx * 0.004, 0, 0), 0.011 * hs), FUR, 0.006)
        b.add(Squash(Sphere(P(0, 0, 0), 0.0095 * hs), e, (0.75, 0.62, 1.15), rot_y(sx * 0.55) @ rot_z(sx * 0.25)), EYE)
        # Cheek ruff tufts behind the jaw.
        if opt["ruff"]:  # cheek ruff flaring out and back behind the jaw
            b.add(Ellipsoid(c(sx * 0.048, -0.03, -0.004), (0.014 * hs, 0.024 * hs, 0.026 * hs), rot_z(sx * 0.5)), FUR, 0.016)
    if opt["ruff"]:
        b.shag(Ellipsoid(c(0, -0.03, -0.006), (0.09 * hs, 0.05 * hs, 0.045 * hs)), 0.016 * hs,
               Tuft(55, (0, -0.6, -1), seed=11), soft=0.015)
    # Ears: upright pointed triangles, cupped toward the front (separate body: thin).
    e = Body(h=0.0025, budget=420)
    for sx in (-1, 1):
        base = c(sx * 0.034, 0.042, -0.006)
        R = rot_y(sx * -0.32) @ rot_z(-sx * opt["ear_splay"])
        hgt = opt["ear"] * hs
        ear = Squash(Cone(P(0, 0, 0), P(0, hgt, -0.006), 0.03 * hs, 0.003), base, (0.38, 1.0, 1.0), R @ rot_y(math.pi / 2))
        e.add(ear, FUR)
        e.sub(Squash(Cone(P(0, 0.006, 0), P(0, hgt * 0.92, -0.004), 0.022 * hs, 0.002), base + R @ P(0, 0, 0.007),
                     (0.3, 1.0, 1.0), R @ rot_y(math.pi / 2)), FUR, 0.002)
        e.add(Sphere(base + P(0, -0.004, 0), 0.02 * hs), FUR, 0.01)  # ear root into the skull
    return [b, e]


def canine_paw(o, sz, front):
    """Oval paw standing on the ground at `o` (spine frame): pad mass, four toes, dark claws."""
    b = Body(h=0.0025, budget=420 if front else 380)
    b.add(Ellipsoid(o + P(0, 0.018 * sz, 0.008 * sz), (0.026 * sz, 0.02 * sz, 0.032 * sz)), FUR)
    b.add(Cone(o + P(0, 0.042, 0.0), o + P(0, 0.02 * sz, 0.006 * sz), 0.0122, 0.02 * sz), FUR, 0.01)
    for x, z, rr in ((-0.0105, 0.037, 0.011), (0.0105, 0.037, 0.011), (-0.026, 0.026, 0.0098), (0.026, 0.026, 0.0098)):
        t = o + P(x * sz, 0.0105 * sz, z * sz)
        b.add(Sphere(t, rr * sz), FUR, 0.008)
        b.add(Cone(t + P(0, -0.002, rr * sz * 0.7), t + P(x * 0.1 * sz, -0.009 * sz, rr * sz * 1.5), 0.0035 * sz, 0.0012),
              DETAIL)  # claw
    ground_cut(b, o[1] - 0.0005)
    return b


# ───────────────────────────────────────────────────────────────── bear
def bear(name, r):
    """Brown bear: long heavy body with a muscular shoulder hump (the highest point), the back
    sloping to a lower rump, shoulders / thighs hanging down over the leg tops, thick tapering
    limbs (no joint bulges), big plantigrade paws with long pale claws, a massive head with a
    short muzzle and small round ears."""
    F = frames(r)
    g = -r["root_y"]
    bw, bh, bl = r["body"]
    zc = r["chest_z"] * 1.35
    zh = -bl / 2 + 0.15
    parts = {}

    b = Body(h=0.0065, budget=2700)
    b.add(Ellipsoid(P(0, 0.01, -0.03), (0.195, 0.17, 0.36)), FUR)  # barrel
    b.add(Ellipsoid(P(0, -0.03, zc - 0.12), (0.185, 0.19, 0.19)), FUR, 0.08)  # chest
    b.add(Ellipsoid(P(0, 0.17, zc - 0.15), (0.14, 0.11, 0.17)), FUR, 0.08)  # shoulder hump
    for sx in (-1, 1):
        b.add(Ellipsoid(P(sx * 0.14, -0.1, zc - 0.02), (0.092, 0.19, 0.125)), FUR, 0.07)  # shoulders
        b.add(Ellipsoid(P(sx * 0.13, -0.1, zh - 0.03), (0.095, 0.19, 0.135)), FUR, 0.07)  # thighs
        # Long fur hanging over the leg tops (shoulder and thigh skirts).
        b.shag(Ellipsoid(P(sx * 0.15, -0.26, zc - 0.02), (0.1, 0.06, 0.13)), 0.011, Tuft(30, (0, -1, -0.2), seed=29 + sx),
               soft=0.03)
        b.shag(Ellipsoid(P(sx * 0.14, -0.26, zh - 0.03), (0.1, 0.06, 0.14)), 0.01, Tuft(30, (0, -1, -0.2), seed=31 + sx),
               soft=0.03)
    b.add(Ellipsoid(P(0, 0.02, zh - 0.07), (0.175, 0.16, 0.16)), FUR, 0.08)  # hindquarters
    b.add(Ellipsoid(P(0, -0.07, -0.03), (0.16, 0.11, 0.25)), FUR, 0.08)  # belly
    b.add(Ellipsoid(P(0, 0.085, zc + 0.05), (0.13, 0.13, 0.11)), FUR, 0.08)  # neck root
    b.shag(Ellipsoid(P(0, 0.0, 0.0), (0.25, 0.25, 0.45)), 0.006, Tuft(28, (0, -0.3, -1), seed=21), soft=0.05)
    b.shag(Ellipsoid(P(0, 0.22, zc - 0.13), (0.15, 0.09, 0.2)), 0.009, Tuft(24, (0, 0, -1), seed=22), soft=0.05)
    b.shag(Ellipsoid(P(0, -0.19, -0.02), (0.2, 0.06, 0.32)), 0.011, Tuft(26, (0, -1, -0.3), seed=23), soft=0.04)
    parts["spine"] = Part("spine", [b], [P(0, 0.0, zc + 0.15), P(0, 0.0, zh - 0.3)])

    nt = F["neck"][1]
    ht = F["head"][1]
    hs = 1.3
    b = Body(h=0.0055, budget=1100)
    hc = ht + P(0, -0.05, 0.02)  # the head hangs low and forward of its joint
    b.add(Chain([(nt + P(0, -0.02, -0.06), 0.14), (hc + P(0, -0.01, -0.04), 0.115)]), FUR)
    b.add(Ellipsoid(nt + P(0, 0.07, -0.04), (0.12, 0.1, 0.12)), FUR, 0.06)
    b.add(Cone(nt + P(0, 0.1, -0.08), hc + P(0, 0.05, -0.04), 0.1, 0.088), FUR, 0.06)  # crest: hump -> poll
    b.shag(Sphere((nt + ht) / 2, 0.2), 0.014, Tuft(26, (0, -0.4, -1), seed=24), soft=0.05)
    parts["neck"] = Part("neck", [b], [ht, nt + P(0, -0.05, -0.08)])

    # Head: massive skull, broad cheeks, short muzzle, small round ears.
    b = Body(h=0.0042, budget=1700)
    c = lambda x, y, z: hc + P(x * hs, y * hs, z * hs)  # noqa: E731
    b.add(Ellipsoid(c(0, 0.025, 0.02), (0.105 * hs, 0.092 * hs, 0.108 * hs)), FUR)  # cranium
    b.add(Ellipsoid(c(0, 0.055, 0.085), (0.072 * hs, 0.048 * hs, 0.062 * hs)), FUR, 0.04)  # brow
    for sx in (-1, 1):
        b.add(Ellipsoid(c(sx * 0.074, -0.025, 0.035), (0.058 * hs, 0.068 * hs, 0.072 * hs)), FUR, 0.05)  # jowls
    b.add(Squash(Cone(P(0, 0, 0), P(0, -0.012 * hs, 0.095 * hs), 0.06 * hs, 0.045 * hs), c(0, -0.012, 0.12),
                 (1.05, 0.95, 1.0)), FUR, 0.04)  # muzzle
    b.add(Cone(c(0, -0.06, 0.085), c(0, -0.06, 0.195), 0.04 * hs, 0.027 * hs), FUR, 0.035)  # lower jaw
    b.add(RBox(c(0, -0.012, 0.226), (0.031 * hs, 0.021 * hs, 0.015 * hs), 0.012 * hs), SKIN, 0.006)  # nose
    for sx in (-1, 1):
        b.sub(Sphere(c(sx * 0.013, -0.018, 0.24), 0.0062 * hs), SKIN, 0.003)
        b.add(Cone(c(sx * 0.04, -0.054, 0.14), c(sx * 0.028, -0.049, 0.208), 0.0058 * hs, 0.0048 * hs), SKIN, 0.004)
        e = c(sx * 0.05, 0.034, 0.118)
        b.sub(Sphere(e + P(sx * 0.004, 0.002, 0), 0.012 * hs), FUR, 0.008)
        b.add(Sphere(e, 0.0098 * hs), EYE)
    b.shag(Ellipsoid(c(0, -0.03, 0.0), (0.15 * hs, 0.09 * hs, 0.09 * hs)), 0.015, Tuft(32, (0, -0.6, -1), seed=25),
           soft=0.03)
    e = Body(h=0.003, budget=380)
    for sx in (-1, 1):
        base = c(sx * 0.08, 0.1, -0.008)
        R = rot_y(sx * 0.4) @ rot_z(-sx * 0.3)
        e.add(Squash(Sphere(P(0, 0, 0), 0.037 * hs), base, (1.0, 0.92, 0.42), R), FUR)
        e.sub(Squash(Sphere(P(0, 0, 0), 0.026 * hs), base + R @ P(0, 0.005, 0.015), (1.0, 0.9, 0.4), R), FUR, 0.003)
    parts["head"] = Part("head", [b, e], [c(0, 0, 0.27), c(0, 0, -0.08)])

    tt = F["tail"][1]
    b = Body(h=0.004, budget=200)
    b.add(Ellipsoid(tt + P(0, -0.005, -0.03), (0.035, 0.032, 0.045)), FUR)
    b.shag(Sphere(tt, 0.08), 0.008, Tuft(50, (0, -0.5, -1), seed=26), soft=0.02)
    parts["tail"] = Part("tail", [b], [tt, tt + P(0, -0.03, -0.07)])

    # Legs: thick, tapering columns whose tops hide inside the shoulder / thigh masses; no joint
    # bulges (each joint is capped by exactly the limb's radius there).
    o = P(-0.032, 0, 0)
    J = F["leg_upper"][1] + o
    W = F["leg_lower"][1] + o
    b = Body(h=0.005, budget=950)
    b.add(Chain([(J + P(0, 0.05, -0.005), 0.07), (J + P(0, -0.07, -0.006), 0.067), (J + P(0, -0.145, 0.003), 0.06),
                 (W, 0.056)]), FUR)
    b.shag(Sphere(W, 0.06), 0.009, Tuft(38, (0, -1, 0.0), seed=33), soft=0.02)  # wrist fringe over the seam
    b.add(Ellipsoid(J + P(0, -0.09, -0.035), (0.055, 0.075, 0.05)), FUR, 0.04)  # fur behind the elbow
    b.shag(Cone(J + P(0, -0.03, -0.05), W + P(0, 0.03, -0.035), 0.065, 0.045), 0.02,
           Tuft(32, (0, -1, -0.2), seed=27), soft=0.03)  # long fur behind the forearm
    pf = P(W[0], g, W[2] + 0.02)
    axis = [J + P(0, 0.12, 0), W, pf]
    parts["leg_upper"] = Part("leg_upper", [b], axis, up=(0, 0, 1))
    b = Body(h=0.004, budget=420)
    b.add(Chain([(W + P(0, 0.025, 0), 0.054), (W, 0.054), (W + P(0, -0.07, 0.016), 0.056)]), FUR)
    b.shag(Sphere(W + P(0, -0.075, 0.016), 0.05), 0.008, Tuft(40, (0, -1, 0.0), seed=34), soft=0.02)
    parts["leg_lower"] = Part("leg_lower", [b], axis, up=(0, 0, 1))
    parts["paw"] = Part("paw", [bear_paw(pf, front=True)], axis, up=(0, 0, 1))

    H = F["hind_upper"][1] + o
    K = F["hind_lower"][1] + o
    b = Body(h=0.005, budget=950)
    b.add(Chain([(H + P(0, 0.05, -0.01), 0.078), (H + P(0, -0.07, 0.01), 0.072), (H + P(0, -0.15, 0.0), 0.06),
                 (K, 0.057)]), FUR)
    b.add(Sphere(K + P(0, 0.012, -0.03), 0.04), FUR, 0.03)  # heel
    b.shag(Sphere(K, 0.062), 0.009, Tuft(38, (0, -1, 0.0), seed=35), soft=0.02)
    b.shag(Ellipsoid(H + P(0, -0.06, -0.05), (0.07, 0.1, 0.05)), 0.012, Tuft(36, (0, -1, -0.2), seed=28), soft=0.03)
    ph = P(K[0], g, K[2])
    axis = [H + P(0, 0.12, 0), K, ph]
    parts["hind_upper"] = Part("hind_upper", [b], axis, up=(0, 0, 1))
    b = Body(h=0.004, budget=420)
    b.add(Chain([(K + P(0, 0.025, 0), 0.055), (K, 0.055), (K + P(0, -0.07, 0.01), 0.056)]), FUR)
    b.shag(Sphere(K + P(0, -0.075, 0.01), 0.05), 0.008, Tuft(40, (0, -1, 0.0), seed=36), soft=0.02)
    b.add(Sphere(K + P(0, -0.045, -0.038), 0.042), FUR, 0.03)  # heel down to the sole
    parts["hind_lower"] = Part("hind_lower", [b], axis, up=(0, 0, 1))
    parts["hind_paw"] = Part("hind_paw", [bear_paw(ph, front=False)], axis, up=(0, 0, 1))
    return parts


def bear_paw(o, front):
    """Bear paw standing on the ground at `o`: broad pad mass, five toes in an arc, long pale
    claws in front, short ones behind; the hind foot is a long plantigrade sole."""
    b = Body(h=0.0032, budget=650)
    if front:
        b.add(Ellipsoid(o + P(0, 0.035, 0.03), (0.064, 0.04, 0.08)), FUR)
        b.add(Cone(o + P(0, 0.085, -0.004), o + P(0, 0.045, 0.02), 0.052, 0.06), FUR, 0.03)
        zt, claw = 0.095, 0.045
    else:
        b.add(Ellipsoid(o + P(0, 0.03, 0.0), (0.058, 0.035, 0.11)), FUR)
        b.add(Cone(o + P(0, 0.08, -0.03), o + P(0, 0.04, -0.01), 0.052, 0.057), FUR, 0.03)
        zt, claw = 0.095, 0.025
    for x in (-0.046, -0.023, 0.0, 0.023, 0.046):
        zz = zt - abs(x) * 0.35
        t = o + P(x, 0.024, zz)
        b.add(Sphere(t, 0.019), FUR, 0.012)
        b.add(Cone(t + P(x * 0.1, 0.0, 0.012), t + P(x * 0.25, -0.02, 0.012 + claw), 0.0075, 0.0015), DETAIL)
    ground_cut(b, o[1] - 0.0005)
    return b


# ───────────────────────────────────────────────────────────────── ungulates
def hoof_cloven(o, sz, budget=300):
    """Deer / goat hoof on the ground at `o`: two pointed dark toes, dewclaws, short pastern."""
    b = Body(h=0.0022, budget=budget)
    b.add(Cone(o + P(0, 0.05 * sz, -0.004), o + P(0, 0.022 * sz, 0.004 * sz), 0.0105 * sz, 0.0115 * sz), FUR)
    for sx in (-1, 1):
        b.add(Squash(Cone(P(0, 0, -0.01), P(0, 0, 0.012), 0.009, 0.003), o + P(sx * 0.0065 * sz, 0.009 * sz, 0.008 * sz),
                     (0.75 * sz, 1.15 * sz, 1.0 * sz), rot_x(0.35)), DETAIL, 0.002)
        b.add(Sphere(o + P(sx * 0.006 * sz, 0.03 * sz, -0.011 * sz), 0.0035 * sz), DETAIL, 0.002)  # dewclaw
    ground_cut(b, o[1] - 0.0004)
    return b


def hoof_solid(o, sz, budget=320):
    """Horse hoof on the ground at `o`: a dark sloped wall under a hairy coronet."""
    b = Body(h=0.0028, budget=budget)
    b.add(Cone(o + P(0, 0.05 * sz, -0.004), o + P(0, 0.03 * sz, 0.006 * sz), 0.0155 * sz, 0.02 * sz), FUR)
    b.add(Cone(o + P(0, 0.028 * sz, 0.004 * sz), o + P(0, 0.006, 0.012 * sz), 0.022 * sz, 0.028 * sz), DETAIL, 0.004)
    ground_cut(b, o[1] - 0.0004)
    return b


def camel_foot(o, sz, budget=360):
    """Camel foot: a broad soft pad with two toes and small dark nails."""
    b = Body(h=0.0028, budget=budget)
    b.add(Cone(o + P(0, 0.06 * sz, -0.006), o + P(0, 0.025 * sz, 0.01 * sz), 0.0165 * sz, 0.024 * sz), FUR)
    b.add(Ellipsoid(o + P(0, 0.016 * sz, 0.018 * sz), (0.042 * sz, 0.018 * sz, 0.05 * sz)), FUR, 0.012)
    for sx in (-1, 1):
        b.add(Ellipsoid(o + P(sx * 0.018 * sz, 0.016 * sz, 0.05 * sz), (0.016 * sz, 0.013 * sz, 0.02 * sz)), FUR, 0.006)
        b.add(Squash(Sphere(P(0, 0, 0), 0.008 * sz), o + P(sx * 0.018 * sz, 0.014 * sz, 0.068 * sz), (1.0, 0.7, 0.8)), DETAIL)
    ground_cut(b, o[1] - 0.0004)
    return b


def ungulate_leg(parts, F, r, g, front, upper, cannon, foot, budget=(800, 480), tuck=0.0):
    """One leg (left): `upper(b, J, W)` sculpts the upper segment between its joints; `cannon` =
    (r_top, r_mid, r_fetlock, fetlock_h, r_pastern, pastern_z) for the lower; `foot(o)` the hoof.
    `tuck` slides the whole column inward so its top hides inside the body's shoulder / haunch
    (the rig only rotates about X, so the offset survives every pose)."""
    key = ("leg", "paw") if front else ("hind", "hind_paw")
    J = F[f"{key[0]}_upper"][1] + P(tuck, 0, 0)
    W = F[f"{key[0]}_lower"][1] + P(tuck, 0, 0)
    rt, rm, rf, fh, rp, pz = cannon
    o = P(W[0], g, W[2] + pz)
    axis = [J + P(0, 0.12, 0), W, o]
    b = Body(h=0.0032, budget=budget[0])
    upper(b, J, W)
    parts[f"{key[0]}_upper"] = Part(f"{key[0]}_upper", [b], axis, up=(0, 0, 1))
    b = Body(h=0.0026, budget=budget[1])
    fet = P(W[0], g + fh, W[2] + pz * 0.35)
    b.add(Chain([(W + P(0, 0.012, 0), rt * 0.97), (W, rt * 0.97), (W + (fet - W) * 0.55, rm), (fet, rf),
                 (P(W[0], g + fh * 0.55, W[2] + pz * 0.8), rp)]), FUR)
    parts[f"{key[0]}_lower"] = Part(f"{key[0]}_lower", [b], axis, up=(0, 0, 1))
    parts[key[1]] = Part(key[1], [foot(o)], axis, up=(0, 0, 1))


def deer(name, r):
    """Red / roe deer (also the elk and goat): slender deep-chested body, long thin legs with a
    hock angle, cloven hooves, a long upright neck, narrow face with a dark nose, big ears,
    branching antlers, short white-bottomed tail."""
    F = frames(r)
    g = -r["root_y"]
    bw, bh, bl = r["body"]
    zc = r["chest_z"] * 1.35
    zh = -bl / 2 + 0.15
    parts = {}

    b = Body(h=0.0045, budget=2000)
    b.add(Ellipsoid(P(0, 0.028, zc - 0.17), (0.078, 0.092, 0.18)), FUR)  # ribcage
    b.add(Ellipsoid(P(0, -0.05, zc - 0.1), (0.056, 0.095, 0.12)), FUR, 0.05)  # keel
    b.add(Ellipsoid(P(0, -0.03, zc - 0.01), (0.058, 0.08, 0.07)), FUR, 0.04)  # brisket
    b.add(Ellipsoid(P(0, 0.072, zc - 0.09), (0.062, 0.048, 0.1)), FUR, 0.04)  # withers
    for sx in (-1, 1):
        b.add(Ellipsoid(P(sx * 0.056, 0.02, zc - 0.05), (0.022, 0.07, 0.045), rot_x(-0.6)), FUR, 0.035)
        b.add(Ellipsoid(P(sx * 0.044, -0.02, zh - 0.04), (0.05, 0.095, 0.085)), FUR, 0.04)  # haunch
    b.add(Ellipsoid(P(0, 0.028, 0.0), (0.074, 0.08, 0.17)), FUR, 0.06)  # loin / belly
    b.add(Ellipsoid(P(0, 0.038, zh - 0.04), (0.075, 0.085, 0.11)), FUR, 0.05)  # croup
    b.add(Sphere(P(0, 0.012, zh - 0.12), 0.055), FUR, 0.05)  # buttocks
    b.add(Ellipsoid(P(0, 0.06, zc + 0.01), (0.05, 0.06, 0.06)), FUR, 0.04)  # neck root
    b.shag(Ellipsoid(P(0, -0.13, zc - 0.11), (0.06, 0.04, 0.12)), 0.004, Tuft(60, (0, -1, -0.4), seed=41))
    parts["spine"] = Part("spine", [b], [P(0, 0.02, zc + 0.12), P(0, 0.02, zh - 0.25)])

    nt = F["neck"][1]
    ht = F["head"][1]
    b = Body(h=0.0038, budget=1000)
    b.add(Chain([(nt + P(0, 0.0, -0.045), 0.058), ((nt + ht) / 2 + P(0, 0.0, -0.012), 0.044), (ht + P(0, -0.012, -0.028), 0.035)]),
          FUR)
    b.add(Cone(P(0, -0.035, zc + 0.04), ht + P(0, -0.035, 0.012), 0.034, 0.024), FUR, 0.04)  # throat
    b.add(Ellipsoid(nt + P(0, 0.035, -0.05), (0.045, 0.05, 0.06)), FUR, 0.04)  # crest onto the withers
    b.shag(Ellipsoid((nt + ht) / 2 + P(0, -0.03, 0.03), (0.03, 0.07, 0.03)), 0.005, Tuft(55, (0, -1, 0.2), seed=42))
    parts["neck"] = Part("neck", [b], [ht, nt + P(0, -0.04, -0.06)])

    # Head
    b = Body(h=0.0028, budget=1400)
    HR = rot_x(0.3)
    c = lambda x, y, z: ht + HR @ P(x, y, z)  # noqa: E731
    b.add(Ellipsoid(c(0, 0.01, 0.0), (0.042, 0.04, 0.05), HR), FUR)  # cranium
    b.add(Squash(Cone(P(0, 0, 0), P(0, -0.02, 0.1), 0.036, 0.019), c(0, 0.0, 0.03), (0.85, 1.05, 1.0), HR), FUR, 0.02)  # face
    b.add(Cone(c(0, 0.025, 0.03), c(0, 0.002, 0.123), 0.022, 0.013), FUR, 0.015)  # nose bridge
    b.add(Cone(c(0, -0.028, 0.02), c(0, -0.031, 0.118), 0.024, 0.011), FUR, 0.015)  # jaw
    b.add(RBox(c(0, -0.012, 0.14), (0.0135, 0.0115, 0.008), 0.0065, HR), SKIN, 0.004)  # wet nose
    for sx in (-1, 1):
        b.sub(Sphere(c(sx * 0.006, -0.015, 0.149), 0.0035), SKIN, 0.002)
        e = c(sx * 0.034, 0.016, 0.042)
        b.sub(Sphere(e + P(sx * 0.005, 0, 0), 0.011), FUR, 0.005)
        b.add(Squash(Sphere(P(0, 0, 0), 0.0108), e, (0.85, 0.85, 1.1), HR @ rot_y(sx * 0.4)), EYE)
        b.add(Ellipsoid(c(sx * 0.032, -0.012, 0.04), (0.02, 0.024, 0.035), HR), FUR, 0.015)  # cheek
    e = Body(h=0.0022, budget=380)
    for sx in (-1, 1):
        base = c(sx * 0.033, 0.036, -0.018)
        R = rot_z(-sx * 0.75) @ rot_y(sx * -0.2)
        ear = Squash(Cone(P(0, 0, 0), P(0, 0.08, 0.0), 0.026, 0.006), base, (0.36, 1.0, 1.0), R @ rot_y(math.pi / 2))
        e.add(ear, FUR)
        e.sub(Squash(Cone(P(0, 0.008, 0), P(0, 0.074, 0.0), 0.02, 0.004), base + R @ P(0, 0, 0.0065), (0.28, 1.0, 1.0),
                     R @ rot_y(math.pi / 2)), FUR, 0.002)
        e.add(Sphere(base + P(0, -0.004, 0), 0.016), FUR, 0.008)
    bodies = [b, e]
    a = Body(h=0.0022, budget=700)  # antlers (the elk shares the deer mesh); upright, not tilted
    for sx in (-1, 1):
        B = c(sx * 0.022, 0.046, -0.008)
        kn = [B, B + P(sx * 0.045, 0.065, -0.03), B + P(sx * 0.075, 0.13, -0.045), B + P(sx * 0.072, 0.2, -0.02),
              B + P(sx * 0.058, 0.245, 0.018)]
        rr = [0.0085, 0.007, 0.006, 0.0048, 0.003]
        a.add(Chain(list(zip(kn, rr))), HORN)
        a.add(Sphere(B, 0.011), HORN, 0.003)  # burr
        for t0, d, rad in ((B + P(sx * 0.008, 0.012, 0.0), P(sx * 0.012, 0.03, 0.055), 0.005),
                           (kn[1], P(sx * 0.012, 0.035, 0.05), 0.0045),
                           (kn[2], P(sx * 0.03, 0.045, 0.035), 0.0042),
                           (kn[3], P(-sx * 0.01, 0.035, 0.04), 0.0036)):
            a.add(Cone(t0, t0 + d, rad, 0.0015), HORN, 0.004)
    bodies.append(a)
    parts["head"] = Part("head", bodies, [c(0, 0, 0.16), c(0, 0, -0.06)])

    tt = F["tail"][1]
    b = Body(h=0.003, budget=260)
    b.add(Ellipsoid(tt + P(0, -0.035, -0.035), (0.022, 0.048, 0.02), rot_x(0.5)), FUR)
    parts["tail"] = Part("tail", [b], [tt + P(0, 0.01, -0.01), tt + P(0, -0.08, -0.06)])

    def fore(b, J, W):
        b.add(Cone(J + P(-0.004, 0.01, 0.006), J + P(-0.006, -0.09, -0.03), 0.028, 0.02), FUR)  # humerus
        b.add(Ellipsoid(J + P(-0.004, -0.05, -0.024), (0.019, 0.045, 0.025)), FUR, 0.012)  # triceps
        b.add(Sphere(J + P(-0.006, -0.095, -0.037), 0.013), FUR, 0.008)  # elbow point
        b.add(Chain([(J + P(-0.006, -0.09, -0.022), 0.019), (J + P(-0.003, -0.19, -0.004), 0.0135), (W, 0.0118)]), FUR, 0.012)
        b.add(Ellipsoid(J + P(-0.003, -0.13, 0.0), (0.016, 0.045, 0.019)), FUR, 0.012)  # forearm muscle
        b.add(Ellipsoid(W + P(0, 0.006, 0.002), (0.0125, 0.016, 0.014)), FUR, 0.006)  # knee (carpus)

    def hind(b, H, K):
        lu = r["lu"]
        b.add(Sphere(H + P(-0.004, 0.008, -0.004), 0.034), FUR)
        b.add(Ellipsoid(H + P(-0.002, -0.06, 0.0), (0.031, 0.08, 0.055), rot_x(-0.3)), FUR, 0.03)  # ham
        b.add(Sphere(H + P(-0.002, -lu * 0.41, 0.03), 0.02), FUR, 0.02)  # stifle
        b.add(Chain([(H + P(-0.002, -lu * 0.39, 0.02), 0.023), (H + P(0, -lu * 0.75, -0.024), 0.0145), (K, 0.0118)]), FUR, 0.02)
        b.add(Cone(H + P(0, -lu * 0.62, -0.034), K + P(0, 0.004, -0.021), 0.0085, 0.0075), FUR, 0.01)  # achilles
        b.add(Sphere(K + P(0, 0.0, -0.018), 0.0085), FUR, 0.006)  # point of hock

    ungulate_leg(parts, F, r, g, True, fore, (0.0118, 0.0098, 0.0122, 0.05, 0.0105, 0.01), lambda o: hoof_cloven(o, 1.0),
                 tuck=-0.01)
    ungulate_leg(parts, F, r, g, False, hind, (0.0118, 0.0098, 0.0122, 0.05, 0.0105, 0.006), lambda o: hoof_cloven(o, 0.96),
                 tuck=-0.008)
    return parts


def horse(name, r):
    """Bay horse: barrel body, deep chest, big hindquarters, arched muscular neck with a mane,
    long head, knees / hocks / fetlocks, solid hooves, a long hair tail."""
    F = frames(r)
    g = -r["root_y"]
    bw, bh, bl = r["body"]
    zc = r["chest_z"] * 1.35
    zh = -bl / 2 + 0.15
    parts = {}

    b = Body(h=0.0055, budget=2200)
    b.add(Ellipsoid(P(0, 0.0, -0.02), (0.128, 0.13, 0.33)), FUR)  # barrel
    b.add(Ellipsoid(P(0, -0.01, zc - 0.12), (0.118, 0.142, 0.15)), FUR, 0.06)  # chest
    b.add(Ellipsoid(P(0, 0.1, zc - 0.1), (0.075, 0.06, 0.12)), FUR, 0.05)  # withers
    for sx in (-1, 1):
        b.add(Ellipsoid(P(sx * 0.094, -0.03, zc - 0.04), (0.05, 0.15, 0.08), rot_x(-0.45)), FUR, 0.05)  # shoulders
        b.add(Ellipsoid(P(sx * 0.082, -0.05, zh - 0.03), (0.076, 0.15, 0.115)), FUR, 0.05)  # haunch
    b.add(Ellipsoid(P(0, 0.035, zh - 0.05), (0.125, 0.12, 0.14)), FUR, 0.06)  # hindquarters
    b.add(Sphere(P(0, 0.0, zh - 0.15), 0.088), FUR, 0.06)  # buttocks
    b.add(Ellipsoid(P(0, 0.08, zc + 0.02), (0.085, 0.09, 0.08)), FUR, 0.05)  # neck root
    parts["spine"] = Part("spine", [b], [P(0, 0.02, zc + 0.15), P(0, 0.02, zh - 0.3)])

    nt = F["neck"][1]
    ht = F["head"][1]
    b = Body(h=0.0045, budget=1200)
    b.add(Chain([(nt + P(0, 0.0, -0.06), 0.088), ((nt + ht) / 2 + P(0, 0.0, -0.03), 0.066), (ht + P(0, -0.02, -0.06), 0.048)]),
          FUR)
    b.add(Cone(nt + P(0, 0.085, -0.09), ht + P(0, 0.03, -0.07), 0.058, 0.034), FUR, 0.05)  # arched crest
    b.add(Cone(P(0, -0.04, zc + 0.06), ht + P(0, -0.06, -0.01), 0.05, 0.032), FUR, 0.05)  # throat
    m = Body(h=0.0035, budget=600)  # mane: a flattened hair crest along the top line
    m.add(Squash(Chain([(P(0, 0, 0), 0.03), (P(0, 0.13, 0.093), 0.03), (P(0, 0.26, 0.185), 0.024)]),
                 nt + P(0, 0.13, -0.1), (0.45, 1.0, 1.0)), ACCENT)
    m.shag(Sphere((nt + ht) / 2 + P(0, 0.08, -0.08), 0.3), 0.01, Tuft(50, (0, -1, -0.3), seed=51), soft=0.05)
    parts["neck"] = Part("neck", [b, m], [ht, nt + P(0, -0.04, -0.06)])

    b = Body(h=0.0032, budget=1500)
    HR = rot_x(0.6)
    c = lambda x, y, z: ht + HR @ P(x, y, z)  # noqa: E731
    b.add(Ellipsoid(c(0, 0.01, 0.0), (0.058, 0.055, 0.07), HR), FUR)  # cranium
    b.add(Squash(Cone(P(0, 0, 0), P(0, -0.035, 0.18), 0.05, 0.034), c(0, 0.0, 0.04), (0.8, 1.1, 1.0), HR), FUR, 0.03)
    b.add(Ellipsoid(c(0, -0.04, 0.225), (0.038, 0.042, 0.04), HR), FUR, 0.03)  # muzzle
    for sx in (-1, 1):
        b.add(Ellipsoid(c(sx * 0.032, -0.04, 0.03), (0.026, 0.05, 0.05), HR), FUR, 0.03)  # jowl
        b.sub(Squash(Sphere(P(0, 0, 0), 0.008), c(sx * 0.02, -0.03, 0.262), (0.7, 1.2, 0.8), HR), SKIN, 0.003)  # nostril
        e = c(sx * 0.05, 0.02, 0.05)
        b.sub(Sphere(e + P(sx * 0.005, 0, 0), 0.012), FUR, 0.006)
        b.add(Squash(Sphere(P(0, 0, 0), 0.012), e, (0.8, 0.85, 1.1), HR @ rot_y(sx * 0.5)), EYE)
    b.add(Cone(c(-0.03, -0.068, 0.2), c(0.03, -0.068, 0.2), 0.006), SKIN, 0.003)  # mouth line
    e = Body(h=0.0024, budget=300)
    for sx in (-1, 1):
        base = c(sx * 0.03, 0.055, -0.03)
        R = rot_x(-0.6 * 0.6) @ rot_z(-sx * 0.2) @ rot_y(sx * -0.3)
        e.add(Squash(Cone(P(0, 0, 0), P(0, 0.065, 0.0), 0.02, 0.004), base, (0.45, 1.0, 1.0), R @ rot_y(math.pi / 2)), FUR)
        e.sub(Squash(Cone(P(0, 0.006, 0), P(0, 0.06, 0.0), 0.015, 0.003), base + R @ P(0, 0, 0.006), (0.32, 1.0, 1.0),
                     R @ rot_y(math.pi / 2)), FUR, 0.002)
    e.add(Squash(Sphere(P(0, 0, 0), 0.03), c(0, 0.055, 0.03), (0.6, 0.5, 1.0), HR), ACCENT, 0.01)  # forelock
    parts["head"] = Part("head", [b, e], [c(0, 0, 0.27), c(0, 0, -0.08)])

    tt = F["tail"][1]
    b = Body(h=0.004, budget=700)
    b.add(Cone(tt, tt + P(0, -0.03, -0.07), 0.032, 0.026), FUR)  # dock
    b.add(Chain([(tt + P(0, -0.01, -0.055), 0.03), (tt + P(0, -0.15, -0.12), 0.048), (tt + P(0, -0.34, -0.13), 0.044),
                 (tt + P(0, -0.48, -0.11), 0.022)]), ACCENT, 0.02)
    b.shag(Sphere(tt + P(0, -0.3, -0.12), 0.25), 0.012, Tuft(45, (0, -1, -0.1), seed=52), soft=0.03)
    parts["tail"] = Part("tail", [b], [tt, tt + P(0, -0.2, -0.13), tt + P(0, -0.5, -0.11)])

    def fore(b, J, W):
        b.add(Cone(J + P(0.0, 0.02, 0.005), J + P(-0.002, -0.12, -0.02), 0.036, 0.031), FUR)  # upper arm
        b.add(Sphere(J + P(-0.008, -0.135, -0.045), 0.02), FUR, 0.012)  # elbow
        b.add(Chain([(J + P(-0.008, -0.12, -0.02), 0.033), (J + P(-0.004, -0.25, -0.002), 0.023), (W, 0.0195)]), FUR, 0.015)
        b.add(Ellipsoid(J + P(-0.004, -0.18, 0.004), (0.026, 0.06, 0.03)), FUR, 0.015)  # forearm muscle
        b.add(Ellipsoid(W + P(0, 0.008, 0.004), (0.021, 0.025, 0.023)), FUR, 0.008)  # knee

    def hind(b, H, K):
        lu = r["lu"]
        b.add(Sphere(H + P(0.0, 0.01, -0.01), 0.05), FUR)
        b.add(Ellipsoid(H + P(0.0, -0.07, 0.0), (0.043, 0.11, 0.08), rot_x(-0.3)), FUR, 0.04)  # thigh
        b.add(Sphere(H + P(-0.004, -lu * 0.45, 0.048), 0.032), FUR, 0.03)  # stifle
        b.add(Chain([(H + P(-0.004, -lu * 0.44, 0.034), 0.038), (H + P(0, -lu * 0.78, -0.03), 0.024), (K, 0.0195)]), FUR, 0.03)
        b.add(Cone(H + P(0, -lu * 0.6, -0.05), K + P(0, 0.008, -0.03), 0.013, 0.012), FUR, 0.012)
        b.add(Sphere(K + P(0, 0.004, -0.028), 0.0145), FUR, 0.008)  # point of hock

    ungulate_leg(parts, F, r, g, True, fore, (0.0195, 0.0158, 0.0195, 0.078, 0.016, 0.018), lambda o: hoof_solid(o, 1.0),
                 tuck=-0.022)
    ungulate_leg(parts, F, r, g, False, hind, (0.0195, 0.0158, 0.0195, 0.078, 0.016, 0.014), lambda o: hoof_solid(o, 0.97),
                 tuck=-0.02)
    return parts


def camel(name, r):
    """Dromedary: one big hump, deep chest, long neck curving forward-down then up to a small
    head with droopy lips, long thin legs with knobby knees, broad padded feet."""
    F = frames(r)
    g = -r["root_y"]
    bw, bh, bl = r["body"]
    zc = r["chest_z"] * 1.35
    zh = -bl / 2 + 0.15
    parts = {}

    b = Body(h=0.0055, budget=2200)
    b.add(Ellipsoid(P(0, 0.0, -0.02), (0.115, 0.115, 0.32)), FUR)  # barrel
    b.add(Ellipsoid(P(0, -0.02, zc - 0.12), (0.1, 0.135, 0.14)), FUR, 0.06)  # chest
    b.add(Ellipsoid(P(0, -0.14, zc - 0.1), (0.04, 0.03, 0.05)), FUR, 0.04)  # chest pad
    b.add(Ellipsoid(P(0, 0.15, -0.04), (0.092, 0.15, 0.22)), FUR, 0.13)  # hump
    b.add(Ellipsoid(P(0, 0.025, zh - 0.05), (0.1, 0.105, 0.13)), FUR, 0.06)  # hindquarters
    for sx in (-1, 1):
        b.add(Ellipsoid(P(sx * 0.07, -0.04, zh - 0.03), (0.055, 0.13, 0.09)), FUR, 0.05)  # haunch
        b.add(Ellipsoid(P(sx * 0.072, -0.03, zc - 0.05), (0.04, 0.13, 0.07), rot_x(-0.4)), FUR, 0.05)  # shoulder
    b.add(Ellipsoid(P(0, 0.06, zc + 0.02), (0.07, 0.085, 0.08)), FUR, 0.06)  # neck root
    b.shag(Ellipsoid(P(0, 0.3, -0.04), (0.1, 0.06, 0.15)), 0.008, Tuft(40, (0, -0.4, -1), seed=61), soft=0.04)
    parts["spine"] = Part("spine", [b], [P(0, 0.02, zc + 0.15), P(0, 0.02, zh - 0.3)])

    nt = F["neck"][1]
    ht = F["head"][1]
    b = Body(h=0.0042, budget=1200)
    knots = [(nt + P(0, 0.02, -0.05), 0.078), (P(0, 0.02, zc + 0.1), 0.056), (P(0, 0.12, zc + 0.215), 0.045),
             (P(0, 0.25, zc + 0.275), 0.039), (ht + P(0, -0.012, -0.03), 0.034)]
    b.add(Chain(knots), FUR)
    b.shag(Chain(knots[1:4]), 0.008, Tuft(45, (0, -1, 0.2), seed=62), soft=0.02)  # shaggy throat
    parts["neck"] = Part("neck", [b], [ht] + [k for k, _ in knots[::-1][1:]])

    b = Body(h=0.003, budget=1300)
    c = lambda x, y, z: ht + P(x, y, z)  # noqa: E731
    b.add(Ellipsoid(c(0, 0.012, 0.0), (0.045, 0.045, 0.055)), FUR)  # cranium
    b.add(Squash(Cone(P(0, 0, 0), P(0, -0.015, 0.12), 0.04, 0.028), c(0, 0.0, 0.03), (0.85, 1.05, 1.0)), FUR, 0.02)
    b.add(Ellipsoid(c(0, -0.03, 0.155), (0.032, 0.034, 0.034)), FUR, 0.02)  # split upper lip
    b.add(Ellipsoid(c(0, -0.058, 0.14), (0.024, 0.018, 0.03)), SKIN, 0.012)  # droopy lower lip
    for sx in (-1, 1):
        b.sub(Squash(Sphere(P(0, 0, 0), 0.007), c(sx * 0.016, -0.012, 0.18), (0.6, 1.3, 0.8), rot_z(sx * 0.5)), SKIN, 0.002)
        e = c(sx * 0.037, 0.02, 0.04)
        b.add(Cone(e + P(-sx * 0.012, 0.012, -0.004), e + P(sx * 0.004, 0.011, 0.008), 0.008, 0.008), FUR, 0.008)  # brow
        b.add(Sphere(e, 0.0105), EYE)
        b.add(Squash(Sphere(P(0, 0, 0), 0.016), c(sx * 0.034, 0.04, -0.03), (0.8, 1.0, 0.5), rot_z(-sx * 0.5)), FUR, 0.006)
    parts["head"] = Part("head", [b], [c(0, 0, 0.19), c(0, 0, -0.06)])

    tt = F["tail"][1]
    b = Body(h=0.0028, budget=260)
    b.add(Chain([(tt, 0.016), (tt + P(0, -0.1, -0.04), 0.012), (tt + P(0, -0.2, -0.045), 0.01)]), FUR)
    b.add(Ellipsoid(tt + P(0, -0.25, -0.045), (0.016, 0.05, 0.014)), FUR, 0.01)  # tuft
    parts["tail"] = Part("tail", [b], [tt, tt + P(0, -0.3, -0.045)])

    def fore(b, J, W):
        b.add(Cone(J + P(0.0, 0.015, 0.005), J + P(-0.002, -0.11, -0.025), 0.03, 0.026), FUR)
        b.add(Sphere(J + P(-0.008, -0.125, -0.04), 0.018), FUR, 0.01)  # elbow callus
        b.add(Chain([(J + P(-0.008, -0.11, -0.02), 0.026), (J + P(-0.004, -0.25, -0.002), 0.018), (W, 0.0165)]), FUR, 0.012)
        b.add(Sphere(W + P(0, 0.004, 0.006), 0.022), FUR, 0.012)  # knobby knee

    def hind(b, H, K):
        lu = r["lu"]
        b.add(Sphere(H + P(0.0, 0.01, -0.006), 0.036), FUR)
        b.add(Ellipsoid(H + P(0.0, -0.07, 0.0), (0.031, 0.09, 0.056), rot_x(-0.3)), FUR, 0.03)
        b.add(Sphere(H + P(-0.002, -lu * 0.42, 0.034), 0.024), FUR, 0.02)
        b.add(Chain([(H + P(-0.002, -lu * 0.41, 0.024), 0.026), (H + P(0, -lu * 0.78, -0.026), 0.017), (K, 0.0165)]), FUR, 0.02)
        b.add(Sphere(K + P(0, 0.003, -0.022), 0.0125), FUR, 0.008)

    ungulate_leg(parts, F, r, g, True, fore, (0.0165, 0.0135, 0.019, 0.075, 0.016, 0.02), lambda o: camel_foot(o, 1.0),
                 tuck=-0.02)
    ungulate_leg(parts, F, r, g, False, hind, (0.0165, 0.0135, 0.019, 0.075, 0.016, 0.016), lambda o: camel_foot(o, 0.95),
                 tuck=-0.018)
    return parts


# ───────────────────────────────────────────────────────────────── coats (tone 0.5 = base coat)
def wolf_coat(F, r):
    """Grey wolf: grizzled agouti body, dark saddle + dorsal line, cream belly / bib / cheeks /
    throat / inner legs, tan legs with a dark stripe down the forelegs, tan ear backs, dark ear
    rims, black tail tip and gland spot, pale tail underside."""
    bh = r["body"][1]
    ht = F["head"][1]
    tt = F["tail"][1]
    zc = r["chest_z"] * 1.35

    def base(p, n, part):
        y, z = p[:, 1], p[:, 2]
        tone = np.full(len(p), 0.5)
        tint = np.zeros(len(p))
        if part in LEGS:
            tint = 0.8 * smoothstep(-0.1, -0.24, y)
            tone += 0.32 * smoothstep(0.1, -0.7, n[:, 0])  # inner side (left leg: -X)
            tone += 0.12 * smoothstep(-0.05, -0.2, y)
            tone += 0.25 * smoothstep(0.0, -0.8, n[:, 1]) * smoothstep(-0.02, -0.1, y)  # under the thigh
            if part == "leg_upper":
                tone -= 0.32 * smoothstep(0.55, 0.95, n[:, 2]) * smoothstep(-0.17, -0.25, y)
            return tone, tint
        if part == "tail":
            tone += 0.32 * smoothstep(0.1, 0.8, n[:, 2]) - 0.12 * smoothstep(0.0, -0.8, n[:, 2])
            return tone, tint
        torso = smoothstep(-0.45, -0.3, z) * (1 - smoothstep(zc + 0.04, zc + 0.16, z))
        tone -= 0.38 * smoothstep(-0.15, 0.7, n[:, 1]) * smoothstep(-0.03, 0.07, y) * torso  # saddle
        tone -= 0.08 * smoothstep(0.0, 0.07, y) * torso
        tone += 0.42 * smoothstep(0.05, -0.7, n[:, 1]) * smoothstep(0.08, -0.12, y)  # belly
        tone += 0.12 * smoothstep(-0.06, -0.16, y)
        return tone, tint

    c = Coat(base)
    c.tone(Ellipsoid(ht + P(0, -0.045, 0.04), (0.06, 0.035, 0.09)), 0.95, soft=0.03)  # throat / lower jaw
    for sx in (-1, 1):
        c.tone(Ellipsoid(ht + P(sx * 0.047, -0.022, 0.03), (0.03, 0.03, 0.05)), 0.9, soft=0.02)  # cheeks
        c.tone(Ellipsoid(ht + P(sx * 0.03, 0.027, 0.078), (0.016, 0.009, 0.018)), 0.86, soft=0.008)  # brow spot
        c.tone(Ellipsoid(ht + P(sx * 0.033, 0.0, 0.085), (0.014, 0.01, 0.02)), 0.82, soft=0.008)  # under the eye
    c.tint(Cone(ht + P(0, 0.02, 0.07), ht + P(0, 0.0, 0.2), 0.034, 0.022), 0.55, soft=0.02)  # tan muzzle
    c.tone(Cone(ht + P(0, 0.027, 0.08), ht + P(0, 0.01, 0.19), 0.012, 0.01), 0.36, soft=0.012)  # darker bridge
    c.tint(Sphere(ht + P(0, 0.08, -0.02), 0.075), 0.55, soft=0.02)  # tan ear backs
    c.tone(Sphere(ht + P(0, 0.13, -0.02), 0.06), 0.25, soft=0.025, k=0.7)  # dark ear tips
    c.tone(Ellipsoid(P(0, -0.06, zc + 0.05), (0.05, 0.1, 0.05)), 0.92, soft=0.04)  # bib
    c.tone(Ellipsoid(P(0, bh * 0.32, 0.0), (0.035, 0.045, 0.34)), 0.1, soft=0.03, k=0.8)  # dorsal stripe
    c.tone(Cone(tt + P(0, 0.025, -0.03), tt + P(0, -0.03, -0.1), 0.04, 0.035), 0.12, soft=0.02)  # gland spot
    c.tone(Sphere(tt + P(0, -0.34, -0.145), 0.065), 0.06, soft=0.03)  # black tail tip
    return c


def dog_coat(F, r):
    """German-shepherd-like: tan with a black saddle (back, neck top, tail top), black mask and
    ears, pale chest / belly / inner legs."""
    ht = F["head"][1]
    tt = F["tail"][1]
    zc = r["chest_z"] * 1.35

    def base(p, n, part):
        y, z = p[:, 1], p[:, 2]
        tone = np.full(len(p), 0.55)
        tint = np.zeros(len(p))
        if part in LEGS:
            tone += 0.2 * smoothstep(0.1, -0.7, n[:, 0]) + 0.05
            tint = 0.35 * smoothstep(-0.1, -0.25, y)
            return tone, tint
        if part == "tail":
            tone -= 0.45 * smoothstep(-0.4, 0.6, -n[:, 2] + n[:, 1])
            return tone, tint
        torso = smoothstep(-0.4, -0.3, z) * (1 - smoothstep(zc - 0.05, zc + 0.08, z))
        tone -= 0.52 * smoothstep(-0.25, 0.45, n[:, 1]) * smoothstep(-0.05, 0.04, y) * torso  # saddle
        tone += 0.28 * smoothstep(0.0, -0.7, n[:, 1]) * smoothstep(0.05, -0.12, y)
        return tone, tint

    c = Coat(base)
    c.tone(Cone(ht + P(0, 0.0, 0.07), ht + P(0, -0.01, 0.2), 0.046, 0.03), 0.08, soft=0.02)  # black muzzle
    c.tone(Sphere(ht + P(0, 0.12, -0.01), 0.08), 0.1, soft=0.02, k=0.85)  # dark ears
    c.tone(Ellipsoid(ht + P(0, -0.05, 0.05), (0.05, 0.03, 0.06)), 0.72, soft=0.02)  # light chin
    c.tone(Ellipsoid(P(0, -0.04, zc + 0.04), (0.05, 0.1, 0.05)), 0.75, soft=0.04)  # chest
    return c


def bear_coat(F, r):
    """Brown bear: chocolate body with grizzled lighter tips over the hump and back, near-black
    legs and paws, a pale muzzle; ears and crown a touch darker."""
    ht = F["head"][1]

    def base(p, n, part):
        y = p[:, 1]
        tone = np.full(len(p), 0.5)
        tint = np.zeros(len(p))
        if part in LEGS:
            tone = 0.16 + 0.2 * smoothstep(-0.3, -0.12, y) + 0.06 * smoothstep(0.0, 0.7, n[:, 1])
            return tone, tint
        tone += 0.18 * smoothstep(0.3, 0.9, n[:, 1]) * smoothstep(0.02, 0.2, y)  # grizzled back
        tone -= 0.22 * smoothstep(-0.12, -0.28, y)  # darker underside / leg roots
        tone -= 0.1 * smoothstep(-0.2, -0.8, n[:, 1])
        return tone, tint

    c = Coat(base)
    c.tint(Cone(ht + P(0, -0.066, 0.18), ht + P(0, -0.072, 0.3), 0.08, 0.06), 0.85, soft=0.03)  # pale muzzle
    for sx in (-1, 1):
        c.tone(Sphere(ht + P(sx * 0.104, 0.085, 0.01), 0.055), 0.3, soft=0.02, k=0.6)  # darker ears
    return c


def deer_coat(F, r):
    """Summer red deer: russet body, dark dorsal line, cream belly / inner legs / throat patch /
    rump patch / tail underside, a pale muzzle band and eye rings, a greyer face and lower legs."""
    ht = F["head"][1]
    tt = F["tail"][1]
    zc = r["chest_z"] * 1.35
    zh = -r["body"][2] / 2 + 0.15
    HR = rot_x(0.3)
    c = lambda x, y, z: ht + HR @ P(x, y, z)  # noqa: E731

    def base(p, n, part):
        y = p[:, 1]
        tone = np.full(len(p), 0.5)
        tint = np.zeros(len(p))
        if part in LEGS:
            tone += 0.36 * smoothstep(0.1, -0.7, n[:, 0])  # pale inner legs
            tone += 0.25 * smoothstep(0.0, -0.8, n[:, 1]) * smoothstep(-0.0, -0.1, y)
            tint = 0.4 * smoothstep(-0.28, -0.42, y)  # greyer lower legs
            return tone, tint
        if part == "tail":
            return 0.45 + 0.5 * smoothstep(-0.2, 0.6, n[:, 2] - n[:, 1] * 0.3), tint
        if part == "head":
            tint = np.full(len(p), 0.55)
        tone -= 0.2 * smoothstep(0.75, 0.97, n[:, 1]) * smoothstep(0.05, 0.1, y)  # dorsal line
        tone += 0.46 * smoothstep(0.0, -0.7, n[:, 1]) * smoothstep(0.04, -0.1, y)  # belly
        return tone, tint

    cz = Coat(base)
    cz.tone(Ellipsoid(P(0, 0.0, zh - 0.16), (0.06, 0.085, 0.06)), 0.95, soft=0.025)  # rump patch
    cz.tone(Ellipsoid(c(0, -0.05, -0.01), (0.035, 0.03, 0.04)), 0.95, soft=0.015)  # throat patch
    cz.tone(Sphere(c(0, -0.012, 0.118), 0.024), 0.92, soft=0.01)  # pale band behind the nose
    cz.tint(Sphere(c(0, -0.012, 0.118), 0.03), 0.0, soft=0.01)
    for sx in (-1, 1):
        cz.tone(Sphere(c(sx * 0.034, 0.016, 0.042), 0.017), 0.88, soft=0.006)  # eye ring
        cz.tint(Sphere(c(sx * 0.034, 0.016, 0.042), 0.02), 0.0, soft=0.006)
    cz.tone(Sphere(c(0, 0.09, -0.03), 0.05), 0.3, soft=0.02, k=0.6)  # darker ear rims
    return cz


def horse_coat(F, r):
    """Bay: red-brown body, black points (legs below the knee / hock), white hind socks and a
    face blaze (tint = white), darker muzzle, lighter belly."""
    ht = F["head"][1]
    HR = rot_x(0.6)
    c = lambda x, y, z: ht + HR @ P(x, y, z)  # noqa: E731
    g = -r["root_y"]

    def base(p, n, part):
        y = p[:, 1]
        tone = np.full(len(p), 0.5)
        tint = np.zeros(len(p))
        if part in LEGS:
            tone = 0.5 - 0.47 * smoothstep(-0.36, -0.46, y)  # black points
            if part.startswith("hind"):
                tint = smoothstep(g + 0.1, g + 0.07, y)  # white socks
            return tone, tint
        tone -= 0.12 * smoothstep(0.6, 0.95, n[:, 1])
        tone += 0.3 * smoothstep(0.0, -0.7, n[:, 1]) * smoothstep(0.0, -0.12, y)
        return tone, tint

    cz = Coat(base)
    cz.tone(Ellipsoid(c(0, -0.04, 0.23), (0.045, 0.05, 0.05), HR), 0.22, soft=0.02)  # dark muzzle
    cz.tint(Cone(c(0, 0.05, 0.03), c(0, 0.018, 0.21), 0.014, 0.01), 1.0, soft=0.006)  # blaze
    return cz


def camel_coat(F, r):
    """Dromedary: sandy coat, darker shaggy hump top and neck crest, paler belly and legs,
    dark knee callosities."""
    W = F["leg_lower"][1] + P(-0.02, 0, 0)  # the camel's (tucked) knee

    def base(p, n, part):
        y = p[:, 1]
        tone = np.full(len(p), 0.5)
        tint = np.zeros(len(p))
        if part in LEGS:
            tone += 0.18 + 0.12 * smoothstep(0.1, -0.7, n[:, 0])
            return tone, tint
        tone -= 0.22 * smoothstep(0.4, 0.95, n[:, 1]) * smoothstep(0.15, 0.3, y)  # hump top
        tone += 0.3 * smoothstep(0.0, -0.7, n[:, 1]) * smoothstep(0.0, -0.12, y)
        if part == "neck":
            tone -= 0.12 * smoothstep(0.0, 0.8, n[:, 1] - n[:, 2])
        return tone, tint

    cz = Coat(base)
    cz.tone(Sphere(W + P(0, 0.006, 0.01), 0.026), 0.2, soft=0.008)  # knee callus
    return cz


# ───────────────────────────────────────────────────────────────── build
def species_parts(name):
    r = RIG[name]
    F = frames(r)
    if name == "wolf":
        opt = dict(scale=1.0, keel=-0.17, shag=1.0, ruff=True, head=1.12, muzzle=0.106, ear=0.08, ear_splay=0.18,
                   leg=1.0, paw=1.0, tail_shag=1.0, tuck=-0.014,
                   tail=[((0, -0.03, -0.075), 0.042), ((0, -0.12, -0.13), 0.05), ((0, -0.22, -0.155), 0.046),
                         ((0, -0.31, -0.15), 0.03), ((0, -0.35, -0.14), 0.012)])
        return canine(name, r, opt), wolf_coat(F, r)
    if name == "dog":
        opt = dict(scale=1.12, keel=-0.15, shag=0.5, ruff=False, head=1.12, muzzle=0.1, ear=0.075, ear_splay=0.12,
                   leg=1.15, paw=1.05, tail_shag=0.8, tuck=-0.022, collar=0.074,
                   tail=[((0, -0.03, -0.065), 0.034), ((0, -0.11, -0.11), 0.038), ((0, -0.2, -0.125), 0.034),
                         ((0, -0.27, -0.105), 0.02), ((0, -0.29, -0.09), 0.01)])
        return canine(name, r, opt), dog_coat(F, r)
    if name == "bear":
        return bear(name, r), bear_coat(F, r)
    if name == "deer":
        return deer(name, r), deer_coat(F, r)
    if name == "horse":
        return horse(name, r), horse_coat(F, r)
    if name == "camel":
        return camel(name, r), camel_coat(F, r)
    raise KeyError(name)


def bl(p):
    """Game (Y up, +Z fwd) -> Blender (Z up) coordinates; export_yup maps it back."""
    return np.stack([p[:, 0], -p[:, 2], p[:, 1]], 1)


DRIFT = Tufts(9, (0, 0, -1), seed=99, n=8, stretch=0.5)
# Global triangle budget scale: ~9k tris per animal (the box-era kit was ~7.2k); the coat reads
# from tone + the fur layer, so the silhouette only needs moderate density.
BUDGET_SCALE = 0.66


def build_object(name, part, frame, animal_sdf, coat):
    R, t = frame
    pieces = []
    for bi, body in enumerate(part.bodies):
        verts, quads = mesh_body(body, R, t)
        me = bpy.data.meshes.new(f"{name}_b{bi}")
        me.from_pydata(bl(verts).tolist(), [], quads.tolist())
        ob = bpy.data.objects.new(f"{name}_b{bi}", me)
        bpy.context.scene.collection.objects.link(ob)
        tris = 2 * len(quads)
        budget = body.budget * BUDGET_SCALE
        if tris > budget:
            m = ob.modifiers.new("dec", "DECIMATE")
            m.ratio = budget / tris
            dg = bpy.context.evaluated_depsgraph_get()
            dme = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
            ob.modifiers.clear()
            ob.data = dme
            bpy.data.meshes.remove(me)
        pieces.append((body, ob))
    # Join bodies into one mesh, remembering which body each face came from.
    verts, faces, owner = [], [], []
    for bi, (body, ob) in enumerate(pieces):
        me = ob.data
        base = len(verts)
        verts += [tuple(v.co) for v in me.vertices]
        for poly in me.polygons:
            faces.append([base + i for i in poly.vertices])
            owner.append(bi)
        bpy.data.objects.remove(ob)
        bpy.data.meshes.remove(me)
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.materials.append(name_material("creature"))
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    for poly in me.polygons:
        poly.use_smooth = True

    # Per-vertex data in the spine frame.
    vb = np.array(verts)
    loc = np.stack([vb[:, 0], vb[:, 2], -vb[:, 1]], 1)  # Blender -> game local
    ps = loc @ R.T + t
    owner = np.array(owner)
    vowner = np.zeros(len(vb), np.int64)
    for fi, f in enumerate(faces):
        vowner[f] = owner[fi]
    nrm = np.zeros_like(ps)
    for bi, (body, _) in enumerate(pieces):
        sel = vowner == bi
        if sel.any():
            g = gradient(body.eval, ps[sel])
            nrm[sel] = g / np.maximum(norm(g), 1e-9)[:, None]
    ao = ambient_occlusion(animal_sdf, ps + nrm * 0.002, nrm, step=0.011, k=1.5)
    ao = 0.5 + 0.5 * ao
    tone, tint = coat(ps, nrm, part.joint)
    # Broad patchy drift (continuous across parts: evaluated in the shared spine frame).
    tone = np.clip(tone + 0.09 * (DRIFT(ps) - 0.5), 0.0, 1.0)
    uu, vv = axis_uv(ps, part.axis, part.up)
    # Face regions at the (projected) face centres.
    cen = np.array([ps[f].mean(0) for f in faces])
    freg = np.zeros(len(faces), np.int64)
    for bi, (body, _) in enumerate(pieces):
        sel = owner == bi
        if sel.any():
            _, rg = body.eval(cen[sel], want_region=True)
            freg[sel] = rg
    cols = []
    uvs = []
    for poly in me.polygons:
        rg = freg[poly.index]
        for li in poly.loop_indices:
            vi = me.loops[li].vertex_index
            cols += [rg / 16.0 + 1.0 / 32.0, ao[vi], tone[vi], tint[vi]]
            uvs += [16.0 + uu[vi] * part.uv_scale, 1.0 - vv[vi] * part.uv_scale]
    me.color_attributes.new("Col", "FLOAT_COLOR", "CORNER")
    me.color_attributes["Col"].data.foreach_set("color", cols)
    me.color_attributes.active_color = me.color_attributes["Col"]
    uvl = me.uv_layers.new(name="UVMap")
    uvl.data.foreach_set("uv", uvs)
    return ob


# Coat length per species: a multiplier on the fur-flow UVs (bigger = finer, shorter hair).
HAIR = {"wolf": 1.0, "bear": 0.85, "dog": 1.25, "deer": 1.8, "horse": 2.4, "camel": 1.5}


def build_species(name):
    parts, coat = species_parts(name)
    for p in parts.values():
        p.uv_scale *= HAIR[name]
    F = frames(RIG[name])
    chains = (("leg_upper", "leg_lower", "paw"), ("hind_upper", "hind_lower", "hind_paw"))

    def ao_field(own):
        """The whole animal's SDF for baking AO into part `own` — the left legs mirrored so the body
        sees both sides — minus `own`'s sibling segments in the same leg: their overlap at the
        joint would ring the leg with a dark band."""
        sib = next((c for c in chains if own in c), ())

        def sdf(q):
            d = np.full(len(q), 1e9)
            for pn, p in parts.items():
                if pn in sib and pn != own:
                    continue
                for b in p.bodies:
                    d = np.minimum(d, b.eval(q))
                    if p.joint in LEGS:
                        d = np.minimum(d, b.eval(q * np.array([-1.0, 1.0, 1.0])))
            return d
        return sdf

    objs = []
    for pname, part in parts.items():
        ob = build_object(f"q_{name}_{pname}", part, F[part.joint], ao_field(pname), coat)
        objs.append(ob)
        print(f"  {ob.name}: {len(ob.data.polygons)} faces")
    return objs


SPECIES = ["wolf", "bear", "dog", "deer", "horse", "camel"]

# Preview-only coat colours (sRGB hex) — the game's coat table in quadruped.rs is the source of truth.
PREVIEW = {
    "wolf": dict(dark=0x2b2722, base=0x7b6f5e, light=0xd9cfbd, tint=0xa47a50, skin=0x1a1614, detail=0x2a2420),
    "dog": dict(dark=0x1c1610, base=0xa5733f, light=0xd8b88a, tint=0xb8844c, skin=0x141010, detail=0x2a2420),
    "bear": dict(dark=0x22170f, base=0x4f3726, light=0x7d5c40, tint=0x9a7a58, skin=0x121010, detail=0xb8ab90),
    "deer": dict(dark=0x4a3322, base=0x8e5c36, light=0xe6dccb, tint=0x6f6152, skin=0x161210, detail=0x2a2420),
    "horse": dict(dark=0x1c1510, base=0x7a4a2a, light=0x9a6a44, tint=0xe2dccf, skin=0x2a2220, detail=0x2a241e),
    "camel": dict(dark=0x8a6a42, base=0xc29f6a, light=0xe2cfa6, tint=0xa98457, skin=0x3a2c22, detail=0x4a3a28),
}


def _lin(hexv):
    c = np.array([(hexv >> 16) & 255, (hexv >> 8) & 255, hexv & 255]) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def preview(objs, png):
    """CPU Cycles render of the rest pose (right legs mirrored), side + 3/4 rows. No GPU."""
    M = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], dtype=np.float64)
    from mathutils import Matrix
    scene = bpy.context.scene
    names = sorted({o.name.split("_")[1] for o in objs}, key=lambda n: SPECIES.index(n) if n in SPECIES else 99)
    for o in objs:
        o.hide_render = True
    x0 = 0.0
    for name in names:
        pal = {k: _lin(v) for k, v in PREVIEW.get(name, PREVIEW["wolf"]).items()}
        F = frames(RIG[name])
        for ob in [o for o in objs if o.name.split("_")[1] == name]:
            pname = ob.name.split("_", 2)[2]
            me = ob.data
            col = np.zeros(len(me.loops) * 4, np.float32)
            me.color_attributes["Col"].data.foreach_get("color", col)
            col = col.reshape(-1, 4)
            rgb = np.zeros((len(col), 3))
            reg = np.floor(col[:, 0] * 16).astype(int)
            t = col[:, 2:3]
            ramp = np.where(t < 0.5, pal["dark"] + (pal["base"] - pal["dark"]) * (t / 0.5),
                            pal["base"] + (pal["light"] - pal["base"]) * ((t - 0.5) / 0.5))
            ramp = ramp + (pal["tint"] - ramp) * col[:, 3:4]
            rgb[:] = ramp
            rgb[reg == SKIN] = pal["skin"]
            rgb[reg == DETAIL] = pal["detail"]
            rgb[reg == EYE] = (0.01, 0.008, 0.006)
            rgb[reg == ACCENT] = (0.02, 0.015, 0.012)
            rgb[reg == HORN] = (0.25, 0.2, 0.14)
            rgb *= col[:, 1:2]
            pc = me.color_attributes.new("prev", "FLOAT_COLOR", "CORNER")
            pc.data.foreach_set("color", np.concatenate([rgb, np.ones((len(rgb), 1))], 1).ravel().astype(np.float32))
            R, t3 = F[pname]
            for row, (yaw, dx) in enumerate(((math.pi / 2, 0.65), (math.pi / 2 - 0.75, 1.95))):
                for side in ((1.0,) if not pname.startswith(("leg", "paw", "hind")) else (1.0, -1.0)):
                    inst = bpy.data.objects.new(f"{ob.name}_p{row}_{side}", me)
                    scene.collection.objects.link(inst)
                    S = np.diag([side, 1.0, 1.0])
                    Rg = rot_y(yaw) @ S @ R
                    tg = rot_y(yaw) @ (S @ t3 + P(0, RIG[name]["root_y"], 0))
                    m4 = np.eye(4)
                    m4[:3, :3] = M @ Rg @ M.T
                    m4[:3, 3] = M @ tg + np.array([x0 + dx, 0.0, 0.0])
                    inst.matrix_world = Matrix(m4.tolist())
                    mat = bpy.data.materials.get("prev_mat")
                    if mat is None:
                        mat = bpy.data.materials.new("prev_mat")
                        mat.use_nodes = True
                        nt = mat.node_tree
                        bsdf = nt.nodes["Principled BSDF"]
                        at = nt.nodes.new("ShaderNodeAttribute")
                        at.attribute_name = "prev"
                        nt.links.new(at.outputs["Color"], bsdf.inputs["Base Color"])
                        bsdf.inputs["Roughness"].default_value = 0.85
                    inst.data.materials.clear()
                    inst.data.materials.append(mat)
        x0 += 2.6
    bpy.ops.mesh.primitive_plane_add(size=40, location=(x0 / 2, 0, 0))
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    scene.collection.objects.link(cam)
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = max(x0 + 0.2, 2.0)
    cam.location = (x0 / 2, -8.0, 0.55)
    cam.rotation_euler = (math.radians(90), 0, 0)
    scene.camera = cam
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 3.5
    sun.rotation_euler = (math.radians(50), math.radians(-20), math.radians(-35))
    scene.collection.objects.link(sun)
    world = bpy.data.worlds.new("w")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.45, 0.5, 0.58, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.8
    scene.world = world
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 24
    ppu = min(560.0, 4200.0 / (x0 + 0.2))  # pixels per unit (keeps a full lineup sane)
    scene.render.resolution_x = int(ppu * (x0 + 0.2))
    scene.render.resolution_y = int(ppu * 1.6)
    scene.view_settings.view_transform = "AgX"
    scene.render.filepath = str(png)
    bpy.ops.render.render(write_still=True)
    print(f"PREVIEW {png}")


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    pngs = [a for a in argv if a.endswith(".png")]
    only = [a for a in argv if not a.endswith(".png")]
    clear_scene()
    objs = []
    for name in (only or SPECIES):
        objs += build_species(name)
        print(f"{name}: done")
    if not pngs or os.environ.get("ANIMALS_EXPORT"):
        export_glb(OUT / "animals.glb", objs, tangents=False)
    if pngs:
        preview(objs, Path(pngs[0]).resolve())
    print("ANIMALS_DONE")
