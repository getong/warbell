//! The castle town kit (zamek v2, phase 3d — `docs/superpowers/specs/2026-10-11-zamek-v2-design.md`
//! §3/§4): granary on staddle stones, smithy, the tavern "The Drowned Squire", Maud's house with
//! the edict board, infirmary + herb garden, the courtyard fire pit, the empty grave of the drowned
//! squire, the Crown set (banners, painted crates, tent, gallows, depot) and four timber-frame
//! houses, built by `tools/blender_forest/town_kit.py` → `town_kit.glb` (node names, footprints and
//! heights are listed in that script's docstring).
//!
//! Every piece has its pivot on the ground under the centre of its footprint with the door / front
//! toward local +Z (`crown_banner_wall` hangs down from its bracket at the origin instead), so a
//! layout only needs [`spawn_piece`] with a ground-snapped transform. The castle layout itself is
//! placed elsewhere (`castle.rs` / `market.rs`, phase 4); this module only carries the handle and a
//! screenshot showcase: `FOREST_TOWNKIT_SHOWCASE=1` lays every piece out on the open ground north of
//! the castle (see [`SHOWCASE`]); park the hero beside one with `FOREST_HERO="x,z"` for scale.

use bevy::camera::visibility::VisibilityRange;
use bevy::prelude::*;

use crate::biome::BiomeEntity;

pub struct TownKitPlugin;

impl Plugin for TownKitPlugin {
    fn build(&self, app: &mut App) {
        if std::env::var("FOREST_TOWNKIT_SHOWCASE").is_ok_and(|v| v != "0") {
            app.add_systems(Update, spawn_showcase);
        }
    }
}

/// The pieces `town_kit.glb` carries, in the script's priority order.
pub const PIECES: [&str; 19] = [
    "town_granary",
    "town_smithy",
    "town_tavern",
    "town_maud_house",
    "town_infirmary",
    "town_firepit",
    "town_grave",
    "crown_banner_wall",
    "crown_banner_pole",
    "crown_crates",
    "crown_tent",
    "crown_gallows",
    "crown_depot",
    "town_house_a",
    "town_house_b",
    "town_house_c",
    "town_house_d",
    "town_carpenter",
    "town_archery",
];

/// A spawned town-kit model root.
#[derive(Component)]
pub struct TownPiece;

/// Spawn town-kit piece `name` at `tf` (pivot = the ground under its footprint centre, front to
/// local +Z). `None` when the kit isn't loaded yet or has no such piece. The caller adds its own
/// tags (`BiomeEntity`, colliders); the piece fades out past ~150 u like the market.
pub fn spawn_piece(commands: &mut Commands, name: &str, tf: Transform) -> Option<Entity> {
    let kit = crate::realforest::get().filter(|k| k.has(name))?;
    let range = VisibilityRange { start_margin: 0.0..0.0, end_margin: 140.0..160.0, use_aabb: true };
    let e = kit.spawn_static_with(commands, name, tf, range)?;
    commands.entity(e).insert(TownPiece);
    Some(e)
}

/// Showcase layout: (piece, world XZ, yaw, collider half-extents of the main body or zero).
/// Rows on the flat ground north of the castle, fronts facing south (+Z) toward the north wall so
/// a camera just outside the wall sees them at 15-20 u: the landmarks + the Crown set at z -29,
/// small props at z -37.5, Maud's house, the infirmary and the houses at z -46.
pub const SHOWCASE: [(&str, Vec2, f32, Vec2); 19] = [
    ("town_granary", Vec2::new(-25.0, -29.0), 0.0, Vec2::new(1.75, 2.25)),
    ("town_smithy", Vec2::new(-16.0, -29.0), 0.0, Vec2::ZERO),
    ("town_tavern", Vec2::new(-5.5, -29.0), 0.0, Vec2::new(3.3, 2.5)),
    ("town_grave", Vec2::new(3.0, -29.0), 0.0, Vec2::ZERO),
    ("crown_gallows", Vec2::new(7.5, -29.0), 0.0, Vec2::new(1.1, 0.8)),
    ("crown_crates", Vec2::new(11.0, -29.0), 0.0, Vec2::ZERO),
    ("crown_tent", Vec2::new(14.3, -29.0), 0.0, Vec2::new(1.2, 1.4)),
    ("crown_banner_pole", Vec2::new(17.0, -29.0), 0.0, Vec2::ZERO),
    ("crown_depot", Vec2::new(21.0, -29.0), 0.0, Vec2::new(1.7, 1.3)),
    // On the depot's west plank wall (x = 21 - 1.6), facing west, the bracket 2.1 up.
    ("crown_banner_wall", Vec2::new(19.32, -29.2), -std::f32::consts::FRAC_PI_2, Vec2::ZERO),
    ("town_firepit", Vec2::new(-25.0, -37.5), 0.0, Vec2::ZERO),
    ("town_carpenter", Vec2::new(-18.0, -37.5), 0.0, Vec2::ZERO),
    ("town_archery", Vec2::new(-12.0, -37.5), 0.0, Vec2::ZERO),
    ("town_maud_house", Vec2::new(-24.0, -46.0), 0.0, Vec2::new(2.7, 2.0)),
    ("town_infirmary", Vec2::new(-12.5, -46.0), 0.0, Vec2::new(3.7, 1.9)),
    ("town_house_a", Vec2::new(-1.0, -46.0), 0.0, Vec2::new(2.4, 1.8)),
    ("town_house_b", Vec2::new(7.0, -46.0), 0.0, Vec2::new(2.9, 1.9)),
    ("town_house_c", Vec2::new(15.0, -46.0), 0.0, Vec2::new(2.0, 1.7)),
    ("town_house_d", Vec2::new(22.0, -46.0), 0.0, Vec2::new(2.5, 1.9)),
];

/// Lays the showcase out once the kit has loaded; a world rebuild clears it (`BiomeEntity`) and
/// this lays it out again.
fn spawn_showcase(mut commands: Commands, existing: Query<(), With<TownPiece>>) {
    if !existing.is_empty() || !crate::realforest::get().is_some_and(|k| k.has(PIECES[0])) {
        return;
    }
    let ground = |p: Vec2| crate::worldmap::ground_at_world(p.x, p.y).unwrap_or(0.0);
    let mut n = 0;
    for (name, p, yaw, half) in SHOWCASE {
        let y = if name == "crown_banner_wall" { ground(Vec2::new(21.0, -29.0)) + 2.1 } else { ground(p) - 0.02 };
        let tf = Transform::from_xyz(p.x, y, p.y).with_rotation(Quat::from_rotation_y(yaw));
        let Some(e) = spawn_piece(&mut commands, name, tf) else { continue };
        commands.entity(e).insert(BiomeEntity);
        if half != Vec2::ZERO {
            crate::blockers::add_obb(p.x, p.y, half.x, half.y, yaw);
        }
        n += 1;
    }
    info!("town kit showcase: {n} pieces laid out north of the castle");
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The showcase lays out every piece exactly once, and the pieces don't overlap.
    #[test]
    fn showcase_covers_every_piece_once() {
        for name in PIECES {
            assert_eq!(SHOWCASE.iter().filter(|s| s.0 == name).count(), 1, "{name}");
        }
        for (i, a) in SHOWCASE.iter().enumerate() {
            for b in &SHOWCASE[i + 1..] {
                if a.3 != Vec2::ZERO && b.3 != Vec2::ZERO {
                    let gap = (a.1 - b.1).abs() - (a.3 + b.3);
                    assert!(gap.x > 0.5 || gap.y > 0.5, "{} overlaps {}", a.0, b.0);
                }
            }
        }
    }
}
