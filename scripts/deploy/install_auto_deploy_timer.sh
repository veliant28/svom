#!/usr/bin/env bash
set -euo pipefail

APP_USER="${APP_USER:-deploy}"
APP_DIR="${APP_DIR:-/opt/svom}"
DEPLOY_BRANCH="${DEPLOY_BRANCH:-main}"
TIMER_NAME="${TIMER_NAME:-svom-auto-deploy}"
INTERVAL="${INTERVAL:-1min}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "ERROR: run as root"
  exit 1
fi

SERVICE_FILE="/etc/systemd/system/${TIMER_NAME}.service"
TIMER_FILE="/etc/systemd/system/${TIMER_NAME}.timer"

cat > "${SERVICE_FILE}" <<EOF
[Unit]
Description=SVOM auto deploy when origin/${DEPLOY_BRANCH} changes
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=oneshot
User=${APP_USER}
WorkingDirectory=${APP_DIR}
Environment=APP_DIR=${APP_DIR}
Environment=DEPLOY_BRANCH=${DEPLOY_BRANCH}
ExecStart=${APP_DIR}/scripts/deploy/auto_pull_and_deploy.sh
EOF

cat > "${TIMER_FILE}" <<EOF
[Unit]
Description=Run SVOM auto deploy check every ${INTERVAL}

[Timer]
OnBootSec=2min
OnUnitActiveSec=${INTERVAL}
Persistent=true

[Install]
WantedBy=timers.target
EOF

chmod 644 "${SERVICE_FILE}" "${TIMER_FILE}"
chmod 755 "${APP_DIR}/scripts/deploy/auto_pull_and_deploy.sh"

systemctl daemon-reload
systemctl enable --now "${TIMER_NAME}.timer"
systemctl restart "${TIMER_NAME}.timer"
systemctl list-timers --all | grep -E "${TIMER_NAME}|NEXT|LEFT" || true
