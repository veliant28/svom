from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class ProductPrice(UUIDPrimaryKeyMixin, TimestampedMixin):
    product = models.OneToOneField(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="product_price",
        verbose_name=_("Товар"),
    )
    currency = models.CharField(_("Валюта"), max_length=3, default="UAH")

    purchase_price = models.DecimalField(_("Закупочная цена"), max_digits=12, decimal_places=2, default=0)
    logistics_cost = models.DecimalField(_("Логистика"), max_digits=12, decimal_places=2, default=0)
    extra_cost = models.DecimalField(_("Дополнительные затраты"), max_digits=12, decimal_places=2, default=0)

    landed_cost = models.DecimalField(_("Себестоимость"), max_digits=12, decimal_places=2, default=0)
    raw_sale_price = models.DecimalField(_("Базовая цена продажи"), max_digits=12, decimal_places=2, default=0)
    final_price = models.DecimalField(_("Финальная цена"), max_digits=12, decimal_places=2, default=0)

    policy = models.ForeignKey(
        "pricing.PricingPolicy",
        on_delete=models.SET_NULL,
        related_name="product_prices",
        blank=True,
        null=True,
        verbose_name=_("Политика"),
    )
    auto_calculation_locked = models.BooleanField(_("Авторасчет заблокирован"), default=False)
    recalculated_at = models.DateTimeField(_("Пересчитано"), blank=True, null=True)

    class Meta:
        ordering = ("product__name",)
        verbose_name = _("Цена товара")
        verbose_name_plural = _("Цены товаров")

    def __str__(self) -> str:
        return f"{self.product} -> {self.final_price} {self.currency}"
