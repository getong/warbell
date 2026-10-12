//! **Trap pockets** — ground the hero can drop INTO but never climb back out of.
//!
//! The hero may step down any ledge (he drops, gravity takes over) but may only climb one terrace
//! class (`steer::MAX_STEP`) and only up ground no steeper than the walk limit. Wherever the
//! terrain closes a hollow with walls/slopes past those limits — a V-crevice between two rock
//! faces in the massif, a pit between mesa shelves, a sunken gully end — a hero who jumps or
//! slides in is wedged for good ("places in the mountains where you get stuck and can't get out").
//!
//! This module finds every such pocket exactly the way the controller moves: it floods a
//! [`STEP`]-unit lattice of the real ground FORWARD from the hero's spawn (walk + hop edges) and
//! BACKWARD to it; a cell reachable but unable to return is a trap. Pockets are then handled at
//! their rim: [`blocks_entry`] refuses any move from safe ground into a trap cell (the hollow reads
//! as an edge you can't step over), and a hero already inside one (an old save, a knock-back, the
//! mask still baking) is let [`in_trap`]-scramble out past the slope/step limits.
//!
//! The mask is pure derived data (deterministic from the map), baked on a background thread the
//! first time the hero moves, so it adds nothing to world generation. Debug report:
//! `cargo test --release trap_pockets -- --nocapture`.

use crate::worldmap::{self, COLS, GX, GZ, ROWS};
use bevy::prelude::*;
use std::sync::OnceLock;

/// Lattice spacing (world units) — about two hero radii.
pub(crate) const STEP: f32 = 0.5;
/// Mirrors `player::movement::MAX_WALK_TAN` (asserted equal in its tests).
pub(crate) const WALK_TAN: f32 = 1.1106;
/// Height a standing hop gains over a ledge (apex 1.06 for JUMP_SPEED 6.5 / GRAVITY 20, minus a
/// margin for the footprint clearing the lip).
const HOP_RISE: f32 = 0.9;
/// Lattice offsets a hop covers (≤ ~1.1u horizontally).
const HOP: [(i32, i32); 12] = [
    (2, 0), (-2, 0), (0, 2), (0, -2), (1, 1), (1, -1), (-1, 1), (-1, -1), (2, 1), (-2, -1), (1, -2), (-1, 2),
];
const WALK: [(i32, i32); 4] = [(1, 0), (-1, 0), (0, 1), (0, -1)];

/// A sampled lattice of the ground: footing height (NaN = water / off-map) and slope.
pub(crate) struct Lattice {
    pub w: i32,
    pub h: i32,
    ox: f32,
    oz: f32,
    pub ys: Vec<f32>,
    pub slope: Vec<f32>,
}

fn minmod(a: f32, b: f32) -> f32 {
    if a * b <= 0.0 {
        0.0
    } else if a.abs() < b.abs() {
        a
    } else {
        b
    }
}

impl Lattice {
    /// Sample `ground` over `[ox, ox + w·STEP) × [oz, oz + h·STEP)`.
    pub(crate) fn sample(ox: f32, oz: f32, w: i32, h: i32, ground: &(dyn Fn(f32, f32) -> Option<f32> + Sync)) -> Lattice {
        let row = |j: usize| {
            (0..w).map(|i| ground(ox + i as f32 * STEP, oz + j as f32 * STEP).unwrap_or(f32::NAN)).collect::<Vec<f32>>()
        };
        // In-game the bake runs on one background thread (never steals the render's cores);
        // tests fan out.
        let rows: Vec<Vec<f32>> = if cfg!(test) { crate::par::par_map(h as usize, row) } else { (0..h as usize).map(row).collect() };
        let ys: Vec<f32> = rows.into_iter().flatten().collect();
        let at = |i: i32, j: i32| if i < 0 || j < 0 || i >= w || j >= h { f32::NAN } else { ys[(j * w + i) as usize] };
        let mut slope = vec![0.0f32; ys.len()];
        for j in 0..h {
            for i in 0..w {
                let c = at(i, j);
                if c.is_nan() {
                    continue;
                }
                let d = |a: f32| if a.is_nan() { 0.0 } else { a };
                let gx = minmod(d(c - at(i - 1, j)) / STEP, d(at(i + 1, j) - c) / STEP);
                let gz = minmod(d(c - at(i, j - 1)) / STEP, d(at(i, j + 1) - c) / STEP);
                slope[(j * w + i) as usize] = gx.hypot(gz);
            }
        }
        Lattice { w, h, ox, oz, ys, slope }
    }

    /// The whole active map. With `solids`, cells the hero's body can't occupy (rocks, walls,
    /// trunks — `blockers`) are no footing: a ledge drop into a gap walled by boulders is a pocket
    /// as surely as a terrain pit.
    fn of_map(solids: bool) -> Lattice {
        let footing = |x: f32, z: f32| {
            if solids && crate::blockers::any_within(x, z, 0.22) {
                return None;
            }
            worldmap::ground_at_world(x, z).or_else(|| crate::bridges::deck_y_at(x, z))
        };
        Lattice::sample(-GX, -GZ, (COLS as f32 / STEP) as i32, (ROWS as f32 / STEP) as i32, &footing)
    }

    pub(crate) fn cell(&self, p: Vec2) -> Option<usize> {
        let i = ((p.x - self.ox) / STEP).round() as i32;
        let j = ((p.y - self.oz) / STEP).round() as i32;
        (i >= 0 && j >= 0 && i < self.w && j < self.h).then(|| (j * self.w + i) as usize)
    }

    pub(crate) fn pos(&self, k: usize) -> Vec2 {
        let (i, j) = ((k as i32) % self.w, (k as i32) / self.w);
        Vec2::new(self.ox + i as f32 * STEP, self.oz + j as f32 * STEP)
    }

    /// Can the hero get from cell `a` to the neighbouring cell `b` (offset `off`)?
    fn edge(&self, a: usize, b: usize, hop: bool) -> bool {
        let (ya, yb) = (self.ys[a], self.ys[b]);
        if ya.is_nan() || yb.is_nan() {
            return false;
        }
        if hop {
            // A standing hop: needs walkable footing to push off.
            return self.slope[a] <= WALK_TAN && yb <= ya + HOP_RISE;
        }
        yb <= ya + crate::steer::MAX_STEP && (yb <= ya + 1e-3 || self.slope[b] <= WALK_TAN)
    }

    fn step(&self, k: usize, (di, dj): (i32, i32)) -> Option<usize> {
        let (i, j) = ((k as i32) % self.w + di, (k as i32) / self.w + dj);
        (i >= 0 && j >= 0 && i < self.w && j < self.h).then(|| (j * self.w + i) as usize)
    }

    /// Trap mask: cells reachable from `start` that cannot get back to it.
    pub(crate) fn traps(&self, start: Vec2) -> Vec<bool> {
        let n = self.ys.len();
        let Some(s) = self.cell(start) else { return vec![false; n] };
        let moves = || WALK.iter().map(|o| (*o, false)).chain(HOP.iter().map(|o| (*o, true)));
        let flood = |forward: bool| {
            let mut seen = vec![false; n];
            seen[s] = true;
            let mut q = vec![s];
            while let Some(a) = q.pop() {
                for (o, hop) in moves() {
                    let Some(b) = self.step(a, o) else { continue };
                    // Backward: is there an edge b → a (b steps INTO the reached set)?
                    let ok = if forward { self.edge(a, b, hop) } else { self.edge(b, a, hop) };
                    if ok && !seen[b] {
                        seen[b] = true;
                        q.push(b);
                    }
                }
            }
            seen
        };
        let (fwd, back) = (flood(true), flood(false));
        fwd.iter().zip(&back).map(|(f, b)| *f && !*b).collect()
    }
}

/// One connected trap pocket: centroid, area (u²) and its floor/rim heights.
#[derive(Debug, Clone)]
#[allow(dead_code)] // centre/floor read by the debug report test
pub(crate) struct Pocket {
    pub centre: Vec2,
    pub area: f32,
    pub floor_y: f32,
}

/// Group the trap cells into 8-connected pockets, largest first.
pub(crate) fn pockets(l: &Lattice, trap: &[bool]) -> Vec<Pocket> {
    let mut seen = vec![false; trap.len()];
    let mut out = Vec::new();
    for k0 in 0..trap.len() {
        if !trap[k0] || seen[k0] {
            continue;
        }
        seen[k0] = true;
        let (mut q, mut sum, mut cnt, mut floor) = (vec![k0], Vec2::ZERO, 0usize, f32::MAX);
        while let Some(k) = q.pop() {
            sum += l.pos(k);
            cnt += 1;
            floor = floor.min(l.ys[k]);
            for dj in -1..=1 {
                for di in -1..=1 {
                    if let Some(b) = l.step(k, (di, dj)) {
                        if trap[b] && !seen[b] {
                            seen[b] = true;
                            q.push(b);
                        }
                    }
                }
            }
        }
        out.push(Pocket { centre: sum / cnt as f32, area: cnt as f32 * STEP * STEP, floor_y: floor });
    }
    out.sort_by(|a, b| b.area.partial_cmp(&a.area).unwrap());
    out
}

// ── Runtime mask ─────────────────────────────────────────────────────────────────
struct Mask {
    map: u8,
    lattice: Lattice,
    trap: Vec<bool>,
}

static MASK: OnceLock<Mask> = OnceLock::new();
static STARTED: std::sync::Once = std::sync::Once::new();

/// The baked mask for the active map, kicking off the background bake on first call. `None`
/// while baking (and in the skirmish arena, whose open island has no pockets worth the bake).
fn mask() -> Option<&'static Mask> {
    if worldmap::is_arena() {
        return None;
    }
    STARTED.call_once(|| {
        let map = worldmap::current_map_u8();
        std::thread::Builder::new()
            .name("trap-mask".into())
            .spawn(move || {
                let t = std::time::Instant::now();
                let lattice = Lattice::of_map(true);
                let (spawn, _) = crate::player::spawn_point();
                let trap = lattice.traps(spawn);
                let ps = pockets(&lattice, &trap);
                info!(
                    "traps: {} trap pockets ({:.0} u²) rim-blocked, baked in {:.0} ms",
                    ps.len(),
                    ps.iter().map(|p| p.area).sum::<f32>(),
                    t.elapsed().as_secs_f64() * 1000.0
                );
                let _ = MASK.set(Mask { map, lattice, trap });
            })
            .ok();
    });
    MASK.get().filter(|m| m.map == worldmap::current_map_u8())
}

fn trap_at(m: &Mask, p: Vec2) -> bool {
    m.lattice.cell(p).is_some_and(|k| m.trap[k])
}

/// Is the hero standing in a trap pocket (he may scramble out past the climb limits)?
pub fn in_trap(p: Vec2) -> bool {
    mask().is_some_and(|m| trap_at(m, p))
}

/// Would stepping from `from` to `to` drop the hero into a pocket he can't leave? (Moves within
/// or out of a pocket are never refused — only crossing its rim from safe ground.)
pub fn blocks_entry(from: Vec2, to: Vec2) -> bool {
    mask().is_some_and(|m| trap_at(m, to) && !trap_at(m, from))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// A conical pit (walls past the walk limit) cut into flat ground: the analysis must flag
    /// its floor as a trap, and leave the flat around it (and a gentle bowl) alone.
    #[test]
    fn steep_pit_is_a_trap_gentle_bowl_is_not() {
        let pit = |x: f32, z: f32| {
            let r = (x - 10.0).hypot(z);
            let bowl = (x + 10.0).hypot(z);
            Some(-(3.0 - r * 2.0).max(0.0) - (3.0 - bowl * 0.4).max(0.0))
        };
        let l = Lattice::sample(-20.0, -10.0, 80, 40, &pit);
        let trap = l.traps(Vec2::new(0.0, 8.0));
        let at = |p: Vec2| trap[l.cell(p).unwrap()];
        assert!(at(Vec2::new(10.0, 0.0)), "the steep pit's floor must read as a trap");
        assert!(!at(Vec2::new(-10.0, 0.0)), "a walkable bowl is not a trap");
        assert!(!at(Vec2::new(0.0, 0.0)), "open flat ground is not a trap");
        let ps = pockets(&l, &trap);
        assert_eq!(ps.len(), 1, "{ps:?}");
        assert!(ps[0].centre.distance(Vec2::new(10.0, 0.0)) < 0.6);
    }

    /// The real map: report every trap pocket (the "wedged in the mountains" spots). Run with
    /// `--nocapture` for the list. Guards against world-gen regressions that would open many new
    /// pits: the total area must stay a sliver of the island.
    #[test]
    fn trap_pockets_on_the_map() {
        let t = std::time::Instant::now();
        let l = Lattice::of_map(false);
        let (spawn, _) = crate::player::spawn_point();
        let trap = l.traps(spawn);
        let ps = pockets(&l, &trap);
        let reach = l.ys.iter().filter(|y| !y.is_nan()).count() as f32 * STEP * STEP;
        let area: f32 = ps.iter().map(|p| p.area).sum();
        println!("trap pockets: {} totalling {area:.0} u² of {reach:.0} u² land (analysed in {:?})", ps.len(), t.elapsed());
        for p in ps.iter().take(25) {
            println!("  pocket at ({:.1}, {:.1}) area {:.1} u² floor y {:.2} biome {:?}", p.centre.x, p.centre.y, p.area, p.floor_y, worldmap::biome_at_world(p.centre.x, p.centre.y));
        }
        assert!(area < reach * 0.01, "trap pockets cover {area:.0} u² — world-gen opened enclosed pits");
    }
}
