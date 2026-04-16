from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import PublishableMixin, TimestampedMixin, UUIDPrimaryKeyMixin


class VehicleGeneration(UUIDPrimaryKeyMixin, TimestampedMixin, PublishableMixin):
    model = models.ForeignKey(
        "vehicles.VehicleModel",
        on_delete=models.CASCADE,
        related_name="generations",
        verbose_name=_("Модель"),
    )
    name = models.CharField(_("Название"), max_length=140)
    year_start = models.PositiveSmallIntegerField(_("Год начала"), blank=True, null=True)
    year_end = models.PositiveSmallIntegerField(_("Год окончания"), blank=True, null=True)

    class Meta:
        ordering = ("model__make__name", "model__name", "-year_start")
        verbose_name = _("Поколение автомобиля")
        verbose_name_plural = _("Поколения автомобилей")
        constraints = [
            models.UniqueConstraint(
                fields=("model", "name", "year_start"),
                name="vehicles_generation_unique_model_name_start",
            ),
        ]

    def __str__(self) -> str:
        years = ""
        if self.year_start:
            years = str(self.year_start)
            if self.year_end:
                years = f"{years}-{self.year_end}"
        return f"{self.model} {self.name} {years}".strip()
