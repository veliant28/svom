#!/usr/bin/env bash
set -euo pipefail

# One-time bootstrap for a fresh Hetzner Ubuntu/Debian server.
# Usage:
#   REPO_URL=https://github.com/<owner>/<repo>.git \
#   APP_DIR=/opt/svom \
#   APP_USER=deploy \
#   SSH_PORT=22 \
#   DEPLOY_SSH_PUBLIC_KEY='ssh-ed25519 AAAA... user@host' \
#   ./scripts/deploy/bootstrap_server.sh

APP_USER="${APP_USER:-deploy}"
APP_DIR="${APP_DIR:-/opt/svom}"
REPO_URL="${REPO_URL:-}"
SSH_PORT="${SSH_PORT:-22}"
DEPLOY_SSH_PUBLIC_KEY="${DEPLOY_SSH_PUBLIC_KEY:-}"
ENABLE_STRICT_SSH_HARDENING="${ENABLE_STRICT_SSH_HARDENING:-1}"

if [[ -z "${REPO_URL}" ]]; then
  echo "ERROR: REPO_URL is required"
  exit 1
fi

if [[ "$(id -u)" -ne 0 ]]; then
  echo "ERROR: run as root"
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y ca-certificates curl git gnupg

install -m 0755 -d /etc/apt/keyrings
if [[ ! -f /etc/apt/keyrings/docker.asc ]]; then
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc || \
    curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
fi

if [[ -f /etc/os-release ]]; then
  # shellcheck disable=SC1091
  source /etc/os-release
else
  echo "ERROR: /etc/os-release not found"
  exit 1
fi

if [[ "${ID}" == "ubuntu" ]]; then
  REPO_LINE="deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable"
else
  REPO_LINE="deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian ${VERSION_CODENAME} stable"
fi

cat > /etc/apt/sources.list.d/docker.list <<EOF
${REPO_LINE}
EOF

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

if ! id -u "${APP_USER}" >/dev/null 2>&1; then
  useradd -m -s /bin/bash "${APP_USER}"
fi

usermod -aG docker "${APP_USER}"

install -d -m 0755 -o "${APP_USER}" -g "${APP_USER}" "${APP_DIR}"

if [[ ! -d "${APP_DIR}/.git" ]]; then
  if command -v sudo >/dev/null 2>&1; then
    sudo -u "${APP_USER}" git clone "${REPO_URL}" "${APP_DIR}"
  else
    su -s /bin/bash -c "git clone '${REPO_URL}' '${APP_DIR}'" "${APP_USER}"
  fi
else
  if command -v sudo >/dev/null 2>&1; then
    sudo -u "${APP_USER}" git -C "${APP_DIR}" fetch --all --prune
  else
    su -s /bin/bash -c "git -C '${APP_DIR}' fetch --all --prune" "${APP_USER}"
  fi
fi

if [[ ! -f "${APP_DIR}/.env.prod" ]]; then
  cp "${APP_DIR}/.env.prod.example" "${APP_DIR}/.env.prod"
  chown "${APP_USER}:${APP_USER}" "${APP_DIR}/.env.prod"
  chmod 600 "${APP_DIR}/.env.prod"
  echo "INFO: created ${APP_DIR}/.env.prod from example. Fill real values before first deploy."
fi

systemctl enable docker
systemctl restart docker

APP_USER="${APP_USER}" \
SSH_PORT="${SSH_PORT}" \
DEPLOY_SSH_PUBLIC_KEY="${DEPLOY_SSH_PUBLIC_KEY}" \
ENABLE_STRICT_SSH_HARDENING="${ENABLE_STRICT_SSH_HARDENING}" \
"${APP_DIR}/scripts/deploy/harden_server.sh"

echo "Bootstrap completed."
echo "Next:"
echo "1) fill ${APP_DIR}/.env.prod"
echo "2) run: sudo -u ${APP_USER} ${APP_DIR}/scripts/deploy/deploy_on_server.sh"
