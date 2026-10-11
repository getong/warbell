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
from wayside_models import Noise, icosphere, mix, rock_col, scale, smooth_mesh, smoothstep, stone, tube  # noqa: E402

M_ROCK, M_PLASTER, M_BARK = range(3)
MATS = ["s_rock", "s_plaster", "bark_oak"]

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


# ─────────────────────────────────────────────────────────────── fractured stone
def frac_block(g, centre, radii, rng, sides=None, nplanes=10, dlo=0.66, dhi=0.95, flat=(0.92, 0.92), rot=None,
               mat=M_ROCK, col_fn=None, tile=0.8, detail=2, notch=0.0, band=0.11, noise=0.012, crisp=1.035,
               ground_y=0.0):
    """A fractured rock block: an icosphere ray-cast onto a random convex polytope {n_i . x <= d_i}
    (scaled by `radii`), so every break is a true PLANE with a sharp edge, chipped where two planes
    nearly agree. Facet-interior vertices take the plane's own normal (crisp, flat breaks); only the
    narrow edge band shades smooth. `flat` = (top, bottom) bedding planes; `sides` = n extra planes
    with near-horizontal normals (a slab's outline); `notch` cuts horizontal bedding grooves every
    `band` units up the steep faces (erosion notches), darkened in the colour."""
    verts, faces = icosphere(detail)
    planes = []
    for _ in range(nplanes):
        planes.append((Vector(rng.normal(size=3)).normalized(), rng.uniform(dlo, dhi)))
    if sides:
        a0 = rng.uniform(0, 6.283)
        for k in range(sides):
            a = a0 + k / sides * 6.283 + rng.uniform(-0.3, 0.3)
            planes.append((Vector((math.cos(a), rng.uniform(-0.18, 0.18), math.sin(a))).normalized(),
                           rng.uniform(0.78, 0.98)))
    if flat:
        tilt = Vector((rng.uniform(-0.06, 0.06), 1.0, rng.uniform(-0.06, 0.06))).normalized()
        planes += [(tilt, flat[0]), (Vector((-tilt.x, -1.0, -tilt.z)).normalized(), flat[1])]
    rot = rot or quat_y(rng.uniform(0, 6.283))
    nz = Noise(rng, 4, 2.4)
    R = Vector(radii)
    C = Vector(centre)
    out, hint, groove = [], [], []
    for v in verts:
        best, second, bi = 9.0, 9.0, 0
        for i, (n, d) in enumerate(planes):
            c = n.dot(v)
            if c > 1e-6:
                t = d / c
                if t < best:
                    best, second, bi = t, best, i
                elif t < second:
                    second = t
        best = min(best, 1.2)
        p = v * best
        q = Vector((p.x * R.x, p.y * R.y, p.z * R.z))
        n = planes[bi][0]
        nl = Vector((n.x / R.x, n.y / R.y, n.z / R.z)).normalized()
        w = C + rot @ q
        gr = 0.0
        if notch > 0 and abs(nl.y) < 0.55:
            f = ((w.y - ground_y) / band) % 1.0
            gr = math.exp(-(f / 0.09) ** 2) + math.exp(-((1 - f) / 0.09) ** 2)
            q -= Vector((nl.x, 0.0, nl.z)) * notch * gr
        q += nl * noise * nz(q * 7.0) * min(R)
        out.append(C + rot @ q)
        hint.append((rot @ nl) if (second / best > crisp and gr < 0.25) else None)
        groove.append(gr)
    tris = []
    for a, b, d in faces:
        nrm = (out[b] - out[a]).cross(out[d] - out[a])
        if nrm.dot((out[a] + out[b] + out[d]) / 3 - C) < 0:
            b, d = d, b
        tris.append((a, b, d))
    vn = [Vector((0, 0, 0)) for _ in out]
    for a, b, d in tris:
        nrm = (out[b] - out[a]).cross(out[d] - out[a])
        for i in (a, b, d):
            vn[i] += nrm
    nrms = [hint[i] if hint[i] is not None else (vn[i].normalized() if vn[i].length > 1e-12 else Vector((0, 1, 0)))
            for i in range(len(out))]
    col_fn = col_fn or rk_col(STONE, nz)
    cols = []
    for i, p in enumerate(out):
        c = col_fn(p, nrms[i])
        if notch > 0:
            k = math.floor((p.y - ground_y) / band)
            c = scale(c, (1.0 + 0.09 * math.sin(k * 2.7 + 1.3)) * (1.0 - 0.38 * min(groove[i], 1.0)))
        cols.append(c)
    for a, b, d in tris:
        fn = (out[b] - out[a]).cross(out[d] - out[a])
        if fn.length < 1e-14:
            continue
        ax = max(range(3), key=lambda k: abs(fn[k]))
        uvs = []
        for i in (a, b, d):
            p = out[i]
            u, v = (p.z, p.y) if ax == 0 else ((p.x, p.z) if ax == 1 else (p.x, p.y))
            uvs.append((u / tile, v / tile))
        g.poly([out[a], out[b], out[d]], uvs, [nrms[a], nrms[b], nrms[d]], [cols[a], cols[b], cols[d]], mat)


def rubble(g, rng, nz, n, rmin, rmax, dmin, dmax, tint=None):
    """Broken chips at the foot of a crag (angular, detail 1)."""
    for k in range(n):
        a = rng.uniform(0, 6.283)
        d = rng.uniform(dmin, dmax)
        r = rng.uniform(rmin, rmax)
        frac_block(g, (math.cos(a) * d, r * 0.3, math.sin(a) * d), (r, r * 0.7, r * 0.85), rng, nplanes=8, flat=None,
                   detail=1, col_fn=rk_col(scale(tint or STONE, rng.uniform(0.72, 1.0)), nz, moss=0.2), tile=0.5,
                   noise=0.0)


def column(g, rng, nz, beds, rx, rz, sides=10, y0=-0.08, drift=0.015, lip=0.02, slope=0.1, var=(0.84, 1.1),
           step=(0.93, 1.05), lean=0.0, rise=0.05, moss=0.2, lichen=LICHEN_ORANGE, tile=0.7):
    """ONE continuous bedded pillar (no stacked blobs): a jointed, irregular `sides`-face outline
    swept up through horizontal beds `(h, s, tint, soft)`. A hard bed keeps planar vertical faces,
    each face set back by its own fracture (so the faces step into small ledges bed to bed), its
    bottom edge a sharp lip (`lip` chip) over the notch below, its top edge weathered back by
    `slope`; a soft bed is a recessed groove (`s` = its own width), an erosion notch between hard
    beds. A slow per-face wobble up the height keeps the beds from repeating. Flat-shaded per
    facet. Returns (top y, top centre)."""
    a0 = rng.uniform(0, 6.283)
    angs = [a0 + (k + rng.uniform(-0.3, 0.3)) / sides * 6.283 for k in range(sides)]
    base = [rng.uniform(*var) for _ in range(sides)]
    dirv = Vector((rng.uniform(-1, 1), 0.0, rng.uniform(-1, 1))).normalized()
    rot = quat_y(rng.uniform(0, 6.283)) @ quat_z(lean)
    rings = []
    off = Vector((0.0, 0.0, 0.0))

    ph = [rng.uniform(0, 6.283) for _ in range(sides)]

    def ring(yy, s, rs, tint, dark):
        w = [base[k] * rs[k] * s * (1.0 + 0.07 * math.sin(yy * 3.1 + ph[k])) for k in range(sides)]
        pts = [rot @ Vector((off.x + math.cos(angs[k]) * w[k] * rx, yy, off.z + math.sin(angs[k]) * w[k] * rz))
               for k in range(sides)]
        rings.append((pts, tint, dark))

    y = y0
    for h, s, tint, soft in beds:
        if soft:
            rs = [rng.uniform(0.95, 1.03) for _ in range(sides)]
            ring(y + h * 0.3, s, rs, tint, 0.68)
            ring(y + h * 0.75, s * rng.uniform(0.96, 1.02), rs, tint, 0.72)
        else:
            off += dirv * drift + Vector((rng.uniform(-1, 1), 0.0, rng.uniform(-1, 1))) * drift * 0.5
            rs = [rng.uniform(*step) for _ in range(sides)]
            tone = rng.uniform(0.9, 1.08)
            ring(y, s, [r * (1.0 - lip * rng.uniform(0.0, 2.0)) for r in rs], tint, 0.86 * tone)
            ring(y + min(0.03, h * 0.15), s, rs, tint, tone)
            ring(y + h * rng.uniform(0.55, 0.75), s, [r * rng.uniform(0.97, 1.0) for r in rs], tint, tone)
            ring(y + h, s, [r * (1.0 - slope * rng.uniform(0.3, 1.6)) for r in rs], tint, 0.95 * tone)
        y += h

    def face(pts, tints, darks, out_ref):
        n = (pts[1] - pts[0]).cross(pts[2] - pts[0])
        if n.length < 1e-10:
            return
        if n.dot(out_ref) < 0:
            pts, tints, darks = pts[::-1], tints[::-1], darks[::-1]
            n = -n
        n.normalize()
        cols = [scale(rk_col(t, nz, moss=moss, lichen=lichen, var=0.15)(p, n), dk) for p, t, dk in zip(pts, tints, darks)]
        g.flat(pts, M_ROCK, cols, tile)

    for j in range(len(rings) - 1):
        lo, hi = rings[j], rings[j + 1]
        for k in range(sides):
            k2 = (k + 1) % sides
            pts = [lo[0][k], lo[0][k2], hi[0][k2], hi[0][k]]
            ctr = (sum(lo[0], Vector()) + sum(hi[0], Vector())) / (2 * sides)
            face(pts, [lo[1], lo[1], hi[1], hi[1]], [lo[2], lo[2], hi[2], hi[2]], sum(pts, Vector()) / 4 - ctr)
    top, tint, dark = rings[-1]
    c = sum(top, Vector()) / sides + Vector((rng.uniform(-0.03, 0.03), rx * rise * rng.uniform(0.5, 1.5), rng.uniform(-0.03, 0.03)))
    for k in range(sides):
        face([top[k], top[(k + 1) % sides], c], [tint] * 3, [dark, dark, dark * 1.05], Vector((0.0, 1.0, 0.0)))
    return y, c


def rk_crag_a(rng):
    """Leaning slab crag (low-poly crag 0): two fractured bedded blocks, one tipped against the
    other over a crevice, broken chips shed at the foot. ~0.7 tall, inside r ~0.65."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 5, 1.6)
    frac_block(g, (-0.08, 0.26, 0.0), (0.56, 0.36, 0.42), rng, rot=quat_y(0.2) @ quat_z(0.32), notch=0.022, band=0.1,
               col_fn=rk_col(STONE, nz, moss=0.4))
    frac_block(g, (0.32, 0.2, -0.04), (0.4, 0.3, 0.34), rng, rot=quat_y(-0.5) @ quat_z(-0.4), notch=0.02, band=0.1,
               col_fn=rk_col(STONE_COOL, nz, moss=0.3, lichen=LICHEN_SAGE))
    rubble(g, rng, nz, 5, 0.05, 0.1, 0.45, 0.6)
    return b


def rk_crag_b(rng):
    """Tall split crag (low-poly crag 1): ONE jointed outcrop of thick grey beds, parting planes
    eroded in as thin notches, faces stepping back bed to bed, a flank slab fallen off it and
    chips at the foot. ~1.4 tall, inside r ~0.55."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 5, 1.4)
    dark = scale(STONE, 0.78)
    column(g, rng, nz, [(0.5, 1.0, scale(STONE, 0.9), False), (0.1, 0.98, scale(STONE, 0.8), False),
                        (0.38, 0.95, STONE, False), (0.09, 0.92, scale(STONE_COOL, 0.85), False),
                        (0.32, 0.88, STONE_COOL, False), (0.08, 0.8, scale(STONE_COOL, 1.05), False)],
           0.46, 0.4, sides=8, var=(0.66, 1.16), step=(0.86, 1.06), drift=0.035, lip=0.0, slope=0.06, lean=0.07,
           rise=0.1, moss=0.35, tile=0.8)
    frac_block(g, (-0.4, 0.13, 0.14), (0.3, 0.1, 0.2), rng, rot=quat_y(0.7) @ quat_z(0.5), detail=1,
               col_fn=rk_col(STONE, nz, moss=0.25, lichen=LICHEN_SAGE))
    rubble(g, rng, nz, 4, 0.05, 0.09, 0.45, 0.55)
    return b


def rk_crag_c(rng):
    """Cobble spill (low-poly crag 2): a low split bedrock slab with angular chips drifted round
    it, thinning outward. ~0.3 tall, inside r ~0.58."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 5, 1.8)
    frac_block(g, (0.0, 0.06, 0.0), (0.38, 0.17, 0.3), rng, rot=quat_y(0.3) @ quat_z(0.08), notch=0.015, band=0.08,
               col_fn=rk_col(STONE, nz, moss=0.4))
    rubble(g, rng, nz, 9, 0.05, 0.12, 0.3, 0.52)
    return b


def rk_cairn(rng):
    """Waymarker cairn: flat angular slabs piled by hand in seven courses (0.46 x 0.40 at the
    foot), each a broken flag of bedded stone, a long marker stone on top. ~0.62 tall."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 3.0)
    y = -0.02
    courses = [(0.23, 0.2, 0.05), (0.21, 0.18, 0.048), (0.18, 0.16, 0.045), (0.155, 0.14, 0.042), (0.13, 0.115, 0.04),
               (0.105, 0.09, 0.038), (0.08, 0.07, 0.035)]
    for ci, (rx, rz, hh) in enumerate(courses):
        tint = scale(mix(STONE, STONE_COOL, rng.uniform(0, 1)), rng.uniform(0.7, 1.02))
        frac_block(g, (rng.uniform(-0.02, 0.02), y + hh, rng.uniform(-0.02, 0.02)), (rx, hh, rz), rng, nplanes=3,
                   sides=int(rng.integers(5, 8)), flat=(0.95, 0.95),
                   rot=quat_y(rng.uniform(0, 6.28)) @ quat_x(rng.uniform(-0.05, 0.05)) @ quat_z(rng.uniform(-0.05, 0.05)),
                   detail=2 if ci < 3 else 1, col_fn=rk_col(tint, nz, moss=0.45 if ci < 4 else 0.3), tile=0.5,
                   noise=0.0)
        y += hh * 1.85
    frac_block(g, (0.0, y + 0.07, 0.0), (0.045, 0.08, 0.035), rng, nplanes=4, sides=5, flat=(0.9, 0.95),
               rot=quat_y(rng.uniform(0, 6.28)) @ quat_z(0.08), detail=1,
               col_fn=rk_col(scale(STONE, 1.02), nz, moss=0.25), tile=0.5, noise=0.0)
    rubble(g, rng, nz, 3, 0.03, 0.05, 0.28, 0.33)
    return b


def spire(rng, beds, rx, rz, cap=None):
    """Layered sandstone pillar: ONE continuous column of horizontal beds (see `column`), hard
    beds standing out as ledged bands, the soft beds between eroded back into deep notches; a
    `cap` = (r, h, tint) is a separate harder caprock balanced on the neck."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 5, 2.0)
    y, c = column(g, rng, nz, beds, rx, rz, sides=9, var=(0.8, 1.12), step=(0.92, 1.05), drift=0.018,
                  lip=0.02, slope=0.12, rise=0.08, moss=0.12, lichen=LICHEN_ORANGE, tile=0.7)
    if cap:
        cr, ch, ct = cap
        frac_block(g, (c.x + 0.04, y + ch * 0.42, c.z), (cr, ch * 0.5, cr * 0.85), rng, nplanes=5, sides=7,
                   flat=(0.95, 0.95), notch=0.015, band=ch / 2.0, ground_y=y, col_fn=rk_col(ct, nz, moss=0.4))
    rubble(g, rng, nz, 4, 0.04, 0.08, 0.32, 0.4, tint=beds[0][2])
    return b


def rk_spire_a(rng):
    """Slender banded spire (low-poly hoodoo 0): ~1.6 tall, foot r ~0.33; thin soft beds
    eroded into notches between the hard bands, the column tapering up."""
    return spire(rng, [(0.34, 1.0, SAND_RUST, False), (0.12, 0.74, SAND_OCHRE, True),
                       (0.16, 0.92, SAND_OCHRE, False), (0.1, 0.72, SAND_RUST, True),
                       (0.3, 0.84, SAND_PALE, False), (0.11, 0.6, SAND_OCHRE, True),
                       (0.2, 0.7, SAND_OCHRE, False), (0.09, 0.5, SAND_RUST, True),
                       (0.24, 0.56, SAND_PALE, False), (0.06, 0.42, SAND_OCHRE, True),
                       (0.12, 0.4, SAND_OCHRE, False)], 0.33, 0.3)


def rk_spire_b(rng):
    """Balanced rock (low-poly hoodoo 1): a bedded, notched neck carrying a broad cap rock, ~1.6 tall."""
    return spire(rng, [(0.36, 1.0, SAND_OCHRE, False), (0.11, 0.7, SAND_RUST, True),
                       (0.24, 0.8, SAND_RUST, False), (0.1, 0.55, SAND_OCHRE, True),
                       (0.22, 0.62, SAND_PALE, False), (0.08, 0.42, SAND_OCHRE, True),
                       (0.12, 0.46, SAND_OCHRE, False)], 0.29, 0.27,
                 cap=(0.36, 0.26, scale(STONE, 1.02)))


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


def ribbed(g, pts, radii, ribs, rng, nz, depth=0.16, segs_per=1, tip=True, pal=None, spine=None, spine_len=0.03,
           spine_p=0.5, foot=0.35):
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
            body, groove = pal or (CACTUS, CACTUS_DARK)
            c = mix(groove, body, 0.35 + 0.65 * pleat)
            c = scale(c, 1.0 + nz(p * 4.0) * 0.08)
            if p.y < foot:
                c = mix((0.45, 0.4, 0.3), c, smoothstep(foot * 0.15, foot, p.y))
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
        cols.append(scale((pal or (CACTUS_PALE,))[0], 1.1))
        ti = len(verts) - 1
        base = (len(rings) - 1) * n_s
        for s in range(n_s):
            tris.append((base + s, base + (s + 1) % n_s, ti))
    lookup = {id(v): c for v, c in zip(verts, cols)}
    # smooth_mesh calls col_fn(vert, normal) with the very Vector objects we pass.
    smooth_mesh(g, verts, tris, M_PLASTER, lambda p, nn: lookup[id(p)], 0.6)
    # Areole spine tufts along the crests: three needle-thin spines splayed out of each areole
    # (double-sided slivers ~5 mm wide at the root, tapering to a point; never solid cards).
    for i in range(1, len(rings) - 1):
        ring, t, _ = rings[i]
        for s in range(0, n_s, 4):
            if rng.uniform() > spine_p:
                continue
            p, d, _, _ = ring[s]
            q = p + d * 0.006
            b2 = d.cross(t).normalized()
            for _k in range(3):
                a = rng.uniform(0, 6.283)
                side = t * math.cos(a) + b2 * math.sin(a)
                tipv = (d * 0.8 + side * 0.6).normalized() * spine_len * rng.uniform(0.75, 1.3)
                wdir = tipv.cross(d)
                wdir = (wdir if wdir.length > 1e-9 else t).normalized() * 0.0025
                tri = [q - wdir, q + wdir, q + tipv]
                nn = (tri[1] - tri[0]).cross(tri[2] - tri[0]).normalized()
                uv = [(0.0, 0.0), (0.05, 0.0), (0.025, 0.1)]
                col = [spine or SPINE] * 3
                g.poly(tri, uv, [nn] * 3, col, M_PLASTER)
                g.poly(tri[::-1], uv[::-1], [-nn] * 3, col, M_PLASTER)


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


# ─────────────────────────────────────────────────────────────── desert scrub
BARREL = ((0.46, 0.58, 0.46), (0.25, 0.35, 0.28))  # muted blue-green body, groove
PEAR = ((0.5, 0.62, 0.46), (0.36, 0.47, 0.34))
SPINE_RED = (0.85, 0.6, 0.44)
ARE0LE = (0.86, 0.82, 0.66)
BONE = (0.93, 0.9, 0.82)
TWIG = (0.72, 0.64, 0.55)


def ds_barrel(rng, h, r, bloom):
    """Barrel cactus (low-poly barrel: r 0.30, h 0.34): a squat ribbed drum, 14 deep ribs, a hooked
    reddish spine cluster on every areole down each crest, a crown of buds."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 2.0)
    n = 6
    pts = [(0, -0.06 + (h + 0.06) * k / (n - 1), 0) for k in range(n)]
    radii = [r * (0.82 + 0.3 * math.sin(math.pi * (0.25 + 0.7 * k / (n - 1)))) * 0.92 for k in range(n)]
    ribbed(g, pts, radii, 14, rng, nz, depth=0.22, pal=BARREL, spine=SPINE_RED, spine_len=0.045, spine_p=0.8,
           foot=0.08)
    for k in range(7):
        a = k / 7 * 6.283 + rng.uniform(-0.2, 0.2)
        rr = radii[-1] * 0.35
        stone(g, (math.cos(a) * rr, h + 0.04, math.sin(a) * rr), (0.03, 0.035, 0.03), rng, mat=M_PLASTER, detail=0,
              cuts=0, col_fn=lambda p, nn: bloom, tile=0.3)
    return b


def ds_barrel_a(rng):
    return ds_barrel(rng, 0.36, 0.3, (0.95, 0.78, 0.25))


def ds_barrel_b(rng):
    return ds_barrel(rng, 0.3, 0.27, (0.86, 0.42, 0.5))


def pear_pad(g, rng, centre, w, h, yaw, tilt, pal):
    """One prickly-pear pad: a flattened ellipsoid, waxy, paler at the rim, with areoles (a pale
    felt dot + a few spines) in a staggered grid on both faces."""
    verts, faces = icosphere(2)
    rot = quat_y(yaw) @ quat_z(tilt)
    C = Vector(centre)
    out = [C + rot @ Vector((v.x * w, v.y * h, v.z * 0.045)) for v in verts]
    nz = Noise(rng, 3, 2.0)

    def col(p, nn):
        loc = rot.inverted() @ (p - C)
        rim = min(1.0, (loc.x / w) ** 2 + (loc.y / h) ** 2)
        return scale(mix(pal[1], pal[0], 0.4 + 0.6 * rim ** 2), 1.0 + nz(p * 6.0) * 0.07)
    smooth_mesh(g, out, faces, M_PLASTER, col, 0.4, inside=centre)
    for i in range(-2, 3):
        for j in range(-2, 3):
            u, v = (i + (0.5 if j % 2 else 0.0)) * 0.36, j * 0.36
            if u * u + v * v > 0.75:
                continue
            for side in (1, -1):
                z = side * 0.045 * math.sqrt(max(0.0, 1 - u * u - v * v)) * 1.02
                p = C + rot @ Vector((u * w, v * h, z))
                nn = (rot @ Vector((0, 0, side))).normalized()
                ax = (rot @ Vector((1, 0, 0))).normalized()
                ay = nn.cross(ax)
                s = 0.009
                g.poly([p + (ax + ay) * s, p + (ax - ay) * s, p + (-ax - ay) * s, p + (-ax + ay) * s][::side],
                       [(0, 0), (0.1, 0), (0.1, 0.1), (0, 0.1)][::side], [nn] * 4, [ARE0LE] * 4, M_PLASTER)
                tip = p + nn * 0.03 + ay * 0.012
                for sx in (ax, -ax):
                    q = [p + sx * 0.004, p - sx * 0.004, tip]
                    g.poly(q, [(0, 0), (0.1, 0), (0.05, 0.1)], [ay] * 3, [SPINE] * 3, M_PLASTER)
                    g.poly(q[::-1], [(0.05, 0.1), (0.1, 0), (0, 0)], [-ay] * 3, [SPINE] * 3, M_PLASTER)


def ds_pear(rng, flip, top):
    """Prickly pear (low-poly pear): a clump of jointed pads, ~0.85 tall, a few purple-red fruits."""
    b = Builder()
    g = G(b)
    pads = [((0, 0.27, 0), 0.22, 0.29, 0.0, 0.08), ((-flip * 0.2, 0.52, 0.05), 0.18, 0.24, flip * 0.55, flip * 0.45),
            ((flip * 0.21, 0.55, -0.04), 0.17, 0.23, -flip * 0.5, -flip * 0.35)]
    if top:
        pads.append(((0.02, 0.76, 0.02), 0.13, 0.17, 0.2, 0.15))
    for c, w, h, yaw, tilt in pads:
        pear_pad(g, rng, c, w, h, yaw, tilt, PEAR)
    for c in [(-flip * 0.24, 0.75, 0.05), (flip * 0.25, 0.77, -0.03), (-flip * 0.1, 0.76, 0.04)]:
        stone(g, c, (0.028, 0.04, 0.028), rng, mat=M_PLASTER, detail=0, cuts=0,
              col_fn=lambda p, nn: (0.55, 0.16, 0.24), tile=0.3)
    return b


def ds_pear_a(rng):
    return ds_pear(rng, 1.0, True)


def ds_pear_b(rng):
    return ds_pear(rng, -1.0, False)


def ds_deadbush(rng, n, spread):
    """Dead desert shrub / tumbleweed stump: wiry bleached stems fanning from a woody crown, each
    forking twice. Bark scan, tinted sun-bleached grey."""
    b = Builder()
    g = G(b)
    for k in range(n):
        a = k / n * 6.283 + rng.uniform(-0.3, 0.3)
        tilt = rng.uniform(0.35, 0.95)
        ln = spread * rng.uniform(0.75, 1.1)
        d = Vector((math.cos(a) * math.sin(tilt), math.cos(tilt), math.sin(a) * math.sin(tilt)))
        p0 = Vector((0, -0.02, 0))
        p1 = p0 + d * ln * 0.5 + Vector((rng.uniform(-0.03, 0.03), 0, rng.uniform(-0.03, 0.03)))
        p2 = p1 + (d + Vector((0, 0.25, 0))).normalized() * ln * 0.5
        c = scale(TWIG, rng.uniform(0.75, 1.05))
        tube(g, [p0, p1, p2], [0.013, 0.009, 0.004], 4, M_BARK, c, tile=0.4, cap=False)
        for f in (0.55, 0.85):
            q = p1 if f < 0.7 else p2
            side = Vector((rng.normal(), 0.4, rng.normal())).normalized()
            tube(g, [q, q + (d + side).normalized() * ln * 0.3], [0.006, 0.002], 3, M_BARK, c, tile=0.4, cap=False)
    return b


def ds_deadbush_a(rng):
    return ds_deadbush(rng, 9, 0.36)


def ds_deadbush_b(rng):
    return ds_deadbush(rng, 12, 0.3)


def ds_rock(rng, big):
    """Wind-scoured desert sandstone (low-poly bleached rocks): bedded, pale, sand-blasted."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 2.0)
    pale = (0.98, 0.9, 0.78)
    if big:
        frac_block(g, (0, 0.2, 0), (0.3, 0.24, 0.26), rng, notch=0.02, band=0.09,
                   col_fn=rk_col(pale, nz, moss=0.0, var=0.12))
        frac_block(g, (0.24, 0.08, 0.1), (0.15, 0.1, 0.13), rng, notch=0.012, band=0.09,
                   col_fn=rk_col(scale(pale, 0.9), nz, moss=0.0))
    else:
        frac_block(g, (0, 0.25, 0), (0.24, 0.3, 0.22), rng, notch=0.02, band=0.1,
                   col_fn=rk_col(scale(pale, 0.95), nz, moss=0.0, var=0.12))
        frac_block(g, (0.05, 0.6, -0.02), (0.15, 0.12, 0.14), rng, notch=0.012, band=0.1,
                   col_fn=rk_col(pale, nz, moss=0.0))
    rubble(g, rng, nz, 3, 0.03, 0.06, 0.3, 0.4, tint=pale)
    return b


def ds_rock_a(rng):
    return ds_rock(rng, True)


def ds_rock_b(rng):
    return ds_rock(rng, False)


def ds_bones(rng):
    """Sun-bleached cattle skull half sunk in the sand, with a couple of long bones."""
    b = Builder()
    g = G(b)
    bone = lambda p, nn: scale(BONE, 0.85 + 0.15 * smoothstep(-0.02, 0.15, p.y))  # noqa: E731
    stone(g, (0, 0.08, 0), (0.12, 0.09, 0.15), rng, mat=M_PLASTER, detail=2, cuts=1, rough=0.06, col_fn=bone,
          tile=0.3, rot=quat_y(0.0))
    stone(g, (0, 0.06, 0.17), (0.065, 0.055, 0.11), rng, mat=M_PLASTER, detail=1, cuts=1, rough=0.05, col_fn=bone,
          tile=0.3, rot=quat_y(0.0))
    for sx in (1, -1):
        stone(g, (sx * 0.05, 0.11, 0.09), (0.028, 0.026, 0.02), rng, mat=M_PLASTER, detail=1, cuts=0,
              col_fn=lambda p, nn: (0.2, 0.17, 0.14), tile=0.3)
        tube(g, [(sx * 0.1, 0.13, -0.03), (sx * 0.2, 0.17, -0.06), (sx * 0.26, 0.25, -0.02)], [0.025, 0.017, 0.006],
             6, M_PLASTER, (0.82, 0.76, 0.64), tile=0.3)
    for (x, z, yaw, ln) in ((0.26, 0.05, 0.5, 0.3), (0.3, -0.13, -0.7, 0.26)):
        d = Vector((math.cos(yaw), 0, math.sin(yaw)))
        p = Vector((x, 0.015, z))
        tube(g, [p - d * ln / 2, p + d * ln / 2], [0.02, 0.02], 6, M_PLASTER, BONE, tile=0.3, cap=False)
        for e in (-1, 1):
            stone(g, tuple(p + d * ln / 2 * e), (0.035, 0.028, 0.03), rng, mat=M_PLASTER, detail=1, cuts=0,
                  col_fn=bone, tile=0.3)
    return b

# ─────────────────────────────────────────────────────────────── ore nodes
def rk_ore_rock(rng):
    """Ore node rock (verbs::ore_rock_mesh, ~0.95 x 0.82, ~0.62 tall): a dark, iron-stained
    fractured outcrop the crystal core erupts from."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 5, 1.6)
    dark = (0.5, 0.48, 0.5)
    frac_block(g, (0.0, 0.18, 0.0), (0.5, 0.3, 0.42), rng, rot=quat_y(0.35), notch=0.018, band=0.1,
               col_fn=rk_col(dark, nz, moss=0.15, lichen=(0.62, 0.42, 0.28)))
    frac_block(g, (0.32, 0.26, 0.15), (0.27, 0.22, 0.25), rng, notch=0.015, band=0.1,
               col_fn=rk_col(scale(dark, 0.85), nz, moss=0.1))
    frac_block(g, (-0.3, 0.22, -0.16), (0.25, 0.2, 0.29), rng, notch=0.015, band=0.1,
               col_fn=rk_col(scale(dark, 1.1), nz, moss=0.1))
    rubble(g, rng, nz, 4, 0.04, 0.08, 0.5, 0.62, tint=dark)
    return b


def crystal(g, base, axis, r, length, tip, rng):
    """One hexagonal quartz-like prism with a pyramidal termination: flat facets (a real crystal
    IS faceted), slightly irregular face widths."""
    axis = Vector(axis).normalized()
    u = axis.orthogonal().normalized()
    w = axis.cross(u)
    rs = [r * rng.uniform(0.85, 1.1) for _ in range(6)]
    ring0 = [Vector(base) + (u * math.cos(k * math.pi / 3) + w * math.sin(k * math.pi / 3)) * rs[k] for k in range(6)]
    ring1 = [p + axis * length for p in ring0]
    apex = Vector(base) + axis * (length + tip)
    col = (1.0, 1.0, 1.0)
    for k in range(6):
        k2 = (k + 1) % 6
        g.flat([ring0[k], ring0[k2], ring1[k2], ring1[k]], M_PLASTER, col, 0.3)
        g.flat([ring1[k], ring1[k2], apex], M_PLASTER, col, 0.3)


def rk_ore_crystals(rng):
    """The glowing gem core (verbs::ore_crystal_mesh): a tall centre prism, two strong leaners, a mid
    fan and shoulder chips, rooted into the rock. Geometry only (the game draws it with the ore's
    own emissive gem material)."""
    b = Builder()
    g = G(b)
    for base, axis, r, ln, tip in [((0.0, 0.25, 0.0), (0.03, 1, 0.02), 0.11, 0.72, 0.24),
                                   ((0.12, 0.3, 0.06), (0.55, 1, 0.2), 0.08, 0.42, 0.16),
                                   ((-0.11, 0.3, -0.05), (-0.6, 1, -0.15), 0.078, 0.44, 0.16),
                                   ((0.03, 0.3, 0.12), (0.1, 1, 0.6), 0.063, 0.32, 0.12),
                                   ((-0.04, 0.3, -0.12), (-0.1, 1, -0.6), 0.06, 0.3, 0.12),
                                   ((0.1, 0.3, -0.08), (0.4, 1, -0.45), 0.053, 0.24, 0.1),
                                   ((0.22, 0.3, 0.02), (1.1, 1, 0.05), 0.042, 0.16, 0.08),
                                   ((-0.2, 0.3, 0.09), (-1.2, 1, 0.2), 0.04, 0.15, 0.07)]:
        crystal(g, base, axis, r, ln, tip, rng)
    return b


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
    "ds_barrel_a": ds_barrel_a,
    "ds_barrel_b": ds_barrel_b,
    "ds_pear_a": ds_pear_a,
    "ds_pear_b": ds_pear_b,
    "ds_deadbush_a": ds_deadbush_a,
    "ds_deadbush_b": ds_deadbush_b,
    "ds_rock_a": ds_rock_a,
    "ds_rock_b": ds_rock_b,
    "ds_bones": ds_bones,
    "rk_ore_rock": rk_ore_rock,
    "rk_ore_crystals": rk_ore_crystals,
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
