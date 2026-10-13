//! Team colours + selection ring in one. A pooled ground mark sits under each **selected** unit,
//! tinted by [`Side`] (player = pale bone-grey, rival = muted rust). Only selected units are ringed
//! — an always-on ring under every body read as clutter — so the ring doubles as the "this is
//! selected" marker. Buildings are never ringed.
//!
//! Same reposition-a-pool approach (no per-entity child management, so a ring can't orphan when a
//! unit dies mid-frame). Each ring is a `combat_marks` decal (`MarkKind::Select`): shared quad +
//! shared lit material, so it sits in the scene's light instead of glowing like the old flat unlit
//! annulus; the side rides the instance `MeshTag`.

use bevy::mesh::MeshTag;
use bevy::prelude::*;

use crate::combat_marks::{spawn_mark, tag, MarkAssets, MarkKind};
use crate::dying::Dying;
use crate::game_state::AppState;
use crate::rts::{in_skirmish, RtsUnit, Selected, Side};

/// World diameter of a selection mark (the line sits at r ≈ 0.84 of the half-width).
const RING_D: f32 = 1.5;

#[derive(Component)]
struct TeamRing;

pub struct RtsTeamColorPlugin;

impl Plugin for RtsTeamColorPlugin {
    fn build(&self, app: &mut App) {
        app.add_systems(
            Update,
            sync_team_rings
                .run_if(in_skirmish)
                .run_if(in_state(AppState::Playing)),
        );
    }
}

#[allow(clippy::type_complexity)]
fn sync_team_rings(
    mut commands: Commands,
    marks: Res<MarkAssets>,
    units: Query<(&GlobalTransform, &Side), (With<RtsUnit>, With<Selected>, Without<Dying>)>,
    mut rings: Query<(&mut Transform, &mut Visibility, &mut MeshTag), With<TeamRing>>,
) {
    // Desired rings: (world pos, side) — units only.
    let want: Vec<(Vec3, Side)> = units.iter().map(|(gt, side)| (gt.translation(), *side)).collect();

    // Grow the pool.
    let have = rings.iter().count();
    for _ in have..want.len() {
        let e = spawn_mark(&mut commands, &marks, MarkKind::Select, Vec3::new(0.0, -100.0, 0.0), RING_D, 0.0, 1.0, 0.9, 3);
        commands.entity(e).insert((Visibility::Hidden, TeamRing));
    }

    let mut it = want.into_iter();
    for (mut tf, mut vis, mut mt) in &mut rings {
        match it.next() {
            Some((p, side)) => {
                tf.translation = Vec3::new(p.x, p.y + 0.04, p.z);
                let aux = match side {
                    Side::Player => 0.0,
                    Side::Rival => 1.0,
                };
                let t = tag(MarkKind::Select, 0.9, 3, aux);
                if mt.value != t.value {
                    mt.value = t.value;
                }
                *vis = Visibility::Visible;
            }
            None => *vis = Visibility::Hidden,
        }
    }
}
