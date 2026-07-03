//! Debug harness: isolate the terrain shader. `FOREST_GROUNDTEST=1` floats a big flat grass
//! plane high above the whole world; pair it with a straight-down `FOREST_CAM` + `FOREST_SHOT`
//! and the shot frames ONLY the terrain shader's lit output — no props, no terrace steps, no
//! tree shadows — so any repeating-pattern artifact in the ground is unmistakable. The plane
//! reads `world_position.xz` exactly like real ground, so its shading pattern is identical to
//! the real island, just unobstructed.
//!
//! Example (top-down over the floating plane):
//!   $env:FOREST_GROUNDTEST="1"; $env:FOREST_SHOT="g.png"; $env:FOREST_CAM="200,92,212,200,40,200"; cargo run

use bevy::asset::RenderAssetUsages;
use bevy::mesh::{Indices, PrimitiveTopology};
use bevy::prelude::*;

use crate::biome::GroundDetail;
use crate::terrain::{make_material, TerrainMaterial};

pub struct GroundTestPlugin;

impl Plugin for GroundTestPlugin {
    fn build(&self, app: &mut App) {
        if std::env::var("FOREST_GROUNDTEST").is_ok() {
            app.add_systems(Startup, spawn_test_plane);
        }
    }
}

fn spawn_test_plane(
    mut commands: Commands,
    mut meshes: ResMut<Assets<Mesh>>,
    mut images: ResMut<Assets<Image>>,
    mut mats: ResMut<Assets<TerrainMaterial>>,
) {
    // Mirrors worldmap's grass ground spec, so the test matches the real grass material.
    let detail = GroundDetail {
        scale: 0.18,
        strength: 0.52,
        variation: 0.70,
        seed: 1.0,
        dark: 0x356b28,
        base: 0x5d9e44,
        light: 0x95d162,
        grain: 0.72,
        streak: 0.5,
    };
    let mat = make_material(&detail, 1.0, None, &mut images, &mut mats);

    // Float a TESSELLATED plane over an open grass area at real world XZ, but high above the
    // world so a top-down camera frames only it. Two things must match the real island so the
    // test is faithful (the earlier flat-colour version hid the vertex-colour grid):
    //   • world_position.xz == the plane's world XZ → the shader's procedural layers match;
    //   • each vertex's COLOUR == real `ground_color`, sampled in BASE space exactly as
    //     `build_terrain_chunk` does: `ground_color((world + G) / MAP_SCALE)`.
    let (cx, cz, y, half) = (-30.0_f32, 30.0_f32, 40.0_f32, 80.0_f32); // open meadow, big so aim can't miss
    const N: usize = 320; // verts per side → ~0.5u cells, fine enough for grain + mottle
    let step = (2.0 * half) / (N - 1) as f32;
    use crate::worldmap::{ground_color, GX, GZ, MAP_SCALE};

    let mut pos: Vec<[f32; 3]> = Vec::with_capacity(N * N);
    let mut nrm: Vec<[f32; 3]> = Vec::with_capacity(N * N);
    let mut uv: Vec<[f32; 2]> = Vec::with_capacity(N * N);
    let mut col: Vec<[f32; 4]> = Vec::with_capacity(N * N);
    for iz in 0..N {
        for ix in 0..N {
            let wx = cx - half + ix as f32 * step;
            let wz = cz - half + iz as f32 * step;
            pos.push([wx, y, wz]);
            nrm.push([0.0, 1.0, 0.0]);
            uv.push([ix as f32 / (N - 1) as f32, iz as f32 / (N - 1) as f32]);
            col.push(ground_color((wx + GX) / MAP_SCALE, (wz + GZ) / MAP_SCALE));
        }
    }
    let mut idx: Vec<u32> = Vec::with_capacity((N - 1) * (N - 1) * 6);
    for iz in 0..N - 1 {
        for ix in 0..N - 1 {
            let a = (iz * N + ix) as u32;
            let b = a + 1;
            let c = a + N as u32;
            let d = c + 1;
            idx.extend_from_slice(&[a, b, d, a, d, c]);
        }
    }

    let mut mesh = Mesh::new(PrimitiveTopology::TriangleList, RenderAssetUsages::default());
    mesh.insert_attribute(Mesh::ATTRIBUTE_POSITION, pos);
    mesh.insert_attribute(Mesh::ATTRIBUTE_NORMAL, nrm);
    mesh.insert_attribute(Mesh::ATTRIBUTE_UV_0, uv);
    mesh.insert_attribute(Mesh::ATTRIBUTE_COLOR, col);
    mesh.insert_indices(Indices::U32(idx));

    commands.spawn((Mesh3d(meshes.add(mesh)), MeshMaterial3d(mat), Transform::default(), Name::new("ground_test_plane")));
    info!("FOREST_GROUNDTEST: spawned faithful terrain test plane (real ground_color) centred world ({cx},{cz}) at y={y} — frame it top-down with FOREST_CAM.");
}
