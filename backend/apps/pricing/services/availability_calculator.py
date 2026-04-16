from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from apps.catalog.models import Product
from apps.pricing.services.selector.types import OfferSelectionResult
from django.utils.translation import gettext_lazy as _


class AvailabilityStatus:
    IN_STOCK = "in_stock"
    LOW_STOCK = "low_stock"
    SUPPLIER_STOCK = "supplier_stock"
    OUT_OF_STOCK = "out_of_stock"
    PREORDER = "preorder"
    ON_REQUEST = "on_request"


AVAILABILITY_LABELS = {
    AvailabilityStatus.IN_STOCK: _("In stock"),
    AvailabilityStatus.LOW_STOCK: _("Low stock"),
    AvailabilityStatus.SUPPLIER_STOCK: _("Supplier stock"),
    AvailabilityStatus.OUT_OF_STOCK: _("Out of stock"),
    AvailabilityStatus.PREORDER: _("Preorder"),
    AvailabilityStatus.ON_REQUEST: _("On request"),
}


@dataclass(frozen=True)
class AvailabilityResult:
    status: str
    label: str
    estimated_delivery_days: int | None
    procurement_source_summary: str
    is_sellable: bool
    max_order_quantity: int | None
    explainability: dict


class AvailabilityCalculator:
    LOW_STOCK_THRESHOLD = 3
    SUPPLIER_STOCK_MAX_LEAD_DAYS = 7

    def calculate(
        self,
        *,
        product: Product,
        selection: OfferSelectionResult,
        requested_quantity: int = 1,
    ) -> AvailabilityResult:
        requested_quantity = max(requested_quantity, 1)
        offer = selection.selected_offer

        if offer is None:
            product_price = getattr(product, "product_price", None)
            has_price = self._has_positive_price(product_price)
            if has_price:
                status = AvailabilityStatus.ON_REQUEST
                return AvailabilityResult(
                    status=status,
                    label=AVAILABILITY_LABELS[status],
                    estimated_delivery_days=None,
                    procurement_source_summary=_("Available on request from partner suppliers"),
                    is_sellable=True,
                    max_order_quantity=None,
                    explainability={
                        "decision": "fallback_without_offer",
                        "reason": "No matched supplier offer, but product has active sell price.",
                    },
                )

            status = AvailabilityStatus.OUT_OF_STOCK
            return AvailabilityResult(
                status=status,
                label=AVAILABILITY_LABELS[status],
                estimated_delivery_days=None,
                procurement_source_summary=_("Currently unavailable"),
                is_sellable=False,
                max_order_quantity=0,
                explainability={
                    "decision": "no_offer_no_price",
                    "reason": "No matched supplier offer and no sell price.",
                },
            )

        stock_qty = max(int(offer.stock_qty), 0)
        lead_time_days = max(int(offer.lead_time_days), 0)

        if stock_qty >= requested_quantity and lead_time_days <= 1:
            status = AvailabilityStatus.IN_STOCK if stock_qty > self.LOW_STOCK_THRESHOLD else AvailabilityStatus.LOW_STOCK
            eta_days = 1
            is_sellable = True
        elif stock_qty > 0 and lead_time_days <= self.SUPPLIER_STOCK_MAX_LEAD_DAYS:
            status = AvailabilityStatus.SUPPLIER_STOCK
            eta_days = max(lead_time_days, 1)
            is_sellable = True
        elif stock_qty > 0:
            status = AvailabilityStatus.PREORDER
            eta_days = max(lead_time_days, self.SUPPLIER_STOCK_MAX_LEAD_DAYS + 1)
            is_sellable = True
        elif lead_time_days > 0:
            if lead_time_days > self.SUPPLIER_STOCK_MAX_LEAD_DAYS:
                status = AvailabilityStatus.PREORDER
            else:
                status = AvailabilityStatus.ON_REQUEST
            eta_days = lead_time_days
            is_sellable = True
        else:
            status = AvailabilityStatus.OUT_OF_STOCK
            eta_days = None
            is_sellable = False

        source_summary = self._source_summary_for_status(status)
        max_order_quantity = stock_qty if stock_qty > 0 else None

        return AvailabilityResult(
            status=status,
            label=AVAILABILITY_LABELS[status],
            estimated_delivery_days=eta_days,
            procurement_source_summary=source_summary,
            is_sellable=is_sellable,
            max_order_quantity=max_order_quantity,
            explainability={
                "decision": "supplier_offer_based",
                "stock_qty": stock_qty,
                "lead_time_days": lead_time_days,
                "requested_quantity": requested_quantity,
            },
        )

    def _has_positive_price(self, product_price) -> bool:
        if not product_price:
            return False
        raw_value = getattr(product_price, "final_price", None)
        if raw_value in (None, ""):
            return False
        try:
            return Decimal(str(raw_value)) > Decimal("0")
        except (InvalidOperation, TypeError, ValueError):
            return False

    def _source_summary_for_status(self, status: str) -> str:
        if status == AvailabilityStatus.IN_STOCK:
            return str(_("Ready from local warehouse"))
        if status == AvailabilityStatus.LOW_STOCK:
            return str(_("Limited warehouse stock"))
        if status == AvailabilityStatus.SUPPLIER_STOCK:
            return str(_("Available from supplier stock"))
        if status == AvailabilityStatus.PREORDER:
            return str(_("Procured by preorder"))
        if status == AvailabilityStatus.ON_REQUEST:
            return str(_("Supplied on request"))
        return str(_("Currently unavailable"))
