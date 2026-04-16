from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import PublishableMixin, TimestampedMixin, UUIDPrimaryKeyMixin


class Brand(UUIDPrimaryKeyMixin, TimestampedMixin, PublishableMixin):
    name = models.CharField(_("Название"), max_length=120, unique=True)
    slug = models.SlugField(_("Slug"), max_length=140, unique=True)
    country = models.CharField(_("Страна"), max_length=120, blank=True)
    description = models.TextField(_("Описание"), blank=True)
    logo = models.ImageField(_("Логотип"), upload_to="catalog/brands/logos/", blank=True)

    class Meta:
        ordering = ("name",)
        verbose_name = _("Бренд")
        verbose_name_plural = _("Бренды")

    def __str__(self) -> str:
        return self.name
