//! The cliffy peak regions (snow massif, rock range) as ONE continuous mountain surface each (a
//! `worldmap` child module — it reads the private tile grid and the region / pass definitions).
//!
//! - SNOW: the procedural Tatra-like massif described below.
//! - ROCK: the same machinery (footprint fade, pass valleys, corner bake) but its SHAPE comes
//!   from a REAL heightmap — the Dolomites around Passo Sella (Sella group + Sassolungo, the heads
//!   of Val Gardena / Val di Fassa; `assets/terrain/dolomites_sella_320.r16`, AWS Terrain Tiles,
//!   see ATTRIBUTION.txt) laid over the footprint at roughly true proportions — the tallest,
//!   most rugged summits on the island: walled limestone blocks and towers over valley heads.
//!
//! Both used to be tiered mesas: flat shelves ringed by sheer walls, which from the meadow read
//! as "three stacked discs" (player report). The snow massif is in the spirit of the Tatras: a
//! continuous field [`massif_y`] (world Y) built from
//! - a broad dome over the region's irregular footprint ([`super::mesa_t`], so the silhouette,
//!   the NW sea-cliff front and the biome edge stay where they were);
//! - domain-warped RIDGED noise — ridgelines and spurs with valleys and couloirs between them,
//!   sharpened toward the crests and growing with altitude;
//! - authored SUMMITS set off the trail lines (NW, W, NNE of the centre, + a SE outlier on the
//!   grown flank), so the skyline has a dominant peak and shoulders instead of one dome;
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

/// Lateral width (base units) over which a pass valley's floor blends into the flanks, at the
/// snow massif's authored r 42 (scaled with the region radius; the rock range's gorges run
/// narrower — limestone walls close in on the trail).
const VALLEY_W: f32 = 3.2;
fn valley_band(reg: &Region) -> f32 {
    if reg.biome == TB::Rock {
        2.6
    } else {
        VALLEY_W * reg.r / 42.0
    }
}

/// Authored snow summits: (base x, base z, extra height in world Y, radius in base units),
/// authored at r 42 — radii scale with the region (r 42→48 grew the massif; the summits keep
/// their positions so the skyline and the NW sea-cliff front stay put, their bells broaden).
/// Heights doubled from the first pass (summit 22.6 → ~35): over a ~110u footprint the old
/// relief read as a low snowy dome only three trees tall from the meadow (player: "plamy").
const SUMMITS: [(f32, f32, f32, f32); 4] = [
    (17.5, 13.0, 11.5, 8.0), // main summit, NW of the col
    (12.5, 31.5, 9.0, 7.0),  // western shoulder
    (34.5, 10.5, 8.5, 6.5),  // NNE peak above the sea cliffs
    (49.5, 28.0, 6.0, 6.0),  // E outlier on the grown flank, in the wedge between the two passes
];

/// The real heightmap the rock range is shaped from: 320×320 little-endian u16 (≈42 m per sample,
/// local relief sharpened — `tools/terrain/bake_dem.py`), 0 = valley floors, 65535 = the summits
/// (Piz Boè / Sassolungo), north up.
static ROCK_DEM: &[u8] = include_bytes!("../../assets/terrain/dolomites_sella_320.r16");
const DEM_N: i32 = 320;
/// Half-extent (base units) of the DEM laid over the rock region — 13.5 km onto 2·44 base
/// (≈343 world units): with [`DEM_RISE`] that keeps the real relief's proportions within ~10%.
const DEM_HALF: f32 = 44.0;
/// World Y the DEM's full 1844 m range maps to.
const DEM_RISE: f32 = 46.0;

fn dem_px(ix: i32, iz: i32) -> f32 {
    let i = (iz.clamp(0, DEM_N - 1) * DEM_N + ix.clamp(0, DEM_N - 1)) as usize * 2;
    u16::from_le_bytes([ROCK_DEM[i], ROCK_DEM[i + 1]]) as f32 / 65535.0
}

/// Catmull-Rom sample of the DEM at fractional pixel `(u, v)` (0..DEM_N) — C1 across the sample
/// lattice, so the ~2-tile DEM cells don't print creases into the slope shading.
fn dem(u: f32, v: f32) -> f32 {
    let (fx, fz) = (u - 0.5, v - 0.5);
    let (ix, iz) = (fx.floor() as i32, fz.floor() as i32);
    let (tx, tz) = (fx - ix as f32, fz - iz as f32);
    let w = |t: f32| {
        let (t2, t3) = (t * t, t * t * t);
        [-0.5 * t3 + t2 - 0.5 * t, 1.5 * t3 - 2.5 * t2 + 1.0, -1.5 * t3 + 2.0 * t2 + 0.5 * t, 0.5 * t3 - 0.5 * t2]
    };
    let (wx, wz) = (w(tx), w(tz));
    let mut acc = 0.0;
    for (j, wzj) in wz.iter().enumerate() {
        let mut row = 0.0;
        for (i, wxi) in wx.iter().enumerate() {
            row += wxi * dem_px(ix - 1 + i as i32, iz - 1 + j as i32);
        }
        acc += wzj * row;
    }
    acc.clamp(0.0, 1.0)
}

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

/// Every cliffy peak region is a continuous massif now (snow procedural, rock DEM-shaped).
pub(super) fn is_massif_region(reg: &Region) -> bool {
    reg.cliffy && reg.peak > 0 && matches!(reg.biome, TB::Snow | TB::Rock)
}

/// The shared footprint fade (0..1) of a massif at base `(x, z)`: the region's own wobbled rim
/// (same wobble as `region_at`, so the biome edge meets the apron level), the BOUNDARY with any
/// overlapping region (`region_at` hands contested ground to the deeper region — without this the
/// grown snow massif stood a wall wherever the forest / desert won a tile), the sea (flanks still
/// end in sea cliffs, partly) and the castle's forced-grass safe ring (the grown massif must not
/// rise against the ring's edge).
fn footprint(x: f32, z: f32, reg: &Region) -> f32 {
    let wob = 2.4 * (x * 0.4 + 1.1).sin() + 2.4 * (z * 0.36 - 0.7).cos();
    let own = (x - reg.x).hypot(z - reg.z) + wob - reg.r; // region_at's edge (negative inside)
    let rim = smooth(0.0, 7.0, -own);
    if rim <= 0.0 {
        return 0.0;
    }
    let mut margin = f32::INFINITY;
    for o in active_map().regions {
        if std::ptr::eq(o, reg) {
            continue;
        }
        let fray = if o.peak > 0 { 0.0 } else { edge_fray(x, z) };
        let oe = (x - o.x).hypot(z - o.z) + wob + fray - o.r;
        if oe < 0.0 {
            margin = margin.min(oe - own);
        }
    }
    // (12, not 6: a neighbour's `edge_fray` scallops its boundary every few units, and a short
    // fade printed those scallops into the flank as a row of bumps.)
    let border = if margin.is_finite() { smooth(0.0, 12.0, margin) } else { 1.0 };
    let coast = 0.25 + 0.75 * smooth(0.0, 9.0, sea_field(x, z));
    let ring = smooth(SAFE_PAD + SAFE_FRAY, SAFE_PAD + SAFE_FRAY + 10.0, castle_ring_dist(x, z));
    // Settle the ground to the swamp bog pools' shore level. (The deliberate lake and the waterfall
    // valley above it are NOT faded here any more: scaling the whole mountain down toward the lake
    // drew a planar ramp whose crag noise stretched into organ-pipe flutes, and the pocket the
    // falls needed was kept by an un-faded disc — two smooth pyramids either side of a slot. The
    // rock range's [`gorge_carve`] cuts the lake basin and the valley out of the relief instead.)
    let wet = smooth(1.0, 9.0, pool_sd(x, z));
    rim * border * coast * ring * wet
}

// ── The waterfall valley ─────────────────────────────────────────────────────────────
/// The HANGING VALLEY above the falls (BASE space), lip → upstream: the feeder brook's shallow
/// trough across the plateau behind the head wall, so water visibly arrives at the lip.
const HANG_CTRL: [(f32, f32); 4] = [(102.9, 65.9), (104.3, 64.1), (106.5, 63.4), (108.0, 62.1)];
/// World Y of the hanging valley's floor at the lip (the falls drop ≈17u from here to the pool).
const LIP_Y: f32 = 17.0;

/// Nearest point of a polyline: `(distance, arc length to it, total length, segment, t, how far
/// the projection falls BEFORE the first point (≥ 0))` — all in base units.
fn poly_hit(n: usize, pt: impl Fn(usize) -> (f32, f32), x: f32, z: f32) -> (f32, f32, f32, usize, f32, f32) {
    let mut best = (f32::INFINITY, 0.0, 0.0, 0, 0.0, 0.0);
    let mut arc = 0.0;
    for i in 0..n - 1 {
        let ((ax, az), (bx, bz)) = (pt(i), pt(i + 1));
        let (abx, abz) = (bx - ax, bz - az);
        let l2 = abx * abx + abz * abz;
        let l = l2.sqrt();
        let tr = ((x - ax) * abx + (z - az) * abz) / l2;
        let t = tr.clamp(0.0, 1.0);
        let d = (x - ax - abx * t).hypot(z - az - abz * t);
        if d < best.0 {
            best = (d, arc + t * l, 0.0, i, t, if i == 0 { (-tr * l).max(0.0) } else { 0.0 });
        }
        arc += l;
    }
    best.2 = arc;
    best
}

/// Rise (world Y) of a valley side `d` world units out from the floor's edge: a scree/talus apron
/// at slope `lo` steepening to the rock wall's `hi` over ~`w` units — the concave profile of a real
/// V-valley side whose foot is buried in its own debris.
fn side_rise(d: f32, lo: f32, hi: f32, w: f32) -> f32 {
    lo * d + (hi - lo) * (d - w * (1.0 - (-d / w).exp()))
}

/// The rock range's SW LAKE BASIN + WATERFALL VALLEY (world Y ceiling; `INFINITY` away from it):
/// - a V-valley round the winding waterfall stream ([`plunge_path`]): a narrow floor that widens
///   toward the lake, concave sides (talus ~30° at the foot steepening to 45–65° rock, with short
///   sheer stretches) whose plan is wobbled by multi-scale noise into spurs and bays;
/// - its HEAD closes behind the plunge pool in a real cliff (~75°) up to the hanging valley
///   ([`HANG_CTRL`]), whose floor rises gently away from the lip — the falls' step;
/// - the lake's tarn basin: the same concave sides rising off the shore.
///
/// [`mountain_y`] takes a smooth minimum of this and the DEM relief, so above the carve the real
/// mountain keeps its own shape and the valley shoulders roll into it.
fn gorge_carve(x: f32, z: f32) -> f32 {
    if !(83.0..=112.0).contains(&x) || !(57.0..=90.0).contains(&z) {
        return f32::INFINITY;
    }
    let b = MAP_SCALE;
    // Shared plan wobble (world units): spurs & bays (~3 base) …
    let spur = (vnoise(x * 0.33 + 3.1, z * 0.33 - 7.7) - 0.5) * 8.0;
    // … and buttresses / gullies whose noise domain SLIDES with height (`hy`, world Y above the
    // floor): a plan-only wobble extrudes straight up a steep face as rows of vertical flutes
    // ("organ pipes"); sliding it makes the gullies wander and die out up the wall.
    let butt = |hy: f32| (vnoise(x * 0.85 - 11.0 + hy * 0.07, z * 0.85 + 2.3 - hy * 0.05) - 0.5) * 2.4;
    let wob = spur + butt(0.0);
    // Wall steepness varies along the valley; here and there a short sheer stretch.
    let sn = vnoise(x * 0.5 + 21.0, z * 0.5 - 13.0);
    let crag = smooth(0.66, 0.86, vnoise(x * 0.7 - 4.0, z * 0.7 + 9.0));
    // Ledges / blocks on the faces (world Y), zero on the floors.
    let bump = (vnoise(x * 1.4 + 1.0, z * 1.4 - 3.0) - 0.5) * 1.6 + (vnoise(x * 3.3, z * 3.3 + 8.0) - 0.5) * 0.6;
    let floor_y = SEA_Y + 0.35;

    // 1. The valley round the waterfall stream.
    let p = plunge_path();
    let (d, arc, total, seg, t, pre) = poly_hit(p.len(), |i| (p[i].0, p[i].1), x, z);
    let s = arc / total; // 0 at the plunge pool … 1 at the lake
    let half = p[seg].2 + (p[(seg + 1).min(p.len() - 1)].2 - p[seg].2) * t;
    let taper = 0.35 + 0.65 * smooth(0.0, 0.3, s); // calmer plan round the plunge pool
    let wf = 0.6 + 3.0 * s; // the floor widens toward the lake
    let head = smooth(0.3, 1.5, pre); // behind the plunge pool: the head wall
    // Talus ~34° at the foot easing to ~24° near the lake; rock 50–60° up-valley, 36–47° at the
    // mouth, short crags to ~68°; the head wall ~77° over a thin debris foot.
    let lo = (0.68 - 0.2 * s) + (1.6 - (0.68 - 0.2 * s)) * head;
    let hi = ((1.45 - 0.55 * s) * (0.8 + 0.4 * sn) + 1.0 * crag) * (1.0 - head) + 4.5 * head;
    let main_at = |w: f32| {
        let d0 = (d * b + w * taper - half * b).max(0.0);
        let dd = (d0 - wf).max(0.0);
        (0.14 * d0.min(wf) + side_rise(dd, lo, hi, 6.0), dd)
    };
    let (h0, _) = main_at(spur + butt(0.0));
    let (h1, dd) = main_at(spur + butt(h0));
    let v_main = floor_y + h1 + bump * smooth(0.0, 4.0, dd);

    // 2. The hanging valley above the lip.
    let (dh, arch, ..) = poly_hit(HANG_CTRL.len(), |i| HANG_CTRL[i], x, z);
    let dh0 = (dh * b + wob * 0.5 - 1.0).max(0.0);
    let v_hang = LIP_Y + 0.35 * arch + 0.12 * dh0.min(2.0)
        + side_rise((dh0 - 2.0).max(0.0), 0.45, 1.0 * (0.8 + 0.4 * sn), 3.0)
        + bump * 0.6 * smooth(2.0, 5.0, dh0);

    // 3. The lake's tarn basin (distance off the shore along the ray from the centre).
    let (lx, lz, rx, rz) = DELIBERATE_LAKE;
    let (dx, dz) = (x - lx, z - lz);
    let r = dx.hypot(dz).max(1e-4);
    let re = 1.0 / ((dx / r / rx).powi(2) + (dz / r / rz).powi(2)).sqrt();
    // The outlet (south) side keeps the broad, nearly level shore flat the old apron had — the
    // rocky story scenes seat on it (`stories_cold_plan_seats_every_scene_in_its_biome`); under
    // the mountain (north / the valley mouth) the slopes rise almost straight off the water.
    let south = smooth(-0.1, 0.7, dz / r);
    let (flat_w, flat_s) = (1.5 + 12.0 * south, 0.12 - 0.05 * south);
    let lake_at = |w: f32| {
        let dl = ((r - re) * b + w).max(0.0);
        let rise = side_rise((dl - flat_w).max(0.0), 0.55, 1.05 * (0.8 + 0.4 * sn) + 0.8 * crag, 6.0);
        (flat_s * dl.min(flat_w) + rise, dl)
    };
    let (hl0, _) = lake_at(spur + butt(0.0));
    let (hl, dl) = lake_at(spur + butt(hl0));
    let v_lake = floor_y + hl + bump * smooth(flat_w, flat_w + 4.0, dl);

    smin_poly(smin_poly(v_main, v_hang, 1.0), v_lake, 2.0).max(floor_y - 0.05)
}

/// 0..1 how much of base `(x, z)` the massif still OWNS against its neighbours: 1 on its own
/// ground, easing to 0 over 12 base units toward any boundary where another region claims the tile
/// (`region_at` hands contested ground to the DEEPER region — the grown desert now owns the rock
/// range's old northern plateau, inside the range's circle). 0 = ceded outright. The pass ramps
/// ride it, so unlike the flank's `footprint` border it must be SMOOTH: continuous across the
/// neighbour's own rim (a claim fades out over 4 base units past its edge instead of vanishing at
/// it), no `edge_fray` (its ±3.7 scallops swing the margin ~1 base per tile — on a 5u-high ramp
/// that was a 2-class step in the only walkable ascent), and a wider 16-unit fade.
pub(super) fn ownership(x: f32, z: f32, reg: &Region) -> f32 {
    // (`region_at`'s wobble is common to both edges and cancels out of the margin.)
    let own = (x - reg.x).hypot(z - reg.z) - reg.r;
    let mut margin = f32::INFINITY;
    for o in active_map().regions {
        if std::ptr::eq(o, reg) {
            continue;
        }
        let oe = (x - o.x).hypot(z - o.z) - o.r;
        if oe < 4.0 {
            margin = margin.min(if oe < 0.0 { oe } else { 3.0 * oe } - own);
        }
    }
    if margin.is_finite() { smooth(0.0, 16.0, margin) } else { 1.0 }
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
    let band = valley_band(reg);
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
        w = w.max(1.0 - smooth(1.6, p.half + band, lat));
    }
    w
}

/// Domain-warped, rotated ridged octaves (nothing lines up with the grid axes): the big ridge
/// lines, spurs riding them, and fine crest detail.
pub(super) fn ridges3(x: f32, z: f32) -> (f32, f32, f32) {
    let wx = x + (vnoise(x * 0.055 + 11.0, z * 0.055 - 4.0) - 0.5) * 10.0;
    let wz = z + (vnoise(x * 0.055 - 7.0, z * 0.055 + 13.0) - 0.5) * 10.0;
    let (ax, az) = (0.857 * wx - 0.515 * wz, 0.515 * wx + 0.857 * wz);
    let (bx, bz) = (0.602 * wx + 0.799 * wz, -0.799 * wx + 0.602 * wz);
    (
        ridged(ax * 0.085 + 3.0, az * 0.085 - 9.0),
        ridged(bx * 0.18 - 5.0, bz * 0.18 + 2.0),
        ridged(ax * 0.38 + 17.0, az * 0.38 + 1.0),
    )
}

/// The raw mountain (world Y) before the pass valleys are cut in.
fn mountain_y(x: f32, z: f32, reg: &Region) -> f32 {
    let f = footprint(x, z, reg);
    if f <= 0.0 {
        return 0.0;
    }
    let t = mesa_t(x, z, reg);
    if reg.biome != TB::Rock {
        return snow_y(x, z, t, reg) * f;
    }
    let m = rock_y(x, z, t, reg) * f;
    // The SW lake basin + waterfall valley, cut OUT of the relief (a ceiling, not a scale-down):
    // a smooth minimum rolls the valley shoulders into the mountain, never dipping a floor below
    // its own level.
    let carve = gorge_carve(x, z);
    const K: f32 = 2.5;
    if carve >= m + K {
        return m;
    }
    smin_poly(m, carve, K).max(m.min(SEA_Y + 0.3))
}

/// The snow massif (Tatra-like): broad dome + ridged relief + authored summits.
fn snow_y(x: f32, z: f32, t: f32, reg: &Region) -> f32 {
    let env = smooth(0.05, 0.92, t);
    if env <= 0.0 {
        return 0.0;
    }
    // Broad dome: gentle foothills, steepening toward the top.
    let dome = 11.0 * env.powf(1.5);
    let (r1, r2, r3) = ridges3(x, z);
    // Sharp crests (squared), finer ridges riding on the big ones (spurs off the main ridges).
    let ridges = r1 * r1 * 0.62 + r2 * r1 * 0.26 + r3 * (0.4 + 0.6 * r1) * 0.12;
    // (env^0.9, not ^1.2: the lower flanks get their spurs and gullies too, instead of a
    // smooth dome skirt under ridged summits.)
    let relief = 12.0 * env.powf(0.9) * ridges;
    let grow = reg.r / 42.0;
    let mut peaks = 0.0f32;
    for (sx, sz, h, rad) in SUMMITS {
        let d = (x - sx).hypot(z - sz) / (rad * grow);
        // Pointed bell (steeper than a Gaussian near the top, long tail).
        peaks += h * (-d * d).exp() * (1.0 + 0.35 * (1.0 - d).max(0.0));
    }
    dome + relief + peaks * env
}

/// The rock range: the real Dolomites DEM over the footprint. A low dome lifts the range out of
/// its apron; the DEM supplies everything else (the Sella's walled block, Sassolungo's towers,
/// the valley heads between them); a fine ridged octave roughens the crags and scree below the
/// DEM's ~84 m sample spacing.
fn rock_y(x: f32, z: f32, t: f32, reg: &Region) -> f32 {
    // Full DEM relief over the inner ~60% of the footprint, fading out over the outer flanks.
    let env = smooth(0.0, 0.58, t);
    if env <= 0.0 {
        return 0.0;
    }
    let u = (0.5 + (x - reg.x) / (2.0 * DEM_HALF)) * DEM_N as f32;
    let v = (0.5 + (z - reg.z) / (2.0 * DEM_HALF)) * DEM_N as f32;
    let d = dem(u, v);
    // The DEM's own steepness (world rise per world unit): the walls of the Sella block and the
    // Sassolungo towers, as opposed to the screes and alpine pastures below them.
    let gx = dem(u + 1.0, v) - dem(u - 1.0, v);
    let gz = dem(u, v + 1.0) - dem(u, v - 1.0);
    let spacing = 2.0 * DEM_HALF * MAP_SCALE / DEM_N as f32;
    let grad = gx.hypot(gz) * 0.5 * DEM_RISE / spacing;
    let steep = smooth(0.35, 0.95, grad) * env;
    let (_, r2, r3) = ridges3(x * 1.3 + 40.0, z * 1.3 - 25.0);
    // Crags: sharp ridged spikes (towers / pinnacles) where the DEM is already steep and high,
    // a gentle roughness on the pastures.
    let crag = (r3 * r3 * r3 * (1.2 + 3.4 * steep) + r2 * 0.9) * (0.35 + d) * env;
    let y = 6.0 * env.powf(1.4) + DEM_RISE * d.powf(1.3) * env.powf(0.6) + crag;
    // CLIFF BANDS: on the steep ground the rise is gathered into near-vertical walls between
    // narrow ledges (the stratified dolomite of the Sella / Sassolungo faces) — a ledge-and-wall
    // profile every BAND units of height, blended in only where the DEM is steep, so pastures,
    // screes and the pass valleys keep their natural slopes.
    // Real dolomite strata are NOT a ruled staircase: beds range from thin to massive, dip a few
    // degrees, and each wall is cut by vertical joints into blocks whose ledges come and go. So:
    // - the height is WARPED by a 1-D noise in y before banding (monotonic: the warp's slope stays
    //   < 0.7), so bed thickness varies ~1.8–9u instead of a fixed 3.2u;
    // - a gentle regional dip + the old broad undulation tilt the beds off the contour lines;
    // - each bed draws its own ledge width (`lo`), so some steps are broad shelves, some hairlines;
    // - a jointing noise (~3.5u blocks along the face) varies how hard the step is gathered, so a
    //   ledge fades out into a plain slab and picks up again on the next block.
    const BAND: f32 = 3.2;
    let warp = 0.75 * (2.0 * vnoise(y * 0.29 + 5.0, 1.7 + 0.15 * vnoise(x * 0.08, z * 0.08)) - 1.0);
    let off = 0.37 * vnoise(x * 0.3 + 7.0, z * 0.3 - 2.0) + (x * 0.21 - z * 0.12) / BAND;
    let s = (y + warp) / BAND + off;
    let (bed, f) = (s.floor(), s - s.floor());
    let lo = 0.42 + 0.36 * vnoise(bed * 1.37 + 0.5, 9.2);
    let stair = (bed + smooth(lo, 0.97, f) - off) * BAND - warp;
    let joint = smooth(0.22, 0.78, vnoise(x * 1.1 + 2.0, z * 1.1 - 5.0));
    // Ledges only on the real walls: on the ~30° screes and pastures a half-strength step drew
    // rows of parallel contour lines across the whole slope.
    let wall = smooth(0.55, 1.15, grad) * env;
    y + (stair - y) * wall * (0.30 + 0.50 * joint)
}

/// The massif surface (world Y) at base `(x, z)` inside a massif region: the mountain with the
/// pass valleys carved in (a trail corridor's floor is exactly the continuous pass ramp).
pub(super) fn massif_y(x: f32, z: f32, reg: &Region) -> f32 {
    let m = mountain_y(x, z, reg);
    let w = valley_w(x, z, reg);
    if w <= 0.0 {
        return m;
    }
    let dc = (x - reg.x).hypot(z - reg.z);
    // The trail floor eases down to the castle ring's grass level where a pass mouth noses into
    // the safe ring (the grown snow massif's SE ascent starts inside it): the ring forces class-1
    // grass there, so an un-eased ramp left a 2-class lip at the foot of the main ascent.
    let ring = smooth(SAFE_PAD + SAFE_FRAY, SAFE_PAD + SAFE_FRAY + 10.0, castle_ring_dist(x, z));
    // ...and to the neighbour's level where the corridor's outer reach crosses ground another
    // region owns (the rock range's N canyon and WNW ascent run out across the grown desert): the
    // bare radial ramp stood there as a rock causeway several units above the dunes. Now the trail
    // runs out of the canyon as a level dry wash (`classify` hands those tiles the owner's biome)
    // and starts climbing where the range's ground begins. Rock range only — the snow massif's
    // corridors keep their tuned ramps (its footprint is the player's favourite; don't touch it).
    let owned = if cedes_corridors(reg) { ownership(x, z, reg) } else { 1.0 };
    m + (ramp_y(dc, reg) * ring * owned - m) * w
}

/// Does this massif's pass corridor yield to a neighbour's ground (see [`massif_y`])?
pub(super) fn cedes_corridors(reg: &Region) -> bool {
    is_massif_region(reg) && reg.biome == TB::Rock
}

/// Height CLASS of a massif tile (the quantised field — the mesh / ground read [`corner_y`]).
pub(super) fn massif_class(x: f32, z: f32, reg: &Region) -> i32 {
    ((massif_y(x, z, reg) / GROUND_STEP).round() as i32 + 1).max(1)
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
    // NO `water_near()` here: that mask's own bake reads corner heights (`bank_cell_active`), so
    // touching it from inside this bake re-locks its mutex on the same thread (a boot deadlock).
    // Rivers keep out of the peak regions (`river_blocked`) and sea tiles are `None`, so "all four
    // tiles are this massif's land" already means dry massif ground.
    let grid = tiles();
    for reg in active_map().regions.iter().filter(|r| is_massif_region(r)) {
        // A tile of the massif's biome that the massif itself classified: inside its mountain
        // footprint (`in_mountain`'s test — the coastal ridges, which also paint Rock, skip it)
        // or on one of its pass corridors.
        let massif_tile = |ix: i32, iz: i32| -> bool {
            if !matches!(tile_in(&grid, ix, iz), Some((b, _)) if b == reg.biome) {
                return false;
            }
            let (x, z) = (ix as f32 / MAP_SCALE, iz as f32 / MAP_SCALE);
            let wob = 2.4 * (x * 0.4 + 1.1).sin() + 2.4 * (z * 0.36 - 0.7).cos();
            (x - reg.x).hypot(z - reg.z) + wob < reg.r + 2.0 || pass_class(x, z, reg).is_some()
        };
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
    }
    // The NATURAL relief outside the massifs (coastal ridges, hills, knolls, dunes): `classify`
    // computed each tile's continuous height before rounding it to a class, sampled exactly at
    // the tile's own corner — so a corner whose four tiles are all natural-relief ground (none
    // force-flat, beach, swamp or water) takes that exact value instead of the class-cluster mean,
    // and the hills render as continuous rounded relief, not 0.5u terraces. The ±1-class guard
    // falls back wherever `terrace_inland` relaxed a tile (the cluster logic then applies).
    let exact = exact_heights();
    if exact.len() == (COLS * ROWS) as usize {
        let natural_tile = |ix: i32, iz: i32, c: i32| -> bool {
            matches!(tile_in(&grid, ix, iz), Some((_, h)) if (h - c).abs() <= 1)
                && !exact[(iz * COLS + ix) as usize].is_nan()
        };
        for cz in 1..ROWS {
            for cx in 1..COLS {
                let i = cz as usize * cw + cx as usize;
                if !out[i].is_nan() {
                    continue;
                }
                let y = exact[(cz * COLS + cx) as usize];
                if y.is_nan() {
                    continue;
                }
                let c = (y / GROUND_STEP).round() as i32 + 1;
                if natural_tile(cx - 1, cz - 1, c) && natural_tile(cx, cz - 1, c) && natural_tile(cx - 1, cz, c) && natural_tile(cx, cz, c) {
                    out[i] = y;
                }
            }
        }
    }
    Arc::new(out)
}
