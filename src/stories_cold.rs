//! **Cold-biome story set-pieces** — environmental storytelling inside the Snow and Rocky biomes
//! (RDR2 / Skyrim style: no text, no interaction, a scene that explains itself). The roadside
//! pieces (`poi.rs`) tell the road's stories; these sit OUT in the wild, where a traveller stumbles
//! on them:
//!
//! - **Snow** — a lost expedition camp (collapsed tent under a drift, a sled with lashed crates, a
//!   cold fire ring, skis still planted upright); an avalanche-buried cabin (beams jutting from the
//!   mound, the stone chimney still standing); a frozen battlefield memorial (a cairn topped with a
//!   helmet, a tattered banner, broken shields and spears in the snow).
//! - **Rocky** — an abandoned mine head (timber headframe over an open shaft, a tipped ore cart at
//!   the end of its rail run); a rockfall that crushed a wagon on the track; a half-cut monolith in
//!   a small quarry, the masons' tools dropped where they stood.
//!
//! Models: `stories_cold.glb` (`tools/blender_forest/stories_cold.py`), real scale, base y=0.
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

/// One story scene: its kit model, the biome it belongs to, the visual radius it reserves, and its
/// solid masses as model-local oriented boxes `(x, z, half width, half depth, local yaw)`.
struct Scene {
    model: &'static str,
    biome: Biome,
    foot: f32,
    solids: &'static [(f32, f32, f32, f32, f32)],
}

const SCENES: [Scene; 6] = [
    // The drift + collapsed tent, the sled with its crates, the planted skis.
    Scene { model: "story_lost_camp", biome: Biome::Snow, foot: 2.6,
        solids: &[(-0.6, 0.2, 1.1, 1.0, 0.0), (1.15, -0.75, 1.0, 0.45, 0.35), (2.02, 0.35, 0.25, 0.3, 0.0)] },
    // The avalanche mound over the cabin + the standing chimney.
    Scene { model: "story_buried_cabin", biome: Biome::Snow, foot: 3.0,
        solids: &[(0.1, 0.0, 1.9, 1.4, 0.0), (-1.9, -0.6, 0.45, 0.45, 0.0)] },
    // The cairn and the banner pole's foot.
    Scene { model: "story_frozen_memorial", biome: Biome::Snow, foot: 2.3,
        solids: &[(0.0, 0.0, 0.6, 0.6, 0.0), (0.6, -0.4, 0.08, 0.08, 0.0)] },
    // Headframe legs over the shaft (the shaft itself is inside the legs), the tipped cart, the spoil heap.
    Scene { model: "story_mine_head", biome: Biome::Rocky, foot: 3.1,
        solids: &[(0.0, 0.0, 1.15, 1.0, 0.0), (2.15, 0.85, 0.55, 0.45, 0.2), (-1.9, 1.2, 0.75, 0.6, 0.0)] },
    // The crushed wagon under its boulders + the third boulder.
    Scene { model: "story_rockfall_wagon", biome: Biome::Rocky, foot: 2.9,
        solids: &[(0.0, 0.0, 1.45, 0.8, 0.0), (1.55, -0.95, 0.55, 0.5, 0.0), (-1.8, -0.85, 0.4, 0.35, 0.0)] },
    // The bedrock shelf with the half-cut block, and the monolith blank on its rollers.
    Scene { model: "story_quarry", biome: Biome::Rocky, foot: 2.8,
        solids: &[(-0.6, -0.4, 1.35, 0.95, 0.08), (1.25, 0.9, 1.2, 0.45, -0.6)] },
];

/// Instances planned per scene (each in its own biome, spread apart).
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
const MIN_GAP: f32 = 12.0;
/// Rocky scenes: clearance from a pass trail's centreline beyond the footprint.
const TRAIL_KEEP: f32 = 3.0;
/// A snow scene stands on real snow (`alpine::snow_cover`, height-driven) — never on the snow
/// biome's green apron, where a buried cabin reads as a white blob on grass. Up on the massif the
/// flat ground is the pass VALLEY floors beside the trails and the col, so snow scenes skip the
/// rocky rules that ban the whole cliffy shelf / pass corridor and only keep [`SNOW_ROAD_KEEP`] off
/// the painted trail strip itself.
const SNOW_COVER: f32 = 0.6;
const SNOW_ROAD_KEEP: f32 = 2.0;
/// Last-resort flatness for snow scenes: the model is then sunk by part of the spread
/// ([`seat_y`]) and its drift skirts swallow the uphill side.
const FLAT_DELTA_SNOW_MAX: f32 = 1.0;

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
fn seat_y(x: f32, z: f32, foot: f32) -> f32 {
    match footprint_heights(x, z, foot) {
        Some((y0, lo, hi)) => (y0 - 0.6 * (hi - lo)).max(lo) - 0.04,
        None => crate::worldmap::ground_at_world(x, z).unwrap_or(0.0) - 0.04,
    }
}

/// Ground + keep-out rules for a footprint of radius `foot` centred at `(x, z)`, all of it inside
/// `biome` and no higher spread than `flat`. Shared by the plan, the spawn re-check and the test.
/// Snow scenes additionally need [`SNOW_COVER`] and use the valley-floor road rule (see there).
fn ground_ok(x: f32, z: f32, foot: f32, biome: Biome, flat: f32, trails: &[Vec<Vec2>]) -> bool {
    let Some(y0) = crate::worldmap::ground_at_world(x, z) else { return false };
    if crate::worldmap::tile_biome_world(x, z) != Some(biome) {
        return false;
    }
    let snow = biome == Biome::Snow;
    if snow && crate::alpine::snow_cover(x, z) < SNOW_COVER {
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
                || (snow && crate::alpine::snow_cover(px, pz) < SNOW_COVER)
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
    planned.iter().all(|s| {
        let d = s.pos.distance(q);
        d > foot + SCENES[s.scene].foot + MIN_GAP && (s.scene != scene || d > SAME_SCENE_SPACING)
    }) && !crate::poi::story_clearings().overlaps(q.x, q.y, foot + 1.0)
        && !(visual && crate::blockers::any_visual_within(q.x, q.y, foot + 0.3))
        && !crate::blockers::any_within(q.x, q.y, foot + 0.3)
}

/// Candidate spots for a biome: a deterministic jittered grid over the whole map, in a stable
/// shuffled order (so the instances spread across the region instead of piling up in one corner).
fn candidates(biome: Biome, seed: u32) -> Vec<Vec2> {
    const STEP: f32 = 9.0;
    let (gx, gz) = (crate::worldmap::GX, crate::worldmap::GZ);
    let (cols, rows) = (crate::worldmap::COLS as f32, crate::worldmap::ROWS as f32);
    let mut rng = seed;
    let mut out: Vec<(f32, Vec2)> = Vec::new();
    let mut z = -gz + STEP * 0.5;
    while z < rows - gz {
        let mut x = -gx + STEP * 0.5;
        while x < cols - gx {
            let p = Vec2::new(x + (rng_next(&mut rng) - 0.5) * STEP * 0.8, z + (rng_next(&mut rng) - 0.5) * STEP * 0.8);
            let key = rng_next(&mut rng);
            if crate::worldmap::tile_biome_world(p.x, p.y) == Some(biome) {
                out.push((key, p));
            }
            x += STEP;
        }
        z += STEP;
    }
    out.sort_by(|a, b| a.0.total_cmp(&b.0));
    out.into_iter().map(|(_, p)| p).collect()
}

/// A stable per-site yaw hashed from the scene and spot.
fn site_yaw(scene: usize, q: Vec2) -> f32 {
    let mut s = q.x.to_bits() ^ q.y.to_bits().rotate_left(16) ^ (scene as u32).wrapping_mul(0x9e37_79b9);
    rng_next(&mut s) * TAU
}

/// Seat up to `want` instances of `scene`, appending to `planned`. Strict flatness first, then the
/// relaxed pass only while the scene is short of [`MIN_PER_SCENE`].
fn seat(scene: usize, want: usize, planned: &mut Vec<Site>, trails: &[Vec<Vec2>], visual: bool) -> usize {
    let s = &SCENES[scene];
    let mut cands = candidates(s.biome, 0x51c0_1d00 ^ (scene as u32).wrapping_mul(0x85eb_ca6b));
    if s.biome == Biome::Snow {
        // Snowiest first (stable: equal cover keeps the shuffled order).
        let cover = |p: &Vec2| crate::alpine::snow_cover(p.x, p.y);
        cands.sort_by(|a, b| cover(b).total_cmp(&cover(a)));
    }
    let mut got = 0;
    let min = MIN_PER_SCENE.min(want);
    let snow_max = if s.biome == Biome::Snow { FLAT_DELTA_SNOW_MAX } else { FLAT_DELTA_RELAXED };
    let passes = [(FLAT_DELTA, want), (FLAT_DELTA_RELAXED, min), (snow_max, min)];
    for (flat, need) in passes {
        for q in &cands {
            if got >= need {
                break;
            }
            if clear_of_others(*q, scene, planned, visual) && ground_ok(q.x, q.y, s.foot, s.biome, flat, trails) {
                planned.push(Site { scene, pos: *q, yaw: site_yaw(scene, *q) });
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
        for scene in 0..SCENES.len() {
            if planned.iter().filter(|s| s.scene == scene).count() == round {
                seat(scene, 1, &mut planned, &trails, true);
            }
        }
    }
    for (scene, s) in SCENES.iter().enumerate() {
        let n = planned.iter().filter(|p| p.scene == scene).count();
        if n < MIN_PER_SCENE {
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
fn max_flat(biome: Biome) -> f32 {
    if biome == Biome::Snow { FLAT_DELTA_SNOW_MAX } else { FLAT_DELTA_RELAXED }
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
    ground_ok(site.pos.x, site.pos.y, s.foot, s.biome, max_flat(s.biome), trails)
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
                site.pos.y, ground_ok(site.pos.x, site.pos.y, s.foot, s.biome, max_flat(s.biome), &trails),
                crate::blockers::any_within(site.pos.x, site.pos.y, s.foot + 0.2));
            if seat(site.scene, 1, &mut others, &trails, false) == 0 {
                warn!("stories_cold: {} at {:.1},{:.1} was claimed and no other spot is free",
                    SCENES[site.scene].model, site.pos.x, site.pos.y);
                continue;
            }
            let moved = others.swap_remove(n);
            info!("stories_cold: {} at {:.1},{:.1} was claimed, moved to {:.1},{:.1}",
                SCENES[site.scene].model, site.pos.x, site.pos.y, moved.pos.x, moved.pos.y);
            moved
        };
        let s = &SCENES[site.scene];
        let y = seat_y(site.pos.x, site.pos.y, s.foot);
        let tf = Transform::from_xyz(site.pos.x, y, site.pos.y).with_rotation(Quat::from_rotation_y(site.yaw));
        if let Some(e) = kit.spawn_static_with(commands, s.model, tf, range.clone()) {
            commands.entity(e).insert(BiomeEntity);
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
            assert!(n >= MIN_PER_SCENE, "{} seated only {n} times", s.model);
            assert!(n <= PER_SCENE, "{} seated {n} times", s.model);
        }
        for (i, a) in first.iter().enumerate() {
            let s = &SCENES[a.scene];
            assert!(ground_ok(a.pos.x, a.pos.y, s.foot, s.biome, max_flat(s.biome), &trails),
                "{} on illegal ground at {}", s.model, a.pos);
            if s.biome == Biome::Snow {
                assert!(crate::alpine::snow_cover(a.pos.x, a.pos.y) >= SNOW_COVER, "{} off the snow at {}", s.model, a.pos);
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
