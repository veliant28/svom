#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
PY_BIN="${UTR_PYTHON:-$PROJECT_ROOT/.venv/bin/python}"

if [[ ! -x "$PY_BIN" ]]; then
  echo "Python interpreter not found or not executable: $PY_BIN" >&2
  exit 1
fi
if [[ ! -d "$BACKEND_DIR" ]]; then
  echo "Backend directory not found: $BACKEND_DIR" >&2
  exit 1
fi

# Conservative anti-ban defaults.
export UTR_FORCE_REFRESH=0
export UTR_UNSAFE_ALLOW_FORCE_REFRESH=0
export UTR_CONCURRENCY="${UTR_CONCURRENCY:-1}"
export UTR_RATE_LIMIT_PER_MINUTE="${UTR_RATE_LIMIT_PER_MINUTE:-3}"
export UTR_BATCH_SIZE="${UTR_BATCH_SIZE:-10}"

if [[ "$UTR_CONCURRENCY" != "1" ]]; then
  echo "UTR_CONCURRENCY must be 1 for safe mode. Got: $UTR_CONCURRENCY" >&2
  exit 1
fi

cd "$BACKEND_DIR"

if [[ "$#" -eq 0 ]]; then
  set -- --resolve-only --resolve-limit 10
fi

echo "[utr-safe-run] UTR_FORCE_REFRESH=$UTR_FORCE_REFRESH UTR_CONCURRENCY=$UTR_CONCURRENCY UTR_RATE_LIMIT_PER_MINUTE=$UTR_RATE_LIMIT_PER_MINUTE UTR_BATCH_SIZE=$UTR_BATCH_SIZE"
echo "[utr-safe-run] manage.py import_utr_autocatalog $*"
"$PY_BIN" manage.py import_utr_autocatalog "$@"
