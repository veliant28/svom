from __future__ import annotations

from rest_framework import serializers

from apps.marketing.models import FooterSettings
from apps.marketing.services.footer_phone import (
    FOOTER_PHONE_FORMAT_MOBILE,
    FOOTER_PHONE_FORMAT_TOLL_FREE_0800,
    format_footer_phone,
    normalize_footer_phone,
)


class BackofficeFooterSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = FooterSettings
        fields = (
            "working_hours",
            "phone_format",
            "phone",
        )

    def validate_phone_format(self, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized not in {FOOTER_PHONE_FORMAT_MOBILE, FOOTER_PHONE_FORMAT_TOLL_FREE_0800}:
            raise serializers.ValidationError("Unsupported phone format.")
        return normalized

    def validate_working_hours(self, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise serializers.ValidationError("Working hours is required.")
        return normalized

    def validate_phone(self, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise serializers.ValidationError("Phone is required.")
        phone_format = str(self.initial_data.get("phone_format") or getattr(self.instance, "phone_format", FOOTER_PHONE_FORMAT_MOBILE))
        try:
            return normalize_footer_phone(normalized, phone_format)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc))

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["phone"] = format_footer_phone(str(data.get("phone") or ""), str(data.get("phone_format") or FOOTER_PHONE_FORMAT_MOBILE))
        return data
