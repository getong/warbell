//! Natural cliff walls for the terrain mesher (a `worldmap` child module — it reads the private
//! tile grid). Replaces the flat-shaded "crisp low-poly crag" lattice of `build_terrain_chunk`.
//!
//! - **Contour-following lips** ([`corner_xz`]): a mesa tier's edge is a contour of the tier
//!   field, but the walls were drawn along tile EDGES, so every curved rim read as a staircase of
//!   1u steps from any distance. Each lip corner now slides (≤ [`LIP_MAX`]) onto the 0.5 iso-line
//!   of a tent-filtered "above the tier" indicator — the smooth contour the staircase
//!   approximates — so rims curve. Pure function of the corner, so every quad / wall sharing it
//!   agrees (no cracks), and only corners whose four tiles are dry land split into exactly two
//!   tiers ever move.
//! - **Eroded, smooth-shaded faces** ([`wall`]): per-vertex normals from the continuous
//!   displacement field (finite differences along the contour tangent and world Y) instead of
//!   per-facet normals; vertical erosion flutes (ridged noise, long in Y), rock strata ledges, a
//!   talus lean at the foot, and a rounded lip (the top rows' normals roll toward the sky).
//!   Every displacement is a pure function of world position + depth below the lip, exactly like
//!   the old lattice, so shared columns stay welded.

use super::*;

/// Furthest a lip corner may slide off the tile grid (world units). Below half a tile, so the
/// moved corner can't cross a neighbour and `round()` recovers its grid index.
const LIP_MAX: f32 = 0.42;
/// Facet columns per 1-tile wall.
const NC: usize = 4;

/// The two tier classes a lip corner sits between (`(lo, hi)`), or `None` when the corner is not
/// a clean two-tier wall corner on dry land (coast, water margin, three tiers, no wall).
fn split(grid: &Grid, cx: i32, cz: i32) -> Option<(i32, i32)> {
    let wet = water_near();
    let mut cls = [0i32; 4];
    for (k, (ix, iz)) in [(cx - 1, cz - 1), (cx, cz - 1), (cx - 1, cz), (cx, cz)].into_iter().enumerate() {
        let (_, h) = tile_in(grid, ix, iz)?;
        if wet[(iz * COLS + ix) as usize] != 0 {
            return None;
        }
        cls[k] = h;
    }
    let lo = *cls.iter().min()?;
    let hi = *cls.iter().max()?;
    if hi - lo < 2 || cls.iter().any(|&c| c - lo > 1 && hi - c > 1) {
        return None;
    }
    Some((lo, hi))
}

/// Tent-filtered fraction of tiles ABOVE class `m` around grid point `(x, z)` (corner space).
fn above(grid: &Grid, x: f32, z: f32, m: f32) -> f32 {
    const R: f32 = 2.3;
    let (mut s, mut ws) = (0.0f32, 0.0f32);
    for iz in (z - R).floor() as i32..=(z + R).ceil() as i32 {
        for ix in (x - R).floor() as i32..=(x + R).ceil() as i32 {
            let d = ((ix as f32 + 0.5 - x).powi(2) + (iz as f32 + 0.5 - z).powi(2)).sqrt();
            let w = (1.0 - d / R).max(0.0);
            if w <= 0.0 {
                continue;
            }
            let up = tile_in(grid, ix, iz).is_some_and(|(_, h)| h as f32 > m);
            s += w * up as u8 as f32;
            ws += w;
        }
    }
    s / ws.max(1e-6)
}

/// (offset, unit contour tangent) for lip corner `(cx, cz)`; `None` for an unmoved corner.
fn lip(cx: i32, cz: i32) -> Option<((f32, f32), (f32, f32))> {
    // Snow-massif corners are the continuous surface the ground sampler reads at the GRID point:
    // never slide them (a moved corner on a slope would float / bury whatever stands there).
    if super::alpine_massif::corner_y(cx, cz).is_some() {
        return None;
    }
    let grid = tiles();
    let (lo, hi) = split(&grid, cx, cz)?;
    let m = (lo + hi) as f32 * 0.5;
    let (x, z) = (cx as f32, cz as f32);
    let e = 0.35;
    let f0 = above(&grid, x, z, m);
    let gx = (above(&grid, x + e, z, m) - above(&grid, x - e, z, m)) / (2.0 * e);
    let gz = (above(&grid, x, z + e, m) - above(&grid, x, z - e, m)) / (2.0 * e);
    let g2 = gx * gx + gz * gz;
    if g2 < 1e-4 {
        return None;
    }
    let k = (0.5 - f0) / g2;
    let (mut ox, mut oz) = (gx * k, gz * k);
    let l = (ox * ox + oz * oz).sqrt();
    if l > LIP_MAX {
        ox *= LIP_MAX / l;
        oz *= LIP_MAX / l;
    }
    let gl = g2.sqrt();
    Some(((ox, oz), (-gz / gl, gx / gl)))
}

/// World XZ of terrain grid corner `(cx, cz)`: the grid point, slid onto the tier contour for a
/// mesa-wall lip corner.
pub(super) fn corner_xz(cx: i32, cz: i32) -> (f32, f32) {
    let (ox, oz) = lip(cx, cz).map(|l| l.0).unwrap_or((0.0, 0.0));
    (cx as f32 + ox - GX, cz as f32 + oz - GZ)
}

/// Contour tangent at the (possibly moved) lip corner nearest world `(wx, wz)`, aligned with `dir`.
fn tangent_at(wx: f32, wz: f32, dir: (f32, f32)) -> (f32, f32) {
    let (cx, cz) = ((wx + GX).round() as i32, (wz + GZ).round() as i32);
    match lip(cx, cz) {
        Some((_, (tx, tz))) if tx * dir.0 + tz * dir.1 >= 0.0 => (tx, tz),
        Some((_, (tx, tz))) => (-tx, -tz),
        None => dir,
    }
}

/// Direction pointing DOWNHILL at world `(wx, wz)` — pure function of position (shared columns
/// of perpendicular walls agree). Off-map / sea reads low, so coastal cliffs lean seaward.
fn downhill(wx: f32, wz: f32) -> (f32, f32) {
    let hcl = |dx: f32, dz: f32| -> f32 {
        tile_at((wx + GX + dx).floor() as i32, (wz + GZ + dz).floor() as i32).map(|(_, h)| h as f32).unwrap_or(0.0)
    };
    let d = 0.9;
    let ox = hcl(-d, 0.0) - hcl(d, 0.0);
    let oz = hcl(0.0, -d) - hcl(0.0, d);
    let l = (ox * ox + oz * oz).sqrt();
    if l < 1e-3 { (0.0, 0.0) } else { (ox / l, oz / l) }
}

/// Displaced position of a wall point at world `(x, y, z)`, `depth` below its lip.
fn displaced(x: f32, y: f32, z: f32, depth: f32) -> [f32; 3] {
    // 0 at the lip (stays welded to the top quad), full from ~1.2u down.
    let w = (depth / 1.2).clamp(0.0, 1.0);
    let w = w * w * (3.0 - 2.0 * w);
    if w <= 1e-4 {
        return [x, y, z];
    }
    let (ox, oz) = downhill(x, z);
    // Vertical erosion flutes: ridged noise, ~1.1u across, stretched ~5x in Y (runnels + spurs).
    let fl = vnoise(x * 0.92 + y * 0.10 + 3.0, z * 0.92 - y * 0.08 - 11.0);
    let flute = 1.0 - (2.0 * fl - 1.0).abs();
    let flute2 = vnoise(x * 2.1 - y * 0.25 + 41.0, z * 2.1 + y * 0.21 + 7.0);
    // Strata ledges: the face steps out a little every ~1.3u of height, the band height wandering.
    let band = (y / 1.3 + vnoise(x * 0.21 + 5.0, z * 0.21 - 9.0) * 1.6).fract();
    let ledge = band * band * (3.0 - 2.0 * band);
    // Foot talus: the base swells outward like scree-footed rock.
    let talus = (depth - 1.2).max(0.0).min(2.0) * 0.12;
    let out = 0.26 + talus + (flute - 0.5) * 0.46 + (flute2 - 0.5) * 0.16 + (ledge - 0.5) * 0.14;
    // Small lateral wander so long faces don't read as extruded.
    let jx = vnoise(x * 0.7 + y * 0.6 + 13.0, z * 0.7 - y * 0.4) - 0.5;
    let jz = vnoise(z * 0.7 + y * 0.5 + 37.0, x * 0.7 + y * 0.7 - 21.0) - 0.5;
    [x + (ox * out + jx * 0.22) * w, y, z + (oz * out + jz * 0.22) * w]
}

fn sub(a: [f32; 3], b: [f32; 3]) -> [f32; 3] {
    [a[0] - b[0], a[1] - b[1], a[2] - b[2]]
}
fn cross(a: [f32; 3], b: [f32; 3]) -> [f32; 3] {
    [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]
}
fn norm(v: [f32; 3]) -> [f32; 3] {
    let l = (v[0] * v[0] + v[1] * v[1] + v[2] * v[2]).sqrt().max(1e-6);
    [v[0] / l, v[1] / l, v[2] / l]
}

/// One subdivided cliff wall from the lip edge (`ya`→`yb` over `pa`→`pb`) down to the lower
/// shelf (`ba`, `bb`, already ≤ the lip). `n` = the wall's outward axis normal (orientation
/// reference), `ctop` / `cbot` the lip / foot vertex colours. Vertex alpha carries the NEGATIVE
/// cliffness flag the terrain shader keys the rock layers on.
#[allow(clippy::too_many_arguments)]
pub(super) fn wall(
    pa: (f32, f32),
    pb: (f32, f32),
    ya: f32,
    yb: f32,
    ba: f32,
    bb: f32,
    n: [f32; 3],
    ctop: [f32; 4],
    cbot: [f32; 4],
    idx: &mut Vec<u32>,
    pos: &mut Vec<[f32; 3]>,
    nrm: &mut Vec<[f32; 3]>,
    col: &mut Vec<[f32; 4]>,
) {
    let drop = ((ya - ba) + (yb - bb)) * 0.5;
    let cliffk = ((drop - 0.40) / 0.90).clamp(0.0, 1.0);
    let bot_a = ba - CLIFF_SKIRT;
    let bot_b = bb - CLIFF_SKIRT;
    // Interior rows on fixed world-Y levels (see CLIFF_ROW) — welded shared columns.
    let lip_hi = ya.max(yb);
    let bot_lo = bot_a.min(bot_b);
    let k_hi = ((lip_hi - 0.10) / CLIFF_ROW).floor() as i32;
    let k_lo = ((bot_lo + 0.10) / CLIFF_ROW).ceil() as i32;
    let mut levels: Vec<f32> = Vec::new();
    let mut k = k_hi;
    while k >= k_lo && levels.len() < 14 {
        levels.push(k as f32 * CLIFF_ROW);
        k -= 1;
    }
    let nrows = levels.len() + 2;
    // Wall direction and the contour tangents at both ends (shared by the neighbouring walls, so
    // the shading normals match across every column — smooth round a curved rim).
    let (dx, dz) = (pb.0 - pa.0, pb.1 - pa.1);
    let dl = (dx * dx + dz * dz).sqrt().max(1e-4);
    let dir = (dx / dl, dz / dl);
    let ta = tangent_at(pa.0, pa.1, dir);
    let tb = tangent_at(pb.0, pb.1, dir);
    let base = pos.len() as u32;
    for ci in 0..=NC {
        let t = ci as f32 / NC as f32;
        let x0 = pa.0 + dx * t;
        let z0 = pa.1 + dz * t;
        let lip = ya + (yb - ya) * t;
        let bot = bot_a + (bot_b - bot_a) * t;
        let tg = norm([ta.0 + (tb.0 - ta.0) * t, 0.0, ta.1 + (tb.1 - ta.1) * t]);
        for rj in 0..nrows {
            let y = if rj == 0 {
                lip
            } else if rj == nrows - 1 {
                bot
            } else {
                levels[rj - 1].clamp(bot, lip)
            };
            let p = displaced(x0, y, z0, lip - y);
            // Smooth normal: finite differences of the continuous surface along the contour
            // tangent and down the face.
            let e = 0.12;
            let s1 = sub(
                displaced(x0 + tg[0] * e, y, z0 + tg[2] * e, lip - y),
                displaced(x0 - tg[0] * e, y, z0 - tg[2] * e, lip - y),
            );
            let s2 = sub(displaced(x0, y + e, z0, lip - y - e), displaced(x0, y - e, z0, lip - y + e));
            let mut nv = norm(cross(s1, s2));
            if nv[0] * n[0] + nv[2] * n[2] < 0.0 {
                nv = [-nv[0], -nv[1], -nv[2]];
            }
            // Rounded lip: the top rows lean toward the sky so the rim reads weathered, not
            // knife-cut (the geometry stays welded to the top quad). Each rim row gets a FIXED
            // up-ness and only its sideways direction follows the flutes: the snow line sits
            // between these two rows, and when their up-ness followed the flutes' tilt (even
            // through a lerp toward +Y) it zig-zagged column to column into vertical white dashes
            // along every snowy rim — a picket fence.
            let up_fix = match rj {
                0 => Some(0.96),
                1 => Some(0.40),
                _ => None,
            };
            let nv = match up_fix {
                Some(u) => {
                    let h = (nv[0] * nv[0] + nv[2] * nv[2]).sqrt();
                    let (hx, hz) = if h > 0.2 { (nv[0] / h, nv[2] / h) } else { (n[0], n[2]) };
                    let s = (1.0f32 - u * u).sqrt();
                    [hx * s, u, hz * s]
                }
                None => nv,
            };
            // Top→bottom tone gradient + a broad value jitter (no per-facet speckle now that the
            // rock texture carries the detail).
            let fr = ((lip - y) / (lip - bot).max(0.3)).clamp(0.0, 1.0);
            let tone = 0.90 + (vnoise(x0 * 0.6 + y * 0.4, z0 * 0.6 - y * 0.3) - 0.5) * 0.30;
            pos.push(p);
            nrm.push(nv);
            col.push([
                (ctop[0] + (cbot[0] - ctop[0]) * fr) * tone,
                (ctop[1] + (cbot[1] - ctop[1]) * fr) * tone,
                (ctop[2] + (cbot[2] - ctop[2]) * fr) * tone,
                // Cliffness fades in over the first ~0.5u below the lip so the rock melts out of
                // the top-surface colour instead of a hard seam.
                -(cliffk * ((lip - y) / 0.5).clamp(0.0, 1.0)),
            ]);
        }
    }
    // Same winding as the old per-facet triangles (outward-facing).
    let nr = nrows as u32;
    for ci in 0..NC as u32 {
        for rj in 0..nr - 1 {
            let ia = base + ci * nr + rj;
            let ib = base + (ci + 1) * nr + rj;
            let ic = base + (ci + 1) * nr + rj + 1;
            let id = base + ci * nr + rj + 1;
            idx.extend_from_slice(&[ia, ib, ic, ia, ic, id]);
        }
    }
}
