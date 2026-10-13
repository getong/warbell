//! On-screen subtitles for spoken lines. A single bottom-centre caption shows what a nearby
//! character just said (villagers today; the [`Subtitles`] resource is public so the hero/ork
//! voices can push to it later). The line fades out on its own — set it and forget it.
//!
//! Speakers write the text + a display duration via [`Subtitles::say`]; the UI system below mirrors
//! the resource into one persistent `Text` node, fading the last stretch out. A voice heard through
//! bars (the caged captives) uses [`Subtitles::say_muffled`] instead: a smaller, dimmer aside that
//! only ever fills an EMPTY caption slot — it never replaces a real line still on screen.

use bevy::prelude::*;

use crate::ui::theme::*;
use crate::ui::{label, UiFonts};

/// Caption size (px) of an ordinary line, and of a muffled aside.
const SIZE: f32 = 19.0;
const MUFFLED_SIZE: f32 = 16.5;

/// The currently-shown caption. A speaker calls [`Subtitles::say`]; the latest line wins.
#[derive(Resource, Default)]
pub struct Subtitles {
    text: String,
    /// `elapsed_secs` at which the caption should be gone.
    until: f32,
    /// Demo/clip override: once locked, ambient `say`/`say_as` calls are ignored so a scripted
    /// caption (`force`) can't be clobbered by the audio director's barks. Never set in play.
    locked: bool,
    /// The caption is a muffled aside ([`Subtitles::say_muffled`]) — drawn dimmer and smaller.
    muffled: bool,
}

impl Subtitles {
    /// Show `text` for `dur` seconds (from `now = time.elapsed_secs()`).
    pub fn say(&mut self, now: f32, text: &str, dur: f32) {
        self.say_as(now, None, text, dur);
    }
    /// Show `text` attributed to `speaker` (renders "Name: text"); `None` = no prefix (the hero).
    pub fn say_as(&mut self, now: f32, speaker: Option<&str>, text: &str, dur: f32) {
        if self.locked {
            return;
        }
        self.set(now, speaker, text, dur);
    }
    /// A MUFFLED aside (a captive behind bars): shown only if no ordinary caption is still up —
    /// it never clobbers a story line — and drawn smaller and dimmer. Spoken words read
    /// "Captive (muffled): …"; a sound caption (`*muffled sobbing*`) stands on its own.
    pub fn say_muffled(&mut self, now: f32, speaker: Option<&str>, text: &str, dur: f32) {
        if self.locked || (now < self.until && !self.muffled) {
            return;
        }
        let sound = text.starts_with('*');
        self.text = match speaker {
            Some(name) if !sound => format!("{name} (muffled): {text}"),
            _ => text.to_string(),
        };
        self.until = now + dur;
        self.muffled = true;
    }
    /// Clip-only: pin a caption that ambient speakers can't override (locks the resource).
    pub fn force(&mut self, now: f32, speaker: Option<&str>, text: &str, dur: f32) {
        self.locked = true;
        self.set(now, speaker, text, dur);
    }
    /// Hand the caption back to ambient speakers (a staged scene is done with its [`force`](Self::force) pin).
    pub fn release(&mut self) {
        self.locked = false;
    }
    /// Is the current caption a muffled aside? (Test probe — the UI reads the field directly.)
    #[cfg(test)]
    pub fn is_muffled(&self) -> bool {
        self.muffled
    }
    fn set(&mut self, now: f32, speaker: Option<&str>, text: &str, dur: f32) {
        self.text = match speaker {
            Some(name) => format!("{name}: {text}"),
            None => text.to_string(),
        };
        self.until = now + dur;
        self.muffled = false;
    }
}

/// A sensible on-screen reading time for a caption: a base plus ~14 chars/sec, clamped so a
/// one-word quip still lingers and a long story doesn't overstay.
pub fn read_secs(text: &str) -> f32 {
    (1.6 + text.chars().count() as f32 / 14.0).clamp(2.5, 8.0)
}

/// The full-width caption row (repositioned above the build palette while it's open).
#[derive(Component)]
pub(crate) struct SubtitleRow;
/// The caption plate (soft dark band behind the line — fades with it).
#[derive(Component)]
struct SubtitlePlate;
/// The speaker-name span ("Townsfolk") — antique gold, so who's talking reads at a glance.
#[derive(Component)]
struct SubtitleSpeaker;
/// The spoken-line span — warm parchment-white.
#[derive(Component)]
struct SubtitleLine;

pub struct SubtitlePlugin;

impl Plugin for SubtitlePlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<Subtitles>()
            .add_systems(Startup, setup)
            .add_systems(Update, update);
    }
}

fn setup(mut commands: Commands, fonts: Res<UiFonts>) {
    commands
        .spawn((
            Node {
                position_type: PositionType::Absolute,
                bottom: Val::Percent(14.0),
                width: Val::Percent(100.0),
                justify_content: JustifyContent::Center,
                ..default()
            },
            GlobalZIndex(40),
            SubtitleRow,
        ))
        .with_children(|p| {
            // A soft, borderless dark band (the film-subtitle read): legible over bright snow or
            // sky without a hard UI box. Invisible until a line is up.
            p.spawn((
                Node {
                    max_width: Val::Px(780.0),
                    padding: UiRect::axes(Val::Px(SP_L), Val::Px(SP_XS + 2.0)),
                    border_radius: radius(R_CARD),
                    ..default()
                },
                BackgroundColor(Color::NONE),
                SubtitlePlate,
            ))
            .with_children(|plate| {
                plate
                    .spawn((
                        label(&fonts.semibold, "", SIZE, Color::NONE),
                        TextShadow { offset: Vec2::splat(1.5), color: TEXT_SHADOW },
                        TextLayout { justify: Justify::Center, ..default() },
                    ))
                    .with_children(|t| {
                        t.spawn((
                            TextSpan::new(""),
                            TextFont { font: fonts.semibold.clone().into(), font_size: SIZE.into(), ..default() },
                            TextColor(Color::NONE),
                            SubtitleSpeaker,
                        ));
                        t.spawn((
                            TextSpan::new(""),
                            TextFont { font: fonts.regular.clone().into(), font_size: SIZE.into(), ..default() },
                            TextColor(Color::NONE),
                            SubtitleLine,
                        ));
                    });
            });
        });
}

/// Split a caption into its "Speaker: " prefix (if it has one) and the spoken line. Only a short,
/// name-like prefix counts, so a line that merely contains a colon isn't split mid-sentence.
fn split_speaker(text: &str) -> (&str, &str) {
    if let Some(i) = text.find(": ") {
        let head = &text[..i];
        if !head.is_empty() && head.chars().count() <= 28 && !head.contains(['.', '!', '?', '*']) {
            return (&text[..i + 2], &text[i + 2..]);
        }
    }
    ("", text)
}

#[allow(clippy::type_complexity)]
fn update(
    time: Res<Time>,
    subs: Res<Subtitles>,
    fonts: Res<UiFonts>,
    mut plate: Query<&mut BackgroundColor, With<SubtitlePlate>>,
    mut speaker: Query<(&mut TextSpan, &mut TextColor, &mut TextFont), (With<SubtitleSpeaker>, Without<SubtitleLine>)>,
    mut line: Query<(&mut TextSpan, &mut TextColor, &mut TextFont), (With<SubtitleLine>, Without<SubtitleSpeaker>)>,
    mut shown: Local<String>,
    build: Option<Res<crate::town::BuildMode>>,
    mut row: Query<&mut Node, With<SubtitleRow>>,
) {
    // Lift the caption clear of the bottom build palette while it's open (it would sit under it).
    let lifted = build.is_some_and(|b| b.active);
    if let Ok(mut n) = row.single_mut() {
        let want = if lifted { Val::Px(262.0) } else { Val::Percent(14.0) };
        if n.bottom != want {
            n.bottom = want;
        }
    }
    let (Ok(mut bg), Ok((mut sp, mut sp_col, mut sp_font)), Ok((mut ln, mut ln_col, mut ln_font))) =
        (plate.single_mut(), speaker.single_mut(), line.single_mut())
    else {
        return;
    };
    let remaining = subs.until - time.elapsed_secs();
    if remaining <= 0.0 {
        if !shown.is_empty() {
            shown.clear();
            sp.0.clear();
            ln.0.clear();
            sp_col.0 = Color::NONE;
            ln_col.0 = Color::NONE;
            bg.0 = Color::NONE;
        }
        return;
    }
    if *shown != subs.text {
        *shown = subs.text.clone();
        let (who, said) = split_speaker(&subs.text);
        sp.0 = who.to_string();
        ln.0 = said.to_string();
        // Restyle only when the caption changes: a muffled aside in the lighter face, smaller.
        let size = if subs.muffled { MUFFLED_SIZE } else { SIZE };
        *sp_font = TextFont { font: fonts.semibold.clone().into(), font_size: size.into(), ..default() };
        let face = if subs.muffled { &fonts.regular } else { &fonts.semibold };
        *ln_font = TextFont { font: face.clone().into(), font_size: size.into(), ..default() };
    }
    // Fade the final 0.6s out so lines don't pop off.
    let a = (remaining / 0.6).min(1.0);
    let k = if subs.muffled { 0.8 } else { 1.0 };
    sp_col.0 = GOLD.with_alpha(a * k);
    ln_col.0 = if subs.muffled { TEXT_DIM.with_alpha(a * k) } else { TEXT.with_alpha(a) };
    bg.0 = SUBTITLE_PLATE.with_alpha(SUBTITLE_PLATE.alpha() * a);
}

/// The caption plate tint — the HUD chrome's warm iron, kept faint (it's a reading aid, not a box).
const SUBTITLE_PLATE: Color = rgba(14, 11, 8, 0.46);

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_muffled_aside_never_clobbers_a_real_caption() {
        let mut s = Subtitles::default();
        s.say_as(0.0, Some("Townsfolk"), "Rain or orcs. Always something.", 3.0);
        s.say_muffled(1.0, Some("Captive"), "Gods… help…", 2.0);
        assert_eq!(s.text, "Townsfolk: Rain or orcs. Always something.");
        assert!(!s.is_muffled());
        // Once the real line has gone, the aside shows — tagged, or as a bare sound caption.
        s.say_muffled(3.5, Some("Captive"), "Gods… help…", 2.0);
        assert_eq!(s.text, "Captive (muffled): Gods… help…");
        assert!(s.is_muffled());
        s.say_muffled(4.0, Some("Captive"), "*muffled sobbing*", 2.0);
        assert_eq!(s.text, "*muffled sobbing*");
        // A real line always replaces an aside.
        s.say_as(4.5, None, "Down it goes.", 2.0);
        assert_eq!(s.text, "Down it goes.");
        assert!(!s.is_muffled());
    }

    #[test]
    fn a_forced_caption_holds_against_asides_too() {
        let mut s = Subtitles::default();
        s.force(0.0, None, "scripted", 1.0);
        s.say_muffled(5.0, Some("Captive"), "*coughing*", 2.0);
        assert_eq!(s.text, "scripted");
    }
}
