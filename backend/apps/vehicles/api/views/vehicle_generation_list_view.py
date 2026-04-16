from rest_framework.generics import ListAPIView

from apps.vehicles.api.serializers import VehicleGenerationSerializer
from apps.vehicles.selectors import get_vehicle_generations_queryset


class VehicleGenerationListAPIView(ListAPIView):
    serializer_class = VehicleGenerationSerializer
    pagination_class = None

    def get_queryset(self):
        return get_vehicle_generations_queryset(model_id=self.request.query_params.get("model"))
