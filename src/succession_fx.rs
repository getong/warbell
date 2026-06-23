//! **Succession visuals** — the soul wisp + the rise flash. When the blade passes (the succession
//! beat in `succession::drive_succession`), [`HeirFell`] flies a glowing spirit from the fallen
//! body into the townsperson being possessed over [`SOUL_DUR`], and [`HeirRose`] pops a bright
//! flash where the new hero stands up. (No grave is planted — the player asked for none.)

use bevy::prelude::*;

use crate::game_state::AppState;

/// Spirit travel time, body → heir. Short: the whole succession beat runs in slow-motion, so this
/// is in *virtual* seconds and the wisp covers its arc within the slowed window (lands ~as the
/// rise flash pops). Tune alongside `succession`'s `TRANSFORM_T` / `SLOW_SPEED`.
const SOUL_DUR: f32 = 0.5;
/// Apex height of the wisp's arc (world units).
const SOUL_ARC: f32 = 1.6;
/// Rise-flash lifetime (virtual secs) — a quick grow-and-fade burst at the possession point.
const FLASH_DUR: f32 = 0.42;

/// Emitted by `succession::drive_succession` when the hero falls: launches the soul wisp from the
/// corpse toward the townsperson about to be possessed.
#[derive(Message, Clone, Copy)]
pub struct HeirFell {
    /// Where the fallen hero lies (the wisp launches here).
    pub grave_at: Vec3,
    /// Where the next heir rises (the wisp flies here).
    pub rise_at: Vec3,
}

/// Emitted by `succession::drive_succession` at the transform instant: pops a flash of light where
/// the peasant stands up as the new hero.
#[derive(Message, Clone, Copy)]
pub struct HeirRose {
    pub at: Vec3,
}

#[derive(Component)]
struct SoulWisp {
    from: Vec3,
    to: Vec3,
    /// Elapsed-seconds the flight started.
    born: f32,
}

/// The possession flash. Owns a per-instance material so its emissive/alpha can fade independently
/// (deaths are rare, so the one-off allocation is fine).
#[derive(Component)]
struct RiseFlash {
    born: f32,
    mat: Handle<StandardMaterial>,
}

/// Shared baked handles so the spawn path needs only `Commands` + this resource.
#[derive(Resource)]
struct FxAssets {
    wisp_mesh: Handle<Mesh>,
    wisp_mat: Handle<StandardMaterial>,
}

pub struct SuccessionFxPlugin;

impl Plugin for SuccessionFxPlugin {
    fn build(&self, app: &mut App) {
        app.add_message::<HeirFell>()
            .add_message::<HeirRose>()
            .add_systems(Startup, setup_fx_assets)
            .add_systems(Update, (spawn_succession_fx, drive_souls, spawn_rise_fx, drive_rise_flash))
            .add_systems(OnExit(AppState::StartScreen), clear_wisps)
            .add_systems(OnExit(AppState::GameOver), clear_wisps);
        // (Pause-menu Restart resets in-process via StartScreen → Playing — see
        // game_state::drive_fresh_run — so this OnExit(StartScreen) clear covers it.)
    }
}


fn setup_fx_assets(
    mut commands: Commands,
    mut meshes: ResMut<Assets<Mesh>>,
    mut materials: ResMut<Assets<StandardMaterial>>,
) {
    // Warm, unlit, brightly-emissive spirit — reads as a glowing wisp (bloom catches it).
    let wisp_mat = materials.add(StandardMaterial {
        base_color: Color::srgb(1.0, 0.85, 0.55),
        emissive: LinearRgba::rgb(3.0, 2.2, 1.0),
        unlit: true,
        ..default()
    });
    commands.insert_resource(FxAssets {
        wisp_mesh: meshes.add(Sphere::new(0.2).mesh().ico(3).unwrap()),
        wisp_mat,
    });
}

/// On each fallen heir: launch a soul wisp from the body toward the rising heir.
fn spawn_succession_fx(
    time: Res<Time>,
    mut fell: MessageReader<HeirFell>,
    assets: Option<Res<FxAssets>>,
    mut commands: Commands,
) {
    let Some(assets) = assets else { return };
    let now = time.elapsed_secs();
    for ev in fell.read() {
        commands.spawn((
            Mesh3d(assets.wisp_mesh.clone()),
            MeshMaterial3d(assets.wisp_mat.clone()),
            Transform::from_translation(ev.grave_at + Vec3::Y),
            SoulWisp { from: ev.grave_at + Vec3::Y, to: ev.rise_at + Vec3::Y, born: now },
        ));
    }
}

/// Ease the wisp along a parabolic arc from body to heir; flicker its scale; despawn on arrival.
fn drive_souls(time: Res<Time>, mut commands: Commands, mut q: Query<(Entity, &SoulWisp, &mut Transform)>) {
    let now = time.elapsed_secs();
    for (e, soul, mut tf) in &mut q {
        let t = ((now - soul.born) / SOUL_DUR).clamp(0.0, 1.0);
        if t >= 1.0 {
            commands.entity(e).try_despawn();
            continue;
        }
        let e_t = t * t * (3.0 - 2.0 * t); // smoothstep
        let mut p = soul.from.lerp(soul.to, e_t);
        p.y += (t * std::f32::consts::PI).sin() * SOUL_ARC; // arc apex mid-flight
        tf.translation = p;
        let flick = 0.85 + (now * 22.0).sin() * 0.12;
        tf.scale = Vec3::splat((0.7 + (t * std::f32::consts::PI).sin() * 0.5) * flick);
    }
}

/// On the rise: pop a bright flash at the possession point — the peasant becomes the knight.
fn spawn_rise_fx(
    time: Res<Time>,
    mut rose: MessageReader<HeirRose>,
    assets: Option<Res<FxAssets>>,
    mut materials: ResMut<Assets<StandardMaterial>>,
    mut commands: Commands,
) {
    let Some(assets) = assets else { return };
    let now = time.elapsed_secs();
    for ev in rose.read() {
        // Fresh material per flash so it can fade its own emissive/alpha (see `RiseFlash`).
        let mat = materials.add(StandardMaterial {
            base_color: Color::srgb(1.0, 0.96, 0.82),
            emissive: LinearRgba::rgb(7.0, 6.0, 3.6),
            unlit: true,
            alpha_mode: AlphaMode::Blend,
            ..default()
        });
        commands.spawn((
            Mesh3d(assets.wisp_mesh.clone()),
            MeshMaterial3d(mat.clone()),
            Transform::from_translation(ev.at + Vec3::Y * 0.9).with_scale(Vec3::splat(0.3)),
            RiseFlash { born: now, mat },
        ));
    }
}

/// Grow the flash outward and fade it (emissive + alpha) over [`FLASH_DUR`]; despawn on finish.
fn drive_rise_flash(
    time: Res<Time>,
    mut commands: Commands,
    mut materials: ResMut<Assets<StandardMaterial>>,
    mut q: Query<(Entity, &RiseFlash, &mut Transform)>,
) {
    let now = time.elapsed_secs();
    for (e, flash, mut tf) in &mut q {
        let t = ((now - flash.born) / FLASH_DUR).clamp(0.0, 1.0);
        if t >= 1.0 {
            commands.entity(e).try_despawn();
            continue;
        }
        tf.scale = Vec3::splat(0.3 + t * 2.8); // burst outward
        if let Some(mut m) = materials.get_mut(&flash.mat) {
            let a = (1.0 - t) * (1.0 - t); // ease-out fade
            m.base_color = m.base_color.with_alpha(a);
            let g = 7.0 * a;
            m.emissive = LinearRgba::rgb(g, g * 0.85, g * 0.5);
        }
    }
}

fn clear_wisps(mut commands: Commands, fx: Query<Entity, Or<(With<SoulWisp>, With<RiseFlash>)>>) {
    for e in &fx {
        commands.entity(e).try_despawn();
    }
}
