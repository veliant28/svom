from rest_framework import serializers

from apps.vehicles.models import VehicleModification


class VehicleModificationSerializer(serializers.ModelSerializer):
    engine_name = serializers.CharField(source="engine.name", read_only=True)
    model_name = serializers.CharField(source="engine.generation.model.name", read_only=True)
    make_name = serializers.CharField(source="engine.generation.model.make.name", read_only=True)

    class Meta:
        model = VehicleModification
        fields = (
            "id",
            "name",
            "engine",
            "engine_name",
            "model_name",
            "make_name",
            "body_type",
            "transmission",
            "drivetrain",
            "year_start",
            "year_end",
        )
