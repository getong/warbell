//! **Townsfolk tools, gripped for real.** A townsperson's right hand holds a [`HeldTool`] (picked
//! from the outfit at spawn); these clips make the hands actually hold it in every state:
//!
//! - **work** — the woodcutter's chop, the miner's pick blow and the farmer's hoe are keyed
//!   two-handed strokes ([`Stroke`]): the left fist rides the haft, the right slides on it, the
//!   trunk turns and pitches into the blow and the feet stay planted by leg IK. Each arm is solved
//!   onto the haft by a swivel IK ([`grip`]): the hand reaches its point on the haft, the fist hole
//!   runs along the haft (thumb toward the head, or the butt for the hoe's broom grip), and the
//!   elbow swivel is the one that keeps forearm twist, upper-arm roll and wrist deviation inside an
//!   anatomical range. The axe/pick blow lands on the [`stroke_impact_in`] beat, which the
//!   lumberjack / miner time their chop cue + damage off.
//! - **at ease** — the axe and pick ride the right shoulder, head behind; the hoe stands upright
//!   beside the right foot at a stop and goes onto the shoulder for the walk.
//! - **hauling** — the tool is slung across the back while both hands grip the load: a log cradled
//!   against the chest ([`LOG_CRADLE`]) or a handcart's shafts at the sides ([`CART_GRIP`]).
//! - **fighting** — a worker cornered by a wolf swings the work stroke at it.
//! - the guard's buckler is held by its centre grip and the archer's stave runs through the fist.
//!
//! Every frame is solved from scratch (no per-mob state): a handful of arm/leg IK solves, no
//! allocation. Rig units throughout (the studio rig frame: x right, y up, z forward, feet planted
//! on y = 0.06).

use std::f32::consts::{PI, TAU};
use std::sync::OnceLock;

use bevy::prelude::*;

use super::{action_over_loco, attack_phase, attack_pose, bow_pose, carry_pose, ease_out_cubic, lerp, loco_pose, rest, rx, sit_pose, smoothstep, work_pose, Jp, Pose};
use crate::biped::BipedDrive;
use crate::player::ATTACK_DURATION;

/// What a townsperson holds in the right hand — set from the outfit at spawn
/// (`villagers::build_biped_body`). Steers [`biped_tool_pose`]: which grip the clips solve for,
/// the work stroke, the carry at ease and where the tool goes while the hands haul a load.
#[derive(Clone, Copy, PartialEq, Eq, Default, Debug)]
pub enum HeldTool {
    /// Empty-handed, or a rig that isn't a townsperson (orks): the plain studio clips.
    #[default]
    None,
    /// The guard's arming sword, with the round buckler on the left fist.
    Sword,
    /// The archer's longbow on the left fist (a nocked arrow in the right).
    Bow,
    Axe,
    Pick,
    Hoe,
}

// ── Rig layout (`biped::spawn_biped`) ─────────────────────────────────────────────────
const UPPER: f32 = 0.30;
const FORE: f32 = 0.25;
const THIGH: f32 = 0.40;
const SHIN: f32 = 0.45;
const HIPS_Y: f32 = 1.05;
const TORSO_UP: f32 = 0.15;
const SHOULDER_Y: f32 = 0.27;
const SHOULDER_Z: f32 = 0.01;
/// Rig-frame height of a planted foot joint (the sole is 9 cm below it, on the ground at 0.06).
const ANKLE_Y: f32 = 0.15;

/// The joint spacing a rig was spawned with (`spawn_biped`'s `hip_dx` / `shoulder_dx`).
#[derive(Clone, Copy, PartialEq)]
struct Rig {
    hip_dx: f32,
    sh_dx: f32,
}

impl Rig {
    const KIT: Rig = Rig { hip_dx: crate::peasant_model::KIT_HIP_DX, sh_dx: crate::peasant_model::KIT_SHOULDER_DX };
    fn of(d: &BipedDrive) -> Rig {
        if d.limb_dx.x > 0.0 && d.limb_dx.y > 0.0 {
            Rig { hip_dx: d.limb_dx.x, sh_dx: d.limb_dx.y }
        } else {
            Rig::KIT
        }
    }
    fn shoulder(self, side: f32) -> Vec3 {
        Vec3::new(side * self.sh_dx, SHOULDER_Y, SHOULDER_Z)
    }
}

// ── Keyed strokes ─────────────────────────────────────────────────────────────────────
/// Stroke channels, in [`Key::v`] order. Hip drop/shift, hip + trunk yaw, trunk pitch; the anchor
/// (left) fist in the trunk frame; the haft's swing angle from vertical (`alpha`) in a plane
/// rolled by `rho` about the forward axis; the right fist's height on the haft; the preferred
/// wrist deviations; the head's nod onto the work.
const HDY: usize = 0;
const HDZ: usize = 1;
const HYAW: usize = 2;
const TYAW: usize = 3;
const TPITCH: usize = 4;
const LX: usize = 5;
const LY: usize = 6;
const LZ: usize = 7;
const ALPHA: usize = 8;
const RHO: usize = 9;
const GR: usize = 10;
const DEVL: usize = 11;
const DEVR: usize = 12;
const HEAD: usize = 13;
const CHANNELS: usize = 14;

#[derive(Clone, Copy)]
enum Seg {
    /// Monotone cubic through the neighbouring keys (no overshoot, flat at turning points).
    Smooth,
    /// Accelerating into the next key — the strike segment (fastest at the blow).
    Strike,
}

struct Key {
    t: f32,
    ease: Seg,
    v: [f32; CHANNELS],
}

const fn key(t: f32, ease: Seg, v: [f32; CHANNELS]) -> Key {
    Key { t, ease, v }
}

/// One looping two-handed work stroke.
struct Stroke {
    /// Seconds per stroke at work.
    period: f32,
    /// The left (anchor) fist's height up the haft (tool-local y).
    gl: f32,
    /// Thumb polarity per hand (left, right): +1 thumb toward the head, -1 toward the butt.
    pol: (f32, f32),
    /// Planted feet, rig-frame (x, z) for a 0.1 hip spacing (left, right).
    stance: [Vec2; 2],
    /// The strike's arc: (from, to, reach) — the fists swing out on a curve through the blow
    /// instead of a straight chord past the chest.
    arc: Option<(f32, f32, f32)>,
    /// Stroke times of the top of the backswing and of the blow.
    top: f32,
    impact: f32,
    keys: &'static [Key],
}

/// A two-handed work tool as `people.py` builds it: the haft runs tool-local +Y from the butt
/// (-0.05), the right fist's grip at the origin, the cutting edge facing +X.
struct Tool {
    /// Haft top.
    top: f32,
    /// The working points (the axe's bit and poll, the pick's two points, the hoe's blade edge).
    #[cfg_attr(not(test), allow(dead_code))] // the ground / reach checks in the tests
    points: [Vec3; 2],
    /// Where the right fist holds the haft on the shoulder carry.
    carry_grip: f32,
    stroke: Stroke,
}

use Seg::{Smooth as S, Strike as IN};

/// The woodcutter's felling chop: a batter's raise over the right shoulder, the trunk wound up,
/// then the bit driven level-ish into the bark at waist height with the hips and trunk unwinding.
static AXE: Tool = Tool {
    top: 0.80,
    points: [Vec3::new(0.19, 0.72, 0.0), Vec3::new(-0.04, 0.72, 0.0)],
    carry_grip: 0.20,
    stroke: Stroke {
        period: 2.1,
        gl: 0.02,
        pol: (1.0, 1.0),
        stance: [Vec2::new(-0.13, 0.14), Vec2::new(0.15, -0.10)],
        arc: None,
        top: 0.42,
        impact: 0.54,
        keys: &[
            //            hdy    hdz   hyaw   tyaw  tpitch   lx     ly    lz   alpha    rho    gr   devl  devr  head
            key(0.00, S, [-0.03, 0.00, 0.05, 0.08, 0.10, 0.03, -0.20, 0.17, 1.05, -0.20, 0.16, 0.30, 0.30, 0.12]),
            key(0.30, S, [-0.02, -0.02, 0.26, 0.32, -0.06, 0.14, 0.14, 0.26, -0.55, -0.45, 0.16, 0.20, 0.20, -0.05]),
            key(0.42, IN, [-0.02, -0.03, 0.30, 0.38, -0.08, 0.14, 0.15, 0.25, -0.65, -0.45, 0.16, 0.20, 0.20, -0.05]),
            key(0.54, S, [-0.05, 0.04, -0.15, -0.20, 0.32, 0.05, -0.14, 0.20, 1.50, -0.55, 0.12, 0.35, 0.35, 0.18]),
            key(0.64, S, [-0.05, 0.04, -0.14, -0.19, 0.32, 0.05, -0.14, 0.20, 1.48, -0.55, 0.12, 0.35, 0.35, 0.18]),
            key(0.80, S, [-0.04, 0.02, -0.02, -0.02, 0.18, 0.04, -0.17, 0.18, 1.25, -0.40, 0.14, 0.30, 0.30, 0.12]),
        ],
    },
};

/// The miner's pick blow: raised straight overhead, then brought down on a forward arc so the
/// point bites the rock face at waist height, angled down into it.
static PICK: Tool = Tool {
    top: 0.80,
    points: [Vec3::new(0.24, 0.70, 0.0), Vec3::new(-0.24, 0.70, 0.0)],
    carry_grip: 0.22,
    stroke: Stroke {
        period: 2.1,
        gl: 0.02,
        pol: (1.0, 1.0),
        stance: [Vec2::new(-0.12, 0.12), Vec2::new(0.14, -0.08)],
        arc: Some((0.42, 0.54, 0.20)),
        top: 0.42,
        impact: 0.54,
        keys: &[
            //            hdy    hdz   hyaw   tyaw  tpitch   lx     ly    lz   alpha    rho    gr   devl  devr  head
            key(0.00, S, [-0.03, 0.00, 0.04, 0.05, 0.12, 0.03, -0.20, 0.17, 1.05, -0.10, 0.16, 0.30, 0.30, 0.15]),
            key(0.30, S, [-0.02, -0.02, 0.12, 0.14, -0.08, 0.10, 0.20, 0.25, -0.75, -0.20, 0.16, 0.20, 0.20, -0.08]),
            key(0.42, IN, [-0.02, -0.03, 0.12, 0.15, -0.10, 0.10, 0.22, 0.24, -0.85, -0.20, 0.16, 0.20, 0.20, -0.08]),
            key(0.54, S, [-0.08, 0.05, -0.02, -0.03, 0.35, 0.04, -0.12, 0.26, 0.68, -0.10, 0.12, 0.35, 0.35, 0.30]),
            key(0.64, S, [-0.08, 0.05, -0.02, -0.03, 0.35, 0.04, -0.12, 0.26, 0.70, -0.10, 0.12, 0.35, 0.35, 0.30]),
            key(0.80, S, [-0.05, 0.03, 0.02, 0.02, 0.24, 0.03, -0.18, 0.18, 1.25, -0.10, 0.14, 0.30, 0.30, 0.20]),
        ],
    },
};

/// The farmer's chop-and-draw with a long hoe: right fist at the butt, left fist choked up the
/// haft, both thumbs toward the butt (the broom grip). Lift the blade to knee height out front,
/// chop it into the soil bent well over, then draw it back toward the feet through the dirt.
static HOE: Tool = Tool {
    top: 1.25,
    points: [Vec3::new(0.17, 1.17, 0.0), Vec3::new(0.03, 1.21, 0.0)],
    carry_grip: 0.35,
    stroke: Stroke {
        period: 1.6,
        gl: 0.27,
        pol: (-1.0, -1.0),
        stance: [Vec2::new(-0.12, 0.16), Vec2::new(0.14, -0.10)],
        arc: None,
        top: 0.40,
        impact: 0.50,
        keys: &[
            //            hdy    hdz   hyaw   tyaw  tpitch   lx     ly    lz   alpha    rho    gr   devl  devr  head
            key(0.00, S, [-0.10, -0.04, 0.05, 0.05, 0.50, -0.10, 0.05, 0.37, 2.21, -0.30, 0.02, 0.25, 0.25, 0.30]),
            key(0.30, S, [-0.03, 0.00, 0.05, 0.05, 0.15, -0.06, 0.19, 0.47, 1.75, -0.30, 0.02, 0.20, 0.20, 0.15]),
            key(0.40, IN, [-0.03, 0.00, 0.05, 0.05, 0.14, -0.06, 0.21, 0.47, 1.70, -0.30, 0.02, 0.20, 0.20, 0.15]),
            key(0.50, S, [-0.12, -0.04, 0.05, 0.05, 0.60, -0.10, 0.10, 0.49, 1.93, -0.30, 0.02, 0.25, 0.25, 0.35]),
            key(0.60, S, [-0.12, -0.04, 0.05, 0.05, 0.60, -0.10, 0.09, 0.48, 1.95, -0.30, 0.02, 0.25, 0.25, 0.35]),
        ],
    },
};

fn long_tool(t: HeldTool) -> Option<&'static Tool> {
    match t {
        HeldTool::Axe => Some(&AXE),
        HeldTool::Pick => Some(&PICK),
        HeldTool::Hoe => Some(&HOE),
        _ => None,
    }
}

/// Channel `c` of a looping keyed stroke at stroke time `x` (wraps at 1): a monotone cubic
/// Hermite through the keys (tangents flattened at turning points, clamped to 3x the secant so
/// nothing overshoots), or the accelerating strike ease on [`Seg::Strike`] segments.
fn chan(keys: &[Key], c: usize, x: f32) -> f32 {
    let n = keys.len() as i32;
    let x = x.rem_euclid(1.0);
    // Key `j` unrolled across loop boundaries: (time, value).
    let at = |j: i32| -> (f32, f32) {
        let k = &keys[j.rem_euclid(n) as usize];
        (k.t + j.div_euclid(n) as f32, k.v[c])
    };
    let i = if x >= keys[0].t { keys.iter().rposition(|k| k.t <= x).unwrap_or(0) as i32 } else { n - 1 };
    let (p0, v0) = at(i);
    let (p1, v1) = at(i + 1);
    let x = if x < p0 { x + 1.0 } else { x };
    let h = p1 - p0;
    let t = ((x - p0) / h).clamp(0.0, 1.0);
    if let Seg::Strike = keys[i.rem_euclid(n) as usize].ease {
        return v0 + (v1 - v0) * t.powf(2.4);
    }
    let tangent = |j: i32| -> f32 {
        let ((pa, va), (pk, vk), (pb, vb)) = (at(j - 1), at(j), at(j + 1));
        let (s0, s1) = ((vk - va) / (pk - pa), (vb - vk) / (pb - pk));
        if s0 * s1 <= 0.0 {
            return 0.0;
        }
        let lim = 3.0 * s0.abs().min(s1.abs());
        ((vb - va) / (pb - pa)).clamp(-lim, lim)
    };
    let (m0, m1) = (tangent(i), tangent(i + 1));
    let (t2, t3) = (t * t, t * t * t);
    (2.0 * t3 - 3.0 * t2 + 1.0) * v0 + (t3 - 2.0 * t2 + t) * h * m0 + (-2.0 * t3 + 3.0 * t2) * v1 + (t3 - t2) * h * m1
}

/// Every channel of `s` at stroke time `x`, with the strike's outward arc added.
fn frame(s: &Stroke, x: f32) -> [f32; CHANNELS] {
    let mut v = [0.0; CHANNELS];
    for (c, o) in v.iter_mut().enumerate() {
        *o = chan(s.keys, c, x);
    }
    if let Some((a0, a1, reach)) = s.arc {
        let x = x.rem_euclid(1.0);
        if (a0..a1).contains(&x) {
            let k = reach * (PI * ((x - a0) / (a1 - a0)).powf(2.4)).sin();
            v[LZ] += k;
            v[LY] += 0.4 * k;
        }
    }
    v
}

/// The haft direction and the leading-edge direction for a swing angle `alpha` (from vertical,
/// toward forward) in the plane rolled `rho` about the forward axis. The edge leads the swing.
fn swing_axes(alpha: f32, rho: f32) -> (Vec3, Vec3) {
    let roll = Quat::from_rotation_z(rho);
    let (s, c) = alpha.sin_cos();
    (roll * Vec3::new(0.0, c, s), roll * Vec3::new(0.0, -s, c))
}

/// A tool frame (tool-local X = `edge`, Y = `haft`), re-orthogonalised.
fn tool_frame(haft: Vec3, edge: Vec3) -> Quat {
    let y = haft.normalize();
    let x = (edge - y * edge.dot(y)).normalize_or(y.any_orthonormal_vector());
    Quat::from_mat3(&Mat3::from_cols(x, y, x.cross(y)))
}

// ── Arm IK: the fist on the haft ──────────────────────────────────────────────────────
/// One solved arm (trunk frame): the shoulder + elbow rotations and the hand joint's place.
#[derive(Clone, Copy)]
struct Arm {
    sh: Quat,
    el: Quat,
    hand: Vec3,
    /// The hand joint's rotation (= the forearm's; there is no wrist joint).
    frame: Quat,
}

impl Arm {
    /// The arm a pose's right-arm joints already describe (forward kinematics).
    fn of(sh: Quat, el: Quat, s: Vec3) -> Arm {
        let frame = sh * el;
        Arm { sh, el, hand: s + sh * Vec3::new(0.0, -UPPER, 0.0) + frame * Vec3::new(0.0, -FORE, 0.0), frame }
    }
    /// The `Sword` (or `Shield`) joint transform that puts a tool's origin at `origin` with
    /// rotation `rot` (both trunk frame) — the joint hangs off this hand.
    fn holding(&self, origin: Vec3, rot: Quat) -> Jp {
        let inv = self.frame.inverse();
        Jp { t: Some(inv * (origin - self.hand)), r: inv * rot }
    }
}

/// The elbow circle for a shoulder→hand reach.
struct Cone {
    s: Vec3,
    h: Vec3,
    hz: Vec3,
    n: Vec3,
    x0: f32,
    rad: f32,
    p: Vec3,
    q: Vec3,
}

/// Swivel cost weights: forearm twist, upper-arm roll, wrist deviation off its keyed preference,
/// deviation past the anatomical band (radial 20° .. ulnar 35°), and a mild elbow-down-and-out
/// preference. The band is soft enough that the cost keeps one valley as the stroke moves, so the
/// solved elbow never flips between two swivels mid-swing.
const W_TAU: f32 = 1.0;
const W_HUM: f32 = 0.6;
const W_DEV: f32 = 0.5;
const W_BAND: f32 = 4.0;
const W_POLE: f32 = 0.3;
const DEV_RADIAL: f32 = -0.35;
const DEV_ULNAR: f32 = 0.62;
/// Coarse swivel samples, then golden-section steps round the best one.
const SWIVEL_SAMPLES: usize = 16;
const SWIVEL_REFINE: usize = 9;

struct Swivel {
    elbow: Vec3,
    upper: Mat3,
    flex: f32,
    twist: f32,
    roll: f32,
    dev: f32,
}

/// The arm with its elbow at swivel angle `ph` on the cone.
fn arm_at(c: &Cone, ph: f32) -> Swivel {
    let elbow = c.s + c.n * c.x0 + c.rad * (ph.cos() * c.p + ph.sin() * c.q);
    let w = (c.h - elbow).normalize_or(c.n);
    let u = (elbow - c.s).normalize_or(c.n);
    let hw = c.hz.dot(w).clamp(-1.0, 1.0);
    let dev = hw.asin();
    // The hand frame: -Y down the forearm, Z (the fist hole / thumb) along the haft.
    let yh = -w;
    let zh = (c.hz - hw * w).normalize_or(w.any_orthonormal_vector());
    let xh = yh.cross(zh);
    let xu = w.cross(u);
    let (upper, flex) = if xu.length_squared() < 1e-10 {
        (Mat3::from_cols(xh, yh, zh), 0.0)
    } else {
        let xu = xu.normalize();
        let yu = -u;
        (Mat3::from_cols(xu, yu, xu.cross(yu)), -u.dot(w).clamp(-1.0, 1.0).acos())
    };
    let xp = (upper * Mat3::from_rotation_x(flex)).transpose() * xh;
    let twist = (-xp.z).atan2(xp.x);
    // Upper-arm roll: the shoulder rotation's twist about the arm, measured from the minimal swing
    // that hangs the arm along `u`.
    let qq = Mat3::from_quat(Quat::from_rotation_arc(Vec3::NEG_Y, u)).transpose() * upper;
    let roll = qq.z_axis.x.atan2(qq.x_axis.x);
    Swivel { elbow, upper, flex, twist, roll, dev }
}

fn swivel_cost(c: &Cone, ph: f32, dev_pref: f32, pole: Vec3) -> f32 {
    let a = arm_at(c, ph);
    let band = (a.dev - DEV_ULNAR).max(0.0) + (DEV_RADIAL - a.dev).max(0.0);
    let mid = c.s + (c.h - c.s) * 0.5;
    W_TAU * a.twist * a.twist + W_HUM * a.roll * a.roll + W_DEV * (a.dev - dev_pref).powi(2) + W_BAND * band * band
        - W_POLE * (a.elbow - mid).normalize_or_zero().dot(pole)
}

/// Solve one arm so the fist closes round a haft at `h` (trunk frame) with the fist hole along
/// `hz` (the thumb's side of the haft). `s` is the shoulder; `pole` the elbow's preferred side.
/// An out-of-reach `h` straightens the arm toward it.
fn grip(s: Vec3, h: Vec3, hz: Vec3, dev_pref: f32, pole: Vec3) -> Arm {
    let d = h - s;
    let len = d.length().max(1e-4);
    let n = d / len;
    let reach = len.min(UPPER + FORE - 1e-4);
    let x0 = (UPPER * UPPER - FORE * FORE + reach * reach) / (2.0 * reach);
    let rad = (UPPER * UPPER - x0 * x0).max(0.0).sqrt();
    let p = n.any_orthonormal_vector();
    let c = Cone { s, h, hz: hz.normalize_or(Vec3::Z), n, x0, rad, p, q: n.cross(p) };
    let step = TAU / SWIVEL_SAMPLES as f32;
    let mut best = (0, f32::MAX);
    for i in 0..SWIVEL_SAMPLES {
        let k = swivel_cost(&c, step * i as f32, dev_pref, pole);
        if k < best.1 {
            best = (i, k);
        }
    }
    let g = (5.0_f32.sqrt() - 1.0) * 0.5;
    let (mut a, mut b) = (step * (best.0 as f32 - 1.0), step * (best.0 as f32 + 1.0));
    for _ in 0..SWIVEL_REFINE {
        let (c1, c2) = (b - g * (b - a), a + g * (b - a));
        if swivel_cost(&c, c1, dev_pref, pole) < swivel_cost(&c, c2, dev_pref, pole) {
            b = c2;
        } else {
            a = c1;
        }
    }
    let sw = arm_at(&c, 0.5 * (a + b));
    let sh = Quat::from_mat3(&sw.upper);
    let el = rx(sw.flex) * Quat::from_rotation_y(sw.twist);
    Arm::of(sh, el, s)
}

/// Elbow preference: down, back and out to the arm's own side.
fn pole(side: f32) -> Vec3 {
    Vec3::new(0.5 * side, -0.7, -0.5).normalize()
}

// ── Leg IK: planted feet ──────────────────────────────────────────────────────────────
/// Hip / knee / foot rotations putting an ankle (rig frame) on `ankle` from a hip at `hip`, the
/// knee tracking forward over a foot turned `foot_yaw` and the sole kept flat.
fn plant_leg(hip: Vec3, ankle: Vec3, hips_r: Quat, foot_yaw: f32) -> (Quat, Quat, Quat) {
    let d = ankle - hip;
    let len = d.length().clamp(0.1, THIGH + SHIN - 1e-3);
    let n = d.normalize_or(Vec3::NEG_Y);
    let knee = PI - ((THIGH * THIGH + SHIN * SHIN - len * len) / (2.0 * THIGH * SHIN)).clamp(-1.0, 1.0).acos();
    let b = ((THIGH * THIGH + len * len - SHIN * SHIN) / (2.0 * THIGH * len)).clamp(-1.0, 1.0).acos();
    let toes = Quat::from_rotation_y(foot_yaw);
    let fwd = toes * Vec3::Z;
    let pole = (fwd - n * fwd.dot(n)).normalize_or(Vec3::Z);
    let thigh = n * b.cos() + pole * b.sin();
    let (y, z) = (-thigh, pole * b.cos() - n * b.sin());
    let thigh_r = Quat::from_mat3(&Mat3::from_cols(y.cross(z), y, z));
    let knee_r = rx(knee);
    (hips_r.inverse() * thigh_r, knee_r, (thigh_r * knee_r).inverse() * toes)
}

// ── Strokes → poses ───────────────────────────────────────────────────────────────────
/// A solved stroke frame: the pose plus what the tests check it against (trunk frame).
#[cfg_attr(not(test), allow(dead_code))]
struct Solved {
    pose: Pose,
    left: Arm,
    right: Arm,
    /// Tool origin (the right fist's zero), haft axis and tool rotation.
    origin: Vec3,
    haft: Vec3,
    rot: Quat,
    /// Planted ankle targets (rig frame), left then right.
    feet: [Vec3; 2],
}

fn solve_stroke(tool: &Tool, x: f32, rig: Rig) -> Solved {
    let s = &tool.stroke;
    let v = frame(s, x);
    let mut p = rest();
    let hips_r = Quat::from_rotation_y(v[HYAW]);
    let hips_t = Vec3::new(0.0, HIPS_Y + v[HDY], v[HDZ]);
    p.hips = Jp { t: Some(hips_t), r: hips_r };
    p.torso = Jp::r(Quat::from_rotation_y(v[TYAW] - v[HYAW]) * rx(v[TPITCH]));
    // Eyes on the work: the head turns back against the trunk's wind-up and nods onto the blow.
    p.head = Jp::r(Quat::from_rotation_y(-0.8 * v[TYAW]) * rx(v[HEAD]));

    let (haft, edge) = swing_axes(v[ALPHA], v[RHO]);
    let rot = tool_frame(haft, edge);
    let hl = Vec3::new(v[LX], v[LY], v[LZ]);
    let origin = hl - haft * s.gl;
    let hr = origin + haft * v[GR];
    let right = grip(rig.shoulder(1.0), hr, s.pol.1 * haft, v[DEVR], pole(1.0));
    let left = grip(rig.shoulder(-1.0), hl, s.pol.0 * haft, v[DEVL], pole(-1.0));
    p.sh_r = Jp::r(right.sh);
    p.el_r = Jp::r(right.el);
    p.sh_l = Jp::r(left.sh);
    p.el_l = Jp::r(left.el);
    p.sword = right.holding(origin, rot);

    // Feet planted on the stance (spread with the rig's hips), toes turned out a touch.
    let spread = rig.hip_dx - Rig::KIT.hip_dx;
    let feet = [
        Vec3::new(s.stance[0].x - spread, ANKLE_Y, s.stance[0].y),
        Vec3::new(s.stance[1].x + spread, ANKLE_Y, s.stance[1].y),
    ];
    for (i, side) in [-1.0_f32, 1.0].into_iter().enumerate() {
        let hip = hips_t + hips_r * Vec3::new(side * rig.hip_dx, -0.05, 0.0);
        let (h, k, f) = plant_leg(hip, feet[i], hips_r, 0.5 * v[HYAW] + 0.12 * side);
        if i == 0 {
            (p.hip_l, p.knee_l, p.foot_l) = (Jp::r(h), Jp::r(k), Jp::r(f));
        } else {
            (p.hip_r, p.knee_r, p.foot_r) = (Jp::r(h), Jp::r(k), Jp::r(f));
        }
    }
    Solved { pose: p, left, right, origin, haft, rot, feet }
}

/// Seconds from stroke clock `clock` (s, the same clock [`biped_tool_pose`] works on: elapsed time
/// + the drive's `phase`) until `tool`'s next blow lands — the lumberjack / miner time the chop
/// cue and the damage tick off this, so the bark takes the hit when the bit meets it.
pub(crate) fn stroke_impact_in(tool: HeldTool, clock: f32) -> Option<f32> {
    let s = &long_tool(tool)?.stroke;
    let now = (clock / s.period).rem_euclid(1.0);
    Some((s.impact - now).rem_euclid(1.0) * s.period)
}

/// The work cooldown until `tool`'s next blow on stroke clock `clock`: the very next one when the
/// worker has just stepped up to the post (`fresh`), else the one a whole stroke on (so a blow
/// timed to land this frame doesn't count again next frame). Empty hands: no wait.
pub(crate) fn next_blow_in(tool: HeldTool, clock: f32, fresh: bool) -> f32 {
    let (Some(wait), Some(t)) = (stroke_impact_in(tool, clock), long_tool(tool)) else {
        return 0.0;
    };
    if !fresh && wait < 0.5 * t.stroke.period {
        wait + t.stroke.period
    } else {
        wait
    }
}

/// Where a fight blow ([`attack_stroke_t`]) has wound back up to the top of the swing, after which
/// the pose eases back onto the carry.
const ATTACK_RECOVERED: f32 = 0.85;

/// A one-shot swing of the work stroke as a fight blow (`ap` = 0..1 through the attack): cock up to
/// the top, drive through to the blow at combat's strike beat, then follow through and lift round
/// to the top again — the stroke's own path both ways, so easing in from / back to the carry only
/// ever blends between neighbouring poses (never the haft through the body).
fn attack_stroke_t(s: &Stroke, ap: f32) -> f32 {
    const WIND: f32 = 0.30;
    const BLOW: f32 = 0.45;
    if ap < WIND {
        lerp(s.top - 0.08, s.top, ease_out_cubic(ap / WIND))
    } else if ap < BLOW {
        lerp(s.top, s.impact, (ap - WIND) / (BLOW - WIND))
    } else {
        lerp(s.impact, 1.0 + s.top, smoothstep((ap - BLOW) / (ATTACK_RECOVERED - BLOW)))
    }
}

// ── At ease, slung, hauling ───────────────────────────────────────────────────────────
/// The right arm + held-tool transform for a tool carried on the right shoulder: the fist in front
/// of and below the shoulder, the haft resting on the trapezius, the head behind with its edge out.
#[derive(Clone, Copy)]
struct Carry {
    sh: Quat,
    el: Quat,
    sword: Jp,
}

fn solve_shoulder_carry(tool: &Tool, rig: Rig) -> Carry {
    let x = rig.sh_dx;
    let hand = Vec3::new(x - 0.03, 0.16, 0.22);
    let rest_on = Vec3::new(x - 0.05, 0.36, 0.0);
    let haft = (rest_on - hand).normalize();
    let arm = grip(rig.shoulder(1.0), hand, haft, 0.1, pole(1.0));
    let rot = tool_frame(haft, Vec3::X);
    Carry { sh: arm.sh, el: arm.el, sword: arm.holding(arm.hand - haft * tool.carry_grip, rot) }
}

/// [`solve_shoulder_carry`] for the kit body's layout, solved once (it's fixed in the trunk frame).
fn shoulder_carry(tool: &'static Tool, rig: Rig) -> Carry {
    static KIT: OnceLock<[Carry; 3]> = OnceLock::new();
    if rig != Rig::KIT {
        return solve_shoulder_carry(tool, rig);
    }
    let all = KIT.get_or_init(|| [&AXE, &PICK, &HOE].map(|t| solve_shoulder_carry(t, Rig::KIT)));
    let i = if std::ptr::eq(tool, &AXE) {
        0
    } else if std::ptr::eq(tool, &PICK) {
        1
    } else {
        2
    };
    all[i]
}

/// The trunk joint's place + rotation in the rig frame for pose `p`.
fn trunk(p: &Pose) -> (Vec3, Quat) {
    let hips_t = p.hips.t.unwrap_or(Vec3::new(0.0, HIPS_Y, 0.0));
    (hips_t + p.hips.r * Vec3::new(0.0, TORSO_UP, 0.0), p.hips.r * p.torso.r)
}

/// Grip a rig-frame point with the right fist (fist hole along `hz`, rig frame) from pose `p`'s
/// trunk — for props that stand in the world frame (a grounded hoe, a cart's shafts).
fn grip_rig_point(p: &Pose, rig: Rig, side: f32, at: Vec3, hz: Vec3, dev: f32) -> (Arm, Vec3, Quat) {
    let (tp, tr) = trunk(p);
    let inv = tr.inverse();
    let arm = grip(rig.shoulder(side), inv * (at - tp), inv * hz, dev, pole(side));
    (arm, tp, inv)
}

/// The hoe at a stop: standing upright on its butt beside the right foot, the fist round the haft
/// at chest height, blade up and facing forward.
fn hoe_upright(p: &Pose, rig: Rig) -> Carry {
    let butt = Vec3::new(rig.hip_dx + 0.20, 0.08, 0.16);
    let haft = Vec3::new(-0.04, 1.0, 0.03).normalize();
    let origin = butt + haft * 0.05;
    let grip_at = 0.97;
    let (arm, tp, inv) = grip_rig_point(p, rig, 1.0, origin + haft * grip_at, haft, 0.0);
    let rot = inv * tool_frame(haft, Vec3::Z);
    Carry { sh: arm.sh, el: arm.el, sword: arm.holding(inv * (origin - tp), rot) }
}

fn put_right(p: &mut Pose, c: &Carry) {
    p.sh_r = Jp::r(c.sh);
    p.el_r = Jp::r(c.el);
    p.sword = c.sword;
}

fn blend_carry(a: &Carry, b: &Carry, s: f32) -> Carry {
    Carry { sh: a.sh.slerp(b.sh, s), el: a.el.slerp(b.el, s), sword: a.sword.lerp(b.sword, s) }
}

/// The tool at ease over a locomotion pose: shouldered while walking (and the axe / pick at a
/// stop too); the hoe eases from upright at a stop onto the shoulder as the walk picks up.
fn at_ease(tool: &'static Tool, loco: &Pose, moving: f32, rig: Rig) -> Pose {
    let mut p = *loco;
    let shoulder = shoulder_carry(tool, rig);
    if std::ptr::eq(tool, &HOE) && moving < 0.6 {
        let up = hoe_upright(loco, rig);
        put_right(&mut p, &blend_carry(&up, &shoulder, smoothstep(moving / 0.6)));
    } else {
        put_right(&mut p, &shoulder);
    }
    p
}

/// Sling the tool diagonally across the back (butt low at the left hip, head up behind the right
/// shoulder, blade flat to the back) whatever the right arm is doing — while both hands haul a
/// load, or sitting. Re-derived from the right hand each frame so the tool stays put on the back.
fn sling(p: &mut Pose, tool: &Tool, rig: Rig) {
    let hand = Arm::of(p.sh_r.r, p.el_r.r, rig.shoulder(1.0));
    let haft = Vec3::new(0.42, 0.9, -0.05).normalize();
    let rot = tool_frame(haft, Vec3::Z.cross(haft));
    let origin = Vec3::new(0.0, 0.10, -0.18) - haft * (0.5 * tool.top);
    p.sword = hand.holding(origin, rot);
}

/// The log a woodcutter hauls home, cradled against the chest (rig frame, its long axis across
/// the body). `lumberjack::attach_log` (and the RTS haulers' load) put the prop here.
pub(crate) const LOG_CRADLE: Vec3 = Vec3::new(0.0, 1.31, 0.29);
/// Where the cradling fists sit under a load (rig frame, right hand; mirror x for the left).
const CRADLE_HAND: Vec3 = Vec3::new(0.23, 1.14, 0.27);
/// A carter's fists on the handcart shafts at his sides (rig frame, right hand) and the shafts'
/// rise (rad) toward the front — `miner::attach_cart` builds the cart's shafts through these.
pub(crate) const CART_GRIP: Vec3 = Vec3::new(0.27, 0.97, 0.14);
pub(crate) const CART_SHAFT_PITCH: f32 = 0.588;

/// Both hands on the load, solved against the walking trunk each frame so the fists stay on a
/// prop that is fixed to the body root: under a cradled log (palms up), or round a pulled cart's
/// shafts (thumbs forward along them).
fn haul_grip(p: &mut Pose, rig: Rig, cart: bool) {
    for side in [-1.0_f32, 1.0] {
        let (at, hz, dev) = if cart {
            let shaft = Vec3::new(0.0, CART_SHAFT_PITCH.sin(), CART_SHAFT_PITCH.cos());
            (Vec3::new(side * CART_GRIP.x, CART_GRIP.y, CART_GRIP.z), shaft, 0.0)
        } else {
            (Vec3::new(side * CRADLE_HAND.x, CRADLE_HAND.y, CRADLE_HAND.z), Vec3::new(side, 0.0, 0.0), 0.0)
        };
        let (arm, _, _) = grip_rig_point(p, rig, side, at, hz, dev);
        if side > 0.0 {
            p.sh_r = Jp::r(arm.sh);
            p.el_r = Jp::r(arm.el);
        } else {
            p.sh_l = Jp::r(arm.sh);
            p.el_l = Jp::r(arm.el);
        }
    }
}

// ── Off-hand props of the fighting folk ───────────────────────────────────────────────
/// The guard's round buckler on the left fist: held by its centre grip (the boss right over the
/// knuckles), face turned outward. The board mesh bakes a +1.15 yaw (its face along
/// `(sin 1.15, 0, cos 1.15)`); this turns that face onto the hand's outer side (-X).
fn buckler() -> Jp {
    Jp { t: Some(Vec3::new(-0.055, -0.01, 0.0)), r: Quat::from_rotation_y(-PI * 0.5 - 1.15) }
}

/// The longbow at ease in the left fist: the grip in the fist, the stave through it, upper limb
/// tipped forward-up ~30° off the fist's axis. The draw (`bow_pose`) turns it upright from here.
pub(crate) const BOW_CARRY_T: Vec3 = Vec3::new(0.0, 0.005, 0.02);
pub(crate) fn bow_carry_r() -> Quat {
    rx(1.05)
}

// ── Entry point ───────────────────────────────────────────────────────────────────────
/// The whole pose for a biped holding `d.tool` — `None` for empty hands (and every ork), which
/// keep the plain studio clip selection in `biped::biped_pose`.
pub(crate) fn biped_tool_pose(d: &BipedDrive, now: f32) -> Option<Pose> {
    match d.tool {
        HeldTool::None => None,
        HeldTool::Sword | HeldTool::Bow => Some(armed_pose(d, now)),
        t => long_tool(t).map(|tool| work_tool_pose(d, tool, now)),
    }
}

/// The guard / archer: the studio clips, with the off-hand prop actually held.
fn armed_pose(d: &BipedDrive, now: f32) -> Pose {
    let moving = d.moving_amt.clamp(0.0, 1.0);
    let loco = loco_pose(now + 2.5 * d.phase, d.walk_phase, moving, d.run_amt.clamp(0.0, 1.0));
    let mut p = if d.sitting {
        sit_pose()
    } else if d.bow {
        let b = bow_pose(now + d.phase, d.bow_t);
        if moving > 0.05 {
            action_over_loco(&b, &loco, moving)
        } else {
            b
        }
    } else if d.attacking {
        let (phase, ap) = attack_phase((d.attack_t / ATTACK_DURATION).clamp(0.0, 1.0));
        let atk = attack_pose(d.attack_variant, &phase, ap);
        if moving > 0.05 {
            action_over_loco(&atk, &loco, moving)
        } else {
            atk
        }
    } else if d.carrying {
        action_over_loco(&carry_pose(), &loco, moving)
    } else if d.work != 0 && moving < 0.05 {
        work_pose(now + d.phase, d.work == 1)
    } else {
        loco
    };
    match d.tool {
        HeldTool::Sword => p.shield = buckler(),
        // The draw clip turns the bow itself; at ease it rides the fist.
        HeldTool::Bow if !d.bow => p.shield = Jp { t: Some(BOW_CARRY_T), r: bow_carry_r() },
        _ => {}
    }
    p
}

/// An axe / pick / hoe holder.
fn work_tool_pose(d: &BipedDrive, tool: &'static Tool, now: f32) -> Pose {
    let rig = Rig::of(d);
    if d.sitting {
        let mut p = sit_pose();
        sling(&mut p, tool, rig);
        return p;
    }
    let moving = d.moving_amt.clamp(0.0, 1.0);
    let loco = loco_pose(now + 2.5 * d.phase, d.walk_phase, moving, d.run_amt.clamp(0.0, 1.0));
    if d.attacking {
        // A cornered worker swings the work stroke at the foe, from and back to the carry.
        let ap = (d.attack_t / ATTACK_DURATION).clamp(0.0, 1.0);
        let blow = solve_stroke(tool, attack_stroke_t(&tool.stroke, ap), rig).pose;
        let ease = at_ease(tool, &loco, moving, rig);
        let w = smoothstep(ap / 0.15) * (1.0 - smoothstep((ap - ATTACK_RECOVERED) / (1.0 - ATTACK_RECOVERED)));
        let p = ease.lerp(&blow, w);
        return if moving > 0.05 { action_over_loco(&p, &loco, moving) } else { p };
    }
    if d.carrying {
        let mut p = loco;
        haul_grip(&mut p, rig, d.pulling);
        sling(&mut p, tool, rig);
        return p;
    }
    if d.work != 0 && moving < 0.5 {
        // Plying the trade at the post; easing out of it as the worker sets off.
        let work = solve_stroke(tool, (now + d.phase) / tool.stroke.period, rig).pose;
        if moving <= 0.0 {
            return work;
        }
        return work.lerp(&at_ease(tool, &loco, moving, rig), smoothstep(moving / 0.5));
    }
    at_ease(tool, &loco, moving, rig)
}

#[cfg(test)]
mod tests {
    use super::*;

    const GROUND_Y: f32 = 0.06;
    /// The head ball (trunk frame) a haft must stay out of.
    const HEAD_C: Vec3 = Vec3::new(0.0, 0.5, 0.03);
    const HEAD_R: f32 = 0.12;

    fn tools() -> [(&'static str, &'static Tool); 3] {
        [("axe", &AXE), ("pick", &PICK), ("hoe", &HOE)]
    }

    /// Distance from `p` to the segment `a`..`b`.
    fn seg_dist(p: Vec3, a: Vec3, b: Vec3) -> f32 {
        let ab = b - a;
        let t = ((p - a).dot(ab) / ab.length_squared()).clamp(0.0, 1.0);
        (a + ab * t - p).length()
    }

    /// The forearm twist of an elbow rotation `rx(flex) * ry(twist)`.
    fn twist_of(el: Quat) -> f32 {
        let y = el * Vec3::Y;
        let x = rx(-y.z.atan2(y.y)) * el * Vec3::X;
        (-x.z).atan2(x.x)
    }

    /// Forward kinematics of a pose's ankles (rig frame).
    fn ankles(p: &Pose, rig: Rig) -> [Vec3; 2] {
        let hips_t = p.hips.t.unwrap();
        let mut out = [Vec3::ZERO; 2];
        for (i, (side, hip, knee)) in [(-1.0, p.hip_l.r, p.knee_l.r), (1.0, p.hip_r.r, p.knee_r.r)].into_iter().enumerate() {
            let hr = p.hips.r * hip;
            let kr = hr * knee;
            out[i] = hips_t + p.hips.r * Vec3::new(side * rig.hip_dx, -0.05, 0.0) + hr * Vec3::new(0.0, -THIGH, 0.0) + kr * Vec3::new(0.0, -SHIN, 0.0);
        }
        out
    }

    /// Both fists sit on the haft at every instant of every stroke, the arms stay inside a
    /// believable twist, the feet stay planted and the tool never digs the ground or the head.
    #[test]
    fn strokes_keep_both_fists_on_the_haft() {
        for rig in [Rig::KIT, Rig { hip_dx: 0.15, sh_dx: 0.3 }] {
            for (name, tool) in tools() {
                let s = &tool.stroke;
                for i in 0..240 {
                    let x = i as f32 / 240.0;
                    let o = solve_stroke(tool, x, rig);
                    let left_on = o.origin + o.haft * s.gl;
                    let v = frame(s, x);
                    let right_on = o.origin + o.haft * v[GR];
                    let reach_l = (left_on - rig.shoulder(-1.0)).length();
                    let reach_r = (right_on - rig.shoulder(1.0)).length();
                    // Within reach → the fist is ON the haft; the box rig's wider shoulders may
                    // fall a touch short and straighten toward it instead.
                    if rig == Rig::KIT {
                        assert!((o.left.hand - left_on).length() < 0.01, "{name} t={x}: left fist {:.3} off the haft (reach {reach_l:.3})", (o.left.hand - left_on).length());
                        assert!((o.right.hand - right_on).length() < 0.01, "{name} t={x}: right fist {:.3} off the haft (reach {reach_r:.3})", (o.right.hand - right_on).length());
                    } else {
                        assert!((o.left.hand - left_on).length() < 0.06 && (o.right.hand - right_on).length() < 0.06, "{name} t={x}: box-rig fists off the haft");
                    }
                    // The tool's place really is the right hand's (the Sword joint hangs off it).
                    let t = o.right.frame * o.pose.sword.t.unwrap() + o.right.hand;
                    assert!((t - o.origin).length() < 1e-3);
                    // Forearm twist inside the anatomical ±85°.
                    for (arm, side) in [(o.left, "left"), (o.right, "right")] {
                        let twist = twist_of(arm.el).to_degrees();
                        assert!(twist.abs() < 85.0, "{name} t={x}: {side} forearm wrung {twist:.0}°");
                    }
                    let (tp, tr) = trunk(&o.pose);
                    let world = |q: Vec3| tp + tr * q;
                    // Nothing below the ground (the hoe's blade may bite the topsoil).
                    let mut low = world(o.origin - o.haft * 0.05).y;
                    for pt in tool.points {
                        low = low.min(world(o.origin + o.rot * pt).y);
                    }
                    assert!(low > GROUND_Y - 0.03, "{name} t={x}: tool dug to y={low:.3}");
                    // The haft never passes through the head.
                    let d = seg_dist(HEAD_C, o.origin - o.haft * 0.05, o.origin + o.haft * tool.top);
                    assert!(d > HEAD_R, "{name} t={x}: haft through the head ({d:.3})");
                    // Feet planted on the stance.
                    for (a, f) in ankles(&o.pose, rig).iter().zip(o.feet) {
                        assert!((*a - f).length() < 0.01, "{name} t={x}: foot slid {:.3}", (*a - f).length());
                    }
                }
            }
        }
    }

    /// The stroke is one continuous motion: no joint jumps between neighbouring frames (a swivel
    /// flipping sides mid-swing would show as a one-frame elbow pop).
    #[test]
    fn strokes_have_no_pops() {
        for (name, tool) in tools() {
            let mut prev: Option<Pose> = None;
            for i in 0..=400 {
                let x = i as f32 / 400.0;
                let p = solve_stroke(tool, x, Rig::KIT).pose;
                if let Some(q) = prev {
                    for (a, b, j) in [(q.sh_r.r, p.sh_r.r, "sh_r"), (q.el_r.r, p.el_r.r, "el_r"), (q.sh_l.r, p.sh_l.r, "sh_l"), (q.el_l.r, p.el_l.r, "el_l"), (q.hip_l.r, p.hip_l.r, "hip_l"), (q.knee_r.r, p.knee_r.r, "knee_r")] {
                        let step = a.angle_between(b).to_degrees();
                        assert!(step < 14.0, "{name} t={x}: {j} jumped {step:.1}°");
                    }
                }
                prev = Some(p);
            }
        }
    }

    /// The blows land where the work is: the axe bit at the bark, the pick point on the rock
    /// face, the hoe blade in the soil.
    #[test]
    fn blows_land_on_the_work() {
        let at = |tool: &Tool, pt: usize| {
            let o = solve_stroke(tool, tool.stroke.impact, Rig::KIT);
            let (tp, tr) = trunk(&o.pose);
            tp + tr * (o.origin + o.rot * tool.points[pt])
        };
        let bit = at(&AXE, 0);
        assert!(bit.z > 0.7 && (0.5..1.0).contains(&bit.y), "axe bit at {bit}");
        let point = at(&PICK, 0);
        assert!(point.z > 0.85 && (0.7..1.3).contains(&point.y), "pick point at {point}");
        let blade = at(&HOE, 0);
        assert!(blade.z > 0.6 && (0.0..0.1).contains(&blade.y), "hoe blade at {blade}");
    }

    #[test]
    fn keyed_channels_pass_through_their_keys() {
        for (_, tool) in tools() {
            for k in tool.stroke.keys {
                for c in 0..CHANNELS {
                    assert!((chan(tool.stroke.keys, c, k.t) - k.v[c]).abs() < 1e-4);
                }
            }
        }
    }

    #[test]
    fn impact_clock_matches_the_stroke() {
        for t in [HeldTool::Axe, HeldTool::Pick, HeldTool::Hoe] {
            let s = &long_tool(t).unwrap().stroke;
            for clock in [0.0, 0.7, 3.3, 101.9] {
                let wait = stroke_impact_in(t, clock).unwrap();
                assert!((0.0..s.period).contains(&wait));
                let at = ((clock + wait) / s.period).rem_euclid(1.0);
                assert!((at - s.impact).abs() < 1e-3 || (at - s.impact).abs() > 0.999);
            }
        }
        assert!(stroke_impact_in(HeldTool::Sword, 1.0).is_none());
    }

    /// On the shoulder: the fist round the haft, the haft resting over the shoulder and clear of
    /// the head, the head of the tool behind the body.
    #[test]
    fn shoulder_carry_rests_on_the_shoulder() {
        for (name, tool) in tools() {
            let c = shoulder_carry(tool, Rig::KIT);
            let arm = Arm::of(c.sh, c.el, Rig::KIT.shoulder(1.0));
            let origin = arm.frame * c.sword.t.unwrap() + arm.hand;
            let haft = (arm.frame * c.sword.r) * Vec3::Y;
            // The fist is on the haft at the carry grip.
            assert!((origin + haft * tool.carry_grip - arm.hand).length() < 0.01, "{name}: fist off the haft");
            let (butt, top) = (origin - haft * 0.05, origin + haft * tool.top);
            assert!(seg_dist(HEAD_C, butt, top) > HEAD_R, "{name}: haft through the head");
            // Rests on (just above) the shoulder joint, not through the deltoid.
            let sd = seg_dist(Rig::KIT.shoulder(1.0), butt, top);
            assert!((0.05..0.14).contains(&sd), "{name}: haft {sd:.3} from the shoulder");
            assert!(top.z < -0.1, "{name}: head not behind the shoulder ({top})");
        }
    }

    /// A cornered worker's fight blow eases in from and back out to the carry without the haft
    /// sweeping through the head on the way.
    #[test]
    fn fight_blows_clear_the_head() {
        for (held, (name, tool)) in [HeldTool::Axe, HeldTool::Pick, HeldTool::Hoe].into_iter().zip(tools()) {
            for i in 0..=200 {
                let ap = i as f32 / 200.0;
                let d = BipedDrive { tool: held, attacking: true, attack_t: ap * ATTACK_DURATION, ..default() };
                let p = work_tool_pose(&d, tool, 0.0);
                let arm = Arm::of(p.sh_r.r, p.el_r.r, Rig::KIT.shoulder(1.0));
                let origin = arm.frame * p.sword.t.unwrap() + arm.hand;
                let haft = (arm.frame * p.sword.r) * Vec3::Y;
                let d = seg_dist(HEAD_C, origin - haft * 0.05, origin + haft * tool.top);
                assert!(d > HEAD_R, "{name} ap={ap}: haft {d:.3} from the head centre");
            }
        }
    }

    /// Slung on the back while hauling: the whole tool behind the trunk.
    #[test]
    fn sling_hangs_the_tool_on_the_back() {
        for (name, tool) in tools() {
            let mut p = rest();
            haul_grip(&mut p, Rig::KIT, false);
            sling(&mut p, tool, Rig::KIT);
            let arm = Arm::of(p.sh_r.r, p.el_r.r, Rig::KIT.shoulder(1.0));
            let origin = arm.frame * p.sword.t.unwrap() + arm.hand;
            let rot = arm.frame * p.sword.r;
            for q in [Vec3::new(0.0, -0.05, 0.0), Vec3::new(0.0, tool.top, 0.0), tool.points[0], tool.points[1]] {
                let w = origin + rot * q;
                assert!(w.z < -0.1, "{name}: {q} pokes forward to {w}");
            }
        }
    }

    /// Cradling a log / pulling a cart: both fists reach their grips.
    #[test]
    fn haul_fists_reach_the_load() {
        for cart in [false, true] {
            let mut p = rest();
            haul_grip(&mut p, Rig::KIT, cart);
            let (tp, tr) = trunk(&p);
            for (side, sh, el) in [(-1.0, p.sh_l.r, p.el_l.r), (1.0, p.sh_r.r, p.el_r.r)] {
                let hand = tp + tr * Arm::of(sh, el, Rig::KIT.shoulder(side)).hand;
                let want = if cart { CART_GRIP } else { CRADLE_HAND };
                let want = Vec3::new(side * want.x, want.y, want.z);
                assert!((hand - want).length() < 0.01, "cart={cart} side={side}: fist at {hand}, grip at {want}");
            }
        }
    }

    /// The archer's stave runs through the fist at ease (within the wrist's reach of the fist's
    /// axis), and the guard's buckler boss sits on the knuckles.
    #[test]
    fn off_hand_props_are_held() {
        let stave = bow_carry_r() * Vec3::Y;
        assert!(stave.angle_between(Vec3::Z) < 0.6, "stave {stave} not through the fist");
        assert!(BOW_CARRY_T.length() < 0.04);
        let b = buckler();
        assert!(b.t.unwrap().length() < 0.07);
        let face = b.r * (Quat::from_rotation_y(1.15) * Vec3::Z);
        assert!(face.angle_between(Vec3::NEG_X) < 0.05, "buckler faces {face}");
    }
}
