from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class OrderItem(UUIDPrimaryKeyMixin, TimestampedMixin):
    PROCUREMENT_PENDING = "pending"
    PROCUREMENT_AWAITING = "awaiting_procurement"
    PROCUREMENT_RESERVED = "reserved"
    PROCUREMENT_PARTIALLY_RESERVED = "partially_reserved"
    PROCUREMENT_UNAVAILABLE = "unavailable"
    PROCUREMENT_CANCELLED = "cancelled"

    PROCUREMENT_STATUS_CHOICES = (
        (PROCUREMENT_PENDING, _("Ожидает")),
        (PROCUREMENT_AWAITING, _("Ожидает закупки")),
        (PROCUREMENT_RESERVED, _("Зарезервирован")),
        (PROCUREMENT_PARTIALLY_RESERVED, _("Частично зарезервирован")),
        (PROCUREMENT_UNAVAILABLE, _("Недоступен")),
        (PROCUREMENT_CANCELLED, _("Отменен")),
    )

    SHORTAGE_STOCK = "stock_shortage"
    SHORTAGE_PRICE_CHANGED = "price_changed"
    SHORTAGE_UNAVAILABLE = "supplier_unavailable"
    SHORTAGE_LEAD_TIME = "lead_time_too_long"
    SHORTAGE_OTHER = "other"

    SHORTAGE_REASON_CHOICES = (
        (SHORTAGE_STOCK, _("Недостаток остатка")),
        (SHORTAGE_PRICE_CHANGED, _("Изменилась цена")),
        (SHORTAGE_UNAVAILABLE, _("Поставщик недоступен")),
        (SHORTAGE_LEAD_TIME, _("Слишком долгий срок поставки")),
        (SHORTAGE_OTHER, _("Другое")),
    )

    order = models.ForeignKey(
        "commerce.Order",
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name=_("Заказ"),
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.PROTECT,
        related_name="order_items",
        verbose_name=_("Товар"),
    )

    product_name = models.CharField(_("Название товара"), max_length=255)
    product_sku = models.CharField(_("SKU товара"), max_length=64)

    quantity = models.PositiveIntegerField(_("Количество"), default=1)
    unit_price = models.DecimalField(_("Цена за единицу"), max_digits=12, decimal_places=2, default=0)
    line_total = models.DecimalField(_("Сумма позиции"), max_digits=12, decimal_places=2, default=0)
    procurement_status = models.CharField(_("Статус закупки"), max_length=32, choices=PROCUREMENT_STATUS_CHOICES, default=PROCUREMENT_PENDING)
    recommended_supplier_offer = models.ForeignKey(
        "pricing.SupplierOffer",
        on_delete=models.SET_NULL,
        related_name="recommended_for_order_items",
        blank=True,
        null=True,
        verbose_name=_("Рекомендованный оффер поставщика"),
    )
    selected_supplier_offer = models.ForeignKey(
        "pricing.SupplierOffer",
        on_delete=models.SET_NULL,
        related_name="selected_for_order_items",
        blank=True,
        null=True,
        verbose_name=_("Выбранный оффер поставщика"),
    )
    shortage_reason_code = models.CharField(_("Причина дефицита"), max_length=32, choices=SHORTAGE_REASON_CHOICES, blank=True)
    shortage_reason_note = models.TextField(_("Комментарий по дефициту"), blank=True)
    operator_note = models.TextField(_("Комментарий оператора"), blank=True)

    snapshot_currency = models.CharField(_("Валюта снимка"), max_length=3, default="UAH")
    snapshot_sell_price = models.DecimalField(_("Цена продажи в снимке"), max_digits=12, decimal_places=2, default=0)
    snapshot_availability_status = models.CharField(_("Статус доступности в снимке"), max_length=32, default="")
    snapshot_availability_label = models.CharField(_("Подпись доступности в снимке"), max_length=64, default="")
    snapshot_estimated_delivery_days = models.PositiveSmallIntegerField(_("Срок доставки в снимке, дней"), blank=True, null=True)
    snapshot_procurement_source = models.CharField(_("Источник закупки в снимке"), max_length=255, default="")
    snapshot_selected_offer = models.ForeignKey(
        "pricing.SupplierOffer",
        on_delete=models.SET_NULL,
        related_name="snapshot_for_order_items",
        blank=True,
        null=True,
        verbose_name=_("Выбранный оффер в снимке"),
    )
    snapshot_offer_explainability = models.JSONField(_("Детали выбора оффера"), default=dict, blank=True)

    class Meta:
        ordering = ("created_at",)
        verbose_name = _("Позиция заказа")
        verbose_name_plural = _("Позиции заказа")

    def __str__(self) -> str:
        return f"{self.order_id}:{self.product_sku}"
