#!/usr/bin/env bash
# Headless boot smoke test — the "does the game still open without breaking?" guard.
#
# Boots the REAL app (release of the debug binary) under Xvfb + Mesa's software Vulkan
# (llvmpipe) in several states via the built-in `FOREST_SHOT` capture harness. Each state runs
# the full plugin set for ~90 frames (so lighting/IBL settle) and then exits; any system that
# panics at runtime — a broken schedule, a missing resource, a bad despawn — crashes the run and
# fails the test. This catches the class of regressions the compiler can't: a feature that
# compiles but is silently wired wrong (e.g. the sky that stops rendering if `Atmosphere` is put
# back on the camera). Pairs with the GPU-free ECS unit tests (`cargo test`).
#
# Usage:  ./scripts/smoke_test.sh           (builds if needed, then runs all states)
# Needs:  the headless stack from the visual-debug-cloud skill —
#           sudo apt-get install -y xvfb mesa-vulkan-drivers libgl1-mesa-dri libegl1 \
#                                   libxkbcommon-x11-0
#
# Each shot is ~3-5 min on llvmpipe; run states sequentially (llvmpipe saturates all cores).

set -uo pipefail
cd "$(dirname "$0")/.." || exit 2
ROOT="$(pwd)"
BIN="$ROOT/target/debug/tileworld_bevy_forest"
OUT="$(mktemp -d)"
export BEVY_ASSET_ROOT="$ROOT"   # so assets/ resolves regardless of the binary's location

if [[ ! -x "$BIN" ]]; then
  echo "[smoke] building debug binary…"
  cargo build || { echo "[smoke] BUILD FAILED"; exit 1; }
fi

# state-label : extra FOREST_* env that stages it
#  - menu     : the title screen (heavy UI text — Parley render path)
#  - day      : default gameplay boot (Playing), midday sky (atmosphere + post passes + HUD)
#  - siege    : a night wave with defenses armed (combat fx, firelight, moon, invader AI)
STATES=(
  "menu:FOREST_MENU=1"
  "day:FOREST_TIME=0.25"
  "siege:FOREST_WAVE=1 FOREST_DEFEND=1 FOREST_TIME=0.78"
)

fail=0
for entry in "${STATES[@]}"; do
  label="${entry%%:*}"
  envs="${entry#*:}"
  png="$OUT/$label.png"
  echo "[smoke] booting state '$label' ($envs)…"
  log="$OUT/$label.log"
  # shellcheck disable=SC2086
  if env $envs FOREST_SHOT="$png" \
        timeout 570 xvfb-run -a -s "-screen 0 1280x720x24" "$BIN" >"$log" 2>&1; then
    # Survived to exit. Require a non-trivial PNG (a blank/early-exit frame is tiny).
    sz=$(stat -c%s "$png" 2>/dev/null || echo 0)
    if [[ "$sz" -gt 50000 ]]; then
      echo "[smoke]   ✅ '$label' booted, ran, and rendered ($sz bytes)"
    else
      echo "[smoke]   ❌ '$label' exited 0 but produced no real frame ($sz bytes)"; fail=1
    fi
  else
    echo "[smoke]   ❌ '$label' crashed / timed out:"
    grep -iE "panic|panicked|thread '.*' panicked" "$log" | head -5 | sed 's/^/[smoke]      /'
    fail=1
  fi
done

if [[ "$fail" -eq 0 ]]; then
  echo "[smoke] ALL STATES PASSED — the game opens and runs."
else
  echo "[smoke] FAILURES above — artifacts in $OUT"
fi
exit "$fail"
