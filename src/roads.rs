//! **Roads** — a map-wide network of natural, curving dirt paths linking the castle to every
//! interesting place on the island. NOT geometry: the network is rasterised **once** into a baked
//! [`RoadField`] (a 2-D strength grid), and every consumer just samples it — O(1), allocation-free:
//!
//! * `worldmap::ground_color` blends [`road_strength`] into the terrain vertex colour (the brown
//!   path), exactly like the old draft — same surface as the lawn, no raised slab.
//! * the biome scatter pass rejects any tree / prop / ground-cover that lands [`on_road`], so
//!   **nothing grows on a path**.
//! * `player::movement` reads [`speed_mult`] for a small road-travel speed bonus.
//!
//! The expensive part (jittered Catmull-Rom curves + brush stamping) runs lazily on the first
//! query — which happens during the world's ground bake — and is cached for the process. The field
//! is pure derived data (deterministic from the world seed + map), so it is neither saved nor reset:
//! it regenerates identically on every world build.
//!
//! Design: `docs/superpowers/specs/2026-06-30-organic-road-network-design.md`.

use crate::worldmap::{ground_at_world, GX, GZ, MAP_SCALE};
use bevy::prelude::*;
use std::sync::OnceLock;

// ── Tunables ──────────────────────────────────────────────────────────────────────
/// Road half-width (world units). Full-strength core within [`EDGE`]·HALF_W, fading to 0 at HALF_W.
const HALF_W: f32 = 1.8;
/// Fraction of the half-width that stays full-strength packed earth before the soft edge begins.
const EDGE: f32 = 0.45;
/// Scatter (trees/props/cover) is rejected where the field exceeds this — keeps paths bare. Kept
/// low so the cleared strip matches the *visible* worn-dirt tint (which shows from strength ≈0.1):
/// at a higher cutoff, props kept growing on the tinted road FRINGE — the swamp's flat moss discs
/// read as "green circles on a broken road", and rock-biome paths never cleared a visible corridor.
const GROW_CUTOFF: f32 = 0.12;
/// Movement speed bonus at a road centreline (player moves a *little* faster on a road).
const SPEED_BONUS: f32 = 0.15;
/// Below this field strength a road gives no speed help (so the soft fringe doesn't buff you).
const SPEED_CUTOFF: f32 = 0.25;
/// One wander waypoint roughly every N units of an edge (more → curvier).
const WAYPOINT_SPACING: f32 = 15.0;
/// Lateral wander amplitude (world units), tapered to 0 at both endpoints so curves hit their nodes.
const JITTER: f32 = 7.0;
/// Centreline rasterisation grid cell (world units). Smaller = crisper edges, more memory.
const CELL: f32 = 0.6;
/// At most this many short spurs branch off the trunk/ring network to nearby minor POIs (camps).
const SPUR_CAP: usize = 6;
/// A spur is only drawn if its camp sits within this distance of the existing network.
const SPUR_MAX_LEN: f32 = 36.0;

// ── Mulberry32 (same deterministic RNG the scatter uses) ────────────────────────────
struct Rng(u32);
impl Rng {
    fn next(&mut self) -> f32 {
        self.0 = self.0.wrapping_add(0x6d2b_79f5);
        let mut t = self.0;
        t = (t ^ (t >> 15)).wrapping_mul(t | 1);
        t ^= t.wrapping_add((t ^ (t >> 7)).wrapping_mul(t | 61));
        ((t ^ (t >> 14)) as f32) / 4_294_967_296.0
    }
}

// ── The baked field ─────────────────────────────────────────────────────────────────
/// A 2-D grid of road strength `[0,1]` covering the network's bounding box. `data[z*w + x]`.
struct RoadField {
    ox: f32,
    oz: f32,
    w: usize,
    h: usize,
    data: Vec<f32>,
}

impl RoadField {
    /// Bilinear lookup at world `(wx, wz)`; 0 outside the grid.
    fn sample(&self, wx: f32, wz: f32) -> f32 {
        let fx = (wx - self.ox) / CELL;
        let fz = (wz - self.oz) / CELL;
        if fx < 0.0 || fz < 0.0 || fx >= (self.w - 1) as f32 || fz >= (self.h - 1) as f32 {
            return 0.0;
        }
        let x0 = fx.floor() as usize;
        let z0 = fz.floor() as usize;
        let tx = fx - x0 as f32;
        let tz = fz - z0 as f32;
        let g = |x: usize, z: usize| self.data[z * self.w + x];
        let top = g(x0, z0) * (1.0 - tx) + g(x0 + 1, z0) * tx;
        let bot = g(x0, z0 + 1) * (1.0 - tx) + g(x0 + 1, z0 + 1) * tx;
        top * (1.0 - tz) + bot * tz
    }

    /// Max-blend a round brush (radius `HALF_W`, full-strength core `core`) centred at `pt`.
    fn stamp(&mut self, pt: Vec2, core: f32) {
        let r = HALF_W;
        let minx = (((pt.x - r - self.ox) / CELL).floor() as i32).max(0);
        let maxx = (((pt.x + r - self.ox) / CELL).ceil() as i32).min(self.w as i32 - 1);
        let minz = (((pt.y - r - self.oz) / CELL).floor() as i32).max(0);
        let maxz = (((pt.y + r - self.oz) / CELL).ceil() as i32).min(self.h as i32 - 1);
        for cz in minz..=maxz {
            for cx in minx..=maxx {
                let c = Vec2::new(self.ox + cx as f32 * CELL, self.oz + cz as f32 * CELL);
                let d = c.distance(pt);
                if d > r {
                    continue;
                }
                let s = if d <= core { 1.0 } else { 1.0 - (d - core) / (r - core) };
                let i = cz as usize * self.w + cx as usize;
                if s > self.data[i] {
                    self.data[i] = s;
                }
            }
        }
    }
}

/// Process-lifetime cache. Built on first query (during the ground bake) and reused thereafter.
fn field() -> &'static RoadField {
    static FIELD: OnceLock<RoadField> = OnceLock::new();
    FIELD.get_or_init(build_field)
}

// ── Public query API (all O(1) field samples) ──────────────────────────────────────
/// Road strength `[0,1]` at world `(wx, wz)` — 1 on a centreline, fading to 0 off the path.
/// `worldmap::ground_color` blends this into the terrain as the worn-dirt path tint.
pub fn road_strength(wx: f32, wz: f32) -> f32 {
    field().sample(wx, wz)
}

/// Is world `(wx, wz)` on a path (strongly enough that nothing should grow there)? The biome
/// scatter pass calls this to keep trees / props / ground-cover off the roads.
pub fn on_road(wx: f32, wz: f32) -> bool {
    field().sample(wx, wz) > GROW_CUTOFF
}

/// Movement multiplier at world `(wx, wz)`: 1.0 off-road, ramping to `1 + SPEED_BONUS` on a
/// centreline. The player moves a little faster when travelling by road.
pub fn speed_mult(wx: f32, wz: f32) -> f32 {
    let s = field().sample(wx, wz);
    if s <= SPEED_CUTOFF {
        1.0
    } else {
        1.0 + SPEED_BONUS * ((s - SPEED_CUTOFF) / (1.0 - SPEED_CUTOFF))
    }
}

// ── Network construction (runs once, inside `build_field`) ──────────────────────────
/// The five biome region centres in WORLD space. Base coords mirror `worldmap::REGIONS`
/// (snow / desert / rock / forest / swamp); `world = base·MAP_SCALE − G`.
fn biome_centres() -> [Vec2; 5] {
    [(26.0, 24.0), (101.0, 10.0), (116.0, 57.0), (32.0, 80.0), (72.0, 92.0)]
        .map(|(x, z): (f32, f32)| Vec2::new(x * MAP_SCALE - GX, z * MAP_SCALE - GZ))
}

/// Pull a wander waypoint back onto walkable land if it strayed onto water/off-map — unless it sits
/// on a bridge, where crossing the river IS the point. Bounded; falls back to the straight line.
fn nudge(p: Vec2, toward: Vec2) -> Vec2 {
    let mut q = p;
    for _ in 0..6 {
        if ground_at_world(q.x, q.y).is_some() || crate::bridges::near_bridge(q.x, q.y, HALF_W + 1.5)
        {
            return q;
        }
        q = q.lerp(toward, 0.45);
    }
    toward
}

/// Build one organic curve from `a` to `b`: jittered waypoints (tapered at the ends), bridge
/// centres in the corridor threaded in by position, smoothed through a Catmull-Rom spline.
fn wander(a: Vec2, b: Vec2, seed: u32) -> Vec<Vec2> {
    let len = a.distance(b);
    let dir = (b - a).normalize_or_zero();
    if dir == Vec2::ZERO {
        return vec![a];
    }
    let perp = Vec2::new(-dir.y, dir.x);
    let n = (len / WAYPOINT_SPACING).floor() as i32;
    let mut rng = Rng(seed);

    // (t, point) controls between the endpoints — jittered waypoints…
    let mut mids: Vec<(f32, Vec2)> = Vec::new();
    for i in 1..=n {
        let t = i as f32 / (n as f32 + 1.0);
        let base = a.lerp(b, t);
        let amp = JITTER * (std::f32::consts::PI * t).sin();
        let off = perp * ((rng.next() * 2.0 - 1.0) * amp);
        mids.push((t, nudge(base + off, base)));
    }
    // …and any existing bridge that sits inside this edge's corridor, so a river crossing lands
    // on a real deck. (Bridges follow the rivers, so this stays correct as rivers are reworked.)
    let ab = b - a;
    let len2 = ab.length_squared().max(1e-3);
    for c in crate::bridges::centers() {
        let t = (c - a).dot(ab) / len2;
        if t > 0.05 && t < 0.95 && (a + ab * t).distance(c) < 16.0 {
            mids.push((t, c));
        }
    }
    mids.sort_by(|x, y| x.0.partial_cmp(&y.0).unwrap_or(std::cmp::Ordering::Equal));

    let mut ctrl = Vec::with_capacity(mids.len() + 2);
    ctrl.push(a);
    ctrl.extend(mids.into_iter().map(|(_, p)| p));
    ctrl.push(b);
    catmull(&ctrl)
}

/// Sample a Catmull-Rom spline through `ctrl` into a dense polyline (step ≈ [`CELL`]).
fn catmull(ctrl: &[Vec2]) -> Vec<Vec2> {
    if ctrl.len() < 3 {
        return ctrl.to_vec();
    }
    let mut out = Vec::new();
    for i in 0..ctrl.len() - 1 {
        let p0 = ctrl[i.saturating_sub(1)];
        let p1 = ctrl[i];
        let p2 = ctrl[i + 1];
        let p3 = ctrl[(i + 2).min(ctrl.len() - 1)];
        let steps = (p1.distance(p2) / CELL).ceil().max(1.0) as usize;
        for s in 0..steps {
            let t = s as f32 / steps as f32;
            let t2 = t * t;
            let t3 = t2 * t;
            out.push(
                (p1 * 2.0
                    + (p2 - p0) * t
                    + (p0 * 2.0 - p1 * 5.0 + p2 * 4.0 - p3) * t2
                    + (-p0 + p1 * 3.0 - p2 * 3.0 + p3) * t3)
                    * 0.5,
            );
        }
    }
    out.push(*ctrl.last().unwrap());
    out
}

/// Assemble the whole network — trunks (castle gate → each major place), a ring linking adjacent
/// biomes, and a few capped spurs to nearby camps — as a list of dense centrelines.
fn build_curves() -> Vec<Vec<Vec2>> {
    let gates = crate::castle::gate_centers();
    let biomes = biome_centres();
    let seed = 0x51ED_2A37u32;
    let mut curves: Vec<Vec<Vec2>> = Vec::new();

    // Trunks: each major destination reached from whichever castle gate faces it.
    let mut majors: Vec<Vec2> = biomes.to_vec();
    // Stop at the fortress GATE (on the wall line), NOT its CENTRE — a trunk run to the centre
    // stamped road_dirt straight through the walls and buried the Blight courtyard's beaten-earth
    // texture under flat path brown ("fortress ground texture gone").
    majors.push(crate::ork_fortress::GATE);
    majors.push(crate::rival::RIVAL_CENTRE);
    for (i, t) in majors.iter().enumerate() {
        let gate = *gates
            .iter()
            .min_by(|a, b| a.distance(*t).partial_cmp(&b.distance(*t)).unwrap())
            .unwrap();
        curves.push(wander(gate, *t, seed ^ (i as u32).wrapping_mul(0x9E37_79B9)));
    }

    // Ring: connect biome centres to their angular neighbours so you can circle the island.
    let mut ring = biomes.to_vec();
    ring.sort_by(|a, b| a.y.atan2(a.x).partial_cmp(&b.y.atan2(b.x)).unwrap());
    for i in 0..ring.len() {
        let a = ring[i];
        let b = ring[(i + 1) % ring.len()];
        curves.push(wander(a, b, seed ^ (0x00B5_0000 + i as u32)));
    }

    // Landmark spurs: every biome landmark gets its own path off the nearest network point. These
    // are always drawn (only 5) — a landmark is a destination worth a road. Sites are pre-chosen
    // from the terrain, so they're known here at bake time.
    let net: Vec<Vec2> = curves.iter().flatten().copied().collect();
    for (k, site) in crate::ruins::landmark_sites().iter().enumerate() {
        let near = *net
            .iter()
            .min_by(|a, b| a.distance(site.pos).partial_cmp(&b.distance(site.pos)).unwrap())
            .unwrap();
        curves.push(wander(near, site.pos, seed ^ (0x00C0_0000 + k as u32)));
    }

    // Spurs: shortest connections from the network to nearby camps, capped to stay organic-not-busy.
    let net: Vec<Vec2> = curves.iter().flatten().copied().collect();
    let mut cand: Vec<(f32, Vec2, Vec2)> = crate::camps::cage_positions()
        .iter()
        .map(|(_, camp)| {
            let near = *net
                .iter()
                .min_by(|a, b| a.distance(*camp).partial_cmp(&b.distance(*camp)).unwrap())
                .unwrap();
            (near.distance(*camp), near, *camp)
        })
        .collect();
    cand.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap());
    for (k, (d, near, camp)) in cand.into_iter().enumerate() {
        if k >= SPUR_CAP || d > SPUR_MAX_LEN {
            break; // sorted ascending — once one is too far, the rest are too.
        }
        curves.push(wander(near, camp, seed ^ (0x0077_0000 + k as u32)));
    }
    curves
}

/// Rasterise every curve into the strength grid (the one-time expensive step).
fn build_field() -> RoadField {
    let curves = build_curves();
    let mut lo = Vec2::splat(f32::MAX);
    let mut hi = Vec2::splat(f32::MIN);
    for c in &curves {
        for p in c {
            lo = lo.min(*p);
            hi = hi.max(*p);
        }
    }
    let pad = HALF_W + 3.0;
    lo -= pad;
    hi += pad;
    let w = (((hi.x - lo.x) / CELL).ceil() as usize) + 1;
    let h = (((hi.y - lo.y) / CELL).ceil() as usize) + 1;
    let mut f = RoadField { ox: lo.x, oz: lo.y, w, h, data: vec![0.0; w * h] };

    let core = EDGE * HALF_W;
    for c in &curves {
        for win in c.windows(2) {
            let (p0, p1) = (win[0], win[1]);
            let steps = (p0.distance(p1) / (CELL * 0.7)).ceil().max(1.0) as usize;
            for s in 0..=steps {
                f.stamp(p0.lerp(p1, s as f32 / steps as f32), core);
            }
        }
    }
    f
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn catmull_hits_endpoints() {
        let pts = catmull(&[Vec2::ZERO, Vec2::new(5.0, 2.0), Vec2::new(10.0, 0.0)]);
        assert!(pts.first().unwrap().distance(Vec2::ZERO) < 1e-3);
        assert!(pts.last().unwrap().distance(Vec2::new(10.0, 0.0)) < 1e-3);
        // The smoothed curve should be denser than the 3 control points.
        assert!(pts.len() > 3);
    }

    #[test]
    fn wander_is_deterministic() {
        let a = Vec2::new(-40.0, 0.0);
        let b = Vec2::new(40.0, 10.0);
        let p = wander(a, b, 12345);
        let q = wander(a, b, 12345);
        assert_eq!(p.len(), q.len());
        assert!(p.iter().zip(&q).all(|(x, y)| x.distance(*y) < 1e-6));
    }

    #[test]
    fn stamp_peaks_at_centre_and_decays() {
        let mut f = RoadField { ox: -5.0, oz: -5.0, w: 17, h: 17, data: vec![0.0; 17 * 17] };
        f.stamp(Vec2::ZERO, EDGE * HALF_W);
        let centre = f.sample(0.0, 0.0);
        let edge = f.sample(HALF_W * 0.9, 0.0);
        let off = f.sample(HALF_W + 2.0, 0.0);
        assert!(centre > 0.9, "centre {centre}");
        assert!(edge < centre && edge > 0.0, "edge {edge}");
        assert!(off.abs() < 1e-6, "off {off}");
    }
}
