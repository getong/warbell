# UAL2 sword-clip bake

Bakes sword clips from Quaternius' [Universal Animation Library 2](https://quaternius.itch.io/universal-animation-library-2)
(CC0, the Standard pack's `Unreal-Godot/UAL2_Standard.glb` — not checked in) into rig-free
targets for `src/player/anim/ual_sword.rs`, which `src/player/anim/swordplay.rs` solves onto the
footman.

```bash
UAL2_GLB=".../UAL2_Standard.glb" python tools/ual_retarget/bake.py \
  Sword_Regular_A,Sword_Regular_A_Rec,Sword_Regular_B,Sword_Regular_B_Rec,Sword_Regular_C \
  src/player/anim/ual_sword.rs
```

Needs numpy.
