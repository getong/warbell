//! Distant background islands — real mountain islands on the horizon, far out past the
//! playable island: Lofoten's granite peaks, Stromboli's smoking cone, Fogo's desert caldera, La
//! Gomera's forested ravines, Jan Mayen's glaciated Beerenberg.
//!
//! They are **real terrain**: `tools/terrain_isles/fetch_isles.py` bakes AWS Terrain Tiles
//! elevation (open data) + Sentinel-2 cloudless 2016 imagery (EOX, CC BY 4.0) into
//! `assets/isles/<name>_height.bin` (metric f32 grid) + `<name>_albedo.png`, and [`build`] turns
//! each into one textured height-field mesh at **near-real scale** (1 unit = 1 m): 9-16 km off the
//! castle, peaks ~0.9-2 km. Horizontal scale is shrunk a little per island (a 25 km archipelago
//! would wrap half the horizon) and height mildly exaggerated so they hold the skyline.
//!
//! - **`NoFrustumCulling`** — the camera's `far` (230) only feeds frustum culling; the projection
//!   is infinite reverse-Z, so geometry kilometres out still rasterises with good depth.
//! - **`fog_enabled: false`** — `DistanceFog` is solid by ~190 and would erase them. Instead
//!   [`drive_isle_haze`] pulls each island's material toward the live fog colour (albedo scaled
//!   down, fog colour added as un-exposed emissive) by an amount that grows with its distance, so
//!   time-of-day / biome mood tints them and farther ranges read paler (aerial perspective); the
//!   `atmospherics` post pass adds its height haze on top.
//! - Edges of each bake box fade below the sea, so a crop through land becomes a coast, not a wall.
//!
//! One draw per island, no shadows. Spawned from `worldmap::build`, tagged `BiomeEntity`.
//! `FOREST_NOISLES=1` drops them (map shots); `FOREST_ISLE_HAZE=<k>` scales the haze for tuning.

use bevy::asset::RenderAssetUsages;
use bevy::camera::visibility::NoFrustumCulling;
use bevy::light::{NotShadowCaster, NotShadowReceiver};
use bevy::mesh::{Indices, PrimitiveTopology};
use bevy::pbr::DistanceFog;
use bevy::prelude::*;

use crate::biome::BiomeEntity;
use crate::palette::lin;

/// Sea-surface Y (mirrors the private `worldmap::SEA_Y`).
const SEA_Y: f32 = -0.4;
/// How far the DEM's 0 m sits below the water, so the coast meets the sea instead of hovering on
/// a sliver of beach.
const SINK: f32 = 3.0;

pub struct DistantIslesPlugin;

impl Plugin for DistantIslesPlugin {
    fn build(&self, app: &mut App) {
        app.add_systems(Update, drive_isle_haze);
    }
}

/// Each island's material + its base haze (grows with distance).
#[derive(Resource, Default)]
struct IsleMaterials(Vec<(Handle<StandardMaterial>, f32)>);

/// One placed landmass. `angle` is the world bearing (`atan2(z, x)`) from the castle.
struct Isle {
    name: &'static str,
    angle: f32,
    dist: f32,
    /// Horizontal / vertical scale applied to the real terrain.
    hs: f32,
    vs: f32,
    yaw: f32,
    /// Ash plume over this island's summit.
    plume: bool,
}

/// The horizon: snow NW, granite ranges N, the desert volcano NE, Stromboli E, Gomera SW.
const ISLES: [Isle; 7] = [
    Isle { name: "beerenberg", angle: -2.35, dist: 14_000.0, hs: 0.55, vs: 0.65, yaw: 0.4, plume: false },
    Isle { name: "lofoten", angle: -1.75, dist: 12_500.0, hs: 0.50, vs: 0.62, yaw: 1.1, plume: false },
    Isle { name: "austvagoy", angle: -1.15, dist: 17_000.0, hs: 0.55, vs: 0.72, yaw: -0.5, plume: false },
    Isle { name: "fogo", angle: -0.50, dist: 16_000.0, hs: 0.45, vs: 0.55, yaw: 0.0, plume: false },
    Isle { name: "stromboli", angle: 0.38, dist: 10_000.0, hs: 1.00, vs: 1.10, yaw: 2.2, plume: true },
    Isle { name: "lofoten", angle: 1.45, dist: 14_000.0, hs: 0.50, vs: 0.60, yaw: -2.0, plume: false },
    Isle { name: "gomera", angle: 2.55, dist: 12_000.0, hs: 0.55, vs: 0.65, yaw: 2.9, plume: false },
];

// ── Noise ────────────────────────────────────────────────────────────────────────
fn hash2(x: i32, z: i32, seed: u32) -> f32 {
    let mut h = seed ^ (x as u32).wrapping_mul(0x8da6_b343) ^ (z as u32).wrapping_mul(0xd816_3841);
    h = (h ^ (h >> 15)).wrapping_mul(0x2c1b_3c6d);
    h = (h ^ (h >> 12)).wrapping_mul(0x297a_2d39);
    (h ^ (h >> 15)) as f32 / 4_294_967_296.0
}

/// Smooth value noise in [0,1].
fn vnoise(x: f32, z: f32, seed: u32) -> f32 {
    let (x0, z0) = (x.floor(), z.floor());
    let (fx, fz) = (x - x0, z - z0);
    let (sx, sz) = (fx * fx * fx * (fx * (fx * 6.0 - 15.0) + 10.0), fz * fz * fz * (fz * (fz * 6.0 - 15.0) + 10.0));
    let (ix, iz) = (x0 as i32, z0 as i32);
    let a = hash2(ix, iz, seed);
    let b = hash2(ix + 1, iz, seed);
    let c = hash2(ix, iz + 1, seed);
    let d = hash2(ix + 1, iz + 1, seed);
    let ab = a + (b - a) * sx;
    let cd = c + (d - c) * sx;
    ab + (cd - ab) * sz
}

#[allow(dead_code)]
fn fbm(x: f32, z: f32, seed: u32, oct: u32) -> f32 {
    let (mut amp, mut f, mut sum, mut norm) = (0.5, 1.0, 0.0, 0.0);
    for o in 0..oct {
        sum += vnoise(x * f, z * f, seed.wrapping_add(o * 977)) * amp;
        norm += amp;
        amp *= 0.5;
        f *= 2.03;
    }
    sum / norm
}

/// Ridged multifractal in ~[0,1]: sharp crests where the noise crosses its midline, each octave
/// weighted by the previous one so detail gathers on the ridges (the classic eroded-range look).
#[allow(dead_code)]
fn ridged(x: f32, z: f32, seed: u32, oct: u32) -> f32 {
    let (mut amp, mut f, mut sum, mut norm, mut w) = (0.5, 1.0, 0.0, 0.0, 1.0f32);
    for o in 0..oct {
        let n = 1.0 - (vnoise(x * f, z * f, seed.wrapping_add(o * 1471)) * 2.0 - 1.0).abs();
        let n = n * n * w;
        w = (n * 1.6).clamp(0.0, 1.0);
        sum += n * amp;
        norm += amp;
        amp *= 0.5;
        f *= 2.1;
    }
    sum / norm
}

fn smoothstep(e0: f32, e1: f32, x: f32) -> f32 {
    let t = ((x - e0) / (e1 - e0)).clamp(0.0, 1.0);
    t * t * (3.0 - 2.0 * t)
}

fn mix4(a: [f32; 4], b: [f32; 4], t: f32) -> [f32; 4] {
    let t = t.clamp(0.0, 1.0);
    [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t, 1.0]
}

// ── Mesh ─────────────────────────────────────────────────────────────────────────
/// Read a baked island: (grid, heights in metres north-row-first, width m, depth m).
fn read_isle(name: &str) -> Option<(usize, Vec<f32>, f32, f32)> {
    let meta = std::fs::read_to_string(crate::realforest::load::asset_path("isles/isles.json")).ok()?;
    // Tiny hand parse of `"name": { "width": W, "depth": D, "max": M, "grid": G }`.
    let block = &meta[meta.find(&format!("\"{name}\""))?..];
    let block = &block[..block.find('}')?];
    let num = |key: &str| -> Option<f32> {
        let at = block.find(&format!("\"{key}\""))? + key.len() + 2;
        let rest = block[at..].trim_start_matches([' ', ':']);
        let end = rest.find([',', '\n', '\r', '}']).unwrap_or(rest.len());
        rest[..end].trim().parse().ok()
    };
    let (w, d, g) = (num("width")?, num("depth")?, num("grid")? as usize);
    let bytes = std::fs::read(crate::realforest::load::asset_path(&format!("isles/{name}_height.bin"))).ok()?;
    if bytes.len() != g * g * 4 {
        return None;
    }
    let hs = bytes.chunks_exact(4).map(|b| f32::from_le_bytes([b[0], b[1], b[2], b[3]])).collect();
    Some((g, hs, w, d))
}

/// One island's height-field mesh in local space (x east, z south, UV = the albedo's pixel frame).
fn build_mesh(g: usize, raw: &[f32], width: f32, depth: f32, hs: f32, vs: f32) -> Mesh {
    let (w, d) = (width * hs, depth * hs);
    let mut hgt = vec![0.0f32; g * g];
    for j in 0..g {
        for i in 0..g {
            // Fade the bake box's rim below the sea so a crop through land reads as a coast.
            let (u, v) = (i as f32 / (g - 1) as f32, j as f32 / (g - 1) as f32);
            let f = smoothstep(0.0, 0.07, u.min(v).min(1.0 - u).min(1.0 - v));
            hgt[j * g + i] = raw[j * g + i].max(-60.0) * vs * f - (1.0 - f) * 40.0;
        }
    }
    let at = |i: usize, j: usize| hgt[j.min(g - 1) * g + i.min(g - 1)];
    let (sx, sz) = (w / (g - 1) as f32, d / (g - 1) as f32);
    let mut positions = Vec::with_capacity(g * g);
    let mut normals = Vec::with_capacity(g * g);
    let mut uvs = Vec::with_capacity(g * g);
    for j in 0..g {
        for i in 0..g {
            let dx = (at(i + 1, j) - at(i.saturating_sub(1), j)) / (2.0 * sx);
            let dz = (at(i, j + 1) - at(i, j.saturating_sub(1))) / (2.0 * sz);
            positions.push([i as f32 * sx - w * 0.5, SEA_Y - SINK + at(i, j), j as f32 * sz - d * 0.5]);
            normals.push(Vec3::new(-dx, 1.0, -dz).normalize().to_array());
            uvs.push([i as f32 / (g - 1) as f32, j as f32 / (g - 1) as f32]);
        }
    }
    let mut idx: Vec<u32> = Vec::with_capacity(g * g * 6);
    for j in 0..g - 1 {
        for i in 0..g - 1 {
            let hmax = at(i, j).max(at(i + 1, j)).max(at(i, j + 1)).max(at(i + 1, j + 1));
            if hmax < SINK * 0.6 {
                continue; // open sea
            }
            let a = (j * g + i) as u32;
            let (b, c) = (a + 1, a + g as u32);
            idx.extend_from_slice(&[a, c, b, b, c, c + 1]);
        }
    }
    let mut mesh = Mesh::new(PrimitiveTopology::TriangleList, RenderAssetUsages::RENDER_WORLD);
    mesh.insert_attribute(Mesh::ATTRIBUTE_POSITION, positions);
    mesh.insert_attribute(Mesh::ATTRIBUTE_NORMAL, normals);
    mesh.insert_attribute(Mesh::ATTRIBUTE_UV_0, uvs);
    mesh.insert_indices(Indices::U32(idx));
    mesh
}

/// A volcano's ash plume: a column of noise-lumped puffs rising out of the crater and bending
/// downwind, grey-brown at the root, paling to steam-white with height, shaded darker underneath.
/// One merged static mesh in a world-aligned frame rooted at the crater.
fn build_plume(seed: u32, wind: Vec3) -> Mesh {
    let mut positions: Vec<[f32; 3]> = Vec::new();
    let mut normals: Vec<[f32; 3]> = Vec::new();
    let mut colors: Vec<[f32; 4]> = Vec::new();
    let mut idx: Vec<u32> = Vec::new();
    let side = Vec3::Y.cross(wind).normalize_or_zero();
    const PUFFS: usize = 30;
    for k in 0..PUFFS {
        let f = k as f32 / (PUFFS - 1) as f32;
        let j = |o: u32| hash2(k as i32, o as i32, seed) - 0.5;
        // Rises fast near the vent, then levels off and shears downwind.
        let up = 300.0 * (1.0 - (1.0 - f).powf(2.0));
        let along = 720.0 * f.powf(1.6);
        let c = Vec3::Y * up + wind * along + side * j(1) * 60.0 * f + Vec3::Y * j(2) * 25.0;
        let rad = 16.0 + 46.0 * f + j(3) * 10.0;
        let ash = mix4(lin(0x9c958d), lin(0xf2f0ec), smoothstep(0.0, 0.40, f));
        let ico = Sphere::new(1.0).mesh().ico(2).expect("ico");
        let base = positions.len() as u32;
        let Some(bevy::mesh::VertexAttributeValues::Float32x3(ps)) = ico.attribute(Mesh::ATTRIBUTE_POSITION) else { continue };
        for v in ps {
            let d = Vec3::from_array(*v);
            let lump = 1.0 + 0.35 * (vnoise(d.x * 2.2 + k as f32 * 3.7, d.z * 2.2 + d.y * 1.7, seed ^ 0x77) - 0.5);
            let p = c + d * rad * lump * Vec3::new(1.0 + f, 0.9 - 0.35 * f, 1.0 + f * 0.6);
            positions.push(p.to_array());
            normals.push(d.to_array());
            // Self-shadow: undersides and the root darker.
            let shade = 0.62 + 0.38 * smoothstep(-0.7, 0.8, d.y);
            colors.push([ash[0] * shade, ash[1] * shade, ash[2] * shade, 1.0]);
        }
        if let Some(Indices::U32(is)) = ico.indices() {
            idx.extend(is.iter().map(|i| i + base));
        } else if let Some(Indices::U16(is)) = ico.indices() {
            idx.extend(is.iter().map(|&i| i as u32 + base));
        }
    }
    let mut mesh = Mesh::new(PrimitiveTopology::TriangleList, RenderAssetUsages::RENDER_WORLD);
    mesh.insert_attribute(Mesh::ATTRIBUTE_POSITION, positions);
    mesh.insert_attribute(Mesh::ATTRIBUTE_NORMAL, normals);
    mesh.insert_attribute(Mesh::ATTRIBUTE_COLOR, colors);
    mesh.insert_indices(Indices::U32(idx));
    mesh
}

// ── Spawn ────────────────────────────────────────────────────────────────────────
/// Spawn the horizon islands. Called once from `worldmap::build`.
pub fn build(
    commands: &mut Commands,
    meshes: &mut Assets<Mesh>,
    images: &mut Assets<Image>,
    std_mats: &mut Assets<StandardMaterial>,
) {
    if std::env::var("FOREST_NOISLES").is_ok() {
        return;
    }
    let mut mats = IsleMaterials::default();
    for isle in &ISLES {
        let key = isle.name;
        let Some((g, raw, w, d)) = read_isle(key) else {
            warn!("distant isle '{key}' missing from assets/isles — skipped");
            continue;
        };
        let tex = match crate::realforest::load::texture(&format!("isles/{key}_albedo.png"), true, None) {
            Ok(img) => images.add(img),
            Err(e) => {
                warn!("distant isle albedo: {e}");
                continue;
            }
        };
        let top = raw.iter().cloned().fold(0.0f32, f32::max) * isle.vs;
        let haze = (0.06 + isle.dist / 60_000.0).min(0.45);
        let mat = std_mats.add(StandardMaterial {
            base_color_texture: Some(tex),
            perceptual_roughness: 0.95,
            reflectance: 0.2,
            fog_enabled: false,
            ..default()
        });
        mats.0.push((mat.clone(), haze));
        let (sa, ca) = isle.angle.sin_cos();
        let centre = Vec3::new(ca * isle.dist, 0.0, sa * isle.dist);
        commands.spawn((
            Mesh3d(meshes.add(build_mesh(g, &raw, w, d, isle.hs, isle.vs))),
            MeshMaterial3d(mat),
            Transform::from_translation(centre).with_rotation(Quat::from_rotation_y(isle.yaw)),
            NoFrustumCulling,
            NotShadowCaster,
            NotShadowReceiver,
            BiomeEntity,
        ));
        if isle.plume {
            // Stromboli's crater sits near the bake's centre; the plume is vertex-coloured.
            let plume_mat = std_mats.add(StandardMaterial {
                base_color: Color::WHITE,
                perceptual_roughness: 1.0,
                fog_enabled: false,
                ..default()
            });
            mats.0.push((plume_mat.clone(), haze));
            let wind = Vec3::new(0.9, 0.0, -0.43).normalize();
            commands.spawn((
                Mesh3d(meshes.add(build_plume(7, wind))),
                MeshMaterial3d(plume_mat),
                Transform::from_translation(centre + Vec3::Y * (SEA_Y - SINK + top * 0.92))
                    .with_scale(Vec3::splat(2.5)),
                NoFrustumCulling,
                NotShadowCaster,
                NotShadowReceiver,
                BiomeEntity,
            ));
        }
    }
    commands.insert_resource(mats);
}

/// Aerial perspective for the horizon: pull each island's material toward the live fog colour —
/// albedo scaled by `1 - haze`, fog colour added as un-exposed emissive (the units the fog blend
/// itself uses) — so dawn, dusk, night and biome tints carry onto the far mountains.
fn drive_isle_haze(
    isles: Option<Res<IsleMaterials>>,
    fog: Query<&DistanceFog, With<Camera3d>>,
    mut mats: ResMut<Assets<StandardMaterial>>,
    mut last: Local<Option<LinearRgba>>,
) {
    let (Some(isles), Ok(fog)) = (isles, fog.single()) else { return };
    let k = std::env::var("FOREST_ISLE_HAZE").ok().and_then(|v| v.parse::<f32>().ok()).unwrap_or(1.0);
    let fc = fog.color.to_linear();
    let same = last.is_some_and(|l| (l.red - fc.red).abs() + (l.green - fc.green).abs() + (l.blue - fc.blue).abs() < 2e-3);
    if same && !isles.is_changed() {
        return;
    }
    *last = Some(fc);
    for (h, base) in &isles.0 {
        let haze = (base * k).clamp(0.0, 0.95);
        let Some(mut m) = mats.get_mut(h) else { continue };
        let a = 1.0 - haze;
        m.base_color = Color::linear_rgb(a, a, a);
        m.emissive = LinearRgba::rgb(fc.red * haze, fc.green * haze, fc.blue * haze);
    }
}
