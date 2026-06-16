# Build placement legibility — design

**Date:** 2026-06-16
**Status:** Approved design, ready for implementation plan
**Supersedes the build-entry UX of:** `2026-06-09-city-building-economy-design.md` (the economy/numbers there stand; only *how the player places a building* changes)

## Problem

Playtesting shows players don't understand **where** they can build. They see a build
affordance ("build a building") but can't tell which spots in the world are buildable, so they
don't know where a house vs. a farm can go. Two concrete breakdowns:

1. **Plots don't read as buildable.** The 8 timber-frame placeholder pads around the castle
   don't communicate "you can build here" — they look like generic scenery.
2. **House vs. producer split.** Producers (Farm / Lumber / Mine) are placed by standing on an
   outer plot and pressing **E**; houses rise on a *separate* courtyard pad via a *different* E
   prompt. Two flows, two locations, one mental model expected.

There is no on-screen entry point that teaches the mechanic, so a new player never discovers the
"walk to a plot, press E" flow at all.

## Goal

Make build placement **legible** and **unified**, cheaply, while laying a foundation the planned
RTS/city-builder expansion can build on.

- The player can see, at a glance, **where** they can build and **what** goes there.
- One entry point, one menu, house folded in with producers.
- The player still **chooses the location** (which of the marked plots) — placement is player
  agency, not auto-placement.
- Keep the work small (no new camera system) but **forward-compatible** with a later top-down
  RTS mode and more building types.

## Non-goals (explicitly deferred)

- **Top-down/overhead build camera.** Considered and deferred: it solves the same problem but is
  a much larger build (new camera mode, transitions, click-picking) and tonally pulls the player
  out of the embodied action game for a placement layer that today has only ~8 plots. Revisit it
  as its own project *when* the town layer grows (more plots, free placement, deeper RTS). See
  **Path to the RTS expansion** below — this design is shaped so that move is cheap later.
- **NPC builders.** Villagers physically constructing placed buildings is a later flavor layer,
  not part of this change. Placement is confirmed instantly so there's never a "placed but not
  built" ambiguity; an NPC layer would only add visual life on top.
- **True free placement** (build anywhere on valid ground). The world is generated with the 8
  plots pre-flattened; arbitrary placement needs runtime ground-flattening + slope/water/overlap
  validation + dynamic collision. Out of scope; the player picks among marked plots.

## Decisions (from the brainstorm)

- Player picks among **marked plots** (not auto-placed, not free placement).
- **Always-on HUD button** is the discoverable entry point.
- Placement keeps the world **live** (the player walks the knight to the chosen plot) — so it is
  **not** a freeze-gated `Modal`; it is a lightweight state read under `Modal::None`.
- Placing a building is **instant on confirm**, with a **construction animation** (scaffolding →
  full over ~1–2s) extending the existing `build_fx` pop. No NPC required.
- House is **folded into the same menu/flow**.

## Design

### A. HUD "Build" button (`hud.rs`)

A persistent pill, top-left, just under the stat bar (resources sit directly above what spends
them). Label `🔨 Build`. Clicking it toggles **build mode** on. It is the one discoverable entry
point — a new player sees it immediately, and pressing it *teaches* the mechanic by lighting up
the world (below).

### B. Build mode — a live placement state (`town.rs` + `interaction.rs`)

Build mode is a small resource, e.g. `BuildMode { active: bool, kind: Option<BuildType> }`, with
its systems gated on `in_state(Modal::None)` so a pause/panel still suspends it but normal play
does **not** freeze (the player must walk).

While `active`:

- **Every buildable spot lights up at once.** Free producer plots (`is_buildable()`) show the
  existing gold ring + a translucent ghost of the currently selected building. When **House** is
  the selected type, the next courtyard slot (`castle::next_house_site`) lights instead of the
  outer ring. This is the core fix: "where can I build?" is answered *visibly* the moment the
  button is pressed.
- **A docked type strip** (reuse the existing slim bottom-centre menu from `spawn_build`):
  **House · Farm · Lumber · Mine**, each with icon + one-line description + wood/stone cost,
  greyed when unaffordable. Selecting a type sets `BuildMode.kind` and the ghosts swap to it.
- **A banner/hint line:** *"Walk to a glowing plot · E to build the Farm · Esc to cancel."*

### C. Pick *what*, then walk to *where*

- Select a type from the strip → that type's valid spots glow with its ghost.
- **Walk the knight onto a lit plot** → that plot becomes the "selected" one (its ghost/ring
  brightens). Press **E** → build there: `town.build(idx, kind)` for producers,
  `town.build_house()` for House. Resources are spent, the construction animation plays.
- Build mode **stays active** so the player can place several in a row; **Esc** (or pressing the
  HUD button again) exits and the spots stop glowing.
- **Shortcut preserved:** if the player is already standing on a plot when they enter build mode,
  that plot is pre-selected, so E builds immediately with no walking.

### D. Plots legible (at rest vs. in build mode)

- **At rest:** the pads stay subtly visible (as today) so the player senses the town has room,
  but they are understated — not glowing, not labeled.
- **In build mode:** they glow + show ghosts + the banner names the action. The HUD button is
  what reveals them; the mechanic is taught by doing.

### E. Construction animation (`build_fx.rs`)

Extend the existing `BuildPop` (which already pops the building out of the plot on a kick of
dust) into a short **scaffolding → full** reveal (~1–2s): the building is logically placed and
resources are spent on confirm (no ambiguity), but it visually rises rather than snapping in.

### F. Remove the old split prompts

- The standalone **"Raise house"** on-site E prompt and the producer-only on-plot **"Build"** E
  prompt are folded into build mode (the unified menu). This removes the "two flows" confusion.
  (`interaction.rs` loses the `Build` and `RaiseHouse` `InteractKind`s; the keep/shop/bell/chest
  resolver is otherwise unchanged.)

## What's reused vs. changed

**Reused unchanged:** `BuildKind`, build costs, `town.build` / `town.build_house`, `town_store`
numbers, the predefined plot offsets + `PlotSpots`, the ghost-preview meshes, `build_fx`.

**Changed:** `hud.rs` gains the Build button; `town.rs`'s `Modal::Build` menu becomes the live
build-mode overlay + the data-driven type strip; `interaction.rs` drops the Build / RaiseHouse
interact kinds; `build_fx.rs` gains the scaffolding reveal.

## Forward-compatibility — the path to the RTS expansion

The user intends to add more buildings and deepen the RTS/city-builder layer later. This design
is deliberately a **foundation**, not a throwaway. Two constraints keep it so:

1. **Building types are data-driven.** Today `MENU` is a hardcoded `[Farm, Lumber, Mine]`.
   Replace it with a single table — one entry per build type: `{ kind, label, description, icon,
   cost, spot_class }` where `spot_class` is `Outer` (producer plots) or `Courtyard` (house
   slots). Adding a new building later = add a row. House becomes just another entry whose
   `spot_class` is `Courtyard`.

2. **Placement is decoupled from town logic.** The placement/interaction layer (lighting spots,
   walking, E-to-confirm) only calls the unchanged `town.build` / `build_house`. Swapping the
   on-foot placement for a future **top-down camera + click-to-place** touches *only* the
   placement layer — the economy, costs, plots, and `build_fx` carry over untouched.

So when the RTS expansion happens, the new top-down view reuses the data model, costs, plot
system, construction animation, and town store; only the camera and click-picking are new work.
More plots are already supported by adding offsets; the `spot_class` concept generalizes to new
spot kinds.

## Open implementation questions (for the plan)

- **State plumbing:** `BuildMode` as a plain `Resource` read under `Modal::None`, vs. retiring
  the freeze-gated `Modal::Build` variant entirely. (The menu can no longer freeze the world,
  since the player walks during placement.)
- **Selected-plot detection:** reuse the existing `BuildTarget` (nearest buildable plot the hero
  stands on) to pick the plot E confirms.
- **House out-of-order slots:** House lights only its single next sequential slot
  (`next_house_site`), so no per-slot core change is needed; keep houses sequential for now.
- **Wave behavior:** whether build mode is allowed during a night `Wave` or prep-only. (Producers
  already only auto-staff in prep; building during a wave is probably harmless but low value.)

## Testing

- Core (`crates/core`) is unchanged — existing `town_store` tests still gate the numbers.
- Manual: press Build → all free plots glow with the selected type's ghost; switch type → ghosts
  swap; walk onto a plot → E → building rises with scaffolding, wood/stone drop; House → next
  courtyard slot glows → E raises a house there; Esc exits and plots stop glowing.
- Screenshot harness: extend `FOREST_PANEL=build` to stage build mode (glowing plots + strip) for
  a capture.
