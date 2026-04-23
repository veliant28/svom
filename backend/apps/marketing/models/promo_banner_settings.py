from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class PromoBannerSettings(UUIDPrimaryKeyMixin, TimestampedMixin):
    code = models.CharField(_("Код"), max_length=32, unique=True, default="default")
    autoplay_enabled = models.BooleanField(_("Автопрокрутка включена"), default=True)
    transition_interval_ms = models.PositiveIntegerField(_("Интервал перехода, мс"), default=4500)
    transition_speed_ms = models.PositiveIntegerField(_("Скорость перехода, мс"), default=700)
    transition_effect = models.CharField(_("Эффект смены"), max_length=32, default="fade")
    max_active_banners = models.PositiveSmallIntegerField(_("Максимум активных баннеров"), default=5)

    class Meta:
        verbose_name = _("Настройки промо-баннеров")
        verbose_name_plural = _("Настройки промо-баннеров")

    def __str__(self) -> str:
        return self.code
