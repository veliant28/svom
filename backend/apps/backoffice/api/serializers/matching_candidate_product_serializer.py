from rest_framework import serializers

from apps.catalog.models import Product


class MatchingCandidateProductSerializer(serializers.ModelSerializer):
    brand_name = serializers.CharField(source="brand.name", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "name",
            "sku",
            "article",
            "brand_name",
            "category_name",
        )
