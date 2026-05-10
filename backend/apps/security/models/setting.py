from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin


class SecuritySetting(TimestampedMixin):
    key = models.CharField(_("Key"), max_length=128, primary_key=True)
    value = models.JSONField(_("Value"), blank=True, default=dict)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="security_settings_updated",
    )

    class Meta:
        ordering = ("key",)
        verbose_name = _("Security setting")
        verbose_name_plural = _("Security settings")

    def __str__(self) -> str:
        return self.key
