from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from apps.commerce.models import CartItem
from apps.commerce.services.sellable_state import get_cart_item_sellable_snapshot

MONEY_PRECISION = Decimal("0.01")


@dataclass(frozen=True)
class CartTotals:
    items_count: int
    subtotal: Decimal


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_PRECISION, rounding=ROUND_HALF_UP)


def get_product_unit_price(item: CartItem) -> Decimal:
    snapshot = get_cart_item_sellable_snapshot(item)
    return quantize_money(Decimal(snapshot.current_sell_price))


def get_line_total(item: CartItem) -> Decimal:
    return quantize_money(get_product_unit_price(item) * Decimal(item.quantity))


def calculate_cart_totals(items: list[CartItem]) -> CartTotals:
    items_count = sum(item.quantity for item in items)
    subtotal = quantize_money(sum((get_line_total(item) for item in items), Decimal("0.00")))
    return CartTotals(items_count=items_count, subtotal=subtotal)
