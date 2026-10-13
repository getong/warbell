# Realistic NPC models + animations — handoff

Status: **content exists only as Blender files; nothing is wired into the game.** A follow-up agent has to
bake/export it and integrate it. Everything below lives OUTSIDE git in
`C:/Users/skibi/Documents/Codex/npc_handoff/` (373 MB; copy of the working files), scripts are also in
`tools/npc_mpfb/` (committed locally, not pushed).

## Where things are
| What | Path |
|---|---|
| 14 characters (Blender 4.5 .blend) | `npc_handoff/npc_cast.blend` — one armature per person, object name = role, custom prop `npc` |
| 87 animations as Blender Actions | `npc_handoff/npc_anims.blend` — actions `NPC_<clip>` on `REF_RIG`, fake-user, 30 fps, keys start at frame 1 |
| Showcase renders | `npc_handoff/npc_town.mp4` (town), `bartender_anims.mp4` (single hand-made woman) |
| Build scripts | `npc_handoff/*.py` (`npc_cast.py` = cast spec, `bake_anims.py`, `town_film.py`, `mpfb_cast.py`) |
| Fabric detail maps used by the cloth shader | `npc_handoff/fabric/*_detail.png` |
| Game textures decoded from DDS (for Blender) | `npc_handoff/gametex/` |
| Raw downloads (never executed) | `C:/Users/skibi/Documents/Codex/downloads/{oga_bartender,ual1,ual2,mpfb,mh_system_assets,mh_packs}` |
| MPFB assets installed into | `%APPDATA%/Blender Foundation/Blender/4.5/extensions/.user/user_default/mpfb/data` |
| Blender | `C:/Users/skibi/Documents/Codex/blender/blender-4.5.14-windows-x64/blender.exe` (MPFB 2.0.18 extension installed in its user config) |

Caveat: the `.blend`s reference external image files by absolute path (MPFB skins/hair under the MPFB data dir,
Poly Haven textures under `Documents/Codex/polyhaven_src`, `fabric/`). Open them on this machine, or pack
(`File > External Data > Pack`) before moving them.

## Characters (`npc_cast.blend`)
Made with MPFB (MakeHuman) macro sliders, rig `game_engine`, ~1.5-1.8 m, feet at z = 0, metres, +Y forward, Z up.
Names: farmer, woodcutter, miner, guard, archer, villager_m, villager_f1, villager_f2, elder_m, elder_f, boy, girl,
priest, merchant. Each = basemesh (skin: MPFB "ENHANCED_SSS" node group) + eyes/eyebrows/lashes/hair (MakeHuman
materials) + garments (`mhclo` assets re-materialled by `npc_cast.fabric_mat`: Poly Haven detail + procedural dye
blotches, hem mud, sheen). Garments are plain stock MakeHuman community clothes (tunic, wool trousers, skirt, blouse,
boots, robe); **no armour, hoods, aprons, helmets, tool/weapon props** — guard and archer read as civilians.
Hair is the stock MakeHuman set (looks a bit glossy).

All 14 share the SAME 53-bone skeleton (bone names below) with different proportions, so any animation plays on any of them.

Bones: Root, pelvis, spine_01-03, neck_01, head, clavicle/upperarm/lowerarm/hand_{l,r}, {index,middle,pinky,ring}_01-03_{l,r},
thumb_01-03_{l,r}, thigh/calf/foot/ball_{l,r}. (Unreal-mannequin naming; `_l` = character's left, -X in game terms to be checked.)

## Animations (`npc_anims.blend`)
87 Quaternius Universal Animation Library clips (UAL1 + UAL2 Standard, CC0), retargeted onto the rig above by
`bake_anims.py` (world-space delta + bone-direction swing retarget, ground-contact corrected per clip, quaternion
continuity fixed). Only `pose.bones[...].rotation_quaternion` for every bone and `pose.bones["pelvis"].location` are keyed;
pelvis location is in **metres of a 1.7 m reference body** — scale by character height. In-place (root motion `_RM` clips
still have no travel). Custom props on each action: `frames`, `src` (ual1/ual2). Loops are the `*_Loop` clips (+ `Idle_*`).

Clips most relevant to the game's `BipedDrive` states (src/biped.rs, src/player/anim/village.rs):
- idle/walk/run: `Idle_Loop`, `Walk_Loop`, `Walk_Formal_Loop`, `Jog_Fwd_Loop`, `Sprint_Loop`
- work: `Farm_PlantSeed`, `Farm_Harvest`, `Farm_Watering`, `TreeChopping_Loop`, `Fixing_Kneeling`, `Interact`, `PickUp_Table`, `Chest_Open`
- carry/pull: `Walk_Carry_Loop`, `Push_Loop`
- sit: `Sitting_Enter`, `Sitting_Idle_Loop`, `Sitting_Talking_Loop`, `Sitting_Exit`
- village-life: `Idle_Talking_Loop`, `Idle_FoldArms_Loop`, `Idle_Rail_Call`, `Idle_No_Loop`, `Yes`, `Dance_Loop`, `Idle_Lantern_Loop`, `Consume`
- combat: `Sword_Idle`, `Sword_Attack`, `Sword_Regular_A/B/C/Combo`, `Sword_Block`, `Punch_*`, `Hit_Chest`, `Hit_Head`, `Hit_Knockback`, `Death01`, `Roll`
- no clip exists for: bow draw/loose, hammering (smith), mining swing, sweeping, laundry, haggling — need extra downloads or keep the procedural poses for those.
Full list (name:frames) is the action list in the file.

## Why it is not in the game yet (read before integrating)
1. The game has **no glTF-skin path**. People are built from `people.glb` pieces on a 14-joint rig
   (`tools/blender_forest/people.py`; `src/peasant_model.rs`, `src/biped.rs`): skin weights are packed into UV0/UV1,
   `creature.wgsl` colours by vertex-colour regions + triplanar detail layers; there is **no UV-mapped albedo path**,
   and animation is procedural (`animate_biped` writing joint rotations), not clips.
2. The new characters use a 53-bone rig with textured skin; the game rig has 14 joints (hips, torso, neck, head, 2×shoulder, 2×elbow, 2×hip, 2×knee, 2×foot).
3. Materials here are Blender node graphs (SSS skin node group, procedural cloth). glTF export needs per-character
   texture baking (albedo + normal + ORM atlas) first.

Sensible integration options (pick one, don't mix):
- A. Add a standard Bevy skinned-glTF NPC path (new material with UV albedo/normal/ORM, `AnimationGraph` from the baked clips), use it for townsfolk only. Keeps the old rig for orks/hero.
- B. Keep the 14-joint procedural runtime: bake the new meshes' weights down to the 14 joints (people.py contract) and add UV albedo to the creature shader; animations stay procedural (clips would have to be sampled into `Pose`).
Option A matches the content as it stands.

Needed work either way: bake each character (skin + garments + hair) to textures, decimate (basemesh ~13k tris, eyes/hair/clothes extra → budget LODs), export one GLB per character + one animation GLB (or clips baked to `.bin` like `assets/models/footman.bin`), add the role→clip mapping, resets/save-game are unaffected (cosmetic). Scale: game villager ≈ 1.46 u, hero ≈ 1.14 u, door ≈ 1.4 u (the film used a human scale of 0.72 u/m).

## Licences (credits already in `assets/CREDITS.md`)
MakeHuman system assets, Bartender (CDmir/TinyWorlds), Quaternius UAL, Poly Haven: CC0. Community garments/beards: some CC-BY
(credit authors, listed in CREDITS.md). MPFB add-on itself is GPL-3 (tool only, output is CC0/CC-BY per asset).

## Known issues in the showcase
Dark/misty last shot and horizon; sparse grass; bench/sit alignment approximate; simple clothes; no hand props; hair glossy.
