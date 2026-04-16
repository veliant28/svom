from rest_framework import serializers

from apps.commerce.models import Order, OrderItem

from .product_summary_serializer import CommerceProductSummarySerializer


class OrderItemSerializer(serializers.ModelSerializer):
    product = CommerceProductSummarySerializer(read_only=True)
    recommended_supplier_offer_id = serializers.CharField(read_only=True, allow_null=True)
    selected_supplier_offer_id = serializers.CharField(read_only=True, allow_null=True)

    class Meta:
        model = OrderItem
        fields = (
            "id",
            "product",
            "product_name",
            "product_sku",
            "quantity",
            "unit_price",
            "line_total",
            "procurement_status",
            "recommended_supplier_offer_id",
            "selected_supplier_offer_id",
            "shortage_reason_code",
            "shortage_reason_note",
            "operator_note",
            "snapshot_currency",
            "snapshot_sell_price",
            "snapshot_availability_status",
            "snapshot_availability_label",
            "snapshot_estimated_delivery_days",
            "snapshot_procurement_source",
            "snapshot_selected_offer",
            "snapshot_offer_explainability",
        )


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "order_number",
            "status",
            "contact_full_name",
            "contact_phone",
            "contact_email",
            "delivery_method",
            "delivery_address",
            "payment_method",
            "subtotal",
            "delivery_fee",
            "total",
            "currency",
            "customer_comment",
            "internal_notes",
            "operator_notes",
            "cancellation_reason_code",
            "cancellation_reason_note",
            "placed_at",
            "items",
        )
