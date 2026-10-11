//! **Micro-POIs + flags** (map-character overhaul pass 4) — the 40-second-rule layer: bigger
//! roadside set-pieces spaced along the arteries so a traveller always has something ahead
//! (CDPR's rule: something interesting every ~40 s of travel), plus the "weenie" FLAGS that
//! pull the eye from far away — smoke columns over Gnashfang Hold and crows wheeling above it.
//! (The town's farmland is ground now — `castle_ground::field_at`, not meshes.)
//!
//! Set-pieces (all vertex-coloured merged primitives, base y=0, ruins.rs contract): a gallows
//! frame on the fortress approach, a burned-out cabin, wayside graves, a standing-stone circle,
//! a collapsed wooden watchtower, a shepherd's hut with a pen. Environmental storytelling à la
//! RDR2 — no interaction, no text; each is a told-without-words scene beside the road.
//! With the realistic forest kit loaded, the set-pieces and the gallows are Blender models instead
//! (`wayside.glb`, see [`STORY_KIT`]) on the same footprints and blocker boxes.
//!
//! Placement is planned at build phase 4, before any scatter ([`plan_clearings`]): every story
//! kind gets exactly ONE spot, reserved at once. The gallows goes first, onto the Gnashfang
//! approach; then a deterministic arc-length walk along the artery polylines (like `wayside`, but
//! ~90–130u spacing and 6–13u OFF the road) offers each stop to the kinds still waiting, rejecting
//! water/roads/plots/camps/landmarks/mesa shelves/the Blight/blockers — a stop that can't take one
//! kind takes the next, and denser fallback walks seat any kind the rhythm couldn't. At phase 32
//! ([`populate`]) a site some later phase claimed after all is re-sited, never dropped.

use std::f32::consts::{FRAC_PI_2, TAU};

use bevy::camera::visibility::VisibilityRange;
use bevy::prelude::*;

use crate::biome::BiomeEntity;
use crate::palette::lin;

pub struct PoiPlugin;
impl Plugin for PoiPlugin {
    fn build(&self, app: &mut App) {
        app.add_systems(Update, (rise_smoke, wheel_crows));
    }
}

// ── Flags: smoke + crows ────────────────────────────────────────────────────────────
/// One rising smoke mote of a tall column (the cheapest far-visible "weenie" there is).
#[derive(Component)]
struct SmokeMote {
    base: Vec3,
    speed: f32,
    phase: f32,
    /// Column height this mote cycles over (taller than a campfire's little puffs).
    rise: f32,
}

fn rise_smoke(time: Res<Time>, mut q: Query<(&SmokeMote, &mut Transform)>) {
    let t = time.elapsed_secs();
    for (s, mut tf) in &mut q {
        let cycle = (t * s.speed + s.phase).rem_euclid(1.0);
        tf.translation = s.base
            + Vec3::new(
                (t * 0.35 + s.phase * 5.0).sin() * (0.4 + cycle * 1.6),
                cycle * s.rise,
                (t * 0.30 + s.phase * 4.0).cos() * (0.4 + cycle * 1.6),
            );
        // Grow then thin out: big soft puffs mid-column, dissolving at the top.
        let sc = (0.5 + cycle * 1.7) * (1.0 - cycle * cycle).max(0.0);
        tf.scale = Vec3::splat(sc.max(0.01));
    }
}

/// A crow wheeling on a slow circle — a handful over the fortress sell "something dead lives
/// there" from across the island.
#[derive(Component)]
struct Crow {
    centre: Vec3,
    radius: f32,
    speed: f32,
    phase: f32,
}

fn wheel_crows(time: Res<Time>, mut q: Query<(&Crow, &mut Transform)>) {
    let t = time.elapsed_secs();
    for (c, mut tf) in &mut q {
        let a = t * c.speed + c.phase;
        let bob = (t * 1.7 + c.phase * 3.0).sin() * 0.8;
        tf.translation = c.centre + Vec3::new(a.cos() * c.radius, bob, a.sin() * c.radius);
        // Face along the flight direction (tangent).
        tf.rotation = Quat::from_rotation_y(-a - FRAC_PI_2);
    }
}

// ── Mesh helpers (ruins/vignettes contract) ─────────────────────────────────────────
fn tint(mut m: Mesh, col: u32) -> Mesh {
    let n = m.count_vertices();
    m.insert_attribute(Mesh::ATTRIBUTE_COLOR, vec![lin(col); n]);
    m
}
fn bx(w: f32, h: f32, d: f32, c: Vec3, col: u32) -> Mesh {
    tint(Cuboid::new(w, h, d).mesh().build().translated_by(c), col)
}
fn bxr(w: f32, h: f32, d: f32, rot: Quat, c: Vec3, col: u32) -> Mesh {
    tint(Cuboid::new(w, h, d).mesh().build().rotated_by(rot).translated_by(c), col)
}
fn cyl(r: f32, h: f32, c: Vec3, col: u32) -> Mesh {
    tint(Cylinder::new(r, h).mesh().resolution(7).build().translated_by(c), col)
}
fn ball(r: f32, c: Vec3, squash: f32, col: u32) -> Mesh {
    tint(
        Sphere::new(r).mesh().ico(1).unwrap().scaled_by(Vec3::new(1.0, squash, 1.0)).translated_by(c),
        col,
    )
}
fn assemble(parts: Vec<Mesh>) -> Mesh {
    let mut it = parts.into_iter();
    let mut base = it.next().expect("at least one part");
    for part in it {
        base.merge(&part).expect("parts share attributes");
    }
    base.duplicate_vertices();
    base.compute_flat_normals();
    base
}

fn fence_rail(centre: Vec3, yaw: f32, length: f32) -> Mesh {
    // Lay the upright cylinder along X before turning it around the world Y axis.
    // The opposite order spins the upright cylinder in place and leaves every rail along X.
    tint(Cylinder::new(0.03, length).mesh().resolution(6).build()
        .rotated_by(Quat::from_rotation_y(yaw) * Quat::from_rotation_z(FRAC_PI_2))
        .translated_by(centre), WOOD)
}

const WOOD: u32 = 0x5c4226;
const WOOD_DK: u32 = 0x453018;
const CHAR: u32 = 0x1f1a14;
const ASH: u32 = 0x4a463e;
const STONE: u32 = 0x83878d;
const STONE_DK: u32 = 0x64686e;
const MOUND: u32 = 0x5d4a32;
const ROPE: u32 = 0x8f7b52;
const THATCH: u32 = 0x8c7440;

/// Gallows frame on the fortress approach: two posts, a crossbeam, a frayed rope stub swaying
/// over a trapdoor platform. Grim and empty — the story tells itself.
fn gallows() -> Mesh {
    let mut v = Vec::new();
    v.push(bx(2.2, 0.28, 1.6, Vec3::new(0.0, 0.5, 0.0), WOOD_DK)); // platform
    for sx in [-0.9_f32, 0.9] {
        v.push(bx(0.3, 0.5, 1.3, Vec3::new(sx, 0.2, 0.0), WOOD)); // platform legs
    }
    v.push(cyl(0.09, 2.6, Vec3::new(-0.85, 1.9, 0.0), WOOD)); // upright
    v.push(bxr(1.9, 0.14, 0.14, Quat::IDENTITY, Vec3::new(0.05, 3.15, 0.0), WOOD)); // crossbeam
    v.push(bxr(0.5, 0.12, 0.12, Quat::from_rotation_z(-0.7), Vec3::new(-0.55, 2.95, 0.0), WOOD_DK)); // brace
    v.push(cyl(0.025, 0.55, Vec3::new(0.72, 2.85, 0.0), ROPE)); // rope stub
    v.push(ball(0.06, Vec3::new(0.72, 2.56, 0.0), 1.0, ROPE)); // knot
    assemble(v)
}

/// Burned-out cabin: charred corner posts, one collapsed wall, fallen roof beams in an ash bed.
fn burned_cabin() -> Mesh {
    let mut v = Vec::new();
    v.push(ball(1.6, Vec3::new(0.0, 0.04, 0.0), 0.16, ASH)); // ash bed
    for (sx, sz, h) in [(-1.1_f32, -0.9_f32, 1.5_f32), (1.1, -0.9, 1.1), (-1.1, 0.9, 0.8), (1.1, 0.9, 1.3)] {
        v.push(bxr(0.22, h, 0.22, Quat::from_rotation_x(0.06) * Quat::from_rotation_z(0.05), Vec3::new(sx, h * 0.5, sz), CHAR));
    }
    v.push(bx(2.4, 0.7, 0.16, Vec3::new(0.0, 0.35, -0.95), CHAR)); // surviving half-wall
    for (a, y) in [(0.5_f32, 0.28_f32), (-0.9, 0.2), (1.9, 0.35)] {
        v.push(bxr(2.0, 0.12, 0.12, Quat::from_rotation_y(a) * Quat::from_rotation_z(0.10), Vec3::new(0.1, y, 0.1), CHAR));
    }
    v.push(bx(0.5, 0.4, 0.4, Vec3::new(0.9, 0.2, 0.6), WOOD_DK)); // one unburnt crate
    assemble(v)
}

/// A pair of wayside graves: mounds, a wooden cross, a headstone.
fn graves() -> Mesh {
    let mut v = Vec::new();
    for (dx, rot) in [(-0.7_f32, 0.12_f32), (0.7, -0.08)] {
        v.push(tint(
            Sphere::new(0.55).mesh().ico(1).unwrap().scaled_by(Vec3::new(1.0, 0.35, 1.7)).rotated_by(Quat::from_rotation_y(rot)).translated_by(Vec3::new(dx, 0.1, 0.0)),
            MOUND,
        ));
    }
    v.push(cyl(0.05, 0.9, Vec3::new(-0.7, 0.45, -0.75), WOOD)); // cross upright
    v.push(bx(0.5, 0.09, 0.09, Vec3::new(-0.7, 0.68, -0.75), WOOD)); // cross arm
    v.push(bxr(0.5, 0.6, 0.14, Quat::from_rotation_z(0.08), Vec3::new(0.7, 0.3, -0.8), STONE)); // headstone
    assemble(v)
}

/// Standing-stone circle: 6 weathered monoliths, one toppled.
fn standing_stones() -> Mesh {
    let mut v = Vec::new();
    for k in 0..6 {
        let a = k as f32 * (TAU / 6.0);
        let (r, h) = (2.3, 1.2 + (k as f32 * 2.1).sin().abs() * 0.9);
        if k == 4 {
            // The fallen one.
            v.push(bxr(0.6, 0.35, 1.6, Quat::from_rotation_y(a + 0.5), Vec3::new(a.cos() * r, 0.18, a.sin() * r), STONE_DK));
        } else {
            v.push(bxr(
                0.55,
                h,
                0.35,
                Quat::from_rotation_y(a) * Quat::from_rotation_z((k as f32 * 1.3).sin() * 0.08),
                Vec3::new(a.cos() * r, h * 0.5, a.sin() * r),
                if k % 2 == 0 { STONE } else { STONE_DK },
            ));
        }
    }
    v.push(ball(0.5, Vec3::ZERO, 0.3, STONE_DK)); // centre altar stump
    assemble(v)
}

/// Collapsed WOODEN watchtower (the stone one is a Rocky vignette): a leaning frame, snapped
/// legs, the fallen platform against it.
fn fallen_watchtower() -> Mesh {
    let lean = Quat::from_rotation_z(0.22);
    let mut v = Vec::new();
    for (sx, sz) in [(-0.7_f32, -0.7_f32), (0.7, -0.7), (-0.7, 0.7)] {
        v.push(bxr(0.16, 2.6, 0.16, lean, Vec3::new(sx + 0.25, 1.25, sz), WOOD));
    }
    v.push(bxr(0.16, 1.1, 0.16, Quat::from_rotation_z(1.1), Vec3::new(1.3, 0.4, 0.7), WOOD_DK)); // snapped leg
    v.push(bxr(1.7, 0.12, 1.7, lean * Quat::from_rotation_x(0.15), Vec3::new(0.55, 2.55, 0.0), WOOD_DK)); // tilted platform
    v.push(bxr(1.5, 0.7, 0.1, Quat::from_rotation_z(0.9), Vec3::new(1.6, 0.5, -0.4), WOOD)); // fallen parapet
    for (a, l) in [(0.3_f32, 1.4_f32), (-0.8, 1.1)] {
        v.push(bxr(l, 0.1, 0.1, Quat::from_rotation_y(a), Vec3::new(0.6, 0.1, 0.5), WOOD_DK)); // debris
    }
    assemble(v)
}

/// Shepherd's hut + a small fenced pen.
fn shepherd_hut() -> Mesh {
    let mut v = Vec::new();
    v.push(bx(1.6, 1.0, 1.3, Vec3::new(-1.0, 0.5, 0.0), WOOD)); // hut body
    for s in [-1.0_f32, 1.0] {
        v.push(bxr(1.05, 0.07, 1.6, Quat::from_rotation_z(s * 0.55), Vec3::new(-1.0 + s * 0.42, 1.25, 0.0), THATCH));
    }
    v.push(bx(0.4, 0.55, 0.06, Vec3::new(-1.0, 0.28, 0.66), WOOD_DK)); // door
    // Pen: posts + rails around a small square to the east.
    for (px, pz) in [(0.2_f32, -1.0_f32), (1.8, -1.0), (0.2, 1.0), (1.8, 1.0)] {
        v.push(cyl(0.05, 0.6, Vec3::new(px, 0.3, pz), WOOD_DK));
    }
    for (c, rot, l) in [
        (Vec3::new(1.0, 0.42, -1.0), 0.0_f32, 1.6_f32),
        (Vec3::new(1.0, 0.42, 1.0), 0.0, 1.6),
        (Vec3::new(1.8, 0.42, 0.0), FRAC_PI_2, 2.0),
    ] {
        v.push(fence_rail(c, rot, l));
    }
    assemble(v)
}

// ── Placement ────────────────────────────────────────────────────────────────────────
/// Reserved visual radius per story kind. Kinds `0..ROADSIDE_KINDS` are the roadside
/// set-pieces; the last one is the gallows ([`GALLOWS`]), which belongs on the fortress approach.
const STORY_FOOTPRINTS: [f32; 6] = [1.9, 1.4, 3.25, 2.4, 2.3, 2.0];
/// The realistic kit's model for each story kind (`wayside.glb`, tools/blender_forest/wayside_models.py),
/// authored to the same footprints and blocker boxes as the low-poly meshes above.
const STORY_KIT: [&str; 6] = ["poi_burned_cabin", "poi_graves", "poi_stones", "poi_watchtower", "poi_shepherd_hut", "poi_gallows"];
/// Roadside kinds: each is planned exactly once along the arteries.
const ROADSIDE_KINDS: usize = 5;
/// The gallows' kind index (planned first, onto the Gnashfang approach).
const GALLOWS: usize = 5;
/// Keep-out around an ork camp centre beyond its flat clearing: tents, cage and guy ropes
/// (`realforest::keep_clear` uses the same reach).
const CAMP_KEEP: f32 = 7.0;
/// Margin past the castle's grass safe ring (world radius `SAFE_R × MAP_SCALE` ≈ 32u): the town
/// meadow — hay corner, beehives, rest campfire, tree clumps (`meadow.rs`, phase 29) — fills that
/// ring without consulting the plan, and a story piece belongs on the road OUT, not in the village.
const TOWN_KEEP: f32 = 4.0;
/// Keep-out around a biome landmark's centre: its Rune-Trial arena (`landmarks::RUNE_R` = 8u, where
/// the guardians spawn and the fight happens) plus a gap, so a story piece never crowds or competes
/// with a landmark (the old walk put the burned cabin at the foot of the Sunken Pyramid).
const LANDMARK_KEEP: f32 = 14.0;

#[derive(Clone)]
struct StorySite { kind: usize, pos: Vec2, yaw: f32 }
static STORY_SITES: std::sync::Mutex<Vec<StorySite>> = std::sync::Mutex::new(Vec::new());

pub fn reset_plan() { STORY_SITES.lock().unwrap().clear(); }

/// Extra clear radius around a cold story site (see [`story_clearings`]).
const COLD_SIGHTLINE: f32 = 3.5;

pub struct StoryClearings(Vec<(Vec2, f32)>);
impl StoryClearings {
    pub fn overlaps(&self, x: f32, z: f32, radius: f32) -> bool {
        let p = Vec2::new(x, z);
        self.0.iter().any(|(pos, foot)| p.distance_squared(*pos) < (foot + radius + 0.35).powi(2))
    }
}
/// Every spot the world build has planned for a later set-piece — the roadside story clearings
/// and the gallows, plus the wayside furniture and the forest vignette (`wayside::plan` /
/// `vignettes::plan`) — so the biome scatter (trees, props, cover, in every biome) leaves them free.
pub fn story_clearings() -> StoryClearings {
    let mut spots: Vec<(Vec2, f32)> =
        STORY_SITES.lock().unwrap().iter().map(|site| (site.pos, STORY_FOOTPRINTS[site.kind])).collect();
    spots.extend(crate::wayside::planned_footprints());
    spots.extend(crate::vignettes::planned_footprint());
    spots.extend(crate::stories_warm::planned_footprints());
    // The cold sites stand out in the snow forest: a wider glade (no trunks or crowns right up to
    // the drift) so the scene reads from a distance instead of through a screen of branches.
    spots.extend(crate::stories_cold::planned_footprints().into_iter().map(|(p, foot)| (p, foot + COLD_SIGHTLINE)));
    StoryClearings(spots)
}
/// Does a circle at `(x, z)` of radius `radius` overlap a planned story clearing (gallows
/// included)? Every placer that runs between the phase-4 plan and phase 32 must ask this.
pub fn overlaps_planned_clearing(x: f32, z: f32, radius: f32) -> bool {
    let p = Vec2::new(x, z);
    STORY_SITES.lock().unwrap().iter().any(|site| {
        p.distance_squared(site.pos) < (STORY_FOOTPRINTS[site.kind] + radius + 0.35).powi(2)
    }) || crate::stories_warm::overlaps_planned(x, z, radius)
        || crate::stories_cold::overlaps_planned(x, z, radius)
}

fn rng_next(state: &mut u32) -> f32 {
    *state = state.wrapping_add(0x6d2b_79f5);
    let mut t = *state;
    t = (t ^ (t >> 15)).wrapping_mul(t | 1);
    t ^= t.wrapping_add((t ^ (t >> 7)).wrapping_mul(t | 61));
    ((t ^ (t >> 14)) as f32) / 4_294_967_296.0
}

/// Flat, unclaimed, dry, off-road land — same discipline as `wayside::spot_ok` but with a wider
/// flatness probe (these set-pieces have real footprints).
fn spot_ok(x: f32, z: f32, probe: f32) -> bool {
    !crate::blockers::any_visual_within(x, z, probe + 0.2) && site_ok(x, z, probe)
}

/// [`spot_ok`] minus the visual-reservation test: a planned clearing reserves its own footprint
/// at plan time, so at spawn only the ground rules and later SOLIDS are re-checked.
pub(crate) fn site_ok(x: f32, z: f32, probe: f32) -> bool {
    let Some(y0) = crate::worldmap::ground_at_world(x, z) else { return false };
    // An outer ring at the footprint edge (flatness + every keep-out) and an inner one at half
    // radius, so a river channel, pool or trail can't slip between the outer probes.
    for (n, r) in [(12, probe), (6, probe * 0.5)] {
        for k in 0..n {
            let a = k as f32 * (TAU / n as f32);
            let (px, pz) = (x + a.cos() * r, z + a.sin() * r);
            match crate::worldmap::ground_at_world(px, pz) {
                Some(y) if (y - y0).abs() <= 0.30 => {}
                _ => return false,
            }
            if crate::roads::on_road(px, pz)
                || crate::worldmap::is_river_world(px, pz)
                || crate::worldmap::is_pool_world(px, pz)
                || crate::town::near_build_plot(px, pz)
                || crate::castle::in_footprint(px, pz)
                || crate::camps::in_clearing(px, pz)
                || crate::rival::near_fort(px, pz)
                || crate::ruins::near_landmark_visual_footprint(px, pz)
            { return false; }
        }
    }
    !crate::roads::on_road(x, z)
        && !crate::town::near_build_plot(x, z)
        && !crate::castle::in_footprint(x, z)
        && !crate::camps::in_clearing(x, z)
        && !crate::rival::near_fort(x, z)
        && !crate::worldmap::cliff_shelf_world(x, z)
        && !crate::ruins::near_landmark_visual_footprint(x, z)
        && !crate::worldmap::is_pool_world(x, z)
        && !crate::worldmap::is_river_world(x, z)
        && !crate::bridges::near_bridge(x, z, probe + 0.5)
}

/// Register each solid mass in model-local space, rotated together with the visible mesh.
fn register_story_blockers(kind: usize, p: Vec2, yaw: f32) {
    let rotation = Quat::from_rotation_y(yaw);
    let local_box = |x: f32, z: f32, hw: f32, hd: f32, local_yaw: f32| {
        let offset = rotation * Vec3::new(x, 0.0, z);
        crate::blockers::add_obb(p.x + offset.x, p.y + offset.z, hw, hd, yaw + local_yaw);
    };
    match kind {
        0 => local_box(0.0, 0.0, 1.3, 1.1, 0.0),
        1 => {
            local_box(-0.7, -0.75, 0.055, 0.055, 0.0);
            local_box(0.7, -0.8, 0.27, 0.09, 0.0);
        }
        2 => {
            for k in 0..6 {
                let a = k as f32 * TAU / 6.0;
                let (hw, hd, stone_yaw) = if k == 4 { (0.31, 0.81, a + 0.5) } else { (0.34, 0.2, a) };
                local_box(a.cos() * 2.3, a.sin() * 2.3, hw, hd, stone_yaw);
            }
        }
        3 => local_box(0.6, 0.0, 1.55, 0.9, 0.0),
        4 => {
            local_box(-1.0, 0.0, 0.83, 0.7, 0.0);
            local_box(1.0, -1.0, 0.84, 0.055, 0.0);
            local_box(1.0, 1.0, 0.84, 0.055, 0.0);
            local_box(1.8, 0.0, 0.055, 1.05, 0.0);
        }
        // The gallows platform + frame (one box, as before it joined the plan).
        GALLOWS => local_box(0.0, 0.0, 1.2, 0.9, 0.0),
        _ => {}
    }
}

/// Ground rules shared by every story kind on top of [`spot_ok`]: clear of the ork camps' tents
/// and guy ropes (their flat clearing is smaller than what they draw), of the castle's town
/// meadow, and of the landmarks' trial arenas.
pub(crate) fn clear_of_settlements(q: Vec2, foot: f32) -> bool {
    q.length() > crate::worldmap::SAFE_R * crate::worldmap::MAP_SCALE + TOWN_KEEP + foot
        && crate::camps::plan().iter().all(|c| c.centre.distance(q) > CAMP_KEEP + foot)
        && crate::ruins::landmark_sites().iter().all(|l| l.pos.distance(q) > LANDMARK_KEEP + foot)
}

/// A ROADSIDE kind's spot: [`spot_ok`], clear of camps, and well clear of the Blight — Gnashfang
/// Hold's walls, gate approach and mire dressing are built at phase 25 from fixed coordinates
/// and claim that ground whatever was planned there (an artery runs past the hold's west wall:
/// the old walk planned the watchtower INSIDE the palisade, and it was always "claimed").
fn roadside_spot_ok(kind: usize, q: Vec2, foot: f32) -> bool {
    crate::ork_fortress::blight_edge_world(q.x, q.y) < -(foot + 4.0)
        && terrain_suits(kind, q, foot)
        && clear_of_settlements(q, foot)
        && spot_ok(q.x, q.y, foot)
}

/// Biome fit: the roadside pieces are dry-land scenes, so none stands on the marsh (the bog has its
/// own drowned-tower / stilt-hut dressing, `bog.rs`); the shepherd's hut and its pen want pasture —
/// grass or forest edge, not dunes or snowfield.
fn terrain_suits(kind: usize, q: Vec2, foot: f32) -> bool {
    use crate::biome::Biome;
    let at = |dx: f32, dz: f32| crate::worldmap::biome_at_world(q.x + dx, q.y + dz);
    let probes = [at(0.0, 0.0), at(foot, 0.0), at(-foot, 0.0), at(0.0, foot), at(0.0, -foot)];
    probes.iter().all(|b| *b != Some(Biome::Swamp))
        && (kind != 4 || probes.iter().all(|b| matches!(b, None | Some(Biome::Forest))))
}

/// The gallows' spot: outside the palisade, off the gate apron (the orks' own wayposts stand
/// there), clear of camps, and [`spot_ok`].
fn gallows_spot_ok(q: Vec2) -> bool {
    let foot = STORY_FOOTPRINTS[GALLOWS];
    q.distance(crate::ork_fortress::CENTRE) > 30.0
        && (0..8).all(|k| {
            let a = k as f32 * (TAU / 8.0);
            !crate::ork_fortress::on_gate_approach(q.x + a.cos() * foot, q.y + a.sin() * foot)
        })
        && !crate::ork_fortress::on_gate_approach(q.x, q.y)
        && clear_of_settlements(q, foot)
        && spot_ok(q.x, q.y, foot)
}

/// One roadside walk over every artery: `(first stop, its jitter, gap, gap jitter, min spacing
/// between set-pieces)`. Pass 1 is the designed rhythm — a set-piece every ~90–130u of road,
/// ≥55u apart. The denser passes only run for a kind the rhythm couldn't seat (the 3.25u stone
/// circle on a cramped stretch) and trade spacing for coverage instead of dropping the kind.
const ROADSIDE_PASSES: [(f32, f32, f32, f32, f32); 3] = [
    (45.0, 60.0, 90.0, 40.0, 55.0),
    (15.0, 20.0, 20.0, 10.0, 40.0),
    (4.0, 4.0, 6.0, 2.0, 24.0),
];

/// Seat each of `kinds` once along the arteries, appending to `planned` (whose sites the spacing
/// also respects). Each stop is offered to the kinds still waiting, in order, so a stop too
/// cramped for the stone circle still takes the graves and the circle tries the next stop —
/// nothing is skipped and no kind is planned twice. Deterministic: the walk, the side picks and
/// the yaws come from fixed seeds. Returns the kinds that found no spot at all.
fn seat_roadside(mut pending: Vec<usize>, planned: &mut Vec<StorySite>) -> Vec<usize> {
    let arteries = crate::roads::artery_polylines();
    let mut rng: u32 = 0x9017_44aa;
    'passes: for (first, first_jitter, gap, gap_jitter, spacing) in ROADSIDE_PASSES {
        for poly in &arteries {
            let mut next_at = first + rng_next(&mut rng) * first_jitter;
            let mut travelled = 0.0_f32;
            for w in poly.windows(2) {
                let seg = w[0].distance(w[1]);
                if seg < 1e-3 { continue; }
                while travelled + seg >= next_at {
                    if pending.is_empty() { break 'passes; }
                    let t = (next_at - travelled) / seg;
                    let p = w[0].lerp(w[1], t);
                    let dir = (w[1] - w[0]) / seg;
                    let perp = Vec2::new(-dir.y, dir.x);
                    next_at += gap + rng_next(&mut rng) * gap_jitter;
                    let side = if rng_next(&mut rng) < 0.5 { 1.0 } else { -1.0 };
                    let seat = pending.iter().enumerate().find_map(|(i, &kind)| {
                        let foot = STORY_FOOTPRINTS[kind];
                        [(side, 6.5_f32), (-side, 6.5), (side, 9.5), (-side, 9.5), (side, 12.5), (-side, 12.5)]
                            .into_iter()
                            .flat_map(|(s, d)| [0.0_f32, -6.0, 6.0].into_iter().map(move |along| p + perp * d * s + dir * along))
                            .find(|q| planned.iter().all(|site| site.pos.distance(*q) >= spacing) && roadside_spot_ok(kind, *q, foot))
                            .map(|q| (i, q))
                    });
                    if let Some((i, q)) = seat {
                        let kind = pending.remove(i);
                        planned.push(StorySite { kind, pos: q, yaw: site_yaw(kind, q) });
                    }
                }
                travelled += seg;
            }
        }
    }
    pending
}

/// A stable per-site yaw, hashed from the kind and spot (independent of the walk order).
fn site_yaw(kind: usize, q: Vec2) -> f32 {
    let mut s = q.x.to_bits() ^ q.y.to_bits().rotate_left(16) ^ (kind as u32).wrapping_mul(0x9e37_79b9);
    rng_next(&mut s) * TAU
}

/// The gallows on the Gnashfang approach: just off the road on the way in, ~30u out from the
/// gate — the message you read before the walls. The fortress spur itself is short (it forks off
/// the nearest artery right outside the hold), so every artery point in the approach band
/// counts, nearest the designed ~30u first. Tried in widening rings — the designed band and
/// offsets, then further out and further off the road (the approach is uneven and partly
/// waterlogged) — rather than dropping the piece. Faces the gate.
fn seat_gallows(planned: &[StorySite]) -> Option<StorySite> {
    let gate = crate::ork_fortress::GATE;
    let arteries = crate::roads::artery_polylines();
    // `(band from the gate, offsets off the road, in front of the wall line only)`. The hold
    // faces north (the castle side): "the way in" is the ground north of the gate.
    let tiers: [(f32, f32, &[f32], bool); 3] = [
        (18.0, 50.0, &[4.5, 6.5], true),
        (12.0, 80.0, &[4.5, 6.5, 8.5, 10.5], true),
        (8.0, 130.0, &[4.5, 6.5, 8.5, 10.5, 13.0], false),
    ];
    for (near, far, offsets, front_only) in tiers {
        let mut stops: Vec<(f32, Vec2, Vec2)> = Vec::new();
        for poly in &arteries {
            for w in poly.windows(2) {
                let d = w[1].distance(gate);
                if (near..=far).contains(&d)
                    && w[1].distance(crate::ork_fortress::CENTRE) > 30.0
                    && (!front_only || w[1].y < gate.y - 4.0)
                {
                    stops.push(((d - 30.0).abs(), w[1], (w[1] - w[0]).normalize_or_zero()));
                }
            }
        }
        // Total order on (band distance, x, z) so equal keys can't depend on the artery order.
        stops.sort_by(|a, b| a.0.total_cmp(&b.0).then(a.1.x.total_cmp(&b.1.x)).then(a.1.y.total_cmp(&b.1.y)));
        for (_, p, dir) in stops {
            let perp = Vec2::new(-dir.y, dir.x);
            for &d in offsets {
                for side in [1.0_f32, -1.0] {
                    let q = p + perp * d * side;
                    if planned.iter().all(|site| site.pos.distance(q) >= 24.0) && gallows_spot_ok(q) {
                        return Some(StorySite { kind: GALLOWS, pos: q, yaw: (gate.x - q.x).atan2(gate.y - q.y) });
                    }
                }
            }
        }
    }
    None
}

/// Reserve every story set-piece's spot (build phase 4, before any scatter): the gallows on the
/// fortress approach, then each roadside kind exactly once. Biome scatter (via
/// [`story_clearings`]) and every placer before phase 32 (ore, chests, forage, the Blight mire,
/// the bog, wayside, …) then leave these clearings free for their set-pieces.
pub fn plan_clearings() {
    reset_plan();
    let mut planned: Vec<StorySite> = Vec::new();
    match seat_gallows(&planned) {
        Some(site) => planned.push(site),
        None => warn!("poi: no spot for the gallows on the fortress approach"),
    }
    for kind in seat_roadside((0..ROADSIDE_KINDS).collect(), &mut planned) {
        warn!("poi: no roadside spot for {}", STORY_KIT[kind]);
    }
    for site in &planned {
        crate::blockers::reserve_visual(site.pos.x, site.pos.y, STORY_FOOTPRINTS[site.kind]);
        info!("poi: planned {} at {:.1},{:.1}", STORY_KIT[site.kind], site.pos.x, site.pos.y);
    }
    info!("poi: planned {} story clearings", planned.len());
    *STORY_SITES.lock().unwrap() = planned;
}

/// Is a planned site still usable at spawn time? Its own reservation is there by design, so only
/// the ground rules and solids placed since the plan are re-checked.
fn still_free(site: &StorySite) -> bool {
    let (q, foot) = (site.pos, STORY_FOOTPRINTS[site.kind]);
    site_ok(q.x, q.y, foot) && !crate::blockers::any_within(q.x, q.y, foot + 0.2)
}

/// A replacement spot for a planned site some later phase claimed after all — the same search,
/// run against the finished world (the visual test now sees everything spawned so far).
fn resite(kind: usize, others: &[StorySite]) -> Option<StorySite> {
    if kind == GALLOWS {
        return seat_gallows(others);
    }
    let mut seated = others.to_vec();
    if !seat_roadside(vec![kind], &mut seated).is_empty() {
        return None;
    }
    seated.pop()
}

/// Build-phase 32 entry: the planned set-pieces (roadside kinds + the gallows) + fortress flags.
pub fn populate(commands: &mut Commands, meshes: &mut Assets<Mesh>, materials: &mut Assets<StandardMaterial>) {
    let mat = materials.add(StandardMaterial { base_color: Color::WHITE, perceptual_roughness: 0.9, ..default() });
    let range = VisibilityRange { start_margin: 0.0..0.0, end_margin: 120.0..120.0, use_aabb: true };
    // Final placement reuses the early plan, but still respects late authored solids. With the
    // realistic forest kit loaded each set-piece is its Blender model (`wayside.glb`: same
    // footprint, masses under the same blocker boxes); otherwise the low-poly mesh.
    let kit = crate::realforest::get().filter(|k| k.has(STORY_KIT[0]));
    let handles: Vec<Handle<Mesh>> =
        [burned_cabin(), graves(), standing_stones(), fallen_watchtower(), shepherd_hut(), gallows()]
            .into_iter().map(|mesh| meshes.add(mesh)).collect();
    let planned = STORY_SITES.lock().unwrap().clone();
    let mut final_sites: Vec<StorySite> = Vec::with_capacity(planned.len());
    // 1. The story set-pieces, each on its planned clearing.
    for (i, site) in planned.iter().enumerate() {
        let site = if still_free(site) {
            site.clone()
        } else {
            // Not a skip: re-site the kind (against every other planned or placed piece).
            let others: Vec<StorySite> = final_sites.iter().chain(&planned[i + 1..]).cloned().collect();
            match resite(site.kind, &others) {
                Some(moved) => {
                    info!("poi: planned {} at {:.1},{:.1} was claimed, moved to {:.1},{:.1}",
                        STORY_KIT[site.kind], site.pos.x, site.pos.y, moved.pos.x, moved.pos.y);
                    moved
                }
                None => {
                    warn!("poi: planned {} at {:.1},{:.1} was claimed and no other spot is free",
                        STORY_KIT[site.kind], site.pos.x, site.pos.y);
                    continue;
                }
            }
        };
        let (q, foot) = (site.pos, STORY_FOOTPRINTS[site.kind]);
        let y = crate::worldmap::ground_at_world(q.x, q.y).unwrap_or(0.0);
        let tf = Transform::from_xyz(q.x, y, q.y).with_rotation(Quat::from_rotation_y(site.yaw));
        match kit.and_then(|k| k.spawn_static_with(commands, STORY_KIT[site.kind], tf, range.clone())) {
            Some(e) => { commands.entity(e).insert(BiomeEntity); }
            None => { commands.spawn((Mesh3d(handles[site.kind].clone()), MeshMaterial3d(mat.clone()), tf, BiomeEntity, range.clone())); }
        }
        register_story_blockers(site.kind, q, site.yaw);
        crate::blockers::reserve_visual(q.x, q.y, foot);
        info!("poi: {} at {:.1},{:.1}", STORY_KIT[site.kind], q.x, q.y);
        final_sites.push(site);
    }
    let placed = final_sites.len();
    // Keep the plan in step with what actually stands (anything reading the clearings later).
    *STORY_SITES.lock().unwrap() = final_sites;

    // 2. FLAGS over Gnashfang Hold: a tall smoke column + wheeling crows, visible far across
    //    the island (sightline weenies — cheap particles/meshes, no lighting cost).
    let hold = crate::ork_fortress::CENTRE;
    // Near-black, denser, taller than the first cut — grey-on-grey it vanished against the
    // hazy sky + the snow massif behind the Hold (verification flag).
    let smoke_mesh = meshes.add(Sphere::new(1.15).mesh().ico(1).unwrap());
    let smoke_mat = materials.add(StandardMaterial {
        base_color: Color::srgba(0.10, 0.095, 0.09, 0.8),
        alpha_mode: AlphaMode::Blend,
        unlit: true,
        ..default()
    });
    let hold_y = crate::worldmap::ground_at_world(hold.x, hold.y).unwrap_or(1.0);
    for k in 0..10 {
        let phase = k as f32 / 10.0;
        commands.spawn((
            Mesh3d(smoke_mesh.clone()),
            MeshMaterial3d(smoke_mat.clone()),
            Transform::from_xyz(hold.x, hold_y + 3.0, hold.y),
            SmokeMote {
                base: Vec3::new(hold.x + 1.0, hold_y + 3.0, hold.y - 1.5),
                speed: 0.055 + phase * 0.01,
                phase: phase * 10.0,
                rise: 22.0,
            },
            bevy::light::NotShadowCaster,
            BiomeEntity,
        ));
    }
    let crow_mesh = meshes.add(crow_mesh());
    let crow_mat = materials.add(StandardMaterial { base_color: Color::srgb(0.05, 0.05, 0.06), unlit: true, ..default() });
    for k in 0..5 {
        let phase = k as f32 * (TAU / 5.0);
        commands.spawn((
            Mesh3d(crow_mesh.clone()),
            MeshMaterial3d(crow_mat.clone()),
            Transform::from_xyz(hold.x, hold_y + 14.0, hold.y),
            Crow {
                centre: Vec3::new(hold.x, hold_y + 13.0 + (k as f32 * 1.3).sin() * 2.0, hold.y),
                radius: 9.0 + (k as f32 * 2.7).sin() * 3.0,
                speed: 0.28 + k as f32 * 0.03,
                phase,
            },
            bevy::light::NotShadowCaster,
            BiomeEntity,
        ));
    }

    // (The low-poly tilled-field meshes that stood here — box beds + post fences, the "wooden
    // rafts" on the meadow — are gone: the fields are ground now, `castle_ground::field_at`.)
    info!("poi: {} set-pieces, smoke + crows over the Hold", placed);
}

/// A tiny low-poly crow: body + swept wings (rotated so local -Z is the flight direction).
fn crow_mesh() -> Mesh {
    let mut v = Vec::new();
    v.push(tint(
        Sphere::new(0.16).mesh().ico(1).unwrap().scaled_by(Vec3::new(0.8, 0.7, 1.5)),
        0x0a0a0c,
    ));
    for s in [-1.0_f32, 1.0] {
        v.push(bxr(
            0.85,
            0.03,
            0.26,
            Quat::from_rotation_z(s * 0.28),
            Vec3::new(s * 0.45, 0.05, 0.0),
            0x0a0a0c,
        ));
    }
    assemble(v)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn fence_meshes_stay_inside_their_reserved_footprints() {
        use bevy::mesh::VertexAttributeValues;
        let hut = shepherd_hut();
        let Some(VertexAttributeValues::Float32x3(hut_vertices)) = hut.attribute(Mesh::ATTRIBUTE_POSITION) else {
            panic!("hut positions must be readable");
        };
        for p in hut_vertices {
            assert!(Vec2::new(p[0], p[2]).length() <= STORY_FOOTPRINTS[4],
                "pen rail escapes the reserved hut footprint: {p:?}");
        }
    }

    #[test]
    fn fence_meshes_fit_their_registered_footprints() {
        for (mesh, half_width, half_depth) in [
            (shepherd_hut(), 1.95, 1.06),
        ] {
            let Some(bevy::mesh::VertexAttributeValues::Float32x3(vertices)) =
                mesh.attribute(Mesh::ATTRIBUTE_POSITION) else { panic!("mesh positions missing") };
            for [x, _, z] in vertices {
                assert!(x.abs() <= half_width && z.abs() <= half_depth,
                    "fence vertex ({x}, {z}) overhangs its collision/placement footprint");
            }
        }
    }

    #[test]
    fn rotated_standing_stones_collide_but_leave_middle_walkable() {
        let _g = crate::blockers::TEST_LOCK.lock().unwrap();
        crate::blockers::reset();
        let p = Vec2::new(40.0, 40.0);
        register_story_blockers(2, p, FRAC_PI_2);
        assert!(crate::blockers::is_blocked(40.0, 37.7));
        assert!(!crate::blockers::is_blocked(40.0, 40.0));
        crate::blockers::reset();
    }
    #[test]
    fn rotated_hut_and_pen_match_model_without_filling_workspace() {
        let _g = crate::blockers::TEST_LOCK.lock().unwrap();
        crate::blockers::reset();
        let p = Vec2::new(40.0, 40.0);
        register_story_blockers(4, p, FRAC_PI_2);
        assert!(crate::blockers::is_blocked(40.0, 41.0));
        assert!(crate::blockers::is_blocked(41.0, 39.0));
        assert!(!crate::blockers::is_blocked(40.0, 39.0));
        crate::blockers::reset();
    }
    fn planned_sites() -> Vec<(usize, Vec2)> {
        STORY_SITES.lock().unwrap().iter().map(|s| (s.kind, s.pos)).collect()
    }

    /// The phase-4 plan seats every story kind exactly once on the Home map — five roadside
    /// set-pieces + the gallows — on legal dry ground, apart from each other, the roadside ones
    /// out of the Blight (Gnashfang Hold's dressing never consults the plan), the gallows on the
    /// fortress approach; and a rebuild re-plans the very same spots.
    #[test]
    fn plan_seats_every_story_kind_exactly_once() {
        let _g = crate::blockers::TEST_LOCK.lock().unwrap();
        crate::blockers::reset();
        plan_clearings();
        let first = planned_sites();
        for (kind, p) in &first {
            eprintln!("planned {} at {:.1},{:.1}", STORY_KIT[*kind], p.x, p.y);
        }
        let mut kinds: Vec<usize> = first.iter().map(|s| s.0).collect();
        kinds.sort_unstable();
        assert_eq!(kinds, (0..STORY_KIT.len()).collect::<Vec<_>>(), "each kind exactly once");
        for (i, &(kind, p)) in first.iter().enumerate() {
            let foot = STORY_FOOTPRINTS[kind];
            assert!(site_ok(p.x, p.y, foot) && clear_of_settlements(p, foot), "{} on illegal ground at {p}", STORY_KIT[kind]);
            if kind != GALLOWS {
                assert!(crate::ork_fortress::blight_edge_world(p.x, p.y) < -foot, "{} inside the Blight at {p}", STORY_KIT[kind]);
                assert!(terrain_suits(kind, p, foot), "{} on unfit terrain at {p}", STORY_KIT[kind]);
            }
            for &(other, q) in &first[i + 1..] {
                assert!(p.distance(q) > foot + STORY_FOOTPRINTS[other] + 2.0, "{} crowds {}", STORY_KIT[kind], STORY_KIT[other]);
            }
        }
        let gallows = first.iter().find(|s| s.0 == GALLOWS).unwrap().1;
        assert!(gallows.distance(crate::ork_fortress::GATE) < 60.0, "the gallows belongs on the approach, not at {gallows}");
        assert!(gallows.distance(crate::ork_fortress::CENTRE) > 30.0, "the gallows stands outside the palisade");

        crate::blockers::reset();
        plan_clearings();
        assert_eq!(planned_sites(), first, "planning must be deterministic across rebuilds");
        crate::blockers::reset();
        reset_plan();
    }

    /// A planned spot a later build phase claims after all is re-sited at spawn rather than
    /// dropped: every kind still stands exactly once, collision included.
    #[test]
    fn claimed_site_is_resited_not_skipped() {
        let _g = crate::blockers::TEST_LOCK.lock().unwrap();
        crate::blockers::reset();
        plan_clearings();
        let victim = STORY_SITES.lock().unwrap().iter().find(|s| s.kind == 3).cloned().expect("watchtower planned");
        crate::blockers::add_box(victim.pos.x, victim.pos.y, 0.5, 0.5); // a late solid on its spot

        let world = World::new();
        let mut queue = bevy::ecs::world::CommandQueue::default();
        let mut commands = Commands::new(&mut queue, &world);
        let (mut meshes, mut materials) = (Assets::<Mesh>::default(), Assets::<StandardMaterial>::default());
        populate(&mut commands, &mut meshes, &mut materials);

        let placed = planned_sites();
        let mut kinds: Vec<usize> = placed.iter().map(|s| s.0).collect();
        kinds.sort_unstable();
        assert_eq!(kinds, (0..STORY_KIT.len()).collect::<Vec<_>>(), "nothing dropped, nothing doubled");
        let moved = placed.iter().find(|s| s.0 == 3).unwrap().1;
        assert!(moved.distance(victim.pos) > STORY_FOOTPRINTS[3], "the claimed watchtower must move");
        for site in STORY_SITES.lock().unwrap().iter() {
            // Each kind's first blocker box, in model space (graves: the cross; circle: stone 0).
            let local = match site.kind { 1 => Vec3::new(-0.7, 0.0, -0.75), 2 => Vec3::new(2.3, 0.0, 0.0), 3 => Vec3::new(0.6, 0.0, 0.0), 4 => Vec3::new(-1.0, 0.0, 0.0), _ => Vec3::ZERO };
            let at = Quat::from_rotation_y(site.yaw) * local;
            assert!(crate::blockers::is_blocked(site.pos.x + at.x, site.pos.y + at.z),
                "{} at {} registered no collision", STORY_KIT[site.kind], site.pos);
        }
        crate::blockers::reset();
        reset_plan();
    }

    #[test]
    fn planned_clearings_reject_overhanging_scatter_and_reset_between_maps() {
        let _g = crate::blockers::TEST_LOCK.lock().unwrap();
        reset_plan();
        STORY_SITES.lock().unwrap().push(StorySite { kind: 2, pos: Vec2::new(40.0, 40.0), yaw: 0.0 });
        assert!(overlaps_planned_clearing(44.2, 40.0, 0.9));
        assert!(story_clearings().overlaps(44.2, 40.0, 0.9));
        reset_plan();
        assert!(!overlaps_planned_clearing(40.0, 40.0, 0.9));
    }
}
