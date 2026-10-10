//! Caged captives' MUFFLED voices — the trigger side. Each prisoner cage carries a [`CageVoice`]
//! clock (on its frame, `camps::spawn_cage`): every 15–40 s, and only while the hero is within
//! earshot, one of its captives makes a sound through the bars — sobbing / a cough / a groan from
//! afar, a few hopeless words once he is near, a frightened gasp when an ork steps up to the cage or
//! a fight breaks out beside it, and — with the hero right there and the jailers dead or away — a
//! plea aimed straight at him. The words get clearer the closer he is twice over: the spatial voice
//! is louder, and the pool shifts from wordless sounds to speech.
//!
//! WHAT plays (the clips, their transcripts, floors, priorities) is the `Speaker::Captive` block
//! of `lines.rs`; HOW is the director: positional at the speaking captive, at
//! `BACKGROUND_PRIORITY` (any real line cuts a murmur; a murmur never waits a real line out), and
//! captioned as a muffled aside that never replaces a story subtitle. This module only decides
//! WHEN, and which captive's mouth it comes from (the speaker also nods along — `captives`).
//!
//! No two lines from one cage overlap (the gap is far longer than any clip, and the shared voice
//! channel is single-file anyway), a busy channel postpones the turn a few seconds instead of
//! spending it, and a few seconds' spacing across ALL cages keeps the Hold's row of cages from
//! sobbing in a chain.

use bevy::prelude::*;

use super::director::{Speak, VoiceManager};
use super::lines::Concept;
use crate::captives::CaptiveLife;
use crate::villagers::WalkOut;

/// Beyond this (world u, hero → cage) nothing is heard, so nothing is said.
const EARSHOT: f32 = 24.0;
/// Inside this the captives' few words carry (otherwise only wordless sounds do).
const MURMUR_R: f32 = 13.0;
/// Inside this, with no jailer near, a captive pleads with the hero directly.
const PLEA_R: f32 = 9.0;
/// "The orks are away": no live ork within this of the cage.
const JAILER_AWAY: f32 = 12.0;
/// An ork this close to the cage centre (half-width 1.1) is right at the bars — the cage answers
/// with fear. (The warband lounging round its fire ~3 u off is not; that is every day.)
const ORK_AT_BARS: f32 = 2.6;
/// …as does any captive this frightened (a fight / a felled ork beside the cage).
const FEAR_LINE: f32 = 0.45;
/// Seconds between one cage's lines.
const GAP: (f32, f32) = (15.0, 40.0);
/// The first line after the hero first comes in earshot — soon, but not on the instant.
const FIRST: (f32, f32) = (3.0, 15.0);
/// Out of earshot: look again this soon.
const RECHECK: (f32, f32) = (2.0, 6.0);
/// The voice channel is busy (or another cage just spoke): try again this soon.
const RETRY: (f32, f32) = (3.0, 6.0);
/// Minimum spacing between any two captive lines, across every cage.
const ALL_CAGES_SPACING: f32 = 6.0;
/// Rough length of a captive line, for the speaker's talk nod (the clips run 1.0–2.9 s).
const NOD_SECS: f32 = 2.2;

/// One cage's voice clock. `next_at` is NaN until the cage is first heard.
#[derive(Component, Clone, Copy, Debug)]
pub(crate) struct CageVoice {
    next_at: f32,
    rng: u32,
}

/// What a cage's turn sees: the hero's and the nearest live ork's XZ distance from the cage
/// centre, and the most frightened captive's fear (`captives::Mind`).
#[derive(Clone, Copy, Debug)]
pub(crate) struct Heard {
    pub(crate) hero_d: f32,
    pub(crate) ork_d: f32,
    pub(crate) fear: f32,
}

/// Which kind of sound the cage makes for `h` (`roll` in 0..1 splits sobs from words in the middle
/// band). `None` = the hero can't hear it, so say nothing.
pub(crate) fn pick_call(h: Heard, roll: f32) -> Option<Concept> {
    if h.hero_d > EARSHOT {
        return None;
    }
    Some(if h.ork_d < ORK_AT_BARS || h.fear > FEAR_LINE {
        Concept::CaptiveFear
    } else if h.hero_d < PLEA_R && h.ork_d > JAILER_AWAY {
        Concept::CaptivePlea
    } else if h.hero_d < MURMUR_R && roll < 0.5 {
        Concept::CaptiveMurmur
    } else {
        Concept::CaptiveSob
    })
}

impl CageVoice {
    pub(crate) fn new(seed: u32) -> Self {
        Self { next_at: f32::NAN, rng: seed.wrapping_mul(0x2545_F491) | 1 }
    }
    fn range(&mut self, (a, b): (f32, f32)) -> f32 {
        a + (b - a) * super::frand(&mut self.rng)
    }
    /// One turn of the cage's clock. `heard` = `None` when nobody is left inside to speak;
    /// `busy` = the voice channel (or the cross-cage spacing) won't take a line now. Returns the
    /// concept to voice when it is this cage's turn, and reschedules either way.
    pub(crate) fn tick(&mut self, now: f32, heard: Option<Heard>, busy: bool) -> Option<Concept> {
        let in_earshot = heard.is_some_and(|h| h.hero_d <= EARSHOT);
        if self.next_at.is_nan() {
            // Wait for the hero to come in earshot, then start the clock — a first line soon.
            if in_earshot {
                self.next_at = now + self.range(FIRST);
            }
            return None;
        }
        if now < self.next_at {
            return None;
        }
        let roll = super::frand(&mut self.rng);
        let Some(call) = heard.and_then(|h| pick_call(h, roll)) else {
            self.next_at = now + self.range(RECHECK);
            return None;
        };
        if busy {
            // Postponed, not spent: the line comes as soon as the channel frees up.
            self.next_at = now + self.range(RETRY);
            return None;
        }
        self.next_at = now + self.range(GAP);
        Some(call)
    }
}

/// Run every cage's voice clock and emit its `Speak` from the right captive's mouth.
#[allow(clippy::type_complexity)]
pub(crate) fn detect_captive_voices(
    time: Res<Time>,
    mgr: Res<VoiceManager>,
    hero: Option<Res<crate::player::HeroState>>,
    mut cages: Query<(&GlobalTransform, &mut CageVoice)>,
    mut captives: Query<(&GlobalTransform, &mut CaptiveLife), Without<WalkOut>>,
    orks: Query<&GlobalTransform, (With<crate::orks::Ork>, Without<crate::dying::Dying>)>,
    mut speak: MessageWriter<Speak>,
    mut last_any: Local<f32>,
) {
    let now = time.elapsed_secs();
    let Some(hero) = hero.filter(|h| h.alive) else { return };
    // Anyone mid-line at all (a captive's own murmur included) holds the cages' turn.
    let channel_busy = mgr.active.values().any(|a| now < a.ends_at) || now - *last_any < ALL_CAGES_SPACING;
    for (cage_g, mut voice) in &mut cages {
        let c = cage_g.translation();
        let centre = Vec2::new(c.x, c.z);
        let hero_d = hero.pos.distance(centre);
        // Cheap early-outs: a far cage that hasn't started its clock, or a turn not yet due.
        if (voice.next_at.is_nan() && hero_d > EARSHOT) || now < voice.next_at {
            continue;
        }
        let inside = || captives.iter().filter(move |(_, l)| l.berth.cage.distance(centre) < 0.5);
        let heard = inside().map(|(_, l)| l.mind.fear()).reduce(f32::max).map(|fear| {
            let ork_d = orks
                .iter()
                .map(|g| Vec2::new(g.translation().x, g.translation().z).distance(centre))
                .fold(f32::INFINITY, f32::min);
            Heard { hero_d, ork_d, fear }
        });
        let Some(call) = voice.tick(now, heard, channel_busy) else { continue };
        // Whose mouth: the plea comes from the captive nearest the hero; a fear line from the most
        // frightened; anything else from whoever the dice pick.
        let pick = match call {
            Concept::CaptivePlea => inside()
                .map(|(g, l)| (g.translation(), l.berth.seat, hero.pos.distance(Vec2::new(g.translation().x, g.translation().z))))
                .min_by(|a, b| a.2.total_cmp(&b.2))
                .map(|(p, s, _)| (p, s)),
            Concept::CaptiveFear => inside()
                .max_by(|a, b| a.1.mind.fear().total_cmp(&b.1.mind.fear()))
                .map(|(g, l)| (g.translation(), l.berth.seat)),
            _ => {
                let n = inside().count();
                let i = (super::frand(&mut voice.rng) * n as f32) as usize % n.max(1);
                inside().nth(i).map(|(g, l)| (g.translation(), l.berth.seat))
            }
        };
        let Some((at, seat)) = pick else { continue };
        // The mouth: head height — standing at the bars or slumped on the straw.
        let up = captives.iter_mut().find(|(_, l)| l.berth.seat == seat).map(|(_, mut l)| {
            l.mind.speak(now, NOD_SECS);
            l.mind.is_up()
        });
        let mouth = at + Vec3::Y * if up == Some(true) { 1.3 } else { 0.8 };
        speak.write(Speak::at(call, mouth));
        *last_any = now;
        return; // one captive line per frame, at most
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const DT: f32 = 0.1;
    fn near(hero_d: f32) -> Option<Heard> {
        Some(Heard { hero_d, ork_d: 30.0, fear: 0.0 })
    }

    #[test]
    fn calls_get_clearer_as_the_hero_comes_closer() {
        let quiet = |hero_d, roll| pick_call(Heard { hero_d, ork_d: 30.0, fear: 0.0 }, roll);
        assert_eq!(quiet(30.0, 0.1), None, "out of earshot: silence");
        assert_eq!(quiet(20.0, 0.1), Some(Concept::CaptiveSob), "far: only wordless sounds carry");
        assert_eq!(quiet(20.0, 0.9), Some(Concept::CaptiveSob));
        assert_eq!(quiet(11.0, 0.1), Some(Concept::CaptiveMurmur), "nearer: a few words");
        assert_eq!(quiet(11.0, 0.9), Some(Concept::CaptiveSob));
        assert_eq!(quiet(5.0, 0.5), Some(Concept::CaptivePlea), "at the bars, jailers gone: a plea");
        // A jailer still about: no plea, just the murmurs.
        let guarded = Heard { hero_d: 5.0, ork_d: 8.0, fear: 0.2 };
        assert_eq!(pick_call(guarded, 0.1), Some(Concept::CaptiveMurmur));
        // An ork at the bars, or a captive in a fright: fear, whatever else holds.
        assert_eq!(pick_call(Heard { ork_d: 2.5, ..guarded }, 0.1), Some(Concept::CaptiveFear));
        assert_eq!(pick_call(Heard { hero_d: 20.0, ork_d: 30.0, fear: 0.7 }, 0.9), Some(Concept::CaptiveFear));
    }

    #[test]
    fn a_cage_stays_silent_until_the_hero_is_in_earshot_then_speaks_soon() {
        let mut v = CageVoice::new(7);
        let mut t = 0.0;
        while t < 60.0 {
            assert_eq!(v.tick(t, near(40.0), false), None);
            t += DT;
        }
        assert!(v.next_at.is_nan(), "the clock doesn't start for a cage nobody can hear");
        let came = t;
        let mut first = None;
        while t < came + 30.0 && first.is_none() {
            if v.tick(t, near(15.0), false).is_some() {
                first = Some(t - came);
            }
            t += DT;
        }
        let first = first.expect("speaks once the hero is near");
        assert!((FIRST.0..=FIRST.1 + DT).contains(&first), "first line after {first}s");
    }

    #[test]
    fn ten_minutes_by_a_cage_keeps_the_gap_and_a_busy_channel_only_postpones() {
        for seed in [1, 2, 3, 99] {
            let mut v = CageVoice::new(seed);
            let mut said = Vec::new();
            let mut t = 0.0;
            while t < 600.0 {
                // Something else speaks for 4 s out of every 23 — the cage must wait it out.
                let busy = t % 23.0 < 4.0;
                if v.tick(t, near(10.0), busy).is_some() {
                    assert!(!busy, "never talks over the channel");
                    said.push(t);
                }
                t += DT;
            }
            assert!(said.len() >= 12, "seed {seed}: a cage by the hero keeps making sound ({} lines)", said.len());
            for w in said.windows(2) {
                let gap = w[1] - w[0];
                // 15–40 s, plus at most a postponement or two behind a busy channel.
                assert!((GAP.0 - DT..=GAP.1 + 2.0 * RETRY.1).contains(&gap), "seed {seed}: gap {gap}");
            }
        }
    }

    #[test]
    fn walking_out_of_earshot_holds_the_turn_without_spending_it() {
        let mut v = CageVoice::new(5);
        v.next_at = 10.0;
        // Out of earshot when the turn comes: nothing, and a quick recheck instead of a full gap.
        assert_eq!(v.tick(10.0, near(30.0), false), None);
        assert!(v.next_at <= 10.0 + RECHECK.1);
        // An empty cage (everyone freed) never speaks.
        let at = v.next_at;
        assert_eq!(v.tick(at, None, false), None);
        // Back in range: the very next turn speaks.
        let at = v.next_at;
        assert!(v.tick(at, near(10.0), false).is_some());
        assert!(v.next_at >= at + GAP.0);
    }
}
