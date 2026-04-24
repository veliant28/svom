from __future__ import annotations

from rest_framework import serializers

from apps.seo.models import SeoSiteSettings


class SeoSiteSettingsSerializer(serializers.ModelSerializer):
    canonical_base_url = serializers.URLField(required=False, allow_blank=True)

    class Meta:
        model = SeoSiteSettings
        fields = (
            "is_enabled",
            "default_meta_title_uk",
            "default_meta_title_ru",
            "default_meta_title_en",
            "default_meta_description_uk",
            "default_meta_description_ru",
            "default_meta_description_en",
            "default_og_title_uk",
            "default_og_title_ru",
            "default_og_title_en",
            "default_og_description_uk",
            "default_og_description_ru",
            "default_og_description_en",
            "default_robots_directive",
            "canonical_base_url",
            "sitemap_enabled",
            "product_sitemap_enabled",
            "category_sitemap_enabled",
            "brand_sitemap_enabled",
            "sitemap_last_rebuild_at",
            "robots_txt",
            "updated_at",
        )
        read_only_fields = ("sitemap_last_rebuild_at", "updated_at")

    def validate_default_robots_directive(self, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            return "index,follow"
        return normalized
