from rest_framework import serializers

from apps.vehicles.models import VehicleEngine


class VehicleEngineSerializer(serializers.ModelSerializer):
    generation_name = serializers.CharField(source="generation.name", read_only=True)
    model_name = serializers.CharField(source="generation.model.name", read_only=True)

    class Meta:
        model = VehicleEngine
        fields = (
            "id",
            "name",
            "code",
            "generation",
            "generation_name",
            "model_name",
            "fuel_type",
            "displacement_cc",
            "power_hp",
        )
