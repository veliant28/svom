from django.db import models
from django.utils.translation import gettext_lazy as _


class AutoDbArticle(models.Model):
    supplier = models.ForeignKey(
        "autodb.AutoDbSupplier",
        on_delete=models.CASCADE,
        related_name="articles",
    )
    article_number = models.CharField(_("Артикул"), max_length=128)
    normalized_article = models.CharField(_("Нормализованный артикул"), max_length=128, db_index=True)

    class Meta:
        db_table = "autodb_articles"
        verbose_name = _("Артикул Auto-DB")
        verbose_name_plural = _("Артикулы Auto-DB")
        constraints = [
            models.UniqueConstraint(
                fields=("supplier", "article_number"),
                name="adb_art_uq_sup_art",
            )
        ]
        indexes = [
            models.Index(fields=("supplier", "normalized_article"), name="autodb_art_sup_norm_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.supplier_id}:{self.article_number}"
