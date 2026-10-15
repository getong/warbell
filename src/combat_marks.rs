//! **Combat ground marks** — the rings and pools a fight paints on the ground: the soft-lock target
//! ring (`player::softlock`), the kill / slam dust shockwave and the blood splats (`player::combat`),
//! and the battlefield's lingering stains + scorches (`aftermath`).
//!
//! They used to be flat `Annulus` / `Circle` meshes (12–40 hard segments, flat unlit amber or a
//! solid disc) — with the realistic PBR forest around them they read as low-poly stamps. Now every
//! mark is ONE flat quad drawn by `assets/shaders/ground_mark.wesl`, which builds the shape
//! analytically (feathered gaussian lines, noise-frayed edges, seeded satellite droplets), so there
//! is no polygon edge anywhere and no two pools are the same disc.
//!
//! Two shared material instances, one per blend recipe:
//! - [`MarkAssets::light`] (premultiplied, PBR-lit pale albedo) — target ring + shockwave. Lit by
//!   the same sun / moon / IBL / torches as the ground, so the ring is a quiet chalk-pale line by
//!   day and dims with the scene at night instead of glowing like the old emissive hoop.
//! - [`MarkAssets::stain`] (multiply) — blood + scorch. Darkens the already-lit ground, so a stain
//!   is never a glowing or pitch-black cut-out whatever the time of day.
//!
//! Per-mark state (kind, seed, fade alpha, shockwave age) is packed into the instance's
//! [`MeshTag`] by [`tag`]: every mark of a recipe shares one material + one quad, so the renderer
//! instances them into a single draw and a fading mark only rewrites a `u32` — no per-mark
//! material clone (the old splats / stains minted one `StandardMaterial` each and re-uploaded it
//! every fade step).

use bevy::mesh::MeshTag;
use bevy::pbr::{ExtendedMaterial, MaterialExtension, MaterialPlugin};
use bevy::prelude::*;
use bevy::render::render_resource::AsBindGroup;
use bevy::shader::ShaderRef;

const SHADER: &str = "shaders/ground_mark.wesl";

/// Positive depth bias so a mark lying on the courtyard cobble (an opaque slab at y≈0.04) wins the
/// depth tie instead of z-fighting it — same value + reason as `aftermath`'s old decals.
const MARK_DEPTH_BIAS: f32 = 50.0;

pub type MarkMaterial = ExtendedMaterial<StandardMaterial, MarkExt>;

/// No uniforms: the whole look is in the shader, the per-mark knobs ride the `MeshTag`.
#[derive(Asset, AsBindGroup, Clone, TypePath, Debug, Default)]
pub struct MarkExt {}

impl MaterialExtension for MarkExt {
    fn fragment_shader() -> ShaderRef {
        SHADER.into()
    }
}

/// What a mark draws as (the shader's `KIND_*`).
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum MarkKind {
    /// Soft-lock target ring — use with [`MarkAssets::light`].
    Ring = 0,
    /// Kill / slam dust shockwave — [`MarkAssets::light`].
    Shock = 1,
    /// Fresh blood pool / fleck — [`MarkAssets::stain`].
    Blood = 2,
    /// Dried, browner blood (the aftermath stain) — [`MarkAssets::stain`].
    BloodDry = 3,
    /// Shaman-bolt scorch — [`MarkAssets::stain`].
    Scorch = 4,
    /// Guardian-trial rune circle (`landmarks`) — [`MarkAssets::light`]; `aux` = hold progress,
    /// which kindles the glyphs into a dim ember glow. Drawn on a [`draped_disc`], not the quad.
    Rune = 5,
    /// Surveyed build plot (`town` build rings) — [`MarkAssets::light`]; `aux` ≥ 0.5 = targeted.
    Plot = 6,
    /// RTS move-order click-mark (`rts::ordermark`) — [`MarkAssets::light`].
    Order = 7,
    /// RTS selected-unit ring (`rts::teamcolor`) — [`MarkAssets::light`]; `aux` ≥ 0.5 = rival.
    Select = 8,
    /// RTS attack-order click-mark (muted rust) — [`MarkAssets::light`].
    OrderAttack = 9,
    /// A boot print pressed into mud / sand / snow (`footprints`) — [`MarkAssets::stain`]. Its
    /// `aux` byte is a bit field, not a 0..1 age: packed by [`boot_tag`].
    Boot = 10,
}

impl MarkKind {
    /// Whether this kind draws with the lit premultiplied [`MarkAssets::light`] recipe (vs the
    /// multiply [`MarkAssets::stain`]).
    pub fn is_light(self) -> bool {
        !matches!(self, MarkKind::Blood | MarkKind::BloodDry | MarkKind::Scorch | MarkKind::Boot)
    }
}

/// A ground-mark disc DRAPED over the terrain: a `res`×`res` grid spanning `diameter` around
/// `centre` (world XZ), each vertex sampled from `worldmap::ground_at_world` + `lift`, with UVs
/// 0..1 like the shared quad. For marks too large to lie flat (the 16u rune circle on a slope
/// would bury half a flat quad). Positions are relative to `(centre.x, base_y, centre.y)`, which
/// is returned so the caller can place the entity there.
pub fn draped_disc(centre: Vec2, diameter: f32, res: u32, lift: f32) -> (Mesh, Vec3) {
    use bevy::asset::RenderAssetUsages;
    use bevy::mesh::{Indices, PrimitiveTopology};
    let base_y = crate::worldmap::ground_at_world(centre.x, centre.y).unwrap_or(0.0);
    let n = res.max(2);
    let mut pos = Vec::with_capacity(((n + 1) * (n + 1)) as usize);
    let mut uv = Vec::with_capacity(pos.capacity());
    for j in 0..=n {
        for i in 0..=n {
            let u = i as f32 / n as f32;
            let v = j as f32 / n as f32;
            let x = (u - 0.5) * diameter;
            let z = (v - 0.5) * diameter;
            let y = crate::worldmap::ground_at_world(centre.x + x, centre.y + z).unwrap_or(base_y) + lift;
            pos.push([x, y - base_y, z]);
            uv.push([u, v]);
        }
    }
    let mut idx = Vec::with_capacity((n * n * 6) as usize);
    for j in 0..n {
        for i in 0..n {
            let a = j * (n + 1) + i;
            let b = a + 1;
            let c = a + n + 1;
            let d = c + 1;
            idx.extend_from_slice(&[a, c, b, b, c, d]);
        }
    }
    let mut mesh = Mesh::new(PrimitiveTopology::TriangleList, RenderAssetUsages::default())
        .with_inserted_attribute(Mesh::ATTRIBUTE_POSITION, pos)
        .with_inserted_attribute(Mesh::ATTRIBUTE_UV_0, uv)
        .with_inserted_indices(Indices::U32(idx));
    mesh.compute_smooth_normals();
    (mesh, Vec3::new(centre.x, base_y, centre.y))
}

/// Pack a mark's per-instance state for `ground_mark.wgsl`: `alpha` (0..1 strength), `kind`, a
/// shape `seed` (any u32 — only its low byte is used), and `aux` (0..1, the shockwave's age).
pub fn tag(kind: MarkKind, alpha: f32, seed: u32, aux: f32) -> MeshTag {
    let a = (alpha.clamp(0.0, 1.0) * 255.0).round() as u32;
    let x = (aux.clamp(0.0, 1.0) * 255.0).round() as u32;
    MeshTag::new(a | (kind as u32) << 8 | (seed & 0xff) << 12 | x << 20)
}

/// [`tag`] for a [`MarkKind::Boot`] print: `aux` carries bit fields instead of a 0..1 value —
/// bits 0-1 the ground (`0` mud, `1` sand, `2` snow), bit 2 a LEFT boot (the shader mirrors the
/// sole), bit 3 a sprinting push-off (toe dug in, spoil thrown back).
pub fn boot_tag(alpha: f32, seed: u32, ground: u32, left: bool, sprint: bool) -> MeshTag {
    let a = (alpha.clamp(0.0, 1.0) * 255.0).round() as u32;
    let aux = (ground & 3) | (left as u32) << 2 | (sprint as u32) << 3;
    MeshTag::new(a | (MarkKind::Boot as u32) << 8 | (seed & 0xff) << 12 | aux << 20)
}

/// The shared quad + the two material recipes. Every mark spawns `Mesh3d(quad)` with one of them.
#[derive(Resource, Clone)]
pub struct MarkAssets {
    /// Unit flat quad in XZ (normal +Y, spans ±0.5) — scale it to the mark's world diameter.
    pub quad: Handle<Mesh>,
    /// Lit, premultiplied: target ring + shockwave.
    pub light: Handle<MarkMaterial>,
    /// Multiply: blood + scorch.
    pub stain: Handle<MarkMaterial>,
}

fn setup(mut commands: Commands, mut meshes: ResMut<Assets<Mesh>>, mut mats: ResMut<Assets<MarkMaterial>>) {
    let quad = meshes.add(Plane3d::new(Vec3::Y, Vec2::splat(0.5)).mesh().build());
    let base = |alpha_mode: AlphaMode| StandardMaterial {
        base_color: Color::WHITE, // the shader writes the albedo
        // Bone-dry matte: no specular glint off a chalk line or a pool of dust.
        perceptual_roughness: 1.0,
        reflectance: 0.2,
        alpha_mode,
        depth_bias: MARK_DEPTH_BIAS,
        ..default()
    };
    let light = mats.add(ExtendedMaterial { base: base(AlphaMode::Premultiplied), extension: MarkExt {} });
    let stain = mats.add(ExtendedMaterial { base: base(AlphaMode::Multiply), extension: MarkExt {} });
    commands.insert_resource(MarkAssets { quad, light, stain });
}

/// A mark that fades (and optionally grows) over its life, then despawns — the shockwave and the
/// combat blood splats. Drives scale + the tag's alpha/age; the material is never touched.
#[derive(Component)]
pub struct MarkFade {
    pub kind: MarkKind,
    pub seed: u32,
    pub born: f32,
    /// Seconds at full strength before the fade starts.
    pub hold: f32,
    /// Seconds the fade (and the growth) takes after the hold.
    pub life: f32,
    pub a0: f32,
    /// World diameter at birth → at the end of the growth (equal = a static pool).
    pub s0: f32,
    pub s1: f32,
}

/// Spawn a ground mark at `at` (world, already on the ground). `yaw` spins the quad so seeded
/// shapes don't all face one way; `squash` (≤1) stretches a pool along one axis.
#[allow(clippy::too_many_arguments)]
pub fn spawn_mark(
    commands: &mut Commands,
    marks: &MarkAssets,
    kind: MarkKind,
    at: Vec3,
    diameter: f32,
    yaw: f32,
    squash: f32,
    alpha: f32,
    seed: u32,
) -> Entity {
    let mat = if kind.is_light() { marks.light.clone() } else { marks.stain.clone() };
    commands
        .spawn((
            Mesh3d(marks.quad.clone()),
            MeshMaterial3d(mat),
            Transform {
                translation: at,
                rotation: Quat::from_rotation_y(yaw),
                scale: Vec3::new(diameter, 1.0, diameter * squash),
            },
            tag(kind, alpha, seed, 0.0),
            // Casts nothing, but RECEIVES: the lit ring/dust darken under a foe's shadow exactly
            // like the ground they lie on (the multiply stains inherit the ground's shading anyway).
            bevy::light::NotShadowCaster,
        ))
        .id()
}

/// Drive every [`MarkFade`]: ease the diameter out `s0 → s1`, hold then drain the alpha, age the
/// shockwave's fray, and reap at the end. Only writes the tag when its packed value moves.
fn drive_mark_fades(
    time: Res<Time>,
    mut commands: Commands,
    mut q: Query<(Entity, &MarkFade, &mut Transform, &mut MeshTag)>,
) {
    let now = time.elapsed_secs();
    for (e, f, mut tf, mut mt) in &mut q {
        let t = now - f.born;
        let k = ((t - f.hold) / f.life.max(1e-3)).clamp(0.0, 1.0);
        if t >= f.hold + f.life {
            // `try_despawn`: marks are `BiomeEntity`, so a rebuild can wipe one the same frame.
            commands.entity(e).try_despawn();
            continue;
        }
        let grow = (t / (f.hold + f.life).max(1e-3)).clamp(0.0, 1.0);
        let ease = 1.0 - (1.0 - grow) * (1.0 - grow);
        let s = f.s0 + (f.s1 - f.s0) * ease;
        let squash = tf.scale.z / tf.scale.x.max(1e-4);
        tf.scale = Vec3::new(s, 1.0, s * squash);
        let want = tag(f.kind, f.a0 * (1.0 - k * k * (3.0 - 2.0 * k)), f.seed, grow);
        if mt.value != want.value {
            mt.value = want.value;
        }
    }
}

pub struct CombatMarksPlugin;

impl Plugin for CombatMarksPlugin {
    fn build(&self, app: &mut App) {
        app.add_plugins(MaterialPlugin::<MarkMaterial>::default())
            // PreStartup so every `Startup` spawner (the soft-lock ring, `CombatFx`) can take the
            // shared handles without an ordering edge.
            .add_systems(PreStartup, setup)
            .add_systems(Update, drive_mark_fades);
    }
}
