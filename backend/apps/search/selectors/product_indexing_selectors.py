from django.db.models import QuerySet

from apps.catalog.models import Product


def get_products_for_indexing(product_ids: list[str] | None = None) -> QuerySet[Product]:
    queryset = Product.objects.filter(is_active=True).select_related("brand", "category", "product_price")
    if product_ids:
        queryset = queryset.filter(id__in=product_ids)
    return queryset
