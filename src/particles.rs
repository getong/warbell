//! Ambient weather particles — a cheap CPU drift system. The active biome (the one the hero
//! stands in) picks a [`ParticleKind`]; [`update_weather`] spawns a few hundred tiny instanced
//! motes tagged [`Particle`] in a box that FOLLOWS the hero, and [`drift`] drifts + wraps them
//! within that moving box. Snow falls, pollen rises, dust drifts sideways, fireflies bob
//! (emissive → bloom). Crossing a biome edge **fades** the field's alpha in/out (so it eases in
//! rather than popping at full strength) and only despawns the old field once it's faded away.
//! No GPU particle plumbing — just instanced soft round sprites ([`soft_disc_mesh`]).

use bevy::asset::RenderAssetUsages;
use bevy::prelude::*;
use bevy::render::render_resource::{Extent3d, TextureDimension, TextureFormat};

use crate::biome::{BiomeAmbiences, BiomeEntity, ParticleKind};
use crate::player::HeroState;

/// Where the weather box is centred (the hero's world XZ), updated each frame so the field
/// follows the player across the map.
#[derive(Resource, Default)]
struct WeatherCenter(Vec2);

/// The weather field currently in the world + its fade ramp, so crossing a biome edge eases
/// the alpha in/out instead of popping the full mote count instantly.
#[derive(Resource, Default)]
struct Weather {
    /// The kind currently spawned (`None` = no field in the world right now).
    spawned: Option<ParticleKind>,
    /// Its shared material — alpha driven by `fade` each frame.
    mat: Option<Handle<StandardMaterial>>,
    /// The kind's intended max alpha (the ramp scales toward this).
    full_alpha: f32,
    /// 0 = invisible, 1 = fully faded in.
    fade: f32,
}

/// Horizontal half-extent of the particle box around the hero.
const R: f32 = 26.0;
/// How fast weather fades in/out when the hero crosses a biome edge (exponential, per second).
/// Gentle so snow/dust eases in over ~2–3 s rather than appearing all at once.
const WEATHER_FADE: f32 = 0.7;

#[derive(Component)]
pub struct Particle {
    vel: Vec3,
    phase: f32,
    sway: f32,
    y_min: f32,
    y_max: f32,
    /// Swamp fog-bank cards set this — [`drift`] yaws them to face the camera each frame (kept
    /// upright) so a big soft quad reads as a rolling mist bank. Motes leave it `false`.
    billboard: bool,
    /// Mote diameter (world units) — the base scale [`drift`] blinks fireflies around.
    size: f32,
    /// Fireflies: pulse the scale in a slow glow-and-dark cycle (a real firefly's flash).
    blink: bool,
}

// ── Shared soft-sprite kit (also used by decor fireflies, bog marsh-lights, landmark smoke…) ──

/// Camera-facing marker: [`face_camera`] copies the 3D camera's rotation onto the entity every
/// frame, so a [`soft_disc_mesh`] quad always shows its round face (screen-aligned billboard).
#[derive(Component)]
pub struct FaceCamera;

/// How far into the dusk→night "firefly hours" the clock is: 0 in full daylight, rising as the
/// sun drops below ~20° (golden hour at t≈0.43), 1 from just after sunset through the night.
/// Shared so every glow-in-the-dark ambient (fireflies, marsh-lights) keeps the same hours.
#[derive(Resource, Default, Clone, Copy)]
pub struct Dusk(pub f32);

pub fn dusk_of(t: f32) -> f32 {
    let a = t * std::f32::consts::TAU;
    let elev = Vec3::new(a.cos(), a.sin(), 0.55).normalize().y;
    let x = ((elev - 0.05) / 0.30).clamp(0.0, 1.0);
    1.0 - x * x * (3.0 - 2.0 * x)
}

/// A unit-diameter (±0.5) soft round sprite: a 16-segment disc in the XY plane (+Z normal) whose
/// vertex alpha falls from 1 at the centre to 0 at the rim. Multiplied into any material's base
/// colour (Blend or Add), it reads as a soft glow/flake/puff — no hard edge, no facets, no texture.
pub fn soft_disc_mesh() -> Mesh {
    use bevy::mesh::{Indices, PrimitiveTopology};
    const SEG: u32 = 16;
    // (radius, alpha) rings — a gaussian-ish falloff.
    const RINGS: [(f32, f32); 4] = [(0.0, 1.0), (0.14, 0.82), (0.3, 0.32), (0.5, 0.0)];
    let mut pos = Vec::new();
    let mut col = Vec::new();
    let mut uv = Vec::new();
    for (ri, &(r, a)) in RINGS.iter().enumerate() {
        let n = if ri == 0 { 1 } else { SEG };
        for k in 0..n {
            let ang = k as f32 / SEG as f32 * std::f32::consts::TAU;
            let (x, y) = (ang.cos() * r, ang.sin() * r);
            pos.push([x, y, 0.0]);
            col.push([1.0, 1.0, 1.0, a]);
            uv.push([x + 0.5, 0.5 - y]);
        }
    }
    let mut idx: Vec<u32> = Vec::new();
    for k in 0..SEG {
        idx.extend_from_slice(&[0, 1 + k, 1 + (k + 1) % SEG]);
    }
    for ring in 1..(RINGS.len() as u32 - 1) {
        let a0 = 1 + (ring - 1) * SEG;
        let b0 = a0 + SEG;
        for k in 0..SEG {
            let k1 = (k + 1) % SEG;
            idx.extend_from_slice(&[a0 + k, b0 + k, b0 + k1, a0 + k, b0 + k1, a0 + k1]);
        }
    }
    let n = pos.len();
    Mesh::new(PrimitiveTopology::TriangleList, RenderAssetUsages::default())
        .with_inserted_attribute(Mesh::ATTRIBUTE_POSITION, pos)
        .with_inserted_attribute(Mesh::ATTRIBUTE_NORMAL, vec![[0.0, 0.0, 1.0]; n])
        .with_inserted_attribute(Mesh::ATTRIBUTE_UV_0, uv)
        .with_inserted_attribute(Mesh::ATTRIBUTE_COLOR, col)
        .with_inserted_indices(Indices::U32(idx))
}

/// Firefly flash curve for a given time + per-fly phase/rate: mostly dark, a soft ~1 s glow every
/// few seconds. Returns 0..1 (callers scale the sprite by it; 0 = dark).
pub fn firefly_blink(t: f32, phase: f32, rate: f32) -> f32 {
    let s = (t * rate + phase).sin();
    let b = ((s - 0.35) / 0.65).clamp(0.0, 1.0);
    b * b * (3.0 - 2.0 * b)
}

fn update_dusk(clock: Option<Res<crate::scene::SkyClock>>, mut dusk: ResMut<Dusk>) {
    let v = clock.map(|c| dusk_of(c.t)).unwrap_or(0.0);
    if (dusk.0 - v).abs() > 1e-4 {
        dusk.0 = v;
    }
}

fn face_camera(
    cam_q: Query<&GlobalTransform, With<Camera3d>>,
    parents: Query<&GlobalTransform, Without<FaceCamera>>,
    mut q: Query<(&mut Transform, Option<&ChildOf>, &ViewVisibility), With<FaceCamera>>,
) {
    let Some(cam) = cam_q.iter().next() else { return };
    let rot = cam.compute_transform().rotation;
    for (mut tf, parent, vis) in &mut q {
        // Off-screen billboards needn't face anyone (one frame stale on entry is invisible).
        if !vis.get() {
            continue;
        }
        // A child sprite (e.g. a landmark model's chimney puff) cancels its parent's rotation.
        tf.rotation = match parent.and_then(|c| parents.get(c.parent()).ok()) {
            Some(pg) => pg.compute_transform().rotation.inverse() * rot,
            None => rot,
        };
    }
}

/// [`soft_disc_mesh`] with its vertex RGB tinted (alpha falloff kept) — for model parts whose
/// shared material is white and whose colour rides the vertices.
pub fn soft_disc_tinted(rgb: [f32; 3]) -> Mesh {
    let mut m = soft_disc_mesh();
    if let Some(bevy::mesh::VertexAttributeValues::Float32x4(cols)) = m.attribute_mut(Mesh::ATTRIBUTE_COLOR) {
        for c in cols.iter_mut() {
            c[0] *= rgb[0];
            c[1] *= rgb[1];
            c[2] *= rgb[2];
        }
    }
    m
}

pub struct ParticlePlugin;

impl Plugin for ParticlePlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<WeatherCenter>()
            .init_resource::<Weather>()
            .init_resource::<Dusk>()
            .add_systems(Update, (update_dusk, face_camera))
            // Picking/respawning the field is sim-ish (spawns entities, follows the hero), so it
            // freezes with panels; the drift itself is visual and keeps animating ungated.
            .add_systems(
                Update,
                (
                    update_weather.run_if(in_state(crate::game_state::Modal::None)),
                    drift,
                ),
            );
    }
}

/// Pick the weather for the biome the hero stands in and ease it in/out: ramp the field's alpha
/// toward full while the hero is in its biome, ramp it to zero (then despawn) when they leave,
/// and spawn the new biome's field once the old one has faded away. Also tracks the hero XZ so
/// [`drift`] can wrap the motes within a box that follows the player.
fn update_weather(
    mut commands: Commands,
    time: Res<Time>,
    hero: Option<Res<HeroState>>,
    ambiences: Option<Res<BiomeAmbiences>>,
    mode: Res<crate::player::PlayMode>,
    fly_cam: Query<&Transform, With<crate::controls::FlyCam>>,
    mut weather: ResMut<Weather>,
    mut center: ResMut<WeatherCenter>,
    existing: Query<Entity, With<Particle>>,
    mut meshes: ResMut<Assets<Mesh>>,
    mut materials: ResMut<Assets<StandardMaterial>>,
    mut images: ResMut<Assets<Image>>,
    dusk: Res<Dusk>,
) {
    let (Some(hero), Some(ambiences)) = (hero, ambiences) else { return };
    // The weather box follows the hero in Play, but the free-roam fly-cam in FreeRoam — otherwise
    // flying off to frame a trailer shot leaves the motes parked back at the (stationary) hero and
    // the scene reads empty. Sample the biome + centre the box at whichever the view is tracking.
    let focus = match *mode {
        crate::player::PlayMode::FreeRoam => {
            fly_cam.single().map(|t| Vec3::new(t.translation.x, t.translation.y, t.translation.z)).unwrap_or(Vec3::new(hero.pos.x, hero.y, hero.pos.y))
        }
        crate::player::PlayMode::Play => Vec3::new(hero.pos.x, hero.y, hero.pos.y),
    };
    center.0 = Vec2::new(focus.x, focus.z);
    // World-space lookup so the Blight (ork castle) drifts ash, not swamp's (lack of) weather.
    let desired = ambiences.sample_world(focus.x, focus.z).particle;
    // Exponential approach, stable across frame rates.
    let k = 1.0 - (-time.delta_secs() * WEATHER_FADE).exp();

    match weather.spawned {
        // The right field is already up → ease it in to full.
        Some(cur) if cur == desired => weather.fade += (1.0 - weather.fade) * k,
        // A field is up but the hero left its biome (or wants a different one) → fade it out,
        // and once it's invisible, despawn the motes and clear the slot.
        Some(_) => {
            weather.fade += (0.0 - weather.fade) * k;
            if weather.fade <= 0.02 {
                for e in &existing {
                    commands.entity(e).try_despawn();
                }
                weather.spawned = None;
                weather.mat = None;
                weather.fade = 0.0;
            }
        }
        // Nothing up → spawn the desired field invisible, to fade in over the next frames.
        None => {
            if desired != ParticleKind::None {
                let (mat, full_alpha) = spawn(desired, &mut commands, &mut meshes, &mut materials, &mut images, focus);
                weather.spawned = Some(desired);
                weather.mat = Some(mat);
                weather.full_alpha = full_alpha;
                weather.fade = 0.0;
            }
        }
    }

    // Drive the shared material's alpha from the fade ramp × the hour (fireflies only come out
    // at dusk; sunlit pollen/dust motes go with the light). One material, written only when the
    // value actually moves (no per-frame GPU re-upload once settled).
    let hour = match weather.spawned {
        Some(ParticleKind::Fireflies) => dusk.0,
        Some(ParticleKind::Pollen) => 1.0 - dusk.0,
        _ => 1.0,
    };
    if let Some(handle) = weather.mat.clone() {
        let want = weather.full_alpha * weather.fade * hour;
        let cur = materials.get(&handle).map(|m| m.base_color.alpha());
        if cur.is_some_and(|c| (c - want).abs() > 0.004 || (want == 0.0 && c != 0.0)) {
            if let Some(mut m) = materials.get_mut(&handle) {
                m.base_color = m.base_color.with_alpha(want);
            }
        }
    }
}

/// Tiny deterministic hash → [0,1) from an integer (per-instance variation).
fn h(n: u32) -> f32 {
    let mut t = n.wrapping_mul(0x6d2b_79f5).wrapping_add(0x9e37_79b9);
    t = (t ^ (t >> 15)).wrapping_mul(t | 1);
    t ^= t.wrapping_add((t ^ (t >> 7)).wrapping_mul(t | 61));
    ((t ^ (t >> 14)) as f32) / 4_294_967_296.0
}

/// Spawn the particle field for `kind`, centred on `center` (the hero). Returns the field's
/// shared material + its intended max alpha, so [`update_weather`] can fade it in/out. The caller
/// guarantees `kind != None`.
fn spawn(
    kind: ParticleKind,
    commands: &mut Commands,
    meshes: &mut Assets<Mesh>,
    materials: &mut Assets<StandardMaterial>,
    images: &mut Assets<Image>,
    center: Vec3,
) -> (Handle<StandardMaterial>, f32) {
    // Swamp mist is NOT motes — big soft camera-facing cards (see `spawn_fog_banks`).
    if kind == ParticleKind::Mist {
        return spawn_fog_banks(commands, meshes, materials, images, center);
    }
    // Per-kind look + motion. Every mote is a soft round camera-facing sprite (no spheres): lit
    // by the scene (snow/sand/ash/pollen read grey at night, warm at dusk) except fireflies, whose
    // own cold light is the point. `size` = sprite diameter in world units.
    let (count, size, color, alpha, vel, sway, y_lo, y_hi) = match kind {
        ParticleKind::Snow => (520u32, 0.13, Color::srgb(0.90, 0.91, 0.93), 0.85, Vec3::new(0.0, -1.5, 0.0), 0.7, 0.0, 16.0),
        // Desert: a dense, fast, ground-to-overhead sheet of blown sand streaming sideways — with
        // the gust in `drift` it surges and lulls so the desert reads as genuinely windy. Fine
        // grains, not beads: small, low alpha, the colour of the dunes.
        ParticleKind::Dust => (420, 0.09, Color::srgb(0.70, 0.60, 0.44), 0.5, Vec3::new(2.6, 0.06, 1.0), 0.9, 0.05, 5.5),
        // Real fireflies: a couple of dozen tiny warm yellow-green points low over the marsh,
        // wandering slowly and blinking (see `drift`), only at dusk/night (alpha x `Dusk`).
        ParticleKind::Fireflies => (26, 0.16, Color::srgb(0.80, 0.86, 0.40), 1.0, Vec3::ZERO, 0.35, 0.35, 1.8),
        // Daylight pollen/dust drifting in the sun shafts — faint, lit, gone at night.
        ParticleKind::Pollen => (120, 0.05, Color::srgb(0.92, 0.88, 0.74), 0.45, Vec3::new(0.08, 0.12, 0.04), 0.4, 0.3, 5.0),
        // Blight ash: grey-black flakes drifting sideways and slowly rising off the burned mire.
        ParticleKind::Ash => (300, 0.10, Color::srgb(0.20, 0.19, 0.18), 0.7, Vec3::new(0.6, 0.35, 0.3), 0.6, 0.3, 8.0),
        ParticleKind::Mist => unreachable!("Mist spawns fog-bank cards, handled above"),
        ParticleKind::None => unreachable!("spawn is only called for an active weather kind"),
    };
    let fly = kind == ParticleKind::Fireflies;

    let mesh = meshes.add(soft_disc_mesh());
    // Always Blend (Add for the glowing fireflies) so the fade ramp can drive alpha.
    let mat = materials.add(if fly {
        StandardMaterial {
            // HDR so the point catches a whisper of bloom; Add sums overlapping glows like light.
            base_color: Color::LinearRgba(LinearRgba::from(color) * 2.4).with_alpha(0.0),
            unlit: true,
            alpha_mode: AlphaMode::Add,
            cull_mode: None,
            ..default()
        }
    } else {
        StandardMaterial {
            base_color: color.with_alpha(0.0), // starts invisible; the fade ramp brings it in
            perceptual_roughness: 1.0,
            reflectance: 0.0,
            alpha_mode: AlphaMode::Blend,
            cull_mode: None,
            ..default()
        }
    });

    for i in 0..count {
        let x = center.x + (h(i) * 2.0 - 1.0) * R;
        let z = center.z + (h(i + 7777) * 2.0 - 1.0) * R;
        let y = y_lo + h(i + 1234) * (y_hi - y_lo);
        let phase = h(i + 99) * std::f32::consts::TAU;
        // Per-instance velocity jitter so they don't move in lockstep (fireflies: a slow wander).
        let jv = if fly {
            Vec3::new((h(i + 11) - 0.5) * 0.5, 0.0, (h(i + 33) - 0.5) * 0.5)
        } else {
            Vec3::new((h(i + 11) - 0.5) * 0.4, (h(i + 22) - 0.5) * 0.15, (h(i + 33) - 0.5) * 0.4)
        };
        let s = size * (0.7 + h(i + 5) * 0.6);
        let tf = Transform::from_xyz(x, y, z).with_scale(Vec3::splat(s));
        commands.spawn((
            Mesh3d(mesh.clone()),
            MeshMaterial3d(mat.clone()),
            tf,
            Particle { vel: vel + jv, phase, sway, y_min: y_lo, y_max: y_hi, billboard: false, size: s, blink: fly },
            bevy::light::NotShadowCaster,
            BiomeEntity,
        ));
    }
    (mat, alpha)
}

/// A soft round alpha sprite (white RGB, alpha = smooth radial falloff) for the swamp fog cards —
/// a textured blob, so a big quad reads as a soft mist puff instead of a hard-edged rectangle.
fn soft_disc_image() -> Image {
    const PX: u32 = 64;
    let mut data = Vec::with_capacity((PX * PX * 4) as usize);
    for y in 0..PX {
        for x in 0..PX {
            let u = (x as f32 + 0.5) / PX as f32 * 2.0 - 1.0;
            let v = (y as f32 + 0.5) / PX as f32 * 2.0 - 1.0;
            let r = (u * u + v * v).sqrt();
            // 1 at the centre → 0 by the rim (clamped), then smoothstepped for an extra-soft edge.
            let s = (1.0 - ((r - 0.12) / 0.88).clamp(0.0, 1.0)).clamp(0.0, 1.0);
            let a = s * s * (3.0 - 2.0 * s);
            data.extend_from_slice(&[255, 255, 255, (a * 255.0) as u8]);
        }
    }
    Image::new(
        Extent3d { width: PX, height: PX, depth_or_array_layers: 1 },
        TextureDimension::D2,
        data,
        TextureFormat::Rgba8UnormSrgb,
        RenderAssetUsages::default(),
    )
}

/// Swamp mist: a handful of BIG soft-alpha cards hovering low over the mire, drifting slowly and
/// re-facing the camera each frame ([`drift`] yaws the `billboard` ones) — rolling ground-fog
/// banks, the body the mote-spheres never sold. One shared material; the weather fade drives its
/// alpha exactly like the mote fields, so it eases in/out at biome edges the same way.
fn spawn_fog_banks(
    commands: &mut Commands,
    meshes: &mut Assets<Mesh>,
    materials: &mut Assets<StandardMaterial>,
    images: &mut Assets<Image>,
    center: Vec3,
) -> (Handle<StandardMaterial>, f32) {
    const COUNT: u32 = 34;
    const FULL_ALPHA: f32 = 0.40;
    let tex = images.add(soft_disc_image());
    let mesh = meshes.add(Rectangle::new(1.0, 1.0)); // unit quad (XY plane, +Z normal), scaled per card
    let color = Color::srgb(0.55, 0.66, 0.53); // murky swamp green
    let mat = materials.add(StandardMaterial {
        base_color: color.with_alpha(0.0), // starts invisible; the fade ramp brings it in
        base_color_texture: Some(tex),
        unlit: true,
        alpha_mode: AlphaMode::Blend,
        cull_mode: None, // double-sided so the billboard shows from either face
        ..default()
    });
    for i in 0..COUNT {
        let x = center.x + (h(i) * 2.0 - 1.0) * R;
        let z = center.z + (h(i + 7777) * 2.0 - 1.0) * R;
        let y = 1.2 + h(i + 1234) * 2.6; // low, hugging the mire
        let scale = 7.0 + h(i + 5) * 7.0; // big, overlapping soft banks
        let drift = Vec3::new((h(i + 11) - 0.5) * 0.5, 0.0, (h(i + 33) - 0.5) * 0.5);
        commands.spawn((
            Mesh3d(mesh.clone()),
            MeshMaterial3d(mat.clone()),
            Transform::from_xyz(x, y, z).with_scale(Vec3::splat(scale)),
            Particle {
                vel: drift,
                phase: h(i + 99) * std::f32::consts::TAU,
                sway: 0.12,
                y_min: y, // vel.y == 0 → no vertical wrap; cards stay at their low band
                y_max: y,
                billboard: true,
                size: scale,
                blink: false,
            },
            bevy::light::NotShadowCaster,
            BiomeEntity,
        ));
    }
    (mat, FULL_ALPHA)
}

/// Drift + sway + wrap every particle within the box that follows the hero; `billboard` cards
/// (swamp fog banks) additionally yaw to face the camera each frame, kept upright.
fn drift(
    time: Res<Time>,
    center: Res<WeatherCenter>,
    cam_q: Query<&GlobalTransform, With<Camera3d>>,
    mut q: Query<(&Particle, &mut Transform)>,
) {
    let dt = time.delta_secs();
    let t = time.elapsed_secs_wrapped();
    let (cx, cz) = (center.0.x, center.0.y);
    let cam = cam_q.iter().next();
    let cam_pos = cam.map(|g| g.translation());
    let cam_rot = cam.map(|g| g.compute_transform().rotation);
    // A slow, layered gust on the *directional* wind (≈0.15× lull → ≈1.85× surge) so a steady
    // drift becomes gusty — the desert dust (big horizontal vel) heaves and slackens like real
    // wind. Snow/pollen/fireflies have little directional vel, so they're barely touched.
    let gust = 1.0 + 0.55 * (t * 0.27).sin() + 0.3 * (t * 0.11 + 1.3).sin();
    for (p, mut tf) in &mut q {
        // Sinusoidal horizontal sway layered on the gusting base velocity.
        let sx = (t * 1.3 + p.phase).sin() * p.sway;
        let sz = (t * 1.1 + p.phase * 1.7).cos() * p.sway;
        tf.translation.x += (p.vel.x * gust + sx) * dt;
        tf.translation.y += p.vel.y * dt;
        tf.translation.z += (p.vel.z * gust + sz) * dt;

        // Wrap vertically by travel direction; wrap horizontally within the moving box.
        if p.vel.y < 0.0 && tf.translation.y < p.y_min {
            tf.translation.y = p.y_max;
        } else if p.vel.y > 0.0 && tf.translation.y > p.y_max {
            tf.translation.y = p.y_min;
        }
        if tf.translation.x > cx + R {
            tf.translation.x = cx - R;
        } else if tf.translation.x < cx - R {
            tf.translation.x = cx + R;
        }
        if tf.translation.z > cz + R {
            tf.translation.z = cz - R;
        } else if tf.translation.z < cz - R {
            tf.translation.z = cz + R;
        }

        // Upright camera-facing billboard for fog cards: yaw so the quad's +Z normal points at the
        // camera (horizontal only, so the bank stays vertical). Motes keep their spawn rotation.
        if p.billboard {
            if let Some(cp) = cam_pos {
                let dir = cp - tf.translation;
                tf.rotation = Quat::from_rotation_y(dir.x.atan2(dir.z));
            }
        } else if let Some(r) = cam_rot {
            // Motes are soft round sprites: screen-aligned so they always show their round face.
            tf.rotation = r;
        }
        if p.blink {
            let b = firefly_blink(t, p.phase, 0.9 + (p.phase * 0.37).fract() * 0.8);
            tf.scale = Vec3::splat(p.size * b.max(0.001));
        }
    }
}
