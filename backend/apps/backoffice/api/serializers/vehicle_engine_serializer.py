from __future__ import annotations

from rest_framework import serializers

from apps.vehicles.models import VehicleEngine, VehicleGeneration
from apps.vehicles.services import normalize_vehicle_name


class BackofficeVehicleEngineSerializer(serializers.ModelSerializer):
    generation = serializers.PrimaryKeyRelatedField(queryset=VehicleGeneration.objects.select_related("model", "model__make"))
    generation_name = serializers.CharField(source="generation.name", read_only=True)
    model_name = serializers.CharField(source="generation.model.name", read_only=True)
    make_name = serializers.CharField(source="generation.model.make.name", read_only=True)

    class Meta:
        model = VehicleEngine
        fields = (
            "id",
            "generation",
            "generation_name",
            "model_name",
            "make_name",
            "name",
            "code",
            "fuel_type",
            "displacement_cc",
            "power_hp",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at", "generation_name", "model_name", "make_name")
        extra_kwargs = {
            "code": {"required": False, "allow_blank": True},
        }

    def validate_name(self, value: str) -> str:
        normalized = normalize_vehicle_name(value)
        if not normalized:
            raise serializers.ValidationError("Название двигателя обязательно.")
        return normalized

    def validate_code(self, value: str) -> str:
        return normalize_vehicle_name(value)

    def validate(self, attrs):
        if "name" in attrs:
            attrs["name"] = normalize_vehicle_name(attrs["name"])
        if "code" in attrs:
            attrs["code"] = normalize_vehicle_name(attrs["code"])
        return attrs
