//! Realistic skinned wildlife — red deer (the `Deer` / `Elk` herds), grey wolf, brown bear (the
//! `Boar` slot: the game's forest bruiser has always worn the bear rig) — replacing the studio quad rig
//! the way `npc_skin` replaces the studio villager body.
//!
//! Content (`assets/animals/`, credits in `assets/CREDITS.md`), each skinned + PBR textured, facing +Z
//! like the studio rig with its feet at 0, in real metres:
//! - `deer_doe.glb` / `deer_stag.glb` — CDmir's CC0 red deer; Idle / Idle2 / LookAround / Eat / Run /
//!   Die from the source, Walk authored on export (`tools/animals/export_deer.py`).
//! - `wolf.glb` — kenchoo's CC-BY "Grey Wolf Rebuilt"; source Idle, Walk / Trot / Run / Attack authored
//!   on its rebuilt leg IK (`tools/animals/export_wolf.py`).
//! - `bear.glb` — Andrey's CC-BY "Brown Bear (animated)"; source Amble, Walk / Run / Attack / Idle
//!   authored on its rebuilt leg IK (`tools/animals/export_bear.py`).
//! - `polar_bear.glb` — the same bear, re-dyed creamy white and stood taller (`export_bear.py … polar`).
//! - `goat.glb` / `dog.glb` / `camel.glb` — CC-BY downloads (GerardoA400 / MAXDESIGN-3D / E.A.Cornell),
//!   gaits + Graze authored on rebuilt leg IK (`tools/animals/export_quad.py`).
//!
//! Runtime contract: the wildlife brain is untouched; it keeps writing [`Animal`] + [`QuadDrive`] and
//! the studio rig still exists under the root (hidden once the skin shows). [`drive_skins`] picks the
//! gait whose native ground speed best fits the root's REAL ground speed and paces it to that speed,
//! so the planted feet stay put. `FOREST_NOANIMALSKIN=1` turns it off.

use std::collections::HashMap;
use std::time::Duration;

use bevy::camera::visibility::{DynamicSkinnedMeshBounds, VisibleEntities};
use bevy::gltf::Gltf;
use bevy::prelude::*;
use bevy::world_serialization::{WorldAsset, WorldAssetRoot, WorldInstanceReady};

use crate::critters::Species;
use crate::npc_skin::WORLD_PER_M;
use crate::quadruped::{QuadDrive, QuadJoint, QuadPart};
use crate::wildlife::Animal;

/// One skinned animal model and how to play it.
struct Kind {
    file: &'static str,
    /// Locomotion clips, slowest first, with the ground speed (real m/s) each covers at 1x — the
    /// exporters log it. A planted foot slides back at exactly this speed.
    gaits: &'static [(&'static str, f32)],
    /// Standing loops, taken in turns (~10 s each).
    idles: &'static [&'static str],
    /// Standing loops while grazing.
    grazes: &'static [&'static str],
    /// A strike, played once across the brain's 0.45 s strike window: (clip, its length in s).
    attack: Option<(&'static str, f32)>,
    /// Played once on death (otherwise the pose freezes while `dying.rs` tips the body over).
    die: Option<&'static str>,
}

const KINDS: [Kind; 8] = [
    // Deer walk: the planted hoof covers `duty` (0.64) of the authored stride, so its native speed is
    // the stride speed over that duty. The source gallop covers ~4x the walk's stride a second.
    Kind {
        file: "animals/deer_doe.glb",
        gaits: &[("Walk", 1.222 / 0.64), ("Run", 1.222 * 4.0)],
        idles: &["Idle", "Idle2", "LookAround"],
        grazes: &["Eat", "Eat", "LookAround", "Eat", "Idle"],
        attack: None,
        die: Some("Die"),
    },
    Kind {
        file: "animals/deer_stag.glb",
        gaits: &[("Walk", 1.418 / 0.64), ("Run", 1.418 * 4.0)],
        idles: &["Idle", "Idle2", "LookAround"],
        grazes: &["Eat", "Eat", "LookAround", "Eat", "Idle"],
        attack: None,
        die: Some("Die"),
    },
    Kind {
        file: "animals/wolf.glb",
        gaits: &[("Walk", 1.493), ("Trot", 3.520), ("Run", 5.760)],
        idles: &["Idle"],
        grazes: &["Idle"],
        attack: Some(("Attack", 14.0 / 24.0)),
        die: None,
    },
    Kind {
        file: "animals/bear.glb",
        gaits: &[("Amble", 0.428), ("Walk", 1.117), ("Run", 3.771)],
        idles: &["Idle"],
        grazes: &["Idle"],
        attack: Some(("Attack", 20.0 / 24.0)),
        die: None,
    },
    Kind {
        file: "animals/polar_bear.glb",
        gaits: &[("Amble", 0.506), ("Walk", 1.320), ("Run", 4.457)],
        idles: &["Idle"],
        grazes: &["Idle"],
        attack: Some(("Attack", 20.0 / 24.0)),
        die: None,
    },
    Kind {
        file: "animals/goat.glb",
        gaits: &[("Walk", 1.140), ("Run", 4.911)],
        idles: &["Idle"],
        grazes: &["Graze", "Graze", "Idle"],
        attack: None,
        die: None,
    },
    Kind {
        file: "animals/dog.glb",
        gaits: &[("Walk", 0.766), ("Trot", 1.806), ("Run", 2.956)],
        idles: &["Idle"],
        grazes: &["Graze", "Idle"],
        attack: None,
        die: None,
    },
    Kind {
        file: "animals/camel.glb",
        gaits: &[("Walk", 0.992), ("Run", 4.333)],
        idles: &["Idle", "Idle2"],
        grazes: &["Graze", "Graze", "Idle2"],
        attack: None,
        die: None,
    },
];
const DOE: usize = 0;
const STAG: usize = 1;
const WOLF: usize = 2;
const BEAR: usize = 3;
const POLAR: usize = 4;
const GOAT: usize = 5;
const DOG: usize = 6;
const CAMEL: usize = 7;
/// An elk is a big stag.
const ELK_SIZE: f32 = 1.18;
/// The brain's strike window (`wildlife::quad_drive`).
const STRIKE_S: f32 = 0.45;
/// Past this the skin's pose freezes and its animation graph is detached (`drive_skins`) — a paused
/// clip still costs `animate_targets` a full per-bone evaluation every frame, a graph-less player
/// costs one lookup. Re-attached inside [`ANIM_WAKE2`] (hysteresis, so it can't flicker).
const ANIM_CULL2: f32 = 90.0 * 90.0;
const ANIM_WAKE2: f32 = 82.0 * 82.0;
/// Skinned animal meshes stop drawing past 140 u (they skip frustum culling, see `skin_ready`).
const SKIN_RANGE: bevy::camera::visibility::VisibilityRange = bevy::camera::visibility::VisibilityRange {
    start_margin: 0.0..0.0,
    end_margin: 140.0..140.0,
    use_aabb: false,
};
const FADE: Duration = Duration::from_millis(300);

pub struct AnimalSkinPlugin;

impl Plugin for AnimalSkinPlugin {
    fn build(&self, app: &mut App) {
        if std::env::var_os("FOREST_NOANIMALSKIN").is_some() {
            return;
        }
        app.add_systems(Startup, load_models)
            .add_systems(Update, (finish_models, attach_skins, reveal_skins, drive_skins).chain());
    }
}

struct Model {
    scene: Handle<WorldAsset>,
    graph: Handle<AnimationGraph>,
    nodes: HashMap<String, AnimationNodeIndex>,
}

#[derive(Resource)]
struct AnimalModels {
    gltf: Vec<Handle<Gltf>>,
    ready: Vec<Option<Model>>,
}

/// On an animal's gameplay root: its skin instance + animation state.
#[derive(Component)]
pub struct AnimalSkin {
    kind: usize,
    inst: Entity,
    player: Option<Entity>,
    clip: &'static str,
    last: Vec3,
    speed: f32,
    /// World units per real metre of this body (the per-animal size jitter included).
    k: f32,
    /// Far from / unseen by the camera: the player's graph is detached so `animate_targets` skips
    /// its bones (see `crate::anim_lod`).
    parked: bool,
    /// One of the skin's mesh entities (on-screen test) and how long it has been off screen.
    body: Option<Entity>,
    unseen: f32,
    /// Every mesh entity of the skin (shadow LOD) and whether they currently cast.
    meshes: Vec<Entity>,
    casting: bool,
}

/// On the skin instance: the gameplay root it dresses.
#[derive(Component)]
struct SkinOf(Entity);

/// Skin instance waiting out its first frames hidden (see `npc_skin::Reveal` — never visible while
/// its materials are pending).
#[derive(Component)]
struct Reveal(u8);

fn load_models(mut commands: Commands, server: Res<AssetServer>) {
    commands.insert_resource(AnimalModels {
        gltf: KINDS.iter().map(|k| server.load(k.file)).collect(),
        ready: KINDS.iter().map(|_| None).collect(),
    });
}

fn finish_models(
    mut models: ResMut<AnimalModels>,
    server: Res<AssetServer>,
    gltfs: Res<Assets<Gltf>>,
    mut graphs: ResMut<Assets<AnimationGraph>>,
) {
    for i in 0..KINDS.len() {
        if models.ready[i].is_some() || !server.is_loaded_with_dependencies(models.gltf[i].id()) {
            continue;
        }
        let Some(g) = gltfs.get(&models.gltf[i]) else { continue };
        let Some(scene) = g.scenes.first().cloned() else { continue };
        let mut names: Vec<_> = g.named_animations.iter().map(|(n, h)| (n.to_string(), h.clone())).collect();
        names.sort_by(|a, b| a.0.cmp(&b.0));
        let (graph, idx) = AnimationGraph::from_clips(names.iter().map(|(_, h)| h.clone()));
        let nodes = names.into_iter().map(|(n, _)| n).zip(idx).collect();
        models.ready[i] = Some(Model { scene, graph: graphs.add(graph), nodes });
    }
}

fn hash(e: Entity) -> u32 {
    e.index_u32().wrapping_mul(2_654_435_761) ^ 0x9e37_79b9
}

fn attach_skins(
    mut commands: Commands,
    models: Res<AnimalModels>,
    mut animals: Query<(Entity, &mut Animal, &Transform), (With<QuadDrive>, Without<AnimalSkin>, Without<crate::dying::Dying>)>,
) {
    for (e, mut a, tf) in &mut animals {
        let h = hash(e);
        // the herds are mostly hinds with the odd stag; every elk is a bull
        let (kind, extra) = match a.species {
            Species::Deer => (if h % 100 < 35 { STAG } else { DOE }, 1.0),
            Species::Elk => (STAG, ELK_SIZE),
            Species::Wolf => (WOLF, 1.0),
            Species::Boar => (BEAR, 1.0),
            Species::PolarBear => (POLAR, 1.0),
            Species::Goat => (GOAT, 1.0),
            Species::Dog => (DOG, 1.0),
            Species::Camel => (CAMEL, 1.0),
            _ => continue,
        };
        let Some(m) = models.ready[kind].as_ref() else { continue };
        // ±5% size, nobody the same
        let size = (0.95 + 0.1 * ((h >> 8) & 255) as f32 / 255.0) * extra;
        // cancel the root's studio scale: the model is in real metres
        let s = WORLD_PER_M * size / tf.scale.x.max(1e-3);
        a.clear_bob();
        let child = commands
            .spawn((WorldAssetRoot(m.scene.clone()), Transform::from_scale(Vec3::splat(s)), Visibility::Hidden, SkinOf(e)))
            .observe(skin_ready)
            .id();
        commands.queue(move |world: &mut World| {
            if world.get_entity(e).is_ok() {
                world.entity_mut(e).add_child(child);
            } else if let Ok(c) = world.get_entity_mut(child) {
                c.despawn();
            }
        });
        commands.entity(e).try_insert(AnimalSkin {
            kind,
            inst: child,
            player: None,
            clip: "",
            last: tf.translation,
            speed: 0.0,
            k: WORLD_PER_M * size,
            parked: false,
            body: None,
            unseen: 0.0,
            meshes: Vec::new(),
            casting: true,
        });
    }
}

fn skin_ready(
    ready: On<WorldInstanceReady>,
    mut commands: Commands,
    models: Res<AnimalModels>,
    of: Query<&SkinOf>,
    children: Query<&Children>,
    players: Query<(), With<AnimationPlayer>>,
    meshes: Query<(), With<Mesh3d>>,
    mut roots: Query<&mut AnimalSkin>,
) {
    let inst = ready.entity;
    let Ok(SkinOf(root)) = of.get(inst) else { return };
    let Ok(mut sk) = roots.get_mut(*root) else { return };
    if sk.inst != inst {
        return;
    }
    let Some(m) = models.ready[sk.kind].as_ref() else { return };
    for d in children.iter_descendants(inst) {
        if players.contains(d) {
            commands.entity(d).insert((AnimationGraphHandle(m.graph.clone()), AnimationTransitions::new()));
            sk.player = Some(d);
            sk.parked = false; // a fresh player starts with its graph attached
        }
        if meshes.contains(d) {
            // frustum-culled on joint-driven bounds (a lunge or a fall grows the box with the pose);
            // past the haze a distant animal is a few pixels: stop drawing it (and its shadow) there
            commands.entity(d).insert((DynamicSkinnedMeshBounds, SKIN_RANGE, crate::quality::SmallDetail));
            sk.body.get_or_insert(d);
            sk.meshes.push(d);
        }
    }
    sk.clip = "";
    commands.entity(inst).insert(Reveal(0));
}

/// Show the skin a few frames after its instance is ready, and hide the studio body under it.
fn reveal_skins(
    mut commands: Commands,
    mut q: Query<(Entity, &mut Reveal, &SkinOf)>,
    mut parts: Query<(&QuadPart, &mut Visibility)>,
    kids: Query<&Children>,
) {
    for (e, mut r, of) in &mut q {
        r.0 += 1;
        if r.0 < 8 {
            continue;
        }
        commands.entity(e).try_remove::<Reveal>().try_insert(Visibility::Inherited);
        for c in kids.iter_descendants(of.0) {
            if let Ok((p, mut v)) = parts.get_mut(c) {
                if p.joint == QuadJoint::Root {
                    *v = Visibility::Hidden;
                }
            }
        }
        // The procedural body is hidden for good: stop posing its ~20 joints every frame.
        commands.entity(of.0).try_insert(crate::quadruped::QuadHidden);
    }
}

/// Pick + cross-fade each animal's clip from its brain state and real ground speed.
fn drive_skins(
    mut commands: Commands,
    time: Res<Time>,
    cam: Query<(&GlobalTransform, &VisibleEntities), With<Camera3d>>,
    mut roots: Query<(Entity, &mut AnimalSkin, &Animal, &QuadDrive, &GlobalTransform, Has<crate::dying::Dying>)>,
    mut players: Query<(&mut AnimationPlayer, &mut AnimationTransitions)>,
    models: Res<AnimalModels>,
) {
    let dt = time.delta_secs();
    if dt <= 0.0 {
        return;
    }
    let now = time.elapsed_secs();
    let cam_p = cam.iter().next().map(|(g, _)| g.translation());
    let on_screen = crate::anim_lod::on_screen_set(cam.iter().next().map(|(_, v)| v));
    for (e, mut sk, a, d, gt, dying) in &mut roots {
        let Some(pe) = sk.player else { continue };
        let Ok((mut player, mut tr)) = players.get_mut(pe) else { continue };
        let kind = &KINDS[sk.kind];
        let p = gt.translation();
        let v = Vec2::new(p.x - sk.last.x, p.z - sk.last.z).length() / dt;
        sk.last = p;
        sk.speed += (v.min(14.0) - sk.speed) * (dt * 6.0).min(1.0);
        let d2 = cam_p.map_or(0.0, |c| c.distance_squared(p));
        let far = d2 > if sk.parked { ANIM_WAKE2 } else { ANIM_CULL2 };
        let (body, mut unseen) = (sk.body, sk.unseen);
        let far = crate::anim_lod::park(far, d2, body, on_screen, &mut unseen, dt);
        sk.unseen = unseen;
        if let Some(cast) = crate::anim_lod::shadow_flip(sk.casting, d2) {
            sk.casting = cast;
            crate::anim_lod::set_casting(&mut commands, &sk.meshes, cast);
        }
        if far != sk.parked {
            sk.parked = far;
            if far {
                commands.entity(pe).try_remove::<AnimationGraphHandle>();
            } else if let Some(m) = models.ready[sk.kind].as_ref() {
                commands.entity(pe).try_insert(AnimationGraphHandle(m.graph.clone()));
            }
        }
        let native = |clip: &str| kind.gaits.iter().find(|g| g.0 == clip).map(|g| g.1 * sk.k);
        let stepping = native(sk.clip).is_some();
        let moving = sk.speed > if stepping { 0.12 } else { 0.3 };
        let h = hash(e);
        let (clip, once, rate): (&'static str, bool, f32) = if dying {
            match kind.die {
                Some(c) => (c, true, 1.0),
                None => (sk.clip, false, 0.0), // freeze mid-stride; `dying.rs` tips the body over
            }
        } else if let (true, Some((c, len))) = (d.attacking, kind.attack) {
            (c, true, len / STRIKE_S)
        } else if moving {
            // The gait whose native speed is nearest the body's (in ratio), with a little stickiness
            // so a speed hovering between two gaits doesn't flicker them.
            let fit = |n: f32| (sk.speed / n).ln().abs();
            let mut best = kind.gaits[0].0;
            let mut best_fit = f32::MAX;
            for &(g, _) in kind.gaits {
                let f = fit(native(g).unwrap()) - if g == sk.clip { 0.25 } else { 0.0 };
                if f < best_fit {
                    best = g;
                    best_fit = f;
                }
            }
            // a fleeing / charging animal never dawdles in its slowest gait
            if a.hurrying() && kind.gaits.len() > 1 && best == kind.gaits[0].0 && sk.speed > native(kind.gaits[0].0).unwrap() * 1.3 {
                best = kind.gaits[1].0;
            }
            (best, false, (sk.speed / native(best).unwrap()).clamp(0.55, 1.7))
        } else if a.grazing() {
            // a grazing deer mostly has its head down, now and then lifting it to look round
            let turn = (now / 9.0) as u32 + h % 5;
            (kind.grazes[turn as usize % kind.grazes.len()], false, 1.0)
        } else {
            let turn = (now / 11.0) as u32 + h % 3;
            (kind.idles[turn as usize % kind.idles.len()], false, 1.0)
        };
        if clip != sk.clip && !clip.is_empty() {
            let Some(&node) = models.ready[sk.kind].as_ref().and_then(|m| m.nodes.get(clip)) else { continue };
            let first = sk.clip.is_empty();
            let anim = tr.play(&mut player, node, if first { Duration::ZERO } else if once { FADE / 3 } else { FADE });
            if !once {
                anim.repeat();
            }
            if first {
                anim.seek_to(((h >> 16) & 1023) as f32 / 1023.0 * 2.0);
            }
            sk.clip = clip;
        }
        for (_, an) in player.playing_animations_mut() {
            an.set_speed(if far { 0.0 } else { rate });
        }
    }
}
