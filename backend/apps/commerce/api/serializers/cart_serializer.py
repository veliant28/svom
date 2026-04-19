from decimal import Decimal

from rest_framework import serializers

from apps.commerce.models import Cart, CartItem
from apps.commerce.services import get_line_total, get_product_unit_price
from apps.commerce.services.sellable_state import build_cart_item_warning, get_cart_item_sellable_snapshot

from .product_summary_serializer import CommerceProductSummarySerializer


class CartItemSerializer(serializers.ModelSerializer):
    product = CommerceProductSummarySerializer(read_only=True)
    unit_price = serializers.SerializerMethodField()
    line_total = serializers.SerializerMethodField()
    availability_status = serializers.SerializerMethodField()
    availability_label = serializers.SerializerMethodField()
    estimated_delivery_days = serializers.SerializerMethodField()
    procurement_source_summary = serializers.SerializerMethodField()
    is_sellable = serializers.SerializerMethodField()
    max_order_quantity = serializers.SerializerMethodField()
    warning = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = (
            "id",
            "product",
            "quantity",
            "unit_price",
            "line_total",
            "availability_status",
            "availability_label",
            "estimated_delivery_days",
            "procurement_source_summary",
            "is_sellable",
            "max_order_quantity",
            "warning",
        )

    def get_unit_price(self, obj: CartItem):
        return get_product_unit_price(obj)

    def get_line_total(self, obj: CartItem):
        return get_line_total(obj)

    def _snapshot(self, obj: CartItem):
        return get_cart_item_sellable_snapshot(obj)

    def get_availability_status(self, obj: CartItem):
        return self._snapshot(obj).availability_status

    def get_availability_label(self, obj: CartItem):
        return self._snapshot(obj).availability_label

    def get_estimated_delivery_days(self, obj: CartItem):
        return self._snapshot(obj).estimated_delivery_days

    def get_procurement_source_summary(self, obj: CartItem):
        return self._snapshot(obj).procurement_source_summary

    def get_is_sellable(self, obj: CartItem):
        return self._snapshot(obj).is_sellable

    def get_max_order_quantity(self, obj: CartItem):
        return self._snapshot(obj).max_order_quantity

    def get_warning(self, obj: CartItem):
        snapshot = self._snapshot(obj)
        return build_cart_item_warning(obj, snapshot)


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    summary = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = (
            "id",
            "currency",
            "items",
            "summary",
            "updated_at",
        )

    def get_summary(self, obj: Cart):
        items = list(obj.items.all())
        items_count = sum(item.quantity for item in items)
        subtotal = sum((get_line_total(item) for item in items), start=Decimal("0.00"))
        warnings_count = 0
        for item in items:
            snapshot = get_cart_item_sellable_snapshot(item)
            if build_cart_item_warning(item, snapshot):
                warnings_count += 1
        return {
            "items_count": items_count,
            "subtotal": subtotal,
            "warnings_count": warnings_count,
        }


class CartItemCreateSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1, default=1)


class CartItemQuantityUpdateSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=0)
