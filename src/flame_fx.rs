//! **Flame cards** — a real-looking open flame for braziers and fire baskets.
//!
//! The old braziers capped their bowls with an emissive sphere/cone, which read as a glowing egg.
//! A [`Flame`] is instead three crossed vertical cards (60° apart) carrying a procedurally painted
//! flame image — ragged licking tongues, a white-yellow core fading through orange to a dark red
//! rim — drawn additively and unlit so it blooms. Two nested flames (a tall outer one and a
//! small hot inner one, rotated against each other) are spawned per fire by [`flame_children`].
//!
//! Animation is transform-only (scale pulse, sway, slow turn) — no asset is mutated per frame.
//! Spawn a child entity with [`flame_bundle`] (or [`flame_children`]); [`attach_flame_meshes`]
//! fills in the shared mesh + material on the next frame, so callers need no extra resources.

use bevy::asset::RenderAssetUsages;
use bevy::image::{ImageAddressMode, ImageFilterMode, ImageSampler, ImageSamplerDescriptor};
use bevy::light::NotShadowCaster;
use bevy::mesh::{Indices, PrimitiveTopology};
use bevy::prelude::*;
use bevy::render::render_resource::{Extent3d, TextureDimension, TextureFormat};

/// One flame (size = height in world units; base at the entity origin).
#[derive(Component, Clone, Copy)]
pub struct Flame {
    pub size: f32,
    pub phase: f32,
}

#[derive(Resource)]
struct FlameAssets {
    mesh: Handle<Mesh>,
    mat: Handle<StandardMaterial>,
}

pub struct FlameFxPlugin;

impl Plugin for FlameFxPlugin {
    fn build(&self, app: &mut App) {
        app.add_systems(Startup, setup_flame_assets).add_systems(Update, (attach_flame_meshes, flicker_flames));
    }
}

/// A flame entity's components (local position `at`, height `size`).
pub fn flame_bundle(at: Vec3, size: f32, phase: f32) -> impl Bundle {
    (
        Transform::from_translation(at).with_scale(Vec3::splat(size)),
        Visibility::Inherited,
        Flame { size, phase },
        NotShadowCaster,
    )
}

/// Spawn the two nested flames of one fire as children of `parent` (base at local `at`).
pub fn flame_children(commands: &mut Commands, parent: Entity, at: Vec3, size: f32, phase: f32) {
    commands.entity(parent).with_children(|c| {
        c.spawn(flame_bundle(at, size, phase));
        c.spawn(flame_bundle(at + Vec3::Y * 0.02, size * 0.62, phase + 1.7));
    });
}

fn smooth(e0: f32, e1: f32, x: f32) -> f32 {
    let t = ((x - e0) / (e1 - e0)).clamp(0.0, 1.0);
    t * t * (3.0 - 2.0 * t)
}

/// Paint the flame image: x across (−1..1), y up (0 bottom). Tongues from summed sines.
fn flame_image() -> Image {
    const W: usize = 64;
    const H: usize = 128;
    let mut px = vec![0u8; W * H * 4];
    for j in 0..H {
        let v = 1.0 - (j as f32 + 0.5) / H as f32; // image rows run top-down
        for i in 0..W {
            let u = (i as f32 + 0.5) / W as f32 * 2.0 - 1.0;
            // Body: a teardrop that widens just above the base and licks to a point.
            let body = (v * 3.2).min(1.0).powf(0.5) * (1.0 - v).powf(0.85) * 0.92;
            // Tongues: the outline wobbles with height, more toward the top.
            let wob = 0.18 * v * ((v * 13.0 + u * 2.0).sin() + 0.6 * (v * 23.0 - 1.3).sin());
            let side = (u - wob * 0.6).abs();
            let w = body * (1.0 + 0.35 * (v * 17.0 + u * 5.0).sin() * v);
            let d = if w > 1e-3 { 1.0 - side / w } else { -1.0 };
            // Split tips: a darker notch through the upper middle.
            let notch = smooth(0.5, 0.9, v) * (1.0 - smooth(0.0, 0.25, (u - 0.25 * (v * 9.0).sin()).abs())) * 0.5;
            let a = (smooth(0.0, 0.35, d) * (1.0 - smooth(0.82, 1.0, v)) * (1.0 - notch)).clamp(0.0, 1.0);
            let core = smooth(0.45, 0.9, d) * (1.0 - smooth(0.25, 0.7, v));
            let mid = smooth(0.1, 0.55, d);
            let (r, g, b) = (
                0.75 + 0.25 * mid,
                0.16 + 0.42 * mid + 0.37 * core,
                0.03 + 0.07 * mid + 0.55 * core,
            );
            let o = (j * W + i) * 4;
            px[o] = (r * 255.0) as u8;
            px[o + 1] = (g * 255.0) as u8;
            px[o + 2] = (b * 255.0) as u8;
            px[o + 3] = (a * 255.0) as u8;
        }
    }
    let mut img = Image::new(
        Extent3d { width: W as u32, height: H as u32, depth_or_array_layers: 1 },
        TextureDimension::D2,
        px,
        TextureFormat::Rgba8UnormSrgb,
        RenderAssetUsages::default(),
    );
    img.sampler = ImageSampler::Descriptor(ImageSamplerDescriptor {
        address_mode_u: ImageAddressMode::ClampToEdge,
        address_mode_v: ImageAddressMode::ClampToEdge,
        mag_filter: ImageFilterMode::Linear,
        min_filter: ImageFilterMode::Linear,
        ..default()
    });
    img
}

/// Three crossed unit cards (height 1, width 0.62), base at y=0.
fn flame_mesh() -> Mesh {
    let mut pos = Vec::new();
    let mut nrm = Vec::new();
    let mut uv = Vec::new();
    let mut idx: Vec<u32> = Vec::new();
    for k in 0..3 {
        let a = k as f32 * std::f32::consts::PI / 3.0;
        let (s, c) = a.sin_cos();
        let hw = 0.31;
        let base = pos.len() as u32;
        for (x, y, uu, vv) in [(-hw, 0.0, 0.0, 1.0), (hw, 0.0, 1.0, 1.0), (hw, 1.0, 1.0, 0.0), (-hw, 1.0, 0.0, 0.0)] {
            pos.push([x * c, y, x * s]);
            nrm.push([-s, 0.0, c]);
            uv.push([uu, vv]);
        }
        idx.extend_from_slice(&[base, base + 1, base + 2, base, base + 2, base + 3]);
    }
    Mesh::new(PrimitiveTopology::TriangleList, RenderAssetUsages::default())
        .with_inserted_attribute(Mesh::ATTRIBUTE_POSITION, pos)
        .with_inserted_attribute(Mesh::ATTRIBUTE_NORMAL, nrm)
        .with_inserted_attribute(Mesh::ATTRIBUTE_UV_0, uv)
        .with_inserted_indices(Indices::U32(idx))
}

fn setup_flame_assets(
    mut commands: Commands,
    mut meshes: ResMut<Assets<Mesh>>,
    mut images: ResMut<Assets<Image>>,
    mut materials: ResMut<Assets<StandardMaterial>>,
) {
    let tex = images.add(flame_image());
    let mat = materials.add(StandardMaterial {
        base_color: Color::LinearRgba(LinearRgba::rgb(3.2, 2.3, 1.6)),
        base_color_texture: Some(tex),
        unlit: true,
        alpha_mode: AlphaMode::Add,
        double_sided: true,
        cull_mode: None,
        fog_enabled: true,
        ..default()
    });
    commands.insert_resource(FlameAssets { mesh: meshes.add(flame_mesh()), mat });
}

fn attach_flame_meshes(mut commands: Commands, assets: Option<Res<FlameAssets>>, q: Query<Entity, Added<Flame>>) {
    let Some(a) = assets else { return };
    for e in &q {
        commands.entity(e).insert((Mesh3d(a.mesh.clone()), MeshMaterial3d(a.mat.clone())));
    }
}

/// Lick + sway: height pulses fast and irregularly, width breathes slower, the cards turn so the
/// tongues never repeat the same silhouette.
fn flicker_flames(time: Res<Time>, mut q: Query<(&Flame, &mut Transform)>) {
    let t = time.elapsed_secs();
    for (f, mut tf) in &mut q {
        let p = f.phase;
        let h = 1.0 + 0.16 * (t * 11.0 + p).sin() + 0.09 * (t * 17.3 + p * 2.1).sin() + 0.05 * (t * 29.0 + p).sin();
        let w = 1.0 + 0.08 * (t * 6.1 + p * 1.3).sin();
        tf.scale = Vec3::new(f.size * w, f.size * h, f.size * w);
        tf.rotation = Quat::from_rotation_y(t * 0.7 + p) *
            Quat::from_rotation_z(0.06 * (t * 3.1 + p).sin()) *
            Quat::from_rotation_x(0.05 * (t * 2.3 + p * 0.7).sin());
    }
}
