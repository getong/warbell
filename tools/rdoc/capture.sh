#!/bin/bash
# Capture one GPU frame with RenderDoc (portable build, Vulkan layer enabled via env — no admin).
#   RDOC_DIR=<renderdoc dir> tools/rdoc/capture.sh <out_template> [extra FOREST_* env ...]
# Builds with `--features renderdoc`, runs the village perftest scene and captures one frame
# FOREST_RDOC (default 20) seconds after WorldReady. See src/rdoc.rs.
set -e
cd "$(dirname "$0")/../.."
RD="${RDOC_DIR:-/c/Users/skibi/Documents/Codex/tools/renderdoc/RenderDoc_1.46_64}"
OUT="${1:-target/rdoc/cap}"; shift || true
mkdir -p "$(dirname "$OUT")"
WIN_RD="$(cygpath -w "$RD")"
env PATH="$RD:$PATH" VK_LAYER_PATH="$WIN_RD" VK_INSTANCE_LAYERS=VK_LAYER_RENDERDOC_Capture \
    ENABLE_VULKAN_RENDERDOC_CAPTURE=1 FOREST_RDOC="${FOREST_RDOC:-20}" FOREST_RDOC_PATH="$OUT" \
    FOREST_PERFTEST="${FOREST_PERFTEST:-40}" FOREST_NOVSYNC=1 FOREST_TPS=1 FOREST_IMMORTAL=1 "$@" \
    cargo run -q --features renderdoc 2>&1 | sed 's/\x1b\[[0-9;]*m//g' | grep -E "RDOC|RenderDoc|panicked|PERF_SUMMARY|Validation" || true
ls -la "$(dirname "$OUT")"
