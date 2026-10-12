//! **Tobin, the castaway** (spec 2026-10-13 "Żywa wyspa" §2 E, item 18). The castaways' snow-house
//! (`stories_cold`, on the snow coast) already shows sled tracks leading off; here they lead
//! somewhere: a pair of runner grooves winds 40–60u along the coast from the igloo to a sea-grotto
//! (`castaway_grotto` in `stashes.glb`: a rock overhang with the boat's sail rigged across its mouth,
//! a bough bed, a dead fire), past a broken runner dropped on the way. Under the sail sits Tobin, the
//! ship's boy, starved thin.
//!
//! **E "Help him up"** — he gets up and walks out; from there he is a townsperson (the freed-captive
//! path, `villagers::release_captives`) who makes his own way to the fort, and the town gains one
//! soul (+1 population). His one line closes the igloo only half-way: *"Nine came off the reef. Six
//! walked inland."* Rescued state rides the save as `WorldFlags["tobin_rescued"]`.

use std::f32::consts::TAU;
use std::sync::Mutex;

use bevy::camera::visibility::VisibilityRange;
use bevy::prelude::*;

use crate::biome::{Biome, BiomeEntity};
use crate::game_state::SimAppExt;
use crate::interaction::{Interactable, Interacted};
use crate::savegame::WorldFlags;

const GROTTO_FOOT: f32 = 3.4;
const SEED: u32 = 0x70B1;

#[derive(Clone, Copy)]
struct Plan {
    igloo: Vec2,
    igloo_yaw: f32,
    grotto: Vec2,
    yaw: f32,
}

static PLAN: Mutex<Option<Plan>> = Mutex::new(None);

pub fn reset_plan() {
    *PLAN.lock().unwrap() = None;
}

pub fn planned_footprints() -> Vec<(Vec2, f32)> {
    PLAN.lock().unwrap().iter().map(|p| (p.grotto, GROTTO_FOOT + 1.0)).collect()
}

fn sea_dir(q: Vec2, reach: f32) -> Option<Vec2> {
    let mut best: Option<(f32, Vec2)> = None;
    for k in 0..24 {
        let a = k as f32 * (TAU / 24.0);
        let d = Vec2::new(a.cos(), a.sin());
        let mut r = GROTTO_FOOT + 1.5;
        while r <= reach {
            if crate::worldmap::is_open_water_world(q.x + d.x * r, q.y + d.y * r) {
                if best.map_or(true, |(b, _)| r < b) {
                    best = Some((r, d));
                }
                break;
            }
            r += 1.5;
        }
    }
    best.map(|(_, d)| d)
}

/// Build phase 4, right after `stories_cold::plan` (needs the igloo): a coastal snow spot 40–60u
/// from the igloo, open sea close in front, flat enough for the overhang.
pub fn plan() {
    reset_plan();
    let Some((igloo, igloo_yaw)) = crate::stories_cold::castaways_site() else {
        warn!("castaway: no castaways' snow-house planned — no Tobin");
        return;
    };
    let mut best: Option<(f32, Plan)> = None;
    for k in 0..72 {
        let a = k as f32 * (TAU / 72.0);
        for r in [42.0f32, 46.0, 50.0, 54.0, 58.0] {
            let p = igloo + Vec2::new(a.cos(), a.sin()) * r;
            let Some(y0) = crate::worldmap::ground_at_world(p.x, p.y) else { continue };
            if crate::worldmap::tile_biome_world(p.x, p.y) != Some(Biome::Snow) || crate::worldmap::is_open_water_world(p.x, p.y) {
                continue;
            }
            let Some(sea) = sea_dir(p, 16.0) else { continue };
            let mut spread = 0.0f32;
            let mut ok = true;
            for j in 0..12 {
                let b = j as f32 * (TAU / 12.0);
                match crate::worldmap::ground_at_world(p.x + b.cos() * GROTTO_FOOT, p.y + b.sin() * GROTTO_FOOT) {
                    Some(y) => spread = spread.max((y - y0).abs()),
                    None => ok = false,
                }
                if crate::roads::on_road(p.x + b.cos() * (GROTTO_FOOT + 2.0), p.y + b.sin() * (GROTTO_FOOT + 2.0)) {
                    ok = false;
                }
            }
            if !ok || spread > 1.4 || crate::poi::overlaps_planned_clearing(p.x, p.y, GROTTO_FOOT) {
                continue;
            }
            let score = spread + (r - 50.0).abs() * 0.02;
            // Local -Z faces the sea: yaw such that (−sin, −cos) = sea.
            let yaw = (-sea.x).atan2(-sea.y);
            if best.map_or(true, |(s, _)| score < s) {
                best = Some((score, Plan { igloo, igloo_yaw, grotto: p, yaw }));
            }
        }
    }
    match best {
        Some((_, p)) => {
            crate::blockers::reserve_visual(p.grotto.x, p.grotto.y, GROTTO_FOOT);
            info!("castaway: grotto planned at {:.1},{:.1} ({:.0}u from the igloo)", p.grotto.x, p.grotto.y, p.grotto.distance(p.igloo));
            *PLAN.lock().unwrap() = Some(p);
        }
        None => warn!("castaway: no coastal spot for the grotto"),
    }
}

/// The sled's path: out of the igloo's back (+Z) and along a gentle S-curve to the grotto mouth.
fn track_path(p: &Plan) -> Vec<Vec2> {
    let start = p.igloo + Vec2::new(p.igloo_yaw.sin(), p.igloo_yaw.cos()) * 4.2;
    let front = Vec2::new(-p.yaw.sin(), -p.yaw.cos());
    let end = p.grotto + front * 2.6;
    let d = end - start;
    let side = Vec2::new(-d.y, d.x).normalize_or_zero();
    let n = (d.length() / 0.6).ceil() as usize;
    (0..=n)
        .map(|i| {
            let t = i as f32 / n as f32;
            start + d * t + side * (t * TAU).sin() * 3.5 * (1.0 - t)
        })
        .collect()
}

/// Two runner grooves (pressed, shadowed snow) as one thin ribbon mesh hugging the ground.
fn track_mesh(path: &[Vec2]) -> Mesh {
    use bevy::asset::RenderAssetUsages;
    use bevy::mesh::{Indices, PrimitiveTopology};
    let mut pos: Vec<[f32; 3]> = Vec::new();
    let mut nrm: Vec<[f32; 3]> = Vec::new();
    let mut col: Vec<[f32; 4]> = Vec::new();
    let mut idx: Vec<u32> = Vec::new();
    for runner in [-0.27f32, 0.27] {
        let base = pos.len() as u32;
        let mut alive = 0u32;
        for (i, p) in path.iter().enumerate() {
            let t = if i + 1 < path.len() { path[i + 1] - *p } else { *p - path[i - 1] };
            let side = Vec2::new(-t.y, t.x).normalize_or_zero();
            let c = *p + side * runner;
            for w in [-0.055f32, 0.055] {
                let q = c + side * w;
                let y = crate::steer::footing(q.x, q.y).unwrap_or(0.0) + 0.025;
                pos.push([q.x, y, q.y]);
                nrm.push([0.0, 1.0, 0.0]);
                // Fade out where a fresh drift covered them; a cool blue-grey in the groove.
                let fade = ((i as f32 * 0.37).sin() * 0.5 + 0.5).powf(3.0);
                let k = 0.62 + 0.25 * fade;
                col.push([0.62 * k, 0.7 * k, 0.86 * k, 1.0]);
            }
            if i > 0 {
                let a = base + (alive - 1) * 2;
                let b = base + alive * 2;
                let water = crate::worldmap::is_open_water_world(p.x, p.y);
                if !water && (i % 23) != 11 {
                    idx.extend([a, b, a + 1, a + 1, b, b + 1]);
                }
            }
            alive += 1;
        }
    }
    Mesh::new(PrimitiveTopology::TriangleList, RenderAssetUsages::default())
        .with_inserted_attribute(Mesh::ATTRIBUTE_POSITION, pos)
        .with_inserted_attribute(Mesh::ATTRIBUTE_NORMAL, nrm)
        .with_inserted_attribute(Mesh::ATTRIBUTE_COLOR, col)
        .with_inserted_indices(Indices::U32(idx))
}

/// Build phase 32: the grotto and the tracks (Tobin himself spawns once the world is ready).
pub fn populate(commands: &mut Commands, meshes: &mut Assets<Mesh>, materials: &mut Assets<StandardMaterial>) {
    let Some(p) = *PLAN.lock().unwrap() else { return };
    let Some(kit) = crate::realforest::get().filter(|k| k.has("castaway_grotto")) else { return };
    let range = VisibilityRange { start_margin: 0.0..0.0, end_margin: 120.0..140.0, use_aabb: true };
    let y = crate::worldmap::ground_at_world(p.grotto.x, p.grotto.y).unwrap_or(0.0) - 0.08;
    let tf = Transform::from_xyz(p.grotto.x, y, p.grotto.y).with_rotation(Quat::from_rotation_y(p.yaw));
    if let Some(e) = kit.spawn_static_with(commands, "castaway_grotto", tf, range.clone()) {
        commands.entity(e).insert(BiomeEntity);
        crate::landmarks::attach_story(commands, e, "The Sail Shelter", "A longboat's sail rigged across a rock overhang. Someone is still here.");
    }
    for (x, z, hw, hd) in [(-1.5f32, 0.5f32, 0.75f32, 1.3f32), (1.55, 0.4, 0.7, 1.2), (0.0, 1.25, 1.4, 0.55)] {
        let o = tf.rotation * Vec3::new(x, 0.0, z);
        crate::blockers::add_obb(p.grotto.x + o.x, p.grotto.y + o.z, hw, hd, p.yaw);
    }
    let path = track_path(&p);
    let mat = materials.add(StandardMaterial { base_color: Color::WHITE, perceptual_roughness: 0.95, reflectance: 0.2, ..default() });
    commands.spawn((Mesh3d(meshes.add(track_mesh(&path))), MeshMaterial3d(mat), Transform::IDENTITY, range.clone(), BiomeEntity,
        bevy::light::NotShadowCaster));
    // The broken runner, dropped beside the track a third of the way along.
    let i = path.len() / 3;
    let q = path[i] + Vec2::new(0.9, 0.6);
    let yq = crate::steer::footing(q.x, q.y).unwrap_or(0.0);
    let d = path[i + 1] - path[i];
    if let Some(e) = kit.spawn_static_with(commands, "sled_runner", Transform::from_xyz(q.x, yq, q.y).with_rotation(Quat::from_rotation_y(d.x.atan2(d.y) + 0.4)), range) {
        commands.entity(e).insert(BiomeEntity);
    }
    info!("castaway: grotto at {:.1},{:.1}, {} track points from the igloo", p.grotto.x, p.grotto.y, path.len());
}

/// Tobin (while unrescued).
#[derive(Component)]
struct Tobin {
    seed: u32,
}

pub struct CastawayPlugin;

impl Plugin for CastawayPlugin {
    fn build(&self, app: &mut App) {
        app.add_systems(Update, spawn_tobin.run_if(crate::rts::in_campaign));
        app.add_sim_systems((help_up, reconcile_tobin));
    }
}

/// Where Tobin sits: under the sail, on the bough bed, facing the sea.
fn berth(p: &Plan) -> crate::captives::Berth {
    let rot = Quat::from_rotation_y(p.yaw);
    let y = crate::worldmap::ground_at_world(p.grotto.x, p.grotto.y).unwrap_or(0.0) - 0.08;
    let at = |x: f32, z: f32| Vec3::new(p.grotto.x, y, p.grotto.y) + rot * Vec3::new(x, 0.06, z);
    let face = p.yaw + std::f32::consts::PI;
    crate::captives::Berth {
        seat: at(-0.2, 0.35),
        seat_yaw: face,
        bars: at(-0.1, -0.35),
        bars_yaw: face,
        cage: p.grotto,
        sit_h: crate::captives::SIT_H_FLAT_STRAW,
    }
}

fn spawn_tobin(
    mut commands: Commands,
    mut meshes: ResMut<Assets<Mesh>>,
    mut creature_mats: ResMut<Assets<crate::creature::CreatureMaterial>>,
    ready: Res<crate::biome::WorldReady>,
    flags: Res<WorldFlags>,
    mut done: Local<bool>,
) {
    if *done || !ready.0 {
        return;
    }
    *done = true;
    let Some(p) = *PLAN.lock().unwrap() else { return };
    if flags.is("tobin_rescued") {
        return;
    }
    let seed = SEED;
    let e = crate::villagers::spawn_cage_captive(&mut commands, &mut meshes, &mut creature_mats, berth(&p), crate::camps::CageKey::Decor, seed);
    commands.entity(e).insert((Tobin { seed }, Interactable::new("Help him up", 2.6)));
    info!("castaway: Tobin waits at {:.1},{:.1}", p.grotto.x, p.grotto.y);
}

#[allow(clippy::too_many_arguments)]
fn help_up(
    time: Res<Time>,
    mut ev: MessageReader<Interacted>,
    mut flags: ResMut<WorldFlags>,
    mut town: ResMut<crate::town::TownRes>,
    mut floats: ResMut<crate::combat_fx::FloatQueue>,
    mut cues: MessageWriter<crate::audio::AudioCue>,
    mut commands: Commands,
    q: Query<(&Tobin, &Transform)>,
) {
    let now = time.elapsed_secs();
    for Interacted(e) in ev.read() {
        let Ok((t, tf)) = q.get(*e) else { continue };
        // "Door" faces the fort: release_captives walks him out along the frame's +X.
        let to_fort = (-Vec2::new(tf.translation.x, tf.translation.z)).normalize_or_zero();
        let out_tf = Transform::from_translation(tf.translation).with_rotation(Quat::from_rotation_y((-to_fort.y).atan2(to_fort.x)));
        crate::villagers::release_captives(&mut commands, now, &out_tf, &[(*e, t.seed)]);
        commands.entity(*e).remove::<(Interactable, Tobin)>();
        town.0.population += 1;
        flags.set("tobin_rescued", 1);
        // Tobin: "Nine came off the reef. Six walked inland."
        floats.0.push(crate::combat_fx::FloatReq {
            world: tf.translation + Vec3::Y * 2.0,
            text: "\"Nine came off the reef. Six walked inland.\"".into(),
            color: Color::srgb(0.9, 0.92, 1.0),
            scale: 1.0,
        });
        cues.write(crate::audio::AudioCue::CampRescue(tf.translation));
    }
}

/// A Continue into a run where Tobin was already brought home: drop the waiting boy.
fn reconcile_tobin(flags: Res<WorldFlags>, mut commands: Commands, q: Query<Entity, With<Tobin>>) {
    if flags.is_changed() && flags.is("tobin_rescued") {
        for e in &q {
            commands.entity(e).try_despawn();
        }
    }
}
