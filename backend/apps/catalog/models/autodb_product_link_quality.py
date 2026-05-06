from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class AutoDbProductLinkQuality(UUIDPrimaryKeyMixin, TimestampedMixin):
    STATUS_TRUSTED = "trusted"
    STATUS_SUSPICIOUS = "suspicious"
    STATUS_NEEDS_MANUAL_REVIEW = "needs_manual_review"
    STATUS_CHOICES = (
        (STATUS_TRUSTED, _("Trusted")),
        (STATUS_SUSPICIOUS, _("Suspicious")),
        (STATUS_NEEDS_MANUAL_REVIEW, _("Needs manual review")),
    )

    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="autodb_link_qualities",
        verbose_name=_("Товар"),
    )
    autodb_article_key = models.CharField(_("Auto_DB_Pro article key"), max_length=196, db_index=True)
    autodb_supplier_id = models.BigIntegerField(_("Auto_DB_Pro supplier ID"), blank=True, null=True, db_index=True)
    autodb_article_number = models.CharField(
        _("Auto_DB_Pro article number"),
        max_length=128,
        blank=True,
        default="",
        db_index=True,
    )
    status = models.CharField(_("Статус качества link"), max_length=32, choices=STATUS_CHOICES, db_index=True)
    reason = models.CharField(_("Причина"), max_length=512, blank=True, default="")
    evidence = models.JSONField(_("Доказательства"), default=dict, blank=True)
    checked_at = models.DateTimeField(_("Проверено"), blank=True, null=True, db_index=True)
    manually_confirmed = models.BooleanField(_("Подтверждено вручную"), default=False, db_index=True)
    note = models.CharField(_("Примечание"), max_length=255, blank=True, default="")

    class Meta:
        ordering = ("-checked_at", "-updated_at")
        verbose_name = _("Качество link Auto_DB_Pro")
        verbose_name_plural = _("Качество links Auto_DB_Pro")
        constraints = [
            models.UniqueConstraint(
                fields=("product", "autodb_article_key"),
                name="cat_adb_link_q_prod_key",
            )
        ]
        indexes = [
            models.Index(
                fields=("status", "manually_confirmed"),
                name="cat_adb_link_q_stat_idx",
            )
        ]

    def __str__(self) -> str:
        return f"{self.product_id}:{self.autodb_article_key}:{self.status}"
