from __future__ import annotations

from email.utils import parseaddr

from rest_framework import serializers

from apps.core.models import EmailDeliverySettings
from apps.core.services.email_delivery import sanitize_smtp_error_message


RESEND_SMTP_PRESET = {
    "host": "smtp.resend.com",
    "port": 587,
    "host_user": "resend",
    "use_tls": True,
    "use_ssl": False,
    "timeout": 10,
    "frontend_base_url": "https://svom.com.ua",
}


class EmailDeliverySettingsSerializer(serializers.ModelSerializer):
    from_email = serializers.EmailField(required=False, allow_blank=True)
    host_password = serializers.CharField(write_only=True, required=False, allow_blank=False, trim_whitespace=False)
    host_password_masked = serializers.CharField(read_only=True)

    class Meta:
        model = EmailDeliverySettings
        fields = (
            "provider",
            "is_enabled",
            "from_name",
            "from_email",
            "host",
            "port",
            "host_user",
            "host_password",
            "host_password_masked",
            "use_tls",
            "use_ssl",
            "timeout",
            "frontend_base_url",
            "last_connection_checked_at",
            "last_connection_ok",
            "last_connection_message",
        )

    def validate(self, attrs: dict) -> dict:
        provider = attrs.get("provider", getattr(self.instance, "provider", EmailDeliverySettings.PROVIDER_MANUAL_SMTP))
        if provider == EmailDeliverySettings.PROVIDER_RESEND_SMTP:
            attrs.update(RESEND_SMTP_PRESET)

        use_tls = attrs.get("use_tls", getattr(self.instance, "use_tls", False))
        use_ssl = attrs.get("use_ssl", getattr(self.instance, "use_ssl", False))
        if use_tls and use_ssl:
            raise serializers.ValidationError({"use_ssl": "Use either TLS or SSL, not both."})
        port = attrs.get("port", getattr(self.instance, "port", 587))
        timeout = attrs.get("timeout", getattr(self.instance, "timeout", 10))
        if int(port or 0) <= 0:
            raise serializers.ValidationError({"port": "Port must be greater than zero."})
        if int(timeout or 0) <= 0:
            raise serializers.ValidationError({"timeout": "Timeout must be greater than zero."})
        return attrs

    def to_representation(self, instance: EmailDeliverySettings) -> dict:
        data = super().to_representation(instance)
        if not data.get("from_name") and "<" in str(data.get("from_email") or ""):
            from_name, from_email = parseaddr(str(data.get("from_email") or ""))
            data["from_name"] = from_name
            data["from_email"] = from_email
        data["host_password_masked"] = instance.host_password_masked
        data["last_connection_message"] = sanitize_smtp_error_message(
            str(instance.last_connection_message or ""),
            settings=instance,
        ) if instance.last_connection_message else ""
        return data

    def update(self, instance: EmailDeliverySettings, validated_data: dict) -> EmailDeliverySettings:
        password = validated_data.pop("host_password", None)
        if password is not None:
            instance.host_password = password.strip()

        for field, value in validated_data.items():
            if isinstance(value, str):
                value = value.strip()
            setattr(instance, field, value)

        instance.save()
        return instance


class EmailDeliveryTestSerializer(serializers.Serializer):
    recipient = serializers.EmailField()


class EmailDeliveryTestResponseSerializer(serializers.Serializer):
    ok = serializers.BooleanField()
    message = serializers.CharField()
