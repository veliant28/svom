from rest_framework.generics import ListAPIView

from apps.vehicles.api.serializers import VehicleModelSerializer
from apps.vehicles.selectors import get_vehicle_models_queryset


class VehicleModelListAPIView(ListAPIView):
    serializer_class = VehicleModelSerializer
    pagination_class = None

    def get_queryset(self):
        return get_vehicle_models_queryset(make_id=self.request.query_params.get("make"))
