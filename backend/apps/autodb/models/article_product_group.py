from django.db import models
from django.utils.translation import gettext_lazy as _


class AutoDbArticleProductGroup(models.Model):
    supplier = models.ForeignKey(
        "autodb.AutoDbSupplier",
        on_delete=models.CASCADE,
        related_name="article_product_groups",
    )
    article_number = models.CharField(_("Артикул"), max_length=128)
    normalized_article = models.CharField(_("Нормализованный артикул"), max_length=128, db_index=True)
    product_group = models.ForeignKey(
        "autodb.AutoDbProductGroup",
        on_delete=models.CASCADE,
        related_name="article_links",
    )

    class Meta:
        db_table = "autodb_article_product_groups"
        verbose_name = _("Связь артикула с товарной группой Auto-DB")
        verbose_name_plural = _("Связи артикула с товарными группами Auto-DB")
        constraints = [
            models.UniqueConstraint(
                fields=("supplier", "article_number", "product_group"),
                name="adb_art_prd_uq_sup_art_prd",
            )
        ]
        indexes = [
            models.Index(fields=("supplier", "normalized_article"), name="adb_art_prd_sup_norm_idx"),
            models.Index(fields=("product_group",), name="adb_art_prd_group_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.supplier_id}:{self.article_number}:{self.product_group_id}"

