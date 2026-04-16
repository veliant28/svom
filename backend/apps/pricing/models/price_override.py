from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class PriceOverride(UUIDPrimaryKeyMixin, TimestampedMixin):
    product = models.OneToOneField(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="price_override",
        verbose_name=_("Товар"),
    )
    currency = models.CharField(_("Валюта"), max_length=3, default="UAH")
    override_price = models.DecimalField(_("Переопределенная цена"), max_digits=12, decimal_places=2)
    reason = models.CharField(_("Причина"), max_length=255, blank=True)
    is_active = models.BooleanField(_("Активно"), default=True)

    class Meta:
        ordering = ("product__name",)
        verbose_name = _("Переопределение цены")
        verbose_name_plural = _("Переопределения цен")

    def __str__(self) -> str:
        return f"Переопределение: {self.product}"
