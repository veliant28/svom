from __future__ import annotations

import hashlib
import logging
import mimetypes
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from django.core.files.base import ContentFile

from apps.catalog.models import Product, ProductImage
from apps.supplier_imports.models import SupplierRawOffer

logger = logging.getLogger(__name__)

_IMAGE_URL_KEYS = (
    "Зображення товару",
    "image_url",
    "image",
    "photo_url",
    "photo",
    "img",
    "picture",
)

_IMAGE_KEY_TOKENS = ("image", "photo", "img", "picture", "зображ")
_MAX_IMAGE_BYTES = 10 * 1024 * 1024

_MIME_EXTENSION_OVERRIDES = {
    "image/webp": ".webp",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
}


def ensure_gpl_product_image(*, raw_offer: SupplierRawOffer, product: Product) -> bool:
    if (raw_offer.supplier.code or "").lower() != "gpl":
        return False

    if product.images.exists():
        return False

    image_url = extract_image_url(raw_offer=raw_offer)
    if not image_url:
        return False

    try:
        content, content_type = _download_image(image_url)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "gpl_image_download_failed raw_offer_id=%s product_id=%s url=%s error=%s",
            raw_offer.id,
            product.id,
            image_url,
            exc,
        )
        return False

    extension = _resolve_extension(image_url=image_url, content_type=content_type)
    filename = _build_filename(product=product, image_url=image_url, extension=extension)
    image = ProductImage(
        product=product,
        alt_text=product.name[:255],
        is_primary=True,
        sort_order=0,
    )
    image.image.save(filename, ContentFile(content), save=False)
    image.save()
    return True


def extract_image_url(*, raw_offer: SupplierRawOffer) -> str:
    payload = raw_offer.raw_payload if isinstance(raw_offer.raw_payload, dict) else {}
    if not payload:
        return ""

    for key in _IMAGE_URL_KEYS:
        value = payload.get(key)
        normalized = _normalize_image_url(value)
        if normalized:
            return normalized

    for key, value in payload.items():
        normalized_key = str(key).strip().lower()
        if not any(token in normalized_key for token in _IMAGE_KEY_TOKENS):
            continue
        normalized = _normalize_image_url(value)
        if normalized:
            return normalized

    return ""


def _download_image(image_url: str) -> tuple[bytes, str]:
    request = Request(image_url, headers={"User-Agent": "SVOM-Importer/1.0"})
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

    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"}:
        return ""
    if not parsed.netloc:
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
    return f"gpl-{product_token}-{digest}{extension}"
