from __future__ import annotations

from rest_framework import serializers

from apps.seo.models import SeoMetaOverride


class SeoMetaOverrideSerializer(serializers.ModelSerializer):
    class Meta:
        model = SeoMetaOverride
        fields = (
            "id",
            "path",
            "locale",
            "meta_title",
            "meta_description",
            "h1",
            "canonical_url",
            "robots_directive",
            "og_title",
            "og_description",
            "og_image_url",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_path(self, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise serializers.ValidationError("SEO_PATH_REQUIRED")
        if not normalized.startswith("/"):
            raise serializers.ValidationError("SEO_PATH_MUST_START_WITH_SLASH")
        return normalized
