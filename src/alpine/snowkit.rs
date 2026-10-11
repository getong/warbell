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
        // 0.62 → 0.48: at 0.62 the snowy crowns went white-on-white against the snowfield and
        // the forest read as bare poles from the meadow.
        "canopy" => 0.48,
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
/// at `(x, z)`: (lod0 model, frosted?). Conifers low on the green apron stay green; in the top
/// ~2.5u under the (per-spot) tree line the forest breaks up into stunted, wind-flagged spruces.
pub fn tree(kit: &Kit, src: usize, x: f32, z: f32) -> Option<(usize, bool)> {
    let (a, _) = crate::realforest::rolls(x, z);
    let (c, _) = flora_rolls(x, z);
    let y = crate::worldmap::ground_at_world(x, z).unwrap_or(0.0);
    let below_line = super::treeline_at(x, z) - y;
    let name = match src {
        // (Only on walkable ground: no stunted spruce hanging on a rock face.)
        _ if below_line < 2.5 && c < 0.75 - below_line * 0.2 && super::slope_at(x, z) < 0.6 => "spruce_flag_lod0",
        0 => "pine_a_lod0",
        1 => "pine_b_lod0",
        2 => "pine_c_lod0",
        // On the green apron a beech in leaf; up in the snow mostly another conifer, the odd bare
        // snag (a fifth of the scatter as dead trees made the snow forest look burnt out).
        _ if super::snow_cover(x, z) < FROST_AT => ["beech_a_lod0", "beech_b_lod0"][(a * 2.0) as usize % 2],
        _ if a < 0.3 => "dead_a_lod0",
        _ => ["pine_a_lod0", "pine_b_lod0", "pine_c_lod0"][(a * 7.0) as usize % 3],
    };
    // (Falls back to a kit pine without alpine_flora.glb.)
    let m = kit.pick_named(&[name], 0.0).or_else(|| kit.pick_named(&["pine_c_lod0"], 0.0))?;
    Some((m, super::snow_cover(x, z) >= FROST_AT))
}

/// A second, independent pair of position hashes for the alpine flora picks ([`crate::realforest::rolls`]'
/// first value is the tree-line jitter itself, so reusing it would tie the flora to that line).
fn flora_rolls(x: f32, z: f32) -> (f32, f32) {
    crate::realforest::rolls(x * 1.37 + 11.3, z * 0.73 - 7.9)
}

/// Above the tree line the massif is not bare: dwarf mountain pine mats (krummholz), creeping
/// juniper and, in the first couple of units past the line, the odd stunted flagged spruce —
/// thinning out toward the summits. `over` = ground height above the spot's tree line. Returns
/// (model, scale, yaw) or `None` for a bare spot. Drawn static (no chop / sway: knee-high scrub).
pub fn alpine_flora(kit: &Kit, x: f32, z: f32, over: f32) -> Option<(usize, f32, f32)> {
    let (c, d) = flora_rolls(x, z);
    let (_, b) = crate::realforest::rolls(x, z);
    // Dense at the line, sparse scrub high up.
    let keep = 0.85 - 0.5 * (over / 9.0).clamp(0.0, 1.0);
    if d > keep {
        return None;
    }
    let (name, s) = match c {
        _ if over < 2.5 && c < 0.12 => ("spruce_flag_lod0", 0.75 + 0.3 * b),
        _ if c < 0.70 => (if b < 0.5 { "krummholz_a" } else { "krummholz_b" }, 0.8 + 0.5 * b),
        _ => ("juniper_a", 0.9 + 0.5 * b),
    };
    kit.pick_named(&[name], 0.0).map(|m| (m, s, d * 97.0))
}
/// Does the kit take over snow scatter class `class` (props)? The snowman stays the hand-built one.
pub fn handles_prop(class: usize) -> bool {
    matches!(class, 1 | 2 | 3)
}

/// Kit prop for snow scatter class `class` (1 = drift / frozen shrub / stump+log, 2 = frost
/// boulders, 3 = the rare decor snowman — the same realistic models as the `snowman.rs`
/// ambushers, so a dormant ambusher still can't be told from decor), source variant `src`: (model, scale ×, frosted?). `None` = leave the spot bare.
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
        // Nobody builds a snowman on a steep bank (and one stood there hangs off the downhill
        // side / drowns in the uphill one): a frost boulder takes the spot instead.
        (3, _) if snowman_too_steep(x, z) => pick(&ROCKS, 0.8),
        (3, _) => kit.pick_named(&crate::snowman::KIT_MODELS, a).map(|m| (m, 1.0, false)),
        _ => None,
    }
}

/// More than ~14° of fall across a decor snowman's footprint.
fn snowman_too_steep(x: f32, z: f32) -> bool {
    let h = |dx: f32, dz: f32| crate::worldmap::ground_at_world(x + dx, z + dz);
    let ys = [h(0.5, 0.0), h(-0.5, 0.0), h(0.0, 0.5), h(0.0, -0.5)];
    let ys: Vec<f32> = ys.into_iter().flatten().collect();
    ys.len() < 4 || ys.iter().copied().fold(f32::MIN, f32::max) - ys.iter().copied().fold(f32::MAX, f32::min) > 0.25
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
    // Nothing grows on the steep / rock faces (the shader paints them bare rock past ~37°) —
    // bar the very odd tuft in a crevice.
    let slope = super::slope_at(x, z);
    if slope > 0.7 && a > 0.03 {
        return None;
    }
    // Past the tree line: tough alpine grass tussocks poke through where the snow is thin (sun-
    // facing ribs, wind-scoured crests), in clusters — never peppered over the deep snow; plus
    // the odd stone. Pale straw, unfrosted, so they catch the light instead of reading as dirt.
    let y = crate::worldmap::ground_at_world(x, z).unwrap_or(0.0);
    if y > super::treeline_at(x, z) - 1.0 {
        let cluster = crate::realforest::rolls((x / 5.0).floor() * 5.0 + 0.5, (z / 5.0).floor() * 5.0 + 0.5).1 < 0.3;
        return match class {
            0 if a < 0.5 && slope < 0.6 && cluster && super::thin_snow_spot(x, z) => {
                kit.pick_named(&["tussock_a", "tussock_b"], b).map(|m| (m, 1.0, false))
            }
            2 if a < 0.2 && slope < 0.6 => pick(&PEBBLES, 0.32),
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
