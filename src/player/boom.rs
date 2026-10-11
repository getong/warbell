//! Third-person **camera boom collision** against solid buildings — the Witcher-3 spring arm.
//!
//! The castle is moving to realistic scale (stone walls ≈4u, towers ≈6u, keep ≈9u against a
//! ≈1.2u hero), so the follow camera can no longer orbit straight through masonry: backed up to a
//! wall the lens would end up inside the stone (or outside the castle, the hero hidden behind it).
//!
//! **What occludes.** Anything tagged [`CameraOccluder`]. Put it on a mesh entity, or on a parent —
//! [`propagate_occluders`] pushes the tag down onto every mesh beneath (glb scene roots included,
//! whose children spawn later). Hidden structures (an upgrade not bought yet) never occlude: the
//! test reads `InheritedVisibility`.
//!
//! **How the boom works** (all numbers below are the `const`s in this file):
//! 1. *Shoulder probe* — the framing offset (shoulder shift + look-ahead lead) is ray-tested
//!    sideways from the hero's eye. Hugging a wall on the shoulder side shrinks the offset so the
//!    boom's origin never sits inside the wall (snaps in, eases back out at `SHOULDER_OUT_RATE`).
//! 2. *Boom probe* — five segments from that origin to the desired eye: the centre line plus four
//!    "feelers" fanned `FEELER_R` around the lens (approximates a sphere sweep, so a wall running
//!    parallel to the boom can't graze the near plane). The nearest solid hit, minus `MARGIN`,
//!    is the wanted boom length, floored at `BOOM_MIN` (≈ just behind the shoulder).
//! 3. *Smoothing* — pull-in is fast (`PULL_IN_RATE`, ≈90% in 0.1 s) and additionally hard-capped
//!    by the centre-line hit every frame, so the lens can never sit behind a visible surface; the
//!    return is held for `HOLD_SECS` then eased out slowly (`EASE_OUT_RATE`) — no popping or
//!    pumping when walking along a crenellated wall or through a gate.
//! 4. *Tight framing* — as the boom shortens below `TIGHT_START`, the eye lifts up to `TIGHT_LIFT`
//!    so a close camera looks over the shoulder instead of into the back of the helm.
//!
//! **Thin things don't pull** (banner poles, beams, posts): each hit is measured as the chord the
//! segment spends inside the mesh; a pass-through shorter than `THIN` is ignored — unless the lens
//! itself would end inside it. Narrow phase is per-triangle (Möller–Trumbore in the mesh's local
//! space) behind a per-entity OBB slab test, so arches and gate passages (one merged mesh whose
//! box spans the opening) don't phantom-block. A mesh whose vertex data isn't CPU-side falls back
//! to its box.
//!
//! Debug: `FOREST_NOBOOM=1` disables collision (before/after shots); `FOREST_CAMDBG=1` logs the
//! per-frame cost and boom length every 2 s; `FOREST_TALLWALLS=1` raises a 4u test curtain wall
//! (+ gate lintels, 6u towers, a thin pole) on the current castle footprint.

use bevy::camera::primitives::Aabb;
use bevy::ecs::system::SystemParam;
use bevy::mesh::{Indices, VertexAttributeValues};
use bevy::prelude::*;

/// Marker for solid building mass the third-person camera must not pass through (walls, towers,
/// keep, gatehouse, houses, solid ruins). On a mesh entity it is used directly; on a parent it is
/// propagated to every descendant mesh. Don't tag thin props, foliage or anything walk-through.
#[derive(Component, Default, Clone, Copy)]
pub struct CameraOccluder;

/// Lens clearance kept in front of the nearest solid hit (world units).
const MARGIN: f32 = 0.22;
/// Feeler fan radius around the lens — approximates a sphere sweep for the near plane.
const FEELER_R: f32 = 0.2;
/// Shortest boom (from the shoulder-shifted look target): just behind the shoulder. Closer than
/// this the lens is inside the helm; past it a tighter lift (below) does the work instead.
const BOOM_MIN: f32 = 0.5;
/// Boom length at which the tight over-the-shoulder lift starts to blend in.
const TIGHT_START: f32 = 1.7;
/// Extra eye height at full tightness (looks over the helm instead of into it).
const TIGHT_LIFT: f32 = 0.28;
/// Pull-in ease (1/s). Fast, plus the centre-line hard cap, so the lens never shows a wall's inside.
const PULL_IN_RATE: f32 = 22.0;
/// Ease-out (1/s) once the occluder clears — slow, so the camera drifts back instead of popping.
const EASE_OUT_RATE: f32 = 2.2;
/// Seconds the boom holds its pulled-in length after the occluder clears before easing out —
/// kills flicker when the boom skims merlons / door jambs.
const HOLD_SECS: f32 = 0.28;
/// Shoulder-offset ease back out (1/s) after a wall on the shoulder side clears.
const SHOULDER_OUT_RATE: f32 = 3.0;
/// Clearance kept between the shifted look target and a wall beside the hero.
const SHOULDER_PAD: f32 = 0.28;
/// Chord (world units) below which a pass-through counts as thin (pole / beam / post) and is ignored.
const THIN: f32 = 0.3;
/// Occluders whose bounding sphere is farther than this from the boom origin are skipped outright.
const REACH: f32 = 20.0;

/// Smoothed boom state, kept on [`super::camera::OrbitCam`].
#[derive(Default, Clone, Copy)]
pub struct BoomState {
    /// Current boom length (world units); `0` = unprimed.
    len: f32,
    /// Seconds since the wanted length last dropped below the current one.
    hold: f32,
    /// Fraction (0..1) of the framing offset currently allowed by the shoulder probe.
    shoulder: f32,
    primed: bool,
    // `FOREST_CAMDBG` accumulators.
    dbg_t: f32,
    dbg_us: f32,
    dbg_n: u32,
}

/// One occluder, flattened for this frame's casts.
struct Occ {
    world_to_local: bevy::math::Affine3A,
    min: Vec3,
    max: Vec3,
    mesh: Option<AssetId<Mesh>>,
}

/// The boom's occluder access, nested into `player_camera`'s `CamGate` (the system is at Bevy's
/// 16-parameter cap).
#[derive(SystemParam)]
pub struct Occluders<'w, 's> {
    q: Query<
        'w,
        's,
        (&'static Aabb, &'static GlobalTransform, &'static InheritedVisibility, Option<&'static Mesh3d>),
        With<CameraOccluder>,
    >,
    meshes: Res<'w, Assets<Mesh>>,
    scratch: Local<'s, Vec<Occ>>,
    hits: Local<'s, Vec<f32>>,
}

/// What the boom hands back: the look target (shoulder-shortened, lifted when tight) and the eye.
pub struct BoomPose {
    pub target: Vec3,
    pub eye: Vec3,
}

fn env_on(k: &str) -> bool {
    std::env::var(k).is_ok()
}

/// `FOREST_NOBOOM` / `FOREST_CAMDBG`, read once.
fn flags() -> (bool, bool) {
    static F: std::sync::OnceLock<(bool, bool)> = std::sync::OnceLock::new();
    *F.get_or_init(|| (env_on("FOREST_NOBOOM"), env_on("FOREST_CAMDBG")))
}

/// Per-shot boom kill switch for the `FOREST_BOOMSHOTS` before/after pairs.
static SHOT_NOBOOM: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);

impl Occluders<'_, '_> {
    /// Resolve the follow camera against occluders. `anchor` is the hero's (smoothed) eye point,
    /// `offset` the framing shift from it (shoulder + lead), `arm` the vector from the shifted
    /// target to the desired eye (orbit + terrain lift already applied).
    pub fn resolve(&mut self, st: &mut BoomState, anchor: Vec3, offset: Vec3, arm: Vec3, dt: f32) -> BoomPose {
        let dt = dt.clamp(1e-4, 0.1);
        let want_len = arm.length();
        if flags().0 || SHOT_NOBOOM.load(std::sync::atomic::Ordering::Relaxed) || want_len < 1e-3 {
            st.primed = false;
            return BoomPose { target: anchor + offset, eye: anchor + offset + arm };
        }
        let t0 = std::time::Instant::now();
        self.gather(anchor, want_len + offset.length());

        // 1. Shoulder probe: how much of the framing offset fits beside the hero.
        let off_len = offset.length();
        let allowed = if off_len > 1e-3 {
            let dir = offset / off_len;
            let probe = off_len + SHOULDER_PAD;
            match self.segment_hit(anchor, anchor + dir * probe) {
                Some(t) => ((t * probe - SHOULDER_PAD) / off_len).clamp(0.0, 1.0),
                None => 1.0,
            }
        } else {
            1.0
        };
        if !st.primed || allowed < st.shoulder {
            st.shoulder = allowed;
        } else {
            st.shoulder += (allowed - st.shoulder) * (1.0 - (-dt * SHOULDER_OUT_RATE).exp());
        }
        let target = anchor + offset * st.shoulder;

        // 2. Boom probe: centre line + four feelers around the lens.
        let dir = arm / want_len;
        let side = {
            let s = Vec3::Y.cross(dir);
            if s.length_squared() > 1e-6 { s.normalize() } else { Vec3::X }
        };
        let up = dir.cross(side).normalize_or_zero();
        let eye = target + arm;
        let centre = self.segment_hit(target, eye).map(|t| t * want_len);
        let mut nearest = centre.unwrap_or(f32::INFINITY);
        for o in [side, -side, up, -up] {
            let end = eye + o * FEELER_R;
            if let Some(t) = self.segment_hit(target, end) {
                // Project the feeler hit back onto the boom axis.
                nearest = nearest.min(((end - target) * t).dot(dir));
            }
        }
        let wanted = if nearest.is_finite() { (nearest - MARGIN).clamp(BOOM_MIN, want_len) } else { want_len };

        // 3. Smoothing: fast in (+ hard cap on the centre line), held then slow out.
        if !st.primed {
            st.len = wanted;
            st.hold = 0.0;
            st.primed = true;
        } else if wanted < st.len {
            st.len += (wanted - st.len) * (1.0 - (-dt * PULL_IN_RATE).exp());
            st.hold = 0.0;
        } else {
            st.hold += dt;
            if st.hold > HOLD_SECS {
                st.len += (wanted - st.len) * (1.0 - (-dt * EASE_OUT_RATE).exp());
            }
        }
        if let Some(c) = centre {
            st.len = st.len.min((c - MARGIN * 0.5).max(BOOM_MIN));
        }
        // A zoom-in (wheel) is never slowed; a zoom-out eases through the same return path.
        st.len = st.len.min(want_len);

        // 4. Tight framing: a short boom lifts to look over the shoulder.
        let tight = ((TIGHT_START - st.len) / (TIGHT_START - BOOM_MIN)).clamp(0.0, 1.0);
        let tight = tight * tight * (3.0 - 2.0 * tight);
        // Lift the look target with the eye so the view keeps the orbit pitch (a lifted eye aimed
        // at the un-lifted target would stare down at the boots).
        let lift = Vec3::Y * (tight * TIGHT_LIFT);
        let eye = target + dir * st.len + lift;

        if flags().1 {
            st.dbg_us += t0.elapsed().as_secs_f32() * 1e6;
            st.dbg_n += 1;
            st.dbg_t += dt;
            if st.dbg_t > 2.0 {
                info!(
                    "camboom: {:.1} us/frame avg over {} frames, {} occluders in reach, boom {:.2}/{:.2} shoulder {:.2}",
                    st.dbg_us / st.dbg_n.max(1) as f32,
                    st.dbg_n,
                    self.scratch.len(),
                    st.len,
                    want_len,
                    st.shoulder
                );
                (st.dbg_t, st.dbg_us, st.dbg_n) = (0.0, 0.0, 0);
            }
        }
        BoomPose { target: target + lift, eye }
    }

    /// Flatten the visible occluders near `origin` into `scratch` for this frame's casts.
    fn gather(&mut self, origin: Vec3, reach: f32) {
        self.scratch.clear();
        for (aabb, gt, vis, mesh) in &self.q {
            if !vis.get() {
                continue;
            }
            let aff = gt.affine();
            let c = aff.transform_point3(Vec3::from(aabb.center));
            let max_scale =
                aff.matrix3.x_axis.length().max(aff.matrix3.y_axis.length()).max(aff.matrix3.z_axis.length());
            let r = max_scale * Vec3::from(aabb.half_extents).length();
            if c.distance(origin) - r > reach.min(REACH) + FEELER_R {
                continue;
            }
            self.scratch.push(Occ {
                world_to_local: aff.inverse(),
                min: Vec3::from(aabb.center - aabb.half_extents),
                max: Vec3::from(aabb.center + aabb.half_extents),
                mesh: mesh.map(|m| m.0.id()),
            });
        }
    }

    /// Earliest fraction `t ∈ [0, 1]` along `a → b` where the segment enters SOLID occluder
    /// geometry (thin pass-throughs skipped), or `None` if the segment is clear.
    fn segment_hit(&mut self, a: Vec3, b: Vec3) -> Option<f32> {
        let seg_len = a.distance(b);
        if seg_len < 1e-4 {
            return None;
        }
        let thin_t = THIN / seg_len;
        let mut best: Option<f32> = None;
        for i in 0..self.scratch.len() {
            let occ = &self.scratch[i];
            let o = occ.world_to_local.transform_point3(a);
            let d = occ.world_to_local.transform_vector3(b - a);
            // Broad phase: segment vs the local box (slab test in segment-parameter space).
            let Some((tmin, tmax)) = slab(o, d, occ.min - Vec3::splat(1e-3), occ.max + Vec3::splat(1e-3)) else {
                continue;
            };
            if best.is_some_and(|bt| tmin >= bt) {
                continue;
            }
            // Narrow phase: every triangle crossing, as segment fractions.
            let mesh = occ.mesh.and_then(|id| self.meshes.get(id));
            let hits = &mut self.hits;
            hits.clear();
            let tri_ok = mesh.is_some_and(|m| collect_tri_hits(m, o, d, hits));
            if !tri_ok {
                // No CPU-side vertex data — the box itself is the solid. A segment that starts
                // inside the box is ignored (the hero stands within its bounds: a doorway, an arch).
                if tmin <= 0.0 {
                    continue;
                }
                hits.clear();
                hits.push(tmin);
                if tmax < 1.0 {
                    hits.push(tmax);
                }
            }
            if hits.is_empty() {
                continue;
            }
            hits.sort_by(|x, y| x.total_cmp(y));
            hits.dedup_by(|x, y| (*x - *y).abs() * seg_len < 1e-3);
            // Walk entry/exit pairs: a chord shorter than `THIN` that ends before the lens is a
            // pole/beam — skip it. An unpaired last hit means the lens ends inside: solid.
            let mut k = 0;
            while k < hits.len() {
                let entry = hits[k];
                let solid = match hits.get(k + 1) {
                    Some(&exit) => exit - entry >= thin_t,
                    None => true,
                };
                if solid {
                    if best.is_none_or(|bt| entry < bt) {
                        best = Some(entry);
                    }
                    break;
                }
                k += 2;
            }
        }
        best
    }
}

/// Segment-vs-box slab test; returns the `[tmin, tmax]` overlap of the segment parameter with the
/// box (clipped to `[0, 1]`), or `None`.
fn slab(o: Vec3, d: Vec3, min: Vec3, max: Vec3) -> Option<(f32, f32)> {
    let mut t0 = 0.0f32;
    let mut t1 = 1.0f32;
    for ax in 0..3 {
        let (oa, da, lo, hi) = (o[ax], d[ax], min[ax], max[ax]);
        if da.abs() < 1e-9 {
            if oa < lo || oa > hi {
                return None;
            }
        } else {
            let inv = 1.0 / da;
            let (mut ta, mut tb) = ((lo - oa) * inv, (hi - oa) * inv);
            if ta > tb {
                std::mem::swap(&mut ta, &mut tb);
            }
            t0 = t0.max(ta);
            t1 = t1.min(tb);
            if t0 > t1 {
                return None;
            }
        }
    }
    Some((t0, t1))
}

/// Push every triangle crossing of the local-space segment `o + t·d`, `t ∈ [0, 1]`, into `out`.
/// Returns `false` if the mesh's vertex data isn't readable (extracted to the render world, or a
/// non-`Float32x3` position layout) so the caller falls back to the bounding box.
fn collect_tri_hits(mesh: &Mesh, o: Vec3, d: Vec3, out: &mut Vec<f32>) -> bool {
    let Ok(VertexAttributeValues::Float32x3(pos)) = mesh.try_attribute(Mesh::ATTRIBUTE_POSITION) else {
        return false;
    };
    let mut tri = |a: usize, b: usize, c: usize| {
        let (Some(a), Some(b), Some(c)) = (pos.get(a), pos.get(b), pos.get(c)) else { return };
        if let Some(t) = seg_tri(o, d, Vec3::from(*a), Vec3::from(*b), Vec3::from(*c)) {
            out.push(t);
        }
    };
    match mesh.try_indices() {
        Ok(Indices::U32(ix)) => ix.chunks_exact(3).for_each(|c| tri(c[0] as usize, c[1] as usize, c[2] as usize)),
        Ok(Indices::U16(ix)) => ix.chunks_exact(3).for_each(|c| tri(c[0] as usize, c[1] as usize, c[2] as usize)),
        Err(_) => (0..pos.len() / 3).for_each(|i| tri(i * 3, i * 3 + 1, i * 3 + 2)),
    }
    true
}

/// Two-sided Möller–Trumbore against the segment `o + t·d`, `t ∈ [0, 1]`.
#[inline]
fn seg_tri(o: Vec3, d: Vec3, a: Vec3, b: Vec3, c: Vec3) -> Option<f32> {
    let e1 = b - a;
    let e2 = c - a;
    let p = d.cross(e2);
    let det = e1.dot(p);
    if det.abs() < 1e-12 {
        return None;
    }
    let inv = 1.0 / det;
    let s = o - a;
    let u = s.dot(p) * inv;
    if !(0.0..=1.0).contains(&u) {
        return None;
    }
    let q = s.cross(e1);
    let v = d.dot(q) * inv;
    if v < 0.0 || u + v > 1.0 {
        return None;
    }
    let t = e2.dot(q) * inv;
    (0.0..=1.0).contains(&t).then_some(t)
}

/// Push [`CameraOccluder`] from a tagged parent down onto every mesh beneath it — both when the tag
/// lands on an existing hierarchy and when a mesh appears later under a tagged ancestor (a glb
/// scene instancing its children a few frames after the root spawned).
pub fn propagate_occluders(
    mut commands: Commands,
    roots: Query<Entity, (Added<CameraOccluder>, With<Children>)>,
    children: Query<&Children>,
    untagged_mesh: Query<(), (With<Mesh3d>, Without<CameraOccluder>)>,
    fresh: Query<Entity, (Added<Mesh3d>, Without<CameraOccluder>)>,
    parents: Query<&ChildOf>,
    tagged: Query<(), With<CameraOccluder>>,
) {
    for root in &roots {
        for e in children.iter_descendants(root) {
            if untagged_mesh.contains(e) {
                commands.entity(e).try_insert(CameraOccluder);
            }
        }
    }
    for e in &fresh {
        if parents.iter_ancestors(e).any(|p| tagged.contains(p)) {
            commands.entity(e).try_insert(CameraOccluder);
        }
    }
}

/// `FOREST_TALLWALLS=1` test rig: a 4u stone curtain wall on the castle footprint — one merged mesh
/// (walls + gate lintels + 6u towers), so the triangle narrow phase is exercised against a box that
/// spans every gate opening — plus a thin 3.5u banner pole in the courtyard that must NOT pull the
/// boom. Not registered as movement blockers; purely a camera test.
pub fn spawn_tall_test_walls(
    mut commands: Commands,
    mut meshes: ResMut<Assets<Mesh>>,
    mut mats: ResMut<Assets<StandardMaterial>>,
) {
    if !env_on("FOREST_TALLWALLS") {
        return;
    }
    let (hx, hz) = crate::castle::courtyard_half();
    const GAP: f32 = 4.0; // castle GATE_GAP
    const H: f32 = 4.0;
    const T: f32 = 0.9;
    const BASE: f32 = -0.6;
    let mut merged: Option<Mesh> = None;
    let mut add = |m: Mesh, at: Vec3| {
        let m = m.transformed_by(Transform::from_translation(at));
        match merged.as_mut() {
            Some(acc) => {
                let _ = acc.merge(&m);
            }
            None => merged = Some(m),
        }
    };
    let cy = BASE + H / 2.0;
    // N/S walls: two runs each side of the gate gap; E/W likewise.
    for z in [-hz, hz] {
        let run = hx - GAP / 2.0;
        for s in [-1.0, 1.0] {
            add(Cuboid::new(run, H - BASE, T).mesh().build(), Vec3::new(s * (GAP / 2.0 + run / 2.0), cy, z));
        }
        add(Cuboid::new(GAP, 1.0, T).mesh().build(), Vec3::new(0.0, H - 0.5, z)); // gate lintel
    }
    for x in [-hx, hx] {
        let run = hz - GAP / 2.0;
        for s in [-1.0, 1.0] {
            add(Cuboid::new(T, H - BASE, run).mesh().build(), Vec3::new(x, cy, s * (GAP / 2.0 + run / 2.0)));
        }
        add(Cuboid::new(T, 1.0, GAP).mesh().build(), Vec3::new(x, H - 0.5, 0.0));
    }
    for (x, z) in [(-hx, -hz), (hx, -hz), (hx, hz), (-hx, hz)] {
        add(Cylinder::new(1.5, 6.0 - BASE).mesh().resolution(20).build(), Vec3::new(x, BASE + (6.0 - BASE) / 2.0, z));
    }
    let stone = mats.add(StandardMaterial {
        base_color: Color::srgb(0.55, 0.54, 0.52),
        perceptual_roughness: 0.9,
        ..default()
    });
    if let Some(m) = merged {
        commands.spawn((Mesh3d(meshes.add(m)), MeshMaterial3d(stone.clone()), Transform::default(), CameraOccluder));
    }
    // Thin banner pole (0.12u) mid-courtyard: occluder-tagged but too thin to pull the boom.
    commands.spawn((
        Mesh3d(meshes.add(Cuboid::new(0.12, 3.5, 0.12).mesh().build())),
        MeshMaterial3d(stone),
        Transform::from_xyz(9.0, 1.75, -3.0),
        CameraOccluder,
    ));
    info!("FOREST_TALLWALLS: 4u test curtain wall + 6u towers on the ±{hx}x±{hz} footprint");
}

/// `FOREST_BOOMSHOTS` — several follow-camera verification shots from ONE launch (a full world
/// boot is minutes). Runs after the main `FOREST_SHOT` lands (it holds the harness open via
/// `capture::ShotHold`). Entries are `|`-separated `path:x,z,az,pitch,dist[,noboom]`: the hero is
/// dropped at world `x,z` with his back to the camera, the orbit set to `az/pitch/dist`, ~70
/// frames settle, then `<path>.png` is saved. `noboom` disables collision for that shot (A/B).
pub fn boom_shot_seq(
    mut commands: Commands,
    mut hold: Option<ResMut<crate::capture::ShotHold>>,
    main: Option<Res<crate::capture::ShotPath>>,
    mut orbit: ResMut<super::camera::OrbitCam>,
    mut hero_q: Query<(&mut super::Hero, &mut Transform)>,
    mut st: Local<(bool, usize, u32, bool)>,
) {
    let Ok(spec) = std::env::var("FOREST_BOOMSHOTS") else { return };
    let (Some(hold), Some(main)) = (hold.as_mut(), main) else { return };
    let entries: Vec<(String, [f32; 5], bool)> = spec
        .split('|')
        .filter_map(|e| {
            let (path, rest) = e.split_once(':')?;
            let parts: Vec<&str> = rest.split(',').map(str::trim).collect();
            let v: Vec<f32> = parts.iter().take(5).filter_map(|p| p.parse().ok()).collect();
            (v.len() == 5).then(|| (format!("{}.png", path.trim()), [v[0], v[1], v[2], v[3], v[4]], parts.get(5) == Some(&"noboom")))
        })
        .collect();
    let (started, idx, frame, shot) = &mut *st;
    if !*started {
        hold.0 = true;
        if !std::path::Path::new(&main.0).exists() {
            return;
        }
        *started = true;
    }
    let Some((path, [x, z, az, pitch, dist], noboom)) = entries.get(*idx) else {
        SHOT_NOBOOM.store(false, std::sync::atomic::Ordering::Relaxed);
        hold.0 = false;
        return;
    };
    if *frame == 0 {
        let _ = std::fs::remove_file(path);
        SHOT_NOBOOM.store(*noboom, std::sync::atomic::Ordering::Relaxed);
        if let Ok((mut hero, mut tf)) = hero_q.single_mut() {
            let y = crate::worldmap::ground_at_world(*x, *z).unwrap_or(hero.y);
            hero.pos = Vec2::new(*x, *z);
            hero.y = y;
            hero.facing = az + std::f32::consts::PI;
            hero.vel = Vec2::ZERO;
            tf.translation = Vec3::new(*x, y, *z);
            tf.rotation = Quat::from_rotation_y(hero.facing);
        }
        orbit.azimuth = *az;
        orbit.pitch = *pitch;
        orbit.dist = *dist;
        orbit.boom = BoomState::default();
    }
    *frame += 1;
    if !*shot && *frame >= 70 {
        commands
            .spawn(bevy::render::view::screenshot::Screenshot::primary_window())
            .observe(bevy::render::view::screenshot::save_to_disk(path.clone()));
        *shot = true;
    }
    if *shot && (std::path::Path::new(path).exists() || *frame > 900) {
        info!("boom shot saved: {path}");
        *idx += 1;
        *frame = 0;
        *shot = false;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn slab_clips_segment_to_box() {
        let (t0, t1) = slab(Vec3::new(-2.0, 0.0, 0.0), Vec3::new(4.0, 0.0, 0.0), Vec3::splat(-0.5), Vec3::splat(0.5)).unwrap();
        assert!((t0 - 0.375).abs() < 1e-5 && (t1 - 0.625).abs() < 1e-5);
        assert!(slab(Vec3::new(-2.0, 2.0, 0.0), Vec3::new(4.0, 0.0, 0.0), Vec3::splat(-0.5), Vec3::splat(0.5)).is_none());
    }

    #[test]
    fn triangle_hit_is_two_sided_and_segment_bounded() {
        let (a, b, c) = (Vec3::new(-1.0, -1.0, 1.0), Vec3::new(1.0, -1.0, 1.0), Vec3::new(0.0, 1.0, 1.0));
        let t = seg_tri(Vec3::ZERO, Vec3::new(0.0, 0.0, 2.0), a, b, c).unwrap();
        assert!((t - 0.5).abs() < 1e-5);
        // Reverse winding still hits (two-sided).
        assert!(seg_tri(Vec3::ZERO, Vec3::new(0.0, 0.0, 2.0), a, c, b).is_some());
        // Segment stopping short of the plane misses.
        assert!(seg_tri(Vec3::ZERO, Vec3::new(0.0, 0.0, 0.5), a, b, c).is_none());
    }

    #[test]
    fn cuboid_mesh_crossings_pair_up() {
        let m = Cuboid::new(1.0, 1.0, 1.0).mesh().build();
        let mut hits = Vec::new();
        assert!(collect_tri_hits(&m, Vec3::new(-2.0, 0.1, 0.13), Vec3::new(4.0, 0.0, 0.0), &mut hits));
        hits.sort_by(|x, y| x.total_cmp(y));
        hits.dedup_by(|x, y| (*x - *y).abs() < 1e-4);
        assert_eq!(hits.len(), 2);
        assert!((hits[1] - hits[0] - 0.25).abs() < 1e-4); // 1u chord over a 4u segment
    }
}
