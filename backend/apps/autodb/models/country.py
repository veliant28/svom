from django.db import models
from django.utils.translation import gettext_lazy as _


class AutoDbCountry(models.Model):
    autodb_country_id = models.BigIntegerField(_("Auto-DB country ID"), unique=True, db_index=True)
    name = models.CharField(_("Название"), max_length=255, blank=True, default="")
    iso_code = models.CharField(_("ISO код"), max_length=16, blank=True, default="")
    source_payload = models.JSONField(_("Source payload"), default=dict, blank=True)
    source_updated_at = models.DateTimeField(_("Обновлено в источнике"), null=True, blank=True)
    imported_at = models.DateTimeField(_("Импортировано"), null=True, blank=True)

    class Meta:
        db_table = "autodb_pro_countries"
        verbose_name = _("Страна Auto_DB_Pro")
        verbose_name_plural = _("Страны Auto_DB_Pro")

    def __str__(self) -> str:
        return self.name or str(self.autodb_country_id)
