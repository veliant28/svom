from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class GoogleIntegrationSettings(UUIDPrimaryKeyMixin, TimestampedMixin):
    DEFAULT_CODE = "default"

    code = models.CharField(max_length=32, unique=True, default=DEFAULT_CODE)
    is_enabled = models.BooleanField(_("Google integration enabled"), default=False)

    ga4_measurement_id = models.CharField(_("GA4 Measurement ID"), max_length=64, blank=True, default="")
    gtm_container_id = models.CharField(_("GTM Container ID"), max_length=64, blank=True, default="")
    search_console_verification_token = models.CharField(
        _("Search Console verification token"),
        max_length=512,
        blank=True,
        default="",
    )
    google_site_verification_meta = models.CharField(
        _("Google site verification meta"),
        max_length=512,
        blank=True,
        default="",
    )

    consent_mode_enabled = models.BooleanField(_("Consent mode enabled"), default=False)
    ecommerce_events_enabled = models.BooleanField(_("Ecommerce events enabled"), default=True)
    debug_mode = models.BooleanField(_("Debug mode"), default=False)
    anonymize_ip = models.BooleanField(_("Anonymize IP"), default=True)

    class Meta:
        verbose_name = _("Google integration settings")
        verbose_name_plural = _("Google integration settings")

    def __str__(self) -> str:
        return "Google integration settings"


class GoogleEventSetting(UUIDPrimaryKeyMixin, TimestampedMixin):
    event_name = models.CharField(_("Event name"), max_length=120, unique=True)
    label = models.CharField(_("Label"), max_length=180)
    is_enabled = models.BooleanField(_("Enabled"), default=True)
    description = models.TextField(_("Description"), blank=True, default="")

    class Meta:
        verbose_name = _("Google event setting")
        verbose_name_plural = _("Google event settings")
        ordering = ("event_name",)

    def __str__(self) -> str:
        return self.event_name
