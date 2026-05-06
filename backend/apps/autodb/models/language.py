from django.db import models
from django.utils.translation import gettext_lazy as _


class AutoDbLanguage(models.Model):
    autodb_language_id = models.BigIntegerField(_("Auto-DB language ID"), unique=True, db_index=True)
    code = models.CharField(_("Код"), max_length=32, blank=True, default="")
    name = models.CharField(_("Название"), max_length=255, blank=True, default="")
    source_payload = models.JSONField(_("Source payload"), default=dict, blank=True)
    source_updated_at = models.DateTimeField(_("Обновлено в источнике"), null=True, blank=True)
    imported_at = models.DateTimeField(_("Импортировано"), null=True, blank=True)

    class Meta:
        db_table = "autodb_pro_languages"
        verbose_name = _("Язык Auto_DB_Pro")
        verbose_name_plural = _("Языки Auto_DB_Pro")

    def __str__(self) -> str:
        return self.code or self.name or str(self.autodb_language_id)
