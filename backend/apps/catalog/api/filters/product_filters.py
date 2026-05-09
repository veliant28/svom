import django_filters

from apps.catalog.models import Category, Product


class ProductFilterSet(django_filters.FilterSet):
    brand = django_filters.CharFilter(field_name="brand__slug")
    category = django_filters.CharFilter(method="filter_category")
    category_id = django_filters.UUIDFilter(method="filter_category_id")
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
            "category_id",
            "is_featured",
            "is_new",
            "is_bestseller",
            "min_price",
            "max_price",
        )

    def filter_category(self, queryset, name, value):
        category = Category.objects.filter(slug=str(value or "").strip()).first()
        return self._filter_category_with_descendants(queryset, category)

    def filter_category_id(self, queryset, name, value):
        category = Category.objects.filter(id=value).first()
        return self._filter_category_with_descendants(queryset, category)

    def _filter_category_with_descendants(self, queryset, category: Category | None):
        if category is None:
            return queryset.none()
        category_ids = self._collect_category_descendant_ids(category)
        return queryset.filter(category_id__in=category_ids)

    def _collect_category_descendant_ids(self, category: Category) -> set:
        child_map: dict[object, list[object]] = {}
        for category_id, parent_id in Category.objects.filter(is_active=True).values_list("id", "parent_id"):
            if parent_id is None:
                continue
            child_map.setdefault(parent_id, []).append(category_id)

        collected = {category.id}
        queue = [category.id]
        while queue:
            parent_id = queue.pop(0)
            for child_id in child_map.get(parent_id, []):
                if child_id in collected:
                    continue
                collected.add(child_id)
                queue.append(child_id)
        return collected
