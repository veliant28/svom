#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
PY_BIN="${UTR_PYTHON:-$PROJECT_ROOT/.venv/bin/python}"
SLEEP_SECONDS="${UTR_APPLICABILITY_SLEEP_SECONDS:-${UTR_SLEEP_SECONDS:-60}}"
BATCH_SIZE="${UTR_APPLICABILITY_BATCH_SIZE:-${UTR_BATCH_SIZE:-20}}"
DETAIL_LIMIT="${UTR_APPLICABILITY_LIMIT:-$BATCH_SIZE}"
ITER_MAX="${UTR_APPLICABILITY_ITER_MAX:-0}"
LOG_FILE="${UTR_APPLICABILITY_LOG_FILE:-$PROJECT_ROOT/utr_applicability_nonstop.log}"
LOCK_FILE="${UTR_APPLICABILITY_LOCK_FILE:-$PROJECT_ROOT/.utr_applicability_nonstop.lock}"
RUN_LOCK_KEY="${UTR_APPLICABILITY_RUN_LOCK_KEY:-804721453}"

if [[ ! -x "$PY_BIN" ]]; then
  echo "Python interpreter not found or not executable: $PY_BIN" >&2
  exit 1
fi
if [[ ! -d "$BACKEND_DIR" ]]; then
  echo "Backend directory not found: $BACKEND_DIR" >&2
  exit 1
fi
if ! [[ "$SLEEP_SECONDS" =~ ^[0-9]+$ ]] || [[ "$SLEEP_SECONDS" -lt 1 ]]; then
  echo "UTR_APPLICABILITY_SLEEP_SECONDS must be a positive integer, got: $SLEEP_SECONDS" >&2
  exit 1
fi
if ! [[ "$BATCH_SIZE" =~ ^[0-9]+$ ]] || [[ "$BATCH_SIZE" -lt 1 ]]; then
  echo "UTR_APPLICABILITY_BATCH_SIZE must be a positive integer, got: $BATCH_SIZE" >&2
  exit 1
fi
if ! [[ "$DETAIL_LIMIT" =~ ^[0-9]+$ ]]; then
  echo "UTR_APPLICABILITY_LIMIT must be a non-negative integer, got: $DETAIL_LIMIT" >&2
  exit 1
fi
if ! [[ "$ITER_MAX" =~ ^[0-9]+$ ]]; then
  echo "UTR_APPLICABILITY_ITER_MAX must be a non-negative integer, got: $ITER_MAX" >&2
  exit 1
fi
if ! [[ "$RUN_LOCK_KEY" =~ ^[0-9]+$ ]]; then
  echo "UTR_APPLICABILITY_RUN_LOCK_KEY must be a positive integer, got: $RUN_LOCK_KEY" >&2
  exit 1
fi

mkdir -p "$(dirname "$LOG_FILE")"
touch "$LOG_FILE"

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG_FILE"
}

if command -v flock >/dev/null 2>&1; then
  exec 9>"$LOCK_FILE"
  if ! flock -n 9; then
    log "skip: another applicability runner already holds $LOCK_FILE"
    exit 0
  fi
fi

progress() {
  "$PY_BIN" manage.py shell -c "from django.db import connection; from apps.autocatalog.models import UtrArticleDetailMap, UtrDetailCarMap; from apps.catalog.models import Product; p=Product._meta.db_table; a=UtrArticleDetailMap._meta.db_table; m=UtrDetailCarMap._meta.db_table; sql=f\"\"\"WITH ids AS (SELECT DISTINCT utr_detail_id FROM {p} WHERE utr_detail_id IS NOT NULL AND utr_detail_id <> '' AND utr_detail_id ~ '^[0-9]+$' UNION SELECT DISTINCT utr_detail_id FROM {a} WHERE utr_detail_id <> '' AND utr_detail_id ~ '^[0-9]+$') SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE EXISTS (SELECT 1 FROM {m} map WHERE map.utr_detail_id = ids.utr_detail_id)) AS done, COUNT(*) FILTER (WHERE NOT EXISTS (SELECT 1 FROM {m} map WHERE map.utr_detail_id = ids.utr_detail_id)) AS missing FROM ids\"\"\"; cursor=connection.cursor(); cursor.execute(sql); row=cursor.fetchone(); print(row[0], row[1], row[2])" | tail -n 1
}

run_applicability_pass() {
  cmd=(manage.py import_utr_autocatalog --missing-applicability-only --batch-size "$BATCH_SIZE")
  if [[ "$DETAIL_LIMIT" -gt 0 ]]; then
    cmd+=(--limit "$DETAIL_LIMIT")
  fi
  if [[ "$app_offset" -gt 0 ]]; then
    cmd+=(--offset "$app_offset")
  fi

  set +e
  out="$(UTR_SINGLE_RUN_LOCK_KEY="$RUN_LOCK_KEY" "$PY_BIN" "${cmd[@]}" 2>&1)"
  cmd_rc=$?
  set -e
  printf '%s\n' "$out" >>"$LOG_FILE"
  if [[ "$out" == *"[utr-lock] skipped_due_to_existing_lock=1"* ]]; then
    log "applicability skipped: import lock is already held"
    return 0
  fi
  if [[ "$out" == *"[utr-guard] skipped_due_to_force_refresh_protection=1"* ]]; then
    log "applicability blocked by force-refresh protection"
    return 0
  fi
  if [[ "$out" == *"[utr-stop] circuit_breaker_open=1"* ]]; then
    log "applicability stopped by UTR circuit breaker; sleeping before retry"
    return 0
  fi
  if [[ "$cmd_rc" -ne 0 ]]; then
    log "applicability failed rc=$cmd_rc; sleeping before retry"
    return "$cmd_rc"
  fi
  return 0
}

cd "$BACKEND_DIR"
"$PY_BIN" manage.py shell -c "from django.core.cache import cache; cache.set('utr:runner:cache_check', '1', timeout=30); assert cache.get('utr:runner:cache_check') == '1'; print('shared-cache-ok')" >/dev/null
log "start applicability runner batch_size=${BATCH_SIZE} limit=${DETAIL_LIMIT} sleep=${SLEEP_SECONDS}s lock_key=${RUN_LOCK_KEY} iter_max=${ITER_MAX} mode=missing-applicability-only"

iter=0
app_offset=0
while true; do
  iter=$((iter + 1))
  before="$(progress || true)"
  log "applicability iter=$iter progress before total_done_missing=$before"

  run_applicability_pass || true

  after="$(progress || true)"
  log "applicability iter=$iter progress after total_done_missing=$after"
  missing="$(printf '%s' "$after" | awk '{print $3}')"
  if [[ "$DETAIL_LIMIT" -gt 0 ]] && [[ "$missing" =~ ^[0-9]+$ ]] && [[ "$missing" -gt 0 ]]; then
    app_offset=$((app_offset + DETAIL_LIMIT))
    if [[ "$app_offset" -ge "$missing" ]]; then
      app_offset=0
    fi
    log "applicability next_offset=$app_offset"
  fi
  if [[ "$ITER_MAX" -gt 0 ]] && [[ "$iter" -ge "$ITER_MAX" ]]; then
    log "applicability iteration cap reached"
    break
  fi
  sleep "$SLEEP_SECONDS"
done
