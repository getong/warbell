//! **Forest nav-grid** — wires core's tested 8-direction A* (`tileworld_core::pathfinding`) to
//! forest's world-space terrain + blockers so night-wave invaders route to the keep **through the
//! gates** instead of smearing along the walls. Walls register collision boxes (impassable); gate
//! gaps register none (open) → A* threads them with no explicit gate-targeting code.
//!
//! Coordinate frame: forest is world-space `f32` with the castle at the origin; one tile = one
//! world unit; `tile = floor(world + G)`. We map a forest tile ↔ a core `PathPoint` (tile+0.5),
//! and the edge-midpoint `wall_at` test (in core) is what opens gates while blocking walls.

use bevy::prelude::*;
use std::cell::RefCell;
use tileworld_core::pathfinding::{find_path_with_workspace, Grid, PathPoint, PathWorkspace};

use crate::blockers;
use crate::worldmap::{COLS, GROUND_STEP, GX, GZ, ROWS};

/// A* node budget for the invader keep-march. The spawn ring is 30 tiles out, but on the enlarged
/// map an invader spawned across one of the four rivers must detour to a bridge, so the explored
/// set can far exceed the straight-line tile count. 1400 truncated those detours to an *empty*
/// path (idle invader); 6000 covered the worst river detour at MAP_SCALE 2.2, re-sized to 8400
/// for the 2.6 bump (budget ∝ tile count ∝ MAP_SCALE²) — now DERIVED from `MAP_SCALE` (8400 at
/// 2.6, ≈18 900 at 3.9) so a scale bump can't silently starve it again. Since the keep is always
/// reachable, A* terminates as soon as it's found — the larger budget only costs on a
/// (never-occurring for invaders) unreachable goal, where the open set drains to the cap.
pub const NAV_MAX_NODES: u32 =
    (8400.0 * (crate::worldmap::MAP_SCALE / 2.6) * (crate::worldmap::MAP_SCALE / 2.6)) as u32;

/// World centre of tile `(ix, iz)` in forest world-space (castle at origin).
#[inline]
fn tile_world_centre(ix: i32, iz: i32) -> (f32, f32) {
    (ix as f32 - GX + 0.5, iz as f32 - GZ + 0.5)
}

/// Forest's terrain + blocker set, viewed as a pathfinding `Grid`. Tile-centre heights come
/// from `worldmap::tile_centre_ground` — a per-map baked flat array (terrain is static per
/// map), so A*'s many re-reads of the same tiles are single array loads. This replaced a
/// per-`find_path` `RefCell<HashMap>` memo (which re-derived every tile once per search —
/// measured at ~208ms for one long-haul stone-miner search before any caching existed).
/// Blockers/bridges stay live queries: walls ARE built and razed mid-run.
///
/// `blocks` is one read lock for the whole search. A* calls [`crate::blockers::BlockView::is_blocked`]
/// on every neighbour; taking that lock per sample was most of the remaining query cost once the
/// obstacles themselves were tile-bucketed.
pub struct ForestGrid<'a> {
    blocks: &'a crate::blockers::BlockView,
    /// Extra world boxes `(cx, cz, hw, hd)` solid for THIS search only — the shut castle gates
    /// for an ork's route (`gates::Gates::ork_boxes`); empty for everyone else.
    extra: &'a [(f32, f32, f32, f32)],
}

impl ForestGrid<'_> {
    fn blocked(&self, wx: f32, wz: f32) -> bool {
        self.blocks.is_blocked(wx, wz)
            || self.extra.iter().any(|&(cx, cz, hw, hd)| (wx - cx).abs() <= hw && (wz - cz).abs() <= hd)
    }
}

impl ForestGrid<'_> {
    fn height_at(&self, ix: i32, iz: i32) -> Option<f32> {
        crate::worldmap::tile_centre_ground(ix, iz)
    }
}

impl Grid for ForestGrid<'_> {
    fn cols(&self) -> i32 {
        COLS
    }
    fn rows(&self) -> i32 {
        ROWS
    }
    fn standable(&self, ix: i32, iz: i32) -> bool {
        // Land (not water / off-map) OR a bridge deck spanning the river — so A* (and the night
        // invaders) can cross the water at a crossing instead of routing all the way around.
        if self.height_at(ix, iz).is_some() {
            return true;
        }
        let (wx, wz) = tile_world_centre(ix, iz);
        crate::bridges::is_on_bridge(wx, wz)
    }
    fn obstacle_tile(&self, ix: i32, iz: i32) -> bool {
        let (wx, wz) = tile_world_centre(ix, iz);
        self.blocked(wx, wz) // a prop / keep / wall box (or a shut gate, for orks) on this tile centre
    }
    fn wall_at(&self, px: f64, pz: f64) -> bool {
        // Core passes continuous coords in ITS grid space (tile+0.5); convert back to forest
        // world. This edge-midpoint test rejects steps crossing a wall while leaving gaps open.
        self.blocked(px as f32 - GX, pz as f32 - GZ)
    }
    fn can_step(&self, fx: i32, fz: i32, tx: i32, tz: i32) -> bool {
        // Effective walk height: terrain, or a bridge deck over the river. Without the deck
        // fallback a bridge tile is `standable` but no step INTO it ever passes (its terrain
        // height is `None`), so A* could never actually use a crossing.
        let eff = |ix: i32, iz: i32| {
            self.height_at(ix, iz).or_else(|| {
                let (wx, wz) = tile_world_centre(ix, iz);
                crate::bridges::deck_y_at(wx, wz)
            })
        };
        match (eff(fx, fz), eff(tx, tz)) {
            (Some(fy), Some(ty)) => (ty - fy).abs() <= GROUND_STEP + 0.1, // ≤1 height class
            _ => false,
        }
    }
}

/// Forest world XZ → a core `PathPoint` (`find_path` floors internally).
fn world_to_pathpoint(wx: f32, wz: f32) -> PathPoint {
    PathPoint { x: (wx + GX) as f64, z: (wz + GZ) as f64 }
}

/// A* waypoints from `from` to `to` in forest world-space (empty if no route / already there).
pub fn path_to(from: Vec2, to: Vec2) -> Vec<Vec2> {
    path_to_budget(from, to, NAV_MAX_NODES)
}

/// [`path_to`] with an explicit node budget — the default [`NAV_MAX_NODES`] is sized for the
/// ~40-tile invader run to the keep and **exhausts (→ empty) on cross-island trips** like the
/// stone miner's castle→Rocky haul (~100 tiles + river detours). On an unreachable goal A*
/// drains the open set and exits early, so a generous budget only costs when a route exists.
pub fn path_to_budget(from: Vec2, to: Vec2, max_nodes: u32) -> Vec<Vec2> {
    path_to_avoiding(from, to, max_nodes, &[])
}

/// [`path_to_budget`] that also treats `extra` world boxes `(cx, cz, hw, hd)` as solid — an ork's
/// route around the shut castle gates (`gates::Gates::ork_boxes`), which the hero/townsfolk pass.
pub fn path_to_avoiding(from: Vec2, to: Vec2, max_nodes: u32, extra: &[(f32, f32, f32, f32)]) -> Vec<Vec2> {
    // Each scheduler thread owns its scratch space; independent searches never share mutable
    // buffers or hold a global navigation mutex. Search generations still query live blockers.
    thread_local! { static WORK: RefCell<PathWorkspace> = RefCell::default(); }
    let blocks = blockers::read();
    WORK.with_borrow_mut(|work| find_path_with_workspace(
        &ForestGrid { blocks: &blocks, extra }, world_to_pathpoint(from.x, from.y),
        world_to_pathpoint(to.x, to.y), max_nodes, work,
    ))
        .into_iter()
        .map(|p| Vec2::new(p.x as f32 - GX, p.z as f32 - GZ))
        .collect()
}

/// Can a body of radius `r` walk the straight line `a → b`? Samples every 0.25u: each point must
/// keep `r` off every blocker and stay on footing within one terrace step of the last sample.
pub fn clear_line(view: &blockers::BlockView, a: Vec2, b: Vec2, r: f32) -> bool {
    let len = a.distance(b);
    let n = (len / 0.25).ceil().max(1.0) as i32;
    let mut y = crate::steer::footing(a.x, a.y);
    for i in 1..=n {
        let q = a.lerp(b, i as f32 / n as f32);
        if view.any_within(q.x, q.y, r) {
            return false;
        }
        let qy = crate::steer::footing(q.x, q.y);
        match (y, qy) {
            (Some(p), Some(c)) if (p - c).abs() <= crate::steer::MAX_STEP => y = qy,
            _ => return false,
        }
    }
    true
}

/// **String-pull** an A* route: from `from`, jump to the farthest waypoint still reachable in a
/// straight clear line ([`clear_line`]), so a walker cuts the tile staircase into a few long,
/// natural legs instead of zig-zagging from tile centre to tile centre.
pub fn smooth_path(from: Vec2, pts: &[Vec2], r: f32) -> Vec<Vec2> {
    let view = blockers::read();
    let mut out = Vec::new();
    let mut at = from;
    let mut i = 0;
    while i < pts.len() {
        let mut j = pts.len() - 1;
        while j > i && !clear_line(&view, at, pts[j], r) {
            j -= 1;
        }
        out.push(pts[j]);
        at = pts[j];
        i = j + 1;
    }
    out
}

/// The nearest point to `p` (searching rings out to ~3.2u) that keeps a body of radius `r` clear
/// of every blocker — so an activity spot drawn against a prop is approached from beside it, not
/// from inside it. Returns `p` itself when it's already clear (or nothing clear is near).
pub fn free_point(p: Vec2, r: f32) -> Vec2 {
    let view = blockers::read();
    if !view.any_within(p.x, p.y, r) {
        return p;
    }
    for ring in 1..=16 {
        let d = ring as f32 * 0.2;
        for k in 0..12 {
            let a = k as f32 * std::f32::consts::TAU / 12.0;
            let q = p + Vec2::new(a.cos(), a.sin()) * d;
            if !view.any_within(q.x, q.y, r) && crate::steer::footing(q.x, q.y).is_some() {
                return q;
            }
        }
    }
    p
}

/// A cached A* route (followed + smoothed by `steer::advance`) — the keep-march of a wave
/// invader, or a freed captive's march home to the courtyard. Both thread the gates this way.
#[derive(Component, Default)]
pub struct NavPath {
    pub waypoints: Vec<Vec2>,
    pub cursor: usize,
    /// Game-time at which to recompute (throttled + staggered per invader).
    pub next_replan: f32,
    /// The goal the cached path was computed for (replan if it moves).
    pub goal_cached: Vec2,
}

impl NavPath {
    /// Spread a large explicit group order across ~9 frames at 60fps. Local steering starts
    /// immediately; expensive routing follows within 150ms rather than in one frame for all units.
    pub fn staggered(now: f32, entity: Entity) -> Self {
        Self { next_replan: now + (entity.to_bits() % 16) as f32 * 0.01, ..default() }
    }

    pub fn refresh_due(&self, now: f32) -> bool {
        tileworld_core::pathfinding::replan_due(now as f64, self.next_replan as f64,
            self.cursor >= self.waypoints.len(), false, true)
    }

    pub fn pursuit_due(&self, now: f32, goal: Vec2) -> bool {
        tileworld_core::pathfinding::replan_due(now as f64, self.next_replan as f64,
            self.cursor >= self.waypoints.len(), self.goal_cached.distance(goal) > 2.0, false)
    }
}
