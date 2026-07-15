//! Skirmish audio glue. The game's audio **playback** pipeline (`src/audio/`) is NOT campaign-gated
//! — `sfx::play_cues` and `director::speak_director` already run in skirmish — so making the RTS
//! audible is purely a matter of *writing the same messages campaign code writes*: an [`AudioCue`]
//! for a one-shot sound effect, a [`Speak`] for a voiced line. This module owns the two RTS-only
//! voice triggers that need their own state (throttled low-resource advice + the match-end line);
//! the incidental SFX (selection clicks, orders, building placement, combat strikes, arrow looses)
//! are written inline from the systems that already own those events (`select`/`command`/`build`/
//! `units`).
//!
//! Voice caveat (known): `Concept::AdviseWood/Farm/Stone`, `WarlordSlain`, `KeepLost` carry
//! campaign-flavoured transcripts ("the keep", "the orks"). They play correctly but the wording is
//! campaign-ish until skirmish-specific lines are recorded — an acceptable reuse for now.

use bevy::prelude::*;

use crate::audio::{Concept, MusicState, Speak};
use crate::game_state::{AppState, Modal};
use crate::player::Health;
use crate::rts::command::AttackTarget;
use crate::rts::{in_skirmish, RtsBanks, RtsBuilding, RtsOutcome, RtsUnit, Side, UnitKind};

/// Below this stock (units) a resource is "short" and worth a spoken nudge.
const LOW_WOOD: f64 = 20.0;
const LOW_FOOD: f64 = 15.0;
const LOW_STONE: f64 = 15.0;
/// Don't repeat the same advice within this many seconds (so a lingering shortage doesn't nag).
const ADVICE_COOLDOWN: f32 = 40.0;
/// Seconds between one townsperson's ambient chatter line (`Greeting` pool — worker/villager idle
/// remarks) so the settlement feels lived-in — but sparse, so it's flavour not chatterbox spam (the
/// lines are 2D + audible in skirmish now, so they don't need to fire nearly as often as when they
/// were half-inaudible spatial).
const CHATTER_EVERY: f32 = 30.0;
/// Seconds between the rival garrison's ambient patrol murmur (`RivalIdle` pool) — sparser still, and
/// only while nothing's fighting.
const RIVAL_CHATTER_EVERY: f32 = 44.0;
/// A drop of at least this much total player-building HP between frames counts as "under attack".
const UNDER_ATTACK_DROP: f32 = 6.0;
/// Don't re-cry "under attack" within this many seconds.
const UNDER_ATTACK_CD: f32 = 22.0;

/// Per-concept "last spoken at" clock for the throttle (sim seconds; 0 = never).
#[derive(Resource, Default)]
struct AdviceClock {
    wood: f32,
    food: f32,
    stone: f32,
}

pub struct RtsAudioPlugin;

impl Plugin for RtsAudioPlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<AdviceClock>().add_systems(
            Update,
            (
                low_resource_advice.run_if(in_state(Modal::None)),
                villager_chatter.run_if(in_state(Modal::None)),
                rival_chatter.run_if(in_state(Modal::None)),
                under_attack_voice.run_if(in_state(Modal::None)),
                combat_music,
                match_end_voice,
            )
                .run_if(in_skirmish)
                .run_if(in_state(AppState::Playing)),
        );
    }
}

/// Watch the player's bank; when a resource runs short, have the hero voice the matching advice
/// (throttled per resource). This is the "we're low on wood / food / stone" nudge the player asked
/// for. Only the PLAYER side is voiced.
fn low_resource_advice(
    time: Res<Time>,
    banks: Res<RtsBanks>,
    mut clock: ResMut<AdviceClock>,
    mut speak: MessageWriter<Speak>,
) {
    let now = time.elapsed_secs();
    let b = banks.side(Side::Player);
    // One line per tick at most (pick the most-pressing shortage) so two empties don't talk over
    // each other. Food first (starvation is the hard fail), then wood (everything costs it), stone.
    if b.food < LOW_FOOD && now - clock.food > ADVICE_COOLDOWN {
        clock.food = now;
        speak.write(Speak::new(Concept::AdviseFarm));
    } else if b.wood < LOW_WOOD && now - clock.wood > ADVICE_COOLDOWN {
        clock.wood = now;
        speak.write(Speak::new(Concept::AdviseWood));
    } else if b.stone < LOW_STONE && now - clock.stone > ADVICE_COOLDOWN {
        clock.stone = now;
        speak.write(Speak::new(Concept::AdviseStone));
    }
}

/// Every so often, one working townsperson pipes up with an idle remark (the `Greeting` pool —
/// worker/villager ambient lines). Positional, so it comes from that worker in the world. Keeps the
/// settlement sounding lived-in. Picks a deterministic worker from the sim clock (no RNG in
/// systems). Only PLAYER townsfolk chatter; the rival has its own `RivalIdle` pool elsewhere.
fn villager_chatter(
    time: Res<Time>,
    focus: Res<crate::rts::camera::RtsCamFocus>,
    mut speak: MessageWriter<Speak>,
    mut acc: Local<f32>,
    workers: Query<(&GlobalTransform, &Side, &RtsUnit), Without<crate::dying::Dying>>,
) {
    *acc += time.delta_secs();
    if *acc < CHATTER_EVERY {
        return;
    }
    *acc -= CHATTER_EVERY;
    // Only townsfolk that are roughly on-screen chatter (an off-screen remark reads as a phantom).
    let mine: Vec<Vec3> = workers
        .iter()
        .filter(|(gt, s, u)| {
            **s == Side::Player
                && u.kind == UnitKind::Worker
                && focus.in_earshot(Vec2::new(gt.translation().x, gt.translation().z))
        })
        .map(|(gt, _, _)| gt.translation())
        .collect();
    if mine.is_empty() {
        return;
    }
    // Pick one by the sim clock (stable within the tick, varies across ticks).
    let idx = (time.elapsed_secs() as usize) % mine.len();
    speak.write(Speak::at(Concept::Greeting, mine[idx]));
}

/// The rival garrison's ambient patrol murmur (`RivalIdle` pool) — the enemy town should sound
/// lived-in too. Only while PEACEFUL (nothing fighting) and only from an on-screen rival body, so a
/// bark never overlaps their combat cries or comes from off-map.
fn rival_chatter(
    time: Res<Time>,
    focus: Res<crate::rts::camera::RtsCamFocus>,
    fighting: Query<(), With<AttackTarget>>,
    mut speak: MessageWriter<Speak>,
    mut acc: Local<f32>,
    units: Query<(&GlobalTransform, &Side, &RtsUnit), Without<crate::dying::Dying>>,
) {
    *acc += time.delta_secs();
    if *acc < RIVAL_CHATTER_EVERY {
        return;
    }
    *acc -= RIVAL_CHATTER_EVERY;
    if !fighting.is_empty() {
        return; // a battle is on — the RivalSpot combat pool owns the airwaves
    }
    let them: Vec<Vec3> = units
        .iter()
        .filter(|(gt, s, _)| {
            **s == Side::Rival
                && focus.in_earshot(Vec2::new(gt.translation().x, gt.translation().z))
        })
        .map(|(gt, _, _)| gt.translation())
        .collect();
    if them.is_empty() {
        return;
    }
    let idx = (time.elapsed_secs() as usize) % them.len();
    speak.write(Speak::at(Concept::RivalIdle, them[idx]));
}

/// Cry "the keep's taking a beating" (`KeepHurt`) when the player's buildings lose HP — the
/// "you're under attack" alert the RTS was missing. Watches the total player-building HP and fires
/// (throttled) whenever it drops by a real chunk, so a raid on your base is HEARD even off-screen.
fn under_attack_voice(
    time: Res<Time>,
    mut last_total: Local<f32>,
    mut clock: Local<f32>,
    mut speak: MessageWriter<Speak>,
    bldgs: Query<(&Side, &Health), With<RtsBuilding>>,
) {
    let mut total = 0.0;
    for (s, h) in &bldgs {
        if *s == Side::Player {
            total += h.hp.max(0.0);
        }
    }
    let now = time.elapsed_secs();
    if total < *last_total - UNDER_ATTACK_DROP && now - *clock > UNDER_ATTACK_CD {
        *clock = now;
        speak.write(Speak::new(Concept::KeepHurt)); // "The keep's taking a beating…"
    }
    *last_total = total;
}

/// Swell the combat-music layer whenever anything on the field is fighting — the skirmish never set
/// `MusicState.fighting`, so the battle track (`music-combat.ogg`) never rose. Skirmish-only, so it
/// never fights the campaign's own combat/boss music flags.
fn combat_music(mut music: ResMut<MusicState>, fighting: Query<(), With<AttackTarget>>) {
    music.fighting = !fighting.is_empty();
}

/// Voice the match verdict once when it lands (victory cheer / defeat lament).
fn match_end_voice(
    outcome: Res<RtsOutcome>,
    mut said: Local<bool>,
    mut speak: MessageWriter<Speak>,
) {
    if *said {
        return;
    }
    match *outcome {
        RtsOutcome::PlayerWon => {
            *said = true;
            speak.write(Speak::new(Concept::WarlordSlain)); // "It's over. It's finally over."
        }
        RtsOutcome::RivalWon => {
            *said = true;
            speak.write(Speak::new(Concept::KeepLost)); // "The walls are down…"
        }
        RtsOutcome::Undecided => {}
    }
}
