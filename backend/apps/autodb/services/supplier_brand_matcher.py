from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db.models import Q
from django.db.utils import OperationalError, ProgrammingError

from apps.autodb.models import AutoDbSupplierBrandAlias
from apps.autodb.services.raw_clone_storage import AutoDbRawCloneStorage
from apps.supplier_imports.models import SupplierBrandAlias
from apps.supplier_imports.parsers.utils import normalize_brand


@dataclass(frozen=True)
class SupplierBrandCandidate:
    supplier_id: int
    supplier_description: str
    supplier_matchcode: str
    confidence: float
    reason: str


@dataclass(frozen=True)
class SupplierBrandMatchResult:
    raw_brand: str
    normalized_brand: str
    matched_supplier_id: int | None
    confidence: float
    reason: str
    candidates: tuple[SupplierBrandCandidate, ...]


def normalize_brand_lookup_key(value: str | None) -> str:
    if not value:
        return ""
    normalized = str(value).upper().strip()
    replacements = {
        "Ä": "AE",
        "Ö": "OE",
        "Ü": "UE",
        "ẞ": "SS",
        "ß": "SS",
        "Æ": "AE",
        "Œ": "OE",
    }
    for source, target in replacements.items():
        normalized = normalized.replace(source, target)
    return normalize_brand(normalized)


class SupplierBrandMatcher:
    LOOKUP_COLUMNS = ("description", "matchcode", "fulldescription")
    HIGH_CONFIDENCE_ALIAS = 0.9

    def __init__(self, *, storage: AutoDbRawCloneStorage | None = None):
        self.storage = storage or AutoDbRawCloneStorage()
        self._supplier_rows_cache: list[dict[str, Any]] | None = None
        self._alias_cache: dict[str, str] | None = None
        self._autodb_alias_cache: dict[str, dict[str, Any]] | None = None

    def resolve_many(self, brands: list[str], *, source_id: str | None = None, supplier_id: str | None = None) -> dict[str, SupplierBrandMatchResult]:
        unique = sorted({normalize_brand_lookup_key(item) for item in brands if normalize_brand_lookup_key(item)})
        if not unique:
            return {}
        rows = self._load_suppliers()
        alias_map = self._load_aliases(source_id=source_id, supplier_id=supplier_id)
        autodb_alias_map = self._load_autodb_aliases()
        rows_by_id = {self._safe_int(row.get("id")): row for row in rows}

        by_desc: dict[str, list[dict[str, Any]]] = {}
        by_matchcode: dict[str, list[dict[str, Any]]] = {}
        by_relaxed: dict[str, list[dict[str, Any]]] = {}

        for row in rows:
            row_desc = str(row.get("description") or "")
            row_matchcode = str(row.get("matchcode") or "")
            row_full = str(row.get("fulldescription") or "")
            desc_norm = normalize_brand_lookup_key(row_desc)
            match_norm = normalize_brand_lookup_key(row_matchcode)
            full_norm = normalize_brand_lookup_key(row_full)

            for key in {desc_norm, full_norm}:
                if key:
                    by_desc.setdefault(key, []).append(row)
                    by_relaxed.setdefault(self._relax(key), []).append(row)
            if match_norm:
                by_matchcode.setdefault(match_norm, []).append(row)
                by_relaxed.setdefault(self._relax(match_norm), []).append(row)

        results: dict[str, SupplierBrandMatchResult] = {}
        for brand in unique:
            alias_hit = autodb_alias_map.get(brand)
            if alias_hit:
                aliased_supplier_id = self._safe_int(alias_hit.get("autodb_supplier_id"))
                row = rows_by_id.get(aliased_supplier_id)
                if row and aliased_supplier_id is not None:
                    alias_confidence = float(alias_hit.get("confidence") or 0.0)
                    alias_reason = (
                        "manual_alias"
                        if bool(alias_hit.get("manual_confirmed"))
                        else "high_confidence_alias"
                    )
                    alias_candidate = self._candidate_from_row(row, confidence=alias_confidence, reason=alias_reason)
                    if alias_candidate is not None:
                        results[brand] = SupplierBrandMatchResult(
                            raw_brand=brand,
                            normalized_brand=brand,
                            matched_supplier_id=alias_candidate.supplier_id,
                            confidence=alias_candidate.confidence,
                            reason=alias_reason,
                            candidates=(alias_candidate,),
                        )
                        continue

            canonical = alias_map.get(brand, brand)
            candidates: list[SupplierBrandCandidate] = []

            for row in by_matchcode.get(canonical, []):
                candidate = self._candidate_from_row(row, confidence=1.0, reason="matchcode_exact")
                if candidate:
                    candidates.append(candidate)
            for row in by_desc.get(canonical, []):
                candidate = self._candidate_from_row(row, confidence=0.95, reason="description_exact")
                if candidate:
                    candidates.append(candidate)

            if not candidates:
                relaxed = self._relax(canonical)
                for row in by_relaxed.get(relaxed, []):
                    candidate = self._candidate_from_row(row, confidence=0.85, reason="relaxed_match")
                    if candidate:
                        candidates.append(candidate)

            candidates = self._dedupe_candidates(candidates)
            top = candidates[0] if candidates else None
            if top:
                results[brand] = SupplierBrandMatchResult(
                    raw_brand=brand,
                    normalized_brand=canonical,
                    matched_supplier_id=top.supplier_id,
                    confidence=top.confidence,
                    reason=top.reason if canonical == brand else f"alias:{top.reason}",
                    candidates=tuple(candidates[:10]),
                )
            else:
                results[brand] = SupplierBrandMatchResult(
                    raw_brand=brand,
                    normalized_brand=canonical,
                    matched_supplier_id=None,
                    confidence=0.0,
                    reason="brand_not_found",
                    candidates=(),
                )
        return results

    def _load_suppliers(self) -> list[dict[str, Any]]:
        if self._supplier_rows_cache is not None:
            return self._supplier_rows_cache
        self.storage.ensure_table("suppliers")
        rows = self.storage.fetch_local_rows(table="suppliers", limit=200000)
        self._supplier_rows_cache = rows
        return rows

    def _load_aliases(self, *, source_id: str | None, supplier_id: str | None) -> dict[str, str]:
        cache_key = f"{source_id or ''}:{supplier_id or ''}"
        if self._alias_cache is not None and cache_key == ":":
            return self._alias_cache

        queryset = SupplierBrandAlias.objects.filter(is_active=True)
        scoped = queryset.filter(Q(source_id=source_id) | Q(source__isnull=True)) if source_id else queryset
        scoped = scoped.filter(Q(supplier_id=supplier_id) | Q(supplier__isnull=True)) if supplier_id else scoped

        alias_map: dict[str, str] = {}
        try:
            for item in scoped.order_by("-priority")[:5000]:
                alias = normalize_brand_lookup_key(item.normalized_alias)
                canonical = normalize_brand_lookup_key(item.canonical_brand_name or (item.canonical_brand.name if item.canonical_brand else ""))
                if alias and canonical and alias not in alias_map:
                    alias_map[alias] = canonical
        except (ProgrammingError, OperationalError):
            alias_map = {}

        if source_id is None and supplier_id is None:
            self._alias_cache = alias_map
        return alias_map

    def _load_autodb_aliases(self) -> dict[str, dict[str, Any]]:
        if self._autodb_alias_cache is not None:
            return self._autodb_alias_cache
        try:
            queryset = AutoDbSupplierBrandAlias.objects.filter(is_active=True).order_by(
                "-manual_confirmed",
                "-confidence",
                "updated_at",
            )
            alias_map: dict[str, dict[str, Any]] = {}
            for item in queryset.iterator(chunk_size=500):
                normalized = normalize_brand_lookup_key(item.normalized_raw_brand or item.raw_brand)
                if not normalized:
                    continue
                confidence = float(item.confidence or 0.0)
                manual = bool(item.manual_confirmed)
                # Safety rule: only manually confirmed AutoDB aliases are eligible.
                if not manual:
                    continue
                if normalized in alias_map:
                    continue
                alias_map[normalized] = {
                    "autodb_supplier_id": int(item.autodb_supplier_id),
                    "confidence": confidence,
                    "manual_confirmed": manual,
                    "source": str(item.source or ""),
                }
            self._autodb_alias_cache = alias_map
            return alias_map
        except Exception:  # noqa: BLE001
            return {}

    def _candidate_from_row(self, row: dict[str, Any], *, confidence: float, reason: str) -> SupplierBrandCandidate | None:
        supplier_id = row.get("id")
        try:
            sid = int(supplier_id)
        except (TypeError, ValueError):
            return None
        return SupplierBrandCandidate(
            supplier_id=sid,
            supplier_description=str(row.get("description") or "").strip(),
            supplier_matchcode=str(row.get("matchcode") or "").strip(),
            confidence=confidence,
            reason=reason,
        )

    def _dedupe_candidates(self, items: list[SupplierBrandCandidate]) -> list[SupplierBrandCandidate]:
        best: dict[int, SupplierBrandCandidate] = {}
        for item in items:
            current = best.get(item.supplier_id)
            if current is None or item.confidence > current.confidence:
                best[item.supplier_id] = item
        return sorted(best.values(), key=lambda item: (-item.confidence, item.supplier_id))

    def _relax(self, value: str) -> str:
        text = normalize_brand_lookup_key(value)
        for needle in ("-", ".", "_", " "):
            text = text.replace(needle, "")
        return text

    def _safe_int(self, value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
