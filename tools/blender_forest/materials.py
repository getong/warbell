"""Bark + prop PBR sets (same albedo / normal / ormh packing as the ground layers).

Bark scans are tileable and get wrapped around the generated trunks by `trees.py`.
Prop sets belong to specific Poly Haven models (their own UV layouts) and are re-used
verbatim by `props.py` after decimation.

Pass set names after `--` to (re)build only those sets, e.g.
    blender -b --factory-startup --python tools/blender_forest/materials.py -- s_rock s_earth
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
from common import ph_model_tex, ph_tex, write_pbr_set as _write_pbr_set  # noqa: E402

ONLY = set(sys.argv[sys.argv.index("--") + 1:]) if "--" in sys.argv else set()


def write_pbr_set(name, *a, **k):
    if not ONLY or name in ONLY:
        _write_pbr_set(name, *a, **k)


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

# Scanned small props (scanned_props.py): the Poly Haven models' own texture sets, 1k.
# (name, model id, saturation, gain). Packed arm = AO / roughness / metal. (ph_wine_barrel_01 is BAKED by
# scanned_props.py instead, onto a clean lathe.)
SCANNED = [
    ("ph_shrub_02", "shrub_02", 0.95, 1.0),
    ("ph_wooden_crate_01", "wooden_crate_01", 0.9, 1.0),
    ("ph_wooden_crate_02", "wooden_crate_02", 0.9, 1.0),
]
for name, mid, sat, gain in SCANNED:
    a = ph_model_tex(mid, f"{mid}_arm_1k.jpg")
    write_pbr_set(name, ph_model_tex(mid, f"{mid}_diff_1k.jpg"), ph_model_tex(mid, f"{mid}_nor_gl_1k.jpg"),
                  (a, 1), ao=(a, 0), sat=sat, gain=gain)

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
    # Wayside furniture / story set-pieces (wayside_models.py): natural weathered rock for
    # megaliths, cairns and headstones (lichen kept subtle so a vertex tint can steer it per biome)
    # and plain trodden earth for grave mounds / ash beds.
    ("s_rock", "mossy_rock", 0.5, 1.25),
    ("s_earth", "dirt_floor", 0.55, 0.95),
]
for name, aid, sat, gain in SETS:
    write_pbr_set(name, ph_tex(aid, "diff"), ph_tex(aid, "nor_gl"), ph_tex(aid, "rough"),
                  ao=ph_tex(aid, "ao"), disp=ph_tex(aid, "disp"), sat=sat, gain=gain)


def nail_free_timber():
    """s_timber: the medieval_wood boards with their rows of nail heads cut out. Three nail-free
    horizontal bands of the scan are stacked (cross-faded, wrapped so it still tiles vertically);
    the grain runs along v. Posts, rails and beams sample within one board of it (wayside_models
    TIMBER_ZONES) so a narrow member shows clean weathered wood, not a studded strip."""
    import tempfile

    import numpy as np
    from common import load, save
    # Source rows (2k scan) between the nail rows at ~138, 308, 868, 1038, 1475, 1645, 1820.
    bands = [(345, 830), (1075, 1440), (1855, 2150)]
    fade = 48
    tmp = Path(tempfile.gettempdir()) / "warbell_timber"
    out_paths = {}
    for key in ("diff", "nor_gl", "rough", "ao", "disp"):
        a = load(ph_tex("medieval_wood", key), 3)
        h = a.shape[0]
        w = np.linspace(0.0, 1.0, fade)[:, None, None]
        out = None
        for y0, y1 in bands:
            seg = a[np.arange(y0, y1) % h]
            out = seg if out is None else np.concatenate([out[:-fade], out[-fade:] * (1 - w) + seg[:fade] * w, seg[fade:]], 0)
        out[:fade] = out[-fade:] * (1 - w) + out[:fade] * w
        out = out[:-fade]
        out_paths[key] = tmp / f"timber_{key}.png"
        save(out, out_paths[key])
    write_pbr_set("s_timber", out_paths["diff"], out_paths["nor_gl"], out_paths["rough"], ao=out_paths["ao"],
                  disp=out_paths["disp"], sat=0.85, gain=1.25)


if not ONLY or "s_timber" in ONLY:
    nail_free_timber()

print("MATERIALS_DONE")
