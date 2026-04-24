from __future__ import annotations

from rest_framework import serializers

from apps.commerce.models import OrderReceipt, VchasnoKasaSettings
from apps.commerce.services.vchasno_kasa import serialize_receipt_row


class BackofficeVchasnoKasaSettingsSerializer(serializers.ModelSerializer):
    api_token = serializers.CharField(write_only=True, required=False, allow_blank=True, trim_whitespace=True)
    api_token_masked = serializers.CharField(read_only=True)

    class Meta:
        model = VchasnoKasaSettings
        fields = (
            "is_enabled",
            "api_token",
            "api_token_masked",
            "rro_fn",
            "default_payment_type",
            "default_tax_group",
            "auto_issue_on_completed",
            "send_customer_email",
            "last_connection_checked_at",
            "last_connection_ok",
            "last_connection_message",
        )

    def to_representation(self, instance: VchasnoKasaSettings) -> dict:
        data = super().to_representation(instance)
        data["api_token_masked"] = instance.api_token_masked
        return data

    def validate(self, attrs: dict) -> dict:
        enabled = attrs.get("is_enabled", getattr(self.instance, "is_enabled", False))
        token = attrs.get("api_token", None)
        existing_token = getattr(self.instance, "api_token", "")
        resolved_token = existing_token if token in {None, ""} else token
        rro_fn = attrs.get("rro_fn", getattr(self.instance, "rro_fn", ""))
        if enabled and not str(resolved_token or "").strip():
            raise serializers.ValidationError({"api_token": "VCHASNO_KASA_TOKEN_MISSING"})
        if enabled and not str(rro_fn or "").strip():
            raise serializers.ValidationError({"rro_fn": "VCHASNO_KASA_RRO_FN_MISSING"})
        return attrs

    def update(self, instance: VchasnoKasaSettings, validated_data: dict) -> VchasnoKasaSettings:
        token = validated_data.pop("api_token", None)
        if token not in {None, ""}:
            instance.api_token = token.strip()
        actor = self.context.get("request").user if self.context.get("request") is not None else None
        if actor is not None:
            if instance.created_by_id is None:
                instance.created_by = actor
            instance.updated_by = actor
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance


class BackofficeVchasnoKasaConnectionCheckSerializer(serializers.Serializer):
    ok = serializers.BooleanField()
    message = serializers.CharField()


class BackofficeOrderReceiptSummarySerializer(serializers.Serializer):
    provider = serializers.CharField()
    available = serializers.BooleanField()
    status_code = serializers.IntegerField(allow_null=True)
    status_key = serializers.CharField()
    status_label = serializers.CharField()
    check_fn = serializers.CharField(allow_blank=True)
    can_issue = serializers.BooleanField()
    can_open = serializers.BooleanField()
    can_sync = serializers.BooleanField()
    error_message = serializers.CharField(allow_blank=True)


class BackofficeOrderReceiptActionSerializer(serializers.Serializer):
    receipt = BackofficeOrderReceiptSummarySerializer()
    already_exists = serializers.BooleanField(default=False)
    sync_performed = serializers.BooleanField(default=False)


class BackofficeVchasnoReceiptRowSerializer(serializers.Serializer):
    id = serializers.CharField()
    order_id = serializers.CharField()
    order_number = serializers.CharField()
    customer_name = serializers.CharField()
    amount = serializers.CharField()
    currency = serializers.CharField()
    status_code = serializers.IntegerField(allow_null=True)
    status_key = serializers.CharField()
    status_label = serializers.CharField()
    check_fn = serializers.CharField(allow_blank=True)
    receipt_url = serializers.CharField(allow_blank=True)
    pdf_url = serializers.CharField(allow_blank=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class BackofficeVchasnoReceiptListSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    results = serializers.SerializerMethodField()

    def get_results(self, obj) -> list[dict]:
        return [serialize_receipt_row(item) for item in obj["results"]]


class AccountOrderReceiptSummarySerializer(serializers.Serializer):
    provider = serializers.CharField()
    available = serializers.BooleanField()
    status_code = serializers.IntegerField(allow_null=True)
    status_key = serializers.CharField()
    status_label = serializers.CharField()
    check_fn = serializers.CharField(allow_blank=True)
    can_open = serializers.BooleanField()
    error_message = serializers.CharField(allow_blank=True)
