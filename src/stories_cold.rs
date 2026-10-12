//! **Cold-biome story set-pieces** — environmental storytelling inside the Snow and Rocky biomes
//! (RDR2 / Skyrim style: no text, no interaction, a scene that explains itself). The roadside
//! pieces (`poi.rs`) tell the road's stories; these sit OUT in the wild, where a traveller stumbles
//! on them:
//!
//! - **Snow** — the remains of the FIRST COLONY (Brother Anselm's, a century ago — see the campaign
//!   plan, `docs/superpowers/specs/2026-10-10-kampania-fabula-design.md`): the timber party's lost
//!   camp (collapsed tent under a drift, a sled with lashed crates, a cold fire ring, skis still
//!   planted upright, a marker pole); a colonist's avalanche-buried winter cabin (beams jutting from
//!   the mound, the stone chimney still standing); the colony's last muster (a cairn topped with a
//!   helmet, a tattered banner, broken shields and spears); a ruined outlying homestead (a burned log
//!   house, charred roof beams jutting from a drift, a broken palisade stub, the well with its winch
//!   fallen, a tipped hand-cart). And three one-off sites: the **Crown Convoy** wrecked beside the
//!   pass trail (the lead wagon broke under a bronze WAR BELL — its cradle snapped, the bell tipped
//!   out on its side in a drift, mouth to the trail, the Crown cast on its flank, the clapper flung
//!   clear; the second wagon thrown on its side), **Anselm's Hermitage** (a dry-stone
//!   cell with an EMPTY bell-cote, two graves, his writing slope) and the **Old Ones' Ring** (carved
//!   standing stones, ork offerings at the centre).
//! - **Rocky** — an abandoned mine head (timber headframe over an open shaft, a tipped ore cart at
//!   the end of its rail run); a rockfall that crushed a wagon on the track; a half-cut monolith in
//!   a small quarry, the masons' tools dropped where they stood.
//!
//! Models: `stories_cold.glb` (`tools/blender_forest/stories_cold.py`), real scale, base y=0.
//!
//! Every site is a minor DISCOVERABLE (`landmarks::attach_story`): walking up to it announces its
//! name + one lore line, chimes and pays a little gold — no beacon, no shrine, outside the
//! five-landmark tally, saved by name. The lore only seeds the campaign's twist (the bell's voice,
//! the Crown's foreknowledge); it never states it.
//!
//! Placement is planned at build phase 4, right after `poi` / `vignettes` / `wayside` ([`plan`]),
//! before any scatter: `poi::story_clearings` folds these sites in, so trees, rocks, ore, chests and
//! forage all keep clear. Each scene gets [`PER_SCENE`] spots inside its own biome, scanned from a
//! deterministic jittered grid and accepted only on FLAT ground — the height is sampled over the
//! whole footprint (`worldmap::ground_at_world`), so the planner follows whatever shape the terrain
//! currently has (no hand-authored coordinates). Off roads, pass trails, rivers, pools, cliff
//! shelves, camps, landmarks, the town, other story pieces and blockers. At phase 32 ([`populate`])
//! each site is re-checked against the finished world and re-sited (never silently dropped) if a
//! later phase claimed it.

use std::f32::consts::TAU;
use std::sync::Mutex;

use bevy::camera::visibility::VisibilityRange;
use bevy::prelude::*;

use crate::biome::{Biome, BiomeEntity};

/// One story scene: its kit model, the biome it belongs to, the visual radius it reserves, its
/// solid masses as model-local oriented boxes `(x, z, half width, half depth, local yaw)`, how many
/// instances it wants, the discoverable name of each instance (by plan order) and its lore line.
/// `trail`: the scene hugs a pass trail (long axis along it) instead of standing out in the open.
struct Scene {
    model: &'static str,
    biome: Biome,
    foot: f32,
    solids: &'static [(f32, f32, f32, f32, f32)],
    want: usize,
    names: &'static [&'static str],
    lore: &'static str,
    trail: bool,
    /// Least `alpine::snow_cover` under the whole footprint (snow scenes; 0 for rocky ones). Snow
    /// grows with altitude, so this sets how high a scene sits: the avalanche-buried cabin in deep
    /// snow, the camps and cairns in patchy snow, the steading and the pass-trail convoy lower,
    /// where the snow line starts.
    snow: f32,
}

const SCENES: [Scene; 10] = [
    // The drift + collapsed tent, the sled with its crates, the planted skis (+ the marker pole).
    Scene { model: "story_lost_camp", biome: Biome::Snow, snow: 0.45, foot: 2.6,
        solids: &[(-0.6, 0.2, 1.1, 1.0, 0.0), (1.15, -0.75, 1.0, 0.45, 0.35), (2.02, 0.35, 0.25, 0.3, 0.0)],
        // One here + the Frozen Camp vignette (`vignettes.rs`, same model) = the two-copy cap.
        want: 1, names: &["The Timber Party's Camp", "The Iron Party's Camp", "The Woodcutters' Last Camp"],
        lore: "Anselm's timber party camped here; the colony rang for them nine dusks, and none came down.",
        trail: false },
    // The avalanche mound over the cabin + the standing chimney.
    Scene { model: "story_buried_cabin", biome: Biome::Snow, snow: 0.4, foot: 3.0,
        solids: &[(0.1, 0.0, 1.9, 1.4, 0.0), (-1.9, -0.6, 0.45, 0.45, 0.0)],
        want: 3, names: &["A Colonist's Winter Cabin", "The Snowbound Cabin", "The Chimney in the Snow"],
        lore: "A colonist built far from the chapel bell; the snow took his cabin, but nothing else came.",
        trail: false },
    // The cairn and the banner pole's foot.
    Scene { model: "story_frozen_memorial", biome: Biome::Snow, snow: 0.45, foot: 2.3,
        solids: &[(0.0, 0.0, 0.6, 0.6, 0.0), (0.6, -0.4, 0.08, 0.08, 0.0)],
        want: 3, names: &["The Last Muster", "The Muster Cairn", "The Colony's Cairn"],
        lore: "The first colony's last muster; that night, as every night, they rang the bell at dusk.",
        trail: false },
    // Headframe legs over the shaft (the shaft itself is inside the legs), the tipped cart, the spoil heap.
    Scene { model: "story_mine_head", biome: Biome::Rocky, snow: 0.0, foot: 3.1,
        solids: &[(0.0, 0.0, 1.15, 1.0, 0.0), (2.15, 0.85, 0.55, 0.45, 0.2), (-1.9, 1.2, 0.75, 0.6, 0.0)],
        want: 3, names: &["The Colony Mine", "The Iron Shaft", "The Old Headframe"],
        lore: "The first colony's iron came out of this shaft; the headframe outlived every man who worked it.",
        trail: false },
    // The crushed wagon under its boulders + the third boulder.
    Scene { model: "story_rockfall_wagon", biome: Biome::Rocky, snow: 0.0, foot: 2.9,
        solids: &[(0.0, 0.0, 1.45, 0.8, 0.0), (1.55, -0.95, 0.55, 0.5, 0.0), (-1.8, -0.85, 0.4, 0.35, 0.0)],
        want: 3, names: &["The Crushed Wagon", "The Rockfall", "The Buried Wagon"],
        lore: "The mountain came down on this wagon, and no one ever came back to dig it out.",
        trail: false },
    // The bedrock shelf with the half-cut block, and the monolith blank on its rollers.
    Scene { model: "story_quarry", biome: Biome::Rocky, snow: 0.0, foot: 2.8,
        solids: &[(-0.6, -0.4, 1.35, 0.95, 0.08), (1.25, 0.9, 1.2, 0.45, -0.6)],
        want: 3, names: &["The Half-Cut Stone", "The Masons' Quarry", "The Silent Quarry"],
        lore: "The masons dropped their tools mid-cut and never came back for the stone.",
        trail: false },
    // The bell on its side, the broken bell wagon, the wagon on its side, the ox's drift.
    Scene { model: "story_wrecked_convoy", biome: Biome::Snow, snow: 0.2, foot: 3.5,
        solids: &[(0.0, -1.45, 0.75, 0.7, 0.0), (1.95, 0.75, 1.25, 0.7, 0.05), (-2.05, 0.7, 1.3, 0.45, 0.12),
            (-0.1, 2.0, 0.9, 0.45, 0.0)],
        want: 1, names: &["The Crown Convoy"],
        lore: "A Crown war bell, hauled up the pass for the first colony; no one ever came back to dig it out.",
        trail: true },
    // The hermitage's walls (door gap included) + the bell-cote gable, and the two graves.
    Scene { model: "story_hermitage", biome: Biome::Snow, snow: 0.5, foot: 3.4,
        solids: &[(0.0, 0.0, 1.35, 1.05, 0.0), (-2.25, 1.45, 0.4, 1.0, 0.0)],
        want: 1, names: &["Anselm's Hermitage"],
        lore: "Cut into the writing slope: the charter bids us ring at dusk, and none of us can say why.",
        trail: false },
    // Six stones on a 2.8u ring + the totem and offering stone at the centre.
    Scene { model: "story_old_ones_ring", biome: Biome::Snow, snow: 0.5, foot: 3.6,
        solids: &[(2.74, 0.56, 0.35, 0.35, 0.0), (0.89, 2.66, 0.33, 0.33, 0.0), (-1.86, 2.1, 0.33, 0.33, 0.0),
            (-2.74, -0.56, 0.33, 0.33, 0.0), (-0.89, -2.66, 0.33, 0.33, 0.0), (1.86, -2.1, 0.33, 0.33, 0.0),
            (0.0, 0.0, 0.55, 0.55, 0.3)],
        want: 1, names: &["The Old Ones' Ring"],
        lore: "Every stone is cut with rings like a bell's voice; the orks still bring tusks, as if to a law.",
        trail: false },
    // The burned log house, the well, the palisade stub, the tipped hand-cart.
    Scene { model: "story_ruined_homestead", biome: Biome::Snow, snow: 0.3, foot: 3.0,
        solids: &[(-0.6, 0.2, 1.3, 1.05, 0.0), (1.55, -0.95, 0.6, 0.6, 0.0), (1.7, 1.5, 0.9, 0.35, -0.3),
            (-2.0, -1.35, 0.55, 0.45, 0.7)],
        want: 3, names: &["The Outlying Steading", "The Burned Homestead", "The Palisade Farm"],
        lore: "They farmed beyond the reach of the chapel bell and raised a palisade instead; it was not enough.",
        trail: false },
];

/// Order the plan seats scenes in each round: the one-off discoverables first (the convoy, which
/// needs the narrowest ground — beside a trail — leads), then the repeating scenes.
const SEAT_ORDER: [usize; 10] = [6, 7, 8, 0, 1, 9, 2, 3, 4, 5];
/// The one-off discoverables stand at least this far from each other, so they spread over the
/// snow region instead of clustering on its best ground.
const ONE_OFF_SPREAD: f32 = 35.0;
/// A trail-hugging scene's centre sits this far (beyond its footprint) off the trail's centreline:
/// alongside the painted strip, never on it ([`ground_ok`] still enforces [`SNOW_ROAD_KEEP`]).
const TRAIL_HUG: [f32; 6] = [2.5, 3.25, 4.0, 4.75, 5.5, 6.5];

/// Most instances any scene is planned (each in its own biome, spread apart; see `Scene::want`).
pub const PER_SCENE: usize = 3;
/// Max terrain height spread under a footprint (outer ring + inner ring vs. the centre). The
/// models sink their contact parts ~0.2–0.3u, so this much slope never shows a floating edge.
const FLAT_DELTA: f32 = 0.45;
/// Relaxed second pass, only for a scene the strict pass couldn't seat [`MIN_PER_SCENE`] times.
const FLAT_DELTA_RELAXED: f32 = 0.7;
const MIN_PER_SCENE: usize = 2;
/// Same keep-outs as `poi.rs`.
const CAMP_KEEP: f32 = 7.0;
const TOWN_KEEP: f32 = 4.0;
const LANDMARK_KEEP: f32 = 14.0;
/// Two instances of the same scene stand at least this far apart; any two story pieces at least
/// [`MIN_GAP`] past their footprints.
const SAME_SCENE_SPACING: f32 = 70.0;
/// The snowfield is smaller than the rocky country (and now also holds the three one-off sites), so
/// repeats of a snow scene may stand closer.
const SAME_SCENE_SPACING_SNOW: f32 = 48.0;
const MIN_GAP: f32 = 12.0;
/// Rocky scenes: clearance from a pass trail's centreline beyond the footprint.
const TRAIL_KEEP: f32 = 3.0;
/// A snow scene stands on real snow (`alpine::snow_cover`, height-driven, at least its own
/// [`Scene::snow`]) — never on the snow biome's bare valley meadow, where a buried cabin reads as a
/// white blob on grass. Up on the massif the
/// flat ground is the pass VALLEY floors beside the trails and the col, so snow scenes skip the
/// rocky rules that ban the whole cliffy shelf / pass corridor and only keep [`SNOW_ROAD_KEEP`] off
/// the painted trail strip itself.
const SNOW_ROAD_KEEP: f32 = 2.0;
/// Last-resort flatness for snow scenes: the model is then sunk by part of the spread
/// ([`seat_y`]) and its drift skirts swallow the uphill side.
const FLAT_DELTA_SNOW_MAX: f32 = 1.3;
/// A trail scene (the convoy) may stand on the pass CLIMB, tilted onto the slope ([`seat_tilted`]):
/// the snow lies up on the climb, while the flat valley floor where the trail starts is bare meadow.
const FLAT_DELTA_TRAIL: f32 = 1.6;
/// Spawn-time last resort: a claimed site with no free alternative is still spawned in place when
/// nothing solid stands inside this fraction of its footprint (only the drift rim is intruded on).
const RIM_GRACE: f32 = 0.8;

#[derive(Clone, Debug, PartialEq)]
struct Site {
    scene: usize,
    pos: Vec2,
    yaw: f32,
}

static SITES: Mutex<Vec<Site>> = Mutex::new(Vec::new());

pub fn reset_plan() {
    SITES.lock().unwrap().clear();
}

/// `(centre, visual radius)` of every planned cold story site (folded into `poi::story_clearings`).
pub fn planned_footprints() -> Vec<(Vec2, f32)> {
    SITES.lock().unwrap().iter().map(|s| (s.pos, SCENES[s.scene].foot)).collect()
}

/// `(centre, visual radius)` of every planned SNOW story site: the alpine mask bakes a pocket of
/// snow under each (`alpine::bake_mask`), so a site at the snow line stands in its own drift.
pub fn snow_footprints() -> Vec<(Vec2, f32)> {
    SITES.lock().unwrap().iter().filter(|s| SCENES[s.scene].biome == Biome::Snow).map(|s| (s.pos, SCENES[s.scene].foot)).collect()
}

/// Does a circle at `(x, z)` of radius `r` overlap a planned cold story site?
pub fn overlaps_planned(x: f32, z: f32, r: f32) -> bool {
    let p = Vec2::new(x, z);
    SITES.lock().unwrap().iter().any(|s| p.distance_squared(s.pos) < (SCENES[s.scene].foot + r + 0.35).powi(2))
}

fn rng_next(state: &mut u32) -> f32 {
    *state = state.wrapping_add(0x6d2b_79f5);
    let mut t = *state;
    t = (t ^ (t >> 15)).wrapping_mul(t | 1);
    t ^= t.wrapping_add((t ^ (t >> 7)).wrapping_mul(t | 61));
    ((t ^ (t >> 14)) as f32) / 4_294_967_296.0
}

fn seg_dist(p: Vec2, a: Vec2, b: Vec2) -> f32 {
    let ab = b - a;
    let t = if ab.length_squared() < 1e-6 { 0.0 } else { ((p - a).dot(ab) / ab.length_squared()).clamp(0.0, 1.0) };
    p.distance(a + ab * t)
}

/// `(centre, lowest, highest)` ground height over a footprint (the same rings [`ground_ok`] probes).
fn footprint_heights(x: f32, z: f32, foot: f32) -> Option<(f32, f32, f32)> {
    let y0 = crate::worldmap::ground_at_world(x, z)?;
    let (mut lo, mut hi) = (y0, y0);
    for (n, r) in [(16, foot), (8, foot * 0.55)] {
        for k in 0..n {
            let a = k as f32 * (TAU / n as f32);
            let y = crate::worldmap::ground_at_world(x + a.cos() * r, z + a.sin() * r)?;
            lo = lo.min(y);
            hi = hi.max(y);
        }
    }
    Some((y0, lo, hi))
}

/// Base height to seat a scene at: the centre, sunk by part of the footprint's height spread (never
/// below its lowest point) so the downhill edge doesn't float; the contact parts / drift skirts run
/// below y=0 and swallow the uphill side.
/// Height + tilt for a trail scene on a slope: the model is laid onto the footprint's best-fit plane
/// (wagons slid off a climbing trail), then sunk like [`seat_y`] by part of what the plane leaves.
fn seat_tilted(x: f32, z: f32, foot: f32) -> (f32, Quat) {
    let h = |dx: f32, dz: f32| crate::worldmap::ground_at_world(x + dx, z + dz);
    let r = foot * 0.7;
    let (Some(y0), Some(xp), Some(xn), Some(zp), Some(zn)) = (h(0.0, 0.0), h(r, 0.0), h(-r, 0.0), h(0.0, r), h(0.0, -r)) else {
        return (seat_y(x, z, foot), Quat::IDENTITY);
    };
    let (gx, gz) = ((xp - xn) / (2.0 * r), (zp - zn) / (2.0 * r));
    let (mut lo, mut hi) = (0.0f32, 0.0f32);
    for k in 0..16 {
        let a = k as f32 * (TAU / 16.0);
        let (dx, dz) = (a.cos() * foot, a.sin() * foot);
        if let Some(y) = h(dx, dz) {
            let d = y - (y0 + gx * dx + gz * dz);
            lo = lo.min(d);
            hi = hi.max(d);
        }
    }
    let tilt = Quat::from_rotation_arc(Vec3::Y, Vec3::new(-gx, 1.0, -gz).normalize());
    (y0 + (-0.6 * (hi - lo)).max(lo) - 0.04, tilt)
}

fn seat_y(x: f32, z: f32, foot: f32) -> f32 {
    match footprint_heights(x, z, foot) {
        Some((y0, lo, hi)) => (y0 - 0.6 * (hi - lo)).max(lo) - 0.04,
        None => crate::worldmap::ground_at_world(x, z).unwrap_or(0.0) - 0.04,
    }
}

/// Ground + keep-out rules for a footprint of radius `foot` centred at `(x, z)`, all of it inside
/// `biome` and no higher spread than `flat`. Shared by the plan, the spawn re-check and the test.
/// Snow scenes additionally need `need` snow cover ([`Scene::snow`]) and use the valley-floor road
/// rule (see [`SNOW_ROAD_KEEP`]).
fn ground_ok(x: f32, z: f32, foot: f32, biome: Biome, need: f32, flat: f32, trails: &[Vec<Vec2>]) -> bool {
    let Some(y0) = crate::worldmap::ground_at_world(x, z) else { return false };
    if crate::worldmap::tile_biome_world(x, z) != Some(biome) {
        return false;
    }
    let snow = biome == Biome::Snow;
    if snow && crate::alpine::snow_cover(x, z) < need {
        return false;
    }
    // The painted trail strip + a margin stays clear of a snow scene's whole footprint.
    if snow {
        for k in 0..16 {
            let a = k as f32 * (TAU / 16.0);
            let r = foot + SNOW_ROAD_KEEP;
            if crate::roads::on_road(x + a.cos() * r, z + a.sin() * r) {
                return false;
            }
        }
    }
    let (mut lo, mut hi) = (y0, y0);
    for (n, r) in [(16, foot), (8, foot * 0.55)] {
        for k in 0..n {
            let a = k as f32 * (TAU / n as f32);
            let (px, pz) = (x + a.cos() * r, z + a.sin() * r);
            let Some(y) = crate::worldmap::ground_at_world(px, pz) else { return false };
            lo = lo.min(y);
            hi = hi.max(y);
            if hi - lo > flat
                || crate::worldmap::tile_biome_world(px, pz) != Some(biome)
                || crate::roads::on_road(px, pz)
                || crate::worldmap::is_river_world(px, pz)
                || crate::worldmap::is_pool_world(px, pz)
                || (!snow && crate::worldmap::cliff_shelf_world(px, pz))
                || (snow && crate::alpine::snow_cover(px, pz) < need)
                || crate::town::near_build_plot(px, pz)
                || crate::castle::in_footprint(px, pz)
                || crate::camps::in_clearing(px, pz)
                || crate::rival::near_fort(px, pz)
                || crate::ruins::near_landmark_visual_footprint(px, pz)
            {
                return false;
            }
        }
    }
    let q = Vec2::new(x, z);
    (snow || !crate::worldmap::cliff_shelf_world(x, z))
        && !crate::bridges::near_bridge(x, z, foot + 0.5)
        && crate::ork_fortress::blight_edge_world(x, z) < -(foot + 4.0)
        && q.length() > crate::worldmap::SAFE_R * crate::worldmap::MAP_SCALE + TOWN_KEEP + foot
        && crate::camps::plan().iter().all(|c| c.centre.distance(q) > CAMP_KEEP + foot)
        && crate::ruins::landmark_sites().iter().all(|l| l.pos.distance(q) > LANDMARK_KEEP + foot)
        && (snow || trails.iter().all(|t| t.windows(2).all(|w| seg_dist(q, w[0], w[1]) > foot + TRAIL_KEEP)))
}

/// Free of every other planned piece: this plan's own sites, the roadside story pieces, wayside
/// furniture, the forest vignette, and anything solid — plus, while planning (`visual`), every
/// visual reservation. A spawn-time re-site skips that last test: by phase 32 the scatter has
/// reserved nearly all open ground, and its trunks / rocks are solids, which are still tested.
fn clear_of_others(q: Vec2, scene: usize, planned: &[Site], visual: bool) -> bool {
    let foot = SCENES[scene].foot;
    let one_off = SCENES[scene].want == 1;
    let same = if SCENES[scene].biome == Biome::Snow { SAME_SCENE_SPACING_SNOW } else { SAME_SCENE_SPACING };
    planned.iter().all(|s| {
        let d = s.pos.distance(q);
        d > foot + SCENES[s.scene].foot + MIN_GAP
            && (s.scene != scene || d > same)
            && !(one_off && SCENES[s.scene].want == 1 && d < ONE_OFF_SPREAD)
    }) && !crate::poi::story_clearings().overlaps(q.x, q.y, foot + 1.0)
        && !(visual && crate::blockers::any_visual_within(q.x, q.y, foot + 0.3))
        && !crate::blockers::any_within(q.x, q.y, foot + 0.3)
}

/// Candidate spots for a biome: a deterministic jittered grid over the whole map, in a stable
/// shuffled order (so the instances spread across the region instead of piling up in one corner).
fn grid_candidates(biome: Biome, seed: u32) -> Vec<Vec2> {
    // The snowfield's legal ground is scarce (valley floors between the trails), so it is scanned
    // at a finer pitch than the open rocky country.
    let step = if biome == Biome::Snow { 4.0 } else { 9.0 };
    let (gx, gz) = (crate::worldmap::GX, crate::worldmap::GZ);
    let (cols, rows) = (crate::worldmap::COLS as f32, crate::worldmap::ROWS as f32);
    let mut rng = seed;
    let mut out: Vec<(f32, Vec2)> = Vec::new();
    let mut z = -gz + step * 0.5;
    while z < rows - gz {
        let mut x = -gx + step * 0.5;
        while x < cols - gx {
            let p = Vec2::new(x + (rng_next(&mut rng) - 0.5) * step * 0.8, z + (rng_next(&mut rng) - 0.5) * step * 0.8);
            let key = rng_next(&mut rng);
            if crate::worldmap::tile_biome_world(p.x, p.y) == Some(biome) {
                out.push((key, p));
            }
            x += step;
        }
        z += step;
    }
    out.sort_by(|a, b| a.0.total_cmp(&b.0));
    out.into_iter().map(|(_, p)| p).collect()
}

/// A stable per-site yaw hashed from the scene and spot.
fn site_yaw(scene: usize, q: Vec2) -> f32 {
    let mut s = q.x.to_bits() ^ q.y.to_bits().rotate_left(16) ^ (scene as u32).wrapping_mul(0x9e37_79b9);
    rng_next(&mut s) * TAU
}

/// Spots alongside the pass trails for a trail-hugging scene: every ~5u down each trail, both
/// sides, at [`TRAIL_HUG`] offsets past the footprint; the yaw lays the model's long axis (local X)
/// along the trail with its spilled front (local -Z) turned toward it.
fn trail_candidates(foot: f32, trails: &[Vec<Vec2>]) -> Vec<(Vec2, f32)> {
    let mut out = Vec::new();
    for t in trails {
        for w in t.windows(2) {
            let (a, b) = (w[0], w[1]);
            let len = a.distance(b);
            if len < 0.5 {
                continue;
            }
            let d = (b - a) / len;
            let n = Vec2::new(-d.y, d.x);
            let steps = (len / 5.0).ceil() as usize;
            for k in 0..steps {
                let p = a + d * (len * (k as f32 + 0.5) / steps as f32);
                for off in TRAIL_HUG {
                    for side in [1.0f32, -1.0] {
                        let q = p + n * side * (foot + off);
                        // Local X along `d`: rotation_y(yaw) maps local X to (cos, -sin).
                        let mut yaw = (-d.y).atan2(d.x);
                        // Local -Z maps to (-sin yaw, -cos yaw); turn it toward the trail (-n * side).
                        if Vec2::new(-yaw.sin(), -yaw.cos()).dot(-n * side) < 0.0 {
                            yaw += std::f32::consts::PI;
                        }
                        out.push((q, yaw));
                    }
                }
            }
        }
    }
    out
}

/// Candidate `(spot, yaw)`s for a scene.
fn candidates(scene: usize, trails: &[Vec<Vec2>]) -> Vec<(Vec2, f32)> {
    let s = &SCENES[scene];
    if s.trail {
        return trail_candidates(s.foot, trails);
    }
    grid_candidates(s.biome, 0x51c0_1d00 ^ (scene as u32).wrapping_mul(0x85eb_ca6b))
        .into_iter()
        .map(|q| (q, site_yaw(scene, q)))
        .collect()
}

/// Seat up to `want` instances of `scene`, appending to `planned`. Strict flatness first, then the
/// relaxed pass only while the scene is short of [`MIN_PER_SCENE`].
fn seat(scene: usize, want: usize, planned: &mut Vec<Site>, trails: &[Vec<Vec2>], visual: bool) -> usize {
    let s = &SCENES[scene];
    let cands = candidates(scene, trails);
    let mut got = 0;
    let min = MIN_PER_SCENE.min(want);
    let passes = [(FLAT_DELTA, want), (FLAT_DELTA_RELAXED, min), (max_flat(s), min)];
    for (flat, need) in passes {
        for &(q, yaw) in &cands {
            if got >= need {
                break;
            }
            if clear_of_others(q, scene, planned, visual) && ground_ok(q.x, q.y, s.foot, s.biome, s.snow, flat, trails) {
                planned.push(Site { scene, pos: q, yaw });
                got += 1;
            }
        }
    }
    got
}

/// Build phase 4 (after `poi::plan_clearings`, `vignettes::plan`, `wayside::plan`): reserve every
/// cold story site so the scatter keeps clear.
pub fn plan() {
    reset_plan();
    let trails = crate::worldmap::pass_trails_world();
    let mut planned: Vec<Site> = Vec::new();
    // Interleave the scenes (one instance each per round) so no scene hogs the best ground.
    for round in 0..PER_SCENE {
        for scene in SEAT_ORDER {
            if round < SCENES[scene].want && planned.iter().filter(|s| s.scene == scene).count() == round {
                seat(scene, 1, &mut planned, &trails, true);
            }
        }
    }
    for (scene, s) in SCENES.iter().enumerate() {
        let n = planned.iter().filter(|p| p.scene == scene).count();
        if n < MIN_PER_SCENE.min(s.want) {
            warn!("stories_cold: only {n} spot(s) for {}", s.model);
        }
    }
    for site in &planned {
        crate::blockers::reserve_visual(site.pos.x, site.pos.y, SCENES[site.scene].foot);
        info!("stories_cold: planned {} at {:.1},{:.1} yaw {:.2}", SCENES[site.scene].model, site.pos.x, site.pos.y, site.yaw);
    }
    info!("stories_cold: planned {} cold story sites", planned.len());
    *SITES.lock().unwrap() = planned;
}

/// The loosest flatness a scene of `biome` is ever planned on.
fn max_flat(s: &Scene) -> f32 {
    if s.trail {
        FLAT_DELTA_TRAIL
    } else if s.biome == Biome::Snow {
        FLAT_DELTA_SNOW_MAX
    } else {
        FLAT_DELTA_RELAXED
    }
}

fn register_blockers(scene: usize, p: Vec2, yaw: f32) {
    let rot = Quat::from_rotation_y(yaw);
    for &(x, z, hw, hd, local_yaw) in SCENES[scene].solids {
        let o = rot * Vec3::new(x, 0.0, z);
        crate::blockers::add_obb(p.x + o.x, p.y + o.z, hw, hd, yaw + local_yaw);
    }
}

/// Still usable at spawn time? Its own reservation is there by design; re-check the ground rules
/// (relaxed flatness — it passed the plan) and solids placed since.
fn still_free(site: &Site, trails: &[Vec<Vec2>]) -> bool {
    let s = &SCENES[site.scene];
    ground_ok(site.pos.x, site.pos.y, s.foot, s.biome, s.snow, max_flat(s), trails)
        && !crate::blockers::any_within(site.pos.x, site.pos.y, s.foot + 0.2)
}

/// Build-phase 32 entry (right after `poi::populate`): spawn each planned scene, re-siting any a
/// later phase claimed.
pub fn populate(commands: &mut Commands, _meshes: &mut Assets<Mesh>, _materials: &mut Assets<StandardMaterial>) {
    let Some(kit) = crate::realforest::get().filter(|k| k.has(SCENES[0].model)) else {
        warn!("stories_cold: stories_cold.glb not in the kit — no cold story set-pieces");
        return;
    };
    let range = VisibilityRange { start_margin: 0.0..0.0, end_margin: 120.0..140.0, use_aabb: true };
    let trails = crate::worldmap::pass_trails_world();
    let planned = SITES.lock().unwrap().clone();
    let mut placed: Vec<Site> = Vec::with_capacity(planned.len());
    for (i, site) in planned.iter().enumerate() {
        let site = if still_free(site, &trails) {
            site.clone()
        } else {
            // Re-site against everything placed or still planned (its own spot excluded).
            let mut others: Vec<Site> = placed.iter().chain(&planned[i + 1..]).cloned().collect();
            let n = others.len();
            let s = &SCENES[site.scene];
            info!("stories_cold: {} at {:.1},{:.1} claimed (ground ok: {}, solid within: {})", s.model, site.pos.x,
                site.pos.y, ground_ok(site.pos.x, site.pos.y, s.foot, s.biome, s.snow, max_flat(s), &trails),
                crate::blockers::any_within(site.pos.x, site.pos.y, s.foot + 0.2));
            // What claimed it: the blocked probe points over the footprint (debug aid for the log).
            let mut hits: Vec<String> = Vec::new();
            for k in 0..48 {
                let (a, r) = (k as f32 * 0.7, s.foot * (0.25 + 0.75 * ((k % 4) as f32 / 3.0)));
                let (px, pz) = (site.pos.x + a.cos() * r, site.pos.y + a.sin() * r);
                if crate::blockers::is_blocked(px, pz) {
                    hits.push(format!("{px:.1},{pz:.1}"));
                }
            }
            info!("stories_cold: {} blocked probes: {}", s.model, hits.join(" "));
            if seat(site.scene, 1, &mut others, &trails, false) == 0 {
                // Last resort: keep the planned spot when the intruder only grazes the outer rim
                // (a trunk or rock at the drift's edge) — a missing discoverable is worse.
                if ground_ok(site.pos.x, site.pos.y, s.foot, s.biome, s.snow, max_flat(s), &trails)
                    && !crate::blockers::any_within(site.pos.x, site.pos.y, s.foot * RIM_GRACE)
                {
                    warn!("stories_cold: {} at {:.1},{:.1} kept: only its rim is claimed", s.model, site.pos.x, site.pos.y);
                    site.clone()
                } else {
                    warn!("stories_cold: {} at {:.1},{:.1} was claimed and no other spot is free",
                        SCENES[site.scene].model, site.pos.x, site.pos.y);
                    continue;
                }
            } else {
            let moved = others.swap_remove(n);
            info!("stories_cold: {} at {:.1},{:.1} was claimed, moved to {:.1},{:.1}",
                SCENES[site.scene].model, site.pos.x, site.pos.y, moved.pos.x, moved.pos.y);
            moved
            }
        };
        let s = &SCENES[site.scene];
        let (y, tilt) =
            if s.trail { seat_tilted(site.pos.x, site.pos.y, s.foot) } else { (seat_y(site.pos.x, site.pos.y, s.foot), Quat::IDENTITY) };
        let tf = Transform::from_xyz(site.pos.x, y, site.pos.y).with_rotation(tilt * Quat::from_rotation_y(site.yaw));
        if let Some(e) = kit.spawn_static_with(commands, s.model, tf, range.clone()) {
            commands.entity(e).insert(BiomeEntity);
            // Instance k of a scene (in plan order) always gets its k-th name: saves match by name.
            let k = placed.iter().filter(|p| p.scene == site.scene).count();
            if let Some(name) = s.names.get(k) {
                crate::landmarks::attach_story(commands, e, name, s.lore);
            }
        }
        register_blockers(site.scene, site.pos, site.yaw);
        crate::blockers::reserve_visual(site.pos.x, site.pos.y, s.foot);
        info!("stories_cold: {} at {:.1},{:.1},{:.1} (snow cover {:.2})", s.model, site.pos.x, y, site.pos.y,
            crate::alpine::snow_cover(site.pos.x, site.pos.y));
        placed.push(site);
    }
    let count = |b: Biome| placed.iter().filter(|p| SCENES[p.scene].biome == b).count();
    info!("stories_cold: {} set-pieces ({} snow, {} rocky)", placed.len(), count(Biome::Snow), count(Biome::Rocky));
    *SITES.lock().unwrap() = placed;
}

/// Screenshot cameras for every placed SNOW site (`FOREST_SHOT_STORIES`, see `capture.rs`): a
/// near oblique from the scene's front (local -Z, the side its story faces) and a high one from the
/// opposite quarter (over the trees), both aimed ~1u above the site centre.
pub fn shot_cams() -> Vec<(String, Transform)> {
    let sites = SITES.lock().unwrap().clone();
    let mut out = Vec::new();
    let mut seen: Vec<usize> = Vec::new();
    for site in sites.iter().filter(|s| SCENES[s.scene].biome == Biome::Snow) {
        let k = seen.iter().filter(|&&s| s == site.scene).count();
        seen.push(site.scene);
        let y = seat_y(site.pos.x, site.pos.y, SCENES[site.scene].foot);
        let aim = Vec3::new(site.pos.x, y + 1.0, site.pos.y);
        let front = Vec3::new(-site.yaw.sin(), 0.0, -site.yaw.cos());
        let side = Vec3::new(front.z, 0.0, -front.x);
        let name = SCENES[site.scene].model.trim_start_matches("story_");
        if SCENES[site.scene].trail {
            // The convoy's bell (local 0, -1.45), seen side-on from the trail at eye height.
            let rot = Quat::from_rotation_y(site.yaw);
            let b = rot * Vec3::new(0.0, 0.0, -1.45);
            let bell = Vec3::new(site.pos.x + b.x, y + 0.75, site.pos.y + b.z);
            // 8u straight in from the trail side; 20u from ON the trail (its strip is clear of
            // trunks), up and down the pass.
            let along = Vec3::new(site.yaw.cos(), 0.0, -site.yaw.sin());
            for (tag, off) in [("eye8", front * 8.0), ("eye20a", front * 7.0 + along * 18.7),
                ("eye20b", front * 7.0 - along * 18.7)] {
                let e = Vec2::new(bell.x + off.x, bell.z + off.z);
                let gy = crate::worldmap::ground_at_world(e.x, e.y).unwrap_or(y);
                let eye = Vec3::new(e.x, gy + 1.7, e.y);
                info!("story cam {name}_{tag}: {:.1},{:.1},{:.1} -> {:.1},{:.1},{:.1}", eye.x, eye.y, eye.z, bell.x, bell.y, bell.z);
                out.push((format!("{name}_{tag}"), Transform::from_translation(eye).looking_at(bell, Vec3::Y)));
            }
        }
        for (tag, off) in [("near", front * 7.5 + side * 3.0 + Vec3::Y * 3.2), ("high", -front * 4.0 + side * 5.0 + Vec3::Y * 11.0)] {
            let eye = aim + off;
            info!("story cam {name}_{k}_{tag}: {:.1},{:.1},{:.1} -> {:.1},{:.1},{:.1}", eye.x, eye.y, eye.z, aim.x, aim.y, aim.z);
            out.push((format!("{name}_{k}_{tag}"), Transform::from_translation(eye).looking_at(aim, Vec3::Y)));
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The phase-4 plan seats every cold scene at least [`MIN_PER_SCENE`] times, each fully inside
    /// its own biome on flat legal ground, never crowding another story piece; and re-planning
    /// reproduces the very same sites.
    #[test]
    fn stories_cold_plan_seats_every_scene_in_its_biome() {
        let _g = crate::blockers::TEST_LOCK.lock().unwrap();
        crate::blockers::reset();
        crate::poi::plan_clearings();
        crate::vignettes::plan();
        crate::wayside::plan();
        plan();
        let first = SITES.lock().unwrap().clone();
        let trails = crate::worldmap::pass_trails_world();
        for site in &first {
            eprintln!("planned {} at {:.1},{:.1}", SCENES[site.scene].model, site.pos.x, site.pos.y);
        }
        for (scene, s) in SCENES.iter().enumerate() {
            let n = first.iter().filter(|p| p.scene == scene).count();
            assert!(n >= MIN_PER_SCENE.min(s.want), "{} seated only {n} times", s.model);
            assert!(n <= s.want, "{} seated {n} times", s.model);
        }
        for (i, a) in first.iter().enumerate() {
            let s = &SCENES[a.scene];
            assert!(ground_ok(a.pos.x, a.pos.y, s.foot, s.biome, s.snow, max_flat(s), &trails),
                "{} on illegal ground at {}", s.model, a.pos);
            if s.biome == Biome::Snow {
                assert!(crate::alpine::snow_cover(a.pos.x, a.pos.y) >= s.snow, "{} off the snow at {}", s.model, a.pos);
            }

            assert!(!crate::wayside::overlaps_planned(a.pos.x, a.pos.y, s.foot)
                && !crate::vignettes::overlaps_planned(a.pos.x, a.pos.y, s.foot),
                "{} on a wayside / vignette clearing at {}", s.model, a.pos);
            for b in &first[i + 1..] {
                assert!(a.pos.distance(b.pos) > s.foot + SCENES[b.scene].foot + MIN_GAP,
                    "{} crowds {}", s.model, SCENES[b.scene].model);
            }
        }
        crate::blockers::reset();
        crate::poi::plan_clearings();
        crate::vignettes::plan();
        crate::wayside::plan();
        plan();
        assert_eq!(*SITES.lock().unwrap(), first, "planning must be deterministic across rebuilds");
        crate::blockers::reset();
        crate::poi::reset_plan();
        crate::vignettes::reset_plan();
        crate::wayside::reset_plan();
        reset_plan();
    }

    /// Every SNOW story site gets placed: each one-off discoverable (convoy, hermitage, ring) exactly
    /// once — the convoy right beside a pass trail but off its painted strip, the one-offs spread
    /// apart — and each repeating first-colony scene at least [`MIN_PER_SCENE`] times; all on real
    /// snow. Names are unique across the table (saves match discoveries by name).
    #[test]
    fn every_snow_site_is_placed() {
        let _g = crate::blockers::TEST_LOCK.lock().unwrap();
        crate::blockers::reset();
        crate::poi::plan_clearings();
        crate::vignettes::plan();
        crate::wayside::plan();
        plan();
        let sites = SITES.lock().unwrap().clone();
        let trails = crate::worldmap::pass_trails_world();
        for (scene, s) in SCENES.iter().enumerate().filter(|(_, s)| s.biome == Biome::Snow) {
            let mine: Vec<&Site> = sites.iter().filter(|p| p.scene == scene).collect();
            if s.want == 1 {
                assert_eq!(mine.len(), 1, "{} not placed", s.model);
            } else {
                assert!(mine.len() >= MIN_PER_SCENE, "{} placed only {} times", s.model, mine.len());
            }
            for site in &mine {
                assert!(crate::alpine::snow_cover(site.pos.x, site.pos.y) >= s.snow, "{} off the snow", s.model);
                if s.trail {
                    let d = trails
                        .iter()
                        .flat_map(|t| t.windows(2).map(|w| seg_dist(site.pos, w[0], w[1])))
                        .fold(f32::INFINITY, f32::min);
                    assert!(d <= s.foot + TRAIL_HUG[TRAIL_HUG.len() - 1] + 0.1, "{} {d:.1}u off the trail", s.model);
                    assert!(!crate::roads::on_road(site.pos.x, site.pos.y), "{} on the trail strip", s.model);
                }
            }
        }
        let one_offs: Vec<&Site> = sites.iter().filter(|p| SCENES[p.scene].want == 1).collect();
        for (i, a) in one_offs.iter().enumerate() {
            for b in &one_offs[i + 1..] {
                assert!(a.pos.distance(b.pos) >= ONE_OFF_SPREAD, "one-off sites crowd each other");
            }
        }
        let mut names: Vec<&str> = SCENES.iter().flat_map(|s| s.names.iter().copied()).collect();
        assert!(SCENES.iter().all(|s| s.names.len() >= s.want && s.want <= PER_SCENE));
        let n = names.len();
        names.sort_unstable();
        names.dedup();
        assert_eq!(names.len(), n, "story site names must be unique (saves match by name)");
        crate::blockers::reset();
        crate::poi::reset_plan();
        crate::vignettes::reset_plan();
        crate::wayside::reset_plan();
        reset_plan();
    }

    #[test]
    fn rotated_scene_blockers_cover_their_masses() {
        let _g = crate::blockers::TEST_LOCK.lock().unwrap();
        crate::blockers::reset();
        let p = Vec2::new(40.0, 40.0);
        register_blockers(1, p, std::f32::consts::FRAC_PI_2);
        // The buried cabin's chimney (local -1.9, -0.6) must stay blocked with the model turned.
        let o = Quat::from_rotation_y(std::f32::consts::FRAC_PI_2) * Vec3::new(-1.9, 0.0, -0.6);
        assert!(crate::blockers::is_blocked(p.x + o.x, p.y + o.z));
        assert!(!crate::blockers::is_blocked(p.x + 3.5, p.y + 3.5));
        crate::blockers::reset();
    }
}
