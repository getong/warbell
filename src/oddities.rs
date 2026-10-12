//! **The wilds' oddities** — five unique creatures, one per biome (spec 2026-10-13 "Żywa wyspa"
//! §2 C, items 8–12). Each is self-contained in the [`crate::snowman`] mould: its own brain, a
//! [`Health`] the hero's melee cone hits (`player::combat` / `player::arts` list `With<Oddity>`),
//! a drop that feeds the witch's brews, and its own respawn. Nothing here is run-state, so none of
//! it rides the save (the dens' stolen hoard is transient like the battlefield).
//!
//! - **Hornet nest** (forest): a grey paper nest under the limb of a dead pollard oak. Strike it or
//!   loiter under it > 4 s and the swarm boils out (particles): 4 dmg/s until you reach water or get
//!   25u away. A broken nest drops `honeycomb`; it rebuilds after two dawns.
//! - **Lantern Toad** (swamp, dusk to dawn): a dog-sized toad on the pool edges whose throat sac
//!   glows green — from afar, the bog's "lights". It hops, and spits slime that slows you 3 s.
//!   HP 60, drops `toad_glow`.
//! - **Carrion vultures** (rocky): a flock soars over the Gully of the First War and drops down to
//!   feed there; lone birds circle every unopened Relic chest in the rocks — a signpost. They only
//!   go for a hero below 30% HP. Hittable only on the ground. Drop `vulture_quill`.
//! - **Antlion pit** (NE dunes): a 4u sand funnel. Inside it the sand drags you to the middle
//!   (moving out ×0.4) where the mandibles snap (14 dmg). Killing it collapses the pit and drops
//!   `antlion_chitin`; the pit re-forms after two dawns.
//! - **Wolverine** (snow, ×2): fast (7), HP 120. A bite STEALS one food from the satchel and it
//!   bolts for its den (`stashes::den_sites`) where the loot piles up; kill it to get the loot back
//!   plus `fur`.
//!
//! Models: `oddities.glb` (`tools/blender_forest/oddities.py`) on the creature material; the
//! wolverine is the kit bear's sculpt on the bear rig, scaled down and recoloured.
//!
//! Close-ups: `FOREST_ODDLINE="x,z"` parks a frozen display of every creature in a row at a world
//! XZ (snag + nest, toad lit, perched vulture + one soaring, antlion pit, wolverine), each 7u apart
//! along +X.

use bevy::camera::visibility::VisibilityRange;
use bevy::prelude::*;

use crate::audio::AudioCue;
use crate::biome::{Biome, BiomeEntity};
use crate::creature::{CreatureMaterial, Surf};
use crate::game_state::SimAppExt;
use crate::player::{Health, HeroState, PendingHeroDamage};
use crate::steer::{self, footing};

/// Marker on every hittable oddity (the hero's melee cone lists `With<Oddity>`).
#[derive(Component)]
pub struct Oddity;

/// Model-space top of the paper nest under the snag's limb (`oddities.py` NEST_ATTACH).
const NEST_AT: Vec3 = Vec3::new(1.22, 2.36, 0.1);
/// Antlion jaw pivot in the head's frame (`oddities.py` JAW_PIVOT).
const JAW_PIVOT: Vec3 = Vec3::new(0.12, 0.15, 0.2);
/// The vulture's shoulder pivots in its body frame.
const SHOULDER: Vec3 = Vec3::new(0.1, 0.47, 0.0);
const PIT_R: f32 = 3.7;

const NEST_HP: f32 = 40.0;
const TOAD_HP: f32 = 60.0;
const VULTURE_HP: f32 = 45.0;
const ANTLION_HP: f32 = 90.0;
const WOLVERINE_HP: f32 = 120.0;

// ── Palettes (coat ramp dark/base/light/tint + regions MAIN, SKIN, DETAIL, EYE, ACCENT, HORN) ──
type Pal = ([u32; 4], [(u32, Surf); 6]);
const PAL_NEST: Pal = ([0x5e584e, 0x8f877a, 0xc4bcaa, 0x7d6c52],
    [(0x8f877a, Surf::Skin), (0x7a7062, Surf::Skin), (0x3e3022, Surf::Bone), (0x111111, Surf::Bone), (0x8f877a, Surf::Skin), (0x5a4a36, Surf::Bone)]);
const PAL_HORNET: Pal = ([0x1a120a, 0x7a4414, 0xd8a020, 0x000000],
    [(0, Surf::Scale), (0xd0c8b8, Surf::Bone), (0x4a2410, Surf::Scale), (0x111111, Surf::Bone), (0x7a3410, Surf::Scale), (0x111111, Surf::Bone)]);
const PAL_TOAD: Pal = ([0x26221a, 0x4e4a30, 0xb4a682, 0x7a4e26],
    [(0, Surf::Skin), (0x7a6c50, Surf::Skin), (0x1a120c, Surf::Skin), (0x6a4a10, Surf::Bone), (0x6a5434, Surf::Skin), (0x1a1a1a, Surf::Bone)]);
const PAL_VULTURE: Pal = ([0x22180f, 0x6e5236, 0xbc9c70, 0x86603c],
    [(0, Surf::Fur), (0xb0aca4, Surf::Skin), (0x4a3c30, Surf::Skin), (0x1a0e08, Surf::Bone), (0xe2dac8, Surf::Fur), (0x8a8274, Surf::Bone)]);
const PAL_VULTURE_LEGS: Pal = ([0x3a2a1a, 0x6e5236, 0xb8986c, 0x86603c],
    [(0, Surf::Fur), (0x86847c, Surf::Scale), (0x161210, Surf::Bone), (0x111111, Surf::Bone), (0xe2dac8, Surf::Fur), (0x8a8274, Surf::Bone)]);
const PAL_ANTLION: Pal = ([0x34291e, 0x7c6a52, 0xbca884, 0x6e4422],
    [(0, Surf::Scale), (0x5e4a38, Surf::Scale), (0x241a12, Surf::Bone), (0x0c0a08, Surf::Bone), (0x7c6a52, Surf::Scale), (0x2e1c10, Surf::Bone)]);
const PAL_JAW: Pal = ([0x160c06, 0x5a3016, 0x9a6230, 0x6e3412],
    [(0, Surf::Bone), (0x5e4a38, Surf::Bone), (0x241a12, Surf::Bone), (0x0c0a08, Surf::Bone), (0x7c6a52, Surf::Bone), (0x22140c, Surf::Bone)]);
/// Wolverine coat on the bear sculpt: near-black points, dark chocolate body, the pale buff of the
/// flank band / brow, a rusty tint.
const WOLVERINE_COAT: [u32; 4] = [0x15100c, 0x3a2a1e, 0xa88a5e, 0x6a4628];

fn coat_mesh(kit: &crate::realforest::Kit, name: &str, pal: &Pal) -> Option<Mesh> {
    let l = crate::palette::lin;
    let coat = pal.0.map(l);
    let palette: Vec<([f32; 4], Surf)> = pal.1.iter().map(|&(c, s)| (l(c), s)).collect();
    kit.coat_part(name, &coat, &palette)
}

/// Mirror a mesh across X = 0 (left wing / jaw → right).
fn mirror_x(mut m: Mesh) -> Mesh {
    use bevy::mesh::{Indices, VertexAttributeValues as V};
    for attr in [Mesh::ATTRIBUTE_POSITION, Mesh::ATTRIBUTE_NORMAL] {
        if let Some(V::Float32x3(vs)) = m.attribute_mut(attr) {
            for p in vs.iter_mut() {
                p[0] = -p[0];
            }
        }
    }
    match m.indices_mut() {
        Some(Indices::U32(ix)) => ix.chunks_exact_mut(3).for_each(|t| t.swap(1, 2)),
        Some(Indices::U16(ix)) => ix.chunks_exact_mut(3).for_each(|t| t.swap(1, 2)),
        None => {}
    }
    m
}

/// Every mesh / material the oddities draw with, uploaded once.
#[derive(Resource, Clone)]
struct Assets_ {
    mat: Handle<CreatureMaterial>,
    nest: Handle<Mesh>,
    hornet: Handle<Mesh>,
    toad: Handle<Mesh>,
    sac: Handle<Mesh>,
    sac_mat: Handle<StandardMaterial>,
    slime: Handle<Mesh>,
    slime_mat: Handle<StandardMaterial>,
    vul_body: Handle<Mesh>,
    vul_wing_l: Handle<Mesh>,
    vul_wing_r: Handle<Mesh>,
    vul_legs: Handle<Mesh>,
    ant_head: Handle<Mesh>,
    jaw_l: Handle<Mesh>,
    jaw_r: Handle<Mesh>,
    wolverine: Option<crate::quadruped::QuadHandles>,
}

fn build_assets(
    meshes: &mut Assets<Mesh>,
    std_mats: &mut Assets<StandardMaterial>,
    creature_mats: &mut Assets<CreatureMaterial>,
) -> Option<Assets_> {
    let kit = crate::realforest::get().filter(|k| k.has("odd_toad_body"))?;
    let m = |meshes: &mut Assets<Mesh>, n: &str, p: &Pal| coat_mesh(kit, n, p).map(|x| meshes.add(x));
    let wing = coat_mesh(kit, "odd_vulture_wing", &PAL_VULTURE)?;
    let jaw = coat_mesh(kit, "odd_antlion_jaw", &PAL_JAW)?;
    let mut sac = kit.raw_part("odd_toad_sac")?;
    sac.remove_attribute(Mesh::ATTRIBUTE_UV_0);
    Some(Assets_ {
        mat: crate::creature::make_creature_material(creature_mats),
        nest: m(meshes, "odd_nest", &PAL_NEST)?,
        hornet: m(meshes, "odd_hornet", &PAL_HORNET)?,
        toad: m(meshes, "odd_toad_body", &PAL_TOAD)?,
        sac: meshes.add(sac),
        sac_mat: std_mats.add(StandardMaterial {
            base_color: Color::WHITE,
            emissive: LinearRgba::rgb(2.2, 4.2, 1.6),
            perceptual_roughness: 0.3,
            ..default()
        }),
        slime: meshes.add(Sphere::new(0.09).mesh().ico(2).unwrap()),
        slime_mat: std_mats.add(StandardMaterial {
            base_color: Color::srgba(0.55, 0.75, 0.3, 0.85),
            emissive: LinearRgba::rgb(0.4, 0.9, 0.25),
            alpha_mode: AlphaMode::Blend,
            perceptual_roughness: 0.15,
            ..default()
        }),
        vul_body: m(meshes, "odd_vulture_body", &PAL_VULTURE)?,
        vul_wing_r: meshes.add(mirror_x(wing.clone())),
        vul_wing_l: meshes.add(wing),
        vul_legs: m(meshes, "odd_vulture_legs", &PAL_VULTURE_LEGS)?,
        ant_head: m(meshes, "odd_antlion_head", &PAL_ANTLION)?,
        jaw_r: meshes.add(mirror_x(jaw.clone())),
        jaw_l: meshes.add(jaw),
        wolverine: crate::quadruped::kit_quad_meshes_with(crate::quadruped::QuadSpecies::Bear, WOLVERINE_COAT).map(|q| q.upload(meshes)),
    })
}

// ── Components ──────────────────────────────────────────────────────────────────────────────
#[derive(Component)]
struct Nest {
    slot: usize,
    /// Seconds the hero has stood under it.
    loiter: f32,
    last_hp: f32,
}

#[derive(Component)]
struct Hornet {
    phase: f32,
    speed: f32,
    radius: f32,
    seed: f32,
}

#[derive(Component)]
struct Toad {
    slot: usize,
    home: Vec2,
    pos: Vec2,
    facing: f32,
    hop_from: Vec2,
    hop_to: Vec2,
    hop_t: f32,
    next_hop: f32,
    spit_cd: f32,
    phase: f32,
    awake: bool,
    hp: f32,
}

#[derive(Component)]
struct ToadSac;

#[derive(Component)]
struct Slime {
    vel: Vec3,
    life: f32,
}

#[derive(Clone, Copy, PartialEq)]
enum VState {
    Soar,
    Descend,
    Feed,
    Climb,
    Dive,
}

#[derive(Component)]
struct Vulture {
    slot: usize,
    /// What it circles: the gully (feeds there) or a Relic chest (`chest = true`, never lands).
    anchor: Vec2,
    chest: bool,
    state: VState,
    ang: f32,
    radius: f32,
    alt: f32,
    pos: Vec3,
    facing: f32,
    timer: f32,
    flap: f32,
    atk_cd: f32,
    hp: f32,
    /// Ground spot it feeds at.
    feed_at: Vec2,
}

#[derive(Component)]
struct Wing {
    right: bool,
}

#[derive(Component)]
struct VultureLegs;

#[derive(Component)]
struct Antlion {
    slot: usize,
    centre: Vec2,
    base_y: f32,
    strike: f32,
    bite_cd: f32,
    pit: Entity,
}

#[derive(Component)]
struct Jaw {
    right: bool,
}

#[derive(Component)]
struct Pit {
    collapse: f32,
}

#[derive(Clone, Copy, PartialEq)]
enum WState {
    Roam,
    Hunt,
    Flee,
    Hidden,
}

#[derive(Component)]
struct Wolverine {
    slot: usize,
    den: Vec2,
    pos: Vec2,
    facing: f32,
    goal: Vec2,
    state: WState,
    timer: f32,
    bite_cd: f32,
    stolen: Vec<String>,
}

/// Frozen display piece of the `FOREST_ODDLINE` stage (no brain).
#[derive(Component)]
struct Display;

// ── World state ─────────────────────────────────────────────────────────────────────────────
#[derive(Clone, Copy, PartialEq, Eq)]
enum Kind {
    Nest,
    Toad,
    Vulture,
    Antlion,
    Wolverine,
}

struct Slot {
    kind: Kind,
    pos: Vec2,
    yaw: f32,
    alive: bool,
    /// Respawn when `dawns >= respawn_dawn` (nest / antlion) or `now >= respawn_at` (the rest).
    respawn_dawn: u32,
    respawn_at: f32,
    extra: Vec2,
    chest: bool,
}

/// Food the wolverines dragged into each den (by den index) — searched out at the den
/// (`stashes.rs`). Transient, like the battlefield.
#[derive(Resource, Default)]
pub struct DenHoards(pub Vec<Vec<String>>);

#[derive(Resource, Default)]
struct Wilds {
    seeded: bool,
    slots: Vec<Slot>,
    dawns: u32,
    /// Swarm: (nest slot, centre, time left angry); `None` when calm.
    swarm: Option<Swarm>,
    gully: Vec2,
}

struct Swarm {
    nest: Vec2,
    centre: Vec3,
    calm_t: f32,
}

/// The hero's slime / sand drag (`apply_drag`): slowed until `slow_until`, and last frame's spot.
#[derive(Resource, Default)]
struct Drag {
    slow_until: f32,
    last: Option<Vec2>,
    pit: Option<Vec2>,
}

/// World positions of the stolen-goods dens (written by the stash planner, read by the wolverines).
pub fn den_spots() -> Vec<Vec2> {
    crate::stashes::den_sites()
}

pub struct OdditiesPlugin;

impl Plugin for OdditiesPlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<Wilds>().init_resource::<Drag>().init_resource::<DenHoards>();
        app.add_systems(Update, (seed_wilds, stage_oddline).run_if(crate::rts::in_campaign));
        app.add_sim_systems(
            (
                count_dawns,
                nest_brain,
                swarm_brain,
                toad_brain,
                slime_fly,
                vulture_brain,
                antlion_brain,
                wolverine_brain,
                apply_drag,
                oddity_deaths,
                respawn_wilds,
            )
                .chain(),
        );
        app.add_systems(Update, (animate_wings, animate_jaws, pulse_sacs, collapse_pits));
    }
}

fn rng(s: &mut u32) -> f32 {
    *s = s.wrapping_add(0x6d2b_79f5);
    let mut t = *s;
    t = (t ^ (t >> 15)).wrapping_mul(t | 1);
    t ^= t.wrapping_add((t ^ (t >> 7)).wrapping_mul(t | 61));
    ((t ^ (t >> 14)) as f32) / 4_294_967_296.0
}

/// Common placement rules: in `biome`, on land, off roads / planned sites / blockers / the town.
fn spot_ok(p: Vec2, biome: Biome, clear: f32) -> bool {
    footing(p.x, p.y).is_some()
        && crate::worldmap::tile_biome_world(p.x, p.y) == Some(biome)
        && !crate::worldmap::is_pool_world(p.x, p.y)
        && !crate::worldmap::is_open_water_world(p.x, p.y)
        && !(0..8).any(|k| {
            let a = k as f32 * std::f32::consts::TAU / 8.0;
            crate::roads::on_road(p.x + a.cos() * (clear + 1.0), p.y + a.sin() * (clear + 1.0))
        })
        && !crate::poi::overlaps_planned_clearing(p.x, p.y, clear)
        && !crate::stashes::overlaps_planned(p.x, p.y, clear)
        && !crate::blockers::any_within(p.x, p.y, clear)
        && !crate::town::near_build_plot(p.x, p.y)
        && crate::camps::plan().iter().all(|c| c.centre.distance(p) > 14.0 + clear)
}

/// Height spread over a disc of radius `r` around `p`.
fn spread(p: Vec2, r: f32) -> f32 {
    let (mut lo, mut hi) = (f32::MAX, f32::MIN);
    for k in 0..12 {
        let a = k as f32 * std::f32::consts::TAU / 12.0;
        for rr in [r, r * 0.5] {
            if let Some(y) = footing(p.x + a.cos() * rr, p.y + a.sin() * rr) {
                lo = lo.min(y);
                hi = hi.max(y);
            } else {
                return f32::MAX;
            }
        }
    }
    hi - lo
}

/// Up to `n` spots inside the box `[x0, x1] × [z0, z1]` satisfying `ok`, at least `sep` apart.
fn scan(seed: u32, n: usize, bx: [f32; 4], sep: f32, mut ok: impl FnMut(Vec2) -> bool) -> Vec<Vec2> {
    let mut s = seed;
    let mut out: Vec<Vec2> = Vec::new();
    for _ in 0..4000 {
        if out.len() >= n {
            break;
        }
        let p = Vec2::new(bx[0] + (bx[1] - bx[0]) * rng(&mut s), bx[2] + (bx[3] - bx[2]) * rng(&mut s));
        if out.iter().all(|q| q.distance(p) > sep) && ok(p) {
            out.push(p);
        }
    }
    out
}

fn region(b: Biome) -> [f32; 4] {
    let (c, r) = match b {
        Biome::Forest => (Vec2::new(-156.0, 101.0), 130.0),
        Biome::Swamp => (Vec2::new(0.0, 148.0), 80.0),
        Biome::Rocky => (Vec2::new(176.0, 23.0), 140.0),
        Biome::Desert => (Vec2::new(144.0, -133.0), 160.0),
        _ => (Vec2::new(-179.0, -117.0), 170.0),
    };
    [c.x - r, c.x + r, c.y - r, c.y + r]
}

#[allow(clippy::too_many_arguments)]
fn seed_wilds(
    mut commands: Commands,
    mut meshes: ResMut<Assets<Mesh>>,
    mut std_mats: ResMut<Assets<StandardMaterial>>,
    mut creature_mats: ResMut<Assets<CreatureMaterial>>,
    ready: Res<crate::biome::WorldReady>,
    mut wilds: ResMut<Wilds>,
    mut hoards: ResMut<DenHoards>,
    landmarks: Query<(&crate::landmarks::Landmark, &GlobalTransform)>,
    chests: Query<(&crate::chest::Chest, &GlobalTransform)>,
) {
    if wilds.seeded || !ready.0 {
        return;
    }
    wilds.seeded = true;
    let Some(a) = build_assets(&mut meshes, &mut std_mats, &mut creature_mats) else {
        warn!("oddities: oddities.glb not in the kit — no wild oddities");
        return;
    };
    commands.insert_resource(a.clone());
    let mut slots: Vec<Slot> = Vec::new();
    let mk = |kind, pos, yaw, extra, chest| Slot { kind, pos, yaw, alive: true, respawn_dawn: 0, respawn_at: 0.0, extra, chest };

    // Hornet nests: 3 snags in the forest, well apart.
    for (i, p) in scan(0xA11CE, 3, region(Biome::Forest), 45.0, |p| spot_ok(p, Biome::Forest, 2.2) && spread(p, 1.5) < 0.5)
        .into_iter()
        .enumerate()
    {
        slots.push(mk(Kind::Nest, p, i as f32 * 2.1 + 0.4, Vec2::ZERO, false));
    }
    // Lantern toads: on the land rim of the swamp pools (a pool within 1.5–4u).
    let near_pool = |p: Vec2| {
        (0..8).any(|k| {
            let a = k as f32 * std::f32::consts::TAU / 8.0;
            [1.5f32, 2.5, 4.0].iter().any(|r| crate::worldmap::is_pool_world(p.x + a.cos() * r, p.y + a.sin() * r))
        })
    };
    for p in scan(0x70AD, 4, region(Biome::Swamp), 22.0, |p| spot_ok(p, Biome::Swamp, 0.8) && near_pool(p)) {
        slots.push(mk(Kind::Toad, p, 0.0, Vec2::ZERO, false));
    }
    // Vultures: a flock of 3 over the Gully of the First War (they feed there) + one bird over each
    // unopened Relic chest in the rocks (up to 3).
    let gully = landmarks
        .iter()
        .find(|(l, _)| l.name == "The Gully of the First War")
        .map(|(_, g)| Vec2::new(g.translation().x, g.translation().z))
        .unwrap_or(Vec2::new(176.0, 23.0));
    wilds.gully = gully;
    let mut s = 0x5EA1u32;
    for i in 0..3 {
        let feed = gully + Vec2::new(rng(&mut s) - 0.5, rng(&mut s) - 0.5) * 6.0;
        slots.push(mk(Kind::Vulture, gully, i as f32 * 2.09, feed, false));
    }
    let mut relics: Vec<Vec2> = chests
        .iter()
        .filter(|(c, _)| c.tier == crate::chest::ChestTier::Relic && !c.opened && !c.cache)
        .map(|(_, g)| Vec2::new(g.translation().x, g.translation().z))
        .filter(|p| crate::worldmap::tile_biome_world(p.x, p.y) == Some(Biome::Rocky))
        .collect();
    relics.sort_by(|a, b| a.distance(gully).total_cmp(&b.distance(gully)));
    for (i, p) in relics.into_iter().take(3).enumerate() {
        slots.push(mk(Kind::Vulture, p, i as f32 * 1.7, p, true));
    }
    // Antlion pits: 3 in the NE dune sea (spec empty area 4), flat sand, wide clearance.
    let mut pits = scan(0xA27, 3, [150.0, 250.0, -190.0, -110.0], 28.0, |p| spot_ok(p, Biome::Desert, 6.4) && spread(p, 5.0) < 0.9);
    if pits.len() < 3 {
        let more = scan(0xA28, 3 - pits.len(), region(Biome::Desert), 28.0, |p| {
            // Deep desert only: never on the castle's doorstep.
            p.length() > 110.0 && spot_ok(p, Biome::Desert, 6.4) && spread(p, 5.0) < 0.9 && pits.iter().all(|q| q.distance(p) > 28.0)
        });
        pits.extend(more);
    }
    for p in pits {
        slots.push(mk(Kind::Antlion, p, 0.0, Vec2::ZERO, false));
    }
    // Wolverines: one per den.
    let dens = den_spots();
    hoards.0 = vec![Vec::new(); dens.len()];
    for (i, d) in dens.iter().enumerate() {
        slots.push(mk(Kind::Wolverine, *d + Vec2::new(0.0, -2.5), 0.0, Vec2::new(i as f32, 0.0), false));
    }
    for (i, s) in slots.iter().enumerate() {
        info!("oddities: slot {i} {} at ({:.1}, {:.1})", kind_name(s.kind), s.pos.x, s.pos.y);
        spawn_slot(&mut commands, &a, s, i, &mut meshes);
    }
    wilds.slots = slots;
}

fn kind_name(k: Kind) -> &'static str {
    match k {
        Kind::Nest => "hornet nest",
        Kind::Toad => "lantern toad",
        Kind::Vulture => "vulture",
        Kind::Antlion => "antlion pit",
        Kind::Wolverine => "wolverine",
    }
}

fn range() -> VisibilityRange {
    VisibilityRange { start_margin: 0.0..0.0, end_margin: 110.0..130.0, use_aabb: true }
}

fn spawn_slot(commands: &mut Commands, a: &Assets_, s: &Slot, slot: usize, meshes: &mut Assets<Mesh>) {
    let y = footing(s.pos.x, s.pos.y).unwrap_or(0.0);
    match s.kind {
        Kind::Nest => {
            let tf = Transform::from_xyz(s.pos.x, y - 0.05, s.pos.y).with_rotation(Quat::from_rotation_y(s.yaw));
            // The snag is permanent scenery (a respawn only re-hangs the nest, `respawn_wilds`).
            if let Some(kit) = crate::realforest::get() {
                if let Some(e) = kit.spawn_static_with(commands, "odd_nest_snag", tf, range()) {
                    commands.entity(e).insert(BiomeEntity);
                }
            }
            crate::blockers::add_obb(s.pos.x, s.pos.y, 0.42, 0.42, s.yaw);
            spawn_nest(commands, a, slot, tf.transform_point(NEST_AT));
        }
        Kind::Toad => spawn_toad(commands, a, slot, s.pos),
        Kind::Vulture => spawn_vulture(commands, a, slot, s),
        Kind::Antlion => spawn_antlion(commands, a, slot, s.pos, meshes),
        Kind::Wolverine => spawn_wolverine(commands, a, slot, s.pos, s.extra.x as usize),
    }
}

fn spawn_nest(commands: &mut Commands, a: &Assets_, slot: usize, at: Vec3) -> Entity {
    commands
        .spawn((
            Transform::from_translation(at),
            Visibility::default(),
            Mesh3d(a.nest.clone()),
            MeshMaterial3d(a.mat.clone()),
            Health { hp: NEST_HP, max: NEST_HP },
            Oddity,
            Nest { slot, loiter: 0.0, last_hp: NEST_HP },
            BiomeEntity,
            range(),
        ))
        .id()
}

fn spawn_toad(commands: &mut Commands, a: &Assets_, slot: usize, p: Vec2) {
    let y = footing(p.x, p.y).unwrap_or(0.0);
    let e = commands
        .spawn((
            Transform::from_xyz(p.x, y, p.y),
            Visibility::Hidden,
            Mesh3d(a.toad.clone()),
            MeshMaterial3d(a.mat.clone()),
            Oddity,
            Toad {
                slot,
                home: p,
                pos: p,
                facing: 0.0,
                hop_from: p,
                hop_to: p,
                hop_t: 1.0,
                next_hop: 2.0,
                spit_cd: 2.0,
                phase: slot as f32 * 1.3,
                awake: false,
                hp: TOAD_HP,
            },
            BiomeEntity,
        ))
        .id();
    let sac = commands
        .spawn((
            Transform::from_translation(Vec3::new(0.0, 0.13, 0.33)),
            Visibility::Inherited,
            Mesh3d(a.sac.clone()),
            MeshMaterial3d(a.sac_mat.clone()),
            ToadSac,
            bevy::light::NotShadowCaster,
        ))
        .with_children(|c| {
            c.spawn((
                PointLight { color: Color::srgb(0.55, 1.0, 0.4), intensity: 9000.0, range: 6.0, ..default() },
                Transform::from_xyz(0.0, 0.05, 0.12),
            ));
        })
        .id();
    commands.entity(e).add_child(sac);
}

fn spawn_vulture(commands: &mut Commands, a: &Assets_, slot: usize, s: &Slot) {
    let alt = if s.chest { 16.0 } else { 20.0 };
    let pos = Vec3::new(s.pos.x, footing(s.pos.x, s.pos.y).unwrap_or(0.0) + alt, s.pos.y);
    let e = commands
        .spawn((
            Transform::from_translation(pos).with_scale(Vec3::splat(1.15)),
            Visibility::default(),
            Mesh3d(a.vul_body.clone()),
            MeshMaterial3d(a.mat.clone()),
            Vulture {
                slot,
                anchor: s.pos,
                chest: s.chest,
                state: VState::Soar,
                ang: s.yaw,
                radius: if s.chest { 9.0 } else { 13.0 + slot as f32 % 3.0 * 2.0 },
                alt,
                pos,
                facing: 0.0,
                timer: 25.0 + s.yaw * 9.0,
                flap: 0.0,
                atk_cd: 0.0,
                hp: VULTURE_HP,
                feed_at: s.extra,
            },
            BiomeEntity,
        ))
        .id();
    attach_vulture_parts(commands, a, e, true);
}

fn attach_vulture_parts(commands: &mut Commands, a: &Assets_, e: Entity, legs_hidden: bool) {
    commands.entity(e).with_children(|c| {
        for right in [false, true] {
            let x = if right { -SHOULDER.x } else { SHOULDER.x };
            c.spawn((
                Transform::from_xyz(x, SHOULDER.y, SHOULDER.z),
                Visibility::Inherited,
                Mesh3d(if right { a.vul_wing_r.clone() } else { a.vul_wing_l.clone() }),
                MeshMaterial3d(a.mat.clone()),
                Wing { right },
            ));
        }
        c.spawn((
            Transform::IDENTITY,
            if legs_hidden { Visibility::Hidden } else { Visibility::Inherited },
            Mesh3d(a.vul_legs.clone()),
            MeshMaterial3d(a.mat.clone()),
            VultureLegs,
        ));
    });
}

fn pit_seat(p: Vec2) -> f32 {
    // Seat the funnel so its floor clears the ground everywhere inside the rim (the terrain can't be
    // dug, so the funnel is a low spoil ring — ~0.6 deep, the hero's feet sink into it like loose
    // sand — whose apron dives back under the ground).
    let funnel = |r: f32| -0.32 + 0.6 * (r / PIT_R).powf(1.3);
    let mut hi = footing(p.x, p.y).unwrap_or(0.0) - funnel(0.0) + 0.04;
    for k in 0..12 {
        let a = k as f32 * std::f32::consts::TAU / 12.0;
        for r in [1.0f32, 2.2, 3.4] {
            if let Some(y) = footing(p.x + a.cos() * r, p.y + a.sin() * r) {
                hi = hi.max(y - funnel(r) + 0.04);
            }
        }
    }
    hi
}

fn spawn_antlion(commands: &mut Commands, a: &Assets_, slot: usize, p: Vec2, _meshes: &mut Assets<Mesh>) {
    let y = pit_seat(p);
    let pit = commands.spawn((Transform::from_xyz(p.x, y, p.y), Visibility::default(), Pit { collapse: -1.0 }, BiomeEntity)).id();
    if let Some(kit) = crate::realforest::get() {
        let mut pe = commands.entity(pit);
        kit.attach_static_with(&mut pe, "odd_antlion_pit", Transform::IDENTITY, range());
    }
    let head = commands
        .spawn((
            Transform::from_xyz(p.x, y - 0.42, p.y).with_scale(Vec3::splat(1.25)),
            Visibility::default(),
            Mesh3d(a.ant_head.clone()),
            MeshMaterial3d(a.mat.clone()),
            Health { hp: ANTLION_HP, max: ANTLION_HP },
            Oddity,
            Antlion { slot, centre: p, base_y: y, strike: 0.0, bite_cd: 0.0, pit },
            BiomeEntity,
            range(),
        ))
        .id();
    commands.entity(head).with_children(|c| {
        for right in [false, true] {
            let piv = if right { Vec3::new(-JAW_PIVOT.x, JAW_PIVOT.y, JAW_PIVOT.z) } else { JAW_PIVOT };
            c.spawn((
                Transform::from_translation(piv),
                Visibility::Inherited,
                Mesh3d(if right { a.jaw_r.clone() } else { a.jaw_l.clone() }),
                MeshMaterial3d(a.mat.clone()),
                Jaw { right },
            ));
        }
    });
}

fn spawn_wolverine(commands: &mut Commands, a: &Assets_, slot: usize, p: Vec2, den: usize) {
    let Some(h) = a.wolverine.clone() else { return };
    let y = footing(p.x, p.y).unwrap_or(0.0);
    let root = commands
        .spawn((
            Transform::from_xyz(p.x, y, p.y).with_scale(Vec3::splat(0.62)),
            Visibility::default(),
            Health { hp: WOLVERINE_HP, max: WOLVERINE_HP },
            Oddity,
            crate::quadruped::QuadDrive::new(crate::quadruped::QuadSpecies::Bear),
            Wolverine {
                slot,
                den: crate::stashes::den_sites().get(den).copied().unwrap_or(p),
                pos: p,
                facing: 0.0,
                goal: p,
                state: WState::Roam,
                timer: 0.0,
                bite_cd: 0.0,
                stolen: Vec::new(),
            },
            BiomeEntity,
        ))
        .id();
    crate::quadruped::spawn_quad(commands, root, &a.mat, crate::quadruped::QuadSpecies::Bear, h);
}

// ── Brains ──────────────────────────────────────────────────────────────────────────────────
fn count_dawns(siege: Option<Res<crate::siege::Siege>>, mut prev: Local<Option<crate::siege::GamePhase>>, mut wilds: ResMut<Wilds>) {
    let Some(siege) = siege else { return };
    if matches!((*prev, siege.phase), (Some(crate::siege::GamePhase::Wave), crate::siege::GamePhase::Prep)) {
        wilds.dawns += 1;
    }
    *prev = Some(siege.phase);
}

fn hero_at(hero: &HeroState) -> Vec3 {
    Vec3::new(hero.pos.x, hero.y + 1.0, hero.pos.y)
}

/// Loitering under a nest or striking it rouses the swarm.
fn nest_brain(
    time: Res<Time>,
    hero: Res<HeroState>,
    mut wilds: ResMut<Wilds>,
    mut cues: MessageWriter<AudioCue>,
    mut q: Query<(&mut Nest, &Health, &GlobalTransform), Without<crate::dying::Dying>>,
    mut tf_q: Query<&mut Transform, With<Nest>>,
) {
    let dt = time.delta_secs();
    let now = time.elapsed_secs();
    for (mut n, hp, gt) in &mut q {
        let p = gt.translation();
        let d = Vec2::new(p.x, p.z).distance(hero.pos);
        let struck = hp.hp < n.last_hp - 0.01;
        n.last_hp = hp.hp;
        n.loiter = if d < 2.6 && hero.alive { n.loiter + dt } else { 0.0 };
        if (struck || n.loiter > 4.0) && wilds.swarm.is_none() {
            wilds.swarm = Some(Swarm { nest: Vec2::new(p.x, p.z), centre: p - Vec3::Y * 0.4, calm_t: 0.0 });
            cues.write(AudioCue::CreatureAggro(p));
        }
        let _ = n.slot;
        let _ = now;
    }
    // A barely-there sway on the paper nests (the twig flexes in the wind).
    for mut tf in &mut tf_q {
        let w = (now * 1.3 + tf.translation.x).sin() * 0.025;
        tf.rotation = Quat::from_rotation_z(w) * Quat::from_rotation_x(w * 0.6);
    }
}

const SWARM_N: usize = 34;

/// The swarm: a buzzing cloud that chases the hero (4 dmg/s inside it) until he reaches water or
/// gets 25u from the nest, then drifts home and settles.
#[allow(clippy::too_many_arguments)]
fn swarm_brain(
    time: Res<Time>,
    hero: Res<HeroState>,
    assets: Option<Res<Assets_>>,
    mut wilds: ResMut<Wilds>,
    mut pending: ResMut<PendingHeroDamage>,
    mut commands: Commands,
    mut hornets: Query<(Entity, &mut Hornet, &mut Transform)>,
) {
    let dt = time.delta_secs();
    let now = time.elapsed_secs();
    let Some(a) = assets else { return };
    let Some(sw) = wilds.swarm.as_mut() else {
        for (e, _, _) in &hornets {
            commands.entity(e).try_despawn();
        }
        return;
    };
    let hp3 = hero_at(&hero);
    let in_water = crate::worldmap::is_open_water_world(hero.pos.x, hero.pos.y) || crate::worldmap::is_pool_world(hero.pos.x, hero.pos.y);
    let fled = hero.pos.distance(sw.nest) > 25.0 || in_water || !hero.alive;
    let nest3 = Vec3::new(sw.nest.x, footing(sw.nest.x, sw.nest.y).unwrap_or(0.0) + 2.0, sw.nest.y);
    let goal = if fled { nest3 } else { hp3 + Vec3::Y * 0.2 };
    let to = goal - sw.centre;
    let speed = if fled { 3.0 } else { 6.2 };
    sw.centre += to.clamp_length_max(speed * dt);
    if fled {
        sw.calm_t += dt;
    } else {
        sw.calm_t = 0.0;
        if sw.centre.distance(hp3) < 1.8 {
            pending.0 += 4.0 * dt;
            pending.1 = Vec2::ZERO;
        }
    }
    let settle = (sw.calm_t / 6.0).clamp(0.0, 1.0);
    let n = hornets.iter().count();
    if n < SWARM_N {
        let mut s = (now * 1000.0) as u32;
        for i in n..SWARM_N {
            commands.spawn((
                Transform::from_translation(sw.centre),
                Visibility::default(),
                Mesh3d(a.hornet.clone()),
                MeshMaterial3d(a.mat.clone()),
                Hornet { phase: rng(&mut s) * 6.28, speed: 3.0 + rng(&mut s) * 4.0, radius: 0.5 + rng(&mut s) * 1.1, seed: i as f32 * 1.7 },
                bevy::light::NotShadowCaster,
                BiomeEntity,
            ));
        }
    }
    let centre = sw.centre;
    for (_, mut h, mut tf) in &mut hornets {
        h.phase += h.speed * dt;
        let r = h.radius * (1.0 - 0.7 * settle);
        let off = Vec3::new(
            (h.phase).cos() * r + (now * 7.0 + h.seed).sin() * 0.12,
            (h.phase * 1.7 + h.seed).sin() * r * 0.55 + (now * 11.0 + h.seed).cos() * 0.08,
            (h.phase).sin() * r,
        );
        let target = centre + off;
        let prev = tf.translation;
        tf.translation = prev.lerp(target, (dt * 12.0).min(1.0));
        let v = tf.translation - prev;
        if v.length_squared() > 1e-8 {
            tf.look_to(v, Vec3::Y);
            tf.rotate_local_y(std::f32::consts::PI); // the hornet's head is +Z
        }
    }
    if settle >= 1.0 {
        wilds.swarm = None;
    }
}

fn is_dusk(clock: &crate::scene::SkyClock) -> bool {
    clock.t >= 0.52 || clock.t < 0.02
}

#[allow(clippy::too_many_arguments)]
fn toad_brain(
    time: Res<Time>,
    hero: Res<HeroState>,
    clock: Res<crate::scene::SkyClock>,
    assets: Option<Res<Assets_>>,
    mut commands: Commands,
    mut q: Query<(Entity, &mut Toad, &mut Transform, &mut Visibility, Option<&Health>), (Without<crate::dying::Dying>, Without<Display>)>,
) {
    let dt = time.delta_secs();
    let Some(a) = assets else { return };
    let dusk = is_dusk(&clock) || std::env::var("FOREST_TOADS").is_ok();
    for (e, mut t, mut tf, mut vis, hp) in &mut q {
        if let Some(h) = hp {
            t.hp = h.hp;
        }
        if dusk != t.awake {
            t.awake = dusk;
            *vis = if dusk { Visibility::Inherited } else { Visibility::Hidden };
            if dusk {
                commands.entity(e).try_insert(Health { hp: t.hp, max: TOAD_HP });
            } else {
                commands.entity(e).remove::<Health>();
            }
        }
        if !t.awake {
            continue;
        }
        t.phase += dt;
        let d = t.pos.distance(hero.pos);
        let alert = d < 9.0 && hero.alive;
        // Hops: a short parabolic arc to a nearby spot on the pool rim (or toward the hero, warily).
        if t.hop_t < 1.0 {
            t.hop_t = (t.hop_t + dt / 0.42).min(1.0);
            t.pos = t.hop_from.lerp(t.hop_to, t.hop_t);
        } else {
            t.next_hop -= dt;
            if t.next_hop <= 0.0 && !alert {
                let mut s = (t.phase * 997.0) as u32 ^ t.slot as u32;
                let ang = rng(&mut s) * std::f32::consts::TAU;
                let mut to = t.pos + Vec2::new(ang.cos(), ang.sin()) * 1.2;
                if to.distance(t.home) > 5.0 {
                    to = t.pos + (t.home - t.pos).normalize_or_zero() * 1.2;
                }
                if footing(to.x, to.y).is_some() && !crate::worldmap::is_pool_world(to.x, to.y) {
                    t.hop_from = t.pos;
                    t.hop_to = to;
                    t.hop_t = 0.0;
                    let dir = to - t.pos;
                    t.facing = dir.x.atan2(dir.y);
                }
                t.next_hop = 2.5 + rng(&mut s) * 4.0;
            }
        }
        if alert {
            let dir = hero.pos - t.pos;
            t.facing = dir.x.atan2(dir.y);
            t.spit_cd -= dt;
            if t.spit_cd <= 0.0 && d > 1.2 {
                t.spit_cd = 3.2;
                let from = Vec3::new(t.pos.x, tf.translation.y + 0.3, t.pos.y) + Vec3::new(t.facing.sin(), 0.0, t.facing.cos()) * 0.45;
                let aim = hero_at(&hero) - Vec3::Y * 0.4;
                let flat = Vec2::new(aim.x - from.x, aim.z - from.z);
                let tt = (flat.length() / 9.0).max(0.15);
                let vel = Vec3::new(flat.x / tt, (aim.y - from.y) / tt + 0.5 * 9.8 * tt, flat.y / tt);
                commands.spawn((
                    Transform::from_translation(from),
                    Visibility::default(),
                    Mesh3d(a.slime.clone()),
                    MeshMaterial3d(a.slime_mat.clone()),
                    Slime { vel, life: 2.5 },
                    bevy::light::NotShadowCaster,
                    BiomeEntity,
                ));
            }
        }
        let y = footing(t.pos.x, t.pos.y).unwrap_or(tf.translation.y);
        let arc = if t.hop_t < 1.0 { (t.hop_t * std::f32::consts::PI).sin() } else { 0.0 };
        let breathe = (t.phase * 2.2).sin() * 0.015;
        let squash = if t.hop_t < 1.0 { 1.0 + 0.18 * arc } else { 1.0 + breathe };
        tf.translation = Vec3::new(t.pos.x, y + arc * 0.45, t.pos.y);
        tf.rotation = Quat::from_rotation_y(t.facing) * Quat::from_rotation_x(-0.35 * arc);
        tf.scale = Vec3::new(1.0 / squash.sqrt(), squash, 1.0 / squash.sqrt());
    }
}

fn slime_fly(
    time: Res<Time>,
    hero: Res<HeroState>,
    mut drag: ResMut<Drag>,
    mut pending: ResMut<PendingHeroDamage>,
    mut floats: ResMut<crate::combat_fx::FloatQueue>,
    mut commands: Commands,
    mut q: Query<(Entity, &mut Slime, &mut Transform)>,
) {
    let dt = time.delta_secs();
    let now = time.elapsed_secs();
    for (e, mut s, mut tf) in &mut q {
        s.vel.y -= 9.8 * dt;
        tf.translation += s.vel * dt;
        s.life -= dt;
        let hit = tf.translation.distance(hero_at(&hero) - Vec3::Y * 0.3) < 0.75 && hero.alive;
        let ground = footing(tf.translation.x, tf.translation.z).is_some_and(|y| tf.translation.y < y);
        if hit {
            drag.slow_until = now + 3.0;
            pending.0 += 3.0;
            floats.0.push(crate::combat_fx::FloatReq {
                world: hero_at(&hero) + Vec3::Y * 0.8,
                text: "Slowed".into(),
                color: Color::srgb(0.6, 0.95, 0.4),
                scale: 0.9,
            });
        }
        if hit || ground || s.life <= 0.0 {
            commands.entity(e).try_despawn();
        }
    }
}

#[allow(clippy::too_many_arguments)]
fn vulture_brain(
    time: Res<Time>,
    hero: Res<HeroState>,
    player: Res<crate::player::PlayerRes>,
    mut pending: ResMut<PendingHeroDamage>,
    mut commands: Commands,
    chests: Query<&crate::chest::Chest>,
    mut q: Query<(Entity, &mut Vulture, &mut Transform, &Children, Option<&Health>), (Without<crate::dying::Dying>, Without<Display>)>,
    mut legs: Query<&mut Visibility, With<VultureLegs>>,
) {
    let dt = time.delta_secs();
    let weak = player.0.hp < player.0.max_hp * 0.3 && player.0.is_alive();
    let _ = chests;
    for (e, mut v, mut tf, kids, hp) in &mut q {
        if let Some(h) = hp {
            v.hp = h.hp;
        }
        v.timer -= dt;
        v.atk_cd = (v.atk_cd - dt).max(0.0);
        let ground = footing(v.anchor.x, v.anchor.y).unwrap_or(0.0);
        let hd = Vec2::new(v.pos.x, v.pos.z).distance(hero.pos);
        if weak && hd < 30.0 && v.state != VState::Dive {
            v.state = VState::Dive;
        } else if !weak && v.state == VState::Dive {
            v.state = VState::Climb;
        }
        let prev_state = v.state;
        match v.state {
            VState::Soar => {
                v.ang += dt * 6.5 / v.radius;
                let c = v.anchor + Vec2::new(v.ang.cos(), v.ang.sin()) * v.radius;
                let target = Vec3::new(c.x, ground + v.alt + (v.ang * 0.7).sin() * 1.5, c.y);
                let d = target - v.pos;
                v.pos += d.clamp_length_max(8.0 * dt);
                let dir = Vec2::new(-v.ang.sin(), v.ang.cos());
                v.facing = dir.x.atan2(dir.y);
                if v.timer <= 0.0 && !v.chest {
                    v.state = VState::Descend;
                }
            }
            VState::Descend => {
                let gy = footing(v.feed_at.x, v.feed_at.y).unwrap_or(ground);
                let target = Vec3::new(v.feed_at.x, gy, v.feed_at.y);
                let d = target - v.pos;
                let flat = Vec2::new(d.x, d.z);
                if flat.length() > 0.1 {
                    v.facing = flat.x.atan2(flat.y);
                }
                v.pos += d.clamp_length_max(6.0 * dt);
                if d.length() < 0.1 {
                    v.state = VState::Feed;
                    v.timer = 18.0 + v.slot as f32 * 3.0;
                }
            }
            VState::Feed => {
                // Mantling over the carcass: shuffle, peck; spooked by the hero walking in close.
                if v.timer <= 0.0 || hd < 5.0 {
                    v.state = VState::Climb;
                }
            }
            VState::Climb => {
                v.ang += dt * 6.5 / v.radius;
                let c = v.anchor + Vec2::new(v.ang.cos(), v.ang.sin()) * v.radius;
                let target = Vec3::new(c.x, ground + v.alt, c.y);
                let d = target - v.pos;
                v.pos += d.clamp_length_max(5.0 * dt);
                let dir = Vec2::new(d.x, d.z);
                if dir.length() > 0.01 {
                    v.facing = dir.x.atan2(dir.y);
                }
                if d.length() < 1.0 {
                    v.state = VState::Soar;
                    v.timer = 35.0 + v.slot as f32 * 7.0;
                }
            }
            VState::Dive => {
                let target = hero_at(&hero) + Vec3::Y * 0.4;
                let d = target - v.pos;
                let dir = Vec2::new(d.x, d.z);
                if dir.length() > 0.01 {
                    v.facing = dir.x.atan2(dir.y);
                }
                v.pos += d.clamp_length_max(9.0 * dt);
                if d.length() < 1.3 && v.atk_cd <= 0.0 && hero.alive {
                    v.atk_cd = 1.6;
                    pending.0 += 8.0;
                    pending.1 = dir.normalize_or_zero();
                }
            }
        }
        // Only a bird on (or near) the ground can be struck.
        let low = v.pos.y - footing(v.pos.x, v.pos.z).unwrap_or(0.0) < 2.0;
        if low && hp.is_none() {
            commands.entity(e).try_insert((Health { hp: v.hp, max: VULTURE_HP }, Oddity));
        } else if !low && hp.is_some() {
            commands.entity(e).remove::<(Health, Oddity)>();
        }
        if prev_state != v.state || v.state == VState::Feed {
            for k in kids.iter() {
                if let Ok(mut vis) = legs.get_mut(k) {
                    *vis = if matches!(v.state, VState::Feed | VState::Descend) && low { Visibility::Inherited } else { Visibility::Hidden };
                }
            }
        }
        let bank = if v.state == VState::Soar { -0.32 } else { 0.0 };
        let pitch = match v.state {
            VState::Feed => -0.25 + (time.elapsed_secs() * 3.0 + v.slot as f32).sin().max(0.0) * 0.35,
            VState::Dive | VState::Descend => 0.25,
            _ => 0.0,
        };
        tf.translation = v.pos;
        tf.rotation = Quat::from_rotation_y(v.facing) * Quat::from_rotation_z(bank) * Quat::from_rotation_x(pitch);
        v.flap += dt;
    }
}

/// Wings: soaring = held flat with a slow dihedral breathing; climbing / landing = deep flaps;
/// feeding = half-open mantle drooped over the carcass.
fn animate_wings(
    time: Res<Time>,
    birds: Query<(&Vulture, Option<&Display>)>,
    mut wings: Query<(&Wing, &ChildOf, &mut Transform)>,
) {
    let now = time.elapsed_secs();
    for (w, parent, mut tf) in &mut wings {
        let Ok((v, _)) = birds.get(parent.parent()) else { continue };
        let s = if w.right { -1.0 } else { 1.0 };
        let ph = now + v.slot as f32 * 0.8;
        let (roll, yaw) = match v.state {
            VState::Soar => (0.08 + 0.03 * (ph * 0.9).sin(), 0.0),
            VState::Climb | VState::Descend => ((ph * 6.0).sin() * 0.75 + 0.1, 0.05),
            VState::Dive => (-0.25, 0.45),
            // Half-folded and swept back along the flanks, the wrists mantling over the carcass.
            VState::Feed => (0.12 + 0.06 * (ph * 2.0).sin(), 1.35),
        };
        tf.rotation = Quat::from_rotation_y(-s * yaw) * Quat::from_rotation_z(s * roll);
        // On the ground the wing folds: the spread mesh is drawn in along its span so it lies along
        // the flank instead of fanning out like a cape.
        tf.scale = if v.state == VState::Feed { Vec3::new(0.48, 1.0, 0.8) } else { Vec3::ONE };
    }
}

#[allow(clippy::too_many_arguments)]
fn antlion_brain(
    time: Res<Time>,
    hero: Res<HeroState>,
    mut drag: ResMut<Drag>,
    mut pending: ResMut<PendingHeroDamage>,
    mut cues: MessageWriter<AudioCue>,
    mut q: Query<(&mut Antlion, &mut Transform), (Without<crate::dying::Dying>, Without<Display>)>,
) {
    let dt = time.delta_secs();
    drag.pit = None;
    for (mut a, mut tf) in &mut q {
        let d = a.centre.distance(hero.pos);
        if d < PIT_R && hero.alive {
            drag.pit = Some(a.centre);
        }
        let near = d < 2.3 && hero.alive;
        a.strike = if near { (a.strike + dt * 4.0).min(1.0) } else { (a.strike - dt * 1.5).max(0.0) };
        a.bite_cd = (a.bite_cd - dt).max(0.0);
        if near && a.strike > 0.8 && a.bite_cd <= 0.0 {
            a.bite_cd = 1.4;
            pending.0 += 14.0;
            pending.1 = (hero.pos - a.centre).normalize_or_zero();
            cues.write(AudioCue::CreatureBite { at: tf.translation, big: false });
        }
        let dir = hero.pos - a.centre;
        let face = if near { dir.x.atan2(dir.y) } else { (time.elapsed_secs() * 0.15 + a.slot as f32).sin() * 0.6 };
        tf.translation.y = a.base_y - 0.42 + 0.34 * a.strike;
        tf.rotation = Quat::from_rotation_y(face) * Quat::from_rotation_x(-0.25 * a.strike);
    }
}

fn animate_jaws(time: Res<Time>, heads: Query<&Antlion>, mut jaws: Query<(&Jaw, &ChildOf, &mut Transform)>) {
    let now = time.elapsed_secs();
    for (j, parent, mut tf) in &mut jaws {
        let Ok(a) = heads.get(parent.parent()) else { continue };
        let s = if j.right { -1.0 } else { 1.0 };
        // Idle: wide open, twitching. Striking: snap shut on a fast cycle.
        let snap = if a.strike > 0.5 { (now * 9.0).sin().abs() } else { 0.0 };
        let open = 0.55 - 0.75 * snap + 0.04 * (now * 3.0 + a.slot as f32).sin();
        tf.rotation = Quat::from_rotation_y(s * open);
    }
}

fn pulse_sacs(time: Res<Time>, mut q: Query<&mut Transform, With<ToadSac>>, mut lights: Query<&mut PointLight>) {
    let now = time.elapsed_secs();
    for mut tf in &mut q {
        let k = 0.75 + 0.4 * ((now * 1.6 + tf.translation.x * 7.0).sin() * 0.5 + 0.5).powf(1.6);
        tf.scale = Vec3::splat(k);
    }
    let _ = &mut lights;
}

#[allow(clippy::too_many_arguments)]
fn wolverine_brain(
    time: Res<Time>,
    hero: Res<HeroState>,
    mut inv: ResMut<crate::inventory::Inventory>,
    wilds: Res<Wilds>,
    mut hoards: ResMut<DenHoards>,
    mut pending: ResMut<PendingHeroDamage>,
    mut floats: ResMut<crate::combat_fx::FloatQueue>,
    mut cues: MessageWriter<AudioCue>,
    mut q: Query<(&mut Wolverine, &mut Transform, &mut crate::quadruped::QuadDrive, &mut Visibility), (Without<crate::dying::Dying>, Without<Display>)>,
) {
    let dt = time.delta_secs();
    for (mut w, mut tf, mut drive, mut vis) in &mut q {
        w.timer -= dt;
        w.bite_cd = (w.bite_cd - dt).max(0.0);
        let d = w.pos.distance(hero.pos);
        match w.state {
            WState::Roam => {
                if d < 12.0 && hero.alive {
                    w.state = WState::Hunt;
                    cues.write(AudioCue::CreatureAggro(tf.translation));
                } else if w.timer <= 0.0 || w.pos.distance(w.goal) < 0.4 {
                    let s = &mut ((w.pos.x * 131.0 + w.pos.y * 71.0 + time.elapsed_secs()) as u32);
                    let ang = rng(s) * std::f32::consts::TAU;
                    w.goal = w.den + Vec2::new(ang.cos(), ang.sin()) * (4.0 + rng(s) * 10.0);
                    w.timer = 6.0 + rng(s) * 6.0;
                }
            }
            WState::Hunt => {
                w.goal = hero.pos;
                if d > 22.0 || !hero.alive {
                    w.state = WState::Roam;
                } else if d < 1.3 && w.bite_cd <= 0.0 {
                    w.bite_cd = 1.2;
                    pending.0 += 10.0;
                    pending.1 = (hero.pos - w.pos).normalize_or_zero();
                    cues.write(AudioCue::CreatureBite { at: tf.translation, big: false });
                    // The theft: one food item out of the satchel, then it bolts for its den.
                    if let Some(food) = inv.0.food_slot() {
                        if inv.0.consume_item(&food.item_id, 1) {
                            floats.0.push(crate::combat_fx::FloatReq {
                                world: hero_at(&hero) + Vec3::Y * 0.9,
                                text: "Stolen!".into(),
                                color: Color::srgb(1.0, 0.55, 0.35),
                                scale: 1.0,
                            });
                            w.stolen.push(food.item_id.clone());
                            w.state = WState::Flee;
                            w.goal = w.den;
                        }
                    }
                }
            }
            WState::Flee => {
                w.goal = w.den;
                if w.pos.distance(w.den) < 1.2 {
                    // Into the burrow: the loot joins the hoard; it comes back out a while later.
                    let den_i = w.slot_den(&wilds);
                    let loot = std::mem::take(&mut w.stolen);
                    if let Some(h) = hoards.0.get_mut(den_i) {
                        h.extend(loot);
                    }
                    w.state = WState::Hidden;
                    w.timer = 40.0;
                    *vis = Visibility::Hidden;
                }
            }
            WState::Hidden => {
                if w.timer <= 0.0 {
                    w.state = WState::Roam;
                    *vis = Visibility::Inherited;
                }
            }
        }
        let speed = match w.state {
            WState::Hunt | WState::Flee => 7.0,
            WState::Roam => 1.6,
            WState::Hidden => 0.0,
        };
        let mut moving = false;
        if speed > 0.0 && !(w.state == WState::Hunt && d < 1.2) {
            let cur_y = footing(w.pos.x, w.pos.y).unwrap_or(tf.translation.y);
            if let Some(step) = steer::advance(w.pos, w.facing, w.goal, speed * dt, 0.35, cur_y, 7.0 * dt) {
                w.pos = step.pos;
                w.facing = step.facing;
                moving = step.moving;
            }
        }
        let run = speed > 3.0 && moving;
        drive.moving_amt += ((if moving { 1.0 } else { 0.0 }) - drive.moving_amt) * (dt * 8.0).min(1.0);
        drive.run_amt += ((if run { 1.0 } else { 0.0 }) - drive.run_amt) * (dt * 8.0).min(1.0);
        drive.phase += dt * if run { 13.0 } else { 6.0 } * drive.moving_amt;
        drive.attacking = w.bite_cd > 0.9;
        drive.attack_t = ((1.2 - w.bite_cd) / 0.3).clamp(0.0, 1.0);
        let y = footing(w.pos.x, w.pos.y).unwrap_or(tf.translation.y);
        tf.translation = Vec3::new(w.pos.x, y, w.pos.y);
        tf.rotation = Quat::from_rotation_y(w.facing);
    }
}

impl Wolverine {
    fn slot_den(&self, wilds: &Wilds) -> usize {
        wilds.slots.get(self.slot).map(|s| s.extra.x as usize).unwrap_or(0)
    }
}

/// Slime slow + antlion sand: drag the hero's own step back. Works on the step he actually took
/// last frame (whatever moved him), so no movement code needs to know.
fn apply_drag(time: Res<Time>, mut drag: ResMut<Drag>, mut hero_q: Query<&mut crate::player::Hero>) {
    let Ok(mut h) = hero_q.single_mut() else { return };
    let now = time.elapsed_secs();
    let dt = time.delta_secs();
    if let Some(last) = drag.last {
        let step = h.pos - last;
        if step.length() < 2.0 {
            let mut keep = step;
            if now < drag.slow_until {
                keep *= 0.5;
            }
            if let Some(c) = drag.pit {
                let out = (h.pos - c).normalize_or_zero();
                let along = keep.dot(out);
                if along > 0.0 {
                    keep -= out * along * 0.6; // moving OUT of the funnel: ×0.4
                }
                // The sand slides you down toward the jaws.
                let r = h.pos.distance(c);
                keep -= out * (1.1 * (r / PIT_R).clamp(0.2, 1.0)) * dt;
            }
            h.pos = last + keep;
        }
    }
    drag.last = Some(h.pos);
}

/// A slain oddity pays its drop (and a wolverine coughs up what it stole), and its slot arms the
/// respawn.
#[allow(clippy::too_many_arguments)]
fn oddity_deaths(
    time: Res<Time>,
    mut wilds: ResMut<Wilds>,
    mut inv: ResMut<crate::inventory::Inventory>,
    mut toasts: ResMut<crate::inventory::Toasts>,
    mut floats: ResMut<crate::combat_fx::FloatQueue>,
    mut swarm_off: Local<bool>,
    nests: Query<(&Nest, &GlobalTransform), Added<crate::dying::Dying>>,
    toads: Query<(&Toad, &GlobalTransform), Added<crate::dying::Dying>>,
    vultures: Query<(&Vulture, &GlobalTransform), Added<crate::dying::Dying>>,
    ants: Query<(&Antlion, &GlobalTransform), Added<crate::dying::Dying>>,
    mut wols: Query<(&mut Wolverine, &GlobalTransform), Added<crate::dying::Dying>>,
    mut pits: Query<&mut Pit>,
) {
    let now = time.elapsed_secs();
    let dawns = wilds.dawns;
    let mut events: Vec<(usize, Vec3, Vec<String>, bool)> = Vec::new();
    for (n, g) in &nests {
        events.push((n.slot, g.translation(), vec!["honeycomb".into()], true));
        *swarm_off = true;
    }
    for (t, g) in &toads {
        events.push((t.slot, g.translation(), vec!["toad_glow".into()], false));
    }
    for (v, g) in &vultures {
        events.push((v.slot, g.translation(), vec!["vulture_quill".into()], false));
    }
    for (a, g) in &ants {
        events.push((a.slot, g.translation(), vec!["antlion_chitin".into()], true));
        if let Ok(mut p) = pits.get_mut(a.pit) {
            p.collapse = 0.0;
        }
    }
    for (mut w, g) in &mut wols {
        let mut loot = vec!["fur".to_string()];
        loot.extend(std::mem::take(&mut w.stolen));
        events.push((w.slot, g.translation(), loot, false));
    }
    for (slot, at, loot, dawn_respawn) in events {
        for id in &loot {
            crate::inventory::try_grant(&mut inv.0, &mut toasts.0, id, 1, now as f64);
        }
        if let Some(def) = loot.first().and_then(|id| tileworld_core::inventory::item_def(id)) {
            floats.0.push(crate::combat_fx::FloatReq {
                world: at + Vec3::Y * 1.2,
                text: format!("+{}", def.name),
                color: crate::combat_fx::col_kill(),
                scale: 1.0,
            });
        }
        if let Some(s) = wilds.slots.get_mut(slot) {
            s.alive = false;
            if dawn_respawn {
                s.respawn_dawn = dawns + 2;
            } else {
                s.respawn_at = now + 300.0;
            }
        }
    }
    if *swarm_off {
        *swarm_off = false;
    }
}

fn respawn_wilds(
    time: Res<Time>,
    assets: Option<Res<Assets_>>,
    mut wilds: ResMut<Wilds>,
    mut commands: Commands,
    mut meshes: ResMut<Assets<Mesh>>,
) {
    let Some(a) = assets else { return };
    let now = time.elapsed_secs();
    let dawns = wilds.dawns;
    let mut due = Vec::new();
    for (i, s) in wilds.slots.iter().enumerate() {
        let ready = match s.kind {
            Kind::Nest | Kind::Antlion => s.respawn_dawn > 0 && dawns >= s.respawn_dawn,
            _ => s.respawn_at > 0.0 && now >= s.respawn_at,
        };
        if !s.alive && ready {
            due.push(i);
        }
    }
    for i in due {
        let s = &wilds.slots[i];
        match s.kind {
            Kind::Nest => {
                let tf = Transform::from_xyz(s.pos.x, footing(s.pos.x, s.pos.y).unwrap_or(0.0) - 0.05, s.pos.y)
                    .with_rotation(Quat::from_rotation_y(s.yaw));
                spawn_nest(&mut commands, &a, i, tf.transform_point(NEST_AT));
            }
            Kind::Antlion => {
                spawn_slot(&mut commands, &a, s, i, &mut meshes);
            }
            _ => spawn_slot(&mut commands, &a, s, i, &mut meshes),
        }
        let s = &mut wilds.slots[i];
        s.alive = true;
        s.respawn_at = 0.0;
        s.respawn_dawn = 0;
    }
}

/// A killed antlion's funnel slumps flat over ~2.5 s, then goes.
fn collapse_pits(time: Res<Time>, mut commands: Commands, mut q: Query<(Entity, &mut Pit, &mut Transform)>) {
    let dt = time.delta_secs();
    for (e, mut p, mut tf) in &mut q {
        if p.collapse < 0.0 {
            continue;
        }
        p.collapse += dt / 2.5;
        tf.scale = Vec3::new(1.0 + 0.1 * p.collapse, (1.0 - p.collapse).max(0.05), 1.0 + 0.1 * p.collapse);
        if p.collapse >= 1.0 {
            commands.entity(e).try_despawn();
        }
    }
}

// ── FOREST_ODDLINE display ──────────────────────────────────────────────────────────────────
fn stage_oddline(
    mut commands: Commands,
    mut done: Local<bool>,
    assets: Option<Res<Assets_>>,
    mut meshes: ResMut<Assets<Mesh>>,
) {
    if *done {
        return;
    }
    let Some(a) = assets else { return };
    *done = true;
    let Ok(v) = std::env::var("FOREST_ODDLINE") else { return };
    let xz: Vec<f32> = v.split(',').filter_map(|s| s.trim().parse().ok()).collect();
    if xz.len() < 2 {
        return;
    }
    let base = Vec2::new(xz[0], xz[1]);
    let at = |dx: f32| {
        let p = base + Vec2::new(dx, 0.0);
        Vec3::new(p.x, footing(p.x, p.y).unwrap_or(0.0), p.y)
    };
    let _ = &mut meshes;
    // Snag + nest (facing the camera on -Z: the limb reaches +X).
    let p = at(0.0);
    if let Some(kit) = crate::realforest::get() {
        kit.spawn_static_with(&mut commands, "odd_nest_snag", Transform::from_translation(p), ());
    }
    commands.spawn((Transform::from_translation(p + NEST_AT), Visibility::default(), Mesh3d(a.nest.clone()), MeshMaterial3d(a.mat.clone()), Display));
    // Toad, sac lit, facing -Z (toward a camera south of the line).
    let p = at(7.0);
    let toad = commands
        .spawn((Transform::from_translation(p).with_rotation(Quat::from_rotation_y(std::f32::consts::PI * 0.85)), Visibility::default(),
            Mesh3d(a.toad.clone()), MeshMaterial3d(a.mat.clone()), Display))
        .id();
    let sac = commands
        .spawn((Transform::from_xyz(0.0, 0.13, 0.33), Visibility::Inherited, Mesh3d(a.sac.clone()), MeshMaterial3d(a.sac_mat.clone()), ToadSac))
        .with_children(|c| {
            c.spawn((PointLight { color: Color::srgb(0.55, 1.0, 0.4), intensity: 9000.0, range: 6.0, ..default() }, Transform::from_xyz(0.0, 0.05, 0.12)));
        })
        .id();
    commands.entity(toad).add_child(sac);
    // Vulture feeding (mantled, legs down) + one soaring above.
    for (k, (dy, state)) in [(0.0, VState::Feed), (4.5, VState::Soar)].into_iter().enumerate() {
        let p = at(14.0) + Vec3::Y * dy;
        let e = commands
            .spawn((
                Transform::from_translation(p).with_rotation(Quat::from_rotation_y(std::f32::consts::PI * (0.8 + 0.4 * k as f32)))
                    .with_scale(Vec3::splat(1.15)),
                Visibility::default(),
                Mesh3d(a.vul_body.clone()),
                MeshMaterial3d(a.mat.clone()),
                Display,
                Vulture { slot: k, anchor: Vec2::ZERO, chest: false, state, ang: 0.0, radius: 1.0, alt: 0.0, pos: p, facing: 0.0, timer: 0.0,
                    flap: 0.0, atk_cd: 0.0, hp: 1.0, feed_at: Vec2::ZERO },
            ))
            .id();
        attach_vulture_parts(&mut commands, &a, e, state != VState::Feed);
    }
    // Antlion pit with the head up and jaws open.
    let p2 = base + Vec2::new(23.0, 0.0);
    let y = pit_seat(p2);
    if let Some(kit) = crate::realforest::get() {
        kit.spawn_static_with(&mut commands, "odd_antlion_pit", Transform::from_xyz(p2.x, y, p2.y), ());
    }
    let head = commands
        .spawn((
            Transform::from_xyz(p2.x, y - 0.12, p2.y).with_rotation(Quat::from_rotation_y(std::f32::consts::PI * 0.9)).with_scale(Vec3::splat(1.25)),
            Visibility::default(),
            Mesh3d(a.ant_head.clone()),
            MeshMaterial3d(a.mat.clone()),
            Display,
            Antlion { slot: 0, centre: p2, base_y: y, strike: 0.0, bite_cd: 0.0, pit: Entity::PLACEHOLDER },
        ))
        .id();
    commands.entity(head).with_children(|c| {
        for right in [false, true] {
            let piv = if right { Vec3::new(-JAW_PIVOT.x, JAW_PIVOT.y, JAW_PIVOT.z) } else { JAW_PIVOT };
            c.spawn((Transform::from_translation(piv), Visibility::Inherited, Mesh3d(if right { a.jaw_r.clone() } else { a.jaw_l.clone() }),
                MeshMaterial3d(a.mat.clone()), Jaw { right }));
        }
    });
    // Wolverine, standing.
    if let Some(h) = a.wolverine.clone() {
        let p = at(31.0);
        let root = commands
            .spawn((Transform::from_translation(p).with_rotation(Quat::from_rotation_y(std::f32::consts::PI * 0.75)).with_scale(Vec3::splat(0.62)),
                Visibility::default(), crate::quadruped::QuadDrive::new(crate::quadruped::QuadSpecies::Bear), Display))
            .id();
        crate::quadruped::spawn_quad(&mut commands, root, &a.mat, crate::quadruped::QuadSpecies::Bear, h);
    }
    info!("oddities: FOREST_ODDLINE staged at {base:?} (nest x+0, toad +7, vultures +14, antlion +23, wolverine +31)");
}
