//! The castle market (map-centre rework, phase 2 — `docs/superpowers/specs/2026-10-11-centrum-mapy-design.md`).
//!
//! Four trestle stalls flank the west cart lane between the keep plaza and the west gate, each with
//! its trade on the counter (bread, cloth, pots, apples / cabbages / fish), plus a hand-cart and a
//! barrel stack (`tools/blender_forest/market.py` → `market.glb`). A vendor stands behind every
//! counter facing the lane, and a couple of townsfolk pause in front of the stalls — so the yard
//! reads as a town someone lives and trades in, not a fort.
//!
//! The people are plain scene peasants (`villagers::spawn_scene_peasant`, `SceneActor` keeps the
//! wander brain off them): they idle in place, and the night curfew hides them with the other
//! non-combatants. Spawned once the castle stands and the kit has the market models; tagged
//! `BiomeEntity`, so a world rebuild clears them and this system lays the market out again.

use bevy::camera::visibility::VisibilityRange;
use bevy::prelude::*;

use crate::biome::BiomeEntity;

pub struct MarketPlugin;

impl Plugin for MarketPlugin {
    fn build(&self, app: &mut App) {
        app.add_systems(Update, (spawn_market, vendor_barks));
    }
}

/// A vendor behind a counter: greets the hero when he walks past (the villager `Greeting` pool —
/// "Finest wares this side of the swamp…" among them), at most once per [`VENDOR_GAP`] each.
#[derive(Component)]
pub struct MarketVendor {
    next: f32,
}

/// Hero within this of a vendor (world units) → a greeting.
const BARK_DIST: f32 = 3.2;
/// Per-vendor quiet time (s) after a greeting, and the market-wide gap between any two.
const VENDOR_GAP: f32 = 90.0;
const MARKET_GAP: f32 = 14.0;

fn vendor_barks(
    time: Res<Time>,
    hero: Query<&crate::player::Hero>,
    mut vendors: Query<(&GlobalTransform, &Visibility, &mut MarketVendor)>,
    mut speak: MessageWriter<crate::audio::director::Speak>,
    mut gap: Local<f32>,
) {
    let now = time.elapsed_secs();
    if now < *gap {
        return;
    }
    let Ok(hero) = hero.single() else { return };
    for (gt, vis, mut v) in &mut vendors {
        let p = gt.translation();
        if *vis == Visibility::Hidden || v.next > now || p.xz().distance(hero.pos) > BARK_DIST {
            continue;
        }
        speak.write(crate::audio::director::Speak::at(crate::audio::lines::Concept::Greeting, p));
        v.next = now + VENDOR_GAP;
        *gap = now + MARKET_GAP;
        return;
    }
}

/// Marks a market model root (the "already laid out" check).
#[derive(Component)]
pub struct MarketRoot;

/// A stall: kit model, world XZ, yaw (local +Z = the customer side), and where its vendor stands
/// along the counter (local x; local z is [`VENDOR_Z`]).
struct Stall {
    model: &'static str,
    pos: Vec2,
    yaw: f32,
    vendor_x: f32,
}

const PI: f32 = std::f32::consts::PI;
/// Vendors stand this far behind the stall's centre line (local −Z), clear of the counter.
const VENDOR_Z: f32 = -0.85;

/// North row faces the lane southward (+Z), south row faces it northward. The west lane runs
/// along z ≈ 0 (`castle_ground::LANES`), the stalls sit just off its trodden shoulder.
///
/// Castle v2 (spec §2): the market square sits just inside the WEST main gate, centred on
/// `castle::MARKET_CENTRE`; everything here is laid out relative to it.
const MC: Vec2 = crate::castle::MARKET_CENTRE;
const STALLS: [Stall; 4] = [
    Stall { model: "market_bread", pos: Vec2::new(MC.x + 1.6, MC.y - 2.9), yaw: 0.0, vendor_x: 0.35 },
    Stall { model: "market_pots", pos: Vec2::new(MC.x - 1.6, MC.y - 2.9), yaw: 0.0, vendor_x: -0.1 },
    Stall { model: "market_cloth", pos: Vec2::new(MC.x + 1.6, MC.y + 2.9), yaw: PI, vendor_x: -0.2 },
    Stall { model: "market_veg", pos: Vec2::new(MC.x - 1.6, MC.y + 2.9), yaw: PI, vendor_x: -0.3 },
];

/// Loose props: (model, world XZ, yaw, blocker radius).
const PROPS: [(&str, Vec2, f32, f32); 2] = [
    ("market_cart", Vec2::new(MC.x - 4.2, MC.y + 2.3), 2.6, 0.8),
    ("market_barrels", Vec2::new(MC.x, MC.y - 4.4), 0.3, 0.75),
];

/// Townsfolk pausing at a counter: (world XZ, facing yaw).
const SHOPPERS: [(Vec2, f32); 2] = [(Vec2::new(MC.x + 1.35, MC.y - 1.65), PI), (Vec2::new(MC.x - 1.85, MC.y + 1.65), 0.0)];

fn spawn_market(
    mut commands: Commands,
    mut meshes: ResMut<Assets<Mesh>>,
    mut creature_mats: ResMut<Assets<crate::creature::CreatureMaterial>>,
    existing: Query<(), With<MarketRoot>>,
    castle: Query<(), With<crate::castle::CastlePart>>,
) {
    if !existing.is_empty() || castle.is_empty() {
        return;
    }
    let Some(kit) = crate::realforest::get().filter(|k| k.has(STALLS[0].model)) else { return };
    let range = VisibilityRange { start_margin: 0.0..0.0, end_margin: 110.0..130.0, use_aabb: true };
    let ground = |p: Vec2| crate::worldmap::ground_at_world(p.x, p.y).unwrap_or(0.0);
    let mut seed = 0x6d61_726b_u32; // "mark"
    for s in &STALLS {
        let rot = Quat::from_rotation_y(s.yaw);
        let tf = Transform::from_xyz(s.pos.x, ground(s.pos) - 0.02, s.pos.y).with_rotation(rot);
        let Some(e) = kit.spawn_static_with(&mut commands, s.model, tf, range.clone()) else { continue };
        commands.entity(e).insert((MarketRoot, BiomeEntity));
        // Counter + awning posts: one box over the frame (the goods sit inside it).
        let c = s.pos + (rot * Vec3::new(0.0, 0.0, -0.04)).xz();
        crate::blockers::add_obb(c.x, c.y, 1.05, 0.55, s.yaw);
        let v = s.pos + (rot * Vec3::new(s.vendor_x, 0.0, VENDOR_Z)).xz();
        seed = seed.wrapping_mul(747_796_405).wrapping_add(2_891_336_453);
        let who = crate::villagers::spawn_scene_peasant(&mut commands, &mut meshes, &mut creature_mats, v, s.yaw, None, seed >> 8);
        commands.entity(who).insert(MarketVendor { next: 0.0 });
    }
    for (model, p, yaw, r) in PROPS {
        let tf = Transform::from_xyz(p.x, ground(p) - 0.02, p.y).with_rotation(Quat::from_rotation_y(yaw));
        if let Some(e) = kit.spawn_static_with(&mut commands, model, tf, range.clone()) {
            commands.entity(e).insert((MarketRoot, BiomeEntity));
            crate::blockers::add(p.x, p.y, r);
        }
    }
    for (p, yaw) in SHOPPERS {
        seed = seed.wrapping_mul(747_796_405).wrapping_add(2_891_336_453);
        crate::villagers::spawn_scene_peasant(&mut commands, &mut meshes, &mut creature_mats, p, yaw, None, seed >> 8);
    }
    info!("market: {} stalls, {} props, {} vendors + {} shoppers laid out", STALLS.len(), PROPS.len(), STALLS.len(), SHOPPERS.len());
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Stalls and their vendors stay off the west cart lane's trodden core and inside the walls.
    #[test]
    fn market_sits_beside_the_lane_inside_the_walls() {
        let (hx, hz) = crate::castle::courtyard_half();
        for s in &STALLS {
            let rot = Quat::from_rotation_y(s.yaw);
            let front = s.pos + (rot * Vec3::new(0.0, 0.0, 0.57)).xz();
            assert!(front.y.abs() > 1.9, "{} counter front {front} crowds the lane", s.model);
            assert!(s.pos.x.abs() < hx - 2.0 && s.pos.y.abs() < hz - 2.0, "{} outside the yard", s.model);
            let v = s.pos + (rot * Vec3::new(s.vendor_x, 0.0, VENDOR_Z)).xz();
            assert!(v.y.abs() > s.pos.y.abs(), "{} vendor isn't behind the counter", s.model);
        }
    }
}
