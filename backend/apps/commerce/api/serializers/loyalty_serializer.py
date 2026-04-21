from __future__ import annotations

from rest_framework import serializers

from apps.commerce.models import LoyaltyPromoCode
from apps.commerce.services.loyalty_service import serialize_loyalty_promo_status


class LoyaltyPromoCodeSerializer(serializers.ModelSerializer):
    state = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()
    is_used = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()

    class Meta:
        model = LoyaltyPromoCode
        fields = (
            "id",
            "code",
            "discount_type",
            "discount_percent",
            "reason",
            "status",
            "state",
            "is_active",
            "is_used",
            "is_expired",
            "usage_limit",
            "usage_count",
            "expires_at",
            "last_redeemed_at",
            "created_at",
        )

    def _status(self, obj: LoyaltyPromoCode) -> dict[str, object]:
        return serialize_loyalty_promo_status(promo=obj)

    def get_state(self, obj: LoyaltyPromoCode) -> str:
        return str(self._status(obj)["state"])

    def get_is_active(self, obj: LoyaltyPromoCode) -> bool:
        return bool(self._status(obj)["is_active"])

    def get_is_used(self, obj: LoyaltyPromoCode) -> bool:
        return bool(self._status(obj)["is_used"])

    def get_is_expired(self, obj: LoyaltyPromoCode) -> bool:
        return bool(self._status(obj)["is_expired"])
