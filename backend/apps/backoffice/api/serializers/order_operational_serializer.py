from __future__ import annotations

from rest_framework import serializers

from apps.commerce.models import Order, OrderItem


class BackofficeOrderItemOperationalSerializer(serializers.ModelSerializer):
    product_id = serializers.CharField(source="product.id", read_only=True)
    recommended_supplier_offer_id = serializers.CharField(read_only=True, allow_null=True)
    recommended_supplier_name = serializers.CharField(source="recommended_supplier_offer.supplier.name", read_only=True, default="")
    selected_supplier_offer_id = serializers.CharField(read_only=True, allow_null=True)
    selected_supplier_name = serializers.CharField(source="selected_supplier_offer.supplier.name", read_only=True, default="")

    class Meta:
        model = OrderItem
        fields = (
            "id",
            "product_id",
            "product_name",
            "product_sku",
            "quantity",
            "unit_price",
            "line_total",
            "procurement_status",
            "recommended_supplier_offer_id",
            "recommended_supplier_name",
            "selected_supplier_offer_id",
            "selected_supplier_name",
            "shortage_reason_code",
            "shortage_reason_note",
            "operator_note",
            "snapshot_availability_status",
            "snapshot_availability_label",
            "snapshot_estimated_delivery_days",
            "snapshot_procurement_source",
            "snapshot_currency",
            "snapshot_sell_price",
        )


class BackofficeOrderOperationalListSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)
    user_id = serializers.CharField(source="user.id", read_only=True)
    items_count = serializers.SerializerMethodField()
    issues_count = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            "id",
            "order_number",
            "status",
            "user_id",
            "user_email",
            "contact_full_name",
            "contact_phone",
            "contact_email",
            "delivery_method",
            "payment_method",
            "subtotal",
            "delivery_fee",
            "total",
            "currency",
            "items_count",
            "issues_count",
            "placed_at",
        )

    def get_items_count(self, obj: Order) -> int:
        return obj.items.count()

    def get_issues_count(self, obj: Order) -> int:
        problematic_statuses = {
            OrderItem.PROCUREMENT_UNAVAILABLE,
            OrderItem.PROCUREMENT_PARTIALLY_RESERVED,
        }
        return sum(
            1
            for item in obj.items.all()
            if item.procurement_status in problematic_statuses or bool(item.shortage_reason_code)
        )


class BackofficeOrderOperationalDetailSerializer(BackofficeOrderOperationalListSerializer):
    items = BackofficeOrderItemOperationalSerializer(many=True, read_only=True)

    class Meta(BackofficeOrderOperationalListSerializer.Meta):
        fields = BackofficeOrderOperationalListSerializer.Meta.fields + (
            "customer_comment",
            "internal_notes",
            "operator_notes",
            "cancellation_reason_code",
            "cancellation_reason_note",
            "items",
        )
