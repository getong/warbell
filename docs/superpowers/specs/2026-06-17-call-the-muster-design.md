# Call the Muster (fortress-endgame Phase 2) — design

**Date:** 2026-06-17
**Status:** approved, implementing
**Roadmap:** `docs/superpowers/specs/2026-06-07-tileworld-parity-port-roadmap.md`;
fortress endgame plan (memory `fortress-endgame-plan`). This is **Phase 2** of three.

## Goal

Give the player a war party. Press a key and the castle's free-roaming guards fall in and
follow the hero around — and fight alongside him. Net-new "something follows the hero" layer
(nothing does today). Testable solo as a parade in Prep, before any fortress fight (Phase 3).

## Trigger & state

- **Key `K`** (free; `1–5` = biome swap, war bell `E` is taken to ring in the night) toggles
  the muster in Play mode, gated `run_if(in_state(Modal::None))`.
- **On:** the **whole standing town pool** falls in (decided with the user — matches the endgame
  plan's "march your whole roster by day"). Existing guards leave their posts; **workers down
  tools** (shed `Worker` + any chop/mine job, armed via `arm_as_guard`) so production pauses while
  rallied — a real cost. Each gains a `Rallied { slot, home }` marker (`slot` = ring index in join
  order; `home` = the post it returns to). `auto_assign_workers` (town.rs) is taught to skip
  `Rallied` guards so they stay fallen-in instead of being re-employed the same day.
- **Off (press `K` again):** restore each guard's `home` post and drop `Rallied`; guards path back
  via the existing return-to-post logic, and the day auto-assign re-employs them.
- Feedback: a hero voice line + a `Toast` ("To me!") on call if the plumbing already exists;
  otherwise silent (no new audio asset work for Phase 2).

## Architecture — reuse, don't duplicate

Chosen approach: **extend the existing `villagers.rs` Guard combat** rather than write a parallel
follow system. A guard's `post: Vec2` already drives both its leash and its return-home pathing,
and `guard_combat` already does "hunt a hostile near the post within leash, else path back to
post." So if `post` *is* the hero, follow + peel-off-to-fight + regroup all fall out of the
tested code with no new combat logic.

### `Rallied` component
```rust
#[derive(Component, Clone, Copy)]
pub struct Rallied { slot: usize }
```

### `rally_follow` system (new; ordered before `guard_combat`)
For each `Rallied` guard:
1. Compute its ring-slot world XZ around `HeroState.pos` — slots evenly spaced on a ~3.5-unit
   ring, indexed by `slot` so guards don't stack.
2. Write that point into `guard.post`.

Then `guard_combat` (unchanged) paths/steers the guard toward the moving post, peels to any
hostile inside its detect radius, and returns when the foe is down. To avoid A* thrash from a
post that moves every frame, only treat the goal as "moved" when the hero has shifted beyond the
existing replan tolerance (~2 units) — the per-guard replan stagger already in `guard_combat`
covers the rest.

### `muster_keys` system (new)
Reads `KeyCode::KeyK` `just_pressed`. **Stateless toggle** (no resource): if any `Rallied` guard
exists, stand the party down; else rally the whole `Townsfolk` pool via a shared `rally_one` helper
(down-tool workers, arm, tag `Rallied`). Deriving the state from the live `Rallied` set means it
self-corrects after a load — no reset path needed. The `fresh` (`Without<Rallied>`) and `rallied`
(`With<Rallied>`) queries are archetype-disjoint, so accessing `Guard` in both doesn't conflict.

### `FOREST_MUSTER` staging hook (`stage_muster`, new)
Screenshot/clip helper in the `FOREST_*` family: when set, re-tags any not-yet-rallied pool member
each frame (catching the bodies `sync_population_bodies` spawns over several frames), so a single
capture shows the war party. Cached env read → free when unset. Logs the running count.

## Scope (Phase 2 only)

In: rally toggle, ring-formation follow, fight-while-following (peel/regroup), dismiss.
Out: fortress march, gate breach, Warlord, Victory — all Phase 3. Keep archers excluded
(`defenses.rs` roof models can't move, no HP).

## Persist / reset

`Rallied` / `MusterState` is **transient battlefield state**, in the same category as timed
`Buffs` and live invaders: deliberately **not** saved. On Continue/New Game guards rebuild fresh
and unrallied. Add a one-line note to the "deliberately not saved" list in `savegame.rs` so this
reads as a decision, not a missed round-trip. No `SaveData` changes.

## Test / verify

- `cargo test` (core unaffected; no logic moved to core for Phase 2).
- Manual: boot to Play in Prep, press `K`, walk — guards form a ring and follow; press `K`
  again — they return to posts. Stage a light Prep skirmish (or wait for a wave) and confirm
  guards peel to fight a nearby ork and regroup after.
- Screenshot proof of the parade via the capture harness if it reads well.
