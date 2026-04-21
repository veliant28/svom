from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model

from apps.catalog.models import Product
from apps.commerce.models import Cart, CartItem, Order, OrderItem, WishlistItem

User = get_user_model()


def seed_commerce_demo(*, products: list[Product]) -> dict[str, int]:
    demo_user, _ = User.objects.get_or_create(
        email="demo@svom.local",
        defaults={
            "is_active": True,
            "first_name": "Demo",
            "last_name": "User",
        },
    )

    wishlist_count = _seed_wishlist(demo_user=demo_user, products=products)
    cart_count = _seed_cart(demo_user=demo_user, products=products)
    orders_count, order_items_count = _seed_orders(demo_user=demo_user, products=products)

    return {
        "wishlist_items": wishlist_count,
        "cart_items": cart_count,
        "orders": orders_count,
        "order_items": order_items_count,
    }


def _seed_wishlist(*, demo_user: User, products: list[Product]) -> int:
    WishlistItem.objects.filter(user=demo_user).exclude(product_id__in=[product.id for product in products[:2]]).delete()

    count = 0
    for product in products[:2]:
        WishlistItem.objects.get_or_create(user=demo_user, product=product)
        count += 1
    return count


def _seed_cart(*, demo_user: User, products: list[Product]) -> int:
    cart, _ = Cart.objects.get_or_create(user=demo_user)

    selected_products = products[:2]
    selected_product_ids = [product.id for product in selected_products]
    cart.items.exclude(product_id__in=selected_product_ids).delete()

    count = 0
    for index, product in enumerate(selected_products, start=1):
        CartItem.objects.update_or_create(
            cart=cart,
            product=product,
            defaults={"quantity": index},
        )
        count += 1

    return count


def _seed_orders(*, demo_user: User, products: list[Product]) -> tuple[int, int]:
    selected_products = products[:2]
    if not selected_products:
        return 0, 0

    order, _ = Order.objects.update_or_create(
        order_number="DEMO-ORDER-001",
        defaults={
            "user": demo_user,
            "status": Order.STATUS_CONFIRMED,
            "contact_full_name": "Demo User",
            "contact_phone": "+380001112233",
            "contact_email": demo_user.email,
            "delivery_method": Order.DELIVERY_PICKUP,
            "delivery_address": "",
            "payment_method": Order.PAYMENT_CASH_ON_DELIVERY,
            "currency": "UAH",
            "customer_comment": "Seeded demo order",
            "subtotal": Decimal("0.00"),
            "delivery_fee": Decimal("0.00"),
            "total": Decimal("0.00"),
        },
    )

    order.items.all().delete()

    subtotal = Decimal("0.00")
    order_items_count = 0

    for index, product in enumerate(selected_products, start=1):
        unit_price = _resolve_product_price(product)
        quantity = index
        line_total = unit_price * Decimal(quantity)
        subtotal += line_total

        OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            product_sku=product.sku,
            quantity=quantity,
            unit_price=unit_price,
            line_total=line_total,
        )
        order_items_count += 1

    order.subtotal = subtotal
    order.delivery_fee = Decimal("0.00")
    order.total = subtotal
    order.save(update_fields=("subtotal", "delivery_fee", "total", "updated_at"))

    return 1, order_items_count


def _resolve_product_price(product: Product) -> Decimal:
    if hasattr(product, "product_price") and product.product_price is not None:
        return Decimal(product.product_price.final_price)

    product_price = getattr(product, "product_price", None)
    if product_price is not None:
        return Decimal(product_price.final_price)

    return Decimal("0.00")
