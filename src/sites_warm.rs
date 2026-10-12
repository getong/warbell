//! **Desert and forest story sites** — one-off discoverables that give each warm biome its own
//! chapter of the island's history (`docs/superpowers/specs/2026-10-12-wyspa-opowiada-design.md`),
//! each with its own palette and models (`sites_warm.glb`, `tools/blender_forest/sites_warm.py`):
//!
//! - **Desert — "the others"** (ochre sandstone, turquoise glaze, salt, faded dye, brass, bone): the
//!   Trading Stones where orks and the Pasha's caravans weighed salt against iron (present day,
//!   abandoned); the first colony's Surveyors' Line — a Crown-marked cairn and stakes running toward
//!   the buried pyramid (turned to face it); the colony's sand-drowned southern outpost with its
//!   EMPTY bell-arch; the Old Ones' petroglyph wall; a caravan of the Pasha's freshly plundered on
//!   an ork war path; and Brother Anselm's journal page under a rock overhang beside his mule.
//! - **Forest — "the beginning"** (oak, moss, lichen, clay, roots): the colony's Bell-Casting Pit
//!   (mould shards, one with the castle bell's inscription reversed — NO bell); the charcoal
//!   burners' mound; the sawpit with the trunk half sawn; an Old Ones' pillar swallowed by a dead
//!   giant oak's roots; and the colony's first graves with a journal page in a hollow oak.
//!
//! Every site is a minor DISCOVERABLE (`landmarks::attach_story`: name + one lore line, chime, a
//! little gold, saved by name). The lore only seeds the twist (the bell, the Crown's old greed, the
//! orks as a people); it never states it. Anselm's pages follow the arc's chronology: forest =
//! arrival, the bell cast, the green folk coming to look; desert = the Governor's survey of the
//! pyramid and the peaceful salt-for-iron trade.
//!
//! Planned at build phase 4 after `stories_cold::plan` ([`plan`]): a deterministic jittered grid
//! per biome, accepted only on FLAT legal ground fully inside the biome (off roads, trails, water,
//! cliffs, camps, landmarks, the rival fort, the town and every other story piece), folded into
//! `poi::story_clearings` so the scatter keeps clear. Spawned at phase 32 ([`populate`]), re-sited
//! if a later phase claimed a spot. Forest sites get a few kit ferns round their rim.

use std::f32::consts::TAU;
use std::sync::Mutex;

use bevy::camera::visibility::VisibilityRange;
use bevy::prelude::*;

use crate::biome::{Biome, BiomeEntity};

/// One site: kit model, biome, visual radius, solids `(x, z, half w, half d, local yaw)` in model
/// space, instance count, discoverable names (by plan order), lore line.
struct Site {
    model: &'static str,
    biome: Biome,
    foot: f32,
    solids: &'static [(f32, f32, f32, f32, f32)],
    want: usize,
    names: &'static [&'static str],
    lore: &'static str,
}

const SITES_DEF: [Site; 11] = [
    Site { model: "site_trading_stones", biome: Biome::Desert, foot: 3.0,
        solids: &[(0.0, 0.0, 1.05, 0.6, 0.0), (-2.0, 0.4, 0.32, 0.2, 0.1), (2.0, 0.4, 0.32, 0.2, -0.1), (-1.35, -0.95, 0.35, 0.25, 0.3)],
        want: 1, names: &["The Trading Stones"],
        lore: "Salt on one side, iron on the other: orks and caravans weighed fair here for thirty years. The scales stand empty now." },
    Site { model: "site_survey_line", biome: Biome::Desert, foot: 3.0,
        solids: &[(0.0, -1.6, 0.55, 0.55, 0.0)],
        want: 1, names: &["The Surveyors' Line"],
        lore: "A Crown mark a century old, and stakes running toward the buried pyramid: someone measured it long before anyone dug." },
    Site { model: "site_drowned_outpost", biome: Biome::Desert, foot: 3.5,
        solids: &[(1.5, 0.3, 1.7, 1.2, 0.0), (-1.4, -0.4, 0.95, 0.3, 0.0), (-1.75, -1.55, 0.95, 0.95, 0.0)],
        want: 1, names: &["The Sand-Drowned Outpost"],
        lore: "The first colony's southern post: even this far from home they raised a bell-arch, and rang it every dusk." },
    Site { model: "site_glyph_wall", biome: Biome::Desert, foot: 3.0,
        solids: &[(0.1, 0.35, 2.3, 0.5, 0.0)],
        want: 1, names: &["The Old Ones' Wall"],
        lore: "Older than any caravan: tusked figures with their arms raised, facing a ring that spreads like a struck bell's voice." },
    Site { model: "site_looted_caravan", biome: Biome::Desert, foot: 3.0,
        solids: &[(0.0, 0.0, 1.1, 0.6, 0.15), (1.55, 0.95, 0.4, 0.35, 0.0)],
        want: 1, names: &["The Plundered Caravan"],
        lore: "The Pasha's cloth slashed, his jars smashed, ork arrows in the boards. The orks never raided here before; the ashes are three days old." },
    Site { model: "site_anselm_desert", biome: Biome::Desert, foot: 2.5,
        solids: &[(0.0, 0.9, 1.3, 0.6, 0.1), (-1.15, 0.6, 0.5, 0.5, 0.0)],
        want: 1, names: &["Anselm's Journal: The Survey Road"],
        lore: "\"The Governor will have the buried pyramid measured to the cubit. The green folk took our salt for their iron, and no one drew a blade.\"" },
    Site { model: "site_bell_pit", biome: Biome::Forest, foot: 3.2,
        solids: &[(-1.6, 0.9, 0.65, 0.65, 0.0), (0.55, -0.75, 0.42, 0.42, 0.0)],
        want: 1, names: &["The Bell-Casting Pit"],
        lore: "Shards of a broken mould. On one, reversed, the same words that are cast on the castle's war bell." },
    Site { model: "site_charcoal_kiln", biome: Biome::Forest, foot: 2.8,
        solids: &[(0.0, 0.25, 1.45, 1.3, 0.0), (2.25, -0.3, 0.42, 0.55, 0.0)],
        want: 1, names: &["The Charcoal Burners' Mound"],
        lore: "Charcoal for the colony's bell furnace. The last burn was never opened." },
    Site { model: "site_sawpit", biome: Biome::Forest, foot: 2.6,
        solids: &[(0.0, 0.0, 2.1, 0.35, 0.0)],
        want: 1, names: &["The Colony Sawpit"],
        lore: "Two sawyers squared oak here for the first bell frame. The saw is still in the cut." },
    Site { model: "site_rooted_pillar", biome: Biome::Forest, foot: 3.0,
        solids: &[(0.45, 0.85, 1.05, 1.05, 0.0), (-0.45, -0.4, 0.35, 0.3, 0.1)],
        want: 1, names: &["The Swallowed Pillar"],
        lore: "The oak lived three hundred years; the rings cut into the stone it swallowed are older still." },
    Site { model: "site_anselm_forest", biome: Biome::Forest, foot: 2.9,
        solids: &[(1.65, 0.5, 0.8, 0.8, 0.0)],
        want: 1, names: &["Anselm's Journal: The First Dusk"],
        lore: "\"We cast the bell by the royal pattern and rang it at the first dusk. The green folk came out of the trees to look, unarmed, curious as children.\"" },
];

const SURVEY: usize = 1;
/// Max terrain height spread under a footprint; the relaxed pass is the fallback for a scene the
/// strict pass couldn't seat (contact parts sink ~0.2-0.3u, the sand / moss skirts the rest).
const FLAT_DELTA: f32 = 0.45;
const FLAT_DELTA_RELAXED: f32 = 0.75;
const CAMP_KEEP: f32 = 7.0;
const TOWN_KEEP: f32 = 4.0;
const LANDMARK_KEEP: f32 = 14.0;
const TRAIL_KEEP: f32 = 3.0;
const ROAD_MARGIN: f32 = 3.0;
/// Any two of this module's sites stand this far apart past their footprints, so each biome's
/// discoverables spread over the region instead of clustering on its best ground.
const SPREAD: f32 = 26.0;
/// Gap to every other story piece past both footprints.
const MIN_GAP: f32 = 10.0;
/// The survey line stands within this band (past the keep-out) of the buried pyramid.
const SURVEY_BAND: f32 = 45.0;

#[derive(Clone, Debug, PartialEq)]
struct Placed {
    site: usize,
    pos: Vec2,
    yaw: f32,
}

static PLAN: Mutex<Vec<Placed>> = Mutex::new(Vec::new());

pub fn reset_plan() {
    PLAN.lock().unwrap().clear();
}

/// `(centre, visual radius)` of every planned site (folded into `poi::story_clearings`).
pub fn planned_footprints() -> Vec<(Vec2, f32)> {
    PLAN.lock().unwrap().iter().map(|s| (s.pos, SITES_DEF[s.site].foot)).collect()
}

/// Does a circle at `(x, z)` of radius `r` overlap a planned site?
pub fn overlaps_planned(x: f32, z: f32, r: f32) -> bool {
    let p = Vec2::new(x, z);
    PLAN.lock().unwrap().iter().any(|s| p.distance_squared(s.pos) < (SITES_DEF[s.site].foot + r + 0.35).powi(2))
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

/// The buried pyramid (the desert's grand landmark), if the island has one.
fn pyramid() -> Option<Vec2> {
    crate::ruins::landmark_sites().iter().find(|l| l.biome == Biome::Desert).map(|l| l.pos)
}

/// Ground + keep-out rules for a footprint of radius `foot` at `(x, z)`, all of it in `biome` with
/// at most `flat` height spread. Shared by the plan, the spawn re-check and the test.
fn ground_ok(x: f32, z: f32, foot: f32, biome: Biome, flat: f32, trails: &[Vec<Vec2>]) -> bool {
    let Some(y0) = crate::worldmap::ground_at_world(x, z) else { return false };
    if crate::worldmap::tile_biome_world(x, z) != Some(biome) || crate::worldmap::cliff_shelf_world(x, z) {
        return false;
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
                || crate::worldmap::cliff_shelf_world(px, pz)
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
    // An extra ring past the footprint: off the road (these are finds, not roadside pieces) and
    // still inside the biome (never straddling a seam).
    let r = foot + ROAD_MARGIN;
    for k in 0..12 {
        let a = k as f32 * (TAU / 12.0);
        let (px, pz) = (x + a.cos() * r, z + a.sin() * r);
        if crate::roads::on_road(px, pz) || crate::worldmap::tile_biome_world(px, pz) != Some(biome) {
            return false;
        }
    }
    let q = Vec2::new(x, z);
    !crate::bridges::near_bridge(x, z, foot + 0.5)
        && crate::ork_fortress::blight_edge_world(x, z) < -(foot + 4.0)
        && q.length() > crate::worldmap::SAFE_R * crate::worldmap::MAP_SCALE + TOWN_KEEP + foot
        && crate::camps::plan().iter().all(|c| c.centre.distance(q) > CAMP_KEEP + foot)
        && crate::ruins::landmark_sites().iter().all(|l| l.pos.distance(q) > LANDMARK_KEEP + foot)
        && trails.iter().all(|t| t.windows(2).all(|w| seg_dist(q, w[0], w[1]) > foot + TRAIL_KEEP))
}

/// Free of this plan's other sites, every other planned story piece and anything solid (plus, while
/// planning, every visual reservation).
fn clear_of_others(q: Vec2, site: usize, planned: &[Placed], visual: bool) -> bool {
    let foot = SITES_DEF[site].foot;
    planned.iter().all(|s| s.pos.distance(q) > foot + SITES_DEF[s.site].foot + SPREAD)
        && !crate::poi::story_clearings().overlaps(q.x, q.y, foot + MIN_GAP)
        && !(visual && crate::blockers::any_visual_within(q.x, q.y, foot + 0.3))
        && !crate::blockers::any_within(q.x, q.y, foot + 0.3)
}

/// Candidate spots for a site: a deterministic jittered grid over its biome, in a stable shuffled
/// order. The survey line instead walks outward from the pyramid's rim.
fn candidates(site: usize) -> Vec<Vec2> {
    let biome = SITES_DEF[site].biome;
    let step = 6.0;
    let (gx, gz) = (crate::worldmap::GX, crate::worldmap::GZ);
    let (cols, rows) = (crate::worldmap::COLS as f32, crate::worldmap::ROWS as f32);
    let mut rng = 0x5173_a11d ^ (site as u32).wrapping_mul(0x85eb_ca6b);
    let pyr = pyramid();
    let mut out: Vec<(f32, Vec2)> = Vec::new();
    let mut z = -gz + step * 0.5;
    while z < rows - gz {
        let mut x = -gx + step * 0.5;
        while x < cols - gx {
            let p = Vec2::new(x + (rng_next(&mut rng) - 0.5) * step * 0.8, z + (rng_next(&mut rng) - 0.5) * step * 0.8);
            let mut key = rng_next(&mut rng);
            if crate::worldmap::tile_biome_world(p.x, p.y) == Some(biome) {
                if site == SURVEY {
                    // Nearest the pyramid first (inside the band), the rest after.
                    match pyr {
                        Some(c) if c.distance(p) < LANDMARK_KEEP + SURVEY_BAND => key = c.distance(p) / 1000.0,
                        _ => key += 1.0,
                    }
                }
                out.push((key, p));
            }
            x += step;
        }
        z += step;
    }
    out.sort_by(|a, b| a.0.total_cmp(&b.0));
    out.into_iter().map(|(_, p)| p).collect()
}

/// The yaw a site is placed at: the survey line's +Z turned to the pyramid, the rest hashed.
fn site_yaw(site: usize, q: Vec2) -> f32 {
    if site == SURVEY {
        if let Some(c) = pyramid() {
            let d = c - q;
            return d.x.atan2(d.y);
        }
    }
    let mut s = q.x.to_bits() ^ q.y.to_bits().rotate_left(16) ^ (site as u32).wrapping_mul(0x9e37_79b9);
    rng_next(&mut s) * TAU
}

fn seat(site: usize, planned: &mut Vec<Placed>, trails: &[Vec<Vec2>], visual: bool) -> bool {
    let s = &SITES_DEF[site];
    let cands = candidates(site);
    for flat in [FLAT_DELTA, FLAT_DELTA_RELAXED] {
        for &q in &cands {
            if clear_of_others(q, site, planned, visual) && ground_ok(q.x, q.y, s.foot, s.biome, flat, trails) {
                planned.push(Placed { site, pos: q, yaw: site_yaw(site, q) });
                return true;
            }
        }
    }
    false
}

/// Build phase 4 (after `stories_cold::plan`): reserve every site so the scatter keeps clear.
pub fn plan() {
    reset_plan();
    let trails = crate::worldmap::pass_trails_world();
    let mut planned: Vec<Placed> = Vec::new();
    let max = SITES_DEF.iter().map(|s| s.want).max().unwrap_or(0);
    for round in 0..max {
        // The pyramid-anchored survey line first (its ground is the narrowest), then in order.
        let order = std::iter::once(SURVEY).chain((0..SITES_DEF.len()).filter(|&i| i != SURVEY));
        for site in order {
            if round < SITES_DEF[site].want && !seat(site, &mut planned, &trails, true) {
                warn!("sites_warm: no spot for {} #{}", SITES_DEF[site].model, round + 1);
            }
        }
    }
    for p in &planned {
        crate::blockers::reserve_visual(p.pos.x, p.pos.y, SITES_DEF[p.site].foot);
        info!("sites_warm: planned {} at {:.1},{:.1} yaw {:.2}", SITES_DEF[p.site].model, p.pos.x, p.pos.y, p.yaw);
    }
    info!("sites_warm: planned {} desert / forest story sites", planned.len());
    *PLAN.lock().unwrap() = planned;
}

fn register_blockers(site: usize, p: Vec2, yaw: f32) {
    let rot = Quat::from_rotation_y(yaw);
    for &(x, z, hw, hd, local_yaw) in SITES_DEF[site].solids {
        let o = rot * Vec3::new(x, 0.0, z);
        crate::blockers::add_obb(p.x + o.x, p.y + o.z, hw, hd, yaw + local_yaw);
    }
}

/// Seat height: the centre, sunk by part of the footprint's height spread (never below its lowest
/// point) so the downhill edge doesn't float.
fn seat_y(x: f32, z: f32, foot: f32) -> f32 {
    let Some(y0) = crate::worldmap::ground_at_world(x, z) else { return 0.0 };
    let (mut lo, mut hi) = (y0, y0);
    for k in 0..16 {
        let a = k as f32 * (TAU / 16.0);
        if let Some(y) = crate::worldmap::ground_at_world(x + a.cos() * foot, z + a.sin() * foot) {
            lo = lo.min(y);
            hi = hi.max(y);
        }
    }
    (y0 - 0.6 * (hi - lo)).max(lo) - 0.04
}

/// Build phase 32 (after `stories_cold::populate`): spawn each planned site, re-siting any a later
/// phase claimed.
pub fn populate(commands: &mut Commands) {
    let Some(kit) = crate::realforest::get().filter(|k| k.has(SITES_DEF[0].model)) else {
        warn!("sites_warm: sites_warm.glb not in the kit — no desert / forest story sites");
        return;
    };
    let range = VisibilityRange { start_margin: 0.0..0.0, end_margin: 120.0..140.0, use_aabb: true };
    let near = VisibilityRange { start_margin: 0.0..0.0, end_margin: 50.0..60.0, use_aabb: true };
    let trails = crate::worldmap::pass_trails_world();
    let planned = PLAN.lock().unwrap().clone();
    let mut placed: Vec<Placed> = Vec::with_capacity(planned.len());
    for (i, p) in planned.iter().enumerate() {
        let s = &SITES_DEF[p.site];
        let free = ground_ok(p.pos.x, p.pos.y, s.foot, s.biome, FLAT_DELTA_RELAXED, &trails)
            && !crate::blockers::any_within(p.pos.x, p.pos.y, s.foot + 0.2);
        let p = if free {
            p.clone()
        } else {
            let mut others: Vec<Placed> = placed.iter().chain(&planned[i + 1..]).cloned().collect();
            let n = others.len();
            if seat(p.site, &mut others, &trails, false) {
                let moved = others.swap_remove(n);
                info!("sites_warm: {} at {:.1},{:.1} was claimed, moved to {:.1},{:.1}", s.model, p.pos.x, p.pos.y, moved.pos.x, moved.pos.y);
                moved
            } else if !crate::blockers::any_within(p.pos.x, p.pos.y, s.foot * 0.75) {
                warn!("sites_warm: {} at {:.1},{:.1} kept: only its rim is claimed", s.model, p.pos.x, p.pos.y);
                p.clone()
            } else {
                warn!("sites_warm: {} at {:.1},{:.1} was claimed and no other spot is free", s.model, p.pos.x, p.pos.y);
                continue;
            }
        };
        let y = seat_y(p.pos.x, p.pos.y, s.foot);
        let tf = Transform::from_xyz(p.pos.x, y, p.pos.y).with_rotation(Quat::from_rotation_y(p.yaw));
        if let Some(e) = kit.spawn_static_with(commands, s.model, tf, range.clone()) {
            commands.entity(e).insert(BiomeEntity);
            let k = placed.iter().filter(|q| q.site == p.site).count();
            if let Some(name) = s.names.get(k) {
                crate::landmarks::attach_story(commands, e, name, s.lore);
            }
        }
        if s.biome == Biome::Forest {
            dress_forest_rim(commands, kit, &p, near.clone());
        }
        register_blockers(p.site, p.pos, p.yaw);
        crate::blockers::reserve_visual(p.pos.x, p.pos.y, s.foot);
        info!("sites_warm: {} at {:.1},{:.1},{:.1} yaw {:.2}", s.model, p.pos.x, y, p.pos.y, p.yaw);
        placed.push(p);
    }
    info!("sites_warm: {} desert / forest story sites placed", placed.len());
    *PLAN.lock().unwrap() = placed;
}

/// Ferns and a fallen branch or two round a forest site's rim, so the glade the scatter left
/// reads as overgrown, not mown (the scatter keeps its cover out of every story clearing).
fn dress_forest_rim(commands: &mut Commands, kit: &crate::realforest::Kit, p: &Placed, range: VisibilityRange) {
    let foot = SITES_DEF[p.site].foot;
    let mut rng = p.pos.x.to_bits() ^ p.pos.y.to_bits().rotate_left(9);
    for k in 0..14 {
        let a = k as f32 * (TAU / 14.0) + rng_next(&mut rng) * 0.4;
        let r = foot * (0.85 + 0.35 * rng_next(&mut rng));
        let (x, z) = (p.pos.x + a.cos() * r, p.pos.y + a.sin() * r);
        if crate::roads::on_road(x, z) || crate::blockers::is_blocked(x, z) {
            continue;
        }
        let Some(y) = crate::worldmap::ground_at_world(x, z) else { continue };
        let roll = rng_next(&mut rng);
        let name = if roll < 0.8 { ["fern_a", "fern_b", "fern_c"][(k * 7 + 1) % 3] } else { "branches_a" };
        let s = 0.8 + 0.5 * rng_next(&mut rng);
        let tf = Transform::from_xyz(x, y - 0.02, z)
            .with_rotation(Quat::from_rotation_y(rng_next(&mut rng) * TAU))
            .with_scale(Vec3::splat(s));
        if let Some(e) = kit.spawn_static_with(commands, name, tf, range.clone()) {
            commands.entity(e).insert(BiomeEntity);
        }
    }
}

/// Screenshot cameras for every placed site (`FOREST_SHOT_STORIES=sites`, see `capture.rs`): a
/// close oblique from the site's front (local -Z) and a medium high one from the opposite quarter.
pub fn shot_cams() -> Vec<(String, Transform)> {
    let sites = PLAN.lock().unwrap().clone();
    let mut out = Vec::new();
    for p in &sites {
        let s = &SITES_DEF[p.site];
        let y = seat_y(p.pos.x, p.pos.y, s.foot);
        let aim = Vec3::new(p.pos.x, y + 0.8, p.pos.y);
        let front = Vec3::new(-p.yaw.sin(), 0.0, -p.yaw.cos());
        let side = Vec3::new(front.z, 0.0, -front.x);
        let name = s.model.trim_start_matches("site_");
        for (tag, off) in [("near", front * 6.0 + side * 2.5 + Vec3::Y * 2.2), ("mid", front * 10.0 - side * 9.0 + Vec3::Y * 7.0)] {
            let eye = aim + off;
            info!("site cam {name}_{tag}: {:.1},{:.1},{:.1} -> {:.1},{:.1},{:.1}", eye.x, eye.y, eye.z, aim.x, aim.y, aim.z);
            out.push((format!("{name}_{tag}"), Transform::from_translation(eye).looking_at(aim, Vec3::Y)));
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Every site is seated once, inside its own biome on legal ground, spread apart and clear of
    /// every other story piece; the survey line faces the pyramid; re-planning is deterministic.
    #[test]
    fn sites_warm_plan_seats_every_site() {
        let _g = crate::blockers::TEST_LOCK.lock().unwrap();
        crate::blockers::reset();
        crate::poi::plan_clearings();
        crate::stories_warm::plan();
        crate::vignettes::plan();
        crate::wayside::plan();
        crate::stories_cold::plan();
        plan();
        let first = PLAN.lock().unwrap().clone();
        let trails = crate::worldmap::pass_trails_world();
        for p in &first {
            eprintln!("planned {} at {:.1},{:.1} yaw {:.2}", SITES_DEF[p.site].model, p.pos.x, p.pos.y, p.yaw);
        }
        for (i, s) in SITES_DEF.iter().enumerate() {
            let n = first.iter().filter(|p| p.site == i).count();
            assert_eq!(n, s.want, "{} seated {n} times", s.model);
        }
        for (i, a) in first.iter().enumerate() {
            let s = &SITES_DEF[a.site];
            assert!(ground_ok(a.pos.x, a.pos.y, s.foot, s.biome, FLAT_DELTA_RELAXED, &trails), "{} on illegal ground at {}", s.model, a.pos);
            assert!(!crate::stories_warm::overlaps_planned(a.pos.x, a.pos.y, s.foot)
                && !crate::stories_cold::overlaps_planned(a.pos.x, a.pos.y, s.foot)
                && !crate::wayside::overlaps_planned(a.pos.x, a.pos.y, s.foot),
                "{} on another story clearing at {}", s.model, a.pos);
            for b in &first[i + 1..] {
                assert!(a.pos.distance(b.pos) > s.foot + SITES_DEF[b.site].foot + SPREAD, "{} crowds {}", s.model, SITES_DEF[b.site].model);
            }
        }
        if let (Some(c), Some(sv)) = (pyramid(), first.iter().find(|p| p.site == SURVEY)) {
            let to = (c - sv.pos).normalize();
            let fwd = Vec2::new(sv.yaw.sin(), sv.yaw.cos());
            assert!(to.dot(fwd) > 0.99, "survey line does not face the pyramid");
            eprintln!("survey line {:.1} from the pyramid", c.distance(sv.pos));
        }
        crate::blockers::reset();
        crate::poi::plan_clearings();
        crate::stories_warm::plan();
        crate::vignettes::plan();
        crate::wayside::plan();
        crate::stories_cold::plan();
        plan();
        assert_eq!(*PLAN.lock().unwrap(), first, "planning must be deterministic");
        crate::blockers::reset();
        reset_plan();
        crate::stories_cold::reset_plan();
        crate::stories_warm::reset_plan();
        crate::poi::reset_plan();
    }
}
