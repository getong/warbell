"""Bake the horizon islands (`src/distant_isles.rs`) from REAL terrain.

For each island below: download AWS Terrain Tiles (terrarium-encoded elevation, open data) and
Sentinel-2 cloudless 2016 imagery (EOX, CC BY 4.0) for its lon/lat box, resample both onto a
regular METRIC grid, and write

    assets/isles/<name>_height.bin   GRID x GRID little-endian f32 metres (row-major, north row first)
    assets/isles/<name>_albedo.png   ALB x ALB sRGB, same footprint
    assets/isles/isles.json          per-island width/depth in metres + max height

Raw tiles are cached under ../downloads/terrain/<name>/ (outside the repo). Run:
    python -I tools/terrain_isles/fetch_isles.py [name ...]
"""

import io
import json
import math
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "assets" / "isles"
CACHE = Path("C:/Users/skibi/Documents/Codex/downloads/terrain")
DEM_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
SAT_URL = "https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless_3857/default/g/{z}/{y}/{x}.jpg"
GRID = 288
# Islands whose DEM source is a coarse blob (Jan Mayen): trust the satellite coastline instead.
# Not applied elsewhere — Stromboli's dark lava slide reads as sea to the colour test.
MASK_WITH_SATELLITE = {"beerenberg"}
ALB = 1024

# name: (lon_min, lat_min, lon_max, lat_max, dem_zoom, sat_zoom)
ISLES = {
    # Lofoten, Moskenesøya + Flakstadøya: jagged granite peaks (~1 000 m) straight out of the sea.
    "lofoten": (12.86, 67.87, 13.42, 68.12, 12, 13),
    # Lofoten, Austvågøya: a second, taller serrated ridge for the far layer.
    "austvagoy": (14.30, 68.17, 14.95, 68.42, 12, 13),
    # Stromboli: the classic smoking cone (924 m).
    "stromboli": (15.175, 38.765, 15.255, 38.825, 13, 14),
    # Fogo, Cape Verde: an arid desert stratovolcano (2 829 m) sitting in a broken caldera.
    "fogo": (-24.52, 14.80, -24.27, 15.06, 12, 13),
    # La Gomera: green, forest-crowned, ravine-cut (1 487 m).
    "gomera": (-17.36, 28.00, -17.08, 28.23, 12, 13),
    # Jan Mayen, Beerenberg: a glaciated snow volcano (2 277 m).
    "beerenberg": (-8.40, 70.98, -7.90, 71.18, 12, 12),
}


def tile_xy(lon, lat, z):
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n
    y = (1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n
    return x, y


def fetch(url, path):
    if path.exists() and path.stat().st_size > 0:
        return path.read_bytes()
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "warbell-terrain-bake/1.0"})
            data = urllib.request.urlopen(req, timeout=30).read()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            time.sleep(0.05)
            return data
        except Exception as e:  # noqa: BLE001
            print("  retry", url, e)
            time.sleep(2 ** attempt)
    raise RuntimeError(url)


def mosaic(box, z, url, cache, decode):
    """Stitch every tile covering `box` at zoom `z`; returns (array, x0_tile, y0_tile)."""
    lon0, lat0, lon1, lat1 = box
    xa, ya = tile_xy(lon0, lat1, z)
    xb, yb = tile_xy(lon1, lat0, z)
    tx0, ty0, tx1, ty1 = int(xa), int(ya), int(xb), int(yb)
    rows = []
    for ty in range(ty0, ty1 + 1):
        row = []
        for tx in range(tx0, tx1 + 1):
            data = fetch(url.format(z=z, x=tx, y=ty), cache / f"{z}_{tx}_{ty}{Path(url).suffix}")
            row.append(decode(Image.open(io.BytesIO(data))))
        rows.append(np.concatenate(row, axis=1))
    return np.concatenate(rows, axis=0), tx0, ty0


def dem_decode(img):
    a = np.asarray(img.convert("RGB"), dtype=np.float64)
    return a[..., 0] * 256.0 + a[..., 1] + a[..., 2] / 256.0 - 32768.0


def sat_decode(img):
    return np.asarray(img.convert("RGB"), dtype=np.float32)


def sample(arr, px, py):
    """Bilinear sample `arr` at fractional pixel coords (arrays)."""
    h, w = arr.shape[:2]
    px = np.clip(px, 0, w - 1.001)
    py = np.clip(py, 0, h - 1.001)
    x0 = np.floor(px).astype(int)
    y0 = np.floor(py).astype(int)
    fx = px - x0
    fy = py - y0
    if arr.ndim == 3:
        fx = fx[..., None]
        fy = fy[..., None]
    a = arr[y0, x0] * (1 - fx) + arr[y0, x0 + 1] * fx
    b = arr[y0 + 1, x0] * (1 - fx) + arr[y0 + 1, x0 + 1] * fx
    return a * (1 - fy) + b * fy


def resample(arr, tx0, ty0, z, box, n):
    """Regular n x n grid over the box (north row first) → pixel coords in the mosaic."""
    lon0, lat0, lon1, lat1 = box
    lons = np.linspace(lon0, lon1, n)
    lats = np.linspace(lat1, lat0, n)
    LON, LAT = np.meshgrid(lons, lats)
    nz = 2 ** z
    X = (LON + 180.0) / 360.0 * nz
    Y = (1.0 - np.arcsinh(np.tan(np.radians(LAT))) / np.pi) / 2.0 * nz
    return sample(arr, (X - tx0) * 256.0, (Y - ty0) * 256.0)


def bake(name):
    lon0, lat0, lon1, lat1, dz, sz = ISLES[name]
    box = (lon0, lat0, lon1, lat1)
    cache = CACHE / name
    print(name, "dem…")
    dem, dx0, dy0 = mosaic(box, dz, DEM_URL, cache / "dem", dem_decode)
    h = resample(dem, dx0, dy0, dz, box, GRID).astype(np.float32)
    print(name, "satellite…")
    sat, sx0, sy0 = mosaic(box, sz, SAT_URL, cache / "sat", sat_decode)
    alb = resample(sat, sx0, sy0, sz, box, ALB)
    # Some DEM sources around remote islands are coarse blobs far bigger than the real coastline;
    # trust the satellite for where land is: open-sea pixels (dark, blue-dominant) sink below 0.
    sg = resample(sat, sx0, sy0, sz, box, GRID)
    lum = sg @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    cand = (sg[..., 2] > sg[..., 1]) & (sg[..., 2] > sg[..., 0] + 8) & (lum < 100)
    # Only open sea: candidates flood-filled from the bake box's border (dark inland forest or
    # shadowed rock that happens to read bluish is never connected to the ocean).
    sea = np.zeros_like(cand)
    stack = [(y, x) for y in range(GRID) for x in (0, GRID - 1) if cand[y, x]]
    stack += [(y, x) for x in range(GRID) for y in (0, GRID - 1) if cand[y, x]]
    while stack:
        y, x = stack.pop()
        if sea[y, x] or not cand[y, x]:
            continue
        sea[y, x] = True
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < GRID and 0 <= nx < GRID and not sea[ny, nx] and cand[ny, nx]:
                stack.append((ny, nx))
    if name in MASK_WITH_SATELLITE:
        h = np.where(sea, np.minimum(h, -15.0), h).astype(np.float32)
    OUT.mkdir(parents=True, exist_ok=True)
    h.astype("<f4").tofile(OUT / f"{name}_height.bin")
    Image.fromarray(np.clip(alb, 0, 255).astype(np.uint8)).save(OUT / f"{name}_albedo.png", optimize=True)
    midlat = math.radians((lat0 + lat1) / 2)
    width = (lon1 - lon0) * 111_320.0 * math.cos(midlat)
    depth = (lat1 - lat0) * 110_540.0
    print(f"  {width:.0f} x {depth:.0f} m, max {h.max():.0f} m, min {h.min():.0f} m")
    return {"width": width, "depth": depth, "max": float(h.max()), "grid": GRID}


def main():
    names = sys.argv[1:] or list(ISLES)
    meta_path = OUT / "isles.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    for n in names:
        meta[n] = bake(n)
    meta_path.write_text(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
