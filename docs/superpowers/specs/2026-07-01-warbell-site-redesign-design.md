# Warbell site redesign — "War Table" visual layer

**Date:** 2026-07-01
**Scope:** Visual-layer redesign of the marketing site (`site/index.html` + `site/changelog.html`).
Same section structure & content flow; new visual language, mobile-first, content truthed-up
against the game at v0.15.0. Screenshots left as-is for now (regenerate later).

## Why

User feedback: the look feels tired, some copy no longer matches the game, and the site scales
badly on phones. Concrete audit findings below. The changelog *versions* are current (v0.15.0),
so "outdated" = look + copy accuracy + mobile, not stale patch notes.

## Direction — "War Table": parchment & forged steel

Keep the medieval-siege identity but refresh the visual language.

- **Palette:** shift the muddy brown-black base to a cooler charcoal so warm gold pops harder, and
  make the game's **day/night duality** drive section theming — forge-gold/warm for day, a real
  steel-blue/violet accent for night, ember-red for danger — instead of one gold on everything. A
  parchment tone (`--parch`) is available for sparing inverted accents.
- **Typography:** display stays **Cinzel** (brand), body switches from EB Garamond serif to a
  humanist sans (**Inter**) for cleaner mobile reading — a modern serif-display / sans-body editorial
  mix. Lore pull-quotes keep an italic serif voice.
- **Components:** hairline frames with corner ticks (war-map/staff-table aesthetic), lighter cards
  with real layered depth, refined chips/kbd, a proper before/after that works on touch.
- **Mobile-first (the real bug):** today under 760px the nav links just `display:none`, leaving only
  Download — no menu. Add a **hamburger drawer**, fluid clamp() type, safe paddings, a **sticky
  bottom Download bar** on phones, larger touch targets.
- **Shared `site/styles.css`:** both pages currently duplicate a large inline `<style>` (drift risk).
  Extract the design system into one stylesheet; pages keep only structural markup + tiny page-specific
  bits.

## Content audit (fixes to fold in)

Verified against `crates/core` + `src` at v0.15.0:

- **Stats strip** is stale: "58K lines of Rust" → **83K** (`wc -l` = 83,375); "13 wildlife species"
  → **15** (Bear, PolarBear, Wolf, Boar, Deer, Elk, Goat, Rabbit, Cat, Dog, Horse, Camel, Scorpion,
  BogCroc, Golem); "126 voice lines" → **200+** (206 catalog entries in `audio/lines.rs`, 305 audio
  clips total); "300+ meshes" kept (plausible, unverifiable cheaply).
- **Controls** section is wrong: it lists "Q Z X C — Eat food · quick-slot items". Real bindings:
  `Q` eat food · `Y`/`T` quick-slot consumables · `Z`/`X`/`C` **combat arts** (`player/arts.rs`).
  Missing keys to add: **`J` quest log** (`quest.rs`), **`B` build mode** (`town.rs`, day/in-town),
  **`N` skip to night** (prep). Confirmed correct: WASD move, LMB attack / RMB block, `E` interact
  (War Table / merchant / war bell), `F` forage / open chest / free the caged (`villagers.rs`),
  `R` recruit at the keep, `I`/`Tab` satchel, `` ` `` free-roam cam toggle, `H` how-to-play, `P`/`Esc`
  pause.
- **New features to surface** (shipped since the copy was written): a **guided quest chain** with
  step-by-step objectives (`quest.rs`), **roads & a natural path network** across the island,
  **ambient fish** (glide + leap in open water), and **Witcher-style soft-lock combat** (auto-picked
  target, ground ring, measured auto-face). The **rival stronghold** (a desert AI opponent that grows
  its own town, `rival.rs`) is worth a feature card.

## Non-goals

- No screenshot regeneration this pass (explicitly deferred).
- No new sections/structure — this is a re-skin + copy pass, not an information-architecture rewrite.
- No changes to the game or `crates/core`.

## Verification

Serve `site/` locally, screenshot desktop (1280) + mobile (375) for both pages; confirm the nav
drawer opens/closes, the before/after slider drags on touch, no horizontal overflow, and reduced-motion
still reveals all content.
