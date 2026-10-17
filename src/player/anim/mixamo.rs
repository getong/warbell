//! The hero's walk, run, jump and dodge roll on Mixamo clips (`mixamo_clips`, baked by
//! `tools/mixamo_retarget/bake.py` from Mixamo's Walking / Running / Jump / Dive Roll).
//!
//! Same recipe as the sword combo ([`super::swordplay`]): the clips are rig-free targets (pelvis and
//! ankle positions in leg lengths, world-delta rotations, the limbs as directions), solved onto the
//! footman with two-bone IK, so his own proportions and armour sit on the motion. What is new here:
//!
//! - **walk / run** are in-place loops played at the speed the ground goes by: the planted boot sweeps
//!   back at `native speed × playback rate`, so choosing the rate = ground speed / native speed pins
//!   it to the ground (no skating). Both loops start on the left heel strike, so one phase drives
//!   either, and the two blend by speed.
//! - **jump** plays the clip's airborne stretch against the real vertical speed (physics owns the
//!   height; the clip only folds the limbs).
//! - **roll** plays the dive-roll's body shape (pelvis frame) through the somersault the root performs.

use std::f32::consts::TAU;

use bevy::prelude::*;

use super::mixamo_clips as mc;
use super::swordplay::{aim_leg, Frame};
use super::{aim_arm, e3, rest, rx, shield_gait_r, smoothstep, sword_rest_r, Jp, Pose, SHIELD_GAIT_T};

/// Model m/s below which the gait is the walk loop, and above which it is the run loop (blended between).
const WALK_TO: f32 = 2.3;
const RUN_FROM: f32 = 3.6;

fn leg_len() -> f32 {
    let rig = super::super::footman::leg_rig();
    rig.knee.length() + rig.foot.length()
}

/// 0 = the walk loop … 1 = the run loop, at a ground speed of `v` model m/s.
pub(super) fn run_weight(v: f32) -> f32 {
    smoothstep((v - WALK_TO) / (RUN_FROM - WALK_TO))
}

/// Gait-phase advance (rad/s) at `v` model m/s: the foot-lock contract. A loop of `n` frames whose
/// stance boot sweeps back at `native` leg-lengths/s plays at `v / (native × leg)` of its own speed.
pub(super) fn phase_rate(v: f32) -> f32 {
    let l = leg_len();
    let cps = |native: f32, n: usize| v / (native * l) * mc::FPS / n as f32;
    let w = run_weight(v);
    TAU * (cps(mc::WALK_SPEED, mc::WALK.len()) * (1.0 - w) + cps(mc::RUN_SPEED, mc::RUN.len()) * w)
}

/// A looping clip at cycle phase `u` (0..1), Catmull-Rom between the baked keys.
fn sample_loop(clip: &[[f32; 53]], u: f32) -> Frame {
    let n = clip.len() as isize;
    let x = u.rem_euclid(1.0) * n as f32;
    let i = x.floor() as isize;
    let k = |j: isize| Frame::of(&clip[j.rem_euclid(n) as usize]);
    Frame::cubic(&k(i - 1), &k(i), &k(i + 1), &k(i + 2), x - i as f32)
}

/// A one-shot clip at frame position `x` (clamped to its ends).
fn sample_once(clip: &[[f32; 53]], x: f32) -> Frame {
    let n = clip.len() as isize;
    let x = x.clamp(0.0, (n - 1) as f32);
    let i = (x.floor() as isize).min(n - 2);
    let k = |j: isize| Frame::of(&clip[j.clamp(0, n - 1) as usize]);
    Frame::cubic(&k(i - 1), &k(i), &k(i + 1), &k(i + 2), x - i as f32)
}

/// One clip frame solved onto the footman: legs by two-bone IK onto the ankle targets (the boots go
/// where the clip puts them), trunk and head by the clip's own rotations, both arms by [`aim_arm`].
/// The sword and shield joints are left at their carries for the caller to dress.
fn solve(f: &Frame, ground: bool) -> Pose {
    let rig = super::super::footman::leg_rig();
    let tp = Frame::of(&mc::TPOSE);
    let leg_len = leg_len();
    let hip_rest = super::super::model::HIP_REST_Y;
    let mut p = rest();

    let pelvis = f.pelvis_r;
    let d = (f.pelvis - tp.pelvis) * leg_len;
    let mut hips = Vec3::new(0.0, hip_rest, 0.0) + d;

    let mirror = |v: Vec3, right: bool| if right { Vec3::new(-v.x, v.y, v.z) } else { v };
    let ankle_rest = |right: bool| Vec3::new(0.0, hip_rest, 0.0) + mirror(rig.hip + rig.knee + rig.foot, right);
    // On the ground a boot is never let through it: the clip's foot is shorter than the knight's
    // boot, so at toe-off the toe would sink; the ankle rides up by what the boot would dip.
    let clear = |i: usize| {
        let low = [Vec3::new(0.0, -rig.ankle_height, -rig.heel), Vec3::new(0.0, -rig.ankle_height, rig.toe)]
            .into_iter()
            .map(|p| (f.foot[i] * p).y)
            .fold(f32::MAX, f32::min);
        -low
    };
    let target = |i: usize| {
        let mut t = ankle_rest(i == 1) + (f.ankle[i] - tp.ankle[i]) * leg_len;
        if ground {
            t.y = t.y.max(clear(i));
        }
        t
    };
    // Never stretch a leg past its reach: the hips settle onto the straighter one.
    let reach = 0.995 * leg_len;
    for i in 0..2 {
        let h = pelvis * mirror(rig.hip, i == 1);
        let a = target(i);
        let (dx, dz) = (a.x - hips.x - h.x, a.z - hips.z - h.z);
        let cap = a.y + (reach * reach - dx * dx - dz * dz).max(0.0).sqrt() - h.y;
        let k = 0.02;
        let s = (0.5 + 0.5 * (cap - hips.y) / k).clamp(0.0, 1.0);
        hips.y = cap + (hips.y - cap) * s - k * s * (1.0 - s);
    }
    let leg = |i: usize| {
        let right = i == 1;
        let (hb, kb, fb) = (mirror(rig.hip, right), mirror(rig.knee, right), mirror(rig.foot, right));
        let (l1, l2) = (kb.length(), fb.length());
        let h = hips + pelvis * hb;
        let to = target(i) - h;
        let dist = to.length().clamp(1e-3, 0.999 * (l1 + l2));
        let dh = to.normalize_or(Vec3::NEG_Y);
        let ang = ((l1 * l1 + dist * dist - l2 * l2) / (2.0 * l1 * dist)).clamp(-1.0, 1.0).acos();
        let pole = (f.pole[i] - dh * f.pole[i].dot(dh)).normalize_or(Vec3::Z);
        let knee = h + l1 * (ang.cos() * dh + ang.sin() * pole);
        let ankle = h + dh * dist;
        let inv = pelvis.inverse();
        let (hq, kq) = aim_leg(inv * (knee - h), inv * (ankle - knee), (kb, fb));
        let fq = (pelvis * hq * kq).inverse() * f.foot[i];
        (Jp::r(hq), Jp::r(kq), Jp::r(fq))
    };
    (p.hip_l, p.knee_l, p.foot_l) = leg(0);
    (p.hip_r, p.knee_r, p.foot_r) = leg(1);
    p.hips = Jp { t: Some(hips + Vec3::Y * (1.05 - hip_rest)), r: pelvis };

    p.torso = Jp::r(pelvis.inverse() * f.chest);
    p.head = Jp::r(f.chest.inverse() * f.head);

    let ab = super::super::footman::arm_bind();
    let inv = f.chest.inverse();
    let arm = |upper: Vec3, fore: Vec3, bind: (Vec3, Vec3)| aim_arm(inv * upper, inv * fore, upper.angle_between(fore), bind);
    let (sr, er) = arm(f.r_upper, f.r_fore, ab[0]);
    p.sh_r = Jp::r(sr);
    p.el_r = Jp::r(er);
    let (sl, el) = arm(f.l_upper, f.l_fore, ab[1]);
    p.sh_l = Jp::r(sl);
    p.el_l = Jp::r(el);
    p.sword = Jp::r(sword_rest_r());
    p.shield = Jp { t: Some(SHIELD_GAIT_T), r: shield_gait_r() };
    p
}

/// Dress a solved clip pose with the knight's kit: the sword carried (hanging on a walk, shouldered
/// on a run) in the sword hand, the shield held edge-on on the shield arm — which swings only part of
/// the clip's way (a board on the forearm is carried, not pumped) unless it is slung (`shield_back`).
/// `run` 0..1 is the walk → run weight, `armed` whether the blade is in hand.
fn dress(mut p: Pose, run: f32, armed: f32, shield_back: f32) -> Pose {
    let carry_sh = e3(0.04, 0.0, 0.0).slerp(e3(0.08, 0.22, -0.07), run);
    let carry_el = rx(-0.26).slerp(rx(-0.6), run);
    let follow = 0.4 + 0.6 * shield_back;
    p.sh_l = Jp::r(carry_sh.slerp(p.sh_l.r, follow));
    p.el_l = Jp::r(carry_el.slerp(p.el_l.r, follow));
    p.sword = Jp::r(sword_rest_r().slerp(super::posed_sword(-2.046, -0.52, 0.119).r, run * armed));
    // The board stays upright, edge-on along the body: cancel the elbow's pitch on it.
    let (el_x, _, _) = p.el_l.r.to_euler(EulerRot::XYZ);
    let undo = rx(-el_x * (0.4 + 0.5 * run));
    p.shield = Jp { t: Some(undo * SHIELD_GAIT_T), r: undo * shield_gait_r() };
    p
}

/// The hero's foot-locked locomotion at ground speed `v` (model m/s), gait phase `c` (rad; the left
/// heel strikes at 0 and the right at π): the Mixamo walk below a jog, the run above, blended between.
pub(super) fn gait(c: f32, v: f32, armed: f32, shield_back: f32) -> Pose {
    let u = c / TAU;
    let w = run_weight(v);
    let f = if w <= 1e-3 {
        sample_loop(&mc::WALK, u)
    } else if w >= 1.0 - 1e-3 {
        sample_loop(&mc::RUN, u)
    } else {
        sample_loop(&mc::WALK, u).lerp(&sample_loop(&mc::RUN, u), w)
    };
    dress(solve(&f, true), w, armed, shield_back)
}

/// The airborne body for vertical speed `vy` (+ rising): the clip's take-off → landing reach, read
/// off the arc (`jump_speed` up at the take-off … `jump_speed` down at the touchdown).
pub(super) fn jump(vy: f32, jump_speed: f32) -> Pose {
    let p = ((jump_speed - vy) / (2.0 * jump_speed)).clamp(0.0, 1.0);
    let f = sample_once(&mc::JUMP, p * (mc::JUMP.len() - 1) as f32);
    dress(solve(&f, false), 0.5, 1.0, 0.0)
}

/// The somersault's limbs at progress `u` (0..1) through the roll: the dive, the tuck, the landing.
/// The root owns the actual tumble and the pelvis turn, so the hips only sit low over its pivot.
pub(super) fn roll(u: f32) -> Pose {
    let f = sample_once(&mc::ROLL, u.clamp(0.0, 1.0) * (mc::ROLL.len() - 1) as f32);
    let mut p = dress(solve(&f, false), 0.5, 1.0, 0.0);
    p.hips = Jp { t: Some(Vec3::new(0.0, 0.74, 0.0)), r: Quat::IDENTITY };
    p
}
