from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class AutoDbArticleManualMapping(UUIDPrimaryKeyMixin, TimestampedMixin):
    brand = models.CharField(_("Бренд"), max_length=180, blank=True, default="")
    article = models.CharField(_("Артикул"), max_length=128)
    normalized_brand = models.CharField(_("Нормализованный бренд"), max_length=180, db_index=True)
    normalized_article = models.CharField(_("Нормализованный артикул"), max_length=128, db_index=True)

    autodb_supplier_id = models.BigIntegerField(_("Auto_DB_Pro supplier ID"), db_index=True)
    autodb_article_id = models.BigIntegerField(_("Auto_DB_Pro article ID"), blank=True, null=True)
    autodb_article_number = models.CharField(_("Auto_DB_Pro article number"), max_length=128)
    autodb_article_key = models.CharField(_("Auto_DB_Pro article key"), max_length=196)

    confidence = models.DecimalField(_("Уверенность"), max_digits=4, decimal_places=3, blank=True, null=True)
    manual_confirmed = models.BooleanField(_("Подтверждено вручную"), default=False, db_index=True)
    source = models.CharField(_("Источник"), max_length=64, blank=True, default="manual")
    created_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        related_name="autodb_manual_mappings",
        blank=True,
        null=True,
        verbose_name=_("Кем создано"),
    )
    note = models.CharField(_("Примечание"), max_length=255, blank=True, default="")

    class Meta:
        ordering = ("-updated_at",)
        verbose_name = _("Ручной маппинг Auto_DB_Pro")
        verbose_name_plural = _("Ручные маппинги Auto_DB_Pro")
        constraints = [
            models.UniqueConstraint(
                fields=("normalized_brand", "normalized_article", "autodb_article_key"),
                name="cat_adb_manual_map_unique",
            )
        ]
        indexes = [
            models.Index(
                fields=("normalized_brand", "normalized_article", "manual_confirmed"),
                name="cat_adb_manual_lookup_idx",
            )
        ]

    def __str__(self) -> str:
        return f"{self.brand}:{self.article} -> {self.autodb_article_key}"
