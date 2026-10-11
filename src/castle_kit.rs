//! Castle fortification kit (phase 3c of `docs/superpowers/specs/2026-10-11-zamek-v2-design.md`):
//! the pieces of `assets/forest_pbr/castle_kit.glb`, built by `tools/blender_forest/castle_kit.py`.
//! That script's docstring is the manifest (every node's footprint and height).
//!
//! **Pivot convention** (every piece): ground at y = 0 (foundations sink to y = -0.3), centred on
//! its footprint, +X runs along the wall, the OUTER (enemy) face looks toward -Z, the courtyard is
//! +Z. Modular wall pieces are 4u long and tile at x = ±2 (`ck_palisade`, `ck_timber_gate`,
//! `ck_curtain`); UVs repeat whole every 2u so straight runs tile seamlessly. `ck_gatehouse` is 6.4u
//! on the wall line (its turrets project to -Z). `ck_corner_tower` (4.6 x 4.6, hoarding on top) and
//! the plain `ck_curtain_corner` (1.4 x 1.4) sit centred on the meeting point of two wall lines with
//! their outer faces on -Z and -X; the curtains attach on +X and +Z. Rotate them by -90° about Y for
//! the corner at the other end of a run (outer faces then +X and -Z, curtains on -X and +Z).
//!
//! The three story layers read without words: OLD COLONY STONE (grey, mossy, broken; the bell tower
//! alone stands whole), OUR FRESH TIMBER (peeled logs, thatch, mud ramparts), then the new dressed
//! stone of the later tiers.
//!
//! `FOREST_CASTLEKIT_SHOWCASE=1` lays every piece out in three rows on open flat ground away from the
//! castle (old colony / timber tier / stone tier), logged as `castle_kit showcase:`, for screenshots
//! beside the hero (`FOREST_HERO`). `FOREST_CASTLEKIT_SHOWCASE=old|timber|stone|keep|enceinte` instead lays
//! ONE group north-south on the flat meadow ring just outside the castle's E wall (x 37.5,
//! z -15..15), outer faces turned east; `=corner` builds a polygon-corner mock-up there (two curtain
//! runs meeting at 135° on a `ck_round_tower`).

use bevy::prelude::*;
use std::sync::Mutex;

use crate::biome::{Biome, BiomeEntity};

/// Every node in `castle_kit.glb`.
pub const PIECES: [&str; 22] = [
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
    "ck_corner_tower",
    "ck_gatehouse",
    "ck_keep_t1",
    "ck_keep_t2",
    // Irregular-polygon enceinte: fillers so runs land on a vertex, and vertex pieces that hide a
    // joint at any corner angle (105-170°). Stone runs start `ATTACH_STONE` from the vertex along
    // each edge, palisade runs `ATTACH_TIMBER`; see the manifest in castle_kit.py.
    "ck_curtain_2",
    "ck_curtain_1",
    "ck_palisade_2",
    "ck_palisade_1",
    "ck_palisade_post",
    "ck_round_tower",
    "ck_d_tower",
];

/// Distance from a polygon vertex (the `ck_round_tower` / `ck_d_tower` pivot) to where the curtain
/// runs on both edges start: the tower hides their ends at any corner angle 105-170°.
pub const ATTACH_STONE: f32 = 2.0;
/// The same for palisade runs meeting at a `ck_palisade_post`.
pub const ATTACH_TIMBER: f32 = 0.9;

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

// ── Pieces edited for the live castle ──────────────────────────────────────────────────────────

/// How the castle (`castle.rs`) edits a piece's mesh before spawning it: the live gate leaves
/// (`gates.rs`) and the live swinging bell (`castle::spawn_bell_swing`) replace the kit's baked
/// ones. Done by triangle filtering at spawn time, so a re-exported glb (same piece names, same
/// opening) keeps working without touching the Blender script.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Edit {
    None,
    /// `ck_timber_gate` without its closed leaves (the opening x ±1.38, y 0..2.7 on the wall line).
    NoLeaves,
    /// `ck_gatehouse` with the portcullis drawn up out of sight and no baked inner doors.
    OpenGatehouse,
    /// `ck_bell_tower` without its bronze bell.
    NoBell,
}

/// World-axis boxes `(min, max)` in the piece's local frame: a triangle with ALL three corners
/// inside one of them is dropped.
fn cut_boxes(edit: Edit) -> &'static [(Vec3, Vec3)] {
    const LEAVES: [(Vec3, Vec3); 1] = [(Vec3::new(-1.39, -0.05, -0.2), Vec3::new(1.39, 2.705, 0.16))];
    // Portcullis in its slot behind the outer arch (z −1.68) + the inner door leaves on the passage
    // walls (x ±1.32, z 0.92..1.88).
    const GATEHOUSE: [(Vec3, Vec3); 3] = [
        (Vec3::new(-1.36, 1.0, -1.76), Vec3::new(1.36, 2.85, -1.56)),
        (Vec3::new(1.15, -0.1, 0.55), Vec3::new(1.45, 2.6, 2.0)),
        (Vec3::new(-1.45, -0.1, 0.55), Vec3::new(-1.15, 2.6, 2.0)),
    ];
    match edit {
        Edit::NoLeaves => &LEAVES,
        Edit::OpenGatehouse => &GATEHOUSE,
        Edit::None | Edit::NoBell => &[],
    }
}

fn cut_mesh(mesh: &Mesh, boxes: &[(Vec3, Vec3)]) -> Mesh {
    use bevy::mesh::{Indices, VertexAttributeValues};
    let mut out = mesh.clone();
    let Some(VertexAttributeValues::Float32x3(pos)) = mesh.attribute(Mesh::ATTRIBUTE_POSITION) else { return out };
    let idx: Vec<u32> = match mesh.indices() {
        Some(Indices::U16(v)) => v.iter().map(|&i| i as u32).collect(),
        Some(Indices::U32(v)) => v.clone(),
        None => (0..pos.len() as u32).collect(),
    };
    let inside = |i: u32| {
        let p = Vec3::from(pos[i as usize]);
        boxes.iter().any(|(lo, hi)| p.cmpge(*lo).all() && p.cmple(*hi).all())
    };
    let kept: Vec<u32> = idx
        .chunks_exact(3)
        .filter(|t| !(inside(t[0]) && inside(t[1]) && inside(t[2])))
        .flatten()
        .copied()
        .collect();
    out.insert_indices(Indices::U32(kept));
    out
}

/// Edited part meshes per (piece, edit), built once and shared by every placement.
static EDITED: Mutex<Vec<(String, Edit, Vec<(Handle<Mesh>, usize)>)>> = Mutex::new(Vec::new());

/// Spawn castle piece `name` at `tf` with `edit` applied (see [`Edit`]); `extra` goes on the root.
/// `None` when the kit or the piece is missing.
pub fn spawn_piece_edited<B: Bundle>(
    commands: &mut Commands,
    meshes: &mut Assets<Mesh>,
    name: &str,
    tf: Transform,
    edit: Edit,
    extra: B,
) -> Option<Entity> {
    let kit = CastleKit::get()?.kit;
    let parts = kit.parts_of(name)?;
    let mut cache = EDITED.lock().unwrap();
    // Handles from an earlier world build stay valid (the mesh assets live as long as the handle).
    let built = match cache.iter().position(|(n, e, _)| n == name && *e == edit) {
        Some(i) => cache[i].2.clone(),
        None => {
            let boxes = cut_boxes(edit);
            let v: Vec<(Handle<Mesh>, usize)> = parts
                .iter()
                .filter(|p| !(edit == Edit::NoBell && kit.mat_is(p.mat, "bronze")))
                .map(|p| {
                    let h = if boxes.is_empty() { p.handle.clone() } else { meshes.add(cut_mesh(&p.mesh, boxes)) };
                    (h, p.mat)
                })
                .collect();
            cache.push((name.to_string(), edit, v.clone()));
            v
        }
    };
    drop(cache);
    let mut e = commands.spawn((tf, Visibility::default(), extra));
    e.with_children(|c| {
        for (h, mat) in built {
            let mut part = c.spawn((Mesh3d(h), Transform::IDENTITY));
            kit.insert_mat(mat, &mut part);
        }
    });
    Some(e.id())
}

// ── Showcase ─────────────────────────────────────────────────────────────────────────────────

/// (x lo, x hi, z lo, z hi) footprint of the corner pieces (the +X / +Z sides are where curtains
/// attach, so they count only to the tower face).
fn corner_footprint(name: &str) -> Option<(f32, f32, f32, f32)> {
    match name {
        "ck_corner_tower" => Some((-3.62, 2.3, -3.62, 2.3)),
        "ck_curtain_corner" => Some((-0.95, 0.7, -0.95, 0.7)),
        _ => None,
    }
}

/// X extent (lo, hi) of piece `name` turned by `yaw` (0 or ±90°) along its row, from the Blender
/// bounds (modular pieces use their module length so they abut).
fn x_extent(name: &str, yaw: f32) -> (f32, f32) {
    if let Some((x0, x1, z0, z1)) = corner_footprint(name) {
        return if yaw.abs() < 0.1 {
            (x0, x1)
        } else if yaw < 0.0 {
            (-z1, -z0)
        } else {
            (z0, z1)
        };
    }
    match name {
        "ck_bell_tower" => (-1.96, 1.96),
        "ck_ruin_keep" => (-3.83, 5.21),
        "ck_ruin_wall_a" => (-3.1, 3.1),
        "ck_ruin_wall_b" => (-2.16, 2.6),
        "ck_rubble" => (-1.7, 1.7),
        "ck_watchtower" => (-1.65, 1.65),
        "ck_stone_tower" => (-2.8, 2.8),
        "ck_gatehouse" => (-3.2, 3.2),
        "ck_keep_t1" => (-4.05, 4.25),
        "ck_keep_t2" => (-4.45, 4.82),
        "ck_curtain_2" | "ck_palisade_2" => (-1.0, 1.0),
        "ck_curtain_1" | "ck_palisade_1" => (-0.5, 0.5),
        // vertex pieces: the runs attach this far out (inside the tower / post cluster)
        "ck_round_tower" | "ck_d_tower" => (-ATTACH_STONE, ATTACH_STONE),
        "ck_palisade_post" => (-ATTACH_TIMBER, ATTACH_TIMBER),
        _ => (-2.0, 2.0), // palisade, timber gate, curtain: 4u modules
    }
}

/// (piece, gap before it, yaw). A zero gap abuts the previous piece (one modular wall run).
type Row = &'static [(&'static str, f32, f32)];
const ROWS: [(&str, f32, Row); 4] = [
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
        ("ck_corner_tower", 0.0, -std::f32::consts::FRAC_PI_2),
        ("ck_stone_tower", 4.0, 0.0),
        ("ck_keep_t2", 5.0, 0.0),
    ]),
    ("enceinte", 36.0, &[
        ("ck_round_tower", 0.0, 0.0),
        ("ck_curtain_2", 0.0, 0.0),
        ("ck_curtain_1", 0.0, 0.0),
        ("ck_d_tower", 0.0, 0.0),
        ("ck_palisade_post", 4.0, 0.0),
        ("ck_palisade_2", 0.0, 0.0),
        ("ck_palisade_1", 0.0, 0.0),
    ]),
];

/// Groups for `FOREST_CASTLEKIT_SHOWCASE=<group>`: one row, ≤31u long, laid north-south (row yaw
/// -90°: local +X -> world +Z, outer faces -Z -> +X, east) at x = `STRIP_X`, centred on z = 0.
const STRIP_ROWS: [(&str, Row); 5] = [
    ("old", &[
        ("ck_bell_tower", 0.0, 0.0),
        ("ck_ruin_keep", 3.0, 0.0),
        ("ck_ruin_wall_a", 3.0, 0.0),
        ("ck_rubble", 2.0, 0.0),
    ]),
    ("timber", &[
        ("ck_palisade", 0.0, 0.0),
        ("ck_timber_gate", 0.0, 0.0),
        ("ck_palisade", 0.0, 0.0),
        ("ck_watchtower", 3.0, 0.0),
        ("ck_keep_t1", 3.0, 0.0),
    ]),
    ("stone", &[
        ("ck_curtain_corner", 0.0, 0.0),
        ("ck_curtain", 0.0, 0.0),
        ("ck_gatehouse", 0.0, 0.0),
        ("ck_curtain", 0.0, 0.0),
        ("ck_corner_tower", 0.0, -std::f32::consts::FRAC_PI_2),
    ]),
    ("keep", &[
        ("ck_stone_tower", 0.0, 0.0),
        ("ck_keep_t2", 4.0, 0.0),
        ("ck_ruin_wall_b", 3.0, 0.0),
    ]),
    ("enceinte", &[
        ("ck_round_tower", 0.0, 0.0),
        ("ck_curtain_2", 0.0, 0.0),
        ("ck_curtain_1", 0.0, 0.0),
        ("ck_d_tower", 0.0, 0.0),
        ("ck_palisade_post", 4.0, 0.0),
        ("ck_palisade_2", 0.0, 0.0),
        ("ck_palisade_1", 0.0, 0.0),
    ]),
];
/// The open meadow ring outside the castle's E wall (zamek v2: flat grass, nothing built there).
const STRIP_X: f32 = 37.5;

/// Half depth (Z) of the ground each row needs, for the flatness probe.
const ROW_HALF_DEPTH: f32 = 5.0;
/// Half extents of the box around the castle the showcase never enters.
const CASTLE_KEEP_OUT: Vec2 = Vec2::new(34.0, 27.0);

#[derive(Clone)]
struct Placed {
    name: &'static str,
    /// World (x, z) of the piece pivot (in `layout`: x along the row, z = the row's z).
    pos: Vec2,
    /// The piece's own yaw within its row (what `x_extent` takes).
    yaw: f32,
    group: usize,
    /// Yaw of the whole row: 0 (runs along +X), -90° (along +Z, the E-ring strip) or any angle
    /// (the corner mock-up).
    row_yaw: f32,
}

impl Placed {
    /// Unit direction the row runs in (local +X turned by `row_yaw`), in world (x, z).
    fn along(&self) -> Vec2 {
        Vec2::new(self.row_yaw.cos(), -self.row_yaw.sin())
    }
}

static SHOWCASE: Mutex<Vec<Placed>> = Mutex::new(Vec::new());

pub fn showcase_enabled() -> bool {
    std::env::var("FOREST_CASTLEKIT_SHOWCASE").is_ok_and(|v| v != "0")
}

/// One row laid out along x, centred on 0, at `z`: pieces with their contiguous-run group index
/// (counting on from `group`, which is left at the next free index).
fn layout_row(row: Row, z: f32, group: &mut usize) -> Vec<Placed> {
    let mut cursor = 0.0;
    let mut pieces = Vec::new();
    for (i, &(name, gap, yaw)) in row.iter().enumerate() {
        if i > 0 && gap > 0.0 {
            *group += 1;
        }
        cursor += gap;
        let (lo, hi) = x_extent(name, yaw);
        let cx = cursor - lo;
        cursor = cx + hi;
        pieces.push(Placed { name, pos: Vec2::new(cx, z), yaw, group: *group, row_yaw: 0.0 });
    }
    *group += 1;
    for p in &mut pieces {
        p.pos.x -= cursor / 2.0;
    }
    pieces
}

/// Local layout (origin-centred) of every row: pieces with their contiguous-run group index.
fn layout() -> Vec<Placed> {
    let mut group = 0;
    ROWS.iter().flat_map(|&(_, z, row)| layout_row(row, z, &mut group)).collect()
}

/// `FOREST_CASTLEKIT_SHOWCASE=corner`: a polygon-corner mock-up on the E ring — two curtain runs
/// (4 + 4 + 2 + 1 u each) meeting at a 135° corner with a `ck_round_tower` on the vertex at
/// (41, 0); the outward bisector points east (+X), the yard lies west.
fn corner_mockup() -> Vec<Placed> {
    let vertex = Vec2::new(41.0, 0.0);
    let outward = Vec2::X;
    let half = (135.0f32 / 2.0).to_radians();
    // yaw turning local +X to `dir` (Bevy: local +X -> (cos θ, -sin θ) in x, z)
    let yaw_of = |dir: Vec2| (-dir.y).atan2(dir.x);
    let mut out = vec![Placed { name: "ck_round_tower", pos: vertex, yaw: 0.0, group: 0, row_yaw: -std::f32::consts::FRAC_PI_2 }];
    for side in [-1.0f32, 1.0] {
        // the run leaves the vertex into the yard side, half the corner angle off the inward bisector
        let dir = Vec2::new(-half.cos(), side * half.sin());
        let mut d = ATTACH_STONE;
        for (name, len) in [("ck_curtain", 4.0), ("ck_curtain", 4.0), ("ck_curtain_2", 2.0), ("ck_curtain_1", 1.0)] {
            // local +X along ±dir, whichever puts the outer face (local -Z) toward the outside
            let mut x_dir = dir;
            let outer = |x: Vec2| Vec2::new(x.y, -x.x); // local -Z for local +X = x (Bevy yaw about +Y)
            if outer(x_dir).dot(outward) < 0.0 {
                x_dir = -x_dir;
            }
            out.push(Placed { name, pos: vertex + dir * (d + len / 2.0), yaw: 0.0, group: 0, row_yaw: yaw_of(x_dir) });
            d += len;
        }
    }
    out
}

/// `FOREST_CASTLEKIT_SHOWCASE=<group>`: that group north-south on the E-ring strip.
fn strip(row: Row) -> Vec<Placed> {
    layout_row(row, 0.0, &mut 0)
        .into_iter()
        .map(|p| Placed { pos: Vec2::new(STRIP_X, p.pos.x), row_yaw: -std::f32::consts::FRAC_PI_2, ..p })
        .collect()
}

/// Ground usable for a showcase piece at relax level `relax` (0 strict meadow .. 3 loosest).
fn ground_ok(x: f32, z: f32, relax: usize) -> Option<f32> {
    // Keep clear of the castle (at the origin) and its planned 28 x 21 ring (zamek v2 §2).
    if x.abs() < CASTLE_KEEP_OUT.x && z.abs() < CASTLE_KEEP_OUT.y {
        return None;
    }
    let y = crate::worldmap::ground_at_world(x, z)?;
    let biome = crate::worldmap::tile_biome_world(x, z);
    let biome_ok = match relax {
        0 | 1 => matches!(biome, None | Some(Biome::Forest)),
        2 => !matches!(biome, Some(Biome::Snow | Biome::Rocky)), // rocky mesas: cliff walls
        _ => true,
    };
    (y > crate::worldmap::SEA_Y + 0.6
        && biome_ok
        && !crate::worldmap::is_river_world(x, z)
        && (relax >= 1 || !crate::roads::on_road(x, z))
        && !crate::blockers::any_visual_within(x, z, 0.5))
    .then_some(y)
}

/// Is every piece run of a row at `origin` on usable, fairly flat ground? `spans` = (x0, x1) of
/// each contiguous run / free-standing piece; the gaps between them are not probed.
fn site_ok(origin: Vec2, spans: &[(f32, f32)], relax: usize) -> bool {
    let flat = [0.8, 1.6, 1.6, 2.0][relax];
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
    let want = std::env::var("FOREST_CASTLEKIT_SHOWCASE").unwrap_or_default();
    let group = STRIP_ROWS.iter().find(|r| r.0 == want.trim()).map(|&(label, row)| (label, strip(row)));
    let group = group.or_else(|| (want.trim() == "corner").then(|| ("corner", corner_mockup())));
    if let Some((label, placed)) = group {
        info!("castle_kit showcase: group '{label}' north-south at x {STRIP_X} (E ring)");
        for p in &placed {
            let (lo, hi) = x_extent(p.name, p.yaw);
            crate::blockers::reserve_visual(p.pos.x, p.pos.y, (hi - lo) * 0.5 + 3.0);
        }
        *SHOWCASE.lock().unwrap() = placed;
        return;
    }
    let local = layout();
    let mut placed: Vec<Placed> = Vec::new();
    let mut prev: Option<Vec2> = None;
    for (label, z, _) in ROWS {
        let row: Vec<&Placed> = local.iter().filter(|p| p.pos.y == z).collect();
        let mut spans: Vec<(usize, f32, f32)> = Vec::new();
        for p in &row {
            let (lo, hi) = x_extent(p.name, p.yaw);
            match spans.iter_mut().find(|s| s.0 == p.group) {
                Some(s) => s.2 = s.2.max(p.pos.x + hi),
                None => spans.push((p.group, p.pos.x + lo, p.pos.x + hi)),
            }
        }
        let spans: Vec<(f32, f32)> = spans.into_iter().map(|s| (s.1, s.2)).collect();
        // Prefer the spot right behind the previous row (+Z), else nearest the castle.
        let want = prev.map(|p| p + Vec2::new(0.0, 18.0));
        let mut best: Option<(f32, Vec2, usize)> = None;
        'relax: for relax in 0..4 {
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
        let (lo, hi) = x_extent(p.name, p.yaw);
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
        let (lo, hi) = x_extent(p.name, p.yaw);
        let (along, across) = (p.along(), p.along().perp());
        let mut y = f32::MAX;
        for fx in [0.0, 0.5, 1.0] {
            for dz in [-1.2, 0.0, 1.2] {
                let q = p.pos + along * (lo + (hi - lo) * fx) + across * dz;
                if let Some(g) = crate::worldmap::ground_at_world(q.x, q.y) {
                    y = y.min(g);
                }
            }
        }
        y
    };
    for p in &placed {
        let y = placed.iter().filter(|q| q.group == p.group).map(&foot_y).fold(f32::MAX, f32::min);
        let tf = Transform::from_xyz(p.pos.x, y, p.pos.y).with_rotation(Quat::from_rotation_y(p.row_yaw + p.yaw));
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
                let (alo, ahi) = x_extent(a.name, a.yaw);
                let (blo, bhi) = x_extent(b.name, b.yaw);
                let overlap = (a.pos.x + ahi).min(b.pos.x + bhi) - (a.pos.x + alo).max(b.pos.x + blo);
                assert!(overlap < 0.01, "{} and {} overlap by {overlap}", a.name, b.name);
            }
        }
        assert_eq!(l.len(), ROWS.iter().map(|r| r.2.len()).sum::<usize>());
        for name in PIECES {
            assert!(l.iter().any(|p| p.name == name), "{name} not in the showcase");
            assert!(STRIP_ROWS.iter().any(|r| r.1.iter().any(|q| q.0 == name)), "{name} in no E-ring group");
        }
        // Each E-ring group fits the strip (z -16..16) without overlaps.
        for (label, row) in STRIP_ROWS {
            let s = strip(row);
            for (i, a) in s.iter().enumerate() {
                let (alo, ahi) = x_extent(a.name, a.yaw);
                assert!(a.pos.y + alo > -16.0 && a.pos.y + ahi < 16.0, "group {label}: {} off the strip", a.name);
                for b in &s[i + 1..] {
                    let (blo, bhi) = x_extent(b.name, b.yaw);
                    let overlap = (a.pos.y + ahi).min(b.pos.y + bhi) - (a.pos.y + alo).max(b.pos.y + blo);
                    assert!(overlap < 0.01, "group {label}: {} and {} overlap", a.name, b.name);
                }
            }
        }
    }
}
