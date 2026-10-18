//! **Far cover** — the undergrowth past its draw range, baked into the ground. Grass, ferns,
//! flowers, litter and scrub are real cards only out to ~46–58u (`COVER_FAR` / `LUSH_FAR`, ×
//! render distance); beyond that the terrain alone used to show — the "bald" far meadows and forest
//! floors. Every cover piece that is placed ([`record`], called from `Chunks::push_snowy`) is also
//! splatted into an island-wide grid as *what it would look like from afar*: its mean card colour
//! (alpha-tested texels of the model's own atlas, × vertex colour) weighted by the visual area of
//! its cards. Once the world is built ([`bake`]) the grid becomes an RGBA8 texture (rgb = mean
//! cover colour, a = coverage) on the terrain material, and `terrain.wesl` blends the ground toward
//! it exactly where the cards thin out — so far ground shows the colour, patchiness and density of
//! the plants that are really there, at the cost of one texture tap.
//!
//! `FOREST_FARCOVER=0` turns it off (A/B); `FOREST_FARCOVER=<k>` scales the blend strength.

use std::sync::Mutex;

use bevy::asset::RenderAssetUsages;
use bevy::prelude::*;
use bevy::render::render_resource::{Extent3d, TextureDimension, TextureFormat};

use super::{Tier, MATERIALS};

/// Texels per world unit of the baked cover map (whole tile grid).
const RES: f32 = 1.0;
/// Alpha-test threshold of the cards (`CARD_CUTOFF`).
const CUTOFF: u8 = (0.42 * 255.0) as u8;
/// Visual area (m²) per texel that reads as "fully covered" from afar, after the exp falloff.
const DENSITY_K: f32 = 4.0;

/// What one model looks like from afar: linear mean colour + visual card area (m² at scale 1).
#[derive(Clone, Copy, Debug)]
pub struct Swatch {
    pub rgb: Vec3,
    pub area: f32,
}

/// Running splat sums over the grid: Σ rgb·w and Σ w per texel.
struct Accum {
    w: usize,
    h: usize,
    x0: f32,
    z0: f32,
    rgb: Vec<Vec3>,
    wsum: Vec<f32>,
}

static ACCUM: Mutex<Option<Accum>> = Mutex::new(None);

pub fn enabled() -> bool {
    strength() > 0.0
}

fn strength() -> f32 {
    static V: std::sync::OnceLock<f32> = std::sync::OnceLock::new();
    *V.get_or_init(|| match std::env::var("FOREST_FARCOVER") {
        Ok(v) if v == "0" => 0.0,
        Ok(v) => v.parse().unwrap_or(1.0),
        Err(_) => 1.0,
    })
}

/// Forget the previous world's cover (top of the forest scatter / an in-process rebuild).
pub fn reset() {
    use crate::worldmap::{COLS, GX, GZ, ROWS};
    let (w, h) = ((COLS as f32 * RES) as usize, (ROWS as f32 * RES) as usize);
    *ACCUM.lock().expect("far cover poisoned") =
        Some(Accum { w, h, x0: -GX, z0: -GZ, rgb: vec![Vec3::ZERO; w * h], wsum: vec![0.0; w * h] });
}

/// Splat one placed cover piece (bilinear, so sub-texel positions don't alias into stripes).
pub fn record(swatch: Option<Swatch>, world: Vec3, scale: f32, tier: Tier) {
    let Some(s) = swatch else { return };
    if !enabled() {
        return;
    }
    // Props (rocks, logs, bushes) stay real geometry to 75u and are mostly seen as objects; they
    // still darken / tint the ground they stand on, but less than a carpet of blades.
    let tier_k = if matches!(tier, Tier::Props | Tier::PropsFar) { 0.5 } else { 1.0 };
    let wgt = s.area * scale * scale * tier_k;
    if wgt <= 0.0 {
        return;
    }
    let mut g = ACCUM.lock().expect("far cover poisoned");
    let Some(a) = g.as_mut() else { return };
    let fx = (world.x - a.x0) * RES - 0.5;
    let fz = (world.z - a.z0) * RES - 0.5;
    let (ix, iz) = (fx.floor() as i64, fz.floor() as i64);
    let (tx, tz) = (fx - ix as f32, fz - iz as f32);
    for (dx, dz, k) in [(0, 0, (1.0 - tx) * (1.0 - tz)), (1, 0, tx * (1.0 - tz)), (0, 1, (1.0 - tx) * tz), (1, 1, tx * tz)] {
        let (x, z) = (ix + dx, iz + dz);
        if x < 0 || z < 0 || x >= a.w as i64 || z >= a.h as i64 {
            continue;
        }
        let i = z as usize * a.w + x as usize;
        a.rgb[i] += s.rgb * (wgt * k);
        a.wsum[i] += wgt * k;
    }
}

/// What `model` looks like from afar, computed once per model on first use from the kit's own
/// atlases (CPU decode of the source PNGs, cached per material). `None` = no PNG / no opaque texel.
pub(super) fn swatch_for(kit: &super::Kit, model: usize) -> Option<Swatch> {
    *kit.cover[model].get_or_init(|| {
        static TEX: Mutex<Vec<Option<std::sync::Arc<Option<super::load::Rgba>>>>> = Mutex::new(Vec::new());
        let lut: [f32; 256] = std::array::from_fn(|i| srgb_to_lin(i as f32 / 255.0));
        let (mut rgb, mut area) = (Vec3::ZERO, 0.0f32);
        for part in &kit.models[model].parts {
            let (_, set, card) = MATERIALS[part.mat];
            if set.is_empty() {
                continue;
            }
            let t = {
                let mut cache = TEX.lock().expect("far cover tex poisoned");
                if cache.len() < MATERIALS.len() {
                    cache.resize(MATERIALS.len(), None);
                }
                cache[part.mat]
                    .get_or_insert_with(|| std::sync::Arc::new(super::load::read_png(&format!("forest_pbr/{set}_albedo.png")).ok()))
                    .clone()
            };
            let Some(t) = t.as_ref() else { continue };
            if let Some((c, a)) = part_swatch(&part.mesh, t, card, &lut) {
                rgb += c * a;
                area += a;
            }
        }
        (area > 1e-4).then(|| Swatch { rgb: rgb / area, area })
    })
}

/// (area-weighted mean linear colour, visual area) of one mesh part over its texture.
fn part_swatch(mesh: &Mesh, t: &super::load::Rgba, card: bool, lut: &[f32]) -> Option<(Vec3, f32)> {
    use bevy::mesh::{Indices, VertexAttributeValues};
    let Some(VertexAttributeValues::Float32x3(pos)) = mesh.attribute(Mesh::ATTRIBUTE_POSITION) else { return None };
    let Some(VertexAttributeValues::Float32x2(uv)) = mesh.attribute(Mesh::ATTRIBUTE_UV_0) else { return None };
    let col = match mesh.attribute(Mesh::ATTRIBUTE_COLOR) {
        Some(VertexAttributeValues::Float32x4(c)) => Some(c),
        _ => None,
    };
    let idx: Vec<usize> = match mesh.indices() {
        Some(Indices::U32(v)) => v.iter().map(|&i| i as usize).collect(),
        Some(Indices::U16(v)) => v.iter().map(|&i| i as usize).collect(),
        None => (0..pos.len()).collect(),
    };
    let sample = |u: f32, v: f32| -> [u8; 4] {
        let x = ((u.rem_euclid(1.0)) * t.w as f32) as u32 % t.w;
        let y = ((v.rem_euclid(1.0)) * t.h as f32) as u32 % t.h;
        let o = ((y * t.w + x) * 4) as usize;
        [t.px[o], t.px[o + 1], t.px[o + 2], t.px[o + 3]]
    };
    let (mut rgb, mut area) = (Vec3::ZERO, 0.0f32);
    // Barycentric sample points per triangle: the centroid + three toward the corners.
    const BARY: [[f32; 3]; 4] = [[1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0], [0.6, 0.2, 0.2], [0.2, 0.6, 0.2], [0.2, 0.2, 0.6]];
    for tri in idx.chunks_exact(3) {
        let (a, b, c) = (Vec3::from(pos[tri[0]]), Vec3::from(pos[tri[1]]), Vec3::from(pos[tri[2]]));
        let cross = (b - a).cross(c - a);
        // Cards: their full face, seen from the side at a distance; solids: their footprint.
        let tri_area = if card { cross.length() * 0.5 } else { cross.y.abs() * 0.5 };
        if tri_area <= 0.0 {
            continue;
        }
        let vcol = |k: usize| col.map_or(Vec3::ONE, |c| Vec3::new(c[tri[k]][0], c[tri[k]][1], c[tri[k]][2]));
        let (mut sum, mut pass) = (Vec3::ZERO, 0u32);
        for w in BARY {
            let u = uv[tri[0]][0] * w[0] + uv[tri[1]][0] * w[1] + uv[tri[2]][0] * w[2];
            let v = uv[tri[0]][1] * w[0] + uv[tri[1]][1] * w[1] + uv[tri[2]][1] * w[2];
            let px = sample(u, v);
            if card && px[3] < CUTOFF {
                continue;
            }
            let vc = vcol(0) * w[0] + vcol(1) * w[1] + vcol(2) * w[2];
            sum += Vec3::new(lut[px[0] as usize], lut[px[1] as usize], lut[px[2] as usize]) * vc;
            pass += 1;
        }
        if pass == 0 {
            continue;
        }
        let frac = pass as f32 / BARY.len() as f32;
        // A double-sided card is seen edge-on as often as face-on: about half its face reads.
        let vis = tri_area * frac * if card { 0.5 } else { 1.0 };
        rgb += sum / pass as f32 * vis;
        area += vis;
    }
    (area > 0.0).then(|| (rgb / area, area))
}

/// Turn the splat sums into the RGBA8 sRGB cover map (rgb = mean colour, a = coverage), softly
/// blurred so single tufts don't print as pixels. Returns `None` when nothing was recorded.
pub fn bake(images: &mut Assets<Image>) -> Option<Handle<Image>> {
    let g = ACCUM.lock().expect("far cover poisoned");
    let a = g.as_ref()?;
    let (w, h) = (a.w, a.h);
    // Premultiplied (colour × coverage, coverage) so the blur doesn't drag bare ground's black in.
    let mut pm: Vec<Vec4> = (0..w * h)
        .map(|i| {
            let ws = a.wsum[i];
            if ws <= 0.0 {
                return Vec4::ZERO;
            }
            let cov = 1.0 - (-ws * DENSITY_K / (RES * RES).max(1e-3) * 0.35).exp();
            (a.rgb[i] / ws * cov).extend(cov)
        })
        .collect();
    let covered = pm.iter().filter(|v| v.w > 0.1).count();
    if covered == 0 {
        return None;
    }
    let mean_cov = pm.iter().map(|v| v.w).sum::<f32>() / covered.max(1) as f32;
    info!("far cover: {covered} of {} texels covered (mean coverage {mean_cov:.2} where covered)", w * h);
    // Two passes of a separable [1 2 1] blur.
    for _ in 0..2 {
        let mut tmp = pm.clone();
        for z in 0..h {
            for x in 0..w {
                let l = pm[z * w + x.saturating_sub(1)];
                let r = pm[z * w + (x + 1).min(w - 1)];
                tmp[z * w + x] = (l + pm[z * w + x] * 2.0 + r) * 0.25;
            }
        }
        for z in 0..h {
            for x in 0..w {
                let u = tmp[z.saturating_sub(1) * w + x];
                let d = tmp[(z + 1).min(h - 1) * w + x];
                pm[z * w + x] = (u + tmp[z * w + x] * 2.0 + d) * 0.25;
            }
        }
    }
    let mut px = Vec::with_capacity(w * h * 4);
    for v in &pm {
        let c = if v.w > 1e-4 { v.truncate() / v.w } else { Vec3::ZERO };
        for ch in [c.x, c.y, c.z] {
            px.push((lin_to_srgb(ch.clamp(0.0, 1.0)) * 255.0).round() as u8);
        }
        px.push((v.w.clamp(0.0, 1.0) * 255.0).round() as u8);
    }
    // `FOREST_FARCOVER_DUMP=<file.png>`: the map as seen from above (colour × coverage over black).
    if let Ok(path) = std::env::var("FOREST_FARCOVER_DUMP") {
        let rgb: Vec<u8> = px.chunks_exact(4).flat_map(|p| {
            let a = p[3] as f32 / 255.0;
            [p[0], p[1], p[2]].map(|c| (c as f32 * a) as u8)
        }).collect();
        if let Some(im) = image::RgbImage::from_raw(w as u32, h as u32, rgb) {
            let _ = im.save(&path);
            info!("far cover: dumped {path}");
        }
    }
    let img = Image::new(
        Extent3d { width: w as u32, height: h as u32, depth_or_array_layers: 1 },
        TextureDimension::D2,
        px,
        TextureFormat::Rgba8UnormSrgb,
        RenderAssetUsages::RENDER_WORLD,
    );
    Some(images.add(img))
}

/// Blend strength for the shader (`FOREST_FARCOVER=<k>`).
pub fn shader_strength() -> f32 {
    strength()
}

fn srgb_to_lin(c: f32) -> f32 {
    if c <= 0.04045 { c / 12.92 } else { ((c + 0.055) / 1.055).powf(2.4) }
}

fn lin_to_srgb(c: f32) -> f32 {
    if c <= 0.003_130_8 { c * 12.92 } else { 1.055 * c.powf(1.0 / 2.4) - 0.055 }
}
