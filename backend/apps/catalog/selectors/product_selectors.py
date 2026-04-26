from django.db.models import Prefetch, QuerySet

from apps.catalog.models import Product, ProductImage
from apps.compatibility.models import ProductFitment
from apps.pricing.models import SupplierOffer


def get_public_products_queryset() -> QuerySet[Product]:
    primary_images = ProductImage.objects.filter(is_primary=True).order_by("sort_order")
    all_images = ProductImage.objects.order_by("sort_order")
    supplier_offers = SupplierOffer.objects.select_related("supplier").order_by("supplier__priority", "supplier__name", "id")
    return (
        Product.objects.filter(is_active=True)
        .select_related("brand", "category", "category__parent", "category__parent__parent", "product_price")
        .prefetch_related(
            Prefetch("images", queryset=primary_images, to_attr="primary_images"),
            Prefetch("images", queryset=all_images, to_attr="all_images"),
            Prefetch("supplier_offers", queryset=supplier_offers),
        )
        .order_by("name")
    )


def get_product_detail_queryset() -> QuerySet[Product]:
    fitments_queryset = ProductFitment.objects.select_related(
        "modification",
        "modification__engine",
        "modification__engine__generation",
        "modification__engine__generation__model",
        "modification__engine__generation__model__make",
    )

    supplier_offers = SupplierOffer.objects.select_related("supplier").order_by("supplier__priority", "supplier__name", "id")

    return (
        Product.objects.filter(is_active=True)
        .select_related("brand", "category", "category__parent", "category__parent__parent", "product_price", "utr_enrichment")
        .prefetch_related(
            "images",
            "product_attributes__attribute",
            "product_attributes__attribute_value",
            Prefetch("fitments", queryset=fitments_queryset),
            Prefetch("supplier_offers", queryset=supplier_offers),
        )
    )
