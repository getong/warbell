//! **Soft-lock** — a light, AAA-style combat aim-assist (the Witcher "soft target"): while a
//! hostile is near and in front, the game quietly PICKS it as your target, marks it with a quiet
//! feathered ground ring, and MEASUREDLY eases the hero's facing onto it — never a hard snap, never
//! a camera lock. Your own movement always overrides (the turn only nudges while you stand), and the
//! swing then commits to the same ringed foe (see `combat::player_attack`, which reads `soft_pos`).
//!
//! It engages purely from proximity to a THREAT (ork / boss / warlord / rival soldier / hunting
//! predator within [`SOFT_RANGE`] in the front arc) — i.e. exactly when you're in a fight — and
//! drops the instant no threat is in front. Wildlife counts ONLY for the hunting species
//! (`wildlife::is_hostile_species` — wolf/bear/boar/scorpion/croc/golem); grazers never grab the
//! ring, so exploring doesn't auto-turn you at deer or workers.

use bevy::mesh::MeshTag;
use bevy::prelude::*;

use super::{Hero, PlayMode};
use crate::combat_marks::{self, MarkAssets, MarkKind};
use crate::boss::Boss;
use crate::dying::Dying;
use crate::orks::Ork;
use crate::rival::RivalSoldier;
use crate::warlord::Warlord;
use crate::wildlife::Animal;

/// The single reusable target-ring entity (moved under the soft target each frame). Carries its
/// own fade so a new target fades in where it stands instead of the ring sliding across the field.
#[derive(Component, Default)]
pub struct TargetRing {
    /// 0..1 fade (eased toward 1 while a target is held, 0 when none).
    shown: f32,
    /// The foe the ring currently marks — a switch restarts the fade at the new foe.
    on: Option<Entity>,
}

/// Ring world diameter (the feathered line sits at 80% of the quad's half-size → ≈0.9u radius:
/// just outside a `WORLD_BUMP`-scaled ork's footprint, so it frames the feet instead of hiding
/// under them).
const RING_DIAMETER: f32 = 2.25;
/// Peak strength of the ring line — a quiet mark, never a hoop.
const RING_ALPHA: f32 = 0.62;
/// Fade in / out rates (1/s) and the slow drift of its ticks (rad/s).
const RING_FADE_IN: f32 = 9.0;
const RING_FADE_OUT: f32 = 7.0;
const RING_SPIN: f32 = 0.35;

/// Consider hostiles within this world-XZ distance (a bit past melee, so a closing foe is picked
/// before you're on top of it).
const SOFT_RANGE: f32 = 7.0;
/// Hostiles within this range (ANY direction — a flanker counts) are tallied into `hero.threats`,
/// which the camera reads to scale its combat dolly with the size of the scrap.
const THREAT_RANGE: f32 = 9.0;
/// Front-arc gate: `dir·facing` must exceed this. −0.15 ≈ a 190° arc — a foe circling to your side
/// stays targeted, but one squarely behind you does not.
const FRONT_DOT: f32 = -0.15;
/// How much better a dead-ahead foe scores vs a side one (world units of "virtual" nearness). Makes
/// the pick favour whoever you're facing, so you steer targets by turning — not just by nearness.
const ALIGN_BONUS: f32 = 2.0;
/// The current target keeps this scoring edge, so it doesn't flicker to a marginally-closer foe.
const STICKY_BONUS: f32 = 1.6;
/// Measured auto-face speed (rad/s) — deliberately gentle (well under the 6–15 rad/s swing/move
/// turns) so it reads as a soft assist easing you onto the foe, not a snap.
const SOFT_TURN_RATE: f32 = 2.5;

/// Spawn the one reusable ground ring (hidden until there's a target): a `combat_marks` decal —
/// a thin, feathered, PBR-lit pale line in four soft-ended arcs with small inward ticks, faintly
/// shadowed outside, so it reads pressed into the ground under the foe. (It was a flat amber
/// emissive 40-gon `Annulus` — a glowing low-poly hoop next to the realistic forest.)
pub fn spawn_target_ring(mut commands: Commands, marks: Res<MarkAssets>) {
    let e = combat_marks::spawn_mark(
        &mut commands, &marks, MarkKind::Ring, Vec3::new(0.0, -100.0, 0.0), RING_DIAMETER, 0.0, 1.0, 0.0, 0,
    );
    commands.entity(e).insert((Visibility::Hidden, TargetRing::default(), crate::game_state::CampaignOnly));
}

/// Pick the soft target, ease facing onto it, and drive the ring. Runs right after `player_move` so
/// live movement input (which already set `facing`) wins — the assist only nudges while you stand.
pub fn soft_lock(
    mode: Res<PlayMode>,
    time: Res<Time>,
    mut hero_q: Query<&mut Hero>,
    hostiles: Query<
        (Entity, &GlobalTransform, Option<&Animal>),
        (
            Or<(
                With<Ork>,
                With<Boss>,
                With<Warlord>,
                With<RivalSoldier>,
                With<Animal>,
                With<crate::snowman::Snowman>,
            )>,
            Without<Dying>,
        ),
    >,
    mut ring_q: Query<(&mut Transform, &mut Visibility, &mut TargetRing, &mut MeshTag)>,
) {
    let Ok(mut hero) = hero_q.single_mut() else { return };

    // Out of play (free-cam / paused-to-menu): no target, hide the ring.
    if *mode != PlayMode::Play {
        hero.soft_target = None;
        hero.soft_pos = None;
        hero.threats = 0;
        for (_, mut vis, mut ring, _) in &mut ring_q {
            vis.set_if_neq(Visibility::Hidden);
            ring.shown = 0.0;
            ring.on = None;
        }
        return;
    }

    // ── Pick the best hostile in the front arc within range (tallying threats as we scan) ──
    let fwd = Vec2::new(hero.facing.sin(), hero.facing.cos());
    let mut best: Option<(f32, Entity, Vec2)> = None; // (score — lower is better, entity, pos)
    let mut threats = 0u32;
    for (e, gt, animal) in &hostiles {
        // Wildlife: only the hunting species are foes — a deer/rabbit never grabs the ring.
        if animal.is_some_and(|a| !crate::wildlife::is_hostile_species(a.species)) {
            continue;
        }
        let t = gt.translation();
        let pos = Vec2::new(t.x, t.z);
        let to = pos - hero.pos;
        let d = to.length();
        if d <= THREAT_RANGE && d > 1e-3 {
            threats += 1; // any-direction tally for the camera's combat dolly
        }
        if d > SOFT_RANGE || d < 1e-3 {
            continue;
        }
        let align = (to / d).dot(fwd); // 1 = dead ahead
        if align < FRONT_DOT {
            continue; // behind you
        }
        let mut score = d - align * ALIGN_BONUS;
        if hero.soft_target == Some(e) {
            score -= STICKY_BONUS; // keep the committed target unless clearly beaten
        }
        if best.map_or(true, |(bs, _, _)| score < bs) {
            best = Some((score, e, pos));
        }
    }
    hero.threats = threats;
    match best {
        Some((_, e, pos)) => {
            hero.soft_target = Some(e);
            hero.soft_pos = Some(pos);
        }
        None => {
            hero.soft_target = None;
            hero.soft_pos = None;
        }
    }

    // ── Measured auto-face — only while standing (moving already steers facing) and not mid-swing
    // (the swing owns its own lean toward the same target). Gentle rate = an ease, not a snap.
    if let (Some(tp), false, false) = (hero.soft_pos, hero.moving, hero.attacking) {
        let to = tp - hero.pos;
        let want = to.x.atan2(to.y);
        let f = (time.delta_secs() * SOFT_TURN_RATE).min(1.0);
        hero.facing = super::movement::lerp_angle(hero.facing, want, f);
    }

    // ── Drive the ring: follow the target, fade in on (re)acquire, fade out when it drops ──
    let dt = time.delta_secs();
    for (mut tf, mut vis, mut ring, mut tag) in &mut ring_q {
        if hero.soft_target != ring.on && hero.soft_target.is_some() {
            // New foe: restart the fade where it stands (no slide across the field).
            ring.on = hero.soft_target;
            ring.shown = 0.0;
        }
        match hero.soft_pos {
            Some(tp) => {
                let y = crate::worldmap::ground_at_world(tp.x, tp.y).unwrap_or(hero.y) + 0.03;
                tf.translation = Vec3::new(tp.x, y, tp.y);
                ring.shown = (ring.shown + dt * RING_FADE_IN).min(1.0);
            }
            None => ring.shown = (ring.shown - dt * RING_FADE_OUT).max(0.0),
        }
        if ring.shown <= 0.0 {
            ring.on = None;
            vis.set_if_neq(Visibility::Hidden);
            continue;
        }
        vis.set_if_neq(Visibility::Visible);
        // A slow drift of the ticks keeps the mark alive without any pulse or glow.
        tf.rotate_y(dt * RING_SPIN);
        let ease = ring.shown * ring.shown * (3.0 - 2.0 * ring.shown);
        let want = combat_marks::tag(MarkKind::Ring, RING_ALPHA * ease, 0, 0.0);
        if tag.value != want.value {
            tag.value = want.value;
        }
    }
}
