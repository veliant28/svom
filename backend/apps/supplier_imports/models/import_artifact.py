from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class ImportArtifact(UUIDPrimaryKeyMixin, TimestampedMixin):
    STATUS_PENDING = "pending"
    STATUS_PROCESSED = "processed"
    STATUS_SKIPPED = "skipped"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = (
        (STATUS_PENDING, _("Ожидает")),
        (STATUS_PROCESSED, _("Обработан")),
        (STATUS_SKIPPED, _("Пропущен")),
        (STATUS_FAILED, _("Ошибка")),
    )

    run = models.ForeignKey(
        "supplier_imports.ImportRun",
        on_delete=models.CASCADE,
        related_name="artifacts",
        verbose_name=_("Запуск"),
    )
    source = models.ForeignKey(
        "supplier_imports.ImportSource",
        on_delete=models.CASCADE,
        related_name="artifacts",
        verbose_name=_("Источник"),
    )
    file_name = models.CharField(_("Имя файла"), max_length=255)
    file_path = models.CharField(_("Путь к файлу"), max_length=1024)
    file_format = models.CharField(_("Формат файла"), max_length=32, blank=True)
    file_size = models.BigIntegerField(_("Размер файла"), default=0)
    checksum_sha1 = models.CharField(_("SHA1"), max_length=40, blank=True)

    status = models.CharField(_("Статус"), max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    parsed_rows = models.PositiveIntegerField(_("Разобрано строк"), default=0)
    errors_count = models.PositiveIntegerField(_("Ошибок"), default=0)

    class Meta:
        ordering = ("file_name",)
        verbose_name = _("Артефакт импорта")
        verbose_name_plural = _("Артефакты импорта")

    def __str__(self) -> str:
        return f"{self.source.code}:{self.file_name}"
