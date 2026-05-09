from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import PublishableMixin, TimestampedMixin, UUIDPrimaryKeyMixin


class Product(UUIDPrimaryKeyMixin, TimestampedMixin, PublishableMixin):
    CATALOG_SOURCE_LEGACY = "legacy"
    CATALOG_SOURCE_AUTODB_PRO = "autodb_pro"
    CATALOG_SOURCE_CHOICES = (
        (CATALOG_SOURCE_LEGACY, _("Legacy")),
        (CATALOG_SOURCE_AUTODB_PRO, _("Auto_DB_Pro")),
    )
    NAME_SOURCE_AUTODB_PRO = "autodb_pro"
    NAME_SOURCE_SUPPLIER_FALLBACK = "supplier_fallback"
    NAME_SOURCE_MANUAL = "manual"
    NAME_SOURCE_CHOICES = (
        (NAME_SOURCE_AUTODB_PRO, _("Auto_DB_Pro")),
        (NAME_SOURCE_SUPPLIER_FALLBACK, _("Supplier fallback")),
        (NAME_SOURCE_MANUAL, _("Manual")),
    )
    NAME_TRANSLATION_PENDING = "pending"
    NAME_TRANSLATION_TRANSLATED = "translated"
    NAME_TRANSLATION_FAILED = "failed"
    NAME_TRANSLATION_MANUAL_LOCKED = "manual_locked"
    NAME_TRANSLATION_STATUS_CHOICES = (
        (NAME_TRANSLATION_PENDING, _("Pending")),
        (NAME_TRANSLATION_TRANSLATED, _("Translated")),
        (NAME_TRANSLATION_FAILED, _("Failed")),
        (NAME_TRANSLATION_MANUAL_LOCKED, _("Manual locked")),
    )
    BRAND_SOURCE_AUTODB_PRO = "autodb_pro"
    BRAND_SOURCE_MANUAL = "manual"
    BRAND_SOURCE_SUPPLIER_FALLBACK = "supplier_fallback"
    BRAND_SOURCE_UNKNOWN = "unknown"
    BRAND_SOURCE_CHOICES = (
        (BRAND_SOURCE_AUTODB_PRO, _("Auto_DB_Pro")),
        (BRAND_SOURCE_MANUAL, _("Manual")),
        (BRAND_SOURCE_SUPPLIER_FALLBACK, _("Supplier fallback")),
        (BRAND_SOURCE_UNKNOWN, _("Unknown")),
    )

    sku = models.CharField(_("SKU"), max_length=64, unique=True)
    article = models.CharField(_("Артикул"), max_length=128, blank=True)
    autodb_article_id = models.BigIntegerField(_("Auto_DB_Pro article ID"), blank=True, null=True, db_index=True)
    autodb_supplier_id = models.BigIntegerField(_("Auto_DB_Pro supplier ID"), blank=True, null=True, db_index=True)
    autodb_article_number = models.CharField(_("Auto_DB_Pro article number"), max_length=128, blank=True, default="", db_index=True)
    autodb_article_key = models.CharField(_("Auto_DB_Pro article key"), max_length=196, blank=True, default="", db_index=True)
    autodb_supplier_name = models.CharField(_("Auto_DB_Pro supplier name"), max_length=255, blank=True, default="", db_index=True)
    normalized_brand = models.CharField(_("Нормализованный бренд"), max_length=180, blank=True, default="", db_index=True)
    normalized_article = models.CharField(_("Нормализованный артикул"), max_length=128, blank=True, default="", db_index=True)
    display_brand_name = models.CharField(_("Отображаемый бренд"), max_length=255, blank=True, default="", db_index=True)
    brand_source = models.CharField(
        _("Источник бренда"),
        max_length=32,
        choices=BRAND_SOURCE_CHOICES,
        blank=True,
        default="",
        db_index=True,
    )
    brand_source_hash = models.CharField(_("Хеш источника бренда"), max_length=64, blank=True, default="", db_index=True)
    brand_manually_locked = models.BooleanField(_("Бренд закреплен вручную"), default=False, db_index=True)
    catalog_source = models.CharField(
        _("Источник каталога"),
        max_length=24,
        choices=CATALOG_SOURCE_CHOICES,
        blank=True,
        default="",
        db_index=True,
    )
    utr_detail_id = models.CharField(_("UTR detail ID"), max_length=64, blank=True, db_index=True)
    name = models.CharField(_("Название"), max_length=255)
    name_uk = models.CharField(_("Название (UA)"), max_length=255, blank=True, default="")
    name_ru = models.CharField(_("Название (RU)"), max_length=255, blank=True, default="")
    name_en = models.CharField(_("Название (EN)"), max_length=255, blank=True, default="")
    name_source = models.CharField(
        _("Источник названия"),
        max_length=32,
        choices=NAME_SOURCE_CHOICES,
        blank=True,
        default="",
        db_index=True,
    )
    name_source_text = models.CharField(_("Исходный текст названия"), max_length=255, blank=True, default="")
    name_source_hash = models.CharField(_("Хеш исходного названия"), max_length=64, blank=True, default="", db_index=True)
    name_translation_status = models.CharField(
        _("Статус перевода названия"),
        max_length=24,
        choices=NAME_TRANSLATION_STATUS_CHOICES,
        blank=True,
        default="",
        db_index=True,
    )
    name_translation_error = models.CharField(_("Ошибка перевода названия"), max_length=255, blank=True, default="")
    name_manually_locked = models.BooleanField(_("Название закреплено вручную"), default=False, db_index=True)
    slug = models.SlugField(_("Slug"), max_length=300, unique=True)
    brand = models.ForeignKey(
        "catalog.Brand",
        on_delete=models.PROTECT,
        related_name="products",
        verbose_name=_("Бренд"),
    )
    category = models.ForeignKey(
        "catalog.Category",
        on_delete=models.PROTECT,
        related_name="products",
        verbose_name=_("Категория"),
        blank=True,
        null=True,
    )
    category_manually_locked = models.BooleanField(_("Категория закреплена вручную"), default=False)
    short_description = models.TextField(_("Короткое описание"), blank=True)
    description = models.TextField(_("Описание"), blank=True)
    is_featured = models.BooleanField(_("Рекомендуемый"), default=False)
    is_new = models.BooleanField(_("Новинка"), default=False)
    is_bestseller = models.BooleanField(_("Хит продаж"), default=False)
    available_stock_qty_cached = models.IntegerField(_("Кэш доступного остатка"), default=0, db_index=True)

    class Meta:
        ordering = ("name",)
        verbose_name = _("Товар")
        verbose_name_plural = _("Товары")
        indexes = [
            models.Index(fields=("brand", "category"), name="cat_prod_brand_cat_idx"),
            models.Index(fields=("is_active", "is_featured"), name="catalog_product_featured_idx"),
        ]

    def __str__(self) -> str:
        return self.name

    def get_localized_name(self, locale: str | None) -> str:
        lang = (locale or "").lower()
        if lang.startswith("ru"):
            return self.name_ru or self.name_uk or self.name
        if lang.startswith("en"):
            return self.name_en or self.name_uk or self.name
        return self.name_uk or self.name
