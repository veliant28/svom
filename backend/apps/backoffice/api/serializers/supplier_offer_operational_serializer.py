from rest_framework import serializers

from apps.pricing.models import SupplierOffer


class SupplierOfferOperationalSerializer(serializers.ModelSerializer):
    supplier_code = serializers.CharField(source="supplier.code", read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    product_id = serializers.CharField(source="product.id", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    product_article = serializers.CharField(source="product.article", read_only=True)
    brand_name = serializers.CharField(source="product.brand.name", read_only=True)

    class Meta:
        model = SupplierOffer
        fields = (
            "id",
            "supplier",
            "supplier_code",
            "supplier_name",
            "supplier_sku",
            "product_id",
            "product_name",
            "product_sku",
            "product_article",
            "brand_name",
            "currency",
            "purchase_price",
            "logistics_cost",
            "extra_cost",
            "stock_qty",
            "lead_time_days",
            "is_available",
            "created_at",
            "updated_at",
        )
