from django.db import models
from django.utils.translation import gettext_lazy as _


class AutoDbPassengerCarTree(models.Model):
    source_row_id = models.CharField(_("Source row ID"), max_length=128, null=True, blank=True, unique=True, db_index=True)
    vehicle = models.ForeignKey(
        "autodb.AutoDbPassengerCar",
        on_delete=models.CASCADE,
        related_name="trees",
    )
    prd_id = models.BigIntegerField(_("PRD ID"), null=True, blank=True, db_index=True)
    category_id = models.BigIntegerField(_("Category ID"), null=True, blank=True)
    parent_id = models.BigIntegerField(_("Parent ID"), null=True, blank=True)
    name_uk = models.CharField(_("Название (UA)"), max_length=255, blank=True, default="")
    name_ru = models.CharField(_("Название (RU)"), max_length=255, blank=True, default="")
    name_en = models.CharField(_("Название (EN)"), max_length=255, blank=True, default="")
    source_payload = models.JSONField(_("Source payload"), default=dict, blank=True)
    source_updated_at = models.DateTimeField(_("Обновлено в источнике"), null=True, blank=True)
    imported_at = models.DateTimeField(_("Импортировано"), null=True, blank=True)

    class Meta:
        db_table = "autodb_pro_passenger_car_trees"
        verbose_name = _("Дерево легковых авто Auto_DB_Pro")
        verbose_name_plural = _("Деревья легковых авто Auto_DB_Pro")
        indexes = [
            models.Index(fields=("vehicle",), name="adb_pro_pctree_vehicle_idx"),
            models.Index(fields=("prd_id",), name="adb_pro_pctree_prd_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.vehicle_id}:{self.prd_id or self.category_id or ''}"
