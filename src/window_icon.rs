//! Brands the *running window* (title-bar + Windows taskbar + Alt-Tab) with the Warbell icon.
//!
//! WHY THIS EXISTS — `build.rs` embeds `branding/warbell.ico` into the `.exe` resource section,
//! which brands the **file** icon (Explorer / installer / Add-Remove-Programs). But that is NOT the
//! live window's icon: winit 0.30 registers its window class with `hIcon = 0` / `hIconSm = 0`
//! (verified in `winit-0.30.13/src/platform_impl/windows/{event_loop,window}.rs`), so it never
//! adopts the exe's embedded icon for the window. Result without this module: the taskbar entry of
//! the *running* game showed the generic default icon even though the exe file was branded. (An
//! earlier `build.rs` comment claiming "winit picks up the exe's icon" for the window was wrong.)
//!
//! Fix: decode the branding PNG (compiled into the binary via `include_bytes!`, so there is no
//! runtime file dependency) into RGBA at startup and hand it to winit. The OS rescales the single
//! 256² source for the title-bar / taskbar / Alt-Tab sizes. Cross-platform: correct on Windows +
//! Linux; on macOS `set_window_icon` is a documented no-op (the dock uses the app bundle icon).

use bevy::ecs::system::NonSendMarker;
use bevy::prelude::*;
use bevy::window::PrimaryWindow;
use bevy::winit::WINIT_WINDOWS;

pub struct WindowIconPlugin;

impl Plugin for WindowIconPlugin {
    fn build(&self, app: &mut App) {
        app.add_systems(Update, set_window_icon);
    }
}

/// Apply the icon once the winit window exists. Runs in `Update` (not `Startup`) and retries via the
/// `Local` guard so it is robust to the window not yet being created on the very first frames — once
/// applied (or the image fails to decode) it early-outs to a single cheap branch per frame.
///
/// `NonSendMarker` forces this onto the main thread: `WINIT_WINDOWS` is a thread-local that is only
/// populated on the thread running the winit event loop, so a worker-thread run would see an empty
/// map and silently no-op.
fn set_window_icon(
    _main_thread: NonSendMarker,
    primary: Query<Entity, With<PrimaryWindow>>,
    mut done: Local<bool>,
) {
    if *done {
        return;
    }
    let Ok(entity) = primary.single() else { return };
    WINIT_WINDOWS.with_borrow(|windows| {
        let Some(window) = windows.get_window(entity) else { return };
        match decode_icon() {
            Ok(icon) => window.set_window_icon(Some(icon)),
            Err(e) => warn!("window icon: failed to decode branding PNG: {e}"),
        }
        *done = true; // window was present — applied or gave up; don't keep retrying.
    });
}

/// Decode the embedded branding PNG into a winit RGBA icon.
fn decode_icon() -> Result<winit::window::Icon, String> {
    let png = include_bytes!("../branding/icon256.png");
    let rgba = image::load_from_memory(png).map_err(|e| e.to_string())?.into_rgba8();
    let (w, h) = rgba.dimensions();
    winit::window::Icon::from_rgba(rgba.into_raw(), w, h).map_err(|e| e.to_string())
}
