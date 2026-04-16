from django.db.models import Prefetch, QuerySet

from apps.catalog.models import ProductImage
from apps.commerce.models import Cart, CartItem, Order, OrderItem, WishlistItem
from apps.pricing.models import SupplierOffer


def _product_image_prefetches() -> tuple[Prefetch, Prefetch]:
    primary_images = ProductImage.objects.filter(is_primary=True).order_by("sort_order")
    all_images = ProductImage.objects.order_by("sort_order")
    return (
        Prefetch("product__images", queryset=primary_images, to_attr="primary_images"),
        Prefetch("product__images", queryset=all_images, to_attr="all_images"),
    )


def _supplier_offer_prefetch() -> Prefetch:
    return Prefetch(
        "product__supplier_offers",
        queryset=SupplierOffer.objects.select_related("supplier").order_by("supplier__priority", "supplier__name", "id"),
    )


def get_wishlist_items_queryset(*, user_id) -> QuerySet[WishlistItem]:
    image_prefetches = _product_image_prefetches()
    supplier_offer_prefetch = _supplier_offer_prefetch()
    return (
        WishlistItem.objects.filter(user_id=user_id)
        .select_related("product", "product__brand", "product__product_price")
        .prefetch_related(*image_prefetches, supplier_offer_prefetch)
        .order_by("-created_at")
    )


def get_cart_queryset(*, user_id) -> QuerySet[Cart]:
    image_prefetches = _product_image_prefetches()
    supplier_offer_prefetch = _supplier_offer_prefetch()
    return (
        Cart.objects.filter(user_id=user_id)
        .prefetch_related(
            Prefetch(
                "items",
                queryset=(
                    CartItem.objects.select_related(
                        "product",
                        "product__brand",
                        "product__product_price",
                    ).prefetch_related(*image_prefetches, supplier_offer_prefetch)
                ),
            )
        )
    )


def get_orders_queryset(*, user_id) -> QuerySet[Order]:
    image_prefetches = _product_image_prefetches()
    supplier_offer_prefetch = _supplier_offer_prefetch()
    return (
        Order.objects.filter(user_id=user_id)
        .prefetch_related(
            Prefetch(
                "items",
                queryset=(
                    OrderItem.objects.select_related(
                        "product",
                        "product__brand",
                        "product__product_price",
                    ).prefetch_related(*image_prefetches, supplier_offer_prefetch)
                ),
            )
        )
        .order_by("-placed_at")
    )
