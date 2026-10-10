//! **Peasant models on the shared biped skeleton** — a faithful port of the studio
//! `peasantBuilder.ts` (woodcutter / farmer / unemployed / miner, + a guard variant) authored for
//! [`crate::biped`]'s studio knight skeleton. Each [`PeasantKind`] yields a [`crate::biped::BipedMeshes`]
//! (per-joint flat-shaded vertex-coloured meshes) for `spawn_biped`. `skin`/`tunic`/`trouser` are
//! passed in so the town keeps its per-villager colour variety; the rest are the studio's fixed hues.
//!
//! Each peasant carries ONLY the tool of his trade on the **right hand's `Sword` pivot** (built +Y
//! like the hero/ork weapons so the shared rest rotation holds them carried): woodcutter → axe,
//! farmer → hoe, miner → pickaxe, guard → sword; the unemployed go empty-handed. The off-hand
//! (`Shield` pivot) is empty for civilians; the GUARD mounts a round livery shield there.
//!
//! Every part carries a [`Surf`] code (baked into the vertex-colour alpha by [`crate::creature::surf`])
//! so the shared `CreatureMaterial` shader textures cloth/metal/skin correctly — without it every part
//! decodes as flat `Skin`.
//!
//! **Realistic body.** When the Blender forest kit loaded `people.glb`
//! (`tools/blender_forest/people.py`), [`peasant_biped_meshes`] instead assembles an organic,
//! realistically-proportioned human as ONE skinned mesh on the same biped joints (see
//! `kit_peasant_meshes`): same joints, clips and props, a slimmer frame — so spawn sites take the
//! rig spacing from [`rig_dims`] — and a per-person `look` (face / hair / beard / everyday hood).
//! The box builder below stays the fallback.

use bevy::mesh::MeshBuilder;
use bevy::prelude::*;
use std::f32::consts::FRAC_PI_2;

use crate::biped::BipedMeshes;
use crate::creature::Surf;
use crate::palette::lin;

/// Which worker the studio peasant builder makes (maps from `villagers::Kind`/`Trade`).
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum PeasantKind {
    Woodcutter,
    Farmer,
    Unemployed,
    Miner,
    Guard,
    /// The town's ranged militia: longbow in the off-hand, a nocked arrow in the string hand,
    /// a back quiver + baldric, leather hood + bow-arm bracer. Fights at range (`villagers.rs`
    /// archer brain) instead of the guard's sword-and-board melee.
    Archer,
}

/// What a `kind`'s right hand carries (its [`kit_tools`] / [`peasant_tools`] weapon slot) — so the
/// biped clips grip that tool (`BipedDrive::tool`). Every spawn of a peasant body sets this.
pub fn held_tool(kind: PeasantKind) -> crate::biped::HeldTool {
    use crate::biped::HeldTool;
    match kind {
        PeasantKind::Woodcutter => HeldTool::Axe,
        PeasantKind::Miner => HeldTool::Pick,
        PeasantKind::Farmer => HeldTool::Hoe,
        PeasantKind::Guard => HeldTool::Sword,
        PeasantKind::Archer => HeldTool::Bow,
        PeasantKind::Unemployed => HeldTool::None,
    }
}

// Fixed studio peasant hues (skin/tunic/trouser are caller-supplied for town variety).
const LEATHER: u32 = 0x4e3b31; // gripColor
const WOOD: u32 = 0x6b4a2e; // wood brown (tool hafts — a real timber haft, not the old pale-grey trim)
const IRON: u32 = 0xcfd3dc; // bladeColor (tools/helmet)
const HAIR: u32 = 0x3a2418; // natural brown (studio reuses plumeColor, but that's our hero red)
const DARK: u32 = 0x23160f; // eyes/mouth
const STRAW: u32 = 0xd7b45f; // farmer hat
const PATCH: u32 = 0x9f7f4f; // stripes/apron/patches/torn hem
const LAMP: u32 = 0xffd166; // miner lamp
// Desert garb (rival NPCs): a keffiyeh headcloth + agal cord + a draped cloak/sash, so the rival's
// men read instantly as "not ours" no matter their trade.
const DESERT_CLOTH: u32 = 0xe7d9b6; // pale sand headcloth drape
const DESERT_BAND: u32 = 0x4a3a22; // dark agal cord / sash
const DESERT_CLOAK: u32 = 0xb1925a; // warm sand cloak
// Soldier livery — a guard wears a steel breastplate + a faction-coloured tabard so a FIGHTER reads
// at a glance from an unarmed peasant/worker (whom you must NOT cut down). Blue = the player's
// militia, crimson = the rival's garrison (picked by the `desert` flag, which is set only for rival
// NPCs). Matches the rival's crimson banners in `rival.rs`.
const LIVERY_BLUE: u32 = 0x2f4a8a;
const LIVERY_CRIMSON: u32 = 0x9a2420;
// Archer kit — dark yew bow stave, pale linen string, fletchings dyed the militia blue so a
// nocked shaft reads against the leather kit (and matches the tabard blue of our melee guards).
const BOW_WOOD: u32 = 0x4f3c26; // oiled yew stave
const BOW_STRING: u32 = 0xe6ddc4; // waxed linen
const FLETCH: u32 = 0x3f5f9e; // dyed goose-feather vanes (militia blue, a shade lighter than LIVERY_BLUE)
/// The RIVAL archer's fletching — crimson-dyed vanes (a shade lighter than LIVERY_CRIMSON, same
/// lightening as FLETCH vs LIVERY_BLUE), so a desert bowman's quiver/arrow/feather reads "theirs"
/// at a glance. Keep in sync with the rival arrow mesh in `projectile.rs::setup_arrow_assets`.
const DESERT_FLETCH: u32 = 0xc23a2e;
const ARCHER_BAND: u32 = 0x33261a; // dark leather hood band / quiver straps
const PLATE: u32 = 0xb9bec8; // brushed steel armour (a touch darker than the bright IRON tool blade)
const DESERT_BRONZE: u32 = 0x8a6a34; // warm desert war-metal (conical war-helm, scimitar hilt)
// The rival garrison's body armour is PALE SANDY plate (sun-bleached leather/scale), NOT heavy
// cold steel like ours and NOT dark bronze — so the desert soldier reads "piaskowy" (sandy/light).
const DESERT_ARMOR: u32 = 0xcab089; // sandy plate
// Desert lower-body garb (rival workers) — a flowing thobe + loose linens + sandals, so the rival's
// men read as a foreign desert people from head to toe, not "our peasant in a headscarf".
const DESERT_ROBE: u32 = 0xcdb784; // sand thobe skirt (a shade lighter/warmer than the DESERT_CLOTH headwrap)
const DESERT_PANT: u32 = 0xb8a06b; // loose linen trousers under the robe
const DESERT_SANDAL: u32 = 0x6e5536; // bare-foot leather sandal

fn v(x: f32, y: f32, z: f32) -> Vec3 {
    Vec3::new(x, y, z)
}
fn rx(a: f32) -> Quat {
    Quat::from_rotation_x(a)
}
fn rz(a: f32) -> Quat {
    Quat::from_rotation_z(a)
}
fn xyz(x: f32, y: f32, z: f32) -> Quat {
    Quat::from_euler(EulerRot::XYZ, x, y, z)
}
/// Tint a part `c` and tag its surface family `s` (alpha-encoded for the creature shader).
fn tinted(mut m: Mesh, c: u32, s: Surf) -> Mesh {
    let n = m.count_vertices();
    m.insert_attribute(Mesh::ATTRIBUTE_COLOR, vec![lin(c); n]);
    crate::creature::surf(m, s)
}
/// Bevelled box matching the hero's softened low-poly edges (`player::model::chamfer_box`), so the
/// peasant's box details (head/buckles/hat) read as the same family as the knight, not sharp cuboids.
fn chamfer_box(w: f32, h: f32, d: f32, e: f32) -> Mesh {
    use bevy::asset::RenderAssetUsages;
    use bevy::mesh::{Indices, PrimitiveTopology};
    let (a, b, c) = (w * 0.5, h * 0.5, d * 0.5);
    let e = e.min(a * 0.49).min(b * 0.49).min(c * 0.49).max(0.001);
    let (ai, bi, ci) = (a - e, b - e, c - e);
    let pos: Vec<[f32; 3]> = vec![
        [a, -bi, -ci], [a, bi, -ci], [a, bi, ci], [a, -bi, ci],
        [-a, -bi, -ci], [-a, bi, -ci], [-a, bi, ci], [-a, -bi, ci],
        [-ai, b, -ci], [ai, b, -ci], [ai, b, ci], [-ai, b, ci],
        [-ai, -b, -ci], [ai, -b, -ci], [ai, -b, ci], [-ai, -b, ci],
        [-ai, -bi, c], [ai, -bi, c], [ai, bi, c], [-ai, bi, c],
        [-ai, -bi, -c], [ai, -bi, -c], [ai, bi, -c], [-ai, bi, -c],
    ];
    let mut raw: Vec<[u32; 3]> = Vec::new();
    let mut quad = |a: u32, b: u32, c: u32, d: u32| {
        raw.push([a, b, c]);
        raw.push([a, c, d]);
    };
    for f in 0..6u32 {
        let o = f * 4;
        quad(o, o + 1, o + 2, o + 3);
    }
    let edges = [
        [1, 2, 10, 9], [3, 0, 13, 14], [6, 5, 8, 11], [7, 4, 12, 15],
        [3, 2, 18, 17], [0, 1, 22, 21], [7, 6, 19, 16], [4, 5, 23, 20],
        [11, 10, 18, 19], [8, 9, 22, 23], [15, 14, 17, 16], [12, 13, 21, 20],
    ];
    for q in edges {
        quad(q[0], q[1], q[2], q[3]);
    }
    for t in [[2, 10, 18], [1, 9, 22], [3, 14, 17], [0, 13, 21], [6, 11, 19], [5, 8, 23], [7, 15, 16], [4, 12, 20]] {
        raw.push(t);
    }
    let g = |i: u32| Vec3::from_array(pos[i as usize]);
    let mut idx: Vec<u32> = Vec::new();
    for t in raw {
        let (va, vb, vc) = (g(t[0]), g(t[1]), g(t[2]));
        let nrm = (vb - va).cross(vc - va);
        let ctr = (va + vb + vc) / 3.0;
        if nrm.dot(ctr) >= 0.0 {
            idx.extend(t);
        } else {
            idx.extend([t[0], t[2], t[1]]);
        }
    }
    let n = pos.len();
    let mut m = Mesh::new(PrimitiveTopology::TriangleList, RenderAssetUsages::default());
    m.insert_attribute(Mesh::ATTRIBUTE_NORMAL, vec![[0.0, 1.0, 0.0]; n]);
    m.insert_attribute(Mesh::ATTRIBUTE_UV_0, vec![[0.0, 0.0]; n]);
    m.insert_attribute(Mesh::ATTRIBUTE_POSITION, pos);
    m.insert_indices(Indices::U32(idx));
    m
}
fn cham(w: f32, h: f32, d: f32) -> f32 {
    (w.min(h).min(d) * 0.32).clamp(0.008, 0.06)
}
fn group(parts: Vec<Mesh>) -> Mesh {
    let mut it = parts.into_iter();
    let mut base = it.next().expect("at least one part");
    for p in it {
        base.merge(&p).expect("peasant parts share attributes");
    }
    base.duplicate_vertices();
    base.compute_flat_normals();
    base
}
fn bx(w: f32, h: f32, d: f32, off: Vec3, c: u32, s: Surf) -> Mesh {
    tinted(chamfer_box(w, h, d, cham(w, h, d)).translated_by(off), c, s)
}
fn bxr(w: f32, h: f32, d: f32, off: Vec3, rot: Quat, c: u32, s: Surf) -> Mesh {
    tinted(chamfer_box(w, h, d, cham(w, h, d)).rotated_by(rot).translated_by(off), c, s)
}
fn frustum(rt: f32, rb: f32, h: f32, off: Vec3, c: u32, s: Surf) -> Mesh {
    tinted(ConicalFrustum { radius_top: rt, radius_bottom: rb, height: h }.mesh().resolution(12).build().translated_by(off), c, s)
}
fn frustum_s(rt: f32, rb: f32, h: f32, scale: Vec3, off: Vec3, c: u32, s: Surf) -> Mesh {
    tinted(ConicalFrustum { radius_top: rt, radius_bottom: rb, height: h }.mesh().resolution(12).build().scaled_by(scale).translated_by(off), c, s)
}
fn frustum_r(rt: f32, rb: f32, h: f32, off: Vec3, rot: Quat, c: u32, s: Surf) -> Mesh {
    tinted(ConicalFrustum { radius_top: rt, radius_bottom: rb, height: h }.mesh().resolution(6).build().rotated_by(rot).translated_by(off), c, s)
}
fn cone(r: f32, h: f32, off: Vec3, rot: Quat, scale: Vec3, c: u32, s: Surf) -> Mesh {
    tinted(Cone { radius: r, height: h }.mesh().build().scaled_by(scale).rotated_by(rot).translated_by(off), c, s)
}
/// Warm + deepen a skin hue toward a sun-tanned desert complexion (keep the red, drop green/blue),
/// preserving the caller's per-NPC variety while making the rival's people read as a foreign people.
fn tan_skin(c: u32) -> u32 {
    let r = (((c >> 16) & 0xff) as f32 * 0.93).min(255.0) as u32;
    let g = (((c >> 8) & 0xff) as f32 * 0.78).min(255.0) as u32;
    let b = ((c & 0xff) as f32 * 0.62).min(255.0) as u32;
    (r << 16) | (g << 8) | b
}

// ── Realistic kit body (Blender SDF pieces, `people.glb`) ──────────────────────────────────────
//
// `tools/blender_forest/people.py` builds a base human (tunic trunk, sleeved or bare arms with
// gripping hands, trousered legs with boots or desert wraps + sandals, four faces) plus add-ons —
// hair styles, beards, headgear, apron / plate + tabard / jerkin + quiver / desert cloak, sash and
// robe, pauldrons, a bracer. Body pieces are authored in the rig's rest frame, head pieces in the
// head joint's frame, and every vertex carries its skin weights (UV0 + UV1). Here a person is
// ASSEMBLED by merging the pieces their trade + look call for into ONE skinned mesh, recoloured by
// one per-person palette (vertex colour R = region code, see the region list in people.py), and
// `biped::spawn_biped` binds it to the joints — elbows, knees and skirts bend instead of pegs.

/// Number of distinct cosmetic looks (face / hair / beard / hair tone / everyday headgear) the
/// kit body cycles through. Callers pass any u32 (the villager seed); it is taken mod this.
pub const LOOKS: u32 = 12;
/// Rig spacing the kit parts were authored against (`people.py` SDX / HDX): a realistic, slimmer
/// frame than the stocky studio peasant (0.3 / 0.15).
pub const KIT_SHOULDER_DX: f32 = 0.2;
pub const KIT_HIP_DX: f32 = 0.1;
/// The sculpted head is life-sized; a touch larger reads better at game distance.
const KIT_HEAD_MUL: f32 = 1.1;
const BOOT: u32 = 0x33241a; // dark boot leather
/// Natural hair colours (brown / dark-brown / near-black / chestnut / auburn / sandy / ash /
/// dark-ash), then two greys for the balding elders.
const HAIR_TONES: [u32; 10] = [0x3a2418, 0x2a1c12, 0x1c1410, 0x6b4a2a, 0x7a3b1e, 0x8a7a5a, 0xa9854e, 0x5a4636, 0x9a9488, 0xc4beb4];
/// Everyday hood / cap dyes: undyed wool, brown, moss, russet.
const HOOD_DYES: [u32; 4] = [0x6a6152, 0x5a4632, 0x46553a, 0x7a4a2a];
/// One row per look: (face, hair style, beard, `HAIR_TONES` index, the unemployed's everyday hat:
/// 0 none · 1 hood · 2 cap). Face `c` is the lean/fine one, `b` the broad one.
const LOOK_TABLE: [(&str, &str, Option<&str>, usize, u8); LOOKS as usize] = [
    ("a", "crop", Some("short"), 0, 0),
    ("b", "shag", Some("full"), 1, 1),
    ("c", "long", None, 3, 0),
    ("a", "bowl", Some("moustache"), 2, 2),
    ("b", "bald", Some("full"), 8, 0),
    ("c", "crop", None, 5, 1),
    ("a", "shag", None, 4, 0),
    ("b", "crop", Some("moustache"), 6, 2),
    ("c", "bowl", Some("short"), 1, 0),
    ("a", "long", Some("full"), 7, 1),
    ("b", "shag", Some("short"), 2, 0),
    ("c", "bald", Some("moustache"), 9, 2),
];

/// The realistic kit, when it loaded the townsfolk parts.
fn kit_people() -> Option<&'static crate::realforest::Kit> {
    crate::realforest::get().filter(|k| k.has("hu_trunk"))
}

/// `(hip_dx, shoulder_dx, head_mul)` for [`crate::biped::spawn_biped`]: the kit body's slimmer
/// frame (and head-scale multiplier) when `people.glb` is loaded, else the box peasant's spacing.
/// Every peasant / villager spawn site must use this so the meshes and the joints agree.
pub fn rig_dims() -> (f32, f32, f32) {
    if kit_people().is_some() {
        (KIT_HIP_DX, KIT_SHOULDER_DX, KIT_HEAD_MUL)
    } else {
        (0.15, 0.3, 1.0)
    }
}

/// The head scale the kit body bakes into its head pieces — what the spawn sites pass to
/// `spawn_biped` (`(1.55 kid | 1.06) * head_mul`). The skinned body's bind pose cancels the joint's
/// own scale, so this is the size the head is drawn at.
fn kit_head_scale(kid: bool) -> f32 {
    (if kid { 1.55 } else { 1.06 }) * KIT_HEAD_MUL
}

/// Per-channel sRGB-hex lerp.
fn mix_hex(a: u32, b: u32, t: f32) -> u32 {
    let ch = |s: u32| {
        let (x, y) = (((a >> s) & 0xff) as f32, ((b >> s) & 0xff) as f32);
        ((x + (y - x) * t).round().clamp(0.0, 255.0) as u32) << s
    };
    ch(16) | ch(8) | ch(0)
}

/// Weathering per region (people.py order): the colour multiplier a fully weathered vertex (vertex
/// colour B = 1) reaches — ruddy skin, grimy cloth, dusty boots and wraps.
const KIT_WEATHER: [[f32; 3]; 16] = [
    [1.0, 0.8, 0.74],    // skin: ruddy cheeks, nose, ears, knuckles
    [1.0, 1.0, 1.0],     // lip
    [31.0, 58.0, 92.0],  // eye: the baked corners lift the dark iris (linear) to off-white whites
    [1.2, 1.15, 1.05],   // hair
    [0.62, 0.6, 0.56],   // tunic: grime toward the hem, sweat under the arms
    [0.7, 0.68, 0.64],   // trim
    [0.62, 0.6, 0.56],   // trousers: worn knees
    [0.8, 0.78, 0.74],   // leather
    [1.7, 1.55, 1.35],   // boots: road dust
    [0.8, 0.78, 0.74],   // metal
    [0.75, 0.72, 0.68],  // headcloth
    [1.25, 1.18, 1.05],  // band (desert wraps: dust)
    [0.68, 0.65, 0.6],   // tabard / apron
    [1.0, 1.0, 1.0],     // fletch / lamp
    [0.78, 0.74, 0.68],  // cloak / robe
    [0.8, 0.78, 0.74],   // helm
];
/// Where the head pieces hang (the head joint's rest position in the rig frame).
const KIT_HEAD_PIVOT: Vec3 = Vec3::new(0.0, 1.63, 0.0);
/// `biped::SKIN_JOINTS` index of the head.
const SKIN_HEAD: u16 = 3;

/// A piece's 4 skin influences from its UV0 + UV1: each component = joint + 0.005 + weight * 0.98
/// (people.py `encode_weights`). Weights renormalised; no data → all on the hips.
fn decode_influences(uv0: [f32; 2], uv1: [f32; 2]) -> ([u16; 4], [f32; 4]) {
    let mut j = [0u16; 4];
    let mut w = [0.0f32; 4];
    for (i, v) in [uv0[0], uv0[1], uv1[0], uv1[1]].into_iter().enumerate() {
        let jj = v.floor().clamp(0.0, 13.0);
        j[i] = jj as u16;
        w[i] = ((v - jj - 0.005) / 0.98).clamp(0.0, 1.0);
    }
    let sum: f32 = w.iter().sum();
    if sum > 1e-4 {
        w.iter_mut().for_each(|x| *x /= sum);
    } else {
        w = [1.0, 0.0, 0.0, 0.0];
    }
    (j, w)
}

/// Merge people.glb pieces into ONE mesh skinned to `biped::SKIN_JOINTS`, in the rig frame. Head
/// pieces (`head == true`, authored in the head joint's frame) are hung at the head pivot and
/// scaled by `head_scale` as far as they are head-weighted, so the neck stub stays body-sized and
/// a kid's big head still meets a slim neck. The rest-pose position also goes into UV0.xy + UV1.x
/// (UV1.y = 64 flags it): the creature shader textures in that space, so the scanned detail layers
/// stay put on a bending limb instead of swimming through it.
fn skinned_body(parts: Vec<(Mesh, bool)>, head_scale: f32) -> Option<Mesh> {
    use bevy::asset::RenderAssetUsages;
    use bevy::mesh::{Indices, PrimitiveTopology, VertexAttributeValues as V};
    let (mut pos, mut nrm, mut col) = (Vec::new(), Vec::new(), Vec::new());
    let (mut uv0, mut uv1, mut ji, mut jw, mut idx) = (Vec::new(), Vec::new(), Vec::new(), Vec::new(), Vec::new());
    for (m, head) in parts {
        let base = pos.len() as u32;
        let (Some(V::Float32x3(p)), Some(V::Float32x3(n)), Some(V::Float32x4(c)), Some(V::Float32x2(a)), Some(V::Float32x2(b))) = (
            m.attribute(Mesh::ATTRIBUTE_POSITION),
            m.attribute(Mesh::ATTRIBUTE_NORMAL),
            m.attribute(Mesh::ATTRIBUTE_COLOR),
            m.attribute(Mesh::ATTRIBUTE_UV_0),
            m.attribute(Mesh::ATTRIBUTE_UV_1),
        ) else {
            return None; // an old (rigid, unweighted) people.glb: no kit body
        };
        for k in 0..p.len() {
            let (j, w) = decode_influences(a[k], b[k]);
            let mut v = Vec3::from(p[k]);
            if head {
                let hw: f32 = (0..4).filter(|&i| j[i] == SKIN_HEAD).map(|i| w[i]).sum();
                v = KIT_HEAD_PIVOT + v * (1.0 + (head_scale - 1.0) * hw);
            }
            pos.push(v.to_array());
            nrm.push(n[k]);
            col.push(c[k]);
            uv0.push([v.x, v.y]);
            uv1.push([v.z, 64.0]);
            ji.push(j);
            jw.push(w);
        }
        match m.indices() {
            Some(Indices::U32(i)) => idx.extend(i.iter().map(|x| x + base)),
            Some(Indices::U16(i)) => idx.extend(i.iter().map(|&x| x as u32 + base)),
            None => idx.extend(base..base + p.len() as u32),
        }
    }
    let mut out = Mesh::new(PrimitiveTopology::TriangleList, RenderAssetUsages::default());
    out.insert_attribute(Mesh::ATTRIBUTE_POSITION, pos);
    out.insert_attribute(Mesh::ATTRIBUTE_NORMAL, nrm);
    out.insert_attribute(Mesh::ATTRIBUTE_COLOR, V::Float32x4(col));
    out.insert_attribute(Mesh::ATTRIBUTE_UV_0, uv0);
    out.insert_attribute(Mesh::ATTRIBUTE_UV_1, uv1);
    out.insert_attribute(Mesh::ATTRIBUTE_JOINT_INDEX, V::Uint16x4(ji));
    out.insert_attribute(Mesh::ATTRIBUTE_JOINT_WEIGHT, jw);
    out.insert_indices(Indices::U32(idx));
    Some(out)
}

/// The realistic townsperson (Blender pieces, `people.glb`) for the same biped joints as the box
/// peasant: same trade marks (straw hat + apron, miner's helmet + lamp, steel helm + plate +
/// livery tabard + pauldrons + shield, archer's hood + jerkin + quiver + bracer + bow, desert
/// turban / cloak / sash / robe / wraps + sandals) and the same props (`peasant_tools`), recoloured
/// with the caller's skin / tunic / trouser so the town keeps its variety; `look` adds face / hair /
/// beard / hood variety. The body is ONE mesh skinned to the joints ([`BipedMeshes::skin`]).
/// `None` without the kit → the box-built body.
fn kit_peasant_meshes(kind: PeasantKind, skin: u32, tunic: u32, trouser: u32, kid: bool, desert: bool, look: u32) -> Option<BipedMeshes> {
    use PeasantKind::*;
    let kit = kit_people()?;
    let (face, hair_style, beard, tone, everyday_hat) = LOOK_TABLE[(look % LOOKS) as usize];
    let skin = if desert { tan_skin(skin) } else { skin };
    let trouser = if desert { DESERT_PANT } else { trouser };
    let worker = matches!(kind, Woodcutter | Farmer | Miner | Unemployed);
    let hood = HOOD_DYES[(look as usize / 3) % HOOD_DYES.len()];

    // Headgear marks the trade; the unemployed (and the caged captives) wear an everyday hood or
    // cap by look, kids go bare-headed.
    let hat: Option<&str> = match kind {
        _ if desert && worker => Some("turban"),
        Guard if desert => Some("warhelm"),
        Archer if desert => Some("headwrap"),
        Farmer => Some("straw"),
        Miner => Some("miner"),
        Guard => Some("helm"),
        Archer => Some("archer"),
        Woodcutter => Some(if look % 2 == 0 { "cap" } else { "hood" }),
        Unemployed if kid => None,
        Unemployed => [None, Some("hood"), Some("cap")][everyday_hat as usize],
    };
    // Hoods / wraps hide the hair; kids are never bald or bearded; woodcutters and desert men
    // always wear a beard (the box peasant's woodcutter beard + the rival's look).
    // (The steel helm counts: hair under it would be hidden tris on every soldier.)
    let covered = matches!(hat, Some("hood" | "archer" | "turban" | "headwrap" | "warhelm" | "helm"));
    // Under a cap / helmet / brim only the crop (or the bald fringe) — a fringe or a long mane
    // would poke through the headgear's front.
    let hair_style = match hair_style {
        "bald" if kid => "crop",
        "bald" => "bald",
        _ if hat.is_some() => "crop",
        s => s,
    };
    let beard = match () {
        _ if kid => None,
        _ if kind == Woodcutter => beard.or(Some("full")),
        _ if desert => beard.or(Some("short")),
        _ => beard,
    };
    let face = if kid { "kid" } else { face };

    // Region palette (order = people.py: SKIN, LIP, EYE, HAIR, TUNIC, TRIM, TROUSER, LEATHER, BOOT,
    // METAL, HEADCLOTH, BAND, TABARD, FLETCH, CLOAK, HELM).
    let (metal, metal_surf) = match kind {
        Guard if desert => (DESERT_ARMOR, Surf::Scale), // sun-bleached lamellar, not steel
        Guard => (PLATE, Surf::Metal),
        _ => (IRON, Surf::Metal),
    };
    let headcloth = match hat {
        Some("straw") => STRAW,
        Some("turban" | "warhelm" | "headwrap") => DESERT_CLOTH,
        Some("archer") => LEATHER,
        _ => hood,
    };
    let band = match kind {
        _ if desert => DESERT_BAND,
        Archer => ARCHER_BAND,
        Farmer => LEATHER,
        _ => mix_hex(hood, 0x000000, 0.45),
    };
    let tabard = match kind {
        Guard if desert => LIVERY_CRIMSON,
        Guard => LIVERY_BLUE,
        _ => PATCH,
    };
    let (accent, accent_surf) = match kind {
        Miner => (LAMP, Surf::Metal),
        _ if desert => (DESERT_FLETCH, Surf::Cloth),
        _ => (FLETCH, Surf::Cloth),
    };
    let c = |hex: u32, s: Surf| (lin(hex), s);
    let palette = [
        c(skin, Surf::Skin),
        c(mix_hex(skin, 0x7a3a34, 0.42), Surf::Skin),
        c(0x2a1e17, Surf::Skin), // the iris (the whites of the eye are baked weathering)
        c(HAIR_TONES[tone], Surf::Fur),
        c(tunic, Surf::Cloth),
        (crate::palette::lin_scaled(tunic, 0.62), Surf::Cloth),
        c(trouser, Surf::Cloth),
        c(LEATHER, Surf::Scale),
        c(if desert { DESERT_SANDAL } else { BOOT }, Surf::Scale),
        c(metal, metal_surf),
        c(headcloth, Surf::Cloth),
        c(band, Surf::Cloth),
        c(tabard, Surf::Cloth),
        c(accent, accent_surf),
        c(DESERT_CLOAK, Surf::Cloth),
        c(if desert { DESERT_BRONZE } else { PLATE }, Surf::Metal),
    ];

    // The pieces this person wears (any missing piece → no kit body).
    let mut names: Vec<String> = vec!["hu_trunk".into()];
    // Workers roll their sleeves up; soldiers and the desert folk keep them down; the idle vary.
    let fore = match kind {
        Guard => "sleeve",
        Archer => "bare",
        Unemployed if look % 2 == 1 => "sleeve",
        _ if desert => "sleeve",
        _ => "bare",
    };
    let legs = if desert { "hu_leg_wrap" } else { "hu_leg" };
    for s in ["l", "r"] {
        names.push(format!("hu_arm_{fore}_{s}"));
        names.push(format!("{legs}_{s}"));
    }
    names.push(format!("hu_head_{face}"));
    if !covered {
        names.push(format!("hu_hair_{hair_style}"));
    }
    if let Some(b) = beard {
        names.push(format!("hu_beard_{b}_{face}"));
    }
    if let Some(h) = hat {
        names.push(format!("hu_hat_{h}"));
    }
    match kind {
        // The farmer's apron is his trade mark (a desert farmer's thobe + turban do that job).
        Farmer if !desert => names.push("hu_apron".into()),
        Guard => {
            names.push("hu_guard".into());
            // Steel pauldrons on our militia; the rival's sandy lamellar goes without (its
            // desert cloak covers the shoulders — and that keeps the outfit inside the budget).
            if !desert {
                names.extend(["hu_pauldron_l", "hu_pauldron_r"].map(String::from));
            }
        }
        Archer => {
            names.push("hu_archer".into());
            if fore == "bare" {
                names.push("hu_bracer_l".into());
            }
        }
        _ => {}
    }
    if desert {
        names.push("hu_cloak".into());
        if worker {
            names.extend(["hu_sash", "hu_robe"].map(String::from));
        }
    }
    let head_frame = |n: &str| ["hu_head", "hu_hair", "hu_beard", "hu_hat"].iter().any(|p| n.starts_with(p));
    let parts = names
        .iter()
        .map(|n| Some((kit.people_part(n, &palette, &KIT_WEATHER)?, head_frame(n))))
        .collect::<Option<Vec<_>>>()?;
    let body = skinned_body(parts, kit_head_scale(kid))?;
    let (weapon, shield) = kit_tools(kit, kind, desert);
    let empty = || Mesh::new(bevy::mesh::PrimitiveTopology::TriangleList, bevy::asset::RenderAssetUsages::default());
    Some(BipedMeshes {
        hips: empty(),
        torso: empty(),
        neck: empty(),
        head: empty(),
        shoulder_l: empty(),
        shoulder_r: empty(),
        elbow_l: empty(),
        elbow_r: empty(),
        hip_l: empty(),
        hip_r: empty(),
        knee_l: empty(),
        knee_r: empty(),
        foot_l: empty(),
        foot_r: empty(),
        weapon,
        shield,
        lion: None,
        skin: Some(body),
    })
}

/// The sculpted trade tool (`Sword` pivot) + off-hand prop (`Shield` pivot) for `kind` from
/// `people.glb` — same grip origins / frames as the box props in [`peasant_tools`], so every pose
/// holds them identically. A slot whose part is missing falls back to the box prop. Tools carry
/// their own palette (region order = people.py `T_*`: wood, iron, leather, accent, bronze, string).
fn kit_tools(kit: &crate::realforest::Kit, kind: PeasantKind, desert: bool) -> (Option<Mesh>, Option<Mesh>) {
    use PeasantKind::*;
    let livery = if desert { LIVERY_CRIMSON } else { LIVERY_BLUE };
    let (wood, accent) = match kind {
        Archer => (BOW_WOOD, if desert { DESERT_FLETCH } else { FLETCH }),
        _ => (WOOD, livery),
    };
    let palette = [
        (lin(wood), Surf::Stone),
        (lin(0xb4b9c2), Surf::Metal),
        (lin(LEATHER), Surf::Scale),
        (lin(accent), Surf::Cloth),
        (lin(DESERT_BRONZE), Surf::Metal),
        (lin(BOW_STRING), Surf::Cloth),
    ];
    let weapon = match kind {
        Woodcutter => Some("hu_tool_axe"),
        Miner => Some("hu_tool_pick"),
        Farmer => Some("hu_tool_hoe"),
        Guard if desert => Some("hu_tool_scimitar"),
        Guard => Some("hu_tool_sword"),
        Archer => Some("hu_tool_arrow"),
        Unemployed => None,
    };
    let (box_weapon, box_shield) = peasant_tools(kind, desert);
    let weapon = weapon.and_then(|n| kit.creature_part(n, &palette).or(box_weapon));
    let shield = match kind {
        // Built facing +Z; the same yaw as the box buckler counters the hero's edge-on carry.
        Guard => kit.creature_part("hu_tool_shield", &palette).map(|m| m.rotated_by(Quat::from_rotation_y(1.15))).or(box_shield),
        Archer => kit.creature_part("hu_tool_bow", &palette).or(box_shield),
        _ => None,
    };
    (weapon, shield)
}

/// Build the per-joint peasant meshes for `kind` with the given body colours. `look` (any u32,
/// used mod [`LOOKS`]) picks the face / hair / beard / everyday headgear of the realistic kit
/// body; the box-built fallback ignores it.
pub fn peasant_biped_meshes(kind: PeasantKind, skin: u32, tunic: u32, trouser: u32, kid: bool, desert: bool, look: u32) -> BipedMeshes {
    if let Some(m) = kit_peasant_meshes(kind, skin, tunic, trouser, kid, desert, look) {
        return m;
    }
    use PeasantKind::*;
    // Surfaces: leather/wood-trim/straw/hair/patches read as matte Cloth; iron + the brass lamp as
    // Metal; skin/eyes/mouth as Skin. (WOOD here is a pale trim hue on tool hafts — flat Skin avoids
    // a cloth weave on bare wood.)
    let woodcutter = kind == Woodcutter;
    let farmer = kind == Farmer;
    let unemployed = kind == Unemployed;
    let miner = kind == Miner;
    let guard = kind == Guard;
    let archer = kind == Archer;

    // Desert (rival) people are a foreign desert folk: sun-tanned skin and loose sand linens, not the
    // player town's pale skin + brown trews. (Workers also get the full thobe + sandals below.)
    let skin = if desert { tan_skin(skin) } else { skin };
    let trouser = if desert { DESERT_PANT } else { trouser };
    // Fletching (quiver tufts / nocked arrow / hood feather) is faction-dyed: militia blue for
    // ours, crimson for the rival's desert bowmen.
    let fletch = if desert { DESERT_FLETCH } else { FLETCH };

    let mut hips_parts = vec![
        frustum(0.2, 0.17, 0.13, v(0.0, -0.06, 0.0), trouser, Surf::Cloth), // pelvis
        frustum(0.24, 0.22, 0.06, v(0.0, 0.03, 0.01), LEATHER, Surf::Cloth), // belt
        bx(0.055, 0.04, 0.025, v(0.0, 0.035, 0.225), IRON, Surf::Metal), // buckle
    ];
    if desert && !guard && !archer {
        // A flowing thobe skirt flaring from the waist down over the thighs — the dominant exotic
        // silhouette (fighters — the armoured guard's tabard, the archer's jerkin — keep their legs
        // free, so the robe is worker-only). Knee-length
        // so the loose linen shins + sandals still show below. Embroidered dark hem band at the edge.
        hips_parts.push(frustum(0.215, 0.33, 0.46, v(0.0, -0.22, 0.0), DESERT_ROBE, Surf::Cloth)); // robe skirt
        hips_parts.push(frustum(0.335, 0.34, 0.05, v(0.0, -0.43, 0.0), DESERT_BAND, Surf::Cloth)); // hem band
    }
    let hips = group(hips_parts);

    // A clean tunic: cone body + collar + hem + belt only. The old vest panel / diagonal shoulder
    // strap / per-trade patches were removed — they piled up into visual clutter on the chest and
    // read as "random junk". A worker's trade is now told by his TOOL + headgear (and the farmer's
    // apron / desert cloak / guard plate below), not by chest decals.
    let mut torso_parts = vec![
        frustum_s(0.25, 0.2, 0.44, v(1.05, 1.0, 0.8), v(0.0, 0.14, 0.02), tunic, Surf::Cloth), // tunic
        frustum_s(0.14, 0.17, 0.045, v(1.05, 1.0, 0.8), v(0.0, 0.34, 0.04), LEATHER, Surf::Cloth), // collar
        frustum_s(0.23, 0.22, 0.04, v(1.08, 1.0, 0.82), v(0.0, -0.08, 0.02), LEATHER, Surf::Cloth), // hem
    ];
    if farmer && !desert {
        // The apron is the farmer's clean trade mark (kept; the suspenders hold it up). Desert farmers
        // skip it — their thobe + turban already mark them, and a European apron would clash.
        torso_parts.push(bxr(0.2, 0.32, 0.035, v(0.0, 0.08, 0.18), rx(0.08), PATCH, Surf::Cloth)); // apron
        for side in [-1.0_f32, 1.0] {
            torso_parts.push(bxr(0.035, 0.42, 0.035, v(side * 0.08, 0.17, 0.195), rz(side * 0.12), LEATHER, Surf::Cloth)); // suspender
        }
    }
    if desert {
        // A cloak draped down the back — a clear desert silhouette over whatever clothes are under it.
        torso_parts.push(bxr(0.36, 0.52, 0.04, v(0.0, 0.04, -0.17), rx(-0.05), DESERT_CLOAK, Surf::Cloth)); // back cloak
        if !guard && !archer {
            // The diagonal sash is the WORKER's desert mark; a soldier wears the steel + tabard below
            // instead (and the archer his own baldric), so fighter vs labourer stays legible even
            // under the shared keffiyeh/cloak.
            torso_parts.push(bxr(0.46, 0.075, 0.05, v(0.0, 0.12, 0.19), rz(0.5), DESERT_BAND, Surf::Cloth)); // chest sash
        }
    }
    if archer {
        // The archer's silhouette from any angle: a leather QUIVER slung on the back (tilted so the
        // shafts poke over the right shoulder) on a diagonal chest baldric, plus a leather jerkin
        // panel over the tunic — lighter kit than the guard's steel (an archer is milicja, not a
        // man-at-arms), but still clearly a FIGHTER against the unarmed workers.
        torso_parts.push(frustum_s(0.25, 0.212, 0.38, v(1.06, 1.0, 0.86), v(0.0, 0.15, 0.025), LEATHER, Surf::Cloth)); // leather jerkin
        torso_parts.push(bxr(0.075, 0.5, 0.03, v(0.0, 0.12, 0.19), rz(0.55), ARCHER_BAND, Surf::Cloth)); // chest baldric
        let qrot = rz(-0.38); // quiver tilts its mouth toward the right shoulder
        torso_parts.push(frustum_r(0.058, 0.046, 0.42, v(0.09, 0.1, -0.19), qrot, LEATHER, Surf::Cloth)); // quiver tube
        torso_parts.push(frustum_r(0.062, 0.06, 0.05, v(0.155, 0.265, -0.19), qrot, ARCHER_BAND, Surf::Cloth)); // mouth band
        // Three spare shafts poking out of the mouth, fletchings up.
        for (dx, dy, dz) in [(0.0_f32, 0.0_f32, 0.0_f32), (0.045, -0.02, 0.03), (0.03, 0.015, -0.035)] {
            let base = v(0.19 + dx, 0.36 + dy, -0.19 + dz);
            torso_parts.push(frustum_r(0.011, 0.011, 0.17, base, qrot, BOW_WOOD, Surf::Skin)); // shaft
            torso_parts.push(bxr(0.045, 0.07, 0.045, base + v(0.035, 0.09, 0.0), qrot, fletch, Surf::Cloth)); // fletch tuft
        }
    }
    if guard {
        // A FIGHTER reads at a glance: a steel breastplate + shoulder pauldrons, over a faction-coloured
        // tabard (blue = player militia, crimson = rival garrison). Unarmed peasants/workers never get
        // this, so the player can tell whom to cut down from whom to spare.
        let livery = if desert { LIVERY_CRIMSON } else { LIVERY_BLUE };
        // Ours is cold STEEL plate; the rival's is PALE SANDY lamellar (sun-bleached leather/scale) so
        // the desert soldier reads light and sandy, not a dark-bronze knight. Desert plate gets scale
        // row lines too. The surface family is Cloth for the sandy leather (matte, not steel-shiny).
        let armor = if desert { DESERT_ARMOR } else { PLATE };
        let armor_surf = if desert { Surf::Cloth } else { Surf::Metal };
        torso_parts.push(frustum_s(0.255, 0.215, 0.40, v(1.08, 1.0, 0.88), v(0.0, 0.16, 0.03), armor, armor_surf)); // breastplate
        torso_parts.push(bxr(0.21, 0.36, 0.03, v(0.0, 0.13, 0.2), rx(0.05), livery, Surf::Cloth)); // tabard front
        for side in [-1.0_f32, 1.0] {
            torso_parts.push(bxr(0.14, 0.08, 0.18, v(side * 0.2, 0.31, 0.02), rz(side * -0.2), armor, armor_surf)); // pauldron
        }
    }
    let torso = group(torso_parts);

    let neck = group(vec![frustum(0.08, 0.09, 0.08, v(0.0, -0.02, 0.0), skin, Surf::Skin)]);

    let mut head_parts = vec![
        bx(0.22, 0.24, 0.2, v(0.0, 0.05, 0.02), skin, Surf::Skin), // face
        bx(0.04, 0.055, 0.035, v(0.0, 0.05, 0.125), skin, Surf::Skin), // nose
        bx(0.07, 0.011, 0.012, v(0.0, -0.005, 0.132), DARK, Surf::Skin), // mouth
    ];
    for side in [-1.0_f32, 1.0] {
        head_parts.push(bx(0.03, 0.018, 0.012, v(side * 0.055, 0.09, 0.126), DARK, Surf::Skin)); // eye
        head_parts.push(bxr(0.042, 0.012, 0.012, v(side * 0.055, 0.12, 0.13), rz(side * if miner { -0.2 } else { 0.12 }), HAIR, Surf::Cloth)); // brow
        head_parts.push(bxr(0.035, 0.055, 0.035, v(side * 0.13, 0.055, 0.0), rz(side * 0.18), skin, Surf::Skin)); // ear
    }
    if (woodcutter || unemployed) && !kid {
        head_parts.push(bxr(0.14, 0.07, 0.028, v(0.0, -0.035, 0.12), rx(0.15), HAIR, Surf::Cloth)); // beard (never on kids — they read as children)
    }
    if desert && !guard && !archer {
        // A fat WRAPPED TURBAN — the rival WORKER's headgear (a soldier wears the bronze war-helm and
        // an archer the sand headwrap below, so the fighters still read apart from the labourer under
        // the shared desert palette).
        // A rounded dome + a banded wrap fold + a side tuck-knot read clearly as a turban, not a cap.
        head_parts.push(frustum(0.16, 0.135, 0.175, v(0.0, 0.16, 0.0), DESERT_CLOTH, Surf::Cloth)); // turban dome
        head_parts.push(frustum(0.168, 0.166, 0.05, v(0.0, 0.12, 0.0), DESERT_BAND, Surf::Cloth)); // wrap fold band
        head_parts.push(bxr(0.06, 0.07, 0.06, v(0.1, 0.255, -0.01), rz(-0.4), DESERT_CLOTH, Surf::Cloth)); // side tuck-knot
        head_parts.push(bxr(0.26, 0.26, 0.03, v(0.0, -0.02, -0.13), rx(-0.12), DESERT_CLOTH, Surf::Cloth)); // long neck drape
        for side in [-1.0_f32, 1.0] {
            head_parts.push(bxr(0.04, 0.22, 0.18, v(side * 0.128, -0.01, 0.0), Quat::IDENTITY, DESERT_CLOTH, Surf::Cloth)); // cheek flap
        }
    } else if farmer {
        head_parts.push(frustum_s(0.2, 0.22, 0.022, v(1.15, 1.0, 0.82), v(0.0, 0.17, 0.0), STRAW, Surf::Cloth)); // brim
        head_parts.push(frustum(0.1, 0.13, 0.09, v(0.0, 0.225, 0.0), STRAW, Surf::Cloth)); // crown
        head_parts.push(frustum(0.105, 0.132, 0.018, v(0.0, 0.195, 0.0), LEATHER, Surf::Cloth)); // hat band
        head_parts.push(bxr(0.018, 0.16, 0.012, v(0.13, 0.23, 0.02), xyz(0.2, 0.0, -0.7), STRAW, Surf::Cloth)); // sprig
    } else if miner {
        head_parts.push(frustum(0.13, 0.145, 0.07, v(0.0, 0.18, 0.0), IRON, Surf::Metal)); // helmet
        head_parts.push(bx(0.18, 0.02, 0.08, v(0.0, 0.16, 0.09), IRON, Surf::Metal)); // brim
        head_parts.push(bx(0.045, 0.04, 0.022, v(0.0, 0.18, 0.14), LAMP, Surf::Metal)); // lamp
        head_parts.push(bx(0.065, 0.055, 0.014, v(0.0, 0.18, 0.132), DARK, Surf::Skin)); // lamp frame
    } else if guard && desert {
        // Rival garrison: a clean SARACEN conical war-helm so the foreign soldier reads exotic at a
        // glance, distinct from the player militia's cold-steel helm. The earlier version stacked a
        // thin spike + finial knob + fat turban + face-veil into a cluttered tower over a faceless
        // head — pared back to ONE tapered bronze cone on a pale turban base band, face left visible.
        let bronze = DESERT_BRONZE;
        head_parts.push(frustum(0.14, 0.158, 0.095, v(0.0, 0.13, 0.0), DESERT_CLOTH, Surf::Cloth)); // turban base band
        head_parts.push(cone(0.135, 0.27, v(0.0, 0.305, 0.0), Quat::IDENTITY, Vec3::ONE, bronze, Surf::Metal)); // conical war-helm
        head_parts.push(bxr(0.22, 0.22, 0.03, v(0.0, -0.02, -0.12), rx(-0.12), DESERT_CLOTH, Surf::Cloth)); // light neck drape
    } else if guard {
        head_parts.push(frustum(0.125, 0.14, 0.11, v(0.0, 0.17, 0.0), PLATE, Surf::Metal)); // steel helm
        head_parts.push(bxr(0.04, 0.1, 0.16, v(0.0, 0.25, 0.0), Quat::IDENTITY, PLATE, Surf::Metal)); // helm crest ridge
        head_parts.push(bx(0.05, 0.11, 0.03, v(0.0, 0.07, 0.12), PLATE, Surf::Metal)); // nasal bar
    } else if archer {
        // A fitted archer's hood: snug skullcap + band, a short drape guarding the neck, and a
        // single fletch-feather tucked in the band — the ranged-fighter headmark (no steel: he
        // stands off the melee). Ours is dark leather + blue feather; the rival's desert bowman
        // wears the same silhouette as a pale sand HEADWRAP + dark agal band + crimson feather,
        // so "archer" and "not ours" both read at a glance.
        let (cap, band) = if desert { (DESERT_CLOTH, DESERT_BAND) } else { (LEATHER, ARCHER_BAND) };
        head_parts.push(frustum(0.115, 0.145, 0.1, v(0.0, 0.17, 0.0), cap, Surf::Cloth)); // skullcap / headwrap
        head_parts.push(frustum(0.148, 0.15, 0.04, v(0.0, 0.115, 0.0), band, Surf::Cloth)); // hood / agal band
        head_parts.push(bxr(0.24, 0.24, 0.03, v(0.0, -0.02, -0.125), rx(-0.12), cap, Surf::Cloth)); // neck drape
        head_parts.push(bxr(0.022, 0.16, 0.045, v(0.1, 0.24, -0.03), xyz(-0.25, 0.0, -0.45), fletch, Surf::Cloth)); // feather
    } else {
        head_parts.push(frustum(0.12, 0.14, 0.075, v(0.0, 0.18, 0.0), HAIR, Surf::Cloth)); // cap
        head_parts.push(bxr(0.17, 0.035, 0.14, v(0.02, 0.23, -0.015), xyz(-0.12, 0.0, if unemployed { 0.2 } else { -0.08 }), HAIR, Surf::Cloth)); // cap top
    }
    let head = group(head_parts);

    let shoulder = || {
        group(vec![
            frustum(0.078, 0.066, 0.28, v(0.0, -0.14, 0.0), tunic, Surf::Cloth), // sleeve
            frustum(0.072, 0.07, 0.045, v(0.0, -0.27, 0.0), LEATHER, Surf::Cloth), // cuff
        ])
    };
    let elbow = |bracer: bool| {
        let mut p = vec![
            frustum(0.058, 0.064, 0.29, v(0.0, -0.145, 0.0), skin, Surf::Skin), // forearm
            frustum(0.066, 0.07, 0.075, v(0.0, -0.22, 0.0), LEATHER, Surf::Cloth), // wrist wrap
            bx(0.07, 0.07, 0.08, v(0.0, -0.22, 0.0), skin, Surf::Skin), // fist
        ];
        if bracer {
            // The archer's BOW-ARM bracer: a laced leather guard over the inner forearm so the
            // released string doesn't flay it — the classic bowman's tell.
            p.push(frustum(0.07, 0.076, 0.15, v(0.0, -0.12, 0.0), LEATHER, Surf::Cloth)); // bracer
            p.push(frustum(0.074, 0.075, 0.025, v(0.0, -0.075, 0.0), ARCHER_BAND, Surf::Cloth)); // lace band
            p.push(frustum(0.074, 0.075, 0.025, v(0.0, -0.165, 0.0), ARCHER_BAND, Surf::Cloth)); // lace band
        }
        group(p)
    };
    let hip = || {
        let mut p = vec![frustum(0.115, 0.097, 0.38, v(0.0, -0.2, 0.0), trouser, Surf::Cloth)]; // thigh
        if unemployed || farmer {
            p.push(bxr(0.075, 0.08, 0.025, v(0.0, -0.2, 0.08), rx(0.1), PATCH, Surf::Cloth)); // knee patch
        }
        group(p)
    };
    let knee = || {
        let mut p = vec![frustum(0.09, 0.095, 0.40, v(0.0, -0.21, 0.0), trouser, Surf::Cloth)]; // shin (runs down to the ankle)
        if desert {
            p.push(frustum(0.095, 0.1, 0.06, v(0.0, -0.36, 0.0), DESERT_BAND, Surf::Cloth)); // bare-leg ankle wrap (no boot)
        } else {
            p.push(frustum(0.092, 0.1, 0.16, v(0.0, -0.35, 0.0), LEATHER, Surf::Cloth)); // boot top wrapping the ankle
        }
        group(p)
    };
    let boot_s = if miner { v(1.05, 1.12, 1.1) } else { Vec3::ONE };
    // Boots for our folk; flat open sandals for the desert people (a thin sole + a toe strap), so even
    // the feet read foreign. A proper boot overlaps the shin (top ~0.195) so the lower leg reads as one
    // piece, not a foot floating below a gap.
    let foot = || {
        if desert {
            group(vec![
                tinted(chamfer_box(0.125, 0.05, 0.24, cham(0.125, 0.05, 0.24)).translated_by(v(0.0, -0.05, 0.05)), DESERT_SANDAL, Surf::Cloth), // sole
                bx(0.12, 0.05, 0.07, v(0.0, -0.005, 0.04), DESERT_BAND, Surf::Cloth), // toe strap
            ])
        } else {
            group(vec![tinted(chamfer_box(0.13, 0.14, 0.2, cham(0.13, 0.14, 0.2)).scaled_by(boot_s).translated_by(v(0.0, -0.025, 0.03)), LEATHER, Surf::Cloth)])
        }
    };

    let (weapon, shield) = peasant_tools(kind, desert);

    BipedMeshes {
        hips,
        torso,
        neck,
        head,
        shoulder_l: shoulder(),
        shoulder_r: shoulder(),
        elbow_l: elbow(archer), // bow arm gets the bracer
        elbow_r: elbow(false),
        hip_l: hip(),
        hip_r: hip(),
        knee_l: knee(),
        knee_r: knee(),
        foot_l: foot(),
        foot_r: foot(),
        weapon,
        shield,
        lion: None,
        skin: None,
    }
}

/// The trade tool on the right hand's `Sword` pivot + the off-hand (`Shield` pivot) prop for
/// `kind` — shared by the box-built peasant above and the realistic kit body
/// ([`kit_peasant_meshes`]), so both carry the exact same, rest-pose-tuned props.
fn peasant_tools(kind: PeasantKind, desert: bool) -> (Option<Mesh>, Option<Mesh>) {
    use PeasantKind::*;
    let woodcutter = kind == Woodcutter;
    let farmer = kind == Farmer;
    let miner = kind == Miner;
    let guard = kind == Guard;
    let archer = kind == Archer;
    let fletch = if desert { DESERT_FLETCH } else { FLETCH };
    // Tool on the right hand (built +Y in sword-local from the fist's grip, edge toward +X). The
    // work tools are full length — the two-handed strokes (`player::anim::toolwork`) grip them with
    // both fists — matching the kit's `people.py` tools (axe/pick head ~0.72-0.76, hoe ~1.2).
    let weapon = if woodcutter {
        Some(group(vec![
            frustum(0.022, 0.026, 0.82, v(0.0, 0.36, 0.0), WOOD, Surf::Skin), // handle
            frustum(0.03, 0.034, 0.07, v(0.0, 0.68, 0.0), IRON, Surf::Metal), // collar
            bxr(0.17, 0.1, 0.04, v(0.07, 0.72, 0.0), rz(0.12), IRON, Surf::Metal), // head
            cone(0.065, 0.13, v(0.2, 0.72, 0.0), rz(-FRAC_PI_2), v(1.0, 0.85, 0.45), IRON, Surf::Metal), // edge
        ]))
    } else if miner {
        Some(group(vec![
            frustum(0.02, 0.024, 0.82, v(0.0, 0.36, 0.0), WOOD, Surf::Skin), // handle
            bx(0.06, 0.08, 0.04, v(0.0, 0.74, 0.0), IRON, Surf::Metal), // socket
            bx(0.40, 0.05, 0.04, v(0.0, 0.74, 0.0), IRON, Surf::Metal), // pick bar
            cone(0.035, 0.12, v(-0.24, 0.72, 0.0), rz(FRAC_PI_2), v(1.0, 1.0, 0.8), IRON, Surf::Metal), // point
            cone(0.03, 0.11, v(0.24, 0.72, 0.0), rz(-FRAC_PI_2), v(1.0, 0.8, 0.45), IRON, Surf::Metal), // chisel
        ]))
    } else if farmer {
        Some(group(vec![
            frustum(0.02, 0.024, 1.25, v(0.0, 0.575, 0.0), WOOD, Surf::Skin), // handle
            frustum(0.032, 0.036, 0.07, v(0.0, 1.2, 0.0), IRON, Surf::Metal), // socket
            bxr(0.15, 0.014, 0.16, v(0.1, 1.19, 0.0), rz(-0.26), IRON, Surf::Metal), // flat hoe blade, canted back
        ]))
    } else if guard && desert {
        // The rival garrison carries a CURVED SCIMITAR (a saracen sabre), not our straight arming
        // sword — segmented along a shallow arc with the cutting edge swept toward +X, bronze hilt.
        let mut parts = vec![
            bx(0.16, 0.05, 0.05, v(0.0, 0.08, 0.0), DESERT_BRONZE, Surf::Metal), // crossguard
            frustum(0.02, 0.018, 0.14, v(0.0, -0.03, 0.0), LEATHER, Surf::Cloth), // grip
            bx(0.05, 0.05, 0.05, v(0.0, -0.11, 0.0), DESERT_BRONZE, Surf::Metal), // pommel
        ];
        // (width, height, offset, z-rotation) — precomputed arc segments (see commit note).
        for (w, h, off, a) in [
            (0.050_f32, 0.15_f32, v(0.007, 0.165, 0.0), -0.1125_f32),
            (0.055, 0.15, v(0.036, 0.291, 0.0), -0.3375),
            (0.060, 0.15, v(0.092, 0.407, 0.0), -0.5625),
            (0.055, 0.15, v(0.173, 0.508, 0.0), -0.7875),
        ] {
            parts.push(bxr(w, h, 0.022, off, rz(a), IRON, Surf::Metal)); // blade segment
        }
        parts.push(cone(0.03, 0.14, v(0.266, 0.591, 0.0), rz(-0.95), v(1.7, 1.0, 0.73), IRON, Surf::Metal)); // swept point
        Some(group(parts))
    } else if guard {
        // A REAL arming sword: a long flat blade tapering to a point above the crossguard — the old
        // "blade" was a degenerate height-0.04 cone (radius 0), so the guard held a bare hilt stub.
        Some(group(vec![
            bx(0.06, 0.46, 0.024, v(0.0, 0.31, 0.0), IRON, Surf::Metal), // blade
            cone(0.03, 0.12, v(0.0, 0.58, 0.0), Quat::IDENTITY, v(2.0, 1.0, 0.8), IRON, Surf::Metal), // point
            bx(0.18, 0.045, 0.05, v(0.0, 0.06, 0.0), IRON, Surf::Metal), // crossguard
            frustum(0.02, 0.018, 0.14, v(0.0, -0.03, 0.0), LEATHER, Surf::Cloth), // grip
            bx(0.05, 0.05, 0.05, v(0.0, -0.11, 0.0), IRON, Surf::Metal), // pommel
        ]))
    } else if archer {
        // A single NOCKED ARROW in the string hand (built +Y like every held weapon, so the shared
        // rest rotation carries it point-down at ease; the bow-draw clip levels it at the target).
        // The hand always shows a "next shaft ready" — low-poly shorthand that keeps the grip
        // honest between shots without swapping meshes; the flying arrow is its own entity
        // (`projectile.rs`).
        Some(group(vec![
            frustum(0.013, 0.013, 0.5, v(0.0, 0.19, 0.0), BOW_WOOD, Surf::Skin), // shaft
            cone(0.026, 0.09, v(0.0, 0.47, 0.0), Quat::IDENTITY, v(1.0, 1.0, 0.5), IRON, Surf::Metal), // bodkin point
            bx(0.055, 0.11, 0.014, v(0.0, -0.01, 0.0), fletch, Surf::Cloth), // fletching vane
            bx(0.014, 0.11, 0.055, v(0.0, -0.01, 0.0), fletch, Surf::Cloth), // crossed vane
        ]))
    } else {
        None // unemployed — empty handed
    };

    // Left hand: WORKERS stay empty (a peasant carries only his trade tool — the old belt-pouch
    // read as random junk and is gone). GUARDS mount a round livery shield: soldier kit that reads
    // "militia" at siege distance (blue = ours, crimson = the rival's, same split as the tabard).
    // The biped animator carries the hero's EDGE-ON shield pose (tuned for the knight's heater), so
    // the disc bakes a +Y counter-rotation to still show its face — same trick as the ork buckler.
    let shield = if guard {
        let livery = if desert { LIVERY_CRIMSON } else { LIVERY_BLUE };
        Some(
            group(vec![
                frustum(0.24, 0.24, 0.04, v(0.0, 0.0, 0.0), WOOD, Surf::Cloth), // wooden disc
                frustum(0.25, 0.25, 0.016, v(0.0, -0.014, 0.0), LEATHER, Surf::Cloth), // rim backing
                frustum(0.17, 0.17, 0.048, v(0.0, 0.0, 0.0), livery, Surf::Cloth), // livery field
                cone(0.06, 0.08, v(0.0, 0.045, 0.0), Quat::IDENTITY, Vec3::ONE, PLATE, Surf::Metal), // boss
            ])
            .rotated_by(Quat::from_rotation_x(FRAC_PI_2)) // disc face → +Z (shield-local)
            .rotated_by(Quat::from_rotation_y(1.15)), // counter the hero pose's edge-on carry
        )
    } else if archer {
        // The LONGBOW rides the off-hand (`Shield`) pivot — grip at the origin, stave arcing in
        // the local Y-Z plane (belly toward +Z, string a straight linen line joining the tips at
        // -Z). Built from a sampled quadratic arc so the limbs read as one bent yew stave, not a
        // stack of boxes. The shared shield rest pose carries it near-vertical along the forearm
        // (a bow at ease); `bow_pose` (player/anim.rs) turns it upright into the draw.
        let tip_y = 0.5_f32;
        let tip_z = -0.12_f32;
        let belly_z = 0.11_f32; // bezier control (grip belly lands ≈ z 0)
        let bez = |t: f32| {
            let u = 1.0 - t;
            v(
                0.0,
                (t * t - u * u) * tip_y, // u²·(-tip_y) + t²·(+tip_y)
                (u * u + t * t) * tip_z + 2.0 * u * t * belly_z,
            )
        };
        let mut parts = vec![
            frustum(0.034, 0.034, 0.15, v(0.0, 0.0, 0.0), LEATHER, Surf::Cloth), // leather grip wrap
            bx(0.014, 1.0, 0.014, v(0.0, 0.0, tip_z), BOW_STRING, Surf::Cloth), // string tip-to-tip
        ];
        const SEGS: usize = 8;
        for i in 0..SEGS {
            let (a, b) = (bez(i as f32 / SEGS as f32), bez((i + 1) as f32 / SEGS as f32));
            let d = b - a;
            let mid = (a + b) * 0.5;
            // Limbs thin toward the tips (0.05 at the grip → 0.028 at a tip).
            let w = 0.05 - 0.022 * ((mid.y.abs() / tip_y).min(1.0));
            parts.push(bxr(
                w,
                d.length() + 0.015,
                w * 1.35,
                mid,
                rx(d.z.atan2(d.y)), // align the box's +Y along the arc segment (Y-Z plane)
                BOW_WOOD,
                Surf::Skin,
            ));
        }
        Some(group(parts))
    } else {
        None
    };

    (weapon, shield)
}

#[cfg(test)]
mod kit_skin_tests {
    use super::*;
    use bevy::mesh::{Indices, PrimitiveTopology, VertexAttributeValues as V};

    /// people.py `encode_weights`: joint + 0.005 + weight * 0.98.
    fn enc(j: u16, w: f32) -> f32 {
        j as f32 + 0.005 + w * 0.98
    }

    #[test]
    fn influences_round_trip() {
        let (j, w) = decode_influences([enc(8, 0.7), enc(0, 0.3)], [0.005, 0.005]);
        assert_eq!((j[0], j[1]), (8, 0));
        assert!((w[0] - 0.7).abs() < 1e-4 && (w[1] - 0.3).abs() < 1e-4 && w[2] == 0.0 && w[3] == 0.0);
        // A full weight on the last joint stays on it (no spill into the next integer).
        let (j, w) = decode_influences([enc(13, 1.0), 0.005], [0.005, 0.005]);
        assert_eq!(j[0], 13);
        assert!((w[0] - 1.0).abs() < 1e-5);
        // No data → everything on the hips.
        assert_eq!(decode_influences([0.0; 2], [0.0; 2]).1, [1.0, 0.0, 0.0, 0.0]);
    }

    fn tri(p: [[f32; 3]; 3], uv0: [f32; 2]) -> Mesh {
        let mut m = Mesh::new(PrimitiveTopology::TriangleList, bevy::asset::RenderAssetUsages::default());
        m.insert_attribute(Mesh::ATTRIBUTE_POSITION, p.to_vec());
        m.insert_attribute(Mesh::ATTRIBUTE_NORMAL, vec![[0.0, 0.0, 1.0]; 3]);
        m.insert_attribute(Mesh::ATTRIBUTE_COLOR, V::Float32x4(vec![[1.0; 4]; 3]));
        m.insert_attribute(Mesh::ATTRIBUTE_UV_0, vec![uv0; 3]);
        m.insert_attribute(Mesh::ATTRIBUTE_UV_1, vec![[0.005, 0.005]; 3]);
        m.insert_indices(Indices::U32(vec![0, 1, 2]));
        m
    }

    #[test]
    fn skinned_body_places_head_pieces_and_keeps_rest_positions() {
        let body = tri([[0.1, 1.0, 0.0], [0.2, 1.0, 0.0], [0.1, 1.1, 0.0]], [enc(0, 1.0), 0.005]);
        // A head piece fully on the head: hung at the pivot and scaled; one on the torso: unscaled.
        let head = tri([[0.0, 0.1, 0.0], [0.05, 0.1, 0.0], [0.0, 0.15, 0.0]], [enc(SKIN_HEAD, 1.0), 0.005]);
        let neck = tri([[0.0, -0.1, 0.0], [0.05, -0.1, 0.0], [0.0, -0.05, 0.0]], [enc(1, 1.0), 0.005]);
        let m = skinned_body(vec![(body, false), (head, true), (neck, true)], 2.0).unwrap();
        let Some(V::Float32x3(p)) = m.attribute(Mesh::ATTRIBUTE_POSITION) else { panic!() };
        assert_eq!(p[0], [0.1, 1.0, 0.0]);
        assert!((Vec3::from(p[3]) - (KIT_HEAD_PIVOT + Vec3::new(0.0, 0.2, 0.0))).length() < 1e-5);
        assert!((Vec3::from(p[6]) - (KIT_HEAD_PIVOT + Vec3::new(0.0, -0.1, 0.0))).length() < 1e-5);
        // The rest position rides in UV0.xy + UV1.x (flagged) for the shader.
        let (Some(V::Float32x2(a)), Some(V::Float32x2(b))) = (m.attribute(Mesh::ATTRIBUTE_UV_0), m.attribute(Mesh::ATTRIBUTE_UV_1)) else {
            panic!()
        };
        assert_eq!([a[3][0], a[3][1], b[3][0]], p[3]);
        assert!(b[3][1] > 32.0);
        let Some(Indices::U32(i)) = m.indices() else { panic!() };
        assert_eq!(i.as_slice(), &[0, 1, 2, 3, 4, 5, 6, 7, 8]);
        let Some(V::Uint16x4(j)) = m.attribute(Mesh::ATTRIBUTE_JOINT_INDEX) else { panic!() };
        assert_eq!(j[3][0], SKIN_HEAD);
    }
}
