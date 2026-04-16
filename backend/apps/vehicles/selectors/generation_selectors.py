from django.db.models import QuerySet

from apps.vehicles.models import VehicleGeneration


def get_vehicle_generations_queryset(*, model_id: str | None = None) -> QuerySet[VehicleGeneration]:
    queryset = VehicleGeneration.objects.filter(is_active=True).select_related("model", "model__make").order_by(
        "model__make__name", "model__name", "-year_start"
    )
    if model_id:
        queryset = queryset.filter(model_id=model_id)
    return queryset
