from rest_framework import serializers

from apps.commerce.models import OrderPayment


class OrderPaymentSerializer(serializers.ModelSerializer):
    invoice_id = serializers.SerializerMethodField(read_only=True)
    reference = serializers.SerializerMethodField(read_only=True)
    page_url = serializers.SerializerMethodField(read_only=True)

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

    def get_invoice_id(self, obj: OrderPayment) -> str:
        provider = (obj.provider or "").strip().lower()
        if provider == OrderPayment.PROVIDER_LIQPAY:
            return obj.liqpay_payment_id or ""
        return obj.monobank_invoice_id or ""

    def get_reference(self, obj: OrderPayment) -> str:
        provider = (obj.provider or "").strip().lower()
        if provider == OrderPayment.PROVIDER_LIQPAY:
            return obj.liqpay_order_id or ""
        return obj.monobank_reference or ""

    def get_page_url(self, obj: OrderPayment) -> str:
        provider = (obj.provider or "").strip().lower()
        if provider == OrderPayment.PROVIDER_LIQPAY:
            return obj.liqpay_page_url or ""
        return obj.monobank_page_url or ""
