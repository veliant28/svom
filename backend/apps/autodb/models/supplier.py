from django.db import models
from django.utils.translation import gettext_lazy as _


class AutoDbSupplier(models.Model):
    id = models.PositiveIntegerField(primary_key=True)
    name = models.CharField(_("Название"), max_length=255, blank=True)
    matchcode = models.CharField(_("Matchcode"), max_length=255, blank=True)
    normalized_name = models.CharField(_("Нормализованное название"), max_length=255, blank=True, db_index=True)
    normalized_matchcode = models.CharField(_("Нормализованный matchcode"), max_length=255, blank=True, db_index=True)

    class Meta:
        db_table = "autodb_suppliers"
        verbose_name = _("Поставщик Auto-DB")
        verbose_name_plural = _("Поставщики Auto-DB")
        indexes = [
            models.Index(fields=("normalized_matchcode",), name="autodb_sup_norm_match_idx"),
            models.Index(fields=("normalized_name",), name="autodb_sup_norm_name_idx"),
        ]

    def __str__(self) -> str:
        return self.name or self.matchcode or str(self.id)
