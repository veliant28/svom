from rest_framework.generics import ListAPIView

from apps.vehicles.api.serializers import VehicleModificationSerializer
from apps.vehicles.selectors import get_vehicle_modifications_queryset


class VehicleModificationListAPIView(ListAPIView):
    serializer_class = VehicleModificationSerializer
    pagination_class = None

    def get_queryset(self):
        return get_vehicle_modifications_queryset(engine_id=self.request.query_params.get("engine"))
