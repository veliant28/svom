from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class SecurityRule(UUIDPrimaryKeyMixin, TimestampedMixin):
    name = models.CharField(_("Name"), max_length=255)
    endpoint_pattern = models.CharField(_("Endpoint pattern"), max_length=255, blank=True, default="")
    scope = models.CharField(_("Scope"), max_length=64, blank=True, default="")
    limit = models.PositiveIntegerField(_("Limit"), default=0)
    window_seconds = models.PositiveIntegerField(_("Window seconds"), default=60)
    action = models.CharField(_("Action"), max_length=64, blank=True, default="")
    enabled = models.BooleanField(_("Enabled"), default=True, db_index=True)
    priority = models.PositiveIntegerField(_("Priority"), default=100)
    metadata = models.JSONField(_("Metadata"), blank=True, default=dict)

    class Meta:
        ordering = ("priority", "name")
        verbose_name = _("Security rule")
        verbose_name_plural = _("Security rules")

    def __str__(self) -> str:
        return self.name
