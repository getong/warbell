//! **Realistic forest** — the Blender-authored PBR kit (`tools/blender_forest/`, Poly Haven CC0
//! scans) swapped into the FOREST biome in place of the low-poly vertex-colour scatter.
//!
//! What it replaces, and how it stays cheap:
//! - **Trees** (`trees.glb`): procedurally grown oaks / beeches / pines / a dead snag with scanned
//!   bark and leaf-spray cards, two LODs each (~1.5k / ~0.35k tris). A tree stays ONE gameplay
//!   entity (`ChopTree` + wind `Sway` on the parent, exactly as before) with its LOD meshes as
//!   children, cross-faded by `VisibilityRange` at [`LOD_NEAR`] and hard-culled at 180u as before.
//! - **Undergrowth + props** (`undergrowth.glb`, `props.glb`): ferns, grass clumps, seed stalks,
//!   scanned stumps / logs / deadfall / mossy rocks. Merged per 16u chunk **per material**, so a
//!   whole chunk of ferns+grass is one draw (they share one atlas), same culling as the old cover.
//! - **Ground**: three scanned forest-floor layers (litter / moss / path) with height maps, splatted
//!   by the terrain shader inside the forest with height-blending and parallax occlusion mapping
//!   (`terrain.wgsl`, `FP_*`). The forest/road mask is baked once from the tile map.
//!
//! Placement, spacing, blockers, chop/regrow and determinism are untouched: `biome::scatter_region`
//! still makes every decision and only asks [`Kit`] *what to draw* at the very end.
//! On by default; `FOREST_PBR=0` restores the low-poly forest (A/B and fallback). If any kit file
//! fails to load the game logs a warning and keeps the low-poly forest.

pub mod foliage;
pub mod load;
pub mod reskin;

use std::collections::HashMap;
use std::sync::OnceLock;

use bevy::camera::visibility::VisibilityRange;
use bevy::prelude::*;

use crate::terrain::TerrainMaterial;

/// LOD0 → LOD1 cross-fade distance (world units, dithered over ±[`LOD_BAND`]).
pub const LOD_NEAR: f32 = 30.0;
const LOD_BAND: f32 = 2.0;
/// Far cull, same as the low-poly trees (fog has them by then).
const TREE_FAR: f32 = 180.0;
/// A kit prop only blocks when it's at least this tall (scaled, ~knee height on the 1.3u hero)…
const SOLID_MIN_H: f32 = 0.35;
/// …and this wide (half-extent).
const SOLID_MIN_R: f32 = 0.25;
/// Kit trees are modelled at real proportions (4-6u); the forest scatter's per-class scale ranges
/// were tuned for the ~1.5u low-poly trees. This brings a kit tree to ~2x the old tree's height
/// (3-6u canopy, 6.5-8u old-growth giants) so the forest keeps its gameplay readability.
const TREE_MODEL_SCALE: f32 = 0.62;

/// Ground-cover / prop chunk cut-offs (mirror `biome::spawn_chunks`), plus the short-range
/// floor clutter (fallen-leaf sheets, pebbles, twigs) that only matters near the camera.
const COVER_FAR: f32 = 58.0;
const PROPS_FAR: f32 = 75.0;
const CLUTTER_FAR: f32 = 34.0;
/// The green carpet is density-LOD'd like big open-world games do it: every tuft near the camera,
/// a thinned set of bigger tufts in a ring beyond, nothing past that — where the ground shader's
/// green moss layer under the carpet carries the read with zero geometry.
const LUSH_NEAR: f32 = 22.0;
const LUSH_FAR: f32 = 46.0;

/// Which merge bucket a kit prop lands in - decides its cull distance and landmark clearing.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum Tier {
    /// Bushes / rocks / stumps / logs from the main scatter.
    Props,
    /// Ferns / grass / stalks from the cover scatter (cleared around landmarks).
    Cover,
    /// Dense near-camera floor clutter ([`Kit::scatter_clutter`]).
    Clutter,
    /// Green carpet, full density, `0..LUSH_NEAR`.
    LushNear,
    /// Green carpet, thinned + enlarged, `LUSH_NEAR..LUSH_FAR`.
    LushFar,
}

/// Contact-darkening splats (x, z, radius) around trunks and solid props, baked into the forest
/// mask's B channel so the floor darkens where roots and stones meet it. Filled during the forest
/// scatter; [`SCATTER_DONE`] tells the terrain hook the list is complete.
static SPLATS: std::sync::Mutex<Vec<Vec3>> = std::sync::Mutex::new(Vec::new());
static SCATTER_DONE: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);

/// Called at the top of the forest scatter (also on an in-process world rebuild).
pub fn begin_scatter() {
    SPLATS.lock().expect("splats poisoned").clear();
    SCATTER_DONE.store(false, std::sync::atomic::Ordering::Release);
}

/// Register a contact-darkening splat (world XZ + radius in world units).
pub fn splat(x: f32, z: f32, r: f32) {
    SPLATS.lock().expect("splats poisoned").push(Vec3::new(x, z, r));
}
/// Alpha-test cutoff for leaf / blade cards (mips keep this coverage, see `load::mip_chain`).
const CARD_CUTOFF: f32 = 0.42;

/// Is the kit wanted? Read once.
pub fn enabled() -> bool {
    static ON: OnceLock<bool> = OnceLock::new();
    *ON.get_or_init(|| std::env::var("FOREST_PBR").map(|v| v != "0").unwrap_or(true))
}

static KIT: OnceLock<Kit> = OnceLock::new();

/// The loaded kit, or `None` when disabled / failed to load / before `PreStartup`.
/// A write-once global for the same reason as `phototrees::get` — the only consumer sits deep
/// inside the `Startup` world-build chain.
pub fn get() -> Option<&'static Kit> {
    KIT.get()
}

/// One mesh primitive of a kit model: CPU copy (for chunk merging) + uploaded handle.
pub struct Part {
    pub mesh: Mesh,
    pub handle: Handle<Mesh>,
    pub mat: usize,
}

pub struct Model {
    pub parts: Vec<Part>,
    /// XZ half-extents of the model about its origin (unscaled).
    pub half: Vec2,
    /// Radius of the trunk base incl. root flare (bark below 0.3u), 0 for non-trees.
    pub trunk: f32,
    /// Rocks / logs / stumps: you walk around them, not through.
    pub solid: bool,
    /// Top of the model above its base (unscaled).
    pub height: f32,
}

pub struct GroundTextures {
    pub albedo: Handle<Image>,
    pub normal: Handle<Image>,
    pub ormh: Handle<Image>,
}

/// A kit material: plain PBR, or a wind-swayed foliage material (leaf cards, undergrowth).
#[derive(Clone)]
pub enum KitMat {
    Std(Handle<StandardMaterial>),
    Foliage(Handle<foliage::FoliageMaterial>),
    /// Snow-dusted twin (`alpine::snowkit`) — the snow biome's trees, rocks and cover.
    Snow(Handle<crate::alpine::snowkit::SnowKitMaterial>),
}

impl KitMat {
    fn insert(&self, e: &mut EntityCommands) {
        match self {
            KitMat::Std(h) => e.insert(MeshMaterial3d(h.clone())),
            KitMat::Foliage(h) => e.insert(MeshMaterial3d(h.clone())),
            KitMat::Snow(h) => e.insert(MeshMaterial3d(h.clone())),
        };
    }
}

pub struct Kit {
    mats: Vec<KitMat>,
    /// Snow-dusted twin per material (`None` = no twin, the plain material is used).
    snow_mats: Vec<Option<KitMat>>,
    models: Vec<Model>,
    by_name: HashMap<String, usize>,
    pub ground: GroundTextures,
}

/// Material sets by the names Blender exported: (name, PBR set file stem, foliage card?).
const MATERIALS: [(&str, &str, bool); 23] = [
    ("bark_oak", "bark_oak", false),
    ("bark_beech", "bark_beech", false),
    ("bark_pine", "bark_pine", false),
    ("canopy", "canopy", true),
    ("undergrowth", "undergrowth", true),
    ("prop_stump", "prop_stump", false),
    ("prop_log", "prop_log", false),
    ("prop_branches", "prop_branches", false),
    ("prop_rock_a", "prop_rock_a", false),
    ("prop_rock_b", "prop_rock_b", false),
    // Apples: untextured, colour from the mesh's vertex colours (see `pbr_material`).
    ("fruit", "", false),
    // Structure sets (structures.glb: ork camp, mill).
    ("s_planks", "s_planks", false),
    ("s_stone", "s_stone", false),
    ("s_hide", "s_hide", false),
    ("s_thatch", "s_thatch", false),
    ("s_cloth", "s_cloth", false),
    ("s_iron", "s_iron", false),
    // Wayside furniture / story set-pieces (wayside.glb): weathered rock, trodden earth, and
    // nail-free hewn timber (the s_planks scan with its nail rows cut out).
    ("s_rock", "s_rock", false),
    ("s_earth", "s_earth", false),
    ("s_timber", "s_timber", false),
    // Settled snow on the cold-biome story scenes (stories_cold.glb): the Poly Haven snow_02 scan
    // (tools/blender_forest/snow_set.sh); vertex colour adds the blue in the shaded drift folds.
    ("s_snow", "s_snow", false),
    // Cast bronze (the Crown convoy's war bell): untextured true metal, colour from the vertex
    // colours (aged bronze mottled with verdigris), a soft sun highlight.
    ("bronze", "bronze", false),
    // Creature parts (creatures.glb, animals.glb, people.glb) — never drawn with this material
    // (recoloured CPU meshes on the creature material); the entry only lets the loader accept them.
    ("creature", "", false),
];

impl Kit {
    fn mat_by_name(&self, name: &str) -> Option<usize> {
        MATERIALS.iter().position(|m| m.0 == name)
    }

    fn model(&self, name: &str) -> Option<usize> {
        self.by_name.get(name).copied()
    }

    fn pick(&self, names: &[&str], roll: f32) -> Option<usize> {
        let i = ((roll * names.len() as f32) as usize).min(names.len() - 1);
        self.model(names[i])
    }

    /// [`Self::pick`] for other scatter tables (`alpine::snowkit`).
    pub fn pick_named(&self, names: &[&str], roll: f32) -> Option<usize> {
        self.pick(names, roll)
    }

    /// Material `i`, or its snow-dusted twin when `snow` (falls back to the plain one).
    fn mat(&self, i: usize, snow: bool) -> &KitMat {
        match self.snow_mats.get(i) {
            Some(Some(m)) if snow => m,
            _ => &self.mats[i],
        }
    }

    /// Which tree to draw for forest tree class `class` (0 = canopy mix, 1 = ancient giants) and
    /// its SOURCE variant (the variant index before `biome::upload_classes` tint expansion).
    /// The forest canopy class lists five living kinds × `trees::TREE_TINTS` then one dead tree
    /// (`biome_forest::config`), so the source variant encodes the old `TreeKind`.
    /// (Apple trees are NOT scatter picks: they are the harvestable forage orchard, see
    /// [`Self::apple_tree`] — a fruiting tree you can't pick from would read as a bug.)
    pub fn tree_for(&self, class: usize, src_variant: usize) -> Option<usize> {
        let tints = crate::trees::TREE_TINTS.len();
        let name = if class == 1 {
            ["oak_a", "oak_b", "oak_c"][src_variant % 3]
        } else if src_variant >= 5 * tints {
            "dead_a"
        } else {
            let t = src_variant % tints;
            match src_variant / tints {
                0 => ["oak_a", "oak_b", "oak_c"][t % 3],   // Broadleaf
                1 => ["beech_a", "beech_b"][t % 2],        // Birch
                2 => ["pine_a", "pine_b", "pine_c"][t % 3], // Pine
                3 => ["beech_b", "beech_a"][t % 2],        // Poplar → tall slim beech
                _ => ["oak_c", "oak_a", "oak_b"][t % 3],   // Autumn canopy → oak
            }
        };
        self.model(&format!("{name}_lod0"))
    }

    /// What to draw for a forest passive class (props: 2 bush / 3 rock / 4 stump; cover: 0 grass,
    /// 1 clover, 2 mushroom, 3 flowers, 4 fern, 5 litter). `None` = leave the spot bare — a real
    /// forest floor is litter with scattered plants, not a meadow carpet. Returns (model, scale ×).
    pub fn passive_for(&self, class: usize, cover: bool, roll: f32, roll2: f32) -> Option<(usize, f32)> {
        const GRASS: [&str; 4] = ["grass_a", "grass_b", "grass_c", "grass_d"];
        const FERN: [&str; 3] = ["fern_a", "fern_b", "fern_c"];
        const FLOWERS: [&str; 6] = ["flower_daisy", "flower_yellow", "flower_lupine_a", "flower_daisy", "flower_yellow", "flower_lupine_b"];
        const ROCKS: [&str; 13] = [
            "rock_01_a", "rock_01_b", "rock_01_c", "rock_01_d", "rock_01_e", "rock_01_f", "rock_02_a",
            "rock_02_b", "rock_02_c", "rock_02_d", "rock_02_e", "rock_02_f", "rock_02_g",
        ];
        let m = |names: &[&str], s: f32| self.pick(names, roll2).map(|i| (i, s));
        if cover {
            match class {
                0 => m(&GRASS, 1.0),
                1 if roll < 0.35 => m(&GRASS, 1.0),
                1 if roll < 0.55 => m(&FERN, 0.85),
                2 if roll < 0.25 => m(&["branches_a"], 0.5),
                3 if roll < 0.70 => m(&FLOWERS, 1.0),
                3 => m(&["stalks_a"], 1.0),
                4 => m(&FERN, 1.0),
                5 if roll < 0.5 => m(&["branches_a"], 0.7),
                5 => m(&ROCKS, 0.35),
                _ => None,
            }
        } else {
            match class {
                2 => m(&["bush_a", "bush_b"], 1.0),
                3 => m(&ROCKS, 0.9),
                4 if roll < 0.45 => m(&["stump_a"], 1.0),
                4 if roll < 0.8 => m(&["log_a"], 0.8),
                4 => m(&["branches_a"], 1.0),
                _ => None,
            }
        }
    }

    /// Hang tree `model` (its `_lod0`, plus the matching `_lod1`) under an already-spawned
    /// gameplay entity. The parent keeps `Transform` / `Sway` / `ChopTree`; the children only draw.
    pub fn attach_tree(&self, e: &mut EntityCommands, lod0: usize, cull: bool) {
        self.attach_tree_tagged(e, lod0, cull, ());
    }

    /// Collision radius for a kit tree `lod0` planted at scale `s` (the trunk you see, not the old
    /// low-poly tree's footprint).
    pub fn trunk_radius(&self, lod0: usize, s: f32) -> f32 {
        (self.models[lod0].trunk * TREE_MODEL_SCALE * s).clamp(0.08, 0.8)
    }

    /// Register the collision of a solid kit prop (rock / stump) — only when it is a real obstacle:
    /// at least [`SOLID_MIN_H`] tall (you step over anything lower — pebbles, twigs, lying logs)
    /// and [`SOLID_MIN_R`] across. The shape is circles, not a box: one for a roundish rock, a row
    /// along the long axis for an elongated one, so the hero's obstacle assist slides him round it
    /// (boxes stop him dead on a diagonal). Returns false for walk-through props.
    pub fn register_solid(&self, model: usize, x: f32, z: f32, scale: f32, rot: Quat) -> bool {
        let m = &self.models[model];
        let half = m.half * scale;
        if !m.solid || m.height * scale < SOLID_MIN_H || half.max_element() < SOLID_MIN_R {
            return false;
        }
        let (major, minor, along) = if half.x >= half.y {
            (half.x, half.y, rot * Vec3::X)
        } else {
            (half.y, half.x, rot * Vec3::Z)
        };
        let r = (minor * 0.8).clamp(0.12, 0.95);
        let reach = (major * 0.85 - r).max(0.0);
        let n = (reach / r).ceil() as i32;
        for k in -n..=n {
            let t = if n == 0 { 0.0 } else { k as f32 / n as f32 * reach };
            crate::blockers::add(x + along.x * t, z + along.z * t, r);
        }
        true
    }

    /// A recoloured CPU copy of creature part `name` (creatures.glb): vertex colour R holds a
    /// region code (region/16), G a baked cavity term. Each region gets `palette[region]` (rgb,
    /// darkened by the cavity) and its creature surface code in alpha.
    pub fn creature_part(&self, name: &str, palette: &[([f32; 4], crate::creature::Surf)]) -> Option<Mesh> {
        use bevy::mesh::VertexAttributeValues;
        let m = self.model(name)?;
        let mut mesh = self.models[m].parts.first()?.mesh.clone();
        if let Some(VertexAttributeValues::Float32x4(cols)) = mesh.attribute_mut(Mesh::ATTRIBUTE_COLOR) {
            for c in cols.iter_mut() {
                let region = ((c[0] * 16.0).floor() as usize).min(palette.len().saturating_sub(1));
                let (rgb, surf) = palette[region];
                let cav = c[1];
                *c = [rgb[0] * cav, rgb[1] * cav, rgb[2] * cav, crate::creature::surf_code(surf)];
            }
        }
        // Not needed on the creature path (triplanar), and the merger-free rigs don't care.
        mesh.remove_attribute(Mesh::ATTRIBUTE_TANGENT);
        Some(mesh)
    }

    /// [`Self::creature_part`] for the townsfolk pieces (people.glb): vertex colour B is a baked
    /// WEATHERING amount (ruddy cheeks and knuckles, grimy hems and knees, dusty boots) that pulls
    /// each region's colour toward `palette[region] * weather[region]`. UV0 / UV1 (the skin
    /// weights) are kept for `peasant_model` to decode.
    pub fn people_part(&self, name: &str, palette: &[([f32; 4], crate::creature::Surf)], weather: &[[f32; 3]]) -> Option<Mesh> {
        use bevy::mesh::VertexAttributeValues;
        let m = self.model(name)?;
        let mut mesh = self.models[m].parts.first()?.mesh.clone();
        if let Some(VertexAttributeValues::Float32x4(cols)) = mesh.attribute_mut(Mesh::ATTRIBUTE_COLOR) {
            for c in cols.iter_mut() {
                let region = ((c[0] * 16.0).floor() as usize).min(palette.len().saturating_sub(1));
                let (rgb, surf) = palette[region];
                let w = weather.get(region).copied().unwrap_or([1.0; 3]);
                let (cav, t) = (c[1], c[2].clamp(0.0, 1.0));
                let k = |i: usize| rgb[i] * (1.0 + (w[i] - 1.0) * t) * cav;
                *c = [k(0), k(1), k(2), crate::creature::surf_code(surf)];
            }
        }
        mesh.remove_attribute(Mesh::ATTRIBUTE_TANGENT);
        Some(mesh)
    }

    /// A CPU copy of kit part `name` with its baked vertex data untouched (region / cavity / tone /
    /// gloss in the colour, skin weights in UV0 / UV1) for a caller that decodes it itself (the
    /// skinned orks, `orks::kit_ork_body`).
    pub fn raw_part(&self, name: &str) -> Option<Mesh> {
        let m = self.model(name)?;
        let mut mesh = self.models[m].parts.first()?.mesh.clone();
        mesh.remove_attribute(Mesh::ATTRIBUTE_TANGENT);
        Some(mesh)
    }

    /// A recoloured CPU copy of animal part `name` (animals.glb, `tools/blender_forest/animals.py`).
    /// Vertex colour R = region (region/16), G = baked cavity / AO, B = coat TONE, A = coat TINT.
    /// Region 0 is fur: its colour walks the `coat` ramp by tone (0 = `coat[0]` dark saddle /
    /// points, 0.5 = `coat[1]` base coat, 1 = `coat[2]` pale belly) and then blends toward
    /// `coat[3]` (the warm tint) by the tint amount. Other regions take `palette[region]`. The
    /// mesh keeps its UV0 — the fur-flow coordinates the creature shader lays the strands along.
    pub fn coat_part(&self, name: &str, coat: &[[f32; 4]; 4], palette: &[([f32; 4], crate::creature::Surf)]) -> Option<Mesh> {
        use bevy::mesh::VertexAttributeValues;
        let m = self.model(name)?;
        let mut mesh = self.models[m].parts.first()?.mesh.clone();
        let mix = |a: [f32; 4], b: [f32; 4], t: f32| [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
        if let Some(VertexAttributeValues::Float32x4(cols)) = mesh.attribute_mut(Mesh::ATTRIBUTE_COLOR) {
            for c in cols.iter_mut() {
                let region = ((c[0] * 16.0).floor() as usize).min(palette.len().saturating_sub(1));
                let (flat, surf) = palette[region];
                let (tone, tint, cav) = (c[2].clamp(0.0, 1.0), c[3].clamp(0.0, 1.0), c[1]);
                let rgb = if region == 0 {
                    let ramp = if tone < 0.5 { mix(coat[0], coat[1], tone * 2.0) } else { mix(coat[1], coat[2], tone * 2.0 - 1.0) };
                    mix([ramp[0], ramp[1], ramp[2], 1.0], coat[3], tint)
                } else {
                    [flat[0], flat[1], flat[2]]
                };
                *c = [rgb[0] * cav, rgb[1] * cav, rgb[2] * cav, crate::creature::surf_code(surf)];
            }
        }
        mesh.remove_attribute(Mesh::ATTRIBUTE_TANGENT);
        Some(mesh)
    }

    /// Is there a kit model called `name`?
    pub fn has(&self, name: &str) -> bool {
        self.by_name.contains_key(name)
    }

    /// (XZ half-extents, height) of kit model `name`, unscaled.
    pub fn extents(&self, name: &str) -> Option<(Vec2, f32)> {
        self.model(name).map(|m| (self.models[m].half, self.models[m].height))
    }

    /// Hang the static kit model `name` (all its material parts) under `e` as children.
    /// Returns false when the kit has no such model.
    pub fn attach_static(&self, e: &mut EntityCommands, name: &str, tf: Transform) -> bool {
        self.attach_static_with(e, name, tf, ())
    }

    /// [`Self::attach_static`], also inserting `extra` on every part (e.g. a `VisibilityRange`,
    /// which Bevy evaluates per mesh entity, not per hierarchy).
    pub fn attach_static_with<B: Bundle + Clone>(&self, e: &mut EntityCommands, name: &str, tf: Transform, extra: B) -> bool {
        let Some(m) = self.model(name) else { return false };
        e.insert(Visibility::default());
        e.with_children(|p| {
            for part in &self.models[m].parts {
                let mut c = p.spawn((Mesh3d(part.handle.clone()), tf, extra.clone()));
                self.mats[part.mat].insert(&mut c);
            }
        });
        true
    }

    /// Spawn the static kit model `name` as a new root entity at `tf`, `extra` on every part.
    pub fn spawn_static_with<B: Bundle + Clone>(&self, commands: &mut Commands, name: &str, tf: Transform, extra: B) -> Option<Entity> {
        self.model(name)?;
        let mut e = commands.spawn((tf, Visibility::default()));
        self.attach_static_with(&mut e, name, Transform::IDENTITY, extra);
        Some(e.id())
    }

    /// Spawn the static kit model `name` as a new root entity at `tf`.
    pub fn spawn_static(&self, commands: &mut Commands, name: &str, tf: Transform) -> Option<Entity> {
        self.model(name)?;
        let mut e = commands.spawn((tf, Visibility::default()));
        self.attach_static(&mut e, name, Transform::IDENTITY);
        Some(e.id())
    }

    /// The wild apple tree used by the forage orchard (`verbs::populate_apple_orchard`).
    pub fn apple_tree(&self, roll: f32) -> Option<usize> {
        self.model(if roll < 0.5 { "apple_a_lod0" } else { "apple_b_lod0" })
    }

    /// [`Self::attach_tree`], also inserting `fruit_tag` on every fruit part (both LODs) so
    /// gameplay can hide / show the apples (harvest + regrow).
    pub fn attach_tree_tagged<B: Bundle + Clone>(&self, e: &mut EntityCommands, lod0: usize, cull: bool, fruit_tag: B) {
        self.attach_tree_with(e, lod0, cull, fruit_tag, false);
    }

    /// [`Self::attach_tree`] with the snow-dusted material twins when `snow` (snow biome).
    pub fn attach_tree_snowy(&self, e: &mut EntityCommands, lod0: usize, cull: bool, snow: bool) {
        self.attach_tree_with(e, lod0, cull, (), snow);
    }

    fn attach_tree_with<B: Bundle + Clone>(&self, e: &mut EntityCommands, lod0: usize, cull: bool, fruit_tag: B, snow: bool) {
        let fruit = self.mat_by_name("fruit");
        let lod1 = self.models.get(lod0 + 1);
        e.insert(Visibility::default());
        let near = VisibilityRange {
            start_margin: 0.0..0.0,
            end_margin: (LOD_NEAR - LOD_BAND)..(LOD_NEAR + LOD_BAND),
            use_aabb: false,
        };
        let far_end = if cull { TREE_FAR } else { 1.0e6 };
        let far = VisibilityRange {
            start_margin: (LOD_NEAR - LOD_BAND)..(LOD_NEAR + LOD_BAND),
            end_margin: far_end..far_end,
            use_aabb: false,
        };
        let tf = Transform::from_scale(Vec3::splat(TREE_MODEL_SCALE));
        e.with_children(|p| {
            let lods = std::iter::once((&self.models[lod0], near.clone())).chain(lod1.map(|l| (l, far.clone())));
            for (model, range) in lods {
                for part in &model.parts {
                    let mut c = p.spawn((Mesh3d(part.handle.clone()), tf, range.clone()));
                    self.mat(part.mat, snow).insert(&mut c);
                    if Some(part.mat) == fruit {
                        c.insert((fruit_tag.clone(), Visibility::Visible));
                    }
                }
            }
        });
    }
}

/// Two decorrelated uniform rolls hashed from a world position — the kit's variety picks, kept
/// OFF the scatter's sequential RNG so turning the kit on/off can't shift any later placement.
pub fn rolls(x: f32, z: f32) -> (f32, f32) {
    let h = |s: u32| {
        let mut v = (x * 64.0).round() as i32 as u32;
        v = v.wrapping_mul(0x9E37_79B1) ^ ((z * 64.0).round() as i32 as u32).wrapping_mul(0x85EB_CA77) ^ s;
        v ^= v >> 15;
        v = v.wrapping_mul(0x2C1B_3C6D);
        v ^= v >> 12;
        v = v.wrapping_mul(0x297A_2D39);
        v ^= v >> 15;
        (v >> 8) as f32 / (1u32 << 24) as f32
    };
    (h(0x1234_5678), h(0x0BAD_F00D))
}

impl Kit {
    /// Dense near-camera floor clutter over `[lo, hi]²` - the layer that stops a game forest floor
    /// reading as a flat painted plane: overlapping fallen-leaf sheets, pebbles and twigs lying ON
    /// the ground (real geometry with contact shadow), plus grass tufts colonising trail EDGES (the
    /// main cover scatter keeps a clear apron around roads). Three hashed rolls per tile, all off the
    /// scatter's RNG so the world layout is untouched. Cull distance [`CLUTTER_FAR`].
    pub fn scatter_clutter(
        &self,
        chunks: &mut Chunks,
        lo: f32,
        hi: f32,
        mask: &dyn Fn(f32, f32) -> bool,
        height_fn: &dyn Fn(f32, f32) -> f32,
    ) {
        const LITTER: [&str; 4] = ["litter_a", "litter_b", "litter_c", "litter_d"];
        const GRASS: [&str; 4] = ["grass_a", "grass_b", "grass_c", "grass_d"];
        const PEBBLES: [&str; 6] = ["rock_01_a", "rock_01_c", "rock_01_e", "rock_02_b", "rock_02_d", "rock_02_f"];
        const FERN: [&str; 3] = ["fern_a", "fern_b", "fern_c"];
        const FLOWERS: [&str; 6] = ["flower_daisy", "flower_yellow", "flower_lupine_a", "flower_daisy", "flower_yellow", "flower_lupine_b"];
        const LUSH: [&str; 3] = ["lush_a", "lush_b", "lush_c"];
        let mut gx = lo;
        while gx < hi {
            let mut gz = lo;
            while gz < hi {
                for k in 0..3u32 {
                    let (a, b) = rolls(gx + k as f32 * 0.37, gz - k as f32 * 0.61);
                    let (c, d) = rolls(gx - k as f32 * 0.53, gz + k as f32 * 0.29);
                    let (x, z) = (gx + a, gz + b);
                    if !mask(x, z) || crate::ruins::near_landmark_visual_footprint(x, z) {
                        continue;
                    }
                    let road = crate::roads::road_strength(x, z);
                    let pick = |names: &[&str], s: f32| self.pick(names, d).map(|m| (m, s));
                    let choice = if road > 0.9 {
                        // The grass strip a cart track keeps between its two ruts.
                        if c < 0.14 { pick(&GRASS, 0.5 + d * 0.3) } else { None }
                    } else if road > 0.55 {
                        // Leaves blown onto the track.
                        if c < 0.22 { pick(&LITTER, 0.7 + d * 0.4) } else { None }
                    } else if road > 0.12 && c < 0.025 {
                        // The odd fallen trunk / mossy boulder / bush right at the verge.
                        if d < 0.4 {
                            pick(&["log_a"], 0.75 + d * 0.5)
                        } else if d < 0.75 {
                            pick(&PEBBLES, 0.4 + d * 0.3)
                        } else {
                            pick(&["bush_a", "bush_b"], 1.0 + d * 0.4)
                        }
                    } else if road > 0.12 {
                        // Trail verge: the lush band a forest path grows along — grass, ferns, flowers.
                        if c < 0.42 {
                            pick(&GRASS, 0.8 + d * 0.5)
                        } else if c < 0.68 {
                            pick(&FLOWERS, 0.85 + d * 0.4)
                        } else if c < 0.90 {
                            pick(&FERN, 0.9 + d * 0.5)
                        } else {
                            pick(&["stalks_a"], 0.9)
                        }
                    } else if c < 0.55 {
                        pick(&LITTER, 0.8 + d * 0.5)
                    } else if c < 0.67 && !crate::blockers::any_within(x, z, 0.35) {
                        pick(&PEBBLES, 0.12 + d * 0.16)
                    } else if c < 0.80 {
                        pick(&["branches_a"], 0.35 + d * 0.25)
                    } else if c < 0.86 {
                        pick(&GRASS, 0.6 + d * 0.3)
                    } else if c < 0.93 {
                        pick(&FERN, 0.8 + d * 0.5)
                    } else {
                        None
                    };
                    if let Some((m, s)) = choice {
                        let rot = Quat::from_rotation_y(c * 97.0 % std::f32::consts::TAU);
                        if chunks.push(self, m, Vec3::new(x, height_fn(x, z), z), rot, s, Tier::Clutter) {
                            self.register_solid(m, x, z, s, rot);
                        }
                    }
                }
                // Undergrowth: up to 3 plants per tile off the trails, in DRIFTS — a broad noise field
                // opens real clearings (a forest floor is mostly litter with plant patches, not a
                // lawn), and the ground fertility thins it further on the bare/worn patches. Every
                // 2nd plant also goes into the far ring at 1.35x scale.
                let fert = crate::biome::ground_patch(gx + 0.5, gz + 0.5).fertility;
                // Glades (open, sunlit) grow a grass + flower sward; groves keep the drifts.
                let glade = 1.0 - crate::biome::fg_smoothstep(0.08, 0.38, crate::biome::forest_grove(gx + 0.5, gz + 0.5));
                let drift = crate::biome::forest_drift(gx + 0.5, gz + 0.5).max(glade * 0.85);
                for k in 0..3u32 {
                    let (a, b) = rolls(gx + 0.13 + k as f32 * 0.71, gz + 0.29 - k as f32 * 0.43);
                    let (c, d) = rolls(gx - 0.31 - k as f32 * 0.17, gz + 0.47 + k as f32 * 0.59);
                    if c > fert * drift {
                        continue;
                    }
                    let (x, z) = (gx + a, gz + b);
                    if !mask(x, z)
                        || crate::roads::road_strength(x, z) > 0.3
                        || crate::blockers::any_within(x, z, 0.3)
                        || crate::ruins::near_landmark_visual_footprint(x, z)
                    {
                        continue;
                    }
                    // Variety over volume: grass, ferns, short dry stalks, a low shrub, a fallen-leaf
                    // sheet, the occasional flower — each patch reads as a mixed understorey.
                    let (pick, s) = if glade > 0.5 {
                        if d < 0.62 {
                            (self.pick(&LUSH, c), 0.6 + c * 0.5)
                        } else if d < 0.82 {
                            // Meadow flowers: mostly daisies + yellow, the odd lupine spike.
                            const GLADE_FLOWERS: [&str; 6] = ["flower_daisy", "flower_yellow", "flower_daisy", "flower_yellow", "flower_daisy", "flower_lupine_a"];
                            (self.pick(&GLADE_FLOWERS, c), 0.8 + c * 0.3)
                        } else if d < 0.92 {
                            (self.pick(&["stalks_a"], c), 0.9)
                        } else {
                            (self.pick(&FERN, c), 0.7 + c * 0.4)
                        }
                    } else if d < 0.42 {
                        (self.pick(&LUSH, c), 0.65 + c * 0.5)
                    } else if d < 0.68 {
                        (self.pick(&FERN, c), 0.8 + c * 0.6)
                    } else if d < 0.78 {
                        (self.pick(&["stalks_a"], c), 0.9)
                    } else if d < 0.85 {
                        (self.pick(&["bush_a", "bush_b"], c), 0.45 + c * 0.35)
                    } else if d < 0.94 {
                        (self.pick(&LITTER, c), 0.9 + c * 0.4)
                    } else {
                        (self.pick(&FLOWERS, c), 0.85)
                    };
                    let Some(m) = pick else { continue };
                    let pos = Vec3::new(x, height_fn(x, z), z);
                    let rot = Quat::from_rotation_y(d * 131.0 % std::f32::consts::TAU);
                    chunks.push(self, m, pos, rot, s, Tier::LushNear);
                    if k % 2 == 0 && d < 0.85 {
                        chunks.push(self, m, pos, rot, s * 1.35, Tier::LushFar);
                    }
                }
                gz += 1.0;
            }
            gx += 1.0;
        }
    }
}

impl Kit {
    /// Shoreline dressing on the eroded river / lake / pool banks ([`crate::worldmap::shore_sample`]):
    /// small pebbles strewn along the waterline (half drowned — the slope runs on under the water),
    /// the odd bigger stone down the damp face, and grass / fern tufts hanging over the lip. Five
    /// hashed probes per tile, all off the scatter's RNG; off the banks a probe is one mask lookup.
    /// Lands in the near-clutter merge buckets (same cull distance, no extra draw groups).
    pub fn scatter_shore(
        &self,
        chunks: &mut Chunks,
        lo: f32,
        hi: f32,
        mask: &dyn Fn(f32, f32) -> bool,
    ) {
        const PEBBLES: [&str; 6] = ["rock_01_a", "rock_01_c", "rock_01_e", "rock_02_b", "rock_02_d", "rock_02_f"];
        const GRASS: [&str; 4] = ["grass_a", "grass_b", "grass_c", "grass_d"];
        const FERN: [&str; 3] = ["fern_a", "fern_b", "fern_c"];
        let mut gx = lo;
        while gx < hi {
            let mut gz = lo;
            while gz < hi {
                for k in 0..5u32 {
                    let (a, b) = rolls(gx + 0.71 + k as f32 * 0.23, gz - 0.37 + k as f32 * 0.57);
                    let (c, d) = rolls(gx - 0.19 - k as f32 * 0.41, gz + 0.83 + k as f32 * 0.13);
                    let (x, z) = (gx + a, gz + b);
                    let Some((sd, bank, ground)) = crate::worldmap::shore_sample(x, z) else { continue };
                    if sd < 0.04 || crate::bridges::near_bridge(x, z, 1.0) || crate::ruins::near_landmark_visual_footprint(x, z) {
                        continue;
                    }
                    // The lower slope runs out over the water TILE beside the bank, which belongs to
                    // no biome: judge such a point by its first land neighbour (fixed order, so
                    // exactly one biome pass claims it).
                    let land = |px: f32, pz: f32| crate::worldmap::is_land_tile_world(px, pz);
                    let owner = if land(x, z) {
                        Some((x, z))
                    } else {
                        [(0.9f32, 0.0f32), (-0.9, 0.0), (0.0, 0.9), (0.0, -0.9)]
                            .into_iter()
                            .map(|(ox, oz)| (x + ox, z + oz))
                            .find(|&(px, pz)| land(px, pz))
                    };
                    let Some((ox, oz)) = owner else { continue };
                    if !mask(ox, oz) {
                        continue;
                    }
                    let pick = |names: &[&str], s: f32| self.pick(names, d).map(|m| (m, s));
                    let (choice, sink) = if sd < 0.6 {
                        // Waterline gravel: a loose string of small stones, thinning out of the water.
                        (if c < 0.62 - sd * 0.6 { pick(&PEBBLES, 0.07 + d * 0.11) } else { None }, 0.35)
                    } else if bank > 0.3 && sd < 2.4 {
                        // The odd stone washed out of the face.
                        (if c < 0.07 { pick(&PEBBLES, 0.15 + d * 0.18) } else { None }, 0.3)
                    } else if bank > 0.01 {
                        // The grass / fern fringe overhanging the lip.
                        (
                            if c < 0.30 {
                                pick(&GRASS, 0.55 + d * 0.45)
                            } else if c < 0.40 {
                                pick(&FERN, 0.65 + d * 0.4)
                            } else {
                                None
                            },
                            0.0,
                        )
                    } else {
                        (None, 0.0)
                    };
                    let Some((m, s)) = choice else { continue };
                    let rot = Quat::from_rotation_y(c * 113.0 % std::f32::consts::TAU);
                    // Stones sit IN the ground (a fraction of their own height), not perched on it.
                    // `ground` is the bank surface itself — also where the slope runs out over the
                    // water tile, which the general ground sampler has no footing for.
                    let y = ground - self.models[m].height * s * sink;
                    chunks.push(self, m, Vec3::new(x, y, z), rot, s, Tier::Clutter);
                }
                gz += 1.0;
            }
            gx += 1.0;
        }
    }
}

// ── Chunk merging for passive props / ground cover ───────────────────────────────────────────

/// Queued kit props, grouped by (16u chunk, cover?, material) so each group merges to one mesh.
#[derive(Default)]
pub struct Chunks {
    /// (chunk, tier, density slice, material, snow twin?) -> queued parts.
    groups: HashMap<((i32, i32), Tier, u8, usize, bool), Vec<(usize, usize, Transform)>>,
}

/// Undergrowth density slice a merged chunk belongs to. Every plant / clutter piece is hashed into
/// one of three slices (45% / 27% / 28%) and each slice merges into its own mesh, so the Settings
/// "Undergrowth" level just shows or hides whole slices at runtime — no rebuild, and a hidden
/// slice costs nothing. Props (rocks, logs, stumps, bushes) are always slice 0.
#[derive(Component, Clone, Copy)]
pub struct DensitySlice(pub u8);

fn density_slice(tier: Tier, world: Vec3) -> u8 {
    if tier == Tier::Props {
        return 0;
    }
    let (e, _) = rolls(world.x * 1.7 + 0.13, world.z * 1.3 - 0.71);
    if e < 0.45 {
        0
    } else if e < 0.72 {
        1
    } else {
        2
    }
}

/// Show the slices the Settings undergrowth level asks for (Low 1 / Medium 2 / High 3 slices).
fn apply_undergrowth(
    settings: Res<crate::quality::GraphicsSettings>,
    mut q: Query<(Ref<DensitySlice>, &mut Visibility)>,
) {
    let all = settings.is_changed();
    let keep = settings.undergrowth.slices();
    for (slice, mut vis) in &mut q {
        if !all && !slice.is_added() {
            continue;
        }
        let want = if slice.0 < keep { Visibility::Inherited } else { Visibility::Hidden };
        if *vis != want {
            *vis = want;
        }
    }
}

fn chunk_key(x: f32, z: f32) -> (i32, i32) {
    let c = crate::biome::COVER_CHUNK;
    ((x / c).floor() as i32, (z / c).floor() as i32)
}

fn chunk_center(k: (i32, i32)) -> Vec3 {
    let c = crate::biome::COVER_CHUNK;
    Vec3::new(k.0 as f32 * c + c * 0.5, 0.0, k.1 as f32 * c + c * 0.5)
}

/// Kit scatter must stay out of the gameplay set-pieces placed later in the world build: ork
/// camps (tents, cage, fire — plus a margin for guy ropes), roadside story clearings, the planned
/// wayside furniture (signposts / cairns / fences / shrines) and forest vignette, and the
/// landmarks. Merged chunks can't be thinned afterwards the way single trees are, so it is
/// decided here, at placement.
pub fn keep_clear(x: f32, z: f32, r: f32) -> bool {
    crate::camps::plan().iter().any(|c| Vec2::new(x - c.centre.x, z - c.centre.y).length() < 6.0 + r)
        || crate::poi::overlaps_planned_clearing(x, z, r)
        || crate::wayside::overlaps_planned(x, z, r)
        || crate::vignettes::overlaps_planned(x, z, r)
        || crate::ruins::near_landmark_visual_footprint(x, z)
}

impl Chunks {
    /// Queue a kit prop for its chunk merge. Returns false (nothing queued) where the spot must
    /// stay clear of a set-piece ([`keep_clear`]).
    pub fn push(&mut self, kit: &Kit, model: usize, world: Vec3, rot: Quat, scale: f32, tier: Tier) -> bool {
        self.push_snowy(kit, model, world, rot, scale, tier, false)
    }

    /// [`Self::push`], drawn with the snow-dusted material twins when `snow`.
    #[allow(clippy::too_many_arguments)]
    pub fn push_snowy(&mut self, kit: &Kit, model: usize, world: Vec3, rot: Quat, scale: f32, tier: Tier, snow: bool) -> bool {
        if keep_clear(world.x, world.z, kit.models[model].half.max_element() * scale) {
            return false;
        }
        let key = chunk_key(world.x, world.z);
        let t = Transform { translation: world - chunk_center(key), rotation: rot, scale: Vec3::splat(scale) };
        let slice = density_slice(tier, world);
        for (pi, part) in kit.models[model].parts.iter().enumerate() {
            self.groups.entry((key, tier, slice, part.mat, snow)).or_default().push((model, pi, t));
        }
        if tier == Tier::Props {
            splat(world.x, world.z, 0.55 * scale);
        }
        true
    }

    pub fn spawn(self, kit: &Kit, commands: &mut Commands, meshes: &mut Assets<Mesh>, cull: bool) {
        SCATTER_DONE.store(true, std::sync::atomic::Ordering::Release);
        for ((key, tier, slice, mat, snow), items) in self.groups {
            let mut it = items.into_iter();
            let Some((m0, p0, t0)) = it.next() else { continue };
            let mut base = kit.models[m0].parts[p0].mesh.clone().transformed_by(t0);
            for (m, p, t) in it {
                let part = kit.models[m].parts[p].mesh.clone().transformed_by(t);
                if base.merge(&part).is_err() {
                    warn!("realforest: chunk merge failed (attribute mismatch) — part skipped");
                }
            }
            let (near, far) = match tier {
                Tier::Props => (0.0, PROPS_FAR),
                Tier::Cover => (0.0, COVER_FAR),
                Tier::Clutter => (0.0, CLUTTER_FAR),
                Tier::LushNear => (0.0, LUSH_NEAR),
                Tier::LushFar => (LUSH_NEAR, LUSH_FAR),
            };
            let mut e = commands.spawn((
                Mesh3d(meshes.add(base)),
                Transform::from_translation(chunk_center(key)),
                bevy::light::NotShadowCaster,
                crate::biome::BiomeEntity,
                DensitySlice(slice),
                Visibility::default(),
            ));
            kit.mat(mat, snow).insert(&mut e);
            if tier != Tier::Props {
                e.insert(crate::biome::GroundCoverChunk);
            }
            if cull || near > 0.0 {
                let far = if cull { far } else { 1.0e6 };
                e.insert(VisibilityRange { start_margin: near..near, end_margin: far..far, use_aabb: true });
            }
        }
    }
}

// ── Loading ────────────────────────────────────────────────────────────────────────────────────

pub struct RealForestPlugin;

impl Plugin for RealForestPlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<ForestLook>();
        app.add_plugins((reskin::ReskinPlugin, foliage::FoliagePlugin));
        if !enabled() {
            return;
        }
        // Before the world build (Startup) reads the kit inside `biome::scatter_region`.
        app.add_systems(PreStartup, build_kit).add_systems(Update, (patch_terrain, drive_forest_look, apply_undergrowth));
    }
}

/// 0..1 "the camera is in the realistic forest" weight, eased. The post stack reads it to give the
/// forest its own look — clearer air (`atmospherics`), richer colour (`grade`), stronger sun shafts
/// (`godrays`) — without touching the tuned look of every other biome.
#[derive(Resource, Default)]
pub struct ForestLook(pub f32);

fn drive_forest_look(
    time: Res<Time>,
    cams: Query<&GlobalTransform, With<Camera3d>>,
    mut look: ResMut<ForestLook>,
) {
    let Some(cam) = cams.iter().next() else { return };
    let p = cam.translation();
    let target = if get().is_some()
        && crate::worldmap::tile_biome_world(p.x, p.z) == Some(crate::biome::Biome::Forest)
    {
        1.0
    } else {
        0.0
    };
    let k = (time.delta_secs() * 1.2).min(1.0);
    let v = look.0 + (target - look.0) * k;
    if (v - look.0).abs() > 1e-4 {
        look.0 = v;
    }
}

fn pbr_material(images: &mut Assets<Image>, set: &str, card: bool) -> Result<StandardMaterial, String> {
    if set == "bronze" {
        return Ok(StandardMaterial { metallic: 1.0, perceptual_roughness: 0.5, reflectance: 0.5, ..default() });
    }
    if set.is_empty() {
        // Waxy fruit skin: base colour comes from the vertex colours.
        return Ok(StandardMaterial { perceptual_roughness: 0.42, reflectance: 0.45, ..default() });
    }
    let albedo = images.add(load::texture(&format!("forest_pbr/{set}_albedo.png"), true, card.then_some(CARD_CUTOFF))?);
    let normal = images.add(load::texture(&format!("forest_pbr/{set}_normal.png"), false, None)?);
    if card {
        return Ok(StandardMaterial {
            base_color_texture: Some(albedo),
            normal_map_texture: Some(normal),
            alpha_mode: AlphaMode::Mask(CARD_CUTOFF),
            // Draw both faces but keep ONE normal for both: the cards carry crown-outward bent
            // normals, and `double_sided` would flip them on the back face (dark inner leaves).
            cull_mode: None,
            double_sided: false,
            perceptual_roughness: 0.62,
            reflectance: 0.32,
            // No `diffuse_transmission`: on a crown of overlapping alpha-tested cards (no early-z,
            // every layer shaded) the extra back-lobe light pass cost ~3.6ms of the opaque pass at
            // 1080p (8.5 -> 4.9ms measured). Bent crown normals + vertex AO carry the volume.
            ..default()
        });
    }
    let ormh = images.add(load::texture(&format!("forest_pbr/{set}_ormh.png"), false, None)?);
    Ok(StandardMaterial {
        base_color_texture: Some(albedo),
        normal_map_texture: Some(normal),
        occlusion_texture: Some(ormh.clone()),
        metallic_roughness_texture: Some(ormh),
        // Both act as multipliers on the texture channels (G roughness, B metal = 0).
        perceptual_roughness: 1.0,
        metallic: 1.0,
        reflectance: 0.35,
        ..default()
    })
}

fn try_build(
    meshes: &mut Assets<Mesh>,
    materials: &mut Assets<StandardMaterial>,
    foliage_mats: &mut Assets<foliage::FoliageMaterial>,
    mut snow_mats: Option<&mut Assets<crate::alpine::snowkit::SnowKitMaterial>>,
    images: &mut Assets<Image>,
) -> Result<Kit, String> {
    let mut mats = Vec::new();
    let mut snow_twins = Vec::new();
    let mut mat_index = HashMap::new();
    for (name, set, card) in MATERIALS {
        mat_index.insert(name.to_string(), mats.len());
        let m = pbr_material(images, set, card)?;
        // Snow-dusted twin for the snow biome (`alpine::snowkit`): same textures, crown tint kept.
        let tint = match name {
            "canopy" => 0.6,
            "undergrowth" => 0.35,
            _ => 0.0,
        };
        snow_twins.push(match (crate::alpine::snowkit::snow_amount(name), snow_mats.as_deref_mut()) {
            (Some(amount), Some(sm)) => Some(KitMat::Snow(sm.add(crate::alpine::snowkit::twin(&m, tint, amount)))),
            _ => None,
        });
        // Leaf cards sway a little at the crown edge, undergrowth blades more at the tips; plus
        // crown / undergrowth colour variety (see `foliage`).
        mats.push(match name {
            "canopy" => KitMat::Foliage(foliage_mats.add(foliage::material(m, 0.025, 1.2, 0.6))),
            "undergrowth" => KitMat::Foliage(foliage_mats.add(foliage::material(m, 0.035, 2.5, 0.35))),
            _ => KitMat::Std(materials.add(m)),
        });
    }
    let wind = [mat_index["canopy"], mat_index["undergrowth"]];
    let mut models = Vec::new();
    let mut by_name = HashMap::new();
    for glb in ["forest_pbr/trees.glb", "forest_pbr/undergrowth.glb", "forest_pbr/props.glb", "forest_pbr/structures.glb", "forest_pbr/wayside.glb", "forest_pbr/stories_warm.glb", "forest_pbr/creatures.glb", "forest_pbr/animals.glb", "forest_pbr/people.glb", "forest_pbr/orks.glb", "forest_pbr/stories_cold.glb", "forest_pbr/snowmen.glb", "forest_pbr/alpine_flora.glb"] {
        // The townsfolk parts (people.glb) and the skinned ork bodies (orks.glb) are optional:
        // without them the villagers keep their box-built bodies (`peasant_model`) and the orks
        // their per-joint creatures.glb parts; the rest of the kit still loads.
        if (glb.ends_with("people.glb") || glb.ends_with("orks.glb") || glb.contains("/stories_") || glb.ends_with("snowmen.glb") || glb.ends_with("alpine_flora.glb"))
            && !load::asset_path(glb).exists()
        {
            warn!("realforest: {glb} missing — falling back to the older bodies");
            continue;
        }
        let mut objs = load::read_glb(glb)?;
        // `attach_tree` finds a tree's LOD1 at `lod0 + 1`, so keep each _lod0 / _lod1 pair adjacent.
        objs.sort_by(|a, b| a.0.cmp(&b.0));
        for (name, prims) in objs {
            let mut raw = Vec::new();
            for p in prims {
                let mat = *mat_index.get(&p.material).ok_or_else(|| format!("{name}: unknown material {}", p.material))?;
                raw.push((p.mesh, mat));
            }
            {
                let mut view: Vec<(&mut Mesh, bool)> = raw.iter_mut().map(|(m, i)| (m, wind.contains(i))).collect();
                foliage::bake_weights(&mut view);
            }
            let parts: Vec<Part> = raw
                .into_iter()
                .map(|(mesh, mat)| Part { handle: meshes.add(mesh.clone()), mesh, mat })
                .collect();
            let (half, trunk, height) = model_extents(&parts, &mats);
            let solid = ["rock_", "log_", "stump_"].iter().any(|p| name.starts_with(p));
            if std::env::var("FOREST_KITDUMP").is_ok() {
                info!("kit model {name}: half {:.2}x{:.2} height {:.2} trunk {:.2}", half.x, half.y, height, trunk);
            }
            by_name.insert(name, models.len());
            models.push(Model { parts, half, trunk, solid, height });
        }
    }
    let ground = GroundTextures {
        albedo: images.add(load::texture_array("forest_pbr/ground_albedo.dds", &LAYERS.map(|l| format!("forest_pbr/ground_{l}_albedo.png")).each_ref().map(|s| s.as_str()), true)?),
        normal: images.add(load::texture_array("forest_pbr/ground_normal.dds", &LAYERS.map(|l| format!("forest_pbr/ground_{l}_normal.png")).each_ref().map(|s| s.as_str()), false)?),
        ormh: images.add(load::texture_array("forest_pbr/ground_ormh.dds", &LAYERS.map(|l| format!("forest_pbr/ground_{l}_ormh.png")).each_ref().map(|s| s.as_str()), false)?),
    };
    // Scanned creature surface layers (orks, villagers, wildlife) — optional.
    let creature = ["albedo", "ormh"].map(|m| {
        let pngs = ["skin", "fur", "leather", "wood", "metal", "cloth", "bone"].map(|l| format!("forest_pbr/creature_{l}_{m}.png"));
        load::texture_array(&format!("forest_pbr/creature_{m}.dds"), &pngs.each_ref().map(|s| s.as_str()), m == "albedo")
    });
    match creature {
        [Ok(a), Ok(o)] => crate::creature::set_detail_layers(images.add(a), images.add(o)),
        _ => warn!("realforest: creature detail layers missing — creatures keep the procedural surfaces"),
    }
    Ok(Kit { mats, snow_mats: snow_twins, models, by_name, ground })
}

/// (XZ half-extent, trunk-base radius) of a model from its CPU meshes. The trunk radius is the
/// widest bark vertex below 0.3u (root flare included) — the kit trees' only plain-PBR part.
fn model_extents(parts: &[Part], mats: &[KitMat]) -> (Vec2, f32, f32) {
    use bevy::mesh::VertexAttributeValues;
    let (mut half, mut trunk, mut height) = (Vec2::ZERO, 0.0f32, 0.0f32);
    for part in parts {
        let Some(VertexAttributeValues::Float32x3(p)) = part.mesh.attribute(Mesh::ATTRIBUTE_POSITION) else { continue };
        let bark = matches!(mats[part.mat], KitMat::Std(_)) && MATERIALS[part.mat].0.starts_with("bark_");
        for v in p {
            half = half.max(Vec2::new(v[0].abs(), v[2].abs()));
            height = height.max(v[1]);
            if bark && v[1] < 0.3 {
                trunk = trunk.max((v[0] * v[0] + v[2] * v[2]).sqrt());
            }
        }
    }
    (half, trunk, height)
}

/// Ground layers, in texture-array order (`terrain.wgsl` indexes them 0/1/2).
const LAYERS: [&str; 3] = ["litter", "moss", "path"];

pub(crate) fn build_kit(
    mut meshes: ResMut<Assets<Mesh>>,
    mut materials: ResMut<Assets<StandardMaterial>>,
    mut foliage_mats: ResMut<Assets<foliage::FoliageMaterial>>,
    mut snow_mats: Option<ResMut<Assets<crate::alpine::snowkit::SnowKitMaterial>>>,
    mut images: ResMut<Assets<Image>>,
) {
    let t0 = std::time::Instant::now();
    match try_build(&mut meshes, &mut materials, &mut foliage_mats, snow_mats.as_deref_mut(), &mut images) {
        Ok(kit) => {
            info!("realforest: kit loaded ({} models) in {:.2}s", kit.models.len(), t0.elapsed().as_secs_f32());
            let _ = KIT.set(kit);
        }
        Err(e) => warn!("realforest: kit failed to load, keeping the low-poly forest — {e}"),
    }
}

// ── Terrain hook ───────────────────────────────────────────────────────────────────────────────

/// Bind the forest-floor layers + the forest/road mask into every world terrain material once.
/// Terrain materials are minted inside the world build (and again on every in-process rebuild),
/// so this watches for unpatched ones instead of hooking each creation site.
fn patch_terrain(
    mut mats: ResMut<Assets<TerrainMaterial>>,
    mut images: ResMut<Assets<Image>>,
    mut mask: Local<Option<(Handle<Image>, Vec4)>>,
) {
    let Some(kit) = get() else { return };
    // The mask's contact-AO channel needs the forest scatter's splats - wait for it.
    if !SCATTER_DONE.load(std::sync::atomic::Ordering::Acquire) {
        return;
    }
    let todo: Vec<_> = mats.iter().filter(|(_, m)| m.extension.params.pbr.x == 0.0).map(|(id, _)| id).collect();
    for id in todo {
        let Some(mut m) = mats.get_mut(id) else { continue };
        // Ground without a road network = a single-biome viewer / ground test: leave it alone.
        // `FOREST_PBR_GROUND=0` keeps the procedural floor (perf isolation / A-B).
        if m.extension.params.rut_region.z <= 0.0 || std::env::var("FOREST_PBR_GROUND").is_ok_and(|v| v == "0") {
            m.extension.params.pbr.x = -1.0;
            continue;
        }
        let (mask_h, region) = mask.get_or_insert_with(|| bake_mask(&mut images)).clone();
        let ext = &mut m.extension;
        ext.fp_albedo = kit.ground.albedo.clone();
        ext.fp_normal = kit.ground.normal.clone();
        ext.fp_ormh = kit.ground.ormh.clone();
        ext.fp_mask = mask_h;
        ext.params.pbr = Vec4::new(1.0, 0.0, 0.0, 0.0);
        ext.params.pbr_region = region;
    }
}

/// RGBA8 mask over the whole tile grid at 2 texels / unit: R = forest tile (soft-edged),
/// G = road strength (worn trail -> the path layer), B = contact darkening around trunks and
/// solid props (the root/stone <-> ground junction). World->UV = `(w - xy) * zw`.
fn bake_mask(images: &mut Assets<Image>) -> (Handle<Image>, Vec4) {
    use crate::worldmap::{COLS, GX, GZ, ROWS};
    const RES: f32 = 2.0;
    let (x0, z0) = (-GX, -GZ);
    let (w, h) = ((COLS as f32 * RES) as usize, (ROWS as f32 * RES) as usize);
    let mut forest = vec![0.0f32; w * h];
    let mut land = vec![false; w * h];
    let mut road = vec![0u8; w * h];
    for j in 0..h {
        let wz = z0 + (j as f32 + 0.5) / RES;
        for i in 0..w {
            let wx = x0 + (i as f32 + 0.5) / RES;
            let k = j * w + i;
            land[k] = crate::worldmap::is_land_tile_world(wx, wz);
            forest[k] = (crate::worldmap::tile_biome_world(wx, wz) == Some(crate::biome::Biome::Forest)) as u8 as f32;
            road[k] = (crate::roads::road_strength(wx, wz).clamp(0.0, 1.0) * 255.0) as u8;
        }
    }
    // Carry the land's forest weight a few units OUT over the water tiles first: an eroded river /
    // lake bank runs down into the water tile beside it, and without this the floor faded to bare
    // vertex green along every forest stream (the bright strip on the bank lip). Each water texel
    // takes the mean of its already-filled neighbours, ring by ring (nearest land wins), so a
    // stream between forest and meadow splits down the middle instead of one side taking both.
    let mut filled = land;
    for _ in 0..6 {
        let (prev, prev_filled) = (forest.clone(), filled.clone());
        for j in 0..h {
            for i in 0..w {
                let k = j * w + i;
                if prev_filled[k] {
                    continue;
                }
                let (mut s, mut n) = (0.0, 0u32);
                for (ok, kk) in [(i > 0, k.wrapping_sub(1)), (i + 1 < w, k + 1), (j > 0, k.wrapping_sub(w)), (j + 1 < h, k + w)] {
                    if ok && prev_filled[kk] {
                        s += prev[kk];
                        n += 1;
                    }
                }
                if n > 0 {
                    forest[k] = s / n as f32;
                    filled[k] = true;
                }
            }
        }
    }
    // Separable box blur (radius 3 texels = 1.5u) so the forest edge feathers instead of
    // stair-stepping along tile borders.
    let r = 3i32;
    let blur = |src: &[f32], horiz: bool| -> Vec<f32> {
        let mut out = vec![0.0f32; w * h];
        for j in 0..h as i32 {
            for i in 0..w as i32 {
                let mut s = 0.0;
                for d in -r..=r {
                    let (x, y) = if horiz { ((i + d).clamp(0, w as i32 - 1), j) } else { (i, (j + d).clamp(0, h as i32 - 1)) };
                    s += src[y as usize * w + x as usize];
                }
                out[j as usize * w + i as usize] = s / (2 * r + 1) as f32;
            }
        }
        out
    };
    let forest = blur(&blur(&forest, true), false);
    let mut occl = vec![0.0f32; w * h];
    for sp in SPLATS.lock().expect("splats poisoned").iter() {
        let (cx, cz, r) = (sp.x, sp.y, sp.z.max(0.2));
        let reach = r * 2.6;
        let i0 = ((cx - reach - x0) * RES).floor().max(0.0) as usize;
        let i1 = (((cx + reach - x0) * RES).ceil().max(0.0) as usize).min(w);
        let j0 = ((cz - reach - z0) * RES).floor().max(0.0) as usize;
        let j1 = (((cz + reach - z0) * RES).ceil().max(0.0) as usize).min(h);
        for j in j0..j1 {
            let dz = z0 + (j as f32 + 0.5) / RES - cz;
            for i in i0..i1 {
                let dx = x0 + (i as f32 + 0.5) / RES - cx;
                let v = (-(dx * dx + dz * dz) / (r * r * 1.6)).exp();
                let o = &mut occl[j * w + i];
                *o = 1.0 - (1.0 - *o) * (1.0 - v);
            }
        }
    }
    let mut grove = vec![0u8; w * h];
    for j in 0..h {
        let wz = z0 + (j as f32 + 0.5) / RES;
        for i in 0..w {
            let wx = x0 + (i as f32 + 0.5) / RES;
            grove[j * w + i] = (crate::biome::forest_grove(wx, wz) * 255.0).round() as u8;
        }
    }
    let mut data = vec![0u8; w * h * 4];
    for k in 0..w * h {
        data[k * 4] = (forest[k] * 255.0).round() as u8;
        data[k * 4 + 1] = road[k];
        data[k * 4 + 2] = (occl[k].clamp(0.0, 1.0) * 255.0).round() as u8;
        data[k * 4 + 3] = grove[k];
    }
    // The castle yard's worn ground (lanes, plaza, wall paths, working corners) rides the same
    // channels: scanned floor + trail + debris — see `castle_ground`.
    let to_u8 = |v: f32| (v.clamp(0.0, 1.0) * 255.0).round() as u8;
    let (i0, i1) = (((-crate::castle_ground::REACH_X - x0) * RES).max(0.0) as usize, (((crate::castle_ground::REACH_X - x0) * RES) as usize).min(w));
    let (j0, j1) = (((-crate::castle_ground::REACH_Z - z0) * RES).max(0.0) as usize, (((crate::castle_ground::REACH_Z - z0) * RES) as usize).min(h));
    for j in j0..j1 {
        let wz = z0 + (j as f32 + 0.5) / RES;
        for i in i0..i1 {
            let wx = x0 + (i as f32 + 0.5) / RES;
            let g = crate::castle_ground::sample(wx, wz);
            if g.floor <= 0.0 {
                continue;
            }
            let k = (j * w + i) * 4;
            data[k] = data[k].max(to_u8(g.floor));
            data[k + 1] = data[k + 1].max(to_u8(g.path));
            data[k + 3] = data[k + 3].max(to_u8(g.debris));
        }
    }
    let mut img = Image::new(
        bevy::render::render_resource::Extent3d { width: w as u32, height: h as u32, depth_or_array_layers: 1 },
        bevy::render::render_resource::TextureDimension::D2,
        data,
        bevy::render::render_resource::TextureFormat::Rgba8Unorm,
        bevy::asset::RenderAssetUsages::default(),
    );
    img.sampler = bevy::image::ImageSampler::Descriptor(bevy::image::ImageSamplerDescriptor {
        mag_filter: bevy::image::ImageFilterMode::Linear,
        min_filter: bevy::image::ImageFilterMode::Linear,
        ..default()
    });
    (images.add(img), Vec4::new(x0, z0, 1.0 / COLS as f32, 1.0 / ROWS as f32))
}
