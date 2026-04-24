from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin
from apps.seo.constants import SEO_DEFAULT_ROBOTS_DIRECTIVE


class SeoSiteSettings(UUIDPrimaryKeyMixin, TimestampedMixin):
    DEFAULT_CODE = "default"

    code = models.CharField(max_length=32, unique=True, default=DEFAULT_CODE)
    is_enabled = models.BooleanField(_("SEO включено"), default=True)

    default_meta_title_uk = models.CharField(_("Default meta title (UK)"), max_length=255, blank=True, default="")
    default_meta_title_ru = models.CharField(_("Default meta title (RU)"), max_length=255, blank=True, default="")
    default_meta_title_en = models.CharField(_("Default meta title (EN)"), max_length=255, blank=True, default="")

    default_meta_description_uk = models.TextField(_("Default meta description (UK)"), blank=True, default="")
    default_meta_description_ru = models.TextField(_("Default meta description (RU)"), blank=True, default="")
    default_meta_description_en = models.TextField(_("Default meta description (EN)"), blank=True, default="")

    default_og_title_uk = models.CharField(_("Default OG title (UK)"), max_length=255, blank=True, default="")
    default_og_title_ru = models.CharField(_("Default OG title (RU)"), max_length=255, blank=True, default="")
    default_og_title_en = models.CharField(_("Default OG title (EN)"), max_length=255, blank=True, default="")

    default_og_description_uk = models.TextField(_("Default OG description (UK)"), blank=True, default="")
    default_og_description_ru = models.TextField(_("Default OG description (RU)"), blank=True, default="")
    default_og_description_en = models.TextField(_("Default OG description (EN)"), blank=True, default="")

    default_robots_directive = models.CharField(
        _("Default robots directive"),
        max_length=64,
        blank=True,
        default=SEO_DEFAULT_ROBOTS_DIRECTIVE,
    )
    canonical_base_url = models.URLField(_("Canonical base URL"), blank=True, default="")

    sitemap_enabled = models.BooleanField(_("Sitemap enabled"), default=True)
    product_sitemap_enabled = models.BooleanField(_("Product sitemap enabled"), default=True)
    category_sitemap_enabled = models.BooleanField(_("Category sitemap enabled"), default=True)
    brand_sitemap_enabled = models.BooleanField(_("Brand sitemap enabled"), default=True)
    sitemap_last_rebuild_at = models.DateTimeField(_("Sitemap last rebuild at"), blank=True, null=True)

    robots_txt = models.TextField(_("Robots.txt"), blank=True, default="")

    class Meta:
        verbose_name = _("SEO site settings")
        verbose_name_plural = _("SEO site settings")

    def __str__(self) -> str:
        return "SEO site settings"
