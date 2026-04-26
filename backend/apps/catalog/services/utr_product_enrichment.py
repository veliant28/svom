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
from django.core.files.base import ContentFile
from django.db.models import Q
from django.utils import timezone

from apps.autocatalog.models import UtrArticleDetailMap
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
_QUEUE_STALE_AFTER = timedelta(minutes=10)
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
    queued: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "product_id": self.product_id,
            "status": self.status,
            "utr_detail_id": self.utr_detail_id,
            "primary_image": self.primary_image,
            "characteristics_count": self.characteristics_count,
            "queued": self.queued,
        }


def request_visible_utr_enrichment(*, product_ids: list[str], request=None, enqueue: bool = True) -> list[dict[str, object]]:
    normalized_ids = _normalize_product_ids(product_ids)[:_MAX_VISIBLE_ENRICHMENT_PRODUCTS]
    if not normalized_ids:
        return []

    products = list(
        Product.objects.filter(id__in=normalized_ids)
        .select_related("brand", "utr_enrichment")
        .prefetch_related("images")
    )
    product_by_id = {str(product.id): product for product in products}
    rows: list[dict[str, object]] = []

    for product_id in normalized_ids:
        product = product_by_id.get(product_id)
        if product is None:
            continue
        rows.append(_prepare_product_enrichment_status(product=product, request=request, enqueue=enqueue).as_dict())

    return rows


def enrich_utr_product(*, product_id: str) -> dict[str, object]:
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
        created_image = False
        if not ProductImage.objects.filter(product=product).exists():
            image_url = _select_image_url(images_payload)
            if image_url:
                try:
                    created_image = _create_product_image(product=product, image_url=image_url)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "utr_product_image_download_failed product_id=%s detail_id=%s url=%s error=%s",
                        product.id,
                        detail_id,
                        image_url,
                        exc,
                    )

        characteristics_payload: list[dict] = []
        if bool(getattr(settings, "UTR_LAZY_ENRICH_CHARACTERISTICS_ENABLED", True)):
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
        if bool(getattr(settings, "UTR_LAZY_ENRICH_APPLICABILITY_ENABLED", True)):
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
            "created_image": created_image,
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


def _prepare_product_enrichment_status(*, product: Product, request, enqueue: bool) -> UtrEnrichmentStatus:
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
            queued=False,
        )

    queued = False
    if enqueue and _should_enqueue(product=product, enrichment=enrichment):
        enrichment.status = UtrProductEnrichment.STATUS_QUEUED
        enrichment.next_retry_at = None
        enrichment.error_message = ""
        enrichment.save(update_fields=("status", "next_retry_at", "error_message", "updated_at"))
        _enqueue_enrichment_task(product_id=str(product.id))
        queued = True

    return UtrEnrichmentStatus(
        product_id=str(product.id),
        status=enrichment.status,
        utr_detail_id=detail_id,
        primary_image=primary_image,
        characteristics_count=_characteristics_count(enrichment),
        queued=queued,
    )


def _should_enqueue(*, product: Product, enrichment: UtrProductEnrichment) -> bool:
    now = timezone.now()
    has_image = ProductImage.objects.filter(product=product).exists()
    has_characteristics = _characteristics_count(enrichment) > 0
    if has_image and has_characteristics:
        return False
    if enrichment.status in {UtrProductEnrichment.STATUS_QUEUED, UtrProductEnrichment.STATUS_IN_PROGRESS}:
        if enrichment.updated_at and enrichment.updated_at >= now - _QUEUE_STALE_AFTER:
            return False
    if enrichment.next_retry_at and enrichment.next_retry_at > now:
        return False
    return True


def _enqueue_enrichment_task(*, product_id: str) -> None:
    from apps.catalog.tasks.utr_product_enrichment import enrich_utr_product_task

    enrich_utr_product_task.delay(product_id=product_id)


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


def _select_image_url(images_payload: list[dict]) -> str:
    for image in images_payload:
        for key in ("fullImagePath", "thumbnail", "imagePath"):
            url = _normalize_image_url(image.get(key))
            if url:
                return url
    return ""


def _create_product_image(*, product: Product, image_url: str) -> bool:
    content, content_type = _download_image(image_url)
    extension = _resolve_extension(image_url=image_url, content_type=content_type)
    filename = _build_filename(product=product, image_url=image_url, extension=extension)
    image = ProductImage(product=product, alt_text=product.name[:255], is_primary=True, sort_order=0)
    image.image.save(filename, ContentFile(content), save=False)
    image.save()
    return True


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
    digest = hashlib.sha1(image_url.encode("utf-8")).hexdigest()[:16]  # noqa: S324
    product_token = str(product.id).replace("-", "")[:12]
    return f"utr-{product_token}-{digest}{extension}"


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
