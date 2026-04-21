from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class OrderPayment(UUIDPrimaryKeyMixin, TimestampedMixin):
    PROVIDER_MONOBANK = "monobank"
    PROVIDER_LIQPAY = "liqpay"
    PROVIDER_COD = "cash_on_delivery"

    PROVIDER_CHOICES = (
        (PROVIDER_MONOBANK, _("Monobank")),
        (PROVIDER_LIQPAY, _("LiqPay")),
        (PROVIDER_COD, _("Наложенный платеж")),
    )

    METHOD_MONOBANK = "monobank"
    METHOD_LIQPAY = "liqpay"
    METHOD_CASH_ON_DELIVERY = "cash_on_delivery"

    METHOD_CHOICES = (
        (METHOD_MONOBANK, _("Monobank")),
        (METHOD_LIQPAY, _("LiqPay")),
        (METHOD_CASH_ON_DELIVERY, _("Наложенный платеж")),
    )

    STATUS_PENDING = "pending"
    STATUS_CREATED = "created"
    STATUS_PROCESSING = "processing"
    STATUS_HOLD = "hold"
    STATUS_SUCCESS = "success"
    STATUS_FAILURE = "failure"
    STATUS_REVERSED = "reversed"
    STATUS_EXPIRED = "expired"

    STATUS_CHOICES = (
        (STATUS_PENDING, _("Ожидает создания")),
        (STATUS_CREATED, _("Создан")),
        (STATUS_PROCESSING, _("Обрабатывается")),
        (STATUS_HOLD, _("Холд")),
        (STATUS_SUCCESS, _("Успешно")),
        (STATUS_FAILURE, _("Ошибка")),
        (STATUS_REVERSED, _("Отменен")),
        (STATUS_EXPIRED, _("Истек")),
    )

    order = models.OneToOneField(
        "commerce.Order",
        on_delete=models.CASCADE,
        related_name="payment",
        verbose_name=_("Заказ"),
    )
    provider = models.CharField(_("Провайдер оплаты"), max_length=32, choices=PROVIDER_CHOICES, default=PROVIDER_COD)
    method = models.CharField(_("Метод оплаты"), max_length=32, choices=METHOD_CHOICES, default=METHOD_CASH_ON_DELIVERY)
    status = models.CharField(_("Статус оплаты"), max_length=32, choices=STATUS_CHOICES, default=STATUS_PENDING)

    amount = models.DecimalField(_("Сумма"), max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(_("Валюта"), max_length=3, default="UAH")

    monobank_invoice_id = models.CharField(_("Invoice ID Monobank"), max_length=128, blank=True)
    monobank_reference = models.CharField(_("Reference Monobank"), max_length=128, blank=True)
    monobank_page_url = models.URLField(_("Page URL Monobank"), max_length=1024, blank=True)
    liqpay_payment_id = models.CharField(_("Payment ID LiqPay"), max_length=128, blank=True)
    liqpay_order_id = models.CharField(_("Order ID LiqPay"), max_length=128, blank=True)
    liqpay_page_url = models.URLField(_("Page URL LiqPay"), max_length=1024, blank=True)

    failure_reason = models.TextField(_("Причина ошибки"), blank=True)
    provider_created_at = models.DateTimeField(_("Создан у провайдера"), blank=True, null=True)
    provider_modified_at = models.DateTimeField(_("Изменен у провайдера"), blank=True, null=True)
    last_webhook_received_at = models.DateTimeField(_("Последний webhook"), blank=True, null=True)
    last_sync_at = models.DateTimeField(_("Последняя синхронизация"), blank=True, null=True)

    raw_create_payload = models.JSONField(_("Сырой payload создания"), default=dict, blank=True)
    raw_create_response = models.JSONField(_("Сырой ответ создания"), default=dict, blank=True)
    raw_status_payload = models.JSONField(_("Сырой payload статуса"), default=dict, blank=True)
    raw_last_webhook_payload = models.JSONField(_("Сырой payload webhook"), default=dict, blank=True)

    class Meta:
        verbose_name = _("Оплата заказа")
        verbose_name_plural = _("Оплаты заказов")
        indexes = [
            models.Index(fields=("provider", "status"), name="com_ordpay_prov_stat_idx"),
            models.Index(fields=("monobank_invoice_id",), name="com_ordpay_invoice_idx"),
            models.Index(fields=("provider_modified_at",), name="com_ordpay_mod_at_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.order.order_number}:{self.provider}:{self.status}"
