from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1
import json
from typing import Any
from urllib.parse import urlsplit

from apps.catalog.models import Product, ProductImage
from apps.supplier_imports.models import SupplierRawOffer


_IMAGE_KEYS = (
    "Зображення товару",
    "image_url",
    "images",
    "photo",
    "photo_url",
    "media",
)
_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".bmp", ".avif"}


@dataclass(frozen=True)
class GplImageSyncResult:
    product_id: str
    source_code: str
    has_candidates: bool
    created: int
    reused: int
    stale_marked: int
    skipped_manual_primary: bool


@dataclass(frozen=True)
class GplImageDiagnostics:
    product_id: str
    source_code: str
    latest_offer_id: str
    payload_keys: tuple[str, ...]
    candidates: tuple[str, ...]


class GplProductImageService:
    def sync_product_images(self, *, product: Product, dry_run: bool) -> GplImageSyncResult:
        source_code = self._resolve_source_code(product=product)
        if source_code != "gpl":
            return GplImageSyncResult(
                product_id=str(product.id),
                source_code=source_code,
                has_candidates=False,
                created=0,
                reused=0,
                stale_marked=0,
                skipped_manual_primary=False,
            )

        latest_offer = (
            SupplierRawOffer.objects.filter(matched_product=product, source__code="gpl")
            .order_by("-updated_at", "-id")
            .first()
        )
        payload = latest_offer.raw_payload if latest_offer and isinstance(latest_offer.raw_payload, dict) else {}
        candidates = self._extract_image_urls(payload)

        existing = list(ProductImage.objects.filter(product=product, source=ProductImage.SOURCE_GPL_PRICE).order_by("sort_order", "id"))
        next_sort_order = self._next_sort_order(product=product)
        by_url = {str(item.remote_url or "").strip(): item for item in existing if str(item.remote_url or "").strip()}

        created = 0
        reused = 0
        stale_marked = 0

        for url in candidates:
            source_payload = {
                "source": ProductImage.SOURCE_GPL_PRICE,
                "provider": "gpl_raw_payload",
                "url": url,
                "payload_keys": sorted(list(payload.keys())),
            }
            source_hash = sha1(json.dumps(source_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()  # noqa: S324
            image = by_url.get(url)
            if image is None:
                image = ProductImage(
                    product=product,
                    image=None,
                    remote_url=url,
                    alt_text=str(product.name or "")[:255],
                    is_primary=False,
                    sort_order=next_sort_order,
                    source=ProductImage.SOURCE_GPL_PRICE,
                    source_payload=source_payload,
                    source_hash=source_hash,
                    is_stale=False,
                    stale_reason="",
                )
                next_sort_order += 1
                created += 1
                if not dry_run:
                    image.save()
                    by_url[url] = image
            else:
                reused += 1
                changed = False
                if image.is_stale:
                    image.is_stale = False
                    changed = True
                if image.stale_reason:
                    image.stale_reason = ""
                    changed = True
                if image.source_payload != source_payload:
                    image.source_payload = source_payload
                    changed = True
                if str(image.source_hash or "") != source_hash:
                    image.source_hash = source_hash
                    changed = True
                if changed and not dry_run:
                    image.save(update_fields=("is_stale", "stale_reason", "source_payload", "source_hash", "updated_at"))

        candidate_set = set(candidates)
        for image in existing:
            url = str(image.remote_url or "").strip()
            if not url:
                continue
            if url in candidate_set:
                continue
            stale_marked += 1
            if not dry_run and (not image.is_stale or image.stale_reason != "missing_from_latest_import"):
                image.is_stale = True
                image.stale_reason = "missing_from_latest_import"
                image.save(update_fields=("is_stale", "stale_reason", "updated_at"))

        skipped_manual_primary = False
        if candidates:
            if self._has_protected_primary(product=product):
                skipped_manual_primary = True
            else:
                self._assign_primary(
                    product=product,
                    preferred_source=ProductImage.SOURCE_GPL_PRICE,
                    dry_run=dry_run,
                )

        return GplImageSyncResult(
            product_id=str(product.id),
            source_code=source_code,
            has_candidates=bool(candidates),
            created=created,
            reused=reused,
            stale_marked=stale_marked,
            skipped_manual_primary=skipped_manual_primary,
        )

    def build_diagnostics(self, *, product: Product) -> GplImageDiagnostics:
        source_code = self._resolve_source_code(product=product)
        latest_offer = (
            SupplierRawOffer.objects.filter(matched_product=product, source__code="gpl")
            .order_by("-updated_at", "-id")
            .first()
        )
        payload = latest_offer.raw_payload if latest_offer and isinstance(latest_offer.raw_payload, dict) else {}
        candidates = self._extract_image_urls(payload)
        return GplImageDiagnostics(
            product_id=str(product.id),
            source_code=source_code,
            latest_offer_id=str(getattr(latest_offer, "id", "") or ""),
            payload_keys=tuple(sorted(payload.keys())),
            candidates=tuple(candidates),
        )

    def _resolve_source_code(self, *, product: Product) -> str:
        has_gpl = SupplierRawOffer.objects.filter(matched_product=product, source__code="gpl").exists()
        return "gpl" if has_gpl else ""

    def _extract_image_urls(self, payload: dict[str, Any]) -> list[str]:
        urls: list[str] = []

        for key in _IMAGE_KEYS:
            urls.extend(self._collect_urls(payload.get(key)))

        for key, value in payload.items():
            normalized_key = str(key).strip().lower()
            if any(token in normalized_key for token in ("image", "photo", "picture", "media", "зображ")):
                urls.extend(self._collect_urls(value))

        seen: set[str] = set()
        out: list[str] = []
        for url in urls:
            if url in seen:
                continue
            seen.add(url)
            out.append(url)
        return out

    def _collect_urls(self, value: Any) -> list[str]:
        if value is None:
            return []

        if isinstance(value, str):
            normalized = self._normalize_url(value)
            return [normalized] if normalized else []

        if isinstance(value, dict):
            out: list[str] = []
            for key in ("url", "href", "src", "image", "photo", "file"):
                out.extend(self._collect_urls(value.get(key)))
            for item in value.values():
                if isinstance(item, (list, tuple)):
                    out.extend(self._collect_urls(item))
            return out

        if isinstance(value, (list, tuple, set)):
            out: list[str] = []
            for item in value:
                out.extend(self._collect_urls(item))
            return out

        return []

    def _normalize_url(self, value: str) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        if raw.startswith("//"):
            raw = f"https:{raw}"

        parsed = urlsplit(raw)
        if parsed.scheme not in {"http", "https"}:
            return ""
        if not parsed.netloc:
            return ""

        suffix = parsed.path.rsplit("/", 1)[-1].lower()
        if "." in suffix:
            ext = "." + suffix.split(".")[-1]
            if ext and ext not in _ALLOWED_EXTENSIONS:
                return ""
        return raw

    def _has_protected_primary(self, *, product: Product) -> bool:
        return ProductImage.objects.filter(
            product=product,
            is_primary=True,
            source=ProductImage.SOURCE_MANUAL,
        ).exists()

    def _assign_primary(self, *, product: Product, preferred_source: str, dry_run: bool) -> None:
        images = list(ProductImage.objects.filter(product=product).order_by("sort_order", "id"))
        if not images:
            return

        target = None
        for image in images:
            if image.source == preferred_source and not image.is_stale:
                target = image
                break
        if target is None:
            return

        for image in images:
            desired = image.id == target.id
            if image.is_primary == desired:
                continue
            if dry_run:
                continue
            image.is_primary = desired
            image.save(update_fields=("is_primary", "updated_at"))

    def _next_sort_order(self, *, product: Product) -> int:
        value = ProductImage.objects.filter(product=product).order_by("-sort_order").values_list("sort_order", flat=True).first()
        if value is None:
            return 0
        return int(value) + 1
