from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class ProductAttribute(UUIDPrimaryKeyMixin, TimestampedMixin):
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="product_attributes",
        verbose_name=_("Товар"),
    )
    attribute = models.ForeignKey(
        "catalog.Attribute",
        on_delete=models.PROTECT,
        related_name="product_attributes",
        verbose_name=_("Атрибут"),
    )
    attribute_value = models.ForeignKey(
        "catalog.AttributeValue",
        on_delete=models.PROTECT,
        related_name="product_attributes",
        blank=True,
        null=True,
        verbose_name=_("Значение атрибута"),
    )
    raw_value = models.CharField(_("Сырое значение"), max_length=255, blank=True)

    class Meta:
        ordering = ("product__name", "attribute__name")
        verbose_name = _("Атрибут товара")
        verbose_name_plural = _("Атрибуты товаров")
        constraints = [
            models.UniqueConstraint(
                fields=("product", "attribute"),
                name="catalog_productattribute_unique_product_attribute",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.product} - {self.attribute}"
