# UI Port from three.js — Design Spec

**Date:** 2026-06-08
**Goal:** Port the original three.js game's HUD/menus/panels into the Bevy game as close to
pixel-faithful as `bevy_ui` allows. The 3js UI is a polished, coherent design system; the current
Bevy UI is ad-hoc rectangles in the default font. This spec recovers the 3js look.

Reference source (canonical): `D:\tileworld\src\hud\` — `hud.css` (2187 lines, the full stylesheet)
plus the per-panel `.tsx` files. Emoji icon ids live in `D:\tileworld\src\world\inventoryStore.ts`,
`shopCatalog.ts`, `upgradeStore.ts`.

---

## Decisions (locked)

- **Render tech:** `bevy_ui` native (not egui). Bevy 0.18 has `BorderRadius`, `BoxShadow`, UI
  gradients, and font loading — enough to match the CSS closely. egui stays the F1 debug panel only.
- **Icons:** Download **Twemoji** PNGs (CC-BY 4.0, attribution required) for the exact codepoints
  used; load into the existing `IconAtlas` as `ImageNode` textures. Procedural shapes stay only as a
  missing-file fallback.
- **Motion:** Full — port the entrance keyframes (pop-in / slide-down / rise / float-up / toast-in /
  sheen) + hover transitions via small Bevy tween systems.
- **Scope:** All ~13 live-data elements **plus** a generic **Notice** queue and a **Settings panel +
  audio toggle** (with minimal backing systems). **Deferred:** LoadingScreen, Minimap.
- **Rollout:** Foundation (`src/ui/`) lands and is screenshot-verified first; then every element is
  re-skinned on it.

---

## Design system (the recurring recipe)

**Palette** (CSS → linear `Color::srgba`):

| Token | Hex / rgba | Use |
|---|---|---|
| `GOLD` | `#ffd58c` | currency, titles, accents |
| `STONE` | `#cdd3da` | stone count |
| `GREEN` | `#9be88a` | buffs, success, toast accent |
| `GREY` | `#8a8e98` | labels, disabled, hints |
| `RED` | `#d63a3a` | HP, damage, danger |
| `TEXT` | `#f3f3f5` | body text |
| `PANEL` | `rgba(22,28,40,0.95)` | modal card bg |
| `PANEL_HUD` | `rgba(20,26,38,0.78)` | HUD chrome bg |
| `SCRIM` | `rgba(8,8,14,0.55)` | modal backdrop (see blur caveat) |
| `PARCHMENT` | `#e7d8b0` | upgrade-tree board |
| `INK` | `#2c2110` | upgrade-tree text |

**Fonts:** Inter (weights 400/600/700/800) for everything; one serif (**EB Garamond**, OFL — a
free Palatino-ish substitute) for the upgrade-tree board only.

**Common chrome:**
- Panel: bg `PANEL`, `border: 1px rgba(255,255,255,0.1)`, `border-radius: 10px`,
  `box-shadow: 0 16px 40px rgba(0,0,0,0.55)`.
- HUD chrome: bg `PANEL_HUD`, `border: 1px rgba(255,255,255,0.08)`, `radius: 8px`,
  `shadow: 0 8px 30px rgba(0,0,0,0.35)`.
- Button: bg `rgba(255,255,255,0.04)`, `border 1px rgba(255,255,255,0.08)`, `radius 6px`; hover →
  bg `rgba(255,255,255,0.09)`, border `rgba(255,255,255,0.18)`.
- Cells: quick-slot **52px**, inventory cell **46px**, mini cell **40px**, `radius 3–4px`.
- Icons: `drop-shadow(0 1px 2px rgba(0,0,0,0.6))`; empty = `opacity 0.28; grayscale(1)`.

**Animation keyframes** (port targets):

| Name | Dur / easing | Transform |
|---|---|---|
| `fade-in` | 200–320ms ease-out | opacity 0→1 |
| `pop-in` | 260–600ms cubic(.22,1,.36,1) | scale .82→1.04→1 |
| `rise` | 600–700ms ease-out, staggered | translateY 10px→0 + fade |
| `toast-in` | 180ms ease | translateX −20px→0 |
| `float-up` | 500ms ease-out | translateY 8px→0 |
| `slide-down` | 360ms cubic | translateY −14px→0 |
| `sheen` | 3.6s ease-in-out ∞ | skewed highlight sweep |

---

## Section 1 — Foundation: `src/ui/` module

New module dir; added as one `UiKitPlugin` early in `main.rs` (before HUD/panel plugins, so fonts
and icons exist at their `Startup`). Files:

### `src/ui/theme.rs`
All palette tokens as `pub const Color`, spacing/radii consts, and `BoxShadow`/`BorderRadius`
preset constructors. Pure data, no systems.

### `src/ui/fonts.rs`
- `UiFonts { inter_400, inter_600, inter_700, inter_800, serif }` resource, populated at `Startup`
  from `assets/fonts/*.ttf`.
- Bundle **Inter** static TTFs (OFL 1.1) for the four weights and **EB Garamond** (OFL) serif.
- Helper `fn text(&self, weight: Weight, size: f32, color: Color) -> (TextFont, TextColor)` so call
  sites read like the CSS.
- Add `assets/fonts/OFL.txt` license text.

### `src/ui/icons.rs` (reworks current `src/icons.rs`)
- Twemoji 72px PNGs → `assets/icons/twemoji/<codepoint>.png`. Downloaded from the maintained
  `jdecked/twemoji` set. Filenames are lowercase hex joined by `-`, VS16 (`fe0f`) handled per the
  repo convention (resolved at download time).
- `fn icon_codepoint(id: &str) -> Option<&'static str>` table mapping **item ids, upgrade-node ids,
  shop ids, buff kinds, branch sigils, and status symbols** to codepoints (full set below).
- `IconAtlas` loads the PNG per id; if absent, falls back to the existing procedural rasteriser.
- Add `assets/icons/twemoji/LICENSE` (CC-BY 4.0 attribution to Twitter/jdecked).

### `src/ui/widgets.rs`
Builder fns returning Bundles (or small spawn closures) for: `scrim()`, `panel_card()`,
`pill_btn(label)`, `cell(px)`, `keycap(s)`, `bar(track_h, fill_color)`, `segmented(options)`,
`icon_node(handle, px)`. Each composes theme tokens + radius + shadow + gradients.

### `src/ui/anim.rs`
- `UiAnim { kind: AnimKind, delay, dur, easing, t0 }` component + a `drive_ui_anim` system that
  lerps a node's transform (scale/offset) and component alpha over its lifetime, then removes itself.
- `Hoverable { rest, hover }` style pairs + a `drive_hover` system reading `Interaction` to lerp
  bg/border/offset.
- **API risk:** exact form of post-layout transform on UI nodes in Bevy 0.18 (`UiTransform` vs
  `Transform` vs `Node` offset) must be verified against
  `docs/specs/bevy-0-18-1-polished-static-3d-scene-verified-apis.md` and the real bevy_ui source
  before relying on it. Gradients are already proven in-repo (`grade.rs` radial vignette).

### `src/ui/mod.rs`
`UiKitPlugin` (loads fonts + icons at `Startup`, registers anim/hover systems, ungated so it runs in
every state). Re-exports `theme`, `widgets`, `fonts`, `anim`.

---

## Section 2 — Element-by-element port

Each row: target style summary + the file/fn that gets rewritten to use the kit. Exact numbers per
element are in the design-system table above and the reference `hud.css`.

| Element | File:fn (rewrite) | Target |
|---|---|---|
| **StartScreen** | `game_state.rs:spawn_start_screen` | Cinematic lower-left: kicker + 2-line title (near-white + blue glow — see note), tagline, divider, **Play** button (gradient + sheen), difficulty **segmented control** (click or `G`), bottom-right controls legend with keycaps, staggered `rise`, full-screen vignette. |
| **PlayerHud** | `hud.rs:setup_hud`/`update_hud` | Level badge (gold border) + HP (red gradient) / XP (blue) / stamina (steel) rounded bars w/ labels + 180ms width tween; damage-flash overlay + level-up flash. |
| **QuickBar** | `hud.rs:setup_inv_hud`/`update_inv_hud` | Bottom-center: gold+stone readout, 4×52px rounded slots (Q/Z/X/C), key + count badges, hover-lift, empty=grayscale. |
| **BuffBar** | `hud.rs` (new pips, replaces text line) | Bottom-left above vitals: icon pip + shrinking duration bar per active buff; renders nothing when idle. |
| **ItemToasts** | `hud.rs:update_inv_hud` | Card w/ green left-accent border, icon + name + count, `toast-in`, 4s auto-expire. (Position per old: upper-left stack.) |
| **Objective banner** (NEW) | `siege.rs` (replaces bare phase bar) | Top-center card: phase label, prep timer + skip button, wave counter, castle-HP bar (turns red on hit), keep-alert pulse + red screen vignette, heirs line (pulses on last heir). |
| **ShopPanel** | `economy.rs:spawn_shop`/`shop_interact` | Scrim + card, header w/ gold, item rows (grid `icon | name | price`), affordable/poor states, buy-pop `shop-pop` anim, close pill. |
| **InventoryPanel** | `inventory.rs:build_inv_panel`/`inv_panel_interact` | Scrim + card, two columns: equipment slots (left) + 6-wide 46px bag grid (right), hover, count badges, close pill. |
| **UpgradeTree** | `economy.rs:spawn_tree`/`tree_interact` | **Parchment serif board** (biggest piece): 4 heraldic charter columns (Economy/Defense/Hero/Arsenal w/ per-branch banner colors + sigil), medallion icons, prereq connector elbows, node states buy / poor (red cost) / `🔒` locked / `✓` owned wax-seal, treasury tally header, footer hint + close. |
| **PauseMenu** | `game_state.rs:spawn_pause_screen` | `pop-in` card, spaced title, primary Resume button; (Settings rows — see §3); Menu/Quit. |
| **GameOver** (Victory/Defeat) | `game_state.rs:spawn_gameover_screen` | `pop-in` glow title (gold victory / red defeat), subtitle, stats row (level/gold/waves), `float-up` Again/Menu buttons. |
| **FloatingText / Ork HP bars** | `combat_fx.rs` | Keep behavior; restyle to theme colors + Inter font once `UiFonts` exists (floats use UI text). |

**Gradient-text note:** bevy_ui text can't fill glyphs with a gradient. The 3js gradient titles are
approximated with a solid near-white fill + the blue glow `BoxShadow`/text-shadow stack. Documented
divergence.

**Backdrop-blur caveat:** bevy_ui can't blur the live 3D scene behind a modal. Approximate with a
stronger dark scrim (`SCRIM`, possibly bumped opacity). Optional future: drive `dof.rs` to blur while
a modal is open.

---

## Section 3 — Added scope (Notice + Settings)

### Notice queue (`src/ui/notice.rs`, new)
A `Notice` resource (VecDeque of `{text, born}`) + a top-center bar styled per old `.notice`
(`padding 9×20`, gold border, `notice-in`). Auto-hides after 3.5s. A `push_notice()` helper any
system can call. Reusable for future events.

### Settings panel + Audio toggle (minimal backing)
- **Audio mute:** add a `AudioSettings { muted }` resource; the audio plugins read it (gate
  playback / set volume to 0). Top-right speaker toggle button (`assets/icons` speaker glyph) +
  a row inside the panel.
- **Fullscreen toggle:** flips `Window::mode` (Bevy built-in — trivial).
- **Effects toggle:** one toggle reusing existing config (e.g. DoF on/off via the value `debug_panel`
  already drives) so the panel does something real without new render systems.
- Panel UI: `pop-in` card with `Settings` title + toggle rows (label + segmented/toggle button),
  Done button. Openable from StartScreen and inline in PauseMenu.
- A small `Settings` modal state or an overlay component (does not need a new `Modal` variant if
  spawned as a plain z-stacked overlay; decided in the plan).

---

## File change summary

**New:** `src/ui/mod.rs`, `theme.rs`, `fonts.rs`, `widgets.rs`, `anim.rs`, `notice.rs`; rework
`src/icons.rs` → `src/ui/icons.rs`. `assets/fonts/*` (Inter ×4 + EB Garamond + OFL.txt),
`assets/icons/twemoji/*.png` (+ LICENSE).

**Rewritten spawn/update fns (no logic change, styling only unless noted):** `game_state.rs`
(start/pause/gameover + settings), `hud.rs` (playerhud/quickbar/buffbar/toasts), `economy.rs`
(shop/tree), `inventory.rs` (bag panel), `siege.rs` (objective banner replaces phase bar),
`combat_fx.rs` (theme colors/font), audio plugins (`AudioSettings` gate). `main.rs` adds
`UiKitPlugin` first.

---

## Emoji / icon codepoint set

Downloaded from the Twemoji set. Mapped by id in `ui/icons.rs`. (Codepoints from the explorer sweep
of the three TS stores; exact filenames — incl. whether `fe0f` is kept — resolved against the asset
repo at download.)

**Items / consumables:** 🍞 1f35e · 🧪 1f9ea · 🍖 1f356 · 🥩 1f969 · 🌿 1f33f · 🍎 1f34e · 🧥 1f9e5 ·
🧫 1f9eb · 🔔 1f514 · 📜 1f4dc
**Weapons:** ⚔️ 2694 · 🗡️ 1f5e1 · 🪓 1fa93 · 🔨 1f528
**Armor:** 🦺 1f9ba · 🛡️ 1f6e1 · 👑 1f451 · 🐉 1f409
**Buffs / quick-slot fallbacks:** food 🍖 1f356 · resist 🛡️ 1f6e1 · power ⚔️ 2694 · haste 💨 1f4a8
**Upgrade nodes:** 🏠 1f3e0 · 🏡 1f3e1 · 🏘️ 1f3d8 · 🌾 1f33e · 💰 1f4b0 · 🏛️ 1f3db · ⚖️ 2696 ·
🧱 1f9f1 · 🚪 1f6aa · 🗼 1f5fc · 🎯 1f3af · 🏹 1f3f9 · 🏰 1f3f0 · 🪖 1fa96 · 🎱 1f3b1 · ⛲ 26f2 ·
❤️ 2764 · 💗 1f497 · 💥 1f4a5 · 🩸 1fa78 · 👢 1f45e · 🌀 1f300 · 🌟 1f31f
**Branch sigils:** Economy 🌾 1f33e · Defense 🛡️ 1f6e1 · Hero ⚔️ 2694 · Arsenal 🏪 1f3ea
**Status symbols:** gold ★ 2b50 (or `2605`) · stone 🪨 1faa8 · sun ☀ 2600 · lock 🔒 1f512 ·
warn ⚠ 26a0 · speaker (settings) 🔊 1f50a / 🔇 1f507 · check ✓ (rendered as wax-seal node, not emoji)

---

## Testing / verification

- `cargo check` + `cargo run` after each phase; `cargo test` (core unchanged — no parity numbers
  touched).
- **Screenshot harness** is the visual gate. Per element:
  - `FOREST_MENU=1 FOREST_SHOT=start.png` — StartScreen.
  - `FOREST_SHOT=hud.png` — in-game HUD (PlayerHud/QuickBar/BuffBar/Objective).
  - `FOREST_PANEL=tree FOREST_SHOT=tree.png` / `FOREST_PANEL=inv FOREST_SHOT=inv.png` — panels.
  - `FOREST_WAVE=1 FOREST_SHOT=siege.png` — objective banner under siege + keep-alert.
  - (Add a shop stage hook if one doesn't exist.)
- Compare each shot against the 3js reference; iterate on theme tokens centrally.

## Non-goals / divergences (intentional)

- No true gradient-fill text; no true backdrop blur (both approximated, noted above).
- LoadingScreen + Minimap deferred (no backing need / never existed).
- Core gameplay numbers untouched — this is pure presentation. The freeze-gate, state machine, and
  `try_despawn`/`try_insert` despawn-race rules are preserved in every rewritten spawn fn.
