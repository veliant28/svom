from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import PublishableMixin, TimestampedMixin, UUIDPrimaryKeyMixin


class Category(UUIDPrimaryKeyMixin, TimestampedMixin, PublishableMixin):
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="children",
        blank=True,
        null=True,
        verbose_name=_("Родительская категория"),
    )
    name = models.CharField(_("Название"), max_length=180)
    name_uk = models.CharField(_("Название (UA)"), max_length=180, blank=True, default="")
    name_ru = models.CharField(_("Название (RU)"), max_length=180, blank=True, default="")
    name_en = models.CharField(_("Название (EN)"), max_length=180, blank=True, default="")
    slug = models.SlugField(_("Slug"), max_length=220, unique=True)
    description = models.TextField(_("Описание"), blank=True)

    class Meta:
        ordering = ("name",)
        verbose_name = _("Категория")
        verbose_name_plural = _("Категории")

    def __str__(self) -> str:
        return self.name

    def get_localized_name(self, locale: str | None) -> str:
        lang = (locale or "").lower()
        if lang.startswith("ru"):
            return self.name_ru or self.name_uk or self.name
        if lang.startswith("en"):
            return self.name_en or self.name_uk or self.name
        return self.name_uk or self.name
