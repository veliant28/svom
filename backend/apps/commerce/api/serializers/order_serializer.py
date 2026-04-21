from rest_framework import serializers

from apps.commerce.models import Order, OrderItem
from apps.commerce.services.delivery_snapshot import resolve_delivery_display, resolve_waybill_seed

from .product_summary_serializer import CommerceProductSummarySerializer
from .order_payment_serializer import OrderPaymentSerializer


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
    payment = OrderPaymentSerializer(read_only=True)
    delivery_city_label = serializers.SerializerMethodField()
    delivery_destination_label = serializers.SerializerMethodField()
    delivery_waybill_seed = serializers.SerializerMethodField()

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
            "delivery_snapshot",
            "delivery_city_label",
            "delivery_destination_label",
            "delivery_waybill_seed",
            "payment_method",
            "payment",
            "subtotal",
            "delivery_fee",
            "discount_total",
            "applied_promo_code",
            "discount_breakdown",
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

    def get_delivery_city_label(self, obj: Order) -> str:
        city, _ = resolve_delivery_display(
            delivery_method=obj.delivery_method,
            delivery_address=obj.delivery_address,
            delivery_snapshot=obj.delivery_snapshot,
        )
        return city

    def get_delivery_destination_label(self, obj: Order) -> str:
        _, destination = resolve_delivery_display(
            delivery_method=obj.delivery_method,
            delivery_address=obj.delivery_address,
            delivery_snapshot=obj.delivery_snapshot,
        )
        return destination

    def get_delivery_waybill_seed(self, obj: Order) -> dict:
        return resolve_waybill_seed(
            delivery_method=obj.delivery_method,
            delivery_address=obj.delivery_address,
            delivery_snapshot=obj.delivery_snapshot,
        )
