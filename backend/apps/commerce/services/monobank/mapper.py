from __future__ import annotations

from decimal import Decimal
from typing import Any

from apps.commerce.models import Order


CCY_BY_CURRENCY = {
    "UAH": 980,
    "USD": 840,
    "EUR": 978,
}


def amount_to_minor_units(value: Decimal) -> int:
    quantized = Decimal(value).quantize(Decimal("0.01"))
    return int(quantized * Decimal("100"))


def resolve_ccy(currency: str) -> int:
    normalized = (currency or "UAH").upper()
    return CCY_BY_CURRENCY.get(normalized, 980)


def build_invoice_create_payload(
    *,
    order: Order,
    webhook_url: str,
    redirect_url: str = "",
) -> dict[str, Any]:
    basket_order = _build_basket_order(order=order)

    payload: dict[str, Any] = {
        "amount": amount_to_minor_units(order.total),
        "ccy": resolve_ccy(order.currency),
        "merchantPaymInfo": {
            "reference": order.order_number,
            "destination": f"Order {order.order_number}",
            "comment": order.customer_comment or f"Order {order.order_number}",
            "basketOrder": basket_order,
        },
        "webHookUrl": webhook_url,
        "paymentType": "debit",
    }

    if redirect_url:
        payload["redirectUrl"] = redirect_url

    return payload


def _build_basket_order(*, order: Order) -> list[dict[str, Any]]:
    basket_order: list[dict[str, Any]] = []

    for item in order.items.all():
        quantity = int(item.quantity or 1)
        if quantity <= 0:
            quantity = 1

        unit_price_minor = amount_to_minor_units(item.unit_price)
        if unit_price_minor < 0:
            unit_price_minor = 0

        basket_order.append(
            {
                "name": (str(item.product_name or "").strip() or str(item.product_sku or "").strip() or "Item")[:128],
                "qty": quantity,
                "sum": unit_price_minor,
                "code": str(item.product_sku or "").strip()[:64],
                "tax": [0],
            }
        )

    if basket_order:
        return basket_order

    # Required by Monobank for fiscalization/split payments: basketOrder must be non-empty.
    return [
        {
            "name": f"Order {order.order_number}"[:128],
            "qty": 1,
            "sum": amount_to_minor_units(order.total),
            "code": str(order.order_number or "").strip()[:64],
            "tax": [0],
        }
    ]
