# Screen-space god rays (light scattering) — design

**Date:** 2026-06-23
**Status:** approved, implementing

## Problem

The daytime scene reads "blank" — flat, evenly lit, no sense of light pushing through the canopy.
The pipeline is already rich (AgX, bloom, SSAO, SMAA, contact+cascade shadows, bokeh DoF, toon
outline, ColorGrading, biome fog, Atmosphere sky, IBL), so contrast/shadow tweaks won't move it.

We already have a **volumetric** god-ray path (`VolumetricFog` + `FogVolume` + the sun's
`VolumetricLight`, on Ultra only). It is a dead end: at the scene's subtle fog it is *imperceptible*,
yet it is the frame's single biggest GPU cost (~13 ms), and any visible density blacks out the
Atmosphere sky (sky pixels have no depth → the volumetric march runs to infinity). This is the
documented `quality.rs::ultra_fog` trap and why "god rays never worked".

## Decision

Replace the volumetric path with a **screen-space radial light-scattering** post pass — the same
effect the original TS game shipped (GPU Gems 3, Ch. 13). Reliable, cheap, always visible, and
**fits the existing custom-post-pass pattern** (`dof.rs`, `outline.rs` are the same shape).

## Effect

For each pixel, march N samples toward the sun's **screen-space position**, accumulating sampled
scene brightness with per-step exponential decay, then **additively** composite, tinted by the sun
colour. The "light mask" is the scene's own luminance (sky/sun = bright, trees = dark), so the
shafts naturally form along the treeline silhouette with no extra geometry or occlusion buffer.

## Architecture (mirrors `dof.rs` 1:1)

- `assets/shaders/godrays.wgsl` — fullscreen fragment; bindings: scene texture + linear sampler +
  `GodRays` uniform. No depth/normal prepass needed.
- `src/godrays.rs` — `GodRaysPlugin`:
  - `GodRays` component = shader uniform (`ExtractComponent` + `ShaderType`): `sun_color`,
    `intensity`, `sun_screen` (UV), `decay`, `density`, `weight`, `threshold`, `num_samples`, `fade`.
  - `RenderStartup` pipeline init; pass system in `Core3dSystems::PostProcess`, pinned
    `.after(smaa).before(outline_pass)` → chain `tonemapping → smaa → godrays → outline → dof`
    (godrays is a `post_process_write` ping-pong pass, so it must be pinned like the others to
    avoid the documented executor-race flicker).
  - `Update` system `drive_godrays`: projects the sun direction to screen UV via `Camera::world_to_ndc`,
    sets `sun_color` from the live sun `DirectionalLight`, and computes `fade` = daylight (sun above
    horizon) × on-screen alignment (camera-forward · to-sun). Rays vanish at night and when the sun
    is behind/beside the camera.

## Scope

- **High + Ultra** carry it (`preset_settings`). **Low does not** (it strips post passes for iGPUs).
  This is the point: it lifts the *everyday* default look, not just the showcase.
- The `god_rays: bool` setting in `GraphicsSettings` now toggles the **screen-space** pass (insert/
  remove the `GodRays` component on the camera, exactly like outline/dof). The volumetric toggling
  (`VolumetricLight` on the sun, `ultra_fog()` swap) is **removed**. The inert `VolumetricFog`/
  `FogVolume` entities cost nothing without a `VolumetricLight` and are left in place.
- `FOREST_GODRAYS="intensity,decay,density,weight,threshold,num_samples"` startup knob for the
  screenshot harness (same idea as the other `FOREST_*` staging hooks).

## Verification

`FOREST_SHOT` + `FOREST_QUALITY=ultra` + a low golden-hour `FOREST_TIME` (sun near the treeline) →
before/after PNG. That is the framing where the effect reads strongest.

## Deliberately out of scope (YAGNI — separate follow-ons)

Sun lens flare, a filmic/split-tone grade overhaul for the warm-haze wash, CAS sharpening. Ship the
god rays first as a clean, reversible upgrade.
