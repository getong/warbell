//! **Warm-biome story scenes** — environmental storytelling set-pieces (RDR2 / Skyrim style: no
//! text, no interaction, a scene that explains itself) placed INSIDE the desert, swamp and forest,
//! away from the roads (the roadside layer is `poi.rs`):
//!
//! - Desert: an overturned caravan wagon with its ox's skeleton and the spilled cargo; the ribcage
//!   of a giant beast arching out of a dune; a dead oasis (dry well, dead palms, water skins).
//! - Swamp: a half-sunken punt by a collapsed stilt hut; a drowned shrine (tilted idol, candles).
//! - Forest: a hunter's camp (lean-to, hide rack, antlers); an abandoned woodcutters' site.
//!
//! Models: `stories_warm.glb` (tools/blender_forest/stories_warm.py), loaded with the realistic kit;
//! without the kit nothing spawns (the low-poly fallback world keeps its roadside POIs only).
//!
//! Planned at build phase 4 right after `poi::plan_clearings` ([`plan`]): a deterministic jittered
//! grid over the island is filtered per scene by biome (centre + a ring past the footprint must all
//! be that biome), the shared POI ground rules (`poi::site_ok`: flat, dry, off roads / plots / camps
//! / landmarks, no bridge) plus an extra road margin, and the visual reservations; each scene then
//! takes 2–3 well-spaced spots. The spots are folded into `poi::story_clearings` /
//! `poi::overlaps_planned_clearing`, so scatter and every later placer leave them free. Spawned at
//! phase 32 ([`populate`]), re-sited if a later phase claimed a spot after all.

use std::f32::consts::TAU;
use std::sync::Mutex;

use bevy::camera::visibility::VisibilityRange;
use bevy::prelude::*;

use crate::biome::{Biome, BiomeEntity};

/// One story scene: kit model, home biome, reserved visual radius, wanted instance count, and its
/// solid masses as model-local oriented boxes `(x, z, half width, half depth, local yaw)`.
struct Scene {
    model: &'static str,
    biome: Biome,
    foot: f32,
    count: usize,
    boxes: &'static [(f32, f32, f32, f32, f32)],
}

// story_caravan / story_boat are capped at one here: the Lost Caravan and Sunken Wreck vignettes
// (`vignettes.rs`) draw the same models, and no story model appears more than twice on the island.
const SCENES: [Scene; 7] = [
    Scene { model: "story_caravan", biome: Biome::Desert, foot: 3.0, count: 1, boxes: &[(-0.36, -0.15, 1.2, 0.45, 0.25)] },
    Scene { model: "story_ribs", biome: Biome::Desert, foot: 3.5, count: 2, boxes: &[(0.0, 0.0, 1.7, 1.2, 0.0)] },
    Scene {
        model: "story_oasis",
        biome: Biome::Desert,
        foot: 2.9,
        count: 2,
        boxes: &[(0.2, -0.2, 0.66, 0.66, 0.0), (-1.45, -1.0, 0.2, 0.2, 0.0), (1.6, 1.1, 0.15, 0.15, 0.0)],
    },
    Scene {
        model: "story_boat",
        biome: Biome::Swamp,
        foot: 2.8,
        count: 1,
        boxes: &[(0.9, 0.5, 1.25, 0.5, 0.45), (-1.0, -0.8, 0.8, 0.7, 0.0), (1.25, -1.5, 0.75, 0.08, 0.0)],
    },
    Scene {
        model: "story_shrine",
        biome: Biome::Swamp,
        foot: 1.6,
        count: 3,
        boxes: &[(0.0, -0.35, 0.3, 0.22, 0.12), (0.05, 0.25, 0.31, 0.2, 0.1)],
    },
    Scene {
        model: "story_hunter",
        biome: Biome::Forest,
        foot: 2.3,
        count: 2,
        boxes: &[(-0.6, -0.95, 0.95, 0.5, 0.0), (1.25, -0.55, 0.7, 0.32, 0.0), (1.3, 0.95, 0.26, 0.26, 0.0)],
    },
    Scene {
        model: "story_woodcut",
        biome: Biome::Forest,
        foot: 2.4,
        count: 2,
        boxes: &[(-0.5, -0.95, 1.3, 0.45, 0.0), (0.95, 0.55, 0.75, 0.35, -0.3), (-0.65, 0.8, 0.33, 0.33, 0.0)],
    },
];

/// Two instances of the same scene stand at least this far apart (they should feel like finds).
const SAME_KIND_SPACING: f32 = 70.0;
/// Gap between the footprints of any two story scenes (this module's and the roadside POIs').
const SCENE_GAP: f32 = 8.0;
/// Extra keep-off from the roads past the footprint (these are off-road finds, not roadside pieces).
const ROAD_MARGIN: f32 = 4.0;
/// Candidate grid pitch (world units) — jittered per cell.
const GRID: f32 = 5.0;

#[derive(Clone, Debug, PartialEq)]
struct Site {
    kind: usize,
    pos: Vec2,
    yaw: f32,
}

static SITES: Mutex<Vec<Site>> = Mutex::new(Vec::new());

pub fn reset_plan() {
    SITES.lock().unwrap().clear();
}

/// `(centre, visual radius)` of every planned scene — folded into `poi::story_clearings`.
pub fn planned_footprints() -> Vec<(Vec2, f32)> {
    SITES.lock().unwrap().iter().map(|s| (s.pos, SCENES[s.kind].foot)).collect()
}

/// Does a circle at `(x, z)` of radius `r` overlap a planned scene? (`poi::overlaps_planned_clearing`.)
pub fn overlaps_planned(x: f32, z: f32, r: f32) -> bool {
    let p = Vec2::new(x, z);
    SITES.lock().unwrap().iter().any(|s| p.distance_squared(s.pos) < (SCENES[s.kind].foot + r + 0.35).powi(2))
}

fn hash01(mut s: u32) -> f32 {
    s = s.wrapping_add(0x6d2b_79f5);
    let mut t = s;
    t = (t ^ (t >> 15)).wrapping_mul(t | 1);
    t ^= t.wrapping_add((t ^ (t >> 7)).wrapping_mul(t | 61));
    ((t ^ (t >> 14)) as f32) / 4_294_967_296.0
}

fn cell_hash(ix: i32, iz: i32, salt: u32) -> u32 {
    (ix as u32).wrapping_mul(0x9e37_79b9) ^ (iz as u32).wrapping_mul(0x85eb_ca6b) ^ salt.wrapping_mul(0xc2b2_ae35)
}

/// The scene's biome all over its footprint and a ring beyond it (so it never straddles a seam),
/// and for the swamp scenes, well clear of the Blight (Gnashfang Hold's own mire dressing).
fn biome_fits(kind: usize, q: Vec2) -> bool {
    let sc = &SCENES[kind];
    let want = Some(sc.biome);
    if crate::worldmap::tile_biome_world(q.x, q.y) != want {
        return false;
    }
    let r = sc.foot + 2.0;
    for k in 0..10 {
        let a = k as f32 * (TAU / 10.0);
        if crate::worldmap::tile_biome_world(q.x + a.cos() * r, q.y + a.sin() * r) != want {
            return false;
        }
    }
    sc.biome != Biome::Swamp || crate::ork_fortress::blight_edge_world(q.x, q.y) < -(sc.foot + 6.0)
}

/// Ground rules on top of the biome: the shared POI site test (flat, dry, off roads / plots /
/// camps / fort / landmarks / bridges), clear of settlements, an extra road margin, and (when
/// `visual`) no reserved visual footprint — `false` only at spawn, where the site's own
/// reservation is there by design.
fn ground_fits(kind: usize, q: Vec2, visual: bool) -> bool {
    let foot = SCENES[kind].foot;
    if visual && crate::blockers::any_visual_within(q.x, q.y, foot + 0.2) {
        return false;
    }
    if !crate::poi::site_ok(q.x, q.y, foot) || !crate::poi::clear_of_settlements(q, foot) {
        return false;
    }
    let r = foot + ROAD_MARGIN;
    (0..12).all(|k| {
        let a = k as f32 * (TAU / 12.0);
        !crate::roads::on_road(q.x + a.cos() * r, q.y + a.sin() * r)
    })
}

/// Search the island for the next spot of `kind`, spaced from `taken` (and same-kind instances).
/// Deterministic: a jittered grid, candidates ordered by a per-cell hash.
fn find_site(kind: usize, taken: &[Site], visual: bool) -> Option<Site> {
    let sc = &SCENES[kind];
    let (x0, x1) = (-crate::worldmap::GX, crate::worldmap::GX);
    let (z0, z1) = (-crate::worldmap::GZ, crate::worldmap::ROWS as f32 - crate::worldmap::GZ);
    let (nx, nz) = (((x1 - x0) / GRID) as i32, ((z1 - z0) / GRID) as i32);
    let mut cands: Vec<(f32, Vec2, u32)> = Vec::new();
    for iz in 0..nz {
        for ix in 0..nx {
            let h = cell_hash(ix, iz, kind as u32 + 17);
            let q = Vec2::new(
                x0 + (ix as f32 + 0.15 + 0.7 * hash01(h)) * GRID,
                z0 + (iz as f32 + 0.15 + 0.7 * hash01(h ^ 0x51ed_270b)) * GRID,
            );
            if !biome_fits(kind, q) {
                continue;
            }
            let mut score = hash01(h ^ 0x2545_f491);
            // The punt belongs at the water's edge: prefer spots with open water just past the rim.
            if sc.model == "story_boat" {
                let near_water = (0..12).any(|k| {
                    let a = k as f32 * (TAU / 12.0);
                    let r = sc.foot + 2.5;
                    let (px, pz) = (q.x + a.cos() * r, q.y + a.sin() * r);
                    crate::worldmap::is_pool_world(px, pz) || crate::worldmap::is_river_world(px, pz)
                });
                if near_water {
                    score -= 1.0;
                }
            }
            cands.push((score, q, h));
        }
    }
    cands.sort_by(|a, b| a.0.total_cmp(&b.0).then(a.1.x.total_cmp(&b.1.x)).then(a.1.y.total_cmp(&b.1.y)));
    for (_, q, h) in cands {
        let spaced = taken.iter().all(|s| {
            let gap = if s.kind == kind { SAME_KIND_SPACING } else { sc.foot + SCENES[s.kind].foot + SCENE_GAP };
            s.pos.distance(q) >= gap
        });
        if spaced && ground_fits(kind, q, visual) {
            return Some(Site { kind, pos: q, yaw: hash01(h ^ 0x68e3_1da4) * TAU });
        }
    }
    None
}

/// Build phase 4 (after `poi::plan_clearings`, before any scatter): reserve every scene's spots.
pub fn plan() {
    reset_plan();
    let mut planned: Vec<Site> = Vec::new();
    // Round-robin so a cramped biome can't let its first scene take every good spot.
    let max = SCENES.iter().map(|s| s.count).max().unwrap_or(0);
    for round in 0..max {
        for kind in 0..SCENES.len() {
            if round >= SCENES[kind].count {
                continue;
            }
            match find_site(kind, &planned, true) {
                Some(site) => {
                    crate::blockers::reserve_visual(site.pos.x, site.pos.y, SCENES[kind].foot);
                    info!("stories_warm: planned {} at {:.1},{:.1}", SCENES[kind].model, site.pos.x, site.pos.y);
                    planned.push(site);
                }
                None => warn!("stories_warm: no spot for {} #{}", SCENES[kind].model, round + 1),
            }
        }
    }
    info!("stories_warm: planned {} scenes", planned.len());
    *SITES.lock().unwrap() = planned;
}

/// Register each solid mass in model-local space, rotated with the model.
fn register_blockers(kind: usize, p: Vec2, yaw: f32) {
    let rot = Quat::from_rotation_y(yaw);
    for &(x, z, hw, hd, local_yaw) in SCENES[kind].boxes {
        let o = rot * Vec3::new(x, 0.0, z);
        crate::blockers::add_obb(p.x + o.x, p.y + o.z, hw, hd, yaw + local_yaw);
    }
}

/// Build phase 32: spawn every planned scene (re-sited if a later phase claimed its spot).
pub fn populate(commands: &mut Commands) {
    let Some(kit) = crate::realforest::get().filter(|k| k.has(SCENES[0].model)) else {
        warn!("stories_warm: realistic kit / stories_warm.glb not loaded — no story scenes");
        return;
    };
    let range = VisibilityRange { start_margin: 0.0..0.0, end_margin: 110.0..130.0, use_aabb: true };
    let planned = SITES.lock().unwrap().clone();
    let mut placed: Vec<Site> = Vec::with_capacity(planned.len());
    for (i, site) in planned.iter().enumerate() {
        let foot = SCENES[site.kind].foot;
        let free = ground_fits(site.kind, site.pos, false) && !crate::blockers::any_within(site.pos.x, site.pos.y, foot + 0.2);
        let site = if free {
            site.clone()
        } else {
            let others: Vec<Site> = placed.iter().chain(&planned[i + 1..]).cloned().collect();
            match find_site(site.kind, &others, true) {
                Some(moved) => {
                    info!("stories_warm: {} at {:.1},{:.1} was claimed, moved to {:.1},{:.1}",
                        SCENES[site.kind].model, site.pos.x, site.pos.y, moved.pos.x, moved.pos.y);
                    moved
                }
                None => {
                    warn!("stories_warm: {} at {:.1},{:.1} was claimed, no other spot", SCENES[site.kind].model, site.pos.x, site.pos.y);
                    continue;
                }
            }
        };
        let q = site.pos;
        let y = crate::worldmap::ground_at_world(q.x, q.y).unwrap_or(0.0) - 0.03;
        let tf = Transform::from_xyz(q.x, y, q.y).with_rotation(Quat::from_rotation_y(site.yaw));
        let Some(e) = kit.spawn_static_with(commands, SCENES[site.kind].model, tf, range.clone()) else { continue };
        commands.entity(e).insert(BiomeEntity);
        register_blockers(site.kind, q, site.yaw);
        crate::blockers::reserve_visual(q.x, q.y, foot);
        info!("stories_warm: {} at {:.1},{:.1} (y {:.2}, yaw {:.2})", SCENES[site.kind].model, q.x, q.y, y, site.yaw);
        placed.push(site);
    }
    info!("stories_warm: {} story scenes placed", placed.len());
    *SITES.lock().unwrap() = placed;
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Every scene gets at least two spots, each in its own biome on legal ground, nothing
    /// crowding anything (roadside POIs included), and the plan is deterministic.
    #[test]
    fn plan_seats_every_scene_in_its_biome() {
        let _g = crate::blockers::TEST_LOCK.lock().unwrap();
        crate::blockers::reset();
        crate::poi::plan_clearings();
        plan();
        let first = SITES.lock().unwrap().clone();
        for s in &first {
            let y = crate::worldmap::ground_at_world(s.pos.x, s.pos.y).unwrap_or(f32::NAN);
            eprintln!("planned {} at {:.1},{:.1} ground {:.2} yaw {:.2}", SCENES[s.kind].model, s.pos.x, s.pos.y, y, s.yaw);
        }
        for (kind, sc) in SCENES.iter().enumerate() {
            let n = first.iter().filter(|s| s.kind == kind).count();
            // Every scene seats as often as it asks (capped at 2 — a vignette model appears at most twice).
            assert!(n >= sc.count.min(2), "{} seated only {n} times", sc.model);
        }
        for (i, s) in first.iter().enumerate() {
            let sc = &SCENES[s.kind];
            assert!(biome_fits(s.kind, s.pos), "{} outside its biome at {}", sc.model, s.pos);
            assert!(ground_fits(s.kind, s.pos, false), "{} on illegal ground at {}", sc.model, s.pos);
            for o in &first[i + 1..] {
                assert!(s.pos.distance(o.pos) > sc.foot + SCENES[o.kind].foot + 2.0, "{} crowds {}", sc.model, SCENES[o.kind].model);
            }
        }
        crate::blockers::reset();
        crate::poi::plan_clearings();
        plan();
        assert_eq!(*SITES.lock().unwrap(), first, "planning must be deterministic");
        crate::blockers::reset();
        reset_plan();
        crate::poi::reset_plan();
    }

    #[test]
    fn rotated_blockers_follow_the_model() {
        let _g = crate::blockers::TEST_LOCK.lock().unwrap();
        crate::blockers::reset();
        // The woodcutters' log stack (local -0.5, -0.95) turned a quarter: lands at (+x local z).
        let p = Vec2::new(40.0, 40.0);
        let yaw = std::f32::consts::FRAC_PI_2;
        register_blockers(6, p, yaw);
        let o = Quat::from_rotation_y(yaw) * Vec3::new(-0.5, 0.0, -0.95);
        assert!(crate::blockers::is_blocked(p.x + o.x, p.y + o.z));
        // The open ground between the stump and the sawhorse stays walkable.
        let mid = Quat::from_rotation_y(yaw) * Vec3::new(0.2, 0.0, 1.6);
        assert!(!crate::blockers::is_blocked(p.x + mid.x, p.y + mid.z));
        crate::blockers::reset();
    }
}
