from __future__ import annotations

from dataclasses import dataclass, field

from django.db.models import Q

from apps.autodb.models import AutoDbSupplierBrandAlias
from apps.autodb.services.raw_clone_storage import AutoDbRawCloneStorage
from apps.autodb.services.matching.constants import (
    BUILTIN_SAFE_ALIASES,
    INVALID_BRAND_VALUE_KEYS,
    NON_TECDOC_BRAND_KEYS,
    UNSAFE_BRAND_KEYS,
)
from apps.supplier_imports.models import SupplierBrandAlias
from apps.supplier_imports.parsers.utils import normalize_brand


@dataclass(frozen=True)
class _SupplierCandidate:
    supplier_id: int
    supplier_name: str
    supplier_matchcode: str
    normalized_name: str
    normalized_matchcode: str
    nbrofarticles: int


@dataclass(frozen=True)
class AutoDbBrandResolution:
    raw_brand: str
    normalized_brand: str
    supplier_code: str
    status: str
    decision: str
    supplier_id: int | None = None
    supplier_name: str = ""
    reason: str = ""
    resolver_source: str = ""
    candidates: tuple[dict[str, str | int], ...] = field(default_factory=tuple)

    @property
    def is_mapped(self) -> bool:
        return self.decision == "mapped" and self.supplier_id is not None


class AutoDbBrandResolver:
    """
    Resolves a supplier raw brand to an Auto_DB supplier ID without blind aliasing.

    The resolver is intentionally conservative: exact/manual aliases win, known
    split/ambiguous brands stay blocked, and missing local suppliers become a
    keep-unmapped decision instead of creating aliases.
    """

    def __init__(self, *, storage: AutoDbRawCloneStorage | None = None):
        self.storage = storage or AutoDbRawCloneStorage()
        self._suppliers_cache: list[_SupplierCandidate] | None = None

    def resolve(
        self,
        *,
        raw_brand: str,
        supplier_code: str = "",
        product_autodb_supplier_id: int | None = None,
    ) -> AutoDbBrandResolution:
        raw = str(raw_brand or "").strip()
        normalized = normalize_brand(raw)
        supplier_code_clean = str(supplier_code or "").strip().lower()
        if not normalized:
            return self._result(
                raw,
                normalized,
                supplier_code_clean,
                "skipped_brand_unresolved",
                "invalid_brand_value",
                "empty or non-normalizable raw_brand",
            )

        if normalized in {normalize_brand(item) for item in INVALID_BRAND_VALUE_KEYS}:
            return self._result(
                raw,
                normalized,
                supplier_code_clean,
                "skipped_brand_unresolved",
                "invalid_brand_value",
                "brand value is placeholder/invalid for TecDoc matching",
            )

        if normalized in {normalize_brand(item) for item in NON_TECDOC_BRAND_KEYS}:
            return self._result(raw, normalized, supplier_code_clean, "skipped_non_tecdoc", "non_tecdoc", "brand is outside TecDoc scope")

        alias = self._autodb_alias(normalized)
        if alias is not None:
            return self._mapped(
                raw,
                normalized,
                supplier_code_clean,
                int(alias.autodb_supplier_id),
                alias.autodb_supplier_name,
                "approved autodb alias",
                resolver_source="alias",
            )

        bound_supplier_id = int(product_autodb_supplier_id or 0)
        if bound_supplier_id > 0:
            bound_supplier = self._supplier_by_id(bound_supplier_id)
            if bound_supplier is not None:
                return self._mapped(
                    raw,
                    normalized,
                    supplier_code_clean,
                    bound_supplier.supplier_id,
                    bound_supplier.supplier_name or bound_supplier.supplier_matchcode,
                    "brand resolved from Product.autodb_supplier_id",
                    resolver_source="product_autodb_supplier_id",
                )
            return self._result(
                raw,
                normalized,
                supplier_code_clean,
                "skipped_unsafe_ambiguous",
                "needs_human_approval",
                f"Product.autodb_supplier_id={bound_supplier_id} missing in auto_db_pro.suppliers",
                resolver_source="product_autodb_supplier_id",
            )

        canonical_from_supplier_alias = self._supplier_import_alias(normalized, supplier_code_clean)
        lookup_key = normalize_brand(canonical_from_supplier_alias) if canonical_from_supplier_alias else BUILTIN_SAFE_ALIASES.get(normalized, normalized)
        resolver_source = "alias" if canonical_from_supplier_alias else ("exact_supplier" if lookup_key == normalized else "normalized_supplier")

        if normalized in UNSAFE_BRAND_KEYS and canonical_from_supplier_alias is None:
            candidates = self._supplier_candidates(lookup_key)
            return AutoDbBrandResolution(
                raw_brand=raw,
                normalized_brand=normalized,
                supplier_code=supplier_code_clean,
                status="skipped_unsafe_ambiguous",
                decision="unsafe_ambiguous",
                reason="brand requires explicit human-approved mapping",
                resolver_source="unsafe_brand",
                candidates=self._candidate_payload(candidates),
            )

        candidates = self._supplier_candidates(lookup_key)
        if len(candidates) == 1:
            supplier = candidates[0]
            return self._mapped(
                raw,
                normalized,
                supplier_code_clean,
                int(supplier.supplier_id),
                supplier.supplier_name or supplier.supplier_matchcode,
                "exact local supplier match" if lookup_key == normalized else f"alias:{lookup_key}",
                resolver_source=resolver_source,
            )

        if len(candidates) > 1:
            return AutoDbBrandResolution(
                raw_brand=raw,
                normalized_brand=normalized,
                supplier_code=supplier_code_clean,
                status="skipped_unsafe_ambiguous",
                decision="unsafe_ambiguous",
                reason="multiple local Auto_DB suppliers match normalized brand",
                resolver_source=resolver_source,
                candidates=self._candidate_payload(candidates),
            )

        return self._result(
            raw,
            normalized,
            supplier_code_clean,
            "skipped_brand_unresolved",
            "keep_unmapped_missing_supplier",
            "no local Auto_DB supplier or approved alias",
            resolver_source=resolver_source,
        )

    def _autodb_alias(self, normalized: str) -> AutoDbSupplierBrandAlias | None:
        return (
            AutoDbSupplierBrandAlias.objects.filter(normalized_raw_brand=normalized, is_active=True)
            .order_by("-manual_confirmed", "-confidence", "created_at")
            .first()
        )

    def _supplier_import_alias(self, normalized: str, supplier_code: str) -> str:
        queryset = SupplierBrandAlias.objects.filter(normalized_alias=normalized, is_active=True)
        if supplier_code:
            queryset = queryset.filter(Q(supplier__code=supplier_code) | Q(supplier__isnull=True))
        alias = queryset.order_by("-priority", "created_at").first()
        if alias is None:
            return ""
        return (alias.canonical_brand_name or (alias.canonical_brand.name if alias.canonical_brand_id else "")).strip()

    def _supplier_by_id(self, supplier_id: int) -> _SupplierCandidate | None:
        if supplier_id <= 0:
            return None
        for candidate in self._load_suppliers():
            if int(candidate.supplier_id) == int(supplier_id):
                return candidate
        return None

    def _supplier_candidates(self, normalized_key: str) -> list[_SupplierCandidate]:
        if not normalized_key:
            return []
        relaxed_key = normalize_brand(normalized_key)
        candidates: list[_SupplierCandidate] = []
        for supplier in self._load_suppliers():
            keys = {
                supplier.normalized_name,
                supplier.normalized_matchcode,
            }
            if relaxed_key and relaxed_key in keys:
                candidates.append(supplier)
        if candidates:
            candidates.sort(key=lambda item: (-int(item.nbrofarticles or 0), int(item.supplier_id)))
            return candidates[:5]
        for supplier in self._load_suppliers():
            keys = {
                normalize_brand(supplier.supplier_name),
                normalize_brand(supplier.supplier_matchcode),
            }
            if relaxed_key and relaxed_key in keys:
                candidates.append(supplier)
        candidates.sort(key=lambda item: (-int(item.nbrofarticles or 0), int(item.supplier_id)))
        if candidates:
            return candidates[:5]
        return []

    def _load_suppliers(self) -> list[_SupplierCandidate]:
        if self._suppliers_cache is not None:
            return self._suppliers_cache
        columns = self.storage.get_local_columns("suppliers")
        if not columns:
            self._suppliers_cache = []
            return self._suppliers_cache
        id_col = self.storage.first_existing_column(table="suppliers", candidates=["id"])
        desc_col = self.storage.first_existing_column(table="suppliers", candidates=["description", "fulldescription", "name"])
        match_col = self.storage.first_existing_column(table="suppliers", candidates=["matchcode", "matchCode"])
        nbrofarticles_col = self.storage.first_existing_column(table="suppliers", candidates=["nbrofarticles", "NbrOfArticles"])
        if not id_col or (not desc_col and not match_col):
            self._suppliers_cache = []
            return self._suppliers_cache
        select_columns = [id_col]
        if desc_col:
            select_columns.append(desc_col)
        if match_col:
            select_columns.append(match_col)
        if nbrofarticles_col:
            select_columns.append(nbrofarticles_col)
        rows = self.storage.fetch_local_rows(table="suppliers", limit=500000, columns=select_columns)
        out: list[_SupplierCandidate] = []
        for row in rows:
            supplier_id_raw = row.get(id_col)
            try:
                supplier_id = int(supplier_id_raw)
            except (TypeError, ValueError):
                continue
            supplier_name = str(row.get(desc_col) or "").strip() if desc_col else ""
            supplier_matchcode = str(row.get(match_col) or "").strip() if match_col else ""
            if not supplier_name:
                continue
            normalized_name = normalize_brand(supplier_name)
            normalized_matchcode = normalize_brand(supplier_matchcode)
            if not normalized_name and not normalized_matchcode:
                continue
            nbrofarticles = 0
            if nbrofarticles_col:
                try:
                    nbrofarticles = int(row.get(nbrofarticles_col) or 0)
                except (TypeError, ValueError):
                    nbrofarticles = 0
            out.append(
                _SupplierCandidate(
                    supplier_id=supplier_id,
                    supplier_name=supplier_name,
                    supplier_matchcode=supplier_matchcode,
                    normalized_name=normalized_name,
                    normalized_matchcode=normalized_matchcode,
                    nbrofarticles=nbrofarticles,
                )
            )
        out.sort(key=lambda item: (-int(item.nbrofarticles or 0), int(item.supplier_id)))
        self._suppliers_cache = out
        return self._suppliers_cache

    def _mapped(
        self,
        raw_brand: str,
        normalized: str,
        supplier_code: str,
        supplier_id: int,
        supplier_name: str,
        reason: str,
        *,
        resolver_source: str,
    ) -> AutoDbBrandResolution:
        return AutoDbBrandResolution(
            raw_brand=raw_brand,
            normalized_brand=normalized,
            supplier_code=supplier_code,
            status="new",
            decision="mapped",
            supplier_id=supplier_id,
            supplier_name=supplier_name,
            reason=reason,
            resolver_source=resolver_source,
        )

    def _result(
        self,
        raw_brand: str,
        normalized: str,
        supplier_code: str,
        status: str,
        decision: str,
        reason: str,
        resolver_source: str = "",
    ) -> AutoDbBrandResolution:
        return AutoDbBrandResolution(
            raw_brand=raw_brand,
            normalized_brand=normalized,
            supplier_code=supplier_code,
            status=status,
            decision=decision,
            reason=reason,
            resolver_source=resolver_source,
        )

    def _candidate_payload(self, candidates: list[_SupplierCandidate]) -> tuple[dict[str, str | int], ...]:
        return tuple(
            {
                "supplier_id": int(item.supplier_id),
                "name": item.supplier_name,
                "matchcode": item.supplier_matchcode,
                "nbrofarticles": int(item.nbrofarticles or 0),
            }
            for item in candidates
        )
