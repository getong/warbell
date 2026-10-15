//! **Footstep feedback** — the visual twin of [`audio::footsteps`](crate::audio). Each hero
//! [`Footfall`] (from [`crate::footing`], shared with the step sound and the boot prints) kicks up
//! a small puff of motes tinted by the surface underfoot (dust / sand / snow powder / mud clods;
//! nothing off grass, stone or planks). Wading the shallows swaps the puff for a splash + an
//! expanding ripple ring. Pure spawn-and-fade — the world answers your feet.
//!
//! Fades run **ungated** (like the combat sparks) so a frozen scene still settles its dust; the
//! emitter is gated on `Modal::None` so panels/pauses don't spawn steps.

use std::f32::consts::FRAC_PI_2;

use bevy::light::NotShadowCaster;
use bevy::prelude::*;

use crate::footing::{Footfall, FootfallSet, Stepper, Surface};
use crate::game_state::SimAppExt;
use crate::worldmap;

/// Downward pull on settling dust motes.
const GRAV: f32 = 6.0;

/// A kicked-up dust/splash mote — shrinks to nothing over its life (shared material, no per-mote
/// alpha, so thousands still batch).
#[derive(Component)]
struct Puff {
    vel: Vec3,
    life: f32,
    life0: f32,
    scale0: f32,
}

/// An expanding water ripple ring — grows + alpha-fades. Owns its material (cloned per spawn) so
/// the alpha fade is per-ring; the handle is freed on death to avoid leaking assets.
#[derive(Component)]
struct Ripple {
    life: f32,
    life0: f32,
    scale0: f32,
    scale1: f32,
    alpha0: f32,
    mat: Handle<StandardMaterial>,
}

/// Shared footstep-fx assets, built once. `puff` + `mortar` are crate-visible so
/// [`build_fx`](crate::build_fx) can reuse the mote pipeline for construction dust.
#[derive(Resource)]
pub(crate) struct FxAssets {
    pub(crate) puff: Handle<Mesh>,
    ring: Handle<Mesh>,
    dirt: Handle<StandardMaterial>,
    snow: Handle<StandardMaterial>,
    sand: Handle<StandardMaterial>,
    mud: Handle<StandardMaterial>,
    splash: Handle<StandardMaterial>,
    /// Pale stone/mortar dust — construction bursts (`build_fx`), not footfalls.
    pub(crate) mortar: Handle<StandardMaterial>,
}

pub struct FootstepFxPlugin;

impl Plugin for FootstepFxPlugin {
    fn build(&self, app: &mut App) {
        app.add_systems(Startup, setup)
            .add_sim_systems(emit.after(FootfallSet))
            // Fades are visual — keep settling even while frozen.
            .add_systems(Update, (fade_puffs, fade_ripples));
    }
}

fn setup(
    mut commands: Commands,
    mut meshes: ResMut<Assets<Mesh>>,
    mut materials: ResMut<Assets<StandardMaterial>>,
) {
    let mut mk = |c: Color, a: f32| {
        materials.add(StandardMaterial {
            base_color: c.with_alpha(a),
            unlit: true,
            alpha_mode: AlphaMode::Blend,
            cull_mode: None,
            ..default()
        })
    };
    commands.insert_resource(FxAssets {
        puff: meshes.add(Sphere::new(0.12).mesh().ico(1).unwrap()),
        // Authored flat in XY (z=0) — laid into the ground plane with a -90° X tilt at spawn.
        ring: meshes.add(Annulus::new(0.5, 0.53).mesh().resolution(48).build()),
        dirt: mk(Color::srgb(0.62, 0.50, 0.34), 0.7),
        snow: mk(Color::srgb(0.95, 0.97, 1.0), 0.85),
        sand: mk(Color::srgb(0.80, 0.70, 0.52), 0.6),
        mud: mk(Color::srgb(0.24, 0.19, 0.13), 0.9),
        splash: mk(Color::srgb(0.86, 0.92, 0.98), 0.55),
        mortar: mk(Color::srgb(0.74, 0.68, 0.56), 0.75),
    });
}

/// The kicked-up mote material for a surface; `None` = the step throws nothing (grass blades,
/// hard stone / planks — the step SOUND carries those).
fn surf_mat(fx: &FxAssets, s: Surface) -> Option<Handle<StandardMaterial>> {
    match s {
        Surface::Dirt => Some(fx.dirt.clone()),
        Surface::Sand => Some(fx.sand.clone()),
        Surface::Snow => Some(fx.snow.clone()),
        Surface::Mud => Some(fx.mud.clone()),
        Surface::Water => Some(fx.splash.clone()),
        Surface::Grass | Surface::Wood | Surface::Stone => None,
    }
}

/// Per hero [`Footfall`] (from [`crate::footing`]): a puff of the surface's motes, a splash +
/// ripple ring in the shallows, a fatter burst on a real **landing**, and sprint footfalls that
/// throw more, faster dust trailing behind the travel. NPC footfalls kick nothing (prints + sound
/// only) to keep a crowd cheap.
fn emit(
    mut steps: MessageReader<Footfall>,
    mut commands: Commands,
    fx: Option<Res<FxAssets>>,
    mut materials: ResMut<Assets<StandardMaterial>>,
) {
    let Some(fx) = fx else {
        steps.clear();
        return;
    };
    for f in steps.read() {
        let p = f.at;
        match f.who {
            Stepper::Npc { .. } => continue,
            Stepper::HeroLanding { fall } => {
                // Scaled by fall height; even grass / stone thump up a little grit on a big drop.
                let k = ((fall - 0.6) / 3.0).clamp(0.0, 1.0);
                let mat = surf_mat(&fx, f.surface).unwrap_or_else(|| fx.dirt.clone());
                spawn_puffs(&mut commands, &fx.puff, &mat, p, 7 + (k * 9.0) as u32, 1.4 + k * 1.8, 0.9 + k * 0.4, 0.0);
                continue;
            }
            Stepper::Hero => {}
        }
        if f.surface == Surface::Water {
            // Wading: a spray of fine droplets + a thin ring spreading on the water plane.
            let n = 9 + (f.gait * 8.0) as u32;
            spawn_puffs(&mut commands, &fx.puff, &fx.splash, p, n, 1.5 + f.gait * 1.4, 0.24 + f.gait * 0.1, 0.0);
            let mat = materials.add(StandardMaterial {
                base_color: Color::srgb(0.85, 0.92, 1.0).with_alpha(0.28),
                unlit: true,
                alpha_mode: AlphaMode::Blend,
                cull_mode: None,
                ..default()
            });
            // On the water plane itself: where the ring runs up the bank the terrain hides it.
            let water_y = worldmap::SEA_Y + 0.015;
            commands.spawn((
                Mesh3d(fx.ring.clone()),
                MeshMaterial3d(mat.clone()),
                Transform::from_translation(Vec3::new(p.x, water_y, p.z))
                    .with_rotation(Quat::from_rotation_x(-FRAC_PI_2))
                    .with_scale(Vec3::splat(0.2)),
                Ripple { life: 0.9, life0: 0.9, scale0: 0.2, scale1: 1.7, alpha0: 0.28, mat },
                NotShadowCaster,
            ));
            continue;
        }
        let Some(mat) = surf_mat(&fx, f.surface) else { continue };
        // Sprinting (gait → 1) throws more, faster dust, kicked back behind the TRAVEL (velocity,
        // not facing — a strafing combat stance would otherwise trail dust sideways). Mud throws
        // a few heavy clods low instead of a drifting puff.
        let run = f.gait;
        let kick = p - Vec3::new(f.dir.x, 0.0, f.dir.y) * (0.22 * run);
        let (n, spd, sc) = match f.surface {
            Surface::Mud => (2 + (run * 3.0) as u32, 0.7 + run * 1.0, 0.45 + run * 0.15),
            Surface::Snow => (3 + (run * 4.0) as u32, 1.0 + run * 1.6, 0.6 + run * 0.3),
            _ => (3 + (run * 3.0) as u32, 1.1 + run * 1.6, 0.65 + run * 0.25),
        };
        spawn_puffs(&mut commands, &fx.puff, &mat, kick, n, spd, sc, 0.0);
    }
}

/// Fling `n` motes outward + up from `at` (golden-angle spread), each shrinking over its life.
/// `radius` offsets each mote's start along its own fling direction — 0 for footfalls (open
/// ground under the hero), the footprint half-width for construction dust (motes born at a
/// building's centre die unseen inside its mesh).
/// Crate-visible: `build_fx` borrows it for construction dust ([`fade_puffs`] settles those too).
pub(crate) fn spawn_puffs(
    commands: &mut Commands,
    mesh: &Handle<Mesh>,
    mat: &Handle<StandardMaterial>,
    at: Vec3,
    n: u32,
    spd: f32,
    scale0: f32,
    radius: f32,
) {
    for i in 0..n {
        let a = i as f32 * 2.399_963_2; // golden angle
        let dir = Vec3::new(a.cos(), 0.0, a.sin());
        let mag = 0.5 + (i % 5) as f32 * 0.12;
        let vel = dir * spd * mag + Vec3::Y * (0.6 + (i % 3) as f32 * 0.25);
        let life = 0.4 + (i % 3) as f32 * 0.06;
        commands.spawn((
            Mesh3d(mesh.clone()),
            MeshMaterial3d(mat.clone()),
            Transform::from_translation(at + dir * radius + Vec3::Y * 0.08)
                .with_scale(Vec3::splat(scale0)),
            Puff { vel, life, life0: life, scale0 },
            NotShadowCaster,
        ));
    }
}

/// Drift + settle each puff, shrink to zero, reap at end of life.
fn fade_puffs(time: Res<Time>, mut commands: Commands, mut q: Query<(Entity, &mut Puff, &mut Transform)>) {
    let dt = time.delta_secs();
    for (e, mut pf, mut tf) in &mut q {
        pf.life -= dt;
        if pf.life <= 0.0 {
            commands.entity(e).try_despawn();
            continue;
        }
        pf.vel.y -= GRAV * dt;
        let v = pf.vel;
        tf.translation += v * dt;
        let t = (pf.life / pf.life0).clamp(0.0, 1.0);
        tf.scale = Vec3::splat(pf.scale0 * t);
    }
}

/// Grow each ripple outward, fade its (owned) material's alpha, free the material + reap at end.
fn fade_ripples(
    time: Res<Time>,
    mut commands: Commands,
    mut materials: ResMut<Assets<StandardMaterial>>,
    mut q: Query<(Entity, &mut Ripple, &mut Transform)>,
) {
    let dt = time.delta_secs();
    for (e, mut r, mut tf) in &mut q {
        r.life -= dt;
        let t = (r.life / r.life0).clamp(0.0, 1.0); // 1 → 0
        let grow = 1.0 - t;
        tf.scale = Vec3::splat(r.scale0 + (r.scale1 - r.scale0) * grow);
        if let Some(mut m) = materials.get_mut(&r.mat) {
            let c = m.base_color;
            m.base_color = c.with_alpha(r.alpha0 * t);
        }
        if r.life <= 0.0 {
            materials.remove(&r.mat);
            commands.entity(e).try_despawn();
        }
    }
}
