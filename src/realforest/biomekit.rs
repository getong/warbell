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
    /// wind sway the low-poly prop had (a cactus flexes a hair, a rock pillar must not).
    Static(&'static str, bool),
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
pub fn rocky_tree(kit: &Kit, src: usize, x: f32, z: f32) -> Option<KitTree> {
    let (a, _) = super::rolls(x, z);
    match src {
        0 => Some(KitTree::Static("rk_spire_a", false)),
        1 => Some(KitTree::Static("rk_spire_b", false)),
        // Timberline conifers: the wind-flagged spruce, the odd full pine (alpine_flora.glb optional).
        2 | 3 => {
            let name = if a < 0.6 { "spruce_flag_lod0" } else { ["pine_c_lod0", "pine_b_lod0"][(a * 9.0) as usize % 2] };
            kit.pick_named(&[name], 0.0).or_else(|| kit.pick_named(&["pine_c_lod0"], 0.0)).map(KitTree::Tree)
        }
        _ => kit.pick_named(&["dead_a_lod0"], 0.0).map(KitTree::Tree),
    }
}

/// Kit prop for rocky passive class `class` (0 = dry shrub, 1 = crags + cairn, 3 = scree), source
/// variant `src`: (model, scale ×). `None` = leave the spot bare.
pub fn rocky_prop(kit: &Kit, class: usize, src: usize, x: f32, z: f32) -> Option<(usize, f32)> {
    let (a, b) = super::rolls(x, z);
    let pick = |names: &[&str], s: f32| kit.pick_named(names, b).map(|m| (m, s));
    match (class, src) {
        // Dry highland scrub: creeping juniper / dwarf pine mats, a tussock; forest bush fallback.
        (0, _) if a < 0.45 => pick(&["juniper_a"], 0.55).or_else(|| pick(&["bush_a", "bush_b"], 0.7)),
        (0, _) if a < 0.75 => pick(&["krummholz_a", "krummholz_b"], 0.5).or_else(|| pick(&["bush_a"], 0.7)),
        (0, _) => pick(&["tussock_a", "tussock_b"], 1.1).or_else(|| pick(&["grass_c"], 1.0)),
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
/// litter / alpine flowers): (model, scale ×).
pub fn rocky_cover(kit: &Kit, class: usize, x: f32, z: f32) -> Option<(usize, f32)> {
    let (a, b) = super::rolls(x, z);
    let pick = |names: &[&str], s: f32| kit.pick_named(names, b).map(|m| (m, s));
    match class {
        0 => pick(&["rk_pebbles"], 1.0),
        1 if a < 0.55 => pick(&["tussock_a", "tussock_b"], 0.7).or_else(|| pick(&["grass_c", "grass_d"], 0.7)),
        1 => pick(&["grass_c", "grass_d"], 0.6),
        2 if a < 0.5 => pick(&["rk_pebbles"], 1.4),
        2 if a < 0.8 => pick(&["flower_yellow", "flower_daisy"], 0.6),
        2 => pick(&["stalks_a"], 0.7),
        _ => None,
    }
}

/// Kit saguaro for desert tree-class source variant `src` (0 = single arm, 1 = two arms, 2 = young).
pub fn saguaro(src: usize) -> KitTree {
    KitTree::Static(["ds_saguaro_b", "ds_saguaro_a", "ds_saguaro_c"][src.min(2)], true)
}

/// Does the kit take over the swamp? Needs `swamp_flora.glb` — the swamp draws ONLY its own
/// species (never the forest's oaks / beeches / snag / stump); without the file the low-poly
/// mangroves stay.
pub fn swamp(kit: &Kit) -> bool {
    kit.has("cypress_a_lod0")
}

/// Kit tree for swamp tree-class source variant `src` (0..2 the old mangroves, 3..4 the old
/// cypress-knee stumps): moss-hung bald cypresses on buttressed bases, drooping willows and
/// drowned, bleached snags; cypress knees (round a rotten stump or alone) for the stump slots.
pub fn swamp_tree(kit: &Kit, src: usize, x: f32, z: f32) -> Option<KitTree> {
    let (a, _) = super::rolls(x, z);
    let name = match src {
        3 => return Some(KitTree::Static("knees_a", false)),
        _ if src >= 4 => return Some(KitTree::Static("knees_b", false)),
        _ if a < 0.22 => ["snag_a_lod0", "snag_b_lod0"][(a * 31.0) as usize % 2],
        0 => "cypress_a_lod0",
        1 => ["cypress_b_lod0", "willow_a_lod0"][(a * 7.0) as usize % 2],
        _ => ["cypress_a_lod0", "cypress_b_lod0"][(a * 7.0) as usize % 2],
    };
    kit.pick_named(&[name], 0.0).map(KitTree::Tree)
}

/// Kit prop for swamp passive class `class` (1 = cattail clump, 2 = small accents), source
/// variant `src`: (model, scale ×). `None` = leave the spot bare (no forest rock / toadstool).
pub fn swamp_prop(kit: &Kit, class: usize, src: usize, x: f32, z: f32) -> Option<(usize, f32)> {
    let (a, b) = super::rolls(x, z);
    let pick = |names: &[&str], s: f32| kit.pick_named(names, b).map(|m| (m, s));
    match (class, src) {
        (1, 0) => pick(&["sw_cattail_a"], 1.0),
        (1, _) => pick(&["sw_cattail_b", "sw_cattail_a"], 1.0),
        // Toadstool / mossy rock / trio / sunken log accents → a knot of knees, or a sedge tuft.
        (2, _) if a < 0.45 => pick(&["knees_b"], 0.7),
        (2, _) => pick(&["sw_sedge_a"], 1.3),
        _ => None,
    }
}

/// Kit ground cover for swamp cover class `class` (0 = moss patch, 1 = reed sprig, 2 = mushroom,
/// 3 = bog cotton / marsh flowers): sedge tufts and the odd cattail; the bare spots are muck.
pub fn swamp_cover(kit: &Kit, class: usize, x: f32, z: f32) -> Option<(usize, f32)> {
    let (a, b) = super::rolls(x, z);
    let pick = |names: &[&str], s: f32| kit.pick_named(names, b).map(|m| (m, s));
    match class {
        0 if a < 0.5 => pick(&["sw_sedge_a"], 0.8),
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
