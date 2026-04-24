from __future__ import annotations

from urllib.parse import urlparse

from rest_framework import serializers

from apps.marketing.models import HeroSlide, HeroSliderSettings


HERO_BLOCK_EFFECT_CHOICES = (
    "crossfade",
    "pan_left",
    "lift_up",
    "cinematic_zoom",
    "reveal_right",
)


class BackofficeHeroBlockSettingsSerializer(serializers.ModelSerializer):
    transition_effect = serializers.ChoiceField(choices=HERO_BLOCK_EFFECT_CHOICES)

    class Meta:
        model = HeroSliderSettings
        fields = (
            "autoplay_enabled",
            "transition_interval_ms",
            "transition_speed_ms",
            "transition_effect",
            "max_active_slides",
        )

    def validate_transition_interval_ms(self, value: int) -> int:
        normalized = int(value or 0)
        if normalized < 1000 or normalized > 60000:
            raise serializers.ValidationError("Transition interval must be between 1000 and 60000 ms.")
        return normalized

    def validate_transition_speed_ms(self, value: int) -> int:
        normalized = int(value or 0)
        if normalized < 150 or normalized > 10000:
            raise serializers.ValidationError("Transition speed must be between 150 and 10000 ms.")
        return normalized

    def validate_max_active_slides(self, value: int) -> int:
        normalized = int(value or 0)
        if normalized < 1 or normalized > 10:
            raise serializers.ValidationError("Maximum active slides must be between 1 and 10.")
        return normalized


class BackofficeHeroSlideSerializer(serializers.ModelSerializer):
    desktop_image_url = serializers.SerializerMethodField(read_only=True)
    mobile_image_url = serializers.SerializerMethodField(read_only=True)
    cta_url = serializers.CharField(required=False, allow_blank=True, max_length=500)

    class Meta:
        model = HeroSlide
        fields = (
            "id",
            "title_uk",
            "title_ru",
            "title_en",
            "subtitle_uk",
            "subtitle_ru",
            "subtitle_en",
            "desktop_image",
            "desktop_image_url",
            "mobile_image",
            "mobile_image_url",
            "cta_url",
            "sort_order",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
        )

    def get_desktop_image_url(self, obj: HeroSlide) -> str:
        if not obj.desktop_image:
            return ""
        request = self.context.get("request")
        if request is None:
            return obj.desktop_image.url
        return request.build_absolute_uri(obj.desktop_image.url)

    def get_mobile_image_url(self, obj: HeroSlide) -> str:
        if not obj.mobile_image:
            return ""
        request = self.context.get("request")
        if request is None:
            return obj.mobile_image.url
        return request.build_absolute_uri(obj.mobile_image.url)

    def validate_cta_url(self, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            return ""
        if normalized.startswith("/"):
            return normalized
        parsed = urlparse(normalized)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            return normalized
        raise serializers.ValidationError("Use absolute URL (http/https) or internal path starting with '/'.")

    def validate(self, attrs):
        titles = [
            str(attrs.get("title_uk", getattr(self.instance, "title_uk", "")) or "").strip(),
            str(attrs.get("title_ru", getattr(self.instance, "title_ru", "")) or "").strip(),
            str(attrs.get("title_en", getattr(self.instance, "title_en", "")) or "").strip(),
        ]
        if not any(titles):
            raise serializers.ValidationError({"title_uk": "At least one localized title is required."})
        return attrs
