//! Game audio — **event-driven**. Gameplay systems emit [`AudioCue`]s (and set [`MusicState`]);
//! this module owns every audio sink. Ported from the old web game's `audio.ts` / `sfx.ts`
//! central registry, split into focused submodules so each file does one job:
//!
//! - [`sfx`] — one-shot combat/UI/footstep stings + spatial creature voices
//! - [`voice`] — the hero's "one-mouth" voice (swing grunt / hurt / death / biome line)
//! - [`music`] — background bed + a combat layer that swells while orks fight the hero
//! - [`ambience`] — biome / water loops + a spatial campfire loop at each camp
//! - [`footsteps`] — per-step stings tied to the hero's gait + ground surface
//! - [`animals`] — the proximity-gated spatial wildlife calls (this game's own clips)
//!
//! Decoupling rule: gameplay code NEVER spawns a sink — it writes an [`AudioCue`] (or flips a
//! flag on [`MusicState`]). Only this module reads them and plays sound.

mod ambience;
mod animals;
mod footsteps;
mod music;
mod sfx;
pub(crate) mod synth;
mod voice;

use bevy::prelude::*;

use crate::biome::Biome;

/// Ground surface under the hero — selects which footstep clip plays.
#[derive(Clone, Copy, PartialEq, Eq)]
pub enum Surface {
    Dirt,
    Snow,
    Stone,
}

/// A one-off **spoken reaction** by the hero (the "mouth"), distinct from the per-biome
/// [`AudioCue::HeroLine`]. Ported from the old game's `sayHeroLine(key, …)` event lines.
#[derive(Clone, Copy, PartialEq, Eq)]
pub enum HeroEvent {
    /// First ore broken this run ("stone → defenses").
    FirstStone,
    /// A chest was opened (repeatable).
    ChestOpen,
    /// First camp freed this run ("the rescued become militia").
    FirstRescue,
    /// Prep is nearly over — night is coming (once per prep day).
    NightWarning,
    /// HP crossed the danger threshold (repeatable).
    LowHp,
    /// Returned to the castle after roaming the wilderness (once this run).
    Home,
}

/// A one-shot audio request. Gameplay writes these via `MessageWriter<AudioCue>`; [`sfx`] and
/// [`voice`] each read the whole stream and handle their own subset.
#[derive(Message, Clone, Copy)]
pub enum AudioCue {
    // ── Combat / UI feedback (non-spatial one-shots, handled by `sfx`) ──
    /// Empty-swing whoosh — fired ONLY on a whiff (a connecting hit plays `Impact` instead,
    /// never both — matches `Character.tsx`'s deferred-whoosh logic).
    Swing,
    /// Hero's blow lands → impact (heavier on a kill).
    Impact { kill: bool },
    /// A hit was actually absorbed by the raised shield (wood/steel knock).
    Block,
    /// One footstep; `landing` = the louder touchdown step after a jump/fall.
    Footstep { surface: Surface, landing: bool },
    /// UI confirm blip (biome switch).
    UiSelect,
    // ── Hero "mouth" (head-locked, one at a time, handled by `voice`) ──
    /// Exertion grunt layered over a swing — voice rolls a 34% chance + the canGrunt gate.
    HeroGruntSwing,
    /// Effort grunt on a jump — voice rolls a 40% chance + the canGrunt gate (no other jump sfx).
    HeroJump,
    /// Pain cry on a non-fatal hit.
    HeroHurt,
    /// Death scream on the killing blow (interrupts any line).
    HeroDeath,
    /// Hero's spoken thought on entering a biome.
    HeroLine(Biome),
    // ── Spatial creature voices (handled by `sfx`, positioned in the world) ──
    /// Ork aggro grunt at a world position.
    OrkGrunt(Vec3),
    /// Warband alert roar at a world position (hero enters a camp clearing).
    OrkRoar(Vec3),
    /// A wild predator's snarl as it bites the hero, at a world position. `big` = a heavy beast
    /// (bear/croc/golem) → a deeper, louder roar. Pitch-jittered so a flurry never repeats.
    CreatureBite { at: Vec3, big: bool },
    /// One metallic chip on a pick-swing against an ore boulder (sampled `var-1`/`var-3`
    /// clips, pitch-jittered). Distinct from the `OreShatter` synth sting on the breaking blow.
    OreChip,
    // ── Procedural stings (synth-baked, handled by `sfx` via [`synth::StingBank`]) ──
    /// Ore boulder shattered.
    OreShatter,
    /// Chest lid opened.
    ChestOpen,
    /// Herb / loot picked up.
    Forage,
    /// Hero gained a level.
    LevelUp,
    /// Gold collected.
    Gold,
    /// Shop purchase confirmed.
    ShopBuy,
    /// Night wave summoned (war bell).
    WarBell,
    /// Camp captive freed.
    CampRescue,
    /// Hero HP crossed the low threshold.
    LowHp,
    /// A one-off spoken reaction by the hero (see [`HeroEvent`]); handled by [`voice`].
    HeroEvent(HeroEvent),
}

/// Per-run gates for the "once" event voice lines (the old game's `spoken` key-set). Reset on
/// a fresh run. `been_away` latches the home-return line: it can only fire after the hero has
/// roamed past [`AWAY_RADIUS`] from the castle.
#[derive(Resource, Default)]
pub(crate) struct HeroLineGates {
    pub first_stone: bool,
    pub first_rescue: bool,
    pub home: bool,
    pub been_away: bool,
    /// Wilderness biomes whose musing has already played this run (the old game's `biome:`
    /// `spoken` keys) — each biome line fires at most once per run. Cleared with the rest on
    /// a fresh run via [`reset_hero_line_gates`].
    pub spoken_biomes: Vec<Biome>,
}

/// Castle is at the world origin; the hero must roam beyond this, then return inside
/// [`HOME_RADIUS`], to trigger the home-return line.
const AWAY_RADIUS: f32 = 34.0;
const HOME_RADIUS: f32 = 16.0;

/// Combat-music driver. Ork AI sets `fighting = true` while any ork hunts / strikes the hero;
/// [`music`] eases the combat layer in/out from it.
#[derive(Resource, Default)]
pub struct MusicState {
    pub fighting: bool,
}

/// Live-tunable mix (F1 debug panel). The wildlife knobs are unchanged from the original
/// `audio.rs`; the rest scale their category at the point of playback.
#[derive(Resource)]
pub struct AudioConfig {
    /// Target volume of a biome/water ambience bed while you're inside it (quiet bed).
    pub ambience_vol: f32,
    /// Camera→animal distance beyond which a wildlife call is not emitted.
    pub audible_range: f32,
    /// Min / max seconds between one animal's ambient calls.
    pub call_min: f32,
    pub call_max: f32,
    /// Master for combat/UI/footstep one-shots — matches the old game's `audioMix.voice`
    /// (every sampled sting ran through it). Per-cue base gains are the old `playSfx` values.
    pub sfx_vol: f32,
    /// Master for hero grunts + creature voices (also the old `audioMix.voice`).
    pub voice_vol: f32,
    /// Music bed + combat layer level.
    pub music_vol: f32,
    /// Hero spoken biome lines level (kept low, under the mix).
    pub narration_vol: f32,
    /// Combat layer gain, relative to `music_vol`, while fighting.
    pub combat_music: f32,
}

impl Default for AudioConfig {
    fn default() -> Self {
        Self {
            ambience_vol: 0.1,
            audible_range: 32.0,
            call_min: 30.0,
            call_max: 70.0,
            sfx_vol: 0.6,
            voice_vol: 0.6,
            music_vol: 0.22,
            narration_vol: 0.57,
            combat_music: 1.0,
        }
    }
}

pub struct GameAudioPlugin;

impl Plugin for GameAudioPlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<AudioConfig>()
            .init_resource::<MusicState>()
            .init_resource::<synth::StingBank>()
            .init_resource::<HeroLineGates>()
            .add_message::<AudioCue>()
            .add_systems(
                Startup,
                (
                    animals::load_voices,
                    ambience::setup_ambience,
                    music::setup_music,
                    sfx::setup_sfx,
                    synth::bake_stings,
                    voice::setup_voice,
                ),
            )
            .add_systems(
                Update,
                (
                    animals::animal_voices,
                    ambience::biome_ambience,
                    ambience::attach_campfire_audio,
                    footsteps::hero_footsteps,
                    music::update_music,
                    sfx::play_cues,
                    voice::play_voice_cues,
                    detect_player_events,
                    detect_home_return,
                    detect_biome_entry,
                    synth::debug_play_stings,
                ),
            )
            // Fresh run: clear the once-per-run voice gates (mirrors siege's reset).
            .add_systems(
                OnExit(crate::game_state::AppState::StartScreen),
                reset_hero_line_gates,
            )
            .add_systems(OnExit(crate::game_state::AppState::GameOver), reset_hero_line_gates);
    }
}

fn reset_hero_line_gates(mut gates: ResMut<HeroLineGates>) {
    *gates = HeroLineGates::default();
}

/// Emit the home-return line: once the hero has roamed past [`AWAY_RADIUS`] from the castle
/// (origin) and comes back inside [`HOME_RADIUS`] during prep. Fires at most once per run
/// (gated by [`HeroLineGates::home`], which `voice` sets when the clip actually plays).
fn detect_home_return(
    hero: Query<&crate::player::Hero>,
    siege: Option<Res<crate::siege::Siege>>,
    mut gates: ResMut<HeroLineGates>,
    mut cues: MessageWriter<AudioCue>,
) {
    let Ok(hero) = hero.single() else { return };
    let d = hero.pos.length();
    if d > AWAY_RADIUS {
        gates.been_away = true;
    }
    if gates.been_away && !gates.home && d < HOME_RADIUS {
        let in_prep =
            siege.map(|s| matches!(s.phase, crate::siege::GamePhase::Prep)).unwrap_or(true);
        if in_prep {
            cues.write(AudioCue::HeroEvent(HeroEvent::Home));
        }
    }
}

/// Emit the hero's biome musing while he stands in a wilderness biome on the world map. The
/// old game spoke this the first time he walked into each biome; we mirror that by sampling
/// the biome under the hero every frame and writing [`AudioCue::HeroLine`] — `voice` de-dupes
/// it to once-per-biome-per-run, and re-firing each frame lets a line dropped mid-sentence
/// (e.g. crossing a frontier right after another musing) speak once the mouth frees up.
///
/// `biome_at_world` returns `None` over grass / sand / water, so the castle and beaches stay
/// silent — the "home, finally" line is left to [`detect_home_return`].
fn detect_biome_entry(hero: Query<&crate::player::Hero>, mut cues: MessageWriter<AudioCue>) {
    let Ok(hero) = hero.single() else { return };
    if let Some(b) = crate::worldmap::biome_at_world(hero.pos.x, hero.pos.y) {
        cues.write(AudioCue::HeroLine(b));
    }
}

/// Emit the level-up + low-HP stings off the hero's progression (no single call site for these).
fn detect_player_events(
    player: Res<crate::player::PlayerRes>,
    mut cues: MessageWriter<AudioCue>,
    mut init: Local<bool>,
    mut last_level: Local<i64>,
    mut was_low: Local<bool>,
) {
    let p = &player.0;
    if !*init {
        *init = true;
        *last_level = p.level;
        *was_low = false;
    }
    if p.level > *last_level {
        *last_level = p.level;
        cues.write(AudioCue::LevelUp);
    }
    let low = p.max_hp > 0.0 && p.hp > 0.0 && p.hp <= p.max_hp * 0.35;
    if low && !*was_low {
        cues.write(AudioCue::LowHp); // synth danger bleep
        cues.write(AudioCue::HeroEvent(HeroEvent::LowHp)); // hero's pained line over it
    }
    *was_low = low;
}

// ── Tiny shared RNG (xorshift) — clip picks + pitch jitter without pulling a crate. ──
pub(crate) fn next_rng(s: &mut u32) -> u32 {
    if *s == 0 {
        *s = 0x9e37_79b9;
    }
    *s ^= *s << 13;
    *s ^= *s >> 17;
    *s ^= *s << 5;
    *s
}

/// Uniform 0..1.
pub(crate) fn frand(s: &mut u32) -> f32 {
    (next_rng(s) & 0x00ff_ffff) as f32 / 0x00ff_ffff as f32
}

/// Pick a random element (panics only on an empty slice — banks are never empty).
pub(crate) fn pick<T: Clone>(items: &[T], s: &mut u32) -> T {
    let i = (frand(s) * items.len() as f32) as usize;
    items[i.min(items.len() - 1)].clone()
}

/// ±`frac` random pitch multiplier — keeps repeated stings from sounding identical.
pub(crate) fn jitter(s: &mut u32, frac: f32) -> f32 {
    1.0 + (frand(s) * 2.0 - 1.0) * frac
}
