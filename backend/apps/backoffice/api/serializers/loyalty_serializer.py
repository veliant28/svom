from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.commerce.models import LoyaltyPromoCode

User = get_user_model()


class BackofficeLoyaltyIssueSerializer(serializers.Serializer):
    customer_id = serializers.IntegerField()
    reason = serializers.CharField(max_length=255)
    discount_type = serializers.ChoiceField(choices=[choice[0] for choice in LoyaltyPromoCode.DISCOUNT_TYPE_CHOICES])
    discount_percent = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=100)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)
    usage_limit = serializers.IntegerField(required=False, min_value=1, default=1)

    def validate_customer_id(self, value: int) -> int:
        if not User.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError("Customer not found.")
        return value


class BackofficeLoyaltyPersonSerializer(serializers.Serializer):
    id = serializers.CharField(allow_null=True)
    email = serializers.CharField(allow_blank=True)
    name = serializers.CharField(allow_blank=True)


class BackofficeLoyaltyPromoSerializer(serializers.Serializer):
    id = serializers.CharField()
    code = serializers.CharField()
    discount_type = serializers.CharField()
    discount_percent = serializers.CharField()
    usage_limit = serializers.IntegerField()
    usage_count = serializers.IntegerField()
    reason = serializers.CharField()
    status = serializers.CharField()
    state = serializers.CharField()
    is_expired = serializers.BooleanField()
    is_used = serializers.BooleanField()
    is_used_up = serializers.BooleanField()
    is_active = serializers.BooleanField()
    expires_at = serializers.DateTimeField(allow_null=True)
    issued_at = serializers.DateTimeField()
    issued_by = BackofficeLoyaltyPersonSerializer()
    customer = BackofficeLoyaltyPersonSerializer()
    last_redeemed_at = serializers.DateTimeField(allow_null=True)
    last_redeemed_order_id = serializers.CharField(allow_null=True)


class BackofficeLoyaltyStaffStatsSerializer(serializers.Serializer):
    staff_id = serializers.CharField()
    staff_email = serializers.CharField()
    staff_name = serializers.CharField(allow_blank=True)
    issued_total = serializers.IntegerField()
    issued_delivery = serializers.IntegerField()
    issued_product = serializers.IntegerField()
    nominal_percent_total = serializers.CharField()
    discount_sum_total = serializers.CharField()
    used_total = serializers.IntegerField()
    conversion_rate = serializers.CharField()


class BackofficeLoyaltyCustomerLookupSerializer(serializers.Serializer):
    id = serializers.CharField()
    email = serializers.CharField()
    full_name = serializers.CharField(allow_blank=True)
    label = serializers.CharField()
