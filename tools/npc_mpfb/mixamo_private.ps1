# Rebuild the PRIVATE townsfolk clip set (gitignored assets/npc_private/) from Mixamo FBX exports.
#
#   powershell tools/npc_mpfb/mixamo_private.ps1 [-Fbx <dir>] [-Handoff <dir>] [-Blender <exe>]
#
# Mixamo's licence lets its animations ship inside the game but not be redistributed as files, so neither
# the FBXs nor anything baked from them is committed. Each machine that builds a release runs this once.
#
# 1. Download from mixamo.com (character "X Bot", FBX 2019, WITHOUT skin, 30 fps, keyframe reduction none,
#    "In Place" ticked where offered) and save each as <dir>/<Slot>.fbx:
#      Idle_Loop            Weight Shift Idle               Walk_Loop        Male Standard Walk
#      Jog_Fwd_Loop         Slow Run Forward                Sad_Walk_Loop    Sad Walk (elders amble)
#      Old_Walk_Loop        Slow Old Man Shuffle Walk       Old_Idle_Loop    Old Man Idle
#      Idle_LookAround_Loop Nervously Look Around           Idle_Bored_Loop  Bored
#      Idle_Talking_Loop    General Conversation            Yes              Nodding Head Yes
#      Sitting_Idle_Loop    Sitting In Chair Hands Resting On Thighs
#      Sitting_Enter        Stand To Sit                    Sitting_Exit     Sit To Stand
#      Sitting_Talking_Loop Sitting Talking                 Crouch_Idle_Loop Crouch Idle
#      Sword_Regular_A      Sword And Shield Downward Slash Spell_Simple_Shoot Standing Aim Fire Arrow
#      Farm_Harvest         Digging Hole With Shovel        Death01          Dying Falling Backward
#      PickUp_Table         Picking Up An Object
#    (Mixamo search titles / descriptions; several share a title — pick the description listed.)
#    A slot name replaces the UAL clip of that name in the game; a missing file keeps the UAL clip.
# 2. Run this script: bake_mixamo.py retargets them onto the MPFB rig, export_anims.py writes one
#    animation-only GLB per look (that look's own rig, pelvis travel scaled to its height).
param(
    [string]$Fbx = "C:/Users/skibi/Documents/Codex/downloads/mixamo/fbx",
    [string]$Handoff = "C:/Users/skibi/Documents/Codex/npc_handoff",
    [string]$Blender = "C:/Users/skibi/Documents/Codex/blender/blender-4.5.14-windows-x64/blender.exe"
)
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$repo = Resolve-Path "$here/../.."
$baked = Join-Path (Split-Path $Fbx) "npc_anims_mixamo.blend"
& $Blender -b "$Handoff/npc_anims.blend" --python "$here/bake_mixamo.py" -- $Fbx $baked 2>&1 | Select-String '^P |Error|Traceback'
$looks = 'farmer','woodcutter','miner','guard','archer','villager_m','villager_f1','villager_f2','elder_m','elder_f','boy','girl','priest','merchant'
foreach ($n in $looks) {
    & $Blender -b "$Handoff/npc_cast.blend" --python "$here/export_anims.py" -- $n "$repo/assets/npc_private/npc_${n}_anims.glb" $baked 2>&1 | Select-String '^P |Error|Traceback'
}
& $Blender -b "$Handoff/npc_maud.blend" --python "$here/export_anims.py" -- maud "$repo/assets/npc_private/npc_maud_anims.glb" $baked 2>&1 | Select-String '^P |Error|Traceback'
