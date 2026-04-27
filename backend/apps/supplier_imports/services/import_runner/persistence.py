from __future__ import annotations

import time
from collections import Counter
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.catalog.models import Product
from apps.pricing.models import SupplierOffer
from apps.supplier_imports.models import (
    ImportArtifact,
    ImportRowError,
    ImportRun,
    ImportSource,
    OfferMatchReview,
    SupplierRawOffer,
)
from apps.supplier_imports.parsers import ParseResult


@transaction.atomic
def persist_parsed_rows(
    service,
    *,
    run: ImportRun,
    source: ImportSource,
    artifact: ImportArtifact,
    parse_result: ParseResult,
    dry_run: bool,
    matcher,
    supplier_offer_sync,
    article_normalizer,
    brand_resolver,
) -> tuple[int, int, int, int, set[str]]:
    if _uses_current_offer_persistence(source=source):
        return persist_current_offer_rows(
            service,
            run=run,
            source=source,
            artifact=artifact,
            parse_result=parse_result,
            dry_run=dry_run,
            matcher=matcher,
            article_normalizer=article_normalizer,
            brand_resolver=brand_resolver,
        )

    return persist_raw_history_rows(
        service,
        run=run,
        source=source,
        artifact=artifact,
        parse_result=parse_result,
        dry_run=dry_run,
        matcher=matcher,
        supplier_offer_sync=supplier_offer_sync,
        article_normalizer=article_normalizer,
        brand_resolver=brand_resolver,
    )


def persist_raw_history_rows(
    service,
    *,
    run: ImportRun,
    source: ImportSource,
    artifact: ImportArtifact,
    parse_result: ParseResult,
    dry_run: bool,
    matcher,
    supplier_offer_sync,
    article_normalizer,
    brand_resolver,
) -> tuple[int, int, int, int, set[str]]:
    created = 0
    updated = 0
    skipped = 0
    errors_count = 0
    affected_products: set[str] = set()

    for issue in parse_result.issues:
        service._create_row_error(
            run=run,
            source=source,
            artifact=artifact,
            message=issue.message,
            row_number=issue.row_number,
            external_sku=issue.external_sku,
            error_code=issue.error_code,
            raw_payload=issue.raw_payload,
        )
        errors_count += 1

    for row_index, offer in enumerate(parse_result.offers, start=1):
        article_result = article_normalizer.normalize(article=offer.article or offer.external_sku, source=source)
        brand_result = brand_resolver.resolve(brand_name=offer.brand_name, source=source, supplier=source.supplier)

        decision = matcher.evaluate_offer(
            article=offer.article,
            external_sku=offer.external_sku,
            brand_name=brand_result.canonical_brand or offer.brand_name,
            source=source,
            supplier=source.supplier,
        )
        product = decision.matched_product
        mapped_category = product.category if product is not None and product.category_id else None
        if mapped_category is not None:
            category_mapping_status = SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED
            category_mapping_reason = SupplierRawOffer.CATEGORY_MAPPING_REASON_FROM_PRODUCT
            category_mapping_confidence = Decimal("1.000")
        else:
            category_mapping_status = SupplierRawOffer.CATEGORY_MAPPING_STATUS_UNMAPPED
            category_mapping_reason = SupplierRawOffer.CATEGORY_MAPPING_REASON_NO_CATEGORY_SIGNAL
            category_mapping_confidence = None
        candidate_product_ids = [str(item.id) for item in decision.candidate_products]
        skip_reason = ""
        is_valid = True

        if offer.price is None:
            is_valid = False
            skip_reason = "missing_price"
        elif decision.status != SupplierRawOffer.MATCH_STATUS_AUTO_MATCHED:
            is_valid = False
            skip_reason = decision.reason or decision.status
        elif product is None:
            is_valid = False
            skip_reason = decision.reason or "product_not_found"

        now = timezone.now()
        raw_offer = SupplierRawOffer.objects.create(
            run=run,
            source=source,
            supplier=source.supplier,
            artifact=artifact,
            row_number=row_index,
            external_sku=offer.external_sku[:128],
            article=offer.article[:128],
            normalized_article=article_result.normalized_article[:128],
            brand_name=offer.brand_name[:180],
            normalized_brand=brand_result.normalized_brand[:180],
            product_name=offer.product_name[:255],
            currency=offer.currency[:3],
            price=offer.price,
            stock_qty=offer.stock_qty,
            lead_time_days=offer.lead_time_days,
            matched_product=product,
            mapped_category=mapped_category,
            category_mapping_status=category_mapping_status,
            category_mapping_reason=category_mapping_reason,
            category_mapping_confidence=category_mapping_confidence,
            category_mapped_at=now if mapped_category is not None else None,
            match_status=decision.status,
            match_reason=decision.reason,
            match_candidate_product_ids=candidate_product_ids,
            matching_attempts=1,
            last_matched_at=now,
            article_normalization_trace=article_result.trace,
            brand_normalization_trace=brand_result.trace,
            is_valid=is_valid,
            skip_reason=skip_reason,
            raw_payload=offer.raw_payload,
        )
        OfferMatchReview.objects.create(
            raw_offer=raw_offer,
            action=OfferMatchReview.ACTION_AUTO_ATTEMPT,
            status_before="",
            status_after=decision.status,
            reason=decision.reason,
            candidate_product_ids=candidate_product_ids,
            selected_product=product,
        )

        utr_detail_id = service._extract_utr_detail_id(source=source, raw_payload=offer.raw_payload)
        if not dry_run and product is not None and utr_detail_id:
            attach_utr_detail_id(product=product, utr_detail_id=utr_detail_id)

        if not is_valid or product is None or offer.price is None:
            skipped += 1
            service._create_row_error(
                run=run,
                source=source,
                artifact=artifact,
                row_number=row_index,
                external_sku=offer.external_sku,
                error_code=skip_reason or "invalid_row",
                message=f"Offer skipped: {skip_reason or 'invalid_row'}.",
                raw_payload=offer.raw_payload,
            )
            errors_count += 1
            continue

        if not dry_run:
            _, was_created = supplier_offer_sync.upsert_from_raw_offer(raw_offer)
            if was_created:
                created += 1
            else:
                updated += 1
            affected_products.add(str(product.id))
        else:
            supplier_sku = (offer.external_sku or offer.article)[:128]
            existing = SupplierOffer.objects.filter(
                supplier=source.supplier,
                product=product,
                supplier_sku=supplier_sku,
            ).first()
            if existing is None:
                created += 1
            else:
                updated += 1

    return created, updated, skipped, errors_count, affected_products


def persist_current_offer_rows(
    service,
    *,
    run: ImportRun,
    source: ImportSource,
    artifact: ImportArtifact,
    parse_result: ParseResult,
    dry_run: bool,
    matcher,
    article_normalizer,
    brand_resolver,
) -> tuple[int, int, int, int, set[str]]:
    created = 0
    updated = 0
    skipped = 0
    errors_count = 0
    affected_products: set[str] = set()
    row_errors: list[ImportRowError] = []
    match_status_counts: Counter[str] = Counter()
    category_status_counts: Counter[str] = Counter()
    now = timezone.now()
    timings: dict[str, float | int] = {
        "parse_issues": len(parse_result.issues),
        "parsed_offers": len(parse_result.offers),
    }

    issues_started = time.perf_counter()
    for issue in parse_result.issues:
        row_errors.append(
            _build_row_error(
                run=run,
                source=source,
                artifact=artifact,
                message=issue.message,
                row_number=issue.row_number,
                external_sku=issue.external_sku,
                error_code=issue.error_code,
                raw_payload=issue.raw_payload,
            )
        )
        errors_count += 1
    timings["parse_issue_errors_sec"] = _elapsed_seconds(issues_started)

    valid_rows: dict[tuple[str, str], dict] = {}
    seen_supplier_skus: set[str] = set()
    utr_detail_updates: dict[str, str] = {}

    match_loop_started = time.perf_counter()
    for row_index, offer in enumerate(parse_result.offers, start=1):
        decision = matcher.evaluate_offer(
            article=offer.article,
            external_sku=offer.external_sku,
            brand_name=offer.brand_name,
            source=source,
            supplier=source.supplier,
        )
        product = decision.matched_product
        if product is not None and product.category_id:
            category_mapping_status = SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED
        else:
            category_mapping_status = SupplierRawOffer.CATEGORY_MAPPING_STATUS_UNMAPPED

        match_status_counts[decision.status] += 1
        category_status_counts[category_mapping_status] += 1

        supplier_sku = ((offer.external_sku or offer.article) or "")[:128]
        skip_reason = ""
        is_valid = True

        if offer.price is None:
            is_valid = False
            skip_reason = "missing_price"
        elif not supplier_sku:
            is_valid = False
            skip_reason = "missing_supplier_sku"
        elif decision.status != SupplierRawOffer.MATCH_STATUS_AUTO_MATCHED:
            is_valid = False
            skip_reason = decision.reason or decision.status
        elif product is None:
            is_valid = False
            skip_reason = decision.reason or "product_not_found"

        if not is_valid or product is None or offer.price is None:
            skipped += 1
            row_errors.append(
                _build_row_error(
                    run=run,
                    source=source,
                    artifact=artifact,
                    row_number=row_index,
                    external_sku=offer.external_sku,
                    error_code=skip_reason or "invalid_row",
                    message=f"Offer skipped: {skip_reason or 'invalid_row'}.",
                    raw_payload=offer.raw_payload,
                )
            )
            errors_count += 1
            continue

        seen_supplier_skus.add(supplier_sku)
        product_id = str(product.id)
        valid_rows[(product_id, supplier_sku)] = {
            "product": product,
            "supplier_sku": supplier_sku,
            "currency": offer.currency[:3],
            "purchase_price": offer.price,
            "price_levels": list(offer.price_levels or []),
            "stock_qty": max(offer.stock_qty, 0),
            "lead_time_days": max(offer.lead_time_days, 0),
            "is_available": offer.stock_qty > 0 and offer.price > Decimal("0"),
        }

        utr_detail_id = service._extract_utr_detail_id(source=source, raw_payload=offer.raw_payload)
        if product_id and utr_detail_id:
            utr_detail_updates[product_id] = utr_detail_id
    timings["match_loop_sec"] = _elapsed_seconds(match_loop_started)
    timings["unique_valid_offers"] = len(valid_rows)
    timings["seen_supplier_skus"] = len(seen_supplier_skus)
    timings["row_errors"] = len(row_errors)

    if row_errors:
        row_errors_started = time.perf_counter()
        ImportRowError.objects.bulk_create(row_errors, batch_size=1000)
        timings["row_errors_bulk_create_sec"] = _elapsed_seconds(row_errors_started)
    else:
        timings["row_errors_bulk_create_sec"] = 0.0

    if dry_run:
        dry_run_started = time.perf_counter()
        existing_keys = set(
            SupplierOffer.objects.filter(
                supplier=source.supplier,
                supplier_sku__in=seen_supplier_skus,
            ).values_list("product_id", "supplier_sku")
        )
        existing_str_keys = {(str(product_id), sku) for product_id, sku in existing_keys}
        created = sum(1 for key in valid_rows if key not in existing_str_keys)
        updated = max(len(valid_rows) - created, 0)
        timings["dry_run_existing_lookup_sec"] = _elapsed_seconds(dry_run_started)
    elif valid_rows:
        existing_load_started = time.perf_counter()
        existing_offers = list(
            SupplierOffer.objects.filter(
                supplier=source.supplier,
                supplier_sku__in=seen_supplier_skus,
            ).values(
                "id",
                "product_id",
                "supplier_sku",
                "currency",
                "purchase_price",
                "price_levels",
                "stock_qty",
                "lead_time_days",
                "is_available",
            )
        )
        timings["existing_offers_load_sec"] = _elapsed_seconds(existing_load_started)
        timings["existing_offers_loaded"] = len(existing_offers)

        existing_index_started = time.perf_counter()
        existing_by_key = {(str(offer["product_id"]), offer["supplier_sku"]): offer for offer in existing_offers}
        existing_by_sku: dict[str, list[dict]] = {}
        for existing in existing_offers:
            existing_by_sku.setdefault(existing["supplier_sku"], []).append(existing)
        timings["existing_index_build_sec"] = _elapsed_seconds(existing_index_started)

        offers_to_create: list[SupplierOffer] = []
        offers_to_update: list[SupplierOffer] = []
        stale_offers_to_disable: list[SupplierOffer] = []
        seen_existing_offer_ids: list[str] = []

        diff_started = time.perf_counter()
        for key, row in valid_rows.items():
            product_id, supplier_sku = key
            existing = existing_by_key.get(key)
            if existing is None:
                offers_to_create.append(
                    SupplierOffer(
                        supplier=source.supplier,
                        product=row["product"],
                        supplier_sku=supplier_sku,
                        currency=row["currency"],
                        purchase_price=row["purchase_price"],
                        price_levels=row["price_levels"],
                        stock_qty=row["stock_qty"],
                        lead_time_days=row["lead_time_days"],
                        is_available=row["is_available"],
                        last_seen_at=now,
                        created_at=now,
                        updated_at=now,
                    )
                )
                affected_products.add(product_id)
            else:
                seen_existing_offer_ids.append(str(existing["id"]))
                changed = (
                    existing["currency"] != row["currency"]
                    or existing["purchase_price"] != row["purchase_price"]
                    or existing["price_levels"] != row["price_levels"]
                    or existing["stock_qty"] != row["stock_qty"]
                    or existing["lead_time_days"] != row["lead_time_days"]
                    or existing["is_available"] != row["is_available"]
                )
                if changed:
                    offers_to_update.append(
                        SupplierOffer(
                            id=existing["id"],
                            currency=row["currency"],
                            purchase_price=row["purchase_price"],
                            price_levels=row["price_levels"],
                            stock_qty=row["stock_qty"],
                            lead_time_days=row["lead_time_days"],
                            is_available=row["is_available"],
                            last_seen_at=now,
                            updated_at=now,
                        )
                    )
                    affected_products.add(product_id)

            for stale in existing_by_sku.get(supplier_sku, []):
                if str(stale["product_id"]) == product_id:
                    continue
                if stale["is_available"] or stale["stock_qty"] != 0:
                    stale_offers_to_disable.append(
                        SupplierOffer(
                            id=stale["id"],
                            stock_qty=0,
                            is_available=False,
                            updated_at=now,
                        )
                    )
                    affected_products.add(str(stale["product_id"]))
        timings["diff_rows_sec"] = _elapsed_seconds(diff_started)
        timings["offers_to_create"] = len(offers_to_create)
        timings["offers_to_update"] = len(offers_to_update)
        timings["stale_offers_to_disable"] = len(stale_offers_to_disable)
        timings["seen_existing_offers"] = len(seen_existing_offer_ids)

        if offers_to_create:
            bulk_create_started = time.perf_counter()
            SupplierOffer.objects.bulk_create(offers_to_create, batch_size=1000)
            created += len(offers_to_create)
            timings["offers_bulk_create_sec"] = _elapsed_seconds(bulk_create_started)
        else:
            timings["offers_bulk_create_sec"] = 0.0
        if offers_to_update:
            bulk_update_started = time.perf_counter()
            SupplierOffer.objects.bulk_update(
                offers_to_update,
                fields=("currency", "purchase_price", "price_levels", "stock_qty", "lead_time_days", "is_available", "last_seen_at", "updated_at"),
                batch_size=1000,
            )
            updated += len(offers_to_update)
            timings["offers_bulk_update_sec"] = _elapsed_seconds(bulk_update_started)
        else:
            timings["offers_bulk_update_sec"] = 0.0
        if seen_existing_offer_ids:
            last_seen_started = time.perf_counter()
            SupplierOffer.objects.filter(id__in=seen_existing_offer_ids).update(last_seen_at=now)
            timings["offers_last_seen_update_sec"] = _elapsed_seconds(last_seen_started)
        else:
            timings["offers_last_seen_update_sec"] = 0.0
        if stale_offers_to_disable:
            stale_update_started = time.perf_counter()
            SupplierOffer.objects.bulk_update(
                stale_offers_to_disable,
                fields=("stock_qty", "is_available", "updated_at"),
                batch_size=1000,
            )
            updated += len(stale_offers_to_disable)
            timings["stale_offers_bulk_update_sec"] = _elapsed_seconds(stale_update_started)
        else:
            timings["stale_offers_bulk_update_sec"] = 0.0

        if _should_disable_missing_offers(source=source, seen_supplier_skus=seen_supplier_skus):
            disable_missing_started = time.perf_counter()
            missing_offer_ids: list[str] = []
            missing_product_ids: set[str] = set()
            available_scan_count = 0
            available_rows = SupplierOffer.objects.filter(
                supplier=source.supplier,
                is_available=True,
            ).values("id", "product_id", "supplier_sku").iterator(chunk_size=5000)
            for available in available_rows:
                available_scan_count += 1
                if available["supplier_sku"] in seen_supplier_skus:
                    continue
                missing_offer_ids.append(str(available["id"]))
                if available["product_id"]:
                    missing_product_ids.add(str(available["product_id"]))
            disabled_count = 0
            if missing_offer_ids:
                disabled_count = SupplierOffer.objects.filter(id__in=missing_offer_ids).update(
                    is_available=False,
                    stock_qty=0,
                    updated_at=now,
                )
            if disabled_count:
                updated += int(disabled_count)
                affected_products.update(missing_product_ids)
            timings["disable_missing_sec"] = _elapsed_seconds(disable_missing_started)
            timings["disable_missing_available_scanned"] = available_scan_count
            timings["disable_missing_count"] = int(disabled_count)
        else:
            timings["disable_missing_sec"] = 0.0
            timings["disable_missing_available_scanned"] = 0
            timings["disable_missing_count"] = 0

        if utr_detail_updates:
            utr_detail_started = time.perf_counter()
            _bulk_attach_utr_detail_ids(updates=utr_detail_updates)
            timings["utr_detail_attach_sec"] = _elapsed_seconds(utr_detail_started)
            timings["utr_detail_candidates"] = len(utr_detail_updates)
        else:
            timings["utr_detail_attach_sec"] = 0.0
            timings["utr_detail_candidates"] = 0

    summary = run.summary if isinstance(run.summary, dict) else {}
    summary["persistence_mode"] = "current_offers"
    summary["match_status_counts"] = dict(match_status_counts)
    summary["category_status_counts"] = dict(category_status_counts)
    summary["current_offer_rows"] = {
        "unique_valid_offers": len(valid_rows),
        "seen_supplier_skus": len(seen_supplier_skus),
        "row_errors": len(row_errors),
        "disable_missing_offers": _should_disable_missing_offers(source=source, seen_supplier_skus=seen_supplier_skus),
    }
    summary["row_error_retention"] = _cleanup_old_row_errors(source=source)
    summary["current_offer_timings"] = timings
    run.summary = summary
    return created, updated, skipped, errors_count, affected_products


def attach_utr_detail_id(*, product: Product, utr_detail_id: str) -> None:
    if product.utr_detail_id == utr_detail_id:
        return
    if product.utr_detail_id:
        return
    product.utr_detail_id = utr_detail_id
    product.save(update_fields=("utr_detail_id", "updated_at"))


def _bulk_attach_utr_detail_ids(*, updates: dict[str, str]) -> None:
    products = list(Product.objects.filter(id__in=updates.keys(), utr_detail_id=""))
    if not products:
        return
    now = timezone.now()
    to_update: list[Product] = []
    for product in products:
        utr_detail_id = updates.get(str(product.id), "")
        if not utr_detail_id:
            continue
        product.utr_detail_id = utr_detail_id
        product.updated_at = now
        to_update.append(product)
    if to_update:
        Product.objects.bulk_update(to_update, fields=("utr_detail_id", "updated_at"), batch_size=1000)


def create_row_error(
    *,
    run: ImportRun,
    source: ImportSource,
    message: str,
    artifact: ImportArtifact | None = None,
    row_number: int | None = None,
    external_sku: str = "",
    error_code: str = "import_error",
    raw_payload: dict | None = None,
) -> None:
    ImportRowError.objects.create(
        **_row_error_kwargs(
            run=run,
            source=source,
            artifact=artifact,
            row_number=row_number,
            external_sku=external_sku,
            error_code=error_code,
            message=message,
            raw_payload=raw_payload,
        )
    )


def _build_row_error(
    *,
    run: ImportRun,
    source: ImportSource,
    message: str,
    artifact: ImportArtifact | None = None,
    row_number: int | None = None,
    external_sku: str = "",
    error_code: str = "import_error",
    raw_payload: dict | None = None,
) -> ImportRowError:
    return ImportRowError(
        **_row_error_kwargs(
            run=run,
            source=source,
            artifact=artifact,
            row_number=row_number,
            external_sku=external_sku,
            error_code=error_code,
            message=message,
            raw_payload=raw_payload,
        )
    )


def _row_error_kwargs(
    *,
    run: ImportRun,
    source: ImportSource,
    message: str,
    artifact: ImportArtifact | None = None,
    row_number: int | None = None,
    external_sku: str = "",
    error_code: str = "import_error",
    raw_payload: dict | None = None,
) -> dict:
    return {
        "run": run,
        "source": source,
        "artifact": artifact,
        "row_number": row_number,
        "external_sku": external_sku[:128],
        "error_code": error_code[:64],
        "message": message,
        "raw_payload": raw_payload or {},
    }


def _uses_current_offer_persistence(*, source: ImportSource) -> bool:
    parser_options = source.parser_options if isinstance(source.parser_options, dict) else {}
    explicit_mode = str(parser_options.get("persistence_mode") or "").strip().lower()
    if explicit_mode in {"raw", "raw_history", "history"}:
        return False
    if explicit_mode in {"current", "current_offers", "direct", "lean"}:
        return True

    current_sources = {
        str(item).strip().lower()
        for item in getattr(settings, "SUPPLIER_IMPORT_CURRENT_OFFER_SOURCES", ())
        if str(item).strip()
    }
    return source.code.lower() in current_sources


def uses_current_offer_persistence(*, source: ImportSource) -> bool:
    return _uses_current_offer_persistence(source=source)


def _cleanup_old_row_errors(*, source: ImportSource) -> dict[str, int]:
    keep_runs = _row_error_retention_runs(source=source)
    if keep_runs <= 0:
        return {
            "enabled": 0,
            "keep_runs": keep_runs,
            "deleted": 0,
        }

    retained_run_ids = list(
        ImportRun.objects.filter(source=source)
        .order_by("-started_at", "-created_at")
        .values_list("id", flat=True)[:keep_runs]
    )
    if not retained_run_ids:
        return {
            "enabled": 1,
            "keep_runs": keep_runs,
            "deleted": 0,
        }

    deleted_count, _ = ImportRowError.objects.filter(source=source).exclude(run_id__in=retained_run_ids).delete()
    return {
        "enabled": 1,
        "keep_runs": keep_runs,
        "retained_runs": len(retained_run_ids),
        "deleted": int(deleted_count),
    }


def _row_error_retention_runs(*, source: ImportSource) -> int:
    parser_options = source.parser_options if isinstance(source.parser_options, dict) else {}
    if "row_error_retention_runs" in parser_options:
        try:
            return max(int(parser_options.get("row_error_retention_runs") or 0), 0)
        except (TypeError, ValueError):
            return 0
    return max(int(getattr(settings, "SUPPLIER_IMPORT_ROW_ERROR_RETENTION_RUNS", 5)), 0)


def _elapsed_seconds(started_at: float) -> float:
    return round(time.perf_counter() - started_at, 3)


def _should_disable_missing_offers(*, source: ImportSource, seen_supplier_skus: set[str]) -> bool:
    if not seen_supplier_skus:
        return False
    parser_options = source.parser_options if isinstance(source.parser_options, dict) else {}
    raw_value = parser_options.get("disable_missing_offers", True)
    return raw_value is not False
