from __future__ import annotations

from urllib.parse import urlparse

from rest_framework import serializers

from apps.marketing.models import PromoBanner, PromoBannerSettings


PROMO_BANNER_EFFECT_CHOICES = (
    "fade",
    "slide_left",
    "slide_up",
    "blinds_vertical",
    "zoom_in",
)


class BackofficePromoBannerSettingsSerializer(serializers.ModelSerializer):
    transition_effect = serializers.ChoiceField(choices=PROMO_BANNER_EFFECT_CHOICES)

    class Meta:
        model = PromoBannerSettings
        fields = (
            "autoplay_enabled",
            "transition_interval_ms",
            "transition_speed_ms",
            "transition_effect",
            "max_active_banners",
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

    def validate_max_active_banners(self, value: int) -> int:
        normalized = int(value or 0)
        if normalized < 1 or normalized > 10:
            raise serializers.ValidationError("Maximum active banners must be between 1 and 10.")
        return normalized


class BackofficePromoBannerSerializer(serializers.ModelSerializer):
    title = serializers.CharField(required=False, allow_blank=False, max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, max_length=500)
    image_url = serializers.SerializerMethodField(read_only=True)
    target_url = serializers.CharField(required=False, allow_blank=True, max_length=500)

    class Meta:
        model = PromoBanner
        fields = (
            "id",
            "title",
            "description",
            "image",
            "image_url",
            "target_url",
            "sort_order",
            "is_active",
            "starts_at",
            "ends_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
        )

    def get_image_url(self, obj: PromoBanner) -> str:
        if not obj.image:
            return ""
        request = self.context.get("request")
        if request is None:
            return obj.image.url
        return request.build_absolute_uri(obj.image.url)

    def to_representation(self, instance: PromoBanner):
        payload = super().to_representation(instance)
        payload["title"] = instance.title_uk or instance.title_ru or instance.title_en or ""
        payload["description"] = instance.description_uk or instance.description_ru or instance.description_en or ""
        return payload

    def validate_target_url(self, value: str) -> str:
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
        starts_at = attrs.get("starts_at", getattr(self.instance, "starts_at", None))
        ends_at = attrs.get("ends_at", getattr(self.instance, "ends_at", None))
        if starts_at is not None and ends_at is not None and ends_at <= starts_at:
            raise serializers.ValidationError({"ends_at": "End datetime must be later than start datetime."})
        return attrs

    def create(self, validated_data):
        title = str(validated_data.pop("title", "")).strip()
        description = str(validated_data.pop("description", "")).strip()
        if not title:
            raise serializers.ValidationError({"title": "Title is required."})
        validated_data["title_uk"] = title
        validated_data["title_ru"] = title
        validated_data["title_en"] = title
        validated_data["description_uk"] = description
        validated_data["description_ru"] = description
        validated_data["description_en"] = description
        return super().create(validated_data)

    def update(self, instance, validated_data):
        title = validated_data.pop("title", serializers.empty)
        description = validated_data.pop("description", serializers.empty)

        if title is not serializers.empty:
            normalized_title = str(title or "").strip()
            if not normalized_title:
                raise serializers.ValidationError({"title": "Title is required."})
            validated_data["title_uk"] = normalized_title
            validated_data["title_ru"] = normalized_title
            validated_data["title_en"] = normalized_title

        if description is not serializers.empty:
            normalized_description = str(description or "").strip()
            validated_data["description_uk"] = normalized_description
            validated_data["description_ru"] = normalized_description
            validated_data["description_en"] = normalized_description

        return super().update(instance, validated_data)
