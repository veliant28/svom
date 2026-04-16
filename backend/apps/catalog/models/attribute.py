from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class Attribute(UUIDPrimaryKeyMixin, TimestampedMixin):
    TYPE_TEXT = "text"
    TYPE_NUMBER = "number"
    TYPE_BOOLEAN = "boolean"
    TYPE_SELECT = "select"

    TYPE_CHOICES = (
        (TYPE_TEXT, _("Текст")),
        (TYPE_NUMBER, _("Число")),
        (TYPE_BOOLEAN, _("Логический")),
        (TYPE_SELECT, _("Справочник")),
    )

    name = models.CharField(_("Название"), max_length=120, unique=True)
    slug = models.SlugField(_("Slug"), max_length=150, unique=True)
    value_type = models.CharField(_("Тип значения"), max_length=16, choices=TYPE_CHOICES, default=TYPE_TEXT)
    is_filterable = models.BooleanField(_("Фильтруемый"), default=True)

    class Meta:
        ordering = ("name",)
        verbose_name = _("Атрибут")
        verbose_name_plural = _("Атрибуты")

    def __str__(self) -> str:
        return self.name
