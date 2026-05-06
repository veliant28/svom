from django.db import models
from django.utils.translation import gettext_lazy as _


class AutoDbArticleLinkage(models.Model):
    supplier = models.ForeignKey(
        "autodb.AutoDbSupplier",
        on_delete=models.CASCADE,
        related_name="article_linkages",
    )
    article_number = models.CharField(_("Артикул"), max_length=128)
    normalized_article = models.CharField(_("Нормализованный артикул"), max_length=128, db_index=True)
    linkage_type = models.CharField(_("Тип связи"), max_length=32)
    linkage_id = models.PositiveIntegerField(_("ID связи"))

    class Meta:
        db_table = "autodb_article_linkages"
        verbose_name = _("Связь артикула с авто Auto-DB")
        verbose_name_plural = _("Связи артикулов с авто Auto-DB")
        constraints = [
            models.UniqueConstraint(
                fields=("supplier", "article_number", "linkage_type", "linkage_id"),
                name="adb_link_uq_sup_art_type_id",
            )
        ]
        indexes = [
            models.Index(fields=("supplier", "normalized_article"), name="adb_link_sup_norm_art_idx"),
            models.Index(fields=("linkage_type", "linkage_id"), name="autodb_linkage_type_id_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.supplier_id}:{self.article_number}:{self.linkage_type}:{self.linkage_id}"
