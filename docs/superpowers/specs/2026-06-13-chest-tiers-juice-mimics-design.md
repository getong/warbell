# Chest Tiers, Juice & Gnashfang Mimics — Design

**Date:** 2026-06-13
**Status:** Approved (brainstorm) — ready for implementation plan.

## Goal

Make chests carry more of Warbell's personality and pull the hero outward. Three things,
layered so a *frequent* interaction never turns into friction:

1. **More chests** + **2 tiers** (distance-gated) → deep biomes hold richer chests = the
   exploration carrot (doubles down on the existing frontier-graded loot).
2. **Every open is instant + juicy** — no UI minigame. Character comes from sound + animation
   + a rarity tell + a hero bark, not a skill meter.
3. **Risk = Gnashfang mimics** — a share of the richest chests bite back. The "skill" is
   *perception + reaction* (spot the tell, pre-attack), never a dexterity gate.

### Research basis (why this shape)

A web survey of chest/lock minigames (Skyrim, Dark Souls mimics, Sea of Thieves cursed chests,
Zelda chest jingle, Diablo loot beams, Balatro juice — see Sources) landed on one firm rule:
**a skill gate on a high-frequency action becomes fatigue** (the canonical "Skyrim lockpick
fatigue"). The consensus fix: keep the open near-instant, let the *open* feel great every time,
make depth *optional*, and make *some* chests special rather than every one a puzzle. Hence:
instant juicy opens for all, with mimics as the rare characterful risk.

Sources: Dark Souls mimics (Fextralife), Sea of Thieves cursed chests (SoT wiki), Zelda chest
sound (fab.industries), color-coded loot origins (Tales of the Aggronaut / GameSpot), juice
(Blood Moon Interactive), lockpick-fatigue commentary (TheGamer, GameDev.net, ESO forums).

## Non-goals (YAGNI)

- No UI/lockpicking minigame, no timing meter, no carry-the-cursed-chest hauls (Sea of Thieves
  "carry it home" was considered and cut — needs an encumbrance system).
- No mimic *pathfinding* — mimics are rooted (a chest doesn't chase).
- No new save schema — mimic-vs-real is re-derived deterministically from `ChestId`.
- Caches (the dawn-refill food/gold economy) are untouched by tiers and are never mimics.

## Architecture: new `src/chest.rs` plugin

Chests have grown into a real subsystem; [verbs.rs](../../../src/verbs.rs) (~1500 lines) already
owns ore + forage + drops. Extract all chest code into its own one-feature plugin (matches the
`main.rs` table-of-contents convention).

**Move out of `verbs.rs` into `src/chest.rs`:**
`Chest`, `ChestId`, `ChestLid`, `LidSwing`, `CHEST_LID_OPEN`, `TROPHY_CHEST_ID`,
`chest_interact`, `chest_respawn`, `populate_chests`, the chest/lid mesh builders, the deep-rim
hoard + Gnashfang trophy spawners, and the chest-local `tile_hash` helper.

`verbs.rs` keeps ore/forage/drops and continues to own the `HeroSwing` broadcast (the mimic and
mining both *read* it). `worldmap::build` calls `crate::chest::populate_chests(...)` instead of
`crate::verbs::populate_chests(...)`. Register `ChestPlugin` in `main.rs`. Every sim system keeps
`.run_if(in_state(Modal::None))` so panels/pauses still freeze chests and mimics.

## 1. Tiers — `enum ChestTier { Wood, Relic }`

Distance-gated off the existing `forest_frontier(x, z)` gradient:

| Tier  | Frontier | Where            | Loot                                                    | Glow      |
|-------|----------|------------------|---------------------------------------------------------|-----------|
| Wood  | `< 0.5`  | home grass / mid | current `frontier::roll_gear` curve (1–2 items, stingy) | none/faint |
| Relic | `>= 0.5` | deep biomes      | top-pool floor + 2–3 items (today's hoard-style roll, **minus** the heavy purse) | warm gold |

- Tier is computed at spawn from the chest's world position and stored on `Chest` (a `tier:
  ChestTier` field). Deterministic, so it survives reloads with no save change.
- **Caches are exempt** — tiers rank *treasure* only. A cache stays the dawn-refill food/gold
  drop it is today, regardless of where it sits.
- **Visual tell** (Diablo-style at-a-distance read): a tier-colored **emissive glow child** —
  a short "loot beam" + a faint rim around the lock. Wood = no beam (or a barely-there warm
  fleck); Relic = a clear gold beam. The glow is a **separate emissive child mesh**, so the
  shared white body `StandardMaterial` keeps auto-batching (CONTRACT.md mesh rule intact).

## 2. The juicy open (every non-mimic chest, instant on F)

On a valid F-press within `CHEST_INTERACT_DIST`, fire the full pipeline (extends today's
lid-swing + gold-popup + `ChestOpen`/`Gold` cues):

1. **Lid** — `LidSwing` overshoot-and-settle (already implemented).
2. **Beam flare** — the tier glow child flares bright then fades over ~0.5s (gold for Relic).
3. **Particle burst** — a one-shot sparkle/dust puff at the lid mouth.
4. **Tiered chime** — 2 `AudioCue` variants (Wood vs Relic; Relic is the richer/longer
   fanfare). Layered over the existing coin `Gold` chime when gold > 0.
5. **Gold popup** — existing `FloatReq` `+N gold` float.
6. **Screen-shake** — push `FeedbackState.trauma` (combat_fx), scaled by tier: a tiny tick for
   Wood, a satisfying punch for Relic. Reuses the existing trauma→camera shake path.
7. **Hero bark** — `Speak(Concept::ChestOpen)` (already wired). Add a couple of tier-flavored
   lines to [lines.rs](../../../src/audio/lines.rs) (e.g. a bigger "now THAT's a haul" line that
   prefers the Relic open). Each new line carries its spoken transcript in a comment (repo rule).

Bag-full still rejects the open (existing behavior). Caches reuse this same juicy pipeline at
Wood intensity.

## 3. Gnashfang mimics — `Component Mimic`, `enum ChestKind { Real, Mimic }`

**Who is a mimic**
- **Relic tier only**, treasure only — never a cache, never a Wood chest, never inside the 14u
  home safe-radius.
- Rolled **deterministically per `ChestId`** at spawn (`hash(ChestId) < MIMIC_RATE`), so the
  same chests are mimics every run and reloads stay consistent. `MIMIC_RATE ≈ 0.20` of Relic
  treasure.

**The tell** (when the hero is within ~4u)
- A looping low **Gnashfang growl** (spatial SFX).
- The **teeth** mesh nudges out of the lid seam — a small `sin`-driven wobble, not a billboard.
- The glow turns **wrong**: sickly ork-green instead of the tier's gold. A reading player
  notices; a greedy one doesn't.

**Combat** — mimic is a **rooted** enemy
- Has `Health` (small — dies in a few hits), reads the **`HeroSwing`** cone for incoming damage
  (the same broadcast mining consumes).
- **Bites** the hero when in melee range: a short lunge + cooldown, damage ≈ ork-grunt
  (`orks::variant_melee`-derived).
- Death → `Dying` fade (dying.rs) + **grants its loot on death via the same path as a normal
  open** (straight to purse/bag, with the bag-full reject), not a ground drop — avoids a
  bag-full edge case mid-combat. All entity mutation via `try_despawn`/`try_insert`
  (despawn-race rule).

**Risk / reward**
- **Open blind** (press F while still disguised): the mimic gets a **free bite** (burst damage)
  and wakes. Kill it for its **normal** Relic loot.
- **Pre-attack** (you spotted the tell and hit it while closed): **no** free bite; on death it
  drops **bonus** loot — the payoff for perception.

**When** — mimics live and fight only during prep (they carry the `Modal::None` gate and are not
spawned into the night-siege ring); a siege never turns into a mimic pile-on.

## 4. Placement & density

- Scatter `CHEST_COUNT` **12 → 24** in `populate_chests`. Same reject-sampling (off
  water/blockers/camps/build-plots/bridges/courtyard).
- 5 deep-rim hoards + the Gnashfang trophy chest: unchanged.
- Tier + mimic-roll computed inside `populate_chests` from each placed chest's world position +
  `ChestId`.

## 5. Save & compatibility

- The save already keys looted/opened state by `ChestId` ([savegame.rs](../../../src/savegame.rs))
  — confirm during implementation. A killed mimic uses the same looted flag as an opened chest.
- `ChestKind` (mimic vs real) and `ChestTier` are **re-derived** from position + `ChestId` on
  load — no new persisted fields.

## 6. Testing

- **Pure fns** are unit-testable (in `src/chest.rs`, mirroring the `crates/core` test style):
  `tier_for(frontier) -> ChestTier`, `is_mimic(chest_id) -> bool` (rate + Wood/cache exclusion),
  loot-count per tier. Assert: no Wood mimics, caches never mimics, Relic mimic share ≈ 20%,
  tier split at 0.5.
- **Visual** — `FOREST_SHOT` staging: a Relic chest (gold beam) beside a mimic mid-tell
  (green glow + teeth out) to eyeball the tells read clearly. (See the screenshot-harness env
  vars in CLAUDE.md.)
- `cargo test` + a normal single-session `cargo run` to verify open feel, mimic bite, and that
  panels/pauses freeze the new systems.

## Open decisions already settled

- **2 tiers** (Wood / Relic), split at frontier 0.5. *(user choice)*
- **Mimics: Relic only, ~20%**, rooted, bite ≈ ork-grunt.
- **Scatter 24** chests.
- **No UI minigame; instant juicy opens.** *(user choice)*
- **Fair tell, punishing blind-open bite, bonus loot for pre-attack.** *(user choice)*
- **New `src/chest.rs` plugin.** *(user choice)*
