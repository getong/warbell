//! **Night-siege storm** — distant lightning flashes + delayed thunder while a wave is on.
//!
//! Sieges happen at night, so the trigger is simply the `Wave` phase (no separate time check).
//! A flash is a brief full-frame blue-white brighten via a `bevy_ui` overlay (over the 3D scene,
//! under the HUD — same layering trick as `grade.rs`'s vignette), not a real light, so it can't
//! fight `scene::advance_sky`'s per-frame sun/moon/ambient writes. Each strike schedules a
//! `Thunder` cue a beat later (sound lags the flash), and the interval/delay are jittered off the
//! clock so strikes don't fall on a metronome. Idle by day / between waves.

use bevy::prelude::*;

use crate::audio::AudioCue;
use crate::siege::{GamePhase, Siege};

/// Overlay tag — one fullscreen node whose alpha is the flash intensity.
#[derive(Component)]
struct StormFlash;

/// Storm state: countdown to the next strike, the current flash intensity (1 → 0), and when the
/// scheduled thunder should fire (`<0` = none pending).
#[derive(Resource)]
struct Storm {
    next_flash: f32,
    flash: f32,
    thunder_at: f32,
}

impl Default for Storm {
    fn default() -> Self {
        Storm { next_flash: 4.0, flash: 0.0, thunder_at: -1.0 }
    }
}

pub struct StormPlugin;

impl Plugin for StormPlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<Storm>()
            .add_systems(Startup, spawn_flash)
            // Ungated (like the sky/firelight render systems) so a flash always finishes its
            // decay — even if a panel opens mid-strike — instead of freezing on screen.
            .add_systems(Update, drive_storm);
    }
}

fn spawn_flash(mut commands: Commands) {
    commands.spawn((
        StormFlash,
        Node {
            position_type: PositionType::Absolute,
            top: Val::Px(0.0),
            left: Val::Px(0.0),
            width: Val::Percent(100.0),
            height: Val::Percent(100.0),
            ..default()
        },
        BackgroundColor(Color::NONE),
        GlobalZIndex(-1),            // over the 3D scene, under the HUD (same as the vignette)
        bevy::ui::FocusPolicy::Pass, // never intercept clicks
    ));
}

fn drive_storm(
    time: Res<Time>,
    siege: Option<Res<Siege>>,
    mut storm: ResMut<Storm>,
    mut cues: MessageWriter<AudioCue>,
    mut q: Query<&mut BackgroundColor, With<StormFlash>>,
) {
    let now = time.elapsed_secs();
    let dt = time.delta_secs();

    // Fire the thunder scheduled by the last flash (the sound lags the light).
    if storm.thunder_at > 0.0 && now >= storm.thunder_at {
        storm.thunder_at = -1.0;
        cues.write(AudioCue::Thunder);
    }

    let active = siege.is_some_and(|s| matches!(s.phase, GamePhase::Wave));
    if active {
        storm.next_flash -= dt;
        if storm.next_flash <= 0.0 {
            storm.flash = 1.0;
            // Clock-hashed jitter (no RNG resource needed here): interval 6–16 s, thunder delay
            // 0.5–1.9 s behind the flash.
            let r = (now * 91.7).sin().abs();
            let r2 = (now * 53.3).sin().abs();
            storm.next_flash = 6.0 + r * 10.0;
            storm.thunder_at = now + 0.5 + r2 * 1.4;
        }
    } else {
        storm.flash = 0.0;
        // A short lead so the first strike doesn't land the instant the next wave begins.
        storm.next_flash = storm.next_flash.max(3.0);
    }

    // Sharp pop + quick fade: `flash²` front-loads the brightness, decay ~4/s clears it in <0.3 s.
    storm.flash = (storm.flash - dt * 4.0).max(0.0);
    if let Ok(mut bg) = q.single_mut() {
        let a = storm.flash * storm.flash * 0.30; // peak ≈ 0.30 alpha — a flash, not a whiteout
        bg.0 = Color::srgba(0.80, 0.85, 1.0, a);
    }
}
