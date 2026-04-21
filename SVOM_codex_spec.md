# SVOM Codex Spec (Actual Project State)

Last updated: 2026-04-21

## 1. Purpose

This file is the working specification for Codex changes in `~/Django/svom`.
It reflects the **current real project state** and replaces old planning assumptions.

Primary objective:
- develop and maintain SVOM as a modular e-commerce platform for auto parts,
- keep backend and frontend aligned,
- prefer safe, incremental changes over large rewrites.

## 2. Source of Truth

When this file conflicts with code:
- **code and migrations are the source of truth**,
- this spec must be updated to match code.

Do not invent architecture from templates.

## 3. Monorepo Layout

```text
~/Django/svom/
  backend/      # Django + DRF
  frontend/     # Next.js App Router storefront + backoffice UI
  infra/        # Dockerfiles and infra helpers
  docs/         # operational notes and audits
  compose.yaml  # local environment
  .env(.example)
  SVOM_codex_spec.md
```

## 4. Actual Stack (Pinned by Repo)

### Backend
- Django `6.0.4`
- Django REST Framework `3.17.1`
- django-cors-headers `4.9.0`
- django-filter `25.2`
- psycopg[binary] `3.2.12`
- Celery `5.6.0`
- Redis `6.4.0`
- Elasticsearch client `9.3.0`
- Pillow `11.2.1`
- gunicorn `23.0.0`

### Frontend
- Next.js `16.2.3`
- React `19.1.0`
- TypeScript `5.9.3`
- Tailwind CSS `4.1.13`
- next-intl `4.9.1`
- lucide-react `1.8.0`
- echarts `5.6.0`

### Infra / local runtime
- PostgreSQL `18.3` (compose)
- Redis `8.0.6` (compose)
- Elasticsearch `9.3.3` (compose)

## 5. Architecture

SVOM is a **modular monolith**:
- backend exposes REST APIs under `/api/*`,
- frontend consumes backend APIs and renders storefront/backoffice,
- background operations run via Celery.

### Important clarification
- Current project does **not** use Django admin/Unfold as active backoffice UI.
- Backoffice is implemented in Next.js (`frontend/src/features/backoffice`).
- Do not reintroduce Unfold assumptions unless explicitly requested and implemented.

## 6. Backend Structure

Django apps (from `INSTALLED_APPS`):
- `core`
- `users`
- `catalog`
- `vehicles`
- `autocatalog`
- `compatibility`
- `marketing`
- `seo`
- `search`
- `pricing`
- `supplier_imports`
- `backoffice`
- `commerce`

Patterns used across apps:
- `api/` for DRF serializers/views/urls
- `models/` split by entity
- `selectors/` for query/read composition
- `services/` for business workflows
- `tasks/` for async execution
- `tests/` for smoke and domain tests

## 7. Frontend Structure

App Router entry points:
- `frontend/src/app/[locale]/(storefront)/*`
- `frontend/src/app/[locale]/(backoffice)/backoffice/*`

Feature-based modules in `frontend/src/features/*`:
- `auth`, `account`, `catalog`, `search`, `cart`, `checkout`, `commerce`, `garage`, `wishlist`, `marketing`, `storefront`, `backoffice`.

Shared layers:
- `shared/api`, `shared/components`, `shared/lib`, `shared/hooks`
- `i18n/*` and `messages/{uk,ru,en}/*`

## 8. API and Routing Conventions

Backend root API routes (see `backend/config/urls.py`):
- `/api/backoffice/`
- `/api/autocatalog/`
- `/api/core/`
- `/api/catalog/`
- `/api/marketing/`
- `/api/vehicles/`
- `/api/users/`
- `/api/commerce/`

No `/admin/` route is configured in current `config/urls.py`.

## 9. Auth, Identity, Access

### Identity model
- Custom user model: `AUTH_USER_MODEL = users.User`
- Login identifier: **email** (`USERNAME_FIELD = "email"`)
- `username` field has been removed from runtime model and migrated out.

### API auth
- Token auth via DRF `TokenAuthentication`
- Frontend stores and reuses auth token for API calls.

### Backoffice access
- Protected by staff/superuser checks and RBAC capability mapping.
- Manage permissions through users/groups/system roles logic in `users.rbac` and backoffice APIs.

## 10. i18n Rules

Locales are fixed:
- `uk` (default)
- `ru`
- `en`

Frontend locale strategy:
- next-intl routing with `localePrefix: "always"`
- all user-facing feature changes require message updates for all supported locales.

Backend:
- `LANGUAGE_CODE = "uk"`
- `TIME_ZONE = "Europe/Kyiv"`
- `USE_I18N = True`, locale files under app `locale/` + `backend/locale`.

## 11. Supplier Imports and Scheduling

Supplier flows are first-class and safety-sensitive:
- import sources and schedule settings live in `supplier_imports` domain,
- operational controls are exposed in backoffice APIs/UI,
- scheduled dispatch is configured via Celery beat,
- UTR safety/rate-limit circuit-breaker settings are defined in Django settings.

Any change touching supplier auth/import scheduling must preserve:
- idempotency,
- explicit status transitions,
- conservative retry/backoff behavior,
- clear operator-facing error states.

## 12. Search and Data Boundaries

- PostgreSQL remains source of truth.
- Elasticsearch is read/search infrastructure, not authoritative data storage.
- Keep domain logic in services/selectors, not in serializer/view shortcuts.

## 13. Coding Constraints

### File size discipline
- target: 200-400 lines
- acceptable: up to 500-600
- split when approaching 700+
- avoid 1000+ manually maintained files

### Change style
- prefer minimal safe diffs,
- avoid broad refactors unless necessary,
- preserve existing module boundaries and naming conventions,
- never silently change API contracts used by frontend.

### Data migrations
- schema-breaking changes must include safe data migration/backfill when needed,
- do not drop user-facing data without migration strategy.

## 14. Quality Gates for Changes

Before finalizing substantial changes, run what is applicable:

Backend:
- `python manage.py check`
- focused tests for affected apps (when DB/runtime is available)

Frontend:
- `npx tsc --noEmit`
- optionally lint/tests if touched scope requires it

If some checks cannot run (env/network/db constraints), explicitly report that.

## 15. Local Runbook

Quick local setup:
1. `cp .env.example .env`
2. `docker compose up --build`

Backend manual commands (local venv):
- `cd backend && ../.venv/bin/python manage.py migrate`
- `cd backend && ../.venv/bin/python manage.py runserver`

Frontend:
- `cd frontend && npm install`
- `cd frontend && npm run dev`

## 16. Out of Scope / Deprecated Assumptions

Treat as deprecated unless explicitly reintroduced:
- Unfold-based admin as primary backoffice runtime,
- assumptions that `username` is login credential,
- architecture decisions that contradict current code and migrations.

## 17. How to Update This Spec

Update this file whenever one of these changes:
- stack version pinning,
- auth model/contract,
- API surface roots,
- i18n locale policy,
- core architectural decisions.

Keep updates concrete and verifiable against repository files.
