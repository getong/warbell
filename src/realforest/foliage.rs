//! **Crown colour variety (+ dormant wind)** — the kit's leaf-card and undergrowth materials as
//! `ExtendedMaterial<StandardMaterial, FoliageExt>`: stock PBR shading, plus a vertex stage
//! (`foliage_wind.wgsl`) that tints each tree's crown (yellow-green .. deep blue-green) and drifts
//! the undergrowth colour in broad patches.
//!
//! The same vertex stage can bend vertices by an analytic wind field, but wind is OFF (amplitude
//! 0, clock not ticked, stock prepass) — a static forest was the call for now. To enable: set an
//! amplitude in `realforest::try_build`, register `tick_wind`, and return
//! `foliage_wind_prepass.wgsl` from `prepass_vertex_shader` so depth / shadows / motion vectors
//! bend identically.
//!
//! Per-vertex freedom (0 = rooted, 1 = free tip) rides in `UV_1.x`, baked by [`bake_weights`]
//! from each model's height when the kit loads, so blade bases and trunk-side twigs stay put.

use bevy::mesh::VertexAttributeValues;
use bevy::pbr::{ExtendedMaterial, MaterialExtension, MaterialPlugin};
use bevy::prelude::*;
use bevy::render::render_resource::{AsBindGroup, ShaderType};
use bevy::shader::ShaderRef;

pub type FoliageMaterial = ExtendedMaterial<StandardMaterial, FoliageExt>;

#[derive(Clone, Copy, ShaderType, Debug)]
pub struct FoliageWind {
    /// x = time, y = previous frame's time, z = amplitude (world units at weight 1), w = ripple.
    pub wind: Vec4,
    /// x = crown tint strength.
    pub tint: Vec4,
}

#[derive(Asset, AsBindGroup, Clone, TypePath, Debug)]
pub struct FoliageExt {
    #[uniform(100)]
    pub wind: FoliageWind,
}

/// Wind on? `FOREST_WIND=0` makes the forest static (amplitude 0, stock prepass). Read once.
pub fn wind_enabled() -> bool {
    static ON: std::sync::OnceLock<bool> = std::sync::OnceLock::new();
    *ON.get_or_init(|| std::env::var("FOREST_WIND").map(|v| v != "0").unwrap_or(true))
}

impl MaterialExtension for FoliageExt {
    fn vertex_shader() -> ShaderRef {
        "shaders/foliage_wind.wgsl".into()
    }
    fn prepass_vertex_shader() -> ShaderRef {
        if wind_enabled() { "shaders/foliage_wind_prepass.wgsl".into() } else { ShaderRef::Default }
    }
}

pub struct FoliagePlugin;

impl Plugin for FoliagePlugin {
    fn build(&self, app: &mut App) {
        app.add_plugins(MaterialPlugin::<FoliageMaterial>::default());
        if wind_enabled() {
            app.add_systems(Update, tick_wind);
        }
    }
}

/// `amplitude` = sway of a free tip in world units; `ripple` = how much neighbouring cards /
/// blades de-sync; `tint` = crown colour variety strength.
pub fn material(base: StandardMaterial, amplitude: f32, ripple: f32, tint: f32) -> FoliageMaterial {
    let amplitude = if wind_enabled() { amplitude } else { 0.0 };
    ExtendedMaterial {
        base,
        extension: FoliageExt {
            wind: FoliageWind { wind: Vec4::new(0.0, 0.0, amplitude, ripple), tint: Vec4::new(tint, 0.0, 0.0, 0.0) },
        },
    }
}

/// Advance the wind clock in every foliage material (a handful of assets — the uniform re-upload
/// is trivial). Only registered when [`wind_enabled`].
fn tick_wind(time: Res<Time>, mut mats: ResMut<Assets<FoliageMaterial>>) {
    let t = time.elapsed_secs_wrapped();
    let ids: Vec<_> = mats.ids().collect();
    for id in ids {
        if let Some(mut m) = mats.get_mut(id) {
            let w = &mut m.extension.wind.wind;
            w.y = w.x;
            w.x = t;
        }
    }
}

/// Write each vertex's wind freedom into `UV_1.x` for one MODEL (all its parts): height above the
/// model base over the model's height, eased, so the lower part of a plant stays rooted. Only the
/// parts in `foliage` (leaf / blade materials) are written; every part gets the attribute so the
/// chunk merger sees consistent layouts per material.
pub fn bake_weights(parts: &mut [(&mut Mesh, bool)]) {
    let top = parts
        .iter()
        .filter_map(|(m, _)| m.attribute(Mesh::ATTRIBUTE_POSITION))
        .filter_map(|a| match a {
            VertexAttributeValues::Float32x3(p) => p.iter().map(|v| v[1]).reduce(f32::max),
            _ => None,
        })
        .fold(0.0f32, f32::max)
        .max(0.05);
    for (mesh, foliage) in parts.iter_mut() {
        if !*foliage {
            continue;
        }
        let Some(VertexAttributeValues::Float32x3(p)) = mesh.attribute(Mesh::ATTRIBUTE_POSITION) else { continue };
        let uv1: Vec<[f32; 2]> = p
            .iter()
            .map(|v| {
                let h = (v[1] / top).clamp(0.0, 1.0);
                // Undergrowth: rooted base, free tips. Tree crowns: the outer / upper cards move most.
                let r = (v[0] * v[0] + v[2] * v[2]).sqrt() / top;
                [(h.powf(1.4) * 0.8 + r.min(1.0) * 0.4).min(1.0), 0.0]
            })
            .collect();
        mesh.insert_attribute(Mesh::ATTRIBUTE_UV_1, uv1);
    }
}
