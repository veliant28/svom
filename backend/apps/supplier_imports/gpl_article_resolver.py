from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any


@dataclass(frozen=True)
class GplArticleResolution:
    manufacturer_article: str
    supplier_sku: str
    article_source: str
    article_confidence: str
    article_resolution_status: str
    search_variants: tuple[str, ...] = ()
    candidates: dict[str, str] = field(default_factory=dict)


class GplArticleResolver:
    MANUFACTURER_FIELDS_HIGH = (
        "Артикул ТД",
        "manufacturer_article",
        "producer_article",
        "brand_article",
        "original_article",
        "DataSupplierArticleNumber",
        "datasupplierarticlenumber",
    )
    MANUFACTURER_FIELDS_MEDIUM = (
        "Артикул",
        "article",
        "vendor_code",
        "item_code",
        "goods_code",
    )
    SKU_FIELDS = (
        "Код",
        "cid",
        "supplier_sku",
        "external_sku",
        "sku",
    )

    def resolve(
        self,
        *,
        raw_payload: dict[str, Any] | None,
        article: str,
        external_sku: str,
    ) -> GplArticleResolution:
        payload = raw_payload or {}
        candidates = self.collect_candidates(payload)
        supplier_sku = self._clean(external_sku) or self._first(payload, self.SKU_FIELDS) or self._clean(article)

        manufacturer_article = ""
        article_source = "unknown"
        confidence = "low"
        status = "not_found"

        explicit = self._first(payload, self.MANUFACTURER_FIELDS_HIGH)
        if explicit:
            manufacturer_article = explicit
            article_source = "raw_payload.manufacturer_article"
            confidence = "high"
            status = "resolved"
        else:
            article_candidate = self._first(payload, self.MANUFACTURER_FIELDS_MEDIUM) or self._clean(article)
            if article_candidate and article_candidate != supplier_sku:
                manufacturer_article = article_candidate
                article_source = "raw_payload.article"
                confidence = "medium"
                status = "resolved"

        if not manufacturer_article and self._clean(article):
            manufacturer_article = self._clean(article)
            article_source = "offer.article_fallback"
            confidence = "low"
            status = "manual_required"

        if not manufacturer_article:
            manufacturer_article = supplier_sku
            article_source = "external_sku_fallback" if supplier_sku else "unknown"
            confidence = "low"
            status = "manual_required" if supplier_sku else "not_found"

        variants = self._build_variants(manufacturer_article)
        candidates["resolved_source"] = article_source
        return GplArticleResolution(
            manufacturer_article=manufacturer_article,
            supplier_sku=supplier_sku,
            article_source=article_source,
            article_confidence=confidence,
            article_resolution_status=status,
            search_variants=variants,
            candidates=candidates,
        )

    def collect_candidates(self, payload: dict[str, Any] | None) -> dict[str, str]:
        data = payload or {}
        pairs = {
            "article": self._first(data, ("Артикул", "article")),
            "manufacturer_article": self._first(
                data,
                (
                    "Артикул ТД",
                    "manufacturer_article",
                    "producer_article",
                    "brand_article",
                    "original_article",
                ),
            ),
            "supplier_sku": self._first(data, ("Код", "cid", "supplier_sku", "external_sku", "sku")),
            "vendor_code": self._first(data, ("vendor_code", "item_code", "goods_code")),
            "ean": self._first(data, ("ean", "EAN", "barcode", "Barcode")),
            "oe": self._first(data, ("oe", "oem", "OENbr", "oe_number")),
            "cross": self._first(data, ("cross", "cross_number", "PartsDataSupplierArticleNumber")),
            "image": self._first(data, ("Зображення товару", "image", "image_url", "images")),
            "product_name": self._first(data, ("Найменування", "name", "title")),
            "price_rrc": self._first(data, ("РРЦ грн.", "rrc_currency_980", "RRC")),
            "price_opt2": self._first(data, ("Ціна ОПТ2 грн.", "opt2_currency_980")),
            "price_opt4": self._first(data, ("Ціна ОПТ4 грн.", "opt4_currency_980")),
            "price_opt10": self._first(data, ("Ціна ОПТ10 грн.", "opt10_currency_980")),
        }
        return {key: value for key, value in pairs.items() if value}

    def _first(self, payload: dict[str, Any], names: tuple[str, ...]) -> str:
        for key in names:
            value = self._clean(payload.get(key))
            if value:
                return value
        return ""

    @staticmethod
    def _clean(value: Any) -> str:
        return str(value or "").strip()

    @classmethod
    def _build_variants(cls, article: str) -> tuple[str, ...]:
        trimmed = re.sub(r"\s+", " ", str(article or "")).strip().upper()
        canonical = trimmed.replace(" ", "")
        normalized = re.sub(r"[^A-Z0-9]", "", canonical)
        variants: list[str] = []
        for item in (
            trimmed,
            canonical,
            canonical.replace("-", ""),
            canonical.replace("/", ""),
            canonical.replace("-", "").replace("/", ""),
            canonical.replace("/", "-"),
            normalized,
        ):
            value = str(item or "").strip().upper()
            if value and value not in variants:
                variants.append(value)
        return tuple(variants)
