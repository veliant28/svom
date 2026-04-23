from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import PublishableMixin, SortableMixin, TimestampedMixin, UUIDPrimaryKeyMixin


class PromoBanner(UUIDPrimaryKeyMixin, TimestampedMixin, PublishableMixin, SortableMixin):
    title_uk = models.CharField(_("Заголовок (uk)"), max_length=255, blank=True)
    title_ru = models.CharField(_("Заголовок (ru)"), max_length=255, blank=True)
    title_en = models.CharField(_("Заголовок (en)"), max_length=255, blank=True)
    description_uk = models.CharField(_("Описание (uk)"), max_length=500, blank=True)
    description_ru = models.CharField(_("Описание (ru)"), max_length=500, blank=True)
    description_en = models.CharField(_("Описание (en)"), max_length=500, blank=True)
    image = models.ImageField(_("Изображение"), upload_to="marketing/promo/")
    target_url = models.URLField(_("Целевая ссылка"), blank=True)
    starts_at = models.DateTimeField(_("Показ с"), null=True, blank=True)
    ends_at = models.DateTimeField(_("Показ до"), null=True, blank=True)

    class Meta(SortableMixin.Meta):
        verbose_name = _("Промо-баннер")
        verbose_name_plural = _("Промо-баннеры")

    def __str__(self) -> str:
        return self.title_uk or self.title_en or self.title_ru or str(self.id)
