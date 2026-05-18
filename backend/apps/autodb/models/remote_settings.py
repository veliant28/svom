from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class AutoDbRemoteSettings(UUIDPrimaryKeyMixin, TimestampedMixin):
    DEFAULT_CODE = "default"

    code = models.CharField(max_length=32, unique=True, default=DEFAULT_CODE)
    remote_host = models.CharField(_("Remote host"), max_length=255, blank=True, default="")
    remote_port = models.PositiveIntegerField(_("Remote port"), default=3306)
    remote_database = models.CharField(_("Remote database"), max_length=255, blank=True, default="")
    remote_user = models.CharField(_("Remote user"), max_length=255, blank=True, default="")
    remote_password = models.TextField(_("Remote password"), blank=True, default="")
    image_base_url = models.CharField(_("Image base URL"), max_length=512, blank=True, default="")

    class Meta:
        db_table = "autodb_remote_settings"
        verbose_name = _("Auto_DB remote settings")
        verbose_name_plural = _("Auto_DB remote settings")

    def __str__(self) -> str:
        return "Auto_DB remote settings"

    @property
    def remote_user_masked(self) -> str:
        return _mask_value(self.remote_user)

    @property
    def remote_password_masked(self) -> str:
        return _mask_value(self.remote_password)


def _mask_value(value: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        return ""
    if len(clean) <= 8:
        return "*" * len(clean)
    return f"{clean[:4]}{'*' * (len(clean) - 8)}{clean[-4:]}"
