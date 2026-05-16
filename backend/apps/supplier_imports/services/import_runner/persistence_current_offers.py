from __future__ import annotations

import time
from collections import Counter
from decimal import Decimal

from django.utils import timezone

from apps.catalog.models import Category
from apps.catalog.services.product_management import sanitize_product_name
from apps.supplier_imports.models import ImportArtifact, ImportRowError, ImportRun, ImportSource, SupplierRawOffer
from apps.supplier_imports.parsers import ParseResult
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
from .persistence_helpers import (
    _build_autodb_supplier_brand_lookup,
    _build_gpl_group_decisions,
    _build_row_error,
    _cleanup_old_row_errors,
    _elapsed_seconds,
    _extract_gpl_image_url,
    _get_or_create_bootstrap_product_for_offer,
    _gpl_group_key,
    _gpl_row_payload,
    _resolve_category_mapping_confidence,
    _resolve_category_mapping_reason,
    _should_bootstrap_unmatched_current_offers,
    _should_disable_missing_offers,
    _should_persist_raw_rows_for_current_offers,
    _sync_product_autodb_brand_from_offer,
)
from .persistence_current_offers_apply import apply_current_offers_changes


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
    autodb_supplier_brand_lookup = _build_autodb_supplier_brand_lookup()

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
    gpl_product_article_updates: dict[str, str] = {}
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
                        autodb_supplier_brand_lookup=autodb_supplier_brand_lookup,
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

        if product is not None and not dry_run:
            _sync_product_autodb_brand_from_offer(
                product=product,
                raw_brand_name=str(offer.brand_name or ""),
                lookup=autodb_supplier_brand_lookup,
            )

        if is_gpl_source and product is not None:
            resolved_article = str(offer.article or "").strip()[:128]
            if resolved_article:
                gpl_product_article_updates[str(product.id)] = resolved_article

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

    created, updated, bootstrap_products_would_reuse, summary_images, affected_products, timings = apply_current_offers_changes(
        dry_run=dry_run,
        source=source,
        seen_supplier_skus=seen_supplier_skus,
        valid_rows=valid_rows,
        now=now,
        timings=timings,
        bootstrap_products_would_create=bootstrap_products_would_create,
        created=created,
        updated=updated,
        affected_products=affected_products,
        utr_detail_updates=utr_detail_updates,
        gpl_product_article_updates=gpl_product_article_updates,
        is_gpl_source=is_gpl_source,
    )
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
        "product_article_sync_candidates": int(len(gpl_product_article_updates)),
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
