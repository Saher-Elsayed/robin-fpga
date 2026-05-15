#!/usr/bin/env bash
# =====================================================================
# ROBIN-FPGA: benchmark sweep across all 14 designs
# Usage: bash scripts/benchmark.sh [versal|agilex]
# =====================================================================
set -euo pipefail

FAMILY="${1:-versal}"
CONFIG="configs/${FAMILY}.yaml"
BENCH="data/benchmarks"
RUNS_BASE="runs/$(date +%Y%m%d_%H%M%S)_${FAMILY}_sweep"

if [[ ! -f "$CONFIG" ]]; then
  echo "ERROR: config $CONFIG not found"
  exit 1
fi

mkdir -p "$RUNS_BASE"
echo "Sweep run -> $RUNS_BASE"
echo "Config:    $CONFIG"
echo "Family:    $FAMILY"
echo

# Discover designs from the manifest (jq required)
if ! command -v jq &>/dev/null; then
  echo "ERROR: jq is required to read the benchmark manifest"
  exit 1
fi

designs=$(jq -r '.designs[].name' "$BENCH/manifest.json")

for d in $designs; do
  design_dir="$BENCH/$(echo "$d" | tr '[:upper:]' '[:lower:]' | tr '-' '_')"
  out_dir="$RUNS_BASE/$d"
  echo "==== $d ===="
  if [[ ! -d "$design_dir" ]]; then
    echo "  skip: $design_dir not present"
    continue
  fi
  python scripts/train.py \
    --config "$CONFIG" \
    --design "$design_dir" \
    --output "$out_dir" \
    --episodes 1200 \
    || echo "  WARNING: $d training failed; continuing"
done

echo
echo "Sweep complete. Per-design outputs under $RUNS_BASE"
