//! **Structure re-skin** — the realistic forest's answer to the hand-built low-poly scenery that
//! still stands in it (wayside signposts / fences / shrines, roadside set-pieces, the abandoned
//! camp, the ork camp, the old mill, chests). Those are gameplay landmarks assembled from
//! primitives in code with flat vertex colours; next to scanned trees and ground they read as toys.
//!
//! Rather than re-authoring each one, every opaque vertex-coloured `StandardMaterial` mesh that
//! lands in (or right at the edge of) the forest is switched to [`ReskinMaterial`]: the same
//! material, plus world-space **triplanar** wood / stone / cloth scans (`struct_*.dds`, Poly Haven
//! CC0) chosen per fragment from the vertex colour (warm saturated = wood, desaturated = stone,
//! anything else = woven cloth). The detail is mean-normalised, so the authored colour stays the
//! authored colour — it just gains grain, mortar, weave, roughness and AO. Shapes, collisions and
//! gameplay are untouched. `FOREST_RESKIN=0` turns it off.

use std::collections::HashMap;

use bevy::pbr::{ExtendedMaterial, MaterialExtension, MaterialPlugin};
use bevy::prelude::*;
use bevy::render::render_resource::{AsBindGroup, ShaderType};
use bevy::shader::ShaderRef;

pub type ReskinMaterial = ExtendedMaterial<StandardMaterial, ReskinExt>;

#[derive(Clone, Copy, ShaderType, Debug)]
pub struct ReskinParams {
    /// World units per texture repeat: x = wood, y = stone, z = cloth; w = detail strength.
    pub tile: Vec4,
}

#[derive(Asset, AsBindGroup, Clone, TypePath, Debug)]
pub struct ReskinExt {
    #[uniform(100)]
    pub params: ReskinParams,
    #[texture(101, dimension = "2d_array")]
    #[sampler(104)]
    pub albedo: Handle<Image>,
    #[texture(102, dimension = "2d_array")]
    pub normal: Handle<Image>,
    #[texture(103, dimension = "2d_array")]
    pub ormh: Handle<Image>,
}

impl MaterialExtension for ReskinExt {
    fn fragment_shader() -> ShaderRef {
        "shaders/reskin.wgsl".into()
    }
}

pub struct ReskinPlugin;

impl Plugin for ReskinPlugin {
    fn build(&self, app: &mut App) {
        app.add_plugins(MaterialPlugin::<ReskinMaterial>::default());
        if std::env::var("FOREST_RESKIN").is_ok_and(|v| v == "0") {
            return;
        }
        // After transform propagation so a freshly spawned piece already knows where it stands.
        app.add_systems(PostUpdate, reskin_new.after(bevy::transform::TransformSystems::Propagate));
    }
}

/// The three struct layers, loaded once on first use.
struct Layers {
    albedo: Handle<Image>,
    normal: Handle<Image>,
    ormh: Handle<Image>,
}

/// Is `(x, z)` in the forest or within a few units of it (camps and POIs sit on its edge)?
fn near_forest(x: f32, z: f32) -> bool {
    const R: f32 = 6.0;
    [(0.0, 0.0), (R, 0.0), (-R, 0.0), (0.0, R), (0.0, -R)].iter().any(|(dx, dz)| {
        crate::worldmap::tile_biome_world(x + dx, z + dz) == Some(crate::biome::Biome::Forest)
    })
}

#[allow(clippy::too_many_arguments, clippy::type_complexity)]
fn reskin_new(
    mut commands: Commands,
    added: Query<(Entity, &MeshMaterial3d<StandardMaterial>, &Mesh3d, &GlobalTransform), Added<MeshMaterial3d<StandardMaterial>>>,
    parents: Query<&ChildOf>,
    actors: Query<(), Or<(With<crate::player::Hero>, With<crate::villagers::Villager>, With<crate::villagers::Captive>, With<bevy::mesh::skinning::SkinnedMesh>, With<AnimationPlayer>)>>,
    meshes: Res<Assets<Mesh>>,
    std_mats: Res<Assets<StandardMaterial>>,
    mut reskins: ResMut<Assets<ReskinMaterial>>,
    mut images: ResMut<Assets<Image>>,
    mut layers: Local<Option<Option<Layers>>>,
    mut cache: Local<HashMap<AssetId<StandardMaterial>, Handle<ReskinMaterial>>>,
) {
    if added.is_empty() || super::get().is_none() {
        return;
    }
    let layers = layers.get_or_insert_with(|| {
        let load = |map: &str, srgb: bool, images: &mut Assets<Image>| {
            let pngs = ["wood", "stone", "cloth"].map(|l| format!("forest_pbr/struct_{l}_{map}.png"));
            super::load::texture_array(&format!("forest_pbr/struct_{map}.dds"), &pngs.each_ref().map(|s| s.as_str()), srgb)
                .map(|i| images.add(i))
        };
        match (load("albedo", true, &mut images), load("normal", false, &mut images), load("ormh", false, &mut images)) {
            (Ok(albedo), Ok(normal), Ok(ormh)) => Some(Layers { albedo, normal, ormh }),
            (a, b, c) => {
                warn!("realforest: structure re-skin textures missing, keeping flat colours — {:?}", a.err().or(b.err()).or(c.err()));
                None
            }
        }
    });
    let Some(layers) = layers.as_ref() else { return };
    for (e, mat, mesh, gt) in &added {
        let p = gt.translation();
        if !near_forest(p.x, p.z) {
            continue;
        }
        let Some(m) = std_mats.get(&mat.0) else { continue };
        // Only flat vertex-coloured opaque scenery: textured (the kit itself), glowing, unlit or
        // see-through materials keep their look.
        if m.base_color_texture.is_some()
            || m.unlit
            || !matches!(m.alpha_mode, AlphaMode::Opaque)
            || m.emissive.red + m.emissive.green + m.emissive.blue > 0.01
        {
            continue;
        }
        if !meshes.get(&mesh.0).is_some_and(|me| me.contains_attribute(Mesh::ATTRIBUTE_COLOR)) {
            continue;
        }
        // Never characters (anything animated / a person), however they're built.
        let mut cur = e;
        let mut actor = actors.contains(cur);
        while !actor {
            let Ok(c) = parents.get(cur) else { break };
            cur = c.parent();
            actor = actors.contains(cur);
        }
        if actor {
            continue;
        }
        let h = cache
            .entry(mat.0.id())
            .or_insert_with(|| {
                reskins.add(ExtendedMaterial {
                    base: m.clone(),
                    extension: ReskinExt {
                        params: ReskinParams { tile: Vec4::new(1.6, 2.4, 0.9, 1.0) },
                        albedo: layers.albedo.clone(),
                        normal: layers.normal.clone(),
                        ormh: layers.ormh.clone(),
                    },
                })
            })
            .clone();
        commands.entity(e).remove::<MeshMaterial3d<StandardMaterial>>().insert(MeshMaterial3d(h));
    }
}
