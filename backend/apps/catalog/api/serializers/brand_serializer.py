from rest_framework import serializers

from apps.catalog.models import Brand


class BrandListSerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()

    class Meta:
        model = Brand
        fields = ("id", "name", "slug", "logo_url")

    def get_logo_url(self, obj: Brand) -> str:
        request = self.context.get("request")
        if not obj.logo:
            return ""
        if request is None:
            return obj.logo.url
        return request.build_absolute_uri(obj.logo.url)
