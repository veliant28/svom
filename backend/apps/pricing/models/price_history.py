from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class PriceHistory(UUIDPrimaryKeyMixin, TimestampedMixin):
    SOURCE_AUTO = "auto"
    SOURCE_MANUAL = "manual"
    SOURCE_IMPORT = "import"

    SOURCE_CHOICES = (
        (SOURCE_AUTO, _("Авто")),
        (SOURCE_MANUAL, _("Вручную")),
        (SOURCE_IMPORT, _("Импорт")),
    )

    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="price_history",
        verbose_name=_("Товар"),
    )
    product_price = models.ForeignKey(
        "pricing.ProductPrice",
        on_delete=models.SET_NULL,
        related_name="history_entries",
        blank=True,
        null=True,
        verbose_name=_("Текущая цена товара"),
    )
    old_price = models.DecimalField(_("Старая цена"), max_digits=12, decimal_places=2, blank=True, null=True)
    new_price = models.DecimalField(_("Новая цена"), max_digits=12, decimal_places=2)
    source = models.CharField(_("Источник"), max_length=16, choices=SOURCE_CHOICES, default=SOURCE_AUTO)
    comment = models.CharField(_("Комментарий"), max_length=255, blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="changed_prices",
        verbose_name=_("Кем изменено"),
    )

    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("История цены")
        verbose_name_plural = _("История цен")

    def __str__(self) -> str:
        return f"{self.product} {self.old_price} -> {self.new_price}"
