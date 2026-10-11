"""Above-the-treeline flora for the snow massif, exported to alpine_flora.glb.

Real mountains don't go from spruce forest straight to bare snow: past the tree line come
dwarf mountain pine mats (krummholz, Polish "kosodrzewina": low sprawling multi-stem pines with
snow lying on top), the odd stunted wind-flagged spruce, juniper mats and tough alpine grass
tussocks. Built from the same parts as trees.py (bark tubes + V-folded needle cards on the canopy
atlas), so they share the kit materials (and their snow-dusted twins) and batch with the forest.

  krummholz_a/b      ~0.8-0.9k tris  low pine mat, 0.7-1.1u high, ~3.5u across
  spruce_flag_lod0/1 ~1.2k / 0.14k   stunted spruce (3.2u), crown flagged to the lee (+x), dense skirt
  juniper_a          ~0.2k           creeping juniper mat, 0.35u high
  tussock_a/b        14 tris          alpine grass tussock (undergrowth atlas, straw tint)

Run: blender -b --factory-startup --python tools/blender_forest/alpine_flora.py
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.append(str(HERE))
# trees.py's helpers (grow_path / tube / card / taper / UV cells) without its species export.
exec((HERE / "trees.py").read_text(encoding="utf-8").split("\nSPECIES = {")[0], globals())  # noqa: S102

UW, UH = LAYOUT["undergrowth"]["size"]


def ucell(cell):
    x, y, w, h = cell
    return (x / UW, 1 - (y + h) / UH, (x + w) / UW, 1 - y / UH, w / h)


UV_GRASS = [ucell(c) for c in LAYOUT["undergrowth"]["grass"]]
DWARF_PINE = (0.80, 0.95, 0.90)  # paler blue-green than the forest spruce (reads as scrub, not a dark blob)
JUNIPER = (0.66, 0.80, 0.80)  # blue-grey
BARK = (0.70, 0.64, 0.60)


def krummholz(seed, spread, height, stems):
    """Low prostrate multi-stem pine: stems creep out along the ground, tips turn upward,
    needle tufts cover the top as one dense dome-shaded mat."""
    rng = np.random.default_rng(seed)
    b = Builder()
    mats = ["bark_pine", "canopy"]
    crown_c = Vector((0, 0, height * 0.15))
    crown_r = Vector((spread, spread, height))
    az0 = rng.uniform(0, 6.3)
    for i in range(stems):
        az = az0 + i * 2 * math.pi / stems + rng.uniform(-0.35, 0.35)
        L = spread * rng.uniform(0.55, 1.15)  # ragged outline, not a disc
        d = Vector((math.cos(az), math.sin(az), rng.uniform(0.08, 0.22)))
        pts = grow_path((0, 0, 0.03), d, L, 3, rng, bend=0.12, gravity=0.10)
        tube(b, Limb(pts, taper(4, 0.045, 0.014), 1), 3, 0, BARK, uv_phase=rng.uniform(0, 1))
        # Needle tufts along the stem: flat sprays facing up (the mat's top), climbing toward the tip.
        n = 10
        for c in range(n):
            f = (c + 0.5) / n
            k = min(int(f * 3), 2)
            base = pts[k].lerp(pts[k + 1], f * 3 - k)
            base.z = max(base.z, 0.02) + height * 0.45 * math.sin(math.pi * min(f * 1.15, 1.0)) * rng.uniform(0.6, 1.0)
            up = Vector((d.x, d.y, 0)).normalized() * rng.uniform(0.6, 1.0) + Vector((rng.normal() * 0.4, rng.normal() * 0.4, 0.55))
            flat = Vector((0, 0, 1)) + up.cross(Vector((0, 0, 1))).normalized() * rng.uniform(-0.5, 0.5)
            s = rng.uniform(0.6, 0.9)
            card(b, base - up.normalized() * s * 0.3, up, flat, s, UV_CONIFER, 1, crown_c, crown_r, DWARF_PINE, rng,
                 fold=0.2, bend_w=0.75)
            if c % 2 == 1:
                side = up.normalized().cross(flat).normalized()
                card(b, base - up.normalized() * s * 0.25, up, side, s * 0.7, UV_CONIFER, 1, crown_c, crown_r,
                     DWARF_PINE, rng, fold=0.1, bend_w=0.75)
        # Low drooping sprays along the stem hide it from the side (the mat reaches the ground).
        for c in range(3):
            f = 0.3 + 0.25 * c
            k = min(int(f * 3), 2)
            base = pts[k].lerp(pts[k + 1], f * 3 - k) + Vector((0, 0, 0.12))
            out = Vector((d.x, d.y, 0)).normalized()
            up = out.cross(Vector((0, 0, 1))) * rng.choice([-1.0, 1.0]) + Vector((0, 0, -0.35))
            card(b, base, up, out, rng.uniform(0.5, 0.7), UV_CONIFER, 1, crown_c, crown_r, DWARF_PINE, rng,
                 fold=0.15, bend_w=0.6)
        # Ascending tip shoot: two crossed upright tufts.
        tip = pts[-1] + Vector((0, 0, height * 0.25))
        for a in (az, az + math.pi / 2):
            card(b, tip - Vector((0, 0, 0.25)), Vector((d.x * 0.3, d.y * 0.3, 1)), Vector((math.cos(a), math.sin(a), 0)),
                 rng.uniform(0.5, 0.7), UV_CONIFER, 1, crown_c, crown_r, DWARF_PINE, rng, fold=0.1, bend_w=0.6)
    # Dense core: the middle of the mat is the highest, thickest part.
    for _ in range(48):
        r = spread * 0.45 * math.sqrt(rng.uniform(0, 1))
        a = rng.uniform(0, 6.3)
        base = Vector((math.cos(a) * r, math.sin(a) * r, height * rng.uniform(0.35, 0.75)))
        up = Vector((math.cos(a), math.sin(a), 0)) * 0.6 + Vector((rng.normal() * 0.3, rng.normal() * 0.3, 0.7))
        flat = Vector((0, 0, 1)) + up.cross(Vector((0, 0, 1))).normalized() * rng.uniform(-0.6, 0.6)
        card(b, base, up, flat, rng.uniform(0.6, 0.85), UV_CONIFER, 1, crown_c, crown_r, DWARF_PINE, rng,
             fold=0.2, bend_w=0.75)
    snow_cap(b, 0.6)
    return b, mats


def snow_cap(b, k):
    """Tilt the needle cards' normals toward the sky by `k`: the frosted material twin settles
    snow on sky-facing normals, so the mat's top reads as a snow cap over dark needles below."""
    up = Vector((0, 0, 1))
    for i, (idx, uvs, nrms, cols, mat) in enumerate(b.faces):
        if mat == 1:
            b.faces[i] = (idx, uvs, [tuple((Vector(n) * (1 - k) + up * k).normalized()) for n in nrms], cols, mat)


def flagged_spruce(seed, lod, height, trunk_r):
    """Stunted tree-line spruce: a dense krummholz skirt on all sides at the foot, then a bare,
    wind-scoured trunk with short branches only on its lee (+x) side — a flag."""
    rng = np.random.default_rng(seed)
    b = Builder()
    mats = ["bark_pine", "canopy"]
    tsegs = 6 if lod == 0 else 3
    trunk = Limb(grow_path((0, 0, 0), (0.06, 0, 1), height, tsegs, rng, bend=0.05),
                 taper(tsegs + 1, trunk_r, trunk_r * 0.15, 0.9), 0)
    tube(b, trunk, 6 if lod == 0 else 4, 0, BARK, flare=0.3, uv_phase=rng.uniform(0, 1))
    crown_c = Vector((0.3, 0, height * 0.4))
    crown_r = Vector((1.2, 1.0, height * 0.55))
    golden = 2.39996
    az = rng.uniform(0, 6.3)
    # Skirt: long drooping limbs all round (snow-protected in winter, so they survive the wind).
    nskirt = 14 if lod == 0 else 6
    for i in range(nskirt):
        az += golden
        z = rng.uniform(0.15, 0.6)
        d = Vector((math.cos(az), math.sin(az), -0.12)).normalized()
        L = rng.uniform(0.9, 1.4)
        p0 = Vector((0, 0, z))
        pts = grow_path(p0, d, L, 2, rng, bend=0.08, gravity=-0.05)
        if lod == 0:
            tube(b, Limb(pts, taper(3, trunk_r * 0.2, trunk_r * 0.06), 1), 3, 0, BARK)
        nc = 4 if lod == 0 else 2
        for c in range(nc):
            base = p0.lerp(pts[-1], 0.1 + 0.8 * c / nc)
            up = (pts[-1] - p0).normalized()
            card(b, base, up, Vector((0, 0, 1)), rng.uniform(0.7, 0.95) * (1.0 if lod == 0 else 1.3), UV_CONIFER, 1,
                 crown_c, crown_r, DWARF_PINE, rng, fold=0.2, bend_w=0.6)
    # Flag: short limbs only toward +x (azimuth within ±70° of the lee), shortening upward.
    z = height * 0.3
    while z < height * 0.92:
        t = (z - height * 0.3) / (height * 0.62)
        for _ in range(5 if lod == 0 else 3):
            a = rng.uniform(-1.25, 1.25)
            d = Vector((math.cos(a), math.sin(a), rng.uniform(-0.15, 0.1))).normalized()
            p0 = Vector((trunk_r * 0.5 + 0.06 * t, 0, z))
            L = (0.95 - 0.55 * t) * rng.uniform(0.8, 1.15)
            pts = [p0, p0 + d * L]
            if lod == 0:
                tube(b, Limb(pts, [trunk_r * 0.2, trunk_r * 0.06], 1), 3, 0, BARK)
            base = p0 + d * L * 0.2
            card(b, base, d, Vector((0, 0, 1)), L * 0.95 + 0.25, UV_CONIFER, 1, crown_c, crown_r, DWARF_PINE, rng,
                 fold=0.2, bend_w=0.6)
            if lod == 0:
                card(b, base, d, d.cross(Vector((0, 0, 1))), (L * 0.95 + 0.25) * 0.7, UV_CONIFER, 1, crown_c, crown_r,
                     DWARF_PINE, rng, fold=0.1, bend_w=0.6)
        z += (0.28 if lod == 0 else 0.5) * rng.uniform(0.85, 1.15)
    # The odd stub on the windward side (dead, no needles), and a ragged leader.
    if lod == 0:
        for z in (height * 0.45, height * 0.7):
            a = math.pi + rng.uniform(-0.6, 0.6)
            p0 = Vector((0, 0, z))
            tube(b, Limb([p0, p0 + Vector((math.cos(a), math.sin(a), 0.1)) * 0.3], [trunk_r * 0.15, trunk_r * 0.05], 1),
                 3, 0, BARK)
    top = trunk.pts[-1]
    card(b, top - Vector((0, 0, 0.45)), Vector((0.25, 0, 1)), Vector((0, 1, 0)), 0.6, UV_CONIFER, 1, crown_c, crown_r,
         DWARF_PINE, rng, fold=0.1, bend_w=0.5)
    return b, mats


def juniper(seed):
    """Creeping juniper: a few prostrate stems under a flat, blue-grey mat of needle sprays."""
    rng = np.random.default_rng(seed)
    b = Builder()
    mats = ["bark_pine", "canopy"]
    crown_c = Vector((0, 0, 0.0))
    crown_r = Vector((1.0, 1.0, 0.4))
    for _ in range(34):
        r = 0.95 * math.sqrt(rng.uniform(0, 1))
        a = rng.uniform(0, 6.3)
        base = Vector((math.cos(a) * r * 0.6, math.sin(a) * r * 0.6, rng.uniform(0.05, 0.2) * (1.2 - r)))
        up = Vector((math.cos(a), math.sin(a), 0.25 + rng.uniform(0, 0.25)))
        flat = Vector((0, 0, 1)) + up.cross(Vector((0, 0, 1))).normalized() * rng.uniform(-0.4, 0.4)
        card(b, base, up, flat, rng.uniform(0.5, 0.75), UV_CONIFER, 1, crown_c, crown_r, JUNIPER, rng,
             fold=0.25, bend_w=0.8)
    for i in range(3):
        a = rng.uniform(0, 6.3)
        pts = grow_path((0, 0, 0.02), (math.cos(a), math.sin(a), 0.05), 0.7, 2, rng, bend=0.1)
        tube(b, Limb(pts, taper(3, 0.03, 0.012), 1), 3, 0, BARK)
    snow_cap(b, 0.5)
    return b, mats


def tussock(seed, size, tint):
    """Alpine grass tussock: a tight crown of blade cards fountaining out, straw over green.
    Normals mostly UP (like the kit grass) so it lights like the ground and catches snow on top
    instead of reading as a dark speck on the snowfield."""
    rng = np.random.default_rng(seed)
    b = Builder()
    mats = ["undergrowth"]
    up_n = Vector((0, 0, 1))
    n = 7
    a0 = rng.uniform(0, math.pi)
    for i in range(n):
        a = a0 + i * math.pi / n + rng.uniform(-0.2, 0.2)
        x0, vb, x1, vt, _ = UV_GRASS[rng.integers(len(UV_GRASS))]
        w = size * rng.uniform(0.7, 0.9)
        h = size * rng.uniform(0.55, 0.75)
        side = Vector((math.cos(a), math.sin(a), 0)) * w * 0.5
        face_n = Vector((-math.sin(a), math.cos(a), 0))
        # Splay: the card's top edge leans out along its facing (alternating), a fountain not a fan.
        lean = face_n * (h * rng.uniform(0.25, 0.5)) * (1 if i % 2 else -1)
        p = [-side - up_n * 0.03, side - up_n * 0.03, side + up_n * h + lean, -side + up_n * h + lean]
        uvs = [(x0, vb), (x1, vb), (x1, vt), (x0, vt)]
        cb = tuple(c * 0.6 for c in tint)
        ns = [(face_n * 0.25 + up_n * 0.75).normalized()] * 4
        b.face(tuple(b.v(q) for q in p), uvs, ns, [cb, cb, tint, tint], 0)
    return b, mats


MODELS = {
    "krummholz_a": lambda: krummholz(201, spread=2.1, height=0.85, stems=8),
    "krummholz_b": lambda: krummholz(211, spread=1.75, height=0.7, stems=7),
    "spruce_flag_lod0": lambda: flagged_spruce(223, 0, height=3.2, trunk_r=0.075),
    "spruce_flag_lod1": lambda: flagged_spruce(223, 1, height=3.2, trunk_r=0.075),
    "juniper_a": lambda: juniper(231),
    "tussock_a": lambda: tussock(241, 0.7, (1.35, 1.15, 0.70)),
    "tussock_b": lambda: tussock(251, 0.6, (1.25, 1.12, 0.75)),
}

clear_scene()
objs = []
report = {}
for name, fn in MODELS.items():
    b, mats = fn()
    objs.append(b.build(name, mats))
    report[name] = b.tris()
export_glb(OUT / "alpine_flora.glb", objs)
for k, v in report.items():
    print(f"{k}: {v} tris")
print("ALPINE_FLORA_DONE")
