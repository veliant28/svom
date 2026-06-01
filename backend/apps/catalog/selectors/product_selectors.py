from django.db.models import Case, IntegerField, Prefetch, QuerySet, Sum, When

from apps.catalog.models import Product, ProductImage
from apps.catalog.models.autodb_product_link_quality import AutoDbProductLinkQuality
from apps.pricing.models import SupplierOffer
from apps.supplier_imports.models import SupplierRawOffer


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
    link_qualities = AutoDbProductLinkQuality.objects.only(
        "id",
        "product_id",
        "autodb_article_key",
        "status",
        "checked_at",
        "updated_at",
    ).order_by("-checked_at", "-updated_at")
    return (
        Product.objects.filter(is_active=True)
        .select_related("category", "category__parent", "category__parent__parent", "product_price")
        .prefetch_related(
            Prefetch("images", queryset=primary_images, to_attr="primary_images"),
            Prefetch("images", queryset=all_images, to_attr="all_images"),
            Prefetch("supplier_offers", queryset=supplier_offers),
            Prefetch("autodb_link_qualities", queryset=link_qualities),
        )
        .order_by("name", "id")
    )


def get_product_detail_queryset() -> QuerySet[Product]:
    supplier_offers = SupplierOffer.objects.select_related("supplier").order_by("supplier__priority", "supplier__name", "id")
    raw_supplier_offers = (
        SupplierRawOffer.objects.select_related("supplier", "source")
        .only(
            "id",
            "matched_product_id",
            "supplier_id",
            "source_id",
            "external_sku",
            "article",
            "brand_name",
            "raw_payload",
            "updated_at",
        )
        .order_by("-updated_at", "-id")
    )
    link_qualities = AutoDbProductLinkQuality.objects.only(
        "id",
        "product_id",
        "autodb_article_key",
        "status",
        "checked_at",
        "updated_at",
    ).order_by("-checked_at", "-updated_at")

    return (
        Product.objects.filter(is_active=True)
        .select_related("category", "category__parent", "category__parent__parent", "product_price")
        .prefetch_related(
            "images",
            Prefetch("supplier_offers", queryset=supplier_offers),
            Prefetch("raw_supplier_offers", queryset=raw_supplier_offers),
            Prefetch("autodb_link_qualities", queryset=link_qualities),
        )
    )
