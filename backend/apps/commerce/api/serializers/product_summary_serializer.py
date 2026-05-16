from rest_framework import serializers

from apps.catalog.models import Product
from apps.catalog.services.product_sku import get_product_display_sku


class CommerceProductSummarySerializer(serializers.ModelSerializer):
    sku = serializers.SerializerMethodField()
    brand_name = serializers.SerializerMethodField()
    final_price = serializers.DecimalField(source="product_price.final_price", max_digits=12, decimal_places=2, read_only=True)
    currency = serializers.CharField(source="product_price.currency", read_only=True)
    primary_image = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            "id",
            "sku",
            "name",
            "slug",
            "brand_name",
            "primary_image",
            "final_price",
            "currency",
        )

    def get_sku(self, obj: Product) -> str:
        return get_product_display_sku(obj)

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
