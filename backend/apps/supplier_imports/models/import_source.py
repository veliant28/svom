from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class ImportSource(UUIDPrimaryKeyMixin, TimestampedMixin):
    PARSER_UTR = "utr"
    PARSER_GPL = "gpl"

    PARSER_CHOICES = (
        (PARSER_UTR, "UTR"),
        (PARSER_GPL, "GPL"),
    )

    code = models.SlugField(_("Код"), max_length=64, unique=True)
    name = models.CharField(_("Название"), max_length=180)
    supplier = models.ForeignKey(
        "pricing.Supplier",
        on_delete=models.PROTECT,
        related_name="import_sources",
        verbose_name=_("Поставщик"),
    )
    parser_type = models.CharField(_("Тип парсера"), max_length=16, choices=PARSER_CHOICES)
    input_path = models.CharField(_("Путь к входному файлу"), max_length=512, blank=True)
    file_patterns = models.JSONField(_("Маски файлов"), default=list, blank=True)
    mapping_config = models.JSONField(_("Конфигурация маппинга"), default=dict, blank=True)
    parser_options = models.JSONField(_("Опции парсера"), default=dict, blank=True)
    default_currency = models.CharField(_("Валюта по умолчанию"), max_length=3, default="UAH")

    # Legacy flags kept for compatibility with existing flows.
    auto_reprice = models.BooleanField(_("Автопереоценка"), default=True)
    auto_reindex = models.BooleanField(_("Автоиндексация"), default=False)

    # Stage 13 scheduling/automation settings.
    is_auto_import_enabled = models.BooleanField(_("Автоимпорт включен"), default=False)
    schedule_cron = models.CharField(_("Cron-расписание"), max_length=120, blank=True, default="")
    schedule_timezone = models.CharField(_("Часовой пояс расписания"), max_length=64, default="Europe/Kyiv")
    auto_reprice_after_import = models.BooleanField(_("Автопереоценка после импорта"), default=True)
    auto_reindex_after_import = models.BooleanField(_("Автоиндексация после импорта"), default=False)
    last_started_at = models.DateTimeField(_("Последний старт"), blank=True, null=True)
    last_finished_at = models.DateTimeField(_("Последнее завершение"), blank=True, null=True)
    last_success_at = models.DateTimeField(_("Последний успешный запуск"), blank=True, null=True)
    last_failed_at = models.DateTimeField(_("Последний запуск с ошибкой"), blank=True, null=True)

    is_active = models.BooleanField(_("Активен"), default=True)

    class Meta:
        ordering = ("name",)
        verbose_name = _("Источник импорта")
        verbose_name_plural = _("Источники импорта")

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"
