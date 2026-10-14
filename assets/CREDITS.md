# Third-party asset credits

Downloaded models / textures used by the game (CLAUDE.md "Assets: download first"). Each source was
downloaded into its own folder outside the repo and converted by the named Blender script; nothing
bundled with a download is executed.

| Asset | Used for | Author | Licence | Source | Converted by |
|---|---|---|---|---|---|
| Raven (raven_0.blend) | carrion vulture (`oddities.rs`, recoloured to a griffon), crows over the Hold (`poi.rs`) | tehbucket (OpenGameArt) | CC0 1.0 | https://opengameart.org/content/raven-0 | `tools/blender_forest/creatures_dl.py` |
| Rabbit (rabbit.blend) | wild rabbit (`critters.rs`) | CDmir (OpenGameArt) | CC0 1.0 | https://opengameart.org/content/rabbit-0 | `tools/blender_forest/creatures_dl.py` |
| Esox - Animated Fish | pond / river fish (`fish.rs`) | CDmir (OpenGameArt) | CC0 1.0 | https://opengameart.org/content/esox-animated-fish | `tools/blender_forest/creatures_dl.py` |
| Shrub 02 (shrub_02) | the bushes (`bush_a` / `bush_b`: meadow bushes, forest class-2 slot) | Poly Haven | CC0 1.0 | https://polyhaven.com/a/shrub_02 | `tools/blender_forest/scanned_props.py` |
| Wine Barrel 01 (wine_barrel_01) | market barrels, meadow crate pile (look baked onto a low-poly lathe) | Poly Haven | CC0 1.0 | https://polyhaven.com/a/wine_barrel_01 | `tools/blender_forest/scanned_props.py` |
| Wooden Crate 01 (wooden_crate_01) | market barrels + meadow crate pile | Poly Haven | CC0 1.0 | https://polyhaven.com/a/wooden_crate_01 | `tools/blender_forest/scanned_props.py` |
| Wooden Crate 02 (wooden_crate_02) | market barrels + meadow crate pile | Poly Haven | CC0 1.0 | https://polyhaven.com/a/wooden_crate_02 | `tools/blender_forest/scanned_props.py` |
| Terrain Tiles (terrarium elevation) | horizon islands' height fields (`distant_isles.rs`: Lofoten, Austvågøya, Stromboli, Fogo, La Gomera, Jan Mayen) | Mapzen / AWS Open Data; sources incl. SRTM, GMTED2010, ETOPO1, EU-DEM, ArcticDEM | open data, attribution per source | https://github.com/tilezen/joerd/blob/master/docs/attribution.md | `tools/terrain_isles/fetch_isles.py` |
| Sentinel-2 cloudless 2016 | horizon islands' colour (`assets/isles/*_albedo.png`) | "Sentinel-2 cloudless - https://s2maps.eu by EOX IT Services GmbH (Contains modified Copernicus Sentinel data 2016 & 2017)" | CC BY 4.0 | https://s2maps.eu | `tools/terrain_isles/fetch_isles.py` |

Photographic textures from Poly Haven (CC0) are listed in `assets/forest_pbr/ATTRIBUTION.txt`.

## Realistic NPC pipeline (experimental, `tools/npc_mpfb/`, not shipped in the game yet)

| Asset | Author | Licence | Source |
|---|---|---|---|
| Bartender (rigged village woman) | CDmir, TinyWorlds | CC0 | https://opengameart.org/content/bartender |
| Universal Animation Library 1 + 2 (Standard) | Quaternius | CC0 | https://opengameart.org/content/universal-animation-library |
| MakeHuman system assets (bodies, skins, hair, eyes) | MakeHuman Community | CC0 | https://static.makehumancommunity.org/assets/assetpacks/makehuman_system_assets.html |
| MPFB 2 (Blender add-on, tool only) | MakeHuman Community | GPL-3.0+ (tool; output is CC0) | https://extensions.blender.org/add-ons/mpfb/ |
| Garments: toigo_wool_pants, toigo_long_full_skirt, culturalibre_male_boots, rehmanpolanski_beard_viking, wdg_scruffy_beard | toigo, culturalibre, rehmanpolanski, wdg | CC0 | MakeHuman asset packs pants01 / skirts01 / shoes01 / bodyparts05 |
| Garments: elvs_male_boho_top1, punkduck_lace_up_blouse, elvs_ruffle_sleeve_peasant_blouse_1, mindfront_male_trousers_2, maciekg_leather_boots, punkduck_medieval_boots, punkduck_female_half-boots, punkduck_riding_boots, maciekg_wizard_robe, grinsegold_full_beard | elvs, punkduck, mindfront, maciekg, grinsegold | CC-BY (credit required) | MakeHuman asset packs shirts02 / shirts03 / pants02 / shoes03 / suits03 / bodyparts06 |
| Maud (campaign cast): hair elvs_braid_bun, garment elvs_ladies_apron | Elvaerwyn | CC-BY (credit required) | MakeHuman community asset library (installed via MPFB) |
| Fabric / leather textures (linen, wool, hessian, leather) | Poly Haven | CC0 | https://polyhaven.com |
