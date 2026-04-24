# SVOM

SVOM is a monorepo for an automotive e-commerce platform with:

- Django 6 backend API
- Next.js 16 frontend storefront and backoffice
- PostgreSQL, Redis, Elasticsearch
- Celery background jobs
- supplier import pipelines for `UTR` and `GPL`
- product pricing, search, marketing, orders, users and support modules

## Repository layout

```text
.
├── backend/                Django API, Celery, supplier imports, pricing, commerce
├── frontend/               Next.js storefront + backoffice
├── infra/docker/           Dockerfiles
├── compose.yaml            Local infrastructure and backend containers
└── .env.example            Local environment template
```

## Main modules

- `catalog` / `autocatalog`: catalog entities, automotive fitment and TecDoc-style vehicle data
- `supplier_imports`: supplier file ingestion, matching, publishing, mapped-offer workflows
- `pricing`: product repricing, overrides, price history
- `commerce`: cart, checkout, payments, orders
- `backoffice`: operations UI/API, dashboards, imports, pricing control, marketing settings
- `marketing`: hero block, promo banners, footer settings
- `search`: DB/Elasticsearch-backed search
- `support`: realtime support presence and wallboard flows

## Tech stack

### Backend

- Python
- Django 6
- Django REST Framework
- Celery
- Channels + Daphne
- PostgreSQL
- Redis
- Elasticsearch

### Frontend

- Next.js 16
- React 19
- TypeScript
- Tailwind CSS 4
- `next-intl`
- `echarts`

## Local setup

### 1. Environment

Create local env file from the template:

```bash
cp .env.example .env
```

Important variables from `.env.example`:

- `DJANGO_SETTINGS_MODULE=config.settings.dev`
- `POSTGRES_*`
- `REDIS_*`
- `ELASTICSEARCH_HOSTS`
- `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api`
- `UTR_*` safety and rate-limit settings

### 2. Start infrastructure and backend

```bash
docker compose up --build
```

This starts:

- `svom_postgres`
- `svom_redis`
- `svom_elasticsearch`
- `svom_backend`
- `svom_celery_worker`

Backend is exposed at:

- `http://localhost:8000`
- API root under `http://localhost:8000/api/...`

The backend container runs migrations on startup.

### 3. Start frontend

In a separate terminal:

```bash
cd frontend
npm install
npm run dev
```

Frontend is exposed at:

- `http://localhost:3000`

## Development commands

### Backend

```bash
cd backend
../.venv/bin/python manage.py migrate
../.venv/bin/python manage.py createsuperuser
../.venv/bin/python manage.py test
```

If you work inside Docker:

```bash
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py test
docker compose exec backend python manage.py createsuperuser
```

### Frontend

```bash
cd frontend
npm run dev
npm run build
npm run lint
npm exec tsc --noEmit
```

## Supplier imports

The project contains import and publishing flows for supplier data:

- `UTR`
- `GPL`

Relevant areas:

- `backend/apps/supplier_imports/`
- `backend/apps/backoffice/services/supplier_workspace/`
- `backend/apps/backoffice/services/supplier_price_workflow/`
- `backend/apps/supplier_imports/services/mapped_offer_publish/`

UTR integration includes conservative anti-ban defaults in `.env.example`, for example:

- `UTR_RATE_LIMIT_PER_MINUTE=6`
- `UTR_CONCURRENCY=1`
- `UTR_CIRCUIT_BREAKER_THRESHOLD=5`
- `UTR_CIRCUIT_BREAKER_COOLDOWN_SECONDS=300`

## Marketing and storefront content

Storefront marketing content is managed from backoffice and backend APIs:

- Hero block
- Promo banners
- Footer settings

Relevant paths:

- `backend/apps/marketing/`
- `frontend/src/features/marketing/`
- `frontend/src/features/backoffice/pages/hero-block-page.tsx`
- `frontend/src/features/backoffice/pages/promo-banners-page.tsx`

## Search

Search backend is configurable:

- `SEARCH_BACKEND=db`
- `SEARCH_BACKEND=elasticsearch`

Elasticsearch is available locally through `compose.yaml`.

## Notes

- The repository can contain active in-progress local changes during development.
- The backend uses `Europe/Kyiv` timezone.
- Frontend and backend are developed together and share the same API contract inside this monorepo.
