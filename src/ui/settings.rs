//! **Settings** — the always-visible top-right toggles ported from the 3js `AudioToggle` /
//! `SettingsPanel`. Two icon buttons with real backing: **mute** drives Bevy's [`GlobalVolume`],
//! **fullscreen** flips the primary window's [`WindowMode`]. Each is also reachable from the keyboard
//! (M / F11) and a [`Notice`] confirms the change.

use bevy::audio::{GlobalVolume, Volume};
use bevy::prelude::*;
use bevy::window::{MonitorSelection, PrimaryWindow, WindowMode};

use super::fonts::UiFonts;
use super::icons::IconAtlas;
use super::notice::Notice;
use super::theme::*;
use super::widgets::{self, border};

#[derive(Resource, Default)]
pub struct AudioSettings {
    pub muted: bool,
}

#[derive(Component)]
struct AudioToggle;
#[derive(Component)]
struct AudioIcon;
#[derive(Component)]
struct FullscreenToggle;
#[derive(Component)]
struct FsIcon;

pub struct SettingsPlugin;
impl Plugin for SettingsPlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<AudioSettings>()
            .add_systems(Startup, setup_settings)
            .add_systems(Update, (settings_click, keys, sync_audio_icon));
    }
}

fn setup_settings(mut commands: Commands, _fonts: Res<UiFonts>) {
    commands
        .spawn(Node {
            position_type: PositionType::Absolute,
            top: Val::Px(14.0),
            right: Val::Px(14.0),
            flex_direction: FlexDirection::Row,
            column_gap: Val::Px(8.0),
            ..default()
        })
        .with_children(|row| {
            for marker in [0u8, 1] {
                let mut e = row.spawn((
                    Node {
                        width: Val::Px(34.0),
                        height: Val::Px(34.0),
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
                ));
                if marker == 0 {
                    e.insert(AudioToggle).with_children(|b| {
                        b.spawn((Node { width: Val::Px(18.0), height: Val::Px(18.0), ..default() }, ImageNode::new(Handle::default()), AudioIcon));
                    });
                } else {
                    e.insert(FullscreenToggle).with_children(|b| {
                        b.spawn((Node { width: Val::Px(18.0), height: Val::Px(18.0), ..default() }, ImageNode::new(Handle::default()), FsIcon));
                    });
                }
            }
        });
}

/// Keep the fullscreen button's icon set, and the audio button's icon in sync with the mute state
/// (also covers the startup race where the icon atlas isn't ready when the buttons spawn).
fn sync_audio_icon(
    settings: Res<AudioSettings>,
    atlas: Res<IconAtlas>,
    mut audio_q: Query<&mut ImageNode, (With<AudioIcon>, Without<FsIcon>)>,
    mut fs_q: Query<&mut ImageNode, (With<FsIcon>, Without<AudioIcon>)>,
) {
    let key = if settings.muted { "sym:audio_off" } else { "sym:audio_on" };
    if let (Ok(mut img), Some(h)) = (audio_q.single_mut(), atlas.get(key)) {
        if img.image != h {
            img.image = h;
        }
    }
    if let (Ok(mut img), Some(h)) = (fs_q.single_mut(), atlas.get("sym:fullscreen")) {
        if img.image != h {
            img.image = h;
        }
    }
}

#[allow(clippy::type_complexity)]
fn settings_click(
    q: Query<(&Interaction, Option<&AudioToggle>, Option<&FullscreenToggle>), Changed<Interaction>>,
    mut settings: ResMut<AudioSettings>,
    mut volume: ResMut<GlobalVolume>,
    mut windows: Query<&mut Window, With<PrimaryWindow>>,
    mut notice: ResMut<Notice>,
    time: Res<Time>,
) {
    let now = time.elapsed_secs_f64();
    for (interaction, audio, fs) in &q {
        if *interaction != Interaction::Pressed {
            continue;
        }
        if audio.is_some() {
            toggle_mute(&mut settings, &mut volume, &mut notice, now);
        }
        if fs.is_some() {
            toggle_fullscreen(&mut windows, &mut notice, now);
        }
    }
}

/// M = mute, F11 = fullscreen.
fn keys(
    input: Res<ButtonInput<KeyCode>>,
    mut settings: ResMut<AudioSettings>,
    mut volume: ResMut<GlobalVolume>,
    mut windows: Query<&mut Window, With<PrimaryWindow>>,
    mut notice: ResMut<Notice>,
    time: Res<Time>,
) {
    let now = time.elapsed_secs_f64();
    if input.just_pressed(KeyCode::KeyM) {
        toggle_mute(&mut settings, &mut volume, &mut notice, now);
    }
    if input.just_pressed(KeyCode::F11) {
        toggle_fullscreen(&mut windows, &mut notice, now);
    }
}

fn toggle_mute(
    settings: &mut AudioSettings,
    volume: &mut GlobalVolume,
    notice: &mut Notice,
    now: f64,
) {
    settings.muted = !settings.muted;
    volume.volume = Volume::Linear(if settings.muted { 0.0 } else { 1.0 });
    notice.push(if settings.muted { "Audio muted" } else { "Audio on" }, now);
}

fn toggle_fullscreen(
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
