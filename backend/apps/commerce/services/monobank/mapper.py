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
    payload: dict[str, Any] = {
        "amount": amount_to_minor_units(order.total),
        "ccy": resolve_ccy(order.currency),
        "merchantPaymInfo": {
            "reference": order.order_number,
            "destination": f"Order {order.order_number}",
            "comment": order.customer_comment or f"Order {order.order_number}",
        },
        "webHookUrl": webhook_url,
        "paymentType": "debit",
    }

    if redirect_url:
        payload["redirectUrl"] = redirect_url

    return payload
