from django.db.models import QuerySet

from apps.vehicles.models import VehicleModification


def get_vehicle_modifications_queryset(*, engine_id: str | None = None) -> QuerySet[VehicleModification]:
    queryset = VehicleModification.objects.filter(is_active=True).select_related(
        "engine",
        "engine__generation",
        "engine__generation__model",
        "engine__generation__model__make",
    ).order_by("engine__generation__model__make__name", "engine__generation__model__name", "name")
    if engine_id:
        queryset = queryset.filter(engine_id=engine_id)
    return queryset
