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
    /// x = blade-root ground match (see `ground_match`), y = 1 on undergrowth (bends under feet,
    /// `grass_trample`), z = amplitude (world units at weight 1), w = ripple.
    pub wind: Vec4,
    /// x = crown tint strength, y = snow amount (`alpine::snowkit` twins), z = range-dissolve band
    /// (world units, 0 = off; see [`dissolve`]), w = shading-normal lean toward world up (see
    /// `ground_match`).
    pub tint: Vec4,
}

#[derive(Asset, AsBindGroup, Clone, TypePath, Debug)]
pub struct FoliageExt {
    #[uniform(100)]
    pub wind: FoliageWind,
    /// Who is walking through the grass (`crate::grass_trample`) — the one shared buffer.
    #[storage(101, read_only)]
    pub trample: Handle<bevy::render::storage::ShaderBuffer>,
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
    fn prepass_vertex_shader() -> ShaderRef {
        // Always ours (amplitude 0 when wind is off): it also feeds the range dissolve.
        "shaders/foliage_wind_prepass.wesl".into()
    }
    fn prepass_fragment_shader() -> ShaderRef {
        "shaders/foliage_wind_prepass.wesl".into()
    }
    fn specialize(
        _pipeline: &bevy::pbr::MaterialExtensionPipeline,
        descriptor: &mut bevy::render::render_resource::RenderPipelineDescriptor,
        _layout: &bevy::mesh::MeshVertexBufferLayoutRef,
        key: bevy::pbr::MaterialExtensionKey<Self>,
    ) -> Result<(), bevy::render::render_resource::SpecializedMeshPipelineError> {
        use bevy::pbr::MeshPipelineKey;
        // Main-pass early-Z for alpha-masked foliage. The depth prepass has already written each
        // card's exact (wind-bent, alpha-tested) depth, so the main pass draws with an EQUAL depth
        // test and NO `discard`: a cut-out texel fails the test (the buffer holds whatever is behind
        // it), so the coverage is identical — but without a discard in the shader the GPU keeps
        // early depth testing, and every hidden / cut-out grass fragment is rejected before shading
        // instead of after.
        let main = descriptor.label.as_deref().is_some_and(|l| l.ends_with("opaque_mesh_pipeline"));
        if main
            && grass_eq()
            && key.mesh_key.contains(MeshPipelineKey::DEPTH_PREPASS | MeshPipelineKey::MAY_DISCARD)
        {
            if let Some(ds) = descriptor.depth_stencil.as_mut() {
                ds.depth_compare = Some(bevy::render::render_resource::CompareFunction::Equal);
                ds.depth_write_enabled = Some(false);
            }
            if let Some(frag) = descriptor.fragment.as_mut() {
                frag.shader_defs.retain(|d| !matches!(d, bevy::shader::ShaderDefVal::Bool(n, _) if n == "MAY_DISCARD"));
            }
        }
        Ok(())
    }
}

/// `FOREST_GRASSEQ=0` restores the stock (discarding, GreaterEqual) foliage main pass for A/B.
fn grass_eq() -> bool {
    static ON: std::sync::OnceLock<bool> = std::sync::OnceLock::new();
    *ON.get_or_init(|| std::env::var("FOREST_GRASSEQ").map(|v| v != "0").unwrap_or(true))
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
            trample: crate::grass_trample::TRAMPLE_BUF,
        },
    }
}

/// Undergrowth only: make the grass / weed / flower cards sit IN the sward instead of on it —
/// `root` lifts the dark blade base into the ground's straw-olive, `up` leans the shading normal to
/// world up (fully at the root) so crossed cards stop printing hard planes at the ground line. (The
/// olive grade of the greens themselves is baked into the atlas — `tools/blender_forest/common.py`
/// `olive_grade` — so the cards keep the stock PBR fragment, no per-pixel cost.)
/// `FOREST_GRASSGRADE="root,up"` overrides the two for tuning.
pub fn ground_match(mut mat: FoliageMaterial, root: f32, up: f32) -> FoliageMaterial {
    let mut v = [root, up];
    if let Ok(env) = std::env::var("FOREST_GRASSGRADE") {
        for (slot, s) in v.iter_mut().zip(env.split(',')) {
            if let Ok(x) = s.trim().parse() {
                *slot = x;
            }
        }
    }
    mat.extension.wind.wind.x = v[0];
    mat.extension.wind.tint.w = v[1];
    // Undergrowth: parts round passing legs and lies over where feet came down.
    mat.extension.wind.wind.y = 1.0;
    mat
}

/// Undergrowth chunks: thin out tuft by tuft over the last `band` units of their `VisibilityRange`
/// instead of popping (`foliage_wind_prepass.wesl`). The chunk's distance is measured from its
/// entity origin, so chunks using this must be centred on their AABB with `use_aabb: false`
/// (`realforest::spawn_group`). `FOREST_DISSOLVE=0` turns it off (A/B).
pub fn dissolve(mut mat: FoliageMaterial, band: f32) -> FoliageMaterial {
    let on = std::env::var("FOREST_DISSOLVE").map(|v| v != "0").unwrap_or(true);
    mat.extension.wind.tint.z = if on { band } else { 0.0 };
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
