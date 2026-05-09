from rest_framework import serializers

from apps.catalog.models import Brand, Category
from apps.catalog.services.product_branding import get_product_display_brand_payload


class ProductBrandSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = Brand
        fields = ("id", "name", "slug")

    def get_name(self, obj: Brand) -> str:
        product = self.context.get("product")
        if product is None:
            return str(getattr(obj, "name", "") or "")
        payload = get_product_display_brand_payload(product)
        return payload.display_brand or str(getattr(obj, "name", "") or "")


class ProductCategorySerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ("id", "name", "slug")

    def _resolve_locale(self) -> str | None:
        request = self.context.get("request")
        if request is None:
            return None

        locale = (request.query_params.get("locale") or "").strip()
        if locale:
            return locale

        language_code = getattr(request, "LANGUAGE_CODE", "")
        if language_code:
            return str(language_code)

        accept_language = str(request.headers.get("Accept-Language", "")).strip()
        if not accept_language:
            return None
        return accept_language.split(",", 1)[0]

    def get_name(self, obj: Category) -> str:
        return obj.get_localized_name(self._resolve_locale())
