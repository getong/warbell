//! **Knight hero model** — box-mesh humanoid ported 1:1 from the TS `Character.tsx` mesh
//! tree (plate armour, visored helm, an iron sword baked into the right arm, a cross
//! shield on its own pivot). Built exactly like `orks.rs` / `critters.rs`: each articulated
//! part is ONE merged, flat-shaded, vertex-coloured `Mesh` against the shared white hero
//! material; feet rest at `y = 0` so the root, placed on the ground, plants the knight.
//!
//! Authoring is in TS units (the TS root group is `scale 0.5`, knight ~1.25u tall before
//! scale); the spawn applies `HERO_SCALE` so the knight stands the same height as the orks.

use bevy::mesh::MeshBuilder;
use bevy::prelude::*;

use crate::palette::lin;

use super::HeroLimb;

// ── Palette (sRGB hex, matches Character.tsx) ────────────────────────────────────────
const ARMOR: u32 = 0xd6d8df;
const ARMOR_LIGHT: u32 = 0xe6e8ed;
const ARMOR_DARK: u32 = 0x9aa0aa;
const VISOR: u32 = 0x1a1a22;
const BELT: u32 = 0x3a2a1a;
const BLADE: u32 = 0xc0c6d0;
const HILT: u32 = 0x3a3a40;
const GRIP: u32 = 0x5a3a22;
const SHIELD_FACE: u32 = 0xa8b8d0;
const SHIELD_RIM: u32 = 0x6a3a22;
const SHIELD_EMBLEM: u32 = 0xd3b14c;
const GOLD: u32 = 0xe8b84b; // Golden Blade gilding
const AXE_STEEL: u32 = 0xaab0bc; // Battle Axe head
const STONE: u32 = 0x8a8d92; // Stone Maul head
const FROST: u32 = 0xaad2f0; // Frostfang greatsword (Bevy rim item, no TS mesh)

/// Shield rest pose (own pivot, decoupled from the left arm): slung on the left flank,
/// decorated face out (−X). Block (M3) swings it across the front.
pub const SHIELD_REST_POS: Vec3 = Vec3::new(-0.3, 0.62, 0.06);
pub fn shield_rest_rot() -> Quat {
    Quat::from_euler(EulerRot::XYZ, 0.04, -1.3, 0.05)
}
/// Block pose: shield swung across the front (face +Z), braced high.
pub const SHIELD_BLOCK_POS: Vec3 = Vec3::new(-0.12, 0.82, 0.5);
pub fn shield_block_rot() -> Quat {
    Quat::from_euler(EulerRot::XYZ, -0.12, 0.05, -0.05)
}

// ── Articulated part + spec ──────────────────────────────────────────────────────────
pub struct HeroPartDef {
    pub limb: HeroLimb,
    pub pivot: Vec3,
    /// Rest orientation of the part (identity for limbs; the shield rests rotated).
    pub rest: Quat,
    pub mesh: Mesh,
}

pub struct KnightSpec {
    pub torso: Mesh,
    pub parts: Vec<HeroPartDef>,
}

// ── Mesh helpers (local copies of the orks/critters contract) ────────────────────────
fn v(x: f32, y: f32, z: f32) -> Vec3 {
    Vec3::new(x, y, z)
}
fn rx(a: f32) -> Quat {
    Quat::from_rotation_x(a)
}
fn rz(a: f32) -> Quat {
    Quat::from_rotation_z(a)
}
fn tinted(mut m: Mesh, c: u32) -> Mesh {
    let n = m.count_vertices();
    m.insert_attribute(Mesh::ATTRIBUTE_COLOR, vec![lin(c); n]);
    m
}
/// Merge + hard flat-shade — the crisp low-poly facets the TS models use.
fn group(parts: Vec<Mesh>) -> Mesh {
    let mut it = parts.into_iter();
    let mut base = it.next().expect("at least one part");
    for p in it {
        base.merge(&p).expect("hero parts share attributes");
    }
    base.duplicate_vertices();
    base.compute_flat_normals();
    base
}
fn bx(w: f32, h: f32, d: f32, off: Vec3, c: u32) -> Mesh {
    tinted(Cuboid::new(w, h, d).mesh().build().translated_by(off), c)
}
fn cyl(r: f32, h: f32, off: Vec3, c: u32) -> Mesh {
    tinted(Cylinder::new(r, h).mesh().resolution(8).build().translated_by(off), c)
}
fn cone(r: f32, h: f32, off: Vec3, rot: Quat, c: u32) -> Mesh {
    tinted(Cone { radius: r, height: h }.mesh().build().rotated_by(rot).translated_by(off), c)
}
fn sphere(r: f32, off: Vec3, c: u32) -> Mesh {
    tinted(Sphere::new(r).mesh().ico(1).unwrap().translated_by(off), c)
}
/// Bake a sub-group (built in its own local space) into the parent: rotate about the group
/// origin, then translate to the group's offset — matches three.js `<group rotation pos>`.
fn baked(m: Mesh, rot: Quat, off: Vec3) -> Mesh {
    m.rotated_by(rot).translated_by(off)
}

// ── Equip-driven palette + geometry selectors ────────────────────────────────────────
/// Lerp an sRGB-hex colour `t` of the way toward `target` (in byte space — close enough for
/// the "feels the same" parity bar; the TS derives plate light/dark the same way).
fn lerp_hex(c: u32, target: u32, t: f32) -> u32 {
    let ch = |x: u32, s: u32| ((x >> s) & 0xff) as f32;
    let mix = |a: f32, b: f32| (a + (b - a) * t).round().clamp(0.0, 255.0) as u32;
    let r = mix(ch(c, 16), ch(target, 16));
    let g = mix(ch(c, 8), ch(target, 8));
    let b = mix(ch(c, 0), ch(target, 0));
    (r << 16) | (g << 8) | b
}

/// The plate colour triple `(base, light, dark)` for the worn armor — derived from the tier
/// tint (light = lerp→white 0.28, dark = lerp→black 0.3), matching `Character.tsx`. `None`
/// (bare) restores the exact default steel palette. Tints are the TS `armorTint` values.
fn armor_palette(armor: Option<&str>) -> (u32, u32, u32) {
    let tint = match armor {
        Some("leather_armor") => 0x7a5230,
        Some("iron_armor") => 0xaeb4c0,
        Some("gold_armor") => 0xe8b84b,
        Some("dragon_plate") => 0x3a6a4a,
        _ => return (ARMOR, ARMOR_LIGHT, ARMOR_DARK),
    };
    (tint, lerp_hex(tint, 0xffffff, 0.28), lerp_hex(tint, 0x000000, 0.3))
}

/// Sword-shaped weapon parts (pommel/grip/guard/blade/tip) with the blade tinted `c`; shared
/// by the iron sword (default), the golden blade, and the frost greatsword.
fn sword_parts(blade: u32, pommel: u32) -> Vec<Mesh> {
    vec![
        sphere(0.05, v(0.0, 0.14, 0.0), pommel),
        cyl(0.03, 0.14, v(0.0, 0.06, 0.0), GRIP),
        bx(0.30, 0.06, 0.08, v(0.0, -0.04, 0.0), pommel),
        bx(0.09, 0.80, 0.03, v(0.0, -0.47, 0.0), blade),
        cone(0.05, 0.12, v(0.0, -0.90, 0.0), rx(std::f32::consts::PI), blade),
    ]
}

/// The held-weapon part meshes for the equipped item, in the sword-group local space (the
/// caller bakes them at the hand). Ported 1:1 from `Character.tsx`; an unknown id falls back to
/// the iron sword (also the bare-handed default).
fn weapon_parts(weapon: Option<&str>) -> Vec<Mesh> {
    match weapon {
        Some("axe") => vec![
            cyl(0.028, 0.8, v(0.0, -0.12, 0.0), GRIP), // haft
            sphere(0.04, v(0.0, 0.3, 0.0), HILT),      // pommel cap
            bx(0.26, 0.22, 0.05, v(0.13, -0.42, 0.0), AXE_STEEL), // head
            cone(0.11, 0.14, v(0.28, -0.42, 0.0), rz(-std::f32::consts::FRAC_PI_2), AXE_STEEL), // edge
        ],
        Some("sword_gold") => sword_parts(GOLD, GOLD),
        Some("blade_frost") => sword_parts(FROST, FROST),
        Some("stone_maul") => vec![
            cyl(0.035, 0.95, v(0.0, -0.1, 0.0), GRIP), // haft
            bx(0.34, 0.26, 0.26, v(0.0, -0.6, 0.0), STONE), // head
            bx(0.06, 0.2, 0.2, v(0.19, -0.6, 0.0), STONE), // striking cap +x
            bx(0.06, 0.2, 0.2, v(-0.19, -0.6, 0.0), STONE), // striking cap -x
        ],
        _ => sword_parts(BLADE, HILT), // iron sword (default + bare-handed)
    }
}

// ── Build (params: equipped weapon + armor ids; None = bare iron sword + steel plate) ─
/// Build the knight mesh reflecting the equipped gear: the held weapon swaps geometry
/// (`weapon_parts`) and the worn armor recolours the plate (`armor_palette`). Re-called by
/// the render layer whenever the equip slots change (`reskin_hero`).
pub fn build_knight(weapon: Option<&str>, armor: Option<&str>) -> KnightSpec {
    // Plate colour triple for the worn armor (bare = default steel).
    let (a, al, ad) = armor_palette(armor);

    // Static torso: legs are articulated; belt + body + breastplate are baked in here.
    let torso = group(vec![
        bx(0.42, 0.08, 0.22, v(0.0, 0.4, 0.0), BELT), // belt
        bx(0.42, 0.46, 0.26, v(0.0, 0.66, 0.0), a), // body
        bx(0.32, 0.32, 0.02, v(0.0, 0.70, 0.135), al), // breastplate
    ]);

    // Head: helm + visor slit + crest.
    let head = group(vec![
        bx(0.32, 0.3, 0.32, v(0.0, 0.0, 0.0), al),
        bx(0.24, 0.06, 0.01, v(0.0, -0.01, 0.165), VISOR),
        bx(0.34, 0.06, 0.34, v(0.0, 0.18, 0.0), ad),
    ]);

    // Right arm (sword hand): shoulder + upper + cuff, with the equipped weapon's parts baked
    // individually at the hand so the blade swings with the arm. Sword sits at arm-local
    // (0,-0.5,0.06) rotated x=-π/2 so it extends FORWARD (+Z). CRITICAL: every part is an
    // indexed primitive merged by the SINGLE outer group() — do NOT pre-`group()` a sub-part
    // and re-merge it (flat-shading makes it non-indexed → merge corrupts the geometry, which
    // is what hid the sword). Matches the ork-club build in `orks.rs`.
    let sw_rot = rx(-std::f32::consts::FRAC_PI_2);
    let sw_off = v(0.0, -0.5, 0.06);
    let mut arm_r_parts = vec![
        bx(0.18, 0.1, 0.28, v(0.0, -0.02, 0.0), al), // shoulder
        bx(0.12, 0.42, 0.22, v(0.0, -0.21, 0.0), a), // upper
        bx(0.13, 0.08, 0.23, v(0.0, -0.45, 0.0), ad), // cuff
    ];
    for part in weapon_parts(weapon) {
        arm_r_parts.push(baked(part, sw_rot, sw_off));
    }
    let arm_r = group(arm_r_parts);

    // Left arm (shield hand): shoulder + upper + cuff (shield is a separate part).
    let arm_l = group(vec![
        bx(0.18, 0.1, 0.28, v(0.0, -0.02, 0.0), al),
        bx(0.12, 0.42, 0.22, v(0.0, -0.21, 0.0), a),
        bx(0.13, 0.08, 0.23, v(0.0, -0.45, 0.0), ad),
    ]);

    // Shield (own pivot): heater plate + raised rim + recessed field + gold cross emblem.
    let shield = group(vec![
        bx(0.42, 0.58, 0.05, v(0.0, 0.0, 0.0), SHIELD_FACE), // plate
        bx(0.46, 0.62, 0.014, v(0.0, 0.0, 0.028), SHIELD_RIM), // rim
        bx(0.34, 0.5, 0.014, v(0.0, 0.0, 0.034), SHIELD_FACE), // inset field
        bx(0.07, 0.4, 0.014, v(0.0, 0.03, 0.04), SHIELD_EMBLEM), // cross vertical
        bx(0.3, 0.07, 0.014, v(0.0, 0.1, 0.04), SHIELD_EMBLEM), // cross horizontal
    ]);

    // Legs (built top-at-hip so the pivot sits at the hip; foot rests at root y≈0).
    let leg = || group(vec![bx(0.16, 0.36, 0.18, v(0.0, -0.18, 0.0), ad)]);

    let parts = vec![
        HeroPartDef { limb: HeroLimb::LegR, pivot: v(0.1, 0.36, 0.0), rest: Quat::IDENTITY, mesh: leg() },
        HeroPartDef { limb: HeroLimb::LegL, pivot: v(-0.1, 0.36, 0.0), rest: Quat::IDENTITY, mesh: leg() },
        HeroPartDef { limb: HeroLimb::ArmR, pivot: v(0.27, 0.87, 0.0), rest: Quat::IDENTITY, mesh: arm_r },
        HeroPartDef { limb: HeroLimb::ArmL, pivot: v(-0.27, 0.87, 0.0), rest: Quat::IDENTITY, mesh: arm_l },
        HeroPartDef { limb: HeroLimb::Head, pivot: v(0.0, 1.04, 0.0), rest: Quat::IDENTITY, mesh: head },
        HeroPartDef { limb: HeroLimb::Shield, pivot: SHIELD_REST_POS, rest: shield_rest_rot(), mesh: shield },
    ];

    KnightSpec { torso, parts }
}
