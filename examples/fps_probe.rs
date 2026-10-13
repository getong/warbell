//! Minimal Bevy app that reports its uncapped frame rate — tells a driver/OS-level frame cap
//! apart from the game's own cost. `cargo run --release --example fps_probe` (`PROBE_MODE=fifo|mailbox|immediate|autonovsync`).
use bevy::prelude::*;
use bevy::window::PresentMode;

fn main() {
    let mode = match std::env::var("PROBE_MODE").as_deref() {
        Ok("fifo") => PresentMode::Fifo,
        Ok("mailbox") => PresentMode::Mailbox,
        Ok("immediate") => PresentMode::Immediate,
        _ => PresentMode::AutoNoVsync,
    };
    App::new()
        .add_plugins(DefaultPlugins.set(WindowPlugin {
            primary_window: Some(Window { present_mode: mode, focused: std::env::var("PROBE_UNFOCUSED").is_err(), ..default() }),
            ..default()
        }))
        .add_systems(Startup, |mut c: Commands, mut m: ResMut<Assets<Mesh>>, mut mat: ResMut<Assets<StandardMaterial>>| {
            c.spawn((Camera3d::default(), Transform::from_xyz(0.0, 2.0, 5.0).looking_at(Vec3::ZERO, Vec3::Y)));
            c.spawn((Mesh3d(m.add(Cuboid::default())), MeshMaterial3d(mat.add(StandardMaterial::default()))));
            c.spawn(DirectionalLight::default());
        })
        .add_systems(Update, |time: Res<Time<Real>>, mut n: Local<u32>, mut exit: MessageWriter<AppExit>| {
            *n += 1;
            let t = time.elapsed_secs();
            if t > 8.0 {
                println!("FPS_PROBE frames={} fps={:.1}", *n, *n as f32 / t);
                exit.write(AppExit::Success);
            }
        })
        .run();
}
