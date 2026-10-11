"""The swamp's own flora, exported to swamp_flora.glb (+ its bark sets and card atlas).

The swamp must not share a single tree with the forest. A southern blackwater swamp reads as:
bald cypresses standing on flared, buttressed, fluted bases with knees poking out of the muck,
tall bare trunks carrying a FLAT-topped feathery crown, grey Spanish moss hanging off every limb;
drooping willows on the banks; drowned, bleached, broken snags. All of it on its own scans:

  bark_cypress  Poly Haven `metasequoia_bark` (dawn redwood - bald cypress's closest relative,
                the same fibrous, stringy, ridged bark), darkened toward the waterline in vertex colour
  bark_willow   Poly Haven `bark_willow_02` (deep diamond furrows)
  bark_snag     the willow scan bleached to silver-grey (sun-dried, barkless drowned wood)
  swamp_cards   2048x1024 procedural card atlas (foliage card material, wind path):
                [0] cypress frond (flat two-ranked linear leaves), [1] Spanish moss festoon,
                [2] willow strand (pendulous twig, lanceolate leaves), [3] top: cattail + sedge
                clump, bottom: lily pads + duckweed (seen from above)

  cypress_a/b_lod0/1  ~1.5k / ~0.35k tris
  willow_a_lod0/1     ~1.5k / ~0.35k
  snag_a/b_lod0/1     ~0.5k / ~0.15k (no leaves)
  knees_a / knees_b   cypress knees around a rotten fluted stump / a knee cluster (static)
  sw_cattail_a/b, sw_sedge_a, sw_lily_a  swamp cover cards

Run: blender -b --factory-startup --python tools/blender_forest/swamp_flora.py
then pack: cargo run --release --example pack_forest_textures (only the PNGs on disk are packed).
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.append(str(HERE))
# trees.py's helpers (grow_path / tube / card / taper / frames) without its species export.
exec((HERE / "trees.py").read_text(encoding="utf-8").split("\nSPECIES = {")[0], globals())  # noqa: S102
from common import bleed_alpha, grade, ph_tex, save, write_pbr_set  # noqa: E402

# ------------------------------------------------------------------ bark sets
write_pbr_set("bark_cypress", ph_tex("metasequoia_bark", "diff"), ph_tex("metasequoia_bark", "nor_gl"),
              ph_tex("metasequoia_bark", "rough"), ao=ph_tex("metasequoia_bark", "ao"),
              disp=ph_tex("metasequoia_bark", "disp"), sat=0.70, gain=1.25)
write_pbr_set("bark_willow", ph_tex("bark_willow_02", "diff"), ph_tex("bark_willow_02", "nor_gl"),
              ph_tex("bark_willow_02", "rough"), ao=ph_tex("bark_willow_02", "ao"),
              disp=ph_tex("bark_willow_02", "disp"), sat=0.75, gain=1.30)
write_pbr_set("bark_snag", ph_tex("bark_willow_02", "diff"), ph_tex("bark_willow_02", "nor_gl"),
              ph_tex("bark_willow_02", "rough"), ao=ph_tex("bark_willow_02", "ao"),
              disp=ph_tex("bark_willow_02", "disp"), sat=0.12, gain=2.1)

# ------------------------------------------------------------------ card atlas
crng = np.random.default_rng(17)


class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.rgb = np.zeros((h, w, 3), np.float32)
        self.a = np.zeros((h, w), np.float32)
        self.n = np.zeros((h, w, 3), np.float32)
        self.n[..., 2] = 1.0

    def over(self, y0, y1, x0, x1, rgb, a, n):
        aa = a[..., None]
        self.rgb[y0:y1, x0:x1] = rgb * aa + self.rgb[y0:y1, x0:x1] * (1 - aa)
        self.n[y0:y1, x0:x1] = n * aa + self.n[y0:y1, x0:x1] * (1 - aa)
        self.a[y0:y1, x0:x1] = a + self.a[y0:y1, x0:x1] * (1 - a)

    def finish(self):
        nrm = self.n / (np.linalg.norm(self.n, axis=-1, keepdims=True) + 1e-6)
        rgb = bleed_alpha(self.rgb, self.a)
        return np.concatenate([rgb, self.a[..., None]], -1), nrm * 0.5 + 0.5


def stroke(cv, p0, p1, w0, w1, color, nscale=0.9):
    """Tapered round stroke p0 -> p1 (px, image rows down), cylindrical normal."""
    (x0, y0), (x1, y1) = p0, p1
    m = max(w0, w1) + 2
    bx0, bx1 = int(max(min(x0, x1) - m, 0)), int(min(max(x0, x1) + m, cv.w))
    by0, by1 = int(max(min(y0, y1) - m, 0)), int(min(max(y0, y1) + m, cv.h))
    if bx1 <= bx0 or by1 <= by0:
        return
    ys, xs = np.mgrid[by0:by1, bx0:bx1].astype(np.float32)
    d = np.array([x1 - x0, y1 - y0], np.float32)
    L2 = max(float(d @ d), 1e-4)
    t = np.clip(((xs - x0) * d[0] + (ys - y0) * d[1]) / L2, 0, 1)
    ox, oy = xs - (x0 + d[0] * t), ys - (y0 + d[1] * t)
    dist = np.sqrt(ox * ox + oy * oy)
    w = (w0 + (w1 - w0) * t) * 0.5
    a = np.clip(w + 0.6 - dist, 0, 1)
    if a.max() <= 0:
        return
    side = np.clip((ox * -d[1] + oy * d[0]) / (math.sqrt(L2) * np.maximum(w, 0.3)), -1, 1)
    perp = np.array([-d[1], -d[0]], np.float32) / math.sqrt(L2)
    nxy = perp[None, None, :] * (side * nscale)[..., None]
    nz = np.sqrt(np.clip(1 - (side * nscale) ** 2, 0.05, 1))
    n = np.concatenate([nxy, nz[..., None]], -1)
    rgb = np.broadcast_to(np.asarray(color, np.float32), (*a.shape, 3)) * (0.75 + 0.25 * nz[..., None])
    cv.over(by0, by1, bx0, bx1, rgb, a, n)


def leaf(cv, base, ang, length, width, color):
    """Lanceolate leaf: widens to ~40% then tapers to a point (two tapered strokes)."""
    dx, dy = math.sin(ang), -math.cos(ang)
    mid = (base[0] + dx * length * 0.38, base[1] + dy * length * 0.38)
    tip = (base[0] + dx * length, base[1] + dy * length)
    stroke(cv, base, mid, width * 0.25, width, color, 0.7)
    stroke(cv, mid, tip, width, 0.6, color, 0.7)


def walk(p, ang, length, step, wobble, rng):
    pts = [np.array(p, np.float32)]
    for _ in range(max(int(length / step), 1)):
        ang += rng.normal() * wobble
        pts.append(pts[-1] + np.array([math.sin(ang), -math.cos(ang)], np.float32) * step)
    return pts


def cypress_frond(w=512, h=1024):
    """Bald cypress spray: NOT one fern frond on a stiff midrib, but a soft cloud of many small
    deciduous branchlets ("feathers") fanning loosely out of a hidden twig - each a hair-thin axis
    set with short, fine, flat needles in two ranks. Overlapping feathers at different angles and
    sizes give the soft, hazy, layered texture of a real cypress crown; the twigs are needle-
    coloured so no dark "stem" lines read. Yellow-green to sage, a few rusty-bronze needles."""
    cv = Canvas(w, h)
    # No midrib: ~150 short feathers scattered through a fan-shaped oval, each pointing away from
    # the card's foot (where the twig attaches) with a little scatter - overlapping, so the cell
    # is one soft mass of needles rather than a frond with a readable stem and leaflet rhythm.
    feathers = []
    foot = np.array([w * 0.5, h * 0.97], np.float32)
    for k in range(150):
        r = math.sqrt(crng.uniform(0.02, 1.0))
        th = crng.uniform(0, 2 * math.pi)
        base = np.array([w * 0.5 + math.cos(th) * r * w * 0.36, h * 0.52 + math.sin(th) * r * h * 0.40], np.float32)
        out = base - foot
        ang = math.atan2(out[0], -out[1]) + crng.normal() * 0.45
        L = h * crng.uniform(0.07, 0.14)
        pts = walk(tuple(base), ang, L, 7, 0.08, crng)
        pts = [np.clip(q, [20, 20], [w - 20, h - 6]).astype(np.float32) for q in pts]
        feathers.append((pts, crng.uniform(0.75, 1.1)))
    needles = []
    for tw, sc in feathers:
        n = len(tw)
        for i, (a, b) in enumerate(zip(tw[:-1], tw[1:])):
            stroke(cv, a, b, 1.6, 1.3, (0.27, 0.32, 0.14), 0.5)
            d = b - a
            seg = float(np.linalg.norm(d))
            dir_ang = math.atan2(d[0], -d[1])
            taper_k = 1.0 - 0.55 * (i / max(n - 1, 1)) ** 1.5  # shorter needles toward the tip
            for j in range(max(int(seg / 2.0), 1)):
                p = a + d * (j + 0.5) / max(int(seg / 2.0), 1)
                for s2 in (-1, 1):
                    needles.append((p, dir_ang + s2 * crng.uniform(1.0, 1.35), crng.uniform(12, 19) * sc * taper_k))
    crng.shuffle(needles)
    for idx, (p, ang, L) in enumerate(needles):
        g = crng.uniform(0, 1)
        lit = 0.70 + 0.40 * idx / len(needles)
        if crng.random() < 0.05:
            col = np.array([0.46, 0.32, 0.14]) * lit  # an early-bronzing needle
        else:
            col = np.array([0.30 + 0.12 * g, 0.40 + 0.08 * g, 0.14 + 0.06 * g]) * lit
        dx, dy = math.sin(ang), -math.cos(ang)
        stroke(cv, tuple(p), (p[0] + dx * L, p[1] + dy * L), 2.0, 0.9, col, 0.55)
    rgba, nrm = cv.finish()
    rgba[..., :3] = grade(rgba[..., :3], sat=1.05, gain=1.08)
    return rgba, nrm


def spanish_moss(w=512, h=1024):
    """Spanish moss festoon: hundreds of thin, kinked, curly grey-green strands hanging from the
    limb (the card's base = the image bottom), thinning out toward ragged tips."""
    cv = Canvas(w, h)
    # Pale silver-grey-green beards: a few narrow tufts gripping the limb (the card's base), whose
    # thick-ish strands fall nearly straight and fan out a little as they hang - long ragged
    # curtains that read from mid-distance, never a rectangle filling the card.
    tufts = crng.uniform(0.36, 0.64, 4)
    for i in range(440):
        x = w * (tufts[i % 4] + crng.normal() * 0.06)
        L = h * crng.uniform(0.35, 0.98) ** 0.7
        ang = crng.normal() * 0.05 + (x / w - 0.5) * 0.12
        pts = walk((x, h * 0.995), ang, L, 9, 0.035, crng)
        g = crng.uniform(0, 1)
        base = np.array([0.62 + 0.10 * g, 0.66 + 0.09 * g, 0.56 + 0.07 * g]) * crng.uniform(0.78, 1.05)
        n = len(pts)
        for k, (a, b) in enumerate(zip(pts[:-1], pts[1:])):
            f = k / n
            stroke(cv, a, b, 5.0 - 2.6 * f, 4.8 - 2.6 * f, base * (0.85 + 0.25 * f), 0.8)
            if k % 3 == 1 and crng.random() < 0.5:  # little curly side wisps
                tw = walk(b, crng.normal() * 1.2, crng.uniform(12, 30), 5, 0.6, crng)
                for c, e in zip(tw[:-1], tw[1:]):
                    stroke(cv, c, e, 1.6, 1.0, base * 0.95, 0.8)
    rgba, nrm = cv.finish()
    return rgba, nrm


def willow_strand(w=512, h=1024):
    """Weeping willow: two or three pendulous whips (attached at the image bottom) set with narrow
    lanceolate leaves pointing along the whip - fresh yellow-green with silvery undersides."""
    cv = Canvas(w, h)
    leaves = []
    for s in range(3):
        x = w * (0.32 + 0.18 * s + crng.normal() * 0.03)
        pts = walk((x, h * 0.995), crng.normal() * 0.08, h * crng.uniform(0.8, 0.95), 20, 0.05, crng)
        for a, b in zip(pts[:-1], pts[1:]):
            stroke(cv, a, b, 3.5, 3.0, (0.36, 0.30, 0.16))
        for a, b in zip(pts[1:-1], pts[2:]):
            d = b - a
            dir_ang = math.atan2(d[0], -d[1])
            for side in (-1, 1):
                for j in range(2):
                    p = a + d * crng.uniform(0, 1)
                    leaves.append((p, dir_ang + side * crng.uniform(0.25, 0.65), crng.uniform(70, 105)))
    crng.shuffle(leaves)
    for idx, (p, ang, L) in enumerate(leaves):
        g = crng.uniform(0, 1)
        silver = crng.random() < 0.3
        col = np.array([0.42, 0.50, 0.34]) if silver else np.array([0.30 + 0.10 * g, 0.44 + 0.08 * g, 0.12 + 0.04 * g])
        leaf(cv, tuple(p), ang, L, crng.uniform(9, 12), col * (0.65 + 0.4 * idx / len(leaves)))
    rgba, nrm = cv.finish()
    rgba[..., :3] = grade(rgba[..., :3], sat=1.1, gain=1.05)
    return rgba, nrm


def cattail_clump(w=512, h=512):
    """Cattails + sedge: a fan of long strap blades from the base, two-three brown cattail heads."""
    cv = Canvas(w, h)
    for i in range(46):
        x = w * (0.5 + crng.normal() * 0.07)
        ang = crng.normal() * 0.32
        pts = walk((x, h * 0.995), ang, h * crng.uniform(0.45, 0.95), 18, 0.07 + abs(ang) * 0.1, crng)
        g = crng.uniform(0, 1)
        col = np.array([0.26 + 0.12 * g, 0.36 + 0.08 * g, 0.14 + 0.04 * g])
        if crng.random() < 0.18:
            col = np.array([0.52, 0.45, 0.28])  # a dead straw blade
        n = len(pts)
        for k, (a, b) in enumerate(zip(pts[:-1], pts[1:])):
            f = k / n
            stroke(cv, a, b, 9 * (1 - f) + 1.5, 9 * (1 - (k + 1) / n) + 1.0, col * (0.7 + 0.35 * f), 0.6)
    for i in range(3):
        x = w * (0.42 + 0.08 * i + crng.normal() * 0.02)
        top = h * crng.uniform(0.04, 0.22)
        stroke(cv, (x, h * 0.99), (x + crng.normal() * 6, top + 40), 4, 3, (0.34, 0.36, 0.18), 0.6)
        stroke(cv, (x, top + 115), (x, top + 20), 17, 15, (0.30, 0.18, 0.09), 0.95)  # the brown spike
        stroke(cv, (x, top + 20), (x, top), 2.5, 1.5, (0.40, 0.34, 0.20), 0.6)
    return cv.finish()


def lily_pads(w=512, h=512):
    """Lily pads + duckweed seen from above: notched round pads with radial veins, red-edged."""
    cv = Canvas(w, h)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    for i in range(380):  # duckweed specks first (under the pads)
        cx, cy = crng.normal(w * 0.5, w * 0.2), crng.normal(h * 0.5, h * 0.2)
        r = crng.uniform(2.5, 5.0)
        x0, x1, y0, y1 = int(max(cx - 7, 0)), int(min(cx + 7, w)), int(max(cy - 7, 0)), int(min(cy + 7, h))
        if x1 <= x0 or y1 <= y0:
            continue
        d = np.sqrt((xs[y0:y1, x0:x1] - cx) ** 2 + (ys[y0:y1, x0:x1] - cy) ** 2)
        a = np.clip(r + 0.6 - d, 0, 1)
        g = crng.uniform(0, 1)
        rgb = np.broadcast_to(np.array([0.36 + 0.1 * g, 0.50 + 0.08 * g, 0.12]), (*a.shape, 3))
        n = np.broadcast_to(np.array([0, 0, 1.0]), (*a.shape, 3))
        cv.over(y0, y1, x0, x1, rgb, a, n)
    for i in range(7):
        cx, cy = crng.uniform(w * 0.2, w * 0.8), crng.uniform(h * 0.2, h * 0.8)
        r = crng.uniform(48, 92)
        notch = crng.uniform(0, 2 * math.pi)
        dx, dy = xs - cx, ys - cy
        d = np.sqrt(dx * dx + dy * dy)
        th = np.arctan2(dy, dx)
        dth = np.abs((th - notch + math.pi) % (2 * math.pi) - math.pi)
        a = np.clip(r + 0.6 - d, 0, 1) * np.clip((dth - 0.12 * (1 - d / r) - 0.02) * 40, 0, 1)
        y0, y1 = int(max(cy - r - 2, 0)), int(min(cy + r + 2, h))
        x0, x1 = int(max(cx - r - 2, 0)), int(min(cx + r + 2, w))
        a = a[y0:y1, x0:x1]
        dd = (d / r)[y0:y1, x0:x1]
        vein = 0.92 + 0.08 * np.cos(th[y0:y1, x0:x1] * 22) * np.clip(dd * 1.5, 0, 1)
        g = crng.uniform(0, 1)
        base = np.array([0.20 + 0.06 * g, 0.33 + 0.06 * g, 0.10])
        rim = np.clip((dd - 0.9) * 10, 0, 1)[..., None]
        rgb = (base * (1 - rim) + np.array([0.42, 0.20, 0.10]) * rim) * vein[..., None] * (0.85 + 0.25 * (1 - dd))[..., None]
        # Cupped pad: normal tilts outward toward the rim.
        nx, ny = (dx / (d + 1e-3))[y0:y1, x0:x1] * dd * 0.35, -(dy / (d + 1e-3))[y0:y1, x0:x1] * dd * 0.35
        n = np.stack([nx, ny, np.ones_like(nx)], -1)
        cv.over(y0, y1, x0, x1, rgb, a, n)
    return cv.finish()


atlas = np.zeros((1024, 2048, 4), np.float32)
atlas_n = np.zeros((1024, 2048, 3), np.float32)
CELLS = {}
for name, fn, x, y, w, h in [("frond", cypress_frond, 0, 0, 512, 1024), ("moss", spanish_moss, 512, 0, 512, 1024),
                             ("willow", willow_strand, 1024, 0, 512, 1024), ("cattail", cattail_clump, 1536, 0, 512, 512),
                             ("lily", lily_pads, 1536, 512, 512, 512)]:
    rgba, nrm = fn(w, h)
    atlas[y:y + h, x:x + w] = rgba
    atlas_n[y:y + h, x:x + w] = nrm
    CELLS[name] = (x, y, w, h)
save(atlas, OUT / "swamp_cards_albedo.png")
save(atlas_n, OUT / "swamp_cards_normal.png")
SW, SH = 2048, 1024


def scell(name):
    x, y, w, h = CELLS[name]
    return (x / SW, 1 - (y + h) / SH, (x + w) / SW, 1 - y / SH, w / h)


UV_FROND, UV_MOSS, UV_WILLOW, UV_CATTAIL, UV_LILY = (scell(n) for n in ("frond", "moss", "willow", "cattail", "lily"))
CARDS = 1  # material slot of swamp_cards in every model below

# ------------------------------------------------------------------ geometry
MOSS_TINT = (0.92, 0.95, 0.88)


def fluted_trunk(b, rng, height, r_top_frac, trunk_r, sides, zs, buttress, lean, tint, mat=0, jagged=0.0):
    """A trunk swept up through rings at heights `zs` whose radius flares hugely at the foot and
    is pushed out into irregular buttress lobes (the cypress / tupelo foot), with fine vertical
    fluting fading up the trunk. Vertex colour: dark wet waterline + algae at the base."""
    lobes = [(rng.uniform(0, 2 * math.pi), rng.uniform(0.6, 1.0), rng.uniform(0.35, 0.6)) for _ in range(rng.integers(5, 8))]
    ph = rng.uniform(0, 6.3)
    bend = Vector((rng.normal(), rng.normal(), 0)) * 0.12
    u_rep = max(1, round(2 * math.pi * trunk_r * 2.0 / BARK_TILE * 1.6))
    rings = []
    centres = []
    for i, z in enumerate(zs):
        f = z / height
        c = Vector((lean.x * z + bend.x * math.sin(f * 3.0), lean.y * z + bend.y * math.sin(f * 3.0), z))
        centres.append(c)
        r = trunk_r * (1 - (1 - r_top_frac) * f ** 0.9) * (1 + buttress * math.exp(-z / 0.42))
        flute = buttress * 0.9 * math.exp(-z / 0.38)
        fine = 0.07 * math.exp(-z / 2.0)
        ring = []
        for s in range(sides + 1):
            a = 2 * math.pi * (s % sides) / sides
            lobe = sum(amp * math.exp(-(((a - a0 + math.pi) % (2 * math.pi) - math.pi) / wd) ** 2) for a0, amp, wd in lobes)
            rr = r * (1 + flute * (lobe - 0.45) + fine * math.sin(a * 9 + ph))
            top = z
            if jagged and i == len(zs) - 1:
                top = z + jagged * (0.5 + 0.5 * math.sin(a * 3 + ph)) * rng.uniform(0.3, 1.0)
            dirv = Vector((math.cos(a), math.sin(a), 0))
            p = Vector((c.x, c.y, top)) + dirv * max(rr, r * 0.35)
            # Wet / algae band: dark mud to ~0.35u, greenish stain to ~0.9u.
            wet = 0.5 + 0.5 * min(max((z - 0.1) / 0.8, 0.0), 1.0)
            col = (tint[0] * wet * (0.92 if z < 0.9 else 1.0), tint[1] * wet, tint[2] * wet * (0.85 if z < 0.9 else 1.0))
            ring.append((b.v(p), dirv, (s / sides * u_rep, z / BARK_TILE), col))
        rings.append(ring)
    for i in range(len(rings) - 1):
        for s in range(sides):
            q = (rings[i][s], rings[i][s + 1], rings[i + 1][s + 1], rings[i + 1][s])
            b.face(tuple(e[0] for e in q), [e[2] for e in q], [e[1] for e in q], [e[3] for e in q], mat)
    top = rings[-1]
    cen = b.v(centres[-1] + Vector((0, 0, jagged * 0.2)))
    for s in range(sides):
        a, bb = top[s], top[s + 1]
        b.face((a[0], bb[0], cen), [a[2], bb[2], (0.5, top[0][2][1])], [a[1], bb[1], (0, 0, 1)], [a[3], bb[3], a[3]], mat)
    return centres


def hang_moss(b, rng, p, length, crown_c, crown_r, lod, n_cross):
    """A Spanish-moss festoon: the card's base (image bottom) at the limb, hanging straight down."""
    down = Vector((rng.normal() * 0.08, rng.normal() * 0.08, -1)).normalized()
    a0 = rng.uniform(0, math.pi)
    # The crown's self-occlusion darkening (inner + lower cards) would turn the pale beards into
    # dark drapes under the canopy: shade them as outer, sky-lit foliage instead (a virtual crown
    # centre far below the festoon -> full brightness, normals bent toward the sky).
    sky_c = p + Vector((0, 0, -50.0))
    sky_r = Vector((1.0, 1.0, 1.0))
    for k in range(n_cross):
        a = a0 + k * math.pi / n_cross
        nrm = Vector((math.cos(a), math.sin(a), 0))
        card(b, p + Vector((0, 0, 0.03)), down, nrm, length, UV_MOSS, CARDS, sky_c, sky_r, MOSS_TINT, rng,
             fold=0.12, bend_w=0.25)


def cypress(seed, lod, height, trunk_r, crown_w, tint, leaf_tint, mossy=1.0):
    rng = np.random.default_rng(seed)
    b = Builder()
    mats = ["bark_cypress", "swamp_cards"]
    lean = Vector((rng.normal() * 0.02, rng.normal() * 0.02, 0))
    trunk_h = height * 0.86
    zs = ([0.0, 0.06, 0.15, 0.28, 0.45, 0.68, 1.0, 1.5] if lod == 0 else [0.0, 0.2, 0.6]) + \
        list(np.linspace(2.1 if lod == 0 else 1.4, trunk_h, 5 if lod == 0 else 3))
    centres = fluted_trunk(b, rng, trunk_h, 0.28, trunk_r, 16 if lod == 0 else 8, zs, 1.5, lean, tint)

    def on_trunk(z):
        z = min(z, trunk_h)
        for c0, c1 in zip(centres[:-1], centres[1:]):
            if c0.z <= z <= c1.z:
                return c0.lerp(c1, (z - c0.z) / max(c1.z - c0.z, 1e-4))
        return centres[-1]

    # Limbs only in the top ~40%: long horizontal, gently upturned, all ending near one height -
    # the flat-topped, wide, layered crown; the top of the trunk splits into spreading leaders.
    limbs = []
    n_limbs = 9 if lod == 0 else 6
    golden = 2.39996
    az0 = rng.uniform(0, 6.3)
    for i in range(n_limbs):
        t = 0.55 + 0.40 * (i + rng.uniform(0, 0.7)) / n_limbs
        p = on_trunk(height * t)
        az = az0 + i * golden + rng.uniform(-0.3, 0.3)
        reach = crown_w * 0.5 * rng.uniform(0.75, 1.05) * (1.15 - 0.35 * (t - 0.55) / 0.4)
        rise = max(height * 0.97 - p.z, 0.15)
        elev = math.atan2(rise * 0.55, reach)
        d = Vector((math.cos(az) * math.cos(elev), math.sin(az) * math.cos(elev), math.sin(elev)))
        segs = 4 if lod == 0 else 2
        pts = grow_path(p, d, math.hypot(reach, rise * 0.55), segs, rng, bend=0.10, gravity=-0.03)
        r0 = trunk_r * 0.30 * rng.uniform(0.8, 1.1) * (1.1 - 0.5 * (t - 0.55))
        limbs.append(Limb(pts, taper(segs + 1, r0, r0 * 0.25), 1))
    if lod == 0:
        for lm in list(limbs):
            for j in range(2):
                k = rng.integers(1, len(lm.pts) - 1)
                d0 = (lm.pts[k + 1] - lm.pts[k]).normalized()
                side = d0.cross(Vector((0, 0, 1))).normalized() * (1 if j else -1)
                d = (d0 + side * rng.uniform(0.6, 1.0) + Vector((0, 0, 0.15))).normalized()
                pts = grow_path(lm.pts[k], d, (lm.pts[-1] - lm.pts[0]).length * 0.35, 2, rng, bend=0.12, gravity=0.0)
                limbs.append(Limb(pts, taper(3, lm.radii[k] * 0.5, lm.radii[k] * 0.15), 2))
    for lm in limbs:
        tube(b, lm, {1: 6 if lod == 0 else 4, 2: 4}[lm.depth], 0, tint, uv_phase=rng.uniform(0, 1))
    crown_c = Vector((0, 0, height * 0.82))
    crown_r = Vector((crown_w * 0.5, crown_w * 0.5, height * 0.2))
    # Feathery sprays laid in flat tiers on the limbs (mostly facing the sky), a few tilted ones
    # so the crown keeps body side-on; the flat top is held by clamping card tops under `height`.
    tips = []
    for lm in limbs:
        for t in np.linspace(0.3, 1.0, 5):
            k = min(int(t * (len(lm.pts) - 1)), len(lm.pts) - 2)
            tips.append((lm.pts[k].lerp(lm.pts[k + 1], t * (len(lm.pts) - 1) - k), (lm.pts[k + 1] - lm.pts[k]).normalized()))
    n_cards = 120 if lod == 0 else 40
    size = crown_w * (0.38 if lod == 0 else 0.55)
    for _ in range(n_cards):
        p, d = tips[rng.integers(len(tips))]
        p = p + Vector((rng.normal() * size * 0.3, rng.normal() * size * 0.3, rng.normal() * size * 0.08))
        hd = Vector((d.x, d.y, 0))
        hd = hd.normalized() if hd.length > 1e-3 else Vector((1, 0, 0))
        up = (hd + Vector((rng.normal() * 0.5, rng.normal() * 0.5, rng.uniform(-0.15, 0.2)))).normalized()
        flat = rng.random() < 0.72
        nrm = Vector((rng.normal() * 0.25, rng.normal() * 0.25, 1)) if flat else Vector((-up.y, up.x, rng.uniform(-0.3, 0.3)))
        if abs(nrm.normalized().dot(up)) > 0.95:
            nrm = up.orthogonal()
        s = size * rng.uniform(0.8, 1.2)
        p.z = min(p.z, height - s * max(up.z, 0) - 0.05)
        card(b, p - up * s * 0.2, up, nrm, s, UV_FROND, CARDS, crown_c, crown_r, leaf_tint, rng, fold=0.12, bend_w=0.55)
    # Spanish moss: long grey-green curtains off the limbs, most of them out toward the crown's
    # rim so they hang BELOW and outside the foliage layer and read from mid-distance, plus a few
    # hung off the trunk under the crown.
    n_moss = int((44 if lod == 0 else 16) * mossy)
    for i in range(n_moss):
        lm = limbs[rng.integers(min(len(limbs), n_limbs))]
        t = rng.uniform(0.35, 0.98)
        k = min(int(t * (len(lm.pts) - 1)), len(lm.pts) - 2)
        p = lm.pts[k].lerp(lm.pts[k + 1], t * (len(lm.pts) - 1) - k)
        L = min(rng.uniform(1.4, 2.9) * (1.0 if lod == 0 else 1.15), p.z - 0.6)
        if L > 0.5:
            hang_moss(b, rng, p, L, crown_c, crown_r, lod, 2)
    return b, mats


def willow(seed, lod, height, trunk_r, crown_w, tint, leaf_tint):
    rng = np.random.default_rng(seed)
    b = Builder()
    mats = ["bark_willow", "swamp_cards"]
    lean = Vector((rng.normal() * 0.12, rng.normal() * 0.12, 0))
    trunk_h = height * 0.38
    zs = [0.0, 0.1, 0.3, trunk_h * 0.6, trunk_h] if lod == 0 else [0.0, 0.3, trunk_h]
    centres = fluted_trunk(b, rng, trunk_h, 0.75, trunk_r, 12 if lod == 0 else 7, zs, 0.45, lean, tint, mat=0)
    top = centres[-1]
    limbs = []
    n = 6 if lod == 0 else 4
    az0 = rng.uniform(0, 6.3)
    for i in range(n):
        az = az0 + i * 2 * math.pi / n + rng.uniform(-0.3, 0.3)
        d = Vector((math.cos(az) * 0.55, math.sin(az) * 0.55, 1)).normalized()
        segs = 5 if lod == 0 else 3
        # Ascending, then arching out and over (gravity bends the tip down).
        pts = grow_path(top, d, height * 0.62 * rng.uniform(0.85, 1.05), segs, rng, bend=0.08, gravity=-0.16)
        r0 = trunk_r * 0.55
        limbs.append(Limb(pts, taper(segs + 1, r0, r0 * 0.2), 1))
    for lm in limbs:
        tube(b, lm, 6 if lod == 0 else 4, 0, tint, uv_phase=rng.uniform(0, 1))
    crown_c = Vector((0, 0, height * 0.65))
    crown_r = Vector((crown_w * 0.5, crown_w * 0.5, height * 0.4))
    # Curtains of pendulous whips: hung from the arching limbs, longer toward the tips so the
    # outline is a dome draping almost to the ground.
    n_hang = 80 if lod == 0 else 26
    for _ in range(n_hang):
        lm = limbs[rng.integers(len(limbs))]
        t = rng.uniform(0.35, 1.0)
        k = min(int(t * (len(lm.pts) - 1)), len(lm.pts) - 2)
        p = lm.pts[k].lerp(lm.pts[k + 1], t * (len(lm.pts) - 1) - k)
        p = p + Vector((rng.normal() * 0.25, rng.normal() * 0.25, rng.normal() * 0.1))
        out = Vector((p.x, p.y, 0))
        out = out.normalized() if out.length > 1e-3 else Vector((1, 0, 0))
        down = (Vector((0, 0, -1)) + out * rng.uniform(0.05, 0.25)).normalized()
        L = min(p.z - 0.35, rng.uniform(1.4, 2.6) * (0.7 + 0.5 * t)) * (1.0 if lod == 0 else 1.1)
        if L < 0.5:
            continue
        side = Vector((-out.y, out.x, 0))
        for k2, nrm in enumerate((out, side) if lod == 0 else (out,)):
            card(b, p + Vector((0, 0, 0.05)), down, nrm, L * (1.0 if k2 == 0 else 0.85), UV_WILLOW, CARDS, crown_c,
                 crown_r, leaf_tint, rng, fold=0.15, bend_w=0.55)
    # A few upright sprays to close the top of the dome.
    for _ in range(14 if lod == 0 else 6):
        lm = limbs[rng.integers(len(limbs))]
        p = lm.pts[-2]
        up = Vector((rng.normal() * 0.6, rng.normal() * 0.6, 0.5)).normalized()
        card(b, p, up, up.orthogonal(), crown_w * 0.28, UV_WILLOW, CARDS, crown_c, crown_r, leaf_tint, rng, fold=0.2)
    return b, mats


def snag(seed, lod, height, trunk_r, tint, stubs):
    """Drowned, bleached, broken snag: barkless silver trunk on a flared base, snapped top, a few
    broken stub limbs."""
    rng = np.random.default_rng(seed)
    b = Builder()
    mats = ["bark_snag"]
    lean = Vector((rng.normal() * 0.05, rng.normal() * 0.05, 0))
    zs = ([0.0, 0.08, 0.22, 0.5, 0.9] if lod == 0 else [0.0, 0.3]) + list(np.linspace(1.5, height, 4 if lod == 0 else 2))
    centres = fluted_trunk(b, rng, height, 0.45, trunk_r, 12 if lod == 0 else 6, zs, 0.9, lean, tint, jagged=0.45)
    for i in range(stubs if lod == 0 else max(stubs - 2, 1)):
        z = height * rng.uniform(0.35, 0.9)
        c = centres[0].lerp(centres[-1], z / height)
        az = rng.uniform(0, 6.3)
        d = Vector((math.cos(az), math.sin(az), rng.uniform(0.1, 0.7))).normalized()
        L = rng.uniform(0.3, 1.1) * (1.2 - z / height)
        pts = grow_path(c, d, L, 2, rng, bend=0.15)
        r0 = trunk_r * rng.uniform(0.25, 0.4)
        tube(b, Limb(pts, taper(3, r0, r0 * 0.55), 1), 5 if lod == 0 else 3, 0, tint, uv_phase=rng.uniform(0, 1))
    return b, mats


def knee(b, rng, x, y, h, r, tint):
    """A cypress knee: a swollen, knobby, ROUND-topped cone (never a sharp spike) - flared foot,
    a bulge, then a blunt dome cap."""
    dx, dy = rng.normal() * 0.02, rng.normal() * 0.02
    zs = [-0.05, h * 0.25, h * 0.55, h * 0.80, h * 0.93, h]
    rs = [r * 1.35, r * 1.0, r * 0.92, r * 0.78, r * 0.55, r * 0.18]
    lm = Limb([Vector((x + dx * z / h, y + dy * z / h, z)) for z in zs], rs, 1)
    tube(b, lm, 8, 0, tint, uv_phase=rng.uniform(0, 1))


def knees(seed, stump):
    """Cypress knees (pneumatophores) rising from the muck, optionally round a rotten stump."""
    rng = np.random.default_rng(seed)
    b = Builder()
    mats = ["bark_cypress"]
    tint = (1.0, 0.93, 0.84)
    if stump:
        fluted_trunk(b, rng, 0.85, 0.7, 0.26, 14, [0.0, 0.06, 0.16, 0.32, 0.55, 0.85], 1.4,
                     Vector((0, 0, 0)), tint, jagged=0.12)
    for i in range(int(rng.integers(6, 10))):
        a = rng.uniform(0, 2 * math.pi)
        d = rng.uniform(0.45, 1.25) if stump else math.sqrt(rng.uniform(0.0, 1.0)) * 0.9
        knee(b, rng, math.cos(a) * d, math.sin(a) * d, rng.uniform(0.18, 0.50), rng.uniform(0.07, 0.13), tint)
    return b, mats


def cover_cross(seed, uvr, size, n, tint, splay=0.3):
    """Crossed upright cards (cattail / sedge clumps)."""
    rng = np.random.default_rng(seed)
    b = Builder()
    mats = ["swamp_cards"]
    upv = Vector((0, 0, 1))
    a0 = rng.uniform(0, math.pi)
    for i in range(n):
        a = a0 + i * math.pi / n + rng.uniform(-0.2, 0.2)
        x0, vb, x1, vt, asp = uvr
        w = size * asp * rng.uniform(0.85, 1.05)
        h = size * rng.uniform(0.85, 1.1)
        side = Vector((math.cos(a), math.sin(a), 0)) * w * 0.5
        face_n = Vector((-math.sin(a), math.cos(a), 0))
        lean = face_n * h * splay * rng.uniform(0.3, 1.0) * (1 if i % 2 else -1)
        p = [-side - upv * 0.04, side - upv * 0.04, side + upv * h + lean, -side + upv * h + lean]
        cb = tuple(c * 0.55 for c in tint)
        ns = [(face_n * 0.3 + upv * 0.7).normalized()] * 4
        b.face(tuple(b.v(q) for q in p), [(x0, vb), (x1, vb), (x1, vt), (x0, vt)], ns, [cb, cb, tint, tint], 0)
    return b, mats


def lily(seed, size):
    """A flat raft of pads + duckweed floating on the water (two overlapping quads)."""
    rng = np.random.default_rng(seed)
    b = Builder()
    mats = ["swamp_cards"]
    x0, vb, x1, vt, _ = UV_LILY
    for i in range(2):
        a = rng.uniform(0, 2 * math.pi)
        s = size * (1.0 if i == 0 else 0.7)
        off = Vector((rng.normal() * size * 0.3, rng.normal() * size * 0.3, 0.01 * i))
        ax = Vector((math.cos(a), math.sin(a), 0)) * s * 0.5
        ay = Vector((-math.sin(a), math.cos(a), 0)) * s * 0.5
        p = [off - ax - ay, off + ax - ay, off + ax + ay, off - ax + ay]
        c = (0.9, 0.95, 0.85)
        b.face(tuple(b.v(q) for q in p), [(x0, vb), (x1, vb), (x1, vt), (x0, vt)], [(0, 0, 1)] * 4, [c] * 4, 0)
    return b, mats


CYP_BARK = (0.58, 0.50, 0.44)  # dark reddish-grey, darker still at the waterline
MODELS = {}
for lod in (0, 1):
    MODELS[f"cypress_a_lod{lod}"] = lambda lod=lod: cypress(301, lod, 6.6, 0.24, 4.6, CYP_BARK, (0.95, 1.0, 0.85))
    MODELS[f"cypress_b_lod{lod}"] = lambda lod=lod: cypress(313, lod, 5.6, 0.21, 4.0, (0.52, 0.47, 0.42), (0.85, 0.92, 0.80), mossy=1.4)
    MODELS[f"willow_a_lod{lod}"] = lambda lod=lod: willow(331, lod, 4.8, 0.22, 5.0, (0.66, 0.62, 0.56), (0.74, 0.80, 0.58))
    MODELS[f"snag_a_lod{lod}"] = lambda lod=lod: snag(347, lod, 4.6, 0.18, (0.85, 0.84, 0.82), 4)
    MODELS[f"snag_b_lod{lod}"] = lambda lod=lod: snag(353, lod, 2.8, 0.22, (0.80, 0.80, 0.78), 3)
MODELS["knees_a"] = lambda: knees(371, True)
MODELS["knees_b"] = lambda: knees(379, False)
MODELS["sw_cattail_a"] = lambda: cover_cross(401, UV_CATTAIL, 1.25, 3, (0.95, 1.0, 0.9))
MODELS["sw_cattail_b"] = lambda: cover_cross(409, UV_CATTAIL, 1.0, 3, (1.0, 0.95, 0.85))
MODELS["sw_sedge_a"] = lambda: cover_cross(419, UV_CATTAIL, 0.55, 2, (0.9, 1.0, 0.8), splay=0.45)
MODELS["sw_lily_a"] = lambda: lily(431, 1.4)

clear_scene()
objs = []
report = {}
for name, fn in MODELS.items():
    b, mats = fn()
    objs.append(b.build(name, mats))
    report[name] = b.tris()
export_glb(OUT / "swamp_flora.glb", objs)
for k, v in report.items():
    print(f"{k}: {v} tris")
print("SWAMP_FLORA_DONE")
