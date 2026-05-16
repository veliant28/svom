from __future__ import annotations

from rest_framework import serializers

from apps.marketing.models import FooterSettings
from apps.marketing.services.footer_phone import format_footer_phone, normalize_footer_phone


class BackofficeFooterSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = FooterSettings
        fields = (
            "working_hours",
            "phone",
        )

    def validate_working_hours(self, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise serializers.ValidationError("Working hours is required.")
        return normalized

    def validate_phone(self, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise serializers.ValidationError("Phone is required.")
        try:
            return normalize_footer_phone(normalized)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc))

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["phone"] = format_footer_phone(str(data.get("phone") or ""))
        return data
