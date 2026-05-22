from __future__ import annotations

from decimal import Decimal
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

from apps.catalog.models import ProductImage
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
    basket_order = _build_basket_order(order=order, webhook_url=webhook_url)

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


def _build_basket_order(*, order: Order, webhook_url: str = "") -> list[dict[str, Any]]:
    basket_order: list[dict[str, Any]] = []
    public_base_url = _extract_public_base_url(webhook_url=webhook_url)

    for item in order.items.all():
        quantity = int(item.quantity or 1)
        if quantity <= 0:
            quantity = 1

        unit_price_minor = amount_to_minor_units(item.unit_price)
        if unit_price_minor < 0:
            unit_price_minor = 0

        row: dict[str, Any] = {
            "name": (str(item.product_name or "").strip() or str(item.product_sku or "").strip() or "Item")[:128],
            "qty": quantity,
            "sum": unit_price_minor,
            "code": str(item.product_sku or "").strip()[:64],
            "tax": [0],
        }
        icon = _resolve_item_icon(item=item, public_base_url=public_base_url)
        if icon:
            row["icon"] = icon

        basket_order.append(row)

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


def _extract_public_base_url(*, webhook_url: str) -> str:
    webhook_url = str(webhook_url or "").strip()
    if not webhook_url:
        return ""
    parsed = urlsplit(webhook_url)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))


def _resolve_item_icon(*, item, public_base_url: str) -> str:
    product = getattr(item, "product", None)
    if product is None:
        return ""

    image_row = (
        ProductImage.objects.filter(product=product)
        .order_by("-is_primary", "sort_order", "id")
        .first()
    )
    if image_row is None:
        return ""

    image = getattr(image_row, "image", None)
    if image:
        image_url = str(getattr(image, "url", "") or "").strip()
        if image_url:
            return _normalize_public_url(raw=image_url, public_base_url=public_base_url)

    remote_url = str(getattr(image_row, "remote_url", "") or "").strip()
    if remote_url:
        return _normalize_public_url(raw=remote_url, public_base_url=public_base_url)

    return ""


def _normalize_public_url(*, raw: str, public_base_url: str) -> str:
    candidate = str(raw or "").strip()
    if not candidate:
        return ""
    parsed = urlsplit(candidate)
    if parsed.scheme and parsed.netloc:
        return candidate
    if not public_base_url:
        return ""
    return urljoin(f"{public_base_url.rstrip('/')}/", candidate.lstrip("/"))
