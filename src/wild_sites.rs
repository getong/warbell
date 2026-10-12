//! **Swamp and Rocky discovery sites** — the island telling its own story (design:
//! `docs/superpowers/specs/2026-10-12-wyspa-opowiada-design.md`, under the campaign plan
//! `2026-10-10-kampania-fabula-design.md`). No text, no interaction: a scene that explains itself,
//! found off the roads. Every site is UNIQUE (one instance each — the design's "few repeats" rule),
//! and each biome has its own kind of place, its own models and its own scanned materials:
//!
//! - **Rocky — "the iron voice"** (granite, slate, black iron, red ochre, lichen, rope): the **Clan
//!   Gong** on the highest flat col (a black-iron gong hung between two menhirs, offerings at its
//!   foot, the maul never lifted — the law of the iron voice, unstated); the first colony's
//!   **signal tower** on a high spur with **Anselm's journal page** (stage 3: the bell hung, rung
//!   every dusk, iron answering iron in the hills) under a stone at the stair foot; the colony's
//!   **rope bridge, cut**, across a real gap (both anchors, the bridge hanging down the far wall); the **Old Ones' door** cut into a granite face backed into
//!   the slope; the **gully of the first war** under scree.
//! - **Swamp — "the end and the other shore"** (black water, rotten timber, rust, peat, bone): the
//!   colony's **sunken mission chapel** at the swamp's edge — empty bell-cote, the lectern with
//!   **Anselm's last page** and the sketch of the bell; the **ork barrows** (orks as a people:
//!   graves, fish offerings, two fresh mounds); an **ork eel weir** and the colony's **causeway
//!   ending in open water**, both facing a bog pool; a **peat cutting**.
//!
//! Models: `wild_sites.glb` (`tools/blender_forest/wild_sites.py`), real scale, base y=0, the
//! scene's front (its story / its water / its drop) toward local -Z.
//!
//! Planned at build phase 4 after `stories_cold::plan` ([`plan`]), the same way as the other story
//! layers: a deterministic jittered grid per biome, accepted only on legal ground (inside the biome,
//! off roads / pass trails / rivers / camps / landmarks / the town / the Blight, clear of every
//! other planned piece) and folded into `poi::story_clearings`, so the scatter keeps clear. Each
//! scene has a [`Seat`] — how it meets the terrain: flat open ground, a pool shore (front in the
//! water), a gap (front across a gully or sea inlet to a far rim), a slope at its back, or the highest flat ground there is.
//! At phase 32 ([`populate`]) each site is re-checked and re-sited if a later phase claimed it;
//! each becomes a minor discoverable (`landmarks::attach_story`).

use std::f32::consts::TAU;
use std::sync::Mutex;

use bevy::camera::visibility::VisibilityRange;
use bevy::prelude::*;

use crate::biome::{Biome, BiomeEntity};

/// How a scene meets the terrain.
#[derive(Clone, Copy, PartialEq, Debug)]
enum Seat {
    /// Flat open ground all round.
    Open,
    /// Open ground, preferring the outer rim of its swamp zone (the colony built at the edge).
    Rim,
    /// The highest flat legal ground in the biome (`rank` 0 = highest, 1 = second, ...).
    High,
    /// On a bog-pool shore: the centre dry, open water in front (local -Z), dry land behind.
    Shore,
    /// Across a gap: a far rim [`GAP_SPANS`] ahead (local -Z) at about the same height, the ground
    /// between them at least this far below both (a gully / the gorge); the far anchor
    /// (`<model>_far`) is spawned there facing back.
    Gap(f32),
    /// Backed into a slope: the ground behind (local +Z) rises at least this far.
    Backed(f32),
}

/// One discovery site: kit model, home biome, visual radius it reserves, solid masses as
/// model-local oriented boxes `(x, z, half width, half depth, local yaw)`, its discoverable name
/// and lore line (English, seeds only), and how it seats.
struct Scene {
    model: &'static str,
    biome: Biome,
    foot: f32,
    solids: &'static [(f32, f32, f32, f32, f32)],
    name: &'static str,
    lore: &'static str,
    seat: Seat,
}

const SCENES: [Scene; 10] = [
    // ── Swamp ──
    Scene { model: "site_mission_chapel", biome: Biome::Swamp, foot: 4.3, seat: Seat::Rim,
        solids: &[(0.0, 0.2, 2.0, 3.0, 0.0), (2.6, -2.7, 0.7, 0.35, 0.9)],
        name: "Anselm's Journal \u{2014} The Last Page",
        lore: "Drowned on the lectern beside a sketch of the bell: \"...came only after we rang...\" \u{2014} \"...the Governor will not let us stop...\"" },
    Scene { model: "site_ork_barrows", biome: Biome::Swamp, foot: 3.6, seat: Seat::Open,
        solids: &[(0.0, 0.3, 2.4, 1.3, 0.0), (-2.7, -1.4, 0.25, 0.25, 0.0)],
        name: "The Ork Barrows",
        lore: "The orks bury their dead here with fish and iron for the road; the two newest graves were dug this year." },
    Scene { model: "site_eel_weir", biome: Biome::Swamp, foot: 3.4, seat: Seat::Shore,
        solids: &[(1.6, 1.9, 0.85, 0.2, 0.0), (-1.55, 2.25, 0.5, 0.45, 0.0)],
        name: "The Ork Eel Weir",
        lore: "Traps mended, eels split and drying: whoever fishes this weir means to stay." },
    Scene { model: "site_colony_causeway", biome: Biome::Swamp, foot: 3.8, seat: Seat::Shore,
        solids: &[(0.0, 3.3, 0.9, 0.45, 0.0)],
        name: "The Colony Causeway",
        lore: "The first colony laid a road into the bog, toward the orks' country, and stopped here." },
    Scene { model: "site_peat_cutting", biome: Biome::Swamp, foot: 3.3, seat: Seat::Open,
        solids: &[(0.4, 1.3, 2.0, 0.9, 0.0), (-1.9, -1.3, 0.55, 0.85, 0.35)],
        name: "The Peat Cuttings",
        lore: "The colony cut its winter fuel here; the last load is still on the sledge." },
    // ── Rocky ──
    Scene { model: "site_clan_gong", biome: Biome::Rocky, foot: 3.5, seat: Seat::High,
        solids: &[(-1.55, 0.0, 0.6, 0.35, 0.0), (1.55, 0.0, 0.6, 0.35, 0.0), (0.0, 0.0, 0.95, 0.12, 0.0), (0.0, 1.45, 0.6, 0.35, 0.0)],
        name: "The Clan Gong",
        lore: "No hand has struck this gong in a hundred years, and no ork will camp beneath it; yet the offerings at its foot are fresh." },
    Scene { model: "site_signal_tower", biome: Biome::Rocky, foot: 3.4, seat: Seat::High,
        solids: &[(0.0, 0.3, 1.4, 1.4, 0.0), (1.75, 1.15, 0.9, 0.8, 0.0)],
        name: "Anselm's Journal \u{2014} The Dusk Charter",
        lore: "Under a stone at the stair: \"We hung the bell and read the charter, and rang at dusk. That night iron answered iron in the hills.\"" },
    Scene { model: "site_rope_bridge", biome: Biome::Rocky, foot: 2.2, seat: Seat::Gap(6.0),
        solids: &[(0.0, 0.3, 1.25, 0.5, 0.0)],
        name: "The Cut Rope Bridge",
        lore: "The colony's road to the east, cut from this side with an axe; no one came back across." },
    Scene { model: "site_old_ones_door", biome: Biome::Rocky, foot: 3.6, seat: Seat::Backed(1.2),
        solids: &[(0.0, 2.0, 3.2, 1.3, 0.0)],
        name: "The Old Ones' Door",
        lore: "Rings cut around a single stroke: the old sign for a voice that must be answered." },
    Scene { model: "site_scree_battlefield", biome: Biome::Rocky, foot: 3.5, seat: Seat::Backed(0.6),
        solids: &[(0.0, 1.5, 2.2, 1.3, 0.0)],
        name: "The Gully of the First War",
        lore: "Colony helmets and ork cleavers under the same scree; both sides came when they were called." },
];

/// Seating order: the most constrained first (shore / gap / backed / high), then the open ones.
const SEAT_ORDER: [usize; 10] = [3, 2, 7, 5, 6, 8, 9, 0, 1, 4];
/// Two sites stand at least this far past their footprints from each other.
const MIN_GAP: f32 = 10.0;
/// Sites of the same biome spread at least this far apart (centre to centre).
const SPREAD: f32 = 26.0;
/// Max terrain spread under the (seated part of the) footprint.
const FLAT_DELTA: f32 = 0.5;
const FLAT_DELTA_RELAXED: f32 = 0.8;
/// Last resort for the shore / gap / backed / high seats (a bank, a ledge): the model's buried
/// footings swallow this much under the seated half.
const FLAT_DELTA_SEAT: f32 = 1.1;
const CAMP_KEEP: f32 = 7.0;
const TOWN_KEEP: f32 = 4.0;
const LANDMARK_KEEP: f32 = 14.0;
/// Clearance from a pass trail's centreline beyond the footprint.
const TRAIL_KEEP: f32 = 3.0;
/// Extra keep-off from roads past the footprint (these are off-road finds).
const ROAD_MARGIN: f32 = 3.0;
/// Extra glade around each site kept free of scatter (see [`planned_footprints`]).
const SIGHTLINE: f32 = 4.0;
/// The biome must hold this far past the footprint (no cacti over the gong, no forest in the bog).
const BIOME_MARGIN: f32 = 6.0;
/// Shore seat: the water probes in front sit this deep in a pool (base-unit signed distance).
const SHORE_WET: f32 = -0.25;
/// Gap seat: the spans tried (centre of the near anchor to the far anchor), shortest first.
const GAP_SPANS: [f32; 5] = [9.0, 10.0, 11.0, 12.5, 14.0];
/// Footprint of the far anchor (posts + cairn) of a gap scene.
const FAR_FOOT: f32 = 1.6;

#[derive(Clone, Debug, PartialEq)]
struct Site {
    scene: usize,
    pos: Vec2,
    yaw: f32,
    /// Gap scenes: distance ahead (local -Z) to the far anchor; 0 otherwise.
    span: f32,
}

impl Site {
    /// The far anchor of a gap scene.
    fn far(&self) -> Option<Vec2> {
        (self.span > 0.0).then(|| self.pos + front(self.yaw) * self.span)
    }
}

static SITES: Mutex<Vec<Site>> = Mutex::new(Vec::new());

pub fn reset_plan() {
    SITES.lock().unwrap().clear();
}

/// `(centre, cleared radius)` of every planned site (folded into `poi::story_clearings`): the
/// footprint plus [`SIGHTLINE`], so the bog's cypresses / willows and the rocky scrub stand back and
/// the scene reads from a distance instead of through a curtain of moss.
pub fn planned_footprints() -> Vec<(Vec2, f32)> {
    let sites = SITES.lock().unwrap();
    let mut out: Vec<(Vec2, f32)> = sites.iter().map(|s| (s.pos, SCENES[s.scene].foot + SIGHTLINE)).collect();
    out.extend(sites.iter().filter_map(|s| s.far()).map(|f| (f, FAR_FOOT + SIGHTLINE * 0.5)));
    out
}

/// Does a circle at `(x, z)` of radius `r` overlap a planned site?
pub fn overlaps_planned(x: f32, z: f32, r: f32) -> bool {
    let p = Vec2::new(x, z);
    SITES.lock().unwrap().iter().any(|s| {
        p.distance_squared(s.pos) < (SCENES[s.scene].foot + r + 0.35).powi(2)
            || s.far().is_some_and(|f| p.distance_squared(f) < (FAR_FOOT + r + 0.35).powi(2))
    })
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

/// World direction of the model's local -Z (its front) at `yaw`.
fn front(yaw: f32) -> Vec2 {
    Vec2::new(-yaw.sin(), -yaw.cos())
}

/// Is this footprint probe (offset `d` from the centre) on the part of the scene that must sit on
/// the ground? Shore / gap scenes leave their front (water / drop) out; a backed scene its back.
fn seated_probe(seat: Seat, d: Vec2, yaw: f32, foot: f32) -> bool {
    let along = d.dot(front(yaw)) / foot.max(0.01);
    match seat {
        Seat::Shore => along < -0.15,
        // A gap anchor (two posts on a slate footing) only needs its inner back half level: rims
        // are rough, and the footing's buried courses take the rest.
        Seat::Gap(_) => along < -0.2 && d.length() < foot * 0.7,
        Seat::Backed(_) => along > -0.35,
        _ => true,
    }
}

/// The footprint probe offsets (two rings) — shared by the ground test and the seat height.
fn probes(foot: f32) -> impl Iterator<Item = Vec2> {
    [(16usize, foot), (8, foot * 0.55)].into_iter().flat_map(|(n, r)| {
        (0..n).map(move |k| {
            let a = k as f32 * (TAU / n as f32);
            Vec2::new(a.cos(), a.sin()) * r
        })
    })
}

/// Ground + keep-out rules for `scene` at `q` turned to `yaw`, with flatness `flat` over its seated
/// part. Shared by the plan, the spawn re-check and the tests.
fn ground_ok(scene: usize, q: Vec2, yaw: f32, flat: f32, trails: &[Vec<Vec2>]) -> bool {
    let s = &SCENES[scene];
    let (x, z, foot) = (q.x, q.y, s.foot);
    let Some(y0) = crate::worldmap::ground_at_world(x, z) else { return false };
    if crate::worldmap::tile_biome_world(x, z) != Some(s.biome) || crate::worldmap::is_pool_world(x, z) {
        return false;
    }
    let swamp = s.biome == Biome::Swamp;
    let rb = foot + if s.seat == Seat::High { BIOME_MARGIN * 0.5 } else { BIOME_MARGIN };
    if (0..12).any(|k| {
        let a = k as f32 * (TAU / 12.0);
        let d = Vec2::new(a.cos(), a.sin());
        let (px, pz) = (x + d.x * rb, z + d.y * rb);
        // A gap scene's front is the gap: whatever lies down there (a stream, a sea inlet) is fine.
        let gap_side = matches!(s.seat, Seat::Gap(_)) && d.dot(front(yaw)) > -0.2;
        !gap_side && !crate::worldmap::is_pool_world(px, pz) && crate::worldmap::tile_biome_world(px, pz) != Some(s.biome)
    }) {
        return false;
    }
    let (mut lo, mut hi) = (y0, y0);
    for d in probes(foot) {
        let (px, pz) = (x + d.x, z + d.y);
        if !seated_probe(s.seat, d, yaw, foot) {
            // The front over the water / drop (or the slope behind) only has to stay off the
            // roads, rivers, plots and other people's ground.
            if crate::roads::on_road(px, pz) || crate::town::near_build_plot(px, pz) || crate::camps::in_clearing(px, pz) {
                return false;
            }
            continue;
        }
        let Some(y) = crate::worldmap::ground_at_world(px, pz) else { return false };
        lo = lo.min(y);
        hi = hi.max(y);
        if hi - lo > flat
            || crate::worldmap::tile_biome_world(px, pz) != Some(s.biome)
            || crate::roads::on_road(px, pz)
            || crate::worldmap::is_river_world(px, pz)
            || (s.seat != Seat::Shore && crate::worldmap::is_pool_world(px, pz))
            || (!swamp && !shelf_ok(s.seat) && crate::worldmap::cliff_shelf_world(px, pz))
            || crate::town::near_build_plot(px, pz)
            || crate::castle::in_footprint(px, pz)
            || crate::camps::in_clearing(px, pz)
            || crate::rival::near_fort(px, pz)
            || crate::ruins::near_landmark_visual_footprint(px, pz)
        {
            return false;
        }
    }
    let r = foot + ROAD_MARGIN;
    if (0..12).any(|k| {
        let a = k as f32 * (TAU / 12.0);
        crate::roads::on_road(x + a.cos() * r, z + a.sin() * r)
    }) {
        return false;
    }
    if !seat_shape_ok(s.seat, q, yaw, foot, y0) {
        return false;
    }
    !crate::bridges::near_bridge(x, z, foot + 0.5)
        && crate::ork_fortress::blight_edge_world(x, z) < -(foot + 6.0)
        && q.length() > crate::worldmap::SAFE_R * crate::worldmap::MAP_SCALE + TOWN_KEEP + foot
        && crate::camps::plan().iter().all(|c| c.centre.distance(q) > CAMP_KEEP + foot)
        && crate::ruins::landmark_sites().iter().all(|l| l.pos.distance(q) > LANDMARK_KEEP + foot)
        && trails.iter().all(|t| t.windows(2).all(|w| seg_dist(q, w[0], w[1]) > foot + TRAIL_KEEP))
}

/// High / gap / backed sites may stand up on a cliffy shelf: they are planned beside a pass trail
/// (high) or against the rise itself (backed), so the climb is the trail's.
fn shelf_ok(seat: Seat) -> bool {
    matches!(seat, Seat::High | Seat::Gap(_) | Seat::Backed(_))
}

/// The terrain shape a seat asks for: water in front of a shore scene (and dry land behind), a drop
/// across a gap, a rise behind a backed scene.
fn seat_shape_ok(seat: Seat, q: Vec2, yaw: f32, foot: f32, y0: f32) -> bool {
    let f = front(yaw);
    let side = Vec2::new(-f.y, f.x);
    let h = |p: Vec2| crate::worldmap::ground_at_world(p.x, p.y);
    match seat {
        Seat::Shore => {
            let wet = [(0.8, 0.0), (1.0, 0.0), (0.9, 0.3), (0.9, -0.3)]
                .iter()
                .all(|&(a, b)| crate::worldmap::pool_sd_world(q.x + (f.x * a + side.x * b) * foot, q.y + (f.y * a + side.y * b) * foot) < SHORE_WET);
            let dry = [(-0.6, 0.0), (-0.9, 0.3), (-0.9, -0.3)]
                .iter()
                .all(|&(a, b)| !crate::worldmap::is_pool_world(q.x + (f.x * a + side.x * b) * foot, q.y + (f.y * a + side.y * b) * foot));
            wet && dry
        }
        Seat::Backed(rise) => [(0.0, 1.0), (0.45, 0.9), (-0.45, 0.9)].iter().all(|&(b, a)| {
            let p = q - f * (foot * a + 1.0) + side * b * foot;
            h(p).is_some_and(|y| y > y0 + rise)
        }),
        Seat::Gap(drop) => gap_span(q, yaw, y0, drop).is_some(),
        _ => true,
    }
}

/// A gap seat's span: the shortest of [`GAP_SPANS`] whose far end is legal rim ground within 1.5u
/// of this one's height, with real edges on both sides (the ground 2.4u in from each anchor already
/// 2u down) and the floor between them `drop` below the lower rim across the bridge's width.
fn gap_span(q: Vec2, yaw: f32, y0: f32, drop: f32) -> Option<f32> {
    let f = front(yaw);
    let side = Vec2::new(-f.y, f.x);
    let h = |p: Vec2| crate::worldmap::ground_at_world(p.x, p.y);
    GAP_SPANS.into_iter().find(|&span| {
        let far = q + f * span;
        let Some(y1) = h(far) else { return false };
        if (y1 - y0).abs() > 1.5 || !far_anchor_ok(far, f, y1) {
            return false;
        }
        let rim = y0.min(y1);
        let edges = h(q + f * 2.4).is_some_and(|y| y < y0 - 2.0) && h(far - f * 2.4).is_some_and(|y| y < y1 - 2.0);
        edges
            && [0.35f32, 0.5, 0.65].iter().all(|&t| {
                [-0.9f32, 0.0, 0.9].iter().all(|&b| {
                    // Over the stream / a sea inlet the floor is the water.
                    let p = q + f * span * t + side * b;
                    h(p).unwrap_or(crate::worldmap::SEA_Y) < rim - drop
                })
            })
    })
}

/// The far anchor's ground: rock-biome rim, off roads / rivers / pools / plots / camps / landmarks,
/// its back half (away from the gap, `+f`) within 0.9u of its centre height.
fn far_anchor_ok(far: Vec2, f: Vec2, y1: f32) -> bool {
    let bad = |p: Vec2| {
        crate::worldmap::tile_biome_world(p.x, p.y) != Some(Biome::Rocky)
            || crate::worldmap::is_pool_world(p.x, p.y)
            || crate::worldmap::is_river_world(p.x, p.y)
            || crate::roads::on_road(p.x, p.y)
            || crate::town::near_build_plot(p.x, p.y)
            || crate::castle::in_footprint(p.x, p.y)
            || crate::camps::in_clearing(p.x, p.y)
            || crate::ruins::near_landmark_visual_footprint(p.x, p.y)
    };
    if bad(far) {
        return false;
    }
    (0..8).all(|k| {
        let a = k as f32 * (TAU / 8.0);
        let d = Vec2::new(a.cos(), a.sin()) * FAR_FOOT * 0.75;
        if d.dot(f) < -0.3 * FAR_FOOT {
            return true; // the gap side
        }
        let p = far + d;
        !bad(p) && crate::worldmap::ground_at_world(p.x, p.y).is_some_and(|y| (y - y1).abs() < 1.3)
    })
}

/// Clear of every other planned piece (this plan's own sites, the other story layers, and
/// anything solid); while planning (`visual`) also of every visual reservation.
fn clear_of_others(q: Vec2, scene: usize, planned: &[Site], visual: bool) -> bool {
    let s = &SCENES[scene];
    planned.iter().all(|o| {
        let d = o.pos.distance(q);
        d > s.foot + SCENES[o.scene].foot + MIN_GAP && (SCENES[o.scene].biome != s.biome || d > SPREAD)
    }) && !crate::poi::story_clearings().overlaps(q.x, q.y, s.foot + 1.0)
        && !(visual && crate::blockers::any_visual_within(q.x, q.y, s.foot + 0.3))
        && !crate::blockers::any_within(q.x, q.y, s.foot + 0.3)
}

/// Candidate spots in the scene's biome, a deterministic jittered grid, in a stable order picked by
/// the seat: shuffled for open ground, outermost first for a rim scene, highest first for a high one.
fn candidates(scene: usize, trails: &[Vec<Vec2>]) -> Vec<Vec2> {
    let s = &SCENES[scene];
    if s.seat == Seat::High {
        return trail_candidates(scene, trails);
    }
    let step = match s.seat {
        Seat::Gap(_) => 1.0,
        Seat::Shore => 2.0,
        _ if s.biome == Biome::Swamp => 4.0,
        _ => 6.0,
    };
    let (gx, gz) = (crate::worldmap::GX, crate::worldmap::GZ);
    let (cols, rows) = (crate::worldmap::COLS as f32, crate::worldmap::ROWS as f32);
    let zones = crate::worldmap::swamp_zones_world();
    let mut rng = 0x7a11_d5e5 ^ (scene as u32).wrapping_mul(0x85eb_ca6b);
    let mut out: Vec<(f32, Vec2)> = Vec::new();
    let mut z = -gz + step * 0.5;
    while z < rows - gz {
        let mut x = -gx + step * 0.5;
        while x < cols - gx {
            // (A gap is a narrow thing: its anchors sit on an exact fine grid, unjittered.)
            let jit = if matches!(s.seat, Seat::Gap(_)) { 0.0 } else { step * 0.8 };
            let p = Vec2::new(x + (rng_next(&mut rng) - 0.5) * jit, z + (rng_next(&mut rng) - 0.5) * jit);
            let key = rng_next(&mut rng);
            if crate::worldmap::tile_biome_world(p.x, p.y) == Some(s.biome) && (!matches!(s.seat, Seat::Gap(_)) || at_edge(p)) {
                let key = match s.seat {
                    Seat::High => -crate::worldmap::ground_at_world(p.x, p.y).unwrap_or(-1e3),
                    Seat::Rim => {
                        // Fraction of the way out from the nearest swamp zone centre (1 = its rim).
                        let f = zones
                            .iter()
                            .map(|&(cx, cz, r)| Vec2::new(cx, cz).distance(p) / r.max(1.0))
                            .fold(f32::INFINITY, f32::min);
                        -(f.min(1.2) * 4.0).floor() + key
                    }
                    _ => key,
                };
                out.push((key, p));
            }
            x += step;
        }
        z += step;
    }
    out.sort_by(|a, b| a.0.total_cmp(&b.0).then(a.1.x.total_cmp(&b.1.x)).then(a.1.y.total_cmp(&b.1.y)));
    out.into_iter().map(|(_, p)| p).collect()
}

/// Cheap gap prefilter: does the ground fall 2u within 2.4u of `p` in some direction (an edge)?
fn at_edge(p: Vec2) -> bool {
    let Some(y0) = crate::worldmap::ground_at_world(p.x, p.y) else { return false };
    (0..12).any(|k| {
        let a = k as f32 * (TAU / 12.0);
        crate::worldmap::ground_at_world(p.x + a.cos() * 2.4, p.y + a.sin() * 2.4).unwrap_or(crate::worldmap::SEA_Y) < y0 - 2.0
    })
}

/// Spots beside the pass trails (every ~3u down each trail, both sides, a few offsets past the
/// footprint + [`TRAIL_KEEP`]), inside the scene's biome: the high sites take the highest (a col on
/// the pass, a spur above it).
fn trail_candidates(scene: usize, trails: &[Vec<Vec2>]) -> Vec<Vec2> {
    let s = &SCENES[scene];
    let mut rng = 0x3c6e_f372 ^ (scene as u32).wrapping_mul(0x85eb_ca6b);
    let mut out: Vec<(f32, Vec2)> = Vec::new();
    for t in trails {
        for w in t.windows(2) {
            let (a, b) = (w[0], w[1]);
            let len = a.distance(b);
            if len < 0.5 {
                continue;
            }
            let d = (b - a) / len;
            let n = Vec2::new(-d.y, d.x);
            let steps = (len / 3.0).ceil() as usize;
            for k in 0..steps {
                let p = a + d * (len * (k as f32 + 0.5) / steps as f32);
                for off in [1.0f32, 3.0, 5.5, 8.5, 12.0] {
                    for side in [1.0f32, -1.0] {
                        let q = p + n * side * (s.foot + TRAIL_KEEP + off);
                        if crate::worldmap::tile_biome_world(q.x, q.y) != Some(s.biome) {
                            continue;
                        }
                        let key = match s.seat {
                            Seat::High => -crate::worldmap::ground_at_world(q.x, q.y).unwrap_or(-1e3),
                            _ => rng_next(&mut rng),
                        };
                        out.push((key, q));
                    }
                }
            }
        }
    }
    out.sort_by(|a, b| a.0.total_cmp(&b.0).then(a.1.x.total_cmp(&b.1.x)).then(a.1.y.total_cmp(&b.1.y)));
    out.into_iter().map(|(_, p)| p).collect()
}

/// The yaws to try at a spot: 12 headings, starting from a stable per-spot hash.
fn yaws(scene: usize, q: Vec2) -> impl Iterator<Item = f32> {
    let mut s = q.x.to_bits() ^ q.y.to_bits().rotate_left(16) ^ (scene as u32).wrapping_mul(0x9e37_79b9);
    let y0 = rng_next(&mut s) * TAU;
    (0..24).map(move |k| (y0 + k as f32 * TAU / 24.0) % TAU)
}

/// Seat `scene` once, appending to `planned`. Strict flatness first, then relaxed.
fn seat(scene: usize, planned: &mut Vec<Site>, trails: &[Vec<Vec2>], visual: bool) -> bool {
    let cands = candidates(scene, trails);
    let last = if SCENES[scene].seat == Seat::Open || SCENES[scene].seat == Seat::Rim { FLAT_DELTA_RELAXED } else { FLAT_DELTA_SEAT };
    // A high site takes the highest legal spot at all (flatness only as a gate), the others prefer
    // the flattest ground first.
    let flats: &[f32] = if SCENES[scene].seat == Seat::High { &[FLAT_DELTA_SEAT] } else { &[FLAT_DELTA, FLAT_DELTA_RELAXED, last] };
    for &flat in flats {
        for &q in &cands {
            if !clear_of_others(q, scene, planned, visual) {
                continue;
            }
            let seat_at = |yaw: f32| {
                if !ground_ok(scene, q, yaw, flat, trails) {
                    return None;
                }
                let Seat::Gap(drop) = SCENES[scene].seat else { return Some(0.0) };
                let y0 = crate::worldmap::ground_at_world(q.x, q.y)?;
                let span = gap_span(q, yaw, y0, drop)?;
                let far = q + front(yaw) * span;
                let free = !crate::poi::story_clearings().overlaps(far.x, far.y, FAR_FOOT + 1.0)
                    && !crate::blockers::any_within(far.x, far.y, FAR_FOOT + 0.3)
                    && !(visual && crate::blockers::any_visual_within(far.x, far.y, FAR_FOOT + 0.3))
                    && planned.iter().all(|o| o.pos.distance(far) > FAR_FOOT + SCENES[o.scene].foot + MIN_GAP * 0.5);
                free.then_some(span)
            };
            if let Some((yaw, span)) = yaws(scene, q).find_map(|yaw| seat_at(yaw).map(|span| (yaw, span))) {
                planned.push(Site { scene, pos: q, yaw, span });
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
    let mut planned: Vec<Site> = Vec::new();
    for scene in SEAT_ORDER {
        if !seat(scene, &mut planned, &trails, true) {
            warn!("wild_sites: no spot for {}", SCENES[scene].model);
        }
    }
    for site in &planned {
        crate::blockers::reserve_visual(site.pos.x, site.pos.y, SCENES[site.scene].foot);
        if let Some(far) = site.far() {
            crate::blockers::reserve_visual(far.x, far.y, FAR_FOOT);
        }
        info!("wild_sites: planned {} at {:.1},{:.1} yaw {:.2} span {:.1}", SCENES[site.scene].model, site.pos.x, site.pos.y,
            site.yaw, site.span);
    }
    *SITES.lock().unwrap() = planned;
}

/// Base height: the seated probes' spread, sunk like `stories_cold::seat_y` (never below the lowest
/// seated point) so the downhill edge doesn't float.
fn seat_y(site: &Site) -> f32 {
    let s = &SCENES[site.scene];
    let Some(y0) = crate::worldmap::ground_at_world(site.pos.x, site.pos.y) else { return 0.0 };
    let (mut lo, mut hi) = (y0, y0);
    for d in probes(s.foot).filter(|&d| seated_probe(s.seat, d, site.yaw, s.foot)) {
        if let Some(y) = crate::worldmap::ground_at_world(site.pos.x + d.x, site.pos.y + d.y) {
            lo = lo.min(y);
            hi = hi.max(y);
        }
    }
    (y0 - 0.6 * (hi - lo)).max(lo) - 0.04
}

/// Base height of a gap scene's far anchor: its back-half ground (the probes [`far_anchor_ok`]
/// checked), sunk like [`seat_y`].
fn far_seat_y(far: Vec2, yaw: f32) -> f32 {
    let f = front(yaw);
    let Some(y0) = crate::worldmap::ground_at_world(far.x, far.y) else { return 0.0 };
    let (mut lo, mut hi) = (y0, y0);
    for k in 0..8 {
        let a = k as f32 * (TAU / 8.0);
        let d = Vec2::new(a.cos(), a.sin()) * FAR_FOOT * 0.75;
        if d.dot(f) < -0.3 * FAR_FOOT {
            continue;
        }
        if let Some(y) = crate::worldmap::ground_at_world(far.x + d.x, far.y + d.y) {
            if (y - y0).abs() < 1.3 {
                lo = lo.min(y);
                hi = hi.max(y);
            }
        }
    }
    (y0 - 0.6 * (hi - lo)).max(lo) - 0.04
}

/// The loosest flatness a scene is ever planned on.
fn max_flat(scene: usize) -> f32 {
    match SCENES[scene].seat {
        Seat::Open | Seat::Rim => FLAT_DELTA_RELAXED,
        _ => FLAT_DELTA_SEAT,
    }
}

fn register_blockers(scene: usize, p: Vec2, yaw: f32) {
    let rot = Quat::from_rotation_y(yaw);
    for &(x, z, hw, hd, local_yaw) in SCENES[scene].solids {
        let o = rot * Vec3::new(x, 0.0, z);
        crate::blockers::add_obb(p.x + o.x, p.y + o.z, hw, hd, yaw + local_yaw);
    }
}

/// Build phase 32 (with the other story layers): spawn each planned site, re-siting any a later
/// phase claimed.
pub fn populate(commands: &mut Commands) {
    let Some(kit) = crate::realforest::get().filter(|k| k.has(SCENES[0].model)) else {
        warn!("wild_sites: wild_sites.glb not in the kit \u{2014} no swamp / rocky discovery sites");
        return;
    };
    let range = VisibilityRange { start_margin: 0.0..0.0, end_margin: 120.0..140.0, use_aabb: true };
    let trails = crate::worldmap::pass_trails_world();
    let planned = SITES.lock().unwrap().clone();
    let mut placed: Vec<Site> = Vec::with_capacity(planned.len());
    for (i, site) in planned.iter().enumerate() {
        let s = &SCENES[site.scene];
        let free = ground_ok(site.scene, site.pos, site.yaw, max_flat(site.scene), &trails)
            && !crate::blockers::any_within(site.pos.x, site.pos.y, s.foot + 0.2);
        let site = if free {
            site.clone()
        } else {
            let mut others: Vec<Site> = placed.iter().chain(&planned[i + 1..]).cloned().collect();
            let n = others.len();
            if seat(site.scene, &mut others, &trails, false) {
                let moved = others.swap_remove(n);
                info!("wild_sites: {} at {:.1},{:.1} was claimed, moved to {:.1},{:.1}", s.model, site.pos.x, site.pos.y,
                    moved.pos.x, moved.pos.y);
                moved
            } else if ground_ok(site.scene, site.pos, site.yaw, max_flat(site.scene), &trails)
                && !crate::blockers::any_within(site.pos.x, site.pos.y, s.foot * 0.8)
            {
                warn!("wild_sites: {} at {:.1},{:.1} kept: only its rim is claimed", s.model, site.pos.x, site.pos.y);
                site.clone()
            } else {
                warn!("wild_sites: {} at {:.1},{:.1} was claimed and no other spot is free", s.model, site.pos.x, site.pos.y);
                continue;
            }
        };
        let y = seat_y(&site);
        let tf = Transform::from_xyz(site.pos.x, y, site.pos.y).with_rotation(Quat::from_rotation_y(site.yaw));
        if let Some(e) = kit.spawn_static_with(commands, s.model, tf, range.clone()) {
            commands.entity(e).insert(BiomeEntity);
            crate::landmarks::attach_story(commands, e, s.name, s.lore);
        }
        register_blockers(site.scene, site.pos, site.yaw);
        crate::blockers::reserve_visual(site.pos.x, site.pos.y, s.foot);
        if let Some(far) = site.far() {
            // The far anchor, turned to face back across the gap.
            let yf = far_seat_y(far, site.yaw);
            let far_model = format!("{}_far", s.model);
            let tf = Transform::from_xyz(far.x, yf, far.y).with_rotation(Quat::from_rotation_y(site.yaw + std::f32::consts::PI));
            if let Some(e) = kit.spawn_static_with(commands, &far_model, tf, range.clone()) {
                commands.entity(e).insert(BiomeEntity);
            }
            crate::blockers::add_obb(far.x, far.y, 1.1, 0.45, site.yaw);
            crate::blockers::reserve_visual(far.x, far.y, FAR_FOOT);
            info!("wild_sites: {far_model} at {:.1},{:.1},{:.1} (span {:.1})", far.x, yf, far.y, site.span);
        }
        info!("wild_sites: {} at {:.1},{:.1},{:.1} yaw {:.2}", s.model, site.pos.x, y, site.pos.y, site.yaw);
        placed.push(site);
    }
    info!("wild_sites: {} discovery sites placed", placed.len());
    *SITES.lock().unwrap() = placed;
}

/// Screenshot cameras for every placed site (`FOREST_SHOT_STORIES=wild`, see `capture.rs`): an
/// eye-height view from the scene's front and a higher one from the opposite quarter.
pub fn shot_cams() -> Vec<(String, Transform)> {
    let sites = SITES.lock().unwrap().clone();
    let mut out = Vec::new();
    for site in &sites {
        let s = &SCENES[site.scene];
        let y = seat_y(site);
        let aim = Vec3::new(site.pos.x, y + 1.2, site.pos.y);
        let f = front(site.yaw);
        let (fw, side) = (Vec3::new(f.x, 0.0, f.y), Vec3::new(-f.y, 0.0, f.x));
        let name = s.model.trim_start_matches("site_");
        if let Some(far) = site.far() {
            // Across a gap: from beside the near anchor across to the far one and the bridge hanging
            // down its wall, and from out over the side of the gap taking in both anchors and the
            // drop (both lifted clear of whatever ground is under them).
            let yf = far_seat_y(far, site.yaw);
            let mid = (site.pos + far) * 0.5;
            let side = Vec2::new(-f.y, f.x);
            let rim = y.max(yf);
            let clear = |p: Vec2, lift: f32| {
                let g = crate::worldmap::ground_at_world(p.x, p.y).unwrap_or(crate::worldmap::SEA_Y).max(crate::worldmap::SEA_Y);
                Vec3::new(p.x, g.max(rim) + lift, p.y)
            };
            let e = site.pos - f * 2.5 + side * 2.5;
            let aim_far = Vec3::new(far.x, yf - 1.5, far.y);
            out.push((format!("wild_{name}_near"), Transform::from_translation(clear(e, 2.2)).looking_at(aim_far, Vec3::Y)));
            let e = mid - side * 13.0;
            let aim = Vec3::new(mid.x, rim - 3.0, mid.y);
            out.push((format!("wild_{name}_high"), Transform::from_translation(clear(e, 4.0)).looking_at(aim, Vec3::Y)));
            info!("wild cam {name}: gap span {:.1} near {:.1},{:.1} far {:.1},{:.1}", site.span, site.pos.x, site.pos.y, far.x, far.y);
            continue;
        }
        // The medium shot looks at the scene's story side (a shore scene's from the bank, out over
        // the water; every other from its front quarter).
        let high = if s.seat == Seat::Shore { -fw * 6.0 + side * 7.0 } else { fw * 7.0 + side * 6.0 };
        for (tag, off, lift) in [("near", fw * 8.0 + side * 3.5, 2.2), ("high", high, 8.0)] {
            let e = aim + off;
            let gy = crate::worldmap::ground_at_world(e.x, e.z).unwrap_or(y).max(crate::worldmap::SEA_Y);
            let eye = Vec3::new(e.x, gy.max(y) + lift, e.z);
            info!("wild cam {name}_{tag}: {:.1},{:.1},{:.1} -> {:.1},{:.1},{:.1}", eye.x, eye.y, eye.z, aim.x, aim.y, aim.z);
            out.push((format!("wild_{name}_{tag}"), Transform::from_translation(eye).looking_at(aim, Vec3::Y)));
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn plan_all() {
        crate::blockers::reset();
        crate::poi::plan_clearings();
        crate::stories_warm::plan();
        crate::vignettes::plan();
        crate::wayside::plan();
        crate::stories_cold::plan();
        plan();
    }

    fn reset_all() {
        crate::blockers::reset();
        crate::poi::reset_plan();
        crate::stories_warm::reset_plan();
        crate::vignettes::reset_plan();
        crate::wayside::reset_plan();
        crate::stories_cold::reset_plan();
        reset_plan();
    }

    /// Every site is seated exactly once, in its own biome on legal ground with its seat's terrain
    /// shape, spread apart, never crowding another story piece; names are unique; re-planning
    /// reproduces the very same sites.
    #[test]
    fn wild_sites_plan_seats_every_scene() {
        let _g = crate::blockers::TEST_LOCK.lock().unwrap();
        plan_all();
        let first = SITES.lock().unwrap().clone();
        let trails = crate::worldmap::pass_trails_world();
        for site in &first {
            let y = crate::worldmap::ground_at_world(site.pos.x, site.pos.y).unwrap_or(f32::NAN);
            eprintln!("planned {} at {:.1},{:.1} ground {y:.2} yaw {:.2}", SCENES[site.scene].model, site.pos.x, site.pos.y, site.yaw);
        }
        for (scene, s) in SCENES.iter().enumerate() {
            let n = first.iter().filter(|p| p.scene == scene).count();
            assert_eq!(n, 1, "{} seated {n} times", s.model);
        }
        for (i, a) in first.iter().enumerate() {
            let s = &SCENES[a.scene];
            assert!(ground_ok(a.scene, a.pos, a.yaw, max_flat(a.scene), &trails), "{} on illegal ground at {}", s.model, a.pos);
            assert!(!crate::stories_cold::overlaps_planned(a.pos.x, a.pos.y, s.foot)
                && !crate::stories_warm::overlaps_planned(a.pos.x, a.pos.y, s.foot)
                && !crate::wayside::overlaps_planned(a.pos.x, a.pos.y, s.foot),
                "{} on another story clearing at {}", s.model, a.pos);
            if let Seat::Gap(drop) = s.seat {
                let y0 = crate::worldmap::ground_at_world(a.pos.x, a.pos.y).unwrap();
                assert!(a.span >= 8.0 && gap_span(a.pos, a.yaw, y0, drop) == Some(a.span), "{} not across a real gap", s.model);
            }
            for b in &first[i + 1..] {
                assert!(a.pos.distance(b.pos) > s.foot + SCENES[b.scene].foot + MIN_GAP, "{} crowds {}", s.model, SCENES[b.scene].model);
            }
        }
        let mut names: Vec<&str> = SCENES.iter().map(|s| s.name).collect();
        names.sort_unstable();
        names.dedup();
        assert_eq!(names.len(), SCENES.len(), "site names must be unique (saves match by name)");
        plan_all();
        assert_eq!(*SITES.lock().unwrap(), first, "planning must be deterministic across rebuilds");
        reset_all();
    }

    #[test]
    fn rotated_site_blockers_cover_their_masses() {
        let _g = crate::blockers::TEST_LOCK.lock().unwrap();
        crate::blockers::reset();
        let p = Vec2::new(40.0, 40.0);
        register_blockers(5, p, std::f32::consts::FRAC_PI_2);
        // The clan gong's left menhir (local -1.55, 0) stays blocked with the model turned.
        let o = Quat::from_rotation_y(std::f32::consts::FRAC_PI_2) * Vec3::new(-1.55, 0.0, 0.0);
        assert!(crate::blockers::is_blocked(p.x + o.x, p.y + o.z));
        assert!(!crate::blockers::is_blocked(p.x + 3.2, p.y + 3.2));
        crate::blockers::reset();
    }
}
