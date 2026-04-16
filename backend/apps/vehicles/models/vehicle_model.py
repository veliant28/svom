from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import PublishableMixin, TimestampedMixin, UUIDPrimaryKeyMixin


class VehicleModel(UUIDPrimaryKeyMixin, TimestampedMixin, PublishableMixin):
    make = models.ForeignKey(
        "vehicles.VehicleMake",
        on_delete=models.CASCADE,
        related_name="models",
        verbose_name=_("Марка"),
    )
    name = models.CharField(_("Название"), max_length=120)
    slug = models.SlugField(_("Slug"), max_length=140)

    class Meta:
        ordering = ("make__name", "name")
        verbose_name = _("Модель автомобиля")
        verbose_name_plural = _("Модели автомобилей")
        constraints = [
            models.UniqueConstraint(
                fields=("make", "slug"),
                name="vehicles_model_unique_slug_per_make",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.make.name} {self.name}"
