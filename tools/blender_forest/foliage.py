"""Foliage card textures: the tree-canopy atlas and the undergrowth atlas.

canopy_{albedo,normal}.png  2048x1024, two 1024² cells:
    [0] broadleaf spray - a twig carrying ~150 real leaves (Poly Haven `shrub_04` scans, CC0),
        each rotated / foreshortened / tinted and cupped so the card reads as a 3D cluster.
    [1] conifer spray   - a branchlet densely set with procedurally drawn needles.
undergrowth_{albedo,normal}.png  2048², cropped CC0 cards: four fern fronds (`fern_02`),
    five grass clumps and a pair of seed-headed stalks (`grass_medium_01`).

Albedo is sRGB with alpha = coverage (colour bled under transparent texels so mips stay
clean); normal is tangent space, OpenGL +Y = card "up". The UV rectangles of every cell
are written to foliage_layout.json for trees.py / undergrowth.py.
"""
import json
import math
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
from common import OUT, bilinear, bleed_alpha, grade, load, olive_grade, ph_model_tex, resize, save  # noqa: E402

rng = np.random.default_rng(7)


class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.rgb = np.zeros((h, w, 3), np.float32)
        self.a = np.zeros((h, w), np.float32)
        self.n = np.zeros((h, w, 3), np.float32)
        self.n[..., 2] = 1.0

    def over(self, y0, y1, x0, x1, rgb, a, n):
        """Alpha-composite a patch (a = coverage) over the canvas region."""
        da = self.a[y0:y1, x0:x1]
        aa = a[..., None]
        self.rgb[y0:y1, x0:x1] = rgb * aa + self.rgb[y0:y1, x0:x1] * (1 - aa)
        self.n[y0:y1, x0:x1] = n * aa + self.n[y0:y1, x0:x1] * (1 - aa)
        self.a[y0:y1, x0:x1] = a + da * (1 - a)

    def finish(self):
        nrm = self.n / (np.linalg.norm(self.n, axis=-1, keepdims=True) + 1e-6)
        rgb = bleed_alpha(self.rgb, self.a)
        return np.concatenate([rgb, self.a[..., None]], -1), nrm * 0.5 + 0.5


def rot2(v, ang):
    """Rotate xy vectors (math orientation, +y up) by ang radians."""
    c, s = math.cos(ang), math.sin(ang)
    return np.stack([v[..., 0] * c - v[..., 1] * s, v[..., 0] * s + v[..., 1] * c], -1)


# ---------------------------------------------------------------- broadleaf spray
SHRUB = "shrub_04"
s_rgb = load(ph_model_tex(SHRUB, "shrub_04_diff_1k.jpg"), 3)
s_a = load(ph_model_tex(SHRUB, "shrub_04_alpha_1k.png"), 1)[..., 0]
s_n = load(ph_model_tex(SHRUB, "shrub_04_nor_gl_1k.jpg"), 3) * 2 - 1
# Individual leaves in the 1k source: (x0, y0, x1, y1), tip at the top, petiole at the bottom.
LEAVES = [(130, 100, 230, 330), (540, 75, 625, 335), (440, 410, 550, 640), (620, 395, 710, 595),
          (240, 655, 335, 940), (385, 715, 490, 950), (565, 700, 650, 900), (55, 740, 150, 965)]


def paste_leaf(cv, leaf, base, ang, length, squash, tint, tilt, shade, src=None):
    """Paste leaf `leaf` with its petiole at `base` (x, y px), pointing along `ang`
    (radians from canvas-up, clockwise positive), `length` px long. `src` swaps the colour
    source (e.g. the browned copy used for fallen litter)."""
    x0, y0, x1, y1 = leaf
    lw, lh = x1 - x0, y1 - y0
    s = length / lh
    half = int(length * 0.75) + 4
    cx = base[0] + math.sin(ang) * length * 0.5
    cy = base[1] - math.cos(ang) * length * 0.5
    bx0, bx1 = int(max(cx - half, 0)), int(min(cx + half, cv.w))
    by0, by1 = int(max(cy - half, 0)), int(min(cy + half, cv.h))
    if bx1 <= bx0 or by1 <= by0:
        return
    ys, xs = np.mgrid[by0:by1, bx0:bx1].astype(np.float32)
    dx, dy = xs - cx, ys - cy
    c, si = math.cos(ang), math.sin(ang)
    # Into leaf-local px: u across the leaf, v along it (v<0 toward the tip).
    u = dx * c + dy * si
    v = -dx * si + dy * c
    sx = x0 + lw / 2 + u / (s * squash)
    sy = y0 + lh / 2 + v / s
    inside = (sx >= x0) & (sx < x1 - 1) & (sy >= y0) & (sy < y1 - 1)
    a = bilinear(s_a, sx, sy) * inside
    if a.max() <= 0:
        return
    rgb = bilinear(s_rgb if src is None else src, sx, sy) * tint * shade
    nl = bilinear(s_n, sx, sy)
    # Leaf normal: source detail rotated into place, plus a tilt about the midrib and a cupped
    # cross-section so each leaf catches light like a curved blade, not a flat sticker.
    across = np.clip((sx - (x0 + lw / 2)) / (lw / 2), -1, 1)
    nxy = nl[..., :2] * 0.6
    nxy[..., 0] += across * 0.55 + tilt
    nxy = rot2(nxy, -ang)
    n = np.concatenate([nxy, np.ones_like(a)[..., None] * 0.9], -1)
    cv.over(by0, by1, bx0, bx1, rgb, a, n)


def draw_capsule(cv, p0, p1, w0, w1, color, nscale=0.9):
    """Tapered round stroke from p0 to p1 (px), width w0 -> w1, cylindrical normal."""
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
    px, py = x0 + d[0] * t, y0 + d[1] * t
    ox, oy = xs - px, ys - py
    dist = np.sqrt(ox * ox + oy * oy)
    w = (w0 + (w1 - w0) * t) * 0.5
    a = np.clip(w + 0.6 - dist, 0, 1)
    if a.max() <= 0:
        return
    side = np.clip((ox * -d[1] + oy * d[0]) / (math.sqrt(L2) * np.maximum(w, 0.3)), -1, 1)
    perp = np.array([-d[1], -d[0]], np.float32) / math.sqrt(L2)  # math-up orientation
    nxy = perp[None, None, :] * (side * nscale)[..., None]
    nz = np.sqrt(np.clip(1 - (side * nscale) ** 2, 0.05, 1))
    n = np.concatenate([nxy, nz[..., None]], -1)
    rgb = np.broadcast_to(np.asarray(color, np.float32), (*a.shape, 3)) * (0.75 + 0.25 * nz[..., None])
    cv.over(by0, by1, bx0, bx1, rgb, a, n)


def curve(p0, p1, bend, n=12):
    """Points along a gently bowed path p0 -> p1."""
    p0, p1 = np.array(p0, np.float32), np.array(p1, np.float32)
    d = p1 - p0
    perp = np.array([-d[1], d[0]]) / (np.linalg.norm(d) + 1e-6)
    return [p0 + d * t + perp * bend * math.sin(math.pi * t) for t in np.linspace(0, 1, n)]


def broadleaf_spray(size=1024):
    cv = Canvas(size, size)
    bark = (0.30, 0.22, 0.15)
    main = curve((size * 0.5, size * 0.98), (size * 0.47, size * 0.06), size * 0.05)
    twigs = [main]
    for i, t in enumerate(np.linspace(0.10, 0.85, 9)):
        k = int(t * (len(main) - 1))
        p = main[k]
        side = -1 if i % 2 else 1
        ang = side * rng.uniform(0.55, 1.0)
        L = size * rng.uniform(0.30, 0.40) * (1.1 - t * 0.5)
        end = (p[0] + math.sin(ang) * L, p[1] - math.cos(ang) * L)
        twigs.append(curve(p, end, side * size * 0.02, 8))
    leaves = []
    for ti, tw in enumerate(twigs):
        for a, b in zip(tw[:-1], tw[1:]):
            draw_capsule(cv, a, b, 7 if ti == 0 else 4, 5 if ti == 0 else 2.5, bark)
        segs = len(tw) - 1
        count = 40 if ti == 0 else 24
        for j in range(count):
            t = rng.uniform(0.12 if ti == 0 else 0.05, 1.0)
            k = min(int(t * segs), segs - 1)
            p = tw[k] + (tw[k + 1] - tw[k]) * (t * segs - k)
            d = tw[k + 1] - tw[k]
            dir_ang = math.atan2(d[0], -d[1])
            side = 1 if j % 2 else -1
            ang = dir_ang + side * rng.uniform(0.35, 1.05)
            leaves.append((p, ang))
    rng.shuffle(leaves)
    for idx, (p, ang) in enumerate(leaves):
        depth = idx / max(len(leaves) - 1, 1)  # later = nearer the viewer = brighter
        g = rng.uniform(0.0, 1.0)
        tint = np.array([0.68 + 0.16 * g, 0.97 + 0.06 * g, 0.55 + 0.08 * g], np.float32)
        paste_leaf(cv, LEAVES[rng.integers(len(LEAVES))], p, ang,
                   length=rng.uniform(100, 150) * size / 1024, squash=rng.uniform(0.6, 1.0),
                   tint=tint, tilt=rng.uniform(-0.45, 0.45), shade=0.62 + 0.38 * depth)
    rgba, nrm = cv.finish()
    rgba[..., :3] = grade(rgba[..., :3], sat=1.25, gain=1.08)
    return rgba, nrm


# ---------------------------------------------------------------- conifer spray
def conifer_spray(size=1024):
    cv = Canvas(size, size)
    bark = (0.27, 0.19, 0.13)
    main = curve((size * 0.5, size * 0.99), (size * 0.52, size * 0.04), size * 0.03)
    twigs = [(main, 1.0)]
    for i, t in enumerate(np.linspace(0.15, 0.75, 7)):
        k = int(t * (len(main) - 1))
        p = main[k]
        side = -1 if i % 2 else 1
        ang = side * rng.uniform(0.6, 0.9)
        L = size * rng.uniform(0.25, 0.34) * (1.05 - t * 0.45)
        twigs.append((curve(p, (p[0] + math.sin(ang) * L, p[1] - math.cos(ang) * L), side * 8, 8), 0.8))
    needles = []
    for tw, sc in twigs:
        for a, b in zip(tw[:-1], tw[1:]):
            draw_capsule(cv, a, b, 6 * sc, 3 * sc, bark)
        for a, b in zip(tw[:-1], tw[1:]):
            d = b - a
            seg = float(np.linalg.norm(d))
            dir_ang = math.atan2(d[0], -d[1])
            for _ in range(int(seg / 2.2)):
                t = rng.uniform(0, 1)
                p = a + d * t
                for side in (-1, 1):
                    ang = dir_ang + side * rng.uniform(0.55, 1.15)
                    L = rng.uniform(42, 66) * sc * size / 1024
                    needles.append((p, ang, L))
    rng.shuffle(needles)
    for idx, (p, ang, L) in enumerate(needles):
        depth = idx / max(len(needles) - 1, 1)
        g = rng.uniform(0, 1)
        col = np.array([0.10 + 0.07 * g, 0.20 + 0.10 * g, 0.07 + 0.04 * g]) * (0.65 + 0.45 * depth)
        end = (p[0] + math.sin(ang) * L, p[1] - math.cos(ang) * L)
        draw_capsule(cv, tuple(p), end, 3.2, 1.2, col, nscale=0.8)
    rgba, nrm = cv.finish()
    return rgba, nrm


# ---------------------------------------------------------------- undergrowth crops
def crop_fit(dst_rgba, dst_n, src_rgba, src_n, rect, cell, anchor_bottom=True):
    """Copy src rect into the dst cell, preserving aspect (fit), bottom-anchored."""
    x0, y0, x1, y1 = rect
    cx, cy, cw, ch = cell
    sw, sh = x1 - x0, y1 - y0
    s = min(cw / sw, ch / sh)
    w, h = max(int(sw * s), 1), max(int(sh * s), 1)
    ox = cx + (cw - w) // 2
    oy = cy + (ch - h if anchor_bottom else (ch - h) // 2)
    sub = src_rgba[y0:y1, x0:x1]
    subn = src_n[y0:y1, x0:x1]
    dst_rgba[oy:oy + h, ox:ox + w] = resize(sub, w, h)
    dst_n[oy:oy + h, ox:ox + w] = resize(subn, w, h)
    return [ox, oy, w, h]


def card_source(mid, pre):
    rgb = load(ph_model_tex(mid, f"{pre}_diff_1k.jpg"), 3)
    a = load(ph_model_tex(mid, f"{pre}_alpha_1k.png"), 1)
    n = load(ph_model_tex(mid, f"{pre}_nor_gl_1k.jpg"), 3)
    return np.concatenate([rgb, a], -1), n


layout = {"canopy": {"size": [2048, 1024]}, "undergrowth": {"size": [2048, 2048]}}

bl_rgba, bl_n = broadleaf_spray()
cf_rgba, cf_n = conifer_spray()
canopy = np.concatenate([bl_rgba, cf_rgba], 1)
canopy_n = np.concatenate([bl_n, cf_n], 1)
save(canopy, OUT / "canopy_albedo.png")
save(canopy_n, OUT / "canopy_normal.png")


def alpha_bbox(a, x_off, pad=6):
    """Tight rectangle around the visible spray: cards are cut to it, so the GPU does not shade
    (and discard) the empty margins of every leaf card - the dominant foliage cost."""
    ys, xs = np.where(a > 0.05)
    x0, y0 = max(xs.min() - pad, 0), max(ys.min() - pad, 0)
    x1, y1 = min(xs.max() + pad, a.shape[1] - 1), min(ys.max() + pad, a.shape[0] - 1)
    return [int(x_off + x0), int(y0), int(x1 - x0 + 1), int(y1 - y0 + 1)]


layout["canopy"]["broadleaf"] = alpha_bbox(bl_rgba[..., 3], 0)
layout["canopy"]["conifer"] = alpha_bbox(cf_rgba[..., 3], 1024)
for k in ("broadleaf", "conifer"):
    x, y, w, h = layout["canopy"][k]
    cov = float((canopy[y:y + h, x:x + w, 3] > 0.42).mean())
    print(f"canopy {k}: rect {layout['canopy'][k]} coverage in rect {cov:.2f}")

ug = np.zeros((2048, 2048, 4), np.float32)
ug_n = np.zeros((2048, 2048, 3), np.float32)
ug_n[..., :] = (0.5, 0.5, 1.0)
fern, fern_n = card_source("fern_02", "fern_02")
FERNS = [(85, 110, 245, 975), (315, 25, 470, 780), (520, 520, 660, 990), (725, 110, 860, 920)]
layout["undergrowth"]["fern"] = [crop_fit(ug, ug_n, fern, fern_n, r, (i * 256, 0, 256, 1024))
                                 for i, r in enumerate(FERNS)]
grass, grass_n = card_source("grass_medium_01", "grass_medium_01")
CLUMPS = [(200, 765, 500, 893), (600, 770, 840, 866), (20, 893, 215, 1000), (250, 912, 510, 1012),
          (590, 895, 815, 1012)]
CELLS = [(1024, 0, 512, 256), (1536, 0, 512, 256), (1024, 256, 512, 256), (1536, 256, 512, 256),
         (1024, 512, 512, 256)]
layout["undergrowth"]["grass"] = [crop_fit(ug, ug_n, grass, grass_n, r, c) for r, c in zip(CLUMPS, CELLS)]
layout["undergrowth"]["stalks"] = [crop_fit(ug, ug_n, grass, grass_n, (865, 10, 1000, 165), (1536, 512, 256, 512))]


# Fallen litter: dead leaves (the same scans, browned) + a few twigs, drawn as if seen from
# straight above, for cards that LIE on the floor - real overlapping geometry on top of the
# ground texture, the "clutter" layer that keeps a game forest floor from reading flat.
s_luma = (s_rgb * np.array([0.30, 0.59, 0.11], np.float32)).sum(-1, keepdims=True)
s_brown = np.clip(s_luma * np.array([1.08, 0.82, 0.56], np.float32), 0, 1)


def litter_sprite(seed, size=512):
    lr = np.random.default_rng(seed)
    cv = Canvas(size, size)
    for _ in range(4):
        x0, y0 = lr.uniform(0.3, 0.7, 2) * size
        ang = lr.uniform(0, 6.3)
        L = lr.uniform(0.15, 0.28) * size
        draw_capsule(cv, (x0, y0), (x0 + math.cos(ang) * L, y0 + math.sin(ang) * L), 6, 2.5,
                     (0.30 + lr.uniform(0, 0.08), 0.22, 0.15))
    n = 46
    for i in range(n):
        r = lr.uniform(0, 0.42) ** 0.8 * size
        a = lr.uniform(0, 6.3)
        base = (size / 2 + math.cos(a) * r, size / 2 + math.sin(a) * r)
        g = lr.uniform(0, 1)
        tint = np.array([0.75 + 0.3 * g, 0.72 + 0.18 * g, 0.62 + 0.05 * g], np.float32)
        paste_leaf(cv, LEAVES[lr.integers(len(LEAVES))], base, lr.uniform(0, 6.3),
                   length=lr.uniform(55, 85) * size / 512, squash=lr.uniform(0.7, 1.0), tint=tint,
                   tilt=lr.uniform(-0.3, 0.3), shade=0.6 + 0.4 * i / n, src=s_brown)
    rgba, nrm = cv.finish()
    return rgba, nrm * 2 - 1


layout["undergrowth"]["litter"] = []
for i in range(4):
    rgba, nrm = litter_sprite(100 + i)
    x, y = i * 512, 1024
    ug[y:y + 512, x:x + 512] = rgba
    ug_n[y:y + 512, x:x + 512] = nrm * 0.5 + 0.5
    layout["undergrowth"]["litter"].append([x, y, 512, 512])



# Wildflowers for path edges and clearings: drawn procedurally (stems, petals, florets) so the
# forest gets the white / purple / yellow accents a lush woodland reads by.
GREEN = (0.20, 0.34, 0.11)


def blade(cv, lr, base, height, lean):
    tip = (base[0] + lean, base[1] - height)
    draw_capsule(cv, base, tip, 5, 1.2, tuple(c * lr.uniform(0.8, 1.15) for c in GREEN), nscale=0.6)


def daisy_head(cv, lr, c, r, petal=(0.93, 0.93, 0.88), disc=(0.95, 0.72, 0.12), n=13):
    a0 = lr.uniform(0, 6.3)
    for k in range(n):
        a = a0 + k * 2 * math.pi / n
        tip = (c[0] + math.cos(a) * r, c[1] + math.sin(a) * r * 0.75)
        col = tuple(v * lr.uniform(0.85, 1.0) for v in petal)
        draw_capsule(cv, c, tip, r * 0.38, r * 0.22, col, nscale=0.4)
    draw_capsule(cv, c, (c[0] + 0.5, c[1]), r * 0.55, r * 0.55, disc, nscale=0.8)


def daisy_sprite(seed, size=512, petal=(0.93, 0.93, 0.88), disc=(0.95, 0.72, 0.12), r_px=(16, 24), n=13):
    lr = np.random.default_rng(seed)
    cv = Canvas(size, size)
    for _ in range(9):
        blade(cv, lr, (lr.uniform(0.2, 0.8) * size, size - 2), lr.uniform(0.15, 0.35) * size, lr.uniform(-40, 40))
    for _ in range(8):
        bx = lr.uniform(0.15, 0.85) * size
        hx, hy = bx + lr.uniform(-30, 30), lr.uniform(0.12, 0.6) * size
        draw_capsule(cv, (bx, size - 2), (hx, hy), 4, 2.5, GREEN, nscale=0.6)
        daisy_head(cv, lr, (hx, hy), lr.uniform(*r_px), petal, disc, n)
    rgba, nrm = cv.finish()
    return rgba, nrm * 2 - 1


def lupine_sprite(seed, w=256, h=512, col=(0.46, 0.32, 0.78)):
    lr = np.random.default_rng(seed)
    cv = Canvas(w, h)
    for _ in range(7):
        blade(cv, lr, (w * 0.5 + lr.uniform(-20, 20), h - 2), lr.uniform(0.12, 0.22) * h, lr.uniform(-70, 70))
    top = h * 0.05
    draw_capsule(cv, (w * 0.5, h - 2), (w * 0.52, top), 6, 3, GREEN, nscale=0.6)
    n = 34
    for k in range(n):
        t = k / (n - 1)
        y = h * 0.55 - t * (h * 0.55 - top - 8)
        x = w * 0.5 + (w * 0.02) * t
        size = 26 * (1.0 - 0.6 * t)
        side = -1 if k % 2 else 1
        c = tuple(v * lr.uniform(0.8, 1.1) * (0.85 + 0.25 * t) for v in col)
        draw_capsule(cv, (x, y), (x + side * size, y - size * 0.25), size * 0.6, size * 0.4, c, nscale=0.7)
    rgba, nrm = cv.finish()
    return rgba, nrm * 2 - 1


def lush_grass_sprite(seed, w=512, h=256):
    """A dense tuft of fresh green blades (drawn, not scanned): the carpet layer. Blades are
    tapered capsules fanning from a base line, dark at the root, sun-yellowed at the tips."""
    lr = np.random.default_rng(seed)
    cv = Canvas(w, h)
    n = 150
    for i in range(n):
        bx = lr.uniform(0.08, 0.92) * w
        tall = lr.uniform(0.45, 0.97) * h
        lean = lr.normal() * 0.18 * h + (bx - w / 2) * 0.25
        g = lr.uniform(0, 1)
        col = np.array([0.16 + 0.18 * g, 0.36 + 0.20 * g, 0.07 + 0.06 * g]) * (0.7 + 0.45 * i / n)
        mid = (bx + lean * 0.4, h - 1 - tall * 0.55)
        tip = (bx + lean, h - 1 - tall)
        draw_capsule(cv, (bx, h - 1), mid, 7, 5, col * 0.8, nscale=0.6)
        draw_capsule(cv, mid, tip, 5, 1.0, col, nscale=0.6)
    rgba, nrm = cv.finish()
    return rgba, nrm * 2 - 1


layout["undergrowth"]["lush"] = []
for seed, cell in [(301, (1536, 1536, 512, 256)), (302, (1536, 1792, 512, 256)), (303, (1024, 768, 512, 256))]:
    rgba, nrm = lush_grass_sprite(seed)
    x, y, cw, ch = cell
    ug[y:y + ch, x:x + cw] = rgba
    ug_n[y:y + ch, x:x + cw] = nrm * 0.5 + 0.5
    layout["undergrowth"]["lush"].append([x, y, cw, ch])

layout["undergrowth"]["flowers"] = []
for i, (rgba, nrm, cell) in enumerate([
    (*daisy_sprite(201), (0, 1536, 512, 512)),
    (*lupine_sprite(202), (512, 1536, 256, 512)),
    (*lupine_sprite(203, col=(0.62, 0.36, 0.72)), (768, 1536, 256, 512)),
    (*daisy_sprite(204, petal=(0.98, 0.82, 0.12), disc=(0.85, 0.55, 0.08), r_px=(9, 13), n=6), (1024, 1536, 512, 512)),
]):
    x, y, cw, ch = cell
    ug[y:y + ch, x:x + cw] = rgba
    ug_n[y:y + ch, x:x + cw] = nrm * 0.5 + 0.5
    layout["undergrowth"]["flowers"].append([x, y, cw, ch])

ug[..., 3] = np.where(ug[..., 3] > 0.04, ug[..., 3], 0.0)
ug[..., :3] = grade(bleed_alpha(ug[..., :3], ug[..., 3]), sat=1.05, gain=0.95)
# The scanned / painted grass greens read neon or near-black against the olive meadow sward: pull
# the green texels toward olive (flowers + straw keep their hue). Baked here rather than in a
# custom foliage fragment stage, so the cards keep the stock PBR fragment (no per-pixel cost).
ug[..., :3] = olive_grade(ug[..., :3], 0.6)
save(ug, OUT / "undergrowth_albedo.png")
save(ug_n, OUT / "undergrowth_normal.png")

(OUT / "foliage_layout.json").write_text(json.dumps(layout, indent=1), encoding="utf-8")
print("canopy coverage", float(canopy[..., 3].mean()), "undergrowth coverage", float(ug[..., 3].mean()))
print("FOLIAGE_DONE")
