//! Realistic skinned red deer for the wild `Deer` / `Elk` herds, replacing the studio quad rig the way
//! `npc_skin` replaces the studio villager body.
//!
//! Content: `assets/animals/deer_doe.glb` / `deer_stag.glb` — CDmir's CC0 red deer (OpenGameArt),
//! skinned + PBR textured, with Idle / Idle2 / LookAround / Eat / Run / Die from the source and a
//! Walk authored on export (`tools/animals/export_deer.py`). Facing +Z like the studio rig, feet at 0.
//!
//! Runtime contract: the wildlife brain is untouched; it keeps writing [`Animal`] + [`QuadDrive`] and
//! the studio rig still exists under the root (hidden once the skin shows). [`drive_skins`] picks the
//! clip from the brain's state and the root's REAL ground speed and paces the gait clips to it.
//! `FOREST_NOANIMALSKIN=1` turns it off.

use std::collections::HashMap;
use std::time::Duration;

use bevy::camera::visibility::NoFrustumCulling;
use bevy::gltf::Gltf;
use bevy::prelude::*;
use bevy::world_serialization::{WorldAsset, WorldAssetRoot, WorldInstanceReady};

use crate::critters::Species;
use crate::npc_skin::WORLD_PER_M;
use crate::quadruped::{QuadDrive, QuadJoint, QuadPart};
use crate::wildlife::Animal;

/// (file, hip height m, Walk ground speed m/s at 1x — `export_deer.py` logs it).
const MODELS: [(&str, f32, f32); 2] = [("animals/deer_doe.glb", 1.12, 1.222), ("animals/deer_stag.glb", 1.30, 1.418)];
const DOE: usize = 0;
const STAG: usize = 1;
/// The source run's ground speed against its walk (the gallop covers ~4x the walk's ground a second).
const RUN_K: f32 = 4.0;
/// An elk is a big stag.
const ELK_SIZE: f32 = 1.18;
const ANIM_CULL2: f32 = 90.0 * 90.0;
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
struct DeerModels {
    gltf: Vec<Handle<Gltf>>,
    ready: Vec<Option<Model>>,
}

/// On a deer's gameplay root: its skin instance + animation state.
#[derive(Component)]
pub struct AnimalSkin {
    model: usize,
    inst: Entity,
    player: Option<Entity>,
    clip: &'static str,
    last: Vec3,
    speed: f32,
    /// World units a second the Walk covers at 1x for this body.
    walk: f32,
}

/// On the skin instance: the gameplay root it dresses.
#[derive(Component)]
struct SkinOf(Entity);

/// Skin instance waiting out its first frames hidden (see `npc_skin::Reveal` — never visible while
/// its materials are pending).
#[derive(Component)]
struct Reveal(u8);

fn load_models(mut commands: Commands, server: Res<AssetServer>) {
    commands.insert_resource(DeerModels {
        gltf: MODELS.iter().map(|m| server.load(m.0)).collect(),
        ready: MODELS.iter().map(|_| None).collect(),
    });
}

fn finish_models(
    mut models: ResMut<DeerModels>,
    server: Res<AssetServer>,
    gltfs: Res<Assets<Gltf>>,
    mut graphs: ResMut<Assets<AnimationGraph>>,
) {
    for i in 0..MODELS.len() {
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
    models: Res<DeerModels>,
    mut deer: Query<(Entity, &mut Animal, &Transform), (With<QuadDrive>, Without<AnimalSkin>, Without<crate::dying::Dying>)>,
) {
    for (e, mut a, tf) in &mut deer {
        let elk = match a.species {
            Species::Deer => false,
            Species::Elk => true,
            _ => continue,
        };
        let h = hash(e);
        // the herds are mostly hinds with the odd stag; every elk is a bull
        let model = if elk || h % 100 < 35 { STAG } else { DOE };
        let Some(m) = models.ready[model].as_ref() else { continue };
        // ±5% size, nobody the same
        let size = (0.95 + 0.1 * ((h >> 8) & 255) as f32 / 255.0) * if elk { ELK_SIZE } else { 1.0 };
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
            model,
            inst: child,
            player: None,
            clip: "",
            last: tf.translation,
            speed: 0.0,
            walk: MODELS[model].2 * WORLD_PER_M * size,
        });
    }
}

fn skin_ready(
    ready: On<WorldInstanceReady>,
    mut commands: Commands,
    models: Res<DeerModels>,
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
    let Some(m) = models.ready[sk.model].as_ref() else { return };
    for d in children.iter_descendants(inst) {
        if players.contains(d) {
            commands.entity(d).insert((AnimationGraphHandle(m.graph.clone()), AnimationTransitions::new()));
            sk.player = Some(d);
        }
        if meshes.contains(d) {
            // skinned bounds follow the rest pose only; a lying-down death would cull wrongly
            commands.entity(d).insert(NoFrustumCulling);
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
    }
}

/// Pick + cross-fade each deer's clip from its brain state and real ground speed.
fn drive_skins(
    time: Res<Time>,
    cam: Query<&GlobalTransform, With<Camera3d>>,
    mut roots: Query<(Entity, &mut AnimalSkin, &Animal, &QuadDrive, &GlobalTransform, Has<crate::dying::Dying>)>,
    mut players: Query<(&mut AnimationPlayer, &mut AnimationTransitions)>,
    models: Res<DeerModels>,
) {
    let dt = time.delta_secs();
    if dt <= 0.0 {
        return;
    }
    let now = time.elapsed_secs();
    let cam_p = cam.iter().next().map(|g| g.translation());
    for (e, mut sk, a, d, gt, dying) in &mut roots {
        let Some(pe) = sk.player else { continue };
        let Ok((mut player, mut tr)) = players.get_mut(pe) else { continue };
        let p = gt.translation();
        let v = Vec2::new(p.x - sk.last.x, p.z - sk.last.z).length() / dt;
        sk.last = p;
        sk.speed += (v.min(14.0) - sk.speed) * (dt * 6.0).min(1.0);
        let far = cam_p.is_some_and(|c| c.distance_squared(p) > ANIM_CULL2);
        let walking = matches!(sk.clip, "Walk" | "Run");
        let moving = sk.speed > if walking { 0.12 } else { 0.3 };
        let walk = sk.walk;
        let h = hash(e);
        let (clip, once, rate): (&'static str, bool, f32) = if dying {
            ("Die", true, 1.0)
        } else if moving && (d.attacking || (a.hurrying() && sk.speed > walk * 1.6) || sk.speed > walk * 2.4) {
            ("Run", false, (sk.speed / (walk * RUN_K)).clamp(0.6, 1.5))
        } else if moving {
            ("Walk", false, (sk.speed / walk).clamp(0.5, 1.9))
        } else if a.grazing() {
            // a grazing deer mostly has its head down, now and then lifting it to look round
            let turn = (now / 9.0) as u32 + h % 5;
            (["Eat", "Eat", "LookAround", "Eat", "Idle"][(turn % 5) as usize], false, 1.0)
        } else {
            let turn = (now / 11.0) as u32 + h % 3;
            (["Idle", "Idle2", "LookAround"][(turn % 3) as usize], false, 1.0)
        };
        if clip != sk.clip {
            let Some(&node) = models.ready[sk.model].as_ref().and_then(|m| m.nodes.get(clip)) else { continue };
            let first = sk.clip.is_empty();
            let anim = tr.play(&mut player, node, if first { Duration::ZERO } else { FADE });
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
