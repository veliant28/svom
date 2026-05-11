from __future__ import annotations

import time
from collections import Counter, defaultdict
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.catalog.models import Brand, Category, Product
from apps.catalog.services.product_management import generate_unique_product_slug, sanitize_product_name
from apps.catalog.services.svom_sku import ensure_product_svom_sku
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
from apps.supplier_imports.services.gpl_images import GplProductImageService
from apps.supplier_imports.services.gpl_import_category_assignment import (
    MAPPING_STATUS_ASSIGNED_GROUP,
    MAPPING_STATUS_ASSIGNED_ROW,
    MAPPING_STATUS_CONFLICT,
    MAPPING_STATUS_IGNORED,
    MAPPING_STATUS_MISSING,
    MAPPING_STATUS_NEEDS,
    GplImportCategoryAssignmentResolver,
    GroupAssignmentDecision,
)


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
    raw_rows_written = 0
    match_reviews_written = 0
    would_create_raw_rows = 0
    would_create_match_reviews = 0

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
        source_product_name = sanitize_product_name(str(offer.product_name or ""))[:255]
        if not source_product_name:
            source_product_name = sanitize_product_name(offer.article or offer.external_sku or "Product")[:255] or "Product"

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
        raw_offer = None
        if dry_run:
            would_create_raw_rows += 1
            would_create_match_reviews += 1
        else:
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
                product_name=source_product_name,
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
            raw_rows_written += 1
            OfferMatchReview.objects.create(
                raw_offer=raw_offer,
                action=OfferMatchReview.ACTION_AUTO_ATTEMPT,
                status_before="",
                status_after=decision.status,
                reason=decision.reason,
                candidate_product_ids=candidate_product_ids,
                selected_product=product,
            )
            match_reviews_written += 1

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

    summary = run.summary if isinstance(run.summary, dict) else {}
    summary["persistence_mode"] = "raw_history"
    summary["raw_history_rows"] = {
        "parsed_offers": len(parse_result.offers),
        "raw_rows_written": int(raw_rows_written),
        "match_reviews_written": int(match_reviews_written),
        "would_create_raw_rows": int(would_create_raw_rows),
        "would_create_match_reviews": int(would_create_match_reviews),
    }
    run.summary = summary

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
    gpl_mapping_status_counts: Counter[str] = Counter()
    now = timezone.now()
    timings: dict[str, float | int] = {
        "parse_issues": len(parse_result.issues),
        "parsed_offers": len(parse_result.offers),
    }
    bootstrap_unmatched = _should_bootstrap_unmatched_current_offers(source=source)
    persist_raw_rows = _should_persist_raw_rows_for_current_offers(source=source, bootstrap_unmatched=bootstrap_unmatched)
    bootstrap_products_created = 0
    bootstrap_products_reused = 0
    bootstrap_products_would_create = 0
    bootstrap_products_would_reuse = 0
    raw_offers_written = 0
    image_detected_count = 0
    price_non_null_count = 0
    stock_non_null_count = 0
    stock_positive_count = 0
    stock_values_suspicious_count = 0
    rows_with_suspicious_stock = 0
    stock_values_ignored = 0
    max_stock_total_after_normalization = 0
    brand_detected_count = 0
    products_with_gpl_primary_image_would: set[str] = set()
    gpl_invalid_target_count = 0
    gpl_non_assignable_target_count = 0
    gpl_missing_target_count = 0
    summary_images = {
        "products_updated": 0,
        "created": 0,
        "reused": 0,
        "stale_marked": 0,
    }

    gpl_resolver: GplImportCategoryAssignmentResolver | None = None
    gpl_group_decisions: dict[tuple[str, str], GroupAssignmentDecision] = {}
    gpl_categories_by_slug: dict[str, Category] = {}
    is_gpl_source = str(getattr(source, "code", "") or "").strip().lower() == "gpl"
    if is_gpl_source:
        gpl_resolver = GplImportCategoryAssignmentResolver()
        gpl_group_decisions = _build_gpl_group_decisions(parse_result=parse_result, resolver=gpl_resolver)
        gpl_categories_by_slug = {
            str(item.slug): item
            for item in Category.objects.filter(is_active=True, is_assignable=True).only("id", "slug", "is_assignable")
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
        if offer.price is not None:
            price_non_null_count += 1
        if offer.stock_qty is not None:
            stock_non_null_count += 1
            if int(offer.stock_qty) > 0:
                stock_positive_count += 1
            if int(offer.stock_qty) > max_stock_total_after_normalization:
                max_stock_total_after_normalization = int(offer.stock_qty)
        if str(offer.brand_name or "").strip():
            brand_detected_count += 1

        stock_meta = {}
        if isinstance(offer.raw_payload, dict):
            stock_meta = offer.raw_payload.get("_utr_stock_normalization") or {}
        suspicious_per_row = int(stock_meta.get("stock_values_suspicious_count", 0) or 0)
        ignored_per_row = int(stock_meta.get("stock_values_ignored", 0) or 0)
        stock_values_suspicious_count += suspicious_per_row
        stock_values_ignored += ignored_per_row
        if suspicious_per_row > 0:
            rows_with_suspicious_stock += 1

        row_payload = _gpl_row_payload(offer=offer)
        image_url = _extract_gpl_image_url(payload=row_payload)
        if image_url:
            image_detected_count += 1

        decision = matcher.evaluate_offer(
            article=offer.article,
            external_sku=offer.external_sku,
            brand_name=offer.brand_name,
            source=source,
            supplier=source.supplier,
        )
        product = decision.matched_product
        mapped_category = product.category if product is not None and product.category_id else None
        gpl_row_decision = None
        if gpl_resolver is not None:
            group_key = _gpl_group_key(payload=row_payload)
            group_decision = gpl_group_decisions.get(group_key)
            gpl_row_decision = gpl_resolver.decide_row(
                row=row_payload,
                group_decision=group_decision,
            )
            gpl_mapping_status_counts[gpl_row_decision.mapping_status] += 1
            gpl_invalid_target_count += int(gpl_row_decision.invalid_target)
            gpl_non_assignable_target_count += int(gpl_row_decision.non_assignable_target)
            gpl_missing_target_count += int(gpl_row_decision.missing_target)
            if mapped_category is None and gpl_row_decision.category_is_assignable and gpl_row_decision.proposed_category_slug:
                mapped_category = gpl_categories_by_slug.get(gpl_row_decision.proposed_category_slug)

        if mapped_category is not None:
            category_mapping_status = SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED
            category_mapping_reason = _resolve_category_mapping_reason(gpl_row_decision=gpl_row_decision, fallback="from_product")
            category_mapping_confidence = _resolve_category_mapping_confidence(gpl_row_decision=gpl_row_decision, fallback=Decimal("1.000"))
        else:
            category_mapping_status = (
                SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW
                if gpl_row_decision is not None
                else SupplierRawOffer.CATEGORY_MAPPING_STATUS_UNMAPPED
            )
            category_mapping_reason = _resolve_category_mapping_reason(gpl_row_decision=gpl_row_decision, fallback="no_category_signal")
            category_mapping_confidence = _resolve_category_mapping_confidence(gpl_row_decision=gpl_row_decision, fallback=None)
        match_status_counts[decision.status] += 1
        category_status_counts[category_mapping_status] += 1

        supplier_sku = ((offer.external_sku or offer.article) or "")[:128]
        skip_reason = ""
        is_valid = True
        used_bootstrap_product = False

        if offer.price is None:
            is_valid = False
            skip_reason = "missing_price"
        elif not supplier_sku:
            is_valid = False
            skip_reason = "missing_supplier_sku"
        elif decision.status == SupplierRawOffer.MATCH_STATUS_AUTO_MATCHED and product is None:
            is_valid = False
            skip_reason = decision.reason or "product_not_found"
        elif decision.status != SupplierRawOffer.MATCH_STATUS_AUTO_MATCHED:
            if bootstrap_unmatched:
                if not dry_run:
                    product, product_created = _get_or_create_bootstrap_product_for_offer(
                        source=source,
                        offer=offer,
                        supplier_sku=supplier_sku,
                        mapped_category=mapped_category,
                    )
                    used_bootstrap_product = True
                    if product_created:
                        bootstrap_products_created += 1
                    else:
                        bootstrap_products_reused += 1
                else:
                    bootstrap_products_would_create += 1
            else:
                is_valid = False
                skip_reason = decision.reason or decision.status

        if not is_valid or (product is None and not dry_run) or offer.price is None:
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

        if persist_raw_rows:
            source_product_name = sanitize_product_name(str(offer.product_name or ""))[:255]
            if not source_product_name:
                source_product_name = sanitize_product_name(offer.article or offer.external_sku or "Product")[:255] or "Product"
            article_result = article_normalizer.normalize(article=offer.article or offer.external_sku, source=source)
            brand_result = brand_resolver.resolve(brand_name=offer.brand_name, source=source, supplier=source.supplier)
            match_status = decision.status
            if used_bootstrap_product and product is not None:
                match_status = SupplierRawOffer.MATCH_STATUS_AUTO_MATCHED
            raw_offer_payload = SupplierRawOffer(
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
                product_name=source_product_name,
                currency=offer.currency[:3],
                price=offer.price,
                stock_qty=max(offer.stock_qty, 0),
                lead_time_days=max(offer.lead_time_days, 0),
                matched_product=product if used_bootstrap_product else decision.matched_product,
                mapped_category=mapped_category,
                category_mapping_status=category_mapping_status,
                category_mapping_reason=category_mapping_reason,
                category_mapping_confidence=category_mapping_confidence,
                category_mapped_at=(now if mapped_category is not None else None),
                match_status=match_status,
                match_reason=(decision.reason or ""),
                match_candidate_product_ids=[str(item.id) for item in decision.candidate_products],
                matching_attempts=1,
                last_matched_at=now,
                article_normalization_trace=article_result.trace,
                brand_normalization_trace=brand_result.trace,
                is_valid=True,
                skip_reason="",
                raw_payload=offer.raw_payload,
            )
            if not dry_run:
                raw_offer_payload.save()
                raw_offers_written += 1

        if product is not None and mapped_category is not None and not dry_run and product.category_id is None:
            product.category = mapped_category
            product.save(update_fields=("category", "updated_at"))

        seen_supplier_skus.add(supplier_sku)
        product_id = str(product.id) if product is not None else f"bootstrap:{supplier_sku}"
        if image_url:
            products_with_gpl_primary_image_would.add(product_id)
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
        bootstrap_products_would_reuse = max(len(valid_rows) - bootstrap_products_would_create, 0)
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

        timings["product_i18n_bulk_update_sec"] = 0.0
        timings["product_i18n_updated_candidates"] = 0

        if is_gpl_source and affected_products:
            image_sync_started = time.perf_counter()
            image_service = GplProductImageService()
            gpl_images_created = 0
            gpl_images_reused = 0
            gpl_images_stale_marked = 0
            gpl_images_products_updated = 0
            products_qs = Product.objects.filter(id__in=list(affected_products)).only("id", "name")
            for product in products_qs.iterator(chunk_size=300):
                result = image_service.sync_product_images(product=product, dry_run=False)
                gpl_images_created += int(result.created)
                gpl_images_reused += int(result.reused)
                gpl_images_stale_marked += int(result.stale_marked)
                if int(result.created) > 0 or int(result.stale_marked) > 0:
                    gpl_images_products_updated += 1
            timings["gpl_image_sync_sec"] = _elapsed_seconds(image_sync_started)
            summary_images = {
                "products_updated": gpl_images_products_updated,
                "created": gpl_images_created,
                "reused": gpl_images_reused,
                "stale_marked": gpl_images_stale_marked,
            }
        else:
            summary_images = {
                "products_updated": 0,
                "created": 0,
                "reused": 0,
                "stale_marked": 0,
            }
            timings["gpl_image_sync_sec"] = 0.0

    summary = run.summary if isinstance(run.summary, dict) else {}
    summary["persistence_mode"] = "current_offers"
    summary["match_status_counts"] = dict(match_status_counts)
    summary["category_status_counts"] = dict(category_status_counts)
    summary["current_offer_rows"] = {
        "unique_valid_offers": len(valid_rows),
        "seen_supplier_skus": len(seen_supplier_skus),
        "row_errors": len(row_errors),
        "disable_missing_offers": _should_disable_missing_offers(source=source, seen_supplier_skus=seen_supplier_skus),
        "bootstrap_unmatched_enabled": int(bootstrap_unmatched),
        "bootstrap_products_created": int(bootstrap_products_created),
        "bootstrap_products_reused": int(bootstrap_products_reused),
        "bootstrap_products_would_create": int(bootstrap_products_would_create),
        "bootstrap_products_would_reuse": int(bootstrap_products_would_reuse),
        "persist_raw_rows": int(persist_raw_rows),
        "raw_offers_written": int(raw_offers_written),
    }
    summary["gpl_import_observability"] = {
        "resolver_used": int(gpl_resolver is not None),
        "image_detected_count": int(image_detected_count),
        "products_with_gpl_primary_image_would": int(len(products_with_gpl_primary_image_would)),
        "brand_detected_count": int(brand_detected_count),
        "price_non_null_count": int(price_non_null_count),
        "stock_non_null_count": int(stock_non_null_count),
        "stock_positive_count": int(stock_positive_count),
        "stock_values_suspicious_count": int(stock_values_suspicious_count),
        "rows_with_suspicious_stock": int(rows_with_suspicious_stock),
        "stock_values_ignored": int(stock_values_ignored),
        "max_stock_total_after_normalization": int(max_stock_total_after_normalization),
    }
    summary["gpl_category_assignment"] = {
        "assigned_by_group_mapping": int(gpl_mapping_status_counts.get(MAPPING_STATUS_ASSIGNED_GROUP, 0)),
        "assigned_by_row_rule": int(gpl_mapping_status_counts.get(MAPPING_STATUS_ASSIGNED_ROW, 0)),
        "needs_category_mapping": int(gpl_mapping_status_counts.get(MAPPING_STATUS_NEEDS, 0)),
        "missing_leaf_category": int(gpl_mapping_status_counts.get(MAPPING_STATUS_MISSING, 0)),
        "conflict": int(gpl_mapping_status_counts.get(MAPPING_STATUS_CONFLICT, 0)),
        "ignored": int(gpl_mapping_status_counts.get(MAPPING_STATUS_IGNORED, 0)),
        "category_assigned_total": int(
            gpl_mapping_status_counts.get(MAPPING_STATUS_ASSIGNED_GROUP, 0)
            + gpl_mapping_status_counts.get(MAPPING_STATUS_ASSIGNED_ROW, 0)
        ),
        "category_assigned_pct": (
            round(
                (
                    (
                        gpl_mapping_status_counts.get(MAPPING_STATUS_ASSIGNED_GROUP, 0)
                        + gpl_mapping_status_counts.get(MAPPING_STATUS_ASSIGNED_ROW, 0)
                    )
                    / max(len(parse_result.offers), 1)
                )
                * 100.0,
                2,
            )
            if parse_result.offers
            else 0.0
        ),
        "category_null_total": int(
            gpl_mapping_status_counts.get(MAPPING_STATUS_NEEDS, 0)
            + gpl_mapping_status_counts.get(MAPPING_STATUS_MISSING, 0)
            + gpl_mapping_status_counts.get(MAPPING_STATUS_CONFLICT, 0)
            + gpl_mapping_status_counts.get(MAPPING_STATUS_IGNORED, 0)
        ),
        "invalid_target_count": int(gpl_invalid_target_count),
        "non_assignable_target_count": int(gpl_non_assignable_target_count),
        "missing_target_count": int(gpl_missing_target_count),
    }
    summary["gpl_image_sync"] = summary_images
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


def _should_bootstrap_unmatched_current_offers(*, source: ImportSource) -> bool:
    parser_options = source.parser_options if isinstance(source.parser_options, dict) else {}
    if "bootstrap_unmatched_products" in parser_options:
        return bool(parser_options.get("bootstrap_unmatched_products"))

    source_code = str(getattr(source, "code", "") or "").strip().lower()
    if source_code != "gpl":
        return False

    # Safe default for clean bootstrap only.
    has_products = Product.objects.exists()
    has_supplier_offers = SupplierOffer.objects.filter(supplier=source.supplier).exists()
    return not has_products and not has_supplier_offers


def _should_persist_raw_rows_for_current_offers(*, source: ImportSource, bootstrap_unmatched: bool) -> bool:
    parser_options = source.parser_options if isinstance(source.parser_options, dict) else {}
    if "persist_raw_rows_current_offers" in parser_options:
        return bool(parser_options.get("persist_raw_rows_current_offers"))
    return bool(bootstrap_unmatched)


def _get_or_create_bootstrap_product_for_offer(
    *,
    source: ImportSource,
    offer,
    supplier_sku: str,
    mapped_category: Category | None = None,
) -> tuple[Product, bool]:
    resolved_sku = _build_bootstrap_product_sku(source=source, supplier_sku=supplier_sku)
    existing = Product.objects.select_related("brand").filter(sku=resolved_sku).first()
    if existing is not None:
        return existing, False

    brand = _get_or_create_bootstrap_brand(brand_name=offer.brand_name)
    base_name = sanitize_product_name(str(offer.product_name or ""))[:255]
    if not base_name:
        base_name = sanitize_product_name(str(offer.article or offer.external_sku or supplier_sku))[:255] or "Товар без названия"
    preferred_slug = slugify(f"{base_name}-{resolved_sku}")[:300]
    now = timezone.now()
    product = Product.objects.create(
        sku=resolved_sku,
        article=str(offer.article or offer.external_sku or supplier_sku)[:128],
        name=base_name,
        name_uk=base_name,
        name_ru=base_name,
        name_en=base_name,
        slug=generate_unique_product_slug(name=base_name, preferred_slug=preferred_slug),
        brand=brand,
        is_active=True,
        published_at=now,
        catalog_source=Product.CATALOG_SOURCE_LEGACY,
        name_source=Product.NAME_SOURCE_SUPPLIER_FALLBACK,
        name_source_text=base_name[:255],
        name_translation_status=Product.NAME_TRANSLATION_PENDING,
        normalized_brand=str(getattr(brand, "name", "") or "").upper(),
        category=mapped_category,
    )
    ensure_product_svom_sku(product)
    return product, True


def _build_gpl_group_decisions(
    *,
    parse_result: ParseResult,
    resolver: GplImportCategoryAssignmentResolver,
) -> dict[tuple[str, str], GroupAssignmentDecision]:
    grouped_rows: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for offer in parse_result.offers:
        payload = _gpl_row_payload(offer=offer)
        grouped_rows[_gpl_group_key(payload=payload)].append(payload)
    out: dict[tuple[str, str], GroupAssignmentDecision] = {}
    for key, rows in grouped_rows.items():
        out[key] = resolver.decide_group(rows=rows)
    return out


def _gpl_group_key(*, payload: dict[str, str]) -> tuple[str, str]:
    raw_category = str(payload.get("Категорія") or payload.get("category") or "").strip()
    raw_group = str(payload.get("Група ТД") or payload.get("group") or "").strip()
    return raw_category, raw_group


def _gpl_row_payload(*, offer) -> dict[str, str]:
    payload = offer.raw_payload if isinstance(offer.raw_payload, dict) else {}
    out = {str(key): str(value) for key, value in payload.items() if key is not None}
    if not out.get("Категорія"):
        out["Категорія"] = str(payload.get("category") or payload.get("Категория") or "")
    if not out.get("Група ТД"):
        out["Група ТД"] = str(payload.get("group") or payload.get("Группа ТД") or "")
    if not out.get("Найменування"):
        out["Найменування"] = str(payload.get("name") or payload.get("title") or "")
    if not out.get("Опис"):
        out["Опис"] = str(payload.get("description") or "")
    if not out.get("Артикул ТД"):
        out["Артикул ТД"] = str(payload.get("article") or "")
    if not out.get("Артикул"):
        out["Артикул"] = str(payload.get("Артикул") or payload.get("article") or "")
    return out


def _extract_gpl_image_url(*, payload: dict[str, str]) -> str:
    candidates = (
        "Зображення товару",
        "Фото",
        "image_url",
        "image",
        "photo",
        "photo_url",
    )
    for key in candidates:
        value = str(payload.get(key) or "").strip()
        if value.startswith("http://") or value.startswith("https://"):
            return value
    return ""


def _resolve_category_mapping_reason(*, gpl_row_decision, fallback: str) -> str:
    if gpl_row_decision is None:
        if fallback == "from_product":
            return SupplierRawOffer.CATEGORY_MAPPING_REASON_FROM_PRODUCT
        return SupplierRawOffer.CATEGORY_MAPPING_REASON_NO_CATEGORY_SIGNAL
    if gpl_row_decision.mapping_status == MAPPING_STATUS_ASSIGNED_GROUP:
        return SupplierRawOffer.CATEGORY_MAPPING_REASON_SUPPLIER_CATEGORY_EXACT
    if gpl_row_decision.mapping_status == MAPPING_STATUS_ASSIGNED_ROW:
        return SupplierRawOffer.CATEGORY_MAPPING_REASON_NAME_TOKENS
    if gpl_row_decision.mapping_status == MAPPING_STATUS_CONFLICT:
        return SupplierRawOffer.CATEGORY_MAPPING_REASON_NOT_ASSIGNABLE
    if gpl_row_decision.mapping_status == MAPPING_STATUS_MISSING:
        return SupplierRawOffer.CATEGORY_MAPPING_REASON_LOW_CONFIDENCE
    return SupplierRawOffer.CATEGORY_MAPPING_REASON_NO_CATEGORY_SIGNAL


def _resolve_category_mapping_confidence(*, gpl_row_decision, fallback: Decimal | None) -> Decimal | None:
    if gpl_row_decision is None:
        return fallback
    confidence = float(getattr(gpl_row_decision, "confidence", 0.0) or 0.0)
    if confidence <= 0.0:
        return fallback
    if confidence > 1.0:
        confidence = 1.0
    return Decimal(f"{confidence:.3f}")


def _build_bootstrap_product_sku(*, source: ImportSource, supplier_sku: str) -> str:
    code = str(getattr(source, "code", "") or "").strip().upper() or "SRC"
    compact = "".join(ch for ch in str(supplier_sku or "").upper() if ch.isalnum())
    compact = compact[:54] if compact else "ITEM"
    candidate = f"{code}-{compact}"[:64]
    if not Product.objects.filter(sku=candidate).exists():
        return candidate

    suffix = 2
    while True:
        reserved = f"-{suffix}"
        sku = f"{candidate[: max(1, 64 - len(reserved))]}{reserved}"
        if not Product.objects.filter(sku=sku).exists():
            return sku
        suffix += 1


def _get_or_create_bootstrap_brand(*, brand_name: str) -> Brand:
    clean = sanitize_product_name(str(brand_name or ""))[:120] or "UNKNOWN"
    existing = Brand.objects.filter(name=clean).first()
    if existing is not None:
        return existing

    base = slugify(clean).strip("-")[:130] or "brand"
    slug = base
    idx = 2
    while Brand.objects.filter(slug=slug).exists():
        suffix = f"-{idx}"
        slug = f"{base[: max(1, 140 - len(suffix))]}{suffix}"
        idx += 1

    return Brand.objects.create(
        name=clean,
        slug=slug,
        is_active=True,
        published_at=timezone.now(),
    )
