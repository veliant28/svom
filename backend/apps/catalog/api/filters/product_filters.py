import django_filters

from apps.catalog.models import Product


class ProductFilterSet(django_filters.FilterSet):
    brand = django_filters.CharFilter(field_name="brand__slug")
    category = django_filters.CharFilter(field_name="category__slug")
    is_featured = django_filters.BooleanFilter(field_name="is_featured")
    is_new = django_filters.BooleanFilter(field_name="is_new")
    is_bestseller = django_filters.BooleanFilter(field_name="is_bestseller")

    min_price = django_filters.NumberFilter(field_name="product_price__final_price", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="product_price__final_price", lookup_expr="lte")

    class Meta:
        model = Product
        fields = (
            "brand",
            "category",
            "is_featured",
            "is_new",
            "is_bestseller",
            "min_price",
            "max_price",
        )
