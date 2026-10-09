"""Forest-floor PBR layers for the terrain shader's forest splat.

Each layer is a 2048² COMPOSITE of several tileable Poly Haven CC0 scans, height-blended through
large tileable noise masks, so one repeat already holds stones, mud, roots, leaves and moss
instead of a single photographed patch stamped over and over:

  ground_<layer>_albedo.png  sRGB base colour
  ground_<layer>_normal.png  tangent-space normal, OpenGL (+Y) convention
  ground_<layer>_ormh.png    linear: R = AO, G = roughness, B = metallic (0), A = height (0..1)

Layers (order = texture-array layer index in `terrain.wgsl`):
  0 litter  forest_leaves_02 + leaf_scattered_gravel           broadleaf litter (dry hollows)
  1 moss    forrest_ground_01 + brown_mud_leaves_01 + forest_ground_06   grass, clover, bare soil
  2 path    mud_forest + forest_ground_04 + rocky_trail + roots           a worn forest trail

Height is normalised per layer so the shader's height-blend compares like with like.
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
from common import OUT, grade, load, ph_tex, save  # noqa: E402

SIZE = 2048
rng = np.random.default_rng(11)


def tile_noise(freqs, octaves=4, size=SIZE):
    """Seamless noise: random-phase cosines on INTEGER frequencies tile over [0,1)²."""
    u = np.arange(size, dtype=np.float32) / size
    x, y = np.meshgrid(u, u)
    n = np.zeros((size, size), np.float32)
    amp = 1.0
    for o in range(octaves):
        f = freqs * (2 ** o)
        for _ in range(3):
            kx, ky = rng.integers(-f, f + 1, 2)
            if kx == 0 and ky == 0:
                kx = f
            n += amp * np.cos(2 * np.pi * (kx * x + ky * y) + rng.uniform(0, 6.3))
        amp *= 0.5
    n -= n.min()
    return n / max(n.max(), 1e-6)


def source(aid, sat, gain):
    diff = grade(load(ph_tex(aid, "diff"), 3), sat, gain)
    nor = load(ph_tex(aid, "nor_gl"), 3) * 2 - 1
    rough = load(ph_tex(aid, "rough"), 1)[..., 0]
    ao = load(ph_tex(aid, "ao"), 1)[..., 0]
    disp = load(ph_tex(aid, "disp"), 1)[..., 0]
    lo, hi = np.percentile(disp, [0.5, 99.5])
    h = np.clip((disp - lo) / max(hi - lo, 1e-4), 0, 1)
    return dict(diff=diff, nor=nor, rough=rough, ao=ao, h=h)


def composite(name, parts, band=0.18):
    """parts: [(source, coverage mask 0..1)]. Height-blend: each texel goes to the source whose
    mask + height scores highest, softened across `band` so stones / leaves poke through."""
    scores = [m + s["h"] * 0.55 for s, m in parts]
    top = np.maximum.reduce(scores)
    ws = [np.clip(sc - (top - band), 0, None) for sc in scores]
    tot = np.sum(ws, axis=0) + 1e-6
    ws = [w / tot for w in ws]
    out = {k: sum(w[..., None] * s[k] if s[k].ndim == 3 else w * s[k] for w, (s, _) in zip(ws, parts))
           for k in ("diff", "nor", "rough", "ao", "h")}
    n = out["nor"]
    n /= np.linalg.norm(n, axis=-1, keepdims=True) + 1e-6
    lo, hi = np.percentile(out["h"], [0.5, 99.5])
    h = np.clip((out["h"] - lo) / max(hi - lo, 1e-4), 0, 1)
    save(out["diff"], OUT / f"ground_{name}_albedo.png")
    save(n * 0.5 + 0.5, OUT / f"ground_{name}_normal.png")
    save(np.stack([out["ao"], out["rough"], np.zeros_like(h), h], -1), OUT / f"ground_{name}_ormh.png")
    print(f"ground {name}: albedo mean {out['diff'].mean(axis=(0, 1)).round(3)}")


def patches(freq, lo, hi, octaves=4):
    n = tile_noise(freq, octaves)
    return np.clip((n - lo) / (hi - lo), 0, 1)


def flat(v):
    return np.full((SIZE, SIZE), v, np.float32)


# Litter: dry leaves, with patches of leafy gravel showing through.
composite("litter", [
    (source("forest_leaves_02", 0.62, 0.92), flat(0.55)),
    (source("leaf_scattered_gravel", 0.7, 1.15), patches(2, 0.68, 0.95)),
])

# Moss: grass + needles, with clover-and-mud drifts and a few bare-soil spots.
composite("moss", [
    (source("forrest_ground_01", 1.15, 0.92), flat(0.6)),
    (source("brown_mud_leaves_01", 0.95, 0.85), patches(2, 0.5, 0.85)),
    (source("forest_ground_06", 0.8, 0.95), patches(3, 0.72, 0.95)),
])

# Path: damp trodden soil with leaves, gravelly stretches, pebble clusters and exposed roots.
composite("path", [
    (source("mud_forest", 0.85, 1.65), flat(0.5)),
    (source("forest_ground_04", 0.9, 0.95), patches(2, 0.5, 0.88)),
    (source("rocky_trail", 0.75, 0.82), patches(3, 0.68, 0.95)),
    (source("roots", 0.8, 0.95), patches(2, 0.55, 0.88)),
])

print("GROUND_DONE")
