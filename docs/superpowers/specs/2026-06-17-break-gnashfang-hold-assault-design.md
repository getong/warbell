# Break Gnashfang Hold — the assault & win condition (Fortress endgame, Phase 3)

**Date:** 2026-06-17 · **Status:** approved (user: "okay implement")

Phase 3 of the fortress-endgame plan (`docs/superpowers/specs/` + the `fortress-endgame-plan`
memory). Phases 1–2 (visible night muster + `K` Call-the-Muster) shipped. This phase gives the
game its **win condition**: break into Gnashfang Hold and kill the Warlord.

## Decisions (user-confirmed)

1. **Assault is the ONLY win; nights loop forever.** Clearing the last wave no longer fires
   `Victory` — nights keep coming, replaying the hardest wave with the existing hero-level HP
   escalation, forever. The only `GamePhase::Victory` is the Warlord's death.
2. **Proximity breach.** Walk up to the Hold gate → a clear UI cue ("you can break the gate") →
   press **E** to breach. Breaking it wakes the whole garrison (incl. the Warlord) into real
   combatants. Killing the Warlord = game over (Victory). The Warlord is **hard-leashed** — it
   barely chases.
3. **Breach anytime; keep siege runs independently.** Day or night. The nightly siege on the
   castle continues on its own (two-front by choice). The fortress garrison **respawns every
   night**.

## Architecture (by subsystem)

### 1. Win condition — `src/siege.rs` + `crates/core`
- `step_wave_director`: drop the `Victory` transition. Clearing the final wave → `Prep` (loop).
  In the `Wave` arm, clamp `WAVES` indexing (`i.min(WAVES.len()-1)`) instead of early-returning,
  so nights past the table replay the last wave; `wave_index` keeps incrementing (the "Night N"
  counter climbs forever) and `ork_level_hp_mul` keeps escalating difficulty.
- Update the director unit test (`last wave cleared → Victory`) to assert `→ Prep`.
- Core `Player`: add `conquered_warlord: bool` (`#[serde(default)]`, defaults false). Rides the
  save automatically like the warden boons.

### 2. Breach prompt — `src/interaction.rs` + `src/ork_fortress.rs`
- `ork_fortress.rs`: `pub` the `GATE` const; add `#[derive(Resource, Default)] AssaultState
  { breached: bool }` and a `BreachGate` message.
- `interaction.rs`: new `InteractKind::BreachGate` candidate anchored at `GATE` (radius ~6u),
  available while the fortress exists + hero alive + `!breached` + `!conquered_warlord`. Press
  **E** → emit `BreachGate`. Prompt label "Break the gate".
- **Visual cue:** a dedicated warp-green emissive beacon mesh at the gate (`GateBeacon`), hidden
  until the hero is in breach range (and `!breached`), pulsing scale/visibility; plus a one-time
  notice "The gate of Gnashfang Hold stands before you — break it open."

### 3. The breach — `src/ork_fortress.rs`
On `BreachGate` (once): set `breached`, swing the gate open (`DirectorState.gate_open = true`),
`blockers::remove_box_near(GATE, ~0.6)` to clear the wall gap, blare horn + roar, notice, hide the
beacon. Convert the garrison: despawn every decorative `Denizen` and respawn a real
**home-leashed** `orks::Ork` at its spot via the kept `BlightPatrols` armory (`Armory::spawn`,
home = its anchor) — they defend the Hold, they don't march the keep. The pacing-warlord `Denizen`
is replaced by the real Warlord (§4).

### 4. The Warlord — new `src/warlord.rs`
A standalone boss, NOT the biome-keyed `boss::Boss`:
- Visual = `Armory::spawn_prop(Berserker, Red, pos, facing, 1.55)` (oversized berserker, `OrkPart`
  limb children) + inserted `Warlord` marker + `Health` (high, scaled by hero level at spawn).
- Hittable: add `With<crate::warlord::Warlord>` to the `Or<>` target filter in `player/combat.rs`
  and `player/arts.rs` (two-line edits). Then swings/arts/cleave + Frostbite/Venom/Poisoned/Slowed
  all apply for free; combat's kill path inserts `Dying` (ork=None ⇒ no bounty orb — bounty/gold
  handled in the death-watch if desired).
- Brain (adapted from `boss_brain`, simpler): hard leash (~12–14u from its hall/spire home; returns
  home if the hero leaves or falls), moderate speed, melee on cooldown, one telegraphed crit
  (reuse the rear-back + shockwave + block/dodge window), honors `Slowed`. `warlord_limbs` animates
  the `OrkPart` children (stride/arms/crit-rear), like `denizen_limbs`/`boss_limbs`.
- Health bar: a dedicated bottom-centre bar (mirrors `boss::sync_boss_bar`) titled "The Warlord".
- Death-watch (`With<Warlord> + With<Dying>`, once via a `Rewarded`-style marker): set
  `player.conquered_warlord = true`, `siege.phase = GamePhase::Victory`, push a slain notice + a
  hero victory bark.

### 5. Nightly garrison respawn — `src/ork_fortress.rs`
On the nightfall (`Prep→Wave`) edge, if `breached` && warlord alive, top the live garrison back up
to roster size at the roster homes (reuse the armory). The Warlord is one-and-done.

### 6. Persistence / reset
The assault is **transient** (not saved — like the swept battlefield). On `GameLoaded`, reconcile
the fortress to pristine: despawn the live Warlord + garrison orks, clear `AssaultState`, re-shut
the gate (`gate_open = false`) + re-add the gate OBB, and respawn the decorative denizen roster
(factor the build's denizen spawn into a reusable fn). Block manual save while `breached`. New Game
resets via the normal exe-relaunch rebuild (`conquered_warlord` defaults false; `AssaultState`
defaults).

## Reuse surface (no new movement/combat systems)
- Gate swing: existing `cinematic::animate_fortress_gate` via `DirectorState.gate_open`.
- Gate blocker drop: existing `blockers::remove_box_near` (documented for exactly this).
- Garrison combat: existing `orks.rs` home-leashed brain (`Armory::spawn`), same as the patrols.
- Hero hitting the Warlord: one `Or<>` branch in two files.
- Status/poison/slow ticking + the `Dying` fade: existing `boss::tick_status` + `dying.rs`.
- Bringing a war party south: the player walks with `K` muster active — no auto-march needed.

## Verification
`cargo test` (the updated director loop test). `cargo check` + full build. Screenshot/clip the
breach + Warlord fight (`FOREST_HERO` near the gate; a staged `FOREST_*` breach hook if useful).
Confirm: nights loop past wave 8 (no auto-Victory), the E cue appears at the gate, breach wakes the
garrison + Warlord, Warlord death → VICTORY, garrison refills at nightfall, Continue resets the
fortress to pristine.
