"""Bake the rock range's heightmap from AWS Terrain Tiles (terrarium PNGs, see fetch_dem.py).

    python bake_dem.py <tile dir> <out .r16> <preview dir> [N=320] [cx=264] [cy=378] [S=512] [sharpen=0.8]

Mosaics the 3x3 zoom-12 tiles around Passo Sella (Dolomites), crops an S x S px window centred on
(cx, cy) of the 768 px mosaic (~26 m/px -> S=512 ~ 13.5 km), box-filters it to N x N and applies a
LOCAL-RELIEF sharpen (unsharp mask, sigma ~2.5 samples): it steepens the limestone walls and
towers and deepens the gullies that the resample softens, without moving the big valleys. The
result is normalised to 0..65535 and written as raw little-endian u16 (row 0 = north).
"""
import sys, os
import numpy as np
from PIL import Image

src, out_bin, prev_dir = sys.argv[1], sys.argv[2], sys.argv[3]
N = int(sys.argv[4]) if len(sys.argv) > 4 else 320
cx = int(sys.argv[5]) if len(sys.argv) > 5 else 264
cy = int(sys.argv[6]) if len(sys.argv) > 6 else 378
S = int(sys.argv[7]) if len(sys.argv) > 7 else 512
sharpen = float(sys.argv[8]) if len(sys.argv) > 8 else 0.8
x0, y0 = 2181, 1447
mos = np.zeros((768, 768), np.float64)
for dy in range(3):
    for dx in range(3):
        im = np.asarray(Image.open(os.path.join(src, f"12_{x0+dx}_{y0+dy}.png")).convert("RGB")).astype(np.float64)
        h = im[..., 0] * 256 + im[..., 1] + im[..., 2] / 256 - 32768
        mos[dy*256:(dy+1)*256, dx*256:(dx+1)*256] = h


def shade(a):
    gy, gx = np.gradient(a)
    s = np.clip(0.5 + (-gx + gy) * 0.02, 0, 1)
    return Image.fromarray((s * 255).astype(np.uint8))


os.makedirs(prev_dir, exist_ok=True)
crop = mos[cy - S//2: cy + S//2, cx - S//2: cx + S//2]
print("crop m min/max", crop.min(), crop.max(), crop.shape)
a = np.asarray(Image.fromarray(crop.astype(np.float32), mode="F").resize((N, N), Image.BOX), np.float64)
if sharpen > 0:
    k = np.exp(-0.5 * (np.arange(-8, 9) / 2.5) ** 2)
    k /= k.sum()
    pad = np.pad(a, 8, mode="edge")
    blur = np.apply_along_axis(lambda r: np.convolve(r, k, mode="valid"), 1, pad)
    blur = np.apply_along_axis(lambda c: np.convolve(c, k, mode="valid"), 0, blur)
    a = a + sharpen * (a - blur)
lo, hi = a.min(), a.max()
print("resampled min/max", lo, hi)
u = np.round((a - lo) / (hi - lo) * 65535).astype("<u2")
u.tofile(out_bin)
shade(a * (N / S)).save(os.path.join(prev_dir, "crop_shade.png"))
print("wrote", out_bin, os.path.getsize(out_bin))
