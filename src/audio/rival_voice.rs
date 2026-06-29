//! Rival-garrison voices — **trigger only** (mirrors `ork.rs`). Detects rival-speech opportunities
//! and emits [`super::Speak`]; the catalog (`lines.rs`) owns the line data + the `Rival` speaker's
//! spatial routing / pitch jitter, and the director (`director.rs`) owns playback + subtitle.
//!
//! - [`RivalVoiceTrigger`] is the one global throttle (like `OrkTrigger`).
//! - [`detect_rival_voices`] fires `RivalDeath` for a freshly-fallen rival, otherwise a bark from
//!   the nearest live rival in earshot: a combat bark (`RivalSpot`) when the hero is in a fight
//!   ([`super::HeroThreat`]), or the bored patrol murmur (`RivalIdle`) when all is quiet.
//! - The raid-march cue (`RivalRaidMarch`) is emitted separately from `rival.rs` when a raid sets out.

use bevy::prelude::*;

use crate::dying::Dying;
use crate::player::Hero;
use crate::rival::{RivalRaider, RivalSoldier};

use super::frand;

/// Shortest gap between any two rival utterances; a random slice up to [`BARK_GAP_JITTER`] is added
/// so the cadence is irregular. A touch slower than the orks — disciplined soldiers, not a snarling
/// horde.
const BARK_GAP: f32 = 7.0;
const BARK_GAP_JITTER: f32 = 6.0;
/// A rival must be within this of the hero (world units) for its bark to be worth playing.
const EARSHOT: f32 = 40.0;
/// Chance we spend a clear cooldown on a freshly-fallen rival's death cry (vs. a living one's bark).
const DEATH_CHANCE: f32 = 0.3;

/// Per-run rival bark throttle + jitter RNG.
#[derive(Resource)]
pub(crate) struct RivalVoiceTrigger {
    next_bark: f32,
    rng: u32,
}

impl Default for RivalVoiceTrigger {
    fn default() -> Self {
        Self { next_bark: 8.0, rng: 0x2f6e_1d77 }
    }
}

pub(crate) fn reset_rival_trigger(mut t: ResMut<RivalVoiceTrigger>) {
    *t = RivalVoiceTrigger::default();
}

/// The rival-voice trigger. Emits a [`super::Speak`] for a fallen rival's death cry, or the nearest
/// living rival in earshot — a combat bark while the hero fights, the patrol murmur otherwise.
pub(crate) fn detect_rival_voices(
    time: Res<Time>,
    mut t: ResMut<RivalVoiceTrigger>,
    mgr: Res<super::director::VoiceManager>,
    threat: Res<super::HeroThreat>,
    mut speak: MessageWriter<crate::audio::Speak>,
    hero: Query<&Hero>,
    dying: Query<&GlobalTransform, (Added<Dying>, Or<(With<RivalSoldier>, With<RivalRaider>)>)>,
    alive: Query<&GlobalTransform, (Or<(With<RivalSoldier>, With<RivalRaider>)>, Without<Dying>)>,
) {
    let now = time.elapsed_secs();
    if now < t.next_bark {
        return;
    }
    if mgr.hero_speaking(now) {
        return; // never talk over the hero
    }
    let Ok(hero) = hero.single() else { return };

    // A newly-fallen rival's death cry (only sometimes, so battle cries get a turn too).
    if let Some(gt) = dying.iter().next() {
        if frand(&mut t.rng) < DEATH_CHANCE {
            speak.write(crate::audio::Speak::at(super::Concept::RivalDeath, gt.translation()));
            t.next_bark = now + BARK_GAP + frand(&mut t.rng) * BARK_GAP_JITTER;
            return;
        }
    }

    // Otherwise the nearest living rival in earshot speaks: a combat bark if the hero is fighting,
    // else a bored patrol line (which the director mutes anyway the instant a fight starts).
    let mut best: Option<(Vec3, f32)> = None;
    for gt in &alive {
        let p = gt.translation();
        let d = Vec2::new(p.x, p.z).distance(hero.pos);
        if d <= EARSHOT && best.is_none_or(|(_, bd)| d < bd) {
            best = Some((p, d));
        }
    }
    let Some((pos, _)) = best else { return };
    let concept = if threat.in_danger { super::Concept::RivalSpot } else { super::Concept::RivalIdle };
    speak.write(crate::audio::Speak::at(concept, pos));
    t.next_bark = now + BARK_GAP + frand(&mut t.rng) * BARK_GAP_JITTER;
}
