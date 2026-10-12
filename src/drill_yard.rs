//! **Militia Butts** (living-island spec 2026-10-13 §2 D.14) — the drill ground north of the
//! postern: two turfed earth butts with straw targets, hacked pell posts, a spear rack and a
//! split-log bench. Every morning of a prep day a few townsfolk in militia kit walk out of the
//! postern and drill: bowmen loose at the butts (the shafts fly and stick), swordsmen hack the
//! pells; before noon they file back in.
//!
//! **Function.** During the drill the rack offers **[E] Lead the drill**. A day the hero led the
//! drill, the night's militia (the guards and the muster) fight on a full stomach of practice:
//! +25% HP for the night ([`DRILL_HP`]) and +15% to the blows they land ([`DRILL_DMG`], applied as
//! a top-up on invader wounds a buffed guard inflicts). State: the `drill_day` world flag.
//!
//! Models: `meadow_kit.glb` (`drill_butt`, `drill_pell`, `drill_rack`, `drill_bench`).

use bevy::prelude::*;
use std::collections::HashMap;

use crate::biome::BiomeEntity;
use crate::meadow::{day_index, face_body, kit_piece, sky_t, walk_body};
use crate::savegame::WorldFlags;

const BUTTS: [(Vec2, f32); 2] = [(Vec2::new(12.0, -46.0), 0.0), (Vec2::new(16.6, -46.4), -0.06)];
const PELLS: [Vec2; 2] = [Vec2::new(21.6, -40.4), Vec2::new(23.2, -42.4)];
const RACK: (Vec2, f32) = (Vec2::new(19.2, -37.0), 0.0);
const BENCH: (Vec2, f32) = (Vec2::new(14.4, -36.6), 0.1);
/// Where the drill files out of / back into the postern.
const POSTERN_OUT: Vec2 = Vec2::new(6.0, -27.5);
/// Drill hours (sky clock): early morning to late morning.
const DRILL_T: (f32, f32) = (0.03, 0.24);
pub const DRILL_HP: f32 = 1.25;
pub const DRILL_DMG: f32 = 1.15;

/// Footprints the other planners keep clear of.
pub fn planned_footprints() -> Vec<(Vec2, f32)> {
    vec![(Vec2::new(16.5, -42.0), 9.0)]
}

/// Worn ground (realforest mask): trampled shooting line, mud round the pells, a track from the
/// postern.
pub fn ground_wear(wx: f32, wz: f32) -> Option<(f32, f32, f32)> {
    let p = Vec2::new(wx, wz);
    if p.distance(Vec2::new(15.0, -39.0)) > 14.0 {
        return None;
    }
    let ss = |a: f32, b: f32, x: f32| {
        let t = ((x - a) / (b - a)).clamp(0.0, 1.0);
        t * t * (3.0 - 2.0 * t)
    };
    let wob = (wx * 1.9).sin() * 0.25 + (wz * 2.1).cos() * 0.2;
    let seg = |a: Vec2, b: Vec2| {
        let ab = b - a;
        let t = ((p - a).dot(ab) / ab.length_squared()).clamp(0.0, 1.0);
        p.distance(a + ab * t)
    };
    let line = 1.0 - ss(0.6, 1.5, seg(Vec2::new(10.5, -38.4), Vec2::new(18.0, -38.6)) + wob);
    let pells = PELLS.iter().map(|c| 1.0 - ss(0.7, 1.8, p.distance(*c) + wob)).fold(0.0f32, f32::max);
    let track = 1.0 - ss(0.5, 1.2, seg(Vec2::new(6.5, -30.0), Vec2::new(12.0, -37.5)) + wob);
    let butts = BUTTS.iter().map(|(c, _)| 1.0 - ss(1.6, 2.6, p.distance(*c + Vec2::new(0.0, 1.2)) + wob)).fold(0.0f32, f32::max);
    let path = (line * 0.7).max(pells * 0.85).max(track * 0.5).max(butts * 0.45);
    (path > 0.01).then(|| (ss(0.0, 0.5, path), path, pells * 0.4))
}

pub struct DrillYardPlugin;

impl Plugin for DrillYardPlugin {
    fn build(&self, app: &mut App) {
        app.add_systems(Update, spawn_drill_yard.run_if(crate::rts::in_campaign)).add_systems(
            Update,
            (drill_brain, fly_arrows, lead_drill, drill_buff)
                .chain()
                .run_if(in_state(crate::game_state::Modal::None))
                .run_if(crate::rts::in_campaign),
        );
    }
}

#[derive(Component)]
struct DrillSite;
#[derive(Component)]
struct DrillRack;
#[derive(Component)]
struct Trainee {
    /// Station (world XZ) and what to face there.
    post: Vec2,
    face: Vec2,
    archer: bool,
    next: f32,
}
#[derive(Component)]
struct Arrow {
    from: Vec3,
    to: Vec3,
    t: f32,
    stuck: f32,
}
/// A guard carrying tonight's drill bonus (its pre-buff max HP, restored at dawn).
#[derive(Component)]
struct Drilled {
    base_max: f32,
}

#[derive(Resource)]
struct ArrowMesh(Handle<Mesh>, Handle<StandardMaterial>);

#[allow(clippy::too_many_arguments)]
fn spawn_drill_yard(
    mut commands: Commands,
    ready: Res<crate::biome::WorldReady>,
    site: Query<(), With<DrillSite>>,
    mut meshes: ResMut<Assets<Mesh>>,
    mut mats: ResMut<Assets<StandardMaterial>>,
    mut cmats: ResMut<Assets<crate::creature::CreatureMaterial>>,
) {
    if !ready.0 || !site.is_empty() || crate::realforest::get().is_none() {
        return;
    }
    let mut anchor = commands.spawn((DrillSite, BiomeEntity, Transform::default()));
    anchor.insert(Visibility::Hidden);
    for (c, yaw) in BUTTS {
        kit_piece(&mut commands, "drill_butt", c.x, c.y, yaw, 0.05);
        crate::blockers::add_obb(c.x, c.y - 0.2, 1.4, 0.7, yaw);
    }
    for (k, c) in PELLS.iter().enumerate() {
        kit_piece(&mut commands, "drill_pell", c.x, c.y, k as f32 * 1.3, 0.0);
        crate::blockers::add_obb(c.x, c.y, 0.14, 0.14, 0.0);
    }
    if let Some(e) = kit_piece(&mut commands, "drill_rack", RACK.0.x, RACK.0.y, RACK.1, 0.0) {
        commands.entity(e).insert(DrillRack);
    }
    crate::blockers::add_obb(RACK.0.x, RACK.0.y, 1.0, 0.2, RACK.1);
    kit_piece(&mut commands, "drill_bench", BENCH.0.x, BENCH.0.y, BENCH.1, 0.02);
    // Two bowmen at the shooting line, two swordsmen at the pells (hidden until the drill).
    let posts = [
        (Vec2::new(11.4, -38.4), BUTTS[0].0, true),
        (Vec2::new(16.2, -38.7), BUTTS[1].0, true),
        (PELLS[0] + Vec2::new(-0.2, 0.95), PELLS[0], false),
        (PELLS[1] + Vec2::new(-0.75, 0.6), PELLS[1], false),
    ];
    for (k, (post, face, archer)) in posts.into_iter().enumerate() {
        let e = crate::villagers::spawn_rts_militia(&mut commands, &mut meshes, &mut cmats, archer, POSTERN_OUT, 0xD811 + k as u32 * 7);
        commands.entity(e).insert((crate::scenes::SceneActor, Trainee { post, face, archer, next: k as f32 * 0.7 }, Visibility::Hidden));
    }
    let mesh = meshes.add(Cuboid::new(0.018, 0.018, 0.62).mesh().build());
    let mat = mats.add(StandardMaterial { base_color: Color::srgb(0.62, 0.5, 0.36), perceptual_roughness: 0.85, ..default() });
    commands.insert_resource(ArrowMesh(mesh, mat));
}

fn drill_on(t: f32, siege: &crate::siege::Siege) -> bool {
    siege.phase == crate::siege::GamePhase::Prep && (DRILL_T.0..DRILL_T.1).contains(&t)
}

#[allow(clippy::type_complexity)]
fn drill_brain(
    mut commands: Commands,
    time: Res<Time>,
    clock: Option<Res<crate::scene::SkyClock>>,
    siege: Option<Res<crate::siege::Siege>>,
    town: Res<crate::town::TownRes>,
    arrows: Option<Res<ArrowMesh>>,
    mut q: Query<(&mut Trainee, &mut crate::villagers::Villager, &mut Transform, &mut Visibility)>,
) {
    let Some(siege) = siege else { return };
    let dt = time.delta_secs().min(0.05);
    let now = time.elapsed_secs();
    let on = drill_on(sky_t(clock.as_deref()), &siege);
    // A small town turns out two (the bowmen); four once it has grown.
    let crew = if town.0.population >= 6 { 4 } else { 2 };
    for (k, (mut tr, mut v, mut tf, mut vis)) in q.iter_mut().enumerate() {
        let tr = &mut *tr;
        if on && k < crew {
            *vis = Visibility::Inherited;
            if walk_body(&mut v, &mut tf, tr.post, 1.3, 0.25, dt) {
                face_body(&mut v, &mut tf, tr.face, dt);
                if now >= tr.next {
                    v.atk_anim = now;
                    if tr.archer {
                        tr.next = now + 3.2 + crate::meadow::hash01((now * 100.0) as u32) * 1.5;
                        if let Some(a) = arrows.as_ref() {
                            let y = tf.translation.y;
                            let aim = tr.face + Vec2::new(crate::meadow::hash01(now.to_bits()) - 0.5, 0.0) * 0.9;
                            let to_y = crate::worldmap::ground_at_world(aim.x, aim.y).unwrap_or(y) + 0.55 + crate::meadow::hash01(now.to_bits() ^ 9) * 0.5;
                            commands.spawn((
                                Mesh3d(a.0.clone()),
                                MeshMaterial3d(a.1.clone()),
                                Transform::from_xyz(v.pos.x, y + 1.45, v.pos.y),
                                Arrow { from: Vec3::new(v.pos.x, y + 1.45, v.pos.y), to: Vec3::new(aim.x, to_y, aim.y + 0.5), t: -0.55, stuck: 0.0 },
                                Visibility::Hidden,
                                BiomeEntity,
                            ));
                        }
                    } else {
                        tr.next = now + 1.1 + crate::meadow::hash01((now * 100.0) as u32) * 0.6;
                    }
                }
            }
        } else if *vis != Visibility::Hidden {
            // Drill over: back through the postern, then gone.
            if walk_body(&mut v, &mut tf, POSTERN_OUT, 1.3, 0.4, dt) {
                *vis = Visibility::Hidden;
            }
        }
    }
}

/// Shafts loosed at the butts: a short arc (after the draw), then they stick and linger.
fn fly_arrows(mut commands: Commands, time: Res<Time>, mut q: Query<(Entity, &mut Arrow, &mut Transform, &mut Visibility)>) {
    let dt = time.delta_secs();
    for (e, mut a, mut tf, mut vis) in &mut q {
        if a.t < 1.0 {
            a.t += dt / 0.45;
            if a.t < 0.0 {
                continue; // still being drawn
            }
            *vis = Visibility::Inherited;
            let t = a.t.min(1.0);
            let p = a.from.lerp(a.to, t) + Vec3::Y * (t * (1.0 - t) * 1.6);
            let ahead = a.from.lerp(a.to, (t + 0.02).min(1.0)) + Vec3::Y * ((t + 0.02) * (1.0 - t - 0.02) * 1.6);
            tf.translation = p;
            if (ahead - p).length_squared() > 1e-6 {
                tf.look_to(ahead - p, Vec3::Y);
            }
        } else {
            a.stuck += dt;
            if a.stuck > 9.0 {
                commands.entity(e).try_despawn();
            }
        }
    }
}

/// The rack's [E] prompt during the drill; pressing it marks today a drill day.
#[allow(clippy::too_many_arguments)]
fn lead_drill(
    mut commands: Commands,
    time: Res<Time>,
    clock: Option<Res<crate::scene::SkyClock>>,
    siege: Option<Res<crate::siege::Siege>>,
    mut flags: ResMut<WorldFlags>,
    mut notice: ResMut<crate::ui::notice::Notice>,
    mut ev: MessageReader<crate::interaction::Interacted>,
    rack: Query<(Entity, Has<crate::interaction::Interactable>), With<DrillRack>>,
) {
    let Some(siege) = siege else { return };
    let day = day_index(&siege);
    let open = drill_on(sky_t(clock.as_deref()), &siege) && flags.get("drill_day") != day + 1;
    for (e, has) in &rack {
        if open && !has {
            commands.entity(e).insert(crate::interaction::Interactable::new("Lead the drill", 3.2));
        } else if !open && has {
            commands.entity(e).remove::<crate::interaction::Interactable>();
        }
    }
    for crate::interaction::Interacted(e) in ev.read() {
        if rack.contains(*e) && open {
            // Stored as day+1 so the flag's default 0 never matches day 0.
            flags.set("drill_day", day + 1);
            notice.push("The militia drilled hard. They'll stand firmer tonight.", time.elapsed_secs_f64());
        }
    }
}

/// Apply the drill bonus to the night's guards (HP up front; the damage top-up per wound), and
/// take it off again at dawn.
#[allow(clippy::type_complexity)]
fn drill_buff(
    mut commands: Commands,
    siege: Option<Res<crate::siege::Siege>>,
    flags: Res<WorldFlags>,
    hero: Option<Res<crate::player::HeroState>>,
    mut guards: Query<(Entity, &mut crate::villagers::NpcHp, Option<&Drilled>, &Transform), With<crate::villagers::Guard>>,
    mut foes: Query<(Entity, &crate::orks::Ork, &mut crate::player::Health), (With<crate::orks::WaveInvader>, Without<crate::dying::Dying>)>,
    mut last: Local<HashMap<Entity, f32>>,
) {
    let Some(siege) = siege else { return };
    let wave = siege.phase == crate::siege::GamePhase::Wave;
    // The night after day `d` is wave_index d-1+1 = d: the buff holds when tonight follows a drill day.
    let buffed = wave && flags.get("drill_day") == siege.wave_index as i64 + 1;
    let mut posts: Vec<Vec2> = Vec::new();
    for (e, mut hp, drilled, tf) in &mut guards {
        match (buffed, drilled) {
            (true, None) => {
                let base = hp.max;
                hp.max = base * DRILL_HP;
                hp.hp *= DRILL_HP;
                commands.entity(e).try_insert(Drilled { base_max: base });
            }
            (false, Some(d)) => {
                hp.max = d.base_max;
                hp.hp = hp.hp.min(hp.max);
                commands.entity(e).remove::<Drilled>();
            }
            _ => {}
        }
        if buffed {
            posts.push(Vec2::new(tf.translation.x, tf.translation.z));
        }
    }
    if !buffed {
        last.clear();
        return;
    }
    // Damage top-up: an invader that lost HP this frame with a drilled guard at its throat (and
    // the hero not in the scrum, whose blows are his own) takes 15% more.
    let hero_pos = hero.map_or(Vec2::splat(1e6), |h| h.pos);
    for (e, o, mut h) in &mut foes {
        let prev = last.insert(e, h.hp).unwrap_or(h.hp);
        let lost = prev - h.hp;
        if lost > 0.0 && o.pos.distance(hero_pos) > 4.0 && posts.iter().any(|p| p.distance(o.pos) < 2.6) {
            h.hp -= lost * (DRILL_DMG - 1.0);
            last.insert(e, h.hp);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn drill_ground_is_clear_of_plots_and_fields() {
        let mut pts: Vec<Vec2> = BUTTS.iter().map(|b| b.0).collect();
        pts.extend(PELLS);
        pts.extend([RACK.0, BENCH.0, Vec2::new(11.4, -38.4), Vec2::new(16.2, -38.7)]);
        for p in pts {
            assert!(!crate::town::near_build_plot(p.x, p.y), "{p} on a build plot");
            assert!(!crate::castle_ground::in_field(p.x, p.y), "{p} on a field");
            assert!(crate::castle::outside_dist(p.x, p.y) > 6.0, "{p} hugs the wall");
        }
    }
}
