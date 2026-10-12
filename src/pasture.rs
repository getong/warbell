//! **Common Pasture & Sheepfold** (living-island spec 2026-10-13 §2 D.13) — the east meadow under
//! the walls: a wattle fold with a hay manger, a hewn water trough, a flock of sheep grazing and
//! drifting together, a shepherd boy and his dog. At dusk the boy and the dog drive the flock into
//! the fold (so the bell announces itself before it rings); at dawn the sheep file back out.
//!
//! **Function.** Living sheep add `pasture_food` (≤ +0.1 food/s for a full flock) to the town's
//! food flow (`Town::pasture`, read by `food_rate`), which speeds settling. A lamb is born every
//! dawn up to [`SHEEP_CAP`]. On **Arson** nights an invader torch that reaches the fold sets it
//! burning and two penned sheep die.
//!
//! **State.** The flock size is the `sheep_count` world flag (saved, wiped on New Game);
//! everything else is derived. Models: `meadow_kit.glb` (`tools/blender_forest/meadow_kit.py`):
//! the fold, trough and the sculpted sheep (fleece coat on the creature material).

use std::f32::consts::TAU;

use bevy::prelude::*;

use crate::biome::BiomeEntity;
use crate::meadow::{hash01, kit_piece, sky_t, walk_body};
use crate::savegame::WorldFlags;

/// Fold centre (world XZ). Local frame: x ±3.5, z ±2.5, the gate gap on the −X side.
/// Centre / reach of the worn ground (the realforest mask pass).
pub const WEAR_C: Vec2 = Vec2::new(39.0, 34.0);
pub const WEAR_R: f32 = 12.0;
pub const FOLD_C: Vec2 = Vec2::new(40.0, 39.5);
const FOLD_HX: f32 = 3.5;
const FOLD_HZ: f32 = 2.5;
/// The grazing ground.
pub const GRAZE_C: Vec2 = Vec2::new(40.5, 27.5);
const GRAZE_R: f32 = 7.0;
const TROUGH: (Vec2, f32) = (Vec2::new(36.9, 34.4), 0.5);
/// Start / full flock and the lambing cap.
const START_FLOCK: i64 = 8;
pub const SHEEP_CAP: i64 = 12;
const ADULT_SCALE: f32 = 0.9;
const LAMB_SCALE: f32 = 0.55;
/// Hero closer than this → a grazing sheep shies away.
const SHY_R: f32 = 2.6;


fn gate_out() -> Vec2 {
    FOLD_C + Vec2::new(-FOLD_HX - 1.4, 0.0)
}
fn gate_in() -> Vec2 {
    FOLD_C + Vec2::new(-FOLD_HX + 0.9, 0.0)
}
/// The `i`-th bedding spot inside the fold.
fn slot(i: usize) -> Vec2 {
    let col = (i % 4) as f32;
    let row = (i / 4) as f32;
    FOLD_C + Vec2::new(-1.6 + col * 1.15 + (row % 2.0) * 0.4, -1.6 + row * 1.05)
}

/// Footprints the other planners keep clear of (fold + trough + grazing ground).
pub fn planned_footprints() -> Vec<(Vec2, f32)> {
    vec![(FOLD_C, 5.0), (GRAZE_C, GRAZE_R + 1.0), (TROUGH.0, 1.5)]
}

/// Worn ground for the realforest floor mask: `(floor, path, debris)` — trampled mud round the
/// fold gate and the trough, a sheep track from the grass to the gate, straw spill inside.
pub fn ground_wear(wx: f32, wz: f32) -> Option<(f32, f32, f32)> {
    let p = Vec2::new(wx, wz);
    if p.distance(WEAR_C) > WEAR_R {
        return None;
    }
    let ss = |a: f32, b: f32, x: f32| {
        let t = ((x - a) / (b - a)).clamp(0.0, 1.0);
        t * t * (3.0 - 2.0 * t)
    };
    let wob = (wx * 1.7).sin() * 0.25 + (wz * 2.3).cos() * 0.2;
    let seg = |a: Vec2, b: Vec2| {
        let ab = b - a;
        let t = ((p - a).dot(ab) / ab.length_squared()).clamp(0.0, 1.0);
        p.distance(a + ab * t)
    };
    // Sheep tracks: narrow, broken, grass between the hoof lines.
    let broken = 0.55 + 0.45 * ((wx * 0.9 + wz * 1.3).sin() * (wz * 0.7 - wx * 0.4).cos()).abs();
    let track = (1.0 - ss(0.25, 0.9, seg(GRAZE_C + Vec2::new(-1.0, 3.5), TROUGH.0) + wob)) * broken;
    let track2 = (1.0 - ss(0.25, 0.9, seg(TROUGH.0, gate_out()) + wob)) * broken;
    let gate = 1.0 - ss(1.2, 2.8, p.distance(gate_out()) + wob);
    let trough = 1.0 - ss(1.0, 2.2, p.distance(TROUGH.0 + Vec2::new(0.0, 0.5)) + wob);
    let l = p - FOLD_C;
    let inside = if l.x.abs() < FOLD_HX && l.y.abs() < FOLD_HZ { 1.0 - ss(-0.6, 0.0, (l.x.abs() - FOLD_HX).max(l.y.abs() - FOLD_HZ)) } else { 0.0 };
    let path = (track * 0.38).max(track2 * 0.45).max(gate * 0.8).max(trough * 0.8).max(inside * 0.7);
    if path <= 0.01 {
        return None;
    }
    Some((ss(0.0, 0.5, path), path, inside * 0.8))
}

pub struct PasturePlugin;

impl Plugin for PasturePlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<SheepAssets>()
            .add_systems(Update, (spawn_pasture, reconcile_flock).chain().run_if(crate::rts::in_campaign))
            .add_systems(
                Update,
                (flock_brain, shepherd_brain, dog_brain, pasture_food, lambing, fold_fire)
                    .after(reconcile_flock)
                    .run_if(in_state(crate::game_state::Modal::None))
                    .run_if(crate::rts::in_campaign),
            )
            // Ungated, like the other animators: a frozen world still draws its sheep posed.
            .add_systems(Update, animate_sheep.after(flock_brain));
    }
}

// ── Components ───────────────────────────────────────────────────────────────────────────

#[derive(Component)]
struct PastureSite;

#[derive(Clone, Copy, PartialEq, Debug)]
enum SMode {
    Graze,
    Walk,
    Shy,
    /// Driven into the fold: 0 → outside the gate, 1 → inside, 2 → its bedding slot.
    ToFold(u8),
    Penned,
    /// Filing out: 0 → inside the gate, 1 → outside, then graze.
    Out(u8),
}

#[derive(Component)]
pub struct Sheep {
    pos: Vec2,
    facing: f32,
    speed: f32,
    mode: SMode,
    target: Vec2,
    timer: f32,
    rng: u32,
    /// 0..1 head-down grazing blend.
    graze: f32,
    gait: f32,
    lamb: bool,
    slot: usize,
}

#[derive(Component)]
struct SheepHead;
#[derive(Component)]
struct SheepLeg {
    offset: f32,
}

#[derive(Component)]
struct Shepherd {
    target: Vec2,
    timer: f32,
}
#[derive(Component)]
struct SheepDog {
    pos: Vec2,
    facing: f32,
    ang: f32,
}
#[derive(Component)]
struct FoldFire;

/// Coat variants: (wool dark, base, light, tint) + face/leg skin.
const COATS: [([u32; 4], u32); 4] = [
    ([0x8f8470, 0xd8cdb4, 0xf1eadb, 0x9c8458], 0xd9ccb4), // white-faced
    ([0x887c68, 0xd2c6ac, 0xece3d0, 0x96805a], 0x2b2420), // black-faced
    ([0x8a7e6a, 0xcfc3aa, 0xe8dfcb, 0x9a8460], 0x6a5440), // brown-faced
    ([0x221e1b, 0x3a332d, 0x5b5046, 0x4a3b2c], 0x2a2420), // the black sheep
];

/// The sheep meshes per coat variant (built once from the kit, CPU-recoloured).
#[derive(Resource, Default)]
struct SheepAssets {
    built: bool,
    mat: Option<Handle<crate::creature::CreatureMaterial>>,
    /// [variant] → (body, head, front L, front R, hind L, hind R).
    meshes: Vec<[Handle<Mesh>; 6]>,
}

fn mirror_x(mut m: Mesh) -> Mesh {
    use bevy::mesh::{Indices, VertexAttributeValues as V};
    for attr in [Mesh::ATTRIBUTE_POSITION, Mesh::ATTRIBUTE_NORMAL] {
        if let Some(V::Float32x3(vs)) = m.attribute_mut(attr) {
            for p in vs.iter_mut() {
                p[0] = -p[0];
            }
        }
    }
    match m.indices_mut() {
        Some(Indices::U32(ix)) => ix.chunks_exact_mut(3).for_each(|t| t.swap(1, 2)),
        Some(Indices::U16(ix)) => ix.chunks_exact_mut(3).for_each(|t| t.swap(1, 2)),
        None => {}
    }
    m
}

fn build_assets(a: &mut SheepAssets, meshes: &mut Assets<Mesh>, cmats: &mut Assets<crate::creature::CreatureMaterial>) -> bool {
    use crate::creature::Surf;
    let Some(kit) = crate::realforest::get().filter(|k| k.has("sheep_body")) else { return false };
    let l = crate::palette::lin;
    for (coat, skin) in COATS {
        let ramp = [l(coat[0]), l(coat[1]), l(coat[2]), l(coat[3])];
        // Region order = meadow_kit.py: WOOL, SKIN, HOOF, EYE.
        let pal = [(l(coat[1]), Surf::Fur), (l(skin), Surf::Skin), (l(0x2a241e), Surf::Bone), (l(0x0d0b09), Surf::Bone)];
        let part = |n: &str| kit.coat_part(n, &ramp, &pal);
        let (Some(body), Some(head), Some(leg), Some(hind)) = (part("sheep_body"), part("sheep_head"), part("sheep_leg"), part("sheep_hind")) else {
            return false;
        };
        a.meshes.push([
            meshes.add(body),
            meshes.add(head),
            meshes.add(leg.clone()),
            meshes.add(mirror_x(leg)),
            meshes.add(hind.clone()),
            meshes.add(mirror_x(hind)),
        ]);
    }
    a.mat = Some(crate::creature::make_creature_material(cmats));
    true
}

fn spawn_sheep(commands: &mut Commands, a: &SheepAssets, pos: Vec2, seed: u32, lamb: bool, mode: SMode, slot_i: usize) {
    let (Some(mat), false) = (a.mat.clone(), a.meshes.is_empty()) else { return };
    // One black sheep in the flock; the rest a mix of white, black- and brown-faced.
    let v = if seed % 11 == 3 { 3 } else { (seed as usize / 7) % 3 };
    let m = &a.meshes[v];
    let facing = hash01(seed ^ 0x51) * TAU;
    let s = if lamb { LAMB_SCALE } else { ADULT_SCALE * (0.94 + 0.12 * hash01(seed ^ 0x77)) };
    let y = crate::worldmap::ground_at_world(pos.x, pos.y).unwrap_or(0.0);
    let root = commands
        .spawn((
            Transform::from_xyz(pos.x, y, pos.y).with_rotation(Quat::from_rotation_y(facing)).with_scale(Vec3::splat(s)),
            Visibility::Visible,
            Sheep {
                pos,
                facing,
                speed: 0.0,
                mode,
                target: pos,
                timer: 1.0 + hash01(seed) * 6.0,
                rng: seed | 1,
                graze: 1.0,
                gait: hash01(seed ^ 0x99) * TAU,
                lamb,
                slot: slot_i,
            },
            BiomeEntity,
        ))
        .id();
    let mesh = |h: &Handle<Mesh>| (Mesh3d(h.clone()), MeshMaterial3d(mat.clone()));
    commands.entity(root).with_children(|c| {
        c.spawn((mesh(&m[0]), Transform::default()));
        c.spawn((mesh(&m[1]), Transform::from_xyz(0.0, 0.5, 0.3), SheepHead));
        for (i, (hip, mi)) in [(Vec3::new(0.095, 0.33, 0.21), 2), (Vec3::new(-0.095, 0.33, 0.21), 3), (Vec3::new(0.095, 0.33, -0.25), 4), (Vec3::new(-0.095, 0.33, -0.25), 5)]
            .into_iter()
            .enumerate()
        {
            // Diagonal pairs move together (a walk): FL+HR, FR+HL.
            let offset = if i == 0 || i == 3 { 0.0 } else { std::f32::consts::PI };
            c.spawn((mesh(&m[mi]), Transform::from_translation(hip), SheepLeg { offset }));
        }
    });
}

// ── Site ─────────────────────────────────────────────────────────────────────────────────

#[allow(clippy::too_many_arguments)]
fn spawn_pasture(
    mut commands: Commands,
    ready: Res<crate::biome::WorldReady>,
    site: Query<(), With<PastureSite>>,
    mut assets: ResMut<SheepAssets>,
    mut meshes: ResMut<Assets<Mesh>>,
    mut cmats: ResMut<Assets<crate::creature::CreatureMaterial>>,
    sheep: Query<Entity, With<Sheep>>,
) {
    if !ready.0 || !site.is_empty() || crate::realforest::get().is_none() {
        return;
    }
    if !assets.built {
        assets.built = true;
        if !build_assets(&mut assets, &mut meshes, &mut cmats) {
            warn!("pasture: meadow_kit.glb sheep missing — no flock");
        }
    }
    // A world rebuild swept the old flock with the rest of the BiomeEntities; clear any stragglers.
    for e in &sheep {
        commands.entity(e).try_despawn();
    }
    let Some(fold) = kit_piece(&mut commands, "meadow_fold", FOLD_C.x, FOLD_C.y, 0.0, 0.02) else {
        warn!("pasture: meadow_kit.glb missing — no pasture");
        commands.spawn((PastureSite, BiomeEntity, Transform::default()));
        return;
    };
    commands.entity(fold).insert(PastureSite);
    kit_piece(&mut commands, "meadow_trough", TROUGH.0.x, TROUGH.0.y, TROUGH.1, 0.04);
    // Fold walls block the hero (thin hurdles; the gate gap stays open).
    let b = |x: f32, z: f32, hw: f32, hd: f32| crate::blockers::add_obb(FOLD_C.x + x, FOLD_C.y + z, hw, hd, 0.0);
    b(0.0, -FOLD_HZ, FOLD_HX, 0.09);
    b(0.0, FOLD_HZ, FOLD_HX, 0.09);
    b(FOLD_HX, 0.0, 0.09, FOLD_HZ);
    b(-FOLD_HX, -1.62, 0.09, 0.88);
    b(-FOLD_HX, 1.62, 0.09, 0.88);
    crate::blockers::add_obb(TROUGH.0.x, TROUGH.0.y, 0.95, 0.3, TROUGH.1);

    // The shepherd boy (a village kid) and his dog.
    let boy_at = GRAZE_C + Vec2::new(-4.5, 3.0);
    let (boy, _, _) = crate::villagers::spawn_life_peasant(&mut commands, &mut meshes, &mut cmats, boy_at, crate::village_life::Body::Kid, 0x5EE9);
    commands.entity(boy).insert((crate::scenes::SceneActor, crate::villagers::Kid, Shepherd { target: boy_at, timer: 2.0 }));
    if let Some(mat) = assets.mat.clone() {
        let dog_at = boy_at + Vec2::new(1.2, 0.8);
        let y = crate::worldmap::ground_at_world(dog_at.x, dog_at.y).unwrap_or(0.0);
        let root = commands
            .spawn((
                Transform::from_xyz(dog_at.x, y, dog_at.y).with_scale(Vec3::splat(0.55 * 1.5)),
                Visibility::Visible,
                crate::quadruped::QuadDrive::new(crate::quadruped::QuadSpecies::Dog),
                SheepDog { pos: dog_at, facing: 0.0, ang: 0.0 },
                BiomeEntity,
            ))
            .id();
        let h = crate::quadruped::quad_meshes(crate::quadruped::QuadSpecies::Dog).upload(&mut meshes);
        crate::quadruped::spawn_quad(&mut commands, root, &mat, crate::quadruped::QuadSpecies::Dog, h);
    }
}

/// Live flock ↔ the `sheep_count` flag: first boot of a run seeds [`START_FLOCK`]; a load / theft /
/// fire / lambing changes the flag and this spawns or removes bodies to match.
fn reconcile_flock(
    mut commands: Commands,
    mut flags: ResMut<WorldFlags>,
    assets: Res<SheepAssets>,
    site: Query<(), With<PastureSite>>,
    sheep: Query<(Entity, &Sheep)>,
    clock: Option<Res<crate::scene::SkyClock>>,
    siege: Option<Res<crate::siege::Siege>>,
    mut lamb_due: Local<bool>,
) {
    if !flags.is("pasture_init") {
        flags.set("pasture_init", 1);
        flags.set("sheep_count", START_FLOCK);
    }
    if site.is_empty() || assets.meshes.is_empty() {
        return;
    }
    let want = flags.get("sheep_count").clamp(0, SHEEP_CAP) as usize;
    let live: Vec<(Entity, usize)> = sheep.iter().map(|(e, s)| (e, s.slot)).collect();
    let have = live.len();
    if have < want {
        let penned = pen_time(sky_t(clock.as_deref()), siege.as_deref());
        let mut used: Vec<usize> = sheep.iter().map(|(_, s)| s.slot).collect();
        let first_spawn = have == 0;
        for k in 0..(want - have) {
            let slot_i = (0..SHEEP_CAP as usize).find(|i| !used.contains(i)).unwrap_or(k);
            used.push(slot_i);
            let seed = 0xA11C_E5ED ^ (slot_i as u32).wrapping_mul(0x9E37_79B9) ^ (flags.get("lambs") as u32).wrapping_mul(31);
            let lamb = !first_spawn && *lamb_due;
            let (pos, mode) = if penned {
                (slot(slot_i), SMode::Penned)
            } else {
                let a = hash01(seed ^ 3) * TAU;
                (GRAZE_C + Vec2::from_angle(a) * GRAZE_R * hash01(seed ^ 5).sqrt() * 0.8, SMode::Graze)
            };
            spawn_sheep(&mut commands, &assets, pos, seed, lamb, mode, slot_i);
        }
        *lamb_due = false;
    } else if have > want {
        // Lost to fire / a load with fewer: drop the highest slots first.
        let mut v = live;
        v.sort_by_key(|(_, s)| std::cmp::Reverse(*s));
        for (e, _) in v.into_iter().take(have - want) {
            commands.entity(e).try_despawn();
        }
    }
    if flags.get("lamb_pending") != 0 {
        flags.set("lamb_pending", 0);
        *lamb_due = true;
    }
}

/// Should the flock be in the fold now? Dusk onward, through the night, until just after dawn.
fn pen_time(t: f32, siege: Option<&crate::siege::Siege>) -> bool {
    siege.is_some_and(|s| s.phase == crate::siege::GamePhase::Wave) || t >= 0.40 || t < 0.035
}

// ── Brains ───────────────────────────────────────────────────────────────────────────────

fn rnd(r: &mut u32) -> f32 {
    *r = r.wrapping_mul(1_664_525).wrapping_add(1_013_904_223);
    hash01(*r)
}

#[allow(clippy::type_complexity)]
fn flock_brain(
    time: Res<Time>,
    clock: Option<Res<crate::scene::SkyClock>>,
    siege: Option<Res<crate::siege::Siege>>,
    hero: Option<Res<crate::player::HeroState>>,
    mut q: Query<(Entity, &mut Sheep, &mut Transform)>,
) {
    let dt = time.delta_secs().min(0.05);
    let pen = pen_time(sky_t(clock.as_deref()), siege.as_deref());
    let hero_pos = hero.as_ref().map_or(Vec2::splat(1e6), |h| h.pos);
    // Flock centroid (grazers only) for cohesion.
    let (mut sum, mut n) = (Vec2::ZERO, 0.0);
    let mut all: Vec<(Entity, Vec2)> = Vec::with_capacity(16);
    for (e, s, _) in &q {
        all.push((e, s.pos));
        if matches!(s.mode, SMode::Graze | SMode::Walk | SMode::Shy) {
            sum += s.pos;
            n += 1.0;
        }
    }
    let centroid = if n > 0.0 { sum / n } else { GRAZE_C };
    for (e, mut s, mut tf) in &mut q {
        let s = &mut *s;
        s.timer -= dt;
        // Transitions between the day and the fold.
        match s.mode {
            SMode::Graze | SMode::Walk | SMode::Shy if pen => {
                s.mode = SMode::ToFold(0);
                s.timer = rnd(&mut s.rng) * 5.0; // the flock drifts in, not in lockstep
            }
            SMode::Penned | SMode::ToFold(_) if !pen => {
                s.mode = SMode::Out(0);
                s.timer = rnd(&mut s.rng) * 6.0;
            }
            _ => {}
        }
        let mut want_speed = 0.0;
        let mut goal = s.pos;
        match s.mode {
            SMode::Graze => {
                if s.pos.distance(hero_pos) < SHY_R {
                    s.mode = SMode::Shy;
                    s.timer = 1.2;
                } else if s.timer <= 0.0 {
                    // Wander a few steps, biased toward the flock and kept on the pasture.
                    let a = rnd(&mut s.rng) * TAU;
                    let mut t = s.pos * 0.5 + centroid * 0.5 + Vec2::from_angle(a) * (1.0 + rnd(&mut s.rng) * 2.5);
                    if t.distance(GRAZE_C) > GRAZE_R {
                        t = GRAZE_C + (t - GRAZE_C).normalize_or_zero() * GRAZE_R * 0.85;
                    }
                    if rnd(&mut s.rng) < 0.12 {
                        t = TROUGH.0 + Vec2::new(rnd(&mut s.rng) - 0.5, 0.9);
                    }
                    s.target = t;
                    s.mode = SMode::Walk;
                }
            }
            SMode::Walk => {
                goal = s.target;
                want_speed = 0.42;
                if s.pos.distance(s.target) < 0.25 {
                    s.mode = SMode::Graze;
                    s.timer = 4.0 + rnd(&mut s.rng) * 9.0;
                }
            }
            SMode::Shy => {
                let away = (s.pos - hero_pos).normalize_or_zero();
                goal = s.pos + away * 3.0;
                want_speed = 1.9;
                if s.timer <= 0.0 && s.pos.distance(hero_pos) > SHY_R + 0.8 {
                    s.mode = SMode::Graze;
                    s.timer = 1.0 + rnd(&mut s.rng) * 3.0;
                }
            }
            SMode::ToFold(stage) => {
                if s.timer > 0.0 {
                    goal = s.pos;
                } else {
                    goal = match stage {
                        0 => gate_out() + Vec2::new(-0.6, (s.slot as f32 % 3.0 - 1.0) * 0.5),
                        1 => gate_in(),
                        _ => slot(s.slot),
                    };
                    want_speed = if stage == 0 { 0.95 } else { 0.7 };
                    if s.pos.distance(goal) < 0.35 {
                        s.mode = if stage >= 2 { SMode::Penned } else { SMode::ToFold(stage + 1) };
                    }
                }
            }
            SMode::Penned => {
                goal = slot(s.slot);
                if s.pos.distance(goal) > 0.3 {
                    want_speed = 0.4;
                }
            }
            SMode::Out(stage) => {
                if s.timer > 0.0 {
                    goal = s.pos;
                } else {
                    goal = match stage {
                        0 => gate_in(),
                        1 => gate_out(),
                        _ => GRAZE_C + Vec2::from_angle(rnd(&mut s.rng) * TAU) * GRAZE_R * 0.6,
                    };
                    want_speed = 0.8;
                    if s.pos.distance(goal) < 0.4 {
                        if stage >= 1 {
                            s.mode = SMode::Walk;
                            s.target = GRAZE_C + Vec2::from_angle(rnd(&mut s.rng) * TAU) * GRAZE_R * 0.6;
                        } else {
                            s.mode = SMode::Out(stage + 1);
                        }
                    }
                }
            }
        }
        // Separation from flock-mates.
        let mut push = Vec2::ZERO;
        for (oe, op) in &all {
            if *oe == e {
                continue;
            }
            let d = s.pos - *op;
            let l = d.length();
            if l < 0.62 && l > 1e-4 {
                push += d / l * (0.62 - l);
            }
        }
        let to = goal - s.pos;
        let dist = to.length();
        let target_speed = if dist > 0.05 { want_speed } else { 0.0 };
        s.speed += (target_speed - s.speed) * (dt * 4.0).min(1.0);
        let mut step = if dist > 1e-4 { to / dist * (s.speed * dt).min(dist) } else { Vec2::ZERO };
        step += push * (dt * 3.0).min(1.0);
        s.pos += step;
        if s.speed > 0.05 && dist > 0.05 {
            let want = to.x.atan2(to.y);
            s.facing += crate::steer::wrap_pi(want - s.facing) * (dt * 4.0).min(1.0);
        }
        let grazing = matches!(s.mode, SMode::Graze | SMode::Penned) && s.speed < 0.1;
        let g_target = if grazing { 1.0 } else { 0.0 };
        s.graze += (g_target - s.graze) * (dt * 2.0).min(1.0);
        s.gait += s.speed * dt * 11.0;
        let y = crate::worldmap::ground_at_world(s.pos.x, s.pos.y).unwrap_or(tf.translation.y);
        tf.translation = Vec3::new(s.pos.x, y, s.pos.y);
        tf.rotation = Quat::from_rotation_y(s.facing);
    }
}

fn animate_sheep(
    time: Res<Time>,
    sheep: Query<&Sheep>,
    mut heads: Query<(&ChildOf, &mut Transform), (With<SheepHead>, Without<SheepLeg>)>,
    mut legs: Query<(&ChildOf, &SheepLeg, &mut Transform), Without<SheepHead>>,
) {
    let now = time.elapsed_secs();
    for (parent, mut tf) in &mut heads {
        let Ok(s) = sheep.get(parent.parent()) else { continue };
        // Head down to the grass, nibbling (small chew bob); up and looking about when walking.
        let chew = (now * 5.0 + s.gait).sin() * 0.06 * s.graze;
        let look = (now * 0.4 + s.rng as f32 * 1e-9).sin() * 0.25 * (1.0 - s.graze);
        tf.rotation = Quat::from_rotation_y(look) * Quat::from_rotation_x(0.95 * s.graze + chew - 0.1 * (1.0 - s.graze));
    }
    for (parent, leg, mut tf) in &mut legs {
        let Ok(s) = sheep.get(parent.parent()) else { continue };
        let amp = (s.speed / 0.5).clamp(0.0, 1.6) * 0.45;
        tf.rotation = Quat::from_rotation_x((s.gait + leg.offset).sin() * amp);
    }
}

#[allow(clippy::type_complexity)]
fn shepherd_brain(
    time: Res<Time>,
    clock: Option<Res<crate::scene::SkyClock>>,
    siege: Option<Res<crate::siege::Siege>>,
    sheep: Query<&Sheep>,
    mut boy: Query<(&mut Shepherd, &mut crate::villagers::Villager, &mut Transform, &mut Visibility)>,
) {
    let dt = time.delta_secs().min(0.05);
    let t = sky_t(clock.as_deref());
    let night = siege.as_deref().is_some_and(|s| s.phase == crate::siege::GamePhase::Wave) || t >= 0.52 || t < 0.02;
    let pen = pen_time(t, siege.as_deref());
    let out: Vec<Vec2> = sheep.iter().filter(|s| s.mode != SMode::Penned).map(|s| s.pos).collect();
    for (mut sh, mut v, mut tf, mut vis) in &mut boy {
        // Off home once the flock is in and night has fallen; back at first light.
        let hide = night && out.is_empty();
        *vis = if hide { Visibility::Hidden } else { Visibility::Inherited };
        if hide {
            v.moving = false;
            continue;
        }
        sh.timer -= dt;
        if pen && !out.is_empty() {
            // Drive the stragglers: walk round behind the farthest one, away from the gate.
            let far = out.iter().copied().max_by(|a, b| a.distance(gate_out()).total_cmp(&b.distance(gate_out()))).unwrap();
            let behind = far + (far - gate_out()).normalize_or_zero() * 2.2;
            walk_body(&mut v, &mut tf, behind, 2.1, 0.4, dt);
        } else if pen {
            // Flock in: lean on the gate.
            if walk_body(&mut v, &mut tf, gate_out() + Vec2::new(-0.6, 1.1), 1.6, 0.3, dt) {
                crate::meadow::face_body(&mut v, &mut tf, FOLD_C, dt);
            }
        } else {
            if sh.timer <= 0.0 {
                sh.timer = 8.0 + hash01(time.elapsed_secs().to_bits()) * 10.0;
                let a = hash01(sh.timer.to_bits()) * TAU;
                sh.target = GRAZE_C + Vec2::from_angle(a) * (GRAZE_R + 1.5);
            }
            let tgt = sh.target;
            if walk_body(&mut v, &mut tf, tgt, 1.0, 0.3, dt) {
                crate::meadow::face_body(&mut v, &mut tf, GRAZE_C, dt);
            }
        }
    }
}

fn dog_brain(
    time: Res<Time>,
    clock: Option<Res<crate::scene::SkyClock>>,
    siege: Option<Res<crate::siege::Siege>>,
    sheep: Query<&Sheep>,
    boy: Query<(&crate::villagers::Villager, &Visibility), With<Shepherd>>,
    mut dogs: Query<(&mut SheepDog, &mut crate::quadruped::QuadDrive, &mut Transform, &mut Visibility), Without<Shepherd>>,
) {
    let dt = time.delta_secs().min(0.05);
    let pen = pen_time(sky_t(clock.as_deref()), siege.as_deref());
    let Ok((boy_v, boy_vis)) = boy.single() else { return };
    let out: Vec<Vec2> = sheep.iter().filter(|s| s.mode != SMode::Penned).map(|s| s.pos).collect();
    for (mut d, mut drive, mut tf, mut vis) in &mut dogs {
        *vis = *boy_vis;
        let (goal, speed) = if pen && !out.is_empty() {
            // Sweep a wide arc behind the flock (gathering), pressing it toward the gate.
            let c = out.iter().copied().sum::<Vec2>() / out.len() as f32;
            d.ang += dt * 0.9;
            let back = (c - gate_out()).normalize_or_zero();
            let side = Vec2::new(-back.y, back.x) * d.ang.sin() * 3.0;
            (c + back * 3.2 + side, 3.4)
        } else {
            // Trot at heel, or lie by the boy.
            (boy_v.pos + Vec2::new(0.9, 0.6), 2.2)
        };
        let to = goal - d.pos;
        let dist = to.length();
        let moving = dist > 0.6;
        if moving {
            d.pos += to / dist * (speed * dt).min(dist);
            let want = to.x.atan2(to.y);
            d.facing += crate::steer::wrap_pi(want - d.facing) * (dt * 6.0).min(1.0);
        }
        let m = if moving { 1.0 } else { 0.0 };
        drive.moving_amt += (m - drive.moving_amt) * (dt * 6.0).min(1.0);
        drive.run_amt = if speed > 3.0 && moving { 1.0 } else { 0.0 };
        let lie = if !moving && !pen { 1.0 } else { 0.0 };
        drive.lie_amt += (lie - drive.lie_amt) * (dt * 1.5).min(1.0);
        drive.phase += dt * if drive.run_amt > 0.5 { 11.0 } else { 7.0 } * drive.moving_amt;
        let y = crate::worldmap::ground_at_world(d.pos.x, d.pos.y).unwrap_or(tf.translation.y);
        tf.translation = Vec3::new(d.pos.x, y, d.pos.y);
        tf.rotation = Quat::from_rotation_y(d.facing);
    }
}

/// The flock's food flow into the town (derived every frame from the live, un-stolen sheep).
fn pasture_food(sheep: Query<&Sheep>, mut town: ResMut<crate::town::TownRes>) {
    let n = sheep.iter().filter(|s| !s.lamb).count() as u32;
    let f = tileworld_core::town_store::pasture_food(n);
    if town.0.pasture != f {
        town.0.pasture = f;
    }
}

/// A lamb each dawn (a survived night), up to the cap; yesterday's lambs grow up.
fn lambing(
    siege: Option<Res<crate::siege::Siege>>,
    mut flags: ResMut<WorldFlags>,
    mut sheep: Query<(&mut Sheep, &mut Transform)>,
    mut prev: Local<Option<crate::siege::GamePhase>>,
) {
    let Some(siege) = siege else { return };
    let dawn = *prev == Some(crate::siege::GamePhase::Wave) && siege.phase == crate::siege::GamePhase::Prep;
    *prev = Some(siege.phase);
    if !dawn {
        return;
    }
    for (mut s, mut tf) in &mut sheep {
        if s.lamb {
            s.lamb = false;
            tf.scale = Vec3::splat(ADULT_SCALE);
        }
    }
    let n = flags.get("sheep_count");
    if (2..SHEEP_CAP).contains(&n) {
        flags.add("sheep_count", 1);
        flags.add("lambs", 1);
        flags.set("lamb_pending", 1);
    }
}

/// Arson nights: an invader torch reaching the fold sets the hurdles alight — two penned sheep
/// die. Once per night; the flames die at dawn.
#[allow(clippy::too_many_arguments)]
fn fold_fire(
    mut commands: Commands,
    time: Res<Time>,
    siege: Option<Res<crate::siege::Siege>>,
    orks: Query<&crate::orks::Ork, (With<crate::orks::WaveInvader>, Without<crate::dying::Dying>)>,
    fires: Query<Entity, With<FoldFire>>,
    mut flags: ResMut<WorldFlags>,
    mut notice: ResMut<crate::ui::notice::Notice>,
) {
    let Some(siege) = siege else { return };
    let wave = siege.phase == crate::siege::GamePhase::Wave;
    if !wave {
        for e in &fires {
            commands.entity(e).try_despawn();
        }
        return;
    }
    let arson = tileworld_core::threat::threat_for(siege.wave_index.max(0) as usize).kind == tileworld_core::threat::ThreatKind::Arson;
    if !arson || flags.get("fold_burned_night") == siege.wave_index as i64 + 1 || !fires.is_empty() {
        return;
    }
    if !orks.iter().any(|o| o.pos.distance(FOLD_C) < 6.5) {
        return;
    }
    flags.set("fold_burned_night", siege.wave_index as i64 + 1);
    let lost = flags.get("sheep_count").min(2);
    flags.add("sheep_count", -lost);
    notice.push("The sheepfold is burning!", time.elapsed_secs_f64());
    for (k, p) in [(-FOLD_HX, -1.6), (0.0, FOLD_HZ), (FOLD_HX, 0.6), (1.4, -FOLD_HZ), (-1.8, FOLD_HZ)].into_iter().enumerate() {
        let w = FOLD_C + Vec2::new(p.0, p.1);
        let y = crate::worldmap::ground_at_world(w.x, w.y).unwrap_or(0.0);
        let mut e = commands.spawn((
            crate::flame_fx::flame_bundle(Vec3::new(w.x, y + 0.1, w.y), 1.1 + 0.2 * (k % 2) as f32, k as f32 * 0.7),
            FoldFire,
            BiomeEntity,
        ));
        if k % 2 == 0 {
            e.insert(crate::firelight::campfire_light(k as f32 * 0.3));
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn pasture_sits_on_open_meadow_clear_of_plots_and_fields() {
        for p in [FOLD_C, GRAZE_C, TROUGH.0, gate_out()] {
            assert!(!crate::town::near_build_plot(p.x, p.y), "{p} on a build plot");
            assert!(!crate::castle_ground::in_field(p.x, p.y), "{p} on a field");
            assert!(crate::castle::outside_dist(p.x, p.y) > 6.0, "{p} hugs the wall");
        }
        // Every bedding slot is inside the fold.
        for i in 0..SHEEP_CAP as usize {
            let l = slot(i) - FOLD_C;
            assert!(l.x.abs() < FOLD_HX - 0.3 && l.y.abs() < FOLD_HZ - 0.3, "slot {i} outside the fold");
        }
        // The grazing ground stays off the build plots.
        for k in 0..32 {
            let p = GRAZE_C + Vec2::from_angle(k as f32 / 32.0 * TAU) * GRAZE_R;
            assert!(!crate::town::near_build_plot(p.x, p.y), "graze edge {p} on a plot");
        }
    }

    #[test]
    fn pen_time_follows_the_sky() {
        assert!(!pen_time(0.25, None));
        assert!(pen_time(0.45, None));
        assert!(pen_time(0.8, None));
        assert!(pen_time(0.01, None));
        assert!(!pen_time(0.1, None));
    }
}
