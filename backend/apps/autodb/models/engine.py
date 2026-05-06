from django.db import models
from django.utils.translation import gettext_lazy as _


class AutoDbEngine(models.Model):
    autodb_engine_id = models.BigIntegerField(_("Auto-DB engine ID"), unique=True, db_index=True)
    engine_code = models.CharField(_("Код двигателя"), max_length=128, blank=True, default="")
    capacity = models.CharField(_("Объем"), max_length=64, blank=True, default="")
    power_kw = models.IntegerField(_("Мощность кВт"), null=True, blank=True)
    power_hp = models.IntegerField(_("Мощность л.с."), null=True, blank=True)
    fuel_type = models.CharField(_("Тип топлива"), max_length=64, blank=True, default="")
    source_payload = models.JSONField(_("Source payload"), default=dict, blank=True)
    source_updated_at = models.DateTimeField(_("Обновлено в источнике"), null=True, blank=True)
    imported_at = models.DateTimeField(_("Импортировано"), null=True, blank=True)

    class Meta:
        db_table = "autodb_pro_engines"
        verbose_name = _("Двигатель Auto_DB_Pro")
        verbose_name_plural = _("Двигатели Auto_DB_Pro")

    def __str__(self) -> str:
        return self.engine_code or str(self.autodb_engine_id)
