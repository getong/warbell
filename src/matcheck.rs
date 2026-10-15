//! `FOREST_MATCHECK=1`: flags any mesh entity carrying MORE THAN ONE `MeshMaterial3d<T>` type.
//! Each material plugin queues the entity into the same render phase, so a doubled material is the
//! Bevy 0.20 "Binning main entity … when it was already binned" panic waiting to happen. Logs the
//! offender (name + parent chain + which types) the frame it appears.

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
