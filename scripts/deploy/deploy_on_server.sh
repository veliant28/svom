#!/usr/bin/env bash
set -euo pipefail

# Deploy script invoked on server manually or by GitHub Actions over SSH.
# Environment variables:
#   APP_DIR (default: current repo root)
#   DEPLOY_BRANCH (default: main)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${APP_DIR:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
DEPLOY_BRANCH="${DEPLOY_BRANCH:-main}"

cd "${APP_DIR}"

if [[ ! -f .env.prod ]]; then
  echo "ERROR: ${APP_DIR}/.env.prod not found"
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is not installed"
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: docker compose plugin is not available"
  exit 1
fi

# Single deploy at a time.
exec 9>/tmp/svom-deploy.lock
if ! flock -n 9; then
  echo "Another deployment is already running"
  exit 1
fi

git fetch origin
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ "${CURRENT_BRANCH}" != "${DEPLOY_BRANCH}" ]]; then
  git checkout "${DEPLOY_BRANCH}"
fi

git reset --hard "origin/${DEPLOY_BRANCH}"

docker compose --env-file .env.prod -f compose.prod.yaml pull || true
docker compose --env-file .env.prod -f compose.prod.yaml build --pull
docker compose --env-file .env.prod -f compose.prod.yaml up -d --remove-orphans

docker image prune -f >/dev/null 2>&1 || true

echo "Deploy completed successfully"
