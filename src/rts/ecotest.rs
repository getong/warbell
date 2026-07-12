//! `FOREST_RTS_ECOTEST=<secs>` — headless-ish skirmish **economy + training smoke test**. Boots the
//! real game in skirmish, auto-places a player Sawmill beside the nearest wood grove, a Farm beside
//! the base, and a Barracks; once the barracks stands it issues a couple of `TrainOrder`s. Then it
//! watches the live sim:
//!
//! - **FAIL fast** if any bonded worker stops moving for [`STUCK_SECS`] while not gathering/tending
//!   (a stuck mover / unreachable goal — exactly the regression the test exists to catch);
//! - at the deadline, **PASS** iff the player bank gathered BOTH wood and food (haul loop works) AND
//!   at least one **soldier** was trained (the "training starves when the economy bonds every idle
//!   worker" regression the RC playtest surfaced — see `units::consume_train_orders`).
//!
//! Prints one `RTS_ECOTEST OK|FAIL ...` line and exits with the matching process code, so a script
//! (or an agent) can run `FOREST_RTS=1 FOREST_RTS_ECOTEST=90 cargo run` and check `$LASTEXITCODE`.
//! Pure staging/verification — registers nothing unless the env var is set.

use std::collections::HashMap;

use bevy::app::AppExit;
use bevy::prelude::*;

use crate::game_state::{AppState, Modal};
use crate::rts::command::MoveTo;
use crate::rts::workers::Assigned;
use crate::rts::{
    base_of, build, in_skirmish, BuildingKind, Deposit, DepositKind, RtsBanks, RtsBuilding,
    RtsUnit, Side, TrainOrder, TrainQueue, UnitKind,
};

/// A worker carrying `MoveTo` that hasn't displaced for this long is stuck (gather/tend phases
/// stand still but hold no `MoveTo`, so they don't trip this).
const STUCK_SECS: f32 = 30.0;
/// Movement below this (world units) between samples counts as "not moving".
const MOVE_EPS: f32 = 0.25;

#[derive(Resource)]
struct EcoTest {
    /// Sim-seconds to run after staging before the verdict.
    duration: f32,
    staged: bool,
    /// The staged barracks (train orders fire once it's `built`); `None` until placement succeeds.
    barracks: Option<Entity>,
    /// Whether the training order has been issued (once the barracks stands).
    trained: bool,
    /// Elapsed at staging + the bank snapshot taken right AFTER paying for the staged buildings.
    started: f32,
    base_wood: f64,
    base_food: f64,
    /// Per-worker (last position, elapsed at last real displacement) for the stuck watchdog.
    track: HashMap<Entity, (Vec2, f32)>,
}

pub struct RtsEcoTestPlugin;

impl Plugin for RtsEcoTestPlugin {
    fn build(&self, app: &mut App) {
        let Ok(v) = std::env::var("FOREST_RTS_ECOTEST") else { return };
        let duration = v.parse::<f32>().unwrap_or(90.0);
        app.insert_resource(EcoTest {
            duration,
            staged: false,
            barracks: None,
            trained: false,
            started: 0.0,
            base_wood: 0.0,
            base_food: 0.0,
            track: HashMap::new(),
        })
        .add_systems(
            Update,
            ecotest_drive
                .run_if(in_skirmish)
                .run_if(in_state(AppState::Playing))
                .run_if(in_state(Modal::None)),
        );
    }
}

// Spot search lives in `build::find_spot` (shared with the RC bridge's auto-spot build op).

#[allow(clippy::too_many_arguments, clippy::type_complexity)]
fn ecotest_drive(
    time: Res<Time>,
    mut commands: Commands,
    mut meshes: ResMut<Assets<Mesh>>,
    mut creature_mats: ResMut<Assets<crate::creature::CreatureMaterial>>,
    mut banks: ResMut<RtsBanks>,
    mut pop: ResMut<crate::rts::RtsPop>,
    mut test: ResMut<EcoTest>,
    assets: Option<Res<build::RtsBuildAssets>>,
    halls: Query<(&RtsBuilding, &Side)>,
    barracks_q: Query<(Entity, &RtsBuilding, &Side), With<TrainQueue>>,
    deposits: Query<(&Deposit, &Transform)>,
    workers: Query<(Entity, &RtsUnit, &Side, &Transform, Has<Assigned>, Has<MoveTo>)>,
    mut trains: MessageWriter<TrainOrder>,
    mut exit: MessageWriter<AppExit>,
) {
    let now = time.elapsed_secs();

    // ── stage once the player's hall (and the build assets + deposits) exist ──
    if !test.staged {
        let Some(assets) = assets.as_ref() else { return };
        let hall_up = halls
            .iter()
            .any(|(b, s)| b.kind == BuildingKind::TownHall && b.built && *s == Side::Player);
        let dep_pos: Vec<Vec2> =
            deposits.iter().map(|(_, t)| Vec2::new(t.translation.x, t.translation.z)).collect();
        if !hall_up || dep_pos.is_empty() {
            return;
        }
        let base = base_of(Side::Player);
        // Sawmill next to the wood grove nearest the base (the intended play pattern).
        let grove = deposits
            .iter()
            .filter(|(d, _)| d.kind == DepositKind::Wood && d.remaining > 0.0)
            .map(|(_, t)| Vec2::new(t.translation.x, t.translation.z))
            .min_by(|a, b| {
                a.distance_squared(base).partial_cmp(&b.distance_squared(base)).unwrap_or(std::cmp::Ordering::Equal)
            });
        let Some(grove) = grove else { return };
        // Search the three buildings around DIFFERENT centres so their footprints can't collide
        // (find_spot returns the same first-valid tile if given the same centre).
        let mill = build::find_spot(BuildingKind::Sawmill, Side::Player, grove, &dep_pos);
        let farm = build::find_spot(BuildingKind::Farm, Side::Player, base + Vec2::new(-6.0, -2.0), &dep_pos);
        let barr = build::find_spot(BuildingKind::Barracks, Side::Player, base + Vec2::new(6.0, 4.0), &dep_pos);
        let (Some(mill), Some(farm), Some(barr)) = (mill, farm, barr) else {
            println!("RTS_ECOTEST FAIL: no valid staging spot (mill/farm/barracks)");
            exit.write(AppExit::error());
            return;
        };
        // Fund the barracks (wood40+stone20) on top of the starting bank so staging can't fail on cost.
        banks.side_mut(Side::Player).stone += 50.0;
        banks.side_mut(Side::Player).wood += 50.0;
        let ok_m = build::try_place(&mut commands, assets, &mut banks, &dep_pos, BuildingKind::Sawmill, Side::Player, mill, 0);
        let ok_f = build::try_place(&mut commands, assets, &mut banks, &dep_pos, BuildingKind::Farm, Side::Player, farm, 0);
        let ok_b = build::try_place(&mut commands, assets, &mut banks, &dep_pos, BuildingKind::Barracks, Side::Player, barr, 0);
        if !ok_m || !ok_f || !ok_b {
            println!("RTS_ECOTEST FAIL: try_place refused (mill={ok_m} farm={ok_f} barracks={ok_b})");
            exit.write(AppExit::error());
            return;
        }
        // Gold for the trainees (each Swordsman = wood10+gold15).
        banks.side_mut(Side::Player).gold += 60.0;
        // Seed a realistic worker pool: 3 starting workers can't staff a sawmill + farm AND give up
        // two to conscription (that starved food in an earlier revision). Add 5 more so the economy
        // survives training — mirrors a real mid-game town, not the bare opening.
        for k in 0..5u32 {
            let a = k as f32 / 5.0 * std::f32::consts::TAU;
            let wp = base + Vec2::new(a.cos(), a.sin()) * 3.0;
            crate::rts::workers::spawn_worker_body(&mut commands, &mut meshes, &mut creature_mats, Side::Player, wp, 0xEC0 ^ k);
            pop.0[Side::Player.ix()].count += 1;
        }
        // Baseline AFTER paying the costs — any later increase is hauled income.
        test.base_wood = banks.side(Side::Player).wood;
        test.base_food = banks.side(Side::Player).food;
        test.started = now;
        test.staged = true;
        println!("RTS_ECOTEST staged: sawmill@{mill:?} farm@{farm:?} barracks@{barr:?}, running {}s", test.duration);
        return;
    }

    // ── issue training once the barracks stands (verifies the conscription path) ──
    if !test.trained {
        if let Some((be, _, _)) = barracks_q.iter().find(|(_, b, s)| {
            b.kind == BuildingKind::Barracks && b.built && **s == Side::Player
        }) {
            // Two swordsmen — enough that at least one must convert even if the economy has bonded
            // every idle worker (the fixed path conscripts a bonded worker as a fallback).
            trains.write(TrainOrder { building: be, kind: UnitKind::Swordsman });
            trains.write(TrainOrder { building: be, kind: UnitKind::Swordsman });
            test.barracks = Some(be);
            test.trained = true;
            println!("RTS_ECOTEST barracks built — issued 2 Swordsman train orders");
        }
    }

    // ── stuck watchdog: a MoveTo-carrying player worker must displace within STUCK_SECS ──
    for (e, u, side, tf, assigned, moving) in &workers {
        if *side != Side::Player || u.kind != UnitKind::Worker || !assigned {
            continue;
        }
        let pos = Vec2::new(tf.translation.x, tf.translation.z);
        let entry = test.track.entry(e).or_insert((pos, now));
        if pos.distance(entry.0) > MOVE_EPS {
            *entry = (pos, now);
        } else if moving && now - entry.1 > STUCK_SECS {
            println!("RTS_ECOTEST FAIL: worker {e} stuck at {pos:?} for {STUCK_SECS}s (MoveTo held)");
            exit.write(AppExit::error());
            return;
        }
    }

    // ── verdict at the deadline ──
    if now - test.started >= test.duration {
        let wood = banks.side(Side::Player).wood - test.base_wood;
        let food = banks.side(Side::Player).food - test.base_food;
        // Soldiers trained = the whole point of the training-regression gate.
        let soldiers = workers
            .iter()
            .filter(|(_, u, s, _, _, _)| {
                **s == Side::Player && matches!(u.kind, UnitKind::Swordsman | UnitKind::Archer)
            })
            .count();
        // NB food also drains at FOOD_DRAIN per living unit — a positive delta means the farmer
        // out-gathered the upkeep, which is the intended healthy-economy bar.
        if wood > 0.0 && food > 0.0 && soldiers >= 1 {
            println!("RTS_ECOTEST OK wood=+{wood:.0} food=+{food:.0} soldiers={soldiers}");
            exit.write(AppExit::Success);
        } else {
            println!(
                "RTS_ECOTEST FAIL wood=+{wood:.0} food=+{food:.0} soldiers={soldiers} \
                 (need wood>0, food>0, soldiers>=1)"
            );
            exit.write(AppExit::error());
        }
    }
}
