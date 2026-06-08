//! **Roads** — worn dirt approach-paths radiating out from the castle gates, a distilled port
//! of the old game's `roads.ts` / `Paths.tsx`. Built as one merged, vertex-coloured ribbon of
//! flat slabs that step along each path at terrain height, laid just above the ground so the
//! eye reads a trampled track leading home. Purely cosmetic (no nav/placement effect).

use bevy::mesh::MeshBuilder;
use bevy::prelude::*;

use crate::biome::BiomeEntity;
use crate::palette::lin;
use crate::worldmap::ground_at_world;

/// Dirt track colour (trampled earth).
const DIRT: u32 = 0x8a6d44;
/// Half-width of the track (world units).
const HALF_W: f32 = 1.2;
/// Slab length per step + how far each road runs out from its gate.
const STEP: f32 = 2.0;
const ROAD_LEN: f32 = 22.0;

fn tinted(mut m: Mesh, c: u32) -> Mesh {
    let n = m.count_vertices();
    m.insert_attribute(Mesh::ATTRIBUTE_COLOR, vec![lin(c); n]);
    m
}

/// Build the merged road mesh (world-space slabs, so the entity is spawned at identity).
fn roads_mesh() -> Option<Mesh> {
    let mut parts: Vec<Mesh> = Vec::new();
    for g in crate::castle::gate_centers() {
        // March outward from the gate (away from the origin).
        let dir = g.normalize_or_zero();
        if dir == Vec2::ZERO {
            continue;
        }
        let yaw = dir.x.atan2(dir.y);
        let steps = (ROAD_LEN / STEP) as i32;
        for i in 0..steps {
            let mid = g + dir * (i as f32 + 0.5) * STEP;
            // Skip slabs over water / off the island.
            let Some(y) = ground_at_world(mid.x, mid.y) else { continue };
            // Taper the track to nothing at its far end so it fades into the wild.
            let t = 1.0 - i as f32 / steps as f32;
            let w = HALF_W * 2.0 * (0.4 + 0.6 * t);
            parts.push(tinted(
                Cuboid::new(w, 0.06, STEP * 1.05)
                    .mesh()
                    .build()
                    .rotated_by(Quat::from_rotation_y(yaw))
                    .translated_by(Vec3::new(mid.x, y + 0.05, mid.y)),
                DIRT,
            ));
        }
    }
    if parts.is_empty() {
        return None;
    }
    let mut it = parts.into_iter();
    let mut base = it.next().unwrap();
    for p in it {
        base.merge(&p).expect("road slabs share attributes");
    }
    base.duplicate_vertices();
    base.compute_flat_normals();
    Some(base)
}

/// Spawn the roads. Called from `worldmap::build`.
pub fn populate(commands: &mut Commands, meshes: &mut Assets<Mesh>, materials: &mut Assets<StandardMaterial>) {
    let Some(mesh) = roads_mesh() else { return };
    let mat = materials.add(StandardMaterial { base_color: Color::WHITE, perceptual_roughness: 1.0, ..default() });
    commands.spawn((Mesh3d(meshes.add(mesh)), MeshMaterial3d(mat), Transform::IDENTITY, BiomeEntity));
}
