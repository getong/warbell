//! **The Salt Caravan** (living-island spec 2026-10-13 §2 E.16) — Pasha's everyday trade. Every
//! other day, all game long, two pack mules, two merchants in desert cloaks and a guard come down
//! the road from the desert fort, set out a rug of salt, jars and sacks beside the King's Road
//! outside the west gate, trade until late afternoon (**[E] Trade** → the shop as
//! `ShopVendor::Caravan`) and walk home before dark.
//!
//! State: none saved — the day's trip is transient (a load restores Prep at dawn and the next
//! caravan day starts a fresh trip).
//! Models: `caravan.glb` (`tools/blender_forest/caravan.py`): the mule packs + the trade spread.

use bevy::prelude::*;

use crate::biome::BiomeEntity;
use crate::meadow::{day_index, face_body, kit_piece, sky_t};
use crate::quadruped::{QuadDrive, QuadJoint, QuadPart, QuadSpecies};

/// Candidate market stops beside the King's Road outside the W gate (first clear one wins).
const STOPS: [Vec2; 5] = [
    Vec2::new(-35.0, -6.8),
    Vec2::new(-37.5, -8.0),
    Vec2::new(-33.5, -9.0),
    Vec2::new(-40.0, -7.5),
    Vec2::new(-36.0, 8.5),
];
/// Path length (u) of the visible approach the caravan walks (from the fort road to the stop).
const APPROACH: f32 = 120.0;
const SPEED: f32 = 1.75;
const GAP: f32 = 2.4;

pub fn stop() -> Vec2 {
    STOPS
        .into_iter()
        .find(|p| crate::castle::plot_clear(p.x, p.y, 2.0) && !crate::castle::village_keep_clear(p.x, p.y, 2.2) && !crate::town::near_build_plot(p.x, p.y))
        .unwrap_or(STOPS[0])
}

pub fn planned_footprints() -> Vec<(Vec2, f32)> {
    vec![(STOPS[0], 4.0)]
}

pub struct CaravanPlugin;

impl Plugin for CaravanPlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<Trip>()
            .add_systems(
                Update,
                (caravan_director, caravan_move, caravan_trade)
                    .chain()
                    .run_if(in_state(crate::game_state::Modal::None))
                    .run_if(crate::rts::in_campaign),
            )
            .add_systems(Update, (attach_packs, open_trade).run_if(crate::rts::in_campaign));
    }
}

#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
enum Leg {
    #[default]
    Idle,
    Inbound,
    Trading,
    Outbound,
}

/// Today's trip (transient).
#[derive(Resource, Default)]
struct Trip {
    day: Option<i64>,
    leg: Leg,
    route: Vec<Vec2>,
    cum: Vec<f32>,
    s: f32,
    spread: Option<Entity>,
}

impl Trip {
    fn len(&self) -> f32 {
        self.cum.last().copied().unwrap_or(0.0)
    }
    /// Point + heading at arc length `s` along the route.
    fn sample(&self, s: f32) -> (Vec2, Vec2) {
        let s = s.clamp(0.0, self.len());
        let i = self.cum.partition_point(|&c| c < s).clamp(1, self.route.len() - 1);
        let (a, b) = (self.route[i - 1], self.route[i]);
        let seg = (self.cum[i] - self.cum[i - 1]).max(1e-4);
        let f = ((s - self.cum[i - 1]) / seg).clamp(0.0, 1.0);
        (a.lerp(b, f), (b - a).normalize_or(Vec2::Y))
    }
}

#[derive(Component)]
struct Member {
    slot: usize,
}
#[derive(Clone, Copy, PartialEq, Eq)]
enum Role {
    Mule,
    Merchant,
    Guard,
}
#[derive(Component)]
struct MuleBody {
    pos: Vec2,
    facing: f32,
    packed: bool,
}
#[derive(Component)]
struct TradeMerchant;

/// Fort gate → stop, A*-routed (roads where the grid allows), trimmed to the last [`APPROACH`] u.
fn plan_route(stop: Vec2) -> Vec<Vec2> {
    let fort = crate::rival::RIVAL_CENTRE;
    let from = fort + (Vec2::ZERO - fort).normalize_or_zero() * 36.0;
    let mut path = crate::navgrid::path_to_budget(from, stop, 400_000);
    if path.len() < 2 {
        path = (0..=40).map(|k| from.lerp(stop, k as f32 / 40.0)).collect();
    }
    if path.last().is_some_and(|p| p.distance(stop) > 0.5) {
        path.push(stop);
    }
    // Keep the tail: the visible walk in.
    let mut acc = 0.0;
    let mut start = 0;
    for i in (1..path.len()).rev() {
        acc += path[i].distance(path[i - 1]);
        if acc >= APPROACH {
            start = i - 1;
            break;
        }
    }
    path.split_off(start)
}

#[allow(clippy::too_many_arguments)]
fn caravan_director(
    mut commands: Commands,
    _time: Res<Time>,
    clock: Option<Res<crate::scene::SkyClock>>,
    siege: Option<Res<crate::siege::Siege>>,
    ready: Res<crate::biome::WorldReady>,
    mut trip: ResMut<Trip>,
    mut meshes: ResMut<Assets<Mesh>>,
    mut cmats: ResMut<Assets<crate::creature::CreatureMaterial>>,
    members: Query<Entity, With<Member>>,
) {
    let Some(siege) = siege else { return };
    if !ready.0 || crate::realforest::get().is_none() {
        return;
    }
    let t = sky_t(clock.as_deref());
    let day = day_index(&siege);
    let prep = siege.phase == crate::siege::GamePhase::Prep;
    let sweep = |commands: &mut Commands, trip: &mut Trip| {
        for e in &members {
            commands.entity(e).try_despawn();
        }
        if let Some(e) = trip.spread.take() {
            commands.entity(e).try_despawn();
        }
        trip.leg = Leg::Idle;
    };
    // Night (or a load / new run rewinding the day): the road empties.
    if !prep || (trip.leg != Leg::Idle && trip.day != Some(day)) {
        if trip.leg != Leg::Idle || !members.is_empty() {
            sweep(&mut commands, &mut trip);
        }
        return;
    }
    match trip.leg {
        Leg::Idle => {
            // Every other day (the first morning included), all game long. A day entered late (a
            // load at noon) finds the caravan already at its stop.
            if day % 2 != 0 || !(0.04..0.36).contains(&t) || trip.day == Some(day) {
                return;
            }
            trip.day = Some(day);
            let st = stop();
            trip.route = plan_route(st);
            trip.cum = std::iter::once(0.0)
                .chain(trip.route.windows(2).scan(0.0, |acc, w| {
                    *acc += w[0].distance(w[1]);
                    Some(*acc)
                }))
                .collect();
            trip.s = if t < 0.2 { 0.0 } else { trip.len() };
            trip.leg = Leg::Inbound;
            // Two mules, two merchants, a guard: mule · merchant · mule · merchant · guard at the rear.
            let roles = [Role::Merchant, Role::Mule, Role::Merchant, Role::Mule, Role::Guard];
            let mat = crate::creature::make_creature_material(&mut cmats);
            for (slot, role) in roles.into_iter().enumerate() {
                let (p, _) = trip.sample(trip.s - slot as f32 * GAP);
                let seed = 0xC0A1 + slot as u32 * 13 + day as u32 * 101;
                let e = match role {
                    Role::Merchant => crate::villagers::spawn_desert_traveller(&mut commands, &mut meshes, &mut cmats, p, seed),
                    Role::Guard => crate::villagers::spawn_rival_soldier(&mut commands, &mut meshes, &mut cmats, p, p, seed),
                    Role::Mule => {
                        let y = crate::worldmap::ground_at_world(p.x, p.y).unwrap_or(0.0);
                        let root = commands
                            .spawn((
                                Transform::from_xyz(p.x, y, p.y).with_scale(Vec3::splat(1.2)),
                                Visibility::Visible,
                                QuadDrive::new(QuadSpecies::Horse),
                                MuleBody { pos: p, facing: 0.0, packed: false },
                                BiomeEntity,
                            ))
                            .id();
                        let h = crate::quadruped::quad_meshes(QuadSpecies::Horse).upload(&mut meshes);
                        crate::quadruped::spawn_quad(&mut commands, root, &mat, QuadSpecies::Horse, h);
                        root
                    }
                };
                commands.entity(e).insert(Member { slot });
                if role != Role::Mule {
                    commands.entity(e).insert(crate::scenes::SceneActor);
                }
                if slot == 0 {
                    commands.entity(e).insert(TradeMerchant);
                }
            }
        }
        Leg::Inbound => {
            if trip.s >= trip.len() - 0.3 {
                trip.leg = Leg::Trading;
                let st = trip.route.last().copied().unwrap_or(stop());
                let (_, d) = trip.sample(trip.len());
                let side = Vec2::new(-d.y, d.x);
                let c = st + side * 2.2;
                trip.spread = kit_piece(&mut commands, "caravan_goods", c.x, c.y, d.x.atan2(d.y), 0.0);
            }
        }
        Leg::Trading => {
            if t >= 0.42 {
                trip.leg = Leg::Outbound;
                if let Some(e) = trip.spread.take() {
                    commands.entity(e).try_despawn();
                }
            }
        }
        Leg::Outbound => {
            if trip.s <= 0.2 {
                sweep(&mut commands, &mut trip); // `trip.day` stays: done for today
            }
        }
    }
}

#[allow(clippy::type_complexity)]
fn caravan_move(
    time: Res<Time>,
    mut trip: ResMut<Trip>,
    mut people: Query<(&Member, &mut crate::villagers::Villager, &mut Transform), Without<MuleBody>>,
    mut mules: Query<(&Member, &mut MuleBody, &mut QuadDrive, &mut Transform), Without<crate::villagers::Villager>>,
) {
    if trip.leg == Leg::Idle || trip.route.len() < 2 {
        return;
    }
    let dt = time.delta_secs().min(0.05);
    let moving = matches!(trip.leg, Leg::Inbound | Leg::Outbound);
    match trip.leg {
        Leg::Inbound => trip.s = (trip.s + SPEED * dt).min(trip.len()),
        Leg::Outbound => trip.s = (trip.s - SPEED * dt).max(0.0),
        _ => {}
    }
    let out = trip.leg == Leg::Outbound;
    let st = trip.route.last().copied().unwrap_or(Vec2::ZERO);
    let (_, end_dir) = trip.sample(trip.len());
    let side = Vec2::new(-end_dir.y, end_dir.x);
    // Where each slot stands while trading: merchants at the rug, mules tethered behind, the guard
    // watching the road.
    let trade_spot = |slot: usize| -> (Vec2, Vec2) {
        let rug = st + side * 2.2;
        match slot {
            0 => (rug + side * 1.3, st),
            1 => (st - end_dir * 3.2 + side * 4.4, st - end_dir * 3.2),
            2 => (rug - end_dir * 1.6 + side * 0.4, rug),
            3 => (st - end_dir * 5.4 + side * 4.0, st - end_dir * 5.4),
            _ => (st + end_dir * 2.0 - side * 0.8, st + end_dir * 8.0),
        }
    };
    let place = |slot: usize, trip: &Trip| -> (Vec2, Vec2) {
        let s = if out { trip.s + slot as f32 * GAP } else { trip.s - slot as f32 * GAP };
        let (p, d) = trip.sample(s);
        // Walk on the right of the road centreline.
        (p + Vec2::new(-d.y, d.x) * 0.9, if out { -d } else { d })
    };
    for (m, mut v, mut tf) in &mut people {
        if trip.leg == Leg::Trading {
            let (spot, look) = trade_spot(m.slot);
            if !crate::meadow::walk_body(&mut v, &mut tf, spot, 1.2, 0.25, dt) {
                continue;
            }
            face_body(&mut v, &mut tf, look, dt);
            continue;
        }
        let (p, d) = place(m.slot, &trip);
        if moving {
            let step = p - v.pos;
            v.pos = p;
            v.moving = step.length() > 1e-3 || moving;
            v.facing += crate::steer::wrap_pi(d.x.atan2(d.y) - v.facing) * (dt * 5.0).min(1.0);
        } else {
            v.moving = false;
        }
        let y = crate::worldmap::ground_at_world(v.pos.x, v.pos.y).unwrap_or(tf.translation.y);
        tf.translation = Vec3::new(v.pos.x, y, v.pos.y);
        tf.rotation = Quat::from_rotation_y(v.facing);
    }
    for (m, mut mb, mut drive, mut tf) in &mut mules {
        let (goal, dir) = if trip.leg == Leg::Trading {
            let (spot, look) = trade_spot(m.slot);
            (spot, (look - spot).normalize_or_zero())
        } else {
            place(m.slot, &trip)
        };
        let to = goal - mb.pos;
        let walking = to.length() > 0.08;
        if walking {
            let step = if trip.leg == Leg::Trading { to.normalize() * (1.2 * dt).min(to.length()) } else { to };
            mb.pos += step;
            let want = if trip.leg == Leg::Trading { to.x.atan2(to.y) } else { dir.x.atan2(dir.y) };
            mb.facing += crate::steer::wrap_pi(want - mb.facing) * (dt * 4.0).min(1.0);
        } else if trip.leg == Leg::Trading {
            mb.facing += crate::steer::wrap_pi(dir.x.atan2(dir.y) - mb.facing) * (dt * 2.0).min(1.0);
        }
        let m_amt = if walking && (moving || trip.leg == Leg::Trading) { 1.0 } else { 0.0 };
        drive.moving_amt += (m_amt - drive.moving_amt) * (dt * 5.0).min(1.0);
        drive.phase += dt * 6.0 * drive.moving_amt;
        let y = crate::worldmap::ground_at_world(mb.pos.x, mb.pos.y).unwrap_or(tf.translation.y);
        tf.translation = Vec3::new(mb.pos.x, y, mb.pos.y);
        tf.rotation = Quat::from_rotation_y(mb.facing);
    }
}

/// The lead merchant offers **[E] Trade** while the rug is out.
fn caravan_trade(mut commands: Commands, trip: Res<Trip>, q: Query<(Entity, Has<crate::interaction::Interactable>), With<TradeMerchant>>) {
    for (e, has) in &q {
        let open = trip.leg == Leg::Trading;
        if open && !has {
            commands.entity(e).try_insert(crate::interaction::Interactable::new("Trade", 3.0));
        } else if !open && has {
            commands.entity(e).remove::<crate::interaction::Interactable>();
        }
    }
}

fn open_trade(
    mut ev: MessageReader<crate::interaction::Interacted>,
    q: Query<(), With<TradeMerchant>>,
    mut active: ResMut<crate::economy::ActiveVendor>,
    mut modal: ResMut<NextState<crate::game_state::Modal>>,
) {
    for crate::interaction::Interacted(e) in ev.read() {
        if q.contains(*e) {
            crate::economy::open_vendor(tileworld_core::shop_catalog::ShopVendor::Caravan, &mut active, &mut modal);
        }
    }
}

/// Hang the pack load on each mule's spine joint once its skeleton exists.
fn attach_packs(mut commands: Commands, mut mules: Query<(Entity, &mut MuleBody)>, parts: Query<(Entity, &QuadPart)>) {
    let Some(kit) = crate::realforest::get() else { return };
    for (root, mut mb) in &mut mules {
        if mb.packed {
            continue;
        }
        let Some((spine, _)) = parts.iter().find(|(_, p)| p.root == root && p.joint == QuadJoint::Spine) else { continue };
        if let Some(pack) = kit.spawn_static(&mut commands, "caravan_pack", Transform::IDENTITY) {
            commands.entity(spine).add_child(pack);
        }
        mb.packed = true;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn market_stop_is_clear() {
        let s = stop();
        assert!(crate::castle::plot_clear(s.x, s.y, 2.0), "stop {s} hits a plot");
        assert!(!crate::castle::village_keep_clear(s.x, s.y, 2.2), "stop {s} on village ground");
        assert!(!crate::town::near_build_plot(s.x, s.y));
        assert!(crate::castle::outside_dist(s.x, s.y) > 3.0, "stop {s} inside the walls");
    }

    #[test]
    fn trip_sampling_walks_the_route() {
        let mut t = Trip { route: vec![Vec2::ZERO, Vec2::new(10.0, 0.0), Vec2::new(10.0, 10.0)], ..default() };
        t.cum = vec![0.0, 10.0, 20.0];
        assert_eq!(t.sample(5.0).0, Vec2::new(5.0, 0.0));
        assert_eq!(t.sample(15.0).0, Vec2::new(10.0, 5.0));
        assert_eq!(t.sample(99.0).0, Vec2::new(10.0, 10.0));
        assert_eq!(t.sample(15.0).1, Vec2::Y);
    }
}
