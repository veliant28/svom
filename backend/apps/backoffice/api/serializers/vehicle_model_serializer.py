from __future__ import annotations

from rest_framework import serializers

from apps.vehicles.models import VehicleMake, VehicleModel
from apps.vehicles.services import generate_unique_model_slug, normalize_vehicle_name


class BackofficeVehicleModelSerializer(serializers.ModelSerializer):
    make = serializers.PrimaryKeyRelatedField(queryset=VehicleMake.objects.all())
    make_name = serializers.CharField(source="make.name", read_only=True)

    class Meta:
        model = VehicleModel
        fields = (
            "id",
            "make",
            "make_name",
            "name",
            "slug",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at", "make_name")
        extra_kwargs = {
            "slug": {"required": False, "allow_blank": True},
        }

    def validate_name(self, value: str) -> str:
        normalized = normalize_vehicle_name(value)
        if not normalized:
            raise serializers.ValidationError("Название модели обязательно.")
        return normalized

    def validate_slug(self, value: str) -> str:
        return (value or "").strip()

    def validate(self, attrs):
        instance: VehicleModel | None = getattr(self, "instance", None)
        instance_id = str(instance.id) if instance is not None else None

        if "name" in attrs:
            attrs["name"] = normalize_vehicle_name(attrs["name"])

        make = attrs.get("make") or (instance.make if instance is not None else None)
        name = attrs.get("name") or (instance.name if instance is not None else "")
        if make is None:
            raise serializers.ValidationError({"make": "Выберите марку."})

        provided_slug = attrs.get("slug", None)
        if provided_slug is not None:
            attrs["slug"] = generate_unique_model_slug(
                make=make,
                name=name,
                preferred_slug=provided_slug,
                exclude_model_id=instance_id,
            )

        return attrs

    def create(self, validated_data):
        if not validated_data.get("slug"):
            validated_data["slug"] = generate_unique_model_slug(
                make=validated_data["make"],
                name=validated_data["name"],
            )
        return super().create(validated_data)
