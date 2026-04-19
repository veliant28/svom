import re

from rest_framework import serializers

from apps.commerce.models import Order

PHONE_FORMAT_REGEX = re.compile(r"^38\(0\d{2}\)\d{3}-\d{2}-\d{2}$")


class CheckoutPreviewQuerySerializer(serializers.Serializer):
    delivery_method = serializers.ChoiceField(
        choices=[choice[0] for choice in Order.DELIVERY_METHOD_CHOICES],
        required=False,
    )


class CheckoutNovaPoshtaLookupQuerySerializer(serializers.Serializer):
    query = serializers.CharField(required=False, allow_blank=True, default="")
    locale = serializers.CharField(required=False, allow_blank=True, default="uk")


class CheckoutNovaPoshtaStreetLookupQuerySerializer(CheckoutNovaPoshtaLookupQuerySerializer):
    settlement_ref = serializers.CharField()


class CheckoutNovaPoshtaWarehouseLookupQuerySerializer(CheckoutNovaPoshtaLookupQuerySerializer):
    city_ref = serializers.CharField(required=False, allow_blank=True, default="")


class CheckoutSubmitSerializer(serializers.Serializer):
    contact_full_name = serializers.CharField(max_length=255)
    contact_phone = serializers.CharField(max_length=16, min_length=16)
    contact_email = serializers.EmailField()
    delivery_method = serializers.ChoiceField(choices=[choice[0] for choice in Order.DELIVERY_METHOD_CHOICES])
    delivery_address = serializers.CharField(max_length=500, required=False, allow_blank=True)
    payment_method = serializers.ChoiceField(choices=[choice[0] for choice in Order.PAYMENT_METHOD_CHOICES])
    customer_comment = serializers.CharField(required=False, allow_blank=True)

    def validate_contact_phone(self, value: str) -> str:
        normalized_value = value.strip()
        if not PHONE_FORMAT_REGEX.fullmatch(normalized_value):
            raise serializers.ValidationError("Phone must match format 38(0XX)XXX-XX-XX.")
        return normalized_value
