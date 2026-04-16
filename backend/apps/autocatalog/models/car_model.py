from __future__ import annotations

from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from apps.autocatalog.models.normalization import collapse_spaces, normalize_name


class CarModel(models.Model):
    make = models.ForeignKey(
        "autocatalog.CarMake",
        on_delete=models.CASCADE,
        related_name="models",
        verbose_name=_("Марка"),
    )
    name = models.CharField(_("Модель"), max_length=120)
    slug = models.SlugField(_("Slug"), max_length=140)
    normalized_name = models.CharField(max_length=120, editable=False)
    created_at = models.DateTimeField(_("Создано"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Обновлено"), auto_now=True)

    class Meta:
        ordering = ("make__name", "name")
        verbose_name = _("Модель авто")
        verbose_name_plural = _("Модели авто")
        constraints = [
            models.UniqueConstraint(
                fields=("make", "normalized_name"),
                name="autocatalog_model_unique_name_per_make",
            ),
            models.UniqueConstraint(
                fields=("make", "slug"),
                name="autocatalog_model_unique_slug_per_make",
            ),
        ]

    def save(self, *args, **kwargs):
        self.name = collapse_spaces(self.name)
        self.normalized_name = normalize_name(self.name)
        if not self.slug:
            self.slug = slugify(self.name)[:140]
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.make.name} {self.name}"
