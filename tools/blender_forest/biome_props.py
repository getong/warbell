"""Realistic replacements for the last low-poly biome scatter -> biome_props.glb.

Rocky highlands (biome_rocky.rs): the crag piles (leaning slabs / tall split crag / cobble spill),
the waymarker cairn, the two hoodoo spires (now weathered sandstone pillars) and the scree spills.
Desert (biome_desert.rs): the saguaro cacti.

Each model keeps the footprint and height of the faceted original it replaces (the game keeps
registering the ORIGINAL blocker, so the drawn mass has to stay inside it), base at y=0 with the
ground-contact stones sunk ~0.05-0.1u so a piece on a slightly uneven spot never floats. Stone is
the tileable `s_rock` scan (Poly Haven mossy_rock) with box-projected world UVs; vertex colour tints
it to the biome's warm grey-brown, ochre sandstone or lichen. The cacti are `s_plaster` (a fine,
matte white scan) tinted waxy green by vertex colour, with real ribs, areoles and spine tufts.

    blender -b --factory-startup --python tools/blender_forest/biome_props.py
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
from wayside_models import Noise, mix, rock_col, scale, slab, smooth_mesh, smoothstep, stone  # noqa: E402

M_ROCK, M_PLASTER = range(2)
MATS = ["s_rock", "s_plaster"]

# Rocky palette (multiplies the grey s_rock scan): warm grey-brown body, sun-bleached caps,
# rusty-orange and sage lichen; ochre / rust sandstone bands for the spires.
STONE = (0.8, 0.75, 0.68)
STONE_COOL = (0.72, 0.72, 0.7)
LICHEN_ORANGE = (0.95, 0.62, 0.3)
LICHEN_SAGE = (0.66, 0.72, 0.48)
SAND_OCHRE = (0.88, 0.7, 0.5)
SAND_RUST = (0.74, 0.52, 0.37)
SAND_PALE = (0.9, 0.8, 0.66)


def rk_col(base, nz, moss=0.35, lichen=LICHEN_ORANGE, var=0.22):
    return rock_col(base, moss=moss, ground=0.0, dark_below=0.45, lichen=lichen, noise=nz, var=var)


def rk_crag_a(rng):
    """Leaning slab crag (low-poly crag 0, r 0.42): two big fractured slabs leaning into each
    other over a crevice, cobbles shed at the foot. ~0.75 tall, inside r ~0.62."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 5, 1.6)
    slab(g, (-0.07, 0.24, 0.0), (1.05, 0.62, 0.78), quat_y(0.2) @ quat_z(0.3), rng, res=(6, 4, 5), round_r=0.04,
         rough=0.13, cuts=3, taper=0.15, col_fn=rk_col(STONE, nz, moss=0.45), tile=0.9)
    slab(g, (0.3, 0.2, -0.05), (0.76, 0.52, 0.66), quat_y(-0.5) @ quat_z(-0.38), rng, res=(5, 4, 4), round_r=0.04,
         rough=0.13, cuts=3, taper=0.2, col_fn=rk_col(STONE_COOL, nz, moss=0.3, lichen=LICHEN_SAGE), tile=0.9)
    for k in range(5):
        a = rng.uniform(0, 6.28)
        d = rng.uniform(0.42, 0.56)
        r = rng.uniform(0.06, 0.11)
        stone(g, (math.cos(a) * d, r * 0.25, math.sin(a) * d), (r, r * 0.65, r * 0.85), rng, detail=1, cuts=2,
              col_fn=rk_col(scale(STONE, rng.uniform(0.8, 1.0)), nz, moss=0.2), tile=0.6)
    return b


def rk_crag_b(rng):
    """Tall split crag (low-poly crag 1, r 0.4): three fractured blocks climbing up, offset at
    the split, a flank slab propped against the foot. ~1.45 tall, inside r ~0.5."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 5, 1.4)
    slab(g, (0.0, 0.3, 0.0), (0.84, 0.72, 0.76), quat_y(0.3) @ quat_x(0.06), rng, res=(5, 5, 5), round_r=0.045,
         rough=0.13, cuts=3, taper=0.12, col_fn=rk_col(scale(STONE, 0.9), nz, moss=0.3), tile=0.9)
    slab(g, (0.1, 0.84, -0.04), (0.64, 0.56, 0.6), quat_y(-0.4) @ quat_z(-0.1), rng, res=(5, 4, 5), round_r=0.04,
         rough=0.13, cuts=3, taper=0.15, col_fn=rk_col(STONE, nz, moss=0.4), tile=0.9)
    stone(g, (0.05, 1.22, 0.02), (0.25, 0.26, 0.22), rng, detail=2, cuts=3, rough=0.12,
          col_fn=rk_col(scale(STONE_COOL, 1.05), nz, moss=0.35), tile=0.8)
    slab(g, (-0.34, 0.16, 0.12), (0.6, 0.3, 0.42), quat_y(0.7) @ quat_z(0.5), rng, res=(4, 3, 3), round_r=0.06,
         rough=0.07, cuts=1, taper=0.2, col_fn=rk_col(STONE, nz, moss=0.25, lichen=LICHEN_SAGE), tile=0.8)
    for k in range(3):
        a = rng.uniform(0, 6.28)
        r = rng.uniform(0.06, 0.1)
        stone(g, (math.cos(a) * 0.46, r * 0.25, math.sin(a) * 0.46), (r, r * 0.65, r * 0.85), rng, detail=1, cuts=2,
              col_fn=rk_col(scale(STONE, 0.85), nz, moss=0.2), tile=0.6)
    return b


def rk_crag_c(rng):
    """Cobble spill (low-poly crag 2, r 0.34): a low split slab with broken cobbles drifted
    round it, thinning outward. ~0.35 tall, inside r ~0.58."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 5, 1.8)
    slab(g, (0.0, 0.08, 0.0), (0.72, 0.34, 0.56), quat_y(0.3) @ quat_z(0.08), rng, res=(5, 3, 4), round_r=0.035,
         rough=0.13, cuts=3, taper=0.1, col_fn=rk_col(STONE, nz, moss=0.4), tile=0.8)
    for k in range(9):
        a = k / 9 * 6.28 + rng.uniform(-0.3, 0.3)
        d = rng.uniform(0.3, 0.52)
        r = rng.uniform(0.07, 0.15) * (1.2 - d)
        stone(g, (math.cos(a) * d, r * 0.25, math.sin(a) * d), (r, r * 0.6, r * 0.85), rng, detail=1, cuts=2,
              col_fn=rk_col(scale(mix(STONE, STONE_COOL, rng.uniform(0, 1)), rng.uniform(0.78, 1.02)), nz, moss=0.25),
              tile=0.6)
    return b


def rk_cairn(rng):
    """Waymarker cairn (low-poly crag 3): six courses of flat fieldstones dry-built to a taper
    (0.46 x 0.40 at the foot), a marker stone on top, two stones dropped at the foot. ~0.62 tall."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 3.0)
    y = -0.02
    courses = [(0.44, 0.38, 0.1), (0.38, 0.33, 0.095), (0.33, 0.28, 0.09), (0.27, 0.23, 0.085), (0.21, 0.18, 0.08),
               (0.15, 0.12, 0.075)]
    for ci, (w, d, h) in enumerate(courses):
        jog = (rng.uniform(-0.02, 0.02), rng.uniform(-0.02, 0.02))
        # Two stones side by side in the wide courses, one up top.
        n = 2 if ci < 3 else 1
        for k in range(n):
            off = (k - (n - 1) / 2) * w * 0.48
            yaw = rng.uniform(-0.6, 0.6) + ci * 0.7
            size = (w / n * rng.uniform(1.0, 1.15), h * rng.uniform(0.9, 1.1), d * rng.uniform(0.9, 1.08))
            p = (jog[0] + off * math.cos(yaw), y + h * 0.5, jog[1] + off * math.sin(yaw))
            rot = quat_y(yaw) @ quat_x(rng.uniform(-0.06, 0.06)) @ quat_z(rng.uniform(-0.06, 0.06))
            tint = scale(mix(STONE, STONE_COOL, rng.uniform(0, 1)), rng.uniform(0.72, 1.02))
            slab(g, p, size, rot, rng, res=(3, 2, 3), round_r=0.025, rough=0.09, cuts=2, taper=rng.uniform(0.0, 0.2),
                 col_fn=rk_col(tint, nz, moss=0.45 if ci < 4 else 0.3), tile=0.5)
        y += h
    stone(g, (0.01, y + 0.04, 0.0), (0.06, 0.05, 0.05), rng, detail=1, cuts=2,
          col_fn=rk_col(scale(STONE, 1.05), nz, moss=0.2), tile=0.5)
    for a, r in ((0.4, 0.05), (3.6, 0.045)):
        stone(g, (math.cos(a) * 0.3, 0.0, math.sin(a) * 0.3), (r, r * 0.6, r * 0.85), rng, detail=1, cuts=2,
              col_fn=rk_col(scale(STONE, 0.85), nz, moss=0.4), tile=0.5)
    return b


def spire(rng, bands, cap=None):
    """A weathered sandstone pillar: drums of fractured stone, each set on the last with a little
    drift, hard bands jutting as ledges. `bands` = (radius, height, tint) bottom -> top."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 5, 2.0)
    y = -0.06
    drift = Vector((0.0, 0.0, 0.0))
    dd = Vector((rng.uniform(0.6, 1.0), 0.0, rng.uniform(-0.4, 0.4))).normalized() * 0.03
    for r, h, tint in bands:
        drift += dd
        stone(g, (drift.x, y + h * 0.5, drift.z), (r, h * 0.62, r * rng.uniform(0.85, 1.0)), rng,
              detail=2 if r > 0.2 else 1, cuts=3,
              rough=0.1, flat_y=0.78, rot=quat_y(rng.uniform(0, 6.28)),
              col_fn=rk_col(tint, nz, moss=0.25, lichen=LICHEN_ORANGE, var=0.18), tile=0.7)
        y += h * 0.86
    if cap:
        cr, ch, ct = cap
        slab(g, (drift.x + 0.04, y + ch * 0.45, drift.z), (cr * 2, ch, cr * 1.7), quat_y(rng.uniform(0, 6.28)) @ quat_z(0.07),
             rng, res=(5, 3, 4), round_r=0.06, rough=0.08, cuts=2, taper=-0.1,
             col_fn=rk_col(ct, nz, moss=0.4), tile=0.8)
    # Fallen band rubble at the foot.
    for k in range(4):
        a = rng.uniform(0, 6.28)
        r = rng.uniform(0.05, 0.09)
        stone(g, (math.cos(a) * 0.36, r * 0.2, math.sin(a) * 0.36), (r, r * 0.6, r * 0.85), rng, detail=1, cuts=2,
              col_fn=rk_col(scale(bands[0][2], rng.uniform(0.75, 0.95)), nz, moss=0.2), tile=0.5)
    return b


def rk_spire_a(rng):
    """Slender banded spire (low-poly hoodoo 0): ~1.9 tall, foot r ~0.33."""
    return spire(rng, [(0.33, 0.36, SAND_RUST), (0.3, 0.34, SAND_OCHRE), (0.27, 0.32, SAND_PALE), (0.23, 0.32, SAND_OCHRE),
                       (0.19, 0.3, SAND_RUST), (0.15, 0.28, SAND_PALE), (0.11, 0.24, SAND_OCHRE)])


def rk_spire_b(rng):
    """Balanced rock (low-poly hoodoo 1): a banded neck carrying a layered cap rock, ~1.8 tall."""
    return spire(rng, [(0.29, 0.42, SAND_OCHRE), (0.23, 0.38, SAND_RUST), (0.18, 0.36, SAND_PALE), (0.13, 0.3, SAND_OCHRE)],
                 cap=(0.36, 0.3, scale(STONE, 1.02)))


def rk_scree(rng, n, spread):
    """Scree spill: a fan of broken stones, big at the head, small down the fall line."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 2.2)
    for k in range(n):
        t = k / max(n - 1, 1)
        along = -0.25 + t * spread
        side = rng.uniform(-0.18, 0.18) * (0.6 + t)
        r = 0.11 * (1.0 - 0.6 * t) * rng.uniform(0.75, 1.2)
        stone(g, (along, r * 0.2, side), (r, r * 0.55, r * 0.85), rng, detail=1, cuts=2, rough=0.12,
              col_fn=rk_col(scale(mix(STONE, STONE_COOL, rng.uniform(0, 1)), rng.uniform(0.75, 1.05)), nz, moss=0.2,
                            lichen=LICHEN_SAGE), tile=0.5)
    return b


def rk_scree_a(rng):
    return rk_scree(rng, 11, 0.75)


def rk_scree_b(rng):
    return rk_scree(rng, 8, 0.6)


def rk_pebbles(rng):
    """Ground-cover pebble cluster (replaces the single faceted cover pebble), r ~0.12."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 3, 3.0)
    for k in range(3):
        a = k * 2.1 + rng.uniform(-0.4, 0.4)
        r = rng.uniform(0.035, 0.06)
        # detail 0 (20 tris): there are thousands of these in the merged cover chunks.
        stone(g, (math.cos(a) * 0.06, r * 0.15, math.sin(a) * 0.06), (r, r * 0.55, r * 0.85), rng, detail=0, cuts=2,
              col_fn=rk_col(scale(STONE, rng.uniform(0.75, 1.05)), nz, moss=0.15), tile=0.4)
    return b


# ─────────────────────────────────────────────────────────────── desert
CACTUS = (0.56, 0.7, 0.4)
CACTUS_DARK = (0.32, 0.44, 0.22)
CACTUS_PALE = (0.6, 0.66, 0.42)
SPINE = (0.92, 0.86, 0.66)


def ribbed(g, pts, radii, ribs, rng, nz, depth=0.16, segs_per=1, tip=True):
    """A saguaro stem along a polyline: `ribs` vertical pleats (round crests, sharp grooves),
    smooth normals, UV u around / v along. A dome closes the top; the foot is left open (buried)."""
    pts = [Vector(p) for p in pts]
    rings = []
    n_prev = None
    sides = ribs * 4
    v_acc = 0.0
    for i, p in enumerate(pts):
        if i == 0:
            t = (pts[1] - pts[0]).normalized()
        elif i == len(pts) - 1:
            t = (pts[-1] - pts[-2]).normalized()
        else:
            t = (pts[i + 1] - pts[i - 1]).normalized()
        n = t.orthogonal().normalized() if n_prev is None else (n_prev - t * n_prev.dot(t)).normalized()
        n_prev = n
        bb = t.cross(n)
        if i:
            v_acc += (pts[i] - pts[i - 1]).length
        ring = []
        for s in range(sides):
            a = 2 * math.pi * s / sides
            pleat = abs(math.cos(a * ribs / 2))  # 1 on a crest, 0 in a groove
            rr = radii[i] * (1.0 - depth + depth * pleat ** 0.6)
            d = n * math.cos(a) + bb * math.sin(a)
            ring.append((p + d * rr, d, pleat, a))
        rings.append((ring, t, v_acc))
    verts, cols, tris = [], [], []
    for i, (ring, t, v) in enumerate(rings):
        f = i / (len(rings) - 1)
        for (p, d, pleat, a) in ring:
            verts.append(p)
            # Grooves shade darker (baked AO), crests catch the light; the foot is browned, corky.
            c = mix(CACTUS_DARK, CACTUS, 0.35 + 0.65 * pleat)
            c = scale(c, 1.0 + nz(p * 4.0) * 0.08)
            if p.y < 0.35:
                c = mix((0.45, 0.4, 0.3), c, smoothstep(0.05, 0.35, p.y))
            cols.append(c)
    n_s = len(rings[0][0])
    for i in range(len(rings) - 1):
        for s in range(n_s):
            a = i * n_s + s
            b2 = i * n_s + (s + 1) % n_s
            c = (i + 1) * n_s + (s + 1) % n_s
            d = (i + 1) * n_s + s
            tris += [(a, b2, c), (a, c, d)]
    if tip:
        ring, t, _ = rings[-1]
        top = pts[-1] + t * radii[-1] * 0.55
        verts.append(top)
        cols.append(CACTUS_PALE)
        ti = len(verts) - 1
        base = (len(rings) - 1) * n_s
        for s in range(n_s):
            tris.append((base + s, base + (s + 1) % n_s, ti))
    lookup = {id(v): c for v, c in zip(verts, cols)}
    # smooth_mesh calls col_fn(vert, normal) with the very Vector objects we pass.
    smooth_mesh(g, verts, tris, M_PLASTER, lambda p, nn: lookup[id(p)], 0.6)
    # Areole spine tufts along the crests: small pale crosses (two crossed quads, double sided).
    for i in range(1, len(rings) - 1):
        ring, t, _ = rings[i]
        for s in range(0, n_s, 4):
            if rng.uniform() > 0.5:
                continue
            p, d, _, _ = ring[s]
            q = p + d * 0.012
            for ax in (t, d.cross(t).normalized()):
                ln = 0.03
                quad = [q - ax * ln + d * 0.0, q + ax * ln, q + ax * ln + d * 0.03, q - ax * ln + d * 0.03]
                nn = ax.cross(d).normalized()
                uv = [(0.0, 0.0), (0.1, 0.0), (0.1, 0.1), (0.0, 0.1)]
                g.poly(quad, uv, [nn] * 4, [SPINE] * 4, M_PLASTER)
                g.poly(quad[::-1], uv[::-1], [-nn] * 4, [SPINE] * 4, M_PLASTER)


def arm(base_y, side, out, up, r, phi):
    """Saguaro arm: leaves the trunk horizontally, elbows and climbs."""
    dx, dz = math.cos(phi), math.sin(phi)
    pts = []
    for k in range(7):
        f = k / 6
        horiz = out * smoothstep(0.0, 0.55, f)
        rise = up * smoothstep(0.25, 1.0, f) ** 1.1
        pts.append((dx * (side + horiz), base_y + rise + 0.05 * f, dz * (side + horiz)))
    radii = [r * (1.0 - 0.18 * (k / 6) ** 2) for k in range(7)]
    return pts, radii


def saguaro(rng, height, r, arms):
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 2.0)
    n = 9
    lean = Vector((rng.uniform(-0.03, 0.03), 0, rng.uniform(-0.03, 0.03)))
    pts = [Vector((0, -0.12 + (height + 0.12) * k / (n - 1), 0)) + lean * (k / (n - 1)) ** 2 for k in range(n)]
    radii = [r * (1.06 - 0.16 * (k / (n - 1)) ** 2) for k in range(n)]
    ribbed(g, pts, radii, 12, rng, nz)
    for by, phi, out, up, ar in arms:
        apts, arad = arm(by, r * 0.7, out, up, ar, phi)
        ribbed(g, apts, arad, 9, rng, nz)
    return b


# Sized to the low-poly saguaros they replace (trunk 1.35 / 1.30 / 0.95 tall, r 0.14 / 0.13 / 0.16,
# arms reaching ~0.5 out).
def ds_saguaro_a(rng):
    """Classic two-arm."""
    return saguaro(rng, 1.35, 0.14, [(0.55, 0.3, 0.26, 0.42, 0.085), (0.72, 3.4, 0.22, 0.36, 0.075)])


def ds_saguaro_b(rng):
    """Single arm."""
    return saguaro(rng, 1.3, 0.13, [(0.5, 1.9, 0.24, 0.42, 0.08)])


def ds_saguaro_c(rng):
    """Young: short, fat, no arms."""
    return saguaro(rng, 0.95, 0.16, [])


MODELS = {
    "rk_crag_a": rk_crag_a,
    "rk_crag_b": rk_crag_b,
    "rk_crag_c": rk_crag_c,
    "rk_cairn": rk_cairn,
    "rk_spire_a": rk_spire_a,
    "rk_spire_b": rk_spire_b,
    "rk_scree_a": rk_scree_a,
    "rk_scree_b": rk_scree_b,
    "rk_pebbles": rk_pebbles,
    "ds_saguaro_a": ds_saguaro_a,
    "ds_saguaro_b": ds_saguaro_b,
    "ds_saguaro_c": ds_saguaro_c,
}


def bounds(builder):
    v = np.array(builder.verts) if builder.verts else np.zeros((1, 3))
    gx, gy, gz = v[:, 0], v[:, 2], -v[:, 1]
    above = gy > 0.02
    r = np.hypot(gx[above], gz[above]).max() if above.any() else 0.0
    return {"tris": builder.tris(), "radius": round(float(r), 3), "y": [round(float(gy.min()), 3), round(float(gy.max()), 3)]}


if __name__ == "__main__":
    clear_scene()
    objs = []
    report = {}
    for i, (name, fn) in enumerate(MODELS.items()):
        b = fn(np.random.default_rng(5100 + i))
        report[name] = bounds(b)
        objs.append(b.build(name, MATS))
    export_glb(OUT / "biome_props.glb", objs)
    for k, v in report.items():
        print(f"{k}: {v}")
    print("BIOME_PROPS_DONE")
