from rest_framework import serializers

from apps.vehicles.models import VehicleGeneration


class VehicleGenerationSerializer(serializers.ModelSerializer):
    model_name = serializers.CharField(source="model.name", read_only=True)
    make_name = serializers.CharField(source="model.make.name", read_only=True)

    class Meta:
        model = VehicleGeneration
        fields = (
            "id",
            "name",
            "model",
            "model_name",
            "make_name",
            "year_start",
            "year_end",
        )
