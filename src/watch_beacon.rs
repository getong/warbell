//! **South Watch Beacon** (living-island spec 2026-10-13 §2 D.15) — a fire basket on a lashed
//! tripod atop an earth mound beside the south track. At dusk a guard climbs the ladder and lights
//! it (seen from the courtyard); at dawn it is let burn out.
//!
//! **Function.** On **Flank** nights the guard stands on the mound and waves a torch toward the
//! side the flankers come from, and the compass carries a beacon-orange marker on that bearing
//! ([`BeaconSignal`] — rendered by this module's own overlay on the compass strip, no edit to
//! `compass.rs`). On **Arson** nights the beacon is the first fire to die. Shown, never told.
//!
//! Model: `meadow_kit.glb` (`beacon_tripod`); flame = `flame_fx` cards + a fire light.

use std::f32::consts::{PI, TAU};

use bevy::prelude::*;

use crate::biome::BiomeEntity;
use crate::meadow::{face_body, kit_piece, sky_t, walk_body};

/// Wanted spot on the south track; the actual site is the first clear candidate (off the road).
const CANDIDATES: [Vec2; 5] = [
    Vec2::new(6.0, 58.0),
    Vec2::new(-6.0, 58.5),
    Vec2::new(7.5, 55.0),
    Vec2::new(-7.5, 55.5),
    Vec2::new(5.0, 62.0),
];
/// Basket fire height above the mound base (meadow_kit.py `BASKET_Y` + the billets).
const FIRE_Y: f32 = 3.42;
/// The ladder (model local): foot and top.
const LADDER_FOOT: Vec3 = Vec3::new(0.1, 0.25, 1.95);
const LADDER_TOP: Vec3 = Vec3::new(0.05, 2.75, 0.62);

/// The beacon site (first clear candidate off the road).
pub fn site() -> Vec2 {
    CANDIDATES
        .into_iter()
        .find(|c| !crate::roads::near_road(c.x, c.y, 3.0) && crate::worldmap::ground_at_world(c.x, c.y).is_some())
        .unwrap_or(CANDIDATES[0])
}

pub fn planned_footprints() -> Vec<(Vec2, f32)> {
    vec![(CANDIDATES[0], 3.5), (CANDIDATES[1], 3.5)]
}

/// Worn ground: a footpath from the road to the ladder foot.
/// `s` is [`site`], resolved once by the mask pass.
pub fn ground_wear_at(s: Vec2, wx: f32, wz: f32) -> Option<(f32, f32, f32)> {
    let p = Vec2::new(wx, wz);
    if p.distance(s) > 6.0 {
        return None;
    }
    let foot = s + Vec2::new(0.0, 2.3);
    let road = Vec2::new(0.0, s.y + 2.5);
    let ab = road - foot;
    let t = ((p - foot).dot(ab) / ab.length_squared()).clamp(0.0, 1.0);
    let d = p.distance(foot + ab * t) + (wx * 2.1).sin() * 0.15;
    let path = (1.0 - ((d - 0.4) / 0.7).clamp(0.0, 1.0)) * 0.6;
    (path > 0.01).then_some((path, path, 0.0))
}

/// Where the flank is coming from tonight (world direction from the beacon), if the beacon guard
/// is signalling. Read by the overlay below (and free for `compass.rs` to read later).
#[derive(Resource, Default)]
pub struct BeaconSignal {
    pub dir: Option<Vec2>,
}

pub struct WatchBeaconPlugin;

impl Plugin for WatchBeaconPlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<BeaconSignal>()
            .add_systems(Startup, setup_overlay)
            .add_systems(Update, spawn_beacon.run_if(crate::rts::in_campaign))
            .add_systems(
                Update,
                (beacon_keeper, flank_signal).chain().run_if(in_state(crate::game_state::Modal::None)).run_if(crate::rts::in_campaign),
            )
            .add_systems(Update, update_overlay.run_if(crate::rts::in_campaign));
    }
}

#[derive(Component)]
struct BeaconSite {
    at: Vec2,
    base_y: f32,
}
#[derive(Component)]
struct BeaconFire;
#[derive(Component)]
struct TorchFlame;
#[derive(Component)]
struct Keeper {
    state: u8, // 0 day watch · 1 to ladder · 2 up · 3 lighting · 4 down · 5 night watch · 6 flank signal
    t: f32,
    lit_day: i64,
}

fn spawn_beacon(
    mut commands: Commands,
    ready: Res<crate::biome::WorldReady>,
    site_q: Query<(), With<BeaconSite>>,
    mut meshes: ResMut<Assets<Mesh>>,
    mut cmats: ResMut<Assets<crate::creature::CreatureMaterial>>,
) {
    if !ready.0 || !site_q.is_empty() || crate::realforest::get().is_none() {
        return;
    }
    let at = site();
    let base_y = crate::worldmap::ground_at_world(at.x, at.y).unwrap_or(0.0) - 0.05;
    let Some(e) = kit_piece(&mut commands, "beacon_tripod", at.x, at.y, 0.0, 0.05) else {
        commands.spawn((BeaconSite { at, base_y }, BiomeEntity, Transform::default()));
        return;
    };
    commands.entity(e).insert(BeaconSite { at, base_y });
    crate::blockers::add_obb(at.x, at.y, 1.3, 1.3, 0.0);
    // The fire: hidden until lit.
    commands.spawn((
        crate::flame_fx::flame_bundle(Vec3::new(at.x, base_y + FIRE_Y, at.y), 1.5, 0.4),
        crate::firelight::campfire_light(0.4),
        BeaconFire,
        Visibility::Hidden,
        BiomeEntity,
    ));
    // The signal torch (shown on Flank nights, bobbing over the keeper's head).
    commands.spawn((crate::flame_fx::flame_bundle(Vec3::new(at.x, base_y + 2.0, at.y), 0.45, 1.3), TorchFlame, Visibility::Hidden, BiomeEntity));
    let post = at + Vec2::new(0.9, 2.6);
    let g = crate::villagers::spawn_rts_militia(&mut commands, &mut meshes, &mut cmats, false, post, 0xBEAC);
    commands.entity(g).insert((crate::scenes::SceneActor, Keeper { state: 0, t: 0.0, lit_day: -1 }));
}

fn mound_y(site: &BeaconSite, p: Vec2) -> f32 {
    let r = (p.distance(site.at) / 1.95).min(1.0);
    site.base_y + 0.75 * (1.0 - r * r).max(0.0).powf(0.7)
}

#[allow(clippy::type_complexity)]
fn beacon_keeper(
    time: Res<Time>,
    clock: Option<Res<crate::scene::SkyClock>>,
    siege: Option<Res<crate::siege::Siege>>,
    signal: Res<BeaconSignal>,
    site_q: Query<&BeaconSite>,
    mut keeper: Query<(&mut Keeper, &mut crate::villagers::Villager, &mut Transform), (Without<BeaconFire>, Without<TorchFlame>)>,
    mut fire: Query<&mut Visibility, (With<BeaconFire>, Without<TorchFlame>)>,
    mut torch: Query<(&mut Transform, &mut Visibility), (With<TorchFlame>, Without<BeaconFire>, Without<Keeper>)>,
    mut wave_t: Local<f32>,
) {
    let (Some(siege), Ok(site)) = (siege, site_q.single()) else { return };
    let dt = time.delta_secs().min(0.05);
    let now = time.elapsed_secs();
    let t = sky_t(clock.as_deref());
    let wave = siege.phase == crate::siege::GamePhase::Wave;
    *wave_t = if wave { *wave_t + dt } else { 0.0 };
    let day = crate::meadow::day_index(&siege);
    let dusk = wave || t >= 0.44 || t < 0.02;
    let arson = wave && tileworld_core::threat::threat_for(siege.wave_index.max(0) as usize).kind == tileworld_core::threat::ThreatKind::Arson;
    let local = |v: Vec3| Vec3::new(site.at.x + v.x, site.base_y + v.y, site.at.y + v.z);
    let Ok((mut k, mut v, mut tf)) = keeper.single_mut() else { return };
    let foot = local(LADDER_FOOT);
    let top = local(LADDER_TOP);
    let foot2 = Vec2::new(foot.x, foot.z) + Vec2::new(0.0, 0.5);
    let post = site.at + Vec2::new(0.9, 2.6);
    let mut lit = k.lit_day == day && dusk;
    // Arson nights: the beacon is the first fire to go out.
    if arson && *wave_t > 25.0 {
        lit = false;
    }
    match k.state {
        0 => {
            if walk_body(&mut v, &mut tf, post, 1.2, 0.3, dt) {
                face_body(&mut v, &mut tf, site.at + Vec2::new(0.0, 12.0), dt);
            }
            if dusk && k.lit_day != day {
                k.state = 1;
            }
        }
        1 => {
            if walk_body(&mut v, &mut tf, foot2, 1.4, 0.15, dt) {
                k.state = 2;
                k.t = 0.0;
            }
        }
        2 | 4 => {
            // On the ladder: facing it, climbing (the gait clip reads as hand-over-hand steps).
            k.t += dt / 2.6;
            let f = if k.state == 2 { k.t.min(1.0) } else { 1.0 - k.t.min(1.0) };
            let p = Vec3::new(foot2.x, foot.y, foot2.y).lerp(top + Vec3::new(0.0, -0.9, 0.35), f);
            v.pos = Vec2::new(p.x, p.z);
            v.facing = PI; // facing -Z, into the ladder
            v.moving = true;
            tf.translation = p;
            tf.rotation = Quat::from_rotation_y(v.facing);
            if k.t >= 1.0 {
                k.t = 0.0;
                k.state = if k.state == 2 { 3 } else { 5 };
            }
        }
        3 => {
            v.moving = false;
            k.t += dt;
            if k.t > 0.3 && k.t - dt <= 0.3 {
                v.atk_anim = now; // reach up with the torch
            }
            if k.t > 1.0 {
                k.lit_day = day;
                k.state = 4;
                k.t = 0.0;
            }
        }
        5 => {
            if let Some(dir) = signal.dir {
                // Up onto the mound, facing the flank, waving the torch.
                let stand = site.at + Vec2::new(dir.x.signum() * 1.0, 0.7);
                let to = stand - v.pos;
                if to.length() > 0.2 {
                    v.facing += crate::steer::wrap_pi(to.x.atan2(to.y) - v.facing) * (6.0 * dt).min(1.0);
                    v.pos += to.normalize() * (1.4 * dt).min(to.length());
                    v.moving = true;
                } else {
                    v.facing += crate::steer::wrap_pi(dir.x.atan2(dir.y) - v.facing) * (5.0 * dt).min(1.0);
                    v.moving = false;
                }
                tf.translation = Vec3::new(v.pos.x, mound_y(site, v.pos), v.pos.y);
                tf.rotation = Quat::from_rotation_y(v.facing);
            } else if walk_body(&mut v, &mut tf, post, 1.2, 0.3, dt) {
                face_body(&mut v, &mut tf, site.at + Vec2::new(0.0, 12.0), dt);
            }
            if !dusk {
                k.state = 0;
            }
        }
        _ => k.state = 0,
    }
    if let Ok(mut vis) = fire.single_mut() {
        let want = if lit || matches!(k.state, 4) && k.lit_day == day { Visibility::Inherited } else { Visibility::Hidden };
        if *vis != want {
            *vis = want;
        }
    }
    // The waving torch: swung in a slow arc over his head toward the flank.
    if let Ok((mut ttf, mut tvis)) = torch.single_mut() {
        let signalling = k.state == 5 && signal.dir.is_some();
        *tvis = if signalling { Visibility::Inherited } else { Visibility::Hidden };
        if signalling {
            let f = Vec2::from_angle(-v.facing + PI / 2.0);
            let side = Vec2::new(-f.y, f.x) * (now * 2.6).sin() * 0.55;
            let p = v.pos + f * 0.35 + side;
            ttf.translation = Vec3::new(p.x, tf.translation.y + 2.05 + (now * 5.2).sin().abs() * 0.15, p.y);
            if (now * 2.6).sin().abs() > 0.97 {
                v.atk_anim = now;
            }
        }
    }
}

/// On Flank nights: which side the flankers come from (the invaders off the south line).
fn flank_signal(
    siege: Option<Res<crate::siege::Siege>>,
    orks: Query<&crate::orks::Ork, (With<crate::orks::WaveInvader>, Without<crate::dying::Dying>)>,
    site_q: Query<&BeaconSite>,
    mut signal: ResMut<BeaconSignal>,
) {
    let flank = siege.as_ref().is_some_and(|s| {
        s.phase == crate::siege::GamePhase::Wave
            && tileworld_core::threat::threat_for(s.wave_index.max(0) as usize).kind == tileworld_core::threat::ThreatKind::Flank
    });
    let Ok(site) = site_q.single() else { return };
    let dir = if flank {
        let (mut east, mut west) = (0, 0);
        for o in &orks {
            if o.pos.x.abs() > 26.0 && o.pos.x.abs() > o.pos.y {
                if o.pos.x > 0.0 { east += 1 } else { west += 1 }
            }
        }
        match (east, west) {
            (0, 0) => None,
            (e, w) => {
                let side = if e >= w { 1.0 } else { -1.0 };
                Some((Vec2::new(side * 45.0, 0.0) - site.at).normalize_or_zero())
            }
        }
    } else {
        None
    };
    if signal.dir != dir {
        signal.dir = dir;
    }
}

// ── Compass overlay (beacon-orange marker on the bearing the beacon signals) ────────────────────

/// The compass strip's geometry (`compass.rs`: 440 px wide, ±70° span, centred, 10 px from the
/// top) — this overlay rides the same scale without touching that module.
const STRIP_W: f32 = 440.0;
const HALF_SPAN: f32 = 70.0;

#[derive(Component)]
struct BeaconPip;

fn setup_overlay(mut commands: Commands, assets: Res<AssetServer>) {
    let mut img = ImageNode::new(assets.load("icons/gameicons/sym_warn.png"));
    img.color = Color::srgb(1.0, 0.55, 0.15);
    commands
        .spawn((
            Node {
                position_type: PositionType::Absolute,
                top: Val::Px(10.0),
                left: Val::Px(0.0),
                width: Val::Percent(100.0),
                flex_direction: FlexDirection::Row,
                justify_content: JustifyContent::Center,
                ..default()
            },
            Pickable::IGNORE,
            crate::game_state::CampaignOnly,
        ))
        .with_children(|w| {
            w.spawn((Node { width: Val::Px(STRIP_W), height: Val::Px(62.0), overflow: Overflow::clip(), ..default() }, GlobalZIndex(96), Pickable::IGNORE))
                .with_children(|s| {
                    s.spawn((
                        Node {
                            position_type: PositionType::Absolute,
                            top: Val::Px(36.0),
                            width: Val::Px(20.0),
                            height: Val::Px(20.0),
                            display: Display::None,
                            ..default()
                        },
                        img,
                        BeaconPip,
                    ));
                });
        });
}

fn update_overlay(
    time: Res<Time>,
    state: Res<State<crate::game_state::AppState>>,
    signal: Res<BeaconSignal>,
    cam_q: Query<&GlobalTransform, With<Camera3d>>,
    hero: Option<Res<crate::player::HeroState>>,
    mut pip: Query<(&mut Node, &mut ImageNode), With<BeaconPip>>,
) {
    let Ok((mut node, mut img)) = pip.single_mut() else { return };
    let playing = *state.get() == crate::game_state::AppState::Playing;
    let (Some(dir), true, Ok(cam), Some(hero)) = (signal.dir, playing, cam_q.single(), hero) else {
        node.display = Display::None;
        return;
    };
    // The flank side as a world point (beyond the walls on that side), seen from the hero.
    let target = Vec2::new(dir.x.signum() * 45.0, 4.0);
    let to = target - hero.pos;
    let bearing = |d: Vec2| d.x.atan2(-d.y);
    let fwd = cam.forward();
    let rel = {
        let mut x = (bearing(to) - bearing(Vec2::new(fwd.x, fwd.z))) % TAU;
        if x > PI {
            x -= TAU;
        } else if x < -PI {
            x += TAU;
        }
        x
    };
    let px = STRIP_W / 2.0 + rel.to_degrees() * (STRIP_W / 2.0) / HALF_SPAN;
    node.display = Display::Flex;
    node.left = Val::Px(px.clamp(4.0, STRIP_W - 24.0) - 10.0);
    // A slow ember pulse.
    let a = 0.7 + 0.3 * (time.elapsed_secs() * 4.0).sin().abs();
    img.color = Color::srgba(1.0, 0.55, 0.15, a);
}
