from django.db.models import QuerySet

from apps.vehicles.models import VehicleEngine


def get_vehicle_engines_queryset(*, generation_id: str | None = None) -> QuerySet[VehicleEngine]:
    queryset = VehicleEngine.objects.filter(is_active=True).select_related(
        "generation", "generation__model", "generation__model__make"
    ).order_by("generation__model__make__name", "generation__model__name", "name")
    if generation_id:
        queryset = queryset.filter(generation_id=generation_id)
    return queryset
