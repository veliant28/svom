#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

TABLES=(articles article_numbers article_oe article_prd)
STATE_FILE=".autodb_priority_clone.state"
WAIT_FOR_AUTODB=120
BATCH_SIZE=0
LIMIT_ROWS=0
PROGRESS_EVERY=20
ALIGN_STATE_WITH_COUNT=false

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

usage() {
  cat <<'EOF'
Usage:
  ./autodb_priority_clone.sh [options]

Copies priority AutoDB tables in order with resume support:
  1) articles
  2) article_numbers
  3) article_oe
  4) article_prd

Options:
  --reset                        Reset sequence state and start from first table
  --from <table>                 Start sequence from table name
  --state-file <path>            Override state file path (default: .autodb_priority_clone.state)
  --wait-for-autodb <seconds>    Wait for local Auto_DB_Pro readiness (default: 120)
  --batch-size <n>               Sync batch size (0 = backend default)
  --limit <n>                    Limit rows per table (0 = no limit)
  --progress-every <n>           Progress print every N batches (default: 20, 0 disables)
  --align-state                  Enable auto-align of sync state by local table row count
  -h, --help                     Show this help
EOF
}

table_index() {
  local table="$1"
  local i
  for i in "${!TABLES[@]}"; do
    if [[ "${TABLES[$i]}" == "$table" ]]; then
      echo "$i"
      return 0
    fi
  done
  return 1
}

read_state_index() {
  if [[ ! -f "$STATE_FILE" ]]; then
    echo 0
    return 0
  fi
  local raw
  raw="$(tr -d '[:space:]' < "$STATE_FILE" 2>/dev/null || true)"
  if [[ "$raw" =~ ^[0-9]+$ ]]; then
    echo "$raw"
  else
    echo 0
  fi
}

write_state_index() {
  local idx="$1"
  printf '%s\n' "$idx" > "$STATE_FILE"
}

align_state_for_table() {
  local table="$1"
  if [[ "$ALIGN_STATE_WITH_COUNT" != true ]]; then
    return 0
  fi
  local payload
  payload="$(docker compose exec -T -e TABLE_NAME="$table" backend python manage.py shell <<'PY'
import os
from django.db import connections
from apps.autodb.models import AutoDbSyncState

t = os.environ.get("TABLE_NAME", "").strip()
tn = t.replace('"', "")

cursor = connections["auto_db_pro"].cursor()
cursor.execute(f'select count(*) from "{tn}"')
cnt = int(cursor.fetchone()[0])

cursor.execute(
    """
    SELECT kcu.column_name
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
      ON tc.constraint_name = kcu.constraint_name
     AND tc.table_schema = kcu.table_schema
    WHERE tc.table_schema = current_schema()
      AND tc.table_name = %s
      AND tc.constraint_type = 'PRIMARY KEY'
    ORDER BY kcu.ordinal_position
    LIMIT 1
    """,
    [tn],
)
row = cursor.fetchone()
pk_col = row[0] if row else None
pk_max = None
if pk_col:
    cursor.execute(f'select max("{pk_col.replace("\"", "")}") from "{tn}"')
    raw = cursor.fetchone()[0]
    if raw is not None:
        pk_max = int(raw)

s, _ = AutoDbSyncState.objects.using("auto_db_pro").get_or_create(source_table=t)
cur = int(s.last_offset or 0)
proc = int(s.processed_rows or 0)
target = max(cur, proc, cnt)
changed = (target != cur) or (target != proc) or (s.status == "running") or (pk_max is not None and int(s.last_pk or 0) != pk_max)
s.last_offset = target
s.processed_rows = target
s.last_cursor = f"offset:{target}"
s.last_pk = pk_max
s.status = "pending"
s.save(using="auto_db_pro")
print({"table": t, "count": cnt, "state_offset": target, "pk_col": pk_col, "pk_max": pk_max, "changed": changed})
PY
 2>&1)" || {
    log "State align skipped for table=$table (unable to read/adjust state): $payload"
    return 0
  }
  log "State align: $payload"
}

RESET=false
FROM_TABLE=""

while (($#)); do
  case "$1" in
    --reset)
      RESET=true
      shift
      ;;
    --from)
      FROM_TABLE="${2:-}"
      shift 2
      ;;
    --state-file)
      STATE_FILE="${2:-}"
      shift 2
      ;;
    --wait-for-autodb)
      WAIT_FOR_AUTODB="${2:-0}"
      shift 2
      ;;
    --batch-size)
      BATCH_SIZE="${2:-0}"
      shift 2
      ;;
    --limit)
      LIMIT_ROWS="${2:-0}"
      shift 2
      ;;
    --progress-every)
      PROGRESS_EVERY="${2:-0}"
      shift 2
      ;;
    --align-state)
      ALIGN_STATE_WITH_COUNT=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ "$RESET" == true ]]; then
  write_state_index 0
  log "State reset: $STATE_FILE -> 0"
fi

if [[ -n "$FROM_TABLE" ]]; then
  if ! idx="$(table_index "$FROM_TABLE")"; then
    echo "Unknown table for --from: $FROM_TABLE" >&2
    echo "Allowed: ${TABLES[*]}" >&2
    exit 1
  fi
  write_state_index "$idx"
  log "Forced start from table=$FROM_TABLE (index=$idx)"
fi

START_INDEX="$(read_state_index)"
TABLE_COUNT="${#TABLES[@]}"

if ! [[ "$START_INDEX" =~ ^[0-9]+$ ]]; then
  START_INDEX=0
fi

if ((START_INDEX >= TABLE_COUNT)); then
  log "All priority tables are already completed (state=$START_INDEX). Use --reset to run again."
  exit 0
fi

RUN_STARTED_AT="$(date +%s)"
log "Priority clone run started. state_file=$STATE_FILE start_index=$START_INDEX tables=${TABLES[*]}"

for ((i=START_INDEX; i<TABLE_COUNT; i++)); do
  table="${TABLES[$i]}"
  step="$((i + 1))/$TABLE_COUNT"
  started_at="$(date +%s)"

  log "[$step] Starting table=$table"
  align_state_for_table "$table"

  cmd=(docker compose exec -T backend python manage.py autodb_clone_sync --only "$table" --resume)

  if ((WAIT_FOR_AUTODB > 0)); then
    cmd+=(--wait-for-autodb "$WAIT_FOR_AUTODB")
  fi
  if ((BATCH_SIZE > 0)); then
    cmd+=(--batch-size "$BATCH_SIZE")
  fi
  if ((LIMIT_ROWS > 0)); then
    cmd+=(--limit "$LIMIT_ROWS")
  fi
  if ((PROGRESS_EVERY > 0)); then
    cmd+=(--progress-every-batches "$PROGRESS_EVERY")
  fi

  log "[$step] Command: ${cmd[*]}"
  if "${cmd[@]}" 2>&1 | while IFS= read -r line; do log "$line"; done; then
    write_state_index "$((i + 1))"
    elapsed="$(( $(date +%s) - started_at ))"
    log "[$step] Done table=$table elapsed=${elapsed}s next_index=$((i + 1))"
  else
    log "[$step] Failed table=$table. Resume later from same table (state kept at index=$i)."
    exit 1
  fi
done

total_elapsed="$(( $(date +%s) - RUN_STARTED_AT ))"
log "Priority clone run finished successfully. elapsed=${total_elapsed}s"
