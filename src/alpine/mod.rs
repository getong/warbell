//! **Alpine terrain** — the snow massif, the mountain walls and the forest → meadow → snow
//! transition, drawn with real PBR layers instead of flat vertex colour.
//!
//! Three parts, all reusing the `realforest` pipeline patterns:
//!
//! - **Ground layers** ([`patch_terrain`]): a 4-layer texture array (snow / alpine meadow / scree /
//!   rock, `tools/blender_forest/alpine.py` → `pack_forest_textures` → `forest_pbr/alpine_*.dds`)
//!   plus an RGBA8 mask baked once per map ([`bake_mask`]) are bound into every world terrain
//!   material. `assets/shaders/alpine.wgsl` splats them: slope- and height-driven snow cover with
//!   patchy edges, drifts at wall feet and sparkle, triplanar rock on cliff faces and steep
//!   slopes, talus scree at the wall feet, and the meadow under / around the snow line.
//! - **Mountain geometry** lives in `worldmap` (it needs the private tile grid) as two child
//!   modules: `terrain_relief.rs` (eroded, nav-safe relief on the mesa shelves) and
//!   `terrain_cliff.rs` (smooth-shaded, gullied cliff walls + contour-following lips).
//! - **Snowy kit scatter** ([`snowkit`]): the snow biome's trees / rocks / cover come from the
//!   Blender forest kit, with snow-dusted material twins.
//!
//! `FOREST_ALPINE=0` turns the ground layers + kit scatter off (A/B and perf isolation); the
//! geometry changes are always on (they are part of the map, like the mesa walls themselves).

use bevy::asset::RenderAssetUsages;
use bevy::prelude::*;
use bevy::render::render_resource::{Extent3d, ShaderType, TextureDimension, TextureFormat};

use crate::terrain::TerrainMaterial;

pub mod snowkit;

/// Uniform block of the alpine layers (`alpine.wgsl` `AlpineParams`, binding 111).
#[derive(Clone, Copy, ShaderType, Debug, Default)]
pub struct AlpineParams {
    /// x = 1 when the layers + mask are bound (0 = not yet, -1 = skipped); y = sparkle strength;
    /// z = snow-cover bias; w = reserved.
    pub on: Vec4,
    /// Mask world → UV: `xy` = world min corner, `zw` = 1 / extent (same contract as the forest
    /// mask's `pbr_region`).
    pub region: Vec4,
}

/// Layer order of the alpine arrays (`alpine.wgsl` indexes them 0..4; 4 = the rock range's pale
/// dolomite, Poly Haven marble_cliff_04).
const LAYERS: [&str; 5] = ["snow", "meadow", "scree", "rock", "dolomite"];

/// Alpine ground + snowy kit wanted? Read once (`FOREST_ALPINE=0` disables).
pub fn enabled() -> bool {
    static ON: std::sync::OnceLock<bool> = std::sync::OnceLock::new();
    *ON.get_or_init(|| std::env::var("FOREST_ALPINE").map(|v| v != "0").unwrap_or(true))
}

pub struct AlpinePlugin;

/// Keeps the `warbell::alpine` WGSL import module loaded (the terrain shader `#import`s it).
#[derive(Resource)]
#[allow(dead_code)]
struct AlpineShader(Handle<Shader>);

impl Plugin for AlpinePlugin {
    fn build(&self, app: &mut App) {
        snowkit::register(app);
        let shader = app.world().resource::<AssetServer>().load::<Shader>("shaders/alpine.wgsl");
        app.insert_resource(AlpineShader(shader));
        app.add_systems(Update, patch_terrain);
    }
}

/// 1×1×4 array bound before the alpine layers are (or when they never are). Process-cached with
/// MAIN_WORLD usage for the same re-preparable-handle reason as `terrain`'s placeholders.
pub fn layers_placeholder(images: &mut Assets<Image>) -> Handle<Image> {
    static CACHE: std::sync::Mutex<Option<Handle<Image>>> = std::sync::Mutex::new(None);
    let mut c = CACHE.lock().expect("alpine placeholder poisoned");
    c.get_or_insert_with(|| images.add(crate::realforest::load::dummy_array(5, [128, 128, 255, 255]))).clone()
}

pub fn mask_placeholder(images: &mut Assets<Image>) -> Handle<Image> {
    static CACHE: std::sync::Mutex<Option<Handle<Image>>> = std::sync::Mutex::new(None);
    let mut c = CACHE.lock().expect("alpine mask placeholder poisoned");
    c.get_or_insert_with(|| {
        images.add(Image::new(
            Extent3d { width: 1, height: 1, depth_or_array_layers: 1 },
            TextureDimension::D2,
            vec![0u8; 4],
            TextureFormat::Rgba8Unorm,
            RenderAssetUsages::default(),
        ))
    })
    .clone()
}

/// The loaded alpine arrays (albedo, normal, ormh), loaded once per process.
fn layers(images: &mut Assets<Image>) -> Option<[Handle<Image>; 3]> {
    static CACHE: std::sync::Mutex<Option<Option<[Handle<Image>; 3]>>> = std::sync::Mutex::new(None);
    let mut c = CACHE.lock().expect("alpine layers poisoned");
    c.get_or_insert_with(|| {
        let load = |map: &str, srgb: bool| {
            let pngs = LAYERS.map(|l| format!("forest_pbr/alpine_{l}_{map}.png"));
            crate::realforest::load::texture_array(
                &format!("forest_pbr/alpine_{map}.dds"),
                &pngs.each_ref().map(|s| s.as_str()),
                srgb,
            )
        };
        match (load("albedo", true), load("normal", false), load("ormh", false)) {
            (Ok(a), Ok(n), Ok(o)) => Some([images.add(a), images.add(n), images.add(o)]),
            (a, n, o) => {
                let e = [a.err(), n.err(), o.err()].into_iter().flatten().next().unwrap_or_default();
                warn!("alpine: terrain layers missing, keeping the procedural snow / rock — {e}");
                None
            }
        }
    })
    .clone()
}

/// Bind the alpine layers + mask into every world terrain material once (materials are minted
/// inside the world build and again on an in-process rebuild, so this watches for unpatched ones).
fn patch_terrain(
    mut mats: ResMut<Assets<TerrainMaterial>>,
    mut images: ResMut<Assets<Image>>,
    mut mask: Local<Option<(u8, Handle<Image>, Vec4)>>,
) {
    let todo: Vec<_> = mats.iter().filter(|(_, m)| m.extension.alpine.on.x == 0.0).map(|(id, _)| id).collect();
    if todo.is_empty() {
        return;
    }
    let layers = if enabled() { layers(&mut images) } else { None };
    let map = crate::worldmap::current_map_u8();
    for id in todo {
        let Some(mut m) = mats.get_mut(id) else { continue };
        // Ground without a road network = a single-biome viewer / ground test: leave it alone.
        let Some([alb, nrm, orm]) = layers.clone().filter(|_| m.extension.params.rut_region.z > 0.0) else {
            m.extension.alpine.on.x = -1.0;
            continue;
        };
        if mask.as_ref().is_none_or(|(id, _, _)| *id != map) {
            let t0 = std::time::Instant::now();
            let (h, r) = bake_mask(&mut images);
            info!("alpine: mask baked in {:.2}s", t0.elapsed().as_secs_f32());
            *mask = Some((map, h, r));
        }
        let (_, mask_h, region) = mask.clone().expect("alpine mask just baked");
        let ext = &mut m.extension;
        ext.alp_albedo = alb;
        ext.alp_normal = nrm;
        ext.alp_ormh = orm;
        ext.alp_mask = mask_h;
        ext.alpine = AlpineParams { on: Vec4::new(1.0, 1.0, 0.0, 0.0), region };
    }
}

fn smoothstep(e0: f32, e1: f32, x: f32) -> f32 {
    let t = ((x - e0) / (e1 - e0)).clamp(0.0, 1.0);
    t * t * (3.0 - 2.0 * t)
}

/// Target snow cover 0..1 at world `(x, z)` before the shader's patchy breakup: zero off the snow
/// biome; on it an altitude zonation like a real massif — a snow-free valley floor (alpine meadow;
/// its only snow is the drifts [`bake_mask`] adds in wall feet, hollows and shady north faces),
/// patchy snow from ~y 3, mostly covered by ~y 6.5 and full cover from ~y 9 up (the spruce belt
/// and everything above it). Height-driven (not class-driven) so the eroded shelf relief carries
/// more snow on its crowns than in its hollows. The kit scatter reads the same function to pick
/// frosted vs. green plants, so ground and props agree.
pub fn snow_cover(x: f32, z: f32) -> f32 {
    if crate::worldmap::tile_biome_world(x, z) != Some(crate::biome::Biome::Snow) {
        return 0.0;
    }
    let y = crate::worldmap::ground_at_world(x, z).unwrap_or(0.0);
    // (Was 0.34 + 0.66·smoothstep(0.6, 3.0): snowy right down to the valley floor.)
    SNOW_FLOOR + (1.0 - SNOW_FLOOR) * smoothstep(SNOW_LINE.0, SNOW_LINE.1, y)
}

/// Cover at which the shader paints (near-)solid snow whatever its breakup noise (its patch edge
/// wanders between ~0.37 and ~0.67): snow-themed sites need this under their WHOLE footprint, so
/// they stand on white ground instead of on the green valley meadow.
pub const SOLID_SNOW: f32 = 0.72;

/// Thinnest [`snow_cover`] over a footprint: the centre plus rings of 12 at `r` and `r`·0.55.
pub fn snow_footprint_min(x: f32, z: f32, r: f32) -> f32 {
    let mut c = snow_cover(x, z);
    for rr in [r, r * 0.55] {
        for k in 0..12 {
            let a = k as f32 * (std::f32::consts::TAU / 12.0);
            c = c.min(snow_cover(x + a.cos() * rr, z + a.sin() * rr));
        }
    }
    c
}

/// Snow cover left on the valley floor (a dusting the shader's breakup never turns into snow).
const SNOW_FLOOR: f32 = 0.03;
/// Altitude band of the snow line (ground y): bare below the low end, full cover past the high one.
const SNOW_LINE: (f32, f32) = (2.0, 8.0);

/// Tree line on the snow massif (base height band): trees thin out from the low end and none grow
/// past the high one, so the upper slopes and summits read as bare snow and rock, not a wooded hill.
const TREELINE: (f32, f32) = (11.0, 16.0);

/// Is ground height `y` at `(x, z)` above the (per-spot jittered, so its edge is no contour) tree line?
pub fn above_treeline(x: f32, z: f32, y: f32) -> bool {
    y > treeline_at(x, z)
}

/// The (per-spot jittered) tree-line height at `(x, z)`.
pub fn treeline_at(x: f32, z: f32) -> f32 {
    let (a, _) = crate::realforest::rolls(x, z);
    TREELINE.0 + (TREELINE.1 - TREELINE.0) * a
}

/// Real ground slope (rise / run, relief included) at `(x, z)`. The alpine scrub only grows on
/// walkable ground: the shader turns slopes past ~37° (≈0.75) into bare rock.
pub fn slope_at(x: f32, z: f32) -> f32 {
    let g = |x: f32, z: f32| crate::worldmap::ground_at_world(x, z).unwrap_or(0.0);
    let d = 0.7;
    let gx = (g(x + d, z) - g(x - d, z)) / (2.0 * d);
    let gz = (g(x, z + d) - g(x, z - d)) / (2.0 * d);
    (gx * gx + gz * gz).sqrt()
}

/// Is `(x, z)` a sun-facing (+z) or convex spot where the wind / sun keeps the snow thin — where
/// alpine grass tussocks poke through? (Crest: ≥0.15u above its 2u ring.)
pub fn thin_snow_spot(x: f32, z: f32) -> bool {
    let g = |x: f32, z: f32| crate::worldmap::ground_at_world(x, z).unwrap_or(0.0);
    let h = g(x, z);
    let ring = (g(x + 2.0, z) + g(x - 2.0, z) + g(x, z + 2.0) + g(x, z - 2.0)) * 0.25;
    let sunny = g(x, z + 0.7) - g(x, z - 0.7) < -0.25;
    sunny || h - ring > 0.15
}

/// Ground height of the TOP of the tree-line band (no tree of any kind past it).
pub const TREELINE_TOP: f32 = TREELINE.1;

/// RGBA8 alpine mask over the whole tile grid at 2 texels / unit:
/// - R = snow cover target ([`snow_cover`]) plus drifts — wall feet, hollows and shady (north-
///   facing, the sun always sits to the south / +z) slopes keep snow below the snow line —
///   feathered ~2u past the snow edge (frost);
/// - G = alpine meadow: the snow biome itself (under its patchy snow) and the grass / forest
///   margin within ~24u of it, fading out;
/// - B = mountain: the snow + rock biomes (gates talus scree and steep-slope rock);
/// - A = wall foot: 1 at the foot of a ≥2-class mesa / ridge wall, fading to 0 by ~5u
///   (snow drifts and talus pile up there).
fn bake_mask(images: &mut Assets<Image>) -> (Handle<Image>, Vec4) {
    use crate::biome::Biome;
    use crate::worldmap::{COLS, GX, GZ, ROWS};
    const RES: f32 = 2.0;
    let (x0, z0) = (-GX, -GZ);
    let (w, h) = ((COLS as f32 * RES) as usize, (ROWS as f32 * RES) as usize);
    let mut snow = vec![0.0f32; w * h];
    let mut is_snow = vec![false; w * h];
    let mut mount = vec![0.0f32; w * h];
    let mut hgt = vec![0.0f32; w * h];
    for j in 0..h {
        let wz = z0 + (j as f32 + 0.5) / RES;
        for i in 0..w {
            let wx = x0 + (i as f32 + 0.5) / RES;
            let k = j * w + i;
            let b = crate::worldmap::tile_biome_world(wx, wz);
            if b == Some(Biome::Snow) {
                is_snow[k] = true;
                snow[k] = snow_cover(wx, wz);
            }
            // (Everywhere, not just on the snow: the drift terms below look at the neighbours.)
            hgt[k] = crate::worldmap::ground_at_world(wx, wz).unwrap_or(0.0);
            // B: 1 = snow massif, 0.5 = the DOLOMITE rock range (the shader keys its pale limestone,
            // talus and sparse turf off the half value).
            mount[k] = match b {
                Some(Biome::Snow) => 1.0,
                Some(Biome::Rocky) => 0.5,
                _ => 0.0,
            };
        }
    }
    // Distance (texels) from the snow biome → the meadow band around it.
    let mut d_snow: Vec<f32> = is_snow.iter().map(|&s| if s { 0.0 } else { f32::INFINITY }).collect();
    chamfer(&mut d_snow, w, h);
    // Wall feet: tile centres that sit ≥0.8u BELOW a 4-neighbour (a ≥2-class split — the corner
    // clusters keep 1-class steps continuous, so only real walls jump that far).
    let mut d_foot = vec![f32::INFINITY; w * h];
    for iz in 0..ROWS {
        for ix in 0..COLS {
            let Some(c) = crate::worldmap::tile_centre_ground(ix, iz) else { continue };
            // The massif is one continuous surface: its steep slopes are not walls (they get
            // slope rock in the shader), and flagging them painted talus blotches all over it.
            if crate::worldmap::on_massif_corner(ix, iz) {
                continue;
            }
            let wall = [(1, 0), (-1, 0), (0, 1), (0, -1)]
                .iter()
                .any(|&(dx, dz)| crate::worldmap::tile_centre_ground(ix + dx, iz + dz).is_some_and(|n| n - c > 0.8));
            if wall {
                for (di, dj) in [(0, 0), (1, 0), (0, 1), (1, 1)] {
                    let (i, j) = ((ix as f32 * RES) as usize + di, (iz as f32 * RES) as usize + dj);
                    if i < w && j < h {
                        d_foot[j * w + i] = 0.0;
                    }
                }
            }
        }
    }
    chamfer(&mut d_foot, w, h);
    // Talus aprons of the rock range: its walls are continuous steep slopes (no class split), so
    // the wall-foot pass above skips them — flag every rock-range texel steeper than ~45° and let
    // the scree run ~6u out from them (the shader keeps rock ON the steep texels themselves).
    let mut d_crag = vec![f32::INFINITY; w * h];
    for j in 1..h - 1 {
        for i in 1..w - 1 {
            let k = j * w + i;
            if (mount[k] - 0.5).abs() > 0.01 {
                continue;
            }
            let gx = (hgt[k + 1] - hgt[k - 1]) * RES * 0.5;
            let gz = (hgt[k + w] - hgt[k - w]) * RES * 0.5;
            if gx.hypot(gz) > 1.0 {
                d_crag[k] = 0.0;
            }
        }
    }
    chamfer(&mut d_crag, w, h);
    // Drifts below the snow line: snow blown into wall feet, filling hollows (ground ≥ ~0.3u below
    // its ~5u neighbourhood) and lingering on the shady north faces.
    let mean_h = blur(&blur(&blur(&blur(&hgt, w, h, 6, true), w, h, 6, false), w, h, 6, true), w, h, 6, false);
    for j in 0..h {
        for i in 0..w {
            let k = j * w + i;
            if !is_snow[k] {
                continue;
            }
            let foot = 1.0 - smoothstep(0.0, 3.0 * RES, d_foot[k]);
            let hollow = smoothstep(0.3, 1.1, mean_h[k] - hgt[k]);
            // d(height)/dz > 0: the slope faces −z, away from the sun.
            let (jn, jp) = (j.saturating_sub(1), (j + 1).min(h - 1));
            let dhdz = (hgt[jp * w + i] - hgt[jn * w + i]) * RES / (jp - jn).max(1) as f32;
            let shade = smoothstep(0.25, 0.8, dhdz);
            // Lingering patches (old avalanche / cornice snow in the shade of the stands): a coarse
            // value noise, so a few white islands lie out on the valley meadow too.
            let (wx, wz) = (x0 + (i as f32 + 0.5) / RES, z0 + (j as f32 + 0.5) / RES);
            let patch = smoothstep(0.66, 0.8, value_noise(wx * 0.07, wz * 0.07));
            let drift = foot.max(hollow * 0.95).max(shade * 0.8).max(patch * 0.9);
            snow[k] += (1.0 - snow[k]) * drift;
        }
    }
    // (No baked snow pockets under the story sites any more: a white disc on the green meadow read
    // as a decal. Snow scenes are seated on real snow instead — `SOLID_SNOW` over their footprint.)
    let snow = blur(&blur(&snow, w, h, 3, true), w, h, 3, false);
    let mount = blur(&blur(&mount, w, h, 4, true), w, h, 4, false);
    let mut data = vec![0u8; w * h * 4];
    let px = |v: f32| (v.clamp(0.0, 1.0) * 255.0).round() as u8;
    for k in 0..w * h {
        let meadow = if is_snow[k] { 1.0 } else { 1.0 - smoothstep(10.0 * RES, 24.0 * RES, d_snow[k]) };
        let crag_foot = (1.0 - smoothstep(0.0, 6.0 * RES, d_crag[k])) * smoothstep(0.3, 0.45, mount[k]);
        let foot = (1.0 - smoothstep(0.0, 5.0 * RES, d_foot[k])).max(crag_foot);
        data[k * 4] = px(snow[k]);
        data[k * 4 + 1] = px(meadow);
        data[k * 4 + 2] = px(mount[k]);
        data[k * 4 + 3] = px(foot);
    }
    let mut img = Image::new(
        Extent3d { width: w as u32, height: h as u32, depth_or_array_layers: 1 },
        TextureDimension::D2,
        data,
        TextureFormat::Rgba8Unorm,
        RenderAssetUsages::default(),
    );
    img.sampler = bevy::image::ImageSampler::Descriptor(bevy::image::ImageSamplerDescriptor {
        mag_filter: bevy::image::ImageFilterMode::Linear,
        min_filter: bevy::image::ImageFilterMode::Linear,
        ..default()
    });
    (images.add(img), Vec4::new(x0, z0, 1.0 / COLS as f32, 1.0 / ROWS as f32))
}

/// Smooth value noise 0..1 on the integer lattice (hash = [`crate::realforest::rolls`]).
fn value_noise(x: f32, z: f32) -> f32 {
    let (xi, zi) = (x.floor(), z.floor());
    let (fx, fz) = (x - xi, z - zi);
    let (sx, sz) = (fx * fx * (3.0 - 2.0 * fx), fz * fz * (3.0 - 2.0 * fz));
    let h = |a: f32, b: f32| crate::realforest::rolls(a * 0.37 + 101.0, b * 0.37 - 57.0).0;
    let top = h(xi, zi) + (h(xi + 1.0, zi) - h(xi, zi)) * sx;
    let bot = h(xi, zi + 1.0) + (h(xi + 1.0, zi + 1.0) - h(xi, zi + 1.0)) * sx;
    top + (bot - top) * sz
}

/// Separable box blur, radius `r` texels.
fn blur(src: &[f32], w: usize, h: usize, r: i32, horiz: bool) -> Vec<f32> {
    let mut out = vec![0.0f32; w * h];
    for j in 0..h as i32 {
        for i in 0..w as i32 {
            let mut s = 0.0;
            for d in -r..=r {
                let (x, y) = if horiz { ((i + d).clamp(0, w as i32 - 1), j) } else { (i, (j + d).clamp(0, h as i32 - 1)) };
                s += src[y as usize * w + x as usize];
            }
            out[j as usize * w + i as usize] = s / (2 * r + 1) as f32;
        }
    }
    out
}

/// Two-pass 8-neighbour chamfer distance transform (≈ Euclidean, texels); `d` holds 0 at the
/// sources and +∞ elsewhere on entry.
pub(crate) fn chamfer(d: &mut [f32], w: usize, h: usize) {
    const DIAG: f32 = std::f32::consts::SQRT_2;
    for z in 0..h {
        for x in 0..w {
            let mut v = d[z * w + x];
            if x > 0 { v = v.min(d[z * w + x - 1] + 1.0); }
            if z > 0 { v = v.min(d[(z - 1) * w + x] + 1.0); }
            if x > 0 && z > 0 { v = v.min(d[(z - 1) * w + x - 1] + DIAG); }
            if x + 1 < w && z > 0 { v = v.min(d[(z - 1) * w + x + 1] + DIAG); }
            d[z * w + x] = v;
        }
    }
    for z in (0..h).rev() {
        for x in (0..w).rev() {
            let mut v = d[z * w + x];
            if x + 1 < w { v = v.min(d[z * w + x + 1] + 1.0); }
            if z + 1 < h { v = v.min(d[(z + 1) * w + x] + 1.0); }
            if x + 1 < w && z + 1 < h { v = v.min(d[(z + 1) * w + x + 1] + DIAG); }
            if x > 0 && z + 1 < h { v = v.min(d[(z + 1) * w + x - 1] + DIAG); }
            d[z * w + x] = v;
        }
    }
}
