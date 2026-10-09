"""Organic quadruped parts for the shared quadruped rig (quadruped.rs) -> animals.glb.

Same contract as creatures.py: one mesh per joint (spine, neck, head, tail, upper leg, lower leg,
paw), authored in the joint's local frame with the dimensions of the species table in
quadruped.rs (`quad_config`), so the animation clips keep working. Metaball muscle masses,
decimated. Vertex colour R = region (FUR, BELLY, ACCENT, DETAIL, EYE) / 16, G = cavity.
"""
import math
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
from mathutils import Vector  # noqa: E402
from common import OUT, clear_scene, export_glb  # noqa: E402
from creatures import Part, build_part  # noqa: E402

FUR, BELLY, ACCENT, DETAIL, EYE = range(5)

# (body w,h,l), chest_z, neck_h, neck_w, head(w,h,l), snout(w,h,l), leg_upper, leg_lower, leg_w,
# paw_w, paw_h, tail_h, ears, antlers, hump, shoulder_hump, mane, collar, build (slender .. heavy)
SPECIES = {
    "dog": dict(body=(0.26, 0.26, 0.55), chest_z=0.25, neck_h=0.25, neck_w=0.16, head=(0.2, 0.2, 0.22),
                snout=(0.12, 0.1, 0.15), lu=0.18, ll=0.18, lw=0.07, paw_w=0.09, paw_h=0.05, tail_h=0.25,
                ears="pointed", collar=True, build=0.55, fluffy_tail=0.6),
    "wolf": dict(body=(0.24, 0.22, 0.62), chest_z=0.28, neck_h=0.28, neck_w=0.14, head=(0.19, 0.17, 0.22),
                 snout=(0.09, 0.08, 0.22), lu=0.2, ll=0.2, lw=0.07, paw_w=0.08, paw_h=0.05, tail_h=0.32,
                 ears="pointed", build=0.55, fluffy_tail=1.0, ruff=True),
    "horse": dict(body=(0.3, 0.28, 0.72), chest_z=0.32, neck_h=0.38, neck_w=0.18, head=(0.18, 0.2, 0.28),
                  snout=(0.1, 0.08, 0.2), lu=0.28, ll=0.26, lw=0.07, paw_w=0.1, paw_h=0.05, tail_h=0.35,
                  ears="long", mane=True, build=0.6, hooves=True, horse_tail=True),
    "deer": dict(body=(0.2, 0.2, 0.58), chest_z=0.26, neck_h=0.22, neck_w=0.12, head=(0.14, 0.16, 0.2),
                 snout=(0.08, 0.07, 0.12), lu=0.22, ll=0.22, lw=0.07, paw_w=0.06, paw_h=0.04, tail_h=0.12,
                 ears="long", antlers=True, build=0.4, hooves=True),
    "camel": dict(body=(0.28, 0.26, 0.7), chest_z=0.3, neck_h=0.42, neck_w=0.14, head=(0.16, 0.16, 0.22),
                  snout=(0.09, 0.08, 0.14), lu=0.3, ll=0.28, lw=0.07, paw_w=0.1, paw_h=0.05, tail_h=0.15,
                  ears="round", hump=True, build=0.5, hooves=True),
    "bear": dict(body=(0.46, 0.42, 0.78), chest_z=0.26, neck_h=0.1, neck_w=0.26, head=(0.32, 0.27, 0.32),
                 snout=(0.2, 0.14, 0.18), lu=0.16, ll=0.15, lw=0.18, paw_w=0.18, paw_h=0.08, tail_h=0.08,
                 ears="round", shoulder_hump=True, build=1.0),
}


def spine(name, s):
    p = Part(f"q_{name}_spine")
    bw, bh, bl = s["body"]
    b = s["build"]
    # Ribcage (front), barrel, hindquarters (back) fused; belly sags a little.
    p.ell(FUR, (0, 0.01, bl * 0.22), (bw * 0.52, bh * 0.55, bl * 0.3))
    p.ell(FUR, (0, -0.01, 0.0), (bw * 0.47, bh * 0.5, bl * 0.36))
    p.ell(FUR, (0, 0.01, -bl * 0.27), (bw * 0.5, bh * 0.52, bl * 0.25))
    p.ell(BELLY, (0, -bh * 0.3, 0.02), (bw * 0.38, bh * 0.25, bl * 0.34))
    for sx in (-1, 1):
        p.ball(FUR, (sx * bw * 0.28, bh * 0.1, bl * 0.3), bh * 0.27 * (0.8 + 0.2 * b))  # shoulder
        p.ball(FUR, (sx * bw * 0.28, bh * 0.06, -bl * 0.33), bh * 0.29 * (0.8 + 0.2 * b))  # haunch
    if s.get("hump"):
        p.ell(FUR, (0, bh * 0.55, -0.05), (0.13, 0.12, 0.17))
    if s.get("shoulder_hump"):
        p.ell(FUR, (0, bh * 0.45, bl * 0.22), (bw * 0.42, 0.1, bl * 0.2))
    return p, 1100


def neck(name, s):
    p = Part(f"q_{name}_neck")
    h, w = s["neck_h"], s["neck_w"]
    p.cap(FUR, (0, -0.06, -0.02), (0, h, 0.02), w * 0.5)
    p.ball(FUR, (0, 0.0, 0.0), w * 0.62)
    if s.get("ruff"):
        p.ell(FUR, (0, h * 0.35, 0.02), (w * 0.75, h * 0.45, w * 0.7))
    if s.get("mane"):
        for k in range(7):
            t = k / 6
            p.ell(ACCENT, (0, h * (0.05 + 0.9 * t), -w * 0.45), (0.025, 0.05, 0.035))
    if s.get("collar"):
        p.cap(ACCENT, (-w * 0.55, h * 0.75, 0), (w * 0.55, h * 0.75, 0), 0.022)
        p.ell(ACCENT, (0, h * 0.75, 0), (w * 0.58, 0.025, w * 0.58))
    return p, 500


def head(name, s):
    p = Part(f"q_{name}_head")
    hw, hh, hl = s["head"]
    sw, sh, sl = s["snout"]
    p.ell(FUR, (0, 0.0, hl * 0.15), (hw * 0.5, hh * 0.5, hl * 0.5))
    snout_c = (0, -sh * 0.4, hl * 0.5 + sl * 0.45)
    p.ell(BELLY if name != "horse" else FUR, snout_c, (sw * 0.5, sh * 0.5, sl * 0.55))
    p.cap(FUR, (0, hh * 0.1, hl * 0.3), snout_c, min(sw, sh) * 0.42)  # bridge of the nose
    p.ball(DETAIL, (0, snout_c[1] + sh * 0.12, hl * 0.5 + sl * 0.98), max(sw * 0.22, 0.022))  # nose
    ex, ey, ez = hw * 0.36, hh * 0.12, hl * 0.42
    for sx in (-1, 1):
        p.ball(EYE, (sx * ex, ey, ez), max(hw * 0.075, 0.012))
        ears = s.get("ears")
        if ears == "long":
            p.ell(FUR, (sx * hw * 0.55, hh * 0.45, -0.03), (0.022, 0.075, 0.035))
        elif ears == "pointed":
            p.cap(FUR, (sx * hw * 0.3, hh * 0.36, -0.03), (sx * hw * 0.4, hh * 0.6, -0.045), 0.028)
        else:
            p.ball(FUR if name != "camel" else ACCENT, (sx * hw * 0.42, hh * 0.42, -0.04), hw * 0.13)
        if s.get("antlers"):
            base = Vector((sx * 0.05, hh * 0.45, -0.01))
            tip = base + Vector((sx * 0.09, 0.2, -0.05))
            p.cap(DETAIL, tuple(base), tuple(tip), 0.013)
            for t, (dx, dy, dz) in ((0.4, (sx * 0.05, 0.07, 0.06)), (0.7, (sx * 0.0, 0.08, 0.07)), (1.0, (sx * 0.06, 0.06, -0.03))):
                q = base.lerp(tip, t)
                p.cap(DETAIL, tuple(q), tuple(q + Vector((dx, dy, dz))), 0.009)
    return p, 900


def tail(name, s):
    p = Part(f"q_{name}_tail")
    h = s["tail_h"]
    if s.get("horse_tail"):
        p.cap(ACCENT, (0, 0, 0), (0, h * 0.4, -0.02), 0.035)
        p.ell(ACCENT, (0, h * 0.6, -0.04), (0.05, h * 0.45, 0.04))
    else:
        f = s.get("fluffy_tail", 0.0)
        p.cap(FUR, (0, 0, 0), (0, h, 0), 0.022 + 0.01 * f)
        if f:
            p.ell(FUR, (0, h * 0.6, 0), (0.035 * f + 0.02, h * 0.45, 0.035 * f + 0.02))
    return p, 300


def leg_upper(name, s):
    p = Part(f"q_{name}_leg_upper")
    lu, lw, b = s["lu"], s["lw"], s["build"]
    p.ball(FUR, (0, 0.02, 0), lw * (0.62 + 0.08 * b))
    p.cap(FUR, (0, 0.0, 0), (0, -lu, 0.0), lw * 0.42)
    p.ball(FUR, (0, -lu * 0.25, 0.01), lw * 0.5)
    p.ball(FUR, (0, -lu, 0), lw * 0.34)
    return p, 450


def leg_lower(name, s):
    p = Part(f"q_{name}_leg_lower")
    ll, lw, b = s["ll"], s["lw"], s["build"]
    r = lw * (0.28 + 0.2 * b)
    p.ball(FUR, (0, 0.0, 0), r * 1.05)  # joint
    p.cap(FUR, (0, 0.0, 0), (0, -ll, 0.0), r)
    p.ball(FUR, (0, -ll * 0.15, -0.005), r * 1.15)
    return p, 350


def paw(name, s):
    p = Part(f"q_{name}_paw")
    pw, ph = s["paw_w"], s["paw_h"]
    if s.get("hooves"):
        p.ell(DETAIL, (0, -ph * 0.5, 0.01), (pw * 0.42, ph * 0.6, pw * 0.5))
        p.ball(FUR, (0, 0.0, 0), pw * 0.32)
    else:
        p.ell(FUR, (0, -ph * 0.45, 0.02), (pw * 0.5, ph * 0.55, pw * 0.62))
        for k in range(4):
            p.ball(DETAIL, (-pw * 0.27 + k * pw * 0.18, -ph * 0.8, pw * 0.42), pw * 0.08)
    return p, 300


clear_scene()
objs = []
for name, s in SPECIES.items():
    for fn in (spine, neck, head, tail, leg_upper, leg_lower, paw):
        part, budget = fn(name, s)
        ob = build_part(part, budget, res=0.008)
        objs.append(ob)
    print(f"{name}: done")
export_glb(OUT / "animals.glb", objs)
print("ANIMALS_DONE")
