from django.db.models import Case, IntegerField, Prefetch, QuerySet, Sum, When

from apps.catalog.models import Product, ProductImage
from apps.pricing.models import SupplierOffer


def with_available_stock_qty(queryset: QuerySet[Product]) -> QuerySet[Product]:
    return queryset.annotate(
        available_stock_qty=Sum(
            Case(
                When(
                    supplier_offers__is_available=True,
                    supplier_offers__stock_qty__gt=0,
                    then="supplier_offers__stock_qty",
                ),
                default=0,
                output_field=IntegerField(),
            ),
            default=0,
        )
    )


def get_public_products_queryset() -> QuerySet[Product]:
    primary_images = ProductImage.objects.filter(is_primary=True).order_by("sort_order")
    all_images = ProductImage.objects.order_by("sort_order")
    supplier_offers = SupplierOffer.objects.select_related("supplier").order_by("supplier__priority", "supplier__name", "id")
    return (
        Product.objects.filter(is_active=True)
        .select_related("category", "category__parent", "category__parent__parent", "product_price")
        .prefetch_related(
            Prefetch("images", queryset=primary_images, to_attr="primary_images"),
            Prefetch("images", queryset=all_images, to_attr="all_images"),
            Prefetch("supplier_offers", queryset=supplier_offers),
        )
        .order_by("name", "id")
    )


def get_product_detail_queryset() -> QuerySet[Product]:
    supplier_offers = SupplierOffer.objects.select_related("supplier").order_by("supplier__priority", "supplier__name", "id")

    return (
        Product.objects.filter(is_active=True)
        .select_related("category", "category__parent", "category__parent__parent", "product_price")
        .prefetch_related(
            "images",
            "product_attributes__attribute",
            "product_attributes__attribute_value",
            Prefetch("supplier_offers", queryset=supplier_offers),
        )
    )
