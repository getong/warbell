//! **Vitals bars** — the one health/stamina bar look shared by the hero HUD, the warden / Warlord
//! boss bars, and (via the same [`super::theme`] palette + [`DamageTrail`] fed into a shader) the
//! world-space enemy bars in `combat_fx`. Matches the realistic look: square-cut, thin, a 1px
//! near-black rim around a 1px muted iron frame, a recessed near-black channel, a gradient fill with
//! a faint lit top edge, and a pale-amber **damage trail** that holds where a blow landed and then
//! drains (the Souls read of how much a hit took).
//!
//! Usage: spawn a [`track`] and, inside it, [`fill`] FIRST (keep its entity) then [`trail`] pointing
//! at it. The owner keeps writing the fill's `Node::width` (a `Val::Percent`) exactly as before;
//! [`drive_vital_trails`] follows that width on its own, so no owner needs trail bookkeeping.

use bevy::prelude::*;
use bevy::ui::{BackgroundGradient, ColorStop, Gradient, LinearGradient};

use super::theme::*;

/// Seconds the trail holds at the pre-hit level before it starts draining.
const TRAIL_HOLD: f32 = 0.5;
/// Drain speed: exponential toward the fill (per s) with a linear floor (fraction of the bar per
/// s), so a big chunk drains briskly and a sliver doesn't crawl in asymptotically.
const TRAIL_EASE: f32 = 4.0;
const TRAIL_FLOOR: f32 = 0.22;
/// Seconds the trail's hot flash takes to settle to [`BAR_TRAIL`].
const TRAIL_FLASH: f32 = 0.3;

/// The delayed-damage ghost's state machine, in bar FRACTIONS (0..1). One implementation for every
/// bar in the game: the UI bars below and the world-space enemy bars (`combat_fx::drive_hp_bars`).
#[derive(Clone, Copy, Debug)]
pub struct DamageTrail {
    /// Fraction the ghost currently reaches (always `>=` the live value).
    pub shown: f32,
    /// The live value last step — a drop marks a fresh blow.
    last: f32,
    hold_until: f32,
    hit_at: f32,
}

impl DamageTrail {
    /// A trail resting at `value` (no ghost).
    pub fn new(value: f32) -> Self {
        DamageTrail { shown: value, last: value, hold_until: 0.0, hit_at: f32::NEG_INFINITY }
    }

    /// Advance one frame toward the live `value`: a drop keeps the ghost where the bar WAS and
    /// (re)starts the hold; after the hold it drains; a heal past the ghost snaps it up.
    pub fn step(&mut self, value: f32, now: f32, dt: f32) {
        if value < self.last - 1.0e-4 {
            self.shown = self.shown.max(self.last);
            self.hold_until = now + TRAIL_HOLD;
            self.hit_at = now;
        }
        self.last = value;
        if value >= self.shown {
            self.shown = value;
        } else if now >= self.hold_until {
            let gap = self.shown - value;
            self.shown = (self.shown - (gap * TRAIL_EASE).max(TRAIL_FLOOR) * dt).max(value);
        }
    }

    /// Hit flash: 1 on the frame a blow lands, easing to 0 over [`TRAIL_FLASH`].
    pub fn flash(&self, now: f32) -> f32 {
        1.0 - ((now - self.hit_at) / TRAIL_FLASH).clamp(0.0, 1.0)
    }
}

/// The bar's track (frame + recessed channel), `w` wide × `h` px tall (frame included). Clips its
/// children so the fill/trail ride inside the frame.
pub fn track(w: Val, h: f32) -> impl Bundle {
    (
        Node {
            width: w,
            height: Val::Px(h),
            border: UiRect::all(Val::Px(1.0)),
            overflow: Overflow::clip(),
            // Centres an in-flow child (the HUD's HP numeral) over the absolute fill / trail.
            align_items: AlignItems::Center,
            justify_content: JustifyContent::Center,
            ..default()
        },
        // The channel: near-black, a breath lighter at the top so it reads recessed, not flat.
        BackgroundGradient(vec![Gradient::Linear(LinearGradient::new(
            std::f32::consts::PI,
            vec![
                ColorStop::new(lighten(BAR_EMPTY, 1.6), Val::Percent(0.0)),
                ColorStop::new(BAR_EMPTY, Val::Percent(100.0)),
            ],
        ))]),
        BorderColor::all(BAR_FRAME),
        // A hairline near-black rim OUTSIDE the frame — separates the bar from snow or night alike.
        Outline::new(Val::Px(1.0), Val::ZERO, BAR_RIM),
    )
}

/// The fill: a full-height absolute gradient (`top` → `bot`, with a faint lit top edge) tagged
/// `marker`, starting at `value` (0..1); the owner drives its width. Drawn above the [`trail`].
/// (Spawn it at the live value: the trail adopts whatever it first sees, so a bar opened on an
/// already-wounded boss must not start full and "drop" into a phantom hit.)
pub fn fill(top: Color, bot: Color, value: f32, marker: impl Bundle) -> impl Bundle {
    (
        Node {
            position_type: PositionType::Absolute,
            left: Val::Px(0.0),
            top: Val::Px(0.0),
            width: Val::Percent(value.clamp(0.0, 1.0) * 100.0),
            height: Val::Percent(100.0),
            ..default()
        },
        BackgroundGradient(vec![Gradient::Linear(LinearGradient::new(
            std::f32::consts::PI,
            vec![
                ColorStop::new(lighten(top, 1.3), Val::Percent(0.0)),
                ColorStop::new(top, Val::Percent(24.0)),
                ColorStop::new(bot, Val::Percent(100.0)),
            ],
        ))]),
        ZIndex(1),
        marker,
    )
}

/// The damage trail behind `fill` (spawn it after the fill, passing the fill's entity).
pub fn trail(fill: Entity) -> impl Bundle {
    (
        Node {
            position_type: PositionType::Absolute,
            left: Val::Px(0.0),
            top: Val::Px(0.0),
            width: Val::Percent(100.0),
            height: Val::Percent(100.0),
            ..default()
        },
        BackgroundColor(BAR_TRAIL),
        ZIndex(0),
        VitalTrail { fill, trail: None },
    )
}

/// Follows a fill node's width with the delayed damage ghost.
#[derive(Component)]
pub struct VitalTrail {
    fill: Entity,
    /// `None` until the first frame snaps it to the fill.
    trail: Option<DamageTrail>,
}

/// Drive every [`VitalTrail`] off its fill's live `Val::Percent` width (see [`DamageTrail`]).
/// Writes the node only when the drawn width / tint actually moves.
pub fn drive_vital_trails(
    time: Res<Time>,
    mut trails: Query<(&mut Node, &mut BackgroundColor, &mut VitalTrail)>,
    fills: Query<&Node, Without<VitalTrail>>,
) {
    let now = time.elapsed_secs();
    let dt = time.delta_secs().min(0.1);
    for (mut node, mut bg, mut vt) in &mut trails {
        let Ok(fill) = fills.get(vt.fill) else { continue };
        let Val::Percent(pct) = fill.width else { continue };
        let value = pct / 100.0;
        let tr = vt.trail.get_or_insert_with(|| DamageTrail::new(value));
        tr.step(value, now, dt);
        let want = Val::Percent(tr.shown * 100.0);
        let col = BAR_TRAIL.mix(&BAR_TRAIL_HOT, tr.flash(now));
        if node.width != want {
            node.width = want;
        }
        if bg.0 != col {
            bg.0 = col;
        }
    }
}

/// `c` scaled brighter in sRGB (clamped) — the lit edge of a gradient.
pub fn lighten(c: Color, k: f32) -> Color {
    let s = c.to_srgba();
    Color::srgba((s.red * k).min(1.0), (s.green * k).min(1.0), (s.blue * k).min(1.0), s.alpha)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn trail_holds_then_drains_to_the_live_value() {
        let mut t = DamageTrail::new(1.0);
        t.step(0.6, 10.0, 0.016); // blow lands
        assert!((t.shown - 1.0).abs() < 1e-6, "holds at the pre-hit level");
        assert!(t.flash(10.0) > 0.99);
        t.step(0.6, 10.0 + TRAIL_HOLD * 0.5, 0.016);
        assert!((t.shown - 1.0).abs() < 1e-6, "still holding mid-hold");
        let mut now = 10.0 + TRAIL_HOLD;
        for _ in 0..240 {
            now += 1.0 / 60.0;
            t.step(0.6, now, 1.0 / 60.0);
        }
        assert!((t.shown - 0.6).abs() < 1e-6, "drained onto the fill");
        assert_eq!(t.flash(now), 0.0);
    }

    #[test]
    fn trail_snaps_up_on_heal_and_restacks_on_combo() {
        let mut t = DamageTrail::new(0.5);
        t.step(0.8, 1.0, 0.016);
        assert!((t.shown - 0.8).abs() < 1e-6, "a heal never leaves a ghost below the fill");
        t.step(0.7, 2.0, 0.016);
        t.step(0.5, 2.2, 0.016); // a second blow inside the hold keeps the FIRST pre-hit level
        assert!((t.shown - 0.8).abs() < 1e-6);
    }
}
