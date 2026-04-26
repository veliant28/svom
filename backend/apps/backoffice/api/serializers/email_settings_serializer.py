from __future__ import annotations

from rest_framework import serializers

from apps.core.models import EmailDeliverySettings


class EmailDeliverySettingsSerializer(serializers.ModelSerializer):
    host_password = serializers.CharField(write_only=True, required=False, allow_blank=False, trim_whitespace=False)
    host_password_masked = serializers.CharField(read_only=True)

    class Meta:
        model = EmailDeliverySettings
        fields = (
            "is_enabled",
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
        data["host_password_masked"] = instance.host_password_masked
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
