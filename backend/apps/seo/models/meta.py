from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin
from apps.seo.constants import SEO_ENTITY_TYPE_CHOICES, SEO_LOCALE_CHOICES


class SeoMetaTemplate(UUIDPrimaryKeyMixin, TimestampedMixin):
    entity_type = models.CharField(_("Entity type"), max_length=24, choices=SEO_ENTITY_TYPE_CHOICES)
    locale = models.CharField(_("Locale"), max_length=2, choices=SEO_LOCALE_CHOICES)

    title_template = models.CharField(_("Title template"), max_length=255, blank=True, default="")
    description_template = models.TextField(_("Description template"), blank=True, default="")
    h1_template = models.CharField(_("H1 template"), max_length=255, blank=True, default="")
    og_title_template = models.CharField(_("OG title template"), max_length=255, blank=True, default="")
    og_description_template = models.TextField(_("OG description template"), blank=True, default="")

    is_active = models.BooleanField(_("Active"), default=True)

    class Meta:
        verbose_name = _("SEO meta template")
        verbose_name_plural = _("SEO meta templates")
        constraints = [
            models.UniqueConstraint(
                fields=("entity_type", "locale"),
                name="seo_meta_template_entity_locale_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=("entity_type", "locale", "is_active"), name="seo_template_lookup_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.entity_type}:{self.locale}"


class SeoMetaOverride(UUIDPrimaryKeyMixin, TimestampedMixin):
    path = models.CharField(_("Path"), max_length=500)
    locale = models.CharField(_("Locale"), max_length=2, choices=SEO_LOCALE_CHOICES)

    meta_title = models.CharField(_("Meta title"), max_length=255, blank=True, default="")
    meta_description = models.TextField(_("Meta description"), blank=True, default="")
    h1 = models.CharField(_("H1"), max_length=255, blank=True, default="")
    canonical_url = models.URLField(_("Canonical URL"), blank=True, default="")
    robots_directive = models.CharField(_("Robots directive"), max_length=64, blank=True, default="")
    og_title = models.CharField(_("OG title"), max_length=255, blank=True, default="")
    og_description = models.TextField(_("OG description"), blank=True, default="")
    og_image_url = models.URLField(_("OG image URL"), blank=True, default="")

    is_active = models.BooleanField(_("Active"), default=True)

    class Meta:
        verbose_name = _("SEO meta override")
        verbose_name_plural = _("SEO meta overrides")
        constraints = [
            models.UniqueConstraint(fields=("path", "locale"), name="seo_meta_override_path_locale_uniq"),
        ]
        indexes = [
            models.Index(fields=("path", "locale", "is_active"), name="seo_override_lookup_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.path} [{self.locale}]"
