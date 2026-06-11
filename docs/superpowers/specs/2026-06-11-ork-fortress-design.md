# Ork Fortress ("Gnashfang Hold") — design

**Date:** 2026-06-11 · **Status:** approved (user said "All good implement")

A non-playable ork stronghold extending the world beyond the swamp (south) edge of the island.
Pure world-dressing with one gameplay tooth: its watchtowers fire real, blockable bolts at the
hero who comes too close. The hero can never enter; the orks never leave.

## Decisions (user-confirmed)

- **Tower fire:** real damage (~shaman-bolt 26, blockable), not theatre.
- **Separation:** palisade at one land neck + sea strait elsewhere. Palisade LOW (~1.5× hero
  height ≈ 2.7u) so the player standing at it sees inside.
- **Scale:** big stronghold (~38×32 world units), reads as THE ork seat of power.
- **Interior:** living — idle orks milling, bonfire, smoke, banners; never path outside.
- **Centerpiece:** crude timber great hall + crooked leaning spire with iron crown + green brazier.
- **Bolts:** sickly green warp-fire (contrast castle cyan).
- **Approach flavor:** war horn + agitated ork shouts on first threshold crossing, then towers hot.
- **Siege tie-in:** subtle — fires/brazier flare brighter during night waves; war drums carry.
- **Warlord:** one oversized berserker-model ork, unique trim, paces hall ↔ bonfire. Decorative.
- **Gate front:** shut spiked gate facing island + rotting broken-bridge stubs across the strait.
- **Ground:** swamp greens fade to trampled black mud, bone/stump scatter near walls.
- **Name notice:** one-time location notice "Gnashfang Hold" on first close approach.

## Approach (chosen: A)

Self-contained `src/ork_fortress.rs` plugin. Bespoke islet terrain mesh south of the grid
(approx Z +84…+120, centred ~`(12, 100)` world), own structures reusing `camps.rs` visual
vocabulary scaled up, decorative ork population with bounded wander, hero-targeting towers
mirroring `defenses.rs` patterns. Zero touch to `worldmap` grid, navgrid, or `crates/core`
(no parity impact).

Rejected: extending the worldmap grid (GZ recentre shifts every world coordinate — breaks
nav/parity/determinism) and an on-island landmark (doesn't extend the world).

## Architecture

- **Geography:** islet floats on the existing 900×900 sea plane (`worldmap::build`). Hero
  containment is free: `player::movement::footing()` is `None` off-grid, so the strait and the
  off-grid land neck are unwalkable; the palisade stands at the walkable boundary as the
  *visual* excuse. Land neck (~8u wide) touches the grid edge at the swamp coast.
- **Meshes:** per CONTRACT — vertex colour (`palette::lin`), parts `tinted()` then merged,
  `duplicate_vertices()` + `compute_flat_normals()`, shared white material for batching.
- **Population:** new `FortressOrk` marker (NOT `orks::Ork` — no warband AI, untargetable,
  no `WaveInvader`). Bounded random wander inside walls + existing idle bob/sway look.
- **Towers:** `FortressTower` emitters; hero in ~16u range → green bolt via
  `projectile::advance_bolt`, damage through the existing blockable hero-damage path
  (`PendingHeroDamage`). Per-tower cooldown. Gated `run_if(in_state(Modal::None))`.
- **Threshold:** distance check on fortress centre; first crossing fires horn (reuse
  `wave-start-roar.ogg` or synth) + ork shout cues + one-time notice via existing notice UI.
- **Drums/campfire audio for free:** the bonfire uses `camps::Flicker`, which the ambience
  system already targets to attach spatial campfire + war-drum sinks.
- **Siege flare:** read `siege::GamePhase`; lerp fire/brazier point-light intensity up at night
  wave.
- **Quality:** Low preset → fewer decorative orks + reduced particles, following `quality.rs`
  conventions.

## Verification

`FOREST_SHOT`/`FOREST_CLIP` staging: hero at swamp coast (`FOREST_HERO`), camera framing the
hold; orbit clip of the islet. `cargo test` unaffected (no core changes). `cargo check` +
full build + screenshots before claiming done.
