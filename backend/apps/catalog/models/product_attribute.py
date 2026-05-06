from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class ProductAttribute(UUIDPrimaryKeyMixin, TimestampedMixin):
    SOURCE_AUTODB_PRO = "autodb_pro"
    SOURCE_MANUAL = "manual"
    SOURCE_LEGACY = "legacy"
    SOURCE_IMPORT = "import"
    SOURCE_CHOICES = (
        (SOURCE_AUTODB_PRO, _("Auto_DB_Pro")),
        (SOURCE_MANUAL, _("Manual")),
        (SOURCE_LEGACY, _("Legacy")),
        (SOURCE_IMPORT, _("Import")),
    )

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
    source = models.CharField(_("Источник"), max_length=24, choices=SOURCE_CHOICES, blank=True, default=SOURCE_LEGACY, db_index=True)
    source_payload = models.JSONField(_("Source payload"), default=dict, blank=True)
    source_hash = models.CharField(_("Source hash"), max_length=64, blank=True, default="", db_index=True)
    autodb_attribute_id = models.BigIntegerField(_("Auto_DB_Pro attribute ID"), blank=True, null=True, db_index=True)
    manual_locked = models.BooleanField(_("Характеристика закреплена вручную"), default=False, db_index=True)

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
