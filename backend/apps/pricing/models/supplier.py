from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import PublishableMixin, TimestampedMixin, UUIDPrimaryKeyMixin


class Supplier(UUIDPrimaryKeyMixin, TimestampedMixin, PublishableMixin):
    name = models.CharField(_("Название"), max_length=180, unique=True)
    code = models.SlugField(_("Код"), max_length=64, unique=True)
    contact_email = models.EmailField(_("Контактный email"), blank=True)
    contact_phone = models.CharField(_("Контактный телефон"), max_length=32, blank=True)
    is_preferred = models.BooleanField(_("Предпочтительный"), default=False)
    priority = models.PositiveIntegerField(_("Приоритет"), default=100)
    quality_score = models.DecimalField(_("Оценка качества"), max_digits=5, decimal_places=2, default=1)

    class Meta:
        ordering = ("name",)
        verbose_name = _("Поставщик")
        verbose_name_plural = _("Поставщики")

    def __str__(self) -> str:
        return self.name
