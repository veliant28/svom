#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT_DIR/compose.yaml}"
BATCH_SIZE="${BATCH_SIZE:-5000}"
WAIT_FOR_AUTODB="${WAIT_FOR_AUTODB:-30}"
PROGRESS_EVERY_BATCHES="${PROGRESS_EVERY_BATCHES:-50}"
RESUME="${RESUME:-1}"
DRY_RUN="${DRY_RUN:-0}"
INCLUDE_HEAVY_TREES="${INCLUDE_HEAVY_TREES:-0}"
ENSURE_INDEXES="${ENSURE_INDEXES:-1}"
SCOPE="${SCOPE:-all}" # all|commercial|passenger

PASSENGER_BASE_TABLES=(
  manufacturers
  models
  engines
  axles
  motorbikes
  passanger_cars
  passanger_car_attributes
  passanger_car_engines
)

COMMERCIAL_BASE_TABLES=(
  manufacturers
  models
  engines
  axles
  motorbikes
  commercial_vehicles
  commercial_vehicle_attributes
  commercial_vehicle_engines
)

PASSENGER_HEAVY_TABLES=(
  passanger_car_trees
)

COMMERCIAL_HEAVY_TABLES=(
  commercial_vehicle_trees
)

run_clone_table() {
  local table="$1"
  local args=(
    docker compose -f "$COMPOSE_FILE" exec -T backend
    python manage.py autodb_clone_sync
    --only "$table"
    --batch-size "$BATCH_SIZE"
    --wait-for-autodb "$WAIT_FOR_AUTODB"
    --progress-every-batches "$PROGRESS_EVERY_BATCHES"
  )

  if [[ "$RESUME" == "1" ]]; then
    args+=(--resume)
  fi
  if [[ "$DRY_RUN" == "1" ]]; then
    args+=(--dry-run)
  fi

  echo "[clone] table=$table batch_size=$BATCH_SIZE resume=$RESUME dry_run=$DRY_RUN"
  "${args[@]}"
}

main() {
  echo "[clone] compose_file=$COMPOSE_FILE"
  echo "[clone] scope=$SCOPE"

  local base_tables=()
  local heavy_tables=()
  case "$SCOPE" in
    all)
      base_tables=("${PASSENGER_BASE_TABLES[@]}" "${COMMERCIAL_BASE_TABLES[@]}")
      heavy_tables=("${PASSENGER_HEAVY_TABLES[@]}" "${COMMERCIAL_HEAVY_TABLES[@]}")
      ;;
    commercial)
      base_tables=("${COMMERCIAL_BASE_TABLES[@]}")
      heavy_tables=("${COMMERCIAL_HEAVY_TABLES[@]}")
      ;;
    passenger)
      base_tables=("${PASSENGER_BASE_TABLES[@]}")
      heavy_tables=("${PASSENGER_HEAVY_TABLES[@]}")
      ;;
    *)
      echo "[clone] invalid SCOPE=$SCOPE (use all|commercial|passenger)" >&2
      exit 2
      ;;
  esac

  echo "[clone] base tables: ${base_tables[*]}"
  for table in "${base_tables[@]}"; do
    run_clone_table "$table"
  done

  if [[ "$INCLUDE_HEAVY_TREES" == "1" ]]; then
    echo "[clone] heavy tables enabled: ${heavy_tables[*]}"
    for table in "${heavy_tables[@]}"; do
      run_clone_table "$table"
    done
  else
    echo "[clone] heavy tables skipped (set INCLUDE_HEAVY_TREES=1 to enable)"
  fi

  if [[ "$ENSURE_INDEXES" == "1" ]]; then
    echo "[clone] ensuring vehicle catalog indexes"
    docker compose -f "$COMPOSE_FILE" exec -T backend \
      python manage.py autodb_clone_ensure_indexes --vehicle-catalog
  fi

  echo "[clone] done"
}

main "$@"
