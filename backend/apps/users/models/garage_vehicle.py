from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class GarageVehicle(UUIDPrimaryKeyMixin, TimestampedMixin):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="garage_vehicles",
        verbose_name=_("Пользователь"),
    )
    make = models.ForeignKey(
        "vehicles.VehicleMake",
        on_delete=models.PROTECT,
        related_name="garage_vehicles",
        verbose_name=_("Марка"),
        blank=True,
        null=True,
    )
    model = models.ForeignKey(
        "vehicles.VehicleModel",
        on_delete=models.PROTECT,
        related_name="garage_vehicles",
        verbose_name=_("Модель"),
        blank=True,
        null=True,
    )
    generation = models.ForeignKey(
        "vehicles.VehicleGeneration",
        on_delete=models.PROTECT,
        related_name="garage_vehicles",
        blank=True,
        null=True,
        verbose_name=_("Поколение"),
    )
    engine = models.ForeignKey(
        "vehicles.VehicleEngine",
        on_delete=models.PROTECT,
        related_name="garage_vehicles",
        blank=True,
        null=True,
        verbose_name=_("Двигатель"),
    )
    modification = models.ForeignKey(
        "vehicles.VehicleModification",
        on_delete=models.PROTECT,
        related_name="garage_vehicles",
        blank=True,
        null=True,
        verbose_name=_("Модификация"),
    )
    car_modification = models.ForeignKey(
        "autocatalog.CarModification",
        on_delete=models.PROTECT,
        related_name="garage_vehicles",
        blank=True,
        null=True,
        verbose_name=_("Автокаталог"),
    )
    nickname = models.CharField(_("Название в гараже"), max_length=120, blank=True)
    year = models.PositiveSmallIntegerField(_("Год выпуска"), blank=True, null=True)
    vin = models.CharField(_("VIN"), max_length=32, blank=True)
    is_primary = models.BooleanField(_("Основной"), default=False)

    class Meta:
        ordering = ("-is_primary", "-created_at")
        verbose_name = _("Автомобиль в гараже")
        verbose_name_plural = _("Гараж пользователей")
        constraints = [
            models.UniqueConstraint(
                fields=("user", "make", "model", "generation", "engine", "modification", "vin"),
                name="users_garage_unique_vehicle_per_user",
            ),
            models.UniqueConstraint(
                fields=("user", "car_modification"),
                condition=Q(car_modification__isnull=False),
                name="users_garage_unique_autocatalog_vehicle_per_user",
            ),
            models.UniqueConstraint(
                fields=("user",),
                condition=Q(is_primary=True),
                name="users_garage_single_primary_vehicle_per_user",
            ),
        ]

    def __str__(self) -> str:
        if self.car_modification is not None:
            return str(self.car_modification)

        parts = [str(part) for part in (self.make, self.model) if part]
        title = " ".join(parts).strip() or str(self.pk)
        if self.modification:
            title = f"{title} ({self.modification})"
        return title
