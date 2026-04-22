from __future__ import annotations

from rest_framework import serializers

from apps.marketing.models import FooterSettings


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
        return normalized
