//! **Settings backing** — the *logic* behind the player-facing settings, with **no permanent HUD
//! chrome**. The toggles themselves live in the Escape pause menu (`game_state::spawn_pause_screen`),
//! which calls the `toggle_*` helpers here; the keyboard shortcuts (M mute / F11 fullscreen /
//! F10 graphics; V first-person lives in `player::camera`) drive the same helpers directly, so a
//! setting is always reachable without opening any menu. **mute** drives Bevy's audio sinks,
//! **fullscreen** flips the primary window's [`WindowMode`]; a [`Notice`] confirms each change.
//!
//! The only thing this module spawns is a pair of **debug cheat buttons**, and only when
//! `FOREST_CHEATS` is set — they never ship in a normal player HUD.

use bevy::audio::{AudioSink, AudioSinkPlayback, SpatialAudioSink};
use bevy::prelude::*;
use bevy::window::{MonitorSelection, PrimaryWindow, WindowMode};

use crate::economy::Bank;
use crate::player::PlayerRes;
use crate::quality::GraphicsQuality;

use super::fonts::{label, UiFonts};
use super::notice::Notice;
use super::theme::*;
use super::widgets::border;

#[derive(Resource, Default)]
pub struct AudioSettings {
    /// Player's manual mute (M key / the pause-menu **Sound** toggle).
    pub muted: bool,
    /// Background mute: true while the game window isn't focused (CS2-style). Driven by
    /// [`track_window_focus`], kept separate from `muted` so refocusing restores the player's own
    /// mute choice and the pause-menu label never flips on an alt-tab. `sync_mute` ORs the two.
    pub unfocused: bool,
}

/// Debug cheat: grants 1000 of every resource (gold + stone + food + wood) on click.
#[derive(Component)]
struct DebugGrant;
/// Debug cheat: unlocks all five warden boons (the active moves + passives) on click.
#[derive(Component)]
struct DebugBoons;

pub struct SettingsPlugin;
impl Plugin for SettingsPlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<AudioSettings>()
            .add_systems(Startup, setup_cheats)
            .add_systems(Update, (cheat_click, keys, track_window_focus, sync_mute));
    }
}

/// Spawn the dev cheat buttons in the top-right — **only** under `FOREST_CHEATS`, so a normal run
/// has no permanent buttons on screen at all (player settings live in the Esc pause menu).
fn setup_cheats(mut commands: Commands, fonts: Res<UiFonts>) {
    if std::env::var("FOREST_CHEATS").is_err() {
        return;
    }
    let cheat_btn = || {
        (
            Node {
                height: Val::Px(34.0),
                padding: UiRect::horizontal(Val::Px(10.0)),
                align_items: AlignItems::Center,
                justify_content: JustifyContent::Center,
                border: border(1.0),
                border_radius: radius(R_BTN),
                ..default()
            },
            BackgroundColor(PANEL_HUD),
            BorderColor::all(BORDER_SOFT),
            Button,
            Interaction::default(),
        )
    };
    commands
        .spawn((
            Node {
                position_type: PositionType::Absolute,
                top: Val::Px(14.0),
                right: Val::Px(14.0),
                flex_direction: FlexDirection::Row,
                column_gap: Val::Px(8.0),
                ..default()
            },
            GlobalZIndex(91),
        ))
        .with_children(|row| {
            row.spawn((cheat_btn(), DebugGrant)).with_children(|b| {
                b.spawn(label(&fonts.bold, "+1k", 13.0, TEXT));
            });
            row.spawn((cheat_btn(), DebugBoons)).with_children(|b| {
                b.spawn(label(&fonts.bold, "Arts", 13.0, TEXT));
            });
        });
}

/// Handle the two debug cheat buttons (only present under `FOREST_CHEATS`).
fn cheat_click(
    q: Query<(&Interaction, Option<&DebugGrant>, Option<&DebugBoons>), Changed<Interaction>>,
    mut bank: ResMut<Bank>,
    mut player: ResMut<PlayerRes>,
    mut notice: ResMut<Notice>,
    time: Res<Time>,
) {
    let now = time.elapsed_secs_f64();
    for (interaction, grant, boons) in &q {
        if *interaction != Interaction::Pressed {
            continue;
        }
        if grant.is_some() {
            grant_debug_resources(&mut bank, &mut player, &mut notice, now);
        }
        if boons.is_some() {
            grant_all_boons(&mut player, &mut notice, now);
        }
    }
}

/// Debug cheat behind the "Arts" button: unlock every warden boon (Ground Slam, Sand Dash,
/// Bramble Sweep, Frostbite, Venom) so the active moves + passives can be tested instantly.
fn grant_all_boons(player: &mut PlayerRes, notice: &mut Notice, now: f64) {
    let p = &mut player.0;
    p.has_ground_slam = true;
    p.has_sand_dash = true;
    p.has_bramble_sweep = true;
    p.frostbite = true;
    p.venom = true;
    notice.push("Debug: all warden abilities unlocked", now);
}

/// Debug cheat behind the "+1k" button: 1000 gold + 1000 of each bank resource.
fn grant_debug_resources(bank: &mut Bank, player: &mut PlayerRes, notice: &mut Notice, now: f64) {
    bank.0.add_stone(1000.0);
    bank.0.add_food(1000.0);
    bank.0.add_wood(1000.0);
    player.0.add_gold(1000);
    notice.push("Debug: +1000 gold/stone/food/wood", now);
}

/// M = mute, F11 = fullscreen, F10 = graphics preset. (V / first-person lives in `player::camera`.)
fn keys(
    input: Res<ButtonInput<KeyCode>>,
    mut settings: ResMut<AudioSettings>,
    mut quality: ResMut<GraphicsQuality>,
    mut windows: Query<&mut Window, With<PrimaryWindow>>,
    mut notice: ResMut<Notice>,
    time: Res<Time>,
) {
    let now = time.elapsed_secs_f64();
    if input.just_pressed(KeyCode::KeyM) {
        toggle_mute(&mut settings, &mut notice, now);
    }
    if input.just_pressed(KeyCode::F11) {
        toggle_fullscreen(&mut windows, &mut notice, now);
    }
    if input.just_pressed(KeyCode::F10) {
        toggle_quality(&mut quality, &mut notice, now);
    }
}

pub(crate) fn toggle_mute(settings: &mut AudioSettings, notice: &mut Notice, now: f64) {
    settings.muted = !settings.muted;
    // The actual silencing happens in `sync_mute` (live `AudioSink`s) — GlobalVolume alone is
    // only sampled when a sink *starts*, so it never touches already-playing music/ambience.
    notice.push(if settings.muted { "Audio muted" } else { "Audio on" }, now);
}

pub(crate) fn toggle_quality(quality: &mut GraphicsQuality, notice: &mut Notice, now: f64) {
    *quality = quality.next();
    notice.push(format!("Graphics: {}", quality.label()), now);
}

/// CS2-style background mute: silence the game whenever its window loses focus (alt-tabbed, or
/// another app on top), and unmute the moment it's focused again. Writes [`AudioSettings::unfocused`]
/// — `sync_mute` ORs it with the manual `muted` flag — so the player's own mute choice survives a
/// tab-away and the pause-menu label (which tracks only `muted`) doesn't twitch on focus changes.
/// Only writes on an actual change to avoid needless change-detection churn.
fn track_window_focus(
    window: Query<&Window, With<PrimaryWindow>>,
    mut settings: ResMut<AudioSettings>,
) {
    let Ok(window) = window.single() else { return };
    let unfocused = !window.focused;
    if settings.unfocused != unfocused {
        settings.unfocused = unfocused;
    }
}

/// Keep every live audio sink's mute state matching the setting. Bevy's `GlobalVolume` is only
/// read when a sink is created, so muting must be pushed onto the playing sinks here — this also
/// catches sinks that start while muted (they get muted within a frame). `mute()`/`unmute()`
/// remember each sink's real volume, so unmuting restores it exactly.
fn sync_mute(
    settings: Res<AudioSettings>,
    mut sinks: Query<&mut AudioSink>,
    mut spatial: Query<&mut SpatialAudioSink>,
) {
    let want = settings.muted || settings.unfocused;
    for mut s in &mut sinks {
        if s.is_muted() != want {
            if want {
                s.mute();
            } else {
                s.unmute();
            }
        }
    }
    for mut s in &mut spatial {
        if s.is_muted() != want {
            if want {
                s.mute();
            } else {
                s.unmute();
            }
        }
    }
}

pub(crate) fn toggle_fullscreen(
    windows: &mut Query<&mut Window, With<PrimaryWindow>>,
    notice: &mut Notice,
    now: f64,
) {
    let Ok(mut window) = windows.single_mut() else { return };
    let to_full = matches!(window.mode, WindowMode::Windowed);
    window.mode = if to_full {
        WindowMode::BorderlessFullscreen(MonitorSelection::Current)
    } else {
        WindowMode::Windowed
    };
    notice.push(if to_full { "Fullscreen" } else { "Windowed" }, now);
}
