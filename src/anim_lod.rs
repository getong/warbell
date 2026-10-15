//! Animation LOD for the skinned townsfolk and animals (`npc_skin`, `animal_skin`): a skin whose
//! animation graph is detached costs `animate_targets` one lookup instead of a full per-bone clip
//! evaluation (~4 ms of main-thread CPU for the village crowd). A skin parks when it is far from
//! the camera (each module's own `ANIM_CULL2` hysteresis) OR when the main camera hasn't drawn
//! it for [`UNSEEN_PARK`] seconds — off-screen people freeze mid-pose and resume the moment
//! they're back in view. Everyone within [`ALWAYS_ANIM`] keeps animating regardless, so a quick
//! turn of the camera never catches a frozen neighbour (the visible set is one frame old).
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
