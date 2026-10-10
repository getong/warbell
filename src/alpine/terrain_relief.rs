//! Eroded relief on the mesa shelves (a `worldmap` child module — it reads the private tile grid).
//!
//! The cliffy mesas (snow massif, rock range) were dead-flat shelves between sheer walls: tables,
//! not mountains. This bakes a per-map height offset at every grid CORNER of their interior and
//! [`super::corner_top_y_in`] adds it to the smoothed corner height — the single point every
//! consumer reads (terrain mesh, normals, `ground_at_world`, the nav-grid's baked tile-centre
//! heights), so the visible ground, the hero's feet, scatter and pathing all agree.
//!
//! Shape (all deterministic, per map):
//! - signed broad MOUNDS from two rotated value-noise octaves, easing in past a noise-jittered
//!   onset (no edge-relative dome: on the narrow tier rings that tilted a band along every edge
//!   the same way and a low sun drew it as a straight seam);
//! - GULLIES from an erosion filter — per-cell cosine stripes running across the shelf toward its
//!   rim (the gradient of a heavily blurred edge distance, so no straight chamfer creases),
//!   bell-blended over a jittered grid (runevision's / Clay John's gradient-aligned erosion noise),
//!   so the flanks read as branching runnels and spurs instead of isotropic blobs.
//!
//! Gameplay safety:
//! - zero at every corner touching ANY class change, water, or a non-mesa tile (and fading in
//!   over the next few tiles), so every wall, pass ramp step and camp / landmark / apron site
//!   keeps its exact old height;
//! - only class ≥ 3 cliffy-region tiles (the class-1/2 apron is untouched);
//! - a Lipschitz envelope caps the slope at [`MAX_GRAD`] per unit (diagonal neighbours √2·that),
//!   so adjacent tile centres never differ by more than ~0.48 — under the nav-grid's 0.6 step
//!   limit (`navgrid::can_step`) and `steer::MAX_STEP`, and below the slope where tree thinning
//!   starts biting hard;
//! - a final tent blur rounds the envelope's crease lines (blurring can't raise a Lipschitz
//!   constant, so the cap survives it).

use super::*;

/// Max relief slope (world Y per world unit) after the Lipschitz envelope.
const MAX_GRAD: f32 = 0.34;
/// Corners within this edge distance (tiles) keep relief exactly 0.
const EDGE: f32 = 1.0;

static RELIEF: OnceLock<Mutex<HashMap<u8, Arc<Vec<f32>>>>> = OnceLock::new();

/// Relief offset (world Y) at grid corner `(cx, cz)` for the active map — 0 off the mesa shelves.
pub(super) fn corner_relief(cx: i32, cz: i32) -> f32 {
    if cx < 0 || cz < 0 || cx > COLS || cz > ROWS {
        return 0.0;
    }
    thread_local! {
        static LOCAL: std::cell::RefCell<Option<(u8, Arc<Vec<f32>>)>> = const { std::cell::RefCell::new(None) };
    }
    let idx = (cz * (COLS + 1) + cx) as usize;
    let id = active_id();
    if let Some(v) = LOCAL.with(|l| l.borrow().as_ref().and_then(|(cid, g)| (*cid == id).then(|| g[idx]))) {
        return v;
    }
    let cache = RELIEF.get_or_init(|| Mutex::new(HashMap::new()));
    let g = cache.lock().expect("relief cache poisoned").entry(id).or_insert_with(build_relief).clone();
    let v = g[idx];
    LOCAL.with(|l| *l.borrow_mut() = Some((id, g)));
    v
}

/// The relief's share of [`super::ground_at_world`] at world `(wx, wz)` — the same bilinear blend
/// of the containing tile's corners `smooth_surface_y` does, so `ground - relief_at_world` is the
/// pre-relief terrain to float precision. Layout DECISIONS read that (scatter slope thinning feeds
/// one RNG stream per region, so a single flipped tile would reshuffle every later prop, and the
/// vignette / decor sites with it); anything resting on the ground keeps the full height.
pub(crate) fn relief_at_world(wx: f32, wz: f32) -> f32 {
    let (gx, gz) = (wx + GX, wz + GZ);
    let (ix, iz) = (gx.floor() as i32, gz.floor() as i32);
    let (fx, fz) = (gx - ix as f32, gz - iz as f32);
    let (c00, c10) = (corner_relief(ix, iz), corner_relief(ix + 1, iz));
    let (c01, c11) = (corner_relief(ix, iz + 1), corner_relief(ix + 1, iz + 1));
    let a = c00 + (c10 - c00) * fx;
    let b = c01 + (c11 - c01) * fx;
    a + (b - a) * fz
}

fn smooth(e0: f32, e1: f32, x: f32) -> f32 {
    let t = ((x - e0) / (e1 - e0)).clamp(0.0, 1.0);
    t * t * (3.0 - 2.0 * t)
}

/// One octave of gradient-aligned gully noise: stripes CONSTANT along `dir` (the fall line) and
/// oscillating across it, one period per `cell`, from a 4×4 neighbourhood of jittered cell points
/// blended by a bell. ~[-1, 1].
fn gullies(x: f32, z: f32, dir: (f32, f32), cell: f32) -> f32 {
    let (px, pz) = (x / cell, z / cell);
    let (ix, iz) = (px.floor() as i32, pz.floor() as i32);
    let perp = (-dir.1, dir.0);
    let (mut acc, mut wsum) = (0.0f32, 0.0f32);
    for dz in -1..=2 {
        for dx in -1..=2 {
            let (gx, gz) = (ix + dx, iz + dz);
            let jx = vhash(gx.wrapping_mul(7) + 13, gz.wrapping_mul(11) + 5);
            let jz = vhash(gx.wrapping_mul(5) + 3, gz.wrapping_mul(13) + 17);
            let (ox, oz) = (px - (gx as f32 + jx), pz - (gz as f32 + jz));
            let w = (-(ox * ox + oz * oz) * 1.8).exp();
            // Per-cell phase so neighbouring cells' stripes interleave into branching runnels.
            let ph = vhash(gx.wrapping_mul(3) + 101, gz.wrapping_mul(17) + 7) * std::f32::consts::TAU;
            acc += ((ox * perp.0 + oz * perp.1) * std::f32::consts::TAU + ph).cos() * w;
            wsum += w;
        }
    }
    acc / wsum.max(1e-6)
}

fn build_relief() -> Arc<Vec<f32>> {
    let grid = tiles();
    let wet = water_near();
    let (w, h) = (COLS as usize, ROWS as usize);
    // 1. Distance (tiles) from every tile to the nearest class change / non-shelf tile.
    let eligible = |ix: i32, iz: i32| -> Option<i32> {
        let (_, cls) = tile_in(&grid, ix, iz)?;
        let ok = cls >= 3
            && wet[(iz * COLS + ix) as usize] == 0
            && cliff_exempt_base((ix as f32 + 0.5) / MAP_SCALE, (iz as f32 + 0.5) / MAP_SCALE);
        ok.then_some(cls)
    };
    let mut d = vec![f32::INFINITY; w * h];
    for iz in 0..ROWS {
        for ix in 0..COLS {
            let k = (iz * COLS + ix) as usize;
            let Some(cls) = eligible(ix, iz) else {
                d[k] = 0.0;
                continue;
            };
            let edge = (-1..=1).any(|dz| {
                (-1..=1).any(|dx| (dx, dz) != (0, 0) && tile_in(&grid, ix + dx, iz + dz).map(|t| t.1) != Some(cls))
            });
            if edge {
                d[k] = 0.0;
            }
        }
    }
    crate::alpine::chamfer(&mut d, w, h);
    // 2. Corner field: distance = min over the corner's four tiles (off-grid = 0).
    let (cw, ch) = (w + 1, h + 1);
    let td = |ix: i32, iz: i32| -> f32 {
        if ix < 0 || iz < 0 || ix >= COLS || iz >= ROWS { 0.0 } else { d[(iz * COLS + ix) as usize] }
    };
    let mut dc = vec![0.0f32; cw * ch];
    for cz in 0..ch as i32 {
        for cx in 0..cw as i32 {
            dc[cz as usize * cw + cx as usize] = td(cx - 1, cz - 1).min(td(cx, cz - 1)).min(td(cx - 1, cz)).min(td(cx, cz));
        }
    }
    let dcf = |cx: i32, cz: i32| -> f32 {
        let (x, z) = (cx.clamp(0, cw as i32 - 1), cz.clamp(0, ch as i32 - 1));
        dc[z as usize * cw + x as usize]
    };
    // 2b. SHAPE distance: the chamfer field heavily blurred (3 separable 7-tap box passes,
    //     sigma ~3.5 tiles). Raw chamfer isolines are straight axis / 45-degree lines and its
    //     medial axis a sharp hip-roof crease, so shapes keyed to it read as faceted pyramids
    //     and its onset as a ruler-straight light/dark seam under a low sun. The raw `dc` still
    //     gates the zero band; only the runnel direction reads the blurred field.
    let mut ds = dc.clone();
    for _ in 0..3 {
        let mut t = vec![0.0f32; cw * ch];
        for z in 0..ch {
            for x in 0..cw {
                let mut acc = 0.0;
                for k in -3i32..=3 {
                    acc += ds[z * cw + (x as i32 + k).clamp(0, cw as i32 - 1) as usize];
                }
                t[z * cw + x] = acc / 7.0;
            }
        }
        for z in 0..ch {
            for x in 0..cw {
                let mut acc = 0.0;
                for k in -3i32..=3 {
                    acc += t[(z as i32 + k).clamp(0, ch as i32 - 1) as usize * cw + x];
                }
                ds[z * cw + x] = acc / 7.0;
            }
        }
    }
    let dsf = |cx: i32, cz: i32| -> f32 {
        let (x, z) = (cx.clamp(0, cw as i32 - 1), cz.clamp(0, ch as i32 - 1));
        ds[z as usize * cw + x as usize]
    };
    // 3. Raw relief, fading in right behind the zero band. It used to start ~4 tiles in (so the
    //    final blur could never leak into the band), which left a dead-flat apron along every lip:
    //    the GTAO pass reads exactly-planar ground as unoccluded but switches on over even a few
    //    cm of relief, so that apron's inner edge showed as a crisp, ruler-straight light/dark
    //    seam across the snow. Starting at the band — onset wobbling 0.2..2 tiles — puts that
    //    switch-on at the lip, where the rim geometry already breaks the plane, and makes the
    //    rest a soft wavy fade. (The blur's tiny leak into the band is zeroed after step 5.)
    let start = EDGE;
    let mut r = vec![0.0f32; cw * ch];
    for cz in 0..ch as i32 {
        for cx in 0..cw as i32 {
            let dd = dcf(cx, cz);
            if dd <= start {
                continue;
            }
            let (x, z) = (cx as f32 - GX, cz as f32 - GZ);
            // Signed undulation, faded in past a noise-jittered onset (0.2..2 tiles beyond the zero
            // band). No edge-relative DOME: on these narrow tier rings a dome tilts a whole band along
            // every edge the same way, which a low sun turned into a ruler-straight bright/dark seam.
            // Mounds and gullies tilt every which way, so the fade-in has no coherent tilt to show
            // and the shelf reads as wind-sculpted ground. (The fade uses the RAW distance: the
            // blurred one sags on rings this narrow and would starve them of relief.)
            let on = start + 0.2 + 1.8 * vnoise(x * 0.12 + 41.0, z * 0.12 - 23.0);
            let ramp = smooth(on, on + 4.0, dd);
            let mounds = (vnoise((0.857 * x - 0.515 * z) * 0.055 + 31.0, (0.515 * x + 0.857 * z) * 0.055 - 7.0) - 0.5) * 1.7
                + (vnoise((0.602 * x - 0.799 * z) * 0.14 - 11.0, (0.799 * x + 0.602 * z) * 0.14 + 19.0) - 0.5) * 0.5;
            // Runnel direction = gradient of the (blurred) edge distance: the gullies drain across
            // the shelf toward its rim, the way meltwater cuts toward a cliff edge.
            let (gx, gz) = ((dsf(cx + 1, cz) - dsf(cx - 1, cz)) * 0.5, (dsf(cx, cz + 1) - dsf(cx, cz - 1)) * 0.5);
            let gl = (gx * gx + gz * gz).sqrt();
            let gully = if gl > 1e-3 {
                let dir = (gx / gl, gz / gl);
                // Strongest mid-flank: fade on the spine (gl -> 0).
                (gullies(x, z, dir, 7.5) * 0.40 + gullies(x * 1.9 + 17.0, z * 1.9 - 5.0, dir, 7.5) * 0.12) * gl.min(1.0)
            } else {
                0.0
            };
            // Signed: the inf-convolution below is L-Lipschitz for any sign; near the band the
            // ramp keeps |r| far under MAX_GRAD x distance, so the band isn't dragged down.
            r[cz as usize * cw + cx as usize] = ramp * (mounds + gully);
        }
    }
    // 4. Lipschitz envelope (inf-convolution with the chamfer metric): |Δ| ≤ MAX_GRAD per unit
    //    axis-wise and √2·MAX_GRAD diagonally (for either sign — a min of L-Lipschitz cones).
    let l = MAX_GRAD;
    let ld = MAX_GRAD * std::f32::consts::SQRT_2;
    for z in 0..ch {
        for x in 0..cw {
            let mut v = r[z * cw + x];
            if x > 0 { v = v.min(r[z * cw + x - 1] + l); }
            if z > 0 { v = v.min(r[(z - 1) * cw + x] + l); }
            if x > 0 && z > 0 { v = v.min(r[(z - 1) * cw + x - 1] + ld); }
            if x + 1 < cw && z > 0 { v = v.min(r[(z - 1) * cw + x + 1] + ld); }
            r[z * cw + x] = v;
        }
    }
    for z in (0..ch).rev() {
        for x in (0..cw).rev() {
            let mut v = r[z * cw + x];
            if x + 1 < cw { v = v.min(r[z * cw + x + 1] + l); }
            if z + 1 < ch { v = v.min(r[(z + 1) * cw + x] + l); }
            if x + 1 < cw && z + 1 < ch { v = v.min(r[(z + 1) * cw + x + 1] + ld); }
            if x > 0 && z + 1 < ch { v = v.min(r[(z + 1) * cw + x - 1] + ld); }
            r[z * cw + x] = v;
        }
    }
    // 5. Soften the envelope's creases. Inf-convolution with the chamfer metric leaves straight
    //    axis / 45-degree crease lines wherever the cap binds (and a slope kink where the relief
    //    starts), which the sun picked out as hard lines across the snow — the very facet look
    //    this module exists to remove. Two separable 3-tap box passes (a tent over ±2 corners
    //    per axis) round them off. An average of L-Lipschitz copies is L-Lipschitz, so the nav
    //    bound above still holds.
    for _ in 0..2 {
        let mut t = vec![0.0f32; cw * ch];
        for z in 0..ch {
            for x in 0..cw {
                let (a, b) = (x.saturating_sub(1), (x + 1).min(cw - 1));
                t[z * cw + x] = (r[z * cw + a] + r[z * cw + x] + r[z * cw + b]) / 3.0;
            }
        }
        for z in 0..ch {
            let (a, b) = (z.saturating_sub(1), (z + 1).min(ch - 1));
            for x in 0..cw {
                r[z * cw + x] = (t[a * cw + x] + t[z * cw + x] + t[b * cw + x]) / 3.0;
            }
        }
    }
    // Re-flatten the band: the blur leaks a few mm into it from the fade-in, but the corners
    // touching another class (wall tops, ramp steps) must keep their exact old height. The
    // leak is tiny next to MAX_GRAD, so zeroing it can't break the nav step bound.
    for (v, &d) in r.iter_mut().zip(dc.iter()) {
        if d <= EDGE {
            *v = 0.0;
        }
    }
    Arc::new(r)
}
