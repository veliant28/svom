from rest_framework import serializers

from apps.commerce.models import Order


class CheckoutPreviewQuerySerializer(serializers.Serializer):
    delivery_method = serializers.ChoiceField(
        choices=[choice[0] for choice in Order.DELIVERY_METHOD_CHOICES],
        required=False,
    )


class CheckoutSubmitSerializer(serializers.Serializer):
    contact_full_name = serializers.CharField(max_length=255)
    contact_phone = serializers.CharField(max_length=32)
    contact_email = serializers.EmailField()
    delivery_method = serializers.ChoiceField(choices=[choice[0] for choice in Order.DELIVERY_METHOD_CHOICES])
    delivery_address = serializers.CharField(max_length=500, required=False, allow_blank=True)
    payment_method = serializers.ChoiceField(choices=[choice[0] for choice in Order.PAYMENT_METHOD_CHOICES])
    customer_comment = serializers.CharField(required=False, allow_blank=True)
