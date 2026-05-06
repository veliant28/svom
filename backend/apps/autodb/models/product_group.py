from django.db import models
from django.utils.translation import gettext_lazy as _


class AutoDbProductGroup(models.Model):
    id = models.PositiveIntegerField(primary_key=True)
    autodb_prd_id = models.BigIntegerField(_("Auto-DB PRD ID"), null=True, blank=True, unique=True, db_index=True)
    parent_id = models.BigIntegerField(_("Parent ID"), null=True, blank=True)
    group_id = models.BigIntegerField(_("Group ID"), null=True, blank=True)
    category_id = models.BigIntegerField(_("Category ID"), null=True, blank=True)
    name = models.CharField(_("Название группы"), max_length=255, blank=True)
    name_uk = models.CharField(_("Название (UA)"), max_length=255, blank=True, default="")
    name_ru = models.CharField(_("Название (RU)"), max_length=255, blank=True, default="")
    name_en = models.CharField(_("Название (EN)"), max_length=255, blank=True, default="")
    normalized_name = models.CharField(_("Нормализованное название"), max_length=255, blank=True, db_index=True)
    source_payload = models.JSONField(_("Source payload"), default=dict, blank=True)
    source_updated_at = models.DateTimeField(_("Обновлено в источнике"), null=True, blank=True)
    imported_at = models.DateTimeField(_("Импортировано"), null=True, blank=True)

    class Meta:
        db_table = "autodb_product_groups"
        verbose_name = _("Группа товаров Auto-DB")
        verbose_name_plural = _("Группы товаров Auto-DB")
        indexes = [
            models.Index(fields=("normalized_name",), name="adb_prd_norm_name_idx"),
        ]

    def __str__(self) -> str:
        return self.name or str(self.id)
