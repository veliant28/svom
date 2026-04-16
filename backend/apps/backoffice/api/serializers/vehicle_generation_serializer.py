from __future__ import annotations

from rest_framework import serializers

from apps.vehicles.models import VehicleGeneration, VehicleModel
from apps.vehicles.services import normalize_vehicle_name


class BackofficeVehicleGenerationSerializer(serializers.ModelSerializer):
    model = serializers.PrimaryKeyRelatedField(queryset=VehicleModel.objects.select_related("make"))
    model_name = serializers.CharField(source="model.name", read_only=True)
    make_name = serializers.CharField(source="model.make.name", read_only=True)

    class Meta:
        model = VehicleGeneration
        fields = (
            "id",
            "model",
            "model_name",
            "make_name",
            "name",
            "year_start",
            "year_end",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at", "model_name", "make_name")

    def validate_name(self, value: str) -> str:
        normalized = normalize_vehicle_name(value)
        if not normalized:
            raise serializers.ValidationError("Название поколения обязательно.")
        return normalized

    def validate(self, attrs):
        instance: VehicleGeneration | None = getattr(self, "instance", None)

        if "name" in attrs:
            attrs["name"] = normalize_vehicle_name(attrs["name"])

        year_start = attrs.get("year_start", instance.year_start if instance is not None else None)
        year_end = attrs.get("year_end", instance.year_end if instance is not None else None)
        if year_start and year_end and year_end < year_start:
            raise serializers.ValidationError({"year_end": "Год окончания не может быть меньше года начала."})

        return attrs
