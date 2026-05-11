from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class GarageVehicle(UUIDPrimaryKeyMixin, TimestampedMixin):
    CATALOG_SOURCE_AUTODB_PRO = "autodb_pro"
    CATALOG_SOURCE_CHOICES = (
        (CATALOG_SOURCE_AUTODB_PRO, _("Auto_DB_Pro")),
    )

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
    autodb_manufacturer_id = models.IntegerField(_("Auto_DB_Pro manufacturer id"), blank=True, null=True, db_index=True)
    autodb_model_id = models.IntegerField(_("Auto_DB_Pro model id"), blank=True, null=True, db_index=True)
    autodb_passanger_car_id = models.IntegerField(_("Auto_DB_Pro passanger car id"), blank=True, null=True, db_index=True)
    autodb_vehicle_label = models.CharField(_("Auto_DB_Pro vehicle label"), max_length=255, blank=True, default="")
    autodb_modification = models.CharField(_("Auto_DB_Pro modification"), max_length=255, blank=True, default="")
    autodb_engine = models.CharField(_("Auto_DB_Pro engine"), max_length=255, blank=True, default="")
    autodb_power_hp = models.PositiveSmallIntegerField(_("Auto_DB_Pro power HP"), blank=True, null=True)
    autodb_power_kw = models.PositiveSmallIntegerField(_("Auto_DB_Pro power kW"), blank=True, null=True)
    catalog_source = models.CharField(
        _("Каталог-источник"),
        max_length=24,
        choices=CATALOG_SOURCE_CHOICES,
        default=CATALOG_SOURCE_AUTODB_PRO,
        db_index=True,
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
                fields=("user", "autodb_passanger_car_id"),
                condition=Q(autodb_passanger_car_id__isnull=False),
                name="users_garage_unique_autodb_vehicle_per_user",
            ),
            models.UniqueConstraint(
                fields=("user",),
                condition=Q(is_primary=True),
                name="users_garage_single_primary_vehicle_per_user",
            ),
        ]

    def __str__(self) -> str:
        if self.autodb_passanger_car_id is not None:
            return self.autodb_vehicle_label or f"autodb:{self.autodb_passanger_car_id}"

        parts = [str(part) for part in (self.make, self.model) if part]
        title = " ".join(parts).strip() or str(self.pk)
        if self.modification:
            title = f"{title} ({self.modification})"
        return title
