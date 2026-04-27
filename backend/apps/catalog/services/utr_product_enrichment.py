from __future__ import annotations

import hashlib
import logging
import mimetypes
from dataclasses import dataclass
from datetime import timedelta
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.db.models import Q
from django.utils import timezone

from apps.autocatalog.models import UtrArticleDetailMap, UtrDetailCarMap
from apps.autocatalog.services.utr_article_detail_resolver.persistence import upsert_mapping as upsert_utr_article_detail_mapping
from apps.autocatalog.services.utr_article_detail_resolver.selector import select_candidate_ids
from apps.autocatalog.services.utr_autocatalog_import_service import UtrAutocatalogImportService
from apps.catalog.models import Product, ProductImage, UtrProductEnrichment
from apps.supplier_imports.parsers.utils import normalize_article, normalize_brand
from apps.supplier_imports.selectors import get_supplier_integration_by_code
from apps.supplier_imports.services.integrations.exceptions import SupplierClientError, SupplierIntegrationError
from apps.supplier_imports.services.integrations.utr.client import UtrClient

logger = logging.getLogger(__name__)

_MAX_VISIBLE_ENRICHMENT_PRODUCTS = 60
_ENRICHMENT_MODE_CATALOG = "catalog"
_ENRICHMENT_MODE_DETAIL = "detail"
_ENRICHMENT_MODES = {_ENRICHMENT_MODE_CATALOG, _ENRICHMENT_MODE_DETAIL}
_QUEUED_RETRY_AFTER = timedelta(minutes=5)
_IN_PROGRESS_RETRY_AFTER = timedelta(seconds=30)
_FAILED_RETRY_AFTER = timedelta(hours=6)
_UNAVAILABLE_RETRY_AFTER = timedelta(hours=24)
_MAX_IMAGE_BYTES = 10 * 1024 * 1024
_MIME_EXTENSION_OVERRIDES = {
    "image/webp": ".webp",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
}


@dataclass(frozen=True)
class UtrEnrichmentStatus:
    product_id: str
    status: str
    utr_detail_id: str
    primary_image: str
    characteristics_count: int
    fitments_count: int
    needs_enrichment: bool = False
    processed: bool = False
    queued: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "product_id": self.product_id,
            "status": self.status,
            "utr_detail_id": self.utr_detail_id,
            "primary_image": self.primary_image,
            "characteristics_count": self.characteristics_count,
            "fitments_count": self.fitments_count,
            "needs_enrichment": self.needs_enrichment,
            "processed": self.processed,
            "queued": self.queued,
        }


def request_visible_utr_enrichment(
    *,
    product_ids: list[str],
    request=None,
    enqueue: bool = True,
    mode: str = _ENRICHMENT_MODE_DETAIL,
) -> list[dict[str, object]]:
    normalized_ids = _normalize_product_ids(product_ids)[:_MAX_VISIBLE_ENRICHMENT_PRODUCTS]
    if not normalized_ids:
        return []
    enrichment_mode = _normalize_enrichment_mode(mode)

    products = list(
        Product.objects.filter(id__in=normalized_ids)
        .select_related("brand", "utr_enrichment")
        .prefetch_related("images")
    )
    product_by_id = {str(product.id): product for product in products}
    rows: list[dict[str, object]] = []
    queued_ids: list[str] = []
    queued_id_set: set[str] = set()

    if enqueue:
        if enrichment_mode == _ENRICHMENT_MODE_CATALOG:
            visible_products = [product_by_id[product_id] for product_id in normalized_ids if product_id in product_by_id]
            queued_ids = _enqueue_visible_catalog_enrichment(products=visible_products)
            _enqueue_visible_catalog_applicability(detail_ids=_visible_catalog_detail_ids(products=visible_products))
        else:
            for product_id in normalized_ids:
                product = product_by_id.get(product_id)
                if product is None:
                    continue
                enrichment = getattr(product, "utr_enrichment", None)
                if enrichment is None:
                    enrichment, _ = UtrProductEnrichment.objects.get_or_create(product=product)
                    product.utr_enrichment = enrichment
                if not _should_enqueue(product=product, enrichment=enrichment, mode=enrichment_mode):
                    continue

                if _enqueue_utr_product_enrichment(product=product, enrichment=enrichment, mode=enrichment_mode):
                    queued_ids.append(str(product.id))
        queued_id_set = set(queued_ids)

    for product_id in normalized_ids:
        product = product_by_id.get(product_id)
        if product is None:
            continue
        rows.append(
            _prepare_product_enrichment_status(
                product=product,
                request=request,
                enqueue=False,
                mode=enrichment_mode,
                processed=False,
                queued=str(product.id) in queued_id_set,
            ).as_dict()
        )

    return rows


def enrich_utr_product(*, product_id: str, mode: str = _ENRICHMENT_MODE_DETAIL) -> dict[str, object]:
    enrichment_mode = _normalize_enrichment_mode(mode)
    product = Product.objects.select_related("brand").filter(id=product_id).first()
    if product is None:
        return {"product_id": product_id, "status": "missing_product"}

    enrichment, _ = UtrProductEnrichment.objects.get_or_create(product=product)
    now = timezone.now()
    client = UtrClient()

    detail_id = resolve_utr_detail_id(product=product)
    if not detail_id:
        try:
            access_token = _resolve_utr_access_token(client=client)
            detail_id = resolve_and_persist_utr_detail_id(product=product, client=client, access_token=access_token)
        except Exception as exc:  # noqa: BLE001
            logger.warning("utr_product_detail_id_resolution_failed product_id=%s error=%s", product.id, exc)
            enrichment.status = UtrProductEnrichment.STATUS_FAILED
            enrichment.last_attempt_at = now
            enrichment.next_retry_at = timezone.now() + _FAILED_RETRY_AFTER
            enrichment.error_message = str(exc)[:2000]
            enrichment.save(update_fields=("status", "last_attempt_at", "next_retry_at", "error_message", "updated_at"))
            return {"product_id": str(product.id), "status": enrichment.status, "error": enrichment.error_message}

        if not detail_id:
            enrichment.status = UtrProductEnrichment.STATUS_UNAVAILABLE
            enrichment.last_attempt_at = now
            enrichment.next_retry_at = timezone.now() + _UNAVAILABLE_RETRY_AFTER
            enrichment.error_message = "UTR detail_id is not available for product."
            enrichment.save(update_fields=("status", "last_attempt_at", "next_retry_at", "error_message", "updated_at"))
            return {"product_id": str(product.id), "status": enrichment.status}
    else:
        access_token = ""

    enrichment.utr_detail_id = detail_id
    enrichment.status = UtrProductEnrichment.STATUS_IN_PROGRESS
    enrichment.last_attempt_at = now
    enrichment.error_message = ""
    enrichment.save(update_fields=("utr_detail_id", "status", "last_attempt_at", "error_message", "updated_at"))

    try:
        if not access_token:
            access_token = _resolve_utr_access_token(client=client)
        detail_payload = client.fetch_detail(
            access_token=access_token,
            detail_id=detail_id,
            request_reason="lazy_product_detail_enrichment",
        )
        images_payload = _extract_images_payload(detail_payload)
        created_images = _create_missing_product_images(product=product, images_payload=images_payload)

        characteristics_payload = (
            enrichment.characteristics_payload
            if isinstance(enrichment.characteristics_payload, list)
            else []
        )
        if enrichment_mode == _ENRICHMENT_MODE_DETAIL and _lazy_characteristics_enabled():
            try:
                characteristics_payload = client.fetch_characteristics(
                    access_token=access_token,
                    detail_id=detail_id,
                    request_reason="lazy_product_characteristics_enrichment",
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "utr_product_characteristics_failed product_id=%s detail_id=%s error=%s",
                    product.id,
                    detail_id,
                    exc,
                )

        applicability_summary = None
        if enrichment_mode == _ENRICHMENT_MODE_DETAIL and _lazy_applicability_enabled():
            try:
                applicability_summary = UtrAutocatalogImportService(client=client).import_from_detail_ids(
                    detail_ids=[detail_id],
                    access_token=access_token,
                    continue_on_error=True,
                    force_refresh=False,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "utr_product_applicability_failed product_id=%s detail_id=%s error=%s",
                    product.id,
                    detail_id,
                    exc,
                )

        enrichment.detail_payload = detail_payload
        enrichment.characteristics_payload = characteristics_payload
        enrichment.images_payload = images_payload
        enrichment.status = UtrProductEnrichment.STATUS_FETCHED
        enrichment.fetched_at = timezone.now()
        enrichment.next_retry_at = None
        enrichment.error_message = ""
        enrichment.save(
            update_fields=(
                "detail_payload",
                "characteristics_payload",
                "images_payload",
                "status",
                "fetched_at",
                "next_retry_at",
                "error_message",
                "updated_at",
            )
        )
        return {
            "product_id": str(product.id),
            "status": enrichment.status,
            "utr_detail_id": detail_id,
            "created_image": created_images > 0,
            "created_images": created_images,
            "characteristics_count": len(characteristics_payload),
            "applicability": applicability_summary.to_dict() if applicability_summary else None,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("utr_product_enrichment_failed product_id=%s detail_id=%s error=%s", product.id, detail_id, exc)
        enrichment.status = UtrProductEnrichment.STATUS_FAILED
        enrichment.next_retry_at = timezone.now() + _FAILED_RETRY_AFTER
        enrichment.error_message = str(exc)[:2000]
        enrichment.save(update_fields=("status", "next_retry_at", "error_message", "updated_at"))
        return {
            "product_id": str(product.id),
            "status": enrichment.status,
            "utr_detail_id": detail_id,
            "error": enrichment.error_message,
        }


def enrich_utr_catalog_products(*, product_ids: list[str]) -> dict[str, object]:
    normalized_ids = _normalize_product_ids(product_ids)[:_MAX_VISIBLE_ENRICHMENT_PRODUCTS]
    if not normalized_ids:
        return {"requested": 0, "processed": 0, "created_images": 0, "batches": 0, "applicability_queued": 0}

    products = list(
        Product.objects.filter(id__in=normalized_ids)
        .select_related("brand", "utr_enrichment")
        .prefetch_related("images")
    )
    product_by_id = {str(product.id): product for product in products}
    products = [product_by_id[product_id] for product_id in normalized_ids if product_id in product_by_id]
    if not products:
        return {"requested": len(normalized_ids), "processed": 0, "created_images": 0, "batches": 0, "applicability_queued": 0}

    now = timezone.now()
    enrichments: dict[str, UtrProductEnrichment] = {}
    eligible_products: list[Product] = []
    for product in products:
        enrichment = getattr(product, "utr_enrichment", None)
        if enrichment is None:
            enrichment, _ = UtrProductEnrichment.objects.get_or_create(product=product)
            product.utr_enrichment = enrichment
        enrichments[str(product.id)] = enrichment
        if _has_complete_image_set(product=product, enrichment=enrichment):
            continue
        eligible_products.append(product)

    if not eligible_products:
        return {
            "requested": len(normalized_ids),
            "processed": 0,
            "created_images": 0,
            "batches": 0,
            "applicability_queued": _enqueue_visible_catalog_applicability(
                detail_ids=_visible_catalog_detail_ids(products=products)
            ),
        }

    UtrProductEnrichment.objects.filter(product_id__in=[product.id for product in eligible_products]).update(
        status=UtrProductEnrichment.STATUS_IN_PROGRESS,
        last_attempt_at=now,
        error_message="",
        updated_at=now,
    )

    client = UtrClient()
    access_token = _resolve_utr_access_token(client=client)
    batch_size = max(int(getattr(settings, "UTR_LAZY_CATALOG_BATCH_SIZE", 25)), 1)
    processed = 0
    created_images = 0
    batches = 0
    unresolved_products = eligible_products
    resolved_detail_ids: list[str] = []

    for stage_index in range(4):
        queries: list[dict[str, str]] = []
        contexts: list[tuple[Product, dict[str, str]]] = []
        for product in unresolved_products:
            query = _build_catalog_batch_query(product=product, stage_index=stage_index)
            if query is None:
                continue
            queries.append(query)
            contexts.append((product, query))
        if not queries:
            break

        next_unresolved: list[Product] = []
        for start in range(0, len(queries), batch_size):
            chunk = queries[start : start + batch_size]
            context_chunk = contexts[start : start + batch_size]
            batches += 1
            batch_result = client.search_details_batch(
                access_token=access_token,
                details=chunk,
                request_reason="lazy_catalog_batch_image_enrichment",
            )
            access_token = batch_result.access_token
            for row, context in zip(batch_result.rows, context_chunk, strict=False):
                product, query = context
                detail = _select_catalog_batch_detail(row=row, query=query)
                if detail is None:
                    next_unresolved.append(product)
                    continue
                enrichment = enrichments[str(product.id)]
                result = _apply_catalog_batch_detail(product=product, enrichment=enrichment, detail=detail)
                processed += 1
                created_images += result["created_images"]
                detail_id = str(result.get("detail_id") or "").strip()
                if detail_id:
                    resolved_detail_ids.append(detail_id)

        unresolved_products = next_unresolved
        if not unresolved_products:
            break

    if unresolved_products:
        retry_at = timezone.now() + _UNAVAILABLE_RETRY_AFTER
        UtrProductEnrichment.objects.filter(product_id__in=[product.id for product in unresolved_products]).update(
            status=UtrProductEnrichment.STATUS_UNAVAILABLE,
            next_retry_at=retry_at,
            error_message="UTR detail_id is not available for product.",
            updated_at=timezone.now(),
        )

    return {
        "requested": len(normalized_ids),
        "processed": processed,
        "created_images": created_images,
        "batches": batches,
        "unresolved": len(unresolved_products),
        "applicability_queued": _enqueue_visible_catalog_applicability(detail_ids=resolved_detail_ids),
    }


def enrich_visible_utr_applicability(*, detail_ids: list[str]) -> dict[str, object]:
    normalized_detail_ids = _normalize_detail_ids(detail_ids)
    if not normalized_detail_ids:
        return {"requested": 0, "processed": 0, "skipped_cached": 0, "failed": 0}
    if not _lazy_catalog_applicability_enabled():
        return {"requested": len(normalized_detail_ids), "processed": 0, "skipped_disabled": len(normalized_detail_ids), "failed": 0}

    client = UtrClient()
    access_token = _resolve_utr_access_token(client=client)
    summary = UtrAutocatalogImportService(client=client).import_from_detail_ids(
        detail_ids=normalized_detail_ids,
        access_token=access_token,
        continue_on_error=True,
        force_refresh=False,
    )
    return summary.to_dict()


def resolve_utr_detail_id(*, product: Product) -> str:
    product_detail_id = str(product.utr_detail_id or "").strip()
    if product_detail_id:
        return product_detail_id

    if not _has_utr_source(product=product):
        return ""

    article = normalize_article(product.article or product.sku)
    brand_name = getattr(product.brand, "name", "")
    brand = normalize_brand(brand_name)
    if not article:
        return ""

    query = UtrArticleDetailMap.objects.filter(normalized_article=article).exclude(utr_detail_id="")
    if brand:
        branded = query.filter(normalized_brand=brand).first()
        if branded is not None:
            return str(branded.utr_detail_id or "").strip()

    fallback = query.filter(normalized_brand="").first()
    if fallback is not None:
        return str(fallback.utr_detail_id or "").strip()
    return ""


def resolve_and_persist_utr_detail_id(*, product: Product, client: UtrClient, access_token: str) -> str:
    if not _has_utr_source(product=product):
        return ""

    brand_name = str(getattr(product.brand, "name", "") or "").strip()
    normalized_brand = normalize_brand(brand_name)
    candidates = _build_detail_resolution_candidates(product=product, brand_name=brand_name)

    for candidate in candidates:
        article = candidate["article"]
        normalized_article = candidate["normalized_article"]
        brand = candidate["brand"]
        details = client.search_details(
            access_token=access_token,
            oem=article,
            brand=brand,
            request_reason="lazy_product_detail_id_resolution",
        )
        detail_ids = select_candidate_ids(
            details=details,
            normalized_article=normalized_article,
            normalized_brand=normalized_brand if brand else "",
        )
        if len(detail_ids) != 1:
            continue

        detail_id = detail_ids[0]
        upsert_utr_article_detail_mapping(
            article=article,
            normalized_article=normalized_article,
            brand_name=brand_name if brand else "",
            normalized_brand=normalized_brand if brand else "",
            utr_detail_id=detail_id,
        )
        if str(product.utr_detail_id or "").strip() != detail_id:
            Product.objects.filter(id=product.id, utr_detail_id="").update(utr_detail_id=detail_id, updated_at=timezone.now())
            product.utr_detail_id = detail_id
        return detail_id

    article = str(product.article or product.sku or "").strip()
    normalized_article = normalize_article(article)
    if normalized_article:
        upsert_utr_article_detail_mapping(
            article=article,
            normalized_article=normalized_article,
            brand_name=brand_name,
            normalized_brand=normalized_brand,
            utr_detail_id="",
        )
    return ""


def _build_detail_resolution_candidates(*, product: Product, brand_name: str) -> list[dict[str, str]]:
    raw_articles = [str(product.article or "").strip(), str(product.sku or "").strip()]
    articles: list[tuple[str, str]] = []
    seen: set[str] = set()
    for article in raw_articles:
        normalized_article = normalize_article(article)
        if not article or not normalized_article or normalized_article in seen:
            continue
        seen.add(normalized_article)
        articles.append((article, normalized_article))

    candidates: list[dict[str, str]] = []
    for article, normalized_article in articles:
        if brand_name:
            candidates.append({"article": article, "normalized_article": normalized_article, "brand": brand_name})
    for article, normalized_article in articles:
        candidates.append({"article": article, "normalized_article": normalized_article, "brand": ""})
    return candidates


def _build_catalog_batch_query(*, product: Product, stage_index: int) -> dict[str, str] | None:
    detail_id = resolve_utr_detail_id(product=product)
    if detail_id:
        if stage_index == 0:
            return {"id": detail_id}
        return None

    brand_name = str(getattr(product.brand, "name", "") or "").strip()
    candidates = _build_detail_resolution_candidates(product=product, brand_name=brand_name)
    if stage_index >= len(candidates):
        return None
    candidate = candidates[stage_index]
    query = {
        "oem": candidate["article"],
        "brand": candidate["brand"],
        "normalized_article": candidate["normalized_article"],
        "normalized_brand": normalize_brand(brand_name) if candidate["brand"] else "",
    }
    return query


def _select_catalog_batch_detail(*, row: dict, query: dict[str, str]) -> dict | None:
    details = row.get("details") if isinstance(row, dict) else None
    if not isinstance(details, list):
        return None
    normalized_details = [item for item in details if isinstance(item, dict)]
    detail_id = str(query.get("id") or "").strip()
    if detail_id:
        for item in normalized_details:
            if str(item.get("id") or "").strip() == detail_id:
                return item
        return normalized_details[0] if normalized_details else None

    detail_ids = select_candidate_ids(
        details=normalized_details,
        normalized_article=str(query.get("normalized_article") or ""),
        normalized_brand=str(query.get("normalized_brand") or ""),
    )
    if len(detail_ids) != 1:
        return None
    selected_id = detail_ids[0]
    for item in normalized_details:
        if str(item.get("id") or "").strip() == selected_id:
            return item
    return None


def _apply_catalog_batch_detail(*, product: Product, enrichment: UtrProductEnrichment, detail: dict) -> dict[str, int | str]:
    detail_id = str(detail.get("id") or "").strip()
    images_payload = _extract_images_payload(detail)
    created_images = _create_missing_product_images(product=product, images_payload=images_payload)
    characteristics_payload = enrichment.characteristics_payload if isinstance(enrichment.characteristics_payload, list) else []

    if detail_id:
        article = str(product.article or product.sku or "").strip()
        normalized_article = normalize_article(article)
        brand_name = str(getattr(product.brand, "name", "") or "").strip()
        normalized_brand = normalize_brand(brand_name)
        if normalized_article:
            upsert_utr_article_detail_mapping(
                article=article,
                normalized_article=normalized_article,
                brand_name=brand_name,
                normalized_brand=normalized_brand,
                utr_detail_id=detail_id,
            )
        if str(product.utr_detail_id or "").strip() != detail_id:
            Product.objects.filter(id=product.id).update(utr_detail_id=detail_id, updated_at=timezone.now())
            product.utr_detail_id = detail_id

    enrichment.utr_detail_id = detail_id or enrichment.utr_detail_id
    enrichment.detail_payload = detail
    enrichment.images_payload = images_payload
    enrichment.characteristics_payload = characteristics_payload
    enrichment.status = UtrProductEnrichment.STATUS_FETCHED
    enrichment.fetched_at = timezone.now()
    enrichment.next_retry_at = None
    enrichment.error_message = ""
    enrichment.save(
        update_fields=(
            "utr_detail_id",
            "detail_payload",
            "images_payload",
            "characteristics_payload",
            "status",
            "fetched_at",
            "next_retry_at",
            "error_message",
            "updated_at",
        )
    )
    return {"detail_id": detail_id, "created_images": created_images}


def apply_utr_search_detail_to_matching_products(
    *,
    article: str,
    normalized_article: str,
    brand_name: str,
    normalized_brand: str,
    detail: dict,
) -> dict[str, int]:
    detail_id = str(detail.get("id") or "").strip()
    images_payload = _extract_images_payload(detail)
    if not detail_id and not images_payload:
        return {"products_matched": 0, "products_enriched": 0, "created_images": 0}

    raw_article = str(article or "").strip()
    normalized_article_value = str(normalized_article or "").strip()
    normalized_brand_value = str(normalized_brand or "").strip()
    if not raw_article or not normalized_article_value:
        return {"products_matched": 0, "products_enriched": 0, "created_images": 0}

    candidates = list(
        Product.objects.filter(Q(article__iexact=raw_article) | Q(sku__iexact=raw_article))
        .select_related("brand", "utr_enrichment")
        .prefetch_related("images")[:20]
    )

    matched_products: list[Product] = []
    for product in candidates:
        product_article = normalize_article(product.article or product.sku)
        if product_article != normalized_article_value:
            continue
        product_brand = normalize_brand(getattr(product.brand, "name", ""))
        if normalized_brand_value and product_brand != normalized_brand_value:
            continue
        matched_products.append(product)

    products_enriched = 0
    created_images = 0
    fallback_brand_name = str(brand_name or "").strip()
    for product in matched_products:
        enrichment = getattr(product, "utr_enrichment", None)
        if enrichment is None:
            enrichment, _ = UtrProductEnrichment.objects.get_or_create(product=product)
            product.utr_enrichment = enrichment
        result = _apply_catalog_batch_detail(product=product, enrichment=enrichment, detail=detail)
        products_enriched += 1
        created_images += int(result.get("created_images") or 0)

        if detail_id and not getattr(product, "brand_id", None) and fallback_brand_name:
            logger.debug(
                "utr_search_detail_product_enriched_without_brand product_id=%s article=%s brand=%s detail_id=%s",
                product.id,
                raw_article,
                fallback_brand_name,
                detail_id,
            )

    return {
        "products_matched": len(matched_products),
        "products_enriched": products_enriched,
        "created_images": created_images,
    }


def build_utr_characteristic_attributes(*, product: Product) -> list[dict[str, str]]:
    enrichment = getattr(product, "utr_enrichment", None)
    if enrichment is None or not isinstance(enrichment.characteristics_payload, list):
        return []

    rows: list[dict[str, str]] = []
    for index, item in enumerate(enrichment.characteristics_payload):
        if not isinstance(item, dict):
            continue
        attribute_payload = item.get("attribute") if isinstance(item.get("attribute"), dict) else {}
        name = str(attribute_payload.get("title") or attribute_payload.get("name") or item.get("name") or "").strip()
        value = str(item.get("value") or "").strip()
        if not name or not value:
            continue
        rows.append(
            {
                "id": f"utr-{enrichment.utr_detail_id}-{index}",
                "attribute_name": name,
                "value": value,
            }
        )
    return rows


def _prepare_product_enrichment_status(
    *,
    product: Product,
    request,
    enqueue: bool,
    mode: str,
    processed: bool = False,
    queued: bool = False,
) -> UtrEnrichmentStatus:
    enrichment_mode = _normalize_enrichment_mode(mode)
    detail_id = resolve_utr_detail_id(product=product)
    primary_image = _build_primary_image_url(product=product, request=request)
    enrichment = getattr(product, "utr_enrichment", None)
    if enrichment is None:
        enrichment, _ = UtrProductEnrichment.objects.get_or_create(product=product)

    if detail_id and enrichment.utr_detail_id != detail_id:
        enrichment.utr_detail_id = detail_id
        enrichment.save(update_fields=("utr_detail_id", "updated_at"))

    if not detail_id and not _has_utr_source(product=product):
        if enrichment.status != UtrProductEnrichment.STATUS_UNAVAILABLE:
            enrichment.status = UtrProductEnrichment.STATUS_UNAVAILABLE
            enrichment.error_message = "UTR detail_id is not available for product."
            enrichment.save(update_fields=("status", "error_message", "updated_at"))
        return UtrEnrichmentStatus(
            product_id=str(product.id),
            status=enrichment.status,
            utr_detail_id="",
            primary_image=primary_image,
            characteristics_count=_characteristics_count(enrichment),
            fitments_count=_fitments_count(detail_id=""),
            needs_enrichment=False,
            processed=processed,
            queued=queued,
        )

    needs_enrichment = _should_enqueue(product=product, enrichment=enrichment, mode=enrichment_mode)
    return UtrEnrichmentStatus(
        product_id=str(product.id),
        status=enrichment.status,
        utr_detail_id=detail_id,
        primary_image=primary_image,
        characteristics_count=_characteristics_count(enrichment),
        fitments_count=_fitments_count(detail_id=detail_id) if enrichment_mode == _ENRICHMENT_MODE_DETAIL else 0,
        needs_enrichment=needs_enrichment,
        processed=processed,
        queued=queued,
    )


def _should_enqueue(*, product: Product, enrichment: UtrProductEnrichment, mode: str) -> bool:
    now = timezone.now()
    enrichment_mode = _normalize_enrichment_mode(mode)
    detail_id = resolve_utr_detail_id(product=product) or str(enrichment.utr_detail_id or "").strip()
    has_image = _has_complete_image_set(product=product, enrichment=enrichment)
    if enrichment_mode == _ENRICHMENT_MODE_CATALOG:
        if has_image:
            return False
    else:
        has_characteristics = (not _lazy_characteristics_enabled()) or _characteristics_count(enrichment) > 0
        has_applicability = (not _lazy_applicability_enabled()) or _has_applicability_result(detail_id=detail_id)
        if has_image and has_characteristics and has_applicability:
            return False
    if enrichment.status == UtrProductEnrichment.STATUS_QUEUED:
        if enrichment.updated_at and enrichment.updated_at >= now - _QUEUED_RETRY_AFTER:
            return False
    if enrichment.status == UtrProductEnrichment.STATUS_IN_PROGRESS:
        if enrichment.updated_at and enrichment.updated_at >= now - _IN_PROGRESS_RETRY_AFTER:
            return False
    if enrichment.next_retry_at and enrichment.next_retry_at > now:
        return False
    return True


def _enqueue_utr_product_enrichment(*, product: Product, enrichment: UtrProductEnrichment, mode: str) -> bool:
    enrichment_mode = _normalize_enrichment_mode(mode)
    product_id = str(product.id)
    lock_key = _enrichment_queue_lock_key(product_id=product_id)
    lock_ttl = max(int(getattr(settings, "UTR_LAZY_ENRICH_QUEUE_LOCK_SECONDS", 10 * 60)), 60)
    try:
        if not cache.add(lock_key, enrichment_mode, timeout=lock_ttl):
            return False
    except Exception:
        pass

    try:
        from apps.catalog.tasks import enrich_utr_product_task

        enrichment.status = UtrProductEnrichment.STATUS_QUEUED
        enrichment.error_message = ""
        enrichment.save(update_fields=("status", "error_message", "updated_at"))
        enrich_utr_product_task.apply_async(kwargs={"product_id": product_id, "mode": enrichment_mode})
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("utr_product_enrichment_enqueue_failed product_id=%s mode=%s error=%s", product_id, enrichment_mode, exc)
        _clear_enrichment_queue_lock(product_id=product_id)
        enrichment.status = UtrProductEnrichment.STATUS_FAILED
        enrichment.next_retry_at = timezone.now() + _FAILED_RETRY_AFTER
        enrichment.error_message = str(exc)[:2000]
        enrichment.save(update_fields=("status", "next_retry_at", "error_message", "updated_at"))
        return False


def _enqueue_visible_catalog_enrichment(*, products: list[Product]) -> list[str]:
    queued_ids: list[str] = []
    queued_id_set: set[str] = set()
    lock_ttl = max(int(getattr(settings, "UTR_LAZY_ENRICH_QUEUE_LOCK_SECONDS", 10 * 60)), 60)
    for product in products:
        enrichment = getattr(product, "utr_enrichment", None)
        if enrichment is None:
            enrichment, _ = UtrProductEnrichment.objects.get_or_create(product=product)
            product.utr_enrichment = enrichment
        if not _should_enqueue(product=product, enrichment=enrichment, mode=_ENRICHMENT_MODE_CATALOG):
            continue
        product_id = str(product.id)
        if product_id in queued_id_set:
            continue
        try:
            if not cache.add(_enrichment_queue_lock_key(product_id=product_id), _ENRICHMENT_MODE_CATALOG, timeout=lock_ttl):
                continue
        except Exception:
            pass
        enrichment.status = UtrProductEnrichment.STATUS_QUEUED
        enrichment.error_message = ""
        queued_ids.append(product_id)
        queued_id_set.add(product_id)

    if not queued_ids:
        return []

    try:
        from apps.catalog.tasks import enrich_visible_utr_catalog_products_task

        now = timezone.now()
        UtrProductEnrichment.objects.filter(product_id__in=queued_id_set).update(
            status=UtrProductEnrichment.STATUS_QUEUED,
            error_message="",
            updated_at=now,
        )
        enrich_visible_utr_catalog_products_task.apply_async(kwargs={"product_ids": queued_ids})
        return queued_ids
    except Exception as exc:  # noqa: BLE001
        logger.warning("utr_visible_catalog_enrichment_enqueue_failed count=%s error=%s", len(queued_ids), exc)
        for product_id in queued_ids:
            _clear_enrichment_queue_lock(product_id=product_id)
        retry_at = timezone.now() + _FAILED_RETRY_AFTER
        UtrProductEnrichment.objects.filter(product_id__in=queued_id_set).update(
            status=UtrProductEnrichment.STATUS_FAILED,
            next_retry_at=retry_at,
            error_message=str(exc)[:2000],
            updated_at=timezone.now(),
        )
        return []


def _enqueue_visible_catalog_applicability(*, detail_ids: list[str]) -> int:
    if not _lazy_catalog_applicability_enabled():
        return 0

    top_n = max(int(getattr(settings, "UTR_LAZY_CATALOG_APPLICABILITY_TOP_N", 12)), 0)
    if top_n <= 0:
        return 0

    queued_detail_ids: list[str] = []
    lock_ttl = max(int(getattr(settings, "UTR_LAZY_APPLICABILITY_QUEUE_LOCK_SECONDS", 30 * 60)), 60)
    for detail_id in _normalize_detail_ids(detail_ids):
        if len(queued_detail_ids) >= top_n:
            break
        if _has_applicability_result(detail_id=detail_id):
            continue
        try:
            if not cache.add(_applicability_queue_lock_key(detail_id=detail_id), "catalog", timeout=lock_ttl):
                continue
        except Exception:
            pass
        queued_detail_ids.append(detail_id)

    if not queued_detail_ids:
        return 0

    try:
        from apps.catalog.tasks import enrich_visible_utr_applicability_task

        enrich_visible_utr_applicability_task.apply_async(kwargs={"detail_ids": queued_detail_ids})
        return len(queued_detail_ids)
    except Exception as exc:  # noqa: BLE001
        logger.warning("utr_visible_catalog_applicability_enqueue_failed count=%s error=%s", len(queued_detail_ids), exc)
        clear_utr_catalog_applicability_queue_locks(detail_ids=queued_detail_ids)
        return 0


def _visible_catalog_detail_ids(*, products: list[Product]) -> list[str]:
    detail_ids: list[str] = []
    for product in products:
        detail_id = resolve_utr_detail_id(product=product)
        if not detail_id:
            enrichment = getattr(product, "utr_enrichment", None)
            detail_id = str(getattr(enrichment, "utr_detail_id", "") or "").strip()
        if detail_id:
            detail_ids.append(detail_id)
    return detail_ids


def _enrichment_queue_lock_key(*, product_id: str) -> str:
    return f"utr:product_enrichment:queued:{product_id}"


def _applicability_queue_lock_key(*, detail_id: str) -> str:
    return f"utr:catalog_applicability:queued:{detail_id}"


def clear_utr_product_enrichment_queue_lock(*, product_id: str) -> None:
    _clear_enrichment_queue_lock(product_id=product_id)


def clear_utr_product_enrichment_queue_locks(*, product_ids: list[str]) -> None:
    for product_id in _normalize_product_ids(product_ids):
        _clear_enrichment_queue_lock(product_id=product_id)


def clear_utr_catalog_applicability_queue_locks(*, detail_ids: list[str]) -> None:
    for detail_id in _normalize_detail_ids(detail_ids):
        try:
            cache.delete(_applicability_queue_lock_key(detail_id=detail_id))
        except Exception:
            pass


def _clear_enrichment_queue_lock(*, product_id: str) -> None:
    try:
        cache.delete(_enrichment_queue_lock_key(product_id=product_id))
    except Exception:
        pass


def _resolve_sync_enrichment_limit(*, product_count: int) -> int:
    if product_count <= 0:
        return 0
    if product_count == 1:
        return 1
    return max(int(getattr(settings, "UTR_SYNC_ENRICH_MAX_PRODUCTS", 1)), 1)


def _has_complete_image_set(*, product: Product, enrichment: UtrProductEnrichment) -> bool:
    image_urls = _select_image_urls(enrichment.images_payload if isinstance(enrichment.images_payload, list) else [])
    if not image_urls:
        if enrichment.status == UtrProductEnrichment.STATUS_FETCHED:
            return True
        return ProductImage.objects.filter(product=product).exists()
    existing_digests = _existing_utr_image_digests(product=product)
    return all(_image_url_digest(image_url) in existing_digests for image_url in image_urls)


def _has_applicability_result(*, detail_id: str) -> bool:
    if not _lazy_applicability_enabled():
        return True
    normalized_detail_id = str(detail_id or "").strip()
    if not normalized_detail_id:
        return False
    if UtrDetailCarMap.objects.filter(utr_detail_id=normalized_detail_id).exists():
        return True
    try:
        return bool(cache.get(f"utr:autocatalog:applicability_done:{normalized_detail_id}"))
    except Exception:
        return False


def _lazy_characteristics_enabled() -> bool:
    return bool(getattr(settings, "UTR_LAZY_ENRICH_CHARACTERISTICS_ENABLED", True))


def _lazy_applicability_enabled() -> bool:
    return bool(getattr(settings, "UTR_LAZY_ENRICH_APPLICABILITY_ENABLED", True))


def _lazy_catalog_applicability_enabled() -> bool:
    return bool(getattr(settings, "UTR_LAZY_CATALOG_APPLICABILITY_ENABLED", True))


def _normalize_enrichment_mode(mode: str) -> str:
    normalized = str(mode or "").strip().lower()
    if normalized in _ENRICHMENT_MODES:
        return normalized
    return _ENRICHMENT_MODE_DETAIL


def _has_utr_source(*, product: Product) -> bool:
    return Product.objects.filter(id=product.id).filter(
        Q(utr_detail_id__gt="")
        | Q(supplier_offers__supplier__code="utr")
        | Q(raw_supplier_offers__source__code="utr")
        | Q(raw_supplier_offers__supplier__code="utr")
    ).exists()


def _resolve_utr_access_token(*, client: UtrClient) -> str:
    integration = get_supplier_integration_by_code(source_code="utr")
    if not integration.is_enabled:
        raise SupplierIntegrationError("UTR integration is disabled.")
    token = str(integration.access_token or "").strip()
    if token and (integration.access_token_expires_at is None or integration.access_token_expires_at > timezone.now()):
        return token
    recovered_token, _method = client._recover_access_token_for_utr()
    if not recovered_token:
        raise SupplierClientError("UTR access token is not available.")
    return recovered_token


def _extract_images_payload(detail_payload: dict) -> list[dict]:
    images = detail_payload.get("images")
    if not isinstance(images, list):
        detail_card = detail_payload.get("detailCard") if isinstance(detail_payload.get("detailCard"), dict) else {}
        images = detail_card.get("images")
    if not isinstance(images, list):
        return []
    return [item for item in images if isinstance(item, dict)]


def _select_image_urls(images_payload: list[dict]) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for image in images_payload:
        for key in ("fullImagePath", "thumbnail", "imagePath"):
            url = _normalize_image_url(image.get(key))
            if not url or url in seen:
                continue
            seen.add(url)
            urls.append(url)
            break
    return urls


def _create_missing_product_images(*, product: Product, images_payload: list[dict]) -> int:
    image_urls = _select_image_urls(images_payload)
    if not image_urls:
        return 0

    created_count = 0
    existing_digests = _existing_utr_image_digests(product=product)
    for image_url in image_urls:
        digest = _image_url_digest(image_url)
        if digest in existing_digests:
            continue
        try:
            if _create_product_image(product=product, image_url=image_url):
                existing_digests.add(digest)
                created_count += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "utr_product_image_download_failed product_id=%s url=%s error=%s",
                product.id,
                image_url,
                exc,
            )
    return created_count


def _create_product_image(*, product: Product, image_url: str) -> bool:
    content, content_type = _download_image(image_url)
    extension = _resolve_extension(image_url=image_url, content_type=content_type)
    filename = _build_filename(product=product, image_url=image_url, extension=extension)
    existing_images = ProductImage.objects.filter(product=product)
    last_sort_order = existing_images.order_by("-sort_order").values_list("sort_order", flat=True).first()
    sort_order = int(last_sort_order if last_sort_order is not None else -1) + 1
    image = ProductImage(
        product=product,
        alt_text=product.name[:255],
        is_primary=not existing_images.filter(is_primary=True).exists(),
        sort_order=sort_order,
    )
    image.image.save(filename, ContentFile(content), save=False)
    image.save()
    return True


def _existing_utr_image_digests(*, product: Product) -> set[str]:
    digests: set[str] = set()
    image_names = ProductImage.objects.filter(product=product).values_list("image", flat=True)
    for image_name in image_names:
        text = str(image_name or "")
        for part in text.replace(".", "-").split("-"):
            if len(part) == 16 and all(char in "0123456789abcdef" for char in part.lower()):
                digests.add(part.lower())
    return digests


def _download_image(image_url: str) -> tuple[bytes, str]:
    request = Request(image_url, headers={"User-Agent": "SVOM-UTR-Enrichment/1.0"})
    with urlopen(request, timeout=8) as response:  # noqa: S310
        content_type = str(response.headers.get("Content-Type", "")).split(";")[0].strip().lower()
        data = response.read(_MAX_IMAGE_BYTES + 1)
        if len(data) > _MAX_IMAGE_BYTES:
            raise ValueError("image_too_large")
        if not data:
            raise ValueError("empty_image_payload")
        if content_type and not content_type.startswith("image/"):
            raise ValueError(f"unexpected_content_type:{content_type}")
        return data, content_type


def _normalize_image_url(value: Any) -> str:
    if value is None:
        return ""
    raw = str(value).strip()
    if not raw:
        return ""
    if raw.startswith("//"):
        raw = f"https:{raw}"
    if raw.startswith("/"):
        raw = f"https://order24-file.utr.ua/{raw.lstrip('/')}"
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return raw


def _resolve_extension(*, image_url: str, content_type: str) -> str:
    if content_type:
        normalized_content_type = content_type.lower()
        if normalized_content_type in _MIME_EXTENSION_OVERRIDES:
            return _MIME_EXTENSION_OVERRIDES[normalized_content_type]
        guessed_by_mime = mimetypes.guess_extension(normalized_content_type)
        if guessed_by_mime:
            return guessed_by_mime.lower()

    suffix = PurePosixPath(urlsplit(image_url).path).suffix.lower()
    if suffix in {".webp", ".jpg", ".jpeg", ".png", ".gif", ".svg"}:
        return ".jpg" if suffix == ".jpeg" else suffix
    return ".webp"


def _build_filename(*, product: Product, image_url: str, extension: str) -> str:
    digest = _image_url_digest(image_url)
    product_token = str(product.id).replace("-", "")[:12]
    return f"utr-{product_token}-{digest}{extension}"


def _image_url_digest(image_url: str) -> str:
    return hashlib.sha1(image_url.encode("utf-8")).hexdigest()[:16]  # noqa: S324


def _build_primary_image_url(*, product: Product, request) -> str:
    primary = None
    images = list(product.images.all()) if hasattr(product, "_prefetched_objects_cache") else list(product.images.order_by("sort_order"))
    for image in images:
        if image.is_primary:
            primary = image
            break
    if primary is None and images:
        primary = images[0]
    if primary is None or not primary.image:
        return ""
    if request is None:
        return primary.image.url
    return request.build_absolute_uri(primary.image.url)


def _characteristics_count(enrichment: UtrProductEnrichment | None) -> int:
    if enrichment is None or not isinstance(enrichment.characteristics_payload, list):
        return 0
    return len(enrichment.characteristics_payload)


def _fitments_count(*, detail_id: str) -> int:
    normalized_detail_id = str(detail_id or "").strip()
    if not normalized_detail_id:
        return 0
    return UtrDetailCarMap.objects.filter(utr_detail_id=normalized_detail_id).count()


def _normalize_product_ids(product_ids: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for product_id in product_ids:
        normalized = str(product_id or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _normalize_detail_ids(detail_ids: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for detail_id in detail_ids:
        normalized = str(detail_id or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result
