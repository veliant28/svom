from rest_framework.generics import ListAPIView

from apps.vehicles.api.serializers import VehicleEngineSerializer
from apps.vehicles.selectors import get_vehicle_engines_queryset


class VehicleEngineListAPIView(ListAPIView):
    serializer_class = VehicleEngineSerializer
    pagination_class = None

    def get_queryset(self):
        return get_vehicle_engines_queryset(generation_id=self.request.query_params.get("generation"))
