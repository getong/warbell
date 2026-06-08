//! **Roads** — worn dirt approach-paths radiating out from the castle gates. Unlike the old
//! draft, these are NOT geometry: [`road_strength`] is a pure query that `worldmap::ground_color`
//! blends into the terrain vertex colour, so a road is just a brown blend in the ground (exactly
//! the original game's paths), with no raised slab to walk over. Distilled from `roads.ts`.

use bevy::prelude::*;

/// Half-width of a track (world units) — full strength within ~40% of this, fading to 0 at the edge.
const HALF_W: f32 = 1.6;
/// How far each road runs out from its gate.
const ROAD_LEN: f32 = 24.0;

/// Distance from point `p` to the segment `a→b`.
fn dist_to_segment(p: Vec2, a: Vec2, b: Vec2) -> f32 {
    let ab = b - a;
    let t = if ab.length_squared() > 1e-6 { ((p - a).dot(ab) / ab.length_squared()).clamp(0.0, 1.0) } else { 0.0 };
    p.distance(a + ab * t)
}

/// How strongly `(wx, wz)` sits on a gate approach-road: 1 at a track centreline, fading to 0
/// by `HALF_W`, and tapering out toward each road's far end so the path fades into the wild.
pub fn road_strength(wx: f32, wz: f32) -> f32 {
    let p = Vec2::new(wx, wz);
    let mut best = 0.0_f32;
    for g in crate::castle::gate_centers() {
        let dir = g.normalize_or_zero();
        if dir == Vec2::ZERO {
            continue;
        }
        let far = g + dir * ROAD_LEN;
        let d = dist_to_segment(p, g, far);
        // Lateral falloff (1 at centre → 0 at HALF_W).
        let lat = 1.0 - (d / HALF_W).clamp(0.0, 1.0);
        // Longitudinal taper: fade the track out over its last third.
        let along = ((p - g).dot(dir) / ROAD_LEN).clamp(0.0, 1.0);
        let taper = (1.0 - (along - 0.66) / 0.34).clamp(0.0, 1.0);
        best = best.max(lat * lat * taper);
    }
    best
}
