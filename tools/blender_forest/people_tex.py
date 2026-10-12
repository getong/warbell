"""Townsfolk garment DETAIL layers -> people_<layer>_{albedo,normal,ormh}.png, packed into the
4-layer `people_*.dds` arrays by `PACK_ONLY=people cargo run --release --example pack_forest_textures`
(then delete the PNG intermediates; only the .dds ship).

Layer order = the creature shader's people kinds (peasant_model.rs `cloth_kind`):
  0 linen (shirts, tunics, kerchiefs, aprons)  1 wool (hose, cloaks, kirtles)
  2 leather (belts, boots, pouches)            3 skin (faces, hands)
Albedo is a mean-0.5 DETAIL map: the per-person palette colour in the vertex colour carries the
hue and the shader multiplies detail x 2, so one shared array serves every villager.
Poly Haven CC0 scans: rough_linen, poly_wool_herringbone, brown_leather (2K PNGs under
$PH_SRC/textures/<id>/). Skin is procedural (no fitting CC0 scan).

    blender -b --factory-startup --python tools/blender_forest/people_tex.py
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
from common import OUT, ph_tex, save, write_pbr_set  # noqa: E402

S = 512

for name, aid, dkey, sat in (("linen", "rough_linen", "diff", 0.0), ("wool", "poly_wool_herringbone", "diff", 0.0),
                             ("leather", "brown_leather", "albedo", 0.25)):
    write_pbr_set(f"people_{name}", ph_tex(aid, dkey), ph_tex(aid, "nor_gl"), ph_tex(aid, "rough"),
                  ao=ph_tex(aid, "ao"), disp=ph_tex(aid, "disp"), size=S, sat=sat, normalize=True)

# Skin: soft blotchy mottle, fine pores and creases - subtle (faces are small on screen).
rng = np.random.default_rng(5)
u = np.arange(S, dtype=np.float32) / S
x, y = np.meshgrid(u, u)


def waves(freq, n=6, aniso=(1.0, 1.0)):
    out = np.zeros((S, S), np.float32)
    amp = 1.0
    for o in range(3):
        f = freq * 2 ** o
        for _ in range(n):
            kx = int(rng.integers(-f, f + 1) * aniso[0])
            ky = int(rng.integers(-f, f + 1) * aniso[1]) or f
            out += amp * np.cos(2 * np.pi * (kx * x + ky * y) + rng.uniform(0, 6.3))
        amp *= 0.5
    out -= out.min()
    return out / max(out.max(), 1e-6)


mottle = waves(3)
pores = waves(60, 10)
crease = np.abs(waves(12, 6, (1.0, 0.3)) - 0.5) * 2
h = 0.5 * mottle + 0.3 * pores + 0.2 * crease
lum = 0.86 + 0.2 * mottle - 0.08 * (1 - pores) - 0.05 * (1 - crease)
a = np.clip(lum / lum.mean() * 0.5, 0, 1)
# A faint warm/cool variation in the skin detail (veins vs flush), still averaging grey.
rgb = np.stack([a * (1.0 + 0.04 * (mottle - 0.5)), a, a * (1.0 - 0.05 * (mottle - 0.5))], -1)
save(np.clip(rgb, 0, 1), OUT / "people_skin_albedo.png")
gy, gx = np.gradient(np.pad(h, 1, mode="wrap"))
n = np.stack([-gx[1:-1, 1:-1] * 5.0, gy[1:-1, 1:-1] * 5.0, np.ones_like(h)], -1)
n /= np.linalg.norm(n, axis=-1, keepdims=True)
save(n * 0.5 + 0.5, OUT / "people_skin_normal.png")
save(np.stack([0.88 + 0.12 * h, 0.5 + 0.18 * mottle + 0.1 * (1 - pores), np.zeros_like(h), h], -1),
     OUT / "people_skin_ormh.png")
print("PEOPLE_TEX_DONE")
