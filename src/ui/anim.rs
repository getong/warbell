//! **UI motion** — ports the three.js entrance keyframes (pop-in / slide-down / rise / float-up /
//! toast-in) and hover feedback onto `bevy_ui` via the post-layout [`UiTransform`] component.
//! [`UiAnim`] is a self-removing tween: attach it (with its matching start transform from
//! [`anim`]) and it eases to identity over its lifetime, then deletes itself.

use bevy::prelude::*;
use bevy::ui::{UiTransform, Val2};

/// Which entrance curve a node plays.
#[derive(Clone, Copy, PartialEq)]
pub enum AnimKind {
    /// Scale .82 → 1 with a slight overshoot (modal cards, victory title).
    PopIn,
    /// Translate down from −14px (objective banner).
    SlideDown,
    /// Translate up from +10px (start-screen menu items; stagger via `delay`).
    Rise,
    /// Translate up from +8px (game-over stats/buttons).
    FloatUp,
    /// Translate in from −20px on X (pickup toasts).
    ToastIn,
}

/// A running entrance tween. Removes itself (leaving an identity transform) when finished.
#[derive(Component)]
pub struct UiAnim {
    pub kind: AnimKind,
    pub delay: f32,
    pub dur: f32,
    pub elapsed: f32,
}

/// `(UiAnim, UiTransform)` bundle: the tween plus the *start* transform (so there's no first-frame
/// flash before the system runs). Use on plain nodes that don't otherwise carry a `UiTransform`.
pub fn anim(kind: AnimKind, delay: f32, dur: f32) -> (UiAnim, UiTransform) {
    (UiAnim { kind, delay, dur, elapsed: 0.0 }, transform_at(kind, 0.0))
}

/// Just the [`UiAnim`] — for nodes that already have a `UiTransform` (e.g. anything built from a
/// `*_paint()` button kit), so the bundle doesn't carry two `UiTransform`s.
pub fn anim_btn(kind: AnimKind, delay: f32, dur: f32) -> UiAnim {
    UiAnim { kind, delay, dur, elapsed: 0.0 }
}

fn ease_out_cubic(t: f32) -> f32 {
    1.0 - (1.0 - t).powi(3)
}
fn ease_out_back(t: f32) -> f32 {
    let c1 = 1.70158;
    let c3 = c1 + 1.0;
    1.0 + c3 * (t - 1.0).powi(3) + c1 * (t - 1.0).powi(2)
}

/// The transform for a given kind at normalised progress `p` (0 = start, 1 = settled).
fn transform_at(kind: AnimKind, p: f32) -> UiTransform {
    let mut tr = UiTransform::IDENTITY;
    match kind {
        AnimKind::PopIn => {
            let s = 0.82 + (1.0 - 0.82) * ease_out_back(p);
            tr.scale = Vec2::splat(s);
        }
        AnimKind::SlideDown => tr.translation = Val2::px(0.0, -14.0 * (1.0 - ease_out_cubic(p))),
        AnimKind::Rise => tr.translation = Val2::px(0.0, 10.0 * (1.0 - ease_out_cubic(p))),
        AnimKind::FloatUp => tr.translation = Val2::px(0.0, 8.0 * (1.0 - ease_out_cubic(p))),
        AnimKind::ToastIn => tr.translation = Val2::px(-20.0 * (1.0 - ease_out_cubic(p)), 0.0),
    }
    tr
}

fn drive_ui_anim(
    time: Res<Time>,
    mut commands: Commands,
    mut q: Query<(Entity, &mut UiAnim, &mut UiTransform)>,
) {
    let dt = time.delta_secs();
    for (e, mut a, mut tr) in &mut q {
        a.elapsed += dt;
        let p = ((a.elapsed - a.delay) / a.dur.max(0.0001)).clamp(0.0, 1.0);
        *tr = transform_at(a.kind, p);
        if a.elapsed >= a.delay + a.dur {
            *tr = UiTransform::IDENTITY;
            commands.entity(e).remove::<UiAnim>();
        }
    }
}

/// Hover/press feedback for a clickable node. `rest`/`hover` colours snap on state change; `lift`
/// raises the node by N px while hovered (CSS `translateY(-Npx)`).
#[derive(Component, Clone)]
pub struct Hoverable {
    pub rest_bg: Color,
    pub hover_bg: Color,
    pub rest_border: Color,
    pub hover_border: Color,
    pub lift: f32,
}

#[allow(clippy::type_complexity)]
fn drive_hover(
    mut q: Query<
        (&Interaction, &Hoverable, &mut BackgroundColor, &mut BorderColor, &mut UiTransform),
        Changed<Interaction>,
    >,
) {
    for (interaction, h, mut bg, mut border, mut tr) in &mut q {
        let on = !matches!(interaction, Interaction::None);
        bg.0 = if on { h.hover_bg } else { h.rest_bg };
        *border = BorderColor::all(if on { h.hover_border } else { h.rest_border });
        tr.translation = Val2::px(0.0, if on { -h.lift } else { 0.0 });
    }
}

pub struct AnimPlugin;
impl Plugin for AnimPlugin {
    fn build(&self, app: &mut App) {
        app.add_systems(Update, (drive_ui_anim, drive_hover));
    }
}
