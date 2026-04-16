from rest_framework import serializers

from apps.pricing.models import ProductPrice


class ProductPriceOperationalSerializer(serializers.ModelSerializer):
    product_id = serializers.CharField(source="product.id", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    product_article = serializers.CharField(source="product.article", read_only=True)
    brand_name = serializers.CharField(source="product.brand.name", read_only=True)
    category_name = serializers.CharField(source="product.category.name", read_only=True)
    policy_name = serializers.CharField(source="policy.name", read_only=True)

    class Meta:
        model = ProductPrice
        fields = (
            "id",
            "product_id",
            "product_name",
            "product_sku",
            "product_article",
            "brand_name",
            "category_name",
            "currency",
            "purchase_price",
            "logistics_cost",
            "extra_cost",
            "landed_cost",
            "raw_sale_price",
            "final_price",
            "policy",
            "policy_name",
            "auto_calculation_locked",
            "recalculated_at",
            "updated_at",
        )
