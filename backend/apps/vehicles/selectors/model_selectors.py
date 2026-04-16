from django.db.models import QuerySet

from apps.vehicles.models import VehicleModel


def get_vehicle_models_queryset(*, make_id: str | None = None) -> QuerySet[VehicleModel]:
    queryset = VehicleModel.objects.filter(is_active=True).select_related("make").order_by("make__name", "name")
    if make_id:
        queryset = queryset.filter(make_id=make_id)
    return queryset
