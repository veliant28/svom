from __future__ import annotations

from rest_framework import serializers

from apps.commerce.models import MonobankSettings, NovaPaySettings, OrderPayment


class MonobankSettingsSerializer(serializers.ModelSerializer):
    merchant_token = serializers.CharField(write_only=True, required=False, allow_blank=False, trim_whitespace=True)
    merchant_token_masked = serializers.CharField(read_only=True)
    widget_private_key_masked = serializers.CharField(read_only=True)
    widget_private_key = serializers.CharField(write_only=True, required=False, allow_blank=False, trim_whitespace=False)
    webhook_url = serializers.CharField(read_only=True)
    redirect_url = serializers.CharField(read_only=True)

    class Meta:
        model = MonobankSettings
        fields = (
            "is_enabled",
            "merchant_token",
            "merchant_token_masked",
            "widget_key_id",
            "widget_private_key_masked",
            "widget_private_key",
            "webhook_url",
            "redirect_url",
            "last_connection_checked_at",
            "last_connection_ok",
            "last_connection_message",
            "last_currency_sync_at",
        )

    def to_representation(self, instance: MonobankSettings) -> dict:
        data = super().to_representation(instance)
        data["merchant_token_masked"] = instance.merchant_token_masked
        data["widget_private_key_masked"] = "************" if (instance.widget_private_key or "").strip() else ""
        data["webhook_url"] = self.context.get("webhook_url", "")
        data["redirect_url"] = self.context.get("redirect_url", "")
        return data

    def update(self, instance: MonobankSettings, validated_data: dict) -> MonobankSettings:
        token = validated_data.pop("merchant_token", None)
        private_key = validated_data.pop("widget_private_key", None)

        if token is not None:
            instance.merchant_token = token.strip()
        if private_key is not None:
            instance.widget_private_key = private_key.strip()

        for field, value in validated_data.items():
            setattr(instance, field, value)

        instance.save()
        return instance


class NovaPaySettingsSerializer(serializers.ModelSerializer):
    api_token = serializers.CharField(write_only=True, required=False, allow_blank=False, trim_whitespace=True)
    api_token_masked = serializers.CharField(read_only=True)

    class Meta:
        model = NovaPaySettings
        fields = (
            "is_enabled",
            "merchant_id",
            "api_token",
            "api_token_masked",
        )

    def to_representation(self, instance: NovaPaySettings) -> dict:
        data = super().to_representation(instance)
        data["api_token_masked"] = instance.api_token_masked
        return data

    def update(self, instance: NovaPaySettings, validated_data: dict) -> NovaPaySettings:
        token = validated_data.pop("api_token", None)
        if token is not None:
            instance.api_token = token.strip()

        for field, value in validated_data.items():
            setattr(instance, field, value)

        instance.save()
        return instance


class MonobankConnectionCheckSerializer(serializers.Serializer):
    ok = serializers.BooleanField()
    message = serializers.CharField()
    public_key = serializers.CharField(allow_blank=True)


class MonobankCurrencyRowSerializer(serializers.Serializer):
    pair = serializers.CharField()
    currency_code_a = serializers.IntegerField()
    currency_code_b = serializers.IntegerField()
    rate_buy = serializers.FloatField(required=False, allow_null=True)
    rate_sell = serializers.FloatField(required=False, allow_null=True)
    rate_cross = serializers.FloatField(required=False, allow_null=True)
    updated_at = serializers.CharField()


class MonobankCurrencyResponseSerializer(serializers.Serializer):
    rows = MonobankCurrencyRowSerializer(many=True)
    last_fetched_at = serializers.DateTimeField(allow_null=True)


class BackofficeOrderPaymentSerializer(serializers.ModelSerializer):
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


class BackofficeMonobankPaymentActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=("refresh", "cancel", "remove", "finalize", "fiscal_checks"))
    amount = serializers.IntegerField(required=False, min_value=1)

    def validate(self, attrs: dict) -> dict:
        action = str(attrs.get("action") or "")
        amount = attrs.get("amount")
        if amount is not None and action not in {"cancel", "finalize"}:
            raise serializers.ValidationError({"amount": "Amount is supported only for cancel/finalize actions."})
        return attrs


class BackofficeMonobankFiscalCheckSerializer(serializers.Serializer):
    id = serializers.CharField(required=False, allow_blank=True)
    status = serializers.CharField(required=False, allow_blank=True)
    type = serializers.CharField(required=False, allow_blank=True)
    statusDescription = serializers.CharField(required=False, allow_blank=True)
    taxUrl = serializers.CharField(required=False, allow_blank=True)
    file = serializers.CharField(required=False, allow_blank=True)
    fiscalizationSource = serializers.CharField(required=False, allow_blank=True)


class BackofficeMonobankPaymentActionResponseSerializer(serializers.Serializer):
    action = serializers.CharField()
    payment = BackofficeOrderPaymentSerializer()
    provider_result = serializers.JSONField()
    fiscal_checks = BackofficeMonobankFiscalCheckSerializer(many=True)
