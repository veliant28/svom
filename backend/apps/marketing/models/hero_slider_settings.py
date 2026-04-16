from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class HeroSliderSettings(UUIDPrimaryKeyMixin, TimestampedMixin):
    code = models.CharField(_("Код"), max_length=32, unique=True, default="default")
    autoplay_enabled = models.BooleanField(_("Автопрокрутка включена"), default=True)
    transition_interval_ms = models.PositiveIntegerField(_("Интервал перехода, мс"), default=5000)
    transition_speed_ms = models.PositiveIntegerField(_("Скорость перехода, мс"), default=600)
    max_active_slides = models.PositiveSmallIntegerField(_("Максимум активных слайдов"), default=10)

    class Meta:
        verbose_name = _("Настройки hero-слайдера")
        verbose_name_plural = _("Настройки hero-слайдера")

    def __str__(self) -> str:
        return self.code
