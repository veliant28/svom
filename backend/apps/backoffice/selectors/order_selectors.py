from __future__ import annotations

from django.db.models import Prefetch, Q, QuerySet

from apps.commerce.models import Order, OrderItem, OrderNovaPoshtaWaybill
from apps.pricing.models import SupplierOffer


WAYBILL_PREFETCH = Prefetch(
    "nova_poshta_waybills",
    queryset=OrderNovaPoshtaWaybill.objects.select_related("sender_profile").filter(is_deleted=False).order_by("-created_at"),
    to_attr="backoffice_active_waybills",
)


ITEM_PREFETCH = Prefetch(
    "items",
    queryset=OrderItem.objects.select_related(
        "product",
        "recommended_supplier_offer",
        "recommended_supplier_offer__supplier",
        "selected_supplier_offer",
        "selected_supplier_offer__supplier",
        "snapshot_selected_offer",
        "snapshot_selected_offer__supplier",
    ).order_by("created_at"),
)


def get_operational_orders_queryset() -> QuerySet[Order]:
    return (
        Order.objects.select_related("user")
         .prefetch_related(ITEM_PREFETCH, WAYBILL_PREFETCH)
        .order_by("-placed_at", "-created_at")
    )


def apply_operational_order_filters(queryset: QuerySet[Order], *, params) -> QuerySet[Order]:
    status_value = params.get("status", "").strip()
    has_issues = params.get("has_issues", "").strip().lower()
    query = params.get("q", "").strip()

    if status_value:
        queryset = queryset.filter(status=status_value)

    if has_issues in {"1", "true", "yes"}:
        queryset = queryset.filter(
            Q(items__procurement_status=OrderItem.PROCUREMENT_UNAVAILABLE)
            | Q(items__procurement_status=OrderItem.PROCUREMENT_PARTIALLY_RESERVED)
            | Q(items__shortage_reason_code__gt="")
        )

    if query:
        queryset = queryset.filter(
            Q(order_number__icontains=query)
            | Q(contact_full_name__icontains=query)
            | Q(contact_phone__icontains=query)
            | Q(contact_email__icontains=query)
            | Q(user__email__icontains=query)
            | Q(items__product_sku__icontains=query)
            | Q(items__product_name__icontains=query)
        )

    return queryset.distinct()


def get_procurement_supplier_offers_queryset() -> QuerySet[SupplierOffer]:
    return SupplierOffer.objects.select_related("supplier", "product", "product__brand").order_by(
        "supplier__priority",
        "supplier__name",
        "id",
    )
