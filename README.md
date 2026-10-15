<img width="1909" height="1079" alt="image" src="https://github.com/user-attachments/assets/03ef2b22-6b3a-4d3d-b35b-f6daa42d2a62" />

<div align="center">

# ⚔️ Warbell

# MASSIVE OVERHALL INCOMING - REALISTIC GRAPHICS, 5h CAMPAIGN

<img width="1907" height="1079" alt="image" src="https://github.com/user-attachments/assets/17df143b-be76-4093-b4cb-6901301e014c" />
<img width="1919" height="1079" alt="image" src="https://github.com/user-attachments/assets/cfc452c3-93d0-4131-96d5-d359cdea436b" />
<img width="1919" height="1079" alt="image" src="https://github.com/user-attachments/assets/b3ddc31e-c084-4aab-9091-6553910d32aa" />
<img width="1919" height="1079" alt="image" src="https://github.com/user-attachments/assets/2afb2706-d07d-4e24-afa9-923a0676e142" />
<img width="1919" height="1079" alt="image" src="https://github.com/user-attachments/assets/59feb714-d62c-4171-a696-01174c0fa31e" />
<img width="1916" height="1079" alt="image" src="https://github.com/user-attachments/assets/d52c16ed-a18b-4de9-836c-40569e7be23a" />




**Defend the keep against nightly ork sieges.**

A knight holds a central castle through wave after wave of night assaults across a
five-biome island — real-time combat, an economy and upgrade tree, a town you build and
defend, inventory and consumables, villagers, wildlife, and a bloodline succession loop.
Built in Rust on [**Bevy 0.18**](https://bevyengine.org).

[**▶ Website**](https://miskibin.github.io/warbell/) · [**⬇ Download for Windows**](https://github.com/miskibin/warbell/releases/latest/download/Warbell-Setup.msi) · [**Changelog**](https://miskibin.github.io/warbell/changelog.html)

<a href="https://miskibin.itch.io/warbell"><img src="https://static.itch.io/images/badge-color.svg" alt="Available on itch.io" height="40"></a>

<img width="1897" height="1094" alt="Screenshot 2026-07-06 110013" src="https://github.com/user-attachments/assets/f122afa8-60e8-46bb-bc37-9c3fbb7a693e" />
</div>

## Play

- **Windows:** download [**`Warbell-Setup.msi`**](https://github.com/miskibin/warbell/releases/latest/download/Warbell-Setup.msi) and run it. The installer is self-signed, so Windows SmartScreen shows "Unknown Publisher" — click **More info → Run anyway**.
- **itch.io:** [**miskibin.itch.io/warbell**](https://miskibin.itch.io/warbell) — Windows & Linux builds, pushed automatically on every release (works with the [itch.io app](https://itch.io/app) for auto-updates).
- **From source** (any platform): see [Build from source](#build-from-source) below.


## Controls

- **WASD / arrows** move · **Space** jump · **Shift** sprint · **LMB** attack · **RMB** block
- **V** / the HUD **FP** button — toggle first-person view
- **E** contextual interact — walk up to the keep (upgrades), a merchant stall (shop), the
  war bell (ring in the night), or a chest (open it) and a prompt names it
- **B** build mode — at your town, press **B**, then point and click to raise houses, farms,
  woodcutters and mines
- **K** gather your militia / stand down · **J** current situation · **H** controls and help
- **Tab / I** satchel · **Q** eat food · **Y / T** quick-slots · **Z / X / C** combat arts
- **F** forage / rescue · **R** recruit · **` (backquote)** free-roam fly-cam · **P / Esc** pause
- **F1** debug tuning panel · **F2** perf/state overlay · **1–5** swap biome patch

## Your first three days

There is no countdown during the first three preparations: ring the war bell with **E** when
ready. The gold compass marker shows the current destination. You can try other approaches or
ring the bell before finishing the suggested preparation.

1. Gather the militia, free the nearby captives and bring the town back to work. A farm counts
   when a villager is actually producing food there.
2. Prepare for torch raiders targeting the farms. Buy a useful upgrade or intercept them yourself;
   clearing their marked staging camp prevents the torch bearers joining that night.
3. Decide how to face shamans: raid their marked camp to remove them from the incoming wave, or
   prepare ranged defenses and face them at home.

Later days bring back the preparation countdown and mix these threats. The day report states
what is coming and what a successful raid changes. Ruined producers stop working; **E** at their
remains rebuilds them. Existing saves keep their progress and resume without replaying the lessons.

## Build from source

```bash
cargo run        # build + open the game window
cargo test       # run the crates/core parity tests (the validation spec)
cargo check      # type-check without the (slow) link
```

On a fresh Linux box you need Bevy's system libraries once before the first build:

```bash
sudo apt-get update && sudo apt-get install -y \
  libwayland-dev libxkbcommon-dev libudev-dev libasound2-dev
```

(macOS / Windows need none of this.) The first build is slow — `bevy` compiles at
`opt-level = 3` even in dev so the scene isn't single-digit FPS — but incremental rebuilds of
`src/` are fast.

## Architecture

Two crates:

- **`crates/core` (`tileworld_core`)** — pure, deterministic, zero-dependency game logic
  (`f64` throughout). Pathfinding (A*), the wave director, upgrade / buff / resource /
  inventory stores, ork & animal config, factions, RNG, the shop catalog. This is the
  unit-tested validation spec — `cargo test` runs it. No Bevy, no I/O, no rendering.
- **`tileworld_bevy_forest` (root `src/`)** — the Bevy app: rendering, ECS systems, input, the
  scene. It imports `tileworld_core` for all the numbers/logic that must stay correct, wrapping
  core's stores as Resources (`PlayerRes`, `Bank`, `Inventory`, …).

Each `src/<feature>.rs` is a self-contained `Plugin`; **`main.rs` is the assembly list** — read
it as the table of contents. The whole world-sim is gated behind a freeze-gate state machine
(`game_state.rs`): opening any panel or leaving `Playing` freezes the sim but keeps rendering.

See **[`CLAUDE.md`](CLAUDE.md)** for the full conventions (coordinate frame, despawn-race rules,
mesh-building contract, combat-number parity) and **`docs/superpowers/specs/`** for the
per-subsystem roadmap and design docs.

## Screenshot harness

The Bevy window can't be captured externally, so visuals are verified via a render-and-exit
harness:

```bash
# PowerShell
$env:FOREST_SHOT="shot.png"; cargo run
# bash
FOREST_SHOT=shot.png cargo run
```

It renders ~90 frames so lighting/IBL settle, saves the PNG, and exits. Stage the shot with
env vars read at startup: `FOREST_CAM` / `FOREST_TIME` (camera pose / time-of-day),
`FOREST_BIOME` (boot into a biome), `FOREST_WAVE` / `FOREST_DEFEND=1` (stage a night siege),
`FOREST_MENU=1` (start screen), `FOREST_PANEL=tree|inv|build` (open a UI panel),
`FOREST_FP=1` (first-person), `FOREST_EQUIP="sword_gold,gold_armor"` (equip items on the hero).
`BEVY_ASSET_ROOT` points at this dir if you run the binary from elsewhere.

## License

Warbell's **source code** is **source-available** under the
[PolyForm Noncommercial License 1.0.0](LICENSE) — read, build, run, modify, and share it for
**non-commercial** purposes; commercial use is reserved. The **assets** under `assets/` carry
their own terms (e.g. [game-icons.net](https://game-icons.net) icons under CC BY 3.0, the
Cinzel / EB Garamond fonts under the SIL Open Font License; audio and other art may be
separately licensed). The hero's light sword combo is retargeted from
[Quaternius' Universal Animation Library 2](https://quaternius.itch.io/universal-animation-library-2)
(CC0). See [`LICENSE`](LICENSE) for the full text and the asset note.


