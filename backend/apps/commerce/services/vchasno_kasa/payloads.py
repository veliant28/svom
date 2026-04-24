from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from apps.commerce.models import Order, OrderReceipt, VchasnoKasaSettings


def build_vchasno_order_payload(*, order: Order, receipt: OrderReceipt, settings: VchasnoKasaSettings) -> dict:
    total_minor = to_minor_units(order.total)
    rows = []
    for item in order.items.all():
        rows.append(
            {
                "name": item.product_name or item.product_sku or f"Item {item.id}",
                "code": item.product_sku or "",
                "cnt": int(item.quantity or 0),
                "price": to_minor_units(item.unit_price),
                "sum": to_minor_units(item.line_total),
                "taxgrp": (settings.default_tax_group or "").strip(),
                "disc": 0,
            }
        )

    payload: dict = {
        "rro_fn": (settings.rro_fn or "").strip(),
        "order_number": order.order_number,
        "external_order_id": str(receipt.external_order_id),
        "notation": f"SVOM order {order.order_number}",
        "data": {
            "fiscal": {
                "receipt": {
                    "sum": total_minor,
                    "rows": rows,
                    "pays": [
                        {
                            "type": int(settings.default_payment_type or 1),
                            "sum": total_minor,
                            "name": resolve_payment_name(order.payment_method),
                        }
                    ],
                }
            },
            "userinfo": {},
        },
    }

    if settings.send_customer_email and (order.contact_email or "").strip():
        payload["data"]["userinfo"]["email"] = order.contact_email.strip()
    if (order.contact_phone or "").strip():
        payload["data"]["userinfo"]["phone"] = order.contact_phone.strip()
    if not payload["data"]["userinfo"]:
        payload["data"].pop("userinfo", None)
    return payload


def build_vchasno_sync_payload(*, receipt: OrderReceipt) -> dict:
    return {
        "order_number": receipt.vchasno_order_number,
        "external_order_id": str(receipt.external_order_id),
    }


def to_minor_units(value) -> int:
    normalized = Decimal(str(value or "0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int((normalized * Decimal("100")).to_integral_value(rounding=ROUND_HALF_UP))


def resolve_payment_name(payment_method: str) -> str:
    normalized = str(payment_method or "").strip().lower()
    if normalized == Order.PAYMENT_CASH_ON_DELIVERY:
        return "cash_on_delivery"
    if normalized == Order.PAYMENT_MONOBANK:
        return "monobank"
    if normalized == Order.PAYMENT_LIQPAY:
        return "liqpay"
    return normalized or "payment"
