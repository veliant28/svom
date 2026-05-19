from rest_framework import serializers

from apps.catalog.models import Product
from apps.catalog.services.product_management import get_product_display_name
from apps.catalog.services.product_sku import (
    get_product_catalog_article,
    get_product_display_sku,
    get_product_manufacturer_article,
)


class CommerceProductSummarySerializer(serializers.ModelSerializer):
    sku = serializers.SerializerMethodField()
    article = serializers.SerializerMethodField()
    manufacturer_article = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    brand_name = serializers.SerializerMethodField()
    final_price = serializers.DecimalField(source="product_price.final_price", max_digits=12, decimal_places=2, read_only=True)
    currency = serializers.CharField(source="product_price.currency", read_only=True)
    primary_image = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            "id",
            "sku",
            "article",
            "manufacturer_article",
            "name",
            "slug",
            "brand_name",
            "primary_image",
            "final_price",
            "currency",
        )

    def get_sku(self, obj: Product) -> str:
        return get_product_display_sku(obj)

    def get_article(self, obj: Product) -> str:
        return get_product_catalog_article(obj)

    def get_manufacturer_article(self, obj: Product) -> str:
        return get_product_manufacturer_article(obj)

    def _resolve_locale(self) -> str | None:
        request = self.context.get("request")
        if request is None:
            return None
        language_code = getattr(request, "LANGUAGE_CODE", "")
        if language_code:
            return str(language_code)
        accept_language = str(request.headers.get("Accept-Language", "")).strip()
        if not accept_language:
            return None
        return accept_language.split(",", 1)[0]

    def get_name(self, obj: Product) -> str:
        return get_product_display_name(obj, self._resolve_locale())

    def get_brand_name(self, obj: Product) -> str:
        return str(obj.display_brand_name or obj.autodb_supplier_name or "").strip()

    def get_primary_image(self, obj: Product) -> str:
        request = self.context.get("request")
        primary_row = None
        primary_images = getattr(obj, "primary_images", None)
        if primary_images:
            primary_row = primary_images[0]
        if primary_row is None:
            images = getattr(obj, "all_images", None)
            if images:
                primary_row = images[0]

        if primary_row is None:
            return ""

        image = getattr(primary_row, "image", None)
        if image:
            if request is None:
                return image.url
            return request.build_absolute_uri(image.url)

        remote_url = str(getattr(primary_row, "remote_url", "") or "").strip()
        if remote_url:
            return remote_url
        return ""
