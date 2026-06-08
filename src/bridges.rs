//! **Bridges** — plank decks spanning the meandering river at a few crossings, ported from the
//! old game's `Bridge.tsx` / `bridges.ts`. Each is a merged vertex-coloured deck (planks + side
//! rails + end posts) laid across the river centerline, and registers a walkable span so the
//! nav-grid's A* (and thus the night invaders) can cross the water there instead of routing all
//! the way around it.

use std::sync::OnceLock;

use bevy::mesh::MeshBuilder;
use bevy::prelude::*;

use crate::biome::BiomeEntity;
use crate::palette::lin;

/// Half-length of a deck across the river (X), and half-width along the bank (Z).
const DECK_HALF_X: f32 = 3.4;
const DECK_HALF_Z: f32 = 1.1;

/// The z-positions (world) at which a bridge crosses the river. Chosen to spread along the
/// meander; each deck is centred on the river centerline `x = 6·sin(0.12·z)` at that z.
const CROSSING_Z: [f32; 3] = [-26.0, 6.0, 34.0];

/// A registered walkable span (world-space AABB on XZ) the nav-grid treats as standable.
#[derive(Clone, Copy)]
struct Span {
    cx: f32,
    cz: f32,
}

/// River centerline X at depth `z` — mirrors `water.rs` (`x = RIVER_AMP·sin(z·RIVER_FREQ)`,
/// AMP=6, FREQ=0.12). Kept local so bridges don't depend on water's private helpers.
fn river_centerline_x(z: f32) -> f32 {
    6.0 * (z * 0.12).sin()
}

fn spans() -> &'static [Span] {
    static SPANS: OnceLock<Vec<Span>> = OnceLock::new();
    SPANS.get_or_init(|| CROSSING_Z.iter().map(|&z| Span { cx: river_centerline_x(z), cz: z }).collect())
}

/// Is `(wx, wz)` on a bridge deck? Consulted by `navgrid::standable` so A* can cross the river.
pub fn is_on_bridge(wx: f32, wz: f32) -> bool {
    spans().iter().any(|s| (wx - s.cx).abs() <= DECK_HALF_X && (wz - s.cz).abs() <= DECK_HALF_Z)
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

/// One bridge deck mesh (local space: spans X, banks at ±DECK_HALF_X, deck top at y≈0).
fn deck_mesh() -> Mesh {
    const LIGHT: u32 = 0x8a5a32;
    const DARK: u32 = 0x6b4222;
    const RAIL: u32 = 0x5a3a22;
    let len = DECK_HALF_X * 2.0;
    let mut parts: Vec<Mesh> = Vec::new();
    // Plank deck — alternating light/dark boards laid across the span.
    let planks = (len * 2.0) as i32;
    for i in 0..planks {
        let x = -DECK_HALF_X + (i as f32 + 0.5) / planks as f32 * len;
        let c = if i % 2 == 0 { LIGHT } else { DARK };
        parts.push(bx(len / planks as f32 * 0.92, 0.1, DECK_HALF_Z * 2.0, Vec3::new(x, 0.0, 0.0), c));
    }
    // Two side rails + end posts.
    for sz in [-DECK_HALF_Z, DECK_HALF_Z] {
        parts.push(bx(len, 0.08, 0.1, Vec3::new(0.0, 0.45, sz), RAIL));
        for sx in [-DECK_HALF_X + 0.2, DECK_HALF_X - 0.2] {
            parts.push(bx(0.12, 0.55, 0.12, Vec3::new(sx, 0.22, sz), RAIL));
        }
    }
    // Underbeams (so the deck reads as raised over the water).
    for sz in [-DECK_HALF_Z + 0.3, DECK_HALF_Z - 0.3] {
        parts.push(bx(len, 0.12, 0.14, Vec3::new(0.0, -0.12, sz), DARK));
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

/// Spawn a deck at each river crossing. Called from `worldmap::build`.
pub fn populate(commands: &mut Commands, meshes: &mut Assets<Mesh>, materials: &mut Assets<StandardMaterial>) {
    let mesh = meshes.add(deck_mesh());
    let mat = materials.add(StandardMaterial { base_color: Color::WHITE, perceptual_roughness: 0.85, ..default() });
    for s in spans() {
        // Sit the deck just above the bank ground so it bridges bank-to-bank over the water gap.
        let bank_y = crate::worldmap::ground_at_world(s.cx + DECK_HALF_X, s.cz)
            .or_else(|| crate::worldmap::ground_at_world(s.cx - DECK_HALF_X, s.cz))
            .unwrap_or(0.0);
        commands.spawn((
            Mesh3d(mesh.clone()),
            MeshMaterial3d(mat.clone()),
            Transform::from_xyz(s.cx, bank_y + 0.25, s.cz),
            BiomeEntity,
        ));
    }
}
