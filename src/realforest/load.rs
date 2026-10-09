//! Synchronous loaders for the Blender forest kit: PNG → mip-mapped `Image`, and GLB →
//! CPU `Mesh`es keyed by object name.
//!
//! Synchronous on purpose (same reason as `phototrees` / the footman): the world scatter runs
//! inside the `Startup` build chain and needs the meshes' CPU data (to merge chunk meshes) and
//! their handles on the very first frame — an `AssetServer` load would still be in flight.

use bevy::asset::RenderAssetUsages;
use bevy::image::{ImageAddressMode, ImageFilterMode, ImageSampler, ImageSamplerDescriptor};
use bevy::mesh::{Indices, PrimitiveTopology, VertexAttributeValues};
use bevy::prelude::*;
use bevy::render::render_resource::{
    Extent3d, TextureDimension, TextureFormat, TextureViewDescriptor, TextureViewDimension,
};

/// Absolute path of a file under `assets/` (exe dir / `BEVY_ASSET_ROOT` / crate root / CWD).
pub fn asset_path(rel: &str) -> std::path::PathBuf {
    crate::phototrees::atlas::resolve(&format!("assets/{rel}"))
}

/// Decoded RGBA8 pixels.
pub struct Rgba {
    pub w: u32,
    pub h: u32,
    pub px: Vec<u8>,
}

pub fn read_png(rel: &str) -> Result<Rgba, String> {
    let path = asset_path(rel);
    let bytes = std::fs::read(&path).map_err(|e| format!("{}: {e}", path.display()))?;
    let img = image::load_from_memory(&bytes).map_err(|e| format!("{}: {e}", path.display()))?.to_rgba8();
    let (w, h) = img.dimensions();
    Ok(Rgba { w, h, px: img.into_raw() })
}

fn srgb_to_lin(c: f32) -> f32 {
    if c <= 0.04045 { c / 12.92 } else { ((c + 0.055) / 1.055).powf(2.4) }
}

fn lin_to_srgb(c: f32) -> f32 {
    if c <= 0.003_130_8 { c * 12.92 } else { 1.055 * c.powf(1.0 / 2.4) - 0.055 }
}

/// Fraction of texels whose alpha passes `cutoff` (after scaling alpha by `scale`).
fn coverage(level: &[u8], cutoff: f32, scale: f32) -> f32 {
    let n = level.len() / 4;
    let pass = level.chunks_exact(4).filter(|p| (p[3] as f32 / 255.0) * scale >= cutoff).count();
    pass as f32 / n.max(1) as f32
}

/// Full box-filtered mip chain (gamma-correct for sRGB colour). With `cutoff`, each level's
/// alpha is rescaled so the fraction of texels passing the alpha test matches level 0 —
/// otherwise averaged leaf/blade edges fall under the cutoff and distant foliage thins out to
/// bare twigs (the classic "trees go bald at range" alpha-mip problem).
pub fn mip_chain(base: &[u8], w: u32, h: u32, srgb: bool, cutoff: Option<f32>) -> (Vec<u8>, u32) {
    let target = cutoff.map(|c| coverage(base, c, 1.0));
    // u8 → linear lookup (the decode side runs 16× per output texel; the encode side once).
    let lut: [f32; 256] = std::array::from_fn(|i| {
        let b = i as f32 / 255.0;
        if srgb { srgb_to_lin(b) } else { b }
    });
    let mut data = base.to_vec();
    let mut levels = 1u32;
    let (mut pw, mut ph, mut off) = (w, h, 0usize);
    while pw > 1 || ph > 1 {
        let (nw, nh) = ((pw / 2).max(1), (ph / 2).max(1));
        let mut next = vec![0u8; (nw * nh * 4) as usize];
        for y in 0..nh {
            for x in 0..nw {
                let mut acc = [0.0f32; 4];
                for dy in 0..2u32 {
                    for dx in 0..2u32 {
                        let sx = (x * 2 + dx).min(pw - 1);
                        let sy = (y * 2 + dy).min(ph - 1);
                        let i = off + ((sy * pw + sx) * 4) as usize;
                        for (c, a) in acc.iter_mut().enumerate() {
                            let b = data[i + c];
                            *a += if c < 3 { lut[b as usize] } else { b as f32 / 255.0 };
                        }
                    }
                }
                let o = ((y * nw + x) * 4) as usize;
                for (c, a) in acc.iter().enumerate() {
                    let v = a * 0.25;
                    let e = if srgb && c < 3 { lin_to_srgb(v) } else { v };
                    next[o + c] = (e.clamp(0.0, 1.0) * 255.0).round() as u8;
                }
            }
        }
        if let (Some(cut), Some(t)) = (cutoff, target) {
            // Binary-search the alpha scale that restores level-0 coverage.
            let (mut lo, mut hi) = (0.5f32, 4.0f32);
            for _ in 0..12 {
                let mid = (lo + hi) * 0.5;
                if coverage(&next, cut, mid) < t { lo = mid } else { hi = mid }
            }
            for p in next.chunks_exact_mut(4) {
                p[3] = ((p[3] as f32 * hi).min(255.0)).round() as u8;
            }
        }
        data.extend_from_slice(&next);
        off += (pw * ph * 4) as usize;
        pw = nw;
        ph = nh;
        levels += 1;
    }
    (data, levels)
}

pub fn repeat_sampler() -> ImageSampler {
    ImageSampler::Descriptor(ImageSamplerDescriptor {
        address_mode_u: ImageAddressMode::Repeat,
        address_mode_v: ImageAddressMode::Repeat,
        address_mode_w: ImageAddressMode::Repeat,
        mag_filter: ImageFilterMode::Linear,
        min_filter: ImageFilterMode::Linear,
        mipmap_filter: ImageFilterMode::Linear,
        anisotropy_clamp: 8,
        ..default()
    })
}

fn format(srgb: bool) -> TextureFormat {
    if srgb { TextureFormat::Rgba8UnormSrgb } else { TextureFormat::Rgba8Unorm }
}

/// A pre-packed BC7 DDS (`examples/pack_forest_textures.rs`): mips included, ~4x smaller than
/// RGBA8 in VRAM, no CPU mip build. `None` when the file isn't there (PNG fallback).
fn dds(rel: &str, array: bool) -> Option<Result<Image, String>> {
    let path = asset_path(rel);
    let bytes = std::fs::read(&path).ok()?;
    Some(
        Image::from_buffer(
            &bytes,
            bevy::image::ImageType::Extension("dds"),
            bevy::image::CompressedImageFormats::BC,
            true,
            repeat_sampler(),
            RenderAssetUsages::default(),
        )
        .map(|mut img| {
            if array {
                img.texture_view_descriptor = Some(TextureViewDescriptor {
                    dimension: Some(TextureViewDimension::D2Array),
                    ..default()
                });
            }
            img
        })
        .map_err(|e| format!("{}: {e}", path.display())),
    )
}

/// A mip-mapped, repeat-sampled 2D texture under `assets/`: the packed `.dds` twin of `rel` when
/// present, else the PNG (with a CPU-built, coverage-preserving mip chain).
pub fn texture(rel: &str, srgb: bool, cutoff: Option<f32>) -> Result<Image, String> {
    if let Some(img) = dds(&rel.replace(".png", ".dds"), false) {
        return img;
    }
    let src = read_png(rel)?;
    let (data, levels) = mip_chain(&src.px, src.w, src.h, srgb, cutoff);
    let mut img = Image::new(
        Extent3d { width: src.w, height: src.h, depth_or_array_layers: 1 },
        TextureDimension::D2,
        src.px,
        format(srgb),
        RenderAssetUsages::default(),
    );
    // `Image::new` validates the base level only; the chain and its count land afterwards.
    img.data = Some(data);
    img.texture_descriptor.mip_level_count = levels;
    img.sampler = repeat_sampler();
    Ok(img)
}

/// A mip-mapped 2D texture ARRAY: the packed multi-layer `.dds` at `packed` when present, else one
/// layer per PNG (all the same size), layer-major data order.
pub fn texture_array(packed: &str, rels: &[&str], srgb: bool) -> Result<Image, String> {
    if let Some(img) = dds(packed, true) {
        return img;
    }
    let mut data = Vec::new();
    let mut base = Vec::new();
    let (mut w, mut h, mut levels) = (0, 0, 1);
    for rel in rels {
        let src = read_png(rel)?;
        if w == 0 {
            (w, h) = (src.w, src.h);
        } else if (src.w, src.h) != (w, h) {
            return Err(format!("{rel}: layer size {}x{} != {w}x{h}", src.w, src.h));
        }
        let (chain, l) = mip_chain(&src.px, w, h, srgb, None);
        levels = l;
        base.extend_from_slice(&src.px);
        data.extend_from_slice(&chain);
    }
    let mut img = Image::new(
        Extent3d { width: w, height: h, depth_or_array_layers: rels.len() as u32 },
        TextureDimension::D2,
        base,
        format(srgb),
        RenderAssetUsages::default(),
    );
    img.data = Some(data);
    img.texture_descriptor.mip_level_count = levels;
    img.texture_view_descriptor = Some(TextureViewDescriptor {
        dimension: Some(TextureViewDimension::D2Array),
        ..default()
    });
    img.sampler = repeat_sampler();
    Ok(img)
}

/// A 1×1×`layers` array texture — the bind-group placeholder when the kit is off.
pub fn dummy_array(layers: u32, px: [u8; 4]) -> Image {
    let mut img = Image::new(
        Extent3d { width: 1, height: 1, depth_or_array_layers: layers },
        TextureDimension::D2,
        px.repeat(layers as usize),
        TextureFormat::Rgba8Unorm,
        RenderAssetUsages::default(),
    );
    img.texture_view_descriptor = Some(TextureViewDescriptor {
        dimension: Some(TextureViewDimension::D2Array),
        ..default()
    });
    img
}

/// One glTF primitive: its CPU mesh (POSITION/NORMAL/UV_0/TANGENT/COLOR, u32 indices) and the
/// material name Blender gave it.
pub struct Primitive {
    pub mesh: Mesh,
    pub material: String,
}

/// Every named mesh object in a GLB → its primitives.
pub fn read_glb(rel: &str) -> Result<Vec<(String, Vec<Primitive>)>, String> {
    let path = asset_path(rel);
    let bytes = std::fs::read(&path).map_err(|e| format!("{}: {e}", path.display()))?;
    let glb = gltf::Gltf::from_slice(&bytes).map_err(|e| format!("{rel}: {e}"))?;
    let blob = glb.blob.as_deref().ok_or_else(|| format!("{rel}: no binary chunk"))?;
    let mut out = Vec::new();
    for node in glb.document.nodes() {
        let Some(mesh) = node.mesh() else { continue };
        let name = node.name().unwrap_or_default().to_string();
        let mut prims = Vec::new();
        for prim in mesh.primitives() {
            let reader = prim.reader(|_| Some(blob));
            let pos: Vec<[f32; 3]> = reader.read_positions().ok_or(format!("{name}: no positions"))?.collect();
            let n = pos.len();
            let nrm: Vec<[f32; 3]> = reader.read_normals().map(|i| i.collect()).unwrap_or_else(|| vec![[0.0, 1.0, 0.0]; n]);
            let uv: Vec<[f32; 2]> = reader
                .read_tex_coords(0)
                .map(|t| t.into_f32().collect())
                .unwrap_or_else(|| vec![[0.0, 0.0]; n]);
            let tan: Vec<[f32; 4]> =
                reader.read_tangents().map(|i| i.collect()).unwrap_or_else(|| vec![[1.0, 0.0, 0.0, 1.0]; n]);
            let col: Vec<[f32; 4]> = reader
                .read_colors(0)
                .map(|c| c.into_rgba_f32().collect())
                .unwrap_or_else(|| vec![[1.0; 4]; n]);
            let idx: Vec<u32> = reader
                .read_indices()
                .map(|i| i.into_u32().collect())
                .unwrap_or_else(|| (0..n as u32).collect());
            let mut m = Mesh::new(PrimitiveTopology::TriangleList, RenderAssetUsages::default());
            m.insert_attribute(Mesh::ATTRIBUTE_POSITION, pos);
            m.insert_attribute(Mesh::ATTRIBUTE_NORMAL, nrm);
            m.insert_attribute(Mesh::ATTRIBUTE_UV_0, uv);
            m.insert_attribute(Mesh::ATTRIBUTE_TANGENT, tan);
            m.insert_attribute(Mesh::ATTRIBUTE_COLOR, VertexAttributeValues::Float32x4(col));
            m.insert_indices(Indices::U32(idx));
            let material = prim.material().name().unwrap_or_default().to_string();
            prims.push(Primitive { mesh: m, material });
        }
        out.push((name, prims));
    }
    Ok(out)
}
