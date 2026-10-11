//! **Prepass / main-pass pipeline sync** — the "pale-white / sky-blue foliage" fix.
//!
//! Every material mesh is drawn twice on the camera: once in the depth(+normal+motion) PREPASS and
//! once in the main opaque pass. Bevy specialises and compiles a separate render pipeline for each
//! pass, compiles them asynchronously, and each pass silently SKIPS any draw whose pipeline isn't
//! compiled yet. When the prepass pipeline lands first (common on a cold driver shader cache, or
//! whenever a new mesh/material key first comes into view), the mesh writes depth but no colour:
//! the main pass then fails the depth test everywhere behind it, the sky pass doesn't draw there
//! either (depth isn't far), and the pixels keep the clear colour plus the atmosphere's aerial
//! haze — the ragged pale-white / sky-blue / lavender tree crowns and grass clumps.
//!
//! [`hold_prepass_until_main_ready`] closes that window: after both queue systems ran, any visible
//! mesh whose main-pass pipeline isn't ready yet is pulled back out of the prepass bins (and parked
//! until it is), so the two passes always agree — a not-yet-compiled mesh is simply absent for a
//! moment instead of punching a sky-coloured hole. `FOREST_PREPASS_SYNC=0` disables it (A/B).
//!
//! The same pass counts the visible meshes still waiting on their main-pass pipeline and mirrors it
//! to the main world ([`world_pipelines_ready`]), so the loading veil and the capture harness can
//! wait for exactly the pipelines the camera needs (foliage, cover, terrain, …) instead of the
//! global "waiting pipelines" count, which never drains (see [`log_pipeline_report`]).
//!
//! `FOREST_PIPEDIAG=1` logs the counts every second plus any pipeline stuck waiting.

use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};

use bevy::core_pipeline::prepass::{AlphaMask3dPrepass, Opaque3dPrepass};
use bevy::pbr::{
    queue_material_meshes, queue_prepass_material_meshes, PendingPrepassMeshMaterialQueues,
    SpecializedMaterialPipelineCache, SpecializedPrepassMaterialPipelineCache,
};
use bevy::platform::collections::{HashMap, HashSet};
use bevy::prelude::*;
use bevy::render::render_phase::ViewBinnedRenderPhases;
use bevy::render::render_resource::{CachedPipelineState, CachedRenderPipelineId, PipelineCache, PipelineDescriptor};
use bevy::render::sync_world::MainEntity;
use bevy::render::view::{ExtractedView, RenderVisibleEntities, RetainedViewEntity};
use bevy::render::{Render, RenderApp, RenderSystems};

/// Visible camera meshes whose main-pass pipeline isn't compiled yet (mirrored each frame).
static UNREADY: AtomicUsize = AtomicUsize::new(0);
/// Set once the render world has run the sync pass at least once (so "0 unready" means something).
static SEEN: AtomicBool = AtomicBool::new(false);
/// Render pipelines of any kind still queued / compiling (post stack, compute, off-screen meshes).
static WAITING: AtomicUsize = AtomicUsize::new(0);

/// True once every mesh the camera can see has its main-pass pipeline compiled. Always true
/// without a render app (headless tests / verify runs), so nothing ever waits on it there.
pub fn world_pipelines_ready() -> bool {
    !SEEN.load(Ordering::Relaxed) || UNREADY.load(Ordering::Relaxed) == 0
}

/// Count of visible camera meshes still waiting on a main-pass pipeline (0 without a render app).
pub fn unready_meshes() -> usize {
    UNREADY.load(Ordering::Relaxed)
}

/// Pipelines of any kind still queued or compiling (0 without a render app).
pub fn waiting_pipelines() -> usize {
    WAITING.load(Ordering::Relaxed)
}

/// The frame is final: every visible mesh can draw its colour AND nothing else (post stack, bloom,
/// tonemapping, culling compute, …) is still compiling. On a cold driver shader cache this takes
/// tens of seconds after the world appears; on a warm one, a few frames. Readers cap their wait.
pub fn settled() -> bool {
    world_pipelines_ready() && waiting_pipelines() == 0
}

fn sync_enabled() -> bool {
    std::env::var("FOREST_PREPASS_SYNC").map(|v| v != "0").unwrap_or(true)
}

fn diag_enabled() -> bool {
    std::env::var("FOREST_PIPEDIAG").is_ok_and(|v| v != "0")
}

pub struct PipelineSyncPlugin;

impl Plugin for PipelineSyncPlugin {
    fn build(&self, app: &mut App) {
        let Some(render_app) = app.get_sub_app_mut(RenderApp) else { return };
        render_app.add_systems(
            Render,
            hold_prepass_until_main_ready
                .in_set(RenderSystems::QueueMeshes)
                .after(queue_prepass_material_meshes)
                .after(queue_material_meshes),
        );
        if diag_enabled() {
            render_app.add_systems(Render, log_pipeline_report.in_set(RenderSystems::Cleanup));
        }
    }
}

/// Meshes pulled out of the prepass, per view, until their main-pass pipeline compiles.
#[derive(Default)]
struct Held(HashMap<RetainedViewEntity, HashSet<(Entity, MainEntity)>>);

fn ready(cache: &PipelineCache, id: CachedRenderPipelineId) -> bool {
    matches!(cache.get_render_pipeline_state(id), CachedPipelineState::Ok(_))
}

#[allow(clippy::too_many_arguments)]
fn hold_prepass_until_main_ready(
    views: Query<(&ExtractedView, &RenderVisibleEntities)>,
    pipeline_cache: Res<PipelineCache>,
    main_cache: Res<SpecializedMaterialPipelineCache>,
    prepass_cache: Res<SpecializedPrepassMaterialPipelineCache>,
    mut opaque_prepass: ResMut<ViewBinnedRenderPhases<Opaque3dPrepass>>,
    mut alpha_mask_prepass: ResMut<ViewBinnedRenderPhases<AlphaMask3dPrepass>>,
    mut pending: ResMut<PendingPrepassMeshMaterialQueues>,
    mut held: Local<Held>,
    mut stats: Local<DiagStats>,
) {
    let t0 = std::time::Instant::now();
    let sync = sync_enabled();
    let mut unready = 0usize;
    let mut holes = 0usize;
    let mut live_views = HashSet::new();
    for (view, visible) in &views {
        let key = view.retained_view_entity;
        let (Some(main_view), Some(prepass_view)) = (main_cache.get(&key), prepass_cache.get(&key)) else {
            continue;
        };
        let Some(visible) = visible.get::<Mesh3d>() else { continue };
        live_views.insert(key);
        let held_view = held.0.entry(key).or_default();

        // Release parked meshes whose main pipeline has compiled (or that left view): queue them
        // into the prepass's retry list, which re-bins them next frame from the cached pipeline.
        if !held_view.is_empty() {
            let pending_view = pending.0.entry(key).or_default();
            held_view.retain(|&(e, me)| {
                let keep = visible.entity_pair_is_visible(e, me)
                    && main_view.get(&me).is_none_or(|&id| !ready(&pipeline_cache, id));
                if !keep {
                    pending_view.current_frame.insert((e, me));
                }
                keep
            });
        }

        for (&e, &me) in visible.iter_visible() {
            // Only meshes the prepass actually draws matter: those with a compiled prepass pipeline.
            let Some(&(_, prepass_id, _)) = prepass_view.get(&me) else { continue };
            let main_ok = main_view.get(&me).is_some_and(|&id| ready(&pipeline_cache, id));
            if main_ok {
                continue;
            }
            unready += 1;
            if !ready(&pipeline_cache, prepass_id) {
                continue;
            }
            // Depth-only so far: a hole this frame unless we pull it. Pull even if already parked —
            // a respecialisation (or re-entering view) can have re-binned it this frame; removing an
            // entity that isn't binned is a no-op.
            if !held_view.contains(&(e, me)) {
                holes += 1;
            }
            if sync {
                if let Some(phase) = opaque_prepass.get_mut(&key) {
                    phase.remove(me);
                }
                if let Some(phase) = alpha_mask_prepass.get_mut(&key) {
                    phase.remove(me);
                }
                held_view.insert((e, me));
            }
        }
    }
    held.0.retain(|k, _| live_views.contains(k));

    SEEN.store(true, Ordering::Relaxed);
    UNREADY.store(unready, Ordering::Relaxed);
    WAITING.store(pipeline_cache.waiting_pipelines().count(), Ordering::Relaxed);
    if diag_enabled() {
        let held_n: usize = held.0.values().map(HashSet::len).sum();
        stats.frames += 1;
        stats.max_cost_us = stats.max_cost_us.max(t0.elapsed().as_micros() as u64);
        stats.sum_cost_us += t0.elapsed().as_micros() as u64;
        stats.max_holes = stats.max_holes.max(holes);
        if stats.frames % 60 == 0 {
            info!(
                "pipesync: unready {unready}, new holes/frame max {}, held {held_n}, cost avg {}us max {}us (sync {})",
                stats.max_holes,
                stats.sum_cost_us / 60,
                stats.max_cost_us,
                sync,
            );
            stats.max_holes = 0;
            stats.max_cost_us = 0;
            stats.sum_cost_us = 0;
        }
    }
}

#[derive(Default)]
struct DiagStats {
    frames: u64,
    max_holes: usize,
    max_cost_us: u64,
    sum_cost_us: u64,
}

/// `FOREST_PIPEDIAG`: every ~5 s, list the pipelines still waiting (label, shaders, state), so a
/// pipeline that never compiles is named instead of silently holding the waiting count above 0.
fn log_pipeline_report(cache: Res<PipelineCache>, mut frame: Local<u64>) {
    *frame += 1;
    if *frame % 300 != 0 {
        return;
    }
    let all: Vec<_> = cache.pipelines().collect();
    let mut waiting: Vec<usize> = cache.waiting_pipelines().collect();
    waiting.sort_unstable();
    let mut by_kind: HashMap<String, usize> = HashMap::default();
    let mut lines = Vec::new();
    for id in &waiting {
        let Some(p) = all.get(*id) else { continue };
        let state = match &p.state {
            CachedPipelineState::Queued => "queued".to_string(),
            CachedPipelineState::Creating(_) => "creating".to_string(),
            CachedPipelineState::Ok(_) => "ok".to_string(),
            CachedPipelineState::Err(e) => format!("err: {e}"),
        };
        let (label, shaders) = match &p.descriptor {
            PipelineDescriptor::RenderPipelineDescriptor(d) => (
                d.label.as_deref().unwrap_or("?").to_string(),
                format!(
                    "vs {:?} fs {:?}",
                    d.vertex.shader.path().map(|p| p.to_string()).unwrap_or_else(|| format!("{:?}", d.vertex.shader.id())),
                    d.fragment.as_ref().map(|f| f.shader.path().map(|p| p.to_string()).unwrap_or_else(|| format!("{:?}", f.shader.id())))
                ),
            ),
            PipelineDescriptor::ComputePipelineDescriptor(d) => (
                d.label.as_deref().unwrap_or("?").to_string(),
                format!("cs {:?}", d.shader.path().map(|p| p.to_string()).unwrap_or_else(|| format!("{:?}", d.shader.id()))),
            ),
        };
        *by_kind.entry(state.clone()).or_default() += 1;
        if lines.len() < 24 {
            lines.push(format!("  #{id} [{label}] {shaders} -> {state}"));
        }
    }
    info!(
        "pipediag frame {}: {} pipelines, {} waiting {:?}, unready visible meshes {}",
        *frame,
        all.len(),
        waiting.len(),
        by_kind,
        unready_meshes()
    );
    for l in lines {
        info!("{l}");
    }
}
