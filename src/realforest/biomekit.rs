//! Kit picks for the last low-poly biomes: the rocky highlands, the desert's saguaros and the
//! swamp's trees draw
//! realistic models (`biome_props.glb`, `tools/blender_forest/biome_props.py`, on the scanned
//! `s_rock` / `s_plaster` sets) plus the forest / alpine kit's pines, snags, junipers and tussocks
//! instead of the faceted primitives in `biome_rocky.rs` / `biome_desert.rs`.
//!
//! Placement stays the biome config's own (same RNG, masks, spacing and the low-poly prop's
//! blocker), exactly like the snow kit: only WHAT is drawn changes. Picks hash the position
//! ([`super::rolls`]) so the world layout is identical with the kit on or off.

use super::Kit;

/// What a biome "tree" slot draws.
pub enum KitTree {
    /// A real kit tree (`_lod0`, its `_lod1` follows) — hung under the gameplay entity like the
    /// forest's.
    Tree(usize),
    /// A static kit model (rock spire, cactus) hung under the gameplay entity; `sway` = keep the
    /// wind sway the low-poly prop had (a cactus flexes a hair, a rock pillar must not); the f32
    /// scales the model under the slot (cypress knees / krummholz are far smaller than a tree).
    Static(&'static str, bool, f32),
    /// Open marsh: no tree at all — the slot becomes a merged reed / sedge bed `(model, scale ×)`,
    /// or bare blackwater (`None`); no gameplay entity and no trunk blocker.
    Open(Option<(&'static str, f32)>),
}

/// Does the kit take over the rocky biome? Needs `biome_props.glb` (else the low-poly scatter stays).
pub fn rocky(kit: &Kit) -> bool {
    kit.has("rk_crag_a")
}

/// Does the kit take over the desert saguaros?
pub fn desert(kit: &Kit) -> bool {
    kit.has("ds_saguaro_a")
}

/// Kit "tree" for rocky tree-class source variant `src` (0..1 hoodoos, 2..3 wind-bent pines, 4 snag).
/// The rocky highland is harsh alpine rock, NOT the forest: no forest pines / snags here — only
/// the alpine kit's wind-flagged timberline spruce and, where the old snag stood, a krummholz mat
/// (wind-crippled dwarf conifer).
pub fn rocky_tree(kit: &Kit, src: usize, x: f32, z: f32) -> Option<KitTree> {
    let (a, _) = super::rolls(x, z);
    match src {
        0 => Some(KitTree::Static("rk_spire_a", false, 1.0)),
        1 => Some(KitTree::Static("rk_spire_b", false, 1.0)),
        // Sparse timberline: a wind-flagged spruce, every third slot a krummholz mat instead.
        2 | 3 if a < 0.66 => kit.pick_named(&["spruce_flag_lod0"], 0.0).map(KitTree::Tree),
        2 | 3 => kit.has("krummholz_a").then_some(KitTree::Static(["krummholz_a", "krummholz_b"][(a * 13.0) as usize % 2], true, 0.8)),
        _ => kit.has("krummholz_b").then_some(KitTree::Static(["krummholz_b", "krummholz_a"][(a * 7.0) as usize % 2], true, 0.8)),
    }
}

/// Kit prop for rocky passive class `class` (0 = dry shrub, 1 = crags + cairn, 3 = scree), source
/// variant `src`: (model, scale ×). `None` = leave the spot bare (never a forest bush).
pub fn rocky_prop(kit: &Kit, class: usize, src: usize, x: f32, z: f32) -> Option<(usize, f32)> {
    let (a, b) = super::rolls(x, z);
    let pick = |names: &[&str], s: f32| kit.pick_named(names, b).map(|m| (m, s));
    match (class, src) {
        // Dry highland scrub: creeping juniper / krummholz mats, dry tussocks, loose scree.
        (0, _) if a < 0.35 => pick(&["juniper_a"], 0.55),
        (0, _) if a < 0.6 => pick(&["krummholz_a", "krummholz_b"], 0.5),
        (0, _) if a < 0.85 => pick(&["tussock_a", "tussock_b"], 1.1),
        (0, _) => pick(&["rk_scree_a", "rk_scree_b"], 0.8),
        (1, 0) => pick(&["rk_crag_a"], 1.0),
        (1, 1) => pick(&["rk_crag_b"], 1.0),
        (1, 2) => pick(&["rk_crag_c"], 1.0),
        (1, _) => pick(&["rk_cairn"], 1.0),
        (3, 0) => pick(&["rk_scree_a"], 1.0),
        (3, _) => pick(&["rk_scree_b"], 1.0),
        _ => None,
    }
}

/// Kit ground cover for rocky cover class `class` (0 = pebbles, 1 = dry tufts, 2 = lichen
/// litter): (model, scale ×). Wind-scoured alpine ground — pebbles, scree and dry tussocks, no
/// lush meadow grass or flowers.
pub fn rocky_cover(kit: &Kit, class: usize, x: f32, z: f32) -> Option<(usize, f32)> {
    let (a, b) = super::rolls(x, z);
    let pick = |names: &[&str], s: f32| kit.pick_named(names, b).map(|m| (m, s));
    match class {
        0 => pick(&["rk_pebbles"], 1.0),
        1 if a < 0.7 => pick(&["tussock_a", "tussock_b"], 0.65),
        1 => pick(&["rk_pebbles"], 1.2),
        2 if a < 0.55 => pick(&["rk_pebbles"], 1.4),
        2 if a < 0.75 => pick(&["rk_scree_a", "rk_scree_b"], 0.45),
        2 => pick(&["tussock_b"], 0.5),
        _ => None,
    }
}

/// Kit saguaro for desert tree-class source variant `src` (0 = single arm, 1 = two arms, 2 = young).
pub fn saguaro(src: usize) -> KitTree {
    KitTree::Static(["ds_saguaro_b", "ds_saguaro_a", "ds_saguaro_c"][src.min(2)], true, 1.0)
}

/// Forest tree slot near the bog: the pines thin out toward the swamp (a waterlogged edge suits
/// alder / birch-like broadleaf, not conifers) and the last trees before the mire are the odd
/// drowned snag. Position-hashed swap of the drawn model only — placement and RNG untouched.
pub fn forest_tree_near_swamp(kit: &Kit, lod0: usize, x: f32, z: f32) -> usize {
    let e = crate::worldmap::region_edge_world(x, z, crate::biome::Biome::Swamp);
    if e < -26.0 {
        return lod0;
    }
    let near = ((e + 26.0) / 22.0).clamp(0.0, 1.0); // 0 at 26u out → 1 at 4u from the bog edge
    let (a, b) = crate::realforest::rolls(x, z);
    let is_pine = ["pine_a_lod0", "pine_b_lod0", "pine_c_lod0"].iter().any(|n| kit.model(n) == Some(lod0));
    if is_pine && a < near * 0.9 {
        let alt = if b < 0.5 { "beech_a_lod0" } else { "beech_b_lod0" };
        return kit.model(alt).unwrap_or(lod0);
    }
    if e > -6.0 && b < 0.16 {
        return kit.model("dead_a_lod0").unwrap_or(lod0);
    }
    lod0
}

/// Desert tree slot at the biome border: a saguaro only where the ground already reads as sand
/// (`worldmap::biome_cover_world` — the same ecotone cut the vertex colour paints), and only the odd
/// one in the transition; further out the slot is dry scrub, and on ground that is still turf
/// nothing at all. Position-hashed, so the scatter's RNG stream (and every later site) is untouched.
pub fn desert_tree(src: usize, x: f32, z: f32) -> KitTree {
    let c = crate::worldmap::biome_cover_world(x, z, crate::biome::Biome::Desert);
    let (a, b) = crate::realforest::rolls(x, z);
    if c > 0.9 || (c > 0.72 && a < 0.3) {
        saguaro(src)
    } else if c > 0.3 && b < 0.7 {
        KitTree::Open(Some((if a < 0.5 { "ds_deadbush_a" } else { "ds_deadbush_b" }, 1.0)))
    } else {
        KitTree::Open(None)
    }
}

/// Desert ground cover at the border (low-poly classes: 0 pebbles, 1 dry grass, 2 succulent,
/// 3 brittlebush / poppy litter): on the transition only the dry grass tufts and the odd pebble
/// reach out; the succulents and blooms keep to the real sand.
pub fn desert_cover_ok(class: usize, x: f32, z: f32) -> bool {
    let c = crate::worldmap::biome_cover_world(x, z, crate::biome::Biome::Desert);
    match class {
        1 => c > 0.15,
        0 => c > 0.45,
        _ => c > 0.8,
    }
}

/// Does the kit take over the swamp? Needs `swamp_flora.glb` — the swamp draws ONLY its own
/// species (never the forest's oaks / beeches / snag / stump); without the file the low-poly
/// mangroves stay.
pub fn swamp(kit: &Kit) -> bool {
    kit.has("cypress_a_lod0")
}

/// Low-frequency "hammock" field over world `(x, z)`, 0..1: two octaves of hashed value noise
/// (~34u lattice + a ~13u ragged edge). Where it is high the swamp keeps its tree islands; the
/// rest is open marsh. A pure function of the position (deterministic, off the scatter RNG), and
/// biome-local: it knows nothing of the swamp region's centre or size, so it follows whatever
/// footprint the region has.
pub fn swamp_hammock(x: f32, z: f32) -> f32 {
    fn lattice(ix: i32, iz: i32, seed: u32) -> f32 {
        let mut v = (ix as u32).wrapping_mul(0x9E37_79B1) ^ (iz as u32).wrapping_mul(0x85EB_CA77) ^ seed;
        v ^= v >> 15;
        v = v.wrapping_mul(0x2C1B_3C6D);
        v ^= v >> 12;
        v = v.wrapping_mul(0x297A_2D39);
        v ^= v >> 15;
        (v >> 8) as f32 / (1u32 << 24) as f32
    }
    fn value(x: f32, z: f32, seed: u32) -> f32 {
        let (fx, fz) = (x.floor(), z.floor());
        let (ix, iz) = (fx as i32, fz as i32);
        let s = |t: f32| t * t * (3.0 - 2.0 * t);
        let (tx, tz) = (s(x - fx), s(z - fz));
        let a = lattice(ix, iz, seed) + (lattice(ix + 1, iz, seed) - lattice(ix, iz, seed)) * tx;
        let b = lattice(ix, iz + 1, seed) + (lattice(ix + 1, iz + 1, seed) - lattice(ix, iz + 1, seed)) * tx;
        a + (b - a) * tz
    }
    value(x / 34.0 + 0.37, z / 34.0 - 0.61, 0x5A3F_11C7) * 0.72 + value(x / 13.0, z / 13.0, 0x0D15_EA5E) * 0.28
}

/// [`swamp_hammock`] thresholds: the island core (≈ a third of the swamp) and its fringe.
pub const HAMMOCK_CORE: f32 = 0.57;
pub const HAMMOCK_FRINGE: f32 = 0.52;

/// Kit tree for swamp tree-class source variant `src` (0..2 the old mangroves, 3..4 the old
/// cypress-knee stumps). The swamp is an OPEN wetland, not a forest: full-crowned bald cypresses
/// and willows stand only on the hammocks (tree islands, [`swamp_hammock`]) and a quarter of those
/// are drowned snags already; a fringe of knees and bleached snags rings each island; between
/// them lies open marsh — reed / cattail beds, sedge tussocks and blackwater, with the odd lone
/// dead snag or knot of knees standing in the water.
pub fn swamp_tree(kit: &Kit, src: usize, x: f32, z: f32) -> Option<KitTree> {
    let (a, b) = super::rolls(x, z);
    let snag = ["snag_a_lod0", "snag_b_lod0"][(a * 31.0) as usize % 2];
    let knees = |s: f32| KitTree::Static(["knees_a", "knees_b"][(b * 17.0) as usize % 2], false, s);
    let cattail = ["sw_cattail_a", "sw_cattail_b"][(b * 5.0) as usize % 2];
    let h = swamp_hammock(x, z);
    let name = if h >= HAMMOCK_CORE {
        match src {
            3 => return Some(KitTree::Static("knees_a", false, 0.6)),
            _ if src >= 4 => return Some(KitTree::Static("knees_b", false, 0.6)),
            _ if a < 0.26 => snag,
            0 => "cypress_a_lod0",
            1 => ["cypress_b_lod0", "willow_a_lod0"][(a * 7.0) as usize % 2],
            _ => ["cypress_a_lod0", "cypress_b_lod0"][(a * 7.0) as usize % 2],
        }
    } else if h >= HAMMOCK_FRINGE {
        // Island fringe: knees and drowned snags, the odd young cypress, reeds between.
        match a {
            _ if a < 0.30 => return Some(knees(0.55)),
            _ if a < 0.58 => snag,
            _ if a < 0.68 => "cypress_b_lod0",
            _ => return Some(KitTree::Open(Some((cattail, 1.25)))),
        }
    } else {
        // Open marsh: reed beds, sedge tussocks and bare blackwater; a lone dead snag here and
        // there so the flats never read as an empty lawn. (No knees out here: cypress knees grow
        // round a cypress — strewn alone over the flats they read as dark pegs / "dots".)
        match a {
            _ if a < 0.085 => snag,
            _ if a < 0.62 => return Some(KitTree::Open(Some((cattail, 1.1 + b * 0.5)))),
            _ if a < 0.86 => return Some(KitTree::Open(Some(("sw_sedge_a", 1.3 + b * 0.5)))),
            _ => return Some(KitTree::Open(None)),
        }
    };
    kit.pick_named(&[name], 0.0).map(KitTree::Tree)
}

/// Load-time pass over a swamp tree's `swamp_cards` part (`cypress_*` / `willow_*`, both LODs):
/// thin and recolour the crown so it stops reading as a closed forest-green canopy.
///
/// Cards are found as connected triangle islands; the atlas cell under each (by its mean U:
/// frond 0..¼, Spanish moss ¼..½, willow strand ½..¾) says what it is. Per card, hashed from its
/// centroid (stable across runs):
/// - fronds: ~30 % dropped (LOD1 ~22 %, its cards are bigger) → a gappy, see-through crown, and
///   the rest tinted olive / rusty-bronze / sage instead of one fresh green;
/// - Spanish moss: most festoons dropped (LOD1 nearly all — at distance they read as pale slabs)
///   and the survivors darkened to a dull grey-green;
/// - willow strands: a light thinning only.
///
/// Runs once on the CPU mesh before upload; nothing touches the asset afterwards.
pub fn thin_swamp_crown(name: &str, mesh: &mut bevy::prelude::Mesh) {
    use bevy::mesh::{Indices, VertexAttributeValues};
    use bevy::prelude::Mesh;
    if !(name.starts_with("cypress_") || name.starts_with("willow_")) {
        return;
    }
    let lod1 = name.ends_with("_lod1");
    let Some(VertexAttributeValues::Float32x3(pos)) = mesh.attribute(Mesh::ATTRIBUTE_POSITION) else { return };
    let pos = pos.clone();
    let Some(VertexAttributeValues::Float32x2(uv)) = mesh.attribute(Mesh::ATTRIBUTE_UV_0) else { return };
    let uv = uv.clone();
    let Some(idx) = mesh.indices().map(|i| i.iter().map(|v| v as u32).collect::<Vec<u32>>()) else { return };
    let n = pos.len();
    // Union-find over shared vertices → one root per card.
    let mut parent: Vec<u32> = (0..n as u32).collect();
    fn find(p: &mut [u32], mut v: u32) -> u32 {
        while p[v as usize] != v {
            p[v as usize] = p[p[v as usize] as usize];
            v = p[v as usize];
        }
        v
    }
    for t in idx.chunks_exact(3) {
        let a = find(&mut parent, t[0]);
        for &o in &t[1..] {
            let b = find(&mut parent, o);
            if a != b {
                parent[b as usize] = a;
            }
        }
    }
    // Per card: centroid + mean U.
    let mut acc: std::collections::HashMap<u32, ([f32; 3], f32, f32)> = std::collections::HashMap::new();
    for v in 0..n {
        let r = find(&mut parent, v as u32);
        let e = acc.entry(r).or_insert(([0.0; 3], 0.0, 0.0));
        for k in 0..3 {
            e.0[k] += pos[v][k];
        }
        e.1 += uv[v][0];
        e.2 += 1.0;
    }
    // (kind 0 frond / 1 moss / 2 willow / 3 other, keep?, colour multiplier)
    let mut verdict: std::collections::HashMap<u32, (bool, [f32; 3])> = std::collections::HashMap::new();
    for (&r, &(c, u, cnt)) in &acc {
        let (cx, cz) = (c[0] / cnt, c[2] / cnt);
        let (h1, h2) = super::rolls(cx * 7.3 + c[1] / cnt * 3.1, cz * 7.3 - c[1] / cnt * 1.7);
        let u = u / cnt;
        let v = match u {
            _ if u < 0.25 => {
                let drop = if lod1 { 0.22 } else { 0.30 };
                // Olive, rusty-bronze, sage, and the odd fresh spray — never one forest green.
                let tint = match h2 {
                    _ if h2 < 0.34 => [0.92, 0.86, 0.52],
                    _ if h2 < 0.52 => [1.05, 0.72, 0.42],
                    _ if h2 < 0.80 => [0.80, 0.84, 0.66],
                    _ => [0.95, 0.95, 0.80],
                };
                (h1 >= drop, tint)
            }
            _ if u < 0.5 => (h1 >= if lod1 { 0.9 } else { 0.55 }, [0.60, 0.62, 0.54]),
            _ if u < 0.75 => (h1 >= 0.15, [0.90, 0.88, 0.70]),
            _ => (true, [1.0; 3]),
        };
        verdict.insert(r, v);
    }
    if let Some(VertexAttributeValues::Float32x4(col)) = mesh.attribute_mut(Mesh::ATTRIBUTE_COLOR) {
        for (v, c) in col.iter_mut().enumerate() {
            let r = find(&mut parent, v as u32);
            let m = verdict[&r].1;
            for k in 0..3 {
                c[k] *= m[k];
            }
        }
    }
    let kept: Vec<u32> = idx
        .chunks_exact(3)
        .filter(|t| verdict[&find(&mut parent, t[0])].0)
        .flatten()
        .copied()
        .collect();
    mesh.insert_indices(Indices::U32(kept));
}

/// Kit prop for swamp passive class `class` (1 = cattail clump, 2 = small accents), source
/// variant `src`: (model, scale ×). `None` = leave the spot bare (no forest rock / toadstool).
pub fn swamp_prop(kit: &Kit, class: usize, src: usize, x: f32, z: f32) -> Option<(usize, f32)> {
    let (a, b) = super::rolls(x, z);
    let pick = |names: &[&str], s: f32| kit.pick_named(names, b).map(|m| (m, s));
    match (class, src) {
        (1, 0) => pick(&["sw_cattail_a"], 1.0),
        (1, _) => pick(&["sw_cattail_b", "sw_cattail_a"], 1.0),
        // Toadstool / mossy rock / trio / sunken log accents → a knot of knees (on the hammocks
        // only, round the cypresses), or a sedge tussock.
        (2, _) if a < 0.45 && swamp_hammock(x, z) >= HAMMOCK_FRINGE => pick(&["knees_b"], 0.7),
        (2, _) => pick(&["sw_sedge_a"], 1.3),
        _ => None,
    }
}

/// Kit ground cover for swamp cover class `class` (0 = moss patch, 1 = reed sprig, 2 = mushroom,
/// 3 = bog cotton / marsh flowers): sedge tussocks and reeds only — never forest grass, flowers
/// or toadstools. Round the bog pools' shores (and out on the open marsh) the reeds thicken into
/// cattail belts; under the hammocks the floor stays mostly bare muck with the odd sedge.
pub fn swamp_cover(kit: &Kit, class: usize, x: f32, z: f32) -> Option<(usize, f32)> {
    let (a, b) = super::rolls(x, z);
    let pick = |names: &[&str], s: f32| kit.pick_named(names, b).map(|m| (m, s));
    let shore = (-0.3..2.6).contains(&crate::worldmap::pool_sd_world(x, z));
    let open = swamp_hammock(x, z) < HAMMOCK_FRINGE;
    match class {
        _ if shore && a < 0.7 => pick(&["sw_cattail_a", "sw_cattail_b"], 0.85 + a * 0.4),
        _ if shore => pick(&["sw_sedge_a"], 1.1),
        _ if !open && a < 0.45 => None,
        _ if open && a < 0.22 => pick(&["sw_cattail_b", "sw_cattail_a"], 0.75),
        0 | 2 => pick(&["sw_sedge_a"], 0.85),
        1 => pick(&["sw_sedge_a"], 1.0),
        3 if a < 0.6 => pick(&["sw_sedge_a"], 0.9),
        3 => pick(&["sw_cattail_b"], 0.7),
        _ => None,
    }
}

/// Kit prop for a passive scatter class of the rocky or desert biome (see [`rocky_prop`]; desert:
/// 0 = dead bush, 2 = barrel cactus, 3 = prickly pear, 4 = bleached rocks + skull): (model, scale ×).
pub fn passive_prop(kit: &Kit, biome: crate::biome::Biome, class: usize, src: usize, x: f32, z: f32) -> Option<(usize, f32)> {
    if biome == crate::biome::Biome::Swamp {
        return swamp_prop(kit, class, src, x, z);
    }
    if biome != crate::biome::Biome::Desert {
        return rocky_prop(kit, class, src, x, z);
    }
    // Border ecotone: cacti only on real sand, dead scrub on the transition, nothing on turf.
    let c = crate::worldmap::biome_cover_world(x, z, crate::biome::Biome::Desert);
    if c < 0.3 {
        return None;
    }
    let class = if matches!(class, 2 | 3) && c < 0.82 { 0 } else { class };
    let name = match (class, src) {
        (0, 0) => "ds_deadbush_a",
        (0, _) => "ds_deadbush_b",
        (2, 0) => "ds_barrel_a",
        (2, _) => "ds_barrel_b",
        (3, 0) => "ds_pear_a",
        (3, _) => "ds_pear_b",
        (4, 0) => "ds_rock_a",
        (4, 1) => "ds_rock_b",
        (4, _) => "ds_bones",
        _ => return None,
    };
    kit.pick_named(&[name], 0.0).map(|m| (m, 1.0))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The hammock mask keeps the swamp mostly OPEN: tree-island cores cover roughly a quarter to
    /// two-fifths of any large patch, and the field is a pure function of position.
    #[test]
    fn hammocks_cover_a_minority_of_the_marsh() {
        let (mut core, mut fringe, mut n) = (0u32, 0u32, 0u32);
        for i in 0..240 {
            for j in 0..240 {
                let (x, z) = (-200.0 + i as f32 * 1.7, -60.0 + j as f32 * 1.7);
                let h = swamp_hammock(x, z);
                assert!((0.0..=1.0).contains(&h));
                assert_eq!(h, swamp_hammock(x, z));
                core += (h >= HAMMOCK_CORE) as u32;
                fringe += (HAMMOCK_FRINGE..HAMMOCK_CORE).contains(&h) as u32;
                n += 1;
            }
        }
        let (c, f) = (core as f32 / n as f32, fringe as f32 / n as f32);
        assert!((0.2..0.45).contains(&c), "hammock core fraction {c}");
        assert!((0.05..0.25).contains(&f), "hammock fringe fraction {f}");
    }
}
