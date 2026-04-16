from __future__ import annotations

from django.db import transaction

from apps.catalog.models import Product
from apps.commerce.models import Cart, CartItem
from apps.commerce.services.sellable_state import get_product_sellable_snapshot
from apps.users.models import User


def get_or_create_user_cart(user: User) -> Cart:
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


@transaction.atomic
def add_product_to_cart(*, user: User, product: Product, quantity: int = 1) -> CartItem:
    cart = get_or_create_user_cart(user)
    item, created = CartItem.objects.select_for_update().get_or_create(
        cart=cart,
        product=product,
        defaults={"quantity": max(quantity, 1)},
    )
    if not created:
        item.quantity += max(quantity, 1)
    _refresh_item_last_known_state(item)
    return item


@transaction.atomic
def set_cart_item_quantity(*, item: CartItem, quantity: int) -> CartItem:
    if quantity <= 0:
        item.delete()
        return item

    item.quantity = quantity
    _refresh_item_last_known_state(item)
    return item


@transaction.atomic
def remove_cart_item(*, item: CartItem) -> None:
    item.delete()


def _refresh_item_last_known_state(item: CartItem) -> None:
    snapshot = get_product_sellable_snapshot(product=item.product, quantity=item.quantity)
    setattr(item, "_sellable_snapshot", snapshot)
    item.last_known_unit_price = snapshot.current_sell_price
    item.last_known_currency = snapshot.currency
    item.last_known_availability_status = snapshot.availability_status
    item.last_known_estimated_delivery_days = snapshot.estimated_delivery_days
    item.save(
        update_fields=(
            "quantity",
            "last_known_unit_price",
            "last_known_currency",
            "last_known_availability_status",
            "last_known_estimated_delivery_days",
            "updated_at",
        )
    )
