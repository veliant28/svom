from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import PublishableMixin, TimestampedMixin, UUIDPrimaryKeyMixin


class Product(UUIDPrimaryKeyMixin, TimestampedMixin, PublishableMixin):
    sku = models.CharField(_("SKU"), max_length=64, unique=True)
    article = models.CharField(_("Артикул"), max_length=128, blank=True)
    utr_detail_id = models.CharField(_("UTR detail ID"), max_length=64, blank=True, db_index=True)
    name = models.CharField(_("Название"), max_length=255)
    slug = models.SlugField(_("Slug"), max_length=300, unique=True)
    brand = models.ForeignKey(
        "catalog.Brand",
        on_delete=models.PROTECT,
        related_name="products",
        verbose_name=_("Бренд"),
    )
    category = models.ForeignKey(
        "catalog.Category",
        on_delete=models.PROTECT,
        related_name="products",
        verbose_name=_("Категория"),
    )
    short_description = models.TextField(_("Короткое описание"), blank=True)
    description = models.TextField(_("Описание"), blank=True)
    is_featured = models.BooleanField(_("Рекомендуемый"), default=False)
    is_new = models.BooleanField(_("Новинка"), default=False)
    is_bestseller = models.BooleanField(_("Хит продаж"), default=False)

    class Meta:
        ordering = ("name",)
        verbose_name = _("Товар")
        verbose_name_plural = _("Товары")
        indexes = [
            models.Index(fields=("brand", "category"), name="cat_prod_brand_cat_idx"),
            models.Index(fields=("is_active", "is_featured"), name="catalog_product_featured_idx"),
        ]

    def __str__(self) -> str:
        return self.name
