//! Background music — a **phase-driven multi-track** mix ported from the old game's `SoundScape`
//! crossfade. Four loops play continuously (no start/stop pops); we only ride their volumes:
//!   - **Bed** (day) — audible in prep/free-roam, ducked under a combat swell.
//!   - **Combat** — swells over the bed while the hero is in a daytime ork fight.
//!   - **Night dread** — swells in while the siege is in its `Wave` phase (and it's not the boss).
//!   - **Boss march** — replaces the dread on the final boss wave.

use bevy::audio::{PlaybackMode, Volume};
use bevy::prelude::*;

use super::{AudioConfig, MusicState};
use crate::siege::{GamePhase, Siege, WAVES};

/// How fast the combat layer eases in/out (per second).
const COMBAT_FADE: f32 = 1.5;
/// How fast the day↔night crossfade eases.
const NIGHT_FADE: f32 = 0.9;
/// How far the day bed ducks under a full combat swell (1.0 = combat plays solo).
const BED_DUCK: f32 = 1.0;

/// Which music loop a sink is.
#[derive(Component, Clone, Copy)]
pub(crate) enum MusicLayer {
    Bed,
    Combat,
    Night,
    Boss,
}

pub(crate) fn setup_music(asset: Res<AssetServer>, cfg: Res<AudioConfig>, mut commands: Commands) {
    let mut layer = |file: &'static str, vol: f32, which: MusicLayer| {
        commands.spawn((
            AudioPlayer(asset.load::<AudioSource>(file)),
            PlaybackSettings {
                mode: PlaybackMode::Loop,
                volume: Volume::Linear(vol),
                spatial: false,
                ..default()
            },
            which,
        ));
    };
    layer("audio/music-bed.ogg", cfg.music_vol, MusicLayer::Bed); // day bed — audible from start
    layer("audio/music-combat.ogg", 0.0, MusicLayer::Combat); // silent until a fight
    layer("audio/soot-banner-dread.ogg", 0.0, MusicLayer::Night); // silent until a wave
    layer("audio/orc-march-tallow.ogg", 0.0, MusicLayer::Boss); // silent until the boss wave
}

pub(crate) fn update_music(
    time: Res<Time>,
    cfg: Res<AudioConfig>,
    state: Res<MusicState>,
    siege: Option<Res<Siege>>,
    mut heat: Local<f32>,
    mut night: Local<f32>,
    mut q: Query<(&MusicLayer, &mut AudioSink)>,
) {
    let dt = time.delta_secs();
    let (is_wave, boss) = match siege.as_deref() {
        Some(s) => {
            let wave = s.phase == GamePhase::Wave;
            (wave, wave && s.wave_index >= 0 && s.wave_index as usize == WAVES.len() - 1)
        }
        None => (false, false),
    };

    // Ease the two mix scalars: combat (daytime ork fight) + night (the siege wave).
    let combat_target = if state.fighting { 1.0 } else { 0.0 };
    *heat += (combat_target - *heat) * (dt * COMBAT_FADE).min(1.0);
    *night += ((if is_wave { 1.0 } else { 0.0 }) - *night) * (dt * NIGHT_FADE).min(1.0);
    let (h, n) = (*heat, *night);
    let day = cfg.music_vol * (1.0 - n); // day tracks fade out as night rises

    for (layer, mut sink) in &mut q {
        let v = match layer {
            MusicLayer::Bed => day * (1.0 - BED_DUCK * h),
            MusicLayer::Combat => day * cfg.combat_music * h,
            MusicLayer::Night => cfg.music_vol * n * if boss { 0.0 } else { 1.0 },
            MusicLayer::Boss => cfg.music_vol * n * if boss { 1.0 } else { 0.0 },
        };
        sink.set_volume(Volume::Linear(v));
    }
}
