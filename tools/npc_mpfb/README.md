# Realistic NPC pipeline (MakeHuman / MPFB + Quaternius UAL) — experimental

Blender 4.5 + the MPFB 2 extension build photoreal-ish medieval townsfolk, and every Quaternius
Universal Animation Library clip (UAL1 + UAL2, CC0) is retargeted onto their shared `game_engine` rig.
Nothing here is wired into the game yet (the game skins people from its own 14-joint rig, see
`tools/blender_forest/people.py`); this is the content + proof-of-quality pipeline for replacing the
procedural townsfolk.

Downloads (each in its own folder under `C:/Users/skibi/Documents/Codex/downloads/`, never executed):
`oga_bartender` (CC0 hand-made woman), `ual1` / `ual2` (CC0 clips), `mpfb` (extension zip),
`mh_system_assets` + `mh_packs` (MakeHuman asset packs, copied into MPFB's user data dir).

| Script | What |
|---|---|
| `mpfb_cast.py` | one MPFB human from a spec (macro sliders, race, skin, hair, eyes, rig) |
| `npc_cast.py` | the 14-person cast; community garments are re-textured with Poly Haven linen / wool / leather |
| `build_cast_blend.py` | builds the whole cast into one .blend |
| `bake_anims.py` | UAL clips -> Blender Actions on the MPFB rig (bone-direction swing retarget; any cast member can play them) |
| `town_film.py` | town set from the game's own kits (`town_kit.glb`, `market.glb`, ...) + Poly Haven props + animated cast; renders frames |
| `build_cast_blend.py` / `export_game.py` | `blender -b --python build_cast_blend.py -- <out.blend> [name,...]` builds (part of) the cast; `blender -b <blend> --python export_game.py -- <npc> <out_dir>` bakes + exports one look (per-look `export` options in the cast spec: layer pass / hidden-skin cull / weight inheritance, see its docstring) |
| `dds2png.py` | decodes the game's BC7 DDS textures to PNG so Blender can bind them |
| `retarget_render.py` | single-character version (Bartender) used for the first showcase |

Paths inside the scripts point at the author's scratchpad; adjust `S`/`D` before re-running.
