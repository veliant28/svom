from __future__ import annotations

from rest_framework import serializers

from apps.core.models import TelegramSettings


class TelegramSettingsSerializer(serializers.ModelSerializer):
    ops_bot_token = serializers.CharField(write_only=True, required=False, allow_blank=True, trim_whitespace=True)
    support_bot_token = serializers.CharField(write_only=True, required=False, allow_blank=True, trim_whitespace=True)
    system_bot_token = serializers.CharField(write_only=True, required=False, allow_blank=True, trim_whitespace=True)
    ops_bot_token_masked = serializers.CharField(read_only=True)
    support_bot_token_masked = serializers.CharField(read_only=True)
    system_bot_token_masked = serializers.CharField(read_only=True)

    class Meta:
        model = TelegramSettings
        fields = (
            "is_enabled",
            "ops_enabled",
            "support_enabled",
            "system_enabled",
            "ops_bot_token",
            "ops_bot_token_masked",
            "ops_chat_id",
            "support_bot_token",
            "support_bot_token_masked",
            "support_chat_id",
            "system_bot_token",
            "system_bot_token_masked",
            "system_chat_id",
            "ops_notify_order_status",
            "ops_notify_return_created",
            "ops_notify_return_status",
            "ops_notify_waybill_created",
            "ops_notify_waybill_updated",
            "ops_notify_waybill_deleted",
            "support_notify_new_thread",
            "support_notify_new_message",
            "system_notify_backup_status",
            "system_notify_import_status",
        )

    def to_representation(self, instance: TelegramSettings) -> dict:
        data = super().to_representation(instance)
        data["ops_bot_token_masked"] = instance.ops_bot_token_masked
        data["support_bot_token_masked"] = instance.support_bot_token_masked
        data["system_bot_token_masked"] = instance.system_bot_token_masked
        return data


class TelegramTestMessageSerializer(serializers.Serializer):
    bot = serializers.ChoiceField(choices=("ops", "support", "system"))
    text = serializers.CharField(required=False, allow_blank=True, max_length=500)


class TelegramTestMessageResponseSerializer(serializers.Serializer):
    ok = serializers.BooleanField()
    message = serializers.CharField()
