//! Extra visual polish + the live-tunable state behind the Debug panel's "Render" section.
//!
//! Adds two things on top of the existing pipeline (camera post-fx lives in `scene.rs`):
//!   * drifting **pollen / dust motes** that catch the light — "living air";
//!   * a global **prop specular** tweak (roughness / reflectance) so the matte low-poly
//!     props pick up a little form-giving highlight.
//!
//! Tunables live in [`VisualSettings`]; the Debug panel mutates it and
//! [`apply_visual_settings`] pushes the pollen-glow + prop-specular changes onto the
//! materials. Colour-grade + exposure are mutated directly on their live components by the
//! panel.

use bevy::light::NotShadowCaster;
use bevy::prelude::*;

const POLLEN_COUNT: usize = 60;
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
    /// Master bloom multiplier. `advance_sky` computes a per-biome/per-time bloom each frame and
    /// scales it by this, so the F1 panel's bloom slider STICKS (writing `Bloom::intensity` directly
    /// would be stomped next frame by that drive). 1.0 = the authored amount, 0 = off.
    pub bloom: f32,
}

impl Default for VisualSettings {
    fn default() -> Self {
        Self {
            pollen_glow: 3.5,
            pollen_speed: 1.0,
            prop_roughness: 0.62,
            prop_reflectance: 0.50,
            bloom: 1.0,
        }
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
            .add_plugins(crate::clouds::CloudsPlugin)
            .add_systems(Startup, spawn_pollen)
            .add_systems(Update, (drift_pollen, apply_visual_settings));
    }
}

// The cloud sky (a realistic high deck, replacing the old low-poly icosphere puffs) lives in
// `crate::clouds`; this plugin installs it since the clouds were always part of the visual layer.

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
        if let Some(mut m) = mats.get_mut(&pm.0) {
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
            // White, opaque, non-emissive prop mats only (skips emissive glow mats, wisps =
            // unlit, tinted set-pieces = non-white). Textured PBR mats (the `realforest` kit) are
            // left alone: their roughness lives in a texture and the scalar is its multiplier.
            (white && !m.unlit && m.emissive == LinearRgba::BLACK && m.base_color_texture.is_none()).then_some(id)
        })
        .collect();
    for id in ids {
        if let Some(mut m) = mats.get_mut(id) {
            m.perceptual_roughness = settings.prop_roughness;
            m.reflectance = settings.prop_reflectance;
        }
    }
}
