"""Organic ork body parts for the shared biped rig -> creatures.glb.

The game animates bipeds as a joint hierarchy (biped.rs) with one mesh per joint, authored in that
joint's local frame (game coords: Y up, +Z forward; arms / legs hang down -Y from their joint).
These replace the box-built ork parts (orks.rs `ork_biped_meshes`) one-for-one, so every clip
keeps working. Shapes are metaballs (fused muscle masses), polygonised and decimated per part.

Vertex colour R carries a REGION code (region / 16 + 1/32) that the game maps to the variant's
skin, the faction cloth, leather, bone, iron ... and the creature shader's surface code; G is a
baked cavity term (darker in creases, from the metaball field) used as a colour multiplier.
"""
import math
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402
from common import OUT, clear_scene, export_glb, name_material  # noqa: E402

SKIN, DARK, BELLY, LEATHER, CLOTH, BONE, HAIR, WOOD, IRON, ORB = range(10)
K = 1.0 / 0.575  # metaball radius -> surface radius (measured: r=1 BALL surfaces at 0.575)


def bl(p):
    return Vector((p[0], -p[2], p[1]))


class Part:
    def __init__(self, name):
        self.name = name
        self.groups = {}  # region -> list of element specs

    def _add(self, region, spec):
        self.groups.setdefault(region, []).append(spec)

    def ball(self, region, c, r, stiff=2.0):
        self._add(region, ("BALL", c, r, None, None, stiff))

    def ell(self, region, c, radii, rot=None, stiff=2.0):
        self._add(region, ("ELLIPSOID", c, 1.0, radii, rot, stiff))

    def cap(self, region, a, b, r, stiff=2.0):
        self._add(region, ("CAPSULE", a, r, b, None, stiff))


def make_metaball(name, specs, res):
    mb = bpy.data.metaballs.new(name)
    mb.resolution = res
    mb.threshold = 0.6
    ob = bpy.data.objects.new(name, mb)
    bpy.context.scene.collection.objects.link(ob)
    for kind, c, r, extra, rot, stiff in specs:
        e = mb.elements.new()
        e.stiffness = stiff
        if kind == "BALL":
            e.type = "BALL"
            e.co = bl(c)
            e.radius = r * K
        elif kind == "ELLIPSOID":
            e.type = "ELLIPSOID"
            e.co = bl(c)
            e.radius = K
            # radii are game (x, y, z) -> Blender (x, z, y) axes
            e.size_x, e.size_y, e.size_z = extra[0], extra[2], extra[1]
            if rot is not None:
                e.rotation = rot
        else:  # CAPSULE between a and b (game coords)
            a, b = bl(c), bl(extra)
            d = b - a
            e.type = "CAPSULE"
            e.co = (a + b) / 2
            e.radius = r * K
            e.size_x = max(d.length / 2, 1e-4)
            e.rotation = Vector((1, 0, 0)).rotation_difference(d.normalized())
    return ob


def build_part(part, target_tris, res=0.012):
    dg = bpy.context.evaluated_depsgraph_get()
    pieces = []
    for region, specs in part.groups.items():
        ob = make_metaball(f"{part.name}_{region}", specs, res)
        dg.update()
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
        bpy.data.objects.remove(ob)
        pieces.append((region, me))
    # Join into one mesh with a per-corner region colour.
    verts, faces, regs = [], [], []
    for region, me in pieces:
        base = len(verts)
        verts += [v.co.copy() for v in me.vertices]
        for p in me.polygons:
            faces.append([base + i for i in p.vertices])
            regs.append(region)
        bpy.data.meshes.remove(me)
    me = bpy.data.meshes.new(part.name)
    me.from_pydata(verts, [], faces)
    me.materials.append(name_material("creature"))
    me.attributes.new("reg", "FLOAT", "FACE").data.foreach_set("value", [float(r) for r in regs])
    ob = bpy.data.objects.new(part.name, me)
    bpy.context.scene.collection.objects.link(ob)
    # Decimate to budget (planar-friendly collapse), then smooth shading.
    tris = sum(len(f) - 2 for f in faces)
    if tris > target_tris:
        m = ob.modifiers.new("dec", "DECIMATE")
        m.ratio = target_tris / tris
        dg = bpy.context.evaluated_depsgraph_get()
        dme = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
        ob.modifiers.clear()
        old = ob.data
        ob.data = dme
        bpy.data.meshes.remove(old)
        dme.materials.clear()
        dme.materials.append(name_material("creature"))
    me = ob.data
    for p in me.polygons:
        p.use_smooth = True
    # Region (+ a cavity term from vertex concavity) into a corner colour.
    me.color_attributes.new("Col", "FLOAT_COLOR", "CORNER")
    reg_attr = me.attributes.get("reg")
    face_reg = [0.0] * len(me.polygons)
    if reg_attr is not None:
        reg_attr.data.foreach_get("value", face_reg)
    # Cavity: vertex normal vs. average neighbour direction (cheap crease darkening).
    nb = [[] for _ in me.vertices]
    for e in me.edges:
        a, b = e.vertices
        nb[a].append(b)
        nb[b].append(a)
    cav = []
    for i, v in enumerate(me.vertices):
        if not nb[i]:
            cav.append(1.0)
            continue
        avg = sum((me.vertices[j].co for j in nb[i]), Vector()) / len(nb[i])
        conc = (avg - v.co).dot(v.normal)
        cav.append(max(0.55, min(1.0, 1.0 - conc * 18.0)))
    cols = []
    for p in me.polygons:
        r = int(round(face_reg[p.index]))
        for li in p.loop_indices:
            vi = me.loops[li].vertex_index
            cols += [r / 16.0 + 1.0 / 32.0, cav[vi], 1.0, 1.0]
    me.color_attributes["Col"].data.foreach_set("color", cols)
    me.color_attributes.active_color = me.color_attributes["Col"]
    return ob


# ─────────────────────────────────────────────────────────────── ork parts
def hips():
    p = Part("ork_hips")
    p.ell(CLOTH, (0, -0.05, 0), (0.23, 0.1, 0.16))
    p.ell(LEATHER, (0, 0.03, 0.005), (0.255, 0.045, 0.185))
    p.ell(CLOTH, (0, -0.16, 0.14), (0.11, 0.12, 0.025))
    p.ell(CLOTH, (0, -0.15, -0.13), (0.12, 0.11, 0.025))
    p.ball(BONE, (0.0, 0.03, 0.19), 0.035)  # belt skull boss
    return p, 700


def torso():
    p = Part("ork_torso")
    # Heavy chest, gut and shoulder girdle fused into one mass.
    p.ell(SKIN, (0, 0.2, 0.02), (0.29, 0.16, 0.18))
    p.ell(SKIN, (0, 0.05, 0.05), (0.23, 0.13, 0.17))
    for sx in (-1, 1):
        p.ball(SKIN, (sx * 0.11, 0.23, 0.12), 0.1)  # pecs
        p.cap(SKIN, (sx * 0.08, 0.34, -0.03), (sx * 0.3, 0.29, -0.02), 0.08)  # traps
        p.ball(SKIN, (sx * 0.31, 0.26, 0.0), 0.105)  # deltoid root
        p.ball(SKIN, (sx * 0.13, 0.15, -0.12), 0.1)  # lats
    p.ell(BELLY, (0, 0.06, 0.16), (0.16, 0.1, 0.05))
    # Leather chest strap + bone tooth necklace.
    for k in range(9):
        t = k / 8
        a = Vector((-0.27, 0.31, 0.12)).lerp(Vector((0.21, 0.0, 0.2)), t)
        a.z = 0.13 + 0.09 * math.sin(math.pi * t) + 0.02
        p.ball(LEATHER, tuple(a), 0.032)
    for k, x in enumerate((-0.09, -0.045, 0.0, 0.045, 0.09)):
        y = 0.27 - (2 - abs(k - 2)) * 0.012
        p.cap(BONE, (x, y, 0.2), (x * 1.1, y - 0.06, 0.205), 0.012)
    return p, 1300


def neck():
    p = Part("ork_neck")
    p.cap(SKIN, (0, -0.06, 0), (0, 0.06, 0.02), 0.1)
    return p, 300


def head(variant):
    p = Part(f"ork_head_{variant}")
    p.ell(SKIN, (0, 0.07, -0.01), (0.125, 0.13, 0.135))
    p.cap(SKIN, (-0.095, 0.125, 0.105), (0.095, 0.125, 0.105), 0.038)  # brow ridge
    p.ell(SKIN, (0, -0.035, 0.07), (0.125, 0.07, 0.1))  # heavy jaw
    for sx in (-1, 1):
        p.ball(SKIN, (sx * 0.08, 0.04, 0.1), 0.05)  # cheekbones
        p.cap(SKIN, (sx * 0.115, 0.075, -0.015), (sx * 0.22, 0.135, -0.06), 0.022)  # long ears
        p.ball(DARK, (sx * 0.052, 0.085, 0.118), 0.026)  # eye sockets
        p.cap(BONE, (sx * 0.06, -0.05, 0.155), (sx * 0.078, 0.045, 0.19), 0.016)  # tusks
    p.ell(SKIN, (0, 0.055, 0.145), (0.032, 0.03, 0.03))  # flat nose
    p.cap(DARK, (-0.05, -0.0, 0.158), (0.05, -0.0, 0.158), 0.008)  # mouth line
    if variant == "grunt":
        p.cap(HAIR, (0, 0.18, -0.05), (0, 0.27, -0.08), 0.035)
        p.ball(HAIR, (0, 0.29, -0.09), 0.045)
    elif variant == "scout":
        p.ell(CLOTH, (0, 0.13, 0.0), (0.145, 0.028, 0.152))
        p.cap(BONE, (0.12, 0.15, -0.05), (0.16, 0.3, -0.1), 0.012)
    elif variant == "berserker":
        for k in range(6):
            z = 0.1 - k * 0.045
            p.ell(CLOTH, (0, 0.2 + 0.02 * math.sin(k), z), (0.022, 0.06, 0.03))
        for sx in (-1, 1):
            p.ell(CLOTH, (sx * 0.09, 0.02, 0.135), (0.015, 0.05, 0.01))
    elif variant == "shaman":
        p.ell(BONE, (0, 0.17, 0.0), (0.14, 0.06, 0.15))
        for sx in (-1, 1):
            p.cap(BONE, (sx * 0.1, 0.2, 0.0), (sx * 0.2, 0.33, -0.05), 0.025)
        p.ball(DARK, (0, 0.17, 0.14), 0.03)
    return p, 1200


def upper_arm():
    p = Part("ork_upper_arm")
    p.ball(SKIN, (0, 0.0, 0.0), 0.12)
    p.cap(SKIN, (0, -0.02, 0), (0, -0.31, 0.0), 0.09)
    p.ball(SKIN, (0, -0.13, 0.045), 0.085)  # bicep
    p.ball(SKIN, (0, -0.12, -0.04), 0.08)  # tricep
    p.ell(LEATHER, (0, 0.06, 0), (0.155, 0.065, 0.145))  # shoulder pad
    p.ball(BONE, (0.0, 0.12, -0.02), 0.03)  # pad spike knob
    return p, 800


def forearm():
    p = Part("ork_forearm")
    p.cap(SKIN, (0, 0.05, 0), (0, -0.2, 0.0), 0.08)  # reaches up into the elbow: no gap when bent
    p.ball(SKIN, (0, 0.0, 0), 0.085)
    p.ball(SKIN, (0, -0.05, 0.02), 0.09)
    p.ell(LEATHER, (0, -0.14, 0), (0.092, 0.075, 0.092))  # bracer
    p.ell(SKIN, (0, -0.25, 0.012), (0.072, 0.068, 0.085))  # fist
    for k in range(4):
        p.ball(SKIN, (-0.045 + k * 0.03, -0.275, 0.07), 0.022)  # knuckles
    return p, 700


def thigh():
    p = Part("ork_thigh")
    p.cap(SKIN, (0, 0.04, 0), (0, -0.41, 0.01), 0.112)
    p.ball(SKIN, (0, -0.13, 0.05), 0.105)
    p.ell(CLOTH, (0, -0.07, 0), (0.135, 0.1, 0.135))
    return p, 700


def shin():
    p = Part("ork_shin")
    p.cap(SKIN, (0, 0.05, 0), (0, -0.43, 0), 0.085)
    p.ball(SKIN, (0, 0.0, 0), 0.095)
    p.ball(SKIN, (0, -0.1, -0.04), 0.09)  # calf
    p.ball(SKIN, (0, 0.0, 0.05), 0.06)  # kneecap
    p.ell(LEATHER, (0, -0.24, 0), (0.098, 0.1, 0.098))  # wrap
    return p, 600


def foot():
    p = Part("ork_foot")
    p.ell(LEATHER, (0, -0.04, 0.05), (0.1, 0.068, 0.15))
    p.ell(LEATHER, (0, -0.06, 0.16), (0.09, 0.048, 0.07))
    p.ell(LEATHER, (0, 0.03, 0.0), (0.085, 0.07, 0.085))
    return p, 400


def club():
    p = Part("ork_club")
    p.cap(LEATHER, (0, -0.12, 0), (0, 0.08, 0), 0.032)
    p.cap(WOOD, (0, 0.05, 0), (0, 0.2, 0), 0.04)
    p.ell(WOOD, (0, 0.33, 0), (0.08, 0.2, 0.08))
    for k in range(6):
        a = k / 6 * 2 * math.pi
        y = 0.28 + (k % 2) * 0.1
        p.cap(IRON, (math.cos(a) * 0.06, y, math.sin(a) * 0.06), (math.cos(a) * 0.14, y + 0.02, math.sin(a) * 0.14), 0.015)
    return p, 500


def staff():
    p = Part("ork_staff")
    p.cap(WOOD, (0, -0.4, 0), (0, 0.55, 0), 0.03)
    p.cap(LEATHER, (0, -0.2, 0), (0, -0.08, 0), 0.036)
    p.ball(ORB, (0, 0.63, 0), 0.085)
    for sx in (-1, 1):
        p.cap(BONE, (sx * 0.03, 0.52, 0), (sx * 0.075, 0.68, 0), 0.016)
    return p, 500


def shield():
    p = Part("ork_shield")
    p.ell(WOOD, (0, 0, 0), (0.26, 0.26, 0.03))
    p.ball(IRON, (0, 0, 0.035), 0.06)
    for k in range(14):
        a = k / 14 * 2 * math.pi
        a2 = (k + 1) / 14 * 2 * math.pi
        p.cap(IRON, (math.cos(a) * 0.255, math.sin(a) * 0.255, 0.0), (math.cos(a2) * 0.255, math.sin(a2) * 0.255, 0.0), 0.02)
    for k in range(4):
        a = k / 4 * 2 * math.pi + 0.785
        p.ball(IRON, (math.cos(a) * 0.17, math.sin(a) * 0.17, 0.03), 0.022)
    return p, 600


PARTS = [hips, torso, neck, upper_arm, forearm, thigh, shin, foot, club, staff, shield] + [
    (lambda v=v: head(v)) for v in ("grunt", "scout", "berserker", "shaman")
]

if __name__ == "__main__":
    clear_scene()
    objs = []
    for fn in PARTS:
        part, budget = fn()
        ob = build_part(part, budget)
        objs.append(ob)
        print(f"{ob.name}: {sum(len(p.vertices) - 2 for p in ob.data.polygons)} tris")
    export_glb(OUT / "creatures.glb", objs)
    print("CREATURES_DONE")
