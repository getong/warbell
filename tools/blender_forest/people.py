"""Organic HUMAN body parts for the shared biped rig -> people.glb.

Same contract as creatures.py (the orks): one mesh per rig joint (hips, torso, neck, head, upper
arm, forearm + hand, thigh, shin, foot), authored in that joint's local frame (game coords: Y up,
+Z forward, limbs hanging down -Y from their joint; joint offsets = `biped::spawn_biped`).
Body masses are fused metaballs, polygonised and decimated per part.

Unlike the orks, a townsperson is ASSEMBLED in the game from a base body plus add-ons merged per
joint (hair style, beard, headgear, apron / armour / quiver / cloak, robe skirt, bracer, ...), so a
dozen looks and every trade / faction come out of ~50 small meshes. `peasant_model::kit_peasant_meshes`
does the assembly; keep the part names in sync with it.

Clothing that sits ON the body (aprons, plate, tabards, jerkins, belts, hems, hair, hoods, helmet
domes, beards) is built as an OFFSET SHELL of the real polygonised surface underneath (`HPart.shell`)
clipped by planes (`HPart.cut`), so it always hugs the body instead of hiding inside the fused
metaball field. Small face features (eyes, brows, mouth, moustache) are SNAPPED onto the skin by a
ray from the front (`HPart.snap_*`).

Vertex colour R carries a REGION code (region / 16 + 1/32) that the game maps to the person's skin,
hair, tunic, trousers, leather, metal ... (and the creature shader's surface code); G is a baked
cavity term.

Rig the parts were authored against (rig units; the villager root scales the whole rig):
  hips joint y 1.05 · legs at (+-HDX, -0.05) · knee -0.40 · ankle -0.45 (sole 0.09 below it)
  torso +0.15 above the hips · neck +0.35 · head +0.08 (head_scale 1.06) · shoulders (+-SDX, 0.27)
  elbow -0.30 · hand (tool grip) -0.25 below the elbow.

    blender -b --factory-startup --python tools/blender_forest/people.py [-- preview.png]
    (PEOPLE_PREVIEW_YAW=deg, PEOPLE_PREVIEW_CAM="x,z,ortho_width" frame the Workbench lineup)
"""
import math
import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402
from common import OUT, clear_scene, export_glb, name_material  # noqa: E402
from creatures import Part, bl, make_metaball  # noqa: E402

# Region codes (<= 16). Keep in sync with `peasant_model::kit_peasant_meshes`.
(SKIN, LIP, EYE, HAIR, TUNIC, TRIM, TROUSER, LEATHER, BOOT, METAL, HEADCLOTH, BAND, TABARD, FLETCH,
 CLOAK, HELM) = range(16)

SDX = 0.2  # shoulder joint half-span the parts are built for (`peasant_model::KIT_SHOULDER_DX`)
HDX = 0.1  # hip joint half-span (`peasant_model::KIT_HIP_DX`)
SNAP_RES = 0.0022  # metaball grid for the tiny snapped face features
# Head parts are authored with the skull base at the origin; the head JOINT is the atlas pivot,
# level with the ears, so every head-mounted part (head, hair, beard, hat) drops by this on export
# (the jaw hangs below the pivot like the box / ork heads, instead of a long neck under it).
HEAD_DROP = 0.05
HEAD_PARTS = ("hu_head", "hu_hair", "hu_beard", "hu_hat")

REF = {}  # cached polygonised surfaces (Blender coords): key -> (verts, faces)


class Cuts:
    """Plane clips for ONE offset shell (`HPart.shell` returns one): keep (p - co) . no >= 0."""

    def __init__(self, lst):
        self.lst = lst

    def cut(self, co, no):
        self.lst.append((tuple(co), tuple(no)))
        return self

    def slab(self, axis, lo, hi):
        """Keep lo <= p . axis <= hi."""
        a = Vector(axis).normalized()
        self.lst += [(tuple(a * lo), tuple(a)), (tuple(a * hi), tuple(-a))]
        return self


class HPart(Part):
    def __init__(self, name):
        super().__init__(name)
        self.cuts = {}  # region -> [(co, no)]: keep (p - co) . no >= 0
        self.shells = []  # (region, ref key, offset, own cuts)
        self.snaps = []  # (region, on, kind, args)
        self.keep = {}  # region -> ref key to cache (before cuts)

    def cut(self, region, co, no):
        """Clip EVERY piece of `region` in this part (metaballs, shells, snaps)."""
        self.cuts.setdefault(region, []).append((co, no))

    def slab(self, region, axis, lo, hi):
        Cuts(self.cuts.setdefault(region, [])).slab(axis, lo, hi)

    def shell(self, region, ref, offset):
        """An offset copy of cached surface `ref`; returns its own `Cuts`."""
        cuts = []
        self.shells.append((region, ref, offset, cuts))
        return Cuts(cuts)

    def cache(self, region, key):
        self.keep[region] = key

    def snap_ell(self, region, xy, radii, embed, on=SKIN):
        self.snaps.append((region, on, "ell", (xy, radii, embed)))

    def snap_cap(self, region, a, b, r, embed, on=SKIN):
        self.snaps.append((region, on, "cap", (a, b, r, embed)))

    def ring(self, region, y, rx, rz, r, n=16, dip=0.0, cz=0.0, cx=0.0):
        """A smooth band of capsules round an ellipse (`dip` lowers the front)."""
        pts = []
        for k in range(n):
            a = k / n * 2 * math.pi
            front = max(0.0, math.cos(a))
            pts.append((cx + rx * math.sin(a), y - dip * front * front, cz + rz * math.cos(a)))
        for k in range(n):
            self.cap(region, pts[k], pts[(k + 1) % n], r)


def _poly(name, specs, res):
    ob = make_metaball(name, specs, res)
    ob.data.render_resolution = res
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob)
    return me


def _ref_of(meshes):
    verts, faces = [], []
    for me in meshes:
        base = len(verts)
        verts += [v.co.copy() for v in me.vertices]
        faces += [[base + i for i in p.vertices] for p in me.polygons]
    return verts, faces


def _offset(ref, d):
    verts, faces = ref
    me = bpy.data.meshes.new("shell_tmp")
    me.from_pydata(verts, [], faces)
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.normal_update()
    c = sum((v.co for v in bm.verts), Vector()) / max(1, len(bm.verts))
    sign = 1.0 if sum((v.co - c).dot(v.normal) for v in bm.verts) >= 0 else -1.0
    for v in bm.verts:
        v.co += v.normal * (d * sign)
    bm.to_mesh(me)
    bm.free()
    return me


def _bisect(me, cuts):
    bm = bmesh.new()
    bm.from_mesh(me)
    for co, no in cuts:
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=bl(co), plane_no=bl(no), clear_inner=True)
    bm.to_mesh(me)
    bm.free()


def _surface_z(bvh, x, y):
    """Front-most surface z (game) at (x, y), by a ray cast along -Z from in front."""
    hit = bvh.ray_cast(bl((x, y, 0.6)), Vector((0, 1, 0)))
    if hit[0] is None:
        return None
    return -hit[0].y


def build(part, target_tris, res=0.008, export=True):
    pieces = {}
    for region, specs in part.groups.items():
        pieces.setdefault(region, []).append(_poly(f"{part.name}_{region}", specs, res))
    for region, key in part.keep.items():
        REF[key] = _ref_of(pieces.get(region, []))
    for region, ref, d, cuts in part.shells:
        me = _offset(REF[ref], d)
        if cuts:
            _bisect(me, cuts)
        pieces.setdefault(region, []).append(me)
    if part.snaps:
        bvhs = {}
        snapped = {}
        for region, on, kind, args in part.snaps:
            if on not in bvhs:
                v, f = REF[on] if isinstance(on, str) else _ref_of(pieces[on])
                bvhs[on] = BVHTree.FromPolygons(v, f)
            bvh = bvhs[on]
            if kind == "ell":
                (x, y), radii, embed = args
                z = _surface_z(bvh, x, y)
                if z is not None:
                    snapped.setdefault(region, []).append(("ELLIPSOID", (x, y, z - embed), 1.0, radii, None, 2.0))
            else:
                a, b, r, embed = args
                za, zb = _surface_z(bvh, *a), _surface_z(bvh, *b)
                if za is not None and zb is not None:
                    snapped.setdefault(region, []).append(("CAPSULE", (a[0], a[1], za - embed), r, (b[0], b[1], zb - embed), None, 2.0))
        for region, specs in snapped.items():
            pieces.setdefault(region, []).append(_poly(f"{part.name}_s{region}", specs, SNAP_RES))
    if not export:
        for meshes in pieces.values():
            for me in meshes:
                bpy.data.meshes.remove(me)
        return None
    verts, faces, regs = [], [], []
    for region, meshes in pieces.items():
        for me in meshes:
            if region in part.cuts:
                _bisect(me, part.cuts[region])
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
    me.color_attributes.new("Col", "FLOAT_COLOR", "CORNER")
    face_reg = [0.0] * len(me.polygons)
    reg_attr = me.attributes.get("reg")
    if reg_attr is not None:
        reg_attr.data.foreach_get("value", face_reg)
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
        # Finer parts than the orks -> a gentler crease gain so faces don't smudge.
        cav.append(max(0.66, min(1.0, 1.0 - conc * 10.0)))
    cols = []
    for p in me.polygons:
        r = int(round(face_reg[p.index]))
        for li in p.loop_indices:
            vi = me.loops[li].vertex_index
            cols += [r / 16.0 + 1.0 / 32.0, cav[vi], 1.0, 1.0]
    me.color_attributes["Col"].data.foreach_set("color", cols)
    me.color_attributes.active_color = me.color_attributes["Col"]
    return ob


# ─────────────────────────────────────────────────────────────── body
def _skirt(p):
    p.ell(TUNIC, (0, 0.07, 0.0), (0.128, 0.1, 0.089))
    p.ell(TUNIC, (0, -0.05, 0.0), (0.162, 0.08, 0.108))
    p.ell(TUNIC, (0, -0.108, 0.0), (0.176, 0.042, 0.12))


def skirt_ref():
    """Reference only: the tunic skirt continued down to the knee — the surface the apron and
    tabard panels hang from (so they drape as one smooth sheet in front of the thighs)."""
    p = HPart("ref_skirt")
    _skirt(p)
    p.ell(TUNIC, (0, -0.2, 0.0), (0.168, 0.13, 0.12))
    p.cache(TUNIC, "skirt_long")
    return p, 0


def hips():
    p = HPart("hu_hips")
    # Pelvis in trousers (only the crotch / seat shows under the tunic skirt).
    p.ell(TROUSER, (0, -0.05, -0.005), (0.125, 0.078, 0.086))
    p.ball(TROUSER, (0, -0.112, 0.0), 0.05)
    for sx in (-1, 1):
        p.ball(TROUSER, (sx * 0.09, -0.085, 0.0), 0.05)
        p.ball(TROUSER, (sx * 0.052, -0.078, -0.042), 0.057)
    # Tunic from the waist (overlapping the torso) flaring into a short skirt over the hips.
    _skirt(p)
    p.cache(TUNIC, "hips_tunic")
    p.shell(TRIM, "hips_tunic", 0.0035).slab((0, 1, 0), -0.2, -0.128)  # hem band
    p.shell(LEATHER, "hips_tunic", 0.009).slab((0, 1, 0), 0.016, 0.05)  # belt
    p.snap_ell(METAL, (0.0, 0.033), (0.019, 0.017, 0.007), -0.002, on=LEATHER)  # buckle
    p.snap_cap(LEATHER, (0.028, 0.02), (0.033, -0.05), 0.0055, -0.003, on=TUNIC)  # strap end
    return p, 550


def hips_robe():
    """Desert thobe skirt from the belt to above the knee (worn over the tunic skirt)."""
    p = HPart("hu_hips_robe")
    p.ell(CLOAK, (0, -0.17, 0.0), (0.162, 0.15, 0.128))
    p.ell(CLOAK, (0, -0.3, 0.0), (0.178, 0.08, 0.142))
    p.cache(CLOAK, "robe")
    p.cut(CLOAK, (0, -0.37, 0), (0, 1, 0))
    p.shell(CLOAK, "hips_tunic", 0.012)
    p.shell(BAND, "robe", 0.004).slab((0, 1, 0), -0.37, -0.335)
    return p, 480


def hips_apron():
    """Lower half of the farmer's apron: a front panel from the belt to the upper thigh."""
    p = HPart("hu_hips_apron")
    p.shell(TABARD, "skirt_long", 0.014).cut((0, 0, 0.05), (0, 0, 1)).slab((0, 1, 0), -0.26, 0.045).slab(
        (1, 0, 0), -0.115, 0.115)
    return p, 200


def hips_tabard():
    """The guard's livery tabard below the belt: the skirt panel front and back + a front flap."""
    p = HPart("hu_hips_tabard")
    p.shell(TABARD, "skirt_long", 0.016).slab((0, 1, 0), -0.24, 0.03).slab((1, 0, 0), -0.078, 0.078)
    return p, 160


def torso():
    p = HPart("hu_torso")
    # Loose tunic over a slim chest: belly, ribcage, shoulder blades, sloping traps.
    p.ell(TUNIC, (0, -0.07, 0.0), (0.124, 0.07, 0.089))
    p.ell(TUNIC, (0, 0.04, 0.0), (0.12, 0.11, 0.086))
    p.ell(TUNIC, (0, 0.18, -0.005), (0.134, 0.11, 0.093))
    for sx in (-1, 1):
        p.cap(TUNIC, (sx * 0.045, 0.338, -0.012), (sx * 0.132, 0.286, -0.006), 0.036)
        p.ball(TUNIC, (sx * 0.142, 0.252, 0.0), 0.04)
    p.ball(TUNIC, (0, 0.322, -0.012), 0.056)
    p.cache(TUNIC, "torso_tunic")
    # Neckline: a band round the neck, scooped lower at the front.
    p.shell(TRIM, "torso_tunic", 0.0045).cut((0, 0.345, 0), (0, 1, 0.35)).slab((1, 0, 0), -0.095, 0.095)
    return p, 800


def torso_apron():
    p = HPart("hu_torso_apron")
    p.shell(TABARD, "torso_tunic", 0.01).cut((0, 0, 0.045), (0, 0, 1)).cut((0, 0.215, 0), (0, -1, 0)).slab(
        (1, 0, 0), -0.1, 0.1)  # bib
    for sx in (-1, 1):  # neck straps over the shoulders
        p.shell(LEATHER, "torso_tunic", 0.012).cut((0, 0.205, 0), (0, 1, 0)).slab((sx, 0, 0), 0.06, 0.078)
    return p, 300


def torso_guard():
    p = HPart("hu_torso_guard")
    p.shell(METAL, "torso_tunic", 0.009).slab((0, 1, 0), -0.1, 0.27)  # breastplate + backplate
    p.shell(TABARD, "torso_tunic", 0.016).slab((0, 1, 0), -0.13, 0.255).slab((1, 0, 0), -0.078, 0.078)  # tabard
    for sx in (-1, 1):  # shoulder straps over the plate
        p.shell(LEATHER, "torso_tunic", 0.013).cut((0, 0.255, 0), (0, 1, 0)).slab((sx, 0, 0), 0.075, 0.098)
    return p, 450


def _diag(p, region, ref, offset, a, b, half_w):
    """A sash / baldric: an offset shell band along the line a -> b (x, y) through the torso."""
    d = Vector((b[0] - a[0], b[1] - a[1], 0)).normalized()
    n = Vector((d.y, -d.x, 0))
    c = Vector(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, 0))
    p.shell(region, ref, offset).cut(c - n * half_w, n).cut(c + n * half_w, -n)


def torso_archer():
    p = HPart("hu_torso_archer")
    p.shell(LEATHER, "torso_tunic", 0.009).slab((0, 1, 0), -0.11, 0.272)  # sleeveless jerkin
    _diag(p, BAND, "torso_tunic", 0.015, (-0.12, -0.04), (0.12, 0.3), 0.02)  # baldric
    # Back quiver, mouth over the right shoulder, with fletched shafts poking out.
    a, b = Vector((0.04, -0.03, -0.142)), Vector((0.15, 0.32, -0.142))
    p.cap(LEATHER, tuple(a), tuple(b), 0.04)
    p.ell(BAND, tuple(b.lerp(a, 0.05)), (0.047, 0.018, 0.047))
    p.ell(BAND, tuple(b.lerp(a, 0.78)), (0.045, 0.015, 0.045))
    d = (b - a).normalized()
    for k, (ox, oz) in enumerate(((0.0, 0.0), (0.016, 0.016), (-0.015, 0.012), (0.005, -0.018))):
        base = b + Vector((ox, 0, oz))
        tip = base + d * (0.1 + 0.015 * k)
        p.cap(BAND, tuple(base), tuple(tip), 0.005)
        p.ell(FLETCH, tuple(tip - d * 0.02), (0.011, 0.028, 0.011))
    return p, 650


def torso_cloak():
    """Desert cloak draped down the back from the shoulders."""
    p = HPart("hu_torso_cloak")
    p.ell(CLOAK, (0, -0.19, -0.098), (0.165, 0.17, 0.03))
    p.shell(CLOAK, "torso_tunic", 0.018)
    p.cut(CLOAK, (0, 0, -0.03), (0, 0, -1))
    p.cut(CLOAK, (0, 0.335, 0), (0, -1, 0))
    p.cut(CLOAK, (0, -0.35, 0), (0, 1, 0))
    p.shell(BAND, "torso_tunic", 0.02).slab((0, 1, 0), 0.272, 0.29).cut((0, 0, 0.0), (0, 0, 1))  # cord
    return p, 380


def torso_sash():
    """The desert worker's diagonal sash across the chest."""
    p = HPart("hu_torso_sash")
    _diag(p, BAND, "torso_tunic", 0.014, (0.13, -0.06), (-0.13, 0.3), 0.03)
    return p, 220


def neck():
    p = HPart("hu_neck")
    p.cap(SKIN, (0, -0.07, -0.004), (0, 0.06, -0.008), 0.055)
    p.ball(SKIN, (0, -0.03, 0.0), 0.058)
    return p, 160


def _skull(p):
    """Elements every face shares above the eyes (the hair / headgear reference surface)."""
    p.ell(SKIN, (0, 0.12, -0.014), (0.074, 0.088, 0.095))  # cranium
    p.ell(SKIN, (0, 0.075, 0.028), (0.06, 0.066, 0.066))  # face mass
    p.ell(SKIN, (0, 0.0, -0.035), (0.048, 0.05, 0.045))  # nape, blends into the neck
    p.cap(SKIN, (-0.036, 0.118, 0.076), (0.036, 0.118, 0.076), 0.0145)  # brow ridge


def scalp_ref():
    p = HPart("ref_scalp")
    _skull(p)
    p.cache(SKIN, "scalp")
    return p, 0


# Face shapes: a (average), b (broad, heavier jaw + nose), c (lean, fine), kid (round, small nose,
# big eyes). All in the head joint's frame (neck top at the origin, face toward +Z).
FACES = {
    "a": dict(w=1.0, jaw=1.0, nose=1.0, eye=1.0, chin=1.0, lip=1.0, cheek=1.0),
    "b": dict(w=1.06, jaw=1.16, nose=1.18, eye=0.95, chin=1.12, lip=1.0, cheek=1.1),
    "c": dict(w=0.95, jaw=0.86, nose=0.88, eye=1.06, chin=0.88, lip=1.12, cheek=0.92),
    "kid": dict(w=1.0, jaw=0.8, nose=0.68, eye=1.3, chin=0.78, lip=0.9, cheek=1.15, kid=True),
}


def head(variant):
    f = FACES[variant]
    kid = f.get("kid", False)
    w, j = f["w"], f["jaw"]
    p = HPart(f"hu_head_{variant}")
    _skull(p)
    p.ell(SKIN, (0, 0.03, 0.03), (0.052 * w * j, 0.037, 0.057))  # jaw
    p.ball(SKIN, (0, 0.004, 0.066), 0.02 * f["chin"])  # chin
    for sx in (-1, 1):
        p.ball(SKIN, (sx * 0.04 * w, 0.072, 0.056), 0.022 * f["cheek"])  # cheekbones
        p.ell(SKIN, (sx * 0.071 * w, 0.085, -0.008), (0.011, 0.026, 0.018))  # ears
        p.ball(SKIN, (sx * 0.044 * w * j, 0.03, 0.032), 0.028)  # jaw angle
    n = f["nose"]
    p.cap(SKIN, (0, 0.108, 0.087), (0, 0.073, 0.097 + 0.009 * n), 0.0098 * n)  # nose bridge
    p.ball(SKIN, (0, 0.068, 0.097 + 0.009 * n), 0.012 * n)  # nose tip
    for sx in (-1, 1):
        p.ball(SKIN, (sx * 0.011 * n, 0.066, 0.092), 0.0085 * n)  # nostril wings
    p.ell(SKIN, (0, 0.04, 0.079), (0.021, 0.011, 0.012))  # upper lip
    p.ell(SKIN, (0, 0.021, 0.077), (0.018, 0.01, 0.012))  # lower lip
    p.cache(SKIN, f"head_{variant}")
    e = f["eye"]
    for sx in (-1, 1):
        p.snap_ell(EYE, (sx * 0.03, 0.094), (0.014 * e, 0.0078 * e, 0.008), 0.003)
        if kid:
            p.snap_cap(HAIR, (sx * 0.015, 0.121), (sx * 0.04, 0.118), 0.0038, 0.0018)
        else:
            p.snap_cap(HAIR, (sx * 0.013, 0.121), (sx * 0.043 * w, 0.116), 0.0052, 0.0024)
    p.snap_cap(LIP, (-0.018 * f["lip"], 0.031), (0.018 * f["lip"], 0.031), 0.0048, 0.0012)
    return p, 1200


def _hairline(cuts, front_y, nape_y):
    """Keep above a plane from the forehead hairline (0, front_y, 0.09) back to the nape."""
    a = Vector((0, front_y, 0.09))
    b = Vector((0, nape_y, -0.11))
    d = (b - a).normalized()
    no = Vector((0, -d.z, d.y))
    if no.y < 0:
        no = -no
    return cuts.cut(a, no)


def hair(style):
    p = HPart(f"hu_hair_{style}")
    if style == "crop":
        _hairline(p.shell(HAIR, "scalp", 0.0065), 0.152, 0.035)
    elif style == "shag":
        _hairline(p.shell(HAIR, "scalp", 0.013), 0.142, -0.005)
        for sx in (-1, 1):
            p.ell(HAIR, (sx * 0.062, 0.075, -0.05), (0.022, 0.045, 0.045))  # over the ears
        p.ell(HAIR, (0, 0.045, -0.082), (0.06, 0.05, 0.03))  # nape
        p.ell(HAIR, (0.012, 0.162, 0.077), (0.055, 0.017, 0.022))  # fringe
    elif style == "long":
        _hairline(p.shell(HAIR, "scalp", 0.009), 0.156, 0.04)
        p.ell(HAIR, (0, 0.03, -0.09), (0.066, 0.11, 0.034))  # falls to the shoulders
        for sx in (-1, 1):
            p.ell(HAIR, (sx * 0.07, 0.07, -0.042), (0.02, 0.07, 0.034))
        p.cap(HAIR, (0, -0.05, -0.1), (0, -0.15, -0.096), 0.02)  # tied tail
    elif style == "bald":
        # Horseshoe fringe round the back and sides; bare crown.
        _hairline(p.shell(HAIR, "scalp", 0.006), 0.14, 0.03).cut((0, 0.16, -0.03), (0, -1, -0.45))
    elif style == "bowl":
        _hairline(p.shell(HAIR, "scalp", 0.015), 0.13, 0.06)
    return p, 240 if style in ("crop", "bald", "bowl") else 360


def beard(style, face):
    p = HPart(f"hu_beard_{style}_{face}")
    ref = f"head_{face}"
    if style == "full":
        # Under the cheekbones (rising toward the ears), nothing behind the jaw hinge.
        p.shell(HAIR, ref, 0.011).cut((0, 0.068, 0.09), (0, -1, -0.55)).cut((0, 0, -0.012), (0, 0.25, 1))
        p.ell(HAIR, (0, -0.006, 0.07), (0.03, 0.03, 0.026))  # chin tuft
        p.snap_cap(HAIR, (-0.03, 0.046), (0.03, 0.046), 0.0075, -0.002, on=ref)  # moustache
    elif style == "short":
        p.shell(HAIR, ref, 0.0055).cut((0, 0.058, 0.09), (0, -1, -0.5)).cut((0, 0, 0.0), (0, 0.25, 1))
        p.snap_cap(HAIR, (-0.026, 0.046), (0.026, 0.046), 0.006, -0.001, on=ref)
    elif style == "moustache":
        for sx in (-1, 1):
            p.snap_cap(HAIR, (sx * 0.004, 0.047), (sx * 0.028, 0.04), 0.0072, -0.001, on=ref)
            p.snap_cap(HAIR, (sx * 0.028, 0.04), (sx * 0.031, 0.018), 0.0052, 0.0, on=ref)
    return p, 200


# ─────────────────────────────────────────────────────────────── headgear
def hat(kind):
    p = HPart(f"hu_hat_{kind}")
    if kind == "hood":
        # Cloth hood: an offset shell of the skull with the face opening cut out, a cowl round the
        # neck and a short point behind.
        p.shell(HEADCLOTH, "scalp", 0.022)
        p.ell(HEADCLOTH, (0, -0.01, -0.035), (0.1, 0.06, 0.1))
        p.cap(HEADCLOTH, (0, 0.17, -0.09), (0, 0.1, -0.155), 0.028)
        p.cut(HEADCLOTH, (0, 0.0, 0.06), (0, 0.18, -1))
        p.cut(HEADCLOTH, (0, -0.065, 0), (0, 1, 0))
    elif kind == "cap":
        # Felt cap pulled over the crown, rolled brim, slouched top.
        p.shell(HEADCLOTH, "scalp", 0.012).cut((0, 0.133, 0), (0, 1, 0.22))
        p.ball(HEADCLOTH, (0.02, 0.212, -0.035), 0.04)
        p.shell(BAND, "scalp", 0.018).slab((0, 1, 0.22), 0.128, 0.146)
    elif kind == "straw":
        p.shell(HEADCLOTH, "scalp", 0.026).cut((0, 0.152, 0), (0, 1, 0))
        p.ell(HEADCLOTH, (0, 0.205, -0.012), (0.07, 0.05, 0.085))  # raised crown
        p.ell(HEADCLOTH, (0, 0.157, -0.012), (0.19, 0.01, 0.185))  # wide brim
        p.shell(BAND, "scalp", 0.03).slab((0, 1, 0), 0.16, 0.18)
    elif kind == "miner":
        p.shell(METAL, "scalp", 0.016).cut((0, 0.136, 0), (0, 1, 0))
        p.ell(METAL, (0, 0.2, -0.012), (0.06, 0.04, 0.075))
        p.ell(METAL, (0, 0.14, 0.0), (0.096, 0.009, 0.124))  # brim
        p.snap_ell(LEATHER, (0.0, 0.172), (0.024, 0.021, 0.014), -0.006, on=METAL)  # lamp housing
        p.snap_ell(FLETCH, (0.0, 0.172), (0.016, 0.014, 0.006), -0.019, on=METAL)  # lamp glass
    elif kind == "helm":
        # Nasal helm: steel dome, a rim band, a nose guard and a crest ridge.
        # Rim sits on the brow, clear of the eyes.
        p.shell(HELM, "scalp", 0.016).cut((0, 0.124, 0), (0, 1, 0.12))
        p.shell(METAL, "scalp", 0.021).slab((0, 1, 0.12), 0.12, 0.138)  # rim band
        p.snap_cap(HELM, (0, 0.132), (0, 0.082), 0.0085, -0.007, on="head_a")
    elif kind == "archer":
        p.shell(HEADCLOTH, "scalp", 0.012)
        p.ell(HEADCLOTH, (0, 0.02, -0.07), (0.08, 0.075, 0.05))  # neck drape
        p.cut(HEADCLOTH, (0, 0.0, 0.052), (0, 0.25, -1))
        p.cut(HEADCLOTH, (0, -0.06, 0), (0, 1, 0))
        p.shell(BAND, "scalp", 0.017).slab((0, 1, 0.25), 0.13, 0.148)
        p.cap(FLETCH, (0.075, 0.165, -0.045), (0.105, 0.28, -0.085), 0.008)  # feather
        p.ell(FLETCH, (0.096, 0.245, -0.075), (0.009, 0.05, 0.017))
    elif kind == "turban":
        p.shell(HEADCLOTH, "scalp", 0.03).cut((0, 0.112, 0), (0, 1, 0.22))
        p.ell(HEADCLOTH, (0, 0.215, -0.012), (0.075, 0.05, 0.088))
        p.ball(HEADCLOTH, (0.07, 0.205, -0.02), 0.032)  # tuck knot
        p.shell(BAND, "scalp", 0.036).slab((0, 1, 0.22), 0.112, 0.13)
        p.ell(CLOAK, (0, 0.035, -0.082), (0.08, 0.09, 0.036))  # neck drape
    elif kind == "warhelm":
        # Saracen war-helm: a bronze cone over a turban band, with a light neck drape.
        p.shell(HEADCLOTH, "scalp", 0.026).slab((0, 1, 0), 0.105, 0.17)
        for y, r in ((0.165, 0.082), (0.21, 0.068), (0.255, 0.05), (0.295, 0.032), (0.325, 0.017)):
            p.ball(HELM, (0, y, -0.012), r)
        p.cut(HELM, (0, 0.15, 0), (0, 1, 0))
        p.ell(CLOAK, (0, 0.035, -0.082), (0.08, 0.09, 0.036))
    elif kind == "headwrap":
        p.shell(HEADCLOTH, "scalp", 0.014)
        p.ell(HEADCLOTH, (0, 0.02, -0.068), (0.085, 0.085, 0.05))
        p.cut(HEADCLOTH, (0, 0.0, 0.052), (0, 0.25, -1))
        p.cut(HEADCLOTH, (0, -0.07, 0), (0, 1, 0))
        p.shell(BAND, "scalp", 0.019).slab((0, 1, 0.25), 0.14, 0.158)
        p.cap(FLETCH, (0.075, 0.17, -0.045), (0.105, 0.28, -0.085), 0.008)
        p.ell(FLETCH, (0.096, 0.245, -0.075), (0.009, 0.05, 0.017))
    return p, 400


# ─────────────────────────────────────────────────────────────── limbs
def upper_arm(sx):
    """Shoulder joint frame (R side at +X when sx = 1). Sleeve to the elbow."""
    side = "r" if sx > 0 else "l"
    p = HPart(f"hu_upper_arm_{side}")
    p.ell(TUNIC, (sx * 0.004, -0.045, 0.0), (0.041, 0.072, 0.043))  # deltoid under the sleeve
    p.ell(TUNIC, (0, -0.16, 0.005), (0.035, 0.13, 0.037))
    p.cap(TUNIC, (0, -0.2, 0), (0, -0.29, 0.0), 0.033)
    p.cache(TUNIC, f"uparm_{side}")
    return p, 260


def pauldron(sx):
    side = "r" if sx > 0 else "l"
    p = HPart(f"hu_pauldron_{side}")
    p.shell(METAL, f"uparm_{side}", 0.012).cut((0, -0.08, 0), (0, 1, 0))
    p.shell(METAL, f"uparm_{side}", 0.017).slab((0, 1, 0), -0.088, -0.068)  # rolled rim
    return p, 140


def _fist(p, sx):
    """Gripping hand round the hand joint (0, -0.25, 0) — the tool haft runs along Z through it."""
    p.ell(SKIN, (sx * 0.005, -0.243, 0.002), (0.02, 0.035, 0.037))  # palm / back of hand
    for k in range(4):
        z = -0.025 + k * 0.0165
        p.cap(SKIN, (sx * 0.011, -0.272, z), (-sx * 0.013, -0.269, z * 0.95), 0.0098)  # curled fingers
    p.cap(SKIN, (-sx * 0.009, -0.227, 0.028), (-sx * 0.015, -0.252, 0.043), 0.0088)  # thumb
    p.cap(SKIN, (0, -0.2, 0), (0, -0.226, 0.0), 0.022)  # wrist


def forearm(sx, sleeve):
    side = "r" if sx > 0 else "l"
    p = HPart(f"hu_forearm_{'sleeve' if sleeve else 'bare'}_{side}")
    if sleeve:
        p.ell(TUNIC, (0, -0.06, 0.003), (0.035, 0.09, 0.036))
        p.cap(TUNIC, (0, 0.0, 0), (0, -0.18, 0.0), 0.03)
        p.ell(TRIM, (0, -0.188, 0), (0.034, 0.015, 0.034))
    else:
        p.ell(TUNIC, (0, -0.005, 0), (0.039, 0.026, 0.039))  # rolled-up sleeve
        p.ell(SKIN, (0, -0.075, 0.004), (0.032, 0.085, 0.034))
        p.cap(SKIN, (0, -0.03, 0), (0, -0.19, 0), 0.023)
        p.ell(LEATHER, (0, -0.193, 0), (0.031, 0.016, 0.031))  # wrist wrap
    _fist(p, sx)
    if not sleeve:
        p.cache(SKIN, f"forearm_{side}")
    return p, 380


def bracer(sx):
    """The archer's laced leather bow-arm guard (forearm add-on)."""
    side = "r" if sx > 0 else "l"
    p = HPart(f"hu_bracer_{side}")
    p.shell(LEATHER, f"forearm_{side}", 0.009).slab((0, 1, 0), -0.186, -0.065)
    for y in (-0.085, -0.13, -0.172):
        p.ell(BAND, (0, y, 0.0), (0.04, 0.006, 0.04))
    return p, 200


def thigh():
    p = HPart("hu_thigh")
    p.ball(TROUSER, (0, -0.04, 0.0), 0.056)
    p.ell(TROUSER, (0, -0.16, 0.006), (0.064, 0.19, 0.067))
    p.cap(TROUSER, (0, -0.2, 0), (0, -0.4, 0.006), 0.045)
    return p, 240


def shin(desert):
    p = HPart("hu_shin_wrap" if desert else "hu_shin")
    p.ball(TROUSER, (0, 0.0, 0.004), 0.043)
    p.ell(TROUSER, (0, -0.13, -0.008), (0.044, 0.14, 0.048))
    if desert:
        p.cap(TROUSER, (0, 0.0, 0), (0, -0.39, 0), 0.042)
        p.ball(TROUSER, (0, -0.36, 0), 0.049)
        p.ell(BAND, (0, -0.405, 0), (0.041, 0.025, 0.041))
        p.cap(SKIN, (0, -0.4, 0), (0, -0.46, 0.004), 0.028)
    else:
        p.cap(TROUSER, (0, 0.0, 0), (0, -0.24, 0), 0.04)
        p.cap(BOOT, (0, -0.22, 0.0), (0, -0.445, 0.004), 0.04)
        p.ball(BOOT, (0, -0.25, -0.006), 0.044)
        p.ell(BOOT, (0, -0.21, 0.0), (0.049, 0.018, 0.049))  # turned-down cuff
    return p, 260


def foot(desert):
    p = HPart("hu_foot_sandal" if desert else "hu_foot")
    if desert:
        p.ball(SKIN, (0, -0.012, -0.004), 0.03)
        p.ball(SKIN, (0, -0.05, -0.03), 0.03)
        p.ell(SKIN, (0, -0.052, 0.05), (0.036, 0.025, 0.08))
        p.ell(SKIN, (0, -0.066, 0.128), (0.036, 0.017, 0.034))
        p.ell(LEATHER, (0, -0.082, 0.05), (0.045, 0.01, 0.128))
        p.ell(BAND, (0, -0.045, 0.085), (0.042, 0.013, 0.02))
        p.ell(BAND, (0, -0.03, -0.01), (0.035, 0.01, 0.035))
    else:
        p.ball(BOOT, (0, -0.01, -0.004), 0.042)
        p.ball(BOOT, (0, -0.05, -0.033), 0.039)
        p.ell(BOOT, (0, -0.048, 0.05), (0.043, 0.037, 0.085))
        p.ell(BOOT, (0, -0.064, 0.128), (0.039, 0.026, 0.045))
        p.ell(LEATHER, (0, -0.082, 0.048), (0.046, 0.011, 0.13))  # sole
    return p, 220


# ─────────────────────────────────────────────────────────────── trade tools / off-hand props
# Same frames and dimensions as the box props in `peasant_model::peasant_tools`: hand tools on the
# `Sword` pivot, built +Y from the grip at the origin (the shared rest rotation carries them); the
# shield faces +Z (the game adds the box shield's yaw), the bow's stave arcs in the Y-Z plane with
# the string at -Z. Tools use their OWN palette (`peasant_model::kit_tool`), so own region codes.
T_WOOD, T_IRON, T_LEATHER, T_ACCENT, T_BRONZE, T_STRING = range(6)


def _rot_z(a):
    """Element rotation about the GAME Z axis (Blender -Y)."""
    from mathutils import Quaternion
    return Quaternion(Vector((0, -1, 0)), a)


def _rot_x(a):
    from mathutils import Quaternion
    return Quaternion(Vector((1, 0, 0)), a)


def tool(kind):
    p = HPart(f"hu_tool_{kind}")
    if kind == "axe":
        p.cap(T_WOOD, (0, -0.05, 0), (0, 0.555, 0), 0.019)
        p.cap(T_LEATHER, (0, -0.04, 0), (0, 0.07, 0), 0.023)  # grip wrap
        p.ell(T_IRON, (0.035, 0.517, 0), (0.05, 0.036, 0.018))  # eye / cheeks
        p.ell(T_IRON, (0.12, 0.515, 0), (0.06, 0.045, 0.01))  # blade body
        p.ell(T_IRON, (0.175, 0.513, 0), (0.016, 0.075, 0.008))  # flared bit
        p.ball(T_IRON, (-0.03, 0.517, 0), 0.02)  # poll
    elif kind == "hoe":
        p.cap(T_WOOD, (0, -0.05, 0), (0, 0.565, 0), 0.018)
        p.ell(T_IRON, (0, 0.512, 0), (0.024, 0.042, 0.024))  # socket
        p.ell(T_IRON, (0.115, 0.48, 0.02), (0.105, 0.03, 0.01), rot=_rot_z(-0.55))  # blade
    elif kind == "pick":
        p.cap(T_WOOD, (0, -0.05, 0), (0, 0.535, 0), 0.018)
        p.ell(T_IRON, (0, 0.49, 0), (0.026, 0.04, 0.024))  # socket
        pts = [(-0.175, 0.45), (-0.09, 0.49), (0.0, 0.5), (0.09, 0.49), (0.175, 0.45)]
        rads = [0.006, 0.014, 0.02, 0.014, 0.006]
        for (a, ra), (b, rb) in zip(zip(pts, rads), zip(pts[1:], rads[1:])):
            p.cap(T_IRON, (a[0], a[1], 0), (b[0], b[1], 0), (ra + rb) / 2)
    elif kind == "sword":
        p.cap(T_LEATHER, (0, -0.1, 0), (0, 0.04, 0), 0.016)  # grip
        p.ball(T_IRON, (0, -0.115, 0), 0.023)  # pommel
        p.cap(T_IRON, (-0.088, 0.058, 0), (0.088, 0.058, 0), 0.013)  # crossguard
        p.ell(T_IRON, (0, 0.31, 0), (0.026, 0.25, 0.0065))  # blade
        p.ell(T_IRON, (0, 0.56, 0), (0.02, 0.08, 0.006))  # point
    elif kind == "scimitar":
        p.cap(T_LEATHER, (0, -0.1, 0), (0, 0.04, 0), 0.016)
        p.ball(T_BRONZE, (0, -0.115, 0), 0.023)
        p.cap(T_BRONZE, (-0.075, 0.075, 0), (0.075, 0.075, 0), 0.016)
        for (x, y, a, w) in ((0.007, 0.165, -0.11, 0.026), (0.036, 0.291, -0.34, 0.03),
                             (0.092, 0.407, -0.56, 0.033), (0.173, 0.508, -0.79, 0.031)):
            p.ell(T_IRON, (x, y, 0), (w, 0.08, 0.0065), rot=_rot_z(a))
        p.ell(T_IRON, (0.245, 0.572, 0), (0.02, 0.055, 0.006), rot=_rot_z(-0.95))
    elif kind == "arrow":
        p.cap(T_WOOD, (0, -0.07, 0), (0, 0.44, 0), 0.0065)
        p.ell(T_IRON, (0, 0.465, 0), (0.013, 0.036, 0.0065))  # bodkin
        p.ell(T_ACCENT, (0, -0.02, 0), (0.02, 0.05, 0.004))  # fletching vanes
        p.ell(T_ACCENT, (0, -0.02, 0), (0.004, 0.05, 0.02))
    elif kind == "shield":
        p.ell(T_WOOD, (0, 0, 0), (0.24, 0.24, 0.02))  # planks
        p.ell(T_ACCENT, (0, 0, 0.0), (0.165, 0.165, 0.03))  # painted livery field (steep edge)
        for k in range(20):  # leather-bound rim
            a, b = k / 20 * 2 * math.pi, (k + 1) / 20 * 2 * math.pi
            p.cap(T_LEATHER, (math.cos(a) * 0.238, math.sin(a) * 0.238, 0), (math.cos(b) * 0.238, math.sin(b) * 0.238, 0), 0.013)
        p.ball(T_IRON, (0, 0, 0.022), 0.045)  # boss
    elif kind == "bow":
        tip_y, tip_z, belly_z = 0.5, -0.12, 0.11

        def bez(t):
            u = 1 - t
            return (0.0, (t * t - u * u) * tip_y, (u * u + t * t) * tip_z + 2 * u * t * belly_z)
        n = 10
        for i in range(n):
            a, b = bez(i / n), bez((i + 1) / n)
            mid = abs((i + 0.5) / n - 0.5) * 2  # 0 at the grip .. 1 at a tip
            p.cap(T_WOOD, a, b, 0.017 - 0.008 * mid)
        p.cap(T_STRING, (0, -tip_y, tip_z), (0, tip_y, tip_z), 0.004)
        p.cap(T_LEATHER, (0, -0.07, -0.004), (0, 0.07, -0.004), 0.02)  # grip wrap
    return p, 320 if kind in ("shield", "bow", "scimitar") else 220


TOOLS = ("axe", "hoe", "pick", "sword", "scimitar", "arrow", "shield", "bow")
BEARDS = ("full", "short", "moustache")
ADULT_FACES = ("a", "b", "c")
PARTS = (
    [scalp_ref, skirt_ref, hips, hips_robe, hips_apron, hips_tabard, torso, torso_apron, torso_guard, torso_archer,
     torso_cloak, torso_sash, neck, thigh, (lambda: shin(False)), (lambda: shin(True)), (lambda: foot(False)),
     (lambda: foot(True))]
    + [(lambda v=v: head(v)) for v in FACES]
    + [(lambda s=s: hair(s)) for s in ("crop", "shag", "long", "bald", "bowl")]
    + [(lambda s=s, f=f: beard(s, f)) for s in BEARDS for f in ADULT_FACES]
    + [(lambda k=k: hat(k)) for k in ("hood", "cap", "straw", "miner", "helm", "archer", "turban", "warhelm", "headwrap")]
    + [(lambda sx=sx: upper_arm(sx)) for sx in (-1, 1)]
    + [(lambda sx=sx: pauldron(sx)) for sx in (-1, 1)]
    + [(lambda sx=sx, s=s: forearm(sx, s)) for sx in (-1, 1) for s in (False, True)]
    + [(lambda: bracer(-1))]
    + [(lambda k=k: tool(k)) for k in TOOLS]
)

# Finer metaball grid for the small parts.
FINE = ("ref_scalp", "hu_head", "hu_hair", "hu_beard", "hu_hat", "hu_forearm", "hu_bracer", "hu_foot", "hu_pauldron")


# ─────────────────────────────────────────────────────────────── preview (Workbench lineup)
PREVIEW_COLS = {
    SKIN: (0.85, 0.62, 0.48), LIP: (0.55, 0.3, 0.28), EYE: (0.08, 0.06, 0.05), HAIR: (0.25, 0.16, 0.1),
    TUNIC: (0.35, 0.5, 0.7), TRIM: (0.2, 0.3, 0.42), TROUSER: (0.25, 0.2, 0.15), LEATHER: (0.32, 0.23, 0.17),
    BOOT: (0.18, 0.13, 0.1), METAL: (0.72, 0.74, 0.78), HEADCLOTH: (0.55, 0.45, 0.3), BAND: (0.3, 0.22, 0.15),
    TABARD: (0.2, 0.3, 0.6), FLETCH: (0.9, 0.8, 0.4), CLOAK: (0.75, 0.65, 0.45), HELM: (0.7, 0.72, 0.76),
}


def joints(sdx=SDX, hdx=HDX):
    """Rest-pose joint positions (game coords) of the biped rig."""
    hp = Vector((0, 1.05 - 0.06, 0))
    t = hp + Vector((0, 0.15, 0))
    nk = t + Vector((0, 0.35, 0))
    j = {"hips": hp, "torso": t, "neck": nk, "head": nk + Vector((0, 0.08, 0))}
    for s, sx in (("l", -1), ("r", 1)):
        sh = t + Vector((sx * sdx, 0.27, 0.01))
        j[f"sh_{s}"] = sh
        j[f"el_{s}"] = sh + Vector((0, -0.3, 0))
        hj = hp + Vector((sx * hdx, -0.05, 0))
        j[f"hip_{s}"] = hj
        j[f"knee_{s}"] = hj + Vector((0, -0.4, 0))
        j[f"foot_{s}"] = hj + Vector((0, -0.85, 0))
    return j


def outfit(look):
    """(joint -> [part names]) for a preview figure — a subset of the game's assembly rules."""
    face, hair_s, beard_s, hat_s, extra = look
    head = [f"hu_head_{face}"]
    if hair_s:
        head.append(f"hu_hair_{hair_s}")
    if beard_s:
        head.append(f"hu_beard_{beard_s}_{face}")
    if hat_s:
        head.append(f"hu_hat_{hat_s}")
    o = {
        "hips": ["hu_hips"], "torso": ["hu_torso"], "neck": ["hu_neck"], "head": head,
        "sh_l": ["hu_upper_arm_l"], "sh_r": ["hu_upper_arm_r"],
        "el_l": ["hu_forearm_bare_l"], "el_r": ["hu_forearm_bare_r"],
        "hip_l": ["hu_thigh"], "hip_r": ["hu_thigh"], "knee_l": ["hu_shin"], "knee_r": ["hu_shin"],
        "foot_l": ["hu_foot"], "foot_r": ["hu_foot"],
    }
    if "apron" in extra:
        o["torso"].append("hu_torso_apron")
        o["hips"].append("hu_hips_apron")
    if "guard" in extra:
        o["torso"].append("hu_torso_guard")
        o["hips"].append("hu_hips_tabard")
        o["sh_l"].append("hu_pauldron_l")
        o["sh_r"].append("hu_pauldron_r")
    if "archer" in extra:
        o["torso"].append("hu_torso_archer")
        o["el_l"].append("hu_bracer_l")
    if "desert" in extra:
        o["torso"] += ["hu_torso_cloak", "hu_torso_sash"]
        o["hips"].append("hu_hips_robe")
        o["knee_l"] = o["knee_r"] = ["hu_shin_wrap"]
        o["foot_l"] = o["foot_r"] = ["hu_foot_sandal"]
    if "sleeve" in extra or "guard" in extra:
        o["el_l"] = ["hu_forearm_sleeve_l"] + o["el_l"][1:]
        o["el_r"] = ["hu_forearm_sleeve_r"]
    return o


def preview(objs, out_png):
    by = {o.name: o for o in objs}
    for o in objs:  # region code -> display colour
        me = o.data
        src = me.color_attributes["Col"]
        dst = me.color_attributes.new("Disp", "FLOAT_COLOR", "CORNER")
        vals = [0.0] * (len(src.data) * 4)
        src.data.foreach_get("color", vals)
        out = []
        for i in range(0, len(vals), 4):
            c = PREVIEW_COLS[min(15, int(vals[i] * 16))]
            cav = vals[i + 1]
            out += [c[0] * cav, c[1] * cav, c[2] * cav, 1.0]
        dst.data.foreach_set("color", out)
        me.color_attributes.active_color = dst
        o.hide_render = True
    looks = [
        ("a", "crop", "short", None, ""),
        ("b", "shag", "full", None, "sleeve"),
        ("c", "long", None, "hood", ""),
        ("b", "bald", "full", "straw", "apron"),
        ("a", "crop", "moustache", "miner", ""),
        ("a", "crop", None, "helm", "guard"),
        ("c", "shag", None, "archer", "archer"),
        ("b", "crop", "short", "turban", "desert"),
        ("kid", "bowl", None, None, ""),
    ]
    scene = bpy.context.scene
    j = joints()
    for i, look in enumerate(looks):
        x0 = (i - (len(looks) - 1) / 2) * 0.75
        kid = look[0] == "kid"
        root_s = 0.55 / 0.81 if kid else 1.0
        for jn, names in outfit(look).items():
            for nm in names:
                src = by.get(nm)
                if src is None:
                    print("preview: missing", nm)
                    continue
                dup = src.copy()
                scene.collection.objects.link(dup)
                dup.hide_render = False
                s = (1.55 if kid else 1.06) if jn == "head" else 1.0
                wp = j[jn] * root_s
                dup.location = bl((wp.x + x0, wp.y, wp.z))
                dup.scale = (s * root_s,) * 3
    cam_data = bpy.data.cameras.new("cam")
    cam_data.type = "ORTHO"
    cx, cz, ow = 0.0, 1.1, 7.2
    if os.environ.get("PEOPLE_PREVIEW_CAM"):
        cx, cz, ow = (float(t) for t in os.environ["PEOPLE_PREVIEW_CAM"].split(","))
    cam_data.ortho_scale = ow
    cam = bpy.data.objects.new("cam", cam_data)
    scene.collection.objects.link(cam)
    a = math.radians(float(os.environ.get("PEOPLE_PREVIEW_YAW", "20")))
    cam.location = (cx + math.sin(a) * 10, -math.cos(a) * 10, cz)
    cam.rotation_euler = (math.radians(90), 0, a)
    scene.camera = cam
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "VERTEX"
    scene.render.resolution_x, scene.render.resolution_y = 2400, 1000
    scene.render.filepath = str(out_png)
    bpy.ops.render.render(write_still=True)
    print(f"PREVIEW {out_png}")


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    clear_scene()
    objs = []
    for fn in PARTS:
        part, budget = fn()
        res = 0.0025 if part.name.startswith("hu_tool") else 0.0045 if part.name.startswith(FINE) else 0.008
        ob = build(part, budget, res, export=budget > 0)
        if ob is None:
            continue
        if ob.name.startswith(HEAD_PARTS):
            for v in ob.data.vertices:
                v.co.z -= HEAD_DROP  # Blender Z = game Y
        objs.append(ob)
        print(f"{ob.name}: {sum(len(p.vertices) - 2 for p in ob.data.polygons)} tris")
    export_glb(OUT / "people.glb", objs)
    if argv:
        preview(objs, Path(argv[0]).resolve())
    print("PEOPLE_DONE")
