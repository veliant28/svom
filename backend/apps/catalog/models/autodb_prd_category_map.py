from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class AutoDbPrdCategoryMap(UUIDPrimaryKeyMixin, TimestampedMixin):
    SOURCE_AUTO = "auto"
    SOURCE_MANUAL = "manual"
    SOURCE_CHOICES = (
        (SOURCE_AUTO, _("Автоматически")),
        (SOURCE_MANUAL, _("Вручную")),
    )

    prd_id = models.PositiveIntegerField(_("ID группы Auto-DB"), unique=True, db_index=True)
    prd_name = models.CharField(_("Название группы Auto-DB"), max_length=255, blank=True, default="")
    category = models.ForeignKey(
        "catalog.Category",
        on_delete=models.CASCADE,
        related_name="autodb_prd_maps",
        verbose_name=_("Категория каталога"),
    )
    source = models.CharField(_("Источник"), max_length=16, choices=SOURCE_CHOICES, default=SOURCE_AUTO)
    confidence = models.DecimalField(_("Уверенность"), max_digits=4, decimal_places=3, null=True, blank=True)

    class Meta:
        ordering = ("prd_name", "prd_id")
        verbose_name = _("Маппинг группы Auto-DB в категорию")
        verbose_name_plural = _("Маппинги групп Auto-DB в категории")

    def __str__(self) -> str:
        return f"{self.prd_id} -> {self.category_id}"

