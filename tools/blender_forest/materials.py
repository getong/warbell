"""Bark + prop PBR sets (same albedo / normal / ormh packing as the ground layers).

Bark scans are tileable and get wrapped around the generated trunks by `trees.py`.
Prop sets belong to specific Poly Haven models (their own UV layouts) and are re-used
verbatim by `props.py` after decimation.
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
from common import ph_model_tex, ph_tex, write_pbr_set  # noqa: E402

BARK = [
    # (name, poly haven id, saturation, brightness)
    ("bark_oak", "bark_brown_02", 0.85, 1.45),
    ("bark_pine", "pine_bark", 0.80, 1.40),
    ("bark_beech", "tree_bark_03", 0.75, 1.15),
]
for name, aid, sat, gain in BARK:
    write_pbr_set(
        name,
        ph_tex(aid, "diff"),
        ph_tex(aid, "nor_gl"),
        ph_tex(aid, "rough"),
        ao=ph_tex(aid, "ao"),
        disp=ph_tex(aid, "disp"),
        sat=sat,
        gain=gain,
    )

PROPS = [
    # (name, model id, texture prefix, has packed arm)
    ("prop_stump", "tree_stump_01", "tree_stump_01", True),
    ("prop_log", "dead_tree_trunk", "dead_tree_trunk", True),
    ("prop_branches", "dry_branches_medium_01", "dry_branches_medium_01", True),
    ("prop_rock_a", "rock_moss_set_01", "rock_moss_set_01", False),
    ("prop_rock_b", "rock_moss_set_02", "rock_moss_set_02", False),
]
for name, mid, pre, arm in PROPS:
    diff = ph_model_tex(mid, f"{pre}_diff_1k.jpg")
    nor = ph_model_tex(mid, f"{pre}_nor_gl_1k.jpg")
    if arm:
        a = ph_model_tex(mid, f"{pre}_arm_1k.jpg")
        write_pbr_set(name, diff, nor, (a, 1), ao=(a, 0), sat=0.92)
    else:
        write_pbr_set(name, diff, nor, ph_model_tex(mid, f"{pre}_rough_1k.jpg"), sat=0.92)

# Structure re-skin layers (`realforest::reskin`): wood / stone / cloth DETAIL textures laid
# triplanar over the low-poly buildings' vertex colours. Albedo is normalised to a 0.5 per-channel
# mean so the shader can multiply it onto the authored vertex colour (x2) without shifting it.
STRUCT = [
    ("struct_wood", "medieval_wood", 0.55),
    ("struct_stone", "mossy_stone_wall", 0.70),
    ("struct_cloth", "hessian_230", 0.35),
]
for name, aid, sat in STRUCT:
    write_pbr_set(name, ph_tex(aid, "diff"), ph_tex(aid, "nor_gl"), ph_tex(aid, "rough"),
                  ao=ph_tex(aid, "ao"), disp=ph_tex(aid, "disp"), sat=sat, normalize=True)

# Structure sets (structures.py: ork camp, mill) - plain tileable PBR, vertex colour tints them.
SETS = [
    ("s_planks", "medieval_wood", 0.85, 1.25),
    ("s_stone", "mossy_stone_wall", 0.85, 1.2),
    ("s_hide", "fabric_leather_02", 0.75, 1.35),
    ("s_thatch", "thatch_roof_angled", 0.85, 1.15),
    ("s_cloth", "hessian_230", 0.7, 1.15),
    ("s_iron", "rusty_metal_02", 0.8, 1.0),
]
for name, aid, sat, gain in SETS:
    write_pbr_set(name, ph_tex(aid, "diff"), ph_tex(aid, "nor_gl"), ph_tex(aid, "rough"),
                  ao=ph_tex(aid, "ao"), disp=ph_tex(aid, "disp"), sat=sat, gain=gain)

print("MATERIALS_DONE")
