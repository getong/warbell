//! **Orks between the camps** (spec `2026-10-13-zywa-wyspa-design.md` §2 E, items 17 + 19):
//!
//! - **The Unanswering** — a lone ork in a rocky niche by the lake under the falls, sitting by a
//!   fire that is never lit, his own gong hammer snapped and laid down beside him. He never fights.
//!   Offer him meat (E) and he scratches a sign in the dirt with a stick; the compass marks the
//!   camp that stages the coming night (`camps::raid_target`) with a red `!` for that day.
//! - **The war trail** — skull posts daubed with ochre stand along the way from the Hold to our
//!   walls: you can read where the night comes from.
//! - **Captive escort** — after a night in which the horde reached the houses, a war party halts
//!   on the trail next day with two bound villagers at a post, taking them to the Hold. Kill the
//!   three escorts and cut the bonds (E): the villagers walk home (+population, the
//!   `villagers::release_captives` path). Left alone, they are gone by nightfall.
//!
//! Models: `tools/blender_forest/ork_folk.py` (exported into `ork_camps.glb`). All player-facing
//! state lives in `WorldFlags` (`outcast_fed_day`, `escort_due`, `escort_freed_day`).

use std::sync::Mutex;

use bevy::camera::visibility::VisibilityRange;
use bevy::prelude::*;

use crate::biome::{Biome, BiomeEntity};
use crate::game_state::SimAppExt;
use crate::interaction::{Interactable, Interacted};
use crate::orks::{self, Faction, OrkVariant};
use crate::savegame::WorldFlags;
use crate::worldmap;

/// Where the spec puts the outcast (rocky niche over the lake by the falls).
const OUTCAST_TARGET: Vec2 = Vec2::new(110.0, 90.0);
const OUTCAST_FOOT: f32 = 3.0;
/// War-trail posts: spacing along the trail and the castle-side start of it.
const POST_STEP: f32 = 30.0;
const TRAIL_START: Vec2 = Vec2::new(0.0, 58.0);
/// The escort halts at this post (index along the trail from the walls).
const ESCORT_POST: usize = 1;
const ESCORT_CAPTIVES: u32 = 2;

pub struct WarPartyPlugin;

impl Plugin for WarPartyPlugin {
    fn build(&self, app: &mut App) {
        app.add_sim_systems(
            (outcast_gift, outcast_state, watch_houses, escort_spawn, escort_free, escort_leaves)
                .run_if(crate::rts::in_campaign)
                .run_if(|ready: Res<crate::biome::WorldReady>| ready.0),
        );
    }
}

// ── Plan ─────────────────────────────────────────────────────────────────────────────

/// The outcast's niche `(centre, yaw)`.
static OUTCAST: Mutex<Option<(Vec2, f32)>> = Mutex::new(None);
/// The war-trail posts as built (the escort halts at one of them).
static POSTS: Mutex<Vec<Vec2>> = Mutex::new(Vec::new());

/// Plan the outcast's niche (world-build phase 4, after the other story planners): the nearest
/// free, level, off-road spot to [`OUTCAST_TARGET`] with water in view, facing it.
pub fn plan() {
    let mut best: Option<(f32, Vec2, f32)> = None;
    let mut z = OUTCAST_TARGET.y - 60.0;
    while z <= OUTCAST_TARGET.y + 60.0 {
        let mut x = OUTCAST_TARGET.x - 60.0;
        while x <= OUTCAST_TARGET.x + 60.0 {
            let p = Vec2::new(x, z);
            let mut score = p.distance(OUTCAST_TARGET);
            if best.is_none_or(|b| score < b.0 + 12.0) && site_ok(p) {
                // Prefer a spot looking onto water (the lake under the falls).
                let water = (0..12).map(|k| k as f32 / 12.0 * std::f32::consts::TAU).find(|a| {
                    let q = p + Vec2::new(a.sin(), a.cos()) * 9.0;
                    worldmap::is_pool_world(q.x, q.y) || worldmap::is_river_world(q.x, q.y)
                });
                if water.is_none() {
                    score += 12.0;
                }
                if best.is_none_or(|b| score < b.0) {
                    best = Some((score, p, water.unwrap_or(0.0)));
                }
            }
            x += 2.0;
        }
        z += 2.0;
    }
    let site = best.map(|(_, p, yaw)| (p, yaw));
    if let Some((p, _)) = site {
        info!("war_party: the Unanswering at {:.1},{:.1}", p.x, p.y);
        crate::blockers::reserve_visual(p.x, p.y, OUTCAST_FOOT);
    }
    *OUTCAST.lock().unwrap() = site;
}

fn site_ok(p: Vec2) -> bool {
    let near_rock = worldmap::biome_at_world(p.x, p.y) == Some(Biome::Rocky)
        || worldmap::biome_at_world(p.x, p.y + 8.0) == Some(Biome::Rocky)
        || worldmap::biome_at_world(p.x + 8.0, p.y) == Some(Biome::Rocky);
    near_rock
        && crate::poi::site_ok(p.x, p.y, OUTCAST_FOOT)
        && !crate::blockers::any_visual_within(p.x, p.y, OUTCAST_FOOT + 0.2)
        && !crate::poi::overlaps_planned_clearing(p.x, p.y, OUTCAST_FOOT)
        && crate::poi::clear_of_settlements(p, OUTCAST_FOOT)
}

/// Planned footprints (scatter keep-out, `poi::story_clearings`).
pub fn planned_footprints() -> Vec<(Vec2, f32)> {
    OUTCAST.lock().unwrap().iter().map(|(p, _)| (*p, OUTCAST_FOOT)).collect()
}

#[allow(dead_code)] // test-side reset (density_report)
pub fn reset_plan() {
    *OUTCAST.lock().unwrap() = None;
}

/// The war trail: posts every [`POST_STEP`] from under our walls to the Hold's gate, each set a
/// few steps off the line onto free ground (never on the road itself).
pub fn trail_posts() -> Vec<Vec2> {
    let end = crate::ork_fortress::GATE - Vec2::Y * 14.0;
    let len = TRAIL_START.distance(end);
    let dir = (end - TRAIL_START).normalize_or(Vec2::Y);
    let side = Vec2::new(-dir.y, dir.x);
    let mut out = Vec::new();
    let mut t = POST_STEP * 0.5;
    let mut k = 0;
    while t < len {
        let base = TRAIL_START + dir * t;
        let sgn = if k % 2 == 0 { 1.0 } else { -1.0 };
        if let Some(p) = [3.5f32, 5.0, 6.5, 8.0, 10.0]
            .iter()
            .flat_map(|o| [base + side * sgn * *o, base - side * sgn * *o])
            .find(|p| crate::poi::site_ok(p.x, p.y, 0.6) && !crate::poi::overlaps_planned_clearing(p.x, p.y, 0.6))
        {
            out.push(p);
        }
        t += POST_STEP;
        k += 1;
    }
    out
}

// ── Build ────────────────────────────────────────────────────────────────────────────

#[derive(Component)]
struct Outcast;
#[derive(Component)]
struct OutcastSign;
/// The bound villagers of the day's escort (+ the post they're tied at).
#[derive(Component)]
struct EscortCaptive;
#[derive(Component)]
struct EscortBonds;

/// Called from `camps::build` (the camps' armory is alive there).
pub fn build(commands: &mut Commands, armory: &orks::Armory, range: VisibilityRange) {
    let Some(kit) = crate::realforest::get() else { return };
    let posts = trail_posts();
    *POSTS.lock().unwrap() = posts.clone();
    for (k, p) in posts.into_iter().enumerate() {
        let y = worldmap::ground_at_world(p.x, p.y).unwrap_or(0.0);
        let tf = Transform::from_xyz(p.x, y, p.y).with_rotation(Quat::from_rotation_y(k as f32 * 2.4));
        if let Some(e) = kit.spawn_static_with(commands, "ork_war_post", tf, range.clone()) {
            commands.entity(e).insert(BiomeEntity);
            crate::blockers::add_obb(p.x, p.y, 0.2, 0.2, 0.0);
        }
    }
    let Some((p, yaw)) = *OUTCAST.lock().unwrap() else { return };
    let y = worldmap::ground_at_world(p.x, p.y).unwrap_or(0.0);
    let rot = Quat::from_rotation_y(yaw);
    let at = |x: f32, yy: f32, z: f32| Vec3::new(p.x, y, p.y) + rot * Vec3::new(x, yy, z);
    if let Some(e) = kit.spawn_static_with(commands, "ork_outcast_niche", Transform::from_xyz(p.x, y, p.y).with_rotation(rot), range.clone()) {
        commands.entity(e).insert(BiomeEntity);
    }
    for (x, z, hw, hd) in [(-1.6f32, -1.7f32, 0.9f32, 0.7f32), (0.2, -2.1, 1.2, 0.8), (1.8, -1.5, 0.7, 0.6), (-2.4, -0.4, 0.5, 0.5)] {
        let w = at(x, 0.0, z);
        crate::blockers::add_obb(w.x, w.z, hw, hd, yaw);
    }
    // He sits on the low boulder at the end of his bedroll, facing the cold fire (no brain, no
    // Health: he cannot be fought — he would only shield his head).
    let seat = at(-2.25, 0.4, -0.3);
    let fire = at(0.3, 0.0, 0.5);
    let face = (fire.x - seat.x).atan2(fire.z - seat.z);
    let body = armory.spawn_seated(commands, OrkVariant::Grunt, Faction::Blue, seat, face);
    commands.entity(body).insert(Outcast);
    commands.spawn((Transform::from_translation(at(-1.4, 0.5, 0.2)), Interactable::new("Offer meat", 2.8), Outcast, BiomeEntity));
    if let Some(e) = kit.spawn_static_with(commands, "ork_outcast_sign", Transform::from_translation(at(1.1, 0.0, -0.2)).with_rotation(rot), range) {
        commands.entity(e).insert((OutcastSign, Visibility::Hidden, BiomeEntity));
    }
}

fn coming_night(siege: &crate::siege::Siege) -> i64 {
    match siege.phase {
        crate::siege::GamePhase::Prep => siege.wave_index + 1,
        _ => siege.wave_index,
    }
    .max(0) as i64
}

fn fed_today(flags: &WorldFlags, siege: &crate::siege::Siege) -> bool {
    flags.0.contains_key("outcast_fed_day") && flags.get("outcast_fed_day") == coming_night(siege)
}

/// Meat for the Unanswering: he scratches tonight's staging camp in the dirt.
#[allow(clippy::too_many_arguments)]
fn outcast_gift(
    mut ev: MessageReader<Interacted>,
    anchors: Query<(), (With<Outcast>, With<Interactable>)>,
    mut inv: ResMut<crate::inventory::Inventory>,
    mut flags: ResMut<WorldFlags>,
    siege: Res<crate::siege::Siege>,
    mut notice: ResMut<crate::ui::notice::Notice>,
    time: Res<Time>,
) {
    for Interacted(e) in ev.read() {
        if !anchors.contains(*e) {
            continue;
        }
        if fed_today(&flags, &siege) {
            notice.push("He has eaten. He does not look up.", time.elapsed_secs_f64());
        } else if inv.0.consume_item("meat", 1) {
            flags.set("outcast_fed_day", coming_night(&siege));
            flags.set("outcast_alive", 1);
            notice.push("He eats, then scratches something in the dirt with a stick.", time.elapsed_secs_f64());
        } else {
            notice.push("He glances at your empty hands.", time.elapsed_secs_f64());
        }
    }
}

/// The sign shows (and the compass marks the staging camp) for the day he was fed.
fn outcast_state(
    flags: Res<WorldFlags>,
    siege: Res<crate::siege::Siege>,
    mut signs: Query<&mut Visibility, With<OutcastSign>>,
    mut hints: ResMut<crate::compass::CompassHints>,
) {
    let fed = fed_today(&flags, &siege);
    for mut v in &mut signs {
        let want = if fed { Visibility::Inherited } else { Visibility::Hidden };
        if *v != want {
            *v = want;
        }
    }
    let mark = fed
        .then(|| crate::camps::raid_target(coming_night(&siege) as i32).and_then(crate::camps::camp_centre))
        .flatten();
    if hints.staging != mark {
        hints.staging = mark;
    }
}

/// Night: if the horde gets in among the houses, an escort will take captives tomorrow.
fn watch_houses(
    siege: Res<crate::siege::Siege>,
    invaders: Query<&orks::Ork, (With<orks::WaveInvader>, Without<crate::dying::Dying>)>,
    mut flags: ResMut<WorldFlags>,
) {
    if siege.phase == crate::siege::GamePhase::Prep {
        return;
    }
    let tomorrow = siege.wave_index as i64 + 1;
    if flags.get("escort_due") == tomorrow && flags.0.contains_key("escort_due") {
        return;
    }
    if invaders.iter().any(|o| crate::town::near_build_plot(o.pos.x, o.pos.y)) {
        flags.set("escort_due", tomorrow);
    }
}

/// Dawn after such a night: the escort halts at a trail post with two bound villagers.
#[allow(clippy::too_many_arguments)]
fn escort_spawn(
    siege: Res<crate::siege::Siege>,
    flags: Res<WorldFlags>,
    wb: Option<Res<crate::camps::CampWarbands>>,
    present: Query<(), With<EscortCaptive>>,
    mut meshes: ResMut<Assets<Mesh>>,
    mut creature_mats: ResMut<Assets<crate::creature::CreatureMaterial>>,
    mut done_day: Local<i64>,
    mut commands: Commands,
) {
    if siege.phase != crate::siege::GamePhase::Prep || !present.is_empty() {
        return;
    }
    let day = coming_night(&siege);
    let due = flags.0.contains_key("escort_due") && flags.get("escort_due") == day;
    let freed = flags.0.contains_key("escort_freed_day") && flags.get("escort_freed_day") == day;
    if !due || freed || *done_day == day {
        return;
    }
    let Some(wb) = wb else { return };
    let Some(post) = POSTS.lock().unwrap().get(ESCORT_POST).copied() else { return };
    *done_day = day;
    let toward_hold = (crate::ork_fortress::GATE - post).normalize_or(Vec2::Y);
    let y = worldmap::ground_at_world(post.x, post.y).unwrap_or(0.0);
    for k in 0..ESCORT_CAPTIVES {
        let side = Vec2::new(-toward_hold.y, toward_hold.x) * (k as f32 - 0.5) * 0.9;
        let s = post + side - toward_hold * 0.5;
        let seat = Vec3::new(s.x, y - 0.1, s.y);
        let yaw = (-toward_hold.x).atan2(-toward_hold.y);
        let berth = crate::captives::Berth { seat, seat_yaw: yaw, bars: seat, bars_yaw: yaw, cage: post, sit_h: crate::captives::SIT_H_FLAT_STRAW };
        let e = crate::villagers::spawn_cage_captive(&mut commands, &mut meshes, &mut creature_mats, berth, crate::camps::CageKey::Decor, 0x5ca7 + k + day as u32 * 7);
        commands.entity(e).insert((EscortCaptive, BiomeEntity));
    }
    // The escort: three orks resting round the post (home-anchored there, so they guard it).
    for (k, variant) in [OrkVariant::Grunt, OrkVariant::Berserker, OrkVariant::Scout].into_iter().enumerate() {
        let a = k as f32 * 2.1 + 0.4;
        let pos = post + Vec2::new(a.sin(), a.cos()) * 3.2;
        wb.armory.spawn(&mut commands, variant, Faction::Red, post, pos, 0xe5c0 + k as u32 + day as u32 * 13);
    }
    commands.spawn((Transform::from_xyz(post.x, y + 0.6, post.y), EscortBonds, BiomeEntity));
    info!("war_party: escort halted at {:.1},{:.1}", post.x, post.y);
}

/// The escort dead, the bonds can be cut: the villagers stand and walk home.
#[allow(clippy::too_many_arguments)]
fn escort_free(
    mut ev: MessageReader<Interacted>,
    bonds: Query<(Entity, &Transform, Has<Interactable>), With<EscortBonds>>,
    orks_q: Query<&orks::Ork, (Without<orks::WaveInvader>, Without<crate::dying::Dying>)>,
    captives: Query<(Entity, &crate::villagers::Captive), With<EscortCaptive>>,
    mut town: ResMut<crate::town::TownRes>,
    mut flags: ResMut<WorldFlags>,
    siege: Res<crate::siege::Siege>,
    mut notice: ResMut<crate::ui::notice::Notice>,
    time: Res<Time>,
    mut commands: Commands,
) {
    let Ok((be, btf, offered)) = bonds.single() else { return };
    let post = btf.translation.xz();
    let guarded = orks_q.iter().any(|o| o.home().distance(post) < 1.0);
    if !guarded && !offered && !captives.is_empty() {
        commands.entity(be).insert(Interactable::new("Cut their bonds", 3.0));
    }
    for Interacted(e) in ev.read() {
        if *e != be || guarded {
            continue;
        }
        let freed: Vec<(Entity, u32)> = captives.iter().map(|(e, c)| (e, c.seed)).collect();
        let n = freed.len() as u32;
        let toward_home = (-post).normalize_or(Vec2::NEG_Y);
        let tf = Transform::from_translation(btf.translation).with_rotation(Quat::from_rotation_y((-toward_home.y).atan2(toward_home.x)));
        crate::villagers::release_captives(&mut commands, time.elapsed_secs(), &tf, &freed);
        for (e, _) in &freed {
            commands.entity(*e).remove::<EscortCaptive>();
        }
        town.0.population += n;
        flags.set("escort_freed_day", coming_night(&siege));
        notice.push(format!("The villagers are free  +{n} townsfolk"), time.elapsed_secs_f64());
        commands.entity(be).try_despawn();
    }
}

/// Nightfall: an escort left alone has reached the Hold — the captives are gone.
fn escort_leaves(
    siege: Res<crate::siege::Siege>,
    captives: Query<Entity, With<EscortCaptive>>,
    bonds: Query<(Entity, &Transform), With<EscortBonds>>,
    orks_q: Query<(Entity, &orks::Ork), Without<orks::WaveInvader>>,
    mut commands: Commands,
) {
    if siege.phase == crate::siege::GamePhase::Prep {
        return;
    }
    for (be, btf) in &bonds {
        let post = btf.translation.xz();
        for (e, o) in &orks_q {
            if o.home().distance(post) < 1.0 {
                commands.entity(e).try_despawn();
            }
        }
        commands.entity(be).try_despawn();
    }
    for e in &captives {
        commands.entity(e).try_despawn();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The outcast finds a niche near the spec spot, and the war trail gets its posts.
    #[test]
    fn outcast_and_trail_are_placed() {
        let _g = crate::blockers::TEST_LOCK.lock().unwrap();
        crate::blockers::reset();
        crate::camps::plan();
        crate::poi::plan_clearings();
        crate::stories_warm::plan();
        crate::vignettes::plan();
        crate::wayside::plan();
        crate::stories_cold::plan();
        crate::sites_warm::plan();
        crate::wild_sites::plan();
        plan();
        let site = OUTCAST.lock().unwrap().expect("the outcast has a niche");
        eprintln!("outcast at {:?}", site.0);
        assert!(site.0.distance(OUTCAST_TARGET) < 70.0, "outcast far from the falls: {:?}", site.0);
        let posts = trail_posts();
        eprintln!("war trail posts {posts:?}");
        assert!(posts.len() >= 3, "the war trail needs posts");
        reset_plan();
        crate::blockers::reset();
    }
}
