from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class NovaPaySettings(UUIDPrimaryKeyMixin, TimestampedMixin):
    DEFAULT_CODE = "default"

    code = models.CharField(_("Код профиля"), max_length=32, unique=True, default=DEFAULT_CODE)
    is_enabled = models.BooleanField(_("Nova Pay включен"), default=False)

    merchant_id = models.CharField(_("Merchant ID"), max_length=64, blank=True)
    api_token = models.CharField(_("API token (X-Sign)"), max_length=255, blank=True)
    last_connection_checked_at = models.DateTimeField(_("Последняя проверка соединения"), blank=True, null=True)
    last_connection_ok = models.BooleanField(_("Последняя проверка успешна"), blank=True, null=True)
    last_connection_message = models.TextField(_("Сообщение последней проверки"), blank=True)

    class Meta:
        verbose_name = _("Настройки Nova Pay")
        verbose_name_plural = _("Настройки Nova Pay")

    def __str__(self) -> str:
        return f"NovaPaySettings:{self.code}"

    @property
    def api_token_masked(self) -> str:
        token = (self.api_token or "").strip()
        if not token:
            return ""
        if len(token) <= 8:
            return "*" * len(token)
        return f"{token[:4]}{'*' * (len(token) - 8)}{token[-4:]}"
