from __future__ import annotations

import re

from rest_framework import serializers

from apps.seo.models import GoogleEventSetting, GoogleIntegrationSettings


GA4_ID_PATTERN = re.compile(r"^G-[A-Z0-9]+$", re.IGNORECASE)
GTM_ID_PATTERN = re.compile(r"^GTM-[A-Z0-9]+$", re.IGNORECASE)


def _contains_script_tag(value: str) -> bool:
    lowered = str(value or "").lower()
    return "<script" in lowered or "</script" in lowered


class GoogleIntegrationSettingsSerializer(serializers.ModelSerializer):
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
            "updated_at",
        )
        read_only_fields = ("updated_at",)

    def validate_ga4_measurement_id(self, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            return ""
        if not GA4_ID_PATTERN.match(normalized):
            raise serializers.ValidationError("SEO_INVALID_GA4_ID")
        return normalized.upper()

    def validate_gtm_container_id(self, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            return ""
        if not GTM_ID_PATTERN.match(normalized):
            raise serializers.ValidationError("SEO_INVALID_GTM_ID")
        return normalized.upper()

    def validate_search_console_verification_token(self, value: str) -> str:
        normalized = str(value or "").strip()
        if _contains_script_tag(normalized):
            raise serializers.ValidationError("SEO_SCRIPT_TAG_NOT_ALLOWED")
        return normalized

    def validate_google_site_verification_meta(self, value: str) -> str:
        normalized = str(value or "").strip()
        if _contains_script_tag(normalized):
            raise serializers.ValidationError("SEO_SCRIPT_TAG_NOT_ALLOWED")
        return normalized


class GoogleEventSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoogleEventSetting
        fields = (
            "id",
            "event_name",
            "label",
            "is_enabled",
            "description",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "event_name",
            "label",
            "description",
            "updated_at",
        )
