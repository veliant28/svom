from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class VchasnoKasaSettings(UUIDPrimaryKeyMixin, TimestampedMixin):
    DEFAULT_CODE = "default"

    code = models.CharField(_("Код профиля"), max_length=32, unique=True, default=DEFAULT_CODE)
    is_enabled = models.BooleanField(_("Вчасно.Каса включена"), default=False)

    api_token = models.CharField(_("Токен кассы"), max_length=255, blank=True)
    rro_fn = models.CharField(_("Фискальный номер РРО/ПРРО"), max_length=64, blank=True)
    default_payment_type = models.PositiveSmallIntegerField(_("Тип оплаты по умолчанию"), default=1)
    default_tax_group = models.CharField(_("Налоговая группа по умолчанию"), max_length=32, blank=True)
    auto_issue_on_completed = models.BooleanField(_("Автоматически создавать чек при завершении"), default=True)
    send_customer_email = models.BooleanField(_("Передавать email клиента"), default=True)

    last_connection_checked_at = models.DateTimeField(_("Последняя проверка соединения"), blank=True, null=True)
    last_connection_ok = models.BooleanField(_("Последняя проверка успешна"), blank=True, null=True)
    last_connection_message = models.TextField(_("Сообщение последней проверки"), blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_vchasno_kasa_settings",
        blank=True,
        null=True,
        verbose_name=_("Создал"),
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="updated_vchasno_kasa_settings",
        blank=True,
        null=True,
        verbose_name=_("Обновил"),
    )

    class Meta:
        verbose_name = _("Настройки Вчасно.Каса")
        verbose_name_plural = _("Настройки Вчасно.Каса")

    def __str__(self) -> str:
        return f"VchasnoKasaSettings:{self.code}"

    @property
    def api_token_masked(self) -> str:
        token = (self.api_token or "").strip()
        if not token:
            return ""
        if len(token) <= 4:
            return "•" * len(token)
        return f"{'•' * max(8, len(token) - 4)}{token[-4:]}"
