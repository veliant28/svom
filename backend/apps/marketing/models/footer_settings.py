from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class FooterSettings(UUIDPrimaryKeyMixin, TimestampedMixin):
    DEFAULT_CODE = "default"

    code = models.CharField(_("Код"), max_length=32, unique=True, default=DEFAULT_CODE)
    working_hours = models.CharField(_("Время работы"), max_length=255, default="ПН, ВТ, СР, ЧТ, ПТ, СБ 10:00-17:00")
    phone = models.CharField(_("Телефон"), max_length=64, default="+38(099)897-94-67")

    class Meta:
        verbose_name = _("Настройки футера")
        verbose_name_plural = _("Настройки футера")

    def __str__(self) -> str:
        return f"FooterSettings:{self.code}"
