from django.db import models
from django.utils.translation import gettext_lazy as _


class AutoDbPassengerCar(models.Model):
    # Deprecated runtime source:
    # Public catalog compatibility must resolve vehicle metadata through
    # apps.autodb.selectors.vehicle_catalog (auto_db_pro raw tables).
    # This managed mirror model is kept only for legacy sync/migration paths.
    id = models.PositiveIntegerField(primary_key=True)
    autodb_vehicle_id = models.BigIntegerField(_("Auto-DB vehicle ID"), null=True, blank=True, unique=True, db_index=True)
    ktype = models.BigIntegerField(_("KType"), null=True, blank=True, db_index=True)
    vehicle_manufacturer = models.ForeignKey(
        "autodb.AutoDbVehicleManufacturer",
        on_delete=models.SET_NULL,
        related_name="passenger_cars",
        null=True,
        blank=True,
    )
    model = models.ForeignKey(
        "autodb.AutoDbVehicleModel",
        on_delete=models.CASCADE,
        related_name="passenger_cars",
        blank=True,
        null=True,
    )
    modification_name = models.CharField(_("Модификация"), max_length=255, blank=True, default="")
    engine_code = models.CharField(_("Код двигателя"), max_length=128, blank=True, default="")
    engine_capacity = models.CharField(_("Объем двигателя"), max_length=64, blank=True, default="")
    power_kw = models.IntegerField(_("Мощность кВт"), null=True, blank=True)
    power_hp = models.IntegerField(_("Мощность л.с."), null=True, blank=True)
    fuel_type = models.CharField(_("Тип топлива"), max_length=64, blank=True, default="")
    body_type = models.CharField(_("Тип кузова"), max_length=128, blank=True, default="")
    source_payload = models.JSONField(_("Source payload"), default=dict, blank=True)
    source_updated_at = models.DateTimeField(_("Обновлено в источнике"), null=True, blank=True)
    imported_at = models.DateTimeField(_("Импортировано"), null=True, blank=True)
    description = models.CharField(_("Модификация"), max_length=255, blank=True)
    full_description = models.CharField(_("Полное описание"), max_length=255, blank=True)
    construction_interval = models.CharField(_("Интервал выпуска"), max_length=64, blank=True)
    start_year = models.PositiveSmallIntegerField(_("Год начала"), null=True, blank=True)
    start_month = models.PositiveSmallIntegerField(_("Месяц начала"), null=True, blank=True)
    end_year = models.PositiveSmallIntegerField(_("Год окончания"), null=True, blank=True)
    end_month = models.PositiveSmallIntegerField(_("Месяц окончания"), null=True, blank=True)

    class Meta:
        db_table = "autodb_passenger_cars"
        verbose_name = _("Легковой автомобиль Auto-DB")
        verbose_name_plural = _("Легковые автомобили Auto-DB")
        indexes = [
            models.Index(fields=("model",), name="autodb_pc_model_idx"),
            models.Index(fields=("start_year", "end_year"), name="autodb_pc_years_idx"),
            models.Index(fields=("ktype",), name="adb_pro_pc_ktype_idx"),
        ]

    def __str__(self) -> str:
        return self.full_description or self.description or str(self.id)
