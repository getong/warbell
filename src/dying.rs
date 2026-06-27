//! **Shared death-fade.** Any entity marked [`Dying`] crumples — it shrinks, sinks into the
//! ground and tips over — then a single reaper despawns it, instead of popping out instantly.
//! Reused by orks (camp + wave invaders) and wildlife: every kill site swaps its `try_despawn`
//! for [`begin_dying`], and every AI/targeting system filters `Without<Dying>` so a corpse is
//! already "gone" — not re-hittable, not re-rewarded, not counted as a living invader.
//!
//! The fade is a transform-only animation (shrink/sink/tip) — orks share one material across the
//! whole armoury, so fading material alpha would fade the entire horde; collapsing the root
//! transform reads as a believable crumple and needs no per-entity material. The systems run
//! ungated (a corpse keeps fading behind a panel) but read `Time<Virtual>`, so they freeze with
//! the rest of the world during a hit-stop.

use bevy::prelude::*;

/// Seconds a corpse takes to fade out before it's reaped.
const FADE_SECS: f32 = 1.4;
/// World units a corpse sinks over its fade.
const SINK: f32 = 1.1;

/// A mortally-struck entity in its death animation. Combat/AI treat it as already gone.
#[derive(Component)]
pub struct Dying {
    /// `time.elapsed_secs()` at the killing blow.
    pub since: f32,
    /// Blow direction (world XZ, normalized) the killing hit travelled along — the body topples THIS
    /// way and lurches along it, so a kill falls the way you struck it. `ZERO` = an undirected death
    /// (environmental, splash, defender bolt) → a varied left/right fallback tip.
    pub dir: Vec2,
    /// Topple/launch strength: `1` = a normal blow, `>1` = a heavy hit throws the corpse harder.
    pub power: f32,
}

/// Convert a killing blow into a fade instead of an instant despawn. Idempotent — two systems
/// reaping the same entity on one frame (cleave + defender bolt, etc.) is harmless. Undirected:
/// the corpse tips a varied left/right. Use [`begin_dying_struck`] when a blow direction is known.
pub fn begin_dying(commands: &mut Commands, e: Entity, now: f32) {
    commands.entity(e).try_insert_if_new(Dying { since: now, dir: Vec2::ZERO, power: 1.0 });
}

/// Death from a directed blow: the corpse topples + lurches along `dir` (world XZ); `heavy` throws
/// it harder. The money-shot kill — falls the way the hero hit it.
pub fn begin_dying_struck(commands: &mut Commands, e: Entity, now: f32, dir: Vec2, heavy: bool) {
    commands.entity(e).try_insert_if_new(Dying {
        since: now,
        dir: dir.normalize_or_zero(),
        power: if heavy { 1.8 } else { 1.0 },
    });
}

pub struct DyingPlugin;

impl Plugin for DyingPlugin {
    fn build(&self, app: &mut App) {
        app.add_systems(Update, (drive_death_fade, reap_dying));
    }
}

/// Crumple each dying entity: shrink, sink, tip over (delta-based so no initial pose is stored).
/// Topple direction + speed vary per-entity (a stable hash of the entity bits) so a cleared wave
/// doesn't fall as a row of identical clones.
fn drive_death_fade(time: Res<Time>, mut q: Query<(Entity, &Dying, &mut Transform)>) {
    let dt = time.delta_secs();
    let rate = dt / FADE_SECS;
    if rate <= 0.0 {
        return; // hit-stop freeze — corpses hang with the rest of the world
    }
    let now = time.elapsed_secs();
    for (e, dying, mut tf) in &mut q {
        // Shrink + sink, shared by every death.
        tf.scale *= 1.0 - 0.85 * rate;
        tf.translation.y -= SINK * rate;

        if dying.dir != Vec2::ZERO {
            // DIRECTED kill: topple AWAY along the blow + an early launch skid in that direction.
            let d = dying.dir;
            // World axis whose rotation tips the body's top toward `d` (= up × d): a face-plant the
            // way you hit it, not a random spin. `rotate` is world-space about the corpse's origin.
            if let Ok(axis) = Dir3::new(Vec3::new(d.y, 0.0, -d.x)) {
                let topple = 1.9 + (dying.power - 1.0) * 0.8; // total radians over the fade
                tf.rotate(Quat::from_axis_angle(*axis, topple * rate));
            }
            // Launch: a front-loaded skid along the blow over the first ~0.28s (the corpse lurches
            // off the hit, then crumples). `power` throws a heavy kill noticeably further.
            let lurch = (1.0 - (now - dying.since) / 0.28).max(0.0);
            let slide = 4.0 * dying.power * lurch * lurch * dt;
            tf.translation.x += d.x * slide;
            tf.translation.z += d.y * slide;
        } else {
            // UNDIRECTED death: the varied left/right tip (a cleared wave doesn't fall as clones).
            let bits = e.to_bits();
            let h = (bits & 0xff) as f32 / 255.0; // 0..1, stable per corpse
            let side = if bits & 1 == 0 { 1.0 } else { -1.0 };
            let speed = 1.1 + h * 0.7; // 1.1..1.8 — some crumple fast, some slow
            tf.rotate_local_z(side * speed * rate);
        }
    }
}

/// Despawn a corpse once its fade is spent.
fn reap_dying(time: Res<Time>, mut commands: Commands, q: Query<(Entity, &Dying)>) {
    let now = time.elapsed_secs();
    for (e, d) in &q {
        if now - d.since >= FADE_SECS {
            commands.entity(e).try_despawn();
        }
    }
}
