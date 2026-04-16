from django.db.models import QuerySet

from apps.catalog.models import Brand


def get_active_brands_queryset() -> QuerySet[Brand]:
    return Brand.objects.filter(is_active=True).order_by("name")
