"""Alpine terrain PBR layers (snow biome, mountain rock, the forest->snow meadow) for the terrain
shader's alpine splat (`src/alpine/`, `assets/shaders/alpine.wgsl`).

Same contract as `ground.py` (one 4-layer texture array per map after packing):

  alpine_<layer>_albedo.png  sRGB base colour
  alpine_<layer>_normal.png  tangent-space normal, OpenGL (+Y) convention
  alpine_<layer>_ormh.png    linear: R = AO, G = roughness, B = metallic (0), A = height (0..1)

Layers (order = texture-array layer index in `alpine.wgsl`):
  0 snow    procedural wind-packed snow: soft sastrugi ripples, crust/powder roughness, faint
            blue cavities. PROCEDURAL ONLY because no snow scan is on disk yet - swap in
            `snow_02` / `snow_01` (Poly Haven CC0) here once downloaded; nothing else changes.
  1 meadow  leafy_grass + forrest_ground_01 + a few rocky_trail stones   alpine meadow turf
  2 scree   rocky_trail + rock_pitted_mossy (graded cold)                 talus / gravel / scree
  3 rock    mossy_rock + rock_pitted_mossy (lichen greys, graded cold)    cliff faces (triplanar)

1024² per layer: the alpine layers repeat every 3.5-6u and the rock is triplanar on walls, so
1k keeps ~200 texels / unit (plenty at gameplay distance) for a quarter of the forest arrays' VRAM.
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
from common import OUT, grade, lin_to_srgb, load, ph_tex, resize, save, srgb_to_lin  # noqa: E402

SIZE = 1024
SRC = 2048  # composite at the source resolution, downsample once at the end
rng = np.random.default_rng(23)


def tile_noise(freqs, octaves=4, size=SRC, aniso=(1.0, 1.0)):
    """Seamless noise: random-phase cosines on INTEGER frequencies tile over [0,1)².
    `aniso` scales the x / y frequency range (wind ripples: many waves across, few along)."""
    u = np.arange(size, dtype=np.float32) / size
    x, y = np.meshgrid(u, u)
    n = np.zeros((size, size), np.float32)
    amp = 1.0
    for o in range(octaves):
        f = freqs * (2 ** o)
        for _ in range(4):
            kx = int(rng.integers(-f, f + 1) * aniso[0])
            ky = int(rng.integers(-f, f + 1) * aniso[1])
            if kx == 0 and ky == 0:
                kx = max(1, int(f * aniso[0]))
            n += amp * np.cos(2 * np.pi * (kx * x + ky * y) + rng.uniform(0, 6.3))
        amp *= 0.5
    n -= n.min()
    return n / max(n.max(), 1e-6)


def normal_from_height(h, strength):
    """Tangent-space OpenGL normal from a tileable height map (wrap-around central differences).
    Image +Y is UP the picture = decreasing row index."""
    dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5
    dy = (np.roll(h, 1, 0) - np.roll(h, -1, 0)) * 0.5
    n = np.stack([-dx * strength, -dy * strength, np.ones_like(h)], -1)
    return n / (np.linalg.norm(n, axis=-1, keepdims=True) + 1e-6)


def source(aid, sat, gain, tint=(1.0, 1.0, 1.0)):
    diff = grade(load(ph_tex(aid, "diff"), 3), sat, gain)
    if tint != (1.0, 1.0, 1.0):
        diff = lin_to_srgb(srgb_to_lin(diff) * np.array(tint, np.float32))
    nor = load(ph_tex(aid, "nor_gl"), 3) * 2 - 1
    rough = load(ph_tex(aid, "rough"), 1)[..., 0]
    ao = load(ph_tex(aid, "ao"), 1)[..., 0]
    disp = load(ph_tex(aid, "disp"), 1)[..., 0]
    lo, hi = np.percentile(disp, [0.5, 99.5])
    h = np.clip((disp - lo) / max(hi - lo, 1e-4), 0, 1)
    return dict(diff=diff, nor=nor, rough=rough, ao=ao, h=h)


def write(name, diff, nor, rough, ao, h):
    diff = resize(diff, SIZE, SIZE)
    nor = resize(nor, SIZE, SIZE)
    nor = nor / (np.linalg.norm(nor, axis=-1, keepdims=True) + 1e-6)
    rough = resize(rough[..., None], SIZE, SIZE)[..., 0]
    ao = resize(ao[..., None], SIZE, SIZE)[..., 0]
    h = resize(h[..., None], SIZE, SIZE)[..., 0]
    lo, hi = np.percentile(h, [0.5, 99.5])
    h = np.clip((h - lo) / max(hi - lo, 1e-4), 0, 1)
    save(diff, OUT / f"alpine_{name}_albedo.png")
    save(nor * 0.5 + 0.5, OUT / f"alpine_{name}_normal.png")
    save(np.stack([ao, rough, np.zeros_like(h), h], -1), OUT / f"alpine_{name}_ormh.png")
    print(f"alpine {name}: albedo mean {diff.mean(axis=(0, 1)).round(3)} rough {rough.mean():.2f}")


def composite(name, parts, band=0.18):
    """Height-blend like ground.py: each texel goes to the source whose mask + height wins."""
    scores = [m + s["h"] * 0.55 for s, m in parts]
    top = np.maximum.reduce(scores)
    ws = [np.clip(sc - (top - band), 0, None) for sc in scores]
    tot = np.sum(ws, axis=0) + 1e-6
    ws = [w / tot for w in ws]
    out = {k: sum(w[..., None] * s[k] if s[k].ndim == 3 else w * s[k] for w, (s, _) in zip(ws, parts))
           for k in ("diff", "nor", "rough", "ao", "h")}
    write(name, out["diff"], out["nor"], out["rough"], out["ao"], out["h"])


def patches(freq, lo, hi, octaves=4):
    n = tile_noise(freq, octaves)
    return np.clip((n - lo) / (hi - lo), 0, 1)


def flat(v):
    return np.full((SRC, SRC), v, np.float32)


def deleaf(src, amount):
    """Turn the scan's orange fallen leaves into dry straw: pull red-dominant texels toward a
    desaturated olive, so leafy_grass reads as a mountain meadow, not a park lawn in autumn."""
    lin = srgb_to_lin(src["diff"])
    r, g = lin[..., 0], lin[..., 1]
    leafy = np.clip((r - g) * 6.0, 0, 1)[..., None] * amount
    luma = (lin * np.array([0.2126, 0.7152, 0.0722])).sum(-1, keepdims=True)
    straw = luma * np.array([1.05, 1.0, 0.62]) * 1.05
    src["diff"] = lin_to_srgb(lin * (1 - leafy) + straw * leafy)
    return src


# ── 0 snow (procedural) ─────────────────────────────────────────────────────────────────────
def snow():
    # Wind ripples (sastrugi): long crests across one axis, broken by a slow cross undulation,
    # plus soft dunelets and a fine crystalline grain.
    ripple = tile_noise(6, 3, aniso=(0.35, 1.6))
    dunes = tile_noise(2, 3)
    grain = tile_noise(48, 2)
    sparkle_n = tile_noise(96, 1)
    h = ripple * 0.55 + dunes * 0.40 + grain * 0.05
    h = (h - h.min()) / max(h.max() - h.min(), 1e-6)
    # Crisp wind-crust lee edges: sharpen the ripple crests a touch.
    h = np.clip(h + (np.clip(ripple - 0.55, 0, 1) ** 2) * 0.35, 0, 1)
    h = (h - h.min()) / max(h.max() - h.min(), 1e-6)
    nor = normal_from_height(h, 9.0)
    # Fine grain normal on top (crystal crust), very soft.
    nor = nor + normal_from_height(grain, 2.0) * np.array([1, 1, 0], np.float32) * 0.6
    nor = nor / (np.linalg.norm(nor, axis=-1, keepdims=True) + 1e-6)
    cav = np.clip(1.0 - (0.62 - h) * 0.55, 0.72, 1.0)
    # Linear albedo: real snow is ~0.8-0.9; hollows a hint bluer, crests a hint warmer.
    base = np.array([0.80, 0.84, 0.90], np.float32)
    blue = np.array([0.70, 0.78, 0.90], np.float32)
    t = np.clip((0.55 - h) * 1.6, 0, 1)[..., None]
    lin = base * (1 - t) + blue * t
    lin = lin * (0.97 + 0.05 * grain[..., None])
    diff = lin_to_srgb(lin)
    # Wind crust (crests) is smoother than the powder in the hollows; grain breaks it up.
    rough = np.clip(0.58 + (0.5 - h) * 0.25 + (sparkle_n - 0.5) * 0.10, 0.38, 0.85)
    write("snow", diff, nor, rough, cav, h)


snow()

# ── 1 meadow ─────────────────────────────────────────────────────────────────────────────────
composite("meadow", [
    (deleaf(source("leafy_grass", 1.12, 0.95), 0.75), flat(0.55)),
    (source("forrest_ground_01", 1.10, 0.92), patches(2, 0.45, 0.85)),
    (source("rocky_trail", 0.55, 0.95, (0.95, 0.97, 1.0)), patches(3, 0.80, 0.97)),
])

# ── 2 scree ──────────────────────────────────────────────────────────────────────────────────
composite("scree", [
    (source("rocky_trail", 0.45, 1.0, (0.92, 0.96, 1.04)), flat(0.6)),
    (source("rock_pitted_mossy", 0.30, 0.95, (0.95, 0.97, 1.03)), patches(2, 0.62, 0.92)),
])

# ── 3 rock ───────────────────────────────────────────────────────────────────────────────────
composite("rock", [
    (source("mossy_rock", 0.32, 1.08, (0.96, 0.98, 1.03)), flat(0.6)),
    (source("rock_pitted_mossy", 0.25, 1.0, (0.95, 0.97, 1.03)), patches(2, 0.55, 0.9)),
])

print("ALPINE_DONE")
