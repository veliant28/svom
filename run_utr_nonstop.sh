#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
PY_BIN="${UTR_PYTHON:-$PROJECT_ROOT/.venv/bin/python}"
SLEEP_SECONDS="${UTR_SLEEP_SECONDS:-60}"
LOG_FILE="${UTR_LOG_FILE:-$PROJECT_ROOT/utr_nonstop.log}"
LOCK_FILE="${UTR_LOCK_FILE:-$PROJECT_ROOT/.utr_nonstop.lock}"
RESOLVE_ITER_MAX="${UTR_RESOLVE_ITER_MAX:-400}"
RESOLVE_STABLE_THRESHOLD="${UTR_RESOLVE_STABLE_THRESHOLD:-25}"
RESOLVE_TAIL_THRESHOLD="${UTR_RESOLVE_TAIL_THRESHOLD:-5}"
BATCH_SIZE="${UTR_BATCH_SIZE:-25}"
FORCE_REFRESH="${UTR_FORCE_REFRESH:-0}"
UNSAFE_FORCE_REFRESH="${UTR_UNSAFE_ALLOW_FORCE_REFRESH:-0}"

if [[ ! -x "$PY_BIN" ]]; then
  echo "Python interpreter not found or not executable: $PY_BIN" >&2
  exit 1
fi
if [[ ! -d "$BACKEND_DIR" ]]; then
  echo "Backend directory not found: $BACKEND_DIR" >&2
  exit 1
fi
if ! [[ "$SLEEP_SECONDS" =~ ^[0-9]+$ ]] || [[ "$SLEEP_SECONDS" -lt 1 ]]; then
  echo "UTR_SLEEP_SECONDS must be a positive integer, got: $SLEEP_SECONDS" >&2
  exit 1
fi
if ! [[ "$BATCH_SIZE" =~ ^[0-9]+$ ]] || [[ "$BATCH_SIZE" -lt 1 ]]; then
  echo "UTR_BATCH_SIZE must be a positive integer, got: $BATCH_SIZE" >&2
  exit 1
fi

mkdir -p "$(dirname "$LOG_FILE")"
touch "$LOG_FILE"

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG_FILE"
}

force_refresh_enabled=0
if [[ "$FORCE_REFRESH" == "1" ]]; then
  if [[ "$UNSAFE_FORCE_REFRESH" != "1" ]]; then
    log "force refresh blocked: set UTR_FORCE_REFRESH=1 and UTR_UNSAFE_ALLOW_FORCE_REFRESH=1 together"
    exit 0
  fi
  force_refresh_enabled=1
fi

if command -v flock >/dev/null 2>&1; then
  exec 9>"$LOCK_FILE"
  if ! flock -n 9; then
    log "skip: another run_utr_nonstop.sh already holds lock $LOCK_FILE"
    exit 0
  fi
else
  LOCK_DIR="${LOCK_FILE}.d"
  if mkdir "$LOCK_DIR" 2>/dev/null; then
    printf '%s\n' "$$" >"$LOCK_DIR/pid"
    trap 'rm -rf "$LOCK_DIR"' EXIT
  else
    holder_pid="$(cat "$LOCK_DIR/pid" 2>/dev/null || true)"
    if [[ "$holder_pid" =~ ^[0-9]+$ ]] && kill -0 "$holder_pid" 2>/dev/null; then
      log "skip: another run_utr_nonstop.sh pid=$holder_pid already holds fallback lock $LOCK_DIR"
      exit 0
    fi
    rm -rf "$LOCK_DIR" 2>/dev/null || true
    if mkdir "$LOCK_DIR" 2>/dev/null; then
      printf '%s\n' "$$" >"$LOCK_DIR/pid"
      trap 'rm -rf "$LOCK_DIR"' EXIT
    else
      log "skip: failed to acquire fallback lock $LOCK_DIR"
      exit 0
    fi
  fi
fi

progress() {
  "$PY_BIN" manage.py shell -c "from apps.autocatalog.services import UtrArticleDetailResolverService; p=UtrArticleDetailResolverService().collect_progress(); print(p.mapped_pairs_resolved, p.mapped_pairs_unresolved)" | tail -n 1
}

cd "$BACKEND_DIR"
log "start nonstop run (sleep ${SLEEP_SECONDS}s between command calls)"

# 1) Retry unresolved pairs with rotating offset.
stable=0
prev_unres=-1
offset=0
for i in $(seq 1 "$RESOLVE_ITER_MAX"); do
  set +e
  out="$("$PY_BIN" manage.py import_utr_autocatalog --resolve-utr-articles --retry-unresolved --resolve-limit "$BATCH_SIZE" --resolve-offset "$offset" --resolve-only 2>&1)"
  cmd_rc=$?
  set -e
  printf '%s\n' "$out" >>"$LOG_FILE"
  if [[ "$out" == *"[utr-lock] skipped_due_to_existing_lock=1"* ]]; then
    log "resolve loop skipped: UTR import lock is already held"
    exit 0
  fi
  if [[ "$out" == *"[utr-guard] skipped_due_to_force_refresh_protection=1"* ]]; then
    log "resolve loop blocked by force-refresh protection"
    exit 0
  fi
  if [[ "$out" == *"[utr-stop] circuit_breaker_open=1"* ]]; then
    log "resolve loop stopped due to UTR circuit breaker; wait cooldown before next run"
    exit 0
  fi
  if [[ "$cmd_rc" -ne 0 ]]; then
    log "resolve command failed with rc=$cmd_rc; stop to avoid aggressive restart"
    exit "$cmd_rc"
  fi

  cur="$(progress || true)"
  cur_res="$(printf '%s' "$cur" | awk '{print $1}')"
  cur_unres="$(printf '%s' "$cur" | awk '{print $2}')"
  if ! [[ "$cur_res" =~ ^[0-9]+$ ]] || ! [[ "$cur_unres" =~ ^[0-9]+$ ]]; then
    log "progress parse error at iter=$i, retry next step"
    sleep "$SLEEP_SECONDS"
    continue
  fi

  log "retry-unresolved iter=$i offset=$offset resolved=$cur_res unresolved=$cur_unres"
  if [[ "$cur_unres" -eq 0 ]]; then
    log "unresolved retry complete"
    break
  fi

  if [[ "$cur_unres" -eq "$prev_unres" ]]; then
    stable=$((stable + 1))
  else
    stable=0
  fi
  prev_unres="$cur_unres"

  offset=$((offset + 1))
  if [[ "$offset" -ge "$cur_unres" ]]; then
    offset=0
  fi

  if [[ "$stable" -ge "$RESOLVE_STABLE_THRESHOLD" ]]; then
    log "unresolved plateau detected, continue to applicability phase"
    break
  fi
  if [[ "$cur_unres" -le 1 ]] && [[ "$stable" -ge "$RESOLVE_TAIL_THRESHOLD" ]]; then
    log "tiny unresolved tail detected (<=1), continue to applicability phase"
    break
  fi
  if [[ "$i" -eq "$RESOLVE_ITER_MAX" ]]; then
    log "unresolved retry loop reached cap"
  fi

  sleep "$SLEEP_SECONDS"
done

# 2) Import applicability with command-level batching and cache-aware resume.
set +e
if [[ "$force_refresh_enabled" -eq 1 ]]; then
  out="$("$PY_BIN" manage.py import_utr_autocatalog --batch-size "$BATCH_SIZE" --force-refresh 2>&1)"
else
  out="$("$PY_BIN" manage.py import_utr_autocatalog --batch-size "$BATCH_SIZE" 2>&1)"
fi
cmd_rc=$?
set -e
printf '%s\n' "$out" >>"$LOG_FILE"
if [[ "$out" == *"[utr-lock] skipped_due_to_existing_lock=1"* ]]; then
  log "applicability pass skipped: UTR import lock is already held"
  exit 0
fi
if [[ "$out" == *"[utr-guard] skipped_due_to_force_refresh_protection=1"* ]]; then
  log "applicability pass blocked by force-refresh protection"
  exit 0
fi
if [[ "$out" == *"[utr-stop] circuit_breaker_open=1"* ]]; then
  log "applicability pass stopped due to UTR circuit breaker; wait cooldown before next run"
  exit 0
fi
if [[ "$cmd_rc" -ne 0 ]]; then
  log "applicability command failed with rc=$cmd_rc; stop to avoid aggressive restart"
  exit "$cmd_rc"
fi
log "applicability batch pass finished"
