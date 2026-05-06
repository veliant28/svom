from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import PublishableMixin, TimestampedMixin, UUIDPrimaryKeyMixin


class Category(UUIDPrimaryKeyMixin, TimestampedMixin, PublishableMixin):
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

    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="children",
        blank=True,
        null=True,
        verbose_name=_("Родительская категория"),
    )
    name = models.CharField(_("Название"), max_length=180)
    name_uk = models.CharField(_("Название (UA)"), max_length=180, blank=True, default="")
    name_ru = models.CharField(_("Название (RU)"), max_length=180, blank=True, default="")
    name_en = models.CharField(_("Название (EN)"), max_length=180, blank=True, default="")
    slug = models.SlugField(_("Slug"), max_length=220, unique=True)
    autodb_prd_id = models.BigIntegerField(_("Auto_DB_Pro PRD ID"), blank=True, null=True, unique=True, db_index=True)
    source = models.CharField(_("Источник"), max_length=24, choices=SOURCE_CHOICES, blank=True, default=SOURCE_LEGACY, db_index=True)
    source_payload = models.JSONField(_("Source payload"), default=dict, blank=True)
    source_hash = models.CharField(_("Source hash"), max_length=64, blank=True, default="", db_index=True)
    description = models.TextField(_("Описание"), blank=True)

    class Meta:
        ordering = ("name",)
        verbose_name = _("Категория")
        verbose_name_plural = _("Категории")

    def __str__(self) -> str:
        return self.name

    def get_localized_name(self, locale: str | None) -> str:
        lang = (locale or "").lower()
        if lang.startswith("ru"):
            return self.name_ru or self.name_uk or self.name
        if lang.startswith("en"):
            return self.name_en or self.name_uk or self.name
        return self.name_uk or self.name
