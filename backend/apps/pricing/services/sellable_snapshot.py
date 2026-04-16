from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from apps.catalog.models import Product
from apps.pricing.services.availability_calculator import AvailabilityCalculator
from apps.pricing.services.rounding import quantize_money
from apps.pricing.services.selector import OfferStrategy, SupplierOfferSelector


@dataclass(frozen=True)
class SellableSnapshot:
    product_id: str
    currency: str
    current_sell_price: Decimal
    availability_status: str
    availability_label: str
    estimated_delivery_days: int | None
    procurement_source_summary: str
    is_sellable: bool
    max_order_quantity: int | None
    selected_offer_id: str | None
    selected_offer_supplier_name: str | None
    strategy_requested: str
    strategy_applied: str | None
    fallback_used: bool
    selector_reason: str
    supplier_confidence: str
    quality_hints: list[str]
    explainability: dict[str, Any]

    def to_public_payload(self) -> dict[str, Any]:
        return {
            "current_sell_price": str(self.current_sell_price),
            "currency": self.currency,
            "availability_status": self.availability_status,
            "availability_label": self.availability_label,
            "estimated_delivery_days": self.estimated_delivery_days,
            "procurement_source_summary": self.procurement_source_summary,
            "is_sellable": self.is_sellable,
        }

    def to_cart_payload(self) -> dict[str, Any]:
        return {
            **self.to_public_payload(),
            "max_order_quantity": self.max_order_quantity,
            "supplier_confidence": self.supplier_confidence,
            "quality_hints": self.quality_hints,
        }

    def to_order_snapshot_payload(self) -> dict[str, Any]:
        return {
            "current_sell_price": str(self.current_sell_price),
            "currency": self.currency,
            "availability_status": self.availability_status,
            "availability_label": self.availability_label,
            "estimated_delivery_days": self.estimated_delivery_days,
            "procurement_source_summary": self.procurement_source_summary,
            "selected_offer_id": self.selected_offer_id,
            "strategy_requested": self.strategy_requested,
            "strategy_applied": self.strategy_applied,
            "fallback_used": self.fallback_used,
            "selector_reason": self.selector_reason,
            "supplier_confidence": self.supplier_confidence,
            "quality_hints": self.quality_hints,
            "explainability": self.explainability,
        }


class ProductSellableSnapshotService:
    def __init__(self) -> None:
        self.selector = SupplierOfferSelector()
        self.availability_calculator = AvailabilityCalculator()

    def build(
        self,
        *,
        product: Product,
        quantity: int = 1,
        strategy: str = OfferStrategy.BEST_OFFER,
    ) -> SellableSnapshot:
        selection = self.selector.select_for_product(
            product=product,
            quantity=quantity,
            strategy=strategy,
        )
        availability = self.availability_calculator.calculate(
            product=product,
            selection=selection,
            requested_quantity=quantity,
        )

        product_price = getattr(product, "product_price", None)
        selected_offer = selection.selected_offer

        sell_price = Decimal("0.00")
        currency = "UAH"

        base_price = self._safe_decimal(getattr(product_price, "final_price", None))
        if base_price > Decimal("0"):
            sell_price = quantize_money(base_price)
            currency = product_price.currency or currency
        elif selected_offer is not None:
            sell_price = quantize_money(selected_offer.purchase_price + selected_offer.logistics_cost + selected_offer.extra_cost)
            currency = selected_offer.currency or currency

        quality_hints: list[str] = []
        if selection.fallback_used:
            quality_hints.append("fallback_strategy_applied")
        if selected_offer is None:
            quality_hints.append("no_matched_supplier_offer")
        if availability.status in {"preorder", "on_request"}:
            quality_hints.append("extended_fulfillment")
        if availability.status == "low_stock":
            quality_hints.append("low_stock")

        supplier_confidence = self._resolve_supplier_confidence(selection, availability.is_sellable)

        explainability = {
            "selector": selection.explainability,
            "availability": availability.explainability,
        }

        return SellableSnapshot(
            product_id=str(product.id),
            currency=currency,
            current_sell_price=sell_price,
            availability_status=availability.status,
            availability_label=availability.label,
            estimated_delivery_days=availability.estimated_delivery_days,
            procurement_source_summary=availability.procurement_source_summary,
            is_sellable=availability.is_sellable and sell_price > Decimal("0"),
            max_order_quantity=availability.max_order_quantity,
            selected_offer_id=str(selected_offer.id) if selected_offer is not None else None,
            selected_offer_supplier_name=selected_offer.supplier.name if selected_offer is not None else None,
            strategy_requested=selection.requested_strategy,
            strategy_applied=selection.strategy_applied,
            fallback_used=selection.fallback_used,
            selector_reason=selection.reason,
            supplier_confidence=supplier_confidence,
            quality_hints=quality_hints,
            explainability=explainability,
        )

    def _resolve_supplier_confidence(self, selection, is_sellable: bool) -> str:
        offer = selection.selected_offer
        if offer is None:
            return "low"
        if not is_sellable:
            return "low"
        if offer.supplier.is_preferred and offer.stock_qty > 0:
            return "high"
        if offer.stock_qty > 0:
            return "medium"
        return "low"

    def _safe_decimal(self, raw_value: Any) -> Decimal:
        if raw_value in (None, ""):
            return Decimal("0")
        try:
            return Decimal(str(raw_value))
        except (InvalidOperation, TypeError, ValueError):
            return Decimal("0")
