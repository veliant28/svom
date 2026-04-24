from __future__ import annotations

from rest_framework import serializers

from apps.seo.api.serializers.google_settings_serializer import GoogleEventSettingSerializer
from apps.seo.api.serializers.meta_override_serializer import SeoMetaOverrideSerializer
from apps.seo.api.serializers.meta_template_serializer import SeoMetaTemplateSerializer
from apps.seo.models import GoogleIntegrationSettings, SeoSiteSettings
from apps.seo.services import normalize_locale, resolve_seo_meta


class SeoPublicSiteSettingsSerializer(serializers.ModelSerializer):
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
            "robots_txt",
        )


class SeoPublicGoogleSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoogleIntegrationSettings
        fields = (
            "is_enabled",
            "ga4_measurement_id",
            "gtm_container_id",
            "search_console_verification_token",
            "google_site_verification_meta",
            "consent_mode_enabled",
            "ecommerce_events_enabled",
            "debug_mode",
            "anonymize_ip",
        )


class SeoResolvedMetaSerializer(serializers.Serializer):
    meta_title = serializers.CharField(allow_blank=True)
    meta_description = serializers.CharField(allow_blank=True)
    h1 = serializers.CharField(allow_blank=True)
    canonical_url = serializers.CharField(allow_blank=True)
    robots_directive = serializers.CharField(allow_blank=True)
    og_title = serializers.CharField(allow_blank=True)
    og_description = serializers.CharField(allow_blank=True)
    og_image_url = serializers.CharField(allow_blank=True)
    source = serializers.CharField()


class SeoPublicConfigSerializer(serializers.Serializer):
    settings = SeoPublicSiteSettingsSerializer()
    google = SeoPublicGoogleSettingsSerializer()
    events = GoogleEventSettingSerializer(many=True)
    templates = SeoMetaTemplateSerializer(many=True)
    overrides = SeoMetaOverrideSerializer(many=True)


class SeoResolveMetaInputSerializer(serializers.Serializer):
    path = serializers.CharField()
    locale = serializers.CharField(required=False, allow_blank=True)
    entity_type = serializers.CharField(required=False, allow_blank=True, default="page")
    context = serializers.JSONField(required=False)

    def validate_path(self, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized.startswith("/"):
            return f"/{normalized}"
        return normalized

    def validate_locale(self, value: str) -> str:
        return normalize_locale(value)

    def create(self, validated_data):
        return validated_data

    def to_resolved_payload(self) -> dict:
        return resolve_seo_meta(
            path=self.validated_data["path"],
            locale=self.validated_data.get("locale", "uk"),
            entity_type=self.validated_data.get("entity_type") or "page",
            context=self.validated_data.get("context") or {},
        ).__dict__
