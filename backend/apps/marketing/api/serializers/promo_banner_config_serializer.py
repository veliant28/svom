from __future__ import annotations

from rest_framework import serializers

from apps.marketing.models import PromoBannerSettings


class PromoBannerPublicSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = PromoBannerSettings
        fields = (
            "autoplay_enabled",
            "transition_interval_ms",
            "transition_speed_ms",
            "transition_effect",
            "max_active_banners",
        )

