//! Trailer staging **director** — triggerable staged scenes/animations for filming a trailer.
//! The user flies their OWN free-cam (` toggles it); this module only stages the WORLD: a fast
//! day→night→dawn sky, custom hero gestures the game never plays, a castle build timelapse, and
//! an ork column marching out of Gnashfang Hold. Everything is fired live from the F1 debug
//! panel's "🎬 Director" section, which mutates [`DirectorState`].
//!
//! Each scene's heavy lifting lives in the module that owns the relevant API (build → `town.rs`,
//! ork march → `siege.rs`, hero gesture → `player/anim.rs`); this module owns the shared state,
//! the self-contained sky timelapse, and the gesture-phase clock.

use bevy::prelude::*;

use crate::scene::SkyClock;

pub struct CinematicPlugin;

/// Staged hero gestures the normal game never plays — for "performance" trailer shots. Held until
/// cleared; looping ones (Wave/Cheer/Work) phase off [`DirectorState::gesture_start`].
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum HeroGesture {
    /// Right arm overhead, hand waving side to side.
    Wave,
    /// Right hand snapped to the brow.
    Salute,
    /// Right arm thrust forward, commanding.
    Point,
    /// Both arms folded across the chest (the "supervise" idle).
    ArmsCrossed,
    /// Both arms thrown overhead.
    Cheer,
    /// A looping chop/hammer swing — the "at work" animation.
    Work,
}

/// Tags an ork that's part of a staged fortress march. Driven by `siege::director_march`, and
/// explicitly SKIPPED by the normal camp brain (`orks::ork_brain`) so the two don't fight over it.
#[derive(Component)]
pub struct DirectorMarcher;

/// Shared trailer-staging state. The F1 panel writes it; the per-scene systems read/consume it.
#[derive(Resource)]
pub struct DirectorState {
    /// Day→night→dawn timelapse: while on, the sky clock is driven at `sky_speed` (t units/sec).
    pub sky_run: bool,
    pub sky_speed: f32,
    /// Held hero gesture (None = normal animation); `gesture_start` is the loop-phase origin.
    pub gesture: Option<HeroGesture>,
    pub gesture_start: f32,
    /// Castle build timelapse: raise the whole stronghold piece by piece in real time.
    pub build_run: bool,
    /// Edge triggers consumed once by `siege::director_march`.
    pub march: bool,
    pub clear_marchers: bool,
}

impl Default for DirectorState {
    fn default() -> Self {
        Self {
            sky_run: false,
            sky_speed: 0.06, // ≈17 s for a full day
            gesture: None,
            gesture_start: 0.0,
            build_run: false,
            march: false,
            clear_marchers: false,
        }
    }
}

impl Plugin for CinematicPlugin {
    fn build(&self, app: &mut App) {
        // `FOREST_GESTURE=wave|salute|point|arms|cheer|work` stages a hero gesture at boot (for a
        // screenshot of the pose) — the same staging-hook style as the other `FOREST_*` vars.
        let mut state = DirectorState::default();
        if let Ok(g) = std::env::var("FOREST_GESTURE") {
            state.gesture = match g.trim().to_ascii_lowercase().as_str() {
                "wave" => Some(HeroGesture::Wave),
                "salute" => Some(HeroGesture::Salute),
                "point" => Some(HeroGesture::Point),
                "arms" | "armscrossed" | "cross" => Some(HeroGesture::ArmsCrossed),
                "cheer" => Some(HeroGesture::Cheer),
                "work" => Some(HeroGesture::Work),
                _ => None,
            };
        }
        app.insert_resource(state)
            .add_systems(Update, (sky_timelapse, track_gesture));
    }
}

/// Drive a fast day/night cycle while `sky_run` is on; hand the clock back to the normal
/// phase-driven sky the moment it's switched off.
fn sky_timelapse(
    state: Res<DirectorState>,
    time: Res<Time>,
    mut clock: ResMut<SkyClock>,
    mut was: Local<bool>,
) {
    if state.sky_run {
        clock.paused = true;
        clock.t = (clock.t + state.sky_speed * time.delta_secs()).rem_euclid(1.0);
    } else if *was {
        clock.paused = false;
    }
    *was = state.sky_run;
}

/// Stamp `gesture_start` whenever the active gesture changes, so looping gestures have a phase 0.
fn track_gesture(
    mut state: ResMut<DirectorState>,
    time: Res<Time>,
    mut prev: Local<Option<HeroGesture>>,
) {
    if state.gesture != *prev {
        state.gesture_start = time.elapsed_secs();
        *prev = state.gesture;
    }
}
