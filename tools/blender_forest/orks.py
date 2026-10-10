"""Organic ORK bodies for the shared biped rig -> orks.glb (GPU-skinned warband).

Round 3 of the orks. Round 2 (`creatures.py`) built one metaball mass per rig joint: every joint
was a separate peg, metaballs ballooned wherever they overlapped (knots at the elbows, a pelvis +
belt + thigh-cloth stack wider than the chest — the "huge behind"), and the rig spread the legs and
arms as wide as a cartoon brute. Here an ork is ONE skinned mesh on the same biped joints, built with
the townsfolk's signed-distance tools (`people.py` / `sdfkit.py`): tapered round-cone chains and
smooth unions for the muscle groups, so a heavy, believable humanoid comes out — broad shoulders and
chest, thick traps and neck, a narrow pelvis, anatomical thighs and calves — and the limbs bend at
the joints instead of reading as pegs.

FRAMES are the townsfolk's (see people.py): body pieces in the RIG's rest space (Y up, +Z forward,
joints at their `spawn_biped` rest offsets), head pieces in the HEAD joint's frame (unscaled — orks
use head scale 1). Two builds set the rig spans the game spawns with (`orks::rig_dims`):
heavy (grunt, berserker) and lean (scout, shaman). The neck belongs to the TRUNK and rises into the
skull, its top weighted to the head, so turning the head never opens a collar seam.

BAKED DATA (the game decodes it in `orks::kit_ork_meshes`)
  vertex colour  R = region / 16 + 1/32 (palette slot, order below; props share slots 0-9)
                 G = cavity / ambient occlusion (from the whole body's SDF)
                 B = TONE, 0.5 neutral: lower = darker / ruddier (knuckles, elbows, knees, ears, the
                     back), higher = paler (belly, inner arms); for leather / cloth: wear and grime
                 A = GLOSS: 0 dry and matte (elbows, knees, knuckles, scuffed leather) .. 1 oily
                     (brow, nose, cheekbones, chest, scars, polished leather)
  UV0, UV1       skin weights, people.py's encoding (joint + 0.005 + weight * 0.98, 4 influences)

    blender -b --factory-startup --python tools/blender_forest/orks.py [-- "out.png|pose|yaw|cx,cz,width|variants" ...]
    pose = rest | idle | walk | smash; variants = '+'-separated subset of grunt, scout, berserker, shaman.
    ORKS_ONLY=prefix,... builds a subset (no export), ORKS_NO_EXPORT=1 skips the glb, ORKS_DRAFT=1.6
    coarsens the meshing grids for quick previews.
"""
import math
import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from common import OUT, clear_scene, export_glb  # noqa: E402
from people import (  # noqa: E402
    BIG, CappedCone, Fn, Folds, P, PBody, Piece, bl, build_piece, euler, gm, half, hit, layer, offset, ring,
    slab, ss, surface_ring,
)
from sdfkit import (  # noqa: E402
    Chain, Cone, Ellipsoid, RBox, Sphere, Squash, Tufts, norm, rot_x, rot_y, rot_z, to_surface, v3,
)

# Region codes (<= 16). Slots 0-9 are the old creatures.glb order (the props still use them);
# keep in sync with `orks::kit_ork_meshes`' palette.
(SKIN, DARK, BELLY, LEATHER, CLOTH, BONE, HAIR, WOOD, IRON, ORB, EYE, PAINT, SCAR, FUR, NAIL,
 STRAP) = range(16)

JOINTS = ("hips", "torso", "neck", "head", "sh_l", "el_l", "sh_r", "el_r", "hip_l", "knee_l", "foot_l",
          "hip_r", "knee_r", "foot_r")
HIPS, TORSO, NECK, HEAD, SH_L, EL_L, SH_R, EL_R, HIP_L, KNEE_L, FOOT_L, HIP_R, KNEE_R, FOOT_R = range(14)
HEAD_Y = 1.63
SOLE_Y = 0.05  # bare / wrapped soles (`orks::ORK_RIG_OFF` drops them onto the ground)

# Rig spans per build (`orks::rig_dims`): shoulder / hip joint half-spans and a trunk width factor.
BUILDS = {"heavy": dict(sdx=0.25, hdx=0.11, w=1.0), "lean": dict(sdx=0.222, hdx=0.1, w=0.87)}
VARIANTS = ("grunt", "scout", "berserker", "shaman")
BUILD_OF = {"grunt": "heavy", "berserker": "heavy", "scout": "lean", "shaman": "lean"}
# Trunk shape per variant: gut, abdominal definition, chest mass, lat flare, sag (age), ribs.
TRUNKS = {
    "grunt": dict(gut=1.0, abs=0.35, chest=1.0, lat=1.0, sag=0.0, ribs=0.0),
    "berserker": dict(gut=0.15, abs=1.0, chest=1.08, lat=1.12, sag=0.0, ribs=0.0),
    "scout": dict(gut=0.0, abs=0.75, chest=0.9, lat=0.95, sag=0.0, ribs=0.35, wmul=0.97),
    "shaman": dict(gut=0.45, abs=0.0, chest=0.82, lat=0.85, sag=1.0, ribs=0.7, wmul=0.9),
}


class Ref(Fn):
    """An SDF callable with bounds that also reads as a Body (`eval`), for `offset` / `layer`."""

    def eval(self, p, want_region=False):
        return self.fn(p)


def mottle(p, freq, seed, n=8):
    """Smooth band-limited noise in about -1..1 (sum of random plane waves)."""
    rng = np.random.default_rng(seed)
    k = rng.normal(size=(n, 3))
    k = k / np.linalg.norm(k, axis=1, keepdims=True) * freq * rng.uniform(0.7, 1.3, (n, 1))
    ph = rng.uniform(0, 2 * math.pi, n)
    return np.sin(p @ k.T + ph).sum(1) / math.sqrt(n / 2)


def blob(p, c, r):
    """Gaussian falloff around `c` (radius ~r)."""
    d2 = ((p - v3(c)) ** 2).sum(1)
    return np.exp(-d2 / (r * r))


# ───────────────────────────────────────────────────────────────── skin weights
def weights_for(build):
    sdx = BUILDS[build]["sdx"]

    def fn(p, kind):
        x, y = p[:, 0], p[:, 1]
        W = np.zeros((len(p), len(JOINTS)))
        if kind == "trunk":
            t = ss(1.12, 1.27, y)  # hips -> torso (torso joint 1.2)
            hd = ss(1.535, 1.6, y)  # neck -> head: the neck's top rides the skull
            leg = ss(1.05, 0.93, y)  # hips -> thighs below the hip joints (1.0)
            sr = ss(-0.06, 0.06, x)
            arm_l = ss(1.5, 1.4, y) * ss(sdx - 0.08, sdx - 0.02, -x)  # the shoulder cap rides the arm
            arm_r = ss(1.5, 1.4, y) * ss(sdx - 0.08, sdx - 0.02, x)
            kw = ss(0.68, 0.58, y)  # a long hem round the knee follows the shin a little
            W[:, HIPS] = (1 - t) * (1 - leg)
            W[:, HIP_L] = (1 - t) * leg * (1 - sr) * (1 - kw)
            W[:, HIP_R] = (1 - t) * leg * sr * (1 - kw)
            W[:, KNEE_L] = (1 - t) * leg * (1 - sr) * kw
            W[:, KNEE_R] = (1 - t) * leg * sr * kw
            up = t * (1 - hd)
            W[:, TORSO] = up * (1 - arm_l - arm_r)
            W[:, SH_L] = up * arm_l
            W[:, SH_R] = up * arm_r
            W[:, HEAD] = t * hd
        elif kind in ("arm_l", "arm_r"):
            sh, el = (SH_L, EL_L) if kind == "arm_l" else (SH_R, EL_R)
            up = ss(1.52, 1.41, y)  # torso -> upper arm round the shoulder pivot (1.47)
            fo = ss(1.215, 1.13, y)  # upper arm -> forearm round the elbow (1.17)
            W[:, TORSO] = 1 - up
            W[:, sh] = up * (1 - fo)
            W[:, el] = up * fo
        elif kind in ("leg_l", "leg_r"):
            hp, kn, ft = (HIP_L, KNEE_L, FOOT_L) if kind == "leg_l" else (HIP_R, KNEE_R, FOOT_R)
            th = ss(1.05, 0.93, y)
            kw = ss(0.645, 0.56, y)  # thigh -> shin (knee 0.6)
            fw = ss(0.2, 0.12, y)  # shin -> foot (ankle 0.15)
            W[:, HIPS] = 1 - th
            W[:, hp] = th * (1 - kw)
            W[:, kn] = kw * (1 - fw)
            W[:, ft] = fw
        elif kind == "head":
            hw = ss(-0.135, -0.095, y)  # head-local: only what hangs below the jaw follows the trunk
            W[:, HEAD] = hw
            W[:, TORSO] = 1 - hw
        else:
            raise KeyError(kind)
        return W
    return fn


# ───────────────────────────────────────────────────────────────── trunks
_TRUNKS = {}


def trunk_body(variant):
    """The bare trunk: pelvis, waist, ribcage, pecs, lats, shoulder blades, traps, neck."""
    if variant in _TRUNKS:
        return _TRUNKS[variant]
    t = TRUNKS[variant]
    bd = BUILDS[BUILD_OF[variant]]
    w, sdx = bd["w"] * t.get("wmul", 1.0), bd["sdx"]
    d = 0.5 + 0.5 * w  # depth follows width only half as much (a lean ork is still deep-chested)
    b = PBody(h=0.0042, budget=1150)
    S = SKIN
    # Pelvis: narrow (well inside the shoulders), the seat modest.
    b.add(Ellipsoid(P(0, 0.995, -0.014), (0.126 * w, 0.094, 0.092 * d)), S)
    for sx in (-1, 1):
        b.add(Ellipsoid(P(sx * 0.058 * w, 0.966, -0.058 * d), (0.062 * w, 0.07, 0.044 * d)), S, 0.03)  # glutes
        b.add(Ellipsoid(P(sx * 0.115 * w, 1.07, 0.004), (0.036 * w, 0.062, 0.066 * d)), S, 0.04)  # obliques over the crest
    b.add(Ellipsoid(P(0, 1.14, 0.002), (0.134 * w, 0.11, 0.098 * d)), S, 0.05)  # waist
    if t["gut"] > 0:
        g = t["gut"]
        b.add(Ellipsoid(P(0, 1.1, 0.036 + 0.02 * g), (0.108 * w, 0.082 + 0.012 * g, 0.05 + 0.03 * g)), S, 0.04)
    # Ribcage: narrow at the floating ribs, widest and deepest under the armpits (the V).
    b.add(Ellipsoid(P(0, 1.262, -0.008), (0.148 * w, 0.11, 0.104 * d)), S, 0.05)
    b.add(Ellipsoid(P(0, 1.39, -0.02), (0.176 * w, 0.112, 0.106 * d)), S, 0.05)
    # Shoulder girdle: collar bones + the top of the traps as one bar out to the deltoids, so the
    # shoulder line is level and broad instead of a coat-hanger slope.
    b.add(Cone(P(-(sdx - 0.05), 1.474, -0.022), P(sdx - 0.05, 1.474, -0.022), 0.066 * d), S, 0.05)
    ch = t["chest"]
    sag = t["sag"]
    for sx in (-1, 1):
        # Pectorals: broad flat plates from the sternum to the armpit, the lower edge crisp.
        b.add(Ellipsoid(P(sx * 0.09 * w, 1.405 - 0.025 * sag, 0.074 * d),
                        (0.098 * w * ch, (0.066 + 0.012 * sag) * ch, 0.036 * d * ch), rot_z(sx * (0.3 + 0.12 * sag))), S, 0.022)
        b.add(Ellipsoid(P(sx * (sdx - 0.065), 1.445, 0.032), (0.04, 0.05, 0.036)), S, 0.03)  # pec -> deltoid tie-in
        b.add(Ellipsoid(P(sx * 0.152 * w, 1.31, -0.042 * d), (0.05 * w * t["lat"], 0.135, 0.072 * d), rot_z(-sx * 0.22)),
              S, 0.045)  # lats: the flare from armpit to waist
        b.add(Ellipsoid(P(sx * 0.085 * w, 1.39, -0.094 * d), (0.072 * w, 0.088, 0.034 * d), rot_z(sx * 0.15)), S, 0.03)  # scapulae
        b.add(Ellipsoid(P(sx * 0.03 * w, 1.17, -0.084 * d), (0.028 * w, 0.14, 0.03 * d)), S, 0.03)  # spinal erectors
        # Trapezius: a thick mound from high on the neck out to the shoulder (the brute's "no neck").
        b.add(Cone(P(sx * 0.035 * w, 1.6, -0.036), P(sx * (sdx - 0.055), 1.5, -0.024), 0.058 * d, 0.05), S, 0.05)
        b.add(Sphere(P(sx * (sdx - 0.035), 1.462, -0.002), 0.056 * (0.5 + 0.5 * w)), S, 0.04)  # deltoid root
        b.add(Cone(P(sx * 0.022, 1.535, 0.052 * d), P(sx * (sdx - 0.07), 1.522, 0.026), 0.011, 0.013), S, 0.018)  # clavicles
        b.add(Ellipsoid(P(sx * 0.135 * w, 1.24, 0.04 * d), (0.026 * w, 0.065, 0.036 * d), rot_z(sx * 0.4)), S, 0.03)  # serratus
    b.add(Ellipsoid(P(0, 1.45, -0.078 * d), (0.085 * w, 0.13, 0.04 * d)), S, 0.04)  # mid traps between the blades
    # Neck: thick, into the skull (its top weighted to the head).
    b.add(Cone(P(0, 1.47, -0.014), P(0, 1.67, -0.032), 0.088 * d, 0.07 * d), S, 0.035)
    for sx in (-1, 1):  # sternocleidomastoids, mastoid -> sternum
        b.add(Cone(P(sx * 0.052 * d, 1.645, -0.024), P(sx * 0.016, 1.535, 0.06 * d), 0.017, 0.016), S, 0.02)
    # Abdominal wall: six blocks either side of the midline, the navel, the groove of the linea alba.
    if t["abs"] > 0:
        a = t["abs"]
        fn = b.eval
        for row, y in enumerate((1.238, 1.178, 1.12)):
            for sx in (-1, 1):
                q = hit(fn, [[sx * 0.034 * w, y, 0.3]], [[0, 0, -1]])[0]
                b.add(Ellipsoid(P(q[0], y, q[2] - 0.014), (0.03 * w, 0.025, 0.02)), S, 0.014 + 0.01 * (1 - a))
        q = hit(b.eval, [[0, 1.17, 0.3]], [[0, 0, -1]])[0]
        b.sub(Ellipsoid(P(0, 1.17, q[2] + 0.004), (0.006, 0.09, 0.008)), S, 0.006)
    q = hit(b.eval, [[0, 1.072, 0.3]], [[0, 0, -1]])[0]
    b.sub(Ellipsoid(P(0, 1.072, q[2] + 0.002), (0.007, 0.009, 0.008)), S, 0.004)  # navel
    q = hit(b.eval, [[0, 1.26, -0.3]], [[0, 0, 1]])[0]
    b.sub(Ellipsoid(P(0, 1.26, q[2] - 0.003), (0.007, 0.2, 0.01)), S, 0.012)  # the spine's furrow
    if t["ribs"] > 0:  # a lean / old ork shows the lower ribs on the flanks
        for i in range(3):
            y = 1.3 - i * 0.04
            for sx in (-1, 1):
                q = hit(b.eval, [[sx * 0.3, y, 0.02]], [[-sx, 0, 0]])[0]
                b.add(Cone(P(q[0] - sx * 0.006, y + 0.012, q[2] + 0.05), P(q[0] - sx * 0.008, y - 0.016, q[2] - 0.03),
                           0.005 * t["ribs"] + 0.002, 0.005 * t["ribs"] + 0.002), S, 0.01)
    for sx in (-1, 1):  # nipples
        q = hit(b.eval, [[sx * 0.09 * w, 1.345 - 0.03 * sag, 0.3]], [[0, 0, -1]])[0]
        b.add(Sphere(P(q[0], q[1], q[2] - 0.004), 0.008), DARK, 0.004)
    # The pelvis floor is closed by the thighs + the loincloth; trim what would poke below it.
    b.cut(half(P(0, 0.88, 0), (0, 1, 0)), 0.02)
    _TRUNKS[variant] = b
    return b


def trunk_tone(p, n, reg, variant, seed):
    """Tone 0.5 neutral: mottling, a darker back and shoulders, a paler belly and chest."""
    tn = 0.5 + 0.09 * mottle(p, 9.0, seed) + 0.04 * mottle(p, 26.0, seed + 1)
    tn -= 0.1 * ss(0.0, -0.08, p[:, 2]) * ss(1.1, 1.45, p[:, 1])  # back + top of the shoulders
    tn += 0.12 * ss(0.03, 0.1, p[:, 2]) * ss(1.3, 1.1, p[:, 1]) * ss(0.13, 0.05, np.abs(p[:, 0]))  # belly
    tn -= 0.12 * ss(1.5, 1.6, p[:, 1])  # weathered neck
    if variant == "shaman":
        tn += 0.05 * mottle(p, 40.0, seed + 2)  # liver spots
    return np.where(reg == SKIN, tn, np.where(reg == SCAR, 0.62, 0.5))


def trunk_gloss(p, n, reg):
    g = 0.35 + 0.35 * ss(1.3, 1.45, p[:, 1]) * ss(0.0, 0.05, p[:, 2])  # sweaty chest
    g += 0.3 * ss(1.4, 1.52, p[:, 1]) * ss(0.12, 0.2, np.abs(p[:, 0]))  # shoulder tops catch the light
    g += 0.15 * mottle(p, 14.0, 77)
    return np.where(reg == SCAR, 0.9, g)


# Scars: (variant) -> list of polylines on the trunk (projected onto the surface; raised keloid).
TRUNK_SCARS = {
    "grunt": [[(0.13, 1.42, 0.3), (0.03, 1.33, 0.3), (-0.08, 1.24, 0.3)]],
    "berserker": [[(0.15, 1.44, 0.3), (0.05, 1.36, 0.3), (-0.06, 1.29, 0.3), (-0.12, 1.24, 0.3)],
                  [(-0.13, 1.42, 0.3), (-0.05, 1.4, 0.3)],
                  [(0.1, 1.2, 0.3), (0.13, 1.12, 0.3)],
                  [(-0.1, 1.38, -0.3), (0.06, 1.28, -0.3)]],
    "scout": [[(-0.12, 1.16, 0.3), (-0.05, 1.12, 0.3)]],
    "shaman": [],
}


def add_scars(b, lines, r=0.0042):
    for line in lines:
        pts = np.array(line, dtype=float)
        # Each knot is cast onto the body along Z (front or back by its sign).
        pts_s = []
        for x, y, z in pts:
            q = hit(b.eval, [[x, y, z]], [[0, 0, -math.copysign(1.0, z)]], t1=0.4)[0]
            pts_s.append(q)
        pts_s = np.array(pts_s)
        dense = np.concatenate([np.linspace(pts_s[i], pts_s[i + 1], 8, endpoint=False) for i in range(len(pts_s) - 1)]
                               + [pts_s[-1:]])
        dense = to_surface(b, dense, inset=0.0012)
        rr = r * (0.55 + 0.45 * np.sin(np.linspace(0, math.pi, len(dense))))
        b.add(Chain([(P(*q), max(rad, 0.0015)) for q, rad in zip(dense, rr)]), SCAR, 0.003)


def paint_trunk(variant):
    """War paint as face regions (no relief): returns fn(face_centres, regions) -> regions."""
    def fn(cen, reg):
        x, y, z = cen[:, 0], cen[:, 1], cen[:, 2]
        m = np.zeros(len(cen), bool)
        if variant == "berserker":
            # Three claw stripes raked across the chest, and a band round each upper arm's root.
            for i in range(3):
                c = 0.05 * (i - 1)
                m |= (np.abs((y - 1.36) - 0.55 * (x - c)) < 0.012) & (np.abs(x - c) < 0.11) & (z > 0.02)
        elif variant == "grunt":
            m |= (np.abs(y - 1.2 + 0.25 * np.abs(x)) < 0.01) & (z > 0.03) & (np.abs(x) < 0.09)
        elif variant == "shaman":
            # Ritual dots down the sternum and a ring under each collar bone.
            for i in range(5):
                m |= ((x ** 2 + (y - (1.46 - i * 0.05)) ** 2) < 0.012 ** 2) & (z > 0.02)
            for sx in (-1, 1):
                rr = np.sqrt((x - sx * 0.1) ** 2 + (y - 1.43) ** 2)
                m |= (np.abs(rr - 0.035) < 0.006) & (z > 0.02)
        return np.where(m & (reg == SKIN), PAINT, reg)
    return fn


def piece_trunk(variant):
    pc = Piece(f"ork_trunk_{variant}", "trunk")
    b = trunk_body(variant)
    add_scars(b, TRUNK_SCARS[variant])
    pc.add(b)
    pc.weights = weights_for(BUILD_OF[variant])
    seed = VARIANTS.index(variant) * 10 + 3
    pc.weather = lambda p, n, reg: trunk_tone(p, n, reg, variant, seed)  # noqa: E731
    pc.extra = trunk_gloss
    pc.regions = paint_trunk(variant)
    return pc


# ───────────────────────────────────────────────────────────────── arms + fists
def ork_fist(b, sx, gx, gy, gz, s=1.3, k=0.007):
    """people.py's gripping hand, scaled up to an ork paw, with blunt dark nails. The haft runs
    along Z through the grip point G (the `Sword` pivot), back of the hand lateral, fingers curled
    under it, the thumb over the front."""
    S = SKIN
    X = lambda dd: gx + sx * dd * s  # noqa: E731
    Y = lambda dd: gy + dd * s  # noqa: E731
    Z = lambda dd: gz + dd * s  # noqa: E731
    b.add(Squash(Cone(P(0, Y(0.095), 0), P(0, Y(0.058), 0), 0.021 * s, 0.02 * s), P(X(0.01), 0, Z(0.004)), (1.0, 1.0, 1.3)),
          S, 0.012 * s)
    b.add(RBox(P(X(0.024), Y(0.03), Z(0.004)), (0.0115 * s, 0.034 * s, 0.034 * s), 0.0105 * s), S, 0.012 * s)
    b.add(Ellipsoid(P(X(0.012), Y(0.034), Z(0.022)), (0.012 * s, 0.022 * s, 0.014 * s)), S, 0.008 * s)
    for i, (z, f) in enumerate(((0.025, 1.0), (0.008, 1.04), (-0.009, 0.98), (-0.024, 0.86))):
        r = 0.0088 * f * s
        knots = [(P(X(0.026), Y(-0.004), Z(z)), r * 1.08), (P(X(0.013), Y(-0.03 * f), Z(z * 1.02)), r),
                 (P(X(-0.016), Y(-0.026 * f), Z(z * 1.03)), r * 0.92), (P(X(-0.026), Y(-0.004), Z(z * 1.03)), r * 0.82)]
        b.add(Chain(knots), S, k)
        b.add(Sphere(P(X(0.028), Y(-0.002), Z(z)), r * 1.15), S, k)  # knuckle
        b.add(Ellipsoid(P(X(-0.029), Y(-0.0), Z(z * 1.03)), (0.003 * s, 0.006 * s, 0.006 * s * f)), NAIL, 0.002)
    b.add(Chain([(P(X(0.012), Y(0.044), Z(0.03)), 0.011 * s), (P(X(-0.006), Y(0.03), Z(0.043)), 0.0092 * s),
                 (P(X(-0.02), Y(0.018), Z(0.041)), 0.008 * s)]), S, k)
    b.add(Ellipsoid(P(X(-0.024), Y(0.02), Z(0.046)), (0.006 * s, 0.003 * s, 0.006 * s)), NAIL, 0.002)


def arm_body(build, sx):
    """One bare arm in the rig frame: deltoid, biceps / triceps, a heavy forearm, the fist."""
    bd = BUILDS[build]
    m = 1.0 if build == "heavy" else 0.84  # muscle mass
    ax, az = sx * bd["sdx"], 0.01
    X = lambda dd: ax + sx * dd  # noqa: E731
    b = PBody(h=0.0026, budget=560 if build == "heavy" else 520)
    S = SKIN
    b.add(Ellipsoid(P(X(0.008), 1.44, az), (0.07 * m, 0.098, 0.078 * m)), S)  # deltoid
    b.add(Ellipsoid(P(X(0.004), 1.41, az + 0.036 * m), (0.05 * m, 0.08, 0.045 * m)), S, 0.03)  # front head
    b.add(Ellipsoid(P(X(0.004), 1.41, az - 0.036 * m), (0.05 * m, 0.08, 0.045 * m)), S, 0.03)  # rear head
    b.add(Chain([(P(X(0.0), 1.44, az), 0.062 * m), (P(X(0.0), 1.32, az + 0.004), 0.06 * m),
                 (P(X(0.0), 1.215, az), 0.048 * m)]), S, 0.03)
    b.add(Ellipsoid(P(X(-0.004), 1.3, az + 0.03 * m), (0.047 * m, 0.082, 0.045 * m)), S, 0.025)  # biceps
    b.add(Ellipsoid(P(X(0.006), 1.33, az - 0.03 * m), (0.05 * m, 0.1, 0.046 * m)), S, 0.025)  # triceps
    b.add(Sphere(P(X(0.0), 1.172, az - 0.004), 0.047 * m), S, 0.025)  # elbow
    b.add(Sphere(P(X(0.002), 1.168, az - 0.035 * m), 0.024 * m), S, 0.012)  # olecranon
    b.add(Ellipsoid(P(X(0.006), 1.108, az + 0.008), (0.055 * m, 0.08, 0.052 * m)), S, 0.03)  # flexor / extensor mass
    b.add(Ellipsoid(P(X(0.02), 1.122, az + 0.022 * m), (0.032 * m, 0.068, 0.03 * m)), S, 0.02)  # brachioradialis
    b.add(Chain([(P(X(0.0), 1.17, az), 0.05 * m), (P(X(0.002), 1.1, az + 0.006), 0.048 * m),
                 (P(X(0.002), 1.02, az + 0.006), 0.036 * m)]), S, 0.025)
    b.add(Squash(Cone(P(0, 1.03, 0), P(0, 0.99, 0), 0.032 * m, 0.031 * m), P(X(0.003), 0, az + 0.006), (1.0, 1.0, 1.25)), S, 0.02)
    ork_fist(b, sx, ax, 0.92, az, s=1.3 if build == "heavy" else 1.2)
    # Veins down the forearm (heavy builds).
    if build == "heavy":
        for zz, x0 in ((0.035, 0.0), (0.02, 0.025)):
            pts = np.array([[X(x0), 1.16, az + zz + 0.1], [X(x0 + 0.004), 1.08, az + zz + 0.1], [X(x0 - 0.002), 1.0, az + zz + 0.1]])
            pts = hit(b.eval, pts, [[0, 0, -1]] * 3, t1=0.2)
            b.add(Chain([(P(*q), 0.0028) for q in to_surface(b, np.concatenate([np.linspace(pts[0], pts[1], 5), np.linspace(pts[1], pts[2], 5)]), 0.0012)]), S, 0.004)
    return b


ARM_SCARS = {"heavy": [[(0.04, 1.36, 0.2), (0.0, 1.3, 0.2)], [(0.03, 1.1, 0.2), (-0.02, 1.05, 0.2)]], "lean": [[(0.02, 1.33, 0.2), (0.0, 1.27, 0.2)]]}


def arm_tone(p, n, reg, sx, seed):
    tn = 0.5 + 0.08 * mottle(p, 10.0, seed) + 0.04 * mottle(p, 30.0, seed + 1)
    tn -= 0.18 * blob(p, (p[:, 0].mean(), 1.17, -0.04), 0.035)  # elbow
    tn -= 0.22 * ss(0.99, 0.93, p[:, 1]) * ss(-0.01, 0.02, sx * (p[:, 0] - p[:, 0].mean()))  # knuckles / back of the paw
    tn += 0.1 * ss(0.0, -0.03, sx * (p[:, 0] - p[:, 0].mean())) * ss(0.98, 1.1, p[:, 1])  # inner arm, paler
    tn -= 0.08 * ss(1.4, 1.5, p[:, 1])  # sun on the shoulder
    return np.where(reg == SKIN, tn, np.where(reg == SCAR, 0.62, np.where(reg == NAIL, 0.35, 0.5)))


def arm_gloss(p, n, reg):
    g = 0.3 + 0.2 * mottle(p, 12.0, 5)
    g -= 0.3 * blob(p, (p[:, 0].mean(), 1.17, -0.04), 0.04)  # dry elbow
    g -= 0.2 * ss(0.99, 0.93, p[:, 1])  # dry, calloused paw
    g += 0.25 * ss(1.38, 1.48, p[:, 1])
    return np.where(reg == SCAR, 0.9, np.where(reg == NAIL, 0.75, g))


def piece_arm(build, sx):
    side = "l" if sx < 0 else "r"
    pc = Piece(f"ork_arm_{build}_{side}", f"arm_{side}")
    b = arm_body(build, sx)
    ax = sx * BUILDS[build]["sdx"]
    lines = [[(ax + sx * q[0], q[1], q[2]) for q in line] for line in ARM_SCARS[build]] if sx > 0 else []
    add_scars(b, lines, r=0.0034)
    pc.add(b)
    pc.weights = weights_for(build)
    pc.weather = lambda p, n, reg: arm_tone(p, n, reg, sx, 40 + (sx > 0))  # noqa: E731
    pc.extra = arm_gloss
    return pc


# ───────────────────────────────────────────────────────────────── legs + feet
def leg_body(build, sx):
    """One bare leg: thigh muscle groups, knee + kneecap, shin and a two-headed calf, the foot."""
    bd = BUILDS[build]
    m = 1.08 if build == "heavy" else 0.92
    x0 = sx * bd["hdx"]
    X = lambda dd: x0 + sx * dd  # noqa: E731
    b = PBody(h=0.003, budget=520)
    S = SKIN
    # Thigh: the femur angles in from the hip, so the mass sits a little medial up top.
    b.add(Chain([(P(X(-0.022), 1.06, -0.008), 0.082 * m), (P(X(-0.012), 0.94, 0.0), 0.084 * m),
                 (P(X(-0.005), 0.8, 0.006), 0.073 * m), (P(X(0.0), 0.67, 0.006), 0.058 * m)]), S)
    b.add(Ellipsoid(P(X(-0.002), 0.81, 0.032 * m), (0.064 * m, 0.14, 0.05 * m)), S, 0.035)  # rectus femoris
    b.add(Ellipsoid(P(X(0.028 * m), 0.83, 0.0), (0.05 * m, 0.12, 0.058 * m)), S, 0.035)  # vastus lateralis
    b.add(Ellipsoid(P(X(-0.032 * m), 0.69, 0.018), (0.04 * m, 0.058, 0.04 * m)), S, 0.025)  # vastus medialis
    b.add(Ellipsoid(P(X(-0.004), 0.84, -0.034 * m), (0.062 * m, 0.12, 0.048 * m)), S, 0.035)  # hamstrings
    b.add(Ellipsoid(P(X(-0.048 * m), 0.92, -0.004), (0.036 * m, 0.1, 0.055 * m)), S, 0.03)  # adductors
    b.add(Sphere(P(X(0.0), 0.6, -0.002), 0.058 * m), S, 0.03)  # knee
    b.add(Ellipsoid(P(X(0.0), 0.6, 0.046 * m), (0.032 * m, 0.036, 0.02)), S, 0.014)  # kneecap
    b.add(Ellipsoid(P(X(0.0), 0.552, 0.038 * m), (0.018 * m, 0.03, 0.014)), S, 0.012)  # patellar tendon
    b.add(Chain([(P(X(0.0), 0.6, -0.004), 0.055 * m), (P(X(0.0), 0.46, -0.006), 0.049 * m),
                 (P(X(0.0), 0.27, 0.0), 0.037 * m), (P(X(0.0), 0.165, -0.004), 0.035 * m)]), S, 0.025)
    b.add(Ellipsoid(P(X(0.016 * m), 0.48, -0.036 * m), (0.048 * m, 0.088, 0.046 * m)), S, 0.03)  # calf, outer head
    b.add(Ellipsoid(P(X(-0.014 * m), 0.465, -0.033 * m), (0.046 * m, 0.088, 0.045 * m)), S, 0.03)  # inner head (lower)
    b.add(Ellipsoid(P(X(0.012), 0.42, 0.028 * m), (0.024 * m, 0.1, 0.018 * m)), S, 0.02)  # shin muscle
    for dd in (-1, 1):
        b.add(Sphere(P(X(0.03 * dd * m), 0.158, -0.006), 0.017 * m), S, 0.012)  # ankle bones
    # Foot: a broad bare sole, heel, instep and five blunt toes with dark nails.
    b.add(Sphere(P(X(0.0), 0.098, -0.044), 0.046 * m), S, 0.02)  # heel
    b.add(Chain([(P(X(0.0), 0.1, -0.03), 0.048 * m), (P(X(0.006), 0.09, 0.06), 0.047 * m),
                 (P(X(0.004), 0.078, 0.122), 0.038 * m)]), S, 0.022)
    b.add(Ellipsoid(P(X(0.0), 0.125, 0.045), (0.042 * m, 0.035, 0.06), rot_x(0.4)), S, 0.02)  # instep
    toes = [(-0.024, 0.016, 0.186), (-0.004, 0.012, 0.18), (0.013, 0.011, 0.172), (0.027, 0.0105, 0.162),
            (0.039, 0.0095, 0.148)]
    for dx, r, z in toes:
        r *= m * 1.05
        b.add(Chain([(P(X(dx * m), 0.074, z - 0.045), r * 1.1), (P(X(dx * m * 1.05), 0.07, z), r)]), S, 0.008)
        b.add(Ellipsoid(P(X(dx * m * 1.05), 0.072 + r * 0.55, z + 0.002), (r * 0.8, r * 0.35, r * 0.7)), NAIL, 0.003)
    b.cut(half(P(0, SOLE_Y, 0), (0, 1, 0)), 0.006)
    return b


def wraps_body(build, sx, leg):
    """Leather wraps wound round the ankle and over the instep: a band hugging the shin (ragged top
    edge) with the raised edges of the overlapping turns spiralling down it."""
    bd = BUILDS[build]
    x0 = sx * bd["hdx"]
    w = PBody(h=0.0018, budget=150, clip=((x0 - 0.1, 0.09, -0.1), (x0 + 0.1, 0.33, 0.12)))
    w.add(layer(leg, -0.003, 0.0055), LEATHER)
    ang = lambda p: np.arctan2(p[:, 0] - x0, p[:, 2])  # noqa: E731
    w.cut(Fn(lambda p: np.maximum(0.122 + 0.02 * ss(0.0, -0.06, p[:, 2]) - p[:, 1],
                                  p[:, 1] - (0.29 + 0.022 * np.sin(ang(p) + 0.6 * sx))), (-BIG,) * 3, (BIG,) * 3))
    knots = []
    for i in range(90):
        t = i / 89
        a = t * 2 * math.pi * 3.6
        knots.append([x0 + 0.09 * math.sin(a), 0.285 - t * 0.15 - 0.012 * math.cos(a), 0.09 * math.cos(a)])
    knots = np.array(knots)
    dirs = np.stack([x0 - knots[:, 0], np.zeros(len(knots)), -knots[:, 2]], 1)
    pts = hit(offset(leg, 0.004).d, knots, dirs, t1=0.1)
    w.add(Chain([(P(*q), 0.0034) for q in pts]), LEATHER, 0.003)
    # A strap under the arch and over the instep.
    angs = np.linspace(0, 2 * math.pi, 18, endpoint=False)
    org = [[x0 + 0.09 * math.sin(a), 0.09 + 0.06 * math.cos(a), 0.04] for a in angs]
    dirs = [[-math.sin(a), -math.cos(a), 0.0] for a in angs]
    pts = hit(leg.eval, org, dirs, t1=0.09)
    w.add(ring([(P(*q), 0.0065) for q in pts]), STRAP, 0.003)
    w.cut(half(P(0, SOLE_Y + 0.002, 0), (0, 1, 0)))
    return w


def leg_tone(p, n, reg, seed):
    tn = 0.5 + 0.08 * mottle(p, 9.0, seed) + 0.04 * mottle(p, 30.0, seed + 1)
    tn -= 0.18 * np.exp(-((p[:, 1] - 0.6) / 0.04) ** 2) * ss(0.0, 0.04, p[:, 2])  # knees
    tn -= 0.25 * ss(0.14, 0.07, p[:, 1])  # grimy feet
    tn += 0.08 * ss(0.85, 1.0, p[:, 1]) * ss(0.0, -0.04, np.abs(p[:, 0]) - 0.1)  # inner thigh
    wear = 0.5 + 0.25 * mottle(p, 50.0, seed + 5) - 0.15 * ss(0.12, 0.07, p[:, 1])
    return np.where(reg == SKIN, tn, np.where(reg == NAIL, 0.3, np.where((reg == LEATHER) | (reg == STRAP), wear, 0.5)))


def leg_gloss(p, n, reg):
    g = 0.3 + 0.15 * mottle(p, 12.0, 9)
    g -= 0.3 * np.exp(-((p[:, 1] - 0.6) / 0.05) ** 2)  # dry knees
    g -= 0.25 * ss(0.14, 0.07, p[:, 1])  # dusty feet
    return np.where((reg == LEATHER) | (reg == STRAP), 0.25, np.where(reg == NAIL, 0.6, g))


_LEGS = {}


def leg_ref(build, sx):
    key = (build, sx)
    if key not in _LEGS:
        _LEGS[key] = leg_body(build, sx)
    return _LEGS[key]


def piece_leg(build, sx):
    side = "l" if sx < 0 else "r"
    pc = Piece(f"ork_leg_{build}_{side}", f"leg_{side}")
    lb = leg_ref(build, sx)
    pc.add(lb)
    pc.add(wraps_body(build, sx, lb), cull=lb.eval, depth=0.0015)
    pc.weights = weights_for(build)
    pc.weather = lambda p, n, reg: leg_tone(p, n, reg, 60 + (sx > 0))  # noqa: E731
    pc.extra = leg_gloss
    return pc


# ───────────────────────────────────────────────────────────────── loincloth + belt
def hip_ref(variant):
    """What the loincloth hangs on: the trunk's pelvis + both thigh tops."""
    tb = trunk_body(variant)
    build = BUILD_OF[variant]
    legs = [leg_ref(build, sx) for sx in (-1, 1)]
    lo, hi = (-0.4, 0.7, -0.3), (0.4, 1.25, 0.3)

    def fn(p):
        d = tb.eval(p)
        for lb in legs:
            d = np.minimum(d, lb.eval(p))
        return d
    return Ref(fn, lo, hi)


def piece_kilt(variant):
    """The war-belt and loincloth: a broad leather belt (iron buckle, a bone trophy), a cloth wrap
    round the loins, front and back flaps in the warband's colour, and leather strips over the hips.
    Weighted like a skirt: the centre follows both thighs, each side its own."""
    build = BUILD_OF[variant]
    w = BUILDS[build]["w"]
    pc = Piece(f"ork_kilt_{variant}", "trunk")
    tb = trunk_body(variant)
    href = hip_ref(variant)
    long_hem = variant == "shaman"
    # Loin wrap round the pelvis and thigh tops.
    wr = PBody(h=0.003, budget=240, clip=((-0.3, 0.86, -0.25), (0.3, 1.09, 0.25)))
    wr.add(offset(href, 0.007), CLOTH).cut(slab((0, 1, 0), 0.885, 1.08))
    wr.cut(Fn(lambda p: 0.93 - p[:, 1] + 0.9 * np.maximum(np.abs(p[:, 0]) - 0.07, 0.0), (-BIG,) * 3, (BIG,) * 3))
    wr.shag(Ellipsoid(P(0, 0.97, 0.0), (0.3, 0.12, 0.25)), 0.003, Folds(13, 0.4, 1.05, 0.9), soft=0.03)
    pc.add(wr, cull=href.d, depth=0.004)
    # Belt.
    bt = PBody(h=0.0024, budget=160, clip=((-0.3, 1.03, -0.25), (0.3, 1.14, 0.25)))
    bt.add(layer(tb, -0.002, 0.013), LEATHER).cut(slab((0, 1, 0), 1.05, 1.11))
    pc.add(bt)
    zf = hit(tb.eval, [[0, 1.08, 0.3]], [[0, 0, -1]])[0][2]
    bk = PBody(h=0.0016, budget=120)
    bk.sym = False
    bk.add(RBox(P(0, 1.08, zf + 0.016), (0.03, 0.026, 0.006), 0.004), IRON)
    bk.sub(RBox(P(0, 1.08, zf + 0.022), (0.018, 0.014, 0.006), 0.003), IRON)
    # A bone trophy (a jaw / skull fragment) hung off the belt on the left hip.
    xs = hit(tb.eval, [[-0.3, 1.06, 0.05]], [[1, 0, 0]])[0][0]
    bk.add(Ellipsoid(P(xs - 0.012, 1.02, 0.06), (0.012, 0.026, 0.02)), BONE, 0.004)
    bk.add(Sphere(P(xs - 0.014, 0.998, 0.064), 0.015), BONE, 0.006)
    bk.sub(Sphere(P(xs - 0.026, 1.0, 0.07), 0.006), BONE, 0.002)
    bk.add(Cone(P(xs - 0.008, 1.075, 0.06), P(xs - 0.012, 1.03, 0.06), 0.003, 0.003), STRAP, 0.002)
    pc.add(bk)
    # Front and back flaps, hanging from the belt to mid-thigh (the shaman's to the knee).
    hem = 0.66 if long_hem else 0.78
    sk = PBody(h=0.003, budget=0)
    sk.add(Squash(CappedCone(P(0, 1.1, 0), P(0, hem - 0.02, 0), 0.14 * w, 0.165 * w), P(0, 0, -0.01), (1, 1, 0.78)), CLOTH)
    for fz, half_w in ((1, 0.085 * w + 0.01), (-1, 0.095 * w + 0.01)):
        fl = PBody(h=0.003, budget=210 if long_hem else 160, clip=((-0.16, hem - 0.03, -0.3), (0.16, 1.1, 0.3)))
        fl.add(layer(Ref(lambda p: np.minimum(sk.eval(p), href.d(p)), (-0.4, 0.6, -0.4), (0.4, 1.2, 0.4)), 0.006, 0.012), CLOTH)
        fl.cut(Fn(lambda p, fz=fz: -fz * p[:, 2], (-BIG,) * 3, (BIG,) * 3))
        # Tapering to a ragged hem.
        fl.cut(Fn(lambda p, hw=half_w: np.abs(p[:, 0]) - hw * (1.0 - 0.25 * ss(1.0, hem, p[:, 1])), (-BIG,) * 3, (BIG,) * 3))
        fl.cut(Fn(lambda p: hem + 0.01 * np.sin(p[:, 0] * 55.0) + 0.005 * np.sin(p[:, 0] * 130.0 + 1.0) - p[:, 1],
                  (-BIG,) * 3, (BIG,) * 3))
        fl.cut(slab((0, 1, 0), hem - 0.05, 1.075))
        fl.shag(Ellipsoid(P(0, (hem + 1.0) / 2, fz * 0.1), (0.15, 0.3, 0.15)), 0.004,
                Folds(7, 0.8 + fz, 1.05, hem, 0.0, 0.0), soft=0.03)
        pc.add(fl)
    # Leather strips over the hips (a war-kilt of hide tongues), gaps between them.
    if not long_hem:
        st = PBody(h=0.0026, budget=260, clip=((-0.3, 0.8, -0.25), (0.3, 1.08, 0.25)))
        st.add(layer(Ref(lambda p: np.minimum(sk.eval(p), href.d(p)), (-0.4, 0.6, -0.4), (0.4, 1.2, 0.4)), 0.013, 0.019), LEATHER)
        ang = lambda p: np.arctan2(p[:, 0], p[:, 2])  # noqa: E731
        st.cut(Fn(lambda p: np.cos(ang(p) * 11.0) - 0.2, (-BIG,) * 3, (BIG,) * 3))  # tongues, gaps between
        st.cut(Fn(lambda p: 0.55 - np.abs(np.sin(ang(p))), (-BIG,) * 3, (BIG,) * 3))  # only over the hips
        st.cut(Fn(lambda p: 0.83 + 0.02 * np.cos(ang(p) * 11.0) - p[:, 1], (-BIG,) * 3, (BIG,) * 3))
        st.cut(slab((0, 1, 0), 0.8, 1.07))
        pc.add(st)
    pc.weights = weights_for(build)

    def tone(p, n, reg):
        grime = 0.5 - 0.22 * ss(0.95, hem, p[:, 1]) + 0.1 * mottle(p, 30.0, 11)
        wear = 0.55 + 0.2 * mottle(p, 40.0, 12)
        return np.where(reg == CLOTH, grime, np.where((reg == LEATHER) | (reg == STRAP), wear, 0.5))
    pc.weather = tone
    pc.extra = lambda p, n, reg: np.where(reg == LEATHER, 0.4 + 0.2 * mottle(p, 25.0, 13),  # noqa: E731
                                          np.where(reg == IRON, 0.6, np.where(reg == BONE, 0.5, 0.0)))
    return pc


# ───────────────────────────────────────────────────────────────── gear
def piece_pauldron(variant):
    """The grunt's left pauldron: boiled leather over a fur collar, iron studs, strapped across."""
    build = BUILD_OF[variant]
    sdx = BUILDS[build]["sdx"]
    pc = Piece(f"ork_pauldron_{variant}", "arm_l")
    arm = arm_body(build, -1)
    ax = -sdx
    sh = PBody(h=0.0024, budget=200, clip=((ax - 0.15, 1.3, -0.15), (ax + 0.12, 1.6, 0.15)))
    sh.add(layer(arm, 0.016, 0.026), LEATHER).cut(half(P(0, 1.34, 0), (0, 1, 0))).cut(
        Fn(lambda p: p[:, 0] - (ax + 0.03), (-BIG,) * 3, (BIG,) * 3))
    sh.cut(Fn(lambda p: 1.36 + 0.03 * np.cos(np.arctan2(p[:, 2], -(p[:, 0] - ax)) * 2) - p[:, 1], (-BIG,) * 3, (BIG,) * 3))
    pc.add(sh, cull=arm.eval, depth=0.004)
    st = PBody(h=0.0016, budget=80)
    for a in np.linspace(-1.0, 1.0, 5):
        org = np.array([[ax - 0.2 * math.cos(a), 1.47 - 0.03 * abs(a), 0.2 * math.sin(a)]])
        q = hit(Fn(lambda p: arm.eval(p) - 0.026, (-1,) * 3, (1,) * 3).d, org, [[math.cos(a), 0, -math.sin(a)]], t1=0.3)[0]
        st.add(Sphere(P(*q), 0.008), IRON, 0.002)
    pc.add(st)
    fur = PBody(h=0.002, budget=140, clip=((ax - 0.12, 1.42, -0.14), (ax + 0.14, 1.6, 0.14)))
    fur.add(layer(arm, 0.006, 0.03), FUR).cut(half(P(0, 1.5, 0), (0, 1, 0)))
    fur.shag(Sphere(P(ax, 1.52, 0), 0.15), 0.008, Tufts(120, (0, -1, 0), seed=21), soft=0.02)
    pc.add(fur, cull=arm.eval, depth=0.004)
    pc.weights = weights_for(build)
    pc.weather = lambda p, n, reg: np.where(reg == LEATHER, 0.5 + 0.25 * mottle(p, 40.0, 3), 0.5)  # noqa: E731
    pc.extra = lambda p, n, reg: np.where(reg == LEATHER, 0.55, np.where(reg == IRON, 0.7, 0.0))  # noqa: E731
    return pc


def piece_bracers(build, sx, kind="bracer"):
    """Laced leather bracers on the forearm (or a berserker's rag wraps)."""
    side = "l" if sx < 0 else "r"
    pc = Piece(f"ork_{kind}_{build}_{side}", f"arm_{side}")
    arm = arm_body(build, sx)
    ax = sx * BUILDS[build]["sdx"]
    if kind == "bracer":
        b = PBody(h=0.0018, budget=150, clip=((ax - 0.1, 0.99, -0.1), (ax + 0.1, 1.13, 0.12)))
        b.add(layer(arm, 0.002, 0.009), LEATHER).cut(slab((0, 1, 0), 1.0, 1.115))
        pc.add(b, cull=arm.eval, depth=0.004)
        la = PBody(h=0.0012, budget=60)
        for y in (1.02, 1.055, 1.09):
            la.add(ring(surface_ring(offset(arm, 0.01).d, ax, 0.012, lambda a, y=y: y, rad=0.14, n=16, tube=0.0024)), STRAP)
        pc.add(la)
    else:
        b = PBody(h=0.0016, budget=140)
        knots = []
        for i in range(48):
            t = i / 47
            y = 1.1 - t * 0.12
            a = t * 2 * math.pi * 3.2
            knots.append([ax + 0.1 * math.sin(a), y - 0.012 * math.cos(a), 0.01 + 0.1 * math.cos(a)])
        knots = np.array(knots)
        dirs = np.stack([ax - knots[:, 0], np.zeros(len(knots)), 0.01 - knots[:, 2]], 1)
        pts = hit(arm.eval, knots, dirs, t1=0.1)
        b.add(Chain([(P(*q), 0.006) for q in pts]), CLOTH, 0.003)
        pc.add(b)
    pc.weights = weights_for(build)
    pc.weather = lambda p, n, reg: 0.5 + 0.2 * mottle(p, 40.0, 7 + (sx > 0))  # noqa: E731
    pc.extra = lambda p, n, reg: np.where(reg == LEATHER, 0.45, 0.0)  # noqa: E731
    return pc


def piece_strap(variant):
    """The scout's baldric: a strap from the right shoulder to the left hip with a pouch."""
    tb = trunk_body(variant)
    pc = Piece(f"ork_strap_{variant}", "trunk")
    b = PBody(h=0.002, budget=160)
    b.sym = False
    knots = []
    for t in np.linspace(0, 1, 16):
        # Front: right shoulder top down to the left hip.
        x = 0.13 - 0.27 * t
        y = 1.52 - 0.44 * t
        knots.append((x, y, 1))
    for t in np.linspace(0, 1, 12):
        x = 0.13 + 0.0 * t
        knots.append((0.15 - 0.3 * t, 1.5 - 0.4 * t, -1))
    pts_f = hit(tb.eval, [[x, y, 0.3 * s] for x, y, s in knots], [[0, 0, -s] for _, _, s in knots], t1=0.35)
    front, back = pts_f[:16], pts_f[16:]
    for seg in (front, back):
        b.add(Chain([(P(q[0], q[1], q[2] + 0.009 * np.sign(q[2])), 0.009) for q in seg]), STRAP, 0.004)
    # Over the shoulder: an arc joining the two ends.
    top = [front[0], (front[0] + back[0]) / 2 + np.array([0.0, 0.04, 0.0]), back[0]]
    b.add(Chain([(P(*q), 0.0095) for q in top]), STRAP, 0.006)
    q = front[-2]
    b.add(RBox(P(q[0] - 0.01, q[1] - 0.02, q[2] + 0.02), (0.028, 0.03, 0.014), 0.008), LEATHER, 0.004)  # pouch
    pc.add(b)
    pc.weights = weights_for(BUILD_OF[variant])
    pc.weather = lambda p, n, reg: 0.5 + 0.2 * mottle(p, 40.0, 17)  # noqa: E731
    pc.extra = lambda p, n, reg: np.full(len(p), 0.35)  # noqa: E731
    return pc


def piece_mantle(variant):
    """The shaman's fur mantle over the shoulders and a cord of teeth and finger bones."""
    tb = trunk_body(variant)
    sdx = BUILDS[BUILD_OF[variant]]["sdx"]
    pc = Piece(f"ork_mantle_{variant}", "trunk")
    m = PBody(h=0.003, budget=420, clip=((-0.4, 1.28, -0.3), (0.4, 1.7, 0.3)))
    m.add(offset(tb, 0.022), FUR)
    for sx in (-1, 1):
        m.add(Ellipsoid(P(sx * (sdx + 0.005), 1.46, 0.0), (0.085, 0.07, 0.09)), FUR, 0.04)  # over the deltoids
    m.cut(Fn(lambda p: 1.33 + 0.07 * (p[:, 2] < 0) + 0.04 * np.sin(np.arctan2(p[:, 0], p[:, 2]) * 7) - p[:, 1],
             (-BIG,) * 3, (BIG,) * 3))
    m.cut(Fn(lambda p: p[:, 1] - (1.575 + 1.2 * (p[:, 0] ** 2 + (0.9 * p[:, 2]) ** 2)), (-BIG,) * 3, (BIG,) * 3))
    m.shag(Sphere(P(0, 1.45, 0), 0.5), 0.012, Tufts(70, (0, -1, 0), seed=31), soft=0.02)
    pc.add(m, cull=tb.eval, depth=0.006)
    nk = PBody(h=0.0014, budget=200)
    nk.sym = False
    angs = np.linspace(-1.25, 1.25, 13)
    org = [[0.3 * math.sin(a), 1.46 - 0.07 * math.cos(a) ** 2 * 0 - 0.05 * math.cos(a), 0.3 * math.cos(a)] for a in angs]
    pts = hit(offset(tb, 0.024).d, org, [[-math.sin(a), 0, -math.cos(a)] for a in angs], t1=0.3)
    nk.add(Chain([(P(*q), 0.003) for q in pts]), STRAP, 0.002)
    for i, q in enumerate(pts[1:-1]):
        dn = np.array([0.0, -1.0, 0.0])
        out = np.array([math.sin(angs[i + 1]), 0.0, math.cos(angs[i + 1])])
        ln = 0.03 if i % 2 == 0 else 0.022
        nk.add(Cone(P(*(q + out * 0.004)), P(*(q + dn * ln + out * 0.01)), 0.006, 0.0025), BONE, 0.002)
    pc.add(nk)
    pc.weights = weights_for(BUILD_OF[variant])
    pc.weather = lambda p, n, reg: np.where(reg == FUR, 0.5 + 0.2 * mottle(p, 20.0, 41), 0.5)  # noqa: E731
    pc.extra = lambda p, n, reg: np.where(reg == BONE, 0.55, 0.0)  # noqa: E731
    return pc


# ───────────────────────────────────────────────────────────────── heads
# Head-local frame: the head pivot (ear level) at the origin, face toward +Z, unscaled.
HEADS = {
    "grunt": dict(w=1.06, jaw=1.12, brow=1.15, tusk=1.25, nose=1.1, ear=1.0, cheek=1.05),
    "scout": dict(w=0.94, jaw=0.92, brow=0.95, tusk=0.8, nose=0.95, ear=1.25, cheek=0.92),
    "berserker": dict(w=1.08, jaw=1.15, brow=1.2, tusk=1.35, nose=1.15, ear=0.95, cheek=1.1),
    "shaman": dict(w=0.96, jaw=0.95, brow=1.05, tusk=0.95, nose=1.05, ear=1.35, cheek=0.85, old=True),
}


def skull(b, f):
    w = f["w"]
    b.add(Ellipsoid(P(0, 0.058, -0.03), (0.082 * w, 0.082, 0.1)), SKIN)  # cranium: low, long
    b.add(Ellipsoid(P(0, 0.034, 0.022), (0.077 * w, 0.06, 0.07)), SKIN, 0.03)  # sloping forehead
    b.add(Ellipsoid(P(0, -0.02, -0.06), (0.064 * w, 0.056, 0.052)), SKIN, 0.03)  # occiput


def scalp(f):
    b = PBody(h=0.002, budget=0)
    skull(b, f)
    return b


def ork_ear(b, sx, f):
    w, e = f["w"], f["ear"]
    c = P(sx * 0.079 * w, 0.03, -0.022)
    R = rot_y(sx * 0.75) @ rot_x(0.1) @ rot_z(-sx * 0.25)
    b.add(Ellipsoid(c, (0.008, 0.03 * e, 0.024 * e), R), SKIN, 0.008)  # pinna
    tip = c + P(sx * 0.03 * e, 0.035 * e, -0.05 * e)
    b.add(Cone(c + P(sx * 0.004, 0.012, -0.012), tip, 0.014 * e, 0.0025), SKIN, 0.01)  # long point, swept back
    b.sub(Ellipsoid(c + P(sx * 0.006, 0.0, 0.004), (0.0045, 0.018 * e, 0.012 * e), R), SKIN, 0.004)  # bowl
    b.add(Sphere(c + P(sx * 0.0, -0.026 * e, 0.008), 0.0075), SKIN, 0.005)  # lobe


def ork_face(b, f, variant):
    w, j, br, n, ch = f["w"], f["jaw"], f["brow"], f["nose"], f["cheek"]
    old = f.get("old", False)
    S = SKIN
    # Heavy brow ridge with a glabella, deep-set eyes under it.
    b.add(Cone(P(-0.044 * w, 0.054, 0.08), P(0.044 * w, 0.054, 0.08), 0.017 * br, 0.017 * br), S, 0.02)
    b.add(Sphere(P(0, 0.056, 0.087), 0.014 * br), S, 0.012)
    b.add(Ellipsoid(P(0, 0.006, 0.048), (0.06 * w, 0.052, 0.054)), S, 0.025)  # midface
    for sx in (-1, 1):
        b.add(Ellipsoid(P(sx * 0.052 * w, 0.018, 0.058), np.array((0.026, 0.017, 0.022)) * ch), S, 0.02)  # cheekbones
        b.add(Ellipsoid(P(sx * 0.044 * w, -0.012, 0.058), (0.026, 0.026, 0.022)), S, 0.025)  # cheeks
        b.sub(Ellipsoid(P(sx * 0.031 * w, 0.034, 0.084), (0.018, 0.0115, 0.014)), S, 0.008)  # eye sockets
    # Prognathous muzzle, the upper lip over it.
    b.add(Ellipsoid(P(0, -0.022, 0.082), (0.036 * w, 0.03, 0.027)), S, 0.018)
    b.add(Ellipsoid(P(0, -0.024, 0.102), (0.028 * w, 0.007, 0.009), rot_x(-0.2)), S, 0.005)
    # Underbite jaw: mandible angle -> chin, the lower lip pushed out past the upper.
    gx, gy, gz = 0.062 * w * j, -0.042, -0.004
    b.add(Chain([(P(-gx, gy, gz), 0.019 * j), (P(-0.046 * w * j, -0.07, 0.058), 0.02 * j),
                 (P(0, -0.076, 0.094), 0.022 * j), (P(0.046 * w * j, -0.07, 0.058), 0.02 * j),
                 (P(gx, gy, gz), 0.019 * j)]), S, 0.024)
    for sx in (-1, 1):
        b.add(Cone(P(sx * gx, gy, gz), P(sx * 0.066 * w, 0.016, -0.01), 0.016, 0.013), S, 0.02)  # rami
        b.add(Ellipsoid(P(sx * 0.05 * w * j, -0.05, 0.03), (0.016, 0.024, 0.026)), S, 0.02)  # masseters
    b.add(Sphere(P(0, -0.074, 0.098), 0.02 * j), S, 0.014)  # chin
    b.add(Ellipsoid(P(0, -0.042, 0.104 + 0.003 * j), (0.029 * w, 0.009, 0.01), rot_x(0.3)), S, 0.006)  # lower lip
    b.sub(Ellipsoid(P(0, -0.034, 0.113), (0.03 * w, 0.0022, 0.012)), DARK, 0.002)  # mouth line
    # Broad flat nose with flared nostrils.
    b.add(Cone(P(0, 0.046, 0.09), P(0, 0.012, 0.112 + 0.004 * n), 0.009 * n, 0.012 * n), S, 0.009)
    b.add(Sphere(P(0, 0.006, 0.114 + 0.004 * n), 0.0135 * n), S, 0.007)
    for sx in (-1, 1):
        b.add(Sphere(P(sx * 0.019 * n, 0.0, 0.1), 0.0125 * n), S, 0.007)  # alae
        b.sub(Ellipsoid(P(sx * 0.011 * n, -0.005, 0.111 + 0.003 * n), (0.0055, 0.004, 0.007), rot_x(-0.5)), S, 0.002)
        # Nasolabial folds and the crease under the eye.
        b.sub(Cone(P(sx * 0.026 * n, 0.006, 0.104), P(sx * 0.044 * w, -0.03, 0.09), 0.0025, 0.0018), S, 0.003)
        b.sub(Cone(P(sx * 0.018 * w, 0.02, 0.098), P(sx * 0.046 * w, 0.017, 0.086), 0.0018, 0.0015), S, 0.0025)
    # Forehead furrows.
    for i, y in enumerate((0.085, 0.1, 0.113) if old else (0.088, 0.104)):
        q = hit(b.eval, [[0, y, 0.2]], [[0, 0, -1]])[0]
        b.sub(Cone(P(-0.04 * w, y, q[2] - 0.004), P(0.04 * w, y + 0.002, q[2] - 0.004), 0.0018, 0.0018), S, 0.003)
    if old:  # gaunt: hollow cheeks, crow's feet
        for sx in (-1, 1):
            b.sub(Ellipsoid(P(sx * 0.052 * w, -0.02, 0.07), (0.012, 0.018, 0.01)), S, 0.012)
            for k in range(3):
                b.sub(Cone(P(sx * 0.052 * w, 0.04 - 0.008 * k, 0.078), P(sx * 0.064 * w, 0.044 - 0.016 * k, 0.066),
                           0.0012, 0.001), S, 0.0015)
    for sx in (-1, 1):
        ork_ear(b, sx, f)


def tusks(f, variant):
    t = f["tusk"]
    b = PBody(h=0.0011, budget=90)
    for sx in (-1, 1):
        base = P(sx * 0.026 * f["w"], -0.046, 0.1)
        mid = base + P(sx * 0.004, 0.026 * t, 0.006)
        tip = base + P(sx * 0.012 * t, 0.046 * t, 0.002)
        b.add(Chain([(base, 0.0085 * t), (mid, 0.0062 * t), (tip, 0.0018)]), BONE)
        if variant == "berserker" and sx > 0:  # a snapped tusk
            b.cut(Fn(lambda p: p[:, 1] + 0.012 - 0.3 * (p[:, 0] < 0), (-BIG,) * 3, (BIG,) * 3))
    return b


def eyes_body(f):
    b = PBody(h=0.001, budget=60)
    for sx in (-1, 1):
        b.add(Sphere(P(sx * 0.031 * f["w"], 0.034, 0.072), 0.0115), EYE)
    return b


def lids_body(f):
    b = PBody(h=0.001, budget=80)
    for sx in (-1, 1):
        cx = sx * 0.031 * f["w"]
        b.add(Ellipsoid(P(cx, 0.042, 0.077), (0.0155, 0.0062, 0.0112), rot_x(-0.45)), SKIN)  # heavy upper lid
        b.add(Ellipsoid(P(cx, 0.0255, 0.0775), (0.0142, 0.004, 0.0098), rot_x(0.35)), SKIN, 0.002)
    return b


HEAD_SCARS = {
    "grunt": [[(0.06, 0.06, 0.2), (0.045, 0.02, 0.2), (0.04, -0.02, 0.2)]],
    "berserker": [[(-0.05, 0.08, 0.2), (-0.03, 0.04, 0.2), (-0.01, -0.0, 0.2), (0.015, -0.03, 0.2)],
                  [(0.05, 0.12, 0.2), (0.07, 0.07, 0.2)]],
    "scout": [],
    "shaman": [],
}


def head_paint(variant):
    def fn(cen, reg):
        x, y, z = cen[:, 0], cen[:, 1], cen[:, 2]
        m = np.zeros(len(cen), bool)
        if variant == "berserker":
            m |= (np.abs(y - 0.034) < 0.013) & (z > 0.04) & (np.abs(x) < 0.07)  # a band across the eyes
            m |= (np.abs(x) < 0.008) & (y > -0.07) & (y < -0.04) & (z > 0.07)  # chin stripe
        elif variant == "shaman":
            for sx in (-1, 1):
                for k in range(3):
                    m |= (np.abs(y - (0.01 - 0.014 * k)) < 0.004) & (np.abs(x - sx * 0.05) < 0.016) & (z > 0.03)
            m |= ((x ** 2 + (y - 0.075) ** 2) < 0.009 ** 2) & (z > 0.05)
        return np.where(m & (reg == SKIN), PAINT, reg)
    return fn


def head_tone(p, n, reg, seed):
    tn = 0.5 + 0.07 * mottle(p, 30.0, seed) + 0.04 * mottle(p, 80.0, seed + 1)
    tn -= 0.18 * ss(0.075, 0.1, np.abs(p[:, 0]))  # ears
    tn -= 0.15 * blob(p, (0, 0.006, 0.115), 0.016)  # nose
    tn -= 0.12 * sum(blob(p, (sx * 0.031, 0.034, 0.08), 0.02) for sx in (-1, 1))  # dark round the eyes
    tn += 0.06 * ss(0.0, -0.06, p[:, 1]) * ss(0.04, 0.09, p[:, 2])  # paler under the jaw
    tn -= 0.16 * ss(0.075, 0.11, p[:, 1]) * ss(0.05, -0.02, p[:, 2])  # stubble shadow on the scalp
    return np.where(reg == SKIN, tn, np.where(reg == SCAR, 0.62, np.where(reg == HAIR, 0.5 + 0.2 * mottle(p, 90.0, 4),
                                                                              np.where(reg == BONE, 0.42, 0.5))))


def head_gloss(p, n, reg):
    g = 0.35 + 0.45 * ss(0.06, 0.1, p[:, 2]) * ss(-0.02, 0.02, p[:, 1])  # oily T-zone: brow, nose, cheekbones
    g += 0.2 * mottle(p, 40.0, 19)
    return np.where(reg == SCAR, 0.9, np.where(reg == EYE, 1.0, np.where(reg == DARK, 0.75, np.where(reg == BONE, 0.55, g))))


def headgear(variant, f, hb):
    """Per-variant hair / headgear bodies (head frame)."""
    out = []
    sc = scalp(f)
    w = f["w"]
    if variant == "grunt":
        # Shaved scalp stubble + a topknot, bound with a leather thong, its tail down the back.
        tk = PBody(h=0.0016, budget=180)
        tk.add(Chain([(P(0, 0.12, -0.05), 0.024), (P(0, 0.165, -0.075), 0.02), (P(0, 0.17, -0.1), 0.016),
                      (P(0, 0.12, -0.14), 0.013), (P(0, 0.05, -0.15), 0.009)]), HAIR, 0.008)
        tk.add(Ellipsoid(P(0, 0.155, -0.07), (0.022, 0.012, 0.022), rot_x(0.6)), STRAP, 0.003)
        tk.shag(Sphere(P(0, 0.12, -0.1), 0.12), 0.003, Tufts(160, (0, -1, -0.5), seed=52), soft=0.02)
        out.append((tk, None))
    elif variant == "scout":
        # A hood in the warband's colour, the long ear tips pushed out through slits.
        hd = PBody(h=0.0022, budget=320)
        hd.add(offset(sc, 0.018), CLOTH)
        hd.add(Squash(CappedCone(P(0, -0.04, 0), P(0, -0.17, 0), 0.09, 0.15), P(0, 0, -0.018), (1, 1, 0.92)), CLOTH, 0.035)
        hd.add(Cone(P(0, 0.11, -0.1), P(0, 0.03, -0.17), 0.03, 0.01), CLOTH, 0.02)  # the point
        hd.sub(Ellipsoid(P(0, 0.006, 0.105), (0.07 * w, 0.09, 0.08)), CLOTH, 0.012)  # face opening
        for sx in (-1, 1):
            hd.sub(Ellipsoid(P(sx * 0.09 * w, 0.045, -0.05), (0.03, 0.012, 0.02), rot_z(-sx * 0.6)), CLOTH, 0.004)
        hd.shag(Ellipsoid(P(0, -0.12, 0.0), (0.17, 0.07, 0.16)), 0.006, Folds(12, 0.4, -0.06, -0.16), soft=0.03)
        hd.cut(half(P(0, -0.175, 0), (0, 1, 0)))
        out.append((hd, hb.eval))
    elif variant == "berserker":
        # A stiff mohawk, its tips dyed in the warband's colour.
        mh = PBody(h=0.0016, budget=260)
        for i in range(9):
            t = i / 8
            a = -0.4 + t * 2.3
            base = P(0, 0.058 + 0.078 * math.cos(a), -0.03 + 0.1 * math.sin(a) * 0.95)
            outv = P(0, math.cos(a), math.sin(a))
            tip = base + outv * (0.045 - 0.018 * abs(t - 0.4)) + P(0, 0.0, -0.025)
            mh.add(Cone(base - outv * 0.01, tip, 0.012, 0.004), HAIR if t > 0.0 else HAIR, 0.008)
        mh.add(offset(sc, 0.004), HAIR, 0.01).cut(Fn(lambda p: np.abs(p[:, 0]) - 0.016, (-BIG,) * 3, (BIG,) * 3), 0.004)
        mh.shag(Sphere(P(0, 0.1, -0.05), 0.15), 0.002, Tufts(220, (0, 1, -0.6), seed=53), soft=0.02)
        out.append((mh, hb.eval))
        ring_b = PBody(h=0.0009, budget=50)
        ring_b.add(ring([(P(0.0 + 0.009 * math.sin(a), -0.004 + 0.009 * math.cos(a), 0.118), 0.0018)
                         for a in np.linspace(0, 2 * math.pi, 14, endpoint=False)]), IRON)
        out.append((ring_b, None))
    elif variant == "shaman":
        # A beast's upper skull worn as a cap, two curling horns, grey braids and a chin braid.
        bs = PBody(h=0.0018, budget=340)
        bs.add(offset(sc, 0.014), BONE).cut(half(P(0, 0.075, 0), (0, 1, 0.35)))
        bs.add(Ellipsoid(P(0, 0.11, 0.07), (0.05, 0.03, 0.06)), BONE, 0.02)  # snout over the brow
        for sx in (-1, 1):
            bs.sub(Sphere(P(sx * 0.03, 0.115, 0.1), 0.014), BONE, 0.005)  # eye holes
            pts = [P(sx * 0.05, 0.13, -0.01), P(sx * 0.1, 0.17, -0.03), P(sx * 0.13, 0.2, -0.08), P(sx * 0.12, 0.23, -0.13)]
            bs.add(Chain([(pts[0], 0.017), (pts[1], 0.013), (pts[2], 0.009), (pts[3], 0.0035)]), BONE, 0.008)
        bs.cut(half(P(0, 0.04, 0), (0, 1, 0)))
        out.append((bs, sc.eval))
        br = PBody(h=0.0014, budget=220)
        for sx in (-1, 1):
            k = [P(sx * 0.07 * w, 0.02, -0.05), P(sx * 0.075 * w, -0.05, -0.04), P(sx * 0.08 * w, -0.14, -0.01)]
            br.add(Chain([(k[0], 0.011), (k[1], 0.0095), (k[2], 0.007)]), HAIR, 0.005)
            br.add(Sphere(k[2] + P(0, -0.006, 0), 0.008), BONE, 0.003)  # bead
        br.add(Chain([(P(0, -0.085, 0.1), 0.009), (P(0, -0.12, 0.096), 0.007), (P(0, -0.16, 0.088), 0.005)]), HAIR, 0.004)
        br.add(Sphere(P(0, -0.165, 0.088), 0.0065), BONE, 0.003)
        br.shag(Sphere(P(0, -0.05, 0.0), 0.2), 0.0015, Tufts(260, (0, -1, 0), seed=54), soft=0.02)
        out.append((br, None))
        for sx in (-1, 1):  # iron rings in the ears
            rb = PBody(h=0.0008, budget=30)
            c = P(sx * 0.093 * w, 0.03, -0.045)
            rb.add(ring([(c + P(0.0, 0.007 * math.cos(a), 0.007 * math.sin(a)), 0.0016)
                         for a in np.linspace(0, 2 * math.pi, 12, endpoint=False)]), IRON)
            out.append((rb, None))
    return out


_HEADS = {}


def head_body(variant):
    if variant not in _HEADS:
        f = HEADS[variant]
        b = PBody(h=0.0014, budget=950)
        skull(b, f)
        ork_face(b, f, variant)
        _HEADS[variant] = b
    return _HEADS[variant]


def piece_head(variant):
    f = HEADS[variant]
    pc = Piece(f"ork_head_{variant}", "head", "head")
    hb = head_body(variant)
    add_scars(hb, [[(x * f["w"], y, z) for x, y, z in line] for line in HEAD_SCARS[variant]], r=0.0026)
    pc.add(hb)
    pc.add(eyes_body(f))
    pc.add(lids_body(f))
    pc.add(tusks(f, variant))
    for body, cull in headgear(variant, f, hb):
        pc.add(body, cull=cull, depth=0.003)
    pc.weights = weights_for(BUILD_OF[variant])
    pc.weather = lambda p, n, reg: head_tone(p, n, reg, 80 + VARIANTS.index(variant))  # noqa: E731
    pc.extra = head_gloss
    pc.regions = head_paint(variant)
    return pc


# ───────────────────────────────────────────────────────────────── assembly + AO
def outfit(variant):
    """The pieces one variant wears — mirrored by `orks::kit_ork_meshes`."""
    b = BUILD_OF[variant]
    names = [f"ork_trunk_{variant}", f"ork_arm_{b}_l", f"ork_arm_{b}_r", f"ork_leg_{b}_l", f"ork_leg_{b}_r",
             f"ork_head_{variant}", f"ork_kilt_{variant}"]
    names += {
        "grunt": [f"ork_pauldron_{variant}", f"ork_bracer_{b}_l", f"ork_bracer_{b}_r"],
        "berserker": [f"ork_wraps_{b}_l", f"ork_wraps_{b}_r"],
        "scout": [f"ork_strap_{variant}", f"ork_bracer_{b}_l"],
        "shaman": [f"ork_mantle_{variant}"],
    }[variant]
    return names


def all_pieces():
    out = [(lambda v=v: piece_trunk(v)) for v in VARIANTS]
    out += [(lambda b=b, sx=sx: piece_arm(b, sx)) for b in BUILDS for sx in (-1, 1)]
    out += [(lambda b=b, sx=sx: piece_leg(b, sx)) for b in BUILDS for sx in (-1, 1)]
    out += [(lambda v=v: piece_head(v)) for v in VARIANTS]
    out += [(lambda v=v: piece_kilt(v)) for v in VARIANTS]
    out += [lambda: piece_pauldron("grunt"), lambda: piece_strap("scout"), lambda: piece_mantle("shaman")]
    out += [(lambda sx=sx: piece_bracers("heavy", sx, "bracer")) for sx in (-1, 1)]
    out += [lambda: piece_bracers("lean", -1, "bracer")]
    out += [(lambda sx=sx: piece_bracers("heavy", sx, "wraps")) for sx in (-1, 1)]
    return out


_REF = {}


def rig_reference(build):
    """A whole default ork of the build (its first variant's trunk, both arms and legs, a head blob)
    for baking AO into the rig pieces."""
    if build not in _REF:
        v = "grunt" if build == "heavy" else "scout"
        tb = trunk_body(v)
        arms = [arm_body(build, sx) for sx in (-1, 1)]
        legs = [leg_ref(build, sx) for sx in (-1, 1)]
        head = Ellipsoid(P(0, HEAD_Y + 0.02, 0.01), (0.09, 0.11, 0.11))

        def fn(p):
            d = np.minimum(tb.eval(p), head.d(p))
            for a in arms:
                d = np.minimum(d, a.eval(p))
            for lb in legs:
                d = np.minimum(d, lb.eval(p))
            return d
        _REF[build] = fn
    return _REF[build]


def head_reference(variant):
    hb = head_body(variant)
    neck = Cone(P(0, -0.16, -0.014), P(0, 0.04, -0.032), 0.088, 0.07)
    return lambda p: np.minimum(hb.eval(p), neck.d(p))  # noqa: E731


def piece_build(pc):
    """The build whose AO reference a piece bakes against."""
    for b in BUILDS:
        if f"_{b}_" in pc.name or pc.name.endswith(f"_{b}"):
            return b
    for v in VARIANTS:
        if pc.name.endswith(v):
            return BUILD_OF[v]
    return "heavy"


# ───────────────────────────────────────────────────────────────── preview (posed Workbench lineup)
PREVIEW_COLS = {
    SKIN: (0.27, 0.33, 0.16), DARK: (0.12, 0.1, 0.07), BELLY: (0.4, 0.42, 0.25), LEATHER: (0.28, 0.17, 0.09),
    CLOTH: (0.42, 0.1, 0.07), BONE: (0.75, 0.7, 0.55), HAIR: (0.07, 0.05, 0.04), WOOD: (0.3, 0.2, 0.1),
    IRON: (0.4, 0.4, 0.42), ORB: (0.7, 0.5, 1.0), EYE: (0.6, 0.45, 0.05), PAINT: (0.5, 0.1, 0.06),
    SCAR: (0.45, 0.4, 0.3), FUR: (0.25, 0.2, 0.15), NAIL: (0.15, 0.12, 0.08), STRAP: (0.18, 0.11, 0.06),
}


def rest_frames(build):
    sdx, hdx = BUILDS[build]["sdx"], BUILDS[build]["hdx"]

    def T(x, y, z):
        m = np.eye(4)
        m[:3, 3] = (x, y, z)
        return m
    hips = T(0, 1.05, 0)
    torso = hips @ T(0, 0.15, 0)
    neck = torso @ T(0, 0.35, 0)
    head = neck @ T(0, 0.08, 0)
    f = {"hips": hips, "torso": torso, "neck": neck, "head": head}
    for s, sx in (("l", -1), ("r", 1)):
        f[f"sh_{s}"] = torso @ T(sx * sdx, 0.27, 0.01)
        f[f"el_{s}"] = f[f"sh_{s}"] @ T(0, -0.3, 0)
        f[f"hip_{s}"] = hips @ T(sx * hdx, -0.05, 0)
        f[f"knee_{s}"] = f[f"hip_{s}"] @ T(0, -0.4, 0)
        f[f"foot_{s}"] = f[f"knee_{s}"] @ T(0, -0.45, 0)
    return f


PARENT = {"torso": "hips", "neck": "torso", "head": "neck", "sh_l": "torso", "el_l": "sh_l", "sh_r": "torso",
          "el_r": "sh_r", "hip_l": "hips", "knee_l": "hip_l", "foot_l": "knee_l", "hip_r": "hips",
          "knee_r": "hip_r", "foot_r": "knee_r"}


def pose_rot(name, c=0.0):
    """Rough stand-ins for the game's ork clips (`player::anim::ork`), for checking deformation."""
    if name == "idle":
        return {"hips": (euler(0.05, 0, 0), 1.02), "torso": euler(0.16, 0, 0), "head": euler(-0.2, 0, 0),
                "sh_l": euler(-0.1, 0, -0.22), "el_l": euler(-0.35, 0, 0), "sh_r": euler(-0.15, 0, 0.22),
                "el_r": euler(-0.5, 0, 0), "hip_l": euler(-0.12, 0, -0.06), "hip_r": euler(-0.12, 0, 0.06),
                "knee_l": euler(0.22, 0, 0), "knee_r": euler(0.22, 0, 0), "foot_l": euler(-0.1, 0, 0.06),
                "foot_r": euler(-0.1, 0, -0.06)}
    if name == "walk":
        l, r = c, c + math.pi
        return {"hips": (euler(0.06, math.cos(c) * 0.1, math.sin(c) * 0.06), 1.0 + math.sin(2 * c) * 0.02),
                "torso": euler(0.2, -math.cos(c) * 0.14, -math.sin(c) * 0.04), "head": euler(-0.22, 0, 0),
                "hip_l": euler(math.sin(l) * 0.55 - 0.1, 0, -0.06), "hip_r": euler(math.sin(r) * 0.55 - 0.1, 0, 0.06),
                "knee_l": euler(max(0.0, -math.cos(l)) * 1.1 + 0.15, 0, 0),
                "knee_r": euler(max(0.0, -math.cos(r)) * 1.1 + 0.15, 0, 0),
                "foot_l": euler(-math.sin(l) * 0.5, 0, 0), "foot_r": euler(-math.sin(r) * 0.5, 0, 0),
                "sh_l": euler(math.sin(r) * 0.3, 0, -0.22), "el_l": euler(-0.5, 0, 0),
                "sh_r": euler(math.sin(l) * 0.3, 0, 0.22), "el_r": euler(-0.6, 0, 0)}
    if name == "smash":
        return {"hips": (euler(0.1, 0.2, 0), 0.97), "torso": euler(-0.15, 0.3, 0.05), "head": euler(0.0, -0.3, 0),
                "sh_r": euler(-2.7, 0.0, 0.3), "el_r": euler(-1.6, 0, 0), "sh_l": euler(-0.6, 0, -0.3),
                "el_l": euler(-1.0, 0, 0), "hip_l": euler(-0.4, 0, -0.1), "knee_l": euler(0.5, 0, 0),
                "hip_r": euler(0.1, 0, 0.1), "knee_r": euler(0.35, 0, 0)}
    return {}


def skin_matrices(build, pose, c):
    rest = rest_frames(build)
    rot = pose_rot(pose, c)
    glob = {}
    for j in JOINTS:
        local = np.linalg.inv(rest[PARENT[j]]) @ rest[j] if j in PARENT else rest[j].copy()
        r = rot.get(j)
        if j == "hips" and r is not None:
            R, hy = r
            local[:3, :3] = local[:3, :3] @ R
            local[1, 3] = hy
        elif r is not None:
            local[:3, :3] = local[:3, :3] @ r
        glob[j] = glob[PARENT[j]] @ local if j in PARENT else local
    return [glob[j] @ np.linalg.inv(rest[j]) for j in JOINTS]


def preview(objs, weights, out_png, pose="rest", yaw=None, cam=None, sel=None):
    by = {o.name: o for o in objs}
    for o in list(bpy.data.objects):
        if o.get("preview_dup"):
            bpy.data.objects.remove(o)
        elif o.type == "MESH":
            o.hide_render = True
    scene = bpy.context.scene
    vs = sel or list(VARIANTS)
    for i, v in enumerate(vs):
        x0 = (i - (len(vs) - 1) / 2) * 0.95
        build = BUILD_OF[v]
        M = skin_matrices(build, pose, 0.9)
        for nm in outfit(v):
            src = by.get(nm)
            if src is None:
                print("preview: missing", nm)
                continue
            W = weights[nm]
            me = src.data.copy()
            co = np.array([vv.co[:] for vv in me.vertices])
            pg = gm(co)
            if src["frame"] == "head":
                pg = pg + np.array([0.0, HEAD_Y, 0.0])
            ph = np.concatenate([pg, np.ones((len(pg), 1))], 1)
            out = np.zeros((len(pg), 3))
            for j in range(len(JOINTS)):
                wj = W[:, j]
                if wj.max() <= 0:
                    continue
                out += wj[:, None] * (ph @ M[j].T)[:, :3]
            out[:, 0] += x0
            me.vertices.foreach_set("co", bl(out).ravel())
            me.update()
            dup = bpy.data.objects.new(nm + f"_p{i}", me)
            dup["preview_dup"] = 1
            scene.collection.objects.link(dup)
            src_c = me.color_attributes["Col"]
            vals = np.zeros(len(src_c.data) * 4)
            src_c.data.foreach_get("color", vals)
            vals = vals.reshape(-1, 4)
            disp = me.color_attributes.new("Disp", "FLOAT_COLOR", "CORNER")
            outc = []
            for c in vals:
                col = PREVIEW_COLS[min(15, int(c[0] * 16))]
                tn = 0.6 + 0.8 * c[2]
                outc += [col[0] * c[1] * tn, col[1] * c[1] * tn, col[2] * c[1] * tn, 1.0]
            disp.data.foreach_set("color", outc)
            me.color_attributes.active_color = disp
    cam_ob = bpy.data.objects.get("cam")
    if cam_ob is None:
        cam_data = bpy.data.cameras.new("cam")
        cam_data.type = "ORTHO"
        cam_ob = bpy.data.objects.new("cam", cam_data)
        scene.collection.objects.link(cam_ob)
    cx, cz, ow = 0.0, 0.95, 1.0 + 1.0 * len(vs)
    if cam:
        cx, cz, ow = (float(t) for t in cam.split(","))
    cam_ob.data.ortho_scale = ow
    a = math.radians(float(yaw if yaw is not None else 20))
    cam_ob.location = (cx + math.sin(a) * 10, -math.cos(a) * 10, cz)
    cam_ob.rotation_euler = (math.radians(90), 0, a)
    scene.camera = cam_ob
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "VERTEX"
    w, h = (int(t) for t in os.environ.get("ORKS_PREVIEW_RES", "2000,1100").split(","))
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.render.filepath = str(out_png)
    bpy.ops.render.render(write_still=True)
    print(f"PREVIEW {out_png}")


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    only = os.environ.get("ORKS_ONLY")
    DRAFT = float(os.environ.get("ORKS_DRAFT", "1"))  # > 1 coarsens every meshing grid (quick previews)
    clear_scene()
    objs, weights = [], {}
    for fn in all_pieces():
        pc = fn()
        if only and not pc.name.startswith(tuple(only.split(","))):
            continue
        for body, _, _ in pc.bodies:
            body.h *= DRAFT
        if pc.frame == "head":
            ao = head_reference(pc.name.rsplit("_", 1)[1])
        else:
            ao = rig_reference(piece_build(pc))
        ob, W = build_piece(pc, ao)
        objs.append(ob)
        weights[ob.name] = W
        print(f"{ob.name}: {sum(len(p.vertices) - 2 for p in ob.data.polygons)} tris", flush=True)
    if os.environ.get("ORKS_NO_EXPORT") != "1" and not only:
        export_glb(OUT / "orks.glb", objs, tangents=False)
    for spec in argv:
        parts = spec.split("|")
        sel = parts[4].split("+") if len(parts) > 4 and parts[4] else None
        preview(objs, weights, Path(parts[0]).resolve(), parts[1] if len(parts) > 1 else "rest",
                float(parts[2]) if len(parts) > 2 and parts[2] else None, parts[3] if len(parts) > 3 and parts[3] else None, sel)
    print("ORKS_DONE")
