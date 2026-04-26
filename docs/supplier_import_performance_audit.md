# Supplier Import Performance Audit

Дата аудита: 2026-04-26

## Контекст

Цель аудита: найти причины долгой цепочки от скачивания прайса поставщика до публикации товаров и предложить безопасный переход к более производительной модели без потери качества сопоставления.

Проверенная цепочка планового запуска:

1. `request_price_list`
2. `download_price_list`
3. `SupplierImportRunner.run_source(..., reprice=False, reindex=False)`
4. `SupplierMappedOffersPublishService.publish_for_supplier(..., reprice_after_publish=True)`
5. `ProductIndexer.reindex_products(...)`

Код цепочки: `backend/apps/supplier_imports/services/scheduling/pipeline.py`.

## Фактические размеры данных

Снимок локальной БД на момент аудита:

| Таблица | Строк | Размер |
| --- | ---: | ---: |
| `supplier_imports_supplierrawoffer` | ~567k | 1135 MB |
| `supplier_imports_offermatchreview` | ~567k | 148 MB |
| `supplier_imports_importrowerror` | ~128k | 139 MB |
| `pricing_pricehistory` | ~326k | 102 MB |
| `catalog_product` | ~113k | 101 MB |
| `pricing_supplieroffer` | ~113k | 58 MB |
| `pricing_productprice` | ~113k | 27 MB |

Распределение raw-offers:

| Поставщик | Raw rows | Distinct external SKU | Distinct article |
| --- | ---: | ---: | ---: |
| GPL | 83,235 | 16,667 | 16,665 |
| UTR | 483,664 | 101,231 | 100,127 |

Последние успешные/частичные raw-import прогоны:

| Поставщик | Типичный объем | Типичное время raw-import |
| --- | ---: | ---: |
| GPL | ~16.6k rows | ~4-5 минут |
| UTR | ~96-97k rows | ~24-38 минут |

Важно: это только raw-import. Полная scheduled-цепочка дополнительно запускает publish, reprice и reindex.

## Главные узкие места

### 1. Raw-import делает построчную запись

`backend/apps/supplier_imports/services/import_runner/persistence.py`:

- на каждую строку создается `SupplierRawOffer`;
- на каждую строку создается `OfferMatchReview`;
- для невалидных строк создается `ImportRowError`;
- для валидных строк вызывается `SupplierOfferSyncService.upsert_from_raw_offer`.

`SupplierOfferSyncService` использует `update_or_create`, то есть минимум SELECT + INSERT/UPDATE на каждую строку.

Для UTR это около 97k строк за один прайс. Даже без публикации это сотни тысяч ORM-операций на один запуск.

### 2. Raw-offers копятся как история без компактного current-state слоя

`SupplierRawOffer` хранит историю всех запусков. Сейчас в таблице ~484k UTR строк при ~101k уникальных SKU. Публикация вынуждена выбирать актуальные строки из исторической таблицы.

Это полезно для аудита, но плохо как оперативная таблица для публикации.

### 3. Publish также работает построчно

`backend/apps/supplier_imports/services/mapped_offer_publish/service.py`:

- строит кэши брендов, продуктов и supplier-offers;
- итерирует raw-offers;
- на каждую подходящую строку открывает `transaction.atomic`;
- вызывает поштучный upsert продукта;
- вызывает поштучный upsert supplier-offer;
- при необходимости сохраняет связь raw-offer -> product;
- после этого запускает reprice.

При `run_id` публикация UTR сканирует около 97k строк. Без `run_id` селектор потенциально идет по всей истории поставщика.

### 4. Reprice пересчитывает каждый товар отдельно

`backend/apps/pricing/services/repricer.py`:

- `ProductPrice.objects.get_or_create(product=product)`;
- `PriceOverride.objects.filter(...).first()`;
- `SupplierOffer.objects.filter(product=product).select_related("supplier")`;
- `product_price.save(...)`;
- опциональная запись `PriceHistory`.

Для UTR это до ~92k товаров после одного импорта. Даже если логика расчета корректная, текущая реализация делает ее через много отдельных запросов.

### 5. XLSX парсер полностью материализует файл в память

`backend/apps/supplier_imports/services/import_runner/parsing.py` и `backend/apps/supplier_imports/parsers/utils.py`:

- XLSX сначала разбирается в `list[tuple[row_number, row]]`;
- затем превращается в CSV-строку;
- затем снова читается как CSV.

Для 100k строк это терпимо, но это лишняя память и лишний проход. Главная проблема все равно в БД, но парсер стоит перевести на streaming перед очень большими прайсами.

### 6. Есть операционный лимит Celery

`run_scheduled_supplier_pipeline_task` имеет default soft/time limit 120/150 минут. Поэтому полная цепочка UTR на 1-2 часа находится рядом с аварийным порогом, а зависшие/осиротевшие runs уже есть в истории.

## Ответ на гипотезу "сначала импортируем в одну таблицу, потом публикуем в другую"

Да, текущая модель близка к этому:

- raw-stage пишет строки в `SupplierRawOffer`;
- затем часть данных синхронизируется в `SupplierOffer`;
- publish-stage создает/обновляет `Product` и `SupplierOffer`;
- reprice-stage обновляет `ProductPrice`;
- reindex-stage обновляет поисковый индекс.

Проблема не в самой идее staging -> publish, а в том, что staging и publish реализованы через построчный ORM и историческую таблицу как рабочий источник.

## Безопасная целевая модель без раздувания истории

Целевая модель: **не хранить полный raw-snapshot прайса в БД на каждый запуск**.

Прайс поставщика должен быть входным артефактом, а не постоянно растущей operational-таблицей. Рабочее состояние должно хранить только актуальную картину:

1. `ImportRun`:
   - статус запуска;
   - counters;
   - duration по стадиям;
   - ссылка на скачанный файл;
   - quality summary.

2. `ImportRowError`:
   - только ошибки/строки, требующие внимания;
   - retention policy, например 30-90 дней.

3. `SupplierCurrentOffer` или переработанный `SupplierOffer`:
   - одна актуальная строка на `(supplier, supplier_sku)` или `(supplier, normalized_brand, normalized_article)`;
   - поля: цена, остаток, валюта, lead time, product/category mapping, match status, import_run_id, checksum, updated_at;
   - unique constraint для upsert;
   - индексы под publish/reprice.

4. `Product`, `SupplierOffer`, `ProductPrice`:
   - рабочие published/price таблицы;
   - обновляются только по delta.

`SupplierRawOffer` в такой модели не нужен как постоянная таблица всех строк. Его можно оставить только как временный compatibility-layer на период миграции или как debug-sampling по флагу.

После импорта обрабатываются только delta-строки:

- новые SKU;
- изменившаяся цена/остаток/lead time/category/product;
- SKU, исчезнувшие из прайса и требующие `stock_qty=0`, `is_available=False`.

Файл прайса хранится в `media/supplier_price_lists` только временно. В проект добавлена retention policy: скачанные прайсы старше 48 часов удаляются автоматической Celery-задачей `supplier_imports.cleanup_price_list_files`. Для аудита остаются summary запуска и ошибки, но проект не копит XLSX-файлы и БД не раздувается на 100k JSON-строк каждый день.

## Direct-flow модель

Рекомендуемый поток:

1. Скачать XLSX и создать `ImportRun`.
2. Стримить строки прайса.
3. Нормализовать article/brand/SKU.
4. Матчить к существующему `Product`.
5. Считать `content_hash` рабочей части строки.
6. Bulk-upsert актуальных offers/current-offers.
7. Bulk-disable offers, которых нет в новом прайсе.
8. Создать новые `Product` только для уверенно опубликованных новых строк.
9. Bulk-reprice только affected products.
10. Reindex только affected products.

В БД после запуска остаются:

- одна актуальная строка на предложение поставщика;
- актуальная карточка товара;
- актуальная цена;
- summary запуска;
- ошибки/ручная очередь;
- опционально сам файл на диске с retention.

Не остаются:

- 97k новых `SupplierRawOffer` на каждый UTR запуск;
- 97k новых `OfferMatchReview` на каждый запуск;
- полный JSON payload каждой строки в БД.

## План миграции

### Этап 0. Измерение без изменения поведения

Добавить timing по стадиям:

- download wait;
- xlsx parse;
- raw offer build;
- raw bulk insert;
- supplier offer upsert;
- publish scan;
- product upsert;
- offer upsert;
- reprice;
- reindex.

Цель: видеть p50/p95 и количество строк на каждом шаге. Это можно добавить в `ImportRun.summary` и payload scheduled pipeline.

### Этап 1. Быстрые безопасные улучшения

1. Добавить составные индексы:
   - `SupplierRawOffer(source, run, -updated_at, -created_at)`;
   - `SupplierRawOffer(supplier, external_sku, -updated_at)`;
   - `SupplierRawOffer(run, category_mapping_status, mapped_category)`;
   - `SupplierOffer(supplier, supplier_sku)`.

2. В publish всегда требовать `run_id` для scheduled flow и не сканировать всю историю поставщика без явного режима.

3. Отключить проверку GPL-картинок для UTR или явно ограничить ее supplier-specific условием.

4. Разнести publish и reprice/reindex в отдельные Celery задачи с checkpoint-ами, чтобы одна длинная задача не умирала на 150 минутах.

### Этап 2. Direct upsert без постоянного raw-import

Вместо массового создания `SupplierRawOffer` сделать новый importer path:

- нормализация и match остаются теми же;
- raw rows в БД не создаются;
- ошибки пишутся пачками в `ImportRowError`;
- актуальные offers пишутся через bulk upsert;
- `last_seen_run`/`last_seen_at` отмечают присутствие строки в новом прайсе;
- отсутствующие после завершения прайса offers массово выключаются.

Качество сопоставления при этом не меняется, потому что matcher и normalizers остаются прежними. Меняется только место записи результата.

### Этап 3. Current-state таблица поставщика, если не менять `SupplierOffer`

Добавить модель условно `SupplierCurrentOffer`:

- `supplier`;
- `supplier_sku`;
- `article`, `normalized_article`;
- `brand_name`, `normalized_brand`;
- `product_name`;
- `price`, `currency`, `stock_qty`, `lead_time_days`;
- `matched_product`, `mapped_category`;
- `match_status`, `category_mapping_status`;
- `last_seen_run`, `last_seen_at`;
- `content_hash`;
- `is_active`.

Unique:

- `(supplier, supplier_sku)`.

Индексы:

- `(supplier, is_active)`;
- `(supplier, last_seen_run)`;
- `(matched_product)`;
- `(mapped_category, category_mapping_status)`.

Если `SupplierOffer` нельзя быстро сделать upsert-friendly по `(supplier, supplier_sku)`, добавляем `SupplierCurrentOffer` как промежуточную актуальную таблицу. Если можно безопасно изменить модель `SupplierOffer`, отдельная current-таблица не обязательна.

### Этап 4. Delta-publish

После current upsert:

1. Отметить `changed=True` только для строк, где изменился hash или product/category mapping.
2. Publish обрабатывает только `changed=True` и исчезнувшие из прайса позиции.
3. `SupplierOffer` обновляется bulk-upsert-ом.
4. Product создается только для новых publishable строк, а не проверяется для каждой исторической строки.
5. Reprice получает только affected product ids.

Ожидаемый эффект: повторный UTR импорт, где изменились только цены/остатки, не должен проходить через 97k полных publish операций.

### Этап 5. Bulk repricing

Сохранить текущую business-логику выбора лучшего оффера, но добавить bulk-вариант:

- загрузить все offers для affected products одним queryset;
- сгруппировать в памяти по product_id;
- загрузить `ProductPrice` одним queryset;
- загрузить overrides одним queryset;
- рассчитать цены в Python;
- `bulk_create` недостающих `ProductPrice`;
- `bulk_update` изменившихся `ProductPrice`;
- `PriceHistory.bulk_create` только для реально изменившихся цен;
- `Product.objects.filter(id__in=...).update(is_active=True, published_at=...)` для массовой активации.

Это самый большой выигрыш после bulk-upsert офферов.

### Этап 6. Streaming parser

Для XLSX перейти на streaming reader:

- предпочтительно `openpyxl.load_workbook(read_only=True, data_only=True)`;
- или оставить текущий zip/xml parser, но отдавать generator строк, не `list` и не CSV-промежуточный слой.

Это снизит память и уберет лишний проход, но не заменяет DB bulk-оптимизацию.

## Контроль качества и откат

Для каждого этапа:

1. Прогонять GPL и UTR на одном и том же скачанном XLSX.
2. Сравнивать:
   - `parsed_rows`;
   - `offers_created/updated/skipped`;
   - match rate;
   - error rate;
   - количество active/inactive supplier offers;
   - выборочный diff цен `ProductPrice`;
   - count affected products.
3. Держать feature flag:
   - `SUPPLIER_IMPORT_BULK_MODE=0/1`;
   - `SUPPLIER_CURRENT_OFFER_PUBLISH=0/1`;
   - `PRICING_BULK_REPRICE=0/1`.
4. Включать по поставщику:
   - сначала GPL;
   - затем UTR на dry-run/копии файла;
   - потом UTR в production flow.

## Приоритеты

1. Сначала убрать постоянное создание `SupplierRawOffer`/`OfferMatchReview` для обычного UTR/GPL импорта.
2. Затем current-state или upsert-friendly `SupplierOffer`.
3. Затем bulk repricing.
4. Потом streaming parser и чистка/архивация старой истории.

Ожидаемый безопасный результат: UTR импорт должен перейти из "создать 100k исторических строк + потом опубликовать" в "обновить актуальные offers + обработать delta". БД перестает расти линейно от каждого прайса, а полная цепочка перестает зависеть от размера истории.
