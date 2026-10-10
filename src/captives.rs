//! **Caged captives that feel alive.** The peasants in the ork cages (`camps::spawn_cage`) used to
//! sit frozen in one seated pose — mannequins behind bars. Each now carries a [`CaptiveLife`]: a
//! small per-captive brain that cycles believable idles and reacts to the world, posing the shared
//! biped rig through [`crate::biped::PoseOverride`] with the captive clip family
//! (`player::anim::captive`). Its muffled voice is the sibling trigger `audio::captive`.
//!
//! - **Idles** — a huddle, hugging the knees and rocking, rubbing the arms against the cold, a
//!   despairing slump — each held a randomised 4–17 s, never the same twice running, every change a
//!   smoothstep cross-fade from the last pose (no pops). Breathing, a slow weight settle and a head
//!   that glances about run under all of them.
//! - **The bars** — now and then (far more often when the hero is near and no guard is) ONE captive
//!   per cage gets up (a keyed stand-up with the feet planted), shuffles to its own spot at the
//!   bars (`ork_fortress::CAGE_BAR_SPOTS`: inside the footprint, clear of every bed and cage-mate),
//!   grips them and looks out — or at the hero — then goes back and sits down again.
//! - **Reactions** — a flinch (hands up, duck, head turned from it) when an ork steps up to the
//!   cage, an ork is felled, a blow lands or a roar goes up nearby; fear curls a loose sitter into a
//!   tight rocking hug and sends a captive at the bars back to its straw. Heads follow the hero
//!   (with the odd look away) and nervously track a guard who comes close.
//! - **Desync** — everything is rolled from the captive's own seed: the starting act and timer,
//!   its tempo, how restless it is, the offset of its clock.
//! - **Rescue** — on [`WalkOut`] the captive stands up through the same rise (timed to its
//!   staggered start) and only then reports [`CaptiveLife::upright`], which `walk_out_captives`
//!   waits for; the override cross-fades into the ordinary biped gait and is dropped. Save/load is
//!   untouched — `camps::reconcile_cages_on_load` still despawns a freed cage's captives.
//! - **Cost** — beyond the biped cull radius from the camera the brain sleeps (the rig isn't posed
//!   out there anyway) and the outer band runs every other frame; no per-frame allocation.
//!
//! Debug: `FOREST_CAPTIVE_ACT=huddle|hug|rub|slump|bars` pins every captive to one idle (or sends one
//! per cage to the bars whenever it can) — for framing the poses in a capture.

use std::f32::consts::{PI, TAU};
use std::sync::OnceLock;

use bevy::prelude::*;

use crate::biped::{BipedDrive, PoseOverride};
use crate::player::anim::captive::{self as clip, Life, Seated, RISE_DZ, RISE_SECS, RISE_TUCK, SIT_SECS};
use crate::player::anim::Pose;
use crate::villagers::WalkOut;

/// Seated hips height (rig units) on the realistic cage's flat straw bed (top ≈0.22 world) and on
/// the procedural cage's heaped bedding (≈0.51) — the backside rests on the straw either way.
pub(crate) const SIT_H_FLAT_STRAW: f32 = 0.28;
pub(crate) const SIT_H_HEAPED_STRAW: f32 = 0.60;
/// Shuffle pace inside the cage (world u/s) — stiff from sitting, a short careful stride.
const SHUFFLE_SPEED: f32 = 0.5;
/// Gait phase per world unit shuffled, so the short stride keeps up with the creep (no skating).
const PHASE_PER_U: f32 = 7.2;
/// Turn rate while shuffling / squaring up to the bars or the seat (rad/s).
const TURN_RATE: f32 = 2.4;
/// An ork this close (world u) makes a captive flinch — edge-triggered, re-armed past +0.8 — and
/// sends one at the bars back to its straw.
const FLINCH_R: f32 = 2.6;
/// Fear rises as an ork comes inside this (world u), full ~2.5 u further in (at the bars). A camp
/// cage stands ~3 u from its warband's fire, so jailers lounging there are part of the furniture —
/// it is one stepping UP to the cage that frightens.
const FEAR_R: f32 = 4.0;
/// With an ork this close nobody gets up to go to the bars.
const STAY_SEATED_R: f32 = 3.5;
/// A felled ork / a landed blow / a roar startles captives within this × its strength (world u).
const STARTLE_R: f32 = 9.0;
/// Orks are noticed (fear, a nervous watch) within this range (world u).
const ORK_SENSE_R: f32 = 8.0;
/// The hero is watched within this range (world u) — an armed knight in sight of the cage, not
/// just one at the bars; it also makes a trip to the bars likelier (they want to be seen).
const WATCH_HERO_R: f32 = 14.0;
/// Camera distance bands: full rate inside `LOD_NEAR2`, every other frame out to `LOD_FAR2` (the
/// biped animator's own cull radius, `biped::LIMB_CULL2`), asleep beyond.
const LOD_NEAR2: f32 = 40.0 * 40.0;
const LOD_FAR2: f32 = 70.0 * 70.0;

/// Where one captive lives: its straw seat and its own spot at the bars (world space).
#[derive(Clone, Copy, Debug)]
pub(crate) struct Berth {
    pub(crate) seat: Vec3,
    pub(crate) seat_yaw: f32,
    pub(crate) bars: Vec3,
    pub(crate) bars_yaw: f32,
    /// Cage centre (world XZ) — which captives share a cage (the decor cages share a `CageKey`).
    pub(crate) cage: Vec2,
    /// Seated hips height for this cage's bedding ([`SIT_H_FLAT_STRAW`] / [`SIT_H_HEAPED_STRAW`]).
    pub(crate) sit_h: f32,
}

/// What a captive is doing.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub(crate) enum Act {
    /// One of the seated idles on the straw.
    Sit(Seated),
    /// Standing up off the straw (feet planted), ends [`RISE_DZ`] forward of the seat.
    Rise,
    /// Shuffling to the bars.
    ToBars,
    /// Gripping the bars, looking out.
    Bars,
    /// Shuffling back to the seat.
    FromBars,
    /// Lowering back onto the straw (the stand-up played backwards).
    SitDown,
    /// Freed: upright, handing the body to the walk-out gait.
    Out,
}

/// A root relocation the brain asks for at an act boundary (the body stays put in the world).
#[derive(Clone, Copy, Default, PartialEq, Eq, Debug)]
pub(crate) enum Shift {
    #[default]
    None,
    /// The stand-up finished: the root steps forward under the upright body.
    Stood,
    /// The sit-down starts: the root goes back to the seat.
    Seated,
}

/// What one brain step decided: a cross-fade to start (its length), and a root relocation.
#[derive(Clone, Copy, Default, Debug)]
pub(crate) struct Ev {
    pub(crate) fade: Option<f32>,
    pub(crate) shift: Shift,
}

/// What a captive notices this frame (world space).
#[derive(Clone, Copy, Default, Debug)]
pub(crate) struct Senses {
    /// The hero (feet), if alive.
    pub(crate) hero: Option<Vec3>,
    /// The nearest live ork within [`ORK_SENSE_R`], with its XZ distance.
    pub(crate) ork: Option<(Vec3, f32)>,
    /// The strongest scare in reach this frame: its source and strength 0..1.
    pub(crate) startle: Option<(Vec3, f32)>,
    /// A cage-mate is already up (one at the bars at a time).
    pub(crate) cage_busy: bool,
}

/// `FOREST_CAPTIVE_ACT` debug pin.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum Forced {
    Seat(Seated),
    Bars,
}

fn forced() -> Option<Forced> {
    static F: OnceLock<Option<Forced>> = OnceLock::new();
    *F.get_or_init(|| match std::env::var("FOREST_CAPTIVE_ACT").ok()?.trim() {
        "huddle" => Some(Forced::Seat(Seated::Huddle)),
        "hug" => Some(Forced::Seat(Seated::Hug)),
        "rub" => Some(Forced::Seat(Seated::Rub)),
        "slump" => Some(Forced::Seat(Seated::Slump)),
        "bars" => Some(Forced::Bars),
        _ => None,
    })
}

fn xz(v: Vec3) -> Vec2 {
    Vec2::new(v.x, v.z)
}
fn wrap(a: f32) -> f32 {
    (a + PI).rem_euclid(TAU) - PI
}
fn smooth(t: f32) -> f32 {
    let c = t.clamp(0.0, 1.0);
    c * c * (3.0 - 2.0 * c)
}
fn yaw_of(q: Quat) -> f32 {
    let f = q * Vec3::Z;
    f.x.atan2(f.z)
}

/// Root-frame look angles from an eye at `eye` (root yaw `yaw`) to `target`: (yaw toward rig +X,
/// pitch + = down) — the convention of `Life::look_*`.
fn look_angles(eye: Vec3, yaw: f32, target: Vec3) -> (f32, f32) {
    let d = target - eye;
    let (s, c) = yaw.sin_cos();
    let lx = d.x * c - d.z * s;
    let lz = d.x * s + d.z * c;
    (lx.atan2(lz), -d.y.atan2((lx * lx + lz * lz).sqrt().max(0.01)))
}

/// One frame of the in-cage shuffle: turn toward `to` and creep there (only once roughly facing
/// it — people turn, then step; nobody crabs), then square up to `face`. Returns the new root
/// position + yaw, how much the legs should be stepping (0..1), and whether it has arrived squared.
pub(crate) fn shuffle_step(pos: Vec2, yaw: f32, to: Vec2, face: f32, dt: f32) -> (Vec2, f32, f32, bool) {
    let turn = TURN_RATE * dt;
    let d = to - pos;
    let dist = d.length();
    if dist > 0.02 {
        let err = wrap(d.x.atan2(d.y) - yaw);
        let align = (1.0 - err.abs()).clamp(0.0, 1.0);
        let step = (SHUFFLE_SPEED * align * dt).min(dist);
        (pos + d / dist * step, yaw + err.clamp(-turn, turn), align.max(0.35), false)
    } else {
        let err = wrap(face - yaw);
        if err.abs() < 0.03 {
            return (to, face, 0.0, true);
        }
        (to, yaw + err.clamp(-turn, turn), 0.35, false)
    }
}

/// The per-captive brain: which act, when the next change is due, how scared it is, where it is
/// looking. Pure (no ECS) so the scheduling is unit-tested directly.
#[derive(Clone, Debug)]
pub(crate) struct Mind {
    rng: u32,
    started: bool,
    pub(crate) act: Act,
    since: f32,
    until: f32,
    /// Personal tempo (breathing, rocking, the stand-up's pace).
    tempo: f32,
    /// 0..1 — how readily this one gets up and goes to the bars.
    restless: f32,
    /// Offset of the captive's own clock, so no two breathe or rock in step.
    clock: f32,
    fear: f32,
    want_hug: bool,
    ork_near: bool,
    flinch_at: f32,
    flinch_amp: f32,
    flinch_from: Vec3,
    glance_at: f32,
    glance: Vec2,
    away_until: f32,
    look: Vec2,
    talk_from: f32,
    talk_until: f32,
    style_at: f32,
    grip: (f32, f32),
    press: (f32, f32),
    rattle: (f32, f32),
}

impl Mind {
    pub(crate) fn new(seed: u32) -> Self {
        let mut m = Self {
            rng: seed.wrapping_mul(0x9E37_79B9) | 1,
            started: false,
            act: Act::Sit(Seated::Huddle),
            since: 0.0,
            until: 0.0,
            tempo: 1.0,
            restless: 0.5,
            clock: 0.0,
            fear: 0.0,
            want_hug: false,
            ork_near: false,
            flinch_at: f32::NEG_INFINITY,
            flinch_amp: 0.0,
            flinch_from: Vec3::ZERO,
            glance_at: 0.0,
            glance: Vec2::ZERO,
            away_until: 0.0,
            look: Vec2::ZERO,
            talk_from: 0.0,
            talk_until: 0.0,
            style_at: 0.0,
            grip: (1.0, 1.0),
            press: (0.0, 0.0),
            rattle: (0.0, 0.0),
        };
        m.tempo = m.range(0.82, 1.22);
        m.restless = m.rand();
        m.clock = m.range(0.0, 97.0);
        const START: [Seated; 4] = [Seated::Huddle, Seated::Hug, Seated::Rub, Seated::Slump];
        let first = START[(m.next() % 4) as usize];
        m.act = Act::Sit(match forced() {
            Some(Forced::Seat(k)) => k,
            _ => first,
        });
        m
    }

    fn next(&mut self) -> u32 {
        let s = &mut self.rng;
        *s ^= *s << 13;
        *s ^= *s >> 17;
        *s ^= *s << 5;
        *s
    }
    fn rand(&mut self) -> f32 {
        (self.next() & 0x00ff_ffff) as f32 / 0x0100_0000 as f32
    }
    fn range(&mut self, a: f32, b: f32) -> f32 {
        a + (b - a) * self.rand()
    }

    /// Up off the straw (rising, at/walking to/from the bars, sitting back down).
    pub(crate) fn is_up(&self) -> bool {
        !matches!(self.act, Act::Sit(_))
    }
    pub(crate) fn fear(&self) -> f32 {
        self.fear
    }
    /// Start the talk nod for a muffled line of about `secs` (`audio::captive` calls this).
    pub(crate) fn speak(&mut self, now: f32, secs: f32) {
        self.talk_from = now;
        self.talk_until = now + secs;
    }
    fn talk(&self, now: f32) -> f32 {
        if now >= self.talk_until {
            return 0.0;
        }
        ((now - self.talk_from) / 0.25).clamp(0.0, 1.0) * ((self.talk_until - now) / 0.3).clamp(0.0, 1.0)
    }
    fn rise_secs(&self) -> f32 {
        RISE_SECS / self.tempo
    }
    pub(crate) fn rise_p(&self, now: f32) -> f32 {
        ((now - self.since - RISE_TUCK) / self.rise_secs()).clamp(0.0, 1.0)
    }
    pub(crate) fn down_p(&self, now: f32) -> f32 {
        ((now - self.since) / (SIT_SECS / self.tempo)).clamp(0.0, 1.0)
    }
    /// The bars grip style, smoothed: (second hand on, lean in, rattle).
    pub(crate) fn bars_style(&self) -> (f32, f32, f32) {
        (self.grip.1, self.press.1, self.rattle.1)
    }

    fn go(&mut self, now: f32, act: Act, fade: f32, ev: &mut Ev) {
        self.act = act;
        self.since = now;
        ev.fade = Some(fade);
    }
    fn sit(&mut self, now: f32, kind: Seated, fade: f32, ev: &mut Ev) {
        self.go(now, Act::Sit(kind), fade, ev);
        self.until = now + match kind {
            Seated::Huddle => self.range(6.0, 13.0),
            Seated::Hug => self.range(7.0, 15.0),
            Seated::Rub => self.range(4.0, 8.0),
            Seated::Slump => self.range(9.0, 17.0),
        };
    }

    /// The next seated idle: weighted (fear favours the hug, despair fades with it), never the
    /// one just played.
    fn pick_seat(&mut self, current: Option<Seated>) -> Seated {
        if let Some(Forced::Seat(k)) = forced() {
            return k;
        }
        if std::mem::take(&mut self.want_hug) && current != Some(Seated::Hug) {
            return Seated::Hug;
        }
        let f = self.fear;
        let w = [
            (Seated::Huddle, 3.0),
            (Seated::Hug, 2.0 + 4.0 * f),
            (Seated::Rub, 1.6),
            (Seated::Slump, (2.2 - 2.0 * f).max(0.4)),
        ];
        let total: f32 = w.iter().filter(|(k, _)| Some(*k) != current).map(|(_, x)| x).sum();
        let mut r = self.rand() * total;
        for (k, x) in w {
            if Some(k) == current {
                continue;
            }
            if r < x {
                return k;
            }
            r -= x;
        }
        if current == Some(Seated::Hug) { Seated::Huddle } else { Seated::Hug }
    }

    /// Get up and go to the bars? Never while scared, with a guard close or a cage-mate already
    /// up; otherwise a modest roll per act change — two and a half times likelier with the hero
    /// in sight (they want to be seen).
    fn wants_bars(&mut self, s: &Senses, here: Vec3) -> bool {
        match forced() {
            Some(Forced::Bars) => return !s.cage_busy,
            Some(Forced::Seat(_)) => return false,
            None => {}
        }
        if s.cage_busy || self.fear > 0.3 || s.ork.is_some_and(|(_, d)| d < STAY_SEATED_R) {
            return false;
        }
        let mut chance = 0.10 + 0.14 * self.restless;
        if s.hero.is_some_and(|h| xz(h).distance(xz(here)) < WATCH_HERO_R) {
            chance *= 2.5;
        }
        self.rand() < chance
    }

    fn startle(&mut self, now: f32, k: f32, from: Vec3) {
        if now - self.flinch_at < 0.9 {
            return; // mid-flinch: one startle at a time
        }
        self.flinch_at = now;
        self.flinch_amp = k.clamp(0.0, 1.0);
        self.flinch_from = from;
        self.fear = self.fear.max(0.55 * k);
    }

    /// Fear from the nearest guard + this frame's scares.
    fn feel(&mut self, now: f32, dt: f32, s: &Senses) {
        let near = s.ork.map_or(0.0, |(_, d)| ((FEAR_R - d) / 2.5).clamp(0.0, 1.0));
        if near > self.fear {
            self.fear += (near - self.fear) * (1.0 - (-3.0 * dt).exp());
        } else {
            self.fear = (self.fear - 0.08 * dt).max(near);
        }
        match s.ork {
            Some((p, d)) if d < FLINCH_R && !self.ork_near => {
                self.ork_near = true;
                self.startle(now, 1.0, p + Vec3::Y * 1.3);
            }
            Some((_, d)) if d > FLINCH_R + 0.8 => self.ork_near = false,
            None => self.ork_near = false,
            _ => {}
        }
        if let Some((p, k)) = s.startle {
            self.startle(now, k, p);
        }
    }

    /// One brain step: act changes (timers, arrivals, fear, a release). `release` = the walk-out's
    /// start time once freed; `arrived` = the shuffle reached its goal this frame.
    pub(crate) fn update(&mut self, now: f32, dt: f32, here: Vec3, s: &Senses, arrived: bool, release: Option<f32>) -> Ev {
        let mut ev = Ev::default();
        if !self.started {
            self.started = true;
            self.since = now;
            self.until = now + self.range(1.0, 7.0); // staggered first change
            self.glance_at = now + self.range(0.3, 2.5);
        }
        self.feel(now, dt, s);
        if let Some(start) = release {
            match self.act {
                Act::Sit(_) if now >= start - RISE_TUCK => self.go(now, Act::Rise, 0.45, &mut ev),
                Act::ToBars | Act::Bars | Act::FromBars => self.go(now, Act::Out, 0.45, &mut ev),
                Act::SitDown => {
                    // Caught half-way down: straight back up from where the body is.
                    let p = 1.0 - self.down_p(now);
                    self.go(now, Act::Rise, 0.25, &mut ev);
                    self.since = now - RISE_TUCK - p * self.rise_secs();
                }
                Act::Rise if self.rise_p(now) >= 1.0 => {
                    self.go(now, Act::Out, 0.35, &mut ev);
                    ev.shift = Shift::Stood;
                }
                _ => {}
            }
            return ev;
        }
        match self.act {
            Act::Sit(kind) => {
                // A scare curls a loose sitter up tight, quickly.
                if self.fear > 0.55 && matches!(kind, Seated::Huddle | Seated::Rub) && self.until > now + 0.6 {
                    self.until = now + 0.6;
                    self.want_hug = true;
                }
                if now >= self.until {
                    if self.wants_bars(s, here) {
                        self.go(now, Act::Rise, 0.5, &mut ev);
                    } else {
                        let k = self.pick_seat(Some(kind));
                        self.sit(now, k, 1.3, &mut ev);
                    }
                }
            }
            Act::Rise => {
                if self.rise_p(now) >= 1.0 {
                    self.go(now, Act::ToBars, 0.35, &mut ev);
                    ev.shift = Shift::Stood;
                }
            }
            Act::ToBars => {
                if self.fear > 0.6 {
                    self.go(now, Act::FromBars, 0.4, &mut ev); // thinks better of it
                } else if arrived {
                    self.go(now, Act::Bars, 0.7, &mut ev);
                    self.until = now + if forced() == Some(Forced::Bars) { 1.0e6 } else { self.range(5.0, 10.0) };
                    self.style_at = now;
                }
            }
            Act::Bars => {
                let guard_close = s.ork.is_some_and(|(_, d)| d < FLINCH_R);
                if now >= self.until || guard_close || self.fear > 0.6 {
                    self.go(now, Act::FromBars, 0.5, &mut ev);
                }
            }
            Act::FromBars => {
                if arrived {
                    self.go(now, Act::SitDown, 0.3, &mut ev);
                    ev.shift = Shift::Seated;
                }
            }
            Act::SitDown => {
                if self.down_p(now) >= 1.0 {
                    let k = self.pick_seat(None);
                    self.sit(now, k, 0.8, &mut ev);
                }
            }
            Act::Out => {}
        }
        ev
    }

    /// The smoothed "life" signals for the clips: where the head looks (a scare → the hero → an
    /// idle glance), the flinch envelope, fear, the talk nod, the bars style.
    pub(crate) fn life(&mut self, now: f32, dt: f32, here: Vec3, yaw: f32, s: &Senses) -> Life {
        if now >= self.glance_at {
            // A new place to rest the eyes every few seconds; near the hero, now and then a look
            // away (down, aside) — nobody stares unblinking.
            self.glance_at = now + self.range(1.8, 5.5);
            let down = if self.act == Act::Sit(Seated::Slump) { 0.25 } else { 0.0 };
            self.glance = Vec2::new(self.range(-0.95, 0.95), self.range(-0.08, 0.28) + down);
            if self.rand() < 0.3 {
                self.away_until = now + self.range(1.2, 2.6);
            }
        }
        let standing = matches!(self.act, Act::ToBars | Act::Bars | Act::FromBars | Act::Out);
        let moving = matches!(self.act, Act::Rise | Act::ToBars | Act::FromBars | Act::SitDown);
        let eye = here + Vec3::Y * if standing { 1.3 } else { 0.8 };
        let since_flinch = now - self.flinch_at;
        let talk = self.talk(now);
        let target = if self.act == Act::Out {
            None
        } else if since_flinch < 1.4 {
            Some(self.flinch_from)
        } else if self.fear > 0.25 && s.ork.is_some_and(|(_, d)| d < 6.0) {
            s.ork.map(|(p, _)| p + Vec3::Y * 1.5)
        } else if moving || (now < self.away_until && talk < 0.1) {
            None
        } else {
            s.hero.filter(|h| xz(*h).distance(xz(here)) < WATCH_HERO_R).map(|h| h + Vec3::Y * 1.55)
        };
        let mut want = if moving || self.act == Act::Out { Vec2::new(0.0, 0.1) } else { self.glance };
        if let Some(p) = target {
            let (y, pitch) = look_angles(eye, yaw, p);
            if y.abs() < 2.0 {
                want = Vec2::new(y, pitch); // not behind the back
            }
        }
        let lim = if standing { 1.1 } else { 1.3 };
        want = Vec2::new(want.x.clamp(-lim, lim), want.y.clamp(-0.45, 0.45));
        let rate = if since_flinch < 0.6 { 8.0 } else { 2.8 };
        self.look += (want - self.look) * (1.0 - (-rate * dt).exp());

        // Bars style: re-rolled every few seconds — sometimes one hand drops, sometimes a lean
        // into the gap, now and then a desperate shake (always while pleading).
        if self.act == Act::Bars {
            if now >= self.style_at {
                self.style_at = now + self.range(2.0, 5.0);
                self.grip.0 = if self.rand() < 0.25 { 0.0 } else { 1.0 };
                self.press.0 = if self.rand() < 0.3 { 1.0 } else { 0.0 };
                self.rattle.0 = if self.rand() < 0.12 { 1.0 } else { 0.0 };
            }
        } else {
            self.grip.0 = 1.0;
            self.press.0 = 0.0;
            self.rattle.0 = 0.0;
        }
        let k = 1.0 - (-3.0 * dt).exp();
        self.grip.1 += (self.grip.0 - self.grip.1) * k;
        self.press.1 += (self.press.0 - self.press.1) * k;
        self.rattle.1 += (self.rattle.0.max(talk) - self.rattle.1) * k;

        let e = since_flinch;
        let flinch = if e >= 0.0 && e < 6.0 { smooth(e / 0.08) * (-(e - 0.08).max(0.0) * 2.4).exp() * self.flinch_amp } else { 0.0 };
        let side = {
            let (y, _) = look_angles(here, yaw, self.flinch_from);
            y.sin().signum() * y.sin().abs().sqrt()
        };
        let calm = if self.act == Act::Out { 0.0 } else { 1.0 };
        Life {
            t: now + self.clock,
            tempo: self.tempo,
            fear: self.fear,
            look_yaw: self.look.x,
            look_pitch: self.look.y,
            flinch: flinch * calm,
            flinch_side: side,
            talk: talk * calm,
        }
    }
}

/// A caged captive's idle life: its berth, its brain, and the cross-fade bookkeeping that keeps
/// every act change pop-free. Lives on the captive root next to [`crate::villagers::Captive`].
#[derive(Component)]
pub(crate) struct CaptiveLife {
    pub(crate) berth: Berth,
    pub(crate) mind: Mind,
    /// The last RAW (pre-overlay) pose shown — what an act change cross-fades from.
    last: Pose,
    from: Pose,
    fade_at: f32,
    fade_len: f32,
    walk_phase: f32,
    gait: f32,
    gait_to: f32,
    last_tick: Option<f32>,
    parity: u32,
}

impl CaptiveLife {
    pub(crate) fn new(berth: Berth, seed: u32) -> Self {
        let mind = Mind::new(seed);
        let first = match mind.act {
            Act::Sit(k) => clip::seated(k, berth.sit_h, &Life::default()),
            _ => clip::rise(0.0, berth.sit_h),
        };
        Self {
            berth,
            mind,
            last: first,
            from: first,
            fade_at: 0.0,
            fade_len: 0.0,
            walk_phase: 0.0,
            gait: 0.0,
            gait_to: 0.0,
            last_tick: None,
            parity: seed & 1,
        }
    }
    /// The pose to spawn with (before the first tick).
    pub(crate) fn first_pose(&self) -> Pose {
        self.last
    }
    /// Freed and standing — the walk-out may set off.
    pub(crate) fn upright(&self) -> bool {
        self.mind.act == Act::Out
    }
    /// Where the stand-up leaves the root: the seat + [`RISE_DZ`] forward (world XZ).
    fn stand_point(&self, scale: f32) -> Vec2 {
        let y = self.berth.seat_yaw;
        xz(self.berth.seat) + Vec2::new(y.sin(), y.cos()) * RISE_DZ * scale
    }
    /// The shuffle's goal (position, final facing) for the walking acts.
    fn goal(&self, scale: f32) -> Option<(Vec2, f32)> {
        match self.mind.act {
            Act::ToBars => Some((xz(self.berth.bars), self.berth.bars_yaw)),
            Act::FromBars => Some((self.stand_point(scale), self.berth.seat_yaw)),
            _ => None,
        }
    }

    fn raw_pose(&self, now: f32, l: &Life, d: &BipedDrive) -> Pose {
        let m = &self.mind;
        match m.act {
            Act::Sit(k) => clip::seated(k, self.berth.sit_h, l),
            Act::Rise => clip::rise(m.rise_p(now), self.berth.sit_h),
            Act::SitDown => clip::rise(1.0 - m.down_p(now), self.berth.sit_h),
            Act::ToBars | Act::FromBars => clip::shuffle(l, self.walk_phase, self.gait),
            Act::Bars => {
                let (grip, press, rattle) = m.bars_style();
                clip::bars(l, grip, press, rattle)
            }
            Act::Out if d.sitting => clip::shuffle(l, self.walk_phase, 0.0),
            Act::Out => crate::biped::biped_pose(d, now),
        }
    }

    /// One brain + body step: the in-cage shuffle moves the root `tf`, the brain decides, the
    /// stand-up / sit-down relocate the root (re-expressing the last pose so nothing jumps), and
    /// the cross-faded, overlaid pose to show comes back.
    pub(crate) fn tick(&mut self, now: f32, tf: &mut Transform, s: &Senses, release: Option<f32>, d: &BipedDrive) -> Pose {
        let dt = self.last_tick.map_or(0.0, |t| (now - t).clamp(0.0, 0.25));
        self.last_tick = Some(now);
        let scale = tf.scale.x;

        let mut arrived = false;
        let yaw0 = yaw_of(tf.rotation);
        if let Some((to, face)) = self.goal(scale) {
            let pos0 = xz(tf.translation);
            let (pos, yaw, gait, done) = shuffle_step(pos0, yaw0, to, face, dt);
            tf.translation.x = pos.x;
            tf.translation.z = pos.y;
            tf.rotation = Quat::from_rotation_y(yaw);
            self.walk_phase += pos.distance(pos0) / scale.max(0.1) * 0.81 * PHASE_PER_U + wrap(yaw - yaw0).abs() * 0.9;
            self.gait_to = gait;
            arrived = done;
        } else {
            self.gait_to = 0.0;
        }

        let ev = self.mind.update(now, dt, tf.translation, s, arrived, release);
        match ev.shift {
            Shift::Stood => {
                let fwd = tf.rotation * Vec3::Z;
                tf.translation += fwd * RISE_DZ * scale;
                clip::shift(&mut self.last, Vec3::new(0.0, 0.0, -RISE_DZ));
            }
            Shift::Seated => {
                let seat = self.berth.seat;
                let rot = Quat::from_rotation_y(self.berth.seat_yaw);
                let delta = rot.inverse() * (tf.translation - seat) / scale.max(0.1);
                tf.translation = seat;
                tf.rotation = rot;
                clip::shift(&mut self.last, delta);
            }
            Shift::None => {}
        }
        if let Some(len) = ev.fade {
            self.from = self.last;
            self.fade_at = now;
            self.fade_len = len;
        }
        self.gait += (self.gait_to - self.gait) * (1.0 - (-6.0 * dt).exp());

        let l = self.mind.life(now, dt, tf.translation, yaw_of(tf.rotation), s);
        let raw = self.raw_pose(now, &l, d);
        let k = if self.fade_len > 0.0 { smooth((now - self.fade_at) / self.fade_len) } else { 1.0 };
        let base = if k < 1.0 { clip::blend(&self.from, &raw, k) } else { raw };
        self.last = base;
        let mut pose = base;
        clip::apply_life(&mut pose, &l);
        if self.mind.act == Act::Out {
            // Freed: let go of the idle overlays (breath, look) over ~0.6 s, so by the time the
            // override is dropped the body is already exactly the plain biped gait — no pop.
            pose = clip::blend(&pose, &base, smooth((now - self.mind.since) / 0.6));
        }
        pose
    }
}

/// Run every captive's idle life and write its pose override. Sim-tier (it walks roots inside the
/// cage), so it is `Modal::None`-gated; a paused world just holds the last pose.
#[allow(clippy::type_complexity, clippy::too_many_arguments)]
pub(crate) fn captive_life(
    time: Res<Time>,
    hero: Option<Res<crate::player::HeroState>>,
    cam: Query<&GlobalTransform, With<Camera3d>>,
    orks: Query<&GlobalTransform, (With<crate::orks::Ork>, Without<crate::dying::Dying>)>,
    felled: Query<&GlobalTransform, (With<crate::orks::Ork>, Added<crate::dying::Dying>)>,
    mut cues: MessageReader<crate::audio::AudioCue>,
    mut q: Query<(Entity, &mut CaptiveLife, &mut Transform, &mut PoseOverride, &BipedDrive, Option<&WalkOut>)>,
    mut commands: Commands,
    mut busy: Local<Vec<Vec2>>,
    mut scares: Local<Vec<(Vec3, f32)>>,
    mut frame: Local<u32>,
) {
    use crate::audio::AudioCue as Cue;
    let now = time.elapsed_secs();
    *frame = frame.wrapping_add(1);
    let cam_p = cam.iter().next().map(|g| g.translation());
    let hero_p = hero.as_ref().filter(|h| h.alive).map(|h| Vec3::new(h.pos.x, h.y, h.pos.y));

    // This frame's scares: a felled ork, the hero's blows landing (or him getting hit), roars.
    scares.clear();
    scares.extend(felled.iter().map(|g| (g.translation(), 1.0)));
    for cue in cues.read() {
        match cue {
            Cue::Impact { kill, .. } => scares.extend(hero_p.map(|h| (h + Vec3::Y, if *kill { 0.8 } else { 0.55 }))),
            Cue::HeroHurt => scares.extend(hero_p.map(|h| (h + Vec3::Y, 0.5))),
            Cue::OrkRoar(p) | Cue::BossRoar(p) => scares.push((*p, 0.9)),
            Cue::OrkGrunt(p) | Cue::GuardStrike(p) => scares.push((*p, 0.45)),
            _ => {}
        }
    }
    // Cages with someone already up — one captive at the bars per cage at a time.
    busy.clear();
    busy.extend(q.iter().filter(|(_, l, ..)| l.mind.is_up()).map(|(_, l, ..)| l.berth.cage));

    for (e, mut life, mut tf, mut over, drive, walk) in &mut q {
        let release = walk.map(|w| w.start);
        // LOD: a captive being freed always runs (the walk-out waits on its stand-up).
        if release.is_none() {
            if let Some(cp) = cam_p {
                let d2 = tf.translation.distance_squared(cp);
                if d2 > LOD_FAR2 || (d2 > LOD_NEAR2 && (*frame + life.parity) % 2 == 1) {
                    continue;
                }
            }
        }
        let here = tf.translation;
        let mut ork: Option<(Vec3, f32)> = None;
        for g in &orks {
            let p = g.translation();
            let d = xz(p).distance(xz(here));
            if d < ORK_SENSE_R && ork.is_none_or(|(_, bd)| d < bd) {
                ork = Some((p, d));
            }
        }
        let startle = scares
            .iter()
            .filter_map(|&(p, k)| {
                let reach = STARTLE_R * k;
                let d = xz(p).distance(xz(here));
                (d < reach).then(|| (p, k * (1.0 - d / reach).clamp(0.35, 1.0)))
            })
            .max_by(|a, b| a.1.total_cmp(&b.1));
        let was_up = life.mind.is_up();
        let senses = Senses { hero: hero_p, ork, startle, cage_busy: !was_up && busy.contains(&life.berth.cage) };
        over.0 = life.tick(now, &mut tf, &senses, release, drive);
        if !was_up && life.mind.is_up() {
            busy.push(life.berth.cage); // claimed the bars this frame
        }
        // Freed, upright and walking for a beat: hand the rig back to the ordinary biped drive.
        if life.upright() && !drive.sitting && now - life.mind.since > 1.2 {
            commands.entity(e).try_remove::<(PoseOverride, CaptiveLife)>();
        }
    }
}

pub struct CaptivesPlugin;

impl Plugin for CaptivesPlugin {
    fn build(&self, app: &mut App) {
        app.add_systems(
            Update,
            captive_life.before(crate::biped::animate_biped).run_if(in_state(crate::game_state::Modal::None)),
        );
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ork_fortress::{CAGE_BAR_SPOTS, CAGE_SEATS, CAGE_W};

    const DT: f32 = 1.0 / 30.0;
    const SCALE: f32 = 0.81;

    /// Seat `i` of a cage at the origin (unrotated), on the realistic straw.
    fn berth(i: usize) -> Berth {
        let (sx, sz, syaw) = CAGE_SEATS[i];
        let (bx, bz, byaw) = CAGE_BAR_SPOTS[i];
        Berth {
            seat: Vec3::new(sx, 0.148, sz),
            seat_yaw: syaw,
            bars: Vec3::new(bx, 0.148, bz),
            bars_yaw: byaw,
            cage: Vec2::ZERO,
            sit_h: SIT_H_FLAT_STRAW,
        }
    }
    fn root(b: &Berth) -> Transform {
        Transform { translation: b.seat, rotation: Quat::from_rotation_y(b.seat_yaw), scale: Vec3::splat(SCALE) }
    }

    /// Run one captive for `secs`, returning every act it entered (in order) and the root track.
    fn run(seed: u32, i: usize, secs: f32, senses: impl Fn(f32) -> Senses) -> (Vec<(f32, Act)>, Vec<Vec3>) {
        let b = berth(i);
        let mut life = CaptiveLife::new(b, seed);
        let mut tf = root(&b);
        let d = BipedDrive { sitting: true, ..default() };
        let mut acts = vec![(0.0, life.mind.act)];
        let mut track = Vec::new();
        let mut t = 0.0;
        while t < secs {
            let pose = life.tick(t, &mut tf, &senses(t), None, &d);
            assert!(pose.get(crate::player::Joint::Head).r.is_finite());
            if acts.last().unwrap().1 != life.mind.act {
                acts.push((t, life.mind.act));
            }
            track.push(tf.translation);
            t += DT;
        }
        (acts, track)
    }

    fn hero_near(_: f32) -> Senses {
        Senses { hero: Some(Vec3::new(3.5, 0.0, 0.5)), ..default() }
    }

    #[test]
    fn seeds_desynchronise_the_idles() {
        let (a, _) = run(11, 0, 90.0, |_| Senses::default());
        let (b, _) = run(12, 0, 90.0, |_| Senses::default());
        assert!(a.len() >= 6 && b.len() >= 6, "both keep changing what they do: {} / {}", a.len(), b.len());
        let ta: Vec<i32> = a.iter().map(|(t, _)| (*t * 10.0) as i32).collect();
        let tb: Vec<i32> = b.iter().map(|(t, _)| (*t * 10.0) as i32).collect();
        assert_ne!(ta, tb, "two captives must not change act in lockstep");
        // …and their clocks differ, so breathing / rocking are out of phase too.
        let (mut ma, mut mb) = (Mind::new(11), Mind::new(12));
        let la = ma.life(1.0, DT, Vec3::ZERO, 0.0, &Senses::default());
        let lb = mb.life(1.0, DT, Vec3::ZERO, 0.0, &Senses::default());
        assert!((la.t - lb.t).abs() > 0.5 && (la.tempo - lb.tempo).abs() > 1e-3);
    }

    #[test]
    fn a_seated_idle_never_repeats_back_to_back() {
        for seed in 1..20 {
            let (acts, _) = run(seed, 1, 120.0, |_| Senses::default());
            let seats: Vec<Act> = acts.iter().map(|(_, a)| *a).collect();
            for w in seats.windows(2) {
                assert_ne!(w[0], w[1], "seed {seed}: {seats:?}");
            }
        }
    }

    #[test]
    fn trips_to_the_bars_complete_in_order_and_stay_inside_the_cage() {
        let mut trips = 0;
        for seed in 1..12 {
            for i in 0..3 {
                let (acts, track) = run(seed * 7 + i as u32, i, 240.0, hero_near);
                for w in acts.windows(2) {
                    let ok = match (w[0].1, w[1].1) {
                        (Act::Sit(_), Act::Sit(_) | Act::Rise) => true,
                        (Act::Rise, Act::ToBars) | (Act::ToBars, Act::Bars | Act::FromBars) => true,
                        (Act::Bars, Act::FromBars) | (Act::FromBars, Act::SitDown) | (Act::SitDown, Act::Sit(_)) => true,
                        _ => false,
                    };
                    assert!(ok, "seed {seed} seat {i}: bad transition {:?} → {:?}", w[0].1, w[1].1);
                }
                trips += acts.iter().filter(|(_, a)| *a == Act::Bars).count();
                let lim = CAGE_W / 2.0 - 0.2;
                for p in &track {
                    assert!(p.x.abs() < lim + 0.07 && p.z.abs() < lim, "seed {seed} seat {i}: root left the cage at {p:?}");
                }
            }
        }
        assert!(trips >= 5, "with the hero watching, captives do get up to the bars (got {trips})");
    }

    #[test]
    fn a_busy_cage_or_a_close_guard_keeps_everyone_seated() {
        let busy = |_: f32| Senses { hero: Some(Vec3::new(3.0, 0.0, 0.0)), cage_busy: true, ..default() };
        let guard = |_: f32| Senses { hero: Some(Vec3::new(3.0, 0.0, 0.0)), ork: Some((Vec3::new(1.8, 0.0, 0.0), 2.4)), ..default() };
        for seed in 1..10 {
            for senses in [&busy as &dyn Fn(f32) -> Senses, &guard] {
                let (acts, _) = run(seed, 0, 200.0, senses);
                assert!(acts.iter().all(|(_, a)| matches!(a, Act::Sit(_))), "seed {seed}: {acts:?}");
            }
        }
    }

    #[test]
    fn an_ork_stepping_up_makes_them_flinch_once_and_curl_up() {
        let mut m = Mind::new(5);
        let here = Vec3::new(0.0, 0.15, 0.0);
        let mut peak = 0.0f32;
        let mut flinches = 0;
        let mut was = 0.0;
        let mut t = 0.0f32;
        while t < 12.0 {
            // Walks in from 6u, then loiters 1.8u off for the rest of the run.
            let d = (6.0 - t * 2.0).max(1.8);
            let s = Senses { ork: Some((Vec3::new(d, 0.0, 0.0), d)), ..default() };
            m.update(t, DT, here, &s, false, None);
            let l = m.life(t, DT, here, 0.0, &s);
            if l.flinch > 0.3 && was <= 0.3 {
                flinches += 1;
            }
            was = l.flinch;
            peak = peak.max(l.flinch);
            t += DT;
        }
        assert!(peak > 0.8, "a guard at the bars is a real scare");
        assert_eq!(flinches, 1, "one flinch per approach, not a seizure while he loiters");
        assert!(m.fear() > 0.8);
        assert_eq!(m.act, Act::Sit(Seated::Hug), "fear curls the captive into a hug");
    }

    #[test]
    fn freeing_stands_them_up_before_the_walk_out() {
        for (seed, start_at_bars) in [(3, false), (4, true)] {
            let b = berth(1);
            let mut life = CaptiveLife::new(b, seed);
            let mut tf = root(&b);
            let d = BipedDrive { sitting: true, ..default() };
            let mut t = 0.0;
            if start_at_bars {
                // Walk it to the bars first.
                let s = |_: f32| Senses::default();
                life.mind.act = Act::ToBars;
                life.mind.since = 0.0;
                while life.mind.act != Act::Bars && t < 20.0 {
                    life.tick(t, &mut tf, &s(t), None, &d);
                    t += DT;
                }
                assert_eq!(life.mind.act, Act::Bars);
            }
            let start = t + 1.1;
            let mut upright_at = None;
            while t < start + 6.0 {
                life.tick(t, &mut tf, &Senses::default(), Some(start), &d);
                if life.upright() && upright_at.is_none() {
                    upright_at = Some(t);
                }
                t += DT;
            }
            let up = upright_at.expect("a freed captive gets up");
            if start_at_bars {
                assert!(up < start, "already standing at the bars → free to go at once");
            } else {
                assert!(up > start && up < start + RISE_SECS * 1.4 + 0.2, "stands up after its start beat: {up} vs {start}");
                // The stand-up moved the root forward onto the stand point, inside the cage.
                assert!(xz(tf.translation).distance(life.stand_point(SCALE)) < 1e-3);
            }
        }
    }

    #[test]
    fn a_freed_captive_hands_off_to_the_plain_biped_gait_without_a_pop() {
        use crate::player::Joint;
        let b = berth(0);
        let mut life = CaptiveLife::new(b, 9);
        let mut tf = root(&b);
        let mut d = BipedDrive { sitting: true, ..default() };
        let start = 1.0;
        let (mut t, mut prev, mut out_at) = (0.0f32, None::<Pose>, None);
        while out_at.is_none_or(|o| t < o + 1.25) {
            if t >= start {
                d.sitting = false; // what `walk_out_captives` does at the walk-out's start
            }
            let p = life.tick(t, &mut tf, &Senses::default(), Some(start), &d);
            if let Some(q) = prev {
                // The stand-up's arm swing is brisk (~4 rad/s); the hand-off itself must be gentle.
                let max = if out_at.is_some() { 0.08 } else { 0.25 };
                for j in [Joint::Hips, Joint::Torso, Joint::Head, Joint::ShoulderL, Joint::KneeR] {
                    let step = p.get(j).r.angle_between(q.get(j).r);
                    assert!(step < max, "t={t:.2}: {j:?} jumps {step} rad in one frame");
                }
            }
            if life.upright() && out_at.is_none() {
                out_at = Some(t);
            }
            prev = Some(p);
            t += DT;
            assert!(t < 10.0, "never got up");
        }
        // When `captive_life` drops the override (1.2 s into Out) the pose already IS the gait.
        let plain = crate::biped::biped_pose(&d, t - DT);
        for j in [Joint::Torso, Joint::Head, Joint::ShoulderL, Joint::ElbowR, Joint::HipL, Joint::KneeR] {
            let off = prev.unwrap().get(j).r.angle_between(plain.get(j).r);
            assert!(off < 5e-3, "{j:?} off by {off}"); // acos round-off near 1 is ~1e-3
        }
    }

    #[test]
    fn bar_spots_are_inside_the_cage_and_clear_of_the_beds() {
        let half = CAGE_W / 2.0;
        for (i, (bx, bz, byaw)) in CAGE_BAR_SPOTS.iter().enumerate() {
            let spot = Vec2::new(*bx, *bz);
            // Clear of the frame by more than a body's half-width (shoulders ≈ ±0.16 world).
            assert!(spot.x.abs() < half - 0.25 && spot.y.abs() < half - 0.25, "spot {i} sits inside the footprint");
            // ~0.36 from the bar plane it faces (the door hangs 0.07 proud of the frame).
            let fwd = Vec2::new(byaw.sin(), byaw.cos());
            let plane = if fwd.x > 0.5 { half + 0.07 } else { half };
            let to_bars = plane - spot.dot(fwd);
            assert!((0.3..0.45).contains(&to_bars), "spot {i}: {to_bars} from the bars");
            for (j, (sx, sz, _)) in CAGE_SEATS.iter().enumerate() {
                let d = spot.distance(Vec2::new(*sx, *sz));
                let need = if i == j { 0.44 } else { 1.0 }; // own bed: just off the straw (r ≈ 0.36)
                assert!(d >= need, "spot {i} vs seat {j}: {d}");
            }
            // Its stand point (where the walk to the bars starts) is inside too.
            let b = berth(i);
            let life = CaptiveLife::new(b, 1);
            let sp = life.stand_point(SCALE);
            assert!(sp.x.abs() < half - 0.25 && sp.y.abs() < half - 0.25);
        }
    }

    #[test]
    fn the_shuffle_turns_then_creeps_then_squares_up() {
        let (mut pos, mut yaw) = (Vec2::new(-0.3, 0.37), 1.25);
        let (to, face) = (Vec2::new(-0.74, -0.48), -PI / 2.0);
        let mut done = false;
        for _ in 0..400 {
            let (p, y, _, d) = shuffle_step(pos, yaw, to, face, DT);
            assert!(p.distance(pos) <= SHUFFLE_SPEED * DT + 1e-4, "no teleporting");
            (pos, yaw, done) = (p, y, d);
            if done {
                break;
            }
        }
        assert!(done && pos.distance(to) < 1e-4 && wrap(yaw - face).abs() < 1e-4);
    }
}
