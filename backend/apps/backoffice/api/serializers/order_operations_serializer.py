from rest_framework import serializers

from apps.commerce.models import Order


class OrderActionSerializer(serializers.Serializer):
    order_id = serializers.UUIDField()
    operator_note = serializers.CharField(required=False, allow_blank=True)


class OrderReserveActionSerializer(OrderActionSerializer):
    item_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
    )


class OrderCancelActionSerializer(OrderActionSerializer):
    reason_code = serializers.ChoiceField(choices=[choice[0] for choice in Order.CANCELLATION_REASON_CHOICES])
    reason_note = serializers.CharField(required=False, allow_blank=True)


class OrderBulkActionSerializer(serializers.Serializer):
    order_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)
    operator_note = serializers.CharField(required=False, allow_blank=True)


class OrderItemSupplierOverrideSerializer(serializers.Serializer):
    supplier_offer_id = serializers.UUIDField()
    operator_note = serializers.CharField(required=False, allow_blank=True)
