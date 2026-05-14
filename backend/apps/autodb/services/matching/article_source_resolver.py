from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.autodb.services.article_number_normalizer import ArticleNumberNormalizer
from apps.supplier_imports.parsers.utils import normalize_brand


@dataclass(frozen=True)
class AutoDbArticleSourceResolution:
    article_value: str
    canonical_article: str
    source_type: str
    confidence: float
    reason: str
    status: str = "ok"

    @property
    def is_usable(self) -> bool:
        return self.status == "ok" and bool(self.canonical_article)


class AutoDbArticleSourceResolver:
    """Chooses manufacturer article sources with supplier/source-specific rules."""

    GPL_MANUFACTURER_KEYS = (
        "payload_manufacturer_article",
        "Артикул ТД",
        "manufacturer_article",
        "manufacturerArticle",
        "manufacturer_article_number",
        "manufacturerArticleNumber",
    )
    GPL_FAST_TRUSTED_KEYS = (
        "Артикул ТД",
        "payload_manufacturer_article",
        "article",
        "Артикул",
    )
    UTR_FAST_TRUSTED_KEYS = (
        "Артикул",
        "article",
    )
    GENERIC_FAST_PAYLOAD_KEYS = (
        "manufacturer_article",
        "manufacturerArticle",
        "manufacturer_article_number",
        "manufacturerArticleNumber",
        "oem",
        "oe",
        "OENbr",
    )

    def __init__(self, *, normalizer: ArticleNumberNormalizer | None = None):
        self.normalizer = normalizer or ArticleNumberNormalizer()

    def resolve(
        self,
        *,
        supplier_code: str = "",
        parser_type: str = "",
        source_code: str = "",
        raw_brand: str = "",
        raw_payload: dict[str, Any] | None = None,
        raw_offer_article: str = "",
        product_article: str = "",
        supplier_sku: str = "",
        supplier_sku_is_manufacturer_article: bool = False,
        forbid_raw_offer_fallback: bool = False,
        enforce_product_article: bool = False,
    ) -> AutoDbArticleSourceResolution:
        payload = raw_payload or {}
        parser = str(parser_type or "").strip().lower()
        source = str(source_code or supplier_code or "").strip().lower()
        brand_key = normalize_brand(raw_brand)
        is_wix = brand_key in {"WIX", "WIXFILTER", "WIXFILTERS"}
        is_gpl = parser == "gpl" or source.startswith("gpl")
        is_utr = parser == "utr" or source.startswith("utr")
        product_article_value = str(product_article or "").strip()

        if enforce_product_article:
            if product_article_value:
                return self._ok(product_article_value, "product_article", 1.0, "forced Product.article source")
            return self._bad("missing_product_article", "Product.article is empty")

        if parser == "utr" and is_wix:
            return self._bad("utr_wix_paused", "UTR-WIX paused until manufacturer article source is confirmed")

        if parser == "gpl" and is_wix:
            value = self._first_payload_value(payload, ("payload_manufacturer_article",))
            if value:
                return self._ok(value, "payload_manufacturer_article", 1.0, "GPL-WIX requires payload_manufacturer_article")
            return self._bad("gpl_wix_missing_payload_manufacturer_article", "GPL-WIX cannot use product_article fallback")

        if forbid_raw_offer_fallback:
            if product_article_value:
                return self._ok(product_article_value, "product_article", 1.0, "FAST trusted canonical product article")
            if is_gpl:
                value, key = self._first_payload_value_with_key(payload, self.GPL_FAST_TRUSTED_KEYS)
                if value:
                    return self._ok(value, key, 0.96, "FAST trusted GPL article source")
            if is_utr:
                value, key = self._first_payload_value_with_key(payload, self.UTR_FAST_TRUSTED_KEYS)
                if value:
                    return self._ok(value, key, 0.94, "FAST trusted UTR article source")
            value, key = self._first_payload_value_with_key(payload, self.GENERIC_FAST_PAYLOAD_KEYS)
            if value:
                return self._ok(value, key, 0.9, "FAST generic manufacturer/OE payload source")
            return self._bad("no_trusted_article", "FAST mode requires trusted product/payload article source")

        if is_gpl:
            value, key = self._first_payload_value_with_key(payload, self.GPL_MANUFACTURER_KEYS)
            if value:
                return self._ok(value, key, 0.98, "GPL manufacturer payload source")
            if raw_offer_article:
                return self._ok(raw_offer_article, "raw_offer_article", 0.75, "GPL raw offer article fallback")
            return self._bad("gpl_missing_manufacturer_article", "GPL manufacturer article field not found")

        if supplier_sku and supplier_sku_is_manufacturer_article:
            return self._ok(supplier_sku, "supplier_sku_supplier_rule", 0.8, "supplier-specific rule marks supplier_sku as manufacturer article")

        value, key = self._first_payload_value_with_key(payload, self.GPL_MANUFACTURER_KEYS)
        if value:
            return self._ok(value, key, 0.9, "generic manufacturer payload source")

        if product_article_value:
            return self._ok(product_article_value, "product_article", 0.6, "product article fallback")

        if supplier_sku:
            return self._bad("supplier_sku_not_allowed", "supplier_sku is not used without supplier-specific proof")

        return self._bad("missing_article_source", "no usable manufacturer article source")

    def _ok(self, value: str, source_type: str, confidence: float, reason: str) -> AutoDbArticleSourceResolution:
        article_value = str(value or "").strip()
        canonical = self.normalizer.normalize(article_value).normalized
        if not canonical:
            return self._bad("empty_canonical_article", "article source normalized to empty value")
        return AutoDbArticleSourceResolution(
            article_value=article_value,
            canonical_article=canonical,
            source_type=source_type,
            confidence=float(confidence),
            reason=reason,
            status="ok",
        )

    def _bad(self, source_type: str, reason: str) -> AutoDbArticleSourceResolution:
        return AutoDbArticleSourceResolution(
            article_value="",
            canonical_article="",
            source_type=source_type,
            confidence=0.0,
            reason=reason,
            status="bad_article_source",
        )

    def _first_payload_value(self, payload: dict[str, Any], keys: tuple[str, ...]) -> str:
        value, _key = self._first_payload_value_with_key(payload, keys)
        return value

    def _first_payload_value_with_key(self, payload: dict[str, Any], keys: tuple[str, ...]) -> tuple[str, str]:
        for key in keys:
            value = self._payload_lookup(payload, key)
            text = str(value or "").strip()
            if text:
                return text, key
        return "", ""

    def _payload_lookup(self, payload: dict[str, Any], key: str) -> Any:
        if key in payload:
            return payload.get(key)
        for container_key in ("payload", "raw_payload", "data", "row", "source"):
            nested = payload.get(container_key)
            if isinstance(nested, dict) and key in nested:
                return nested.get(key)
        return None
