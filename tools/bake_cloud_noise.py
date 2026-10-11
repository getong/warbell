"""Bake the tileable cloud-sky noise texture used by `src/clouds.rs` / `assets/shaders/clouds.wgsl`.

    python tools/bake_cloud_noise.py            # writes assets/sky/cloud_noise.png

512x512 RGBA8, every channel tiles seamlessly (all lattices are periodic):
  R  Perlin-Worley base shape  - billowy cumulus "cauliflower" lobes (Schneider 2015 remap of
                                 a Perlin fBm by an inverted Worley fBm)
  G  inverted Worley fBm detail - erodes the cloud edges into wisps / small puffs
  B  low-frequency Perlin fBm   - coverage / "weather" map: clear sky vs. cloud banks
  A  255
Original procedural work (no third-party data), CC0 like the rest of the generated assets.
"""

import numpy as np
from PIL import Image

N = 512
rng = np.random.default_rng(0xC10D5)


def perlin(freq: int, seed: int) -> np.ndarray:
    """Periodic 2D gradient noise in ~[-1, 1] with `freq` cells across the tile."""
    r = np.random.default_rng(seed)
    ang = r.uniform(0, 2 * np.pi, (freq, freq))
    gx, gy = np.cos(ang), np.sin(ang)
    c = np.arange(N) * freq / N
    x, y = np.meshgrid(c, c)
    xi, yi = np.floor(x).astype(int), np.floor(y).astype(int)
    xf, yf = x - xi, y - yi

    def dot(ox, oy):
        ix, iy = (xi + ox) % freq, (yi + oy) % freq
        return gx[iy, ix] * (xf - ox) + gy[iy, ix] * (yf - oy)

    fade = lambda t: t * t * t * (t * (t * 6 - 15) + 10)
    u, v = fade(xf), fade(yf)
    n0 = dot(0, 0) * (1 - u) + dot(1, 0) * u
    n1 = dot(0, 1) * (1 - u) + dot(1, 1) * u
    return (n0 * (1 - v) + n1 * v) * 1.41


def worley(freq: int, seed: int) -> np.ndarray:
    """Periodic F1 cellular noise, 0 at feature points → ~1 at cell borders."""
    r = np.random.default_rng(seed)
    pts = r.uniform(0, 1, (freq, freq, 2))
    c = np.arange(N) * freq / N
    x, y = np.meshgrid(c, c)
    xi, yi = np.floor(x).astype(int), np.floor(y).astype(int)
    best = np.full((N, N), 9.0)
    for oy in (-1, 0, 1):
        for ox in (-1, 0, 1):
            cx, cy = xi + ox, yi + oy
            p = pts[cy % freq, cx % freq]
            dx = cx + p[..., 0] - x
            dy = cy + p[..., 1] - y
            best = np.minimum(best, np.sqrt(dx * dx + dy * dy))
    return np.clip(best, 0, 1)


def fbm(fn, base: int, octaves: int, seed: int, gain=0.5) -> np.ndarray:
    acc, amp, tot = np.zeros((N, N)), 1.0, 0.0
    for o in range(octaves):
        acc += amp * fn(base * 2**o, seed + o * 101)
        tot += amp
        amp *= gain
    return acc / tot


def norm(a: np.ndarray) -> np.ndarray:
    lo, hi = np.percentile(a, 0.5), np.percentile(a, 99.5)
    return np.clip((a - lo) / (hi - lo), 0, 1)


def remap(v, lo, hi, nlo, nhi):
    return nlo + (v - lo) / (hi - lo) * (nhi - nlo)


# Base shape: Perlin fBm, billowed by inverted Worley (rounded lobes instead of mushy blobs).
p = norm(fbm(perlin, 4, 5, 11))
w = 1.0 - (0.625 * worley(4, 31) + 0.25 * worley(8, 37) + 0.125 * worley(16, 41)) / 1.0
pw = norm(np.clip(remap(p, w - 1.0, 1.0, 0.0, 1.0), 0, 1))
# Detail: higher-frequency inverted Worley fBm.
d = norm(1.0 - (0.625 * worley(16, 53) + 0.25 * worley(32, 59) + 0.125 * worley(64, 61)))
# Weather / coverage map.
cov = norm(fbm(perlin, 2, 3, 71, gain=0.45))

rgba = np.stack([pw, d, cov, np.ones_like(pw)], axis=-1)
out = (rgba * 255.0 + 0.5).astype(np.uint8)
Image.fromarray(out, "RGBA").save("assets/sky/cloud_noise.png", optimize=True)
print("wrote assets/sky/cloud_noise.png", out.shape)
