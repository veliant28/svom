from django.utils.translation import get_language
from rest_framework import serializers

from apps.marketing.models import HeroSlide


class HeroSlideSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    subtitle = serializers.SerializerMethodField()
    desktop_image_url = serializers.SerializerMethodField()
    mobile_image_url = serializers.SerializerMethodField()

    class Meta:
        model = HeroSlide
        fields = (
            "id",
            "title",
            "subtitle",
            "desktop_image_url",
            "mobile_image_url",
            "cta_url",
            "sort_order",
        )

    def _lang(self) -> str:
        request = self.context.get("request")
        if request is not None:
            return request.GET.get("lang", get_language() or "uk")
        return get_language() or "uk"

    def _localized(self, obj: HeroSlide, prefix: str) -> str:
        lang = self._lang()
        for candidate in (lang, "uk", "en", "ru"):
            value = getattr(obj, f"{prefix}_{candidate}", "")
            if value:
                return value
        return ""

    def get_title(self, obj: HeroSlide) -> str:
        return self._localized(obj, "title")

    def get_subtitle(self, obj: HeroSlide) -> str:
        return self._localized(obj, "subtitle")

    def get_desktop_image_url(self, obj: HeroSlide) -> str:
        request = self.context.get("request")
        if request is None:
            return obj.desktop_image.url
        return request.build_absolute_uri(obj.desktop_image.url)

    def get_mobile_image_url(self, obj: HeroSlide) -> str:
        request = self.context.get("request")
        if request is None:
            return obj.mobile_image.url
        return request.build_absolute_uri(obj.mobile_image.url)
