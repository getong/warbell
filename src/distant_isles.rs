//! Distant background islands — big mountainous landmasses on the horizon, out past the playable
//! island: a snow-capped alpine range, a volcano, a desert mesa, forested hills.
//!
//! They are built at **true scale** (peaks 200–480 units tall, 250–600 units across, 1 100–2 300
//! units off the castle) instead of as small props squeezed inside the fog wall, so they hold
//! the right size and parallax from anywhere on the island. Three things make that work:
//!
//! - **`NoFrustumCulling`** — the camera's `far` (230) only feeds frustum culling; the projection
//!   itself is infinite reverse-Z, so geometry far past it still rasterises with good depth.
//! - **`fog_enabled: false`** — `DistanceFog` goes solid by ~190 and would erase them. Instead
//!   [`drive_isle_haze`] blends the shared material toward the live fog colour (base colour
//!   scaled down + fog colour as un-exposed emissive), so the time-of-day / biome mood still
//!   tints them; the `atmospherics` post pass layers its height haze on top (denser low down,
//!   so the peaks stand out of a hazy foot — real aerial perspective).
//! - **One-sided modelling** — the camera never leaves the main island, so each landmass only
//!   models the side facing the castle; the far back slope is simply not emitted.
//!
//! Heights come from a ridged-fractal height field per kind (alpine ridge / volcano cone with a
//! crater and radial gullies / stratified mesa / rolling hills), coloured in vertex colours by
//! height + slope (beach → grass → forest → rock → snow), smooth-shaded. One shared material, one
//! draw per island, no shadows. Spawned from `worldmap::build` and tagged `BiomeEntity` so the
//! biome-swap rebuild despawns + recreates them. `FOREST_NOISLES=1` drops them (map shots);
//! `FOREST_ISLE_HAZE=<0..1>` overrides the material haze for tuning.

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
/// Grid vertices per side of one island's height field.
const GRID: usize = 168;
/// Default haze the material carries toward the fog colour (the post pass adds its own on top).
const HAZE: f32 = 0.12;

pub struct DistantIslesPlugin;

impl Plugin for DistantIslesPlugin {
    fn build(&self, app: &mut App) {
        app.add_systems(Update, drive_isle_haze);
    }
}

/// The shared island material, tagged so [`drive_isle_haze`] can find it.
#[derive(Resource)]
struct IsleMaterial(Handle<StandardMaterial>);

#[derive(Clone, Copy, PartialEq)]
enum Kind {
    /// Long snow-capped ridge with sharp ridged peaks.
    Alpine,
    /// Single cone with a crater, radial gullies, dark basalt and ash.
    Volcano,
    /// Flat-topped stratified desert rock, cliffs banded in ochre/red.
    Mesa,
    /// Rolling forested hills, a rocky crown.
    Hills,
}

/// One authored landmass. `angle` is the world bearing (`atan2(z, x)`) from the castle.
struct Isle {
    kind: Kind,
    angle: f32,
    dist: f32,
    /// Half-extents along the island's long (tangent) / short (radial) axes.
    rx: f32,
    rz: f32,
    peak: f32,
    seed: u32,
}

/// The horizon, authored for art direction rather than rolled: each landmass echoes the biome on
/// the main island's matching shore (snow NW, desert NE, rock E, forest SW, Blight S).
const ISLES: [Isle; 8] = [
    // NW — the big alpine range behind the snowfields, with a taller, hazier range behind it.
    Isle { kind: Kind::Alpine, angle: -2.30, dist: 1350.0, rx: 560.0, rz: 300.0, peak: 400.0, seed: 11 },
    Isle { kind: Kind::Alpine, angle: -1.80, dist: 2250.0, rx: 700.0, rz: 360.0, peak: 520.0, seed: 23 },
    // NE — the volcano past the desert.
    Isle { kind: Kind::Volcano, angle: -0.80, dist: 1500.0, rx: 520.0, rz: 490.0, peak: 300.0, seed: 37 },
    // E — red desert mesas.
    Isle { kind: Kind::Mesa, angle: 0.12, dist: 1150.0, rx: 430.0, rz: 240.0, peak: 170.0, seed: 41 },
    // SE — a far misty ridge.
    Isle { kind: Kind::Alpine, angle: 0.95, dist: 1900.0, rx: 520.0, rz: 300.0, peak: 330.0, seed: 53 },
    // S — dark hills past the Blight.
    Isle { kind: Kind::Hills, angle: 1.62, dist: 1500.0, rx: 480.0, rz: 280.0, peak: 190.0, seed: 67 },
    // SW — green forested hills.
    Isle { kind: Kind::Hills, angle: 2.40, dist: 1150.0, rx: 460.0, rz: 260.0, peak: 210.0, seed: 79 },
    // W — a green alpine island with snow on its crown.
    Isle { kind: Kind::Alpine, angle: 3.05, dist: 1550.0, rx: 480.0, rz: 280.0, peak: 300.0, seed: 97 },
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

// ── Height field ─────────────────────────────────────────────────────────────────
/// Height above the sea at island-local `(x, z)` (x = long/tangent axis, z = radial, +z toward
/// the castle). Negative = under water.
fn height(isle: &Isle, x: f32, z: f32) -> f32 {
    let s = isle.seed;
    let (nx, nz) = (x / isle.rx, z / isle.rz);
    // Domain-warped coast so the outline is ragged bays and headlands, not an ellipse.
    let wx = nx + (fbm(nx * 1.7, nz * 1.7, s ^ 0xa1, 3) - 0.5) * 0.55;
    let wz = nz + (fbm(nx * 1.7 + 9.3, nz * 1.7, s ^ 0xb2, 3) - 0.5) * 0.55;
    let r = (wx * wx + wz * wz).sqrt();
    let land = 1.0 - smoothstep(0.62, 1.0, r); // 1 inland → 0 at the coast
    let p = isle.peak;
    let h = match isle.kind {
        Kind::Alpine => {
            // A wandering ridge spine along the long axis; broad massifs on it, carved by ridged
            // noise into arêtes and cirques (broad low-frequency crests, not needles).
            let spine_z = 0.16 * (wx * 2.3 + s as f32).sin() + 0.08 * (wx * 5.1 + s as f32 * 0.37).sin();
            let spine = (-(wz - spine_z).powi(2) * 4.0).exp();
            let mass = (1.0 - r).max(0.0).powf(0.75);
            let peaks = ridged(x * 0.0028 + 3.1, z * 0.0028, s, 6);
            let crests = 0.5 + 0.5 * (fbm(x * 0.0016, z * 0.0016, s ^ 0x1f, 3) * 2.0 - 0.6).clamp(0.0, 1.0);
            p * mass * (0.42 * spine + 0.18 + 0.62 * peaks * crests * (0.4 + 0.6 * spine))
        }
        Kind::Volcano => {
            // Asymmetric stratovolcano: warped radius, a parasitic shoulder cone, a crater breached
            // toward one flank, radial gullies, and a broad hilly apron around the foot.
            let wr = |ox: f32, oz: f32| ((nx - ox).powi(2) + (nz - oz).powi(2)).sqrt();
            let warp = (fbm(nx * 2.2, nz * 2.2, s ^ 0x33, 3) - 0.5) * 0.22;
            let rr = wr(0.0, 0.0) + warp;
            let cone = (1.0 - (rr.max(0.12) - 0.12) / 0.74).max(0.0).powf(1.45);
            let shoulder = 0.42 * (1.0 - wr(-0.38, 0.12) / 0.42).max(0.0).powf(1.5);
            let ang = nz.atan2(nx);
            let breach = smoothstep(0.55, 0.0, (ang - 0.9).abs()) * 0.10;
            let crater = smoothstep(0.11, 0.02, rr) * (0.20 + breach);
            let gully = (ridged(ang * 2.4 + 10.0, rr * 4.0, s, 3) - 0.35) * 0.09 * smoothstep(0.06, 0.45, rr);
            let apron = (1.0 - r).max(0.0).powf(0.9) * fbm(x * 0.006, z * 0.006, s ^ 7, 4) * 0.30;
            p * (cone.max(shoulder) - crater + gully * cone.sqrt() + apron)
        }
        Kind::Mesa => {
            // Terraced tablelands: quantise a broad noise into flat tops with steep scarps.
            let base = fbm(x * 0.0035, z * 0.0035, s, 4) * land;
            let steps = 3.0;
            let t = base * steps * 1.6;
            let stepped = (t.floor() + smoothstep(0.78, 1.0, t.fract())) / steps;
            p * stepped.min(1.0) + p * 0.04 * fbm(x * 0.03, z * 0.03, s ^ 3, 3)
        }
        Kind::Hills => {
            let mass = (1.0 - r).max(0.0).powf(0.7);
            let hills = fbm(x * 0.006, z * 0.006, s, 5);
            let crown = ridged(x * 0.005, z * 0.005, s ^ 9, 4);
            p * mass * (0.55 * hills + 0.45 * crown)
        }
    };
    // Coast: sink everything outside the landmass below the sea.
    h * land - (1.0 - land) * 18.0 + 2.5 * land
}

// ── Colour ───────────────────────────────────────────────────────────────────────
fn mix4(a: [f32; 4], b: [f32; 4], t: f32) -> [f32; 4] {
    let t = t.clamp(0.0, 1.0);
    [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t, 1.0]
}

/// Vertex colour from height `h`, slope `steep` (0 flat … 1 vertical) and position noise.
fn color(isle: &Isle, h: f32, steep: f32, x: f32, z: f32) -> [f32; 4] {
    let s = isle.seed;
    let t = h / isle.peak; // 0 at sea … 1 at the summit
    let n = fbm(x * 0.02, z * 0.02, s ^ 0x55, 3);
    let n2 = fbm(x * 0.09, z * 0.09, s ^ 0x66, 2);
    let sand = lin(0xc2ad80);
    let mut c = match isle.kind {
        Kind::Alpine | Kind::Hills => {
            let grass = mix4(lin(0x5b7a3a), lin(0x6e8a45), n);
            let forest = mix4(lin(0x2c4424), lin(0x36502b), n2);
            let rock = mix4(lin(0x6d665c), lin(0x8a8276), n2);
            // Forest band on the lower slopes (patchy), grass above, bare rock on steep/high.
            let forest_w = smoothstep(0.62, 0.45, t) * smoothstep(0.30, 0.55, n + 0.15);
            let mut c = mix4(grass, forest, forest_w);
            let rock_w = smoothstep(0.42, 0.72, steep + t * 0.55 - 0.15);
            c = mix4(c, rock, rock_w);
            if isle.kind == Kind::Alpine {
                // Snow: a ragged snowline that holds on flatter ground, streaks down gullies.
                let line = 0.58 + (n - 0.5) * 0.18;
                let snow_w = smoothstep(line, line + 0.08, t + (0.25 - steep) * 0.2 + (n2 - 0.5) * 0.08);
                c = mix4(c, lin(0xeef3f8), snow_w);
            }
            c
        }
        Kind::Volcano => {
            let basalt = mix4(lin(0x2f2b2a), lin(0x3d3633), n2);
            let ash = mix4(lin(0x6a5a4c), lin(0x7d6b5a), n);
            let scrub = mix4(lin(0x3a4a2a), lin(0x56643a), n);
            let mut c = mix4(scrub, ash, smoothstep(0.22, 0.42, t + (n - 0.5) * 0.15 + steep * 0.2));
            c = mix4(c, basalt, smoothstep(0.35, 0.65, t + steep * 0.3 + (n2 - 0.5) * 0.2));
            // Rust-red scorched ring round the crater lip.
            mix4(c, lin(0x5e3426), smoothstep(0.92, 0.99, t) * 0.45)
        }
        Kind::Mesa => {
            // Horizontal strata on the scarps, pale sand on the flat tops.
            let band = (h * 0.11 + n2 * 2.0).sin() * 0.5 + 0.5;
            let strata = mix4(lin(0x9a5a3a), lin(0xc0875a), band);
            let top = mix4(lin(0xc9a774), lin(0xb89262), n);
            mix4(top, strata, smoothstep(0.25, 0.55, steep))
        }
    };
    // Beach ring + wet dark foot right at the waterline.
    c = mix4(c, sand, smoothstep(5.0, 1.5, h) * (1.0 - steep) * smoothstep(0.3, 0.6, n2 + 0.2));
    // Faint per-area brightness variation so broad slopes don't read as flat paint.
    let v = 0.90 + 0.2 * n2;
    [c[0] * v, c[1] * v, c[2] * v, 1.0]
}

// ── Mesh ─────────────────────────────────────────────────────────────────────────
/// Build one island in local space (x tangent, z radial with +z facing the castle).
fn build_mesh(isle: &Isle) -> Mesh {
    let ext = isle.rx.max(isle.rz) * 1.15;
    let step = 2.0 * ext / (GRID - 1) as f32;
    let at = |i: usize, j: usize| (-ext + i as f32 * step, -ext + j as f32 * step);

    let mut hs = vec![0.0f32; GRID * GRID];
    for j in 0..GRID {
        for i in 0..GRID {
            let (x, z) = at(i, j);
            hs[j * GRID + i] = height(isle, x, z);
        }
    }
    let h_at = |i: usize, j: usize| hs[j.min(GRID - 1) * GRID + i.min(GRID - 1)];

    let mut positions = Vec::with_capacity(GRID * GRID);
    let mut normals = Vec::with_capacity(GRID * GRID);
    let mut colors = Vec::with_capacity(GRID * GRID);
    for j in 0..GRID {
        for i in 0..GRID {
            let (x, z) = at(i, j);
            let h = h_at(i, j);
            let dx = h_at(i + 1, j) - h_at(i.saturating_sub(1), j);
            let dz = h_at(i, j + 1) - h_at(i, j.saturating_sub(1));
            let n = Vec3::new(-dx, 2.0 * step, -dz).normalize();
            positions.push([x, SEA_Y + h, z]);
            normals.push(n.to_array());
            colors.push(color(isle, h.max(0.0), 1.0 - n.y, x, z));
        }
    }

    // Emit only quads that are (a) above the sea somewhere and (b) on the castle-facing side: the
    // camera never gets behind these landmasses, so the far back slope is never seen.
    let back_cut = -0.45 * isle.rz;
    let mut idx: Vec<u32> = Vec::with_capacity(GRID * GRID * 6);
    for j in 0..GRID - 1 {
        for i in 0..GRID - 1 {
            let (_, z) = at(i, j + 1);
            if z < back_cut {
                continue;
            }
            let hmax = h_at(i, j).max(h_at(i + 1, j)).max(h_at(i, j + 1)).max(h_at(i + 1, j + 1));
            if hmax < -1.0 {
                continue;
            }
            let a = (j * GRID + i) as u32;
            let b = a + 1;
            let c = a + GRID as u32;
            let d = c + 1;
            // Counter-clockwise from above → +Y faces.
            idx.extend_from_slice(&[a, c, b, b, c, d]);
        }
    }

    let mut mesh = Mesh::new(PrimitiveTopology::TriangleList, RenderAssetUsages::RENDER_WORLD);
    mesh.insert_attribute(Mesh::ATTRIBUTE_POSITION, positions);
    mesh.insert_attribute(Mesh::ATTRIBUTE_NORMAL, normals);
    mesh.insert_attribute(Mesh::ATTRIBUTE_COLOR, colors);
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
        let ash = mix4(lin(0x6b625a), lin(0xd6d3cf), smoothstep(0.0, 0.45, f));
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
/// Spawn the horizon landmasses. Called once from `worldmap::build`.
pub fn build(commands: &mut Commands, meshes: &mut Assets<Mesh>, std_mats: &mut Assets<StandardMaterial>) {
    if std::env::var("FOREST_NOISLES").is_ok() {
        return;
    }
    let mat = std_mats.add(StandardMaterial {
        base_color: Color::WHITE,
        perceptual_roughness: 0.95,
        reflectance: 0.2,
        // DistanceFog is solid by ~190; these sit 1 000+ out. Haze is driven by hand instead.
        fog_enabled: false,
        ..default()
    });
    commands.insert_resource(IsleMaterial(mat.clone()));

    for isle in &ISLES {
        let (sa, ca) = isle.angle.sin_cos();
        let centre = Vec3::new(ca * isle.dist, 0.0, sa * isle.dist);
        // Local +z must point back at the castle: rotate so local +z = -radial.
        let yaw = (-ca).atan2(-sa);
        commands.spawn((
            Mesh3d(meshes.add(build_mesh(isle))),
            MeshMaterial3d(mat.clone()),
            Transform::from_translation(centre).with_rotation(Quat::from_rotation_y(yaw)),
            NoFrustumCulling,
            NotShadowCaster,
            NotShadowReceiver,
            BiomeEntity,
        ));
        if isle.kind == Kind::Volcano {
            // Rooted just inside the crater; leans the same way the cloth banners stream.
            let wind = Vec3::new(0.9, 0.0, -0.43).normalize();
            let vent = centre + Vec3::Y * (SEA_Y + isle.peak * 0.86);
            commands.spawn((
                Mesh3d(meshes.add(build_plume(isle.seed, wind))),
                MeshMaterial3d(mat.clone()),
                Transform::from_translation(vent),
                NoFrustumCulling,
                NotShadowCaster,
                NotShadowReceiver,
                BiomeEntity,
            ));
        }
    }
}

/// Aerial perspective for the horizon: pull the shared material toward the live fog colour —
/// albedo scaled by `1 - haze`, fog colour added as un-exposed emissive (same units the fog
/// blend itself uses) — so dawn, dusk, night and biome tints carry onto the far mountains.
fn drive_isle_haze(
    mat: Option<Res<IsleMaterial>>,
    fog: Query<&DistanceFog, With<Camera3d>>,
    mut mats: ResMut<Assets<StandardMaterial>>,
    mut last: Local<Option<LinearRgba>>,
) {
    let (Some(mat), Ok(fog)) = (mat, fog.single()) else { return };
    let haze = std::env::var("FOREST_ISLE_HAZE").ok().and_then(|v| v.parse().ok()).unwrap_or(HAZE);
    let fc = fog.color.to_linear();
    if last.is_some_and(|l| (l.red - fc.red).abs() + (l.green - fc.green).abs() + (l.blue - fc.blue).abs() < 2e-3) {
        return;
    }
    *last = Some(fc);
    let Some(mut m) = mats.get_mut(&mat.0) else { return };
    let k = 1.0 - haze;
    m.base_color = Color::linear_rgb(k, k, k);
    m.emissive = LinearRgba::rgb(fc.red * haze, fc.green * haze, fc.blue * haze);
}
