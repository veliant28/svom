from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class ImportRunQuality(UUIDPrimaryKeyMixin, TimestampedMixin):
    run = models.OneToOneField(
        "supplier_imports.ImportRun",
        on_delete=models.CASCADE,
        related_name="quality",
        verbose_name=_("Запуск"),
    )
    source = models.ForeignKey(
        "supplier_imports.ImportSource",
        on_delete=models.CASCADE,
        related_name="quality_runs",
        verbose_name=_("Источник"),
    )
    previous_run = models.ForeignKey(
        "supplier_imports.ImportRun",
        on_delete=models.SET_NULL,
        related_name="quality_comparisons",
        blank=True,
        null=True,
        verbose_name=_("Предыдущий запуск"),
    )
    status = models.CharField(_("Статус"), max_length=16, default="pending")

    total_rows = models.PositiveIntegerField(_("Всего строк"), default=0)
    matched_rows = models.PositiveIntegerField(_("Сопоставленные строки"), default=0)
    auto_matched_rows = models.PositiveIntegerField(_("Автосопоставленные строки"), default=0)
    manual_matched_rows = models.PositiveIntegerField(_("Сопоставленные вручную строки"), default=0)
    ignored_rows = models.PositiveIntegerField(_("Игнорированные строки"), default=0)
    unmatched_rows = models.PositiveIntegerField(_("Несопоставленные строки"), default=0)
    conflict_rows = models.PositiveIntegerField(_("Конфликтные строки"), default=0)
    error_rows = models.PositiveIntegerField(_("Строки с ошибками"), default=0)

    match_rate = models.DecimalField(_("Доля сопоставления"), max_digits=6, decimal_places=2, default=0)
    error_rate = models.DecimalField(_("Доля ошибок"), max_digits=6, decimal_places=2, default=0)
    match_rate_delta = models.DecimalField(_("Изменение доли сопоставления"), max_digits=6, decimal_places=2, default=0)
    error_rate_delta = models.DecimalField(_("Изменение доли ошибок"), max_digits=6, decimal_places=2, default=0)

    flags = models.JSONField(_("Флаги"), default=list, blank=True)
    requires_operator_attention = models.BooleanField(_("Требует внимания оператора"), default=False)
    summary = models.JSONField(_("Сводка"), default=dict, blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("Качество запуска импорта")
        verbose_name_plural = _("Качество запусков импорта")
        indexes = [
            models.Index(fields=("source", "-created_at")),
            models.Index(fields=("requires_operator_attention", "-created_at")),
            models.Index(fields=("status", "-created_at")),
        ]

    def __str__(self) -> str:
        return f"качество:{self.source.code}:{self.run_id}"
