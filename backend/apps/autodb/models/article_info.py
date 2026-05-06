from django.db import models
from django.utils.translation import gettext_lazy as _


class AutoDbArticleInfo(models.Model):
    supplier = models.ForeignKey(
        "autodb.AutoDbSupplier",
        on_delete=models.CASCADE,
        related_name="article_infos",
    )
    article_number = models.CharField(_("Артикул"), max_length=128)
    normalized_article = models.CharField(_("Нормализованный артикул"), max_length=128, db_index=True)
    info_text = models.TextField(_("Текстовая информация"), blank=True, default="")
    info_language = models.CharField(_("Язык"), max_length=32, blank=True, default="")
    info_type = models.CharField(_("Тип информации"), max_length=64, blank=True, default="")
    sort_order = models.IntegerField(_("Порядок сортировки"), default=0)

    class Meta:
        db_table = "autodb_article_infos"
        verbose_name = _("Информация об артикуле Auto-DB")
        verbose_name_plural = _("Информация об артикулах Auto-DB")
        constraints = [
            models.UniqueConstraint(
                fields=("supplier", "article_number", "info_text", "info_language", "info_type"),
                name="adb_inf_uq_sup_art_text_lang_type",
            )
        ]
        indexes = [
            models.Index(fields=("supplier", "normalized_article"), name="adb_inf_sup_norm_art_idx"),
            models.Index(fields=("info_type",), name="adb_inf_type_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.supplier_id}:{self.article_number}:{self.info_type}"
