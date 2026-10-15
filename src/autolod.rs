//! **Automatic mesh LOD** — meshoptimizer's edge-collapse simplifier (`meshopt`) on any Bevy `Mesh`.
//!
//! Simplification only produces a new index buffer over the SAME vertices, so every attribute
//! (UVs, tangents, vertex colours, skin joints / weights, the foliage wind weights) carries over
//! untouched; the result is then compacted to the vertices it still references. Seams (UV / colour
//! splits sharing a position) are welded by the simplifier itself, so they don't tear.
//!
//! Used where a far tier costs vertex work nobody can see: the kit props chunks past
//! `realforest::PROPS_LOD`, biome static models, skinned townsfolk / animals past a few dozen units.

use bevy::mesh::{Indices, VertexAttributeValues};
use bevy::prelude::*;

/// Simplify `mesh` to about `ratio` of its triangles, stopping early where the deviation would
/// exceed `max_error` (fraction of the mesh's extent). `None` when the mesh isn't an indexed /
/// non-indexed triangle list with float3 positions, or simplifying wouldn't save ≥15%.
pub fn simplify(mesh: &Mesh, ratio: f32, max_error: f32) -> Option<Mesh> {
    simplified_indices(mesh, ratio, max_error, false).map(|out| compact(mesh, &out))
}

/// [`simplify`] for a FAR tier: when the topology-preserving collapse stalls well short of the
/// target (flat-faceted models, where every edge is a normal seam — the rock spires didn't lose a
/// single triangle), fall back to meshopt's sloppy vertex clustering, which ignores topology. Fine
/// at the distances a far twin is drawn.
pub fn simplify_far(mesh: &Mesh, ratio: f32, max_error: f32) -> Option<Mesh> {
    simplified_indices(mesh, ratio, max_error, true).map(|out| compact(mesh, &out))
}

/// [`simplify`], keeping the full vertex buffer (only the index buffer shrinks) — for meshes whose
/// per-vertex side data is indexed by vertex number (morph targets: the townsfolk's mouths).
pub fn simplify_keep_vertices(mesh: &Mesh, ratio: f32, max_error: f32) -> Option<Mesh> {
    let out = simplified_indices(mesh, ratio, max_error, false)?;
    let mut m = mesh.clone();
    m.insert_indices(Indices::U32(out));
    Some(m)
}

fn simplified_indices(mesh: &Mesh, ratio: f32, max_error: f32, sloppy: bool) -> Option<Vec<u32>> {
    let Some(VertexAttributeValues::Float32x3(pos)) = mesh.try_attribute_option(Mesh::ATTRIBUTE_POSITION).ok().flatten() else {
        return None;
    };
    let indices: Vec<u32> = match mesh.try_indices_option().ok()? {
        Some(Indices::U32(i)) => i.clone(),
        Some(Indices::U16(i)) => i.iter().map(|&v| v as u32).collect(),
        None => (0..pos.len() as u32).collect(),
    };
    if indices.len() < 3 * 64 {
        return None;
    }
    let target = ((indices.len() as f32 * ratio) as usize / 3 * 3).max(3);
    let mut out = meshopt::simplify_decoder(&indices, pos, target, max_error, meshopt::SimplifyOptions::None, None);
    if sloppy && out.len() > target * 8 / 5 {
        let loose = meshopt::simplify_sloppy_decoder(&indices, pos, target, max_error * 2.0, None);
        if !loose.is_empty() && loose.len() < out.len() {
            out = loose;
        }
    }
    if out.is_empty() || out.len() as f32 > indices.len() as f32 * 0.85 {
        return None;
    }
    Some(out)
}

/// `mesh` reduced to the vertices `indices` references, re-indexed (U32).
fn compact(mesh: &Mesh, indices: &[u32]) -> Mesh {
    let n = mesh.count_vertices();
    let mut remap = vec![u32::MAX; n];
    let mut order = Vec::new();
    for &i in indices {
        if remap[i as usize] == u32::MAX {
            remap[i as usize] = order.len() as u32;
            order.push(i as usize);
        }
    }
    let mut out = Mesh::new(mesh.primitive_topology(), mesh.asset_usage);
    for (attr, values) in mesh.attributes() {
        if let Some(v) = gather(values, &order) {
            out.insert_attribute(attr.clone(), v);
        }
    }
    out.insert_indices(Indices::U32(indices.iter().map(|&i| remap[i as usize]).collect()));
    out
}

fn gather(values: &VertexAttributeValues, order: &[usize]) -> Option<VertexAttributeValues> {
    use VertexAttributeValues as V;
    macro_rules! g {
        ($variant:ident, $v:expr) => {
            V::$variant(order.iter().map(|&i| $v[i]).collect())
        };
    }
    Some(match values {
        V::Float32(v) => g!(Float32, v),
        V::Float32x2(v) => g!(Float32x2, v),
        V::Float32x3(v) => g!(Float32x3, v),
        V::Float32x4(v) => g!(Float32x4, v),
        V::Uint32(v) => g!(Uint32, v),
        V::Uint32x2(v) => g!(Uint32x2, v),
        V::Uint32x3(v) => g!(Uint32x3, v),
        V::Uint32x4(v) => g!(Uint32x4, v),
        V::Uint16x2(v) => g!(Uint16x2, v),
        V::Uint16x4(v) => g!(Uint16x4, v),
        V::Unorm16x2(v) => g!(Unorm16x2, v),
        V::Unorm16x4(v) => g!(Unorm16x4, v),
        V::Uint8x2(v) => g!(Uint8x2, v),
        V::Uint8x4(v) => g!(Uint8x4, v),
        V::Unorm8x2(v) => g!(Unorm8x2, v),
        V::Unorm8x4(v) => g!(Unorm8x4, v),
        V::Sint32(v) => g!(Sint32, v),
        V::Sint32x2(v) => g!(Sint32x2, v),
        V::Sint32x3(v) => g!(Sint32x3, v),
        V::Sint32x4(v) => g!(Sint32x4, v),
        V::Sint16x2(v) => g!(Sint16x2, v),
        V::Sint16x4(v) => g!(Sint16x4, v),
        V::Snorm16x2(v) => g!(Snorm16x2, v),
        V::Snorm16x4(v) => g!(Snorm16x4, v),
        V::Sint8x2(v) => g!(Sint8x2, v),
        V::Sint8x4(v) => g!(Sint8x4, v),
        V::Snorm8x2(v) => g!(Snorm8x2, v),
        V::Snorm8x4(v) => g!(Snorm8x4, v),
        _ => return None,
    })
}
