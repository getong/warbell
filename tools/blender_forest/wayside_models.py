"""Realistic replacements for the hand-built roadside furniture and story set-pieces -> wayside.glb.

Wayside (wayside.rs): junction signpost, mile cairn, post-and-rail fence run, roadside shrine.
Story set-pieces (poi.rs): burned cabin, wayside graves, standing-stone circle, fallen watchtower,
shepherd's hut + pen, the gallows. Vignette (vignettes.rs): the forest's Abandoned Camp.

Every model keeps the footprint, heights and anchors of the low-poly original it replaces, so the
collision boxes registered in code still hug the drawn mass, and each stays inside the visual
radius its placement reserves. Authored in game coordinates (Y up, +Z = the original's local +Z)
through geo.py; ground-contact parts run ~0.25u below y=0 so a piece seated on a slightly uneven
spot never floats. Materials by name: bark_oak + the s_* PBR sets (materials.py), vertex colour
tints the albedo (weathering, soot, moss, ground damp).

    blender -b --factory-startup --python tools/blender_forest/wayside_models.py
"""
import json
import math
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402
from common import OUT, clear_scene, export_glb  # noqa: E402
from geo import G, box, frustum, quat_x, quat_y, quat_z, sheet, tube  # noqa: E402
from meshkit import Builder  # noqa: E402

M_BARK, M_PLANK, M_STONE, M_HIDE, M_THATCH, M_CLOTH, M_IRON, M_ROCK, M_EARTH, M_FRUIT, M_TIMBER = range(11)
MATS = ["bark_oak", "s_planks", "s_stone", "s_hide", "s_thatch", "s_cloth", "s_iron", "s_rock", "s_earth", "fruit",
        "s_timber"]

ROPE = (0.95, 0.8, 0.55)
CHAR = (0.13, 0.12, 0.11)
IRON = (0.55, 0.5, 0.48)
# s_planks (Poly Haven medieval_wood) is a wall of nailed boards ~0.1875 of the texture wide;
# s_timber (materials.py) is the same scan with the nail rows cut out, boards ~0.2 wide. A face of
# a hewn member samples the inside of one s_timber board (texture u, ~0.165 wide), so posts, rails
# and beams show clean weathered grain; planks / doors / decks keep their nails (s_planks).
TIMBER_ZONES = [k * 0.2 + 0.017 for k in range(5)]
TIMBER_ZONE_W = 0.165
BOARD_CENTRES = {M_PLANK: [k * 0.1875 + 0.094 for k in range(5)], M_TIMBER: [k * 0.2 + 0.1 for k in range(5)]}


def V(x, y, z):
    return Vector((x, y, z))


def tube(g, pts, radii, sides, mat, col, tile=1.1, cap=True, uv_phase=0.0, col_fn=None):
    """geo.tube with end caps whose winding always agrees with their outward normal (geo's caps
    can come out wound against it on some frames and render black)."""
    from geo import tube as geo_tube
    geo_tube(g, pts, radii, sides, mat, col, tile=tile, cap=False, uv_phase=uv_phase, col_fn=col_fn)
    if not cap:
        return
    pts = [Vector(p) for p in pts]
    # The same parallel-transported frames geo.tube used, so each cap meets its ring exactly.
    frames = []
    n_prev = None
    for i in range(len(pts)):
        if i == 0:
            t = (pts[1] - pts[0]).normalized()
        elif i == len(pts) - 1:
            t = (pts[-1] - pts[-2]).normalized()
        else:
            t = (pts[i + 1] - pts[i - 1]).normalized()
        n = t.orthogonal().normalized() if n_prev is None else (n_prev - t * n_prev.dot(t)).normalized()
        n_prev = n
        frames.append((t, n, t.cross(n)))
    for end, sign in ((0, -1), (len(pts) - 1, 1)):
        t, a0, b0 = frames[end]
        nn = t * sign
        r = radii[end]
        c = col_fn(1.0 if end else 0.0) if col_fn else col
        dirs = [a0 * math.cos(2 * math.pi * s / sides) + b0 * math.sin(2 * math.pi * s / sides) for s in range(sides)]
        ring = [pts[end] + d * r for d in dirs]
        # A shallow dome (a rounded log end / tied bundle), normals blending from the rim to the axis.
        tip = pts[end] + nn * r * 0.3
        for s in range(sides):
            k = (s + 1) % sides
            tri = [ring[s], ring[k], tip]
            ns = [(nn * 0.7 + dirs[s] * 0.7).normalized(), (nn * 0.7 + dirs[k] * 0.7).normalized(), nn.copy()]
            if (tri[1] - tri[0]).cross(tri[2] - tri[0]).dot(nn) < 0:
                tri, ns = [tri[1], tri[0], tri[2]], [ns[1], ns[0], ns[2]]
            # World-scaled UVs like every other face.
            uv = [(0.5 + (p - pts[end]).dot(a0) / tile, 0.5 + (p - pts[end]).dot(b0) / tile) for p in tri]
            g.poly(tri, uv, ns, [scale(c, 1.1)] * 3, mat)


def smoothstep(a, b, x):
    t = min(max((x - a) / (b - a), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def mix(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def scale(c, k):
    return tuple(x * k for x in c)


# ─────────────────────────────────────────────────────────────── primitives
def smooth_mesh(g, verts, tris, mat, col_fn, tile, inside=None):
    """Indexed triangles -> smooth (area-weighted) vertex normals, per-face box-projected world UVs.
    `inside`: a point inside the (roughly convex) shape; triangles facing it get flipped."""
    tris = list(tris)
    if inside is not None:
        c = Vector(inside)
        for i, (a, b, d) in enumerate(tris):
            n = (verts[b] - verts[a]).cross(verts[d] - verts[a])
            if n.dot((verts[a] + verts[b] + verts[d]) / 3 - c) < 0:
                tris[i] = (a, d, b)
    vn = [Vector((0, 0, 0)) for _ in verts]
    fns = []
    for a, b, d in tris:
        n = (verts[b] - verts[a]).cross(verts[d] - verts[a])
        fns.append(n)
        for i in (a, b, d):
            vn[i] += n
    vn = [n.normalized() if n.length > 1e-12 else Vector((0, 1, 0)) for n in vn]
    cols = [col_fn(verts[i], vn[i]) for i in range(len(verts))]
    for (a, b, d), fn in zip(tris, fns):
        if fn.length < 1e-14:
            continue
        ax = max(range(3), key=lambda k: abs(fn[k]))
        uvs = []
        for i in (a, b, d):
            p = verts[i]
            u, v = (p.z, p.y) if ax == 0 else ((p.x, p.z) if ax == 1 else (p.x, p.y))
            uvs.append((u / tile, v / tile))
        g.poly([verts[a], verts[b], verts[d]], uvs, [vn[a], vn[b], vn[d]], [cols[a], cols[b], cols[d]], mat)


def icosphere(detail):
    t = (1 + 5 ** 0.5) / 2
    verts = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
             (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    faces = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2),
             (10, 7, 6), (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11),
             (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    verts = [Vector(v).normalized() for v in verts]
    for _ in range(detail):
        cache = {}
        nf = []

        def mid(a, b):
            k = (min(a, b), max(a, b))
            if k not in cache:
                verts.append(((verts[a] + verts[b]) / 2).normalized())
                cache[k] = len(verts) - 1
            return cache[k]
        for a, b, c in faces:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            nf += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        faces = nf
    return verts, faces


class Noise:
    """Cheap smooth 3D noise: a few randomly oriented sine waves."""

    def __init__(self, rng, octaves=5, f0=1.6):
        self.w = []
        for k in range(octaves):
            d = Vector(rng.normal(size=3)).normalized()
            f = f0 * (1.9 ** k) * rng.uniform(0.8, 1.2)
            self.w.append((d, f, rng.uniform(0, 6.283), 0.55 ** k))
        self.norm = sum(a for _, _, _, a in self.w)

    def __call__(self, p):
        return sum(a * math.sin(p.dot(d) * f + ph) for d, f, ph, a in self.w) / self.norm


def rock_col(base, moss=0.0, ground=0.0, dark_below=0.32, lichen=(0.52, 0.62, 0.3), noise=None, var=0.12):
    """Rock tint: darker toward the ground contact, moss/lichen on up-facing surfaces."""
    def f(p, n):
        k = 1.0 - (1.0 - dark_below) * (1.0 - smoothstep(ground - 0.05, ground + 0.3, p.y))
        c = scale(base, k * (1.0 + (noise(p * 3.0) * var if noise else 0.0)))
        m = moss * smoothstep(0.3, 0.85, n.y) * (0.7 + 0.3 * (noise(p * 5.0) if noise else 0.0))
        return mix(c, scale(lichen, k), max(0.0, min(m, 1.0)))
    return f


def stone(g, centre, radii, rng, mat=M_ROCK, col_fn=None, tile=0.7, detail=2, rough=0.14, rot=None, cuts=2,
          flat_y=None):
    """A fieldstone: displaced icosphere with a couple of planar fracture faces, smooth normals."""
    verts, faces = icosphere(detail)
    nz = Noise(rng, 4, 1.4)
    planes = []
    for _ in range(cuts):
        d = Vector(rng.normal(size=3)).normalized()
        planes.append((d, rng.uniform(0.62, 0.85)))
    if flat_y is not None:
        planes += [(Vector((0, 1, 0)), flat_y), (Vector((0, -1, 0)), flat_y)]
    rot = rot or quat_y(rng.uniform(0, 6.283))
    out = []
    for v in verts:
        p = v * (1.0 + rough * nz(v))
        for d, c in planes:
            e = p.dot(d) - c
            if e > 0:
                p = p - d * e * 0.92
        out.append(Vector(centre) + rot @ Vector((p.x * radii[0], p.y * radii[1], p.z * radii[2])))
    col_fn = col_fn or rock_col((1.0, 1.0, 0.97), ground=0.0, noise=nz)
    smooth_mesh(g, out, faces, mat, col_fn, tile, inside=centre)


def slab(g, centre, size, rot, rng, mat=M_ROCK, col_fn=None, tile=0.8, res=(5, 12, 3), round_r=0.07, taper=0.0,
         rough=0.035, crown=0.0, cuts=0, lean_top=(0.0, 0.0)):
    """A rough-hewn block (megalith / headstone / lintel): subdivided rounded box, tapered and
    noise-displaced, optional fracture planes; shared vertices so the surface shades smooth."""
    hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
    nx, ny, nzr = res
    nz = Noise(rng, 5, 2.2)
    planes = [(Vector(rng.normal(size=3)).normalized(), rng.uniform(0.75, 0.92)) for _ in range(cuts)]
    index = {}
    verts = []

    def vid(i, j, k):
        key = (i, j, k)
        if key not in index:
            p = Vector((-hx + 2 * hx * i / nx, -hy + 2 * hy * j / ny, -hz + 2 * hz * k / nzr))
            r = min(round_r, hx * 0.95, hy * 0.95, hz * 0.95)
            c = Vector((max(-hx + r, min(hx - r, p.x)), max(-hy + r, min(hy - r, p.y)), max(-hz + r, min(hz - r, p.z))))
            d = p - c
            q = c + d.normalized() * r if d.length > 1e-9 else p
            nrm = d.normalized() if d.length > 1e-9 else Vector((0, 1, 0))
            f = (q.y + hy) / (2 * hy)
            q.x *= 1.0 - taper * f
            q.z *= 1.0 - taper * f * 0.7
            if crown:
                q.y -= crown * ((q.x / hx) ** 2 + (q.z / hz) ** 2) * smoothstep(0.55, 1.0, f) * hy
            q.x += lean_top[0] * f * f
            q.z += lean_top[1] * f * f
            q += nrm * rough * nz(q * 1.0) * min(hx, hz) * 2
            for dd, cc in planes:
                s = Vector((q.x / hx, q.y / hy, q.z / hz))
                e = s.dot(dd) - cc
                if e > 0:
                    q -= Vector((dd.x * hx, dd.y * hy, dd.z * hz)) * e * 0.9
            index[key] = len(verts)
            verts.append(q)
        return index[key]

    quads = []
    for (a, na), (b, nb) in (((0, nx), (1, ny)), ((0, nx), (2, nzr)), ((1, ny), (2, nzr))):
        c = 3 - a - b
        nc = (nx, ny, nzr)[c]
        for side in (0, nc):
            for i in range(na):
                for j in range(nb):
                    ids = []
                    for di, dj in ((0, 0), (1, 0), (1, 1), (0, 1)):
                        co = [0, 0, 0]
                        co[a], co[b], co[c] = i + di, j + dj, side
                        ids.append(vid(*co))
                    quads.append(ids)
    tris = []
    for q in quads:
        tris += [(q[0], q[1], q[2]), (q[0], q[2], q[3])]
    world = [Vector(centre) + rot @ p for p in verts]
    col_fn = col_fn or rock_col((1.0, 1.0, 0.97), noise=nz)
    smooth_mesh(g, world, tris, mat, col_fn, tile, inside=centre)


def mound(g, centre, rx, rz, h, rng, mat=M_EARTH, col_fn=None, tile=0.9, rings=6, seg=20, skirt=0.1, rough=0.12,
          edge=0.12, power=0.8):
    """A low earth mound / ash bed: polar grid, irregular outline, edge sinks below y=0."""
    nz = Noise(rng, 4, 2.0)
    cx, cy, cz = centre
    verts = [Vector((cx, cy + h, cz))]
    for j in range(1, rings + 1):
        f = j / rings
        for i in range(seg):
            a = 2 * math.pi * i / seg
            dirv = Vector((math.cos(a), 0, math.sin(a)))
            e = 1.0 + edge * nz(dirv * 1.3 + Vector((0, 3.1, 0)))
            x = cx + math.cos(a) * rx * f * e
            z = cz + math.sin(a) * rz * f * e
            y = cy + h * (max(0.0, 1 - f * f) ** power) * (1 + rough * nz(Vector((x, 0, z)) * 2.0)) - skirt * f ** 6
            verts.append(Vector((x, y, z)))
    tris = []
    for i in range(seg):
        tris.append((0, 1 + (i + 1) % seg, 1 + i))
    for j in range(rings - 1):
        r0, r1 = 1 + j * seg, 1 + (j + 1) * seg
        for i in range(seg):
            a, b = r0 + i, r0 + (i + 1) % seg
            c, d = r1 + (i + 1) % seg, r1 + i
            tris += [(a, b, c), (a, c, d)]
    col_fn = col_fn or (lambda p, n: (0.6, 0.52, 0.45))
    smooth_mesh(g, verts, tris, mat, col_fn, tile, inside=(cx, cy - 50.0, cz))


def beam(g, pts, w, h, up=(0, 1, 0), mat=M_PLANK, col=(1, 1, 1), chamfer=0.18, mode="timber", rng=None,
         jag=(0.0, 0.0), point=0.0, col_fn=None, rough=0.0, tile=None, cap=(True, True)):
    """Squared timber / plank / board along a polyline. Cross-section `w` (along s = up x t) by
    `h` (along u = t x s), chamfered. UVs keep the grain along the member:
    - mode "timber": each face samples the inside of one s_timber board (posts, beams, rails;
      `M_PLANK` is promoted to `M_TIMBER`);
    - mode "plank": broad faces show one whole board — of s_planks, nails and all (decks, doors),
      or of s_timber (sign boards);
    - mode "bark": continuous wrap (charred beams in bark_oak).
    `jag` splinters an end (broken / burnt through), `point` sharpens the far end into an arrow tip
    (collapses the w axis)."""
    rng = rng if rng is not None else np.random.default_rng(7)
    pts = [Vector(p) for p in pts]
    upv = Vector(up).normalized()
    hw, hh = w / 2, h / 2
    c = chamfer * min(w, h)
    if c > 1e-5:
        prof = [(hw, hh - c), (hw - c, hh), (-hw + c, hh), (-hw, hh - c), (-hw, -hh + c), (-hw + c, -hh), (hw - c, -hh),
                (hw, -hh + c)]
    else:
        prof = [(hw, hh), (-hw, hh), (-hw, -hh), (hw, -hh)]
    if rough:
        prof = [(s + rng.uniform(-rough, rough) * min(w, h), u + rng.uniform(-rough, rough) * min(w, h)) for s, u in prof]
    n = len(prof)
    frames = []
    for i, p in enumerate(pts):
        if i == 0:
            t = pts[1] - pts[0]
        elif i == len(pts) - 1:
            t = pts[-1] - pts[-2]
        else:
            t = pts[i + 1] - pts[i - 1]
        t.normalize()
        s = upv.cross(t)
        if s.length < 1e-4:
            s = Vector((0, 0, 1)).cross(t)
        s.normalize()
        u = t.cross(s).normalized()
        frames.append((t, s, u))
    rings = []
    for i, (p, (t, s, u)) in enumerate(zip(pts, frames)):
        ring = []
        for k, (ps, pu) in enumerate(prof):
            q = p + s * ps + u * pu
            if i == 0 and jag[0]:
                q += t * rng.uniform(0, jag[0])
            if i == len(pts) - 1 and jag[1]:
                q -= t * rng.uniform(0, jag[1])
            ring.append(q)
        rings.append(ring)
    if point:
        t, s, u = frames[-1]
        tip = pts[-1] + t * point
        rings.append([tip + u * pu for ps, pu in prof])
        pts = pts + [tip]
        frames = frames + [frames[-1]]
    # arc length per ring
    arc = [0.0]
    for i in range(1, len(pts)):
        arc.append(arc[-1] + (pts[i] - pts[i - 1]).length)
    if mode == "timber":
        if mat == M_PLANK:
            mat = M_TIMBER
        tl = tile or max(max(w, h) / (TIMBER_ZONE_W - 0.01), 0.5)
    elif mode == "plank":
        tl = tile or 1.0
    else:
        tl = tile or 0.55
    vph = rng.uniform(0, 4)
    widths = [math.hypot(prof[(k + 1) % n][0] - prof[k][0], prof[(k + 1) % n][1] - prof[k][1]) for k in range(n)]
    perim = [0.0]
    for wk in widths:
        perim.append(perim[-1] + wk)
    zone_face = [TIMBER_ZONES[int(rng.integers(len(TIMBER_ZONES)))] + rng.uniform(0, max(0.0, TIMBER_ZONE_W - wk / tl))
                 for wk in widths]
    centres = BOARD_CENTRES.get(mat, BOARD_CENTRES[M_PLANK])
    board_c = centres[int(rng.integers(len(centres)))]
    L = arc[-1] if arc[-1] > 0 else 1.0

    def colour(i):
        if col_fn:
            return col_fn(arc[i] / L)
        return col

    for i in range(len(rings) - 1):
        c0, c1 = colour(i), colour(i + 1)
        for k in range(n):
            k2 = (k + 1) % n
            quad = [rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]]
            if mode == "timber":
                u0, u1 = zone_face[k], zone_face[k] + widths[k] / tl
            elif mode == "plank":
                u0 = board_c - widths[k] / 2 / tl
                u1 = u0 + widths[k] / tl
            else:
                u0, u1 = perim[k] / tl, perim[k + 1] / tl
            v0, v1 = vph + arc[i] / tl, vph + arc[i + 1] / tl
            uv = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
            cs = [c0, c0, c1, c1]
            # outward = direction of the profile edge midpoint
            t, s, u = frames[i]
            mid2 = ((prof[k][0] + prof[k2][0]) / 2, (prof[k][1] + prof[k2][1]) / 2)
            outward = s * mid2[0] + u * mid2[1]
            nrm = (quad[1] - quad[0]).cross(quad[3] - quad[0])
            if nrm.length < 1e-10:
                nrm = (quad[2] - quad[1]).cross(quad[0] - quad[1])
            if nrm.length < 1e-10:
                continue
            if nrm.dot(outward) < 0:
                quad, uv, cs = quad[::-1], uv[::-1], cs[::-1]
                nrm = -nrm
            nrm.normalize()
            g.poly(quad, uv, [nrm] * 4, cs, mat)
    ends = [(0, -1)] if point else [(0, -1), (len(rings) - 1, 1)]
    for idx, sign in ends:
        if not cap[0 if sign < 0 else 1]:
            continue
        ring = rings[idx]
        t = frames[idx][0] * sign
        centre = sum(ring, Vector((0, 0, 0))) / len(ring)
        if jag[0 if sign < 0 else 1]:
            centre += t * jag[0 if sign < 0 else 1] * rng.uniform(-0.2, 0.5)
        cc = colour(idx)
        for k in range(n):
            a, b2 = ring[k], ring[(k + 1) % n]
            tri = [a, b2, centre]
            nn = (tri[1] - tri[0]).cross(tri[2] - tri[0])
            if nn.length < 1e-12:
                continue
            if nn.dot(t) < 0:
                tri = tri[::-1]
                nn = -nn
            nn.normalize()
            uv = [(0.3 + (p - centre).dot(frames[idx][1]) / 0.5, 0.3 + (p - centre).dot(frames[idx][2]) / 0.5) for p in tri]
            g.poly(tri, uv, [nn] * 3, [scale(cc, 0.85)] * 3, mat)


def board(g, centre, ldir, normal, length, width, thick, **kw):
    """A board `length` long along `ldir`, `width` across (perpendicular to ldir and normal), `thick`
    along `normal`."""
    c = Vector(centre)
    ldir = Vector(ldir).normalized()
    normal = Vector(normal).normalized()
    kw.setdefault("mode", "plank")
    kw.setdefault("chamfer", 0.12)
    beam(g, [c - ldir * (length / 2), c + ldir * (length / 2)], width, thick, up=normal, **kw)


def lbox(g, centre, size, rot, mat, col, tile=1.0, grain=1, u0=0.0, v0=0.0):
    """Oriented box with LOCAL-frame UVs: v runs along local axis `grain` on the side faces (thatch
    straws down a roof slope, stone courses level on a wall). `col` is one colour, or a list whose
    first / third entries are the colours at the low / high end of the grain axis."""
    c = Vector(centre)
    h = [size[0] / 2, size[1] / 2, size[2] / 2]
    if isinstance(col, list):
        lo, hi = col[0], col[2]
    else:
        lo = hi = col
    for ax in range(3):
        for sgn in (-1, 1):
            o = [a for a in range(3) if a != ax]
            if grain in o:
                va = grain
                ua = o[0] if o[1] == grain else o[1]
            else:
                ua, va = o
            corners = []
            for du, dv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                p = [0.0, 0.0, 0.0]
                p[ax] = sgn * h[ax]
                p[ua] = du * h[ua]
                p[va] = dv * h[va]
                corners.append(((du * h[ua] + u0) / tile, (dv * h[va] + v0) / tile, Vector(p)))
            nl = Vector((0, 0, 0))
            nl[ax] = sgn
            pts = [c + rot @ q[2] for q in corners]
            uvs = [(q[0], q[1]) for q in corners]
            cols = [lo if q[2][grain] < 0 else hi for q in corners]
            nw = rot @ nl
            fn = (pts[1] - pts[0]).cross(pts[3] - pts[0])
            if fn.dot(nw) < 0:
                pts, uvs, cols = pts[::-1], uvs[::-1], cols[::-1]
            g.poly(pts, uvs, [nw] * 4, cols, mat)


def lashing(g, p, axis, r, rng, turns=3):
    a = Vector(axis).normalized()
    side = a.orthogonal().normalized()
    for k in range(turns):
        o = Vector(p) + a * (k - (turns - 1) / 2) * 0.03
        ring = [o + (side * math.cos(2 * math.pi * s / 8) + a.cross(side) * math.sin(2 * math.pi * s / 8)) * r
                for s in range(9)]
        tube(g, ring, [0.011] * len(ring), 4, M_CLOTH, ROPE, tile=0.25, cap=False)


def pole(g, p0, p1, r0, r1, rng, mat=M_BARK, col=(0.9, 0.86, 0.8), sides=7, wobble=0.012, tile=0.9, col_fn=None,
         cap=True, segs=3):
    """A round pole / log with a slight natural wobble."""
    p0, p1 = Vector(p0), Vector(p1)
    pts, radii = [], []
    for k in range(segs + 1):
        f = k / segs
        q = p0.lerp(p1, f)
        if 0 < k < segs:
            q += Vector(rng.normal(size=3)) * wobble
        pts.append(q)
        radii.append(r0 + (r1 - r0) * f)
    tube(g, pts, radii, sides, mat, col, tile=tile, cap=cap, uv_phase=rng.uniform(0, 3), col_fn=col_fn)


def weathered(base, damp=0.6, top=1.0):
    """Timber colour along a vertical member: damp-dark at the foot, sun-greyed toward the top."""
    def f(t):
        k = damp + (top - damp) * smoothstep(0.0, 0.35, t)
        return scale(base, k)
    return f


def charred(rng, base=CHAR, var=0.35):
    k = rng.uniform(1 - var, 1 + var)
    warm = rng.uniform(0, 1)
    c = scale(base, k)
    return (c[0] * (1 + 0.25 * warm), c[1] * (1 + 0.1 * warm), c[2])


# ─────────────────────────────────────────────────────────────── wayside furniture
def wayside_signpost(rng):
    """Junction fingerpost: round weathered post (r 0.07, collider r 0.065) to ~2.05, a little gable
    cap, two arrow boards at y 1.62 / 1.38 pointing along yaw 0.35 / -2.2 (tips ~0.79 out, inside
    the 0.84 visual radius), packing stones at the foot."""
    b = Builder()
    g = G(b)
    lean = quat_z(rng.uniform(-0.015, 0.015)) @ quat_x(rng.uniform(-0.015, 0.015))
    base, top = V(0, -0.3, 0), lean @ V(0, 2.04, 0)
    post_col = (0.95, 0.9, 0.8)
    tube(g, [base, base.lerp(top, 0.5), top, top + lean @ V(0, 0.035, 0)], [0.072, 0.07, 0.064, 0.03], 10, M_TIMBER,
         post_col, tile=0.7, cap=True, col_fn=lambda t: scale(post_col, 0.62 + 0.38 * smoothstep(0.0, 0.3, t)))
    # Gable cap: two short boards meeting over the post head.
    ridge = top + V(0, 0.1, 0)
    for sx in (-1, 1):
        th = 0.62
        nrm = V(sx * math.sin(th), math.cos(th), 0)
        down = V(sx * math.cos(th), -math.sin(th), 0)
        board(g, ridge + down * 0.075 + nrm * 0.012, (0, 0, 1), nrm, 0.26, 0.15, 0.022, mat=M_PLANK,
              col=(0.7, 0.66, 0.6), rng=rng)
    beam(g, [ridge + V(0, 0.012, -0.14), ridge + V(0, 0.012, 0.14)], 0.035, 0.03, mat=M_PLANK, col=(0.6, 0.56, 0.5),
         rng=rng)
    # Arrow boards (local X along the heading, nailed flush to the post's side).
    for y, yaw, shade in ((1.62, 0.35, 1.0), (1.38, -2.2, 0.85)):
        q = quat_y(yaw)
        ldir, nrm = q @ V(1, 0, 0), q @ V(0, 0, 1)
        sag = rng.uniform(-0.03, 0.03)
        start = lean @ V(0, y, 0) + nrm * 0.083 - ldir * 0.1
        end = start + ldir * 0.72 + V(0, sag, 0)
        col = (0.98 * shade, 0.9 * shade, 0.76 * shade)
        beam(g, [start, end], 0.17, 0.034, up=nrm, mat=M_TIMBER, col=col, mode="plank", chamfer=0.1, point=0.13,
             rng=rng)
        for dy in (0.045, -0.045):
            box(g, tuple(start + ldir * 0.1 + nrm * 0.018 + V(0, dy, 0)), (0.018, 0.018, 0.01), q, M_IRON,
                (0.35, 0.32, 0.3), tile=0.3)
    # Packing stones round the foot.
    for k in range(5):
        a = k / 5 * 2 * math.pi + rng.uniform(-0.3, 0.3)
        r = rng.uniform(0.06, 0.09)
        stone(g, (math.cos(a) * 0.15, 0.0, math.sin(a) * 0.15), (r, r * 0.65, r * 0.85), rng, detail=1,
              col_fn=rock_col((0.95, 0.94, 0.9), moss=0.4), tile=0.5)
    return b


def wayside_cairn(rng):
    """Mile cairn: a dry-built cone of rough flat fieldstones in courses (each leaning in on the
    one below), topped by a marker stone set on end — ~0.7 tall, moss in the joints and on the
    upper faces, a few loose stones at the foot. Inside r 0.34 (collider 0.30 box)."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 3.0)
    courses = [(0.0, 0.18, 7, (0.24, 0.13, 0.17)), (0.115, 0.12, 6, (0.2, 0.11, 0.15)), (0.215, 0.075, 4, (0.17, 0.1, 0.13)),
               (0.305, 0.04, 3, (0.14, 0.09, 0.11)), (0.385, 0.0, 1, (0.17, 0.09, 0.15))]
    for ci, (y, ring, n, (sx, sy, sz)) in enumerate(courses):
        a0 = rng.uniform(0, 6.28)
        for k in range(n):
            a = a0 + k / n * 2 * math.pi + rng.uniform(-0.15, 0.15)
            p = (math.cos(a) * ring, y + sy * 0.45 + rng.uniform(-0.01, 0.015), math.sin(a) * ring)
            # Long axis roughly tangential, outer edge dipping (stones laid to shed water outward).
            rot = quat_y(-a + math.pi / 2 + rng.uniform(-0.4, 0.4)) @ quat_x(rng.uniform(-0.12, 0.12)) @ quat_z(rng.uniform(-0.1, 0.1))
            size = (sx * rng.uniform(0.8, 1.15), sy * rng.uniform(0.75, 1.1), sz * rng.uniform(0.8, 1.15))
            tint = scale((1.0, 0.98, 0.95), rng.uniform(0.7, 1.05))
            slab(g, p, size, rot, rng, res=(3, 2, 3), round_r=0.03, rough=0.09, cuts=2, taper=rng.uniform(0.0, 0.25),
                 col_fn=rock_col(tint, moss=0.5 if ci < 3 else 0.3, noise=nz, ground=0.0), tile=0.55)
    # The marker stone on end.
    slab(g, (0.01, 0.56, -0.01), (0.12, 0.26, 0.08), quat_y(rng.uniform(0, 6.28)) @ quat_z(0.06), rng, res=(2, 3, 2),
         round_r=0.025, rough=0.08, cuts=1, taper=0.35, col_fn=rock_col((0.92, 0.9, 0.86), moss=0.25, noise=nz),
         tile=0.5)
    # Loose stones at the foot.
    for k in range(4):
        a = rng.uniform(0, 6.28)
        r = rng.uniform(0.05, 0.07)
        stone(g, (math.cos(a) * 0.29, -0.01, math.sin(a) * 0.29), (r, r * 0.6, r * 0.85), rng, detail=1, cuts=2,
              col_fn=rock_col(scale((1.0, 0.98, 0.94), rng.uniform(0.75, 1.0)), moss=0.5, noise=nz), tile=0.5)
    return b


def wayside_fence(rng):
    """Post-and-rail run along local X: three split posts at x -1 / 0 / 1 (~0.7 tall), split rails
    at y 0.28 and 0.50 running through mortises (staggered at the middle post), pegged. Stays
    inside the 1.125 x 0.05 collider (rails |z| <= 0.04)."""
    b = Builder()
    g = G(b)
    grey = (0.9, 0.86, 0.78)
    for x in (-1.0, 0.0, 1.0):
        h = rng.uniform(0.66, 0.72)
        lean = V(rng.uniform(-0.02, 0.02), 0, rng.uniform(-0.02, 0.02))
        tint = scale(grey, rng.uniform(0.82, 1.05))
        beam(g, [V(x, -0.3, 0), V(x, h, 0) + lean], 0.12, 0.085, up=(0, 0, 1), mat=M_PLANK, chamfer=0.3, rough=0.08,
             jag=(0, 0.03), rng=rng, col_fn=weathered(tint, 0.7))
    for y in (0.28, 0.5):
        for (x0, x1, dz) in ((-1.12, 0.09, 0.012), (-0.08, 1.12, -0.012)):
            sag = -rng.uniform(0.005, 0.02)
            tint = scale((0.76, 0.72, 0.66), rng.uniform(0.82, 1.02))
            mid = (x0 + x1) / 2
            pts = [V(x0, y + rng.uniform(-0.01, 0.01), dz), V(mid, y + sag, dz + rng.uniform(-0.006, 0.006)),
                   V(x1, y + rng.uniform(-0.01, 0.01), dz)]
            if y == 0.28 and x0 > -0.5:
                # One rail is a round pole that kept its bark.
                tube(g, pts, [0.035, 0.037, 0.033], 7, M_BARK, (0.85, 0.8, 0.74), tile=0.8, uv_phase=rng.uniform(0, 3))
            else:
                beam(g, pts, 0.055, 0.08, mat=M_PLANK, chamfer=0.35, rough=0.2, rng=rng, col=tint)
    # Wooden pegs through each mortise.
    for x in (-1.0, 0.0, 1.0):
        for y in (0.28, 0.5):
            tube(g, [V(x + 0.02, y + 0.06, -0.06), V(x + 0.02, y + 0.06, 0.06)], [0.011, 0.011], 5, M_PLANK,
                 (0.7, 0.62, 0.52), tile=0.3)
    return b


def wayside_shrine(rng):
    """Roadside shrine facing +Z: rough stone footing, rubble-masonry pillar, a stone niche with a
    small carved figure and candle stubs, a shingled wooden roof with a little cross (to ~1.2).
    Inside r 0.43 (collider 0.26 box)."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 3.0)
    slab(g, (0, -0.06, 0), (0.56, 0.2, 0.54), quat_y(rng.uniform(-0.05, 0.05)), rng, res=(4, 2, 4), round_r=0.04,
         rough=0.05, col_fn=rock_col((0.95, 0.94, 0.9), moss=0.6, noise=nz), tile=0.6)
    lbox(g, (0, 0.24, 0), (0.38, 0.4, 0.38), quat_y(0.0), M_STONE, (0.95, 0.93, 0.88), tile=1.1, grain=1, v0=0.3)
    slab(g, (0, 0.475, 0), (0.46, 0.07, 0.44), quat_y(0.02), rng, res=(4, 1, 4), round_r=0.02, rough=0.03,
         col_fn=rock_col((0.92, 0.9, 0.86), moss=0.35, noise=nz), tile=0.6)
    # Niche: back + side walls, lintel.
    lbox(g, (0, 0.685, -0.135), (0.4, 0.35, 0.07), quat_y(0.0), M_STONE, (0.9, 0.88, 0.84), tile=1.1, grain=1)
    for sx in (-1, 1):
        lbox(g, (sx * 0.165, 0.685, 0.0), (0.07, 0.35, 0.34), quat_y(0.0), M_STONE, (0.92, 0.9, 0.86), tile=1.1, grain=1,
             u0=0.2 * sx)
    slab(g, (0, 0.895, 0.0), (0.44, 0.075, 0.38), quat_y(-0.02), rng, res=(4, 1, 4), round_r=0.02, rough=0.03,
         col_fn=rock_col((0.9, 0.88, 0.84), moss=0.2, noise=nz), tile=0.6)
    # Inner shadow (soot from candles) on the niche back.
    lbox(g, (0, 0.69, -0.098), (0.26, 0.3, 0.005), quat_y(0.0), M_STONE, (0.35, 0.33, 0.31), tile=1.1)
    # Carved figure: robed body + head, worn smooth.
    frustum(g, 0.055, 0.032, 0.51, 0.17, 9, M_ROCK, (1.25, 1.2, 1.1), tile=0.4, centre=(0, 0, -0.05), cap_top=True)
    stone(g, (0, 0.71, -0.05), (0.033, 0.038, 0.033), rng, detail=1, rough=0.05, cuts=0,
          col_fn=lambda p, n: (1.25, 1.2, 1.1), tile=0.3)
    # Candles: wax stubs + a small flame bead.
    for cx, cz, ch in ((0.085, 0.07, 0.07), (-0.09, 0.08, 0.045)):
        tube(g, [V(cx, 0.505, cz), V(cx, 0.51 + ch, cz)], [0.017, 0.015], 7, M_CLOTH, (1.5, 1.42, 1.2), tile=0.2)
        stone(g, (cx, 0.53 + ch, cz), (0.007, 0.018, 0.007), rng, mat=M_CLOTH, detail=1, rough=0.0, cuts=0,
              col_fn=lambda p, n: (3.0, 1.9, 0.6), tile=0.2)
    # Roof: three courses of shingle boards per side over two rafters, ridge board, small cross.
    ridge_y = 1.0
    th = 0.62
    for sx in (-1, 1):
        nrm = V(sx * math.sin(th), math.cos(th), 0)
        down = V(sx * math.cos(th), -math.sin(th), 0)
        for zr in (-0.2, 0.2):
            beam(g, [V(0, ridge_y - 0.04, zr), V(0, ridge_y - 0.04, zr) + down * 0.33], 0.04, 0.035, up=nrm,
                 mat=M_PLANK, col=(0.55, 0.5, 0.45), rng=rng)
        for k in range(3):
            f = 0.035 + k * 0.1
            c = V(0, ridge_y, 0) + down * (f + 0.06) + nrm * (0.012 + (2 - k) * 0.008)
            board(g, c, (0, 0, 1), nrm, 0.52 + rng.uniform(-0.01, 0.02), 0.13, 0.018, mat=M_PLANK,
                  col=scale((0.78, 0.72, 0.64), rng.uniform(0.85, 1.05)), rng=rng, chamfer=0.2)
    beam(g, [V(0, ridge_y + 0.03, -0.27), V(0, ridge_y + 0.03, 0.27)], 0.05, 0.035, mat=M_PLANK, col=(0.6, 0.55, 0.48),
         rng=rng)
    beam(g, [V(0, ridge_y + 0.04, 0.2), V(0, ridge_y + 0.22, 0.2)], 0.025, 0.025, up=(0, 0, 1), mat=M_PLANK,
         col=(0.6, 0.55, 0.48), rng=rng)
    beam(g, [V(-0.055, ridge_y + 0.165, 0.2), V(0.055, ridge_y + 0.165, 0.2)], 0.022, 0.022, mat=M_PLANK,
         col=(0.6, 0.55, 0.48), rng=rng)
    # Offering: a small clay pot with dry stems at the foot, front-right.
    frustum(g, 0.035, 0.048, -0.01, 0.075, 9, M_EARTH, (1.15, 0.62, 0.42), tile=0.3, centre=(0.17, 0, 0.27))
    for k in range(4):
        a = rng.uniform(0, 6.28)
        p0 = V(0.17, 0.05, 0.27)
        p1 = p0 + V(math.cos(a) * 0.05, 0.16 + rng.uniform(0, 0.05), math.sin(a) * 0.05)
        tube(g, [p0, p1], [0.004, 0.003], 3, M_CLOTH, (0.75, 0.65, 0.35), tile=0.2, cap=False)
        stone(g, tuple(p1), (0.012, 0.01, 0.012), rng, mat=M_CLOTH, detail=0, rough=0.0, cuts=0,
              col_fn=lambda p, n: (1.1, 0.75, 0.3), tile=0.2)
    return b


# ─────────────────────────────────────────────────────────────── story set-pieces
def poi_burned_cabin(rng):
    """Burned-out log cabin (inside the 1.3 x 1.1 collider box, r <= 1.9): an ash bed, charred sill
    logs and the stub of the back wall, broken corner posts (1.5 / 1.1 / 1.3 / 0.8 as before), the
    stone chimney left standing on the west wall, fallen rafters, an iron pot and the one unburnt
    crate at (0.9, 0.6)."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 5, 1.8)

    def ash(p, n):
        # s_earth is a warm dirt scan: the tints lean blue so the bed reads as grey ash and charcoal.
        k = 0.5 + 0.5 * nz(p * 2.5)
        c = mix((0.08, 0.085, 0.095), (0.34, 0.38, 0.43), k)
        edge = smoothstep(1.1, 1.6, math.hypot(p.x, p.z * 1.1))
        return mix(c, (0.36, 0.34, 0.32), edge * 0.8)
    mound(g, (0, 0.0, 0), 1.62, 1.42, 0.06, rng, col_fn=ash, tile=1.1, rings=7, seg=24, skirt=0.12, edge=0.08)

    def log(p0, p1, r, burnt=(False, False)):
        p0, p1 = Vector(p0), Vector(p1)
        pts = [p0, p0.lerp(p1, 0.15), p0.lerp(p1, 0.5) + Vector(rng.normal(size=3)) * 0.01, p0.lerp(p1, 0.85), p1]
        rad = [r * (0.6 if burnt[0] else 0.95), r * (0.9 if burnt[0] else 1.0), r, r * (0.9 if burnt[1] else 1.0),
               r * (0.55 if burnt[1] else 0.95)]
        c = charred(rng)
        tube(g, pts, rad, 8, M_BARK, c, tile=0.7, uv_phase=rng.uniform(0, 3),
             col_fn=lambda t, c=c: mix(c, scale(c, 1.6), 0.5 + 0.5 * math.sin(t * 9.0 + rng.uniform(0, 6))))

    R = 0.11
    # Sill course (back/front at y 0.11, sides at 0.22) and the surviving back-wall courses.
    log((-1.28, 0.1, -0.9), (1.27, 0.1, -0.9), R)
    log((-1.27, 0.1, 0.9), (-0.22, 0.09, 0.9), R, (False, True))
    log((0.42, 0.09, 0.9), (1.25, 0.1, 0.9), R, (True, False))
    log((-1.1, 0.21, -1.05), (-1.1, 0.21, 1.05), R)
    log((1.1, 0.2, -1.05), (1.1, 0.19, 0.45), R, (False, True))
    log((-1.25, 0.32, -0.9), (0.95, 0.31, -0.9), R, (False, True))
    log((-1.1, 0.43, -1.04), (-1.1, 0.42, -0.1), R, (False, True))
    log((-1.24, 0.53, -0.9), (0.3, 0.53, -0.89), R, (False, True))
    log((1.1, 0.41, -1.02), (1.1, 0.4, -0.45), R * 0.9, (False, True))
    log((-1.2, 0.74, -0.9), (-0.45, 0.73, -0.9), R * 0.95, (False, True))
    # Corner posts, charred square timbers with burnt tops.
    for x, z, h in ((-1.1, -0.9, 1.5), (1.1, -0.9, 1.1), (-1.1, 0.9, 0.8), (1.1, 0.9, 1.3)):
        lean = V(rng.uniform(-0.05, 0.05), 0, rng.uniform(-0.05, 0.05))
        beam(g, [V(x, -0.25, z), V(x, h, z) + lean], 0.17, 0.16, up=(0, 0, 1), mat=M_BARK, mode="bark", chamfer=0.25,
             rough=0.06, jag=(0, 0.22), rng=rng, col=charred(rng))
    # The stone chimney on the west wall: firebox + stack, broken off unevenly at the top.
    sc = (0.85, 0.83, 0.79)
    lbox(g, (-1.08, 0.42, 0.0), (0.48, 1.34, 0.76), quat_y(0.0), M_STONE,
         [scale(sc, 0.75), scale(sc, 0.75), scale(sc, 0.9), scale(sc, 0.9)], tile=1.2)
    lbox(g, (-1.11, 1.55, 0.0), (0.38, 0.95, 0.5), quat_y(0.0), M_STONE, [scale(sc, 0.6), scale(sc, 0.6), sc, sc],
         tile=1.2, v0=0.4)
    lbox(g, (-1.13, 2.12, -0.06), (0.34, 0.24, 0.32), quat_y(0.0), M_STONE, scale(sc, 0.55), tile=1.2, v0=0.1)
    for k in range(5):
        stone(g, (-1.1 + rng.uniform(-0.12, 0.1), 2.27 + rng.uniform(0, 0.04), rng.uniform(-0.2, 0.12)),
              (rng.uniform(0.06, 0.09), 0.05, rng.uniform(0.06, 0.08)), rng, detail=1,
              col_fn=rock_col((0.6, 0.58, 0.55), moss=0.0), tile=0.5)
    # Hearth mouth facing the room (+X), soot-black, with a lintel stone.
    lbox(g, (-0.835, 0.27, 0.0), (0.012, 0.42, 0.36), quat_y(0.0), M_STONE, (0.1, 0.09, 0.09), tile=1.2)
    slab(g, (-0.82, 0.52, 0.0), (0.12, 0.1, 0.5), quat_y(0.0), rng, res=(1, 1, 4), round_r=0.02, rough=0.03,
         col_fn=rock_col((0.55, 0.52, 0.5)), tile=0.5)
    # Fallen rafters and roof planks.
    for p0, p1 in (((-0.85, 0.07, 0.72), (0.18, 0.88, -0.86)), ((0.98, 0.09, 0.5), (-0.35, 0.64, -0.84)),
                   ((-0.55, 0.1, -0.2), (0.85, 0.11, 0.25))):
        beam(g, [V(*p0), V(*p1)], 0.12, 0.14, mat=M_BARK, mode="bark", chamfer=0.25, rough=0.06, jag=(0.15, 0.2),
             rng=rng, col=charred(rng))
    for k in range(7):
        a = rng.uniform(0, 6.28)
        c = V(rng.uniform(-0.6, 0.85), 0.04 + k * 0.012, rng.uniform(-0.55, 0.6))
        ldir = V(math.cos(a), rng.uniform(-0.05, 0.05), math.sin(a))
        board(g, c, ldir, V(0, 1, 0), rng.uniform(0.5, 1.0), 0.18, 0.03, mat=M_PLANK, mode="plank",
              col=charred(rng, (0.2, 0.17, 0.15)), rng=rng, jag=(0.08, 0.12))
    # Iron pot half sunk in the ash, its bail handle fallen to one side.
    frustum(g, 0.12, 0.15, -0.04, 0.2, 12, M_IRON, (0.35, 0.32, 0.3), tile=0.4, centre=(0.25, 0, 0.2))
    frustum(g, 0.15, 0.165, 0.15, 0.025, 12, M_IRON, (0.3, 0.28, 0.27), tile=0.4, centre=(0.25, 0, 0.2))
    tube(g, [V(0.25 + 0.15 * math.cos(a), 0.17 + 0.03 * math.sin(a * 2), 0.2 + 0.15 * math.sin(a))
             for a in np.linspace(0.3, 3.0, 9)], [0.008] * 9, 4, M_IRON, (0.3, 0.28, 0.27), tile=0.2)
    # The unburnt crate: board sides + corner battens, scorched on the side facing the fire.
    cpos = V(0.9, 0.2, 0.6)
    q = quat_y(0.35)
    lbox(g, cpos, (0.5, 0.4, 0.4), q, M_PLANK, [(0.32, 0.27, 0.22), None, (0.95, 0.84, 0.68)], tile=1.0, grain=0)
    for sx in (-1, 1):
        for sz in (-1, 1):
            beam(g, [cpos + q @ V(sx * 0.255, -0.2, sz * 0.205), cpos + q @ V(sx * 0.255, 0.205, sz * 0.205)], 0.05,
                 0.05, up=tuple(q @ V(0, 0, 1)), mat=M_PLANK, col=(0.7, 0.62, 0.5), rng=rng)
    # Stones fallen from the chimney top.
    for k in range(4):
        stone(g, (rng.uniform(-0.75, -0.5), 0.03, rng.uniform(-0.7, 0.7)), (rng.uniform(0.07, 0.11), 0.06, 0.08), rng,
              detail=1, col_fn=rock_col((0.7, 0.68, 0.64)), tile=0.5)
    return b


def poi_graves(rng):
    """Two wayside graves (r <= 1.4): settled earth mounds at x = -0.7 / +0.7 running along Z,
    a lashed wooden cross at (-0.7, -0.75) (collider 0.055) and a weathered headstone at
    (0.7, -0.8) (collider 0.27 x 0.09); fieldstones edging one grave, a few dry flowers."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 2.5)

    def earth(old, cx):
        def f(p, n):
            k = 0.5 + 0.5 * nz(p * 3.0)
            c = mix((0.2, 0.19, 0.18), (0.42, 0.38, 0.33), k)
            # The older (left) grave has grassed over: moss green over its crown.
            c = mix(c, (0.34, 0.42, 0.2), old * (0.55 + 0.45 * nz(p * 5.0)))
            # Feather the foot into the forest floor (sun-bleached litter / grass).
            f_edge = smoothstep(0.6, 1.0, math.hypot((p.x - cx) / 0.4, (p.z - 0.05) / 0.86))
            return mix(c, (0.55, 0.52, 0.34), f_edge * 0.75)
        return f
    for dx, old in ((-0.7, 1.0), (0.7, 0.0)):
        mound(g, (dx, 0.0, 0.05), 0.42, 0.88, 0.17 if old else 0.24, rng, col_fn=earth(old, dx), tile=0.7, rings=8,
              seg=28, skirt=0.1, edge=0.1, power=0.75, rough=0.38)
    # Fieldstones outlining the left grave.
    for k in range(14):
        a = k / 14 * 2 * math.pi
        x = -0.7 + math.cos(a) * 0.5
        z = 0.05 + math.sin(a) * 0.95
        if z < -0.65 and abs(x + 0.7) < 0.2:
            continue  # the cross stands there
        r = rng.uniform(0.06, 0.085)
        stone(g, (x, 0.0, z), (r, r * 0.6, r * 0.85), rng, detail=1,
              col_fn=rock_col(scale((1.0, 0.98, 0.94), rng.uniform(0.75, 1.0)), moss=0.6, noise=nz), tile=0.5)
    # The cross: two rough poles lashed together, leaning a little.
    lean = quat_x(0.05) @ quat_z(-0.04)
    base = V(-0.7, -0.25, -0.75)
    top = base + lean @ V(0, 1.18, 0)
    pole(g, base, top, 0.042, 0.034, rng, col=(0.75, 0.7, 0.62), sides=7, wobble=0.006)
    arm_c = base + lean @ V(0, 0.93, 0.035)
    pole(g, arm_c - lean @ V(0.27, 0, 0), arm_c + lean @ V(0.27, 0, 0), 0.03, 0.028, rng, col=(0.72, 0.66, 0.58),
         sides=6, wobble=0.004)
    lashing(g, arm_c, lean @ V(1, 1, 0), 0.05, rng)
    # Headstone: rough slab with a rounded crown, leaning back, mossy foot.
    slab(g, (0.7, 0.2, -0.8), (0.5, 0.86, 0.14), quat_y(0.06) @ quat_z(0.08) @ quat_x(-0.08), rng, res=(5, 8, 2),
         round_r=0.035, rough=0.03, crown=0.55, taper=0.08,
         col_fn=rock_col((0.95, 0.94, 0.9), moss=0.5, noise=nz, ground=0.0), tile=0.7)
    stone(g, (0.71, 0.66, -0.79), (0.04, 0.03, 0.035), rng, detail=1, col_fn=rock_col((0.9, 0.88, 0.85)), tile=0.3)
    # Dry flowers laid on the right mound.
    for k in range(5):
        p0 = V(0.62 + rng.uniform(-0.04, 0.04), 0.22, -0.2 + rng.uniform(-0.03, 0.03))
        p1 = p0 + V(rng.uniform(-0.08, 0.08), 0.02, rng.uniform(0.22, 0.3))
        tube(g, [p0, p1], [0.005, 0.004], 3, M_CLOTH, (0.6, 0.62, 0.3), tile=0.2, cap=False)
        stone(g, tuple(p1), (0.018, 0.012, 0.018), rng, mat=M_CLOTH, detail=0, rough=0.0, cuts=0,
              col_fn=lambda p, n: (1.2, 0.95, 0.5), tile=0.2)
    return b


def poi_stones(rng):
    """Standing-stone circle (r <= 3.25): six weathered megaliths on the r = 2.3 ring at the original
    angles / heights / tilts (each inside its 0.34 x 0.2 collider), the fifth toppled (0.31 x 0.81),
    a low altar stone in the middle."""
    b = Builder()
    g = G(b)
    for k in range(6):
        a = k * (2 * math.pi / 6)
        r = 2.3
        c = (math.cos(a) * r, 0, math.sin(a) * r)
        tint = scale((1.0, 0.99, 0.95), rng.uniform(0.8, 1.0))
        nzk = Noise(rng, 4, 2.0)
        if k == 4:
            rot = quat_y(a + 0.5) @ quat_z(rng.uniform(-0.05, 0.05))
            slab(g, (c[0], 0.12, c[2]), (0.54, 0.34, 1.5), rot, rng, res=(5, 3, 12), round_r=0.08, rough=0.04,
                 taper=0.0, cuts=1, col_fn=rock_col(tint, moss=0.7, noise=nzk, ground=0.0), tile=0.8)
            continue
        h = 1.2 + abs(math.sin(k * 2.1)) * 0.9
        rot = quat_y(a) @ quat_z(math.sin(k * 1.3) * 0.08)
        slab(g, (c[0], (h - 0.3) / 2, c[2]), (0.52, h + 0.3, 0.32), rot, rng, res=(6, 14, 4), round_r=0.07, rough=0.04,
             taper=0.22, crown=0.35, cuts=1, lean_top=(rng.uniform(-0.03, 0.03), rng.uniform(-0.02, 0.02)),
             col_fn=rock_col(tint, moss=0.55, noise=nzk, ground=0.0), tile=0.8)
        # Packing stones at the foot.
        for j in range(2):
            o = rot @ V(rng.uniform(-0.3, 0.3), 0, (1 if j else -1) * rng.uniform(0.22, 0.3))
            rr = rng.uniform(0.07, 0.1)
            stone(g, (c[0] + o.x, -0.01, c[2] + o.z), (rr, rr * 0.6, rr * 0.8), rng, detail=1,
                  col_fn=rock_col(tint, moss=0.5), tile=0.5)
    slab(g, (0.05, -0.02, -0.03), (0.95, 0.3, 0.72), quat_y(0.4), rng, res=(6, 2, 5), round_r=0.08, rough=0.05, cuts=1,
         col_fn=rock_col((0.92, 0.9, 0.86), moss=0.35), tile=0.8)
    return b


def poi_watchtower(rng):
    """Collapsed timber watchtower (in the (0.6, 0) 1.55 x 0.9 collider box, r <= 2.4): a four-post
    frame racked over toward -X, one post snapped (its top lying in the debris), girts and X-braces,
    the plank deck dropped onto its broken corner, a parapet panel fallen against the frame, a ladder
    leaning on the west side, loose planks."""
    b = Builder()
    g = G(b)
    tcol = (0.82, 0.76, 0.66)
    lean = quat_z(0.22) @ quat_x(0.035)
    L = 2.75
    bases = {"A": V(-0.05, -0.25, -0.68), "B": V(1.35, -0.25, -0.68), "C": V(-0.05, -0.25, 0.68), "D": V(1.35, -0.25, 0.68)}

    def along(p, s):
        return bases[p] + lean @ V(0, s, 0)

    for name in "ABC":
        beam(g, [bases[name], along(name, L)], 0.16, 0.16, up=(0, 0, 1), mat=M_PLANK, chamfer=0.15, rng=rng,
             col_fn=weathered(scale(tcol, rng.uniform(0.85, 1.05)), 0.7), jag=(0, 0.04))
    # D snapped ~0.6 up; its top lies in the debris.
    beam(g, [bases["D"], bases["D"] + V(-0.04, 0.88, 0.02)], 0.16, 0.16, up=(0, 0, 1), mat=M_PLANK, chamfer=0.15,
         jag=(0, 0.2), rng=rng, col_fn=weathered(tcol, 0.7))
    beam(g, [V(1.95, 0.08, -0.72), V(0.55, 0.1, 0.72)], 0.16, 0.16, mat=M_PLANK, chamfer=0.15, jag=(0.2, 0.03),
         rng=rng, col=scale(tcol, 0.9))
    # Girts at 1.3 up and X-braces on the -Z and -X faces.
    for p, q in (("A", "B"), ("A", "C")):
        beam(g, [along(p, 1.3) + V(0, 0, 0), along(q, 1.3)], 0.1, 0.12, mat=M_PLANK, chamfer=0.2, rng=rng,
             col=scale(tcol, 0.88))
        beam(g, [along(p, 0.35), along(q, 1.25)], 0.08, 0.1, mat=M_PLANK, chamfer=0.2, rng=rng, col=scale(tcol, 0.8))
        beam(g, [along(q, 0.35), along(p, 1.25)], 0.08, 0.1, mat=M_PLANK, chamfer=0.2, rng=rng, col=scale(tcol, 0.8))
    # Broken girts hanging off the snapped corner.
    beam(g, [along("C", 1.3), along("C", 1.3).lerp(V(0.7, 0.2, 0.78), 0.9)], 0.1, 0.12, mat=M_PLANK, chamfer=0.2,
         jag=(0, 0.15), rng=rng, col=scale(tcol, 0.85))
    beam(g, [along("B", 1.3), V(1.5, 0.08, 0.15)], 0.1, 0.12, mat=M_PLANK, chamfer=0.2, jag=(0, 0.15), rng=rng,
         col=scale(tcol, 0.85))
    # Deck: frame + planks, dropped onto the broken corner.
    tops = [along(n, L - 0.1) for n in "ABC"]
    centre = (tops[0] + tops[1] + tops[2]) / 3 + V(0.3, -0.5, 0.2)
    deck = quat_z(-0.42) @ quat_x(0.42) @ quat_y(0.05)
    for sx, sz, lx, lz in ((0, -0.85, 1.8, 0.0), (0, 0.85, 1.8, 0.0), (-0.85, 0, 0.0, 1.8), (0.85, 0, 0.0, 1.8)):
        c = centre + deck @ V(sx, -0.06, sz)
        d = deck @ V(lx / 2, 0, lz / 2)
        beam(g, [c - d, c + d], 0.12, 0.14, up=tuple(deck @ V(0, 1, 0)), mat=M_PLANK, chamfer=0.2, rng=rng,
             col=scale(tcol, 0.8))
    for k in range(9):
        x = -0.8 + k * 0.2
        if k in (5, 6):
            continue  # gone
        c = centre + deck @ V(x, 0.03, rng.uniform(-0.03, 0.03))
        if k == 8:
            # One plank hangs from the low corner.
            hinge = centre + deck @ V(x, 0.03, 0.75)
            board(g, hinge + V(0.05, -0.4, 0.15), V(0.1, -0.9, 0.35), deck @ V(1, 0, 0), 1.0, 0.18, 0.035, mat=M_PLANK,
                  col=scale(tcol, 0.75), rng=rng, jag=(0.0, 0.1))
            continue
        board(g, c, deck @ V(0, 0, 1), deck @ V(0, 1, 0), 1.85 + rng.uniform(-0.05, 0.03), 0.18, 0.035, mat=M_PLANK,
              col=scale(tcol, rng.uniform(0.7, 0.95)), rng=rng)
    # Parapet panel fallen against the frame on the east.
    pq = quat_z(0.95) @ quat_y(0.08)
    pc = V(1.6, 0.48, -0.32)
    for k in range(5):
        bc = pc + pq @ V(0, 0, -0.44 + k * 0.22)
        board(g, bc, pq @ V(0, 1, 0), pq @ V(1, 0, 0), 0.95, 0.19, 0.03, mat=M_PLANK,
              col=scale(tcol, rng.uniform(0.7, 0.9)), rng=rng, jag=(0, 0.06 if k == 2 else 0))
    for y in (-0.3, 0.3):
        c = pc + pq @ V(-0.035, y, 0)
        beam(g, [c + pq @ V(0, 0, -0.55), c + pq @ V(0, 0, 0.55)], 0.06, 0.08, up=tuple(pq @ V(1, 0, 0)), mat=M_PLANK,
             chamfer=0.2, rng=rng, col=scale(tcol, 0.75))
    # Ladder leaning on the west side.
    lb, lt = V(-0.9, -0.05, 0.2), V(-0.42, 1.55, 0.25)
    side = V(0, 0, 1)
    for s in (-0.19, 0.19):
        pole(g, lb + side * s, lt + side * s, 0.03, 0.026, rng, col=(0.85, 0.8, 0.72), sides=6)
    for k in range(6):
        f = 0.1 + k * 0.155
        p = lb.lerp(lt, f)
        pole(g, p - side * 0.21, p + side * 0.21, 0.018, 0.018, rng, col=(0.8, 0.74, 0.66), sides=5, wobble=0.002)
    # Loose planks on the ground.
    for k in range(3):
        a = rng.uniform(0, 6.28)
        c = V(rng.uniform(0.0, 1.9), 0.03 + k * 0.03, rng.uniform(-0.75, 0.75))
        board(g, c, V(math.cos(a), 0, math.sin(a)), V(0, 1, 0), rng.uniform(0.7, 1.1), 0.18, 0.03, mat=M_PLANK,
              col=scale(tcol, rng.uniform(0.65, 0.85)), rng=rng, jag=(0.05, 0.1))
    return b


def wattle(g, p0, p1, rng, h=0.6, stake_gap=0.27):
    """A woven hurdle panel from p0 to p1 (ground points): stakes + rods weaving between them."""
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    L = d.length
    t = d.normalized()
    perp = V(0, 1, 0).cross(t).normalized()
    n = max(2, round(L / stake_gap))
    stakes = [p0.lerp(p1, i / n) for i in range(n + 1)]
    for i, s in enumerate(stakes):
        pole(g, s + V(0, -0.2, 0), s + V(rng.uniform(-0.01, 0.01), h + rng.uniform(0.02, 0.07), 0), 0.022, 0.018, rng,
             col=(0.85, 0.78, 0.66), sides=5, wobble=0.004, segs=2)
    rods = 9
    for r in range(rods):
        y = 0.06 + r * (h - 0.08) / (rods - 1)
        pts = []
        for i, s in enumerate(stakes):
            off = 0.026 * (1 if (i + r) % 2 else -1)
            pts.append(s + perp * off + V(0, y + rng.uniform(-0.008, 0.008), 0))
            if i < n:
                pts.append(s.lerp(stakes[i + 1], 0.5) + V(0, y, 0))
        col = scale((1.1, 1.0, 0.82), rng.uniform(0.75, 1.0))
        tube(g, pts, [0.012] * len(pts), 4, M_BARK, col, tile=0.5, cap=False, uv_phase=rng.uniform(0, 3))


def poi_shepherd_hut(rng):
    """Shepherd's hut + pen (r <= 2.3). Drystone hut on x -1.8..-0.2, z -0.65..0.65 (collider
    0.83 x 0.7 at (-1, 0)), eaves at 1.0, thatched roof with its ridge along Z at ~1.52, plank door
    ajar on the +Z gable at x = -1. Pen to the east: wattle hurdles along z = -1 / +1 and x = 1.8
    (colliders 0.84 x 0.055 / 0.055 x 1.05), open toward the hut; trough + hay inside, a crook by
    the door."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 2.5)
    wc = (0.92, 0.9, 0.86)
    T = 0.16
    # Side (eave) walls.
    for x in (-1.8 + T / 2, -0.2 - T / 2):
        lbox(g, (x, 0.42, 0), (T, 1.16, 1.3), quat_y(0.0), M_STONE, [scale(wc, 0.75), scale(wc, 0.75), wc, wc], tile=1.3,
             grain=1, u0=x)
    # Gable walls (z = +-0.65): rectangles + triangle, door gap on the front.
    for z in (-0.65 + T / 2, 0.65 - T / 2):
        front = z > 0
        if front:
            for x0, x1 in ((-1.8, -1.22), (-0.78, -0.2)):
                lbox(g, ((x0 + x1) / 2, 0.42, z), (x1 - x0, 1.16, T), quat_y(0.0), M_STONE,
                     [scale(wc, 0.75), scale(wc, 0.75), wc, wc], tile=1.3, grain=1, u0=x0)
            lbox(g, (-1.0, 0.9, z), (0.44, 0.2, T), quat_y(0.0), M_STONE, wc, tile=1.3, grain=1, v0=0.3)
            beam(g, [V(-1.3, 0.79, z + 0.02), V(-0.7, 0.79, z + 0.02)], 0.12, 0.1, mat=M_PLANK, chamfer=0.2, rng=rng,
                 col=(0.6, 0.54, 0.46))
        else:
            lbox(g, (-1.0, 0.42, z), (1.6, 1.16, T), quat_y(0.0), M_STONE, [scale(wc, 0.75), scale(wc, 0.75), wc, wc],
                 tile=1.3, grain=1)
        # Gable triangle (prism), both faces + no top (the roof covers it).
        for zz, s in ((z + T / 2, 1), (z - T / 2, -1)):
            pts = [V(-1.8, 1.0, zz), V(-0.2, 1.0, zz), V(-1.0, 1.48, zz)]
            if s < 0:
                pts = pts[::-1]
            g.flat(pts, M_STONE, wc, 1.3)
    # Corner quoins.
    for x in (-1.8, -0.2):
        for z in (-0.65, 0.65):
            for k in range(4):
                along_x = k % 2 == 0
                sz = (0.3, 0.19, 0.2) if along_x else (0.2, 0.19, 0.3)
                cx = x + (0.12 if x < -1 else -0.12) * (1 if along_x else 0.5)
                cz = z + (0.1 if z < 0 else -0.1) * (0.5 if along_x else 1)
                slab(g, (cx, 0.1 + k * 0.23, cz), sz, quat_y(rng.uniform(-0.05, 0.05)), rng, res=(2, 2, 2),
                     round_r=0.03, rough=0.05, col_fn=rock_col(scale(wc, rng.uniform(0.6, 0.78)), moss=0.3, noise=nz),
                     tile=0.6)
    # Thatched roof: two thick coats with the straw running down-slope, rounded at the eaves and
    # the gable verges by bound rolls, a ridge roll pinned with hazel spars.
    th = 0.55
    for sx in (-1, 1):
        q = quat_z(-sx * th)
        c = V(-1.0 + sx * 0.44, 1.24, 0) + q @ V(0, 0.05, 0)
        lbox(g, c, (1.08, 0.24, 1.66), q, M_THATCH, (0.92, 0.86, 0.74), tile=0.8, grain=0)
        # Rolls end in rounded, tucked-in bundles rather than cut discs.
        eave = [c + q @ V(sx * 0.54, -0.01, z) for z in (-0.93, -0.88, -0.8, -0.3, 0.3, 0.8, 0.88, 0.93)]
        tube(g, eave, [0.03, 0.09, 0.125, 0.135, 0.135, 0.125, 0.09, 0.03], 10, M_THATCH, (0.8, 0.74, 0.62), tile=0.6,
             uv_phase=rng.uniform(0, 2))
        for z in (-0.83, 0.83):
            a, e = c + q @ V(-sx * 0.5, 0.0, z), c + q @ V(sx * 0.5, -0.01, z)
            tube(g, [a, a.lerp(e, 0.1), a.lerp(e, 0.9), e], [0.07, 0.11, 0.12, 0.08], 8, M_THATCH, (0.78, 0.72, 0.6),
                 tile=0.6)
    tube(g, [V(-1.0, 1.58, -0.96), V(-1.0, 1.6, -0.88), V(-1.0, 1.63, 0.0), V(-1.0, 1.6, 0.88), V(-1.0, 1.58, 0.96)],
         [0.04, 0.12, 0.14, 0.12, 0.04], 10, M_THATCH, (0.72, 0.66, 0.55), tile=0.6)
    for z in np.linspace(-0.7, 0.7, 6):
        for sx in (-1, 1):
            a = V(-1.0 + sx * 0.1, 1.68, z)
            tube(g, [a, a + V(sx * 0.17, -0.12, 0.0)], [0.012, 0.012], 4, M_BARK, (0.85, 0.78, 0.66), tile=0.3)
    # Door leaf, ajar, hinged on its west edge.
    hinge = V(-1.21, 0.0, 0.66)
    dq = quat_y(-0.55)
    for k in range(3):
        c = hinge + dq @ V(0.07 + k * 0.14, 0.38, 0.0)
        board(g, c, (0, 1, 0), dq @ V(0, 0, 1), 0.74, 0.135, 0.03, mat=M_PLANK, col=scale((0.85, 0.78, 0.68),
              rng.uniform(0.85, 1.0)), rng=rng)
    for y in (0.15, 0.6):
        c = hinge + dq @ V(0.21, y, 0.028)
        beam(g, [c - dq @ V(0.2, 0, 0), c + dq @ V(0.2, 0, 0)], 0.07, 0.025, up=tuple(dq @ V(0, 0, 1)), mat=M_PLANK,
             rng=rng, col=(0.6, 0.55, 0.48))
    # Threshold stone.
    slab(g, (-1.0, -0.03, 0.78), (0.6, 0.1, 0.26), quat_y(0.04), rng, res=(4, 1, 2), round_r=0.03, rough=0.05,
         col_fn=rock_col((0.85, 0.83, 0.8)), tile=0.6)
    # Shepherd's crook leaning by the door.
    cb = V(-0.6, -0.05, 0.74)
    ct = V(-0.45, 1.25, 0.69)
    pole(g, cb, ct, 0.017, 0.015, rng, col=(0.8, 0.7, 0.55), sides=6)
    hook = [ct, ct + V(0.03, 0.08, 0), ct + V(0.1, 0.11, 0), ct + V(0.16, 0.06, 0), ct + V(0.15, 0.0, 0)]
    tube(g, hook, [0.015] * len(hook), 6, M_BARK, (0.8, 0.7, 0.55), tile=0.5)
    # The pen: corner posts + three wattle hurdles.
    for x, z in ((0.2, -1.0), (1.8, -1.0), (0.2, 1.0), (1.8, 1.0)):
        pole(g, V(x, -0.25, z), V(x + rng.uniform(-0.01, 0.01), 0.74, z), 0.05, 0.044, rng, col=(0.85, 0.8, 0.72))
    wattle(g, V(0.26, 0, -1.0), V(1.74, 0, -1.0), rng)
    wattle(g, V(0.26, 0, 1.0), V(1.74, 0, 1.0), rng)
    wattle(g, V(1.8, 0, -0.94), V(1.8, 0, 0.94), rng)
    # Trough (plank box) and a hay heap inside.
    tq = quat_y(0.1)
    tc = V(1.15, 0.0, 0.42)
    for dz in (-0.12, 0.12):
        lbox(g, tc + tq @ V(0, 0.12, dz), (0.8, 0.22, 0.035), tq, M_PLANK, (0.72, 0.66, 0.56), tile=1.0, grain=0)
    for dx in (-0.4, 0.4):
        lbox(g, tc + tq @ V(dx, 0.12, 0), (0.035, 0.22, 0.27), tq, M_PLANK, (0.72, 0.66, 0.56), tile=1.0, grain=1)
    lbox(g, tc + tq @ V(0, 0.03, 0), (0.8, 0.03, 0.24), tq, M_PLANK, (0.5, 0.45, 0.38), tile=1.0, grain=0)
    lbox(g, tc + tq @ V(0, 0.16, 0), (0.76, 0.01, 0.2), tq, M_IRON, (0.08, 0.1, 0.1), tile=1.0)
    # A haycock (straw standing up the cone) by the back hurdle.
    frustum(g, 0.36, 0.3, -0.05, 0.32, 14, M_THATCH, (0.95, 0.9, 0.78), tile=0.7, centre=(1.3, 0, -0.52), segs=2,
            jitter=0.06, rng=rng)
    frustum(g, 0.3, 0.12, 0.27, 0.26, 14, M_THATCH, (1.0, 0.94, 0.82), tile=0.7, centre=(1.3, 0, -0.52), segs=2,
            jitter=0.06, rng=rng)
    frustum(g, 0.12, 0.01, 0.53, 0.08, 10, M_THATCH, (1.0, 0.94, 0.82), tile=0.5, centre=(1.3, 0, -0.52), cap_top=True)
    return b


def poi_gallows(rng):
    """Gallows on the fortress approach (collider 1.2 x 0.9, r <= 2.0): a plank platform 2.2 x 1.6
    with its top at 0.64 on posts and a frame, a trapdoor under the rope, the upright at x = -0.85
    to 3.25, the crossbeam at 3.12 with its knee brace, a noose hanging at x = 0.72."""
    b = Builder()
    g = G(b)
    tc = (0.62, 0.56, 0.48)
    for x in (-1.0, 1.0):
        for z in (-0.7, 0.7):
            beam(g, [V(x, -0.3, z), V(x, 0.56, z)], 0.16, 0.16, up=(0, 0, 1), mat=M_PLANK, chamfer=0.15, rng=rng,
                 col_fn=weathered(tc, 0.6))
    for z in (-0.7, 0.7):
        beam(g, [V(-1.1, 0.53, z), V(1.1, 0.53, z)], 0.12, 0.14, mat=M_PLANK, chamfer=0.15, rng=rng, col=scale(tc, 0.85))
    for x in (-1.0, 0.0, 1.0):
        beam(g, [V(x, 0.53, -0.78), V(x, 0.53, 0.78)], 0.12, 0.14, mat=M_PLANK, chamfer=0.15, rng=rng, col=scale(tc, 0.8))
    # X-braces under the deck on the long sides.
    for z in (-0.7, 0.7):
        beam(g, [V(-0.95, 0.0, z), V(0.95, 0.5, z)], 0.07, 0.09, mat=M_PLANK, chamfer=0.2, rng=rng, col=scale(tc, 0.75))
    # Deck planks along Z; the trapdoor pair (x 0.62 / 0.82) sits a touch low with iron hinges.
    for k in range(11):
        x = -1.0 + k * 0.2
        trap = k in (8, 9)
        y = 0.615 - (0.012 if trap else 0.0)
        board(g, V(x, y, rng.uniform(-0.01, 0.01)), (0, 0, 1), (0, 1, 0), 1.62 if not trap else 0.9, 0.19, 0.05,
              mat=M_PLANK, col=scale(tc, rng.uniform(0.8, 1.05)), rng=rng)
    for x in (0.65, 0.85):
        box(g, (x, 0.645, -0.32), (0.05, 0.012, 0.2), quat_y(0.0), M_IRON, IRON, tile=0.3)
    for z in (-0.47, 0.47):
        board(g, V(0.72, 0.615, z * 1.33 + (0.12 if z > 0 else -0.12)), (0, 0, 1), (0, 1, 0), 0.36, 0.38, 0.05,
              mat=M_PLANK, col=scale(tc, 0.9), rng=rng)
    # Upright, crossbeam, knee brace.
    beam(g, [V(-0.85, -0.3, 0), V(-0.85, 3.27, 0)], 0.2, 0.2, up=(0, 0, 1), mat=M_PLANK, chamfer=0.15, rng=rng,
         col_fn=weathered(tc, 0.7))
    beam(g, [V(-1.02, 3.12, 0), V(1.02, 3.12, 0)], 0.18, 0.16, mat=M_PLANK, chamfer=0.15, rng=rng, col=scale(tc, 0.9))
    beam(g, [V(-0.85, 2.5, 0), V(-0.3, 3.05, 0)], 0.1, 0.12, mat=M_PLANK, chamfer=0.2, rng=rng, col=scale(tc, 0.85))
    # Rope: wrapped round the beam, hanging to a noose.
    lashing(g, V(0.72, 3.12, 0), (1, 0, 0), 0.105, rng, turns=3)
    tube(g, [V(0.72, 3.03, 0), V(0.725, 2.85, 0.005), V(0.72, 2.68, 0)], [0.02, 0.02, 0.02], 6, M_CLOTH, ROPE, tile=0.3)
    for k in range(4):
        y = 2.66 - k * 0.028
        ring = [V(0.72 + 0.03 * math.cos(a), y, 0.03 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 9)]
        tube(g, ring, [0.016] * 9, 5, M_CLOTH, ROPE, tile=0.2, cap=False)
    loop = [V(0.72 + 0.11 * math.sin(a), 2.48 + 0.14 * math.cos(a), 0.0) for a in np.linspace(0, 2 * math.pi, 15)]
    tube(g, loop, [0.018] * 15, 6, M_CLOTH, ROPE, tile=0.3, cap=False)
    # A short ladder up the east side.
    lb, lt = V(1.42, -0.05, 0.25), V(1.14, 0.72, 0.25)
    for s in (-0.17, 0.17):
        pole(g, lb + V(0, 0, s), lt + V(0, 0, s), 0.028, 0.025, rng, col=(0.7, 0.64, 0.56), sides=6)
    for k in range(3):
        p = lb.lerp(lt, 0.2 + k * 0.3)
        pole(g, p - V(0, 0, 0.19), p + V(0, 0, 0.19), 0.017, 0.017, rng, col=(0.66, 0.6, 0.52), sides=5, wobble=0.002)
    return b


# ─────────────────────────────────────────────────────────────── vignette
def vignette_camp(rng):
    """The Abandoned Camp (r <= 1.6, collider 0.9 box): a cold fire ring at the origin with a cooking
    tripod and pot, a sagging canvas A-frame tent at x = 0.9 (ridge along Z at 0.8) with its guy
    ropes, a bedroll, the crate tipped at (-0.7, 0.4) spilling apples, a log seat with a hatchet and
    a dropped knapsack."""
    b = Builder()
    g = G(b)
    nz = Noise(rng, 4, 2.0)

    def ash(p, n):
        k = 0.5 + 0.5 * nz(p * 6.0)
        return mix((0.07, 0.075, 0.085), (0.36, 0.4, 0.45), k)
    mound(g, (0, 0, 0), 0.34, 0.34, 0.04, rng, col_fn=ash, tile=0.6, rings=4, seg=16, skirt=0.06)
    for k in range(8):
        a = k / 8 * 2 * math.pi + rng.uniform(-0.15, 0.15)
        r = rng.uniform(0.08, 0.11)
        stone(g, (math.cos(a) * 0.42, 0.0, math.sin(a) * 0.42), (r, r * 0.7, r * 0.85), rng, detail=1,
              col_fn=lambda p, n: mix((0.95, 0.93, 0.88), (0.3, 0.28, 0.26),
                                      smoothstep(0.5, 0.33, math.hypot(p.x, p.z))), tile=0.5)
    for k in range(3):
        a = k / 3 * math.pi + 0.4
        d = V(math.cos(a), 0, math.sin(a))
        c = charred(rng)
        tube(g, [d * -0.3 + V(0, 0.05, 0), V(0, 0.07 + k * 0.03, 0), d * 0.28 + V(0, 0.05, 0)], [0.03, 0.045, 0.025], 7,
             M_BARK, c, tile=0.5, uv_phase=rng.uniform(0, 3))
    # Cooking tripod + pot.
    apex = V(0.02, 1.0, 0.0)
    for a in (1.2, 3.3, 5.3):
        foot = V(math.cos(a) * 0.5, -0.1, math.sin(a) * 0.5)
        pole(g, foot, apex + (apex - foot).normalized() * 0.1, 0.022, 0.018, rng, col=(0.85, 0.8, 0.72), sides=6,
             wobble=0.006)
    lashing(g, apex, (0, 1, 0), 0.04, rng)
    tube(g, [apex, V(0.02, 0.62, 0.0)], [0.006, 0.006], 4, M_IRON, IRON, tile=0.2)
    frustum(g, 0.1, 0.12, 0.42, 0.16, 12, M_IRON, (0.4, 0.37, 0.35), tile=0.4, centre=(0.02, 0, 0))
    frustum(g, 0.12, 0.13, 0.565, 0.02, 12, M_IRON, (0.35, 0.33, 0.3), tile=0.4, centre=(0.02, 0, 0))
    tube(g, [V(0.02 + 0.125 * math.cos(a), 0.585 + 0.035 * math.sin(a), 0.0) for a in np.linspace(0.1, math.pi - 0.1, 7)],
         [0.006] * 7, 4, M_IRON, IRON, tile=0.2)
    # Tent: two end poles, ridge pole, sagging canvas slopes, guy ropes + stakes.
    tx = 0.9
    for z in (-0.6, 0.6):
        pole(g, V(tx, -0.15, z), V(tx, 0.84, z), 0.026, 0.022, rng, col=(0.85, 0.8, 0.72), sides=6, wobble=0.005)
    pole(g, V(tx, 0.81, -0.68), V(tx, 0.81, 0.68), 0.024, 0.024, rng, col=(0.85, 0.8, 0.72), sides=6, wobble=0.004)
    ni, nj = 10, 17
    for sx in (-1, 1):
        grid = []
        for i in range(ni):
            u = i / (ni - 1)
            row = []
            for j in range(nj):
                v = j / (nj - 1)
                z = (-1 + 2 * v) * 0.66
                x = tx + sx * (0.03 + u * 0.5)
                y = 0.83 - u * 0.85
                # Canvas drapes between the poles: deepest mid-span, plus soft diagonal folds
                # running from the ridge poles down to the pegs.
                sag = (0.1 if sx > 0 else 0.14) * math.sin(math.pi * u) * (0.35 + 0.65 * math.sin(math.pi * v))
                sag += 0.025 * math.sin(math.pi * u) * math.sin(v * 13.0 + u * 4.0 + sx)
                if sx < 0 and v < 0.35:
                    sag += 0.08 * math.sin(math.pi * u) * (0.35 - v) / 0.35  # a slipped peg
                x -= sx * sag * 0.5
                y -= sag
                if i == ni - 1:
                    y += abs(rng.normal()) * 0.02
                row.append((x, max(y, -0.01), z))
            grid.append(row)

        def col(u, v):
            k = 0.85 + 0.1 * math.sin(u * 7 + v * 11) + 0.05 * math.sin(v * 23)
            dirt = smoothstep(0.65, 1.0, u)
            return mix(scale((0.95, 0.88, 0.72), k), (0.5, 0.42, 0.32), dirt * 0.7)
        sheet(g, grid, M_CLOTH, col, tile=0.5, double=True)
    for z, s in ((-0.62, -1), (0.62, 1)):
        top = V(tx, 0.84, z)
        stake = V(tx + rng.uniform(-0.05, 0.05), 0.04, z + s * 0.38)
        tube(g, [top, top.lerp(stake, 0.5) - V(0, 0.03, 0), stake], [0.007] * 3, 4, M_CLOTH, ROPE, tile=0.3)
        pole(g, stake - V(0, 0.12, 0), stake + V(0, 0.1, s * 0.03), 0.02, 0.014, rng, col=(0.85, 0.8, 0.72), sides=5,
             segs=1)
    # Bedroll inside.
    tube(g, [V(tx - 0.12, 0.08, -0.45), V(tx - 0.1, 0.085, 0.0), V(tx - 0.13, 0.08, 0.38)], [0.085, 0.09, 0.085], 9,
         M_HIDE, (0.7, 0.55, 0.42), tile=0.4)
    # Tipped crate + its lid + spilled apples.
    cq = quat_y(0.5) @ quat_x(0.4)
    cc = V(-0.7, 0.16, 0.4)
    lbox(g, cc, (0.34, 0.34, 0.34), cq, M_PLANK, (0.92, 0.8, 0.62), tile=1.0, grain=0)
    for sx in (-1, 1):
        for sz in (-1, 1):
            beam(g, [cc + cq @ V(sx * 0.175, -0.17, sz * 0.175), cc + cq @ V(sx * 0.175, 0.175, sz * 0.175)], 0.04, 0.04,
                 up=tuple(cq @ V(0, 0, 1)), mat=M_PLANK, rng=rng, col=(0.65, 0.56, 0.44))
    lq = quat_y(1.1) @ quat_z(0.06)
    lbox(g, V(-1.0, 0.02, -0.12), (0.36, 0.025, 0.36), lq, M_PLANK, (0.9, 0.8, 0.64), tile=1.0, grain=0)
    for k in range(5):
        p = V(-0.48 + rng.uniform(-0.1, 0.25), 0.035, 0.55 + rng.uniform(-0.2, 0.15))
        p.y = 0.024
        stone(g, tuple(p), (0.027, 0.025, 0.027), rng, mat=M_FRUIT, detail=1, rough=0.05, cuts=0,
              col_fn=lambda q, n, k=k: mix((0.45, 0.06, 0.03), (0.5, 0.36, 0.06), 0.25 * (k % 3)), tile=0.2)
    # Log seat with a hatchet bitten into it.
    ls, le = V(-0.55, 0.12, -0.78), V(0.2, 0.13, -0.86)
    pole(g, ls, le, 0.13, 0.125, rng, col=(0.85, 0.8, 0.74), sides=9, wobble=0.008)
    hb = V(-0.12, 0.25, -0.82)
    tube(g, [hb, hb + V(0.14, 0.24, 0.05)], [0.014, 0.013], 6, M_PLANK, (0.8, 0.68, 0.52), tile=0.3)
    box(g, tuple(hb + V(0.0, 0.0, 0.0)), (0.12, 0.06, 0.018), quat_y(-0.35) @ quat_z(0.52), M_IRON, (0.45, 0.42, 0.4),
        tile=0.3)
    # A hessian sack slumped against the log end, its neck tied off.
    sq = quat_y(0.4) @ quat_z(-0.3)
    sc = V(0.38, 0.13, -0.72)
    stone(g, tuple(sc), (0.15, 0.15, 0.11), rng, mat=M_CLOTH, detail=2, rough=0.1, cuts=1, flat_y=0.75, rot=sq,
          col_fn=lambda p, n: mix((0.55, 0.47, 0.36), (0.8, 0.72, 0.56), smoothstep(0.0, 0.2, p.y)), tile=0.35)
    neck = sc + sq @ V(0, 0.13, 0)
    tube(g, [neck, neck + sq @ V(0, 0.07, 0), neck + sq @ V(0.03, 0.11, 0.0)], [0.045, 0.028, 0.04], 8, M_CLOTH,
         (0.72, 0.64, 0.5), tile=0.3)
    lashing(g, neck + sq @ V(0, 0.05, 0), sq @ V(0, 1, 0), 0.033, rng, turns=2)
    return b


MODELS = {
    "wayside_signpost": wayside_signpost,
    "wayside_cairn": wayside_cairn,
    "wayside_fence": wayside_fence,
    "wayside_shrine": wayside_shrine,
    "poi_burned_cabin": poi_burned_cabin,
    "poi_graves": poi_graves,
    "poi_stones": poi_stones,
    "poi_watchtower": poi_watchtower,
    "poi_shepherd_hut": poi_shepherd_hut,
    "poi_gallows": poi_gallows,
    "vignette_camp": vignette_camp,
}


def bounds(builder):
    """Extents in GAME coordinates (the Builder stores Blender (x, -z, y))."""
    v = np.array(builder.verts) if builder.verts else np.zeros((1, 3))
    gx, gy, gz = v[:, 0], v[:, 2], -v[:, 1]
    above = gy > 0.02  # what shows above ground (buried footings don't count toward the reach)
    r = np.hypot(gx[above], gz[above]).max() if above.any() else 0.0

    def rng_of(a):
        return [round(float(a.min()), 3), round(float(a.max()), 3)]
    return {"tris": builder.tris(), "radius": round(float(r), 3), "x": rng_of(gx), "z": rng_of(gz), "y": rng_of(gy)}


if __name__ == "__main__":  # importable: stories_cold.py reuses the primitives above
    clear_scene()
    objs = []
    report = {}
    for i, (name, fn) in enumerate(MODELS.items()):
        b = fn(np.random.default_rng(2000 + i))
        report[name] = bounds(b)
        objs.append(b.build(name, MATS))
    export_glb(OUT / "wayside.glb", objs)
    (OUT / "wayside_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    for k, v in report.items():
        print(f"{k}: {v}")
    print("WAYSIDE_DONE")
