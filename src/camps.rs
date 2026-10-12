//! **Ork camps** — one warband camp per wilderness biome (snow, desert, forest, swamp, rock), and
//! no two alike (spec `2026-10-12-wyspa-opowiada-design.md` §1 rule 6). Each [`CampKind`] is its
//! own place with its own Blender model (`tools/blender_forest/ork_camps.py` → `ork_camps.glb`):
//! the forest shamans' ritual ground, desert raiders in a ruined caravanserai, a rocky cave mouth
//! with its tally wall, the swamp's cage deck on stilts over the bog, and a snow hunters' winter
//! camp. Every camp keeps the gameplay contract: a flickering campfire, a faction flag, a mixed
//! warband (`orks.rs`) that fights, flees, brawls rival factions and respawns. Only the camps
//! that keep prisoners (raiders, cave, stilts) have a rescue cage (`villagers::camp_rescue`,
//! tagged here by [`Cage`]); the shamans and the hunters hold none. Camps render only in the
//! Combined world-map view (built from `worldmap::build`, like the castle).
//!
//! Placement ([`plan`]) deterministically reject-samples one flat clearing per biome; the cave
//! looks first for flat ground with the massif rising right behind it, the stilt camp for a bog
//! bank with open pool water in front (both fall back to a plain clearing). The plan is cached in
//! a `OnceLock`; [`in_clearing`] lets the scatter + wildlife keep their props/herds out of the
//! camps, and the story planners keep their distance from [`plan`]. Solid props register in
//! [`crate::blockers`] (per-kind boxes in `LAYOUTS`) so the orks + wildlife route around them.
//! Without the realistic kit the old procedural template stands in.

use std::f32::consts::{FRAC_PI_2, TAU};
use std::sync::OnceLock;

use bevy::camera::visibility::VisibilityRange;
use bevy::mesh::MeshBuilder;
use bevy::prelude::*;

use crate::biome::{Biome, BiomeEntity};
use crate::orks::{self, Faction, VARIANTS};
use crate::palette::lin;
use crate::worldmap::{self, GX, GZ};
use crate::meshkit::tinted;
use crate::game_state::SimAppExt;
use tileworld_core::threat::{threat_for, ThreatKind};

// ── Plugin (campfire flicker + smoke) ────────────────────────────────────────────────

pub struct CampsPlugin;

impl Plugin for CampsPlugin {
    fn build(&self, app: &mut App) {
        // swing_cage_doors + reconcile_cages_on_load are UNGATED: the door swing is cosmetic
        // (a mid-swing door finishing under a pause is harmless), and the load reconcile must
        // fire on the GameLoaded message whenever it lands.
        app.add_systems(Update, (flicker_flames, drift_smoke, swing_cage_doors, reconcile_cages_on_load));
        app.add_systems(Update, reconcile_warbands_on_load
            .after(crate::savegame::RestoreRunSet)
            .before(crate::game_state::SimulationSet));
        app.add_sim_systems(respawn_warbands.run_if(crate::rts::in_campaign)
            .run_if(|ready: Res<crate::biome::WorldReady>| ready.0));
    }
}

/// Ease every cage door toward its `open` target — the rescue "animation": a quick fling that
/// settles (cubic ease-out). The door is a child of the cage frame, so this writes rotation
/// only; the frame (and its blocker) never change.
fn swing_cage_doors(time: Res<Time>, mut q: Query<(&mut Transform, &mut CageDoor)>) {
    let dt = time.delta_secs();
    for (mut tf, mut d) in &mut q {
        let step = dt / CAGE_DOOR_SWING;
        d.t = (d.t + if d.open { step } else { -step }).clamp(0.0, 1.0);
        let s = 1.0 - (1.0 - d.t).powi(3);
        tf.rotation = Quat::from_rotation_y(CAGE_DOOR_OPEN_YAW * s);
    }
}

/// Post-load reconcile: a restored run's cages must match its `rescued_camps` /
/// `blight_captives_freed` flags, whatever state the live world is in (a fresh world rebuild
/// spawns every cage closed + stocked; an in-process Continue may have them open from the dead
/// run). Snap each door to its saved state and despawn the captives of already-freed cages.
fn reconcile_cages_on_load(
    mut ev: MessageReader<crate::savegame::GameLoaded>,
    mut doors: Query<&mut CageDoor>,
    captives: Query<(Entity, &crate::villagers::Captive)>,
    mut commands: Commands,
) {
    let Some(crate::savegame::GameLoaded(data)) = ev.read().last() else { return };
    let freed = |key: CageKey| match key {
        CageKey::Camp(i) => data.rescued_camps.get(i).copied().unwrap_or(false),
        CageKey::Blight(i) => data.blight_captives_freed.get(i).copied().unwrap_or(false),
        CageKey::Decor => false,
    };
    for mut d in &mut doors {
        d.open = freed(d.key);
        d.t = if d.open { 1.0 } else { 0.0 }; // snap — no ghost swing on load
    }
    for (e, c) in &captives {
        if freed(c.key) {
            commands.entity(e).try_despawn(); // rescued long ago — walked home already
        }
    }
}

/// Spawn one prisoner cage: the natural-timber frame (`ork_fortress::cage_mesh`), the separate
/// hinged door child, and `captives` REAL seated peasants inside
/// (`villagers::spawn_cage_captive`, one per `ork_fortress::CAGE_SEATS` straw bed). A rescue
/// opens the door by ANIMATION and walks the peasants out — nothing about the cage is swapped
/// or despawned. Callers register their own collision blocker (footprints differ per site).
#[allow(clippy::too_many_arguments)]
pub fn spawn_cage(
    commands: &mut Commands,
    meshes: &mut Assets<Mesh>,
    creature_mats: &mut Assets<crate::creature::CreatureMaterial>,
    prop_mat: &Handle<StandardMaterial>,
    tf: Transform,
    key: CageKey,
    captives: usize,
    seed: u32,
    open: bool,
) -> Entity {
    use crate::ork_fortress::{cage_door_mesh, cage_mesh, CAGE_BAR_SPOTS, CAGE_SEATS, CAGE_W};
    let mut rng = seed | 1;
    let kit = crate::realforest::get().filter(|k| k.has("ork_cage"));
    // The cage's muffled voice clock (`audio::captive`) rides the frame — one per cage, so two
    // decor cages sharing `CageKey::Decor` still keep their own time.
    let voice = crate::audio::CageVoice::new(seed);
    let root = match kit {
        // Realistic forest: the Blender cage (same 2.2 x 1.8 frame, open on +X, beds on the seats).
        Some(k) => {
            let mut e = commands.spawn((tf, Cage { key }, voice, BiomeEntity));
            k.attach_static(&mut e, "ork_cage", Transform::IDENTITY);
            e.id()
        }
        None => commands
            .spawn((Mesh3d(meshes.add(cage_mesh(&mut rng))), MeshMaterial3d(prop_mat.clone()), tf, Cage { key }, voice, BiomeEntity))
            .id(),
    };
    // The door hangs just proud of the (+X, +Z) corner post. No BiomeEntity of its own — it
    // despawns with the frame (child cascade), and a second tag would double-despawn.
    let door_tf = Transform::from_translation(v(CAGE_W / 2.0 + 0.07, 0.0, CAGE_W / 2.0));
    // `open` pre-opens the door (the `FOREST_CAGETEST` after-state cage) — it eases from shut on
    // the first frames, which is invisible during boot.
    let door = match kit {
        Some(k) => {
            let mut e = commands.spawn((door_tf, CageDoor { key, open, t: 0.0 }));
            k.attach_static(&mut e, "ork_cage_door", Transform::IDENTITY);
            e.id()
        }
        None => commands
            .spawn((
                Mesh3d(meshes.add(cage_door_mesh(&mut rng))),
                MeshMaterial3d(prop_mat.clone()),
                door_tf,
                CageDoor { key, open, t: 0.0 },
            ))
            .id(),
    };
    commands.entity(root).add_child(door);
    // The captives: real peasants seated on the straw beds (roots of their own — they stand up
    // and WALK OUT on rescue, so they can't be children of the frame). Each gets its berth — the
    // seat plus its own spot at the bars — so its idle life (`captives`) can get up, shuffle over,
    // grip the bars and come back without leaving the footprint or walking into a cage-mate. The
    // seated hips height matches the bedding: the Blender cage's straw is a low flat bed (top
    // ≈0.22), the procedural one heaps it to ≈0.51.
    let sit_h = if kit.is_some() { crate::captives::SIT_H_FLAT_STRAW } else { crate::captives::SIT_H_HEAPED_STRAW };
    let yaw_of = |q: Quat| {
        let f = q * Vec3::Z;
        f.x.atan2(f.z)
    };
    for ((sx, sz, syaw), (bx, bz, byaw)) in CAGE_SEATS.iter().zip(CAGE_BAR_SPOTS).take(captives) {
        let seat = tf.transform_point(v(*sx, 0.148, *sz)); // on the plank floor
        let facing = tf.rotation * ry(*syaw);
        let berth = crate::captives::Berth {
            seat,
            seat_yaw: yaw_of(facing),
            bars: tf.transform_point(v(bx, 0.148, bz)),
            bars_yaw: yaw_of(tf.rotation * ry(byaw)),
            cage: Vec2::new(tf.translation.x, tf.translation.z),
            sit_h,
        };
        crate::villagers::spawn_cage_captive(commands, meshes, creature_mats, berth, key, next_u32(&mut rng));
    }
    root
}

/// Campfire flame marker — also the anchor the audio module hangs a spatial campfire loop
/// (+ war-drum sink) on. `pub(crate)` phase: the ork fortress (`ork_fortress.rs`) tags its
/// bonfire with this same component precisely to inherit that audio lifecycle.
#[derive(Component)]
pub struct Flicker {
    pub(crate) phase: f32,
}
#[derive(Component)]
struct CampSmoke {
    base: Vec3,
    phase: f32,
    speed: f32,
}

/// Which prisoner cage an entity belongs to — shared by the cage frame ([`Cage`]), its hinged
/// door ([`CageDoor`]) and the seated peasants inside (`villagers::Captive`), so a rescue can
/// address all three parts of one cage.
#[derive(Component, Clone, Copy, PartialEq, Eq, Debug)]
pub enum CageKey {
    /// A wilderness camp's cage — the enumerate index of [`plan`] (the same index
    /// [`cage_positions`] and `villagers::camp_rescue` use).
    Camp(usize),
    /// A Blight cage outside Gnashfang Hold — the `ork_fortress::BLIGHT_CAGES` slot.
    Blight(usize),
    /// Decorative only (the Hold's own hoard-cage, the `FOREST_CAGETEST` stage) — never freed.
    Decor,
}

/// Tags the prisoner-cage FRAME. The frame persists through a rescue — opening is the hinged
/// [`CageDoor`] child swinging (an animation), never a model swap.
#[derive(Component)]
pub struct Cage {
    pub key: CageKey,
}

/// The cage's hinged door (a child of the frame, hung at the (+X, +Z) corner post). A rescue
/// sets `open`; [`swing_cage_doors`] eases the yaw so the door visibly swings out.
#[derive(Component)]
pub struct CageDoor {
    pub key: CageKey,
    /// Target state — set true by the rescue systems (or snapped by the save-load reconcile).
    pub open: bool,
    /// Swing progress 0 (shut) → 1 (fully open). Snap to 1.0 to open instantly (load reconcile).
    pub t: f32,
}

/// How far the door swings (rad about the hinge post; negative = outward past perpendicular).
const CAGE_DOOR_OPEN_YAW: f32 = -2.05;
/// Full swing duration (s).
const CAGE_DOOR_SWING: f32 = 1.4;

/// Seconds after a camp's warband is wiped before it repopulates. 3× the old 60s (TS
/// `OrkCamp.tsx` used 60) so clearing a camp buys real breathing room instead of an endless
/// treadmill of fresh orks.
const CAMP_RESPAWN_DELAY: f32 = 180.0;
/// The hero must be at least this far (world units) from a camp for it to repopulate, so a cleared
/// warband returns OUT OF SIGHT rather than in front of the player (TS `CAMP_RESPAWN_FAR` = 40).
const CAMP_RESPAWN_FAR: f32 = 40.0;

/// The prebuilt ork [`orks::Armory`] kept alive past [`build`] so a wiped warband can respawn, plus
/// each camp's clear timestamp (`Some(t)` once it has zero living orks, `None` while populated).
/// Captives are deliberately NOT tracked here — a freed cage stays open and empty, matching the
/// original: a camp's prisoners are a one-time rescue, the warband a renewable threat.
#[derive(Resource)]
pub(crate) struct CampWarbands {
    /// The prebuilt ork mesh/material armory — also reused by `landmarks.rs` to summon Rune-Trial
    /// guardians (camp-style orks home-anchored at a landmark).
    pub(crate) armory: orks::Armory,
    cleared_at: Vec<Option<f32>>,
    /// A clear is real only after the warband has been observed alive (startup/load safety).
    seen: Vec<bool>,
}

fn flicker_flames(time: Res<Time>, mut q: Query<(&Flicker, &mut Transform)>) {
    let t = time.elapsed_secs();
    for (f, mut tf) in &mut q {
        let sx = 1.0 + (t * 7.0 + f.phase).sin() * 0.12 + (t * 14.3 + f.phase).sin() * 0.06;
        let sy = 1.0 + (t * 9.5 + f.phase).sin() * 0.22;
        tf.scale = Vec3::new(sx, sy, sx);
    }
}

fn drift_smoke(time: Res<Time>, mut q: Query<(&CampSmoke, &mut Transform)>) {
    let t = time.elapsed_secs();
    for (s, mut tf) in &mut q {
        let cycle = (t * s.speed + s.phase).rem_euclid(1.0);
        tf.translation.x = s.base.x + (t * 0.7 + s.phase * 6.0).sin() * 0.18 * cycle;
        tf.translation.z = s.base.z + (t * 0.6 + s.phase * 6.0).cos() * 0.18 * cycle;
        tf.translation.y = s.base.y + cycle * 1.6;
        let sc = (0.1 + cycle * 0.4) * (1.0 - cycle).max(0.0);
        tf.scale = Vec3::splat(sc.max(0.001));
    }
}

// ── Layouts (one per camp kind) ───────────────────────────────────────────────────

/// What kind of camp a biome's warband keeps — every camp is its own place (spec
/// `2026-10-12-wyspa-opowiada-design.md` §1 rule 6), not a copy of one template.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum CampKind {
    /// FOREST — the shamans' ritual ground: bone circle, totems, charm tree, drum. No cage.
    Shaman,
    /// DESERT — raiders in a ruined caravanserai with the loot of the Pasha's caravans.
    Raiders,
    /// ROCKY — a warband living in a cave mouth (backed onto the massif when a cliff is found);
    /// the tally wall inside.
    Cave,
    /// SWAMP — the cage camp: cages on a stilt deck over the bog water, food set out for them.
    Stilts,
    /// SNOW — a winter hunters' camp: yurts, drying racks, a frozen fishing pond, a carcass. No cage.
    Hunters,
}

impl CampKind {
    fn of(b: Biome) -> CampKind {
        match b {
            Biome::Forest => CampKind::Shaman,
            Biome::Desert => CampKind::Raiders,
            Biome::Rocky => CampKind::Cave,
            Biome::Swamp => CampKind::Stilts,
            _ => CampKind::Hunters,
        }
    }
}

/// A camp kind's fixed anchors, camp-local (centre = origin, rotated by the site yaw). The
/// Blender model (`tools/blender_forest/ork_camps.py`) is authored around these same numbers —
/// change both together.
struct Layout {
    /// Kit model (`assets/forest_pbr/ork_camps.glb`).
    model: &'static str,
    /// Fire centre (the emissive flame + smoke + firelight + the audio campfire anchor).
    fire: Vec3,
    /// Where the faction flag hangs (top of the model's banner pole).
    flag: Vec3,
    /// The rescue cage (captives inside), `(position incl. deck height, local yaw)`. Its door
    /// opens on the cage's local +X, so the yaw also aims where the freed captives walk out.
    cage: Option<(Vec3, f32)>,
    /// Extra empty cages (decor, never freed).
    spare_cages: &'static [(Vec3, f32)],
    /// Warband spawn / idle anchors, one per `orks::VARIANTS` entry.
    warband: [(f32, f32); 4],
    /// Solid props: (x, z, half-width, half-depth, local yaw).
    blockers: &'static [(f32, f32, f32, f32, f32)],
    /// Camp-local footprint `(x0, x1, z0, z1)` the scatter keeps out of (the cave's rock runs far
    /// back into the slope, the stilt deck out over the water).
    foot: (f32, f32, f32, f32),
}

const FOOT: (f32, f32, f32, f32) = (-CLEAR_HALF, CLEAR_HALF, -CLEAR_HALF, CLEAR_HALF);

/// Deck top of the swamp camp's stilt platform (`ork_camps.py` DECK_Y).
const STILT_DECK_Y: f32 = 0.6;

const LAYOUTS: [Layout; 5] = [
    Layout {
        model: "ork_camp_shaman",
        fire: Vec3::new(0.0, 0.0, 0.0),
        flag: Vec3::new(-2.0, 2.5, -3.2),
        cage: None,
        spare_cages: &[],
        warband: [(1.9, -0.6), (-1.7, -0.9), (0.9, 1.9), (-1.2, 1.5)],
        blockers: &[
            (-3.3, -1.9, 0.3, 0.3, 0.0),
            (3.2, -2.2, 0.3, 0.3, 0.0),
            (0.4, 3.75, 0.3, 0.3, 0.0),
            (-3.7, 2.5, 0.35, 0.35, 0.0),
            (2.45, 1.75, 0.6, 0.6, 0.0),
            (-0.5, -4.3, 1.4, 1.4, 0.0),
            (1.75, -3.5, 0.7, 0.4, 0.15),
        ],
        foot: FOOT,
    },
    Layout {
        model: "ork_camp_raiders",
        fire: Vec3::new(0.9, 0.0, 0.7),
        flag: Vec3::new(3.0, 2.5, -1.2),
        cage: Some((Vec3::new(-3.3, 0.0, 1.0), 0.0)),
        spare_cages: &[],
        warband: [(2.2, -1.0), (-1.6, -0.6), (2.6, 2.4), (-0.4, 2.6)],
        blockers: &[
            (-3.43, -4.6, 1.9, 0.3, 0.0),
            (3.13, -4.6, 1.6, 0.3, 0.0),
            (-1.25, -4.6, 0.32, 0.36, 0.0),
            (1.25, -4.6, 0.32, 0.36, 0.0),
            (0.1, -3.45, 1.9, 0.75, 0.0),
            (-5.3, -1.2, 0.3, 3.4, 0.0),
            (4.7, -3.4, 0.3, 1.2, 0.0),
            (2.6, -3.4, 0.4, 0.3, 0.3),
        ],
        foot: FOOT,
    },
    Layout {
        model: "ork_camp_cave",
        fire: Vec3::new(0.2, 0.0, -1.0),
        flag: Vec3::new(-3.1, 2.5, -0.4),
        cage: Some((Vec3::new(1.25, 0.0, -4.5), -FRAC_PI_2)),
        spare_cages: &[],
        warband: [(1.8, 0.6), (-1.6, 0.0), (0.4, 2.0), (-1.0, -3.9)],
        blockers: &[
            (-5.6, -5.0, 2.6, 2.6, 0.0),
            (5.6, -5.0, 2.6, 2.6, 0.0),
            (0.0, -7.6, 3.4, 1.0, 0.0),
            (-4.6, -2.0, 1.2, 0.5, 0.0),
            (4.6, -2.0, 1.2, 0.5, 0.0),
            (2.9, -0.9, 0.3, 0.85, 0.0),
        ],
        foot: (-8.8, 8.8, -11.5, CLEAR_HALF),
    },
    Layout {
        model: "ork_camp_stilts",
        fire: Vec3::new(0.6, 0.0, -1.4),
        flag: Vec3::new(3.45, 2.5, 2.55),
        cage: Some((Vec3::new(-1.6, STILT_DECK_Y, 4.7), FRAC_PI_2)),
        spare_cages: &[(Vec3::new(1.7, STILT_DECK_Y, 4.8), FRAC_PI_2)],
        warband: [(1.8, -0.8), (-1.6, -0.4), (2.4, -3.0), (0.1, 0.9)],
        blockers: &[
            (0.0, 4.8, 3.7, 2.5, 0.0),
            (-3.5, 1.1, 0.4, 1.5, 0.35),
            (-2.7, -2.0, 0.35, 1.0, 0.0),
            (-3.0, -4.0, 1.2, 1.0, 0.0),
        ],
        foot: (-CLEAR_HALF, CLEAR_HALF, -CLEAR_HALF, 8.0),
    },
    Layout {
        model: "ork_camp_hunters",
        fire: Vec3::new(0.0, 0.0, 0.0),
        flag: Vec3::new(-3.2, 3.2, -2.6),
        cage: None,
        spare_cages: &[],
        warband: [(1.5, -0.7), (-1.6, 0.5), (0.3, 1.7), (-0.9, -1.9)],
        blockers: &[
            (-3.2, -2.6, 1.7, 1.7, 0.0),
            (3.1, -3.0, 1.4, 1.4, 0.0),
            (-3.9, 1.4, 0.3, 1.1, 0.0),
            (-2.2, 2.9, 0.65, 0.3, 2.4),
            (-0.4, -4.1, 0.5, 0.5, 0.0),
        ],
        foot: FOOT,
    },
];

fn layout(kind: CampKind) -> &'static Layout {
    &LAYOUTS[match kind {
        CampKind::Shaman => 0,
        CampKind::Raiders => 1,
        CampKind::Cave => 2,
        CampKind::Stilts => 3,
        CampKind::Hunters => 4,
    }]
}

// ── Placement ─────────────────────────────────────────────────────────────────────

#[derive(Clone, Copy)]
pub struct CampSite {
    pub(crate) centre: Vec2,
    biome: Biome,
    kind: CampKind,
    faction: Faction,
    rot: f32,
    seed: u32,
}

impl CampSite {
    /// Camp-local `(x, z)` → world XZ.
    fn world(&self, local: Vec3) -> Vec2 {
        let w = Quat::from_rotation_y(self.rot) * Vec3::new(local.x, 0.0, local.z);
        self.centre + Vec2::new(w.x, w.z)
    }
}

static SITES: OnceLock<Vec<CampSite>> = OnceLock::new();

/// Half-extent (world units) of a camp's reserved clearing — scatter + wildlife stay out.
const CLEAR_HALF: f32 = 5.2;

/// Plan one camp per wilderness biome (cached). Pure tile-map queries, so it's deterministic
/// and stable across biome-switch rebuilds. Call before scatter so clearings get reserved.
/// The ORDER (snow, desert, forest, swamp, rock) is the camp index saves key `rescued_camps` by.
pub fn plan() -> &'static [CampSite] {
    SITES
        .get_or_init(|| {
            let targets = [Biome::Snow, Biome::Desert, Biome::Forest, Biome::Swamp, Biome::Rocky];
            let mut rng = 0xca37_5eedu32;
            let mut placed: Vec<CampSite> = Vec::new();
            for (i, b) in targets.iter().enumerate() {
                let faction = if i % 2 == 0 { Faction::Red } else { Faction::Blue };
                let kind = CampKind::of(*b);
                let mut found = None;
                // The cave wants a cliff at its back and the stilt camp open bog water at its
                // front; when no such spot exists they fall back to an ordinary flat clearing
                // (the cave model is a freestanding outcrop, the deck then stands over dry reeds).
                // The cave wants a cliff at its back, the stilt camp open bog water at its front,
                // the hunters a level shelf in the snow: settings rare enough that they're found by
                // a full grid scan (one pick among every valid spot), not by random darts. When
                // none exists they fall back to an ordinary flat clearing (the cave model is a
                // freestanding outcrop, the deck then stands over dry reeds).
                if matches!(kind, CampKind::Cave | CampKind::Stilts | CampKind::Hunters) {
                    let mut options = Vec::new();
                    let mut z = -GZ + 8.0;
                    while z < GZ - 8.0 {
                        let mut x = -GX + 8.0;
                        while x < GX - 8.0 {
                            let rot0 = rng_range(&mut rng, 0.0, TAU);
                            if let Some(rot) = site_ok(x, z, *b, kind, true, rot0, &placed) {
                                options.push((x, z, rot));
                            }
                            x += 1.5;
                        }
                        z += 1.5;
                    }
                    if !options.is_empty() {
                        found = Some(options[next_u32(&mut rng) as usize % options.len()]);
                        info!("camps: {:?} found its own setting ({} spots)", kind, options.len());
                        #[cfg(test)]
                        eprintln!("camps: {:?} found its own setting ({} spots)", kind, options.len());
                    }
                }
                if found.is_none() {
                    for _ in 0..8000 {
                        let cx = rng_range(&mut rng, -GX + 8.0, GX - 8.0);
                        let cz = rng_range(&mut rng, -GZ + 8.0, GZ - 8.0);
                        let rot0 = rng_range(&mut rng, 0.0, TAU);
                        if let Some(rot) = site_ok(cx, cz, *b, kind, false, rot0, &placed) {
                            found = Some((cx, cz, rot));
                            break;
                        }
                    }
                }
                if let Some((cx, cz, rot)) = found {
                    info!("camps: {:?} at {cx:.1},{cz:.1}", kind);
                    let seed = next_u32(&mut rng);
                    placed.push(CampSite { centre: Vec2::new(cx, cz), biome: *b, kind, faction, rot, seed });
                } else {
                    info!("camps: no site found for {:?}", b);
                }
            }
            placed
        })
        .as_slice()
}

/// Does camp `index` keep a rescue cage (captives to free)? The shamans' ground and the hunters'
/// winter camp hold no prisoners.
pub fn has_cage(index: usize) -> bool {
    plan().get(index).is_some_and(|s| layout(s.kind).cage.is_some())
}

/// A nearby, manageable first expedition — the nearest camp that HAS captives to free (the
/// opening objective is a rescue). Stable for the run, independent of hero movement.
pub fn intro_target() -> Option<usize> {
    let spawn = crate::player::spawn_point().0;
    plan().iter().enumerate()
        .filter(|(i, _)| has_cage(*i))
        .min_by(|(_, a), (_, b)| a.centre.distance_squared(spawn).total_cmp(&b.centre.distance_squared(spawn)))
        .map(|(i, _)| i)
}

pub fn camp_centre(index: usize) -> Option<Vec2> {
    plan().get(index).map(|s| s.centre)
}

/// One camp stages the announced specialists. Biomes are retained on the site, so a failed
/// placement cannot shift every camp's identity. The arson introduction uses a fresh camp.
pub fn raid_target(next_night: i32) -> Option<usize> {
    let kind = threat_for(next_night.max(0) as usize).kind;
    if kind == ThreatKind::Recon { return intro_target(); }
    let preferred: &[Biome] = match kind {
        ThreatKind::Arson => &[Biome::Forest, Biome::Desert, Biome::Rocky, Biome::Snow, Biome::Swamp],
        ThreatKind::Ritual => &[Biome::Forest, Biome::Swamp, Biome::Desert, Biome::Snow, Biome::Rocky],
        ThreatKind::Flank => &[Biome::Desert, Biome::Forest, Biome::Snow, Biome::Rocky, Biome::Swamp],
        ThreatKind::Breakers => &[Biome::Rocky, Biome::Snow, Biome::Desert, Biome::Forest, Biome::Swamp],
        ThreatKind::Recon => unreachable!(),
    };
    let avoid_intro = kind == ThreatKind::Arson && next_night == 1 && plan().len() > 1;
    preferred.iter().find_map(|biome| plan().iter().enumerate()
        .find(|(i, s)| s.biome == *biome && (!avoid_intro || Some(*i) != intro_target()))
        .map(|(i, _)| i))
}

/// Camp work only changes the night it was done for; permanent captive flags are separate.
pub fn raid_cleared(campaign: &tileworld_core::campaign::Campaign, next_night: usize) -> bool {
    campaign.raid_day == next_night as i32
        && raid_target(next_night as i32).is_some_and(|i| campaign.cleared_camps.get(i).copied().unwrap_or(false))
}

/// Each camp's `(prisoner-cage world XZ, camp-centre world XZ)`, index-aligned with [`plan`] —
/// the rescue interaction walks up to the cage, and the centre is used to test whether the
/// warband guarding it is cleared. A camp without a cage ([`has_cage`] false) reports its centre
/// as the cage spot; `villagers::camp_rescue` skips it.
pub fn cage_positions() -> Vec<(Vec2, Vec2)> {
    plan()
        .iter()
        .map(|s| {
            let cage = layout(s.kind).cage.map_or(s.centre, |(p, _)| s.world(p));
            (cage, s.centre)
        })
        .collect()
}

/// True if `(wx, wz)` is inside any planned camp's footprint (the kind's camp-local box,
/// rotated with the site).
pub fn in_clearing(wx: f32, wz: f32) -> bool {
    near_camp(wx, wz, 0.0)
}

/// True if a circle of radius `r` at `(wx, wz)` touches any planned camp's footprint — the
/// scatter keep-out (`realforest::keep_clear`).
pub fn near_camp(wx: f32, wz: f32, r: f32) -> bool {
    let Some(sites) = SITES.get() else { return false };
    sites.iter().any(|c| {
        let l = Quat::from_rotation_y(-c.rot) * Vec3::new(wx - c.centre.x, 0.0, wz - c.centre.y);
        let (x0, x1, z0, z1) = layout(c.kind).foot;
        l.x >= x0 - r && l.x <= x1 + r && l.z >= z0 - r && l.z <= z1 + r
    })
}

/// A candidate `(cx, cz)` is a valid camp centre for `biome` if a flat clearing of base-height
/// land sits there, clear of the castle + central safe-zone + other camps, and it's in the biome
/// (or on grass within ~8 tiles of it, for the mountainous biomes). `special` asks for the kind's
/// own setting — a cliff behind the cave (local −Z), bog water in front of the stilt deck (local
/// +Z) — and returns the yaw that faces it; otherwise `rot0` is kept. `None` = rejected.
fn site_ok(cx: f32, cz: f32, biome: Biome, kind: CampKind, special: bool, rot0: f32, placed: &[CampSite]) -> Option<f32> {
    let h0 = worldmap::ground_at_world(cx, cz)?;
    // Flat base ground only (avoids plateaus + mountain terraces) — except the hunters, who
    // winter up in the snow: the snow biome's valley floor is a bare alpine meadow.
    if h0 > 0.01 && !(special && kind == CampKind::Hunters) {
        return None;
    }
    // Keep camps off the castle's doorstep — the biome blobs sit 70+ units out, so this only
    // rejects the too-close apron, never a real biome clearing.
    if crate::castle::in_footprint(cx, cz) || Vec2::new(cx, cz).length() < 60.0 || crate::rival::near_fort(cx, cz) {
        return None;
    }
    // The Blight is Gnashfang Hold's own ground (it reads as Swamp to `biome_at_world`).
    if crate::ork_fortress::in_blight_world(cx, cz) {
        return None;
    }
    if placed.iter().any(|c| c.centre.distance(Vec2::new(cx, cz)) < 18.0) {
        return None;
    }
    let on_biome = worldmap::biome_at_world(cx, cz) == Some(biome);
    let near = |r: i32| on_biome || (worldmap::is_grass_world(cx, cz) && biome_within(cx, cz, biome, r));
    // Flat dry ground over camp-local x ∈ [x0, x1], z ∈ [z0, z1] at yaw `rot`.
    let flat = |rot: f32, (x0, x1, z0, z1): (i32, i32, i32, i32), tol: f32| {
        let q = Quat::from_rotation_y(rot);
        (z0..=z1).all(|dz| (x0..=x1).all(|dx| {
            let w = q * Vec3::new(dx as f32, 0.0, dz as f32);
            worldmap::ground_at_world(cx + w.x, cz + w.z).is_some_and(|h| (h - h0).abs() < tol)
        }))
    };
    let at = |rot: f32, x: f32, z: f32| {
        let w = Quat::from_rotation_y(rot) * Vec3::new(x, 0.0, z);
        Vec2::new(cx + w.x, cz + w.z)
    };
    match (kind, special) {
        (CampKind::Cave, true) => {
            // Cheap first: is there a wall anywhere close (8 bearings, 11u out)?
            let wall = (0..8).any(|k| {
                let a = k as f32 * TAU / 8.0;
                worldmap::ground_at_world(cx + a.sin() * 11.0, cz + a.cos() * 11.0).is_some_and(|h| h - h0 > 3.0)
            });
            if !wall || !near(12) {
                return None;
            }
            // The mouth needs flat ground in front and 4u into the rock; the mountain must rise
            // steeply right behind it (≥0.8u by 8u back, ≥3u by 11u) so the shell backs into it.
            (0..16).map(|k| rot0 + k as f32 * TAU / 16.0).find(|&rot| {
                flat(rot, (-4, 4, -4, 4), 0.12)
                    && [-2.5, 0.0, 2.5].iter().all(|&x| {
                        let rise = |z: f32| {
                            let p = at(rot, x, z);
                            worldmap::ground_at_world(p.x, p.y).map_or(f32::NEG_INFINITY, |h| h - h0)
                        };
                        rise(-8.0) > 0.8 && rise(-11.0) > 3.0
                    })
            })
        }
        (CampKind::Hunters, true) => {
            // A level shelf above the snow line (snow on the ground round the yurts).
            (on_biome && h0 > 1.0 && crate::alpine::snow_cover(cx, cz) >= 0.2 && flat(rot0, (-5, 5, -5, 5), 0.35)).then_some(rot0)
        }
        (CampKind::Stilts, true) => {
            let wet = (0..8).any(|k| {
                let a = k as f32 * TAU / 8.0;
                worldmap::pool_sd_world(cx + a.sin() * 5.0, cz + a.cos() * 5.0) < -0.2
            });
            if !on_biome || !wet {
                return None;
            }
            // Dry bank behind (local z ≤ 1), open bog water under the deck (z 4..7).
            (0..16).map(|k| rot0 + k as f32 * TAU / 16.0).find(|&rot| {
                flat(rot, (-4, 4, -4, 0), 0.12)
                    && [-2.0, 0.0, 2.0].iter().all(|&x| {
                        [4.5, 6.0].iter().all(|&z| {
                            let p = at(rot, x, z);
                            worldmap::pool_sd_world(p.x, p.y) < -0.2
                        })
                    })
            })
        }
        _ => {
            // Forest and desert camps stand IN their biome; the mountain biomes may use the
            // grass apron at their edge.
            let on = if matches!(kind, CampKind::Shaman | CampKind::Raiders) { on_biome } else { near(8) };
            if !on {
                return None;
            }
            // ±5: the whole camp must stand on dry, level land (a beach site put half a camp in
            // the sea). The cave's shell reaches further back, so it checks its own depth.
            let depth = if kind == CampKind::Cave { (-5, 5, -7, 5) } else { (-5, 5, -5, 5) };
            flat(rot0, depth, 1e-3).then_some(rot0)
        }
    }
}

/// True if `biome` occurs on any tile within `r` tiles of `(cx, cz)`.
fn biome_within(cx: f32, cz: f32, biome: Biome, r: i32) -> bool {
    for dz in -r..=r {
        for dx in -r..=r {
            if worldmap::biome_at_world(cx + dx as f32, cz + dz as f32) == Some(biome) {
                return true;
            }
        }
    }
    false
}

// ── Build ────────────────────────────────────────────────────────────────────────

/// Build every planned camp: props (registering blockers) + the warband. Tagged `BiomeEntity`
/// so the biome switch despawns/rebuilds them. Called from `worldmap::build` after the castle.
pub fn build(
    commands: &mut Commands,
    meshes: &mut Assets<Mesh>,
    images: &mut Assets<Image>,
    materials: &mut Assets<StandardMaterial>,
    creature_mats: &mut Assets<crate::creature::CreatureMaterial>,
) {
    let sites = plan();
    if sites.is_empty() {
        return;
    }

    // The orks draw against the shared creature material (per-surface texture from the surf code).
    let mat = crate::creature::make_creature_material(creature_mats);
    // The fallback props (tents, cage, banner, fire ring) carry a FAINT grime-grain detail
    // texture multiplied over their vertex colours — same trick as Gnashfang Hold.
    let grime = crate::biome::GroundDetail {
        scale: 1.0,
        strength: 0.16,
        variation: 0.5,
        seed: 13.0,
        dark: 0x9c968c,
        base: 0xc2bcb0,
        light: 0xe6e0d4,
        grain: 0.6,
        streak: 0.5,
    };
    let (grime_img, _) = crate::terrain::detail_image(&grime);
    let grime_tex = images.add(grime_img);
    let prop_mat = materials.add(StandardMaterial {
        base_color: Color::WHITE,
        base_color_texture: Some(grime_tex),
        perceptual_roughness: 0.95,
        ..default()
    });
    // Emissive flame (bloom-lit, like the castle torches) + translucent smoke.
    // Fire: crossed alpha flame cards (a painted tongue-of-flame texture, HDR-bright so it blooms),
    // never a solid cone. Double-sided, unlit, no shadows; the `Flicker` scale wobble animates it.
    let flame_tex = images.add(flame_card_image());
    let flame_mat = materials.add(StandardMaterial {
        base_color: Color::linear_rgb(5.0, 2.6, 1.1),
        base_color_texture: Some(flame_tex),
        alpha_mode: AlphaMode::Blend,
        unlit: true,
        double_sided: true,
        cull_mode: None,
        ..default()
    });
    let flame_cards = meshes.add(flame_card_mesh());
    let smoke_mat = materials.add(StandardMaterial {
        base_color: Color::srgba(0.55, 0.55, 0.57, 0.4),
        alpha_mode: AlphaMode::Blend,
        unlit: true,
        ..default()
    });
    let smoke_puff = meshes.add(Sphere::new(0.5).mesh().ico(1).unwrap());

    let armory = orks::Armory::new(meshes, materials, mat.clone());

    // Screenshot hook: `FOREST_ORKLINE="x,z"` parks one ork of each variant in a line at the
    // given world XZ, each home-anchored on its own spot so it idles in place for the shot —
    // pair with `FOREST_CAM` to frame the warband close up.
    if let Ok(s) = std::env::var("FOREST_ORKLINE") {
        let p: Vec<f32> = s.split(',').filter_map(|t| t.trim().parse().ok()).collect();
        if p.len() == 2 {
            for (i, variant) in VARIANTS.iter().enumerate() {
                let pos = Vec2::new(p[0] + i as f32 * 1.8 - 2.7, p[1]);
                armory.spawn(commands, *variant, Faction::Red, pos, pos, 11 + i as u32);
            }
            // + one seated ork at the end of the line (verifies the sit pose on a stump).
            let (sx, sz) = (p[0] + 4.0 * 1.8 - 2.7, p[1]);
            let sy = worldmap::ground_at_world(sx, sz).unwrap_or(0.0);
            armory.spawn_seated(commands, crate::orks::OrkVariant::Grunt, Faction::Red, Vec3::new(sx, sy, sz), 0.0);
        }
    }

    // Screenshot hook: `FOREST_CAGETEST="x,z"` parks the rescue's before/after states side by
    // side at the given world XZ: a CLOSED cage full of seated peasant captives, and 5.5u
    // further +X an OPEN, emptied one — so one still verifies the captive models, the natural
    // frame and the swung door. (The swing ANIMATION itself films best via the real rescue:
    // `FOREST_DEMO=rescue` + `FOREST_CLIP`.) Both doors face +X; frame from the east.
    if let Ok(s) = std::env::var("FOREST_CAGETEST") {
        let p: Vec<f32> = s.split(',').filter_map(|t| t.trim().parse().ok()).collect();
        if p.len() == 2 {
            for (dx, open) in [(0.0, false), (5.5, true)] {
                let (x, z) = (p[0] + dx, p[1]);
                let y = worldmap::ground_at_world(x, z).unwrap_or(0.0);
                info!("FOREST_CAGETEST cage at {x:.1},{y:.2},{z:.1} (open: {open})"); // for FOREST_CAM framing
                spawn_cage(
                    commands,
                    meshes,
                    creature_mats,
                    &prop_mat,
                    Transform::from_xyz(x, y, z),
                    CageKey::Decor,
                    if open { 0 } else { crate::ork_fortress::CAGE_SEATS.len() },
                    0xca6e_7e57 + dx as u32,
                    open,
                );
            }
        }
    }

    // The camp models cull like the story set-pieces, a little later (a lit camp reads far off).
    let range = VisibilityRange { start_margin: 0.0..0.0, end_margin: 160.0..190.0, use_aabb: true };
    for (camp, site) in sites.iter().enumerate() {
        let lay = layout(site.kind);
        // Logged so staging tools (screenshot framing, debugging) can find each camp.
        info!("camp {camp} ({:?}) at {:.1},{:.1} yaw {:.2}", site.kind, site.centre.x, site.centre.y, site.rot);
        let rot_q = Quat::from_rotation_y(site.rot);
        let cy = worldmap::ground_at_world(site.centre.x, site.centre.y).unwrap_or(0.0);
        let centre3 = Vec3::new(site.centre.x, cy, site.centre.y);
        let place = |local: Vec3| centre3 + rot_q * local;

        // The camp itself: one merged Blender model per camp kind (`ork_camps.glb`). Without the
        // realistic kit, the old procedural template stands in (tent, banner, skull spikes, fire).
        let kit = crate::realforest::get();
        let modelled = kit
            .and_then(|k| k.spawn_static_with(commands, lay.model, Transform::from_translation(centre3).with_rotation(rot_q), range.clone()))
            .map(|e| { commands.entity(e).insert(BiomeEntity); })
            .is_some();
        if modelled {
            for &(x, z, hw, hd, yaw) in lay.blockers {
                let w = place(v(x, 0.0, z));
                crate::blockers::add_obb(w.x, w.z, hw, hd, site.rot + yaw);
            }
        } else {
            build_fallback_props(commands, meshes, &prop_mat, site, lay, &place);
        }
        crate::blockers::reserve_visual(site.centre.x, site.centre.y, CLEAR_HALF + 1.0);

        // The prisoner cage: the fortress frame + hinged door + a full cage of real seated
        // peasants (`spawn_cage`). It blocks like any solid prop — you walk UP TO it to rescue,
        // not through it. The blocker set is append-only, so the frame stays solid after the
        // door opens too (an opened cage is a fine wall; the peasants leave through the door
        // mouth, which sits outside the box). Only the camps that keep prisoners have one.
        let cages = lay.cage.iter().map(|c| (*c, true)).chain(lay.spare_cages.iter().map(|c| (*c, false)));
        for (k, ((local, yaw), real)) in cages.enumerate() {
            let w = place(local);
            spawn_cage(
                commands,
                meshes,
                creature_mats,
                &prop_mat,
                Transform { translation: w, rotation: rot_q * ry(yaw), scale: Vec3::ONE },
                if real { CageKey::Camp(camp) } else { CageKey::Decor },
                if real { crate::villagers::CAMP_RESCUE_POP as usize } else { 0 },
                site.seed ^ 0xca6e_0000 ^ (k as u32 * 0x51),
                false,
            );
            crate::blockers::add_obb(w.x, w.z, 1.2, 1.2, site.rot + yaw);
        }

        // The banner's cloth — a fluttering faction flag on the model's banner pole.
        let flag = crate::banner::spawn_flag(commands, meshes, materials, place(lay.flag), 0.8, 0.5, site.faction.hex(), Some(0x2a2118));
        commands.entity(flag).insert(BiomeEntity);

        // Campfire flame (emissive + flicker) + rising smoke, at the fire.
        let fire = place(lay.fire);
        let phase = (site.seed % 1000) as f32 * 0.01;
        commands.spawn((
            Mesh3d(flame_cards.clone()),
            MeshMaterial3d(flame_mat.clone()),
            Transform::from_translation(fire + Vec3::Y * 0.06),
            bevy::light::NotShadowCaster,
            Flicker { phase },
            BiomeEntity,
            // Pooled flicker-light so the camp reads from across the map at night (the flame
            // mesh alone is emissive-only). The light rides the flame's own transform — its
            // scale wobble doesn't move the light, and it shares the flame's BiomeEntity life.
            crate::firelight::campfire_light(phase),
        ));
        for i in 0..3 {
            commands.spawn((
                Mesh3d(smoke_puff.clone()),
                MeshMaterial3d(smoke_mat.clone()),
                Transform::from_translation(fire).with_scale(Vec3::splat(0.01)),
                CampSmoke { base: fire + Vec3::Y * 0.4, phase: i as f32 / 3.0, speed: 0.3 },
                BiomeEntity,
            ));
        }

        // The first rescue faces two scouts; the other camps retain their mixed warbands.
        // Once repopulated this becomes an ordinary camp, so the introduction is not a loot loop.
        let introduction = Some(camp) == intro_target();
        let variants: &[orks::OrkVariant] = if introduction { &[orks::OrkVariant::Scout, orks::OrkVariant::Scout] } else { &VARIANTS };
        spawn_warband_with(commands, &armory, site, variants);
    }

    // Keep the armory + per-camp clear timers alive so `respawn_warbands` can repopulate a wiped
    // camp off-screen after a cooldown (the cage + its captives are NOT respawned).
    commands.insert_resource(CampWarbands { armory, cleared_at: vec![None; sites.len()], seen: vec![false; sites.len()] });
}

/// The pre-kit procedural camp (no `ork_camps.glb`): the fortress hide tent, banner pole, skull
/// spikes, fire ring and three sit-stumps, laid out round the layout's fire.
fn build_fallback_props(
    commands: &mut Commands,
    meshes: &mut Assets<Mesh>,
    prop_mat: &Handle<StandardMaterial>,
    site: &CampSite,
    lay: &Layout,
    place: &dyn Fn(Vec3) -> Vec3,
) {
    let mut prop_rng = site.seed | 1;
    let f = lay.fire;
    let solids = vec![
        (crate::ork_fortress::tent_mesh(0.7, &mut prop_rng), f + v(-2.5, 0.0, -2.1), (1.05_f32, 0.85_f32)),
        (banner_mesh(site.faction), lay.flag - v(0.0, lay.flag.y, -1.4), (0.0, 0.0)),
        (spikes_mesh(), f, (0.0, 0.0)),
        (fire_base_mesh(), f, (0.32, 0.32)),
    ];
    for (m, local, (hw, hd)) in solids {
        let world = place(local);
        let tf = Transform { translation: world, rotation: Quat::from_rotation_y(site.rot), scale: Vec3::ONE };
        commands.spawn((Mesh3d(meshes.add(m)), MeshMaterial3d(prop_mat.clone()), tf, BiomeEntity));
        if hw > 0.0 && hd > 0.0 {
            crate::blockers::add_obb(world.x, world.z, hw, hd, site.rot);
        }
    }
    for (i, local) in [v(1.05, 0.0, 0.5), v(-0.7, 0.0, 0.95), v(0.25, 0.0, -1.05)].into_iter().enumerate() {
        let seed = site.seed.wrapping_add(i as u32 * 37).wrapping_add(7) | 1;
        commands.spawn((
            Mesh3d(meshes.add(sit_stump_mesh(seed))),
            MeshMaterial3d(prop_mat.clone()),
            Transform { translation: place(f + local), rotation: ry((seed % 628) as f32 / 100.0), scale: Vec3::ONE },
            BiomeEntity,
        ));
    }
}

/// Respawn a camp's whole warband (one of each variant at its ring offset, home-anchored to the
/// camp centre) — the same layout [`build`] lays down, from the kept-alive armory.
fn spawn_warband(commands: &mut Commands, armory: &orks::Armory, site: &CampSite) {
    spawn_warband_with(commands, armory, site, &VARIANTS);
}

fn spawn_warband_with(commands: &mut Commands, armory: &orks::Armory, site: &CampSite, variants: &[orks::OrkVariant]) {
    let rot_q = Quat::from_rotation_y(site.rot);
    let cy = worldmap::ground_at_world(site.centre.x, site.centre.y).unwrap_or(0.0);
    let centre3 = Vec3::new(site.centre.x, cy, site.centre.y);
    for (i, variant) in variants.iter().enumerate() {
        let (lx, lz) = layout(site.kind).warband[i];
        let world = centre3 + rot_q * v(lx, 0.0, lz);
        let seed = site.seed.wrapping_add((i as u32).wrapping_mul(0x9e37_79b1));
        armory.spawn(commands, *variant, site.faction, site.centre, Vec2::new(world.x, world.z), seed);
    }
}

/// A Continue restores camps from the saved day ledger rather than the abandoned battlefield.
/// Partial kills are transient; today's successfully raided camps stay quiet. Timer/seen state
/// is reset synchronously before simulation, so a stale empty camp cannot manufacture a raid.
fn reconcile_warbands_on_load(
    mut loaded: MessageReader<crate::savegame::GameLoaded>,
    campaign: Res<crate::quest::CampaignRes>,
    game: Res<crate::siege::GameTime>,
    wb: Option<ResMut<CampWarbands>>,
    q: Query<(Entity, &orks::Ork), (Without<orks::WaveInvader>, Without<crate::dying::Dying>)>,
    mut commands: Commands,
) {
    let Some(crate::savegame::GameLoaded(data)) = loaded.read().last() else { return };
    let Some(mut wb) = wb else { return };
    let sites = plan();
    wb.cleared_at = vec![None; sites.len()];
    wb.seen = vec![false; sites.len()];
    for (entity, ork) in &q {
        if sites.iter().any(|site| site.centre.distance(ork.home()) < 1.0) {
            commands.entity(entity).try_despawn();
        }
    }
    for (i, site) in sites.iter().enumerate() {
        let cleared = campaign.0.raid_day == data.wave_index + 1
            && campaign.0.cleared_camps.get(i).copied().unwrap_or(false);
        if cleared {
            wb.cleared_at[i] = Some(game.0);
        } else if campaign.0.guided && data.wave_index < 0 && !campaign.0.rescued && Some(i) == intro_target() {
            spawn_warband_with(&mut commands, &wb.armory, site, &[orks::OrkVariant::Scout, orks::OrkVariant::Scout]);
        } else {
            spawn_warband(&mut commands, &wb.armory, site);
        }
    }
}

/// Repopulate cleared ork camps — the port of TS `OrkCamp.tsx`'s respawn. A camp whose warband has
/// been wiped starts a [`CAMP_RESPAWN_DELAY`] cooldown; once it elapses AND the hero is at least
/// [`CAMP_RESPAWN_FAR`] away (so the warband returns unseen), the whole warband respawns. Only the
/// orks come back: the prisoner cage stays open, the apples/chests run their own respawn timers
/// (`verbs.rs`), so a re-cleared camp yields no fresh captives — just a renewed fight.
pub(crate) fn respawn_warbands(
    game: Res<crate::siege::GameTime>,
    siege: Res<crate::siege::Siege>,
    mut campaign: ResMut<crate::quest::CampaignRes>,
    hero: Res<crate::player::HeroState>,
    wb: Option<ResMut<CampWarbands>>,
    orks_q: Query<(Entity, &orks::Ork), (Without<orks::WaveInvader>, Without<crate::dying::Dying>)>,
    mut notice: ResMut<crate::ui::notice::Notice>,
    time: Res<Time>,
    mut commands: Commands,
) {
    let Some(mut wb) = wb else { return };
    let sites = plan();
    if sites.is_empty() || wb.cleared_at.len() != sites.len() {
        return;
    }
    let now = game.0;
    let next_night = match siege.phase {
        crate::siege::GamePhase::Prep => siege.wave_index + 1,
        _ => siege.wave_index,
    }.max(0);
    let new_day = siege.phase == crate::siege::GamePhase::Prep && campaign.0.raid_day != next_night;
    if new_day {
        campaign.0.raid_day = next_night;
        campaign.0.cleared_camps = vec![false; sites.len()];
        campaign.0.shaman_cleared = false;
    } else {
        // Padding preserves old-save flags instead of discarding progress after a schema change.
        campaign.0.cleared_camps.resize(sites.len(), false);
    }
    // Living warband orks per camp (invaders + fading corpses excluded by the query filter).
    let mut alive = vec![Vec::new(); sites.len()];
    for (entity, o) in &orks_q {
        let h = o.home();
        if let Some(i) = sites.iter().position(|s| s.centre.distance(h) < 1.0) {
            alive[i].push(entity);
        }
    }
    for (i, site) in sites.iter().enumerate() {
        if new_day && Some(i) == raid_target(next_night) && alive[i].is_empty()
            && wb.cleared_at[i].is_some() && hero.pos.distance(site.centre) <= CAMP_RESPAWN_FAR {
            // Holding an already-defeated forward camp through dawn is a valid way to stop it
            // regrouping. The next day cannot promise shamans from an empty, occupied camp.
            campaign.0.cleared_camps[i] = true;
            campaign.0.shaman_cleared = threat_for(next_night as usize).kind == ThreatKind::Ritual;
            notice.push(threat_for(next_night as usize).raid_result, time.elapsed_secs_f64());
        }
        let protected = campaign.0.raid_day == next_night && campaign.0.cleared_camps[i];
        if protected {
            // Rebuild/load spawns pristine warbands. Reconcile today's successful raid so the
            // camp stays visibly quiet and suppression cannot expire before its promised night.
            for entity in &alive[i] { commands.entity(*entity).try_despawn(); }
            wb.cleared_at[i].get_or_insert(now);
            continue;
        }
        if !alive[i].is_empty() {
            wb.seen[i] = true;
            wb.cleared_at[i] = None; // still populated — reset the clear clock
            continue;
        }
        let Some(cleared) = wb.cleared_at[i] else {
            if !wb.seen[i] { continue; }
            wb.cleared_at[i] = Some(now); // just went quiet — start the cooldown
            if siege.phase == crate::siege::GamePhase::Prep {
                campaign.0.cleared_camps[i] = true;
                if Some(i) == raid_target(next_night) {
                    let threat = threat_for(next_night as usize);
                    campaign.0.shaman_cleared = threat.kind == ThreatKind::Ritual;
                    notice.push(threat.raid_result, time.elapsed_secs_f64());
                }
            }
            continue;
        };
        // At dawn a previously cleared staging camp can regroup off-screen for its next raid;
        // all other camps keep their normal cooldown. No one respawns in the hero's view.
        let regroup = siege.phase == crate::siege::GamePhase::Prep && Some(i) == raid_target(next_night);
        if (now - cleared >= CAMP_RESPAWN_DELAY || regroup)
            && hero.pos.distance(site.centre) > CAMP_RESPAWN_FAR {
            spawn_warband(&mut commands, &wb.armory, site);
            wb.cleared_at[i] = None;
            wb.seen[i] = false;
        }
    }
}

// ── Prop models (vertex-coloured, flat-shaded; ported from the TS components) ─────────

const POLE: u32 = 0x3a2a1a;
const SKULL: u32 = 0xe0d8c0;
const STONE: u32 = 0x6e6e76;
const LOG_LIGHT: u32 = 0x7a4a26;
const LOG_DARK: u32 = 0x3a2a1a;

// (The camps' bespoke A-frame tent + faction tent colours are gone — every warband now
//  pitches the fortress hide tent, `ork_fortress::tent_mesh`; the banner carries the
//  faction colour instead.)

/// Warband banner pole — the faction-coloured flag itself is a fluttering cloth entity
/// (banner.rs), spawned alongside the solids in [`build`].
fn banner_mesh(_f: Faction) -> Mesh {
    group(vec![cyl(0.03, 3.0, v(0.0, 1.5, -1.4), Quat::IDENTITY, lin(POLE))])
}

/// Two skull-topped spikes (decorative; no blocker).
fn spikes_mesh() -> Mesh {
    let spike = |x: f32, z: f32, rot: f32| {
        vec![
            cyl(0.025, 0.8, v(x, 0.4, z), ry(rot), lin(POLE)),
            bx(0.12, 0.13, 0.13, v(x, 0.85, z), lin(SKULL)),
        ]
    };
    let mut parts = spike(-0.9, 1.4, 0.4);
    parts.extend(spike(1.6, 1.2, -0.6));
    group(parts)
}

// (The opened-husk cage model is gone — a rescue no longer swaps meshes at all. The one cage
//  model (`ork_fortress::cage_mesh`) persists and its hinged door child swings open by
//  animation: see [`spawn_cage`] / [`swing_cage_doors`].)

/// Campfire base — a ring of stones + two crossed logs (the solid, vertex-coloured part).
fn fire_base_mesh() -> Mesh {
    let mut p: Vec<Mesh> = Vec::new();
    for i in 0..7 {
        let a = (i as f32 / 7.0) * TAU;
        p.push(orb_mesh(0.13, v(a.cos() * 0.42, 0.07, a.sin() * 0.42), lin(STONE)));
    }
    p.push(cyl(0.045, 0.72, v(0.0, 0.08, 0.0), xyz(FRAC_PI_2, 0.0, FRAC_PI_2 / 2.0), lin(LOG_LIGHT)));
    p.push(cyl(0.045, 0.72, v(0.0, 0.13, 0.0), xyz(FRAC_PI_2, 0.0, -FRAC_PI_2 / 2.0), lin(LOG_DARK)));
    group(p)
}

/// A rough log stool ringing the campfire — orks roost on these between musters (the "sit-stumps").
/// A short tapered trunk with a lighter sawn top + heartwood ring and a low root flare; `seed`
/// jitters the height so a ring of them doesn't read as clones.
fn sit_stump_mesh(mut seed: u32) -> Mesh {
    let h = 0.36 + (next_u32(&mut seed) % 110) as f32 / 1000.0; // 0.36..0.47
    group(vec![
        cyl(0.25, h, v(0.0, h * 0.5, 0.0), Quat::IDENTITY, lin(LOG_DARK)), // trunk
        cyl(0.30, 0.09, v(0.0, 0.045, 0.0), Quat::IDENTITY, lin(LOG_DARK)), // root flare
        cyl(0.235, 0.05, v(0.0, h, 0.0), Quat::IDENTITY, lin(LOG_LIGHT)), // sawn top (lighter heartwood)
        cyl(0.12, 0.055, v(0.0, h + 0.004, 0.0), Quat::IDENTITY, lin(LOG_DARK)), // inner growth ring
    ])
}

/// The camp fire's flame cards: three vertical quads crossed at 60° plus a smaller inner set,
/// 0.75 wide x 0.95 tall, base at y=0, UV v=1 at the base (the flame texture's root).
pub(crate) fn flame_card_mesh() -> Mesh {
    use bevy::asset::RenderAssetUsages;
    use bevy::mesh::{Indices, PrimitiveTopology};
    let (mut pos, mut uv, mut nrm, mut idx) = (Vec::new(), Vec::new(), Vec::new(), Vec::new());
    for (w, h, phase) in [(0.75_f32, 0.95_f32, 0.0_f32), (0.42, 0.62, 0.5)] {
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

// ── Mesh helpers ─────────────────────────────────────────────────────────────────

fn v(x: f32, y: f32, z: f32) -> Vec3 {
    Vec3::new(x, y, z)
}
fn ry(a: f32) -> Quat {
    Quat::from_rotation_y(a)
}
fn xyz(x: f32, y: f32, z: f32) -> Quat {
    Quat::from_euler(EulerRot::XYZ, x, y, z)
}
fn group(parts: Vec<Mesh>) -> Mesh {
    let mut it = parts.into_iter();
    let mut base = it.next().expect("at least one part");
    for p in it {
        base.merge(&p).expect("camp parts share attributes");
    }
    base.duplicate_vertices();
    base.compute_flat_normals();
    base
}
fn bx(w: f32, h: f32, d: f32, off: Vec3, c: [f32; 4]) -> Mesh {
    tinted(Cuboid::new(w, h, d).mesh().build().translated_by(off), c)
}
fn cyl(r: f32, h: f32, off: Vec3, rot: Quat, c: [f32; 4]) -> Mesh {
    tinted(Cylinder::new(r, h).mesh().resolution(6).build().rotated_by(rot).translated_by(off), c)
}
fn orb_mesh(r: f32, off: Vec3, c: [f32; 4]) -> Mesh {
    tinted(Sphere::new(r).mesh().ico(0).unwrap().translated_by(off), c)
}

// ── Deterministic mulberry32 RNG ─────────────────────────────────────────────────────

fn next_u32(s: &mut u32) -> u32 {
    *s = s.wrapping_add(0x6d2b_79f5);
    let mut t = *s;
    t = (t ^ (t >> 15)).wrapping_mul(t | 1);
    t ^= t.wrapping_add((t ^ (t >> 7)).wrapping_mul(t | 61));
    t ^ (t >> 14)
}
fn rng01(s: &mut u32) -> f32 {
    next_u32(s) as f32 / 4_294_967_296.0
}
fn rng_range(s: &mut u32, lo: f32, hi: f32) -> f32 {
    lo + rng01(s) * (hi - lo)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Five camps, five different kinds; the rescue cages sit only in the camps that keep
    /// prisoners, and the introductory rescue always points at one of them.
    #[test]
    fn camps_are_five_unique_places() {
        let sites = plan();
        for (i, s) in sites.iter().enumerate() {
            let y = worldmap::ground_at_world(s.centre.x, s.centre.y).unwrap_or(0.0);
            eprintln!("camp {i} {:?} at {:.1},{y:.2},{:.1} yaw {:.2} cage {}", s.kind, s.centre.x, s.centre.y, s.rot, has_cage(i));
        }
        assert_eq!(sites.len(), 5, "one camp per wilderness biome");
        for (i, a) in sites.iter().enumerate() {
            assert!(sites[i + 1..].iter().all(|b| b.kind != a.kind), "{:?} camp twice", a.kind);
        }
        let caged: Vec<CampKind> = sites.iter().enumerate().filter(|(i, _)| has_cage(*i)).map(|(_, s)| s.kind).collect();
        assert!(caged.contains(&CampKind::Stilts), "the swamp is the cage camp");
        assert!(!caged.contains(&CampKind::Shaman) && !caged.contains(&CampKind::Hunters));
        assert!(intro_target().is_some_and(has_cage), "the opening rescue needs a cage");
        assert_eq!(cage_positions().len(), sites.len(), "cage list stays index-aligned with the plan");
    }
}

