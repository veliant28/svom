from __future__ import annotations

from decimal import Decimal

from django.utils import timezone

from apps.pricing.models import SupplierOffer
from apps.supplier_imports.models import ImportArtifact, ImportRun, ImportSource, OfferMatchReview, SupplierRawOffer
from apps.supplier_imports.parsers import ParseResult
from apps.catalog.services.product_management import sanitize_product_name

from .persistence_helpers import attach_utr_detail_id


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
