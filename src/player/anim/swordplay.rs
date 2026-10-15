//! The hero's light sword combo on keyframed clips from Quaternius' Universal Animation Library 2
//! (CC0): `Sword_Regular_A` → `_B` → `_C`, each with its own recovery.
//!
//! The clips are baked (see `ual_sword`) into rig-free targets in our body frame — pelvis and
//! ankle positions in leg lengths, world-delta rotations of the pelvis, chest, head and boots off
//! the source T-pose, and the limbs and the sword hand as directions — so the footman's own
//! proportions solve them here: the legs by two-bone IK onto the scaled ankle targets (the boots
//! plant where the clip plants them), the arms by [`aim_arm`], and the blade by turning the
//! sword joint until our blade lies along the clip's grip.

use bevy::prelude::*;

use super::ual_sword as ual;
use super::{aim_arm, e3, rest, rx, smoothstep, Jp, Pose};

/// One sampled clip frame (see the layout in `ual_sword`).
#[derive(Clone, Copy)]
struct Frame {
    pelvis: Vec3,
    pelvis_r: Quat,
    chest: Quat,
    head: Quat,
    r_upper: Vec3,
    r_fore: Vec3,
    blade: Vec3,
    edge: Vec3,
    l_upper: Vec3,
    l_fore: Vec3,
    ankle: [Vec3; 2],
    pole: [Vec3; 2],
    foot: [Quat; 2],
}

impl Frame {
    fn of(row: &[f32; 53]) -> Frame {
        let v = |i: usize| Vec3::new(row[i], row[i + 1], row[i + 2]);
        let d = |i: usize| v(i).normalize_or(Vec3::NEG_Y);
        let q = |i: usize| Quat::from_xyzw(row[i], row[i + 1], row[i + 2], row[i + 3]).normalize();
        Frame {
            pelvis: v(0),
            pelvis_r: q(3),
            chest: q(7),
            head: q(11),
            r_upper: d(15),
            r_fore: d(18),
            blade: d(21),
            edge: d(24),
            l_upper: d(27),
            l_fore: d(30),
            ankle: [v(33), v(43)],
            pole: [d(36), d(46)],
            foot: [q(39), q(49)],
        }
    }

    /// `self` → `o` by `s` (rotations slerped, directions renormalised).
    fn lerp(&self, o: &Frame, s: f32) -> Frame {
        let dir = |p: Vec3, q: Vec3| p.lerp(q, s).normalize_or(p);
        Frame {
            pelvis: self.pelvis.lerp(o.pelvis, s),
            pelvis_r: self.pelvis_r.slerp(o.pelvis_r, s),
            chest: self.chest.slerp(o.chest, s),
            head: self.head.slerp(o.head, s),
            r_upper: dir(self.r_upper, o.r_upper),
            r_fore: dir(self.r_fore, o.r_fore),
            blade: dir(self.blade, o.blade),
            edge: dir(self.edge, o.edge),
            l_upper: dir(self.l_upper, o.l_upper),
            l_fore: dir(self.l_fore, o.l_fore),
            ankle: [self.ankle[0].lerp(o.ankle[0], s), self.ankle[1].lerp(o.ankle[1], s)],
            pole: [dir(self.pole[0], o.pole[0]), dir(self.pole[1], o.pole[1])],
            foot: [self.foot[0].slerp(o.foot[0], s), self.foot[1].slerp(o.foot[1], s)],
        }
    }
}

/// Uniform Catmull-Rom between `p1` and `p2` (C1 through every key).
fn cr<T>(p0: T, p1: T, p2: T, p3: T, s: f32) -> T
where
    T: Copy + std::ops::Add<Output = T> + std::ops::Sub<Output = T> + std::ops::Mul<f32, Output = T>,
{
    let (s2, s3) = (s * s, s * s * s);
    (p1 * 2.0 + (p2 - p0) * s + (p0 * 2.0 - p1 * 5.0 + p2 * 4.0 - p3) * s2 + (p1 * 3.0 - p0 - p2 * 3.0 + p3) * s3) * 0.5
}

/// [`cr`] on rotations: the neighbours sign-matched to `q1` (same hemisphere), then renormalised.
fn cr_q(q0: Quat, q1: Quat, q2: Quat, q3: Quat, s: f32) -> Quat {
    let v = |q: Quat, r: Quat| if q.dot(r) < 0.0 { -Vec4::from(q) } else { Vec4::from(q) };
    let q2v = v(q2, q1);
    let q3v = v(q3, Quat::from_vec4(q2v));
    Quat::from_vec4(cr(v(q0, q1), Vec4::from(q1), q2v, q3v, s)).normalize()
}

impl Frame {
    /// `b` → `c` by `s` on a Catmull-Rom through `a`, `b`, `c`, `d`.
    fn cubic(a: &Frame, b: &Frame, c: &Frame, d: &Frame, s: f32) -> Frame {
        let p = |f: fn(&Frame) -> Vec3| cr(f(a), f(b), f(c), f(d), s);
        let dir = |f: fn(&Frame) -> Vec3| p(f).normalize_or(f(b));
        let q = |f: fn(&Frame) -> Quat| cr_q(f(a), f(b), f(c), f(d), s);
        Frame {
            pelvis: p(|f| f.pelvis),
            pelvis_r: q(|f| f.pelvis_r),
            chest: q(|f| f.chest),
            head: q(|f| f.head),
            r_upper: dir(|f| f.r_upper),
            r_fore: dir(|f| f.r_fore),
            blade: dir(|f| f.blade),
            edge: dir(|f| f.edge),
            l_upper: dir(|f| f.l_upper),
            l_fore: dir(|f| f.l_fore),
            ankle: [p(|f| f.ankle[0]), p(|f| f.ankle[1])],
            pole: [dir(|f| f.pole[0]), dir(|f| f.pole[1])],
            foot: [q(|f| f.foot[0]), q(|f| f.foot[1])],
        }
    }
}

/// Cubic in time between the baked frames. The clips are keyed at 30 fps and the strike moves the
/// blade up to ~90° a key, so a straight line between keys turned every key into a visible corner
/// (the blade's path and the trunk's spin changing speed in one frame): a Catmull-Rom keeps both
/// the path and its speed continuous, still passing through every authored key.
fn sample(clip: &[[f32; 53]], t: f32) -> Frame {
    let n = clip.len();
    let x = (t.max(0.0) * ual::FPS).min((n - 1) as f32);
    let i = (x.floor() as usize).min(n.saturating_sub(2));
    let k = |j: isize| Frame::of(&clip[j.clamp(0, n as isize - 1) as usize]);
    let i = i as isize;
    Frame::cubic(&k(i - 1), &k(i), &k(i + 1), &k(i + 2), (x - i as f32).clamp(0.0, 1.0))
}

/// Right-handed frame with `a` first and `b` (made orthogonal to it) second.
fn frame(a: Vec3, b: Vec3) -> Mat3 {
    let a = a.normalize();
    let b = (b - a * b.dot(a)).normalize_or(a.any_orthonormal_vector());
    Mat3::from_cols(a, b, a.cross(b))
}

/// Shoulder + elbow (or hip + knee) rotations laying a two-bone limb's bind segments `bind` along
/// `upper` / `lower` (parent frame). Arms flex the hinge negative ([`aim_arm`]); knees positive.
fn aim_leg(upper: Vec3, lower: Vec3, bind: (Vec3, Vec3)) -> (Quat, Quat) {
    let (u0, f0) = (bind.0.normalize(), bind.1.normalize());
    let bend = upper.angle_between(lower);
    let (a, b) = (u0.y * f0.y + u0.z * f0.z, u0.z * f0.y - u0.y * f0.z);
    let open = ((bend.cos() - u0.x * f0.x) / a.hypot(b).max(1e-5)).clamp(-1.0, 1.0).acos();
    let knee = rx(b.atan2(a) + open);
    let to = frame(upper, lower);
    (Quat::from_mat3(&(to * frame(u0, knee * f0).transpose())), knee)
}

// The source clips are stylised game moves — a lunge that drops the hips ~45% of a leg, a
// stance a full leg long, the trunk folded 60–80° over the front knee and wound 120–170° round.
// An armoured shield-bearer fights a little taller and closer, so each is kept in part — but
// most of it: kept under half (0.4–0.6) the blows were all arm, the trunk barely turning into
// them and the hips staying up, and the knight read as timid in every swing.
/// …of the hips' drop (the feet still plant; the legs just bend less).
const SINK: f32 = 0.65;
/// …of the stance's spread and the hips' travel over it (the step into the blow).
const STRIDE: f32 = 0.8;
/// …of the trunk's turn about the vertical (the arms ride the eased trunk, so this is also how
/// much of the blade's sweep survives).
const TURN_KEEP: f32 = 0.75;
/// …of its forward/side fold.
const LEAN_KEEP: f32 = 0.65;
/// …and of the head's: the eyes stay on the foe.
const GAZE_KEEP: f32 = 0.15;
const HEAD_LEAN: f32 = 0.3;
/// How far the shield arm follows the clip's free left arm away from the guard it holds the board in.
const SHIELD_FOLLOW: f32 = 0.15;

/// The body-commit shares above, overridable for look-dev with
/// `FOREST_SWORDKEEP="sink,stride,turn,lean,gaze,shield"` (any prefix of the list).
struct Keep {
    sink: f32,
    stride: f32,
    turn: f32,
    lean: f32,
    gaze: f32,
    shield: f32,
}

fn keep() -> &'static Keep {
    static K: std::sync::OnceLock<Keep> = std::sync::OnceLock::new();
    K.get_or_init(|| {
        let mut v = [SINK, STRIDE, TURN_KEEP, LEAN_KEEP, GAZE_KEEP, SHIELD_FOLLOW];
        if let Ok(s) = std::env::var("FOREST_SWORDKEEP") {
            for (slot, x) in v.iter_mut().zip(s.split(',')) {
                if let Ok(x) = x.trim().parse() {
                    *slot = x;
                }
            }
        }
        Keep { sink: v[0], stride: v[1], turn: v[2], lean: v[3], gaze: v[4], shield: v[5] }
    })
}

/// `q` with only `turn` of its heading and `lean` of its tilt off the vertical (swing–twist about Y).
fn ease(q: Quat, turn: f32, lean: f32) -> Quat {
    let yaw = 2.0 * q.y.atan2(q.w);
    let swing = q * Quat::from_rotation_y(-yaw);
    Quat::IDENTITY.slerp(swing, lean) * Quat::from_rotation_y(turn * yaw)
}

/// Solve one clip frame onto the footman.
fn solve(f: &Frame) -> Pose {
    let rig = super::super::footman::leg_rig();
    let tp = Frame::of(&ual::TPOSE);
    let leg_len = rig.knee.length() + rig.foot.length();
    let mut p = rest();

    // ── Pelvis: the clip's travel off its T-pose in our leg lengths ──
    let k = keep();
    let pelvis = ease(f.pelvis_r, k.turn, k.lean);
    let d = (f.pelvis - tp.pelvis) * leg_len;
    let d = Vec3::new(d.x * k.stride, d.y * k.sink, d.z * k.stride);
    let mut hips = Vec3::new(0.0, super::super::model::HIP_REST_Y, 0.0) + d;

    // ── Legs: ankles where the clip plants them, scaled from our rest stance ──
    let mirror = |v: Vec3, right: bool| if right { Vec3::new(-v.x, v.y, v.z) } else { v };
    let ankle_rest = |right: bool| {
        Vec3::new(0.0, super::super::model::HIP_REST_Y, 0.0) + mirror(rig.hip + rig.knee + rig.foot, right)
    };
    let target = |i: usize| {
        let d = (f.ankle[i] - tp.ankle[i]) * leg_len;
        ankle_rest(i == 1) + Vec3::new(d.x * k.stride, d.y, d.z * k.stride)
    };
    // Never stretch a leg past its reach: the hips settle onto the straighter one (as the idle).
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
    p.hips = Jp { t: Some(hips + Vec3::Y * (1.05 - super::super::model::HIP_REST_Y)), r: pelvis };

    // ── Trunk: turn and fold eased (above); the head holds the foe ──
    let chest = ease(f.chest, k.turn, k.lean);
    p.torso = Jp::r(pelvis.inverse() * chest);
    p.head = Jp::r(chest.inverse() * ease(f.head, k.gaze, HEAD_LEAN));

    // ── Sword arm and blade: posed against the clip's own chest, so they ride the eased one ──
    let ab = super::super::footman::arm_bind();
    let inv = f.chest.inverse();
    let arm = |upper: Vec3, fore: Vec3, bind: (Vec3, Vec3)| aim_arm(inv * upper, inv * fore, upper.angle_between(fore), bind);
    let (sr, er) = arm(f.r_upper, f.r_fore, ab[0]);
    p.sh_r = Jp::r(sr);
    p.el_r = Jp::r(er);
    let (d0, e0) = super::super::footman::blade_axes();
    let hand = f.chest * sr * er;
    let want = frame(f.blade, f.edge) * frame(d0, e0).transpose();
    p.sword = Jp::r(hand.inverse() * Quat::from_mat3(&want));

    // ── Shield arm: the board stays up in guard, swayed a little by the clip's free arm ──
    let (sl, el) = arm(f.l_upper, f.l_fore, ab[1]);
    p.sh_l = Jp::r(e3(-0.45, 0.1, -0.35).slerp(sl, k.shield));
    p.el_l = Jp::r(rx(-1.05).slerp(el, k.shield));
    p.shield = Jp { t: Some(Vec3::new(-0.02, -0.02, 0.12)), r: e3(0.7, -0.8, 0.0) };
    p
}

/// A combo step: the strike clip (ending where the next step's starts), its blade-contact time,
/// the recovery that settles it back to the ready when the chain stops there, and — for a strike
/// cut out of a longer clip — the pose it is stepped into from (the previous step's end).
/// `settle` is where the strike's follow-through is spent and `go` where the recovery starts to
/// move: between them the clips hold still (the window the next step chains from), which
/// [`after_contact`] skims.
struct Step {
    strike: &'static [[f32; 53]],
    hit: f32,
    settle: f32,
    recover: &'static [[f32; 53]],
    go: f32,
    /// Playback rate of the recovery proper (a touch brisker than the clip: back on guard sooner).
    rec_rate: f32,
    lead: Option<&'static [f32; 53]>,
}

/// `Sword_Regular_C` opens with a leaping 360° spin; the finisher takes it from the landing step
/// out of that spin (`C_START`, the left foot coming down forward), walked into from `_B`'s end,
/// and carries its own recovery after the blade's follow-through (`C_SPLIT`).
const C_START: usize = 16;
const C_SPLIT: usize = 26;

/// Clip time of key `n`.
const fn key(n: usize) -> f32 {
    n as f32 / ual::FPS
}

fn step(variant: u8) -> Step {
    // `settle` / `go` are read off the clips' blade and trunk speeds (per-key deltas of the bake).
    match variant {
        1 => Step {
            strike: &ual::SWORD_REGULAR_B,
            hit: ual::SWORD_REGULAR_B_HIT,
            settle: key(10),
            recover: &ual::SWORD_REGULAR_B_REC,
            go: key(10),
            // `_B` ends arms flung wide and draws them back in slowly: hurry it more.
            rec_rate: 1.5,
            lead: None,
        },
        2 => Step {
            strike: &ual::SWORD_REGULAR_C[C_START..=C_SPLIT],
            hit: ual::SWORD_REGULAR_C_HIT - key(C_START),
            settle: key(24 - C_START),
            recover: &ual::SWORD_REGULAR_C[C_SPLIT..],
            go: key(6),
            rec_rate: 1.25,
            lead: ual::SWORD_REGULAR_B.last(),
        },
        _ => Step {
            strike: &ual::SWORD_REGULAR_A,
            hit: ual::SWORD_REGULAR_A_HIT,
            settle: key(10),
            recover: &ual::SWORD_REGULAR_A_REC,
            go: key(5),
            rec_rate: 1.25,
            lead: None,
        },
    }
}

/// Share of the wind-up (up to the blade contact) a `lead` takes to hand over to the clip.
const LEAD_IN: f32 = 0.7;
/// Boot lift over a lead-in step, per unit of its travel.
const STEP_LIFT: f32 = 0.2;
/// Playback rate through the still stretch between a strike's `settle` and its recovery's `go`.
const SKIM: f32 = 3.0;

fn length(clip: &[[f32; 53]]) -> f32 {
    (clip.len() - 1) as f32 / ual::FPS
}

/// Where a step is `tau` real seconds after its blade contact, on one timeline running through
/// the strike's follow-through (clip time below `length(strike)`) and on into its recovery (past
/// it, offset by the strike's length). The follow-through plays at the clip's own speed; the
/// still stretch where the clips wait for the next combo press is skimmed at [`SKIM`]× — held at
/// clip speed that read as the whole body freezing mid-swing for ~0.4 s before it began to settle.
fn after_contact(s: &Step, tau: f32) -> f32 {
    let end = length(s.strike);
    let follow = s.settle - s.hit;
    if tau <= follow {
        return s.hit + tau;
    }
    let skim = (end - s.settle + s.go) / SKIM;
    if tau <= follow + skim {
        return s.settle + (tau - follow) * SKIM;
    }
    end + s.go + (tau - follow - skim) * s.rec_rate
}

/// Timeline time ([`after_contact`]) at swing progress `ap` of a swing lasting `dur` s. The
/// wind-up is squeezed so the clip's contact lands exactly on the damage instant `hp` (the game
/// hits 105–135 ms after the press; the clips take ~267 ms to get there), on a cubic that arrives
/// at the contact already at the clip's own speed.
///
/// (It used to be two straight lines through the contact: ~2× into it, then the rest of the clip
/// stretched over the rest of the swing — the blade braked 4× in one frame at contact, then the
/// body sat in the strike's held last key until the recovery began. Every light swing read as a
/// snap and a freeze.)
fn strike_time(s: &Step, ap: f32, hp: f32, dur: f32) -> f32 {
    if ap >= hp {
        return after_contact(s, (ap - hp) * dur);
    }
    let d0 = s.hit / hp;
    // Hermite in `ap` from (0, 0) to (hp, hit), arriving at real-time speed (dt/dap = dur).
    let (m0, m1) = ((1.5 * d0 - 0.5 * dur).max(0.0) * hp, dur * hp);
    let u = ap / hp;
    let (u2, u3) = (u * u, u * u * u);
    m0 * (u3 - 2.0 * u2 + u) + s.hit * (3.0 * u2 - 2.0 * u3) + m1 * (u3 - u2)
}

/// The pose at timeline time `t` past the wind-up: the strike, or once it is spent its recovery.
fn timeline_pose(s: &Step, t: f32) -> Pose {
    let end = length(s.strike);
    if t < end { solve(&sample(s.strike, t)) } else { solve(&sample(s.recover, t - end)) }
}

/// The swing at progress `ap` (0..1 of a swing lasting `dur` s; see [`strike_time`]).
pub(crate) fn strike_pose(variant: u8, ap: f32, hit_phase: f32, dur: f32) -> Pose {
    let s = step(variant);
    let ap = ap.clamp(0.0, 1.0);
    let t = strike_time(&s, ap, hit_phase, dur);
    if ap >= hit_phase {
        return timeline_pose(&s, t);
    }
    let c = sample(s.strike, t);
    let f = match s.lead {
        Some(row) if ap < hit_phase * LEAD_IN => {
            let from = Frame::of(row);
            let b = smoothstep(ap / (hit_phase * LEAD_IN));
            let mut f = from.lerp(&c, b);
            // The stepping boot (the one travelling furthest) leaves the ground instead of sliding
            // across it; the other stays planted to push off — lifting both reads as a hop.
            let travel = |i: usize| (c.ankle[i] - from.ankle[i]).with_y(0.0).length() * keep().stride;
            let i = if travel(0) >= travel(1) { 0 } else { 1 };
            f.ankle[i].y += STEP_LIFT * travel(i) * (std::f32::consts::PI * b).sin();
            f
        }
        _ => c,
    };
    solve(&f)
}

/// Seconds after its blade contact that the recovery of `variant` has fully settled.
pub(crate) fn recover_len(variant: u8) -> f32 {
    let s = step(variant);
    let skim = (length(s.strike) - s.settle + s.go) / SKIM;
    s.settle - s.hit + skim + (length(s.recover) - s.go) / s.rec_rate
}

/// The step `tau` s after its blade contact (the swing itself may be over), and how much of it
/// still shows (fading into the stance over the recovery's last stretch, so the clip's own sword
/// idle hands over to the game's guard).
pub(crate) fn recover_pose(variant: u8, tau: f32) -> (Pose, f32) {
    let s = step(variant);
    let t = after_contact(&s, tau);
    let r = (t - length(s.strike)) / length(s.recover);
    (timeline_pose(&s, t), 1.0 - smoothstep((r - 0.55) / 0.45))
}
