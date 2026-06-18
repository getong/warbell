//! Render-recovery policy (Bevy 0.19's configurable render error handling).
//!
//! By default Bevy **quits the app on ANY `RenderError`**. That's the right call for
//! validation / out-of-memory / internal errors — continuing would re-hit the same fault every
//! frame and can cause hazardous strobing (bevy_render says as much). But a **device-lost** event
//! is the normal, *recoverable* case on real player hardware: a GPU driver update, a laptop
//! sleep/wake, or a TDR timeout reset all surface as `ErrorType::DeviceLost`. For a shipping game,
//! rebuilding the renderer beats dumping the player to the desktop with a lost run.
//!
//! This installs a handler that **recovers on `DeviceLost`** and keeps Bevy's safe default
//! (log + quit) for every other error class.
//!
//! NOTE: this path can't be exercised by the headless software-renderer smoke test (you can't fake
//! a device loss under llvmpipe) — registration is verified there, but the *recovery* itself wants
//! a real-GPU check (driver swap / sleep-wake) before being fully relied upon.

use bevy::prelude::*;
use bevy::render::error_handler::{ErrorType, RenderErrorHandler, RenderErrorPolicy};
use bevy::render::settings::RenderCreation;

pub struct RenderRecoveryPlugin;

impl Plugin for RenderRecoveryPlugin {
    fn build(&self, app: &mut App) {
        // `RenderPlugin` (inside `DefaultPlugins`) `init_resource`s a default `RenderErrorHandler`
        // that quits on every error. This `insert_resource` overrides it — it must run after
        // `DefaultPlugins`, which it does (all game plugins are added after it in `main`).
        app.insert_resource(RenderErrorHandler(|error, main_world, _render_world| {
            match error.ty {
                // GPU went away (driver update / sleep-wake / TDR reset). Recoverable: rebuild the
                // renderer with default settings (we don't customise `WgpuSettings`) and keep the
                // run alive instead of hard-quitting.
                ErrorType::DeviceLost => {
                    warn!(
                        "GPU device lost ({}); attempting renderer recovery instead of quitting",
                        error.description
                    );
                    RenderErrorPolicy::Recover(RenderCreation::default())
                }
                // Validation / OutOfMemory / Internal: keep Bevy's default — log and quit. These
                // signal a real fault; continuing would likely re-hit it and strobe the screen.
                _ => {
                    error!("Fatal RenderError ({:?}): {}", error.ty, error.description);
                    main_world.write_message(AppExit::error());
                    RenderErrorPolicy::StopRendering
                }
            }
        }));
    }
}
