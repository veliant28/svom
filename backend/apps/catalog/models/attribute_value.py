from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class AttributeValue(UUIDPrimaryKeyMixin, TimestampedMixin):
    SOURCE_AUTODB_PRO = "autodb_pro"
    SOURCE_MANUAL = "manual"
    SOURCE_LEGACY = "legacy"
    SOURCE_IMPORT = "import"
    SOURCE_CHOICES = (
        (SOURCE_AUTODB_PRO, _("Auto_DB_Pro")),
        (SOURCE_MANUAL, _("Manual")),
        (SOURCE_LEGACY, _("Legacy")),
        (SOURCE_IMPORT, _("Import")),
    )

    attribute = models.ForeignKey(
        "catalog.Attribute",
        on_delete=models.CASCADE,
        related_name="values",
        verbose_name=_("Атрибут"),
    )
    value = models.CharField(_("Значение"), max_length=255)
    value_uk = models.CharField(_("Значение (UA)"), max_length=255, blank=True, default="")
    value_ru = models.CharField(_("Значение (RU)"), max_length=255, blank=True, default="")
    value_en = models.CharField(_("Значение (EN)"), max_length=255, blank=True, default="")
    sort_order = models.PositiveIntegerField(_("Порядок сортировки"), default=0)
    autodb_attribute_id = models.BigIntegerField(_("Auto_DB_Pro attribute ID"), blank=True, null=True, db_index=True)
    source = models.CharField(_("Источник"), max_length=24, choices=SOURCE_CHOICES, blank=True, default=SOURCE_LEGACY, db_index=True)
    source_payload = models.JSONField(_("Source payload"), default=dict, blank=True)
    source_hash = models.CharField(_("Source hash"), max_length=64, blank=True, default="", db_index=True)

    class Meta:
        ordering = ("attribute__name", "sort_order", "value")
        verbose_name = _("Значение атрибута")
        verbose_name_plural = _("Значения атрибутов")
        constraints = [
            models.UniqueConstraint(
                fields=("attribute", "value"),
                name="catalog_attributevalue_unique_value_per_attribute",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.attribute.name}: {self.value}"
