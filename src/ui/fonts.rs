//! **Fonts.** Inter (weights 400/600/700/800) for body/numerals — readability first — plus two
//! display faces for the medieval chrome: **Cinzel** (OFL, Trajan-style roman capitals) for
//! titles/headers, and **EB Garamond** (OFL serif) for parchment body text. Bevy's `TextFont`
//! selects a face by `Handle<Font>` (no weight axis), so each weight is a separate file.

use bevy::prelude::*;

/// Loaded font faces, indexed by the weights the UI actually uses.
#[derive(Resource, Clone)]
pub struct UiFonts {
    pub regular: Handle<Font>,  // 400
    pub semibold: Handle<Font>, // 600
    pub bold: Handle<Font>,     // 700
    pub extrabold: Handle<Font>, // 800
    pub serif: Handle<Font>,    // EB Garamond — parchment body text
    pub display: Handle<Font>,  // Cinzel — titles, headers, banners
}

impl UiFonts {
    pub fn load(assets: &AssetServer) -> Self {
        Self {
            regular: assets.load("fonts/Inter-Regular.ttf"),
            semibold: assets.load("fonts/Inter-SemiBold.ttf"),
            bold: assets.load("fonts/Inter-Bold.ttf"),
            extrabold: assets.load("fonts/Inter-ExtraBold.ttf"),
            serif: assets.load("fonts/EBGaramond.ttf"),
            display: assets.load("fonts/Cinzel.ttf"),
        }
    }
}

/// **HUD type scale.** Prefer these named sizes over ad-hoc numbers so text stays consistent across
/// the HUD (Inter for body/numerals via `regular`/`semibold`/`bold`; Cinzel `display` for the big
/// medieval headers). Roughly: caption = pips / compass letters / fine print; body = counters and
/// secondary text; label = buttons, menu rows, prompts; display = the large Cinzel titles (PAUSED,
/// screen banners). New HUD text should reach for one of these; the remaining ad-hoc sizes across
/// the older HUD files are a follow-up sweep.
pub const FONT_CAPTION: f32 = 11.0;
pub const FONT_BODY: f32 = 13.0;
pub const FONT_LABEL: f32 = 16.0;
pub const FONT_DISPLAY: f32 = 34.0;

/// A text bundle in a chosen face/size/colour. `font` is one of the `UiFonts` handles, cloned.
pub fn label(font: &Handle<Font>, s: impl Into<String>, size: f32, color: Color) -> impl Bundle {
    (
        Text::new(s),
        TextFont { font: font.clone(), font_size: size, ..default() },
        TextColor(color),
    )
}
