from __future__ import annotations

from rest_framework import serializers

from apps.vehicles.models import VehicleMake
from apps.vehicles.services import generate_unique_make_slug, normalize_vehicle_name


class BackofficeVehicleMakeSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleMake
        fields = (
            "id",
            "name",
            "slug",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")
        extra_kwargs = {
            "slug": {"required": False, "allow_blank": True},
        }

    def validate_name(self, value: str) -> str:
        normalized = normalize_vehicle_name(value)
        if not normalized:
            raise serializers.ValidationError("Название марки обязательно.")
        return normalized

    def validate_slug(self, value: str) -> str:
        return (value or "").strip()

    def validate(self, attrs):
        instance: VehicleMake | None = getattr(self, "instance", None)
        instance_id = str(instance.id) if instance is not None else None

        if "name" in attrs:
            attrs["name"] = normalize_vehicle_name(attrs["name"])

        name = attrs.get("name") or (instance.name if instance is not None else "")
        provided_slug = attrs.get("slug", None)
        if provided_slug is not None:
            attrs["slug"] = generate_unique_make_slug(
                name=name,
                preferred_slug=provided_slug,
                exclude_make_id=instance_id,
            )

        return attrs

    def create(self, validated_data):
        if not validated_data.get("slug"):
            validated_data["slug"] = generate_unique_make_slug(name=validated_data["name"])
        return super().create(validated_data)
