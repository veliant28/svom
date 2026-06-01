# Hetzner production setup (SVOM)

Этот документ описывает полностью автоматизированный деплой на выделенный сервер Hetzner.

## Что уже подготовлено в репозитории

- `compose.prod.yaml` - production stack
- `deploy/nginx/svom.conf` - reverse proxy (frontend + backend + websockets)
- `scripts/deploy/bootstrap_server.sh` - one-time server bootstrap
- `scripts/deploy/harden_server.sh` - security hardening profile (SSH, UFW, fail2ban, updates, sysctl)
- `scripts/deploy/deploy_on_server.sh` - deploy script for CI and manual deploy
- `.github/workflows/deploy-prod.yml` - auto deploy on push
- `.env.prod.example` - production env template

## 1) Первичный запуск на сервере (один раз)

Под root (или sudo):

```bash
apt update && apt install -y git
git clone https://github.com/veliant28/svom.git /opt/svom
cd /opt/svom
REPO_URL=https://github.com/veliant28/svom.git APP_DIR=/opt/svom APP_USER=deploy SSH_PORT=22 DEPLOY_SSH_PUBLIC_KEY='ssh-ed25519 AAAA...your_key...' ./scripts/deploy/bootstrap_server.sh
```

Что делает bootstrap:
- ставит Docker Engine + Docker Compose plugin
- настраивает пользователя `deploy`
- клонирует/обновляет проект в `/opt/svom`
- создает `.env.prod` из `.env.prod.example`
- включает hardening-профиль:
  - SSH только по ключу (если передан `DEPLOY_SSH_PUBLIC_KEY`)
  - `ufw` (только SSH/80/443)
  - `fail2ban` (`sshd` + `recidive`)
  - автоматические security-обновления (`unattended-upgrades`)
  - безопасные `sysctl` сетевые параметры

Важно:
- Передавайте `DEPLOY_SSH_PUBLIC_KEY` при первом запуске bootstrap, иначе строгий SSH-hardening будет пропущен.
- Если хотите временно оставить парольный SSH, задайте `ENABLE_STRICT_SSH_HARDENING=0`.

## 2) Заполнить production env

Файл: `/opt/svom/.env.prod`

Минимум обязательного:
- `DJANGO_SECRET_KEY`
- `POSTGRES_PASSWORD`
- `AUTODB_PRO_LOCAL_DATABASE_PASSWORD`
- `DJANGO_ALLOWED_HOSTS`
- `NEXT_PUBLIC_API_BASE_URL`
- `EMAIL_HOST_PASSWORD`

Если пока без домена и SSL:
- оставьте `DJANGO_SECURE_SSL_REDIRECT=0`
- используйте `http://SERVER_IP/api` для `NEXT_PUBLIC_API_BASE_URL`

## 3) Первый деплой вручную

Под пользователем `deploy`:

```bash
cd /opt/svom
APP_DIR=/opt/svom DEPLOY_BRANCH=main ./scripts/deploy/deploy_on_server.sh
```

Проверка:

```bash
docker compose --env-file .env.prod -f compose.prod.yaml ps
```

## 4) Автодеплой из GitHub

Добавьте GitHub Secrets в репозитории:
- `PROD_SSH_HOST` - IP сервера
- `PROD_SSH_PORT` - обычно `22`
- `PROD_SSH_USER` - `deploy`
- `PROD_SSH_PRIVATE_KEY` - приватный ключ, которому разрешен вход на сервер
- `PROD_APP_DIR` - `/opt/svom`
- `PROD_DEPLOY_BRANCH` - `main` (опционально)

После этого каждый `git push` в `main`/`master` запускает workflow и автоматически применяет изменения на сервере.

## 5) Полезные команды поддержки

```bash
# Логи конкретного сервиса
docker compose --env-file .env.prod -f compose.prod.yaml logs -f backend

# Перезапуск всего стека
docker compose --env-file .env.prod -f compose.prod.yaml up -d --remove-orphans

# Статус
docker compose --env-file .env.prod -f compose.prod.yaml ps
```

## Рекомендация по серверу из аукциона

Конфигурация `i7-6700 / 64 GB / 2x480 SSD` подходит с большим запасом для этого стека.
На старте можно держать всё на одном сервере без вынесения БД отдельно.
