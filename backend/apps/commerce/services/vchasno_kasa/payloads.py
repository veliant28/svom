from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from apps.commerce.models import Order, OrderReceipt, VchasnoKasaSettings
from .exceptions import VchasnoKasaConfigError

VCHASNO_PAYMENT_METHOD_CODES = (
    "0",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "8",
    "11",
    "12",
    "13",
    "14",
    "15",
    "16",
    "17",
    "18",
    "19",
    "20",
)
VCHASNO_TAX_GROUP_CODES = (
    "А",
    "В",
    "З",
    "Б",
    "Е",
    "ИК",
    "ГД",
    "Ж",
    "Л",
)
VCHASNO_PAYMENT_METHOD_CODE_SET = set(VCHASNO_PAYMENT_METHOD_CODES)
VCHASNO_TAX_GROUP_CODE_SET = set(VCHASNO_TAX_GROUP_CODES)


def build_vchasno_order_payload(*, order: Order, receipt: OrderReceipt, settings: VchasnoKasaSettings) -> dict:
    selected_payment_methods = get_selected_payment_methods(settings=settings)
    if not selected_payment_methods:
        raise VchasnoKasaConfigError(
            "Оберіть хоча б один засіб оплати каси Вчасно.Каса",
            code="VCHASNO_KASA_PAYMENT_METHODS_REQUIRED",
        )
    selected_tax_groups = get_selected_tax_groups(settings=settings)
    if not selected_tax_groups:
        raise VchasnoKasaConfigError(
            "Оберіть хоча б одну податкову групу каси Вчасно.Каса",
            code="VCHASNO_KASA_TAX_GROUPS_REQUIRED",
        )

    default_tax_group = selected_tax_groups[0]
    total_minor = to_minor_units(order.total)
    pays = build_pays_payload(selected_payment_methods=selected_payment_methods, total_minor=total_minor, order=order)
    rows = []
    for item in order.items.all():
        rows.append(
            {
                "name": item.product_name or item.product_sku or f"Item {item.id}",
                "code": item.product_sku or "",
                "cnt": int(item.quantity or 0),
                "price": to_minor_units(item.unit_price),
                "sum": to_minor_units(item.line_total),
                "taxgrp": default_tax_group,
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
                    "pays": pays,
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
    # /api/v1/orders/list rejects order_number/external_order_id as unknown fields.
    # Fetch the latest page and match by order identifiers on the application side.
    return {}


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
    if normalized == "novapay":
        return "novapay"
    return normalized or "payment"


def build_pays_payload(*, selected_payment_methods: list[str], total_minor: int, order: Order) -> list[dict[str, Any]]:
    ordered_codes = reorder_payment_method_codes_for_order(
        selected_payment_methods=selected_payment_methods,
        payment_method=order.payment_method,
    )
    pays: list[dict[str, Any]] = []
    for index, code in enumerate(ordered_codes):
        pay_sum = total_minor if index == 0 else 0
        pay_name = resolve_payment_name(order.payment_method) if index == 0 else f"payment_{code}"
        pays.append(
            {
                "type": int(code),
                "sum": int(pay_sum),
                "name": pay_name,
            }
        )
    return pays


def reorder_payment_method_codes_for_order(*, selected_payment_methods: list[str], payment_method: str) -> list[str]:
    if not selected_payment_methods:
        return []
    primary_code = resolve_primary_payment_method_code(
        selected_payment_methods=selected_payment_methods,
        payment_method=payment_method,
    )
    if primary_code is None:
        return selected_payment_methods
    return [primary_code, *[code for code in selected_payment_methods if code != primary_code]]


def resolve_primary_payment_method_code(*, selected_payment_methods: list[str], payment_method: str) -> str | None:
    normalized = str(payment_method or "").strip().lower()
    preferred_codes = payment_method_preferred_codes(normalized)
    for code in preferred_codes:
        if code in selected_payment_methods:
            return code
    return selected_payment_methods[0] if selected_payment_methods else None


def payment_method_preferred_codes(payment_method: str) -> tuple[str, ...]:
    if payment_method == Order.PAYMENT_CASH_ON_DELIVERY:
        return ("4", "0", "1")
    if payment_method == Order.PAYMENT_MONOBANK:
        return ("16", "2", "1")
    if payment_method == Order.PAYMENT_LIQPAY:
        return ("17", "16", "2", "1")
    if payment_method == "novapay":
        return ("20", "16", "2", "1")
    if payment_method == Order.PAYMENT_CARD_PLACEHOLDER:
        return ("2", "16", "1")
    return ()


def get_selected_payment_methods(*, settings: VchasnoKasaSettings) -> list[str]:
    return normalize_payment_method_codes(getattr(settings, "selected_payment_methods", []))


def get_selected_tax_groups(*, settings: VchasnoKasaSettings) -> list[str]:
    return normalize_tax_group_codes(getattr(settings, "selected_tax_groups", []))


def normalize_payment_method_codes(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        if item is None:
            continue
        code = str(item).strip()
        if not code:
            continue
        if code.isdigit():
            code = str(int(code))
        if code not in VCHASNO_PAYMENT_METHOD_CODE_SET or code in seen:
            continue
        seen.add(code)
        normalized.append(code)
    return normalized


def normalize_tax_group_codes(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        if item is None:
            continue
        code = str(item).strip().upper()
        if not code:
            continue
        if code not in VCHASNO_TAX_GROUP_CODE_SET or code in seen:
            continue
        seen.add(code)
        normalized.append(code)
    return normalized
