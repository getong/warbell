//! The central **castle** — a faithful, textured Bevy port of the TS game's fully-upgraded
//! city (`cityModels.tsx` + `House.tsx` + `WarBell.tsx`, layout from `cityPlan.ts`). Built
//! complete: keep, perimeter walls split around four gates, four corner towers, eight
//! houses, a cobbled courtyard, the war bell, banners, torches and chimney smoke.
//!
//! This module owns the **meshes** — the structures are otherwise static here; the gameplay that
//! lives *on* them is wired elsewhere: the keep's HP/repair and the night siege in `siege.rs`, the
//! war-bell ring + War Table in `interaction.rs`, the tower-mounted archers/ballista in
//! `defenses.rs`. At the island centre (world origin, flat grass safe-zone, y=0). Kept at TS
//! *absolute* size (NOT ×1.4) but the PERIMETER is widened (`HALF_X/HALF_Z`) for more courtyard
//! room. Coordinate map: world = `(base − (72,54))`.
//!
//! Surfaces use procedural canvas-style textures ported from the TS `textures.ts`
//! (ashlar stone, plaster, wood planks, roof shingles, cobbles, tilled soil) on tiling
//! repeat-sampled materials — the "feels textured like the original" the brief asked for.
//! Solid bits (banners, bronze, crops) + emissive bits (windows, torch flames, gold) use
//! plain materials. Walls + building footprints register in [`crate::blockers`] so the
//! ambient animals route around them.

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

// Perimeter half-extents — castle v2 (`docs/superpowers/specs/2026-10-11-zamek-v2-design.md` §2):
// 28×21, an interior of 56×42u (≈84×63 m at 1u ≈ 1.5 m) — a small town inside the walls with an
// open courtyard between the keep and the south gate. EVERY castle position below derives from
// these two numbers (gates, keep, zones, houses, yard props, paths), so the perimeter can be
// re-tuned in one place.
pub(crate) const HALF_X: f32 = 28.0;
pub(crate) const HALF_Z: f32 = 21.0;
/// Gap left in a wall run for a gate; the gate posts stand inside it (opening ≈2.9u, a cart passes).
pub(crate) const GATE_GAP: f32 = 3.8;
/// Gate positions along their walls (spec v2 §5): the WEST main gate (King's Road to the bay) at
/// mid-wall, the SOUTH gate (the orc side, under the bell tower) at mid-wall, the NORTH postern
/// (forest + quarry) east of the keep. The EAST wall is solid.
pub(crate) const W_GATE_Z: f32 = 0.0;
pub(crate) const S_GATE_X: f32 = 0.0;
pub(crate) const N_GATE_X: f32 = HALF_X * 0.29;

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
fn pyramid(r: f32, h: f32, base_y: f32) -> Mesh {
    let m = Cone { radius: r, height: h }
        .mesh()
        .resolution(4)
        .build()
        .rotated_by(Quat::from_rotation_y(std::f32::consts::FRAC_PI_4))
        .translated_by(Vec3::new(0.0, base_y + h / 2.0, 0.0));
    flat(scale_uv(m, r / TILE, h / TILE))
}

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

// ── Per-structure local parts ────────────────────────────────────────────────────
const KEEP_W: f32 = 7.0;
const KEEP_H: f32 = 1.9;
const KEEP_D: f32 = 6.0;
const KEEP_FOUND: f32 = 0.3;
/// Keep centre (world XZ): north-centre, its back ~5u off the north wall, so the whole band south
/// of its door down to the south gate is open courtyard (spec v2 §2).
pub const KEEP_POS: Vec2 = Vec2::new(0.0, -HALF_Z + 9.5);
/// World Z of the keep's front (door) face.
pub(crate) const KEEP_FRONT: f32 = KEEP_POS.y + KEEP_D * KEEP_SCALE.z / 2.0;

fn keep_parts() -> Vec<(Mesh, M)> {
    let mut v: Vec<(Mesh, M)> = Vec::new();
    let roof_y = KEEP_FOUND + KEEP_H;
    // Stepped base: a broad ground footing skirt under the foundation course — depth at the
    // waterline without reflowing any of the body geometry above it.
    v.push((bx(KEEP_W + 0.9, 0.14, KEEP_D + 0.9, 0.0, 0.07, 0.0), M::DarkStone));
    v.push((bx(KEEP_W + 0.5, KEEP_FOUND, KEEP_D + 0.5, 0.0, KEEP_FOUND / 2.0, 0.0), M::DarkStone));
    v.push((bx(KEEP_W, KEEP_H, KEEP_D, 0.0, KEEP_FOUND + KEEP_H / 2.0, 0.0), M::Stone));
    // Light-stone belt course banding the body (horizontal articulation).
    v.push((bx(KEEP_W + 0.18, 0.16, KEEP_D + 0.18, 0.0, KEEP_FOUND + KEEP_H * 0.52, 0.0), M::LightStone));
    // Corner buttresses.
    for sx in [-1.0_f32, 1.0] {
        for sz in [-1.0_f32, 1.0] {
            v.push((bx(0.5, KEEP_H + 0.1, 0.5, sx * (KEEP_W / 2.0 - 0.15), KEEP_FOUND + (KEEP_H + 0.1) / 2.0, sz * (KEEP_D / 2.0 - 0.15)), M::DarkStone));
        }
    }
    // Corbelled battlement lip just under the merlons (overhang shadow line, like the walls).
    v.push((bx(KEEP_W + 0.22, 0.16, KEEP_D + 0.22, 0.0, roof_y - 0.04, 0.0), M::DarkStone));
    // Merlons.
    let mut x = -KEEP_W / 2.0 + 0.4;
    while x <= KEEP_W / 2.0 - 0.4 + 1e-3 {
        v.push((bx(0.5, 0.5, 0.5, x, roof_y + 0.25, -KEEP_D / 2.0 + 0.2), M::DarkStone));
        v.push((bx(0.5, 0.5, 0.5, x, roof_y + 0.25, KEEP_D / 2.0 - 0.2), M::DarkStone));
        x += 1.0;
    }
    let mut z = -KEEP_D / 2.0 + 1.2;
    while z <= KEEP_D / 2.0 - 1.2 + 1e-3 {
        v.push((bx(0.5, 0.5, 0.5, -KEEP_W / 2.0 + 0.2, roof_y + 0.25, z), M::DarkStone));
        v.push((bx(0.5, 0.5, 0.5, KEEP_W / 2.0 - 0.2, roof_y + 0.25, z), M::DarkStone));
        z += 1.0;
    }
    // Central tower + cornice + roof + finial + a fluttering pennant.
    v.push((bx(2.0, 1.3, 2.0, 0.0, roof_y + 0.65, 0.0), M::LightStone));
    v.push((bx(2.16, 0.14, 2.16, 0.0, roof_y + 1.24, 0.0), M::DarkStone)); // cornice under the roof
    v.push((pyramid(1.4, 0.95, roof_y + 1.3), M::Roof));
    v.push((Sphere::new(0.18).mesh().ico(2).unwrap().translated_by(Vec3::new(0.0, roof_y + 2.2, 0.0)), M::Gold));
    // Spire pole — the pennant itself is a fluttering cloth entity (banner.rs), spawned in
    // `build` so the merged keep geometry keeps only the pole.
    v.push((cyl(0.03, 0.6, 0.0, roof_y + 2.6, 0.0), M::Beam));
    // Threshold steps + door + arch beam + flanking banners.
    v.push((bx(1.8, 0.1, 0.34, 0.0, 0.05, KEEP_D / 2.0 + 0.32), M::HouseStone)); // lower step
    v.push((bx(1.5, 0.1, 0.22, 0.0, 0.13, KEEP_D / 2.0 + 0.22), M::HouseStone)); // upper step
    v.push((bx(1.4, 1.6, 0.12, 0.0, KEEP_FOUND + 0.85, KEEP_D / 2.0 + 0.02), M::Wood));
    v.push((bx(1.7, 0.3, 0.2, 0.0, KEEP_FOUND + 1.75, KEEP_D / 2.0 + 0.05), M::Beam));
    for sx in [-1.45_f32, 1.45] {
        v.push((bx(0.6, 1.5, 0.04, sx, KEEP_FOUND + 1.3, KEEP_D / 2.0 + 0.08), M::Banner));
    }
    // Arrow slits — front + back pairs, one centred on each side.
    for sx in [-2.4_f32, 2.4] {
        v.push((bx(0.16, 0.7, 0.06, sx, KEEP_FOUND + 1.1, KEEP_D / 2.0 + 0.02), M::Slit));
        v.push((bx(0.16, 0.7, 0.06, sx, KEEP_FOUND + 1.1, -KEEP_D / 2.0 - 0.02), M::Slit));
    }
    for sx in [-1.0_f32, 1.0] {
        v.push((bx(0.06, 0.7, 0.16, sx * (KEEP_W / 2.0 + 0.02), KEEP_FOUND + 1.1, 0.0), M::Slit));
    }
    // Warm glowing windows on the side faces (the keep reads as lived-in at dusk).
    for sx in [-1.0_f32, 1.0] {
        for sz in [-1.4_f32, 1.4] {
            v.push((bx(0.05, 0.5, 0.4, sx * (KEEP_W / 2.0 + 0.01), KEEP_FOUND + 0.6, sz), M::Window));
        }
    }
    v
}

/// **Keep tier 1 — "fortified"** (revealed once the Palisade Walls go up). Four corner turrets rise
/// above the keep's battlements with spired caps + gold finials, so the keep reads as a real castle
/// rather than a lone hall. Authored in the same local space as [`keep_parts`] and spawned with the
/// same transform, so these parts sit exactly on the base keep — purely additive.
fn keep_tier1_parts() -> Vec<(Mesh, M)> {
    let mut v: Vec<(Mesh, M)> = Vec::new();
    let roof_y = KEEP_FOUND + KEEP_H;
    for sx in [-1.0_f32, 1.0] {
        for sz in [-1.0_f32, 1.0] {
            let cx = sx * (KEEP_W / 2.0 - 0.15);
            let cz = sz * (KEEP_D / 2.0 - 0.15);
            v.push((bx(0.74, 1.7, 0.74, cx, roof_y + 0.85, cz), M::Stone)); // turret shaft above the merlons
            v.push((bx(0.9, 0.16, 0.9, cx, roof_y + 1.62, cz), M::DarkStone)); // corbel ring
            v.push((pyramid(0.58, 0.62, roof_y + 1.7).translated_by(Vec3::new(cx, 0.0, cz)), M::Roof)); // spired cap
            v.push((
                Sphere::new(0.1).mesh().ico(1).unwrap().translated_by(Vec3::new(cx, roof_y + 2.44, cz)),
                M::Gold,
            )); // finial
        }
    }
    v
}

/// **Keep tier 2 — "grand fortress"** (revealed once the Reinforced Keep upgrade is bought). A tall
/// pennant spire crowns the central tower, big heraldic banners drape the front, the corner turrets
/// get gilded caps, and a gold band wraps the central tower — the keep at its mightiest. Additive
/// over tiers 0 + 1.
fn keep_tier2_parts() -> Vec<(Mesh, M)> {
    let mut v: Vec<(Mesh, M)> = Vec::new();
    let roof_y = KEEP_FOUND + KEEP_H;
    // Gilded caps crowning the four corner turrets.
    for sx in [-1.0_f32, 1.0] {
        for sz in [-1.0_f32, 1.0] {
            let cx = sx * (KEEP_W / 2.0 - 0.15);
            let cz = sz * (KEEP_D / 2.0 - 0.15);
            v.push((pyramid(0.34, 0.42, roof_y + 2.32).translated_by(Vec3::new(cx, 0.0, cz)), M::Gold));
        }
    }
    // Large heraldic banners draping the front of the keep body.
    for sx in [-1.7_f32, 1.7] {
        v.push((bx(0.95, 2.5, 0.05, sx, KEEP_FOUND + 1.45, KEEP_D / 2.0 + 0.12), M::Banner));
    }
    // Gilded band low on the central tower.
    v.push((bx(2.22, 0.16, 2.22, 0.0, roof_y + 0.2, 0.0), M::Gold));
    v
}

/// Curtain wall to the wall-walk (spec v2 §1: 3.6–4.0u to the merlon tops, 1.2–1.5u thick).
const WALL_H: f32 = 3.4;
pub(crate) const WALL_THICK: f32 = 1.3;

fn wall_parts(len: f32) -> Vec<(Mesh, M)> {
    let mut v: Vec<(Mesh, M)> = Vec::new();
    v.push((bx(len, WALL_H, WALL_THICK, 0.0, WALL_H / 2.0, 0.0), M::Stone));
    // Walkway lip (a thin overhang course just under the merlons). Its top sits a hair ABOVE the
    // main wall's top (which is also at WALL_H) so the two coplanar top faces don't Z-fight/flicker.
    v.push((bx(len, 0.12, WALL_THICK + 0.12, 0.0, WALL_H - 0.04, 0.0), M::DarkStone));
    let step = 0.8;
    let count = (len / step).floor().max(1.0) as i32;
    let start = -((count - 1) as f32 * step) / 2.0;
    for i in 0..count {
        v.push((bx(0.38, 0.42, WALL_THICK + 0.06, start + i as f32 * step, WALL_H + 0.21, 0.0), M::Stone));
    }
    v
}

/// Wall-tower shaft (spec v2 §1: towers 5.5–6.5u to the battlement).
const TOWER_H: f32 = 5.0;

fn tower_parts() -> Vec<(Mesh, M)> {
    let mut v: Vec<(Mesh, M)> = Vec::new();
    v.push((bx(2.05, 0.32, 2.05, 0.0, 0.16, 0.0), M::DarkStone)); // base plinth
    v.push((bx(1.8, TOWER_H, 1.8, 0.0, TOWER_H / 2.0, 0.0), M::Stone)); // shaft
    v.push((bx(1.94, 0.12, 1.94, 0.0, TOWER_H * 0.55, 0.0), M::LightStone)); // string course
    v.push((bx(2.1, 0.4, 2.1, 0.0, TOWER_H + 0.1, 0.0), M::DarkStone)); // corbelled battlement
    // Full crenellation: four corner merlons + four edge-midpoint merlons (gapped crenels between).
    let my = TOWER_H + 0.45;
    for (mx, mz) in [
        (-0.85_f32, -0.85_f32), (0.85, -0.85), (0.85, 0.85), (-0.85, 0.85),
        (0.0, -0.92), (0.92, 0.0), (0.0, 0.92), (-0.92, 0.0),
    ] {
        v.push((bx(0.4, 0.42, 0.4, mx, my, mz), M::DarkStone));
    }
    v.push((pyramid(1.5, 1.4, TOWER_H + 0.3), M::Roof));
    // Arrow slits on all four faces.
    for (ax, az, rot) in [(0.0, 0.91, 0.0), (0.0, -0.91, 0.0), (0.91, 0.0, HALF_PI), (-0.91, 0.0, HALF_PI)] {
        v.push((bake(bx(0.16, 0.8, 0.06, 0.0, 0.0, 0.0), Vec3::new(ax, TOWER_H * 0.5, az), rot, Vec3::ONE), M::Slit));
    }
    // Flag pole — the flag itself is a fluttering cloth entity (banner.rs), spawned in `build`.
    v.push((cyl(0.04, 1.0, 0.0, TOWER_H + 2.0, 0.0), M::Beam));
    v
}

/// Gate passage clear height (spec v2 §1: 2.6–2.8u high × 2.6–3.0u wide — a loaded cart passes).
pub(crate) const GATE_H: f32 = 2.8;

fn gate_parts(width: f32) -> Vec<(Mesh, M)> {
    let mut v: Vec<(Mesh, M)> = Vec::new();
    let half = width / 2.0;
    let post_h = WALL_H + 0.5;
    for sx in [-half, half] {
        v.push((bx(0.9, post_h, WALL_THICK + 0.3, sx, post_h / 2.0, 0.0), M::Stone));
        v.push((bx(1.05, 0.3, WALL_THICK + 0.4, sx, post_h + 0.1, 0.0), M::DarkStone)); // capital
    }
    // Stone head over the passage, from the clear height up to the wall-walk.
    v.push((bx(width + 0.9, WALL_H - GATE_H + 0.2, WALL_THICK, 0.0, (GATE_H + WALL_H + 0.2) / 2.0, 0.0), M::Stone));
    v.push((bx(width + 1.2, 0.3, WALL_THICK + 0.2, 0.0, GATE_H + 0.1, 0.0), M::Beam)); // lintel beam
    v.push((bx(0.6, 0.5, 0.12, 0.0, GATE_H + 0.75, WALL_THICK / 2.0 + 0.04), M::Gold)); // crest
    // The door leaves are separate hinged entities now (`gates.rs`): they swing shut at dusk.
    v
}

// House (the standard cottage's dims — other archetypes carry their own).
const HW: f32 = 2.6;
const HH: f32 = 1.15;
const HD: f32 = 2.0;
const H_FOUND: f32 = 0.18;

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
pub(crate) const HOUSE_SCALE: Vec3 =
    Vec3::new(0.9 * WORLD_BUMP * 1.2, 0.74 * WORLD_BUMP * BUILDING_TALLER * 1.32, 0.9 * WORLD_BUMP * 1.2);
/// Keep root scale (shared by the keep + both grandeur tiers so their parts stay registered). Y is
/// ×[`BUILDING_TALLER`]; footprint unchanged.
/// Castle v2 (spec §1): a keep that dominates the yard — ≈9.5×8u footprint, the body ≈4.4u, the
/// central tower ≈7u, turret caps ≈9.0u and gilded spire tips ≈9.9u — all ≤10u (Y 2.0; interim
/// primitive heights until `castle_kit.glb`).
const KEEP_SCALE: Vec3 = Vec3::new(1.35, 2.0, 1.35);
/// Corner-tower root scale. Y is ×[`BUILDING_TALLER`]; footprint unchanged.
/// Castle v2: 2.7u-square towers, the shaft ([`TOWER_H`]) at full height.
const TOWER_SCALE: Vec3 = Vec3::new(1.5, 1.0, 1.5);

/// Four dwelling silhouettes spread across the twelve slots (3 huts, 4 cottages, 3 townhouses,
/// 2 longhouses) so the rows read as a grown village instead of barracks. All archetypes keep
/// the shared conventions: local origin, base at y=0, FRONT facing +Z, spawned at the same
/// (0.9, 0.74, 0.9) scale — the accessors below feed the per-slot blocker / shutter / smoke
/// wiring that used to assume one cottage.
#[derive(Clone, Copy, PartialEq)]
enum HouseStyle {
    Hut,
    Cottage,
    Townhouse,
    Longhouse,
}

/// Style per dwelling slot (indexes `houses()`); reveal order is unchanged, so even the early
/// settlement mixes a hut, cottages and a townhouse rather than clones.
const HOUSE_STYLES: [HouseStyle; 12] = [
    HouseStyle::Hut, HouseStyle::Cottage, HouseStyle::Townhouse, HouseStyle::Cottage, // N row
    HouseStyle::Cottage, HouseStyle::Longhouse, HouseStyle::Cottage, HouseStyle::Longhouse, // S row | W/E flanks
    HouseStyle::Townhouse, HouseStyle::Hut, HouseStyle::Hut, HouseStyle::Townhouse, // W/E flanks (a hut fits between the smithy and the tavern)
];

/// Roof material per slot — huts thatch; the rest alternate warm vs weathered shingle.
fn house_roof(i: usize) -> M {
    match HOUSE_STYLES[i] {
        HouseStyle::Hut => M::Thatch,
        _ => {
            if i % 2 == 0 {
                M::HouseRoof
            } else {
                M::HouseRoof2
            }
        }
    }
}

/// Local (pre-scale) footprint (w, d) — feeds the per-slot collision blocker.
fn house_dims(style: HouseStyle) -> (f32, f32) {
    match style {
        HouseStyle::Hut => (2.0, 1.7),
        HouseStyle::Cottage => (HW, HD),
        HouseStyle::Townhouse => (2.3, 1.9),
        HouseStyle::Longhouse => (3.6, 1.8),
    }
}

/// Local (pre-scale) front-window centre — where the curfew shutters hang.
fn house_window(style: HouseStyle) -> Vec3 {
    match style {
        HouseStyle::Hut => Vec3::new(0.45, 0.76, 0.85),
        HouseStyle::Cottage => Vec3::new(0.5, H_FOUND + 0.9, HD / 2.0),
        HouseStyle::Townhouse => Vec3::new(0.45, 1.8, 1.03), // the upstairs pane
        HouseStyle::Longhouse => Vec3::new(1.05, 0.78, 0.9),
    }
}

/// Local (pre-scale) chimney spot + stack-top height, for the smoke column. Huts vent
/// through the thatch — no chimney, no smoke.
fn house_chimney(style: HouseStyle) -> Option<(Vec2, f32)> {
    match style {
        HouseStyle::Hut => None,
        HouseStyle::Cottage => Some((Vec2::new(HW / 2.0 - 0.4, 0.25), H_FOUND + HH + 0.74)),
        HouseStyle::Townhouse => Some((Vec2::new(0.75, 0.2), 2.98)),
        HouseStyle::Longhouse => Some((Vec2::new(-1.2, 0.25), 1.94)),
    }
}

fn house_parts_for(i: usize) -> Vec<(Mesh, M)> {
    let roof = house_roof(i);
    match HOUSE_STYLES[i] {
        HouseStyle::Hut => hut_parts(),
        HouseStyle::Cottage => house_parts(roof),
        HouseStyle::Townhouse => townhouse_parts(roof),
        HouseStyle::Longhouse => longhouse_parts(roof),
    }
}

/// The textured village cottage (plaster walls, half-timbered posts, shingle gable, glowing
/// window, stone chimney) — the baseline dwelling the other archetypes riff on.
fn house_parts(roof: M) -> Vec<(Mesh, M)> {
    let mut v: Vec<(Mesh, M)> = Vec::new();
    let wall_top = H_FOUND + HH;
    v.push((bx(HW + 0.2, H_FOUND, HD + 0.2, 0.0, H_FOUND / 2.0, 0.0), M::HouseStone));
    v.push((bx(0.26, 0.75, 0.26, HW / 2.0 - 0.4, wall_top + 0.38, 0.25), M::HouseStone)); // chimney
    v.push((bx(0.32, 0.08, 0.32, HW / 2.0 - 0.4, wall_top + 0.74, 0.25), M::Beam)); // cap
    v.push((bx(HW, HH, HD, 0.0, H_FOUND + HH / 2.0, 0.0), M::Plaster));
    // Corner timber posts (half-timbered look). Straddle the wall's corner EDGE (centre on
    // the corner, half the 0.14 post inside, half proud) — so no post face is coplanar with
    // a wall face. (At the old `HW/2 - 0.07` inset the outer faces sat exactly on the wall
    // surface, z-fighting into the corner flicker.)
    for sx in [-1.0_f32, 1.0] {
        for sz in [-1.0_f32, 1.0] {
            v.push((bx(0.16, HH, 0.16, sx * (HW / 2.0), H_FOUND + HH / 2.0, sz * (HD / 2.0)), M::Beam));
        }
    }
    // Door + lintel + glowing window on the +Z front.
    v.push((bx(0.46, 0.92, 0.06, -0.56, H_FOUND + 0.5, HD / 2.0 + 0.02), M::Wood));
    v.push((bx(0.56, 0.1, 0.08, -0.56, H_FOUND + 1.0, HD / 2.0 + 0.03), M::Beam));
    v.push((bx(0.42, 0.42, 0.04, 0.5, H_FOUND + 0.9, HD / 2.0 + 0.02), M::Window));
    v.push((bx(0.52, 0.06, 0.06, 0.5, H_FOUND + 1.13, HD / 2.0 + 0.03), M::Beam)); // window lintel
    // Gable roof — ridge along X (width), slopes facing ±Z.
    v.push((gable(HW + 0.3, HD + 0.3, 0.6, wall_top), roof));
    v
}

/// The smallest dwelling: one plaster room under a deep-eaved thatch gable.
fn hut_parts() -> Vec<(Mesh, M)> {
    let (w, h, d, f) = (2.0, 0.95, 1.7, 0.14);
    let top = f + h;
    let mut v: Vec<(Mesh, M)> = Vec::new();
    v.push((bx(w + 0.16, f, d + 0.16, 0.0, f / 2.0, 0.0), M::HouseStone));
    v.push((bx(w, h, d, 0.0, f + h / 2.0, 0.0), M::Plaster));
    for sx in [-1.0_f32, 1.0] {
        for sz in [-1.0_f32, 1.0] {
            v.push((bx(0.14, h, 0.14, sx * (w / 2.0), f + h / 2.0, sz * (d / 2.0)), M::Beam));
        }
    }
    v.push((bx(0.42, 0.78, 0.06, -0.45, f + 0.42, d / 2.0 + 0.02), M::Wood)); // door
    v.push((bx(0.52, 0.09, 0.08, -0.45, f + 0.86, d / 2.0 + 0.03), M::Beam));
    v.push((bx(0.42, 0.36, 0.04, 0.45, 0.76, d / 2.0 + 0.02), M::Window));
    v.push((bx(0.5, 0.06, 0.06, 0.45, 0.98, d / 2.0 + 0.03), M::Beam));
    v.push((gable(w + 0.55, d + 0.6, 0.8, top), M::Thatch)); // deep eaves
    v
}

/// Two-story jettied townhouse: stone ground floor, timber-framed plaster upper that juts
/// past it, glowing pane upstairs, tall gable. The vertical accent in each row.
fn townhouse_parts(roof: M) -> Vec<(Mesh, M)> {
    let (w, d, f) = (2.3, 1.9, 0.18);
    let h1 = 1.0; // stone ground floor
    let h2 = 0.85; // jettied upper floor
    let up0 = f + h1 + 0.12; // upper-floor base (above the jetty band)
    let top = up0 + h2;
    let (uw, ud) = (w + 0.16, d + 0.16); // the jetty overhang
    let mut v: Vec<(Mesh, M)> = Vec::new();
    v.push((bx(w + 0.2, f, d + 0.2, 0.0, f / 2.0, 0.0), M::HouseStone));
    v.push((bx(w, h1, d, 0.0, f + h1 / 2.0, 0.0), M::HouseStone));
    v.push((bx(uw + 0.08, 0.12, ud + 0.08, 0.0, f + h1 + 0.06, 0.0), M::Beam)); // jetty band
    v.push((bx(uw, h2, ud, 0.0, up0 + h2 / 2.0, 0.0), M::Plaster));
    for sx in [-1.0_f32, 1.0] {
        for sz in [-1.0_f32, 1.0] {
            v.push((bx(0.14, h2, 0.14, sx * (uw / 2.0), up0 + h2 / 2.0, sz * (ud / 2.0)), M::Beam));
        }
    }
    v.push((bx(0.46, 0.95, 0.06, -0.5, f + 0.5, d / 2.0 + 0.02), M::Wood)); // door
    v.push((bx(0.56, 0.1, 0.08, -0.5, f + 1.0, d / 2.0 + 0.03), M::Beam));
    v.push((bx(0.38, 0.3, 0.04, 0.55, f + 0.62, d / 2.0 + 0.02), M::Slit)); // dark ground pane
    v.push((bx(0.42, 0.42, 0.04, 0.45, 1.8, ud / 2.0 + 0.02), M::Window)); // upstairs glow
    v.push((bx(0.52, 0.06, 0.06, 0.45, 2.05, ud / 2.0 + 0.03), M::Beam));
    v.push((bx(0.26, 0.9, 0.26, 0.75, top + 0.4, 0.2), M::HouseStone)); // chimney
    v.push((bx(0.32, 0.08, 0.32, 0.75, top + 0.83, 0.2), M::Beam));
    v.push((gable(uw + 0.3, ud + 0.34, 0.72, top), roof));
    v
}

/// A long single-ridge hall: the widest dwelling, mid-posts pacing the long wall, two glowing
/// windows flanking a centre door, gable-end chimney, firewood stacked against the end wall.
fn longhouse_parts(roof: M) -> Vec<(Mesh, M)> {
    let (w, h, d, f) = (3.6, 1.0, 1.8, 0.16);
    let top = f + h;
    let mut v: Vec<(Mesh, M)> = Vec::new();
    v.push((bx(w + 0.2, f, d + 0.2, 0.0, f / 2.0, 0.0), M::HouseStone));
    v.push((bx(w, h, d, 0.0, f + h / 2.0, 0.0), M::Plaster));
    // Corner + mid posts give the long wall its half-timber rhythm.
    for sx in [-w / 2.0, -w / 6.0, w / 6.0, w / 2.0] {
        for sz in [-1.0_f32, 1.0] {
            v.push((bx(0.15, h, 0.15, sx, f + h / 2.0, sz * (d / 2.0)), M::Beam));
        }
    }
    v.push((bx(0.5, 0.92, 0.06, 0.0, f + 0.48, d / 2.0 + 0.02), M::Wood)); // centre door
    v.push((bx(0.6, 0.1, 0.08, 0.0, f + 0.98, d / 2.0 + 0.03), M::Beam));
    for sx in [-1.05_f32, 1.05] {
        v.push((bx(0.42, 0.4, 0.04, sx, 0.78, d / 2.0 + 0.02), M::Window));
        v.push((bx(0.5, 0.06, 0.06, sx, 1.02, d / 2.0 + 0.03), M::Beam));
    }
    v.push((bx(0.28, 0.75, 0.28, -1.2, top + 0.34, 0.25), M::HouseStone)); // gable-end chimney
    v.push((bx(0.34, 0.08, 0.34, -1.2, top + 0.74, 0.25), M::Beam));
    v.push((gable(w + 0.4, d + 0.5, 0.62, top), roof));
    // Firewood against the −X gable wall (cylinder axis turned to lie along Z).
    for (y, kz) in [(0.11_f32, -0.13_f32), (0.11, 0.13), (0.3, 0.0)] {
        v.push((
            Cylinder::new(0.1, 0.7)
                .mesh()
                .resolution(8)
                .build()
                .rotated_by(Quat::from_rotation_x(HALF_PI))
                .translated_by(Vec3::new(-w / 2.0 - 0.24, y, kz)),
            M::Wood,
        ));
    }
    v
}

// ── The war bell ─────────────────────────────────────────────────────────────────
// Split in two: a static baked STAND (steps/posts/braces/roof, `bell_frame_parts`) and a live
// swinging assembly hinged at the crossbeam (`spawn_bell_swing` + `swing_bell`) — the bell,
// clapper and pull-rope are real entities so ringing it actually rocks the bronze.

/// World-XZ of the war bell — the BELL TOWER on the south wall line, flanking the south gate on
/// its west side (spec v2 §4/§5: the gate "under the bell tower", where the orcs come from).
/// Shared with `interaction.rs`'s ring zone so the prompt and the prop can never drift apart.
pub const BELL_POS: Vec2 = Vec2::new(S_GATE_X - GATE_GAP / 2.0 - BELL_TOWER_HALF - 0.4, HALF_Z);
/// Half-width of the bell tower's square shaft.
pub(crate) const BELL_TOWER_HALF: f32 = 1.7;
/// Shaft height; the open belfry (four corner piers) stands on it up to [`BELL_TOWER_TOP`].
const BELL_TOWER_SHAFT: f32 = 6.2;
const BELL_TOWER_TOP: f32 = 8.0;
/// Frame yaw — the headstock runs along the wall, so the bell swings in and out of the town.
const BELL_YAW: f32 = 0.0;
/// Headstock hinge height (world Y over `BELL_POS`): the bell hangs in the open belfry.
const BELL_PIVOT_Y: f32 = 7.75;

/// The BELL TOWER (interim primitive until `castle_kit.glb`): old-colony stone — the one thing of
/// the first colony that still stands whole (spec v2 §3). A square ashlar shaft with a dark plinth
/// and string courses, a door on the town side, an OPEN belfry of four corner piers carrying the
/// headstock beam the live bell hangs from, a slab cap and a pyramid roof. Static, `Always`.
fn bell_frame_parts() -> Vec<(Mesh, M)> {
    let mut v: Vec<(Mesh, M)> = Vec::new();
    let w = BELL_TOWER_HALF * 2.0;
    v.push((bx(w + 0.5, 0.6, w + 0.5, 0.0, 0.3, 0.0), M::DarkStone)); // plinth
    v.push((bx(w, BELL_TOWER_SHAFT, w, 0.0, BELL_TOWER_SHAFT / 2.0, 0.0), M::Stone)); // shaft
    for y in [2.4_f32, BELL_TOWER_SHAFT - 0.1] {
        v.push((bx(w + 0.16, 0.2, w + 0.16, 0.0, y, 0.0), M::DarkStone)); // string courses
    }
    // Door on the town (north, -Z) face + a slit above it; a slit on the field side too.
    v.push((bx(1.0, 1.9, 0.08, 0.0, 1.25, -BELL_TOWER_HALF - 0.03), M::Wood));
    v.push((bx(1.2, 0.2, 0.12, 0.0, 2.25, -BELL_TOWER_HALF - 0.05), M::DarkStone));
    v.push((bx(0.16, 0.8, 0.06, 0.0, 4.2, -BELL_TOWER_HALF - 0.02), M::Slit));
    v.push((bx(0.16, 0.8, 0.06, 0.0, 4.2, BELL_TOWER_HALF + 0.02), M::Slit));
    // Open belfry: four corner piers, the headstock beam across them.
    let pier = 0.55;
    let ph = BELL_TOWER_TOP - BELL_TOWER_SHAFT;
    for sx in [-1.0_f32, 1.0] {
        for sz in [-1.0_f32, 1.0] {
            let (px, pz) = (sx * (BELL_TOWER_HALF - pier / 2.0), sz * (BELL_TOWER_HALF - pier / 2.0));
            v.push((bx(pier, ph, pier, px, BELL_TOWER_SHAFT + ph / 2.0, pz), M::Stone));
        }
    }
    v.push((bx(w - 0.2, 0.22, 0.24, 0.0, BELL_PIVOT_Y, 0.0), M::Beam)); // headstock beam (the hinge line)
    v.push((bx(w + 0.3, 0.3, w + 0.3, 0.0, BELL_TOWER_TOP + 0.15, 0.0), M::DarkStone)); // cap slab
    v.push((pyramid(BELL_TOWER_HALF * 1.25, 1.6, BELL_TOWER_TOP + 0.3), M::Roof));
    v
}

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

// ── Layout (parametric perimeter) ────────────────────────────────────────────────

/// The open COURTYARD (spec v2 §2: ≥24×16u, nothing built in it but the fire pit + well at its
/// north edge) as `(cx, cz, half_x, half_z)`: from just south of the keep's door to the south house
/// row, between the west market and the east plots.
pub(crate) const COURTYARD: (f32, f32, f32, f32) =
    (0.0, (KEEP_FRONT + 1.2 + HALF_Z - 5.4) / 2.0, 12.5, (HALF_Z - 5.4 - KEEP_FRONT - 1.2) / 2.0);

/// The worn route network `(cx, cz, w, d)`: [0] the courtyard (the keep apron → the south gate),
/// then the three gate paths. Drawn as packed earth pre-walls and cobble after (see `build`); also
/// used to keep grass sprigs off the paving.
const PATH_RECTS: [(f32, f32, f32, f32); 4] = [
    (COURTYARD.0, COURTYARD.1, COURTYARD.2 * 2.0 - 4.0, COURTYARD.3 * 2.0 - 2.0), // courtyard
    (N_GATE_X, (-HALF_Z + KEEP_FRONT + 1.0) / 2.0, 3.2, KEEP_FRONT + 1.0 + HALF_Z), // north postern → yard
    (S_GATE_X, HALF_Z - 3.0, 3.6, 6.0),                                           // south gate → yard
    ((-HALF_X - COURTYARD.2) / 2.0, W_GATE_Z, HALF_X - COURTYARD.2 + 2.0, 3.6),    // west gate → market → yard
];

/// Cobble paving raised with the walls `(cx, cz, w, d)`: [0] the keep apron, then the three gate
/// passages (through the gap, a stride either side). Everything else stays earth.
const PAVED_RECTS: [(f32, f32, f32, f32); 4] = [
    (KEEP_POS.x, KEEP_FRONT + 1.4, KEEP_W * KEEP_SCALE.x + 1.0, 3.2),
    (N_GATE_X, -HALF_Z, 3.4, 5.0),
    (S_GATE_X, HALF_Z, 3.8, 5.0),
    (-HALF_X, W_GATE_Z, 5.0, 3.8),
];

/// How strongly world point `(wx, wz)` sits on the trodden castle yard (the plaza + the four gate
/// paths of [`PATH_RECTS`]): 1 across a rect's core, fading to 0 over ~`EDGE` beyond its rim, with
/// a little sine wobble so the outline isn't a crisp rectangle. `worldmap::ground_color` bakes this
/// straight into the terrain vertex colour (same as the gate approach-roads), so the packed-earth
/// yard is **the same surface as the ground** — no raised slab laid on top. (Pre-walls only; raising
/// the walls paves the SAME network in cobble geometry — see `build`.)
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

/// The three gates (spec v2 §5). The east wall has none.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Gate {
    /// Main gate — the King's Road west to the bay (later a portcullis).
    West,
    /// The attacked gate, under the bell tower — the orcs come from the south (later a barbican).
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
    /// Yaw of the gate structure (its local X runs along the wall).
    fn yaw(self) -> f32 {
        if self == Gate::West { HALF_PI } else { 0.0 }
    }
}

/// Wall runs `(cx, cz, yaw, length)`: each side corner to corner, split around its gate (the east
/// side is one solid run).
fn wall_segments() -> Vec<(f32, f32, f32, f32)> {
    let g = GATE_GAP / 2.0;
    let mut v = Vec::new();
    for (z, gx) in [(-HALF_Z, N_GATE_X), (HALF_Z, S_GATE_X)] {
        for (a, b) in [(-HALF_X, gx - g), (gx + g, HALF_X)] {
            v.push(((a + b) / 2.0, z, 0.0, b - a));
        }
    }
    for (a, b) in [(-HALF_Z, W_GATE_Z - g), (W_GATE_Z + g, HALF_Z)] {
        v.push((-HALF_X, (a + b) / 2.0, HALF_PI, b - a));
    }
    v.push((HALF_X, 0.0, HALF_PI, HALF_Z * 2.0)); // the solid east wall
    v
}
fn gates() -> [(f32, f32, f32); 3] {
    Gate::ALL.map(|g| (g.center().x, g.center().y, g.yaw()))
}
fn towers() -> [(f32, f32); 4] {
    [(-HALF_X, -HALF_Z), (HALF_X, -HALF_Z), (HALF_X, HALF_Z), (-HALF_X, HALF_Z)]
}
/// Twelve dwelling slots ALONG THE WALLS (spec v2 §2 — the middle stays open): the south row
/// either side of the south gate and the bell tower, then the west and east flanks. Clear of the
/// keep, the reserved plots ([`TOWN_PLOTS`]), the market and every gate lane. The first
/// `town.houses` reveal in order.
fn houses() -> [(f32, f32); 12] {
    let sz = HALF_Z - 3.2; // the south row, backs to the wall
    let ex = HALF_X - 3.2; // the west / east flanks
    [
        (-HALF_X * 0.36, sz), (HALF_X * 0.29, sz), (-HALF_X * 0.57, sz), (HALF_X * 0.5, sz),
        (-HALF_X * 0.79, sz), (HALF_X * 0.71, sz),
        (-ex, HALF_Z * 0.43), (ex, HALF_Z * 0.24), (-ex, HALF_Z * 0.67), (ex, HALF_Z * 0.52),
        (-ex, -HALF_Z * 0.59), (ex, -HALF_Z * 0.55),
    ]
}

/// A reserved plot inside (or just outside) the walls: interim primitive placeholder + blocker
/// until the town kit (`town_kit.glb`, spec v2 phase 3d) replaces it. `half` is in world axes.
#[derive(Clone, Copy, Debug)]
pub(crate) struct TownPlot {
    pub(crate) name: &'static str,
    pub(crate) pos: Vec2,
    pub(crate) half: Vec2,
}

const fn plot(name: &'static str, x: f32, z: f32, hx: f32, hz: f32) -> TownPlot {
    TownPlot { name, pos: Vec2::new(x, z), half: Vec2::new(hx, hz) }
}

/// The zones of spec v2 §2 inside the walls: the north band (smithy + carpenter, barracks, the
/// granary on stilts, Maud's house + edict board), the west side (the tavern above the market), the
/// east side (infirmary + herb garden), and the fire pit + well at the courtyard's north edge.
pub(crate) const TOWN_PLOTS: [TownPlot; 9] = [
    plot("smithy", -HALF_X + 6.5, -HALF_Z + 4.0, 3.0, 2.5),
    plot("barracks", -HALF_X * 0.41, -HALF_Z + 3.5, 4.0, 1.75),
    plot("granary", HALF_X * 0.5, -HALF_Z + 4.0, 3.0, 2.0),
    plot("maud_house", HALF_X - 5.5, -HALF_Z + 4.5, 2.5, 2.0),
    plot("tavern", -HALF_X + 6.5, -HALF_Z * 0.36, 3.0, 2.5),
    plot("infirmary", HALF_X - 5.5, -HALF_Z * 0.33, 3.0, 2.0),
    plot("herb_garden", HALF_X - 5.5, -HALF_Z * 0.33 + 4.5, 2.2, 1.5),
    plot("fire_pit", -5.5, KEEP_FRONT + 2.8, 0.8, 0.8),
    plot("well", 5.5, KEEP_FRONT + 2.8, 0.6, 0.6),
];

/// OUTSIDE the west gate, by the King's Road (spec v2 §4): the Crown depot, the Crown gallows and
/// the empty grave of "Wat's drowned squire" by the road from the bay.
pub(crate) const OUTER_PLOTS: [TownPlot; 3] = [
    plot("crown_depot", -HALF_X - 10.0, W_GATE_Z - 8.0, 3.0, 2.5),
    plot("gallows", -HALF_X - 9.0, W_GATE_Z + 7.5, 1.3, 1.0),
    plot("empty_grave", -HALF_X - 16.0, W_GATE_Z + 4.0, 1.1, 0.7),
];

/// A reserved plot by name (inside or outside the walls).
pub(crate) fn town_plot(name: &str) -> Option<TownPlot> {
    TOWN_PLOTS.iter().chain(OUTER_PLOTS.iter()).find(|p| p.name == name).copied()
}

/// Centre of the market square just inside the west gate (spec v2 §2: "W brama ══ RYNEK").
pub(crate) const MARKET_CENTRE: Vec2 = Vec2::new(-HALF_X + 9.0, W_GATE_Z);

/// The work-yard props `(x, z, yaw)`: the wood yard by the smithy, hay by the granary, the
/// hand-cart by the west houses.
pub(crate) const WOOD_YARD: (f32, f32, f32) = (-HALF_X * 0.59, -HALF_Z * 0.55, 0.6);
pub(crate) const HAY_CORNER: (f32, f32, f32) = (HALF_X * 0.59, -HALF_Z * 0.55, -0.5);
pub(crate) const CART_CORNER: (f32, f32, f32) = (-HALF_X * 0.52, HALF_Z * 0.38, 2.3);

/// World-XZ of the dwelling slot the NEXT house will occupy (`houses()[built]`), or `None`
/// once all twelve stand. The on-site "Raise house" interaction + its pad anchor here, so a
/// new home always rises exactly where the player chose to build it (`sync_castle` reveals
/// the mesh at this same slot when `town.houses` increments).
pub(crate) fn next_house_site(built: u32) -> Option<Vec2> {
    houses().get(built as usize).map(|&(x, z)| Vec2::new(x, z))
}

/// True inside the castle footprint (+ margin) — scatter is cleared here.
pub fn in_footprint(wx: f32, wz: f32) -> bool {
    wx.abs() <= HALF_X + 1.6 && wz.abs() <= HALF_Z + 1.6
}

/// Courtyard half-extents (the wall perimeter) — for placing town villagers inside.
pub fn courtyard_half() -> (f32, f32) {
    (HALF_X, HALF_Z)
}

/// True strictly INSIDE the wall ring (wall thickness excluded). Siege rule: an invader only
/// batters the keep from in here — outside, the walls shield it, so the wall ring is a real
/// obstacle (thread a gate or do nothing), never a spot to chip the keep from.
pub fn in_courtyard(wx: f32, wz: f32) -> bool {
    wx.abs() < HALF_X - WALL_THICK && wz.abs() < HALF_Z - WALL_THICK
}

/// The keep's footprint half-extents (body, without the plinth) — for props that dress its walls.
/// World Y of the keep's flat roof (the body top) — where the keep-roof archers stand.
/// The healing shrine (castle_decor, Bulwark upgrade) by the infirmary on the east side — and the
/// centre of its heal aura (`defenses::shrine_heal`).
pub(crate) const SHRINE_POS: Vec2 = Vec2::new(HALF_X * 0.6, -HALF_Z * 0.12);

pub(crate) const KEEP_ROOF_Y: f32 = (KEEP_FOUND + KEEP_H) * KEEP_SCALE.y;
/// World Y of a corner tower's fighting top — the tower defenders' muzzle height.
pub(crate) const TOWER_TOP: f32 = TOWER_H * TOWER_SCALE.y;

pub(crate) const KEEP_HALF: Vec2 = Vec2::new(KEEP_W * KEEP_SCALE.x / 2.0, KEEP_D * KEEP_SCALE.z / 2.0);

/// The keep steps — the gather spot / muster mark just in front of the keep door.
pub(crate) const KEEP_STEPS: Vec2 = Vec2::new(KEEP_POS.x, KEEP_FRONT + 1.6);

/// The wandering merchant's roofed shop (`villagers::shop_parts`), on the market's north side,
/// its open front facing south onto the west lane; `interaction::shop_anchor` browses here.
pub(crate) const MERCHANT_SHOP: Vec2 = Vec2::new(MARKET_CENTRE.x + 4.8, W_GATE_Z - 4.4);

/// Where the hero stands to ring the bell: inside the yard at the bell tower's door.
pub(crate) const BELL_ROPE: Vec2 = Vec2::new(BELL_POS.x, BELL_POS.y - BELL_TOWER_HALF - 0.9);

/// True in the OPEN yard in front of the keep (the courtyard plus a ring round the keep itself)
/// — where nothing stands between an invader and the keep, so it may press it in a straight line.
pub fn in_keep_yard(wx: f32, wz: f32) -> bool {
    let (cx, cz, hx, hz) = COURTYARD;
    ((wx - cx).abs() <= hx && (wz - cz).abs() <= hz + 0.6) || Vec2::new(wx, wz).distance(KEEP_POS) < 8.0
}

fn snap_cardinal(a: f32) -> f32 {
    (a / HALF_PI).round() * HALF_PI
}
fn face_center(wx: f32, wz: f32) -> f32 {
    snap_cardinal((-wx).atan2(-wz))
}
/// Yaw for a building at `(wx, wz)`: inside the walls it turns its back to the NEAREST wall and its
/// front to the yard (houses and plots line the walls, spec v2 §2); outside it faces the castle.
fn face_yard(wx: f32, wz: f32) -> f32 {
    let (dx, dz) = (HALF_X - wx.abs(), HALF_Z - wz.abs());
    if dx <= 0.0 || dz <= 0.0 {
        return face_center(wx, wz);
    }
    if dz < dx {
        if wz > 0.0 { std::f32::consts::PI } else { 0.0 }
    } else if wx > 0.0 {
        -HALF_PI
    } else {
        HALF_PI
    }
}

// ── Build ────────────────────────────────────────────────────────────────────────
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
    // Each part is tagged with the upgrade that reveals it (`CastleKind`); gated parts start
    // hidden so the castle BUILDS UP as you buy (a deliberate change from the old always-full
    // render). `Always` parts (keep core, courtyard, bell, keep-door torches) show from the start.
    let mut spawn = |parts: Vec<(Mesh, M)>, pos: Vec3, rot: f32, scale: Vec3, kind: CastleKind| {
        // `Always` and `PreWalls` are present on a fresh, wall-less keep; the rest start hidden and
        // `sync_castle` reveals them as you buy upgrades (and flips PreWalls off once Walls go up).
        let vis = if matches!(kind, CastleKind::Always | CastleKind::PreWalls) {
            Visibility::Inherited
        } else {
            Visibility::Hidden
        };
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
            ))
            // Masonry + roofs are solid to the follow camera's boom (walls, towers, keep, gate posts,
            // houses); wood/beam/metal/cloth/paving parts (braziers, lintel, props) are not.
            .insert_if(crate::player::CameraOccluder, || matches!(slot, M::Stone | M::DarkStone | M::LightStone | M::HouseStone | M::Plaster | M::Roof | M::HouseRoof | M::HouseRoof2 | M::Thatch));
        }
    };

    // Ground: NOT one big sheet — that read as a repeating carpet wall-to-wall. Instead a worn
    // route network: a plaza under the keep + bell + muster yard, and four paths running to the
    // gates, with the courtyard lawn showing everywhere between. Day one the routes are trodden
    // packed earth (the feet of the settlement wrote them); raising the Palisade Walls paves the
    // SAME network in cobble — paving as progression. The pre-walls **packed earth is NOT geometry**:
    // it's baked into the terrain ground colour (`castle::yard_strength` → `worldmap::ground_color`),
    // so it's the same surface as the lawn, not a slab laid on top. Only the cobble paving is a
    // raised `worn_slab` (a genuine built pavement), sitting 1.5cm above the ground; its frayed rim
    // overlaps at the junctions sit slightly higher so they can't z-fight.
    // Map-centre rework (`castle_ground`): the walls no longer pave the WHOLE route network — a
    // pale cobble cross wall-to-wall read as a carpet. Cobble goes only where traffic is heaviest
    // (the keep apron + the four gate passages); the lanes between stay trodden mud with wheel
    // ruts and puddles, baked into the terrain masks.
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

    // Keep (centre) — always present, then two grandeur tiers that reveal as you fortify (corner
    // turrets with the Walls, the grand spire + banners with the Reinforced Keep). Same transform as
    // the keep so the parts sit exactly on it.
    let keep_at = Vec3::new(KEEP_POS.x, 0.0, KEEP_POS.y);
    spawn(keep_parts(), keep_at, 0.0, KEEP_SCALE, CastleKind::Always);
    spawn(keep_tier1_parts(), keep_at, 0.0, KEEP_SCALE, CastleKind::KeepTier1);
    spawn(keep_tier2_parts(), keep_at, 0.0, KEEP_SCALE, CastleKind::KeepTier2);
    for (x, z, rot, len) in wall_segments() {
        spawn(wall_parts(len), Vec3::new(x, 0.0, z), rot, Vec3::ONE, CastleKind::Walls);
    }
    for (x, z) in towers() {
        spawn(tower_parts(), Vec3::new(x, 0.0, z), 0.0, TOWER_SCALE, CastleKind::Towers);
    }
    for (x, z, rot) in gates() {
        spawn(gate_parts(GATE_GAP), Vec3::new(x, 0.0, z), rot, Vec3::ONE, CastleKind::Gate);
    }
    for (i, (x, z)) in houses().into_iter().enumerate() {
        spawn(house_parts_for(i), Vec3::new(x, 0.0, z), face_yard(x, z), HOUSE_SCALE, CastleKind::House(i as u8));
    }
    spawn(bell_frame_parts(), Vec3::new(BELL_POS.x, 0.0, BELL_POS.y), BELL_YAW, Vec3::ONE, CastleKind::Always);

    // Torches temporarily removed (read as unnatural) — only the war-braziers light the gates for now.
    for gate in Gate::ALL {
        for p in brazier_spots(gate) {
            spawn(brazier_parts(), p, 0.0, Vec3::ONE, CastleKind::Gate);
        }
    }
    // The settlement's working corners: woodpile, hay store, cart. Permanent (`Always`) — the
    // courtyard never goes blank, walls or no walls. Beside the smithy / the granary / the west
    // houses, OFF the open courtyard (spec v2 §2).
    for (parts, (x, z, yaw)) in [
        (wood_yard_parts(), WOOD_YARD),
        (hay_corner_parts(), HAY_CORNER),
        (cart_corner_parts(), CART_CORNER),
    ] {
        spawn(parts, Vec3::new(x, 0.0, z), yaw, Vec3::ONE, CastleKind::Always);
    }
    // The reserved plots (spec v2 §2/§4) as interim primitive placeholders.
    for tp in TOWN_PLOTS.iter().chain(OUTER_PLOTS.iter()) {
        let (parts, yaw) = plot_parts(tp);
        spawn(parts, Vec3::new(tp.pos.x, 0.0, tp.pos.y), yaw, Vec3::ONE, CastleKind::Always);
    }

    // The bell's live swinging half (bronze + clapper/rope) — separate hinged entities, after the
    // last `spawn` closure call so the `commands`/`meshes` borrows are free again.
    spawn_bell_swing(commands, meshes, &mats);

    // Pooled flicker-lights — only the war-braziers remain (gate/keep torches removed for now).
    for gate in Gate::ALL {
        let (x, z) = (gate.center().x, gate.center().y);
        // The war-braziers' pools (same gate lifecycle; flame local y = 1.5).
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
    // Curfew shutters over each house's front window — a wooden pair that swings shut as night
    // falls (`shutters::drive_shutters`), so the lit town visibly buttons up before the siege (and
    // a closed leaf hides the glowing pane, reading as "lamp out"). Built here, after the `spawn`
    // closure releases `commands`; tagged per-house so each pair reveals with its dwelling. The two
    // mirrored leaf meshes are baked at world size and shared across all houses.
    let shutter_right = meshes.add(bx(0.20, 0.36, 0.03, -0.10, 0.0, 0.0));
    let shutter_left = meshes.add(bx(0.20, 0.36, 0.03, 0.10, 0.0, 0.0));
    for (i, (hx, hz)) in houses().into_iter().enumerate() {
        crate::shutters::spawn_house_shutters(
            commands,
            &shutter_right,
            &shutter_left,
            mats.get(M::Wood),
            hx,
            hz,
            face_yard(hx, hz),
            CastleKind::House(i as u8),
            house_window(HOUSE_STYLES[i]),
        );
    }

    // Cloth flags (banner.rs) on the poles the merged geometry left bare: the keep spire's
    // pennant (always shown) and each wall tower's flag (revealed with the Towers upgrade —
    // `sync_castle` drives their visibility via the same `CastlePart` tag as the towers).
    // Attach heights are the static flags' old local positions × the structures' Y scales.
    let keep_flag = crate::banner::spawn_flag(
        commands, meshes, std_mats,
        Vec3::new(KEEP_POS.x, 4.88 * KEEP_SCALE.y, KEEP_POS.y), 0.85, 0.42, BANNER, Some(0xd9b34a),
    );
    commands
        .entity(keep_flag)
        .insert((CastlePart { kind: CastleKind::Always }, BiomeEntity));
    for (x, z) in towers() {
        let flag = crate::banner::spawn_flag(
            commands, meshes, std_mats,
            Vec3::new(x, (TOWER_H + 2.25) * TOWER_SCALE.y, z), 0.68, 0.36, BANNER, None,
        );
        commands.entity(flag).insert((
            CastlePart { kind: CastleKind::Towers },
            Visibility::Hidden,
            BiomeEntity,
        ));
    }

    // Grass tufts + clover round the courtyard rim and scattered through the lawn (off the
    // paving) — the courtyard floor is living ground now, not a stamped sheet. Permanent.
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
        // Rim band: walk the yard perimeter, jittering across the fray band; skip the four
        // gate lanes (the approach roads keep their trodden-bare mouths).
        let (bx_, bz_) = (HALF_X - 1.2, HALF_Z - 1.2);
        for i in 0..64 {
            let t = i as f32 / 64.0;
            let p = t * 2.0 * (bx_ + bz_); // half-perimeter parameter (mirrored to ±)
            let (mut x, mut z) = if p < bx_ * 2.0 { (p - bx_, bz_) } else { (bx_, p - bx_ * 2.0 - bz_) };
            if r.f() < 0.5 { x = -x; }
            if r.f() < 0.5 { z = -z; }
            x += (r.f() - 0.5) * 3.4;
            z += (r.f() - 0.5) * 3.4;
            let near_gate = Gate::ALL.iter().any(|g| g.center().distance(Vec2::new(x, z)) < 3.6);
            if near_gate || !plot_clear(x, z, 0.4) {
                continue;
            }
            let mesh = if r.f() < 0.55 { pick(&tufts, &mut r) } else { pick(&clovers, &mut r) };
            let s = 0.45 + r.f() * 0.45;
            sprig(x, z, mesh, s, &mut r, commands);
        }
        // Lawn patches inside the courtyard — small, sparse, low ("gdzie niegdzie"), and
        // never poking up through the plaza/path paving.
        for _ in 0..14 {
            let x = (r.f() - 0.5) * 2.0 * (bx_ - 2.0);
            let z = (r.f() - 0.5) * 2.0 * (bz_ - 2.0);
            if on_paving(x, z) || !plot_clear(x, z, 0.4) {
                continue;
            }
            let mesh = if r.f() < 0.35 { pick(&tufts, &mut r) } else { pick(&clovers, &mut r) };
            let s = 0.35 + r.f() * 0.3;
            sprig(x, z, mesh, s, &mut r, commands);
        }
    }

    // Chimney smoke above each house.
    let smoke_mat = std_mats.add(StandardMaterial {
        base_color: Color::srgba(0.62, 0.64, 0.67, 0.5),
        alpha_mode: AlphaMode::Blend,
        unlit: true,
        ..default()
    });
    let puff = meshes.add(Sphere::new(1.0).mesh().ico(1).unwrap());
    for (hi, (hx, hz)) in houses().into_iter().enumerate() {
        // Smoke rises from the archetype's own stack; huts have none (they vent through thatch).
        let Some((ch, ch_top)) = house_chimney(HOUSE_STYLES[hi]) else { continue };
        let rot = face_yard(hx, hz);
        let local = Quat::from_rotation_y(rot) * Vec3::new(ch.x * HOUSE_SCALE.x, 0.0, ch.y * HOUSE_SCALE.z);
        let (cx, cz) = (hx + local.x, hz + local.z);
        let base_y = ch_top * HOUSE_SCALE.y + 0.2;
        for i in 0..3 {
            commands.spawn((
                Mesh3d(puff.clone()),
                MeshMaterial3d(smoke_mat.clone()),
                Transform::from_translation(Vec3::new(cx, base_y, cz)).with_scale(Vec3::splat(0.01)),
                Smoke { x: cx, z: cz, base_y, phase: i as f32 / 3.0, speed: 0.3 },
                Visibility::Hidden, // follows its house's reveal
                CastlePart { kind: CastleKind::House(hi as u8) },
                BiomeEntity,
            ));
        }
    }

    // A few hens pecking in the dirt by the wood yard + well (one shared, batched mesh set; each is
    // a moving root parented to its parts, so `peck_hens` can bob the whole bird). Permanent — the
    // courtyard keeps its fowl whatever gets built.
    let hen_meshes: Vec<(Handle<Mesh>, M)> =
        hen_parts().into_iter().map(|(m, slot)| (meshes.add(m), slot)).collect();
    for (i, (hx, hz, yaw, sp)) in [
        (WOOD_YARD.0 + 0.6, WOOD_YARD.1 + 1.6, 0.7_f32, 1.6_f32),
        (WOOD_YARD.0 + 1.8, WOOD_YARD.1 + 0.9, 2.2, 1.9),
        (HAY_CORNER.0 - 0.5, HAY_CORNER.1 + 1.5, -1.1, 1.7),
        (HAY_CORNER.0 - 1.7, HAY_CORNER.1 + 0.8, 2.6, 2.2),
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

    // The always-present keep and work-yard props are solid from the start; gated structures
    // register their blockers when their upgrade reveals them (see `sync_castle`), so the
    // courtyard is open until you build the walls — no invisible barriers.
    register_keep_blocker();
    register_yard_blockers();
    register_plot_blockers();
    mats
}

/// The two war-brazier spots flanking a gate's APPROACH (outside the walls, clear of the gate
/// lane): the night siege's melee happens right here, and on the moon-dark ground it filmed as
/// black-on-black.
fn brazier_spots(gate: Gate) -> [Vec3; 2] {
    let (c, out) = (gate.center(), gate.outward());
    let perp = Vec2::new(-out.y, out.x);
    let half = GATE_GAP / 2.0 + 1.9;
    [-half, half].map(|s| {
        let p = c + out * (WALL_THICK / 2.0 + 2.6) + perp * s;
        Vec3::new(p.x, 0.0, p.y)
    })
}

/// Is `(x, z)` clear (by `margin`) of every reserved plot, inside and outside the walls?
pub(crate) fn plot_clear(x: f32, z: f32, margin: f32) -> bool {
    TOWN_PLOTS.iter().chain(OUTER_PLOTS.iter()).all(|p| {
        (x - p.pos.x).abs() > p.half.x + margin || (z - p.pos.y).abs() > p.half.y + margin
    })
}

/// A plot building facing the courtyard: (yaw, local width, local depth) for world half-extents
/// `half` — a quarter-turned building swaps its local width/depth.
fn plot_frame(tp: &TownPlot) -> (f32, f32, f32) {
    let yaw = face_yard(tp.pos.x, tp.pos.y);
    let turned = (yaw.abs() - HALF_PI).abs() < 0.1;
    let (w, d) = if turned { (tp.half.y * 2.0, tp.half.x * 2.0) } else { (tp.half.x * 2.0, tp.half.y * 2.0) };
    (yaw, w, d)
}

/// Interim placeholder geometry for a reserved plot (spec v2 §2/§4) — honest primitive massing at
/// the hero-relative scale (eaves ≈2.0u, doors ≈1.4u), so the layout and its sightlines can be
/// judged before the town kit lands. Local +Z faces the courtyard.
fn plot_parts(tp: &TownPlot) -> (Vec<(Mesh, M)>, f32) {
    let (yaw, w, d) = plot_frame(tp);
    let mut v: Vec<(Mesh, M)> = Vec::new();
    // A plain hall: stone footing, plaster/timber body to the eaves, door, gable roof.
    let hall = |v: &mut Vec<(Mesh, M)>, body: M, roof: M, eave: f32| {
        v.push((bx(w + 0.2, 0.25, d + 0.2, 0.0, 0.125, 0.0), M::HouseStone));
        v.push((bx(w, eave - 0.25, d, 0.0, 0.25 + (eave - 0.25) / 2.0, 0.0), body));
        for sx in [-1.0_f32, 1.0] {
            for sz in [-1.0_f32, 1.0] {
                v.push((bx(0.2, eave - 0.25, 0.2, sx * w / 2.0, 0.25 + (eave - 0.25) / 2.0, sz * d / 2.0), M::Beam));
            }
        }
        v.push((bx(0.8, 1.4, 0.08, 0.0, 0.25 + 0.7, d / 2.0 + 0.03), M::Wood)); // door ≈1.4u
        v.push((gable(w + 0.5, d + 0.5, (d * 0.42).max(1.2), eave), roof));
    };
    match tp.name {
        "granary" => {
            // On stilts (rats, damp): nine posts, a raised plank floor, a thatched store.
            for sx in [-1.0_f32, 0.0, 1.0] {
                for sz in [-1.0_f32, 0.0, 1.0] {
                    v.push((bx(0.22, 1.0, 0.22, sx * (w / 2.0 - 0.3), 0.5, sz * (d / 2.0 - 0.3)), M::Beam));
                    v.push((cyl(0.24, 0.08, sx * (w / 2.0 - 0.3), 1.0, sz * (d / 2.0 - 0.3)), M::HouseStone)); // rat stone
                }
            }
            v.push((bx(w, 0.15, d, 0.0, 1.1, 0.0), M::Wood));
            v.push((bx(w - 0.3, 1.6, d - 0.3, 0.0, 1.95, 0.0), M::Wood));
            v.push((bx(0.8, 1.3, 0.08, 0.0, 1.85, (d - 0.3) / 2.0 + 0.03), M::Beam));
            v.push((gable(w + 0.4, d + 0.4, 1.4, 2.75), M::Thatch));
            v.push((bake(bx(0.6, 0.08, 1.6, 0.0, 0.0, 0.0), Vec3::new(0.0, 0.55, d / 2.0 + 0.6), 0.0, Vec3::ONE)
                .rotated_by(Quat::IDENTITY), M::Beam)); // ladder-plank up to the door
        }
        "smithy" => {
            hall(&mut v, M::HouseStone, M::HouseRoof2, 2.2);
            v.push((bx(0.9, 3.0, 0.9, -w / 2.0 + 0.6, 1.5, -d / 2.0 + 0.6), M::DarkStone)); // forge chimney
            v.push((bx(0.7, 0.5, 0.4, w / 2.0 - 0.9, 0.5, d / 2.0 + 0.7), M::Iron)); // anvil
            v.push((cyl(0.25, 0.5, w / 2.0 - 0.9, 0.25, d / 2.0 + 0.7), M::Wood)); // anvil block
        }
        "barracks" => {
            hall(&mut v, M::Wood, M::HouseRoof, 2.2);
            for k in 0..4 {
                let x = -w / 2.0 + 0.8 + k as f32 * (w - 1.6) / 3.0;
                v.push((cyl(0.35, 0.06, x, 1.4, d / 2.0 + 0.06).rotated_by(Quat::IDENTITY), M::Banner)); // shields on the front
            }
        }
        "tavern" => {
            hall(&mut v, M::Plaster, M::HouseRoof, 2.4);
            v.push((bx(0.08, 1.2, 0.08, w / 2.0 - 0.3, 3.0, d / 2.0 + 0.5), M::Beam)); // sign post
            v.push((bx(0.7, 0.5, 0.05, w / 2.0 - 0.3, 3.3, d / 2.0 + 0.5), M::Wood)); // sign board
        }
        "maud_house" => {
            hall(&mut v, M::Plaster, M::HouseRoof2, 2.2);
            // The edict board in front, on two posts.
            for sx in [-0.7_f32, 0.7] {
                v.push((bx(0.12, 1.9, 0.12, sx, 0.95, d / 2.0 + 1.3), M::Beam));
            }
            v.push((bx(1.6, 1.0, 0.08, 0.0, 1.45, d / 2.0 + 1.36), M::Wood));
            for (px, py) in [(-0.4_f32, 1.55_f32), (0.15, 1.35), (0.5, 1.6)] {
                v.push((bx(0.32, 0.4, 0.02, px, py, d / 2.0 + 1.41), M::Parchment));
            }
        }
        "infirmary" => hall(&mut v, M::Plaster, M::Thatch, 2.1),
        "herb_garden" => {
            v.push((bx(w, 0.12, d, 0.0, 0.06, 0.0), M::Soil));
            for k in 0..4 {
                let x = -w / 2.0 + 0.45 + k as f32 * (w - 0.9) / 3.0;
                v.push((bx(0.3, 0.22, d - 0.4, x, 0.17, 0.0), M::Crop));
            }
            for sz in [-1.0_f32, 1.0] {
                v.push((bx(w + 0.2, 0.06, 0.06, 0.0, 0.5, sz * (d / 2.0 + 0.1)), M::Beam)); // wattle rails
            }
        }
        "fire_pit" => {
            for k in 0..9 {
                let a = k as f32 / 9.0 * std::f32::consts::TAU;
                v.push((bx(0.3, 0.22, 0.24, a.cos() * 0.62, 0.11, a.sin() * 0.62), M::DarkStone));
            }
            v.push((cyl(0.5, 0.04, 0.0, 0.02, 0.0), M::Slit)); // ash bed
            for a in [0.3_f32, 1.4, 2.5] {
                v.push((bake(bx(0.9, 0.12, 0.12, 0.0, 0.0, 0.0), Vec3::new(0.0, 0.12, 0.0), a, Vec3::ONE), M::Beam));
            }
            for sx in [-1.0_f32, 1.0] {
                v.push((bx(1.6, 0.3, 0.35, 0.0, 0.15, sx * 1.4), M::Wood)); // log benches
            }
        }
        "well" => v.extend(well_parts()),
        "crown_depot" => {
            // The Crown's store: a crimson-roofed shed, painted crates stacked before it.
            hall(&mut v, M::Wood, M::Roof, 2.0);
            for (cx, cy, cz) in [(-0.9_f32, 0.3_f32, d / 2.0 + 0.6), (-0.3, 0.3, d / 2.0 + 0.7), (-0.6, 0.85, d / 2.0 + 0.65), (0.8, 0.3, d / 2.0 + 0.6)] {
                v.push((bx(0.55, 0.55, 0.55, cx, cy, cz), M::Roof));
            }
        }
        "gallows" => {
            v.push((bx(2.2, 0.3, 1.6, 0.0, 0.6, 0.0), M::Wood)); // platform
            for sx in [-0.9_f32, 0.9] {
                v.push((bx(0.3, 0.6, 1.3, sx, 0.3, 0.0), M::Beam));
            }
            v.push((bx(0.2, 3.0, 0.2, -0.8, 2.0, 0.0), M::Beam)); // upright
            v.push((bx(1.8, 0.18, 0.18, 0.05, 3.4, 0.0), M::Beam)); // crossbeam
            v.push((cyl(0.025, 0.8, 0.7, 2.95, 0.0), M::Straw)); // rope
        }
        "empty_grave" => {
            // The empty grave: an open pit, its spoil heaped beside, a plain cross — no body.
            v.push((bx(1.0, 0.04, 2.0, -0.4, 0.01, 0.0), M::Slit)); // the dark pit mouth
            v.push((bx(0.7, 0.35, 1.8, 0.55, 0.17, 0.0), M::Soil)); // spoil heap
            v.push((bx(0.1, 1.2, 0.1, -0.4, 0.6, -1.15), M::Beam)); // cross
            v.push((bx(0.6, 0.1, 0.1, -0.4, 0.85, -1.15), M::Beam));
        }
        _ => hall(&mut v, M::Plaster, M::HouseRoof, 2.0),
    }
    (v, yaw)
}

/// Every reserved plot is solid from the start (open plots — garden, fire pit — only at their
/// fixtures).
fn register_plot_blockers() {
    let p = COLLISION_PAD;
    for tp in TOWN_PLOTS.iter().chain(OUTER_PLOTS.iter()) {
        let (hx, hz) = match tp.name {
            "herb_garden" | "fire_pit" | "empty_grave" => continue,
            "well" => (0.55 + p, 0.55 + p),
            _ => (tp.half.x + p, tp.half.y + p),
        };
        crate::blockers::add_box(tp.pos.x, tp.pos.y, hx, hz);
    }
    // The bell tower stands from the start (old-colony stone).
    crate::blockers::add_box(BELL_POS.x, BELL_POS.y, BELL_TOWER_HALF + 0.25 + p, BELL_TOWER_HALF + 0.25 + p);
}

/// Player-body margin so movers stop just shy of a face instead of clipping into it.
const COLLISION_PAD: f32 = 0.12;

/// The keep is solid from the start.
fn register_keep_blocker() {
    let p = COLLISION_PAD;
    crate::blockers::add_box(KEEP_POS.x, KEEP_POS.y, KEEP_W * KEEP_SCALE.x / 2.0 + p, KEEP_D * KEEP_SCALE.z / 2.0 + p);
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
    part(wood, 0.6, 0.0, 0.0, 0.30, 0.30); // chopping block
    part(wood, 0.6, 0.0, -0.9, 0.75, 0.37); // stacked logs

    let hay = Vec2::new(HAY_CORNER.0, HAY_CORNER.1);
    part(hay, -0.5, 0.0, 0.025, 0.71, 0.315); // bales and binding ropes
    for (x, z) in [(0.72, 0.24), (0.8, -0.22)] {
        part(hay, -0.5, x, z, 0.20, 0.20);
    }

    let cart = Vec2::new(CART_CORNER.0, CART_CORNER.1);
    part(cart, 2.3, 0.0, 0.0, 0.65, 0.44); // bed, rails and wheels
    for z in [-0.28, 0.28] {
        part(cart, 2.3, 0.85, z, 0.45, 0.03); // handle shafts
    }
    for (x, z) in [(0.95, -0.6), (1.2, -0.35)] {
        part(cart, 2.3, x, z, 0.31, 0.31); // barrels and hoops
    }
}

/// Perimeter wall blockers — one box per segment (registered when Walls is built).
pub(crate) fn register_walls_blockers() {
    let p = COLLISION_PAD;
    for (x, z, rot, len) in wall_segments() {
        let along = len / 2.0;
        let across = WALL_THICK / 2.0 + p;
        let (hw, hd) = if rot.abs() < 0.1 { (along, across) } else { (across, along) };
        crate::blockers::add_box(x, z, hw, hd);
    }
}

/// Corner-tower blockers (registered when Towers is built).
fn register_towers_blockers() {
    let p = COLLISION_PAD;
    for (x, z) in towers() {
        crate::blockers::add_box(x, z, 0.9 * TOWER_SCALE.x + p, 0.9 * TOWER_SCALE.z + p);
    }
}

/// One house's blocker (registered when that district is built) — sized to its archetype.
fn register_house_blocker(i: usize) {
    let p = COLLISION_PAD;
    let (x, z) = houses()[i];
    let (w, d) = house_dims(HOUSE_STYLES[i]);
    let (hx, hz) = (w * HOUSE_SCALE.x / 2.0 + p, d * HOUSE_SCALE.z / 2.0 + p);
    let (hw, hd) = if (face_yard(x, z).abs() - HALF_PI).abs() < 0.1 { (hz, hx) } else { (hx, hz) };
    crate::blockers::add_box(x, z, hw, hd);
}

/// Drop the lazily-registered wall / tower / house collision boxes by their centres (the keep box
/// stays — it's permanent). Pairs with resetting [`CastleBuilt`] so `sync_castle` re-registers the
/// boxes the loaded run actually earns. The eps is loose enough to catch each box's centre but far
/// below the spacing between distinct boxes, so it leaves the keep (origin) and the town/rival plots
/// (≥10 units out) untouched.
fn clear_castle_blockers() {
    for (x, z, _, _) in wall_segments() {
        crate::blockers::remove_box_near(x, z, 0.4);
    }
    for (x, z) in towers() {
        crate::blockers::remove_box_near(x, z, 0.4);
    }
    for (x, z) in houses() {
        crate::blockers::remove_box_near(x, z, 0.4);
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

/// Which upgrade reveals a given castle part (the castle builds up instead of starting full).
#[derive(Clone, Copy, PartialEq, Eq)]
pub enum CastleKind {
    Always,
    /// Shown ONLY before the Palisade Walls go up — the trodden packed-earth route network of the
    /// young settlement. Buying Walls hides it (the same routes re-appear paved in cobble).
    PreWalls,
    Walls,
    Gate,
    Towers,
    House(u8),
    /// Keep grandeur tier 1 (corner turrets) — revealed when the Palisade Walls go up, so the keep
    /// visibly fortifies alongside its castle. See [`keep_tier1_parts`].
    KeepTier1,
    /// Keep grandeur tier 2 (grand spire + banners + gilding) — revealed when Reinforced Keep is
    /// bought. See [`keep_tier2_parts`].
    KeepTier2,
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
    towers: bool,
    houses: [bool; 12],
}

/// Reveal castle parts and lazily register each group's collision the first time it appears.
/// Walls/towers/gate gate on the Defense-branch upgrades (the keep fortifies as you invest); the
/// 8 interior **houses** are the town's dwellings — the first `town.houses` of them show, so the
/// settlement visibly grows as you build homes (start 2 → 4 peasants). The farm is gone (food is a
/// flow now; producers live out on the town plots).
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
        let show = match part.kind {
            CastleKind::Always => true,
            CastleKind::PreWalls => !def.walls, // the bare-yard look gives way to the cobbled courtyard
            CastleKind::Walls => def.walls,
            CastleKind::Gate => def.walls && def.gate, // a gate without walls would float
            CastleKind::Towers => def.towers,
            CastleKind::House(i) => (i as u32) < houses,
            // The keep grades up as you fortify: corner turrets with the Walls, the grand spire +
            // banners with the Reinforced Keep upgrade.
            CastleKind::KeepTier1 => def.walls,
            CastleKind::KeepTier2 => def.reinforced,
        };
        if live && show && *vis == Visibility::Hidden {
            if let Some(crate::build_fx::RevealAt(pos)) = at {
                let pop = crate::build_fx::BuildPop::rise();
                tf.scale = pop.scale0(); // same-frame, so the part never flashes full-size
                commands.entity(e).try_insert(pop);
                // One burst per structure, not per material part (a house is ~4 entities).
                if !dust.iter().any(|p| p.distance_squared(*pos) < 1.0) {
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

    #[test]
    fn yard_props_are_solid_without_closing_gate_lanes() {
        let _guard = crate::blockers::TEST_LOCK.lock().unwrap();
        crate::blockers::reset();
        register_yard_blockers();
        register_plot_blockers();
        for (x, z, _) in [WOOD_YARD, HAY_CORNER, CART_CORNER] {
            assert!(crate::blockers::is_blocked(x, z), "work-yard prop at ({x}, {z}) must be solid");
        }
        let logs = Vec3::new(WOOD_YARD.0, 0.0, WOOD_YARD.1)
            + Quat::from_rotation_y(WOOD_YARD.2) * Vec3::new(0.6, 0.0, -0.9);
        assert!(crate::blockers::is_blocked(logs.x, logs.z), "rotated log pile must be solid");
        let barrel = Vec3::new(CART_CORNER.0, 0.0, CART_CORNER.1)
            + Quat::from_rotation_y(CART_CORNER.2) * Vec3::new(1.2, 0.0, -0.35);
        assert!(crate::blockers::is_blocked(barrel.x, barrel.z), "offset cart barrel must be solid");
        // Every gate lane stays open from the gate to the courtyard.
        for g in Gate::ALL {
            for k in 1..8 {
                let p = g.center() - g.outward() * k as f32;
                assert!(!crate::blockers::any_within(p.x, p.y, 0.35), "{g:?} lane at {p} must stay clear");
            }
        }
        crate::blockers::reset();
    }

    /// Spec v2 §2: a ≥24×16u open courtyard between the keep and the south gate — no plot, house,
    /// yard prop, bell tower or keep inside it (the fire pit + well sit at its north edge).
    #[test]
    fn courtyard_stays_open() {
        let (cx, cz, hx, hz) = COURTYARD;
        assert!(hx * 2.0 >= 24.0 && hz * 2.0 >= 16.0, "courtyard {}x{} too small", hx * 2.0, hz * 2.0);
        let inside = |x: f32, z: f32, r: f32| (x - cx).abs() < hx - r && (z - cz).abs() < hz - r;
        for (x, z) in houses() {
            assert!(!inside(x, z, -2.0), "house at ({x},{z}) intrudes on the courtyard");
        }
        for tp in TOWN_PLOTS.iter().filter(|p| !matches!(p.name, "fire_pit" | "well")) {
            assert!(!inside(tp.pos.x, tp.pos.y, -tp.half.max_element()), "{} intrudes on the courtyard", tp.name);
        }
        for (x, z, _) in [WOOD_YARD, HAY_CORNER, CART_CORNER] {
            assert!(!inside(x, z, -1.5), "yard prop at ({x},{z}) intrudes on the courtyard");
        }
        assert!(!inside(BELL_POS.x, BELL_POS.y, -BELL_TOWER_HALF));
        assert!(KEEP_FRONT < cz - hz, "the keep must sit north of the courtyard");
        // Houses and plots never overlap each other or the walls.
        let mut boxes: Vec<(&str, Vec2, Vec2)> = TOWN_PLOTS.iter().map(|p| (p.name, p.pos, p.half)).collect();
        for (i, (x, z)) in houses().into_iter().enumerate() {
            let (w, d) = house_dims(HOUSE_STYLES[i]);
            let (a, b) = (w * HOUSE_SCALE.x / 2.0, d * HOUSE_SCALE.z / 2.0);
            let half = if (face_yard(x, z).abs() - HALF_PI).abs() < 0.1 { Vec2::new(b, a) } else { Vec2::new(a, b) };
            assert!(x.abs() + half.x < HALF_X - WALL_THICK / 2.0 && z.abs() + half.y < HALF_Z - WALL_THICK / 2.0, "house {i} in the wall");
            boxes.push(("house", Vec2::new(x, z), half));
        }
        for i in 0..boxes.len() {
            for j in i + 1..boxes.len() {
                let (n1, p1, h1) = boxes[i];
                let (n2, p2, h2) = boxes[j];
                let gap = (p1 - p2).abs() - h1 - h2;
                assert!(gap.x > 0.1 || gap.y > 0.1, "{n1} at {p1} overlaps {n2} at {p2}");
            }
        }
    }
}
