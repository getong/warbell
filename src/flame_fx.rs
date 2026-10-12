//! **Flame cards** — the ONE flame system for every open fire in the game: camp fires, the meadow
//! rest fire, gate braziers and fire baskets, burning plots, ork and trailer torches.
//!
//! A flame is two nested sets of three crossed vertical cards (60° apart) carrying a painted flame
//! image (four licking tongues over a hot root, white-yellow core, orange then deep red at the
//! ragged edges), unlit and HDR-bright so it blooms, never a solid cone or egg. The texture is a
//! fixed-id handle ([`FLAME_CARD_TEX`]) so any builder can call [`flame_card_material`] /
//! [`flame_card_mesh`] without an `Assets<Image>`. For a simple fire, spawn [`flame_bundle`] (or
//! [`flame_children`]) and the shared mesh + material + a lick/sway flicker are filled in here.
//!
//! Animation is transform-only (scale pulse, sway, slow turn) — no asset is mutated per frame.
//! Spawn a child entity with [`flame_bundle`] (or [`flame_children`]); [`attach_flame_meshes`]
//! fills in the shared mesh + material on the next frame, so callers need no extra resources.

use bevy::light::NotShadowCaster;
use bevy::prelude::*;

/// One flame (`size` scales the 0.95 u-tall card set; base at the entity origin).
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
        app.add_systems(PreStartup, insert_flame_card_tex)
            .add_systems(Startup, setup_flame_assets).add_systems(Update, (attach_flame_meshes, flicker_flames));
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

/// Spawn one fire's flame cards as a child of `parent` (base at local `at`), so the flame shares
/// the parent's visibility / reveal lifecycle.
pub fn flame_children(commands: &mut Commands, parent: Entity, at: Vec3, size: f32, phase: f32) {
    commands.entity(parent).with_children(|c| {
        c.spawn(flame_bundle(at, size, phase));
    });
}

/// The shared painted flame texture of every flame card (camp fires, the meadow fire, ork torches,
/// the trailer torches): a fixed-id handle, filled once at startup ([`insert_flame_card_tex`], registered by [`FlameFxPlugin`]), so
/// any builder can make a flame material without an `Assets<Image>`.
pub(crate) const FLAME_CARD_TEX: Handle<Image> = bevy::asset::uuid_handle!("6b1f0c52-3c8e-4d4f-9a51-2f7e0b9d4a11");

pub(crate) fn insert_flame_card_tex(mut images: ResMut<Assets<Image>>) {
    let _ = images.insert(&FLAME_CARD_TEX, flame_card_image());
}

/// The flame cards' material: the painted flame, HDR-bright (blooms), alpha-blended, unlit,
/// double-sided, never a solid cone.
pub(crate) fn flame_card_material(materials: &mut Assets<StandardMaterial>) -> Handle<StandardMaterial> {
    materials.add(StandardMaterial {
        base_color: Color::linear_rgb(5.0, 2.6, 1.1),
        base_color_texture: Some(FLAME_CARD_TEX),
        alpha_mode: AlphaMode::Blend,
        unlit: true,
        double_sided: true,
        cull_mode: None,
        ..default()
    })
}

/// Flame cards: three vertical quads crossed at 60° plus a smaller inner set, `size` x (0.75 wide
/// x 0.95 tall — a camp fire; ~0.3 is a torch), base at y=0, UV v=1 at the base (the flame root).
/// Spawn with `bevy::light::NotShadowCaster`.
pub(crate) fn flame_card_mesh(size: f32) -> Mesh {
    use bevy::asset::RenderAssetUsages;
    use bevy::mesh::{Indices, PrimitiveTopology};
    let (mut pos, mut uv, mut nrm, mut idx) = (Vec::new(), Vec::new(), Vec::new(), Vec::new());
    for (w, h, phase) in [(0.75 * size, 0.95 * size, 0.0_f32), (0.42 * size, 0.62 * size, 0.5)] {
        for k in 0..3 {
            let a = phase + k as f32 * std::f32::consts::FRAC_PI_3;
            let d = Vec3::new(a.cos(), 0.0, a.sin()) * (w / 2.0);
            let n = Vec3::new(-a.sin(), 0.0, a.cos());
            let base = pos.len() as u32;
            for (p, t) in [(-d, [0.0, 1.0]), (d, [1.0, 1.0]), (d + Vec3::Y * h, [1.0, 0.0]), (-d + Vec3::Y * h, [0.0, 0.0])] {
                pos.push(p.to_array());
                uv.push(t);
                nrm.push(n.to_array());
            }
            idx.extend([base, base + 1, base + 2, base, base + 2, base + 3]);
        }
    }
    Mesh::new(PrimitiveTopology::TriangleList, RenderAssetUsages::default())
        .with_inserted_attribute(Mesh::ATTRIBUTE_POSITION, pos)
        .with_inserted_attribute(Mesh::ATTRIBUTE_NORMAL, nrm)
        .with_inserted_attribute(Mesh::ATTRIBUTE_UV_0, uv)
        .with_inserted_indices(Indices::U32(idx))
}

/// A painted flame (64x128 RGBA): three licking tongues over a hot root, white-yellow at the core,
/// orange then deep red at the ragged edges, soft alpha falloff — the card texture for the fire.
pub(crate) fn flame_card_image() -> Image {
    use bevy::asset::RenderAssetUsages;
    use bevy::render::render_resource::{Extent3d, TextureDimension, TextureFormat};
    let (w, h) = (64u32, 128u32);
    let mut data = Vec::with_capacity((w * h * 4) as usize);
    let sstep = |a: f32, b: f32, x: f32| {
        let t = ((x - a) / (b - a)).clamp(0.0, 1.0);
        t * t * (3.0 - 2.0 * t)
    };
    for y in 0..h {
        let v = 1.0 - y as f32 / (h - 1) as f32; // 0 root .. 1 tip
        for x in 0..w {
            let u = x as f32 / (w - 1) as f32 * 2.0 - 1.0;
            let mut heat = 0.0_f32;
            for (off, tall, sway) in [(0.0_f32, 1.0_f32, 0.0_f32), (-0.42, 0.7, 0.9), (0.4, 0.78, -0.7), (0.18, 0.52, 1.7)] {
                let vt = v / tall;
                if vt >= 1.0 {
                    continue;
                }
                let centre = off * (1.0 - vt * 0.6) + 0.12 * (vt * 6.0 + sway).sin() * vt;
                let half = (0.42 - (off.abs() * 0.25)) * (1.0 - vt).powf(0.75) * (0.75 + 0.25 * (1.0 - vt * vt));
                let d = ((u - centre).abs() / half.max(1e-3)).min(2.0);
                heat = heat.max((1.0 - d) * (1.0 - vt * 0.55));
            }
            heat *= sstep(0.0, 0.08, v); // the root sits in the embers
            let a = sstep(0.0, 0.35, heat);
            let core = sstep(0.35, 0.85, heat);
            let r = 1.0;
            let g = 0.25 + 0.65 * sstep(0.1, 0.7, heat);
            let b = 0.05 + 0.6 * core * core;
            data.extend([(r * 255.0) as u8, (g * 255.0) as u8, (b * 255.0) as u8, (a * 255.0) as u8]);
        }
    }
    Image::new(
        Extent3d { width: w, height: h, depth_or_array_layers: 1 },
        TextureDimension::D2,
        data,
        TextureFormat::Rgba8UnormSrgb,
        RenderAssetUsages::default(),
    )
}

fn setup_flame_assets(mut commands: Commands, mut meshes: ResMut<Assets<Mesh>>, mut materials: ResMut<Assets<StandardMaterial>>) {
    let mat = flame_card_material(&mut materials);
    commands.insert_resource(FlameAssets { mesh: meshes.add(flame_card_mesh(1.0)), mat });
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
