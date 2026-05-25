from __future__ import annotations

import contextlib
import signal
import time

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.autodb.models import AutoDbMatchingRun, AutoDbRemoteQuotaState, AutoDbSupplier
from apps.autodb.services.matching.constants import REMOTE_QUOTA_KEY
from apps.autodb.services.matching.quota_tracker import AutoDbRemoteQuotaTracker
from apps.autodb.services.matching.backoffice_tecdoc_batch import BackofficeTecdocBatchSelector
from apps.autodb.services.public_api import AutoDbPublicApiClient
from apps.autodb.services.raw_clone_storage import AutoDbRawCloneStorage
from apps.autodb.services.remote_client import AutoDbProRemoteClientError
from apps.autodb.services.supplier_brand_matcher import SupplierBrandMatcher, normalize_brand_lookup_key
from apps.autodb.services.article_enrichment import AutoDbArticleEnrichmentService
from apps.autodb.services.product_fitment_enrichment import AutoDbProductFitmentEnrichmentService
from apps.autodb.services.product_image_enrichment import AutoDbProductImageEnrichmentService
from apps.autodb.services.product_name_lock import is_product_name_manual_locked
from apps.autodb.services.product_name_enrichment import AutoDbProductNameEnrichmentService
from apps.autodb.services.product_name_translation import ProductNameTranslationService
from apps.catalog.models import AutoDbArticleManualMapping, AutoDbProductLinkQuality, Product
from apps.catalog.services import resolve_autodb_article_name
from apps.core.services import (
    send_system_autodb_batch_finished_notification,
    send_system_autodb_batch_progress_notification,
)
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.parsers.utils import normalize_article, normalize_brand


@shared_task(name="autodb.manual_bind_product")
def manual_bind_product_to_autodb_task(
    *,
    product_id: str,
    supplier_id: int,
    article_number: str,
    supplier_name: str = "",
    article_id: int | None = None,
    actor_id: str = "",
    skip_clone_enrichment: bool = False,
    clone_replace_local: bool = False,
) -> dict[str, object]:
    article_value = str(article_number or "").strip().upper()
    if not product_id or not supplier_id or not article_value:
        return {
            "status": "validation_error",
            "detail": "product_id, supplier_id, article_number are required",
        }

    supplier = AutoDbSupplier.objects.filter(id=int(supplier_id)).first()
    supplier_display = str(supplier_name or "").strip() or str(getattr(supplier, "name", "") or "").strip() or str(
        getattr(supplier, "matchcode", "") or ""
    ).strip()
    if not supplier_display:
        supplier_display = str(int(supplier_id))

    article_key = f"{int(supplier_id)}:{article_value}"
    now = timezone.now()
    normalized_article = normalize_article(article_value)
    normalized_supplier = normalize_brand(supplier_display)
    warnings: list[str] = []

    with transaction.atomic():
        product = Product.objects.filter(pk=product_id).first()
        if product is None:
            return {"status": "not_found", "detail": "product not found", "product_id": str(product_id)}

        update_fields: list[str] = []

        if int(getattr(product, "autodb_supplier_id", 0) or 0) != int(supplier_id):
            product.autodb_supplier_id = int(supplier_id)
            update_fields.append("autodb_supplier_id")
        if str(getattr(product, "autodb_supplier_name", "") or "") != supplier_display:
            product.autodb_supplier_name = supplier_display
            update_fields.append("autodb_supplier_name")
        if str(getattr(product, "autodb_article_number", "") or "") != article_value:
            product.autodb_article_number = article_value
            update_fields.append("autodb_article_number")
        if str(getattr(product, "autodb_article_key", "") or "") != article_key:
            product.autodb_article_key = article_key
            update_fields.append("autodb_article_key")

        if article_id is not None:
            try:
                parsed_article_id = int(article_id)
            except (TypeError, ValueError):
                parsed_article_id = None
            if parsed_article_id and int(getattr(product, "autodb_article_id", 0) or 0) != parsed_article_id:
                product.autodb_article_id = parsed_article_id
                update_fields.append("autodb_article_id")

        if normalized_article and str(getattr(product, "normalized_article", "") or "") != normalized_article:
            product.normalized_article = normalized_article
            update_fields.append("normalized_article")
        if normalized_supplier and str(getattr(product, "normalized_brand", "") or "") != normalized_supplier:
            product.normalized_brand = normalized_supplier
            update_fields.append("normalized_brand")

        if not bool(getattr(product, "brand_manually_locked", False)):
            if str(getattr(product, "display_brand_name", "") or "") != supplier_display:
                product.display_brand_name = supplier_display
                update_fields.append("display_brand_name")
            if str(getattr(product, "brand_source", "") or "") != Product.BRAND_SOURCE_AUTODB_PRO:
                product.brand_source = Product.BRAND_SOURCE_AUTODB_PRO
                update_fields.append("brand_source")

        if str(getattr(product, "catalog_source", "") or "") != Product.CATALOG_SOURCE_AUTODB_PRO:
            product.catalog_source = Product.CATALOG_SOURCE_AUTODB_PRO
            update_fields.append("catalog_source")

        if not is_product_name_manual_locked(product):
            try:
                previous_name = str(getattr(product, "name", "") or "")
                previous_source_text = str(getattr(product, "name_source_text", "") or "")
                article_name = resolve_autodb_article_name(
                    normalized_article=normalized_article,
                    normalized_brand=normalized_supplier,
                    prefer_live=False,
                )
                normalized_article_name = str(article_name or "").strip()[:255]
                if normalized_article_name:
                    article_name = normalized_article_name
                translation_source_text = str(article_name or previous_source_text or previous_name).strip()[:255]
                if article_name and str(getattr(product, "name_source", "") or "") != Product.NAME_SOURCE_AUTODB_PRO:
                    product.name_source = Product.NAME_SOURCE_AUTODB_PRO
                    update_fields.append("name_source")
                if article_name and str(getattr(product, "name_source_text", "") or "") != article_name:
                    product.name_source_text = article_name
                    update_fields.append("name_source_text")
                if translation_source_text:
                    translation = ProductNameTranslationService().translate_product_name(source_text=translation_source_text)
                    translated_uk = str(translation.uk or article_name).strip()[:255]
                    translated_ru = str(translation.ru or article_name).strip()[:255]
                    translated_en = str(translation.en or article_name).strip()[:255]

                    i18n_targets = {
                        "name_uk": translated_uk,
                        "name_ru": translated_ru,
                        "name_en": translated_en,
                    }
                    for field, next_value in i18n_targets.items():
                        current_value = str(getattr(product, field, "") or "")
                        if (
                            not current_value
                            or current_value == previous_name
                            or current_value == previous_source_text
                            or str(getattr(product, "name_source", "") or "") == Product.NAME_SOURCE_AUTODB_PRO
                        ):
                            if current_value != next_value:
                                setattr(product, field, next_value)
                                update_fields.append(field)

                    base_name = translated_uk or translation_source_text
                    if base_name and str(getattr(product, "name", "") or "") != base_name:
                        product.name = base_name
                        update_fields.append("name")

                    translation_status = str(translation.status or "").strip() or Product.NAME_TRANSLATION_PENDING
                    if str(getattr(product, "name_translation_status", "") or "") != translation_status:
                        product.name_translation_status = translation_status
                        update_fields.append("name_translation_status")
                    translation_error = str(translation.error or "").strip()
                    if str(getattr(product, "name_translation_error", "") or "") != translation_error:
                        product.name_translation_error = translation_error
                        update_fields.append("name_translation_error")
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"name_prepare_failed: {exc}")

        if update_fields:
            product.save(update_fields=[*update_fields, "updated_at"])

        manual_mapping_defaults = {
            "brand": supplier_display,
            "article": article_value,
            "autodb_supplier_id": int(supplier_id),
            "autodb_article_number": article_value,
            "autodb_article_key": article_key,
            "manual_confirmed": True,
            "source": "backoffice_manual_search_bind",
            "note": f"actor={actor_id}" if actor_id else "backoffice_manual_search_bind",
        }
        if article_id is not None:
            try:
                parsed_article_id = int(article_id)
            except (TypeError, ValueError):
                parsed_article_id = None
            if parsed_article_id:
                manual_mapping_defaults["autodb_article_id"] = parsed_article_id

        AutoDbArticleManualMapping.objects.update_or_create(
            normalized_brand=normalized_supplier
            or normalize_brand(str(getattr(product, "display_brand_name", "") or ""))
            or normalize_brand(str(getattr(product, "autodb_supplier_name", "") or ""))
            or str(getattr(product, "normalized_brand", "") or ""),
            normalized_article=normalized_article,
            autodb_article_key=article_key,
            defaults=manual_mapping_defaults,
        )

        quality_defaults = {
            "autodb_supplier_id": int(supplier_id),
            "autodb_article_number": article_value,
            "status": AutoDbProductLinkQuality.STATUS_TRUSTED,
            "reason": "manual_bind_from_backoffice",
            "evidence": {
                "source": "backoffice.autodb-matching.manual-search",
                "actor_id": actor_id,
                "supplier_id": int(supplier_id),
                "supplier_name": supplier_display,
                "article_number": article_value,
            },
            "checked_at": now,
            "manually_confirmed": True,
            "note": "manual bind",
        }
        quality, created = AutoDbProductLinkQuality.objects.get_or_create(
            product=product,
            autodb_article_key=article_key,
            defaults=quality_defaults,
        )
        if not created:
            quality.autodb_supplier_id = int(supplier_id)
            quality.autodb_article_number = article_value
            quality.status = AutoDbProductLinkQuality.STATUS_TRUSTED
            quality.reason = "manual_bind_from_backoffice"
            quality.evidence = quality_defaults["evidence"]
            quality.checked_at = now
            quality.manually_confirmed = True
            quality.note = "manual bind"
            quality.save(
                update_fields=[
                    "autodb_supplier_id",
                    "autodb_article_number",
                    "status",
                    "reason",
                    "evidence",
                    "checked_at",
                    "manually_confirmed",
                    "note",
                    "updated_at",
                ]
            )

    clone_result = None
    if not skip_clone_enrichment:
        try:
            clone_result = AutoDbArticleEnrichmentService().enrich_article(
                supplier_id=int(supplier_id),
                article_number=article_value,
                dry_run=False,
                replace_local=clone_replace_local,
            )
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"clone_enrichment_failed: {exc}")

    product = Product.objects.filter(pk=product_id).first()
    if product is None:
        return {"status": "bound", "product_id": str(product_id), "autodb_article_key": article_key, "quality_created": bool(created), "warnings": warnings}

    try:
        name_result = AutoDbProductNameEnrichmentService().enrich_product(
            product=product,
            dry_run=False,
            only_missing_translations=False,
        )
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"name_enrichment_failed: {exc}")
        name_result = None

    try:
        fitment_result = AutoDbProductFitmentEnrichmentService().enrich_product(product=product, dry_run=False)
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"fitment_enrichment_failed: {exc}")
        fitment_result = None

    try:
        image_result = AutoDbProductImageEnrichmentService().sync_product_images(
            product=product,
            dry_run=False,
            prefer_gpl=True,
        )
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"image_enrichment_failed: {exc}")
        image_result = None

    return {
        "status": "bound",
        "product_id": str(product_id),
        "autodb_article_key": article_key,
        "quality_created": bool(created),
        "warnings": warnings,
        "clone": {
            "remote_queries": int(clone_result.remote_queries) if clone_result is not None else 0,
            "remote_hits": int(clone_result.remote_hits) if clone_result is not None else 0,
            "populated_tables": clone_result.populated_tables if clone_result is not None else {},
        },
        "name": {
            "status": name_result.status if name_result is not None else "error",
            "source_title": name_result.autodb_source_title if name_result is not None else "",
            "name_uk": name_result.new_name_uk if name_result is not None else "",
            "name_ru": name_result.new_name_ru if name_result is not None else "",
            "name_en": name_result.new_name_en if name_result is not None else "",
            "translation_status": name_result.translation_status if name_result is not None else "",
            "translation_error": name_result.translation_error if name_result is not None else "",
        },
        "fitments": {
            "status": fitment_result.status if fitment_result is not None else "error",
            "created": int(fitment_result.fitments_created) if fitment_result is not None else 0,
            "updated": int(fitment_result.fitments_updated) if fitment_result is not None else 0,
            "stale_marked": int(fitment_result.stale_marked) if fitment_result is not None else 0,
        },
        "attributes": {
            "status": "clone_only_source",
            "created": 0,
            "updated": 0,
        },
        "images": {
            "created": int(image_result.created) if image_result is not None else 0,
            "reused": int(image_result.reused) if image_result is not None else 0,
            "stale_marked": int(image_result.stale_marked) if image_result is not None else 0,
        },
    }


BACKOFFICE_TECDOC_BATCH_RUN_TYPE = "backoffice_tecdoc_batch_bind"
BACKOFFICE_TECDOC_API_BATCH_RUN_TYPE = "backoffice_tecdoc_api_batch_bind"
BACKOFFICE_TECDOC_BATCH_ITEM_TIMEOUT_SECONDS = max(
    10,
    int(getattr(settings, "AUTODB_BACKOFFICE_BATCH_ITEM_TIMEOUT_SECONDS", 90) or 90),
)


class _BatchItemTimeoutError(RuntimeError):
    pass


@contextlib.contextmanager
def _batch_item_timeout(seconds: int):
    if seconds <= 0 or not hasattr(signal, "setitimer"):
        yield
        return

    def _handler(_signum, _frame):
        raise _BatchItemTimeoutError(f"batch_item_timeout_after_{seconds}s")

    previous = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, _handler)
    signal.setitimer(signal.ITIMER_REAL, float(seconds))
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.0)
        signal.signal(signal.SIGALRM, previous)


@shared_task(name="autodb.backoffice_tecdoc_batch_bind")
def run_backoffice_tecdoc_batch_bind_task(
    *,
    run_id: str,
    limit: int = 200,
    actor_id: str = "",
    product_ids: list[str] | None = None,
    continuous: bool = False,
    strict_tecdoc_only: bool = False,
    batch_source: str = "legacy_batch",
) -> dict[str, object]:
    run = AutoDbMatchingRun.objects.filter(id=run_id).first()
    if run is None:
        return {"status": "not_found", "detail": "run not found", "run_id": str(run_id)}

    requested_limit = max(1, min(int(limit or 0), 1000))
    requested_product_ids_count = len(product_ids or [])
    continuous_mode = bool(continuous and requested_product_ids_count == 0)
    started_at = timezone.now()
    run.started_at = run.started_at or started_at
    run.status = AutoDbMatchingRun.STATUS_RUNNING
    run.error = ""
    run.summary_json = {
        **(run.summary_json or {}),
        "running": True,
        "stage": "selecting_candidates",
        "requested_limit": requested_limit,
        "requested_product_ids_count": requested_product_ids_count,
        "processed": 0,
        "bound": 0,
        "failed": 0,
        "continuous": continuous_mode,
        "stopped_reason": "",
        "last_error": "",
        "actor_id": str(actor_id or ""),
        "strict_tecdoc_only": bool(strict_tecdoc_only),
        "batch_source": str(batch_source or "legacy_batch"),
        "started_at": run.started_at.isoformat() if run.started_at else started_at.isoformat(),
        "last_heartbeat_at": started_at.isoformat(),
    }
    run.save(update_fields=["started_at", "status", "error", "summary_json", "updated_at"])

    selector = BackofficeTecdocBatchSelector()
    brand_matcher = SupplierBrandMatcher()
    clone_storage = AutoDbRawCloneStorage()
    use_public_search = bool(getattr(settings, "AUTODB_BATCH_PUBLIC_SEARCH_ENABLED", True))
    public_api = AutoDbPublicApiClient() if use_public_search else None
    supplier_display_cache: dict[int, str] = {}
    remote_retry_seconds = max(
        int(getattr(settings, "AUTODB_BACKOFFICE_BATCH_REMOTE_RETRY_SECONDS", 15) or 15),
        1,
    )
    remote_retry_max_seconds = max(
        int(getattr(settings, "AUTODB_BACKOFFICE_BATCH_REMOTE_RETRY_MAX_SECONDS", 120) or 120),
        remote_retry_seconds,
    )
    quota_poll_seconds = max(
        int(getattr(settings, "AUTODB_BACKOFFICE_BATCH_QUOTA_POLL_SECONDS", 30) or 30),
        5,
    )
    results: list[dict[str, object]] = []
    processed = 0
    bound = 0
    failed = 0
    selected_total = 0
    cycle_index = 0
    stop_reason = ""
    last_error = ""
    selected_last_cycle = 0
    while True:
        cycle_index += 1
        effective_product_ids = product_ids if cycle_index == 1 else None
        cycle_base_processed = processed
        cycle_base_bound = bound
        cycle_base_failed = failed
        candidates = selector.select_candidates(
            limit=requested_limit,
            product_ids=effective_product_ids,
            only_new_tecdoc=continuous_mode and effective_product_ids is None,
            strict_tecdoc_only=bool(strict_tecdoc_only),
        )
        selected_last_cycle = len(candidates)
        selected_total += selected_last_cycle

        now = timezone.now()
        run.summary_json = {
            **(run.summary_json or {}),
            "running": True,
            "stage": "processing_items",
            "continuous": continuous_mode,
            "requested_limit": requested_limit,
            "requested_product_ids_count": requested_product_ids_count,
            "cycle_index": cycle_index,
            "selected": selected_last_cycle,
            "selected_total": selected_total,
            "processed_in_cycle": 0,
            "linked_in_cycle": 0,
            "failed_in_cycle": 0,
            "processed": processed,
            "bound": bound,
            "failed": failed,
            "stopped_reason": stop_reason,
            "last_error": last_error,
            "strict_tecdoc_only": bool(strict_tecdoc_only),
            "batch_source": str(batch_source or "legacy_batch"),
            "last_heartbeat_at": now.isoformat(),
        }
        run.save(update_fields=["summary_json", "updated_at"])

        if selected_last_cycle <= 0:
            break

        for index, item in enumerate(candidates, start=1):
            transient_attempt = 0
            while True:
                loop_heartbeat = timezone.now()
                run.summary_json = {
                    **(run.summary_json or {}),
                    "running": True,
                    "stage": "processing_item",
                    "continuous": continuous_mode,
                    "requested_limit": requested_limit,
                    "requested_product_ids_count": requested_product_ids_count,
                    "cycle_index": cycle_index,
                    "selected": selected_last_cycle,
                    "selected_total": selected_total,
                    "processed_in_cycle": max(processed - cycle_base_processed, 0),
                    "linked_in_cycle": max(bound - cycle_base_bound, 0),
                    "failed_in_cycle": max(failed - cycle_base_failed, 0),
                    "processing_index": index,
                    "processing_product_id": str(item.product_id),
                    "processing_supplier_id": int(item.supplier_id),
                    "processing_article": str(item.article or ""),
                    "processing_retry_attempt": transient_attempt,
                    "processed": processed,
                    "bound": bound,
                    "failed": failed,
                    "stopped_reason": stop_reason,
                    "last_error": last_error,
                    "strict_tecdoc_only": bool(strict_tecdoc_only),
                    "batch_source": str(batch_source or "legacy_batch"),
                    "last_heartbeat_at": loop_heartbeat.isoformat(),
                }
                run.save(update_fields=["summary_json", "updated_at"])
                try:
                    bind_supplier_id = int(item.supplier_id)
                    bind_article = str(item.article or "")
                    bind_supplier_name = str(item.supplier_name or "")
                    relinked_by_brand_guard = False
                    resolved_by_public_search = False
                    raw_offer_brand = ""

                    with _batch_item_timeout(BACKOFFICE_TECDOC_BATCH_ITEM_TIMEOUT_SECONDS):
                        raw_offer_brand = _latest_raw_offer_brand_for_product(product_id=item.product_id)
                        if public_api is not None and bind_article:
                            public_candidate = _resolve_batch_candidate_via_public_search(
                                client=public_api,
                                article=bind_article,
                                preferred_supplier_id=bind_supplier_id,
                                preferred_brand=raw_offer_brand or bind_supplier_name,
                                supplier_display_cache=supplier_display_cache,
                            )
                            if public_candidate is not None:
                                bind_supplier_id, bind_supplier_name, bind_article = public_candidate
                                resolved_by_public_search = True
                            elif bind_supplier_id <= 0:
                                _mark_link_clone_data_missing_needs_review(
                                    product_id=item.product_id,
                                    supplier_id=0,
                                    article_number=bind_article,
                                    reason="batch_public_search_no_candidate",
                                )
                                _apply_fallback_name_translation_for_product(
                                    product_id=str(item.product_id),
                                    reason="batch_public_search_no_candidate",
                                )
                                processed += 1
                                failed += 1
                                results.append(
                                    {
                                        "product_id": item.product_id,
                                        "supplier_id": 0,
                                        "article": bind_article,
                                        "status": "remote_not_found",
                                        "reason": "batch_public_search_no_candidate",
                                    }
                                )
                                break

                        if bind_supplier_id > 0 and not bind_supplier_name:
                            bind_supplier_name = _supplier_display_name_from_autodb(
                                supplier_id=bind_supplier_id,
                                cache=supplier_display_cache,
                            )
                        if raw_offer_brand:
                            raw_brand_norm = normalize_brand(raw_offer_brand)
                            supplier_brand_norm = normalize_brand(bind_supplier_name or str(bind_supplier_id))
                            if raw_brand_norm and supplier_brand_norm and raw_brand_norm != supplier_brand_norm:
                                matched_supplier_id, matched_supplier_name, matched_reason = _resolve_supplier_by_brand(
                                    matcher=brand_matcher,
                                    raw_brand=raw_offer_brand,
                                )
                                if matched_supplier_id and "relaxed_match" not in matched_reason:
                                    canonical_article = _resolve_article_for_supplier(
                                        storage=clone_storage,
                                        supplier_id=matched_supplier_id,
                                        article_input=bind_article,
                                    )
                                    if canonical_article:
                                        bind_supplier_id = int(matched_supplier_id)
                                        bind_article = str(canonical_article)
                                        bind_supplier_name = str(matched_supplier_name or raw_offer_brand or bind_supplier_name)
                                        relinked_by_brand_guard = True
                                    else:
                                        _mark_link_brand_mismatch_needs_review(
                                            product_id=item.product_id,
                                            supplier_id=bind_supplier_id,
                                            article_number=bind_article,
                                            raw_brand=raw_offer_brand,
                                            supplier_brand=bind_supplier_name,
                                            reason="batch_brand_match_ok_article_not_found_for_brand",
                                        )
                                        _apply_fallback_name_translation_for_product(
                                            product_id=str(item.product_id),
                                            reason="brand_matched_article_missing",
                                        )
                                        processed += 1
                                        failed += 1
                                        results.append(
                                            {
                                                "product_id": item.product_id,
                                                "supplier_id": int(item.supplier_id),
                                                "article": item.article,
                                                "status": "skipped_brand_mismatch",
                                                "reason": "brand_matched_article_missing",
                                                "raw_offer_brand": raw_offer_brand,
                                                "supplier_brand": bind_supplier_name,
                                            }
                                        )
                                        break
                                else:
                                    _mark_link_brand_mismatch_needs_review(
                                        product_id=item.product_id,
                                        supplier_id=bind_supplier_id,
                                        article_number=bind_article,
                                        raw_brand=raw_offer_brand,
                                        supplier_brand=bind_supplier_name,
                                        reason="batch_brand_mismatch_raw_offer_vs_supplier",
                                    )
                                    _apply_fallback_name_translation_for_product(
                                        product_id=str(item.product_id),
                                        reason="brand_mismatch_needs_manual_review",
                                    )
                                    processed += 1
                                    failed += 1
                                    results.append(
                                        {
                                            "product_id": item.product_id,
                                            "supplier_id": int(item.supplier_id),
                                            "article": item.article,
                                            "status": "skipped_brand_mismatch",
                                            "reason": "brand_mismatch_needs_manual_review",
                                            "raw_offer_brand": raw_offer_brand,
                                            "supplier_brand": bind_supplier_name,
                                        }
                                    )
                                    break

                        # Remote-first: refresh full article-related clone tables before bind.
                        # Fitment/image/name enrichment runs right after bind and depends on
                        # article_li/article_images/article_attributes being present locally.
                        pre_clone = AutoDbArticleEnrichmentService().enrich_article(
                            supplier_id=bind_supplier_id,
                            article_number=bind_article,
                            dry_run=False,
                            replace_local=True,
                        )
                        pre_clone_remote_hits = int(pre_clone.remote_hits or 0)
                        pre_clone_rows_total = sum(int(value or 0) for value in (pre_clone.populated_tables or {}).values())
                        pre_clone_has_data = pre_clone_remote_hits > 0 or pre_clone_rows_total > 0
                        clone_precheck_warning = ""
                        if not pre_clone_has_data:
                            clone_precheck_warning = "remote_or_clone_rows_not_found_for_article"

                        bind_result = manual_bind_product_to_autodb_task(
                            product_id=item.product_id,
                            supplier_id=bind_supplier_id,
                            article_number=bind_article,
                            supplier_name=bind_supplier_name,
                            article_id=None,
                            actor_id=str(actor_id or ""),
                            skip_clone_enrichment=True,
                        )
                        status_value = str(bind_result.get("status") or "")

                    processed += 1
                    if status_value == "bound" and not clone_precheck_warning:
                        bound += 1
                    else:
                        if clone_precheck_warning:
                            _mark_link_clone_data_missing_needs_review(
                                product_id=item.product_id,
                                supplier_id=bind_supplier_id,
                                article_number=bind_article,
                                reason="batch_clone_data_missing_after_bind",
                            )
                        _apply_fallback_name_translation_for_product(
                            product_id=str(item.product_id),
                            reason=clone_precheck_warning or f"bind_status_{status_value or 'error'}",
                        )
                        failed += 1
                    results.append(
                        {
                            "product_id": item.product_id,
                            "supplier_id": bind_supplier_id,
                            "article": bind_article,
                            "status": "needs_review" if clone_precheck_warning and status_value == "bound" else (status_value or "error"),
                            "relinked_by_brand_guard": relinked_by_brand_guard,
                            "resolved_by_public_search": resolved_by_public_search,
                            "warning": clone_precheck_warning,
                            "detail": bind_result,
                        }
                    )
                    last_error = ""
                    break
                except Exception as exc:  # noqa: BLE001
                    error_text = str(exc)
                    transient_reason = _classify_batch_transient_error(exc)
                    if continuous_mode and transient_reason in {"quota_limit", "remote_disconnect"}:
                        transient_attempt += 1
                        last_error = error_text
                        if transient_reason == "quota_limit":
                            _wait_for_batch_quota_recovery(
                                run=run,
                                requested_limit=requested_limit,
                                requested_product_ids_count=requested_product_ids_count,
                                cycle_index=cycle_index,
                                selected=selected_last_cycle,
                                selected_total=selected_total,
                                processed=processed,
                                processed_in_cycle=max(processed - cycle_base_processed, 0),
                                linked_in_cycle=max(bound - cycle_base_bound, 0),
                                failed_in_cycle=max(failed - cycle_base_failed, 0),
                                bound=bound,
                                failed=failed,
                                last_error=last_error,
                                item=item,
                                polling_seconds=quota_poll_seconds,
                            )
                        else:
                            retry_delay = min(
                                remote_retry_seconds * (2 ** max(transient_attempt - 1, 0)),
                                remote_retry_max_seconds,
                            )
                            wait_now = timezone.now()
                            run.summary_json = {
                                **(run.summary_json or {}),
                                "running": True,
                                "stage": "waiting_remote_retry",
                                "continuous": continuous_mode,
                                "requested_limit": requested_limit,
                                "requested_product_ids_count": requested_product_ids_count,
                                "cycle_index": cycle_index,
                                "selected": selected_last_cycle,
                                "selected_total": selected_total,
                                "processed_in_cycle": max(processed - cycle_base_processed, 0),
                                "linked_in_cycle": max(bound - cycle_base_bound, 0),
                                "failed_in_cycle": max(failed - cycle_base_failed, 0),
                                "processing_index": index,
                                "processing_product_id": str(item.product_id),
                                "processing_supplier_id": int(item.supplier_id),
                                "processing_article": str(item.article or ""),
                                "processing_retry_attempt": transient_attempt,
                                "retry_reason": "remote_disconnect",
                                "retry_in_seconds": int(retry_delay),
                                "processed": processed,
                                "bound": bound,
                                "failed": failed,
                                "stopped_reason": "",
                                "last_error": last_error,
                                "strict_tecdoc_only": bool(strict_tecdoc_only),
                                "batch_source": str(batch_source or "legacy_batch"),
                                "last_heartbeat_at": wait_now.isoformat(),
                            }
                            run.save(update_fields=["summary_json", "updated_at"])
                            time.sleep(float(retry_delay))
                        continue

                    processed += 1
                    failed += 1
                    _apply_fallback_name_translation_for_product(
                        product_id=str(item.product_id),
                        reason=error_text[:120] or "batch_exception",
                    )
                    if isinstance(exc, _BatchItemTimeoutError):
                        _mark_link_clone_data_missing_needs_review(
                            product_id=item.product_id,
                            supplier_id=int(item.supplier_id),
                            article_number=item.article,
                            reason="batch_item_timeout",
                        )
                    else:
                        _mark_link_clone_data_missing_needs_review(
                            product_id=item.product_id,
                            supplier_id=int(item.supplier_id),
                            article_number=item.article,
                            reason="batch_exception",
                        )
                    results.append(
                        {
                            "product_id": item.product_id,
                            "supplier_id": int(item.supplier_id),
                            "article": item.article,
                            "status": "error",
                            "reason": error_text,
                        }
                    )
                    stop_key = _classify_batch_transient_error(exc)
                    if stop_key == "quota_limit":
                        stop_reason = "quota_limit"
                        last_error = error_text
                    elif stop_key == "remote_disconnect":
                        stop_reason = "remote_disconnect"
                        last_error = error_text
                    break

            loop_done = timezone.now()
            run.summary_json = {
                **(run.summary_json or {}),
                "running": True,
                "stage": "processing_items",
                "continuous": continuous_mode,
                "requested_limit": requested_limit,
                "requested_product_ids_count": requested_product_ids_count,
                "cycle_index": cycle_index,
                "selected": selected_last_cycle,
                "selected_total": selected_total,
                "processed_in_cycle": max(processed - cycle_base_processed, 0),
                "linked_in_cycle": max(bound - cycle_base_bound, 0),
                "failed_in_cycle": max(failed - cycle_base_failed, 0),
                "processed": processed,
                "bound": bound,
                "failed": failed,
                "stopped_reason": stop_reason,
                "last_error": last_error,
                "strict_tecdoc_only": bool(strict_tecdoc_only),
                "batch_source": str(batch_source or "legacy_batch"),
                "last_heartbeat_at": loop_done.isoformat(),
            }
            run.save(update_fields=["summary_json", "updated_at"])
            _maybe_send_batch_progress_notification(
                run=run,
                processed=processed,
                linked=bound,
                errors=failed,
                batch_size=requested_limit,
            )
            if stop_reason:
                break

        if stop_reason:
            break

        if not continuous_mode:
            break

    finished_at = timezone.now()
    final_status = AutoDbMatchingRun.STATUS_SUCCESS
    if stop_reason:
        final_status = AutoDbMatchingRun.STATUS_PARTIAL
    run.status = final_status
    run.finished_at = finished_at
    run.error = last_error
    run.summary_json = {
        **(run.summary_json or {}),
        "running": False,
        "stage": "finished",
        "continuous": continuous_mode,
        "requested_limit": requested_limit,
        "requested_product_ids_count": requested_product_ids_count,
        "selected": selected_last_cycle,
        "selected_total": selected_total,
        "cycle_index": cycle_index,
        "processed_in_cycle": max(processed - cycle_base_processed, 0) if cycle_index > 0 else 0,
        "processed": processed,
        "bound": bound,
        "failed": failed,
        "stopped_reason": stop_reason,
        "last_error": last_error,
        "strict_tecdoc_only": bool(strict_tecdoc_only),
        "batch_source": str(batch_source or "legacy_batch"),
        "last_heartbeat_at": finished_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "results_preview": results[:50],
    }
    run.save(update_fields=["status", "finished_at", "error", "summary_json", "updated_at"])
    quota_used, quota_limit = _current_quota_snapshot()
    send_system_autodb_batch_finished_notification(
        run_id=str(run.id),
        final_status=run.status,
        batch_size=requested_limit,
        processed=processed,
        linked=bound,
        errors=failed,
        quota_used=quota_used,
        quota_limit=quota_limit,
        stop_reason=stop_reason,
        last_error=last_error,
    )

    return {
        "status": "done",
        "run_id": str(run.id),
        "selected": selected_last_cycle,
        "selected_total": selected_total,
        "cycle_index": cycle_index,
        "processed": processed,
        "bound": bound,
        "failed": failed,
        "stopped_reason": stop_reason,
        "last_error": last_error,
    }


def _maybe_send_batch_progress_notification(
    *,
    run: AutoDbMatchingRun,
    processed: int,
    linked: int,
    errors: int,
    batch_size: int,
) -> None:
    if processed <= 0:
        return

    summary = dict(run.summary_json or {})
    total = max(int(batch_size or 0), 0)
    continuous = bool(summary.get("continuous"))
    if total > 0 and processed >= total and not continuous:
        return

    last_processed = int(summary.get("last_progress_notify_processed") or 0)
    cycle_index = int(summary.get("cycle_index") or 0)
    batch_source = str(summary.get("batch_source") or "")
    is_tecdoc_api_batch = batch_source == "tecdoc_api"
    progress_linked = int(summary.get("linked_in_cycle") or linked or 0) if is_tecdoc_api_batch else int(linked)
    progress_errors = int(summary.get("failed_in_cycle") or errors or 0) if is_tecdoc_api_batch else int(errors)

    last_linked = int(summary.get("last_progress_notify_linked") or 0)
    last_errors = int(summary.get("last_progress_notify_errors") or 0)
    last_cycle_index = int(summary.get("last_progress_notify_cycle_index") or 0)

    if (
        processed == last_processed
        and progress_linked == last_linked
        and progress_errors == last_errors
        and cycle_index == last_cycle_index
    ):
        return

    # In continuous mode keep notifications alive after requested_limit,
    # but avoid sending on every single item.
    if continuous and progress_linked == last_linked and progress_errors == last_errors and cycle_index == last_cycle_index:
        progress_step = 25
        if (processed - last_processed) < progress_step:
            return

    quota_used, quota_limit = _current_quota_snapshot()
    cycle_processed = int(summary.get("processed_in_cycle") or 0)
    cycle_total = int(summary.get("selected") or total or 0)
    send_system_autodb_batch_progress_notification(
        run_id=str(run.id),
        processed=processed,
        batch_size=total,
        linked=progress_linked,
        errors=progress_errors,
        quota_used=quota_used,
        quota_limit=quota_limit,
        cycle_index=cycle_index,
        cycle_processed=cycle_processed,
        cycle_total=cycle_total,
    )
    summary["last_progress_notify_processed"] = int(processed)
    summary["last_progress_notify_linked"] = int(progress_linked)
    summary["last_progress_notify_errors"] = int(progress_errors)
    summary["last_progress_notify_cycle_index"] = int(cycle_index)
    run.summary_json = summary
    run.save(update_fields=["summary_json", "updated_at"])


def _current_quota_snapshot() -> tuple[int, int]:
    quota_state = AutoDbRemoteQuotaState.objects.filter(remote_key=REMOTE_QUOTA_KEY).first()
    payload = AutoDbRemoteQuotaTracker().serialize(quota_state)
    used = int(payload.get("estimated_queries_used") or 0)
    limit = int(payload.get("estimated_limit_per_hour") or 0)
    return used, max(limit, 0)


@shared_task(name="autodb.check_remote_quota_recovery")
def check_remote_quota_recovery_task() -> dict[str, object]:
    quota = AutoDbRemoteQuotaState.objects.filter(remote_key=REMOTE_QUOTA_KEY).first()
    now = timezone.now()
    if quota is None:
        return {
            "remote_key": REMOTE_QUOTA_KEY,
            "status": "no_quota_state",
            "cooldown_until": None,
            "seconds_until_reset": 0,
            "skipped": True,
        }
    if not quota.cooldown_until:
        return {
            "remote_key": REMOTE_QUOTA_KEY,
            "status": "idle",
            "cooldown_until": None,
            "seconds_until_reset": 0,
            "skipped": True,
        }
    if quota.cooldown_until > now:
        seconds_left = max(int((quota.cooldown_until - now).total_seconds()), 0)
        return {
            "remote_key": REMOTE_QUOTA_KEY,
            "status": "waiting",
            "cooldown_until": quota.cooldown_until.isoformat(),
            "seconds_until_reset": seconds_left,
            "skipped": True,
        }
    payload = AutoDbRemoteQuotaTracker().serialize(quota)
    return {
        "remote_key": REMOTE_QUOTA_KEY,
        "status": str(payload.get("status") or ""),
        "cooldown_until": payload.get("cooldown_until"),
        "seconds_until_reset": int(payload.get("seconds_until_reset") or 0),
        "skipped": False,
    }


def _classify_batch_transient_error(exc: Exception) -> str:
    message = str(exc or "").lower()
    if (
        "1226" in message
        or "max_questions" in message
        or "quota" in message
        or "blocked by quota gate" in message
    ):
        return "quota_limit"
    if isinstance(exc, AutoDbProRemoteClientError):
        return "remote_disconnect"
    remote_tokens = (
        "timeout",
        "timed out",
        "connection",
        "server has gone away",
        "lost connection",
        "temporary failure",
        "unavailable",
    )
    if "remote" in message and any(token in message for token in remote_tokens):
        return "remote_disconnect"
    return ""


def _is_quota_or_remote_stop_error(exc: Exception) -> bool:
    return bool(_classify_batch_transient_error(exc))


def _wait_for_batch_quota_recovery(
    *,
    run: AutoDbMatchingRun,
    requested_limit: int,
    requested_product_ids_count: int,
    cycle_index: int,
    selected: int,
    selected_total: int,
    processed: int,
    processed_in_cycle: int,
    linked_in_cycle: int,
    failed_in_cycle: int,
    bound: int,
    failed: int,
    last_error: str,
    item,
    polling_seconds: int,
) -> None:
    tracker = AutoDbRemoteQuotaTracker()
    while True:
        quota = AutoDbRemoteQuotaState.objects.filter(remote_key=REMOTE_QUOTA_KEY).first()
        payload = tracker.serialize(quota)
        status_value = str(payload.get("status") or "")
        if status_value != "quota_paused":
            break
        seconds_left = int(payload.get("seconds_until_reset") or 0)
        wait_seconds = max(min(seconds_left, polling_seconds), 1) if seconds_left > 0 else polling_seconds
        wait_now = timezone.now()
        run.summary_json = {
            **(run.summary_json or {}),
            "running": True,
            "stage": "waiting_quota_recovery",
            "continuous": True,
            "requested_limit": requested_limit,
            "requested_product_ids_count": requested_product_ids_count,
            "cycle_index": cycle_index,
            "selected": selected,
            "selected_total": selected_total,
            "processed_in_cycle": int(max(processed_in_cycle, 0)),
            "linked_in_cycle": int(max(linked_in_cycle, 0)),
            "failed_in_cycle": int(max(failed_in_cycle, 0)),
            "processing_product_id": str(getattr(item, "product_id", "") or ""),
            "processing_supplier_id": int(getattr(item, "supplier_id", 0) or 0),
            "processing_article": str(getattr(item, "article", "") or ""),
            "retry_reason": "quota_limit",
            "retry_in_seconds": int(wait_seconds),
            "quota_cooldown_until": payload.get("cooldown_until"),
            "processed": processed,
            "bound": bound,
            "failed": failed,
            "stopped_reason": "",
            "last_error": last_error,
            "last_heartbeat_at": wait_now.isoformat(),
        }
        run.save(update_fields=["summary_json", "updated_at"])
        time.sleep(float(wait_seconds))


def _resolve_batch_candidate_via_public_search(
    *,
    client: AutoDbPublicApiClient,
    article: str,
    preferred_supplier_id: int,
    preferred_brand: str,
    supplier_display_cache: dict[int, str],
) -> tuple[int, str, str] | None:
    article_value = str(article or "").strip()
    if not article_value:
        return None
    try:
        candidates = client.search_candidates(article=article_value, limit=120)
    except Exception:  # noqa: BLE001
        return None
    if not candidates:
        return None

    preferred_supplier = int(preferred_supplier_id or 0)
    if preferred_supplier > 0:
        for item in candidates:
            supplier_id = int(item.get("supplier_id") or 0)
            if supplier_id != preferred_supplier:
                continue
            matched = str(item.get("matched_stored_article") or article_value).strip().upper()
            supplier_name = _supplier_display_name_from_autodb(supplier_id=supplier_id, cache=supplier_display_cache)
            if preferred_brand and (not supplier_name or supplier_name.isdigit()):
                supplier_name = str(preferred_brand).strip()
            return supplier_id, supplier_name, matched or article_value

    preferred_brand_norm = normalize_brand_lookup_key(preferred_brand)
    if preferred_brand_norm:
        for item in candidates:
            supplier_id = int(item.get("supplier_id") or 0)
            if supplier_id <= 0:
                continue
            supplier_name = _supplier_display_name_from_autodb(supplier_id=supplier_id, cache=supplier_display_cache)
            if normalize_brand_lookup_key(supplier_name) != preferred_brand_norm:
                continue
            matched = str(item.get("matched_stored_article") or article_value).strip().upper()
            if preferred_brand and (not supplier_name or supplier_name.isdigit()):
                supplier_name = str(preferred_brand).strip()
            return supplier_id, supplier_name, matched or article_value

    return None


def _supplier_display_name_from_autodb(*, supplier_id: int, cache: dict[int, str]) -> str:
    supplier_key = int(supplier_id or 0)
    if supplier_key <= 0:
        return ""
    cached = cache.get(supplier_key)
    if cached is not None:
        return cached
    supplier = AutoDbSupplier.objects.filter(id=supplier_key).first()
    label = str(getattr(supplier, "name", "") or getattr(supplier, "matchcode", "") or "").strip() or str(supplier_key)
    cache[supplier_key] = label
    return label


def _latest_raw_offer_brand_for_product(*, product_id: str) -> str:
    value = (
        SupplierRawOffer.objects.filter(matched_product_id=product_id)
        .exclude(brand_name="")
        .order_by("-updated_at")
        .values_list("brand_name", flat=True)
        .first()
    )
    return str(value or "").strip()


def _mark_link_brand_mismatch_needs_review(
    *,
    product_id: str,
    supplier_id: int,
    article_number: str,
    raw_brand: str,
    supplier_brand: str,
    reason: str,
) -> None:
    product = Product.objects.filter(pk=product_id).first()
    if product is None:
        return
    article_value = str(article_number or "").strip()
    if not article_value:
        article_value = str(getattr(product, "autodb_article_number", "") or "").strip()
    article_key = f"{int(supplier_id)}:{article_value}" if supplier_id and article_value else str(
        getattr(product, "autodb_article_key", "") or ""
    ).strip()
    if not article_key:
        return

    now = timezone.now()
    defaults = {
        "autodb_supplier_id": int(supplier_id),
        "autodb_article_number": article_value,
        "status": AutoDbProductLinkQuality.STATUS_NEEDS_MANUAL_REVIEW,
        "reason": reason,
        "evidence": {
            "source": "autodb.backoffice_tecdoc_batch_bind",
            "raw_offer_brand": str(raw_brand or ""),
            "supplier_brand": str(supplier_brand or ""),
            "product_id": str(product_id),
        },
        "checked_at": now,
    }
    quality, created = AutoDbProductLinkQuality.objects.get_or_create(
        product=product,
        autodb_article_key=article_key,
        defaults=defaults,
    )
    if created:
        return
    quality.autodb_supplier_id = int(supplier_id)
    quality.autodb_article_number = article_value
    quality.status = AutoDbProductLinkQuality.STATUS_NEEDS_MANUAL_REVIEW
    quality.reason = reason
    quality.evidence = defaults["evidence"]
    quality.checked_at = now
    quality.save(
        update_fields=[
            "autodb_supplier_id",
            "autodb_article_number",
            "status",
            "reason",
            "evidence",
            "checked_at",
            "updated_at",
        ]
    )


def _mark_link_clone_data_missing_needs_review(
    *,
    product_id: str,
    supplier_id: int,
    article_number: str,
    reason: str,
) -> None:
    product = Product.objects.filter(pk=product_id).first()
    if product is None:
        return
    article_value = str(article_number or "").strip()
    if not article_value:
        article_value = str(getattr(product, "autodb_article_number", "") or "").strip()
    article_key = f"{int(supplier_id)}:{article_value}" if supplier_id and article_value else str(
        getattr(product, "autodb_article_key", "") or ""
    ).strip()
    if not article_key:
        return

    now = timezone.now()
    defaults = {
        "autodb_supplier_id": int(supplier_id),
        "autodb_article_number": article_value,
        "status": AutoDbProductLinkQuality.STATUS_NEEDS_MANUAL_REVIEW,
        "reason": reason,
        "evidence": {
            "source": "autodb.backoffice_tecdoc_batch_bind",
            "reason": "clone_data_missing",
            "product_id": str(product_id),
        },
        "checked_at": now,
    }
    quality, created = AutoDbProductLinkQuality.objects.get_or_create(
        product=product,
        autodb_article_key=article_key,
        defaults=defaults,
    )
    if created:
        return
    quality.autodb_supplier_id = int(supplier_id)
    quality.autodb_article_number = article_value
    quality.status = AutoDbProductLinkQuality.STATUS_NEEDS_MANUAL_REVIEW
    quality.reason = reason
    quality.evidence = defaults["evidence"]
    quality.checked_at = now
    quality.save(
        update_fields=[
            "autodb_supplier_id",
            "autodb_article_number",
            "status",
            "reason",
            "evidence",
            "checked_at",
            "updated_at",
        ]
    )


def _apply_fallback_name_translation_for_product(*, product_id: str, reason: str) -> None:
    product = Product.objects.filter(pk=product_id).first()
    if product is None or is_product_name_manual_locked(product):
        return

    source_text = (
        str(getattr(product, "name_source_text", "") or "").strip()
        or str(getattr(product, "name_uk", "") or "").strip()
        or str(getattr(product, "name_ru", "") or "").strip()
        or str(getattr(product, "name_en", "") or "").strip()
        or str(getattr(product, "name", "") or "").strip()
    )[:255]
    if not source_text:
        return

    translation = ProductNameTranslationService().translate_product_name(source_text=source_text)
    update_fields: list[str] = []
    for field, value in (
        ("name_uk", str(translation.uk or source_text).strip()[:255]),
        ("name_ru", str(translation.ru or source_text).strip()[:255]),
        ("name_en", str(translation.en or source_text).strip()[:255]),
    ):
        current = str(getattr(product, field, "") or "")
        if value and current != value:
            setattr(product, field, value)
            update_fields.append(field)

    status_value = str(translation.status or "").strip() or Product.NAME_TRANSLATION_PENDING
    if str(getattr(product, "name_translation_status", "") or "") != status_value:
        product.name_translation_status = status_value
        update_fields.append("name_translation_status")
    error_value = str(translation.error or "").strip()
    if not error_value and reason:
        error_value = f"fallback:{reason[:80]}"
    if str(getattr(product, "name_translation_error", "") or "") != error_value:
        product.name_translation_error = error_value
        update_fields.append("name_translation_error")

    if update_fields:
        product.save(update_fields=[*update_fields, "updated_at"])


def _resolve_supplier_by_brand(*, matcher: SupplierBrandMatcher, raw_brand: str) -> tuple[int | None, str, str]:
    normalized = normalize_brand_lookup_key(raw_brand)
    if not normalized:
        return None, "", "brand_not_found"
    result = matcher.resolve_many([normalized]).get(normalized)
    if result is None or not result.matched_supplier_id:
        return None, "", "brand_not_found"

    supplier_name = ""
    if result.candidates:
        top = result.candidates[0]
        supplier_name = str(top.supplier_matchcode or top.supplier_description or "").strip()
    return int(result.matched_supplier_id), supplier_name, str(result.reason or "")


def _resolve_article_for_supplier(*, storage: AutoDbRawCloneStorage, supplier_id: int, article_input: str) -> str:
    supplier_value = int(supplier_id or 0)
    article_raw = str(article_input or "").strip()
    if supplier_value <= 0 or not article_raw:
        return ""

    variants: list[str] = []
    for value in (article_raw, article_raw.replace(" ", ""), normalize_article(article_raw)):
        candidate = str(value or "").strip()
        if candidate and candidate not in variants:
            variants.append(candidate)

    for table in ("article_numbers", "articles"):
        columns = list(storage.get_local_columns(table))
        if not columns:
            continue
        supplier_column = storage.first_existing_column(table=table, candidates=["supplierId", "supplierid", "SupplierId", "supplier_id"])
        article_column = storage.first_existing_column(
            table=table,
            candidates=["DataSupplierArticleNumber", "datasupplierarticlenumber", "article", "articlenumber", "number"],
        )
        if not supplier_column or not article_column:
            continue
        rows = storage.fetch_local_rows_in(
            table=table,
            column=article_column,
            values=variants,
            extra_filters={supplier_column: supplier_value},
            limit=50,
            columns=[article_column],
        )
        if not rows:
            continue
        by_lower = {str(row.get(article_column) or "").strip().lower(): str(row.get(article_column) or "").strip() for row in rows}
        direct = by_lower.get(article_raw.lower())
        if direct:
            return direct
        for variant in variants:
            hit = by_lower.get(str(variant).lower())
            if hit:
                return hit
        first = str(rows[0].get(article_column) or "").strip()
        if first:
            return first
    return ""
