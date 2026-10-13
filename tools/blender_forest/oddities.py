"""The wilds' five unique creatures (src/oddities.rs) -> oddities.glb.

Sculpted as signed-distance models (sdfkit.py, the animals' method): smooth muscle / chitin blends,
baked per-vertex region (R), cavity / AO (G), coat tone (B) and tint (A) plus a flow UV, drawn on the
shared creature material (`Kit::coat_part` maps tone / tint onto each creature's colour ramp).
Animated pieces are separate objects with their pivot at the origin (the game poses them):

  odd_nest_snag        dead pollard oak (bark_oak, cylindrical bark UVs) with one stout limb
  odd_nest             grey paper hornet nest, hung from its top (origin = attach point)
  odd_hornet           one hornet (swarm particle), ~2x life size so it reads
  odd_toad_body        the Lantern Toad: dog-sized, warty, squatting, parotoid glands, gold eyes
  odd_toad_sac         its throat sac (glow material; origin = sac centre so it can pulse)
  odd_vulture_body     griffon vulture body + bare neck + ruff + hooked bill (no legs, no wings)
  odd_vulture_wing     LEFT wing, spread, pivot at the shoulder (the game mirrors it)
  odd_vulture_legs     feathered thighs, scaly shanks, talons (hidden in flight)
  odd_antlion_head     antlion larva: head + bristly thorax / abdomen, buried to the thorax
  odd_antlion_jaw      LEFT sickle mandible, pivot at its base (mirrored for the right)
  odd_antlion_pit      the sand funnel (s_plaster tinted to the dune sand), rim r ~4.3

Game coords (Y up, +Z forward = the creature's face), real-ish scale (hero ~1.3u, 1u ~ 1.35 m).

    blender -b --factory-startup --python tools/blender_forest/oddities.py
"""
import math
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from common import OUT, clear_scene, export_glb, name_material  # noqa: E402
from sdfkit import (  # noqa: E402
    Body, Chain, Cone, Ellipsoid, RBox, Sphere, Squash, Tufts, ambient_occlusion, axis_uv, gradient,
    mesh_body, norm, rot_x, rot_y, rot_z, smoothstep, v3,
)

MAIN, SKIN, DETAIL, EYE, ACCENT, HORN = range(6)
I3 = np.eye(3)


def bl(p):
    return np.stack([p[:, 0], -p[:, 2], p[:, 1]], 1)


class Ground:
    """Half-space y >= y0 (as a primitive to `cut` with)."""

    def __init__(self, y0):
        self.y0 = y0

    def d(self, p):
        return self.y0 - p[:, 1]

    def bounds(self):
        return v3((-50, self.y0, -50)), v3((50, 50, 50))


class Fn:
    """Wrap a callable p -> value as a shag source."""

    def __init__(self, f):
        self.f = f

    def __call__(self, p):
        return self.f(p)


def bumps(freq, seed, power=3.0):
    t = Tufts(freq, (0, 1, 0), seed=seed, n=14, stretch=0.0)
    return Fn(lambda p: t(p) ** power)


def build(name, body, origin=(0, 0, 0), tone=None, tint=None, axis=None, uv_scale=6.0, mat="creature",
          col=None, uv=None, budget=None, ao_field=None):
    """Mesh `body` with its pivot at `origin` (model coords), decimate, bake and link the object."""
    t = v3(origin)
    verts, quads = mesh_body(body, I3, t)
    me = bpy.data.meshes.new(name + "_raw")
    me.from_pydata(bl(verts).tolist(), [], quads.tolist())
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    tris = 2 * len(quads)
    budget = budget or body.budget
    if tris > budget:
        m = ob.modifiers.new("dec", "DECIMATE")
        m.ratio = budget / tris
        dg = bpy.context.evaluated_depsgraph_get()
        dme = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
        ob.modifiers.clear()
        ob.data = dme
        bpy.data.meshes.remove(me)
        me = dme
    me.name = name
    me.materials.clear()
    me.materials.append(name_material(mat))
    for poly in me.polygons:
        poly.use_smooth = True
    vb = np.array([tuple(v.co) for v in me.vertices])
    loc = np.stack([vb[:, 0], vb[:, 2], -vb[:, 1]], 1)
    ps = loc + t
    g = gradient(body.eval, ps)
    nrm = g / np.maximum(norm(g), 1e-9)[:, None]
    me.normals_split_custom_set_from_vertices(bl(nrm).tolist())
    field = ao_field or body.eval
    ao = 0.45 + 0.55 * ambient_occlusion(field, ps + nrm * 0.002, nrm, step=max(body.h * 2.2, 0.004), k=1.5)
    cen = np.array([ps[list(p.vertices)].mean(0) for p in me.polygons])
    _, freg = body.eval(cen, want_region=True)
    tn = tone(ps, nrm) if tone else np.full(len(ps), 0.5)
    ti = tint(ps, nrm) if tint else np.zeros(len(ps))
    if uv is not None:
        uu, vv = uv(ps, nrm)
    elif axis is not None:
        uu, vv = axis_uv(ps, axis)
        uu, vv = 16.0 + uu * uv_scale, 1.0 - vv * uv_scale
    else:
        uu, vv = ps[:, 0] * uv_scale, ps[:, 2] * uv_scale
    cols, uvs = [], []
    for poly in me.polygons:
        rg = int(freg[poly.index])
        for li in poly.loop_indices:
            vi = me.loops[li].vertex_index
            if col is not None:
                c = col(ps[vi], nrm[vi], ao[vi], rg)
                cols += [c[0], c[1], c[2], 1.0]
            else:
                cols += [rg / 16.0 + 1.0 / 32.0, ao[vi], float(np.clip(tn[vi], 0, 1)), float(np.clip(ti[vi], 0, 1))]
            uvs += [float(uu[vi]), float(vv[vi])]
    me.color_attributes.new("Col", "FLOAT_COLOR", "CORNER")
    me.color_attributes["Col"].data.foreach_set("color", cols)
    me.color_attributes.active_color = me.color_attributes["Col"]
    uvl = me.uv_layers.new(name="UVMap")
    uvl.data.foreach_set("uv", uvs)
    print(f"{name}: {len(me.polygons)} faces, {len(me.vertices)} verts")
    return ob


def P(x, y, z):
    return v3((x, y, z))


# ───────────────────────────────────────────────────────────────── hornet nest + snag
NEST_ATTACH = (1.22, 2.36, 0.1)  # model coords of the nest's top under the limb (oddities.rs NEST_AT)


def nest_snag():
    b = Body(h=0.022, budget=3200)
    trunk = [(P(0, -0.35, 0), 0.5), (P(0, 0.35, 0), 0.41), (P(0.04, 1.3, 0.02), 0.35), (P(0.08, 2.3, 0.0), 0.31),
             (P(0.04, 2.95, -0.04), 0.27)]
    b.add(Chain(trunk), MAIN)
    for k in range(6):
        a = k * math.tau / 6 + 0.4
        r = 0.95 + 0.25 * math.sin(k * 2.3)
        b.add(Cone(P(0, 0.35, 0), P(math.cos(a) * r, -0.22, math.sin(a) * r), 0.24, 0.07), MAIN, k=0.12)
    limb = [(P(0.12, 2.2, 0.0), 0.2), (P(0.7, 2.47, 0.06), 0.14), (P(1.3, 2.55, 0.11), 0.105), (P(1.75, 2.5, 0.16), 0.075)]
    b.add(Chain(limb), MAIN, k=0.1)
    # A short dead side stub and the snapped crown.
    b.add(Chain([(P(-0.05, 2.6, 0.0), 0.12), (P(-0.45, 2.95, -0.2), 0.07)]), MAIN, k=0.06)
    # Broken branch stubs all the way up: snapped short, a few with a splintered end.
    stubs = [((0.0, 1.05, 0.0), (-0.52, 1.32, 0.3), 0.09), ((0.0, 1.6, 0.0), (0.18, 1.85, -0.55), 0.08),
             ((0.0, 1.9, 0.0), (-0.6, 2.25, -0.12), 0.1), ((0.6, 2.42, 0.05), (0.85, 2.9, -0.2), 0.06),
             ((1.15, 2.53, 0.1), (1.3, 2.75, 0.45), 0.045), ((0.0, 0.75, 0.0), (0.35, 0.95, 0.42), 0.07)]
    for a0, a1, r in stubs:
        b.add(Cone(P(*a0), P(*a1), r, r * 0.55), MAIN, k=0.05)
        tip = P(*a1)
        b.add(Cone(tip, tip + (P(*a1) - P(*a0)) * 0.25 + P(0.02, 0.03, 0.0), r * 0.4, 0.008), MAIN, k=0.01)  # splinter
    b.cut(RBox(P(0, 1.2, 0), (4, 2.02, 4), rot=rot_z(0.18) @ rot_x(-0.1)), k=0.02)
    # The snapped crown: torn splinters standing proud of the break.
    srng = np.random.default_rng(13)
    for k in range(7):
        a = k * math.tau / 7 + srng.uniform(-0.3, 0.3)
        rr = 0.2 + srng.uniform(0, 0.06)
        base_y = 3.02 + 0.18 * math.sin(a) - 0.1 * math.cos(a)
        o = P(0.06 + math.cos(a) * rr, base_y - 0.12, -0.04 + math.sin(a) * rr)
        b.add(Cone(o, o + P(math.cos(a) * 0.04, srng.uniform(0.2, 0.55), math.sin(a) * 0.04), 0.05, 0.006), MAIN, k=0.02)
    b.sub(Ellipsoid(P(0.18, 1.15, 0.31), (0.1, 0.16, 0.12)), DETAIL, k=0.03)  # knot hole
    b.sub(Ellipsoid(P(0.05, 3.25, 0.0), (0.2, 0.25, 0.2)), DETAIL, k=0.05)  # rotten crown hollow
    bark = Tufts(14.0, (0, 1, 0), seed=7, n=14, stretch=0.96)
    b.shag(Sphere(P(0, 1.5, 0), 4.0), 0.05, Fn(lambda p: bark(p) ** 1.8), soft=0.1)  # deep oak furrows
    b.cut(Ground(-0.3))
    axis_t = [p for p, _ in trunk]
    axis_l = [p for p, _ in limb]

    def uv(ps, n):
        u1, v1 = axis_uv(ps, axis_t)
        u2, v2 = axis_uv(ps, axis_l)
        dt = np.min(np.stack([norm(ps - a) for a in axis_t]), 0)
        dl = np.min(np.stack([norm(ps - a) for a in axis_l]), 0)
        on_limb = (ps[:, 1] > 2.05) & (ps[:, 0] > 0.35)
        on_limb |= dl < dt * 0.7
        u = np.where(on_limb, u2, u1) / 0.75
        v = np.where(on_limb, v2, v1) / 1.1
        return u, v

    def col(p, n, ao, rg):
        moss = smoothstep(0.6, 0.0, p[1]) * 0.6 + 0.35 * max(0.0, n[2]) * smoothstep(2.4, 1.0, p[1])
        base = np.array([0.86, 0.83, 0.8]) * (0.5 + 0.5 * ao)
        green = np.array([0.55, 0.66, 0.36]) * (0.55 + 0.45 * ao)
        c = base * (1 - moss) + green * moss
        if rg == DETAIL:
            c = c * 0.35
        return c

    return build("odd_nest_snag", b, uv=uv, mat="bark_snag", col=col)  # weathered, bark-sloughing dead oak


def nest():
    """Paper nest hung from its top: a teardrop of scalloped paper bands, entrance at the bottom."""
    b = Body(h=0.008, budget=1400)
    b.add(Ellipsoid(P(0, -0.36, 0), (0.25, 0.36, 0.24)), MAIN)
    b.add(Ellipsoid(P(0, -0.12, 0), (0.16, 0.14, 0.15)), MAIN, k=0.08)
    b.add(Cone(P(0, -0.02, 0), P(0, 0.06, 0), 0.07, 0.05), MAIN, k=0.04)  # petiole wrapping the limb
    b.add(Cone(P(-0.12, 0.05, 0), P(0.12, 0.05, 0), 0.055, 0.055), DETAIL, k=0.02)  # the twig it hugs
    b.sub(Ellipsoid(P(0, -0.73, 0.02), (0.045, 0.05, 0.045)), DETAIL, k=0.02)  # entrance
    rng = np.random.default_rng(5)
    ph = rng.uniform(0, 6.28, 4)

    def scallop(p):
        a = np.arctan2(p[:, 2], p[:, 0])
        y = p[:, 1] + 0.012 * np.sin(a * 3 + ph[0]) + 0.008 * np.sin(a * 7 + ph[1])
        band = 0.5 + 0.5 * np.sin(y * 85.0 + 0.6 * np.sin(a * 2 + ph[2]))
        return band ** 2.5

    b.shag(Ellipsoid(P(0, -0.38, 0), (0.3, 0.42, 0.3)), 0.022, Fn(scallop), soft=0.03)

    def tone(ps, n):
        a = np.arctan2(ps[:, 2], ps[:, 0])
        s = np.sin(ps[:, 1] * 42.0 + 2.2 * np.sin(a * 2 + ph[3]) + 1.1 * np.sin(a * 5))
        return 0.45 + 0.3 * s + 0.15 * (n[:, 1])

    def tint(ps, n):
        return np.clip(0.4 * np.sin(ps[:, 1] * 19.0 + np.arctan2(ps[:, 2], ps[:, 0]) * 3.0), 0, 1)

    return build("odd_nest", b, tone=tone, tint=tint, uv_scale=8.0)


def hornet():
    b = Body(h=0.0018, budget=260)
    b.add(Ellipsoid(P(0, 0, -0.018), (0.009, 0.009, 0.016)), MAIN)  # abdomen
    b.add(Ellipsoid(P(0, 0.001, 0.004), (0.0065, 0.0065, 0.008)), DETAIL, k=0.002)  # thorax
    b.add(Sphere(P(0, 0.0, 0.015), 0.0055), ACCENT, k=0.002)  # head
    for s in (1, -1):
        b.add(Squash(Sphere(P(0, 0, 0), 1.0), P(s * 0.012, 0.007, -0.004), (0.011, 0.0012, 0.005), rot=rot_y(s * 0.5)), SKIN)

    def tone(ps, n):
        s = np.sin((ps[:, 2] + 0.03) * 520.0)
        return np.where(ps[:, 2] < -0.004, 0.5 + 0.5 * np.sign(s), 0.2)

    return build("odd_hornet", b, tone=tone, uv_scale=40.0)


# ───────────────────────────────────────────────────────────────── lantern toad
WARTS = bumps(46, 3, 4.5)


def toad_sdf():
    b = Body(h=0.0085, budget=4200)
    b.add(Ellipsoid(P(0, 0.23, -0.02), (0.29, 0.19, 0.34)), MAIN)
    b.add(Ellipsoid(P(0, 0.27, 0.25), (0.25, 0.14, 0.18)), MAIN, k=0.08)  # broad flat head
    b.add(Ellipsoid(P(0, 0.17, 0.34), (0.2, 0.08, 0.1)), SKIN, k=0.05)  # chin / lower jaw
    for s in (1, -1):
        b.add(Ellipsoid(P(s * 0.14, 0.37, 0.14), (0.075, 0.05, 0.12), rot=rot_y(s * 0.25)), ACCENT, k=0.04)  # parotoid
        b.add(Ellipsoid(P(s * 0.125, 0.385, 0.3), (0.075, 0.055, 0.07)), MAIN, k=0.035)  # brow ridge
        b.add(Sphere(P(s * 0.135, 0.415, 0.315), 0.058), EYE, k=0.006)
        b.add(Ellipsoid(P(s * 0.15, 0.425, 0.366), (0.024, 0.011, 0.012)), DETAIL, k=0.002)  # horizontal pupil
        # Front legs: shoulder -> elbow -> wrist, spread fingers.
        arm = [(P(s * 0.18, 0.22, 0.2), 0.07), (P(s * 0.27, 0.13, 0.27), 0.05), (P(s * 0.26, 0.035, 0.36), 0.04)]
        b.add(Chain(arm), MAIN, k=0.05)
        for f in range(4):
            a = s * (0.2 + f * 0.33)
            d = P(math.sin(a) * 0.08, -0.01, math.cos(a) * 0.08)
            b.add(Cone(P(s * 0.26, 0.03, 0.36), P(s * 0.26, 0.02, 0.36) + d, 0.022, 0.012), SKIN, k=0.012)
        # Hind legs folded beside the body: thigh, shin back, long foot forward.
        b.add(Ellipsoid(P(s * 0.25, 0.16, -0.14), (0.1, 0.1, 0.18), rot=rot_y(s * 0.35)), MAIN, k=0.06)
        b.add(Chain([(P(s * 0.31, 0.13, -0.01), 0.065), (P(s * 0.33, 0.06, -0.22), 0.045)]), MAIN, k=0.04)
        b.add(Cone(P(s * 0.33, 0.035, -0.24), P(s * 0.38, 0.025, -0.02), 0.04, 0.024), SKIN, k=0.03)
        for f in range(5):
            a = s * (-0.1 + f * 0.17)
            d = P(math.sin(a) * 0.1, -0.005, math.cos(a) * 0.1)
            b.add(Cone(P(s * 0.38, 0.024, -0.03), P(s * 0.38, 0.018, -0.03) + d, 0.016, 0.009), SKIN, k=0.01)
    b.sub(Ellipsoid(P(0, 0.25, 0.36), (0.235, 0.005, 0.13)), DETAIL, k=0.004)  # the long mouth line
    for s in (1, -1):
        b.sub(Sphere(P(s * 0.035, 0.305, 0.425), 0.008), DETAIL)  # nostrils
    b.shag(Ellipsoid(P(0, 0.26, 0.0), (0.33, 0.22, 0.42)), 0.02, WARTS, soft=0.02)
    b.shag(Ellipsoid(P(0, 0.37, 0.14), (0.25, 0.08, 0.16)), 0.01, bumps(110, 9, 2.0), soft=0.02)
    b.cut(Ground(0.0))
    return b


def toad():
    b = toad_sdf()
    blot = Tufts(16, (0, 0, 1), seed=11, n=10, stretch=0.2)

    def tone(ps, n):
        belly = smoothstep(0.0, -0.6, n[:, 1]) * smoothstep(0.2, 0.08, ps[:, 1])
        back = 0.42 - 0.3 * (blot(ps) > 0.55)
        return np.clip(back * (1 - belly) + 0.95 * belly, 0, 1)

    def tint(ps, n):
        warm = smoothstep(0.3, 0.7, Tufts(9, (0, 0, 1), seed=4, n=8)(ps))
        flank = smoothstep(0.1, 0.5, np.abs(n[:, 0]))
        return np.clip(0.55 * warm * flank + 0.7 * WARTS(ps), 0, 1)  # rusty wart tips

    return build("odd_toad_body", b, tone=tone, tint=tint, axis=[P(0, 0.3, 0.45), P(0, 0.25, -0.35)], uv_scale=7.0)


def toad_sac():
    b = Body(h=0.006, budget=700)
    c = P(0, 0.13, 0.33)
    b.add(Ellipsoid(c, (0.14, 0.1, 0.11)), MAIN)
    b.shag(Sphere(c, 0.2), 0.006, bumps(60, 21, 2.0), soft=0.02)

    def col(p, n, ao, rg):
        k = 0.65 + 0.35 * max(0.0, -n[1])
        return np.array([0.55, 1.0, 0.42]) * k * (0.7 + 0.3 * ao)

    return build("odd_toad_sac", b, origin=c, mat="glow", col=col)


# ───────────────────────────────────────────────────────────────── griffon vulture
def vulture_body():
    b = Body(h=0.008, budget=3600)
    pitch = rot_x(-0.12)
    b.add(Ellipsoid(P(0, 0.44, 0.0), (0.17, 0.145, 0.36), rot=pitch), MAIN)  # body
    b.add(Ellipsoid(P(0, 0.43, 0.15), (0.12, 0.115, 0.13)), MAIN, k=0.07)  # breast / crop
    # Tail: a short broad fan.
    b.add(Squash(Sphere(P(0, 0, 0), 1.0), P(0, 0.36, -0.37), (0.12, 0.022, 0.17), rot=rot_x(0.2)), MAIN, k=0.05)
    # The ruff: a fluffy collar of lanceolate feathers at the neck base.
    b.add(Ellipsoid(P(0, 0.56, 0.2), (0.15, 0.09, 0.11)), ACCENT, k=0.03)
    neck = [(P(0, 0.56, 0.22), 0.042), (P(0, 0.66, 0.31), 0.03), (P(0, 0.69, 0.4), 0.034)]
    b.add(Chain(neck), SKIN, k=0.025)
    b.add(Ellipsoid(P(0, 0.7, 0.45), (0.045, 0.043, 0.06)), SKIN, k=0.02)  # head
    b.add(Cone(P(0, 0.698, 0.49), P(0, 0.688, 0.565), 0.027, 0.016), HORN, k=0.008)  # bill
    b.add(Cone(P(0, 0.688, 0.565), P(0, 0.664, 0.583), 0.016, 0.004), HORN, k=0.006)  # hook
    b.add(Ellipsoid(P(0, 0.684, 0.53), (0.022, 0.012, 0.03)), DETAIL, k=0.006)  # cere / gape
    for s in (1, -1):
        b.add(Sphere(P(s * 0.033, 0.712, 0.475), 0.011), EYE, k=0.003)
        b.add(Ellipsoid(P(s * 0.11, 0.48, -0.03), (0.06, 0.1, 0.24), rot=rot_x(-0.3)), MAIN, k=0.05)  # wing shoulder
    ruff = Tufts(30, (0, 1, -1), seed=17, n=12, stretch=0.6)
    b.shag(Ellipsoid(P(0, 0.56, 0.2), (0.17, 0.1, 0.13)), 0.03, ruff, soft=0.03)
    feathers = Tufts(18, (0, 0, -1), seed=12, n=10, stretch=0.85)
    b.shag(Ellipsoid(P(0, 0.42, -0.05), (0.2, 0.2, 0.45)), 0.008, feathers, soft=0.03)
    down = Tufts(60, (0, 0, -1), seed=3, n=8, stretch=0.3)
    b.shag(Ellipsoid(P(0, 0.67, 0.38), (0.06, 0.08, 0.13)), 0.003, down, soft=0.01)

    def tone(ps, n):
        belly = smoothstep(0.1, -0.6, n[:, 1])
        tail = smoothstep(-0.25, -0.38, ps[:, 2])
        return np.clip(0.55 + 0.25 * belly - 0.45 * tail + 0.1 * (feathers(ps) - 0.5), 0, 1)

    return build("odd_vulture_body", b, tone=tone, axis=[P(0, 0.62, 0.35), P(0, 0.44, 0.0), P(0, 0.36, -0.5)], uv_scale=5.0)


def vulture_wing():
    """Left wing, spread (soaring), shoulder pivot at the origin; span ~0.95 out along +X."""
    b = Body(h=0.007, budget=2600)
    th = 0.03
    arm = [(P(0.0, 0.0, 0.05), 0.045), (P(0.36, 0.01, 0.09), 0.032), (P(0.6, 0.0, 0.05), 0.022)]
    b.add(Chain(arm), MAIN)
    b.add(Squash(Sphere(P(0, 0, 0), 1.0), P(0.3, 0.0, -0.1), (0.34, th, 0.21)), MAIN, k=0.03)  # secondaries
    b.add(Squash(Sphere(P(0, 0, 0), 1.0), P(0.58, 0.0, -0.05), (0.15, th * 0.9, 0.15)), MAIN, k=0.03)  # hand
    # Primaries: six slotted "fingers" splaying from the hand.
    for k in range(7):
        a = -0.62 + k * 0.19
        root = P(0.62, 0.006 * k, 0.04 - k * 0.024)
        tip = root + P(math.cos(a) * (0.36 - abs(k - 3) * 0.022), 0.014 * k, math.sin(a) * 0.36)
        L = float(np.hypot((tip - root)[0], (tip - root)[2]))
        b.add(Squash(Cone(P(0, 0, 0), P(1, 0, 0), 1.0, 0.3), root, (L, 0.016, 0.04), rot=rot_y(-a)), MAIN, k=0.008)
    # Overlapping covert rows: shingled ridges across the inner wing.
    rows = Fn(lambda p: (0.5 + 0.5 * np.sin(p[:, 2] * 62.0 + p[:, 0] * 6.0)) ** 3)
    b.shag(Squash(Sphere(P(0, 0, 0), 1.0), P(0.3, 0.02, -0.02), (0.36, 0.06, 0.16)), 0.009, rows, soft=0.03)
    serr = Tufts(40, (0, 0, -1), seed=8, n=10, stretch=0.95)
    b.shag(Squash(Sphere(P(0, 0, 0), 1.0), P(0.35, 0, -0.17), (0.38, 0.05, 0.08)), 0.008, serr, soft=0.02)

    def tone(ps, n):
        trailing = smoothstep(-0.02, -0.14, ps[:, 2])
        prim = smoothstep(0.62, 0.72, ps[:, 0])
        under = smoothstep(0.2, -0.6, n[:, 1])
        rows = 0.06 * np.sin(ps[:, 2] * 70.0 + ps[:, 0] * 9.0)  # covert rows
        return np.clip(0.74 + rows - 0.7 * np.maximum(trailing, prim) - 0.12 * under, 0, 1)

    return build("odd_vulture_wing", b, tone=tone, axis=[P(0, 0, 0.1), P(0, 0, -0.3)], uv_scale=5.0)


def vulture_legs():
    b = Body(h=0.006, budget=1600)
    for s in (1, -1):
        b.add(Ellipsoid(P(s * 0.075, 0.3, 0.03), (0.05, 0.08, 0.06)), MAIN)  # feathered "trousers"
        b.add(Chain([(P(s * 0.08, 0.26, 0.04), 0.024), (P(s * 0.085, 0.05, 0.06), 0.018)]), SKIN, k=0.015)
        for k in range(3):
            a = s * (-0.35 + k * 0.35)
            d = P(math.sin(a) * 0.075, -0.03, math.cos(a) * 0.075)
            o = P(s * 0.085, 0.035, 0.06)
            b.add(Cone(o, o + d, 0.013, 0.009), SKIN, k=0.008)
            b.add(Cone(o + d, o + d * 1.25 + P(0, -0.012, 0), 0.008, 0.002), DETAIL, k=0.002)
        o = P(s * 0.085, 0.035, 0.06)
        b.add(Cone(o, o + P(0, -0.02, -0.05), 0.011, 0.003), DETAIL, k=0.005)
    b.cut(Ground(0.0))
    return build("odd_vulture_legs", b, tone=lambda p, n: np.full(len(p), 0.45))


# ───────────────────────────────────────────────────────────────── antlion
def antlion_head():
    b = Body(h=0.012, budget=3000)
    b.add(Squash(Sphere(P(0, 0, 0), 1.0), P(0, 0.16, 0.05), (0.21, 0.09, 0.19)), MAIN)  # flat square head
    b.add(Ellipsoid(P(0, 0.12, -0.24), (0.3, 0.13, 0.2)), MAIN, k=0.06)  # thorax
    b.add(Ellipsoid(P(0, 0.06, -0.6), (0.42, 0.16, 0.36)), MAIN, k=0.08)  # abdomen (mostly in the sand)
    for s in (1, -1):
        for k in range(3):  # stemmata on little eye turrets
            b.add(Sphere(P(s * (0.16 + 0.02 * k), 0.21, 0.1 - 0.035 * k), 0.022), EYE, k=0.01)
        b.add(Cone(P(s * 0.2, 0.15, 0.16), P(s * 0.25, 0.17, 0.32), 0.02, 0.012), DETAIL, k=0.01)  # palp
        for k in range(3):  # stubby legs half dug in
            z = -0.15 - k * 0.12
            b.add(Chain([(P(s * 0.25, 0.1, z), 0.035), (P(s * 0.42, 0.08, z + 0.05), 0.025),
                         (P(s * 0.5, -0.02, z + 0.08), 0.015)]), SKIN, k=0.02)
    bristle = Tufts(34, (0, 0, -1), seed=23, n=14, stretch=0.4)
    b.shag(Ellipsoid(P(0, 0.08, -0.45), (0.48, 0.22, 0.5)), 0.022, Fn(lambda p: bristle(p) ** 2.5), soft=0.03)
    b.shag(Squash(Sphere(P(0, 0, 0), 1.0), P(0, 0.17, 0.05), (0.23, 0.1, 0.21)), 0.006, bumps(70, 31, 2.0), soft=0.02)
    b.cut(Ground(-0.04))
    spots = Tufts(14, (0, 0, -1), seed=19, n=10, stretch=0.3)

    def tone(ps, n):
        return np.clip(0.55 - 0.45 * (spots(ps) > 0.6) + 0.15 * n[:, 1], 0, 1)

    return build("odd_antlion_head", b, tone=tone, axis=[P(0, 0.15, 0.3), P(0, 0.08, -0.9)], uv_scale=5.0)


JAW_PIVOT = (0.12, 0.15, 0.2)


def antlion_jaw():
    b = Body(h=0.006, budget=1200)
    o = P(*JAW_PIVOT)
    knots = [(o, 0.04), (o + P(0.09, 0.0, 0.2), 0.032), (o + P(0.07, 0.01, 0.42), 0.024), (o + P(-0.02, 0.01, 0.56), 0.013),
             (o + P(-0.1, 0.0, 0.6), 0.003)]
    b.add(Chain(knots), MAIN)
    for k, (z, l) in enumerate(((0.16, 0.07), (0.27, 0.08), (0.37, 0.065))):
        root = o + P(0.08 - k * 0.005, 0.0, z)
        b.add(Cone(root, root + P(-l, 0.0, 0.02), 0.014, 0.002), HORN, k=0.008)

    def tone(ps, n):
        return np.clip(0.65 - 0.65 * smoothstep(0.35, 0.55, ps[:, 2] - o[2]), 0, 1)

    return build("odd_antlion_jaw", b, origin=JAW_PIVOT, tone=tone, tint=lambda p, n: np.full(len(p), 0.6),
                 axis=[o, o + P(0, 0, 0.6)], uv_scale=8.0)


def antlion_pit():
    """The sand funnel as one heightfield disc (s_plaster tinted to the dune sand)."""
    from meshkit import Builder
    from mathutils import Vector
    rng = np.random.default_rng(41)
    rings, seg = 26, 56
    R_RIM, R_OUT = 3.7, 6.2
    ph = rng.uniform(0, 6.28, 6)

    def h(r, a):
        wob = 0.05 * math.sin(a * 3 + ph[0]) + 0.03 * math.sin(a * 7 + ph[1])
        if r <= R_RIM:
            t = r / R_RIM
            y = -0.32 + 0.6 * t ** 1.3  # shallow: the game seats the floor just above the ground
            y += 0.025 * math.sin(r * 9.0 + a * 2 + ph[2]) * t  # slumped sand runnels
        else:
            t = min(1.0, (r - R_RIM) / (R_OUT - R_RIM))
            # The spoil apron dives under the ground so it never ends in a floating lip.
            y = 0.28 * (1 - t) ** 1.4 - 0.9 * t ** 1.2
            if r > R_OUT:
                y = -1.4  # buried skirt
        return y + wob * min(1.0, r / 2.0)

    bld = Builder()
    pts, uvs, cols, nrm = [], [], [], []
    for i in range(rings + 2):
        r = R_OUT * (i / rings) ** 0.85 if i <= rings else R_OUT + 0.05
        for j in range(seg):
            a = math.tau * j / seg
            y = h(r, a)
            pts.append((math.cos(a) * r, y, math.sin(a) * r))
    pts = np.array(pts)

    def idx(i, j):
        return i * seg + (j % seg)

    # Normals by finite differences.
    def normal(i, j):
        p = pts[idx(i, j)]
        a = pts[idx(min(i + 1, rings), j)] - pts[idx(max(i - 1, 0), j)]
        if i > rings:
            a = pts[idx(rings, j)] - pts[idx(rings - 1, j)]
        b = pts[idx(i, j + 1)] - pts[idx(i, j - 1)]
        n = np.cross(b, a) if i > 0 else np.array([0, 1.0, 0])
        if n[1] < 0:
            n = -n
        return n / max(np.linalg.norm(n), 1e-9)

    vid = [bld.v((p[0], -p[2], p[1])) for p in pts]
    for i in range(rings + 1):
        for j in range(seg):
            q = [idx(i, j), idx(i, j + 1), idx(i + 1, j + 1), idx(i + 1, j)]
            uv_, n_, c_ = [], [], []
            for k in q:
                ii, jj = divmod(k, seg)
                p = pts[k]
                uv_.append((p[0] / 1.6, p[2] / 1.6))
                n = normal(ii, jj)
                n_.append((n[0], -n[2], n[1]))
                r = math.hypot(p[0], p[2])
                a = math.atan2(p[2], p[0])
                t = min(1.0, r / R_RIM)
                shade = 0.34 + 0.66 * t ** 1.6  # the funnel floor sits in its own shadow
                shade *= 1.0 + 0.12 * math.sin(a * 23.0 + 3.0 * math.sin(a * 5.0 + ph[3])) * t  # slip runnels
                shade *= 1.0 + 0.16 * math.exp(-((r - R_RIM + 0.1) / 0.35) ** 2)  # dry pale lip
                if r < 0.55:
                    shade *= 0.55 + 0.45 * r / 0.55  # the burrow mouth
                c_.append(tuple(min(1.0, v * shade) for v in (0.95, 0.78, 0.46)))  # the dune sand's ochre
            bld.face([vid[k] for k in q], uv_, n_, c_, 0)  # q runs CCW seen from above: faces up
    return bld.build("odd_antlion_pit", ["s_plaster"])  # fine, pale grain tinted to sand


# ───────────────────────────────────────────────────────────────── wolverine
# A low, long, heavy mustelid: arched back, short thick legs, big paws, a broad bear-like head with
# small round ears, a bushy tail; dark chocolate coat with the pale buff side stripe running from the
# shoulder to the tail root and a pale brow band. Body ~0.95 long, 0.42 at the hump (real scale).
WOLV_SHOULDER = (0.115, 0.29, 0.25)  # left front-leg pivot (oddities.rs mirrors x for the right)
WOLV_HIP = (0.12, 0.31, -0.3)
WOLV_TAIL = (0.0, 0.36, -0.47)
WOLV_FUR = Tufts(34, (0, 0, -1), seed=29, n=12, stretch=0.7)


def wolv_stripe(ps, n):
    """0..1 on the pale band: a curve along each flank from the shoulder, rising over the hips."""
    z = ps[:, 2]
    along = smoothstep(0.3, 0.16, z) * smoothstep(-0.56, -0.38, z)
    centre = 0.3 + 0.07 * smoothstep(0.2, -0.45, z)
    band = np.exp(-((ps[:, 1] - centre) / 0.045) ** 2)
    side = smoothstep(0.25, 0.6, np.abs(n[:, 0]))
    over_rump = smoothstep(-0.36, -0.46, z) * smoothstep(0.28, 0.36, ps[:, 1])  # the bands meet over the tail root
    return np.clip(np.maximum(band * side, over_rump) * along, 0, 1)


def wolverine_body():
    b = Body(h=0.009, budget=5200)
    b.add(Ellipsoid(P(0, 0.31, 0.12), (0.15, 0.13, 0.22)), MAIN)  # chest / shoulders
    b.add(Ellipsoid(P(0, 0.33, -0.2), (0.16, 0.14, 0.27)), MAIN, k=0.1)  # arched loin and hips
    b.add(Ellipsoid(P(0, 0.31, 0.34), (0.105, 0.1, 0.1)), MAIN, k=0.07)  # thick neck
    b.add(Ellipsoid(P(0, 0.31, 0.45), (0.105, 0.085, 0.09)), MAIN, k=0.05)  # broad skull
    b.add(Ellipsoid(P(0, 0.275, 0.55), (0.06, 0.055, 0.07)), SKIN, k=0.04)  # short muzzle
    b.add(Sphere(P(0, 0.29, 0.615), 0.021), DETAIL, k=0.006)  # nose
    for s in (1, -1):
        b.add(Squash(Sphere(P(0, 0, 0), 1.0), P(s * 0.085, 0.385, 0.42), (0.035, 0.03, 0.016), rot=rot_z(s * 0.4)), MAIN, k=0.02)  # ear
        b.add(Sphere(P(s * 0.05, 0.325, 0.53), 0.014), EYE, k=0.003)
        b.add(Ellipsoid(P(s * 0.11, 0.25, 0.2), (0.06, 0.09, 0.08)), MAIN, k=0.05)  # shoulder mass
        b.add(Ellipsoid(P(s * 0.12, 0.27, -0.3), (0.07, 0.1, 0.11)), MAIN, k=0.05)  # haunch
    b.shag(Ellipsoid(P(0, 0.3, -0.05), (0.2, 0.19, 0.5)), 0.022, WOLV_FUR, soft=0.04)
    b.shag(Ellipsoid(P(0, 0.2, -0.05), (0.17, 0.08, 0.4)), 0.03, Tufts(26, (0, -1, 0), seed=31, n=10, stretch=0.8), soft=0.03)  # belly fringe

    def tone(ps, n):
        brow = np.exp(-((ps[:, 2] - 0.47) / 0.035) ** 2) * smoothstep(0.31, 0.36, ps[:, 1])  # pale brow band
        face = smoothstep(0.5, 0.58, ps[:, 2])
        legs_low = smoothstep(0.22, 0.14, ps[:, 1])
        base = 0.4 + 0.1 * (WOLV_FUR(ps) - 0.5) - 0.3 * legs_low - 0.25 * face
        return np.clip(base + 0.62 * wolv_stripe(ps, n) + 0.45 * brow, 0, 1)

    def tint(ps, n):
        return 0.5 * wolv_stripe(ps, n)

    return build("odd_wolv_body", b, tone=tone, tint=tint, axis=[P(0, 0.31, 0.6), P(0, 0.33, -0.5)], uv_scale=6.0)


def wolverine_leg(front):
    piv = WOLV_SHOULDER if front else WOLV_HIP
    o = P(*piv)
    b = Body(h=0.007, budget=1500)
    if front:
        b.add(Chain([(o, 0.06), (o + P(0.005, -0.15, 0.02), 0.047), (o + P(0.0, -0.265, 0.03), 0.04)]), MAIN, k=0.03)
        paw = o + P(0.0, -0.272, 0.06)
    else:
        b.add(Chain([(o, 0.07), (o + P(0.0, -0.13, -0.05), 0.05), (o + P(0.0, -0.29, -0.02), 0.04)]), MAIN, k=0.03)
        paw = o + P(0.0, -0.292, 0.03)
    b.add(Ellipsoid(paw, (0.05, 0.026, 0.065)), MAIN, k=0.025)  # broad snowshoe paw
    for k in range(5):  # pale, half-retractile claws
        a = -0.5 + k * 0.25
        c = paw + P(math.sin(a) * 0.035, -0.008, 0.055 + 0.01 * math.cos(a))
        b.add(Cone(c, c + P(math.sin(a) * 0.01, -0.018, 0.028), 0.007, 0.002), HORN, k=0.004)
    b.shag(Sphere(o + P(0, -0.1, 0), 0.16), 0.014, WOLV_FUR, soft=0.03)
    b.cut(Ground(0.0))
    tone = lambda ps, n: np.clip(0.12 + 0.12 * smoothstep(piv[1] - 0.12, piv[1], ps[:, 1]), 0, 1)
    return build("odd_wolv_leg_f" if front else "odd_wolv_leg_h", b, origin=piv, tone=tone,
                 axis=[o, o + P(0, -0.3, 0)], uv_scale=8.0)


def wolverine_tail():
    o = P(*WOLV_TAIL)
    b = Body(h=0.007, budget=1300)
    b.add(Chain([(o, 0.05), (o + P(0, -0.04, -0.13), 0.075), (o + P(0, -0.1, -0.28), 0.06), (o + P(0, -0.15, -0.36), 0.03)]), MAIN, k=0.04)
    b.shag(Sphere(o + P(0, -0.07, -0.18), 0.25), 0.03, Tufts(30, (0, -0.4, -1), seed=37, n=12, stretch=0.85), soft=0.03)
    tone = lambda ps, n: np.clip(0.18 + 0.4 * smoothstep(-0.52, -0.47, ps[:, 2]) * smoothstep(0.33, 0.37, ps[:, 1]), 0, 1)
    return build("odd_wolv_tail", b, origin=WOLV_TAIL, tone=tone, axis=[o, o + P(0, -0.15, -0.36)], uv_scale=6.0)


if __name__ == "__main__":
    clear_scene()
    only = set(sys.argv[sys.argv.index("--") + 1:]) if "--" in sys.argv else set()
    makers = [nest_snag, nest, hornet, toad, toad_sac, vulture_body, vulture_wing, vulture_legs, antlion_head, antlion_jaw,
              antlion_pit, wolverine_body, lambda: wolverine_leg(True), lambda: wolverine_leg(False), wolverine_tail]
    objs = [m() for m in makers]
    export_glb(OUT / "oddities.glb", objs)
    print("ODDITIES_DONE")
