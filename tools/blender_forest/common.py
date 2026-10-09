"""Shared helpers for the Blender forest pipeline (run inside Blender's bundled Python).

Every script in this folder is executed headless:

    blender -b --factory-startup --python tools/blender_forest/<script>.py

Sources are Poly Haven CC0 downloads (see README.md); outputs land in assets/forest_pbr/.
Images are handled as numpy arrays in TOP-DOWN row order (row 0 = top of the picture, the
way image editors and the crop rectangles in these scripts count pixels). Blender stores
pixels bottom-up, so `load` / `save` flip at the boundary.
"""
import os
from pathlib import Path

import bpy
import numpy as np

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "assets" / "forest_pbr"
PH = Path(os.environ.get("PH_SRC", r"C:/Users/skibi/Documents/Codex/polyhaven_src"))


def ph_tex(aid, key):
    """Path of a downloaded Poly Haven texture map (`diff` also matches `diffuse`)."""
    hits = sorted((PH / "textures" / aid).glob(f"{aid}_{key}*_2k.png"))
    if not hits:
        raise SystemExit(f"missing {aid} {key}")
    return hits[0]


def ph_model_tex(aid, name):
    """Path of a texture shipped with a downloaded Poly Haven model (1k jpg/png)."""
    p = PH / "models" / aid / "textures" / name
    if not p.exists():
        raise SystemExit(f"missing {p}")
    return p


def load(path, channels=4):
    """Load an image file as float32 HxWxC in [0,1], top-down, raw (no colour conversion)."""
    img = bpy.data.images.load(str(path), check_existing=False)
    img.colorspace_settings.name = "Non-Color"
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    arr = px.reshape(h, w, 4)[::-1]
    return np.ascontiguousarray(arr[:, :, :channels])


def save(arr, path):
    """Save an HxW(xC) float array in [0,1] as an 8-bit PNG (RGBA), top-down."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    a = np.asarray(arr, dtype=np.float32)
    if a.ndim == 2:
        a = a[:, :, None]
    h, w, c = a.shape
    rgba = np.ones((h, w, 4), dtype=np.float32)
    if c == 1:
        rgba[:, :, :3] = a
    else:
        rgba[:, :, :c] = a
    img = bpy.data.images.new(path.stem, w, h, alpha=True)
    img.colorspace_settings.name = "Non-Color"
    img.pixels.foreach_set(np.clip(rgba[::-1], 0, 1).ravel())
    img.filepath_raw = str(path)
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)


def resize(arr, w, h):
    """Area-average down / bilinear up resize of an HxWxC array."""
    sh, sw = arr.shape[:2]
    if (sw, sh) == (w, h):
        return arr
    if sw % w == 0 and sh % h == 0 and sw >= w:
        fx, fy = sw // w, sh // h
        return arr.reshape(h, fy, w, fx, -1).mean(axis=(1, 3)).reshape(h, w, *arr.shape[2:])
    ys = (np.arange(h) + 0.5) * sh / h - 0.5
    xs = (np.arange(w) + 0.5) * sw / w - 0.5
    return bilinear(arr, xs[None, :].repeat(h, 0), ys[:, None].repeat(w, 1))


def bilinear(arr, x, y):
    """Sample arr at float pixel coords (x, y arrays of equal shape), clamped edges."""
    sh, sw = arr.shape[:2]
    x = np.clip(x, 0, sw - 1.001)
    y = np.clip(y, 0, sh - 1.001)
    x0 = np.floor(x).astype(np.int32)
    y0 = np.floor(y).astype(np.int32)
    fx = (x - x0)[..., None]
    fy = (y - y0)[..., None]
    a = arr.reshape(sh, sw, -1)
    c00 = a[y0, x0]
    c10 = a[y0, x0 + 1]
    c01 = a[y0 + 1, x0]
    c11 = a[y0 + 1, x0 + 1]
    out = (c00 * (1 - fx) + c10 * fx) * (1 - fy) + (c01 * (1 - fx) + c11 * fx) * fy
    return out.reshape(*x.shape, *arr.shape[2:])


def srgb_to_lin(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def grade(srgb, sat=1.0, gain=1.0):
    """Saturation/value grade done in linear light, returned as sRGB."""
    lin = srgb_to_lin(srgb)
    luma = (lin * np.array([0.2126, 0.7152, 0.0722])).sum(-1, keepdims=True)
    return lin_to_srgb((luma + (lin - luma) * sat) * gain)


def write_pbr_set(name, diff, nor, rough, ao=None, disp=None, size=1024, sat=1.0, gain=1.0,
                  normalize=False):
    """Pack one material into `<name>_albedo.png` (sRGB), `<name>_normal.png` (OpenGL tangent
    space) and `<name>_ormh.png` (linear glTF ORM - R=AO, G=roughness, B=metallic 0 - plus
    A=height normalised to 0..1, read by the terrain parallax).
    `rough` / `ao` / `disp` are file paths, or `(path, channel)` to pull one channel of a
    packed map (Poly Haven `arm` = AO, rough, metal). Missing AO -> 1, missing height -> 0.5."""
    def chan(src):
        if src is None:
            return None
        path, ch = src if isinstance(src, tuple) else (src, 0)
        return resize(load(path, 3), size, size)[:, :, ch]

    albedo = grade(resize(load(diff, 3), size, size), sat, gain)
    if normalize:
        albedo = np.clip(albedo / (albedo.mean(axis=(0, 1), keepdims=True) + 1e-4) * 0.5, 0, 1)
    n = resize(load(nor, 3), size, size) * 2.0 - 1.0
    n /= np.linalg.norm(n, axis=-1, keepdims=True) + 1e-6
    r = chan(rough)
    a = chan(ao)
    a = np.ones_like(r) if a is None else a
    h = chan(disp)
    if h is None:
        h = np.full_like(r, 0.5)
    else:
        lo, hi = np.percentile(h, [0.5, 99.5])
        h = np.clip((h - lo) / max(hi - lo, 1e-4), 0, 1)
    save(albedo, OUT / f"{name}_albedo.png")
    save(n * 0.5 + 0.5, OUT / f"{name}_normal.png")
    save(np.stack([a, r, np.zeros_like(r), h], -1), OUT / f"{name}_ormh.png")
    print(f"pbr {name}: albedo mean {albedo.mean(axis=(0, 1)).round(3)}")


def bleed_alpha(rgb, alpha, steps=24):
    """Dilate opaque colour into transparent texels so mip levels of cut-out foliage don't
    pick up a dark/magenta fringe from whatever the source left under alpha 0."""
    rgb = rgb.copy()
    known = alpha > 0.5
    for _ in range(steps):
        if known.all():
            break
        acc = np.zeros_like(rgb)
        cnt = np.zeros(known.shape, dtype=np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
            k = np.roll(np.roll(known, dy, 0), dx, 1)
            c = np.roll(np.roll(rgb, dy, 0), dx, 1)
            acc += c * k[..., None]
            cnt += k
        grow = (~known) & (cnt > 0)
        rgb[grow] = acc[grow] / cnt[grow][:, None]
        known = known | grow
    rgb[~known] = rgb[known].mean(axis=0) if known.any() else 0.5
    return rgb


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def export_glb(path, objects, tangents=True):
    """Export only `objects` as a geometry GLB: positions, normals, UV0, tangents, vertex colour.
    Materials export as NAMES only (no textures) - the game binds its own PBR sets by name.
    `tangents=False` skips them (meshes whose UV0 is data, not a texture mapping)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    for o in objects:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.export_scene.gltf(
        filepath=str(path),
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_yup=True,
        export_texcoords=True,
        export_normals=True,
        export_tangents=tangents,
        export_vertex_color="ACTIVE",
        export_all_vertex_colors=False,
        export_materials="EXPORT",
        export_image_format="NONE",
        export_animations=False,
        export_skins=False,
        export_morph=False,
        export_cameras=False,
        export_lights=False,
    )


def name_material(name):
    return bpy.data.materials.get(name) or bpy.data.materials.new(name)
