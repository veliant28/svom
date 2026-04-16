from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import SortableMixin, TimestampedMixin, UUIDPrimaryKeyMixin


class ProductImage(UUIDPrimaryKeyMixin, TimestampedMixin, SortableMixin):
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="images",
        verbose_name=_("Товар"),
    )
    image = models.ImageField(_("Изображение"), upload_to="catalog/products/images/")
    alt_text = models.CharField(_("Alt-текст"), max_length=255, blank=True)
    is_primary = models.BooleanField(_("Основное"), default=False)

    class Meta(SortableMixin.Meta):
        verbose_name = _("Изображение товара")
        verbose_name_plural = _("Изображения товаров")
        constraints = [
            models.UniqueConstraint(
                fields=("product", "sort_order"),
                name="catalog_productimage_unique_order_per_product",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.product} #{self.sort_order}"
