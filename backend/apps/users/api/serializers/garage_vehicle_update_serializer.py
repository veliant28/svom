from rest_framework import serializers

from apps.users.models import GarageVehicle


class GarageVehicleUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = GarageVehicle
        fields = ("is_primary",)

