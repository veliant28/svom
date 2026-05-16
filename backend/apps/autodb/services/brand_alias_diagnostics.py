from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from django.db.models import Q

from apps.autodb.models import AutoDbSupplierBrandAlias
from apps.autodb.services.supplier_brand_matcher import (
    SupplierBrandMatchResult,
    SupplierBrandMatcher,
    normalize_brand_lookup_key,
)
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.parsers.utils import normalize_article


def _brand_hint_key(value: str) -> str:
    text = str(value or "").strip().upper()
    for needle in ("-", ".", "_", " "):
        text = text.replace(needle, "")
    return text


INVALID_AUTO_BRANDS = {
    _brand_hint_key("Без бренду"),
    _brand_hint_key("ТМК"),
    _brand_hint_key("Промбизнес"),
    _brand_hint_key("Покраско"),
    _brand_hint_key("AT"),
    _brand_hint_key("K2"),
    _brand_hint_key("LSA"),
    _brand_hint_key("MITKA"),
    _brand_hint_key("DAINTON"),
    _brand_hint_key("LAVITA"),
    _brand_hint_key("VIRA"),
    _brand_hint_key("CS SYSTEM"),
    _brand_hint_key("Elegant"),
    _brand_hint_key("MOL"),
    _brand_hint_key("XADO"),
    _brand_hint_key("LOTOS"),
    _brand_hint_key("HELPIX"),
    _brand_hint_key("Hi-Gear"),
    _brand_hint_key("TURTLE WAX"),
    _brand_hint_key("TotalEnergies"),
    _brand_hint_key("DOLONI"),
    _brand_hint_key("YATO"),
    _brand_hint_key("NANO5"),
    _brand_hint_key("Mr.Build"),
    _brand_hint_key("VERYLUBE"),
    _brand_hint_key("Doctor Wax"),
    _brand_hint_key("Done Deal"),
    _brand_hint_key("STEEL POWER"),
    _brand_hint_key("VOIN"),
    _brand_hint_key("Smirdex"),
    _brand_hint_key("VIROK"),
    _brand_hint_key("NOVVIC"),
    _brand_hint_key("STEP UP"),
    _brand_hint_key("NANOX"),
    _brand_hint_key("ANY WAY"),
    _brand_hint_key("ATAMAN"),
    _brand_hint_key("asia360"),
}


@dataclass
class BrandAliasStat:
    raw_brand: str
    normalized_brand: str
    offers: int = 0
    unique_articles: set[str] = field(default_factory=set)
    sample_articles: list[str] = field(default_factory=list)

    def add_article(self, value: str) -> None:
        article = normalize_article(value or "")
        if not article:
            return
        self.unique_articles.add(article)
        if len(self.sample_articles) < 5 and article not in self.sample_articles:
            self.sample_articles.append(article)


@dataclass
class BrandAliasDiagnosticRow:
    raw_brand: str
    normalized_brand: str
    offers: int
    unique_articles: int
    exact_supplier_match: bool
    relaxed_candidates: int
    current_alias: bool
    current_alias_supplier_id: int | None
    recommended_supplier_id: int | None
    recommended_supplier_name: str
    confidence: float
    recommendation: str
    reason: str
    candidates: str
    sample_articles: str


class AutoDbBrandAliasDiagnosticsService:
    RECOMMEND_CONFIDENCE_MIN = 0.9

    def __init__(self, *, matcher: SupplierBrandMatcher | None = None):
        self.matcher = matcher or SupplierBrandMatcher()

    def collect_brand_stats(
        self,
        *,
        supplier_code: str,
        all_suppliers: bool,
        limit: int,
        brand_filters: set[str],
    ) -> list[BrandAliasStat]:
        queryset = SupplierRawOffer.objects.select_related("source", "supplier").order_by("id")
        if not all_suppliers:
            query = Q(source__code__iexact=supplier_code) | Q(supplier__code__iexact=supplier_code)
            queryset = queryset.filter(query)
        if limit > 0:
            queryset = queryset[:limit]

        grouped: dict[str, BrandAliasStat] = {}
        values = queryset.values("brand_name", "normalized_brand", "article", "external_sku")
        for row in values.iterator(chunk_size=2000):
            raw_brand = str(row.get("brand_name") or "").strip()
            normalized = normalize_brand_lookup_key(raw_brand)
            if not normalized:
                normalized = normalize_brand_lookup_key(str(row.get("normalized_brand") or ""))
            if brand_filters and _brand_hint_key(raw_brand or normalized) not in brand_filters:
                continue
            raw_key = raw_brand or normalized or "-"
            stat = grouped.get(raw_key)
            if stat is None:
                stat = BrandAliasStat(raw_brand=raw_key, normalized_brand=normalized)
                grouped[raw_key] = stat
            stat.offers += 1
            stat.add_article(str(row.get("article") or row.get("external_sku") or ""))

        rows = list(grouped.values())
        rows.sort(key=lambda item: item.offers, reverse=True)
        return rows

    def diagnose(
        self,
        *,
        stats: list[BrandAliasStat],
        min_confidence: float,
        source_id: str | None = None,
        supplier_id: str | None = None,
    ) -> list[BrandAliasDiagnosticRow]:
        brand_keys = [item.normalized_brand for item in stats if item.normalized_brand]
        match_map = self.matcher.resolve_many(brand_keys, source_id=source_id, supplier_id=supplier_id)
        alias_map = self._load_existing_aliases(brand_keys)

        rows: list[BrandAliasDiagnosticRow] = []
        for stat in stats:
            matched = match_map.get(stat.normalized_brand) if stat.normalized_brand else None
            top = matched.candidates[0] if matched and matched.candidates else None
            second = matched.candidates[1] if matched and len(matched.candidates) > 1 else None
            current_alias = alias_map.get(stat.normalized_brand)
            relaxed_candidates = len([c for c in (matched.candidates if matched else ()) if c.reason == "relaxed_match"])
            exact_match = bool(top and top.reason in {"matchcode_exact", "description_exact", "manual_alias", "high_confidence_alias"})
            recommendation = "manual_review"
            reason = "no_match_candidates"
            rec_supplier_id: int | None = None
            rec_supplier_name = ""
            confidence = float(top.confidence if top else 0.0)

            invalid_hint = _brand_hint_key(stat.raw_brand) in INVALID_AUTO_BRANDS or not stat.normalized_brand
            if invalid_hint:
                recommendation = "supplier_only_or_non_auto"
                reason = "invalid_or_non_auto_brand"
            elif current_alias is not None:
                recommendation = "alias_exists"
                reason = "already_aliased"
            elif top is None:
                recommendation = "manual_review"
                reason = "brand_not_found"
            elif second is not None and float(second.confidence) == float(top.confidence) and second.supplier_id != top.supplier_id:
                recommendation = "manual_review"
                reason = "ambiguous_top_candidates"
            elif top.reason not in {"matchcode_exact", "description_exact", "relaxed_match"}:
                recommendation = "manual_review"
                reason = f"unsupported_reason:{top.reason}"
            elif confidence < float(min_confidence):
                recommendation = "manual_review"
                reason = f"confidence_below_threshold:{confidence:.2f}"
            else:
                recommendation = "create_alias"
                reason = top.reason
                rec_supplier_id = int(top.supplier_id)
                rec_supplier_name = str(top.supplier_description or top.supplier_matchcode or "")

            candidate_text = ""
            if matched and matched.candidates:
                candidate_text = "; ".join(
                    f"{c.supplier_id}:{c.confidence:.2f}:{c.reason}" for c in matched.candidates[:5]
                )

            rows.append(
                BrandAliasDiagnosticRow(
                    raw_brand=stat.raw_brand,
                    normalized_brand=stat.normalized_brand,
                    offers=stat.offers,
                    unique_articles=len(stat.unique_articles),
                    exact_supplier_match=exact_match,
                    relaxed_candidates=relaxed_candidates,
                    current_alias=current_alias is not None,
                    current_alias_supplier_id=int(current_alias["autodb_supplier_id"]) if current_alias else None,
                    recommended_supplier_id=rec_supplier_id,
                    recommended_supplier_name=rec_supplier_name,
                    confidence=confidence,
                    recommendation=recommendation,
                    reason=reason,
                    candidates=candidate_text,
                    sample_articles=", ".join(stat.sample_articles[:5]),
                )
            )
        rows.sort(key=lambda item: item.offers, reverse=True)
        return rows

    def _load_existing_aliases(self, normalized_brands: list[str]) -> dict[str, dict[str, Any]]:
        values = sorted({item for item in normalized_brands if item})
        if not values:
            return {}
        result: dict[str, dict[str, Any]] = {}
        queryset = AutoDbSupplierBrandAlias.objects.filter(
            normalized_raw_brand__in=values,
            is_active=True,
        ).values("normalized_raw_brand", "autodb_supplier_id", "manual_confirmed", "confidence")
        for row in queryset.iterator(chunk_size=1000):
            key = normalize_brand_lookup_key(str(row.get("normalized_raw_brand") or ""))
            if key and key not in result:
                result[key] = row
        return result

    def upsert_alias(
        self,
        *,
        raw_brand: str,
        normalized_brand: str,
        supplier_id: int,
        supplier_name: str,
        confidence: float,
        manual_confirmed: bool,
        note: str,
        source: str,
    ) -> tuple[AutoDbSupplierBrandAlias, bool]:
        defaults = {
            "raw_brand": raw_brand,
            "autodb_supplier_id": supplier_id,
            "autodb_supplier_name": supplier_name[:255],
            "source": source,
            "confidence": Decimal(f"{confidence:.2f}"),
            "manual_confirmed": manual_confirmed,
            "note": note or "",
            "is_active": True,
        }
        return AutoDbSupplierBrandAlias.objects.update_or_create(
            normalized_raw_brand=normalize_brand_lookup_key(normalized_brand),
            defaults=defaults,
        )
