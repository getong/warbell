//! Animation LOD for the skinned townsfolk and animals (`npc_skin`, `animal_skin`): a skin whose
//! animation graph is detached costs `animate_targets` one lookup instead of a full per-bone clip
//! evaluation (~4 ms of main-thread CPU for the village crowd). A skin parks when it is far from
//! the camera (each module's own `ANIM_CULL2` hysteresis) OR when the main camera hasn't drawn
//! it for [`UNSEEN_PARK`] seconds — off-screen people freeze mid-pose and resume the moment
//! they're back in view. Everyone within [`ALWAYS_ANIM`] keeps animating regardless, so a quick
//! turn of the camera never catches a frozen neighbour (the visible set is one frame old).
//! Also the skins' shadow LOD ([`shadow_flip`]; `FOREST_SKINSHADOW=all` keeps every skin casting).
//! `FOREST_ANIMLOD=0` disables the on-screen test (distance parking only); so does `FOREST_LIFECHECK`.

use bevy::camera::visibility::VisibleEntities;
use bevy::prelude::*;

const ALWAYS_ANIM: f32 = 14.0;
const UNSEEN_PARK: f32 = 0.4;

/// The main camera's visible `Mesh3d` entities (sorted, as `check_visibility` leaves them), or
/// `None` when the on-screen test is off / there's no camera.
pub fn on_screen_set(v: Option<&VisibleEntities>) -> Option<&[Entity]> {
    static ON: std::sync::OnceLock<bool> = std::sync::OnceLock::new();
    // (also off under `FOREST_LIFECHECK`, which reads every villager's live pelvis pose)
    if !*ON.get_or_init(|| {
        std::env::var("FOREST_ANIMLOD").map(|v| v != "0").unwrap_or(true) && std::env::var_os("FOREST_LIFECHECK").is_none()
    }) {
        return None;
    }
    v.map(|v| v.get(std::any::TypeId::of::<Mesh3d>()))
}

/// Should this skin be parked this frame? `far` = the module's own distance verdict; `body` = one of
/// the skin's mesh entities; `unseen` = its running off-screen timer (updated here).
pub fn park(far: bool, d2: f32, body: Option<Entity>, on_screen: Option<&[Entity]>, unseen: &mut f32, dt: f32) -> bool {
    let seen = match (on_screen, body) {
        (Some(vis), Some(b)) => d2 < ALWAYS_ANIM * ALWAYS_ANIM || vis.binary_search(&b).is_ok(),
        _ => true,
    };
    *unseen = if seen { 0.0 } else { *unseen + dt };
    far || *unseen > UNSEEN_PARK
}

/// Shadow LOD: past [`SHADOW_FAR`] a skinned person / animal stops casting (its shadow is a few
/// pixels, but each caster is a full skinned draw in every cascade); back inside [`SHADOW_NEAR`]
/// it casts again. Returns the new `casting` state when it flips.
pub const SHADOW_FAR: f32 = 38.0;
pub const SHADOW_NEAR: f32 = 33.0;

pub fn shadow_flip(casting: bool, d2: f32) -> Option<bool> {
    static ON: std::sync::OnceLock<bool> = std::sync::OnceLock::new();
    if !*ON.get_or_init(|| std::env::var("FOREST_SKINSHADOW").map(|v| v != "all").unwrap_or(true)) {
        return None;
    }
    if casting && d2 > SHADOW_FAR * SHADOW_FAR {
        Some(false)
    } else if !casting && d2 < SHADOW_NEAR * SHADOW_NEAR {
        Some(true)
    } else {
        None
    }
}

/// Apply a [`shadow_flip`] to a skin's mesh entities.
pub fn set_casting(commands: &mut Commands, meshes: &[Entity], cast: bool) {
    for &m in meshes {
        if cast {
            commands.entity(m).try_remove::<bevy::light::NotShadowCaster>();
        } else {
            commands.entity(m).try_insert(bevy::light::NotShadowCaster);
        }
    }
}

/// Skinned meshes swap to a meshopt-simplified twin past `SKIN_LOD_FAR` (back inside
/// `SKIN_LOD_NEAR`): a townsperson or deer at 30u+ is ~60px tall, and the full mesh is ~13k indices
/// of SKINNED vertex work in the prepass, the main pass and (near) the shadow cascades.
const SKIN_LOD_FAR2: f32 = 30.0 * 30.0;
const SKIN_LOD_NEAR2: f32 = 26.0 * 26.0;
const SKIN_LOD_RATIO: f32 = 0.3;

/// Full mesh -> far twin (`None`: simplifying didn't pay), and far twin -> full mesh.
#[derive(bevy::prelude::Resource, Default)]
pub struct SkinLodCache {
    far: std::collections::HashMap<AssetId<Mesh>, Option<Handle<Mesh>>>,
    full: std::collections::HashMap<AssetId<Mesh>, Handle<Mesh>>,
}

fn skin_lod_enabled() -> bool {
    static ON: std::sync::OnceLock<bool> = std::sync::OnceLock::new();
    *ON.get_or_init(|| std::env::var("FOREST_SKINLOD").map(|v| v != "0").unwrap_or(true) && std::env::var_os("FOREST_LIFECHECK").is_none())
}

/// Hysteresis for the mesh LOD: `Some(new far state)` when it should flip.
pub fn lod_flip(far: bool, d2: f32) -> Option<bool> {
    if !skin_lod_enabled() {
        return None;
    }
    let want = if far { d2 > SKIN_LOD_NEAR2 } else { d2 > SKIN_LOD_FAR2 };
    (want != far).then_some(want)
}

/// Point every mesh entity of one skin at its far twin (`far`) or back at the full mesh. Twins are
/// built once per source mesh (shared by every instance of that look, so they still batch).
pub fn swap_meshes(ents: &[Entity], far: bool, q: &mut Query<&mut Mesh3d>, meshes: &mut Assets<Mesh>, cache: &mut SkinLodCache) {
    for &e in ents {
        let Ok(mut m) = q.get_mut(e) else { continue };
        let id = m.0.id();
        let next = if far {
            if cache.full.contains_key(&id) {
                continue; // already the twin
            }
            let twin = cache.far.entry(id).or_insert_with(|| {
                let src = meshes.get(id)?;
                let lod = crate::autolod::simplify_keep_vertices(src, SKIN_LOD_RATIO, 0.03)?;
                Some(meshes.add(lod))
            });
            let Some(t) = twin.clone() else { continue };
            cache.full.insert(t.id(), m.0.clone());
            t
        } else {
            let Some(full) = cache.full.get(&id) else { continue };
            full.clone()
        };
        m.0 = next;
    }
}
