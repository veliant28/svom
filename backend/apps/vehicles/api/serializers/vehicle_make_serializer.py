from rest_framework import serializers

from apps.vehicles.models import VehicleMake


class VehicleMakeSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleMake
        fields = ("id", "name", "slug")
