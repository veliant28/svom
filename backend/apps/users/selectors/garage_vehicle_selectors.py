from django.db.models import QuerySet

from apps.users.models import GarageVehicle


def get_garage_vehicles_queryset() -> QuerySet[GarageVehicle]:
    return GarageVehicle.objects.select_related("user").order_by("-is_primary", "-created_at")
