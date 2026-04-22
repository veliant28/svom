from __future__ import annotations

from rest_framework import serializers

from apps.marketing.models import FooterSettings


class FooterSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = FooterSettings
        fields = (
            "working_hours",
            "phone",
        )
