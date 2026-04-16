from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import PublishableMixin, SortableMixin, TimestampedMixin, UUIDPrimaryKeyMixin


class HeroSlide(UUIDPrimaryKeyMixin, TimestampedMixin, PublishableMixin, SortableMixin):
    title_uk = models.CharField(_("Заголовок (uk)"), max_length=255, blank=True)
    title_ru = models.CharField(_("Заголовок (ru)"), max_length=255, blank=True)
    title_en = models.CharField(_("Заголовок (en)"), max_length=255, blank=True)
    subtitle_uk = models.CharField(_("Подзаголовок (uk)"), max_length=500, blank=True)
    subtitle_ru = models.CharField(_("Подзаголовок (ru)"), max_length=500, blank=True)
    subtitle_en = models.CharField(_("Подзаголовок (en)"), max_length=500, blank=True)
    desktop_image = models.ImageField(_("Изображение для десктопа"), upload_to="marketing/hero/desktop/")
    mobile_image = models.ImageField(_("Изображение для мобильных"), upload_to="marketing/hero/mobile/")
    cta_url = models.URLField(_("Ссылка CTA"), blank=True)

    class Meta(SortableMixin.Meta):
        verbose_name = _("Слайд hero")
        verbose_name_plural = _("Слайды hero")

    def __str__(self) -> str:
        return self.title_uk or self.title_en or self.title_ru or str(self.id)
