from rest_framework.generics import ListCreateAPIView
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated

from apps.users.api.serializers import GarageVehicleCreateSerializer, GarageVehicleListSerializer
from apps.users.selectors import get_garage_vehicles_queryset
from apps.users.services import ensure_primary_garage_vehicle


class GarageVehicleListCreateAPIView(ListCreateAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_serializer_class(self):
        if self.request.method == "POST":
            return GarageVehicleCreateSerializer
        return GarageVehicleListSerializer

    def get_queryset(self):
        return get_garage_vehicles_queryset().filter(user=self.request.user)

    def perform_create(self, serializer):
        garage_vehicle = serializer.save()
        ensure_primary_garage_vehicle(garage_vehicle=garage_vehicle)
