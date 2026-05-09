from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import PublishableMixin, TimestampedMixin, UUIDPrimaryKeyMixin


class CategoryNavigationCollection(UUIDPrimaryKeyMixin, TimestampedMixin, PublishableMixin):
    title = models.CharField(_("Название"), max_length=180)
    title_uk = models.CharField(_("Название (UA)"), max_length=180, blank=True, default="")
    title_ru = models.CharField(_("Название (RU)"), max_length=180, blank=True, default="")
    title_en = models.CharField(_("Название (EN)"), max_length=180, blank=True, default="")
    slug = models.SlugField(_("Slug"), max_length=220, unique=True)
    root_category = models.ForeignKey(
        "catalog.Category",
        on_delete=models.PROTECT,
        related_name="navigation_collections",
        blank=True,
        null=True,
        verbose_name=_("Корневая категория навигации"),
    )
    show_in_header = models.BooleanField(_("Показывать в шапке"), default=False, db_index=True)
    sort_order = models.PositiveIntegerField(_("Порядок сортировки"), default=1000, db_index=True)

    class Meta:
        ordering = ("sort_order", "title", "id")
        verbose_name = _("Навигационная коллекция")
        verbose_name_plural = _("Навигационные коллекции")

    def __str__(self) -> str:
        return self.title

    def get_localized_title(self, locale: str | None) -> str:
        lang = (locale or "").lower()
        if lang.startswith("ru"):
            return self.title_ru or self.title_uk or self.title
        if lang.startswith("en"):
            return self.title_en or self.title_uk or self.title
        return self.title_uk or self.title


class CategoryNavigationGroup(UUIDPrimaryKeyMixin, TimestampedMixin, PublishableMixin):
    collection = models.ForeignKey(
        "catalog.CategoryNavigationCollection",
        on_delete=models.CASCADE,
        related_name="groups",
        verbose_name=_("Коллекция"),
    )
    title = models.CharField(_("Название"), max_length=180)
    title_uk = models.CharField(_("Название (UA)"), max_length=180, blank=True, default="")
    title_ru = models.CharField(_("Название (RU)"), max_length=180, blank=True, default="")
    title_en = models.CharField(_("Название (EN)"), max_length=180, blank=True, default="")
    slug = models.SlugField(_("Slug"), max_length=220)
    sort_order = models.PositiveIntegerField(_("Порядок сортировки"), default=1000, db_index=True)

    class Meta:
        ordering = ("sort_order", "title", "id")
        constraints = (
            models.UniqueConstraint(fields=("collection", "slug"), name="uniq_catalog_nav_group_collection_slug"),
        )
        verbose_name = _("Группа навигации")
        verbose_name_plural = _("Группы навигации")

    def __str__(self) -> str:
        return self.title

    def get_localized_title(self, locale: str | None) -> str:
        lang = (locale or "").lower()
        if lang.startswith("ru"):
            return self.title_ru or self.title_uk or self.title
        if lang.startswith("en"):
            return self.title_en or self.title_uk or self.title
        return self.title_uk or self.title


class CategoryNavigationItem(UUIDPrimaryKeyMixin, TimestampedMixin, PublishableMixin):
    group = models.ForeignKey(
        "catalog.CategoryNavigationGroup",
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name=_("Группа"),
    )
    category = models.ForeignKey(
        "catalog.Category",
        on_delete=models.PROTECT,
        related_name="navigation_items",
        verbose_name=_("Категория"),
    )
    title_override = models.CharField(_("Переопределение названия"), max_length=180, blank=True, default="")
    title_override_uk = models.CharField(_("Переопределение названия (UA)"), max_length=180, blank=True, default="")
    title_override_ru = models.CharField(_("Переопределение названия (RU)"), max_length=180, blank=True, default="")
    title_override_en = models.CharField(_("Переопределение названия (EN)"), max_length=180, blank=True, default="")
    sort_order = models.PositiveIntegerField(_("Порядок сортировки"), default=1000, db_index=True)

    class Meta:
        ordering = ("sort_order", "id")
        constraints = (
            models.UniqueConstraint(fields=("group", "category"), name="uniq_catalog_nav_item_group_category"),
        )
        verbose_name = _("Пункт навигации")
        verbose_name_plural = _("Пункты навигации")

    def __str__(self) -> str:
        return self.title_override or str(self.category)

    def get_localized_title(self, locale: str | None) -> str:
        lang = (locale or "").lower()
        if lang.startswith("ru"):
            return self.title_override_ru or self.title_override_uk or self.title_override
        if lang.startswith("en"):
            return self.title_override_en or self.title_override_uk or self.title_override
        return self.title_override_uk or self.title_override
