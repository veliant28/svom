from django.db import models
from django.utils.translation import gettext_lazy as _


class AutoDbVehicleAttribute(models.Model):
    source_row_id = models.CharField(_("Source row ID"), max_length=128, null=True, blank=True, unique=True, db_index=True)
    vehicle = models.ForeignKey(
        "autodb.AutoDbPassengerCar",
        on_delete=models.CASCADE,
        related_name="attributes",
    )
    source_key = models.CharField(_("Source key"), max_length=128, blank=True, default="")
    name_uk = models.CharField(_("Название (UA)"), max_length=255, blank=True, default="")
    name_ru = models.CharField(_("Название (RU)"), max_length=255, blank=True, default="")
    name_en = models.CharField(_("Название (EN)"), max_length=255, blank=True, default="")
    value_uk = models.CharField(_("Значение (UA)"), max_length=255, blank=True, default="")
    value_ru = models.CharField(_("Значение (RU)"), max_length=255, blank=True, default="")
    value_en = models.CharField(_("Значение (EN)"), max_length=255, blank=True, default="")
    unit = models.CharField(_("Единица"), max_length=64, blank=True, default="")
    source_payload = models.JSONField(_("Source payload"), default=dict, blank=True)
    source_updated_at = models.DateTimeField(_("Обновлено в источнике"), null=True, blank=True)
    imported_at = models.DateTimeField(_("Импортировано"), null=True, blank=True)

    class Meta:
        db_table = "autodb_pro_vehicle_attributes"
        verbose_name = _("Атрибут авто Auto_DB_Pro")
        verbose_name_plural = _("Атрибуты авто Auto_DB_Pro")
        indexes = [
            models.Index(fields=("vehicle",), name="adb_pro_vattr_vehicle_idx"),
            models.Index(fields=("source_key",), name="adb_pro_vattr_key_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.vehicle_id}:{self.source_key}"
