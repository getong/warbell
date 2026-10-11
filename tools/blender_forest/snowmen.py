"""Realistic snowmen -> snowmen.glb (snowman.rs ambushers + the rare biome_snow decor snowman).

Rolled, hand-packed snow on the s_snow scan (snow_02), not three toy spheres:
- each ball is oblate, flattened where it sits and where the next one was pressed on, lumpy from
  the packing, with faint leaf-litter streaks banded around its roll axis (the big one picked up
  the most), a collar of hand-packed snow filling each crease, a drift banked against the foot;
- dark pebble eyes / mouth / buttons pressed in, a bent carrot, forked bark sticks for arms.

    snowman_a  the classic: pebble face, carrot, stick arms, a faded striped wool scarf.
    snowman_b  the soldier's: a dented, rust-spotted iron kettle hat with snow settled on it.
    snowman_c  the old one: slumped and wind-crusted, head slipped, one arm snapped off, its carrot
               lying in the drift at its foot - built long ago by someone who never came back.

Built facing +Z, base at y=0 (the skirt runs below), ~1.3u to the crown (hero ~1.8u); the
ambushers scale it 1.0-1.28. Bottom ball r 0.40 = snowman.rs BODY_R.

    blender -b --factory-startup --python tools/blender_forest/snowmen.py
"""
import json
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
                            mound, pole, scale, smooth_mesh, smoothstep, stone, tube)

M_SNOW = len(W.MATS)
MATS = W.MATS + ["s_snow"]

PACKED = (0.97, 0.98, 1.0)     # hand-packed snow (the s_snow scan already carries the grain)
SHADE = (0.78, 0.85, 0.98)     # sky-lit undersides
OLD = (0.92, 0.93, 0.96)       # weeks-old, wind-crusted
LITTER = (0.5, 0.45, 0.36)     # rolled-in needles / leaf litter / earth
PEBBLE = (0.15, 0.14, 0.13)
CARROT = (0.86, 0.4, 0.09)
STICK = (0.58, 0.52, 0.46)
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
            ao *= 1.0 - 0.14 * (1.0 - smoothstep(0.0, 0.1, abs(p.y - jy)))
        if litter > 0.0:
            d = (p - c0).normalized().dot(axis)
            band = smoothstep(0.62, 0.95, 0.5 + 0.5 * math.sin(d * 11.0 + 2.2 * nz(p * 1.3)))
            speck = smoothstep(0.25, 0.75, nz(p * 11.0))
            col = mix(col, LITTER, 0.6 * litter * band * speck * (1.0 - smoothstep(-0.2, 0.6, d)))
        return scale(col, k * ao)
    return f


def snowball(g, centre, r, rng, squash=0.92, lo=0.8, hi=0.86, lumps=0.045, tilt=(0.0, 0.0), litter=0.0,
             joints=(), base=PACKED, detail=2, pats=5):
    """A rolled snowball: oblate (`squash` on Y), flattened at unit height -`lo` (where it sits) and
    +`hi` (where the next ball was pressed on), low packing lumps and a few shallow flats where a
    gloved hand patted it firm. Returns (centre, r, squash)."""
    verts, faces = icosphere(detail)
    nz = Noise(rng, 4, 1.5)
    fine = Noise(rng, 3, 7.0)
    rot = quat_x(tilt[0]) @ quat_z(tilt[1])
    flats = []
    for _ in range(pats):
        d = Vector((rng.normal(), rng.uniform(-0.5, 0.6), rng.normal())).normalized()
        flats.append((d, rng.uniform(0.93, 0.97)))
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
    return Vector(centre), r, squash, rot


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


def stack(rng, radii, squash, sink=(0.04, 0.02, 0.015), litter=(0.5, 0.25, 0.1), lumps=(0.06, 0.055, 0.045),
          offsets=((0, 0), (0, 0), (0, 0)), tilts=((0, 0), (0, 0), (0, 0)), base=PACKED):
    """Centres of three pressed-together balls, bottom flat on y=-sink[0]; returns the per-ball
    parameters and the two crease heights (draw with `body`)."""
    lo = (0.78, 0.8, 0.85)
    hi = (0.85, 0.86, 1.0)
    balls = []
    y = -sink[0]
    for i in range(3):
        hh = radii[i] * squash[i]
        cy = y + lo[i] * hh
        balls.append(dict(c=V(offsets[i][0], cy, offsets[i][1]), r=radii[i], sq=squash[i], lo=lo[i], hi=hi[i],
                          lit=litter[i], lumps=lumps[i], tilt=tilts[i]))
        y = cy + hi[i] * hh - (sink[i + 1] if i < 2 else 0.0)
    creases = [balls[i]["c"].y + balls[i]["hi"] * balls[i]["r"] * balls[i]["sq"] - sink[i + 1] * 0.5 for i in range(2)]
    return balls, creases


def body(g, rng, balls, creases, base=PACKED):
    for b in balls:
        snowball(g, b["c"], b["r"], rng, squash=b["sq"], lo=b["lo"], hi=b["hi"], lumps=b["lumps"], tilt=b["tilt"],
                 litter=b["lit"], joints=creases, base=base)
    # Hand-packed collars filling the creases (the balls read stuck together, not stacked).
    nz = Noise(rng, 3, 4.0)
    for i, cy in enumerate(creases):
        lower, upper = balls[i], balls[i + 1]
        ring_r = 0.55 * (math.sqrt(max(0.0, 1 - lower["hi"] ** 2)) * lower["r"] +
                         math.sqrt(max(0.0, 1 - upper["lo"] ** 2)) * upper["r"])
        mid = (lower["c"] + upper["c"]) * 0.5
        tr = 0.045 if i == 0 else 0.032
        pts, radii = [], []
        for k in range(19):
            a = 2 * math.pi * k / 18
            w = 1.0 + 0.12 * nz(Vector((math.cos(a), 0.0, math.sin(a))))
            pts.append(V(mid.x + math.cos(a) * ring_r * w, cy + 0.01 * nz(Vector((a, 1.0, 0.0))),
                         mid.z + math.sin(a) * ring_r * w))
            radii.append(tr * (0.8 + 0.4 * max(0.0, nz(Vector((0.0, a, 2.0))))))
        pts[-1], radii[-1] = pts[0], radii[0]
        tube(g, pts, radii, 7, M_SNOW, PACKED, tile=0.9, cap=False)


def skirt(g, rng, rx=0.52, rz=0.48, h=0.11, off=(0.0, 0.0), base=PACKED):
    """Snow banked against the foot. Its rim dives well below y=0, so on a slope the downhill side
    still meets the ground instead of showing a plate under the snowman."""
    nz = Noise(rng, 4, 1.5)
    snow_mound(g, (off[0], -0.02, off[1]), rx, rz, h, rng, mat=M_SNOW,
          col_fn=snow_col((off[0], -1.0, off[1]), nz, base=base, ground=-0.3), tile=0.9, rings=5, seg=18,
          skirt=0.4, rough=0.1, edge=0.16, power=1.2)


def on_ball(b, d, inset=0.0):
    """Point on ball `b`'s surface along direction `d` (from its centre), pushed `inset` inward."""
    d = Vector(d).normalized()
    r, sq = b["r"], b["sq"]
    t = 1.0 / math.sqrt((d.x / r) ** 2 + (d.y / (r * sq)) ** 2 + (d.z / r) ** 2)
    return b["c"] + d * (t - inset)


# ─────────────────────────────────────────────────────────────── features
def pebble(g, p, s, rng, col=PEBBLE):
    stone(g, tuple(p), (s, s * 0.85, s * 0.75), rng, mat=M_ROCK, col_fn=lambda q, n: scale(col, 0.9 + 0.2 * n.y),
          detail=0, rough=0.18, cuts=1, tile=0.25)


def face(g, rng, head, yaw=0.0, eyes=True, mouth=7, carrot=True, eye_drop=(0.0, 0.0)):
    q = quat_y(yaw)

    def at(x, y, z, inset):
        return on_ball(head, q @ Vector((x, y, 1.0)), inset)
    if eyes:
        for side, drop in ((1, eye_drop[0]), (-1, eye_drop[1])):
            pebble(g, at(side * 0.36, 0.3 - drop, 0, 0.012), 0.03, rng)
    for k in range(mouth):
        t = k / max(mouth - 1, 1) * 2 - 1
        pebble(g, at(t * 0.36, -0.3 - 0.12 * (1 - t * t), 0, 0.006), 0.016 + 0.004 * rng.uniform(), rng)
    if carrot:
        base = at(0.0, 0.02, 0, 0.03)
        fwd = q @ Vector((0.0, -0.06, 1.0)).normalized()
        bend = q @ Vector((rng.uniform(-0.08, 0.08), -0.05, 0.0))
        n = 6
        pts = [base + fwd * (0.25 * k / n) + bend * (k / n) ** 2 * 0.25 for k in range(n + 1)]
        radii = [0.032 * (1 - k / n) ** 0.8 + 0.003 for k in range(n + 1)]
        tube(g, pts, radii, 8, M_FRUIT, CARROT, tile=0.2,
             col_fn=lambda t: scale(CARROT, 0.82 + 0.18 * (0.5 + 0.5 * math.sin(t * 38.0)) - 0.12 * t))


def buttons(g, rng, mid, n=3, yaw=0.0):
    q = quat_y(yaw)
    for k in range(n):
        y = 0.42 - k * 0.38
        pebble(g, on_ball(mid, q @ Vector((0.0, y, 1.0)), 0.012), 0.026 + 0.004 * rng.uniform(), rng)


def stick_arm(g, rng, mid, side, lift=0.55, length=0.66, forks=2, droop=0.0, snap=None):
    """A forked bark stick pushed into the mid ball's flank, angled out and up (`droop` bends it
    down instead); `snap` cuts it to that fraction with a splintered end and no forks."""
    shoulder = on_ball(mid, (side, 0.12, rng.uniform(-0.12, 0.12)), 0.09)
    d = Vector((side * 0.82, lift - droop, rng.uniform(-0.25, 0.25))).normalized()
    L = length * (snap if snap else 1.0)
    tip = shoulder + d * L
    pole(g, shoulder, tip, 0.019, 0.011 if not snap else 0.015, rng, col=STICK, sides=5, segs=4, wobble=0.012,
         tile=0.35)
    if snap:
        return
    for f in range(forks):
        t = 0.55 + 0.25 * f + rng.uniform(-0.05, 0.05)
        p = shoulder + d * (L * t)
        a = (0.55 + rng.uniform(-0.1, 0.15)) * (1 if (f + (side > 0)) % 2 else -1)
        fd = (quat_z(a * side) @ quat_y(rng.uniform(-0.4, 0.4)) @ d).normalized()
        pole(g, p, p + fd * rng.uniform(0.14, 0.24), 0.009, 0.004, rng, col=STICK, sides=4, segs=2, wobble=0.006,
             tile=0.3)
    # Twiglets at the tip (a hand of three).
    for k in range(3):
        fd = (quat_z((k - 1) * 0.45 * side) @ d).normalized()
        pole(g, tip, tip + fd * rng.uniform(0.06, 0.11), 0.006, 0.003, rng, col=STICK, sides=4, segs=1, wobble=0.0,
             tile=0.3)


def scarf(g, rng, head, mid, crease):
    """A faded striped wool scarf wound at the neck, knot on the left front, two tails down the chest."""
    nz = Noise(rng, 3, 5.0)
    neck_r = 0.5 * (math.sqrt(1 - mid["hi"] ** 2) * mid["r"] + math.sqrt(1 - head["lo"] ** 2) * head["r"]) + 0.035
    c = (mid["c"] + head["c"]) * 0.5

    def stripes(t):
        return (0.5, 0.16, 0.12) if int(t * 9) % 3 else (0.76, 0.7, 0.58)
    for turn, (dy, rr) in enumerate(((0.0, 0.042), (0.045, 0.036))):
        pts = []
        for k in range(25):
            a = 2 * math.pi * k / 24
            w = 1.0 + 0.06 * nz(Vector((math.cos(a), turn, math.sin(a))))
            pts.append(V(c.x + math.cos(a) * neck_r * w, crease + dy + 0.012 * math.sin(a * 2 + turn),
                         c.z + math.sin(a) * neck_r * w))
        pts[-1] = pts[0]
        tube(g, pts, [rr] * len(pts), 8, M_CLOTH, (0.5, 0.16, 0.12), tile=0.25, cap=False,
             col_fn=lambda t: stripes(t * 4.0))
    # Knot + tails hanging over the mid ball (following its surface, a little lifted off it).
    ka = math.radians(62)
    knot = V(c.x + math.cos(ka) * neck_r, crease + 0.02, c.z + math.sin(ka) * neck_r)
    stone(g, tuple(knot), (0.045, 0.04, 0.04), rng, mat=M_CLOTH, col_fn=lambda q, n: (0.48, 0.15, 0.11), detail=1,
          rough=0.2, cuts=0, tile=0.2)
    for j, (spread, length) in enumerate(((0.1, 0.34), (-0.08, 0.27))):
        pts = []
        for k in range(6):
            t = k / 5
            d = Vector((math.cos(ka) + spread * t, 0.35 - 1.1 * t, math.sin(ka) + 0.1))
            pts.append(on_ball(mid, d, -0.025 - 0.01 * t) if t > 0.15 else knot + Vector((0, -0.04 * t, 0)))
        pts = [knot] + pts[1:]
        n_len = len(pts)
        tube(g, pts, [0.03 - 0.004 * (k / n_len) for k in range(n_len)], 6, M_CLOTH, (0.5, 0.16, 0.12), tile=0.25,
             col_fn=lambda t, j=j: stripes(t * length * 3 + j * 0.3))
        # Fringe at the tail end.
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


def kettle_hat(g, rng, head):
    """An old infantry kettle hat: low iron dome, broad sloping brim, a dent, rust in the weather,
    a pillow of snow on the crown. Sits a little askew."""
    nz = Noise(rng, 4, 3.0)
    top = head["c"].y + head["r"] * head["sq"] * 0.96
    centre = V(head["c"].x + 0.01, top - 0.08, head["c"].z - 0.01)
    rot = quat_x(-0.12) @ quat_z(0.09)
    outer = [(0.0, 0.135), (0.06, 0.13), (0.105, 0.112), (0.135, 0.08), (0.152, 0.04), (0.16, 0.01), (0.2, -0.008),
             (0.26, -0.03), (0.285, -0.043), (0.288, -0.05)]
    under = [(0.28, -0.054), (0.25, -0.042), (0.19, -0.018), (0.152, -0.002), (0.14, 0.03), (0.12, 0.07),
             (0.08, 0.098), (0.0, 0.104)]
    dent_c = Vector((0.08, 0.11, 0.06))

    def dent(p):
        return -0.035 * math.exp(-((p - dent_c).length / 0.05) ** 2) + 0.004 * nz(p * 2.0)

    def iron(p, n):
        rust = smoothstep(0.15, 0.6, nz(p * 6.0) + 0.3 * (1 - n.y))
        return scale(mix(IRON, RUST, rust * 0.45), 0.72 + 0.25 * smoothstep(-0.2, 0.8, n.y))
    lathe(g, outer + under, centre, rot, 18, M_IRON, iron, 0.3, dent=dent)
    snow_mound(g, tuple(centre + rot @ Vector((-0.01, 0.13, 0.0))), 0.1, 0.09, 0.035, rng, mat=M_SNOW,
          col_fn=snow_col(tuple(centre), nz, base=(0.94, 0.96, 1.0)), tile=0.6, rings=3, seg=14, skirt=0.01,
          rough=0.1, edge=0.15, power=0.6)
    # Settled snow along the brim's uphill side.
    for k in range(5):
        a = math.radians(200 + k * 28)
        p = centre + rot @ Vector((math.cos(a) * 0.22, -0.02, math.sin(a) * 0.22))
        snow_mound(g, tuple(p), 0.05, 0.035, 0.018, rng, mat=M_SNOW, col_fn=snow_col(tuple(p), nz), tile=0.6, rings=2,
              seg=8, skirt=0.0, rough=0.1, edge=0.1, power=0.6)


# ─────────────────────────────────────────────────────────────── the three snowmen
def snowman_a(rng):
    b = Builder()
    g = G(b)
    balls, creases = stack(rng, (0.40, 0.29, 0.20), (0.9, 0.93, 0.97), tilts=((0, 0), (0.02, -0.03), (0.0, 0.04)))
    body(g, rng, balls, creases)
    skirt(g, rng)
    bot, mid, head = balls
    face(g, rng, head, yaw=0.08)
    buttons(g, rng, mid)
    stick_arm(g, rng, mid, 1.0, lift=0.62, forks=2)
    stick_arm(g, rng, mid, -1.0, lift=0.35, forks=1)
    scarf(g, rng, head, mid, creases[1])
    return b


def snowman_b(rng):
    b = Builder()
    g = G(b)
    balls, creases = stack(rng, (0.41, 0.30, 0.205), (0.88, 0.92, 0.96), litter=(0.6, 0.3, 0.12),
                           offsets=((0, 0), (0.01, -0.01), (-0.01, 0.0)))
    body(g, rng, balls, creases)
    skirt(g, rng, rx=0.6, rz=0.55, h=0.13)
    bot, mid, head = balls
    face(g, rng, head, yaw=-0.1, mouth=5)
    buttons(g, rng, mid, n=4)
    stick_arm(g, rng, mid, 1.0, lift=0.18, length=0.72, forks=2)
    stick_arm(g, rng, mid, -1.0, lift=0.7, length=0.6, forks=2)
    kettle_hat(g, rng, head)
    return b


def snowman_c(rng):
    b = Builder()
    g = G(b)
    balls, creases = stack(rng, (0.42, 0.28, 0.19), (0.8, 0.9, 0.95), sink=(0.08, 0.035, 0.03),
                           litter=(0.35, 0.15, 0.05), lumps=(0.07, 0.065, 0.06),
                           offsets=((0, 0), (0.035, 0.01), (0.07, -0.02)),
                           tilts=((0.0, 0.0), (0.04, -0.08), (0.1, -0.22)), base=OLD)
    body(g, rng, balls, creases, base=OLD)
    # Wind-crust: a drift banked up the windward (-X) side.
    skirt(g, rng, rx=0.64, rz=0.58, h=0.15, base=OLD)
    nz = Noise(rng, 4, 1.8)
    snow_mound(g, (-0.34, 0.02, 0.0), 0.36, 0.44, 0.3, rng, mat=M_SNOW, col_fn=snow_col((-0.34, -1.0, 0.0), nz, base=OLD),
          tile=0.9, rings=5, seg=20, skirt=0.06, rough=0.15, edge=0.2, power=0.75)
    bot, mid, head = balls
    face(g, rng, head, yaw=0.3, carrot=False, mouth=4, eye_drop=(0.0, 0.1))
    buttons(g, rng, mid, n=2, yaw=0.1)
    stick_arm(g, rng, mid, 1.0, lift=0.1, droop=0.5, length=0.62, forks=1)
    stick_arm(g, rng, mid, -1.0, lift=0.4, snap=0.32)
    # The rest of the snapped arm and the carrot, fallen into the drift at its foot.
    pole(g, V(-0.55, 0.03, 0.42), V(-0.92, 0.0, 0.3), 0.014, 0.009, rng, col=STICK, sides=5, segs=3, wobble=0.01,
         tile=0.35)
    pts = [V(0.36, 0.035, 0.52) + Vector((0.2 * k / 5, -0.004 * k, 0.06 * k / 5)) for k in range(6)]
    tube(g, pts, [0.03 * (1 - k / 5) ** 0.8 + 0.003 for k in range(6)], 8, M_FRUIT, scale(CARROT, 0.8), tile=0.2)
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
