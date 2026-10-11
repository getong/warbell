//! **Cloud sky** — a realistic cumulus / stratocumulus deck high above the island, replacing the
//! old low-poly icosphere puffs (which sat at y 42–80, right in front of the enlarged town's
//! build-mode camera).
//!
//! One camera-centred sphere drawn with [`CloudSkyMaterial`] (`assets/shaders/clouds.wgsl`):
//! the vertex stage re-centres it on the camera and pins it to the far plane, so it only ever
//! fills SKY pixels — it can't sit between any camera and the world, at any height. The fragment
//! stage ray-casts a virtual deck at [`DECK_HEIGHT`] and samples a baked tileable Perlin-Worley
//! texture (`assets/sky/cloud_noise.png`, `tools/bake_cloud_noise.py`), lit by the live
//! directional lights + ambient from the view uniform, so dawn / noon / dusk / moonlit night all
//! follow `scene::advance_sky` for free. Drift is `globals.time` in the shader.
//!
//! Static by design: the material and mesh are written ONCE at startup and never touched again
//! (per-frame material mutation was a big perf regression in the past), and there's no transform
//! system either — `NoFrustumCulling` + the vertex shader do the following.
//!
//! `FOREST_NOCLOUDS` skips it; it's tagged `CampaignOnly` so the RTS skirmish hides it.

use bevy::camera::visibility::NoFrustumCulling;
use bevy::light::{NotShadowCaster, NotShadowReceiver};
use bevy::mesh::MeshVertexBufferLayoutRef;
use bevy::pbr::{MaterialPipeline, MaterialPipelineKey};
use bevy::prelude::*;
use bevy::render::render_resource::{
    AsBindGroup, RenderPipelineDescriptor, ShaderType, SpecializedMeshPipelineError,
};
use bevy::shader::ShaderRef;

/// World height of the virtual cloud deck. Far above every camera: the build-mode cam tops out
/// around y≈100 for the grown town, the RTS ortho cam ≈86, FOREST_CAM overviews ≈150–250.
pub const DECK_HEIGHT: f32 = 650.0;
/// World size of one noise-texture tile on the deck (its base lobes come out ~250–400u across).
pub const DECK_TILE: f32 = 3400.0;
/// Wind across the deck, world units / second (≈ a 6 m/s breeze at the deck's scale — the
/// clouds visibly crawl but never race). Shared with the ground light patches.
pub const WIND: Vec2 = Vec2::new(5.2, 2.6);

/// Uniform block — field order must match `CloudParams` in `clouds.wgsl`.
#[derive(Clone, Copy, ShaderType)]
pub struct CloudParams {
    /// x deck height · y tile size · z coverage 0..1 · w max opacity.
    pub shape: Vec4,
    /// xy wind (u/s) · z detail tile size · w horizon fade distance.
    pub wind: Vec4,
}

#[derive(Asset, TypePath, AsBindGroup, Clone)]
pub struct CloudSkyMaterial {
    #[uniform(0)]
    pub params: CloudParams,
    #[texture(1)]
    #[sampler(2)]
    pub noise: Handle<Image>,
}

impl Material for CloudSkyMaterial {
    fn vertex_shader() -> ShaderRef {
        "shaders/clouds.wgsl".into()
    }
    fn fragment_shader() -> ShaderRef {
        "shaders/clouds.wgsl".into()
    }
    fn alpha_mode(&self) -> AlphaMode {
        AlphaMode::Blend
    }
    /// Sort first among transparents (view-space distance is negative in front, ascending =
    /// back-to-front): chimney smoke, sparks, banners against the sky all draw OVER the clouds.
    fn depth_bias(&self) -> f32 {
        -1.0e7
    }
    fn enable_prepass() -> bool {
        false
    }
    fn enable_shadows() -> bool {
        false
    }
    fn specialize(
        _pipeline: &MaterialPipeline,
        descriptor: &mut RenderPipelineDescriptor,
        _layout: &MeshVertexBufferLayoutRef,
        _key: MaterialPipelineKey<Self>,
    ) -> Result<(), SpecializedMeshPipelineError> {
        // The camera sits INSIDE the sphere: draw both faces.
        descriptor.primitive.cull_mode = None;
        if let Some(ds) = descriptor.depth_stencil.as_mut() {
            ds.depth_write_enabled = Some(false);
            ds.bias = default();
        }
        Ok(())
    }
}

pub struct CloudsPlugin;

impl Plugin for CloudsPlugin {
    fn build(&self, app: &mut App) {
        app.add_plugins(MaterialPlugin::<CloudSkyMaterial>::default())
            .add_systems(Startup, spawn_cloud_sky);
    }
}

fn noise_image() -> Option<Image> {
    let mut img = match crate::realforest::load::texture("sky/cloud_noise.png", false, None) {
        Ok(img) => img,
        Err(e) => {
            warn!("clouds: {e} — cloud sky disabled");
            return None;
        }
    };
    use bevy::image::{ImageAddressMode, ImageFilterMode, ImageSampler, ImageSamplerDescriptor};
    // Trilinear + anisotropic: the deck is seen at grazing angles toward the horizon.
    img.sampler = ImageSampler::Descriptor(ImageSamplerDescriptor {
        address_mode_u: ImageAddressMode::Repeat,
        address_mode_v: ImageAddressMode::Repeat,
        address_mode_w: ImageAddressMode::Repeat,
        mag_filter: ImageFilterMode::Linear,
        min_filter: ImageFilterMode::Linear,
        mipmap_filter: ImageFilterMode::Linear,
        anisotropy_clamp: 8,
        ..default()
    });
    Some(img)
}

fn spawn_cloud_sky(
    mut commands: Commands,
    mut meshes: ResMut<Assets<Mesh>>,
    mut images: ResMut<Assets<Image>>,
    mut mats: ResMut<Assets<CloudSkyMaterial>>,
) {
    if std::env::var("FOREST_NOCLOUDS").is_ok() {
        return;
    }
    let Some(img) = noise_image() else { return };
    let coverage = std::env::var("FOREST_CLOUDCOVER")
        .ok()
        .and_then(|s| s.trim().parse::<f32>().ok())
        .unwrap_or(0.46);
    let mat = mats.add(CloudSkyMaterial {
        params: CloudParams {
            shape: Vec4::new(DECK_HEIGHT, DECK_TILE, coverage, 0.97),
            wind: Vec4::new(WIND.x, WIND.y, DECK_TILE * 0.21, 7000.0),
        },
        noise: images.add(img),
    });
    commands.spawn((
        Mesh3d(meshes.add(Sphere::new(1.0).mesh().uv(48, 24))),
        MeshMaterial3d(mat),
        Transform::default(),
        NoFrustumCulling,
        NotShadowCaster,
        NotShadowReceiver,
        crate::game_state::CampaignOnly,
        Name::new("CloudSky"),
    ));
}
