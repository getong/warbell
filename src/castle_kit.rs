//! Castle fortification kit (phase 3c of `docs/superpowers/specs/2026-10-11-zamek-v2-design.md`):
//! the pieces of `assets/forest_pbr/castle_kit.glb`, built by `tools/blender_forest/castle_kit.py`.
//! That script's docstring is the manifest (every node's footprint and height).
//!
//! **Pivot convention** (every piece): ground at y = 0 (foundations sink to y = -0.3), centred on
//! its footprint, +X runs along the wall, the OUTER (enemy) face looks toward -Z, the courtyard is
//! +Z. Modular wall pieces are 4u long and tile at x = ±2 (`ck_palisade`, `ck_timber_gate`,
//! `ck_curtain`); `ck_gatehouse` is 6.4u on the wall line; `ck_curtain_corner` is 1.4 x 1.4 with its
//! outer faces on -Z and -X (rotate it to turn the other way).
//!
//! The three story layers read without words: OLD COLONY STONE (grey, mossy, broken; the bell tower
//! alone stands whole), OUR FRESH TIMBER (peeled logs, thatch, mud ramparts), then the new dressed
//! stone of the later tiers.
//!
//! `FOREST_CASTLEKIT_SHOWCASE=1` lays every piece out in three rows on open flat ground away from the
//! castle (old colony / timber tier / stone tier), logged as `castle_kit showcase:`, for screenshots
//! beside the hero (`FOREST_HERO`).

use bevy::prelude::*;
use std::sync::Mutex;

use crate::biome::{Biome, BiomeEntity};

/// Every node in `castle_kit.glb`.
pub const PIECES: [&str; 14] = [
    "ck_bell_tower",
    "ck_ruin_keep",
    "ck_ruin_wall_a",
    "ck_ruin_wall_b",
    "ck_rubble",
    "ck_palisade",
    "ck_timber_gate",
    "ck_watchtower",
    "ck_curtain",
    "ck_curtain_corner",
    "ck_stone_tower",
    "ck_gatehouse",
    "ck_keep_t1",
    "ck_keep_t2",
];

/// Handle to the loaded kit (the shared realforest kit, checked to contain `castle_kit.glb`).
/// Inserted as a resource by the first `populate`; [`CastleKit::get`] works any time after the
/// realforest kit has loaded.
#[derive(Resource, Clone, Copy)]
pub struct CastleKit {
    kit: &'static crate::realforest::Kit,
}

impl CastleKit {
    pub fn get() -> Option<Self> {
        crate::realforest::get().filter(|k| k.has(PIECES[0])).map(|kit| Self { kit })
    }

    #[allow(dead_code)] // API for the castle rework
    pub fn has(&self, name: &str) -> bool {
        self.kit.has(name)
    }

    /// Spawn piece `name` as a new root entity at `tf` (see the pivot convention above).
    pub fn spawn_piece(&self, commands: &mut Commands, name: &str, tf: Transform) -> Option<Entity> {
        self.kit.spawn_static(commands, name, tf)
    }
}

/// [`CastleKit::spawn_piece`] without holding the handle; `None` when the kit (or the piece) is missing.
#[allow(dead_code)] // API for the castle rework
pub fn spawn_piece(commands: &mut Commands, name: &str, tf: Transform) -> Option<Entity> {
    CastleKit::get()?.spawn_piece(commands, name, tf)
}

// ── Showcase ─────────────────────────────────────────────────────────────────────────────────

/// X extent (lo, hi) of each piece along its row, from the Blender bounds (modular pieces use
/// their module length so they abut).
fn x_extent(name: &str) -> (f32, f32) {
    match name {
        "ck_bell_tower" => (-1.96, 1.96),
        "ck_ruin_keep" => (-3.83, 5.21),
        "ck_ruin_wall_a" => (-3.1, 3.1),
        "ck_ruin_wall_b" => (-2.16, 2.6),
        "ck_rubble" => (-1.7, 1.7),
        "ck_watchtower" => (-1.65, 1.65),
        "ck_curtain_corner" => (-0.7, 0.7),
        "ck_stone_tower" => (-2.4, 2.4),
        "ck_gatehouse" => (-3.2, 3.2),
        "ck_keep_t1" => (-4.05, 4.25),
        "ck_keep_t2" => (-3.85, 4.6),
        _ => (-2.0, 2.0), // palisade, timber gate, curtain: 4u modules
    }
}

/// (piece, gap before it, yaw). A zero gap abuts the previous piece (one modular wall run).
type Row = &'static [(&'static str, f32, f32)];
const ROWS: [(&str, f32, Row); 3] = [
    ("old colony", -18.0, &[
        ("ck_bell_tower", 0.0, 0.0),
        ("ck_ruin_keep", 5.0, 0.0),
        ("ck_ruin_wall_a", 4.0, 0.0),
        ("ck_ruin_wall_b", 3.0, 0.0),
        ("ck_rubble", 3.0, 0.0),
    ]),
    ("timber tier", 0.0, &[
        ("ck_palisade", 0.0, 0.0),
        ("ck_palisade", 0.0, 0.0),
        ("ck_timber_gate", 0.0, 0.0),
        ("ck_palisade", 0.0, 0.0),
        ("ck_palisade", 0.0, 0.0),
        ("ck_watchtower", 3.5, 0.0),
        ("ck_keep_t1", 5.0, 0.0),
    ]),
    ("stone tier", 18.0, &[
        ("ck_curtain_corner", 0.0, 0.0),
        ("ck_curtain", 0.0, 0.0),
        ("ck_curtain", 0.0, 0.0),
        ("ck_gatehouse", 0.0, 0.0),
        ("ck_curtain", 0.0, 0.0),
        ("ck_curtain", 0.0, 0.0),
        ("ck_stone_tower", 4.0, 0.0),
        ("ck_keep_t2", 5.0, 0.0),
    ]),
];

/// Half depth (Z) of the ground each row needs, for the flatness probe.
const ROW_HALF_DEPTH: f32 = 5.0;
/// Half extents of the box around the castle the showcase never enters.
const CASTLE_KEEP_OUT: Vec2 = Vec2::new(34.0, 27.0);

#[derive(Clone)]
struct Placed {
    name: &'static str,
    pos: Vec2,
    yaw: f32,
    group: usize,
}

static SHOWCASE: Mutex<Vec<Placed>> = Mutex::new(Vec::new());

pub fn showcase_enabled() -> bool {
    std::env::var("FOREST_CASTLEKIT_SHOWCASE").is_ok_and(|v| v != "0")
}

/// Local layout (origin-centred) of every row: pieces with their contiguous-run group index.
fn layout() -> Vec<Placed> {
    let mut out = Vec::new();
    let mut group = 0;
    for (_, z, row) in ROWS {
        let mut cursor = 0.0;
        let mut pieces = Vec::new();
        for (i, &(name, gap, yaw)) in row.iter().enumerate() {
            if i > 0 && gap > 0.0 {
                group += 1;
            }
            cursor += gap;
            let (lo, hi) = x_extent(name);
            let cx = cursor - lo;
            cursor = cx + hi;
            pieces.push(Placed { name, pos: Vec2::new(cx, z), yaw, group });
        }
        group += 1;
        for p in &mut pieces {
            p.pos.x -= cursor / 2.0;
        }
        out.extend(pieces);
    }
    out
}

/// Ground usable for a showcase piece at relax level `relax` (0 strict .. 2 loosest).
fn ground_ok(x: f32, z: f32, relax: usize) -> Option<f32> {
    // Keep clear of the castle (at the origin) and its planned 28 x 21 ring (zamek v2 §2).
    if x.abs() < CASTLE_KEEP_OUT.x && z.abs() < CASTLE_KEEP_OUT.y {
        return None;
    }
    let y = crate::worldmap::ground_at_world(x, z)?;
    let biome = crate::worldmap::tile_biome_world(x, z);
    let biome_ok = match relax {
        0 => matches!(biome, None | Some(Biome::Forest)),
        1 => biome != Some(Biome::Snow),
        _ => true,
    };
    (y > crate::worldmap::SEA_Y + 0.6
        && biome_ok
        && !crate::worldmap::is_river_world(x, z)
        && (relax >= 2 || !crate::roads::on_road(x, z))
        && !crate::blockers::any_visual_within(x, z, 0.5))
    .then_some(y)
}

/// Is every piece run of a row at `origin` on usable, fairly flat ground? `spans` = (x0, x1) of
/// each contiguous run / free-standing piece; the gaps between them are not probed.
fn site_ok(origin: Vec2, spans: &[(f32, f32)], relax: usize) -> bool {
    let flat = [0.7, 1.2, 2.0][relax];
    for &(x0, x1) in spans {
        let (mut lo, mut hi) = (f32::MAX, f32::MIN);
        let mut x = x0;
        while x <= x1 + 0.01 {
            for dz in [-ROW_HALF_DEPTH * 0.5, 0.0, ROW_HALF_DEPTH * 0.5] {
                let Some(y) = ground_ok(origin.x + x, origin.y + dz, relax) else { return false };
                lo = lo.min(y);
                hi = hi.max(y);
            }
            if hi - lo > flat {
                return false;
            }
            x += 2.0;
        }
    }
    true
}

/// Build-phase 4 (after the other planners, before the scatter): find open flat ground away from
/// the castle (at the world origin) for each row, the later rows as close as possible behind the
/// first, and reserve it so the forest scatter keeps off the rows.
pub fn plan() {
    SHOWCASE.lock().unwrap().clear();
    if !showcase_enabled() {
        return;
    }
    let local = layout();
    let mut placed: Vec<Placed> = Vec::new();
    let mut prev: Option<Vec2> = None;
    for (label, z, _) in ROWS {
        let row: Vec<&Placed> = local.iter().filter(|p| p.pos.y == z).collect();
        let mut spans: Vec<(usize, f32, f32)> = Vec::new();
        for p in &row {
            let (lo, hi) = x_extent(p.name);
            match spans.iter_mut().find(|s| s.0 == p.group) {
                Some(s) => s.2 = s.2.max(p.pos.x + hi),
                None => spans.push((p.group, p.pos.x + lo, p.pos.x + hi)),
            }
        }
        let spans: Vec<(f32, f32)> = spans.into_iter().map(|s| (s.1, s.2)).collect();
        // Prefer the spot right behind the previous row (+Z), else nearest the castle.
        let want = prev.map(|p| p + Vec2::new(0.0, 18.0));
        let mut best: Option<(f32, Vec2, usize)> = None;
        'relax: for relax in 0..3 {
            for ring in 0..26 {
                let r = 38.0 + ring as f32 * 5.0;
                let n = 24 + ring * 4;
                for k in 0..n {
                    let a = k as f32 * std::f32::consts::TAU / n as f32;
                    let o = Vec2::new(a.cos() * r, a.sin() * r);
                    let score = want.map_or(r, |w| o.distance(w));
                    if best.is_some_and(|b| b.0 <= score) || !site_ok(o, &spans, relax) {
                        continue;
                    }
                    let clear = placed.iter().all(|q| (q.pos.y - o.y).abs() > 11.0 || (q.pos.x - o.x).abs() > 60.0);
                    if clear {
                        best = Some((score, o, relax));
                    }
                }
            }
            if best.is_some() {
                break 'relax;
            }
        }
        let Some((_, origin, relax)) = best else {
            warn!("castle_kit showcase: no open flat ground for row '{label}'");
            continue;
        };
        info!("castle_kit showcase: row '{label}' along x at z {:.1}, centred x {:.1} (relax {relax})", origin.y, origin.x);
        prev = Some(origin);
        placed.extend(row.into_iter().map(|p| Placed { pos: Vec2::new(p.pos.x + origin.x, origin.y), ..p.clone() }));
    }
    for p in &placed {
        let (lo, hi) = x_extent(p.name);
        crate::blockers::reserve_visual(p.pos.x, p.pos.y, (hi - lo) * 0.5 + 3.0);
    }
    *SHOWCASE.lock().unwrap() = placed;
}

/// Build-phase 32: spawn the planned showcase rows. Each contiguous wall run sits at the lowest
/// ground under it (the foundations hide the rest), every free-standing piece at its own.
pub fn populate(commands: &mut Commands) {
    let placed = SHOWCASE.lock().unwrap().clone();
    if placed.is_empty() {
        return;
    }
    let Some(kit) = CastleKit::get() else {
        warn!("castle_kit: castle_kit.glb not in the kit — no showcase");
        return;
    };
    commands.insert_resource(kit);
    let foot_y = |p: &Placed| {
        let (lo, hi) = x_extent(p.name);
        let mut y = f32::MAX;
        for fx in [0.0, 0.5, 1.0] {
            for dz in [-1.2, 0.0, 1.2] {
                let x = p.pos.x + lo + (hi - lo) * fx;
                if let Some(g) = crate::worldmap::ground_at_world(x, p.pos.y + dz) {
                    y = y.min(g);
                }
            }
        }
        y
    };
    for p in &placed {
        let y = placed.iter().filter(|q| q.group == p.group).map(&foot_y).fold(f32::MAX, f32::min);
        let tf = Transform::from_xyz(p.pos.x, y, p.pos.y).with_rotation(Quat::from_rotation_y(p.yaw));
        if let Some(e) = kit.spawn_piece(commands, p.name, tf) {
            commands.entity(e).insert(BiomeEntity);
            info!("castle_kit showcase: {} at {:.1},{:.2},{:.1}", p.name, p.pos.x, y, p.pos.y);
        } else {
            warn!("castle_kit showcase: {} missing from castle_kit.glb", p.name);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn showcase_rows_do_not_overlap() {
        let l = layout();
        for (i, a) in l.iter().enumerate() {
            for b in &l[i + 1..] {
                if a.pos.y != b.pos.y {
                    continue;
                }
                let (alo, ahi) = x_extent(a.name);
                let (blo, bhi) = x_extent(b.name);
                let overlap = (a.pos.x + ahi).min(b.pos.x + bhi) - (a.pos.x + alo).max(b.pos.x + blo);
                assert!(overlap < 0.01, "{} and {} overlap by {overlap}", a.name, b.name);
            }
        }
        assert_eq!(l.len(), ROWS.iter().map(|r| r.2.len()).sum::<usize>());
        for name in PIECES {
            assert!(l.iter().any(|p| p.name == name), "{name} not in the showcase");
        }
    }
}
