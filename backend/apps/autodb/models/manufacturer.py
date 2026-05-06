from django.db import models
from django.utils.translation import gettext_lazy as _


class AutoDbManufacturer(models.Model):
    id = models.PositiveIntegerField(primary_key=True)
    description = models.CharField(_("Название"), max_length=255, blank=True)
    matchcode = models.CharField(_("Matchcode"), max_length=255, blank=True)

    class Meta:
        db_table = "autodb_manufacturers"
        verbose_name = _("Производитель Auto-DB")
        verbose_name_plural = _("Производители Auto-DB")

    def __str__(self) -> str:
        return self.description or str(self.id)
