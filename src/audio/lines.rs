//! Bevy-free voice-line catalog + pure resolver. Every spoken line in the game is one [`Line`]
//! entry here: its speaker, transcript (the on-screen subtitle AND our in-code record of the
//! quote, per CLAUDE.md), whether it can be cut off, its barge-in priority, and optional reply
//! chains. The Bevy glue that actually plays clips lives in `director.rs`; this module is pure
//! data + decision logic so it can be unit-tested without spinning up an App.
//!
//! Model is the Valve "dynamic dialog" bark scheme (see
//! `docs/superpowers/plans/2026-06-09-voice-line-catalog-refactor.md`): a concept fires, the
//! resolver gathers candidate lines for it, filters by a per-line replay floor, and picks one.

use crate::biome::Biome;

/// Who owns a line — selects voice routing (head-locked vs spatial) via [`SPEAKERS`].
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum Speaker {
    Hero,
    Villager,
    Ork,
}

/// How a speaker's voice is routed. Looked up from [`SPEAKERS`] by the director.
#[derive(Clone, Copy)]
pub struct SpeakerVoice {
    /// Head-locked (hero) vs world-positioned (villager/ork).
    pub spatial: bool,
    /// Base gain multiplier (× `AudioConfig.voice_vol`).
    pub gain: f32,
    /// Display name shown in the subtitle (`None` = no prefix, e.g. the hero's own musings).
    pub name: Option<&'static str>,
}

/// The voice registry: one entry per [`Speaker`]. Linear-scanned (3 entries).
pub const SPEAKERS: &[(Speaker, SpeakerVoice)] = &[
    (Speaker::Hero, SpeakerVoice { spatial: false, gain: 1.0, name: None }),
    (Speaker::Villager, SpeakerVoice { spatial: true, gain: 1.4, name: Some("Townsfolk") }),
    (Speaker::Ork, SpeakerVoice { spatial: true, gain: 0.85, name: None }),
];

pub fn speaker_voice(s: Speaker) -> SpeakerVoice {
    SPEAKERS.iter().find(|(k, _)| *k == s).map(|(_, v)| *v).expect("every Speaker is registered")
}

/// A situation that asks for a line. Triggers (`detect_*` systems) emit one of these; the
/// resolver maps it to candidate [`Line`]s. Biome musings carry the biome so one concept covers
/// all five. The `Reply*` variants are chain targets dispatched by a finished line's `then`.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Concept {
    // ── Hero event reactions (was `HeroEvent`) ──
    FirstStone,
    ChestOpen,
    FirstRescue,
    NightWarning,
    LowHp,
    Home,
    Equip,
    LevelUp,
    WaveSurvived,
    FirstKill,
    GoldRich,
    Broke,
    KeepHurt,
    ShrineHeal,
    // ── Hero biome musing (was `HeroLine(Biome)`) ──
    BiomeEntered(Biome),
    // ── Hero observational remarks (was `Trig`) ──
    Intro,
    NearTown,
    NearKids,
    NearPet,
    NearGuard,
    InKeep,
    NightMusing,
    QuietMusing,
    KillMusing,
    // ── Villager ──
    Greeting,
    SiegeFalls,
    Dawn,
    Rescued,
    // ── Ork ──
    OrkSpot,
    OrkDeath,
    // ── Chain reply concepts ──
    ReplyToVillagerJab,
}

/// A follow-up dispatched when a line finishes: ask `target` to look up a line whose
/// `reply_to == Some(concept)`. If none matches the (now-current) facts, nothing plays — the
/// chain self-terminates (the Valve "no explicit interruption" property).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Chain {
    pub concept: Concept,
    pub target: Speaker,
}

/// One voice line — the whole record.
#[derive(Clone, Copy)]
pub struct Line {
    /// Stable key; also the clip stem at `audio/vo/<dir>/<id>.ogg` (dir per speaker).
    pub id: &'static str,
    pub speaker: Speaker,
    pub concept: Concept,
    /// Transcript: the on-screen subtitle AND our in-code record of the quote.
    pub text: &'static str,
    /// May a louder/just-as-loud new line cut this off mid-clip?
    pub interruptible: bool,
    /// Barge-in priority: a new line plays over a playing one only if `new.priority >= cur.priority`.
    pub priority: u8,
    /// If set, this line is a valid reply to a dispatched chain `Concept`.
    pub reply_to: Option<Concept>,
    /// If set, dispatch this chain when the line finishes.
    pub then: Option<Chain>,
}

/// Convenience constructor for the common case (no reply_to / no then, interruptible, prio 10).
const fn line(id: &'static str, speaker: Speaker, concept: Concept, text: &'static str) -> Line {
    Line { id, speaker, concept, text, interruptible: true, priority: 10, reply_to: None, then: None }
}

/// THE catalog. Filled in across the migration tasks (Phase C). Starts with a single hero line so
/// Phase A/B have something real to resolve and test against.
pub const LINES: &[Line] = &[
    line("levelup", Speaker::Hero, Concept::LevelUp, "Stronger. The blade feels lighter than it did."),
];

/// All catalog lines for a concept, in declaration order.
pub fn candidates(concept: Concept) -> impl Iterator<Item = &'static Line> {
    LINES.iter().filter(move |l| l.concept == concept)
}

/// All catalog lines that are a valid reply to a dispatched chain concept.
pub fn replies_to(concept: Concept) -> impl Iterator<Item = &'static Line> {
    LINES.iter().filter(move |l| l.reply_to == Some(concept))
}

/// xorshift — same as the audio module's RNG, duplicated here to keep `lines` Bevy/dep-free.
fn next_rng(s: &mut u32) -> u32 {
    if *s == 0 {
        *s = 0x9e37_79b9;
    }
    *s ^= *s << 13;
    *s ^= *s >> 17;
    *s ^= *s << 5;
    *s
}
fn frand(s: &mut u32) -> f32 {
    (next_rng(s) & 0x00ff_ffff) as f32 / 0x00ff_ffff as f32
}

/// Pick a line for `concept`: among candidates, drop any played more recently than `floor`
/// seconds ago (per-line replay floor, keyed by `id` in `last`), random pick of the rest.
/// Returns `None` if the concept has no candidates or all are still floored.
pub fn pick_line(
    concept: Concept,
    last: &std::collections::HashMap<&'static str, f32>,
    now: f32,
    floor: f32,
    rng: &mut u32,
) -> Option<&'static Line> {
    let fresh: Vec<&'static Line> = candidates(concept)
        .filter(|l| now - *last.get(l.id).unwrap_or(&f32::NEG_INFINITY) >= floor)
        .collect();
    if fresh.is_empty() {
        return None;
    }
    let i = (frand(rng) * fresh.len() as f32) as usize % fresh.len();
    Some(fresh[i])
}

/// What a speaker is currently saying (tracked by the director's `VoiceManager`).
#[derive(Clone, Copy, Debug)]
pub struct Active {
    pub id: &'static str,
    /// `elapsed_secs` when the clip is estimated to finish.
    pub ends_at: f32,
    pub priority: u8,
    pub interruptible: bool,
    /// Chain to dispatch when it finishes (consumed once).
    pub then: Option<Chain>,
}

/// May a new line of `new_priority` start now, given the speaker's current `active` line?
/// Rule (Pixel Crushers): play if the speaker is idle, its line already finished, or the current
/// line is interruptible AND the newcomer is at least as important.
pub fn can_play(active: Option<&Active>, now: f32, new_priority: u8) -> bool {
    match active {
        None => true,
        Some(a) if now >= a.ends_at => true,
        Some(a) => a.interruptible && new_priority >= a.priority,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;

    #[test]
    fn candidates_filters_by_concept() {
        // The seed catalog has exactly one LevelUp line and no ChestOpen line yet.
        assert_eq!(candidates(Concept::LevelUp).count(), 1);
        assert_eq!(candidates(Concept::ChestOpen).count(), 0);
    }

    #[test]
    fn pick_line_none_when_no_candidates() {
        let last = HashMap::new();
        let mut rng = 1;
        assert!(pick_line(Concept::ChestOpen, &last, 100.0, 300.0, &mut rng).is_none());
    }

    #[test]
    fn pick_line_respects_replay_floor() {
        let mut last = HashMap::new();
        last.insert("levelup", 50.0);
        let mut rng = 1;
        // 10s later, floor 300 → still floored → None.
        assert!(pick_line(Concept::LevelUp, &last, 60.0, 300.0, &mut rng).is_none());
        // 400s later → floor cleared → returns the line.
        assert_eq!(pick_line(Concept::LevelUp, &last, 450.0, 300.0, &mut rng).unwrap().id, "levelup");
    }

    #[test]
    fn pick_line_first_play_ignores_floor() {
        let last = HashMap::new();
        let mut rng = 1;
        assert!(pick_line(Concept::LevelUp, &last, 0.0, 300.0, &mut rng).is_some());
    }

    #[test]
    fn every_speaker_is_registered() {
        for s in [Speaker::Hero, Speaker::Villager, Speaker::Ork] {
            let _ = speaker_voice(s); // must not panic
        }
    }

    fn active(prio: u8, interruptible: bool, ends_at: f32) -> Active {
        Active { id: "x", ends_at, priority: prio, interruptible, then: None }
    }

    #[test]
    fn can_play_when_idle() {
        assert!(can_play(None, 0.0, 0));
    }

    #[test]
    fn can_play_when_current_finished() {
        let a = active(255, false, 5.0);
        assert!(can_play(Some(&a), 6.0, 0)); // past ends_at → even a non-interruptible line is done
    }

    #[test]
    fn cannot_interrupt_protected_line() {
        let a = active(50, false, 100.0);
        assert!(!can_play(Some(&a), 1.0, 255)); // not interruptible → blocked regardless of priority
    }

    #[test]
    fn interrupt_needs_equal_or_higher_priority() {
        let a = active(50, true, 100.0);
        assert!(!can_play(Some(&a), 1.0, 49)); // lower → blocked
        assert!(can_play(Some(&a), 1.0, 50)); // equal → allowed
        assert!(can_play(Some(&a), 1.0, 200)); // higher → allowed
    }
}
