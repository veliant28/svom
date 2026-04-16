from rest_framework import serializers

from apps.catalog.models import Product


class CommerceProductSummarySerializer(serializers.ModelSerializer):
    brand_name = serializers.CharField(source="brand.name", read_only=True)
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

    def get_primary_image(self, obj: Product) -> str:
        request = self.context.get("request")

        primary_images = getattr(obj, "primary_images", None)
        image = primary_images[0].image if primary_images else None
        if image is None:
            images = getattr(obj, "all_images", None)
            if images:
                image = images[0].image

        if not image:
            return ""

        if request is None:
            return image.url
        return request.build_absolute_uri(image.url)
