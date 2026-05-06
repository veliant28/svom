from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class ProductFitment(UUIDPrimaryKeyMixin, TimestampedMixin):
    SOURCE_MANUAL = "manual"
    SOURCE_AUTODB_PRO = "autodb_pro"
    SOURCE_LEGACY = "legacy"
    SOURCE_CHOICES = (
        (SOURCE_MANUAL, _("Manual")),
        (SOURCE_AUTODB_PRO, _("Auto_DB_Pro")),
        (SOURCE_LEGACY, _("Legacy")),
    )
    QUALITY_STATUS_TRUSTED = "trusted"
    QUALITY_STATUS_SUSPICIOUS = "suspicious"
    QUALITY_STATUS_NEEDS_MANUAL_REVIEW = "needs_manual_review"
    QUALITY_STATUS_CHOICES = (
        (QUALITY_STATUS_TRUSTED, _("Trusted")),
        (QUALITY_STATUS_SUSPICIOUS, _("Suspicious")),
        (QUALITY_STATUS_NEEDS_MANUAL_REVIEW, _("Needs manual review")),
    )

    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="fitments",
        verbose_name=_("Товар"),
    )
    modification = models.ForeignKey(
        "vehicles.VehicleModification",
        on_delete=models.CASCADE,
        related_name="fitments",
        blank=True,
        null=True,
        verbose_name=_("Модификация"),
    )
    note = models.CharField(_("Примечание"), max_length=255, blank=True)
    is_exact = models.BooleanField(_("Точное соответствие"), default=True)
    source = models.CharField(_("Источник"), max_length=24, choices=SOURCE_CHOICES, blank=True, default=SOURCE_LEGACY, db_index=True)
    autodb_passanger_car_id = models.BigIntegerField(_("Auto_DB_Pro passanger_car ID"), blank=True, null=True, db_index=True)
    linkage_type = models.CharField(_("Тип связи"), max_length=32, blank=True, default="", db_index=True)
    autodb_article_key = models.CharField(_("Auto_DB_Pro article key"), max_length=196, blank=True, default="", db_index=True)
    supplier_id = models.BigIntegerField(_("Auto_DB_Pro supplier ID"), blank=True, null=True, db_index=True)
    article_number = models.CharField(_("Auto_DB_Pro article number"), max_length=128, blank=True, default="", db_index=True)
    source_payload = models.JSONField(_("Source payload"), default=dict, blank=True)
    source_hash = models.CharField(_("Source hash"), max_length=64, blank=True, default="", db_index=True)
    is_stale = models.BooleanField(_("Устаревшая совместимость"), default=False, db_index=True)
    stale_reason = models.CharField(_("Причина устаревания"), max_length=64, blank=True, default="")
    manual_locked = models.BooleanField(_("Совместимость закреплена вручную"), default=False, db_index=True)
    quality_status = models.CharField(
        _("Статус качества link"),
        max_length=32,
        choices=QUALITY_STATUS_CHOICES,
        blank=True,
        default="",
        db_index=True,
    )
    quality_reason = models.CharField(_("Причина качества link"), max_length=512, blank=True, default="")
    excluded_from_public_filtering = models.BooleanField(
        _("Исключено из публичной фильтрации"),
        default=False,
        db_index=True,
    )

    class Meta:
        ordering = ("product__name",)
        verbose_name = _("Применимость товара")
        verbose_name_plural = _("Применимость товаров")
        constraints = [
            models.UniqueConstraint(
                fields=("product", "modification"),
                condition=Q(modification__isnull=False),
                name="compatibility_fitment_unique_product_modification",
            ),
            models.UniqueConstraint(
                fields=("product", "source", "linkage_type", "autodb_passanger_car_id"),
                condition=Q(autodb_passanger_car_id__isnull=False),
                name="compatibility_fitment_unique_autodb_linkage",
            ),
            models.UniqueConstraint(
                fields=("product", "source", "source_hash"),
                condition=~Q(source_hash=""),
                name="compatibility_fitment_unique_source_hash",
            ),
        ]

    def __str__(self) -> str:
        if self.modification_id:
            return f"{self.product} -> {self.modification}"
        if self.autodb_passanger_car_id:
            return f"{self.product} -> {self.linkage_type}:{self.autodb_passanger_car_id}"
        return f"{self.product} -> fitment"
