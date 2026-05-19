# SVOM

Монорепозиторий e-commerce платформы автозапчастей.

В проекте объединены:
- backend API и бизнес-логика (Django + DRF + Celery + Channels)
- frontend storefront и backoffice (Next.js + React + TypeScript)
- локальная инфраструктура (PostgreSQL, Redis, Elasticsearch, LibreTranslate)
- интеграции поставщиков, Auto_DB_Pro, платежей, логистики, поддержки и уведомлений

## Что внутри

- Каталог: бренды, категории, товары, fitment/compatibility, поисковая выдача, sellable snapshots
- Коммерция: корзина, wishlist, checkout, заказы, promo-коды, loyalty
- Возвраты: клиентский/админский контур возвратов, статусы, ТТН, RBAC, интеграция с заказами
- Backoffice: операционный UI/API для каталога, прайсов, импорта, заказов, безопасности, SEO, маркетинга
- Supplier imports: UTR/GPL потоки, валидация, quality, публикация офферов, reprice/reindex
- Auto_DB_Pro: локальный clone DB + remote lookup/gate + matching/tecdoc batch
- Интеграции: Monobank, LiqPay, NovaPay, Nova Poshta, Vchasno.Kasa, Telegram
- Support: треды, очередь, counters, wallboard, presence reconciliation

## Структура репозитория

```text
.
├── backend/                 Django backend (apps, API, Celery, management commands)
├── frontend/                Next.js storefront + backoffice
├── infra/docker/            Dockerfiles backend/frontend
├── compose.yaml             Локальный docker-compose стек
├── .env.example             Шаблон переменных окружения
├── docs/                    Технические аудиты и внутренние заметки
├── UTR/                     Локальные справочники API UTR
└── Довідник Нова Пошта/     Локальные справочники API Nova Poshta
```

## Backend: домены и модули

`backend/apps`:
- `autodb`: работа с Auto_DB_Pro, clone sync, matching, enrichment, диагностика
- `autocatalog`: UTR/autocatalog импорты и справочники применяемости
- `backoffice`: основной операционный API (imports, pricing, orders, support, integrations)
- `catalog`: товарный каталог, карточка товара, навигация, fitment
- `commerce`: корзина, checkout, заказы, платежные webhooks
- `compatibility`: совместимость продуктов
- `core`: health, общие настройки, backup, системные сервисы
- `marketing`: hero/promo/footer контент
- `pricing`: репрайсинг, правила и сервисы расчета
- `search`: поисковый backend и индексирование
- `security`: контур блокировок/аудита/акторов
- `seo`: SEO-конфиги, шаблоны, overrides, sitemap/robots
- `supplier_imports`: пайплайн прайсов и сопоставления поставщиков
- `support`: поддержка, realtime-presence, wallboard
- `users`: auth/profile/garage/RBAC
- `vehicles`: автомобильная таксономия

### Основные API-префиксы backend

- `/api/backoffice/`
- `/api/autodb/`
- `/api/core/`
- `/api/catalog/`
- `/api/marketing/`
- `/api/seo/`
- `/api/users/`
- `/api/commerce/`

### Выделенные операционные зоны Backoffice API

- `autodb-matching/*` (включая `tecdoc-batch/run|state|stop` и `remote-quota`)
- `suppliers/*`, `import-runs/*`, `import-quality/*`, `import-errors/*`
- `pricing/*`, `product-prices/*`
- `orders/*`, waybill lifecycle, procurement suggestions
- `returns/*` (операционный список/деталь/смена статусов возврата)
- `support/*`, `security/*`
- `payments/*`, `nova-poshta/*`, `vchasno-kasa/*`
- `settings/*` (hero, promo, footer, email)
- `telegram/settings`, `telegram/test`
- `rbac/meta`, `users/*`, `groups/*`

## Frontend: зоны функциональности

`frontend/src/features`:
- storefront: `catalog`, `product`, `search`, `cart`, `checkout`, `wishlist`, `account`, `garage`, `support`
- backoffice: imports, suppliers, products/categories/brands, pricing, orders, payments
- integrations/security/support/telegram: отдельные страницы и API-клиенты в `backoffice/*`
- marketing/seo: публичные и backoffice-экраны

Примеры backoffice-страниц:
- `autodb-matching-page.tsx`
- `supplier-import*.tsx` / `suppliers-page.tsx`
- `orders-page.tsx` / `order-detail-page.tsx`
- `integration-center-page.tsx`
- `telegram-settings-page.tsx`
- `support-page.tsx` / `support-wallboard-page.tsx`
- `pricing-page.tsx`, `payments-page.tsx`, `seo-page.tsx`

## Технологический стек

Backend:
- Python 3.13
- Django 6
- Django REST Framework
- Celery + Redis
- Channels + Daphne
- PostgreSQL (primary + Auto_DB_Pro clone)
- Elasticsearch

Frontend:
- Next.js 16
- React 19
- TypeScript 5
- Tailwind CSS 4
- next-intl
- ECharts

## Локальный запуск через Docker (рекомендуется)

### 1) Подготовка env

```bash
cp .env.example .env
```

### 2) Запуск

```bash
docker compose up --build
```

Поднимаются сервисы:
- `svom_postgres`
- `svom_auto_db_pro_postgres`
- `svom_redis`
- `svom_elasticsearch`
- `svom_libretranslate`
- `svom_backend`
- `svom_frontend`
- `svom_celery_worker`
- `svom_celery_beat`

Endpoints:
- Backend: `http://localhost:8000`
- Frontend: `http://localhost:3000`
- Elasticsearch: `http://localhost:9200`

Важно:
- backend контейнер выполняет `migrate` при старте
- frontend в compose запускается в production-режиме (`build + start`)

## Локальный запуск без Docker (частично)

### Backend

```bash
cd backend
../.venv/bin/python manage.py migrate
../.venv/bin/python manage.py createsuperuser
../.venv/bin/python manage.py runserver 0.0.0.0:8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Ключевые переменные окружения

### Базовые
- `DJANGO_SETTINGS_MODULE` (`config.settings.dev` локально)
- `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`
- `POSTGRES_*`
- `REDIS_CACHE_URL`, `REDIS_CELERY_URL`
- `ELASTICSEARCH_HOSTS`, `SEARCH_BACKEND`

### Auto_DB_Pro
- local clone DB: `AUTODB_PRO_LOCAL_DATABASE_*`, `AUTODB_PRO_LOCAL_DATABASE_URL`
- remote source: `AUTODB_PRO_REMOTE_*`
- gate/quota: `AUTODB_PRO_REMOTE_LIMIT_PER_HOUR`, `AUTODB_PRO_REMOTE_STRICT_QUOTA_GATE_ENABLED`, `AUTODB_PRO_REMOTE_ENFORCE_GATEWAY_ONLY`
- backoffice batch timeout: `AUTODB_BACKOFFICE_BATCH_ITEM_TIMEOUT_SECONDS` (по умолчанию 90; можно увеличить при тяжёлых пакетах)
- API toggle: `AUTODB_PRO_VEHICLE_CATALOG_API_ENABLED`

### Supplier imports / retention
- `SUPPLIER_PRICE_LIST_FILE_RETENTION_HOURS`
- `SUPPLIER_IMPORT_SCHEDULE_DISPATCH_LOCK_SECONDS`
- `AUTODB_PRO_SUPPLIER_IMPORT_ENRICHMENT_ENABLED`
- `AUTODB_PRO_SUPPLIER_IMPORT_NAME_UPDATE_ENABLED`
- `AUTODB_PRO_SUPPLIER_IMPORT_REMOTE_LOOKUP_ENABLED`

### UTR safety profile
- `UTR_ENABLED`
- `UTR_RATE_LIMIT_PER_MINUTE`, `UTR_CONCURRENCY`
- `UTR_MAX_RETRIES`, `UTR_BACKOFF_BASE_SECONDS`
- `UTR_CIRCUIT_BREAKER_THRESHOLD`, `UTR_CIRCUIT_BREAKER_COOLDOWN_SECONDS`
- `UTR_BATCH_SIZE`, `UTR_RESOLVE_BATCH_SIZE`
- `UTR_APPLICABILITY_ENABLED`, `UTR_FORCE_REFRESH`

### Frontend/API
- `NEXT_PUBLIC_API_BASE_URL`
- `NEXT_SERVER_API_BASE_URL`
- `NEXT_PUBLIC_AUTODB_PRO_VEHICLE_CATALOG_ENABLED`

### Контент/переводы AutoDB
- `AUTODB_LIVE_CONTENT_ENABLED`
- `AUTODB_OFFLINE_TRANSLATE_ENABLED`
- `AUTODB_OFFLINE_TRANSLATE_PROVIDER`
- `AUTODB_OFFLINE_TRANSLATE_URL`
- `AUTODB_GOOGLE_TRANSLATE_*`

## Celery и периодические задачи

`CELERY_BEAT_SCHEDULE` включает:
- `supplier_imports.run_scheduled_imports` (каждую минуту)
- `core.dispatch_scheduled_database_backup` (каждую минуту)
- `supplier_imports.cleanup_price_list_files` (по расписанию cleanup)
- `commerce.sync_nova_poshta_waybill_statuses` (каждые 20 минут)
- `support.reconcile_presence` (каждую минуту)
- `support.rebuild_wallboard_snapshots` (каждые 5 минут)
- `pricing.sync_products_activity_by_price_freshness` (каждые 15 минут)

## Realtime обновления (Orders/Returns)

- Для клиентских `orders` и `returns` используется WebSocket push (`/ws/commerce/user/`) как основной канал.
- Polling сохранён как fallback при недоступном сокете.
- События:
  - `commerce.order.updated`
  - `commerce.return.updated`

### Статусы возврата: важное

- Статус `refund_processing` физически удалён из активного workflow.
- Финальный денежный статус возврата — единый `refunded` (в UI отображается как `Возврат`).
- Миграция `commerce.0024_unify_return_refund_status` переводит legacy-записи `refund_processing -> refunded`.

## Auto_DB_Pro: практические команды

Проверка подключения:

```bash
cd backend
../.venv/bin/python manage.py autodb_check
```

Синхронизация clone (примеры):

```bash
cd backend
../.venv/bin/python manage.py autodb_clone_sync --vehicle-catalog --schema-only
../.venv/bin/python manage.py autodb_clone_sync --only manufacturers --limit 100
../.venv/bin/python manage.py autodb_clone_sync --vehicle-catalog --batch-size 1000 --resume
```

Диагностика/обслуживание:
- `autodb_clone_ensure_indexes`
- `autodb_matching_*`
- `autodb_update_product_*`
- `autodb_diagnose_*`

## Supplier import pipeline

Основной flow:
1. request/download price list
2. import raw offers
3. match/review/category mapping
4. publish mapped products/offers
5. reprice + reindex

Ключевые области кода:
- `backend/apps/supplier_imports/services/`
- `backend/apps/backoffice/services/supplier_workspace/`
- `backend/apps/backoffice/services/supplier_price_workflow/`
- `backend/apps/supplier_imports/services/mapped_offer_publish/`

См. аудит производительности:
- `docs/supplier_import_performance_audit.md`

## Интеграции

Платежи:
- Monobank
- LiqPay
- NovaPay

Доставка:
- Nova Poshta (sender profiles, lookups, waybill lifecycle, sync/print/history)

Касса:
- Vchasno.Kasa (settings, shift, receipts, issue/sync/open чека)

Уведомления:
- Telegram settings в backoffice (`telegram.manage` capability)
- Каналы `ops`, `support`, `system`
- События отправляются из сервисов заказов и waybill

## RBAC и безопасность

- Backoffice RBAC метаданные: `/api/backoffice/rbac/meta/`
- Capability-ориентированная проверка доступа в backoffice страницах и API
- Security контур: actors, blocks, audit, timeseries, false-positive flow

## Поиск и SEO

Поиск:
- `SEARCH_BACKEND=db|elasticsearch`
- индексатор: `manage.py reindex_products`

SEO API:
- public config/google/site/resolve-meta
- backoffice settings/templates/overrides/dashboard/sitemap/robots-preview

## Тесты и проверка качества

Backend:

```bash
cd backend
../.venv/bin/python manage.py test
```

Frontend:

```bash
cd frontend
npm run lint
npm run test:unit
npm run build
```

## Полезные документы в репозитории

- `docs/utr_audit.md`
- `docs/supplier_import_performance_audit.md`
- `docs/backoffice_admin_migration_audit.md`

## Примечания по эксплуатации

- Таймзона backend: `Europe/Kyiv`
- После внезапного рестарта хоста PostgreSQL может быть в recovery, это нужно учитывать при Auto_DB_Pro задачах
- Репозиторий активно развивается, возможны локальные незакоммиченные изменения в рабочем дереве
