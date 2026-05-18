from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class AutoDbTranslationSettings(UUIDPrimaryKeyMixin, TimestampedMixin):
    DEFAULT_CODE = "default"
    PROVIDER_LIBRETRANSLATE = "libretranslate"
    PROVIDER_GOOGLE = "google"
    PROVIDER_CHOICES = (
        (PROVIDER_LIBRETRANSLATE, "libretranslate"),
        (PROVIDER_GOOGLE, "google"),
    )

    code = models.CharField(max_length=32, unique=True, default=DEFAULT_CODE)
    provider = models.CharField(
        _("Translation provider"),
        max_length=32,
        choices=PROVIDER_CHOICES,
        default=PROVIDER_LIBRETRANSLATE,
    )
    google_api_key = models.TextField(_("Google Translate API key"), blank=True, default="")

    class Meta:
        db_table = "autodb_translation_settings"
        verbose_name = _("Auto_DB translation settings")
        verbose_name_plural = _("Auto_DB translation settings")

    def __str__(self) -> str:
        return "Auto_DB translation settings"

    @property
    def google_api_key_masked(self) -> str:
        key = str(self.google_api_key or "").strip()
        if not key:
            return ""
        if len(key) <= 8:
            return "*" * len(key)
        return f"{key[:4]}{'*' * (len(key) - 8)}{key[-4:]}"
