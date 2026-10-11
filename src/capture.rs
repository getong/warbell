//! Capture harness — the Bevy window can't be grabbed by external tools, so we render
//! to disk ourselves. Two modes, both read once at startup:
//!
//! - `FOREST_SHOT=<path.png>` — single screenshot: render ~90 frames (so lighting / IBL /
//!   prepasses settle), grab the window, save, exit.
//! - `FOREST_CLIP=<dir>` — frame-sequence capture for GIFs / video: after a short warm-up,
//!   save every frame as `<dir>/frame_00001.png …` for `FOREST_CLIP_FRAMES` frames, then exit.
//!   A clamped fixed timestep keeps the world motion smooth despite the per-frame PNG-encode
//!   stall, and an optional slow camera orbit (`FOREST_CLIP_ORBIT`) circles a point of
//!   interest. ffmpeg then stitches the sequence into a clip at `FOREST_CLIP_FPS`.
//!
//! Clip knobs (all optional, env, read at startup):
//! | `FOREST_CLIP_FRAMES` | saved frames (default 150) |
//! | `FOREST_CLIP_FPS`    | playback fps → fixed timestep + ffmpeg rate (default 30) |
//! | `FOREST_CLIP_WARMUP` | warm-up frames before the first save (default 30) |
//! | `FOREST_CLIP_ORBIT`  | `"cx,cy,cz,radius,height,deg_per_sec"` slow camera orbit around a point |

use bevy::prelude::*;
use bevy::render::view::screenshot::{save_to_disk, Screenshot};
use std::time::Duration;

pub struct CapturePlugin;

#[derive(Resource)]
pub(crate) struct ShotPath(pub(crate) String);

/// Set `true` by a follow-up shot sequence (e.g. `player::boom`'s `FOREST_BOOMSHOTS`) to keep the
/// app alive after the main `FOREST_SHOT` lands; `drive_shot` exits once it drops back to `false`.
#[derive(Resource, Default)]
pub(crate) struct ShotHold(pub(crate) bool);

#[derive(Resource, Default)]
struct ShotClock {
    frame: u32,
    shot: bool,
    /// Frame the screenshot was requested on — the readback safety cap counts from HERE, not from
    /// boot, or a long `FOREST_SHOT_WARMUP` (request at frame ≫ cap) exits the app the same frame
    /// as the request and the async readback lands on a despawned window ("Unknown window", no PNG).
    shot_at: u32,
    /// `FOREST_SHOT_STORIES=1`: after the main shot, one extra shot per snow story site (cameras
    /// from `stories_cold::shot_cams`), each saved next to the main PNG as `<name>.png`.
    seq: Option<Vec<(String, Transform)>>,
    seq_idx: usize,
    seq_frame: u32,
    seq_shot: bool,
}

impl Plugin for CapturePlugin {
    fn build(&self, app: &mut App) {
        if let Ok(path) = std::env::var("FOREST_SHOT") {
            app.insert_resource(ShotPath(path))
                .init_resource::<ShotClock>()
                .init_resource::<ShotHold>()
                .add_systems(Update, drive_shot);
        } else if let Ok(dir) = std::env::var("FOREST_CLIP") {
            let cfg = clip_cfg(dir);
            // `FOREST_CLIP_FIXED=1`: every tick advances the sim by exactly one playback frame
            // (the default only caps the step, so quick ticks between PNG saves record unevenly
            // spaced frames) — for frame-exact animation reviews.
            if std::env::var("FOREST_CLIP_FIXED").is_ok() {
                app.insert_resource(bevy::time::TimeUpdateStrategy::ManualDuration(Duration::from_secs_f32(
                    1.0 / cfg.fps as f32,
                )));
            }
            app.insert_resource(cfg)
                .init_resource::<ClipClock>()
                .init_resource::<ClipProgress>()
                .add_systems(Startup, clip_setup)
                .add_systems(Update, (clip_orbit, drive_clip).chain());
        }
        // FOREST_NOHUD=1: hide every UI node each frame (HUD, prompts, quick-bar) so a
        // staged shot shows only the world — for marketing/store captures.
        if std::env::var("FOREST_NOHUD").is_ok() || crate::controls::walk_mode() {
            app.add_systems(Update, hide_hud);
        }
    }
}

fn hide_hud(
    mut nodes: Query<&mut Visibility, With<Node>>,
    menu: Option<Res<crate::ui::graphics_menu::GraphicsMenuOpen>>,
) {
    // The forest walk's Settings panel (key O) must stay usable: pause the hiding while it's up
    // (the HUD nodes stay hidden from before; only the freshly spawned panel shows).
    if menu.is_some_and(|m| m.0) {
        return;
    }
    for mut vis in &mut nodes {
        *vis = Visibility::Hidden;
    }
}

fn drive_shot(
    mut clock: ResMut<ShotClock>,
    // `Time<Real>` (true wall-clock), NOT the default `Res<Time>` (virtual): a hit-stop slowmo or a
    // debug pause scales/freezes virtual time, which must not stall the warm-up gate below.
    time: Res<Time<Real>>,
    path: Res<ShotPath>,
    mut commands: Commands,
    mut exit: MessageWriter<AppExit>,
    mut cams: Query<(&mut Transform, Option<&mut crate::controls::FlyCam>), With<Camera3d>>,
    hold: Res<ShotHold>,
) {
    clock.frame += 1;
    // Take the shot once the scene has actually WARMED: ≥240 rendered frames AND ≥10 s wall-clock
    // (raised from 120/6 s — user report: shaders sometimes still hadn't finished compiling at
    // grab time, so shots captured with missing materials). `FOREST_SHOT_WARMUP=<secs>` raises
    // the wall-clock floor further for pathological cases. The wall-clock floor is load-bearing
    // on a COLD run — the first frame stalls several seconds compiling every render pipeline
    // (and the IBL / atmosphere LUTs take a few frames to settle), and a bare frame count
    // elapses while the GPU is still warming, so the grab races an unfinished scene and captures
    // BLACK or shader-less patches. (On a warm run the extra latency is fine for a verification
    // shot.) Spawn the screenshot exactly once. We exit on file-existence below, so FIRST ensure
    // the parent dir exists AND delete any stale PNG already at this path — otherwise a leftover
    // from a prior run trips the exit guard on this very frame (before the async readback lands)
    // and the harness exits leaving the OLD image in place.
    let min_secs = std::env::var("FOREST_SHOT_WARMUP")
        .ok()
        .and_then(|v| v.parse::<f32>().ok())
        .unwrap_or(0.0)
        .max(10.0);
    if !clock.shot && clock.frame >= 240 && time.elapsed_secs() >= min_secs {
        if let Some(parent) = std::path::Path::new(&path.0).parent().filter(|p| !p.as_os_str().is_empty()) {
            let _ = std::fs::create_dir_all(parent);
        }
        let _ = std::fs::remove_file(&path.0);
        commands.spawn(Screenshot::primary_window()).observe(save_to_disk(path.0.clone()));
        clock.shot = true;
        clock.shot_at = clock.frame;
    }
    // The shot is an async GPU readback: `save_to_disk` (and the PNG write) only fire once the
    // `ScreenshotCaptured` observer lands, a few frames AFTER the request. So once requested, keep
    // rendering until the (freshly-written) file exists on disk, or a hard safety cap (counted
    // from the REQUEST frame — see `shot_at`), THEN exit — a fixed-frame exit would race the
    // readback and write no PNG.
    if clock.shot && (std::path::Path::new(&path.0).exists() || clock.frame > clock.shot_at + 1800) {
        if std::env::var("FOREST_SHOT_STORIES").is_ok() && drive_story_seq(&mut clock, &path.0, &mut commands, &mut cams) {
            return;
        }
        if hold.0 {
            return;
        }
        exit.write(AppExit::Success);
    }
}

/// One extra shot per story site after the main shot: park the camera (and the fly-cam's eased
/// yaw/pitch, so it doesn't swing back), let ~45 frames settle, grab, wait for the PNG, next.
/// Returns `true` while the sequence still runs.
fn drive_story_seq(
    clock: &mut ShotClock,
    main: &str,
    commands: &mut Commands,
    cams: &mut Query<(&mut Transform, Option<&mut crate::controls::FlyCam>), With<Camera3d>>,
) -> bool {
    if clock.seq.is_none() {
        clock.seq = Some(crate::stories_cold::shot_cams());
    }
    let dir = std::path::Path::new(main).parent().map(|p| p.to_path_buf()).unwrap_or_default();
    let list = clock.seq.clone().unwrap_or_default();
    let Some((name, tf)) = list.get(clock.seq_idx) else { return false };
    let out = dir.join(format!("{name}.png"));
    if clock.seq_frame == 0 {
        let _ = std::fs::remove_file(&out);
        for (mut t, fly) in cams.iter_mut() {
            *t = *tf;
            if let Some(mut f) = fly {
                let (yaw, pitch, _) = tf.rotation.to_euler(EulerRot::YXZ);
                (f.yaw, f.pitch, f.target_yaw, f.target_pitch, f.vel) = (yaw, pitch, yaw, pitch, Vec3::ZERO);
            }
        }
    }
    clock.seq_frame += 1;
    if !clock.seq_shot && clock.seq_frame >= 45 {
        commands.spawn(Screenshot::primary_window()).observe(save_to_disk(out.clone()));
        clock.seq_shot = true;
    }
    if clock.seq_shot && (out.exists() || clock.seq_frame > 900) {
        info!("story shot {name} saved: {}", out.display());
        clock.seq_idx += 1;
        clock.seq_frame = 0;
        clock.seq_shot = false;
    }
    true
}

// ── clip mode ──────────────────────────────────────────────────────────────────────

#[derive(Resource)]
struct ClipCfg {
    dir: String,
    frames: u32,
    warmup: u32,
    fps: u32,
    orbit: Option<Orbit>,
}

#[derive(Clone, Copy)]
struct Orbit {
    center: Vec3,
    radius: f32,
    height: f32,
    /// degrees per second
    speed: f32,
}

#[derive(Resource, Default)]
struct ClipClock {
    /// total ticks elapsed (warm-up included)
    frame: u32,
    /// frames written to disk
    saved: u32,
    /// tick the last frame was written — start of the flush tail
    done_at: Option<u32>,
}

/// Read by the demo director (`demo.rs` / `town.rs`) so scripted timelines (the hero walk, the
/// build sequence, caption cues) start only once recording begins — the warm-up frames render
/// (shaders compile, lighting / IBL / the world sim settle) without burning the scripted action.
#[derive(Resource, Default)]
pub struct ClipProgress {
    /// false during warm-up, true once frames are being saved
    pub recording: bool,
    /// count of frames written so far (0 during warm-up) — a frame-locked clock for scripts
    pub frame: u32,
}

fn clip_cfg(dir: String) -> ClipCfg {
    let num = |k: &str, d: f32| {
        std::env::var(k).ok().and_then(|s| s.trim().parse::<f32>().ok()).unwrap_or(d)
    };
    ClipCfg {
        dir,
        frames: num("FOREST_CLIP_FRAMES", 150.0).max(1.0) as u32,
        warmup: num("FOREST_CLIP_WARMUP", 30.0).max(0.0) as u32,
        fps: num("FOREST_CLIP_FPS", 30.0).max(1.0) as u32,
        orbit: std::env::var("FOREST_CLIP_ORBIT").ok().and_then(parse_orbit),
    }
}

fn parse_orbit(s: String) -> Option<Orbit> {
    let v: Vec<f32> = s.split(',').filter_map(|p| p.trim().parse().ok()).collect();
    (v.len() == 6).then(|| Orbit {
        center: Vec3::new(v[0], v[1], v[2]),
        radius: v[3],
        height: v[4],
        speed: v[5],
    })
}

fn clip_setup(cfg: Res<ClipCfg>, mut vtime: ResMut<Time<Virtual>>) {
    let _ = std::fs::create_dir_all(&cfg.dir);
    // Clamp the per-tick delta to exactly one playback frame. Encoding a PNG every frame makes a
    // tick take far longer than 1/fps of wall-clock, so without this the world would fast-forward
    // in big jumps between saved frames. Clamped, every tick advances the sim by ≤1/fps, so the
    // recorded motion plays back as smooth real-time when ffmpeg assembles at FOREST_CLIP_FPS.
    vtime.set_max_delta(Duration::from_secs_f32(1.0 / cfg.fps as f32));
}

/// Optional cinematic move: circle `center` at a fixed radius/height, `speed` deg/s. Driven off
/// the saved-frame index (not wall time) so the path is deterministic. The fly-cam is idle under
/// capture (no input), so writing the transform here doesn't fight it.
fn clip_orbit(cfg: Res<ClipCfg>, clock: Res<ClipClock>, mut cam: Query<&mut Transform, With<Camera3d>>) {
    let Some(o) = cfg.orbit else { return };
    let t = clock.frame.saturating_sub(cfg.warmup) as f32 / cfg.fps as f32;
    let ang = (o.speed * t).to_radians();
    let pos = Vec3::new(o.center.x + o.radius * ang.cos(), o.height, o.center.z + o.radius * ang.sin());
    for mut tf in &mut cam {
        *tf = Transform::from_translation(pos).looking_at(o.center, Vec3::Y);
    }
}

fn drive_clip(
    cfg: Res<ClipCfg>,
    mut clock: ResMut<ClipClock>,
    mut prog: ResMut<ClipProgress>,
    mut commands: Commands,
    mut exit: MessageWriter<AppExit>,
) {
    prog.recording = clock.frame >= cfg.warmup;
    prog.frame = clock.saved;
    // Flush tail: all frames written → wait a few ticks for the async disk writes to land, exit.
    if let Some(done) = clock.done_at {
        if clock.frame >= done + 15 {
            exit.write(AppExit::Success);
        }
        clock.frame += 1;
        return;
    }

    if clock.frame >= cfg.warmup && clock.saved < cfg.frames {
        clock.saved += 1;
        let path = format!("{}/frame_{:05}.png", cfg.dir, clock.saved);
        commands.spawn(Screenshot::primary_window()).observe(save_to_disk(path));
        if clock.saved >= cfg.frames {
            clock.done_at = Some(clock.frame);
        }
    }
    clock.frame += 1;
}
