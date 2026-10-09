"""Forest-floor PBR layers for the terrain shader's forest splat.

Three tileable Poly Haven CC0 scans, each packed by `common.write_pbr_set` into 1024² maps:

  ground_<layer>_albedo.png  sRGB base colour
  ground_<layer>_normal.png  tangent-space normal, OpenGL (+Y) convention
  ground_<layer>_ormh.png    linear: R = AO, G = roughness, B = metallic (0), A = height (0..1)

Layers (order = texture-array layer index in `terrain.wgsl`):
  0 litter  forest_leaves_02   broadleaf litter, twigs, damp patches (the main floor)
  1 moss    forrest_ground_01  short grass + needles for the lighter clearings
  2 path    forest_ground_04   compacted stony soil under trails

Height is normalised per layer so the shader's height-blend compares like with like.
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
from common import ph_tex, write_pbr_set  # noqa: E402

LAYERS = [
    # (name, poly haven id, saturation, brightness) - graded toward the game's slightly muted,
    # overcast-forest palette so the scans sit next to the existing biomes.
    ("litter", "forest_leaves_02", 0.65, 1.05),
    ("moss", "forrest_ground_01", 0.85, 1.0),
    ("path", "forest_ground_04", 0.55, 0.95),
]

for name, aid, sat, gain in LAYERS:
    write_pbr_set(
        f"ground_{name}",
        ph_tex(aid, "diff"),
        ph_tex(aid, "nor_gl"),
        ph_tex(aid, "rough"),
        ao=ph_tex(aid, "ao"),
        disp=ph_tex(aid, "disp"),
        sat=sat,
        gain=gain,
    )

print("GROUND_DONE")
