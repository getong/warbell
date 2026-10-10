//! Realistic water material + the river-centerline placement queries.
//!
//! ONE `ExtendedMaterial<StandardMaterial, WaterExt>` draws every water surface on the island —
//! the sea, the four rivers, the lake + its brooks and the swamp bog pools are all the single
//! `SEA_Y` plane showing through the carved terrain. Its FRAGMENT shader
//! (`assets/shaders/water.wgsl`) is a single-pass, physically-plausible water model:
//!
//! - **Normals** from a procedural tileable *slope* map ([`ripple_map`], baked here at startup —
//!   no texture download) sampled in 2–3 scrolling layers; river layers are **flow-mapped** along
//!   the baked river direction, still water just drifts. The map's mips carry each texel's slope
//!   VARIANCE so distant water widens its sun highlight into a glitter path instead of aliasing.
//! - **Body colour** by Beer–Lambert absorption over a *synthesised* depth: the terrain has no
//!   underwater geometry (cliff walls stop at the waterline), so prepass depth can't measure
//!   shallowness — the baked distance-to-bank field (`worldmap::bake_water_field`) stands in for
//!   it. Clear near the banks (silty bed showing through) → teal/green-brown in depth; swamp pools
//!   are tannin-dark.
//! - **Reflection** is Bevy's own PBR Fresnel (F0 ≈ 0.02) of the scene's environment map + GGX sun
//!   / moon glints. A cheap two-tap march of the bank field along the reflected ray occludes the
//!   sky where the far bank would be mirrored — the dark treeline band every real lake has.
//!
//! The material is OPAQUE (it was alpha-blended): nothing exists under the plane to show through,
//! and blending hid the water from the depth prepass — so the DoF blurred it as sky, the
//! atmospherics haze skipped it and the outline pass traced every bank. Opaque water is in the
//! prepass, so all of those now treat it as the surface it is, and it costs no blending.
//! `WaterPlugin` only registers the material; `worldmap` builds the plane and bakes the field.
//!
//! Exposes [`on_river`] / [`river_bank_t`] — the sine-centerline queries
//! the scatter (and the kept `decor` charm) use to keep props out of the water + dress banks.

use std::sync::Mutex;

use bevy::asset::RenderAssetUsages;
use bevy::image::{ImageAddressMode, ImageFilterMode, ImageSampler, ImageSamplerDescriptor};
use bevy::pbr::{ExtendedMaterial, MaterialExtension, MaterialPlugin};
use bevy::prelude::*;
use bevy::render::render_resource::{AsBindGroup, Extent3d, ShaderType, TextureDimension, TextureFormat};
use bevy::shader::ShaderRef;

// ── River geometry constants (shared by the on_river / river_bank_t helpers) ──

/// Sideways swing amplitude of the centerline (world units): `x = AMP * sin(z*FREQ)`.
const RIVER_AMP: f32 = 6.0;
/// Spatial frequency of the centerline sine (radians per world unit along Z).
const RIVER_FREQ: f32 = 0.12;
/// Half the water-surface width: a tile is "on the river" within this of the centerline.
const HALF_WIDTH: f32 = 2.4;
/// How far past the water edge the bank ramp (`river_bank_t` 0→1) extends.
const BANK_RAMP: f32 = 3.0;
/// The river runs the full depth of the scene (well past the 32×32 patch) so it reads to
/// the fog horizon at both ends.
const Z_MIN: f32 = -90.0;
const Z_MAX: f32 = 90.0;

const WATER_SHADER: &str = "shaders/water.wgsl";

// ── Centerline math (one source of truth for mesh + queries) ────────────────────

/// World-space X of the river centerline at depth `z`.
#[inline]
fn centerline_x(z: f32) -> f32 {
    RIVER_AMP * (z * RIVER_FREQ).sin()
}

/// Unit tangent of the centerline in the XZ plane at depth `z` (advancing +Z).
#[inline]
fn centerline_tangent(z: f32) -> Vec2 {
    // d/dz of (centerline_x(z), z) = (AMP*FREQ*cos(z*FREQ), 1).
    let dx = RIVER_AMP * RIVER_FREQ * (z * RIVER_FREQ).cos();
    Vec2::new(dx, 1.0).normalize()
}

/// Unit normal (in XZ) pointing to the river's left/right edges at depth `z`.
#[inline]
fn centerline_normal(z: f32) -> Vec2 {
    let t = centerline_tangent(z);
    Vec2::new(t.y, -t.x) // perpendicular in XZ
}

/// Perpendicular distance from world point `(x,z)` to the centerline. Uses the local
/// normal at the point's own `z`, which is accurate because the curve is gentle
/// (|slope| ≤ AMP*FREQ = 0.72) — good enough for placement masking + banks.
#[inline]
fn dist_to_centerline(x: f32, z: f32) -> f32 {
    let n = centerline_normal(z);
    // Offset from the centerline point at this z is purely in X (same-z projection); its
    // perpendicular distance is that offset dotted with the unit normal's X component.
    ((x - centerline_x(z)) * n.x).abs()
}

/// True where the river water surface is (within the half-width of the centerline).
/// Scatter calls this to avoid spawning props in the water.
pub fn on_river(x: f32, z: f32) -> bool {
    if z < Z_MIN || z > Z_MAX {
        return false;
    }
    dist_to_centerline(x, z) <= HALF_WIDTH
}

/// 0 at the centerline, ramping to 1 a few units past the bank — decor uses this to
/// place wet-shore dressing (reeds, pebbles) along the edges and fade it out inland.
/// Returns 1.0 well away from the river (fully "dry land").
#[allow(dead_code)] // used only by the (kept, unwired) `decor` charm's bank dressing
pub fn river_bank_t(x: f32, z: f32) -> f32 {
    if z < Z_MIN || z > Z_MAX {
        return 1.0;
    }
    let d = dist_to_centerline(x, z);
    if d <= HALF_WIDTH {
        0.0
    } else {
        ((d - HALF_WIDTH) / BANK_RAMP).clamp(0.0, 1.0)
    }
}

// ── Material ────────────────────────────────────────────────────────────────────

pub type WaterMaterial = ExtendedMaterial<StandardMaterial, WaterExt>;

#[derive(Clone, Copy, ShaderType, Debug)]
pub struct WaterParams {
    /// x = ripple strength (normal-tilt multiplier, 1 = as authored in the shader), y = river flow
    /// speed (world units/s at a baked flow magnitude of 1), z = shore-foam strength, w = unused.
    pub params: Vec4,
    /// Water-field mapping: xy = world-space min corner of the baked region, zw = 1 / its world
    /// extent (world XZ → texture UV).
    pub region: Vec4,
}

#[derive(Asset, AsBindGroup, Clone, TypePath, Debug)]
pub struct WaterExt {
    #[uniform(100)]
    pub params: WaterParams,
    /// RGBA8 water field baked by `worldmap::bake_water_field` (mapped by `params.region`):
    /// R = signed distance to the bank in world units (−1 inside the bank … +8 offshore — the
    /// shader's stand-in for depth), G = bog murk mask, BA = river flow (direction × speed,
    /// 0.5-biased). Must be `Some`: Bevy's 1×1 white fallback would read as bog murk everywhere.
    #[texture(101)]
    #[sampler(102)]
    pub field: Option<Handle<Image>>,
    /// The tileable ripple slope map ([`ripple_map`]).
    #[texture(103)]
    #[sampler(104)]
    pub ripples: Option<Handle<Image>>,
}

impl MaterialExtension for WaterExt {
    fn fragment_shader() -> ShaderRef {
        WATER_SHADER.into()
    }
    // alpha_mode() left as None → inherits the base StandardMaterial's AlphaMode::Opaque
    // (see the module doc for why the water is no longer blended).
}

// ── Procedural ripple map ───────────────────────────────────────────────────────

/// Side of the procedural ripple map, texels. 256² with its full mip chain is ~350 KB and bakes in
/// a few ms; the shader samples it at three scales and rotations so the tile never reads as a repeat.
const RIPPLE_SIZE: usize = 256;
/// Wave components summed into the map. Every one has an INTEGER wave vector, so each is exactly
/// periodic over the tile — the sum tiles seamlessly with no wrap blending.
const RIPPLE_WAVES: usize = 96;

/// The shared ripple map (baked once per process; re-bound into the fresh water material of every
/// in-process world rebuild, so it keeps its CPU copy — same hazard as `worldmap::rut_mask_image`).
pub fn ripple_map(images: &mut Assets<Image>) -> Handle<Image> {
    static CACHE: Mutex<Option<Handle<Image>>> = Mutex::new(None);
    let mut c = CACHE.lock().expect("ripple map cache poisoned");
    c.get_or_insert_with(|| images.add(build_ripple_image())).clone()
}

/// Build the ripple map: a tileable random wave field — a sum of [`RIPPLE_WAVES`] cosines with
/// random directions, power-law amplitudes and random phases, which (central-limit theorem) reads
/// as a natural wind-roughened surface, not a sine pattern — stored as its analytic SLOPES rather
/// than a height or a normal: slopes add linearly across layers and average correctly down mips.
///
/// Texel: RG = ∂h/∂u, ∂h/∂v normalised to ±1 (0.5-biased); B = the slope standard deviation the
/// mip's box filter averaged away (0 at mip 0 — the shader turns it into extra GGX roughness, a
/// Toksvig/LEAN-style fix so distant water widens the sun into a glitter path instead of
/// shimmering); A = height 0..1 (foam break-up, river-bed mottling).
fn build_ripple_image() -> Image {
    use std::f32::consts::TAU;
    let n = RIPPLE_SIZE;
    let mut rng = tileworld_core::rng::Mulberry32::new(0x5eed_3a7e);
    let mut rnd = || rng.next() as f32;
    // (kx, kz, height amplitude, phase)
    let mut waves: Vec<(f32, f32, f32, f32)> = Vec::with_capacity(RIPPLE_WAVES);
    while waves.len() < RIPPLE_WAVES {
        // Log-uniform wavenumber, 2..28 cycles per tile.
        let k = (2.0f32.ln() + rnd() * (28.0f32.ln() - 2.0f32.ln())).exp();
        let a = rnd() * TAU;
        let (kx, kz) = ((k * a.cos()).round(), (k * a.sin()).round());
        if kx == 0.0 && kz == 0.0 {
            continue;
        }
        // Height ∝ k^-1.7 → slope ∝ k^-0.7: the broad waves carry the shape while the capillaries
        // still tilt the normal enough to sparkle.
        waves.push((kx, kz, kx.hypot(kz).powf(-1.7), rnd() * TAU));
    }

    // Separable evaluation: cos/sin(a + b) from per-column (a) and per-row (b) angles, so the inner
    // loop is a complex multiply — no trig per texel.
    let (mut h, mut sx, mut sz) = (vec![0f32; n * n], vec![0f32; n * n], vec![0f32; n * n]);
    let (mut col_c, mut col_s) = (vec![0f32; n], vec![0f32; n]);
    for &(kx, kz, amp, ph) in &waves {
        for x in 0..n {
            let a = TAU * kx * x as f32 / n as f32;
            col_c[x] = a.cos();
            col_s[x] = a.sin();
        }
        let (gx, gz) = (-amp * TAU * kx, -amp * TAU * kz);
        for z in 0..n {
            let b = TAU * kz * z as f32 / n as f32 + ph;
            let (cb, sb) = (b.cos(), b.sin());
            for x in 0..n {
                let c = col_c[x] * cb - col_s[x] * sb;
                let s = col_s[x] * cb + col_c[x] * sb;
                let i = z * n + x;
                h[i] += amp * c;
                sx[i] += gx * s;
                sz[i] += gz * s;
            }
        }
    }
    let smax = sx.iter().chain(sz.iter()).fold(1e-6f32, |m, v| m.max(v.abs()));
    let (hmin, hmax) = h.iter().fold((f32::MAX, f32::MIN), |(lo, hi), v| (lo.min(*v), hi.max(*v)));

    // Mip chain: box-filter (slope, slope², height) and encode each level, largest first.
    let enc = |v: f32| (v.clamp(0.0, 1.0) * 255.0 + 0.5) as u8;
    let levels = n.trailing_zeros() as usize + 1;
    let mut data: Vec<u8> = Vec::with_capacity(n * n * 4 * 4 / 3 + 4);
    let mut cur: Vec<[f32; 4]> =
        (0..n * n).map(|i| [sx[i], sz[i], sx[i] * sx[i] + sz[i] * sz[i], h[i]]).collect();
    let mut size = n;
    for _ in 0..levels {
        for v in &cur {
            let var = (v[2] - v[0] * v[0] - v[1] * v[1]).max(0.0);
            data.extend_from_slice(&[
                enc(v[0] / smax * 0.5 + 0.5),
                enc(v[1] / smax * 0.5 + 0.5),
                enc(var.sqrt() / smax),
                enc((v[3] - hmin) / (hmax - hmin).max(1e-6)),
            ]);
        }
        if size == 1 {
            break;
        }
        let half = size / 2;
        let mut next = vec![[0f32; 4]; half * half];
        for z in 0..half {
            for x in 0..half {
                let mut acc = [0f32; 4];
                for (dx, dz) in [(0, 0), (1, 0), (0, 1), (1, 1)] {
                    let p = cur[(2 * z + dz) * size + 2 * x + dx];
                    for k in 0..4 {
                        acc[k] += p[k] * 0.25;
                    }
                }
                next[z * half + x] = acc;
            }
        }
        cur = next;
        size = half;
    }

    let mut img = Image::new_uninit(
        Extent3d { width: n as u32, height: n as u32, depth_or_array_layers: 1 },
        TextureDimension::D2,
        TextureFormat::Rgba8Unorm, // linear data, NOT sRGB
        RenderAssetUsages::default(),
    );
    img.data = Some(data);
    img.texture_descriptor.mip_level_count = levels as u32;
    // Repeat-tiled, trilinear + 8× anisotropic: water is mostly seen at grazing angles, where
    // plain trilinear would smear the ripples flat a few metres out.
    img.sampler = ImageSampler::Descriptor(ImageSamplerDescriptor {
        address_mode_u: ImageAddressMode::Repeat,
        address_mode_v: ImageAddressMode::Repeat,
        address_mode_w: ImageAddressMode::Repeat,
        mag_filter: ImageFilterMode::Linear,
        min_filter: ImageFilterMode::Linear,
        mipmap_filter: ImageFilterMode::Linear,
        anisotropy_clamp: 8,
        ..default()
    });
    img
}

pub struct WaterPlugin;

impl Plugin for WaterPlugin {
    fn build(&self, app: &mut App) {
        // Registers the water material; the world map builds the river/lake geometry with it.
        app.add_plugins(MaterialPlugin::<WaterMaterial>::default());
    }
}
