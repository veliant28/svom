from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin
from apps.supplier_imports.parsers.utils import normalize_brand


class AutoDbSupplierBrandAlias(UUIDPrimaryKeyMixin, TimestampedMixin):
    SOURCE_AUTO = "auto"
    SOURCE_MANUAL = "manual"
    SOURCE_IMPORTED = "imported"
    SOURCE_CHOICES = (
        (SOURCE_AUTO, "auto"),
        (SOURCE_MANUAL, "manual"),
        (SOURCE_IMPORTED, "imported"),
    )

    raw_brand = models.CharField(_("Raw brand"), max_length=255)
    normalized_raw_brand = models.CharField(_("Normalized raw brand"), max_length=255, db_index=True)
    autodb_supplier_id = models.BigIntegerField(_("Auto_DB_Pro supplier ID"), db_index=True)
    autodb_supplier_name = models.CharField(_("Auto_DB_Pro supplier name"), max_length=255, blank=True, default="")
    source = models.CharField(_("Source"), max_length=32, choices=SOURCE_CHOICES, default=SOURCE_AUTO)
    confidence = models.DecimalField(_("Confidence"), max_digits=5, decimal_places=2, default=0.0)
    manual_confirmed = models.BooleanField(_("Manual confirmed"), default=False, db_index=True)
    note = models.TextField(_("Note"), blank=True, default="")
    is_active = models.BooleanField(_("Active"), default=True, db_index=True)

    class Meta:
        db_table = "autodb_supplier_brand_aliases"
        verbose_name = _("Auto_DB supplier brand alias")
        verbose_name_plural = _("Auto_DB supplier brand aliases")
        indexes = [
            models.Index(fields=("normalized_raw_brand", "is_active"), name="autodb_alias_norm_active_idx"),
            models.Index(fields=("autodb_supplier_id", "is_active"), name="autodb_alias_sup_active_idx"),
            models.Index(fields=("manual_confirmed", "is_active"), name="autodb_alias_manual_active_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=("normalized_raw_brand",), name="autodb_alias_norm_unique"),
        ]

    def save(self, *args, **kwargs):
        self.normalized_raw_brand = normalize_brand(self.raw_brand)[:255]
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.raw_brand} -> {self.autodb_supplier_id}"
