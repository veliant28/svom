from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class ReturnRequest(UUIDPrimaryKeyMixin, TimestampedMixin):
    STATUS_NEW = "new"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_AWAITING_TTN = "awaiting_ttn"
    STATUS_IN_TRANSIT = "in_transit"
    STATUS_RECEIVED = "received"
    STATUS_ACCEPTED = "accepted"
    STATUS_REFUND_PROCESSING = "refund_processing"
    STATUS_REFUNDED = "refunded"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = (
        (STATUS_NEW, _("Новая заявка")),
        (STATUS_APPROVED, _("Одобрено")),
        (STATUS_REJECTED, _("Отказано")),
        (STATUS_AWAITING_TTN, _("Ожидаем ТТН")),
        (STATUS_IN_TRANSIT, _("В пути")),
        (STATUS_RECEIVED, _("Получено")),
        (STATUS_ACCEPTED, _("Принято")),
        (STATUS_REFUND_PROCESSING, _("Возврат средств в обработке")),
        (STATUS_REFUNDED, _("Средства возвращены")),
        (STATUS_CANCELLED, _("Отменено")),
    )

    REFUND_STATUS_NONE = "none"
    REFUND_STATUS_PROCESSING = "processing"
    REFUND_STATUS_DONE = "done"
    REFUND_STATUS_FAILED = "failed"
    REFUND_STATUS_CHOICES = (
        (REFUND_STATUS_NONE, _("Не начат")),
        (REFUND_STATUS_PROCESSING, _("В обработке")),
        (REFUND_STATUS_DONE, _("Выполнен")),
        (REFUND_STATUS_FAILED, _("Ошибка")),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="return_requests",
        verbose_name=_("Пользователь"),
    )
    order = models.ForeignKey(
        "commerce.Order",
        on_delete=models.PROTECT,
        related_name="return_requests",
        verbose_name=_("Заказ"),
    )
    return_number = models.CharField(_("Номер возврата"), max_length=32, unique=True, db_index=True)
    status = models.CharField(_("Статус"), max_length=32, choices=STATUS_CHOICES, default=STATUS_NEW, db_index=True)

    reason_comment = models.TextField(_("Причина возврата"))
    admin_comment = models.TextField(_("Комментарий администратора"), blank=True, default="")
    rejection_reason = models.TextField(_("Причина отказа"), blank=True, default="")

    refund_amount = models.DecimalField(_("Сумма возврата"), max_digits=12, decimal_places=2, default=Decimal("0.00"))
    refund_status = models.CharField(
        _("Статус возврата средств"),
        max_length=32,
        choices=REFUND_STATUS_CHOICES,
        default=REFUND_STATUS_NONE,
    )
    refund_method = models.CharField(_("Способ возврата"), max_length=64, blank=True, default="")

    customer_return_tracking_number = models.CharField(_("ТТН клиента"), max_length=32, blank=True, default="")
    customer_return_tracking_submitted_at = models.DateTimeField(_("ТТН отправлена"), blank=True, null=True)
    nova_poshta_return_status_code = models.CharField(_("Код статуса НП"), max_length=32, blank=True, default="")
    nova_poshta_return_status_text = models.CharField(_("Текст статуса НП"), max_length=255, blank=True, default="")
    nova_poshta_return_status_synced_at = models.DateTimeField(_("Статус НП синхронизирован"), blank=True, null=True)

    return_address_snapshot = models.JSONField(_("Снимок адреса возврата"), default=dict, blank=True)

    received_at = models.DateTimeField(_("Получено магазином"), blank=True, null=True)
    approved_at = models.DateTimeField(_("Одобрено"), blank=True, null=True)
    rejected_at = models.DateTimeField(_("Отклонено"), blank=True, null=True)
    accepted_at = models.DateTimeField(_("Принято"), blank=True, null=True)
    refund_processing_at = models.DateTimeField(_("Возврат в обработке"), blank=True, null=True)
    refunded_at = models.DateTimeField(_("Средства возвращены"), blank=True, null=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("Заявка на возврат")
        verbose_name_plural = _("Заявки на возврат")
        indexes = [
            models.Index(fields=("user", "-created_at"), name="com_ret_usr_created_idx"),
            models.Index(fields=("order", "-created_at"), name="com_ret_ord_created_idx"),
            models.Index(fields=("status", "-created_at"), name="com_ret_status_created_idx"),
        ]

    def __str__(self) -> str:
        return self.return_number


class ReturnRequestNumberSequence(models.Model):
    singleton_key = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    last_number = models.PositiveIntegerField(_("Последний номер возврата"), default=0)

    class Meta:
        verbose_name = _("Счетчик номеров возвратов")
        verbose_name_plural = _("Счетчики номеров возвратов")

    def __str__(self) -> str:
        return f"ReturnSequence:{self.last_number}"


class ReturnRequestItem(UUIDPrimaryKeyMixin, TimestampedMixin):
    return_request = models.ForeignKey(
        "commerce.ReturnRequest",
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name=_("Заявка на возврат"),
    )
    order_item = models.ForeignKey(
        "commerce.OrderItem",
        on_delete=models.PROTECT,
        related_name="return_items",
        verbose_name=_("Позиция заказа"),
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.PROTECT,
        related_name="return_items",
        verbose_name=_("Товар"),
    )

    product_name_snapshot = models.CharField(_("Название товара"), max_length=255)
    product_sku_snapshot = models.CharField(_("SKU товара"), max_length=64)

    quantity_ordered = models.PositiveIntegerField(_("Количество в заказе"), default=1)
    quantity_requested = models.PositiveIntegerField(_("Запрошено к возврату"), default=1)
    quantity_approved = models.PositiveIntegerField(_("Одобрено к возврату"), default=0)

    original_unit_price = models.DecimalField(_("Цена на момент заказа"), max_digits=12, decimal_places=2, default=Decimal("0.00"))
    original_line_total = models.DecimalField(_("Сумма позиции на момент заказа"), max_digits=12, decimal_places=2, default=Decimal("0.00"))
    refund_amount = models.DecimalField(_("Сумма возврата"), max_digits=12, decimal_places=2, default=Decimal("0.00"))

    is_returnable_snapshot = models.BooleanField(_("Возвратный товар"), default=True)
    non_returnable_reason_snapshot = models.CharField(_("Причина невозвратности"), max_length=255, blank=True, default="")

    class Meta:
        ordering = ("created_at",)
        verbose_name = _("Позиция заявки на возврат")
        verbose_name_plural = _("Позиции заявок на возврат")

    def __str__(self) -> str:
        return f"{self.return_request_id}:{self.product_sku_snapshot} x{self.quantity_requested}"


class ReturnEvent(UUIDPrimaryKeyMixin, TimestampedMixin):
    return_request = models.ForeignKey(
        "commerce.ReturnRequest",
        on_delete=models.CASCADE,
        related_name="events",
        verbose_name=_("Заявка на возврат"),
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="return_events",
        blank=True,
        null=True,
        verbose_name=_("Кто выполнил"),
    )
    from_status = models.CharField(_("Из статуса"), max_length=32, blank=True, default="")
    to_status = models.CharField(_("В статус"), max_length=32, blank=True, default="")
    comment = models.CharField(_("Комментарий"), max_length=500, blank=True, default="")
    metadata = models.JSONField(_("Метаданные"), default=dict, blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("Событие возврата")
        verbose_name_plural = _("События возврата")
        indexes = [
            models.Index(fields=("return_request", "-created_at"), name="com_ret_evt_req_created_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.return_request_id}:{self.from_status}->{self.to_status}"
