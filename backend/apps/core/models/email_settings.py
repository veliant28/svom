from __future__ import annotations

from email.utils import formataddr

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class EmailDeliverySettings(UUIDPrimaryKeyMixin, TimestampedMixin):
    DEFAULT_CODE = "default"
    PROVIDER_RESEND_SMTP = "resend_smtp"
    PROVIDER_MANUAL_SMTP = "manual_smtp"
    PROVIDER_CHOICES = (
        (PROVIDER_RESEND_SMTP, _("Resend SMTP")),
        (PROVIDER_MANUAL_SMTP, _("Manual SMTP")),
    )

    code = models.CharField(_("Код профиля"), max_length=32, unique=True, default=DEFAULT_CODE)
    provider = models.CharField(_("SMTP provider"), max_length=32, choices=PROVIDER_CHOICES, default=PROVIDER_MANUAL_SMTP)
    is_enabled = models.BooleanField(_("SMTP отправка включена"), default=False)

    from_name = models.CharField(_("Имя отправителя"), max_length=255, blank=True)
    from_email = models.CharField(_("Email отправителя"), max_length=255, blank=True)
    host = models.CharField(_("SMTP host"), max_length=255, blank=True)
    port = models.PositiveIntegerField(_("SMTP port"), default=587)
    host_user = models.CharField(_("SMTP user"), max_length=255, blank=True)
    host_password = models.CharField(_("SMTP password"), max_length=255, blank=True)
    use_tls = models.BooleanField(_("Use TLS"), default=True)
    use_ssl = models.BooleanField(_("Use SSL"), default=False)
    timeout = models.PositiveIntegerField(_("Timeout"), default=10)
    frontend_base_url = models.URLField(_("Frontend base URL"), max_length=255, blank=True)

    last_connection_checked_at = models.DateTimeField(_("Последняя проверка соединения"), blank=True, null=True)
    last_connection_ok = models.BooleanField(_("Последняя проверка успешна"), blank=True, null=True)
    last_connection_message = models.TextField(_("Сообщение последней проверки"), blank=True)

    class Meta:
        verbose_name = _("Настройки отправки email")
        verbose_name_plural = _("Настройки отправки email")

    def __str__(self) -> str:
        return f"EmailDeliverySettings:{self.code}"

    @property
    def formatted_from_email(self) -> str:
        address = (self.from_email or "").strip()
        name = (self.from_name or "").strip()
        if name and address:
            return formataddr((name, address))
        return address

    @property
    def host_password_masked(self) -> str:
        password = (self.host_password or "").strip()
        if not password:
            return ""
        if len(password) <= 8:
            return "*" * len(password)
        return f"{password[:2]}{'*' * (len(password) - 4)}{password[-2:]}"
