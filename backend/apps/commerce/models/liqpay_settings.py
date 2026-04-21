from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class LiqPaySettings(UUIDPrimaryKeyMixin, TimestampedMixin):
    DEFAULT_CODE = "default"

    code = models.CharField(_("Код профиля"), max_length=32, unique=True, default=DEFAULT_CODE)
    is_enabled = models.BooleanField(_("LiqPay включен"), default=False)

    public_key = models.CharField(_("Public key"), max_length=255, blank=True)
    private_key = models.CharField(_("Private key"), max_length=255, blank=True)
    last_connection_checked_at = models.DateTimeField(_("Последняя проверка соединения"), blank=True, null=True)
    last_connection_ok = models.BooleanField(_("Последняя проверка успешна"), blank=True, null=True)
    last_connection_message = models.TextField(_("Сообщение последней проверки"), blank=True)

    class Meta:
        verbose_name = _("Настройки LiqPay")
        verbose_name_plural = _("Настройки LiqPay")

    def __str__(self) -> str:
        return f"LiqPaySettings:{self.code}"

    @property
    def public_key_masked(self) -> str:
        token = (self.public_key or "").strip()
        if not token:
            return ""
        if len(token) <= 8:
            return "*" * len(token)
        return f"{token[:4]}{'*' * (len(token) - 8)}{token[-4:]}"

    @property
    def private_key_masked(self) -> str:
        token = (self.private_key or "").strip()
        if not token:
            return ""
        if len(token) <= 8:
            return "*" * len(token)
        return f"{token[:4]}{'*' * (len(token) - 8)}{token[-4:]}"
