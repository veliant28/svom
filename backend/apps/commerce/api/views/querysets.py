from django.db import DatabaseError, OperationalError, ProgrammingError, connection
from django.db.models import Prefetch, QuerySet

from apps.catalog.models import ProductImage
from apps.catalog.services import FitmentFilteringService
from apps.commerce.models import Cart, CartItem, Order, OrderItem, OrderReceipt, WishlistItem
from apps.pricing.models import SupplierOffer


def _product_image_prefetches(*, relation_prefix: str = "product__") -> tuple[Prefetch, Prefetch]:
    primary_images = ProductImage.objects.filter(is_primary=True).order_by("sort_order")
    all_images = ProductImage.objects.order_by("sort_order")
    return (
        Prefetch(f"{relation_prefix}images", queryset=primary_images, to_attr="primary_images"),
        Prefetch(f"{relation_prefix}images", queryset=all_images, to_attr="all_images"),
    )


def _supplier_offer_prefetch(*, relation_prefix: str = "product__") -> Prefetch:
    return Prefetch(
        f"{relation_prefix}supplier_offers",
        queryset=SupplierOffer.objects.select_related("supplier").order_by("supplier__priority", "supplier__name", "id"),
    )


def _has_wishlist_fitment_filter(fitment_params) -> bool:
    if fitment_params is None:
        return False
    return any(
        str(fitment_params.get(key) or "").strip()
        for key in ("fitment", "vehicle_id", "passanger_car_id", "garage_vehicle", "category", "category_id")
    )


def _wishlist_product_queryset(*, fitment_params=None):
    product_queryset = (
        WishlistItem.product.field.related_model.objects.select_related(
            "brand",
            "category",
            "category__parent",
            "category__parent__parent",
            "product_price",
        )
        .prefetch_related(
            *_product_image_prefetches(relation_prefix=""),
            _supplier_offer_prefetch(relation_prefix=""),
        )
    )
    if fitment_params is not None:
        product_queryset, _ = FitmentFilteringService().apply(
            queryset=product_queryset,
            params=fitment_params,
        )
    return product_queryset


def _wishlist_product_prefetch(*, product_queryset) -> Prefetch:
    return Prefetch("product", queryset=product_queryset)


def get_wishlist_items_queryset(*, user_id, fitment_params=None) -> QuerySet[WishlistItem]:
    apply_fitment_filter = _has_wishlist_fitment_filter(fitment_params)
    product_queryset = _wishlist_product_queryset(
        fitment_params=fitment_params if apply_fitment_filter else None,
    )
    queryset = WishlistItem.objects.filter(user_id=user_id)
    if apply_fitment_filter:
        queryset = queryset.filter(product_id__in=product_queryset.values("id"))

    return (
        queryset
        .prefetch_related(_wishlist_product_prefetch(product_queryset=product_queryset))
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
    queryset = (
        Order.objects.filter(user_id=user_id)
        .select_related("payment")
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
            ),
        )
        .order_by("-placed_at")
    )
    if _order_receipt_table_exists():
        queryset = queryset.prefetch_related(
            Prefetch(
                "receipts",
                queryset=OrderReceipt.objects.filter(
                    provider=OrderReceipt.PROVIDER_VCHASNO_KASA,
                    receipt_type=OrderReceipt.TYPE_SALE,
                ).order_by("-updated_at", "-created_at"),
                to_attr="vchasno_receipts",
            ),
        )
    return queryset


def _order_receipt_table_exists() -> bool:
    try:
        return OrderReceipt._meta.db_table in set(connection.introspection.table_names())
    except (DatabaseError, OperationalError, ProgrammingError):
        return False
