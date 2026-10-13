//! Trailer **staged scenes** — hand-composed, looped tableaus the normal game never assembles, for
//! filming promo shots. The user flies their OWN free-cam (` toggles it); each scene only stages the
//! WORLD: it pins the time-of-day, spawns + poses actors (orks, villagers, the hero) and props at
//! fixed marks, and drives a small looped behaviour so the shot has motion. Fired from the F1 debug
//! panel's "🎬 Director → Scenes" row; one scene at a time.
//!
//! Six scenes (see [`SceneId`]):
//! * **WorkSite** — the hero stands arms-crossed, supervising, while peasants labour; one leans on a
//!   shovel. (Daylight.)
//! * **Mason** — the gag ("He laid three stones. Then he supervised."): a peasant at a half-built
//!   wall slowly sets three stones on the course, then steps back, clasps his hands behind his
//!   back, points and nods — supervising — while two labourers keep grinding beside him.
//! * **WallPatrol** — an ork archer outside the east wall looses a green bolt at the rampart on a
//!   loop, flanked by idle grunts — a ride-along-the-palisade shot.
//! * **OrksFlee** — comedic: a warband streams outward from their campfire in a panicked scatter.
//! * **NightSiege** — the hero on the north wall at night, the war bell beside him, torches lit, a
//!   horde flooding past toward the keep below.
//! * **BarrelPeek** — a peasant peeks out from behind a barrel while orks rampage through the yard.
//!
//! Scene actors carry [`SceneActor`] so the camp/wander brains leave them to this module; props carry
//! [`SceneProp`]. Both are torn down when the scene changes or clears.

use bevy::prelude::*;

use crate::orks::{Faction, OrkVariant};
use crate::siege::InvaderArmory;
use crate::meshkit::{merged_flat as merged, tinted_hex as tinted};

// ── Public tags ──────────────────────────────────────────────────────────────────────

/// An ork/villager driven by a staged scene — excluded from the camp/wander brains (see the
/// `Without<SceneActor>` filters in `orks.rs`, `villagers.rs`) so this module owns its motion.
#[derive(Component)]
pub struct SceneActor;

/// Static scenery spawned for a scene (props, lights) — despawned wholesale on teardown.
#[derive(Component)]
struct SceneProp;

// ── Scene identity + state ─────────────────────────────────────────────────────────────

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum SceneId {
    WorkSite,
    WallPatrol,
    OrksFlee,
    NightSiege,
    BarrelPeek,
    Mason,
    /// Ch.2 cutscene (campaign screenplay): dawn after night 1, a farmer mending a burnt fence.
    FarmMorning,
}

/// What the F1 panel asks for vs. what's currently staged. `clock` is seconds since the active scene
/// began (the loop phase every driven behaviour reads). A fresh scene starts the clock at
/// `-cinematic::PRE_ROLL`: actors hold their marks (drivers clamp to `t = 0`) until it crosses
/// zero, giving the user time to set the free-cam before anything moves.
#[derive(Resource, Default)]
pub struct SceneState {
    /// Panel request: `Some(id)` to stage, `None` to clear. Compared against `active` each frame.
    pub want: Option<SceneId>,
    pub active: Option<SceneId>,
    clock: f32,
    /// Where to pin the hero while the scene runs (world pos + yaw), if the scene stages him.
    hero: Option<(Vec3, f32)>,
    /// The staged hero is walking (his gait fields are written by the scene, not cleared by [`hold_scene_hero`]).
    hero_moving: bool,
}

/// Per-ork looped role within a scene.
#[derive(Clone, Copy)]
enum OrkRole {
    /// Stream outward from `origin` along `dir`, wrapping at `span` — a panicked scatter.
    Flee,
    /// March from a start point toward the keep (origin), wrapping — a siege stream.
    Horde,
    /// Stand and (for the archer) mime a draw on a cadence.
    Idle,
    Archer,
}

#[derive(Component)]
struct SceneOrk {
    role: OrkRole,
    origin: Vec2,
    dir: Vec2,
    speed: f32,
    span: f32,
    phase: f32,
}

/// A peasant that periodically swings its tool — reads as digging/hoeing.
#[derive(Component)]
struct SceneLabor {
    period: f32,
    phase: f32,
    last: f32,
}

/// The gag mason — [`drive_scene_mason`] owns his WHOLE rig (root pose + every limb), so
/// `villager_limbs` skips him (see its `Without<SceneMason>` filter). `pub` for that filter.
#[derive(Component)]
pub struct SceneMason;

/// One of the mason's three wall stones, pre-spawned at its course slot at scale ~0 and popped
/// in when its lay cycle "places" it (reset to 0 when the loop wraps).
#[derive(Component)]
struct MasonStone {
    idx: u32,
}

/// A glowing bolt that flies `from`→`to` on a loop (the ork archer's green warp-bolt).
#[derive(Component)]
struct SceneBolt {
    from: Vec3,
    to: Vec3,
    period: f32,
    phase: f32,
}

/// Shared materials/meshes for scene props + bolts (props share one white vertex-coloured material,
/// like every other prop in the game; the bolt/flame are unlit emissives that bloom).
#[derive(Resource)]
struct SceneAssets {
    prop_mat: Handle<StandardMaterial>,
    bolt_mat: Handle<StandardMaterial>,
    bolt_mesh: Handle<Mesh>,
    flame_mat: Handle<StandardMaterial>,
    flame_mesh: Handle<Mesh>,
}

pub struct ScenesPlugin;

impl Plugin for ScenesPlugin {
    fn build(&self, app: &mut App) {
        // `FOREST_SCENE=worksite|wallpatrol|orksflee|nightsiege|barrelpeek` stages a scene at boot
        // (for a screenshot/clip), same staging-hook style as the other `FOREST_*` vars.
        let mut state = SceneState::default();
        if let Ok(s) = std::env::var("FOREST_SCENE") {
            state.want = match s.trim().to_ascii_lowercase().as_str() {
                "worksite" | "work" => Some(SceneId::WorkSite),
                "wallpatrol" | "wall" => Some(SceneId::WallPatrol),
                "orksflee" | "flee" => Some(SceneId::OrksFlee),
                "nightsiege" | "siege" | "night" => Some(SceneId::NightSiege),
                "barrelpeek" | "barrel" => Some(SceneId::BarrelPeek),
                "mason" | "threestones" | "stones" => Some(SceneId::Mason),
                "farm" | "farmmorning" | "ch2" | "protection" => Some(SceneId::FarmMorning),
                _ => None,
            };
        }
        app.insert_resource(state)
            .add_systems(Startup, setup_scene_assets)
            .add_systems(
                Update,
                (apply_scene_change, drive_scene_orks, drive_scene_labor, drive_scene_bolts, drive_scene_mason, drive_farm_scene)
                    .chain(),
            )
            // Pin the staged hero LAST (after locomotion/gravity have run) and just before transforms
            // propagate, so his elevated wall mark is the authoritative pose regardless of PlayMode.
            .add_systems(
                PostUpdate,
                (hold_scene_hero, farm_camera, farm_hide_hud).before(bevy::transform::TransformSystems::Propagate),
            );
    }
}

fn setup_scene_assets(
    mut commands: Commands,
    mut meshes: ResMut<Assets<Mesh>>,
    mut materials: ResMut<Assets<StandardMaterial>>,
) {
    let prop_mat =
        materials.add(StandardMaterial { base_color: Color::WHITE, perceptual_roughness: 0.85, ..default() });
    // Sickly-green warp glow (matches the fortress towers' bolts), unlit so it blooms.
    let bolt_mat = materials.add(StandardMaterial {
        base_color: Color::srgb(0.62, 0.78, 0.5), // desaturated off the old neon green
        emissive: LinearRgba::rgb(0.6, 3.4, 0.7),
        unlit: true,
        ..default()
    });
    let bolt_mesh = meshes.add(Sphere::new(0.18).mesh().ico(2).unwrap());
    let flame_mat = crate::flame_fx::flame_card_material(&mut materials);
    let flame_mesh = meshes.add(crate::flame_fx::flame_card_mesh(0.34));
    commands.insert_resource(SceneAssets { prop_mat, bolt_mat, bolt_mesh, flame_mat, flame_mesh });
}

// ── Scene change: teardown + setup ─────────────────────────────────────────────────────

#[allow(clippy::too_many_arguments, clippy::type_complexity)]
fn apply_scene_change(
    time: Res<Time>,
    mut state: ResMut<SceneState>,
    assets: Res<SceneAssets>,
    armory: Option<Res<InvaderArmory>>,
    mut director: ResMut<crate::cinematic::DirectorState>,
    mut clock: ResMut<crate::scene::SkyClock>,
    mut commands: Commands,
    mut meshes: ResMut<Assets<Mesh>>,
    mut creature_mats: ResMut<Assets<crate::creature::CreatureMaterial>>,
    old: Query<Entity, Or<(With<SceneActor>, With<SceneProp>)>>,
    prog: Option<Res<crate::capture::ClipProgress>>,
    mut subs: ResMut<crate::subtitles::Subtitles>,
) {
    if state.want == state.active {
        // A clip's warm-up frames don't count: the scene starts when recording does.
        // `FOREST_SCENE_T` freezes the clock at that instant (a still of one moment of the cutscene).
        let still = state.active == Some(SceneId::FarmMorning) && std::env::var_os("FOREST_SCENE_T").is_some();
        if !still && !prog.is_some_and(|p| !p.recording) {
            state.clock += time.delta_secs();
        }
        return;
    }
    // Tear down the previous scene's actors + props.
    for e in &old {
        commands.entity(e).try_despawn();
    }
    state.clock = 0.0;
    state.hero = None;
    state.hero_moving = false;
    subs.release();
    director.gesture = None;
    director.hide_weapon = false;

    let Some(id) = state.want else {
        // Cleared: hand the sky back to the normal cycle.
        state.active = None;
        clock.paused = false;
        return;
    };
    let Some(armory) = armory.as_ref() else { return };
    let arm = &armory.0;

    match id {
        SceneId::WorkSite => {
            pin_sky(&mut clock, 0.25); // midday
            // Hero supervising, arms folded (keeps his sword — a captain's idle).
            state.hero = Some((world_y(2.0, 5.0), std::f32::consts::PI)); // facing +Z toward the gang
            director.gesture = Some(crate::cinematic::HeroGesture::ArmsCrossed);
            // Three farmhands hauling/hoeing, facing the camera side.
            for (i, (x, z)) in [(0.0, 8.0), (2.2, 8.7), (4.2, 8.2)].into_iter().enumerate() {
                let e = crate::villagers::spawn_scene_peasant(
                    &mut commands, &mut meshes, &mut creature_mats,
                    Vec2::new(x, z), 0.0, Some(crate::villagers::Trade::Farmer), 31 + i as u32 * 17,
                );
                commands.entity(e).insert(SceneLabor { period: 1.6, phase: i as f32 * 0.37, last: -1.0 });
            }
            // A fourth peasant loafing, leaning by a planted shovel.
            crate::villagers::spawn_scene_peasant(
                &mut commands, &mut meshes, &mut creature_mats, Vec2::new(-2.0, 6.6), 0.5, None, 7,
            );
            spawn_prop_mesh(&mut commands, &mut meshes, &assets, shovel_mesh(), Vec3::new(-1.4, 0.0, 6.7), 0.4, 0.55);
            spawn_prop_mesh(&mut commands, &mut meshes, &assets, stone_pile_mesh(), Vec3::new(1.2, 0.0, 9.6), 0.0, 1.0);
        }
        SceneId::WallPatrol => {
            pin_sky(&mut clock, 0.46); // dusk
            // An ork archer just outside the east wall, drawing on a loop, with two idle grunts.
            spawn_scene_ork(&mut commands, arm, OrkVariant::Scout, Vec2::new(24.0, 2.0), -std::f32::consts::FRAC_PI_2,
                SceneOrk { role: OrkRole::Archer, origin: Vec2::new(24.0, 2.0), dir: Vec2::NEG_X, speed: 0.0, span: 0.0, phase: 0.0 });
            spawn_scene_ork(&mut commands, arm, OrkVariant::Grunt, Vec2::new(25.5, 5.0), -std::f32::consts::FRAC_PI_2,
                SceneOrk { role: OrkRole::Idle, origin: Vec2::new(25.5, 5.0), dir: Vec2::NEG_X, speed: 0.0, span: 0.0, phase: 0.0 });
            spawn_scene_ork(&mut commands, arm, OrkVariant::Berserker, Vec2::new(23.5, -2.2), -std::f32::consts::FRAC_PI_2,
                SceneOrk { role: OrkRole::Idle, origin: Vec2::new(23.5, -2.2), dir: Vec2::NEG_X, speed: 0.0, span: 0.0, phase: 0.0 });
            // Green bolt streaking from the archer at the rampart, looping.
            commands.spawn((
                Mesh3d(assets.bolt_mesh.clone()),
                MeshMaterial3d(assets.bolt_mat.clone()),
                Transform::from_translation(Vec3::new(24.0, 2.6, 2.0)),
                SceneBolt { from: Vec3::new(24.0, 2.6, 2.0), to: Vec3::new(17.5, 1.7, -2.5), period: 1.3, phase: 0.0 },
                SceneActor,
            ));
        }
        SceneId::OrksFlee => {
            pin_sky(&mut clock, 0.30);
            let c = nearest_camp().unwrap_or(Vec2::new(-32.0, 2.0));
            spawn_prop_mesh(&mut commands, &mut meshes, &assets, campfire_mesh(), Vec3::new(c.x, world_y_at(c), c.y), 0.0, 1.0);
            // Eight orks bolting outward in a fan, each on its own loop phase — chaos.
            for i in 0..8u32 {
                let a = i as f32 / 8.0 * std::f32::consts::TAU + 0.3;
                let dir = Vec2::new(a.cos(), a.sin());
                spawn_scene_ork(&mut commands, arm, variant_cycle(i), c + dir * 1.2, a,
                    SceneOrk { role: OrkRole::Flee, origin: c, dir, speed: 4.5 + (i % 3) as f32 * 0.8, span: 16.0, phase: i as f32 / 8.0 });
            }
            // A couple of knocked-over barrels for the gag.
            spawn_prop_mesh(&mut commands, &mut meshes, &assets, barrel_mesh(), Vec3::new(c.x + 2.0, world_y_at(c) + 0.3, c.y + 1.0), 1.3, 1.0);
            spawn_prop_mesh(&mut commands, &mut meshes, &assets, barrel_mesh(), Vec3::new(c.x - 1.5, world_y_at(c) + 0.3, c.y - 1.8), 2.6, 1.0);
        }
        SceneId::NightSiege => {
            pin_sky(&mut clock, 0.82); // deep night
            const WALL_TOP: f32 = 1.05; // north rampart walkway top (WALL_H·0.78)
            const WALL_Z: f32 = -12.0; // wall centre line
            // Hero up on the north rampart, war bell beside him, facing out over the field.
            state.hero = Some((Vec3::new(5.0, WALL_TOP, WALL_Z), 0.0)); // facing -Z (outward)
            director.gesture = Some(crate::cinematic::HeroGesture::Salute);
            spawn_prop_mesh(&mut commands, &mut meshes, &assets, bell_mesh(), Vec3::new(3.0, WALL_TOP, WALL_Z), 0.0, 1.0);
            // Torches strung along the wall walk.
            for x in [-9.0, -3.0, 9.0] {
                spawn_torch(&mut commands, &mut meshes, &assets, Vec3::new(x, WALL_TOP, WALL_Z));
            }
            // A horde flooding from the north toward the keep, funnelled near the gate (x≈0), looping.
            for i in 0..16u32 {
                let lane = (i % 5) as f32 - 2.0;
                let start = Vec2::new(lane * 1.6, -26.0 - (i / 5) as f32 * 3.0);
                let dir = (Vec2::ZERO - start).normalize_or_zero();
                spawn_scene_ork(&mut commands, arm, variant_cycle(i), start, dir.x.atan2(dir.y),
                    SceneOrk { role: OrkRole::Horde, origin: start, dir, speed: 3.2, span: start.length(), phase: i as f32 / 16.0 });
            }
        }
        SceneId::Mason => {
            pin_sky(&mut clock, 0.25); // midday
            // The mason himself — a plain peasant at his mark before the half-built wall.
            let e = crate::villagers::spawn_scene_peasant(
                &mut commands, &mut meshes, &mut creature_mats, MASON_MARK, 0.0, None, 11,
            );
            commands.entity(e).insert(SceneMason);
            // The half-built wall he's "working" on (gap in the top course for his three stones),
            // plus the stone pile he draws from.
            let wy = world_y_at(Vec2::new(MASON_MARK.x, MASON_WALL_Z));
            spawn_prop_mesh(&mut commands, &mut meshes, &assets, wall_course_mesh(), Vec3::new(MASON_MARK.x, wy, MASON_WALL_Z), 0.0, 1.0);
            let pile = MASON_MARK + Vec2::new(-1.1, -0.4);
            spawn_prop_mesh(&mut commands, &mut meshes, &assets, stone_pile_mesh(), Vec3::new(pile.x, world_y_at(pile), pile.y), 0.6, 0.8);
            // His three stones: pre-spawned at their course slots, popped in as each is "placed".
            let stone = meshes.add(mason_stone_mesh());
            for (i, dx) in MASON_STONE_X.into_iter().enumerate() {
                commands.spawn((
                    Mesh3d(stone.clone()),
                    MeshMaterial3d(assets.prop_mat.clone()),
                    Transform {
                        translation: Vec3::new(MASON_MARK.x + dx, wy + 0.40, MASON_WALL_Z),
                        rotation: Quat::from_rotation_y(i as f32 * 0.13 - 0.13), // slightly askew — hand-laid
                        scale: Vec3::splat(0.001),
                    },
                    MasonStone { idx: i as u32 },
                    SceneProp,
                ));
            }
            // Two labourers grinding at the wall's flanks — the ones he ends up "supervising".
            for (i, dx) in [-1.05f32, 1.05].into_iter().enumerate() {
                let e = crate::villagers::spawn_scene_peasant(
                    &mut commands, &mut meshes, &mut creature_mats,
                    MASON_MARK + Vec2::new(dx, 0.1), 0.0, Some(crate::villagers::Trade::Miner), 41 + i as u32 * 13,
                );
                commands.entity(e).insert(SceneLabor { period: 1.5, phase: i as f32 * 0.43, last: -1.0 });
            }
        }
        SceneId::FarmMorning => {
            pin_sky(&mut clock, 0.13); // first light
            setup_farm_morning(&mut commands, &mut meshes, &mut creature_mats, &assets);
        }
        SceneId::BarrelPeek => {
            pin_sky(&mut clock, 0.82);
            // A peasant peeking out from behind a barrel in the yard.
            spawn_prop_mesh(&mut commands, &mut meshes, &assets, barrel_mesh(), Vec3::new(6.0, world_y(6.0, 2.0).y, 2.0), 0.0, 1.0);
            crate::villagers::spawn_scene_peasant(
                &mut commands, &mut meshes, &mut creature_mats, Vec2::new(6.0, 2.7), std::f32::consts::PI, None, 5,
            );
            spawn_torch(&mut commands, &mut meshes, &assets, Vec3::new(8.5, world_y(8.5, 1.0).y, 1.0));
            // Three orks rampaging across the yard toward the keep, looping.
            for i in 0..3u32 {
                let start = Vec2::new(-12.0 + i as f32 * 2.0, -7.0 - i as f32 * 1.5);
                let dir = (Vec2::ZERO - start).normalize_or_zero();
                spawn_scene_ork(&mut commands, arm, variant_cycle(i + 1), start, dir.x.atan2(dir.y),
                    SceneOrk { role: OrkRole::Horde, origin: start, dir, speed: 3.6, span: start.length(), phase: i as f32 / 3.0 });
            }
        }
    }
    // Loop scenes get a camera-setting grace; the cutscene starts at once (`FOREST_SCENE_T=<s>` skips ahead for a still).
    state.clock = if id == SceneId::FarmMorning {
        std::env::var("FOREST_SCENE_T").ok().and_then(|v| v.trim().parse().ok()).unwrap_or(0.0)
    } else {
        -crate::cinematic::PRE_ROLL
    };
    state.active = Some(id);
}

// ── Per-frame drives ───────────────────────────────────────────────────────────────────

fn drive_scene_orks(
    time: Res<Time>,
    state: Res<SceneState>,
    mut q: Query<(&mut crate::orks::Ork, &mut Transform, &SceneOrk), With<SceneActor>>,
) {
    if state.active.is_none() {
        return;
    }
    let t = state.clock.max(0.0); // clamp: actors hold their marks through the pre-roll
    let rnow = time.elapsed_secs();
    for (mut o, mut tf, s) in &mut q {
        let pos = match s.role {
            OrkRole::Flee => {
                let d = (t * s.speed + s.phase * s.span).rem_euclid(s.span);
                o.facing = s.dir.x.atan2(s.dir.y);
                o.moving = true;
                s.origin + s.dir * d
            }
            OrkRole::Horde => {
                let len = s.span.max(0.01);
                let d = (t * s.speed + s.phase * len).rem_euclid(len);
                let dir = (Vec2::ZERO - s.origin).normalize_or_zero();
                o.facing = dir.x.atan2(dir.y);
                o.moving = true;
                s.origin + dir * d
            }
            OrkRole::Idle => {
                o.moving = false;
                s.origin
            }
            OrkRole::Archer => {
                o.moving = false;
                o.facing = s.dir.x.atan2(s.dir.y);
                // Mime a draw/loose every ~1.3s (drives the club/staff swing animation). `atk_anim`
                // is a timestamp in the `elapsed_secs` domain the limb animator reads. The clamped
                // `t` sits at 0 all through the pre-roll — don't re-stamp every held frame.
                if state.clock >= 0.0 && (t % 1.3) < time.delta_secs() {
                    o.atk_anim = rnow;
                }
                s.origin
            }
        };
        let gy = crate::worldmap::ground_at_world(pos.x, pos.y).unwrap_or(tf.translation.y);
        tf.translation = Vec3::new(pos.x, gy, pos.y);
        tf.rotation = Quat::from_rotation_y(o.facing);
    }
}

fn drive_scene_labor(
    time: Res<Time>,
    state: Res<SceneState>,
    mut q: Query<(&mut crate::villagers::Villager, &mut SceneLabor)>,
) {
    if state.active.is_none() || state.clock < 0.0 {
        return; // pre-roll: no tool swings (and no stray cycle-0 stamp) until the grace ends
    }
    let t = state.clock;
    for (mut v, mut l) in &mut q {
        let cyc = ((t / l.period) + l.phase).floor();
        if cyc != l.last {
            l.last = cyc;
            // Stamp the swing in the `elapsed_secs` domain `villager_limbs` compares against.
            v.atk_anim = time.elapsed_secs();
        }
    }
}

// ── The mason gag loop ───────────────────────────────────────────────────────────────

/// Where the mason stands (world XZ), facing +Z toward his wall — the open courtyard west of the
/// keep, clear of the market/well gather knots so wanderers don't photobomb the shot.
const MASON_MARK: Vec2 = Vec2::new(-5.5, 7.2);
const MASON_WALL_Z: f32 = MASON_MARK.y + 0.75;
/// One lay cycle: bow to the ground, heave the stone up, set it on the course.
const MASON_LAY_DUR: f32 = 2.6;
const MASON_LAY_TOTAL: f32 = 3.0 * MASON_LAY_DUR;
/// The supervising beat: step back, hands clasped behind, a long point, satisfied nods.
const MASON_SUP_DUR: f32 = 6.0;
const MASON_LOOP: f32 = MASON_LAY_TOTAL + MASON_SUP_DUR;
/// When within a lay cycle the stone lands on the wall (fraction of [`MASON_LAY_DUR`]).
const MASON_PLACE_AT: f32 = 0.80;
/// The three course slots (local X along the wall) his stones fill, in lay order.
const MASON_STONE_X: [f32; 3] = [-0.36, 0.0, 0.36];

/// Piecewise keyframe envelope: smoothstep between consecutive `(x, value)` keys (monotonic x),
/// clamped to the end values outside the key range. The whole mason mime is built from these.
fn env(x: f32, keys: &[(f32, f32)]) -> f32 {
    if x <= keys[0].0 {
        return keys[0].1;
    }
    for w in keys.windows(2) {
        let ((x0, v0), (x1, v1)) = (w[0], w[1]);
        if x < x1 {
            let u = ((x - x0) / (x1 - x0)).clamp(0.0, 1.0);
            return v0 + (v1 - v0) * (u * u * (3.0 - 2.0 * u));
        }
    }
    keys[keys.len() - 1].1
}

/// "He laid three stones. Then he supervised." — the looped pantomime. This system owns the
/// mason's whole rig: root pose (bow pitch + crouch + the step back), every limb (arms reach /
/// clasp behind the back / point; head looks at the work and nods), and the three stones popping
/// onto the course as each is placed. `villager_limbs` skips him entirely.
#[allow(clippy::type_complexity)]
fn drive_scene_mason(
    state: Res<SceneState>,
    mut roots: Query<
        (&mut crate::villagers::Villager, &mut Transform, &Children),
        (With<SceneMason>, Without<crate::villagers::VilPart>, Without<MasonStone>),
    >,
    mut parts: Query<
        (&crate::villagers::VilPart, &mut Transform),
        (Without<SceneMason>, Without<MasonStone>),
    >,
    mut stones: Query<
        (&MasonStone, &mut Transform),
        (Without<SceneMason>, Without<crate::villagers::VilPart>),
    >,
) {
    if state.active != Some(SceneId::Mason) {
        return;
    }
    // Clamp: he stands at his mark (rest pose, stones hidden) through the camera-setting pre-roll.
    let t = state.clock.max(0.0).rem_euclid(MASON_LOOP);

    // Pop each placed stone in (ease-out); the wrap resets all three for the next loop.
    for (s, mut tf) in &mut stones {
        let placed = (s.idx as f32 + MASON_PLACE_AT) * MASON_LAY_DUR;
        let k = if t >= placed {
            let u = ((t - placed) / 0.3).min(1.0);
            1.0 - (1.0 - u) * (1.0 - u)
        } else {
            0.0
        };
        tf.scale = Vec3::splat(k.max(0.001));
    }

    // Pose channels for this loop instant: torso pitch (+ = bow forward), hip drop, per-arm and
    // head rotations, how far he's stepped back off his mark, and the leg-shuffle swing.
    let (pitch, crouch, arm_l, arm_r, head_pitch, head_yaw, back, leg) = if t < MASON_LAY_TOTAL {
        // ── Laying: bow down, hold (he's not hurrying), heave up, set the stone, straighten. ──
        let u = (t % MASON_LAY_DUR) / MASON_LAY_DUR;
        let pitch = env(u, &[(0.0, 0.0), (0.26, 0.85), (0.44, 0.85), (0.60, 0.14), (0.78, 0.42), (0.92, 0.42), (1.0, 0.02)]);
        let crouch = 0.20 * env(u, &[(0.0, 0.0), (0.26, 1.0), (0.46, 1.0), (0.62, 0.0), (1.0, 0.0)]);
        // Both arms together — a two-handed carry, so the stone reads heavy.
        let arm = env(u, &[(0.0, -0.05), (0.26, -0.55), (0.44, -0.6), (0.60, -1.0), (0.78, -1.25), (0.92, -1.25), (1.0, -0.1)]);
        let head_pitch = env(u, &[(0.0, 0.05), (0.26, 0.32), (0.60, 0.18), (0.80, 0.35), (1.0, 0.08)]);
        (pitch, crouch, arm, arm, head_pitch, 0.0, 0.0, 0.02 * (t * 1.3).sin())
    } else {
        // ── Supervising: step back, chest out, hands clasped behind, point at the work with
        // emphatic nods, one satisfied double-nod, then step back up to the wall for the wrap. ──
        let s = t - MASON_LAY_TOTAL;
        let back = 0.85 * env(s, &[(0.0, 0.0), (0.7, 1.0), (MASON_SUP_DUR - 0.7, 1.0), (MASON_SUP_DUR, 0.0)]);
        let lean = env(s, &[(0.0, 0.0), (0.9, -0.07), (MASON_SUP_DUR - 0.8, -0.07), (MASON_SUP_DUR, 0.0)]);
        let clasp = env(s, &[(0.0, 0.0), (0.9, 0.5), (MASON_SUP_DUR - 0.6, 0.5), (MASON_SUP_DUR, 0.0)]);
        let point = env(s, &[(2.0, 0.0), (2.5, 1.0), (3.8, 1.0), (4.3, 0.0)]);
        let arm_r = clasp + (-1.35 - clasp) * point; // the point overrides the clasped right arm
        let nod = -0.12 * (s * 5.0).sin() * point
            + env(s, &[(4.5, 0.0), (4.7, 0.25), (4.9, 0.02), (5.1, 0.2), (5.3, 0.0)]);
        // Scan the work side to side; while pointing, fix on the right-hand labourer.
        let head_yaw = 0.22 * (s * 0.9).sin() * (1.0 - point) + 0.3 * point;
        let stepping = !(0.7..=MASON_SUP_DUR - 0.7).contains(&s);
        let leg = if stepping { 0.35 * (s * 11.0).sin() } else { 0.02 * (s * 1.1).sin() };
        (lean, 0.0, clasp, arm_r, nod, head_yaw, back, leg)
    };

    for (mut v, mut tf, children) in &mut roots {
        let facing = 0.0; // toward the wall (+Z)
        let pos = Vec2::new(MASON_MARK.x, MASON_MARK.y - back);
        let gy = crate::worldmap::ground_at_world(pos.x, pos.y).unwrap_or(tf.translation.y);
        v.pos = pos;
        v.facing = facing;
        v.moving = false;
        tf.translation = Vec3::new(pos.x, gy - crouch, pos.y);
        tf.rotation = Quat::from_rotation_y(facing) * Quat::from_rotation_x(pitch);
        for &child in children {
            let Ok((part, mut ptf)) = parts.get_mut(child) else { continue };
            use crate::critters::PartKind;
            ptf.rotation = match part.kind {
                PartKind::Leg(sign) => Quat::from_rotation_x(sign * leg),
                PartKind::Arm(sign) => Quat::from_rotation_x(if sign > 0.0 { arm_r } else { arm_l }),
                PartKind::Head => Quat::from_rotation_y(head_yaw) * Quat::from_rotation_x(head_pitch),
                PartKind::Tail => Quat::IDENTITY,
            };
        }
    }
}

fn drive_scene_bolts(state: Res<SceneState>, mut q: Query<(&mut Transform, &SceneBolt)>) {
    if state.active.is_none() {
        return;
    }
    let t = state.clock.max(0.0); // parked at its phase point through the pre-roll
    for (mut tf, b) in &mut q {
        let u = ((t / b.period) + b.phase).rem_euclid(1.0);
        tf.translation = b.from.lerp(b.to, u);
    }
}

/// Pin the staged hero at his mark each frame (works in free-cam, the filming mode, where the
/// locomotion system holds him at `Hero.pos`/`.y` without gravity).
fn hold_scene_hero(
    state: Res<SceneState>,
    mut hero_q: Query<(&mut crate::player::Hero, &mut Transform)>,
) {
    let Some((p, yaw)) = state.hero else { return };
    let Ok((mut hero, mut tf)) = hero_q.single_mut() else { return };
    hero.pos = Vec2::new(p.x, p.z);
    hero.y = p.y;
    hero.facing = yaw;
    hero.moving = state.hero_moving;
    tf.translation = p;
    tf.rotation = Quat::from_rotation_y(yaw);
}

// ── Ch.2 cutscene: "Bless you for the protection" ────────────────────────────────────
//
// Campaign screenplay Ch.2 (`docs/superpowers/specs/2026-10-13-kampania-scenariusz-design.md`): the
// dawn after night 1. A farmer kneels mending a burnt fence, another hauls planks past, the knight
// walks up. ~19 s, every clip from the UAL pool (`Fixing_Kneeling`, `Walk_Carry_Loop`, hero walk).
// Pure scene-director: the same `SceneState` clock drives actors, camera cuts, captions, letterbox +
// fades, and the scene clears itself (`want = None`) at the end. `FOREST_SCENE=farm` stages it
// (`FOREST_SCENE_T=<s>` freezes the clock there for a still; under `FOREST_CLIP` it starts with recording).

/// The fence line's centre (world XZ): open grass on the road out to the south-west farms.
const FARM: Vec2 = Vec2::new(-36.0, 34.0);
/// Where the kneeling farmer works — just on the +Z side of the fence gap, facing the fence (−Z).
const FARM_KNEEL: Vec2 = Vec2::new(FARM.x, FARM.y + 0.55);
const FARM_END: f32 = 19.4;
/// The knight's walk-in: from the road to a conversational stop beside the farmer.
const WAT_FROM: Vec2 = Vec2::new(FARM.x + 9.5, FARM.y + 1.2);
const WAT_TO: Vec2 = Vec2::new(FARM.x + 1.9, FARM.y + 0.9);
/// The plank-hauler's lane (behind the pair) and where he finishes walking.
const HAUL_Z: f32 = FARM.y + 3.3;
const HAUL_END_X: f32 = FARM.x - 6.5;
const HAUL_SPEED: f32 = 1.2; // = npc_skin::WALK_NATIVE, so the carry-walk's feet don't skate

/// Timed captions: (start s, duration s, speaker, line). Texts verbatim from the screenplay; the
/// farmer's first line is the existing villager VO clip `screaming` (`audio/lines.rs`).
const FARM_LINES: [(f32, f32, &str, &str); 4] = [
    (5.6, 5.3, "Farmer", "Bless you for the protection. The screaming at night is a lovely touch."),
    (11.2, 2.0, "Wat", "You're welcome."),
    (13.8, 2.0, "Farmer", "Wasn't thanking you."),
    (16.4, 1.8, "Wat", "I know."),
];

#[derive(Component, Clone, Copy, PartialEq)]
enum FarmRole {
    Kneeler,
    Hauler,
}

/// Full-screen black overlay for the open/close fades.
#[derive(Component)]
struct FarmFade;

fn setup_farm_morning(
    commands: &mut Commands,
    meshes: &mut Assets<Mesh>,
    creature_mats: &mut Assets<crate::creature::CreatureMaterial>,
    assets: &SceneAssets,
) {
    let a = FARM;
    // The fence: three bays each side of a gap; the right-hand ones scorched.
    for dx in [-6.0f32, -4.0, -2.0, 2.0, 4.0, 6.0] {
        let p = Vec2::new(a.x + dx, a.y);
        spawn_prop_mesh(commands, meshes, assets, fence_section_mesh(dx > 3.0), Vec3::new(p.x, world_y_at(p), p.y), 0.0, 1.0);
    }
    // Torn-out rail: one end still nailed to the post, hanging; a spare lying in the grass.
    let hinge = Vec3::new(a.x - 1.0, world_y_at(Vec2::new(a.x - 1.0, a.y)) + 0.72, a.y);
    commands.spawn((
        Mesh3d(meshes.add(cube(1.0, 0.07, 0.05, Vec3::new(0.5, 0.0, 0.0), WOOD))),
        MeshMaterial3d(assets.prop_mat.clone()),
        Transform::from_translation(hinge).with_rotation(Quat::from_rotation_z(-0.6)),
        SceneProp,
    ));
    let spare = Vec2::new(a.x + 0.6, a.y - 0.5);
    spawn_prop_mesh(commands, meshes, assets, cube(1.4, 0.06, 0.12, Vec3::new(0.0, 0.03, 0.0), WOOD), Vec3::new(spare.x, world_y_at(spare), spare.y), 0.5, 1.0);
    // Planks stacked beside the work.
    let pile = Vec2::new(a.x - 1.5, a.y + 0.45);
    spawn_prop_mesh(commands, meshes, assets, plank_pile_mesh(), Vec3::new(pile.x, world_y_at(pile), pile.y), 0.2, 1.0);
    // The burnt field behind them: charred ground + blackened stakes.
    for (dx, dz, r) in [(-3.0f32, 6.5f32, 2.6f32), (1.5, 8.0, 3.2), (5.5, 6.0, 2.2), (-6.5, 9.5, 2.8), (9.0, 9.0, 2.4)] {
        let p = Vec2::new(a.x + dx, a.y + dz);
        spawn_prop_mesh(commands, meshes, assets, scorch_patch_mesh(), Vec3::new(p.x, world_y_at(p) + 0.02, p.y), dx, r);
    }
    for (dx, dz) in [(-2.0f32, 5.6f32), (0.2, 7.4), (2.8, 6.8), (4.4, 8.6), (-4.6, 8.2), (-0.8, 9.6)] {
        let p = Vec2::new(a.x + dx, a.y + dz);
        spawn_prop_mesh(commands, meshes, assets, char_stake_mesh(), Vec3::new(p.x, world_y_at(p), p.y), dx * 1.7, 0.7 + (dz % 1.0) * 0.5);
    }

    // The kneeling farmer (never looks up) and the plank-hauler.
    let farmer = crate::villagers::spawn_scene_peasant(
        commands, meshes, creature_mats, FARM_KNEEL, std::f32::consts::PI, Some(crate::villagers::Trade::Farmer), 23,
    );
    commands.entity(farmer).insert((FarmRole::Kneeler, crate::npc_skin::SkinClip("Fixing_Kneeling")));
    let hauler = crate::villagers::spawn_scene_peasant(
        commands, meshes, creature_mats, Vec2::new(FARM.x + 9.6, HAUL_Z), -std::f32::consts::FRAC_PI_2, None, 13,
    );
    let bundle = meshes.add(plank_bundle_mesh());
    commands.entity(hauler).insert((FarmRole::Hauler, crate::npc_skin::SkinClip("Walk_Carry_Loop"))).with_children(|p| {
        // The load, cradled at the chest (the carry clip holds the arms out; the bundle is the prop).
        p.spawn((Mesh3d(bundle), MeshMaterial3d(assets.prop_mat.clone()), Transform::from_xyz(0.0, 1.0, 0.5)));
    });

    // Letterbox + fade-from-black.
    for top in [true, false] {
        commands.spawn((
            Node {
                position_type: PositionType::Absolute,
                left: Val::Px(0.0),
                width: Val::Percent(100.0),
                height: Val::Percent(12.8), // 2.39:1 on a 16:9 frame
                top: if top { Val::Px(0.0) } else { Val::Auto },
                bottom: if top { Val::Auto } else { Val::Px(0.0) },
                ..default()
            },
            BackgroundColor(Color::BLACK),
            GlobalZIndex(35),
            SceneProp,
        ));
    }
    commands.spawn((
        Node {
            position_type: PositionType::Absolute,
            left: Val::Px(0.0),
            top: Val::Px(0.0),
            width: Val::Percent(100.0),
            height: Val::Percent(100.0),
            ..default()
        },
        BackgroundColor(Color::BLACK),
        GlobalZIndex(38),
        FarmFade,
        SceneProp,
    ));
}

/// The knight's walk-in: (position, facing, still striding?) at scene time `t`.
fn farm_wat(t: f32) -> (Vec2, f32, bool) {
    let speed = crate::player::SPEED;
    let len = WAT_FROM.distance(WAT_TO);
    let arrive = len / speed;
    let pos = WAT_FROM.lerp(WAT_TO, ((t * speed) / len).clamp(0.0, 1.0));
    let yaw = |v: Vec2| v.x.atan2(v.y);
    let (walk, stand) = (yaw(WAT_TO - WAT_FROM), yaw(FARM_KNEEL - WAT_TO));
    // ease the last bit of heading round to face the farmer
    let k = env(t, &[(arrive, 0.0), (arrive + 0.5, 1.0)]);
    (pos, walk + (stand - walk) * k, t > 0.0 && t < arrive)
}

#[allow(clippy::type_complexity)]
fn drive_farm_scene(
    time: Res<Time>,
    mut state: ResMut<SceneState>,
    mut subs: ResMut<crate::subtitles::Subtitles>,
    mut actors: Query<
        (&FarmRole, &mut crate::villagers::Villager, &mut Transform, Option<&mut crate::npc_skin::SkinClip>),
        Without<crate::player::Hero>,
    >,
    mut hero_q: Query<&mut crate::player::Hero>,
    mut fade: Query<&mut BackgroundColor, With<FarmFade>>,
) {
    if state.active != Some(SceneId::FarmMorning) {
        return;
    }
    let t = state.clock.max(0.0);
    let (dt, now) = (time.delta_secs(), time.elapsed_secs());

    for (role, mut v, mut tf, clip) in &mut actors {
        let (pos, facing, walking) = match role {
            FarmRole::Kneeler => (FARM_KNEEL, std::f32::consts::PI, false),
            FarmRole::Hauler => {
                // already mid-stride when the scene opens
                let x = (FARM.x + 12.0 - HAUL_SPEED * (t + 2.0)).max(HAUL_END_X);
                (Vec2::new(x, HAUL_Z), -std::f32::consts::FRAC_PI_2, x > HAUL_END_X + 1e-3)
            }
        };
        v.pos = pos;
        v.facing = facing;
        v.moving = walking;
        tf.translation = Vec3::new(pos.x, world_y_at(pos), pos.y);
        tf.rotation = Quat::from_rotation_y(facing);
        if *role == FarmRole::Hauler {
            if let Some(mut c) = clip {
                let want = if walking { "Walk_Carry_Loop" } else { "" };
                if c.0 != want {
                    c.0 = want;
                }
            }
        }
    }

    // The knight: pose handed to `hold_scene_hero` (PostUpdate); gait fields written here.
    let (wp, wf, walking) = farm_wat(t);
    state.hero = Some((Vec3::new(wp.x, world_y_at(wp), wp.y), wf));
    state.hero_moving = walking;
    if let Ok(mut hero) = hero_q.single_mut() {
        if walking {
            crate::player::anim::stage_gait(&mut hero, crate::player::SPEED, dt);
            hero.sprint_held = false;
        } else {
            hero.moving_amt *= (-dt * 8.0).exp();
        }
    }

    // Captions (pinned against ambient barks; `release`d on teardown).
    match FARM_LINES.iter().find(|(s, d, ..)| t >= *s && t < s + d) {
        Some((s, d, who, text)) => subs.force(now, Some(who), text, s + d - t),
        None => subs.force(now, None, "", 0.0),
    }

    // Fade in from black, out to black.
    let a = (1.0 - t / 1.2).max((t - (FARM_END - 1.0)) / 1.0).clamp(0.0, 1.0);
    for mut bg in &mut fade {
        bg.0 = Color::srgba(0.0, 0.0, 0.0, a);
    }

    if t >= FARM_END {
        state.want = None; // done — the next frame's teardown hands the world back
    }
}

/// What the cutscene borrows from the camera and restores on teardown.
struct FarmLookSaved {
    fov: f32,
    dof: (f32, f32, f32),
}

/// Camera cuts + lens: wide track of the walk-in, then farmer / knight coverage of the exchange.
/// Each shot has its own focal length (wide 46° → telephoto close-ups) and a shallow depth of field
/// racked onto the subject; a faint handheld drift keeps the frame alive; film grain, vignette and
/// a touch of chromatic aberration ride the final grade pass. All of it is put back afterwards.
#[allow(clippy::type_complexity)]
fn farm_camera(
    time: Res<Time>,
    state: Res<SceneState>,
    mut cam: Query<
        (&mut Transform, &mut Projection, &mut crate::dof::Dof, Option<&mut crate::filmgrade::FilmGrade>),
        (With<Camera3d>, Without<crate::player::Hero>),
    >,
    mut saved: Local<Option<FarmLookSaved>>,
) {
    let Ok((mut c, mut proj, mut dof, grade)) = cam.single_mut() else { return };
    if state.active != Some(SceneId::FarmMorning) {
        // Hand the lens back (once) after the scene.
        if let Some(sv) = saved.take() {
            if let Projection::Perspective(p) = &mut *proj {
                p.fov = sv.fov;
            }
            (dof.range, dof.far_ramp, dof.max_radius) = sv.dof;
            if let Some(mut g) = grade {
                (g.grain, g.vignette, g.aberration) = (0.0, 0.0, 0.0);
            }
        }
        return;
    }
    let t = state.clock.max(0.0);
    let now = time.elapsed_secs();
    let gy = world_y_at(FARM);
    let at3 = |x: f32, y: f32, z: f32| Vec3::new(FARM.x + x, gy + y, FARM.y + z);
    // (cut time, shot): wide · farmer · knight · farmer · knight
    const CUTS: [(f32, u8); 5] = [(0.0, 0), (5.4, 1), (11.0, 2), (13.6, 1), (16.2, 2)];
    let (start, shot) = CUTS.iter().rev().find(|(s, _)| t >= *s).copied().unwrap_or((0.0, 0));
    let u = t - start;
    // (eye, look-at, field of view, sharp half-band) per shot.
    let (eye, at, fov_deg, band): (Vec3, Vec3, f32, f32) = match shot {
        // Low, through the fence line, following the knight in (a slow drift sideways).
        0 => {
            let (w, _, _) = farm_wat(t);
            let chest = Vec3::new(w.x, world_y_at(w) + 1.0, w.y);
            (at3(3.8 - 0.1 * u, 1.05, -4.6), chest.lerp(at3(0.8, 0.9, 0.8), 0.4), 46.0, 7.0)
        }
        // The farmer, shot through the gap in the fence; a slow push-in on a long lens.
        1 => (at3(-0.5, 0.85, -2.6 + 0.07 * u), at3(0.0, 0.62, 0.55), 30.0, 0.9),
        // Over the farmer's shoulder at the knight.
        _ => (
            at3(-1.1, 0.95, 1.5 - 0.04 * u),
            Vec3::new(WAT_TO.x, world_y_at(WAT_TO) + 1.0, WAT_TO.y),
            34.0,
            1.1,
        ),
    };
    // Handheld: slow, tiny, incommensurate drifts on position and aim (never a shake).
    let h = |f: f32, ph: f32| (now * f + ph).sin();
    let sway = Vec3::new(h(0.9, 0.0) + 0.5 * h(2.3, 1.0), h(1.1, 2.0) * 0.6, h(0.7, 4.0)) * 0.012;
    let aim = Vec3::new(h(1.3, 3.0), h(0.8, 5.0) * 0.7, h(1.7, 1.5)) * 0.01;
    c.translation = eye + sway;
    c.look_at(at + aim, Vec3::Y);

    if saved.is_none() {
        let fov = if let Projection::Perspective(p) = &*proj { p.fov } else { 50f32.to_radians() };
        *saved = Some(FarmLookSaved { fov, dof: (dof.range, dof.far_ramp, dof.max_radius) });
    }
    if let Projection::Perspective(p) = &mut *proj {
        p.fov = fov_deg.to_radians();
    }
    // Rack focus onto the subject: sharp through the subject, melting off behind it.
    dof.focal = eye.distance(at);
    dof.range = band;
    dof.far_ramp = 16.0;
    dof.max_radius = 7.0;
    if let Some(mut g) = grade {
        g.grain = 0.045;
        g.vignette = 0.42;
        g.aberration = 0.0035;
        g.time = now.fract() * 17.0;
    }
}

/// Hide the whole HUD for the duration (every root UI node but the cutscene's own letterbox / fade
/// and the caption row), remembering each node's visibility so it comes back exactly as it was.
#[allow(clippy::type_complexity)]
fn farm_hide_hud(
    state: Res<SceneState>,
    mut roots: Query<
        (Entity, &mut Visibility),
        (With<Node>, Without<ChildOf>, Without<SceneProp>, Without<crate::subtitles::SubtitleRow>),
    >,
    mut hidden: Local<Vec<(Entity, Visibility)>>,
) {
    if state.active == Some(SceneId::FarmMorning) {
        for (e, mut v) in &mut roots {
            if *v != Visibility::Hidden {
                hidden.push((e, *v));
                *v = Visibility::Hidden;
            }
        }
    } else if !hidden.is_empty() {
        for (e, was) in hidden.drain(..) {
            if let Ok((_, mut v)) = roots.get_mut(e) {
                *v = was;
            }
        }
    }
}

/// One fence bay (2 u wide, centred on the origin): two posts + two rails. `burnt` = scorched black.
fn fence_section_mesh(burnt: bool) -> Mesh {
    let (post, rail) = if burnt { (0x2a2520, 0x352d26) } else { (WOOD_DARK, WOOD) };
    merged(vec![
        cylr(0.05, 0.95, Vec3::new(-1.0, 0.475, 0.0), Quat::IDENTITY, post),
        cylr(0.05, 0.95, Vec3::new(1.0, 0.475, 0.0), Quat::IDENTITY, post),
        cube(2.0, 0.07, 0.05, Vec3::new(0.0, 0.40, 0.0), rail),
        cube(2.0, 0.07, 0.05, Vec3::new(0.0, 0.72, 0.0), rail),
    ])
}

/// A short stack of fresh-cut planks.
fn plank_pile_mesh() -> Mesh {
    merged(vec![
        cube(1.2, 0.05, 0.2, Vec3::new(0.0, 0.03, 0.0), 0xb08a58),
        cube(1.2, 0.05, 0.2, Vec3::new(0.02, 0.08, 0.22), 0xa87f4e),
        cube(1.2, 0.05, 0.2, Vec3::new(-0.03, 0.13, 0.1), 0xb89463),
        cube(1.1, 0.05, 0.2, Vec3::new(0.05, 0.18, 0.16), 0xa98250),
    ])
}

/// The planks the hauler carries (length along local +Z, the way he faces).
fn plank_bundle_mesh() -> Mesh {
    merged(vec![
        cube(0.2, 0.05, 1.3, Vec3::new(-0.11, 0.0, 0.0), 0xb08a58),
        cube(0.2, 0.05, 1.3, Vec3::new(0.11, 0.0, 0.0), 0xa87f4e),
        cube(0.2, 0.05, 1.2, Vec3::new(0.0, 0.055, 0.0), 0xb89463),
    ])
}

/// A scorched patch of ground: a flat soot disc.
fn scorch_patch_mesh() -> Mesh {
    cylr(1.0, 0.03, Vec3::new(0.0, 0.015, 0.0), Quat::IDENTITY, 0x1e1914)
}

/// A blackened stalk/stake left standing in the burnt field.
fn char_stake_mesh() -> Mesh {
    merged(vec![
        cylr(0.04, 0.8, Vec3::new(0.0, 0.4, 0.0), Quat::IDENTITY, 0x1b1713),
        cone_m(0.05, 0.12, Vec3::new(0.0, 0.86, 0.0), Quat::IDENTITY, 0x2a231d),
    ])
}

// ── Spawn helpers ──────────────────────────────────────────────────────────────────────

fn spawn_scene_ork(commands: &mut Commands, arm: &crate::orks::Armory, variant: OrkVariant, pos: Vec2, _facing: f32, role: SceneOrk) {
    // `arm.spawn` sets a correct ground transform + per-variant scale; `drive_scene_orks` re-poses
    // it (position + facing) every frame, so we only tag it here.
    let e = arm.spawn(commands, variant, Faction::Red, pos, pos, pos.x.to_bits() ^ pos.y.to_bits());
    commands.entity(e).insert((SceneActor, role));
}

fn spawn_prop_mesh(commands: &mut Commands, meshes: &mut Assets<Mesh>, assets: &SceneAssets, mesh: Mesh, pos: Vec3, yaw: f32, scale: f32) {
    commands.spawn((
        Mesh3d(meshes.add(mesh)),
        MeshMaterial3d(assets.prop_mat.clone()),
        Transform { translation: pos, rotation: Quat::from_rotation_y(yaw), scale: Vec3::splat(scale) },
        SceneProp,
    ));
}

fn spawn_torch(commands: &mut Commands, meshes: &mut Assets<Mesh>, assets: &SceneAssets, pos: Vec3) {
    // Post + a warm point light + flame cards on its head.
    spawn_prop_mesh(commands, meshes, assets, torch_post_mesh(), pos, 0.0, 1.0);
    commands.spawn((
        Mesh3d(assets.flame_mesh.clone()),
        MeshMaterial3d(assets.flame_mat.clone()),
        Transform::from_translation(pos + Vec3::new(0.0, 1.2, 0.0)),
        bevy::light::NotShadowCaster,
        crate::camps::Flicker { phase: pos.x * 1.3 },
        SceneProp,
    ));
    commands.spawn((
        PointLight { color: Color::srgb(1.0, 0.6, 0.25), intensity: 18_000.0, range: 9.0, shadow_maps_enabled: false, ..default() },
        Transform::from_translation(pos + Vec3::new(0.0, 1.3, 0.0)),
        SceneProp,
    ));
}

// ── Prop meshes (vertex-coloured, flat-shaded — the shared-material contract) ───────────

fn cube(w: f32, h: f32, d: f32, off: Vec3, hex: u32) -> Mesh {
    tinted(Cuboid::new(w, h, d).mesh().build().translated_by(off), hex)
}
fn cylr(r: f32, h: f32, off: Vec3, rot: Quat, hex: u32) -> Mesh {
    tinted(Cylinder::new(r, h).mesh().resolution(10).build().rotated_by(rot).translated_by(off), hex)
}
fn cone_m(r: f32, h: f32, off: Vec3, rot: Quat, hex: u32) -> Mesh {
    tinted(Cone { radius: r, height: h }.mesh().build().rotated_by(rot).translated_by(off), hex)
}

const WOOD: u32 = 0x6b4a2c;
const WOOD_DARK: u32 = 0x4a3320;
const IRON: u32 = 0x4b4f57;
const STONE_C: u32 = 0x8a8d92;

/// A spade planted in the earth, blade down, leaning (the entity tilts it).
fn shovel_mesh() -> Mesh {
    merged(vec![
        cylr(0.035, 1.5, Vec3::new(0.0, 0.85, 0.0), Quat::IDENTITY, WOOD), // shaft
        cube(0.22, 0.04, 0.05, Vec3::new(0.0, 1.6, 0.0), WOOD_DARK),       // T-grip
        cube(0.24, 0.3, 0.04, Vec3::new(0.0, 0.18, 0.0), IRON),           // blade
    ])
}

/// A short pile of cut stone blocks.
fn stone_pile_mesh() -> Mesh {
    merged(vec![
        cube(1.0, 0.3, 0.7, Vec3::new(0.0, 0.15, 0.0), STONE_C),
        cube(0.8, 0.28, 0.55, Vec3::new(0.05, 0.43, 0.0), 0x9a9da2),
        cube(0.5, 0.26, 0.4, Vec3::new(-0.1, 0.69, 0.05), STONE_C),
    ])
}

/// A half-built wall: a full base course plus raised end stacks, leaving the gap in the top
/// course the mason's three stones fill (slots at [`MASON_STONE_X`]).
fn wall_course_mesh() -> Mesh {
    merged(vec![
        cube(2.6, 0.40, 0.50, Vec3::new(0.0, 0.20, 0.0), STONE_C),
        cube(0.62, 0.26, 0.46, Vec3::new(-0.95, 0.53, 0.0), 0x9a9da2),
        cube(0.62, 0.26, 0.46, Vec3::new(0.95, 0.53, 0.0), 0x84878c),
    ])
}

/// One of the mason's wall stones (base at y=0, per the mesh contract — the slot transform seats
/// it on the course top).
fn mason_stone_mesh() -> Mesh {
    merged(vec![cube(0.32, 0.26, 0.42, Vec3::new(0.0, 0.13, 0.0), 0x9a9da2)])
}

/// A wooden barrel — staves + three iron hoops + a lid.
fn barrel_mesh() -> Mesh {
    let mut p = vec![
        cylr(0.34, 0.9, Vec3::new(0.0, 0.45, 0.0), Quat::IDENTITY, WOOD),
        cylr(0.30, 0.05, Vec3::new(0.0, 0.92, 0.0), Quat::IDENTITY, WOOD_DARK), // lid
    ];
    for y in [0.12, 0.45, 0.78] {
        p.push(cylr(0.36, 0.06, Vec3::new(0.0, y, 0.0), Quat::IDENTITY, IRON));
    }
    merged(p)
}

/// A bell hung in a small A-frame (two posts + crossbeam + a flared bell + clapper).
fn bell_mesh() -> Mesh {
    let post = |x: f32| cylr(0.06, 1.5, Vec3::new(x, 0.75, 0.0), Quat::IDENTITY, WOOD);
    merged(vec![
        post(-0.45),
        post(0.45),
        cube(1.1, 0.1, 0.12, Vec3::new(0.0, 1.45, 0.0), WOOD_DARK), // crossbeam
        cone_m(0.26, 0.42, Vec3::new(0.0, 1.0, 0.0), Quat::IDENTITY, 0xb8892f), // bell body (apex up)
        cylr(0.27, 0.06, Vec3::new(0.0, 0.8, 0.0), Quat::IDENTITY, 0x9a6f22),    // bell lip
        cylr(0.04, 0.18, Vec3::new(0.0, 0.86, 0.0), Quat::IDENTITY, IRON),       // clapper
    ])
}

/// A campfire — a ring of logs around a charred core (the firelight is a separate scene light if
/// wanted; the emissive embers here keep it lit even by day).
fn campfire_mesh() -> Mesh {
    let mut p = vec![cube(0.7, 0.08, 0.7, Vec3::new(0.0, 0.04, 0.0), 0x2a2018)]; // ash bed
    for i in 0..5 {
        let a = i as f32 / 5.0 * std::f32::consts::TAU;
        p.push(cylr(0.07, 0.7, Vec3::new(a.cos() * 0.28, 0.18, a.sin() * 0.28), Quat::from_rotation_x(1.1) * Quat::from_rotation_y(a), WOOD));
    }
    merged(p)
}

/// A wall torch — a short post with a pitch-wrapped head; the flame cards + point light are
/// spawned alongside ([`spawn_torch`]).
fn torch_post_mesh() -> Mesh {
    merged(vec![
        cylr(0.05, 1.2, Vec3::new(0.0, 0.6, 0.0), Quat::IDENTITY, WOOD_DARK),
        cylr(0.075, 0.14, Vec3::new(0.0, 1.17, 0.0), Quat::IDENTITY, 0x2c2019),
    ])
}

// ── Small utilities ────────────────────────────────────────────────────────────────────

fn pin_sky(clock: &mut crate::scene::SkyClock, t: f32) {
    clock.t = t;
    clock.paused = true;
}
fn world_y(x: f32, z: f32) -> Vec3 {
    Vec3::new(x, crate::worldmap::ground_at_world(x, z).unwrap_or(0.0), z)
}
fn world_y_at(p: Vec2) -> f32 {
    crate::worldmap::ground_at_world(p.x, p.y).unwrap_or(0.0)
}
fn variant_cycle(i: u32) -> OrkVariant {
    match i % 4 {
        0 => OrkVariant::Grunt,
        1 => OrkVariant::Scout,
        2 => OrkVariant::Berserker,
        _ => OrkVariant::Shaman,
    }
}
/// The ork camp nearest the castle (for the flee scene), if any are placed.
fn nearest_camp() -> Option<Vec2> {
    crate::camps::cage_positions()
        .into_iter()
        .map(|(_, centre)| centre)
        .min_by(|a, b| a.length().partial_cmp(&b.length()).unwrap())
}
