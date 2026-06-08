//! Distant scenery — the world map's unreachable forest edge on the NORTH (-Z) shore: a
//! river channel off the coast, a row of full-detail trees on the far bank, then a mass of
//! low-res conifers on rising ground fading into the `DistanceFog`. The other three sides
//! stay open ocean. Baked into a few merged flat-shaded meshes (a handful of draw calls),
//! coloured via `ATTRIBUTE_COLOR` against a shared white material, `NotShadowCaster` +
//! static. Deterministic (constant-seeded Mulberry32).

use bevy::asset::RenderAssetUsages;
use bevy::light::NotShadowCaster;
use bevy::mesh::{Indices, PrimitiveTopology};
use bevy::prelude::*;

use crate::biome::BiomeEntity;
use crate::palette::lin;

pub struct DistantPlugin;

impl Plugin for DistantPlugin {
    fn build(&self, _app: &mut App) {
        // No systems — the world-map build calls `spawn_forest_edge`.
    }
}

// ── World-map north forest edge (one side only — other 3 sides stay open ocean) ─
// The island's NORTH (-Z) shore is a land edge instead of open sea: a river channel off
// the coast, then a visible bank of ground that rises out of the water, carrying a mass of
// low-poly conifers up into the fog. The other three sides keep the open ocean (+ boats).
// North = -Z (atan2(z,x) convention).
const EDGE_SHORE_Z: f32 = -88.0; // waterline of the far bank (island N coast ≈ -74 → ~14u river)
const EDGE_Z_FAR: f32 = -200.0; // forest recedes to the fog horizon
const EDGE_X_HALF: f32 = 122.0; // half-width across the north
const EDGE_WATERLINE: f32 = -0.4; // ground meets the sea exactly here
const EDGE_BANK_RISE: f32 = 6.0; // world-units of depth over which the shore bank climbs
const EDGE_PLATEAU_H: f32 = 4.5; // height the bank/plateau sits above the water
const EDGE_MAX_RISE: f32 = 18.0; // forested hill climbs this much more toward the fog
const EDGE_BEACH_DEPTH: f32 = 7.0; // sandy band depth at the shore (visible shore strip)
const EDGE_TREE_SETBACK: f32 = 7.0; // keep trees this far back from the water
const EDGE_LOWRES_TREES: u32 = 1300; // low-poly conifers covering the hill
const EDGE_BEACH: u32 = 0xbcae7e; // sandy shore at the waterline (light, reads against blue)
const EDGE_FLOOR_DARK: u32 = 0x203619; // forest floor in shadow
const EDGE_FLOOR_LIT: u32 = 0x35531f; // sunlit forest floor
const SHORE_DARK: u32 = 0x18351f; // conifer shadow tone
const SHORE_MID: u32 = 0x2a5631; // conifer body tone

/// Ground height of the north forest floor at world `(x, z)`. Meets the sea at the shore,
/// rises steeply over `EDGE_BANK_RISE` to a plateau that sits clearly above the water, then
/// climbs into a forested hill toward the fog. Shared by the floor mesh and tree placement.
fn edge_ground_y(x: f32, z: f32) -> f32 {
    let depth = (EDGE_SHORE_Z - z).max(0.0); // 0 at the waterline, grows going north
    let bank = (depth / EDGE_BANK_RISE).clamp(0.0, 1.0) * EDGE_PLATEAU_H; // steep visible bank
    let t = (depth / (EDGE_SHORE_Z - EDGE_Z_FAR)).clamp(0.0, 1.0);
    let hills = t * t * EDGE_MAX_RISE;
    let bump = ((x * 0.06).sin() * 1.6 + (z * 0.05 + x * 0.025).sin() * 2.2) * t;
    EDGE_WATERLINE + bank + hills + bump
}

/// Spawn the north forest edge: a rising ground bank + a low-poly conifer mass on it. The
/// river is the open water between the island coast and this bank. Tagged [`BiomeEntity`],
/// static, `NotShadowCaster`.
pub fn spawn_forest_edge(
    commands: &mut Commands,
    meshes: &mut Assets<Mesh>,
    materials: &mut Assets<StandardMaterial>,
    _sea_y: f32,
) {
    let mat = materials.add(StandardMaterial { base_color: Color::WHITE, perceptual_roughness: 0.8, ..default() });

    // Rising ground (sandy shore → forest floor → hills) so the trees stand on real land.
    let floor = meshes.add(build_forest_floor());
    commands.spawn((Mesh3d(floor), MeshMaterial3d(mat.clone()), Transform::default(), NotShadowCaster, BiomeEntity));

    // The conifer mass, set back from the water onto the bank.
    let trees = meshes.add(build_lowres_forest());
    commands.spawn((Mesh3d(trees), MeshMaterial3d(mat), Transform::default(), NotShadowCaster, BiomeEntity));
}

/// Rising forest-floor heightfield over the north band: sandy at the waterline, forest
/// floor inland (vertex-coloured, flat-shaded).
fn build_forest_floor() -> Mesh {
    let cols = 72usize;
    let rows = 48usize;
    let mut r = Rng(0x0f10_2026);
    let mut positions: Vec<[f32; 3]> = Vec::with_capacity((cols + 1) * (rows + 1));
    let mut colors: Vec<[f32; 4]> = Vec::with_capacity((cols + 1) * (rows + 1));
    let beach = lin(EDGE_BEACH);
    let dark = lin(EDGE_FLOOR_DARK);
    let lit = lin(EDGE_FLOOR_LIT);
    for ri in 0..=rows {
        let tz = ri as f32 / rows as f32;
        let z = EDGE_SHORE_Z + (EDGE_Z_FAR - EDGE_SHORE_Z) * tz;
        for ci in 0..=cols {
            let tx = ci as f32 / cols as f32;
            let x = -EDGE_X_HALF + 2.0 * EDGE_X_HALF * tx;
            positions.push([x, edge_ground_y(x, z), z]);
            // Forest-floor tone, faded to a sandy beach band right at the waterline.
            let m = (r.next() * 0.5 + 0.5).clamp(0.0, 1.0);
            let floor = [
                dark[0] + (lit[0] - dark[0]) * m,
                dark[1] + (lit[1] - dark[1]) * m,
                dark[2] + (lit[2] - dark[2]) * m,
                1.0,
            ];
            let depth = EDGE_SHORE_Z - z;
            let shore = (depth / EDGE_BEACH_DEPTH).clamp(0.0, 1.0); // 0 = sand at water, 1 = forest
            colors.push([
                beach[0] + (floor[0] - beach[0]) * shore,
                beach[1] + (floor[1] - beach[1]) * shore,
                beach[2] + (floor[2] - beach[2]) * shore,
                1.0,
            ]);
        }
    }
    let w = cols + 1;
    let mut indices: Vec<u32> = Vec::with_capacity(cols * rows * 6);
    for ri in 0..rows {
        for ci in 0..cols {
            let a = (ri * w + ci) as u32;
            let b = (ri * w + ci + 1) as u32;
            let c = ((ri + 1) * w + ci) as u32;
            let d = ((ri + 1) * w + ci + 1) as u32;
            indices.extend_from_slice(&[a, c, b, b, c, d]);
        }
    }
    let mut m = Mesh::new(PrimitiveTopology::TriangleList, RenderAssetUsages::default());
    m.insert_attribute(Mesh::ATTRIBUTE_POSITION, positions);
    m.insert_attribute(Mesh::ATTRIBUTE_COLOR, colors);
    m.insert_indices(Indices::U32(indices));
    flat_shaded(m)
}

/// Low-poly conifer mass covering the bank/hill, set back from the waterline. Sized 1.5×
/// smaller than the original wall so the ground reads beneath them.
fn build_lowres_forest() -> Mesh {
    let mut r = Rng(0x00fe_2026);
    let mut parts: Vec<Mesh> = Vec::new();
    for _ in 0..EDGE_LOWRES_TREES {
        let x = r.range(-EDGE_X_HALF, EDGE_X_HALF);
        let z = r.range(EDGE_Z_FAR, EDGE_SHORE_Z - EDGE_TREE_SETBACK);
        let base = Vec3::new(x, edge_ground_y(x, z), z);
        let trunk_h = r.range(0.7, 1.3);
        let trunk_r = r.range(0.17, 0.3);
        let needle_h = r.range(4.7, 9.3);
        let needle_r = r.range(1.5, 2.7);
        let crown = if r.next() < 0.5 { SHORE_DARK } else { SHORE_MID };
        // Trunk stub, tucked INSIDE the lower cone so nothing floats.
        parts.push(tinted(
            Cylinder::new(trunk_r, trunk_h).mesh().resolution(4).build().translated_by(base + Vec3::new(0.0, trunk_h * 0.5, 0.0)),
            lin(SHORE_DARK),
        ));
        // Lowest cone tier sits ON the ground (skirt meets the land — no levitation gap).
        parts.push(tinted(cone_base_y0(needle_r, needle_h, 5, base), lin(crown)));
        parts.push(tinted(
            cone_base_y0(needle_r * 0.62, needle_h * 0.6, 5, base + Vec3::new(0.0, needle_h * 0.45, 0.0)),
            lin(crown),
        ));
    }
    flat_shaded(merged(parts))
}

// ── Deterministic RNG (Mulberry32, same as scatter) ───────────────────────────
struct Rng(u32);
impl Rng {
    fn next(&mut self) -> f32 {
        self.0 = self.0.wrapping_add(0x6d2b_79f5);
        let mut t = self.0;
        t = (t ^ (t >> 15)).wrapping_mul(t | 1);
        t ^= t.wrapping_add((t ^ (t >> 7)).wrapping_mul(t | 61));
        ((t ^ (t >> 14)) as f32) / 4_294_967_296.0
    }
    fn range(&mut self, lo: f32, hi: f32) -> f32 {
        lo + self.next() * (hi - lo)
    }
}

// ── Mesh helpers ───────────────────────────────────────────────────────────────
fn tinted(mut m: Mesh, c: [f32; 4]) -> Mesh {
    let n = m.count_vertices();
    m.insert_attribute(Mesh::ATTRIBUTE_COLOR, vec![c; n]);
    m
}

fn merged(parts: Vec<Mesh>) -> Mesh {
    let mut it = parts.into_iter();
    let mut base = it.next().expect("at least one part");
    for p in it {
        base.merge(&p).expect("distant parts share attributes");
    }
    base
}

fn flat_shaded(mut m: Mesh) -> Mesh {
    m.duplicate_vertices();
    m.compute_flat_normals();
    m
}

/// A cone whose BASE sits on local y=0, then translated to `center`.
fn cone_base_y0(radius: f32, height: f32, sides: u32, center: Vec3) -> Mesh {
    Cone { radius, height }
        .mesh()
        .resolution(sides)
        .build()
        .translated_by(Vec3::new(0.0, height * 0.5, 0.0) + center)
}

