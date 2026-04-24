from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class OrderReceipt(UUIDPrimaryKeyMixin, TimestampedMixin):
    PROVIDER_VCHASNO_KASA = "vchasno_kasa"
    TYPE_SALE = "sale"
    TYPE_RETURN = "return"

    PROVIDER_CHOICES = (
        (PROVIDER_VCHASNO_KASA, _("Вчасно.Каса")),
    )
    RECEIPT_TYPE_CHOICES = (
        (TYPE_SALE, _("Продажа")),
        (TYPE_RETURN, _("Возврат")),
    )

    order = models.ForeignKey(
        "commerce.Order",
        on_delete=models.CASCADE,
        related_name="receipts",
        verbose_name=_("Заказ"),
    )
    provider = models.CharField(_("Провайдер"), max_length=32, choices=PROVIDER_CHOICES, default=PROVIDER_VCHASNO_KASA)
    receipt_type = models.CharField(_("Тип чека"), max_length=16, choices=RECEIPT_TYPE_CHOICES, default=TYPE_SALE)

    external_order_id = models.UUIDField(_("Наш idempotency id"), default=uuid.uuid4, editable=False)
    vchasno_order_number = models.CharField(_("Номер заказа во Вчасно"), max_length=128, blank=True)
    check_fn = models.CharField(_("Фискальный номер чека"), max_length=128, blank=True)
    fiscal_status_code = models.IntegerField(_("Код фискального статуса"), blank=True, null=True)
    fiscal_status_key = models.CharField(_("Ключ фискального статуса"), max_length=64, blank=True)
    fiscal_status_label = models.CharField(_("Подпись фискального статуса"), max_length=255, blank=True)
    receipt_url = models.URLField(_("Ссылка на чек"), max_length=1024, blank=True)
    pdf_url = models.URLField(_("Ссылка на PDF"), max_length=1024, blank=True)
    email = models.EmailField(_("Email"), blank=True)
    email_sent_at = models.DateTimeField(_("Чек отправлен на email"), blank=True, null=True)
    fiscalized_at = models.DateTimeField(_("Фискализирован"), blank=True, null=True)

    error_code = models.CharField(_("Код ошибки"), max_length=64, blank=True)
    error_message = models.TextField(_("Текст ошибки"), blank=True)
    request_payload = models.JSONField(_("Payload запроса"), default=dict, blank=True)
    response_payload = models.JSONField(_("Payload ответа"), default=dict, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_order_receipts",
        blank=True,
        null=True,
        verbose_name=_("Создал"),
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="updated_order_receipts",
        blank=True,
        null=True,
        verbose_name=_("Обновил"),
    )

    class Meta:
        verbose_name = _("Фискальный чек")
        verbose_name_plural = _("Фискальные чеки")
        ordering = ("-updated_at", "-created_at")
        constraints = [
            models.UniqueConstraint(
                fields=("order", "provider", "receipt_type"),
                name="commerce_order_receipt_provider_type_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=("provider", "receipt_type"), name="com_rcpt_provider_type_idx"),
            models.Index(fields=("fiscal_status_code",), name="com_rcpt_status_code_idx"),
            models.Index(fields=("vchasno_order_number",), name="com_rcpt_order_number_idx"),
        ]

    def __str__(self) -> str:
        return self.vchasno_order_number or str(self.id)
