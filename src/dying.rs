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
}

/// Convert a killing blow into a fade instead of an instant despawn. Idempotent — two systems
/// reaping the same entity on one frame (cleave + defender bolt, etc.) is harmless.
pub fn begin_dying(commands: &mut Commands, e: Entity, now: f32) {
    commands.entity(e).try_insert_if_new(Dying { since: now });
}

pub struct DyingPlugin;

impl Plugin for DyingPlugin {
    fn build(&self, app: &mut App) {
        app.add_systems(Update, (drive_death_fade, reap_dying));
    }
}

/// Crumple each dying entity: shrink, sink, tip over (delta-based so no initial pose is stored).
fn drive_death_fade(time: Res<Time>, mut q: Query<&mut Transform, With<Dying>>) {
    let rate = time.delta_secs() / FADE_SECS;
    if rate <= 0.0 {
        return; // hit-stop freeze — corpses hang with the rest of the world
    }
    for mut tf in &mut q {
        tf.scale *= 1.0 - 0.85 * rate;
        tf.translation.y -= SINK * rate;
        tf.rotate_local_z(1.4 * rate);
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
