from django.db.models import QuerySet
from django.db import OperationalError, ProgrammingError

from apps.catalog.models import Brand


def get_active_brands_queryset() -> QuerySet[Brand]:
    try:
        return Brand.objects.filter(is_active=True).order_by("name")
    except (OperationalError, ProgrammingError):
        return Brand.objects.none()
