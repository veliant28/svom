from django.db import models
from django.utils.translation import gettext_lazy as _


class AutoDbArticleAttribute(models.Model):
    supplier = models.ForeignKey(
        "autodb.AutoDbSupplier",
        on_delete=models.CASCADE,
        related_name="article_attributes",
    )
    article_number = models.CharField(_("Артикул"), max_length=128)
    normalized_article = models.CharField(_("Нормализованный артикул"), max_length=128, db_index=True)
    attribute_name = models.CharField(_("Название характеристики"), max_length=255)
    attribute_value = models.TextField(_("Значение характеристики"), blank=True, default="")
    unit = models.CharField(_("Единица измерения"), max_length=64, blank=True, default="")
    sort_order = models.IntegerField(_("Порядок сортировки"), default=0)

    class Meta:
        db_table = "autodb_article_attributes"
        verbose_name = _("Характеристика артикула Auto-DB")
        verbose_name_plural = _("Характеристики артикулов Auto-DB")
        constraints = [
            models.UniqueConstraint(
                fields=("supplier", "article_number", "attribute_name", "attribute_value", "unit"),
                name="adb_attr_uq_sup_art_name_value_unit",
            )
        ]
        indexes = [
            models.Index(fields=("supplier", "normalized_article"), name="adb_attr_sup_norm_art_idx"),
            models.Index(fields=("attribute_name",), name="adb_attr_name_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.supplier_id}:{self.article_number}:{self.attribute_name}"

