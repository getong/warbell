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
    /// The desert rival's garrison — foreign Saracen-style mercenaries (`rival.rs`). Spatial, like
    /// the orks, with a pitch jitter so one recorded voice covers the whole host.
    Rival,
    /// A peasant locked in an ork cage (`camps.rs`) — spatial at the cage, heard MUFFLED: the clips
    /// are low-passed re-cuts of the villager recordings (`tools/make_captive_vo.py`) and the
    /// subtitle is drawn as a muffled aside that never clobbers a real line
    /// (`Subtitles::say_muffled`). Paced by `audio::captive`.
    Captive,
    /// A village-life resident (`village_life`): the six recorded village voices
    /// ([`LifeVoice`]), spatial at whoever speaks. Clips live under `audio/vo/life/` and are
    /// optional — a line whose `.ogg` isn't on disk yet is never loaded and stays silent (no
    /// subtitle either), so the catalogue can be recorded piecemeal.
    Life,
    /// A named campaign character other than Wat (Wat's own lines use [`Speaker::Hero`], orks use
    /// [`Speaker::Ork`]). Spatial at the `Speak::at` position, or beside the hero if none is given.
    Cast(Cast),
}

/// The campaign cast with recorded voices (`assets/audio/vo/campaign/VOICES.md`).
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum Cast {
    Harrow,
    Maud,
    Pip,
    Settler,
    Farmer,
    Hamid,
}

/// The recorded village voices of `docs/audio/elevenlabs-zycie-wsi.md` — each resident is mapped
/// to one by body (man / woman / elder / child), plus the market vendors and the wall guards.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum LifeVoice {
    Man,
    Woman,
    Vendor,
    Elder,
    Child,
    Guard,
}

/// The everyday situations a village-life resident speaks in (`village_life` triggers them; each
/// voice only has lines for the cues it can say).
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum LifeCue {
    /// The knight walks by.
    Greet,
    /// A buyer at a stall: asks the price, balks at it, gives in.
    Ask,
    Haggle,
    Agree,
    /// The vendor's side of a sale: names the price, counters, done.
    Price,
    Counter,
    Sold,
    /// Hawking wares across the square; teasing the knight; a slow day.
    Hawk,
    Tease,
    Slow,
    /// A line in a conversation (a two-line exchange between neighbours).
    Chat,
    Sit,
    Stand,
    Eat,
    /// Effort at work, and the end of it.
    Work,
    WorkDone,
    Yawn,
    Laugh,
    /// Sun's going — get inside.
    Dusk,
    /// Shooing a kid off something.
    Scold,
    /// A mother calling her child home.
    CallKid,
    Laundry,
    Sweep,
    Water,
    Doze,
    Whittle,
    Cough,
    /// Children at play.
    Tag,
    Unfair,
    Run,
    Knight,
    Mum,
    Hide,
    Count,
    /// The guards' mutter on the wall / at the gate.
    Patrol,
    Gate,
    /// Beat `.1` (0-based) of scripted two-hander `.0` (index into [`LIFE_DIALOGUES`]).
    Dlg(u8, u8),
}

/// A scripted exchange between two village-life residents (`village_life::life_social` plays one
/// when a chatting pair's voices match, instead of two unrelated `Chat` lines): `a` opens and the
/// beats alternate a, b, a, b... Clips are `audio/vo/life/life_dlg_NN_K.ogg` (NN = index + 1, K = beat
/// + 1), cue `LifeCue::Dlg(index, beat)`; a dialogue only plays once ALL its beats are on disk.
/// The ElevenLabs prompts (per voice, v3 tags) are in `docs/audio/elevenlabs-dialogi-wsi.md`.
pub struct LifeDialogue {
    pub a: LifeVoice,
    pub b: LifeVoice,
    pub beats: u8,
}

pub const LIFE_DIALOGUES: &[LifeDialogue] = &[
    LifeDialogue { a: LifeVoice::Man, b: LifeVoice::Woman, beats: 8 }, // 01 the knight's letters
    LifeDialogue { a: LifeVoice::Woman, b: LifeVoice::Man, beats: 9 }, // 02 the squire's grave
    LifeDialogue { a: LifeVoice::Man, b: LifeVoice::Woman, beats: 9 }, // 03 orks are onions
    LifeDialogue { a: LifeVoice::Woman, b: LifeVoice::Man, beats: 9 }, // 04 the swamp witch
    LifeDialogue { a: LifeVoice::Man, b: LifeVoice::Man, beats: 7 }, // 05 the brewer's schnapps
    LifeDialogue { a: LifeVoice::Man, b: LifeVoice::Man, beats: 9 }, // 06 the old wound
    LifeDialogue { a: LifeVoice::Man, b: LifeVoice::Man, beats: 7 }, // 07 a laden goose
    LifeDialogue { a: LifeVoice::Man, b: LifeVoice::Man, beats: 9 }, // 08 the betting pool
    LifeDialogue { a: LifeVoice::Woman, b: LifeVoice::Woman, beats: 10 }, // 09 under the helmet
    LifeDialogue { a: LifeVoice::Woman, b: LifeVoice::Woman, beats: 10 }, // 10 Margit's bread
    LifeDialogue { a: LifeVoice::Woman, b: LifeVoice::Woman, beats: 7 }, // 11 Hamid hums
    LifeDialogue { a: LifeVoice::Woman, b: LifeVoice::Man, beats: 8 }, // 12 the same day
    LifeDialogue { a: LifeVoice::Elder, b: LifeVoice::Man, beats: 9 }, // 13 the monster hunter
    LifeDialogue { a: LifeVoice::Elder, b: LifeVoice::Woman, beats: 11 }, // 14 the monk's diary
    LifeDialogue { a: LifeVoice::Elder, b: LifeVoice::Woman, beats: 7 }, // 15 the dancer
    LifeDialogue { a: LifeVoice::Woman, b: LifeVoice::Man, beats: 9 }, // 16 the shutter
    LifeDialogue { a: LifeVoice::Man, b: LifeVoice::Woman, beats: 7 }, // 17 the outlaw
    LifeDialogue { a: LifeVoice::Man, b: LifeVoice::Man, beats: 8 }, // 18 the stairs
];

/// The catalog line for beat `beat` of dialogue `d`.
pub fn life_dialogue_line(d: u8, beat: u8) -> Option<&'static Line> {
    LINES.iter().find(|l| matches!(l.concept, Concept::Life(_, LifeCue::Dlg(x, k)) if x == d && k == beat))
}

/// Are all of dialogue `d`'s clips recorded and on disk? (Checked once per run.)
pub fn life_dialogue_recorded(d: u8) -> bool {
    static READY: std::sync::OnceLock<Vec<bool>> = std::sync::OnceLock::new();
    READY
        .get_or_init(|| {
            LIFE_DIALOGUES
                .iter()
                .enumerate()
                .map(|(i, dlg)| {
                    (0..dlg.beats).all(|k| {
                        life_dialogue_line(i as u8, k)
                            .and_then(voice_clip_path)
                            .is_some_and(|p| crate::realforest::load::asset_path(&p).is_file())
                    })
                })
                .collect()
        })
        .get(d as usize)
        .copied()
        .unwrap_or(false)
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
    /// Random playback-speed (pitch) range rolled per utterance — `(1.0, 1.0)` = no shift.
    pub pitch: (f32, f32),
    /// Heard through bars / a wall: its subtitle is a dimmer muffled aside that yields to any
    /// ordinary caption instead of replacing it (`Subtitles::say_muffled`).
    pub muffled: bool,
}

/// The voice registry: one entry per [`Speaker`]. Linear-scanned (5 entries).
pub const SPEAKERS: &[(Speaker, SpeakerVoice)] = &[
    (Speaker::Hero,     SpeakerVoice { spatial: false, gain: 1.0,  name: None,              pitch: (1.0,  1.0),  muffled: false }),
    (Speaker::Villager, SpeakerVoice { spatial: true,  gain: 1.4,  name: Some("Townsfolk"), pitch: (1.0,  1.0),  muffled: false }),
    (Speaker::Ork,      SpeakerVoice { spatial: true,  gain: 0.85, name: None,              pitch: (0.82, 1.18), muffled: false }),
    (Speaker::Rival,    SpeakerVoice { spatial: true,  gain: 0.9,  name: Some("Rival"),     pitch: (0.88, 1.12), muffled: false }),
    // The clips are mastered ~13 dB under a townsperson's; the extra gain only claws a little of
    // that back, so a captive stays the quietest voice in the world. A slight pitch spread keeps
    // the cages from sounding like one recorded prisoner.
    (Speaker::Captive,  SpeakerVoice { spatial: true,  gain: 1.6,  name: Some("Captive"),   pitch: (0.95, 1.05), muffled: true  }),
    (Speaker::Life,     SpeakerVoice { spatial: true,  gain: 1.3,  name: Some("Townsfolk"), pitch: (1.0,  1.0),  muffled: false }),
    // Campaign cast: clips mastered like the village-life VO (-16 LUFS per voice), so gain 1.3.
    (Speaker::Cast(Cast::Harrow),  SpeakerVoice { spatial: true, gain: 1.3, name: Some("Ser Godric"), pitch: (1.0, 1.0), muffled: false }),
    (Speaker::Cast(Cast::Maud),    SpeakerVoice { spatial: true, gain: 1.3, name: Some("Maud"),       pitch: (1.0, 1.0), muffled: false }),
    (Speaker::Cast(Cast::Pip),     SpeakerVoice { spatial: true, gain: 1.3, name: Some("Pip"),        pitch: (1.0, 1.0), muffled: false }),
    (Speaker::Cast(Cast::Settler), SpeakerVoice { spatial: true, gain: 1.3, name: Some("Settler"),    pitch: (1.0, 1.0), muffled: false }),
    (Speaker::Cast(Cast::Farmer),  SpeakerVoice { spatial: true, gain: 1.3, name: Some("Farmer"),     pitch: (1.0, 1.0), muffled: false }),
    (Speaker::Cast(Cast::Hamid),   SpeakerVoice { spatial: true, gain: 1.3, name: Some("Hamid"),      pitch: (1.0, 1.0), muffled: false }),
];

pub fn speaker_voice(s: Speaker) -> SpeakerVoice {
    SPEAKERS.iter().find(|(k, _)| *k == s).map(|(_, v)| *v).expect("every Speaker is registered")
}

/// A situation that asks for a line. Triggers (`detect_*` systems) emit one of these; the
/// resolver maps it to candidate [`Line`]s. Biome musings carry the biome so one concept covers
/// all five. The `Reply*` variants are chain targets dispatched by a finished line's `then`.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Concept {
    /// One scripted campaign line, addressed by its clip key (`a1_maud_04`…): exactly that line
    /// plays. Clips live under `audio/vo/campaign/`. Not peaceful — a scripted line cuts through a fight.
    Script(&'static str),
    // ── Hero event reactions (was `HeroEvent`) ──
    Campaign(super::campaign::CampaignLine),
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
    NearFortress,
    NightMusing,
    QuietMusing,
    KillMusing,
    // ── Hero commands — the muster (K): rally the town to follow, or stand it down ──
    MusterCall,
    MusterStandDown,
    // ── Villager ──
    Greeting,
    VillagerArmedJab,
    SiegeFalls,
    Dawn,
    Rescued,
    /// The hero swung at (and harmlessly bonked) a townsperson — they answer with a barbed remark.
    HitByHero,
    // ── Ork ──
    OrkSpot,
    OrkDeath,
    // ── Rival garrison (desert AI opponent) — spatial enemy barks, like the orks. `RivalSpot` is
    //    the catch-all combat bark (aggro / attack cries / gloating taunts / pain), `RivalDeath`
    //    the death cry, `RivalRaidMarch` the cue when their raid sets out, `RivalIdle` the bored
    //    patrol murmur (peaceful — muted once the hero is in a fight). ──
    RivalSpot,
    RivalDeath,
    RivalRaidMarch,
    RivalIdle,
    // ── Chain reply concepts ──
    ReplyToVillagerJab,
    /// Second-level chain: after the hero's comeback, the villager gets the last word.
    VillagerLastWord,
    // ── Guidance / tutorial nudges (hero hint + townsfolk gripe POOLED per concept, so the same
    //    advice sometimes comes as the hero musing, sometimes a peasant nagging — never both at
    //    once). Emitted sparingly by `audio/advice.rs` when the matching town/economy state holds. ──
    AdviseFarm,
    AdviseHouses,
    AdviseWood,
    AdviseStone,
    AdviseUpgrade,
    AdviseWalls,
    AdviseBell,
    PrepNudge,
    PopLost,
    TownThriving,
    // ── Warden (boss) approach — the hero feels the boon worth taking. `WardenSighted` is the
    //    one-per-run generic "why hunt it" teach; `NearWarden(biome)` is the per-warden flavor
    //    (emitted by `boss::boss_proximity`). ──
    WardenSighted,
    NearWarden(Biome),
    // ── New-mechanic / new-place beats (2026-07 coverage pass). These react to milestones the
    //    original catalog predated — the fortress assault, the endgame, world-bosses, the rival,
    //    rune-trials, succession, economy/quest steps. Combat/victory beats are NOT in `is_peaceful`
    //    (they must survive the fight they cap); the calm economy/discovery beats ARE. ──
    /// The Warlord is slain — Gnashfang Hold broken, the run is won (`warlord.rs`). Hero triumph.
    WarlordSlain,
    /// The dying horde despairs as the Warlord falls (`warlord.rs`). Ork — its own concept (not
    /// pooled with `WarlordSlain`) so BOTH the hero cheer and the ork wail fire, per the
    /// `NightWarning`/`SiegeFalls` split-speaker precedent.
    OrkRout,
    /// The Hold's gate is breached — the garrison + Warlord wake (`ork_fortress.rs`). Hero resolve.
    GateBreached,
    /// The garrison's alarm as the gate falls (`ork_fortress.rs`). Ork (split from `GateBreached`).
    OrkBreachAlarm,
    /// The fortress throws its gate open and musters for the night assault (`ork_fortress.rs`). Ork.
    FortressMuster,
    /// A biome Warden (world boss) is slain and its boon claimed (`boss/mod.rs`). Hero.
    WardenSlain,
    /// The rival desert stronghold is destroyed — the raids cease (`rival.rs`). Hero.
    RivalFell,
    /// The rival garrison's lament as their stronghold falls (`rival.rs`). Rival (split from
    /// `RivalFell`).
    RivalLament,
    /// A "Hold the Rune" trial is begun at a landmark shrine (`landmarks.rs`). Hero.
    RuneTrialStart,
    /// A rune-trial is completed — sealed landmark gear granted (`landmarks.rs`). Hero.
    RuneTrialWon,
    /// A named landmark is discovered for the first time (`landmarks.rs`). Hero. (Replaces the
    /// borrowed `ChestOpen` bark discovery used to reuse.)
    LandmarkFound,
    /// An heir takes up the fallen knight's watch — succession (`succession.rs`). Hero (the new one).
    HeirRose,
    /// A War Table upgrade is purchased. Hero.
    UpgradeBought,
    /// A town building goes up (`town.rs` `PlayerBuilt`). Villager cheer + hero note.
    BuildRaised,
    /// A quest-chain step completes (`quest.rs`). Hero.
    QuestDone,
    /// The town's numbers grow — a new villager is born (`town.rs`). Villager.
    VillagerBorn,
    /// The keep falls — defeat (`siege.rs`). Hero's last word.
    KeepLost,
    // ── Caged captives (`audio::captive`) — background murmurs heard through the bars. NOT
    //    peaceful: a cage is always guarded, so the hero is "in danger" whenever he can hear one,
    //    and these are the sound of exactly that. They sit at [`BACKGROUND_PRIORITY`] instead, so
    //    any real line cuts them off and none ever waits on them. ──
    /// The far, wordless layer — sobbing, a cough, a groan.
    CaptiveSob,
    /// A few hopeless words, once the hero is within earshot of them.
    CaptiveMurmur,
    /// An ork at the bars or a fight close by — a frightened gasp or line.
    CaptiveFear,
    /// The hero is at the cage and no jailer is near — a direct plea to him.
    CaptivePlea,
    // ── Village life (`village_life`) — the residents' everyday talk, keyed by voice + situation.
    //    Peaceful: it all falls silent the moment the hero is in a fight. ──
    Life(LifeVoice, LifeCue),
}

/// PEACEFUL concepts — ambient/exploration/economy lines that must fall silent the moment the hero
/// is in a fight (see `HeroThreat`). The director drops these while `in_danger`, so one rule covers
/// what used to be a scatter of per-trigger phase checks (and the gap that let "Quiet day…" play
/// during a warden fight). Everything NOT listed here — combat reactions, warnings, kill barks,
/// enemy taunts, the dawn-relief / wave-survived beats, muster orders — is allowed to cut through a
/// fight. Tunable: move a concept in/out of this list to change whether it survives combat.
pub fn is_peaceful(c: Concept) -> bool {
    use Concept::*;
    matches!(
        c,
        Campaign(_) | Intro | NearTown | NearKids | NearPet | NearGuard | InKeep | NearFortress
            | QuietMusing | BiomeEntered(_)
            | Greeting | VillagerArmedJab | ReplyToVillagerJab | VillagerLastWord
            | AdviseFarm | AdviseHouses | AdviseWood | AdviseStone | AdviseUpgrade | AdviseWalls
            | AdviseBell | PrepNudge | PopLost | TownThriving
            | GoldRich | Broke | LevelUp | Equip | ChestOpen | ShrineHeal | FirstStone | Home
            | RivalIdle
            // New calm beats — discovery/economy chatter that should fall silent in a fight. The
            // combat/victory beats (WarlordSlain, GateBreached, WardenSlain, RivalFell, HeirRose,
            // KeepLost, FortressMuster, RuneTrial*) are deliberately ABSENT — they must cut through.
            | LandmarkFound | UpgradeBought | BuildRaised | QuestDone | VillagerBorn
            | Life(..)
    )
}

/// A follow-up dispatched when a line finishes: ask `target` to look up a line whose
/// `reply_to == Some(concept)`. If none matches the (now-current) facts, nothing plays — the
/// chain self-terminates (the Valve "no explicit interruption" property).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Chain {
    pub concept: Concept,
    pub target: Speaker,
    /// `true` = don't auto-play: offer the reply to the PLAYER as an `E — Talk back` prompt near
    /// the speaker for a few seconds (see `interaction.rs`); unanswered, it expires silently.
    pub manual: bool,
}

/// A villager's at-the-hero jab → the hero MAY fire back: offered to the player (`manual`), not
/// auto-played. Used as the `then` on the `pa_*` jab lines; resolved against the hero's
/// `ReplyToVillagerJab` reply pool when the player takes it.
const REPLY_TO_JAB: Chain =
    Chain { concept: Concept::ReplyToVillagerJab, target: Speaker::Hero, manual: true };

/// Second link: some hero comebacks hand the exchange BACK to the villager for a parting shot
/// (jab → comeback → last word, then the chain ends — no `then` on the last-word pool). The NPC
/// answers on his own, so this one stays automatic.
const LAST_WORD: Chain =
    Chain { concept: Concept::VillagerLastWord, target: Speaker::Villager, manual: false };

/// One voice line — the whole record.
#[derive(Clone, Copy)]
pub struct Line {
    /// Stable key; also the clip stem at `audio/vo/<dir>/<id>.ogg` (dir per speaker).
    pub id: &'static str,
    pub speaker: Speaker,
    pub concept: Concept,
    /// Transcript: the on-screen subtitle AND our in-code record of the quote.
    pub text: &'static str,
    /// Planned lines without a bundled recording stay silent and are not preloaded.
    pub recorded: bool,
    /// May a louder/just-as-loud new line cut this off mid-clip?
    pub interruptible: bool,
    /// Barge-in priority: a new line plays over a playing one only if `new.priority >= cur.priority`.
    pub priority: u8,
    /// Plays at most once this often (seconds); 0 = no floor. Per-line replay throttle.
    pub floor: f32,
    /// Plays at most ONCE per run (e.g. "first kill"); reset on a fresh run.
    pub once: bool,
    /// If set, this line is a valid reply to a dispatched chain `Concept`.
    pub reply_to: Option<Concept>,
    /// If set, dispatch this chain when the line finishes.
    pub then: Option<Chain>,
}

/// Convenience constructor for the common case (no reply_to / no then, interruptible, prio 10).
const fn line(id: &'static str, speaker: Speaker, concept: Concept, text: &'static str) -> Line {
    Line {
        id, speaker, concept, text, recorded: true,
        interruptible: true, priority: 10, floor: 0.0, once: false,
        reply_to: None, then: None,
    }
}

/// A village-life line (`village_life`): spatial at the speaker, low priority (anything real cuts
/// it, and it never interrupts one), interruptible, with a long replay floor so the same quip
/// doesn't come round twice in a visit. Transcripts are the catalogue text WITHOUT the v3 tags.
const fn life(id: &'static str, voice: LifeVoice, cue: LifeCue, text: &'static str) -> Line {
    Line { priority: 5, floor: 150.0, ..line(id, Speaker::Life, Concept::Life(voice, cue), text) }
}

/// A scripted campaign line: fired by key via `Speak::new(Concept::Script(id))`, high priority and
/// not interruptible, so a barking villager can't talk over the story. Text is the subtitle
/// (the ElevenLabs prompt minus its v3 tags; the full prompts are in `docs/audio/elevenlabs-akt-1.md`).
const fn script(id: &'static str, speaker: Speaker, text: &'static str) -> Line {
    Line { priority: 20, interruptible: false, ..line(id, speaker, Concept::Script(id), text) }
}

/// A scripted line written but not recorded yet: in the catalogue, silent until `recorded` flips.
const fn script_planned(id: &'static str, speaker: Speaker, text: &'static str) -> Line {
    Line { recorded: false, ..script(id, speaker, text) }
}

/// THE catalog. Filled in across the migration tasks (Phase C).
pub const LINES: &[Line] = &[
    // ── Village life (`docs/audio/elevenlabs-zycie-wsi.md`; clips `audio/vo/life/<id>.ogg`) ──
    // Voices (ElevenLabs v3, DO NOT change on re-takes): m=Darby Skelm, w=MoanElisa, v=Luna, e=Alder, c=Omar J, g=Wilf. See assets/audio/vo/life/VOICES.md.
    // Man
    life("life_m_greet_1", LifeVoice::Man, LifeCue::Greet, "M'lord."),
    life("life_m_greet_2", LifeVoice::Man, LifeCue::Greet, "Morning, Ser Godric. Or what's left of it."),
    life("life_m_greet_3", LifeVoice::Man, LifeCue::Greet, "Ah, the armour's out for a walk. Good day to it."),
    life("life_m_buy_1", LifeVoice::Man, LifeCue::Ask, "How much for the bread?"),
    life("life_m_buy_2", LifeVoice::Man, LifeCue::Haggle, "Three pennies? For that? It's mostly air!"),
    life("life_m_buy_3", LifeVoice::Man, LifeCue::Agree, "Fine. Fine. Robbery, but fine."),
    life("life_m_buy_4", LifeVoice::Man, LifeCue::Ask, "Any salt today?"),
    life("life_m_chat_1", LifeVoice::Man, LifeCue::Chat, "Did you hear the bell last night? Course you did. Everyone hears the bell."),
    life("life_m_chat_2", LifeVoice::Man, LifeCue::Chat, "Fence is down again by the barley. Third time."),
    life("life_m_chat_3", LifeVoice::Man, LifeCue::Chat, "He fell asleep on the woodpile. Snoring like a bear."),
    life("life_m_chat_4", LifeVoice::Man, LifeCue::Chat, "They say the knight never takes that helmet off. Not even to eat."),
    life("life_m_sit", LifeVoice::Man, LifeCue::Sit, "Oh, my back. Oh, that's better."),
    life("life_m_stand", LifeVoice::Man, LifeCue::Stand, "Right. Up we get."),
    life("life_m_eat", LifeVoice::Man, LifeCue::Eat, "Hm. Stale. Again."),
    life("life_m_work_1", LifeVoice::Man, LifeCue::Work, "Hup!"),
    life("life_m_work_2", LifeVoice::Man, LifeCue::Work, "Come on, you stubborn thing!"),
    life("life_m_work_3", LifeVoice::Man, LifeCue::WorkDone, "That's the last of it. Till tomorrow."),
    life("life_m_yawn", LifeVoice::Man, LifeCue::Yawn, "Hhhaaah. Too early for living."),
    life("life_m_laugh", LifeVoice::Man, LifeCue::Laugh, "(laughs heartily)"),
    life("life_m_dusk", LifeVoice::Man, LifeCue::Dusk, "Sun's going. Best get inside."),
    life("life_m_kid", LifeVoice::Man, LifeCue::Scold, "Oi! Get down off that cart!"),
    // Woman
    life("life_w_greet_1", LifeVoice::Woman, LifeCue::Greet, "Ser Godric. Mind the chickens."),
    life("life_w_greet_2", LifeVoice::Woman, LifeCue::Greet, "Oh, it's you. Wipe your boots."),
    life("life_w_buy_1", LifeVoice::Woman, LifeCue::Ask, "Two eggs and the cabbage. And not the one with the worm."),
    life("life_w_buy_2", LifeVoice::Woman, LifeCue::Haggle, "I'll give you two pennies. Not a crumb more."),
    life("life_w_buy_3", LifeVoice::Woman, LifeCue::Agree, "Pleasure doing business. Mostly."),
    life("life_w_chat_1", LifeVoice::Woman, LifeCue::Chat, "She's walking out with the cooper's boy. The cooper's boy!"),
    life("life_w_chat_2", LifeVoice::Woman, LifeCue::Chat, "Need rain for the beans. And none of us need orks."),
    life("life_w_chat_3", LifeVoice::Woman, LifeCue::Chat, "He thinks I didn't see him with the ale. I see everything."),
    life("life_w_chat_4", LifeVoice::Woman, LifeCue::Chat, "Pip's not sleeping. Up the tower at all hours with that rope."),
    life("life_w_laundry", LifeVoice::Woman, LifeCue::Laundry, "Wash it, hang it, it rains. Every single time."),
    life("life_w_sweep", LifeVoice::Woman, LifeCue::Sweep, "Dust, mud, dust, mud."),
    life("life_w_water", LifeVoice::Woman, LifeCue::Water, "Hnn. Heavier every day, this bucket."),
    life("life_w_call_kid", LifeVoice::Woman, LifeCue::CallKid, "Tom! Supper! Now, not in a minute!"),
    life("life_w_scold", LifeVoice::Woman, LifeCue::Scold, "What did I say about the well?"),
    life("life_w_dusk", LifeVoice::Woman, LifeCue::Dusk, "Shutters! Everyone, shutters!"),
    life("life_w_laugh", LifeVoice::Woman, LifeCue::Laugh, "(laughs)"),
    life("life_w_sit", LifeVoice::Woman, LifeCue::Sit, "Ah. Five minutes."),
    // Vendor
    life("life_v_call_1", LifeVoice::Vendor, LifeCue::Hawk, "Bread! Fresh bread! Fresh-ish!"),
    life("life_v_call_2", LifeVoice::Vendor, LifeCue::Hawk, "Cabbages, onions, turnips the orks missed!"),
    life("life_v_call_3", LifeVoice::Vendor, LifeCue::Hawk, "Pots! Good pots! Don't leak! Much!"),
    life("life_v_haggle_1", LifeVoice::Vendor, LifeCue::Price, "Three pennies, love. Times are hard."),
    life("life_v_haggle_2", LifeVoice::Vendor, LifeCue::Counter, "Two? You'll starve me! Fine. Two and a half."),
    life("life_v_haggle_3", LifeVoice::Vendor, LifeCue::Price, "For you? Same price as everyone. But I'll smile."),
    life("life_v_sold", LifeVoice::Vendor, LifeCue::Sold, "Done! Mind how you go."),
    life("life_v_hero_1", LifeVoice::Vendor, LifeCue::Tease, "Shiny armour like that, you can afford the good loaf."),
    life("life_v_hero_2", LifeVoice::Vendor, LifeCue::Tease, "Does the knight eat? Or does he just glare at bread?"),
    life("life_v_slow", LifeVoice::Vendor, LifeCue::Slow, "Quiet day. Even the flies are thinking twice."),
    life("life_v_laugh", LifeVoice::Vendor, LifeCue::Laugh, "(laughs brightly)"),
    // Elder
    life("life_e_greet", LifeVoice::Elder, LifeCue::Greet, "Eh? Oh. The knight. Taller than I thought."),
    life("life_e_chat_1", LifeVoice::Elder, LifeCue::Chat, "In my day we had proper winters. Snow up to your ears."),
    life("life_e_chat_2", LifeVoice::Elder, LifeCue::Chat, "Young ones. No patience. Couldn't wait for a kettle."),
    life("life_e_chat_3", LifeVoice::Elder, LifeCue::Chat, "My grandfather said this fort was cursed. Never said why."),
    life("life_e_doze", LifeVoice::Elder, LifeCue::Doze, "Mm. Mmm. I'm awake!"),
    life("life_e_whittle", LifeVoice::Elder, LifeCue::Whittle, "Hmm-hmm, hmm-hmm."),
    life("life_e_cough", LifeVoice::Elder, LifeCue::Cough, "Damp. It's always the damp."),
    life("life_e_stand", LifeVoice::Elder, LifeCue::Stand, "Up. Up. Bones like dry sticks."),
    life("life_e_laugh", LifeVoice::Elder, LifeCue::Laugh, "(wheezy laugh)"),
    // Child
    life("life_c_tag", LifeVoice::Child, LifeCue::Tag, "Tag! You're it!"),
    life("life_c_unfair", LifeVoice::Child, LifeCue::Unfair, "Not fair! You cheated!"),
    life("life_c_run", LifeVoice::Child, LifeCue::Run, "Can't catch me!"),
    life("life_c_knight_1", LifeVoice::Child, LifeCue::Knight, "Look. It's the knight."),
    life("life_c_knight_2", LifeVoice::Child, LifeCue::Knight, "Is it hot in there? In the helmet?"),
    life("life_c_knight_3", LifeVoice::Child, LifeCue::Knight, "Can I hold the sword? Just once?"),
    life("life_c_mum", LifeVoice::Child, LifeCue::Mum, "Mu-um! He pushed me!"),
    life("life_c_laugh", LifeVoice::Child, LifeCue::Laugh, "(laughs uncontrollably)"),
    life("life_c_hide", LifeVoice::Child, LifeCue::Hide, "Shh! I'm hiding!"),
    life("life_c_count", LifeVoice::Child, LifeCue::Count, "One, two, three, four, five... coming!"),
    // Guard
    life("life_g_greet_1", LifeVoice::Guard, LifeCue::Greet, "M'lord."),
    life("life_g_greet_2", LifeVoice::Guard, LifeCue::Greet, "All quiet. For now."),
    life("life_g_patrol", LifeVoice::Guard, LifeCue::Patrol, "Wall, wall, more wall. Lovely wall."),
    life("life_g_gate", LifeVoice::Guard, LifeCue::Gate, "Gate shuts at dusk. No exceptions."),
    life("life_g_kid", LifeVoice::Guard, LifeCue::Scold, "You. Off the rampart. Now."),
    life("life_g_yawn", LifeVoice::Guard, LifeCue::Yawn, "Hhh. Who scheduled the dawn so early."),
    life("life_g_dusk", LifeVoice::Guard, LifeCue::Dusk, "Bell's soon. Torches lit, eyes open."),
    // -- Village-life two-handers (`LIFE_DIALOGUES`; prompts in `docs/audio/elevenlabs-dialogi-wsi.md`).
    // Text = transcript; silent until the clip is on disk. Trigger: a chatting pair whose voices match.
    // 01 the knight's letters
    life("life_dlg_01_1", LifeVoice::Man, LifeCue::Dlg(0, 0), "The Reeve was reading the knight his letters again. Out loud. In the square."),
    life("life_dlg_01_2", LifeVoice::Woman, LifeCue::Dlg(0, 1), "It's his eyes. Since the axe."),
    life("life_dlg_01_3", LifeVoice::Man, LifeCue::Dlg(0, 2), "His eyes are fine. He spotted a ham on my windowsill from the gate."),
    life("life_dlg_01_4", LifeVoice::Woman, LifeCue::Dlg(0, 3), "Ham's different. Ham is a calling."),
    life("life_dlg_01_5", LifeVoice::Man, LifeCue::Dlg(0, 4), "My brother served in the eastern campaign. Says Ser Godric used to write poems. In the margins of the casualty lists."),
    life("life_dlg_01_6", LifeVoice::Woman, LifeCue::Dlg(0, 5), "Lovely."),
    life("life_dlg_01_7", LifeVoice::Man, LifeCue::Dlg(0, 6), "Bit grim, Edda."),
    life("life_dlg_01_8", LifeVoice::Woman, LifeCue::Dlg(0, 7), "Well, he doesn't write anything now. So that's an improvement for everyone."),
    // 02 the squire's grave
    life("life_dlg_02_1", LifeVoice::Woman, LifeCue::Dlg(1, 0), "Somebody leaves flowers on the squire's grave. Every morning. Fresh ones."),
    life("life_dlg_02_2", LifeVoice::Man, LifeCue::Dlg(1, 1), "The empty one? There's nobody under it."),
    life("life_dlg_02_3", LifeVoice::Woman, LifeCue::Dlg(1, 2), "Doesn't stop the flowers."),
    life("life_dlg_02_4", LifeVoice::Man, LifeCue::Dlg(1, 3), "The baker's girl, maybe. She was sweet on him on the boat."),
    life("life_dlg_02_5", LifeVoice::Woman, LifeCue::Dlg(1, 4), "She was sweet on everyone on that boat. And she's never up before noon."),
    life("life_dlg_02_6", LifeVoice::Man, LifeCue::Dlg(1, 5), "Then who?"),
    life("life_dlg_02_7", LifeVoice::Woman, LifeCue::Dlg(1, 6), "I couldn't sleep last night. Saw a big shape by the gate. In armour. Just standing there."),
    life("life_dlg_02_8", LifeVoice::Man, LifeCue::Dlg(1, 7), "So the knight was mourning his squire. That's nice. That's a nice thing."),
    life("life_dlg_02_9", LifeVoice::Woman, LifeCue::Dlg(1, 8), "He kept saying sorry. Over and over. In a different voice."),
    // 03 orks are onions
    life("life_dlg_03_1", LifeVoice::Man, LifeCue::Dlg(2, 0), "You know what orks are like? Onions."),
    life("life_dlg_03_2", LifeVoice::Woman, LifeCue::Dlg(2, 1), "They make you cry?"),
    life("life_dlg_03_3", LifeVoice::Man, LifeCue::Dlg(2, 2), "Layers. Hide, then mail, then more hide. Then a sort of second hide."),
    life("life_dlg_03_4", LifeVoice::Woman, LifeCue::Dlg(2, 3), "You've been peeling orks, Jory?"),
    life("life_dlg_03_5", LifeVoice::Man, LifeCue::Dlg(2, 4), "Only the one. For learning."),
    life("life_dlg_03_6", LifeVoice::Woman, LifeCue::Dlg(2, 5), "And what's in the middle?"),
    life("life_dlg_03_7", LifeVoice::Man, LifeCue::Dlg(2, 6), "Teeth. It's teeth all the way down."),
    life("life_dlg_03_8", LifeVoice::Woman, LifeCue::Dlg(2, 7), "I'm not eating your stew tonight."),
    life("life_dlg_03_9", LifeVoice::Man, LifeCue::Dlg(2, 8), "It's turnip! ...It's mostly turnip."),
    // 04 the swamp witch
    life("life_dlg_04_1", LifeVoice::Woman, LifeCue::Dlg(3, 0), "Marek walked out to the swamp witch. For a wish."),
    life("life_dlg_04_2", LifeVoice::Man, LifeCue::Dlg(3, 1), "And?"),
    life("life_dlg_04_3", LifeVoice::Woman, LifeCue::Dlg(3, 2), "Came back with nine fingers and a goat."),
    life("life_dlg_04_4", LifeVoice::Man, LifeCue::Dlg(3, 3), "He wished for a goat?"),
    life("life_dlg_04_5", LifeVoice::Woman, LifeCue::Dlg(3, 4), "He wished for a wife."),
    life("life_dlg_04_6", LifeVoice::Man, LifeCue::Dlg(3, 5), "...And the goat?"),
    life("life_dlg_04_7", LifeVoice::Woman, LifeCue::Dlg(3, 6), "We don't ask about the goat, Will."),
    life("life_dlg_04_8", LifeVoice::Man, LifeCue::Dlg(3, 7), "Did it work, at least? The wish?"),
    life("life_dlg_04_9", LifeVoice::Woman, LifeCue::Dlg(3, 8), "He's very happy. That's the worrying part."),
    // 05 the brewer's schnapps
    life("life_dlg_05_1", LifeVoice::Man, LifeCue::Dlg(4, 0), "Brewer's got a new schnapps. Drink it before bed, and if you die, you wake up right where you drank it."),
    life("life_dlg_05_2", LifeVoice::Man, LifeCue::Dlg(4, 1), "And has anyone tested that?"),
    life("life_dlg_05_3", LifeVoice::Man, LifeCue::Dlg(4, 2), "Hob did. Twice."),
    life("life_dlg_05_4", LifeVoice::Man, LifeCue::Dlg(4, 3), "Did it work?"),
    life("life_dlg_05_5", LifeVoice::Man, LifeCue::Dlg(4, 4), "Well. The first time he woke up."),
    life("life_dlg_05_6", LifeVoice::Man, LifeCue::Dlg(4, 5), "And the second?"),
    life("life_dlg_05_7", LifeVoice::Man, LifeCue::Dlg(4, 6), "We're giving it a few more days."),
    // 06 the old wound
    life("life_dlg_06_1", LifeVoice::Man, LifeCue::Dlg(5, 0), "I was a soldier once, you know. Like him. Proper adventurer."),
    life("life_dlg_06_2", LifeVoice::Man, LifeCue::Dlg(5, 1), "What happened?"),
    life("life_dlg_06_3", LifeVoice::Man, LifeCue::Dlg(5, 2), "Took an ork spear in the..."),
    life("life_dlg_06_4", LifeVoice::Man, LifeCue::Dlg(5, 3), "Don't you dare say knee."),
    life("life_dlg_06_5", LifeVoice::Man, LifeCue::Dlg(5, 4), "Arse, Wendel. Took it in the arse."),
    life("life_dlg_06_6", LifeVoice::Man, LifeCue::Dlg(5, 5), "...Oh."),
    life("life_dlg_06_7", LifeVoice::Man, LifeCue::Dlg(5, 6), "Can't sit a horse. Can't sit a bench. Can barely sit in judgement."),
    life("life_dlg_06_8", LifeVoice::Man, LifeCue::Dlg(5, 7), "Bet you'll be first up on the wall tonight, then."),
    life("life_dlg_06_9", LifeVoice::Man, LifeCue::Dlg(5, 8), "Well, I'm not sitting down, am I."),
    // 07 a laden goose
    life("life_dlg_07_1", LifeVoice::Man, LifeCue::Dlg(6, 0), "How much do you reckon a goose can carry?"),
    life("life_dlg_07_2", LifeVoice::Man, LifeCue::Dlg(6, 1), "A goose?"),
    life("life_dlg_07_3", LifeVoice::Man, LifeCue::Dlg(6, 2), "In flight. Fully laden."),
    life("life_dlg_07_4", LifeVoice::Man, LifeCue::Dlg(6, 3), "Is this a riddle, or are you trying to send letters home again?"),
    life("life_dlg_07_5", LifeVoice::Man, LifeCue::Dlg(6, 4), "My mother's not heard from me since the wreck. She thinks I drowned with the squire."),
    life("life_dlg_07_6", LifeVoice::Man, LifeCue::Dlg(6, 5), "Then let her. You owe her money."),
    life("life_dlg_07_7", LifeVoice::Man, LifeCue::Dlg(6, 6), "...A goose could carry a small apology."),
    // 08 the betting pool
    life("life_dlg_08_1", LifeVoice::Man, LifeCue::Dlg(7, 0), "Pool's open for tonight. Two pennies says the cooper's boy doesn't see harvest."),
    life("life_dlg_08_2", LifeVoice::Man, LifeCue::Dlg(7, 1), "That's monstrous. He's nine."),
    life("life_dlg_08_3", LifeVoice::Man, LifeCue::Dlg(7, 2), "Odds are good, though."),
    life("life_dlg_08_4", LifeVoice::Man, LifeCue::Dlg(7, 3), "...What odds?"),
    life("life_dlg_08_5", LifeVoice::Man, LifeCue::Dlg(7, 4), "Four to one."),
    life("life_dlg_08_6", LifeVoice::Man, LifeCue::Dlg(7, 5), "Three pennies, then. On him living. Little bugger's quick."),
    life("life_dlg_08_7", LifeVoice::Man, LifeCue::Dlg(7, 6), "That's the spirit. Nobody's betting on you, by the way."),
    life("life_dlg_08_8", LifeVoice::Man, LifeCue::Dlg(7, 7), "Nobody?"),
    life("life_dlg_08_9", LifeVoice::Man, LifeCue::Dlg(7, 8), "Couldn't find takers. Either way."),
    // 09 under the helmet
    life("life_dlg_09_1", LifeVoice::Woman, LifeCue::Dlg(8, 0), "Is that knight ever going to take his helmet off?"),
    life("life_dlg_09_2", LifeVoice::Woman, LifeCue::Dlg(8, 1), "My sister says he's very handsome under there."),
    life("life_dlg_09_3", LifeVoice::Woman, LifeCue::Dlg(8, 2), "Your sister's never seen under there."),
    life("life_dlg_09_4", LifeVoice::Woman, LifeCue::Dlg(8, 3), "That's why she's so sure."),
    life("life_dlg_09_5", LifeVoice::Woman, LifeCue::Dlg(8, 4), "Old Bram says the axe took half his face. Says he eats through the visor. Soup only."),
    life("life_dlg_09_6", LifeVoice::Woman, LifeCue::Dlg(8, 5), "Bram also says he once fought a bear for a wife. And lost."),
    life("life_dlg_09_7", LifeVoice::Woman, LifeCue::Dlg(8, 6), "He did lose. You've met her."),
    life("life_dlg_09_8", LifeVoice::Woman, LifeCue::Dlg(8, 7), "...Fair."),
    life("life_dlg_09_9", LifeVoice::Woman, LifeCue::Dlg(8, 8), "Still. Soup only. Poor lamb."),
    life("life_dlg_09_10", LifeVoice::Woman, LifeCue::Dlg(8, 9), "My sister says she'd make him soup."),
    // 10 Margit's bread
    life("life_dlg_10_1", LifeVoice::Woman, LifeCue::Dlg(9, 0), "Margit's bread's gone up a penny again."),
    life("life_dlg_10_2", LifeVoice::Woman, LifeCue::Dlg(9, 1), "And down a size. I could post it through the keyhole."),
    life("life_dlg_10_3", LifeVoice::Woman, LifeCue::Dlg(9, 2), "Found a tooth in mine yesterday."),
    life("life_dlg_10_4", LifeVoice::Woman, LifeCue::Dlg(9, 3), "Margit's?"),
    life("life_dlg_10_5", LifeVoice::Woman, LifeCue::Dlg(9, 4), "Not Margit's. Not anybody's I know. Long. Pointy."),
    life("life_dlg_10_6", LifeVoice::Woman, LifeCue::Dlg(9, 5), "Well, the orks did get into her mill last month..."),
    life("life_dlg_10_7", LifeVoice::Woman, LifeCue::Dlg(9, 6), "Don't."),
    life("life_dlg_10_8", LifeVoice::Woman, LifeCue::Dlg(9, 7), "Grinds very fine, that mill."),
    life("life_dlg_10_9", LifeVoice::Woman, LifeCue::Dlg(9, 8), "I said don't!"),
    life("life_dlg_10_10", LifeVoice::Woman, LifeCue::Dlg(9, 9), "Shh, here she comes. Lovely loaves, Margit!"),
    // 11 Hamid hums
    life("life_dlg_11_1", LifeVoice::Woman, LifeCue::Dlg(10, 0), "That southerner they pulled out of the cage. Hamid. He hums at sundown."),
    life("life_dlg_11_2", LifeVoice::Woman, LifeCue::Dlg(10, 1), "Everybody hums."),
    life("life_dlg_11_3", LifeVoice::Woman, LifeCue::Dlg(10, 2), "Not their songs. The orks'. The drum one."),
    life("life_dlg_11_4", LifeVoice::Woman, LifeCue::Dlg(10, 3), "Four months in a cage, I'd hum anything too."),
    life("life_dlg_11_5", LifeVoice::Woman, LifeCue::Dlg(10, 4), "He stops when you look at him. Then he smiles and tries to sell you a carpet."),
    life("life_dlg_11_6", LifeVoice::Woman, LifeCue::Dlg(10, 5), "Did you buy one?"),
    life("life_dlg_11_7", LifeVoice::Woman, LifeCue::Dlg(10, 6), "Half price. It's lovely."),
    // 12 the same day
    life("life_dlg_12_1", LifeVoice::Woman, LifeCue::Dlg(11, 0), "Do you ever feel like we live the same day, over and over?"),
    life("life_dlg_12_2", LifeVoice::Man, LifeCue::Dlg(11, 1), "Bell. Orks. Bury someone. Bell."),
    life("life_dlg_12_3", LifeVoice::Woman, LifeCue::Dlg(11, 2), "Bury someone, bell, orks..."),
    life("life_dlg_12_4", LifeVoice::Man, LifeCue::Dlg(11, 3), "It's a circle, Agnes. That's a circle."),
    life("life_dlg_12_5", LifeVoice::Woman, LifeCue::Dlg(11, 4), "Pip's found scratches up the tower. Little tally marks. Hundreds of them."),
    life("life_dlg_12_6", LifeVoice::Man, LifeCue::Dlg(11, 5), "Not his. Pip's been here a month."),
    life("life_dlg_12_7", LifeVoice::Woman, LifeCue::Dlg(11, 6), "Then whose?"),
    life("life_dlg_12_8", LifeVoice::Man, LifeCue::Dlg(11, 7), "...Someone with a lot of free time and no window."),
    // 13 the monster hunter
    life("life_dlg_13_1", LifeVoice::Elder, LifeCue::Dlg(12, 0), "When I was your age, we fought orks with a rake."),
    life("life_dlg_13_2", LifeVoice::Man, LifeCue::Dlg(12, 1), "And did it work?"),
    life("life_dlg_13_3", LifeVoice::Elder, LifeCue::Dlg(12, 2), "No. That's why I'm still angry about it."),
    life("life_dlg_13_4", LifeVoice::Man, LifeCue::Dlg(12, 3), "Should've hired a monster hunter."),
    life("life_dlg_13_5", LifeVoice::Elder, LifeCue::Dlg(12, 4), "Had one once. Cat's eyes, white hair, two swords."),
    life("life_dlg_13_6", LifeVoice::Man, LifeCue::Dlg(12, 5), "Any good?"),
    life("life_dlg_13_7", LifeVoice::Elder, LifeCue::Dlg(12, 6), "Charged forty crowns for a drowner and moaned about the weather the whole time."),
    life("life_dlg_13_8", LifeVoice::Man, LifeCue::Dlg(12, 7), "Sounds like you."),
    life("life_dlg_13_9", LifeVoice::Elder, LifeCue::Dlg(12, 8), "His horse was nicer than me. Smarter, too. Kept changing its name."),
    // 14 the monk's diary
    life("life_dlg_14_1", LifeVoice::Elder, LifeCue::Dlg(13, 0), "This fort's seen worse winters than this."),
    life("life_dlg_14_2", LifeVoice::Woman, LifeCue::Dlg(13, 1), "It's summer, Grandad."),
    life("life_dlg_14_3", LifeVoice::Elder, LifeCue::Dlg(13, 2), "Then it's seen worse summers. There was a colony here before us, you know. Hundred years back."),
    life("life_dlg_14_4", LifeVoice::Woman, LifeCue::Dlg(13, 3), "What happened to them?"),
    life("life_dlg_14_5", LifeVoice::Elder, LifeCue::Dlg(13, 4), "Same as us. Bell, orks, bury someone."),
    life("life_dlg_14_6", LifeVoice::Woman, LifeCue::Dlg(13, 5), "And then?"),
    life("life_dlg_14_7", LifeVoice::Elder, LifeCue::Dlg(13, 6), "Then there was nobody left to ring it. Found a page of their monk's diary in the old chapel."),
    life("life_dlg_14_8", LifeVoice::Woman, LifeCue::Dlg(13, 7), "What did it say?"),
    life("life_dlg_14_9", LifeVoice::Elder, LifeCue::Dlg(13, 8), "Can't read, can I? Used it to light the stove."),
    life("life_dlg_14_10", LifeVoice::Woman, LifeCue::Dlg(13, 9), "Grandad!"),
    life("life_dlg_14_11", LifeVoice::Elder, LifeCue::Dlg(13, 10), "Lovely flame. Very holy."),
    // 15 the dancer
    life("life_dlg_15_1", LifeVoice::Elder, LifeCue::Dlg(14, 0), "Your mother was the finest dancer on the whole east coast."),
    life("life_dlg_15_2", LifeVoice::Woman, LifeCue::Dlg(14, 1), "You never met my mother."),
    life("life_dlg_15_3", LifeVoice::Elder, LifeCue::Dlg(14, 2), "I'm being polite. Was she a good dancer?"),
    life("life_dlg_15_4", LifeVoice::Woman, LifeCue::Dlg(14, 3), "She had one leg."),
    life("life_dlg_15_5", LifeVoice::Elder, LifeCue::Dlg(14, 4), "...Then she must've been tremendous at it."),
    life("life_dlg_15_6", LifeVoice::Woman, LifeCue::Dlg(14, 5), "She was, actually. Hopped the whole harvest reel. Won a pig."),
    life("life_dlg_15_7", LifeVoice::Elder, LifeCue::Dlg(14, 6), "There you are. Finest dancer on the east coast."),
    // 16 the shutter
    life("life_dlg_16_1", LifeVoice::Woman, LifeCue::Dlg(15, 0), "Did you fix the shutter like I asked?"),
    life("life_dlg_16_2", LifeVoice::Man, LifeCue::Dlg(15, 1), "I looked at it. Very carefully."),
    life("life_dlg_16_3", LifeVoice::Woman, LifeCue::Dlg(15, 2), "And?"),
    life("life_dlg_16_4", LifeVoice::Man, LifeCue::Dlg(15, 3), "It's definitely broken."),
    life("life_dlg_16_5", LifeVoice::Woman, LifeCue::Dlg(15, 4), "The orks will come right through it, Piet."),
    life("life_dlg_16_6", LifeVoice::Man, LifeCue::Dlg(15, 5), "Then they'll be in the larder. And they'll see what you cook. And they'll leave."),
    life("life_dlg_16_7", LifeVoice::Woman, LifeCue::Dlg(15, 6), "...Sleep in the barn tonight."),
    life("life_dlg_16_8", LifeVoice::Man, LifeCue::Dlg(15, 7), "Barn's gone, love."),
    life("life_dlg_16_9", LifeVoice::Woman, LifeCue::Dlg(15, 8), "Then sleep where the barn was."),
    // 17 the outlaw
    life("life_dlg_17_1", LifeVoice::Man, LifeCue::Dlg(16, 0), "Heard there's a fellow in the western woods robbing the Crown's men and giving it all to the poor."),
    life("life_dlg_17_2", LifeVoice::Woman, LifeCue::Dlg(16, 1), "Giving it to who?"),
    life("life_dlg_17_3", LifeVoice::Man, LifeCue::Dlg(16, 2), "The poor."),
    life("life_dlg_17_4", LifeVoice::Woman, LifeCue::Dlg(16, 3), "We're the poor. Nobody's given us anything."),
    life("life_dlg_17_5", LifeVoice::Man, LifeCue::Dlg(16, 4), "Well, he's mostly giving it to himself. He's very poor too."),
    life("life_dlg_17_6", LifeVoice::Woman, LifeCue::Dlg(16, 5), "Then he's just a robber."),
    life("life_dlg_17_7", LifeVoice::Man, LifeCue::Dlg(16, 6), "He's a robber with a lovely hat."),
    // 18 the stairs
    life("life_dlg_18_1", LifeVoice::Man, LifeCue::Dlg(17, 0), "Why doesn't the knight ever go up the tower?"),
    life("life_dlg_18_2", LifeVoice::Man, LifeCue::Dlg(17, 1), "Bad knee. From the campaign."),
    life("life_dlg_18_3", LifeVoice::Man, LifeCue::Dlg(17, 2), "He ran up the wall steps last night. Three at a time. With an ork on his back."),
    life("life_dlg_18_4", LifeVoice::Man, LifeCue::Dlg(17, 3), "Wall steps aren't stairs. They're more of a slope with ambitions."),
    life("life_dlg_18_5", LifeVoice::Man, LifeCue::Dlg(17, 4), "And he talks about himself like he's somebody else. 'Ser Godric will see to it.'"),
    life("life_dlg_18_6", LifeVoice::Man, LifeCue::Dlg(17, 5), "Lords do that. My old lord called himself 'we'. Even on the privy."),
    life("life_dlg_18_7", LifeVoice::Man, LifeCue::Dlg(17, 6), "Both of them?"),
    life("life_dlg_18_8", LifeVoice::Man, LifeCue::Dlg(17, 7), "There was only him, Osric. That's the point."),

    // ── Campaign Prologue + Act I (`docs/audio/elevenlabs-akt-1.md`; clips `audio/vo/campaign/<id>.ogg`) ──
    // Voices (DO NOT change on re-takes): harrow=Julian, wat=Sully, maud=MoanElisa, pip=Omar J, settler=Wilf,
    // farmer=Darby Skelm, hamid=Sal, ork/shaman=Dante. See assets/audio/vo/campaign/VOICES.md.
    // Trigger: none wired yet. Play one by key with `Speak::new(Concept::Script("a1_maud_04"))` (or
    // `Speak::at` to place a cast voice). The trailing comment on each line is the scene it was written for.
    script("a1_harrow_01", Speaker::Cast(Cast::Harrow), "Tighter. You've done that strap every day for fifteen years and it's still wrong."), // P.0 cabin
    script("a1_harrow_02", Speaker::Cast(Cast::Harrow), "Forty peasants and a Reeve. That's what the Crown sends a man after the eastern campaign."), // P.0 cabin
    script("a1_harrow_03", Speaker::Cast(Cast::Harrow), "Do you know what they said about me in the city? Before it burned?"), // P.0 cabin
    script("a1_harrow_04", Speaker::Cast(Cast::Harrow), "Neither do I. Nobody looks at the man behind the shield, Wat. That's the point of you."), // P.0 cabin
    script("a1_harrow_05", Speaker::Cast(Cast::Harrow), "Left. It's always the left."), // P.0 cabin
    script("a1_harrow_06", Speaker::Cast(Cast::Harrow), "The helmet goes on the chest, Wat. Not near it. On it."), // P.0 cabin
    script("a1_harrow_07", Speaker::Cast(Cast::Harrow), "The letter. To the Reeve. Today, if the sea allows."), // P.0 cabin
    script("a1_harrow_08", Speaker::Cast(Cast::Harrow), "Stop hovering."), // P.0 cabin
    script("a1_harrow_09", Speaker::Cast(Cast::Harrow), "Sleep, Wat. I'll want you at first light, and I'll want you awake."), // P.0 cabin
    script("a1_wat_01", Speaker::Hero, "Yes, Ser."), // P.0 cabin
    script("a1_wat_02", Speaker::Hero, "No, Ser."), // P.0 cabin
    script("a1_wat_03", Speaker::Hero, "His squire."), // P.0 below deck (to Maud)
    script("a1_wat_04", Speaker::Hero, "He's resting."), // P.0 below deck (to Maud)
    script("a1_wat_05", Speaker::Hero, "Hnn. There."), // P.0 squire tasks
    script("a1_wat_06", Speaker::Hero, "Left. Always the left."), // P.0 squire tasks
    script("a1_wat_07", Speaker::Hero, "Ser Godric doesn't do churches."), // Ch.1 dawn campfire
    script("a1_wat_08", Speaker::Hero, "Ser Godric said hold the line."), // Ch.2 campfire (Farmer)
    script("a1_wat_09", Speaker::Hero, "Ser Godric can't climb the tower."), // Ch.3 fever room
    script("a1_wat_10", Speaker::Hero, "You're the Pasha's man."), // Ch.4 Hamid
    script("a1_wat_11", Speaker::Hero, "What's the song?"), // Ch.4 Hamid
    script("a1_wat_12", Speaker::Hero, "Ser Godric is not a carpenter."), // Act I bank
    script("a1_wat_13", Speaker::Hero, "Ser Godric wants a wall. Ser Godric will settle for half."), // mission bark
    script("a1_wat_14", Speaker::Hero, "Stones. Ser Godric carries them now. Don't tell anyone."), // mission bark
    script("a1_wat_15", Speaker::Hero, "The wall won't build itself. Ser Godric checked."), // mission bark
    script("a1_wat_16", Speaker::Hero, "Dusk. To the walls."), // mission bark
    script("a1_wat_17", Speaker::Hero, "Dawn. Count the heads."), // mission bark
    script("a1_wat_18", Speaker::Hero, "Torch-bearers. Keep them off the fields."), // mission bark
    script("a1_wat_19", Speaker::Hero, "Barn. Ser Godric said barn."), // mission bark
    script("a1_wat_20", Speaker::Hero, "Fields need hands. Ser Godric has two. Both busy."), // mission bark
    script("a1_wat_21", Speaker::Hero, "Shamans in the marsh. Ser Godric goes. Alone is faster."), // mission bark
    script("a1_wat_22", Speaker::Hero, "Camp's burning. Their problem now."), // mission bark
    script("a1_wat_23", Speaker::Hero, "Ser Godric needs men. Brave ones. Stupid will do."), // mission bark
    script("a1_wat_24", Speaker::Hero, "Cages. Somebody's still alive in them."), // mission bark
    script("a1_wat_25", Speaker::Hero, "Out. Walk. Fort's that way."), // mission bark
    script("a1_wat_26", Speaker::Hero, "Ser Godric has had worse. Ser Godric has never had worse."), // low HP
    script("a1_wat_27", Speaker::Hero, "Fifteen years behind him. Now they're all behind me. Wrong way round."), // private musing (alone)
    script("a1_wat_28", Speaker::Hero, "Breathe. Rasp. Short words. You're him."), // private musing (alone)
    script("a1_wat_29", Speaker::Hero, "Don't take it off. Not out here."), // private musing (alone)
    script("a1_wat_30", Speaker::Hero, "Nobody looks at the man behind the shield. They're all looking now."), // private musing (alone)
    script("a1_wat_31", Speaker::Hero, "*pained grunt*"), // effort / exhausted
    script_planned("a1_wat_32", Speaker::Hero, "*heavy breathing, exhausted*"), // effort / exhausted
    script_planned("a1_wat_33", Speaker::Hero, "You're welcome."), // Ch.2 farm cutscene
    script_planned("a1_wat_34", Speaker::Hero, "I know."), // Ch.2 farm cutscene
    script("a1_maud_01", Speaker::Cast(Cast::Maud), "You're his boy."), // P.0 below deck
    script("a1_maud_02", Speaker::Cast(Cast::Maud), "Same thing, from down here. Does he ever come out?"), // P.0 below deck
    script("a1_maud_03", Speaker::Cast(Cast::Maud), "Resting. The knight's resting. Sleep well, everyone, we're guarded by a man who's resting."), // P.0 below deck
    script("a1_maud_04", Speaker::Cast(Cast::Maud), "Ser Godric's up! Behind him, all of you!"), // beach fight
    script("a1_maud_05", Speaker::Cast(Cast::Maud), "The sea took the squire. Wat. Some of you knew him."), // P.2 orders
    script("a1_maud_06", Speaker::Cast(Cast::Maud), "Ser Godric took an axe on the beach. Throat and face. He'll speak when he's ready and not before. Nobody argues with a man who lived through that."), // P.2 orders
    script("a1_maud_07", Speaker::Cast(Cast::Maud), "\"Make for the old fort of Saint Ottilie. Restore it. Ring the King's bell at every dusk.\" That's the whole order. The rest is who to thank."), // P.2 orders
    script("a1_maud_08", Speaker::Cast(Cast::Maud), "Then we'll ring it from the ground."), // P.2 orders
    script("a1_maud_09", Speaker::Cast(Cast::Maud), "This one's \"for the Lord Commissioner's eyes only.\" Ser Godric keeps it. Ser Godric's eyes, since the blow. I'll read him what he needs."), // P.2 orders
    script("a1_maud_10", Speaker::Cast(Cast::Maud), "Ask him."), // King's Road march
    script("a1_maud_11", Speaker::Cast(Cast::Maud), "Then that's your answer, isn't it."), // King's Road march
    script("a1_maud_12", Speaker::Cast(Cast::Maud), "In the fort, if the first lot didn't melt it for spoons."), // King's Road march
    script("a1_maud_13", Speaker::Cast(Cast::Maud), "People who had a roof."), // King's Road march
    script("a1_maud_14", Speaker::Cast(Cast::Maud), "The well's whole too. Start with the well."), // P.3 fort
    script("a1_maud_15", Speaker::Cast(Cast::Maud), "At dusk. King's orders, one of them."), // P.3 fort
    script("a1_maud_16", Speaker::Cast(Cast::Maud), "God help us. A well, a bell, and a wall and a half."), // P.3 fort
    script("a1_maud_17", Speaker::Cast(Cast::Maud), "Go on. They're watching Ser Godric, not me."), // Ch.1 first bell
    script("a1_maud_18", Speaker::Cast(Cast::Maud), "Three walls, no gate, a bell. We're a church with ambitions."), // Ch.1 dawn campfire
    script("a1_maud_19", Speaker::Cast(Cast::Maud), "Ser Godric doesn't do stairs, I've noticed. Mind the shoulder strap. It's riding up."), // Ch.1 dawn campfire
    script("a1_maud_20", Speaker::Cast(Cast::Maud), "Write it down. Next time he'll say barn."), // Ch.2 campfire
    script("a1_maud_21", Speaker::Cast(Cast::Maud), "Swamp fever. It's one night. Someone else can pull a rope."), // Ch.3 fever room
    script("a1_maud_22", Speaker::Cast(Cast::Maud), "Ser Godric can't climb the tower in front of forty people. Different thing."), // Ch.3 fever room
    script("a1_maud_23", Speaker::Cast(Cast::Maud), "...Fine. One night. The King can write me a letter."), // Ch.3 fever room
    script("a1_maud_24", Speaker::Cast(Cast::Maud), "...Could be. Dig."), // Ch.3 quiet-night morning
    script("a1_maud_25", Speaker::Cast(Cast::Maud), "Ser Godric inspected the wall. The wall is inspected. The wall is also still a hole."), // Act I bank
    script("a1_maud_26", Speaker::Cast(Cast::Maud), "Would you take it off, with what's out there?"), // Act I bank
    script("a1_maud_27", Speaker::Cast(Cast::Maud), "Ser Godric isn't a lot of things. Hold the plank."), // Act I bank
    script("a1_maud_28", Speaker::Cast(Cast::Maud), "Stones to the north wall! Ser Godric's watching. Look busy."), // mission bark
    script("a1_maud_29", Speaker::Cast(Cast::Maud), "Wood, stone, hands. We've got hands."), // mission bark
    script("a1_maud_30", Speaker::Cast(Cast::Maud), "The keep's still mostly sky. Stone, Ser Godric. Stone."), // mission bark
    script("a1_maud_31", Speaker::Cast(Cast::Maud), "Food's low. Nobody fights well hungry. Or at all."), // mission bark
    script("a1_maud_32", Speaker::Cast(Cast::Maud), "Dusk! Shutters, fires down, everyone on the wall!"), // mission bark
    script("a1_maud_33", Speaker::Cast(Cast::Maud), "Dawn. Count yourselves. Good. Same number."), // mission bark
    script("a1_maud_34", Speaker::Cast(Cast::Maud), "Dawn. Fewer than last night. Bury them before noon."), // mission bark
    script("a1_maud_35", Speaker::Cast(Cast::Maud), "Torches in the fields! Ser Godric, the barley!"), // mission bark
    script("a1_maud_36", Speaker::Cast(Cast::Maud), "Barley's ash. We'll eat the lecture instead."), // mission bark
    script("a1_maud_37", Speaker::Cast(Cast::Maud), "Fields need a fence. Or a knight. Fence is cheaper."), // mission bark
    script("a1_maud_38", Speaker::Cast(Cast::Maud), "Ser Godric's off to the marsh. Nobody follow him. He likes it quiet."), // mission bark
    script("a1_maud_39", Speaker::Cast(Cast::Maud), "Anyone who can hold a spear, the yard! Anyone who can't, hold one anyway."), // mission bark
    script("a1_maud_40", Speaker::Cast(Cast::Maud), "Twelve farmers and a grudge. Ser Godric, your army."), // mission bark
    script("a1_maud_41", Speaker::Cast(Cast::Maud), "You brought them back. Ser Godric brought them back!"), // mission bark
    script("a1_maud_42", Speaker::Cast(Cast::Maud), "A southerner. Put him by the fire. Not near the grain."), // mission bark
    script("a1_maud_43", Speaker::Cast(Cast::Maud), "Wall's breached! Hold the gap!"), // mission bark
    script("a1_maud_44", Speaker::Cast(Cast::Maud), "Ser Godric's down! Get him behind the line! Nobody touch the helmet!"), // mission bark
    script("a1_maud_45", Speaker::Cast(Cast::Maud), "Up. They're watching you."), // mission bark
    script("a1_maud_46", Speaker::Cast(Cast::Maud), "You're bleeding through the plate. Inside. Now."), // mission bark
    script_planned("a1_maud_47", Speaker::Cast(Cast::Maud), "He laid three stones. Then he supervised."), // mason gag
    script("a1_pip_01", Speaker::Cast(Cast::Pip), "Is it true? About the axe?"), // King's Road march
    script("a1_pip_02", Speaker::Cast(Cast::Pip), "He doesn't talk."), // King's Road march
    script("a1_pip_03", Speaker::Cast(Cast::Pip), "Where's the bell?"), // King's Road march
    script("a1_pip_04", Speaker::Cast(Cast::Pip), "Who's the first lot?"), // King's Road march
    script("a1_pip_05", Speaker::Cast(Cast::Pip), "There's a well! And that... that was a chapel! There's a bell! Up there! It's whole. Can I—"), // P.3 fort
    script("a1_pip_06", Speaker::Cast(Cast::Pip), "Can I—"), // P.3 fort
    script("a1_pip_07", Speaker::Cast(Cast::Pip), "Did you hear her? That's mine. She's the only thing on this island that does what it's told."), // Ch.1 first bell
    script("a1_pip_08", Speaker::Cast(Cast::Pip), "Don't let anyone else ring her."), // Ch.3 fever room
    script("a1_pip_09", Speaker::Cast(Cast::Pip), "The well's clean. I did the well. Nobody says anything about the well."), // Act I bank
    script("a1_pip_10", Speaker::Cast(Cast::Pip), "It's getting dark. Can I go up?"), // bark
    script("a1_pip_11", Speaker::Cast(Cast::Pip), "I counted the arrows. There aren't enough. I counted twice."), // bark
    script("a1_pip_12", Speaker::Cast(Cast::Pip), "Your sword's dirty, Ser Godric. I can clean it. I won't touch the helmet."), // bark
    script("a1_pip_13", Speaker::Cast(Cast::Pip), "I don't like the drums. Do you like the drums?"), // bark
    script("a1_pip_14", Speaker::Cast(Cast::Pip), "I'm better. Did anyone ring her? Good."), // bark
    script_planned("a1_pip_15", Speaker::Cast(Cast::Pip), "*coughing weakly*"), // bark
    script("a1_settler_01", Speaker::Cast(Cast::Settler), "A bell? We haven't got a roof."), // P.2 orders
    script("a1_settler_02", Speaker::Cast(Cast::Settler), "Not a one! Not a single one! You broke their ritual, Ser Godric. That's what it was. That's what brought them. Burn the shamans, the rest go home."), // Ch.3 quiet-night morning
    script("a1_settler_03", Speaker::Cast(Cast::Settler), "Does he sleep in it?"), // Act I bank
    script("a1_settler_04", Speaker::Cast(Cast::Settler), "Another camp burned, another quiet night coming. You'll see."), // bark
    script("a1_settler_05", Speaker::Cast(Cast::Settler), "Burn the shamans, sleep like a baby. That's my religion now."), // bark
    script("a1_settler_06", Speaker::Cast(Cast::Settler), "Quiet night, he says. Tell that to my roof."), // bark
    script("a1_settler_07", Speaker::Cast(Cast::Settler), "Took an axe to the face and still walks. I'd still be lying down."), // bark
    script("a1_settler_08", Speaker::Cast(Cast::Settler), "Drums again. Means they're close. Or bored. Either's bad."), // bark
    script("a1_farmer_01", Speaker::Cast(Cast::Farmer), "You said hold the line. Line's fine. Barn's gone."), // Ch.2 campfire
    script("a1_farmer_02", Speaker::Cast(Cast::Farmer), "Ser Godric should've said hold the barn."), // Ch.2 campfire
    script("a1_farmer_03", Speaker::Cast(Cast::Farmer), "They're at the barley! Somebody! Anybody in armour!"), // bark
    script("a1_farmer_04", Speaker::Cast(Cast::Farmer), "Third field this week. I'm farming ash now."), // bark
    script("a1_farmer_05", Speaker::Cast(Cast::Farmer), "Fields held. Don't let it go to your helmet."), // bark
    script_planned("a1_farmer_06", Speaker::Cast(Cast::Farmer), "Wasn't thanking you."), // Ch.2 farm cutscene
    script("a1_hamid_01", Speaker::Cast(Cast::Hamid), "You. In the tin. Yes, you. Open this and I'll owe you, which I hate."), // Ch.4 cage
    script("a1_hamid_02", Speaker::Cast(Cast::Hamid), "Three weeks. They fed me. Badly, but they fed me. You don't feed what you mean to eat."), // Ch.4 freed
    script("a1_hamid_03", Speaker::Cast(Cast::Hamid), "I'm the Pasha's caravan. The man is in the desert, and he's going to ask me what I was worth. ...Ser Godric Harrow. He'll want to hear that too."), // Ch.4 freed
    script("a1_hamid_04", Speaker::Cast(Cast::Hamid), "Head. Three weeks of their drums, knight, you'd have a head too."), // Ch.4 dusk, indoors
    script("a1_hamid_05", Speaker::Cast(Cast::Hamid), "Theirs. They sing in the evenings. Not what you'd expect. Sad. Like somebody's leaving for work."), // Ch.4 dusk, indoors
    script("a1_hamid_06", Speaker::Cast(Cast::Hamid), "Not the yard, not at sundown. My head. I'll sit inside."), // bark
    script("a1_hamid_07", Speaker::Cast(Cast::Hamid), "I'll pay for the bed. Eventually. With interest. Somebody's interest."), // bark
    script("a1_hamid_08", Speaker::Cast(Cast::Hamid), "A well, three walls and a knight who doesn't talk. In the desert we call that a bargain."), // bark
    script("a1_hamid_09", Speaker::Cast(Cast::Hamid), "*humming a slow, sad tune*"), // bark
    script("a1_hamid_10", Speaker::Cast(Cast::Hamid), "*humming softly, sighs*"), // bark
    script("a1_ork_01", Speaker::Ork, "*guttural roar*"), // bark
    script("a1_ork_02", Speaker::Ork, "Iron voice calls!"), // bark
    script("a1_ork_03", Speaker::Ork, "Answer! Answer!"), // bark
    script("a1_ork_04", Speaker::Ork, "Hrah. Hrah. Hrah."), // bark
    script("a1_ork_05", Speaker::Ork, "Tin man!"), // bark
    script("a1_ork_06", Speaker::Ork, "*dying groan*"), // bark
    script_planned("a1_shaman_01", Speaker::Ork, "*low guttural ritual chanting*"), // bark
    script_planned("a1_shaman_02", Speaker::Ork, "*rasping incantation, rising*"), // bark
    script("a1_shaman_03", Speaker::Ork, "*furious shriek*"), // bark

    // Opening campaign: all clips are from the supplied Sully recording.
    Line { once: true, priority: 14, floor: 90.0, ..line("campaign_rescue_plan", Speaker::Hero, Concept::Campaign(super::campaign::CampaignLine::RescuePlan), "They've taken our people. Gather the militia. We're getting them back.") },
    Line { once: true, priority: 14, floor: 90.0, ..line("campaign_home_workers", Speaker::Hero, Concept::Campaign(super::campaign::CampaignLine::HomeWorkers), "You're home. Back to the fields. Heroism doesn't pay for supper.") },
    Line { once: true, priority: 14, floor: 90.0, ..line("campaign_farm_working", Speaker::Hero, Concept::Campaign(super::campaign::CampaignLine::FarmWorking), "Food and defenders. Almost looks like I know what I'm doing.") },
    Line { once: true, priority: 14, floor: 90.0, ..line("campaign_torch_raid", Speaker::Hero, Concept::Campaign(super::campaign::CampaignLine::TorchRaid), "Torch bearers. Keep them off the farms. I prefer my wheat uncooked.") },
    Line { once: true, priority: 14, floor: 90.0, ..line("campaign_shaman_plan", Speaker::Hero, Concept::Campaign(super::campaign::CampaignLine::ShamanPlan), "Shamans are gathering. Break their camp, or ready the archers.") },
    Line { once: true, priority: 14, floor: 90.0, ..line("campaign_ritual_broken", Speaker::Hero, Concept::Campaign(super::campaign::CampaignLine::RitualBroken), "Ritual broken. Apparently, swords are bad for morale.") },
    Line { once: false, priority: 9, floor: 90.0, ..line("campaign_rally_reminder", Speaker::Hero, Concept::Campaign(super::campaign::CampaignLine::RallyReminder), "I should probably gather some men. Brave, not stupid.") },
    Line { once: false, priority: 9, floor: 90.0, ..line("campaign_rescue_reminder", Speaker::Hero, Concept::Campaign(super::campaign::CampaignLine::RescueReminder), "Those people are still caged. Standing here isn't helping.") },
    Line { once: false, priority: 9, floor: 90.0, ..line("campaign_home_reminder", Speaker::Hero, Concept::Campaign(super::campaign::CampaignLine::HomeReminder), "I should head home and dismiss the militia. Crops won't grow themselves.") },
    Line { once: false, priority: 9, floor: 90.0, ..line("campaign_farm_reminder", Speaker::Hero, Concept::Campaign(super::campaign::CampaignLine::FarmReminder), "I should probably build a farm. People insist on eating.") },
    Line { once: false, priority: 9, floor: 90.0, ..line("campaign_upgrade_reminder", Speaker::Hero, Concept::Campaign(super::campaign::CampaignLine::UpgradeReminder), "I should buy an upgrade at the keep. Insults won't stop torches.") },
    Line { once: false, priority: 9, floor: 90.0, ..line("campaign_shaman_reminder", Speaker::Hero, Concept::Campaign(super::campaign::CampaignLine::ShamanReminder), "Those shamans need dealing with. Arrows do shorten sermons.") },
    Line { once: false, priority: 9, floor: 90.0, ..line("campaign_bell_reminder", Speaker::Hero, Concept::Campaign(super::campaign::CampaignLine::BellReminder), "Time to ring the bell. Invite the neighbours. The ugly ones.") },

    // ── Hero event reactions ──
    Line { once: true,  priority: 20, ..line("stone",         Speaker::Hero, Concept::FirstStone,   "Huh, stone. I could shore up the castle walls with this.") },
    Line { floor: 300.0,              ..line("chest",         Speaker::Hero, Concept::ChestOpen,    "Ooh, a chest.") },
    Line { once: true,  priority: 20, ..line("rescue",        Speaker::Hero, Concept::FirstRescue,  "There, you're free. Get to the castle. You'll fight at my side now.") },
    Line { priority: 30,              ..line("night",         Speaker::Hero, Concept::NightWarning, "Getting dark. Night soon. Maybe I wandered too far.") },
    Line { floor: 300.0, priority: 15, ..line("hurt",         Speaker::Hero, Concept::LowHp,        "I'm hurt. Could use some herbs.") },
    Line { once: true,  priority: 15, ..line("home",          Speaker::Hero, Concept::Home,         "Home. Finally. Safe here. Guess I ring the bell when I'm ready. Then they come.") },
    // Fires once per run the first time GEAR — armour OR a weapon — lands in the bag (see
    // `detect_gear_found`); the one armour-flavoured clip covers either find. Text == the `equip.ogg`
    // transcript (don't reword without re-recording, or the subtitle desyncs from the audio).
    Line { once: true,  priority: 15, ..line("equip",         Speaker::Hero, Concept::Equip,        "Mm, new armor. I should look it over in my satchel.") },
    Line { floor: 300.0,               ..line("levelup",      Speaker::Hero, Concept::LevelUp,      "Stronger. The blade feels lighter than it did.") },
    Line { floor: 300.0, priority: 12, ..line("wave_survived", Speaker::Hero, Concept::WaveSurvived, "Dawn. We held. ...this time.") },
    Line { once: true,  priority: 15, ..line("first_kill",    Speaker::Hero, Concept::FirstKill,    "Down it goes. Plenty more where that came from.") },
    Line { once: true,                ..line("gold_rich",     Speaker::Hero, Concept::GoldRich,     "Coin enough to make the merchant smile. Good.") },
    Line { floor: 300.0,              ..line("broke",         Speaker::Hero, Concept::Broke,        "Pockets empty. Steel will have to do the talking.") },
    Line { floor: 300.0, priority: 25, ..line("keep_hurt",    Speaker::Hero, Concept::KeepHurt,     "The keep's taking a beating. Get to the walls.") },
    Line { floor: 300.0,              ..line("shrine_heal",   Speaker::Hero, Concept::ShrineHeal,   "The old stones still have mercy in them.") },
    // ── Hero commands — the muster (K). One rally variant rolls when the war party forms up, one
    //    stand-down variant when it disbands (emitted from `villagers::muster_keys`). priority 25 so
    //    a deliberate order plays over idle musings; transcripts == the recorded `.ogg` (don't reword
    //    without re-recording, or the subtitle desyncs from the clip). ──
    Line { priority: 25, ..line("muster_to_me",     Speaker::Hero, Concept::MusterCall,      "To me! Form up!") },
    Line { priority: 25, ..line("muster_on_me",     Speaker::Hero, Concept::MusterCall,      "On me, all of you. We move.") },
    Line { priority: 25, ..line("muster_take_arms", Speaker::Hero, Concept::MusterCall,      "Take up arms — fall in behind me!") },
    Line { priority: 25, ..line("muster_with_me",   Speaker::Hero, Concept::MusterCall,      "With me, lads. Stay close now.") },
    Line { priority: 25, ..line("standdown_work",   Speaker::Hero, Concept::MusterStandDown, "Stand down. Back to your work.") },
    Line { priority: 25, ..line("standdown_ease",   Speaker::Hero, Concept::MusterStandDown, "That'll do. Ease off.") },
    Line { priority: 25, ..line("standdown_hold",   Speaker::Hero, Concept::MusterStandDown, "Hold here. Rest while you can.") },
    // ── Hero biome musings (once per biome per run via `once`) ──
    // REWORKED 2026-07 (was stale): the old versions all presumed a prisoner cage sat in every
    // biome ("Huh, prisoners", "someone's locked in that cage", "are those captives?") — but cages
    // spawn at scattered ork camps, not per-biome, so the line lied on most entries. They also ran
    // long and got clipped at read_secs' 8s cap. These are shorter, cage-free, and the desert now
    // nods the rival stronghold that lives there. NB: the .ogg clips must be RE-RECORDED to match —
    // until then the old audio plays under the new subtitle (desync). Re-cut ids: forest/snow/rock/
    // desert/swamp.
    Line { once: true, ..line("forest", Speaker::Hero, Concept::BiomeEntered(Biome::Forest), "A forest. Good hunting here — apples too, if the birds left me any.") },
    Line { once: true, ..line("snow",   Speaker::Hero, Concept::BiomeEntered(Biome::Snow),   "Freezing up here. Beasts to hunt, and there's loot buried in the ice — if the cold don't take me first.") },
    Line { once: true, ..line("rock",   Speaker::Hero, Concept::BiomeEntered(Biome::Rocky),  "All this rock. A lot of ore in it. The keep walls could drink every ton I dig.") },
    Line { once: true, ..line("desert", Speaker::Hero, Concept::BiomeEntered(Biome::Desert), "Desert. Hot as a forge. And that's the rival's banner on the dunes — I'm not welcome out here.") },
    Line { once: true, ..line("swamp",  Speaker::Hero, Concept::BiomeEntered(Biome::Swamp),  "Ugh, the marsh. Slow going — but the healing herbs grow thick here. Worth the stink.") },
    // ── Hero observational remarks ──
    // Trigger: NearTown — hero near townsfolk (folded from people/name/well/townday/laugh/market/woodpile/grumble lines)
    Line { floor: 300.0, priority: 5, ..line("people_a",   Speaker::Hero, Concept::NearTown, "These people. Loud, stubborn, alive. That's the whole point of all this, isn't it.") },
    Line { floor: 300.0, priority: 5, ..line("people_b",   Speaker::Hero, Concept::NearTown, "Look at them — bickering, trading, breathing. That's what the wall is for.") },
    Line { floor: 300.0, priority: 5, ..line("name_a",     Speaker::Hero, Concept::NearTown, "Half of them don't know my name. Good. Means they're free to forget the war.") },
    Line { floor: 300.0, priority: 5, ..line("name_b",     Speaker::Hero, Concept::NearTown, "They nod and move on. Better that than knowing what's out past the gate.") },
    Line { floor: 300.0, priority: 5, ..line("well_a",     Speaker::Hero, Concept::NearTown, "Fresh water, idle talk, small quarrels. The things we're actually fighting for.") },
    Line { floor: 300.0, priority: 5, ..line("well_b",     Speaker::Hero, Concept::NearTown, "Gossip at the well. Sounds like nothing. Sounds like peace, is what it is.") },
    Line { floor: 300.0, priority: 5, ..line("townday_a",  Speaker::Hero, Concept::NearTown, "A town that still argues over fences and taxes. Means there's still a town.") },
    Line { floor: 300.0, priority: 5, ..line("townday_b",  Speaker::Hero, Concept::NearTown, "Still squabbling over hens and rent. The day that stops, we've lost.") },
    Line { floor: 300.0, priority: 5, ..line("laugh_a",    Speaker::Hero, Concept::NearTown, "They laugh like there was never a siege. ...Maybe that's the victory.") },
    Line { floor: 300.0, priority: 5, ..line("laugh_b",    Speaker::Hero, Concept::NearTown, "Laughter in the square, after all this. ...Maybe that's the whole point.") },
    Line { floor: 300.0, priority: 5, ..line("market_a",   Speaker::Hero, Concept::NearTown, "Coin changes hands, bread gets baked, the world turns. I just keep the wolves off it.") },
    Line { floor: 300.0, priority: 5, ..line("market_b",   Speaker::Hero, Concept::NearTown, "Buy, sell, haggle — honest work. I'd take it over mine most days.") },
    Line { floor: 300.0, priority: 5, ..line("woodpile_a", Speaker::Hero, Concept::NearTown, "Stack it high. The nights are only getting longer.") },
    Line { floor: 300.0, priority: 5, ..line("woodpile_b", Speaker::Hero, Concept::NearTown, "More wood. Good. Cold kills slower than orks — but it still kills.") },
    Line { floor: 300.0, priority: 5, ..line("grumble_a",  Speaker::Hero, Concept::NearTown, "The taxes, aye. Tell it to the orks — they're wonderful listeners.") },
    Line { floor: 300.0, priority: 5, ..line("grumble_b",  Speaker::Hero, Concept::NearTown, "Complain to me about rent. I'll forward it to the horde — they decide who pays.") },
    // Trigger: NearKids — hero near child villagers
    Line { floor: 300.0, priority: 5, ..line("kids_a",     Speaker::Hero, Concept::NearKids, "Mind those sticks, little ones. ...Gods, let them stay little ones a while longer.") },
    Line { floor: 300.0, priority: 5, ..line("kids_b",     Speaker::Hero, Concept::NearKids, "Run while you can, little ones. Wish I still had the knees for it.") },
    // Trigger: NearPet — hero near a dog or cat
    Line { floor: 300.0, priority: 5, ..line("pet_a",      Speaker::Hero, Concept::NearPet, "At least the hound's got the right idea. Rest while the light holds.") },
    Line { floor: 300.0, priority: 5, ..line("pet_b",      Speaker::Hero, Concept::NearPet, "The cat fears nothing. Must be nice, being a cat.") },
    // Trigger: NearGuard — hero near a guard / militia
    Line { floor: 300.0, priority: 5, ..line("guard_a",    Speaker::Hero, Concept::NearGuard, "Stand tall. The wall holds because you do.") },
    Line { floor: 300.0, priority: 5, ..line("guard_b",    Speaker::Hero, Concept::NearGuard, "Eyes on the dark, soldier. I'll be right beside you when it comes.") },
    // Trigger: InKeep — hero inside the keep footprint
    Line { floor: 300.0, priority: 5, ..line("keep_a",     Speaker::Hero, Concept::InKeep, "Old stones. They've outlived better men than me. They'll outlive me too.") },
    Line { floor: 300.0, priority: 5, ..line("keep_b",     Speaker::Hero, Concept::InKeep, "This keep's swallowed a hundred sieges. One more won't choke it.") },
    // Trigger: NearFortress — hero within sight range of Gnashfang Hold (south swamp)
    Line { floor: 600.0, priority: 8, ..line("fortress_sight", Speaker::Hero, Concept::NearFortress, "There it is. Gnashfang Hold. Every roar on this island starts there.") },
    Line { floor: 600.0, priority: 8, ..line("fortress_near",  Speaker::Hero, Concept::NearFortress, "Walk soft. Their archers don't ask questions.") },
    Line { floor: 600.0, priority: 8, ..line("fortress_drums", Speaker::Hero, Concept::NearFortress, "Hear the drums? They're not celebrating. They're counting.") },
    // Trigger: NightMusing — during a wave
    Line { floor: 300.0, priority: 5, ..line("night_a",    Speaker::Hero, Concept::NightMusing, "Stars are out. Somewhere up there someone's keeping a tally. Hope I'm ahead.") },
    Line { floor: 300.0, priority: 5, ..line("night_b",    Speaker::Hero, Concept::NightMusing, "Clear night. Pretty — if you forget what comes with the dark.") },
    // Trigger: QuietMusing — prep phase, no orks nearby
    Line { floor: 300.0, priority: 5, ..line("quiet_a",    Speaker::Hero, Concept::QuietMusing, "Quiet day. I've learned not to trust quiet days.") },
    Line { floor: 300.0, priority: 5, ..line("quiet_b",    Speaker::Hero, Concept::QuietMusing, "Too calm. The quiet always sends a bill, sooner or later.") },
    // Trigger: KillMusing — after a kill, but only on a small chance roll (`KILL_REMARK_CHANCE`)
    // so the hero doesn't comment on every felled ork/animal during a wave ("mouth never closes").
    Line { floor: 300.0, priority: 5, ..line("kill_a",     Speaker::Hero, Concept::KillMusing, "One more for the pile. I stopped counting around the second winter.") },
    Line { floor: 300.0, priority: 5, ..line("kill_b",     Speaker::Hero, Concept::KillMusing, "Down. There's always another behind it. Always is.") },
    // ── Hero intro lines (once per run — the tutorial in the hero's own voice) ──
    // TIGHTENED 2026-07: the old versions ran ~14–17s but read_secs clamps mouth-busy at 8s, so the
    // back half was silently dropped mid-sentence. These are cut to land inside ~8s. RE-RECORD the
    // intro_a/intro_b clips to match (else new subtitle over old, longer audio).
    Line { once: true, priority: 3, ..line("intro_a", Speaker::Hero, Concept::Intro, "Daylight's short. Loot the chests, gather coin and stone, arm up. When dark falls, the orks come for the keep — and we hold it.") },
    Line { once: true, priority: 3, ..line("intro_b", Speaker::Hero, Concept::Intro, "By day you scavenge and arm at the War Table. By night the horde hits these walls. Keep the keep standing.") },
    // ── Villager ambient chatter (nearest working townsperson, when the hero lingers) ──
    // One villager voice globally at a time (director enforces this); accepted simplification vs. the
    // old one-per-cluster model. floor:360 keeps the ~7-min rotation cycling without going silent.
    // Speakers: Ed (greet … screaming) and Professor (day_dream … screaming). Text is the clip transcript.
    Line { floor: 360.0, ..line("greet",        Speaker::Villager, Concept::Greeting,         "Oh, hello there, m'lord. Mind the mud.") },
    Line { floor: 360.0, ..line("greet_2",      Speaker::Villager, Concept::Greeting,         "Bless your night. We sleep easier when you're about.") },
    Line { floor: 360.0, ..line("idle_hens",    Speaker::Villager, Concept::Greeting,         "I told the hens about the orks. They were not impressed.") },
    Line { floor: 360.0, ..line("idle_cousin",  Speaker::Villager, Concept::Greeting,         "Me cousin says he killed an ork once. Me cousin says a lotta things.") },
    Line { floor: 360.0, ..line("merchant",     Speaker::Villager, Concept::Greeting,         "Finest wares this side of the swamp. Only wares this side of the swamp, but still.") },
    // Worker ambient lines — lumberjack, miner, farmer. Pooled into Greeting so they
    // rotate naturally with the other ambient chatter; spatial villager routing applies.
    Line { floor: 360.0, ..line("timber",          Speaker::Villager, Concept::Greeting, "Timber!") },
    Line { floor: 360.0, ..line("lumber_opinions", Speaker::Villager, Concept::Greeting, "This one's got opinions.") },
    Line { floor: 360.0, ..line("lumber_trees",    Speaker::Villager, Concept::Greeting, "Trees don't fight back. That's why I like trees.") },
    Line { floor: 360.0, ..line("lumber_dream",    Speaker::Villager, Concept::Greeting, "Chop, haul, stack. Living the dream.") },
    Line { floor: 360.0, ..line("miner_growback",  Speaker::Villager, Concept::Greeting, "Stone doesn't grow back. Wish someone tell the keep that.") },
    Line { floor: 360.0, ..line("miner_heavy",     Speaker::Villager, Concept::Greeting, "Heavy? No, no. I walk like this for fun.") },
    Line { floor: 360.0, ..line("miner_ore",       Speaker::Villager, Concept::Greeting, "Found ore! Somebody else carry it.") },
    Line { floor: 360.0, ..line("miner_pa",        Speaker::Villager, Concept::Greeting, "Pick, rock, repeat. My paw did this. His paw did this. None of us learned.") },
    Line { floor: 360.0, ..line("farmer_grow",     Speaker::Villager, Concept::Greeting, "Grow, you little green liars.") },
    Line { floor: 360.0, ..line("farmer_turnips",  Speaker::Villager, Concept::Greeting, "Orcs trampled the turnips again. The turnips.") },
    Line { floor: 360.0, ..line("farmer_always",   Speaker::Villager, Concept::Greeting, "Rain or orcs. Always something.") },
    Line { floor: 360.0, ..line("farmer_feeds",    Speaker::Villager, Concept::Greeting, "Feed the whole island, they said. Nobody feeds the farmer.") },
    // These jabs are aimed AT the hero, so each opens a call-and-response chain: when the
    // line finishes it dispatches `ReplyToVillagerJab` to the hero, who picks a comeback from his
    // reply pool below (the Valve "then" dispatch — `tick_chains` resolves it against current facts,
    // so if the hero has wandered out of earshot / is mid-line, the comeback simply doesn't land).
    Line { floor: 360.0, then: Some(REPLY_TO_JAB), ..line("pa_hero",   Speaker::Villager, Concept::Greeting, "Off to be a hero again, are we? Must be nice having the time.") },
    Line { floor: 360.0, then: Some(REPLY_TO_JAB), ..line("pa_chosen", Speaker::Villager, Concept::Greeting, "Oh, the chosen one graces us. Mind you don't trip on all that destiny.") },
    Line { floor: 360.0, then: Some(REPLY_TO_JAB), ..line("pa_slept",  Speaker::Villager, Concept::Greeting, "Saved us all last night, did you? Funny, I slept fine without you.") },
    // pa_armor and everything after it in this file were batch-generated with ElevenLabs
    // ("Victor — deep" voice, single take split on silences), so they share one voice.
    Line { floor: 360.0, then: Some(REPLY_TO_JAB), ..line("pa_armor",  Speaker::Villager, Concept::Greeting, "Lovely armor, that. Shame about the taxes what paid for it.") },
    Line { floor: 360.0, then: Some(REPLY_TO_JAB), ..line("pa_late",   Speaker::Villager, Concept::Greeting, "Oh, look who turns up once the screaming's done. Impeccable timing, as ever.") },
    Line { floor: 360.0, ..line("pa_fence",     Speaker::Villager, Concept::Greeting,         "Big strong knight. Can't fix a fence, but big strong knight.") },
    Line { floor: 360.0, ..line("story_barn",   Speaker::Villager, Concept::Greeting,         "See ol' Marek's barn? Burned clean down. He says lightning. Was the ale.") },
    Line { floor: 360.0, ..line("story_miller", Speaker::Villager, Concept::Greeting,         "The miller's daughter married a soldier. He left, she kept the goat. Smart girl.") },
    Line { floor: 360.0, ..line("story_witch",  Speaker::Villager, Concept::Greeting,         "They say the swamp witch grants wishes. They also say she eats fingers. I'll keep my fingers.") },
    Line { floor: 360.0, ..line("story_gran",   Speaker::Villager, Concept::Greeting,         "We don't talk about grandfather.") },
    Line { floor: 360.0, ..line("story_baker",  Speaker::Villager, Concept::Greeting,         "Heard the baker's getting rich. Heard it from the baker. So.") },
    Line { floor: 360.0, ..line("day_dream",    Speaker::Villager, Concept::Greeting,         "Another glorious day of standing exactly here. Living the dream.") },
    Line { floor: 360.0, ..line("chicken",      Speaker::Villager, Concept::Greeting,         "If one more chicken gets into the chapel, I'm converting.") },
    Line { floor: 360.0, ..line("taxes",        Speaker::Villager, Concept::Greeting,         "Taxes up, walls down, orks at the door. But sure, ring the bell. That'll help.") },
    Line { floor: 360.0, ..line("trade",        Speaker::Villager, Concept::Greeting,         "I had a trade once, then the war. Now I... do this.") },
    Line { floor: 360.0, ..line("grateful",     Speaker::Villager, Concept::Greeting,         "We're ever so grateful. Truly. Now could you grateful your boots off my step.") },
    Line { floor: 360.0, ..line("screaming",    Speaker::Villager, Concept::Greeting,         "Bless you for the protection. The screaming at night is a lovely touch.") },
    Line { floor: 360.0, ..line("statue",       Speaker::Villager, Concept::Greeting,         "They'll raise you a statue one day, m'lord. The pigeons are very excited.") },
    Line { floor: 360.0, ..line("favorite",     Speaker::Villager, Concept::Greeting,         "You're my favorite knight. You're the only knight. Still counts.") },
    Line { floor: 360.0, ..line("moat",         Speaker::Villager, Concept::Greeting,         "I said dig a moat. 'Too dear,' they said. But swords for everyone, sure.") },
    Line { floor: 360.0, ..line("optimist",     Speaker::Villager, Concept::Greeting,         "Mum always said look on the bright side. So: at least the orks are punctual.") },
    Line { floor: 360.0, ..line("roof",         Speaker::Villager, Concept::Greeting,         "There's a hole in my roof shaped just like a catapult stone. Decorative, I'm told.") },
    // pa_sword is weapon-gated → its own concept so the trigger can conditionally emit it only when armed
    Line { floor: 360.0, ..line("pa_sword",     Speaker::Villager, Concept::VillagerArmedJab, "Look at the size of that sword. My uncle's is smaller, and he's twice the man.") },
    Line { floor: 360.0, ..line("pa_shiny",     Speaker::Villager, Concept::VillagerArmedJab, "Ooh, shiny. Did the merchant see you coming, or did you queue up special?") },
    // ── Villager event reactions (must finish; outrank ambient chatter) ──
    // interruptible:false + priority:15 so these aren't cut off by ambient. floor:600 = 10-min floor.
    Line { interruptible: false, priority: 15, floor: 600.0, ..line("siege_fear",  Speaker::Villager, Concept::SiegeFalls, "They're coming. Inside, inside. Lock the door.") },
    Line { interruptible: false, priority: 15, floor: 600.0, ..line("dawn_relief", Speaker::Villager, Concept::Dawn,       "Made it to morning. Knew you'd see us through.") },
    Line { interruptible: false, priority: 15, floor: 600.0, ..line("rescued",     Speaker::Villager, Concept::Rescued,    "You came for me? Gods bless you. I'll take up a spear, I swear it.") },
    // Dry-wit variants of the same events — same must-finish gating, so the pool just gets wider.
    Line { interruptible: false, priority: 15, floor: 600.0, ..line("siege_dry",   Speaker::Villager, Concept::SiegeFalls, "Orks again. Right on schedule. Everyone act surprised.") },
    Line { interruptible: false, priority: 15, floor: 600.0, ..line("dawn_dry",    Speaker::Villager, Concept::Dawn,       "Still alive, then. The betting pool will be devastated.") },
    Line { interruptible: false, priority: 15, floor: 600.0, ..line("rescued_dry", Speaker::Villager, Concept::Rescued,    "My hero. Only took you, what, a fortnight? Bless.") },
    // ── "You just HIT me?!" — harmless bonk reactions (the hero can clip a townsperson with a
    // swing; it does no damage but earns a sarcastic earful). These REUSE existing villager clips
    // whose lines best fit getting smacked by your own knight — no new audio, same affronted tone.
    // priority 13 so a bonk barges over idle chatter (prio 10) but yields to event lines (15);
    // floor 5 throttles machine-gun swinging without making a clip feel unresponsive.
    Line { priority: 13, floor: 5.0, ..line("last_word_c", Speaker::Villager, Concept::HitByHero, "Touchy, touchy. And after everything we do for you.") },
    Line { priority: 13, floor: 5.0, ..line("last_word_a", Speaker::Villager, Concept::HitByHero, "Ooh, sharp. Practice that one on the cows, did we?") },
    Line { priority: 13, floor: 5.0, ..line("last_word_b", Speaker::Villager, Concept::HitByHero, "Noted, m'lord. I'll scream quieter tonight, just for you.") },
    Line { priority: 13, floor: 5.0, ..line("grateful",    Speaker::Villager, Concept::HitByHero, "We're ever so grateful. Truly. Now could you grateful your boots off my step.") },
    Line { priority: 13, floor: 5.0, ..line("screaming",   Speaker::Villager, Concept::HitByHero, "Bless you for the protection. The screaming at night is a lovely touch.") },
    // ── Ork battle barks (nearest ork in earshot; pitch-shifted per utterance) ──
    Line { ..line("spot",   Speaker::Ork, Concept::OrkSpot,  "Little knight. Little bones.") },
    Line { ..line("charge", Speaker::Ork, Concept::OrkSpot,  "Smash the stone. Burn the nest.") },
    Line { ..line("blood",  Speaker::Ork, Concept::OrkSpot,  "Blood. Blood.") },
    Line { ..line("taunt",  Speaker::Ork, Concept::OrkSpot,  "Run, runt. We eat slow ones first.") },
    Line { ..line("where",  Speaker::Ork, Concept::OrkSpot,  "Where? Where you hide, worm?") },
    Line { ..line("feast",  Speaker::Ork, Concept::OrkSpot,  "Tonight we feast.") },
    Line { ..line("shaman", Speaker::Ork, Concept::OrkSpot,  "Spirits take him. Saka.") },
    Line { ..line("gate",   Speaker::Ork, Concept::OrkSpot,  "Break the gate. Break the man.") },
    Line { ..line("meat",   Speaker::Ork, Concept::OrkSpot,  "Fresh meat for the war pot.") },
    // ── Ork death snarl (on a kill) ──
    Line { ..line("death",  Speaker::Ork, Concept::OrkDeath, "Not done.") },
    Line { ..line("death_2", Speaker::Ork, Concept::OrkDeath, "Cold... why cold...") },
    Line { ..line("death_3", Speaker::Ork, Concept::OrkDeath, "Good fight. Good... fight.") },
    // ── Rival garrison (desert mercenaries) — clips at `audio/vo/rival/<id>.ogg`, transcripts are
    //    the actual recorded lines (ElevenLabs, per the chop). RivalSpot is the catch-all combat
    //    bark pool (aggro + attack cries + gloating + pain + exertion grunts); the detector
    //    (`rival_voice.rs`) rolls one when the hero fights near a rival. Default prio 10 like the
    //    orks; the spatial routing + pitch jitter live on the `Rival` SpeakerVoice. ──
    Line { ..line("spot_dog",    Speaker::Rival, Concept::RivalSpot, "Northern dog! You are far from your little walls.") },
    Line { ..line("spot_beggar", Speaker::Rival, Concept::RivalSpot, "Another beggar-knight. The sand will drink you.") },
    Line { ..line("spot_mine",   Speaker::Rival, Concept::RivalSpot, "Hut! He is mine — fan out!") },
    Line { ..line("spot_dunes",  Speaker::Rival, Concept::RivalSpot, "You should not have crossed the dunes, stranger.") },
    Line { ..line("spot_toy",    Speaker::Rival, Concept::RivalSpot, "Look at his shining toy sword. Pretty. Useless.") },
    Line { ..line("spot_pasha",  Speaker::Rival, Concept::RivalSpot, "For the Pasha! Yaaah!") },
    Line { ..line("atk_bleed",   Speaker::Rival, Concept::RivalSpot, "Hah! Bleed!") },
    Line { ..line("atk_strike",  Speaker::Rival, Concept::RivalSpot, "Strike — down, dog!") },
    Line { ..line("atk_head",    Speaker::Rival, Concept::RivalSpot, "Take his head!") },
    Line { ..line("atk_still",   Speaker::Rival, Concept::RivalSpot, "Stand still!") },
    Line { ..line("atk_ribbons", Speaker::Rival, Concept::RivalSpot, "Cut him to ribbons!") },
    Line { ..line("taunt_army",  Speaker::Rival, Concept::RivalSpot, "Is this your army? Peasants with sticks.") },
    Line { ..line("taunt_down",  Speaker::Rival, Concept::RivalSpot, "Down he goes. Sweep them aside.") },
    Line { ..line("taunt_farmers", Speaker::Rival, Concept::RivalSpot, "Run home, farmers!") },
    Line { ..line("hurt_pay",    Speaker::Rival, Concept::RivalSpot, "You will pay for that.") },
    Line { ..line("hurt_all",    Speaker::Rival, Concept::RivalSpot, "Is that all, runt?") },
    Line { ..line("hurt_coward", Speaker::Rival, Concept::RivalSpot, "Coward's blow!") },
    Line { ..line("hurt_angry",  Speaker::Rival, Concept::RivalSpot, "You only make me angry.") },
    Line { ..line("grunt_1",     Speaker::Rival, Concept::RivalSpot, "Ugh!") },
    Line { ..line("grunt_2",     Speaker::Rival, Concept::RivalSpot, "Hah!") },
    // Death cry (on a rival's fall).
    Line { ..line("death_sands",   Speaker::Rival, Concept::RivalDeath, "The sands... take me...") },
    Line { ..line("death_held",    Speaker::Rival, Concept::RivalDeath, "Tell the Pasha... I held...") },
    Line { ..line("death_cold",    Speaker::Rival, Concept::RivalDeath, "Cold... northern... cold...") },
    Line { ..line("death_nothing", Speaker::Rival, Concept::RivalDeath, "You... win nothing... dog...") },
    // Raid-march cue — fired when the daytime raid sets out (`rival.rs`). Slightly louder so it
    // carries across the field as the warning it is.
    Line { priority: 12, floor: 30.0, ..line("raid_forward",  Speaker::Rival, Concept::RivalRaidMarch, "Forward! Burn their keep!") },
    Line { priority: 12, floor: 30.0, ..line("raid_chant",    Speaker::Rival, Concept::RivalRaidMarch, "Sand and steel! Sand and steel!") },
    Line { priority: 12, floor: 30.0, ..line("raid_drums",    Speaker::Rival, Concept::RivalRaidMarch, "Beat the drums — we march!") },
    Line { priority: 12, floor: 30.0, ..line("raid_kindling", Speaker::Rival, Concept::RivalRaidMarch, "Your walls are kindling, little lord.") },
    // Idle patrol murmur (peaceful — `is_peaceful`, muted once the hero is fighting). Floored so a
    // sentry doesn't mutter constantly.
    Line { floor: 25.0, ..line("idle_wind",  Speaker::Rival, Concept::RivalIdle, "Hot wind today... bad omen.") },
    Line { floor: 25.0, ..line("idle_quiet", Speaker::Rival, Concept::RivalIdle, "Quiet on the eastern wall. Too quiet.") },
    Line { floor: 25.0, ..line("idle_gold",  Speaker::Rival, Concept::RivalIdle, "The Pasha promised us gold. I see only sand.") },
    // ── Hero comebacks to a villager's jab (chain replies — `reply_to`, never emitted directly) ──
    // Dispatched by `tick_chains` when a `pa_*` jab finishes; `pick`-of-pool gives variety. Priority
    // 12 so the retort lands over idle chatter; floored so the same comeback doesn't repeat soon.
    Line { priority: 12, floor: 90.0, reply_to: Some(Concept::ReplyToVillagerJab), ..line("reply_jab_a", Speaker::Hero, Concept::ReplyToVillagerJab, "Mm. And yet here you still stand, breathing. Funny how that works.") },
    Line { priority: 12, floor: 90.0, reply_to: Some(Concept::ReplyToVillagerJab), ..line("reply_jab_b", Speaker::Hero, Concept::ReplyToVillagerJab, "Destiny's heavy. Someone has to carry it. Might as well be the fool with the sword.") },
    // These two comebacks chain a SECOND link: the villager gets the last word (jab → comeback →
    // parting shot, three speaker turns through the same `then` machinery — no special casing).
    Line { priority: 12, floor: 90.0, reply_to: Some(Concept::ReplyToVillagerJab), then: Some(LAST_WORD), ..line("reply_jab_c", Speaker::Hero, Concept::ReplyToVillagerJab, "Keep talking. The orks find the loud ones first.") },
    Line { priority: 12, floor: 90.0, reply_to: Some(Concept::ReplyToVillagerJab), then: Some(LAST_WORD), ..line("reply_jab_d", Speaker::Hero, Concept::ReplyToVillagerJab, "One day I'll sleep in. Just the once. See how the jokes hold up.") },
    Line { priority: 12, floor: 90.0, reply_to: Some(Concept::ReplyToVillagerJab), ..line("reply_jab_e", Speaker::Hero, Concept::ReplyToVillagerJab, "Wit like that, the orks would die laughing. Saves me the swinging.") },
    // ── Villager last words (chain replies to a hero comeback — never emitted directly) ──
    // End of the exchange: no `then` here, so the chain terminates.
    Line { priority: 12, floor: 120.0, reply_to: Some(Concept::VillagerLastWord), ..line("last_word_a", Speaker::Villager, Concept::VillagerLastWord, "Ooh, sharp. Practice that one on the cows, did we?") },
    Line { priority: 12, floor: 120.0, reply_to: Some(Concept::VillagerLastWord), ..line("last_word_b", Speaker::Villager, Concept::VillagerLastWord, "Noted, m'lord. I'll scream quieter tonight, just for you.") },
    Line { priority: 12, floor: 120.0, reply_to: Some(Concept::VillagerLastWord), ..line("last_word_c", Speaker::Villager, Concept::VillagerLastWord, "Touchy, touchy. And after everything we do for you.") },
    // ── Guidance: HERO hints (priority 5 musing tier — wait out the hero window; rarely barge) ──
    Line { floor: 300.0, priority: 5, ..line("hint_houses", Speaker::Hero, Concept::AdviseHouses, "Folk are packed in tight down there. I should raise more houses — give them room to grow.") },
    Line { floor: 300.0, priority: 5, ..line("hint_farm",   Speaker::Hero, Concept::AdviseFarm,   "Stomachs are growling louder than the orks. We need a farm before someone faints on the wall.") },
    Line { floor: 300.0, priority: 5, ..line("hint_wood",   Speaker::Hero, Concept::AdviseWood,   "Walls eat timber, and we're nearly dry. Best put someone on the trees.") },
    Line { floor: 300.0, priority: 5, ..line("hint_stone",  Speaker::Hero, Concept::AdviseStone,  "Stone's thin. The hills are full of it — time someone started digging.") },
    Line { floor: 300.0, priority: 5, ..line("hint_upgrade", Speaker::Hero, Concept::AdviseUpgrade, "Coin's piling up. I should spend it at the War Table before I get sentimental about it.") },
    Line { floor: 240.0, priority: 5, ..line("hint_bell",   Speaker::Hero, Concept::AdviseBell,   "Daylight won't hold. When I'm set, the bell calls the night.") },
    Line { floor: 300.0, priority: 5, ..line("hint_walls",  Speaker::Hero, Concept::AdviseWalls,  "These walls won't stop a stiff breeze. I should shore them up while there's light.") },
    Line { floor: 240.0, priority: 5, ..line("hint_prep",   Speaker::Hero, Concept::PrepNudge,    "Quiet now. Doesn't last. Use the hours — loot, build, arm.") },
    // ── Guidance: TOWNSFOLK gripes (Ed) — priority 11 so advice outranks idle chatter (10) but
    //    still yields to event lines (15); spatial, positioned on the nearest peasant. ──
    Line { floor: 300.0, priority: 11, ..line("need_farm_a",  Speaker::Villager, Concept::AdviseFarm,   "We're down to boiled belt-leather, m'lord. Build us a farm. I'm far too pretty to starve.") },
    Line { floor: 300.0, priority: 11, ..line("need_farm_b",  Speaker::Villager, Concept::AdviseFarm,   "The little ones are gnawing the fenceposts. Maybe — just a thought — a farm?") },
    Line { floor: 300.0, priority: 11, ..line("need_house_a", Speaker::Villager, Concept::AdviseHouses, "Eight of us to one cot, m'lord. I know every snore by name. Build a house, I beg you.") },
    Line { floor: 300.0, priority: 11, ..line("need_house_b", Speaker::Villager, Concept::AdviseHouses, "Give us room and we'd breed like rabbits. Houses, m'lord. It's romance, really.") },
    Line { floor: 300.0, priority: 11, ..line("need_wood",    Speaker::Villager, Concept::AdviseWood,   "Can't shore a wall with good wishes. We need wood — put someone on the trees.") },
    Line { floor: 300.0, priority: 11, ..line("need_stone",   Speaker::Villager, Concept::AdviseStone,  "Walls want stone, and we've none. Hills are lousy with it. Send a miner, eh?") },
    Line { floor: 300.0, priority: 11, ..line("spend_gold",   Speaker::Villager, Concept::AdviseUpgrade, "Rich as a bishop, and still swinging that rusty thing. Spend it, m'lord — the War Table.") },
    Line { floor: 300.0, priority: 11, ..line("weak_walls",   Speaker::Villager, Concept::AdviseWalls,  "These walls are a fence and a prayer. The orks point. They laugh. I've seen them.") },
    Line { floor: 240.0, priority: 11, ..line("ring_bell",    Speaker::Villager, Concept::AdviseBell,   "Whenever you're ready for the screaming, the bell's right there. No rush. Some rush.") },
    Line { floor: 300.0, priority: 11, ..line("pop_lost",     Speaker::Villager, Concept::PopLost,      "Buried another last night. Fewer of us to complain at you now. Small mercies.") },
    Line { floor: 600.0, priority: 11, ..line("thriving",     Speaker::Villager, Concept::TownThriving, "Food in the pot, roof overhead — careful, m'lord, you'll spoil us. We'll want chairs next.") },
    Line { floor: 600.0, priority: 11, ..line("strong_walls", Speaker::Villager, Concept::TownThriving, "Lovely strong walls these days. Almost a shame the orks keep knocking.") },
    // ── Warden approach (hero) — priority 15 (urgent tier): approaching a world boss is a rare,
    //    significant beat, so it must cut through the hero-line window (anything < 15 is held while
    //    the window is open, which would silently drop this once-per-warden line). ──
    Line { once: true, ..line("warden_near",   Speaker::Hero, Concept::WardenSighted,          "Something vast sleeps out here. I feel it in my bones — put that beast down, and I'd walk away the stronger for it.") },
    Line { floor: 600.0, ..line("warden_forest", Speaker::Hero, Concept::NearWarden(Biome::Forest), "That old wooden thing among the trees… beat it, and I think my blade would learn a new sweep. I can almost feel it.") },
    Line { floor: 600.0, ..line("warden_snow",   Speaker::Hero, Concept::NearWarden(Biome::Snow),   "Whatever stirs in the ice up here — kill it, and I swear the cold itself would start fighting on my side.") },
    Line { floor: 600.0, ..line("warden_rock",   Speaker::Hero, Concept::NearWarden(Biome::Rocky),  "A mountain that walks. Break it, and maybe I'd learn to bring the mountain down myself.") },
    Line { floor: 600.0, ..line("warden_desert", Speaker::Hero, Concept::NearWarden(Biome::Desert), "That dead thing moves like the wind off the dunes. Put it down, and perhaps I would too.") },
    Line { floor: 600.0, ..line("warden_swamp",  Speaker::Hero, Concept::NearWarden(Biome::Swamp),  "The bog-hag's brewed every poison there is. Best her, and I'd turn that venom loose on the horde.") },
    // ── New-mechanic / new-place beats (2026-07). Clips at `audio/vo/<dir>/<id>.ogg` still need
    //    RECORDING — until the .ogg exists the director no-ops the line (no audio AND no subtitle,
    //    since `play_line` gates the caption on the loaded asset). Transcripts here are the record to
    //    record from (hero = laconic veteran; ork = broken guttural; rival = proud mercenary;
    //    villager = dry). Priorities put the marquee wins/alarms in the urgent tier so they cut the
    //    hero window; the quiet economy beats sit low and wait it out. ──
    // Warlord slain — THE win. Priority 30 (nightfall tier) so nothing buries it; once per run.
    Line { once: true, priority: 30, ..line("warlord_slain_a", Speaker::Hero, Concept::WarlordSlain, "The Warlord's down. Gnashfang Hold is broken. ...It's over. It's finally over.") },
    Line { once: true, priority: 30, ..line("warlord_slain_b", Speaker::Hero, Concept::WarlordSlain, "Their great beast lies still. No more horns. No more nights. We're done.") },
    // The dying horde despairs (ork, spatial — emit at the Warlord's position).
    Line { priority: 15, ..line("ork_warlord_a", Speaker::Ork, Concept::OrkRout, "Warlord... falls. The horde... scatters.") },
    Line { priority: 15, ..line("ork_warlord_b", Speaker::Ork, Concept::OrkRout, "No. No! Who leads us now...") },
    // Hold gate breached. Priority 25 (keep-hurt tier), once per run.
    Line { once: true, priority: 25, ..line("breach_hero_a", Speaker::Hero, Concept::GateBreached, "The gate's down. Nothing between me and the Warlord now. Good.") },
    Line { once: true, priority: 25, ..line("breach_hero_b", Speaker::Hero, Concept::GateBreached, "Gnashfang's open. Whatever's in there, it's mine to end.") },
    Line { priority: 15, ..line("breach_ork_a",  Speaker::Ork, Concept::OrkBreachAlarm, "Man inside the walls! Wake! Wake!") },
    Line { priority: 15, ..line("breach_ork_b",  Speaker::Ork, Concept::OrkBreachAlarm, "Gate broke! Kill it — kill it now!") },
    // Fortress musters for the night assault (ork, spatial — the gate/horn). Floored like raid-march.
    Line { priority: 12, floor: 30.0, ..line("fort_muster_a", Speaker::Ork, Concept::FortressMuster, "Open the gate! To the keep, to the keep!") },
    Line { priority: 12, floor: 30.0, ..line("fort_muster_b", Speaker::Ork, Concept::FortressMuster, "Gnashfang marches! Blood tonight!") },
    Line { priority: 12, floor: 30.0, ..line("fort_muster_c", Speaker::Ork, Concept::FortressMuster, "Horns up! The knight's walls fall tonight!") },
    // World-boss slain + boon (hero). Not once — up to five wardens; floor 600 spaces them.
    Line { priority: 20, floor: 600.0, ..line("warden_slain_a", Speaker::Hero, Concept::WardenSlain, "The beast is dead. I can feel its strength settling into my arm. Worth the scars.") },
    Line { priority: 20, floor: 600.0, ..line("warden_slain_b", Speaker::Hero, Concept::WardenSlain, "Down. Whatever it was guarding, it's mine now — and I'm the stronger for it.") },
    // Rival stronghold destroyed (hero win + rival lament, spatial for the rival).
    Line { once: true, priority: 20, ..line("rival_fell_hero_a", Speaker::Hero, Concept::RivalFell, "The rival's keep is ash. No more raids from the dunes. One less war to fight.") },
    Line { once: true, priority: 20, ..line("rival_fell_hero_b", Speaker::Hero, Concept::RivalFell, "The Pasha's men won't trouble us again. Their sand-castle's rubble.") },
    Line { recorded: false, priority: 15, ..line("rival_fell_a", Speaker::Rival, Concept::RivalLament, "The stronghold... falls. The Pasha will not forgive this.") },
    Line { recorded: false, priority: 15, ..line("rival_fell_b", Speaker::Rival, Concept::RivalLament, "Our walls, our gold — all sand now. Curse you, northerner.") },
    // Rune-trial begun (hero). Priority 15 (urgent tier) so the "here we go" lands; floored.
    Line { priority: 15, floor: 120.0, ..line("trial_start_a", Speaker::Hero, Concept::RuneTrialStart, "The rune wakes. Hold it, the old stories say, and it yields its gift. Let's see.") },
    Line { priority: 15, floor: 120.0, ..line("trial_start_b", Speaker::Hero, Concept::RuneTrialStart, "Guardians of the stone. Beat them, keep the rune. Simple enough.") },
    // Rune-trial won — sealed gear (hero).
    Line { priority: 20, floor: 120.0, ..line("trial_won_a", Speaker::Hero, Concept::RuneTrialWon, "The rune's mine. Sealed gear, forged for no living hand. It'll do.") },
    Line { priority: 20, floor: 120.0, ..line("trial_won_b", Speaker::Hero, Concept::RuneTrialWon, "Trial's done. This is no smith's work — it hums in my grip.") },
    // Landmark discovered (hero). Priority 12 so it clears idle chatter; floor 30 across the five.
    Line { priority: 12, floor: 30.0, ..line("landmark_a", Speaker::Hero, Concept::LandmarkFound, "Now there's a thing. Someone raised this long before me.") },
    Line { priority: 12, floor: 30.0, ..line("landmark_b", Speaker::Hero, Concept::LandmarkFound, "Old stones, old bones. This island keeps its secrets close.") },
    Line { priority: 12, floor: 30.0, ..line("landmark_c", Speaker::Hero, Concept::LandmarkFound, "I'll mark this on the map. Might matter later.") },
    // Heir rises (the new knight, mid-siege). Priority 30 so it cuts the fight; floored, not once.
    Line { priority: 30, floor: 30.0, ..line("heir_rose_a", Speaker::Hero, Concept::HeirRose, "The knight is fallen. ...I have the watch now. The keep still stands.") },
    Line { priority: 30, floor: 30.0, ..line("heir_rose_b", Speaker::Hero, Concept::HeirRose, "Take up the blade. Someone always must. Tonight, it's me.") },
    // War Table upgrade purchased (hero, dry). Low musing tier, waits out the window; floored.
    Line { priority: 8, floor: 45.0, ..line("upgrade_a", Speaker::Hero, Concept::UpgradeBought, "War Table's earned its keep. Let's see them laugh at this.") },
    Line { priority: 8, floor: 45.0, ..line("upgrade_b", Speaker::Hero, Concept::UpgradeBought, "Good steel, coin well spent. I'll feel the difference by dark.") },
    // Building raised (villager cheer, spatial + hero note). Peaceful — drops in a fight.
    Line { priority: 11, floor: 30.0, ..line("build_villager_a", Speaker::Villager, Concept::BuildRaised, "Fresh timbers up! Try not to knock it down, m'lord.") },
    Line { priority: 11, floor: 30.0, ..line("build_villager_b", Speaker::Villager, Concept::BuildRaised, "New roof, new walls. Almost feels like a town again.") },
    Line { priority: 8,  floor: 30.0, ..line("build_hero",       Speaker::Hero,     Concept::BuildRaised, "It's going up. Brick by brick, we're harder to kill.") },
    // Quest step complete (hero). Peaceful.
    Line { priority: 12, floor: 30.0, ..line("quest_done_a", Speaker::Hero, Concept::QuestDone, "That's that done. One less thing gnawing at me.") },
    Line { priority: 12, floor: 30.0, ..line("quest_done_b", Speaker::Hero, Concept::QuestDone, "Task's finished. Small victories — I'll take them where I find them.") },
    // New villager born (villager, spatial). Peaceful.
    Line { priority: 10, floor: 90.0, ..line("born_a", Speaker::Villager, Concept::VillagerBorn, "Another mouth born into all this. Gods help the little one.") },
    Line { priority: 10, floor: 90.0, ..line("born_b", Speaker::Villager, Concept::VillagerBorn, "New babe in the town. More of us to complain at you, m'lord.") },
    // Keep lost — defeat (hero's last word). Priority 30, once.
    Line { once: true, priority: 30, ..line("keep_lost_a", Speaker::Hero, Concept::KeepLost, "The keep... it's falling. I couldn't hold it. ...I'm sorry.") },
    Line { once: true, priority: 30, ..line("keep_lost_b", Speaker::Hero, Concept::KeepLost, "The walls are down. This is how it ends, then. Standing.") },
    // ── Caged captives — clips at `audio/vo/npc/captive/<id>.ogg`, built by
    //    `tools/make_captive_vo.py` (no TTS: cut from the villager recordings above, low-passed,
    //    quietened; the script's `RECIPES` carry the exact source spans). Every spoken subtitle is a
    //    word actually audible in the clip; the wordless ones name the sound. All background
    //    (priority ≤ `BACKGROUND_PRIORITY`) with per-line floors so one cage never repeats itself. ──
    // Sobbing: catches of breath + the falling "Oh," of `greet` and "Ooh" of `pa_shiny`, wavered.
    Line { priority: 1, floor: 40.0, ..line("captive_sob_a", Speaker::Captive, Concept::CaptiveSob, "*muffled sobbing*") },
    // Weeping: the inhale of `screaming` + a softer `pa_shiny` "Ooh" and `greet` "Oh".
    Line { priority: 1, floor: 40.0, ..line("captive_sob_b", Speaker::Captive, Concept::CaptiveSob, "*quiet weeping*") },
    // Three dry coughs: the /s/ of "house" (`need_house_a`) over the /k/ of "came" (`rescued`), dropped.
    Line { priority: 1, floor: 40.0, ..line("captive_cough", Speaker::Captive, Concept::CaptiveSob, "*coughing*") },
    // A low moan: the `pa_shiny` "Ooh" taken down ~4 semitones after a slow inhale.
    Line { priority: 1, floor: 40.0, ..line("captive_groan", Speaker::Captive, Concept::CaptiveSob, "*a low groan*") },
    // "Gods… help…" — the "Gods" + "help" of `born_a` ("...Gods help the little one."), pulled apart.
    Line { priority: 1, floor: 60.0, ..line("captive_gods_help",   Speaker::Captive, Concept::CaptiveMurmur, "Gods… help…") },
    // "Three weeks…" — the opening of `trailer_cage` ("Three weeks I was in there...").
    Line { priority: 1, floor: 60.0, ..line("captive_three_weeks", Speaker::Captive, Concept::CaptiveMurmur, "Three weeks…") },
    // "Buried another last night…" — the first sentence of `pop_lost`.
    Line { priority: 1, floor: 60.0, ..line("captive_buried",      Speaker::Captive, Concept::CaptiveMurmur, "Buried another last night…") },
    // "They're coming…" — the gasp + first words of `siege_fear`.
    Line { priority: 2, floor: 25.0, ..line("captive_coming",  Speaker::Captive, Concept::CaptiveFear, "They're coming…") },
    // "He's right behind me, isn't he?" — the whole of `vill_behind`.
    Line { priority: 2, floor: 25.0, ..line("captive_behind",  Speaker::Captive, Concept::CaptiveFear, "He's right behind me, isn't he?") },
    // A gasp (`siege_fear`) into a high shaking "oh" (`greet`, raised) — no words.
    Line { priority: 2, floor: 25.0, ..line("captive_whimper", Speaker::Captive, Concept::CaptiveFear, "*a frightened whimper*") },
    // "M'lord… I beg you." — "m'lord" + "I beg you" from one take of `need_house_a`.
    Line { priority: 2, floor: 45.0, ..line("captive_beg",  Speaker::Captive, Concept::CaptivePlea, "M'lord… I beg you.") },
    // "You came for me?" — the opening question of `rescued`.
    Line { priority: 2, floor: 45.0, ..line("captive_came", Speaker::Captive, Concept::CaptivePlea, "You came for me?") },
    // "Help… help." — the last word of `taxes` ("...That'll help."), twice, the second weaker.
    Line { priority: 2, floor: 45.0, ..line("captive_help", Speaker::Captive, Concept::CaptivePlea, "Help… help.") },
];

/// All catalog lines for a concept, in declaration order.
pub fn candidates(concept: Concept) -> impl Iterator<Item = &'static Line> {
    LINES.iter().filter(move |l| l.concept == concept)
}

pub fn voice_clip_path(line: &Line) -> Option<String> {
    if !line.recorded { return None; }
    let dir = match (line.concept, line.speaker) {
        (Concept::Script(_), _) | (_, Speaker::Cast(_)) => "campaign",
        (_, Speaker::Hero) => "hero", (_, Speaker::Villager) => "npc",
        (_, Speaker::Ork) => "ork", (_, Speaker::Rival) => "rival", (_, Speaker::Captive) => "npc/captive",
        (_, Speaker::Life) => "life",
    };
    Some(format!("audio/vo/{dir}/{}.ogg", line.id))
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

/// Does this line pass its per-line replay gates right now? Blocked if it's a `once` line already
/// played this run, or if it played more recently than `floor` seconds ago.
pub fn passes_gates(
    line: &Line,
    last: &std::collections::HashMap<&'static str, f32>,
    played_once: &std::collections::HashSet<&'static str>,
    now: f32,
) -> bool {
    if !line.recorded { return false; }
    if line.once && played_once.contains(line.id) {
        return false;
    }
    now - *last.get(line.id).unwrap_or(&f32::NEG_INFINITY) >= line.floor
}

/// Pick a line for `concept`: among candidates, keep only those passing their per-line gates
/// (replay floor + once-per-run), then random-pick. `None` if no candidate is currently eligible.
pub fn pick_line(
    concept: Concept,
    last: &std::collections::HashMap<&'static str, f32>,
    played_once: &std::collections::HashSet<&'static str>,
    now: f32,
    rng: &mut u32,
) -> Option<&'static Line> {
    let fresh: Vec<&'static Line> =
        candidates(concept).filter(|l| passes_gates(l, last, played_once, now)).collect();
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
    /// `elapsed_secs` when the decoded recording finishes (including playback-speed scaling).
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

/// One subtitle channel: ordinary dialogue waits for every speaker. Only a strictly
/// higher urgent line can cut an interruptible utterance, never equal-priority chatter — except a
/// BACKGROUND line (a captive's murmur), which anything that out-ranks it may cut, so the world's
/// real dialogue never queues behind a sob from a cage.
pub fn channel_available<'a>(active: impl Iterator<Item = &'a Active>, now: f32, priority: u8) -> bool {
    active.filter(|a| now < a.ends_at).all(|a| {
        a.interruptible
            && priority > a.priority
            && (priority >= HERO_URGENT_PRIORITY || a.priority <= BACKGROUND_PRIORITY)
    })
}

/// Lines at or below this priority are background murmur (the caged captives): they play only
/// into a silent channel, never hold it against a real line, and don't count as "someone
/// speaking" for the triggers that politely wait their turn (`VoiceManager::others_speaking`).
pub const BACKGROUND_PRIORITY: u8 = 2;

/// Hero-line spacing: while the shared ~20 s window is open, only a genuinely URGENT line —
/// priority at or above this — may barge in. The hero's tiers below it (musings 5, chest/broke 10,
/// comebacks 12) always wait the window out; at/above it sit the real warnings (low-HP/level 15,
/// wave/first-stone 20, keep-hurt 25, nightfall 30).
pub const HERO_URGENT_PRIORITY: u8 = 15;

/// While the hero-line window is open, is a newcomer of `new_priority` still blocked?
/// (`window_priority` = priority of the line that opened the window.) Two conditions to pass:
/// the newcomer must be urgent ([`HERO_URGENT_PRIORITY`]) AND strictly out-rank the opener —
/// merely out-ranking is not enough, or the hero ladders up his own priority tiers (musing,
/// then a chest remark 3 s later because 10 > 5, then a level-up line because 15 > 10…) and
/// never shuts up. An urgent line that does cut through re-stamps the window at its own
/// priority, so everything quieter waits the full cooldown behind it.
pub fn hero_window_blocks(new_priority: u8, window_priority: u8) -> bool {
    new_priority < HERO_URGENT_PRIORITY || new_priority <= window_priority
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bundled_voice_catalog_has_all_recorded_clips_and_skips_planned_lines() {
        let assets = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("assets");
        let last = HashMap::new();
        let once = HashSet::new();
        for line in LINES {
            // Village-life clips are recorded piecemeal: a missing one is simply never loaded.
            if line.speaker == Speaker::Life {
                continue;
            }
            if let Some(path) = voice_clip_path(line) {
                assert!(assets.join(path).is_file(), "missing recorded clip: {}", line.id);
            } else {
                assert!(!passes_gates(line, &last, &once, 0.0), "planned line selected: {}", line.id);
            }
        }
    }
    use std::collections::{HashMap, HashSet};

    #[test]
    fn shared_channel_prevents_two_speakers_and_equal_priority_cuts() {
        let a = Active { id: "test", ends_at: 14.0, priority: 14, interruptible: true, then: None };
        assert!(!channel_available(std::iter::once(&a), 9.0, 14));
        assert!(!channel_available(std::iter::once(&a), 9.0, 10));
        assert!(channel_available(std::iter::once(&a), 9.0, 25));
        assert!(channel_available(std::iter::once(&a), 14.0, 0));
        let protected = Active { interruptible: false, ..a };
        assert!(!channel_available(std::iter::once(&protected), 9.0, 255));
    }

    #[test]
    fn candidates_filters_by_concept() {
        assert_eq!(candidates(Concept::LevelUp).count(), 1);
        assert_eq!(candidates(Concept::ChestOpen).count(), 1);
    }

    #[test]
    fn pick_line_none_when_all_candidates_floored() {
        // LevelUp has a single catalog line (floor 300). Mark it as just played → the only
        // candidate is ineligible → `pick_line` returns None (every concept now has ≥1 line, so we
        // prove the empty-pool path via the floor instead of an unpopulated concept).
        let mut last = HashMap::new();
        last.insert("levelup", 50.0);
        let once = HashSet::new();
        let mut rng = 1;
        assert!(pick_line(Concept::LevelUp, &last, &once, 60.0, &mut rng).is_none()); // 10s < 300 floor
        assert!(pick_line(Concept::LevelUp, &last, &once, 400.0, &mut rng).is_some()); // floor cleared
    }

    #[test]
    fn pick_line_returns_candidate() {
        let (last, once) = (HashMap::new(), HashSet::new());
        let mut rng = 1;
        assert_eq!(pick_line(Concept::LevelUp, &last, &once, 0.0, &mut rng).unwrap().id, "levelup");
    }

    fn test_line() -> Line {
        line("t", Speaker::Hero, Concept::LevelUp, "x")
    }

    #[test]
    fn passes_gates_floor_blocks_then_clears() {
        let mut l = test_line();
        l.floor = 300.0;
        let mut last = HashMap::new();
        last.insert("t", 50.0);
        let once = HashSet::new();
        assert!(!passes_gates(&l, &last, &once, 60.0));  // 10s later → floored
        assert!(passes_gates(&l, &last, &once, 400.0));  // 350s later → cleared
    }

    #[test]
    fn passes_gates_first_play_ignores_floor() {
        let mut l = test_line();
        l.floor = 300.0;
        let (last, once) = (HashMap::new(), HashSet::new());
        assert!(passes_gates(&l, &last, &once, 0.0)); // never played → passes
    }

    #[test]
    fn hero_window_blocks_ordinary_lines_even_when_they_outrank_the_opener() {
        // A priority-5 musing opened the window. A chest remark (10) and a comeback (12) both
        // out-rank it but are NOT urgent → still blocked. (The old relative-only rule let the
        // hero ladder 5 → 10 → 15 back-to-back in a busy minute.)
        assert!(hero_window_blocks(10, 5));
        assert!(hero_window_blocks(12, 5));
        assert!(hero_window_blocks(5, 5));
    }

    #[test]
    fn hero_window_lets_urgent_lines_through_then_reseals_behind_them() {
        assert!(!hero_window_blocks(30, 5)); // nightfall warning cuts through idle chatter
        assert!(!hero_window_blocks(15, 10)); // low-HP cry cuts through a chest remark
        // The urgent line re-stamps the window at ITS priority: equal-or-lower urgency now waits.
        assert!(hero_window_blocks(15, 15));
        assert!(hero_window_blocks(25, 30));
    }

    #[test]
    fn urgent_threshold_splits_the_catalog_where_intended() {
        // Warnings sit at/above the bar; idle observational remarks sit below it, so no remark
        // can ever barge into an open window no matter what opened it.
        for (id, urgent) in
            [("night", true), ("keep_hurt", true), ("hurt", true), ("chest", false), ("people_a", false), ("reply_jab_a", false)]
        {
            let l = LINES.iter().find(|l| l.id == id).unwrap();
            assert_eq!(l.priority >= HERO_URGENT_PRIORITY, urgent, "{id}");
        }
    }

    #[test]
    fn passes_gates_once_blocks_after_played() {
        let mut l = test_line();
        l.once = true;
        let last = HashMap::new();
        let mut once = HashSet::new();
        assert!(passes_gates(&l, &last, &once, 0.0));        // not yet played
        once.insert("t");
        assert!(!passes_gates(&l, &last, &once, 1000.0));    // played once → blocked forever
    }

    #[test]
    fn every_speaker_is_registered() {
        for s in [Speaker::Hero, Speaker::Villager, Speaker::Ork, Speaker::Rival, Speaker::Captive, Speaker::Life] {
            let _ = speaker_voice(s);
        }
        for c in [Cast::Harrow, Cast::Maud, Cast::Pip, Cast::Settler, Cast::Farmer, Cast::Hamid] {
            let _ = speaker_voice(Speaker::Cast(c));
        }
    }

    #[test]
    fn script_lines_resolve_to_exactly_their_own_campaign_clip() {
        let scripted: Vec<_> = LINES.iter().filter(|l| matches!(l.concept, Concept::Script(_))).collect();
        assert!(scripted.len() >= 130);
        for l in scripted {
            assert_eq!(l.concept, Concept::Script(l.id), "{} must be keyed by its own id", l.id);
            assert_eq!(candidates(Concept::Script(l.id)).count(), 1, "duplicate key {}", l.id);
            if l.recorded {
                assert_eq!(voice_clip_path(l).unwrap(), format!("audio/vo/campaign/{}.ogg", l.id));
            }
        }
    }

    #[test]
    fn captive_murmurs_are_background_and_yield_to_any_real_line() {
        let caps: Vec<&Line> = LINES.iter().filter(|l| l.speaker == Speaker::Captive).collect();
        assert_eq!(caps.len(), 13);
        for l in &caps {
            assert!(l.priority <= BACKGROUND_PRIORITY && l.interruptible && l.floor > 0.0, "{}", l.id);
            assert!(!is_peaceful(l.concept), "{}: a guarded cage is always 'in danger'", l.id);
            assert!(voice_clip_path(l).unwrap().starts_with("audio/vo/npc/captive/captive_"));
            // A wordless clip is captioned as a sound, never as invented words.
            let sound = l.text.starts_with('*');
            assert_eq!(sound, l.text.ends_with('*'), "{}", l.id);
            assert_eq!(sound, matches!(l.id, "captive_sob_a" | "captive_sob_b" | "captive_cough"
                | "captive_groan" | "captive_whimper"), "{}", l.id);
        }
        let sob = Active { id: "captive_sob_a", ends_at: 10.0, priority: 1, interruptible: true, then: None };
        // A greeting (10), a hero musing (5) or a fear line (2) cuts a sob…
        assert!(channel_available(std::iter::once(&sob), 5.0, 10));
        assert!(channel_available(std::iter::once(&sob), 5.0, 5));
        assert!(channel_available(std::iter::once(&sob), 5.0, 2));
        // …but another sob never talks over it, and ordinary chatter still can't cut real lines.
        assert!(!channel_available(std::iter::once(&sob), 5.0, 1));
        let greet = Active { id: "greet", priority: 10, ..sob };
        assert!(!channel_available(std::iter::once(&greet), 5.0, 2));
        assert!(!channel_available(std::iter::once(&greet), 5.0, 12));
        assert!(channel_available(std::iter::once(&greet), 5.0, 15));
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
        assert!(can_play(Some(&a), 6.0, 0));
    }

    #[test]
    fn cannot_interrupt_protected_line() {
        let a = active(50, false, 100.0);
        assert!(!can_play(Some(&a), 1.0, 255));
    }

    #[test]
    fn interrupt_needs_equal_or_higher_priority() {
        let a = active(50, true, 100.0);
        assert!(!can_play(Some(&a), 1.0, 49));
        assert!(can_play(Some(&a), 1.0, 50));
        assert!(can_play(Some(&a), 1.0, 200));
    }

    // ── Call-and-response chain (D3) ───────────────────────────────────────────────────────────

    #[test]
    fn jab_lines_dispatch_the_reply_chain() {
        // The three at-the-hero villager jabs each finish with a `then` that targets the hero.
        for id in ["pa_hero", "pa_chosen", "pa_slept"] {
            let l = LINES.iter().find(|l| l.id == id).unwrap();
            let chain = l.then.unwrap_or_else(|| panic!("{id} should chain a reply"));
            assert_eq!(chain.concept, Concept::ReplyToVillagerJab);
            assert_eq!(chain.target, Speaker::Hero);
            assert!(chain.manual, "the comeback is offered to the player, not auto-played");
        }
    }

    #[test]
    fn reply_pool_answers_the_jab() {
        // `replies_to` is what the director's `tick_chains` queries: every match is a hero line
        // tagged as a valid reply, and there's a pool of them (the user's "a set of replies that
        // fit a prompt").
        let pool: Vec<&Line> = replies_to(Concept::ReplyToVillagerJab).collect();
        assert!(pool.len() >= 2, "want a pool of comebacks, got {}", pool.len());
        assert!(pool.iter().all(|l| l.speaker == Speaker::Hero));
        assert!(pool.iter().all(|l| l.reply_to == Some(Concept::ReplyToVillagerJab)));
    }

    #[test]
    fn chain_resolves_end_to_end() {
        // Replay exactly what `tick_chains` does once a `pa_*` jab finishes: take the chain, gather
        // replies for it, filter to the target speaker + per-line gates, pick the highest priority.
        let chain = LINES.iter().find(|l| l.id == "pa_slept").unwrap().then.unwrap();
        let (last, once) = (HashMap::new(), HashSet::new());
        let pick = replies_to(chain.concept)
            .filter(|l| l.speaker == chain.target)
            .filter(|l| passes_gates(l, &last, &once, 0.0))
            .max_by_key(|l| l.priority);
        let reply = pick.expect("a fresh jab should resolve to a comeback");
        assert_eq!(reply.speaker, Speaker::Hero);
        assert!(reply.id.starts_with("reply_jab_"));
    }

    // ── Second-level chain: jab → comeback → villager last word ────────────────────────────────

    #[test]
    fn some_comebacks_hand_the_villager_the_last_word() {
        let chained: Vec<&Line> = replies_to(Concept::ReplyToVillagerJab)
            .filter(|l| l.then.is_some())
            .collect();
        assert!(!chained.is_empty(), "at least one comeback should chain a last word");
        for l in &chained {
            let chain = l.then.unwrap();
            assert_eq!(chain.concept, Concept::VillagerLastWord);
            assert_eq!(chain.target, Speaker::Villager);
            assert!(!chain.manual, "the NPC's parting shot plays on its own");
        }
        // ...but not ALL of them — sometimes the hero ends the exchange.
        assert!(
            replies_to(Concept::ReplyToVillagerJab).any(|l| l.then.is_none()),
            "some comebacks should end the exchange"
        );
    }

    #[test]
    fn last_word_pool_answers_and_terminates() {
        let pool: Vec<&Line> = replies_to(Concept::VillagerLastWord).collect();
        assert!(pool.len() >= 2, "want a pool of last words, got {}", pool.len());
        assert!(pool.iter().all(|l| l.speaker == Speaker::Villager));
        // The exchange must END here: a last word that chained again could ping-pong forever.
        assert!(pool.iter().all(|l| l.then.is_none()));
    }

    #[test]
    fn three_step_chain_resolves_end_to_end() {
        // jab (villager) → comeback (hero) → last word (villager), replaying `tick_chains` twice.
        let (last, once) = (HashMap::new(), HashSet::new());
        let jab = LINES.iter().find(|l| l.id == "pa_armor").unwrap();
        let step1 = jab.then.expect("jab chains a comeback");
        let comeback = replies_to(step1.concept)
            .filter(|l| l.speaker == step1.target && l.then.is_some())
            .max_by_key(|l| l.priority)
            .expect("a chaining comeback exists");
        let step2 = comeback.then.unwrap();
        let last_word = replies_to(step2.concept)
            .filter(|l| l.speaker == step2.target)
            .filter(|l| passes_gates(l, &last, &once, 0.0))
            .max_by_key(|l| l.priority)
            .expect("the villager gets the last word");
        assert!(last_word.id.starts_with("last_word_"));
        assert!(last_word.then.is_none(), "and the exchange ends there");
    }

    #[test]
    fn stale_chain_self_terminates_when_pool_floored() {
        // If every comeback is on its replay floor (the hero just fired one), the chain finds no
        // reply and silently dies — the Valve "no explicit interruption" property.
        let chain = REPLY_TO_JAB;
        let mut last = HashMap::new();
        for l in replies_to(chain.concept) {
            last.insert(l.id, 0.0); // all played at t=0
        }
        let once = HashSet::new();
        let any = replies_to(chain.concept)
            .filter(|l| l.speaker == chain.target)
            .any(|l| passes_gates(l, &last, &once, 10.0)); // 10s later, floor 90 still active
        assert!(!any, "a floored pool should yield no reply → chain self-terminates");
    }
}
