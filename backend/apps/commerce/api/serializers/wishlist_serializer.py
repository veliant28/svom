from rest_framework import serializers

from apps.commerce.models import WishlistItem

from .product_summary_serializer import CommerceProductSummarySerializer


class WishlistItemSerializer(serializers.ModelSerializer):
    product = CommerceProductSummarySerializer(read_only=True)

    class Meta:
        model = WishlistItem
        fields = (
            "id",
            "product",
            "created_at",
        )


class WishlistAddSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
