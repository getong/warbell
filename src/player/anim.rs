//! Hero limb animation, based on the user's three.js `updateKnightAnimation`
//! (low-poly-knight-studio): **idle / walk / run / jump /
//! defend / attack1 (overhead chop) / attack2 (horizontal slash) / attack3 (forward thrust) /
//! victory**. The studio builds each frame imperatively — reset every joint to rest, then a `switch`
//! case sets some — so we mirror that: [`rest`] seeds a full [`Pose`] table and each clip function
//! mutates the fields it touches. The per-frame system then writes the chosen pose onto the rig
//! joints.
//!
//! Game adaptations:
//! - **walk/jog/sprint** (the hero) are a procedural, foot-locked IK gait cut from the real ground
//!   speed (`Hero::gait_speed`; see [`footman_gait`]): the planted boot sweeps back exactly as fast
//!   as the body travels, the cadence follows from that ([`gait_phase_rate`]), and the style
//!   (walk → jog → sprint) is picked by speed. Other bipeds retain the shared studio walk/run clips.
//! - **clip changes** (take-off, landing, a swing starting, dash/charge) cross-fade from the last
//!   written pose instead of snapping ([`ClipBlend`]).
//! - **jump** — the studio faked the hop by sliding `hips.y`; here the **real jump physics own the
//!   height** (the root's world Y), so the studio `height` (0 launch/landing, 1 apex) is recovered
//!   from the hero's vertical speed and fed into the studio's exact airtime joint formulas.
//! - **attack** — our one-shot swing (`attack_t/ATTACK_DURATION`) is split into the studio's
//!   wind/strike/recovery phases (strike starts at `HIT_PHASE` so the blade meets the damage frame).
//! - **defend** — eased in/out by a smoothed `block_amt` instead of the studio's `time`-since-block.
//! On top sit our own layers: the Director's staged gestures (arms), the touchdown landing-squash,
//! and a slack keel-over on death. (First person doesn't use this rig at all — it is hidden and the
//! camera-parented `viewmodel` draws the hands.)

use std::f32::consts::{PI, TAU};

use bevy::prelude::*;

use super::combat::{CHARGE_GRACE, CHARGE_THRESHOLD};
use super::{Hero, HeroHealth, HeroPart, Joint};

fn e3(x: f32, y: f32, z: f32) -> Quat {
    Quat::from_euler(EulerRot::XYZ, x, y, z)
}
fn rx(a: f32) -> Quat {
    Quat::from_rotation_x(a)
}
fn lerp(a: f32, b: f32, t: f32) -> f32 {
    a + (b - a) * t
}
fn ease_out_cubic(t: f32) -> f32 {
    let c = t.clamp(0.0, 1.0);
    1.0 - (1.0 - c).powi(3)
}
fn smoothstep(t: f32) -> f32 {
    let c = t.clamp(0.0, 1.0);
    c * c * (3.0 - 2.0 * c)
}

/// Shield rest pose — turned EDGE-ON along the forearm when not blocking (previs look); the defend
/// clip swings it face-forward. (Studio idle was face-out; the user wants it sideways at rest.)
const SHIELD_REST_T: Vec3 = Vec3::new(-0.07, -0.08, 0.13);
fn shield_rest_r() -> Quat {
    e3(0.12, -1.5, 0.0)
}
/// Walk/run — held edge-on, a touch closer to the body.
const SHIELD_GAIT_T: Vec3 = Vec3::new(-0.1, -0.05, 0.15);
fn shield_gait_r() -> Quat {
    e3(0.12, -1.45, 0.0)
}
/// Sword rest X-rotation — a relaxed forward-down carry (~22° below horizontal). 1.2 ("tip
/// up-forward at the ready") held the blade near-horizontal out of a hanging fist, so the grip
/// buried itself in the vambrace and the blade visibly pierced the wrist; ~1.95 runs the grip
/// through the fist at a natural angle (pommel up behind the wrist, blade clear of the arm)
/// without reaching the studio's full 2.2 straight-down (which risks ground-clipping on the walk
/// backswing). Shared by the rest pose AND the attacks' wind-start / recovery-end so idle⇄attack
/// stays smooth.
pub(crate) const SWORD_REST_X: f32 = 1.95;
pub(crate) fn sword_rest_r() -> Quat {
    e3(SWORD_REST_X, 0.3, 0.0)
}

/// Three.js footman clips store joint eulers where **identity is the baked carry**. The mesh is
/// pre-rotated by the inverse of the game rest, so a three.js euler `e` becomes `e * rest` here
/// (and the shield's small rest translation is swung with it) and the blade/board move the way
/// they did in the source model.
fn posed_sword(ex: f32, ey: f32, ez: f32) -> Jp {
    Jp::r(m3(ex, ey, ez) * sword_rest_r())
}
fn posed_shield(ex: f32, ey: f32, ez: f32) -> Jp {
    let e = m3(ex, ey, ez);
    Jp { t: Some(e * SHIELD_REST_T), r: e * shield_rest_r() }
}
/// A three.js euler carried across the export's X mirror: X turns survive, Y and Z flip.
fn m3(ex: f32, ey: f32, ez: f32) -> Quat {
    e3(ex, -ey, -ez)
}

/// Landing squash recovery time (a crouch that decays over this many seconds after touchdown).
const LAND_RECOVER: f32 = 0.20;

/// One joint's target: an optional local translation override (`Some` only for joints the studio
/// moves — hips always, the shield, the hips-joints in victory) + a local rotation (always applied).
#[derive(Clone, Copy)]
pub(crate) struct Jp {
    pub(crate) t: Option<Vec3>,
    pub(crate) r: Quat,
}
impl Jp {
    fn r(r: Quat) -> Self {
        Jp { t: None, r }
    }
    fn lerp(self, o: Jp, s: f32) -> Jp {
        let t = match (self.t, o.t) {
            (Some(a), Some(b)) => Some(a.lerp(b, s)),
            (Some(a), None) => Some(a),
            (None, Some(b)) => Some(b),
            (None, None) => None,
        };
        Jp { t, r: self.r.slerp(o.r, s) }
    }
}

/// A full rig pose (the studio sets joints imperatively onto one of these each frame).
#[derive(Clone, Copy)]
pub(crate) struct Pose {
    hips: Jp,
    torso: Jp,
    head: Jp,
    sh_l: Jp,
    sh_r: Jp,
    el_l: Jp,
    el_r: Jp,
    hip_l: Jp,
    hip_r: Jp,
    knee_l: Jp,
    knee_r: Jp,
    foot_l: Jp,
    foot_r: Jp,
    shield: Jp,
    sword: Jp,
}

impl Pose {
    pub(crate) fn get(&self, j: Joint) -> Jp {
        match j {
            Joint::Hips => self.hips,
            Joint::Torso => self.torso,
            Joint::Head => self.head,
            Joint::ShoulderL => self.sh_l,
            Joint::ShoulderR => self.sh_r,
            Joint::ElbowL => self.el_l,
            Joint::ElbowR => self.el_r,
            Joint::HipL => self.hip_l,
            Joint::HipR => self.hip_r,
            Joint::KneeL => self.knee_l,
            Joint::KneeR => self.knee_r,
            Joint::FootL => self.foot_l,
            Joint::FootR => self.foot_r,
            Joint::Shield => self.shield,
            Joint::Sword => self.sword,
        }
    }
    fn lerp(&self, o: &Pose, s: f32) -> Pose {
        Pose {
            hips: self.hips.lerp(o.hips, s),
            torso: self.torso.lerp(o.torso, s),
            head: self.head.lerp(o.head, s),
            sh_l: self.sh_l.lerp(o.sh_l, s),
            sh_r: self.sh_r.lerp(o.sh_r, s),
            el_l: self.el_l.lerp(o.el_l, s),
            el_r: self.el_r.lerp(o.el_r, s),
            hip_l: self.hip_l.lerp(o.hip_l, s),
            hip_r: self.hip_r.lerp(o.hip_r, s),
            knee_l: self.knee_l.lerp(o.knee_l, s),
            knee_r: self.knee_r.lerp(o.knee_r, s),
            foot_l: self.foot_l.lerp(o.foot_l, s),
            foot_r: self.foot_r.lerp(o.foot_r, s),
            shield: self.shield.lerp(o.shield, s),
            sword: self.sword.lerp(o.sword, s),
        }
    }
}

/// The studio reset block (every clip starts here): hips at 1.05, all rotations zero, the shield at
/// its idle pose, the sword at its held rest.
fn rest() -> Pose {
    let id = Jp::r(Quat::IDENTITY);
    Pose {
        hips: Jp { t: Some(Vec3::new(0.0, 1.05, 0.0)), r: Quat::IDENTITY },
        torso: id,
        head: id,
        sh_l: id,
        sh_r: id,
        el_l: id,
        el_r: id,
        hip_l: id,
        hip_r: id,
        knee_l: id,
        knee_r: id,
        foot_l: id,
        foot_r: id,
        shield: Jp { t: Some(SHIELD_REST_T), r: shield_rest_r() },
        sword: Jp::r(sword_rest_r()),
    }
}

// ── Locomotion clips ───────────────────────────────────────────────────────────────────
fn idle_pose(t: f32) -> Pose {
    let breath = (t * 2.2).sin();
    let s11 = (t * 1.1).sin();
    let c11 = (t * 1.1).cos();
    // Slow weight shift (≈14s full cycle): a person at rest settles onto one hip, then the other.
    // The pelvis slides + rolls a touch, the torso counter-rolls to keep the head over the feet,
    // and the legs take up the slack — kills the "statue with a breathing chest" read.
    let w = (t * 0.45).sin();
    let mut p = rest();
    p.hips = Jp {
        t: Some(Vec3::new(w * 0.03, 1.05 + breath * 0.015 - w.abs() * 0.008, 0.0)),
        r: e3(0.0, s11 * 0.02, w * 0.035),
    };
    p.torso = Jp::r(e3(breath * 0.01, -s11 * 0.012, -w * 0.028));
    p.head = Jp::r(e3(-breath * 0.015, s11 * 0.04, s11 * 0.006 - w * 0.012));
    // The footman's bind pose IS the standing carry (arms already clear of the torso). Idle only
    // breathes — the old +0.1 / −0.4 elbow bend was compensating for a straight-down mesh.
    p.sh_l = Jp::r(e3(breath * 0.035, 0.0, c11 * 0.012 + w * 0.01));
    p.el_l = Jp::r(rx(-0.05 - breath * 0.02));
    p.sh_r = Jp::r(e3(breath * 0.035, 0.0, -c11 * 0.012 + w * 0.01));
    p.el_r = Jp::r(rx(-0.04 - breath * 0.015));
    // Stance leg straightens, free leg softens at the knee as the weight rides across.
    p.hip_l = Jp::r(e3(0.0, 0.0, w.max(0.0) * 0.05));
    p.hip_r = Jp::r(e3(0.0, 0.0, w.min(0.0) * 0.05));
    p.knee_l = Jp::r(rx((-w).max(0.0) * 0.08));
    p.knee_r = Jp::r(rx(w.max(0.0) * 0.08));
    p
}

fn walk_pose(c: f32) -> Pose {
    let l = c;
    let r = c + PI;
    let torso_x = 0.05 + (c * 2.0).sin() * 0.02;
    let mut p = rest();
    // A confident, decisive march — more arm swing and torso commitment than the studio's restrained
    // values, while the legs carry a solid stride. 2026-07 humanization: real lateral weight
    // transfer (the pelvis rides over the planted foot and ROLLS with it), a torso that
    // counter-rolls, and a head that stays level — the counter-motions are what read as "person",
    // not "piston".
    p.hips = Jp {
        t: Some(Vec3::new(c.sin() * 0.032, 1.04 + (c * 2.0).sin() * 0.028, 0.0)),
        r: e3(0.0, c.cos() * 0.08, c.sin() * 0.045),
    };
    p.torso = Jp::r(e3(torso_x, -c.cos() * 0.11, -c.sin() * 0.035));
    p.head = Jp::r(e3(-torso_x * 0.5, c.cos() * 0.035, -c.sin() * 0.012));
    p.hip_l = Jp::r(rx(l.sin() * 0.6));
    p.hip_r = Jp::r(rx(r.sin() * 0.6));
    p.knee_l = Jp::r(rx((-l.cos()).max(0.0) * 1.1));
    p.knee_r = Jp::r(rx((-r.cos()).max(0.0) * 1.1));
    // Foot roll with a toe-off flick at the back of the stride (the +0.25 kick as the leg trails).
    p.foot_l = Jp::r(rx(-l.sin() * 0.6 + (-l.sin()).max(0.0) * 0.25));
    p.foot_r = Jp::r(rx(-r.sin() * 0.6 + (-r.sin()).max(0.0) * 0.25));
    // The footman's arms are already in the carry. These are the three.js walk deltas off that
    // bind (a few degrees of counter-swing), not the old straight-arm knight bends — those lifted
    // the blade into a lance and flared the shield.
    p.sh_l = Jp::r(m3(r.sin() * 0.11, 0.0, 0.04));
    p.el_l = Jp::r(rx(-0.30 + r.sin().min(0.0) * 0.08));
    p.sh_r = Jp::r(m3(l.sin() * 0.16, 0.0, -0.04));
    p.el_r = Jp::r(rx(-0.22 + l.sin().min(0.0) * 0.11));
    p
}

fn run_pose(c: f32) -> Pose {
    let l = c;
    let r = c + PI;
    let absin = c.sin().abs();
    let mut p = rest();
    // A purposeful armored run — bigger, more committed stride than the studio's restrained jog
    // (but not the old frantic sprint): real lean, driving arms, knees that lift.
    p.hips = Jp {
        t: Some(Vec3::new(c.sin() * 0.02, 1.0 + absin * 0.06, 0.0)),
        r: e3(0.0, c.cos() * 0.1, c.sin() * 0.04),
    };
    p.torso = Jp::r(e3(0.18 + absin * 0.04, -c.cos() * 0.12, -c.sin() * 0.035));
    p.head = Jp::r(e3(-0.1 - absin * 0.04, c.cos() * 0.04, -c.sin() * 0.01));
    p.hip_l = Jp::r(e3(l.sin() * 0.8, 0.0, l.sin().max(0.0) * 0.02));
    p.hip_r = Jp::r(e3(r.sin() * 0.8, 0.0, -r.sin().max(0.0) * 0.02));
    p.knee_l = Jp::r(rx((-l.cos()).max(0.0) * 1.3 + 0.12));
    p.knee_r = Jp::r(rx((-r.cos()).max(0.0) * 1.3 + 0.12));
    p.foot_l = Jp::r(rx(-l.sin() * 0.8 * 0.5 + 0.14));
    p.foot_r = Jp::r(rx(-r.sin() * 0.8 * 0.5 + 0.14));
    // Three.js run: elbows tuck, the blade rides point-up over the shoulder, the shield stays
    // edge-on against the forearm. Eulers are identity-at-carry, composed onto the game rest.
    p.sh_l = Jp::r(m3(r.sin() * 0.15, 0.0, 0.14));
    p.el_l = Jp::r(rx(-1.15 + r.sin().min(0.0) * 0.2));
    p.sh_r = Jp::r(m3(l.sin() * 0.12, 0.0, -0.14));
    p.el_r = Jp::r(rx(-1.25 + l.sin().min(0.0) * 0.15));
    p.sword = posed_sword(-2.046, -0.52, 0.119);
    p.shield = posed_shield(0.924, 0.415, -0.121);
    p
}

/// idle → (walk → run by `run`) → blended toward idle by `m` (moving_amt).
pub(crate) fn loco_pose(t: f32, wp: f32, m: f32, run: f32) -> Pose {
    let gait = walk_pose(wp).lerp(&run_pose(wp), run);
    idle_pose(t).lerp(&gait, m)
}

// ── Hero (footman) gait: foot-locked, speed-driven ─────────────────────────────────────────
// The old footman gait swept the planted boot only ±0.18 m while the body travelled ~2 m per
// step at the hero's base speed — the feet covered under a fifth of the ground the body did, which
// is the "moonwalk". Here the gait is cut FROM the ground speed: the stance foot sweeps back
// exactly as fast as the body moves forward (so it stays nailed to the ground), and the cadence is
// derived from that same contract ([`gait_phase_rate`]), so any speed — haste, swamp, roads, a
// heavy-strike creep — stays foot-locked with no retuning.
//
// Speed also picks the gait STYLE: a walk (long stance, double support, a vaulting hip) at low
// speed, a jog (short stance, a flight phase, knees that drive) at the hero's base speed, and a
// sprint (longer reach, high heel kick, deep lean, pumping arms) with Shift. NB the base speed
// (`movement::SPEED`, ≈4.5 model-m/s) is jogging pace for a ~1.9 m figure — a foot-locked walk there
// would need ~5 steps/s — so the base gait IS a jog; the walk shows at the slower speeds.
//
// Leg cycle `u` (0..1, left = walk_phase/2π, right half a cycle later): heel strike at `u = 0`
// (so the footstep SFX/dust, keyed on walk_phase crossing kπ, land on contacts), stance until
// `duty`, then the swing.

/// Shape of the gait at one ground speed (model metres / s).
#[derive(Clone, Copy)]
struct Gait {
    /// Stance travel of the planted ankle, strike → toe-off, relative to the hips (m).
    sweep: f32,
    /// Share of `sweep` ahead of the hip at heel strike (runners land closer under the body).
    front: f32,
    /// Stance share of one leg cycle (walk > 0.5 = double support; run < 0.5 = flight).
    duty: f32,
    /// Plantar-flex at toe-off (rad, + = toe down) and the boot pitch at contact (− = heel first).
    toe_off: f32,
    strike: f32,
    /// 0 walk → 1 jog, and 0 jog → 1 sprint (style weights for the upper body / bob).
    run: f32,
    sprint: f32,
}

fn gait_at(v: f32) -> Gait {
    let run = smoothstep((v - 2.0) / 1.7);
    let sprint = smoothstep((v - 4.4) / 1.9);
    // Short creeping steps when barely moving, a full stride by a brisk walk.
    let walk_sweep = lerp(0.40, 0.9, smoothstep(v / 1.5));
    let k = |w: f32, j: f32, s: f32| lerp(lerp(w, j, run), s, sprint);
    Gait {
        // At running speeds the stance shape comes from the gait-lab run model ([`run_gait`]):
        // its natural contact sweep and a duty factor shrinking from a jog's ~1/3 to a sprint's ~0.23.
        sweep: lerp(walk_sweep, run_sweep(sprint), run),
        front: k(0.44, 0.40, 0.38),
        duty: lerp(0.6, lerp(0.32, 0.23, sprint), run),
        toe_off: k(0.38, 0.48, 0.6),
        strike: k(-0.22, -0.08, 0.0),
        run,
        sprint,
    }
}

/// World units per footman model metre (rig scale × `HERO_SCALE`).
fn hero_model_scale() -> f32 {
    super::footman::leg_rig().scale * super::HERO_SCALE
}

/// `walk_phase` advance rate (rad/s) at a world ground speed — the foot-lock contract: a stance of
/// `duty` of the cycle must carry the planted ankle back through `sweep` at exactly the body's speed.
pub(crate) fn gait_phase_rate(world_speed: f32) -> f32 {
    let v = world_speed.max(0.0) / hero_model_scale();
    if v < 1e-4 {
        return 0.0;
    }
    let g = gait_at(v);
    std::f32::consts::TAU * v * g.duty / g.sweep
}

/// Where one leg's boot is at leg-cycle `u`: (flat-ankle z, clearance of the lowest boot point,
/// pitch, stance support weight 0..1). Only the pitch is meaningful in the swing.
fn leg_track(u: f32, g: &Gait) -> (f32, f32, f32, f32) {
    let z_strike = g.front * g.sweep;
    if u < g.duty {
        // Planted: the ankle slides back linearly = locked to the ground. Heel rocker settles the
        // boot flat after the strike, toe rocker peels the heel up into the push-off.
        let s = u / g.duty;
        let pitch = lerp(g.strike, 0.0, smoothstep(s / 0.18)) + g.toe_off * smoothstep((s - 0.68) / 0.32);
        (z_strike - s * g.sweep, 0.0, pitch, (PI * s).sin())
    } else {
        // Swing legs are posed by joint angle (see `swing_leg`), not by an ankle path; only the
        // boot pitch is used from here: pointed through the fold-up, levelled for the strike.
        let s = (u - g.duty) / (1.0 - g.duty);
        let pitch = lerp(g.toe_off, g.strike, smoothstep((s - 0.3) / 0.55));
        (0.0, 0.0, pitch, 0.0)
    }
}

/// A swing leg's (thigh, knee-flex) forward angles at swing progress `s`, keyed on running /
/// walking gait-lab joint curves (Novacheck '98: jog hip flexion peaks ≈45° late in the swing and
/// the knee folds to ≈90–95° just after toe-off; a sprint ≈65–70° / ≈120°; a walk ≈28° / ≈55°),
/// with the ends pinned to the stance IK at toe-off and strike so the hand-off is seamless.
/// (An ankle-path IK here let the thigh fly up past horizontal whenever the boot rose under the
/// hip — 136° of hip flexion in the sprint.)
fn swing_leg(s: f32, g: &Gait, off: (f32, f32), strike: (f32, f32)) -> (f32, f32) {
    let k = |w: f32, j: f32, sp: f32| lerp(lerp(w, j, g.run), sp, g.sprint).to_radians();
    // Run rework: the thigh swings through quickly (already ~vertical a quarter into the swing),
    // so the knee's deepest fold happens UNDER the hip with the knee driving forward — the
    // reverse order (fold while the thigh still trails) is what read as a butt-kick skip.
    let thigh = [off.0, k(8.0, 4.0, 10.0), k(22.0, 34.0, 50.0), k(28.0, 48.0, 66.0), strike.0];
    let knee = [off.1, k(58.0, 80.0, 92.0), k(48.0, 86.0, 98.0), k(16.0, 40.0, 44.0), strike.1];
    let ends = |v: &[f32; 5]| ((v[1] - v[0]) / 0.25, (v[4] - v[3]) / 0.25);
    let (ts, te) = ends(&thigh);
    let (ks, ke) = ends(&knee);
    (keyed(&thigh, s, ts, te), keyed(&knee, s, ks, ke))
}

/// Smooth curve through five evenly spaced keys at s = 0, ¼, ½, ¾, 1 (Catmull-Rom tangents
/// inside, the given end slopes in per-s units).
fn keyed(k: &[f32; 5], s: f32, t_start: f32, t_end: f32) -> f32 {
    const H: f32 = 0.25;
    let s = s.clamp(0.0, 1.0);
    let i = ((s / H) as usize).min(3);
    let tan = |j: usize| match j {
        0 => t_start,
        4 => t_end,
        _ => (k[j + 1] - k[j - 1]) / (2.0 * H),
    };
    let t = (s - i as f32 * H) / H;
    let (t2, t3) = (t * t, t * t * t);
    (2.0 * t3 - 3.0 * t2 + 1.0) * k[i]
        + (t3 - 2.0 * t2 + t) * H * tan(i)
        + (-2.0 * t3 + 3.0 * t2) * k[i + 1]
        + (t3 - t2) * H * tan(i + 1)
}

/// Ankle (z, height) for a boot whose flat-foot ankle is at `z`, lowest point `clear` above the
/// ground, pitched by `pitch` — rolling about the toe tip (toe down) or the heel (toe up), so a
/// rocker keeps its contact edge planted instead of sinking/skating.
fn boot_ankle(z: f32, clear: f32, pitch: f32, rig: &super::footman::LegRig) -> (f32, f32) {
    let (h, (s, c)) = (rig.ankle_height, pitch.sin_cos());
    if pitch >= 0.0 {
        (z + rig.toe + h * s - rig.toe * c, clear + h * c + rig.toe * s)
    } else {
        (z - rig.heel + h * s + rig.heel * c, clear + h * c - rig.heel * s)
    }
}

/// Two-bone sagittal IK for one leg. `hip` = hip joint (z, height), `ankle` = target. Returns the
/// (hip, knee, foot) X rotations that land the ankle there with the boot at `pitch` (relative to
/// the pelvis-independent leg frame).
fn leg_ik(hip: Vec2, ankle: Vec2, pitch: f32, rig: &super::footman::LegRig) -> (f32, f32, f32) {
    let (thigh, shin) = leg_dirs(hip, ankle, rig);
    leg_rot(thigh, shin, pitch, rig)
}

/// Forward angle from straight down toward +Z (the sagittal bone direction the gait works in).
fn fwd_angle(v: Vec2) -> f32 {
    v.x.atan2(-v.y)
}

/// The (thigh, shin) forward angles that land the ankle on `ankle` from the hip joint `hip`.
fn leg_dirs(hip: Vec2, ankle: Vec2, rig: &super::footman::LegRig) -> (f32, f32) {
    let upper = rig.knee.y.hypot(rig.knee.z);
    let lower = rig.foot.y.hypot(rig.foot.z);
    let d = ankle - hip;
    let dist = d.length().clamp((upper - lower).abs() + 1e-3, upper + lower - 1e-3);
    let open = ((upper * upper + dist * dist - lower * lower) / (2.0 * upper * dist)).clamp(-1.0, 1.0).acos();
    let thigh_dir = fwd_angle(d) + open; // knee ahead of the hip→ankle line
    let knee_pt = hip + upper * Vec2::new(thigh_dir.sin(), -thigh_dir.cos());
    (thigh_dir, fwd_angle(hip + d.normalize_or_zero() * dist - knee_pt))
}

/// Bone forward angles → the hip/knee/foot X rotations (`rx(θ)` turns a bone by −θ in that
/// angle), with the boot at world `pitch`.
fn leg_rot(thigh_dir: f32, shin_dir: f32, pitch: f32, rig: &super::footman::LegRig) -> (f32, f32, f32) {
    let thigh_rest = fwd_angle(Vec2::new(rig.knee.z, rig.knee.y));
    let shin_rest = fwd_angle(Vec2::new(rig.foot.z, rig.foot.y));
    let th = thigh_rest - thigh_dir;
    let kn = shin_rest - th - shin_dir;
    (th, kn, pitch - th - kn)
}

/// The hero's foot-locked locomotion at world ground speed `speed`, cycle phase `c`: the IK walk
/// ([`walk_gait`]) below a jog, the gait-lab run ([`run_gait`]) above it, cross-faded between.
/// `armed` (0..1): the sword is in hand (1) or slung on the back (0); `shield_back` (0..1): the
/// shield is on the arm (0) or slung on the back for a sprint (1), when both arms run free.
fn footman_gait(c: f32, speed: f32, armed: f32, shield_back: f32) -> Pose {
    let g = gait_at(speed.max(0.0) / hero_model_scale());
    if g.run <= 1e-3 {
        walk_gait(c, &g, armed)
    } else if g.run >= 1.0 - 1e-3 {
        run_gait(c, &g, armed, shield_back)
    } else {
        walk_gait(c, &g, armed).lerp(&run_gait(c, &g, armed, shield_back), g.run)
    }
}

// ── Run: gait-lab joint curves, foot-locked by a stance time-warp ─────────────────────────
// Redone from scratch (user, 2026-10). Instead of solving the legs from a foot path and keying
// the swing, every joint follows measured running curves (global thigh angle, knee flexion,
// ankle plantar-flexion over the gait cycle), so the stride has the shape of a real run: a soft
// landing just ahead of the hips, the knee loading through mid-stance, a full push-off, the heel
// folding up UNDER the body as the thigh drives forward, and the leg reaching out again before
// contact. Ground contact stays exact without bending the curves: during stance they play on a
// WARPED clock chosen so the planted boot's contact edge slides back at exactly the body's speed,
// and the hips ride at whatever height that planted leg puts them, so the bob (lowest at
// mid-stance, highest in flight) falls out of the leg instead of a sine. In flight the hips arc
// from toe-off to the next landing.

/// One style's curves over a leg cycle (fraction from initial contact; toe-off at `to`): global
/// thigh angle (deg forward of vertical), knee flexion (deg), ankle plantar-flexion (deg, minus =
/// dorsiflexion; only the swing uses it, the stance pitch is the boot rolling on the ground).
struct RunCurves {
    to: f32,
    p: &'static [f32],
    thigh: &'static [f32],
    knee: &'static [f32],
    ankle: &'static [f32],
}

/// A jog (shapes from gait-lab means around 3-3.5 m/s, Novacheck 1998): landing with the thigh
/// ~28 deg ahead and the knee soft, push-off with the thigh ~18 behind, ~80 deg of knee fold in
/// the swing, thigh drive to ~38. Fitted to this rig: its shin is half again its thigh and its
/// sabaton long and rigid, so the stance knee loads to ~32 deg (not the lab's ~40, which sank the
/// hips into a bouncing crouch) and the boot peels to only ~30 deg at toe-off (a steeper roll on
/// that lever vaulted the hips up onto tiptoe).
const JOG: RunCurves = RunCurves {
    to: 0.38,
    p: &[0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.38, 0.45, 0.52, 0.60, 0.68, 0.76, 0.84, 0.92],
    thigh: &[28.0, 24.0, 19.0, 13.0, 7.0, 0.0, -8.0, -18.0, -13.0, -2.0, 12.0, 26.0, 35.0, 38.0, 34.0],
    knee: &[21.0, 28.0, 32.0, 32.0, 29.0, 25.0, 21.0, 20.0, 34.0, 56.0, 74.0, 80.0, 70.0, 52.0, 30.0],
    ankle: &[-4.0, -10.0, -16.0, -20.0, -21.0, -18.0, -12.0, -8.0, 6.0, 6.0, 0.0, -3.0, -5.0, -5.0, -4.0],
};

/// An armoured soldier's sprint: shorter contact, more thigh drive (~60 deg) and reach, but only
/// ~85 deg of heel recovery: with this rig's long shins a lab fold (100-125) swings the shin out
/// horizontal behind, the heels-kicking-back look the user rejected. Timed like real front-side
/// mechanics: at the other foot's landing the folded leg is passing under the hips (thigh ~18 deg,
/// heel tucked in and angled down), the knee then drives up to
/// its peak as the other foot toes off, and opens only for the reach and paw-back into contact,
/// so in the flight the front leg is carried high instead of skimming the ground in a split.
const SPRINT: RunCurves = RunCurves {
    to: 0.27,
    p: &[0.0, 0.05, 0.10, 0.15, 0.20, 0.27, 0.35, 0.43, 0.51, 0.59, 0.67, 0.75, 0.83, 0.91],
    thigh: &[32.0, 26.0, 18.0, 9.0, -3.0, -20.0, -12.0, 4.0, 18.0, 36.0, 52.0, 60.0, 55.0, 42.0],
    knee: &[22.0, 28.0, 30.0, 27.0, 21.0, 18.0, 42.0, 68.0, 84.0, 86.0, 78.0, 62.0, 44.0, 30.0],
    ankle: &[2.0, -8.0, -15.0, -18.0, -14.0, -3.0, 10.0, 6.0, 0.0, -3.0, -4.0, -2.0, 0.0, 1.0],
};

/// Periodic Catmull-Rom through keys `(p[i], v[i])` on a unit cycle (non-uniform spacing).
fn cycle_curve(p: &[f32], v: &[f32], x: f32) -> f32 {
    let n = p.len() as isize;
    let x = x.rem_euclid(1.0);
    let i = p.iter().rposition(|&k| k <= x).unwrap_or(0) as isize;
    // Key `j` of the endless cycle: wraps round, its position shifted by whole cycles.
    let key = |j: isize| {
        let w = j.rem_euclid(n) as usize;
        (p[w] + j.div_euclid(n) as f32, v[w])
    };
    let (pa, va) = key(i - 1);
    let (p0, v0) = key(i);
    let (p1, v1) = key(i + 1);
    let (pb, vb) = key(i + 2);
    let h = p1 - p0;
    let (m0, m1) = ((v1 - va) / (p1 - pa), (vb - v0) / (pb - p0));
    let t = ((x - p0) / h).clamp(0.0, 1.0);
    let (t2, t3) = (t * t, t * t * t);
    (2.0 * t3 - 3.0 * t2 + 1.0) * v0 + (t3 - 2.0 * t2 + t) * h * m0 + (-2.0 * t3 + 3.0 * t2) * v1 + (t3 - t2) * h * m1
}

/// (thigh, knee flex, ankle) in radians, jog to sprint by `sprint`, at stance progress `s`
/// (planted: 0 = contact, 1 = toe-off) or swing progress `s` (0 = toe-off, 1 = the next contact).
fn run_angles(sprint: f32, stance: bool, s: f32) -> (f32, f32, f32) {
    let at = |c: &RunCurves| {
        let x = if stance { c.to * s } else { c.to + (1.0 - c.to) * s };
        (cycle_curve(c.p, c.thigh, x), cycle_curve(c.p, c.knee, x), cycle_curve(c.p, c.ankle, x))
    };
    let (a, b) = (at(&JOG), at(&SPRINT));
    (lerp(a.0, b.0, sprint).to_radians(), lerp(a.1, b.1, sprint).to_radians(), lerp(a.2, b.2, sprint).to_radians())
}

/// A planted run leg at (warped) stance progress `s`: (thigh, knee, boot pitch, flat-ankle z
/// relative to the hip joint, hip-joint height above the ground). The boot rolls from the landing
/// pitch (heel or mid-foot) to flat and up onto the toe for the push-off; the end pitches equal
/// the swing's (shin angle + ankle), so contact and lift-off hand over seamlessly.
fn run_stance(sprint: f32, s: f32, rig: &super::footman::LegRig) -> (f32, f32, f32, f32, f32) {
    let (t, k, _) = run_angles(sprint, true, s);
    let end_pitch = |e: f32| {
        let (t, k, a) = run_angles(sprint, true, e);
        -(t - k) + a
    };
    let pitch = lerp(end_pitch(0.0), 0.0, smoothstep(s / 0.2)) + end_pitch(1.0) * smoothstep((s - 0.5) / 0.5);
    let (upper, lower) = (rig.knee.y.hypot(rig.knee.z), rig.foot.y.hypot(rig.foot.z));
    let shin = t - k;
    let ankle = Vec2::new(upper * t.sin() + lower * shin.sin(), -upper * t.cos() - lower * shin.cos());
    let (roll_z, ground_y) = boot_ankle(0.0, 0.0, pitch, rig);
    (t, k, pitch, ankle.x - roll_z, ground_y - ankle.y)
}

/// The run's natural contact sweep (flat-ankle travel strike to toe-off, model m).
fn run_sweep(sprint: f32) -> f32 {
    let rig = super::footman::leg_rig();
    run_stance(sprint, 0.0, &rig).3 - run_stance(sprint, 1.0, &rig).3
}

/// The warped stance progress whose pose puts the planted boot at linear progress `s` of its
/// sweep, less `dz` (the hip joint's own fore-aft shift from the pelvis yaw). The flat-ankle z
/// falls monotonically through the stance, so a bisection is exact.
fn run_warp(sprint: f32, s: f32, dz: f32, rig: &super::footman::LegRig) -> f32 {
    let z0 = run_stance(sprint, 0.0, rig).3;
    let z1 = run_stance(sprint, 1.0, rig).3;
    let want = lerp(z0, z1, s.clamp(0.0, 1.0)) - dz;
    let (mut a, mut b) = (0.0_f32, 1.0_f32);
    for _ in 0..18 {
        let m = 0.5 * (a + b);
        if run_stance(sprint, m, rig).3 > want {
            a = m;
        } else {
            b = m;
        }
    }
    0.5 * (a + b)
}

/// The hip-joint height a stance holds at warped progress `s`: the planted leg's own height
/// through the landing and the loading, then a steady, accelerating rise into toe-off. Left to
/// itself the leg would hump the hips up mid-push (the boot peeling onto its toe) and sink them
/// again as the thigh trails out behind, so the body would fall through every flight; under the
/// rise the knee simply gives a little more ([`run_gait`] solves those frames with IK). Equal to
/// the leg's own height at contact and toe-off, so the swing curves pick up seamlessly.
fn run_hold_height(sprint: f32, s: f32, rig: &super::footman::LegRig) -> f32 {
    let own = |x: f32| run_stance(sprint, x, rig).4;
    let (mut s_min, mut h_min) = (0.0_f32, f32::MAX);
    for i in 0..=16 {
        let x = i as f32 / 16.0;
        let h = own(x);
        if h < h_min {
            (s_min, h_min) = (x, h);
        }
    }
    let h = own(s);
    if s <= s_min {
        return h;
    }
    let t = (s - s_min) / (1.0 - s_min).max(1e-3);
    h.min(lerp(h_min, own(1.0), t * t))
}

/// Hip-joint height at step phase `q` (0..0.5: one stance of `duty`, then the flight to the other
/// foot's contact). Planted: what the leg's pose dictates. Flight: a Hermite arc from toe-off to
/// the next landing matching both ends' vertical speed (up off the toe, over, down onto the heel).
fn run_hip_height(sprint: f32, duty: f32, q: f32, rig: &super::footman::LegRig) -> f32 {
    let planted = |q: f32| run_hold_height(sprint, run_warp(sprint, q / duty, 0.0, rig), rig);
    if q < duty {
        return planted(q);
    }
    let e = 0.01 * duty;
    let (y0, y1) = (planted(duty), planted(0.0));
    // Ballistic: the hips leave the toe rising and land falling (clamped, so a curve tweak that
    // flattened either end can never make the flight sag below its take-off and landing).
    let (m0, m1) = (((y0 - planted(duty - e)) / e).max(0.0), ((planted(e) - y1) / e).min(0.0));
    let span = 0.5 - duty;
    let t = ((q - duty) / span).clamp(0.0, 1.0);
    let (t2, t3) = (t * t, t * t * t);
    (2.0 * t3 - 3.0 * t2 + 1.0) * y0 + (t3 - 2.0 * t2 + t) * span * m0 + (-2.0 * t3 + 3.0 * t2) * y1 + (t3 - t2) * span * m1
}

fn run_gait(c: f32, g: &Gait, armed: f32, shield_back: f32) -> Pose {
    let rig = super::footman::leg_rig();
    let (sprint, duty) = (g.sprint, g.duty);
    let u_l = (c / TAU).rem_euclid(1.0);
    let u_r = (u_l + 0.5).fract();
    // Stance weight per leg (0 at contact / toe-off, 1 mid-stance) for the pelvis drop and sway.
    let load = |u: f32| if u < duty { (PI * u / duty).sin() } else { 0.0 };
    let (kl, kr) = (load(u_l), load(u_r));
    let fwd_l = (TAU * u_l).cos(); // +1 at the left contact (left leg out front)

    // ── Pelvis: tipped forward a touch, yawing with the forward leg, dropping on the swing side ──
    let tilt = lerp(0.07, 0.1, sprint);
    let pel_yaw = lerp(0.09, 0.12, sprint) * (TAU * (u_l - 0.04)).cos();
    let pel_drop = 0.05 * (kr - kl); // minus = right (+X) hip low: left leg loaded
    let pelvis = e3(tilt, pel_yaw, pel_drop);
    let hip_l = pelvis * rig.hip;
    let hip_r = pelvis * Vec3::new(-rig.hip.x, rig.hip.y, rig.hip.z);
    let hip_nominal = e3(tilt, 0.0, 0.0) * rig.hip;
    // The hips ride at the height the planted leg dictates (the hip joint sits at its pelvis
    // offset below the hips joint); in flight they follow the arc between the two stances.
    let q = u_l.rem_euclid(0.5);
    let loaded = if q < duty { if u_l < 0.5 { hip_l } else { hip_r } } else { hip_nominal };
    let hips_y = run_hip_height(sprint, duty, q, &rig) - loaded.y;
    let sway = 0.01 * (kr - kl);
    let hips_t = Vec3::new(sway, hips_y, 0.0);
    let mut p = rest();
    p.hips = Jp { t: Some(hips_t + Vec3::Y * (1.05 - super::model::HIP_REST_Y)), r: pelvis };

    // ── Legs ──
    let leg = |off: Vec3, u: f32| {
        let (th, kn, ft) = if u < duty {
            let s = run_warp(sprint, u / duty, off.z - hip_nominal.z, &rig);
            let (t, k, pitch, _, own) = run_stance(sprint, s, &rig);
            let hold = run_hold_height(sprint, s, &rig);
            if hold < own - 1e-4 {
                // Hips held under the leg's own height: same boot placement, the knee takes it up.
                let (upper, lower) = (rig.knee.y.hypot(rig.knee.z), rig.foot.y.hypot(rig.foot.z));
                let shin = t - k;
                let ankle = Vec2::new(upper * t.sin() + lower * shin.sin(), -upper * t.cos() - lower * shin.cos());
                leg_ik(Vec2::ZERO, ankle + Vec2::Y * (own - hold), pitch, &rig)
            } else {
                leg_rot(t, t - k, pitch, &rig)
            }
        } else {
            let (t, k, a) = run_angles(sprint, false, (u - duty) / (1.0 - duty));
            leg_rot(t, t - k, -(t - k) + a, &rig)
        };
        // Keep the boots on their track under the swaying pelvis (as in `walk_gait`).
        let leg_len = (hips_t.y + off.y).max(0.3);
        let abduct = Quat::from_rotation_z((-(hips_t.x) / leg_len).clamp(-0.5, 0.5).asin());
        (Jp::r(pelvis.inverse() * abduct * rx(th)), Jp::r(rx(kn)), Jp::r(rx(ft)))
    };
    (p.hip_l, p.knee_l, p.foot_l) = leg(hip_l, u_l);
    (p.hip_r, p.knee_r, p.foot_r) = leg(hip_r, u_r);

    // ── Trunk: a modest forward lean (7-10 deg), the shoulders counter-rotating the pelvis, the
    // head steady and level on the road ──
    let lean = lerp(0.12, 0.17, sprint) + 0.025 * (kl + kr);
    let torso_yaw = -1.6 * pel_yaw;
    p.torso = Jp::r(Quat::from_rotation_y(torso_yaw) * e3(lean - tilt, 0.0, -0.7 * pel_drop));
    p.head = Jp::r(e3(-lean * 0.8, -0.8 * (pel_yaw + torso_yaw), -0.3 * pel_drop));

    // ── Arms: opposite arm to the forward leg, swung from a loose shoulder, more behind than in
    // front (a runner drives the arm back); elbows fairly open (the user's reference: ~60-75 deg
    // of bend, closing a little as the hand comes forward, opening behind); forearms angling in
    // toward the midline in front. The swing trails the legs a touch, the elbow the shoulder. ──
    let sh_amp = lerp(0.56, 0.8, sprint);
    let sh_mid = -0.08;
    // On top of the bind's own ~25 deg carry bend: ~60 deg in all, ~75 in front, ~45 behind.
    let el_mid = lerp(0.55, 0.62, sprint);
    let el_amp = lerp(0.22, 0.28, sprint);
    let arm = |u_leg: f32, side: f32, scale: f32, el_fix: f32| {
        let f = (TAU * (u_leg - 0.03)).cos(); // +1 = this arm fully forward
        let fl = (TAU * (u_leg - 0.08)).cos();
        let flex = sh_mid + scale * sh_amp * f; // + = upper arm forward of the trunk
        let cross = 0.22 * f.max(0.0) * scale;
        let sh = e3(-flex, -0.22 * side, side * (0.07 - cross));
        let el = rx(-lerp(el_mid + el_amp * fl, el_mid, el_fix));
        (sh, el)
    };
    // Sword arm: free (the blade is slung), or with the sword in hand a shortened pump.
    let (sr, er) = arm(u_l, 1.0, lerp(1.0, 0.7, armed), 0.0);
    // Shield arm: a board on the forearm is carried, not pumped (small swing, elbow held); with the
    // shield slung on the back for the sprint, the arm runs free like the other.
    let (sl_c, el_c) = arm(u_r, -1.0, 0.4, 0.75);
    let (sl_f, el_f) = arm(u_r, -1.0, 1.0, 0.0);
    let (sl, el) = (sl_c.slerp(sl_f, shield_back), el_c.slerp(el_f, shield_back));
    let girdle = |rest: Vec3, f: f32| rest + Vec3::new(0.0, 0.012 * f.max(0.0), 0.03 * f);
    p.sh_r = Jp { t: Some(girdle(rig.shoulder_r, fwd_l)), r: sr };
    p.el_r = Jp::r(er);
    p.sh_l = Jp { t: Some(girdle(rig.shoulder, -fwd_l)), r: sl };
    p.el_l = Jp::r(el);
    // A blade in hand rides shouldered (wrist against the pump) rather than fanning behind.
    let wrist = armed * 0.6 * sh_amp * (TAU * (u_l - 0.03)).cos();
    p.sword = Jp::r(rx(wrist) * sword_rest_r().slerp(posed_sword(-2.046, -0.52, 0.119).r, armed));
    // The board stays upright, edge-on along the body: cancel the elbow's pitch on it.
    let (el_x, _, _) = el.to_euler(EulerRot::XYZ);
    let undo = rx(-el_x * 0.9);
    p.shield = Jp { t: Some(undo * SHIELD_GAIT_T), r: undo * shield_gait_r() };
    p
}

/// The IK walk (and its jog end, cross-faded into [`run_gait`]): `c` cycle phase, `g` the gait.
/// `armed` (0..1): the sword is in hand (1) or slung on the back (0), an empty sword hand pumps
/// as freely as the shield arm.
fn walk_gait(c: f32, g: &Gait, armed: f32) -> Pose {
    let rig = super::footman::leg_rig();
    let g = *g;
    let (run, sprint) = (g.run, g.sprint);
    let u_l = (c / std::f32::consts::TAU).rem_euclid(1.0);
    let u_r = (u_l + 0.5).fract();
    let (zl, cl, pl, kl) = leg_track(u_l, &g);
    let (zr, cr, pr, kr) = leg_track(u_r, &g);
    let al = boot_ankle(zl, cl, pl, &rig);
    let ar = boot_ankle(zr, cr, pr, &rig);
    // The stance targets a swing leg hands off from (toe-off) and to (strike).
    let at = |u: f32| {
        let (z, c, p, _) = leg_track(u, &g);
        boot_ankle(z, c, p, &rig)
    };
    let (a_off, a_strike) = (at(g.duty - 1e-4), at(0.0));
    let swing_s = |u: f32| (u >= g.duty).then(|| (u - g.duty) / (1.0 - g.duty));
    // +1 when the LEFT boot is out front (its strike), −1 at the right strike.
    let swing = (c).cos();

    // ── Pelvis ──
    // Vertical bob, once per step — the main carrier of weight. A walk vaults UP over the planted
    // leg (highest at single-leg mid-stance, lowest in double support); a run sinks INTO the
    // stance (lowest mid-stance, loaded knee) and peaks in the flight phase. Amplitudes follow
    // human centre-of-mass excursion scaled to this ~1.9 m body: ~4-5 cm peak-to-peak walking,
    // ~8-9 cm jogging, a little flatter in a full sprint.
    let step = (2.0 * u_l).fract();
    let crest = (TAU * (step - (g.duty + 0.5 * run))).cos(); // +1 at the top of the bob
    let bob = lerp(0.022, lerp(0.045, 0.038, sprint), run) * crest;
    // Run tall (2026-10 rework): only a small sink — the old 3.5-5 cm drop read as running in a crouch.
    let base = super::model::HIP_REST_Y - lerp(0.012, lerp(0.016, 0.024, sprint), run);
    let sway = lerp(0.022, 0.012, run) * (kr - kl); // over the stance foot (left leg is −X)
    // Hips work in all three planes: they yaw with the stride (the forward leg's hip swings
    // forward), DROP on the swing-leg side while the other leg carries the weight, and tip
    // forward a touch as the body loads into each stance.
    let pel_yaw = lerp(0.10, lerp(0.12, 0.14, sprint), run) * swing; // + swings the left hip forward
    let pel_drop = lerp(0.045, 0.075, run) * (kr - kl); // − = right (+X) hip low: left leg loaded
    let pelvis = e3(run * (0.06 - 0.03 * crest), pel_yaw, pel_drop);
    // Never ask a planted leg for more reach than it has: the hips sink at the far ends of a
    // stride instead of the boot peeling off the ground (soft-min keeps it smooth).
    let reach = 0.985 * (rig.knee.y.hypot(rig.knee.z) + rig.foot.y.hypot(rig.foot.z));
    let hip_l = pelvis * rig.hip;
    let hip_r = pelvis * Vec3::new(-rig.hip.x, rig.hip.y, rig.hip.z);
    let cap = |a: (f32, f32), off: Vec3| {
        let dz = a.0 - off.z;
        a.1 + (reach * reach - dz * dz).max(0.0).sqrt() - off.y
    };
    let smin = |a: f32, b: f32| {
        let k = 0.03;
        let h = (0.5 + 0.5 * (b - a) / k).clamp(0.0, 1.0);
        lerp(b, a, h) - k * h * (1.0 - h)
    };
    // Planted legs cap the hips directly; a swing leg only through the stance it is leaving /
    // about to land in, phased in so the hips glide rather than jump at contact.
    let leg_cap = |u: f32, a: (f32, f32), off: Vec3| match swing_s(u) {
        None => cap(a, off),
        Some(s) => (cap(a_off, off) + smoothstep(s / 0.3)).min(cap(a_strike, off) + 1.0 - smoothstep((s - 0.5) / 0.5)),
    };
    let hips_y = smin(smin(base + bob, leg_cap(u_l, al, hip_l)), leg_cap(u_r, ar, hip_r));
    let hips_t = Vec3::new(sway, hips_y, 0.0);

    let mut p = rest();
    // The writer re-adds HIP_REST_Y − 1.05 (legacy 1.05-hip clips); store in that convention.
    p.hips = Jp { t: Some(hips_t + Vec3::Y * (1.05 - super::model::HIP_REST_Y)), r: pelvis };
    let leg = |off: Vec3, u: f32, a: (f32, f32), pitch: f32| {
        let hip = Vec2::new(hips_t.z + off.z, hips_t.y + off.y);
        let (th, kn, ft) = match swing_s(u) {
            None => leg_ik(hip, Vec2::new(a.0, a.1), pitch, &rig),
            Some(s) => {
                let dirs = |t: (f32, f32)| {
                    let (thigh, shin) = leg_dirs(hip, Vec2::new(t.0, t.1), &rig);
                    (thigh, thigh - shin)
                };
                let (thigh, flex) = swing_leg(s, &g, dirs(a_off), dirs(a_strike));
                leg_rot(thigh, thigh - flex, pitch, &rig)
            }
        };
        // Legs live in the pelvis frame: undo the pelvis turn so the leg plane stays on the travel
        // line and a planted boot never twists or skates with the hip swing. The sagittal IK
        // ignores X, so the pelvis's side-to-side sway would carry the boots with it (a planted
        // foot shuffling ±2 cm sideways every step reads as wobbly on the legs): abduct the leg
        // against the sway so the feet keep their track and only the pelvis travels.
        let leg_len = (hip.y - a.1).max(0.3);
        let abduct = Quat::from_rotation_z((-(hips_t.x) / leg_len).clamp(-0.5, 0.5).asin());
        (Jp::r(pelvis.inverse() * abduct * rx(th)), Jp::r(rx(kn)), Jp::r(rx(ft)))
    };
    (p.hip_l, p.knee_l, p.foot_l) = leg(hip_l, u_l, al, pl);
    (p.hip_r, p.knee_r, p.foot_r) = leg(hip_r, u_r, ar, pr);

    // ── Trunk: lean into the speed, shoulders counter-rotate the pelvis, head stays on the road ──
    // Reference (user, 2026-10): an upright armoured run — only a slight forward lean.
    let lean = lerp(0.04, lerp(0.11, 0.17, sprint), run) + run * 0.03 * (1.0 - crest) * 0.5;
    // Overlapping action: nothing moves in lock-step. The pelvis leads, the shoulders follow it a
    // beat later, the arms later still, the elbows and the head last — identical in-phase sines on
    // every joint are what read as stiff / robotic.
    let shoulder = lerp(0.07, lerp(0.16, 0.19, sprint), run) * (c - 0.2).cos(); // + = right shoulder forward
    // The trunk soaks up each landing a moment after the low point (and the head counters most
    // of it so the gaze stays steady).
    let absorb = lerp(0.015, 0.03, run) * -(TAU * (step - (g.duty + 0.5 * run)) - 0.7).cos();
    // The trunk takes back most of the pelvic drop so the shoulders stay nearly level.
    p.torso = Jp::r(
        Quat::from_rotation_y(-pel_yaw - shoulder)
            * e3(lean - lerp(0.0, 0.03, run) + absorb, 0.0, -0.75 * pel_drop),
    );
    let head_yaw = lerp(0.07, lerp(0.13, 0.17, sprint), run) * (c - 0.45).cos();
    p.head = Jp::r(e3(-lean * 0.75 - 0.7 * absorb, head_yaw * 0.85, -0.25 * pel_drop));

    // ── Arms: opposite arm to the forward leg (right/sword arm forward when the left boot is out
    // front). Sprint-coaching rules of thumb: the swing comes from a relaxed shoulder with the
    // elbows kept close to the body; the hand rises to about chin height just inside the
    // shoulder, drifting toward (never across) the midline, and drops past the hip behind; the
    // elbow is NOT locked at 90° — it closes to ~70° in front and opens past 90° behind, trailing
    // the shoulder a beat (that lag is what reads as loose rather than robotic). A walk swings
    // near-straight. ──
    // A compact swing with the fists ahead of the hips (the reference look), not a sprinter's
    // full pump.
    let amp = lerp(0.26, lerp(0.46, 0.56, sprint), run);
    let back_bias = lerp(0.04, 0.18, run);
    // Elbows fairly open (~65-75 deg of flex, i.e. a 105-115 deg arm angle) — the user's
    // reference keeps the arms much less bent than a sprinter's tight 90.
    let flex_front = lerp(0.45, lerp(1.25, 1.35, sprint), run);
    let flex_back = lerp(0.12, lerp(1.0, 1.05, sprint), run);
    // One arm: `scale` trims the pump; `cross_f` drifts the front swing toward the midline and
    // `cross_b` tucks the back swing toward the spine (a bent arm otherwise flings the fist out
    // past the hip); `out` is the resting abduction (+ = away from the body); `elbow_fix` holds the
    // elbow at a steady carry.
    let arm = |fwd: f32, fwd_late: f32, side: f32, scale: f32, cross_f: f32, cross_b: f32, out: f32, elbow_fix: f32| {
        let z = out - run * (cross_f * fwd.max(0.0) + cross_b * (-fwd).max(0.0));
        let sh = e3(-scale * amp * fwd + back_bias, -0.2 * run * side, side * z);
        let pump = -lerp(flex_back, flex_front, 0.5 + 0.5 * fwd_late);
        let el = rx(lerp(pump, -0.5 * (flex_back + flex_front), elbow_fix));
        (sh, el)
    };
    // The arm trails the leg phase a touch and the forearm the upper arm — enough to read as
    // loose, not so much that the hands whip.
    let arm_swing = (c - 0.15).cos();
    let late = (c - 0.15 - 0.25).cos();
    // Free (sword) arm: the full sprinter's pump.
    let (sr, er) = arm(arm_swing, late, 1.0, lerp(1.0, 0.8, armed), 0.25, 0.4, lerp(0.0, -0.06, run), 0.0);
    // Shield arm: a shield is CARRIED, not pumped — elbow held near 90° with the board upright on
    // the outside of the forearm, riding the stride with only a small swing (pumping it flailed
    // the board and drove it through the fist and thigh).
    // (Fully fixed elbow + a near-dead shoulder read as a stiff, wrong-looking arm: keep a relaxed
    // half-pump with some elbow give, the board tucked closer to the body.)
    let (sl, el) = arm(-arm_swing, -late, -1.0, lerp(0.85, 0.45, run), 0.0, 0.1, lerp(0.0, 0.08, run), lerp(0.2, 0.7, run));
    // The shoulder girdle travels with its arm (forward + a hair up on the front swing, back on
    // the back swing) instead of the arm pivoting about a bolted-down socket.
    let girdle = |rest: Vec3, fwd: f32| {
        rest + Vec3::new(0.0, lerp(0.006, 0.014, run) * fwd.max(0.0), lerp(0.015, 0.03, run) * fwd)
    };
    p.sh_r = Jp { t: Some(girdle(rig.shoulder_r, arm_swing)), r: sr };
    p.el_r = Jp::r(er);
    p.sh_l = Jp { t: Some(girdle(rig.shoulder, -arm_swing)), r: sl };
    p.el_l = Jp::r(el);
    // With the blade in hand, the wrist rides the pump against it so the sword stays shouldered
    // near-upright instead of fanning behind the head.
    let wrist = armed * run * 0.85 * (lerp(1.0, 0.8, armed) * amp * arm_swing + (flex_front - flex_back) * 0.5 * late);
    p.sword = Jp::r(rx(wrist) * sword_rest_r().slerp(posed_sword(-2.046, -0.52, 0.119).r, run));
    // The board hangs off the hand, so a flexed elbow would tip it flat like a tray; cancel the
    // elbow's pitch on it so it stays upright, edge-on along the body, through the whole stride.
    let (el_x, _, _) = el.to_euler(EulerRot::XYZ);
    let undo = rx(-el_x * lerp(0.4, 0.9, run));
    p.shield = Jp { t: Some(undo * SHIELD_GAIT_T), r: undo * shield_gait_r() };
    p
}

/// Preview/staging drivers (`FOREST_VIEW_ANIM`, `FOREST_ANIMTEST`, demos): play the gait at a
/// world ground speed exactly as movement would (foot-locked phase advance).
pub(crate) fn stage_gait(hero: &mut super::Hero, speed: f32, dt: f32) {
    hero.moving = true;
    hero.moving_amt = 1.0;
    hero.gait_speed = speed;
    hero.walk_phase += dt * gait_phase_rate(speed);
}

fn footman_loco_pose(t: f32, wp: f32, m: f32, speed: f32, armed: f32, shield_back: f32) -> Pose {
    idle_pose(t).lerp(&footman_gait(wp, speed, armed, shield_back), m)
}

/// Footman combat-stance locomotion with two extra axes driven by `movement` —
/// `back` (0..1) cross-fades toward the gait played in REVERSE phase (a backpedal: the hero
/// steps backward while still facing the foe), and `twist` (radians) yaws the pelvis+legs
/// toward the movement while the torso/head counter-rotate to stay square on the target — the
/// classic lower-body-aims-along-movement / upper-body-faces-target split every lock-on game
/// uses, here as a differential yaw on the existing joints.
#[allow(clippy::too_many_arguments)]
pub(crate) fn stance_loco_pose(t: f32, wp: f32, m: f32, speed: f32, back: f32, twist: f32, armed: f32, shield_back: f32) -> Pose {
    let mut p = footman_loco_pose(t, wp, m, speed, armed, shield_back);
    if back > 0.001 {
        // The same cycle run backward reads as stepping back; the mid-blend "gather step" as the
        // two phases cancel is exactly what a person does reversing direction.
        p = p.lerp(&footman_loco_pose(t, -wp, m, speed, armed, shield_back), back.clamp(0.0, 1.0));
    }
    if twist.abs() > 1e-3 {
        // Hips carry the legs AND the torso (rig: hips → torso, hips → hip_l/r), so yawing the
        // hips aims the whole lower body along the movement; the torso takes most of the counter
        // and the head the remainder, landing the eyes exactly back on the foe.
        p.hips.r = Quat::from_rotation_y(twist) * p.hips.r;
        p.torso.r = Quat::from_rotation_y(-twist * 0.85) * p.torso.r;
        p.head.r = Quat::from_rotation_y(-twist * 0.15) * p.head.r;
    }
    p
}

/// **Combat-guard overlay** — while the stance holds, the knight actually LOOKS ready to fight:
/// weight dropped into bent knees, torso crouched a touch forward, the shield raised into a
/// half-guard and the blade carried UP at the ready instead of trailing at rest (which also stops
/// the arms doing their casual walk-swing mid-fight). Blended over idle/walk/run by `amt`
/// (`hero.stance_amt`), so leaving combat melts back to the relaxed carry — and coming out of a
/// roll/attack flows straight into this ready pose. Attack/block/roll clips own their joints
/// wholesale past this point, so the overlay only colours locomotion.
fn guard_overlay(p: &mut Pose, amt: f32, moving: f32) {
    let a = amt.clamp(0.0, 1.0);
    if a <= 0.001 {
        return;
    }
    // Moving legs already have a solved support/recovery. Apply the extra guard crouch
    // only as movement settles; bending those knees again drove the supporting boot down.
    let lower_amt = a * (1.0 - moving.clamp(0.0, 1.0));
    if let Some(t) = p.hips.t {
        p.hips.t = Some(t - Vec3::new(0.0, 0.045 * lower_amt, 0.0));
    }
    p.hips.r = e3(0.05 * lower_amt, 0.0, 0.0) * p.hips.r;
    p.torso.r = e3(0.09 * a, 0.0, 0.0) * p.torso.r;
    p.knee_l.r = p.knee_l.r * rx(0.22 * lower_amt);
    p.knee_r.r = p.knee_r.r * rx(0.20 * lower_amt);
    p.hip_l.r = p.hip_l.r * rx(-0.11 * lower_amt);
    p.hip_r.r = p.hip_r.r * rx(-0.10 * lower_amt);
    // Sword arm to a mid guard — forearm raised, blade angled up-forward at the ready.
    p.sh_r = p.sh_r.lerp(Jp::r(e3(-0.35, -0.1, 0.28)), a);
    p.el_r = p.el_r.lerp(Jp::r(rx(-1.15)), a);
    p.sword = p.sword.lerp(Jp::r(e3(1.15, 0.25, -0.1)), a);
    // Shield swings from the edge-on carry into a forward half-guard.
    p.sh_l = p.sh_l.lerp(Jp::r(e3(-0.45, 0.1, -0.35)), a);
    p.el_l = p.el_l.lerp(Jp::r(rx(-1.05)), a);
    p.shield = p.shield.lerp(Jp { t: Some(Vec3::new(-0.02, -0.02, 0.12)), r: e3(0.7, -0.8, 0.0) }, a);
}

fn blend_t(a: Option<Vec3>, b: Option<Vec3>, s: f32) -> Option<Vec3> {
    match (a, b) {
        (Some(x), Some(y)) => Some(x.lerp(y, s)),
        (Some(x), None) => Some(x),
        (None, Some(y)) => Some(y),
        (None, None) => None,
    }
}

/// Shield-block while still mobile: the torso/arms/shield brace by `block`, but the legs (and the
/// hip bob) only brace as the hero stands still (`1 - moving`) — so blocking *while walking* keeps
/// the legs striding instead of freezing them and sliding the body across the ground.
fn brace(loco: &Pose, d: &Pose, block: f32, moving: f32) -> Pose {
    let leg = block * (1.0 - moving);
    Pose {
        hips: Jp { t: blend_t(loco.hips.t, d.hips.t, leg), r: loco.hips.r.slerp(d.hips.r, block) },
        torso: loco.torso.lerp(d.torso, block),
        head: loco.head.lerp(d.head, block),
        sh_l: loco.sh_l.lerp(d.sh_l, block),
        sh_r: loco.sh_r.lerp(d.sh_r, block),
        el_l: loco.el_l.lerp(d.el_l, block),
        el_r: loco.el_r.lerp(d.el_r, block),
        hip_l: loco.hip_l.lerp(d.hip_l, leg),
        hip_r: loco.hip_r.lerp(d.hip_r, leg),
        knee_l: loco.knee_l.lerp(d.knee_l, leg),
        knee_r: loco.knee_r.lerp(d.knee_r, leg),
        foot_l: loco.foot_l.lerp(d.foot_l, leg),
        foot_r: loco.foot_r.lerp(d.foot_r, leg),
        shield: loco.shield.lerp(d.shield, block),
        sword: loco.sword.lerp(d.sword, block),
    }
}

/// An upper-body action (an attack) laid over locomotion legs: the action drives torso/head/arms/
/// sword/shield; the legs (and the hip bob) ease toward the walking/running gait by `leg`
/// (= moving_amt), so swinging mid-run keeps the legs striding (a "running attack") instead of
/// freezing into the attack's planted stance. Standing still → `leg≈0` → the full attack.
pub(crate) fn action_over_loco(action: &Pose, loco: &Pose, leg: f32) -> Pose {
    Pose {
        hips: Jp { t: blend_t(action.hips.t, loco.hips.t, leg), r: action.hips.r.slerp(loco.hips.r, leg) },
        torso: action.torso,
        head: action.head,
        sh_l: action.sh_l,
        sh_r: action.sh_r,
        el_l: action.el_l,
        el_r: action.el_r,
        hip_l: action.hip_l.lerp(loco.hip_l, leg),
        hip_r: action.hip_r.lerp(loco.hip_r, leg),
        knee_l: action.knee_l.lerp(loco.knee_l, leg),
        knee_r: action.knee_r.lerp(loco.knee_r, leg),
        foot_l: action.foot_l.lerp(loco.foot_l, leg),
        foot_r: action.foot_r.lerp(loco.foot_r, leg),
        shield: action.shield,
        sword: action.sword,
    }
}

/// A forward running leap (studio `jumpForward` feel) — blended over the plain vertical jump by how
/// fast the hero is moving. Now a real broad-jump arc: lead knee drives high at launch/apex then
/// **extends to plant** as you fall, while the trail leg scissors the other way — so the silhouette
/// changes through the jump instead of holding one stiff frame. `h` = apex closeness, `fall` ramps
/// 0→1 only on the descent (signed velocity), driving the landing reach.
fn leap_pose(vel_y: f32) -> Pose {
    let v = (vel_y / 6.5).clamp(-1.0, 1.0); // 6.5 = movement::JUMP_SPEED
    let h = (1.0 - v.abs()).clamp(0.0, 1.0);
    let fall = (-v).max(0.0); // 0 on the way up, 1 falling fast
    let mut p = rest();
    p.torso = Jp::r(e3(0.42 - fall * 0.2, 0.12, 0.0)); // deep forward dive, chest opens to spot the landing
    p.head = Jp::r(rx(-0.2 + fall * 0.3)); // chin tucks in flight, lifts to look down on descent
    // Lead (left) leg: knee tucks high through the climb, then drives down/forward to reach the ground.
    p.hip_l = Jp::r(rx(-0.95 + h * 0.2 + fall * 0.7));
    p.knee_l = Jp::r(rx(1.15 - fall * 0.95)); // tucked at apex, straightens to plant
    p.foot_l = Jp::r(rx(-0.35 + fall * 0.4));
    // Trail (right) leg: streams back hard at launch, sweeps forward under you as you fall (scissor).
    p.hip_r = Jp::r(rx(0.65 - fall * 0.55));
    p.knee_r = Jp::r(rx(0.3 + fall * 0.45));
    p.foot_r = Jp::r(rx(0.3 - fall * 0.2));
    // Arms pump the broad jump: lead arm reaches forward/up, trail arm drives back and opens on descent.
    p.sh_l = Jp::r(e3(-0.7 - h * 0.45, 0.0, -0.25));
    p.el_l = Jp::r(rx(-0.6));
    p.sh_r = Jp::r(e3(0.35 + fall * 0.25, 0.0, 0.3 + fall * 0.2));
    p.el_r = Jp::r(rx(-0.85 + h * 0.3));
    p
}

/// **Sand Dash** — the blink read as a swift, committed forward lunge with a flat sword swipe, so
/// the move *travels* instead of teleporting. `p` is 0→1 progress along the slide
/// (`hero.dash_t / movement::DASH_TIME`). A `lunge` envelope (0 at the ends, 1 mid-blink) drops the
/// hips and drives the legs into a speed-skater push; the sword arm whips a horizontal swipe across
/// the dash. The tail eases back toward locomotion in [`hero_anim`] so there's no snap on landing.
fn dash_pose(p: f32) -> Pose {
    let lunge = (p * PI).sin(); // deepest commitment mid-dash, settled at both ends
    let mut po = rest();
    po.hips = Jp { t: Some(Vec3::new(0.0, 1.0 - lunge * 0.13, lunge * 0.05)), r: e3(lunge * 0.12, 0.0, 0.0) };
    po.torso = Jp::r(e3(0.26 + lunge * 0.18, lerp(-0.32, 0.42, p), 0.0)); // pitch into the dash + twist through the swipe
    po.head = Jp::r(e3(-0.16, lerp(-0.16, 0.22, p), 0.0));
    // Lead (left) leg drives ahead, trail (right) leg streams back — a flat, low push.
    po.hip_l = Jp::r(rx(-0.72 - lunge * 0.22));
    po.knee_l = Jp::r(rx(0.5 + lunge * 0.3));
    po.foot_l = Jp::r(rx(-0.2));
    po.hip_r = Jp::r(rx(0.6 + lunge * 0.32));
    po.knee_r = Jp::r(rx(0.42));
    po.foot_r = Jp::r(rx(0.26));
    // Sword arm whips a flat horizontal swipe across the blink; off hand trails for balance.
    po.sh_r = Jp::r(e3(lerp(-0.2, -1.35, p), lerp(-0.7, 0.45, p), lerp(0.5, -0.3, p)));
    po.el_r = Jp::r(rx(lerp(-1.25, -0.3, p)));
    po.sword = Jp::r(e3(lerp(2.3, 2.5, p), lerp(0.7, -0.45, p), lerp(-0.55, 0.3, p)));
    po.sh_l = Jp::r(e3(-0.3 - lunge * 0.2, 0.0, -0.5));
    po.el_l = Jp::r(rx(-0.85));
    po.shield = Jp { t: Some(SHIELD_GAIT_T), r: shield_gait_r() };
    po
}

/// **Dodge roll** — the tucked-ball pose held through the somersault. The ROOT owns the actual
/// tumble (a full 2π pitch about the centre of mass, in `movement::player_move`); this just folds
/// the limbs into the tuck: chin down, knees hauled to the chest, arms wrapped in, shield/sword
/// pulled tight so nothing flails through the spin. Blended in/out by the roll envelope in
/// [`hero_anim`] so the stand-up flows back into locomotion.
fn roll_pose() -> Pose {
    let mut p = rest();
    p.hips = Jp { t: Some(Vec3::new(0.0, 0.74, 0.0)), r: rx(0.35) };
    p.torso = Jp::r(rx(1.0));
    p.head = Jp::r(rx(0.55)); // chin tucked
    p.hip_l = Jp::r(e3(-1.7, 0.0, 0.06));
    p.hip_r = Jp::r(e3(-1.75, 0.0, -0.06));
    p.knee_l = Jp::r(rx(2.15));
    p.knee_r = Jp::r(rx(2.2));
    p.foot_l = Jp::r(rx(0.5));
    p.foot_r = Jp::r(rx(0.5));
    p.sh_l = Jp::r(e3(-0.9, 0.0, -0.45));
    p.el_l = Jp::r(rx(-1.9));
    p.sh_r = Jp::r(e3(-0.85, 0.0, 0.45));
    p.el_r = Jp::r(rx(-1.8));
    p.shield = Jp { t: Some(SHIELD_GAIT_T), r: shield_gait_r() };
    p.sword = Jp::r(e3(2.4, 0.3, 0.0));
    p
}

// ── Jump (physics height → studio airtime formulas) ─────────────────────────────────────
// A standing hop, but no longer mirror-symmetric: signed velocity splits **rise** (legs trail from
// the push-off) → **apex** (knees tuck up, arms thrown high + a small torso twist for life) →
// **fall** (legs reach down to land, arms open for balance). The lead/trail legs differ so it never
// reads like a flat frontal frame.
fn jump_pose(vel_y: f32) -> Pose {
    let v = (vel_y / 6.5).clamp(-1.0, 1.0); // 6.5 = movement::JUMP_SPEED; signed: + rising, − falling
    let h = (1.0 - v.abs()).clamp(0.0, 1.0); // studio `height`: 0 at launch/landing, 1 at apex
    let rise = v.max(0.0); // 1 just off the ground, 0 by apex
    let fall = (-v).max(0.0); // 0 until apex, 1 dropping fast
    let mut p = rest(); // root owns real height → hips stay at rest
    p.torso = Jp::r(e3(0.3 - h * 0.45 + fall * 0.2, h * 0.18, h * 0.12)); // crunch + a touch of twist/roll at apex
    p.head = Jp::r(rx(-0.2 + h * 0.15 - fall * 0.2));
    // Lead (left) leg tucks higher at apex; trail (right) trails the push-off and reaches first to land.
    p.hip_l = Jp::r(rx(-0.4 + h * 0.95 - fall * 0.35));
    p.hip_r = Jp::r(rx(-0.6 + h * 0.45 + fall * 0.2));
    p.knee_l = Jp::r(rx(1.0 - h * 0.95 + rise * 0.2));
    p.knee_r = Jp::r(rx(1.0 - h * 0.5 - fall * 0.3));
    p.foot_l = Jp::r(rx(-0.5 + h * 0.6));
    p.foot_r = Jp::r(rx(-0.5 + h * 0.8 + fall * 0.2));
    // Arms thrown up at apex; on the way down the off arm sweeps wider to balance the descent.
    p.sh_l = Jp::r(e3(0.5 - h * 1.7 - rise * 0.2, 0.0, -h * 0.4));
    p.el_l = Jp::r(rx(-0.8 + h * 0.5));
    p.sh_r = Jp::r(e3(0.5 - h * 1.5, 0.0, h * 0.45 + fall * 0.35));
    p.el_r = Jp::r(rx(-0.85 + h * 0.5));
    p
}

// ── Defend (shield block) — full studio depth (ease=1) + idle sway; cross-faded by block_amt. ──
fn defend_pose(t: f32) -> Pose {
    // The three.js footman BLOCK: bladed stance, shield squared in front of the chest, the sword
    // drawn back at the hip with its point toward the foe.
    let b = (t * PI * 2.0 / 1.2).sin();
    let mut p = rest();
    p.hips = Jp { t: Some(Vec3::new(0.0, 1.035, 0.0)), r: m3(0.0, -0.25, 0.0) };
    p.torso = Jp::r(m3(0.1 + 0.02 * b, -0.15, 0.0));
    p.head = Jp::r(m3(0.0, 0.38, 0.0));
    p.hip_l = Jp::r(m3(-0.32, 0.25, 0.06));
    p.knee_l = Jp::r(rx(0.38));
    p.foot_l = Jp::r(rx(-0.06));
    p.hip_r = Jp::r(m3(0.28, 0.25, -0.06));
    p.knee_r = Jp::r(rx(0.3));
    p.foot_r = Jp::r(rx(-0.58));
    p.sh_l = Jp::r(m3(-1.15, 0.0, -0.2));
    p.el_l = Jp::r(rx(-1.05));
    p.shield = posed_shield(2.133, -0.344, 0.06);
    p.sh_r = Jp::r(m3(-0.35, 0.0, -0.25));
    p.el_r = Jp::r(rx(-1.15));
    p.sword = posed_sword(-0.09, 0.149, 0.254);
    p
}

// ── Attacks (the studio 3-phase wind/strike/recovery functions, verbatim lerp targets) ──
pub(crate) enum Phase {
    Wind,
    Strike,
    Recovery,
}

/// Split our one-shot swing progress `ap = attack_t/ATTACK_DURATION` into the studio phases, eased
/// like the studio's `getAttackPhase`. `WIND_END` aligns the strike start with combat's `HIT_PHASE`.
pub(crate) fn attack_phase(ap: f32) -> (Phase, f32) {
    const WIND_END: f32 = 0.30;
    const STRIKE_END: f32 = 0.55;
    if ap < WIND_END {
        (Phase::Wind, ease_out_cubic(ap / WIND_END))
    } else if ap < STRIKE_END {
        let t = (ap - WIND_END) / (STRIKE_END - WIND_END);
        (Phase::Strike, 1.0 - (1.0 - t).powf(2.5))
    } else {
        (Phase::Recovery, smoothstep((ap - STRIKE_END) / (1.0 - STRIKE_END)))
    }
}

pub(crate) fn attack_pose(variant: u8, phase: &Phase, p: f32) -> Pose {
    match variant {
        1 => horizontal_slash(phase, p),
        2 => forward_thrust(phase, p),
        v if v == super::combat::HEAVY_VARIANT => heavy_chop(phase, p),
        _ => overhead_chop(phase, p),
    }
}

/// The charged **Heavy Strike** — a true two-handed **overhead smash**: the wind-up hauls the blade
/// up over the head, the strike drives it down through the front with the whole body behind it, and
/// the recovery settles back to rest. The raise is modelled on the proven `overhead_chop` (attack1):
/// the arm lifts via a **moderate shoulder flex + a folded elbow** (NOT by cranking `sh_r` X toward
/// π — that swings the arm up the *back* arc, wrenching the shoulder backward like a backstroke), so
/// the blade is hauled up over the head the natural way. Both hands grip (off-hand drawn up to the
/// haft) and the legs coil into a load-crouch for the heavy. The cocked **Wind-end pose IS the held
/// [`charge_stance`]**, so the release flows seamlessly from raised-overhead into the downward chop —
/// one continuous "raise → smash".
fn heavy_chop(phase: &Phase, p: f32) -> Pose {
    let mut po = rest();
    match phase {
        Phase::Wind => {
            // Haul the blade up over the head the natural way (shoulder flex + folded elbow, à la
            // attack1), both hands to the haft, legs coiled into a load-crouch — wound up to smash down.
            po.hips = Jp { t: Some(Vec3::new(0.0, lerp(1.05, 0.97, p), lerp(0.0, -0.1, p))), r: e3(lerp(0.0, 0.06, p), lerp(0.0, -0.22, p), 0.0) };
            po.torso = Jp::r(e3(lerp(0.0, -0.16, p), lerp(0.0, -0.18, p), 0.0)); // coil away, ready to uncoil
            po.head = Jp::r(e3(lerp(0.0, -0.02, p), lerp(0.0, 0.18, p), 0.0)); // eyes stay on the target
            po.sh_r = Jp::r(e3(lerp(0.12, -2.9, p), 0.0, lerp(0.15, 0.05, p))); // raise up the FRONT arc (neg X) → arm overhead, leaning toward the foe (no back-wrench)
            po.el_r = Jp::r(rx(lerp(-0.4, -0.3, p))); // near-straight: arm + blade read as one raised line
            po.sword = Jp::r(e3(lerp(SWORD_REST_X, 2.3, p), lerp(0.3, 0.2, p), 0.0)); // counter-rotate: blade laid back over the head toward horizontal (natural cock, not a vertical flagpole)
            po.sh_l = Jp::r(e3(lerp(0.1, 0.45, p), lerp(0.0, 0.35, p), lerp(-0.15, -0.15, p))); // off hand drawn up to the haft (two-handed)
            po.el_l = Jp::r(rx(lerp(-0.5, -1.2, p)));
            po.shield = Jp { t: Some(SHIELD_REST_T), r: e3(lerp(0.15, 0.3, p), lerp(-1.5, -1.0, p), 0.0) };
            po.hip_l = Jp::r(rx(lerp(0.0, -0.2, p)));
            po.hip_r = Jp::r(rx(lerp(0.0, -0.25, p)));
            po.knee_l = Jp::r(rx(lerp(0.0, 0.3, p))); // braced load-crouch
            po.knee_r = Jp::r(rx(lerp(0.0, 0.32, p)));
        }
        Phase::Strike => {
            // Explosive downward chop — the raised arm unfolds and smashes through the front, body
            // drives in, stepping into a planted lunge.
            po.hips = Jp { t: Some(Vec3::new(0.0, 0.97 + (p * PI).sin() * 0.05, lerp(-0.1, 0.32, p))), r: e3(lerp(0.06, 0.18, p), lerp(-0.22, 0.16, p), 0.0) };
            po.torso = Jp::r(e3(lerp(-0.16, 0.42, p), lerp(-0.18, 0.12, p), 0.0));
            po.head = Jp::r(e3(lerp(-0.02, 0.14, p), lerp(0.18, -0.06, p), 0.0));
            po.sh_r = Jp::r(e3(lerp(-2.9, -1.45, p), lerp(0.0, 0.1, p), lerp(0.05, -0.12, p))); // overhead-front → down-front (one forward arc)
            po.el_r = Jp::r(rx(lerp(-0.3, -0.3, p)));
            po.sword = Jp::r(e3(lerp(2.3, 2.75, p), lerp(0.2, -0.5, p), lerp(0.0, -0.3, p))); // blade whips down through the front
            po.sh_l = Jp::r(e3(lerp(0.45, -0.2, p), lerp(0.35, -0.1, p), lerp(-0.15, -0.4, p)));
            po.el_l = Jp::r(rx(lerp(-1.2, -0.85, p)));
            po.hip_l = Jp::r(rx(lerp(-0.2, 0.5, p)));
            po.knee_l = Jp::r(rx(lerp(0.3, 0.6, p))); // step into a planted lunge
            po.hip_r = Jp::r(rx(lerp(-0.25, -0.15, p)));
            po.knee_r = Jp::r(rx(lerp(0.32, 0.42, p)));
        }
        Phase::Recovery => {
            po.hips = Jp { t: Some(Vec3::new(0.0, lerp(0.97, 1.05, p), lerp(0.32, 0.0, p))), r: e3(lerp(0.18, 0.0, p), lerp(0.16, 0.0, p), 0.0) };
            po.torso = Jp::r(e3(lerp(0.42, 0.0, p), lerp(0.12, 0.0, p), 0.0));
            po.head = Jp::r(e3(lerp(0.14, 0.0, p), lerp(-0.06, 0.0, p), 0.0));
            po.sh_r = Jp::r(e3(lerp(-1.45, 0.12, p), lerp(0.1, 0.0, p), lerp(-0.12, 0.15, p)));
            po.el_r = Jp::r(rx(lerp(-0.3, -0.4, p)));
            po.sword = Jp::r(e3(lerp(2.75, SWORD_REST_X, p), lerp(-0.5, 0.3, p), lerp(-0.3, 0.0, p)));
            po.sh_l = Jp::r(e3(lerp(-0.2, 0.1, p), lerp(-0.12, 0.0, p), lerp(-0.4, -0.15, p)));
            po.el_l = Jp::r(rx(lerp(-0.85, -0.5, p)));
            po.hip_l = Jp::r(rx(lerp(0.5, 0.0, p)));
            po.knee_l = Jp::r(rx(lerp(0.6, 0.0, p)));
            po.hip_r = Jp::r(rx(lerp(-0.15, 0.0, p)));
            po.knee_r = Jp::r(rx(lerp(0.42, 0.0, p)));
        }
    }
    po
}

/// The held **charge stance** while winding up a Heavy Strike (after the light swing, before
/// release). Completely reworked: instead of a stiff sword-out-to-the-side point, this is a proper
/// **two-handed overhead raise** — the blade hauled up high over the head, body coiled back onto the
/// rear foot, ready to smash straight down. It IS the wind-up phase of [`heavy_chop`] held at the
/// current charge (`frac` 0→1 deepens the coil), so the release flows seamlessly into the chop's
/// strike from exactly this cocked position — one continuous "raise → smash" motion. A small
/// `wobble` (a tiny tremble of effort, driven from wall-clock in [`hero_anim`]) keeps it alive
/// instead of frozen.
fn charge_stance(frac: f32, wobble: f32) -> Pose {
    let f = frac.clamp(0.0, 1.0);
    // Reuse the heavy chop's wind-up so the held coil and the strike are the same motion.
    let mut po = heavy_chop(&Phase::Wind, f);
    // Tremble of effort: a faint shake on the blade/arms + a breath at the torso, scaled by how
    // wound-up we are, so a full charge visibly strains.
    let tw = wobble * f;
    po.sword = Jp::r(po.sword.r * e3(tw * 0.05, tw * 0.07, 0.0));
    po.torso = Jp::r(po.torso.r * e3(tw * 0.03, 0.0, tw * 0.02));
    po.sh_r = Jp::r(po.sh_r.r * e3(0.0, 0.0, tw * 0.04));
    po
}

/// attack1 — diagonal overhead chop (studio `applyOverheadChop`).
fn overhead_chop(phase: &Phase, p: f32) -> Pose {
    let mut po = rest();
    match phase {
        Phase::Wind => {
            po.hips = Jp { t: Some(Vec3::new(0.0, lerp(1.05, 0.99, p), lerp(0.0, -0.1, p))), r: e3(lerp(0.0, 0.06, p), lerp(0.0, -0.25, p), 0.0) };
            po.torso = Jp::r(e3(lerp(0.0, -0.18, p), lerp(0.0, -0.15, p), 0.0));
            po.head = Jp::r(e3(0.0, lerp(0.0, 0.2, p), 0.0));
            po.sh_r = Jp::r(e3(lerp(0.12, 0.35, p), lerp(0.0, -0.55, p), lerp(0.15, 0.45, p)));
            po.el_r = Jp::r(rx(lerp(-0.4, -1.75, p)));
            po.sword = Jp::r(e3(lerp(SWORD_REST_X, 0.55, p), lerp(0.3, 0.55, p), lerp(0.0, -0.45, p)));
            po.sh_l = Jp::r(e3(lerp(0.1, 0.05, p), lerp(0.0, 0.15, p), lerp(-0.15, -0.25, p)));
            po.el_l = Jp::r(rx(lerp(-0.5, -0.65, p)));
            po.shield = Jp { t: Some(Vec3::new(0.0, 0.0, lerp(0.14, 0.16, p))), r: e3(lerp(0.15, 0.25, p), lerp(-0.45, -0.35, p), lerp(0.1, 0.05, p)) };
            po.hip_l = Jp::r(rx(lerp(0.0, -0.2, p)));
            po.hip_r = Jp::r(rx(lerp(0.0, -0.25, p)));
        }
        Phase::Strike => {
            po.hips = Jp { t: Some(Vec3::new(0.0, 0.99 + (p * PI).sin() * 0.05, lerp(-0.1, 0.2, p))), r: e3(lerp(0.06, 0.14, p), lerp(-0.25, 0.15, p), 0.0) };
            po.torso = Jp::r(e3(lerp(-0.18, 0.26, p), lerp(-0.15, 0.1, p), 0.0));
            po.head = Jp::r(e3(lerp(0.0, 0.08, p), lerp(0.2, -0.05, p), 0.0));
            po.sh_r = Jp::r(e3(lerp(0.35, -1.25, p), lerp(-0.55, 0.2, p), lerp(0.45, -0.15, p)));
            po.el_r = Jp::r(rx(lerp(-1.75, -0.35, p)));
            po.sword = Jp::r(e3(lerp(0.55, 2.7, p), lerp(0.55, -0.8, p), lerp(-0.45, -0.8, p)));
            po.sh_l = Jp::r(e3(lerp(0.05, -0.15, p), lerp(0.15, -0.1, p), lerp(-0.25, -0.35, p)));
            po.el_l = Jp::r(rx(lerp(-0.65, -0.85, p)));
            po.hip_l = Jp::r(rx(lerp(-0.2, 0.35, p)));
            po.knee_l = Jp::r(rx(lerp(0.0, 0.4, p)));
            po.hip_r = Jp::r(rx(lerp(-0.25, -0.1, p)));
            po.knee_r = Jp::r(rx(lerp(0.0, 0.3, p)));
        }
        Phase::Recovery => {
            po.hips = Jp { t: Some(Vec3::new(0.0, lerp(0.99, 1.05, p), lerp(0.2, 0.0, p))), r: e3(lerp(0.14, 0.0, p), lerp(0.15, 0.0, p), 0.0) };
            po.torso = Jp::r(e3(lerp(0.26, 0.0, p), lerp(0.1, 0.0, p), 0.0));
            po.head = Jp::r(e3(lerp(0.08, 0.0, p), lerp(-0.05, 0.0, p), 0.0));
            po.sh_r = Jp::r(e3(lerp(-1.25, 0.12, p), lerp(0.2, 0.0, p), lerp(-0.15, 0.15, p)));
            po.el_r = Jp::r(rx(lerp(-0.35, -0.4, p)));
            po.sword = Jp::r(e3(lerp(2.7, SWORD_REST_X, p), lerp(-0.8, 0.3, p), lerp(-0.8, 0.0, p)));
            po.sh_l = Jp::r(e3(lerp(-0.15, 0.1, p), lerp(-0.1, 0.0, p), lerp(-0.35, -0.15, p)));
            po.el_l = Jp::r(rx(lerp(-0.85, -0.5, p)));
            po.hip_l = Jp::r(rx(lerp(0.35, 0.0, p)));
            po.knee_l = Jp::r(rx(lerp(0.4, 0.0, p)));
            po.hip_r = Jp::r(rx(lerp(-0.1, 0.0, p)));
            po.knee_r = Jp::r(rx(lerp(0.3, 0.0, p)));
        }
    }
    po
}

/// attack2 — horizontal slash (studio `applyHorizontalSlash`).
fn horizontal_slash(phase: &Phase, p: f32) -> Pose {
    let mut po = rest();
    match phase {
        Phase::Wind => {
            // Sink into a WIDE, LOW, planted power-stance (the reference silhouette): hips drop deep,
            // both legs splay out to the sides and bend hard, weight coiled onto both feet — loaded to
            // unleash a big horizontal sweep. The arms cock the blade back/out to the right.
            po.hips = Jp { t: Some(Vec3::new(0.0, lerp(1.05, 0.86, p), lerp(0.0, -0.04, p))), r: e3(0.0, lerp(0.0, -0.4, p), 0.0) };
            po.torso = Jp::r(e3(lerp(0.0, 0.05, p), lerp(0.0, -0.35, p), 0.0));
            po.head = Jp::r(e3(0.0, lerp(0.0, -0.3, p), 0.0));
            po.sh_r = Jp::r(e3(lerp(0.12, -0.15, p), lerp(0.0, -0.65, p), lerp(0.15, 0.55, p)));
            po.el_r = Jp::r(rx(lerp(-0.4, -1.35, p)));
            po.sword = Jp::r(e3(lerp(SWORD_REST_X, 2.35, p), lerp(0.3, 0.75, p), lerp(0.0, -0.6, p)));
            po.sh_l = Jp::r(e3(lerp(0.1, 0.25, p), lerp(0.0, 0.35, p), lerp(-0.15, -0.1, p)));
            po.el_l = Jp::r(rx(lerp(-0.5, -0.4, p)));
            po.shield = Jp { t: Some(Vec3::new(0.0, 0.0, lerp(0.14, 0.18, p))), r: e3(lerp(0.15, 0.35, p), lerp(-0.45, -0.2, p), lerp(0.1, 0.15, p)) };
            // Wide planted legs: hips roll OUT on Z (splay), thighs sit back, knees fold deep, feet flatten.
            po.hip_l = Jp::r(e3(lerp(0.0, -0.12, p), 0.0, lerp(0.0, 0.4, p)));
            po.knee_l = Jp::r(rx(lerp(0.0, 0.7, p)));
            po.foot_l = Jp::r(rx(lerp(0.0, -0.25, p)));
            po.hip_r = Jp::r(e3(lerp(0.0, -0.1, p), 0.0, lerp(0.0, -0.5, p)));
            po.knee_r = Jp::r(rx(lerp(0.0, 0.78, p)));
            po.foot_r = Jp::r(rx(lerp(0.0, -0.3, p)));
        }
        Phase::Strike => {
            // Uncoil EXPLOSIVELY: drive up out of the deep stance (hips rise 0.86→1.0) as the splayed
            // legs sweep into a forward plant and the blade whips across the front.
            po.hips = Jp { t: Some(Vec3::new(0.0, lerp(0.86, 1.0, p) + (p * PI).sin() * 0.04, lerp(-0.04, 0.2, p))), r: e3(0.0, lerp(-0.4, 0.55, p), 0.0) };
            po.torso = Jp::r(e3(lerp(0.05, 0.12, p), lerp(-0.35, 0.55, p), lerp(0.0, 0.08, p)));
            po.head = Jp::r(e3(0.0, lerp(-0.3, 0.15, p), 0.0));
            po.sh_r = Jp::r(e3(lerp(-0.15, -1.4, p), lerp(-0.65, 0.0, p), lerp(0.55, -0.4, p)));
            po.el_r = Jp::r(rx(lerp(-1.35, -0.25, p)));
            po.sword = Jp::r(e3(lerp(2.35, 2.45, p), lerp(0.75, 0.05, p), lerp(-0.6, 0.25, p)));
            po.sh_l = Jp::r(e3(lerp(0.25, -0.35, p), lerp(0.35, -0.45, p), lerp(-0.1, -0.4, p)));
            po.el_l = Jp::r(rx(lerp(-0.4, -0.75, p)));
            po.hip_l = Jp::r(e3(lerp(-0.12, 0.3, p), 0.0, lerp(0.4, 0.0, p))); // splay closes as the leg drives forward
            po.knee_l = Jp::r(rx(lerp(0.7, 0.25, p)));
            po.foot_l = Jp::r(rx(lerp(-0.25, 0.0, p)));
            po.hip_r = Jp::r(e3(lerp(-0.1, -0.15, p), 0.0, lerp(-0.5, 0.0, p)));
            po.knee_r = Jp::r(rx(lerp(0.78, 0.2, p)));
            po.foot_r = Jp::r(rx(lerp(-0.3, 0.0, p)));
        }
        Phase::Recovery => {
            po.hips = Jp { t: Some(Vec3::new(0.0, lerp(1.0, 1.05, p), lerp(0.2, 0.0, p))), r: e3(0.0, lerp(0.55, 0.0, p), 0.0) };
            po.torso = Jp::r(e3(lerp(0.12, 0.0, p), lerp(0.55, 0.0, p), lerp(0.08, 0.0, p)));
            po.head = Jp::r(e3(0.0, lerp(0.15, 0.0, p), 0.0));
            po.sh_r = Jp::r(e3(lerp(-1.4, 0.12, p), lerp(0.0, 0.0, p), lerp(-0.4, 0.15, p)));
            po.el_r = Jp::r(rx(lerp(-0.25, -0.4, p)));
            po.sword = Jp::r(e3(lerp(2.45, SWORD_REST_X, p), lerp(0.05, 0.3, p), lerp(0.25, 0.0, p)));
            po.sh_l = Jp::r(e3(lerp(-0.35, 0.1, p), lerp(-0.45, 0.0, p), lerp(-0.4, -0.15, p)));
            po.el_l = Jp::r(rx(lerp(-0.75, -0.5, p)));
            po.hip_l = Jp::r(rx(lerp(0.3, 0.0, p)));
            po.knee_l = Jp::r(rx(lerp(0.25, 0.0, p)));
            po.hip_r = Jp::r(rx(lerp(-0.15, 0.0, p)));
            po.knee_r = Jp::r(rx(lerp(0.2, 0.0, p)));
        }
    }
    po
}

/// attack3 — forward thrust (studio `applyForwardThrust`).
fn forward_thrust(phase: &Phase, p: f32) -> Pose {
    let mut po = rest();
    match phase {
        Phase::Wind => {
            po.hips = Jp { t: Some(Vec3::new(0.0, lerp(1.05, 0.97, p), lerp(0.0, -0.05, p))), r: e3(lerp(0.0, 0.08, p), lerp(0.0, -0.15, p), 0.0) };
            po.torso = Jp::r(e3(lerp(0.0, 0.1, p), lerp(0.0, -0.1, p), 0.0));
            po.head = Jp::r(e3(0.0, lerp(0.0, 0.1, p), 0.0));
            po.sh_r = Jp::r(e3(lerp(0.12, -0.35, p), lerp(0.0, -0.25, p), lerp(0.15, 0.3, p)));
            po.el_r = Jp::r(rx(lerp(-0.4, -1.45, p)));
            po.sword = Jp::r(e3(lerp(SWORD_REST_X, 2.4, p), lerp(0.3, 0.2, p), lerp(0.0, 0.3, p)));
            po.sh_l = Jp::r(e3(lerp(0.1, -0.2, p), lerp(0.0, 0.25, p), lerp(-0.15, -0.3, p)));
            po.el_l = Jp::r(rx(lerp(-0.5, -0.7, p)));
            po.shield = Jp { t: Some(Vec3::new(0.0, 0.0, lerp(0.14, 0.12, p))), r: e3(lerp(0.15, PI / 2.0, p), lerp(-0.45, -0.1, p), lerp(0.1, 0.0, p)) };
            po.hip_l = Jp::r(rx(lerp(0.0, -0.25, p)));
            po.hip_r = Jp::r(rx(lerp(0.0, -0.3, p)));
            po.knee_l = Jp::r(rx(lerp(0.0, 0.35, p)));
            po.knee_r = Jp::r(rx(lerp(0.0, 0.4, p)));
        }
        Phase::Strike => {
            po.hips = Jp { t: Some(Vec3::new(0.0, 0.97, lerp(-0.05, 0.3, p))), r: e3(lerp(0.08, 0.12, p), lerp(-0.15, 0.05, p), 0.0) };
            po.torso = Jp::r(e3(lerp(0.1, 0.2, p), lerp(-0.1, 0.05, p), 0.0));
            po.head = Jp::r(e3(lerp(0.0, 0.05, p), lerp(0.1, -0.05, p), 0.0));
            po.sh_r = Jp::r(e3(lerp(-0.35, -1.55, p), lerp(-0.25, 0.05, p), lerp(0.3, 0.05, p)));
            po.el_r = Jp::r(rx(lerp(-1.45, -0.1, p)));
            po.sword = Jp::r(e3(lerp(2.4, 2.7, p), lerp(0.2, 0.8, p), lerp(0.3, 0.4, p)));
            po.sh_l = Jp::r(e3(lerp(-0.2, -0.55, p), lerp(0.25, 0.1, p), lerp(-0.3, -0.45, p)));
            po.el_l = Jp::r(rx(lerp(-0.7, -0.85, p)));
            po.hip_l = Jp::r(rx(lerp(-0.25, 0.45, p)));
            po.knee_l = Jp::r(rx(lerp(0.35, 0.15, p)));
            po.hip_r = Jp::r(rx(lerp(-0.3, 0.1, p)));
            po.knee_r = Jp::r(rx(lerp(0.4, 0.1, p)));
        }
        Phase::Recovery => {
            po.hips = Jp { t: Some(Vec3::new(0.0, lerp(0.97, 1.05, p), lerp(0.3, 0.0, p))), r: e3(lerp(0.12, 0.0, p), lerp(0.05, 0.0, p), 0.0) };
            po.torso = Jp::r(e3(lerp(0.2, 0.0, p), lerp(0.05, 0.0, p), 0.0));
            po.head = Jp::r(e3(lerp(0.05, 0.0, p), lerp(-0.05, 0.0, p), 0.0));
            po.sh_r = Jp::r(e3(lerp(-1.55, 0.12, p), lerp(0.05, 0.0, p), lerp(0.05, 0.15, p)));
            po.el_r = Jp::r(rx(lerp(-0.1, -0.4, p)));
            po.sword = Jp::r(e3(lerp(2.7, SWORD_REST_X, p), lerp(0.8, 0.3, p), lerp(0.4, 0.0, p)));
            po.sh_l = Jp::r(e3(lerp(-0.55, 0.1, p), lerp(0.1, 0.0, p), lerp(-0.45, -0.15, p)));
            po.el_l = Jp::r(rx(lerp(-0.85, -0.5, p)));
            po.hip_l = Jp::r(rx(lerp(0.45, 0.0, p)));
            po.knee_l = Jp::r(rx(lerp(0.15, 0.0, p)));
            po.hip_r = Jp::r(rx(lerp(0.1, 0.0, p)));
            po.knee_r = Jp::r(rx(lerp(0.1, 0.0, p)));
        }
    }
    po
}

// ── Victory (studio `victory`) ──────────────────────────────────────────────────────────
fn victory_pose(t: f32) -> Pose {
    let s = (t * 1.5).sin();
    let mut p = rest();
    p.hips = Jp { t: Some(Vec3::new(0.0, 1.07 + (t * 3.5).sin() * 0.02, 0.0)), r: e3(0.0, 0.25 * s, 0.0) };
    p.torso = Jp::r(e3(-0.12, 0.05 * s, 0.0));
    p.head = Jp::r(e3(-0.25, 0.25 * s, 0.0));
    p.sh_l = Jp::r(e3(0.1, 0.2, -0.3));
    p.el_l = Jp::r(rx(-0.3));
    p.sh_r = Jp::r(e3(2.8, 0.0, -0.1)); // sword thrust skyward
    p.el_r = Jp::r(Quat::IDENTITY);
    p.sword = Jp::r(e3(0.15, 0.3, 0.0));
    // Wide stance (studio overrides the hip-joint X positions).
    p.hip_l = Jp { t: Some(Vec3::new(-0.22, -0.05, 0.0)), r: e3(0.0, 0.0, -0.15) };
    p.hip_r = Jp { t: Some(Vec3::new(0.22, -0.05, 0.0)), r: e3(0.0, 0.0, 0.15) };
    p
}

/// Seated rest pose (studio `applySeatedPose` / `SEATED`) — for a mob roosting on a stump: hips
/// dropped + tipped back, thighs forward with a deep knee bend, feet tucked, hands low. Shared by
/// the biped animator (orcs sitting on camp stumps); the caller positions the root on the stump.
pub(crate) fn sit_pose() -> Pose {
    let mut p = rest();
    p.hips = Jp { t: Some(Vec3::new(0.0, 0.6725, -0.08)), r: e3(0.10, 0.0, 0.0) };
    p.torso = Jp::r(e3(0.20, 0.0, 0.0));
    p.head = Jp::r(e3(-0.10, 0.0, 0.0));
    p.hip_l = Jp::r(e3(-0.78, 0.38, -0.18));
    p.hip_r = Jp::r(e3(-0.78, -0.38, 0.18));
    p.knee_l = Jp::r(rx(1.95));
    p.knee_r = Jp::r(rx(1.95));
    p.foot_l = Jp::r(rx(-0.55));
    p.foot_r = Jp::r(rx(-0.55));
    p.sh_l = Jp::r(e3(0.15, -0.15, -0.45));
    p.el_l = Jp::r(rx(-0.9));
    p.sh_r = Jp::r(e3(0.1, 0.2, 0.3));
    p.el_r = Jp::r(rx(-1.0));
    p.shield = Jp { t: Some(Vec3::new(0.0, -0.05, 0.1)), r: e3(0.85, -0.25, 0.12) };
    p.sword = Jp::r(e3(2.5, 0.25, 0.2));
    p
}

/// A posted town worker's repetitive two-handed tool stroke (a Warbell flavour clip, not a studio
/// one): both arms swing together on X over a fixed elbow grip, legs planted with a tiny
/// weight-shift, and a small head nod toward the work. `hoe` = a quick forward farmer stroke; else a
/// slower overhead chop/pick (woodcutter/miner). `t` is the worker's phase-desynced clock.
pub(crate) fn work_pose(t: f32, hoe: bool) -> Pose {
    let mut p = rest();
    let (arm, nod_rate) = if hoe {
        (0.6 + 0.7 * (t * 4.5).sin(), 4.5) // quick hoe, ~1.4s
    } else {
        (-0.2 + 1.3 * (0.5 - 0.5 * (t * 3.0).cos()), 3.0) // overhead → down chop/pick, ~2.1s
    };
    // Both arms drive the stroke together; a fixed elbow bend so they read as gripping the haft.
    p.sh_l = Jp::r(e3(arm, 0.0, -0.12));
    p.sh_r = Jp::r(e3(arm, 0.0, 0.12));
    p.el_l = Jp::r(rx(-0.7));
    p.el_r = Jp::r(rx(-0.7));
    p.head = Jp::r(rx((t * nod_rate).sin() * 0.06));
    // A subtle planted weight-shift so they aren't board-stiff while working.
    let sway = (t * 0.8).sin() * 0.02;
    p.hip_l = Jp::r(rx(sway));
    p.hip_r = Jp::r(rx(-sway));
    p
}

/// The bow shot's release moment as a fraction of the whole clip — the arrow entity must leave the
/// string exactly when the string hand snaps open, so the archer brain (`villagers::guard_combat`)
/// times its `ArrowSpawn` off this same constant.
pub(crate) const BOW_RELEASE_P: f32 = 0.60;

/// A Warbell flavour clip (not a studio one): the archer's **draw-and-loose**. One shot, `p` 0..1:
/// the bow arm levels at the target while the string hand reaches to the string (draw), pulls to
/// the cheek and holds a steady aiming beat (a faint tremble of effort), the string hand SNAPS open
/// at [`BOW_RELEASE_P`] with a small whole-body recoil, then everything settles back to the carry.
/// The body blades side-on (hips + torso yaw toward the string side, head counter-yawed onto the
/// target) — the root still faces the target, so the silhouette reads as a braced archer, not a
/// squared-up peasant. The off-hand `Shield` pivot carries the BOW (stave authored +Y,
/// string at -Z): this clip turns it upright into the draw; the `Sword` pivot's nocked arrow is
/// levelled at the target through the aim.
pub(crate) fn bow_pose(t: f32, p: f32) -> Pose {
    let p = p.clamp(0.0, 1.0);
    let draw = smoothstep(p / 0.40); // reach + pull to the cheek
    let loose = smoothstep((p - BOW_RELEASE_P) / 0.05); // the string hand snaps open
    let settle = smoothstep((p - 0.70) / 0.30); // ease the whole pose back to rest
    // A faint aiming tremble while at full draw (gone once loosed).
    let trem = (t * 21.0).sin() * 0.012 * draw * (1.0 - loose);

    let mut po = rest();
    // Blade the body: hips + torso yaw toward the string side, head counter-yawed onto the target,
    // weight settled into a staggered stance (lead/left foot toward the foe).
    po.hips = Jp {
        t: Some(Vec3::new(0.0, lerp(1.05, 1.01, draw), 0.0)),
        r: e3(0.0, 0.42 * draw, 0.0),
    };
    po.torso = Jp::r(e3(-0.05 * draw, 0.30 * draw, 0.04 * draw));
    po.head = Jp::r(e3(0.02 * draw + trem, -0.62 * draw, 0.0));
    po.hip_l = Jp::r(e3(-0.22 * draw, 0.12 * draw, -0.05 * draw));
    po.knee_l = Jp::r(rx(0.14 * draw));
    po.foot_l = Jp::r(rx(-0.06 * draw));
    po.hip_r = Jp::r(e3(0.14 * draw, -0.1 * draw, 0.06 * draw));
    po.knee_r = Jp::r(rx(0.22 * draw));

    // Bow arm: levels straight out at the target (compensating the torso yaw), elbow near-locked.
    po.sh_l = Jp::r(e3(lerp(0.1, -1.42, draw) + trem, lerp(0.0, 0.34, draw), lerp(-0.15, -0.06, draw)));
    po.el_l = Jp::r(rx(lerp(-0.5, -0.1, draw)));
    // The bow itself: from the at-ease carry along the forearm to UPRIGHT in the draw. With the
    // arm raised forward (hand-local −Y ≈ world-forward, +Z ≈ world-up), pitching the mesh +X by
    // +π/2 stands the stave (mesh +Y) vertical and turns the string (mesh −Z) back at the cheek.
    po.shield = Jp {
        t: Some(Vec3::new(0.0, -0.02, 0.05)),
        r: Jp::r(e3(0.12, -1.5, 0.0)).r.slerp(e3(1.55, 0.0, 0.0), draw),
    };
    // String hand: reaches forward with the nock, hauls straight back to the cheek (the elbow
    // folding to a right angle at shoulder height, shoulder drawn back around the yawed torso),
    // then SNAPS open past the release point.
    let pull = draw; // reach and pull share the envelope; the reach reads in the elbow unfolding
    po.sh_r = Jp::r(e3(
        lerp(0.12, -1.14, pull) + 0.14 * loose,
        lerp(0.0, -0.66, pull) - 0.45 * loose,
        lerp(0.15, 0.26, pull) + 0.12 * loose,
    ));
    po.el_r = Jp::r(rx(lerp(-0.4, -1.7, pull) + 0.95 * loose));
    // The nocked arrow lies level along the draw (pointing at the target), and drops with the hand
    // after the loose — the "next shaft" carried down at ease.
    po.sword = Jp::r(Jp::r(sword_rest_r()).r.slerp(e3(1.5, 0.15, 0.0), draw * (1.0 - loose)));

    // Recoil: a small whole-body give the instant the string lets go.
    if loose > 0.0 && settle < 1.0 {
        let k = loose * (1.0 - settle);
        po.torso = Jp::r(po.torso.r * e3(-0.05 * k, 0.03 * k, 0.0));
        po.sh_l = Jp::r(po.sh_l.r * e3(0.0, 0.06 * k, 0.04 * k));
    }

    // Settle everything back to the rest carry after the loose.
    let out = rest();
    if settle > 0.0 {
        return po.lerp(&out, settle);
    }
    po
}

/// A worker hauling a load home (a log / a handcart): both arms raise forward with a fixed elbow
/// bend, gripping the load level in front of the chest. The legs come from locomotion (the worker
/// walks the load home), so the caller layers this over the gait with `action_over_loco`.
pub(crate) fn carry_pose() -> Pose {
    let mut p = rest();
    p.sh_l = Jp::r(e3(-0.55, 0.0, -0.12)); // upper arm raised forward
    p.sh_r = Jp::r(e3(-0.55, 0.0, 0.12));
    p.el_l = Jp::r(rx(-0.6)); // forearm up, gripping the load level
    p.el_r = Jp::r(rx(-0.6));
    p
}

/// The caged-captive clip family (huddle / hug-and-rock / rub arms / slump, the feet-planted
/// stand-up, gripping the bars, and the breath / look / flinch / talk overlays) — a child module so
/// it can build [`Pose`]s field-by-field like the clips above; `crate::captives` drives it.
pub(crate) mod captive;

/// Which clip family [`hero_anim`] is playing — a change triggers the cross-fade.
#[derive(Clone, Copy, PartialEq, Eq, Default)]
pub(crate) enum Clip {
    #[default]
    Loco,
    Air,
    Attack(u8),
    Charge,
    Dash,
    Roll,
    Victory,
}

#[derive(Default)]
pub struct ClipBlend {
    clip: Clip,
    last: Option<Pose>,
    /// (pose to fade from, start time, duration).
    from: Option<(Pose, f32, f32)>,
    /// The airborne clip leads with the right leg (mirrored) this jump.
    lead_right: bool,
}

/// Draw/sheathe bookkeeping. Drawing for a fight that's coming (a foe ringed, blows traded)
/// plays the over-the-shoulder reach; an action straight from the slung carry (a swing, a block)
/// draws instantly so combat never waits on a flourish. Sheathing waits until things have been
/// calm for a moment (sooner when sprinting away).
#[derive(Default)]
pub struct Sheath {
    drawn: bool,
    /// Smoothed 0..1 of `drawn`, for the gait's arm carry.
    armed: f32,
    /// Progress (s) of a draw/sheathe reach in flight, and whether it ends drawn.
    reach_t: Option<f32>,
    to_drawn: bool,
    calm_for: f32,
}

const SHEATHE_REACH: f32 = 0.55;
const SHEATHE_DELAY: f32 = 1.6;
const SHEATHE_DELAY_SPRINT: f32 = 0.4;

impl Sheath {
    fn update(&mut self, dt: f32, want: bool, action: bool, sprinting: bool) {
        self.calm_for = if want { 0.0 } else { self.calm_for + dt };
        if want && action && (!self.drawn || self.reach_t.is_some()) {
            // Straight into a swing/block: the blade is simply in hand.
            self.drawn = true;
            self.reach_t = None;
        } else if self.reach_t.is_none() {
            let delay = if sprinting { SHEATHE_DELAY_SPRINT } else { SHEATHE_DELAY };
            if want && !self.drawn {
                (self.reach_t, self.to_drawn) = (Some(0.0), true);
            } else if !want && self.drawn && self.calm_for > delay {
                (self.reach_t, self.to_drawn) = (Some(0.0), false);
            }
        } else if want && !self.to_drawn {
            // Trouble mid-sheathe: keep the blade out.
            self.drawn = true;
            self.reach_t = None;
        }
        if let Some(t) = self.reach_t.as_mut() {
            *t += dt;
            if *t >= 0.5 * SHEATHE_REACH {
                self.drawn = self.to_drawn; // hand at the hilt: swap
            }
            if *t >= SHEATHE_REACH {
                self.reach_t = None;
            }
        }
        let target = if self.drawn { 1.0 } else { 0.0 };
        self.armed += (target - self.armed) * (dt * 8.0).min(1.0);
    }

    /// 0→1→0 weight of the reach in flight.
    fn reach(&self) -> Option<f32> {
        self.reach_t.map(|t| (PI * (t / SHEATHE_REACH).clamp(0.0, 1.0)).sin())
    }
}

/// The shield's sling: on the arm normally, swung onto the back once a sprint is under way (so
/// both arms can run), and back onto the arm when the sprint ends. A fight (any action, or the
/// sword drawn) puts it straight on the arm. The swap plays a reach over the left shoulder.
#[derive(Default)]
pub struct ShieldSling {
    on_back: bool,
    /// Smoothed 0..1 of `on_back`, for the gait's shield-arm carry.
    back: f32,
    reach_t: Option<f32>,
    to_back: bool,
    want_for: f32,
    calm_for: f32,
}

const SLING_REACH: f32 = 0.5;
/// Sprint held this long before the shield goes onto the back / ended this long before it returns.
const SLING_DELAY: f32 = 0.12;
const UNSLING_DELAY: f32 = 0.45;

impl ShieldSling {
    fn update(&mut self, dt: f32, sprinting: bool, fight: bool) {
        (self.want_for, self.calm_for) = if sprinting && !fight { (self.want_for + dt, 0.0) } else { (0.0, self.calm_for + dt) };
        if fight && (self.on_back || self.reach_t.is_some()) {
            // A swing / block / draw: the board is simply on the arm.
            self.on_back = false;
            self.reach_t = None;
        } else if self.reach_t.is_none() {
            if !self.on_back && self.want_for > SLING_DELAY {
                (self.reach_t, self.to_back) = (Some(0.0), true);
            } else if self.on_back && self.calm_for > UNSLING_DELAY {
                (self.reach_t, self.to_back) = (Some(0.0), false);
            }
        }
        if let Some(t) = self.reach_t.as_mut() {
            *t += dt;
            if *t >= 0.5 * SLING_REACH {
                self.on_back = self.to_back; // hand at the shoulder: swap
            }
            if *t >= SLING_REACH {
                self.reach_t = None;
            }
        }
        let target = if self.on_back { 1.0 } else { 0.0 };
        self.back += (target - self.back) * (dt * 8.0).min(1.0);
    }

    fn reach(&self) -> Option<f32> {
        self.reach_t.map(|t| (PI * (t / SLING_REACH).clamp(0.0, 1.0)).sin())
    }
}

/// Swap the two legs of a pose (the clips here are sagittal X turns, so a straight swap mirrors).
fn mirror_legs(p: &Pose) -> Pose {
    let mut m = *p;
    (m.hip_l, m.hip_r) = (p.hip_r, p.hip_l);
    (m.knee_l, m.knee_r) = (p.knee_r, p.knee_l);
    (m.foot_l, m.foot_r) = (p.foot_r, p.foot_l);
    m
}

pub fn hero_anim(
    time: Res<Time>,
    player: Res<super::PlayerRes>,
    dir: Res<crate::cinematic::DirectorState>,
    mut hero_q: Query<(&mut Hero, &HeroHealth)>,
    mut parts: Query<(&HeroPart, &mut Transform)>,
    // Edge-detect touchdown (was airborne, now grounded) to stamp a short landing-squash window.
    mut was_air: Local<bool>,
    mut land_at: Local<f32>,
    // Smoothed block weight (0 = open, 1 = full defend) so the brace eases in/out.
    mut block_amt: Local<f32>,
    // Clip cross-fade: the last pose written, the clip it came from, and an in-flight fade.
    mut blend: Local<ClipBlend>,
    // Sword in hand vs. slung on the back (+ the draw/sheathe reach in flight).
    mut sheath: Local<Sheath>,
    // Shield on the arm vs. slung on the back for a sprint.
    mut sling: Local<ShieldSling>,
    mut sword_vis: Query<(&HeroPart, &mut Visibility), (Without<super::BackSword>, Without<super::BackShield>)>,
    mut back_vis: Query<&mut Visibility, (With<super::BackSword>, Without<HeroPart>, Without<super::BackShield>)>,
    mut back_shield_vis: Query<&mut Visibility, (With<super::BackShield>, Without<HeroPart>, Without<super::BackSword>)>,
) {
    let Ok((mut hero_mut, hh)) = hero_q.single_mut() else { return };
    let now = time.elapsed_secs();
    let dt = time.delta_secs();

    // Touchdown edge → arm the landing squash (before the early-returns so it's always stamped).
    if *was_air && hero_mut.on_ground {
        *land_at = now;
    }
    *was_air = !hero_mut.on_ground;

    // Slain: let the limbs go slack while the body keels over (root rotation owned by health.rs).
    if !player.0.is_alive() {
        for (part, mut tf) in &mut parts {
            tf.rotation = match part.joint {
                Joint::Hips => {
                    tf.translation = Vec3::new(0.0, super::model::HIP_REST_Y, 0.0);
                    Quat::IDENTITY
                }
                Joint::ShoulderL => e3(0.2, 0.0, -0.2),
                Joint::ShoulderR => e3(0.2, 0.0, 0.2),
                Joint::ElbowL | Joint::ElbowR => rx(-0.3),
                Joint::Shield => shield_rest_r(),
                Joint::Sword => sword_rest_r(),
                _ => Quat::IDENTITY,
            };
        }
        return;
    }

    // Ease the block weight toward its target each frame (≈0.15s settle, ~the studio 0.22 ENTER).
    let block_target = if hh.blocking { 1.0 } else { 0.0 };
    *block_amt += (block_target - *block_amt) * (dt * 10.0).min(1.0);
    let block_amt = block_amt.clamp(0.0, 1.0);

    // ── Sword: drawn for a fight, slung on the back otherwise ──
    let action = hero_mut.attacking || hh.blocking || hero_mut.charge_t >= 0.0 || hero_mut.dash_t >= 0.0;
    // Holding Shift in a fight (no swing / block under way) puts the weapons away so the hero can
    // run: no sprinting with sword and shield drawn.
    let fight = hero_mut.soft_pos.is_some() || now < hero_mut.combat_until;
    let want_drawn = action || hero_mut.victory || (fight && !hero_mut.sprint_held);
    sheath.update(dt, want_drawn, action, hero_mut.sprint_held);
    hero_mut.weapons_drawn = sheath.drawn;
    let hero: &Hero = &hero_mut;
    // The shield goes onto the back once the hero is actually running fast.
    sling.update(dt, hero.gait_speed > super::SPEED * 1.6 && hero.on_ground, action || sheath.drawn);
    for (part, mut vis) in &mut sword_vis {
        if part.joint == Joint::Sword {
            vis.set_if_neq(if sheath.drawn { Visibility::Inherited } else { Visibility::Hidden });
        } else if part.joint == Joint::Shield {
            vis.set_if_neq(if sling.on_back { Visibility::Hidden } else { Visibility::Inherited });
        }
    }
    for mut vis in &mut back_vis {
        vis.set_if_neq(if sheath.drawn { Visibility::Hidden } else { Visibility::Inherited });
    }
    for mut vis in &mut back_shield_vis {
        vis.set_if_neq(if sling.on_back { Visibility::Inherited } else { Visibility::Hidden });
    }
    let armed = sheath.armed;

    let attack = hero.attacking.then(|| attack_phase((hero.attack_t / hero.attack_dur).clamp(0.0, 1.0)));
    let gesture = dir.gesture.map(|g| gesture_pose(g, now - dir.gesture_start));

    // Pick the active clip. Actions now LAYER over locomotion so combined moves read right: swinging
    // while running keeps the legs striding (a running attack), and a jump taken at speed becomes a
    // forward leap. (Priority: victory › attack › jump › block-blended locomotion.)
    let moving = hero.moving_amt.clamp(0.0, 1.0);

    // Combat stance feeds two extra locomotion axes (backpedal blend + pelvis-vs-torso twist);
    // both are 0 out of the stance, where this reduces exactly to the footman locomotion. The
    // guard overlay then colours ALL stance locomotion (idle/walk/run) into the ready-to-fight
    // carry — knees bent, shield up, blade at the ready.
    let loco = {
        let mut p = stance_loco_pose(
            now,
            hero.walk_phase,
            moving,
            hero.gait_speed,
            hero.back_amt,
            hero.strafe_twist,
            armed,
            sling.back,
        );
        guard_overlay(&mut p, hero.stance_amt, moving);
        p
    };
    // ── Clip cross-fade ── Each clip below is continuous within itself, but switching between
    // them (stride → jump at take-off, jump → stride on landing, a swing starting mid-run, the
    // dash/charge entering) used to SNAP the whole rig in one frame. On a clip change, freeze the
    // last written pose and ease from it into the new clip over a short, per-transition window.
    let clip = if hero.victory {
        Clip::Victory
    } else if hero.roll_t >= 0.0 {
        Clip::Roll
    } else if hero.dash_t >= 0.0 {
        Clip::Dash
    } else if hero.attacking {
        Clip::Attack(hero.attack_variant)
    } else if hero.charge_t > CHARGE_GRACE && hero.on_ground {
        Clip::Charge
    } else if !hero.on_ground {
        Clip::Air
    } else {
        Clip::Loco
    };
    if clip == Clip::Air && blend.clip != Clip::Air {
        // Take-off: the leg in its swing (not the planted one) drives up into the leap.
        let g = gait_at(hero.gait_speed / hero_model_scale());
        let u_l = (hero.walk_phase / std::f32::consts::TAU).rem_euclid(1.0);
        blend.lead_right = moving > 0.05 && u_l < g.duty;
    }
    let pose = if hero.victory {
        victory_pose(now)
    } else if hero.roll_t >= 0.0 {
        // Dodge roll: fold into the tuck through the somersault's core, unfolding at both ends so
        // the dive-in / stand-up carry the transition (the root owns the actual tumble).
        let u = (hero.roll_t / super::movement::ROLL_TIME).clamp(0.0, 1.0);
        let w = smoothstep(u / 0.15) * smoothstep((1.0 - u) / 0.18);
        loco.lerp(&roll_pose(), w)
    } else if hero.dash_t >= 0.0 {
        // Sand Dash slide: play the dash-swipe lunge, easing back into locomotion at the blink's tail.
        let p = (hero.dash_t / super::movement::DASH_TIME).clamp(0.0, 1.0);
        let tail = smoothstep((p - 0.7) / 0.3);
        dash_pose(p).lerp(&loco, tail)
    } else if let Some((phase, p)) = &attack {
        let atk = attack_pose(hero.attack_variant, phase, *p);
        if hero.on_ground && moving > 0.05 {
            action_over_loco(&atk, &loco, moving) // running / walking attack
        } else {
            atk
        }
    } else if hero.charge_t > CHARGE_GRACE && hero.on_ground {
        // Holding a Heavy Strike (the light swing has finished): coil into the overhead wind-up,
        // deepening as the bar fills. Layers over locomotion so you can creep while charging.
        let frac = (hero.charge_t / CHARGE_THRESHOLD).clamp(0.0, 1.0);
        let st = charge_stance(frac, (now * 22.0).sin());
        if moving > 0.05 {
            action_over_loco(&st, &loco, moving)
        } else {
            st
        }
    } else if !hero.on_ground {
        let j = jump_pose(hero.vel_y);
        let j = if moving > 0.05 {
            j.lerp(&leap_pose(hero.vel_y), moving) // running leap
        } else {
            j
        };
        // Lead with whichever leg was swinging forward at take-off, so a running jump continues
        // the stride instead of swapping legs mid-air.
        if blend.lead_right { mirror_legs(&j) } else { j }
    } else if block_amt > 0.001 {
        brace(&loco, &defend_pose(now), block_amt, moving)
    } else {
        loco
    };

    if clip != blend.clip {
        let dur = match (blend.clip, clip) {
            (_, Clip::Attack(_)) | (_, Clip::Dash) => 0.07, // actions must stay snappy
            (Clip::Air, Clip::Loco) => 0.09,                 // landing (the squash carries the rest)
            (Clip::Loco, Clip::Air) => 0.12,                 // take-off into the jump/leap
            (_, Clip::Victory) => 0.3,
            _ => 0.14,
        };
        if let Some(last) = blend.last {
            blend.from = Some((last, now, dur));
        }
        blend.clip = clip;
    }
    let pose = match blend.from {
        Some((from, start, dur)) if now - start < dur => from.lerp(&pose, smoothstep((now - start) / dur)),
        _ => {
            blend.from = None;
            pose
        }
    };
    blend.last = Some(pose);
    // The draw/sheathe reach: the sword hand goes up over the right shoulder to the slung hilt
    // and back (the swap happens at the top, in `Sheath::update`).
    let pose = match sheath.reach() {
        Some(w) => {
            let mut p = pose;
            // Fist at the slung grip just under the crossguard (tuned against the viewer).
            p.sh_r = p.sh_r.lerp(Jp::r(e3(-3.1, -0.4, 0.3)), w);
            p.el_r = p.el_r.lerp(Jp::r(rx(-2.0)), w);
            p.head = Jp::r(p.head.r * e3(0.0, -0.25 * w, 0.0)); // a glance at the hand
            p.torso = Jp::r(p.torso.r * e3(-0.05 * w, -0.15 * w, 0.0));
            p
        }
        None => pose,
    };
    let pose = match sling.reach() {
        Some(w) => {
            let mut p = pose;
            // Shield hand up over the left shoulder to the sling (mirror of the sword reach).
            p.sh_l = p.sh_l.lerp(Jp::r(e3(-3.0, 0.4, -0.3)), w);
            p.el_l = p.el_l.lerp(Jp::r(rx(-1.9)), w);
            p.torso = Jp::r(p.torso.r * e3(-0.04 * w, 0.12 * w, 0.0));
            p
        }
        None => pose,
    };

    // Landing squash: a quick crouch the instant the feet hit, easing back over `LAND_RECOVER`.
    let landing = if *land_at <= 0.0 {
        0.0 // no touchdown yet (fresh boot) — don't play an unearned landing crouch
    } else {
        let u = (1.0 - (now - *land_at) / LAND_RECOVER).clamp(0.0, 1.0);
        u * u
    };

    for (part, mut tf) in &mut parts {
        let mut jp = pose.get(part.joint);
        // Only the gait slides the shoulder girdle; every other clip leaves the shoulders' `t`
        // unset, so pin them back to the bind offset instead of keeping the last stride's.
        if jp.t.is_none() && matches!(part.joint, Joint::ShoulderL | Joint::ShoulderR) {
            let rig = super::footman::leg_rig();
            jp.t = Some(if part.joint == Joint::ShoulderL { rig.shoulder } else { rig.shoulder_r });
        }
        if let Some(t) = jp.t {
            // Clips were authored when the hips sat at y = 1.05. The footman's hips are at
            // `HIP_REST_Y` (0.98); shift every absolute hip height by the same delta so crouches
            // keep their depth and the feet stay on the ground.
            tf.translation = if part.joint == Joint::Hips {
                Vec3::new(t.x, t.y + (super::model::HIP_REST_Y - 1.05), t.z)
            } else {
                t
            };
        }
        let mut rot = jp.r;

        // Arm overrides: the Director's staged gesture wins on the arms; otherwise the combat /
        // locomotion clip already in `rot` plays. (First person hides this rig entirely — see
        // `camera::fp_body_visibility` / `viewmodel` — so nothing here is FP-aware.)
        match part.joint {
            Joint::ShoulderR | Joint::ElbowR => {
                if let Some((Some((sh, el)), _)) = gesture {
                    rot = if part.joint == Joint::ElbowR { el } else { sh };
                }
            }
            Joint::ShoulderL | Joint::ElbowL => {
                if let Some((_, Some((sh, el)))) = gesture {
                    rot = if part.joint == Joint::ElbowL { el } else { sh };
                }
            }
            _ => {}
        }
        tf.rotation = rot;

        // Landing squash folded over the locomotion pose right after touchdown (studio positive-knee
        // crouch: hips dip, knees bend, thighs settle back, feet flatten, torso leans in).
        if landing > 0.0 && attack.is_none() && hero.on_ground {
            match part.joint {
                Joint::Hips => tf.translation.y -= 0.12 * landing,
                Joint::KneeL | Joint::KneeR => tf.rotation *= rx(0.9 * landing),
                Joint::HipL | Joint::HipR => tf.rotation *= rx(-0.35 * landing),
                Joint::FootL | Joint::FootR => tf.rotation *= rx(0.4 * landing),
                Joint::Torso => tf.rotation *= rx(0.25 * landing),
                // Arms throw down to absorb the impact, then spring back as `landing` decays.
                Joint::ShoulderL | Joint::ShoulderR => tf.rotation *= rx(0.3 * landing),
                Joint::ElbowL | Joint::ElbowR => tf.rotation *= rx(-0.25 * landing),
                _ => {}
            }
        }
    }
}

/// Staged-gesture arm poses (Director). Returns `(right, left)`, each `Some((shoulder, elbow))` or
/// `None` to leave that arm on its normal animation. `ph` = seconds since the gesture began. Right
/// is the sword arm, left the shield arm. Rough by design — eyeball + nudge against a capture.
fn gesture_pose(g: crate::cinematic::HeroGesture, ph: f32) -> (Option<(Quat, Quat)>, Option<(Quat, Quat)>) {
    use crate::cinematic::HeroGesture::*;
    let raise = (ph / 0.45).clamp(0.0, 1.0);
    let e = raise * raise * (3.0 - 2.0 * raise); // smoothstep
    match g {
        Wave => (Some((e3(-2.55 * e, 0.0, 0.20 + (ph * 5.0).sin() * 0.45 * e), rx(-0.5))), None),
        Salute => (Some((e3(-2.6 * e, 0.0, 0.85 * e), rx(-0.2))), None),
        Point => (Some((e3(-1.6 * e, 0.0, 0.05), rx(-0.1))), None),
        ArmsCrossed => (
            Some((e3(-1.15 * e, 0.0, 0.85 * e), rx(-1.4))),
            Some((e3(-1.15 * e, 0.0, -0.85 * e), rx(-1.4))),
        ),
        Cheer => {
            let pump = (ph * 4.0).sin() * 0.15;
            (
                Some((e3((-2.75 + pump) * e, 0.0, -0.35 * e), rx(-0.3))),
                Some((e3((-2.75 + pump) * e, 0.0, 0.35 * e), rx(-0.3))),
            )
        }
        // A looping chop — the "at work" gesture (villager-staging cinematics).
        Work => {
            let chop = ((ph.max(0.0) * 1.3).fract() * PI).sin();
            (Some((e3(-1.2 - chop * 0.5, 0.0, 0.1), rx(-0.6 + chop * 0.3))), None)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Forward kinematics of one posed leg (rig space, ground at y = 0): (ankle, boot rotation).
    fn ankle(p: &Pose, right: bool) -> (Vec3, Quat) {
        let rig = super::super::footman::leg_rig();
        let (hip, knee, foot) = if right {
            (p.hip_r, p.knee_r, p.foot_r)
        } else {
            (p.hip_l, p.knee_l, p.foot_l)
        };
        let mirror = |v: Vec3| if right { Vec3::new(-v.x, v.y, v.z) } else { v };
        let hip_rotation = p.hips.r * hip.r;
        let knee_rotation = hip_rotation * knee.r;
        let foot_rotation = knee_rotation * foot.r;
        let hips = p.hips.t.unwrap() + Vec3::Y * (super::super::model::HIP_REST_Y - 1.05);
        let ankle = hips + p.hips.r * mirror(rig.hip)
            + hip_rotation * mirror(rig.knee) + knee_rotation * mirror(rig.foot);
        (ankle, foot_rotation)
    }

    /// The boot's heel and toe contact points.
    fn heel_toe(p: &Pose, right: bool) -> (Vec3, Vec3) {
        let rig = super::super::footman::leg_rig();
        let (a, r) = ankle(p, right);
        let h = rig.ankle_height;
        (a + r * Vec3::new(0.0, -h, -rig.heel), a + r * Vec3::new(0.0, -h, rig.toe))
    }

    #[test]
    #[ignore]
    fn dump_run_cycle() {
        let rig = super::super::footman::leg_rig();
        for (e, h) in super::super::footman::arm_bind() {
            println!("arm bind: upper {e:?} fore {h:?} elbow flex {:.1} deg", e.angle_between(h).to_degrees());
        }
        println!("rig thigh {} shin {} ankle_h {} toe {} heel {} hip {:?} scale {}", rig.knee.length(), rig.foot.length(), rig.ankle_height, rig.toe, rig.heel, rig.hip, hero_model_scale());
        for v in [4.4_f32, 5.04] {
            let g = gait_at(v / hero_model_scale());
            println!("v={v} run={} sprint={} duty={} sweep={} steps/s={}", g.run, g.sprint, g.duty, g.sweep, gait_phase_rate(v) / PI);
            for i in 0..40 {
                let ph = TAU * i as f32 / 40.0;
                let p = footman_gait(ph, v, 0.0, 1.0);
                let (lh, lt) = heel_toe(&p, false);
                let (rh, rt) = heel_toe(&p, true);
                let ang = |hip: &Jp, knee: &Jp| {
                    let h = p.hips.r * hip.r;
                    let th = h * Vec3::NEG_Y;
                    let sh = h * knee.r * Vec3::NEG_Y;
                    (th.z.atan2(-th.y).to_degrees(), th.angle_between(sh).to_degrees())
                };
                let arm = |sh: &Jp, el: &Jp, bind: (Vec3, Vec3)| {
                    let t = p.hips.r * p.torso.r * sh.r;
                    let up = t * bind.0;
                    let fore = t * el.r * bind.1;
                    (up.z.atan2(-up.y).to_degrees(), fore.z.atan2(-fore.y).to_degrees())
                };
                let ab = super::super::footman::arm_bind();
                let (ru, rf) = arm(&p.sh_r, &p.el_r, ab[0]);
                let (lu, lf) = arm(&p.sh_l, &p.el_l, ab[1]);
                if i % 4 == 0 { println!("   arms: R upper {ru:.0} fore {rf:.0} | L upper {lu:.0} fore {lf:.0}"); }
                let (tl, kl) = ang(&p.hip_l, &p.knee_l);
                let (tr, kr) = ang(&p.hip_r, &p.knee_r);
                println!("u={:.3} hips_y={:.3} L low={:.3} z={:.3} th={tl:.0} kn={kl:.0}  R low={:.3} z={:.3} th={tr:.0} kn={kr:.0}", i as f32 / 40.0, p.hips.t.unwrap().y, lh.y.min(lt.y), lh.z, rh.y.min(rt.y), rh.z);
            }
        }
    }

    /// World ground speeds spanning a creep, a walk, the base jog and the sprint.
    const SPEEDS: [f32; 7] = [0.5, 1.4, 2.4, 3.5, 4.4, 6.125, 7.0];

    #[test]
    fn footman_boots_stay_grounded_through_every_gait() {
        for v in SPEEDS {
            let g = gait_at(v / hero_model_scale());
            let mut max_lift = 0.0_f32;
            for frame in 0..240 {
                let phase = std::f32::consts::TAU * frame as f32 / 240.0;
                let p = footman_gait(phase, v, 1.0, 0.0);
                for right in [false, true] {
                    let u = (phase / std::f32::consts::TAU + if right { 0.5 } else { 0.0 }).rem_euclid(1.0);
                    let (heel, toe) = heel_toe(&p, right);
                    let low = heel.y.min(toe.y);
                    assert!(low >= -0.02, "boot penetrates ground: v={v}, u={u}, y={low}");
                    if u < g.duty {
                        assert!(low.abs() <= 0.02, "planted boot floats: v={v}, u={u}, y={low}");
                    }
                    max_lift = max_lift.max(low);
                }
            }
            assert!(max_lift > 0.04, "recovery foot must lift, not skate (v={v})");
        }
    }

    /// The moonwalk regression: while a boot is planted, its contact edge must stay put on the
    /// ground as the body travels — the rig-space sweep cancels the root's real speed.
    #[test]
    fn planted_boot_does_not_skate() {
        for v in SPEEDS {
            let vm = v / hero_model_scale();
            let g = gait_at(vm);
            let rate = gait_phase_rate(v);
            let dt = 1.0 / 240.0;
            for frame in 0..200 {
                let phase = std::f32::consts::TAU * frame as f32 / 200.0;
                for right in [false, true] {
                    let u = (phase / std::f32::consts::TAU + if right { 0.5 } else { 0.0 }).rem_euclid(1.0);
                    let u2 = u + rate * dt / std::f32::consts::TAU;
                    if u < 0.02 || u2 > g.duty - 0.02 {
                        continue; // the touchdown / lift-off frames themselves
                    }
                    let a = heel_toe(&footman_gait(phase, v, 1.0, 0.0), right);
                    let b = heel_toe(&footman_gait(phase + rate * dt, v, 1.0, 0.0), right);
                    // Whichever edge carries the weight (the lower one; both when flat).
                    let (pa, pb) = if a.0.y <= a.1.y { (a.0, b.0) } else { (a.1, b.1) };
                    let slip = (pb.z - pa.z) / dt + vm;
                    assert!(slip.abs() < 0.06 * vm + 0.05, "planted boot skates: v={v}, u={u}, slip={slip} m/s of {vm}");
                    // …nor shuffle sideways with the pelvis sway (the "wobbly on its legs" read).
                    let side = (pb.x - pa.x) / dt;
                    assert!(side.abs() < 0.08, "planted boot shuffles sideways: v={v}, u={u}, {side} m/s");
                }
            }
        }
    }

    /// Swing-leg joint angles stay inside human running ranges (the ankle-path IK once swung the
    /// sprinting thigh to 136° and folded the knee to 154°).
    #[test]
    fn swing_joint_angles_stay_human() {
        for (v, hip_max, knee_max) in [(1.4_f32, 40.0_f32, 75.0_f32), (3.5, 55.0, 105.0), (6.125, 75.0, 132.0)] {
            let (mut hi, mut kn) = (0.0_f32, 0.0_f32);
            for i in 0..200 {
                let p = footman_gait(std::f32::consts::TAU * i as f32 / 200.0, v, 0.0, 1.0);
                let hip = p.hips.r * p.hip_l.r;
                let thigh = hip * Vec3::NEG_Y;
                let shin = hip * p.knee_l.r * Vec3::NEG_Y;
                hi = hi.max(thigh.z.atan2(-thigh.y).to_degrees());
                kn = kn.max(thigh.angle_between(shin).to_degrees());
            }
            assert!(hi < hip_max && hi > 0.5 * hip_max, "v={v}: peak hip flexion {hi}°");
            assert!(kn < knee_max && kn > 0.5 * knee_max, "v={v}: peak knee flexion {kn}°");
        }
    }

    #[test]
    fn sword_draws_for_a_fight_and_slings_when_calm() {
        let dt = 1.0 / 60.0;
        let mut sh = Sheath::default();
        assert!(!sh.drawn);
        // A swing from the slung carry: in hand at once, no reach flourish.
        sh.update(dt, true, true, false);
        assert!(sh.drawn && sh.reach().is_none());
        // Calm: stays out through the delay, then the reach slings it at its midpoint.
        let mut t = 0.0;
        while sh.drawn {
            sh.update(dt, false, false, false);
            t += dt;
            assert!(t < SHEATHE_DELAY + SHEATHE_REACH, "never sheathed");
        }
        assert!(t > SHEATHE_DELAY, "sheathed mid-fight");
        // A foe ringed (no action yet): drawn via the reach.
        for _ in 0..60 {
            sh.update(dt, false, false, false);
        }
        sh.update(dt, true, false, false);
        assert!(!sh.drawn && sh.reach().is_some());
        for _ in 0..60 {
            sh.update(dt, true, false, false);
        }
        assert!(sh.drawn && sh.reach().is_none());
        // Sprinting away slings it sooner.
        let mut t = 0.0;
        while sh.drawn {
            sh.update(dt, false, false, true);
            t += dt;
        }
        assert!(t < SHEATHE_DELAY);
    }

    #[test]
    fn shield_slings_for_a_sprint_and_returns_for_a_fight() {
        let dt = 1.0 / 60.0;
        let mut sl = ShieldSling::default();
        // Sprinting: onto the back after the short delay and the reach.
        let mut t = 0.0;
        while !sl.on_back {
            sl.update(dt, true, false);
            t += dt;
            assert!(t < SLING_DELAY + SLING_REACH, "never slung");
        }
        assert!(t > SLING_DELAY, "slung before the sprint was under way");
        // A swing / block mid-sprint: straight onto the arm, no reach.
        for _ in 0..30 {
            sl.update(dt, true, false);
        }
        sl.update(dt, true, true);
        assert!(!sl.on_back && sl.reach().is_none());
        // Sprint again, then stop: it comes back to the arm after the calm delay.
        for _ in 0..60 {
            sl.update(dt, true, false);
        }
        assert!(sl.on_back);
        let mut t = 0.0;
        while sl.on_back {
            sl.update(dt, false, false);
            t += dt;
            assert!(t < UNSLING_DELAY + SLING_REACH, "never unslung");
        }
        assert!(t > UNSLING_DELAY);
    }

    #[test]
    fn cadence_reads_human() {
        let steps = |v: f32| gait_phase_rate(v) / PI; // two steps per 2π
        let walk = steps(super::super::SPEED);
        assert!((1.8..2.6).contains(&walk), "walk cadence {walk}");
        let jog = steps(3.2);
        assert!((2.6..3.6).contains(&jog) && jog > walk, "jog cadence {jog}");
        let sprint = steps(super::super::SPEED * super::super::SPRINT_MULT);
        assert!((3.0..4.6).contains(&sprint) && sprint > jog, "sprint cadence {sprint}");
        assert_eq!(gait_phase_rate(0.0), 0.0);
    }

    #[test]
    fn footman_gait_is_periodic_and_blends_back_to_idle() {
        for v in SPEEDS {
            let a = footman_gait(0.0, v, 1.0, 0.0);
            let b = footman_gait(std::f32::consts::TAU, v, 1.0, 0.0);
            for j in [Joint::Hips, Joint::Torso, Joint::ShoulderR, Joint::HipL, Joint::HipR, Joint::KneeL, Joint::KneeR, Joint::FootL, Joint::FootR] {
                let d = a.get(j).r.angle_between(b.get(j).r);
                assert!(d < 0.002, "gait not periodic at v={v}: joint {} off by {d}", j as u8);
            }
            let stopped = stance_loco_pose(2.0, 1.7, 0.0, v, 0.0, 0.0, 1.0, 0.0);
            let idle = idle_pose(2.0);
            assert!(stopped.hips.t.unwrap().distance(idle.hips.t.unwrap()) < 0.0001);
            assert!(stopped.knee_l.r.angle_between(idle.knee_l.r) < 0.001);
        }
    }

    /// Opposite arm to the forward leg — the old gait swung the sword arm WITH the same-side leg.
    #[test]
    fn arms_counter_swing_the_legs() {
        for v in SPEEDS {
            // Left heel strike: left boot out front → right (sword) arm forward (negative X).
            let p = footman_gait(0.0, v, 1.0, 0.0);
            assert!(heel_toe(&p, false).0.z > heel_toe(&p, true).0.z);
            let fwd = |q: Quat| (q * Vec3::NEG_Y).z;
            assert!(fwd(p.sh_r.r) > fwd(p.sh_l.r), "sword arm must lead with the left leg (v={v})");
        }
    }

    #[test]
    fn combat_guard_preserves_moving_footman_support() {
        for back in [0.0, 1.0] {
            for twist in [-0.7, 0.0, 0.7] {
                for frame in 0..120 {
                    let phase = std::f32::consts::TAU * frame as f32 / 120.0;
                    let mut p = stance_loco_pose(2.0, phase, 1.0, 2.6, back, twist, 1.0, 0.0);
                    guard_overlay(&mut p, 1.0, 1.0);
                    for right in [false, true] {
                        let (heel, toe) = heel_toe(&p, right);
                        assert!(heel.y.min(toe.y) >= -0.02, "guard must not drive the moving boot into the ground");
                    }
                }
            }
        }
    }
}
