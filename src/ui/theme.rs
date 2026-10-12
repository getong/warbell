//! **UI design system** — the ONE place the game's UI look is defined: palette (incl. semantic
//! good / warn / bad / info tones), type scale, spacing scale, radii, shadows. Every HUD element,
//! panel and menu pulls its colours, sizes and gaps from here so the look stays coherent and is
//! tuned in one place. Paint bundles built on these tokens live in [`super::widgets`].
//!
//! **Design language — "iron & parchment".** Grounded, muted, medieval: warm dark-iron translucent
//! panels with a thin bronze hairline; warm parchment-white text (never cool screen-white); ONE
//! restrained antique-gold accent for titles/currency/focus; state colours desaturated toward the
//! world's earth tones (sage, ochre, brick, steel) — nothing neon. Cinzel for headings, Inter for
//! body/numerals, EB Garamond for parchment prose (all OFL, bundled in `assets/fonts`). Spacing on
//! a 4px grid ([`SP_XS`]..[`SP_XXL`]). Motion is subtle: short fades/slides (`super::anim`).
//!
//! Construction note: colours are `const` via the [`Color::Srgba`] struct-literal form (the
//! `Color::srgb*` helpers aren't all `const`), so they can live as associated constants.

use bevy::color::Srgba;
use bevy::prelude::*;
use bevy::ui::{BorderRadius, BoxShadow, ShadowStyle, Val};

/// sRGB colour from 0-255 channel bytes + alpha float — `const`-friendly.
pub const fn rgba(r: u8, g: u8, b: u8, a: f32) -> Color {
    Color::Srgba(Srgba {
        red: r as f32 / 255.0,
        green: g as f32 / 255.0,
        blue: b as f32 / 255.0,
        alpha: a,
    })
}
/// Opaque sRGB colour from 0-255 channel bytes.
pub const fn rgb(r: u8, g: u8, b: u8) -> Color {
    rgba(r, g, b, 1.0)
}

// ── Palette (from hud.css) ───────────────────────────────────────────────────────────────
pub const GOLD: Color = rgb(226, 196, 138); // antique gold — currency, titles, the one accent
pub const GOLD_DEEP: Color = rgb(190, 146, 76); // tarnished bronze-gold — button gradient base
pub const STONE: Color = rgb(196, 196, 190); // stone tally
pub const WOOD: Color = rgb(184, 148, 102); // wood tally
pub const GREEN: Color = rgb(146, 178, 118); // dry sage — buffs / success / toast accent
pub const GREY: Color = rgb(140, 135, 126); // warm ash — labels, disabled, hints
pub const RED: Color = rgb(176, 64, 50); // brick — danger
pub const TEXT: Color = rgb(236, 229, 214); // warm parchment-white — body
pub const TEXT_DIM: Color = rgb(190, 181, 164); // secondary
pub const TEXT_FAINT: Color = rgb(146, 138, 124); // tertiary

// ── Semantic tones — use these for state, not raw RGB (all desaturated earth tones) ───────
/// Positive / gain / ready (sage).
pub const GOOD: Color = GREEN;
/// Caution / blocked-but-not-bad / attention (ochre).
pub const WARN: Color = rgb(204, 160, 84);
/// Loss / danger / damage taken (brick).
pub const BAD: Color = rgb(196, 92, 72);
/// Neutral information / defensive (pale steel).
pub const INFO: Color = rgb(170, 182, 194);
/// Drop shadow behind HUD text drawn straight over the world (subtitles, floats, prompts).
pub const TEXT_SHADOW: Color = rgba(8, 6, 4, 0.85);

// Panels / chrome — warm iron/charcoal-brown, not web blue-grey. The signature frame is
// outer 2px IRON_EDGE + inner 1px GOLD_HAIRLINE + 6px corner notches (see `widgets::chrome_layers`).
pub const PANEL: Color = rgba(30, 24, 18, 0.96); // modal card bg (warm iron)
pub const PANEL_HUD: Color = rgba(27, 22, 16, 0.84); // persistent-HUD chrome bg
pub const SCRIM: Color = rgba(12, 9, 6, 0.66); // modal backdrop (warm-dark)
pub const IRON_EDGE: Color = rgba(9, 7, 5, 0.92); // outer frame border
pub const GOLD_HAIRLINE: Color = rgba(224, 168, 74, 0.34); // inner frame hairline
pub const GOLD_NOTCH: Color = rgba(224, 168, 74, 0.58); // corner notch squares
pub const BORDER_SOFT: Color = rgba(224, 184, 120, 0.14);
pub const BTN_BG: Color = rgba(232, 196, 130, 0.05);
pub const BTN_BG_HOVER: Color = rgba(232, 196, 130, 0.11);

// Slots / cells
pub const SLOT_BG: Color = rgba(146, 122, 86, 0.14);
pub const SLOT_BORDER: Color = rgba(98, 78, 50, 0.9);
pub const SLOT_BORDER_HOVER: Color = rgba(216, 178, 114, 0.95);

// Bars — the VITALS palette, shared by the hero HUD, the boss bars, the FP reticle bar AND the
// world-space enemy bars (`combat_fx`, which feeds these into its shader), so every health bar in
// the game reads as one family. Deliberately muted (no flat primaries): the old #d63a3a / cyan
// candy bars looked like a mobile game next to the realistic forest. Blood is a deep, slightly
// brown crimson with a soft top→bottom gradient; stamina a dry sage; XP a dim bronze thread.
pub const HP_TOP: Color = rgb(150, 30, 24); // deep blood (lit top of the tube)
pub const HP_BOT: Color = rgb(92, 14, 12); // clotted crimson (bottom)
pub const XP_TOP: Color = rgb(184, 146, 82); // dim bronze
pub const XP_BOT: Color = rgb(122, 92, 46);
pub const STAM_TOP: Color = rgb(128, 146, 100); // dry sage
pub const STAM_BOT: Color = rgb(78, 94, 58);
/// Delayed-damage "trail" ghost behind a health fill (the Souls read of how much a blow took):
/// a pale, desaturated amber — reads clearly against the blood without being a warning orange.
pub const BAR_TRAIL: Color = rgb(186, 152, 104);
/// The trail on the frame a blow lands (eases to [`BAR_TRAIL`]).
pub const BAR_TRAIL_HOT: Color = rgb(236, 214, 170);
/// Drained channel behind every vitals fill — near-black warm iron, a recessed slot.
pub const BAR_EMPTY: Color = rgb(16, 13, 11);
/// The 1px frame line around a vitals bar (muted iron-bronze) and the hairline near-black rim
/// outside it that separates the bar from any background.
pub const BAR_FRAME: Color = rgb(98, 84, 64);
pub const BAR_RIM: Color = rgba(6, 5, 4, 0.92);

// Primary action button (Play / Resume) — bronze-gold, dark text (`INK`).
pub const PRIMARY: Color = rgb(196, 144, 62); // bronze base
pub const PRIMARY_HI: Color = rgb(222, 170, 84); // hover
pub const PRIMARY_BORDER: Color = rgb(222, 186, 124);

// Cool accent — muted steel (was a web-blue #4a6fc8; nothing in the world is that blue).
pub const BLUE: Color = rgb(92, 112, 138);
pub const BLUE_HI: Color = rgb(114, 134, 160);
pub const BLUE_BORDER: Color = rgb(146, 162, 184);

// Danger action button (Overwrite save / destructive confirms)
pub const RED_HI: Color = rgb(196, 84, 66); // hover
pub const RED_BORDER: Color = rgb(214, 124, 102);

// Start-screen warm accent
pub const KICKER: Color = rgb(199, 155, 106); // #c79b6a

// Upgrade-tree parchment board
pub const PARCHMENT: Color = rgb(231, 216, 176); // #e7d8b0
pub const INK: Color = rgb(36, 27, 12); // #241b0c
pub const INK_SOFT: Color = rgb(90, 69, 36); // #5a4524
pub const BRANCH_ECON: Color = rgb(92, 122, 52); // #5c7a34
pub const BRANCH_DEF: Color = rgb(76, 100, 126); // #4c647e
pub const BRANCH_HERO: Color = rgb(142, 55, 44); // #8e372c
pub const BRANCH_ARSENAL: Color = rgb(138, 94, 42); // #8a5e2a

// ── Type scale (re-exported from `fonts`, so one `use theme::*` brings every token) ───────
#[allow(unused_imports)]
pub use super::fonts::{FONT_BODY, FONT_CAPTION, FONT_DISPLAY, FONT_LABEL};
/// Panel / card headings (Cinzel).
pub const FONT_TITLE: f32 = 20.0;
/// Large on-world numerals (resource counters, big stat values).
pub const FONT_STAT: f32 = 15.0;

// ── Spacing scale (4px grid) — paddings, gaps, margins ──────────────────────────────────
pub const SP_XS: f32 = 4.0;
pub const SP_S: f32 = 8.0;
pub const SP_M: f32 = 12.0;
pub const SP_L: f32 = 16.0;
pub const SP_XL: f32 = 24.0;
pub const SP_XXL: f32 = 32.0;
/// Inset of every persistent HUD cluster from the screen edge.
pub const HUD_EDGE: f32 = 16.0;

// ── Shapes ───────────────────────────────────────────────────────────────────────────────
pub const R_PANEL: f32 = 10.0;
pub const R_CARD: f32 = 8.0;
pub const R_BTN: f32 = 6.0;
pub const R_CELL: f32 = 4.0;
pub const R_SLOT: f32 = 3.0;

pub fn radius(px: f32) -> BorderRadius {
    BorderRadius::all(Val::Px(px))
}

/// The standard modal-card drop shadow (`0 16px 40px rgba(0,0,0,0.55)`).
pub fn shadow_card() -> BoxShadow {
    BoxShadow(vec![ShadowStyle {
        color: rgba(0, 0, 0, 0.55),
        x_offset: Val::Px(0.0),
        y_offset: Val::Px(16.0),
        spread_radius: Val::Px(0.0),
        blur_radius: Val::Px(40.0),
    }])
}

/// The lighter HUD-chrome shadow (`0 8px 30px rgba(0,0,0,0.35)`).
pub fn shadow_hud() -> BoxShadow {
    BoxShadow(vec![ShadowStyle {
        color: rgba(0, 0, 0, 0.35),
        x_offset: Val::Px(0.0),
        y_offset: Val::Px(8.0),
        spread_radius: Val::Px(0.0),
        blur_radius: Val::Px(30.0),
    }])
}
