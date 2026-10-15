//! `FOREST_MATCHECK=1`: flags any mesh entity carrying MORE THAN ONE `MeshMaterial3d<T>` type.
//! Each material plugin queues the entity into the same render phase, so a doubled material is the
//! Bevy 0.20 "Binning main entity … when it was already binned" panic waiting to happen. Logs the
//! offender (name + parent chain + which types) the frame it appears.
//!
//! `FOREST_VERTREPORT=1`: a census of the index counts the main camera draws, by mesh kind (below).

use bevy::prelude::*;

pub struct MatCheckPlugin;

impl Plugin for MatCheckPlugin {
    fn build(&self, app: &mut App) {
        if std::env::var_os("FOREST_MATCHECK").is_some() {
            app.add_systems(Last, check);
        }
        if std::env::var_os("FOREST_WHOIS").is_some() {
            app.add_systems(Last, whois);
        }
        if std::env::var_os("FOREST_VERTREPORT").is_some() {
            app.init_resource::<VertCensus>().add_systems(PostUpdate, (census_added, census_report).chain());
        }
    }
}

type M<T> = MeshMaterial3d<T>;

#[allow(clippy::type_complexity)]
fn check(
    q: Query<(
        Entity,
        (
            Has<M<StandardMaterial>>,
            Has<M<crate::creature::CreatureMaterial>>,
            Has<M<crate::vista::FallsMaterial>>,
            Has<M<crate::combat_marks::MarkMaterial>>,
            Has<M<crate::realforest::reskin::ReskinMaterial>>,
            Has<M<crate::terrain::TerrainMaterial>>,
            Has<M<crate::water::WaterMaterial>>,
            Has<M<crate::realforest::foliage::FoliageMaterial>>,
            Has<M<crate::alpine::snowkit::SnowKitMaterial>>,
            Has<M<crate::clouds::CloudSkyMaterial>>,
            Has<M<crate::combat_fx::HpBarMaterial>>,
        ),
    ), With<Mesh3d>>,
    names: Query<&Name>,
    parents: Query<&ChildOf>,
    mut seen: Local<bevy::platform::collections::HashSet<Entity>>,
) {
    const N: [&str; 11] = ["Standard", "Creature", "Falls", "Mark", "Reskin", "Terrain", "Water", "Foliage", "SnowKit", "CloudSky", "HpBar"];
    for (e, h) in &q {
        let f = [h.0, h.1, h.2, h.3, h.4, h.5, h.6, h.7, h.8, h.9, h.10];
        if f.iter().filter(|b| **b).count() < 2 || !seen.insert(e) {
            continue;
        }
        let types: Vec<&str> = f.iter().zip(N).filter(|(b, _)| **b).map(|(_, n)| n).collect();
        let mut chain = Vec::new();
        let mut cur = Some(e);
        while let Some(c) = cur {
            chain.push(names.get(c).map(|n| n.as_str().to_string()).unwrap_or_else(|_| format!("{c}")));
            cur = parents.get(c).ok().map(|p| p.parent());
            if chain.len() > 8 {
                break;
            }
        }
        warn!("MATCHECK: {e} has {types:?} — chain {}", chain.join(" < "));
    }
}

/// `FOREST_WHOIS=<entity index>`: log that mesh entity's name, parent chain and component list the
/// first frame it exists (to identify an entity named in a render-world panic message).
pub fn whois(world: &mut World, mut done: Local<bool>) {
    let Some(want) = std::env::var("FOREST_WHOIS").ok() else { return };
    if *done {
        return;
    }
    let prefix = format!("{want}v");
    let mut q = world.query::<Entity>();
    let Some(e) = q.iter(world).find(|e| format!("{e}").starts_with(&prefix)) else { return };
    *done = true;
    let comps: Vec<String> = world
        .inspect_entity(e)
        .map(|it| it.map(|(_, c)| { let n = format!("{:?}", c.name()); n.rsplit("::").next().unwrap_or("").trim_matches('"').to_string() }).collect())
        .unwrap_or_default();
    let mut chain = Vec::new();
    let mut cur = Some(e);
    while let Some(c) = cur {
        chain.push(world.get::<Name>(c).map(|n| n.as_str().to_string()).unwrap_or_else(|| format!("{c}")));
        cur = world.get::<ChildOf>(c).map(|p| p.parent());
    }
    let mesh = world.get::<Mesh3d>(e).map(|m| format!("{:?}", m.0.path()));
    let root = chain_root(world, e);
    let rc: Vec<String> = world
        .inspect_entity(root)
        .map(|it| it.map(|(_, c)| { let n = format!("{:?}", c.name()); n.rsplit("::").next().unwrap_or("").trim_matches('"').to_string() }).collect())
        .unwrap_or_default();
    warn!("WHOIS root {root}: comps {rc:?}");
    warn!("WHOIS {e}: chain {} | mesh {mesh:?} | comps {comps:?}", chain.join(" < "));
}

fn chain_root(world: &World, mut e: Entity) -> Entity {
    while let Some(p) = world.get::<ChildOf>(e) {
        e = p.parent();
    }
    e
}

/// `FOREST_VERTREPORT=1`: every 5 s, log the index count of all mesh entities the camera can see,
/// bucketed by what they are (material type, ground-cover flag, root entity name) — to find which
/// meshes the GPU's vertex work actually goes to. Counts are captured when each mesh entity appears
/// (GPU-only meshes are dropped from the main world after upload).
#[derive(Resource, Default)]
struct VertCensus {
    per: bevy::platform::collections::HashMap<Entity, (String, u32)>,
    last: f32,
}

#[allow(clippy::type_complexity)]
fn census_added(
    q: Query<(Entity, &Mesh3d, Has<M<StandardMaterial>>, Has<M<crate::realforest::foliage::FoliageMaterial>>, Has<M<crate::terrain::TerrainMaterial>>, Has<crate::biome::GroundCoverChunk>, Has<bevy::light::NotShadowCaster>, Option<&bevy::camera::visibility::VisibilityRange>), Added<Mesh3d>>,
    meshes: Res<Assets<Mesh>>,
    names: Query<&Name>,
    parents: Query<&ChildOf>,
    mut c: ResMut<VertCensus>,
) {
    for (e, m, std, fol, ter, cover, nsc, vr) in &q {
        let Some(mesh) = meshes.get(&m.0) else { continue };
        let n = mesh.indices().map_or(mesh.count_vertices(), |i| i.len()) as u32;
        let mut root = e;
        while let Ok(p) = parents.get(root) {
            root = p.parent();
        }
        let rn = names.get(root).map(|n| n.as_str().split(['(', ' ', '#']).next().unwrap_or("").to_string()).unwrap_or_default();
        let mat = if std { "std" } else if fol { "foliage" } else if ter { "terrain" } else { "other" };
        let rng = vr.map_or("".to_string(), |r| format!(" R{:.0}", r.end_margin.end));
        let tag = format!("{mat}{}{}{rng} root={}", if cover { " COVER" } else { "" }, if nsc { "" } else { " +shadow" }, if root == e { "-".into() } else { rn });
        c.per.insert(e, (tag, n));
    }
}

fn census_report(time: Res<Time<Real>>, vis: Query<(Entity, &ViewVisibility)>, gt: Query<&GlobalTransform>, cam: Query<&GlobalTransform, With<Camera3d>>, cam_vis: Query<&bevy::camera::visibility::VisibleEntities, With<Camera3d>>, mut c: ResMut<VertCensus>) {
    let main_vis: bevy::platform::collections::HashSet<Entity> = cam_vis.single().map(|v| v.iter(std::any::TypeId::of::<Mesh3d>()).copied().collect()).unwrap_or_default();
    let now = time.elapsed_secs();
    if now - c.last < 5.0 {
        return;
    }
    c.last = now;
    let mut sum: bevy::platform::collections::HashMap<String, (u64, u32)> = Default::default();
    let mut total = 0u64;
    c.per.retain(|e, _| vis.contains(*e));
    for (e, (tag, n)) in &c.per {
        if main_vis.contains(e) {
            let s = sum.entry(tag.clone()).or_default();
            s.0 += *n as u64;
            s.1 += 1;
            total += *n as u64;
        }
    }
    let mut v: Vec<_> = sum.into_iter().collect();
    v.sort_by(|a, b| b.1 .0.cmp(&a.1 .0));
    let top: Vec<String> = v.iter().take(14).map(|(t, (n, k))| format!("{:.2}M/{k} {t}", *n as f64 / 1e6)).collect();
    if let Ok(cp) = cam.single() {
        let mut hist = [0u32; 8];
        for (e, (tag, _)) in &c.per {
            if tag.starts_with("std COVER") && main_vis.contains(e) {
                if let Ok(g) = gt.get(*e) {
                    let d = g.translation().xz().distance(cp.translation().xz());
                    hist[((d / 20.0) as usize).min(7)] += 1;
                }
            }
        }
        info!("VERTS std COVER visible chunks by 20u distance band from camera {:?} (cam {:?})", hist, cp.translation());
    }
    info!("VERTS visible {:.2}M idx | {}", total as f64 / 1e6, top.join(" | "));
}
