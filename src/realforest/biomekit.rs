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

/// Kit tree for swamp tree-class source variant `src` (0..2 the old mushroom-crowned mangroves,
/// 3..4 cypress-knee stumps): gnarled oaks and alder-like beeches with drowned snags among them,
/// and the scanned stump for the stumps.
pub fn swamp_tree(kit: &Kit, src: usize, x: f32, z: f32) -> Option<KitTree> {
    let (a, _) = super::rolls(x, z);
    let name = match src {
        _ if src >= 3 => return Some(KitTree::Static("stump_a", false)),
        _ if a < 0.3 => "dead_a_lod0",
        0 => ["oak_c_lod0", "oak_a_lod0"][(a * 7.0) as usize % 2],
        1 => "beech_b_lod0",
        _ => ["oak_b_lod0", "beech_a_lod0"][(a * 7.0) as usize % 2],
    };
    kit.pick_named(&[name], 0.0).map(KitTree::Tree)
}
