from __future__ import annotations

from django.conf import settings as django_settings

from apps.core.models import EmailDeliverySettings


def get_email_delivery_settings() -> EmailDeliverySettings:
    settings, _ = EmailDeliverySettings.objects.get_or_create(
        code=EmailDeliverySettings.DEFAULT_CODE,
        defaults={
            "from_email": getattr(django_settings, "DEFAULT_FROM_EMAIL", "") or "",
            "host": getattr(django_settings, "EMAIL_HOST", "") or "",
            "port": int(getattr(django_settings, "EMAIL_PORT", 587) or 587),
            "host_user": getattr(django_settings, "EMAIL_HOST_USER", "") or "",
            "host_password": getattr(django_settings, "EMAIL_HOST_PASSWORD", "") or "",
            "use_tls": bool(getattr(django_settings, "EMAIL_USE_TLS", True)),
            "use_ssl": bool(getattr(django_settings, "EMAIL_USE_SSL", False)),
            "timeout": int(getattr(django_settings, "EMAIL_TIMEOUT", 10) or 10),
            "frontend_base_url": getattr(django_settings, "FRONTEND_BASE_URL", "") or "",
        },
    )
    return settings
