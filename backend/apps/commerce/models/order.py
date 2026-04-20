from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class Order(UUIDPrimaryKeyMixin, TimestampedMixin):
    STATUS_NEW = "new"
    STATUS_CONFIRMED = "confirmed"
    STATUS_AWAITING_PROCUREMENT = "awaiting_procurement"
    STATUS_RESERVED = "reserved"
    STATUS_PARTIALLY_RESERVED = "partially_reserved"
    STATUS_READY_TO_SHIP = "ready_to_ship"
    STATUS_SHIPPED = "shipped"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"
    STATUS_DRAFT = "draft"
    STATUS_PLACED = "placed"

    STATUS_CHOICES = (
        (STATUS_NEW, _("Новый")),
        (STATUS_CONFIRMED, _("Подтвержден")),
        (STATUS_AWAITING_PROCUREMENT, _("Ожидает закупки")),
        (STATUS_RESERVED, _("Зарезервирован")),
        (STATUS_PARTIALLY_RESERVED, _("Частично зарезервирован")),
        (STATUS_READY_TO_SHIP, _("Готов к отправке")),
        (STATUS_SHIPPED, _("Отправлен")),
        (STATUS_COMPLETED, _("Завершен")),
        (STATUS_CANCELLED, _("Отменен")),
        (STATUS_DRAFT, _("Черновик (legacy)")),
        (STATUS_PLACED, _("Оформлен (legacy)")),
    )

    CANCELLATION_CUSTOMER_REQUEST = "customer_request"
    CANCELLATION_PAYMENT_FAILED = "payment_failed"
    CANCELLATION_SUPPLIER_SHORTAGE = "supplier_shortage"
    CANCELLATION_UNAVAILABLE = "unavailable"
    CANCELLATION_OPERATOR_DECISION = "operator_decision"
    CANCELLATION_OTHER = "other"

    CANCELLATION_REASON_CHOICES = (
        (CANCELLATION_CUSTOMER_REQUEST, _("Запрос клиента")),
        (CANCELLATION_PAYMENT_FAILED, _("Ошибка оплаты")),
        (CANCELLATION_SUPPLIER_SHORTAGE, _("Дефицит у поставщика")),
        (CANCELLATION_UNAVAILABLE, _("Недоступно")),
        (CANCELLATION_OPERATOR_DECISION, _("Решение оператора")),
        (CANCELLATION_OTHER, _("Другое")),
    )

    DELIVERY_PICKUP = "pickup"
    DELIVERY_COURIER = "courier"
    DELIVERY_NOVA_POSHTA = "nova_poshta"

    DELIVERY_METHOD_CHOICES = (
        (DELIVERY_PICKUP, _("Самовывоз")),
        (DELIVERY_COURIER, _("Курьер")),
        (DELIVERY_NOVA_POSHTA, _("Новая Почта")),
    )

    PAYMENT_CASH_ON_DELIVERY = "cash_on_delivery"
    PAYMENT_MONOBANK = "monobank"
    PAYMENT_CARD_PLACEHOLDER = "card_placeholder"

    PAYMENT_METHOD_CHOICES = (
        (PAYMENT_MONOBANK, _("Monobank")),
        (PAYMENT_CASH_ON_DELIVERY, _("Наложенный платеж")),
        (PAYMENT_CARD_PLACEHOLDER, _("Оплата картой (legacy)")),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders",
        verbose_name=_("Пользователь"),
    )
    order_number = models.CharField(_("Номер заказа"), max_length=32, unique=True)
    status = models.CharField(_("Статус"), max_length=32, choices=STATUS_CHOICES, default=STATUS_NEW)

    contact_full_name = models.CharField(_("ФИО"), max_length=255)
    contact_phone = models.CharField(_("Телефон"), max_length=32)
    contact_email = models.EmailField(_("Email"))

    delivery_method = models.CharField(_("Способ доставки"), max_length=32, choices=DELIVERY_METHOD_CHOICES)
    delivery_address = models.CharField(_("Адрес доставки"), max_length=500, blank=True)
    delivery_snapshot = models.JSONField(_("Снимок доставки"), default=dict, blank=True)
    payment_method = models.CharField(_("Способ оплаты"), max_length=32, choices=PAYMENT_METHOD_CHOICES)

    subtotal = models.DecimalField(_("Промежуточная сумма"), max_digits=12, decimal_places=2, default=0)
    delivery_fee = models.DecimalField(_("Стоимость доставки"), max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(_("Итоговая сумма"), max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(_("Валюта"), max_length=3, default="UAH")

    customer_comment = models.TextField(_("Комментарий клиента"), blank=True)
    internal_notes = models.TextField(_("Внутренние заметки"), blank=True)
    operator_notes = models.TextField(_("Заметки оператора"), blank=True)
    cancellation_reason_code = models.CharField(_("Причина отмены"), max_length=32, choices=CANCELLATION_REASON_CHOICES, blank=True)
    cancellation_reason_note = models.TextField(_("Комментарий к отмене"), blank=True)
    placed_at = models.DateTimeField(_("Дата оформления"), auto_now_add=True)

    class Meta:
        ordering = ("-placed_at", "-created_at")
        verbose_name = _("Заказ")
        verbose_name_plural = _("Заказы")
        indexes = [
            models.Index(fields=("user", "status"), name="commerce_order_user_status_idx"),
            models.Index(fields=("order_number",), name="commerce_order_number_idx"),
        ]

    def __str__(self) -> str:
        return self.order_number
