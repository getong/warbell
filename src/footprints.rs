//! **Boot prints** — every footfall on yielding ground presses a print that stays (deep reliefs in
//! mud, sand and snow; a shallow scuff on packed earth; a bruised patch of crushed blades on grass):
//! left / right boots alternate on the real planted foot (`footing::Footfall::side`), the toe
//! points along the stride, and the print is a relief, not a stamp — `ground_mark.wesl`'s
//! `KIND_BOOT` builds a pressed height field (heel deepest, the arch barely touching, spoil pushed
//! up round the rim) and shades it against the sun, darkening the wet cavity in mud and turning
//! the shaded plug blue in snow. Prints hold, then fade: snow keeps them longest, wind-dried sand
//! the shortest.
//!
//! Cheap by construction: each print is one instanced quad on the shared `combat_marks` stain
//! material (no per-print material; a fade only rewrites the `MeshTag`), and the pools are capped —
//! the oldest print is lifted when a new one would overflow. The hero's trail has its own pool
//! ([`MAX_HERO_PRINTS`]) so a muddy village full of walkers ([`MAX_NPC_PRINTS`]) can't erase it.
//!
//! Spawn + fade are sim-gated: a frozen world neither takes steps nor dries its prints.

use std::collections::VecDeque;

use bevy::mesh::MeshTag;
use bevy::prelude::*;

use crate::combat_marks::{boot_tag, MarkAssets};
use crate::footing::{Footfall, FootfallSet, Stepper, Surface};
use crate::game_state::SimAppExt;
use crate::worldmap;

/// Hard caps on live prints — the oldest is lifted to make room. Separate pools: the hero's own
/// trail must survive a crowd walking the same mud.
const MAX_HERO_PRINTS: usize = 192;
const MAX_NPC_PRINTS: usize = 160;
/// Print quad footprint (world units): width across the sole × length heel→toe. The shader's sole
/// fills ~80% of it, leaving room for the spoil rim.
const PRINT_W: f32 = 0.2;
const PRINT_L: f32 = 0.36;

/// One live print: ages, holds at full strength, then fades out.
#[derive(Component)]
struct BootPrint {
    age: f32,
    hold: f32,
    fade: f32,
    a0: f32,
    seed: u32,
    ground: u32,
    left: bool,
    sprint: bool,
}

/// Spawn order of live prints, oldest first (may hold already-faded ids; pruned lazily):
/// `.0` the hero's, `.1` everyone else's.
#[derive(Resource, Default)]
struct PrintPool(VecDeque<Entity>, VecDeque<Entity>);

/// (shader ground code, hold s, fade s, strength) per yielding surface.
fn ground_params(s: Surface) -> Option<(u32, f32, f32, f32)> {
    match s {
        Surface::Mud => Some((0, 35.0, 15.0, 0.95)),
        Surface::Sand => Some((1, 22.0, 12.0, 0.85)),
        Surface::Snow => Some((2, 45.0, 15.0, 1.0)),
        // Packed earth / roads: a dusty scuff that the next cart wheel would erase.
        Surface::Dirt => Some((3, 22.0, 10.0, 0.8)),
        // The sward springs back: a short-lived bruise where the blades were crushed (the blades
        // themselves lie flat a while too, `grass_trample`).
        Surface::Grass => Some((4, 12.0, 8.0, 0.6)),
        _ => None,
    }
}

/// Tilt a print to the terrain under it (a flat quad on a slope would float at one end and bury
/// the other), facing `dir`.
fn print_rotation(at: Vec3, dir: Vec2) -> Quat {
    let yaw = dir.x.atan2(dir.y);
    let g = |dx: f32, dz: f32| worldmap::ground_at_world(at.x + dx, at.z + dz).unwrap_or(at.y);
    let (fx, fz) = (dir.x * PRINT_L * 0.5, dir.y * PRINT_L * 0.5);
    let (rx, rz) = (-dir.y * PRINT_W * 0.5, dir.x * PRINT_W * 0.5);
    let fwd = Vec3::new(fx * 2.0, g(fx, fz) - g(-fx, -fz), fz * 2.0);
    let right = Vec3::new(rx * 2.0, g(rx, rz) - g(-rx, -rz), rz * 2.0);
    let mut n = right.cross(fwd).normalize_or(Vec3::Y);
    if n.y < 0.0 {
        n = -n;
    }
    // Ignore wild normals (a cliff lip / deck edge under one sample): lie flat instead.
    if n.y < 0.8 {
        n = Vec3::Y;
    }
    Quat::from_rotation_arc(Vec3::Y, n) * Quat::from_rotation_y(yaw)
}

fn spawn_prints(
    mut commands: Commands,
    mut steps: MessageReader<Footfall>,
    marks: Option<Res<MarkAssets>>,
    mut pool: ResMut<PrintPool>,
    mut seed: Local<u32>,
    live: Query<(), With<BootPrint>>,
) {
    let Some(marks) = marks else {
        steps.clear();
        return;
    };
    for f in steps.read() {
        if !f.surface.takes_prints() {
            continue;
        }
        let Some((ground, hold, fade, a0)) = ground_params(f.surface) else { continue };
        // A landing plants both boots side by side; a step plants the one foot.
        let right = Vec2::new(-f.dir.y, f.dir.x);
        let feet: &[(Vec2, f32)] = match f.who {
            Stepper::HeroLanding { .. } => &[(right * 0.1, 1.0), (right * -0.1, -1.0)],
            _ => &[(Vec2::ZERO, f.side)],
        };
        let (q, cap) = match f.who {
            Stepper::Npc { .. } => (&mut pool.1, MAX_NPC_PRINTS),
            _ => (&mut pool.0, MAX_HERO_PRINTS),
        };
        for &(off, side) in feet {
            if q.len() >= cap {
                q.retain(|e| live.contains(*e));
                while q.len() >= cap {
                    if let Some(old) = q.pop_front() {
                        commands.entity(old).try_despawn();
                    }
                }
            }
            *seed = seed.wrapping_mul(1_664_525).wrapping_add(1_013_904_223);
            let s = *seed >> 13;
            // Sit on the terrain under the boot itself (the footfall carries the body's footing
            // height; on a bank or slope the boot's own ground differs) — unless it's a deck.
            let foot = f.at.xz() + off;
            let y = worldmap::ground_at_world(foot.x, foot.y).filter(|g| (g - f.at.y).abs() < 0.4).unwrap_or(f.at.y);
            let at = Vec3::new(foot.x, y + 0.012, foot.y);
            let left = side < 0.0;
            let sprint = f.gait > 0.6;
            let e = commands
                .spawn((
                    Mesh3d(marks.quad.clone()),
                    MeshMaterial3d(marks.stain.clone()),
                    Transform {
                        translation: at,
                        rotation: print_rotation(at, f.dir),
                        scale: Vec3::new(PRINT_W, 1.0, PRINT_L),
                    },
                    boot_tag(a0, s, ground, left, sprint),
                    BootPrint { age: 0.0, hold, fade, a0, seed: s, ground, left, sprint },
                    bevy::light::NotShadowCaster,
                    // World rebuilds (New Game, biome swap) sweep prints with everything else.
                    crate::biome::BiomeEntity,
                ))
                .id();
            q.push_back(e);
        }
    }
}

/// Age every print: full strength through its hold, then a smooth fade; reap at the end.
fn fade_prints(time: Res<Time>, mut commands: Commands, mut q: Query<(Entity, &mut BootPrint, &mut MeshTag)>) {
    let dt = time.delta_secs();
    for (e, mut p, mut tag) in &mut q {
        p.age += dt;
        let k = ((p.age - p.hold) / p.fade).clamp(0.0, 1.0);
        if k >= 1.0 {
            commands.entity(e).try_despawn();
            continue;
        }
        let want = boot_tag(p.a0 * (1.0 - k * k * (3.0 - 2.0 * k)), p.seed, p.ground, p.left, p.sprint);
        if tag.value != want.value {
            tag.value = want.value;
        }
    }
}

/// `FOREST_PRINTTEST="x,z"`: once the world is up, park rows of boot prints (mud / sand / snow /
/// packed earth / grass,
/// left + right + a sprint push-off) and a blood-pool control mark on the ground at a world XZ,
/// so a still (`FOREST_SHOT` + `FOREST_CAM`) frames the print look without a walk. Rows run +X,
/// toes point -Z.
fn print_test(
    mut commands: Commands,
    time: Res<Time>,
    marks: Option<Res<MarkAssets>>,
    mut done: Local<bool>,
) {
    if *done || time.elapsed_secs() < 4.0 {
        return;
    }
    let Some(marks) = marks else { return };
    *done = true;
    let Some(c) = std::env::var("FOREST_PRINTTEST").ok().and_then(|s| {
        let v: Vec<f32> = s.split(',').filter_map(|p| p.trim().parse().ok()).collect();
        (v.len() == 2).then(|| Vec2::new(v[0], v[1]))
    }) else {
        return;
    };
    let dir = Vec2::new(0.0, -1.0);
    // `FOREST_PRINTTEST_SCALE=<k>` blows the test prints up k× to inspect the shader's shape.
    let k: f32 = std::env::var("FOREST_PRINTTEST_SCALE").ok().and_then(|v| v.parse().ok()).unwrap_or(1.0);
    for ground in 0..5u32 {
        for (i, (left, sprint)) in [(true, false), (false, false), (true, true), (false, true)].into_iter().enumerate() {
            let p = c + Vec2::new(i as f32 * 0.32 - 0.5, ground as f32 * 0.6) * k;
            let y = worldmap::ground_at_world(p.x, p.y).unwrap_or(0.0) + 0.012;
            let at = Vec3::new(p.x, y, p.y);
            commands.spawn((
                Mesh3d(marks.quad.clone()),
                MeshMaterial3d(marks.stain.clone()),
                Transform { translation: at, rotation: print_rotation(at, dir), scale: Vec3::new(PRINT_W * k, 1.0, PRINT_L * k) },
                boot_tag(1.0, 17 + i as u32 * 31, ground, left, sprint),
                bevy::light::NotShadowCaster,
            ));
        }
    }
    let b = c + Vec2::new(1.2, 0.6) * k;
    let y = worldmap::ground_at_world(b.x, b.y).unwrap_or(0.0) + 0.012;
    crate::combat_marks::spawn_mark(
        &mut commands,
        &marks,
        crate::combat_marks::MarkKind::Blood,
        Vec3::new(b.x, y, b.y),
        0.6,
        0.0,
        1.0,
        1.0,
        5,
    );
    info!("footprints: print test staged at {c:?}");
}

pub struct FootprintsPlugin;

impl Plugin for FootprintsPlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<PrintPool>()
            .add_sim_systems((spawn_prints.after(FootfallSet), fade_prints));
        if std::env::var_os("FOREST_PRINTTEST").is_some() {
            app.add_systems(Update, print_test);
        }
    }
}
