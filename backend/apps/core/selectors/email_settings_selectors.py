from __future__ import annotations

from email.utils import parseaddr

from django.conf import settings as django_settings

from apps.core.models import EmailDeliverySettings


def _split_default_from_email() -> tuple[str, str]:
    name, address = parseaddr(getattr(django_settings, "DEFAULT_FROM_EMAIL", "") or "")
    return name.strip(), address.strip()


def _infer_provider() -> str:
    host = str(getattr(django_settings, "EMAIL_HOST", "") or "").strip().lower()
    host_user = str(getattr(django_settings, "EMAIL_HOST_USER", "") or "").strip().lower()
    if host == "smtp.resend.com" and host_user == "resend":
        return EmailDeliverySettings.PROVIDER_RESEND_SMTP
    return EmailDeliverySettings.PROVIDER_MANUAL_SMTP


def get_email_delivery_settings() -> EmailDeliverySettings:
    from_name, from_email = _split_default_from_email()
    settings, _ = EmailDeliverySettings.objects.get_or_create(
        code=EmailDeliverySettings.DEFAULT_CODE,
        defaults={
            "provider": _infer_provider(),
            "from_name": from_name,
            "from_email": from_email or getattr(django_settings, "DEFAULT_FROM_EMAIL", "") or "",
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
