//! Pack the Blender forest kit's PNG maps (`assets/forest_pbr/*.png`, written by
//! `tools/blender_forest/`) into GPU-ready BC7 DDS files with full mip chains:
//!
//!     cargo run --release --example pack_forest_textures
//!
//! - every `<set>_{albedo,normal,ormh}.png` → `<set>_<map>.dds` (albedo = sRGB BC7)
//! - foliage-card albedo (`canopy`, `undergrowth`) keeps its alpha-test COVERAGE in every mip, so
//!   distant crowns / grass don't thin out (see `realforest::load::mip_chain`)
//! - the three ground layers become ONE 3-layer array per map (`ground_<map>.dds`) for the terrain
//!   shader's texture arrays
//!
//! ~4x smaller than RGBA8 on disk and in VRAM, and the game no longer builds mips at startup.

use std::fs::File;
use std::path::{Path, PathBuf};

use ddsfile::{AlphaMode, D3D10ResourceDimension, Dds, DxgiFormat, NewDxgiParams};
use intel_tex_2::{bc7, RgbaSurface};

const DIR: &str = "assets/forest_pbr";
const CARD_CUTOFF: f32 = 0.42;
const CARD_SETS: [&str; 3] = ["canopy", "undergrowth", "swamp_cards"];
const GROUND: [&str; 3] = ["litter", "moss", "path"];
const STRUCT: [&str; 3] = ["wood", "stone", "cloth"];
/// Creature surface detail layers, in `creature::Surf` code order.
const CREATURE: [&str; 7] = ["skin", "fur", "leather", "wood", "metal", "cloth", "bone"];
/// Alpine terrain splat layers, in `alpine.wgsl` layer order (`tools/blender_forest/alpine.py`).
const ALPINE: [&str; 5] = ["snow", "meadow", "scree", "rock", "dolomite"];
const MAPS: [&str; 3] = ["albedo", "normal", "ormh"];

fn srgb_to_lin(c: f32) -> f32 {
    if c <= 0.04045 { c / 12.92 } else { ((c + 0.055) / 1.055).powf(2.4) }
}
fn lin_to_srgb(c: f32) -> f32 {
    if c <= 0.003_130_8 { c * 12.92 } else { 1.055 * c.powf(1.0 / 2.4) - 0.055 }
}

fn coverage(px: &[u8], cutoff: f32, scale: f32) -> f32 {
    let pass = px.chunks_exact(4).filter(|p| p[3] as f32 / 255.0 * scale >= cutoff).count();
    pass as f32 / (px.len() / 4).max(1) as f32
}

/// Box-filtered mips (gamma-correct for sRGB), alpha-coverage preserving when `cutoff` is set.
fn mips(base: Vec<u8>, w: u32, h: u32, srgb: bool, cutoff: Option<f32>) -> Vec<(Vec<u8>, u32, u32)> {
    let lut: Vec<f32> = (0..256).map(|i| if srgb { srgb_to_lin(i as f32 / 255.0) } else { i as f32 / 255.0 }).collect();
    let target = cutoff.map(|c| coverage(&base, c, 1.0));
    let mut out = vec![(base, w, h)];
    loop {
        let (prev, pw, ph) = out.last().unwrap();
        let (pw, ph) = (*pw, *ph);
        if pw == 1 && ph == 1 {
            break;
        }
        let (nw, nh) = ((pw / 2).max(1), (ph / 2).max(1));
        let mut next = vec![0u8; (nw * nh * 4) as usize];
        for y in 0..nh {
            for x in 0..nw {
                let mut acc = [0f32; 4];
                for dy in 0..2 {
                    for dx in 0..2 {
                        let sx = (x * 2 + dx).min(pw - 1);
                        let sy = (y * 2 + dy).min(ph - 1);
                        let i = ((sy * pw + sx) * 4) as usize;
                        for c in 0..4 {
                            acc[c] += if c < 3 { lut[prev[i + c] as usize] } else { prev[i + c] as f32 / 255.0 };
                        }
                    }
                }
                let o = ((y * nw + x) * 4) as usize;
                for c in 0..4 {
                    let v = acc[c] * 0.25;
                    let e = if srgb && c < 3 { lin_to_srgb(v) } else { v };
                    next[o + c] = (e.clamp(0.0, 1.0) * 255.0).round() as u8;
                }
            }
        }
        if let (Some(cut), Some(t)) = (cutoff, target) {
            let (mut lo, mut hi) = (0.5f32, 4.0f32);
            for _ in 0..12 {
                let mid = (lo + hi) * 0.5;
                if coverage(&next, cut, mid) < t { lo = mid } else { hi = mid }
            }
            for p in next.chunks_exact_mut(4) {
                p[3] = (p[3] as f32 * hi).min(255.0).round() as u8;
            }
        }
        out.push((next, nw, nh));
    }
    out
}

/// BC7-encode one level (padded up to whole 4x4 blocks by edge clamping).
fn bc7_level(px: &[u8], w: u32, h: u32, alpha: bool) -> Vec<u8> {
    let (bw, bh) = (w.div_ceil(4) * 4, h.div_ceil(4) * 4);
    let mut padded = vec![0u8; (bw * bh * 4) as usize];
    for y in 0..bh {
        for x in 0..bw {
            let s = ((y.min(h - 1) * w + x.min(w - 1)) * 4) as usize;
            let d = ((y * bw + x) * 4) as usize;
            padded[d..d + 4].copy_from_slice(&px[s..s + 4]);
        }
    }
    let surface = RgbaSurface { width: bw, height: bh, stride: bw * 4, data: &padded };
    let settings = if alpha { bc7::alpha_basic_settings() } else { bc7::opaque_basic_settings() };
    bc7::compress_blocks(&settings, &surface)
}

fn load(path: &Path) -> (Vec<u8>, u32, u32) {
    let img = image::open(path).unwrap_or_else(|e| panic!("{}: {e}", path.display())).to_rgba8();
    let (w, h) = img.dimensions();
    (img.into_raw(), w, h)
}

/// One array layer to write: a fresh mip chain to BC7-encode, or a layer's already-encoded bytes
/// (all mips) lifted verbatim from the previous `.dds` (no second compression pass).
enum Layer {
    Px(Vec<(Vec<u8>, u32, u32)>),
    Raw(Vec<u8>),
}

fn write_dds(out: &Path, layers: Vec<Layer>, srgb: bool, alpha: bool) {
    let Some(Layer::Px(first)) = layers.iter().find(|l| matches!(l, Layer::Px(_))) else {
        panic!("{}: no fresh layer to size the array from", out.display());
    };
    let (w, h) = (first[0].1, first[0].2);
    let levels = first.len() as u32;
    let mut dds = Dds::new_dxgi(NewDxgiParams {
        height: h,
        width: w,
        depth: None,
        format: if srgb { DxgiFormat::BC7_UNorm_sRGB } else { DxgiFormat::BC7_UNorm },
        mipmap_levels: Some(levels),
        array_layers: Some(layers.len() as u32),
        caps2: None,
        is_cubemap: false,
        resource_dimension: D3D10ResourceDimension::Texture2D,
        alpha_mode: AlphaMode::Straight,
    })
    .expect("dds header");
    let mut data = Vec::new();
    for layer in &layers {
        match layer {
            Layer::Px(chain) => {
                for (px, lw, lh) in chain {
                    data.extend(bc7_level(px, *lw, *lh, alpha));
                }
            }
            Layer::Raw(bytes) => data.extend_from_slice(bytes),
        }
    }
    dds.data = data;
    dds.write(&mut File::create(out).expect("create dds")).expect("write dds");
    println!("{}  {}x{} x{} layers, {} mips", out.display(), w, h, layers.len(), levels);
}

fn main() {
    let dir = PathBuf::from(DIR);
    // `PACK_ONLY=creature` (or `ground` / `struct`) re-packs just that array set and skips every
    // other file — for regenerating one set when the other PNG intermediates aren't on disk.
    let only = std::env::var("PACK_ONLY").ok();
    // Ground + structure re-skin: three layers per map → one array file each.
    for (prefix, names) in [("ground", &GROUND[..]), ("struct", &STRUCT[..]), ("creature", &CREATURE[..]), ("alpine", &ALPINE[..])] {
        if only.as_deref().is_some_and(|o| o != prefix) {
            continue;
        }
        // Layer PNGs come from `<PREFIX>_SRC` when set (e.g. `ALPINE_SRC=<scratch dir>` for
        // intermediates that shouldn't land in the repo), else from `assets/forest_pbr`.
        let src = std::env::var(format!("{}_SRC", prefix.to_uppercase())).map(PathBuf::from).unwrap_or(dir.clone());
        let png = |l: &str, m: &str| src.join(format!("{prefix}_{l}_{m}.png"));
        let fresh = |l: &str| MAPS.iter().all(|m| png(l, m).exists());
        // A group with no fresh layer (only another material script was re-run) keeps its packed
        // array. A PARTLY fresh group re-packs those layers and lifts the others' encoded bytes
        // verbatim from the existing array (e.g. new scans for three alpine layers while the
        // fourth's Blender intermediates aren't on disk).
        if !names.iter().any(|l| fresh(l)) {
            println!("{prefix}: skipped (no layer PNGs in {})", src.display());
            continue;
        }
        for map in MAPS {
            let srgb = map == "albedo";
            let out = dir.join(format!("{prefix}_{map}.dds"));
            let old = names.iter().any(|l| !fresh(l)).then(|| {
                Dds::read(File::open(&out).unwrap_or_else(|e| panic!("{}: {e}", out.display()))).expect("read dds")
            });
            let layers = names
                .iter()
                .enumerate()
                .map(|(i, l)| {
                    if fresh(l) {
                        let (px, w, h) = load(&png(l, map));
                        Layer::Px(mips(px, w, h, srgb, None))
                    } else {
                        println!("  {prefix}_{l}_{map}: kept from {}", out.display());
                        Layer::Raw(old.as_ref().unwrap().get_data(i as u32).expect("old dds layer").to_vec())
                    }
                })
                .collect();
            write_dds(&out, layers, srgb, map == "ormh");
        }
    }
    if only.is_some() {
        return;
    }
    // Everything else: one file per PNG.
    let mut pngs: Vec<PathBuf> = std::fs::read_dir(&dir)
        .expect("forest_pbr dir")
        .filter_map(|e| e.ok().map(|e| e.path()))
        .filter(|p| p.extension().is_some_and(|x| x == "png"))
        .filter(|p| {
            let n = p.file_name().unwrap().to_string_lossy().to_string();
            !["ground_", "struct_", "creature_", "alpine_"].iter().any(|p| n.starts_with(p))
        })
        .collect();
    pngs.sort();
    for png in pngs {
        let stem = png.file_stem().unwrap().to_string_lossy().to_string();
        let srgb = stem.ends_with("_albedo");
        let card = srgb && CARD_SETS.iter().any(|s| stem == format!("{s}_albedo"));
        let alpha = card || stem.ends_with("_ormh");
        let (px, w, h) = load(&png);
        let chain = mips(px, w, h, srgb, card.then_some(CARD_CUTOFF));
        write_dds(&png.with_extension("dds"), vec![Layer::Px(chain)], srgb, alpha);
    }
}
