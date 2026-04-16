from __future__ import annotations

from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from apps.autocatalog.models.normalization import collapse_spaces, normalize_name


class CarMake(models.Model):
    name = models.CharField(_("Марка"), max_length=120)
    slug = models.SlugField(_("Slug"), max_length=140, unique=True)
    normalized_name = models.CharField(max_length=120, unique=True, editable=False)
    created_at = models.DateTimeField(_("Создано"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Обновлено"), auto_now=True)

    class Meta:
        ordering = ("name",)
        verbose_name = _("Марка авто")
        verbose_name_plural = _("Марки авто")

    def save(self, *args, **kwargs):
        self.name = collapse_spaces(self.name)
        self.normalized_name = normalize_name(self.name)
        if not self.slug:
            self.slug = slugify(self.name)[:140]
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name
