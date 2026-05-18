from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class TelegramSettings(UUIDPrimaryKeyMixin, TimestampedMixin):
    DEFAULT_CODE = "default"

    code = models.CharField(_("Код профиля"), max_length=32, unique=True, default=DEFAULT_CODE)

    is_enabled = models.BooleanField(_("Telegram интеграция включена"), default=False)
    ops_enabled = models.BooleanField(_("Ops бот включен"), default=False)
    support_enabled = models.BooleanField(_("Support бот включен"), default=False)
    system_enabled = models.BooleanField(_("System бот включен"), default=False)

    ops_bot_token = models.CharField(_("Ops bot token"), max_length=255, blank=True, default="")
    ops_chat_id = models.CharField(_("Ops chat ID"), max_length=64, blank=True, default="")
    support_bot_token = models.CharField(_("Support bot token"), max_length=255, blank=True, default="")
    support_chat_id = models.CharField(_("Support chat ID"), max_length=64, blank=True, default="")
    system_bot_token = models.CharField(_("System bot token"), max_length=255, blank=True, default="")
    system_chat_id = models.CharField(_("System chat ID"), max_length=64, blank=True, default="")

    ops_notify_order_status = models.BooleanField(_("Ops: уведомления о статусах заказа"), default=True)
    ops_notify_waybill_created = models.BooleanField(_("Ops: уведомления о создании ТТН"), default=True)
    ops_notify_waybill_updated = models.BooleanField(_("Ops: уведомления о редактировании ТТН"), default=True)
    ops_notify_waybill_deleted = models.BooleanField(_("Ops: уведомления об удалении ТТН"), default=True)
    support_notify_new_thread = models.BooleanField(_("Support: новый чат поддержки"), default=True)
    support_notify_new_message = models.BooleanField(_("Support: новое сообщение от клиента"), default=True)
    system_notify_backup_status = models.BooleanField(_("System: бэкапы"), default=True)
    system_notify_import_status = models.BooleanField(_("System: импорты"), default=True)

    class Meta:
        verbose_name = _("Настройки Telegram")
        verbose_name_plural = _("Настройки Telegram")

    def __str__(self) -> str:
        return f"TelegramSettings:{self.code}"

    @staticmethod
    def _mask_secret(value: str) -> str:
        clean = str(value or "").strip()
        if not clean:
            return ""
        if len(clean) <= 8:
            return "*" * len(clean)
        return f"{clean[:4]}{'*' * (len(clean) - 8)}{clean[-4:]}"

    @property
    def ops_bot_token_masked(self) -> str:
        return self._mask_secret(self.ops_bot_token)

    @property
    def support_bot_token_masked(self) -> str:
        return self._mask_secret(self.support_bot_token)

    @property
    def system_bot_token_masked(self) -> str:
        return self._mask_secret(self.system_bot_token)
