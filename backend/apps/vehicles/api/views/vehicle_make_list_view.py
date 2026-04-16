from rest_framework.generics import ListAPIView

from apps.vehicles.api.serializers import VehicleMakeSerializer
from apps.vehicles.selectors import get_vehicle_makes_queryset


class VehicleMakeListAPIView(ListAPIView):
    serializer_class = VehicleMakeSerializer
    pagination_class = None

    def get_queryset(self):
        return get_vehicle_makes_queryset()
