from __future__ import annotations

from rest_framework import serializers

from apps.catalog.models import Category
from apps.catalog.services import (
    find_category_by_normalized_name,
    generate_unique_category_slug,
    sanitize_category_name,
)


class BackofficeCatalogCategorySerializer(serializers.ModelSerializer):
    parent = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        allow_null=True,
        required=False,
    )
    parent_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Category
        fields = (
            "id",
            "name",
            "name_uk",
            "name_ru",
            "name_en",
            "slug",
            "parent",
            "parent_name",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at", "parent_name")
        extra_kwargs = {
            "slug": {"required": False, "allow_blank": True},
            "description": {"required": False, "allow_blank": True},
            "name_uk": {"required": False, "allow_blank": True},
            "name_ru": {"required": False, "allow_blank": True},
            "name_en": {"required": False, "allow_blank": True},
        }

    def _resolve_locale(self) -> str | None:
        request = self.context.get("request")
        if request is None:
            return None

        locale = (request.query_params.get("locale") or "").strip()
        if locale:
            return locale

        language_code = getattr(request, "LANGUAGE_CODE", "")
        if language_code:
            return str(language_code)

        accept_language = str(request.headers.get("Accept-Language", "")).strip()
        if not accept_language:
            return None
        return accept_language.split(",", 1)[0]

    def get_parent_name(self, obj: Category) -> str:
        if obj.parent:
            return obj.parent.get_localized_name(self._resolve_locale())
        return ""

    def validate_name(self, value: str) -> str:
        cleaned = sanitize_category_name(value)
        if not cleaned:
            raise serializers.ValidationError("Название категории обязательно.")
        return cleaned

    def validate_slug(self, value: str) -> str:
        return (value or "").strip()

    def validate(self, attrs):
        instance: Category | None = getattr(self, "instance", None)
        instance_id = str(instance.id) if instance is not None else None

        for field in ("name_uk", "name_ru", "name_en"):
            if field in attrs:
                attrs[field] = sanitize_category_name(attrs.get(field, ""))

        if "name" in attrs:
            attrs["name"] = sanitize_category_name(attrs["name"])

        if not attrs.get("name"):
            fallback_name = attrs.get("name_uk") or (instance.name_uk if instance is not None else "")
            if fallback_name:
                attrs["name"] = fallback_name

        if not attrs.get("name_uk"):
            fallback_uk = attrs.get("name") or (instance.name if instance is not None else "")
            if fallback_uk:
                attrs["name_uk"] = fallback_uk
        if not attrs.get("name_ru"):
            fallback_ru = attrs.get("name_uk") or attrs.get("name") or (instance.name_ru if instance is not None else "")
            if fallback_ru:
                attrs["name_ru"] = fallback_ru
        if not attrs.get("name_en"):
            fallback_en = attrs.get("name_uk") or attrs.get("name") or (instance.name_en if instance is not None else "")
            if fallback_en:
                attrs["name_en"] = fallback_en

        parent = attrs.get("parent", instance.parent if instance is not None else None)
        name = attrs.get("name", instance.name if instance is not None else "")
        provided_slug = attrs.get("slug", None)

        if instance is not None and parent is not None:
            if str(parent.id) == str(instance.id):
                raise serializers.ValidationError({"parent": "Категория не может быть родителем самой себе."})

            ancestor = parent
            while ancestor is not None:
                if str(ancestor.id) == str(instance.id):
                    raise serializers.ValidationError({"parent": "Нельзя выбрать дочернюю категорию в качестве родителя."})
                ancestor = ancestor.parent

        if name:
            duplicate = find_category_by_normalized_name(
                name=name,
                parent=parent,
                exclude_category_id=instance_id,
            )
            if duplicate is not None:
                raise serializers.ValidationError({"name": "Категория с таким названием уже существует на этом уровне."})

        if provided_slug is not None:
            if not provided_slug:
                attrs["slug"] = generate_unique_category_slug(
                    name=name,
                    exclude_category_id=instance_id,
                )
            else:
                attrs["slug"] = generate_unique_category_slug(
                    name=name,
                    preferred_slug=provided_slug,
                    exclude_category_id=instance_id,
                )

        return attrs

    def create(self, validated_data):
        if not validated_data.get("slug"):
            validated_data["slug"] = generate_unique_category_slug(name=validated_data["name"])
        return super().create(validated_data)
