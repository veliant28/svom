#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"
# Continue from saved cursor between runs (no table recreate).
FORCE_RECREATE_TABLE=0
# Skip expensive remote COUNT(*) for faster startup on huge table.
SKIP_TOTAL_COUNT_OVERRIDE=1
# Aggressive batch for best rows/query ratio under remote query quota.
BATCH_SIZE_OVERRIDE=10000
# Keep per-batch progress in logs.
PROGRESS_EVERY_OVERRIDE=1
run_table "passanger_car_trees"
