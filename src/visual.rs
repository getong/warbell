//! Extra visual polish + the live-tunable state behind the Debug panel's "Render" section.
//!
//! Adds three things on top of the existing pipeline (camera post-fx lives in `scene.rs`):
//!   * a big **`FogVolume`** region so the sun (a `VolumetricLight`) casts god-rays /
//!     light-shafts through gaps in the canopy (the camera carries `VolumetricFog`);
//!   * drifting **pollen / dust motes** that catch the light — "living air", great with the
//!     volumetrics;
//!   * a global **prop specular** tweak (roughness / reflectance) so the matte low-poly
//!     props pick up a little form-giving highlight.
//!
//! Tunables live in [`VisualSettings`]; the Debug panel mutates it and
//! [`apply_visual_settings`] pushes the pollen-glow + prop-specular changes onto the
//! materials. The `FogVolume`, camera `VolumetricFog`, CAS, colour-grade and exposure are
//! mutated directly on their live components by the panel.

use bevy::light::{FogVolume, NotShadowCaster};
use bevy::prelude::*;

const POLLEN_COUNT: usize = 150;
const TAU: f32 = std::f32::consts::TAU;
/// Warm pollen glow colour (sRGB → linear in the emissive so bloom catches it).
const POLLEN_TINT: Color = Color::srgb(1.0, 0.93, 0.7);

/// Live-tunable visual knobs not owned by a single Bevy component (driven by the panel).
#[derive(Resource)]
pub struct VisualSettings {
    /// Pollen emissive strength (0 = invisible motes).
    pub pollen_glow: f32,
    /// Pollen drift speed multiplier.
    pub pollen_speed: f32,
    /// Roughness pushed onto the white prop materials (lower = glossier).
    pub prop_roughness: f32,
    /// Reflectance pushed onto the white prop materials (specular strength).
    pub prop_reflectance: f32,
}

impl Default for VisualSettings {
    fn default() -> Self {
        Self { pollen_glow: 2.5, pollen_speed: 1.0, prop_roughness: 0.85, prop_reflectance: 0.30 }
    }
}

/// Handle to the shared pollen material so the apply system can retune its glow.
#[derive(Resource)]
struct PollenMat(Handle<StandardMaterial>);

/// A drifting mote: bobs + wanders around its spawn point (deterministic per-mote phase).
#[derive(Component)]
struct Pollen {
    base: Vec3,
    phase: f32,
    speed: f32,
    bob: f32,
    drift: f32,
}

pub struct VisualPlugin;

impl Plugin for VisualPlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<VisualSettings>()
            .add_systems(Startup, (spawn_fog_volume, spawn_pollen))
            .add_systems(Update, (drift_pollen, apply_visual_settings));
    }
}

/// One big box of uniform fog covering the play patch + the air above it. With a
/// `VolumetricLight` sun + the camera's `VolumetricFog`, the sun casts shafts through gaps
/// in the canopy. Density etc. are tuned live via the panel (`Query<&mut FogVolume>`).
fn spawn_fog_volume(mut commands: Commands) {
    commands.spawn((
        FogVolume {
            // Density is per-unit extinction, so it must stay TINY for a big box (a long view
            // ray through dense fog goes black — that includes rays to the sky). With this
            // ~70u box, ~0.006 gives subtle atmosphere; crank `vol density` (≤0.04) + `vol
            // scattering` in the Debug panel for dramatic god-rays toward a low sun.
            density_factor: 0.006,
            scattering: 0.6,
            absorption: 0.2,
            scattering_asymmetry: 0.80,
            ..default()
        },
        // Box just large enough to cover the 32×32 patch + margin (keeps view-ray path
        // lengths bounded so the fog stays subtle instead of blacking out the horizon).
        Transform::from_xyz(0.0, 8.0, 0.0).with_scale(Vec3::new(72.0, 30.0, 72.0)),
    ));
}

/// Scatter ~150 small unlit emissive motes across the patch, drifting slowly. Deterministic
/// placement (Mulberry32, no `random()`), persists across biome switches (not `BiomeEntity`).
fn spawn_pollen(
    mut commands: Commands,
    mut meshes: ResMut<Assets<Mesh>>,
    mut mats: ResMut<Assets<StandardMaterial>>,
) {
    let glow = VisualSettings::default().pollen_glow;
    let mesh = meshes.add(Sphere::new(0.03).mesh().ico(1).expect("ico detail in range"));
    let mat = mats.add(StandardMaterial {
        base_color: Color::srgb(1.0, 0.96, 0.8),
        emissive: LinearRgba::from(POLLEN_TINT) * glow,
        unlit: true,
        ..default()
    });

    let mut seed = 0x9e37_79b9_u32;
    let mut next = || {
        seed = seed.wrapping_add(0x6d2b_79f5);
        let mut t = seed;
        t = (t ^ (t >> 15)).wrapping_mul(t | 1);
        t ^= t.wrapping_add((t ^ (t >> 7)).wrapping_mul(t | 61));
        ((t ^ (t >> 14)) as f32) / 4_294_967_296.0
    };
    for _ in 0..POLLEN_COUNT {
        let x = -15.0 + next() * 30.0;
        let z = -15.0 + next() * 30.0;
        let y = 0.5 + next() * 3.2;
        commands.spawn((
            Mesh3d(mesh.clone()),
            MeshMaterial3d(mat.clone()),
            Transform::from_xyz(x, y, z),
            NotShadowCaster,
            Pollen {
                base: Vec3::new(x, y, z),
                phase: next() * TAU,
                speed: 0.2 + next() * 0.4,
                bob: 0.15 + next() * 0.3,
                drift: 0.2 + next() * 0.5,
            },
        ));
    }
    commands.insert_resource(PollenMat(mat));
}

/// Gentle independent bob + wander per mote, scaled by the live drift-speed knob.
fn drift_pollen(time: Res<Time>, settings: Res<VisualSettings>, mut q: Query<(&mut Transform, &Pollen)>) {
    let t = time.elapsed_secs() * settings.pollen_speed;
    for (mut tf, p) in &mut q {
        let ph = p.phase + t * p.speed;
        tf.translation.x = p.base.x + (ph * 0.6).sin() * p.drift;
        tf.translation.z = p.base.z + (ph * 0.8 + 1.1).cos() * p.drift;
        tf.translation.y = p.base.y + ph.sin() * p.bob;
    }
}

/// Push the panel's pollen-glow + prop-specular knobs onto the materials, only when they
/// actually change (so the GPU upload doesn't churn every frame).
fn apply_visual_settings(
    settings: Res<VisualSettings>,
    pollen_mat: Option<Res<PollenMat>>,
    mut mats: ResMut<Assets<StandardMaterial>>,
) {
    if !settings.is_changed() {
        return;
    }

    // Pollen glow.
    if let Some(pm) = pollen_mat {
        if let Some(m) = mats.get_mut(&pm.0) {
            m.emissive = LinearRgba::from(POLLEN_TINT) * settings.pollen_glow;
        }
    }

    // Prop specular — applied to the white, opaque, non-emissive prop materials (the
    // scatter / landmark `Color::WHITE` mats). Skips water/terrain (own material types),
    // wisps/fireflies/pollen (unlit), and tinted set-pieces (non-white base). Collect ids
    // first to release the immutable borrow before mutating.
    let ids: Vec<_> = mats
        .iter()
        .filter_map(|(id, m)| {
            let c = m.base_color.to_linear();
            let white = c.red > 0.85 && c.green > 0.85 && c.blue > 0.85;
            (white && !m.unlit).then_some(id)
        })
        .collect();
    for id in ids {
        if let Some(m) = mats.get_mut(id) {
            m.perceptual_roughness = settings.prop_roughness;
            m.reflectance = settings.prop_reflectance;
        }
    }
}
