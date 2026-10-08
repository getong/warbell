# Blender forest kit

Headless Blender pipeline that builds the realistic forest biome assets in
`assets/forest_pbr/`. The game side is `src/realforest/` (loader, materials, scatter hook) and
the forest-floor splat + parallax in `assets/shaders/terrain.wgsl`.

## Run

Blender 4.5 LTS (portable zip is fine) and the Poly Haven sources (below). From the repo root:

```bash
B=path/to/blender.exe
for s in ground materials foliage trees undergrowth props; do
  "$B" -b --factory-startup --python tools/blender_forest/$s.py
done
# optional studio render of a lineup (Eevee):
"$B" -b --factory-startup --python tools/blender_forest/preview.py -- shots/realforest/trees.png trees.glb
```

`PH_SRC` points at the downloaded Poly Haven folder (default
`C:/Users/skibi/Documents/Codex/polyhaven_src`), laid out as
`textures/<id>/<id>_<map>_2k.png` and `models/<id>/<id>_1k.gltf` + `textures/`.

| Script | Output | What it does |
|---|---|---|
| `ground.py` | `ground_{litter,moss,path}_*` | 3 tileable floor scans → 1k albedo / normal / ORM+height |
| `materials.py` | `bark_*`, `prop_*` | bark scans + the prop models' own texture sets |
| `foliage.py` | `canopy_*`, `undergrowth_*`, `foliage_layout.json` | leaf spray built from scanned leaves, procedural needle spray, cropped fern / grass cards |
| `trees.py` | `trees.glb` | procedurally grown oaks, beeches, pines, a dead snag, bushes — 2 LODs each |
| `undergrowth.py` | `undergrowth.glb` | ferns (arching frond strips), grass clumps, seed stalks |
| `props.py` | `props.glb` | Poly Haven stump / log / deadfall / mossy rocks, decimated |
| `preview.py` | PNG | Eevee lineup render with the same material binding as the game |

## Texture contract

- `<set>_albedo.png`: sRGB, alpha = coverage for card sets (colour bled under alpha 0).
- `<set>_normal.png`: tangent space, OpenGL (+Y up).
- `<set>_ormh.png`: linear glTF ORM (R = AO, G = roughness, B = metallic 0), plus A = height
  (0..1, per-layer normalised; used by the terrain parallax).

GLBs carry geometry only (positions, normals, UV0, tangents, vertex colour). Materials are exported
as names (`bark_oak`, `canopy`, `undergrowth`, `prop_rock_a`, ...) that the game binds to the sets above.
Base at Z = 0, game units (hero ≈ 1.3u, 1u ≈ 1.35 m).

## Budgets

| Asset | LOD0 tris | LOD1 tris |
|---|---|---|
| oak / beech | 1.2–1.7k | 0.33–0.43k |
| pine | 2.3–2.6k | 0.42–0.48k |
| dead snag | 0.76k | 0.17k |
| bush | 0.21k | 0.06k |
| fern / grass / stalks | 112–128 / 6 / 4 | — |
| stump / log / deadfall / rock | 1000 / 1400 / 700 / 350 | — |

Trees cross-fade to LOD1 at 42u and cull at 180u. Undergrowth and props merge per 16u chunk
per material, cut off at 58u / 75u, and cast no shadows.

## Sources (all CC0, polyhaven.com)

Textures: `forest_leaves_02`, `forrest_ground_01`, `forest_ground_04`, `bark_brown_02`,
`pine_bark`, `tree_bark_03`. Models (textures and/or geometry): `shrub_04` (leaves),
`fern_02`, `grass_medium_01`, `tree_stump_01`, `dead_tree_trunk`, `dry_branches_medium_01`,
`rock_moss_set_01`, `rock_moss_set_02`.
