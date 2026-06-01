#!/usr/bin/env bash
set -euo pipefail

# Server hardening profile for Hetzner dedicated host.
# This script is safe to run multiple times.

APP_USER="${APP_USER:-deploy}"
SSH_PORT="${SSH_PORT:-22}"
DEPLOY_SSH_PUBLIC_KEY="${DEPLOY_SSH_PUBLIC_KEY:-}"
ENABLE_STRICT_SSH_HARDENING="${ENABLE_STRICT_SSH_HARDENING:-1}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "ERROR: run as root"
  exit 1
fi

if ! [[ "${SSH_PORT}" =~ ^[0-9]+$ ]] || [[ "${SSH_PORT}" -lt 1 || "${SSH_PORT}" -gt 65535 ]]; then
  echo "ERROR: SSH_PORT must be integer in range 1..65535"
  exit 1
fi

if ! id -u "${APP_USER}" >/dev/null 2>&1; then
  echo "ERROR: APP_USER '${APP_USER}' does not exist"
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends fail2ban ufw unattended-upgrades apt-listchanges

# Configure SSH key for deploy user when provided.
if [[ -n "${DEPLOY_SSH_PUBLIC_KEY}" ]]; then
  install -d -m 700 -o "${APP_USER}" -g "${APP_USER}" "/home/${APP_USER}/.ssh"
  AUTH_FILE="/home/${APP_USER}/.ssh/authorized_keys"
  touch "${AUTH_FILE}"
  if ! grep -Fqx "${DEPLOY_SSH_PUBLIC_KEY}" "${AUTH_FILE}"; then
    printf '%s\n' "${DEPLOY_SSH_PUBLIC_KEY}" >> "${AUTH_FILE}"
  fi
  chown "${APP_USER}:${APP_USER}" "${AUTH_FILE}"
  chmod 600 "${AUTH_FILE}"
fi

# Strict SSH hardening is applied only if we have a public key.
if [[ "${ENABLE_STRICT_SSH_HARDENING}" == "1" ]]; then
  if [[ -z "${DEPLOY_SSH_PUBLIC_KEY}" ]]; then
    echo "WARN: strict SSH hardening skipped because DEPLOY_SSH_PUBLIC_KEY is empty"
  else
    install -d -m 755 /etc/ssh/sshd_config.d
    cat > /etc/ssh/sshd_config.d/99-svom-hardening.conf <<EOF
Port ${SSH_PORT}
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
ChallengeResponseAuthentication no
PubkeyAuthentication yes
AuthenticationMethods publickey
MaxAuthTries 4
LoginGraceTime 20
X11Forwarding no
AllowAgentForwarding no
ClientAliveInterval 300
ClientAliveCountMax 2
UseDNS no
EOF

    if ! sshd -t; then
      echo "ERROR: sshd config test failed"
      exit 1
    fi

    if ! (systemctl reload ssh || systemctl reload sshd); then
      echo "WARN: could not reload ssh service automatically"
    fi
  fi
fi

# Kernel/network baseline hardening.
cat > /etc/sysctl.d/99-svom-hardening.conf <<'EOF'
net.ipv4.tcp_syncookies = 1
net.ipv4.icmp_echo_ignore_broadcasts = 1
net.ipv4.icmp_ignore_bogus_error_responses = 1
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv6.conf.all.accept_redirects = 0
net.ipv6.conf.default.accept_redirects = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.default.send_redirects = 0
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1
net.ipv4.conf.all.log_martians = 1
net.ipv4.conf.default.log_martians = 1
EOF
sysctl --system >/dev/null

# UFW: deny everything inbound except ssh/http/https.
ufw default deny incoming
ufw default allow outgoing
ufw allow "${SSH_PORT}/tcp"
ufw limit "${SSH_PORT}/tcp"
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# Fail2ban profile tailored for ssh brute-force and repeated offenders.
cat > /etc/fail2ban/jail.d/svom.local <<EOF
[DEFAULT]
ignoreip = 127.0.0.1/8 ::1
banaction = ufw
bantime = 1h
findtime = 10m
maxretry = 5

[sshd]
enabled = true
port = ${SSH_PORT}
backend = systemd

[recidive]
enabled = true
logpath = /var/log/fail2ban.log
banaction = ufw
bantime = 1w
findtime = 1d
maxretry = 5
EOF

# Automatic security updates.
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF

cat > /etc/apt/apt.conf.d/52svom-unattended-upgrades <<'EOF'
Unattended-Upgrade::AutoFixInterruptedDpkg "true";
Unattended-Upgrade::MinimalSteps "true";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
Unattended-Upgrade::Automatic-Reboot "false";
EOF

systemctl enable fail2ban
systemctl restart fail2ban
systemctl enable unattended-upgrades
systemctl restart unattended-upgrades

echo "Hardening completed."
