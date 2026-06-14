//! **Realistic textured tree (POC)** — a proof-of-concept tree that deliberately breaks
//! the project's low-poly / single-white-material convention to explore a *photographic*
//! look built from web textures (CC0 from ambientCG: `Bark012` + `LeafSet024`).
//!
//! Unlike the batched primitive props in `trees.rs` (one shared white material, colour
//! baked into vertices), this tree owns **two textured materials**:
//!   - a smooth, normal-mapped **bark** trunk/branch skeleton (one merged mesh of tapered
//!     conical-frustum segments grown recursively), and
//!   - a **canopy** of a few hundred alpha-masked **leaf cards** — quads each UV-mapped to
//!     one cell of the 3×3 leaf atlas, scattered over the crown and clustered at branch
//!     tips. The classic real-time "leaf instancing" approach: many cutout quads read as a
//!     full, soft canopy far more convincingly than blob spheres.
//!
//! It is gated behind `FOREST_TREE` so it only appears when staging a POC screenshot and
//! never touches normal gameplay. `FOREST_TREE=1` drops it at a default open spot;
//! `FOREST_TREE="x,z"` places it at a world XZ. Frame it with `FOREST_CAM` + `FOREST_SHOT`.

use bevy::asset::RenderAssetUsages;
use bevy::camera::visibility::{RenderLayers, VisibilityRange};
use bevy::camera::{RenderTarget, ScalingMode};
use bevy::core_pipeline::tonemapping::Tonemapping;
use bevy::light::NotShadowCaster;
use bevy::mesh::{Indices, PrimitiveTopology};
use bevy::prelude::*;
use bevy::render::render_resource::{Extent3d, TextureDimension, TextureFormat, TextureUsages};
use bevy::render::view::screenshot::{save_to_disk, Screenshot};

/// Final tree height (world units): the ~2u scatter trees in `biome_forest`.
const TARGET_H: f32 = 2.1;
/// Billboard bake frame height (world units), base-aligned so the impostor quad lines the
/// 3D model up exactly at the LOD swap distance.
const FRAME_H: f32 = 2.4;

pub struct RealTreePlugin;

impl Plugin for RealTreePlugin {
    fn build(&self, app: &mut App) {
        if std::env::var("FOREST_TREE").is_ok() {
            app.add_systems(Startup, spawn_real_tree);
        }
        // bake one variant's billboard impostor to a transparent PNG (offline tool)
        if std::env::var("FOREST_TREE_BAKE").is_ok() {
            app.add_systems(Startup, bake_setup)
                .add_systems(Update, drive_bake);
        }
        // LOD slice: near = full 3D model, far = baked billboard, VisibilityRange crossfade
        if std::env::var("FOREST_TREE_LOD").is_ok() {
            app.add_systems(Startup, spawn_lod_demo)
                .add_systems(Update, face_camera);
        }
    }
}

// ── deterministic tiny RNG (xorshift) so the tree is reproducible per screenshot ────────
struct Rng(u32);
impl Rng {
    fn next_u32(&mut self) -> u32 {
        let mut x = self.0;
        x ^= x << 13;
        x ^= x >> 17;
        x ^= x << 5;
        self.0 = x;
        x
    }
    /// uniform 0.0..1.0
    fn f(&mut self) -> f32 {
        (self.next_u32() >> 8) as f32 / (1u32 << 24) as f32
    }
    /// uniform lo..hi
    fn range(&mut self, lo: f32, hi: f32) -> f32 {
        lo + (hi - lo) * self.f()
    }
}

// ── branch skeleton → one merged, UV-scaled, tangent-bearing bark mesh ──────────────────

/// Append one tapered segment (a conical frustum, base at `from`, growing along `dir`) to
/// `parts`, with bark UVs tiled ~`u_tiles` around and proportional to length along it.
fn segment(parts: &mut Vec<Mesh>, from: Vec3, dir: Vec3, len: f32, r0: f32, r1: f32) {
    let frustum = ConicalFrustum {
        radius_top: r1,
        radius_bottom: r0,
        height: len,
    };
    let mut m = frustum.mesh().resolution(10).build();
    // bark tiling: ~2 wraps around, repeat along height by length so bark doesn't smear
    scale_uv(&mut m, 2.0, len * 1.1);
    // primitive frustum is centred on origin along +Y; lift so its base sits at y=0,
    // rotate +Y → dir, then move the base to `from`.
    let m = m
        .translated_by(Vec3::Y * len * 0.5)
        .rotated_by(Quat::from_rotation_arc(Vec3::Y, dir.normalize()))
        .translated_by(from);
    parts.push(m);
}

/// Scale the UV_0 attribute in place (tile the bark texture).
fn scale_uv(m: &mut Mesh, su: f32, sv: f32) {
    use bevy::mesh::VertexAttributeValues as V;
    if let Some(V::Float32x2(uvs)) = m.attribute_mut(Mesh::ATTRIBUTE_UV_0) {
        for uv in uvs.iter_mut() {
            uv[0] *= su;
            uv[1] *= sv;
        }
    }
}

/// Grow the branch skeleton recursively. Each call adds its own segment, records its tip
/// (for leaf clustering), and forks 2–3 children that bend away with some upward bias.
#[allow(clippy::too_many_arguments)]
fn grow(
    parts: &mut Vec<Mesh>,
    tips: &mut Vec<Vec3>,
    rng: &mut Rng,
    from: Vec3,
    dir: Vec3,
    len: f32,
    r0: f32,
    depth: u32,
) {
    let r1 = r0 * 0.72; // taper toward the tip
    segment(parts, from, dir, len, r0, r1);
    let tip = from + dir * len;

    if depth == 0 || r1 < 0.03 {
        tips.push(tip); // a thin terminal twig → cluster leaves here
        return;
    }
    // deeper branches also drop a few leaves along their length, not just at the very ends
    if depth <= 2 {
        tips.push(tip);
    }

    let children = if depth >= 4 { 2 } else { rng.next_u32() % 2 + 2 };
    for _ in 0..children {
        // bend away from the parent: random yaw around the parent dir + a spread tilt,
        // with a steady upward bias so the crown lifts rather than droops.
        let yaw = rng.range(0.0, std::f32::consts::TAU);
        let tilt = rng.range(0.45, 0.95);
        let basis = Quat::from_rotation_arc(Vec3::Y, dir.normalize());
        let local = Quat::from_rotation_y(yaw) * Quat::from_rotation_x(tilt);
        let mut child = (basis * local) * Vec3::Y;
        child = (child + Vec3::Y * 0.55).normalize(); // upward bias
        let child_len = len * rng.range(0.68, 0.82);
        grow(parts, tips, rng, tip, child, child_len, r1, depth - 1);
    }
}

// ── leaf cards ──────────────────────────────────────────────────────────────────────

/// One leaf quad (two tris, double-sided handled by the material) at `center`, sized `size`,
/// oriented by `rot`, UV-mapped to atlas cell (`cx`,`cy`) of a 3×3 grid. Appends into the
/// shared position/normal/uv/index buffers.
#[allow(clippy::too_many_arguments)]
fn leaf_quad(
    pos: &mut Vec<[f32; 3]>,
    nor: &mut Vec<[f32; 3]>,
    uv: &mut Vec<[f32; 2]>,
    idx: &mut Vec<u32>,
    center: Vec3,
    size: f32,
    rot: Quat,
    cx: u32,
    cy: u32,
) {
    let base = pos.len() as u32;
    let hw = size * 0.5;
    let h = size; // leaves slightly taller than wide
    // local quad in XY plane, pivot at the stem (bottom-centre) so leaves hang off twigs
    let corners = [
        Vec3::new(-hw, 0.0, 0.0),
        Vec3::new(hw, 0.0, 0.0),
        Vec3::new(hw, h, 0.0),
        Vec3::new(-hw, h, 0.0),
    ];
    let n = rot * Vec3::Z;
    let c = 1.0 / 3.0;
    let (u0, v0) = (cx as f32 * c, cy as f32 * c);
    // atlas leaf points DOWN in the texture (stem at bottom), so v grows downward
    let uvs = [
        [u0, v0 + c],
        [u0 + c, v0 + c],
        [u0 + c, v0],
        [u0, v0],
    ];
    for (k, corner) in corners.iter().enumerate() {
        pos.push((center + rot * *corner).to_array());
        nor.push(n.to_array());
        uv.push(uvs[k]);
    }
    idx.extend_from_slice(&[base, base + 1, base + 2, base, base + 2, base + 3]);
}

/// Build the canopy mesh: `density` leaves clustered around every recorded branch tip, each
/// a random atlas cell at a random orientation, sized within `leaf` (min,max).
fn build_canopy(tips: &[Vec3], rng: &mut Rng, density: u32, leaf: (f32, f32)) -> Mesh {
    let mut pos = Vec::new();
    let mut nor = Vec::new();
    let mut uv = Vec::new();
    let mut idx = Vec::new();

    for &tip in tips {
        let n = density + rng.next_u32() % (density / 2).max(1);
        for _ in 0..n {
            let off = Vec3::new(
                rng.range(-0.6, 0.6),
                rng.range(-0.35, 0.7),
                rng.range(-0.6, 0.6),
            );
            let rot = Quat::from_euler(
                EulerRot::YXZ,
                rng.range(0.0, std::f32::consts::TAU),
                rng.range(-1.2, 1.2),
                rng.range(-0.6, 0.6),
            );
            let cell = rng.next_u32() % 9;
            leaf_quad(
                &mut pos,
                &mut nor,
                &mut uv,
                &mut idx,
                tip + off,
                rng.range(leaf.0, leaf.1),
                rot,
                cell % 3,
                cell / 3,
            );
        }
    }

    let mut m = Mesh::new(PrimitiveTopology::TriangleList, RenderAssetUsages::default());
    m.insert_attribute(Mesh::ATTRIBUTE_POSITION, pos);
    m.insert_attribute(Mesh::ATTRIBUTE_NORMAL, nor);
    m.insert_attribute(Mesh::ATTRIBUTE_UV_0, uv);
    m.insert_indices(Indices::U32(idx));
    m
}

// ── variants ──────────────────────────────────────────────────────────────────────

/// A tree "species": shape knobs + a canopy tint, all normalised to one final height so
/// every variant matches the scatter trees regardless of its natural proportions.
struct Variant {
    name: &'static str,
    seed: u32,
    trunk_h: f32,    // base trunk before the crown forks
    trunk_r: f32,    // base trunk radius
    branch_len: f32, // first crown branch length
    depth: u32,      // recursion depth → crown bushiness
    lean: Vec3,      // initial crown direction (un-normalised)
    leaf_tint: Color,
    leaf_size: (f32, f32),
    density: u32, // leaves per branch tip
}

/// Five species spanning broad/slender shapes and a seasonal colour spread.
fn variants() -> [Variant; 5] {
    [
    Variant {
        name: "oak (broad green)",
        seed: 0x51ED_7A2C,
        trunk_h: 1.6,
        trunk_r: 0.34,
        branch_len: 1.35,
        depth: 6,
        lean: Vec3::new(0.04, 1.0, 0.02),
        leaf_tint: Color::srgb(0.80, 0.92, 0.70),
        leaf_size: (0.5, 0.82),
        density: 18,
    },
    Variant {
        name: "birch (slender pale-green)",
        seed: 0x1A2B_3C4D,
        trunk_h: 2.3,
        trunk_r: 0.24,
        branch_len: 1.05,
        depth: 5,
        lean: Vec3::new(-0.05, 1.0, 0.03),
        leaf_tint: Color::srgb(0.92, 0.98, 0.72),
        leaf_size: (0.42, 0.66),
        density: 14,
    },
    Variant {
        name: "maple (autumn gold)",
        seed: 0x77AA_BB11,
        trunk_h: 1.5,
        trunk_r: 0.36,
        branch_len: 1.4,
        depth: 6,
        lean: Vec3::new(0.06, 1.0, -0.04),
        leaf_tint: Color::srgb(1.10, 0.74, 0.34),
        leaf_size: (0.55, 0.9),
        density: 20,
    },
    Variant {
        name: "spruce-ish (deep cool green)",
        seed: 0x0BAD_F00D,
        trunk_h: 1.9,
        trunk_r: 0.3,
        branch_len: 1.15,
        depth: 6,
        lean: Vec3::new(0.0, 1.0, 0.0),
        leaf_tint: Color::srgb(0.58, 0.80, 0.58),
        leaf_size: (0.46, 0.72),
        density: 16,
    },
    Variant {
        name: "sapling (small fresh green)",
        seed: 0xC0FF_EE42,
        trunk_h: 1.3,
        trunk_r: 0.22,
        branch_len: 1.0,
        depth: 5,
        lean: Vec3::new(-0.08, 1.0, -0.05),
        leaf_tint: Color::srgb(0.74, 0.96, 0.56),
        leaf_size: (0.4, 0.62),
        density: 14,
    },
    ]
}

// ── reusable build helpers ────────────────────────────────────────────────────────────

/// Highest y across a mesh's vertices (its AABB top), for height normalisation.
fn mesh_top(m: &Mesh) -> f32 {
    use bevy::mesh::VertexAttributeValues as V;
    if let Some(V::Float32x3(pos)) = m.attribute(Mesh::ATTRIBUTE_POSITION) {
        pos.iter().map(|p| p[1]).fold(0.0, f32::max)
    } else {
        1.0
    }
}

/// Build a variant's `(bark, canopy)` meshes plus the uniform scale that normalises the
/// tree to [`TARGET_H`]. Deterministic per `Variant::seed`.
fn build_variant(v: &Variant) -> (Mesh, Mesh, f32) {
    let mut rng = Rng(v.seed);
    let mut parts = Vec::new();
    let mut tips = Vec::new();

    segment(&mut parts, Vec3::ZERO, Vec3::Y, v.trunk_h, v.trunk_r, v.trunk_r * 0.82);
    grow(
        &mut parts,
        &mut tips,
        &mut rng,
        Vec3::Y * v.trunk_h,
        v.lean.normalize(),
        v.branch_len,
        v.trunk_r * 0.82,
        v.depth,
    );

    let mut bark = parts
        .into_iter()
        .reduce(|mut a, b| {
            a.merge(&b).expect("bark parts share attributes");
            a
        })
        .expect("at least the trunk");
    if let Err(e) = bark.generate_tangents() {
        warn!("realtree[{}]: tangent generation failed ({e:?})", v.name);
    }

    let canopy = build_canopy(&tips, &mut rng, v.density, v.leaf_size);
    let natural_h = mesh_top(&bark).max(mesh_top(&canopy)).max(0.01);
    (bark, canopy, TARGET_H / natural_h)
}

/// The shared normal-mapped bark material.
fn bark_material(assets: &AssetServer, mats: &mut Assets<StandardMaterial>) -> Handle<StandardMaterial> {
    mats.add(StandardMaterial {
        base_color: Color::WHITE,
        base_color_texture: Some(assets.load("textures/tree/bark_color.png")),
        normal_map_texture: Some(assets.load("textures/tree/bark_normal.png")),
        perceptual_roughness: 0.9,
        ..default()
    })
}

/// A per-variant tinted, alpha-cutout leaf-card material.
fn leaf_material(tint: Color, tex: Handle<Image>, mats: &mut Assets<StandardMaterial>) -> Handle<StandardMaterial> {
    mats.add(StandardMaterial {
        base_color: tint,
        base_color_texture: Some(tex),
        perceptual_roughness: 0.75,
        alpha_mode: AlphaMode::Mask(0.5),
        cull_mode: None,
        double_sided: true,
        ..default()
    })
}

// ── spawn: the FOREST_TREE variant row ────────────────────────────────────────────────

fn spawn_real_tree(
    mut commands: Commands,
    mut meshes: ResMut<Assets<Mesh>>,
    mut mats: ResMut<Assets<StandardMaterial>>,
    assets: Res<AssetServer>,
) {
    // placement: FOREST_TREE="x,z" centres the variant row; "1"/anything else → default spot
    let (cx, cz) = std::env::var("FOREST_TREE")
        .ok()
        .and_then(|s| {
            let p: Vec<f32> = s.split(',').filter_map(|t| t.trim().parse().ok()).collect();
            (p.len() == 2).then(|| (p[0], p[1]))
        })
        .unwrap_or((0.0, 16.0));

    const SPACING: f32 = 2.6;
    let bark_mat = bark_material(&assets, &mut mats);
    let leaf_tex = assets.load("textures/tree/leaf.png");

    let vs = variants();
    let n = vs.len();
    for (i, v) in vs.iter().enumerate() {
        let (bark, canopy, scale) = build_variant(v);
        let leaf_mat = leaf_material(v.leaf_tint, leaf_tex.clone(), &mut mats);

        // lay the variants out in a row, centred on (cx,cz)
        let x = cx + (i as f32 - (n as f32 - 1.0) * 0.5) * SPACING;
        commands
            .spawn((
                Name::new(format!("RealTree POC: {}", v.name)),
                Transform::from_translation(Vec3::new(x, 0.0, cz)).with_scale(Vec3::splat(scale)),
                Visibility::Visible,
            ))
            .with_children(|p| {
                p.spawn((Mesh3d(meshes.add(bark)), MeshMaterial3d(bark_mat.clone())));
                p.spawn((
                    Mesh3d(meshes.add(canopy)),
                    MeshMaterial3d(leaf_mat),
                    NotShadowCaster, // many cutout tris aren't worth the shadow pass
                ));
            });
    }
}

// ── billboard baker (offline impostor tool) ───────────────────────────────────────────
//
// `FOREST_TREE_BAKE=path.png` (+ optional `FOREST_TREE_VARIANT=<0..4>`) renders ONE variant
// to a transparent PNG: the tree is placed on a private render layer, an orthographic camera
// on that same layer renders it (and only it) to an off-screen image with a transparent
// clear colour, and we screenshot that image. The resulting cutout is the far-LOD impostor.

#[derive(Resource)]
struct BakeTarget {
    image: Handle<Image>,
    path: String,
    clock: u32,
}

fn bake_setup(
    mut commands: Commands,
    mut meshes: ResMut<Assets<Mesh>>,
    mut mats: ResMut<Assets<StandardMaterial>>,
    mut images: ResMut<Assets<Image>>,
    assets: Res<AssetServer>,
) {
    let path = std::env::var("FOREST_TREE_BAKE").unwrap_or_else(|_| "billboard.png".into());
    let vi = std::env::var("FOREST_TREE_VARIANT")
        .ok()
        .and_then(|s| s.trim().parse::<usize>().ok())
        .unwrap_or(0);
    let vs = variants();
    let v = &vs[vi.min(vs.len() - 1)];

    // off-screen RGBA target the bake camera renders to (and we screenshot)
    const SIZE: u32 = 1024;
    let mut img = Image::new_fill(
        Extent3d { width: SIZE, height: SIZE, depth_or_array_layers: 1 },
        TextureDimension::D2,
        &[0, 0, 0, 0],
        TextureFormat::Rgba8UnormSrgb,
        RenderAssetUsages::default(),
    );
    img.texture_descriptor.usage =
        TextureUsages::RENDER_ATTACHMENT | TextureUsages::COPY_SRC | TextureUsages::TEXTURE_BINDING;
    let image = images.add(img);

    // the tree, on its own render layer so the world/sky never bleed into the cutout
    let layer = RenderLayers::layer(1);
    let (bark, canopy, scale) = build_variant(v);
    let bark_mat = bark_material(&assets, &mut mats);
    let leaf_mat = leaf_material(v.leaf_tint, assets.load("textures/tree/leaf.png"), &mut mats);
    commands
        .spawn((
            Transform::from_scale(Vec3::splat(scale)),
            Visibility::Visible,
            layer.clone(),
        ))
        .with_children(|p| {
            p.spawn((Mesh3d(meshes.add(bark)), MeshMaterial3d(bark_mat), layer.clone()));
            p.spawn((Mesh3d(meshes.add(canopy)), MeshMaterial3d(leaf_mat), layer.clone()));
        });

    // a private sun for the layer (the world's DirectionalLight is on layer 0)
    commands.spawn((
        DirectionalLight { illuminance: 9000.0, ..default() },
        Transform::from_rotation(Quat::from_euler(EulerRot::YXZ, -0.6, -0.9, 0.0)),
        layer.clone(),
    ));

    // orthographic camera: frame y∈[0,FRAME_H] (base-aligned), transparent clear
    commands.spawn((
        Camera3d::default(),
        Camera {
            clear_color: ClearColorConfig::Custom(Color::NONE),
            order: -1,
            ..default()
        },
        RenderTarget::Image(image.clone().into()),
        Projection::from(OrthographicProjection {
            scaling_mode: ScalingMode::FixedVertical { viewport_height: FRAME_H },
            ..OrthographicProjection::default_3d()
        }),
        Tonemapping::None,
        Transform::from_xyz(0.0, FRAME_H * 0.5, 12.0).looking_at(Vec3::new(0.0, FRAME_H * 0.5, 0.0), Vec3::Y),
        layer,
    ));

    commands.insert_resource(BakeTarget { image, path, clock: 0 });
}

fn drive_bake(
    mut bake: ResMut<BakeTarget>,
    mut commands: Commands,
    mut exit: MessageWriter<AppExit>,
) {
    bake.clock += 1;
    // let the scene/IBL settle, then capture the off-screen image and save it
    if bake.clock == 60 {
        let path = bake.path.clone();
        info!("realtree: baking billboard → {path}");
        commands
            .spawn(Screenshot::image(bake.image.clone()))
            .observe(save_to_disk(path));
    }
    if bake.clock > 90 {
        exit.write(AppExit::Success);
    }
}

// ── LOD demo: near = 3D model, far = baked billboard, VisibilityRange crossfade ────────

/// A camera-facing impostor quad (yaw only) tagged for [`face_camera`].
#[derive(Component)]
struct Billboard;

fn spawn_lod_demo(
    mut commands: Commands,
    mut meshes: ResMut<Assets<Mesh>>,
    mut mats: ResMut<Assets<StandardMaterial>>,
    assets: Res<AssetServer>,
) {
    // centre of the receding row; same default open spot as the bake/showcase
    let (cx, cz) = std::env::var("FOREST_TREE_LOD")
        .ok()
        .and_then(|s| {
            let p: Vec<f32> = s.split(',').filter_map(|t| t.trim().parse().ok()).collect();
            (p.len() == 2).then(|| (p[0], p[1]))
        })
        .unwrap_or((0.0, -42.0));

    // LOD switch distance + crossfade half-width (camera→tree, world units)
    const R: f32 = 18.0;
    const F: f32 = 2.5;
    // higher LOD's end == lower LOD's start, so the dither crossfade lines up (Bevy docs)
    let full_range = VisibilityRange { start_margin: 0.0..0.0, end_margin: (R - F)..(R + F), use_aabb: false };
    let bill_range = VisibilityRange { start_margin: (R - F)..(R + F), end_margin: 400.0..400.0, use_aabb: false };

    // one variant for the slice so the only visible difference is model vs. impostor
    let v = &variants()[0];
    let (bark, canopy, scale) = build_variant(v);
    let bark_h = meshes.add(bark);
    let canopy_h = meshes.add(canopy);
    let bark_mat = bark_material(&assets, &mut mats);
    let leaf_mat = leaf_material(v.leaf_tint, assets.load("textures/tree/leaf.png"), &mut mats);

    // billboard quad (base-aligned, FRAME_H square) + its baked impostor texture
    let bill_mesh = meshes.add(billboard_quad());
    let bill_mat = mats.add(StandardMaterial {
        base_color: Color::WHITE,
        base_color_texture: Some(assets.load("textures/tree/billboard_oak.png")),
        alpha_mode: AlphaMode::Mask(0.5),
        cull_mode: None,
        double_sided: true,
        perceptual_roughness: 0.9,
        ..default()
    });

    // Stage the demo on its own flat platform lifted high above the map, so the LOD ramp
    // frames cleanly against sky instead of fighting the real island's uneven terrain.
    let base = Vec3::new(cx, 100.0, cz);
    let ground_mat = mats.add(StandardMaterial {
        base_color: Color::srgb(0.34, 0.55, 0.24),
        perceptual_roughness: 1.0,
        ..default()
    });
    commands.spawn((
        Name::new("LOD demo ground"),
        Mesh3d(meshes.add(Cuboid::new(30.0, 0.4, 10.0))),
        MeshMaterial3d(ground_mat),
        Transform::from_translation(base - Vec3::Y * 0.2),
    ));

    // a line of identical trees marching away along +X; viewed from the near end they form
    // a monotonic distance ramp so one frame captures the full model→impostor handoff.
    for k in 0..7 {
        let pos = base + Vec3::new((k as f32 - 3.0) * 3.0, 0.0, 0.0);
        // full model (scaled), fades out past R
        commands
            .spawn((
                Name::new("LOD full"),
                Transform::from_translation(pos).with_scale(Vec3::splat(scale)),
                Visibility::Visible,
                full_range.clone(),
            ))
            .with_children(|p| {
                p.spawn((Mesh3d(bark_h.clone()), MeshMaterial3d(bark_mat.clone())));
                p.spawn((Mesh3d(canopy_h.clone()), MeshMaterial3d(leaf_mat.clone()), NotShadowCaster));
            });
        // impostor (unscaled — quad already authored in world units), fades in past R
        commands.spawn((
            Name::new("LOD billboard"),
            Mesh3d(bill_mesh.clone()),
            MeshMaterial3d(bill_mat.clone()),
            Transform::from_translation(pos),
            bill_range.clone(),
            Billboard,
            NotShadowCaster,
        ));
    }
}

/// A base-aligned quad in the XY plane, `FRAME_H` tall and wide, UV 0..1 (v flipped so the
/// baked image is upright). Matches the bake camera framing so the impostor overlays the
/// 3D model exactly at the swap distance.
fn billboard_quad() -> Mesh {
    let h = FRAME_H;
    let hw = FRAME_H * 0.5;
    let pos = vec![[-hw, 0.0, 0.0], [hw, 0.0, 0.0], [hw, h, 0.0], [-hw, h, 0.0]];
    let nor = vec![[0.0, 0.0, 1.0]; 4];
    let uv = vec![[0.0, 1.0], [1.0, 1.0], [1.0, 0.0], [0.0, 0.0]];
    let mut m = Mesh::new(PrimitiveTopology::TriangleList, RenderAssetUsages::default());
    m.insert_attribute(Mesh::ATTRIBUTE_POSITION, pos);
    m.insert_attribute(Mesh::ATTRIBUTE_NORMAL, nor);
    m.insert_attribute(Mesh::ATTRIBUTE_UV_0, uv);
    m.insert_indices(Indices::U32(vec![0, 1, 2, 0, 2, 3]));
    m
}

/// Yaw every [`Billboard`] to face the camera (impostors are flat, so they must turn).
fn face_camera(
    cam: Query<&GlobalTransform, With<Camera3d>>,
    mut bills: Query<&mut Transform, With<Billboard>>,
) {
    let Ok(cam) = cam.single() else { return };
    let cp = cam.translation();
    for mut t in &mut bills {
        let d = cp - t.translation;
        let yaw = d.x.atan2(d.z);
        t.rotation = Quat::from_rotation_y(yaw);
    }
}
