from rest_framework import serializers

from apps.vehicles.models import VehicleModel


class VehicleModelSerializer(serializers.ModelSerializer):
    make_name = serializers.CharField(source="make.name", read_only=True)

    class Meta:
        model = VehicleModel
        fields = ("id", "name", "slug", "make", "make_name")
