from __future__ import annotations

from decimal import Decimal

from apps.catalog.models import Product
from apps.commerce.models import CartItem
from apps.pricing.services import ProductSellableSnapshotService, SellableSnapshot
from django.utils.translation import gettext_lazy as _

_snapshot_service = ProductSellableSnapshotService()


def get_product_sellable_snapshot(*, product: Product, quantity: int = 1) -> SellableSnapshot:
    return _snapshot_service.build(product=product, quantity=quantity)


def get_cart_item_sellable_snapshot(item: CartItem) -> SellableSnapshot:
    cached = getattr(item, "_sellable_snapshot", None)
    if cached is not None:
        return cached

    snapshot = _snapshot_service.build(product=item.product, quantity=item.quantity)
    setattr(item, "_sellable_snapshot", snapshot)
    return snapshot


def build_cart_item_warning(item: CartItem, snapshot: SellableSnapshot) -> str:
    if not snapshot.is_sellable:
        return str(_("Item is currently unavailable for checkout."))

    if item.last_known_availability_status and item.last_known_availability_status != snapshot.availability_status:
        return str(_("Availability changed since item was added to cart."))

    if item.last_known_unit_price and Decimal(item.last_known_unit_price) != snapshot.current_sell_price:
        return str(_("Price changed since item was added to cart."))

    if snapshot.max_order_quantity is not None and item.quantity > snapshot.max_order_quantity:
        return str(_("Requested quantity exceeds available supplier stock."))

    return ""
