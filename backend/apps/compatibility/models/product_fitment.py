from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class ProductFitment(UUIDPrimaryKeyMixin, TimestampedMixin):
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="fitments",
        verbose_name=_("Товар"),
    )
    modification = models.ForeignKey(
        "vehicles.VehicleModification",
        on_delete=models.CASCADE,
        related_name="fitments",
        verbose_name=_("Модификация"),
    )
    note = models.CharField(_("Примечание"), max_length=255, blank=True)
    is_exact = models.BooleanField(_("Точное соответствие"), default=True)

    class Meta:
        ordering = ("product__name",)
        verbose_name = _("Применимость товара")
        verbose_name_plural = _("Применимость товаров")
        constraints = [
            models.UniqueConstraint(
                fields=("product", "modification"),
                name="compatibility_fitment_unique_product_modification",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.product} -> {self.modification}"
