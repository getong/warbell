# First-person mode — design

**Date:** 2026-06-16
**Status:** approved, implementing

## Goal

A toggleable first-person camera for the knight. Full-combat (attacks/blocks/arts fire
where you look), reachable from a HUD button and the **V** key. Designed to avoid motion
sickness and photosensitive-seizure triggers (the user's explicit concern).

## Background (verified from code)

- Camera is a third-person orbit around the hero: `OrbitCam { azimuth, pitch, dist, locked }`
  in `src/player/camera.rs`. Mouse (while `locked`) drives azimuth/pitch; wheel drives dist.
- `PlayMode` (`src/player/mod.rs`) = `Play | FreeRoam` (backtick toggles to the debug fly-cam).
- Movement (`src/player/movement.rs`) is **camera-relative** (W = flattened camera-forward) and
  lerps `hero.facing` toward the move direction. Combat cone (`combat.rs:407`) and arts
  (`arts.rs:99`) read `hero.facing`.
- **The camera never uses the body bob** — it tracks `hero.y + EYE_H`, so first-person has no
  head-bob by construction.
- Combat hits add a trauma **screen-shake** (`sin(t*47)`-style jitter) and an **FOV punch** in
  `player_camera` (`camera.rs:171-184`), fed by `combat_fx::HitFeedback`.

## Research (motion sickness + epilepsy)

- Top first-person sickness triggers: screen-shake, head-bob, motion blur, narrow FOV, low FPS;
  best practice is to damp/disable them. (Busseneau; Xbox Accessibility Guideline 117.)
- WCAG 2.3.1 / game-accessibility: avoid >3 flashes/sec over ≥25% of screen for >5s; oscillating
  full-screen motion is in scope. At first-person scale the raw combat shake fills the whole view
  with high-frequency oscillation — that is the targeted risk.

## Design

First-person is a **sub-mode of Play**, not a new `PlayMode`. New resource (in `player/mod.rs`):

```rust
#[derive(Resource, Default)]
pub struct FirstPerson {
    pub active: bool, // toggled by button / V key
    pub blend: f32,   // eased 0 (third) -> 1 (first); smooth transition, no hard cut
    pub pitch: f32,   // FP look-pitch, INDEPENDENT of orbit.pitch
}
```

`orbit.azimuth` is shared (heading survives the toggle). `orbit.pitch` is the camera's
*elevation above the hero* (always tilts the view down) — useless as a look-pitch, so FP keeps
its own `fp.pitch`, clamped to a natural look range (~ -1.3 up-to-down .. +1.3).

### Camera (`player/camera.rs`)

1. **Input:** when `orbit.locked`, mouse delta drives `orbit.azimuth` always; the vertical delta
   drives `fp.pitch` when `fp.active` and `orbit.pitch` otherwise.
2. **Toggle:** a system flips `fp.active` on **V**; the HUD button writes the same flag.
3. **Blend:** ease `fp.blend` toward `active ? 1 : 0` (same exp-ease as `build_blend`).
4. **Pose:** FP eye = `(hero.pos.x, hero.y + FP_EYE_H, hero.pos.y)` with `FP_EYE_H ≈ 1.55`;
   forward = `dir(azimuth, fp.pitch)`. Lerp eye + look-target between the third-person pose and
   the FP pose by `blend` (a smooth dolly-in).
5. **Aim coupling:** when `blend > 0.5`, set `hero.facing = look yaw` so attacks fire where you
   look. The camera system must run **after** movement so this write wins (verify in `main.rs`
   schedule; add `.after(...)` if needed).
6. **Hide body:** `blend > 0.5` → hero root `Visibility::Hidden`, else `Visibility::Inherited`
   (the head would otherwise fill the screen). Weapon goes with it (no FP arms — YAGNI).
   Known tradeoff: the hero's own shadow disappears in FP — unnoticeable from the eyes.

### Anti-sickness / anti-epilepsy (the targeted fix)

- Scale the combat **screen-shake and FOV-punch by `(1 - 0.75 * blend)`** — damped, not removed,
  so a hit still reads as a hit but never becomes a full-screen high-freq oscillation.
- No head-bob (already absent from the camera path; body hidden anyway).
- Eased toggle (no jarring cut). FOV otherwise stable.

### Toggle UI (`ui/settings.rs`)

An "eye" icon button in the existing top-right row (next to mute / fullscreen / quality). Click
flips `FirstPerson::active`; a `Notice` confirms ("First person" / "Third person"). Hotkey **V**.

## Files touched

- `src/player/mod.rs` — `FirstPerson` resource + register default.
- `src/player/camera.rs` — input split, toggle (V), blend, FP pose, facing coupling, shake damp,
  body hide. (Most of the work.)
- `src/ui/settings.rs` — eye toggle button + click handler.

## Out of scope / non-goals

- First-person arms/weapon viewmodel.
- Per-effect intensity sliders (single damped mode instead).
- Saving the FP toggle across runs (it's a transient view preference, like the debug panel).
- FreeRoam fly-cam is untouched.
