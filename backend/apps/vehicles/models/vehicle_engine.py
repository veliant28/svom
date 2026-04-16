from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import PublishableMixin, TimestampedMixin, UUIDPrimaryKeyMixin


class VehicleEngine(UUIDPrimaryKeyMixin, TimestampedMixin, PublishableMixin):
    FUEL_PETROL = "petrol"
    FUEL_DIESEL = "diesel"
    FUEL_HYBRID = "hybrid"
    FUEL_EV = "ev"
    FUEL_OTHER = "other"

    FUEL_CHOICES = (
        (FUEL_PETROL, _("Бензин")),
        (FUEL_DIESEL, _("Дизель")),
        (FUEL_HYBRID, _("Гибрид")),
        (FUEL_EV, _("Электро")),
        (FUEL_OTHER, _("Другое")),
    )

    generation = models.ForeignKey(
        "vehicles.VehicleGeneration",
        on_delete=models.CASCADE,
        related_name="engines",
        verbose_name=_("Поколение"),
    )
    name = models.CharField(_("Название"), max_length=140)
    code = models.CharField(_("Код"), max_length=64, blank=True)
    displacement_cc = models.PositiveIntegerField(_("Объем, см3"), blank=True, null=True)
    fuel_type = models.CharField(_("Тип топлива"), max_length=16, choices=FUEL_CHOICES, default=FUEL_OTHER)
    power_hp = models.PositiveIntegerField(_("Мощность, л.с."), blank=True, null=True)

    class Meta:
        ordering = ("generation__model__make__name", "generation__model__name", "name")
        verbose_name = _("Двигатель")
        verbose_name_plural = _("Двигатели")
        constraints = [
            models.UniqueConstraint(
                fields=("generation", "name", "code"),
                name="vehicles_engine_unique_generation_name_code",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.generation} - {self.name}"
