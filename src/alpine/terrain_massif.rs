//! The snow massif as ONE continuous mountain surface (a `worldmap` child module — it reads the
//! private tile grid and the region / pass definitions).
//!
//! The snow region used to be a tiered mesa: four flat shelves ringed by sheer walls, which from
//! the meadow read as "three stacked discs" (player report). It is now a natural massif in the
//! spirit of the Tatras: a continuous field [`massif_y`] (world Y) built from
//! - a broad dome over the region's irregular footprint ([`super::mesa_t`], so the silhouette,
//!   the NW sea-cliff front and the biome edge stay where they were);
//! - domain-warped RIDGED noise — ridgelines and spurs with valleys and couloirs between them,
//!   sharpened toward the crests and growing with altitude;
//! - three authored SUMMITS set off the trail lines (NW, W, NNE of the centre), so the skyline
//!   has a dominant peak and two shoulders instead of one dome;
//! - the authored pass corridors carved in as smooth VALLEYS: the trail floor is the old pass
//!   ramp made continuous (≤ 0.09 rise per tile, the same mouth → col line the roads paint),
//!   blended into the flanks over a wide band, so the ascents read as valleys winding up to a
//!   high col under the peaks.
//!
//! Two consumers, one field:
//! - `classify` stores `round(massif_y)` as the tile CLASS (biome, scatter, the class-based tests);
//! - [`corner_y`] returns the exact field at every grid corner whose four tiles are all massif
//!   ground, and `corner_top_y_in` (the single height source of the mesh, `ground_at_world`, the
//!   nav grid and scatter) returns it verbatim — so the surface is smooth everywhere (no class
//!   terraces), no corner of the massif ever splits into a wall, and steep ground is simply steep:
//!   the alpine shader puts rock on it from the slope, and `navgrid::can_step` (0.6 per tile)
//!   blocks it where it's too steep to walk. Walls survive only where the massif meets the sea.

use super::*;

/// Lateral width (base units) over which a pass valley's floor blends into the flanks.
const VALLEY_W: f32 = 3.2;

/// Authored summits: (base x, base z, extra height in world Y, radius in base units).
/// Heights doubled from the first pass (summit 22.6 → ~35): over a ~110u footprint the old
/// relief read as a low snowy dome only three trees tall from the meadow (player: "plamy").
const SUMMITS: [(f32, f32, f32, f32); 3] = [
    (17.5, 13.0, 11.0, 8.0), // main summit, NW of the col
    (12.5, 31.5, 8.5, 7.0),  // western shoulder
    (34.5, 10.5, 8.0, 6.5),  // NNE peak above the sea cliffs
];

fn smooth(e0: f32, e1: f32, x: f32) -> f32 {
    let t = ((x - e0) / (e1 - e0)).clamp(0.0, 1.0);
    t * t * (3.0 - 2.0 * t)
}

/// One ridged octave in [0, 1] (1 on a crest line). Ridged over a SUM of two rotated value-noise
/// lattices: a single lattice's 0.5-isolines hug its cells, so its crests came out as blocky
/// rectangles in the hillshade.
fn ridged(x: f32, z: f32) -> f32 {
    let v = 0.6 * vnoise(x, z) + 0.4 * vnoise(1.93 * x + 0.41 * z + 31.0, -0.41 * x + 1.93 * z - 17.0);
    1.0 - ((v - 0.5) * 2.6).abs().min(1.0)
}

fn is_massif_region(reg: &Region) -> bool {
    reg.biome == TB::Snow && reg.cliffy && reg.peak > 0
}

/// The continuous pass-ramp floor at distance `dc` (base) from the centre — `pass_class` without
/// the staircase (its floor() steps' mean, so the classes match it: class 2 for the first step at
/// the mouth, where the castle safe-zone's class-1 grass meets the trail) up to the region's peak
/// class at the centre (the col).
fn ramp_y(dc: f32, reg: &Region) -> f32 {
    let span = (reg.peak - 2).max(1) as f32;
    (0.5 + span * (1.0 - dc / reg.r).clamp(0.0, 1.0)) * GROUND_STEP
}

/// Valley weight (1 on a trail corridor, easing to 0 across the valley band) at base `(x, z)`.
fn valley_w(x: f32, z: f32, reg: &Region) -> f32 {
    let dx = x - reg.x;
    let dz = z - reg.z;
    let dc = dx.hypot(dz);
    let mut w = 0.0f32;
    for p in reg.passes {
        // Same (serpentined) angular corridor as `pass_class`, measured as an arc length.
        let mut da = (dz.atan2(dx) - p.ang - pass_sway(dc, reg, p)) % std::f32::consts::TAU;
        if da < -std::f32::consts::PI {
            da += std::f32::consts::TAU;
        }
        if da > std::f32::consts::PI {
            da -= std::f32::consts::TAU;
        }
        let lat = da.abs() * dc.max(1.5);
        // V/U profile: only the trail's own strip (±1.6 base) is the exact ramp; the floor then
        // rises across the rest of the authored corridor into the flanks, so the ascent reads as
        // a valley rather than a flat-floored trench.
        w = w.max(1.0 - smooth(1.6, p.half + VALLEY_W, lat));
    }
    w
}

/// The raw mountain (world Y) before the pass valleys are cut in.
fn mountain_y(x: f32, z: f32, reg: &Region) -> f32 {
    let t = mesa_t(x, z, reg);
    // Fade to the foot at the region's own (wobbled) rim, so the snow biome edge meets the
    // surrounding apron level, and partly toward the sea (the NW flanks still end in sea cliffs).
    let wob = 2.4 * (x * 0.4 + 1.1).sin() + 2.4 * (z * 0.36 - 0.7).cos();
    let edge = reg.r - ((x - reg.x).hypot(z - reg.z) + wob);
    let rim = smooth(0.0, 7.0, edge);
    let coast = 0.25 + 0.75 * smooth(0.0, 9.0, sea_field(x, z));
    let env = smooth(0.05, 0.92, t);
    if env <= 0.0 || rim <= 0.0 {
        return 0.0;
    }
    // Broad dome: gentle foothills, steepening toward the top.
    let dome = 11.0 * env.powf(1.5);
    // Domain-warped ridged octaves (rotated lattices so nothing lines up with the grid axes).
    let wx = x + (vnoise(x * 0.055 + 11.0, z * 0.055 - 4.0) - 0.5) * 10.0;
    let wz = z + (vnoise(x * 0.055 - 7.0, z * 0.055 + 13.0) - 0.5) * 10.0;
    let (ax, az) = (0.857 * wx - 0.515 * wz, 0.515 * wx + 0.857 * wz);
    let (bx, bz) = (0.602 * wx + 0.799 * wz, -0.799 * wx + 0.602 * wz);
    let r1 = ridged(ax * 0.085 + 3.0, az * 0.085 - 9.0);
    let r2 = ridged(bx * 0.18 - 5.0, bz * 0.18 + 2.0);
    let r3 = ridged(ax * 0.38 + 17.0, az * 0.38 + 1.0);
    // Sharp crests (squared), finer ridges riding on the big ones (spurs off the main ridges).
    let ridges = r1 * r1 * 0.62 + r2 * r1 * 0.26 + r3 * (0.4 + 0.6 * r1) * 0.12;
    // (env^0.9, not ^1.2: the lower flanks get their spurs and gullies too, instead of a
    // smooth dome skirt under ridged summits.)
    let relief = 12.0 * env.powf(0.9) * ridges;
    let mut peaks = 0.0f32;
    for (sx, sz, h, rad) in SUMMITS {
        let d = (x - sx).hypot(z - sz) / rad;
        // Pointed bell (steeper than a Gaussian near the top, long tail).
        peaks += h * (-d * d).exp() * (1.0 + 0.35 * (1.0 - d).max(0.0));
    }
    (dome + relief + peaks * env) * rim * coast
}

/// The massif surface (world Y) at base `(x, z)` inside the snow region: the mountain with the
/// pass valleys carved in (a trail corridor's floor is exactly the continuous pass ramp).
pub(super) fn massif_y(x: f32, z: f32, reg: &Region) -> f32 {
    let m = mountain_y(x, z, reg);
    let w = valley_w(x, z, reg);
    if w <= 0.0 {
        return m;
    }
    let dc = (x - reg.x).hypot(z - reg.z);
    m + (ramp_y(dc, reg) - m) * w
}

/// Height CLASS of a massif tile (the quantised field — the mesh / ground read [`corner_y`]).
pub(super) fn massif_class(x: f32, z: f32, reg: &Region) -> i32 {
    ((massif_y(x, z, reg) / GROUND_STEP).round() as i32 + 1).max(1)
}

/// The snow massif region of the active map, if it has one.
fn massif_region() -> Option<&'static Region> {
    active_map().regions.iter().find(|r| is_massif_region(r))
}

static CORNERS: OnceLock<Mutex<HashMap<u8, Arc<Vec<f32>>>>> = OnceLock::new();

/// Exact massif height (world Y) at grid corner `(cx, cz)` when all four of its tiles are dry
/// massif ground; `None` elsewhere (the cluster-mean corner logic then applies as before).
pub(super) fn corner_y(cx: i32, cz: i32) -> Option<f32> {
    if cx < 0 || cz < 0 || cx > COLS || cz > ROWS {
        return None;
    }
    thread_local! {
        static LOCAL: std::cell::RefCell<Option<(u8, Arc<Vec<f32>>)>> = const { std::cell::RefCell::new(None) };
    }
    let idx = (cz * (COLS + 1) + cx) as usize;
    let id = active_id();
    let v = LOCAL.with(|l| l.borrow().as_ref().and_then(|(cid, g)| (*cid == id).then(|| g[idx])));
    let v = match v {
        Some(v) => v,
        None => {
            let cache = CORNERS.get_or_init(|| Mutex::new(HashMap::new()));
            let g = cache.lock().expect("massif cache poisoned").entry(id).or_insert_with(build_corners).clone();
            let v = g[idx];
            LOCAL.with(|l| *l.borrow_mut() = Some((id, g)));
            v
        }
    };
    (!v.is_nan()).then_some(v)
}

fn build_corners() -> Arc<Vec<f32>> {
    let (cw, ch) = ((COLS + 1) as usize, (ROWS + 1) as usize);
    let mut out = vec![f32::NAN; cw * ch];
    let Some(reg) = massif_region() else {
        return Arc::new(out);
    };
    // NO `water_near()` here: that mask's own bake reads corner heights (`bank_cell_active`), so
    // touching it from inside this bake re-locks its mutex on the same thread (a boot deadlock).
    // Rivers keep out of the peak regions (`river_blocked`) and sea tiles are `None`, so "all four
    // tiles are snow land" already means dry massif ground.
    let grid = tiles();
    let massif_tile = |ix: i32, iz: i32| -> bool { matches!(tile_in(&grid, ix, iz), Some((TB::Snow, _))) };
    // Only the region's bounding box can hold massif corners.
    let pad = reg.r * 1.4 + 4.0;
    let lo_x = (((reg.x - pad) * MAP_SCALE).floor() as i32).max(1);
    let hi_x = (((reg.x + pad) * MAP_SCALE).ceil() as i32).min(COLS - 1);
    let lo_z = (((reg.z - pad) * MAP_SCALE).floor() as i32).max(1);
    let hi_z = (((reg.z + pad) * MAP_SCALE).ceil() as i32).min(ROWS - 1);
    for cz in lo_z..=hi_z {
        for cx in lo_x..=hi_x {
            if massif_tile(cx - 1, cz - 1) && massif_tile(cx, cz - 1) && massif_tile(cx - 1, cz) && massif_tile(cx, cz) {
                out[cz as usize * cw + cx as usize] = massif_y(cx as f32 / MAP_SCALE, cz as f32 / MAP_SCALE, reg);
            }
        }
    }
    Arc::new(out)
}
