from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from apps.commerce.models import Order, OrderItem
from apps.pricing.models import SupplierOffer
from apps.pricing.services import OfferStrategy, ProductSellableSnapshotService


class ProcurementService:
    def __init__(self) -> None:
        self.snapshot_service = ProductSellableSnapshotService()

    def build_item_recommendation(self, item: OrderItem) -> dict:
        effective_offer = item.selected_supplier_offer or item.recommended_supplier_offer

        fallback_snapshot = None
        if effective_offer is None:
            fallback_snapshot = self.snapshot_service.build(
                product=item.product,
                quantity=item.quantity,
                strategy=OfferStrategy.IN_STOCK_FIRST,
            )
            if fallback_snapshot.selected_offer_id:
                effective_offer = SupplierOffer.objects.select_related("supplier").filter(id=fallback_snapshot.selected_offer_id).first()

        can_fulfill = bool(effective_offer and effective_offer.is_available and effective_offer.stock_qty >= item.quantity)
        partially_available = bool(effective_offer and effective_offer.is_available and 0 < effective_offer.stock_qty < item.quantity)

        recommendation_payload = self._offer_payload(effective_offer)

        return {
            "order_item_id": str(item.id),
            "order_id": str(item.order_id),
            "product_id": str(item.product_id),
            "product_name": item.product_name,
            "product_sku": item.product_sku,
            "quantity": item.quantity,
            "current_procurement_status": item.procurement_status,
            "recommended_offer": recommendation_payload,
            "selected_offer_id": str(item.selected_supplier_offer_id) if item.selected_supplier_offer_id else None,
            "can_fulfill": can_fulfill,
            "partially_available": partially_available,
            "fallback_used": fallback_snapshot is not None,
            "availability_status": item.snapshot_availability_status,
            "availability_label": item.snapshot_availability_label,
            "eta_days": item.snapshot_estimated_delivery_days,
            "issues": self._issue_flags(item=item, can_fulfill=can_fulfill, partially_available=partially_available),
        }

    def build_grouped_suggestions(self, orders: Iterable[Order]) -> dict:
        grouped: dict[str, dict] = defaultdict(
            lambda: {
                "supplier_id": None,
                "supplier_code": "",
                "supplier_name": "Unassigned",
                "items": [],
                "items_count": 0,
                "total_quantity": 0,
            }
        )

        for order in orders:
            for item in order.items.all():
                recommendation = self.build_item_recommendation(item)
                offer = recommendation["recommended_offer"]
                supplier_id = offer.get("supplier_id") or "unassigned"

                bucket = grouped[supplier_id]
                bucket["supplier_id"] = offer.get("supplier_id")
                bucket["supplier_code"] = offer.get("supplier_code", "")
                bucket["supplier_name"] = offer.get("supplier_name") or "Unassigned"
                bucket["items"].append(
                    {
                        "order_id": str(order.id),
                        "order_number": order.order_number,
                        **recommendation,
                    }
                )
                bucket["items_count"] += 1
                bucket["total_quantity"] += item.quantity

        return {
            "groups": sorted(grouped.values(), key=lambda row: (row["supplier_name"], row["supplier_id"] or "")),
            "groups_count": len(grouped),
            "items_count": sum(group["items_count"] for group in grouped.values()),
        }

    def _offer_payload(self, offer: SupplierOffer | None) -> dict:
        if offer is None:
            return {
                "offer_id": None,
                "supplier_id": None,
                "supplier_code": "",
                "supplier_name": "",
                "supplier_sku": "",
                "purchase_price": None,
                "currency": "",
                "stock_qty": 0,
                "lead_time_days": None,
                "is_available": False,
            }

        return {
            "offer_id": str(offer.id),
            "supplier_id": str(offer.supplier_id),
            "supplier_code": offer.supplier.code,
            "supplier_name": offer.supplier.name,
            "supplier_sku": offer.supplier_sku,
            "purchase_price": str(offer.purchase_price),
            "currency": offer.currency,
            "stock_qty": offer.stock_qty,
            "lead_time_days": offer.lead_time_days,
            "is_available": offer.is_available,
        }

    def _issue_flags(self, *, item: OrderItem, can_fulfill: bool, partially_available: bool) -> list[str]:
        issues: list[str] = []
        if not can_fulfill:
            issues.append("cannot_fulfill")
        if partially_available:
            issues.append("partial_stock")
        if item.shortage_reason_code:
            issues.append(item.shortage_reason_code)
        if item.snapshot_availability_status in {"out_of_stock", "on_request", "preorder"}:
            issues.append(item.snapshot_availability_status)
        return sorted(set(issues))
