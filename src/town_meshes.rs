//! **Building meshes for the town economy** — proper low-poly Farm + House models,
//! replacing the placeholder boxes in `town.rs`. Same contract as `props.rs`/`camps.rs`:
//! each builder returns ONE merged, flat-shaded, vertex-coloured `Mesh` with its base at
//! `y = 0`, against the shared white vertex-colour material so the renderer batches them.
//!
//! House proportions follow the TS `House.tsx` (foundation + plaster walls + gable roof +
//! door + glowing window + chimney). The Farm is forest's own invention: a thatched hut
//! beside a tilled field of crop rows ringed by a low fence — so a farm reads as a farm.

use bevy::prelude::*;

use crate::palette::lin;

// ── Mesh helpers (mirror props.rs: tint every vertex, then merge same-attr parts) ──

fn tinted(mut m: Mesh, c: u32) -> Mesh {
    let n = m.count_vertices();
    m.insert_attribute(Mesh::ATTRIBUTE_COLOR, vec![lin(c); n]);
    m
}

/// A coloured box of size `(w,h,d)` translated to `(x,y,z)` (its centre).
fn box_at(w: f32, h: f32, d: f32, x: f32, y: f32, z: f32, c: u32) -> Mesh {
    tinted(Cuboid::new(w, h, d).mesh().build().translated_by(Vec3::new(x, y, z)), c)
}

/// Merge parts (all share POSITION/NORMAL/UV/COLOR), then facet for the crisp low-poly look.
fn finish(parts: Vec<Mesh>) -> Mesh {
    let mut it = parts.into_iter();
    let mut base = it.next().expect("at least one part");
    for p in it {
        base.merge(&p).expect("building parts share attributes");
    }
    base.duplicate_vertices();
    base.compute_flat_normals();
    base
}

// ── Palette (House.tsx + forest farm tones, sRGB hex) ──
const PLASTER: u32 = 0xd3b78b;
const ROOF: u32 = 0x6b3322;
const FRAME: u32 = 0x5a3a22;
const DOOR: u32 = 0x3a2618;
const WINDOW_GLOW: u32 = 0xffd58c;
const STONE: u32 = 0x6e6e76;

const STRAW: u32 = 0xb9975a;
const THATCH: u32 = 0x6e4a2a;
const SOIL: u32 = 0x6b4a2e;
const CROP: u32 = 0x6a9a3a;
const CROP_TIP: u32 = 0xc8a84a;
const FENCE: u32 = 0x6a4a30;

// ── House ──────────────────────────────────────────────────────────────────────────
//
// Walls 2.6(X) × 1.3(Y) × 2.2(Z) on a stone foundation; a gable roof ridging along X
// (slopes face ±Z); door + window on the +Z front face; a stone chimney on the −X side.

/// One gable-roof slab: a flat slab tilted `+/-angle` about X and lifted to sit on `wall_top`.
/// `rise` = ridge height above the eave, `hz` = half-depth (incl. overhang).
fn roof_slab(len_x: f32, hz: f32, rise: f32, wall_top: f32, c: u32, positive_z: bool) -> Mesh {
    let slope = (rise * rise + hz * hz).sqrt();
    let ang = rise.atan2(hz); // tilt from horizontal
    let sign = if positive_z { 1.0 } else { -1.0 };
    // Flat slab centred at origin (z spans the slope), tilt it, then move the high edge to
    // the ridge (z=0, y=wall_top+rise) and the low edge to the eave (z=±hz, y=wall_top).
    let half = slope * 0.5;
    let dy = wall_top + rise - (ang.sin() * half); // lift so the high edge hits the ridge
    let dz = sign * (ang.cos() * half); // shift toward the eave side
    tinted(
        Cuboid::new(len_x, 0.12, slope)
            .mesh()
            .build()
            .rotated_by(Quat::from_rotation_x(sign * ang))
            .translated_by(Vec3::new(0.0, dy, dz)),
        c,
    )
}

pub fn house() -> Mesh {
    let wall_w = 2.6;
    let wall_d = 2.2;
    let wall_h = 1.3;
    let found_h = 0.2;
    let wall_top = found_h + wall_h; // 1.5
    let rise = 0.8;
    let hz = wall_d * 0.5 + 0.2; // overhang
    let front = wall_d * 0.5; // +Z face

    let mut parts = vec![
        // Foundation (oversized, low).
        box_at(wall_w + 0.2, found_h, wall_d + 0.2, 0.0, found_h * 0.5, 0.0, STONE),
        // Plaster walls.
        box_at(wall_w, wall_h, wall_d, 0.0, found_h + wall_h * 0.5, 0.0, PLASTER),
        // Gable roof (two slabs meeting at the ridge over X).
        roof_slab(wall_w + 0.4, hz, rise, wall_top, ROOF, true),
        roof_slab(wall_w + 0.4, hz, rise, wall_top, ROOF, false),
        // Door (recessed dark panel + timber frame) on the +Z front.
        box_at(0.62, 0.96, 0.06, -0.5, found_h + 0.48, front + 0.02, FRAME),
        box_at(0.46, 0.84, 0.06, -0.5, found_h + 0.42, front + 0.05, DOOR),
        // Window (frame + warm pane) on the +Z front, other side of the door.
        box_at(0.6, 0.6, 0.06, 0.6, found_h + 0.78, front + 0.02, FRAME),
        box_at(0.44, 0.44, 0.06, 0.6, found_h + 0.78, front + 0.05, WINDOW_GLOW),
        // Stone chimney on the −X roof side.
        box_at(0.3, 0.9, 0.3, -wall_w * 0.5 + 0.45, wall_top + 0.45, 0.3, STONE),
    ];
    parts.push(box_at(0.36, 0.16, 0.36, -wall_w * 0.5 + 0.45, wall_top + 0.92, 0.3, FRAME)); // cap
    finish(parts)
}

// ── Farm: thatched hut (−X) + tilled field (+X) ──────────────────────────────────────

fn hut() -> Vec<Mesh> {
    let w = 1.8;
    let d = 1.6;
    let h = 1.05;
    let found_h = 0.16;
    let wall_top = found_h + h;
    let rise = 0.85; // steeper thatch
    let hz = d * 0.5 + 0.18;
    let cx = -1.15; // sit on the −X side of the plot
    let mut v = vec![
        box_at(w + 0.16, found_h, d + 0.16, cx, found_h * 0.5, 0.0, STONE),
        box_at(w, h, d, cx, found_h + h * 0.5, 0.0, STRAW),
    ];
    // Thatch gable, shifted to the hut centre.
    let mut r1 = roof_slab(w + 0.3, hz, rise, wall_top, THATCH, true);
    let mut r2 = roof_slab(w + 0.3, hz, rise, wall_top, THATCH, false);
    r1 = r1.translated_by(Vec3::new(cx, 0.0, 0.0));
    r2 = r2.translated_by(Vec3::new(cx, 0.0, 0.0));
    v.push(r1);
    v.push(r2);
    // Dark doorway on the +Z face.
    v.push(box_at(0.42, 0.72, 0.05, cx, found_h + 0.36, d * 0.5 + 0.03, DOOR));
    v
}

fn field() -> Vec<Mesh> {
    let cx = 1.05; // +X side
    let fw = 2.3;
    let fd = 2.5;
    let mut v = vec![
        // Tilled soil pad (low).
        box_at(fw, 0.1, fd, cx, 0.05, 0.0, SOIL),
    ];
    // Crop rows: four long low rows with gold tips.
    for i in 0..4 {
        let z = -fd * 0.5 + 0.5 + i as f32 * (fd - 1.0) / 3.0;
        v.push(box_at(fw - 0.5, 0.34, 0.2, cx, 0.1 + 0.17, z, CROP));
        v.push(box_at(fw - 0.5, 0.1, 0.2, cx, 0.1 + 0.36, z, CROP_TIP)); // ripe tips
    }
    // Low post-and-rail fence around the field.
    let hx = fw * 0.5;
    let hzf = fd * 0.5;
    for (px, pz) in [(-hx, -hzf), (hx, -hzf), (-hx, hzf), (hx, hzf), (0.0, -hzf), (0.0, hzf)] {
        v.push(box_at(0.09, 0.5, 0.09, cx + px, 0.25, pz, FENCE));
    }
    // Two side rails (run along Z on the ±X edges).
    for px in [-hx, hx] {
        v.push(box_at(0.05, 0.06, fd, cx + px, 0.34, 0.0, FENCE));
    }
    v
}

pub fn farm() -> Mesh {
    let mut parts = hut();
    parts.extend(field());
    finish(parts)
}

// ── Woodcutter: timber cabin (−X) + a stacked log pile (+X) + a chopping stump ──

const WOOD_WALL: u32 = 0x6e5232; // dark timber
const WOOD_ROOF: u32 = 0x4a3826; // dark shingle
const LOG: u32 = 0x7a5a36;
const LOG_END: u32 = 0xb89466; // lighter sawn cut-ends
const AXE_HANDLE: u32 = 0x8a6a40;
const AXE_HEAD: u32 = 0x9aa0aa;

pub fn woodcutter() -> Mesh {
    let cx = -1.0; // cabin on the −X side
    let found_h = 0.16;
    let wall_h = 1.0;
    let wall_top = found_h + wall_h; // 1.16
    let d = 1.5;
    let mut parts = vec![
        // Cabin: foundation + timber walls + gable shingle roof + door.
        box_at(1.8, found_h, d + 0.1, cx, found_h * 0.5, 0.0, STONE),
        box_at(1.6, wall_h, d, cx, found_h + wall_h * 0.5, 0.0, WOOD_WALL),
        box_at(0.4, 0.66, 0.05, cx, found_h + 0.33, d * 0.5 + 0.03, DOOR),
    ];
    let mut r1 = roof_slab(1.9, d * 0.5 + 0.18, 0.7, wall_top, WOOD_ROOF, true);
    let mut r2 = roof_slab(1.9, d * 0.5 + 0.18, 0.7, wall_top, WOOD_ROOF, false);
    r1 = r1.translated_by(Vec3::new(cx, 0.0, 0.0));
    r2 = r2.translated_by(Vec3::new(cx, 0.0, 0.0));
    parts.push(r1);
    parts.push(r2);

    // Log pile (+X): two stacked rows of logs running along Z, with lighter cut-ends.
    let lx = 1.15;
    for dx in [-0.36, 0.0, 0.36] {
        parts.push(box_at(0.34, 0.34, 1.5, lx + dx, 0.17, 0.0, LOG)); // bottom row
        parts.push(box_at(0.34, 0.34, 0.08, lx + dx, 0.17, 0.75, LOG_END)); // cut-end
    }
    for dx in [-0.18, 0.18] {
        parts.push(box_at(0.34, 0.34, 1.5, lx + dx, 0.51, 0.0, LOG)); // top row
        parts.push(box_at(0.34, 0.34, 0.08, lx + dx, 0.51, 0.75, LOG_END));
    }

    // Chopping stump + axe, front-centre between cabin and pile.
    parts.push(box_at(0.5, 0.45, 0.5, 0.1, 0.225, 1.15, LOG));
    parts.push(box_at(0.5, 0.06, 0.5, 0.1, 0.45, 1.15, LOG_END)); // sawn top
    parts.push(box_at(0.05, 0.5, 0.05, 0.2, 0.72, 1.15, AXE_HANDLE)); // handle
    parts.push(box_at(0.18, 0.13, 0.05, 0.2, 0.94, 1.15, AXE_HEAD)); // head

    finish(parts)
}
