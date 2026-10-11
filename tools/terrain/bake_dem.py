"""Mosaic terrarium tiles, crop the Dolomites (Sella/Langkofel), resample to N×N u16 LE."""
import sys, os
import numpy as np
from PIL import Image

src, out_bin, prev_dir = sys.argv[1], sys.argv[2], sys.argv[3]
N = int(sys.argv[4]) if len(sys.argv) > 4 else 160
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
shade(mos).save(os.path.join(prev_dir, "mosaic_shade.png"))
cx, cy = int(sys.argv[5]) if len(sys.argv) > 5 else 264, int(sys.argv[6]) if len(sys.argv) > 6 else 378
S = int(sys.argv[7]) if len(sys.argv) > 7 else 512
crop = mos[cy - S//2: cy + S//2, cx - S//2: cx + S//2]
print("crop m min/max", crop.min(), crop.max(), crop.shape)
img = Image.fromarray(crop.astype(np.float32), mode="F").resize((N, N), Image.BOX)
a = np.asarray(img, np.float64)
lo, hi = a.min(), a.max()
print("resampled min/max", lo, hi)
u = np.round((a - lo) / (hi - lo) * 65535).astype("<u2")
u.tofile(out_bin)
shade(a * (N / S)).resize((N * 3, N * 3)).save(os.path.join(prev_dir, "crop_shade.png"))
Image.fromarray((u >> 8).astype(np.uint8)).resize((N * 3, N * 3)).save(os.path.join(prev_dir, "crop_height.png"))
print("wrote", out_bin, os.path.getsize(out_bin))
