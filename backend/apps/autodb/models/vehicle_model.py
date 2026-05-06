from django.db import models
from django.utils.translation import gettext_lazy as _


class AutoDbVehicleModel(models.Model):
    id = models.PositiveIntegerField(primary_key=True)
    autodb_model_id = models.BigIntegerField(_("Auto-DB model ID"), null=True, blank=True, unique=True, db_index=True)
    vehicle_manufacturer = models.ForeignKey(
        "autodb.AutoDbVehicleManufacturer",
        on_delete=models.SET_NULL,
        related_name="vehicle_models",
        null=True,
        blank=True,
    )
    manufacturer = models.ForeignKey(
        "autodb.AutoDbManufacturer",
        on_delete=models.CASCADE,
        related_name="vehicle_models",
        null=True,
        blank=True,
    )
    name = models.CharField(_("Название"), max_length=255, blank=True, default="")
    normalized_name = models.CharField(_("Нормализованное название"), max_length=255, blank=True, default="", db_index=True)
    year_from = models.PositiveSmallIntegerField(_("Год от"), null=True, blank=True)
    year_to = models.PositiveSmallIntegerField(_("Год до"), null=True, blank=True)
    source_payload = models.JSONField(_("Source payload"), default=dict, blank=True)
    source_updated_at = models.DateTimeField(_("Обновлено в источнике"), null=True, blank=True)
    imported_at = models.DateTimeField(_("Импортировано"), null=True, blank=True)
    description = models.CharField(_("Модель"), max_length=255, blank=True)
    full_description = models.CharField(_("Полное описание"), max_length=255, blank=True)

    class Meta:
        db_table = "autodb_models"
        verbose_name = _("Модель Auto-DB")
        verbose_name_plural = _("Модели Auto-DB")
        indexes = [
            models.Index(fields=("manufacturer",), name="autodb_model_manu_idx"),
            models.Index(fields=("description",), name="autodb_model_desc_idx"),
            models.Index(fields=("normalized_name",), name="adb_pro_model_nname_idx"),
        ]

    def __str__(self) -> str:
        return self.full_description or self.description or str(self.id)
