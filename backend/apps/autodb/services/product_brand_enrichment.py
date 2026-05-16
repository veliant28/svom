from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1
from typing import Any

from django.db.models import QuerySet

from apps.autodb.services.column_helpers import find_column_name
from apps.autodb.services.raw_clone_storage import AutoDbRawCloneStorage
from apps.catalog.models import Product
from apps.catalog.services import sanitize_brand_name
from apps.supplier_imports.models import SupplierRawOffer


@dataclass(frozen=True)
class ProductBrandEnrichmentResult:
    product_id: str
    status: str
    old_brand_name: str
    new_brand_name: str
    brand_source: str
    autodb_supplier_id: int | None
    autodb_supplier_name: str
    source_hash: str
    raw_supplier_brand_examples: tuple[str, ...] = ()
    reason: str = ""


@dataclass(frozen=True)
class ProductBrandDiagnostics:
    product_id: str
    product_name: str
    current_brand_id: str
    current_brand_name: str
    autodb_supplier_id: int | None
    autodb_article_key: str
    autodb_supplier_name: str
    raw_supplier_brand_examples: tuple[str, ...]
    proposed_brand_name: str
    proposed_brand_source: str
    status: str
    reason: str
    would_update: bool


class AutoDbProductBrandEnrichmentService:
    def __init__(self, *, storage: AutoDbRawCloneStorage | None = None):
        self.storage = storage or AutoDbRawCloneStorage()
        self._supplier_name_cache: dict[int, str] = {}
        self._supplier_rows_loaded = False
        self._supplier_columns: list[str] = []
        self._supplier_id_column: str | None = None
        self._supplier_name_column: str | None = None
        self._supplier_normalized_name_column: str | None = None
        self._supplier_matchcode_column: str | None = None
        self._details_loaded = False
        self._details_name_by_supplier_id: dict[int, str] = {}

    def build_queryset(self, *, only_linked: bool = False, product_id: str = "", include_all: bool = False) -> QuerySet[Product]:
        qs = Product.objects.select_related("category").order_by("id")
        if only_linked:
            qs = qs.filter(autodb_supplier_id__isnull=False)
        elif not include_all:
            qs = qs.filter(autodb_supplier_id__isnull=False)
        if product_id:
            qs = qs.filter(pk=product_id)
        return qs

    def prime_supplier_cache(self, supplier_ids: set[int]) -> None:
        valid_ids = sorted({int(item) for item in supplier_ids if int(item) > 0})
        if not valid_ids:
            return
        self._ensure_supplier_columns()
        if not self._supplier_id_column:
            return

        missing = [item for item in valid_ids if item not in self._supplier_name_cache]
        if not missing:
            return

        rows = self.storage.fetch_local_rows_in(
            table="suppliers",
            column=self._supplier_id_column,
            values=missing,
            limit=max(len(missing) * 2, 500),
            columns=self._supplier_columns,
        )
        for row in rows:
            supplier_id = self._safe_int(row.get(self._supplier_id_column))
            if supplier_id is None:
                continue
            resolved = self._pick_supplier_name(row=row, supplier_id=supplier_id)
            if resolved:
                self._supplier_name_cache[supplier_id] = resolved
        self._load_supplier_details_for(missing_supplier_ids=set(missing))
        for supplier_id in missing:
            if supplier_id in self._supplier_name_cache:
                continue
            fallback = self._details_name_by_supplier_id.get(supplier_id, "")
            if fallback:
                self._supplier_name_cache[supplier_id] = fallback

    def resolve_supplier_name(self, supplier_id: int | None) -> str:
        resolved_id = self._safe_int(supplier_id)
        if resolved_id is None or resolved_id <= 0:
            return ""
        if resolved_id in self._supplier_name_cache:
            return self._supplier_name_cache[resolved_id]
        self.prime_supplier_cache({resolved_id})
        return self._supplier_name_cache.get(resolved_id, "")

    def diagnose_product(self, *, product: Product) -> ProductBrandDiagnostics:
        supplier_id = self._safe_int(getattr(product, "autodb_supplier_id", None))
        autodb_supplier_name = self.resolve_supplier_name(supplier_id)
        current_brand_name = self._current_brand_name(product=product)
        normalized_brand_name = sanitize_brand_name(str(getattr(product, "normalized_brand", "") or ""))
        raw_examples = self._collect_raw_supplier_brand_examples(product=product)

        if autodb_supplier_name:
            proposed_brand_name = autodb_supplier_name
            proposed_brand_source = Product.BRAND_SOURCE_AUTODB_PRO
        elif raw_examples:
            proposed_brand_name = raw_examples[0]
            proposed_brand_source = Product.BRAND_SOURCE_SUPPLIER_FALLBACK
        elif normalized_brand_name:
            proposed_brand_name = normalized_brand_name
            proposed_brand_source = Product.BRAND_SOURCE_SUPPLIER_FALLBACK
        elif current_brand_name:
            proposed_brand_name = current_brand_name
            proposed_brand_source = Product.BRAND_SOURCE_SUPPLIER_FALLBACK
        else:
            proposed_brand_name = ""
            proposed_brand_source = Product.BRAND_SOURCE_UNKNOWN

        status = "ok"
        reason = ""
        if bool(getattr(product, "brand_manually_locked", False)):
            status = "skipped_manual_locked"
            reason = "brand_manually_locked"
        elif supplier_id is not None and (not autodb_supplier_name):
            status = "skipped_supplier_missing_local"
            reason = "supplier_missing_or_name_empty_in_local_autodb"
        elif not proposed_brand_name:
            status = "skipped_no_source_brand"
            reason = "canonical_and_fallback_brand_missing"

        current_display_name = str(getattr(product, "display_brand_name", "") or "").strip() or current_brand_name
        current_source = str(getattr(product, "brand_source", "") or "").strip()
        proposed_hash = self._build_source_hash(
            supplier_id=supplier_id,
            source=proposed_brand_source,
            brand_name=proposed_brand_name,
        )
        would_update = (
            bool(proposed_brand_name)
            and status == "ok"
            and (
                current_display_name != proposed_brand_name
                or current_source != proposed_brand_source
                or str(getattr(product, "autodb_supplier_name", "") or "").strip() != autodb_supplier_name
                or str(getattr(product, "brand_source_hash", "") or "").strip() != proposed_hash
            )
        )

        return ProductBrandDiagnostics(
            product_id=str(product.id),
            product_name=str(product.name or ""),
            current_brand_id=str(getattr(product, "brand_id", "") or ""),
            current_brand_name=current_brand_name,
            autodb_supplier_id=supplier_id,
            autodb_article_key=str(getattr(product, "autodb_article_key", "") or ""),
            autodb_supplier_name=autodb_supplier_name,
            raw_supplier_brand_examples=raw_examples,
            proposed_brand_name=proposed_brand_name,
            proposed_brand_source=proposed_brand_source,
            status=status,
            reason=reason,
            would_update=would_update,
        )

    def enrich_product(self, *, product: Product, dry_run: bool) -> ProductBrandEnrichmentResult:
        diagnostics = self.diagnose_product(product=product)
        old_brand_name = str(getattr(product, "display_brand_name", "") or "").strip() or diagnostics.current_brand_name
        source_hash = self._build_source_hash(
            supplier_id=diagnostics.autodb_supplier_id,
            source=diagnostics.proposed_brand_source,
            brand_name=diagnostics.proposed_brand_name,
        )
        status = diagnostics.status
        reason = diagnostics.reason
        if status == "ok":
            status = "updated" if diagnostics.would_update else "skipped_hash_unchanged"
            reason = "resolved_autodb_supplier_name" if diagnostics.would_update else "brand_hash_unchanged"

        if status == "updated" and not dry_run:
            product.display_brand_name = diagnostics.proposed_brand_name
            product.autodb_supplier_name = diagnostics.autodb_supplier_name
            product.brand_source = diagnostics.proposed_brand_source
            product.brand_source_hash = source_hash
            product.save(
                update_fields=(
                    "display_brand_name",
                    "autodb_supplier_name",
                    "brand_source",
                    "brand_source_hash",
                    "updated_at",
                )
            )

        return ProductBrandEnrichmentResult(
            product_id=str(product.id),
            status=status,
            old_brand_name=old_brand_name,
            new_brand_name=diagnostics.proposed_brand_name,
            brand_source=diagnostics.proposed_brand_source,
            autodb_supplier_id=diagnostics.autodb_supplier_id,
            autodb_supplier_name=diagnostics.autodb_supplier_name,
            source_hash=source_hash,
            raw_supplier_brand_examples=diagnostics.raw_supplier_brand_examples,
            reason=reason,
        )

    def _collect_raw_supplier_brand_examples(self, *, product: Product) -> tuple[str, ...]:
        names = (
            SupplierRawOffer.objects.filter(matched_product=product)
            .exclude(brand_name="")
            .order_by("-updated_at", "-id")
            .values_list("brand_name", flat=True)[:5]
        )
        seen: set[str] = set()
        out: list[str] = []
        for value in names:
            clean = sanitize_brand_name(str(value or ""))
            if not clean or clean in seen:
                continue
            seen.add(clean)
            out.append(clean)
        return tuple(out)

    def _ensure_supplier_columns(self) -> None:
        if self._supplier_rows_loaded:
            return
        self.storage.ensure_table("suppliers")
        columns = sorted(self.storage.get_local_columns("suppliers"))
        self._supplier_columns = columns
        self._supplier_id_column = find_column_name(columns, ["id", "supplierId", "supplierid"])
        self._supplier_name_column = find_column_name(columns, ["description", "Description", "name", "Name"])
        self._supplier_normalized_name_column = find_column_name(
            columns,
            ["normalizeddescription", "NormalizedDescription", "normalized_name", "normalizedname"],
        )
        self._supplier_matchcode_column = find_column_name(columns, ["matchcode", "Matchcode", "MatchCode"])
        self._supplier_rows_loaded = True

    def _pick_supplier_name(self, *, row: dict[str, Any], supplier_id: int) -> str:
        for column in [self._supplier_name_column, self._supplier_normalized_name_column, self._supplier_matchcode_column]:
            if not column:
                continue
            value = sanitize_brand_name(str(row.get(column, "") or ""))
            if value:
                return value
        details_name = self._details_name_by_supplier_id.get(supplier_id, "")
        if details_name:
            return details_name
        return ""

    def _load_supplier_details_for(self, *, missing_supplier_ids: set[int]) -> None:
        if not missing_supplier_ids:
            return
        if self._details_loaded and all(item in self._details_name_by_supplier_id for item in missing_supplier_ids):
            return
        self.storage.ensure_table("supplier_details")
        columns = sorted(self.storage.get_local_columns("supplier_details"))
        if not columns:
            self._details_loaded = True
            return

        supplier_column = find_column_name(columns, ["supplierId", "supplierid", "SupplierId", "id"])
        name_column = find_column_name(
            columns,
            ["description", "Description", "name", "Name", "displayname", "DisplayName", "fullname", "FullName"],
        )
        if not supplier_column or not name_column:
            self._details_loaded = True
            return

        rows = self.storage.fetch_local_rows_in(
            table="supplier_details",
            column=supplier_column,
            values=sorted(missing_supplier_ids),
            limit=max(len(missing_supplier_ids) * 3, 500),
            columns=[supplier_column, name_column],
        )
        for row in rows:
            supplier_id = self._safe_int(row.get(supplier_column))
            if supplier_id is None:
                continue
            value = sanitize_brand_name(str(row.get(name_column, "") or ""))
            if value and supplier_id not in self._details_name_by_supplier_id:
                self._details_name_by_supplier_id[supplier_id] = value
        self._details_loaded = True

    def _build_source_hash(self, *, supplier_id: int | None, source: str, brand_name: str) -> str:
        payload = f"{int(supplier_id or 0)}:{source}:{brand_name}"
        return sha1(payload.encode("utf-8")).hexdigest()  # noqa: S324

    def _current_brand_name(self, *, product: Product) -> str:
        return sanitize_brand_name(str(getattr(getattr(product, "brand", None), "name", "") or ""))

    def _safe_int(self, value: Any) -> int | None:
        try:
            if value is None or str(value).strip() == "":
                return None
            return int(value)
        except (TypeError, ValueError):
            return None
