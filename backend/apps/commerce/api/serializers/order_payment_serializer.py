from rest_framework import serializers

from apps.commerce.models import OrderPayment


class OrderPaymentSerializer(serializers.ModelSerializer):
    invoice_id = serializers.CharField(source="monobank_invoice_id", read_only=True)
    reference = serializers.CharField(source="monobank_reference", read_only=True)
    page_url = serializers.CharField(source="monobank_page_url", read_only=True)

    class Meta:
        model = OrderPayment
        fields = (
            "provider",
            "method",
            "status",
            "amount",
            "currency",
            "invoice_id",
            "reference",
            "page_url",
            "failure_reason",
            "provider_created_at",
            "provider_modified_at",
            "last_webhook_received_at",
            "last_sync_at",
        )
