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
APP_ITER_MAX="${UTR_APPLICABILITY_ITER_MAX:-20}"
APP_STABLE_THRESHOLD="${UTR_APPLICABILITY_STABLE_THRESHOLD:-3}"
APP_SLEEP_SECONDS="${UTR_APPLICABILITY_SLEEP_SECONDS:-$SLEEP_SECONDS}"
APP_DETAIL_LIMIT="${UTR_APPLICABILITY_LIMIT:-$BATCH_SIZE}"
KEEP_RUNNING="${UTR_KEEP_RUNNING:-0}"

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
if ! [[ "$APP_ITER_MAX" =~ ^[0-9]+$ ]]; then
  echo "UTR_APPLICABILITY_ITER_MAX must be a non-negative integer, got: $APP_ITER_MAX" >&2
  exit 1
fi
if ! [[ "$APP_STABLE_THRESHOLD" =~ ^[0-9]+$ ]] || [[ "$APP_STABLE_THRESHOLD" -lt 1 ]]; then
  echo "UTR_APPLICABILITY_STABLE_THRESHOLD must be a positive integer, got: $APP_STABLE_THRESHOLD" >&2
  exit 1
fi
if ! [[ "$APP_SLEEP_SECONDS" =~ ^[0-9]+$ ]] || [[ "$APP_SLEEP_SECONDS" -lt 1 ]]; then
  echo "UTR_APPLICABILITY_SLEEP_SECONDS must be a positive integer, got: $APP_SLEEP_SECONDS" >&2
  exit 1
fi
if ! [[ "$APP_DETAIL_LIMIT" =~ ^[0-9]+$ ]]; then
  echo "UTR_APPLICABILITY_LIMIT must be a non-negative integer, got: $APP_DETAIL_LIMIT" >&2
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

applicability_progress() {
  "$PY_BIN" manage.py shell -c "from django.db import connection; from apps.autocatalog.models import UtrArticleDetailMap, UtrDetailCarMap; from apps.catalog.models import Product; product_table=Product._meta.db_table; article_map_table=UtrArticleDetailMap._meta.db_table; car_map_table=UtrDetailCarMap._meta.db_table; sql=f\"\"\"WITH ids AS (SELECT DISTINCT utr_detail_id FROM {product_table} WHERE utr_detail_id IS NOT NULL AND utr_detail_id <> '' AND utr_detail_id ~ '^[0-9]+$' UNION SELECT DISTINCT utr_detail_id FROM {article_map_table} WHERE utr_detail_id <> '' AND utr_detail_id ~ '^[0-9]+$'), covered AS (SELECT DISTINCT utr_detail_id FROM {car_map_table}) SELECT COUNT(*) AS total, COUNT(covered.utr_detail_id) AS with_maps, COUNT(*) - COUNT(covered.utr_detail_id) AS missing FROM ids LEFT JOIN covered ON covered.utr_detail_id = ids.utr_detail_id\"\"\"; cursor=connection.cursor(); cursor.execute(sql); row=cursor.fetchone(); print(row[0], row[1], row[2])" | tail -n 1
}

run_applicability_pass() {
  cmd=("$PY_BIN" manage.py import_utr_autocatalog --batch-size "$BATCH_SIZE" --missing-applicability-only)
  if [[ "$APP_DETAIL_LIMIT" -gt 0 ]]; then
    cmd+=(--limit "$APP_DETAIL_LIMIT")
  fi
  if [[ "$force_refresh_enabled" -eq 1 ]]; then
    cmd+=(--force-refresh)
  fi

  set +e
  out="$("${cmd[@]}" 2>&1)"
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
}

cd "$BACKEND_DIR"
log "start nonstop run (sleep ${SLEEP_SECONDS}s between resolve calls, ${APP_SLEEP_SECONDS}s between applicability calls, applicability_limit=${APP_DETAIL_LIMIT})"

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
app_iter=0
app_stable=0
prev_missing=-1
while true; do
  app_iter=$((app_iter + 1))
  before="$(applicability_progress || true)"
  before_total="$(printf '%s' "$before" | awk '{print $1}')"
  before_done="$(printf '%s' "$before" | awk '{print $2}')"
  before_missing="$(printf '%s' "$before" | awk '{print $3}')"
  if ! [[ "$before_total" =~ ^[0-9]+$ ]] || ! [[ "$before_done" =~ ^[0-9]+$ ]] || ! [[ "$before_missing" =~ ^[0-9]+$ ]]; then
    log "applicability progress parse error before iter=$app_iter; run one guarded pass"
  else
    log "applicability iter=$app_iter before total_detail_ids=$before_total with_maps=$before_done missing_maps=$before_missing"
    if [[ "$before_missing" -eq 0 ]]; then
      log "applicability complete: every known UTR detail_id has compatibility mapping"
      break
    fi
  fi

  run_applicability_pass

  after="$(applicability_progress || true)"
  after_total="$(printf '%s' "$after" | awk '{print $1}')"
  after_done="$(printf '%s' "$after" | awk '{print $2}')"
  after_missing="$(printf '%s' "$after" | awk '{print $3}')"
  if ! [[ "$after_total" =~ ^[0-9]+$ ]] || ! [[ "$after_done" =~ ^[0-9]+$ ]] || ! [[ "$after_missing" =~ ^[0-9]+$ ]]; then
    log "applicability batch pass finished; progress parse error after iter=$app_iter"
  else
    log "applicability iter=$app_iter after total_detail_ids=$after_total with_maps=$after_done missing_maps=$after_missing"
    if [[ "$after_missing" -eq 0 ]]; then
      log "applicability complete: every known UTR detail_id has compatibility mapping"
      break
    fi
    if [[ "$after_missing" -eq "$prev_missing" ]]; then
      app_stable=$((app_stable + 1))
    else
      app_stable=0
    fi
    prev_missing="$after_missing"
    if [[ "$app_stable" -ge "$APP_STABLE_THRESHOLD" ]]; then
      if [[ "$KEEP_RUNNING" == "1" ]]; then
        log "applicability plateau detected, keep-running mode sleeps before next retry"
        app_stable=0
      else
        log "applicability plateau detected; remaining detail_ids likely have empty UTR applicability, cached done state, or repeated provider errors"
        break
      fi
    fi
  fi

  if [[ "$APP_ITER_MAX" -gt 0 ]] && [[ "$app_iter" -ge "$APP_ITER_MAX" ]]; then
    if [[ "$KEEP_RUNNING" == "1" ]]; then
      log "applicability iteration cap reached; keep-running mode resets counter after sleep"
      app_iter=0
      app_stable=0
    else
      log "applicability iteration cap reached"
      break
    fi
  fi

  sleep "$APP_SLEEP_SECONDS"
done
log "applicability batch loop finished"
