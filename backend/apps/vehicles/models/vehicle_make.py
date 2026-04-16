from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import PublishableMixin, TimestampedMixin, UUIDPrimaryKeyMixin


class VehicleMake(UUIDPrimaryKeyMixin, TimestampedMixin, PublishableMixin):
    name = models.CharField(_("Название"), max_length=120, unique=True)
    slug = models.SlugField(_("Slug"), max_length=140, unique=True)

    class Meta:
        ordering = ("name",)
        verbose_name = _("Марка автомобиля")
        verbose_name_plural = _("Марки автомобилей")

    def __str__(self) -> str:
        return self.name
