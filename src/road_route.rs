//! **Slope-aware road routing** — the footpath planner behind `roads::build_curves`.
//!
//! Real footpaths don't run straight at a hill: they follow the contours, take the saddle, zig-zag
//! up a hillside and never go up a cliff. The old network drew each road as a jittered straight
//! line, so a route between two places happily painted up a 45° rock face ("paths often run over
//! unnatural steep slopes"). Now every road is an A* search over a coarse ([`CELL`]-unit) cost grid
//! sampled once from the real ground:
//!
//! * a hard **grade cap** ([`GRADE_MAX`] rise/run along the path) and a hard **side-slope cap**
//!   ([`SLOPE_MAX`], the ground's own steepness under the path) — a road can't climb a cliff or
//!   run across a rock face at all;
//! * a quadratic **grade cost** below the cap — gentle valleys and contours win, and where a road
//!   *must* climb, 16-way connectivity lets it traverse the hillside diagonally (switchbacks
//!   emerge from the search, they aren't authored);
//! * low-frequency **cost noise** so routes over flat ground meander organically instead of
//!   ruling straight lines;
//! * open sea / lakes are impassable, rivers + bog pools cost a bridge-sized toll (arteries get a
//!   deck wherever they cross, `bridges.rs`), and capillaries may not cross water at all.
//!
//! The grid is built once (in parallel, ~90k cells) and searched ~200 times; the raw cell path is
//! Chaikin-smoothed into the dense polyline the road field rasterises.

use crate::worldmap::{ground_at_world, is_open_water_world, COLS, GX, GZ, ROWS};
use bevy::prelude::*;
use std::cmp::Ordering;
use std::collections::BinaryHeap;

/// Grid cell (world units). 2u resolves every hill and terrace while keeping a full-map search
/// cheap (281×320 cells).
const CELL: f32 = 2.0;
/// Steepest grade (rise / run) a road may climb between two cells — ~16°, a stiff mountain path.
pub(crate) const GRADE_MAX: f32 = 0.28;
/// Steepest ground (max gradient under the path) a road may cross even on the contour — ~33°.
/// Catches cliffs/rock faces between cell centres that the along-path grade would miss.
const SLOPE_MAX: f32 = 0.65;
/// Quadratic grade penalty: cost ×(1 + K·g²) — 0.1 → ×1.3, 0.2 → ×2.2, 0.28 → ×3.4.
const GRADE_K: f32 = 30.0;
/// Side-slope penalty: ×(1 + K·s²).
const SLOPE_K: f32 = 1.6;
/// Cost-noise amplitude (± fraction) and wavelength (world units) — the organic meander.
const NOISE_AMP: f32 = 0.28;
const NOISE_WAVE: f32 = 26.0;
/// Extra cost per water cell an artery crosses (a bridge is worth a short detour, not a long one).
const WATER_TOLL: f32 = 18.0;
/// Weighted-A* factor: slightly inadmissible for speed; paths stay near-optimal.
const H_WEIGHT: f32 = 1.15;

const LAND: u8 = 0;
const WATER: u8 = 1; // river / stream / bog pool — bridgeable
const BLOCK: u8 = 2; // sea, lake, castle interior

/// The sampled cost grid.
pub(crate) struct Grid {
    w: i32,
    h: i32,
    y: Vec<f32>,
    slope: Vec<f32>,
    kind: Vec<u8>,
    noise: Vec<f32>,
}

/// What a search may do.
#[derive(Clone, Copy)]
pub(crate) struct Opts<'a> {
    /// May cross rivers / pools (arteries: yes, bridged; capillaries: no).
    pub water: bool,
    /// Camp centres + radius the route should keep clear of (cost ×8 inside).
    pub keep_out: &'a [Vec2],
    pub keep_r: f32,
    /// Give up after this many node expansions (capillaries stay cheap); `usize::MAX` = no limit.
    pub max_expand: usize,
}

fn hash(ix: i32, iz: i32) -> f32 {
    let mut h = (ix as u32).wrapping_mul(0x8da6_b343) ^ (iz as u32).wrapping_mul(0xd816_3841) ^ 0x5bd1_e995;
    h ^= h >> 13;
    h = h.wrapping_mul(0x2c1b_3c6d);
    h ^= h >> 15;
    (h & 0xffff) as f32 / 65535.0
}

fn value_noise(x: f32, z: f32) -> f32 {
    let (ix, iz) = (x.floor() as i32, z.floor() as i32);
    let (fx, fz) = (x - ix as f32, z - iz as f32);
    let (sx, sz) = (fx * fx * (3.0 - 2.0 * fx), fz * fz * (3.0 - 2.0 * fz));
    let a = hash(ix, iz) + (hash(ix + 1, iz) - hash(ix, iz)) * sx;
    let b = hash(ix, iz + 1) + (hash(ix + 1, iz + 1) - hash(ix, iz + 1)) * sx;
    a + (b - a) * sz
}

impl Grid {
    fn world(&self, i: i32, j: i32) -> Vec2 {
        Vec2::new(i as f32 * CELL - GX, j as f32 * CELL - GZ)
    }
    fn cell_of(&self, p: Vec2) -> (i32, i32) {
        (((p.x + GX) / CELL).round() as i32, ((p.y + GZ) / CELL).round() as i32)
    }
    fn idx(&self, i: i32, j: i32) -> Option<usize> {
        (i >= 0 && j >= 0 && i < self.w && j < self.h).then(|| (j * self.w + i) as usize)
    }

    /// Sample the whole map (parallel over rows).
    pub(crate) fn build() -> Grid {
        let w = (COLS as f32 / CELL).ceil() as i32 + 1;
        let h = (ROWS as f32 / CELL).ceil() as i32 + 1;
        let (hx, hz) = (crate::castle::HALF_X - 1.5, crate::castle::HALF_Z - 1.5);
        let rows = crate::par::par_map(h as usize, |j| {
            let mut out = Vec::with_capacity(w as usize);
            for i in 0..w {
                let p = Vec2::new(i as f32 * CELL - GX, j as f32 * CELL - GZ);
                let n = 1.0 + NOISE_AMP * (2.0 * value_noise(p.x / NOISE_WAVE, p.y / NOISE_WAVE) - 1.0);
                let cell = match ground_at_world(p.x, p.y) {
                    _ if p.x.abs() < hx && p.y.abs() < hz => (f32::NAN, 0.0, BLOCK),
                    Some(y) => {
                        // Max one-sided gradient over a ±0.7u cross: any cliff lip / rock face
                        // within the cell's core reads steep (a smoothed central difference would
                        // average a wall away against a flat shelf).
                        let d = 0.7;
                        let mut s = 0.0f32;
                        for (dx, dz) in [(d, 0.0), (-d, 0.0), (0.0, d), (0.0, -d)] {
                            if let Some(q) = ground_at_world(p.x + dx, p.y + dz) {
                                s = s.max((q - y).abs() / d);
                            }
                        }
                        (y, s, LAND)
                    }
                    None if is_open_water_world(p.x, p.y) => (f32::NAN, 0.0, BLOCK),
                    None => (f32::NAN, 0.0, WATER),
                };
                out.push((cell, n));
            }
            out
        });
        let n = (w * h) as usize;
        let (mut y, mut slope, mut kind, mut noise) =
            (Vec::with_capacity(n), Vec::with_capacity(n), Vec::with_capacity(n), Vec::with_capacity(n));
        for ((cy, cs, ck), cn) in rows.into_iter().flatten() {
            y.push(cy);
            slope.push(cs);
            kind.push(ck);
            noise.push(cn);
        }
        Grid { w, h, y, slope, kind, noise }
    }

    /// Nearest passable land cell to `p` (endpoints can sit on a shore / beside a wall).
    fn snap(&self, p: Vec2) -> Option<(i32, i32)> {
        let (ci, cj) = self.cell_of(p);
        let mut best: Option<((i32, i32), f32)> = None;
        for r in 0..=4i32 {
            for dj in -r..=r {
                for di in -r..=r {
                    if di.abs().max(dj.abs()) != r {
                        continue;
                    }
                    let (i, j) = (ci + di, cj + dj);
                    let Some(k) = self.idx(i, j) else { continue };
                    if self.kind[k] != LAND || self.slope[k] > SLOPE_MAX {
                        continue;
                    }
                    let d = self.world(i, j).distance(p);
                    if best.is_none_or(|(_, bd)| d < bd) {
                        best = Some(((i, j), d));
                    }
                }
            }
            if best.is_some() {
                break;
            }
        }
        best.map(|(c, _)| c)
    }

    /// A* from `a` to `b`. Returns the dense smoothed world polyline (exact endpoints), or `None`
    /// when no route exists under the caps.
    pub(crate) fn route(&self, a: Vec2, b: Vec2, o: Opts) -> Option<Vec<Vec2>> {
        let s = self.snap(a)?;
        let g = self.snap(b)?;
        let si = self.idx(s.0, s.1)?;
        let gi = self.idx(g.0, g.1)?;
        let n = (self.w * self.h) as usize;
        let mut cost = vec![f32::INFINITY; n];
        let mut from = vec![u32::MAX; n];
        let mut heap = BinaryHeap::new();
        let goal = self.world(g.0, g.1);
        let hmin = 1.0 - NOISE_AMP;
        let heur = |i: i32, j: i32| self.world(i, j).distance(goal) * hmin * H_WEIGHT;
        cost[si] = 0.0;
        heap.push(Node(heur(s.0, s.1), si as u32));
        let keep_r2 = o.keep_r * o.keep_r;
        let mut expanded = 0usize;
        const NB: [(i32, i32); 16] = [
            (1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1),
            (2, 1), (2, -1), (-2, 1), (-2, -1), (1, 2), (1, -2), (-1, 2), (-1, -2),
        ];
        while let Some(Node(f, k)) = heap.pop() {
            let k = k as usize;
            if k == gi {
                break;
            }
            let (i, j) = ((k as i32) % self.w, (k as i32) / self.w);
            if f - heur(i, j) > cost[k] + 1e-3 {
                continue; // stale entry
            }
            expanded += 1;
            if expanded > o.max_expand {
                return None;
            }
            let here_y = self.last_land_y(k, &from);
            for (di, dj) in NB {
                let (ni, nj) = (i + di, j + dj);
                let Some(nk) = self.idx(ni, nj) else { continue };
                let Some(step) = self.edge(k, nk, i, j, di, dj, here_y, o, keep_r2) else { continue };
                let c = cost[k] + step;
                if c < cost[nk] {
                    cost[nk] = c;
                    from[nk] = k as u32;
                    heap.push(Node(c + heur(ni, nj), nk as u32));
                }
            }
        }
        if !cost[gi].is_finite() {
            return None;
        }
        let mut cells = vec![gi];
        while *cells.last().unwrap() != si {
            cells.push(from[*cells.last().unwrap()] as usize);
        }
        cells.reverse();
        let mut pts: Vec<Vec2> = cells.iter().map(|&k| self.world(k as i32 % self.w, k as i32 / self.w)).collect();
        pts[0] = a;
        *pts.last_mut().unwrap() = b;
        Some(smooth(&pts))
    }

    /// Height to measure the next step's grade from: the cell's own ground, or — on a water cell
    /// (mid-bridge) — the last land cell behind it, so a deck can't launch a cliff climb.
    fn last_land_y(&self, mut k: usize, from: &[u32]) -> f32 {
        for _ in 0..12 {
            if !self.y[k].is_nan() {
                return self.y[k];
            }
            match from[k] {
                u32::MAX => break,
                p => k = p as usize,
            }
        }
        f32::NAN
    }

    /// Cost of stepping `k → nk` (offset `di,dj`), or `None` if forbidden.
    #[allow(clippy::too_many_arguments)]
    fn edge(&self, k: usize, nk: usize, i: i32, j: i32, di: i32, dj: i32, here_y: f32, o: Opts, keep_r2: f32) -> Option<f32> {
        let len = CELL * ((di * di + dj * dj) as f32).sqrt();
        // Knight moves pass over two intermediate cells: both must be passable too.
        let mut water_cells = 0;
        let mut check = |kk: usize| -> Option<()> {
            match self.kind[kk] {
                BLOCK => None,
                WATER if !o.water => None,
                WATER => {
                    water_cells += 1;
                    Some(())
                }
                _ if self.slope[kk] > SLOPE_MAX => None,
                _ => Some(()),
            }
        };
        check(nk)?;
        if di.abs() == 2 || dj.abs() == 2 {
            // The two cells a knight move straddles, e.g. (2,1) → (1,0) and (1,1).
            let mid_a = self.idx(i + di / 2, j + dj / 2)?;
            let mid_b = self.idx(i + di - di / 2, j + dj - dj / 2)?;
            check(mid_a)?;
            check(mid_b)?;
        } else if di != 0 && dj != 0 {
            // Diagonal: don't squeeze between two blocked/cliff cells.
            check(self.idx(i + di, j)?)?;
            check(self.idx(i, j + dj)?)?;
        }
        let ny = self.y[nk];
        let mut mult = 1.0;
        if !ny.is_nan() && !here_y.is_nan() {
            // Over a bridge (here_y from the bank behind), measure across the whole span.
            let grade = (ny - here_y).abs() / len;
            if grade > GRADE_MAX && self.kind[k] == LAND {
                return None;
            }
            if grade > GRADE_MAX * 1.6 {
                return None; // far bank is a cliff
            }
            let s = self.slope[nk];
            mult = (1.0 + GRADE_K * grade * grade) * (1.0 + SLOPE_K * s * s);
        }
        mult *= self.noise[nk];
        let p = self.world(i + di, j + dj);
        if o.keep_out.iter().any(|c| c.distance_squared(p) < keep_r2) {
            mult *= 8.0;
        }
        Some(len * mult + water_cells as f32 * WATER_TOLL)
    }
}

#[derive(PartialEq)]
struct Node(f32, u32);
impl Eq for Node {}
impl PartialOrd for Node {
    fn partial_cmp(&self, o: &Self) -> Option<Ordering> {
        Some(self.cmp(o))
    }
}
impl Ord for Node {
    fn cmp(&self, o: &Self) -> Ordering {
        o.0.partial_cmp(&self.0).unwrap_or(Ordering::Equal).then(o.1.cmp(&self.1))
    }
}

/// Chaikin corner-cutting (3 rounds, endpoints pinned) then resample to ~0.6u. Stays inside the
/// cell path's hull — a switchback's legs stay on their contours instead of being cut across.
fn smooth(pts: &[Vec2]) -> Vec<Vec2> {
    let mut p = pts.to_vec();
    for _ in 0..3 {
        if p.len() < 3 {
            break;
        }
        let mut q = Vec::with_capacity(p.len() * 2);
        q.push(p[0]);
        for w in p.windows(2) {
            q.push(w[0].lerp(w[1], 0.25));
            q.push(w[0].lerp(w[1], 0.75));
        }
        q.push(*p.last().unwrap());
        p = q;
    }
    let mut out = vec![p[0]];
    for w in p.windows(2) {
        let steps = (w[0].distance(w[1]) / 0.6).ceil().max(1.0) as usize;
        for s in 1..=steps {
            out.push(w[0].lerp(w[1], s as f32 / steps as f32));
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn smooth_pins_endpoints() {
        let p = smooth(&[Vec2::ZERO, Vec2::new(4.0, 0.0), Vec2::new(4.0, 4.0)]);
        assert!(p[0].distance(Vec2::ZERO) < 1e-4);
        assert!(p.last().unwrap().distance(Vec2::new(4.0, 4.0)) < 1e-4);
        assert!(p.windows(2).all(|w| w[0].distance(w[1]) < 0.7));
    }
}
