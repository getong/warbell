//! **Bridges** — plank decks laid across the combined map's real river. The river is a carved
//! terrain channel (the sea plane shows through where `worldmap::is_river_world` is true), so we
//! SCAN that channel at a few depths, find the water run's centre + width, and span it bank to
//! bank. Each deck also registers a walkable span the nav-grid honours, so the night invaders'
//! A* can cross at a bridge. Ports Bridge.tsx/bridges.ts, placed on the actual water.

use std::sync::OnceLock;

use bevy::mesh::MeshBuilder;
use bevy::prelude::*;

use crate::biome::BiomeEntity;
use crate::palette::lin;
use crate::worldmap::{is_river_world, GX};

/// Half-width along the bank (Z) of a deck.
const DECK_HALF_Z: f32 = 1.2;
/// Bank overhang past the water edge on each side (world units).
const OVERHANG: f32 = 1.4;
/// Min Z gap between successive bridges as we scan (so they spread along the river).
const MIN_SPACING_Z: f32 = 30.0;
/// At most this many bridges.
const MAX_BRIDGES: usize = 3;
/// Acceptable half-width of a river run to bridge (skip slivers + implausibly wide spans).
const MIN_HALF: f32 = 0.6;
const MAX_HALF: f32 = 9.0;

/// A bridge: deck centre (world XZ) + half-length across the river (X).
#[derive(Clone, Copy)]
struct Span {
    cx: f32,
    cz: f32,
    half_x: f32,
}

/// Find the river crossings by scanning the (pure) `is_river_world` channel. Cached — the scan
/// only reads the river formula, so it's valid any time (no built terrain needed).
fn spans() -> &'static [Span] {
    static SPANS: OnceLock<Vec<Span>> = OnceLock::new();
    SPANS.get_or_init(|| {
        let mut out: Vec<Span> = Vec::new();
        let mut z = -65.0_f32;
        while z <= 65.0 && out.len() < MAX_BRIDGES {
            if let Some((cx, half)) = river_run_at_z(z) {
                if out.last().is_none_or(|s| (z - s.cz).abs() >= MIN_SPACING_Z) {
                    out.push(Span { cx, cz: z, half_x: half + OVERHANG });
                }
            }
            z += 2.0;
        }
        out
    })
}

/// Scan world-x at depth `z` for the longest contiguous river run; return its `(centre_x, half)`.
fn river_run_at_z(z: f32) -> Option<(f32, f32)> {
    let (mut best_lo, mut best_hi) = (0.0_f32, -1.0_f32);
    let (mut lo, mut in_run) = (0.0_f32, false);
    let mut x = -GX + 2.0;
    let step = 0.5;
    while x <= GX - 2.0 {
        let wet = is_river_world(x, z);
        if wet && !in_run {
            in_run = true;
            lo = x;
        } else if !wet && in_run {
            in_run = false;
            if x - lo > best_hi - best_lo {
                best_lo = lo;
                best_hi = x;
            }
        }
        x += step;
    }
    if in_run && (GX - 2.0) - lo > best_hi - best_lo {
        best_lo = lo;
        best_hi = GX - 2.0;
    }
    let half = (best_hi - best_lo) * 0.5;
    if (MIN_HALF..=MAX_HALF).contains(&half) {
        Some(((best_lo + best_hi) * 0.5, half))
    } else {
        None
    }
}

/// Is `(wx, wz)` on a bridge deck? Consulted by `navgrid::standable` so A* can cross the river.
pub fn is_on_bridge(wx: f32, wz: f32) -> bool {
    spans().iter().any(|s| (wx - s.cx).abs() <= s.half_x && (wz - s.cz).abs() <= DECK_HALF_Z)
}

// ── mesh ───────────────────────────────────────────────────────────────────────────
fn tinted(mut m: Mesh, c: u32) -> Mesh {
    let n = m.count_vertices();
    m.insert_attribute(Mesh::ATTRIBUTE_COLOR, vec![lin(c); n]);
    m
}
fn bx(w: f32, h: f32, d: f32, off: Vec3, c: u32) -> Mesh {
    tinted(Cuboid::new(w, h, d).mesh().build().translated_by(off), c)
}

/// One deck mesh spanning `2·half_x` across X (local space; deck top at y≈0).
fn deck_mesh(half_x: f32) -> Mesh {
    const LIGHT: u32 = 0x8a5a32;
    const DARK: u32 = 0x6b4222;
    const RAIL: u32 = 0x5a3a22;
    let len = half_x * 2.0;
    let mut parts: Vec<Mesh> = Vec::new();
    let planks = (len * 2.0).max(4.0) as i32;
    for i in 0..planks {
        let x = -half_x + (i as f32 + 0.5) / planks as f32 * len;
        let c = if i % 2 == 0 { LIGHT } else { DARK };
        parts.push(bx(len / planks as f32 * 0.92, 0.1, DECK_HALF_Z * 2.0, Vec3::new(x, 0.0, 0.0), c));
    }
    for sz in [-DECK_HALF_Z, DECK_HALF_Z] {
        parts.push(bx(len, 0.08, 0.1, Vec3::new(0.0, 0.45, sz), RAIL)); // side rail
        for sx in [-half_x + 0.2, half_x - 0.2] {
            parts.push(bx(0.12, 0.55, 0.12, Vec3::new(sx, 0.22, sz), RAIL)); // end post
        }
    }
    for sz in [-DECK_HALF_Z + 0.3, DECK_HALF_Z - 0.3] {
        parts.push(bx(len, 0.12, 0.14, Vec3::new(0.0, -0.12, sz), DARK)); // underbeam
    }
    let mut it = parts.into_iter();
    let mut base = it.next().unwrap();
    for p in it {
        base.merge(&p).expect("bridge parts share attributes");
    }
    base.duplicate_vertices();
    base.compute_flat_normals();
    base
}

/// Spawn a deck at each river crossing. Called from `worldmap::build` (after terrain).
pub fn populate(commands: &mut Commands, meshes: &mut Assets<Mesh>, materials: &mut Assets<StandardMaterial>) {
    let mat = materials.add(StandardMaterial { base_color: Color::WHITE, perceptual_roughness: 0.85, ..default() });
    for s in spans() {
        // Sit the deck on the bank ground (sampled just past the water on either side).
        let bank_y = crate::worldmap::ground_at_world(s.cx + s.half_x, s.cz)
            .or_else(|| crate::worldmap::ground_at_world(s.cx - s.half_x, s.cz))
            .unwrap_or(0.0);
        commands.spawn((
            Mesh3d(meshes.add(deck_mesh(s.half_x))),
            MeshMaterial3d(mat.clone()),
            Transform::from_xyz(s.cx, bank_y + 0.2, s.cz),
            BiomeEntity,
        ));
    }
}
