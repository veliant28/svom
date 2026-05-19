from __future__ import annotations

import contextlib
import signal

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.autodb.models import AutoDbMatchingRun, AutoDbSupplier
from apps.autodb.services.matching.backoffice_tecdoc_batch import BackofficeTecdocBatchSelector
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
            previous_name = str(getattr(product, "name", "") or "")
            previous_source_text = str(getattr(product, "name_source_text", "") or "")
            article_name = resolve_autodb_article_name(
                normalized_article=normalized_article,
                normalized_brand=normalized_supplier,
                prefer_live=True,
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

        if skip_clone_enrichment:
            clone_result = None
        else:
            clone_result = AutoDbArticleEnrichmentService().enrich_article(
                supplier_id=int(supplier_id),
                article_number=article_value,
                dry_run=False,
                replace_local=clone_replace_local,
            )
        name_result = AutoDbProductNameEnrichmentService().enrich_product(
            product=product,
            dry_run=False,
            only_missing_translations=False,
        )
        fitment_result = AutoDbProductFitmentEnrichmentService().enrich_product(product=product, dry_run=False)
        image_result = AutoDbProductImageEnrichmentService().sync_product_images(
            product=product,
            dry_run=False,
            prefer_gpl=True,
        )

    return {
        "status": "bound",
        "product_id": str(product_id),
        "autodb_article_key": article_key,
        "quality_created": bool(created),
        "clone": {
            "remote_queries": int(clone_result.remote_queries) if clone_result is not None else 0,
            "remote_hits": int(clone_result.remote_hits) if clone_result is not None else 0,
            "populated_tables": clone_result.populated_tables if clone_result is not None else {},
        },
        "name": {
            "status": name_result.status,
            "source_title": name_result.autodb_source_title,
            "name_uk": name_result.new_name_uk,
            "name_ru": name_result.new_name_ru,
            "name_en": name_result.new_name_en,
            "translation_status": name_result.translation_status,
            "translation_error": name_result.translation_error,
        },
        "fitments": {
            "status": fitment_result.status,
            "created": int(fitment_result.fitments_created),
            "updated": int(fitment_result.fitments_updated),
            "stale_marked": int(fitment_result.stale_marked),
        },
        "attributes": {
            "status": "clone_only_source",
            "created": 0,
            "updated": 0,
        },
        "images": {
            "created": int(image_result.created),
            "reused": int(image_result.reused),
            "stale_marked": int(image_result.stale_marked),
        },
    }


BACKOFFICE_TECDOC_BATCH_RUN_TYPE = "backoffice_tecdoc_batch_bind"
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
) -> dict[str, object]:
    run = AutoDbMatchingRun.objects.filter(id=run_id).first()
    if run is None:
        return {"status": "not_found", "detail": "run not found", "run_id": str(run_id)}

    requested_limit = max(1, min(int(limit or 0), 1000))
    requested_product_ids_count = len(product_ids or [])
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
        "stopped_reason": "",
        "last_error": "",
        "actor_id": str(actor_id or ""),
        "started_at": run.started_at.isoformat() if run.started_at else started_at.isoformat(),
        "last_heartbeat_at": started_at.isoformat(),
    }
    run.save(update_fields=["started_at", "status", "error", "summary_json", "updated_at"])

    selector = BackofficeTecdocBatchSelector()
    brand_matcher = SupplierBrandMatcher()
    clone_storage = AutoDbRawCloneStorage()
    candidates = selector.select_candidates(
        limit=requested_limit,
        product_ids=product_ids,
    )
    results: list[dict[str, object]] = []
    processed = 0
    bound = 0
    failed = 0
    stop_reason = ""
    last_error = ""
    now = timezone.now()
    run.summary_json = {
        **(run.summary_json or {}),
        "running": True,
        "stage": "processing_items",
        "requested_limit": requested_limit,
        "requested_product_ids_count": requested_product_ids_count,
        "selected": len(candidates),
        "processed": processed,
        "bound": bound,
        "failed": failed,
        "stopped_reason": stop_reason,
        "last_error": last_error,
        "last_heartbeat_at": now.isoformat(),
    }
    run.save(update_fields=["summary_json", "updated_at"])

    for index, item in enumerate(candidates, start=1):
        loop_heartbeat = timezone.now()
        run.summary_json = {
            **(run.summary_json or {}),
            "running": True,
            "stage": "processing_item",
            "requested_limit": requested_limit,
            "requested_product_ids_count": requested_product_ids_count,
            "selected": len(candidates),
            "processing_index": index,
            "processing_product_id": str(item.product_id),
            "processing_supplier_id": int(item.supplier_id),
            "processing_article": str(item.article or ""),
            "processed": processed,
            "bound": bound,
            "failed": failed,
            "stopped_reason": stop_reason,
            "last_error": last_error,
            "last_heartbeat_at": loop_heartbeat.isoformat(),
        }
        run.save(update_fields=["summary_json", "updated_at"])
        try:
            bind_supplier_id = int(item.supplier_id)
            bind_article = str(item.article or "")
            bind_supplier_name = str(item.supplier_name or "")
            relinked_by_brand_guard = False
            raw_offer_brand = ""

            with _batch_item_timeout(BACKOFFICE_TECDOC_BATCH_ITEM_TIMEOUT_SECONDS):
                raw_offer_brand = _latest_raw_offer_brand_for_product(product_id=item.product_id)
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
                                continue
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
                            continue

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
                if not pre_clone_has_data:
                    _mark_link_clone_data_missing_needs_review(
                        product_id=item.product_id,
                        supplier_id=bind_supplier_id,
                        article_number=bind_article,
                        reason="batch_clone_data_missing_before_bind",
                    )
                    _apply_fallback_name_translation_for_product(
                        product_id=str(item.product_id),
                        reason="remote_or_clone_rows_not_found_for_article",
                    )
                    processed += 1
                    failed += 1
                    results.append(
                        {
                            "product_id": item.product_id,
                            "supplier_id": bind_supplier_id,
                            "article": bind_article,
                            "status": "clone_data_missing",
                            "reason": "remote_or_clone_rows_not_found_for_article",
                            "relinked_by_brand_guard": relinked_by_brand_guard,
                        }
                    )
                    continue

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
            if status_value == "bound":
                bound += 1
            else:
                _apply_fallback_name_translation_for_product(
                    product_id=str(item.product_id),
                    reason=f"bind_status_{status_value or 'error'}",
                )
                failed += 1
            results.append(
                {
                    "product_id": item.product_id,
                    "supplier_id": bind_supplier_id,
                    "article": bind_article,
                    "status": status_value or "error",
                    "relinked_by_brand_guard": relinked_by_brand_guard,
                    "detail": bind_result,
                }
            )
        except Exception as exc:  # noqa: BLE001
            processed += 1
            failed += 1
            error_text = str(exc)
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
            results.append(
                {
                    "product_id": item.product_id,
                    "supplier_id": int(item.supplier_id),
                    "article": item.article,
                    "status": "error",
                    "reason": error_text,
                }
            )
            if _is_quota_or_remote_stop_error(exc):
                stop_reason = "quota_or_remote_error"
                last_error = error_text
                break

        loop_done = timezone.now()
        run.summary_json = {
            **(run.summary_json or {}),
            "running": True,
            "stage": "processing_items",
            "requested_limit": requested_limit,
            "requested_product_ids_count": requested_product_ids_count,
            "selected": len(candidates),
            "processed": processed,
            "bound": bound,
            "failed": failed,
            "stopped_reason": stop_reason,
            "last_error": last_error,
            "last_heartbeat_at": loop_done.isoformat(),
        }
        run.save(update_fields=["summary_json", "updated_at"])

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
        "requested_limit": requested_limit,
        "requested_product_ids_count": requested_product_ids_count,
        "selected": len(candidates),
        "processed": processed,
        "bound": bound,
        "failed": failed,
        "stopped_reason": stop_reason,
        "last_error": last_error,
        "last_heartbeat_at": finished_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "results_preview": results[:50],
    }
    run.save(update_fields=["status", "finished_at", "error", "summary_json", "updated_at"])

    return {
        "status": "done",
        "run_id": str(run.id),
        "selected": len(candidates),
        "processed": processed,
        "bound": bound,
        "failed": failed,
        "stopped_reason": stop_reason,
        "last_error": last_error,
    }


def _is_quota_or_remote_stop_error(exc: Exception) -> bool:
    if isinstance(exc, AutoDbProRemoteClientError):
        return True
    message = str(exc or "").lower()
    if "1226" in message or "max_questions" in message or "quota" in message:
        return True
    return "remote" in message and ("timeout" in message or "connection" in message or "unavailable" in message)


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
