from django.db import models
from django.utils.translation import gettext_lazy as _


class AutoDbPassengerCarEngine(models.Model):
    source_row_id = models.CharField(_("Source row ID"), max_length=128, null=True, blank=True, unique=True, db_index=True)
    passenger_car = models.ForeignKey(
        "autodb.AutoDbPassengerCar",
        on_delete=models.CASCADE,
        related_name="engines",
    )
    engine_id = models.BigIntegerField(_("Engine ID"), null=True, blank=True)
    engine_code = models.CharField(_("Код двигателя"), max_length=128, blank=True, default="")
    capacity = models.CharField(_("Объем"), max_length=64, blank=True, default="")
    power_kw = models.IntegerField(_("Мощность кВт"), null=True, blank=True)
    power_hp = models.IntegerField(_("Мощность л.с."), null=True, blank=True)
    fuel_type = models.CharField(_("Тип топлива"), max_length=64, blank=True, default="")
    source_payload = models.JSONField(_("Source payload"), default=dict, blank=True)
    source_updated_at = models.DateTimeField(_("Обновлено в источнике"), null=True, blank=True)
    imported_at = models.DateTimeField(_("Импортировано"), null=True, blank=True)

    class Meta:
        db_table = "autodb_pro_passenger_car_engines"
        verbose_name = _("Двигатель модификации Auto_DB_Pro")
        verbose_name_plural = _("Двигатели модификаций Auto_DB_Pro")
        indexes = [
            models.Index(fields=("passenger_car",), name="adb_pro_pce_car_idx"),
            models.Index(fields=("engine_id",), name="adb_pro_pce_engine_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.passenger_car_id}:{self.engine_code}"
