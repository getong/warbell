"""Realistic snowmen -> snowmen.glb (snowman.rs ambushers + the rare biome_snow decor snowman).

Rolled, hand-packed snow on the s_snow scan (snow_02), not three toy spheres:
- each ball is a little oblate and lumpy from the packing, with faint leaf-litter streaks banded
  around its roll axis (the big one picked up the most); the base is pressed flat into the ground
  and each upper ball is seated down INTO the one below (pushed on and twisted to bed in), so every
  joint is a tight crease with a thin, uneven fillet of hand-packed snow - not stacked discs;
- coal eyes, a coal smile and coal buttons pressed in proud enough to read from across a
  clearing, a bent carrot pushed into the face, forked sticks pushed deep into the middle ball;
- a low ring of trampled snow around the foot whose rim dives below y=0, so on a slope the
  downhill side still meets the ground.

    snowman_a  the classic: carrot, stick arms, a faded striped wool scarf.
    snowman_b  the bucket-head: an upturned, rust-streaked iron pail (bail handle folded down the
               side) with snow settled on its bottom.
    snowman_c  the kids' one: small and lopsided, lumpy, short twig arms (one waving), a crooked
               smile, somebody's red knitted cap with a bobble.

Built facing +Z, base at y=0, ~1.3u to the crown (the kids' one ~0.9u; hero ~1.8u); the ambushers
scale it 1.0-1.28. Bottom ball r 0.40 = snowman.rs BODY_R.

    blender -b --factory-startup --python tools/blender_forest/snowmen.py
"""
import math
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402
from common import OUT, clear_scene, export_glb  # noqa: E402
from geo import G, quat_x, quat_y, quat_z  # noqa: E402
from meshkit import Builder  # noqa: E402
import wayside_models as W  # noqa: E402
from wayside_models import (M_BARK, M_CLOTH, M_IRON, M_ROCK, M_FRUIT, V, Noise, bounds, icosphere, mix,  # noqa: E402
                            pole, scale, smooth_mesh, smoothstep, stone, tube)

M_SNOW = len(W.MATS)
MATS = W.MATS + ["s_snow"]

PACKED = (0.97, 0.98, 1.0)     # hand-packed snow (the s_snow scan already carries the grain)
SHADE = (0.78, 0.85, 0.98)     # sky-lit undersides
LITTER = (0.5, 0.45, 0.36)     # rolled-in needles / leaf litter / earth
COAL = (0.09, 0.085, 0.08)
CARROT = (0.86, 0.4, 0.09)
STICK = (0.5, 0.42, 0.34)
IRON = (0.4, 0.38, 0.36)
RUST = (0.46, 0.26, 0.13)
BEND = 0.85                    # how far the snow's shading normals lean toward the sky


# ─────────────────────────────────────────────────────────────── snow
def snow_col(centre, nz, base=PACKED, litter=0.0, axis=None, joints=(), ground=0.0):
    """Snow tint: cool on the undersides, darker in the creases between balls and at the ground,
    optional rolled-in litter banded around the roll `axis` (only where specks fall)."""
    c0 = Vector(centre)

    def f(p, n):
        k = 0.95 + 0.05 * nz(p * 2.3)
        col = mix(base, SHADE, (1.0 - smoothstep(-0.25, 0.7, n.y)) * 0.35)
        ao = 1.0 - 0.18 * (1.0 - smoothstep(-0.04, 0.16, p.y - ground))
        for jy in joints:
            ao *= 1.0 - 0.16 * (1.0 - smoothstep(0.0, 0.07, abs(p.y - jy)))
        if litter > 0.0:
            d = (p - c0).normalized().dot(axis)
            band = smoothstep(0.62, 0.95, 0.5 + 0.5 * math.sin(d * 11.0 + 2.2 * nz(p * 1.3)))
            speck = smoothstep(0.25, 0.75, nz(p * 11.0))
            col = mix(col, LITTER, 0.6 * litter * band * speck * (1.0 - smoothstep(-0.2, 0.6, d)))
        return scale(col, k * ao)
    return f


def snowball(g, centre, r, rng, squash=0.92, lo=0.8, hi=1.5, lumps=0.045, tilt=(0.0, 0.0), litter=0.0,
             joints=(), base=PACKED, detail=3, pats=4):
    """A rolled snowball: oblate (`squash` on Y), flattened at unit height -`lo` (the base, where it
    was pressed into the ground; `hi` likewise on top, off by default), low packing lumps and a few
    shallow flats where a gloved hand patted it firm."""
    verts, faces = icosphere(detail)
    nz = Noise(rng, 4, 1.5)
    fine = Noise(rng, 3, 7.0)
    rot = quat_x(tilt[0]) @ quat_z(tilt[1])
    flats = []
    for _ in range(pats):
        d = Vector((rng.normal(), rng.uniform(-0.3, 0.5), rng.normal())).normalized()
        flats.append((d, rng.uniform(0.95, 0.98)))
    out = []
    for v in verts:
        k = 1.0 + lumps * nz(v) + 0.01 * fine(v)
        p = Vector((v.x * k, v.y * k, v.z * k))
        for d, c in flats:
            e = p.dot(d) - c
            if e > 0:
                p -= d * e * 0.85
        if p.y < -lo:
            p.y = -lo + (p.y + lo) * 0.12
        if p.y > hi:
            p.y = hi + (p.y - hi) * 0.12
        out.append(Vector(centre) + rot @ Vector((p.x * r, p.y * r * squash, p.z * r)))
    axis = Vector(rng.normal(size=3)).normalized()
    col = snow_col(centre, Noise(rng, 4, 2.0), base=base, litter=litter, axis=axis, joints=joints)
    wrapped_mesh(g, out, faces, M_SNOW, col, Vector(centre), r, 0.9)


def wrapped_mesh(g, verts, tris, mat, col_fn, centre, r, tile, planar=False):
    """`smooth_mesh` for a ball, but UV'd by a cylindrical wrap around Y (one seam, at the back)
    instead of per-face box projection, whose axis switches showed as seams in the snow scan;
    `planar` maps top-down instead (mounds). `centre` is a point inside, for the winding."""
    tris = list(tris)
    for i, (a, b, d) in enumerate(tris):
        n = (verts[b] - verts[a]).cross(verts[d] - verts[a])
        if n.dot((verts[a] + verts[b] + verts[d]) / 3 - centre) < 0:
            tris[i] = (a, d, b)
    vn = [Vector((0, 0, 0)) for _ in verts]
    for a, b, d in tris:
        n = (verts[b] - verts[a]).cross(verts[d] - verts[a])
        for i in (a, b, d):
            vn[i] += n
    vn = [n.normalized() if n.length > 1e-12 else Vector((0, 1, 0)) for n in vn]
    cols = [col_fn(verts[i], vn[i]) for i in range(len(verts))]
    # Sky-bent shading normals (like the tree cards' crown-bent ones): real snow scatters light
    # through itself and is lit by the snow all around it, so a snowman's flanks never go as dark
    # as a hard sphere's under the game's sky IBL; they read grey-brown next to the ground snow.
    vn = [(n + Vector((0.0, BEND, 0.0))).normalized() for n in vn]
    period = 2 * math.pi * r / tile
    if planar:
        uv = [(v.x / tile, v.z / tile) for v in verts]
        period = 1e9
    else:
        uv = [(math.atan2(v.x - centre.x, v.z - centre.z) * r / tile, v.y / tile) for v in verts]
    for a, b, d in tris:
        us = [uv[a], uv[b], uv[d]]
        if max(u for u, _ in us) - min(u for u, _ in us) > period * 0.5:
            us = [(u + period, v) if u < 0 else (u, v) for u, v in us]
        g.poly([verts[a], verts[b], verts[d]], us, [vn[a], vn[b], vn[d]], [cols[a], cols[b], cols[d]], mat)


def snow_mound(g, centre, rx, rz, h, rng, col_fn, tile=0.9, rings=6, seg=20, skirt=0.1, rough=0.12, edge=0.12,
               power=0.8, mat=None):
    """`wayside_models.mound` in snow: the same polar dome, sky-bent normals + top-down UVs."""
    nz = Noise(rng, 4, 2.0)
    cx, cy, cz = centre
    verts = [Vector((cx, cy + h, cz))]
    for j in range(1, rings + 1):
        f = j / rings
        for i in range(seg):
            a = 2 * math.pi * i / seg
            e = 1.0 + edge * nz(Vector((math.cos(a), 0, math.sin(a))) * 1.3 + Vector((0, 3.1, 0)))
            x = cx + math.cos(a) * rx * f * e
            z = cz + math.sin(a) * rz * f * e
            y = cy + h * (max(0.0, 1 - f * f) ** power) * (1 + rough * nz(Vector((x, 0, z)) * 2.0)) - skirt * f ** 6
            verts.append(Vector((x, y, z)))
    tris = [(0, 1 + (i + 1) % seg, 1 + i) for i in range(seg)]
    for j in range(rings - 1):
        r0, r1 = 1 + j * seg, 1 + (j + 1) * seg
        for i in range(seg):
            a, b = r0 + i, r0 + (i + 1) % seg
            c, d = r1 + (i + 1) % seg, r1 + i
            tris += [(a, b, c), (a, c, d)]
    wrapped_mesh(g, verts, tris, M_SNOW, col_fn, Vector((cx, cy - 50.0, cz)), 1.0, tile, planar=True)


# ─────────────────────────────────────────────────────────────── the stack
def rho(b, y):
    """Horizontal radius of ball `b` (its smooth ellipsoid, lumps ignored) at height `y`."""
    t = (y - b["c"].y) / (b["r"] * b["sq"])
    return b["r"] * math.sqrt(max(0.0, 1.0 - t * t))


def stack(radii, squash, sink=(0.05, 0.24, 0.22), litter=(0.5, 0.25, 0.1), lumps=(0.05, 0.045, 0.04),
          offsets=((0, 0), (0, 0), (0, 0)), tilts=((0, 0), (0, 0), (0, 0))):
    """Three balls: the base pressed `sink[0]` (world u) into the ground with a flat underside, each
    upper ball seated `sink[i]` of its own half-height down into the top of the one below. Returns
    the balls and the joints as (crease height, contact-ring radius, ring centre)."""
    balls = []
    for i in range(3):
        hh = radii[i] * squash[i]
        if i == 0:
            lo = 0.8
            cy = -sink[0] + lo * hh
        else:
            lo = 1.5
            below = balls[-1]
            cy = below["c"].y + below["r"] * below["sq"] + hh * (1.0 - sink[i])
        balls.append(dict(c=V(offsets[i][0], cy, offsets[i][1]), r=radii[i], sq=squash[i], lo=lo,
                          lit=litter[i], lumps=lumps[i], tilt=tilts[i]))
    joints = []
    for i in range(2):
        lower, upper = balls[i], balls[i + 1]
        a = upper["c"].y - upper["r"] * upper["sq"]
        b = lower["c"].y + lower["r"] * lower["sq"]
        for _ in range(40):  # rho(lower) falls, rho(upper) rises across [a, b]: bisect the crossing
            m = 0.5 * (a + b)
            if rho(lower, m) > rho(upper, m):
                a = m
            else:
                b = m
        y = 0.5 * (a + b)
        joints.append((y, rho(lower, y), (lower["c"] + upper["c"]) * 0.5))
    return balls, joints


def body(g, rng, balls, joints, base=PACKED):
    creases = [j[0] for j in joints]
    for b in balls:
        snowball(g, b["c"], b["r"], rng, squash=b["sq"], lo=b["lo"], lumps=b["lumps"], tilt=b["tilt"],
                 litter=b["lit"], joints=creases, base=base)
    # A thin, uneven fillet of hand-packed snow in each crease (thick where a mitten smoothed it,
    # gone elsewhere) - the balls read pressed together, not balanced.
    nz = Noise(rng, 3, 3.0)
    for i, (cy, rr, mid) in enumerate(joints):
        tr = (0.032 if i == 0 else 0.022) * balls[i + 1]["r"] / 0.29
        pts, radii = [], []
        for k in range(25):
            a = 2 * math.pi * k / 24
            pts.append(V(mid.x + math.cos(a) * rr * 0.97, cy + 0.006 * nz(Vector((a, 0.3, 1.0))),
                         mid.z + math.sin(a) * rr * 0.97))
            radii.append(tr * (0.35 + 0.65 * smoothstep(-0.5, 0.6, nz(Vector((math.cos(a), 0.0, math.sin(a)))))))
        pts[-1], radii[-1] = pts[0], radii[0]
        tube(g, pts, radii, 6, M_SNOW, scale(PACKED, 0.93), tile=0.9, cap=False)


def skirt(g, rng, ball, h=0.06, grow=1.3):
    """Trampled snow ringing the foot. Its rim dives well below y=0, so on a slope the downhill
    side still meets the ground instead of showing a gap under the snowman."""
    nz = Noise(rng, 4, 1.5)
    rx = ball["r"] * grow
    snow_mound(g, (ball["c"].x, -0.03, ball["c"].z), rx, rx * 0.93, h, rng, mat=M_SNOW,
               col_fn=snow_col((0.0, -1.0, 0.0), nz, ground=-0.3), tile=0.9, rings=5, seg=22,
               skirt=0.35, rough=0.15, edge=0.14, power=1.6)


def on_ball(b, d, inset=0.0):
    """Point on ball `b`'s surface along direction `d` (from its centre), pushed `inset` inward."""
    d = Vector(d).normalized()
    r, sq = b["r"], b["sq"]
    t = 1.0 / math.sqrt((d.x / r) ** 2 + (d.y / (r * sq)) ** 2 + (d.z / r) ** 2)
    return b["c"] + d * (t - inset)


# ─────────────────────────────────────────────────────────────── features
def coal(g, p, s, rng):
    """A lump of hearth coal pressed into the snow (about half of it proud)."""
    stone(g, tuple(p), (s, s * 0.9, s * 0.8), rng, mat=M_ROCK, col_fn=lambda q, n: scale(COAL, 0.8 + 0.4 * max(0.0, n.y)),
          detail=1, rough=0.22, cuts=1, tile=0.25)


def face(g, rng, head, yaw=0.0, eye=0.034, eye_x=0.3, eye_y=0.32, mouth=5, smile=0.08, mouth_y=-0.4, coal_s=0.022,
         wonky=0.0, carrot=0.24):
    q = quat_y(yaw)

    def at(x, y, inset):
        return on_ball(head, q @ Vector((x, y, 1.0)), inset)
    for side in (1, -1):
        s = eye * (1.0 + wonky * rng.uniform(-0.4, 0.4))
        coal(g, at(side * eye_x, eye_y + wonky * rng.uniform(-0.08, 0.08), s * 0.45), s, rng)
    for k in range(mouth):
        t = k / max(mouth - 1, 1) * 2 - 1
        y = mouth_y - smile * (1 - t * t) + wonky * rng.uniform(-0.05, 0.05)
        coal(g, at(t * 0.3, y, coal_s * 0.4), coal_s * (0.85 + 0.3 * rng.uniform()), rng)
    # The carrot, pushed a good way into the face and drooping a touch under its own weight.
    base = at(0.0, 0.0, 0.06)
    fwd = (q @ Vector((rng.uniform(-0.06, 0.06), -0.02, 1.0))).normalized()
    n = 7
    pts = [base + fwd * ((carrot + 0.06) * k / n) + Vector((0.0, -0.03 * (k / n) ** 2, 0.0)) for k in range(n + 1)]
    radii = [0.034 * (carrot / 0.24) ** 0.5 * (1 - k / n) ** 0.85 + 0.003 for k in range(n + 1)]
    tube(g, pts, radii, 8, M_FRUIT, CARROT, tile=0.2,
         col_fn=lambda t: scale(CARROT, 0.82 + 0.18 * (0.5 + 0.5 * math.sin(t * 38.0)) - 0.12 * t))


def buttons(g, rng, mid, n=3, yaw=0.0, s=0.03, top=0.45, step=0.36):
    q = quat_y(yaw)
    for k in range(n):
        y = top - k * step
        coal(g, on_ball(mid, q @ Vector((rng.uniform(-0.03, 0.03), y, 1.0)), s * 0.4), s * (0.9 + 0.2 * rng.uniform()),
             rng)


def stick_arm(g, rng, mid, side, lift=0.25, length=0.62, forks=2, fwd=0.0, r0=0.02):
    """A forked stick pushed deep into the middle ball's flank, angled out (`lift` up, negative
    down) with one natural kink, a side fork or two and a three-twig hand."""
    shoulder = on_ball(mid, (side, 0.15, fwd), 0.13)
    d = Vector((side * 0.9, lift, fwd + rng.uniform(-0.12, 0.12))).normalized()
    kink = (quat_z(side * rng.uniform(-0.25, 0.25)) @ quat_y(rng.uniform(-0.25, 0.25)) @ d).normalized()
    elbow = shoulder + d * (length * 0.55 + 0.13)
    tip = elbow + kink * (length * 0.45)
    pole(g, shoulder, elbow, r0, r0 * 0.75, rng, col=STICK, sides=6, segs=3, wobble=0.006, tile=0.35)
    pole(g, elbow - d * 0.01, tip, r0 * 0.75, r0 * 0.4, rng, col=STICK, sides=5, segs=3, wobble=0.006, tile=0.35)
    for f in range(forks):
        t = 0.45 + 0.4 * f + rng.uniform(-0.05, 0.05)
        p = elbow + kink * (length * 0.45 * t) if f else shoulder + d * ((length * 0.55 + 0.13) * (0.55 + 0.4 * t))
        a = (0.6 + rng.uniform(-0.1, 0.15)) * (1 if f % 2 else -1)
        fd = (quat_z(a * side) @ quat_y(rng.uniform(-0.4, 0.4)) @ (kink if f else d)).normalized()
        pole(g, p, p + fd * rng.uniform(0.11, 0.19) * length / 0.62, r0 * 0.45, r0 * 0.2, rng, col=STICK, sides=4,
             segs=2, wobble=0.004, tile=0.3)
    for k in range(3):
        fd = (quat_z((k - 1) * 0.5 * side) @ quat_y(rng.uniform(-0.3, 0.3)) @ kink).normalized()
        pole(g, tip - kink * 0.005, tip + fd * rng.uniform(0.05, 0.09) * length / 0.62, r0 * 0.3, r0 * 0.15, rng,
             col=STICK, sides=4, segs=1, wobble=0.0, tile=0.3)


def scarf(g, rng, mid, head, joint):
    """A faded striped wool scarf wound at the neck, knot on the left front, two tails down the chest."""
    nz = Noise(rng, 3, 5.0)
    cy, _, c = joint

    def stripes(t):
        return (0.5, 0.16, 0.12) if int(t * 9) % 3 else (0.76, 0.7, 0.58)
    for turn, (dy, rr) in enumerate(((-0.005, 0.04), (0.042, 0.034))):
        y = cy + dy
        neck_r = max(rho(mid, y), rho(head, y)) + rr * 0.55
        pts = []
        for k in range(21):
            a = 2 * math.pi * k / 20
            w = 1.0 + 0.05 * nz(Vector((math.cos(a), turn, math.sin(a))))
            pts.append(V(c.x + math.cos(a) * neck_r * w, y + 0.01 * math.sin(a * 2 + turn), c.z + math.sin(a) * neck_r * w))
        pts[-1] = pts[0]
        tube(g, pts, [rr] * len(pts), 7, M_CLOTH, (0.5, 0.16, 0.12), tile=0.25, cap=False,
             col_fn=lambda t: stripes(t * 4.0))
    # Knot + tails hanging over the mid ball (following its surface, a little lifted off it).
    ka = math.radians(62)
    kr = max(rho(mid, cy), rho(head, cy)) + 0.045
    knot = V(c.x + math.cos(ka) * kr, cy + 0.01, c.z + math.sin(ka) * kr)
    stone(g, tuple(knot), (0.045, 0.04, 0.04), rng, mat=M_CLOTH, col_fn=lambda q, n: (0.48, 0.15, 0.11), detail=1,
          rough=0.2, cuts=0, tile=0.2)
    for j, (spread, length) in enumerate(((0.1, 0.34), (-0.08, 0.27))):
        pts = [knot]
        for k in range(1, 6):
            t = k / 5
            d = Vector((math.cos(ka) + spread * t, 0.5 - 1.1 * t * length / 0.34, math.sin(ka) + 0.15))
            pts.append(on_ball(mid, d, -0.028 - 0.008 * t))
        n_len = len(pts)
        tube(g, pts, [0.03 - 0.004 * (k / n_len) for k in range(n_len)], 6, M_CLOTH, (0.5, 0.16, 0.12), tile=0.25,
             col_fn=lambda t, j=j: stripes(t * length * 3 + j * 0.3))
        end = pts[-1]
        for f in range(4):
            fp = end + Vector(((f - 1.5) * 0.012, 0.0, 0.0))
            pole(g, fp, fp + Vector((0.0, -0.05, 0.01)), 0.005, 0.003, rng, mat=M_CLOTH, col=(0.74, 0.68, 0.56),
                 sides=3, segs=1, wobble=0.0, tile=0.2)


def lathe(g, prof, centre, rot, sides, mat, col_fn, tile, dent=None):
    """Surface of revolution (profile (r, y) top -> down, winding outward for a profile that runs
    out and down; a profile that turns back in/up faces down/in - right for a hat's underside)."""
    verts = []
    for r, y in prof:
        for i in range(sides):
            a = 2 * math.pi * i / sides
            p = Vector((math.cos(a) * r, y, math.sin(a) * r))
            if dent and r > 0.02:
                p += Vector((math.cos(a), 0.0, math.sin(a))) * dent(p)
            verts.append(Vector(centre) + rot @ p)
    tris = []
    for j in range(len(prof) - 1):
        for i in range(sides):
            a, b = j * sides + i, j * sides + (i + 1) % sides
            c, d = (j + 1) * sides + (i + 1) % sides, (j + 1) * sides + i
            tris += [(a, b, c), (a, c, d)]
    smooth_mesh(g, verts, tris, mat, col_fn, tile)


def ring(g, centre, rot, r, y, tr, mat, col, sides=6, seg=28):
    pts = [Vector(centre) + rot @ Vector((math.cos(a) * r, y, math.sin(a) * r))
           for a in (2 * math.pi * k / seg for k in range(seg + 1))]
    tube(g, pts, [tr] * len(pts), sides, mat, col, tile=0.2, cap=False)


def bucket_hat(g, rng, head):
    """An old iron pail jammed upside-down on the head, tipped back and to one side: two hoops,
    a dent, rust streaks running down from the (now upward) bottom, the bail handle folded down
    along its side and a pillow of snow settled on top."""
    nz = Noise(rng, 4, 3.0)
    top = head["c"].y + head["r"] * head["sq"]
    rim_y = top - 0.075
    H, r_top = 0.2, 0.112
    r_open = rho(head, rim_y) + 0.008
    centre = V(head["c"].x, rim_y, head["c"].z + 0.005)
    rot = quat_x(-0.14) @ quat_z(0.1)
    wall = 0.009

    def rad(y):
        return r_open + (r_top - r_open) * y / H
    outer = [(0.0, H), (r_top * 0.7, H), (r_top - 0.004, H - 0.002), (r_top, H - 0.012), (rad(0.12), 0.12),
             (rad(0.05), 0.05), (r_open + 0.006, 0.006), (r_open + 0.008, -0.004)]
    inner = [(r_open - wall, -0.004), (r_open - wall, 0.01), (rad(0.12) - wall, 0.12), (r_top - wall, H - 0.014),
             (0.0, H - 0.014)]
    dent_c = Vector((0.07, 0.13, 0.09))

    def dent(p):
        return -0.022 * math.exp(-((p - dent_c).length / 0.045) ** 2) + 0.002 * nz(p * 2.0)

    def iron(p, n):
        lp = rot.inverted() @ (p - centre)
        streak = smoothstep(0.1, 0.7, nz(Vector((lp.x * 9.0, lp.y * 0.6, lp.z * 9.0))) + 0.4 * lp.y / H)
        return scale(mix(IRON, RUST, 0.15 + 0.5 * streak), 0.7 + 0.25 * smoothstep(-0.2, 0.8, n.y))
    lathe(g, outer + inner, centre, rot, 22, M_IRON, iron, 0.3, dent=dent)
    for y in (0.045, H - 0.04):
        ring(g, centre, rot, rad(y) + 0.003, y, 0.0055, M_IRON, scale(IRON, 0.55))
    # Bail handle folded down the side wall, hinged on two lugs.
    for s in (1, -1):
        stone(g, tuple(centre + rot @ Vector((s * (rad(0.15) + 0.008), 0.15, 0.0))), (0.012, 0.016, 0.012), rng,
              mat=M_IRON, col_fn=lambda q, n: scale(RUST, 0.8), detail=0, rough=0.1, cuts=0, tile=0.2)
    pts = []
    for k in range(13):
        a = math.pi * k / 12
        y = 0.15 - 0.11 * math.sin(a)
        r = rad(y) + 0.012
        pts.append(centre + rot @ Vector((math.cos(a) * r, y, -math.sin(a) * r)))
    tube(g, pts, [0.0045] * len(pts), 5, M_IRON, scale(IRON, 0.6), tile=0.2, cap=True)
    snow_mound(g, tuple(centre + rot @ Vector((0.0, H - 0.004, 0.0))), r_top * 0.95, r_top * 0.9, 0.04, rng,
               mat=M_SNOW, col_fn=snow_col(tuple(centre), nz, base=(0.94, 0.96, 1.0)), tile=0.6, rings=3, seg=16,
               skirt=0.012, rough=0.12, edge=0.12, power=0.6)


def wool_cap(g, rng, head):
    """A child's knitted cap pulled on askew: ribbed turn-up, red with cream bands, a bobble."""
    rot = quat_x(-0.1) @ quat_z(-0.18)
    c = head["c"]
    r, hh = head["r"] + 0.014, head["r"] * head["sq"] + 0.014
    prof = []
    for k in range(9):
        t = math.radians(4 + 58 * k / 8)
        prof.append((r * math.sin(t) * (1.0 + 0.05 * (k / 8)), hh * math.cos(t) + 0.05 * (1 - k / 8) ** 2))
    br_y = prof[-1][1]
    br_r = prof[-1][0]
    prof += [(br_r + 0.012, br_y - 0.004), (br_r + 0.016, br_y - 0.03), (br_r + 0.006, br_y - 0.052),
             (br_r - 0.012, br_y - 0.055), (br_r * 0.7, br_y - 0.02), (0.0, hh * 0.5)]

    def wool(p, n):
        y = (rot.inverted() @ (p - c)).y
        band = int((y + 1.0) * 28) % 5 == 0 and y > br_y + 0.01
        base = (0.86, 0.8, 0.68) if band else (0.62, 0.1, 0.08)
        return scale(base, 0.85 + 0.15 * n.y)
    lathe(g, prof, c, rot, 22, M_CLOTH, wool, 0.15)
    stone(g, tuple(c + rot @ Vector((0.0, hh + 0.06, 0.0))), (0.045, 0.042, 0.045), rng, mat=M_CLOTH,
          col_fn=lambda q, n: (0.86, 0.8, 0.68), detail=2, rough=0.25, cuts=0, tile=0.12)


# ─────────────────────────────────────────────────────────────── the three snowmen
def snowman_a(rng):
    b = Builder()
    g = G(b)
    balls, joints = stack((0.40, 0.29, 0.20), (0.9, 0.93, 0.96), offsets=((0, 0), (0.01, -0.01), (-0.005, 0.01)),
                          tilts=((0, 0), (0.02, -0.03), (0.0, 0.04)))
    body(g, rng, balls, joints)
    skirt(g, rng, balls[0])
    bot, mid, head = balls
    face(g, rng, head, yaw=0.06)
    buttons(g, rng, mid)
    stick_arm(g, rng, mid, 1.0, lift=0.45, length=0.5, forks=2)
    stick_arm(g, rng, mid, -1.0, lift=0.12, length=0.48, forks=1)
    scarf(g, rng, mid, head, joints[1])
    return b


def snowman_b(rng):
    b = Builder()
    g = G(b)
    balls, joints = stack((0.41, 0.30, 0.205), (0.88, 0.92, 0.95), litter=(0.6, 0.3, 0.12),
                          offsets=((0, 0), (-0.012, 0.008), (0.01, 0.0)), tilts=((0, 0), (-0.02, 0.03), (0.03, -0.03)))
    body(g, rng, balls, joints)
    skirt(g, rng, balls[0], h=0.07)
    bot, mid, head = balls
    face(g, rng, head, yaw=-0.08, mouth=6, smile=0.07, eye_y=0.27, mouth_y=-0.4)
    buttons(g, rng, mid, n=3, top=0.5, step=0.33)
    stick_arm(g, rng, mid, 1.0, lift=-0.05, length=0.55, forks=2, fwd=0.15)
    stick_arm(g, rng, mid, -1.0, lift=0.55, length=0.5, forks=2)
    bucket_hat(g, rng, head)
    return b


def snowman_c(rng):
    """The kids' snowman: they couldn't roll the base very big or lift a heavy head, so it's small,
    lumpy and leans; the face is a bit crooked."""
    b = Builder()
    g = G(b)
    balls, joints = stack((0.29, 0.21, 0.155), (0.9, 0.92, 0.95), sink=(0.04, 0.26, 0.24),
                          litter=(0.7, 0.35, 0.15), lumps=(0.08, 0.075, 0.06),
                          offsets=((0, 0), (0.025, 0.01), (0.04, 0.0)),
                          tilts=((0.0, 0.0), (0.03, -0.06), (0.06, -0.1)))
    body(g, rng, balls, joints)
    skirt(g, rng, balls[0], h=0.05, grow=1.4)
    bot, mid, head = balls
    face(g, rng, head, yaw=0.12, eye=0.03, eye_x=0.32, mouth=4, smile=0.12, coal_s=0.019, wonky=1.0, carrot=0.15)
    buttons(g, rng, mid, n=2, s=0.026, top=0.4, step=0.42)
    stick_arm(g, rng, mid, 1.0, lift=1.0, length=0.36, forks=1, r0=0.014)    # waving
    stick_arm(g, rng, mid, -1.0, lift=-0.1, length=0.34, forks=0, r0=0.013)
    wool_cap(g, rng, head)
    return b


MODELS = {"snowman_a": snowman_a, "snowman_b": snowman_b, "snowman_c": snowman_c}

if __name__ == "__main__":
    clear_scene()
    objs = []
    report = {}
    for i, (name, fn) in enumerate(MODELS.items()):
        b = fn(np.random.default_rng(5300 + i))
        report[name] = bounds(b)
        objs.append(b.build(name, MATS))
    export_glb(OUT / "snowmen.glb", objs)
    for k, v in report.items():
        print(f"{k}: {v}")
    print("SNOWMEN_DONE")
