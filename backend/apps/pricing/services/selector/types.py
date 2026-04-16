from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from apps.pricing.models import SupplierOffer


class OfferStrategy:
    BEST_OFFER = "best_offer"
    CHEAPEST = "cheapest"
    FASTEST_DELIVERY = "fastest_delivery"
    PREFERRED_SUPPLIER = "preferred_supplier"
    IN_STOCK_FIRST = "in_stock_first"

    ALL = (
        BEST_OFFER,
        CHEAPEST,
        FASTEST_DELIVERY,
        PREFERRED_SUPPLIER,
        IN_STOCK_FIRST,
    )


@dataclass(frozen=True)
class OfferCandidate:
    offer: SupplierOffer
    landed_cost: Decimal
    has_stock: bool
    supplier_is_preferred: bool
    supplier_priority: int
    supplier_quality_score: Decimal

    def to_debug_payload(self) -> dict[str, Any]:
        return {
            "offer_id": str(self.offer.id),
            "supplier_id": str(self.offer.supplier_id),
            "supplier_name": self.offer.supplier.name,
            "supplier_code": self.offer.supplier.code,
            "supplier_preferred": self.supplier_is_preferred,
            "supplier_priority": self.supplier_priority,
            "supplier_quality_score": str(self.supplier_quality_score),
            "stock_qty": self.offer.stock_qty,
            "lead_time_days": self.offer.lead_time_days,
            "currency": self.offer.currency,
            "landed_cost": str(self.landed_cost),
            "is_available": self.offer.is_available,
        }


@dataclass(frozen=True)
class OfferSelectionResult:
    selected_offer: SupplierOffer | None
    requested_strategy: str
    strategy_applied: str | None
    fallback_used: bool
    reason: str
    explainability: dict[str, Any]
