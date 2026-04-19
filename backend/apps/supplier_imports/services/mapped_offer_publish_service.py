"""Backward-compatible shim for the decomposed mapped offer publish service."""

from __future__ import annotations

from apps.catalog.services import generate_unique_product_slug, sanitize_product_name
from apps.pricing.services import ProductRepricer
from apps.supplier_imports.parsers.utils import normalize_brand
from apps.supplier_imports.selectors import get_import_source_by_code, get_supplier_raw_offers_publish_queryset

from .mapped_offer_publish import SupplierMappedOffersPublishService, SupplierMappedPublishResult
from .mapped_offer_publish.selection import PUBLISHABLE_STATUSES as _PUBLISHABLE_STATUSES
from .mapped_offer_publish.types import PublishCounters as _PublishCounters

__all__ = [
    "SupplierMappedPublishResult",
    "SupplierMappedOffersPublishService",
    "_PublishCounters",
    "_PUBLISHABLE_STATUSES",
    "ProductRepricer",
    "normalize_brand",
    "sanitize_product_name",
    "generate_unique_product_slug",
    "get_import_source_by_code",
    "get_supplier_raw_offers_publish_queryset",
]
