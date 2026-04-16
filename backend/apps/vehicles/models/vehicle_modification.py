from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import PublishableMixin, TimestampedMixin, UUIDPrimaryKeyMixin


class VehicleModification(UUIDPrimaryKeyMixin, TimestampedMixin, PublishableMixin):
    engine = models.ForeignKey(
        "vehicles.VehicleEngine",
        on_delete=models.CASCADE,
        related_name="modifications",
        verbose_name=_("Двигатель"),
    )
    name = models.CharField(_("Название"), max_length=160)
    body_type = models.CharField(_("Тип кузова"), max_length=80, blank=True)
    transmission = models.CharField(_("Трансмиссия"), max_length=80, blank=True)
    drivetrain = models.CharField(_("Привод"), max_length=80, blank=True)
    year_start = models.PositiveSmallIntegerField(_("Год начала"), blank=True, null=True)
    year_end = models.PositiveSmallIntegerField(_("Год окончания"), blank=True, null=True)

    class Meta:
        ordering = (
            "engine__generation__model__make__name",
            "engine__generation__model__name",
            "name",
        )
        verbose_name = _("Модификация автомобиля")
        verbose_name_plural = _("Модификации автомобилей")
        constraints = [
            models.UniqueConstraint(
                fields=("engine", "name", "year_start"),
                name="vehicles_modification_unique_engine_name_start",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.engine} - {self.name}"
