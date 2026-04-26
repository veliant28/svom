from __future__ import annotations

from typing import Iterable

from django.conf import settings as django_settings
from django.core.mail import EmailMessage, get_connection, send_mail
from django.utils import timezone

from apps.core.models import EmailDeliverySettings
from apps.core.selectors import get_email_delivery_settings


class EmailDeliveryError(RuntimeError):
    pass


def get_configured_frontend_base_url() -> str:
    delivery_settings = get_email_delivery_settings()
    db_url = str(delivery_settings.frontend_base_url or "").strip().rstrip("/")
    if db_url:
        return db_url
    return str(getattr(django_settings, "FRONTEND_BASE_URL", "") or "").strip().rstrip("/")


def send_configured_mail(
    *,
    subject: str,
    message: str,
    recipient_list: Iterable[str],
    fail_silently: bool = False,
) -> int:
    delivery_settings = get_email_delivery_settings()
    recipients = [email for email in recipient_list if str(email or "").strip()]
    if not delivery_settings.is_enabled:
        return send_mail(
            subject=subject,
            message=message,
            from_email=getattr(django_settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=recipients,
            fail_silently=fail_silently,
        )

    _validate_smtp_settings(delivery_settings)
    connection = _build_smtp_connection(delivery_settings)
    email = EmailMessage(
        subject=subject,
        body=message,
        from_email=delivery_settings.from_email.strip(),
        to=recipients,
        connection=connection,
    )
    return email.send(fail_silently=fail_silently)


def send_email_settings_test_message(*, recipient: str) -> dict[str, object]:
    delivery_settings = get_email_delivery_settings()
    recipient = str(recipient or "").strip()
    if not recipient:
        return _save_check_result(settings=delivery_settings, ok=False, message="Test recipient is required.")

    try:
        _validate_smtp_settings(delivery_settings)
        connection = _build_smtp_connection(delivery_settings)
        message = EmailMessage(
            subject="SVOM email delivery test",
            body=(
                "This is a test email from SVOM backoffice.\n\n"
                "If you received it, SMTP delivery is configured correctly."
            ),
            from_email=delivery_settings.from_email.strip(),
            to=[recipient],
            connection=connection,
        )
        sent_count = message.send(fail_silently=False)
    except Exception as exc:
        return _save_check_result(settings=delivery_settings, ok=False, message=str(exc) or exc.__class__.__name__)

    if sent_count > 0:
        return _save_check_result(settings=delivery_settings, ok=True, message="Test email sent successfully.")
    return _save_check_result(settings=delivery_settings, ok=False, message="SMTP backend did not send the test email.")


def _validate_smtp_settings(settings: EmailDeliverySettings) -> None:
    if not str(settings.from_email or "").strip():
        raise EmailDeliveryError("From email is required.")
    if not str(settings.host or "").strip():
        raise EmailDeliveryError("SMTP host is required.")
    if int(settings.port or 0) <= 0:
        raise EmailDeliveryError("SMTP port must be greater than zero.")
    if settings.use_tls and settings.use_ssl:
        raise EmailDeliveryError("Use either TLS or SSL, not both.")


def _build_smtp_connection(settings: EmailDeliverySettings):
    return get_connection(
        backend="django.core.mail.backends.smtp.EmailBackend",
        host=settings.host.strip(),
        port=int(settings.port or 587),
        username=settings.host_user.strip(),
        password=settings.host_password,
        use_tls=bool(settings.use_tls),
        use_ssl=bool(settings.use_ssl),
        timeout=int(settings.timeout or 10),
    )


def _save_check_result(*, settings: EmailDeliverySettings, ok: bool, message: str) -> dict[str, object]:
    settings.last_connection_checked_at = timezone.now()
    settings.last_connection_ok = bool(ok)
    settings.last_connection_message = str(message or "").strip()
    settings.save(
        update_fields=(
            "last_connection_checked_at",
            "last_connection_ok",
            "last_connection_message",
            "updated_at",
        )
    )
    return {
        "ok": bool(ok),
        "message": settings.last_connection_message,
    }
