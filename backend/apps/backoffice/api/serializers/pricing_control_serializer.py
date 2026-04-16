from __future__ import annotations

from decimal import Decimal, InvalidOperation

from rest_framework import serializers


class PricingPercentSerializerMixin(serializers.Serializer):
    percent_markup = serializers.DecimalField(max_digits=7, decimal_places=2)

    def validate_percent_markup(self, value: Decimal) -> Decimal:
        try:
            parsed = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise serializers.ValidationError("Некорректный процент наценки.") from exc

        if parsed < Decimal("0"):
            raise serializers.ValidationError("Процент не может быть меньше 0.")
        if parsed > Decimal("100"):
            raise serializers.ValidationError("Процент не может быть больше 100.")
        return parsed


class PricingGlobalMarkupUpdateSerializer(PricingPercentSerializerMixin):
    dispatch_async = serializers.BooleanField(default=True)


class PricingCategoryMarkupUpdateSerializer(PricingPercentSerializerMixin):
    category_id = serializers.UUIDField()
    include_children = serializers.BooleanField(default=False)
    dispatch_async = serializers.BooleanField(default=True)


class PricingCategoryImpactQuerySerializer(serializers.Serializer):
    category_id = serializers.UUIDField()
    include_children = serializers.BooleanField(default=False)


class PricingRecalculateSerializer(serializers.Serializer):
    dispatch_async = serializers.BooleanField(default=True)
    category_id = serializers.UUIDField(required=False)
    include_children = serializers.BooleanField(default=False)
