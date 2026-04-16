from django.utils.translation import get_language
from rest_framework import serializers

from apps.marketing.models import PromoBanner


class PromoBannerSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = PromoBanner
        fields = (
            "id",
            "title",
            "description",
            "image_url",
            "target_url",
            "sort_order",
        )

    def _lang(self) -> str:
        request = self.context.get("request")
        if request is not None:
            return request.GET.get("lang", get_language() or "uk")
        return get_language() or "uk"

    def get_title(self, obj: PromoBanner) -> str:
        lang = self._lang()
        return getattr(obj, f"title_{lang}", "") or obj.title_uk

    def get_description(self, obj: PromoBanner) -> str:
        lang = self._lang()
        return getattr(obj, f"description_{lang}", "") or obj.description_uk

    def get_image_url(self, obj: PromoBanner) -> str:
        request = self.context.get("request")
        if request is None:
            return obj.image.url
        return request.build_absolute_uri(obj.image.url)
