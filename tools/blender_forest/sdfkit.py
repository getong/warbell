"""Signed-distance modelling for the animal kit (animals.py).

Metaballs (creatures.py) inflate wherever elements overlap, so tapered limbs grew balloon knots at
every joint. Here a body part is a list of exact SDF primitives (spheres, ellipsoids, tapered
capsules, rounded boxes) combined with smooth unions / subtractions, evaluated on a grid in the
joint's local frame and polygonised with surface nets, then decimated in Blender.

Everything is AUTHORED in one frame: the quadruped's rest-pose SPINE frame (game coords: Y up,
+Z forward, origin = body centre), so anatomy lines up across parts; each part only says which
joint frame its mesh is exported in. The same frame drives the baked per-vertex data:

  vertex colour  R = region / 16 + 1/32   (FUR, SKIN, DETAIL, EYE, ACCENT ... -> palette in game)
                 G = cavity / AO          (from the whole animal's SDF, so leg roots, armpits,
                                           eye sockets and toe gaps darken)
                 B = coat tone            (0 dark saddle / points .. 0.5 base .. 1 pale belly)
                 A = coat tint            (0..1 blend toward the species' warm tint colour)
  UV0            fur flow: u = arc length around the part's axis (+16 = "has fur flow" flag),
                 v = arc length along it, so the fur strand layer runs head -> tail, down the legs.
"""
import math

import numpy as np

EPS = 1e-9


def v3(a):
    return np.asarray(a, dtype=np.float64)


def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], dtype=np.float64)


def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], dtype=np.float64)


def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=np.float64)


def norm(a, axis=-1):
    return np.sqrt(np.maximum((a * a).sum(axis=axis), 0.0))


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


# ───────────────────────────────────────────────────────────────── primitives
class Prim:
    def bounds(self):
        raise NotImplementedError

    def d(self, p):
        raise NotImplementedError


class Sphere(Prim):
    def __init__(self, c, r):
        self.c, self.r = v3(c), float(r)

    def d(self, p):
        return norm(p - self.c) - self.r

    def bounds(self):
        return self.c - self.r, self.c + self.r


class Ellipsoid(Prim):
    """Approximate (iq) ellipsoid distance; `rot` maps local -> model."""

    def __init__(self, c, radii, rot=None):
        self.c, self.r = v3(c), v3(radii)
        self.R = np.eye(3) if rot is None else v3(rot)

    def d(self, p):
        q = (p - self.c) @ self.R
        k0 = norm(q / self.r)
        k1 = norm(q / (self.r * self.r))
        return k0 * (k0 - 1.0) / np.maximum(k1, EPS)

    def bounds(self):
        m = self.r.max()
        return self.c - m, self.c + m


class Cone(Prim):
    """Round cone (tapered capsule) from `a` (radius ra) to `b` (radius rb) — exact (iq)."""

    def __init__(self, a, b, ra, rb=None):
        self.a, self.b = v3(a), v3(b)
        self.ra = float(ra)
        self.rb = float(ra if rb is None else rb)

    def d(self, p):
        a, b, r1, r2 = self.a, self.b, self.ra, self.rb
        ba = b - a
        l2 = float(ba @ ba)
        if l2 < 1e-12:
            return norm(p - a) - max(r1, r2)
        rr = r1 - r2
        a2 = l2 - rr * rr
        il2 = 1.0 / l2
        pa = p - a
        y = pa @ ba
        z = y - l2
        x2 = ((pa * l2 - y[:, None] * ba) ** 2).sum(1)
        y2 = y * y * l2
        z2 = z * z * l2
        k = math.copysign(1.0, rr) * rr * rr * x2 if rr != 0 else np.zeros_like(x2)
        d_mid = (np.sqrt(np.maximum(x2 * a2 * il2, 0.0)) + y * rr) * il2 - r1
        d_b = np.sqrt(x2 + z2) * il2 - r2
        d_a = np.sqrt(x2 + y2) * il2 - r1
        out = np.where(np.sign(y) * a2 * y2 < k, d_a, d_mid)
        return np.where(np.sign(z) * a2 * z2 > k, d_b, out)

    def bounds(self):
        r = max(self.ra, self.rb)
        return np.minimum(self.a, self.b) - r, np.maximum(self.a, self.b) + r


class RBox(Prim):
    """Rounded box: half-extents `h`, corner radius `r`, `rot` local -> model."""

    def __init__(self, c, h, r=0.0, rot=None):
        self.c, self.h, self.r = v3(c), v3(h), float(r)
        self.R = np.eye(3) if rot is None else v3(rot)

    def d(self, p):
        q = np.abs((p - self.c) @ self.R) - (self.h - self.r)
        return norm(np.maximum(q, 0.0)) + np.minimum(q.max(1), 0.0) - self.r

    def bounds(self):
        m = norm(self.h)
        return self.c - m, self.c + m


class Squash(Prim):
    """Child primitive evaluated in a non-uniformly scaled frame (flattened ears, toe pads ...).
    The child is authored around the origin; `scale` squashes its local axes, `rot` then `c`
    place it. Distances are scaled by the smallest factor (a conservative bound)."""

    def __init__(self, child, c, scale, rot=None):
        self.child, self.c, self.s = child, v3(c), v3(scale)
        self.R = np.eye(3) if rot is None else v3(rot)

    def d(self, p):
        q = ((p - self.c) @ self.R) / self.s
        return self.child.d(q) * self.s.min()

    def bounds(self):
        lo, hi = self.child.bounds()
        corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
        w = (corners * self.s) @ self.R.T + self.c
        return w.min(0), w.max(0)


class Chain(Prim):
    """A tapered tube through a polyline of (point, radius) knots: a union of round cones, so the
    radius interpolates linearly with no bulge at the knots (unlike overlapping metaballs)."""

    def __init__(self, knots):
        self.cones = [Cone(knots[i][0], knots[i + 1][0], knots[i][1], knots[i + 1][1]) for i in range(len(knots) - 1)]

    def d(self, p):
        return np.min(np.stack([c.d(p) for c in self.cones]), axis=0)

    def bounds(self):
        b = [c.bounds() for c in self.cones]
        return np.min([x[0] for x in b], 0), np.max([x[1] for x in b], 0)


# ───────────────────────────────────────────────────────────────── fur tufts
class Tufts:
    """Directional clump noise for shaggy silhouettes: a sum of plane waves whose wave vectors lie
    mostly across `flow`, so bumps stretch along the fur. Returns ~0..1 (ridged toward clumps)."""

    def __init__(self, freq, flow=(0, 0, -1), seed=1, n=10, stretch=0.8):
        rng = np.random.default_rng(seed)
        f = v3(flow)
        f = f / max(np.linalg.norm(f), EPS)
        ks = []
        for _ in range(n):
            r = rng.normal(size=3)
            r -= f * (r @ f) * stretch
            ks.append(r / max(np.linalg.norm(r), EPS) * freq * rng.uniform(0.75, 1.3))
        self.k = np.array(ks)
        self.ph = rng.uniform(0, 2 * math.pi, n)

    def __call__(self, p):
        s = np.sin(p @ self.k.T + self.ph).sum(1) / math.sqrt(len(self.ph))
        # A smooth saturation (tanh, not a clip): clipped crests / troughs left flat plateaus with
        # creased rims that the decimated mesh turned into faceted clumps.
        return (0.5 + 0.5 * np.tanh(s * 1.1)) ** 1.6


# ───────────────────────────────────────────────────────────────── bodies
class Body:
    """One closed surface: SDF ops in the spine frame, meshed on a grid of spacing `h`."""

    def __init__(self, h=0.005, budget=1000):
        self.ops = []
        self.shags = []
        self.h = h
        self.budget = budget

    def add(self, prim, region=0, k=0.0):
        self.ops.append(("add", prim, region, k))
        return self

    def sub(self, prim, region=None, k=0.0):
        self.ops.append(("sub", prim, region, k))
        return self

    def cut(self, prim, k=0.0):
        """Intersect with `prim` (keep only what is inside it)."""
        self.ops.append(("int", prim, None, k))
        return self

    def shag(self, mask, amp, tufts, soft=0.03):
        """Displace the surface outward by `amp * tufts(p)` inside `mask` (soft edge `soft`)."""
        self.shags.append((mask, amp, tufts, soft))
        return self

    def bounds(self):
        los, his = zip(*[op[1].bounds() for op in self.ops if op[0] == "add"])
        pad = max([s[1] for s in self.shags], default=0.0) + 2 * self.h
        return np.min(los, 0) - pad, np.max(his, 0) + pad

    def eval(self, p, want_region=False):
        d = np.full(len(p), 1e9)
        reg = np.zeros(len(p), dtype=np.int32)
        for kind, prim, region, k in self.ops:
            di = prim.d(p)
            if kind == "add":
                if want_region:
                    reg = np.where(di < d, region, reg)
                if k > 0:
                    hh = np.clip(0.5 + 0.5 * (d - di) / k, 0.0, 1.0)
                    d = d * (1 - hh) + di * hh - k * hh * (1 - hh)
                else:
                    d = np.minimum(d, di)
            elif kind == "sub":
                if want_region and region is not None:
                    reg = np.where(-di > d - 1e-4, region, reg)
                if k > 0:
                    hh = np.clip(0.5 - 0.5 * (d + di) / k, 0.0, 1.0)
                    d = d * (1 - hh) - di * hh + k * hh * (1 - hh)
                else:
                    d = np.maximum(d, -di)
            else:  # intersect
                if k > 0:
                    hh = np.clip(0.5 - 0.5 * (di - d) / k, 0.0, 1.0)
                    d = di * (1 - hh) + d * hh + k * hh * (1 - hh)
                else:
                    d = np.maximum(d, di)
        for mask, amp, tufts, soft in self.shags:
            w = smoothstep(soft, -soft, mask.d(p))
            sel = w > 1e-3
            if sel.any():
                d[sel] -= amp * w[sel] * tufts(p[sel])
        return (d, reg) if want_region else d


def to_surface(body, pts, inset=0.0, iters=6):
    """Project points onto `body`'s surface as built so far (Newton steps along the gradient),
    then sink them `inset` along the inward normal — to lay a thin line (lips, seams) exactly on a
    blended surface instead of guessing where the smooth unions put it."""
    q = np.atleast_2d(v3(pts)).astype(np.float64).copy()
    for _ in range(iters):
        d = body.eval(q)
        g = gradient(body.eval, q)
        q -= (d / np.maximum((g * g).sum(1), 1e-9))[:, None] * g
    n = gradient(body.eval, q)
    return q - n / np.maximum(norm(n), 1e-9)[:, None] * inset


def resample(pts, n):
    """`n` points evenly spaced (by arc length) along the polyline `pts`."""
    pts = np.atleast_2d(v3(pts))
    seg = norm(pts[1:] - pts[:-1])
    s = np.concatenate([[0.0], np.cumsum(seg)])
    t = np.linspace(0.0, s[-1], n)
    return np.stack([np.interp(t, s, pts[:, i]) for i in range(3)], 1)


def eval_chunked(fn, p, chunk=300_000):
    if len(p) <= chunk:
        return fn(p)
    return np.concatenate([fn(p[i:i + chunk]) for i in range(0, len(p), chunk)])


def gradient(fn, p, e=5e-4):
    g = np.zeros_like(p)
    for i in range(3):
        o = np.zeros(3)
        o[i] = e
        g[:, i] = (fn(p + o) - fn(p - o)) / (2 * e)
    return g


# ───────────────────────────────────────────────────────────────── surface nets
_OFFS = np.array([(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0), (0, 0, 1), (1, 0, 1), (0, 1, 1), (1, 1, 1)])
_EDGES = [(0, 1), (2, 3), (4, 5), (6, 7), (0, 2), (1, 3), (4, 6), (5, 7), (0, 4), (1, 5), (2, 6), (3, 7)]


def surface_nets(F, origin, h):
    """Quad mesh of the zero level set of grid samples F (nx, ny, nz) at origin + h * ijk."""
    nx, ny, nz = F.shape
    cs = (nx - 1, ny - 1, nz - 1)
    corner = [F[o[0]:nx - 1 + o[0], o[1]:ny - 1 + o[1], o[2]:nz - 1 + o[2]] for o in _OFFS]
    acc = np.zeros(cs + (3,), np.float64)
    cnt = np.zeros(cs, np.int16)
    for a, b in _EDGES:
        fa, fb = corner[a], corner[b]
        m = (fa < 0) != (fb < 0)
        if not m.any():
            continue
        t = np.where(m, fa / np.where(m, fa - fb, 1.0), 0.0)
        pa, pb = _OFFS[a], _OFFS[b]
        acc += m[..., None] * (pa + t[..., None] * (pb - pa))
        cnt += m
    active = cnt > 0
    idx = -np.ones(cs, np.int64)
    n = int(active.sum())
    idx[active] = np.arange(n)
    ijk = np.argwhere(active)
    verts = (ijk + acc[active] / cnt[active][:, None]) * h + origin
    inside = F < 0
    quads = []
    for axis in range(3):
        sl_lo = [slice(None)] * 3
        sl_hi = [slice(None)] * 3
        sl_lo[axis] = slice(0, -1)
        sl_hi[axis] = slice(1, None)
        for ax2 in range(3):
            if ax2 != axis:
                sl_lo[ax2] = slice(1, -1)
                sl_hi[ax2] = slice(1, -1)
        lo = inside[tuple(sl_lo)]
        hi = inside[tuple(sl_hi)]
        m = lo != hi
        if not m.any():
            continue
        ii = list(np.nonzero(m))
        s_lo = lo[m]
        for ax2 in range(3):
            if ax2 != axis:
                ii[ax2] = ii[ax2] + 1
        u, w = [a for a in range(3) if a != axis]

        def cell(du, dw):
            c = [ii[0].copy(), ii[1].copy(), ii[2].copy()]
            c[u] -= du
            c[w] -= dw
            return idx[c[0], c[1], c[2]]

        q = np.stack([cell(1, 1), cell(0, 1), cell(0, 0), cell(1, 0)], 1)
        ok = (q >= 0).all(1)
        q, s_lo = q[ok], s_lo[ok]
        # Orient so the face normal points outward (+axis when the low end is inside).
        nrm = np.cross(verts[q[:, 2]] - verts[q[:, 0]], verts[q[:, 3]] - verts[q[:, 1]])
        want = np.where(s_lo, 1.0, -1.0)
        flip = np.sign(nrm[:, axis]) != want
        q[flip] = q[flip][:, ::-1]
        quads.append(q)
    quads = np.concatenate(quads) if quads else np.zeros((0, 4), np.int64)
    return verts, quads


def mesh_body(body, R, t):
    """Mesh `body` in the joint frame (R, t: local -> spine). Returns local verts + quads."""
    lo, hi = body.bounds()
    corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
    loc = (corners - t) @ R  # spine -> local (R orthonormal)
    llo, lhi = loc.min(0), loc.max(0)
    h = body.h
    n = np.ceil((lhi - llo) / h).astype(int) + 1
    gx, gy, gz = (llo[i] + h * np.arange(n[i]) for i in range(3))
    G = np.stack(np.meshgrid(gx, gy, gz, indexing="ij"), -1).reshape(-1, 3)
    fn = lambda q: body.eval(q @ R.T + t)  # noqa: E731
    F = eval_chunked(fn, G).reshape(n[0], n[1], n[2])
    verts, quads = surface_nets(F, llo, h)
    if len(verts):
        # One Newton step onto the true surface (surface nets averages edge crossings).
        d = eval_chunked(fn, verts)
        g = gradient(lambda q: eval_chunked(fn, q), verts)
        gg = np.maximum((g * g).sum(1), 1e-8)
        step = np.clip(d / gg, -h, h)[:, None] * g
        verts = verts - step
    return verts, quads


# ───────────────────────────────────────────────────────────────── per-vertex data
def ambient_occlusion(fn, p, n, step=0.012, k=1.6, taps=5):
    occ = np.zeros(len(p))
    for i in range(1, taps + 1):
        hh = step * i
        occ += (hh - fn(p + n * hh)) / hh * (0.5 ** i)
    return np.clip(1.0 - k * occ * 0.5, 0.0, 1.0)


def axis_uv(p, axis_pts, up=(0, 1, 0)):
    """Fur-flow coordinates around a polyline axis: v = arc length of the closest point (the
    flow runs from the first knot toward the last), u = distance around the axis measured from
    the `up` side, mirrored (|angle|) so there is no seam."""
    pts = [v3(a) for a in axis_pts]
    best = np.full(len(p), 1e9)
    vv = np.zeros(len(p))
    uu = np.zeros(len(p))
    s0 = 0.0
    upv = v3(up)
    for a, b in zip(pts[:-1], pts[1:]):
        ab = b - a
        L = float(np.linalg.norm(ab))
        T = ab / max(L, EPS)
        U = upv - T * (upv @ T)
        if np.linalg.norm(U) < 1e-4:
            U = np.array([0.0, 0.0, 1.0]) - T * T[2]
        U /= np.linalg.norm(U)
        X = np.cross(T, U)
        tt = np.clip((p - a) @ T, 0.0, L)
        c = a + tt[:, None] * T
        dv = p - c
        dist = norm(dv)
        sel = dist < best
        ang = np.abs(np.arctan2(dv @ X, dv @ U))
        best = np.where(sel, dist, best)
        vv = np.where(sel, s0 + tt, vv)
        uu = np.where(sel, ang * dist, uu)
        s0 += L
    return uu, vv
