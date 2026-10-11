//! Lived-in ground under and around the castle (map-centre rework, phase 1 — see
//! `docs/superpowers/specs/2026-10-11-centrum-mapy-design.md` §4).
//!
//! The castle used to stand on one flat lawn with a packed-earth tint under the plaza and gate
//! paths. A real castle yard (KCD2's Trosky / Kuttenberg) is a mosaic of WEAR instead: cart lanes
//! trodden to bare mud from every gate, with twin wheel ruts and puddles standing in them; a
//! trampled plaza where the muster forms; a guard path worn along the inside of the walls while
//! the grass survives in tufts right against the stones and in the quiet corners; mud around the
//! well, debris and chips around the wood yard and the hay store.
//!
//! None of this is geometry. It is written into the two baked masks the terrain shader already
//! reads, so it is the SAME surface as the meadow around it:
//! - the realforest floor mask (`realforest::bake_mask`): R = scanned-floor weight, G = trail
//!   (→ the scanned soil + pebble "path" layer, with POM and its puddles), A = grove density
//!   (high A switches the floor from moss to the litter layer — read here as chips and straw);
//! - the wheel-rut mask (`roads::bake_rut_mask`): [`rut_lanes`] are stamped as cart arteries, so
//!   the shader presses grooves and pools water in them exactly like on the island's roads.

use bevy::math::Vec2;

use crate::castle::{COURTYARD, HALF_X, HALF_Z, KEEP_FRONT, MARKET_CENTRE, N_GATE_X, S_GATE_X, W_GATE_Z};

/// What the castle ground wants at one world point. All 0..1.
#[derive(Clone, Copy, Debug, Default, PartialEq)]
pub struct CastleGround {
    /// Scanned-floor weight (realforest mask R): how far the procedural meadow gives way.
    pub floor: f32,
    /// Trodden-earth strength (mask G). Kept ≤ ~0.86 off the lane centrelines: the shader turns
    /// G > 0.88 without a rut into the grass strip a cart path keeps between its wheel tracks.
    pub path: f32,
    /// Debris (mask A, the grove field): chips / straw / litter instead of moss.
    pub debris: f32,
}

/// World bounds the castle ground can touch (beyond it [`sample`] is all zero): the walls plus
/// the ~16u lawn feather outside them.
pub const REACH_X: f32 = 31.0 + 16.0; // the enceinte's E corner is at x 31
pub const REACH_Z: f32 = HALF_Z + 16.0;

/// Cart lanes, gate by gate (castle v2: W main, S under the bell, N postern; the east wall is
/// solid): from the courtyard rim, through the gate gap, a short leg out onto the approach (where
/// the island's own road trunk, which starts at the gate centre, takes over — running the lane
/// further drew a second, offset verge beside the road). Gently bent inside — carts never run a
/// ruler line. World XZ; the gate centre (`castle::Gate::center`) is always the third point.
const LANES: [[Vec2; 4]; 3] = [
    // North postern → down past the keep's east flank to the keep apron.
    [
        Vec2::new(N_GATE_X - 1.6, KEEP_FRONT + 0.6),
        Vec2::new(N_GATE_X + 0.35, -HALF_Z + 4.6),
        Vec2::new(N_GATE_X, -HALF_Z),
        Vec2::new(N_GATE_X, -HALF_Z - 5.0),
    ],
    // South gate (under the bell tower) → straight up the courtyard.
    [
        Vec2::new(S_GATE_X + 0.6, HALF_Z - 9.0),
        Vec2::new(S_GATE_X + 0.2, HALF_Z - 4.0),
        Vec2::new(S_GATE_X, HALF_Z),
        Vec2::new(S_GATE_X, HALF_Z + 5.0),
    ],
    // West main gate (the market square lies outside it now) → the courtyard's west rim.
    [
        Vec2::new(-COURTYARD.2 + 2.0, W_GATE_Z + 0.6),
        Vec2::new(-20.0, W_GATE_Z - 0.35),
        Vec2::new(-HALF_X, W_GATE_Z),
        Vec2::new(-HALF_X - 5.0, W_GATE_Z),
    ],
];

/// The cart lanes as polylines, for the wheel-rut bake.
pub fn rut_lanes() -> impl Iterator<Item = &'static [Vec2]> {
    LANES.iter().map(|l| l.as_slice())
}

fn hash(ix: i32, iz: i32, seed: u32) -> f32 {
    let mut h = (ix as u32).wrapping_mul(0x8da6_b343) ^ (iz as u32).wrapping_mul(0xd816_3841) ^ seed.wrapping_mul(0xcb1a_b31f);
    h ^= h >> 13;
    h = h.wrapping_mul(0x5bd1_e995);
    h ^= h >> 15;
    (h & 0xffff) as f32 / 65535.0
}

/// Smooth value noise in 0..1 at frequency `f` (cycles per world unit).
fn noise(x: f32, z: f32, f: f32, seed: u32) -> f32 {
    let (px, pz) = (x * f, z * f);
    let (ix, iz) = (px.floor() as i32, pz.floor() as i32);
    let (fx, fz) = (px - ix as f32, pz - iz as f32);
    let (ux, uz) = (fx * fx * (3.0 - 2.0 * fx), fz * fz * (3.0 - 2.0 * fz));
    let a = hash(ix, iz, seed);
    let b = hash(ix + 1, iz, seed);
    let c = hash(ix, iz + 1, seed);
    let d = hash(ix + 1, iz + 1, seed);
    let top = a + (b - a) * ux;
    let bot = c + (d - c) * ux;
    top + (bot - top) * uz
}

fn smoothstep(e0: f32, e1: f32, x: f32) -> f32 {
    let t = ((x - e0) / (e1 - e0)).clamp(0.0, 1.0);
    t * t * (3.0 - 2.0 * t)
}

fn seg_dist(p: Vec2, a: Vec2, b: Vec2) -> f32 {
    let ab = b - a;
    let t = ((p - a).dot(ab) / ab.length_squared().max(1e-6)).clamp(0.0, 1.0);
    p.distance(a + ab * t)
}

fn poly_dist(p: Vec2, pts: &[Vec2]) -> f32 {
    pts.windows(2).map(|w| seg_dist(p, w[0], w[1])).fold(f32::MAX, f32::min)
}

/// The castle ground at world `(wx, wz)`.
pub fn sample(wx: f32, wz: f32) -> CastleGround {
    if wx.abs() > REACH_X || wz.abs() > REACH_Z {
        return CastleGround::default();
    }
    let p = Vec2::new(wx, wz);
    let n_lo = noise(wx, wz, 0.16, 11); // ~6u patches
    let n_mid = noise(wx, wz, 0.45, 23); // ~2u tongues
    let n_hi = noise(wx, wz, 1.3, 37); // fine fray

    // Cart lanes: a trodden core with a frayed shoulder; the centreline itself peaks so the
    // shader keeps the grass strip between the wheel tracks. They fade out down the approach.
    let mut lane = 0.0f32;
    let mut crown = 0.0f32;
    for l in &LANES {
        let d = poly_dist(p, l);
        // Feather out over the first few units past the gate, under the road trunk.
        let gate = l[2];
        let beyond = (p - gate).dot(gate.normalize());
        let fade = 1.0 - smoothstep(0.5, 4.5, beyond);
        let core = 1.55 + (n_mid - 0.5) * 0.8 + (n_hi - 0.5) * 0.3;
        lane = lane.max((1.0 - smoothstep(core, core + 1.3, d)) * fade);
        crown = crown.max((1.0 - smoothstep(0.12, 0.45, d)) * fade);
    }

    // The muster plaza — the open courtyard (`castle::COURTYARD`) in front of the keep: trampled
    // almost everywhere, a few worn-grass islands where nobody stands.
    let (cx, cz, w, d) = (COURTYARD.0, COURTYARD.1, COURTYARD.2 * 2.0, COURTYARD.3 * 2.0);
    let din = (w / 2.0 - (wx - cx).abs()).min(d / 2.0 - (wz - cz).abs());
    let plaza = smoothstep(-1.4, 1.2, din + (n_mid - 0.5) * 2.2) * (0.72 + 0.28 * smoothstep(0.3, 0.6, n_lo));

    // Inside the walls: the guards' path worn a stride in from the wall foot, grass surviving in
    // tufts hard against the stones. Outside: a fainter siege-trodden strip along the foot.
    let d_in = crate::castle::wall_inset(wx, wz); // >0 inside the wall line
    let ring_in = if d_in > 0.0 {
        let band = smoothstep(0.9, 1.5, d_in) * (1.0 - smoothstep(2.4, 3.4, d_in));
        // Broken into scuffs, not a ring: a continuous band read as a drawn rectangle.
        band * smoothstep(0.5, 0.75, n_mid) * smoothstep(0.35, 0.6, n_lo) * 0.5
    } else {
        0.0
    };
    let d_out = crate::castle::outside_dist(wx, wz); // >0 outside the wall line
    let ring_out = if d_out > 0.0 {
        let band = smoothstep(0.7, 1.3, d_out) * (1.0 - smoothstep(2.6, 4.0, d_out));
        band * smoothstep(0.6, 0.85, n_mid) * smoothstep(0.4, 0.65, n_lo) * 0.32
    } else {
        0.0
    };

    // Worn yard between the houses: bald patches of earth in the trodden grass.
    let yard = if d_in > 1.2 { smoothstep(0.52, 0.78, n_lo) * 0.62 * (0.6 + 0.4 * n_hi) } else { 0.0 };

    // The working corners (`castle::build`): mud round the well, a cart stand, chips and bark
    // round the wood yard, straw spill by the hay store, the market square churned to mud.
    let near = |c: Vec2, r: f32| 1.0 - smoothstep(r * 0.45, r, p.distance(c) + (n_mid - 0.5) * 1.2);
    let at = |t: (f32, f32, f32)| Vec2::new(t.0, t.1);
    let well_pos = crate::castle::town_plot("well").map_or(Vec2::new(5.5, KEEP_FRONT + 2.8), |tp| tp.pos);
    let well = near(well_pos, 3.0) * 0.85;
    let cart = near(at(crate::castle::CART_CORNER), 3.2) * 0.8;
    let wood = near(at(crate::castle::WOOD_YARD), 3.6);
    let hay = near(at(crate::castle::HAY_CORNER), 3.4);
    let market = near(MARKET_CENTRE, 6.5) * 0.8;

    let path = (lane * 0.84 + crown * 0.16)
        .max(plaza * 0.84)
        .max(ring_in)
        .max(ring_out)
        .max(yard)
        .max(well)
        .max(market)
        .max(cart)
        .max(wood * 0.55)
        .max(hay * 0.45)
        .min(1.0);
    let debris = (wood * 0.95).max(hay * 0.75);
    // The scanned floor takes over wherever the ground is worn (path or debris); plain lawn keeps
    // the procedural meadow. A light courtyard-wide share blends the two inside the walls.
    // The share feathers out over ~7u past the wall line, so the bright procedural meadow fades
    // into the trodden yard instead of stopping at a hard patch edge.
    // Past that a faint share carries on across the castle meadow (to ~16u out, inside the reach),
    // knocking the procedural lawn's neon green toward a trodden, natural green.
    let lawn = ((0.38 + 0.2 * n_lo) * (1.0 - smoothstep(1.0, 8.0, d_out)))
        .max((0.24 + 0.12 * n_mid) * (1.0 - smoothstep(9.0, 16.0, d_out)));
    let floor = smoothstep(0.0, 0.55, path.max(debris)).max(lawn);
    CastleGround { floor, path, debris }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn lanes_are_trodden_and_corners_keep_their_grass() {
        // Mid-lane inside the north postern: bare trodden earth on the full scanned floor.
        let g = sample(N_GATE_X + 0.3, -HALF_Z + 3.0);
        assert!(g.path > 0.8 && g.floor > 0.95, "{g:?}");
        // Far out on the meadow: untouched.
        assert_eq!(sample(60.0, 60.0), CastleGround::default());
        // The plaza never crosses the shader's grass-strip threshold off a lane centreline.
        for (x, z) in [(3.0, 3.0), (-4.0, 6.0), (5.5, -3.0)] {
            assert!(sample(x, z).path <= 0.88, "({x},{z}) {:?}", sample(x, z));
        }
    }
}
