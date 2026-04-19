from __future__ import annotations

from decimal import Decimal

from apps.supplier_imports.models import SupplierRawOffer

from .normalizers import to_confidence


def has_changes(
    *,
    raw_offer: SupplierRawOffer,
    category_id: str | None,
    status: str,
    reason: str,
    confidence: Decimal | None,
    mapped_by_id: str | None,
) -> bool:
    current_category_id = str(raw_offer.mapped_category_id) if raw_offer.mapped_category_id else None
    current_confidence = to_confidence(raw_offer.category_mapping_confidence)
    next_confidence = to_confidence(confidence)
    current_mapped_by_id = str(raw_offer.category_mapped_by_id) if raw_offer.category_mapped_by_id else None
    return (
        current_category_id != category_id
        or raw_offer.category_mapping_status != status
        or raw_offer.category_mapping_reason != reason
        or current_confidence != next_confidence
        or current_mapped_by_id != mapped_by_id
    )
