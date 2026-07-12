# RTS Skirmish Mode ("Potyczka") — Design

Date: 2026-07-12 · Status: approved POC scope · Owner: skibin

A Stronghold-Crusader-style skirmish mode inside Warbell: top-down isometric view, no hero,
one small symmetric arena, player vs one mirrored AI rival. Base building, four resources,
worker hauling, barracks training, destroy the enemy town hall to win. Maximum reuse of the
existing campaign substrate (terrain gen, navgrid, combat channels, worker haul loops,
rival.rs AI shape, UI kit).

User decisions locked during brainstorming:

- Rival faction = the **desert faction** models from `rival.rs`/`villagers.rs` (keffiyeh/cloak
  workers, rival soldier/bow). Mirrored costs and rules.
- Entry = **"Potyczka" button** on the start screen.
- Construction = **Stronghold style**: pay cost, building grows by itself over N seconds
  (scaffold), no builder unit.
- Terrain = **natural terrain, symmetric key positions** (flat base plateaus, mirrored
  deposits, a road through the middle) — not a geometric mirror.

## 1. Mode entry & state machine

- `GameMode { Campaign, Skirmish }` — a resource decided once at boot from env
  `FOREST_RTS=1`. Never changes mid-process.
- Start screen gains a **"Potyczka"** button. Clicking it relaunches the exe with
  `FOREST_RTS=1` (exact same relaunch pattern New Game uses — fresh world = fresh process;
  the 29 scattered Startup systems make in-process regen a non-starter).
- `AppState` / `Modal` / the `SimAppExt::add_sim_systems` freeze gate are reused **unchanged**.
  Esc pause works for free. RTS build placement is **not** a `Modal` (Stronghold doesn't
  pause while placing) — it's a plain input-state resource.
- Campaign-only plugins/systems get `run_if(in_mode(GameMode::Campaign))` (helper
  `game_state::campaign_only()` / `skirmish_only()` run conditions). Disabled in Skirmish:
  hero/player plugin (no hero entity at all), siege/night waves, quests, savegame, wildlife,
  camps, warlord, ork_fortress, old `rival.rs` stronghold, meadow, fish, boss/wardens,
  landmarks, tutorial, shop/upgrade-tree/inventory modals, hero voice lines.
  Still running in both: terrain/worldmap, navgrid/blockers, `Health`/`Dying`/damage
  channels, projectiles, dust/FX, audio (music+ambient+combat SFX), UI kit, quality/post.
- New code namespaced under `src/rts/` — one `RtsPlugin` (assembled from submodule plugins)
  added unconditionally in `main.rs`; every RTS system carries
  `.run_if(in_mode(GameMode::Skirmish))` **and** the sim gate where it simulates.

## 2. Arena map

- New `MapId::Arena` + `MapDef` (third map; Home/Ashlands prove maps are a data swap).
- Grid stays at `MAP_SCALE 2.6` / existing `COLS×ROWS` — **no navgrid or scale refactor**.
  The arena is a small ellipse ≈ 90×90 tiles centred on the origin; ocean beyond.
- Deterministic layout (mulberry32, fixed seed):
  - Two force-flattened **base plateaus** on the SW/NE diagonal (player SW, rival NE),
    ≈ 26 tiles across, mirrored through the origin.
  - A dirt **road** connecting the bases through the map centre (reuse road-rut ground
    styling from worldmap).
  - **Finite mirrored deposits** per side: a tree grove (wood), a stone outcrop, a gold
    vein near each base — plus one richer contested set at the centre.
  - Gentle rolling terrain elsewhere; grass/forest palette; clear daylight, fog pushed far,
    no day/night cycle (fixed pleasant afternoon time).
- Nothing else spawns: no rivers, castle, camps, wildlife, chests, landmarks, old rival fort.
- Start state per side: Town Hall pre-built on the plateau, 3 workers idle beside it,
  bank = 50 wood / 30 stone / 20 gold / 30 food, population cap 6 (hall).

## 3. Camera — single `Camera3d`, hard rule

- **Never a second `Camera3d`** (CLAUDE.md; fails three documented ways). The RTS camera is
  a new pose branch driving the ONE existing camera entity (same pattern as build-cam /
  fly-cam poses).
- On Skirmish boot: swap `Projection` to `Orthographic`, fixed iso yaw 45°, pitch ≈ 50°,
  looking at a ground **focus point**.
- Controls: WASD pan + edge-pan (cursor within ~24 px of a screen edge), wheel zoom =
  clamped ortho scale. No camera rotation in POC (R is building rotation).
- Post-stack risk: DoF/godrays are perspective-tuned. In Skirmish they are configured OFF
  **at startup** (never toggled at runtime — the documented `apply_quality` re-insert wgpu
  crash). Bloom/AO/atmosphere stay. Fallback if ortho corrupts the post stack in practice:
  steep telephoto perspective (FOV ≈ 25°) as "fake iso".
- No fog of war (out of scope).

## 4. Selection & commands (net-new input layer)

- Cursor→world: `viewport_to_world` ray, intersected with terrain via iterative
  `ground_at_world` refinement (nothing like this exists yet — the only prior art is
  build-mode's forward projection).
- **LMB click** = select nearest own unit within a screen-space pick radius; **LMB drag** =
  box select own units inside the screen rect; **Shift** adds to selection. Buildings are
  single-selectable (info/training panel). Enemy units: click shows info only, never
  commandable.
- **RMB** context command: ground → move; enemy unit/building → attack; deposit (with
  workers selected) → reassign harvest.
- **Attack-move**: press A then LMB/RMB on ground — units path there engaging anything
  hostile en route.
- Selection visuals: `outline.rs` highlight + a ground ring under selected units; HUD
  selection panel (§10).
- Movement: commands write goals into the existing `NavPath`/`path_to` machinery; group
  moves fan goal offsets in a small phyllotaxis blob (reuse rally-blob offsets) with
  staggered replans (existing pattern) so 30-unit orders don't hitch.

## 5. Factions & economy

- `Side { Player, Rival }` component on every RTS unit/building/deposit-claim.
- `RtsBanks` resource: per-side `{ wood, stone, gold, food }` (`f64`, all-or-nothing spend,
  mirroring core `ResourceState` semantics; gold included since core's store lacks it).
  Both sides play by identical costs/rules — the AI spends from its own bank only.
- **Deposits** are entities: `Deposit { kind: Wood|Stone|Gold, remaining }`.
  - Wood = a grove of real tree entities; felling reuses the `lumberjack.rs` chop loop;
    no regrow in Skirmish → finite.
  - Stone/gold = ore-style rocks (reuse ore meshes; gold gets a warm recolor); deplete by
    hauled loads, shatter at zero, no regrow.
- **Worker haul loop** (fork of `lumberjack`/`miner` shape, generic): production building
  completes → auto-claims the nearest idle worker of its side → worker walks to the nearest
  matching deposit → gather timer → physically carries the load **to its own Town Hall** →
  banks it → repeats. Farm: worker tends the field, periodically carries a food sack to the
  hall. Deposit exhausted or building destroyed → worker returns to idle pool.
- **Population**: Town Hall +6 cap, each House +4 cap. Food surplus tick (shape of core
  `population_tick`): every ~20 s, if food > threshold and pop < cap, a new worker walks
  out of the hall. Small per-capita food drain per second so food stays meaningful.
- Workers **flee** nearby enemies (reuse flee/blacklist machinery) and return to work when
  clear.

## 6. Buildings

| Building | Footprint | Cost | Build time | Function |
|---|---|---|---|---|
| Town Hall | 4×4 | — (pre-built) | — | drop-off, worker spawn, win objective, HP 1200 |
| House | 2×2 | 20 w | 8 s | +4 pop cap |
| Sawmill (tartak) | 3×3 | 25 w | 10 s | claims worker → wood hauling |
| Quarry (kamieniołom) | 3×3 | 30 w | 12 s | claims worker → stone hauling |
| Gold Mine (kopalnia) | 3×3 | 30 w 10 s(tone) | 14 s | claims worker → gold hauling |
| Farm | 3×3 | 15 w | 8 s | claims worker → food cycle |
| Barracks (koszary) | 4×4 | 40 w 20 s(tone) | 20 s | trains units (§7) |

- Meshes: reuse `town_meshes` (lumber→sawmill, mine→quarry/gold-mine recolor, farm, house);
  Town Hall = compact keep-like assembly; Barracks = simple new merge from existing parts.
  All follow the mesh contract (base at y=0, vertex COLOR, one white material, flat normals).
- **Free-grid placement**: ghost mesh follows the cursor snapped to 1 tile, **R rotates
  90°**, translucent green/red by validity. Valid = terrain flat enough (height spread
  under the footprint below threshold) + land + `blockers::is_blocked` footprint sweep
  clear + not on a deposit. Pay on place.
- **Timed construction**: scaffold state (frame mesh + building scaling up from the
  ground) → timer → complete → registers its blocker box → auto-claims a worker if a
  producer. Buildings have `Health`, are attackable, burn/die via the shared channels.
  No repair in POC.

## 7. Units & training

| Unit | Model (player / rival) | HP | Dmg | Notes |
|---|---|---|---|---|
| Worker | peasant / desert worker | 40 | — | hauls, flees combat |
| Swordsman | guard / rival soldier | 90 | 12 melee | chase→strike→cooldown brain |
| Archer | bowman / rival bow | 60 | 9 ranged | `bow_cycle` draw-loose volleys, `BOW_RANGE` |

- **Training** (spec rule: converts a **free worker**): Barracks panel button → costs
  (Swordsman 15 gold 10 wood, Archer 15 gold 10 wood) + one idle worker; the worker walks
  into the barracks, 8 s timer, emerges as the unit. Population count unchanged
  (worker→soldier). Queue depth 3.
- Cap ≈ **30 units per side** total (enforced by housing).
- Combat reuses: `Health`/`Dying`/`try_despawn`, `NpcDamage` channels, melee brain, archer
  volley cycle, `projectile::ArrowSpawn`, `blockers::wall_between` LOS. Targeting is by
  `Side` (hostile = the other side) in new RTS brains — campaign brains stay untouched.
- Attack-move engages hostiles in sight along the way, then resumes the path.

## 8. Rival AI (mirrored)

- Same banks, costs, build times, training rules, unit caps. No cheating.
- Think tick every ~5 s (fork of `rival_economy`'s paced-decision shape):
  1. **Build**: follow a build order (Farm, Sawmill, House, Quarry, House, Gold Mine,
     Barracks, House, …) when affordable; place at pre-authored mirrored offsets from its
     hall (validity-checked, skip-and-retry if blocked).
  2. **Assign**: worker claiming is the same automatic system as the player's.
  3. **Train**: once Barracks stands, alternate swordsman/archer while affordable and a
     free worker exists, keeping ≥ 4 workers hauling.
  4. **Attack waves**: when army ≥ 6, attack-move the whole army at the player's Town
     Hall; each next wave threshold +2 (8, 10, … cap 14). Fights to the death.
- LOD: none needed (small map, camera always near); the `rival.rs` LOD freeze is not
  carried over.

## 9. Win / lose

- Both Town Halls have `Health` 1200. Hall reaches `Dying` → `RtsOutcome { PlayerWon |
  RivalWon }` resource set → `watch_end` (parameterized to watch either `Siege.phase` in
  Campaign or `RtsOutcome` in Skirmish) flips to `AppState::GameOver`.
- GameOver screen reused with RTS strings: "ZWYCIĘSTWO — wrogi ratusz zburzony" /
  "PORAŻKA — twój ratusz padł". Buttons: back to menu / play again (relaunch with flag).

## 10. HUD

- **Top bar**: four resource counters (wood/stone/gold/food icons from the icon atlas) +
  population `cur/cap`. Reuse hud row styling.
- **Bottom-right build strip**: 7 building buttons with cost tooltips, greyed when
  unaffordable (template: `spawn_build_strip`).
- **Bottom-left selection panel**: selected unit icons + counts; single selected barracks
  shows train buttons + progress bar; single building shows HP.
- Toasts reused for "za mało surowców", "limit populacji", "złoże wyczerpane".
- No minimap in POC (only the compass exists in campaign; a minimap needs its own
  procedural widget — deferred).

## 11. Out of scope (POC)

Save/load, multiplayer, fog of war, walls/gates/towers, weapon-item production, extended
menus, minimap, formations/patrol/stances, rally points, repair, camera rotation, more than
one AI opponent, difficulty settings.

## 12. File layout & integration points

```
src/rts/mod.rs        RtsPlugin assembly + Side/GameMode helpers + RtsBanks + RtsOutcome
src/rts/camera.rs     iso ortho pose, edge-pan/WASD/zoom
src/rts/pick.rs       cursor→world ray, unit/building picking
src/rts/select.rs     click/box/shift selection + rings/outline
src/rts/command.rs    RMB move/attack, attack-move, group goal fan-out
src/rts/build.rs      ghost placement, validation, scaffold growth, blocker registration
src/rts/deposits.rs   deposit entities, depletion, arena deposit spawn
src/rts/workers.rs    claim/haul/flee loops (generic fork of lumberjack/miner)
src/rts/units.rs      training pipeline, RTS combat brains (Side targeting)
src/rts/ai.rs         rival think tick (build/train/wave)
src/rts/hud.rs        top bar, build strip, selection panel
```

Touched existing files: `main.rs` (add plugin, gate campaign plugins), `game_state.rs`
(`GameMode`, run-condition helpers, Potyczka button, parameterized `watch_end`, GameOver
strings), `worldmap.rs` (`MapId::Arena` + arena build branch), `villagers.rs`/`rival.rs`
(expose model spawn helpers as `pub` where needed — no behavior changes).

## 13. Conventions that apply (from CLAUDE.md)

`try_despawn`/`try_insert` everywhere combat can race; `Without<Dying>` on every targeting
query; sim systems carry the `Modal::None` gate; mesh contract (y=0 base, vertex color,
flat normals, duplicate-first); mulberry32 determinism; world coords through the arena's
own constants (not `world22`); new run-state needs no save round-trip (no save in
Skirmish) but **must** reset — trivially satisfied by the relaunch-per-run entry.

## 14. Verification

- `FOREST_RTS=1` boots straight into the arena (dev shortcut past the menu, like other
  harness flags), so `FOREST_SHOT`/`FOREST_CLIP` captures work unchanged.
- Milestones verified by screenshot: arena layout (low oblique shots at both bases +
  centre), camera framing, ghost placement, a worker haul round-trip clip, a training +
  attack-wave siege clip, GameOver screens.
- `cargo test` must stay green (core untouched); `cargo check` after each integration wave.
