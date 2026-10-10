//! **Shared biped rig + animator** — lets non-hero bipeds (orcs, peasants/villagers) drive the
//! exact same studio `Pose` clips the hero uses, instead of their own bespoke limb code. The pose
//! math lives in [`crate::player::anim`] (the hero's proven, verified clips); this module just
//! exposes it to other mobs via a small ECS contract:
//!
//! - [`BipedPart`] tags each joint entity of a biped (with a back-reference to its `root`).
//! - [`BipedDrive`] is the per-frame animation input a mob's AI fills (gait phase, attack, …).
//! - [`animate_biped`] reads every drive, builds one [`crate::player::anim::Pose`] per root, and
//!   writes it onto that root's tagged joints.
//!
//! The hero keeps its own richer driver (`player::anim::hero_anim`: gestures,
//! landing squash) and is **not** touched by this module — it only borrows the clip functions.
//! Spawning a biped's skeleton (the joint hierarchy from a per-joint mesh set) is added alongside
//! the first mob that uses it.

use std::collections::HashMap;

use bevy::prelude::*;

use crate::player::anim::{action_over_loco, attack_phase, attack_pose, biped_tool_pose, bow_pose, carry_pose, loco_pose, sit_pose, work_pose, Pose};
pub(crate) use crate::player::anim::HeldTool;
use crate::player::{Joint, ATTACK_DURATION};

/// One animated joint of a biped mob. `root` points back at the entity carrying [`BipedDrive`] so a
/// single [`animate_biped`] pass can pose many mobs at once.
#[derive(Component)]
pub struct BipedPart {
    pub joint: Joint,
    pub root: Entity,
}

/// Marks the `rig` wrapper entity [`spawn_biped`] parents the whole joint tree under. A caller that
/// rebuilds a mob's body in place (e.g. a villager changing job in `villagers::reskin_townsfolk`)
/// despawns the child carrying this to drop the *whole* skeleton in one go, then re-spawns it.
#[derive(Component)]
pub struct BipedRig;

/// Per-frame animation inputs a mob's AI writes each tick; [`animate_biped`] turns it into a pose.
/// (Superset grows as more clips are wired — jump/block/sit/woodchop/mine come with later mobs.)
#[derive(Component, Default)]
pub struct BipedDrive {
    /// 0..1 blend toward "moving" (idle ↔ gait).
    pub moving_amt: f32,
    /// 0..1 blend toward "running" (walk ↔ run).
    pub run_amt: f32,
    /// Gait phase, advanced by the AI at its movement speed.
    pub walk_phase: f32,
    /// Mid-swing this frame.
    pub attacking: bool,
    /// Seconds into the current swing (0..`ATTACK_DURATION`).
    pub attack_t: f32,
    /// Which studio attack clip (0 overhead / 1 slash / 2 thrust).
    pub attack_variant: u8,
    /// Seated on a stump (overrides locomotion with the seated pose).
    pub sitting: bool,
    /// Posted-worker tool stroke when standing still: 0 none · 1 hoe (farmer) · 2 chop/pick
    /// (woodcutter/miner). Layered over the idle stance by [`work_pose`].
    pub work: u8,
    /// True while hauling a load home (a woodcutter's log / a miner's cart) — both arms grip forward.
    pub carrying: bool,
    /// The load is a handcart pulled behind (a miner's ore cart): the fists hold its shafts at the
    /// sides instead of cradling a log against the chest. Only read while `carrying`.
    pub pulling: bool,
    /// Per-instance clock offset (radians/seconds) so neighbouring mobs don't fidget/work in
    /// lockstep. Fed into the work stroke; locomotion already carries its own phase via `walk_phase`.
    pub phase: f32,
    /// Mid bow-shot this frame (an archer's draw-and-loose plays instead of the melee swing).
    pub bow: bool,
    /// 0..1 progress through the bow-shot clip (the archer brain advances it over its shot time).
    pub bow_t: f32,
    /// What the right hand holds (set once from the outfit at spawn). Anything but `None` hands the
    /// clip selection to `player::anim::toolwork`, which grips the tool for real in every state
    /// (two-handed work strokes, the shoulder carry, slung while hauling, the guard's buckler, the
    /// archer's bow at ease). Orks and empty-handed folk leave it `None`.
    pub tool: HeldTool,
    /// This rig's `(hip_dx, shoulder_dx)` from [`spawn_biped`] — the tool clips place fists and feet
    /// by IK, so they need the real joint layout. Zero = the realistic kit body's.
    pub limb_dx: Vec2,
}

/// A whole pose written by a richer per-mob animator, used INSTEAD of the [`BipedDrive`] clip
/// selection while present — e.g. a caged captive's idle life (`captives::captive_life`: huddles,
/// rocking, the stand-up, gripping the bars), which needs more than the drive's flags can say.
/// Removing it hands the rig straight back to the drive (the captive walk-out does exactly that
/// once its cross-fade into the gait completes). Culling is unchanged.
#[derive(Component, Clone, Copy)]
pub(crate) struct PoseOverride(pub(crate) Pose);

/// Select + compose the studio clips for one biped from its drive (reuses the hero's clip math).
/// An attack while moving layers over the gait (a running attack), exactly like the hero.
pub(crate) fn biped_pose(d: &BipedDrive, now: f32) -> Pose {
    // A townsperson with a tool / weapon in hand: the tool clips own the whole pose.
    if let Some(p) = biped_tool_pose(d, now) {
        return p;
    }
    if d.sitting {
        return sit_pose();
    }
    let moving = d.moving_amt.clamp(0.0, 1.0);
    // The idle runs on the mob's own clock offset, so a crowd doesn't shift its weight and look
    // round in unison.
    let loco = loco_pose(now + 2.5 * d.phase, d.walk_phase, moving, d.run_amt.clamp(0.0, 1.0));
    if d.bow {
        // An archer's draw-and-loose. Shot mid-step (a repositioning archer) it layers over the
        // gait like a running attack; planted, the full braced stance plays.
        let b = bow_pose(now + d.phase, d.bow_t);
        if moving > 0.05 {
            action_over_loco(&b, &loco, moving)
        } else {
            b
        }
    } else if d.attacking {
        let (phase, p) = attack_phase((d.attack_t / ATTACK_DURATION).clamp(0.0, 1.0));
        let atk = attack_pose(d.attack_variant, &phase, p);
        if moving > 0.05 {
            action_over_loco(&atk, &loco, moving)
        } else {
            atk
        }
    } else if d.carrying {
        // Hauling a load home: both arms grip forward (carry pose) while the legs keep walking.
        action_over_loco(&carry_pose(), &loco, moving)
    } else if d.work != 0 && moving < 0.05 {
        // A posted worker plies their trade in place; walking back to/from post falls through to loco.
        work_pose(now + d.phase, d.work == 1)
    } else {
        loco
    }
}

/// Squared CAMERA distance past which a rig is no longer posed — the same 70u radius the legacy
/// box rigs cull at (`orks::LIMB_CULL2`, `wildlife::LIMB_CULL2`); at that range fog + DoF have long
/// since swallowed the individual joints. Posing is ~20 joint writes per rig per frame, so with a
/// siege-sized crowd this is one of the fattest ungated Update systems in the game.
const LIMB_CULL2: f32 = 70.0 * 70.0;

/// Pose every biped: one [`Pose`] per root (from its [`BipedDrive`]), written onto its [`BipedPart`]s.
/// Ungated (like the hero animator) so a frozen/paused world still draws its mobs posed.
///
/// Distance-culled from the camera ([`LIMB_CULL2`]), matching `ork_limbs` / `animal_limbs`. A culled
/// rig simply keeps its last pose (same precedent) — it is not reset, so nothing snaps; when the
/// camera closes back in, the next frame poses it from the live drive. The **hero is never culled**:
/// he drives his own richer animator (`player::anim::hero_anim`) and never carries a `BipedDrive`,
/// but the marker check is kept explicit so the hero rig can never be frozen out by this system if
/// he is ever moved onto the shared rig.
pub fn animate_biped(
    time: Res<Time>,
    cam: Query<&GlobalTransform, With<Camera3d>>,
    drives: Query<(
        Entity,
        &BipedDrive,
        Option<&GlobalTransform>,
        Has<crate::player::Hero>,
        Option<&PoseOverride>,
        Option<&crate::player::anim::ork::OrkMotion>,
    )>,
    mut parts: Query<(&BipedPart, &mut Transform)>,
    // Reused across frames so a full siege+town's worth of bipeds doesn't heap-alloc a fresh map
    // every frame (clear keeps the capacity).
    mut poses: Local<HashMap<Entity, Pose>>,
) {
    let now = time.elapsed_secs();
    let cam_p = cam.iter().next().map(|g| g.translation());
    poses.clear();
    poses.extend(drives.iter().filter_map(|(e, d, gt, is_hero, over, ork)| {
        if !is_hero {
            // No transform yet (spawned this frame) → pose it; the cull needs a real position.
            if let (Some(cp), Some(gt)) = (cam_p, gt) {
                if gt.translation().distance_squared(cp) > LIMB_CULL2 {
                    return None;
                }
            }
        }
        // An ork carries its own animator (`OrkMotion`: its stance, waddle and wound-up blows);
        // everyone else plays the shared studio clips from the drive.
        let pose = match (over, ork) {
            (Some(o), _) => o.0,
            (None, Some(m)) => crate::player::anim::ork::ork_pose(d, m, now),
            (None, None) => biped_pose(d, now),
        };
        Some((e, pose))
    }));
    for (part, mut tf) in &mut parts {
        if let Some(pose) = poses.get(&part.root) {
            let jp = pose.get(part.joint);
            if let Some(t) = jp.t {
                tf.translation = t;
            }
            tf.rotation = jp.r;
        }
    }
}

/// A per-joint mesh set for a biped — the 14 body joints (hips/torso/neck/head, both shoulders/
/// elbows, both hips/knees/feet) plus an optional held weapon (on the `Sword` pivot), shield, and
/// shield emblem. Each becomes one flat-shaded vertex-coloured mesh, like the hero's.
///
/// Or, with [`BipedMeshes::skin`] set, the whole body is ONE mesh skinned to the same joints (the
/// realistic townsfolk, `peasant_model::kit_peasant_meshes`): limbs then bend at the joints instead
/// of reading as separate pegs, and the per-joint meshes are ignored (leave them empty).
#[allow(dead_code)]
pub struct BipedMeshes {
    pub hips: Mesh,
    pub torso: Mesh,
    pub neck: Mesh,
    pub head: Mesh,
    pub shoulder_l: Mesh,
    pub shoulder_r: Mesh,
    pub elbow_l: Mesh,
    pub elbow_r: Mesh,
    pub hip_l: Mesh,
    pub hip_r: Mesh,
    pub knee_l: Mesh,
    pub knee_r: Mesh,
    pub foot_l: Mesh,
    pub foot_r: Mesh,
    pub weapon: Option<Mesh>,
    pub shield: Option<Mesh>,
    pub lion: Option<Mesh>,
    /// The whole body as one skinned mesh, authored in the `rig` frame at the rest pose, with
    /// `ATTRIBUTE_JOINT_INDEX` / `ATTRIBUTE_JOINT_WEIGHT` indexing [`SKIN_JOINTS`].
    pub skin: Option<Mesh>,
}

/// The joint order a [`BipedMeshes::skin`] mesh's joint indices refer to (`people.py` `JOINTS`).
#[allow(dead_code)]
pub const SKIN_JOINTS: [&str; 14] =
    ["hips", "torso", "neck", "head", "sh_l", "el_l", "sh_r", "el_r", "hip_l", "knee_l", "foot_l", "hip_r", "knee_r", "foot_r"];

/// Rest-pose transforms (in the `rig` frame) of the [`SKIN_JOINTS`], exactly as [`spawn_biped`]
/// lays the joints out — the bind pose of a skinned body.
pub fn rest_joint_matrices(head_scale: f32, foot_scale: f32, hip_dx: f32, shoulder_dx: f32) -> [Mat4; 14] {
    let t = |x: f32, y: f32, z: f32| Mat4::from_translation(Vec3::new(x, y, z));
    let ts = |x: f32, y: f32, z: f32, s: f32| Mat4::from_scale_rotation_translation(Vec3::splat(s), Quat::IDENTITY, Vec3::new(x, y, z));
    let hips = t(0.0, 1.05, 0.0);
    let torso = hips * t(0.0, 0.15, 0.0);
    let neck = torso * t(0.0, 0.35, 0.0);
    let head = neck * ts(0.0, 0.08, 0.0, head_scale);
    let sh_l = torso * t(-shoulder_dx, 0.27, 0.01);
    let el_l = sh_l * t(0.0, -0.30, 0.0);
    let sh_r = torso * t(shoulder_dx, 0.27, 0.01);
    let el_r = sh_r * t(0.0, -0.30, 0.0);
    let hip_l = hips * t(-hip_dx, -0.05, 0.0);
    let knee_l = hip_l * t(0.0, -0.40, 0.0);
    let foot_l = knee_l * ts(0.0, -0.45, 0.0, foot_scale);
    let hip_r = hips * t(hip_dx, -0.05, 0.0);
    let knee_r = hip_r * t(0.0, -0.40, 0.0);
    let foot_r = knee_r * ts(0.0, -0.45, 0.0, foot_scale);
    [hips, torso, neck, head, sh_l, el_l, sh_r, el_r, hip_l, knee_l, foot_l, hip_r, knee_r, foot_r]
}

/// Pre-uploaded handles for a [`BipedMeshes`] set — so a cached spawner (e.g. the ork `Armory`)
/// uploads each mesh once and clones cheap handles per mob, instead of re-uploading 14 meshes per
/// spawn (which would bloat memory badly during a siege).
#[derive(Clone)]
pub struct BipedHandles {
    hips: Option<Handle<Mesh>>,
    torso: Option<Handle<Mesh>>,
    neck: Option<Handle<Mesh>>,
    head: Option<Handle<Mesh>>,
    shoulder_l: Option<Handle<Mesh>>,
    shoulder_r: Option<Handle<Mesh>>,
    elbow_l: Option<Handle<Mesh>>,
    elbow_r: Option<Handle<Mesh>>,
    hip_l: Option<Handle<Mesh>>,
    hip_r: Option<Handle<Mesh>>,
    knee_l: Option<Handle<Mesh>>,
    knee_r: Option<Handle<Mesh>>,
    foot_l: Option<Handle<Mesh>>,
    foot_r: Option<Handle<Mesh>>,
    weapon: Option<Handle<Mesh>>,
    shield: Option<Handle<Mesh>>,
    lion: Option<Handle<Mesh>>,
    /// The skinned body + its rest-pose bounds (rig frame), padded for the poses' reach.
    skin: Option<(Handle<Mesh>, bevy::camera::primitives::Aabb)>,
}

impl BipedHandles {
    /// Swap the off-hand (shield-slot) mesh — e.g. an ork torch-bearer carries a lit war-torch in
    /// the shield hand instead of a buckler. `None` strips the off-hand entirely. The shield
    /// emblem is dropped either way (it only makes sense riding an actual shield).
    pub fn with_shield(mut self, shield: Option<Handle<Mesh>>) -> Self {
        self.shield = shield;
        self.lion = None;
        self
    }
}

/// Vertex positions of a mesh (empty if it has none).
fn skin_positions(m: &Mesh) -> Vec<Vec3> {
    match m.attribute(Mesh::ATTRIBUTE_POSITION) {
        Some(bevy::mesh::VertexAttributeValues::Float32x3(p)) => p.iter().map(|v| Vec3::from(*v)).collect(),
        _ => Vec::new(),
    }
}

impl BipedMeshes {
    /// Upload every mesh once, returning shareable (cloneable) handles for cached spawning.
    pub fn upload(self, meshes: &mut Assets<Mesh>) -> BipedHandles {
        // A skinned body replaces the 14 per-joint leaves (those stay empty and are not uploaded).
        let rigid = self.skin.is_none();
        let mut add = |m: Mesh| rigid.then(|| meshes.add(m));
        let (hips, torso, neck, head) = (add(self.hips), add(self.torso), add(self.neck), add(self.head));
        let (shoulder_l, shoulder_r, elbow_l, elbow_r) = (add(self.shoulder_l), add(self.shoulder_r), add(self.elbow_l), add(self.elbow_r));
        let (hip_l, hip_r, knee_l, knee_r) = (add(self.hip_l), add(self.hip_r), add(self.knee_l), add(self.knee_r));
        let (foot_l, foot_r) = (add(self.foot_l), add(self.foot_r));
        let skin = self.skin.map(|m| {
            // Rest bounds padded for the clips' reach (an overhead chop, a seated lap, a stride).
            let aabb = match bevy::camera::primitives::Aabb::enclosing(skin_positions(&m)) {
                Some(b) => bevy::camera::primitives::Aabb::from_min_max(
                    Vec3::from(b.min()) - Vec3::new(0.35, 0.3, 0.5),
                    Vec3::from(b.max()) + Vec3::new(0.35, 0.45, 0.5),
                ),
                None => bevy::camera::primitives::Aabb::from_min_max(Vec3::new(-1.0, 0.0, -1.0), Vec3::new(1.0, 2.3, 1.0)),
            };
            (meshes.add(m), aabb)
        });
        BipedHandles {
            hips,
            torso,
            neck,
            head,
            shoulder_l,
            shoulder_r,
            elbow_l,
            elbow_r,
            hip_l,
            hip_r,
            knee_l,
            knee_r,
            foot_l,
            foot_r,
            weapon: self.weapon.map(|m| meshes.add(m)),
            shield: self.shield.map(|m| meshes.add(m)),
            lion: self.lion.map(|m| meshes.add(m)),
            skin,
        }
    }
}

/// Spawn the studio knight skeleton (the same joint hierarchy + frames the hero uses) for a mob,
/// from pre-uploaded `h` handles. Tags each joint [`BipedPart`] so [`animate_biped`] poses it from
/// the root's [`BipedDrive`]. **Returns `(Head, Option<Shield>)` joint entities** so callers can
/// attach extras (an ork's glowing eyes on the head; a torch-bearer's flame + light on the
/// off-hand). Per-mob tuning: `head_scale`/`foot_scale` (studio group scales), `hip_dx`/
/// `shoulder_dx` (limb spacing), `rig_offset_y` (drop feet onto the ground), and `shield_xf`
/// (Some → mount the shield + emblem on the left hand). The held `weapon` rides the `Sword`
/// pivot. Built under a `rig` child of `root` so the caller's root scale sizes the whole mob.
#[allow(clippy::too_many_arguments)]
pub fn spawn_biped(
    commands: &mut Commands,
    root: Entity,
    mat: &Handle<crate::creature::CreatureMaterial>,
    h: BipedHandles,
    head_scale: f32,
    foot_scale: f32,
    hip_dx: f32,
    shoulder_dx: f32,
    rig_offset_y: f32,
    shield_xf: Option<Transform>,
) -> (Entity, Option<Entity>) {
    let p = |t: Vec3| Transform::from_translation(t);
    let ps = |t: Vec3, s: f32| Transform { translation: t, scale: Vec3::splat(s), ..default() };
    // Spawn a tagged joint (transform-only) under `parent`, with an optional mesh-leaf child.
    let joint = |commands: &mut Commands, parent: Entity, j: Option<Joint>, xf: Transform, leaf: Option<Handle<Mesh>>| -> Entity {
        let mut ec = commands.spawn((xf, Visibility::Visible));
        if let Some(j) = j {
            ec.insert(BipedPart { joint: j, root });
        }
        let e = ec.id();
        commands.entity(parent).add_child(e);
        if let Some(mesh) = leaf {
            let leaf_e = commands.spawn((Mesh3d(mesh), MeshMaterial3d(mat.clone()), Transform::default())).id();
            commands.entity(e).add_child(leaf_e);
        }
        e
    };
    use Joint::*;

    let rig = commands.spawn((Transform::from_xyz(0.0, rig_offset_y, 0.0), Visibility::Visible, BipedRig)).id();
    commands.entity(root).add_child(rig);

    // Spine.
    let hips = joint(commands, rig, Some(Hips), p(Vec3::new(0.0, 1.05, 0.0)), h.hips);
    let torso = joint(commands, hips, Some(Torso), p(Vec3::new(0.0, 0.15, 0.0)), h.torso);
    let neck = joint(commands, torso, None, p(Vec3::new(0.0, 0.35, 0.0)), h.neck);
    let head_e = joint(commands, neck, Some(Head), ps(Vec3::new(0.0, 0.08, 0.0), head_scale), h.head);

    // Left arm (+ optional shield/emblem on the hand).
    let sh_l = joint(commands, torso, Some(ShoulderL), p(Vec3::new(-shoulder_dx, 0.27, 0.01)), h.shoulder_l);
    let el_l = joint(commands, sh_l, Some(ElbowL), p(Vec3::new(0.0, -0.30, 0.0)), h.elbow_l);
    let hand_l = joint(commands, el_l, None, p(Vec3::new(0.0, -0.25, 0.0)), None);
    let mut shield_out = None;
    if let (Some(sx), Some(shield)) = (shield_xf, h.shield) {
        let shield_e = joint(commands, hand_l, Some(Shield), sx, Some(shield));
        if let Some(lion) = h.lion {
            joint(commands, shield_e, None, p(Vec3::new(0.0, -0.03, 0.033)), Some(lion));
        }
        shield_out = Some(shield_e);
    }

    // Right arm (+ optional weapon on the Sword pivot).
    let sh_r = joint(commands, torso, Some(ShoulderR), p(Vec3::new(shoulder_dx, 0.27, 0.01)), h.shoulder_r);
    let el_r = joint(commands, sh_r, Some(ElbowR), p(Vec3::new(0.0, -0.30, 0.0)), h.elbow_r);
    let hand_r = joint(commands, el_r, None, p(Vec3::new(0.0, -0.25, 0.0)), None);
    if let Some(weapon) = h.weapon {
        joint(commands, hand_r, Some(Sword), Transform::default(), Some(weapon));
    }

    // Legs.
    let hip_l = joint(commands, hips, Some(HipL), p(Vec3::new(-hip_dx, -0.05, 0.0)), h.hip_l);
    let knee_l = joint(commands, hip_l, Some(KneeL), p(Vec3::new(0.0, -0.40, 0.0)), h.knee_l);
    let foot_l = joint(commands, knee_l, Some(FootL), ps(Vec3::new(0.0, -0.45, 0.0), foot_scale), h.foot_l);
    let hip_r = joint(commands, hips, Some(HipR), p(Vec3::new(hip_dx, -0.05, 0.0)), h.hip_r);
    let knee_r = joint(commands, hip_r, Some(KneeR), p(Vec3::new(0.0, -0.40, 0.0)), h.knee_r);
    let foot_r = joint(commands, knee_r, Some(FootR), ps(Vec3::new(0.0, -0.45, 0.0), foot_scale), h.foot_r);

    // A skinned body: one mesh in the rig frame, bound to the joints above (`SKIN_JOINTS` order)
    // with their rest transforms as the bind pose. Bevy's skinning reads the joints' live
    // GlobalTransforms, so every clip the animator writes bends the body.
    if let Some((mesh, aabb)) = h.skin {
        let joints = vec![hips, torso, neck, head_e, sh_l, el_l, sh_r, el_r, hip_l, knee_l, foot_l, hip_r, knee_r, foot_r];
        let inverse: Vec<Mat4> = rest_joint_matrices(head_scale, foot_scale, hip_dx, shoulder_dx).iter().map(|m| m.inverse()).collect();
        let body = commands.spawn((Transform::default(), Visibility::Visible, aabb, bevy::camera::visibility::NoAutoAabb)).id();
        commands.entity(rig).add_child(body);
        let mat = mat.clone();
        // The bind-pose asset needs the asset store: add it (and the mesh, so the body never draws
        // unskinned for a frame) when the commands flush.
        commands.queue(move |world: &mut World| {
            let Some(mut poses) = world.get_resource_mut::<Assets<bevy::mesh::skinning::SkinnedMeshInverseBindposes>>() else {
                return;
            };
            let inverse_bindposes = poses.add(bevy::mesh::skinning::SkinnedMeshInverseBindposes::from(inverse));
            if let Ok(mut e) = world.get_entity_mut(body) {
                e.insert((Mesh3d(mesh), MeshMaterial3d(mat), bevy::mesh::skinning::SkinnedMesh { inverse_bindposes, joints }));
            }
        });
    }

    (head_e, shield_out)
}

pub struct BipedPlugin;

impl Plugin for BipedPlugin {
    fn build(&self, app: &mut App) {
        app.add_systems(Update, animate_biped);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// A skinned body's bind pose must be exactly where `spawn_biped` puts the joints.
    #[test]
    fn rest_joint_matrices_match_the_spawned_layout() {
        let m = rest_joint_matrices(1.2, 1.0, 0.1, 0.2);
        let at = |i: usize| m[i].transform_point3(Vec3::ZERO);
        assert_eq!(SKIN_JOINTS[3], "head");
        assert!((at(3) - Vec3::new(0.0, 1.63, 0.0)).length() < 1e-5);
        assert!((m[3].transform_vector3(Vec3::X).length() - 1.2).abs() < 1e-5);
        assert_eq!(SKIN_JOINTS[7], "el_r");
        assert!((at(7) - Vec3::new(0.2, 1.17, 0.01)).length() < 1e-5);
        assert_eq!(SKIN_JOINTS[10], "foot_l");
        assert!((at(10) - Vec3::new(-0.1, 0.15, 0.0)).length() < 1e-5);
    }
}
