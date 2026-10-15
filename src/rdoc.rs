//! GPU frame captures via the RenderDoc in-app API (`cargo run --features renderdoc`).
//!
//! `FOREST_RDOC=<secs>` captures ONE frame `<secs>` of real time after the world is ready (so the
//! scene, streaming and pipelines have settled), into `FOREST_RDOC_PATH` (default
//! `target/rdoc/cap`; RenderDoc appends `_frameN.rdc`). The capture is then analysed offline with
//! `tools/rdoc/` (per-draw GPU timings, pipeline / mesh / material breakdown).
//!
//! RenderDoc must already be loaded into the process for the Vulkan backend: the portable build's
//! layer is enabled through the environment rather than a system registration —
//! `VK_LAYER_PATH=<renderdoc dir>`, `VK_INSTANCE_LAYERS=VK_LAYER_RENDERDOC_Capture`,
//! `ENABLE_VULKAN_RENDERDOC_CAPTURE=1`, and `PATH` including the RenderDoc dir so the API lookup
//! finds the same `renderdoc.dll` the layer loaded. `tools/rdoc/capture.sh` sets all of that.

use bevy::prelude::*;
use renderdoc::{RenderDoc, V141};
use std::sync::Mutex;

pub struct RdocPlugin;

#[derive(Resource)]
struct Rdoc {
    api: Mutex<RenderDoc<V141>>,
    at: f32,
    ready_at: Option<f32>,
    done: bool,
}

impl Plugin for RdocPlugin {
    fn build(&self, app: &mut App) {
        let Some(at) = std::env::var("FOREST_RDOC").ok().and_then(|v| v.parse::<f32>().ok()) else { return };
        match RenderDoc::<V141>::new() {
            Ok(mut api) => {
                let path = std::env::var("FOREST_RDOC_PATH").unwrap_or_else(|_| "target/rdoc/cap".into());
                api.set_capture_file_path_template(path.as_str());
                info!("RDOC: RenderDoc API loaded; capturing one frame {at}s after WorldReady -> {path}");
                app.insert_resource(Rdoc { api: Mutex::new(api), at, ready_at: None, done: false })
                    .add_systems(Last, rdoc_tick);
            }
            Err(e) => error!("RDOC: RenderDoc API not available ({e}) — is the layer enabled? see src/rdoc.rs"),
        }
    }
}

fn rdoc_tick(time: Res<Time<Real>>, ready: Res<crate::biome::WorldReady>, mut rd: ResMut<Rdoc>) {
    if rd.done || !ready.0 {
        return;
    }
    let now = time.elapsed_secs();
    let start = *rd.ready_at.get_or_insert(now);
    if now - start < rd.at {
        return;
    }
    rd.done = true;
    let mut api = rd.api.lock().unwrap();
    api.trigger_capture();
    info!("RDOC: capture triggered at t={now:.1}s");
}
