//! **Caged-captive clips** — the Warbell flavour poses `crate::captives` cycles a prisoner through
//! so a cage of peasants reads as frightened people instead of mannequins: a loose huddle on the
//! straw, arms hugged round drawn-up knees (rocking), rubbing the arms against the cold, a
//! hung-head slump, the multi-key stand-up, a two-handed grip on the bars, plus the overlays every
//! act wears on top ([`apply_life`]: breathing, a head that looks about, a startled flinch, the nod
//! of a muttered line).
//!
//! A child of `anim` so it can build [`Pose`]s field-by-field like the studio clips. Every seated
//! pose solves its legs with [`solve_leg`] — a planar two-bone IK — so the feet stay nailed to the
//! cage planks whatever the hips do (rocking, rising, slumping); the arm angles were solved offline
//! against the same joint layout (`biped::rest_joint_matrices`) to land the hands on the shins /
//! knees / opposite upper arms / the bars, then rounded. Conventions (as everywhere in `anim`):
//! the rig faces +Z; hip/knee/shoulder/elbow `+X` = thigh back / knee flex / arm back / —, so a
//! thigh or arm swings FORWARD on `−X` and an elbow flexes on `−X`.

use std::f32::consts::{PI, TAU};

use bevy::prelude::*;

use super::{e3, idle_pose, lerp, loco_pose, rest, rx, smoothstep, Jp, Pose};

/// Thigh and shin bone lengths (hip → knee → ankle) of the shared rig (`biped::spawn_biped`).
const THIGH: f32 = 0.40;
const SHIN: f32 = 0.45;
/// The hip joints hang this far under the `Hips` joint.
const HIP_DROP: f32 = 0.05;
/// Ankle height above the sole in the rig frame: an ankle target at this height plants the foot.
const ANKLE_Y: f32 = 0.15;
/// Where the feet tuck (rig `z`) for a stand-up. The risen body ends right over them, so the brain
/// moves the root forward by exactly this much (× the root scale) when the rise completes — the
/// standing captive is then an ordinary biped centred on its root again.
pub(crate) const RISE_DZ: f32 = 0.30;
/// The tuck beat before a stand-up starts lifting (s) — the feet are drawn in under the knees.
pub(crate) const RISE_TUCK: f32 = 0.5;
/// Stand-up / sit-down lengths (s), at tempo 1.
pub(crate) const RISE_SECS: f32 = 1.5;
pub(crate) const SIT_SECS: f32 = 1.6;

/// The seated idles a captive cycles between on its straw.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub(crate) enum Seated {
    /// Knees up, forearms draped over them, hands loosely together — the default wait.
    Huddle,
    /// Knees drawn in tight, arms wrapped round the shins, rocking (fear / comfort).
    Hug,
    /// Arms crossed, rubbing the upper arms against the cold, with a little shiver.
    Rub,
    /// Shoulders rolled, head hung, forearms dropped over the thighs — despair.
    Slump,
}

/// The per-frame "life" a captive wears over whatever act it plays — the smoothed signals the
/// brain (`crate::captives`) hands down, so the clips themselves stay pure functions.
#[derive(Clone, Copy, Debug)]
pub(crate) struct Life {
    /// The captive's own clock (elapsed seconds + a per-captive offset): nobody breathes in step.
    pub t: f32,
    /// Personal tempo (≈0.8–1.25): breathing, rocking and rubbing speed.
    pub tempo: f32,
    /// 0..1 fear — quicker, shallower breaths.
    pub fear: f32,
    /// Head look in the root frame (rad): yaw (+ toward rig +X) and pitch (+ = down).
    pub look_yaw: f32,
    pub look_pitch: f32,
    /// 0..1 startle envelope, and the side the scare came from (−1 rig −X … +1 rig +X).
    pub flinch: f32,
    pub flinch_side: f32,
    /// 0..1 while muttering a line (a chin-up nod with a little bob).
    pub talk: f32,
}

impl Default for Life {
    fn default() -> Self {
        Self { t: 0.0, tempo: 1.0, fear: 0.0, look_yaw: 0.0, look_pitch: 0.0, flinch: 0.0, flinch_side: 0.0, talk: 0.0 }
    }
}

/// One arm as solved offline: shoulder euler (x, y, z) + elbow flex.
pub(super) type Arm = [f32; 4];

pub(super) fn arm(a: Arm) -> (Quat, Quat) {
    (e3(a[0], a[1], a[2]), rx(a[3]))
}
pub(super) fn mix(a: Arm, b: Arm, s: f32) -> (Quat, Quat) {
    let (a, b) = (arm(a), arm(b));
    (a.0.slerp(b.0, s), a.1.slerp(b.1, s))
}
pub(super) fn set_arms(p: &mut Pose, l: (Quat, Quat), r: (Quat, Quat)) {
    p.sh_l = Jp::r(l.0);
    p.el_l = Jp::r(l.1);
    p.sh_r = Jp::r(r.0);
    p.el_r = Jp::r(r.1);
}

// Solved arm sets, (left, right). The right arm mirrors the left as (x, −y, −z) except where the
// pose is deliberately lopsided (the hug's hands overlap, one over the other).
/// Forearms draped over the knees, hands loosely together in front of the shins.
const HUDDLE: (Arm, Arm) = ([-1.00, 1.04, -0.13, -1.02], [-1.00, -1.04, 0.13, -1.02]);
/// Arms wrapped round the shins, one hand over the other.
const HUG: (Arm, Arm) = ([-1.00, 1.16, -0.18, -1.15], [-0.98, -1.21, 0.16, -0.99]);
/// Arms crossed, each hand on the opposite upper arm — high (by the shoulder) and low (by the
/// elbow); the rub slides between them.
const RUB_HI: (Arm, Arm) = ([-2.30, 1.05, 1.32, -1.65], [-2.27, -1.08, -1.30, -1.63]);
const RUB_LO: (Arm, Arm) = ([-1.93, 1.18, 1.05, -1.49], [-1.90, -1.19, -1.03, -1.45]);
/// Forearms dropped over the thighs, hands dangling between the knees.
const SLUMP: (Arm, Arm) = ([-0.71, 0.67, 0.03, -0.97], [-0.67, -0.66, -0.01, -0.96]);
/// Hands thrown up in front of the face — the flinch guard.
const GUARD: (Arm, Arm) = ([-1.84, 0.47, 0.06, -1.68], [-1.84, -0.47, -0.06, -1.68]);
/// Standing, elbows down, both fists round a bar either side of the face (bars ±0.24 m apart).
const BARS: (Arm, Arm) = ([-0.61, -0.19, -0.20, -1.72], [-0.61, 0.19, 0.20, -1.72]);
/// Stand-up keys: gripping the shins (tuck), hands pushing off the thighs (lift-off), arms
/// swinging free for balance, then the relaxed standing carry.
const RISE_GRIP: (Arm, Arm) = ([-0.11, 1.09, -0.93, -1.82], [-0.11, -1.09, 0.93, -1.82]);
const RISE_PUSH: (Arm, Arm) = ([0.74, 0.89, -1.18, -2.13], [0.74, -0.89, 1.18, -2.13]);
const RISE_SWING: (Arm, Arm) = ([-0.50, 0.0, -0.10, -0.30], [-0.50, 0.0, 0.10, -0.30]);
const STAND: (Arm, Arm) = ([0.0, 0.0, 0.0, -0.05], [0.0, 0.0, 0.0, -0.04]);

/// Planar two-bone leg IK in the rig's sagittal plane: the local hip pitch, knee flex and foot
/// pitch that put the ankle at (`ANKLE_Y`, `ankle_z`) with the sole flat, for a `Hips` joint at
/// `hips` pitched by `pitch`. Out-of-reach targets clamp to a straight (or fully folded) leg.
pub(crate) fn solve_leg(hips: Vec3, pitch: f32, ankle_z: f32) -> (f32, f32, f32) {
    let hip = hips + Quat::from_rotation_x(pitch) * Vec3::new(0.0, -HIP_DROP, 0.0);
    let (dz, dy) = (ankle_z - hip.z, ANKLE_Y - hip.y);
    let d = (dz * dz + dy * dy).sqrt().clamp(0.08, THIGH + SHIN - 1e-3);
    // Absolute pitch of the hip→ankle line (rx of "straight down"; forward = negative).
    let line = -dz.atan2(-dy);
    let at_hip = ((THIGH * THIGH + d * d - SHIN * SHIN) / (2.0 * THIGH * d)).clamp(-1.0, 1.0).acos();
    let at_knee = ((THIGH * THIGH + SHIN * SHIN - d * d) / (2.0 * THIGH * SHIN)).clamp(-1.0, 1.0).acos();
    let knee = PI - at_knee;
    // The knee bends forward, so the thigh sits `at_hip` further forward than the line.
    let thigh = line - at_hip;
    (thigh - pitch, knee, -(thigh + knee))
}

/// Plant both feet at rig `z = feet` under a hips joint at `hips`/`pitch`; `splay` lets the knees
/// fall open. The splay turns each whole leg about its own hip→ankle line, so the knee swings out
/// while the planted ankle stays exactly where the IK put it; the sole is then re-levelled with
/// the toes turned out a little after the knee.
pub(super) fn plant_legs(p: &mut Pose, hips: Vec3, pitch: f32, feet: f32, splay: f32) {
    let (h, k, _) = solve_leg(hips, pitch, feet);
    let thigh = rx(h);
    let reach = thigh * (Vec3::new(0.0, -THIGH, 0.0) + rx(k) * Vec3::new(0.0, -SHIN, 0.0));
    let axis = reach.normalize_or(Vec3::NEG_Y);
    // + about the (down/forward) hip→ankle line swings the knee toward −X — out, for the left leg.
    let leg = |s: f32| {
        let hip = Quat::from_axis_angle(axis, s) * thigh;
        let foot = (hip * rx(k)).inverse() * rx(-pitch) * Quat::from_rotation_y(-0.5 * s);
        (hip, foot)
    };
    let ((hl, fl), (hr, fr)) = (leg(splay), leg(-splay));
    p.hip_l = Jp::r(hl);
    p.hip_r = Jp::r(hr);
    p.knee_l = Jp::r(rx(k));
    p.knee_r = Jp::r(rx(k));
    p.foot_l = Jp::r(fl);
    p.foot_r = Jp::r(fr);
}

/// A sitting body: hips joint + pitch/roll, torso curl, head pitch, feet distance and knee splay.
struct Seat {
    hips: Vec3,
    pitch: f32,
    roll: f32,
    torso: f32,
    head: f32,
    feet: f32,
    splay: f32,
}

fn sit_on(s: &Seat, arms: ((Quat, Quat), (Quat, Quat))) -> Pose {
    let mut p = rest();
    p.hips = Jp { t: Some(s.hips), r: e3(s.pitch, 0.0, s.roll) };
    p.torso = Jp::r(e3(s.torso, 0.0, -s.roll * 0.8)); // keep the head over the seat as the hips roll
    p.head = Jp::r(rx(s.head));
    plant_legs(&mut p, s.hips, s.pitch, s.feet, s.splay);
    set_arms(&mut p, arms.0, arms.1);
    p
}

/// A seated idle on the straw. `seat` = the hips height that rests the backside on the bedding
/// (rig units — low on the realistic cage's flat straw bed, higher on the heaped procedural one).
/// Each kind carries its own slow motion (a weight settle, the rock, the rub, a sigh); breathing
/// and the head come from [`apply_life`].
pub(crate) fn seated(kind: Seated, seat: f32, l: &Life) -> Pose {
    let t = l.t;
    let settle = (t * 0.47).sin(); // a slow shift from one sit bone to the other
    match kind {
        Seated::Huddle => sit_on(
            &Seat {
                hips: Vec3::new(0.0, seat, -0.04),
                pitch: -0.12,
                roll: settle * 0.035,
                torso: 0.40 + (t * 0.31).sin() * 0.03,
                head: -0.18,
                feet: 0.46,
                splay: 0.16,
            },
            (arm(HUDDLE.0), arm(HUDDLE.1)),
        ),
        Seated::Hug => {
            // Rocking: the pelvis tips on the sit bones, the curled torso follows a beat later
            // and the head counters — the feet stay planted (re-solved every frame).
            let rate = TAU / 2.9 * l.tempo * (1.0 + l.fear * 0.5);
            let rock = (t * rate).sin();
            let lag = (t * rate - 0.5).sin();
            sit_on(
                &Seat {
                    hips: Vec3::new(0.0, seat, -0.06 + rock * 0.015),
                    pitch: -0.20 + rock * 0.09,
                    roll: settle * 0.02,
                    torso: 0.62 + lag * 0.05,
                    head: -0.05 - lag * 0.06,
                    feet: 0.36,
                    splay: 0.08,
                },
                (arm(HUG.0), arm(HUG.1)),
            )
        }
        Seated::Rub => {
            // Both hands slide up and down the opposite upper arms (~1.2 Hz) over a fine shiver.
            let u = 0.5 + 0.5 * (t * TAU * 1.2 * l.tempo).sin();
            let shiver = (t * 23.0).sin() * 0.012 + (t * 31.0).sin() * 0.006;
            sit_on(
                &Seat {
                    hips: Vec3::new(0.0, seat, -0.04),
                    pitch: -0.10,
                    roll: settle * 0.02 + shiver,
                    torso: 0.34 + shiver * 0.5,
                    head: 0.05,
                    feet: 0.44,
                    splay: 0.10,
                },
                (mix(RUB_LO.0, RUB_HI.0, u), mix(RUB_LO.1, RUB_HI.1, u)),
            )
        }
        Seated::Slump => {
            // Long, heavy breaths through the rolled shoulders; the hung head sways a little.
            let sigh = (t * 0.9 * l.tempo).sin();
            sit_on(
                &Seat {
                    hips: Vec3::new(0.0, seat, -0.02),
                    pitch: -0.18,
                    roll: settle * 0.03,
                    torso: 0.62 + sigh * 0.035,
                    head: 0.55 + (t * 0.37 + 1.0).sin() * 0.06,
                    feet: 0.56,
                    splay: 0.30,
                },
                (arm(SLUMP.0), arm(SLUMP.1)),
            )
        }
    }
}

/// One key of the stand-up: hips height/forward/pitch, torso curl, head pitch and the arms.
struct RiseKey {
    at: f32,
    hy: f32,
    hz: f32,
    pitch: f32,
    torso: f32,
    head: f32,
    arms: (Arm, Arm),
}

/// The stand-up from the straw, `p` 0 → 1 (the sit-down plays it backwards). Four keys — feet
/// tucked with hands on the shins, a forward lean that rolls the weight over the feet with the
/// hands pushing off the thighs, the half-up with arms swinging free, then upright — interpolated
/// as PARAMETERS (not as poses) so the leg IK keeps both feet planted at [`RISE_DZ`] all the way.
/// At `p = 1` the hips stand right over the feet, i.e. [`RISE_DZ`] ahead of the root.
pub(crate) fn rise(p: f32, seat: f32) -> Pose {
    let keys = [
        RiseKey { at: 0.0, hy: seat, hz: -0.04, pitch: -0.05, torso: 0.55, head: -0.25, arms: RISE_GRIP },
        RiseKey { at: 0.45, hy: seat + 0.22, hz: 0.12, pitch: 0.35, torso: 0.45, head: -0.35, arms: RISE_PUSH },
        RiseKey { at: 0.75, hy: (seat + 0.30).max(0.80), hz: 0.24, pitch: 0.22, torso: 0.25, head: -0.15, arms: RISE_SWING },
        RiseKey { at: 1.0, hy: 1.045, hz: RISE_DZ, pitch: 0.0, torso: 0.04, head: 0.0, arms: STAND },
    ];
    let p = p.clamp(0.0, 1.0);
    let i = keys.iter().rposition(|k| k.at <= p).unwrap_or(0).min(keys.len() - 2);
    let (a, b) = (&keys[i], &keys[i + 1]);
    let s = smoothstep((p - a.at) / (b.at - a.at));
    let hips = Vec3::new(0.0, lerp(a.hy, b.hy, s), lerp(a.hz, b.hz, s));
    let pitch = lerp(a.pitch, b.pitch, s);
    let mut po = rest();
    po.hips = Jp { t: Some(hips), r: rx(pitch) };
    po.torso = Jp::r(rx(lerp(a.torso, b.torso, s)));
    po.head = Jp::r(rx(lerp(a.head, b.head, s)));
    plant_legs(&mut po, hips, pitch, RISE_DZ, lerp(0.10, 0.02, p));
    set_arms(&mut po, mix(a.arms.0, b.arms.0, s), mix(a.arms.1, b.arms.1, s));
    po
}

/// Standing at the bars: the idle stance's weight shifts, a lean in, both fists round the bars
/// either side of the face. `grip` 1 = both hands on (0 = the right hand has dropped to the
/// side), `press` leans the face into the gap, `rattle` shakes the bars (pleading / panic).
pub(crate) fn bars(l: &Life, grip: f32, press: f32, rattle: f32) -> Pose {
    let mut p = idle_pose(l.t);
    if let Some(t) = p.hips.t.as_mut() {
        t.z += 0.03 + press * 0.03;
    }
    p.torso = Jp::r(rx(0.08 + press * 0.14) * p.torso.r);
    p.head = Jp::r(rx(-0.06 - press * 0.08) * p.head.r); // chin up over the lashing, looking out
    // A lean brings the shoulders closer to the bars, so the elbows fold a touch more.
    let fold = rx(-press * 0.25);
    let shake = rx((l.t * 7.5).sin() * 0.08 * rattle);
    let bl = arm(BARS.0);
    p.sh_l = Jp::r(shake * bl.0);
    p.el_l = Jp::r(bl.1 * fold);
    let r = mix(STAND.1, BARS.1, grip);
    p.sh_r = Jp::r(rx((l.t * 7.5 + 1.3).sin() * 0.08 * rattle * grip) * r.0);
    p.el_r = Jp::r(r.1 * fold);
    p
}

/// The in-cage shuffle — the shared walk at a short, stiff stride (`m` 0 = standing idle).
pub(crate) fn shuffle(l: &Life, walk_phase: f32, m: f32) -> Pose {
    loco_pose(l.t, walk_phase, m.clamp(0.0, 1.0) * 0.55, 0.0)
}

/// Cross-fade two poses (`s` 0 = `a`).
pub(crate) fn blend(a: &Pose, b: &Pose, s: f32) -> Pose {
    a.lerp(b, s.clamp(0.0, 1.0))
}

/// Move the whole body by `d` (rig units) relative to its root — the hips carry every other joint.
/// Used to re-express the last pose when the brain relocates the root (stand-up / sit-down), so
/// the cross-fade continues from exactly where the body already is.
pub(crate) fn shift(p: &mut Pose, d: Vec3) {
    if let Some(t) = p.hips.t.as_mut() {
        *t += d;
    }
}

/// The layer every act wears: breathing (faster and shallower with fear), the head look (a third
/// of the yaw carried by the torso), the flinch (curl in, duck, hands up, head turned from the
/// scare) and the nod of a muttered line. Applied AFTER act cross-fades so it never double-counts.
pub(crate) fn apply_life(p: &mut Pose, l: &Life) {
    let rate = TAU / 3.6 * l.tempo * (1.0 + l.fear * 0.9);
    let b = (l.t * rate).sin() * (1.0 - l.fear * 0.4);
    p.torso.r = p.torso.r * rx(-0.022 * b);
    p.sh_l.r = e3(0.0, 0.0, -0.015 * b) * p.sh_l.r;
    p.sh_r.r = e3(0.0, 0.0, 0.015 * b) * p.sh_r.r;

    let share = 0.3;
    p.torso.r = Quat::from_rotation_y(l.look_yaw * share) * p.torso.r;
    p.head.r = Quat::from_rotation_y(l.look_yaw * (1.0 - share)) * p.head.r * rx(l.look_pitch);

    if l.flinch > 1e-3 {
        let f = l.flinch;
        let (gl, gr) = (arm(GUARD.0), arm(GUARD.1));
        p.sh_l.r = p.sh_l.r.slerp(gl.0, f * 0.8);
        p.el_l.r = p.el_l.r.slerp(gl.1, f * 0.8);
        p.sh_r.r = p.sh_r.r.slerp(gr.0, f * 0.8);
        p.el_r.r = p.el_r.r.slerp(gr.1, f * 0.8);
        p.torso.r = p.torso.r * rx(0.10 * f);
        p.head.r = Quat::from_rotation_y(-l.flinch_side * 0.45 * f) * p.head.r * rx(0.25 * f);
        shift(p, Vec3::new(0.0, 0.0, -0.025 * f));
    }
    if l.talk > 1e-3 {
        let k = l.talk;
        p.head.r = p.head.r * rx(-0.10 * k + (l.t * 8.5).sin() * 0.035 * k);
        p.torso.r = p.torso.r * rx(0.04 * k);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Forward kinematics of one leg: the ankle in the rig frame (`side` −1 left / +1 right).
    fn ankle(p: &Pose, side: f32) -> Vec3 {
        let (hip, knee) = if side < 0.0 { (p.hip_l, p.knee_l) } else { (p.hip_r, p.knee_r) };
        let hr = p.hips.r;
        p.hips.t.unwrap()
            + hr * Vec3::new(side * 0.1, -HIP_DROP, 0.0)
            + hr * hip.r * Vec3::new(0.0, -THIGH, 0.0)
            + hr * hip.r * knee.r * Vec3::new(0.0, -SHIN, 0.0)
    }

    #[test]
    fn leg_ik_lands_the_ankle_on_its_target() {
        for (hips, pitch, feet) in [
            (Vec3::new(0.0, 0.28, -0.04), -0.12, 0.46),
            (Vec3::new(0.0, 0.50, 0.12), 0.35, RISE_DZ),
            (Vec3::new(0.0, 0.62, -0.02), -0.18, 0.40),
            (Vec3::new(0.0, 1.0, 0.25), 0.1, RISE_DZ),
        ] {
            let (h, k, _) = solve_leg(hips, pitch, feet);
            let mut p = rest();
            p.hips = Jp { t: Some(hips), r: rx(pitch) };
            p.hip_l = Jp::r(rx(h));
            p.knee_l = Jp::r(rx(k));
            let a = ankle(&p, -1.0);
            assert!((a.y - ANKLE_Y).abs() < 1e-3 && (a.z - feet).abs() < 1e-3, "ankle {a:?} vs z {feet}");
            assert!(k >= 0.0, "a knee only bends forward");
        }
    }

    #[test]
    fn the_stand_up_keeps_both_feet_planted() {
        for seat in [0.28, 0.60] {
            for i in 0..=40 {
                let p = rise(i as f32 / 40.0, seat);
                for side in [-1.0, 1.0] {
                    let a = ankle(&p, side);
                    // Knee splay swings the ankle a hair off the sagittal solve — well under 2 cm.
                    assert!((a.y - ANKLE_Y).abs() < 0.02 && (a.z - RISE_DZ).abs() < 0.02, "seat {seat} p {i}/40: {a:?}");
                }
            }
        }
        // Upright at the end, hips straight over the planted feet.
        let up = rise(1.0, 0.28).hips.t.unwrap();
        assert!(up.y > 1.0 && (up.z - RISE_DZ).abs() < 1e-4);
    }

    #[test]
    fn seated_idles_keep_the_feet_on_the_planks_while_they_move() {
        let seat = 0.28;
        for kind in [Seated::Huddle, Seated::Hug, Seated::Rub, Seated::Slump] {
            for i in 0..60 {
                let l = Life { t: i as f32 * 0.37, fear: 0.5, ..default() };
                let p = seated(kind, seat, &l);
                for side in [-1.0f32, 1.0] {
                    let a = ankle(&p, side);
                    assert!((a.y - ANKLE_Y).abs() < 0.03, "{kind:?} t={}: ankle y {}", l.t, a.y);
                    // The knees fall OPEN (never knock inward through each other).
                    let hip = if side < 0.0 { p.hip_l } else { p.hip_r };
                    let knee = p.hips.t.unwrap() + p.hips.r * (Vec3::new(side * 0.1, -HIP_DROP, 0.0) + hip.r * Vec3::new(0.0, -THIGH, 0.0));
                    assert!(knee.x * side > 0.1, "{kind:?}: knee {knee:?} on side {side}");
                }
                assert!((p.hips.t.unwrap().y - seat).abs() < 1e-4, "{kind:?}: the backside stays on the straw");
            }
        }
    }

    #[test]
    fn overlays_stay_finite_and_normalised() {
        let l = Life { t: 3.3, tempo: 1.2, fear: 1.0, look_yaw: 1.2, look_pitch: -0.4, flinch: 1.0, flinch_side: -1.0, talk: 1.0 };
        for mut p in [seated(Seated::Hug, 0.28, &l), rise(0.6, 0.28), bars(&l, 0.5, 1.0, 1.0), shuffle(&l, 2.0, 1.0)] {
            apply_life(&mut p, &l);
            for q in [p.hips.r, p.torso.r, p.head.r, p.sh_l.r, p.el_r.r, p.hip_l.r, p.knee_r.r, p.foot_l.r] {
                assert!(q.is_finite() && (q.length() - 1.0).abs() < 1e-3);
            }
        }
    }
}
