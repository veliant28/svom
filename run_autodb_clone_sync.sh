#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

TABLES=(
  manufacturers
  models
  passanger_cars
  passanger_car_attributes
  passanger_car_engines
  passanger_car_trees
  commercial_vehicles
  motorbikes
  engines
  axles
  suppliers
  supplier_details
  suppliers_with_nv_articles
  suppliers_with_nv_linkages
  countries
  country_groups
  languages
  prd
  manufacturers_of_new_linkages
)

STATE_FILE=".autodb_clone_sync.state"
WAIT_FOR_AUTODB=120
BATCH_SIZE=0
LIMIT_ROWS=0
PROGRESS_EVERY=20
FORCE_RECREATE=false
SCHEMA_ONLY=false
DATA_ONLY=false

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

is_service_running() {
  local service_name="$1"
  if command -v rg >/dev/null 2>&1; then
    docker compose ps --services --status running | rg -qx "$service_name"
  else
    docker compose ps --services --status running | grep -qx "$service_name"
  fi
}

usage() {
  cat <<'EOF'
Usage:
  ./run_autodb_clone_sync.sh [options]

Clones Auto_DB_Pro tables from remote DB to local clone with resume support.
Resume works on two levels:
  1) Between tables via local state file (.autodb_clone_sync.state)
  2) Inside each table via `manage.py autodb_clone_sync --resume`

Options:
  --reset                        Reset table sequence state and start from first table
  --from <table>                 Start sequence from given table name
  --state-file <path>            Override state file path
  --wait-for-autodb <seconds>    Wait for local Auto_DB_Pro readiness (default: 120)
  --batch-size <n>               Clone batch size (0 = backend default)
  --limit <n>                    Limit rows per table (0 = no limit)
  --progress-every <n>           Print progress every N batches (default: 20, 0 disables)
  --force-recreate-table         Pass --force-recreate-table to clone command
  --schema-only                  Pass --schema-only to clone command
  --data-only                    Pass --data-only to clone command
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
    --force-recreate-table)
      FORCE_RECREATE=true
      shift
      ;;
    --schema-only)
      SCHEMA_ONLY=true
      shift
      ;;
    --data-only)
      DATA_ONLY=true
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

if [[ "$SCHEMA_ONLY" == true && "$DATA_ONLY" == true ]]; then
  echo "Error: --schema-only and --data-only cannot be used together." >&2
  exit 1
fi

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

if ! is_service_running "backend"; then
  echo "Backend service is not running. Start SVOM first: docker compose up -d backend" >&2
  exit 1
fi

START_INDEX="$(read_state_index)"
TABLE_COUNT="${#TABLES[@]}"

if ! [[ "$START_INDEX" =~ ^[0-9]+$ ]]; then
  START_INDEX=0
fi

if ((START_INDEX >= TABLE_COUNT)); then
  log "All tables already completed (state=$START_INDEX). Use --reset to run again."
  exit 0
fi

RUN_STARTED_AT="$(date +%s)"
log "Clone run started. state_file=$STATE_FILE start_index=$START_INDEX"
log "Tables: ${TABLES[*]}"

for ((i=START_INDEX; i<TABLE_COUNT; i++)); do
  table="${TABLES[$i]}"
  step="$((i + 1))/$TABLE_COUNT"
  started_at="$(date +%s)"

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
  if [[ "$FORCE_RECREATE" == true ]]; then
    cmd+=(--force-recreate-table)
  fi
  if [[ "$SCHEMA_ONLY" == true ]]; then
    cmd+=(--schema-only)
  fi
  if [[ "$DATA_ONLY" == true ]]; then
    cmd+=(--data-only)
  fi

  log "[$step] Start table=$table"
  log "[$step] Command: ${cmd[*]}"
  if "${cmd[@]}" 2>&1 | while IFS= read -r line; do log "[$table] $line"; done; then
    write_state_index "$((i + 1))"
    elapsed="$(( $(date +%s) - started_at ))"
    log "[$step] Done table=$table elapsed=${elapsed}s next_index=$((i + 1))"
  else
    elapsed="$(( $(date +%s) - started_at ))"
    log "[$step] Failed table=$table elapsed=${elapsed}s"
    log "State kept at index=$i. Resume later with: ./run_autodb_clone_sync.sh"
    exit 1
  fi
done

total_elapsed="$(( $(date +%s) - RUN_STARTED_AT ))"
log "Clone run finished successfully. total_elapsed=${total_elapsed}s"
