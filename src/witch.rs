//! **Old Seffa at the Witch's Hut** (design: `docs/superpowers/specs/2026-10-13-zywa-wyspa-design.md`
//! §2 item 6, §4). The hut has always stood in the swamp (`ruins.rs` landmark, trial + shrine); now
//! somebody lives there: an old desert-born woman — a townsperson body on the shared biped rig
//! (`peasant_model::elder_woman_meshes`: kirtle, faded headscarf, shawl) with a blackthorn staff and
//! a basket — working round her yard: stirring the cauldron, hanging herbs on the drying rack,
//! throwing hay to the goat's stake. She does not deal with a Crown knight: while her door is shut
//! she goes indoors whenever he comes near (and at night), and comes out again once he has gone.
//!
//! **The introduction — the silent trade.** Outside her wattle fence, by the shut wicket, lies a
//! flat stone. E "Leave an ingredient" puts one of the hero's ingredients on it (a herb bundle lies
//! there). One offering is enough: the wicket swings open, she comes out to the stone, takes it and
//! leaves a stoppered jar in its place. E "Take the jar" grants the brew made from it
//! (`bog_draught` / `wolfsbane` / `hornet_balm`, spec table). Nobody says a word.
//! **After that she is a shop.** The wicket stays open and the hut's lore changes. She no longer
//! hides from him (only at night) and turns to him when he comes close. E "Trade with Old Seffa"
//! opens the shop as `ShopVendor::Witch` (her brews; she buys ingredients through the SELL list).
//!
//! Player state is three `savegame::WorldFlags` (`witch_open`, `witch_stone`, `witch_brew`), so it
//! saves and resets with the run. The yard and Seffa are spawned lazily once the world (the hut
//! landmark) and the kit exist, tagged `BiomeEntity` so a rebuild reaps and re-spawns them.
//! Models: `swamp_folk.glb` (`sf_*`).

use std::f32::consts::{FRAC_PI_2, PI};

use bevy::camera::visibility::VisibilityRange;
use bevy::prelude::*;
use tileworld_core::shop_catalog::ShopVendor;

use crate::biome::{Biome, BiomeEntity};
use crate::biped::{BipedDrive, BipedPart, PoseOverride};
use crate::combat_fx::{FloatQueue, FloatReq};
use crate::game_state::{Modal, SimAppExt};
use crate::interaction::{Interactable, Interacted};
use crate::player::anim::village::{self as clip, Act, Carry};
use crate::player::anim::Pose;
use crate::player::Joint;
use crate::savegame::WorldFlags;
use crate::siege::{GamePhase, Siege};

/// The hut landmark's spawn scale (`ruins::populate_landmarks`).
const HUT_SCALE: f32 = 1.4;
/// Hut-model-local spots (unscaled): where she stands for each chore, and what she faces.
const STIR_AT: Vec2 = Vec2::new(1.12, 1.95);
const CAULDRON: Vec2 = Vec2::new(1.75, 1.3);
const RACK: Vec2 = Vec2::new(-1.85, 2.8);
const RACK_AT: Vec2 = Vec2::new(-1.85, 3.25);
const STAKE: Vec2 = Vec2::new(3.05, -0.55);
const FEED_AT: Vec2 = Vec2::new(2.45, -0.05);
/// The ladder foot: she climbs in (hides) here.
const DOOR_AT: Vec2 = Vec2::new(0.0, 2.2);
/// The trade stone (its fence runs 0.8 behind it, toward the hut), and where she stands to take
/// what lies on it (inside the fence, reaching over).
const STONE: Vec2 = Vec2::new(0.3, 4.75);
const STONE_REACH: Vec2 = Vec2::new(0.3, 3.95);
/// Stone top height (swamp_folk.py `sf_trade_stone`).
const STONE_TOP: f32 = 0.4;

/// She goes in when the hero comes this close (while her door is shut) / comes out past `OUT_R`.
const SHY_R: f32 = 14.0;
const OUT_R: f32 = 22.0;
/// She turns to the hero inside this (door open).
const GREET_R: f32 = 6.5;
const WALK: f32 = 0.85;

const SKIN: u32 = 0x9a6a4c;
const DRESS: u32 = 0x3b342c;
const SCARF: u32 = 0x56607a; // a desert indigo, sun-faded
const SHAWL: u32 = 0x5e2f26; // madder wool gone dark with smoke (never near her skin tone)

/// Ingredient → the brew Seffa leaves for it (spec §2 table: bog_draught = marsh_herb + toad_glow,
/// wolfsbane = venom + vulture_quill, hornet_balm = honeycomb + goat_charm). Stone code = index + 1.
const INGREDIENTS: [(&str, &str); 7] = [
    ("toad_glow", "bog_draught"),
    ("marsh_herb", "bog_draught"),
    ("venom", "wolfsbane"),
    ("vulture_quill", "wolfsbane"),
    ("honeycomb", "hornet_balm"),
    ("goat_charm", "hornet_balm"),
    ("antlion_chitin", "bog_draught"),
];
const BREWS: [&str; 3] = ["bog_draught", "wolfsbane", "hornet_balm"];

fn brew_code(id: &str) -> i64 {
    BREWS.iter().position(|b| *b == id).map_or(0, |i| i as i64 + 1)
}

/// The brew code for an ingredient left on the stone (code = INGREDIENTS index + 1).
pub fn brew_for(stone_code: i64) -> i64 {
    INGREDIENTS.get((stone_code - 1).max(0) as usize).map_or(1, |(_, b)| brew_code(b))
}

#[derive(Clone, Copy)]
struct Hut {
    pos: Vec2,
    y: f32,
    yaw: f32,
}

impl Hut {
    fn find() -> Option<Self> {
        crate::ruins::landmark_sites().iter().find(|s| s.biome == Biome::Swamp).map(|s| Hut { pos: s.pos, y: s.y, yaw: s.yaw })
    }
    /// Hut-model-local (unscaled) → world XZ.
    fn at(&self, l: Vec2) -> Vec2 {
        let l = l * HUT_SCALE;
        let (s, c) = self.yaw.sin_cos();
        self.pos + Vec2::new(l.x * c + l.y * s, -l.x * s + l.y * c)
    }
}

/// The trodden yard (hut-local centre, world radius): no reeds or scatter on it.
const YARD_C: Vec2 = Vec2::new(0.4, 2.9);
const YARD_R: f32 = 7.0;
static YARD: std::sync::Mutex<Option<(Vec2, f32)>> = std::sync::Mutex::new(None);

pub fn reset_plan() {
    *YARD.lock().unwrap() = None;
}

/// World plan (after the story layers, before the scatter): keep her yard clear.
pub fn plan() {
    let Some(hut) = Hut::find() else { return };
    let c = hut.at(YARD_C);
    crate::blockers::reserve_visual(c.x, c.y, YARD_R);
    *YARD.lock().unwrap() = Some((c, YARD_R));
}

pub fn planned_footprints() -> Vec<(Vec2, f32)> {
    YARD.lock().unwrap().iter().copied().collect()
}

pub fn overlaps_planned(x: f32, z: f32, r: f32) -> bool {
    YARD.lock().unwrap().is_some_and(|(c, yr)| c.distance_squared(Vec2::new(x, z)) < (yr + r).powi(2))
}

fn ground(p: Vec2) -> f32 {
    crate::worldmap::ground_at_world(p.x, p.y).unwrap_or(0.0)
}

/// Yaw that turns a +Z-forward rig to face `d`.
fn face(d: Vec2) -> f32 {
    d.x.atan2(d.y)
}

// ── Components ───────────────────────────────────────────────────────────────────────

#[derive(Clone, Copy, PartialEq, Debug)]
enum Chore {
    Stir,
    Hang,
    Feed,
}

#[derive(Clone, Copy, PartialEq, Debug)]
enum St {
    Walk(Chore),
    Work(Chore),
    GoIn,
    Inside,
    Greet,
    /// Out to the stone for the first offering…
    Fetch,
    /// …taking it and leaving the jar.
    Give,
}

#[derive(Component)]
pub struct Seffa {
    st: St,
    t0: f32,
    until: f32,
    chore: usize,
    walk_phase: f32,
    from: Pose,
    blend_t0: f32,
    last: Pose,
    prev: Option<St>,
    away_since: f32,
    props: Option<(Entity, Entity)>,
}

#[derive(Component)]
struct TradeStone;
#[derive(Component)]
struct StoneHerbs;
#[derive(Component)]
struct StoneJar;
#[derive(Component)]
struct Wicket {
    closed: Quat,
}
/// Seffa's goat: stands, lies down a while, gets up (eased).
#[derive(Component)]
struct Goat {
    flip_at: f32,
    lying: bool,
}
const GOAT_SCALE: f32 = 0.62;

/// The last torso / head rotation [`stoop`] wrote (so a culled, un-reposed rig isn't bent twice).
#[derive(Component)]
struct Stooped(Quat);

pub struct WitchPlugin;

impl Plugin for WitchPlugin {
    fn build(&self, app: &mut App) {
        app.add_systems(Update, (stage_env, spawn_yard, attach_props, sync_yard, hut_lore).run_if(crate::rts::in_campaign))
            .add_systems(Update, stoop.after(crate::biped::animate_biped))
            .add_sim_systems((seffa_brain, stone_and_shop, goat_life).run_if(crate::rts::in_campaign));
    }
}

/// Screenshot staging: `FOREST_WITCH=open` (her door open: wicket swung, she stays and turns to the
/// hero, a jar waiting on the stone) or `FOREST_WITCH=herbs` (the first offering just left: she
/// comes out to fetch it).
fn stage_env(mut flags: ResMut<WorldFlags>, mut mode: Local<Option<String>>) {
    let m = mode.get_or_insert_with(|| std::env::var("FOREST_WITCH").unwrap_or_default());
    match m.as_str() {
        "open" if !flags.is("witch_open") => {
            flags.set("witch_open", 1);
            flags.set("witch_brew", 2);
        }
        "herbs" if !flags.is("witch_open") => {
            flags.set("witch_open", 1);
            flags.set("witch_stone", 2);
        }
        _ => {}
    }
}

fn range() -> VisibilityRange {
    VisibilityRange { start_margin: 0.0..0.0, end_margin: 110.0..130.0, use_aabb: true }
}

/// Once the hut and the kit exist (and again after a world rebuild reaped the yard): Seffa, the
/// trade stone + fence + wicket, the drying rack, the goat's stake.
#[allow(clippy::too_many_arguments)]
fn spawn_yard(
    mut commands: Commands,
    mut meshes: ResMut<Assets<Mesh>>,
    mut creature_mats: ResMut<Assets<crate::creature::CreatureMaterial>>,
    landmarks: Query<&crate::landmarks::Landmark>,
    existing: Query<(), With<TradeStone>>,
    now: Res<Time>,
) {
    if !existing.is_empty() || !landmarks.iter().any(|l| l.name == crate::landmarks::WITCH_HUT) {
        return;
    }
    let (Some(hut), Some(kit)) = (Hut::find(), crate::realforest::get().filter(|k| k.has("sf_trade_stone"))) else { return };
    let place = |commands: &mut Commands, name: &str, l: Vec2, yaw: f32| -> Option<Entity> {
        let p = hut.at(l);
        let tf = Transform::from_xyz(p.x, ground(p) - 0.04, p.y).with_rotation(Quat::from_rotation_y(hut.yaw + yaw));
        let e = kit.spawn_static_with(commands, name, tf, range())?;
        commands.entity(e).insert(BiomeEntity);
        Some(e)
    };
    // The stone faces away from the hut (its fence toward the yard).
    let stone_yaw = hut.yaw + PI;
    let sp = hut.at(STONE);
    let sy = ground(sp) - 0.04;
    let stone_rot = Quat::from_rotation_y(stone_yaw);
    if let Some(e) = kit.spawn_static_with(&mut commands, "sf_trade_stone", Transform::from_xyz(sp.x, sy, sp.y).with_rotation(stone_rot), range()) {
        commands.entity(e).insert((BiomeEntity, TradeStone, Interactable::new("Leave an ingredient", 2.0)));
    }
    let local = |x: f32, z: f32| {
        let o = stone_rot * Vec3::new(x, 0.0, z);
        Vec2::new(sp.x + o.x, sp.y + o.z)
    };
    for (x0, x1, z) in [(-3.2f32, -0.62f32, 0.82f32), (0.62, 3.1, 0.87)] {
        let c = local((x0 + x1) * 0.5, z);
        crate::blockers::add_obb(c.x, c.y, (x1 - x0) * 0.5, 0.07, stone_yaw);
    }
    crate::blockers::add_obb(sp.x, sp.y, 0.45, 0.36, stone_yaw);
    let top = Vec3::new(sp.x, sy + STONE_TOP, sp.y);
    if let Some(e) = kit.spawn_static_with(&mut commands, "sf_offer_herbs", Transform::from_translation(top).with_rotation(stone_rot), range()) {
        commands.entity(e).insert((BiomeEntity, StoneHerbs, Visibility::Hidden));
    }
    if let Some(e) = kit.spawn_static_with(&mut commands, "sf_brew_jar", Transform::from_translation(top + Vec3::new(0.0, -0.01, 0.0)).with_rotation(stone_rot), range()) {
        commands.entity(e).insert((BiomeEntity, StoneJar, Visibility::Hidden));
    }
    let hinge = local(0.6, 0.8);
    if let Some(e) = kit.spawn_static_with(&mut commands, "sf_wicket", Transform::from_xyz(hinge.x, ground(hinge) - 0.04, hinge.y).with_rotation(stone_rot), range()) {
        commands.entity(e).insert((BiomeEntity, Wicket { closed: stone_rot }));
    }
    place(&mut commands, "sf_herb_rack", RACK, 0.0);
    place(&mut commands, "sf_goat_stake", STAKE, 0.4);
    // Her goat on its tether (the island's goat is the small deer rig, as in `wildlife`).
    let gp = hut.at(STAKE + Vec2::new(0.45, 0.5));
    let goat_mat = crate::creature::make_creature_material(&mut creature_mats);
    let goat = commands
        .spawn((
            Transform::from_xyz(gp.x, ground(gp), gp.y).with_rotation(Quat::from_rotation_y(hut.yaw + 2.2)).with_scale(Vec3::splat(GOAT_SCALE)),
            Visibility::Visible,
            crate::quadruped::QuadDrive::new(crate::quadruped::QuadSpecies::Deer),
            Goat { flip_at: now.elapsed_secs() + 18.0, lying: false },
            BiomeEntity,
        ))
        .id();
    let gh = crate::quadruped::quad_meshes(crate::quadruped::QuadSpecies::Deer).upload(&mut meshes);
    crate::quadruped::spawn_quad(&mut commands, goat, &goat_mat, crate::quadruped::QuadSpecies::Deer, gh);

    // Old Seffa.
    let Some(body) = crate::peasant_model::elder_woman_meshes(SKIN, DRESS, SCARF, SHAWL) else {
        warn!("witch: people.glb has no kirtle / headwrap \u{2014} Old Seffa not spawned");
        return;
    };
    let rig = crate::peasant_model::person_rig(crate::peasant_model::PeasantKind::Unemployed, false, 11);
    let scale = crate::villagers::SCALE * rig.root;
    let at = hut.at(STIR_AT);
    let mat = crate::creature::make_creature_material(&mut creature_mats);
    let first = clip::stand(Act::Stand, 0.0, 1.0);
    let root = commands
        .spawn((
            Transform {
                translation: Vec3::new(at.x, ground(at), at.y),
                rotation: Quat::from_rotation_y(face(hut.at(CAULDRON) - at)),
                scale: Vec3::splat(scale),
            },
            Visibility::Visible,
            BipedDrive { phase: 1.7, ..default() },
            PoseOverride(first),
            Seffa {
                st: St::Work(Chore::Stir),
                t0: now.elapsed_secs(),
                until: now.elapsed_secs() + 12.0,
                chore: 0,
                walk_phase: 0.0,
                from: first,
                blend_t0: -10.0,
                last: first,
                prev: None,
                away_since: 0.0,
                props: None,
            },
            BiomeEntity,
        ))
        .id();
    let h = body.upload(&mut meshes);
    crate::biped::spawn_biped_scaled(
        &mut commands,
        root,
        &mat,
        h,
        rig.head_scale,
        1.0,
        rig.hip_dx,
        rig.shoulder_dx,
        crate::villagers::VIL_RIG_OFF - rig.drop,
        None,
        rig.limbs,
    );
    info!("witch: Old Seffa's yard at the hut {:.1},{:.1} (stone {:.1},{:.1})", hut.pos.x, hut.pos.y, sp.x, sp.y);
    let _ = hut.y;
}

/// Hang the staff (right hand) and the basket (left forearm) on her rig once its joints exist.
fn attach_props(mut commands: Commands, mut q: Query<(Entity, &mut Seffa, &Transform)>, parts: Query<(Entity, &BipedPart)>) {
    let Some(kit) = crate::realforest::get() else { return };
    for (root, mut s, tf) in &mut q {
        if s.props.is_some() {
            continue;
        }
        let find = |j: Joint| parts.iter().find(|(_, p)| p.root == root && p.joint == j).map(|(e, _)| e);
        let (Some(er), Some(el)) = (find(Joint::ElbowR), find(Joint::ElbowL)) else { continue };
        let _ = tf;
        // Elbow frame: the forearm runs down local -Y, the fist at y -0.25.
        let staff = commands.spawn((Transform::from_xyz(0.0, -0.25, 0.02), Visibility::Inherited)).id();
        kit.attach_static(&mut commands.entity(staff), "sf_staff", Transform::IDENTITY);
        commands.entity(er).add_child(staff);
        let basket = commands
            .spawn((Transform::from_xyz(0.0, -0.13, -0.02).with_rotation(Quat::from_rotation_x(FRAC_PI_2)), Visibility::Inherited))
            .id();
        kit.attach_static(&mut commands.entity(basket), "sf_basket", Transform::IDENTITY);
        commands.entity(el).add_child(basket);
        s.props = Some((staff, basket));
    }
}

fn chore_spot(c: Chore) -> (Vec2, Vec2) {
    match c {
        Chore::Stir => (STIR_AT, CAULDRON),
        Chore::Hang => (RACK_AT, RACK),
        Chore::Feed => (FEED_AT, STAKE),
    }
}

const ROUND: [Chore; 4] = [Chore::Stir, Chore::Hang, Chore::Stir, Chore::Feed];

/// Her day: chores in a round, walking between them with the basket; indoors when the knight comes
/// (door shut) or the night falls; out to the stone for the first offering; turned to him when her
/// door is open.
#[allow(clippy::too_many_arguments)]
fn seffa_brain(
    time: Res<Time>,
    siege: Res<Siege>,
    mut flags: ResMut<WorldFlags>,
    hero: Res<crate::player::HeroState>,
    mut q: Query<(&mut Seffa, &mut Transform, &mut PoseOverride, &mut Visibility)>,
    mut vis: Query<&mut Visibility, Without<Seffa>>,
) {
    let Some(hut) = Hut::find() else { return };
    let now = time.elapsed_secs();
    let dt = time.delta_secs();
    let open = flags.is("witch_open");
    let offered = flags.get("witch_stone");
    let night = siege.phase == GamePhase::Wave;
    for (mut s, mut tf, mut pose, mut v) in &mut q {
        let pos = Vec2::new(tf.translation.x, tf.translation.z);
        let hero_d = hero.pos.distance(pos).min(hero.pos.distance(hut.pos));
        let shy = night || (!open && hero_d < SHY_R);
        // ── state transitions ──
        match s.st {
            St::Inside => {
                if !night && (open || hero_d > OUT_R) {
                    if s.away_since == 0.0 {
                        s.away_since = now;
                    }
                    if now - s.away_since > 4.0 {
                        *v = Visibility::Visible;
                        let door = hut.at(DOOR_AT);
                        tf.translation = Vec3::new(door.x, ground(door), door.y);
                        s.st = St::Walk(ROUND[s.chore % ROUND.len()]);
                    }
                } else {
                    s.away_since = 0.0;
                }
            }
            St::GoIn => {}
            _ if shy => s.st = St::GoIn,
            St::Fetch => {}
            St::Give => {
                if now > s.until {
                    // Taken; the jar in its place.
                    if offered != 0 {
                        flags.set("witch_brew", brew_for(offered));
                        flags.set("witch_stone", 0);
                    }
                    s.st = St::Walk(ROUND[s.chore % ROUND.len()]);
                }
            }
            _ if offered != 0 => s.st = St::Fetch,
            St::Greet => {
                if hero.pos.distance(pos) > GREET_R + 1.5 {
                    s.st = St::Walk(ROUND[s.chore % ROUND.len()]);
                }
            }
            _ if open && hero.pos.distance(pos) < GREET_R => s.st = St::Greet,
            St::Work(_) if now > s.until => {
                s.chore += 1;
                s.st = St::Walk(ROUND[s.chore % ROUND.len()]);
            }
            _ => {}
        }
        if s.prev != Some(s.st) {
            s.prev = Some(s.st);
            s.from = s.last;
            s.blend_t0 = now;
            s.t0 = now;
            match s.st {
                St::Work(_) => s.until = now + 14.0 + 8.0 * ((now * 1.3).sin() * 0.5 + 0.5),
                St::Give => s.until = now + 3.2,
                _ => {}
            }
        }
        // ── motion ──
        let target = match s.st {
            St::Walk(c) => Some((hut.at(chore_spot(c).0), WALK)),
            St::Fetch => Some((hut.at(STONE_REACH), WALK)),
            St::GoIn => Some((hut.at(DOOR_AT), WALK * 1.45)),
            _ => None,
        };
        let mut moving = 0.0;
        if let Some((to, speed)) = target {
            let d = to - pos;
            if d.length() > 0.12 {
                let step = d.normalize() * (speed * dt).min(d.length());
                let np = pos + step;
                tf.translation = Vec3::new(np.x, ground(np), np.y);
                tf.rotation = tf.rotation.slerp(Quat::from_rotation_y(face(step)), (dt * 4.0).min(1.0));
                s.walk_phase += dt * 6.2 * speed / WALK;
                moving = 1.0;
            } else {
                match s.st {
                    St::Walk(c) => s.st = St::Work(c),
                    St::Fetch => s.st = St::Give,
                    St::GoIn => {
                        s.st = St::Inside;
                        s.away_since = 0.0;
                        *v = Visibility::Hidden;
                    }
                    _ => {}
                }
            }
        }
        // Face the work / the hero.
        let look_at = match s.st {
            St::Work(c) => Some(hut.at(chore_spot(c).1)),
            St::Greet => Some(hero.pos),
            St::Give => Some(hut.at(STONE)),
            _ => None,
        };
        if let Some(at) = look_at {
            let d = at - pos;
            if d.length() > 0.05 {
                tf.rotation = tf.rotation.slerp(Quat::from_rotation_y(face(d)), (dt * 3.0).min(1.0));
            }
        }
        // ── pose ──
        let t = now - s.t0 + 1.7;
        let p = match s.st {
            St::Walk(_) | St::GoIn | St::Fetch => clip::carry_walk(t, s.walk_phase, moving, 0.0, Carry::Basket),
            St::Give => clip::stand(Act::Pay, t, 1.0),
            St::Work(Chore::Stir) => clip::stand(Act::Draw, t * 0.55, 1.0),
            St::Work(Chore::Hang) => clip::stand(Act::Hang, t * 0.7, 1.0),
            St::Work(Chore::Feed) => clip::stand(Act::Scatter, t * 0.8, 1.0),
            St::Greet => {
                let mut p = clip::stand(Act::Stand, t, 1.0);
                clip::look(&mut p, 0.0, 0.08);
                p
            }
            St::Inside => s.last,
        };
        let k = ((now - s.blend_t0) / 0.5).clamp(0.0, 1.0);
        let out = clip::blend(&s.from, &p, k * k * (3.0 - 2.0 * k));
        s.last = out;
        pose.0 = out;
        // Staff while walking / greeting, basket while walking / feeding.
        if let Some((staff, basket)) = s.props {
            let staff_on = matches!(s.st, St::Walk(_) | St::GoIn | St::Fetch | St::Greet);
            let basket_on = matches!(s.st, St::Walk(_) | St::GoIn | St::Work(Chore::Feed));
            for (e, on) in [(staff, staff_on), (basket, basket_on)] {
                if let Ok(mut pv) = vis.get_mut(e) {
                    let want = if on { Visibility::Inherited } else { Visibility::Hidden };
                    if *pv != want {
                        *pv = want;
                    }
                }
            }
        }
    }
}

/// An old woman's carriage: bent forward at the chest, the head lifted to see. Applied on top of
/// whatever the animator wrote this frame (and only then — a culled rig keeps its last pose).
#[allow(clippy::type_complexity)]
fn stoop(
    mut commands: Commands,
    seffa: Query<Entity, With<Seffa>>,
    mut parts: Query<(Entity, &BipedPart, &mut Transform, Option<&mut Stooped>)>,
) {
    let Ok(root) = seffa.single() else { return };
    for (e, part, mut tf, stooped) in &mut parts {
        if part.root != root {
            continue;
        }
        let bend = match part.joint {
            Joint::Torso => Quat::from_rotation_x(0.24),
            Joint::Head => Quat::from_rotation_x(-0.16),
            _ => continue,
        };
        match stooped {
            Some(s) if s.0 == tf.rotation => {}
            Some(mut s) => {
                tf.rotation *= bend;
                s.0 = tf.rotation;
            }
            None => {
                tf.rotation *= bend;
                commands.entity(e).try_insert(Stooped(tf.rotation));
            }
        }
    }
}

fn goat_life(time: Res<Time>, mut q: Query<(&mut Goat, &mut crate::quadruped::QuadDrive)>) {
    let now = time.elapsed_secs();
    for (mut g, mut d) in &mut q {
        if now > g.flip_at {
            g.lying = !g.lying;
            g.flip_at = now + if g.lying { 25.0 } else { 16.0 };
        }
        let target = if g.lying { 1.0 } else { 0.0 };
        d.lie_amt += (target - d.lie_amt) * (time.delta_secs() * 0.8).min(1.0);
    }
}

/// The stone's prompt for the current flags: room for the first offering, a jar to take, or nothing
/// (the introduction is done; she trades in person now).
fn stone_prompt(flags: &WorldFlags) -> Option<&'static str> {
    if flags.get("witch_brew") != 0 {
        Some("Take the jar")
    } else if flags.is("witch_open") {
        None
    } else {
        Some("Leave an ingredient")
    }
}

/// E on the stone (the first offering / taking the jar), E on Seffa (her shop).
#[allow(clippy::too_many_arguments)]
fn stone_and_shop(
    mut commands: Commands,
    mut ev: MessageReader<Interacted>,
    time: Res<Time>,
    mut flags: ResMut<WorldFlags>,
    mut inv: ResMut<crate::inventory::Inventory>,
    mut toasts: ResMut<crate::inventory::Toasts>,
    mut floats: ResMut<FloatQueue>,
    mut cues: MessageWriter<crate::audio::AudioCue>,
    mut vendor: ResMut<crate::economy::ActiveVendor>,
    mut modal: ResMut<NextState<Modal>>,
    stones: Query<(Entity, &GlobalTransform, Option<&Interactable>), With<TradeStone>>,
    seffa: Query<(Entity, &Seffa, Option<&Interactable>)>,
) {
    let now = time.elapsed_secs();
    let open = flags.is("witch_open");
    for Interacted(e) in ev.read() {
        if let Ok((_, gt, _)) = stones.get(*e) {
            let head = gt.translation() + Vec3::Y * 1.3;
            let brew = flags.get("witch_brew");
            if brew != 0 {
                let id = BREWS[((brew - 1).max(0) as usize).min(BREWS.len() - 1)];
                if crate::inventory::try_grant(&mut inv.0, &mut toasts.0, id, 1, now as f64) {
                    flags.set("witch_brew", 0);
                    cues.write(crate::audio::AudioCue::Forage);
                }
            } else if !open {
                match INGREDIENTS.iter().position(|(id, _)| inv.0.count_item(id) > 0) {
                    Some(i) => {
                        // One offering is enough: the wicket opens and she comes for it.
                        inv.0.consume_item(INGREDIENTS[i].0, 1);
                        flags.set("witch_stone", i as i64 + 1);
                        flags.set("witch_open", 1);
                        cues.write(crate::audio::AudioCue::Forage);
                    }
                    None => {
                        floats.0.push(FloatReq { world: head, text: "You have nothing she would want.".into(), color: Color::srgb(0.7, 0.7, 0.75), scale: 0.9 });
                        cues.write(crate::audio::AudioCue::UiSelect);
                    }
                }
            }
        } else if seffa.contains(*e) && open {
            crate::economy::open_vendor(ShopVendor::Witch, &mut vendor, &mut modal);
        }
    }
    // Prompts follow the flags.
    let want = stone_prompt(&flags);
    for (e, _, it) in &stones {
        match (want, it.map(|i| i.prompt.as_str())) {
            (Some(w), Some(have)) if w == have => {}
            (Some(w), _) => {
                commands.entity(e).try_insert(Interactable::new(w, 2.0));
            }
            (None, Some(_)) => {
                commands.entity(e).try_remove::<Interactable>();
            }
            (None, None) => {}
        }
    }
    for (e, s, it) in &seffa {
        let available = open && !matches!(s.st, St::Inside | St::GoIn | St::Fetch | St::Give);
        match (available, it.is_some()) {
            (true, false) => {
                commands.entity(e).try_insert(Interactable::new("Trade with Old Seffa", 2.6));
            }
            (false, true) => {
                commands.entity(e).try_remove::<Interactable>();
            }
            _ => {}
        }
    }
}

/// What lies on the stone, and the wicket: shut, or swung open into the yard once she trades.
fn sync_yard(
    flags: Res<WorldFlags>,
    time: Res<Time>,
    mut herbs: Query<&mut Visibility, (With<StoneHerbs>, Without<StoneJar>)>,
    mut jar: Query<&mut Visibility, (With<StoneJar>, Without<StoneHerbs>)>,
    mut wicket: Query<(&Wicket, &mut Transform)>,
) {
    let show = |v: &mut Visibility, on: bool| {
        let want = if on { Visibility::Inherited } else { Visibility::Hidden };
        if *v != want {
            *v = want;
        }
    };
    for mut v in &mut herbs {
        show(&mut v, flags.get("witch_stone") != 0);
    }
    for mut v in &mut jar {
        show(&mut v, flags.get("witch_brew") != 0);
    }
    let open = flags.is("witch_open");
    for (w, mut tf) in &mut wicket {
        let target = if open { w.closed * Quat::from_rotation_y(1.35) } else { w.closed };
        if tf.rotation.angle_between(target) > 1e-3 {
            tf.rotation = tf.rotation.slerp(target, (time.delta_secs() * 1.5).min(1.0));
        }
    }
}

/// The hut's lore follows her door.
fn hut_lore(flags: Res<WorldFlags>, mut q: Query<&mut crate::landmarks::Landmark>, mut last: Local<Option<bool>>) {
    let open = flags.is("witch_open");
    for mut lm in &mut q {
        if lm.name == crate::landmarks::WITCH_HUT && (*last != Some(open) || lm.is_added()) {
            lm.set_lore(if open { crate::landmarks::WITCH_HUT_LORE_OPEN } else { crate::landmarks::WITCH_HUT_LORE_SHUT });
            *last = Some(open);
        }
    }
}

/// Screenshot cameras (`FOREST_SHOT_STORIES=wild`, via `wild_sites::shot_cams`): the yard from the
/// path, the trade stone and wicket, Seffa at her cauldron.
pub fn shot_cams() -> Vec<(String, Transform)> {
    let Some(hut) = Hut::find() else { return Vec::new() };
    let cam = |name: &str, eye: Vec2, lift: f32, aim: Vec2, aim_lift: f32| {
        let e = Vec3::new(eye.x, ground(eye).max(crate::worldmap::SEA_Y) + lift, eye.y);
        let a = Vec3::new(aim.x, ground(aim) + aim_lift, aim.y);
        info!("witch cam {name}: {:.1},{:.1},{:.1} -> {:.1},{:.1},{:.1}", e.x, e.y, e.z, a.x, a.y, a.z);
        (name.to_string(), Transform::from_translation(e).looking_at(a, Vec3::Y))
    };
    vec![
        cam("witch_yard", hut.at(Vec2::new(4.2, 9.0)), 2.6, hut.at(Vec2::new(0.4, 2.4)), 1.2),
        cam("witch_stone", hut.at(Vec2::new(-1.4, 7.3)), 1.6, hut.at(STONE), 0.5),
        cam("witch_seffa", hut.at(Vec2::new(3.4, 3.9)), 1.6, hut.at(STIR_AT), 1.0),
    ]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ingredients_make_the_spec_brews() {
        let code = |id: &str| INGREDIENTS.iter().position(|(i, _)| *i == id).unwrap() as i64 + 1;
        assert_eq!(BREWS[brew_for(code("marsh_herb")) as usize - 1], "bog_draught");
        assert_eq!(BREWS[brew_for(code("toad_glow")) as usize - 1], "bog_draught");
        assert_eq!(BREWS[brew_for(code("venom")) as usize - 1], "wolfsbane");
        assert_eq!(BREWS[brew_for(code("vulture_quill")) as usize - 1], "wolfsbane");
        assert_eq!(BREWS[brew_for(code("honeycomb")) as usize - 1], "hornet_balm");
        assert_eq!(BREWS[brew_for(code("goat_charm")) as usize - 1], "hornet_balm");
        for (id, brew) in INGREDIENTS {
            assert!(tileworld_core::inventory::item_def(id).is_some(), "{id}");
            assert!(tileworld_core::inventory::item_def(brew).is_some(), "{brew}");
        }
    }

    #[test]
    fn stone_prompts_follow_the_introduction() {
        let mut g = WorldFlags::default();
        assert_eq!(stone_prompt(&g), Some("Leave an ingredient"));
        g.set("witch_open", 1);
        g.set("witch_stone", 2);
        assert_eq!(stone_prompt(&g), None);
        g.set("witch_stone", 0);
        g.set("witch_brew", 1);
        assert_eq!(stone_prompt(&g), Some("Take the jar"));
        g.set("witch_brew", 0);
        assert_eq!(stone_prompt(&g), None);
    }
}
