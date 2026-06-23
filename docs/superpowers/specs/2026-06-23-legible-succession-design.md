# Legible Succession ("Steal the Body") + Last-Hero Alert — design

**Date:** 2026-06-23
**Status:** approved, implementing

## Problem

Players don't understand succession. Today, when the hero dies he simply blinks to the
north gate after a dead-feeling ~1.6 s pause while `town.population` silently drops by one
(`player/health.rs::apply_hero_damage`). Nothing on screen explains that **an heir is a
townsperson** — that the bloodline literally *takes over a peasant's body*. And there is no
warning when the town runs out of heirs, so the player has no idea their next death is final.

## Goals

1. Make succession legible as **possession of the nearest peasant**: a short directed beat
   where the camera frames the nearest living townsperson, the soul wisp flies from the
   corpse into them, and they transform into the hero *where they stand* (the new hero takes
   control there).
2. Warn the player, unmissably, when **no heirs remain** (`population == 0`) — their next
   death ends the run.

Non-goals: changing the bloodline *rules* (heirs ≡ `town.population`), the defeat condition,
or the save format. No `crates/core` changes.

## Decisions (locked with the user)

- **Respawn location:** at the stolen peasant (not the gate). Accepted tradeoff: mid-siege the
  nearest peasant may be at the keep/in town, so the hero can resurrect away from where he fell.
- **Feel:** a *brief dramatic beat* — ~1.2 s of slow-motion, a camera swing to the peasant, the
  wisp arc, a transform flash, then control + normal speed return. Replaces today's dead pause.
- **Alert:** a one-time **stinger** ("THE LINE ENDS WITH YOU") on the 1→0 transition, plus a
  **persistent red banner** while `population == 0`, auto-clearing when the town regrows an heir.

## Architecture

### 1. The succession beat — `Succession` resource + `drive_succession`

A new transient resource owns the beat as a tiny real-time state machine; the per-frame damage
system no longer does the respawn itself.

```
Succession {
  active: bool,
  final_death: bool,     // died with 0 heirs → this beat ends in Defeat, not a rise
  transformed: bool,     // the swap has happened (fire-once guard)
  real_t0: f32,          // Time<Real> elapsed at beat start (phase clock is real-time)
  corpse_pos: Vec3,      // where the hero fell (wisp launches here)
  steal_entity: Option<Entity>, // the peasant whose body we take (None → gate fallback)
  steal_pos: Vec3,       // where the new hero rises (peasant pos, or gate)
  cam_blend: f32,        // 0..1 — how far the camera is pulled to the cinematic framing
}
```

**Phase clock is `Time<Real>`** so the beat is a fixed wall-clock duration regardless of the
slow-mo applied to `Time<Virtual>`. Constants (real seconds):

- `CAM_IN = 0.30` — ease `cam_blend` 0→1
- `TRANSFORM_T = 1.05` — the swap instant
- `RESUME_END = 1.40` — ease speed back to 1× and `cam_blend` 1→0; beat ends
- `SLOW_SPEED = 0.28` — `Time<Virtual>` relative speed during the beat
- `RISE_IFRAMES = 1.0` — spawn-protection (virtual secs) granted to the risen hero

`drive_succession` (run_if `AppState::Playing`):

- **Start (not active):** if `player.dead_since.is_some()` → begin a beat. Capture `corpse_pos`.
  If `population == 0` → `final_death = true`, no steal target. Else find the nearest living
  `Townsfolk` to the corpse → `steal_entity`/`steal_pos` (fallback to the north gate if none) and
  emit `HeirFell{ grave_at: corpse, rise_at: steal_pos }` so the wisp flies corpse→peasant.
- **Run:** drive `Time<Virtual>` relative speed (ease to `SLOW_SPEED`, back to 1× during resume)
  and `cam_blend`. At `TRANSFORM_T`, once: if `final_death` → `lives.defeat = true` and snap speed
  back to 1× (→ GameOver). Else → `population -= 1`, `try_despawn(steal_entity)`, relocate the
  persistent hero entity to `steal_pos`, `respawn_at` (full HP), reset stamina, grant
  `RISE_IFRAMES`, and emit `HeirRose{ at: steal_pos }` for the flash. At `RESUME_END` → end beat.

**Safety:** an `OnExit(AppState::Playing)` system forces `Time<Virtual>` speed back to 1× and
clears `Succession`, so a pause / GameOver mid-beat can never leave the world stuck in slow-mo.

`apply_hero_damage` is trimmed to *only* apply damage / set `dead_since` (the whole
`dead_since → respawn` block, plus its `lives`/`town`/`villagers`/`commands`/`fell` params, move
into `drive_succession`). This also drops it back under Bevy's 16-param cap.

### 2. Camera — cinematic blend in `player_camera`

`Succession` is added to the existing `CamGate` SystemParam (keeps `player_camera` at the param
cap). After the normal follow/FP pose is resolved and before the build-mode lerp, if a beat is
active the camera lerps toward a framing of `steal_pos` by `cam_blend`, reusing the current orbit
azimuth/pitch (pulled back a touch) so the move reads as the camera *orbiting the peasant*, not a
random cut. Because the risen hero ends up *at* `steal_pos`, easing `cam_blend` back to 0 during
resume hands control smoothly back to the normal follow.

### 3. The transform flash — `succession_fx.rs`

The wisp already flies `from`→`to`; only its target changes (peasant, via the message). Tune
`SOUL_DUR` so the wisp lands ~at the transform given the slow-mo virtual-time budget. Add a
`HeirRose{ at }` message → a brief expanding, fading emissive flash at the rise point to sell the
"peasant becomes the hero" pop.

### 4. The alert — new `succession_alert.rs` plugin

Reads `TownRes`; **no new saved/derived state**. A persistent banner node (spawned hidden) is
toggled visible while `population == 0 && AppState::Playing`. A `Local<Option<u32>>` tracks the
previous population; on a `>0 → 0` transition while playing, spawn a centered **stinger** entity
that fades over ~2.5 s. Stingers are cleared on `OnExit(StartScreen)`/`OnExit(GameOver)`; the
banner self-corrects from `population` each frame, so no explicit reset is needed. Styling pulls
from the UI kit (`ui::theme` reds, `ui::fonts` Cinzel display for the stinger).

## Edge cases / save / reset

- Night militia keep the `Townsfolk` tag (`arm_as_guard` only *adds* `Guard`), so a body is
  always available to steal during a siege.
- `population > 0` but no `Townsfolk` entity found → rise at the north gate (old behavior), no crash.
- **Save:** nothing new — `population` already round-trips; the beat + banner are transient/derived.
- **Reset:** `New Game` already wipes `population`; `Succession` is cleared by the `OnExit` resets;
  stingers cleared on menu/GameOver exit.

## Verification

Pure Bevy front-end — no `crates/core` tests. Add a `FOREST_SUCCESSION=1` staging hook that, on
the first playing frame, kills the hero so the beat can be filmed/screenshotted via the existing
capture harness. Verify: camera swings to a peasant, wisp + flash, hero rises there; and that
taking the last peasant fires the stinger + leaves the persistent banner up.
