from __future__ import annotations

from rest_framework import serializers

from apps.vehicles.models import VehicleEngine, VehicleModification
from apps.vehicles.services import normalize_vehicle_name


class BackofficeVehicleModificationSerializer(serializers.ModelSerializer):
    engine = serializers.PrimaryKeyRelatedField(queryset=VehicleEngine.objects.select_related("generation", "generation__model", "generation__model__make"))
    engine_name = serializers.CharField(source="engine.name", read_only=True)
    generation_name = serializers.CharField(source="engine.generation.name", read_only=True)
    model_name = serializers.CharField(source="engine.generation.model.name", read_only=True)
    make_name = serializers.CharField(source="engine.generation.model.make.name", read_only=True)

    class Meta:
        model = VehicleModification
        fields = (
            "id",
            "engine",
            "engine_name",
            "generation_name",
            "model_name",
            "make_name",
            "name",
            "body_type",
            "transmission",
            "drivetrain",
            "year_start",
            "year_end",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "engine_name",
            "generation_name",
            "model_name",
            "make_name",
        )
        extra_kwargs = {
            "body_type": {"required": False, "allow_blank": True},
            "transmission": {"required": False, "allow_blank": True},
            "drivetrain": {"required": False, "allow_blank": True},
        }

    def validate_name(self, value: str) -> str:
        normalized = normalize_vehicle_name(value)
        if not normalized:
            raise serializers.ValidationError("Название модификации обязательно.")
        return normalized

    def validate(self, attrs):
        instance: VehicleModification | None = getattr(self, "instance", None)

        for field in ("name", "body_type", "transmission", "drivetrain"):
            if field in attrs:
                attrs[field] = normalize_vehicle_name(attrs[field])

        year_start = attrs.get("year_start", instance.year_start if instance is not None else None)
        year_end = attrs.get("year_end", instance.year_end if instance is not None else None)
        if year_start and year_end and year_end < year_start:
            raise serializers.ValidationError({"year_end": "Год окончания не может быть меньше года начала."})

        return attrs
