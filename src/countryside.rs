//! **The countryside** (Oct 2026, player: "the meadow round the castle is enormous and empty — you
//! run over nothing for too long"). The land between the castle meadow and the five biomes used to
//! be one flat, uniform lawn: a dead-flat disc ≈110u round the keep (`worldmap::relief_ease` fixed
//! that half) with nothing on it but grass tufts. This module farms it, KCD2-style — a lived-in
//! medieval countryside rather than a park:
//!
//! * **two farmsteads** ([`FARMS`]) — house, small barn, shed, hayrick, well, coop, garden beds,
//!   woodpile, beehives, a cart, a trough, a split-rail horse paddock with grazing horses
//!   ([`Grazer`]), trodden yard mud ([`ground_wear`]) and a cart track to the road network
//!   (`roads::build_curves`); the ground under each is levelled (`worldmap::relief_ease`);
//! * **field boundaries** — hedgerows (kit bushes with the odd standard oak) and dry-stone walls
//!   (courses of small kit stones) along hand-laid lines ([`HEDGES`], [`WALLS`]);
//! * **wayside** — a shrine at a crossroads, a broken-down cart in the verge;
//! * **groves and lone old trees** on a jittered cell grid (never on the gate lanes or right under
//!   the walls, so the sight-lines from the walls stay open);
//! * **the biome foreland** — scrub thickening toward each biome's edge (oak and hazel before the
//!   wood, pines and boulders under the crags and the snow massif, stones and dead snags before the
//!   dunes, alder scrub before the marsh): with `worldmap::foreland_tint` the grass leans into the
//!   next biome before its ecotone line, so the transition reads as a gradient;
//! * **meadow life** — wildflower drifts and tall-grass sweeps (merged ground cover), haystacks and
//!   bales on the mown hay meadows.
//!
//! **Placement.** Everything is planned at world-build phase 4 ([`plan`], before the scatter, so the
//! meadow cover keeps out of the yards — `poi::story_clearings` / `realforest::keep_clear`) and
//! spawned at phase 30 ([`populate`]). The procedural layers are seeded per grid cell with
//! mulberry32, so the countryside is the same every run. Every spot is re-checked against roads,
//! fields, build plots, the castle, camps, story clearings, water and slope ([`spot_ok`]).
//!
//! **Perf.** Small props (hedge bushes, wall stones, scrub rocks, flowers) go through the realforest
//! chunk merge (`realforest::Chunks` — one mesh per 16u chunk and material, streamed near the
//! camera, meshopt far twin); trees use the kit LOD pair + impostor path (`Kit::attach_tree`);
//! buildings are single kit pieces with a fade range. Static `StandardMaterial` meshes drop their
//! sun shadow by distance automatically (`shadow_lod.rs`).
//!
//! Everything is a [`BiomeEntity`] (world rebuild owns the lifetime); nothing here is run-state, so
//! there is nothing to save or reset.

use std::f32::consts::{FRAC_PI_2, PI, TAU};
use std::sync::Mutex;

use bevy::prelude::*;

use crate::biome::BiomeEntity;
use crate::realforest::Tier;

// ── Hand-laid geography ─────────────────────────────────────────────────────────────────────────

/// The farmsteads: yard centre (world XZ) and facing (yaw; the house fronts and the yard open
/// toward local +Z, where the cart track arrives). Read by `worldmap::relief_ease` (the ground is
/// levelled under them) and `roads::build_curves` (their tracks) — so these are fixed constants,
/// not part of the phase-4 plan.
/// Sites picked with the `farm_scan` test (`FARM_SCAN=1`): the open meadow is cut up by roads,
/// the street village and the planned story clearings, and these are the pockets where a yard fits.
pub const FARMS: [(Vec2, f32); 2] = [
    // The farmstead: the open pocket south-east of the castle, between the south road, the wood and
    // the marsh; the gate faces west to the road, the orchard east, the paddock north.
    (Vec2::new(28.0, 66.0), -FRAC_PI_2),
    // A woodland-edge croft west of the south fields, under the forest; gate north-east.
    (Vec2::new(-64.0, 52.0), 2.36),
];
/// Index of the small croft in [`FARMS`] (house, shed, garden, beehives — no barn or paddock).
const CROFT: usize = 1;
/// Radius (world) levelled flat round a yard centre (farm, croft); the knolls return 12u further.
const FARM_FLAT: [f32; 2] = [17.0, 11.0];

/// Where a farm's cart track meets its yard (the gate, local +Z).
pub fn farm_gate(i: usize) -> Vec2 {
    let (c, yaw) = FARMS[i];
    c + rot2(yaw, Vec2::new(0.0, if i == CROFT { 8.0 } else { 12.5 }))
}

/// 0 on a farmstead's levelled yard, easing to 1 by `FARM_FLAT + 12` (multiplies the knolls).
pub fn farm_flatten(wx: f32, wz: f32) -> f32 {
    let p = Vec2::new(wx, wz);
    let mut k = 1.0f32;
    for (i, (c, _)) in FARMS.iter().enumerate() {
        let t = ((c.distance(p) - FARM_FLAT[i]) / 12.0).clamp(0.0, 1.0);
        k = k.min(t * t * (3.0 - 2.0 * t));
    }
    k
}

/// Hedgerow lines (world XZ polylines): field boundaries round the farms and along the old tracks.
const HEDGES: &[&[Vec2]] = &[
    // The farmstead: its east boundary beyond the orchard, and the head of its strip fields.
    &[Vec2::new(50.0, 46.0), Vec2::new(52.0, 62.0), Vec2::new(49.0, 80.0)],
    &[Vec2::new(10.0, 49.5), Vec2::new(26.0, 49.0), Vec2::new(40.0, 50.5)],
    // The south road's east verge, from the fields to the farm track.
    &[Vec2::new(5.5, 42.0), Vec2::new(6.0, 52.0), Vec2::new(5.0, 64.0)],
    // The croft's garth, and the old boundary running down to the south fields.
    &[Vec2::new(-74.0, 40.0), Vec2::new(-77.0, 52.0), Vec2::new(-73.0, 64.0)],
    &[Vec2::new(-48.0, 40.0), Vec2::new(-34.0, 44.0), Vec2::new(-22.0, 43.0)],
];
/// Dry-stone walls (world XZ polylines): pasture walls on the stonier ground near the crags and
/// under the snow massif's foot.
const WALLS: &[&[Vec2]] = &[
    &[Vec2::new(46.0, 14.0), Vec2::new(54.0, 4.0), Vec2::new(57.0, -8.0)],
    &[Vec2::new(-58.0, -26.0), Vec2::new(-46.0, -33.0), Vec2::new(-34.0, -36.0)],
    &[Vec2::new(-74.0, -8.0), Vec2::new(-66.0, -16.0)],
];
/// The crossroads shrine and the broken cart (spot, yaw); searched outward until a clear spot.
const SHRINE: (Vec2, f32) = (Vec2::new(-6.5, 50.0), FRAC_PI_2);
const BROKEN_CART: (Vec2, f32) = (Vec2::new(-40.0, -42.0), 2.2);

// ── The plan ─────────────────────────────────────────────────────────────────────────────────────

/// A single kit model spawned as its own entity (buildings, haystacks, the cart, the shrine).
#[derive(Clone, Debug)]
struct Piece {
    name: &'static str,
    pos: Vec2,
    yaw: f32,
    /// Collider half-extents in the piece frame (zero = walk-through).
    solid: Vec2,
    /// Extra roll (radians, about local Z) for the broken cart's lean.
    roll: f32,
    sink: f32,
    far: f32,
}

/// A kit tree on its own gameplay entity (sway, chop, LOD pair + impostor).
#[derive(Clone, Debug)]
struct TreeSpot {
    name: &'static str,
    pos: Vec2,
    scale: f32,
    yaw: f32,
}

/// A small kit prop for the realforest chunk merge.
#[derive(Clone, Debug)]
struct PropSpot {
    name: &'static str,
    pos: Vec2,
    yaw: f32,
    scale: f32,
    tier: Tier,
    /// Fraction of the model's height pressed into the ground.
    sink: f32,
    /// Register a round blocker of this radius (0 = walk-through).
    solid: f32,
}

#[derive(Clone, Debug, Default)]
struct Plan {
    pieces: Vec<Piece>,
    trees: Vec<TreeSpot>,
    props: Vec<PropSpot>,
    /// Reserved footprints (yards, groves) the scatter keeps clear of.
    foot: Vec<(Vec2, f32)>,
    /// Horse paddocks: (centre, half extents, yaw).
    paddocks: Vec<(Vec2, Vec2, f32)>,
}

static PLAN: Mutex<Option<Plan>> = Mutex::new(None);

pub fn reset_plan() {
    *PLAN.lock().expect("countryside plan poisoned") = None;
}

/// Footprints the biome scatter and cover keep clear of (farm yards, paddocks).
pub fn planned_footprints() -> Vec<(Vec2, f32)> {
    PLAN.lock().expect("countryside plan poisoned").as_ref().map(|p| p.foot.clone()).unwrap_or_default()
}

/// Does a circle at `(x, z)` of radius `r` overlap a planned farm footprint?
pub fn overlaps_planned(x: f32, z: f32, r: f32) -> bool {
    let p = Vec2::new(x, z);
    PLAN.lock()
        .expect("countryside plan poisoned")
        .as_ref()
        .is_some_and(|plan| plan.foot.iter().any(|(c, f)| p.distance_squared(*c) < (f + r).powi(2)))
}

fn rot2(yaw: f32, v: Vec2) -> Vec2 {
    // `Quat::from_rotation_y(yaw)` applied to (v.x, 0, v.y).
    let (s, c) = yaw.sin_cos();
    Vec2::new(c * v.x + s * v.y, -s * v.x + c * v.y)
}

/// mulberry32 → [0, 1).
fn rng(state: &mut u32) -> f32 {
    *state = state.wrapping_add(0x6d2b_79f5);
    let mut t = *state;
    t = (t ^ (t >> 15)).wrapping_mul(t | 1);
    t ^= t.wrapping_add((t ^ (t >> 7)).wrapping_mul(t | 61));
    ((t ^ (t >> 14)) as f32) / 4_294_967_296.0
}

fn cell_seed(ix: i32, iz: i32, salt: u32) -> u32 {
    (ix as u32).wrapping_mul(0x9E37_79B1) ^ (iz as u32).wrapping_mul(0x85EB_CA77) ^ salt
}

/// Can a footprint of radius `foot` stand at `(x, z)`? Grass (or, with `forest_ok`, the frontier
/// woods), slope within `tol`, off roads / fields / plots / the castle / camps / the village /
/// every planned set-piece / water.
fn spot_ok(x: f32, z: f32, foot: f32, tol: f32, forest_ok: bool, clear: &crate::poi::StoryClearings) -> bool {
    use crate::worldmap as wm;
    let Some(y0) = wm::ground_at_world(x, z) else { return false };
    if clear.overlaps(x, z, foot)
        || crate::bridges::near_bridge(x, z, foot + 0.5)
        || crate::castle::village_keep_clear(x, z, foot)
        || crate::blockers::any_visual_within(x, z, foot)
        || crate::rival::near_fort(x, z)
    {
        return false;
    }
    let (mut lo, mut hi) = (y0, y0);
    for k in 0..=8 {
        let a = k as f32 * (TAU / 8.0);
        let (px, pz) = if k == 8 { (x, z) } else { (x + a.cos() * foot, z + a.sin() * foot) };
        let Some(y) = wm::ground_at_world(px, pz) else { return false };
        lo = lo.min(y);
        hi = hi.max(y);
        let ground_ok = wm::is_grass_world(px, pz) || (forest_ok && matches!(wm::tile_biome_world(px, pz), Some(crate::biome::Biome::Forest)));
        if !ground_ok
            || crate::roads::on_road(px, pz)
            || crate::castle_ground::in_field(px, pz)
            || crate::town::near_build_plot(px, pz)
            || crate::castle::in_footprint(px, pz)
            || crate::camps::in_clearing(px, pz)
            || crate::ruins::near_landmark_visual_footprint(px, pz)
            || wm::cliff_shelf_world(px, pz)
            || wm::is_pool_world(px, pz)
            || wm::is_river_world(px, pz)
            || wm::over_inland_water_world(px, pz)
        {
            return false;
        }
    }
    hi - lo <= tol
}

/// At least `d` world units past the castle walls (`worldmap::castle_ring_world`) — keeps the
/// ground right under the walls open (fields of fire, the gate lanes, the meadow sites).
fn past_walls(x: f32, z: f32, d: f32) -> bool {
    crate::worldmap::castle_ring_world(x, z) > d
}

/// Plan the countryside (world-build phase 4, after the other planners). Deterministic.
pub fn plan() {
    if crate::worldmap::is_arena() {
        return;
    }
    let clear = crate::poi::story_clearings();
    let mut p = Plan::default();
    plan_farms(&mut p, &clear);
    plan_lines(&mut p, &clear);
    plan_wayside(&mut p, &clear);
    plan_trees(&mut p, &clear);
    plan_foreland(&mut p, &clear);
    plan_meadow_life(&mut p, &clear);
    info!(
        "countryside: {} pieces, {} trees, {} props, {} paddocks",
        p.pieces.len(),
        p.trees.len(),
        p.props.len(),
        p.paddocks.len()
    );
    *PLAN.lock().expect("countryside plan poisoned") = Some(p);
}

/// One farmstead's buildings and yard furniture, in the yard frame (local +Z = the gate side).
/// (piece, local XZ, local yaw, solid?) — colliders come from the piece's measured extents.
const FARM_LAYOUT: [(&str, Vec2, f32, bool); 17] = [
    ("town_house_b", Vec2::new(-6.5, -4.0), 0.0, true),
    ("town_farm", Vec2::new(5.5, -4.5), 0.0, true),
    ("town_shed", Vec2::new(-13.0, 0.5), FRAC_PI_2, true),
    ("town_hayrick", Vec2::new(11.5, 1.5), 0.4, true),
    ("yard_hay", Vec2::new(9.0, 3.6), 1.1, false),
    ("yard_well", Vec2::new(-0.5, 3.5), 0.3, true),
    ("town_coop", Vec2::new(-2.5, -0.4), PI, false),
    ("town_woodpile", Vec2::new(-11.5, -4.5), FRAC_PI_2, true),
    ("town_garden", Vec2::new(-9.0, 7.5), 0.0, false),
    ("town_garden", Vec2::new(-5.4, 7.7), 0.05, false),
    ("town_dung", Vec2::new(10.5, -1.6), 0.0, false),
    ("yard_cart", Vec2::new(3.5, 6.0), 0.65, true),
    ("decor_trough", Vec2::new(13.6, 5.8), FRAC_PI_2, false),
    ("meadow_beehive", Vec2::new(-14.6, 6.2), 0.2, false),
    ("meadow_beehive", Vec2::new(-15.8, 7.4), 1.0, false),
    ("meadow_beehive", Vec2::new(-14.2, 8.3), 2.3, false),
    ("town_outhouse", Vec2::new(-10.0, -8.6), 0.0, false),
];
/// The croft: a cottage with its lean-to, garden beds, woodpile, beehives and a hay stook.
const CROFT_LAYOUT: [(&str, Vec2, f32, bool); 9] = [
    ("town_house_c", Vec2::new(-1.5, -3.0), 0.0, true),
    ("town_shed", Vec2::new(4.5, -2.5), -FRAC_PI_2, true),
    ("town_woodpile", Vec2::new(-5.6, -3.4), FRAC_PI_2, true),
    ("town_garden", Vec2::new(-3.5, 3.6), 0.1, false),
    ("town_garden", Vec2::new(0.2, 3.9), -0.05, false),
    ("yard_hay", Vec2::new(5.0, 2.5), 0.8, false),
    ("meadow_beehive", Vec2::new(-6.8, 1.6), 0.4, false),
    ("meadow_beehive", Vec2::new(-7.6, 3.0), 1.7, false),
    ("decor_trough", Vec2::new(3.2, 5.0), 0.2, false),
];
/// The farmstead's horse paddock (local centre, half extents) — split-rail fence + horses. Behind
/// the barn end of the yard, past the orchard (the road runs north of the yard, the marsh south).
const PADDOCK: (Vec2, Vec2) = (Vec2::new(6.0, -11.5), Vec2::new(5.0, 3.5));

/// Measured kit footprints (XZ half extents) of the farm pieces — from the GLBs, so the colliders
/// and the plan's checks work before the kit has loaded (and in tests).
fn piece_half(name: &str) -> Vec2 {
    match name {
        "town_house_b" => Vec2::new(4.0, 3.0),
        "town_house_c" => Vec2::new(2.3, 2.4),
        "town_farm" => Vec2::new(2.9, 1.8),
        "town_shed" => Vec2::new(1.4, 1.1),
        "town_hayrick" => Vec2::new(1.6, 1.45),
        "yard_well" => Vec2::new(1.0, 1.0),
        "town_woodpile" => Vec2::new(1.1, 0.8),
        "yard_cart" => Vec2::new(1.05, 0.7),
        _ => Vec2::splat(0.8),
    }
}

fn plan_farms(p: &mut Plan, clear: &crate::poi::StoryClearings) {
    for (fi, &(c, yaw)) in FARMS.iter().enumerate() {
        let croft = fi == CROFT;
        if !spot_ok(c.x, c.y, if croft { 4.0 } else { 6.0 }, 1.2, false, clear) {
            warn!("countryside: farmstead {fi} at {c:?} is not clear ground — skipped");
            continue;
        }
        let layout: &[(&str, Vec2, f32, bool)] = if croft { &CROFT_LAYOUT } else { &FARM_LAYOUT };
        for &(name, local, ly, solid) in layout {
            let pos = c + rot2(yaw, local);
            if crate::roads::on_road(pos.x, pos.y) || crate::town::near_build_plot(pos.x, pos.y) {
                continue;
            }
            let half = piece_half(name);
            p.pieces.push(Piece {
                name,
                pos,
                yaw: yaw + ly,
                solid: if solid { half * 0.85 } else { Vec2::ZERO },
                roll: 0.0,
                sink: 0.03,
                far: 230.0,
            });
            crate::blockers::reserve_visual(pos.x, pos.y, half.max_element());
        }
        if croft {
            p.foot.push((c, 9.0));
            continue;
        }
        // The orchard behind the house: two rows of apple trees.
        for (k, local) in [(-16.0, -12.0), (-9.0, -13.5), (-2.0, -12.5), (-13.0, -19.0), (-6.0, -19.5)].into_iter().enumerate() {
            let pos = c + rot2(yaw, Vec2::new(local.0, local.1));
            if spot_ok(pos.x, pos.y, 1.0, 0.8, false, clear) {
                let mut s = cell_seed(fi as i32, k as i32, 0xA991E);
                p.trees.push(TreeSpot {
                    name: if rng(&mut s) < 0.5 { "apple_a_lod0" } else { "apple_b_lod0" },
                    pos,
                    scale: 0.8 + rng(&mut s) * 0.25,
                    yaw: rng(&mut s) * TAU,
                });
            }
        }
        p.foot.push((c, 15.0));
        let (pc, ph) = PADDOCK;
        let centre = c + rot2(yaw, pc);
        if spot_ok(centre.x, centre.y, ph.min_element(), 1.0, false, clear) {
            p.paddocks.push((centre, ph, yaw));
            p.foot.push((centre, ph.max_element() + 1.0));
            crate::blockers::reserve_visual(centre.x, centre.y, ph.max_element());
        } else {
            warn!("countryside: farmstead {fi}'s paddock at {centre:?} is not clear — no horses");
        }
    }
}

/// Points every `step` along a polyline, with the local direction.
fn along(line: &[Vec2], step: f32) -> Vec<(Vec2, Vec2)> {
    let mut out = Vec::new();
    for w in line.windows(2) {
        let (a, b) = (w[0], w[1]);
        let len = a.distance(b);
        let dir = (b - a) / len.max(1e-3);
        let n = (len / step).ceil().max(1.0) as usize;
        for i in 0..n {
            out.push((a + dir * (len * i as f32 / n as f32), dir));
        }
    }
    out
}

fn plan_lines(p: &mut Plan, clear: &crate::poi::StoryClearings) {
    const BUSHES: [&str; 2] = ["bush_a", "bush_b"];
    const OAKS: [&str; 3] = ["oak_a_lod0", "oak_b_lod0", "oak_c_lod0"];
    for (li, line) in HEDGES.iter().enumerate() {
        let mut s = cell_seed(li as i32, 7, 0x4ED6E);
        for (k, (pt, dir)) in along(line, 1.25).into_iter().enumerate() {
            let side = Vec2::new(-dir.y, dir.x) * (rng(&mut s) - 0.5) * 0.7;
            let pos = pt + side;
            // A gap now and then (a field gate), and none across a road.
            if rng(&mut s) < 0.06 || !spot_ok(pos.x, pos.y, 0.6, 0.9, true, clear) {
                continue;
            }
            if k % 11 == 5 && rng(&mut s) < 0.75 {
                p.trees.push(TreeSpot { name: OAKS[k % 3], pos, scale: 0.85 + rng(&mut s) * 0.35, yaw: rng(&mut s) * TAU });
                continue;
            }
            p.props.push(PropSpot {
                name: BUSHES[(rng(&mut s) * 2.0) as usize % 2],
                pos,
                yaw: rng(&mut s) * TAU,
                scale: 1.05 + rng(&mut s) * 0.55,
                tier: Tier::Props,
                sink: 0.08,
                solid: 0.0,
            });
        }
    }
    const STONES: [&str; 5] = ["rock_02_a", "rock_02_b", "rock_02_c", "rock_02_d", "rock_02_f"];
    for (li, line) in WALLS.iter().enumerate() {
        let mut s = cell_seed(li as i32, 9, 0x57A11);
        for (pt, dir) in along(line, 0.62) {
            if !spot_ok(pt.x, pt.y, 0.5, 0.9, false, clear) {
                continue;
            }
            let yaw = dir.x.atan2(dir.y) + FRAC_PI_2;
            // Two courses: a footing of bigger stones, a capping row of smaller ones.
            for (course, sc, sink) in [(0, 1.3, 0.25), (1, 1.0, -0.6)] {
                if course == 1 && rng(&mut s) < 0.18 {
                    continue; // a tumbled gap in the cap
                }
                let jitter = Vec2::new(-dir.y, dir.x) * (rng(&mut s) - 0.5) * 0.12;
                p.props.push(PropSpot {
                    name: STONES[(rng(&mut s) * STONES.len() as f32) as usize % STONES.len()],
                    pos: pt + jitter,
                    yaw: yaw + (rng(&mut s) - 0.5) * 0.5,
                    scale: sc * (0.85 + rng(&mut s) * 0.3),
                    tier: Tier::Props,
                    sink,
                    solid: 0.0,
                });
            }
        }
    }
}

/// Colliders along the dry-stone walls (spawn time — a knee-high wall you walk round, not through).
/// One thin box per stretch of standing wall, split wherever the plan dropped the stones (a road,
/// a field, the ends), so the gaps stay passable.
fn wall_colliders(plan: &Plan) {
    let stones: Vec<Vec2> = plan.props.iter().filter(|p| p.name.starts_with("rock_02") && p.sink > 0.0).map(|p| p.pos).collect();
    for line in WALLS {
        let mut run: Vec<Vec2> = Vec::new();
        let flush = |run: &mut Vec<Vec2>| {
            if run.len() >= 2 {
                let (a, b) = (run[0], run[run.len() - 1]);
                let c = (a + b) * 0.5;
                let d = b - a;
                crate::blockers::add_obb(c.x, c.y, d.length() * 0.5 + 0.3, 0.35, (-d.y).atan2(d.x));
            }
            run.clear();
        };
        for (pt, _) in along(line, 0.62) {
            if stones.iter().any(|s| s.distance(pt) < 0.2) {
                run.push(pt);
            } else {
                flush(&mut run);
            }
        }
        flush(&mut run);
    }
}

/// Search outward from `want` for the nearest clear spot (rings of 8, up to `reach`).
fn find_near(want: Vec2, foot: f32, reach: f32, clear: &crate::poi::StoryClearings) -> Option<Vec2> {
    let mut r = 0.0;
    while r <= reach {
        let n = if r == 0.0 { 1 } else { 10 };
        for k in 0..n {
            let a = k as f32 / n as f32 * TAU;
            let q = want + Vec2::new(a.cos(), a.sin()) * r;
            if spot_ok(q.x, q.y, foot, 0.5, false, clear) {
                return Some(q);
            }
        }
        r += 1.5;
    }
    None
}

fn plan_wayside(p: &mut Plan, clear: &crate::poi::StoryClearings) {
    if let Some(q) = find_near(SHRINE.0, 1.0, 12.0, clear) {
        p.pieces.push(Piece { name: "decor_shrine", pos: q, yaw: SHRINE.1, solid: Vec2::new(0.6, 0.55), roll: 0.0, sink: 0.02, far: 160.0 });
        p.foot.push((q, 2.0));
        crate::blockers::reserve_visual(q.x, q.y, 1.0);
    }
    if let Some(q) = find_near(BROKEN_CART.0, 1.6, 14.0, clear) {
        // Lost a wheel and settled on its axle: a lean and a sink on one side.
        p.pieces.push(Piece { name: "yard_cart", pos: q, yaw: BROKEN_CART.1, solid: Vec2::new(1.0, 0.65), roll: 0.28, sink: 0.12, far: 160.0 });
        p.props.push(PropSpot { name: "meadow_bale", pos: q + Vec2::new(1.9, 0.6), yaw: 0.4, scale: 1.0, tier: Tier::Props, sink: 0.03, solid: 0.0 });
        crate::blockers::reserve_visual(q.x, q.y, 1.6);
    }
}

/// Groves and lone old trees on a jittered 26u grid over the open country.
fn plan_trees(p: &mut Plan, clear: &crate::poi::StoryClearings) {
    const CELL: f32 = 26.0;
    const KINDS: [&str; 6] = ["oak_a_lod0", "oak_b_lod0", "oak_c_lod0", "beech_a_lod0", "beech_b_lod0", "oak_b_lod0"];
    for iz in -9..=9 {
        for ix in -9..=9 {
            let mut s = cell_seed(ix, iz, 0x6E07E);
            let c = Vec2::new((ix as f32 + 0.2 + rng(&mut s) * 0.6) * CELL, (iz as f32 + 0.2 + rng(&mut s) * 0.6) * CELL);
            let roll = rng(&mut s);
            // Keep the near ground under the walls open (lanes of fire, the meadow sites); groves
            // only once well out, lone trees a little nearer.
            if !crate::worldmap::is_grass_world(c.x, c.y) || !past_walls(c.x, c.y, 16.0) || crate::roads::near_road(c.x, c.y, 4.0) {
                continue;
            }
            if roll < 0.22 && past_walls(c.x, c.y, 30.0) {
                // A grove: 4–8 trees round a little clearing-less knot, with a few bushes.
                let n = 4 + (rng(&mut s) * 5.0) as usize;
                let mut placed = 0;
                for _ in 0..n * 3 {
                    if placed >= n {
                        break;
                    }
                    let a = rng(&mut s) * TAU;
                    let r = 1.5 + rng(&mut s) * 7.0;
                    let q = c + Vec2::new(a.cos(), a.sin()) * r;
                    if !spot_ok(q.x, q.y, 0.9, 1.4, true, clear) || p.trees.iter().any(|t| t.pos.distance(q) < 3.6) {
                        continue;
                    }
                    p.trees.push(TreeSpot { name: KINDS[(rng(&mut s) * 6.0) as usize % 6], pos: q, scale: 0.8 + rng(&mut s) * 0.45, yaw: rng(&mut s) * TAU });
                    placed += 1;
                }
                for _ in 0..3 {
                    let a = rng(&mut s) * TAU;
                    let q = c + Vec2::new(a.cos(), a.sin()) * (6.0 + rng(&mut s) * 3.5);
                    if spot_ok(q.x, q.y, 0.7, 1.2, true, clear) {
                        p.props.push(PropSpot { name: if rng(&mut s) < 0.5 { "bush_a" } else { "bush_b" }, pos: q, yaw: rng(&mut s) * TAU, scale: 1.0 + rng(&mut s) * 0.5, tier: Tier::Props, sink: 0.08, solid: 0.0 });
                    }
                }
            } else if roll < 0.55 {
                // A lone old tree — the big spreading oak of a field corner — sometimes with a
                // boulder or a stump at its foot.
                if spot_ok(c.x, c.y, 1.0, 1.2, false, clear) && !p.trees.iter().any(|t| t.pos.distance(c) < 8.0) {
                    p.trees.push(TreeSpot { name: KINDS[(rng(&mut s) * 3.0) as usize % 3], pos: c, scale: 1.25 + rng(&mut s) * 0.35, yaw: rng(&mut s) * TAU });
                    if rng(&mut s) < 0.45 {
                        let q = c + Vec2::from_angle(rng(&mut s) * TAU) * 2.6;
                        let name = if rng(&mut s) < 0.6 { "rock_01_c" } else { "stump_a" };
                        p.props.push(PropSpot { name, pos: q, yaw: rng(&mut s) * TAU, scale: 0.8, tier: Tier::Props, sink: 0.2, solid: 0.0 });
                    }
                }
            }
        }
    }
}

/// The biome foreland: scrub that thickens toward each biome edge over ≈27u (`worldmap::FORELAND`).
fn plan_foreland(p: &mut Plan, clear: &crate::poi::StoryClearings) {
    use crate::biome::Biome as B;
    const STEP: f32 = 3.0;
    const BAND: f32 = 27.0;
    let mut z = -230.0;
    while z < 230.0 {
        let mut x = -260.0;
        while x < 260.0 {
            let ix = (x / STEP) as i32;
            let iz = (z / STEP) as i32;
            x += STEP;
            let mut s = cell_seed(ix, iz, 0xF0E1A);
            let q = Vec2::new(x - STEP + rng(&mut s) * STEP, z + rng(&mut s) * STEP);
            if !crate::worldmap::is_grass_world(q.x, q.y) || !past_walls(q.x, q.y, 14.0) {
                continue;
            }
            // The nearest biome edge in front of this grass, and how close.
            let mut best: Option<(B, f32)> = None;
            for b in [B::Forest, B::Snow, B::Rocky, B::Desert, B::Swamp] {
                let e = crate::worldmap::region_edge_world(q.x, q.y, b);
                if e > -BAND && best.is_none_or(|(_, be)| e > be) {
                    best = Some((b, e));
                }
            }
            let Some((biome, e)) = best else { continue };
            let t = (1.0 + e / BAND).clamp(0.0, 1.0);
            if rng(&mut s) > 0.16 * t * t {
                continue;
            }
            let pick = rng(&mut s);
            let yaw = rng(&mut s) * TAU;
            let sc = rng(&mut s);
            let (tree, prop): (Option<&'static str>, Option<(&'static str, f32, f32)>) = match biome {
                B::Forest => {
                    if pick < 0.35 { (Some(["oak_a_lod0", "beech_a_lod0", "oak_c_lod0"][(sc * 3.0) as usize % 3]), None) } else { (None, Some((if pick < 0.7 { "bush_a" } else { "bush_b" }, 1.0 + sc * 0.6, 0.08))) }
                }
                B::Snow | B::Rocky => {
                    if pick < 0.3 { (Some(["pine_a_lod0", "pine_b_lod0", "pine_c_lod0"][(sc * 3.0) as usize % 3]), None) } else if pick < 0.75 { (None, Some((["rock_01_a", "rock_01_c", "rock_01_e", "rock_02_g"][(sc * 4.0) as usize % 4], 0.7 + sc * 0.8, 0.3))) } else { (None, Some(("bush_b", 0.9 + sc * 0.4, 0.1))) }
                }
                B::Desert => {
                    if pick < 0.12 { (Some("dead_a_lod0"), None) } else if pick < 0.65 { (None, Some((["rock_02_e", "rock_02_g", "rock_01_f", "rock_02_d"][(sc * 4.0) as usize % 4], 0.6 + sc * 0.7, 0.35))) } else { (None, Some(("bush_b", 0.7 + sc * 0.3, 0.12))) }
                }
                B::Swamp => {
                    if pick < 0.15 { (Some("dead_a_lod0"), None) } else { (None, Some((if pick < 0.6 { "bush_a" } else { "bush_b" }, 0.9 + sc * 0.5, 0.1))) }
                }
            };
            if let Some(name) = tree {
                if spot_ok(q.x, q.y, 1.0, 1.4, true, clear) && !p.trees.iter().any(|t| t.pos.distance(q) < 4.0) {
                    p.trees.push(TreeSpot { name, pos: q, scale: 0.75 + sc * 0.45, yaw });
                }
            } else if let Some((name, scale, sink)) = prop {
                if spot_ok(q.x, q.y, 0.7, 1.4, true, clear) {
                    let solid = if name.starts_with("rock_01") && scale > 1.0 { 0.55 * scale } else { 0.0 };
                    p.props.push(PropSpot { name, pos: q, yaw, scale, tier: Tier::Props, sink, solid });
                }
            }
        }
        z += STEP;
    }
}

/// Wildflower drifts, tall-grass sweeps, haystacks and bales on a 17u cell grid.
fn plan_meadow_life(p: &mut Plan, clear: &crate::poi::StoryClearings) {
    const CELL: f32 = 17.0;
    const DRIFTS: [&[&str]; 4] = [
        &["flower_daisy", "flower_daisy", "grass_b", "flower_yellow"],
        &["flower_yellow", "flower_yellow", "grass_a", "stalks_a"],
        &["flower_lupine_a", "flower_lupine_b", "grass_c", "flower_daisy"],
        &["lush_a", "lush_b", "lush_c", "stalks_a"], // the tall-grass sweep
    ];
    for iz in -14..=14 {
        for ix in -16..=16 {
            let mut s = cell_seed(ix, iz, 0xF10E5);
            let c = Vec2::new((ix as f32 + rng(&mut s)) * CELL, (iz as f32 + rng(&mut s)) * CELL);
            let roll = rng(&mut s);
            if !crate::worldmap::is_grass_world(c.x, c.y) || crate::castle::in_footprint(c.x, c.y) {
                continue;
            }
            if roll < 0.34 {
                let set = DRIFTS[(rng(&mut s) * 4.0) as usize % 4];
                let r = 2.5 + rng(&mut s) * 4.0;
                let n = (r * r * 1.6) as usize;
                let stretch = 1.0 + rng(&mut s) * 0.8;
                let ang = rng(&mut s) * PI;
                for _ in 0..n {
                    // Gaussian-ish blob, stretched along the wind.
                    let a = rng(&mut s) * TAU;
                    let d = r * (rng(&mut s) + rng(&mut s)) * 0.5;
                    let q = c + rot2(ang, Vec2::new(a.cos() * d * stretch, a.sin() * d));
                    if !crate::worldmap::is_grass_world(q.x, q.y)
                        || crate::roads::on_road(q.x, q.y)
                        || crate::castle_ground::in_field(q.x, q.y)
                        || crate::town::near_build_plot(q.x, q.y)
                        || crate::castle::village_keep_clear(q.x, q.y, 0.3)
                        || clear.overlaps(q.x, q.y, 0.2)
                    {
                        continue;
                    }
                    p.props.push(PropSpot {
                        name: set[(rng(&mut s) * set.len() as f32) as usize % set.len()],
                        pos: q,
                        yaw: rng(&mut s) * TAU,
                        scale: 0.75 + rng(&mut s) * 0.55,
                        tier: Tier::Cover,
                        sink: 0.0,
                        solid: 0.0,
                    });
                }
            } else if roll < 0.43 && past_walls(c.x, c.y, 16.0) {
                // A haystack on a mown hay meadow, a bale or two beside it.
                if spot_ok(c.x, c.y, 2.2, 0.6, false, clear) {
                    let yaw = rng(&mut s) * TAU;
                    p.pieces.push(Piece { name: "town_hayrick", pos: c, yaw, solid: Vec2::new(1.3, 1.2), roll: 0.0, sink: 0.05, far: 200.0 });
                    crate::blockers::reserve_visual(c.x, c.y, 1.8);
                    for k in 0..(rng(&mut s) * 3.0) as usize {
                        let q = c + Vec2::from_angle(yaw + 1.3 + k as f32 * 0.9) * 3.0;
                        if spot_ok(q.x, q.y, 0.7, 0.5, false, clear) {
                            p.props.push(PropSpot { name: "meadow_bale", pos: q, yaw: rng(&mut s) * TAU, scale: 1.0, tier: Tier::Props, sink: 0.03, solid: 0.0 });
                        }
                    }
                }
            }
        }
    }
}

// ── Spawn (world-build phase 30) ───────────────────────────────────────────────────────────────

pub fn populate(commands: &mut Commands, meshes: &mut Assets<Mesh>) {
    let Some(plan) = PLAN.lock().expect("countryside plan poisoned").clone() else { return };
    let Some(kit) = crate::realforest::get() else {
        warn!("countryside: realistic kit missing — the countryside stays bare");
        return;
    };
    let ground = |p: Vec2| crate::worldmap::ground_at_world(p.x, p.y).unwrap_or(0.0);
    let cull = crate::biome::scatter_cull_enabled();
    for pc in &plan.pieces {
        let Some((half, height)) = kit.extents(pc.name) else { continue };
        let _ = half;
        let rot = Quat::from_rotation_y(pc.yaw) * Quat::from_rotation_z(pc.roll);
        let tf = Transform::from_xyz(pc.pos.x, ground(pc.pos) - pc.sink * height, pc.pos.y).with_rotation(rot);
        let range = bevy::camera::visibility::VisibilityRange {
            start_margin: 0.0..0.0,
            end_margin: if cull { (pc.far - 20.0)..pc.far } else { 1.0e6..1.0e6 },
            use_aabb: true,
        };
        if let Some(e) = kit.spawn_static_with(commands, pc.name, tf, range) {
            commands.entity(e).insert(BiomeEntity);
        }
        if pc.solid.x > 0.0 {
            crate::blockers::add_obb(pc.pos.x, pc.pos.y, pc.solid.x, pc.solid.y, pc.yaw);
        }
    }
    for t in &plan.trees {
        let Some(lod0) = kit.pick_named(&[t.name], 0.0) else { continue };
        let trunk = kit.trunk_radius(lod0, t.scale);
        crate::blockers::add(t.pos.x, t.pos.y, trunk);
        let base = Quat::from_rotation_y(t.yaw);
        let mut e = commands.spawn((
            Transform { translation: Vec3::new(t.pos.x, ground(t.pos), t.pos.y), rotation: Quat::IDENTITY, scale: Vec3::splat(t.scale) },
            crate::wind::sway_for(t.pos.x, t.pos.y, base),
            crate::verbs::ChopTree::new(trunk),
            BiomeEntity,
        ));
        kit.attach_tree(&mut e, lod0, cull);
        crate::realforest::splat(t.pos.x, t.pos.y, 0.35 * t.scale);
    }
    let mut chunks = crate::realforest::Chunks::default();
    for pr in &plan.props {
        let Some(m) = kit.pick_named(&[pr.name], 0.0) else { continue };
        let Some((_, h)) = kit.extents(pr.name) else { continue };
        let y = ground(pr.pos) - h * pr.scale * pr.sink;
        if chunks.push(kit, m, Vec3::new(pr.pos.x, y, pr.pos.y), Quat::from_rotation_y(pr.yaw), pr.scale, pr.tier) && pr.solid > 0.0 {
            crate::blockers::add(pr.pos.x, pr.pos.y, pr.solid.min(0.95));
        }
    }
    chunks.spawn(kit, commands, meshes, cull);
    wall_colliders(&plan);
    for &(c, half, yaw) in &plan.paddocks {
        spawn_paddock(commands, c, half, yaw);
    }
}

/// A split-rail paddock (the meadow's `meadow_fence` bays) with a gap for a gate, and its horses.
fn spawn_paddock(commands: &mut Commands, c: Vec2, half: Vec2, yaw: f32) {
    let corners = [Vec2::new(-half.x, -half.y), Vec2::new(half.x, -half.y), Vec2::new(half.x, half.y), Vec2::new(-half.x, half.y)];
    for side in 0..4 {
        let (a, b) = (corners[side], corners[(side + 1) % 4]);
        let len = a.distance(b);
        let bays = (len / 3.0).round().max(1.0) as i32;
        let dir = (b - a) / len;
        for i in 0..bays {
            // The gate gap: the middle bay of the side facing the yard.
            if side == 3 && i == bays / 2 {
                continue;
            }
            let m = a + dir * (len / bays as f32 * (i as f32 + 0.5));
            let w = c + rot2(yaw, m);
            let wd = rot2(yaw, dir);
            let fy = (-wd.y).atan2(wd.x);
            let tf = Transform::from_xyz(w.x, crate::worldmap::ground_at_world(w.x, w.y).unwrap_or(0.0), w.y)
                .with_rotation(Quat::from_rotation_y(fy))
                .with_scale(Vec3::new(len / bays as f32 / 3.0, 1.0, 1.0));
            if let Some(e) = crate::town_kit::spawn_piece(commands, "meadow_fence", tf) {
                commands.entity(e).insert(BiomeEntity);
            }
            crate::blockers::add_obb(w.x, w.y, len / bays as f32 * 0.5, 0.12, fy);
        }
    }
    commands.spawn((
        Transform::from_xyz(c.x, 0.0, c.y),
        PaddockSite { centre: c, half, yaw, spawned: false },
        BiomeEntity,
    ));
}

// ── Grazing horses ───────────────────────────────────────────────────────────────────────────────

pub struct CountrysidePlugin;

impl Plugin for CountrysidePlugin {
    fn build(&self, app: &mut App) {
        app.add_systems(Update, (stock_paddocks, graze.run_if(in_state(crate::game_state::Modal::None))).chain());
    }
}

#[derive(Component)]
struct PaddockSite {
    centre: Vec2,
    half: Vec2,
    yaw: f32,
    spawned: bool,
}

/// A horse grazing inside its paddock: amble to a random spot, stand and crop, repeat.
#[derive(Component)]
pub struct Grazer {
    pos: Vec2,
    facing: f32,
    target: Vec2,
    timer: f32,
    rng: u32,
    centre: Vec2,
    half: Vec2,
    yaw: f32,
}

const HORSE_SCALE: f32 = 1.75;
const HORSE_COATS: usize = 3;

fn stock_paddocks(
    mut commands: Commands,
    ready: Res<crate::biome::WorldReady>,
    mut sites: Query<&mut PaddockSite>,
    mut meshes: ResMut<Assets<Mesh>>,
    mut cmats: ResMut<Assets<crate::creature::CreatureMaterial>>,
) {
    use crate::quadruped::{QuadDrive, QuadSpecies};
    if !ready.0 || crate::realforest::get().is_none() {
        return;
    }
    let mut mat = None;
    for (si, mut site) in sites.iter_mut().enumerate() {
        if site.spawned {
            continue;
        }
        site.spawned = true;
        let mat = mat.get_or_insert_with(|| crate::creature::make_creature_material(&mut cmats)).clone();
        let n = 2 + si % 2;
        for k in 0..n.min(HORSE_COATS) {
            let mut r = cell_seed(si as i32, k as i32, 0x40125E);
            let local = Vec2::new((rng(&mut r) - 0.5) * site.half.x * 1.2, (rng(&mut r) - 0.5) * site.half.y * 1.2);
            let pos = site.centre + rot2(site.yaw, local);
            let facing = rng(&mut r) * TAU;
            let y = crate::worldmap::ground_at_world(pos.x, pos.y).unwrap_or(0.0);
            let root = commands
                .spawn((
                    Transform::from_xyz(pos.x, y, pos.y).with_rotation(Quat::from_rotation_y(facing)).with_scale(Vec3::splat(HORSE_SCALE)),
                    Visibility::Visible,
                    QuadDrive::new(QuadSpecies::Horse),
                    Grazer { pos, facing, target: pos, timer: 2.0 + rng(&mut r) * 6.0, rng: r | 1, centre: site.centre, half: site.half, yaw: site.yaw },
                    BiomeEntity,
                ))
                .id();
            let h = crate::quadruped::quad_meshes(QuadSpecies::Horse).upload(&mut meshes);
            crate::quadruped::spawn_quad(&mut commands, root, &mat, QuadSpecies::Horse, h);
        }
    }
}

fn graze(time: Res<Time>, mut q: Query<(&mut Grazer, &mut crate::quadruped::QuadDrive, &mut Transform)>) {
    let dt = time.delta_secs().min(0.05);
    for (mut g, mut drive, mut tf) in &mut q {
        let g = &mut *g;
        g.timer -= dt;
        let to = g.target - g.pos;
        let d = to.length();
        let walking = d > 0.3;
        if walking {
            let want = to.x.atan2(to.y);
            g.facing += crate::steer::wrap_pi(want - g.facing) * (dt * 1.6).min(1.0);
            let fwd = Vec2::new(g.facing.sin(), g.facing.cos());
            // Only step once roughly facing the goal: a horse turns, then walks.
            if fwd.dot(to / d) > 0.6 {
                g.pos += fwd * (0.55 * dt).min(d);
            }
        } else if g.timer <= 0.0 {
            let local = Vec2::new((rng(&mut g.rng) - 0.5) * 1.6 * g.half.x, (rng(&mut g.rng) - 0.5) * 1.6 * g.half.y);
            g.target = g.centre + rot2(g.yaw, local);
            g.timer = 6.0 + rng(&mut g.rng) * 14.0;
        }
        let m_amt = if walking { 1.0 } else { 0.0 };
        drive.moving_amt += (m_amt - drive.moving_amt) * (dt * 3.0).min(1.0);
        drive.phase += dt * 4.5 * drive.moving_amt;
        let y = crate::worldmap::ground_at_world(g.pos.x, g.pos.y).unwrap_or(tf.translation.y);
        tf.translation = Vec3::new(g.pos.x, y, g.pos.y);
        tf.rotation = Quat::from_rotation_y(g.facing);
    }
}

// ── Ground wear (realforest floor mask) ──────────────────────────────────────────────────────────

/// The farmyards' trodden ground for the realforest floor mask: `(centre, reach)` per farm, read by
/// [`ground_wear`] (via `meadow::ground_wear_passes`).
pub fn wear_sites() -> Vec<(Vec2, f32)> {
    FARMS.iter().enumerate().map(|(i, (c, _))| (*c, FARM_FLAT[i])).collect()
}

/// `(floor, path, debris)` at a farmyard: mud in the yard's heart thinning to grass at its rim, a
/// beaten path out of the gate, chaff and straw (debris) round the hayrick and the barn.
pub fn ground_wear(wx: f32, wz: f32) -> Option<(f32, f32, f32)> {
    let p = Vec2::new(wx, wz);
    let (fi, (c, yaw)) = FARMS.iter().enumerate().min_by(|a, b| a.1 .0.distance(p).total_cmp(&b.1 .0.distance(p)))?;
    let l = rot2(-*yaw, p - *c);
    let n = (wx * 0.83 + wz * 0.41).sin() * 0.5 + (wx * 0.37 - wz * 1.13 + fi as f32).sin() * 0.5;
    // The yard: an ellipse round the well, ragged.
    let k = if fi == CROFT { 0.55 } else { 1.0 };
    let yard = 1.0 - ((Vec2::new(l.x / (13.0 * k), (l.y - 1.5 * k) / (7.5 * k)).length() + n * 0.12 - 0.75) / 0.3).clamp(0.0, 1.0);
    // The gate path (local +Z) out to the track.
    let path = if l.y > 2.0 * k && l.y < 14.0 * k { 1.0 - ((l.x.abs() + n * 0.3 - 0.9) / 0.8).clamp(0.0, 1.0) } else { 0.0 };
    let straw = 1.0 - ((l - Vec2::new(10.0, 0.5) * k).length() + n - 3.5 * k).clamp(0.0, 3.0) / 3.0;
    let floor = yard.max(path);
    (floor > 0.01 || straw > 0.01).then_some((floor.max(straw * 0.6), (yard * 0.7).max(path * 0.85), straw * 0.8))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn plan_world() {
        reset_plan(); // as the world build does at step 0 (the plan feeds `poi::story_clearings`)
        crate::blockers::reset();
        crate::wreck_cove::plan();
        crate::camps::plan();
        crate::poi::plan_clearings();
        crate::stories_warm::plan();
        crate::vignettes::plan();
        crate::wayside::plan();
        crate::stories_cold::plan();
        crate::sites_warm::plan();
        crate::wild_sites::plan();
        plan();
    }

    /// The farmsteads seat (both yards on clear, level grass, every building placed), the plan is
    /// deterministic, and nothing lands on a road, a field or a build plot.
    #[test]
    fn countryside_plan_seats_and_is_deterministic() {
        let _g = crate::blockers::TEST_LOCK.lock().unwrap();
        plan_world();
        let first = PLAN.lock().unwrap().clone().unwrap();
        assert_eq!(first.paddocks.len(), 1, "the farmstead's paddock must seat");
        let houses = first.pieces.iter().filter(|p| p.name == "town_house_b" || p.name == "town_house_c").count();
        assert_eq!(houses, FARMS.len(), "every farmstead must seat");
        eprintln!("countryside: {} pieces, {} trees, {} props", first.pieces.len(), first.trees.len(), first.props.len());
        assert!(first.trees.len() > 20, "only {} countryside trees", first.trees.len());
        assert!(first.props.len() > 400, "only {} countryside props", first.props.len());
        for pc in &first.pieces {
            assert!(!crate::roads::on_road(pc.pos.x, pc.pos.y), "{} on a road at {:?}", pc.name, pc.pos);
            assert!(!crate::town::near_build_plot(pc.pos.x, pc.pos.y), "{} on a plot", pc.name);
        }
        for t in &first.trees {
            assert!(!crate::castle_ground::in_field(t.pos.x, t.pos.y), "tree in a field at {:?}", t.pos);
        }
        // Farm yards are levelled: the house and barn corners within a step of each other.
        for (i, (c, _)) in FARMS.into_iter().enumerate() {
            let y0 = crate::worldmap::ground_at_world(c.x, c.y).unwrap();
            for a in 0..8 {
                let q = c + Vec2::from_angle(a as f32 * TAU / 8.0) * (FARM_FLAT[i] - 4.0);
                let y = crate::worldmap::ground_at_world(q.x, q.y).unwrap();
                assert!((y - y0).abs() < 0.6, "farm at {c:?} not level: {y0:.2} vs {y:.2} at {q:?}");
            }
        }
        eprintln!("countryside: {} pieces, {} trees, {} props", first.pieces.len(), first.trees.len(), first.props.len());
        plan_world();
        let second = PLAN.lock().unwrap().clone().unwrap();
        assert_eq!(format!("{:?}", first.trees), format!("{:?}", second.trees), "planning must be deterministic");
        reset_plan();
        crate::blockers::reset();
    }

    /// `SPOT_WHY="x,z,r"`: print which [`spot_ok`] rule rejects each probe of a footprint.
    #[test]
    fn spot_why() {
        let Ok(v) = std::env::var("SPOT_WHY") else { return };
        let v: Vec<f32> = v.split(',').map(|s| s.trim().parse().unwrap()).collect();
        let _g = crate::blockers::TEST_LOCK.lock().unwrap();
        plan_world();
        reset_plan();
        let clear = crate::poi::story_clearings();
        let (x, z, r) = (v[0], v[1], v[2]);
        eprintln!("WHY clear {} village {} visual {}", clear.overlaps(x, z, r), crate::castle::village_keep_clear(x, z, r), crate::blockers::any_visual_within(x, z, r));
        for k in 0..=8 {
            let a = k as f32 * (TAU / 8.0);
            let (px, pz) = if k == 8 { (x, z) } else { (x + a.cos() * r, z + a.sin() * r) };
            eprintln!(
                "WHY ({px:.1},{pz:.1}) y {:?} grass {} biome {:?} road {} field {} plot {} river {} water {}",
                crate::worldmap::ground_at_world(px, pz),
                crate::worldmap::is_grass_world(px, pz),
                crate::worldmap::tile_biome_world(px, pz),
                crate::roads::on_road(px, pz),
                crate::castle_ground::in_field(px, pz),
                crate::town::near_build_plot(px, pz),
                crate::worldmap::is_river_world(px, pz),
                crate::worldmap::over_inland_water_world(px, pz)
            );
        }
        crate::blockers::reset();
    }

    /// `FARM_SCAN=1`: list yard centres where a farmstead disc (r 15) is all open grass, off roads,
    /// plots, the village and every clearing — the candidates [`FARMS`] was picked from.
    #[test]
    fn farm_scan() {
        if std::env::var("FARM_SCAN").is_err() {
            return;
        }
        let _g = crate::blockers::TEST_LOCK.lock().unwrap();
        plan_world();
        reset_plan();
        let clear = crate::poi::story_clearings();
        let mut z = -160.0;
        while z <= 160.0 {
            let mut x = -160.0;
            while x <= 160.0 {
                let ok = (0..24).all(|k| {
                    let a = k as f32 / 24.0 * TAU;
                    [0.0, 3.0, 6.0, 9.0].iter().all(|r| {
                        let q = Vec2::new(x, z) + Vec2::new(a.cos(), a.sin()) * *r;
                        (crate::worldmap::is_grass_world(q.x, q.y)
                            || (*r > 6.5 && matches!(crate::worldmap::tile_biome_world(q.x, q.y), Some(crate::biome::Biome::Forest))))
                            && !crate::roads::on_road(q.x, q.y)
                            && !crate::town::near_build_plot(q.x, q.y)
                            && !crate::castle::village_keep_clear(q.x, q.y, 0.0)
                            && !crate::castle_ground::in_field(q.x, q.y)
                            && !clear.overlaps(q.x, q.y, 0.0)
                            && crate::worldmap::ground_at_world(q.x, q.y).is_some()
                    })
                });
                if ok {
                    let ring = crate::worldmap::castle_ring_world(x, z);
                    let road = (1..40).find(|d| crate::roads::near_road(x, z, *d as f32)).unwrap_or(99);
                    eprintln!("FARMCAND ({x:.0},{z:.0}) ring {ring:.0} road {road}");
                }
                x += 4.0;
            }
            z += 4.0;
        }
        crate::blockers::reset();
    }

    /// `COUNTRY_DUMP=<file.ppm>`: a 2 px/u planning map of the castle surroundings (±170u): biome
    /// tiles, hillshade, roads, fields, plots, the castle, the village, planned story clearings, the
    /// countryside plan (trees dark, pieces red, props tan), a 20u grid.
    #[test]
    fn country_map_dump() {
        let Ok(path) = std::env::var("COUNTRY_DUMP") else { return };
        let _g = crate::blockers::TEST_LOCK.lock().unwrap();
        plan_world();
        let plan = PLAN.lock().unwrap().clone().unwrap();
        let clear = crate::poi::story_clearings();
        const R: f32 = 170.0;
        const PX: f32 = 2.0;
        let n = (2.0 * R * PX) as usize;
        let mut px = vec![0u8; n * n * 3];
        for j in 0..n {
            for i in 0..n {
                let wx = -R + (i as f32 + 0.5) / PX;
                let wz = -R + (j as f32 + 0.5) / PX;
                let k = (j * n + i) * 3;
                let Some(y) = crate::worldmap::ground_at_world(wx, wz) else {
                    px[k..k + 3].copy_from_slice(&[40, 70, 120]);
                    continue;
                };
                use crate::biome::Biome as B;
                let mut c: [f32; 3] = if crate::worldmap::is_grass_world(wx, wz) {
                    [110.0, 170.0, 80.0]
                } else {
                    match crate::worldmap::tile_biome_world(wx, wz) {
                        Some(B::Forest) => [50.0, 110.0, 50.0],
                        Some(B::Snow) => [225.0, 232.0, 240.0],
                        Some(B::Rocky) => [140.0, 132.0, 122.0],
                        Some(B::Desert) => [220.0, 193.0, 137.0],
                        Some(B::Swamp) => [85.0, 97.0, 58.0],
                        None => [200.0, 180.0, 120.0],
                    }
                };
                let e = crate::worldmap::ground_at_world(wx + 0.5, wz).unwrap_or(y);
                let s = crate::worldmap::ground_at_world(wx, wz + 0.5).unwrap_or(y);
                let nrm = Vec3::new((y - e) * 4.0, 1.0, (y - s) * 4.0).normalize();
                let l = 0.45 + 0.75 * nrm.dot(Vec3::new(-0.6, 0.7, -0.4).normalize()).max(0.0);
                c = c.map(|v| v * l);
                if crate::roads::road_strength(wx, wz) > 0.3 {
                    c = [120.0, 85.0, 45.0];
                }
                if crate::castle_ground::field_at(wx, wz).is_some_and(|(w, _)| w > 0.4) {
                    c = [150.0, 105.0, 60.0];
                }
                if ground_wear(wx, wz).is_some_and(|(f, _, _)| f > 0.5) {
                    c = [125.0, 100.0, 70.0];
                }
                if crate::castle::village_keep_clear(wx, wz, 0.0) {
                    c = [c[0] * 0.6 + 80.0, c[1] * 0.6, c[2] * 0.6 + 90.0];
                }
                if crate::town::near_build_plot(wx, wz) {
                    c = [220.0, 60.0, 60.0];
                }
                if crate::castle::in_footprint(wx, wz) {
                    c = [90.0, 90.0, 95.0];
                }
                if clear.overlaps(wx, wz, -0.35) {
                    c = [c[0] * 0.5 + 127.0, c[1] * 0.5 + 127.0, c[2] * 0.5];
                }
                let gx = wx.rem_euclid(20.0) < 0.5 / PX * 1.01;
                let gz = wz.rem_euclid(20.0) < 0.5 / PX * 1.01;
                if gx || gz {
                    let axis = wx.abs() < 0.5 || wz.abs() < 0.5;
                    c = if axis { [0.0, 0.0, 0.0] } else { c.map(|v| v * 0.6) };
                }
                for ch in 0..3 {
                    px[k + ch] = c[ch].clamp(0.0, 255.0) as u8;
                }
            }
        }
        let mut dot = |p: Vec2, r: i32, rgb: [u8; 3]| {
            let (ci, cj) = (((p.x + R) * PX) as i32, ((p.y + R) * PX) as i32);
            for dj in -r..=r {
                for di in -r..=r {
                    let (i, j) = (ci + di, cj + dj);
                    if i >= 0 && j >= 0 && (i as usize) < n && (j as usize) < n {
                        let k = (j as usize * n + i as usize) * 3;
                        px[k..k + 3].copy_from_slice(&rgb);
                    }
                }
            }
        };
        for pr in &plan.props {
            let col = if pr.tier == Tier::Cover { [235, 225, 90] } else { [175, 150, 110] };
            dot(pr.pos, 0, col);
        }
        for t in &plan.trees {
            dot(t.pos, 2, [20, 60, 20]);
        }
        for pc in &plan.pieces {
            dot(pc.pos, 2, [200, 30, 30]);
        }
        let mut out = format!("P6\n{n} {n}\n255\n").into_bytes();
        out.extend_from_slice(&px);
        std::fs::write(path, out).unwrap();
        reset_plan();
        crate::blockers::reset();
    }
}
