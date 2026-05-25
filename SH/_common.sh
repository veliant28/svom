#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

WAIT_FOR_AUTODB="${WAIT_FOR_AUTODB:-120}"
MAX_RETRIES="${MAX_RETRIES:-8}"
RETRY_DELAY_SECONDS="${RETRY_DELAY_SECONDS:-45}"
LIMIT_ROWS="${LIMIT_ROWS:-0}"
BATCH_SIZE_OVERRIDE="${BATCH_SIZE_OVERRIDE:-0}"
PROGRESS_EVERY_OVERRIDE="${PROGRESS_EVERY_OVERRIDE:-0}"
SKIP_TOTAL_COUNT_OVERRIDE="${SKIP_TOTAL_COUNT_OVERRIDE:-}"
FORCE_RECREATE_TABLE="${FORCE_RECREATE_TABLE:-0}"

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

format_duration() {
  local total_seconds="$1"
  if ((total_seconds < 0)); then
    total_seconds=0
  fi
  local days="$((total_seconds / 86400))"
  local hours="$(((total_seconds % 86400) / 3600))"
  local minutes="$(((total_seconds % 3600) / 60))"
  local seconds="$((total_seconds % 60))"
  if ((days > 0)); then
    printf '%dd %02d:%02d:%02d' "$days" "$hours" "$minutes" "$seconds"
  else
    printf '%02d:%02d:%02d' "$hours" "$minutes" "$seconds"
  fi
}

acquire_table_lock() {
  local table="$1"
  local lock_dir="/tmp/svom_autodb_clone_${table}.lock"
  local pid_file="$lock_dir/pid"

  if mkdir "$lock_dir" 2>/dev/null; then
    echo "$$" >"$pid_file"
    printf '%s' "$lock_dir"
    return 0
  fi

  if [[ -f "$pid_file" ]]; then
    local existing_pid
    existing_pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [[ -n "$existing_pid" ]] && kill -0 "$existing_pid" 2>/dev/null; then
      return 1
    fi
  fi

  rm -rf "$lock_dir" >/dev/null 2>&1 || true
  if mkdir "$lock_dir" 2>/dev/null; then
    echo "$$" >"$pid_file"
    printf '%s' "$lock_dir"
    return 0
  fi

  return 1
}

release_table_lock() {
  local lock_dir="$1"
  if [[ -z "$lock_dir" ]]; then
    return 0
  fi
  local pid_file="$lock_dir/pid"
  local owner_pid
  owner_pid="$(cat "$pid_file" 2>/dev/null || true)"
  if [[ "$owner_pid" == "$$" ]]; then
    rm -rf "$lock_dir" >/dev/null 2>&1 || true
  fi
}

is_service_running() {
  local service_name="$1"
  if command -v rg >/dev/null 2>&1; then
    docker compose ps --services --status running | rg -qx "$service_name"
  else
    docker compose ps --services --status running | grep -qx "$service_name"
  fi
}

default_batch_size() {
  local table="$1"
  case "$table" in
    passanger_car_trees|articles)
      echo 20
      ;;
    article_numbers|article_prd|article_cross|article_oe|article_nn|article_li|article_links)
      echo 300
      ;;
    *)
      echo 100
      ;;
  esac
}

default_progress_every() {
  local table="$1"
  case "$table" in
    passanger_car_trees|articles)
      echo 1
      ;;
    *)
      echo 20
      ;;
  esac
}

default_skip_total_count() {
  local table="$1"
  case "$table" in
    articles|article_numbers|article_prd|article_cross|article_oe|article_nn|article_li|article_links)
      echo 1
      ;;
    *)
      echo 0
      ;;
  esac
}

is_retryable_error() {
  local log_file="$1"
  if command -v rg >/dev/null 2>&1; then
    rg -q "(Lost connection to MySQL server during query|Unknown MySQL server host|Auto_DB_Pro remote query failed: 2013|Auto_DB_Pro remote query failed: 2005|quota_paused|max_questions)" "$log_file"
  else
    grep -Eq "(Lost connection to MySQL server during query|Unknown MySQL server host|Auto_DB_Pro remote query failed: 2013|Auto_DB_Pro remote query failed: 2005|quota_paused|max_questions)" "$log_file"
  fi
}

is_skippable_error() {
  local log_file="$1"
  if command -v rg >/dev/null 2>&1; then
    rg -q "(is not allowed for remote access|SELECT command denied|remote query failed: 1142)" "$log_file"
  else
    grep -Eq "(is not allowed for remote access|SELECT command denied|remote query failed: 1142)" "$log_file"
  fi
}

print_state() {
  local table="$1"
  docker compose exec -T backend python manage.py shell -c "from apps.autodb.models import AutoDbSyncState as S; s=S.objects.using('auto_db_pro').filter(source_table='${table}').first(); print((s.status if s else 'none'), (s.processed_rows if s else 0), (s.total_rows if s else 0), (s.last_error or '').replace('\\n',' ')[:140] if s else '')"
}

normalize_resume_state() {
  local table="$1"
  docker compose exec -T backend python manage.py shell -c "from apps.autodb.models import AutoDbSyncState as S
s=S.objects.using('auto_db_pro').filter(source_table='${table}').first()
if s and s.status=='completed' and (s.total_rows or 0)>0 and (s.processed_rows or 0)<(s.total_rows or 0):
 s.status='running'
 s.save(using='auto_db_pro', update_fields=['status','updated_at'])
 print('reopened')
else:
 print('unchanged')" | tail -n 1
}

run_table() {
  local table="$1"

  if ! is_service_running "backend"; then
    echo "Backend service is not running. Start with: docker compose up -d backend" >&2
    exit 1
  fi

  local lock_dir
  if ! lock_dir="$(acquire_table_lock "$table")"; then
    log "table=$table lock_busy another sync instance is already running"
    return 1
  fi
  trap 'release_table_lock "$lock_dir"' RETURN

  local normalize_result
  normalize_result="$(normalize_resume_state "$table")"
  if [[ "$normalize_result" == "reopened" ]]; then
    log "table=$table state_fixed completed->running because processed<total"
  fi

  local batch_size
  local progress_every
  local skip_total_count

  if ((BATCH_SIZE_OVERRIDE > 0)); then
    batch_size="$BATCH_SIZE_OVERRIDE"
  else
    batch_size="$(default_batch_size "$table")"
  fi

  if ((PROGRESS_EVERY_OVERRIDE > 0)); then
    progress_every="$PROGRESS_EVERY_OVERRIDE"
  else
    progress_every="$(default_progress_every "$table")"
  fi

  if [[ -n "$SKIP_TOTAL_COUNT_OVERRIDE" ]]; then
    skip_total_count="$SKIP_TOTAL_COUNT_OVERRIDE"
  else
    skip_total_count="$(default_skip_total_count "$table")"
  fi

  log "table=$table started wait_for_autodb=$WAIT_FOR_AUTODB batch_size=$batch_size progress_every=$progress_every skip_total_count=$skip_total_count force_recreate_table=$FORCE_RECREATE_TABLE"
  log "state_before: $(print_state "$table" | tail -n 1)"

  local cmd=(
    docker compose exec
    -e PYTHONUNBUFFERED=1
    -e AUTODB_PRO_REMOTE_SKIP_TOTAL_COUNT="$skip_total_count"
    -T backend
    python manage.py autodb_clone_sync
    --only "$table"
    --resume
    --wait-for-autodb "$WAIT_FOR_AUTODB"
    --batch-size "$batch_size"
    --progress-every-batches "$progress_every"
  )

  if ((FORCE_RECREATE_TABLE > 0)); then
    cmd+=(--force-recreate-table)
  fi

  if ((LIMIT_ROWS > 0)); then
    cmd+=(--limit "$LIMIT_ROWS")
  fi

  local attempt=0
  while :; do
    local started_at
    started_at="$(date +%s)"
    local tmp_log
    tmp_log="$(mktemp)"

    set +e
    local eta_base_processed=-1
    local eta_base_ts=0
    "${cmd[@]}" 2>&1 | tee "$tmp_log" | while IFS= read -r line; do
      local line_out="$line"
      if [[ "$line" == "[$table] progress "* ]]; then
        local progress_processed
        local progress_total
        if [[ "$line" =~ processed=([0-9]+) ]]; then
          progress_processed="${BASH_REMATCH[1]}"
        else
          progress_processed=""
        fi
        if [[ "$line" =~ total=([0-9]+) ]]; then
          progress_total="${BASH_REMATCH[1]}"
        else
          progress_total=""
        fi
        if [[ -n "$progress_processed" && -n "$progress_total" && "$progress_total" -gt 0 ]]; then
          local now_ts
          now_ts="$(date +%s)"
          if ((eta_base_processed < 0)); then
            eta_base_processed="$progress_processed"
            eta_base_ts="$now_ts"
          else
            local delta_rows="$((progress_processed - eta_base_processed))"
            local delta_sec="$((now_ts - eta_base_ts))"
            if ((delta_rows > 0 && delta_sec > 0)); then
              local remaining="$((progress_total - progress_processed))"
              if ((remaining < 0)); then
                remaining=0
              fi
              local eta_seconds="$(( (remaining * delta_sec + delta_rows - 1) / delta_rows ))"
              local eta_human
              eta_human="$(format_duration "$eta_seconds")"
              line_out="$line eta=$eta_human"
            fi
          fi
        fi
      fi
      if [[ "$line" == "[$table]"* ]]; then
        log "$line_out"
      else
        log "[$table] $line_out"
      fi
    done
    local rc="${PIPESTATUS[0]}"
    set -e

    if ((rc == 0)); then
      local elapsed
      elapsed="$(( $(date +%s) - started_at ))"
      log "table=$table completed elapsed=${elapsed}s"
      log "state_after: $(print_state "$table" | tail -n 1)"
      rm -f "$tmp_log"
      return 0
    fi

    if ((attempt < MAX_RETRIES)) && is_retryable_error "$tmp_log"; then
      attempt="$((attempt + 1))"
      log "table=$table retryable_failure attempt=${attempt}/${MAX_RETRIES} sleep=${RETRY_DELAY_SECONDS}s"
      rm -f "$tmp_log"
      sleep "$RETRY_DELAY_SECONDS"
      continue
    fi

    if is_skippable_error "$tmp_log"; then
      log "table=$table skipped reason=remote_access_restricted"
      log "state_after_skip: $(print_state "$table" | tail -n 1)"
      rm -f "$tmp_log"
      return 0
    fi

    log "table=$table failed non-retryable"
    log "state_after_fail: $(print_state "$table" | tail -n 1)"
    rm -f "$tmp_log"
    return 1
  done
}
