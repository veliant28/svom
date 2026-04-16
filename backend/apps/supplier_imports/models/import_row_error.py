from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class ImportRowError(UUIDPrimaryKeyMixin, TimestampedMixin):
    run = models.ForeignKey(
        "supplier_imports.ImportRun",
        on_delete=models.CASCADE,
        related_name="row_errors",
        verbose_name=_("Запуск"),
    )
    source = models.ForeignKey(
        "supplier_imports.ImportSource",
        on_delete=models.CASCADE,
        related_name="row_errors",
        verbose_name=_("Источник"),
    )
    artifact = models.ForeignKey(
        "supplier_imports.ImportArtifact",
        on_delete=models.SET_NULL,
        related_name="row_errors",
        blank=True,
        null=True,
        verbose_name=_("Артефакт"),
    )

    row_number = models.PositiveIntegerField(_("Номер строки"), blank=True, null=True)
    external_sku = models.CharField(_("Внешний SKU"), max_length=128, blank=True)
    error_code = models.CharField(_("Код ошибки"), max_length=64, blank=True)
    message = models.TextField(_("Сообщение"))
    raw_payload = models.JSONField(_("Полезная нагрузка"), default=dict, blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("Ошибка строки импорта")
        verbose_name_plural = _("Ошибки строк импорта")

    def __str__(self) -> str:
        return f"{self.source.code}:{self.error_code or 'ошибка'}"
