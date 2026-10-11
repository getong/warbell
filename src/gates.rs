//! **Gate mechanics** (castle v2 spec §5): the three castle gates close at dusk — when the war
//! bell starts the night (`siege::GamePhase::Wave`) — and open again at dawn.
//!
//! - With `walls && gate` (the Gate upgrade) the opening shuts with two oak leaves
//!   ([`WOOD_GATE_HP`]); with walls but no Gate upgrade a wagon barricade is dragged into the gap
//!   at night ([`BARRICADE_HP`]); with no walls there is nothing to close.
//! - A shut gate is solid for **orks only**: their A* treats its gap as a wall
//!   ([`Gates::ork_boxes`] → `navgrid::path_to_avoiding`) and the invader brain refuses any step into
//!   it ([`Gates::blocks_ork`]). The hero, the militia and the townsfolk pass freely — the watch
//!   swings a leaf for them ([`drive_gate_visuals`] opens the leaves while a friend is in the gap),
//!   so nobody is ever trapped outside or inside.
//! - With every route shut, invaders march on the nearest shut gate ([`Gates::ork_goal`]; the
//!   southern horde's nearest is the S gate) and hack it down. A broken gate stays open (leaves
//!   gone) until dawn, when it is rebuilt for free.
//!
//! State lives in the [`Gates`] resource (pure, unit-tested); the leaves / barricades / HP markers
//! are spawned with the castle (`castle::build` → [`build`]).

use bevy::prelude::*;

use crate::biome::BiomeEntity;
use crate::castle::{bake, bx, Gate, Mats, GATE_GAP, GATE_H, M, WALL_THICK};

/// Oak gate hit points (tune with the Gates upgrade track later).
pub const WOOD_GATE_HP: f32 = 600.0;
/// Wagon barricade hit points (the no-Gate-upgrade stopgap).
pub const BARRICADE_HP: f32 = 250.0;
/// Seconds for the leaves to swing fully shut / open.
const SWING_SECS: f32 = 3.0;
/// Half the clear opening between the gate posts (posts are 0.9 wide, centred on ±GATE_GAP/2).
pub const OPEN_HALF: f32 = GATE_GAP / 2.0 - 0.45;
/// Half-depth of the gap box an ork may not enter while the gate is shut (wall half-thickness +
/// a stride either side, so a body can't wedge into the passage).
const GAP_DEPTH: f32 = WALL_THICK / 2.0 + 0.35;
/// An invader within this of a shut gate's centre (outside it) is close enough to hack it.
pub const HACK_RANGE: f32 = 3.4;
/// How far out from the gate centre the hacking crowd aims (just past the wall face).
const HACK_STANDOFF: f32 = WALL_THICK / 2.0 + 1.1;

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum GateKind {
    /// No walls — nothing to close.
    None,
    /// Walls but no Gate upgrade: a wagon barricade at night.
    Barricade,
    /// Walls + Gate upgrade: two oak leaves.
    Wood,
}

impl GateKind {
    pub fn from_defenses(walls: bool, gate: bool) -> Self {
        match (walls, gate) {
            (true, true) => GateKind::Wood,
            (true, false) => GateKind::Barricade,
            _ => GateKind::None,
        }
    }
    pub fn max_hp(self) -> f32 {
        match self {
            GateKind::Wood => WOOD_GATE_HP,
            GateKind::Barricade => BARRICADE_HP,
            GateKind::None => 0.0,
        }
    }
}

/// One gate's live state.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct GateRt {
    pub kind: GateKind,
    /// Ordered shut (night). The leaves animate toward it; orks treat it as solid at once.
    pub closed: bool,
    /// Hacked down tonight — open (passable) until dawn.
    pub broken: bool,
    pub hp: f32,
    pub max: f32,
}

impl GateRt {
    const fn open() -> Self {
        GateRt { kind: GateKind::None, closed: false, broken: false, hp: 0.0, max: 0.0 }
    }
    /// Can an invader walk through this gate right now?
    pub fn ork_passable(&self) -> bool {
        self.kind == GateKind::None || !self.closed || self.broken
    }
}

/// Where a keep-marching invader outside the walls should head.
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum OrkGoal {
    /// Walk in through gate `i` — aim at its interior point.
    Enter(usize, Vec2),
    /// Every route is shut: hack gate `i` from this standoff point outside it.
    Hack(usize, Vec2),
}

impl OrkGoal {
    pub fn point(self) -> Vec2 {
        match self {
            OrkGoal::Enter(_, p) | OrkGoal::Hack(_, p) => p,
        }
    }
}

/// The three gates' state, in [`Gate::ALL`] order (W, S, N).
#[derive(Resource, Clone, Debug)]
pub struct Gates {
    pub g: [GateRt; 3],
    night: bool,
    /// Set for one frame when a gate breaks (index) — the visuals play the crash.
    pub just_broke: Option<usize>,
}

impl Default for Gates {
    fn default() -> Self {
        Gates { g: [GateRt::open(); 3], night: false, just_broke: None }
    }
}

impl Gates {
    /// Dusk / dawn transition. Dusk shuts every gate with `kind` at full HP; dawn opens them and
    /// rebuilds the broken ones (free for now). Idempotent within a phase.
    pub fn set_night(&mut self, night: bool, kind: GateKind) {
        if night && !self.night {
            for g in &mut self.g {
                *g = GateRt { kind, closed: kind != GateKind::None, broken: false, hp: kind.max_hp(), max: kind.max_hp() };
            }
        } else if !night && self.night {
            for g in &mut self.g {
                *g = GateRt { kind, closed: false, broken: false, hp: kind.max_hp(), max: kind.max_hp() };
            }
        }
        self.night = night;
    }

    /// Apply `amount` damage to gate `i`; returns `true` on the blow that breaks it.
    pub fn damage(&mut self, i: usize, amount: f32) -> bool {
        let g = &mut self.g[i];
        if g.ork_passable() {
            return false;
        }
        g.hp = (g.hp - amount).max(0.0);
        if g.hp <= 0.0 {
            g.broken = true;
            self.just_broke = Some(i);
            return true;
        }
        false
    }

    /// The keep-march goal for an invader at `from` OUTSIDE the walls: the nearest passable gate's
    /// interior, else the nearest shut gate's hacking standoff.
    pub fn ork_goal(&self, from: Vec2) -> OrkGoal {
        let near = |pass: bool| {
            Gate::ALL
                .iter()
                .enumerate()
                .filter(|(i, _)| self.g[*i].ork_passable() == pass)
                .min_by(|(_, a), (_, b)| from.distance_squared(a.center()).total_cmp(&from.distance_squared(b.center())))
                .map(|(i, g)| (i, *g))
        };
        if let Some((i, g)) = near(true) {
            return OrkGoal::Enter(i, g.interior(4.0));
        }
        let (i, g) = near(false).expect("three gates");
        OrkGoal::Hack(i, g.center() + g.outward() * HACK_STANDOFF)
    }

    /// The gap boxes `(cx, cz, hw, hd)` an invader may not path through (shut, unbroken gates).
    pub fn ork_boxes(&self) -> Vec<(f32, f32, f32, f32)> {
        Gate::ALL
            .iter()
            .enumerate()
            .filter(|(i, _)| !self.g[*i].ork_passable())
            .map(|(_, g)| gap_box(*g))
            .collect()
    }

    /// Would a body of radius `r` at `p` stand in a shut gate's gap?
    pub fn blocks_ork(&self, p: Vec2, r: f32) -> bool {
        self.ork_boxes()
            .iter()
            .any(|&(cx, cz, hw, hd)| (p.x - cx).abs() < hw + r && (p.y - cz).abs() < hd + r)
    }

    /// Index of a shut gate an invader at `p` (outside the walls) is close enough to hack.
    pub fn hackable_at(&self, p: Vec2) -> Option<usize> {
        Gate::ALL.iter().enumerate().find_map(|(i, g)| {
            let rel = p - g.center();
            (!self.g[i].ork_passable() && rel.dot(g.outward()) > 0.0 && rel.length() < HACK_RANGE).then_some(i)
        })
    }
}

/// World-axis box over a gate's passage `(cx, cz, half_x, half_z)`.
pub fn gap_box(g: Gate) -> (f32, f32, f32, f32) {
    let c = g.center();
    let o = g.outward();
    // Along the wall: the whole gap between the wall-run ends (the posts stand inside it); across:
    // the passage. A hair wider than the gap so a tile centre can't slip past the post edges.
    let along = GATE_GAP / 2.0 + 0.2;
    if o.x.abs() > 0.5 {
        (c.x, c.y, GAP_DEPTH, along)
    } else {
        (c.x, c.y, along, GAP_DEPTH)
    }
}

// ── ECS ────────────────────────────────────────────────────────────────────────────

/// One oak leaf: hinged at a post, swings from open (folded inward against the wall) to shut.
#[derive(Component)]
pub struct GateLeaf {
    gate: usize,
    /// −1 = the leaf hinged on the gate's left post, +1 = the right one.
    side: f32,
    /// 0 = fully open, 1 = fully shut.
    shut: f32,
}

/// The night wagon barricade dragged into gate `0`'s gap (no Gate upgrade).
#[derive(Component)]
pub struct GateBarricade(usize);

/// HP carrier for a gate's world bar (`combat_fx` floats it while the gate is damaged).
#[derive(Component)]
pub struct GateHp {
    pub gate: usize,
    pub hp: f32,
    pub max: f32,
}

pub struct GatesPlugin;

impl Plugin for GatesPlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<Gates>().add_systems(
            Update,
            (drive_gate_state, drive_gate_visuals).chain().run_if(crate::rts::in_campaign),
        );
    }
}

/// Along-the-wall unit vector of gate `g` (left → right seen from inside).
fn along(g: Gate) -> Vec2 {
    let o = g.outward();
    Vec2::new(o.y, -o.x)
}

/// Leaf yaw so its local +X (hinge → free edge) points along `dir` (XZ).
fn yaw_for(dir: Vec2) -> f32 {
    (-dir.y).atan2(dir.x)
}

/// Spawn the gate leaves, barricades and HP carriers (called from `castle::build`).
pub fn build(commands: &mut Commands, meshes: &mut Assets<Mesh>, mats: &Mats) {
    let leaf_w = OPEN_HALF;
    let leaf_h = GATE_H - 0.1;
    // Plank leaf hinged at local x=0, spanning +X; two iron bands.
    let leaf = meshes.add(bx(leaf_w, leaf_h, 0.14, leaf_w / 2.0, leaf_h / 2.0, 0.0));
    let band = meshes.add({
        let mut m = bx(leaf_w - 0.08, 0.1, 0.17, leaf_w / 2.0, leaf_h * 0.25, 0.0);
        m.merge(&bx(leaf_w - 0.08, 0.1, 0.17, leaf_w / 2.0, leaf_h * 0.75, 0.0)).ok();
        m
    });
    let barricade = meshes.add(barricade_mesh());
    for (i, g) in Gate::ALL.into_iter().enumerate() {
        let c = g.center();
        let a = along(g);
        for side in [-1.0_f32, 1.0] {
            let hinge = c + a * (side * OPEN_HALF);
            commands
                .spawn((
                    Transform::from_xyz(hinge.x, 0.0, hinge.y),
                    Visibility::Hidden,
                    GateLeaf { gate: i, side, shut: 0.0 },
                    BiomeEntity,
                ))
                .with_children(|p| {
                    p.spawn((Mesh3d(leaf.clone()), MeshMaterial3d(mats.get(M::Wood)), Transform::default()));
                    p.spawn((Mesh3d(band.clone()), MeshMaterial3d(mats.get(M::Iron)), Transform::default()));
                });
        }
        let yaw = yaw_for(a);
        commands.spawn((
            Mesh3d(barricade.clone()),
            MeshMaterial3d(mats.get(M::Wood)),
            Transform::from_xyz(c.x, 0.0, c.y).with_rotation(Quat::from_rotation_y(yaw)),
            Visibility::Hidden,
            GateBarricade(i),
            BiomeEntity,
        ));
        commands.spawn((
            Transform::from_xyz(c.x, GATE_H - 1.0, c.y),
            Visibility::Inherited,
            GateHp { gate: i, hp: 1.0, max: 1.0 },
            BiomeEntity,
        ));
    }
}

/// An overturned hay-wain wedged across the gap: bed, wheels, a stake row (local X = along the wall).
fn barricade_mesh() -> Mesh {
    let mut m = bake(bx(OPEN_HALF * 2.0, 0.9, 0.9, 0.0, 0.0, 0.0), Vec3::new(0.0, 0.75, 0.15), 0.0, Vec3::ONE);
    let mut add = |part: Mesh| {
        m.merge(&part).ok();
    };
    // Tipped bed side boards.
    add(bx(OPEN_HALF * 2.0 + 0.2, 0.12, 1.1, 0.0, 1.25, 0.15));
    // Wheels (flat discs as boxes, upright against the bed).
    for sx in [-0.95_f32, 0.95] {
        add(bx(0.12, 1.0, 1.0, sx * OPEN_HALF, 0.55, -0.45));
    }
    // Sharpened stakes leaning outward.
    for k in 0..6 {
        let x = -OPEN_HALF + 0.3 + k as f32 * (OPEN_HALF * 2.0 - 0.6) / 5.0;
        add(bake(bx(0.12, 1.5, 0.12, 0.0, 0.0, 0.0), Vec3::new(x, 0.65, 0.75), 0.0, Vec3::ONE));
    }
    m
}

/// Dusk/dawn: follow the siege phase (the war bell starts the night), with the kind set by the
/// Defenses upgrades at the moment the night falls.
fn drive_gate_state(
    siege: Res<crate::siege::Siege>,
    defenses: Res<crate::economy::Defenses>,
    mut gates: ResMut<Gates>,
    mut hp: Query<&mut GateHp>,
) {
    let night = siege.phase == crate::siege::GamePhase::Wave;
    gates.set_night(night, GateKind::from_defenses(defenses.walls, defenses.gate));
    for mut h in &mut hp {
        let g = gates.g[h.gate];
        let (cur, max) = if g.max > 0.0 && g.closed && !g.broken { (g.hp, g.max) } else { (1.0, 1.0) };
        if h.hp != cur || h.max != max {
            h.hp = cur;
            h.max = max;
        }
    }
}

/// Swing the leaves (open for a friend standing in the gap), show the barricades, play the crash.
#[allow(clippy::type_complexity)]
fn drive_gate_visuals(
    time: Res<Time>,
    mut gates: ResMut<Gates>,
    hero: Res<crate::player::HeroState>,
    folk: Query<&Transform, (With<crate::villagers::NpcHp>, Without<GateLeaf>, Without<GateBarricade>)>,
    mut leaves: Query<(&mut GateLeaf, &mut Transform, &mut Visibility), Without<GateBarricade>>,
    mut barricades: Query<(&GateBarricade, &mut Visibility), Without<GateLeaf>>,
    mut cues: MessageWriter<crate::audio::AudioCue>,
) {
    let dt = time.delta_secs().min(0.1);
    // A friend in (or right at) a gap → the watch swings that gate open for them.
    let friend_at = |g: Gate| {
        let (cx, cz, hw, hd) = gap_box(g);
        let near = |p: Vec2| (p.x - cx).abs() < hw + 2.2 && (p.y - cz).abs() < hd + 2.2;
        (hero.alive && near(hero.pos)) || folk.iter().any(|t| near(Vec2::new(t.translation.x, t.translation.z)))
    };
    let hero_near = |g: Gate| hero.pos.distance(g.center()) < 30.0;
    let mut let_in = [false; 3];
    for (i, g) in Gate::ALL.into_iter().enumerate() {
        let_in[i] = gates.g[i].closed && friend_at(g);
    }
    for (mut leaf, mut tf, mut vis) in &mut leaves {
        let st = gates.g[leaf.gate];
        let g = Gate::ALL[leaf.gate];
        let show = st.kind == GateKind::Wood && !st.broken;
        vis.set_if_neq(if show { Visibility::Inherited } else { Visibility::Hidden });
        let want = if st.closed && !st.broken && !let_in[leaf.gate] { 1.0 } else { 0.0 };
        let before = leaf.shut;
        leaf.shut = if want > leaf.shut { (leaf.shut + dt / SWING_SECS).min(1.0) } else { (leaf.shut - dt / SWING_SECS * 1.5).max(0.0) };
        if show && before < 1.0 && leaf.shut >= 1.0 && leaf.side > 0.0 && hero_near(g) {
            cues.write(crate::audio::AudioCue::WoodChop); // the leaves meet — a heavy wooden thud
        }
        // Shut: the leaf runs from its post toward the centre; open: folded back into the yard.
        let a = along(g);
        let shut_dir = a * -leaf.side;
        let open_dir = (-g.outward() * 0.97 + shut_dir * 0.24).normalize();
        let s = leaf.shut * leaf.shut * (3.0 - 2.0 * leaf.shut);
        let (y0, y1) = (yaw_for(open_dir), yaw_for(shut_dir));
        let d = (y1 - y0 + std::f32::consts::PI).rem_euclid(std::f32::consts::TAU) - std::f32::consts::PI;
        tf.rotation = Quat::from_rotation_y(y0 + d * s);
    }
    for (b, mut vis) in &mut barricades {
        let st = gates.g[b.0];
        let show = st.kind == GateKind::Barricade && st.closed && !st.broken;
        vis.set_if_neq(if show { Visibility::Inherited } else { Visibility::Hidden });
    }
    if let Some(i) = gates.just_broke.take() {
        if hero_near(Gate::ALL[i]) {
            cues.write(crate::audio::AudioCue::TreeFall { cactus: false }); // timber crash
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn gates_shut_at_dusk_and_open_repaired_at_dawn() {
        let mut gs = Gates::default();
        assert!(gs.g.iter().all(|g| g.ork_passable()), "day: everything open");
        gs.set_night(true, GateKind::Wood);
        assert!(gs.g.iter().all(|g| g.closed && !g.ork_passable() && g.hp == WOOD_GATE_HP));
        // Hack the S gate down.
        assert!(!gs.damage(1, WOOD_GATE_HP - 1.0));
        assert!(gs.damage(1, 5.0), "the last blow breaks it");
        assert!(gs.g[1].broken && gs.g[1].ork_passable() && gs.just_broke == Some(1));
        assert!(!gs.damage(1, 50.0), "a broken gate takes no more damage");
        // Still night: stays broken.
        gs.set_night(true, GateKind::Wood);
        assert!(gs.g[1].broken);
        // Dawn: open + rebuilt; next dusk shuts it again at full HP.
        gs.set_night(false, GateKind::Wood);
        assert!(gs.g.iter().all(|g| !g.closed && !g.broken && g.hp == WOOD_GATE_HP));
        gs.set_night(true, GateKind::Wood);
        assert!(!gs.g[1].ork_passable() && gs.g[1].hp == WOOD_GATE_HP);
    }

    #[test]
    fn barricade_without_the_gate_upgrade_and_nothing_without_walls() {
        assert_eq!(GateKind::from_defenses(true, true), GateKind::Wood);
        assert_eq!(GateKind::from_defenses(true, false), GateKind::Barricade);
        assert_eq!(GateKind::from_defenses(false, false), GateKind::None);
        let mut gs = Gates::default();
        gs.set_night(true, GateKind::Barricade);
        assert!(gs.g.iter().all(|g| !g.ork_passable() && g.max == BARRICADE_HP));
        let mut open = Gates::default();
        open.set_night(true, GateKind::None);
        assert!(open.g.iter().all(|g| g.ork_passable()), "no walls: nothing to shut");
    }

    #[test]
    fn southern_orks_hack_the_south_gate_then_pour_through_the_breach() {
        let mut gs = Gates::default();
        gs.set_night(true, GateKind::Wood);
        let from = Vec2::new(3.0, 60.0); // the southern spawn arc
        match gs.ork_goal(from) {
            OrkGoal::Hack(i, p) => {
                assert_eq!(Gate::ALL[i], Gate::South, "the natural target is the S gate");
                assert!(p.y > Gate::South.center().y, "hack from outside");
                assert_eq!(gs.hackable_at(p), Some(i));
            }
            other => panic!("expected a hack goal, got {other:?}"),
        }
        // The gap is solid for orks while shut.
        let gap = Gate::South.center();
        assert!(gs.blocks_ork(gap, 0.4));
        gs.damage(1, WOOD_GATE_HP);
        assert!(!gs.blocks_ork(gap, 0.4));
        match gs.ork_goal(from) {
            OrkGoal::Enter(i, p) => {
                assert_eq!(Gate::ALL[i], Gate::South);
                assert!(crate::castle::in_courtyard(p.x, p.y), "into the yard");
            }
            other => panic!("expected to enter through the breach, got {other:?}"),
        }
        // A western ork also heads for the breach (the only open route), not its shut W gate.
        assert!(matches!(gs.ork_goal(Vec2::new(-60.0, 0.0)), OrkGoal::Enter(1, _)));
    }
}
