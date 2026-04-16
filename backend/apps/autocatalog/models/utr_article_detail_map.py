from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _


class UtrArticleDetailMap(models.Model):
    article = models.CharField(_("Артикул UTR"), max_length=128)
    normalized_article = models.CharField(_("Нормализованный артикул UTR"), max_length=128, db_index=True)
    brand_name = models.CharField(_("Бренд"), max_length=180, blank=True)
    normalized_brand = models.CharField(_("Нормализованный бренд"), max_length=180, blank=True, db_index=True)
    utr_detail_id = models.CharField(_("UTR detail ID"), max_length=64, db_index=True)
    created_at = models.DateTimeField(_("Создано"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Обновлено"), auto_now=True)

    class Meta:
        ordering = ("normalized_article", "normalized_brand")
        verbose_name = _("Связь артикула UTR с detail ID")
        verbose_name_plural = _("Связи артикула UTR с detail ID")
        constraints = [
            models.UniqueConstraint(
                fields=("normalized_article", "normalized_brand"),
                name="autocatalog_unique_utr_article_brand_detail_map",
            ),
        ]
        indexes = [
            models.Index(fields=("utr_detail_id",), name="ac_utr_article_did_idx"),
        ]

    def __str__(self) -> str:
        brand = self.brand_name.strip()
        if brand:
            return f"{self.article} ({brand}) -> {self.utr_detail_id}"
        return f"{self.article} -> {self.utr_detail_id}"
