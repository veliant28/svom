from __future__ import annotations

from rest_framework import serializers

from apps.marketing.models import FooterSettings
from apps.marketing.services.footer_phone import FOOTER_PHONE_FORMAT_MOBILE, format_footer_phone


class FooterSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = FooterSettings
        fields = (
            "working_hours",
            "phone_format",
            "phone",
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["phone"] = format_footer_phone(str(data.get("phone") or ""), str(data.get("phone_format") or FOOTER_PHONE_FORMAT_MOBILE))
        return data
