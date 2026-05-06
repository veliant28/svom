from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import SortableMixin, TimestampedMixin, UUIDPrimaryKeyMixin


class ProductImage(UUIDPrimaryKeyMixin, TimestampedMixin, SortableMixin):
    SOURCE_MANUAL = "manual"
    SOURCE_GPL_PRICE = "gpl_price"
    SOURCE_AUTODB_PRO = "autodb_pro"
    SOURCE_IMPORTED = "imported"
    SOURCE_CHOICES = (
        (SOURCE_MANUAL, _("Manual")),
        (SOURCE_GPL_PRICE, _("GPL price")),
        (SOURCE_AUTODB_PRO, _("Auto_DB_Pro")),
        (SOURCE_IMPORTED, _("Imported")),
    )

    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="images",
        verbose_name=_("Товар"),
    )
    image = models.ImageField(_("Изображение"), upload_to="catalog/products/images/", blank=True, null=True)
    remote_url = models.URLField(_("Remote URL"), max_length=1000, blank=True, default="")
    alt_text = models.CharField(_("Alt-текст"), max_length=255, blank=True)
    is_primary = models.BooleanField(_("Основное"), default=False)
    source = models.CharField(_("Источник"), max_length=24, choices=SOURCE_CHOICES, blank=True, default=SOURCE_IMPORTED, db_index=True)
    source_payload = models.JSONField(_("Source payload"), default=dict, blank=True)
    source_hash = models.CharField(_("Source hash"), max_length=64, blank=True, default="", db_index=True)
    is_stale = models.BooleanField(_("Устаревшее изображение"), default=False, db_index=True)
    stale_reason = models.CharField(_("Причина устаревания"), max_length=64, blank=True, default="")

    class Meta(SortableMixin.Meta):
        verbose_name = _("Изображение товара")
        verbose_name_plural = _("Изображения товаров")
        constraints = [
            models.UniqueConstraint(
                fields=("product", "sort_order"),
                name="catalog_productimage_unique_order_per_product",
            ),
            models.UniqueConstraint(
                fields=("product", "source", "remote_url"),
                condition=~Q(remote_url=""),
                name="catalog_productimage_unique_remote_per_source",
            ),
            models.UniqueConstraint(
                fields=("product", "source", "source_hash"),
                condition=~Q(source_hash=""),
                name="catalog_productimage_unique_source_hash_per_source",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.product} #{self.sort_order}"
