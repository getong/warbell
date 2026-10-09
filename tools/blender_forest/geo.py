"""Small geometry helpers for hand-built structures (structures.py), authored in GAME coordinates
(Y up, the camp/mill door on +Z) and converted to Blender's Z-up on the way into the Builder, so
the glTF exporter's Y-up conversion lands them back exactly as written.

UVs are world-scaled (one texture repeat per `tile` units), so every structure shares tileable
PBR sets (planks / stone / hide / thatch / cloth / bark) at a consistent texel density.
"""
import math

import numpy as np
from mathutils import Quaternion, Vector


def bl(p):
    """Game (x, y, z) -> Blender (x, -z, y)."""
    return Vector((p[0], -p[2], p[1]))


def bn(n):
    return Vector((n[0], -n[2], n[1]))


def quat_y(a):
    return Quaternion((0, 1, 0), a)


def quat_x(a):
    return Quaternion((1, 0, 0), a)


def quat_z(a):
    return Quaternion((0, 0, 1), a)


class G:
    """Game-space wrapper over meshkit.Builder."""

    def __init__(self, builder):
        self.b = builder

    def poly(self, pts, uvs, nrms, cols, mat):
        idx = [self.b.v(bl(p)) for p in pts]
        self.b.face(idx, uvs, [tuple(bn(n)) for n in nrms], cols, mat)

    def flat(self, pts, mat, col, tile, rot_uv=0.0):
        """Planar polygon with a flat normal and a box-projected world UV."""
        pts = [Vector(p) for p in pts]
        n = (pts[1] - pts[0]).cross(pts[2] - pts[0])
        if n.length < 1e-9:
            return
        n.normalize()
        ax = max(range(3), key=lambda i: abs(n[i]))
        uvs = []
        for p in pts:
            if ax == 0:
                u, v = p.z, p.y
            elif ax == 1:
                u, v = p.x, p.z
            else:
                u, v = p.x, p.y
            if rot_uv:
                u, v = u * math.cos(rot_uv) - v * math.sin(rot_uv), u * math.sin(rot_uv) + v * math.cos(rot_uv)
            uvs.append((u / tile, v / tile))
        cols = col if isinstance(col, list) else [col] * len(pts)
        self.poly(pts, uvs, [n] * len(pts), cols, mat)


def box(g, centre, size, rot, mat, col, tile=1.0, grain_y=False):
    """Oriented box. `rot` is a mathutils Quaternion in game space. `grain_y` maps UV v along the
    box's local Y on the side faces (planks / posts keep their grain running lengthwise)."""
    c = Vector(centre)
    hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
    corners = [Vector((sx * hx, sy * hy, sz * hz)) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    w = [c + rot @ p for p in corners]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    for f in faces:
        pts = [w[i] for i in f]
        g.flat(pts, mat, col, tile)


def tube(g, pts, radii, sides, mat, col, tile=1.1, cap=True, uv_phase=0.0, col_fn=None):
    """Tapered tube along a polyline (bark / poles / rope), parallel-transport framed."""
    pts = [Vector(p) for p in pts]
    n_prev = None
    rings = []
    v_acc = uv_phase
    u_rep = max(1, round(2 * math.pi * max(radii) / tile * 1.6))
    for i, p in enumerate(pts):
        if i == 0:
            t = (pts[1] - pts[0]).normalized()
        elif i == len(pts) - 1:
            t = (pts[-1] - pts[-2]).normalized()
        else:
            t = (pts[i + 1] - pts[i - 1]).normalized()
        if n_prev is None:
            n = t.orthogonal().normalized()
        else:
            n = (n_prev - t * n_prev.dot(t)).normalized()
        n_prev = n
        b = t.cross(n)
        if i > 0:
            v_acc += (pts[i] - pts[i - 1]).length / tile
        ring = []
        for s in range(sides + 1):
            a = 2 * math.pi * (s % sides) / sides
            d = n * math.cos(a) + b * math.sin(a)
            ring.append((p + d * radii[i], d, (s / sides * u_rep, v_acc)))
        rings.append(ring)
    for i in range(len(rings) - 1):
        c0 = col_fn(i / max(len(rings) - 1, 1)) if col_fn else col
        c1 = col_fn((i + 1) / max(len(rings) - 1, 1)) if col_fn else col
        for s in range(sides):
            a, b2 = rings[i][s], rings[i][s + 1]
            c, d = rings[i + 1][s + 1], rings[i + 1][s]
            g.poly([a[0], b2[0], c[0], d[0]], [a[2], b2[2], c[2], d[2]], [a[1], b2[1], c[1], d[1]],
                   [c0, c0, c1, c1], mat)
    if cap:
        for end, sign in ((0, -1), (len(rings) - 1, 1)):
            ring = rings[end]
            centre = pts[end]
            t = (pts[1] - pts[0]).normalized() if end == 0 else (pts[-1] - pts[-2]).normalized()
            nn = t * sign
            for s in range(sides):
                a, b2 = ring[s], ring[s + 1]
                tri = [a[0], b2[0], centre] if sign > 0 else [b2[0], a[0], centre]
                uv = [(0.5 + 0.4 * math.cos(2 * math.pi * k / sides), 0.5 + 0.4 * math.sin(2 * math.pi * k / sides))
                      for k in ((s, s + 1) if sign > 0 else (s + 1, s))] + [(0.5, 0.5)]
                c = col_fn(1.0 if end else 0.0) if col_fn else col
                g.poly(tri, uv, [nn] * 3, [c] * 3, mat)


def frustum(g, r_bot, r_top, y0, h, sides, mat, col, tile=1.0, centre=(0, 0, 0), jitter=0.0, rng=None,
            col_fn=None, segs=1, cap_top=False):
    """Faceted tapered drum with its UV v running up the height (planks stand vertical)."""
    cx, cz = centre[0], centre[2]
    rings = []
    for k in range(segs + 1):
        f = k / segs
        r = r_bot + (r_top - r_bot) * f
        y = y0 + h * f
        ring = []
        for s in range(sides + 1):
            a = 2 * math.pi * (s % sides) / sides
            rr = r * (1 + (rng.uniform(-jitter, jitter) if (rng is not None and jitter and s < sides) else 0))
            ring.append(Vector((cx + math.cos(a) * rr, y, cz + math.sin(a) * rr)))
        ring[-1] = ring[0]
        rings.append(ring)
    circ = 2 * math.pi * max(r_bot, r_top)
    for k in range(segs):
        c0 = col_fn(k / segs) if col_fn else col
        c1 = col_fn((k + 1) / segs) if col_fn else col
        for s in range(sides):
            p = [rings[k][s], rings[k][s + 1], rings[k + 1][s + 1], rings[k + 1][s]]
            n = (p[1] - p[0]).cross(p[3] - p[0])
            if n.length < 1e-9:
                continue
            u0 = s / sides * circ / tile
            u1 = (s + 1) / sides * circ / tile
            v0 = (p[0].y) / tile
            v1 = (p[3].y) / tile
            uv = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
            cs = [c0, c0, c1, c1]
            n = n.normalized()
            if n.dot(Vector((p[0].x - cx, 0, p[0].z - cz))) < 0:
                # Face outward: flip the winding (not just the normal) or it gets back-face culled.
                p, uv, cs, n = p[::-1], uv[::-1], cs[::-1], -n
            g.poly(p, uv, [n] * 4, cs, mat)
    if cap_top:
        top = rings[-1]
        cpt = Vector((cx, y0 + h, cz))
        for s in range(sides):
            tri = [top[s], top[s + 1], cpt]
            if (tri[1] - tri[0]).cross(tri[2] - tri[0]).y < 0:
                tri = tri[::-1]
            g.poly(tri, [(0, 0), (1, 0), (0.5, 1)], [Vector((0, 1, 0))] * 3,
                   [col_fn(1.0) if col_fn else col] * 3, mat)


def rock(g, centre, radius, squash, rng, mat, col, tile=0.8, detail=2):
    """Displaced icosphere boulder, flat-ish shaded, box UVs."""
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
    phase = rng.uniform(0, 100, 3)
    out = []
    for v in verts:
        d = 1 + 0.22 * math.sin(v.x * 3.1 + phase[0]) * math.sin(v.y * 2.7 + phase[1]) + 0.12 * math.sin(v.z * 5.3 + phase[2])
        p = Vector((v.x * d * radius[0], max(v.y * d * radius[1] * squash, -0.15 * radius[1]), v.z * d * radius[2]))
        out.append(Vector(centre) + p)
    for a, b, c in faces:
        pts = [out[a], out[b], out[c]]
        g.flat(pts, mat, col, tile)


def sheet(g, grid, mat, col_fn, tile=1.0, double=False):
    """A cloth/hide sheet from a 2D grid of game-space points [i][j]; smooth normals, UV from the
    grid's arc length so the weave doesn't stretch over a sag."""
    ni, nj = len(grid), len(grid[0])
    P = [[Vector(p) for p in row] for row in grid]
    U = np.zeros((ni, nj))
    V = np.zeros((ni, nj))
    for i in range(ni):
        for j in range(1, nj):
            V[i][j] = V[i][j - 1] + (P[i][j] - P[i][j - 1]).length
    for j in range(nj):
        for i in range(1, ni):
            U[i][j] = U[i - 1][j] + (P[i][j] - P[i - 1][j]).length
    N = [[None] * nj for _ in range(ni)]
    for i in range(ni):
        for j in range(nj):
            du = P[min(i + 1, ni - 1)][j] - P[max(i - 1, 0)][j]
            dv = P[i][min(j + 1, nj - 1)] - P[i][max(j - 1, 0)]
            n = du.cross(dv)
            N[i][j] = n.normalized() if n.length > 1e-9 else Vector((0, 1, 0))
    for i in range(ni - 1):
        for j in range(nj - 1):
            q = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]
            pts = [P[a][b] for a, b in q]
            uvs = [(U[a][b] / tile, V[a][b] / tile) for a, b in q]
            ns = [N[a][b] for a, b in q]
            cs = [col_fn(a / (ni - 1), b / (nj - 1)) for a, b in q]
            g.poly(pts, uvs, ns, cs, mat)
            if double:
                g.poly(pts[::-1], uvs[::-1], [-n for n in ns[::-1]], cs[::-1], mat)
