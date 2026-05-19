from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class ReturnServiceSettings(UUIDPrimaryKeyMixin, TimestampedMixin):
    DEFAULT_CODE = "default"

    code = models.CharField(_("Код профиля"), max_length=32, unique=True, default=DEFAULT_CODE)
    returns_enabled = models.BooleanField(_("Сервис возвратов включен"), default=False)

    returns_recipient_full_name = models.CharField(_("Получатель ФИО"), max_length=255, blank=True, default="")
    returns_recipient_phone = models.CharField(_("Получатель телефон"), max_length=32, blank=True, default="")

    returns_region_ref = models.CharField(_("Ref области"), max_length=64, blank=True, default="")
    returns_region_label = models.CharField(_("Область"), max_length=255, blank=True, default="")
    returns_city_ref = models.CharField(_("Ref города"), max_length=64, blank=True, default="")
    returns_city_label = models.CharField(_("Город"), max_length=255, blank=True, default="")
    returns_np_warehouse_text = models.CharField(_("Отделение Новой Почты"), max_length=255, blank=True, default="")

    returns_non_returnable_category_ids = models.JSONField(_("Невозвратные категории"), default=list, blank=True)
    returns_include_subcategories = models.BooleanField(_("Включать подкатегории"), default=True)

    class Meta:
        verbose_name = _("Настройки сервиса возвратов")
        verbose_name_plural = _("Настройки сервиса возвратов")

    def __str__(self) -> str:
        return f"ReturnServiceSettings:{self.code}"
