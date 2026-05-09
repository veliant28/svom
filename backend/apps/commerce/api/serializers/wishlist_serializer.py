from rest_framework import serializers

from apps.catalog.api.serializers import ProductListSerializer
from apps.commerce.models import WishlistItem


class WishlistItemSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)

    class Meta:
        model = WishlistItem
        fields = (
            "id",
            "product",
            "created_at",
        )


class WishlistAddSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
