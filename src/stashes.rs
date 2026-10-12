//! **Biome stashes** (spec 2026-10-13 "Żywa wyspa" §2 F, item 20) — ten small hidden caches, two
//! per biome and every one its own model (`stashes.glb`, `tools/blender_forest/stashes.py`): a
//! hollow windfall and a poacher's snare line in the forest, a buried jar and a lost camel pack in
//! the dunes, a niche cairn and a miner's cache in the rocks, a frozen ski bundle and a ship's crate
//! in the snow, a drowned crate and a fisher's creel in the swamp. They lean toward the spec's
//! empty areas (SE coast, NE dunes, N coast). Walking up is a minor discovery
//! (`landmarks::attach_story`); **E "Search"** pays a chest-style haul (gold + provisions, tier by
//! distance from the keep like `chest.rs`). Looted stashes ride the save as one `WorldFlags`
//! bitmask (`stash_looted`).
//!
//! Also planned here: the **wolverine dens** (two, in the snow) — the burrow `oddities.rs`' thieves
//! flee to. E "Search the den" hands back whatever they dragged in (`oddities::DenHoards`); the
//! first search also turns up the castaways' ship's biscuit (`den_searched` bitmask).
//!
//! Planned at build phase 4 (after `wild_sites`), folded into `poi::story_clearings` so the scatter
//! keeps clear, spawned at phase 32. `FOREST_STASHLINE="x,z"` parks every model in a row (+X, 4.5u
//! apart) for close-ups.

use std::f32::consts::TAU;
use std::sync::Mutex;

use bevy::camera::visibility::VisibilityRange;
use bevy::prelude::*;

use crate::biome::{Biome, BiomeEntity};
use crate::game_state::SimAppExt;
use crate::interaction::{Interactable, Interacted};
use crate::savegame::WorldFlags;

struct Kind {
    model: &'static str,
    biome: Biome,
    foot: f32,
    name: &'static str,
    lore: &'static str,
    /// Preferred box (spec empty area), tried first.
    prefer: Option<[f32; 4]>,
    /// Wants a pool within reach (the drowned crate).
    wet: bool,
}

const AREA3: [f32; 4] = [40.0, 110.0, 120.0, 200.0];
const AREA4: [f32; 4] = [150.0, 250.0, -190.0, -110.0];
const AREA5: [f32; 4] = [-70.0, 30.0, -210.0, -175.0];

const KINDS: [Kind; 10] = [
    Kind { model: "stash_hollow_log", biome: Biome::Forest, foot: 1.9, name: "The Hollow Windfall", prefer: None, wet: false,
        lore: "Someone pushed a bundle deep into the rotten trunk and never came back for it." },
    Kind { model: "stash_snare_line", biome: Biome::Forest, foot: 2.1, name: "The Poacher's Line", prefer: None, wet: false,
        lore: "Snares on the deer run, skins on a forked stake. The poacher meant to come back." },
    Kind { model: "stash_buried_jar", biome: Biome::Desert, foot: 1.2, name: "The Buried Jar", prefer: Some(AREA4), wet: false,
        lore: "A marker cairn and a stoppered jar, buried to the shoulder against the wind." },
    Kind { model: "stash_camel_pack", biome: Biome::Desert, foot: 1.5, name: "The Lost Pack", prefer: Some(AREA4), wet: false,
        lore: "The dunes took the camel. Its saddle-bags are still here." },
    Kind { model: "stash_niche_cairn", biome: Biome::Rocky, foot: 1.0, name: "The Niche Cairn", prefer: Some(AREA3), wet: false,
        lore: "A traveller's cairn with a hollow at its foot, and something wrapped inside." },
    Kind { model: "stash_miner_sack", biome: Biome::Rocky, foot: 1.3, name: "The Miner's Cache", prefer: Some(AREA3), wet: false,
        lore: "A sack and a pick, pushed under the slab out of the rain." },
    Kind { model: "stash_frozen_bundle", biome: Biome::Snow, foot: 1.1, name: "The Frozen Bundle", prefer: Some(AREA5), wet: false,
        lore: "A bundle lashed to short skis, half drifted over. The skier is nowhere." },
    Kind { model: "stash_boat_crate", biome: Biome::Snow, foot: 1.5, name: "The Ship's Crate", prefer: Some(AREA5), wet: false,
        lore: "A ship's crate with rope handles, dragged up from the shore." },
    Kind { model: "stash_sunken_crate", biome: Biome::Swamp, foot: 1.5, name: "The Drowned Crate", prefer: None, wet: true,
        lore: "A crate lashed to a pile, left for the black water to keep." },
    Kind { model: "stash_fish_basket", biome: Biome::Swamp, foot: 1.7, name: "The Fisher's Creel", prefer: Some(AREA3), wet: false,
        lore: "A creel and a willow trap by the stake. The fisher left before the catch." },
];

const DEN_MODEL: &str = "den_wolverine";
const DEN_FOOT: f32 = 1.7;
const DEN_NAMES: [&str; 2] = ["The Wolverine's Den", "The Thief's Burrow"];
const DEN_LORE: &str = "Gnawed bones, a torn sack, and a little water cask branded with a ship's mark.";
/// Stashes keep at least this far from each other.
const SPREAD: f32 = 30.0;

#[derive(Clone, Debug)]
struct Site {
    /// `0..10` = [`KINDS`], `10..` = dens.
    idx: usize,
    pos: Vec2,
    yaw: f32,
}

static SITES: Mutex<Vec<Site>> = Mutex::new(Vec::new());

pub fn reset_plan() {
    SITES.lock().unwrap().clear();
}

fn foot_of(idx: usize) -> f32 {
    KINDS.get(idx).map(|k| k.foot).unwrap_or(DEN_FOOT)
}

/// `(centre, radius)` of every planned stash / den (folded into `poi::story_clearings`).
pub fn planned_footprints() -> Vec<(Vec2, f32)> {
    SITES.lock().unwrap().iter().map(|s| (s.pos, foot_of(s.idx) + 1.0)).collect()
}

/// Centre of every planned stash / den — for the density audit.
#[cfg_attr(not(test), allow(dead_code))]
pub fn planned_sites() -> Vec<Vec2> {
    SITES.lock().unwrap().iter().map(|s| s.pos).collect()
}

pub fn overlaps_planned(x: f32, z: f32, r: f32) -> bool {
    let p = Vec2::new(x, z);
    SITES.lock().unwrap().iter().any(|s| p.distance_squared(s.pos) < (foot_of(s.idx) + r + 0.35).powi(2))
}

/// The wolverine dens (world XZ), in plan order.
pub fn den_sites() -> Vec<Vec2> {
    SITES.lock().unwrap().iter().filter(|s| s.idx >= KINDS.len()).map(|s| s.pos).collect()
}

fn rng_next(state: &mut u32) -> f32 {
    *state = state.wrapping_add(0x6d2b_79f5);
    let mut t = *state;
    t = (t ^ (t >> 15)).wrapping_mul(t | 1);
    t ^= t.wrapping_add((t ^ (t >> 7)).wrapping_mul(t | 61));
    ((t ^ (t >> 14)) as f32) / 4_294_967_296.0
}

fn region_box(b: Biome) -> [f32; 4] {
    let (c, r) = match b {
        Biome::Forest => (Vec2::new(-156.0, 101.0), 130.0),
        Biome::Swamp => (Vec2::new(0.0, 148.0), 85.0),
        Biome::Rocky => (Vec2::new(176.0, 23.0), 145.0),
        Biome::Desert => (Vec2::new(144.0, -133.0), 165.0),
        _ => (Vec2::new(-179.0, -117.0), 175.0),
    };
    [c.x - r, c.x + r, c.y - r, c.y + r]
}

fn ground_ok(p: Vec2, biome: Biome, foot: f32, wet: bool) -> bool {
    let Some(y0) = crate::worldmap::ground_at_world(p.x, p.y) else { return false };
    if crate::worldmap::tile_biome_world(p.x, p.y) != Some(biome)
        || crate::worldmap::is_pool_world(p.x, p.y)
        || crate::worldmap::is_open_water_world(p.x, p.y)
    {
        return false;
    }
    let (mut lo, mut hi) = (y0, y0);
    for k in 0..10 {
        let a = k as f32 * (TAU / 10.0);
        let q = p + Vec2::new(a.cos(), a.sin()) * foot;
        let Some(y) = crate::worldmap::ground_at_world(q.x, q.y) else { return false };
        lo = lo.min(y);
        hi = hi.max(y);
        if crate::roads::on_road(q.x + a.cos() * 1.5, q.y + a.sin() * 1.5) {
            return false;
        }
    }
    if hi - lo > 0.45 {
        return false;
    }
    if wet {
        let near = (0..12).any(|k| {
            let a = k as f32 * (TAU / 12.0);
            [1.8f32, 2.6, 3.4].iter().any(|r| crate::worldmap::is_pool_world(p.x + a.cos() * r, p.y + a.sin() * r))
        });
        if !near {
            return false;
        }
    }
    !crate::poi::overlaps_planned_clearing(p.x, p.y, foot)
        && !crate::town::near_build_plot(p.x, p.y)
        && p.length() > 70.0
        && crate::camps::plan().iter().all(|c| c.centre.distance(p) > 16.0 + foot)
        && crate::ruins::landmark_sites().iter().all(|l| l.pos.distance(p) > 18.0 + foot)
}

fn seat(idx: usize, biome: Biome, foot: f32, wet: bool, prefer: Option<[f32; 4]>, planned: &[Site], seed: u32) -> Option<Site> {
    let mut boxes: Vec<[f32; 4]> = prefer.into_iter().collect();
    boxes.push(region_box(biome));
    for (bi, bx) in boxes.iter().enumerate() {
        let mut s = seed ^ (bi as u32 * 0x9E37);
        for _ in 0..2500 {
            let p = Vec2::new(bx[0] + (bx[1] - bx[0]) * rng_next(&mut s), bx[2] + (bx[3] - bx[2]) * rng_next(&mut s));
            if planned.iter().any(|o| o.pos.distance(p) < SPREAD) {
                continue;
            }
            if ground_ok(p, biome, foot, wet) {
                return Some(Site { idx, pos: p, yaw: rng_next(&mut s) * TAU });
            }
        }
    }
    None
}

/// Build phase 4 (after `wild_sites::plan`): reserve every stash and den.
pub fn plan() {
    reset_plan();
    let mut planned: Vec<Site> = Vec::new();
    for (i, k) in KINDS.iter().enumerate() {
        match seat(i, k.biome, k.foot, k.wet, k.prefer, &planned, 0x57A5_0000 + i as u32 * 7919) {
            Some(s) => planned.push(s),
            None => warn!("stashes: no spot for {}", k.model),
        }
    }
    for d in 0..2 {
        match seat(KINDS.len() + d, Biome::Snow, DEN_FOOT, false, None, &planned, 0xDE40_0000 + d as u32 * 104_729) {
            Some(s) => planned.push(s),
            None => warn!("stashes: no spot for wolverine den {d}"),
        }
    }
    for s in &planned {
        crate::blockers::reserve_visual(s.pos.x, s.pos.y, foot_of(s.idx));
        let model = KINDS.get(s.idx).map(|k| k.model).unwrap_or(DEN_MODEL);
        info!("stashes: planned {model} at {:.1},{:.1}", s.pos.x, s.pos.y);
    }
    *SITES.lock().unwrap() = planned;
}

/// One stash on the map: its index into [`KINDS`] (its bit in `stash_looted`).
#[derive(Component)]
struct Stash(usize);

/// A wolverine den (index into `den_sites`).
#[derive(Component)]
struct Den(usize);

fn seat_y(p: Vec2, foot: f32) -> f32 {
    let y0 = crate::worldmap::ground_at_world(p.x, p.y).unwrap_or(0.0);
    let mut lo = y0;
    for k in 0..10 {
        let a = k as f32 * (TAU / 10.0);
        if let Some(y) = crate::worldmap::ground_at_world(p.x + a.cos() * foot * 0.7, p.y + a.sin() * foot * 0.7) {
            lo = lo.min(y);
        }
    }
    (y0 - 0.6 * (y0 - lo)).max(lo) - 0.03
}

/// Build phase 32: spawn every planned stash and den.
pub fn populate(commands: &mut Commands) {
    let Some(kit) = crate::realforest::get().filter(|k| k.has(KINDS[0].model)) else {
        warn!("stashes: stashes.glb not in the kit — no stashes");
        return;
    };
    let range = VisibilityRange { start_margin: 0.0..0.0, end_margin: 90.0..110.0, use_aabb: true };
    let sites = SITES.lock().unwrap().clone();
    for s in sites {
        let foot = foot_of(s.idx);
        let tf = Transform::from_xyz(s.pos.x, seat_y(s.pos, foot), s.pos.y).with_rotation(Quat::from_rotation_y(s.yaw));
        let (model, name, lore, prompt) = match KINDS.get(s.idx) {
            Some(k) => (k.model, k.name, k.lore, "Search the stash"),
            None => {
                let d = s.idx - KINDS.len();
                (DEN_MODEL, DEN_NAMES[d.min(1)], DEN_LORE, "Search the den")
            }
        };
        let Some(e) = kit.spawn_static_with(commands, model, tf, range.clone()) else { continue };
        commands.entity(e).insert((BiomeEntity, Interactable::new(prompt, 2.4)));
        if s.idx < KINDS.len() {
            commands.entity(e).insert(Stash(s.idx));
        } else {
            commands.entity(e).insert(Den(s.idx - KINDS.len()));
        }
        crate::landmarks::attach_story(commands, e, name, lore);
        crate::blockers::add_obb(s.pos.x, s.pos.y, foot * 0.35, foot * 0.35, s.yaw);
        info!("stashes: {model} at {:.1},{:.1}", s.pos.x, s.pos.y);
    }
}

pub struct StashesPlugin;

impl Plugin for StashesPlugin {
    fn build(&self, app: &mut App) {
        app.add_sim_systems((search, reconcile_looted));
        app.add_systems(Update, stage_stashline);
    }
}

/// Deterministic per-spot roll.
fn hash(p: Vec2) -> f64 {
    let s = (p.x as f64 * 127.1 + p.y as f64 * 311.7).sin() * 43758.5453;
    s - s.floor()
}

/// A chest-pool haul by distance from the keep (`chest::tier_for`): gold + provisions.
fn haul(p: Vec2) -> (i64, Vec<&'static str>) {
    let f = crate::verbs::forest_frontier(p.x, p.y);
    let h = hash(p);
    match crate::chest::tier_for(f) {
        crate::chest::ChestTier::Relic => ((22.0 + f * 30.0 + h * 12.0).round() as i64, vec![if h < 0.5 { "potion" } else { "feast" }, "bread"]),
        crate::chest::ChestTier::Wood => ((8.0 + f * 20.0 + h * 6.0).round() as i64, vec!["bread"]),
    }
}

#[allow(clippy::too_many_arguments)]
fn search(
    time: Res<Time>,
    mut ev: MessageReader<Interacted>,
    mut flags: ResMut<WorldFlags>,
    mut inv: ResMut<crate::inventory::Inventory>,
    mut toasts: ResMut<crate::inventory::Toasts>,
    mut player: ResMut<crate::player::PlayerRes>,
    mut floats: ResMut<crate::combat_fx::FloatQueue>,
    mut hoards: ResMut<crate::oddities::DenHoards>,
    mut cues: MessageWriter<crate::audio::AudioCue>,
    mut commands: Commands,
    stashes: Query<(&Stash, &GlobalTransform)>,
    dens: Query<(&Den, &GlobalTransform)>,
) {
    let now = time.elapsed_secs() as f64;
    for Interacted(e) in ev.read() {
        let (items, gold, at): (Vec<String>, i64, Vec3) = if let Ok((s, g)) = stashes.get(*e) {
            if flags.get("stash_looted") & (1 << s.0) != 0 {
                continue;
            }
            let p = g.translation();
            let (gold, items) = haul(Vec2::new(p.x, p.z));
            let m = flags.get("stash_looted") | (1 << s.0);
            flags.set("stash_looted", m);
            commands.entity(*e).remove::<Interactable>();
            (items.into_iter().map(String::from).collect(), gold, p)
        } else if let Ok((d, g)) = dens.get(*e) {
            let mut items: Vec<String> = hoards.0.get_mut(d.0).map(std::mem::take).unwrap_or_default();
            let mut gold = 0;
            if flags.get("den_searched") & (1 << d.0) == 0 {
                let m = flags.get("den_searched") | (1 << d.0);
                flags.set("den_searched", m);
                items.push("bread".into()); // the castaways' ship's biscuit
                gold = 12;
            }
            if items.is_empty() {
                floats.0.push(crate::combat_fx::FloatReq {
                    world: g.translation() + Vec3::Y * 1.2,
                    text: "Only bones".into(),
                    color: crate::combat_fx::col_block(),
                    scale: 0.9,
                });
                continue;
            }
            (items, gold, g.translation())
        } else {
            continue;
        };
        for id in &items {
            crate::inventory::try_grant(&mut inv.0, &mut toasts.0, id, 1, now);
        }
        if gold > 0 {
            player.0.add_gold(gold);
            floats.0.push(crate::combat_fx::FloatReq {
                world: at + Vec3::Y * 1.3,
                text: format!("+{gold} gold"),
                color: crate::combat_fx::col_kill(),
                scale: 1.0,
            });
            cues.write(crate::audio::AudioCue::Gold);
        }
        cues.write(crate::audio::AudioCue::Forage);
    }
}

/// Looted state follows the flags both ways: a Continue re-marks looted stashes, a New Game (flags
/// cleared) re-arms them.
fn reconcile_looted(flags: Res<WorldFlags>, mut commands: Commands, q: Query<(Entity, &Stash, Has<Interactable>)>) {
    if !flags.is_changed() {
        return;
    }
    let mask = flags.get("stash_looted");
    for (e, s, has) in &q {
        let looted = mask & (1 << s.0) != 0;
        if looted && has {
            commands.entity(e).remove::<Interactable>();
        } else if !looted && !has {
            commands.entity(e).try_insert(Interactable::new("Search the stash", 2.4));
        }
    }
}

fn stage_stashline(mut commands: Commands, mut done: Local<bool>, ready: Res<crate::biome::WorldReady>) {
    if *done || !ready.0 {
        return;
    }
    *done = true;
    let Ok(v) = std::env::var("FOREST_STASHLINE") else { return };
    let xz: Vec<f32> = v.split(',').filter_map(|s| s.trim().parse().ok()).collect();
    let (Some(kit), [x, z, ..]) = (crate::realforest::get(), xz.as_slice()) else { return };
    let models: Vec<&str> = KINDS.iter().map(|k| k.model).chain([DEN_MODEL, "castaway_grotto", "sled_runner"]).collect();
    let mut dx = 0.0;
    for m in models {
        let p = Vec2::new(x + dx, *z);
        let y = crate::steer::footing(p.x, p.y).unwrap_or(0.0);
        kit.spawn_static(&mut commands, m, Transform::from_xyz(p.x, y, p.y));
        info!("stashes: STASHLINE {m} at {:.1},{:.1}", p.x, p.y);
        dx += if m == "castaway_grotto" { 7.0 } else { 4.5 };
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Every stash lands in its own biome, apart from the others; the dens in the snow; Tobin's
    /// grotto on the snow coast. Prints the sites (`-- --nocapture`) for shot framing.
    #[test]
    fn stashes_plan_in_their_biomes() {
        let _g = crate::blockers::TEST_LOCK.lock().unwrap();
        crate::blockers::reset();
        crate::poi::plan_clearings();
        crate::stories_warm::plan();
        crate::vignettes::plan();
        crate::wayside::plan();
        crate::stories_cold::plan();
        crate::sites_warm::plan();
        crate::wild_sites::plan();
        crate::castaway::plan();
        plan();
        let sites = SITES.lock().unwrap().clone();
        for s in &sites {
            let (model, biome) = KINDS.get(s.idx).map(|k| (k.model, k.biome)).unwrap_or((DEN_MODEL, Biome::Snow));
            let y = crate::worldmap::ground_at_world(s.pos.x, s.pos.y).unwrap_or(0.0);
            eprintln!("stash {model} at ({:.1}, {:.2}, {:.1}) yaw {:.2}", s.pos.x, y, s.pos.y, s.yaw);
            assert_eq!(crate::worldmap::tile_biome_world(s.pos.x, s.pos.y), Some(biome), "{model} off its biome");
        }
        assert!(sites.len() >= 10, "only {} stashes/dens planned", sites.len());
        for (i, a) in sites.iter().enumerate() {
            for b in &sites[i + 1..] {
                assert!(a.pos.distance(b.pos) >= SPREAD - 0.01);
            }
        }
        for (p, _) in crate::castaway::planned_footprints() {
            eprintln!("grotto at ({:.1}, {:.2}, {:.1})", p.x, crate::worldmap::ground_at_world(p.x, p.y).unwrap_or(0.0), p.y);
        }
        for (x, z) in [(-45.0f32, -42.0f32), (-30.0, -42.0), (-14.0, -42.0), (-45.0, -54.0), (0.0, -54.0), (20.0, -54.0)] {
            eprintln!("ground ({x},{z}) = {:?}", crate::worldmap::ground_at_world(x, z));
        }
        crate::blockers::reset();
        reset_plan();
        crate::castaway::reset_plan();
    }
}
