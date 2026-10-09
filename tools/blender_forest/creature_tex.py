"""Creature surface DETAIL layers -> creature_<layer>_{albedo,normal,ormh}.png (packed into the
7-layer `creature_*.dds` arrays by pack_forest_textures).

Layer order = the creature shader's surface codes (creature.rs `Surf`):
  0 skin  1 fur  2 leather (Surf::Scale)  3 wood (Surf::Stone)  4 metal  5 cloth  6 bone
Albedo is a mean-0.5 DETAIL map (the rig's vertex colour carries the hue; the shader multiplies
detail x 2), so one set serves every ork variant, peasant and animal coat. Skin, fur and bone
are procedural (no fitting CC0 scan); leather, wood, metal and cloth come from Poly Haven scans.
Run headless in Blender (numpy) or any Python with numpy + the common helpers.
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
from common import OUT, ph_tex, save, write_pbr_set  # noqa: E402

S = 512
rng = np.random.default_rng(23)


def tile_noise(freq, octaves=4, aniso=(1.0, 1.0), gen=None):
    gen = rng if gen is None else gen
    u = np.arange(S, dtype=np.float32) / S
    x, y = np.meshgrid(u, u)
    n = np.zeros((S, S), np.float32)
    amp = 1.0
    for o in range(octaves):
        f = freq * (2 ** o)
        for _ in range(4):
            kx = int(gen.integers(-f, f + 1) * aniso[0])
            ky = int(gen.integers(-f, f + 1) * aniso[1])
            if kx == 0 and ky == 0:
                ky = f
            n += amp * np.cos(2 * np.pi * (kx * x + ky * y) + gen.uniform(0, 6.3))
        amp *= 0.55
    n -= n.min()
    return n / max(n.max(), 1e-6)


def cells(freq):
    """Tileable Worley-ish cell distance (pores / scales)."""
    pts = rng.random((freq * freq, 2))
    u = (np.arange(S) + 0.5) / S
    x, y = np.meshgrid(u, u)
    d = np.full((S, S), 9.0, np.float32)
    for px, py in pts:
        for ox in (-1, 0, 1):
            for oy in (-1, 0, 1):
                dd = (x - px - ox) ** 2 + (y - py - oy) ** 2
                d = np.minimum(d, dd)
    d = np.sqrt(d) * freq
    return np.clip(d, 0, 1)


def normal_from_height(h, k):
    gy, gx = np.gradient(np.pad(h, 1, mode="wrap"))
    gx, gy = gx[1:-1, 1:-1], gy[1:-1, 1:-1]
    n = np.stack([-gx * k, gy * k, np.ones_like(h)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n * 0.5 + 0.5


def write_proc(name, albedo_l, height, rough, k):
    a = np.clip(albedo_l / max(albedo_l.mean(), 1e-4) * 0.5, 0, 1)
    save(np.stack([a, a, a], -1), OUT / f"creature_{name}_albedo.png")
    save(normal_from_height(height, k), OUT / f"creature_{name}_normal.png")
    save(np.stack([np.ones_like(rough) * (0.85 + 0.15 * height), rough, np.zeros_like(rough), height], -1),
         OUT / f"creature_{name}_ormh.png")
    print(f"creature {name}: done")


# Skin: soft mottle, pores, fine wrinkles.
mottle = tile_noise(3, 4)
pores = cells(28)
wrinkle = np.abs(tile_noise(10, 3) - 0.5) * 2
h_skin = 0.55 * mottle + 0.3 * (1 - np.exp(-pores * 3)) + 0.15 * wrinkle
alb_skin = 0.8 + 0.25 * mottle - 0.12 * np.exp(-pores * 6) - 0.06 * (1 - wrinkle)
write_proc("skin", alb_skin, h_skin, 0.55 + 0.15 * mottle, 6.0)

# (The old strand maps' draws stay so the bone layer below keeps its exact noise.)
_ = tile_noise(24, 3, aniso=(1.0, 0.12)), tile_noise(4, 3)


def fur_maps():
    """Fur clumps along +V (tips point down the image = down the animal's fur flow; the animal kit
    lays V root -> tip). Three sizes of randomly placed hair clumps, each a long teardrop whose
    strands converge to its tip, agouti-banded (shadowed root, light band, darker tip). Where
    clumps overlap, the one whose TIP reaches the texel lies on top (larger t wins), so tips
    shingle over the next clumps' roots like a real coat. Returns (lum, height, occlusion)."""
    fr = np.random.default_rng(71)
    key = np.full((S, S), -1.0, np.float32)
    lum = np.full((S, S), 0.42, np.float32)
    hgt = np.zeros((S, S), np.float32)
    occ = np.full((S, S), 0.62, np.float32)
    # (count, length px, half-width px): coarse clumps first, finer ones fill and break them up.
    for count, length, half in ((60, 150, 15), (150, 105, 10), (320, 70, 6.5)):
        for _ in range(count):
            x0, y0 = fr.uniform(0, S, 2)
            L = length * fr.uniform(0.75, 1.3)
            W = half * fr.uniform(0.75, 1.3)
            bend = fr.uniform(-0.6, 0.6) * W
            n = int(np.clip(fr.integers(3, 7), 2, max(2, W / 2.6)))
            ph = fr.uniform(0, 6.3)
            gain = fr.uniform(0.76, 1.2)
            iy = np.arange(int(L) + 1)
            ix = np.arange(-int(W) - 2, int(W) + 3)
            ys = (int(y0) + iy) % S
            xs = (int(x0) + ix) % S
            t = iy[:, None] / L
            dx = ix[None, :] - bend * t * t
            wt = W * np.clip(1.0 - t, 0.0, 1.0) ** 0.6 * (0.7 + 0.3 * np.clip(t * 5, 0, 1)) + 0.5
            q = dx / wt
            m = (np.abs(q) < 1.0) & (t <= 1.0)
            k = t + fr.uniform(0, 0.12)
            win = np.ix_(ys, xs)
            take = m & (k > key[win])
            if not take.any():
                continue
            prof = np.sqrt(np.clip(1.0 - q * q, 0.0, 1.0))
            band = 0.6 + 0.4 * np.clip(t / 0.4, 0, 1) - 0.2 * np.clip((t - 0.75) / 0.25, 0, 1)
            strand = 0.5 + 0.5 * np.cos(np.pi * n * q + ph)
            l = gain * band * (0.7 + 0.3 * prof ** 0.5) * (0.9 + 0.1 * strand)
            h = prof * (0.3 + 0.7 * t) * (0.85 + 0.15 * strand)
            o = 0.62 + 0.38 * np.clip(t * 1.6, 0, 1) * prof
            key[win] = np.where(take, k, key[win])
            lum[win] = np.where(take, l, lum[win])
            hgt[win] = np.where(take, h, hgt[win])
            occ[win] = np.where(take, o, occ[win])
    fine = tile_noise(48, 2, aniso=(1.0, 0.25), gen=fr)
    lum = lum * (0.92 + 0.16 * fine)

    def soften(a):  # 1-2-1 wrap blur for the bump / occlusion (no single-texel stair-steps)
        a = (np.roll(a, 1, 0) + 2 * a + np.roll(a, -1, 0)) * 0.25
        return (np.roll(a, 1, 1) + 2 * a + np.roll(a, -1, 1)) * 0.25

    # Across-strand 1-2-1 blur: the finest strand stripes alias into a stipple on the GPU.
    lum = (np.roll(lum, 1, 1) + 2 * lum + np.roll(lum, -1, 1)) * 0.25
    return lum, soften(hgt), soften(occ)


def fur_layer():
    lum, hgt, occ = fur_maps()
    a = np.clip(lum / max(lum.mean(), 1e-4) * 0.5, 0, 1)
    save(np.stack([a, a, a], -1), OUT / "creature_fur_albedo.png")
    save(normal_from_height(hgt, 7.0), OUT / "creature_fur_normal.png")
    rough = 0.78 + 0.16 * (1.0 - hgt)
    save(np.stack([occ, rough, np.zeros_like(rough), hgt], -1), OUT / "creature_fur_ormh.png")
    print("creature fur: done")


fur_layer()

# Bone: fine grain + hairline cracks.
grain = tile_noise(14, 3)
crack = np.exp(-np.abs(tile_noise(5, 3) - 0.5) * 60)
h_bone = 0.7 * grain - 0.3 * crack + 0.3
alb_bone = 0.95 + 0.12 * grain - 0.35 * crack
write_proc("bone", alb_bone, h_bone, 0.45 + 0.2 * grain, 3.0)

# Scanned layers (mean-normalised detail).
for name, aid, sat in (("leather", "fabric_leather_02", 0.4), ("wood", "medieval_wood", 0.4),
                       ("metal", "rusty_metal_02", 0.5), ("cloth", "hessian_230", 0.3)):
    write_pbr_set(f"creature_{name}", ph_tex(aid, "diff"), ph_tex(aid, "nor_gl"), ph_tex(aid, "rough"),
                  ao=ph_tex(aid, "ao"), disp=ph_tex(aid, "disp"), size=S, sat=sat, normalize=True)

print("CREATURE_TEX_DONE")
