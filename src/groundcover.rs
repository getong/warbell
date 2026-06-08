//! Ground cover — grass tufts, ferns, red-cap mushrooms, flowers, clover.
//!
//! CONTRACT: each returns ONE small merged, vertex-coloured `Mesh`, base at y=0,
//! against the shared white vertex-colour material (spawned `NotShadowCaster`). These
//! are scattered densely. See
//! `docs/specs/forest-biome-props-ground-cover-exact-bevy-rebuild.md` + `CONTRACT.md`.
//!
//! All visual values (dims / colours / offsets / counts) come from the ground-cover
//! spec; the Rust mesh API (primitive `.mesh().build()`, `translated_by`/`rotated_by`/
//! `scaled_by`, `tinted` + `Mesh::merge`) comes from `CONTRACT.md` §"mesh-building
//! pattern" + the verified-APIs doc §9. Every part is `tinted()` (gets a flat linear
//! `ATTRIBUTE_COLOR`) before merging so the parts share one attribute set and batch.

use bevy::prelude::*;

use crate::palette::lin;

// ── Local ground-cover palette (exact hex from the spec) ───────────────────────
const TUFT_GREEN: u32 = 0x3aa044; // grass blade base (#3aa044)
const TUFT_TIP: u32 = 0x5fc060; // lighter blade tip for the two-tone clump
const FERN_GREEN: u32 = 0x2f7e30; // deep fern frond green
const FERN_TIP: u32 = 0x46a047; // lighter frond tip
const FERN_STEM: u32 = 0x33621f; // fern central rachis (darker stalk)

const MUSH_STEM: u32 = 0xf0e8d0; // mushroom pale stem (#f0e8d0)
const MUSH_RED: u32 = 0xc83838; // red amanita cap (#c83838)
const MUSH_BROWN: u32 = 0x8a5a3a; // brown cap variant (#8a5a3a)
const MUSH_DOT: u32 = 0xf8f6e8; // white cap speckles (#f8f6e8)

const FLOWER_STEM: u32 = 0x3a7a2a; // flower green stem (#3a7a2a)
const FLOWER_CENTER: u32 = 0xe8c84a; // yellow flower centre (#e8c84a)
const PETAL_PINK: u32 = 0xe88ad6; // variant 0 — pink (#e88ad6)
const PETAL_YELLOW: u32 = 0xe6c84a; // variant 1 — yellow (#e6c84a)
const PETAL_WHITE: u32 = 0xf2f0e4; // variant 2 — white
const PETAL_RED: u32 = 0xd8413a; // poppy red
const PETAL_BLUE: u32 = 0x5878d8; // cornflower blue
const PETAL_PURPLE: u32 = 0xa861cc; // wild violet purple
const POPPY_CORE: u32 = 0x2a1a12; // dark poppy centre

/// How many flower colour/shape variants `build_flower_mesh` produces.
pub const NUM_FLOWER_VARIANTS: u32 = 7;

const CLOVER_GREEN: u32 = 0x4a8f3a; // clover leaf green

// ── Forest-floor litter (pinecones, acorns, pebbles, fallen leaves) ──────────────
const PINECONE: u32 = 0x6e4a2c; // brown pinecone scales
const ACORN_NUT: u32 = 0x9a6536; // acorn nut body
const ACORN_CAP: u32 = 0x5a3a1f; // darker acorn cap
const LITTER_PEBBLE: u32 = 0x9a8f82; // small grey ground pebble
const LITTER_PEBBLE_DK: u32 = 0x7d7466; // shadowed pebble
const LEAF_RED: u32 = 0xc05a30; // fallen autumn leaf (rust)
const LEAF_GOLD: u32 = 0xd0a440; // fallen autumn leaf (gold)
const LEAF_BROWN: u32 = 0x8a6a3a; // fallen leaf (brown)

/// How many forest-floor litter variants `build_floor_litter_mesh` produces.
pub const NUM_LITTER_VARIANTS: u32 = 4;

// ── Mesh helpers (verified 0.18 forms, mirrors CONTRACT §mesh-building) ────────

fn y(v: f32) -> Vec3 {
    Vec3::new(0.0, v, 0.0)
}

/// Tag every vertex of `m` with one flat linear colour (REQUIRED before merge — all
/// merged parts must carry the same attribute set, incl. `ATTRIBUTE_COLOR`).
fn tinted(mut m: Mesh, c: [f32; 4]) -> Mesh {
    let n = m.count_vertices();
    m.insert_attribute(Mesh::ATTRIBUTE_COLOR, vec![c; n]);
    m
}

/// Merge several tinted parts into ONE mesh (so identical props still batch into one
/// draw call). `Mesh::merge` returns `Result` in 0.18 — unwrap it.
fn merged(parts: Vec<Mesh>) -> Mesh {
    let mut it = parts.into_iter();
    let mut base = it.next().expect("at least one part");
    for p in it {
        base.merge(&p).expect("ground-cover parts share attributes");
    }
    base
}

/// A cylinder whose centre sits at `cy` (so a stem of height `h` rooted at y=0 uses
/// `cy = h / 2`).
fn cyl_at(r: f32, h: f32, cy: f32, c: u32) -> Mesh {
    tinted(Cylinder::new(r, h).mesh().resolution(6).build().translated_by(y(cy)), lin(c))
}

/// A small (optionally squashed) faceted icosphere centred at `off`. ico(0) keeps the
/// stylised low-poly facet count tiny — these props are scattered by the thousand.
fn ball_at(r: f32, off: Vec3, squash: f32, c: u32) -> Mesh {
    tinted(
        Sphere::new(r)
            .mesh()
            .ico(0)
            .unwrap()
            .scaled_by(Vec3::new(1.0, squash, 1.0))
            .translated_by(off),
        lin(c),
    )
}

/// A thin flat-shaded cone blade rooted at y≈0, leaned outward by `tilt` (about Z)
/// then yawed by `yaw` (about Y) so a clump of them fans out. Flat-shaded so the blade
/// reads as a crisp spike, not a soft round cone.
fn blade(yaw: f32, tilt: f32, h: f32, r: f32, c: u32) -> Mesh {
    let mut m = Cone { radius: r, height: h }
        .mesh()
        .build()
        .translated_by(y(h / 2.0))
        .rotated_by(Quat::from_rotation_z(tilt))
        .rotated_by(Quat::from_rotation_y(yaw));
    m.duplicate_vertices();
    m.compute_flat_normals();
    tinted(m, lin(c))
}

// ── Grass tuft ─────────────────────────────────────────────────────────────────

/// Grass tuft: 5 thin tapered cone blades fanned around the clump, ~0.26u tall, leaned
/// + yawed out so it reads as a spiky clump (port of `Scatter.tsx` PARTS.tuft — 5 cones,
/// radii 0.025→0.02, heights 0.26→0.17, exact offsets/rotations from the spec). Green
/// base (#3aa044) → lighter tip (#5fc060): the two taller central blades use the base
/// tone, the shorter outer blades the lighter tip tone, so the clump reads two-tone.
pub fn build_grass_tuft_mesh() -> Mesh {
    // (yaw, tilt, height, radius, colour) — spec blade table, with the tilt encoding
    // each blade's lean (the spec's combined x/z euler tilts folded into one Z lean).
    let specs = [
        (0.0_f32, 0.00_f32, 0.26_f32, 0.025_f32, TUFT_GREEN),
        (0.5, 0.22, 0.22, 0.022, TUFT_GREEN),
        (-0.4, -0.20, 0.20, 0.022, TUFT_TIP),
        (1.9, 0.15, 0.18, 0.020, TUFT_TIP),
        (-1.7, -0.18, 0.17, 0.020, TUFT_TIP),
    ];
    let parts = specs
        .iter()
        .map(|&(yaw, tilt, h, r, c)| blade(yaw, tilt, h, r, c))
        .collect();
    merged(parts)
}

// ── Fern ───────────────────────────────────────────────────────────────────────

/// Fern: a low spray of several angled fronds radiating from the base, deep green,
/// ~0.3u tall. Each frond is a thin flattened box (a leaf blade) tilted up + outward;
/// they fan around the clump in a low rosette. A short darker central stalk anchors it.
pub fn build_fern_mesh() -> Mesh {
    const FROND_LEN: f32 = 0.30;
    let mut parts = vec![
        // Short central rachis (a thin upright box) so the fronds read as rooted.
        tinted(
            Cuboid::new(0.018, 0.10, 0.018).mesh().build().translated_by(y(0.05)),
            lin(FERN_STEM),
        ),
    ];
    // 6 fronds fanned around the clump: a thin flattened box, pivoted at the base, laid
    // out almost flat (low spray) with a slight upward lift, alternating two green tones.
    for i in 0..6 {
        let yaw = (i as f32 / 6.0) * std::f32::consts::TAU;
        let lift = if i % 2 == 0 { 0.62 } else { 0.50 }; // radians from horizontal
        let c = if i % 2 == 0 { FERN_GREEN } else { FERN_TIP };
        // Build a thin flat leaf along +Y (length FROND_LEN), shift so its base is at the
        // origin, tilt it down toward horizontal (about X), then yaw it around the clump.
        let frond = Cuboid::new(0.05, FROND_LEN, 0.012)
            .mesh()
            .build()
            .translated_by(y(FROND_LEN * 0.5))
            // tilt away from vertical: PI/2 - lift leans it toward the ground (low spray).
            .rotated_by(Quat::from_rotation_x(std::f32::consts::FRAC_PI_2 - lift))
            .rotated_by(Quat::from_rotation_y(yaw))
            // lift the whole frond a touch so it sprays from ~0.05 above ground, base ≥ 0.
            .translated_by(y(0.05));
        parts.push(tinted(frond, lin(c)));
    }
    merged(parts)
}

// ── Mushroom (red amanita) ───────────────────────────────────────────────────

/// Red-cap amanita: a pale white stem + a domed cap (squashed half-ball) + (red
/// variant) a few tiny white speckle boxes on the cap. `variant`: even = red cap
/// (#c83838) with white spots, odd = brown cap (#8a5a3a) with no spots. Two sizes via
/// the variant too — variant ≥ 2 builds a slightly larger mushroom. ~0.15u tall.
pub fn build_mushroom_mesh(variant: u32) -> Mesh {
    // Size: variants 0/1 are small, 2/3 a touch bigger (the spec's 2-size cluster).
    let s = if variant >= 2 { 1.25 } else { 1.0 };
    // Cap colour: even = red amanita, odd = brown.
    let red = variant % 2 == 0;
    let cap = if red { MUSH_RED } else { MUSH_BROWN };

    let stem_h = 0.10 * s;
    let cap_y = stem_h; // cap sits at the top of the stem
    let cap_r = 0.09 * s;

    let mut parts = vec![
        // Pale stem (slightly tapered look approximated with a thin cylinder).
        cyl_at(0.034 * s, stem_h, stem_h * 0.5, MUSH_STEM),
        // Domed cap: a squashed half-ball resting on the stem.
        ball_at(cap_r, y(cap_y), 0.62, cap),
    ];
    // White speckles only on the red amanita cap (a few tiny boxes near the crown).
    if red {
        for &(dx, dz) in &[(0.045_f32, 0.02_f32), (-0.035, -0.04), (0.01, 0.05)] {
            let spot = Cuboid::new(0.020 * s, 0.014 * s, 0.020 * s)
                .mesh()
                .build()
                .translated_by(Vec3::new(dx * s, cap_y + 0.045 * s, dz * s));
            parts.push(tinted(spot, lin(MUSH_DOT)));
        }
    }
    merged(parts)
}

// ── Flower ───────────────────────────────────────────────────────────────────

/// Flower: a thin green stem + a small bright petal head — a ring of petal balls around a
/// centre. `variant` (mod [`NUM_FLOWER_VARIANTS`]) picks colour + shape, so a meadow reads
/// as a mix of pink/yellow/white daisies, red poppies, blue cornflowers and violets of
/// varying height and petal count. ~0.16–0.24u tall.
pub fn build_flower_mesh(variant: u32) -> Mesh {
    // (petal, centre, n_petals, head_y, ring_r, petal_r, petal_squash)
    let (petal, center, n, head_y, ring_r, petal_r, squash) = match variant % NUM_FLOWER_VARIANTS {
        0 => (PETAL_PINK, FLOWER_CENTER, 5, 0.16, 0.045, 0.030, 0.55),
        1 => (PETAL_YELLOW, FLOWER_CENTER, 5, 0.16, 0.045, 0.030, 0.55),
        2 => (PETAL_WHITE, FLOWER_CENTER, 5, 0.16, 0.045, 0.030, 0.55),
        3 => (PETAL_RED, POPPY_CORE, 5, 0.20, 0.050, 0.036, 0.50), // poppy — taller, dark core
        4 => (PETAL_BLUE, FLOWER_CENTER, 8, 0.18, 0.046, 0.022, 0.50), // cornflower — many petals
        5 => (PETAL_PURPLE, FLOWER_CENTER, 6, 0.19, 0.046, 0.026, 0.55), // violet
        _ => (PETAL_WHITE, FLOWER_CENTER, 11, 0.23, 0.052, 0.016, 0.40), // daisy — tall, thin rays
    };
    let mut parts = vec![
        // Thin green stem (a slender cone from the ground up to the bloom).
        tinted(
            Cone { radius: 0.010, height: head_y }.mesh().build().translated_by(y(head_y * 0.5)),
            lin(FLOWER_STEM),
        ),
        // Centre disc (small squashed ball at the bloom).
        ball_at(0.024, y(head_y), 0.7, center),
    ];
    // Ring of petals around the centre (small flattened balls).
    for i in 0..n {
        let a = (i as f32 / n as f32) * std::f32::consts::TAU;
        parts.push(ball_at(
            petal_r,
            Vec3::new(a.cos() * ring_r, head_y, a.sin() * ring_r),
            squash,
            petal,
        ));
    }
    merged(parts)
}

// ── Forest-floor litter ──────────────────────────────────────────────────────────

/// Tiny forest-floor litter that makes the ground feel lived-in. `variant` (mod
/// [`NUM_LITTER_VARIANTS`]): 0 = pinecone, 1 = acorn, 2 = pebble cluster, 3 = a few fallen
/// autumn leaves. All very low (≤0.12u), base flush at y=0.
pub fn build_floor_litter_mesh(variant: u32) -> Mesh {
    match variant % NUM_LITTER_VARIANTS {
        // Pinecone — three stacked squashed brown balls tapering to a tip.
        0 => merged(vec![
            ball_at(0.045, y(0.04), 1.15, PINECONE),
            ball_at(0.036, y(0.085), 1.15, PINECONE),
            ball_at(0.024, y(0.115), 1.1, PINECONE),
        ]),
        // Acorn — a rounded nut with a darker textured cap + a tiny stalk.
        1 => merged(vec![
            ball_at(0.040, y(0.035), 1.05, ACORN_NUT),
            ball_at(0.044, y(0.066), 0.55, ACORN_CAP),
            tinted(
                Cylinder::new(0.008, 0.03).mesh().resolution(5).build().translated_by(y(0.092)),
                lin(ACORN_CAP),
            ),
        ]),
        // Pebble cluster — two or three small grey stones.
        2 => merged(vec![
            ball_at(0.050, y(0.028), 0.55, LITTER_PEBBLE),
            ball_at(0.036, Vec3::new(0.06, 0.020, 0.03), 0.5, LITTER_PEBBLE_DK),
            ball_at(0.030, Vec3::new(-0.05, 0.018, -0.04), 0.5, LITTER_PEBBLE),
        ]),
        // Fallen leaves — a few flat tinted discs lying on the ground, lightly overlapping.
        _ => {
            let leaf = |r: f32, off: Vec3, c: u32| -> Mesh {
                tinted(
                    Circle::new(r)
                        .mesh()
                        .resolution(6)
                        .build()
                        .rotated_by(Quat::from_rotation_x(-std::f32::consts::FRAC_PI_2))
                        .translated_by(off),
                    lin(c),
                )
            };
            merged(vec![
                leaf(0.06, y(0.004), LEAF_RED),
                leaf(0.055, Vec3::new(0.07, 0.008, 0.02), LEAF_GOLD),
                leaf(0.05, Vec3::new(-0.05, 0.012, 0.05), LEAF_BROWN),
            ])
        }
    }
}

// ── Clover ────────────────────────────────────────────────────────────────────

/// Clover: a tiny tri-leaf clump — 3 small flattened green discs in a triangle, very
/// low to the ground (~0.06u), each on a stub. Base at y=0.
pub fn build_clover_mesh() -> Mesh {
    const LEAF_Y: f32 = 0.05;
    const RING_R: f32 = 0.04;
    let mut parts = Vec::new();
    for i in 0..3 {
        let a = (i as f32 / 3.0) * std::f32::consts::TAU;
        let off = Vec3::new(a.cos() * RING_R, LEAF_Y, a.sin() * RING_R);
        // Leaf: a small flattened (very squashed) ball — a low rounded disc.
        parts.push(ball_at(0.035, off, 0.30, CLOVER_GREEN));
    }
    merged(parts)
}
