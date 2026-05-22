from __future__ import annotations

from django.db.models import Prefetch, Q, QuerySet

from apps.commerce.models import ReturnRequest, ReturnRequestItem


RETURN_ITEM_PREFETCH = Prefetch(
    "items",
    queryset=ReturnRequestItem.objects.select_related(
        "product",
        "order_item",
        "order_item__selected_supplier_offer",
        "order_item__selected_supplier_offer__supplier",
        "order_item__snapshot_selected_offer",
        "order_item__snapshot_selected_offer__supplier",
    ),
)


def get_operational_returns_queryset() -> QuerySet[ReturnRequest]:
    return (
        ReturnRequest.objects.select_related("order", "user")
        .prefetch_related(RETURN_ITEM_PREFETCH, "events", "events__actor")
        .order_by("-created_at")
    )


def apply_operational_return_filters(queryset: QuerySet[ReturnRequest], *, params) -> QuerySet[ReturnRequest]:
    status_value = str(params.get("status", "") or "").strip()
    query = str(params.get("q", "") or "").strip()

    if status_value:
        if status_value == ReturnRequest.STATUS_ACCEPTED:
            queryset = queryset.filter(status__in=[ReturnRequest.STATUS_ACCEPTED, ReturnRequest.STATUS_RECEIVED])
        elif status_value == "refund":
            queryset = queryset.filter(status=ReturnRequest.STATUS_REFUNDED)
        else:
            queryset = queryset.filter(status=status_value)

    if query:
        queryset = queryset.filter(
            Q(return_number__icontains=query)
            | Q(order__order_number__icontains=query)
            | Q(order__contact_full_name__icontains=query)
            | Q(order__contact_phone__icontains=query)
            | Q(order__contact_email__icontains=query)
            | Q(customer_return_tracking_number__icontains=query)
            | Q(items__product_sku_snapshot__icontains=query)
            | Q(items__product_name_snapshot__icontains=query)
        )

    return queryset.distinct()
