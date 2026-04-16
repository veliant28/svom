from django.db.models import QuerySet

from apps.vehicles.models import VehicleMake


def get_vehicle_makes_queryset() -> QuerySet[VehicleMake]:
    return VehicleMake.objects.filter(is_active=True).order_by("name")
