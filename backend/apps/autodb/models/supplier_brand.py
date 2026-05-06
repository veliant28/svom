from django.db import models
from django.utils.translation import gettext_lazy as _


class AutoDbSupplierBrand(models.Model):
    autodb_supplier_id = models.BigIntegerField(_("Auto-DB supplier ID"), unique=True, db_index=True)
    name = models.CharField(_("Название"), max_length=255, blank=True, default="")
    normalized_name = models.CharField(_("Нормализованное название"), max_length=255, blank=True, default="", db_index=True)
    supplier_details_payload = models.JSONField(_("Supplier details payload"), default=dict, blank=True)
    source_payload = models.JSONField(_("Source payload"), default=dict, blank=True)

    class Meta:
        db_table = "autodb_pro_supplier_brands"
        verbose_name = _("Бренд поставщика Auto_DB_Pro")
        verbose_name_plural = _("Бренды поставщиков Auto_DB_Pro")

    def __str__(self) -> str:
        return self.name or str(self.autodb_supplier_id)
