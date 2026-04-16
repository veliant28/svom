from __future__ import annotations

from rest_framework import serializers

from apps.catalog.models import Brand
from apps.catalog.services import (
    find_brand_by_normalized_name,
    generate_unique_brand_slug,
    sanitize_brand_name,
)


class BackofficeCatalogBrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = (
            "id",
            "name",
            "slug",
            "country",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")
        extra_kwargs = {
            "slug": {"required": False, "allow_blank": True},
            "country": {"required": False, "allow_blank": True},
            "description": {"required": False, "allow_blank": True},
        }

    def validate_name(self, value: str) -> str:
        cleaned = sanitize_brand_name(value)
        if not cleaned:
            raise serializers.ValidationError("Название бренда обязательно.")
        return cleaned

    def validate_slug(self, value: str) -> str:
        return (value or "").strip()

    def validate_country(self, value: str) -> str:
        return sanitize_brand_name(value)

    def validate(self, attrs):
        instance: Brand | None = getattr(self, "instance", None)
        instance_id = str(instance.id) if instance is not None else None

        if "name" in attrs:
            duplicate = find_brand_by_normalized_name(name=attrs["name"], exclude_brand_id=instance_id)
            if duplicate is not None:
                raise serializers.ValidationError({"name": "Бренд с таким названием уже существует."})

        name_for_slug = attrs.get("name") or (instance.name if instance is not None else "")
        provided_slug = attrs.get("slug", "")
        if "slug" in attrs and not provided_slug:
            attrs["slug"] = generate_unique_brand_slug(
                name=name_for_slug,
                exclude_brand_id=instance_id,
            )
        elif "slug" in attrs and provided_slug:
            attrs["slug"] = generate_unique_brand_slug(
                name=name_for_slug,
                preferred_slug=provided_slug,
                exclude_brand_id=instance_id,
            )

        return attrs

    def create(self, validated_data):
        if not validated_data.get("slug"):
            validated_data["slug"] = generate_unique_brand_slug(name=validated_data["name"])
        return super().create(validated_data)
