//! **Crown colour variety + wind** — the kit's leaf-card and undergrowth materials as
//! `ExtendedMaterial<StandardMaterial, FoliageExt>`: stock PBR shading, plus a vertex stage
//! (`foliage_wind.wgsl`) that tints each tree's crown (yellow-green .. deep blue-green), drifts
//! the undergrowth colour in broad patches and bends vertices by an analytic wind field.
//!
//! Wind is on unless `FOREST_WIND=0`; `foliage_wind_prepass.wgsl` bends depth / shadows / motion
//! vectors identically. The wind clock is Bevy's `globals.time` — never tick it through the
//! material (see the note below `material`).
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
    /// x = blade-root ground match (see `ground_match`), y unused, z = amplitude (world units at
    /// weight 1), w = ripple.
    pub wind: Vec4,
    /// x = crown tint strength, y = snow amount (`alpine::snowkit` twins), z = olive meadow grade
    /// (green-only, fragment stage), w = shading-normal lean toward world up (see `ground_match`).
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
        "shaders/foliage_wind.wesl".into()
    }
    fn fragment_shader() -> ShaderRef {
        "shaders/foliage_grade.wesl".into()
    }
    fn prepass_vertex_shader() -> ShaderRef {
        if wind_enabled() { "shaders/foliage_wind_prepass.wesl".into() } else { ShaderRef::Default }
    }
}

pub struct FoliagePlugin;

impl Plugin for FoliagePlugin {
    fn build(&self, app: &mut App) {
        app.add_plugins(MaterialPlugin::<FoliageMaterial>::default());
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

/// Undergrowth only: make the grass / weed / flower cards sit IN the sward instead of on it —
/// `root` lifts the dark blade base into the ground's straw-olive, `grade` pulls the vivid and the
/// deep greens toward the meadow's olive, `up` leans the shading normal to world up (fully at the
/// root) so crossed cards stop printing hard planes at the ground line. The grade only touches
/// green-dominant texels (white daisies, yellow / purple flowers and straw stalks keep their hue).
/// `FOREST_GRASSGRADE="root,grade,up"` overrides the three for tuning.
pub fn ground_match(mut mat: FoliageMaterial, root: f32, grade: f32, up: f32) -> FoliageMaterial {
    let mut v = [root, grade, up];
    if let Ok(env) = std::env::var("FOREST_GRASSGRADE") {
        for (slot, s) in v.iter_mut().zip(env.split(',')) {
            if let Ok(x) = s.trim().parse() {
                *slot = x;
            }
        }
    }
    mat.extension.wind.wind.x = v[0];
    mat.extension.wind.tint.z = v[1];
    mat.extension.wind.tint.w = v[2];
    mat
}

// No per-frame wind tick: the shaders read Bevy's `globals.time`. Writing the clock into these
// materials every frame marked them all modified, and Bevy then re-specialized every foliage mesh
// (main pass, prepass, every shadow cascade) every frame — 32-60 fps -> 90-108 fps when removed.

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
