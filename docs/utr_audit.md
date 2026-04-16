# UTR Audit (SVOM)

Дата аудита: 2026-04-14

## Часть A. Аудит

### 1) Что найдено по UTR

- Корень репозитория:
  - `run_utr_nonstop.sh` (ручной shell-оркестратор UTR-проходов).
  - `utr_nonstop.log` (факт запусков и прогресса).
  - `utr_latest_price_*.xlsx` (локальные выгрузки).
- Локальная документация API:
  - `UTR/Пакетный поиск деталей (API версия 2).txt`.
  - `UTR/Поиск детали по артикулу и бренду (API версия 2).txt`.
  - `UTR/Применяемость детали (API версия 2).txt`.
  - `UTR/Информация о детали (API версия 2).txt`.
  - `UTR/Характеристики детали (API версия 2).txt`.
  - `UTR/Аутентификация и авторизация (API версия 2).txt`.
- Backend UTR-контур:
  - Клиент: `backend/apps/supplier_imports/services/integrations/utr_client.py`.
  - Автокаталог-команда: `backend/apps/autocatalog/management/commands/import_utr_autocatalog.py`.
  - Резолвер article+brand -> detail_id: `backend/apps/autocatalog/services/utr_article_detail_resolver_service.py`.
  - Импорт применяемости по detail_id: `backend/apps/autocatalog/services/utr_autocatalog_import_service.py`.
  - Модели/кеш-слой в БД:
    - `backend/apps/autocatalog/models/utr_article_detail_map.py`.
    - `backend/apps/autocatalog/models/utr_detail_car_map.py`.
    - `backend/apps/catalog/models/product.py` (поле `utr_detail_id`).
- Backoffice UTR API-поток (не автокаталог):
  - `backend/apps/backoffice/services/supplier_workspace_service.py` (login/refresh/check/brands).
  - `backend/apps/backoffice/services/supplier_price_workflow_service.py` (pricelists).

### 2) Что реально используется сейчас

- `run_utr_nonstop.sh` реально запускался: в `utr_nonstop.log` есть старты:
  - `2026-04-14 07:12:12`
  - `2026-04-14 08:07:36`
  - `2026-04-14 15:24:44`
- Основной тяжелый поток автокаталога идет через:
  - `manage.py import_utr_autocatalog`
  - внутри: `UtrArticleDetailResolverService` (`search`) + `UtrAutocatalogImportService` (`applicability`).
- Автоматического Celery/cron запуска `import_utr_autocatalog` не найдено; Celery beat запускает scheduler supplier-import, а не автокаталог-команду UTR.

### 3) Карта потока запросов

1. Старт импорта:
   - Ручной запуск `manage.py import_utr_autocatalog` или через `run_utr_nonstop.sh`.
2. Получение article/brand:
   - Из `SupplierRawOffer` (`source__code="utr"`) в `UtrArticleDetailResolverService`.
3. Получение `detail_id`:
   - Через `UtrClient.search_details()` (`/api/search/{oem}`), затем фильтрация кандидатов.
   - Сохранение в `UtrArticleDetailMap`.
4. Получение applicability:
   - Для списка detail_id вызывается `UtrClient.fetch_applicability()` (`/api/applicability/{detail_id}`).
   - Результат маппится в `CarMake/CarModel/CarModification` + `UtrDetailCarMap`.
5. Где хранится прогресс:
   - `UtrArticleDetailMap` хранит article->detail.
   - `UtrDetailCarMap` хранит detail->car mapping.
   - В исходной версии не было явного persistent-маркера «detail уже опрошен и пустой». 

### 4) Узкие места и риски бана (до правок)

1. Поштучный паттерн в корневом скрипте:
   - `run_utr_nonstop.sh` дергал `--resolve-limit 1` и затем applicability `--limit 1 --offset N` с `sleep 60`.
   - В логе видно шаг ~1 минута и длительный tail unresolved.
2. Повторные запросы по тем же detail_id между прогонами:
   - Лог показывает повтор одинаковых detail_id при новых стартах nonstop.
3. Локальные throttling/retry были разнесены по разным сервисам:
   - Не было единой policy-обертки для UTR вызовов.
4. Не было circuit breaker при серии 429/5xx/timeout.
5. Не было jitter в backoff.
6. Не было централизованного конфигурируемого rate-limit/concurrency для всех UTR endpoint-ов.
7. `progress/resume` был только через ручные `--offset/--limit`, без cache-state на пустые applicability.
8. Batch search из документации UTR есть, но в текущем контуре автокаталога использовался одиночный GET-search.

### 5) Проверка API-оптимальности по локальным docs

- В docs присутствует batch endpoint:
  - `POST /api/search` (пакетный поиск нескольких деталей).
- В коде автокаталога использовался одиночный поиск:
  - `GET /api/search/{oem}` (+brand).
- Applicability endpoint в docs одиночный:
  - `GET /api/applicability/{detail_id}`.
- `detail` и `characteristics` endpoints документированы, но в автокаталог-потоке не использовались.

### 6) Вывод о причине медленной и рискованной работы

Ключевая причина — не сам API UTR, а паттерн запуска:
- поштучный shell-loop (`limit=1`, `offset` по одному, `sleep 60`),
- плюс повторные прогоны по уже обработанным `detail_id`,
- плюс отсутствие централизованной политики защиты (общий limiter/retry/circuit/cache).

Итог: очень медленно и потенциально опасно (долгие многочасовые однотипные серии вызовов), при этом «ускорения» за счет параллелизма не применялось.

---

## Часть B. Внесенные изменения (anti-ban hardening)

### Измененные файлы

1. `backend/config/settings/base.py`
2. `.env.example`
3. `backend/apps/supplier_imports/services/integrations/utr_client.py`
4. `backend/apps/autocatalog/services/utr_article_detail_resolver_service.py`
5. `backend/apps/autocatalog/services/utr_autocatalog_import_service.py`
6. `backend/apps/autocatalog/management/commands/import_utr_autocatalog.py`
7. `run_utr_nonstop.sh`

### Что сделано и как это снижает риск бана

1. Единый UTR client wrapper
- В `UtrClient` добавлены централизованные safety-механизмы:
  - глобальный rate-limit через shared cache lock/key,
  - ограничение concurrency (clamp до 1..2),
  - retry policy с exponential backoff + jitter,
  - circuit breaker по серии ошибок,
  - кэш ответов (`search`, `applicability`, `detail`, `characteristics`),
  - единые request reasons.
- Это убирает разброс логики по сервисам и исключает «обходы» protection policy.

2. Консервативные настройки по умолчанию
- Добавлены параметры:
  - `UTR_ENABLED`
  - `UTR_RATE_LIMIT_PER_MINUTE`
  - `UTR_CONCURRENCY`
  - `UTR_MAX_RETRIES`
  - `UTR_BACKOFF_BASE_SECONDS`
  - `UTR_CIRCUIT_BREAKER_THRESHOLD`
  - `UTR_CIRCUIT_BREAKER_COOLDOWN_SECONDS`
  - `UTR_APPLICABILITY_ENABLED`
  - `UTR_CHARACTERISTICS_ENABLED`
  - `UTR_FORCE_REFRESH`
  - `UTR_BATCH_SIZE`
- Safe defaults выставлены консервативно (`rate=6/min`, `concurrency=1`, `retries=3`, и т.д.).

3. Убран дублирующий «локальный» throttling в сервисах
- `UtrArticleDetailResolverService` и `UtrAutocatalogImportService` больше не держат собственные hardcoded sleep/retry окна.
- Теперь они используют единый `UtrClient` policy.

4. Дедупликация и resume/cache для applicability
- В `UtrAutocatalogImportService` добавлены:
  - dedupe входного списка detail_id,
  - skip уже обработанных detail_id:
    - по `UtrDetailCarMap` (persisted mapping),
    - по cache-маркеру done для detail_id.
  - `force_refresh` для контролируемого bypass кеша.
- Это сильно снижает повторные вызовы между прогонами.

5. Chunk/batch processing в management command
- `import_utr_autocatalog` теперь обрабатывает detail_id по батчам (`--batch-size`, default из `UTR_BATCH_SIZE`) с агрегированной summary.
- Логирует runtime safety-конфиг на запуск.

6. Безопасный rewrite `run_utr_nonstop.sh`
- Убрана поштучная applicability-фаза `--limit 1 --offset N`.
- Скрипт теперь вызывает batched command-pass (`--batch-size`) и опциональный `--force-refresh`.
- Это исключает самый медленный и неудачный обходной паттерн.

### Значения safe defaults

- `UTR_ENABLED=1`
- `UTR_RATE_LIMIT_PER_MINUTE=6`
- `UTR_CONCURRENCY=1`
- `UTR_MAX_RETRIES=3`
- `UTR_BACKOFF_BASE_SECONDS=2`
- `UTR_CIRCUIT_BREAKER_THRESHOLD=5`
- `UTR_CIRCUIT_BREAKER_COOLDOWN_SECONDS=300`
- `UTR_APPLICABILITY_ENABLED=1`
- `UTR_CHARACTERISTICS_ENABLED=0`
- `UTR_FORCE_REFRESH=0`
- `UTR_BATCH_SIZE=25`
- `UTR_CACHE_TTL_SECONDS=2592000`

---

## Часть C. План дальше

1. Этап 2 (без роста риска): добавить ограниченный batch-resolve для article+brand через `POST /api/search` на малых пачках (например 10-25), под тем же rate-limit wrapper.
2. Добавить отдельный persisted checkpoint-state (БД) для detail_id со статусами `ok/empty/not_found/failed`, чтобы полностью исключить повторные пустые запросы даже при cache reset.
3. Подключить метрики по endpoint-ам UTR (requests/min, 429-rate, cache-hit-rate, circuit-open count).
4. Ввести «safe test profile» для прогона на малой выборке:
   - `UTR_RATE_LIMIT_PER_MINUTE=3`
   - `UTR_CONCURRENCY=1`
   - `UTR_BATCH_SIZE=10`
   - `--limit 50`
5. Не делать:
   - concurrency > 2,
   - перенос тяжелых UTR вызовов в UI,
   - массовый force-refresh без необходимости.

---

## Ответы на контрольные вопросы

1. Используется ли сейчас `utr nonstop`?
- Да, фактические запуски подтверждены в `utr_nonstop.log` (несколько стартов 2026-04-14).

2. Есть ли в проекте более одной реализации UTR-импорта?
- Да.
  - UTR supplier import (прайс/офферы).
  - UTR autocatalog import (`import_utr_autocatalog` + resolver/applicability).
  - Плюс отдельный ручной shell-оркестратор `run_utr_nonstop.sh`.

3. Где именно происходит основной поток запросов к UTR?
- Для проблемы из лога: `import_utr_autocatalog` -> `UtrArticleDetailResolverService.search_details` + `UtrAutocatalogImportService.fetch_applicability`.

4. Что чаще всего дергается: search, detail, applicability, characteristics?
- В проблемном контуре: `search` (резолв) и `applicability` (массовый проход).
- `detail`/`characteristics` в автокаталог-потоке не были активны.

5. Есть ли повторный запрос одного и того же detail_id?
- Да, повторы между прогонами были (видно по `utr_nonstop.log`).

6. Есть ли кэш и реально ли он используется?
- Был частичный:
  - article+brand -> detail_id (DB: `UtrArticleDetailMap`).
- Для applicability до правок полноценного skip-cache не было.
- После правок: cache + persisted skip по `UtrDetailCarMap` + done-маркер в cache.

7. Есть ли progress/resume?
- До правок: только ручные `offset/limit`.
- После правок: resume через skip уже обработанных detail_id (persisted mapping + cache-marker), плюс chunk processing.

8. Есть ли защита от 429 и timeouts?
- До правок: частично и локально, без jitter/circuit/централизации.
- После правок: централизованный retry(backoff+jitter) + circuit breaker + общий limiter в `UtrClient`.

9. Что является главным риском бана прямо сейчас?
- До правок главным риском был длительный поштучный shell-паттерн с повторными однотипными сериями запросов и без общей policy-обертки.
- После правок риск снижен, но остается операционный риск при ручном `force_refresh` и неправильной конфигурации.

10. Какая минимальная безопасная конфигурация запуска?
- `UTR_RATE_LIMIT_PER_MINUTE=3..6`, `UTR_CONCURRENCY=1`, `UTR_BATCH_SIZE=10..25`, `UTR_FORCE_REFRESH=0`.
- Для самого осторожного режима: 3/min, batch 10.

11. Можно ли сократить число запросов без потери функции?
- Да:
  - не дергать applicability повторно для уже обработанных detail_id,
  - использовать persisted mappings + cache markers,
  - использовать batch-size обработку,
  - (следующий этап) аккуратно внедрить batch-search `POST /api/search` для резолва article+brand.

## Final anti-ban hardening

### Что добавлено

1. Global single-run lock
- `import_utr_autocatalog` теперь берет глобальный lock перед любой работой.
- Механизм:
  - PostgreSQL advisory lock (`pg_try_advisory_lock`) через `UtrRunLockService`.
  - fallback для non-PostgreSQL: cache lock с TTL (`UTR_SINGLE_RUN_LOCK_TTL_SECONDS`).
- При уже активном импорте:
  - запуск корректно завершается без работы,
  - пишет `[utr-lock] skipped_due_to_existing_lock=1`.

2. Защита `UTR_FORCE_REFRESH`
- Включен двойной предохранитель:
  - `UTR_FORCE_REFRESH=1`
  - и обязательно `UTR_UNSAFE_ALLOW_FORCE_REFRESH=1`.
- Без второго флага запуск блокируется:
  - `[utr-guard] skipped_due_to_force_refresh_protection=1`.

3. Circuit breaker stop semantics
- При открытом breaker (`429/5xx/timeout` серия) дальнейшие запросы останавливаются:
  - resolve-фаза прерывается и импорт завершается безопасно,
  - applicability-фаза останавливает дальнейшие пачки.
- Выбран максимально безопасный режим:
  - продолжение после cooldown не автоматическое,
  - нужен новый ручной/cron запуск после cooldown.

4. Наблюдаемость (observability)
- В конце каждого запуска команда печатает `[utr-observability]` с counters:
  - `requests_sent_total`
  - `requests_skipped_cache`
  - `retries_total`
  - `timeouts_total`
  - `http_429_total`
  - `http_5xx_total`
  - `circuit_breaker_open_total`
  - `skipped_due_to_existing_lock`
  - `skipped_due_to_force_refresh_protection`

5. Shell orchestration hardening (`run_utr_nonstop.sh`)
- Добавлен shell-level lock:
  - если есть `flock` — non-blocking `flock`;
  - fallback без `flock` — lock directory + PID + stale cleanup.
- Loop теперь уважает защитные маркеры команды:
  - lock skip,
  - force-refresh protection,
  - circuit breaker stop.
- При ошибке management command скрипт не делает агрессивный бесконтрольный рестарт.

### Safe runbook

- Безопасный режим по умолчанию:
  - `UTR_CONCURRENCY=1`
  - `UTR_RATE_LIMIT_PER_MINUTE=6` (допустимый безопасный диапазон 3..6)
  - `UTR_BATCH_SIZE=25` (допустимый безопасный диапазон 10..25)
  - `UTR_FORCE_REFRESH=0`
  - `UTR_UNSAFE_ALLOW_FORCE_REFRESH=0`
- Для максимально осторожного прогона:
  - `UTR_RATE_LIMIT_PER_MINUTE=3`
  - `UTR_BATCH_SIZE=10`
  - `UTR_CONCURRENCY=1`
- Чего делать нельзя:
  - запускать несколько параллельных импортов,
  - включать force refresh без двойного подтверждения,
  - обходить management command через экспериментальные обходные скрипты.

### Smoke подтверждения (локально)

- Force refresh guard:
  - `UTR_FORCE_REFRESH=1 UTR_UNSAFE_ALLOW_FORCE_REFRESH=0 manage.py import_utr_autocatalog ...`
  - результат: `[utr-guard] skipped_due_to_force_refresh_protection=1`, запросы в UTR не отправляются.
- Single-run lock:
  - при удержании lock вторым процессом `manage.py import_utr_autocatalog ...`
  - результат: `[utr-lock] skipped_due_to_existing_lock=1`.
- Circuit breaker stop:
  - при искусственно открытом `utr:circuit_breaker:open_until` import service прекращает проход после первого detail:
  - `stopped_due_to_circuit_breaker=1`, `requests_sent_total=0`.

## Resolve batch search refactor

- Подтверждено по локальному UTR doc: `POST /api/search` принимает массив `details` с `oem+brand` и возвращает массив результатов по индексам.
- Resolve-поток переведен на staged batch search (без изменений applicability):
  1. `primary_brandless`
  2. `fallback_brandless` (если есть fallback article)
  3. `primary_branded` (если есть brand)
  4. `fallback_branded` (если есть fallback + brand)
- Внутри каждого stage запросы дедуплицируются и отправляются пачками.
- Добавлен отдельный параметр:
  - `UTR_RESOLVE_BATCH_SIZE` (safe default `10`).
- Добавлены resolve counters:
  - `resolve_batches_sent_total`
  - `resolve_pairs_sent_total`
  - `resolve_pairs_resolved_total`
  - `resolve_pairs_unresolved_total`
  - `resolve_pairs_ambiguous_total`
  - `resolve_batch_failures_total`
- Логи по batch-поиску:
  - `[resolve-search-batch] stage=... batch=... size=... details_non_empty=... errors=...`
  - при ошибке батча: `failed=1 message=...`

### Stage hit-rate на реальных данных

- Safe benchmark (`resolve-limit=40`, `rate=3/min`, `concurrency=1`) с `UTR_RESOLVE_STAGE_ORDER=brandless_first`:
  - `stage_primary_brandless_attempted_total=40`
  - `stage_primary_brandless_resolved_total=0` (hit-rate 0%)
  - `stage_primary_branded_attempted_total=40`
  - `stage_primary_branded_resolved_total=40` (hit-rate 100%)
  - `resolve_batches_sent_total=8`
  - `resolve_pairs_sent_total=80`
- Контрольный benchmark при `UTR_RESOLVE_STAGE_ORDER=branded_first`:
  - `stage_primary_branded_attempted_total=40`
  - `stage_primary_branded_resolved_total=40` (hit-rate 100%)
  - `stage_primary_brandless_attempted_total=0`
  - `resolve_batches_sent_total=4`
  - `resolve_pairs_sent_total=40`

Вывод:
- Для текущих данных проекта branded-stage существенно эффективнее brandless-stage.
- По умолчанию установлен `UTR_RESOLVE_STAGE_ORDER=branded_first`.
- Это снижает лишние resolve batch-вызовы без роста concurrency и без увеличения мгновенной нагрузки.
