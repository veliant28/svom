#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/svom}"
DEPLOY_BRANCH="${DEPLOY_BRANCH:-main}"

cd "${APP_DIR}"

if [[ ! -d .git ]]; then
  echo "ERROR: ${APP_DIR} is not a git repository"
  exit 1
fi

git fetch origin "${DEPLOY_BRANCH}"

CURRENT_REV="$(git rev-parse HEAD)"
REMOTE_REV="$(git rev-parse FETCH_HEAD)"

if [[ "${CURRENT_REV}" == "${REMOTE_REV}" ]]; then
  echo "No changes for ${DEPLOY_BRANCH}"
  exit 0
fi

echo "New revision detected: ${CURRENT_REV} -> ${REMOTE_REV}"
APP_DIR="${APP_DIR}" DEPLOY_BRANCH="${DEPLOY_BRANCH}" "${APP_DIR}/scripts/deploy/deploy_on_server.sh"
