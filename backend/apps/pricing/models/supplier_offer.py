from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class SupplierOffer(UUIDPrimaryKeyMixin, TimestampedMixin):
    supplier = models.ForeignKey(
        "pricing.Supplier",
        on_delete=models.CASCADE,
        related_name="offers",
        verbose_name=_("Поставщик"),
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="supplier_offers",
        verbose_name=_("Товар"),
    )
    supplier_sku = models.CharField(_("SKU поставщика"), max_length=128)
    currency = models.CharField(_("Валюта"), max_length=3, default="UAH")
    purchase_price = models.DecimalField(_("Закупочная цена"), max_digits=12, decimal_places=2)
    price_levels = models.JSONField(_("Уровни цен"), default=list, blank=True)
    logistics_cost = models.DecimalField(_("Логистика"), max_digits=12, decimal_places=2, default=0)
    extra_cost = models.DecimalField(_("Дополнительные затраты"), max_digits=12, decimal_places=2, default=0)
    stock_qty = models.IntegerField(_("Остаток"), default=0)
    lead_time_days = models.PositiveSmallIntegerField(_("Срок поставки, дней"), default=0)
    is_available = models.BooleanField(_("Доступен"), default=True)
    last_seen_at = models.DateTimeField(_("Последний раз в прайсе"), blank=True, null=True)

    class Meta:
        ordering = ("supplier__name", "product__name")
        verbose_name = _("Оффер поставщика")
        verbose_name_plural = _("Офферы поставщиков")
        indexes = [
            models.Index(fields=("supplier", "last_seen_at"), name="pricing_so_supplier_seen_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("supplier", "product", "supplier_sku"),
                name="pricing_supplieroffer_unique_supplier_product_sku",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.supplier} / {self.product} ({self.supplier_sku})"
