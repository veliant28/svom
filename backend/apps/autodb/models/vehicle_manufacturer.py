from django.db import models
from django.utils.translation import gettext_lazy as _


class AutoDbVehicleManufacturer(models.Model):
    autodb_manufacturer_id = models.BigIntegerField(_("Auto-DB manufacturer ID"), unique=True, db_index=True)
    name = models.CharField(_("Название"), max_length=255, blank=True, default="")
    normalized_name = models.CharField(_("Нормализованное название"), max_length=255, blank=True, default="", db_index=True)
    country_id = models.BigIntegerField(_("ID страны"), null=True, blank=True)
    source_payload = models.JSONField(_("Source payload"), default=dict, blank=True)
    source_updated_at = models.DateTimeField(_("Обновлено в источнике"), null=True, blank=True)
    imported_at = models.DateTimeField(_("Импортировано"), auto_now_add=True)

    class Meta:
        db_table = "autodb_pro_vehicle_manufacturers"
        verbose_name = _("Производитель авто Auto_DB_Pro")
        verbose_name_plural = _("Производители авто Auto_DB_Pro")

    def __str__(self) -> str:
        return self.name or str(self.autodb_manufacturer_id)
