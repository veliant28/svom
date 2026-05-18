from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1
import json
from typing import Any
from urllib.parse import urlsplit

from apps.autodb.selectors import get_autodb_image_base_url
from apps.autodb.services.column_helpers import find_column_name, find_value
from apps.autodb.services.raw_clone_storage import AutoDbRawCloneStorage
from apps.catalog.models import Product, ProductImage
from apps.supplier_imports.models import SupplierRawOffer


@dataclass(frozen=True)
class AutoDbImageCandidate:
    remote_url: str
    reference: str
    reference_kind: str
    raw_row: dict[str, Any]
    pending_url_resolution: bool


@dataclass(frozen=True)
class AutoDbImageSyncResult:
    product_id: str
    has_candidates: bool
    created: int
    reused: int
    stale_marked: int
    skipped_manual_primary: bool
    skipped_no_autodb_link: bool


@dataclass(frozen=True)
class AutoDbImageDiagnostics:
    product_id: str
    bridge_supplier_id: int | None
    bridge_article_number: str
    bridge_article_key: str
    article_images_rows: tuple[dict[str, Any], ...]
    candidates: tuple[dict[str, Any], ...]


class AutoDbProductImageEnrichmentService:
    def __init__(self, *, storage: AutoDbRawCloneStorage | None = None):
        self.storage = storage or AutoDbRawCloneStorage()

    def sync_product_images(self, *, product: Product, dry_run: bool, prefer_gpl: bool = True) -> AutoDbImageSyncResult:
        supplier_id = self._safe_int(getattr(product, "autodb_supplier_id", None))
        article_number = str(getattr(product, "autodb_article_number", "") or "").strip()
        if supplier_id is None or not article_number:
            return AutoDbImageSyncResult(
                product_id=str(product.id),
                has_candidates=False,
                created=0,
                reused=0,
                stale_marked=0,
                skipped_manual_primary=False,
                skipped_no_autodb_link=True,
            )

        rows = self._find_article_images_rows(supplier_id=supplier_id, article_number=article_number)
        candidates = self._build_candidates(rows)
        existing = list(ProductImage.objects.filter(product=product, source=ProductImage.SOURCE_AUTODB_PRO).order_by("sort_order", "id"))
        next_sort_order = self._next_sort_order(product=product)

        by_remote = {str(item.remote_url or "").strip(): item for item in existing if str(item.remote_url or "").strip()}
        by_hash = {str(item.source_hash or "").strip(): item for item in existing if str(item.source_hash or "").strip()}

        created = 0
        reused = 0
        stale_marked = 0

        for candidate in candidates:
            source_payload = {
                "source": ProductImage.SOURCE_AUTODB_PRO,
                "pending_url_resolution": candidate.pending_url_resolution,
                "reference_kind": candidate.reference_kind,
                "reference": candidate.reference,
                "remote_url": candidate.remote_url,
                "raw": self._trim_payload(candidate.raw_row),
            }
            source_hash = sha1(json.dumps(source_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()  # noqa: S324

            image = None
            if candidate.remote_url:
                image = by_remote.get(candidate.remote_url)
            if image is None:
                image = by_hash.get(source_hash)

            if image is None:
                image = ProductImage(
                    product=product,
                    image=None,
                    remote_url=candidate.remote_url,
                    alt_text=str(product.name or "")[:255],
                    is_primary=False,
                    sort_order=next_sort_order,
                    source=ProductImage.SOURCE_AUTODB_PRO,
                    source_payload=source_payload,
                    source_hash=source_hash,
                    is_stale=False,
                    stale_reason="",
                )
                next_sort_order += 1
                created += 1
                if not dry_run:
                    image.save()
                    if candidate.remote_url:
                        by_remote[candidate.remote_url] = image
                    by_hash[source_hash] = image
            else:
                reused += 1
                changed = False
                if image.is_stale:
                    image.is_stale = False
                    changed = True
                if image.stale_reason:
                    image.stale_reason = ""
                    changed = True
                if image.remote_url != candidate.remote_url:
                    image.remote_url = candidate.remote_url
                    changed = True
                if image.source_payload != source_payload:
                    image.source_payload = source_payload
                    changed = True
                if str(image.source_hash or "") != source_hash:
                    image.source_hash = source_hash
                    changed = True
                if changed and not dry_run:
                    image.save(update_fields=("is_stale", "stale_reason", "remote_url", "source_payload", "source_hash", "updated_at"))

        active_remote_urls = {item.remote_url for item in candidates if item.remote_url}
        active_hashes: set[str] = set()
        for item in candidates:
            source_payload = {
                "source": ProductImage.SOURCE_AUTODB_PRO,
                "pending_url_resolution": item.pending_url_resolution,
                "reference_kind": item.reference_kind,
                "reference": item.reference,
                "remote_url": item.remote_url,
                "raw": self._trim_payload(item.raw_row),
            }
            source_hash = sha1(json.dumps(source_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()  # noqa: S324
            active_hashes.add(source_hash)

        for image in existing:
            if str(image.remote_url or "").strip() and str(image.remote_url or "").strip() in active_remote_urls:
                continue
            if str(image.source_hash or "").strip() and str(image.source_hash or "").strip() in active_hashes:
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
            elif prefer_gpl and self._is_gpl_product(product=product) and self._has_active_gpl_image(product=product):
                skipped_manual_primary = True
            else:
                self._assign_primary(product=product, preferred_source=ProductImage.SOURCE_AUTODB_PRO, dry_run=dry_run)

        return AutoDbImageSyncResult(
            product_id=str(product.id),
            has_candidates=bool(candidates),
            created=created,
            reused=reused,
            stale_marked=stale_marked,
            skipped_manual_primary=skipped_manual_primary,
            skipped_no_autodb_link=False,
        )

    def build_diagnostics(self, *, product: Product) -> AutoDbImageDiagnostics:
        supplier_id = self._safe_int(getattr(product, "autodb_supplier_id", None))
        article_number = str(getattr(product, "autodb_article_number", "") or "").strip()
        rows: list[dict[str, Any]] = []
        candidates: list[AutoDbImageCandidate] = []
        if supplier_id is not None and article_number:
            rows = self._find_article_images_rows(supplier_id=supplier_id, article_number=article_number)
            candidates = self._build_candidates(rows)
        return AutoDbImageDiagnostics(
            product_id=str(product.id),
            bridge_supplier_id=supplier_id,
            bridge_article_number=article_number,
            bridge_article_key=str(getattr(product, "autodb_article_key", "") or ""),
            article_images_rows=tuple(dict(row) for row in rows),
            candidates=tuple(
                {
                    "remote_url": item.remote_url,
                    "reference": item.reference,
                    "reference_kind": item.reference_kind,
                    "pending_url_resolution": item.pending_url_resolution,
                }
                for item in candidates
            ),
        )

    def _build_candidates(self, rows: list[dict[str, Any]]) -> list[AutoDbImageCandidate]:
        out: list[AutoDbImageCandidate] = []
        seen: set[str] = set()
        for row in rows:
            candidate = self._candidate_from_row(row)
            if candidate is None:
                continue
            key = candidate.remote_url or f"pending:{candidate.reference_kind}:{candidate.reference}"
            if key in seen:
                continue
            seen.add(key)
            out.append(candidate)
        return out

    def _candidate_from_row(self, row: dict[str, Any]) -> AutoDbImageCandidate | None:
        direct_keys = [
            "TecdocHyperlinkName",
            "tecdocHyperlinkName",
            "tecdochyperlinkname",
            "ImageUrl",
            "imageUrl",
            "imageurl",
            "url",
            "fullImagePath",
        ]
        reference_keys = [
            "FileName",
            "filename",
            "PictureName",
            "picturename",
            "DocumentName",
            "documentname",
        ]

        for key in direct_keys:
            value = str(find_value(row, [key]) or "").strip()
            normalized = self._normalize_image_url(value)
            if normalized:
                return AutoDbImageCandidate(
                    remote_url=normalized,
                    reference=value,
                    reference_kind=key,
                    raw_row=dict(row),
                    pending_url_resolution=False,
                )

        for key in reference_keys:
            value = str(find_value(row, [key]) or "").strip()
            if not value:
                continue
            normalized = self._normalize_image_url(value)
            pending = not bool(normalized)
            return AutoDbImageCandidate(
                remote_url=normalized,
                reference=value,
                reference_kind=key,
                raw_row=dict(row),
                pending_url_resolution=pending,
            )
        return None

    def _normalize_image_url(self, raw: str) -> str:
        value = str(raw or "").strip()
        if not value:
            return ""
        if value.startswith("//"):
            value = f"https:{value}"

        parsed = urlsplit(value)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            return value

        base_url = get_autodb_image_base_url()
        if not base_url:
            return ""

        path = value
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{base_url}{path}"

    def _find_article_images_rows(self, *, supplier_id: int, article_number: str) -> list[dict[str, Any]]:
        if supplier_id <= 0 or not article_number:
            return []
        self.storage.ensure_table("article_images")
        columns = list(self.storage.get_local_columns("article_images"))
        if not columns:
            return []

        supplier_column = find_column_name(columns, ["supplierId", "supplierid", "SupplierId", "supplier_id"])
        article_column = find_column_name(
            columns,
            ["DataSupplierArticleNumber", "datasupplierarticlenumber", "article", "articlenumber", "number"],
        )
        if not supplier_column or not article_column:
            return []

        order_column = find_column_name(columns, ["id", "ID", "sortOrder", "SortOrder"]) or supplier_column
        article_variants: list[str] = []
        for candidate in (article_number, "".join(str(article_number).split())):
            value = str(candidate or "").strip()
            if value and value not in article_variants:
                article_variants.append(value)

        for variant in article_variants:
            rows = self.storage.fetch_local_rows(
                table="article_images",
                filters={supplier_column: supplier_id, article_column: variant},
                limit=1000,
                order_by=order_column,
                columns=columns,
            )
            if rows:
                return rows
        return []

    def _trim_payload(self, row: dict[str, Any]) -> dict[str, Any]:
        keys = [
            "supplierId",
            "supplierid",
            "DataSupplierArticleNumber",
            "datasupplierarticlenumber",
            "AdditionalDescription",
            "Description",
            "DocumentName",
            "DocumentType",
            "NormedDescriptionID",
            "PictureName",
            "ShowImmediately",
            "TecdocHyperlinkName",
            "FileName",
            "id",
        ]
        out: dict[str, Any] = {}
        for key in keys:
            value = find_value(row, [key])
            if value is None or str(value).strip() == "":
                continue
            out[key] = str(value)[:255]
        return out

    def _has_protected_primary(self, *, product: Product) -> bool:
        return ProductImage.objects.filter(
            product=product,
            is_primary=True,
            source=ProductImage.SOURCE_MANUAL,
        ).exists()

    def _has_active_gpl_image(self, *, product: Product) -> bool:
        return ProductImage.objects.filter(
            product=product,
            source=ProductImage.SOURCE_GPL_PRICE,
            is_stale=False,
        ).exists()

    def _is_gpl_product(self, *, product: Product) -> bool:
        return SupplierRawOffer.objects.filter(matched_product=product, source__code="gpl").exists()

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

    def _safe_int(self, value: Any) -> int | None:
        try:
            if value is None or str(value).strip() == "":
                return None
            return int(value)
        except (TypeError, ValueError):
            return None
