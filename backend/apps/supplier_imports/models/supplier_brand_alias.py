from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin
from apps.supplier_imports.parsers.utils import normalize_brand


class SupplierBrandAlias(UUIDPrimaryKeyMixin, TimestampedMixin):
    source = models.ForeignKey(
        "supplier_imports.ImportSource",
        on_delete=models.CASCADE,
        related_name="brand_aliases",
        blank=True,
        null=True,
        verbose_name=_("Источник"),
    )
    supplier = models.ForeignKey(
        "pricing.Supplier",
        on_delete=models.CASCADE,
        related_name="brand_aliases",
        blank=True,
        null=True,
        verbose_name=_("Поставщик"),
    )
    canonical_brand = models.ForeignKey(
        "catalog.Brand",
        on_delete=models.SET_NULL,
        related_name="supplier_brand_aliases",
        blank=True,
        null=True,
        verbose_name=_("Канонический бренд"),
    )
    canonical_brand_name = models.CharField(_("Название канонического бренда"), max_length=180, blank=True)
    supplier_brand_alias = models.CharField(_("Алиас поставщика"), max_length=180)
    normalized_alias = models.CharField(_("Нормализованный алиас"), max_length=180, db_index=True)
    is_active = models.BooleanField(_("Активен"), default=True)
    priority = models.IntegerField(_("Приоритет"), default=100)
    notes = models.TextField(_("Примечание"), blank=True)

    class Meta:
        ordering = ("supplier__code", "source__code", "-priority", "normalized_alias")
        verbose_name = _("Алиас бренда поставщика")
        verbose_name_plural = _("Алиасы брендов поставщиков")
        indexes = [
            models.Index(fields=("normalized_alias", "is_active", "priority")),
            models.Index(fields=("source", "is_active", "priority")),
            models.Index(fields=("supplier", "is_active", "priority")),
        ]

    def save(self, *args, **kwargs):
        self.normalized_alias = normalize_brand(self.supplier_brand_alias)[:180]
        if self.canonical_brand and not self.canonical_brand_name:
            self.canonical_brand_name = self.canonical_brand.name
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        canonical = self.canonical_brand_name or (self.canonical_brand.name if self.canonical_brand else "")
        return f"{self.supplier_brand_alias} -> {canonical or '-'}"
