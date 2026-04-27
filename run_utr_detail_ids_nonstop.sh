#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
PY_BIN="${UTR_PYTHON:-$PROJECT_ROOT/.venv/bin/python}"
SLEEP_SECONDS="${UTR_DETAIL_SLEEP_SECONDS:-${UTR_SLEEP_SECONDS:-60}}"
BATCH_SIZE="${UTR_DETAIL_BATCH_SIZE:-${UTR_BATCH_SIZE:-25}}"
ITER_MAX="${UTR_DETAIL_ITER_MAX:-0}"
RETRY_EVERY="${UTR_DETAIL_RETRY_EVERY:-5}"
LOG_FILE="${UTR_DETAIL_LOG_FILE:-$PROJECT_ROOT/utr_detail_ids_nonstop.log}"
LOCK_FILE="${UTR_DETAIL_LOCK_FILE:-$PROJECT_ROOT/.utr_detail_ids_nonstop.lock}"
RUN_LOCK_KEY="${UTR_DETAIL_RUN_LOCK_KEY:-804721452}"

if [[ ! -x "$PY_BIN" ]]; then
  echo "Python interpreter not found or not executable: $PY_BIN" >&2
  exit 1
fi
if [[ ! -d "$BACKEND_DIR" ]]; then
  echo "Backend directory not found: $BACKEND_DIR" >&2
  exit 1
fi
if ! [[ "$SLEEP_SECONDS" =~ ^[0-9]+$ ]] || [[ "$SLEEP_SECONDS" -lt 1 ]]; then
  echo "UTR_DETAIL_SLEEP_SECONDS must be a positive integer, got: $SLEEP_SECONDS" >&2
  exit 1
fi
if ! [[ "$BATCH_SIZE" =~ ^[0-9]+$ ]] || [[ "$BATCH_SIZE" -lt 1 ]]; then
  echo "UTR_DETAIL_BATCH_SIZE must be a positive integer, got: $BATCH_SIZE" >&2
  exit 1
fi
if ! [[ "$ITER_MAX" =~ ^[0-9]+$ ]]; then
  echo "UTR_DETAIL_ITER_MAX must be a non-negative integer, got: $ITER_MAX" >&2
  exit 1
fi
if ! [[ "$RETRY_EVERY" =~ ^[0-9]+$ ]] || [[ "$RETRY_EVERY" -lt 1 ]]; then
  echo "UTR_DETAIL_RETRY_EVERY must be a positive integer, got: $RETRY_EVERY" >&2
  exit 1
fi
if ! [[ "$RUN_LOCK_KEY" =~ ^[0-9]+$ ]]; then
  echo "UTR_DETAIL_RUN_LOCK_KEY must be a positive integer, got: $RUN_LOCK_KEY" >&2
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
    log "skip: another detail_id runner already holds $LOCK_FILE"
    exit 0
  fi
fi

progress() {
  "$PY_BIN" manage.py shell -c "from apps.autocatalog.services import UtrArticleDetailResolverService; p=UtrArticleDetailResolverService().collect_progress(); print(p.mapped_pairs_resolved, p.mapped_pairs_unresolved, p.raw_pairs_unresolved_total)" | tail -n 1
}

run_resolve_pass() {
  label="$1"
  shift
  set +e
  out="$(UTR_SINGLE_RUN_LOCK_KEY="$RUN_LOCK_KEY" UTR_RESOLVE_BATCH_SIZE="$BATCH_SIZE" "$PY_BIN" manage.py import_utr_autocatalog "$@" 2>&1)"
  cmd_rc=$?
  set -e
  printf '%s\n' "$out" >>"$LOG_FILE"
  if [[ "$out" == *"[utr-lock] skipped_due_to_existing_lock=1"* ]]; then
    log "$label skipped: detail_id import lock is already held"
    return 0
  fi
  if [[ "$out" == *"[utr-guard] skipped_due_to_force_refresh_protection=1"* ]]; then
    log "$label blocked by force-refresh protection"
    return 0
  fi
  if [[ "$out" == *"[utr-stop] circuit_breaker_open=1"* ]]; then
    log "$label stopped by UTR circuit breaker; sleeping before retry"
    return 0
  fi
  if [[ "$cmd_rc" -ne 0 ]]; then
    log "$label failed rc=$cmd_rc; sleeping before retry"
    return "$cmd_rc"
  fi
  return 0
}

cd "$BACKEND_DIR"
"$PY_BIN" manage.py shell -c "from django.core.cache import cache; cache.set('utr:runner:cache_check', '1', timeout=30); assert cache.get('utr:runner:cache_check') == '1'; print('shared-cache-ok')" >/dev/null
log "start detail_id runner batch_size=${BATCH_SIZE} sleep=${SLEEP_SECONDS}s lock_key=${RUN_LOCK_KEY} iter_max=${ITER_MAX} retry_every=${RETRY_EVERY}"

iter=0
while true; do
  iter=$((iter + 1))
  before="$(progress || true)"
  log "detail_id iter=$iter progress before: resolved_unresolved_raw=$before"

  run_resolve_pass "resolve-new" \
    --resolve-utr-articles \
    --resolve-only \
    --resolve-limit "$BATCH_SIZE" || true

  if (( iter % RETRY_EVERY == 0 )); then
    run_resolve_pass "retry-unresolved" \
      --resolve-utr-articles \
      --retry-unresolved \
      --resolve-only \
      --resolve-limit "$BATCH_SIZE" || true
  else
    log "retry-unresolved skipped: iter=$iter retry_every=$RETRY_EVERY"
  fi

  after="$(progress || true)"
  log "detail_id iter=$iter progress after: resolved_unresolved_raw=$after"
  if [[ "$ITER_MAX" -gt 0 ]] && [[ "$iter" -ge "$ITER_MAX" ]]; then
    log "detail_id iteration cap reached"
    break
  fi
  sleep "$SLEEP_SECONDS"
done
