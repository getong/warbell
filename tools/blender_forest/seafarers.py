"""Background seafarers + distant isles (CONCEPT / preview stage - not wired into the game yet).

Builds low-poly, vertex-coloured decoration models that live OUTSIDE the playable map:
  ships : ork war galley "Tuskhull", ork raider longboat, the mysterious "Pale Lantern"
  isles : Pine Crag (cliffs, pines, a ruined watchtower whose beacon still burns),
          Bone Atoll (dune island with a colossal half-buried skeleton),
          Ash Peak (black volcanic ork isle with a glowing crater + stake palisade)
and renders Eevee preview shots of each plus a hazy seascape composition.

    blender -b --factory-startup --python tools/blender_forest/seafarers.py -- <out_dir> [shot,shot]

Axes: Blender Z-up, ships bow +X, waterline at Z=0. Game units (hero ~1.3u).
"""
import math
import random
import sys
import time
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector, noise

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUTDIR = Path(argv[0]).resolve() if argv else Path(__file__).resolve().parents[2] / "shots" / "seafarers"
ONLY = set(argv[1].split(",")) if len(argv) > 1 and argv[1] else None
OUTDIR.mkdir(parents=True, exist_ok=True)
T0 = time.time()

bpy.ops.wm.read_factory_settings(use_empty=True)
SCENE = bpy.context.scene


# ── colour helpers ─────────────────────────────────────────────────────────────
def hexc(h):
    def lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return (lin(((h >> 16) & 255) / 255), lin(((h >> 8) & 255) / 255), lin((h & 255) / 255), 0.0)


def glowc(h, g=1.0):
    """Colour whose alpha (= emission mask on the solid material) is `g`."""
    c = hexc(h)
    return (c[0], c[1], c[2], g)


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(a[i] * (1 - t) + b[i] * t for i in range(4))


def jit(c, rng, amt=0.12):
    k = 1.0 + rng.uniform(-amt, amt)
    return (c[0] * k, c[1] * k, c[2] * k, c[3])


def smooth(e0, e1, x):
    if e0 == e1:
        return 1.0 if x >= e1 else 0.0
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def n2(x, y, s=0.0):
    return noise.noise(Vector((x, y, s)))


def fbm(x, y, s=0.0, oct=4):
    a, f, tot, nrm = 0.5, 1.0, 0.0, 0.0
    for o in range(oct):
        tot += a * noise.noise(Vector((x * f, y * f, s + o * 7.31)))
        nrm += a
        a *= 0.5
        f *= 2.03
    return tot / nrm


# ── materials ──────────────────────────────────────────────────────────────────
def mat_vc(name, rough=0.85, emit=0.0, sheen=0.0, alpha_glow=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    a = nt.nodes.new("ShaderNodeVertexColor")
    a.layer_name = "Col"
    nt.links.new(a.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rough
    if emit:
        nt.links.new(a.outputs["Color"], b.inputs["Emission Color"])
        b.inputs["Emission Strength"].default_value = emit
    elif alpha_glow:
        mul = nt.nodes.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        mul.inputs[1].default_value = alpha_glow
        nt.links.new(a.outputs["Alpha"], mul.inputs[0])
        nt.links.new(a.outputs["Color"], b.inputs["Emission Color"])
        nt.links.new(mul.outputs[0], b.inputs["Emission Strength"])
    if sheen:
        b.inputs["Sheen Weight"].default_value = sheen
    return m


def get_mats():
    names = ["vc_solid", "vc_glow", "vc_cloth", "vc_metal"]
    mats = [bpy.data.materials.get(n) for n in names]
    if any(m is None for m in mats):
        m_solid = mat_vc("vc_solid", 0.82, alpha_glow=3.5)
        m_glow = mat_vc("vc_glow", 0.5, emit=4.0)
        m_cloth = mat_vc("vc_cloth", 0.95, sheen=0.4)
        m_metal = mat_vc("vc_metal", 0.68)
        try:
            m_cloth.node_tree.nodes["Principled BSDF"].inputs["Subsurface Weight"].default_value = 0.0
        except KeyError:
            pass
        return [m_solid, m_glow, m_cloth, m_metal]
    return mats


SOLID, GLOW, CLOTH, METAL = 0, 1, 2, 3


# ── mesh builder ───────────────────────────────────────────────────────────────
class B:
    def __init__(self):
        self.v, self.f, self.c, self.m = [], [], [], []

    def poly(self, pts, col, mat=SOLID):
        base = len(self.v)
        self.v.extend(tuple(p) for p in pts)
        self.f.append(tuple(range(base, base + len(pts))))
        self.c.append(col if isinstance(col, list) else [col] * len(pts))
        self.m.append(mat)

    def tris(self):
        return sum(len(f) - 2 for f in self.f)

    def build(self, name, sharp_deg=38.0):
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.v, [], self.f)
        for m in get_mats():
            me.materials.append(m)
        attr = me.color_attributes.new("Col", "FLOAT_COLOR", "CORNER")
        attr.data.foreach_set("color", [x for cols in self.c for col in cols for x in col])
        me.polygons.foreach_set("material_index", self.m)
        me.update()
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
        me.shade_smooth()
        me.set_sharp_from_angle(angle=math.radians(sharp_deg))
        ob = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(ob)
        print(f"[seafarers] {name}: {len(me.polygons)} faces, "
              f"{sum(len(p.vertices) - 2 for p in me.polygons)} tris")
        return ob


def frame_of(ax):
    ax = ax.normalized()
    up = Vector((0, 0, 1)) if abs(ax.z) < 0.9 else Vector((1, 0, 0))
    u = ax.cross(up).normalized()
    return u, ax.cross(u)


def tube(b, pts, radii, n, col, mat=SOLID, cap=True):
    """Generalised cylinder along a polyline (parallel-transport-ish frames)."""
    pts = [Vector(p) for p in pts]
    rings = []
    for i, p in enumerate(pts):
        d = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)])
        u, w = frame_of(d)
        r = radii[i] if isinstance(radii, (list, tuple)) else radii
        rings.append([p + (u * math.cos(a) + w * math.sin(a)) * r
                      for a in (k * math.tau / n for k in range(n))])
    for i in range(len(rings) - 1):
        ci = col(i) if callable(col) else col
        for k in range(n):
            j = (k + 1) % n
            b.poly([rings[i][k], rings[i][j], rings[i + 1][j], rings[i + 1][k]], ci, mat)
    if cap:
        b.poly(list(reversed(rings[0])), col(0) if callable(col) else col, mat)
        b.poly(rings[-1], col(len(rings) - 2) if callable(col) else col, mat)


def cyl(b, p0, p1, r0, r1, n, col, mat=SOLID, cap=True):
    p0, p1 = Vector(p0), Vector(p1)
    u, w = frame_of(p1 - p0)
    ring = lambda c, r: [c + (u * math.cos(a) + w * math.sin(a)) * r
                         for a in (k * math.tau / n for k in range(n))]
    a, z = ring(p0, r0), ring(p1, r1)
    for k in range(n):
        j = (k + 1) % n
        if r1 > 1e-5:
            b.poly([a[k], a[j], z[j], z[k]], col, mat)
        else:
            b.poly([a[k], a[j], p1], col, mat)
    if cap:
        b.poly(list(reversed(a)), col, mat)
        if r1 > 1e-5:
            b.poly(z, col, mat)


def box(b, c, hs, col, rot=None, mat=SOLID):
    c = Vector(c)
    R = rot or Matrix.Identity(3)
    corners = [c + R @ Vector((sx * hs[0], sy * hs[1], sz * hs[2]))
               for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    for f in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
        b.poly([corners[i] for i in f], col, mat)


def sphere(b, c, rad, nu, nv, col, mat=SOLID, rot=None):
    c = Vector(c)
    R = rot or Matrix.Identity(3)
    P = lambda i, j: c + R @ Vector((
        rad[0] * math.sin(math.pi * j / nv) * math.cos(math.tau * i / nu),
        rad[1] * math.sin(math.pi * j / nv) * math.sin(math.tau * i / nu),
        rad[2] * math.cos(math.pi * j / nv)))
    for j in range(nv):
        for i in range(nu):
            q = [P(i, j), P(i, j + 1), P(i + 1, j + 1), P(i + 1, j)]
            cc = col(i, j) if callable(col) else col
            if j == 0:
                b.poly([q[0], q[1], q[2]], cc, mat)
            elif j == nv - 1:
                b.poly([q[0], q[1], q[3]], cc, mat)
            else:
                b.poly(q, cc, mat)


def rotz(a):
    return Matrix.Rotation(a, 3, "Z")


# ── shared ship parts ──────────────────────────────────────────────────────────
def hull(b, L, beam, depth, rail, bow_rise, stern_rise, pal, rng, n=20, flare=0.08):
    """Lofted clinker hull. Returns (stations, top_z(t), half_width(t), deck_z)."""
    rows = 8
    grid = []
    for i in range(n + 1):
        t = i / n
        x = -L / 2 + t * L
        wf = math.sin(math.pi * t) ** 0.55
        w = beam * wf
        sb, ss = smooth(0.70, 1.0, t), smooth(0.30, 0.0, t)
        top = rail + bow_rise * sb ** 2.2 + stern_rise * ss ** 2.2
        keel = -depth * min(1.0, 0.25 + wf * 1.2)
        prof = [(0.0, keel), (0.55 * w, 0.78 * keel), (0.9 * w, 0.32 * keel), (w, 0.0)]
        for r in range(1, rows + 1):
            f = r / rows
            prof.append((w * (1 + flare * math.sin(math.pi * f * 0.9)) - 0.02 * r * (1 - wf), top * f))
        grid.append([(x, y, z) for y, z in prof])
    deck_z = rail * 0.55
    plank = [pal["plank_a"], pal["plank_b"]]
    for side in (1, -1):
        for i in range(n):
            for j in range(len(grid[0]) - 1):
                q = [grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]]
                q = [(p[0], p[1] * side, p[2]) for p in q]
                if j < 3:
                    col = pal["bottom"]
                elif j == 3:
                    col = pal["tar"]
                elif j == len(grid[0]) - 2:
                    col = pal["band"]
                else:
                    col = plank[(j + (i // 7)) % 2]
                b.poly(q, jit(col, rng, 0.10), SOLID)
    # inner face of the topsides (so the bulwarks read as planks from above, not a void)
    for side in (1, -1):
        for i in range(n):
            a0, a1 = grid[i][-1], grid[i + 1][-1]
            b0 = (a0[0], a0[1] * 0.9, deck_z)
            b1 = (a1[0], a1[1] * 0.9, deck_z)
            if a0[2] < deck_z + 0.01 and a1[2] < deck_z + 0.01:
                continue
            q = [(a0[0], a0[1] * side * 0.97, a0[2]), (a1[0], a1[1] * side * 0.97, a1[2]),
                 (b1[0], b1[1] * side, b1[2]), (b0[0], b0[1] * side, b0[2])]
            b.poly(q, jit(pal["inner"], rng, 0.08), SOLID)
    # deck planking (stripes run fore-aft)
    for i in range(n):
        w0 = grid[i][4][1] * 0.92
        w1 = grid[i + 1][4][1] * 0.92
        x0, x1 = grid[i][0][0], grid[i + 1][0][0]
        for k in range(4):
            f0, f1 = -1 + k * 0.5, -1 + (k + 1) * 0.5
            b.poly([(x0, w0 * f0, deck_z), (x1, w1 * f0, deck_z), (x1, w1 * f1, deck_z),
                    (x0, w0 * f1, deck_z)], jit(pal["deck"], rng, 0.12), SOLID)

    def top_z(t):
        sb, ss = smooth(0.70, 1.0, t), smooth(0.30, 0.0, t)
        return rail + bow_rise * sb ** 2.2 + stern_rise * ss ** 2.2

    def half_w(t):
        return beam * math.sin(math.pi * min(max(t, 0.0), 1.0)) ** 0.55 * (1 + flare * 0.5)

    return top_z, half_w, deck_z


def sail(b, top_c, width, height, billow, nx, ny, colfn, taper=0.0, rng=None, ragged=0.0, yaw=0.0,
         decals=()):
    """Square/lug sail hanging from a yard centred at top_c. Faces with colfn -> None are holes.
    `decals` = [(quads, colour)], quads in sail metres (X across from centre, Y down from yard);
    they're painted onto both faces of the billowed cloth. Returns the surface fn S(u, v, off)."""
    top_c = Vector(top_c)
    R = rotz(yaw)
    rng = rng or random.Random(1)
    tear = [rng.uniform(0, ragged) for _ in range(nx + 1)]

    def S(u, v, off=0.0):
        hw = width * (0.5 + taper * v * 0.5)
        y = (u - 0.5) * 2 * hw
        z = -v * height
        x = billow * math.sin(math.pi * u) * math.sin(math.pi * min(v * 0.95 + 0.05, 1.0)) ** 0.8 + off
        return top_c + R @ Vector((x, y, z))

    def P(i, j):
        p = S(i / nx, j / ny)
        if j == ny:
            p = p + R @ Vector((0, 0, height * tear[i]))
        return p

    for j in range(ny):
        for i in range(nx):
            cc = colfn((i + 0.5) / nx, (j + 0.5) / ny)
            if cc is None:
                continue
            b.poly([P(i, j), P(i + 1, j), P(i + 1, j + 1), P(i, j + 1)], cc, CLOTH)
    for quads, col in decals:
        for q in quads:
            uv = [(0.5 + X / width, Y / height) for X, Y in q]
            # subdivide 2x2 so the decal hugs the curved cloth
            def lerp(a, c, t):
                return (a[0] + (c[0] - a[0]) * t, a[1] + (c[1] - a[1]) * t)
            for a in range(2):
                for c in range(2):
                    sub = []
                    for (s, t) in ((a / 2, c / 2), ((a + 1) / 2, c / 2), ((a + 1) / 2, (c + 1) / 2),
                                   (a / 2, (c + 1) / 2)):
                        top = lerp(uv[0], uv[1], s)
                        bot = lerp(uv[3], uv[2], s)
                        sub.append(lerp(top, bot, t))
                    for off in (0.025, -0.025):
                        b.poly([S(u, v, off) for u, v in sub], col, CLOTH)
    return S


def decal_strip(path, widths):
    """Quads along a polyline (sail metres) with per-point half-widths (paint stroke / tusk)."""
    out = []
    for i in range(len(path) - 1):
        (x0, y0), (x1, y1) = path[i], path[i + 1]
        dx, dy = x1 - x0, y1 - y0
        ln = math.hypot(dx, dy) or 1.0
        nx_, ny_ = -dy / ln, dx / ln
        w0, w1 = widths[i], widths[i + 1]
        out.append([(x0 + nx_ * w0, y0 + ny_ * w0), (x1 + nx_ * w1, y1 + ny_ * w1),
                    (x1 - nx_ * w1, y1 - ny_ * w1), (x0 - nx_ * w0, y0 - ny_ * w0)])
    return out


def ork_sigil_decal(cx, cy, s, rng):
    """Painted 'tusked maw': a broken ring of the jaw, two great tusks, crude drips."""
    quads = []
    seg = 14
    pts = [(cx + math.cos(a) * s, cy - math.sin(a) * s * 0.95)
           for a in (math.radians(-35 + k * (250 / seg)) for k in range(seg + 1))]
    quads += decal_strip(pts, [s * 0.11 * (0.8 + 0.4 * rng.random()) for _ in pts])
    for side in (1, -1):
        tusk = [(cx + side * s * (0.25 + 0.42 * k / 5 - 0.3 * (k / 5) ** 2), cy + s * (0.75 - 1.2 * k / 5))
                for k in range(6)]
        quads += decal_strip(tusk, [s * 0.16 * (1 - k / 5.3) for k in range(6)])
    for k in range(5):  # paint drips under the jaw
        x = cx + (k - 2) * s * 0.28 + rng.uniform(-0.05, 0.05)
        y0 = cy + s * (0.55 + 0.1 * rng.random())
        quads += decal_strip([(x, y0), (x, y0 + s * rng.uniform(0.3, 0.7))], [s * 0.05, s * 0.025])
    return quads


def shield(b, c, normal_y, r, face, rim, boss, n=8):
    c = Vector(c)
    pts = [c + Vector((math.cos(a) * r, normal_y * 0.0, math.sin(a) * r))
           for a in (k * math.tau / n for k in range(n))]
    front = c + Vector((0, normal_y * 0.05, 0))
    for k in range(n):
        j = (k + 1) % n
        b.poly([pts[k], pts[j], front], face if k % 2 else mix(face, rim, 0.25), SOLID)
    cyl(b, front, front + Vector((0, normal_y * 0.07, 0)), r * 0.28, r * 0.12, 6, boss, METAL, cap=False)
    # rim ring
    for k in range(n):
        j = (k + 1) % n
        a, z = pts[k], pts[j]
        b.poly([a, z, z + (z - c) * 0.14, a + (a - c) * 0.14], rim, METAL)


def skull(b, c, s, pal, rng, horns=True, glow=True, yaw=0.0):
    """Big horned beast skull facing +X (figurehead / bone totem)."""
    c = Vector(c)
    R = rotz(yaw)
    bone, bone_d, socket = pal["bone"], pal["bone_dark"], pal["socket"]
    sphere(b, c, (0.55 * s, 0.46 * s, 0.48 * s), 9, 7,
           lambda i, j: jit(mix(bone, bone_d, j / 7 * 0.7), rng, 0.06), SOLID, R)
    # snout / upper jaw
    sphere(b, c + R @ Vector((0.42 * s, 0, -0.18 * s)), (0.38 * s, 0.32 * s, 0.22 * s), 8, 5,
           lambda i, j: jit(bone, rng, 0.08), SOLID, R)
    # lower jaw
    box(b, c + R @ Vector((0.38 * s, 0, -0.42 * s)), (0.32 * s, 0.26 * s, 0.07 * s),
        jit(bone_d, rng), R @ Matrix.Rotation(-0.25, 3, "Y"))
    # heavy brow ridge (gives the skull a scowl instead of a round 'cute' dome)
    box(b, c + R @ Vector((0.36 * s, 0, 0.22 * s)), (0.16 * s, 0.44 * s, 0.07 * s),
        jit(bone_d, rng, 0.05), R @ Matrix.Rotation(0.35, 3, "Y"))
    for side in (1, -1):
        eye = c + R @ Vector((0.44 * s, side * 0.2 * s, 0.06 * s))
        sphere(b, eye, (0.12 * s, 0.15 * s, 0.13 * s), 6, 4, socket, SOLID, R)
        if glow:
            sphere(b, eye + R @ Vector((0.06 * s, 0, 0)), (0.05 * s, 0.06 * s, 0.05 * s), 6, 4,
                   pal["eye"], GLOW, R)
        # tusks curving up out of the lower jaw
        t0 = c + R @ Vector((0.6 * s, side * 0.22 * s, -0.42 * s))
        tusk = [t0 + R @ Vector((0.13 * s * k, side * 0.05 * s * k, 0.05 * s * k * k)) for k in range(5)]
        tube(b, tusk, [0.09 * s * (1 - k / 4.3) for k in range(5)], 6, jit(pal["tusk"], rng, 0.05))
        if horns:
            h0 = c + R @ Vector((-0.05 * s, side * 0.38 * s, 0.28 * s))
            horn = [h0 + R @ Vector((-0.2 * s * k, side * 0.22 * s * k, 0.3 * s * k - 0.07 * s * k * k))
                    for k in range(6)]
            tube(b, horn, [0.14 * s * (1 - k / 5.6) for k in range(6)], 6,
                 lambda i: mix(pal["horn"], bone_d, i / 5))


def flag(b, base, length, height, col_fn, rng, n=7, yaw=0.0):
    base = Vector(base)
    R = rotz(yaw)
    for i in range(n):
        u0, u1 = i / n, (i + 1) / n
        wv = lambda u: Vector((-u * length, math.sin(u * 7 + 1.0) * 0.18 * u * length / 2,
                               -0.12 * u * length))
        h0, h1 = height * (1 - 0.45 * u0), height * (1 - 0.45 * u1)
        p = [base + R @ (wv(u0)), base + R @ (wv(u1)),
             base + R @ (wv(u1) + Vector((0, 0, -h1))), base + R @ (wv(u0) + Vector((0, 0, -h0)))]
        cc = col_fn(u0)
        if cc is not None:
            b.poly(p, cc, CLOTH)


ORK_PAL = dict(
    plank_a=hexc(0x3b2a1f), plank_b=hexc(0x2e2119), bottom=hexc(0x1d1d17), tar=hexc(0x141210),
    band=hexc(0x7a1f17), inner=hexc(0x4a3424), deck=hexc(0x5a4330), bone=hexc(0xd9cdb0),
    bone_dark=hexc(0x8f8266), socket=hexc(0x15100c), eye=hexc(0xff4a1a), tusk=hexc(0xe8dcc0),
    horn=hexc(0x3a3128), iron=hexc(0x34312d), rust=hexc(0x6b3a22), sail=hexc(0x5e1b14),
    sail_d=hexc(0x3c120e), sigil=hexc(0xd8ccb0), black=hexc(0x1a1716), rope=hexc(0x6b5a40),
    fire=hexc(0xff7a22), hide=hexc(0x7a5a3a),
)


def ork_sigil(u, v):
    """Bone-white 'tusked jaw' sigil in sail space (u 0..1 across, v 0..1 down)."""
    x, y = (u - 0.5) * 1.15, v - 0.42
    r = math.hypot(x, y * 1.1)
    ring = 0.17 < r < 0.235 and y < 0.12
    tusks = any(abs(x - sx * (0.10 + (y - 0.02) * 0.25)) < 0.035 * (1 - (y - 0.02) / 0.32)
                and 0.02 < y < 0.32 for sx in (1, -1))
    teeth = abs(y + 0.03) < 0.035 and abs(x) < 0.16 and (int((x + 1) * 25) % 2 == 0)
    return ring or tusks or teeth


def build_ork_galley(name="ork_galley", seed=11):
    rng = random.Random(seed)
    b = B()
    P = ORK_PAL
    L, beam = 11.0, 1.55
    top_z, half_w, deck_z = hull(b, L, beam, 0.65, 1.0, 2.0, 1.5, P, rng, n=22)
    # iron ram at the bow waterline
    bx = L / 2
    for k, (zz, ln) in enumerate(((0.05, 1.3), (0.38, 0.9))):
        cyl(b, (bx - 0.6, 0, zz), (bx + ln, 0, zz - 0.05), 0.2 - k * 0.05, 0.02, 6, P["iron"], METAL)
    for side in (1, -1):
        cyl(b, (bx + 0.2, side * 0.12, 0.15), (bx + 0.55, side * 0.45, 0.25), 0.07, 0.0, 5, P["iron"], METAL)
    # bow stem post curling up into a horned skull figurehead
    stem = [(bx - 0.05, 0, top_z(1.0) - 0.4)]
    for k in range(1, 6):
        a = k / 5
        stem.append((bx + 0.35 * math.sin(a * 1.6), 0, top_z(1.0) - 0.4 + 1.3 * a))
    tube(b, stem, [0.2 - 0.02 * k for k in range(6)], 6, P["plank_b"])
    skull(b, Vector(stem[-1]) + Vector((0.25, 0, 0.35)), 1.05, P, rng)
    # stern post with a hanging iron cage-lantern
    sx = -L / 2
    spost = [(sx + 0.1, 0, top_z(0.0) - 0.3)] + [
        (sx - 0.35 * math.sin(k / 5 * 2.2), 0, top_z(0.0) - 0.3 + 1.1 * k / 5) for k in range(1, 6)]
    tube(b, spost, 0.16, 6, P["plank_b"])
    cyl(b, Vector(spost[-1]) + Vector((-0.25, 0, 0)), Vector(spost[-1]) + Vector((-0.25, 0, -0.55)),
        0.015, 0.015, 3, P["iron"], METAL)
    lantern = Vector(spost[-1]) + Vector((-0.25, 0, -0.75))
    box(b, lantern, (0.13, 0.13, 0.18), P["iron"], mat=METAL)
    sphere(b, lantern, (0.15, 0.15, 0.13), 6, 4, P["fire"], GLOW)
    # aft fighting platform (raised) with a hide-covered hut and a brazier
    plat_x0, plat_x1 = -L / 2 + 0.9, -L / 2 + 3.1
    pz = deck_z + 0.7
    box(b, ((plat_x0 + plat_x1) / 2, 0, pz - 0.05), ((plat_x1 - plat_x0) / 2, half_w(0.18) * 0.95, 0.06),
        P["deck"])
    for x in (plat_x0, plat_x1):
        for side in (1, -1):
            cyl(b, (x, side * half_w(0.15) * 0.8, deck_z), (x, side * half_w(0.15) * 0.8, pz + 0.55),
                0.06, 0.05, 5, P["plank_b"])
    # hut: lean-to of stitched hides on poles
    hx = plat_x0 + 0.85
    for side in (1, -1):
        b.poly([(hx - 0.7, side * 0.85, pz), (hx + 0.6, side * 0.85, pz),
                (hx + 0.5, side * 0.15, pz + 1.1), (hx - 0.6, side * 0.15, pz + 1.15)],
               jit(P["hide"], rng, 0.15), CLOTH)
    b.poly([(hx - 0.7, 0.85, pz), (hx - 0.6, 0.15, pz + 1.15), (hx - 0.6, -0.15, pz + 1.15),
            (hx - 0.7, -0.85, pz)], jit(P["hide"], rng, 0.2), CLOTH)
    brazier = Vector((plat_x1 - 0.35, 0.55, pz))
    cyl(b, brazier, brazier + Vector((0, 0, 0.45)), 0.08, 0.08, 5, P["iron"], METAL, cap=False)
    cyl(b, brazier + Vector((0, 0, 0.45)), brazier + Vector((0, 0, 0.62)), 0.12, 0.25, 7, P["iron"], METAL)
    sphere(b, brazier + Vector((0, 0, 0.68)), (0.2, 0.2, 0.16), 7, 4, P["fire"], GLOW)
    # war banner pole with skull totem
    bp = Vector((plat_x0 + 0.2, -0.6, pz))
    cyl(b, bp, bp + Vector((0, 0, 3.4)), 0.06, 0.05, 5, P["plank_b"])
    skull(b, bp + Vector((0.05, 0, 3.0)), 0.32, P, rng, horns=True, glow=False)
    flag(b, bp + Vector((0, 0, 3.35)), 1.6, 1.0,
         lambda u: None if (u > 0.7 and rng.random() < 0.35) else jit(P["black"], rng, 0.2), rng, yaw=0.15)
    # shields hung along both gunwales
    nsh = 10
    for side in (1, -1):
        for k in range(nsh):
            t = 0.22 + 0.56 * k / (nsh - 1)
            x = -L / 2 + t * L
            z = top_z(t) - 0.28
            face = [P["band"], P["black"], P["bone_dark"]][k % 3]
            shield(b, (x, side * (half_w(t) + 0.06), z), side, 0.32, jit(face, rng, 0.15), P["iron"],
                   P["rust"])
    # oars (oarsmen below deck)
    for side in (1, -1):
        for k in range(9):
            t = 0.25 + 0.5 * k / 8
            x = -L / 2 + t * L
            a = Vector((x, side * half_w(t) * 0.95, top_z(t) - 0.55))
            e = a + Vector((-0.35 + 0.1 * math.sin(k), side * 2.4, -0.95))
            cyl(b, a, e, 0.04, 0.035, 4, P["plank_a"], cap=False)
            d = (e - a).normalized()
            box(b, e + d * 0.35, (0.05, 0.42, 0.13), P["plank_b"],
                rot=Matrix.Rotation(math.atan2(d.z, abs(d.y)) * -side, 3, "X"))
    # rail spikes between the shields
    for side in (1, -1):
        for k in range(12):
            t = 0.2 + 0.6 * k / 11
            x = -L / 2 + t * L + 0.25
            base = Vector((x, side * half_w(t) * 1.03, top_z(t) - 0.02))
            cyl(b, base, base + Vector((0.05, side * 0.18, 0.42)), 0.05, 0.0, 4, P["bone"])
    # mast, yard, crow's nest, sail
    mx = 0.6
    cyl(b, (mx, 0, deck_z), (mx, 0, 8.2), 0.17, 0.11, 7, P["plank_a"])
    yard_z = 7.2
    cyl(b, (mx + 0.15, -3.0, yard_z), (mx + 0.15, 3.0, yard_z), 0.08, 0.08, 6, P["plank_b"])
    for side in (1, -1):
        cyl(b, (mx + 0.15, side * 3.0, yard_z), (mx + 0.15, side * 3.25, yard_z + 0.12), 0.06, 0.0, 4,
            P["bone"])
    box(b, (mx, 0, 8.0), (0.38, 0.38, 0.2), P["plank_b"])
    for k in range(6):  # spiked crown on the nest
        a = k / 6 * math.tau
        p = Vector((mx + math.cos(a) * 0.36, math.sin(a) * 0.36, 8.18))
        cyl(b, p, p + Vector((math.cos(a) * 0.1, math.sin(a) * 0.1, 0.35)), 0.04, 0.0, 4, P["bone"])
    flag(b, (mx, 0, 8.9), 1.8, 0.45, lambda u: jit(P["band"], rng, 0.2), rng, n=8, yaw=0.3)
    cyl(b, (mx, 0, 8.2), (mx, 0, 8.95), 0.04, 0.03, 4, P["plank_b"])
    srng = random.Random(seed + 5)
    holes = {(srng.randrange(28), srng.randrange(9, 20)) for _ in range(6)}

    def sail_col(u, v):
        i, j = int(u * 28), int(v * 20)
        if (i, j) in holes:
            return None
        stripe = P["sail"] if (i // 4) % 2 == 0 else P["sail_d"]
        grime = 0.25 * max(0.0, n2(u * 4, v * 4, 3.3))
        return jit(mix(mix(stripe, P["black"], v * 0.4), hexc(0x2a1a12), grime), srng, 0.08)

    sail(b, (mx + 0.2, 0, yard_z - 0.05), 5.6, 4.8, 1.1, 28, 20, sail_col, taper=0.04, rng=srng,
         ragged=0.2, decals=[(ork_sigil_decal(0.0, 2.0, 1.25, srng), P["sigil"])])
    # rigging lines (bow + stern stays, shrouds)
    for a, z in (((mx, 0, 7.9), (L / 2 + 0.3, 0, top_z(1.0) + 0.9)),
                 ((mx, 0, 7.9), (-L / 2 - 0.1, 0, top_z(0.0) + 0.6))):
        cyl(b, a, z, 0.02, 0.02, 3, P["rope"], cap=False)
    for side in (1, -1):
        for dx in (-0.6, 0.0, 0.6):
            cyl(b, (mx, 0, 7.6), (mx + dx, side * half_w(0.55) * 1.02, top_z(0.55)), 0.015, 0.015, 3,
                P["rope"], cap=False)
    # chained captive cage on deck (a hint of a story)
    cx = -0.9
    for k in range(6):
        a = k / 6 * math.tau
        p = Vector((cx + math.cos(a) * 0.45, math.sin(a) * 0.45, deck_z))
        cyl(b, p, p + Vector((0, 0, 1.0)), 0.025, 0.025, 3, P["iron"], METAL, cap=False)
    cyl(b, (cx, 0, deck_z + 1.0), (cx, 0, deck_z + 1.08), 0.5, 0.3, 6, P["iron"], METAL)
    return b.build(name)


def build_ork_raider(name="ork_raider", seed=23):
    rng = random.Random(seed)
    b = B()
    P = dict(ORK_PAL, plank_a=hexc(0x45301f), plank_b=hexc(0x372619), band=hexc(0x2a2522))
    L, beam = 6.0, 0.95
    top_z, half_w, deck_z = hull(b, L, beam, 0.4, 0.6, 1.1, 0.7, P, rng, n=16)
    bx = L / 2
    stem = [(bx - 0.05, 0, top_z(1.0) - 0.3)] + [
        (bx + 0.2 * math.sin(k / 4 * 1.4), 0, top_z(1.0) - 0.3 + 0.7 * k / 4) for k in range(1, 5)]
    tube(b, stem, 0.12, 6, P["plank_b"])
    skull(b, Vector(stem[-1]) + Vector((0.12, 0, 0.18)), 0.55, P, rng, horns=False)
    for side in (1, -1):
        for k in range(6):
            t = 0.24 + 0.52 * k / 5
            x = -L / 2 + t * L
            face = [P["sail"], P["bone_dark"], P["hide"]][k % 3]
            shield(b, (x, side * (half_w(t) + 0.05), top_z(t) - 0.18), side, 0.24, jit(face, rng, 0.2),
                   P["iron"], P["rust"], n=7)
        for k in range(5):
            t = 0.28 + 0.44 * k / 4
            x = -L / 2 + t * L
            a = Vector((x, side * half_w(t) * 0.95, top_z(t) - 0.35))
            e = a + Vector((-0.2, side * 1.5, -0.6))
            cyl(b, a, e, 0.03, 0.03, 4, P["plank_a"], cap=False)
            box(b, e, (0.04, 0.25, 0.08), P["plank_b"])
    cyl(b, (0.2, 0, deck_z), (0.2, 0, 4.6), 0.1, 0.07, 6, P["plank_a"])
    cyl(b, (0.3, -1.8, 4.1), (0.3, 1.8, 4.1), 0.05, 0.05, 5, P["plank_b"])
    srng = random.Random(seed + 9)

    def sail_col(u, v):
        if v > 0.82 and srng.random() < 0.18:
            return None
        return jit(mix(P["black"], hexc(0x2c2622), u), srng, 0.12)

    claws = []
    for o in (-0.55, 0.0, 0.55):
        path = [(o + 0.45 - 0.3 * k / 4 + 0.05 * math.sin(k), 0.45 + 1.7 * k / 4) for k in range(5)]
        claws += decal_strip(path, [0.04, 0.13, 0.15, 0.1, 0.02])
    sail(b, (0.38, 0, 4.05), 3.4, 2.7, 0.55, 12, 10, sail_col, rng=srng, ragged=0.25,
         decals=[(claws, hexc(0x9a2016))])
    flag(b, (0.2, 0, 4.9), 1.0, 0.3, lambda u: jit(hexc(0x8c1d14), rng, 0.1), rng, n=6, yaw=0.3)
    cyl(b, (0.2, 0, 4.6), (0.2, 0, 4.95), 0.03, 0.02, 4, P["plank_b"])
    # torch at the stern
    tp = Vector((-L / 2 + 0.6, 0, top_z(0.1)))
    cyl(b, tp, tp + Vector((-0.1, 0, 0.9)), 0.04, 0.04, 4, P["plank_b"])
    sphere(b, tp + Vector((-0.1, 0, 1.0)), (0.12, 0.12, 0.16), 6, 4, P["fire"], GLOW)
    return b.build(name)


PALE_PAL = dict(
    plank_a=hexc(0x8d8a7e), plank_b=hexc(0x77756b), bottom=hexc(0x2f3a36), tar=hexc(0x3b4a44),
    band=hexc(0x3f6b63), inner=hexc(0x6e6a5e), deck=hexc(0x8a8270), sail=hexc(0xcfc8b4),
    sail_d=hexc(0xa9a596), batten=hexc(0x2e2a24), teal=hexc(0x3fe0b8), robe=hexc(0x4a5552),
    rope=hexc(0x5a5446), stone=hexc(0xb7b2a2), verdigris=hexc(0x4f8f7e),
)


def build_pale_lantern(name="pale_lantern", seed=37):
    """Tall, narrow, ghost-pale junk with fan sails, lantern strings and a hooded figurehead
    holding a light out over the water. Nobody knows who sails it."""
    rng = random.Random(seed)
    b = B()
    P = PALE_PAL
    L, beam = 12.0, 1.35
    top_z, half_w, deck_z = hull(b, L, beam, 0.6, 1.2, 1.2, 2.6, P, rng, n=22, flare=0.14)
    # stern tower (high, narrow, with a big lantern room)
    sx0, sx1 = -L / 2 + 0.5, -L / 2 + 2.4
    tz = top_z(0.12)
    box(b, ((sx0 + sx1) / 2, 0, tz + 0.55), ((sx1 - sx0) / 2, half_w(0.12) * 0.85, 0.55), P["plank_b"])
    box(b, ((sx0 + sx1) / 2 + 0.05, 0, tz + 1.15), ((sx1 - sx0) / 2 + 0.1, half_w(0.12) * 0.95, 0.06),
        P["band"])
    lz = tz + 1.21
    for x in (sx0 + 0.25, sx1 - 0.15):
        for side in (1, -1):
            cyl(b, (x, side * 0.45, lz), (x, side * 0.45, lz + 0.9), 0.05, 0.05, 4, P["verdigris"], METAL)
    sphere(b, ((sx0 + sx1) / 2, 0, lz + 0.45), (0.55, 0.42, 0.4), 8, 5, P["teal"], GLOW)
    cyl(b, ((sx0 + sx1) / 2, 0, lz + 0.9), ((sx0 + sx1) / 2, 0, lz + 1.6), 0.9, 0.0, 8, P["verdigris"], METAL)
    # hooded figurehead holding a lantern out ahead
    bx = L / 2
    fb = Vector((bx - 0.35, 0, top_z(0.97) - 0.2))
    cyl(b, fb, fb + Vector((0.55, 0, 1.25)), 0.32, 0.2, 7, P["robe"])  # robe body leaning forward
    hood = fb + Vector((0.66, 0, 1.45))
    sphere(b, hood, (0.24, 0.22, 0.27), 7, 5, P["robe"])
    sphere(b, hood + Vector((0.13, 0, -0.03)), (0.12, 0.15, 0.17), 6, 4, hexc(0x0b0d0c))  # empty face
    arm = [fb + Vector((0.5, 0.18, 1.05)), fb + Vector((0.95, 0.2, 1.2)), fb + Vector((1.4, 0.15, 1.35))]
    tube(b, arm, [0.08, 0.07, 0.06], 5, P["robe"])
    hook = arm[-1]
    cyl(b, hook, hook + Vector((0, 0, -0.35)), 0.012, 0.012, 3, P["verdigris"], METAL, cap=False)
    sphere(b, hook + Vector((0, 0, -0.5)), (0.14, 0.14, 0.17), 6, 4, P["teal"], GLOW)
    # three masts with battened fan sails
    masts = [(2.6, 7.2, 2.2, 4.8), (-0.2, 9.0, 2.7, 6.3), (-2.9, 7.6, 2.2, 5.2)]
    srng = random.Random(seed + 3)
    for mi, (mx, mh, sw, shh) in enumerate(masts):
        cyl(b, (mx, 0, deck_z), (mx, 0, mh), 0.13, 0.08, 6, P["plank_b"])
        cyl(b, (mx, 0, mh), (mx, 0, mh + 0.5), 0.05, 0.0, 4, P["verdigris"], METAL)
        top = mh - 0.35
        nb = 7
        holes = {(srng.randrange(10), srng.randrange(2, 9)) for _ in range(4)}

        def sail_col(u, v, holes=holes):
            i, j = int(u * 10), int(v * 9)
            if (i, j) in holes:
                return None
            c = P["sail"] if (j % 2 == 0) else P["sail_d"]
            stain = smooth(0.4, 1.0, v) * 0.35 + 0.25 * max(0.0, n2(u * 3, v * 3, mi))
            return jit(mix(c, P["verdigris"], stain * 0.5), srng, 0.05)

        sail(b, (mx - 0.35, 0, top), sw * 1.0, shh, 0.35, 10, 9, sail_col, taper=0.9, rng=srng,
             ragged=0.12, yaw=0.18 * (1 if mi % 2 else -1))
        R = rotz(0.18 * (1 if mi % 2 else -1))
        for k in range(nb + 1):  # battens
            v = k / nb
            hw = sw * 1.0 * (0.5 + 0.9 * v * 0.5)
            z = top - v * shh
            xo = 0.35 * math.sin(math.pi * min(v * 0.95 + 0.05, 1.0)) ** 0.8 * 0.6
            a = Vector((mx - 0.35, 0, 0)) + R @ Vector((xo, -hw * 2 * 0.5, 0))
            e = Vector((mx - 0.35, 0, 0)) + R @ Vector((xo, hw * 2 * 0.5, 0))
            a.z = e.z = z
            cyl(b, a, e, 0.025, 0.025, 3, P["batten"], cap=False)
    # lantern strings sagging between mast tops and the stern tower
    anchors = [(L / 2 + 0.4, 0, top_z(1.0) + 0.6), (2.6, 0, 6.9), (-0.2, 0, 8.6), (-2.9, 0, 7.3),
               ((sx0 + sx1) / 2, 0, lz + 1.5)]
    for a, z in zip(anchors[:-1], anchors[1:]):
        a, z = Vector(a), Vector(z)
        pts = []
        for k in range(9):
            t = k / 8
            p = a.lerp(z, t)
            p.z -= math.sin(math.pi * t) * 1.1
            pts.append(p)
        for p0, p1 in zip(pts[:-1], pts[1:]):
            cyl(b, p0, p1, 0.012, 0.012, 3, P["rope"], cap=False)
        for p in pts[2:-1:2]:
            sphere(b, p + Vector((0, 0, -0.18)), (0.07, 0.07, 0.09), 5, 3, P["teal"], GLOW)
    # hull runes: verdigris eye at the bow, both sides
    for side in (1, -1):
        e = Vector((bx - 1.2, side * (half_w(0.9) + 0.07), top_z(0.9) * 0.55))
        sphere(b, e, (0.32, 0.03, 0.17), 8, 3, P["verdigris"], METAL)
        sphere(b, e + Vector((0.03, side * 0.03, 0)), (0.1, 0.02, 0.1), 6, 3, P["teal"], GLOW)
    return b.build(name)


# ── islands ────────────────────────────────────────────────────────────────────
def heightfield(b, size, N, hfn, colfn, matfn=None, cull=-1.6):
    h = size / N
    xs = [-size / 2 + i * h for i in range(N + 1)]
    Z = [[hfn(x, y) for x in xs] for y in xs]
    for j in range(N):
        for i in range(N):
            zs = (Z[j][i], Z[j][i + 1], Z[j + 1][i + 1], Z[j + 1][i])
            if max(zs) < cull:
                continue
            q = [(xs[i], xs[j], zs[0]), (xs[i + 1], xs[j], zs[1]), (xs[i + 1], xs[j + 1], zs[2]),
                 (xs[i], xs[j + 1], zs[3])]
            sx = (zs[1] + zs[2] - zs[0] - zs[3]) / (2 * h)
            sy = (zs[3] + zs[2] - zs[0] - zs[1]) / (2 * h)
            slope = math.hypot(sx, sy)
            cols = [colfn(p[0], p[1], p[2], slope) for p in q]
            mat = matfn(q, slope) if matfn else SOLID
            b.poly(q, cols, mat)
    return Z, xs


def pine(b, base, hgt, rng, dark=0.0):
    base = Vector(base)
    g = mix(hexc(0x2b4a26), hexc(0x16261a), dark + rng.uniform(0, 0.4))
    cyl(b, base + Vector((0, 0, -0.3)), base + Vector((0, 0, hgt * 0.25)), hgt * 0.05, hgt * 0.04, 4,
        hexc(0x3a2a1c))
    r = hgt * 0.26
    for k, (z0, z1, rr) in enumerate(((0.15, 0.75, 1.0), (0.45, 1.0, 0.68))):
        cyl(b, base + Vector((0, 0, hgt * z0)), base + Vector((rng.uniform(-.05, .05), 0, hgt * z1)),
            r * rr, 0.0, 6, jit(mix(g, hexc(0x3c6a33), k * 0.25), rng, 0.08), cap=True)


def build_pine_crag(name="isle_pine_crag", seed=3):
    rng = random.Random(seed)
    b = B()
    S = 3.1

    def hfn(x, y):
        d = math.hypot(x / 34, y / 23) + 0.17 * n2(x * 0.045, y * 0.045, S) + 0.05 * n2(x * .16, y * .16, S + 2)
        m = 1 - d
        ang = math.atan2(y, x)
        cove = max(0.0, math.cos(ang - 2.5)) ** 5
        shelf = -3.0 + 3.1 * smooth(-0.16, 0.0, m)
        cliff = smooth(0.0, 0.06, m) * 8.5 * (1 - cove)
        beach = smooth(0.0, 0.35, m) * 3.0 * cove
        ridge = 1 - abs(fbm(x * 0.05, y * 0.05, S + 5, 4))
        hills = smooth(0.05, 0.75, m) * (5 + 9 * ridge ** 2) * (1 - 0.5 * cove)
        return shelf + max(cliff, beach) + hills + 0.4 * n2(x * 0.3, y * 0.3, S + 9) * smooth(0, .1, m)

    def colfn(x, y, z, s):
        nz = n2(x * 0.2, y * 0.2, 11)
        if z < -0.25:
            return mix(hexc(0x1f2a26), hexc(0x2d3a30), nz * 0.5 + 0.5)
        if z < 0.35:
            return hexc(0x2a2620) if s > 0.5 else hexc(0xb59c6c)
        if s > 0.85:
            strata = 0.5 + 0.5 * math.sin(z * 2.6 + nz * 1.5)
            return mix(hexc(0x5b5952), hexc(0x8a857a), strata * 0.7)
        if z < 1.3 and s < 0.5:
            return mix(hexc(0xc4ab78), hexc(0x7a8a4a), smooth(0.6, 1.3, z))
        g = mix(hexc(0x3f6a2c), hexc(0x6d8a3c), 0.5 + 0.5 * nz)
        return mix(g, hexc(0x8a8a5a), smooth(12, 18, z) * 0.6)

    Z, xs = heightfield(b, 90, 70, hfn, colfn)
    # pines in clumps on gentle green ground
    for _ in range(900):
        x, y = rng.uniform(-40, 40), rng.uniform(-30, 30)
        z = hfn(x, y)
        e = 0.6
        s = math.hypot(hfn(x + e, y) - hfn(x - e, y), hfn(x, y + e) - hfn(x, y - e)) / (2 * e)
        if z > 2.0 and s < 0.7 and n2(x * 0.09, y * 0.09, 21) > -0.05:
            pine(b, (x, y, z), rng.uniform(2.6, 4.6), rng, dark=smooth(10, 16, z) * 0.3)
    # sea stacks off the cliffs
    for (x, y, r, hgt) in ((36, 6, 2.2, 9), (33, -9, 1.4, 6.5), (39, -2, 1.0, 4)):
        pts = [(x, y, -1.5)] + [(x + rng.uniform(-.3, .3), y + rng.uniform(-.3, .3), hgt * k / 4) for k in range(1, 5)]
        tube(b, pts, [r * 1.25, r * 1.05, r, r * 0.9, r * 0.75], 7,
             lambda i: mix(hexc(0x4f4d47), hexc(0x8a857a), i / 4))
        cyl(b, (x, y, hgt), (x, y, hgt + 0.35), r * 0.8, r * 0.5, 7, hexc(0x4c6e30))
    # ruined watchtower on the high ground, beacon still lit
    best = max(((hfn(x, y), x, y) for x in range(-20, 21, 3) for y in range(-12, 13, 3)))
    tz, tx, ty = best
    stone = hexc(0x9a948a)
    n = 9
    for k in range(n):
        a0, a1 = k / n * math.tau, (k + 1) / n * math.tau
        top0 = 6.5 - (2.4 if k in (2, 3) else rng.uniform(0, 0.9))
        for (ri, ro) in ((1.15, 1.45),):
            p = lambda a, r, z: (tx + math.cos(a) * r, ty + math.sin(a) * r, tz + z)
            b.poly([p(a0, ro, -1), p(a1, ro, -1), p(a1, ro, top0), p(a0, ro, top0)], jit(stone, rng, 0.12))
            b.poly([p(a0, ri, -1), p(a0, ri, top0), p(a1, ri, top0), p(a1, ri, -1)], jit(stone, rng, 0.2))
            b.poly([p(a0, ri, top0), p(a0, ro, top0), p(a1, ro, top0), p(a1, ri, top0)], hexc(0x6b6a58))
    sphere(b, (tx, ty, tz + 5.4), (0.75, 0.75, 0.9), 7, 4, hexc(0xffa040), GLOW)
    for k in range(5):  # tumbled blocks
        a = rng.uniform(0, math.tau)
        r = rng.uniform(2.0, 3.5)
        box(b, (tx + math.cos(a) * r, ty + math.sin(a) * r, hfn(tx + math.cos(a) * r, ty + math.sin(a) * r) + 0.2),
            (0.45, 0.3, 0.3), jit(stone, rng, 0.15), rot=rotz(rng.uniform(0, 3)))
    return b.build(name, sharp_deg=55)


def build_bone_atoll(name="isle_bone_atoll", seed=5):
    rng = random.Random(seed)
    b = B()
    S = 8.7

    def hfn(x, y):
        d = math.hypot(x / 30, y / 16) + 0.14 * n2(x * 0.05, y * 0.05, S)
        m = 1 - d
        dune = 0.8 * fbm(x * 0.08, y * 0.08, S + 3, 3)
        hill = 6.5 * smooth(0.25, 0.85, 1 - math.hypot((x + 12) / 12, (y - 2) / 9))
        return -2.4 + 2.9 * smooth(-0.1, 0.12, m) + smooth(0.05, 0.6, m) * (1.4 + dune) + hill

    def colfn(x, y, z, s):
        nz = n2(x * 0.25, y * 0.25, 4)
        if z < -0.2:
            return mix(hexc(0x2f5a5a), hexc(0x9ed0c0), smooth(-1.5, -0.2, z))  # shallows
        if z < 0.6:
            return mix(hexc(0xe2cf9e), hexc(0xd2bd8a), 0.5 + 0.5 * nz)
        if s > 0.8:
            return mix(hexc(0x8a7a5a), hexc(0xa89a76), 0.5 + 0.5 * nz)
        grass = smooth(-0.1, 0.4, nz + (z - 1.0) * 0.25)
        return mix(hexc(0xd8c48e), mix(hexc(0x8a9a4a), hexc(0x5d7a36), 0.5 + 0.5 * nz), grass)

    heightfield(b, 76, 60, hfn, colfn)
    bone, bone_d = hexc(0xe6dcc4), hexc(0x9c8f72)
    # colossal skeleton: spine arching out of the dunes, ribs, a half-buried skull with one tusk
    spine = []
    for k in range(15):
        t = k / 14
        x = -2 + t * 26
        y = 4 * math.sin(t * 2.3)
        z = hfn(x, y) - 0.8 + 3.2 * math.sin(math.pi * min(t * 1.15, 1.0))
        spine.append(Vector((x, y, z)))
    tube(b, spine, [0.7 - 0.25 * k / 14 for k in range(15)], 6, lambda i: jit(bone_d, rng, 0.1))
    for k, p in enumerate(spine[1:-1:2]):  # vertebra knobs
        sphere(b, p + Vector((0, 0, 0.5)), (0.5, 0.6, 0.45), 6, 4, jit(bone, rng, 0.08))
    for k in range(2, 12):
        p = spine[k]
        span = 4.5 * math.sin(math.pi * (k - 1) / 12) + 1.0
        for side in (1, -1):
            if rng.random() < 0.12:
                continue  # missing ribs
            rib = []
            for q in range(8):
                a = q / 7
                rib.append(p + Vector((-0.6 * a, side * span * math.sin(a * 1.9),
                                       2.0 * math.sin(a * 2.2) - (p.z - hfn(p.x, p.y + side * span)) * a ** 1.5 - 0.6 * a)))
            if rng.random() < 0.3:
                rib = rib[:rng.randint(4, 6)]  # broken
            tube(b, rib, [0.32 * (1 - 0.55 * q / 7) for q in range(len(rib))], 5,
                 lambda i: jit(mix(bone, bone_d, i / 7), rng, 0.06), cap=True)
    sk = spine[-1] + Vector((3.5, 1.0, -0.6))
    sk.z = hfn(sk.x, sk.y) + 1.2
    sphere(b, sk, (3.0, 2.2, 2.0), 9, 6, lambda i, j: jit(mix(bone, bone_d, j / 6), rng, 0.06))
    sphere(b, sk + Vector((2.6, 0, -0.6)), (2.2, 1.6, 1.1), 8, 5, lambda i, j: jit(bone, rng, 0.06))
    sphere(b, sk + Vector((1.6, 1.3, 0.5)), (0.6, 0.45, 0.55), 6, 4, hexc(0x1b1510))
    tusk = [sk + Vector((3.2, -1.0, -0.6)) + Vector((1.4 * k, -0.4 * k, 0.6 * k * k * 0.5)) for k in range(6)]
    tube(b, tusk, [0.55 * (1 - k / 5.5) for k in range(6)], 6, jit(hexc(0xefe4c8), rng, 0.04))
    # sparse grass tufts / shrubs on the hill
    for _ in range(260):
        x, y = rng.uniform(-30, 25), rng.uniform(-13, 13)
        z = hfn(x, y)
        if z > 1.0 and n2(x * 0.25, y * 0.25, 4) > 0.0:
            sphere(b, (x, y, z + 0.2), (rng.uniform(.5, 1.0),) * 2 + (rng.uniform(.35, .7),), 5, 3,
                   jit(mix(hexc(0x4f6a2a), hexc(0x7a8a3c), rng.random()), rng, 0.1))
    return b.build(name, sharp_deg=55)


def build_ash_peak(name="isle_ash_peak", seed=9):
    rng = random.Random(seed)
    b = B()
    S = 2.2

    def hfn(x, y):
        d = math.hypot(x / 30, y / 26) + 0.12 * n2(x * 0.06, y * 0.06, S)
        m = 1 - d
        gully = abs(n2(math.atan2(y, x) * 2.5, d * 3, S + 4))
        cone = 26 * smooth(0.0, 1.0, m) ** 1.6 * (0.85 + 0.15 * gully)
        crater = 7 * smooth(0.72, 0.92, m)
        return -3 + 3.3 * smooth(-0.12, 0.02, m) + cone - crater + 0.6 * n2(x * .3, y * .3, S + 7)

    def lava(x, y, z):
        d = math.hypot(x / 30, y / 26)
        g = abs(n2(math.atan2(y, x) * 3.2, 0.5, S + 13))
        return (g < 0.07 and 3 < z < 18) or d < 0.18

    def colfn(x, y, z, s):
        nz = n2(x * 0.2, y * 0.2, 6)
        if z < 0.3:
            return hexc(0x16161a)
        c = mix(hexc(0x26221f), hexc(0x423a33), 0.5 + 0.5 * nz)
        c = mix(c, hexc(0x6a645c), smooth(17, 22, z) * 0.6)  # ash dusting near the rim
        if s < 0.35 and z < 4:
            c = mix(c, hexc(0x3d4528), 0.6)  # sickly scrub at the foot
        if lava(x, y, z):
            return hexc(0xff4a12) if math.hypot(x / 30, y / 26) < 0.18 else hexc(0xd8380e)
        return c

    def matfn(q, s):
        cx, cy = sum(p[0] for p in q) / 4, sum(p[1] for p in q) / 4
        return GLOW if lava(cx, cy, sum(p[2] for p in q) / 4) else SOLID

    heightfield(b, 74, 58, hfn, colfn, matfn)
    # ork shore camp: palisade of stakes, jetty, totem with skull
    wood, wood_d = hexc(0x4a3524), hexc(0x2e2117)
    for k in range(34):
        a = 3.6 + k * 0.035
        r = 28.0 + rng.uniform(-0.4, 0.4)
        x, y = math.cos(a) * r * 0.98, math.sin(a) * r * 0.85
        z = max(hfn(x, y), 0.2)
        cyl(b, (x, y, z - 0.3), (x * 1.01, y * 1.01, z + rng.uniform(2.2, 3.0)), 0.22, 0.0, 5,
            jit(wood, rng, 0.2))
    jx, jy = math.cos(3.95) * 31, math.sin(3.95) * 27
    for k in range(6):
        p = Vector((jx, jy, 0)) + Vector((math.cos(3.95), math.sin(3.95), 0)) * (k * 1.4)
        for side in (-1, 1):
            q = p + Vector((-math.sin(3.95), math.cos(3.95), 0)) * side * 0.8
            cyl(b, q + Vector((0, 0, -1.5)), q + Vector((0, 0, 0.9)), 0.13, 0.12, 5, wood_d)
    a = Vector((math.cos(3.95), math.sin(3.95), 0))
    box(b, Vector((jx, jy, 0.75)) + a * 3.5, (3.9, 0.9, 0.1), wood, rot=rotz(3.95))
    tp = Vector((math.cos(3.75) * 26, math.sin(3.75) * 22, 0))
    tp.z = hfn(tp.x, tp.y)
    cyl(b, tp, tp + Vector((0, 0, 6.0)), 0.3, 0.22, 6, wood_d)
    skull(b, tp + Vector((0, 0, 5.6)), 1.3, ORK_PAL, rng, yaw=3.75)
    for side in (1, -1):  # two signal braziers
        bp = tp + Vector((side * 2.0, side * 1.2, 0))
        bp.z = hfn(bp.x, bp.y)
        cyl(b, bp, bp + Vector((0, 0, 1.6)), 0.2, 0.5, 6, ORK_PAL["iron"], METAL)
        sphere(b, bp + Vector((0, 0, 1.75)), (0.55, 0.55, 0.5), 6, 4, ORK_PAL["fire"], GLOW)
    return b.build(name, sharp_deg=50)


def smoke_plume(name, base, height, radius):
    """Volumetric smoke column (render-only; in game this would be a cheap billboard)."""
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=1.0)
    ob = bpy.context.object
    ob.name = name
    ob.scale = (radius, radius, height / 2)
    ob.location = Vector(base) + Vector((0, 0, height / 2))
    m = bpy.data.materials.new(name + "_mat")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Color"].default_value = (0.08, 0.075, 0.07, 1)
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 2.2
    nz.inputs["Detail"].default_value = 6
    co = nt.nodes.new("ShaderNodeTexCoord")
    grad = nt.nodes.new("ShaderNodeMath")
    grad.operation = "MULTIPLY"
    ramp = nt.nodes.new("ShaderNodeMapRange")
    ramp.inputs["From Min"].default_value = 0.45
    ramp.inputs["From Max"].default_value = 0.75
    ramp.inputs["To Max"].default_value = 0.9
    sph = nt.nodes.new("ShaderNodeVectorMath")
    sph.operation = "LENGTH"
    fall = nt.nodes.new("ShaderNodeMapRange")
    fall.inputs["From Min"].default_value = 1.0
    fall.inputs["From Max"].default_value = 0.3
    nt.links.new(co.outputs["Object"], nz.inputs["Vector"])
    nt.links.new(co.outputs["Object"], sph.inputs[0])
    nt.links.new(sph.outputs["Value"], fall.inputs["Value"])
    nt.links.new(nz.outputs["Fac"], ramp.inputs["Value"])
    nt.links.new(ramp.outputs["Result"], grad.inputs[0])
    nt.links.new(fall.outputs["Result"], grad.inputs[1])
    nt.links.new(grad.outputs["Value"], vol.inputs["Density"])
    nt.links.new(vol.outputs["Volume"], out.inputs["Volume"])
    ob.data.materials.append(m)
    return ob


# ── stage: water, sky, light ───────────────────────────────────────────────────
def setup_stage():
    sc = SCENE
    for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            sc.render.engine = eng
            break
        except TypeError:
            pass
    sc.render.resolution_x, sc.render.resolution_y = 1600, 900
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    ee = sc.eevee
    for attr, val in (("taa_render_samples", 64), ("use_raytracing", True), ("use_shadows", True),
                      ("volumetric_end", 1500.0), ("volumetric_tile_size", "4"),
                      ("use_volumetric_shadows", True)):
        try:
            setattr(ee, attr, val)
        except (AttributeError, TypeError):
            pass
    try:
        ee.ray_tracing_options.resolution_scale = "1"
    except Exception:
        pass
    # ocean
    bpy.ops.mesh.primitive_plane_add(size=6000, location=(0, 0, 0))
    sea = bpy.context.object
    sea.name = "sea"
    m = bpy.data.materials.new("sea")
    m.use_nodes = True
    nt = m.node_tree
    bs = nt.nodes["Principled BSDF"]
    bs.inputs["Base Color"].default_value = (0.012, 0.045, 0.055, 1)
    bs.inputs["Roughness"].default_value = 0.06
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 900.0
    nz.inputs["Detail"].default_value = 8
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.12
    nt.links.new(nz.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bs.inputs["Normal"])
    sea.data.materials.append(m)
    # sun + sky
    sun = bpy.data.lights.new("sun", "SUN")
    sun.energy = 4.2
    sun.color = (1.0, 0.92, 0.82)
    sun.angle = math.radians(2.5)
    so = bpy.data.objects.new("sun", sun)
    so.rotation_euler = (math.radians(58), 0, math.radians(-140))
    SCENE.collection.objects.link(so)
    w = bpy.data.worlds.new("sky")
    w.use_nodes = True
    nt = w.node_tree
    bg = nt.nodes["Background"]
    co = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    rmp = nt.nodes.new("ShaderNodeValToRGB")
    rmp.color_ramp.elements[0].position = 0.0
    rmp.color_ramp.elements[0].color = (0.62, 0.66, 0.68, 1)  # hazy horizon
    rmp.color_ramp.elements[1].position = 0.45
    rmp.color_ramp.elements[1].color = (0.22, 0.36, 0.58, 1)
    nt.links.new(co.outputs["Generated"], sep.inputs[0])
    nt.links.new(sep.outputs["Z"], rmp.inputs["Fac"])
    nt.links.new(rmp.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 1.0
    SCENE.world = w
    return sea, w


def set_fog(world, density):
    nt = world.node_tree
    out = nt.nodes["World Output"]
    vol = nt.nodes.get("fog") or nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.name = "fog"
    vol.inputs["Color"].default_value = (0.7, 0.76, 0.82, 1)
    vol.inputs["Density"].default_value = density
    vol.inputs["Anisotropy"].default_value = 0.3
    if density > 0:
        nt.links.new(vol.outputs["Volume"], out.inputs["Volume"])
    else:
        for l in list(out.inputs["Volume"].links):
            nt.links.remove(l)


def cam_look(eye, target, lens=50):
    cam = SCENE.camera
    if cam is None:
        cd = bpy.data.cameras.new("cam")
        cam = bpy.data.objects.new("cam", cd)
        SCENE.collection.objects.link(cam)
        SCENE.camera = cam
    cam.data.lens = lens
    cam.data.clip_end = 5000
    cam.location = Vector(eye)
    cam.rotation_euler = (Vector(target) - Vector(eye)).to_track_quat("-Z", "Y").to_euler()


def render(name, visible):
    if ONLY and name not in ONLY:
        return
    for o in SCENE.objects:
        if o.type in ("MESH",) and o.name != "sea":
            o.hide_render = o not in visible
    SCENE.render.filepath = str(OUTDIR / f"{name}.png")
    t = time.time()
    bpy.ops.render.render(write_still=True)
    print(f"[seafarers] rendered {name} in {time.time() - t:.1f}s")


# ── main ───────────────────────────────────────────────────────────────────────
sea, world = setup_stage()
galley = build_ork_galley()
raider = build_ork_raider()
pale = build_pale_lantern()
crag = build_pine_crag()
atoll = build_bone_atoll()
ash = build_ash_peak()
smoke = smoke_plume("ash_smoke", (0, 0, 16), 34, 7)
smoke.parent = ash
for o, loc in ((galley, (0, 0, 0)), (raider, (0, 40, 0)), (pale, (0, 80, 0)),
               (crag, (400, 0, 0)), (atoll, (400, 200, 0)), (ash, (400, -220, 0))):
    o.location = loc

set_fog(world, 0.0)
cam_look((12.5, -19.5, 5.5), (0.3, 0, 3.6), 40)
render("ork_galley", [galley])
cam_look((-13.0, -14.5, 6.5), (-1.0, 0, 3.4), 40)
render("ork_galley_stern", [galley])
cam_look((6.5, 40 - 9.5, 3.0), (0.0, 40, 1.8), 40)
render("ork_raider", [raider])
cam_look((11.5, 80 - 15.5, 4.8), (0.0, 80, 3.6), 40)
render("pale_lantern", [pale])
cam_look((400 + 55, -70, 22), (400, 0, 5), 38)
render("isle_pine_crag", [crag])
cam_look((400 + 42, 200 - 48, 15), (400 + 3, 200, 2), 38)
render("isle_bone_atoll", [atoll])
cam_look((400 - 68, -220 - 52, 16), (400, -220, 9), 38)
render("isle_ash_peak", [ash, smoke])

# seascape: how they would read from the island shore, through the game's sea haze
copies = []
for src, loc, yaw in ((crag, (-140, 330, 0), 0.4), (ash, (210, 430, 0), 2.2), (atoll, (40, 250, 0), -0.3),
                      (galley, (-25, 105, 0), 0.25), (raider, (12, 82, 0), 0.4), (raider, (24, 92, 0), 0.35),
                      (pale, (95, 160, 0), 2.9)):
    c = src.copy()
    SCENE.collection.objects.link(c)
    c.location = loc
    c.rotation_euler = (0, 0, yaw)
    copies.append(c)
sm2 = smoke.copy()
SCENE.collection.objects.link(sm2)
sm2.parent = None
sm2.location = Vector((210, 430, 16 + 17))
copies.append(sm2)
set_fog(world, 0.0022)
cam_look((0, -10, 7), (20, 200, 8), 32)
render("seascape", copies)
cam_look((-60, 40, 4), (-25, 105, 3.5), 45)
render("seascape_galley_close", copies)

bpy.ops.wm.save_as_mainfile(filepath=str(OUTDIR / "seafarers.blend"))
print(f"[seafarers] done in {time.time() - T0:.1f}s -> {OUTDIR}")
