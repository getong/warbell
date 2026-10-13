//! Realistic skinned townsfolk: MakeHuman (MPFB) characters with Quaternius UAL clips, replacing the
//! procedural 14-joint studio body for people who carry a [`SkinRequest`].
//!
//! Content: `assets/npc/npc_<look>.glb` (53-bone skin + the clip set baked onto that look's rig) and
//! its BC7 maps (`_albedo` / `_normal` / `_orm` atlas + RGBA hair / brow / lash / beard cards), all
//! produced by `tools/npc_mpfb/export_game.py` and packed by `examples/pack_forest_textures.rs`
//! (`NPC_SRC=`). The glTF materials are placeholders matched by NAME (`npc_body`, `npc_cloth`, ...).
//!
//! Runtime contract: the gameplay brains are untouched. They keep writing [`BipedDrive`] (and the
//! studio rig still exists, hidden, so joint lookups keep working). [`drive_skins`] reads the drive
//! plus the root's real ground speed and cross-fades the matching clip on the glTF `AnimationPlayer`.
//! `FOREST_NOSKIN=1` turns the whole thing off (studio bodies everywhere).

use std::collections::HashMap;
use std::time::Duration;

use bevy::camera::visibility::NoFrustumCulling;
use bevy::gltf::{Gltf, GltfMaterialName};
use bevy::prelude::*;
use bevy::world_serialization::{WorldAsset, WorldAssetRoot, WorldInstanceReady};

use crate::biped::{BipedDrive, BipedRig};

/// Cast order = the look index a [`SkinRequest`] carries.
pub const LOOKS: [&str; 14] = [
    "farmer", "woodcutter", "miner", "guard", "archer", "villager_m", "villager_f1", "villager_f2",
    "elder_m", "elder_f", "boy", "girl", "priest", "merchant",
];
pub const FARMER: u8 = 0;
pub const WOODCUTTER: u8 = 1;
pub const MINER: u8 = 2;
pub const GUARD: u8 = 3;
pub const ARCHER: u8 = 4;
pub const VILLAGER_M: u8 = 5;
pub const VILLAGER_F1: u8 = 6;
pub const VILLAGER_F2: u8 = 7;
pub const ELDER_M: u8 = 8;
pub const ELDER_F: u8 = 9;
pub const BOY: u8 = 10;
pub const GIRL: u8 = 11;
pub const PRIEST: u8 = 12;
pub const MERCHANT: u8 = 13;

/// World units per real metre: a 1.75 m adult stands the studio villager's 1.46 u.
pub const WORLD_PER_M: f32 = 0.834;
/// Alpha-test cutoff of the hair / brow / lash cards (the packer keeps mip coverage for this).
pub const CARD_CUTOFF: f32 = 0.5;
/// Ground speed (world u/s) the walk / jog clips cover at 1x playback.
const WALK_NATIVE: f32 = 1.2;
const JOG_NATIVE: f32 = 2.9;
/// Past this camera distance a skin's player is paused (fog + distance hide the joints anyway).
const ANIM_CULL2: f32 = 90.0 * 90.0;
const FADE: Duration = Duration::from_millis(280);

pub struct NpcSkinPlugin;

impl Plugin for NpcSkinPlugin {
    fn build(&self, app: &mut App) {
        if std::env::var("FOREST_NOSKIN").is_ok() {
            return;
        }
        app.add_systems(Startup, load_cast)
            .add_systems(Update, (finish_cast, attach_skins, hide_studio_rigs, copy_tools, drive_skins, carry_loads).chain());
    }
}

/// Ask for a realistic body: the look index into [`LOOKS`]. Inserted by the spawner; the studio
/// rig is hidden and the skin attached as soon as the look's assets have loaded. Re-inserting a
/// different look (a job change) swaps the outfit.
#[derive(Component, Clone, Copy)]
pub struct SkinRequest(pub u8);

/// Clip hint from a non-locomotion brain (village life acts, vendors): `""` = let the drive pick.
#[derive(Component, Default, Clone, Copy, PartialEq)]
pub struct SkinClip(pub &'static str);

/// A root whose skin child is attached. `player` / hands fill in once the glTF instance is ready.
#[derive(Component)]
pub struct Skinned {
    look: u8,
    inst: Entity,
    tools_done: bool,
    player: Option<Entity>,
    clip: &'static str,
    last: Vec3,
    speed: f32,
    pub hand_r: Option<Entity>,
    pub hand_l: Option<Entity>,
    /// The skin's pelvis joint (read by the `FOREST_LIFECHECK` seat check).
    pub pelvis: Option<Entity>,
    /// Hand-held props copied from the studio rig: (entity, right hand?, grip -> head distance).
    props: Vec<(Entity, bool, f32)>,
    /// Which grip the props are in (true = the two-handed work / fight grip).
    work_grip: bool,
}

impl Skinned {
    /// The spawned glTF instance (the visible body) under the gameplay root.
    pub fn inst(&self) -> Entity {
        self.inst
    }
}

/// Points the glTF instance back at its gameplay root (read by the ready observer).
#[derive(Component)]
struct SkinOf(Entity);

struct LookAssets {
    scene: Handle<WorldAsset>,
    graph: Handle<AnimationGraph>,
    nodes: HashMap<String, AnimationNodeIndex>,
    mats: HashMap<&'static str, Handle<StandardMaterial>>,
}

#[derive(Resource)]
struct NpcCast {
    gltf: Vec<Handle<Gltf>>,
    mats: Vec<HashMap<&'static str, Handle<StandardMaterial>>>,
    /// Per look: dyed-cloth variants, then hair-shade variants (index 0 = the look's own).
    vars: Vec<(Vec<Handle<StandardMaterial>>, Vec<Handle<StandardMaterial>>)>,
    looks: Vec<Option<LookAssets>>,
}

/// Cloth dyes a village could afford (multiplied over the look's own albedo): undyed, madder
/// russet, woad blue, weld/olive, a dark walnut-dyed, a sun-faded grey. Townsfolk sharing a look
/// still read as different people across a street.
const CLOTH_DYES: [Vec3; 6] = [
    Vec3::new(1.0, 1.0, 1.0),
    Vec3::new(1.12, 0.86, 0.78),
    Vec3::new(0.82, 0.92, 1.1),
    Vec3::new(1.02, 1.0, 0.76),
    Vec3::new(0.7, 0.66, 0.62),
    Vec3::new(1.05, 1.05, 1.05),
];
/// Hair shades over the card texture: own, darker brown, near-black, sandy, greying.
const HAIR_SHADES: [Vec3; 5] = [
    Vec3::new(1.0, 1.0, 1.0),
    Vec3::new(0.62, 0.55, 0.5),
    Vec3::new(0.38, 0.35, 0.34),
    Vec3::new(1.35, 1.18, 0.9),
    Vec3::new(1.25, 1.25, 1.25),
];

/// A stable per-person hash (outfit dye, hair, height) from the root entity.
fn person_hash(e: Entity) -> u32 {
    let mut h = e.index_u32().wrapping_mul(0x9E37_79B9) ^ 0x5bd1_e995;
    h ^= h >> 15;
    h = h.wrapping_mul(0x2c1b_3c6d);
    h ^ (h >> 12)
}

/// Livery looks keep their colours (a guard's tabard, the archer's kit, the priest's habit).
fn uniform_look(look: u8) -> bool {
    matches!(look, GUARD | ARCHER | PRIEST)
}

fn card_key(k: &str) -> &'static str {
    match k {
        "hair" => "npc_hair",
        "beard" => "npc_beard",
        "brow" => "npc_brow",
        _ => "npc_lash",
    }
}

fn load_cast(mut commands: Commands, server: Res<AssetServer>, mut materials: ResMut<Assets<StandardMaterial>>) {
    let mut gltf = Vec::new();
    let mut mats = Vec::new();
    let mut vars = Vec::new();
    for name in LOOKS {
        gltf.push(server.load(format!("npc/npc_{name}.glb")));
        let tex = |m: &str| -> Handle<Image> { server.load(format!("npc/npc_{name}_{m}.dds")) };
        let atlas = |double: bool| StandardMaterial {
            base_color_texture: Some(tex("albedo")),
            normal_map_texture: Some(tex("normal")),
            metallic_roughness_texture: Some(tex("orm")),
            occlusion_texture: Some(tex("orm")),
            perceptual_roughness: 1.0,
            metallic: 1.0, // x the ORM blue channel (0): the factor only enables the texture read
            reflectance: 0.35,
            double_sided: double,
            cull_mode: if double { None } else { Some(bevy::render::render_resource::Face::Back) },
            ..default()
        };
        let card = |k: &str, rough: f32| StandardMaterial {
            base_color_texture: Some(tex(k)),
            alpha_mode: AlphaMode::Mask(CARD_CUTOFF),
            perceptual_roughness: rough,
            reflectance: 0.3,
            double_sided: true,
            cull_mode: None,
            ..default()
        };
        let mut m = HashMap::new();
        m.insert("npc_body", materials.add(atlas(false)));
        m.insert("npc_cloth", materials.add(atlas(true)));
        for (k, rough) in [("hair", 0.62), ("beard", 0.7), ("brow", 0.7), ("lash", 0.7)] {
            // not every look has every card (no beard on the women / kids)
            if std::path::Path::new(&format!("assets/npc/npc_{name}_{k}.dds")).exists() {
                m.insert(card_key(k), materials.add(card(k, rough)));
            }
        }
        let tint = |base: StandardMaterial, k: Vec3| StandardMaterial { base_color: Color::srgb(k.x, k.y, k.z), ..base };
        let cloth: Vec<_> = CLOTH_DYES.iter().map(|&k| materials.add(tint(atlas(true), k))).collect();
        let hair: Vec<_> = if m.contains_key("npc_hair") {
            HAIR_SHADES.iter().map(|&k| materials.add(tint(card("hair", 0.62), k))).collect()
        } else {
            Vec::new()
        };
        vars.push((cloth, hair));
        mats.push(m);
    }
    commands.insert_resource(NpcCast { looks: (0..LOOKS.len()).map(|_| None).collect(), gltf, mats, vars });
}

/// Build each look's animation graph once its GLB is in (clip name -> graph node).
fn finish_cast(mut cast: ResMut<NpcCast>, gltfs: Res<Assets<Gltf>>, mut graphs: ResMut<Assets<AnimationGraph>>) {
    if cast.looks.iter().all(Option::is_some) {
        return;
    }
    for i in 0..LOOKS.len() {
        if cast.looks[i].is_some() {
            continue;
        }
        let Some(g) = gltfs.get(&cast.gltf[i]) else { continue };
        let Some(scene) = g.scenes.first().cloned() else { continue };
        let mut names: Vec<_> = g.named_animations.iter().map(|(n, h)| (n.to_string(), h.clone())).collect();
        names.sort_by(|a, b| a.0.cmp(&b.0));
        let (graph, idx) = AnimationGraph::from_clips(names.iter().map(|(_, h)| h.clone()));
        let nodes = names.into_iter().map(|(n, _)| n).zip(idx).collect();
        let mats = cast.mats[i].clone();
        cast.looks[i] = Some(LookAssets { scene, graph: graphs.add(graph), nodes, mats });
    }
}

fn attach_skins(
    mut commands: Commands,
    cast: Res<NpcCast>,
    reqs: Query<(Entity, &SkinRequest, &Transform, Option<&Skinned>)>,
) {
    for (e, req, tf, had) in &reqs {
        if let Some(sk) = had {
            if sk.look == req.0 {
                continue;
            }
            // job change (`villagers::reskin_townsfolk`): drop the old outfit's instance + props
            commands.entity(sk.inst).try_despawn();
        }
        let Some(look) = cast.looks.get(req.0 as usize).and_then(Option::as_ref) else { continue };
        // Cancel the root's studio scale (kids / women / per-look build): the cast carries its own
        // real proportions, a child model is simply a shorter person.
        let s = WORLD_PER_M / tf.scale.x.max(1e-3);
        // Nobody is the same size: ±5% height, ±6% build (feet stay on the ground — the pivot).
        let h = person_hash(e);
        let tall = 0.95 + 0.1 * ((h >> 4) & 255) as f32 / 255.0;
        let broad = 0.94 + 0.12 * ((h >> 12) & 255) as f32 / 255.0;
        let child = commands
            .spawn((WorldAssetRoot(look.scene.clone()), Transform::from_scale(Vec3::new(s * broad, s * tall, s * broad)), SkinOf(e)))
            .observe(skin_ready)
            .id();
        commands.entity(e).add_child(child).try_insert(Skinned {
            look: req.0,
            inst: child,
            tools_done: false,
            player: None,
            clip: "",
            last: tf.translation,
            speed: 0.0,
            hand_r: None,
            hand_l: None,
            pelvis: None,
            props: Vec::new(),
            work_grip: false,
        });
    }
}

/// glTF instance spawned: hook up the graph, swap in the game materials, find the hand bones.
fn skin_ready(
    ready: On<WorldInstanceReady>,
    mut commands: Commands,
    cast: Res<NpcCast>,
    of: Query<&SkinOf>,
    children: Query<&Children>,
    players: Query<(), With<AnimationPlayer>>,
    mat_names: Query<&GltfMaterialName>,
    names: Query<&Name>,
    mut roots: Query<&mut Skinned>,
) {
    let inst = ready.entity;
    let Ok(SkinOf(root)) = of.get(inst) else { return };
    let Ok(mut sk) = roots.get_mut(*root) else { return };
    if sk.inst != inst {
        return; // a stale outfit finishing after a job change
    }
    let Some(look) = cast.looks[sk.look as usize].as_ref() else { return };
    for d in children.iter_descendants(inst) {
        if players.contains(d) {
            commands.entity(d).insert((AnimationGraphHandle(look.graph.clone()), AnimationTransitions::new()));
            sk.player = Some(d);
        }
        if let Ok(mn) = mat_names.get(d) {
            // This person's own dye and hair shade (a stable pick per root entity).
            let h = person_hash(*root);
            let (cloth, hair) = &cast.vars[sk.look as usize];
            let var = match mn.0.as_str() {
                "npc_cloth" if !uniform_look(sk.look) => cloth.get((h % cloth.len() as u32) as usize),
                "npc_hair" if !matches!(sk.look, ELDER_M | ELDER_F | MERCHANT | WOODCUTTER) => hair.get(((h >> 8) % hair.len().max(1) as u32) as usize),
                _ => None,
            };
            if let Some(m) = var.or_else(|| look.mats.get(mn.0.as_str())) {
                // Skinned bounds follow the rest pose only; a crouch / sit / swing would cull wrongly.
                commands.entity(d).insert((MeshMaterial3d(m.clone()), NoFrustumCulling));
            }
        }
        if let Ok(n) = names.get(d) {
            match n.as_str() {
                "hand_r" => sk.hand_r = Some(d),
                "hand_l" => sk.hand_l = Some(d),
                "pelvis" => sk.pelvis = Some(d),
                _ => {}
            }
        }
    }
    sk.clip = "";
    sk.tools_done = false;
}

/// The studio body under a skinned root stays (joint lookups, prop sockets) but is never drawn.
fn hide_studio_rigs(mut rigs: Query<(&ChildOf, &mut Visibility), With<BipedRig>>, skinned: Query<(), With<SkinRequest>>) {
    for (parent, mut vis) in &mut rigs {
        if skinned.contains(parent.parent()) && *vis != Visibility::Hidden {
            *vis = Visibility::Hidden;
        }
    }
}

/// A two-handed load (a log, a bundle of planks) carried by a skinned person: a child of the
/// gameplay root that [`carry_loads`] keeps glued between the skin's real hand bones every frame, so
/// the load rides the carry clip's arms (bob, sway and all) instead of floating at a fixed offset.
/// Its mesh is authored in METRES (the skin's own scale); `across` lays it across the body (a log
/// on both palms), otherwise it points the way the carrier faces.
#[derive(Component, Clone, Copy)]
pub struct CarriedLoad {
    pub across: bool,
}

/// Seat every [`CarriedLoad`] on the midpoint of its carrier's hands (+ a hair up and forward, so the
/// fingers wrap the sides rather than the load sinking into the palms), level with the carrier's
/// facing. Reads last frame's bone poses in the ROOT's own frame, so the carrier's walk never
/// skates the load.
fn carry_loads(
    roots: Query<(&Skinned, &GlobalTransform)>,
    mut loads: Query<(&ChildOf, &CarriedLoad, &mut Transform)>,
    bones: Query<&GlobalTransform>,
) {
    for (parent, load, mut tf) in &mut loads {
        let Ok((sk, root_gt)) = roots.get(parent.parent()) else { continue };
        let Some((hr, hl)) = hands(sk) else { continue };
        let (Ok(r), Ok(l)) = (bones.get(hr), bones.get(hl)) else { continue };
        let k = root_gt.scale().x.max(1e-3);
        let mid = root_gt.affine().inverse().transform_point3((r.translation() + l.translation()) * 0.5);
        let m = WORLD_PER_M / k; // metres → this root's local units
        tf.translation = mid + Vec3::new(0.0, 0.02, 0.03) * m;
        tf.rotation = if load.across { Quat::from_rotation_y(std::f32::consts::FRAC_PI_2) } else { Quat::IDENTITY };
        tf.scale = Vec3::splat(m);
    }
}

/// The skin's (right, left) hand bones once its glTF instance is ready.
pub fn hands(sk: &Skinned) -> Option<(Entity, Entity)> {
    Some((sk.hand_r?, sk.hand_l?))
}

/// Re-seat a prop authored in the studio rig's elbow frame (forearm down local -Y, fist at
/// y -0.25, forward +Z) into the matching hand bone: forearm line -> wrist->fingers, forward ->
/// through the fist pinky->index, fist -> fist.
pub fn elbow_to_hand(right: bool) -> Transform {
    let (across, _, centre) = fist(right);
    let y = -Vec3::Y;
    let rot = Quat::from_mat3(&Mat3::from_cols(y.cross(across), y, across));
    Transform { translation: centre - rot * Vec3::new(0.0, -0.25, 0.0), rotation: rot, scale: Vec3::ONE }
}

/// Fist frame in the cast's hand bones (metres; +Y wrist -> fingers, bones X-mirrored left/right),
/// measured off the MPFB `game_engine` finger joints: `across` runs through the closed fist
/// pinky -> index, `palm` points out of the palm, `centre` is the middle of the fist.
fn fist(right: bool) -> (Vec3, Vec3, Vec3) {
    let m = if right { 1.0 } else { -1.0 };
    let across = Vec3::new(0.571 * m, 0.0, -0.821);
    let palm = Vec3::new(-0.821 * m, 0.0, -0.571);
    (across, palm, Vec3::new(0.0, 0.085, 0.0) + palm * 0.03)
}

/// Where a studio tool (`peasant_model::kit_tools`: grip at the origin, haft along +Y, edge toward
/// +X, 1 unit ~ 1 m) sits in the fist. `work`: the haft runs through the fist pinky -> index
/// (chopping, hoeing, fighting); otherwise it is carried hanging, the fist round the haft just
/// under the head (`head` = grip -> head distance) and the haft down along the leg.
fn grip(right: bool, work: bool, head: f32) -> Transform {
    let (across, palm, centre) = fist(right);
    if work {
        // a real hammer grip: the haft runs diagonally from the heel of the hand out past the
        // index knuckle, so the head leans toward the fingers; the edge leads along the knuckles
        let haft = (across + Vec3::Y * 0.55).normalize();
        let edge = (Vec3::Y - haft * haft.y).normalize() * if right { 1.0 } else { -1.0 };
        let rot = Quat::from_mat3(&Mat3::from_cols(edge, haft, edge.cross(haft)));
        return Transform { translation: centre, rotation: rot, scale: Vec3::ONE };
    }
    // haft (+Y tool) toward the wrist (-Y hand, i.e. head up when the arm hangs); edge forward
    let haft = Vec3::NEG_Y;
    let edge = -palm.cross(haft).normalize() * if right { 1.0 } else { -1.0 };
    let rot = Quat::from_mat3(&Mat3::from_cols(edge, haft, edge.cross(haft)));
    let hold = (head - 0.12).max(0.0);
    Transform { translation: centre - haft * hold, rotation: rot, scale: Vec3::ONE }
}

fn top_y(m: &Mesh) -> f32 {
    match m.attribute(Mesh::ATTRIBUTE_POSITION) {
        Some(bevy::mesh::VertexAttributeValues::Float32x3(p)) => p.iter().map(|v| v[1]).fold(0.0, f32::max),
        _ => 0.0,
    }
}

/// Put the studio rig's held tool (`Sword` pivot) / off-hand prop (`Shield` pivot) into the skin's
/// hands: same meshes + creature material, so trade outfits keep their exact tools.
fn copy_tools(
    mut commands: Commands,
    mut roots: Query<(Entity, &mut Skinned)>,
    parts: Query<(&crate::biped::BipedPart, &Children)>,
    leaves: Query<(&Mesh3d, &MeshMaterial3d<crate::creature::CreatureMaterial>)>,
    rigs: Query<(), With<BipedRig>>,
    kids: Query<&Children>,
    meshes: Res<Assets<Mesh>>,
) {
    for (root, mut sk) in &mut roots {
        if sk.tools_done {
            continue;
        }
        let (Some(hr), Some(hl)) = (sk.hand_r, sk.hand_l) else { continue };
        // wait for the (queued) studio rig so a tool-less outfit is told apart from a late one
        if !kids.get(root).is_ok_and(|c| c.iter().any(|k| rigs.contains(k))) {
            continue;
        }
        for (part, children) in &parts {
            if part.root != root {
                continue;
            }
            let right = match part.joint {
                crate::player::Joint::Sword => true,
                crate::player::Joint::Shield => false,
                _ => continue,
            };
            for c in children.iter() {
                if let Ok((mesh, mat)) = leaves.get(c) {
                    let head = meshes.get(&mesh.0).map_or(0.0, top_y);
                    let prop = commands.spawn((mesh.clone(), mat.clone(), grip(right, false, head))).id();
                    commands.entity(if right { hr } else { hl }).add_child(prop);
                    sk.props.push((prop, right, head));
                }
            }
        }
        sk.tools_done = true;
        sk.clip = ""; // re-apply the grip for the current clip
    }
}

/// Pick + cross-fade each skin's clip from its drive and real ground speed.
fn drive_skins(
    time: Res<Time>,
    cam: Query<&GlobalTransform, With<Camera3d>>,
    cast: Res<NpcCast>,
    mut roots: Query<(&mut Skinned, &BipedDrive, &GlobalTransform, Has<crate::dying::Dying>, Option<&SkinClip>)>,
    mut players: Query<(&mut AnimationPlayer, &mut AnimationTransitions)>,
    mut props: Query<&mut Transform>,
    mut prop_vis: Query<&mut Visibility>,
) {
    let dt = time.delta_secs();
    if dt <= 0.0 {
        return; // paused / hit-stop: hold the pose
    }
    let cam_p = cam.iter().next().map(|g| g.translation());
    for (mut sk, d, gt, dying, hint) in &mut roots {
        let Some(pe) = sk.player else { continue };
        let Ok((mut player, mut tr)) = players.get_mut(pe) else { continue };
        let p = gt.translation();
        let v = Vec2::new(p.x - sk.last.x, p.z - sk.last.z).length() / dt;
        sk.last = p;
        sk.speed += (v.min(8.0) - sk.speed) * (dt * 8.0).min(1.0);
        let far = cam_p.is_some_and(|c| c.distance_squared(p) > ANIM_CULL2);
        let moving = sk.speed > 0.3 || d.moving_amt > 0.6;
        let (clip, once, rate): (&'static str, bool, f32) = if dying {
            ("Death01", true, 1.0)
        } else if let Some(h) = hint.filter(|h| !h.0.is_empty() && !d.attacking) {
            (h.0, h.0.ends_with("_Enter") || h.0.ends_with("_Exit"), 1.0)
        } else if d.sitting {
            ("Sitting_Idle_Loop", false, 1.0)
        } else if d.attacking {
            ("Sword_Regular_A", false, 1.3)
        } else if d.bow {
            ("Spell_Simple_Shoot", false, 1.0)
        } else if d.carrying && moving {
            (if d.pulling { "Push_Loop" } else { "Walk_Carry_Loop" }, false, (sk.speed / WALK_NATIVE).clamp(0.6, 1.5))
        } else if moving && (sk.speed > 2.3 || d.run_amt > 0.5) {
            ("Jog_Fwd_Loop", false, (sk.speed / JOG_NATIVE).clamp(0.7, 1.5))
        } else if moving {
            ("Walk_Loop", false, (sk.speed.max(0.6) / WALK_NATIVE).clamp(0.55, 1.6))
        } else if d.work == 2 {
            ("TreeChopping_Loop", false, 1.0)
        } else if d.work == 1 {
            ("Farm_Harvest", false, 1.0)
        } else {
            ("Idle_Loop", false, 1.0)
        };
        let Some(look) = cast.looks[sk.look as usize].as_ref() else { continue };
        // A scripted / life-act clip (`SkinClip`) puts its own prop in the hands (a hammer, a plank
        // bundle…): the trade tool carried by the outfit would hang there wrong (a hoe held upside
        // down through a kneel), so it is hidden for the act and comes back with the work clips.
        let acting = !dying && !d.attacking && hint.is_some_and(|h| !h.0.is_empty());
        let want_vis = if acting { Visibility::Hidden } else { Visibility::Inherited };
        for &(pe, _, _) in &sk.props {
            if let Ok(mut v) = prop_vis.get_mut(pe) {
                if *v != want_vis {
                    *v = want_vis;
                }
            }
        }
        if clip != sk.clip {
            let Some(&node) = look.nodes.get(clip) else { continue };
            let first = sk.clip.is_empty();
            let a = tr.play(&mut player, node, if first { Duration::ZERO } else { FADE });
            if !once {
                a.repeat();
            }
            if first {
                // de-sync neighbours on the same loop
                let h = (pe.index_u32().wrapping_mul(2_654_435_761) >> 16) as f32 / 65_536.0;
                a.seek_to(h * 2.0);
            }
            sk.clip = clip;
            // two-handed work / fight clips grip the haft through the fist, the rest carry it
            let work = matches!(clip, "TreeChopping_Loop" | "Farm_Harvest" | "Sword_Regular_A" | "Spell_Simple_Shoot");
            if work != sk.work_grip || first {
                sk.work_grip = work;
                for &(pe, right, head) in &sk.props {
                    if let Ok(mut t) = props.get_mut(pe) {
                        *t = grip(right, work, head);
                    }
                }
            }
        }
        for (_, a) in player.playing_animations_mut() {
            a.set_speed(if far { 0.0 } else { rate });
        }
    }
}
