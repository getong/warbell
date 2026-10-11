//! The central **castle** and its village (spec `2026-10-11-zamek-v2-design.md` §2, layout v3).
//!
//! The fort is a FIXED irregular polygon enceinte ([`ENCEINTE`], nine corners, the same every seed)
//! built from `castle_kit.glb` pieces tier by tier as the Defense upgrades land ([`CastleKind`]):
//! the old colony's ruins and roofless keep → a log palisade with timber gates and corner posts
//! (watchtowers, then stone towers on the Towers track) → a stone curtain with round / D / square
//! corner towers and gatehouses, the keep re-roofed then rebuilt as a donjon. The old bell tower
//! stands from the start; its live bell swings (`spawn_bell_swing`). Inside, only the castle's own
//! buildings lean against the curtain (`town_kit.glb`: barracks, stable, store, cart shed, smithy,
//! granary, infirmary) round an open courtyard; outside the W gate the market square (tavern,
//! Maud's house) and a street village along the King's Road whose houses rise one by one.
//!
//! This module owns the **geometry**; the gameplay on it lives elsewhere: the keep's HP and the
//! night siege in `siege.rs`, the gate leaves in `gates.rs`, the bell ring in `interaction.rs`,
//! the tower defenders in `defenses.rs`. Polygon queries ([`wall_inset`], [`in_footprint`],
//! [`in_courtyard`], [`outside_dist`]) replace the old rectangle everywhere castle-local; the flat
//! open ring round it (and the village lobe) is `worldmap::castle_ring_dist`. Kit pieces and plots
//! register oriented boxes in [`crate::blockers`] (the walls lazily, as they're built).
//! Small primitive props (paving, braziers, yard clutter, the well, hens) still use the procedural
//! textured materials below (shared with the town as [`VillageMats`]).

use bevy::asset::RenderAssetUsages;
use bevy::image::{ImageAddressMode, ImageFilterMode, ImageSampler, ImageSamplerDescriptor};
use bevy::mesh::{Indices, PrimitiveTopology, VertexAttributeValues};
use bevy::prelude::*;
use bevy::render::render_resource::{Extent3d, TextureDimension, TextureFormat};

use crate::biome::BiomeEntity;
use crate::economy::Defenses;
use crate::palette::srgb;

// ── Palette (sRGB hex, from the TS materials) ────────────────────────────────────
// Castle/wall masonry — darkened ~10% off the old bright greys (0x7d7e86 / 0x5c5d64 / 0x969aa4)
// so the keep + curtain walls read as weathered, mature stone instead of flat pale blocks, without
// going gloomy. Paired with the higher-contrast, grime-streaked `tex_stone` below. (House stone
// `H_STONE` stays lighter.)
const STONE: u32 = 0x8a8b95;
const DARK_STONE: u32 = 0x6a6b73;
const LIGHT_STONE: u32 = 0x9da1ac;
const BEAM: u32 = 0x5a3a22;
const ROOF: u32 = 0x7a2f28;
const BANNER: u32 = 0x2f5fa6;
const WOOD: u32 = 0x3a2618;
const SOIL: u32 = 0x6b4a2a;
const CROP: u32 = 0x8fae4a;
const GOLD: u32 = 0xe0b04a;
const COBBLE: u32 = 0x8b8a86; // courtyard paving
const PACKED: u32 = 0x6e5436; // bare packed-earth yard ("klepisko") before the walls
const STRAW: u32 = 0xcaa84e; // hay bales / thatched sacks
const HEN: u32 = 0xe7e2d6; // courtyard fowl (off-white plumage)
const H_WALL: u32 = 0xd3b78b;
const H_ROOF: u32 = 0x6b3322;
const H_ROOF2: u32 = 0x6e6256; // weathered grey-brown shingle (house variety)
const THATCH: u32 = 0xb89b4f; // bound-straw roofing (huts, the farm barn)
const IRON: u32 = 0x6a6e72; // arms & armour (racks, blades, helms)
const PARCHMENT: u32 = 0xe6d9b5; // notice/bounty-board paper
const H_STONE: u32 = 0x86868e;
const WINDOW_GLOW: u32 = 0xffd58c;
const BRONZE: u32 = 0xb9892f;
const BRONZE_DARK: u32 = 0x7c5a1e;
const TORCH_FLAME: u32 = 0xff7a2a;
const BRAZIER_FLAME: u32 = 0xff5a1e; // deeper orange for the big brazier flame shell (`M::Ember`)
const SLIT: u32 = 0x23242a; // arrow-slit / shadow inset

const HALF_PI: f32 = std::f32::consts::FRAC_PI_2;
/// Texture tiles every ~this many world units (keeps block scale consistent).
const TILE: f32 = 1.5;

// The enceinte — castle v3 (`docs/superpowers/specs/2026-10-11-zamek-v2-design.md` §2; the author:
// "the fort doesn't have to be square — it must be more realistic"): a FIXED, hand-designed
// irregular polygon, the same every seed. Nine corners clockwise (x east, z south), sides 12.5–30u,
// every interior angle convex (124–162°), ≈2440u² (the old 56×42 rectangle was 2352). The three gate
// sides stay axis-aligned — the W main gate on a N–S side, the S gate and the N postern on E–W sides
// — so the gate passages, their leaves and the orks' gate boxes (`gates.rs`) stay box-aligned; every
// other side runs at an angle, the NE / E / SE sides bending the way a builder follows the rise. The
// keep stands on the north side by the postern, the old bell tower beside the S gate.
pub(crate) const ENCEINTE: [Vec2; 9] = [
    Vec2::new(-22.0, -20.0), // 0 NW
    Vec2::new(-10.0, -24.0), // 1 — the N side (postern) runs 1 → 2
    Vec2::new(14.0, -24.0),  // 2
    Vec2::new(29.0, -14.0),  // 3 NE
    Vec2::new(31.0, 8.0),    // 4 E
    Vec2::new(18.0, 24.0),   // 5 SE — the S side (gate + bell tower) runs 5 → 6
    Vec2::new(-12.0, 24.0),  // 6
    Vec2::new(-28.0, 13.0),  // 7 SW — the W side (main gate) runs 7 → 8
    Vec2::new(-28.0, -9.0),  // 8
];
/// The enceinte side each gate is cut into (side `i` runs `ENCEINTE[i]` → `ENCEINTE[i + 1]`).
const W_SIDE: usize = 7;
const S_SIDE: usize = 5;
const N_SIDE: usize = 1;
/// The W wall line (x) and the N/S wall lines (±z) — exact for the three gate sides; for DISTANT
/// users only a rough "how far out the walls reach" (wildlife sanctuary, meadow + town-plot offsets,
/// road junctions). Castle-local code uses the polygon: [`wall_inset`], [`in_footprint`],
/// [`in_courtyard`], [`outside_dist`].
pub(crate) const HALF_X: f32 = 28.0;
pub(crate) const HALF_Z: f32 = 24.0;
/// The gate opening — the kit's `ck_timber_gate` / `ck_gatehouse` passage (2.8u wide × 2.7u high: a
/// loaded cart passes).
pub(crate) const GATE_GAP: f32 = 2.8;
/// Gate positions on their sides (spec §5): the WEST main gate (King's Road to the bay), the SOUTH
/// gate (the ork side, under the bell tower), the NORTH postern (forest + quarry) east of the keep.
pub(crate) const W_GATE_Z: f32 = 0.0;
pub(crate) const S_GATE_X: f32 = 0.0;
pub(crate) const N_GATE_X: f32 = 6.0;

// ── Material slots ───────────────────────────────────────────────────────────────
// `pub(crate)` so the town's producer buildings (`town_meshes`) render with the SAME
// textured materials as the keep, via the shared [`VillageMats`] resource.
#[derive(Clone, Copy)]
pub(crate) enum M {
    Stone,
    DarkStone,
    LightStone,
    HouseStone,
    Plaster,
    Wood,
    Beam,
    Roof,
    HouseRoof,
    /// Weathered grey-brown shingle — the second roof hue that breaks up the dwelling rows.
    HouseRoof2,
    /// Bound straw — hut + barn roofing.
    Thatch,
    /// Dull arms-and-armour metal (rack blades, helms, strongbox bands).
    Iron,
    /// Paper pinned to the notice / bounty boards.
    Parchment,
    Soil,
    Cobble,
    Packed,
    Straw,
    Hen,
    Banner,
    Bronze,
    BronzeDark,
    Crop,
    Slit,
    Gold,
    Window,
    Flame,
    /// Deep-orange fire shell at a LOW emissive — the brazier flame's outer layer. `M::Flame`'s
    /// ×6 emissive is right for a torch-speck but a brazier-sized mesh at ×6 clips through AgX
    /// to a cream-white egg on camera; this slot stays saturated fire-orange at size.
    Ember,
}

#[derive(Clone)]
pub(crate) struct Mats {
    h: std::collections::HashMap<u8, Handle<StandardMaterial>>,
}
impl Mats {
    pub(crate) fn get(&self, m: M) -> Handle<StandardMaterial> {
        self.h[&(m as u8)].clone()
    }
}

/// The shared, procedurally-textured village material set (plaster, shingle, timber, stone, soil,
/// cobble, glowing window, …). Built once with the keep and held as a resource so the town's
/// producer buildings + build plots render in the same textured aesthetic as the castle.
#[derive(Resource, Clone)]
pub(crate) struct VillageMats(pub(crate) Mats);

// ── Procedural textures (ported from textures.ts) ────────────────────────────────
struct Rng(u32);
impl Rng {
    fn f(&mut self) -> f32 {
        self.0 = self.0.wrapping_add(0x6d2b_79f5);
        let mut t = self.0;
        t = (t ^ (t >> 15)).wrapping_mul(t | 1);
        t ^= t.wrapping_add((t ^ (t >> 7)).wrapping_mul(t | 61));
        ((t ^ (t >> 14)) as f32) / 4_294_967_296.0
    }
}

fn rgb(hex: u32) -> [f32; 3] {
    [((hex >> 16) & 0xff) as f32, ((hex >> 8) & 0xff) as f32, (hex & 0xff) as f32]
}
/// Shift each channel by `amt`×255, clamp to bytes.
fn shade(c: [f32; 3], amt: f32) -> [u8; 3] {
    let f = |v: f32| (v + amt * 255.0).clamp(0.0, 255.0).round() as u8;
    [f(c[0]), f(c[1]), f(c[2])]
}

const TN: usize = 128;
struct Canvas {
    px: Vec<u8>,
}
impl Canvas {
    fn new(base: [u8; 3]) -> Self {
        let mut px = vec![0u8; TN * TN * 4];
        for i in 0..TN * TN {
            px[i * 4] = base[0];
            px[i * 4 + 1] = base[1];
            px[i * 4 + 2] = base[2];
            px[i * 4 + 3] = 255;
        }
        Canvas { px }
    }
    fn rect(&mut self, x: f32, y: f32, w: f32, h: f32, c: [u8; 3]) {
        let x0 = (x.floor().max(0.0)) as usize;
        let y0 = (y.floor().max(0.0)) as usize;
        let x1 = ((x + w).ceil().min(TN as f32)) as usize;
        let y1 = ((y + h).ceil().min(TN as f32)) as usize;
        for yy in y0..y1 {
            for xx in x0..x1 {
                let i = (yy * TN + xx) * 4;
                self.px[i] = c[0];
                self.px[i + 1] = c[1];
                self.px[i + 2] = c[2];
            }
        }
    }
    fn disc(&mut self, cx: f32, cy: f32, r: f32, c: [u8; 3], a: f32) {
        let x0 = ((cx - r).floor().max(0.0)) as usize;
        let y0 = ((cy - r).floor().max(0.0)) as usize;
        let x1 = ((cx + r).ceil().min(TN as f32)) as usize;
        let y1 = ((cy + r).ceil().min(TN as f32)) as usize;
        for yy in y0..y1 {
            for xx in x0..x1 {
                let dx = xx as f32 - cx;
                let dy = yy as f32 - cy;
                if dx * dx + dy * dy <= r * r {
                    let i = (yy * TN + xx) * 4;
                    for k in 0..3 {
                        self.px[i + k] = (self.px[i + k] as f32 * (1.0 - a) + c[k] as f32 * a) as u8;
                    }
                }
            }
        }
    }
    /// Separable box blur with toroidal wrap, so a Repeat-tiled texture stays seamless.
    /// Softens hard rect/grout edges → quieter, less shimmery at a distance.
    fn blur(&mut self, radius: usize) {
        if radius == 0 {
            return;
        }
        let n = TN;
        let win = (radius * 2 + 1) as f32;
        let src = self.px.clone();
        let mut tmp = vec![0u8; n * n * 4];
        for y in 0..n {
            for x in 0..n {
                let mut acc = [0f32; 3];
                for k in 0..=radius * 2 {
                    let sx = (x + n + k - radius) % n;
                    let i = (y * n + sx) * 4;
                    for c in 0..3 {
                        acc[c] += src[i + c] as f32;
                    }
                }
                let o = (y * n + x) * 4;
                for c in 0..3 {
                    tmp[o + c] = (acc[c] / win) as u8;
                }
                tmp[o + 3] = 255;
            }
        }
        for y in 0..n {
            for x in 0..n {
                let mut acc = [0f32; 3];
                for k in 0..=radius * 2 {
                    let sy = (y + n + k - radius) % n;
                    let i = (sy * n + x) * 4;
                    for c in 0..3 {
                        acc[c] += tmp[i + c] as f32;
                    }
                }
                let o = (y * n + x) * 4;
                for c in 0..3 {
                    self.px[o + c] = (acc[c] / win) as u8;
                }
            }
        }
    }
    fn into_image(self) -> Image {
        let mut img = Image::new(
            Extent3d { width: TN as u32, height: TN as u32, depth_or_array_layers: 1 },
            TextureDimension::D2,
            self.px,
            TextureFormat::Rgba8UnormSrgb,
            RenderAssetUsages::default(),
        );
        img.sampler = ImageSampler::Descriptor(ImageSamplerDescriptor {
            address_mode_u: ImageAddressMode::Repeat,
            address_mode_v: ImageAddressMode::Repeat,
            address_mode_w: ImageAddressMode::Repeat,
            mag_filter: ImageFilterMode::Linear,
            min_filter: ImageFilterMode::Linear,
            mipmap_filter: ImageFilterMode::Linear,
            ..default()
        });
        img
    }
}

fn speckle(cv: &mut Canvas, r: &mut Rng, n: usize, c: [f32; 3]) {
    for _ in 0..n {
        let x = (r.f() * TN as f32).floor();
        let y = (r.f() * TN as f32).floor();
        cv.rect(x, y, 1.0, 1.0, shade(c, (r.f() - 0.5) * 0.1));
    }
}

/// Ashlar courses — castle stone (running-bond bricks + mortar + bevel highlight). `pub(crate)` so
/// the rival fort (`rival.rs`) can bake sandstone-hued masonry from the same generator (textured,
/// not flat blocks) while keeping its own warm palette.
pub(crate) fn tex_stone(hex: u32) -> Image {
    let c = rgb(hex);
    // Deep recessed mortar (was −0.07): a real shadowed joint gives the blocks 3D relief instead
    // of the old near-flat grout that vanished at distance.
    let mut cv = Canvas::new(shade(c, -0.13));
    let mut r = Rng(0x511 ^ hex);
    let (rows, cols) = (4usize, 4usize);
    let (bh, bw) = (TN as f32 / rows as f32, TN as f32 / cols as f32);
    for ry in 0..rows {
        let off = (ry % 2) as f32 * (bw / 2.0);
        for i in -1..=cols as i32 {
            let x = i as f32 * bw + off + 1.5;
            let y = ry as f32 * bh + 1.5;
            // Per-block value drift (gentler — was ±0.22): every stone weathers to its own tone, so a
            // wall reads as aged masonry rather than one uniform grey slab, without looking grubby.
            cv.rect(x, y, bw - 3.0, bh - 3.0, shade(c, (r.f() - 0.5) * 0.13));
            cv.rect(x, y, bw - 3.0, 1.5, shade(c, 0.07)); // top bevel — lit upper lip
            cv.rect(x, y + bh - 4.5, bw - 3.0, 1.5, shade(c, -0.11)); // bottom AO — block sits in its own shadow
        }
    }
    // Weathering: broad soft grime/damp stains drifting across the face (soot above torches, rain
    // streaks) at low alpha so they tint the stone for a lived-in, mature look — not hard blotches.
    for _ in 0..9 {
        let x = r.f() * TN as f32;
        let y = r.f() * TN as f32;
        let rad = 6.0 + r.f() * 16.0;
        cv.disc(x, y, rad, shade(c, -0.10 - r.f() * 0.08), 0.07 + r.f() * 0.07);
    }
    speckle(&mut cv, &mut r, 500, c);
    cv.into_image()
}

/// Plaster / stucco — house walls (mottled blobs + speckle).
fn tex_plaster(hex: u32) -> Image {
    let c = rgb(hex);
    let mut cv = Canvas::new(shade(c, 0.0));
    let mut r = Rng(0x9a3 ^ hex);
    for _ in 0..90 {
        let x = r.f() * TN as f32;
        let y = r.f() * TN as f32;
        let rad = 4.0 + r.f() * 14.0;
        cv.disc(x, y, rad, shade(c, (r.f() - 0.5) * 0.5), 0.06 + r.f() * 0.08);
    }
    speckle(&mut cv, &mut r, 400, c);
    cv.into_image()
}

/// Wood planks — beams/doors (vertical planks + gaps + grain streaks). `pub(crate)` for the rival
/// fort's timber (gates/poles).
pub(crate) fn tex_wood(hex: u32, planks: usize) -> Image {
    let c = rgb(hex);
    let mut cv = Canvas::new(shade(c, 0.0));
    let mut r = Rng(0x4d2 ^ hex);
    let pw = TN as f32 / planks as f32;
    for i in 0..planks {
        let x = i as f32 * pw;
        cv.rect(x, 0.0, pw, TN as f32, shade(c, (r.f() - 0.5) * 0.1));
        cv.rect(x, 0.0, 1.5, TN as f32, shade(c, -0.22)); // plank gap
        for _ in 0..7 {
            let gx = x + 3.0 + r.f() * (pw - 6.0);
            cv.rect(gx, 0.0, 0.8, TN as f32, shade(c, (r.f() - 0.5) * 0.14)); // grain streak
        }
    }
    cv.into_image()
}

/// Roof shingles — overlapping rows (offset tiles + shadow band per row).
fn tex_shingle(hex: u32) -> Image {
    let c = rgb(hex);
    let mut cv = Canvas::new(shade(c, -0.12));
    let mut r = Rng(0x5f1 ^ hex);
    let (rows, cols) = (6usize, 6usize);
    let (rh, cw) = (TN as f32 / rows as f32, TN as f32 / cols as f32);
    for ry in 0..rows {
        let off = (ry % 2) as f32 * (cw / 2.0);
        for i in -1..=cols as i32 {
            let x = i as f32 * cw + off;
            let y = ry as f32 * rh;
            cv.rect(x + 0.5, y, cw - 1.0, rh * 0.86, shade(c, (r.f() - 0.5) * 0.14));
            cv.rect(x + 0.5, y + rh * 0.86, cw - 1.0, rh * 0.14, shade(c, -0.2)); // shadow line
        }
    }
    cv.into_image()
}

/// Thatch — bound straw courses (horizontal rows, stalk streaks, a shadow line per course).
fn tex_thatch(hex: u32) -> Image {
    let c = rgb(hex);
    let mut cv = Canvas::new(shade(c, -0.04));
    let mut r = Rng(0x7a7 ^ hex);
    let rows = 8usize;
    let rh = TN as f32 / rows as f32;
    for ry in 0..rows {
        let y = ry as f32 * rh;
        cv.rect(0.0, y, TN as f32, rh - 1.5, shade(c, (r.f() - 0.5) * 0.10));
        cv.rect(0.0, y + rh - 1.5, TN as f32, 1.5, shade(c, -0.22)); // course shadow
        for _ in 0..26 {
            let x = r.f() * TN as f32;
            cv.rect(x, y + r.f() * 2.0, 1.0, rh - 2.0 - r.f() * 3.0, shade(c, (r.f() - 0.5) * 0.16)); // stalks
        }
    }
    speckle(&mut cv, &mut r, 300, c);
    cv.into_image()
}

/// Cobbles — courtyard paving as IRREGULAR Voronoi flagstones, NOT a brick grid (a regular
/// running-bond pattern read as cheap stamped bricks). One jittered seed per cell → organic
/// stone shapes; the nearest seed gives each stone its own colour drift; the gap between the
/// nearest and 2nd-nearest seed is the mortar joint, so joints wind naturally around the stones.
/// Seeds wrap toroidally so the texture still tiles seamlessly, and a faint per-stone dome +
/// light blur keep it reading as worn stone instead of flat tiles.
fn tex_cobble(hex: u32) -> Image {
    let c = rgb(hex);
    let mut cv = Canvas::new(shade(c, 0.0));
    let mut r = Rng(0xc0b ^ hex);
    const CELLS: usize = 4; // stones per axis (~0.37 world-unit flagstones at TILE 1.5)
    let cw = TN as f32 / CELLS as f32;
    // Jittered seed position + per-stone value drift, one per cell.
    let mut sx = [[0f32; CELLS]; CELLS];
    let mut sy = [[0f32; CELLS]; CELLS];
    let mut sh = [[0f32; CELLS]; CELLS];
    for gy in 0..CELLS {
        for gx in 0..CELLS {
            sx[gy][gx] = (gx as f32 + 0.18 + r.f() * 0.64) * cw;
            sy[gy][gx] = (gy as f32 + 0.18 + r.f() * 0.64) * cw;
            sh[gy][gx] = (r.f() - 0.5) * 0.15; // light vs dark stone
        }
    }
    let n = CELLS as i32;
    const MORTAR_W: f32 = 2.6; // joint half-width in px
    for py in 0..TN {
        for px in 0..TN {
            let (fx, fy) = (px as f32 + 0.5, py as f32 + 0.5);
            let gx0 = (fx / cw).floor() as i32;
            let gy0 = (fy / cw).floor() as i32;
            let (mut d1, mut d2, mut best) = (1e9f32, 1e9f32, 0f32);
            for dy in -1..=1 {
                for dx in -1..=1 {
                    let (gi, gj) = (gx0 + dx, gy0 + dy);
                    let (wi, wj) = (gi.rem_euclid(n), gj.rem_euclid(n));
                    let ex = sx[wj as usize][wi as usize] + ((gi - wi) / n) as f32 * TN as f32;
                    let ey = sy[wj as usize][wi as usize] + ((gj - wj) / n) as f32 * TN as f32;
                    let d = ((fx - ex).powi(2) + (fy - ey).powi(2)).sqrt();
                    if d < d1 {
                        d2 = d1;
                        d1 = d;
                        best = sh[wj as usize][wi as usize];
                    } else if d < d2 {
                        d2 = d;
                    }
                }
            }
            // Mortar where the nearest two cells are nearly equidistant (the stone border).
            let edge = ((d2 - d1) / MORTAR_W).clamp(0.0, 1.0);
            // Faint dome: a touch brighter at the stone centre, darker toward its rim.
            let dome = (0.06 - d1 / cw * 0.10).clamp(-0.06, 0.06);
            let grit = (((px * 131 + py * 197) & 31) as f32 / 31.0 - 0.5) * 0.02;
            let amt = -0.17 * (1.0 - edge) + (best + dome + grit) * edge;
            let col = shade(c, amt);
            let i = (py * TN + px) * 4;
            cv.px[i] = col[0];
            cv.px[i + 1] = col[1];
            cv.px[i + 2] = col[2];
        }
    }
    speckle(&mut cv, &mut r, 120, c);
    cv.blur(1); // take the hard aliased edge off the mortar
    cv.into_image()
}

/// Tilled soil — farm bed (horizontal furrow ridges + speckle).
fn tex_soil(hex: u32) -> Image {
    let c = rgb(hex);
    let mut cv = Canvas::new(shade(c, 0.0));
    let mut r = Rng(0x501 ^ hex);
    let mut y = 0.0;
    while y < TN as f32 {
        cv.rect(0.0, y, TN as f32, 5.0, shade(c, 0.05));
        cv.rect(0.0, y + 5.0, TN as f32, 5.0, shade(c, -0.08));
        y += 10.0;
    }
    speckle(&mut cv, &mut r, 700, c);
    cv.into_image()
}

/// Packed earth — the bare courtyard "klepisko" the young settlement stands on before the walls
/// are raised. Trodden flat (no furrows — that's tilled `tex_soil`): big SOFT damp/dry mottling
/// (overlapping low-alpha discs, no hard rectangles — those read as a repeating grid once tiled),
/// faint surviving grass flecks trodden into the dirt, and a few small pebbles. Deliberately low
/// contrast: the worn-ground feel comes from broad value drift, not busy noise.
fn tex_packed(hex: u32) -> Image {
    let c = rgb(hex);
    let mut cv = Canvas::new(shade(c, 0.0));
    let mut r = Rng(0x9e3 ^ hex);
    // Broad soft mottled patches (damp vs sun-dried earth) — large overlapping discs at low
    // alpha so tones flow into each other instead of tiling as visible blocks.
    for _ in 0..46 {
        let x = r.f() * TN as f32;
        let y = r.f() * TN as f32;
        let rad = 7.0 + r.f() * 18.0;
        cv.disc(x, y, rad, shade(c, (r.f() - 0.5) * 0.13), 0.22 + r.f() * 0.16);
    }
    // Trodden-in grass remnants — small muted green-tan flecks where the lawn survives the
    // foot traffic ("przebłyski trawy"), denser as soft discs + a few single-pixel blades.
    let grass = [c[0] * 0.78 + 18.0, c[1] * 0.9 + 42.0, c[2] * 0.75];
    for _ in 0..26 {
        let x = r.f() * TN as f32;
        let y = r.f() * TN as f32;
        cv.disc(x, y, 1.0 + r.f() * 2.2, shade(grass, (r.f() - 0.4) * 0.12), 0.4 + r.f() * 0.3);
    }
    for _ in 0..70 {
        let x = (r.f() * TN as f32).floor();
        let y = (r.f() * TN as f32).floor();
        cv.rect(x, y, 1.0, 1.0 + r.f() * 2.0, shade(grass, (r.f() - 0.3) * 0.15));
    }
    // Sparse trodden-in pebbles (a light stone over its own little shadow) — fewer + smaller
    // than before so they read as grit, not confetti.
    for _ in 0..40 {
        let x = r.f() * TN as f32;
        let y = r.f() * TN as f32;
        let s = 1.0 + r.f() * 1.6;
        cv.rect(x, y + s, s, s * 0.5, shade(c, -0.12)); // contact shadow
        cv.rect(x, y, s, s, shade(c, 0.10 + r.f() * 0.10)); // pebble
    }
    speckle(&mut cv, &mut r, 450, c);
    cv.into_image()
}

// ── Material table ───────────────────────────────────────────────────────────────
/// The scanned cobble paving material (`assets/forest_pbr/s_cobble_*`, packed DDS or PNG).
fn cobble_pbr(images: &mut Assets<Image>) -> Result<StandardMaterial, String> {
    use crate::realforest::load::texture;
    let albedo = images.add(texture("forest_pbr/s_cobble_albedo.png", true, None)?);
    let normal = images.add(texture("forest_pbr/s_cobble_normal.png", false, None)?);
    let ormh = images.add(texture("forest_pbr/s_cobble_ormh.png", false, None)?);
    Ok(StandardMaterial {
        base_color_texture: Some(albedo),
        normal_map_texture: Some(normal),
        occlusion_texture: Some(ormh.clone()),
        metallic_roughness_texture: Some(ormh),
        perceptual_roughness: 1.0,
        metallic: 1.0,
        reflectance: 0.35,
        cull_mode: None,
        ..default()
    })
}

pub(crate) fn build_mats(images: &mut Assets<Image>, std_mats: &mut Assets<StandardMaterial>) -> Mats {
    let mut h = std::collections::HashMap::new();
    // Double-sided: our custom gable/slab/taper meshes don't all wind CCW-outward, and
    // back-face culling would drop those faces (the see-through roof bug). Bevy flips the
    // normal for back fragments so lighting stays correct.
    let mut tex = |img: Image, rough: f32, m: M| {
        let t = images.add(img);
        let handle = std_mats.add(StandardMaterial {
            base_color: Color::WHITE,
            base_color_texture: Some(t),
            perceptual_roughness: rough,
            cull_mode: None,
            double_sided: true,
            ..default()
        });
        h.insert(m as u8, handle);
    };
    tex(tex_stone(STONE), 0.84, M::Stone); // weathered masonry, but catches a soft highlight (was dead-matte 0.97)
    tex(tex_stone(DARK_STONE), 0.84, M::DarkStone);
    tex(tex_stone(LIGHT_STONE), 0.82, M::LightStone);
    tex(tex_stone(H_STONE), 0.82, M::HouseStone);
    tex(tex_plaster(H_WALL), 0.95, M::Plaster);
    tex(tex_wood(WOOD, 3), 1.0, M::Wood);
    tex(tex_wood(BEAM, 4), 1.0, M::Beam);
    tex(tex_shingle(ROOF), 0.85, M::Roof);
    tex(tex_shingle(H_ROOF), 0.85, M::HouseRoof);
    tex(tex_shingle(H_ROOF2), 0.88, M::HouseRoof2);
    tex(tex_thatch(THATCH), 1.0, M::Thatch);
    tex(tex_soil(SOIL), 1.0, M::Soil);

    // Yard grounds (Packed klepisko / Cobble courtyard): fully OPAQUE — `worn_slab` cuts the
    // ragged rim into the geometry itself. (Alpha-Blend rims rendered as a washed-out film at
    // grazing angles; alpha-Mask fought the depth prepass. See `worn_slab`.)
    let mut ground_tex = |img: Image, rough: f32, m: M| {
        let t = images.add(img);
        h.insert(m as u8, std_mats.add(StandardMaterial {
            base_color: Color::WHITE,
            base_color_texture: Some(t),
            perceptual_roughness: rough,
            cull_mode: None,
            double_sided: true,
            ..default()
        }));
    };
    ground_tex(tex_cobble(COBBLE), 0.95, M::Cobble);
    ground_tex(tex_packed(PACKED), 1.0, M::Packed);
    // Map-centre rework phase 2: the paving is the scanned `s_cobble` set (Poly Haven cobblestone_05,
    // `tools/blender_forest/cobble_set.sh`) — dark setts with earth in the joints, so the keep apron
    // and the gate passages sit in the trodden-mud yard instead of reading as a pale flat sheet.
    // Falls back to the procedural Voronoi flagstones above when the set isn't shipped.
    match cobble_pbr(images) {
        Ok(m) => {
            h.insert(M::Cobble as u8, std_mats.add(m));
        }
        Err(e) => warn!("castle: s_cobble set missing, keeping the procedural paving — {e}"),
    }

    let mut solid = |hex: u32, rough: f32, metal: f32, m: M| {
        h.insert(m as u8, std_mats.add(StandardMaterial {
            base_color: srgb(hex),
            perceptual_roughness: rough,
            metallic: metal,
            cull_mode: None,
            double_sided: true,
            ..default()
        }));
    };
    solid(STRAW, 0.95, 0.0, M::Straw);
    solid(IRON, 0.42, 0.78, M::Iron);
    solid(PARCHMENT, 0.95, 0.0, M::Parchment);
    solid(HEN, 0.9, 0.0, M::Hen);
    solid(BANNER, 0.8, 0.0, M::Banner);
    solid(BRONZE, 0.45, 0.7, M::Bronze);
    solid(BRONZE_DARK, 0.5, 0.6, M::BronzeDark);
    solid(CROP, 0.9, 0.0, M::Crop);
    solid(SLIT, 0.9, 0.0, M::Slit);

    let mut glow = |hex: u32, intensity: f32, metal: f32, m: M| {
        h.insert(m as u8, std_mats.add(StandardMaterial {
            base_color: srgb(hex),
            emissive: srgb(hex).to_linear() * intensity,
            perceptual_roughness: 0.5,
            metallic: metal,
            ..default()
        }));
    };
    glow(GOLD, 0.8, 0.6, M::Gold);
    glow(WINDOW_GLOW, 2.2, 0.0, M::Window);
    glow(TORCH_FLAME, 6.0, 0.0, M::Flame);
    glow(BRAZIER_FLAME, 2.4, 0.0, M::Ember);

    Mats { h }
}

// ── Mesh helpers ─────────────────────────────────────────────────────────────────
fn scale_uv(mut m: Mesh, su: f32, sv: f32) -> Mesh {
    if let Some(VertexAttributeValues::Float32x2(uvs)) = m.attribute_mut(Mesh::ATTRIBUTE_UV_0) {
        for uv in uvs.iter_mut() {
            uv[0] *= su;
            uv[1] *= sv;
        }
    }
    m
}

/// A textured box centred at (x,y,z), UVs scaled so the texture tiles at ~`TILE` units.
pub(crate) fn bx(w: f32, h: f32, d: f32, x: f32, y: f32, z: f32) -> Mesh {
    let horiz = ((w + d) * 0.5 / TILE).max(0.6);
    let vert = (h / TILE).max(0.6);
    scale_uv(Mesh::from(Cuboid::new(w, h, d)), horiz, vert).translated_by(Vec3::new(x, y, z))
}

pub(crate) fn flat(mut m: Mesh) -> Mesh {
    m.duplicate_vertices();
    m.compute_flat_normals();
    m
}

/// A 4-sided pyramid roof, base at `base_y`, apex up (45° so faces align to a square).
pub(crate) fn cyl(r: f32, h: f32, x: f32, y: f32, z: f32) -> Mesh {
    Cylinder::new(r, h).mesh().resolution(12).build().translated_by(Vec3::new(x, y, z))
}

/// Tapered 12-gon frustum (bell body): top radius `rt`, bottom `rb`.
pub(crate) fn taper(rt: f32, rb: f32, h: f32, y: f32) -> Mesh {
    let seg = 12usize;
    let mut pos: Vec<[f32; 3]> = Vec::new();
    let mut idx: Vec<u32> = Vec::new();
    let tau = std::f32::consts::TAU;
    for i in 0..seg {
        let a = i as f32 / seg as f32 * tau;
        let (co, si) = (a.cos(), a.sin());
        pos.push([co * rb, y - h / 2.0, si * rb]);
        pos.push([co * rt, y + h / 2.0, si * rt]);
    }
    for i in 0..seg {
        let b0 = (i * 2) as u32;
        let t0 = b0 + 1;
        let b1 = (((i + 1) % seg) * 2) as u32;
        let t1 = b1 + 1;
        idx.extend_from_slice(&[b0, t0, t1, b0, t1, b1]);
    }
    let mut m = Mesh::new(PrimitiveTopology::TriangleList, RenderAssetUsages::default());
    m.insert_attribute(Mesh::ATTRIBUTE_POSITION, pos);
    m.insert_indices(Indices::U32(idx));
    flat(m)
}

/// Gable (triangular-prism) roof — ridge along X, slopes facing ±Z, gable triangles ±X.
pub(crate) fn gable(span_x: f32, span_z: f32, rise: f32, base_y: f32) -> Mesh {
    let hx = span_x / 2.0;
    let hz = span_z / 2.0;
    let (y0, y1) = (base_y, base_y + rise);
    // 0,1,2 = +X end (back-left, back-right, apex); 3,4,5 = -X end
    let pos = vec![
        [hx, y0, -hz], [hx, y0, hz], [hx, y1, 0.0],
        [-hx, y0, -hz], [-hx, y0, hz], [-hx, y1, 0.0],
    ];
    // planar UV from (x,z) so shingles tile across the roof
    let uv = vec![
        [hx / TILE, -hz / TILE], [hx / TILE, hz / TILE], [hx / TILE, 0.0],
        [-hx / TILE, -hz / TILE], [-hx / TILE, hz / TILE], [-hx / TILE, 0.0],
    ];
    let idx = vec![
        0, 2, 1, // +X gable (normal +X)
        3, 4, 5, // -X gable (normal -X)
        1, 2, 5, 1, 5, 4, // +Z slope (normal +Y/+Z)
        0, 3, 5, 0, 5, 2, // -Z slope (normal +Y/-Z)
        0, 4, 3, 0, 1, 4, // underside (normal -Y)
    ];
    let mut m = Mesh::new(PrimitiveTopology::TriangleList, RenderAssetUsages::default());
    m.insert_attribute(Mesh::ATTRIBUTE_POSITION, pos);
    m.insert_attribute(Mesh::ATTRIBUTE_UV_0, uv);
    m.insert_indices(Indices::U32(idx));
    flat(m)
}

/// Smooth low-frequency field used to fray the yard rim and drift its brightness —
/// a few sin octaves (≈1–3-unit features), cheap and seamless in world space.
fn wear_noise(x: f32, z: f32) -> f32 {
    (x * 1.31 + 1.7).sin() * (z * 1.13 - 2.3).cos()
        + (x * 0.53 + z * 0.61 + 4.5).sin() * 0.6
        + (x * 2.70 - z * 2.20 + 0.8).sin() * 0.25
}

/// The yard ground sheet — a vertex grid whose rim is CUT BY THE NOISE FIELD: grid cells whose
/// wear value falls below the threshold are simply not emitted, so trodden fingers of paving
/// reach into the lawn and grass bites back into the yard along a crisp ragged outline (no
/// hard rectangle edge). Fully opaque — earlier versions faded the rim with vertex ALPHA, but
/// blended rims render as a washed-out translucent film at grazing angles, and alpha-Mask
/// fights the depth prepass (whose cutoff ignores vertex alpha → sky-coloured holes). Geometry
/// can't lie. The interior carries a low-frequency brightness mottle in the vertex colour so
/// the tiling texture stops reading as a grid. `noise_amp` scales how ragged the rim is;
/// `mottle` the interior value drift.
fn worn_slab(w: f32, d: f32, y: f32, fray: f32, noise_amp: f32, mottle: f32) -> Mesh {
    let hw = w / 2.0 + fray;
    let hd = d / 2.0 + fray;
    // Finer grid → the noise-cut rim steps in ~quarter-tile teeth instead of the old blocky
    // half-tile sawtooth that read as a pixelated cut-out against the lawn.
    let step = 0.25_f32;
    let nx = (2.0 * hw / step).ceil() as usize;
    let nz = (2.0 * hd / step).ceil() as usize;
    let mut pos: Vec<[f32; 3]> = Vec::with_capacity((nx + 1) * (nz + 1));
    let mut nrm: Vec<[f32; 3]> = Vec::with_capacity(pos.capacity());
    let mut uv: Vec<[f32; 2]> = Vec::with_capacity(pos.capacity());
    let mut col: Vec<[f32; 4]> = Vec::with_capacity(pos.capacity());
    let mut wear: Vec<f32> = Vec::with_capacity(pos.capacity());
    for iz in 0..=nz {
        for ix in 0..=nx {
            // Spread the grid exactly across [-hw, hw] (no clamped duplicate columns).
            let x = -hw + 2.0 * hw * ix as f32 / nx as f32;
            let z = -hd + 2.0 * hd * iz as f32 / nz as f32;
            // Distance inside the OUTER rect; the wear band spans ~2×fray of it.
            let d_in = (hw - x.abs()).min(hd - z.abs());
            let t = d_in / (fray * 2.0) + wear_noise(x, z) * noise_amp - 0.5 * noise_amp;
            // Low-frequency brightness drift breaks the texture's tile repetition.
            let b = 1.0
                + mottle * (x * 0.37 + 1.1).sin() * (z * 0.41 - 0.6).cos()
                + mottle * 0.7 * (x * 0.13 - z * 0.17 + 2.0).sin();
            pos.push([x, y, z]);
            nrm.push([0.0, 1.0, 0.0]);
            uv.push([x / TILE, z / TILE]);
            col.push([b, b, b, 1.0]);
            wear.push(t);
        }
    }
    let mut idx: Vec<u32> = Vec::with_capacity(nx * nz * 6);
    let row = (nx + 1) as u32;
    for iz in 0..nz as u32 {
        for ix in 0..nx as u32 {
            let i0 = iz * row + ix;
            let (i1, i2, i3) = (i0 + 1, i0 + row + 1, i0 + row);
            // Keep the cell only where the worn surface survives (mean corner wear above the
            // cut) — the rim outline follows the noise, half-cell crisp.
            let mean = (wear[i0 as usize] + wear[i1 as usize] + wear[i2 as usize] + wear[i3 as usize]) / 4.0;
            if mean < 0.5 {
                continue;
            }
            // Same up-facing winding as `slab`.
            idx.extend_from_slice(&[i0, i2, i1, i0, i3, i2]);
        }
    }
    let mut m = Mesh::new(PrimitiveTopology::TriangleList, RenderAssetUsages::default());
    m.insert_attribute(Mesh::ATTRIBUTE_POSITION, pos);
    m.insert_attribute(Mesh::ATTRIBUTE_NORMAL, nrm);
    m.insert_attribute(Mesh::ATTRIBUTE_UV_0, uv);
    m.insert_attribute(Mesh::ATTRIBUTE_COLOR, col);
    m.insert_indices(Indices::U32(idx));
    m
}

/// MikkTSpace tangents for a normal-mapped mesh (the scanned cobble); a mesh that can't take them
/// is returned as-is (its normal map then simply doesn't perturb).
fn with_tangents(mut m: Mesh) -> Mesh {
    let _ = m.generate_tangents();
    m
}

/// A flat upward-facing slab quad at height `y` (cobble courtyard), UV tiled.
#[allow(dead_code)] // superseded by `worn_slab` for the yard; kept for flat textured sheets
fn slab(w: f32, d: f32, y: f32) -> Mesh {
    let (hw, hd) = (w / 2.0, d / 2.0);
    let pos = vec![[-hw, y, -hd], [hw, y, -hd], [hw, y, hd], [-hw, y, hd]];
    let nrm = vec![[0.0, 1.0, 0.0]; 4];
    let uv = vec![[0.0, 0.0], [w / TILE, 0.0], [w / TILE, d / TILE], [0.0, d / TILE]];
    let idx = vec![0u32, 2, 1, 0, 3, 2];
    let mut m = Mesh::new(PrimitiveTopology::TriangleList, RenderAssetUsages::default());
    m.insert_attribute(Mesh::ATTRIBUTE_POSITION, pos);
    m.insert_attribute(Mesh::ATTRIBUTE_NORMAL, nrm);
    m.insert_attribute(Mesh::ATTRIBUTE_UV_0, uv);
    m.insert_indices(Indices::U32(idx));
    m
}

pub(crate) fn bake(m: Mesh, pos: Vec3, rot: f32, scale: Vec3) -> Mesh {
    m.scaled_by(scale).rotated_by(Quat::from_rotation_y(rot)).translated_by(pos)
}

// ── Keep, walls, gates: `castle_kit.glb` pieces (see `castle_kit.rs` and [`kit_layout`]) ──────────
/// Keep centre (world XZ): on the north side, its back ≈5u off the N curtain, the postern just east
/// of it, so everything south of its door down to the S gate is open courtyard.
pub const KEEP_POS: Vec2 = Vec2::new(-2.0, -14.5);
/// The keep's footprint half-extents (`ck_keep_t2`, the largest tier: x ±4.8, z −3.4..4.7).
pub(crate) const KEEP_HALF: Vec2 = Vec2::new(4.8, 4.4);
/// World Z of the keep's front (the door + timber stair, local +Z).
pub(crate) const KEEP_FRONT: f32 = KEEP_POS.y + 4.7;
/// Wall thickness for collision and the courtyard inset (the curtain body is 1.4, the palisade's
/// logs on their bank about the same).
pub(crate) const WALL_THICK: f32 = 1.3;
/// Gate passage clear height (the kit opening).
pub(crate) const GATE_H: f32 = 2.7;

/// Factor the human-scale world (hero/orks/townsfolk/houses) was enlarged by — see
/// `player::HERO_SCALE`. Keeps the courtyard dwellings in proportion with the rescaled hero.
pub(crate) const WORLD_BUMP: f32 = 1.35;
/// Vertical-only stretch applied to every building (houses, keep, towers, town producer buildings)
/// — base sits at y=0 so this raises the roofline without touching the footprint (so pathfinding /
/// collision are unaffected). Bump this one number to make all buildings taller/shorter.
pub(crate) const BUILDING_TALLER: f32 = 1.15;
/// Per-dwelling root scale: the original squat (0.9, 0.74, 0.9) × [`WORLD_BUMP`], with the Y also
/// ×[`BUILDING_TALLER`]. Shared by the spawn transform, the shutter window placement
/// (`shutters.rs`), the collision blocker and the chimney-smoke anchors so they never desync.
/// Castle v2 (spec §1) re-scales the dwellings to the hero: eaves ≈2.0u, door ≈1.4u
/// (×1.32 in Y over the old squat cottages, ×1.2 on the footprint to keep the proportions).
#[allow(dead_code)] // the old primitive dwellings' scale (shutters.rs placement)
pub(crate) const HOUSE_SCALE: Vec3 =
    Vec3::new(0.9 * WORLD_BUMP * 1.2, 0.74 * WORLD_BUMP * BUILDING_TALLER * 1.32, 0.9 * WORLD_BUMP * 1.2);

// ── The war bell ─────────────────────────────────────────────────────────────────
// The old colony's bell tower is the kit piece `ck_bell_tower` (its own baked bell cut away,
// `castle_kit::Edit::NoBell`); the live swinging assembly hangs in its open belfry
// (`spawn_bell_swing` + `swing_bell`) so ringing it actually rocks the bronze.

/// World-XZ of the war bell — the BELL TOWER on the S wall line, west of the S gate (spec §4/§5:
/// the gate "under the bell tower", where the orks come from). Shared with `interaction.rs`'s ring
/// zone so the prompt and the prop can never drift apart.
pub const BELL_POS: Vec2 = Vec2::new(S_GATE_X - 5.6, HALF_Z);
/// Half-width of the bell tower's shaft (`ck_bell_tower`: x ±1.96).
pub(crate) const BELL_TOWER_HALF: f32 = 1.96;
/// How far Pip's platform + ladder reach into the yard from the wall line (`ck_bell_tower` z 3.98).
const BELL_TOWER_YARD: f32 = 3.98;
/// Frame yaw — the headstock runs along the wall, so the bell swings in and out of the town.
const BELL_YAW: f32 = 0.0;
/// Headstock hinge height: the live bell hangs in the kit tower's open belfry (5.2–7.55u), its lip
/// (≈1.26 below the hinge) where the kit's own bell hung (5.82).
const BELL_PIVOT_Y: f32 = 7.1;

/// Tags the hinged headstock + bell assembly (rocked by [`swing_bell`]).
#[derive(Component)]
pub struct BellSwing;
/// Tags the clapper + pull-rope pivot — swings on the same hinge with lag/overshoot so the
/// ball visibly hammers the sound-bow.
#[derive(Component)]
pub struct BellClapper;

/// Elapsed-secs timestamp of the last ring (E press in `interaction.rs`, or the night arriving on
/// its own — see [`swing_bell`]). `None` once the toll has decayed. Transient VFX — not saved.
#[derive(Resource, Default)]
pub struct BellRing(pub Option<f32>);

/// The moving half of the war bell: two pivot entities hinged at the crossbeam centre — the
/// headstock + bronze bell under `BellSwing`, the clapper + hanging pull-rope under `BellClapper`.
/// All part meshes are LOCAL to the hinge (pivot at the origin), so a single rotation swings them.
fn spawn_bell_swing(commands: &mut Commands, meshes: &mut Assets<Mesh>, mats: &Mats) {
    let base = Transform::from_translation(Vec3::new(BELL_POS.x, BELL_PIVOT_Y, BELL_POS.y))
        .with_rotation(Quat::from_rotation_y(BELL_YAW));
    // (mesh, material) parts of the bell proper: wooden headstock, bronze profile with a proper
    // shoulder-waist-flare curve, dark crown + sound-bow lip, one gold accent band.
    let bell_parts: Vec<(Mesh, M)> = vec![
        (bx(0.55, 0.22, 0.22, 0.0, -0.09, 0.0), M::Beam), // headstock the bell hangs off
        (cyl(0.08, 0.14, 0.0, -0.27, 0.0), M::BronzeDark), // crown knob
        (taper(0.17, 0.31, 0.30, -0.49), M::Bronze), // shoulder
        (cyl(0.32, 0.05, 0.0, -0.62, 0.0), M::Gold), // accent band
        (taper(0.31, 0.37, 0.34, -0.81), M::Bronze), // waist
        (taper(0.37, 0.50, 0.22, -1.09), M::Bronze), // sound-bow flare
        (cyl(0.52, 0.08, 0.0, -1.22, 0.0), M::BronzeDark), // lip
    ];
    let clapper_parts: Vec<(Mesh, M)> = vec![
        (bx(0.07, 0.85, 0.07, 0.0, -0.62, 0.0), M::BronzeDark), // arm
        (
            flat(Mesh::from(Sphere::new(0.11).mesh().ico(1).unwrap())
                .translated_by(Vec3::new(0.0, -1.06, 0.0))),
            M::BronzeDark,
        ), // ball
        (cyl(0.028, 0.62, 0.0, -1.42, 0.0), M::Straw), // pull rope, through the mouth
        (cyl(0.055, 0.1, 0.0, -1.76, 0.0), M::Beam), // rope-end grip
    ];
    for (tag, parts) in [(true, bell_parts), (false, clapper_parts)] {
        let mut e = commands.spawn((base, Visibility::default(), BiomeEntity));
        if tag {
            e.insert(BellSwing);
        } else {
            e.insert(BellClapper);
        }
        e.with_children(|p| {
            for (m, slot) in parts {
                p.spawn((
                    Mesh3d(meshes.add(m)),
                    MeshMaterial3d(mats.get(slot)),
                    Transform::default(),
                ));
            }
        });
    }
}

/// Rock the war bell. Idle: a whisper of wind sway so the prop never reads frozen. Rung: a hard
/// decaying toll swing; the clapper runs the same hinge with lag + overshoot (clamped to the
/// sound-bow) so it visibly hammers the wall. Also TOLLS the bell when the night arrives on its
/// own — prep ran out un-rung — because the bell IS the night's announcement either way.
/// Ungated VFX (keeps swinging over freezes), like the chimney smoke.
fn swing_bell(
    time: Res<Time>,
    siege: Res<crate::siege::Siege>,
    mut ring: ResMut<BellRing>,
    mut cues: MessageWriter<crate::audio::AudioCue>,
    mut prev_phase: Local<Option<crate::siege::GamePhase>>,
    mut belltest: Local<Option<bool>>,
    mut q: Query<(&mut Transform, Has<BellClapper>), Or<(With<BellSwing>, With<BellClapper>)>>,
) {
    let now = time.elapsed_secs();
    // `FOREST_BELLTEST=1`: re-toll on a loop so a shot/clip can frame the swing without a keypress
    // (a `FOREST_WAVE` boot starts already IN the wave — no Prep→Wave edge ever fires).
    if *belltest.get_or_insert_with(|| std::env::var("FOREST_BELLTEST").is_ok())
        && !ring.0.is_some_and(|t| now - t <= 12.0)
    {
        ring.0 = Some(now);
        cues.write(crate::audio::AudioCue::WarBell);
    }
    // Natural nightfall (Prep → Wave with no recent player ring) still swings + tolls. The 10s
    // guard covers the E-ring case: the skip floors prep to ~3s, so the phase edge lands while
    // that ring's swing is still live — don't double-toll it.
    let was = prev_phase.replace(siege.phase);
    if was.is_some_and(|w| w != siege.phase)
        && siege.phase == crate::siege::GamePhase::Wave
        && !ring.0.is_some_and(|t| now - t < 10.0)
    {
        ring.0 = Some(now);
        cues.write(crate::audio::AudioCue::WarBell);
    }
    // Toll fully decayed → back to idle sway.
    if ring.0.is_some_and(|t| now - t > 9.0) {
        ring.0 = None;
    }
    let sway = 0.015 * (now * 0.8).sin();
    let (bell, clapper) = match ring.0 {
        Some(t0) => {
            let dt = now - t0;
            let damp = (-dt * 0.55).exp();
            let b = 0.55 * damp * (dt * 7.0).sin();
            // The clapper lags the bell and over-swings, clamped to the sound-bow's inner wall
            // (≈0.38 rad of relative travel) so the ball never pokes through the bronze.
            let c_raw = 0.85 * damp * (dt * 7.0 - 0.6).sin();
            (b, b + (c_raw - b).clamp(-0.38, 0.38))
        }
        None => (0.0, 0.0),
    };
    for (mut tf, is_clapper) in &mut q {
        let theta = sway + if is_clapper { clapper } else { bell };
        tf.rotation = Quat::from_rotation_y(BELL_YAW) * Quat::from_rotation_x(theta);
    }
}

#[allow(dead_code)] // torches temporarily unspawned (read as unnatural); kept for easy restore
fn torch_parts() -> Vec<(Mesh, M)> {
    let mut v: Vec<(Mesh, M)> = Vec::new();
    v.push((bx(0.12, 1.0, 0.12, 0.0, 0.5, 0.0), M::Wood)); // post
    v.push((bx(0.22, 0.12, 0.22, 0.0, 1.04, 0.0), M::BronzeDark)); // bowl
    v.push((flat(Mesh::from(Sphere::new(0.16).mesh().ico(1).unwrap()).scaled_by(Vec3::new(1.0, 1.5, 1.0)).translated_by(Vec3::new(0.0, 1.22, 0.0))), M::Flame));
    v
}

/// A gate war-brazier — the torch's big sibling that lights the siege kill-zone OUTSIDE each
/// gate (see the brazier spawn loop + `firelight::brazier_light`). Heavier post, wide iron bowl,
/// a fat flame: reads as deliberate war-lighting, not a scaled-up torch.
fn brazier_parts() -> Vec<(Mesh, M)> {
    let mut v: Vec<(Mesh, M)> = Vec::new();
    v.push((bx(0.2, 1.1, 0.2, 0.0, 0.55, 0.0), M::Wood)); // heavy post
    v.push((bx(0.34, 0.1, 0.34, 0.0, 0.06, 0.0), M::BronzeDark)); // ground foot
    v.push((bx(0.5, 0.16, 0.5, 0.0, 1.18, 0.0), M::BronzeDark)); // wide bowl
    v.push((bx(0.42, 0.1, 0.42, 0.0, 1.28, 0.0), M::BronzeDark)); // bowl lip
    // Layered flame: a saturated deep-orange shell (`M::Ember`, low emissive — stays FIRE-coloured
    // on camera) around a small hot `M::Flame` core. One big `M::Flame` sphere clipped to a
    // cream-white egg on the first AFTER capture.
    v.push((flat(Mesh::from(Sphere::new(0.24).mesh().ico(1).unwrap()).scaled_by(Vec3::new(1.0, 1.5, 1.0)).translated_by(Vec3::new(0.0, 1.48, 0.0))), M::Ember));
    v.push((flat(Mesh::from(Sphere::new(0.13).mesh().ico(1).unwrap()).scaled_by(Vec3::new(1.0, 1.6, 1.0)).translated_by(Vec3::new(0.0, 1.42, 0.0))), M::Flame));
    v
}

// ── Rustic yard clutter ──────────────────────────────────────────────────────────
// Small work-yard props that dress the courtyard corners. Tagged `Always` — they used to be
// `PreWalls`, which meant buying the Palisade Walls DELETED every sign of life and left bare
// paving; now the settlement's working corners stay through the whole game. Built at local
// origin, base at y=0; the `build()` spawn closure bakes each cluster to its courtyard spot.
// Solid ground-level parts register tight, rotated footprints in `register_yard_blockers`,
// leaving the space between each cluster walkable. They sit at the courtyard corners (±10, ±6),
// clear of the keep, the bell, the gates and every house slot. More set dressing — and the
// upgrade-bought set pieces — live in `castle_decor.rs`.

/// A log lying along the X axis (for stacked woodpiles / windlass rollers).
pub(crate) fn log_x(r: f32, len: f32, y: f32, z: f32) -> Mesh {
    Cylinder::new(r, len)
        .mesh()
        .resolution(8)
        .build()
        .rotated_by(Quat::from_rotation_z(HALF_PI))
        .translated_by(Vec3::new(0.0, y, z))
}

/// Chopping block with a buried axe + a small stacked woodpile.
fn wood_yard_parts() -> Vec<(Mesh, M)> {
    let mut v: Vec<(Mesh, M)> = Vec::new();
    v.push((cyl(0.3, 0.5, 0.0, 0.25, 0.0), M::Wood)); // chopping block
    v.push((bx(0.05, 0.5, 0.05, 0.08, 0.55, 0.0), M::Beam)); // axe handle
    v.push((bx(0.2, 0.12, 0.06, 0.08, 0.78, 0.0), M::DarkStone)); // axe head
    // Pyramid-stacked logs beside the block (3 / 2 / 1).
    for (row, &(y, n)) in [(0.12_f32, 3i32), (0.33, 2), (0.54, 1)].iter().enumerate() {
        for k in 0..n {
            let z = -0.9 + (k as f32 - (n - 1) as f32 / 2.0) * 0.26;
            let m = if (row + k as usize) % 2 == 0 { M::Wood } else { M::Beam };
            v.push((log_x(0.11, 1.5, y, z), m));
        }
    }
    v
}

/// Two stacked hay bales (roped) with a couple of grain sacks at the base.
fn hay_corner_parts() -> Vec<(Mesh, M)> {
    let mut v: Vec<(Mesh, M)> = Vec::new();
    v.push((bx(0.9, 0.55, 0.55, 0.0, 0.28, 0.0), M::Straw));
    v.push((bx(0.9, 0.55, 0.55, 0.0, 0.83, 0.05), M::Straw));
    for x in [-0.25_f32, 0.25] {
        v.push((bx(0.92, 0.05, 0.58, x, 0.28, 0.0), M::Beam)); // binding rope
        v.push((bx(0.92, 0.05, 0.58, x, 0.83, 0.05), M::Beam));
    }
    for (sx, sz) in [(0.72_f32, 0.24_f32), (0.8, -0.22)] {
        v.push((taper(0.1, 0.2, 0.42, 0.21).translated_by(Vec3::new(sx, 0.0, sz)), M::Plaster)); // burlap sack
    }
    v
}

/// A hand-cart with side rails + two barrels (hooped) parked beside it.
fn cart_corner_parts() -> Vec<(Mesh, M)> {
    let mut v: Vec<(Mesh, M)> = Vec::new();
    v.push((bx(1.3, 0.12, 0.7, 0.0, 0.42, 0.0), M::Beam)); // bed
    for sz in [-0.34_f32, 0.34] {
        v.push((bx(1.3, 0.18, 0.06, 0.0, 0.55, sz), M::Wood)); // side rail
    }
    // Wheels (discs standing in the X/Y plane → cylinder axis along Z).
    for sz in [-0.4_f32, 0.4] {
        v.push((
            Cylinder::new(0.32, 0.08)
                .mesh()
                .resolution(10)
                .build()
                .rotated_by(Quat::from_rotation_x(HALF_PI))
                .translated_by(Vec3::new(-0.2, 0.32, sz)),
            M::Wood,
        ));
    }
    for sz in [-0.28_f32, 0.28] {
        v.push((bx(0.9, 0.06, 0.06, 0.85, 0.62, sz), M::Beam)); // handle shaft
    }
    for (cx, cz) in [(0.95_f32, -0.6_f32), (1.2, -0.35)] {
        v.push((taper(0.26, 0.3, 0.62, 0.31).translated_by(Vec3::new(cx, 0.0, cz)), M::Wood)); // barrel
        v.push((cyl(0.31, 0.05, cx, 0.16, cz), M::Beam)); // lower hoop
        v.push((cyl(0.31, 0.05, cx, 0.48, cz), M::Beam)); // upper hoop
    }
    v
}

/// A little roofed draw-well — stone curb, posts, windlass roller, a bucket on the rim.
fn well_parts() -> Vec<(Mesh, M)> {
    let mut v: Vec<(Mesh, M)> = Vec::new();
    v.push((cyl(0.55, 0.5, 0.0, 0.25, 0.0), M::HouseStone)); // curb
    v.push((cyl(0.42, 0.04, 0.0, 0.46, 0.0), M::Slit)); // dark water surface (recessed below the rim)
    for sx in [-0.5_f32, 0.5] {
        v.push((bx(0.1, 1.1, 0.1, sx, 0.55, 0.0), M::Beam)); // post
    }
    v.push((log_x(0.07, 1.0, 1.05, 0.0), M::Wood)); // windlass roller
    v.push((gable(1.4, 0.7, 0.35, 1.15), M::HouseRoof)); // little roof
    v.push((taper(0.13, 0.16, 0.26, 0.13).translated_by(Vec3::new(0.0, 0.0, 0.62)), M::Wood)); // bucket on the rim
    v
}

/// A low-poly courtyard hen (off-white body, gold beak, red comb). Parts share local origin; the
/// whole bird is parented under a moving root and bobbed/pecked by [`peck_hens`].
fn hen_parts() -> Vec<(Mesh, M)> {
    let mut v: Vec<(Mesh, M)> = Vec::new();
    v.push((flat(Sphere::new(0.12).mesh().ico(1).unwrap().scaled_by(Vec3::new(1.3, 0.95, 1.0)).translated_by(Vec3::new(0.0, 0.12, 0.0))), M::Hen)); // body
    v.push((flat(Sphere::new(0.07).mesh().ico(1).unwrap().translated_by(Vec3::new(0.13, 0.23, 0.0))), M::Hen)); // head
    v.push((Cone { radius: 0.03, height: 0.08 }.mesh().build().rotated_by(Quat::from_rotation_z(-HALF_PI)).translated_by(Vec3::new(0.22, 0.22, 0.0)), M::Gold)); // beak
    v.push((bx(0.03, 0.06, 0.05, 0.12, 0.3, 0.0), M::Roof)); // comb
    v.push((flat(bx(0.16, 0.12, 0.02, 0.0, 0.0, 0.0).rotated_by(Quat::from_rotation_z(0.5)).translated_by(Vec3::new(-0.13, 0.2, 0.0))), M::Hen)); // cocked tail
    v
}

// ── Layout: the enceinte, its kit tiers, the courtyard, the village ──────────────────

/// Number of enceinte sides (= corners).
pub(crate) const SIDES: usize = ENCEINTE.len();

/// Side `i` (`ENCEINTE[i]` → `ENCEINTE[i + 1]`): start corner, unit direction, length.
pub(crate) fn side(i: usize) -> (Vec2, Vec2, f32) {
    let a = ENCEINTE[i % SIDES];
    let b = ENCEINTE[(i + 1) % SIDES];
    let len = a.distance(b);
    (a, (b - a) / len, len)
}

/// Unit normal of side direction `d` pointing INTO the castle (clockwise winding, x east, z south).
pub(crate) fn inward(d: Vec2) -> Vec2 {
    Vec2::new(-d.y, d.x)
}

/// Yaw turning a piece's local +X along `d`: on a clockwise side its local −Z (a kit wall's field
/// face) then looks out of the castle and local +Z (a town piece's front) into the yard.
pub(crate) fn yaw_along(d: Vec2) -> f32 {
    (-d.y).atan2(d.x)
}

/// Yaw turning a piece's local −Z along `out` (a D / round tower's field face; its door, +Z, then
/// faces the yard).
fn yaw_facing_out(out: Vec2) -> f32 {
    (-out.y).atan2(out.x) - HALF_PI
}

/// Unit OUTWARD bisector at corner `v`.
pub(crate) fn corner_out(v: usize) -> Vec2 {
    let (_, d_in, _) = side((v + SIDES - 1) % SIDES);
    let (_, d_out, _) = side(v);
    (-(inward(d_in) + inward(d_out))).normalize()
}

/// Signed distance to the wall LINE, positive inside (the min over the sides' lines: exact inside
/// a convex polygon; outside only a lower bound — [`outside_dist`] is the true distance).
pub(crate) fn wall_inset(wx: f32, wz: f32) -> f32 {
    let p = Vec2::new(wx, wz);
    (0..SIDES)
        .map(|i| {
            let (a, d, _) = side(i);
            inward(d).dot(p - a)
        })
        .fold(f32::INFINITY, f32::min)
}

/// Euclidean distance from `(wx, wz)` out to the wall line (0 inside the enceinte).
pub(crate) fn outside_dist(wx: f32, wz: f32) -> f32 {
    if wall_inset(wx, wz) >= 0.0 {
        return 0.0;
    }
    let p = Vec2::new(wx, wz);
    (0..SIDES)
        .map(|i| {
            let (a, d, len) = side(i);
            p.distance(a + d * (p - a).dot(d).clamp(0.0, len))
        })
        .fold(f32::INFINITY, f32::min)
}

/// The corners whose towers carry the tower defenders (`defenses.rs`) and the Towers-upgrade
/// watchtowers of the palisade tier: NW, NE, SE, SW.
pub(crate) const DEFENDER_CORNERS: [usize; 4] = [0, 3, 5, 7];

/// World XZ of the four defender towers.
pub(crate) fn defender_towers() -> [Vec2; 4] {
    DEFENDER_CORNERS.map(|v| ENCEINTE[v])
}

/// A point `d` inside corner `v`, along its bisector.
pub(crate) fn corner_inside(v: usize, d: f32) -> Vec2 {
    ENCEINTE[v] - corner_out(v) * d
}

/// The vertex tower of the stone (curtain) tier on each corner — round, D and square hoarded
/// towers mixed so the circuit doesn't read as one stamped tower.
const CORNER_TOWERS: [&str; SIDES] = [
    "ck_d_tower",      // 0 NW
    "ck_round_tower",  // 1
    "ck_d_tower",      // 2
    "ck_corner_tower", // 3 NE
    "ck_round_tower",  // 4 E
    "ck_d_tower",      // 5 SE
    "ck_round_tower",  // 6
    "ck_corner_tower", // 7 SW, by the main gate
    "ck_d_tower",      // 8
];

/// Yaw for a corner piece on corner `v`: the D / round towers turn their field face along the
/// outward bisector; the square corner tower (outer faces local −Z/−X) its outer diagonal.
fn corner_yaw(name: &str, v: usize) -> f32 {
    let out = corner_out(v);
    if name == "ck_corner_tower" {
        (-out.y).atan2(out.x) - 3.0 * std::f32::consts::FRAC_PI_4
    } else {
        yaw_facing_out(out)
    }
}

/// The open COURTYARD (spec v2 §2: ≥24×16u, nothing built in it but the fire pit + well at its
/// north edge) as `(cx, cz, half_x, half_z)`: from below the keep's door to the S lean-tos.
pub(crate) const COURTYARD: (f32, f32, f32, f32) = (0.0, 5.0, 12.5, 9.0);

/// The worn route network `(cx, cz, w, d)`: [0] the courtyard, the three gate paths, and the
/// market square outside the W gate. Baked into the terrain colour as packed earth (`yard_strength`)
/// and used to keep grass sprigs off the routes.
const PATH_RECTS: [(f32, f32, f32, f32); 5] = [
    (COURTYARD.0, COURTYARD.1, COURTYARD.2 * 2.0 - 4.0, COURTYARD.3 * 2.0 - 2.0), // courtyard
    (N_GATE_X, -14.0, 3.2, 20.0),                                                // north postern → yard
    (S_GATE_X, 19.5, 3.6, 9.0),                                                  // south gate → yard
    (-20.25, W_GATE_Z, 17.5, 3.6),                                               // west gate → yard
    (MARKET_CENTRE.x, MARKET_CENTRE.y, 12.0, 9.0),                               // the market square
];

/// Cobble paving raised with the walls `(cx, cz, w, d)`: [0] the keep apron, then the three gate
/// passages (through the gap, a stride either side). Everything else stays earth.
const PAVED_RECTS: [(f32, f32, f32, f32); 4] = [
    (KEEP_POS.x, KEEP_FRONT + 1.4, KEEP_HALF.x * 2.0 + 1.0, 3.2),
    (N_GATE_X, -HALF_Z, 3.4, 5.0),
    (S_GATE_X, HALF_Z, 3.8, 5.0),
    (-HALF_X, W_GATE_Z, 5.0, 3.8),
];

/// How strongly world point `(wx, wz)` sits on the trodden castle yard (the plaza + the gate paths
/// + the market square of [`PATH_RECTS`]): 1 across a rect's core, fading to 0 over ~`EDGE` beyond
/// its rim, with a little sine wobble so the outline isn't a crisp rectangle. `worldmap::ground_color`
/// bakes this into the terrain vertex colour, so the packed-earth yard is the ground itself.
pub fn yard_strength(wx: f32, wz: f32) -> f32 {
    const EDGE: f32 = 1.7; // world-unit falloff band outside each rect
    let wob = 0.55 * (wx * 0.7 + 1.3).sin() * (wz * 0.5 - 0.4).cos()
        + 0.35 * (wx * 0.23 - wz * 0.19 + 2.1).sin();
    let mut best = 0.0_f32;
    for (cx, cz, w, d) in PATH_RECTS {
        // Distance inside the rect (positive inside, negative outside) to the nearest edge.
        let din = (w / 2.0 - (wx - cx).abs()).min(d / 2.0 - (wz - cz).abs());
        let s = ((din + wob + EDGE) / EDGE).clamp(0.0, 1.0);
        best = best.max(s * s);
    }
    best
}

/// Is `(wx, wz)` on (or hard against) the plaza/path paving? Used to keep grass off the routes.
fn on_paving(wx: f32, wz: f32) -> bool {
    PATH_RECTS
        .iter()
        .any(|(cx, cz, w, d)| (wx - cx).abs() < w / 2.0 + 0.5 && (wz - cz).abs() < d / 2.0 + 0.5)
}

/// The three gates (spec v2 §5). The east side has none.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Gate {
    /// Main gate — the King's Road west through the village to the bay (later a portcullis).
    West,
    /// The attacked gate, beside the bell tower — the orcs come from the south (later a barbican).
    South,
    /// The north postern — forest and quarry.
    North,
}

impl Gate {
    pub const ALL: [Gate; 3] = [Gate::West, Gate::South, Gate::North];
    /// Gate-gap centre on the wall line (world XZ).
    pub fn center(self) -> Vec2 {
        match self {
            Gate::West => Vec2::new(-HALF_X, W_GATE_Z),
            Gate::South => Vec2::new(S_GATE_X, HALF_Z),
            Gate::North => Vec2::new(N_GATE_X, -HALF_Z),
        }
    }
    /// Unit vector pointing OUT of the castle through this gate.
    pub fn outward(self) -> Vec2 {
        match self {
            Gate::West => Vec2::NEG_X,
            Gate::South => Vec2::Y,
            Gate::North => Vec2::NEG_Y,
        }
    }
    /// A point `d` units INSIDE the gate gap, on its axis (the courtyard side).
    pub fn interior(self, d: f32) -> Vec2 {
        self.center() - self.outward() * d
    }
    /// The enceinte side this gate is cut into.
    pub(crate) fn side(self) -> usize {
        match self {
            Gate::West => W_SIDE,
            Gate::South => S_SIDE,
            Gate::North => N_SIDE,
        }
    }
    /// Distance of the gate centre along its side from the side's start corner.
    fn u(self) -> f32 {
        let (a, d, _) = side(self.side());
        (self.center() - a).dot(d)
    }
}

/// Where along side `i` something other than a run module stands on the wall line: `(u0, u1,
/// soft)` intervals (a gate piece, the bell tower). `soft` = a run may tuck up to 1u into it.
fn line_stops(i: usize, gate_half: f32, gate_soft: bool) -> Vec<(f32, f32, bool)> {
    let mut v = Vec::new();
    for g in Gate::ALL {
        if g.side() == i {
            v.push((g.u() - gate_half, g.u() + gate_half, gate_soft));
        }
    }
    if i == S_SIDE {
        let (a, d, _) = side(i);
        let u = (BELL_POS - a).dot(d);
        v.push((u - BELL_TOWER_HALF, u + BELL_TOWER_HALF, true));
    }
    v.sort_by(|a, b| a.0.total_cmp(&b.0));
    v
}

/// One kit piece of the castle, placed.
#[derive(Clone, Copy, Debug)]
pub(crate) struct KitPlace {
    pub(crate) name: &'static str,
    pub(crate) pos: Vec2,
    pub(crate) yaw: f32,
    pub(crate) kind: CastleKind,
    edit: crate::castle_kit::Edit,
}

/// Fill `[u0, u1]` of side `i` with whole 4u / 2u / 1u wall modules (`names` = 4u, 2u, 1u). The run
/// rounds UP to a whole length and the surplus (<1u) tucks under its soft end(s) — a tower, a
/// gatehouse, the bell tower — so the modules never stretch.
fn fill_run(out: &mut Vec<KitPlace>, i: usize, u0: f32, u1: f32, soft: (bool, bool), names: [&'static str; 3], kind: CastleKind) {
    let len = u1 - u0;
    if len < 0.25 {
        return;
    }
    let n = (len - 0.05).ceil().max(1.0);
    let extra = n - len;
    let start = match soft {
        (true, false) => u0 - extra,
        (false, true) => u0,
        _ => u0 - extra / 2.0,
    };
    let n = n as i32;
    let (fours, rest) = (n / 4, n % 4);
    // Fillers in the middle of the run, the 4u modules either side.
    let mut seq: Vec<(f32, &'static str)> = Vec::new();
    for _ in 0..fours / 2 {
        seq.push((4.0, names[0]));
    }
    if rest >= 2 {
        seq.push((2.0, names[1]));
    }
    if rest % 2 == 1 {
        seq.push((1.0, names[2]));
    }
    for _ in fours / 2..fours {
        seq.push((4.0, names[0]));
    }
    let (a, d, _) = side(i);
    let yaw = yaw_along(d);
    let mut u = start;
    for (l, name) in seq {
        out.push(KitPlace { name, pos: a + d * (u + l / 2.0), yaw, kind, edit: crate::castle_kit::Edit::None });
        u += l;
    }
}

/// Every kit piece of the castle, tier by tier (see [`CastleKind`] for which upgrade shows what):
/// the old colony's ruins, the palisade + timber gates + corner posts (watchtowers / stone towers
/// with the Towers track), the stone curtain + corner towers + gatehouses, the three keep tiers and
/// the bell tower.
pub(crate) fn kit_layout() -> Vec<KitPlace> {
    use crate::castle_kit::{Edit, ATTACH_STONE, ATTACH_TIMBER};
    let mut v = Vec::new();
    let place = |name, pos, yaw, kind, edit| KitPlace { name, pos, yaw, kind, edit };
    for i in 0..SIDES {
        let len = side(i).2;
        // Palisade tier: runs 0.9u out of each corner post, cut for the timber gates.
        let mut u = ATTACH_TIMBER;
        for (s0, s1, soft) in line_stops(i, 2.0, false) {
            fill_run(&mut v, i, u, s0, (true, soft), ["ck_palisade", "ck_palisade_2", "ck_palisade_1"], CastleKind::Palisade);
            u = s1;
        }
        let last_soft = line_stops(i, 2.0, false).last().is_none_or(|s| s.2);
        fill_run(&mut v, i, u, len - ATTACH_TIMBER, (last_soft, true), ["ck_palisade", "ck_palisade_2", "ck_palisade_1"], CastleKind::Palisade);
        // Curtain tier: runs 2u out of each tower, cut for the gatehouses (6.4u on the line).
        let mut u = ATTACH_STONE;
        for (s0, s1, soft) in line_stops(i, 3.2, true) {
            fill_run(&mut v, i, u, s0, (true, soft), ["ck_curtain", "ck_curtain_2", "ck_curtain_1"], CastleKind::Curtain);
            u = s1;
        }
        fill_run(&mut v, i, u, len - ATTACH_STONE, (true, true), ["ck_curtain", "ck_curtain_2", "ck_curtain_1"], CastleKind::Curtain);
    }
    for g in Gate::ALL {
        let (_, d, _) = side(g.side());
        v.push(place("ck_timber_gate", g.center(), yaw_along(d), CastleKind::Palisade, Edit::NoLeaves));
        v.push(place("ck_gatehouse", g.center(), yaw_along(d), CastleKind::Curtain, Edit::OpenGatehouse));
    }
    for (c, &p) in ENCEINTE.iter().enumerate() {
        let yaw = yaw_facing_out(corner_out(c));
        let defender = DEFENDER_CORNERS.contains(&c);
        let post = if defender { CastleKind::PalisadeCorner } else { CastleKind::Palisade };
        v.push(place("ck_palisade_post", p, yaw, post, Edit::None));
        if defender {
            v.push(place("ck_watchtower", p, yaw, CastleKind::WatchTower, Edit::None));
            v.push(place("ck_stone_tower", p, yaw, CastleKind::StoneTower, Edit::None));
        }
        let tower = CORNER_TOWERS[c];
        v.push(place(tower, p, corner_yaw(tower, c), CastleKind::Curtain, Edit::None));
    }
    // The old colony's broken circuit (no walls yet): fragments on the old line, rubble between.
    for (i, t, name) in RUINS {
        let (a, d, len) = side(i);
        v.push(place(name, a + d * (len * t), yaw_along(d), CastleKind::PreWalls, Edit::None));
    }
    let keep = KEEP_POS;
    v.push(place("ck_ruin_keep", keep, 0.0, CastleKind::KeepTier0, Edit::None));
    v.push(place("ck_keep_t1", keep, 0.0, CastleKind::KeepTier1, Edit::None));
    v.push(place("ck_keep_t2", keep, 0.0, CastleKind::KeepTier2, Edit::None));
    let (_, d, _) = side(S_SIDE);
    v.push(place("ck_bell_tower", BELL_POS, yaw_along(d), CastleKind::Always, Edit::NoBell));
    v
}

/// The ruins of the old colony's circuit `(side, t along it, piece)` — shown until the walls rise.
const RUINS: [(usize, f32, &str); 10] = [
    (0, 0.5, "ck_ruin_wall_a"),
    (1, 0.25, "ck_ruin_wall_b"),
    (2, 0.5, "ck_ruin_wall_a"),
    (3, 0.3, "ck_rubble"),
    (3, 0.7, "ck_ruin_wall_b"),
    (4, 0.45, "ck_ruin_wall_a"),
    (5, 0.3, "ck_ruin_wall_b"),
    (6, 0.5, "ck_ruin_wall_a"),
    (7, 0.25, "ck_rubble"),
    (8, 0.5, "ck_ruin_wall_b"),
];

/// Wall collision runs `(a, b)` along the wall line: every side corner to corner (a little past
/// each corner so the joints are sealed), split only at the gate OPENINGS (the gate pieces' posts
/// are solid). The bell tower stands in the line too (its own permanent box on top).
fn wall_segments() -> Vec<(Vec2, Vec2)> {
    let mut v = Vec::new();
    for i in 0..SIDES {
        let (a, d, len) = side(i);
        let mut u = -0.35;
        let stops: Vec<(f32, f32)> = Gate::ALL
            .iter()
            .filter(|g| g.side() == i)
            .map(|g| (g.u() - GATE_GAP / 2.0 - 0.02, g.u() + GATE_GAP / 2.0 + 0.02))
            .collect();
        for (s0, s1) in stops {
            v.push((a + d * u, a + d * s0));
            u = s1;
        }
        v.push((a + d * u, a + d * (len + 0.35)));
    }
    v
}

/// A reserved plot: a town-kit building (or a primitive fixture) with its collision footprint.
/// `half` is in the piece's own frame (x along its front, z depth); `yaw` turns it into the world.
#[derive(Clone, Copy, Debug)]
pub(crate) struct TownPlot {
    pub(crate) name: &'static str,
    pub(crate) pos: Vec2,
    pub(crate) half: Vec2,
    pub(crate) yaw: f32,
    /// The town-kit piece standing here (`None` = a primitive fixture, see `build`).
    piece: Option<&'static str>,
    /// Collision box `(centre offset along local x, half)` when it differs from the footprint
    /// (the infirmary's herb garden is walk-through); `None` = no collision at all.
    solid: Option<(f32, Vec2)>,
}

/// A lean-to / building backed onto the curtain of side `i`, `u` along it: its back sits on the
/// wall's inner face (+0.9 off the line, `gap` more for a free-standing one), its front to the yard.
fn against_wall(name: &'static str, piece: &'static str, i: usize, u: f32, half: Vec2, gap: f32) -> TownPlot {
    let (a, d, _) = side(i);
    let pos = a + d * u + inward(d) * (0.9 + gap + half.y);
    TownPlot { name, pos, half, yaw: yaw_along(d), piece: Some(piece), solid: Some((0.0, half)) }
}

/// The plots inside the walls (spec v2 §2, layout v3): the castle's own buildings as lean-tos
/// against the curtain — barracks, stable, store, cart shed — the smithy, granary and infirmary
/// (+ its herb garden) on the wall too, and the fire pit + well at the courtyard's north edge.
/// Nothing in rows: the middle stays open.
pub(crate) fn town_plots() -> &'static [TownPlot] {
    static PLOTS: std::sync::LazyLock<Vec<TownPlot>> = std::sync::LazyLock::new(|| {
        let mut infirmary = against_wall("infirmary", "town_infirmary", 3, 8.5, Vec2::new(3.6, 1.8), 0.0);
        infirmary.solid = Some((0.0, Vec2::new(3.6, 1.8))); // the garden (local x 3.9..7.0) stays open
        vec![
            against_wall("barracks", "castle_barracks", 2, 9.0, Vec2::new(3.8, 1.8), 0.0),
            infirmary,
            against_wall("granary", "town_granary", 4, 6.0, Vec2::new(1.6, 2.1), 1.2),
            against_wall("cart_shed", "castle_cartshed", 4, 13.5, Vec2::new(3.2, 1.9), 0.0),
            against_wall("stable", "castle_stable", 5, 8.0, Vec2::new(3.6, 1.7), 0.0),
            against_wall("smithy", "town_smithy", 6, 6.0, Vec2::new(2.3, 1.7), 0.5),
            against_wall("store", "castle_store", 7, 6.3, Vec2::new(2.8, 1.6), 0.0),
            TownPlot {
                name: "fire_pit",
                pos: Vec2::new(-7.5, -6.6),
                half: Vec2::splat(1.6),
                yaw: 0.0,
                piece: Some("town_firepit"),
                solid: Some((0.0, Vec2::splat(0.7))),
            },
            TownPlot { name: "well", pos: Vec2::new(9.6, -6.4), half: Vec2::splat(0.6), yaw: 0.0, piece: None, solid: Some((0.0, Vec2::splat(0.55))) },
        ]
    });
    &PLOTS
}

/// OUTSIDE the west gate (layout v3): the market square's tavern and Maud's house (edict board),
/// and by the King's Road beyond the village the Crown depot at the fork, the Crown gallows on a
/// low rise and — further west — the empty grave of the drowned squire.
pub(crate) fn outer_plots() -> &'static [TownPlot] {
    static PLOTS: std::sync::LazyLock<Vec<TownPlot>> = std::sync::LazyLock::new(|| {
        let p = |name, piece, pos: Vec2, half: Vec2, yaw: f32| TownPlot { name, pos, half, yaw, piece: Some(piece), solid: Some((0.0, half)) };
        let (end, dir) = polyline_at(&STREET, f32::INFINITY);
        let north = Vec2::new(-dir.y, dir.x);
        let face = |p: Vec2, target: Vec2| {
            let f = (target - p).normalize();
            f.x.atan2(f.y)
        };
        let depot = end + north * 6.5 - dir * 1.0;
        let gallows = end + dir * 9.0 - north * 6.5;
        let grave = end + dir * 19.0 + north * 5.0;
        let road_at = |q: Vec2| q - north * (q - end).dot(north);
        let mut v = vec![
            p("tavern", "town_tavern", Vec2::new(-40.5, -8.0), Vec2::new(3.2, 2.3), 0.0),
            p("maud_house", "town_maud_house", Vec2::new(-38.5, 8.5), Vec2::new(2.6, 1.9), std::f32::consts::PI),
            p("crown_depot", "crown_depot", depot, Vec2::new(1.6, 1.2), face(depot, road_at(depot))),
            p("gallows", "crown_gallows", gallows, Vec2::new(1.1, 0.8), face(gallows, road_at(gallows))),
        ];
        v.push(TownPlot { name: "empty_grave", pos: grave, half: Vec2::new(0.7, 1.3), yaw: face(grave, road_at(grave)), piece: Some("town_grave"), solid: None });
        v
    });
    &PLOTS
}

/// A reserved plot by name (inside or outside the walls).
pub(crate) fn town_plot(name: &str) -> Option<TownPlot> {
    town_plots().iter().chain(outer_plots().iter()).find(|p| p.name == name).copied()
}

/// Centre of the market square OUTSIDE the west gate (layout v3: the market moved out of the walls,
/// onto the King's Road where the village meets the gate).
pub(crate) const MARKET_CENTRE: Vec2 = Vec2::new(-38.5, 0.6);

/// The King's Road through the village: from the W gate west to the fork (world XZ control points;
/// `roads.rs` lays the road through them and the houses line it).
pub(crate) const STREET: [Vec2; 6] = [
    Vec2::new(-28.0, 0.0),
    Vec2::new(-44.0, 1.2),
    Vec2::new(-54.0, 3.2),
    Vec2::new(-64.0, 7.0),
    Vec2::new(-73.0, 12.5),
    Vec2::new(-80.0, 17.5),
];
/// The village's one side lane, south off the King's Road.
pub(crate) const LANE: [Vec2; 5] = [Vec2::new(-52.5, 3.1), Vec2::new(-52.0, 16.0), Vec2::new(-52.5, 28.0), Vec2::new(-54.0, 37.0), Vec2::new(-56.0, 45.0)];

/// Point + unit direction at arc length `s` along a polyline (clamped past its end).
pub(crate) fn polyline_at(pl: &[Vec2], s: f32) -> (Vec2, Vec2) {
    let mut s = s.max(0.0);
    for w in pl.windows(2) {
        let l = w[0].distance(w[1]);
        let d = (w[1] - w[0]) / l;
        if s <= l {
            return (w[0] + d * s, d);
        }
        s -= l;
    }
    let n = pl.len();
    ((pl[n - 1]), (pl[n - 1] - pl[n - 2]).normalize())
}

/// Distance from `p` to a polyline.
fn polyline_dist(pl: &[Vec2], p: Vec2) -> f32 {
    pl.windows(2)
        .map(|w| {
            let (a, b) = (w[0], w[1]);
            let d = b - a;
            let t = ((p - a).dot(d) / d.length_squared()).clamp(0.0, 1.0);
            p.distance(a + d * t)
        })
        .fold(f32::INFINITY, f32::min)
}

/// Distance from `(wx, wz)` to the village's streets (the King's Road through it + the side lane):
/// `worldmap` flattens a lobe of open ground along them (`castle_ring_dist`).
pub(crate) fn village_dist(wx: f32, wz: f32) -> f32 {
    let p = Vec2::new(wx, wz);
    polyline_dist(&STREET, p).min(polyline_dist(&LANE, p))
}

/// One dwelling of the street village outside the W gate (layout v3): a burgage plot with the
/// gable + door to the road, the yard / garden / shed / fence behind.
#[derive(Clone, Copy, Debug)]
pub(crate) struct HouseSite {
    pub(crate) pos: Vec2,
    pub(crate) yaw: f32,
    pub(crate) piece: &'static str,
    /// Footprint half-extents in the house's frame (x across its front, z depth).
    pub(crate) half: Vec2,
    /// Variant index for the yard dressing.
    dress: u8,
}

/// Depth of a burgage yard behind the house (garden, shed, back fence).
const YARD: f32 = 5.0;

impl HouseSite {
    /// The whole burgage plot `(centre, half, yaw)`: the house + its yard behind, a stride either side.
    pub(crate) fn plot(&self) -> (Vec2, Vec2, f32) {
        let half = Vec2::new(self.half.x.max(2.4) + 0.7, self.half.y + YARD / 2.0);
        let back = Quat::from_rotation_y(self.yaw) * Vec3::new(0.0, 0.0, -YARD / 2.0);
        (self.pos + Vec2::new(back.x, back.z), half, self.yaw)
    }
    /// World XZ of a point in the house's frame.
    fn local(&self, x: f32, z: f32) -> Vec2 {
        let w = Quat::from_rotation_y(self.yaw) * Vec3::new(x, 0.0, z);
        self.pos + Vec2::new(w.x, w.z)
    }
}

/// The twelve house sites, nearest the W gate first (the order `town.houses` reveals them): eight
/// along the King's Road — alternating sides, uneven gaps, the building line following the road,
/// a little yaw jitter — and four cottages on the side lane.
pub(crate) fn houses() -> &'static [HouseSite] {
    static SITES: std::sync::LazyLock<Vec<HouseSite>> = std::sync::LazyLock::new(|| {
        // (arc length along the street, side: +1 north / −1 south, piece, front-yard depth, yaw jitter)
        const MAIN: [(f32, f32, &str, f32, f32); 8] = [
            (19.0, -1.0, "town_street_house_b", 0.6, 0.03),
            (19.5, 1.0, "town_street_house_a", 0.9, -0.05),
            (26.5, 1.0, "town_street_house_b", 0.5, 0.04),
            (33.5, 1.0, "town_street_house_a", 1.1, -0.02),
            (42.5, -1.0, "town_street_house_a", 0.8, 0.06),
            (41.0, 1.0, "town_street_house_a", 0.6, 0.02),
            (49.5, -1.0, "town_street_house_b", 1.0, -0.04),
            (48.0, 1.0, "town_street_house_b", 0.7, 0.05),
        ];
        const LANE_HOUSES: [(f32, f32, &str, f32, f32); 4] = [
            (17.5, -1.0, "town_house_a", 0.7, -0.04),
            (25.0, -1.0, "town_house_d", 0.9, 0.05),
            (32.5, -1.0, "town_house_c", 1.0, 0.03),
            (33.0, 1.0, "town_house_b", 0.6, -0.06),
        ];
        let half_of = |piece: &str| match piece {
            "town_street_house_a" => Vec2::new(2.2, 3.8),
            "town_street_house_b" => Vec2::new(2.4, 3.5),
            "town_house_a" => Vec2::new(2.3, 1.7),
            "town_house_b" => Vec2::new(2.8, 1.8),
            "town_house_c" => Vec2::new(1.9, 1.6),
            _ => Vec2::new(2.4, 1.8), // town_house_d
        };
        // Path distance from the gate to the lane's mouth.
        let lane_s0 = {
            let mut best = (f32::INFINITY, 0.0);
            let mut s = 0.0;
            while s < 60.0 {
                let d = polyline_at(&STREET, s).0.distance(LANE[0]);
                if d < best.0 {
                    best = (d, s);
                }
                s += 0.25;
            }
            best.1
        };
        let mut v: Vec<(f32, HouseSite)> = Vec::new();
        for (pl, list, base, road_half) in [(&STREET[..], &MAIN[..], 0.0, 2.2), (&LANE[..], &LANE_HOUSES[..], lane_s0, 1.6)] {
            for (k, &(s, side, piece, front, jitter)) in list.iter().enumerate() {
                let (p, dir) = polyline_at(pl, s);
                let left = Vec2::new(-dir.y, dir.x); // north of the westward street, east of the southward lane
                let half = half_of(piece);
                let pos = p + left * side * (road_half + front + half.y);
                let f = -left * side; // the front looks back at the road
                let yaw = f.x.atan2(f.y) + jitter;
                v.push((base + s, HouseSite { pos, yaw, piece, half, dress: (k as u8 * 3 + (base > 0.0) as u8) % 4 }));
            }
        }
        v.sort_by(|a, b| a.0.total_cmp(&b.0));
        v.into_iter().map(|(_, h)| h).collect()
    });
    &SITES
}

/// The work-yard props `(x, z, yaw)`: the wood yard behind the keep, hay by the W wall, the
/// hand-cart before the stable.
pub(crate) const WOOD_YARD: (f32, f32, f32) = (-15.0, -18.6, 0.6);
pub(crate) const HAY_CORNER: (f32, f32, f32) = (-23.0, -11.0, 0.9);
pub(crate) const CART_CORNER: (f32, f32, f32) = (12.0, 17.0, 2.3);

/// World-XZ of the dwelling slot the NEXT house will occupy (`houses()[built]`), or `None`
/// once all twelve stand. The on-site "Raise house" interaction + its pad anchor here, so a
/// new home always rises exactly where the player chose to build it (`sync_castle` reveals
/// the mesh at this same slot when `town.houses` increments).
pub(crate) fn next_house_site(built: u32) -> Option<Vec2> {
    houses().get(built as usize).map(|h| h.pos)
}

/// True inside the castle footprint (+ the towers' and gatehouse turrets' reach) — scatter is
/// cleared here.
pub fn in_footprint(wx: f32, wz: f32) -> bool {
    wall_inset(wx, wz) > -4.0
}

/// Bounding half-extents of the enceinte round the origin — sample inside it, then keep the
/// points [`in_courtyard`] accepts (the outline is an irregular polygon).
pub fn courtyard_half() -> (f32, f32) {
    (31.0, 24.0)
}

/// True strictly INSIDE the wall ring (wall thickness excluded). Siege rule: an invader only
/// batters the keep from in here — outside, the walls shield it, so the wall ring is a real
/// obstacle (thread a gate or do nothing), never a spot to chip the keep from.
pub fn in_courtyard(wx: f32, wz: f32) -> bool {
    wall_inset(wx, wz) > WALL_THICK
}

/// Ground cover (grass, ferns, flowers) and kit scatter stay off the village's working ground:
/// the market square, every burgage plot, the Crown plots and the grave by the road.
pub(crate) fn village_keep_clear(wx: f32, wz: f32, r: f32) -> bool {
    let p = Vec2::new(wx, wz);
    if p.distance(MARKET_CENTRE) < 8.0 + r {
        return true;
    }
    let in_obb = |c: Vec2, half: Vec2, yaw: f32, m: f32| {
        let l = Quat::from_rotation_y(-yaw) * Vec3::new(p.x - c.x, 0.0, p.y - c.y);
        l.x.abs() < half.x + m && l.z.abs() < half.y + m
    };
    houses().iter().any(|h| {
        let (c, half, yaw) = h.plot();
        in_obb(c, half, yaw, r + 0.6)
    }) || outer_plots().iter().any(|tp| in_obb(tp.pos, tp.half, tp.yaw, r + 1.5))
        || town_plots().iter().any(|tp| matches!(tp.name, "fire_pit") && in_obb(tp.pos, tp.half, tp.yaw, r + 0.5))
}

/// The healing shrine (castle_decor, Bulwark upgrade) by the infirmary on the east side — and the
/// centre of its heal aura (`defenses::shrine_heal`).
pub(crate) const SHRINE_POS: Vec2 = Vec2::new(20.0, -3.0);

/// World Y of the keep's fighting top (`ck_keep_t2`'s parapet walk) — where the keep-roof archers
/// stand.
pub(crate) const KEEP_ROOF_Y: f32 = 8.6;
/// World Y of a tower's fighting top (the D / mural towers' walk 5.4) — the tower defenders'
/// muzzle height.
pub(crate) const TOWER_TOP: f32 = 5.4;

/// The keep steps — the gather spot / muster mark just in front of the keep door.
pub(crate) const KEEP_STEPS: Vec2 = Vec2::new(KEEP_POS.x, KEEP_FRONT + 1.6);

/// The wandering merchant's roofed shop (`villagers::shop_parts`), on the market square's north
/// side by the W gate, its open front facing south onto the square; `interaction::shop_anchor`
/// browses here.
pub(crate) const MERCHANT_SHOP: Vec2 = Vec2::new(-34.4, -5.2);

/// Where the hero stands to ring the bell: inside the yard at the foot of the bell tower's ladder.
pub(crate) const BELL_ROPE: Vec2 = Vec2::new(BELL_POS.x, BELL_POS.y - BELL_TOWER_YARD - 0.8);

/// True in the OPEN yard in front of the keep (the courtyard plus a ring round the keep itself)
/// — where nothing stands between an invader and the keep, so it may press it in a straight line.
pub fn in_keep_yard(wx: f32, wz: f32) -> bool {
    let (cx, cz, hx, hz) = COURTYARD;
    ((wx - cx).abs() <= hx && (wz - cz).abs() <= hz + 0.6) || Vec2::new(wx, wz).distance(KEEP_POS) < 8.0
}

// ── Build ────────────────────────────────────────────────────────────────────────
/// Is a part of this kind shown on a fresh, wall-less start (before `sync_castle`'s first pass)?
fn shown_at_start(kind: CastleKind) -> bool {
    matches!(kind, CastleKind::Always | CastleKind::PreWalls | CastleKind::KeepTier0)
}

/// Spawn one kit piece (castle kit or town kit) as a castle part: tagged with the upgrade that
/// reveals it, solid to the follow camera's boom when `occluder`.
fn spawn_kit(
    commands: &mut Commands,
    meshes: &mut Assets<Mesh>,
    name: &str,
    pos: Vec2,
    yaw: f32,
    kind: CastleKind,
    edit: crate::castle_kit::Edit,
    occluder: bool,
) {
    let y = if in_footprint(pos.x, pos.y) { 0.0 } else { crate::worldmap::ground_at_world(pos.x, pos.y).unwrap_or(0.0) };
    let tf = Transform::from_xyz(pos.x, y, pos.y).with_rotation(Quat::from_rotation_y(yaw));
    let tags = (CastlePart { kind }, crate::build_fx::RevealAt(Vec3::new(pos.x, y, pos.y)), BiomeEntity);
    let e = if name.starts_with("ck_") {
        crate::castle_kit::spawn_piece_edited(commands, meshes, name, tf, edit, tags)
    } else {
        crate::town_kit::spawn_piece(commands, name, tf).inspect(|&e| {
            commands.entity(e).insert(tags);
        })
    };
    let Some(e) = e else { return };
    let vis = if shown_at_start(kind) { Visibility::Inherited } else { Visibility::Hidden };
    let mut ec = commands.entity(e);
    ec.insert(vis);
    if occluder {
        ec.insert(crate::player::CameraOccluder);
    }
}

/// The burgage yard behind house `i`: fences, garden, shed / woodpile / coop / hayrick (local
/// frame: the house's front +Z to the road, the yard toward −Z).
fn house_yard(h: &HouseSite) -> Vec<(&'static str, f32, f32, f32)> {
    let back = -h.half.y;
    let w = h.half.x.max(2.4) + 0.6; // the side fence line
    let (fence, gate) = if h.dress % 2 == 0 {
        ("town_fence_wattle", "town_fence_wattle_gate")
    } else {
        ("town_fence_picket", "town_fence_picket_gate")
    };
    let flip = if h.dress < 2 { 1.0 } else { -1.0 };
    let mut v = vec![
        // back fence (two modules, one with a gate) and one side fence
        (fence, -1.5 * flip, back - YARD, 0.0),
        (gate, 1.5 * flip, back - YARD, 0.0),
        (fence, w * flip, back - 1.4, HALF_PI),
        (fence, w * flip, back - YARD + 1.5, HALF_PI),
        ("town_garden", -1.1 * flip, back - 1.9, 0.0),
    ];
    match h.dress {
        0 => v.push(("town_shed", 1.6 * flip, back - YARD + 1.3, 0.0)),
        1 => {
            v.push(("town_woodpile", 1.5 * flip, back - 0.8, 0.0));
            v.push(("town_coop", 1.6 * flip, back - YARD + 1.4, 0.0));
        }
        2 => v.push(("town_shed", 1.6 * flip, back - YARD + 1.3, 0.0)),
        _ => v.push(("town_hayrick", 1.6 * flip, back - YARD + 1.6, 0.0)),
    }
    v
}

pub fn build(
    commands: &mut Commands,
    meshes: &mut Assets<Mesh>,
    images: &mut Assets<Image>,
    std_mats: &mut Assets<StandardMaterial>,
) -> Mats {
    let mats = build_mats(images, std_mats);
    // Share the textured material set with the town (producer buildings + plots render textured).
    // Returned to the caller too, so plot seeding in the same build pass (before this deferred
    // `insert_resource` lands) can use it directly.
    commands.insert_resource(VillageMats(mats.clone()));
    // Primitive parts (paving, braziers, yard clutter, the well) are baked in world space and
    // tagged with the upgrade that reveals them (`CastleKind`); gated parts start hidden so the
    // castle BUILDS UP as you buy.
    let mut spawn = |parts: Vec<(Mesh, M)>, pos: Vec3, rot: f32, scale: Vec3, kind: CastleKind| {
        let vis = if shown_at_start(kind) { Visibility::Inherited } else { Visibility::Hidden };
        for (m, slot) in parts {
            let mesh = meshes.add(bake(m, pos, rot, scale));
            commands.spawn((
                Mesh3d(mesh),
                MeshMaterial3d(mats.get(slot)),
                Transform::default(),
                vis,
                CastlePart { kind },
                // Authored position — `sync_castle` aims the construction dust burst with it
                // (the mesh is baked in world space, the Transform stays identity).
                crate::build_fx::RevealAt(pos),
                BiomeEntity,
            ));
        }
    };

    // Ground: a worn route network (the yard + the gate paths + the market square) baked into the
    // terrain colour as packed earth (`yard_strength`); raising the walls lays cobble only where
    // traffic is heaviest — the keep apron + the three gate passages.
    for (i, (px, pz, w, d)) in PAVED_RECTS.into_iter().enumerate() {
        let y = if i == 0 { 0.02 } else { 0.035 };
        spawn(
            vec![(with_tangents(worn_slab(w, d, y + 0.005, 0.7, 0.12, 0.04)), M::Cobble)],
            Vec3::new(px, 0.0, pz),
            0.0,
            Vec3::ONE,
            CastleKind::Walls,
        );
    }
    // War-braziers lighting the kill-zone outside each gate (with the Gate upgrade).
    for gate in Gate::ALL {
        for p in brazier_spots(gate) {
            spawn(brazier_parts(), p, 0.0, Vec3::ONE, CastleKind::Gate);
        }
    }
    // The settlement's working corners: woodpile, hay store, cart. Permanent (`Always`) — the
    // courtyard never goes blank, walls or no walls. Off the open courtyard (spec v2 §2).
    for (parts, (x, z, yaw)) in [
        (wood_yard_parts(), WOOD_YARD),
        (hay_corner_parts(), HAY_CORNER),
        (cart_corner_parts(), CART_CORNER),
    ] {
        spawn(parts, Vec3::new(x, 0.0, z), yaw, Vec3::ONE, CastleKind::Always);
    }
    if let Some(well) = town_plot("well") {
        spawn(well_parts(), Vec3::new(well.pos.x, 0.0, well.pos.y), well.yaw, Vec3::ONE, CastleKind::Always);
    }

    // The fortifications: every castle-kit piece of every tier (ruins → palisade → stone curtain,
    // the three keep tiers, the bell tower), shown by `sync_castle` as the Defenses upgrades land.
    for p in kit_layout() {
        let occluder = !matches!(p.name, "ck_rubble" | "ck_palisade_post");
        spawn_kit(commands, meshes, p.name, p.pos, p.yaw, p.kind, p.edit, occluder);
    }
    // The town-kit plots inside (lean-tos, smithy, granary, infirmary, fire pit) and outside the W
    // gate (tavern, Maud's house, the Crown's depot + gallows, the empty grave).
    for tp in town_plots().iter().chain(outer_plots().iter()) {
        if let Some(piece) = tp.piece {
            let solid = !matches!(tp.name, "fire_pit" | "empty_grave" | "gallows");
            spawn_kit(commands, meshes, piece, tp.pos, tp.yaw, CastleKind::Always, crate::castle_kit::Edit::None, solid);
        }
    }
    // The street village: each house with its burgage yard behind it, revealed one by one.
    for (i, h) in houses().iter().enumerate() {
        let kind = CastleKind::House(i as u8);
        spawn_kit(commands, meshes, h.piece, h.pos, h.yaw, kind, crate::castle_kit::Edit::None, true);
        for (piece, x, z, yaw) in house_yard(h) {
            spawn_kit(commands, meshes, piece, h.local(x, z), h.yaw + yaw, kind, crate::castle_kit::Edit::None, false);
        }
    }

    // The bell's live swinging half (bronze + clapper/rope) hangs in the kit tower's belfry.
    spawn_bell_swing(commands, meshes, &mats);

    // Pooled flicker-lights for the war-braziers (same gate lifecycle; flame local y = 1.5).
    for gate in Gate::ALL {
        let (x, z) = (gate.center().x, gate.center().y);
        for (k, p) in brazier_spots(gate).into_iter().enumerate() {
            commands.spawn((
                Transform::from_translation(Vec3::new(p.x, 1.5, p.z)),
                Visibility::Hidden,
                CastlePart { kind: CastleKind::Gate },
                BiomeEntity,
                crate::firelight::brazier_light(x * 0.43 + z * 0.57 + k as f32 * 3.3),
            ));
        }
    }

    // Grass tufts + clover round the courtyard rim and scattered through the lawn (off the
    // paving) — the courtyard floor is living ground, not a stamped sheet. Permanent.
    {
        let cover_mat = std_mats.add(StandardMaterial {
            base_color: Color::WHITE, // vertex colour carries the hue (groundcover contract)
            perceptual_roughness: 0.62,
            reflectance: 0.5,
            ..default()
        });
        use crate::groundcover as gc;
        let tufts: Vec<Handle<Mesh>> =
            (0..gc::NUM_GRASS_VARIANTS).map(|v| meshes.add(gc::build_grass_tuft_mesh(v))).collect();
        let clovers: Vec<Handle<Mesh>> =
            (0..gc::NUM_CLOVER_VARIANTS).map(|v| meshes.add(gc::build_clover_mesh(v))).collect();
        let mut r = Rng(0x9ea5);
        // Pick a random variant handle from a set.
        let pick = |set: &[Handle<Mesh>], r: &mut Rng| -> Handle<Mesh> {
            set[((r.f() * set.len() as f32) as usize).min(set.len() - 1)].clone()
        };
        let sprig = |x: f32, z: f32, mesh: Handle<Mesh>, s: f32, r: &mut Rng, commands: &mut Commands| {
            commands.spawn((
                Mesh3d(mesh),
                MeshMaterial3d(cover_mat.clone()),
                Transform {
                    translation: Vec3::new(x, 0.02, z),
                    rotation: Quat::from_rotation_y(r.f() * std::f32::consts::TAU),
                    scale: Vec3::splat(s),
                },
                bevy::light::NotShadowCaster,
                CastlePart { kind: CastleKind::Always },
                BiomeEntity,
            ));
        };
        // Rim band: walk the enceinte a few strides inside the wall, jittering across the fray
        // band; skip the gate lanes and the plots.
        for i in 0..72 {
            let k = i * SIDES / 72;
            let (a, d, len) = side(k);
            let t = (i * SIDES % 72) as f32 / 72.0 + r.f() / SIDES as f32;
            let p = a + d * (len * t.fract()) + inward(d) * (2.4 + r.f() * 2.6);
            let (x, z) = (p.x, p.y);
            let near_gate = Gate::ALL.iter().any(|g| g.center().distance(p) < 3.6);
            if near_gate || !plot_clear(x, z, 0.4) || !in_courtyard(x, z) {
                continue;
            }
            let mesh = if r.f() < 0.55 { pick(&tufts, &mut r) } else { pick(&clovers, &mut r) };
            let s = 0.45 + r.f() * 0.45;
            sprig(x, z, mesh, s, &mut r, commands);
        }
        // Lawn patches inside the courtyard — small, sparse, low ("gdzie niegdzie"), and
        // never poking up through the plaza/path paving.
        let (bx_, bz_) = courtyard_half();
        for _ in 0..18 {
            let x = (r.f() - 0.5) * 2.0 * (bx_ - 2.0);
            let z = (r.f() - 0.5) * 2.0 * (bz_ - 2.0);
            if on_paving(x, z) || !plot_clear(x, z, 0.4) || wall_inset(x, z) < 3.0 {
                continue;
            }
            let mesh = if r.f() < 0.35 { pick(&tufts, &mut r) } else { pick(&clovers, &mut r) };
            let s = 0.35 + r.f() * 0.3;
            sprig(x, z, mesh, s, &mut r, commands);
        }
    }

    // A few hens pecking in the dirt by the wood yard + the hay (one shared, batched mesh set; each
    // is a moving root parented to its parts, so `peck_hens` can bob the whole bird). Permanent.
    let hen_meshes: Vec<(Handle<Mesh>, M)> =
        hen_parts().into_iter().map(|(m, slot)| (meshes.add(m), slot)).collect();
    for (i, (hx, hz, yaw, sp)) in [
        (WOOD_YARD.0 + 0.6, WOOD_YARD.1 + 1.6, 0.7_f32, 1.6_f32),
        (WOOD_YARD.0 + 1.8, WOOD_YARD.1 + 0.9, 2.2, 1.9),
        (HAY_CORNER.0 + 1.5, HAY_CORNER.1 + 0.5, -1.1, 1.7),
        (HAY_CORNER.0 + 1.7, HAY_CORNER.1 - 1.0, 2.6, 2.2),
    ]
    .into_iter()
    .enumerate()
    {
        let base_yaw = Quat::from_rotation_y(yaw);
        let parent = commands
            .spawn((
                Transform::from_xyz(hx, 0.0, hz).with_rotation(base_yaw),
                Visibility::Inherited,
                CastlePart { kind: CastleKind::Always },
                Hen { base_yaw, phase: i as f32 * 1.3, speed: sp },
                BiomeEntity,
            ))
            .id();
        commands.entity(parent).with_children(|p| {
            for (mh, slot) in &hen_meshes {
                p.spawn((Mesh3d(mh.clone()), MeshMaterial3d(mats.get(*slot)), Transform::default()));
            }
        });
    }

    // Courtyard set dressing + the upgrade-bought set pieces (armory, tax booth, shrine, …) —
    // a separate module so the structures stay readable here.
    crate::castle_decor::build(commands, meshes, &mats);
    crate::gates::build(commands, meshes, &mats);

    // The always-present structures are solid from the start; gated ones register their blockers
    // when their upgrade reveals them (see `sync_castle`) — no invisible barriers.
    register_keep_blocker();
    register_yard_blockers();
    register_plot_blockers();
    mats
}

/// The two war-brazier spots flanking a gate's APPROACH (outside the walls, clear of the gate
/// lane and the gatehouse turrets): the night siege's melee happens right here, and on the
/// moon-dark ground it filmed as black-on-black.
fn brazier_spots(gate: Gate) -> [Vec3; 2] {
    let (c, out) = (gate.center(), gate.outward());
    let perp = Vec2::new(-out.y, out.x);
    let half = GATE_GAP / 2.0 + 1.9;
    [-half, half].map(|s| {
        let p = c + out * 5.2 + perp * s;
        Vec3::new(p.x, 0.0, p.y)
    })
}

/// Is `(x, z)` clear (by `margin`) of every reserved plot inside the walls and the market's
/// buildings outside?
pub(crate) fn plot_clear(x: f32, z: f32, margin: f32) -> bool {
    town_plots().iter().chain(outer_plots().iter()).all(|p| {
        let l = Quat::from_rotation_y(-p.yaw) * Vec3::new(x - p.pos.x, 0.0, z - p.pos.y);
        l.x.abs() > p.half.x + margin || l.z.abs() > p.half.y + margin
    })
}

/// Every reserved plot is solid from the start (at its building's footprint; open plots — the
/// herb garden, the grave — only at their fixtures).
fn register_plot_blockers() {
    let p = COLLISION_PAD;
    for tp in town_plots().iter().chain(outer_plots().iter()) {
        let Some((off, half)) = tp.solid else { continue };
        let c = Quat::from_rotation_y(tp.yaw) * Vec3::new(off, 0.0, 0.0);
        crate::blockers::add_obb(tp.pos.x + c.x, tp.pos.y + c.z, half.x + p, half.y + p, tp.yaw);
    }
    // The bell tower stands from the start (old-colony stone): the shaft on the wall line + Pip's
    // platform and ladder on the yard side.
    let (_, d, _) = side(S_SIDE);
    let c = BELL_POS + inward(d) * 0.9;
    crate::blockers::add_obb(c.x, c.y, BELL_TOWER_HALF + p, 2.9 + p, yaw_along(d));
    // The old colony's broken circuit: each standing fragment's wall body (the rubble spill and
    // the rubble heaps stay walkable).
    for (i, t, name) in RUINS {
        if name == "ck_rubble" {
            continue;
        }
        let (a, d, len) = side(i);
        let c = a + d * (len * t) - inward(d) * 0.5;
        let hw = if name == "ck_ruin_wall_a" { 2.6 } else { 1.8 };
        crate::blockers::add_obb(c.x, c.y, hw, 0.7, yaw_along(d));
    }
}

/// Player-body margin so movers stop just shy of a face instead of clipping into it.
const COLLISION_PAD: f32 = 0.12;

/// The keep is solid from the start (every tier stands on the same footprint: the ruin shell, the
/// re-roofed keep, the donjon with its stair).
fn register_keep_blocker() {
    let p = COLLISION_PAD;
    crate::blockers::add_box(KEEP_POS.x + 0.1, KEEP_POS.y + 0.1, 4.5 + p, 4.1 + p);
}

/// Match the permanent work-yard props' ground footprints, including their baked local offsets
/// and rotations. Separate boxes leave gaps around logs, cart handles and sacks walkable instead
/// of turning each courtyard corner into one oversized obstacle.
fn register_yard_blockers() {
    let part = |pos: Vec2, yaw: f32, x: f32, z: f32, hw: f32, hd: f32| {
        let offset = Quat::from_rotation_y(yaw) * Vec3::new(x, 0.0, z);
        crate::blockers::add_obb(pos.x + offset.x, pos.y + offset.z, hw, hd, yaw);
    };

    let wood = Vec2::new(WOOD_YARD.0, WOOD_YARD.1);
    part(wood, WOOD_YARD.2, 0.0, 0.0, 0.30, 0.30); // chopping block
    part(wood, WOOD_YARD.2, 0.0, -0.9, 0.75, 0.37); // stacked logs

    let hay = Vec2::new(HAY_CORNER.0, HAY_CORNER.1);
    part(hay, HAY_CORNER.2, 0.0, 0.025, 0.71, 0.315); // bales and binding ropes
    for (x, z) in [(0.72, 0.24), (0.8, -0.22)] {
        part(hay, HAY_CORNER.2, x, z, 0.20, 0.20);
    }

    let cart = Vec2::new(CART_CORNER.0, CART_CORNER.1);
    part(cart, CART_CORNER.2, 0.0, 0.0, 0.65, 0.44); // bed, rails and wheels
    for z in [-0.28, 0.28] {
        part(cart, CART_CORNER.2, 0.85, z, 0.45, 0.03); // handle shafts
    }
    for (x, z) in [(0.95, -0.6), (1.2, -0.35)] {
        part(cart, CART_CORNER.2, x, z, 0.31, 0.31); // barrels and hoops
    }
}

/// Wall blockers (registered when the walls go up — the palisade and the stone curtain share the
/// line): one oriented box per run between corners / gate openings, plus each corner post.
pub(crate) fn register_walls_blockers() {
    let p = COLLISION_PAD;
    for (a, b) in wall_segments() {
        let c = (a + b) / 2.0;
        crate::blockers::add_obb(c.x, c.y, a.distance(b) / 2.0, WALL_THICK / 2.0 + p, yaw_along((b - a).normalize()));
    }
    for v in ENCEINTE {
        crate::blockers::add_box(v.x, v.y, 1.0 + p, 1.0 + p);
    }
}

/// The stone tier's extra bulk (registered with the Reinforced upgrade): the corner towers and
/// the gatehouse bodies either side of each passage (the turrets project into the field).
fn register_curtain_blockers() {
    let p = COLLISION_PAD;
    for v in ENCEINTE {
        crate::blockers::add_box(v.x, v.y, 2.3 + p, 2.3 + p);
    }
    for g in Gate::ALL {
        let (_, d, _) = side(g.side());
        for s in [-1.0_f32, 1.0] {
            let c = g.center() + d * (s * 2.35) - inward(d) * 0.68;
            crate::blockers::add_obb(c.x, c.y, 0.85 + p, 3.02 + p, yaw_along(d));
        }
    }
}

/// The defender towers' footprints (registered when Towers is built — standing on the corners).
fn register_towers_blockers() {
    let p = COLLISION_PAD;
    for t in defender_towers() {
        crate::blockers::add_box(t.x, t.y, 1.7 + p, 1.7 + p);
    }
}

/// One house's blocker (registered when that house rises).
fn register_house_blocker(i: usize) {
    let p = COLLISION_PAD;
    let h = &houses()[i];
    crate::blockers::add_obb(h.pos.x, h.pos.y, h.half.x + p, h.half.y + p, h.yaw);
}

/// Drop the lazily-registered wall / curtain / tower / house collision boxes by their centres (the
/// keep, plot and ruin boxes stay — they're permanent). Pairs with resetting [`CastleBuilt`] so
/// `sync_castle` re-registers the boxes the loaded run actually earns.
fn clear_castle_blockers() {
    for (a, b) in wall_segments() {
        let c = (a + b) / 2.0;
        crate::blockers::remove_box_near(c.x, c.y, 0.3);
    }
    for v in ENCEINTE {
        crate::blockers::remove_box_near(v.x, v.y, 0.3);
    }
    for g in Gate::ALL {
        let (_, d, _) = side(g.side());
        for s in [-1.0_f32, 1.0] {
            let c = g.center() + d * (s * 2.35) - inward(d) * 0.68;
            crate::blockers::remove_box_near(c.x, c.y, 0.3);
        }
    }
    for h in houses() {
        crate::blockers::remove_box_near(h.pos.x, h.pos.y, 0.3);
    }
}

/// On a Continue/Load ([`crate::savegame::GameLoaded`]), reconcile the castle's lazily-registered
/// collision to the loaded build state. `CastleBuilt` + the wall/tower/house boxes are otherwise
/// only reset by a full world rebuild's `blockers::reset` (`biome::apply_build`); an in-process
/// Continue rebuilds nothing, so loading into a less-built state would leave last run's
/// wall/tower/house boxes lingering as **invisible barriers** while their meshes hide. Drop those
/// boxes + re-arm `CastleBuilt`; `sync_castle` re-registers from the loaded flags next pass.
fn reconcile_castle_blockers_on_load(
    mut ev: MessageReader<crate::savegame::GameLoaded>,
    mut built: ResMut<CastleBuilt>,
) {
    if ev.read().count() == 0 {
        return;
    }
    clear_castle_blockers();
    *built = CastleBuilt::default();
}

// ── Drifting chimney smoke ───────────────────────────────────────────────────────
#[derive(Component)]
#[allow(dead_code)] // chimney anchors return with the town kit's chimneys
struct Smoke {
    x: f32,
    z: f32,
    base_y: f32,
    phase: f32,
    speed: f32,
}

/// A pre-wall courtyard hen: a moving root that [`peck_hens`] bobs + tips forward (pecking the
/// dirt). `base_yaw` is its facing; visibility is driven by its `CastlePart { PreWalls }`.
#[derive(Component)]
struct Hen {
    base_yaw: Quat,
    phase: f32,
    speed: f32,
}

/// Which upgrade reveals a given castle part (the castle builds up instead of starting full). The
/// fortification tiers (spec v2 §2): the old colony's RUINS until the walls rise; the PALISADE
/// (timber gates, corner posts, Towers-track watchtowers → stone towers) with the Walls; the STONE
/// CURTAIN (corner towers, gatehouses) with the Reinforced upgrade.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum CastleKind {
    Always,
    /// Shown ONLY before the walls go up — the old colony's broken circuit (ruin fragments, rubble).
    PreWalls,
    /// Any wall tier (the cobbled gate passages + keep apron).
    Walls,
    /// Walls + the Gate upgrade (the war-braziers outside the gates).
    Gate,
    House(u8),
    /// The palisade tier: log runs, timber gates, the plain corner posts.
    Palisade,
    /// A defender corner's post — the palisade tier before the Towers upgrade puts a tower on it.
    PalisadeCorner,
    /// A defender corner's timber watchtower (Towers, before Tower Mastery), unless the stone
    /// curtain stands.
    WatchTower,
    /// A defender corner's stone mural tower (Tower Mastery), unless the stone curtain stands.
    StoneTower,
    /// The stone tier: curtain runs, corner towers, gatehouses (Reinforced).
    Curtain,
    /// The ruined keep shell of the old colony (no walls yet).
    KeepTier0,
    /// The keep re-roofed in timber — with the Walls.
    KeepTier1,
    /// The stone donjon — with the Reinforced upgrade.
    KeepTier2,
}

impl CastleKind {
    /// Is a part of this kind shown for these defenses / this many houses?
    pub(crate) fn shown(self, def: &Defenses, houses: u32) -> bool {
        let stone = def.walls && def.reinforced;
        match self {
            CastleKind::Always => true,
            CastleKind::PreWalls => !def.walls,
            CastleKind::Walls => def.walls,
            CastleKind::Gate => def.walls && def.gate,
            CastleKind::House(i) => (i as u32) < houses,
            CastleKind::Palisade => def.walls && !def.reinforced,
            CastleKind::PalisadeCorner => def.walls && !def.reinforced && !def.towers,
            CastleKind::WatchTower => def.towers && !def.tower_mastery && !stone,
            CastleKind::StoneTower => def.towers && def.tower_mastery && !stone,
            CastleKind::Curtain => stone,
            CastleKind::KeepTier0 => !def.walls && !def.reinforced,
            CastleKind::KeepTier1 => def.walls && !def.reinforced,
            CastleKind::KeepTier2 => def.reinforced,
        }
    }
}

#[derive(Component)]
pub(crate) struct CastlePart {
    pub(crate) kind: CastleKind,
}

/// Which gated groups have had their (append-only) collision blockers registered, so each is
/// added exactly once the first time it's revealed. **Must be reset whenever the matching boxes
/// leave the obstacle set**, or the lazily-registered wall/tower/house boxes never come back — they
/// read as "already built" while their collision is gone. Two reset paths: a full world rebuild /
/// biome swap (`biome::apply_build` resets this right after `blockers::reset()`), and an in-process
/// Continue/Load (`reconcile_castle_blockers_on_load` — a Load rebuilds nothing, so it drops last
/// run's boxes by centre and re-arms this so `sync_castle` re-registers from the loaded flags).
#[derive(Resource, Default)]
pub(crate) struct CastleBuilt {
    walls: bool,
    curtain: bool,
    towers: bool,
    houses: [bool; 12],
}

/// Reveal castle parts and lazily register each group's collision the first time it appears.
/// The fortification tiers follow the Defense-branch upgrades; the twelve village **houses** are
/// the town's dwellings — the first `town.houses` of them show, nearest the W gate first.
fn sync_castle(
    def: Res<Defenses>,
    town: Res<crate::town::TownRes>,
    mut built: ResMut<CastleBuilt>,
    mut commands: Commands,
    mut q: Query<(Entity, &CastlePart, &mut Visibility, &mut Transform, Option<&crate::build_fx::RevealAt>)>,
    mut seeded: Local<bool>,
) {
    let houses = town.0.houses;
    // Construction feedback (rise + dust) fires only on a *live* flag flip — never on the first
    // pass (FOREST_DEFEND staging / a loaded save start already-built) and never on a biome
    // rebuild's respawn (parts respawn Hidden but def/town didn't change).
    let live = *seeded && (def.is_changed() || town.is_changed());
    *seeded = true;
    let mut dust: Vec<Vec3> = Vec::new();
    for (e, part, mut vis, mut tf, at) in &mut q {
        let show = part.kind.shown(&def, houses);
        if live && show && *vis == Visibility::Hidden {
            if let Some(crate::build_fx::RevealAt(pos)) = at {
                let pop = crate::build_fx::BuildPop::rise();
                tf.scale = pop.scale0(); // same-frame, so the part never flashes full-size
                commands.entity(e).try_insert(pop);
                // One burst per structure, not per piece.
                if !dust.iter().any(|p| p.distance_squared(*pos) < 9.0) {
                    dust.push(*pos);
                    commands.spawn(crate::build_fx::DustBurst::part(*pos));
                }
            }
        }
        *vis = if show { Visibility::Inherited } else { Visibility::Hidden };
    }
    // Lazy, once-only collision registration on first reveal.
    if def.walls && !built.walls {
        built.walls = true;
        register_walls_blockers();
    }
    if def.walls && def.reinforced && !built.curtain {
        built.curtain = true;
        register_curtain_blockers();
    }
    if def.towers && !built.towers {
        built.towers = true;
        register_towers_blockers();
    }
    for i in 0..12 {
        if (i as u32) < houses && !built.houses[i] {
            built.houses[i] = true;
            register_house_blocker(i);
        }
    }
}

/// Windows are lamplight, not paint: barely lit by day, warm and bright once the townsfolk
/// shutter themselves indoors at dusk — the visible half of the night curfew (`villagers`
/// pulls everyone off the streets as night falls; the lit windows say where they went).
/// One shared material drives every window on the island, so this is a single write.
fn window_glow(
    clock: Res<crate::scene::SkyClock>,
    mats: Option<Res<VillageMats>>,
    mut materials: ResMut<Assets<StandardMaterial>>,
) {
    let Some(mats) = mats else { return };
    let night = crate::scene::night_of(clock.t);
    if let Some(mut m) = materials.get_mut(&mats.0.get(M::Window)) {
        m.emissive = srgb(WINDOW_GLOW).to_linear() * (0.35 + 4.4 * night);
    }
}

pub struct CastlePlugin;
impl Plugin for CastlePlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<CastleBuilt>().init_resource::<BellRing>().add_systems(
            Update,
            (
                drift_smoke,
                peck_hens,
                swing_bell,
                // Reconcile-on-load runs before sync so the same frame re-registers from the
                // loaded flags after last run's stale boxes are dropped.
                reconcile_castle_blockers_on_load.before(sync_castle),
                sync_castle,
                window_glow,
            ),
        );
    }
}

/// Bob each hen and tip it forward on the down-stroke so it reads as pecking the dirt (ungated VFX
/// — keeps moving even while the world is frozen, like the chimney smoke).
fn peck_hens(time: Res<Time>, mut q: Query<(&Hen, &mut Transform)>) {
    let t = time.elapsed_secs();
    for (h, mut tf) in &mut q {
        let cycle = (t * h.speed + h.phase).sin();
        let peck = cycle.max(0.0); // 0..1 forward-tip on the down beat
        tf.rotation = h.base_yaw * Quat::from_rotation_z(peck * 0.55);
        tf.translation.y = peck * 0.015; // a tiny hop
    }
}

fn drift_smoke(time: Res<Time>, mut q: Query<(&Smoke, &mut Transform)>) {
    let t = time.elapsed_secs();
    for (s, mut tf) in &mut q {
        let cycle = (t * s.speed + s.phase).rem_euclid(1.0);
        tf.translation.x = s.x + (t * 0.7 + s.phase * 6.0).sin() * 0.18 * cycle;
        tf.translation.z = s.z + (t * 0.6 + s.phase * 6.0).cos() * 0.18 * cycle;
        tf.translation.y = s.base_y + cycle * 1.7;
        let sc = (0.12 + cycle * 0.42) * (1.0 - cycle).max(0.0);
        tf.scale = Vec3::splat(sc.max(0.001));
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Separating-axis overlap test of two oriented rectangles `(centre, half, yaw)`.
    fn obb_overlap(a: (Vec2, Vec2, f32), b: (Vec2, Vec2, f32), gap: f32) -> bool {
        let axes = |yaw: f32| {
            let x = Quat::from_rotation_y(yaw) * Vec3::X;
            let z = Quat::from_rotation_y(yaw) * Vec3::Z;
            [Vec2::new(x.x, x.z), Vec2::new(z.x, z.z)]
        };
        let (aa, ba) = (axes(a.2), axes(b.2));
        let radius = |ax: Vec2, axes: [Vec2; 2], half: Vec2| axes[0].dot(ax).abs() * half.x + axes[1].dot(ax).abs() * half.y;
        aa.iter().chain(ba.iter()).all(|&ax| {
            let d = (b.0 - a.0).dot(ax).abs();
            d < radius(ax, aa, a.1) + radius(ax, ba, b.1) + gap
        })
    }

    /// The enceinte is a fixed convex polygon: 7–9 corners, sides 10–30u, every interior angle
    /// 105–170°, clockwise, about the old rectangle's area, the gate sides axis-aligned.
    #[test]
    fn enceinte_is_a_realistic_convex_polygon() {
        assert!((7..=9).contains(&SIDES));
        let mut area = 0.0;
        for i in 0..SIDES {
            let (a, d, len) = side(i);
            assert!((10.0..=30.5).contains(&len), "side {i} is {len}u");
            let (_, d2, _) = side(i + 1);
            let turn = d.perp_dot(d2); // clockwise in x-east/z-south = positive perp-dot
            assert!(turn > 0.0, "corner {} is reflex", (i + 1) % SIDES);
            let interior = 180.0 - d.angle_to(d2).abs().to_degrees();
            assert!((105.0..=170.0).contains(&interior), "corner {} is {interior}°", (i + 1) % SIDES);
            let b = a + d * len;
            area += a.perp_dot(b) / 2.0;
        }
        assert!((2000.0..2800.0).contains(&area), "area {area}");
        for g in Gate::ALL {
            let (_, d, _) = side(g.side());
            assert!(d.x.abs() < 1e-4 || d.y.abs() < 1e-4, "{g:?} side must be axis-aligned");
            assert!(wall_inset(g.center().x, g.center().y).abs() < 1e-3, "{g:?} centre on its side");
            assert!((inward(d) + g.outward()).length() < 1e-4, "{g:?} outward must leave the castle");
        }
        assert!(in_courtyard(0.0, 0.0) && !in_courtyard(0.0, -30.0) && in_footprint(-29.0, 0.0));
        assert!(outside_dist(-38.0, 0.0) > 9.9 && outside_dist(-38.0, 0.0) < 10.1);
    }

    /// Every wall run lands on whole modules between the corner towers / gate pieces: the kit
    /// pieces of a side tile it without gaps or overlaps beyond the tuck-under at soft ends.
    #[test]
    fn kit_runs_tile_each_side() {
        let layout = kit_layout();
        for i in 0..SIDES {
            let (a, d, len) = side(i);
            let mut spans: Vec<(f32, f32)> = layout
                .iter()
                .filter(|p| p.kind == CastleKind::Curtain && p.name.starts_with("ck_curtain"))
                .filter(|p| inward(d).dot(p.pos - a).abs() < 1e-3 && (p.pos - a).dot(d) > 0.0 && (p.pos - a).dot(d) < len)
                .map(|p| {
                    let l = match p.name {
                        "ck_curtain_2" => 2.0,
                        "ck_curtain_1" => 1.0,
                        _ => 4.0,
                    };
                    let u = (p.pos - a).dot(d);
                    (u - l / 2.0, u + l / 2.0)
                })
                .collect();
            spans.sort_by(|x, y| x.0.total_cmp(&y.0));
            assert!(!spans.is_empty(), "side {i} has no curtain");
            assert!(spans[0].0 > 0.9 && spans[0].0 < 2.05, "side {i} run starts at {}", spans[0].0);
            assert!(len - spans.last().unwrap().1 > 0.9, "side {i} run overruns the corner");
            for w in spans.windows(2) {
                let gap = w[1].0 - w[0].1;
                assert!(gap.abs() < 1e-3 || gap > 1.9, "side {i}: modules {:?} {:?} neither abut nor leave a gate", w[0], w[1]);
            }
        }
    }

    #[test]
    fn yard_props_are_solid_without_closing_gate_lanes() {
        let _guard = crate::blockers::TEST_LOCK.lock().unwrap();
        crate::blockers::reset();
        register_keep_blocker();
        register_yard_blockers();
        register_plot_blockers();
        register_walls_blockers();
        register_curtain_blockers();
        register_towers_blockers();
        for (x, z, _) in [WOOD_YARD, HAY_CORNER, CART_CORNER] {
            assert!(crate::blockers::is_blocked(x, z), "work-yard prop at ({x}, {z}) must be solid");
        }
        // Every gate lane stays open from outside the gate to the courtyard.
        for g in Gate::ALL {
            for k in -5..8 {
                let p = g.center() - g.outward() * k as f32;
                assert!(!crate::blockers::any_within(p.x, p.y, 0.35), "{g:?} lane at {p} must stay clear");
            }
        }
        // The wall ring is closed everywhere else: walking the polygon just outside, every step
        // toward the centre hits a blocker before the courtyard.
        for i in 0..SIDES {
            let (a, d, len) = side(i);
            let mut u = 0.5;
            while u < len - 0.5 {
                let p = a + d * u;
                let gate = Gate::ALL.iter().any(|g| g.side() == i && g.center().distance(p) < GATE_GAP / 2.0 + 0.2);
                if !gate {
                    assert!(crate::blockers::is_blocked(p.x, p.y), "wall gap at side {i} u {u} ({p})");
                }
                u += 0.5;
            }
        }
        crate::blockers::reset();
    }

    /// Spec v2 §2 / layout v3: a ≥24×16u open courtyard between the keep and the south gate — no
    /// plot, yard prop, bell tower or keep inside it; every inner plot stands inside the walls
    /// against the curtain, clear of the others, of the gate lanes and of the corner towers.
    #[test]
    fn courtyard_stays_open() {
        let (cx, cz, hx, hz) = COURTYARD;
        assert!(hx * 2.0 >= 24.0 && hz * 2.0 >= 16.0, "courtyard {}x{} too small", hx * 2.0, hz * 2.0);
        for (x, z) in [(cx - hx, cz - hz), (cx + hx, cz - hz), (cx - hx, cz + hz), (cx + hx, cz + hz)] {
            assert!(wall_inset(x, z) > 5.0, "courtyard corner ({x},{z}) too close to the wall");
        }
        let yard = (Vec2::new(cx, cz), Vec2::new(hx, hz), 0.0);
        let mut boxes: Vec<(&str, (Vec2, Vec2, f32))> = Vec::new();
        for tp in town_plots() {
            let b = (tp.pos, tp.half, tp.yaw);
            if !matches!(tp.name, "fire_pit" | "well") {
                assert!(!obb_overlap(b, yard, 0.0), "{} intrudes on the courtyard", tp.name);
            }
            // inside the walls, clear of the corner towers (r ≈ 3) and the gate passages
            let l = Quat::from_rotation_y(tp.yaw);
            for (sx, sz) in [(-1.0, -1.0), (1.0, -1.0), (-1.0, 1.0), (1.0, 1.0)] {
                let c = l * Vec3::new(sx * tp.half.x, 0.0, sz * tp.half.y);
                let p = tp.pos + Vec2::new(c.x, c.z);
                assert!(wall_inset(p.x, p.y) > 0.8, "{} corner {p} in the wall", tp.name);
                assert!(ENCEINTE.iter().all(|v| v.distance(p) > 3.0), "{} corner {p} in a corner tower", tp.name);
            }
            for g in Gate::ALL {
                for k in 0..7 {
                    let q = g.interior(k as f32);
                    assert!(!obb_overlap(b, (q, Vec2::splat(1.5), 0.0), 0.0), "{} blocks the {g:?} lane", tp.name);
                }
            }
            boxes.push((tp.name, b));
        }
        for (x, z, _) in [WOOD_YARD, HAY_CORNER, CART_CORNER] {
            assert!(!obb_overlap((Vec2::new(x, z), Vec2::splat(1.5), 0.0), yard, 0.0), "yard prop at ({x},{z}) intrudes on the courtyard");
            assert!(in_courtyard(x, z));
        }
        boxes.push(("keep", (KEEP_POS, KEEP_HALF, 0.0)));
        boxes.push(("bell tower", (BELL_POS - Vec2::Y * 1.0, Vec2::new(BELL_TOWER_HALF, 3.0), 0.0)));
        assert!(!obb_overlap(boxes.last().unwrap().1, yard, 0.0));
        assert!(KEEP_FRONT < cz - hz, "the keep must sit north of the courtyard");
        for i in 0..boxes.len() {
            for j in i + 1..boxes.len() {
                assert!(!obb_overlap(boxes[i].1, boxes[j].1, 0.1), "{} overlaps {}", boxes[i].0, boxes[j].0);
            }
        }
    }

    /// Layout v3: the houses stand OUTSIDE the walls as a street village along the King's Road —
    /// every burgage plot clear of the walls, the road, the lane, the market and every other plot.
    #[test]
    fn village_plots_line_the_road_without_overlapping() {
        let hs = houses();
        assert_eq!(hs.len(), 12);
        let mut plots: Vec<(String, (Vec2, Vec2, f32))> =
            hs.iter().enumerate().map(|(i, h)| (format!("house {i} ({})", h.piece), h.plot())).collect();
        for tp in outer_plots() {
            plots.push((tp.name.to_string(), (tp.pos, tp.half, tp.yaw)));
        }
        plots.push(("merchant shop".into(), (MERCHANT_SHOP, Vec2::new(1.6, 1.05), 0.0)));
        for (i, (name, p)) in plots.iter().enumerate() {
            assert!(outside_dist(p.0.x, p.0.y) > 5.0, "{name} at {} hugs the walls", p.0);
            for (other, q) in plots.iter().skip(i + 1) {
                assert!(!obb_overlap(*p, *q, 0.2), "{name} at {} overlaps {other} at {}", p.0, q.0);
            }
        }
        for (i, h) in hs.iter().enumerate() {
            // the house front sits by its street, never on it
            let d = village_dist(h.pos.x, h.pos.y);
            assert!(d > h.half.y + 1.8 && d < h.half.y + 4.0, "house {i} is {d}u off the street");
            for s in 0..64 {
                let q = polyline_at(&STREET, s as f32).0;
                assert!(!obb_overlap(h.plot(), (q, Vec2::splat(1.6), 0.0), 0.0), "house {i} plot over the King's Road at {q}");
                let q = polyline_at(&LANE, s as f32 * 0.4).0;
                assert!(!obb_overlap(h.plot(), (q, Vec2::splat(1.2), 0.0), 0.0), "house {i} plot over the lane at {q}");
            }
        }
        // nearest the gate first
        let gate = Gate::West.center();
        assert!(hs[0].pos.distance(gate) < hs[11].pos.distance(gate));
    }
}
