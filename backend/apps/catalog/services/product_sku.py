from __future__ import annotations

from collections.abc import Iterable
import re

from apps.catalog.models import AutoDbProductLinkQuality, Product
from apps.pricing.models import SupplierOffer
from apps.supplier_imports.models import SupplierRawOffer


GPL_SUPPLIER_CODE = "gpl"


def _clean(value: str | None) -> str:
    return str(value or "").strip()


def _prefetched_supplier_offers(product: Product) -> list[SupplierOffer]:
    backoffice_prefetched = getattr(product, "backoffice_supplier_offers", None)
    if backoffice_prefetched is not None:
        return list(backoffice_prefetched)
    cached = getattr(product, "_prefetched_objects_cache", {})
    if isinstance(cached, dict) and "supplier_offers" in cached:
        return list(cached["supplier_offers"])
    return []


def _prefetched_raw_offers(product: Product) -> list[SupplierRawOffer]:
    backoffice_prefetched = getattr(product, "backoffice_raw_offers", None)
    if backoffice_prefetched is not None:
        return list(backoffice_prefetched)
    cached = getattr(product, "_prefetched_objects_cache", {})
    if isinstance(cached, dict) and "raw_supplier_offers" in cached:
        return list(cached["raw_supplier_offers"])
    return []


def _first(items: Iterable[str]) -> str:
    for item in items:
        clean = _clean(item)
        if clean:
            return clean
    return ""


def _normalize_code(value: str | None) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def _resolve_supplier_code_set(product: Product) -> set[str]:
    codes: set[str] = set()
    for offer in _prefetched_supplier_offers(product):
        code = _clean(getattr(getattr(offer, "supplier", None), "code", "")).lower()
        if code:
            codes.add(code)
    for raw_offer in _prefetched_raw_offers(product):
        source_code = _clean(getattr(getattr(raw_offer, "source", None), "code", "")).lower()
        supplier_code = _clean(getattr(getattr(raw_offer, "supplier", None), "code", "")).lower()
        if source_code:
            codes.add(source_code)
        if supplier_code:
            codes.add(supplier_code)
    if codes:
        return codes
    return {
        _clean(code).lower()
        for code in product.supplier_offers.values_list("supplier__code", flat=True).distinct()
        if _clean(code)
    }


def _resolve_offer_supplier_code_set(product: Product) -> set[str]:
    codes: set[str] = set()
    for offer in _prefetched_supplier_offers(product):
        code = _clean(getattr(getattr(offer, "supplier", None), "code", "")).lower()
        if code:
            codes.add(code)
    if codes:
        return codes
    return {
        _clean(code).lower()
        for code in product.supplier_offers.values_list("supplier__code", flat=True).distinct()
        if _clean(code)
    }


def is_gpl_product(product: Product) -> bool:
    return GPL_SUPPLIER_CODE in _resolve_supplier_code_set(product)


def is_multi_offer_product(product: Product) -> bool:
    return len(_resolve_offer_supplier_code_set(product)) > 1


def _is_gpl_only_product(product: Product) -> bool:
    codes = _resolve_supplier_code_set(product)
    if not codes:
        return False
    return GPL_SUPPLIER_CODE in codes and all(code == GPL_SUPPLIER_CODE for code in codes)


def _resolve_gpl_display_sku(product: Product) -> str:
    raw_offers = _prefetched_raw_offers(product)
    if not raw_offers:
        raw_offers = list(
            product.raw_supplier_offers.filter(source__code=GPL_SUPPLIER_CODE)
            .order_by("-updated_at", "-id")
            .only("raw_payload", "external_sku")
        )

    for raw_offer in raw_offers:
        payload = getattr(raw_offer, "raw_payload", {}) or {}
        code_value = _clean(payload.get("Код"))
        if code_value:
            return code_value

    from_raw_offer = _first(getattr(raw_offer, "external_sku", "") for raw_offer in raw_offers)
    if from_raw_offer:
        return from_raw_offer

    supplier_offers = _prefetched_supplier_offers(product)
    if not supplier_offers:
        supplier_offers = list(
            product.supplier_offers.filter(supplier__code=GPL_SUPPLIER_CODE)
            .select_related("supplier")
            .order_by("supplier__priority", "-updated_at", "id")
            .only("supplier_sku", "supplier__code")
        )
    from_supplier_offer = _first(getattr(offer, "supplier_sku", "") for offer in supplier_offers)
    if from_supplier_offer:
        return from_supplier_offer

    return _clean(getattr(product, "sku", ""))


def get_product_display_sku(product: Product) -> str:
    svom_sku = _clean(getattr(product, "svom_sku", ""))
    if svom_sku:
        return svom_sku

    if is_multi_offer_product(product):
        canonical_article = _clean(getattr(product, "article", ""))
        if canonical_article:
            return canonical_article

        autodb_article = _clean(getattr(product, "autodb_article_number", ""))
        if autodb_article:
            return autodb_article

        return _clean(getattr(product, "sku", ""))

    if not is_gpl_product(product):
        return _clean(getattr(product, "sku", ""))

    if _is_gpl_only_product(product):
        return _resolve_gpl_display_sku(product)

    canonical_article = _clean(getattr(product, "article", ""))
    if canonical_article:
        return canonical_article

    autodb_article = _clean(getattr(product, "autodb_article_number", ""))
    if autodb_article:
        return autodb_article

    return _clean(getattr(product, "sku", ""))


def get_product_internal_import_key(product: Product) -> str:
    return _clean(getattr(product, "sku", ""))


def get_product_manufacturer_article(product: Product) -> str:
    display_sku = get_product_display_sku(product)

    raw_offers = _prefetched_raw_offers(product)
    if not raw_offers and is_gpl_product(product) and _is_gpl_only_product(product):
        raw_offers = list(
            product.raw_supplier_offers.filter(source__code=GPL_SUPPLIER_CODE)
            .order_by("-updated_at", "-id")
            .only("raw_payload", "article")
        )

    def _candidate(values: Iterable[str]) -> str:
        for value in values:
            clean = _clean(value)
            if not clean:
                continue
            if clean == display_sku:
                continue
            return clean
        return ""

    if raw_offers and _is_gpl_only_product(product):
        td_candidate = _candidate(
            (
                (getattr(raw_offer, "raw_payload", {}) or {}).get("Артикул ТД")
                or (getattr(raw_offer, "raw_payload", {}) or {}).get("Артикул ТД.")
                or (getattr(raw_offer, "raw_payload", {}) or {}).get("manufacturer_article")
                or (getattr(raw_offer, "raw_payload", {}) or {}).get("article_td")
            )
            for raw_offer in raw_offers
        )
        if td_candidate:
            return td_candidate

        supplier_article_candidate = _candidate(
            (
                (getattr(raw_offer, "raw_payload", {}) or {}).get("Артикул")
                or (getattr(raw_offer, "raw_payload", {}) or {}).get("article")
                or getattr(raw_offer, "article", "")
            )
            for raw_offer in raw_offers
        )
        if supplier_article_candidate:
            return supplier_article_candidate

    if raw_offers:
        generic_candidate = _candidate(
            (
                (getattr(raw_offer, "raw_payload", {}) or {}).get("manufacturer_article")
                or (getattr(raw_offer, "raw_payload", {}) or {}).get("article_td")
                or (getattr(raw_offer, "raw_payload", {}) or {}).get("article")
                or getattr(raw_offer, "article", "")
            )
            for raw_offer in raw_offers
        )
        if generic_candidate:
            return generic_candidate

    article_fallback = _clean(getattr(product, "article", ""))
    if not _is_gpl_only_product(product) and article_fallback:
        return article_fallback
    if article_fallback and article_fallback != display_sku:
        return article_fallback

    article_key = _clean(getattr(product, "autodb_article_key", ""))
    autodb_article_number = _clean(getattr(product, "autodb_article_number", ""))
    if article_key and autodb_article_number and autodb_article_number != display_sku:
        is_trusted = AutoDbProductLinkQuality.objects.filter(
            product=product,
            autodb_article_key=article_key,
            status=AutoDbProductLinkQuality.STATUS_TRUSTED,
        ).exists()
        if is_trusted:
            return autodb_article_number

    return ""
