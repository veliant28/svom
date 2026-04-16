from django.db.models import QuerySet

from apps.catalog.models import Category


def get_active_categories_queryset() -> QuerySet[Category]:
    return Category.objects.filter(is_active=True).select_related("parent").order_by("name")
