from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class MonobankSettings(UUIDPrimaryKeyMixin, TimestampedMixin):
    DEFAULT_CODE = "default"

    code = models.CharField(_("Код профиля"), max_length=32, unique=True, default=DEFAULT_CODE)
    is_enabled = models.BooleanField(_("Monobank включен"), default=False)

    merchant_token = models.CharField(_("Merchant token"), max_length=255, blank=True)
    widget_key_id = models.CharField(_("Widget key id"), max_length=255, blank=True)
    widget_private_key = models.TextField(_("Widget private key (PEM)"), blank=True)
    webhook_public_key = models.TextField(_("Webhook public key (PEM)"), blank=True)

    last_connection_checked_at = models.DateTimeField(_("Последняя проверка соединения"), blank=True, null=True)
    last_connection_ok = models.BooleanField(_("Последняя проверка успешна"), blank=True, null=True)
    last_connection_message = models.TextField(_("Сообщение последней проверки"), blank=True)

    last_sync_at = models.DateTimeField(_("Последняя синхронизация"), blank=True, null=True)
    last_currency_sync_at = models.DateTimeField(_("Последнее обновление курсов"), blank=True, null=True)
    currency_rates_snapshot = models.JSONField(_("Снимок курсов валют"), default=list, blank=True)

    class Meta:
        verbose_name = _("Настройки Monobank")
        verbose_name_plural = _("Настройки Monobank")

    def __str__(self) -> str:
        return f"MonobankSettings:{self.code}"

    @property
    def merchant_token_masked(self) -> str:
        token = (self.merchant_token or "").strip()
        if not token:
            return ""
        if len(token) <= 8:
            return "*" * len(token)
        return f"{token[:4]}{'*' * (len(token) - 8)}{token[-4:]}"
