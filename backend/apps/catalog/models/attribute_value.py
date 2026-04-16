from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class AttributeValue(UUIDPrimaryKeyMixin, TimestampedMixin):
    attribute = models.ForeignKey(
        "catalog.Attribute",
        on_delete=models.CASCADE,
        related_name="values",
        verbose_name=_("Атрибут"),
    )
    value = models.CharField(_("Значение"), max_length=255)
    sort_order = models.PositiveIntegerField(_("Порядок сортировки"), default=0)

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
