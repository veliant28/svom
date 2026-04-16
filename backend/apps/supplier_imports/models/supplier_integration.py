from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class SupplierIntegration(UUIDPrimaryKeyMixin, TimestampedMixin):
    supplier = models.OneToOneField(
        "pricing.Supplier",
        on_delete=models.PROTECT,
        related_name="integration",
        verbose_name=_("Поставщик"),
    )
    source = models.OneToOneField(
        "supplier_imports.ImportSource",
        on_delete=models.PROTECT,
        related_name="integration",
        verbose_name=_("Источник импорта"),
        blank=True,
        null=True,
    )

    login = models.CharField(_("Логин"), max_length=255, blank=True)
    password = models.CharField(_("Пароль"), max_length=255, blank=True)
    browser_fingerprint = models.CharField(_("Подпись клиента"), max_length=128, blank=True, default="svom-backoffice")

    access_token = models.TextField(_("Access token"), blank=True)
    refresh_token = models.TextField(_("Refresh token"), blank=True)
    access_token_expires_at = models.DateTimeField(_("Access token действует до"), blank=True, null=True)
    refresh_token_expires_at = models.DateTimeField(_("Refresh token действует до"), blank=True, null=True)
    token_obtained_at = models.DateTimeField(_("Токен получен"), blank=True, null=True)
    last_token_refresh_at = models.DateTimeField(_("Последнее обновление токена"), blank=True, null=True)
    last_token_error_at = models.DateTimeField(_("Последняя ошибка токена"), blank=True, null=True)
    last_token_error_message = models.TextField(_("Текст ошибки токена"), blank=True)
    credentials_updated_at = models.DateTimeField(_("Когда обновлены credentials"), blank=True, null=True)
    is_enabled = models.BooleanField(_("Интеграция включена"), default=True)

    last_request_at = models.DateTimeField(_("Последний запрос к API"), blank=True, null=True)
    next_allowed_request_at = models.DateTimeField(_("Следующий разрешенный запрос"), blank=True, null=True)

    last_successful_import_at = models.DateTimeField(_("Последний успешный импорт"), blank=True, null=True)
    last_failed_import_at = models.DateTimeField(_("Последний неуспешный импорт"), blank=True, null=True)
    last_import_error_message = models.TextField(_("Текст последней ошибки импорта"), blank=True)

    last_connection_check_at = models.DateTimeField(_("Последняя проверка подключения"), blank=True, null=True)
    last_connection_status = models.CharField(_("Статус подключения"), max_length=32, blank=True, default="")

    last_brands_import_at = models.DateTimeField(_("Последний импорт брендов"), blank=True, null=True)
    last_brands_import_count = models.PositiveIntegerField(_("Количество брендов последнего импорта"), default=0)
    last_brands_import_error_at = models.DateTimeField(_("Последняя ошибка импорта брендов"), blank=True, null=True)
    last_brands_import_error_message = models.TextField(_("Текст ошибки импорта брендов"), blank=True)

    class Meta:
        ordering = ("supplier__name",)
        verbose_name = _("Интеграция поставщика")
        verbose_name_plural = _("Интеграции поставщиков")

    def __str__(self) -> str:
        return f"{self.supplier.name} ({self.supplier.code})"

    @staticmethod
    def mask_secret(value: str) -> str:
        if not value:
            return ""
        if len(value) <= 8:
            return "*" * len(value)
        return f"{value[:4]}...{value[-4:]}"

    @property
    def masked_access_token(self) -> str:
        return self.mask_secret(self.access_token)

    @property
    def masked_refresh_token(self) -> str:
        return self.mask_secret(self.refresh_token)
