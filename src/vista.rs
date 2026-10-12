//! **Vista pass** (map-character overhaul pass 5) — the "miejsca w które się można wpatrywać":
//! a WATERFALL plunging off the head wall of the rock range's SW valley toward the lake (the
//! island's one moving landmark — motion + white water pull the eye from the whole south), and
//! three authored OVERLOOK spots — a framing prop (crooked lone pine + sitting stone + cairn) on a
//! shelf edge with a composed view behind it: the rock summit gazing back at the castle plain,
//! the snow summit over the western sea, and the canyon mouth's release onto the desert.
//!
//! The waterfall is found procedurally but deterministically from the authored plunge-stream
//! head (`worldmap::plunge_path`): a fan of bearings into the head wall is profiled and the
//! tallest, steepest one wins; its LIP is where the climb out of the pool flattens onto the
//! plateau (≈11–24u up). From there:
//! - the SHEET is a ribbon of water columns each SIMULATED off the lip (gravity + a steady
//!   outward drift; free fall where the face is steeper than the jet, riding the rock where not),
//!   so the falls hug the real wall — plunges off the cliff bands, slides down the ledges;
//! - a wider, fainter spray VEIL wraps the core; MIST shells billow off the plunge pool; a FOAM
//!   disc churns on the pool; a FEEDER brook walks up the plateau's thalweg from the lip, so the
//!   water visibly arrives from above.
//! Every surface animates in `assets/shaders/waterfall.wgsl` off `globals.time` — no per-frame
//! system, no material or mesh writes.

use std::f32::consts::TAU;

use bevy::asset::RenderAssetUsages;
use bevy::camera::visibility::VisibilityRange;
use bevy::light::NotShadowCaster;
use bevy::mesh::{Indices, PrimitiveTopology};
use bevy::pbr::{ExtendedMaterial, MaterialExtension, MaterialPlugin};
use bevy::prelude::*;
use bevy::render::render_resource::AsBindGroup;
use bevy::shader::ShaderRef;

use crate::biome::BiomeEntity;
use crate::palette::lin;

const FALLS_SHADER: &str = "shaders/waterfall.wgsl";

pub struct VistaPlugin;
impl Plugin for VistaPlugin {
    fn build(&self, app: &mut App) {
        // The falls animate entirely in `waterfall.wgsl` off `globals.time` — no Update system.
        app.add_plugins(MaterialPlugin::<FallsMaterial>::default());
    }
}

/// The waterfall's water surfaces: blended, PBR-lit, animated in the shader (see the WGSL header).
pub type FallsMaterial = ExtendedMaterial<StandardMaterial, FallsExt>;

#[derive(Asset, AsBindGroup, Clone, TypePath, Debug, Default)]
pub struct FallsExt {
    /// x = kind (0 sheet, 1 mist, 2 pool foam, 3 feeder stream), y = mist base y, z = mist
    /// height, w = noise seed.
    #[uniform(100)]
    pub p: Vec4,
}

impl MaterialExtension for FallsExt {
    fn fragment_shader() -> ShaderRef {
        FALLS_SHADER.into()
    }
}

fn falls_material(p: Vec4) -> FallsMaterial {
    ExtendedMaterial {
        base: StandardMaterial {
            base_color: Color::WHITE,
            alpha_mode: AlphaMode::Blend,
            double_sided: true,
            cull_mode: None,
            perceptual_roughness: 0.4,
            ..default()
        },
        extension: FallsExt { p },
    }
}

/// Spawn a falls surface. `vista::populate` runs inside the world build, which only hands it the
/// StandardMaterial store — the falls material is minted by a queued world command instead (once
/// per build, never touched again).
fn spawn_falls(commands: &mut Commands, mesh: Handle<Mesh>, p: Vec4) {
    let e = commands.spawn((Mesh3d(mesh), Transform::IDENTITY, BiomeEntity, NotShadowCaster)).id();
    commands.queue(move |world: &mut World| {
        let h = world.resource_mut::<Assets<FallsMaterial>>().add(falls_material(p));
        if let Ok(mut ent) = world.get_entity_mut(e) {
            ent.insert(MeshMaterial3d(h));
        }
    });
}

// ── meshes ───────────────────────────────────────────────────────────────────────────
fn tint(mut m: Mesh, col: u32) -> Mesh {
    let n = m.count_vertices();
    m.insert_attribute(Mesh::ATTRIBUTE_COLOR, vec![lin(col); n]);
    m
}
fn assemble(parts: Vec<Mesh>) -> Mesh {
    let mut it = parts.into_iter();
    let mut base = it.next().expect("at least one part");
    for part in it {
        base.merge(&part).expect("parts share attributes");
    }
    base.duplicate_vertices();
    base.compute_flat_normals();
    base
}

/// A `cols × rows` vertex grid (row-major) as a smooth-shaded triangle mesh.
fn grid_mesh(pos: &[Vec3], uv: &[[f32; 2]], cols: usize, rows: usize) -> Mesh {
    let mut idx = Vec::with_capacity((cols - 1) * (rows - 1) * 6);
    for k in 0..rows - 1 {
        for j in 0..cols - 1 {
            let a = (k * cols + j) as u32;
            let (b, c) = (a + 1, a + cols as u32);
            idx.extend([a, c, b, b, c, c + 1]);
        }
    }
    let mut m = Mesh::new(PrimitiveTopology::TriangleList, RenderAssetUsages::RENDER_WORLD);
    m.insert_attribute(Mesh::ATTRIBUTE_POSITION, pos.iter().map(|p| p.to_array()).collect::<Vec<_>>());
    m.insert_attribute(Mesh::ATTRIBUTE_UV_0, uv.to_vec());
    m.insert_indices(Indices::U32(idx));
    m.compute_smooth_normals();
    m
}

/// Ground (world Y) for the falls' geometry; carved water reads as the water surface.
fn gy(p: Vec2) -> f32 {
    crate::worldmap::ground_at_world(p.x, p.y).unwrap_or(crate::worldmap::SEA_Y)
}

/// The head wall's lip along one bearing from the plunge head: `(lip distance, lip height)`.
/// The lip is where the climb out of the pool first flattens (< 0.45 rise per unit over the next
/// 2u) once it has risen ≥ 11u — the rim of the head wall — or where the climb reaches 24u.
fn find_lip(head: Vec2, axis: Vec2, base_y: f32) -> Option<(f32, f32)> {
    let prof: Vec<f32> = (0..=90).map(|i| gy(head + axis * (i as f32 * 0.5))).collect();
    let flat = |i: usize| (prof[i + 4] - prof[i]) / 2.0 < 0.45;
    for i in 2..prof.len() - 4 {
        let rise = prof[i] - base_y;
        if rise >= 11.0 && flat(i) {
            return Some((i as f32 * 0.5, prof[i]));
        }
        if rise >= 24.0 {
            // Still climbing at 24u: take the real rim if it comes within the next 6u of height
            // (so the feeder can reach the lip across the plateau), else spring from the face here.
            let rim = (i..prof.len() - 4).take_while(|&k| prof[k] - base_y <= 30.0).find(|&k| flat(k));
            let k = rim.unwrap_or(i);
            return Some((k as f32 * 0.5, prof[k]));
        }
    }
    None
}

/// One water column of the sheet, simulated off the lip: a steady drift toward the pool, gravity,
/// and the wall face — where the face is steeper than the trajectory the water flies free; where
/// it is not, the water rides the rock (a 0.35u stand-off behind it keeps the sheet off the face).
/// Returns the path from the lip down to the pool surface.
fn fall_column(lip: Vec2, flow: Vec2, side: Vec2, lat0: f32, y0: f32, drop: f32, base_y: f32) -> Vec<Vec3> {
    // Over the pool there is nothing to ride: the carved water's surface sits a hair above
    // `base_y`, and riding it sent the sheet skating 25u down the lake.
    let wet = |p: Vec2| crate::worldmap::ground_at_world(p.x, p.y).is_none_or(|y| y < base_y + 0.45);
    let ground = |p: Vec2| if wet(p) { base_y - 1.0 } else { gy(p).max(gy(p - flow * 0.35)) + 0.14 };
    let (dt, vh) = (0.02_f32, 1.7_f32);
    let (mut a, mut vy) = (0.0_f32, 0.0_f32);
    let start = lip + side * lat0;
    let mut y = y0.max(ground(start));
    let mut out = vec![Vec3::new(start.x, y, start.y)];
    for _ in 0..900 {
        vy = (vy - 9.8 * dt).max(-16.0);
        a += vh * dt;
        let fallen = (y0 - y).max(0.0);
        // The sheet spreads a little as it falls.
        let p = lip + flow * a + side * lat0 * (1.0 + 0.55 * (fallen / drop).min(1.0));
        let mut ny = y + vy * dt;
        let g = ground(p);
        if ny < g {
            ny = g.min(y); // riding the face (never climbs)
            vy *= 0.4;
        }
        y = ny;
        if y <= base_y {
            out.push(Vec3::new(p.x, base_y, p.y));
            return out;
        }
        out.push(Vec3::new(p.x, y, p.y));
    }
    out
}

/// Point at `frac` (0 = lip, 1 = pool) of a column's height drop.
fn at_drop(col: &[Vec3], frac: f32) -> Vec3 {
    let (y0, y1) = (col[0].y, col[col.len() - 1].y);
    let target = y0 + (y1 - y0) * frac;
    for w in col.windows(2) {
        if w[1].y <= target {
            let span = w[0].y - w[1].y;
            let s = if span > 1e-5 { (w[0].y - target) / span } else { 0.0 };
            return w[0].lerp(w[1], s);
        }
    }
    col[col.len() - 1]
}

/// The feeder brook: walked UPSTREAM from the lip along the plateau's thalweg (each step takes
/// the lowest of a fan of uphill candidates), ~16u or until it meets a steep rise (the spring
/// seeps out of the rock there). Returned source → lip.
fn feeder_path(lip: Vec2, axis: Vec2) -> Vec<Vec2> {
    let mut pts = vec![lip];
    let (mut p, mut dir) = (lip, axis);
    let y_lip = gy(lip);
    for _ in 0..26 {
        let side = Vec2::new(-dir.y, dir.x);
        let here = gy(p);
        let mut best: Option<(f32, Vec2)> = None;
        for k in -3..=3 {
            let c = p + dir * 0.65 + side * (k as f32 * 0.4);
            let h = gy(c);
            // Upstream barely runs downhill (the gorge's lip is a crest: the plateau behind it
            // sits level or a touch lower, so a strict "always uphill" walk never left the lip).
            if h < here - 0.3 || h < y_lip - 1.2 {
                continue;
            }
            let score = h + (k as f32).abs() * 0.04;
            if best.is_none_or(|(s, _)| score < s) {
                best = Some((score, c));
            }
        }
        let Some((_, c)) = best else { break };
        if gy(c) - here > 1.6 || gy(c) - y_lip > 8.0 {
            break; // a step in the rock: the brook springs from its foot
        }
        dir = (dir * 0.75 + (c - p).normalize_or_zero() * 0.25).normalize_or_zero();
        p = c;
        pts.push(p);
    }
    pts.reverse();
    pts
}

/// The feeder ribbon draped on the plateau (`uv.y` = metres downstream for the shader's flow).
fn feeder_mesh(path: &[Vec2]) -> Mesh {
    // Chaikin-smooth the thalweg walk so the brook meanders instead of zig-zagging.
    let mut pts = path.to_vec();
    for _ in 0..2 {
        let mut s = vec![pts[0]];
        for w in pts.windows(2) {
            s.push(w[0].lerp(w[1], 0.25));
            s.push(w[0].lerp(w[1], 0.75));
        }
        s.push(pts[pts.len() - 1]);
        pts = s;
    }
    let n = pts.len();
    let cols = 5;
    let (mut pos, mut uv) = (Vec::new(), Vec::new());
    let mut along = 0.0;
    for i in 0..n {
        if i > 0 {
            along += pts[i].distance(pts[i - 1]);
        }
        let tdir = (pts[(i + 1).min(n - 1)] - pts[i.saturating_sub(1)]).normalize_or_zero();
        let side = Vec2::new(-tdir.y, tdir.x);
        let f = i as f32 / (n - 1).max(1) as f32;
        let half = 0.45 + 0.55 * f; // widens toward the lip as it gathers
        for j in 0..cols {
            let u = j as f32 / (cols - 1) as f32;
            let q = pts[i] + side * (u - 0.5) * 2.0 * half;
            pos.push(Vec3::new(q.x, gy(q).max(gy(pts[i])) + 0.07, q.y));
            uv.push([u, along]);
        }
    }
    grid_mesh(&pos, &uv, cols, n)
}

/// Overlook framing prop: a crooked windswept lone pine, a flat sitting stone, a marker cairn —
/// stand here, look past the tree, see the island.
fn overlook_prop() -> Mesh {
    const BARK: u32 = 0x4e3a24;
    const NEEDLE: u32 = 0x2f5233;
    const NEEDLE_D: u32 = 0x24402a;
    const STONE: u32 = 0x83878d;
    let mut v = Vec::new();
    // Windswept trunk: two leaning segments.
    v.push(tint(
        Cylinder::new(0.14, 1.6).mesh().resolution(7).build().rotated_by(Quat::from_rotation_z(0.35)).translated_by(Vec3::new(0.0, 0.75, 0.0)),
        BARK,
    ));
    v.push(tint(
        Cylinder::new(0.10, 1.2).mesh().resolution(7).build().rotated_by(Quat::from_rotation_z(0.75)).translated_by(Vec3::new(-0.65, 1.75, 0.0)),
        BARK,
    ));
    // Wind-flagged canopy: layered pads all pushed to the lee side.
    for (dx, dy, r, col) in [
        (-1.15_f32, 2.25_f32, 0.55_f32, NEEDLE),
        (-1.6, 2.05, 0.42, NEEDLE_D),
        (-0.75, 2.5, 0.4, NEEDLE),
        (-1.95, 2.3, 0.3, NEEDLE),
    ] {
        v.push(tint(
            Sphere::new(r).mesh().ico(1).unwrap().scaled_by(Vec3::new(1.5, 0.5, 1.1)).translated_by(Vec3::new(dx, dy, 0.0)),
            col,
        ));
    }
    // Flat sitting stone + small cairn.
    v.push(tint(Cuboid::new(0.9, 0.3, 0.7).mesh().build().translated_by(Vec3::new(0.9, 0.15, 0.5)), STONE));
    for (i, (r, y)) in [(0.22_f32, 0.08_f32), (0.16, 0.28), (0.10, 0.42)].into_iter().enumerate() {
        v.push(tint(
            Sphere::new(r).mesh().ico(1).unwrap().scaled_by(Vec3::new(1.0, 0.6, 1.0)).translated_by(Vec3::new(1.0 + i as f32 * 0.02, y, -0.5)),
            STONE,
        ));
    }
    assemble(v)
}

// ── placement ────────────────────────────────────────────────────────────────────────
/// Build-phase 33: the waterfall + the three overlooks.
/// The three overlook anchors `(anchor, what the view looks AT, label)`, DERIVED from the region
/// layout (they were hand-authored world coords that went stale on every scale bump / region
/// retune): the rock summit gazing back at the castle plain, the snow summit over the western sea,
/// and 5 base units inside the rock range's N canyon mouth looking out at the rival's dunes.
pub fn overlook_anchors() -> Vec<(Vec2, Vec2, &'static str)> {
    use crate::worldmap::{biome_centres_world, pass_point_world, world22};
    let c = biome_centres_world();
    let mut out = vec![
        (c[2], Vec2::ZERO, "rock summit → castle plain"),
        (c[0], world22(-150.0, -66.0), "snow summit → western sea"),
    ];
    if let Some(canyon) = pass_point_world(2, 1, 5.0) {
        out.push((canyon, crate::rival::RIVAL_CENTRE, "canyon mouth → rival dunes"));
    }
    out
}

/// The waterfall (see the module doc). Logs the lip / drop so a capture can frame it.
fn populate_falls(commands: &mut Commands, meshes: &mut Assets<Mesh>) {
    // The plunge head is the AUTHORED waterfall stream's head (`worldmap::plunge_path`, carved
    // water connected to the lake); the head wall rises against the flow.
    let (head, flow) = crate::worldmap::waterfall_site_world();
    let base_y = crate::worldmap::SEA_Y + 0.05;
    // Fan of bearings into the wall: the gorge head is not exactly square to the authored flow.
    // Prefer the steepest wall (most rise per unit of approach) among those ≥ 11u tall.
    let mut best: Option<(f32, Vec2, f32, f32)> = None; // (score, axis, lip dist, lip y)
    for k in -4..=4 {
        let axis = Vec2::from_angle(k as f32 * 0.12).rotate(-flow);
        if let Some((d, y)) = find_lip(head, axis, base_y) {
            let score = (y - base_y) / (d + 4.0) - (k as f32).abs() * 0.02;
            if best.is_none_or(|(s, ..)| score > s) {
                best = Some((score, axis, d, y));
            }
        }
    }
    let Some((_, axis, d_lip, y_lip)) = best else {
        warn!("vista: no head wall found for the waterfall above the lake");
        return;
    };
    let flow = -axis;
    let side = Vec2::new(-flow.y, flow.x);
    let lip = head + axis * d_lip;
    let drop = y_lip - base_y;

    // 1. THE SHEET — 11 simulated columns across a 2.6u lip, resampled at equal fractions of each
    //    column's own drop (so the rows stay level-ish whatever path each column took).
    const COLS: usize = 11;
    let rows = ((drop / 0.35).ceil() as usize).clamp(12, 90);
    let half_w = 1.3;
    let columns: Vec<Vec<Vec3>> = (0..COLS)
        .map(|j| {
            let lat = (j as f32 / (COLS - 1) as f32 - 0.5) * 2.0 * half_w;
            fall_column(lip, flow, side, lat, y_lip + 0.12, drop, base_y)
        })
        .collect();
    let (mut pos, mut uv) = (Vec::new(), Vec::new());
    let (mut vpos, mut vuv) = (Vec::new(), Vec::new());
    for k in 0..=rows {
        let f = k as f32 / rows as f32;
        for (j, col) in columns.iter().enumerate() {
            let p = at_drop(col, f);
            let u = j as f32 / (COLS - 1) as f32;
            let fallen = col[0].y - p.y;
            pos.push(p);
            uv.push([u, fallen]);
            // The spray veil: 1.6× wider, 0.35u further out from the face, from a quarter down.
            let mid = at_drop(&columns[COLS / 2], f);
            let out = flow * (0.35 + 0.5 * f);
            vpos.push(mid + (p - mid) * Vec3::new(1.6, 1.0, 1.6) + out.extend(0.0).xzy());
            vuv.push([u + 2.0, fallen]);
        }
    }
    let sheet = grid_mesh(&pos, &uv, COLS, rows + 1);
    let veil = grid_mesh(&vpos, &vuv, COLS, rows + 1);
    spawn_falls(commands, meshes.add(sheet), Vec4::new(0.0, 0.0, 0.0, 3.7));
    spawn_falls(commands, meshes.add(veil), Vec4::new(0.0, 0.0, 0.0, 11.3));

    // Where the water meets the pool: the mean of the columns' last points.
    let impact = columns.iter().map(|c| c[c.len() - 1]).sum::<Vec3>() / COLS as f32;

    // 2. MIST — two spray shells over the impact: a broad low billow and a taller column that
    //    climbs the lower third of the falls.
    let shell = |r: f32, h: f32| Sphere::new(1.0).mesh().uv(24, 14).scaled_by(Vec3::new(r, h, r));
    let mist_lo = shell(5.0, 3.6).translated_by(Vec3::new(impact.x, base_y, impact.z) + (flow * 1.2).extend(0.0).xzy());
    let mist_hi = shell(3.2, drop * 0.32).translated_by(Vec3::new(impact.x, base_y, impact.z) + (flow * 0.9).extend(0.0).xzy());
    spawn_falls(commands, meshes.add(mist_lo), Vec4::new(1.0, base_y, 3.6, 5.1));
    spawn_falls(commands, meshes.add(mist_hi), Vec4::new(1.0, base_y, drop * 0.32, 8.9));

    // 3. POOL FOAM — a churning disc on the water under the falls.
    let foam = Circle::new(6.5)
        .mesh()
        .resolution(48)
        .build()
        .rotated_by(Quat::from_rotation_x(-std::f32::consts::FRAC_PI_2))
        .translated_by(Vec3::new(impact.x, crate::worldmap::SEA_Y + 0.06, impact.z) + (flow * 1.2).extend(0.0).xzy());
    spawn_falls(commands, meshes.add(foam), Vec4::new(2.0, 0.0, 0.0, 2.3));

    // 4. FEEDER — the brook that runs over the plateau to the lip.
    let path = feeder_path(lip, axis);
    let feeder_len: f32 = path.windows(2).map(|w| w[0].distance(w[1])).sum();
    let behind: Vec<String> = (0..=8).map(|k| format!("{:.1}", gy(lip + axis * k as f32))).collect();
    debug!("vista: ground behind the lip (1u steps): {}", behind.join(" "));
    if path.len() >= 3 {
        spawn_falls(commands, meshes.add(feeder_mesh(&path)), Vec4::new(3.0, 0.0, 0.0, 6.6));
    }

    info!(
        "vista: waterfall lip at {:.1},{:.1} y {:.1} (drop {:.1}u, {:.1}u back from the pool head {:.1},{:.1}), impact {:.1},{:.1}, feeder {:.1}u",
        lip.x, lip.y, y_lip, drop, d_lip, head.x, head.y, impact.x, impact.z, feeder_len
    );
}

pub fn populate(commands: &mut Commands, meshes: &mut Assets<Mesh>, materials: &mut Assets<StandardMaterial>) {
    let mat = materials.add(StandardMaterial { base_color: Color::WHITE, perceptual_roughness: 0.85, ..default() });

    // 1. THE WATERFALL.
    populate_falls(commands, meshes);

    // 2. OVERLOOKS — ring-search a flat legal spot near each authored anchor, face the view.
    let prop = meshes.add(overlook_prop());
    let range = VisibilityRange { start_margin: 0.0..0.0, end_margin: 130.0..130.0, use_aabb: true };
    let anchors = overlook_anchors();
    let spot_ok = |x: f32, z: f32| {
        let Some(y0) = crate::worldmap::ground_at_world(x, z) else { return false };
        (0..6).all(|k| {
            let a = k as f32 * (TAU / 6.0);
            matches!(crate::worldmap::ground_at_world(x + a.cos() * 1.4, z + a.sin() * 1.4), Some(y) if (y - y0).abs() <= 0.3)
        }) && !crate::roads::on_road(x, z)
            && !crate::blockers::is_blocked(x, z)
    };
    let mut placed = 0;
    for (anchor, view_at, label) in anchors {
        let mut found = None;
        'ring: for r in [0.0_f32, 2.5, 5.0, 7.5, 10.0] {
            for k in 0..10 {
                let a = k as f32 * (TAU / 10.0);
                let (x, z) = (anchor.x + a.cos() * r, anchor.y + a.sin() * r);
                if spot_ok(x, z) {
                    found = Some(Vec2::new(x, z));
                    break 'ring;
                }
            }
        }
        let Some(q) = found else {
            warn!("vista: no overlook footing near {label}");
            continue;
        };
        let y = crate::worldmap::ground_at_world(q.x, q.y).unwrap_or(0.0);
        // The pine's wind-flagged canopy sweeps toward local −X; yaw so that sweep frames the
        // view direction (stand at the prop, look past the lean at `view_at`).
        let v = (view_at - q).normalize_or_zero();
        let yaw = v.y.atan2(v.x) + std::f32::consts::PI;
        let tf = Transform::from_xyz(q.x, y, q.y).with_rotation(Quat::from_rotation_y(-yaw));
        // Realistic kit: a wind-flagged spruce (its lee sweep along -X like the old pine), a scanned
        // sitting boulder and a cairn, all sunk a little into the summit turf.
        let kit = crate::realforest::get().filter(|k| k.has("spruce_flag_lod0") && k.has("rock_02_a") && k.has("rk_cairn"));
        if let Some(k) = kit {
            let mut e = commands.spawn((tf, Visibility::default(), BiomeEntity));
            if let Some(tree) = k.pick_named(&["spruce_flag_lod0"], 0.0) {
                e.with_children(|p| {
                    let mut t = p.spawn((Transform::from_xyz(-0.2, -0.1, 0.0).with_scale(Vec3::splat(0.85)), Visibility::default()));
                    k.attach_tree(&mut t, tree, true);
                });
            }
            k.attach_static_with(&mut e, "rock_02_a", Transform::from_xyz(0.95, -0.12, 0.55).with_rotation(Quat::from_rotation_y(0.7)).with_scale(Vec3::new(0.55, 0.38, 0.5)), range.clone());
            k.attach_static_with(&mut e, "rk_cairn", Transform::from_xyz(1.0, -0.06, -0.6).with_scale(Vec3::splat(0.45)), range.clone());
        } else {
            commands.spawn((Mesh3d(prop.clone()), MeshMaterial3d(mat.clone()), tf, BiomeEntity, range.clone()));
        }
        crate::blockers::add_obb(q.x, q.y, 0.5, 0.5, 0.0);
        placed += 1;
        info!("vista: overlook ({label}) at {:.1},{:.1}", q.x, q.y);
    }
    info!("vista: {placed}/3 overlooks");
}
