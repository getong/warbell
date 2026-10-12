//! **The Field of the Answered** — the orks' graveyard on the swamp's north edge, beside the road the
//! night waves walk (design: `docs/superpowers/specs/2026-10-13-zywa-wyspa-design.md` §2 item 7, §4).
//! It grew out of the old "Ork Barrows" discovery site (`wild_sites.rs`): that barrow group is now the
//! field's oldest corner, with rows of turfed long barrows and notched iron grave stones behind it
//! and, toward the road, two rows of FRESH graves (a fixed set — the field does not change as the
//! story moves on).
//!
//! By day one or two old ork mourners tend the graves (brainless puppets, never in a hit query);
//! they leave when the hero comes near. Two E verbs, no comment either way:
//! - **"Leave an offering"** (meat or fish): a Resist blessing, once a day.
//! - **"Take grave goods"** (once): +40 gold and an ork axe — and `graveyard_desecrated`: the
//!   mourners never come back and two more berserkers march for two nights (`siege::NightMods`).
//!
//! Planned at build phase 4 after `wild_sites::plan` (a spiral search round the spec's spot, world
//! (-25, 105)), folded into `poi::story_clearings`; spawned at phase 32. Models: `swamp_folk.glb`
//! (`tools/blender_forest/swamp_folk.py`, the `og_*` pieces) + `wild_sites.glb`'s `site_ork_barrows`.

use std::f32::consts::{FRAC_PI_2, PI, TAU};
use std::sync::Mutex;

use bevy::camera::visibility::VisibilityRange;
use bevy::prelude::*;
use tileworld_core::buff_store::BuffKind;

use crate::biome::{Biome, BiomeEntity};
use crate::combat_fx::{FloatQueue, FloatReq};
use crate::game_state::SimAppExt;
use crate::interaction::{Interactable, Interacted};
use crate::savegame::WorldFlags;
use crate::siege::{GamePhase, Siege};

/// The spec's spot (world, MAP_SCALE 3.9): the swamp's north rim on the orks' road.
const TARGET: Vec2 = Vec2::new(-25.0, 105.0);
/// Visual radius the field reserves (the fresh rows reach ~8.8 from the centre).
pub const FOOT: f32 = 9.0;
/// Search reach round [`TARGET`].
const SEARCH_R: f32 = 60.0;
/// Max terrain spread under the field (every piece seats on its own ground).
const FLAT: f32 = 1.8;
const NAME: &str = "The Field of the Answered";
const LORE: &str = "Row on row of ork graves. The newest earth is still soft.";
/// The fresh graves (two rows toward the road).
pub const FRESH: usize = 13;
const OFFER_ITEMS: [&str; 4] = ["meat", "croc_steak", "elk_jerky", "feast"];
const BLESS_MS: f64 = 60_000.0;
const GRAVE_GOLD: i64 = 40;
/// Mourners leave when the hero comes this close, and are gone past [`MOURNER_GONE`] from him.
const MOURNER_SHY: f32 = 15.0;
const MOURNER_GONE: f32 = 34.0;

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Field {
    pub pos: Vec2,
    pub yaw: f32,
}

impl Field {
    /// Field-local (x, z) → world XZ.
    pub fn at(&self, l: Vec2) -> Vec2 {
        let (s, c) = self.yaw.sin_cos();
        self.pos + Vec2::new(l.x * c + l.y * s, -l.x * s + l.y * c)
    }
}

static SITE: Mutex<Option<Field>> = Mutex::new(None);

/// The placed field (after [`plan`]).
pub fn site() -> Option<Field> {
    *SITE.lock().unwrap()
}

pub fn reset_plan() {
    *SITE.lock().unwrap() = None;
}

/// `(centre, cleared radius)` for `poi::story_clearings` (scatter keeps clear of the field).
pub fn planned_footprints() -> Vec<(Vec2, f32)> {
    site().map(|f| vec![(f.pos, FOOT + 2.0)]).unwrap_or_default()
}

/// Does a circle at `(x, z)` of radius `r` overlap the planned field?
pub fn overlaps_planned(x: f32, z: f32, r: f32) -> bool {
    site().is_some_and(|f| f.pos.distance_squared(Vec2::new(x, z)) < (FOOT + r + 0.35).powi(2))
}

// ── Layout (field-local; front = -Z toward the road / the castle) ─────────────────────

/// The old barrow group (wild_sites.glb), turned like the field.
const CORE: (Vec2, f32) = (Vec2::new(-4.4, 3.6), 0.0);
/// Old long barrows `(pos, yaw)` (og_long_barrow runs along its local X, head stone at -X).
const LONG: [(Vec2, f32); 3] = [(Vec2::new(3.4, 1.7), 0.05), (Vec2::new(3.1, 4.3), -0.04), (Vec2::new(2.6, 6.9), 0.1)];
/// Lone notched iron stones (old graves sunk flat).
const STONES: [(Vec2, f32); 5] =
    [(Vec2::new(-0.2, 1.5), 0.1), (Vec2::new(-0.5, 4.2), -0.2), (Vec2::new(-0.1, 7.1), 0.15), (Vec2::new(-7.8, -0.4), 0.3), (Vec2::new(7.6, 0.1), -0.25)];
const BOWLS: [Vec2; 4] = [Vec2::new(0.35, 1.0), Vec2::new(-1.2, 0.2), Vec2::new(4.9, 0.4), Vec2::new(-6.9, 0.3)];
/// Where the E verbs stand.
const OFFER_AT: Vec2 = Vec2::new(-0.2, 0.6);
const GOODS_AT: Vec2 = Vec2::new(-3.1, 1.2);

/// Fresh grave `k` (0..[`FRESH`]): a full row of eight nearest the old field, then a part-dug
/// second row from the middle out (the field is still being filled). Graves run along local Z
/// (yaw π/2: head toward the old field).
pub fn fresh_slot(k: usize) -> Vec2 {
    let row = k / 8;
    let col = [3usize, 4, 2, 5, 1, 6, 0, 7][k % 8];
    // A grave or two out of line, like hands dug them.
    let wob = ((k as f32 * 2.399).sin()) * 0.18;
    Vec2::new(-6.3 + col as f32 * 1.8 + wob, -1.0 - row as f32 * 2.6 + wob * 0.6)
}

fn every_piece() -> impl Iterator<Item = Vec2> {
    let mut v: Vec<Vec2> = vec![CORE.0];
    v.extend(LONG.iter().map(|l| l.0));
    v.extend(STONES.iter().map(|s| s.0));
    v.extend((0..FRESH).map(fresh_slot));
    v.into_iter()
}

// ── Plan ─────────────────────────────────────────────────────────────────────────────

fn site_ok(q: Vec2, yaw: f32) -> bool {
    let field = Field { pos: q, yaw };
    let Some(y0) = crate::worldmap::ground_at_world(q.x, q.y) else { return false };
    if q.length() < crate::worldmap::SAFE_R * crate::worldmap::MAP_SCALE + 6.0 + FOOT
        || crate::ork_fortress::blight_edge_world(q.x, q.y) > -(FOOT + 6.0)
        || crate::camps::plan().iter().any(|c| c.centre.distance(q) < 7.0 + FOOT)
        || crate::ruins::landmark_sites().iter().any(|l| l.pos.distance(q) < 14.0 + FOOT)
        || crate::poi::story_clearings().overlaps(q.x, q.y, FOOT)
        || crate::blockers::any_within(q.x, q.y, FOOT * 0.6)
    {
        return false;
    }
    // Off the road itself, but within sight of it (the orks bury beside their road).
    let ring = |r: f32, n: usize| (0..n).map(move |k| q + Vec2::from_angle(k as f32 * TAU / n as f32) * r);
    if ring(FOOT + 1.0, 16).any(|p| crate::roads::on_road(p.x, p.y)) || !ring(FOOT + 14.0, 24).any(|p| crate::roads::on_road(p.x, p.y)) {
        return false;
    }
    let (mut lo, mut hi) = (y0, y0);
    for p in every_piece().map(|l| field.at(l)).chain(ring(FOOT, 12)) {
        let Some(y) = crate::worldmap::ground_at_world(p.x, p.y) else { return false };
        lo = lo.min(y);
        hi = hi.max(y);
        let biome = crate::worldmap::tile_biome_world(p.x, p.y);
        if hi - lo > FLAT
            || !matches!(biome, Some(Biome::Swamp) | None)
            || crate::worldmap::is_pool_world(p.x, p.y)
            || crate::worldmap::is_river_world(p.x, p.y)
            || crate::roads::on_road(p.x, p.y)
            || crate::town::near_build_plot(p.x, p.y)
            || crate::castle::in_footprint(p.x, p.y)
            || crate::camps::in_clearing(p.x, p.y)
            || crate::rival::near_fort(p.x, p.y)
            || crate::ruins::near_landmark_visual_footprint(p.x, p.y)
        {
            return false;
        }
    }
    true
}

/// Build phase 4 (after `wild_sites::plan`): find the field's spot, nearest [`TARGET`] first.
pub fn plan() {
    reset_plan();
    let mut cands: Vec<Vec2> = Vec::new();
    let mut r = 0.0f32;
    while r <= SEARCH_R {
        let n = ((r * TAU / 3.0).ceil() as usize).max(1);
        cands.extend((0..n).map(|k| TARGET + Vec2::from_angle(k as f32 * TAU / n as f32 + r * 0.37) * r));
        r += 2.5;
    }
    for q in cands {
        // Face the castle: the field's front (-Z) toward the origin, a few turns either side.
        let to = (-q).normalize_or_zero();
        let base = (-to.x).atan2(-to.y);
        for dy in [0.0f32, 0.35, -0.35, 0.7, -0.7] {
            let yaw = base + dy;
            if site_ok(q, yaw) {
                crate::blockers::reserve_visual(q.x, q.y, FOOT);
                info!("ork_graveyard: planned at {:.1},{:.1} yaw {:.2}", q.x, q.y, yaw);
                *SITE.lock().unwrap() = Some(Field { pos: q, yaw });
                return;
            }
        }
    }
    warn!("ork_graveyard: no spot for the Field of the Answered");
}

// ── Spawn ────────────────────────────────────────────────────────────────────────────

#[derive(Component)]
struct FieldRoot;
#[derive(Component)]
struct OfferSpot;
#[derive(Component)]
struct GoodsSpot;
#[derive(Component)]
struct Mourner {
    /// Grave it tends (world XZ) and the next one.
    tend: [Vec2; 2],
    leg: usize,
    pause: f32,
    fleeing: Option<Vec2>,
}

fn ground(p: Vec2) -> f32 {
    crate::worldmap::ground_at_world(p.x, p.y).unwrap_or(0.0)
}

/// A piece's seat: the lowest ground under its footprint, sunk a touch (no floating downhill edge).
fn seat(p: Vec2, r: f32) -> f32 {
    (0..8)
        .map(|k| ground(p + Vec2::from_angle(k as f32 * TAU / 8.0) * r))
        .fold(ground(p), f32::min)
        - 0.04
}

fn range() -> VisibilityRange {
    VisibilityRange { start_margin: 0.0..0.0, end_margin: 110.0..130.0, use_aabb: true }
}

/// Build phase 32: plant the field (old barrows, iron stones, the fresh rows) + the verb spots.
pub fn populate(commands: &mut Commands) {
    let Some(field) = site() else { return };
    let Some(kit) = crate::realforest::get().filter(|k| k.has("og_long_barrow")) else {
        warn!("ork_graveyard: swamp_folk.glb not in the kit \u{2014} no Field of the Answered");
        return;
    };
    let y = ground(field.pos);
    let root = commands
        .spawn((Transform::from_xyz(field.pos.x, y, field.pos.y), Visibility::default(), FieldRoot, BiomeEntity))
        .id();
    crate::landmarks::attach_story(commands, root, NAME, LORE);
    let mut place = |name: &str, l: Vec2, yaw: f32, r: f32, solid: Option<(f32, f32)>| {
        let p = field.at(l);
        let tf = Transform::from_xyz(p.x, seat(p, r), p.y).with_rotation(Quat::from_rotation_y(field.yaw + yaw));
        if let Some(e) = kit.spawn_static_with(commands, name, tf, range()) {
            commands.entity(e).insert(BiomeEntity);
        }
        if let Some((hw, hd)) = solid {
            crate::blockers::add_obb(p.x, p.y, hw, hd, field.yaw + yaw);
        }
    };
    if kit.has("site_ork_barrows") {
        place("site_ork_barrows", CORE.0, CORE.1, 3.0, None);
        // The old group's masses (wild_sites' solids for it), turned into place.
        for (x, z, hw, hd) in [(0.0, 0.3, 2.4, 1.3), (-2.7, -1.4, 0.25, 0.25)] {
            let p = field.at(CORE.0 + Vec2::new(x, z));
            crate::blockers::add_obb(p.x, p.y, hw, hd, field.yaw + CORE.1);
        }
    }
    for &(l, yaw) in &LONG {
        place("og_long_barrow", l, yaw, 1.5, Some((1.7, 0.8)));
    }
    for &(l, yaw) in &STONES {
        place("og_iron_stone", l, yaw, 0.4, Some((0.3, 0.2)));
    }
    for k in 0..FRESH {
        let model = if (k * 7 + 3) % 3 == 0 { "og_fresh_mound_b" } else { "og_fresh_mound_a" };
        let jitter = ((k as f32 * 2.399).sin()) * 0.08;
        place(model, fresh_slot(k), FRAC_PI_2 + jitter, 0.9, None);
    }
    for (k, &l) in BOWLS.iter().enumerate() {
        place("og_fish_bowl", l, k as f32 * 1.7, 0.15, None);
    }
    crate::blockers::reserve_visual(field.pos.x, field.pos.y, FOOT);
    for (at, marker) in [(OFFER_AT, 0), (GOODS_AT, 1)] {
        let p = field.at(at);
        let mut e = commands.spawn((Transform::from_xyz(p.x, ground(p), p.y), BiomeEntity));
        if marker == 0 {
            e.insert((OfferSpot, Interactable::new("Leave an offering", 1.9)));
        } else {
            e.insert((GoodsSpot, Interactable::new("Take grave goods", 1.7)));
        }
    }
    info!("ork_graveyard: the Field of the Answered at {:.1},{:.1},{:.1}", field.pos.x, y, field.pos.y);
}

// ── Live systems ─────────────────────────────────────────────────────────────────────

pub struct OrkGraveyardPlugin;

impl Plugin for OrkGraveyardPlugin {
    fn build(&self, app: &mut App) {
        app.add_sim_systems((graveyard_verbs, mourners).run_if(crate::rts::in_campaign));
    }
}

/// The two E verbs at the graves.
#[allow(clippy::too_many_arguments)]
fn graveyard_verbs(
    mut commands: Commands,
    mut ev: MessageReader<Interacted>,
    time: Res<Time>,
    siege: Res<Siege>,
    mut flags: ResMut<WorldFlags>,
    mut night_mods: ResMut<crate::siege::NightMods>,
    mut player: ResMut<crate::player::PlayerRes>,
    mut inv: ResMut<crate::inventory::Inventory>,
    mut toasts: ResMut<crate::inventory::Toasts>,
    mut buffs: ResMut<crate::inventory::Buffs>,
    mut floats: ResMut<FloatQueue>,
    mut cues: MessageWriter<crate::audio::AudioCue>,
    offer: Query<&GlobalTransform, With<OfferSpot>>,
    goods: Query<(Entity, &GlobalTransform), With<GoodsSpot>>,
    mourners: Query<Entity, With<Mourner>>,
) {
    let now = time.elapsed_secs();
    // A desecrated field keeps no grave goods to take.
    if flags.is("graveyard_desecrated") {
        for (e, _) in &goods {
            commands.entity(e).try_remove::<Interactable>();
        }
    }
    for Interacted(e) in ev.read() {
        if let Ok(gt) = offer.get(*e) {
            let head = gt.translation() + Vec3::Y * 1.6;
            let day = siege.wave_index as i64 + 10;
            if flags.get("graveyard_offered_day") == day {
                floats.0.push(FloatReq { world: head, text: "The bowls are full.".into(), color: Color::srgb(0.7, 0.7, 0.75), scale: 0.9 });
                cues.write(crate::audio::AudioCue::UiSelect);
                continue;
            }
            let Some(item) = OFFER_ITEMS.iter().find(|id| inv.0.count_item(id) > 0) else {
                floats.0.push(FloatReq { world: head, text: "You have no meat or fish.".into(), color: Color::srgb(0.7, 0.7, 0.75), scale: 0.9 });
                cues.write(crate::audio::AudioCue::UiSelect);
                continue;
            };
            inv.0.consume_item(item, 1);
            flags.set("graveyard_offered_day", day);
            buffs.0.apply_buff(BuffKind::Resist, BLESS_MS, 0.6, now as f64);
            floats.0.push(FloatReq { world: head, text: format!("{} — {}", NAME, BuffKind::Resist.label()), color: Color::srgb(0.7, 1.0, 0.85), scale: 1.1 });
            cues.write(crate::audio::AudioCue::Forage);
        } else if let Ok((ge, gt)) = goods.get(*e) {
            if flags.is("graveyard_desecrated") {
                continue;
            }
            flags.set("graveyard_desecrated", 1);
            night_mods.add(2, 2);
            player.0.add_gold(GRAVE_GOLD);
            crate::inventory::try_grant(&mut inv.0, &mut toasts.0, "axe", 1, now as f64);
            floats.0.push(FloatReq { world: gt.translation() + Vec3::Y * 1.5, text: format!("+{GRAVE_GOLD} gold"), color: crate::combat_fx::col_kill(), scale: 1.1 });
            cues.write(crate::audio::AudioCue::Gold);
            commands.entity(ge).try_remove::<Interactable>();
            // The mourners see it done and go; they don't come back.
            for m in &mourners {
                if let Ok(mut ec) = commands.get_entity(m) {
                    ec.try_insert(Fled);
                }
            }
        }
    }
}

/// A mourner already sent away (flees, then despawns).
#[derive(Component)]
struct Fled;

/// By day 1–2 old orks tend the graves; they leave when the hero nears and never return once the
/// field is robbed. Night (or a robbed field) clears them.
#[allow(clippy::too_many_arguments, clippy::type_complexity)]
fn mourners(
    mut commands: Commands,
    time: Res<Time>,
    siege: Res<Siege>,
    flags: Res<WorldFlags>,
    hero: Res<crate::player::HeroState>,
    armory: Option<Res<crate::siege::InvaderArmory>>,
    roots: Query<(), With<FieldRoot>>,
    mut q: Query<(Entity, &mut Mourner, &mut Transform, Has<Fled>)>,
    mut gone_day: Local<i32>,
) {
    let Some(field) = site() else { return };
    let dt = time.delta_secs();
    let day = siege.wave_index;
    let present = q.iter().count();
    let wanted = siege.phase == GamePhase::Prep && !flags.is("graveyard_desecrated") && !roots.is_empty();
    if !wanted {
        for (e, ..) in &q {
            commands.entity(e).try_despawn();
        }
        return;
    }
    // Spawn the day's mourners once (not again the same day after they left).
    if present == 0 && *gone_day != day + 1000 && hero.pos.distance(field.pos) > MOURNER_SHY + 8.0 {
        if let Some(arm) = armory.as_deref() {
            for (i, variant) in [crate::orks::OrkVariant::Shaman, crate::orks::OrkVariant::Grunt].into_iter().enumerate() {
                let a = field.at(fresh_slot(i * 3) + Vec2::new(0.9, 0.0));
                let b = field.at(if i == 0 { OFFER_AT } else { CORE.0 + Vec2::new(0.0, -3.4) });
                let face = field.yaw + PI;
                let e = arm.0.spawn_prop(&mut commands, variant, crate::orks::Faction::Red, Vec3::new(a.x, ground(a), a.y), face, 0.92);
                commands.entity(e).insert((Mourner { tend: [a, b], leg: 0, pause: 4.0 + 3.0 * i as f32, fleeing: None }, BiomeEntity));
            }
            *gone_day = day + 1000;
        }
        return;
    }
    for (e, mut m, mut tf, fled) in &mut q {
        let pos = Vec2::new(tf.translation.x, tf.translation.z);
        if m.fleeing.is_none() && (fled || pos.distance(hero.pos) < MOURNER_SHY) {
            // Away from the hero, off past the field's back.
            let away = (pos - hero.pos).normalize_or(Vec2::X);
            m.fleeing = Some(pos + away * 45.0);
        }
        let (target, speed) = match m.fleeing {
            Some(t) => (t, 3.2),
            None => {
                if m.pause > 0.0 {
                    m.pause -= dt;
                    (pos, 0.0)
                } else {
                    (m.tend[m.leg], 0.9)
                }
            }
        };
        let d = target - pos;
        if speed > 0.0 && d.length() > 0.2 {
            let step = d.normalize() * (speed * dt).min(d.length());
            let np = pos + step;
            if crate::worldmap::is_pool_world(np.x, np.y) && m.fleeing.is_some() {
                // Skirt the water: turn a quarter and keep going.
                m.fleeing = Some(pos + Vec2::new(-d.y, d.x).normalize_or(Vec2::X) * 40.0);
            }
            tf.translation = Vec3::new(np.x, ground(np), np.y);
            let want = (-step.x).atan2(-step.y) + PI;
            tf.rotation = tf.rotation.slerp(Quat::from_rotation_y(want), (dt * 5.0).min(1.0));
        } else if m.fleeing.is_none() && speed > 0.0 {
            // Arrived: stand at the grave a while, then the other one.
            m.leg = 1 - m.leg;
            m.pause = 9.0;
        }
        if m.fleeing.is_some() && pos.distance(hero.pos) > MOURNER_GONE {
            commands.entity(e).try_despawn();
        }
    }
}

/// Screenshot cameras (`FOREST_SHOT_STORIES=wild`, via `wild_sites::shot_cams`): the field from the
/// road over the fresh rows, high over the whole field, and the offering bowl close.
pub fn shot_cams() -> Vec<(String, Transform)> {
    let Some(f) = site() else { return Vec::new() };
    let g = |p: Vec2| crate::worldmap::ground_at_world(p.x, p.y).unwrap_or(0.0).max(crate::worldmap::SEA_Y);
    let cam = |name: &str, eye: Vec2, lift: f32, aim: Vec2, aim_lift: f32| {
        let (eye, aim) = (f.at(eye), f.at(aim));
        let e = Vec3::new(eye.x, g(eye) + lift, eye.y);
        let a = Vec3::new(aim.x, g(aim) + aim_lift, aim.y);
        info!("graveyard cam {name}: {:.1},{:.1},{:.1} -> {:.1},{:.1},{:.1}", e.x, e.y, e.z, a.x, a.y, a.z);
        (name.to_string(), Transform::from_translation(e).looking_at(a, Vec3::Y))
    };
    vec![
        cam("graveyard_road", Vec2::new(-4.0, -12.5), 3.2, Vec2::new(-0.5, 1.5), 0.4),
        cam("graveyard_high", Vec2::new(11.0, -11.0), 9.0, Vec2::new(-1.0, 2.0), 0.0),
        cam("graveyard_offer", Vec2::new(1.4, -2.2), 1.5, OFFER_AT, 0.2),
    ]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fresh_rows_fit_without_overlap() {
        let slots: Vec<Vec2> = (0..FRESH).map(fresh_slot).collect();
        for (i, a) in slots.iter().enumerate() {
            assert!(a.length() < FOOT, "slot {i} outside the field");
            for b in &slots[i + 1..] {
                assert!(a.distance(*b) > 1.5, "fresh graves overlap");
            }
        }
    }

    #[test]
    fn field_plans_near_the_swamp_rim() {
        let _g = crate::blockers::TEST_LOCK.lock().unwrap();
        crate::blockers::reset();
        crate::poi::plan_clearings();
        crate::stories_warm::plan();
        crate::vignettes::plan();
        crate::wayside::plan();
        crate::stories_cold::plan();
        crate::sites_warm::plan();
        crate::wild_sites::plan();
        plan();
        let f = site().expect("the field must find a spot");
        eprintln!("field at {:.1},{:.1} yaw {:.2}", f.pos.x, f.pos.y, f.yaw);
        assert!(f.pos.distance(TARGET) <= SEARCH_R + 0.1);
        assert!(!crate::wild_sites::overlaps_planned(f.pos.x, f.pos.y, FOOT));
        reset_plan();
        crate::wild_sites::reset_plan();
        crate::sites_warm::reset_plan();
        crate::stories_cold::reset_plan();
        crate::wayside::reset_plan();
        crate::vignettes::reset_plan();
        crate::stories_warm::reset_plan();
        crate::poi::reset_plan();
        crate::blockers::reset();
    }
}
