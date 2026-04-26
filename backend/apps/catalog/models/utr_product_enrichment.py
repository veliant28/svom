from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class UtrProductEnrichment(UUIDPrimaryKeyMixin, TimestampedMixin):
    STATUS_PENDING = "pending"
    STATUS_QUEUED = "queued"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_FETCHED = "fetched"
    STATUS_FAILED = "failed"
    STATUS_UNAVAILABLE = "unavailable"

    STATUS_CHOICES = (
        (STATUS_PENDING, _("Ожидает")),
        (STATUS_QUEUED, _("В очереди")),
        (STATUS_IN_PROGRESS, _("Выполняется")),
        (STATUS_FETCHED, _("Получено")),
        (STATUS_FAILED, _("Ошибка")),
        (STATUS_UNAVAILABLE, _("Недоступно")),
    )

    product = models.OneToOneField(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="utr_enrichment",
        verbose_name=_("Товар"),
    )
    utr_detail_id = models.CharField(_("UTR detail ID"), max_length=64, blank=True, db_index=True)
    status = models.CharField(_("Статус"), max_length=24, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    detail_payload = models.JSONField(_("UTR detail payload"), default=dict, blank=True)
    characteristics_payload = models.JSONField(_("UTR characteristics payload"), default=list, blank=True)
    images_payload = models.JSONField(_("UTR images payload"), default=list, blank=True)
    last_attempt_at = models.DateTimeField(_("Последняя попытка"), blank=True, null=True)
    fetched_at = models.DateTimeField(_("Получено"), blank=True, null=True)
    next_retry_at = models.DateTimeField(_("Следующая попытка"), blank=True, null=True)
    error_message = models.TextField(_("Текст ошибки"), blank=True)

    class Meta:
        ordering = ("product__name",)
        verbose_name = _("UTR обогащение товара")
        verbose_name_plural = _("UTR обогащения товаров")
        indexes = [
            models.Index(fields=("status", "next_retry_at"), name="cat_utr_enrich_retry_idx"),
            models.Index(fields=("utr_detail_id",), name="cat_utr_enrich_did_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.product_id} [{self.status}]"
