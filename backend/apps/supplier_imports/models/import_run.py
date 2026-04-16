from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class ImportRun(UUIDPrimaryKeyMixin, TimestampedMixin):
    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_SUCCESS = "success"
    STATUS_PARTIAL = "partial"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = (
        (STATUS_PENDING, _("Ожидает")),
        (STATUS_RUNNING, _("Выполняется")),
        (STATUS_SUCCESS, _("Успешно")),
        (STATUS_PARTIAL, _("Частично")),
        (STATUS_FAILED, _("Ошибка")),
    )

    source = models.ForeignKey(
        "supplier_imports.ImportSource",
        on_delete=models.CASCADE,
        related_name="runs",
        verbose_name=_("Источник"),
    )
    status = models.CharField(_("Статус"), max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    trigger = models.CharField(_("Триггер"), max_length=64, default="manual")
    dry_run = models.BooleanField(_("Тестовый запуск"), default=False)

    started_at = models.DateTimeField(_("Начат"), blank=True, null=True)
    finished_at = models.DateTimeField(_("Завершен"), blank=True, null=True)

    processed_rows = models.PositiveIntegerField(_("Обработано строк"), default=0)
    parsed_rows = models.PositiveIntegerField(_("Разобрано строк"), default=0)
    offers_created = models.PositiveIntegerField(_("Офферов создано"), default=0)
    offers_updated = models.PositiveIntegerField(_("Офферов обновлено"), default=0)
    offers_skipped = models.PositiveIntegerField(_("Офферов пропущено"), default=0)
    errors_count = models.PositiveIntegerField(_("Ошибок"), default=0)

    repriced_products = models.PositiveIntegerField(_("Переоценено товаров"), default=0)
    reindexed_products = models.PositiveIntegerField(_("Переиндексировано товаров"), default=0)

    summary = models.JSONField(_("Сводка"), default=dict, blank=True)
    note = models.TextField(_("Примечание"), blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("Запуск импорта")
        verbose_name_plural = _("Запуски импорта")

    def __str__(self) -> str:
        return f"{self.source.code} / {self.created_at:%Y-%m-%d %H:%M:%S} / {self.status}"
