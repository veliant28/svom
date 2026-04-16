from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class SupplierPriceList(UUIDPrimaryKeyMixin, TimestampedMixin):
    STATUS_GENERATING = "generating"
    STATUS_READY = "ready"
    STATUS_DOWNLOADED = "downloaded"
    STATUS_IMPORTED = "imported"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = (
        (STATUS_GENERATING, _("Генерируется")),
        (STATUS_READY, _("Готов")),
        (STATUS_DOWNLOADED, _("Скачан")),
        (STATUS_IMPORTED, _("Импортирован")),
        (STATUS_FAILED, _("Ошибка")),
    )

    supplier = models.ForeignKey(
        "pricing.Supplier",
        on_delete=models.CASCADE,
        related_name="price_lists",
        verbose_name=_("Поставщик"),
    )
    source = models.ForeignKey(
        "supplier_imports.ImportSource",
        on_delete=models.CASCADE,
        related_name="price_lists",
        verbose_name=_("Источник"),
    )
    integration = models.ForeignKey(
        "supplier_imports.SupplierIntegration",
        on_delete=models.SET_NULL,
        related_name="price_lists",
        verbose_name=_("Интеграция"),
        blank=True,
        null=True,
    )

    status = models.CharField(_("Статус"), max_length=24, choices=STATUS_CHOICES, default=STATUS_GENERATING, db_index=True)
    request_mode = models.CharField(_("Режим запроса"), max_length=32, default="local", blank=True)

    remote_id = models.CharField(_("ID прайса у поставщика"), max_length=128, blank=True, default="")
    remote_token = models.CharField(_("Токен прайса у поставщика"), max_length=255, blank=True, default="")
    remote_status = models.CharField(_("Статус прайса у поставщика"), max_length=64, blank=True, default="")

    requested_format = models.CharField(_("Запрошенный формат"), max_length=16, blank=True, default="")
    original_format = models.CharField(_("Исходный формат"), max_length=16, blank=True, default="")
    locale = models.CharField(_("Локаль"), max_length=16, blank=True, default="")

    is_in_stock = models.BooleanField(_("Только в наличии"), default=True)
    show_scancode = models.BooleanField(_("Показывать штрихкод"), default=False)
    utr_article = models.BooleanField(_("Показывать артикул UTR"), default=False)
    visible_brands = models.JSONField(_("Выбранные бренды"), default=list, blank=True)
    categories = models.JSONField(_("Выбранные категории"), default=list, blank=True)
    models_filter = models.JSONField(_("Выбранные модели"), default=list, blank=True)

    source_file_name = models.CharField(_("Имя файла источника"), max_length=255, blank=True, default="")
    source_file_path = models.CharField(_("Путь к исходному файлу"), max_length=1024, blank=True, default="")
    downloaded_file_path = models.CharField(_("Путь скачанного файла"), max_length=1024, blank=True, default="")

    file_size_label = models.CharField(_("Размер файла (текст)"), max_length=64, blank=True, default="")
    file_size_bytes = models.BigIntegerField(_("Размер файла (байты)"), default=0)

    price_columns = models.JSONField(_("Колонки цен"), default=list, blank=True)
    warehouse_columns = models.JSONField(_("Колонки складов"), default=list, blank=True)
    row_count = models.PositiveIntegerField(_("Количество строк"), default=0)

    requested_at = models.DateTimeField(_("Когда запрошен"), blank=True, null=True)
    expected_ready_at = models.DateTimeField(_("Ожидаемая готовность"), blank=True, null=True)
    generated_at = models.DateTimeField(_("Когда сформирован"), blank=True, null=True)
    downloaded_at = models.DateTimeField(_("Когда скачан"), blank=True, null=True)
    imported_at = models.DateTimeField(_("Когда импортирован"), blank=True, null=True)

    imported_run = models.ForeignKey(
        "supplier_imports.ImportRun",
        on_delete=models.SET_NULL,
        related_name="price_lists",
        verbose_name=_("Запуск импорта"),
        blank=True,
        null=True,
    )

    last_error_at = models.DateTimeField(_("Когда произошла последняя ошибка"), blank=True, null=True)
    last_error_message = models.TextField(_("Текст последней ошибки"), blank=True)

    request_payload = models.JSONField(_("Payload запроса"), default=dict, blank=True)
    response_payload = models.JSONField(_("Payload ответа"), default=dict, blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("Прайс поставщика")
        verbose_name_plural = _("Прайсы поставщиков")

    def __str__(self) -> str:
        marker = self.remote_id or str(self.id)
        return f"{self.source.code}:{marker}"
