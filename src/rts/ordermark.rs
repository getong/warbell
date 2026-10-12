//! Click-order feedback — a Stronghold-style marker that pops + fades at the spot the player just
//! ordered troops to (chalk chevrons for a move/harvest, muted rust for an attack/attack-move).
//! Gives the "yes, I heard you, here" confirmation the RTS was missing.
//!
//! `command.rs` writes an [`OrderMark`] for PLAYER orders only (AI orders don't mark). Each one is a
//! `combat_marks` ground decal (shared quad + material) that shrinks and fades over ~0.6s.

use bevy::prelude::*;

use crate::game_state::AppState;
use crate::rts::in_skirmish;

/// A player order landed here — spawn a marker. `attack` picks red vs green.
#[derive(Message)]
pub struct OrderMark {
    pub at: Vec2,
    pub attack: bool,
}

/// Marker lifetime (seconds).
const DUR: f32 = 0.6;

pub struct RtsOrderMarkPlugin;

impl Plugin for RtsOrderMarkPlugin {
    fn build(&self, app: &mut App) {
        app.add_message::<OrderMark>().add_systems(
            Update,
            spawn_marks.run_if(in_skirmish).run_if(in_state(AppState::Playing)),
        );
    }
}

/// Spawn one shared-material ground mark per player order (`combat_marks` chevrons: chalk for a
/// move, muted rust for an attack). `MarkFade` shrinks + fades + reaps it — no per-click material.
fn spawn_marks(
    mut commands: Commands,
    marks: Res<crate::combat_marks::MarkAssets>,
    time: Res<Time>,
    mut msgs: MessageReader<OrderMark>,
) {
    use crate::combat_marks::{spawn_mark, MarkFade, MarkKind};
    let now = time.elapsed_secs();
    for ev in msgs.read() {
        let kind = if ev.attack { MarkKind::OrderAttack } else { MarkKind::Order };
        let y = crate::worldmap::ground_at_world(ev.at.x, ev.at.y).unwrap_or(0.0) + 0.03;
        let e = spawn_mark(&mut commands, &marks, kind, Vec3::new(ev.at.x, y, ev.at.y), 2.2, 0.0, 1.0, 0.9, 0);
        commands.entity(e).insert((
            MarkFade { kind, seed: 0, born: now, hold: DUR * 0.3, life: DUR * 0.7, a0: 0.9, s0: 2.2, s1: 1.4 },
            crate::rts::RtsSpawned,
        ));
    }
}
