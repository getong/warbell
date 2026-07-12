---
name: game-rc
description: Drive and inspect a LIVE running Warbell game session via the FOREST_RC JSON bridge — send semantic commands (build, train, order units, speed up time, screenshot) and read full game-state snapshots (fps, banks, every unit/building position, siege phase) as JSON files. Use when playtesting the game agent-side, reproducing a gameplay bug interactively, verifying a change needs a LIVE evolving session (not a one-shot FOREST_SHOT), or when the user asks to "play the game", "test the game live", or "check the game state".
---

# Game remote-control bridge (FOREST_RC)

`FOREST_SHOT` gives one frozen frame; the ecotest gives one pass/fail. The **RC bridge** gives a
conversation with a LIVE game: you drop JSON commands into a file, the game executes them through
the same entry points the real UI uses, and twice a second it publishes its full state as JSON.
That's enough to actually *play* a skirmish match end-to-end, agent-side.

Lives in `src/rc.rs` (plugin registered in `main.rs`, inert without the env var).

## Boot

```powershell
# RTS skirmish under the bridge (the main use):
$env:FOREST_RTS="1"; $env:FOREST_RC="target/rc"; cargo run
# Campaign works too (state snapshot only has fewer ops that apply):
$env:FOREST_RC="target/rc"; cargo run
```

Run it as a **background task** and interact from the same session. The dir gets three files:

| File | Direction | What |
|---|---|---|
| `cmd.json` | you → game | one op object, an array of ops, or `{"seq":N,"ops":[...]}`. Game executes + **deletes** it. |
| `state.json` | game → you | full snapshot, rewritten every ~0.5s (atomic — always safe to Read). |
| `log.jsonl` | game → you | one compact line per ~2s (fps + economy/army/phase) — the run's timeline for post-mortems. |

Protocol: Write `cmd.json`, wait ≥1s, Read `state.json` — your batch is done when `seq_done`
bumped and `results` echoes per-op `{"ok":..}`. A half-written `cmd.json` gets a ~2s grace, then
is rejected with a parse error in `results`. Stale files are swept at boot.

## State snapshot (what you get)

Always: `fps` (real-clock EMA), `sim_time`/`real_time`, `speed`, `app_state` (StartScreen/Playing/…),
`modal`, `mode`, `sky` (`t` 0..1 day fraction, `day_secs`). Campaign adds `campaign.phase`
(Prep/Wave/…), `wave_index`, `hero {x,z,alive}`, `player {hp,gold,level}`. Skirmish adds `rts`:

- `outcome` — `Undecided` / `PlayerWon` / `RivalWon` (the match verdict)
- `banks.player|rival` — wood/stone/gold/food
- `pop.player|rival` — `{count, cap}`
- `units[]` — `{id, side: "P"|"R", kind, x, z, hp, working, selected}`
- `buildings[]` — `{id, side, kind, x, z, hp, built}` (`built:false` = scaffold under construction)
- `deposits[]` — `{id, kind: Wood|Stone|Gold, x, z, remaining}`

The `id` strings are live entity bits — pass them back in `order` ops. They die with the entity;
re-read state rather than caching them long.

## Ops

```jsonc
{"op":"speed","mult":3.0}            // virtual-clock multiplier 0.05..10 — fast-forward a match
{"op":"shot","path":"target/rc.png"} // async screenshot (lands a few frames later)
{"op":"quit"}                        // clean AppExit
{"op":"give","wood":100,"gold":50,"side":"player"}   // bank cheat (skirmish banks; side default player)

// Skirmish-only:
{"op":"build","kind":"Barracks","x":-20,"z":30}      // kinds: House|Sawmill|Quarry|GoldMine|Farm|Barracks
                                                     // "auto":true (default) ring-searches a valid spot
                                                     // near (x,z) if the exact tile is invalid
{"op":"train","unit":"Swordsman","count":2}          // first built player barracks; converts idle workers!
{"op":"order","select":"soldiers","type":"attack_move","x":40,"z":-35}
{"op":"order","select":["<id>","<id>"],"type":"attack","target":"<building-or-unit id>"}
// select: "all" | "soldiers" | "workers" | [ids]; types: move | attack_move | attack | harvest
```

Results echo in `state.results` — ALWAYS check `ok` before assuming the op landed
(e.g. `train` fails politely when no barracks is built yet; `build` when funds are short).

## Playing a skirmish (the recipe that works)

1. Boot, poll until `app_state=="Playing"` and `rts.buildings` shows both TownHalls.
2. Economy: `build` Sawmill **next to a wood grove** (pick grove coords from `deposits`), Farm +
   House near base. Workers auto-bond to producers and haul (verify `banks` growing in `log.jsonl`).
3. `{"op":"speed","mult":3}` — the AI takes ~10 real min otherwise. Watch `rival` army in the log.
4. Barracks (needs wood 40 + stone 20 → Quarry first, or `give`), then `train` — **each trainee
   consumes an idle worker**, so keep food positive and pop under cap (Houses raise cap).
5. Attack: rival TownHall's `{x,z}` from `buildings` (side `"R"`), then
   `{"op":"order","select":"soldiers","type":"attack_move","x":…,"z":…}`.
6. Poll `outcome` — `PlayerWon` on razing the rival hall; the GameOver screen appears (state keeps
   publishing). `shot` along the way for visual checkpoints.

## Gotchas

- **One instance at a time** — two games would fight over the same `cmd.json`/`state.json`.
- `speed` >3 subtly starves movement vs timers (the mover clamps per-frame dt at 0.05); economy
  timing stays proportional, just don't measure fine game-feel above ~3×.
- `shot` is async — wait ~1s before Reading the PNG, and confirm the run logged `Screenshot saved`.
- The bridge polls `cmd.json` **every frame**; don't stream ops — batch them in one file drop.
- Entity `id`s go stale on death (orders with stale ids are silently skipped per-entity).
- Campaign ops beyond speed/shot/quit/state don't exist yet — extend `run_op` in `src/rc.rs`
  (semantic ops only: route through real game entry points, never synthesize input events).
- Pair with `FOREST_RTS_ECOTEST` for unattended pass/fail; the RC bridge is for *interactive* runs.
