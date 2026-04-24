from rest_framework import serializers

from apps.marketing.models import HeroSliderSettings


class HeroSliderPublicSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = HeroSliderSettings
        fields = (
            "autoplay_enabled",
            "transition_interval_ms",
            "transition_speed_ms",
            "transition_effect",
            "max_active_slides",
        )
