//! **Clip audio capture** — records the game's OWN mixed audio, sample-locked to the
//! `FOREST_CLIP` frame sequence, into `<clip dir>/audio.wav`.
//!
//! Bevy's audio output is a private resource hard-wired to the sound device, and a clip runs far
//! slower than real time (each frame stalls on a PNG encode), so recording the device would drift
//! out of sync within seconds. Instead every sound the game starts (`AudioPlayer<AudioSource>` +
//! its `AudioSink` / `SpatialAudioSink`) is MIRRORED into our own rodio mixer that no device pulls:
//! each recorded frame pulls exactly `sample_rate / fps` samples, so audio time advances in lockstep
//! with the frames (the sim runs a fixed `1/fps` step under capture — see `CapturePlugin`).
//!
//! Each frame the mirror copies the live sink state (volume incl. the game's fades, speed / pitch
//! jitter, pause, mute) and, for spatial sounds, the emitter + ear positions, exactly as
//! `bevy_audio` feeds its own players. A looping sound follows its entity's lifetime; a one-shot
//! plays out to its natural end even when the (faster, wall-clock) device copy finished first and
//! Bevy already despawned the entity. Sounds already playing when recording begins (music, ambience
//! beds) start part-way in, at the point the sim has reached.
//!
//! On by default with `FOREST_CLIP`; `FOREST_CLIP_AUDIO=0` turns it off. Mux with
//! `ffmpeg -framerate 30 -i frame_%05d.png -i audio.wav -c:v libx264 -c:a aac -shortest out.mp4`.

use bevy::audio::{AudioSinkPlayback, DefaultSpatialScale, PlaybackMode, SpatialAudioSink, SpatialListener};
use bevy::prelude::*;
use rodio::Source;
use std::collections::HashMap;
use std::num::NonZero;
use std::sync::Mutex;
use std::time::Duration;

const SAMPLE_RATE: u32 = 48_000;
const CHANNELS: u16 = 2;

pub struct AudioCapturePlugin;

impl Plugin for AudioCapturePlugin {
    fn build(&self, app: &mut App) {
        let Ok(dir) = std::env::var("FOREST_CLIP") else { return };
        if std::env::var("FOREST_CLIP_AUDIO").as_deref() == Ok("0") {
            return;
        }
        let fps = std::env::var("FOREST_CLIP_FPS").ok().and_then(|s| s.trim().parse::<f32>().ok()).unwrap_or(30.0).max(1.0);
        let _ = std::fs::create_dir_all(&dir);
        let path = format!("{dir}/audio.wav");
        let spec = hound::WavSpec { channels: CHANNELS, sample_rate: SAMPLE_RATE, bits_per_sample: 32, sample_format: hound::SampleFormat::Float };
        let writer = match hound::WavWriter::create(&path, spec) {
            Ok(w) => w,
            Err(e) => {
                warn!("clip audio: can't create {path}: {e} — recording video only");
                return;
            }
        };
        let (mixer, mut out) = rodio::mixer::mixer(NonZero::new(CHANNELS).unwrap(), NonZero::new(SAMPLE_RATE).unwrap());
        // An endless silent input keeps the mixer from reporting "ended" between sounds.
        mixer.add(rodio::source::Zero::new(NonZero::new(CHANNELS).unwrap(), NonZero::new(SAMPLE_RATE).unwrap()));
        let _ = out.next();
        info!("clip audio: mirroring game audio into {path} ({SAMPLE_RATE} Hz, {fps} fps)");
        app.insert_resource(Cap {
            inner: Mutex::new(Inner { out, writer, written: 0 }),
            mixer,
            fps,
            mirrors: HashMap::new(),
            first_seen: HashMap::new(),
        })
        .add_systems(PostUpdate, (mirror_audio, render_audio).chain().after(bevy::transform::TransformSystems::Propagate));
    }
}

struct Inner {
    out: rodio::mixer::MixerSource,
    writer: hound::WavWriter<std::io::BufWriter<std::fs::File>>,
    /// Sample FRAMES (one per channel pair) written so far.
    written: u64,
}

enum Player {
    Plain(rodio::Player),
    Spatial(rodio::SpatialPlayer),
}

impl Player {
    fn set_volume(&self, v: f32) {
        match self {
            Player::Plain(p) => p.set_volume(v),
            Player::Spatial(p) => p.set_volume(v),
        }
    }
    fn set_speed(&self, v: f32) {
        match self {
            Player::Plain(p) => p.set_speed(v),
            Player::Spatial(p) => p.set_speed(v),
        }
    }
    fn set_paused(&self, paused: bool) {
        match self {
            Player::Plain(p) if paused => p.pause(),
            Player::Plain(p) => p.play(),
            Player::Spatial(p) if paused => p.pause(),
            Player::Spatial(p) => p.play(),
        }
    }
    fn stop(&self) {
        match self {
            Player::Plain(p) => p.stop(),
            Player::Spatial(p) => p.stop(),
        }
    }
    fn detach(self) {
        match self {
            Player::Plain(p) => p.detach(),
            Player::Spatial(p) => p.detach(),
        }
    }
}

struct Mirror {
    player: Player,
    looping: bool,
}

#[derive(Resource)]
struct Cap {
    inner: Mutex<Inner>,
    mixer: rodio::mixer::Mixer,
    fps: f32,
    mirrors: HashMap<Entity, Mirror>,
    /// Sim time each audio entity was first seen — a sound already running when recording starts
    /// is started that far in.
    first_seen: HashMap<Entity, f32>,
}

#[allow(clippy::type_complexity)]
fn mirror_audio(
    mut cap: ResMut<Cap>,
    prog: Option<Res<crate::capture::ClipProgress>>,
    time: Res<Time>,
    sources: Res<Assets<AudioSource>>,
    default_scale: Res<DefaultSpatialScale>,
    ears: Query<(&GlobalTransform, &SpatialListener)>,
    players: Query<(
        Entity,
        &AudioPlayer<AudioSource>,
        &PlaybackSettings,
        Option<&GlobalTransform>,
        Option<&AudioSink>,
        Option<&SpatialAudioSink>,
    )>,
) {
    let now = time.elapsed_secs();
    let recording = prog.is_some_and(|p| p.recording);
    let (left, right) = ears
        .iter()
        .next()
        .map(|(t, l)| (t.transform_point(l.left_ear_offset), t.transform_point(l.right_ear_offset)))
        .unwrap_or_else(|| {
            let l = SpatialListener::default();
            (l.left_ear_offset, l.right_ear_offset)
        });
    let cap = &mut *cap;
    let mut live = Vec::new();
    for (e, player, settings, tf, sink, spatial_sink) in &players {
        // Only sounds the game actually started (Bevy inserted a device sink) are mirrored.
        let state: Option<&dyn AudioSinkPlayback> = match (sink, spatial_sink) {
            (Some(s), _) => Some(s),
            (_, Some(s)) => Some(s),
            _ => None,
        };
        let Some(state) = state else { continue };
        live.push(e);
        let first = *cap.first_seen.entry(e).or_insert(now);
        if !recording {
            continue;
        }
        let scale = settings.spatial_scale.unwrap_or(default_scale.0).0;
        if !cap.mirrors.contains_key(&e) {
            let Some(src) = sources.get(&player.0) else { continue };
            let looping = matches!(settings.mode, PlaybackMode::Loop);
            let p = if settings.spatial {
                let emitter = tf.map_or(Vec3::ZERO, |t| t.translation()) * scale;
                Player::Spatial(rodio::SpatialPlayer::connect_new(&cap.mixer, emitter.into(), (left * scale).into(), (right * scale).into()))
            } else {
                Player::Plain(rodio::Player::connect_new(&cap.mixer))
            };
            // Started before this frame (e.g. during warm-up): join it where the sim has got to.
            let age = Duration::from_secs_f32((now - first).max(0.0) * settings.speed);
            let start = settings.start_position.unwrap_or_default();
            let dec = src.decoder();
            let append = |s: Box<dyn Source + Send>| match &p {
                Player::Plain(pl) => pl.append(s),
                Player::Spatial(pl) => pl.append(s),
            };
            match (looping, settings.duration) {
                (true, Some(d)) => append(Box::new(dec.skip_duration(start).take_duration(d).repeat_infinite().skip_duration(age))),
                (true, None) => append(Box::new(dec.skip_duration(start).repeat_infinite().skip_duration(age))),
                (false, Some(d)) => append(Box::new(dec.skip_duration(start + age).take_duration(d.saturating_sub(age)))),
                (false, None) => append(Box::new(dec.skip_duration(start + age))),
            }
            cap.mirrors.insert(e, Mirror { player: p, looping });
        }
        let m = &cap.mirrors[&e];
        let vol = if state.is_muted() { 0.0 } else { state.volume().to_linear() };
        m.player.set_volume(vol);
        m.player.set_speed(state.speed());
        m.player.set_paused(state.is_paused());
        if let (Player::Spatial(p), Some(t)) = (&m.player, tf) {
            p.set_emitter_position((t.translation() * scale).into());
            p.set_left_ear_position((left * scale).into());
            p.set_right_ear_position((right * scale).into());
        }
    }
    // Entity gone or its sink removed: a loop stops with it; a one-shot rings out on its own.
    let gone: Vec<Entity> = cap.mirrors.keys().copied().filter(|e| !live.contains(e)).collect();
    for e in gone {
        if let Some(m) = cap.mirrors.remove(&e) {
            if m.looping {
                m.player.stop();
            } else {
                m.player.detach();
            }
        }
    }
    cap.first_seen.retain(|e, _| live.contains(e));
}

/// Pull audio up to the end of the last recorded frame and append it to the WAV.
fn render_audio(cap: Res<Cap>, prog: Option<Res<crate::capture::ClipProgress>>) {
    let Some(prog) = prog else { return };
    if !prog.recording {
        return;
    }
    let target = (prog.frame as f64 * SAMPLE_RATE as f64 / cap.fps as f64).round() as u64;
    let mut inner = cap.inner.lock().expect("clip audio poisoned");
    let inner = &mut *inner;
    while inner.written < target {
        for _ in 0..CHANNELS {
            let s = inner.out.next().unwrap_or(0.0);
            // A soft clip instead of wrap-around if a big moment stacks past full scale.
            let _ = inner.writer.write_sample(s.clamp(-1.0, 1.0));
        }
        inner.written += 1;
    }
    // Keep the header valid on disk so a killed run still leaves a playable file.
    let _ = inner.writer.flush();
}
