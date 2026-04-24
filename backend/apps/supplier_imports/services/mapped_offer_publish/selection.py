from __future__ import annotations

from decimal import Decimal

from apps.catalog.services import sanitize_product_name
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.selectors import get_supplier_raw_offers_publish_queryset

PUBLISHABLE_STATUSES = frozenset(
    {
        SupplierRawOffer.CATEGORY_MAPPING_STATUS_MANUAL_MAPPED,
        SupplierRawOffer.CATEGORY_MAPPING_STATUS_AUTO_MAPPED,
    }
)


def get_publish_queryset(*, supplier_code: str, run_id: str | None = None):
    return get_supplier_raw_offers_publish_queryset(supplier_code=supplier_code, run_id=run_id)


def resolve_supplier_sku(*, raw_offer: SupplierRawOffer) -> str:
    return (raw_offer.external_sku or raw_offer.article or "").strip()[:128]


def build_product_sku(*, supplier_sku: str) -> str:
    return supplier_sku[:64]


def build_offer_key(*, supplier_sku: str, raw_offer_id: str) -> str:
    return supplier_sku.upper() if supplier_sku else f"row:{raw_offer_id}"


def resolve_skip_reason(
    *,
    raw_offer: SupplierRawOffer,
    supplier_sku: str,
    include_needs_review: bool,
) -> str:
    if raw_offer.mapped_category_id is None:
        return "missing_mapped_category"

    if raw_offer.category_mapping_status == SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW and not include_needs_review:
        return "needs_review"

    if raw_offer.category_mapping_status not in PUBLISHABLE_STATUSES:
        if include_needs_review and raw_offer.category_mapping_status == SupplierRawOffer.CATEGORY_MAPPING_STATUS_NEEDS_REVIEW:
            pass
        else:
            return f"status_{raw_offer.category_mapping_status or 'unknown'}"

    if raw_offer.price is None:
        return "missing_price"
    if raw_offer.price <= Decimal("0"):
        return "non_positive_price"

    if not sanitize_product_name(raw_offer.product_name):
        return "missing_product_name"
    if not supplier_sku:
        return "missing_supplier_sku"
    return ""
