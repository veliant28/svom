from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class Attribute(UUIDPrimaryKeyMixin, TimestampedMixin):
    SOURCE_AUTODB_PRO = "autodb_pro"
    SOURCE_MANUAL = "manual"
    SOURCE_LEGACY = "legacy"
    SOURCE_IMPORT = "import"
    SOURCE_CHOICES = (
        (SOURCE_AUTODB_PRO, _("Auto_DB_Pro")),
        (SOURCE_MANUAL, _("Manual")),
        (SOURCE_LEGACY, _("Legacy")),
        (SOURCE_IMPORT, _("Import")),
    )

    TYPE_TEXT = "text"
    TYPE_NUMBER = "number"
    TYPE_BOOLEAN = "boolean"
    TYPE_SELECT = "select"

    TYPE_CHOICES = (
        (TYPE_TEXT, _("Текст")),
        (TYPE_NUMBER, _("Число")),
        (TYPE_BOOLEAN, _("Логический")),
        (TYPE_SELECT, _("Справочник")),
    )

    name = models.CharField(_("Название"), max_length=120, unique=True)
    name_uk = models.CharField(_("Название (UA)"), max_length=120, blank=True, default="")
    name_ru = models.CharField(_("Название (RU)"), max_length=120, blank=True, default="")
    name_en = models.CharField(_("Название (EN)"), max_length=120, blank=True, default="")
    slug = models.SlugField(_("Slug"), max_length=150, unique=True)
    value_type = models.CharField(_("Тип значения"), max_length=16, choices=TYPE_CHOICES, default=TYPE_TEXT)
    is_filterable = models.BooleanField(_("Фильтруемый"), default=True)
    autodb_attribute_id = models.BigIntegerField(_("Auto_DB_Pro attribute ID"), blank=True, null=True, db_index=True)
    source = models.CharField(_("Источник"), max_length=24, choices=SOURCE_CHOICES, blank=True, default=SOURCE_LEGACY, db_index=True)
    source_payload = models.JSONField(_("Source payload"), default=dict, blank=True)
    source_hash = models.CharField(_("Source hash"), max_length=64, blank=True, default="", db_index=True)

    class Meta:
        ordering = ("name",)
        verbose_name = _("Атрибут")
        verbose_name_plural = _("Атрибуты")

    def __str__(self) -> str:
        return self.name
