from rest_framework.authentication import TokenAuthentication
from rest_framework.generics import RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated

from apps.users.api.serializers import GarageVehicleListSerializer, GarageVehicleUpdateSerializer
from apps.users.selectors import get_garage_vehicles_queryset
from apps.users.services import ensure_primary_garage_vehicle, reassign_primary_after_delete


class GarageVehicleRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    http_method_names = ["get", "patch", "delete"]

    def get_queryset(self):
        return get_garage_vehicles_queryset().filter(user=self.request.user)

    def get_serializer_class(self):
        if self.request.method in ("PATCH", "PUT"):
            return GarageVehicleUpdateSerializer
        return GarageVehicleListSerializer

    def perform_update(self, serializer):
        garage_vehicle = serializer.save()
        ensure_primary_garage_vehicle(garage_vehicle=garage_vehicle)

    def perform_destroy(self, instance):
        user_id = instance.user_id
        instance.delete()
        reassign_primary_after_delete(user_id=user_id)
