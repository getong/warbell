//! Snow-dusted forest kit for the snow biome: material twins (`alpine_snowkit.wgsl` settles snow
//! on every sky-facing surface of a kit model — needles, branch tops, rock caps, grass tips) and the
//! picks that map the snow biome's scatter classes onto kit models.
//!
//! Placement stays the snow config's own (same RNG, same masks, same spacing): only WHAT is drawn
//! changes, exactly like the realistic forest. Picks hash the position ([`crate::realforest::rolls`]).

use bevy::pbr::{ExtendedMaterial, MaterialExtension, MaterialPlugin};
use bevy::prelude::*;
use bevy::render::render_resource::AsBindGroup;
use bevy::shader::ShaderRef;

use crate::realforest::foliage::FoliageWind;
use crate::realforest::Kit;

pub type SnowKitMaterial = ExtendedMaterial<StandardMaterial, SnowKitExt>;

/// Same uniform layout as the foliage material (the wind vertex stage is shared); `tint.y` carries
/// the snow amount 0..1.
#[derive(Asset, AsBindGroup, Clone, TypePath, Debug)]
pub struct SnowKitExt {
    #[uniform(100)]
    pub wind: FoliageWind,
}

impl MaterialExtension for SnowKitExt {
    fn vertex_shader() -> ShaderRef {
        "shaders/foliage_wind.wgsl".into()
    }
    fn fragment_shader() -> ShaderRef {
        "shaders/alpine_snowkit.wgsl".into()
    }
}

pub(super) fn register(app: &mut App) {
    app.add_plugins(MaterialPlugin::<SnowKitMaterial>::default());
}

/// Snow amount for a kit material twin, `None` = no twin (structures, creatures, fruit).
pub fn snow_amount(material: &str) -> Option<f32> {
    Some(match material {
        // Needle cards: enough to load the sky-facing tops; more turned the sparse kit crowns
        // into white skeletons at range.
        "canopy" => 0.62,
        "undergrowth" => 0.45,
        "bark_pine" | "bark_oak" | "bark_beech" => 0.55,
        "prop_rock_a" | "prop_rock_b" | "prop_log" | "prop_stump" | "prop_branches" => 0.85,
        _ => return None,
    })
}

/// The snow twin of a kit material: same textures and wind, plus settled snow. Wind is kept off
/// (amplitude 0): the stock prepass draws these, so the main pass must not bend.
pub fn twin(base: &StandardMaterial, tint: f32, snow: f32) -> SnowKitMaterial {
    ExtendedMaterial {
        base: base.clone(),
        extension: SnowKitExt { wind: FoliageWind { wind: Vec4::ZERO, tint: Vec4::new(tint, snow, 0.0, 0.0) } },
    }
}

/// Snow cover at which props switch from the green meadow look to the frosted twins.
const FROST_AT: f32 = 0.42;

/// Kit tree for a snow-biome tree class source variant (0..2 snow-laden conifers, 3 bare birch)
/// at `(x, z)`: (lod0 model, frosted?). Conifers low on the green apron stay green.
pub fn tree(kit: &Kit, src: usize, x: f32, z: f32) -> Option<(usize, bool)> {
    let (a, _) = crate::realforest::rolls(x, z);
    let name = match src {
        0 => "pine_a_lod0",
        1 => "pine_b_lod0",
        2 => "pine_c_lod0",
        // A bare tree among the conifers; on the green apron a beech in leaf instead.
        _ if super::snow_cover(x, z) < FROST_AT => ["beech_a_lod0", "beech_b_lod0"][(a * 2.0) as usize % 2],
        _ => "dead_a_lod0",
    };
    kit.pick_named(&[name], 0.0).map(|m| (m, super::snow_cover(x, z) >= FROST_AT))
}

/// Does the kit take over snow scatter class `class` (props)? The snowman stays the hand-built one.
pub fn handles_prop(class: usize) -> bool {
    matches!(class, 1 | 2)
}

/// Kit prop for snow scatter class `class` (1 = drift / frozen shrub / stump+log, 2 = frost
/// boulders), source variant `src`: (model, scale ×, frosted?). `None` = leave the spot bare.
pub fn prop(kit: &Kit, class: usize, src: usize, x: f32, z: f32) -> Option<(usize, f32, bool)> {
    const ROCKS: [&str; 13] = [
        "rock_01_a", "rock_01_b", "rock_01_c", "rock_01_d", "rock_01_e", "rock_01_f", "rock_02_a",
        "rock_02_b", "rock_02_c", "rock_02_d", "rock_02_e", "rock_02_f", "rock_02_g",
    ];
    let (a, b) = crate::realforest::rolls(x, z);
    let snowy = super::snow_cover(x, z) >= FROST_AT;
    let pick = |names: &[&str], s: f32| kit.pick_named(names, b).map(|m| (m, s, snowy));
    match (class, src) {
        // Drift mound: the ground shader already piles drifts — a half-buried stone instead.
        (1, 0) => (a < 0.6).then(|| pick(&ROCKS, 0.45)).flatten(),
        (1, 1) => pick(&["bush_a", "bush_b"], 0.85),
        (1, _) if a < 0.5 => pick(&["stump_a"], 1.0),
        (1, _) => pick(&["log_a"], 0.8),
        (2, _) => pick(&ROCKS, 1.0),
        _ => None,
    }
}

/// Kit ground cover for snow cover class `class` (0 = snow tufts, 1 = ice glints, 2 = winter
/// litter) at `(x, z)`: (model, scale ×, frosted?). On the green apron the tufts become an alpine
/// meadow sward (grass, flowers, the odd stone); up in the snow, sparse frosted grass and twigs.
pub fn cover(kit: &Kit, class: usize, x: f32, z: f32) -> Option<(usize, f32, bool)> {
    const GRASS: [&str; 4] = ["grass_a", "grass_b", "grass_c", "grass_d"];
    const FLOWERS: [&str; 6] = ["flower_daisy", "flower_yellow", "flower_daisy", "flower_lupine_a", "flower_yellow", "flower_daisy"];
    const PEBBLES: [&str; 6] = ["rock_01_a", "rock_01_c", "rock_01_e", "rock_02_b", "rock_02_d", "rock_02_f"];
    let (a, b) = crate::realforest::rolls(x, z);
    let cover = super::snow_cover(x, z);
    let snowy = cover >= FROST_AT;
    let pick = |names: &[&str], s: f32| kit.pick_named(names, b).map(|m| (m, s, snowy));
    if !snowy {
        return match class {
            0 if a < 0.58 => pick(&GRASS, 0.9),
            0 if a < 0.86 => pick(&FLOWERS, 0.9),
            0 => pick(&["stalks_a"], 0.9),
            2 if a < 0.5 => pick(&PEBBLES, 0.3),
            2 => pick(&["fern_a", "fern_b", "fern_c"], 0.75),
            _ => None,
        };
    }
    // Deep snow buries most of it: thin out with cover.
    if a > 1.25 - cover {
        return None;
    }
    match class {
        0 => pick(&GRASS, 0.7),
        2 if a < 0.4 => pick(&["branches_a"], 0.55),
        2 => pick(&PEBBLES, 0.28),
        _ => None,
    }
}

/// Talus at a wall foot (replaces the low-poly drift mounds): a frosted boulder, scaled `s`.
pub fn talus(kit: &Kit, x: f32, z: f32) -> Option<(usize, f32, bool)> {
    const ROCKS: [&str; 7] = ["rock_01_b", "rock_01_d", "rock_01_f", "rock_02_a", "rock_02_c", "rock_02_e", "rock_02_g"];
    let (_, b) = crate::realforest::rolls(x, z);
    kit.pick_named(&ROCKS, b).map(|m| (m, 0.55, super::snow_cover(x, z) >= FROST_AT * 0.6))
}
