//! **Village-life clips** — the everyday acts `crate::village_life` cycles its residents through so
//! the courtyard and the street village read as people living there: the bench sit (sit down, eat,
//! drink, chat, whittle, doze, stand up — legs solved by IK so the feet stay planted and the pelvis
//! lands ON the seat), the standing chores (sweep, draw water at the winch, hang laundry, scatter
//! grain, weed on the knees, hammer, saw, warm the hands at the fire), the social beats (talk
//! gestures, listening with crossed arms, nods, laughs, a wave, a bow, haggling, paying), kids'
//! staring and hiding, and the carries layered over the walk (sack on the shoulder, basket in the
//! crook of the arm, a bucket at arm's length).
//!
//! A child of `anim` so it builds [`Pose`]s field-by-field like the studio clips. Same conventions
//! as everywhere in `anim`: the rig faces +Z; shoulder/hip `−X` swings the limb FORWARD, an elbow
//! or knee flexes on `−X` (elbow) / `+X` (knee); the LEFT arm abducts on `−Z`, the right on `+Z`;
//! torso / head `+X` curl forward / look down.

use std::f32::consts::{PI, TAU};

use bevy::prelude::*;

use super::captive::{self, arm, mix, plant_legs, set_arms, Arm};
use super::{e3, idle_pose, loco_pose, rest, rx, smoothstep, Jp, Pose};

/// A standing (or crouched) act.
#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
pub(crate) enum Act {
    #[default]
    Stand,
    Talk,
    Listen,
    Nod,
    Laugh,
    Wave,
    Bow,
    Sweep,
    Draw,
    Hang,
    Scatter,
    Weed,
    Haggle,
    Pay,
    Yawn,
    Hammer,
    Saw,
    Warm,
    Stare,
    Hide,
    Call,
    Browse,
}

/// What a seated resident does on the bench.
#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
pub(crate) enum SitAct {
    #[default]
    Rest,
    Eat,
    Drink,
    Talk,
    Whittle,
    Doze,
    Laugh,
}

/// What is carried while walking (arms only; the legs keep the gait).
#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
pub(crate) enum Carry {
    #[default]
    None,
    Sack,
    Basket,
    Bucket,
    Broom,
}

const REST_A: (Arm, Arm) = ([0.0, 0.0, 0.0, -0.06], [0.0, 0.0, 0.0, -0.05]);
/// Arms crossed over the chest (hands at the opposite elbows) — the captive's low rub key.
const CROSSED: (Arm, Arm) = ([-1.93, 1.18, 1.05, -1.49], [-1.90, -1.19, -1.03, -1.45]);
/// Hands resting on the thighs / knees, seated.
const LAP: (Arm, Arm) = ([-0.62, 0.0, 0.06, -0.42], [-0.62, 0.0, -0.06, -0.42]);
/// Hands folded on the belly (dozing).
const FOLDED: (Arm, Arm) = ([-0.32, 0.0, 0.48, -1.62], [-0.32, 0.0, -0.48, -1.62]);
/// The right hand brought to the mouth (a bite / a sip), elbow raised forward.
const R_MOUTH: Arm = [-1.22, 0.0, -0.42, -2.25];
const R_SIP: Arm = [-1.45, 0.0, -0.30, -2.15];
/// The right hand low in the lap holding the food / the mug.
const R_LAP: Arm = [-0.70, 0.0, -0.18, -1.15];
const L_LAP: Arm = [-0.70, 0.0, 0.18, -1.15];

fn wave01(x: f32) -> f32 {
    0.5 + 0.5 * x.sin()
}

/// One standing act at the resident's own clock `t` (seconds, phase-desynced). `k` is the act's
/// 0..1 envelope (the caller eases it in/out so an act blends from the idle stance, never pops).
pub(crate) fn stand(act: Act, t: f32, k: f32) -> Pose {
    let base = idle_pose(t);
    let mut p = base;
    match act {
        Act::Stand => return base,
        Act::Talk => {
            // The right forearm comes up and turns the point over; the left hangs loose. Beats
            // every ~0.7 s with a small head bob.
            let g = (t * 4.3).sin();
            let g2 = (t * 2.1 + 0.6).sin();
            set_arms(
                &mut p,
                arm([-0.18, 0.0, -0.10, -0.55]),
                arm([-0.62 + 0.18 * g2, 0.0, 0.18 + 0.08 * g, -1.35 + 0.28 * g]),
            );
            p.head.r = p.head.r * rx(0.04 * g - 0.05);
            p.torso.r = p.torso.r * Quat::from_rotation_y(0.06 * g2);
        }
        Act::Listen => {
            set_arms(&mut p, arm(CROSSED.0), arm(CROSSED.1));
            p.head.r = p.head.r * Quat::from_rotation_z(0.10) * rx(0.05 + 0.04 * (t * 0.9).sin());
        }
        Act::Nod => {
            set_arms(&mut p, arm(CROSSED.0), arm(CROSSED.1));
            p.head.r = p.head.r * rx(0.16 * wave01(t * 9.0) - 0.02);
        }
        Act::Laugh => {
            // Head back, shoulders shaking, a hand on the belly.
            let shake = (t * 17.0).sin();
            p.torso.r = p.torso.r * rx(-0.10 + 0.03 * shake);
            p.head.r = p.head.r * rx(-0.28 + 0.05 * shake);
            set_arms(&mut p, arm([-0.15, 0.0, -0.12, -0.35]), arm([-0.42, 0.0, -0.38, -1.45]));
        }
        Act::Wave => {
            let w = (t * 7.5).sin();
            set_arms(&mut p, arm(REST_A.0), arm([-0.35, 0.0, 2.45 + 0.22 * w, -0.45 - 0.2 * w]));
            p.head.r = p.head.r * rx(-0.06);
        }
        Act::Bow => {
            // A bow from the hips, right hand to the chest; `k` is the bow's own 0→1→0.
            let b = smoothstep(k);
            if let Some(h) = p.hips.t.as_mut() {
                h.z -= 0.05 * b;
            }
            p.hips.r = p.hips.r * rx(0.18 * b);
            p.torso.r = p.torso.r * rx(0.45 * b);
            p.head.r = p.head.r * rx(0.25 * b);
            set_arms(&mut p, arm([-0.28 * b, 0.0, 0.0, -0.2]), arm([-0.55, 0.0, -0.55, -1.95]));
            return base.lerp(&p, 1.0);
        }
        Act::Sweep => {
            // Both hands on the broom handle, the trunk swinging the strokes side to side.
            let s = (t * 2.4).sin();
            if let Some(h) = p.hips.t.as_mut() {
                h.y -= 0.03;
            }
            p.torso.r = Quat::from_rotation_y(0.28 * s) * rx(0.30);
            p.head.r = rx(0.30) * Quat::from_rotation_y(-0.15 * s);
            set_arms(&mut p, arm([-0.72 - 0.10 * s, 0.0, 0.40, -0.95]), arm([-0.30 + 0.10 * s, 0.0, -0.08, -0.55]));
        }
        Act::Draw => {
            // Cranking the well winch: both fists turn a circle at chest height, half a turn apart.
            let w = t * 3.4;
            p.torso.r = p.torso.r * rx(0.16 + 0.05 * w.sin());
            set_arms(
                &mut p,
                arm([-1.05 + 0.35 * (w + PI).sin(), 0.0, 0.20, -1.05 - 0.40 * (w + PI).cos()]),
                arm([-1.05 + 0.35 * w.sin(), 0.0, -0.20, -1.05 - 0.40 * w.cos()]),
            );
        }
        Act::Hang => {
            // Reaching up to peg a sheet on the line, hands alternating, chin up.
            let a = (t * 1.6).sin();
            p.head.r = p.head.r * rx(-0.30);
            p.torso.r = p.torso.r * rx(-0.06);
            set_arms(&mut p, arm([-2.45 + 0.18 * a, 0.0, -0.25, -0.55 - 0.2 * a]), arm([-2.45 - 0.18 * a, 0.0, 0.25, -0.55 + 0.2 * a]));
        }
        Act::Scatter => {
            // Grain bowl on the left forearm, the right hand flinging handfuls out to the side.
            let c = (t * 1.3).fract();
            let throw = if c < 0.25 { smoothstep(c / 0.25) } else { 1.0 - smoothstep((c - 0.25) / 0.75) };
            p.torso.r = p.torso.r * Quat::from_rotation_y(-0.18 * throw) * rx(0.10);
            p.head.r = p.head.r * rx(0.25);
            set_arms(&mut p, arm([-0.45, 0.0, 0.35, -1.55]), arm([-0.55 - 0.65 * throw, 0.0, -0.10 + 0.55 * throw, -1.3 + 0.9 * throw]));
        }
        Act::Weed | Act::Hide => {
            // A deep squat, feet planted; weeding pulls at the ground, hiding hugs the knees.
            let hips = Vec3::new(0.0, if act == Act::Hide { 0.50 } else { 0.55 }, -0.06);
            let pitch = 0.42;
            let mut q = rest();
            q.hips = Jp { t: Some(hips), r: rx(pitch) };
            plant_legs(&mut q, hips, pitch, 0.28, 0.22);
            if act == Act::Weed {
                let pull = (t * 2.2).sin();
                q.torso.r = rx(0.45);
                q.head.r = rx(0.35);
                set_arms(&mut q, arm([-0.75 + 0.15 * pull, 0.0, -0.05, -0.35]), arm([-0.95 - 0.2 * pull, 0.0, 0.05, -0.25 - 0.3 * wave01(t * 4.4)]));
            } else {
                // Peeking: the head comes up over the knees now and then.
                let peek = smoothstep(((t * 0.4).sin() - 0.4) * 2.0);
                q.torso.r = rx(0.55 - 0.25 * peek);
                q.head.r = rx(-0.10 - 0.2 * peek) * Quat::from_rotation_y(0.4 * (t * 0.3).sin());
                set_arms(&mut q, arm(captive_hug().0), arm(captive_hug().1));
            }
            return base.lerp(&q, k);
        }
        Act::Haggle => {
            // Point at the goods, then a weary head-shake; the left hand on the hip.
            let beat = (t * 0.5).fract();
            let point = smoothstep(beat * 3.0) * (1.0 - smoothstep((beat - 0.55) * 4.0));
            let shake = if beat > 0.6 { (t * 11.0).sin() * 0.28 * (1.0 - smoothstep((beat - 0.6) * 2.5)) } else { 0.0 };
            p.head.r = p.head.r * Quat::from_rotation_y(shake);
            set_arms(&mut p, arm([0.25, 0.0, -0.55, -1.55]), arm([-0.30 - 0.85 * point, 0.0, 0.05, -1.1 + 0.7 * point]));
        }
        Act::Pay => {
            // Hand held out palm up over the counter, the other at the purse on the belt.
            p.torso.r = p.torso.r * rx(0.10);
            p.head.r = p.head.r * rx(0.18);
            set_arms(&mut p, arm([-0.15, 0.0, 0.15, -1.25]), arm([-0.95, 0.0, -0.08, -0.55]));
        }
        Act::Yawn => {
            // Arms up over the head, back arched, mouth to the sky — `k` is the stretch envelope.
            let s = smoothstep(k);
            p.torso.r = p.torso.r * rx(-0.16 * s);
            p.head.r = p.head.r * rx(-0.35 * s);
            let up = mix(REST_A.0, [-2.85, 0.0, -0.35, -0.35], s);
            let up_r = mix(REST_A.1, [-2.85, 0.0, 0.35, -0.35], s);
            set_arms(&mut p, up, up_r);
            return p;
        }
        Act::Hammer => {
            let c = (t * 1.6).fract();
            let strike = if c < 0.7 { smoothstep(c / 0.7) } else { 1.0 - smoothstep((c - 0.7) / 0.3) };
            p.torso.r = p.torso.r * rx(0.40);
            p.head.r = p.head.r * rx(0.30);
            set_arms(&mut p, arm([-0.95, 0.0, 0.30, -0.55]), arm([-1.55 + 0.75 * (1.0 - strike), 0.0, 0.05, -1.55 + 0.9 * (1.0 - strike)]));
        }
        Act::Saw => {
            let s = (t * 4.0).sin();
            p.torso.r = p.torso.r * rx(0.32) * Quat::from_rotation_y(0.05 * s);
            p.head.r = p.head.r * rx(0.30);
            set_arms(&mut p, arm([-0.85, 0.0, 0.32, -0.50]), arm([-0.75 + 0.30 * s, 0.0, -0.05, -1.10 - 0.55 * s]));
        }
        Act::Warm => {
            // Palms held out to the fire, rubbed together now and then.
            let rub = (t * 6.0).sin() * smoothstep((t * 0.35).sin());
            p.torso.r = p.torso.r * rx(0.08);
            set_arms(&mut p, arm([-0.95, 0.0, 0.10 + 0.06 * rub, -0.95]), arm([-0.95, 0.0, -0.10 + 0.06 * rub, -0.95]));
        }
        Act::Stare => {
            // A kid gawping up at the knight: hands behind the back, chin up, swaying.
            let sway = (t * 1.4).sin();
            p.head.r = p.head.r * rx(-0.22) * Quat::from_rotation_z(0.08 * sway);
            p.torso.r = p.torso.r * Quat::from_rotation_y(0.10 * sway);
            set_arms(&mut p, arm([0.45, 0.0, 0.10, -0.55]), arm([0.45, 0.0, -0.10, -0.55]));
        }
        Act::Call => {
            // A hand cupped at the mouth, calling across the yard.
            p.head.r = p.head.r * rx(-0.12);
            p.torso.r = p.torso.r * rx(-0.05);
            set_arms(&mut p, arm([-0.10, 0.0, -0.05, -0.30]), arm([-1.25, 0.0, -0.55, -2.20]));
        }
        Act::Browse => {
            // Leaning in over the counter, a hand hovering over the goods.
            let h = (t * 0.8).sin();
            p.torso.r = p.torso.r * rx(0.18) * Quat::from_rotation_y(0.12 * h);
            p.head.r = p.head.r * rx(0.28) * Quat::from_rotation_y(0.2 * h);
            set_arms(&mut p, arm([0.10, 0.0, -0.10, -0.80]), arm([-0.85 + 0.1 * h, 0.0, -0.05 + 0.08 * h, -0.70]));
        }
    }
    base.lerp(&p, k)
}

fn captive_hug() -> (Arm, Arm) {
    ([-1.00, 1.16, -0.18, -1.15], [-0.98, -1.21, 0.16, -0.99])
}

/// Seated on a bench whose sitting height puts the `Hips` joint at `seat` (rig units). The body
/// leans on the sit bones, feet planted forward by IK; the act sets the arms / trunk / head.
pub(crate) fn seated(act: SitAct, seat: f32, t: f32) -> Pose {
    let settle = (t * 0.41).sin();
    let breath = (t * TAU / 3.8).sin();
    let mut hips = Vec3::new(0.0, seat, -0.04);
    let mut pitch = -0.06;
    let mut torso = 0.10 + breath * 0.012;
    let head;
    let mut feet = 0.40;
    let mut splay = 0.10;
    let (mut l, mut r) = (arm(LAP.0), arm(LAP.1));
    match act {
        SitAct::Rest => {
            head = 0.05 + 0.04 * (t * 0.23).sin();
        }
        SitAct::Eat => {
            // A bite every ~4 s: the right hand comes up to the mouth, then chewing.
            let c = (t * 0.25).fract();
            let lift = smoothstep(c / 0.18) * (1.0 - smoothstep((c - 0.40) / 0.15));
            torso = 0.22;
            head = 0.12 - 0.10 * lift + 0.03 * (t * 9.0).sin() * (1.0 - lift);
            l = arm(L_LAP);
            r = mix(R_LAP, R_MOUTH, lift);
        }
        SitAct::Drink => {
            let c = (t * 0.18).fract();
            let lift = smoothstep(c / 0.15) * (1.0 - smoothstep((c - 0.45) / 0.15));
            torso = 0.12 - 0.08 * lift;
            head = 0.05 - 0.30 * lift;
            l = arm(LAP.0);
            r = mix(R_LAP, R_SIP, lift);
        }
        SitAct::Talk => {
            let g = (t * 4.0).sin();
            torso = 0.16;
            head = -0.02 + 0.04 * g;
            r = arm([-0.70 + 0.12 * (t * 2.0).sin(), 0.0, 0.10 + 0.06 * g, -1.30 + 0.25 * g]);
        }
        SitAct::Whittle => {
            let w = (t * 3.2).sin();
            torso = 0.32;
            head = 0.45;
            feet = 0.44;
            splay = 0.22;
            l = arm([-0.80, 0.0, 0.38, -1.25]);
            r = arm([-0.72 + 0.10 * w, 0.0, -0.34, -1.20 + 0.18 * w]);
        }
        SitAct::Doze => {
            // Chin on the chest, slow heavy breaths; now and then a snort jerks the head up.
            let snort = smoothstep(((t * 0.11).sin() - 0.93) * 14.0);
            pitch = -0.14;
            torso = 0.30 + breath * 0.03;
            head = 0.75 - 0.6 * snort + breath * 0.03;
            feet = 0.48;
            splay = 0.24;
            l = arm(FOLDED.0);
            r = arm(FOLDED.1);
        }
        SitAct::Laugh => {
            let shake = (t * 16.0).sin();
            torso = -0.05 + 0.03 * shake;
            head = -0.25 + 0.05 * shake;
            pitch = -0.10;
            r = arm([-0.42, 0.0, -0.36, -1.45]);
        }
    }
    hips.y += breath * 0.003;
    let mut p = rest();
    p.hips = Jp { t: Some(hips), r: e3(pitch, 0.0, settle * 0.02) };
    p.torso = Jp::r(e3(torso, 0.0, -settle * 0.016));
    p.head = Jp::r(rx(head));
    plant_legs(&mut p, hips, pitch, feet, splay);
    p.sh_l = Jp::r(l.0);
    p.el_l = Jp::r(l.1);
    p.sh_r = Jp::r(r.0);
    p.el_r = Jp::r(r.1);
    p
}

/// The stand-up from a bench (`p` 0 → 1; the sit-down plays it backwards). The captive's
/// feet-planted rise keys work unchanged from a bench height: at `p = 1` the hips stand
/// [`RISE_DZ`] ahead of the seated root, so the brain moves the root by exactly that much.
pub(crate) fn rise(p: f32, seat: f32) -> Pose {
    captive::rise(p, seat)
}
pub(crate) use captive::RISE_DZ;

/// The walk / run with a load in the arms — the legs and the free arm keep the gait.
pub(crate) fn carry_walk(t: f32, walk_phase: f32, moving: f32, run: f32, carry: Carry) -> Pose {
    let mut p = loco_pose(t, walk_phase, moving, run);
    match carry {
        Carry::None => {}
        Carry::Sack => {
            // Right hand up on the shoulder steadying the sack.
            let (s, e) = arm([-0.95, 0.0, 0.95, -2.25]);
            p.sh_r = Jp::r(s);
            p.el_r = Jp::r(e);
            p.torso.r = p.torso.r * Quat::from_rotation_z(0.06) * rx(0.06);
        }
        Carry::Basket => {
            // The basket's handle in the crook of the left arm, forearm level.
            let (s, e) = arm([-0.30, 0.0, -0.30, -1.50]);
            p.sh_l = Jp::r(s);
            p.el_l = Jp::r(e);
        }
        Carry::Bucket => {
            // A full bucket at arm's length: the right arm straight and held off the leg, the
            // body leaning away from the weight, the left arm out for balance.
            let (s, e) = arm([0.02, 0.0, 0.20, -0.06]);
            p.sh_r = Jp::r(s);
            p.el_r = Jp::r(e);
            p.torso.r = p.torso.r * Quat::from_rotation_z(-0.07);
            p.sh_l.r = p.sh_l.r * Quat::from_rotation_z(-0.22);
        }
        Carry::Broom => {
            // The broom shouldered, bristles up behind.
            let (s, e) = arm([-0.55, 0.0, 0.25, -2.0]);
            p.sh_r = Jp::r(s);
            p.el_r = Jp::r(e);
        }
    }
    p
}

/// A little head-turn toward something (the hero, a partner) layered on any pose — a third of the
/// yaw carried by the trunk.
pub(crate) fn look(p: &mut Pose, yaw: f32, pitch: f32) {
    p.torso.r = Quat::from_rotation_y(yaw * 0.3) * p.torso.r;
    p.head.r = Quat::from_rotation_y(yaw * 0.7) * p.head.r * rx(pitch);
}

/// Cross-fade two poses (`s` 0 = `a`).
pub(crate) fn blend(a: &Pose, b: &Pose, s: f32) -> Pose {
    a.lerp(b, s.clamp(0.0, 1.0))
}

/// Ease a 0..1 envelope `x` over `secs` of attack from the act's start (`age`) and the same release
/// before `len` — the standard in/out every timed act wears.
pub(crate) fn envelope(age: f32, len: f32, secs: f32) -> f32 {
    smoothstep((age / secs).min(1.0)) * smoothstep(((len - age) / secs).clamp(0.0, 1.0))
}

/// The preview roster (`FOREST_VIEW=life`): one clip per rig index, cycling.
pub(crate) fn preview(i: usize, t: f32, seat: f32) -> Pose {
    const STAND: [Act; 16] = [
        Act::Talk, Act::Listen, Act::Laugh, Act::Wave, Act::Sweep, Act::Draw, Act::Hang, Act::Scatter,
        Act::Weed, Act::Haggle, Act::Pay, Act::Hammer, Act::Saw, Act::Warm, Act::Stare, Act::Call,
    ];
    const SIT: [SitAct; 6] = [SitAct::Eat, SitAct::Drink, SitAct::Talk, SitAct::Whittle, SitAct::Doze, SitAct::Rest];
    let mode = std::env::var("FOREST_VIEW_LIFE").unwrap_or_default();
    match mode.as_str() {
        "sit" => seated(SIT[i % SIT.len()], seat, t),
        "rise" => rise(wave01(t * 1.2 + i as f32), seat),
        "carry" => {
            let c = [Carry::Sack, Carry::Basket, Carry::Bucket, Carry::Broom][i % 4];
            carry_walk(t, t * 8.0, 1.0, 0.0, c)
        }
        "bow" => stand(Act::Bow, t, wave01(t * 1.5)),
        "yawn" => stand(Act::Yawn, t, wave01(t * 1.0)),
        "hide" => stand(Act::Hide, t, 1.0),
        "b" => stand(STAND[(i + 8) % STAND.len()], t, 1.0),
        _ => stand(STAND[i % STAND.len()], t, 1.0),
    }
}

/// Re-express a pose after its root moved `dz` (rig units, along the root's facing) — the
/// cross-fade then continues from exactly where the body already is (bench sit / stand-up).
pub(crate) fn shift(p: &mut Pose, dz: f32) {
    captive::shift(p, Vec3::new(0.0, 0.0, dz));
}
