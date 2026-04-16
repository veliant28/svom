from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class SupplierRawOffer(UUIDPrimaryKeyMixin, TimestampedMixin):
    MATCH_STATUS_UNMATCHED = "unmatched"
    MATCH_STATUS_AUTO_MATCHED = "auto_matched"
    MATCH_STATUS_MANUAL_REQUIRED = "manual_match_required"
    MATCH_STATUS_MANUALLY_MATCHED = "manually_matched"
    MATCH_STATUS_IGNORED = "ignored"

    MATCH_STATUS_CHOICES = (
        (MATCH_STATUS_UNMATCHED, _("Не сопоставлен")),
        (MATCH_STATUS_AUTO_MATCHED, _("Сопоставлен автоматически")),
        (MATCH_STATUS_MANUAL_REQUIRED, _("Требуется ручное сопоставление")),
        (MATCH_STATUS_MANUALLY_MATCHED, _("Сопоставлен вручную")),
        (MATCH_STATUS_IGNORED, _("Игнорирован")),
    )

    MATCH_REASON_BRAND_CONFLICT = "brand_conflict"
    MATCH_REASON_ARTICLE_CONFLICT = "article_conflict"
    MATCH_REASON_AMBIGUOUS = "ambiguous_match"
    MATCH_REASON_MISSING_BRAND = "missing_brand"
    MATCH_REASON_MISSING_ARTICLE = "missing_article"

    MATCH_REASON_CHOICES = (
        (MATCH_REASON_BRAND_CONFLICT, _("Конфликт бренда")),
        (MATCH_REASON_ARTICLE_CONFLICT, _("Конфликт артикула")),
        (MATCH_REASON_AMBIGUOUS, _("Неоднозначное совпадение")),
        (MATCH_REASON_MISSING_BRAND, _("Не указан бренд")),
        (MATCH_REASON_MISSING_ARTICLE, _("Не указан артикул")),
    )

    CATEGORY_MAPPING_STATUS_UNMAPPED = "unmapped"
    CATEGORY_MAPPING_STATUS_AUTO_MAPPED = "auto_mapped"
    CATEGORY_MAPPING_STATUS_MANUAL_MAPPED = "manual_mapped"
    CATEGORY_MAPPING_STATUS_NEEDS_REVIEW = "needs_review"

    CATEGORY_MAPPING_STATUS_CHOICES = (
        (CATEGORY_MAPPING_STATUS_UNMAPPED, _("Не сопоставлен")),
        (CATEGORY_MAPPING_STATUS_AUTO_MAPPED, _("Сопоставлен автоматически")),
        (CATEGORY_MAPPING_STATUS_MANUAL_MAPPED, _("Сопоставлен вручную")),
        (CATEGORY_MAPPING_STATUS_NEEDS_REVIEW, _("Требуется проверка")),
    )

    CATEGORY_MAPPING_REASON_MANUAL = "manual"
    CATEGORY_MAPPING_REASON_FROM_PRODUCT = "from_product"
    CATEGORY_MAPPING_REASON_SUPPLIER_CATEGORY_EXACT = "supplier_category_exact"
    CATEGORY_MAPPING_REASON_SUPPLIER_CATEGORY_FUZZY = "supplier_category_fuzzy"
    CATEGORY_MAPPING_REASON_NAME_TOKENS = "name_tokens"
    CATEGORY_MAPPING_REASON_AMBIGUOUS_CATEGORY_SIGNAL = "ambiguous_category_signal"
    CATEGORY_MAPPING_REASON_AMBIGUOUS_NAME_SIGNAL = "ambiguous_name_signal"
    CATEGORY_MAPPING_REASON_NO_CATEGORY_SIGNAL = "no_category_signal"
    CATEGORY_MAPPING_REASON_LOW_CONFIDENCE = "low_confidence"
    CATEGORY_MAPPING_REASON_UNSET = "unset"
    CATEGORY_MAPPING_REASON_FORCE_SIGNAL_LEARNING = "force_signal_learning"
    CATEGORY_MAPPING_REASON_FORCE_TITLE_SIGNATURE = "force_title_signature"
    CATEGORY_MAPPING_REASON_FORCE_BRAND_CLUSTER = "force_brand_cluster"
    CATEGORY_MAPPING_REASON_FORCE_TOKEN_CLUSTER = "force_token_cluster"
    CATEGORY_MAPPING_REASON_FORCE_RELAXED_NAME = "force_relaxed_name"
    CATEGORY_MAPPING_REASON_FORCE_SUPPLIER_DEFAULT = "force_supplier_default"
    CATEGORY_MAPPING_REASON_FORCE_GLOBAL_DEFAULT = "force_global_default"
    CATEGORY_MAPPING_REASON_FORCE_GUARDRAIL_REMAP = "force_guardrail_remap"
    CATEGORY_MAPPING_REASON_FORCE_GUARDRAIL_REVIEW = "force_guardrail_review"

    CATEGORY_MAPPING_REASON_CHOICES = (
        (CATEGORY_MAPPING_REASON_MANUAL, _("Ручной выбор")),
        (CATEGORY_MAPPING_REASON_FROM_PRODUCT, _("Из связанного товара")),
        (CATEGORY_MAPPING_REASON_SUPPLIER_CATEGORY_EXACT, _("Точное совпадение категории поставщика")),
        (CATEGORY_MAPPING_REASON_SUPPLIER_CATEGORY_FUZZY, _("Похожая категория поставщика")),
        (CATEGORY_MAPPING_REASON_NAME_TOKENS, _("Совпадение по названию товара")),
        (CATEGORY_MAPPING_REASON_AMBIGUOUS_CATEGORY_SIGNAL, _("Неоднозначный сигнал категории поставщика")),
        (CATEGORY_MAPPING_REASON_AMBIGUOUS_NAME_SIGNAL, _("Неоднозначный сигнал по названию")),
        (CATEGORY_MAPPING_REASON_NO_CATEGORY_SIGNAL, _("Нет сигнала категории")),
        (CATEGORY_MAPPING_REASON_LOW_CONFIDENCE, _("Низкая уверенность")),
        (CATEGORY_MAPPING_REASON_UNSET, _("Сопоставление снято")),
        (CATEGORY_MAPPING_REASON_FORCE_SIGNAL_LEARNING, _("Принудительно из накопленных сигналов категории")),
        (CATEGORY_MAPPING_REASON_FORCE_TITLE_SIGNATURE, _("Принудительно по сигнатуре названия")),
        (CATEGORY_MAPPING_REASON_FORCE_BRAND_CLUSTER, _("Принудительно по брендовому кластеру")),
        (CATEGORY_MAPPING_REASON_FORCE_TOKEN_CLUSTER, _("Принудительно по токенам названия")),
        (CATEGORY_MAPPING_REASON_FORCE_RELAXED_NAME, _("Принудительно по ослабленному совпадению названия")),
        (CATEGORY_MAPPING_REASON_FORCE_SUPPLIER_DEFAULT, _("Принудительно по категории поставщика по умолчанию")),
        (CATEGORY_MAPPING_REASON_FORCE_GLOBAL_DEFAULT, _("Принудительно по глобальной категории по умолчанию")),
        (CATEGORY_MAPPING_REASON_FORCE_GUARDRAIL_REMAP, _("Переназначено guardrail-правилом")),
        (CATEGORY_MAPPING_REASON_FORCE_GUARDRAIL_REVIEW, _("Оставлено на проверку guardrail-правилом")),
    )

    run = models.ForeignKey(
        "supplier_imports.ImportRun",
        on_delete=models.CASCADE,
        related_name="raw_offers",
        verbose_name=_("Запуск"),
    )
    source = models.ForeignKey(
        "supplier_imports.ImportSource",
        on_delete=models.CASCADE,
        related_name="raw_offers",
        verbose_name=_("Источник"),
    )
    supplier = models.ForeignKey(
        "pricing.Supplier",
        on_delete=models.CASCADE,
        related_name="raw_offers",
        verbose_name=_("Поставщик"),
    )
    artifact = models.ForeignKey(
        "supplier_imports.ImportArtifact",
        on_delete=models.SET_NULL,
        related_name="raw_offers",
        blank=True,
        null=True,
        verbose_name=_("Артефакт"),
    )

    row_number = models.PositiveIntegerField(_("Номер строки"), blank=True, null=True)
    external_sku = models.CharField(_("Внешний SKU"), max_length=128)
    article = models.CharField(_("Артикул"), max_length=128, blank=True)
    normalized_article = models.CharField(_("Нормализованный артикул"), max_length=128, db_index=True)
    brand_name = models.CharField(_("Бренд"), max_length=180, blank=True)
    normalized_brand = models.CharField(_("Нормализованный бренд"), max_length=180, blank=True, db_index=True)
    product_name = models.CharField(_("Название товара"), max_length=255, blank=True)

    currency = models.CharField(_("Валюта"), max_length=3, default="UAH")
    price = models.DecimalField(_("Цена"), max_digits=12, decimal_places=2, blank=True, null=True)
    stock_qty = models.IntegerField(_("Остаток"), default=0)
    lead_time_days = models.PositiveSmallIntegerField(_("Срок поставки (дней)"), default=0)

    matched_product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.SET_NULL,
        related_name="raw_supplier_offers",
        blank=True,
        null=True,
        verbose_name=_("Сопоставленный товар"),
    )
    mapped_category = models.ForeignKey(
        "catalog.Category",
        on_delete=models.SET_NULL,
        related_name="raw_offer_category_mappings",
        blank=True,
        null=True,
        verbose_name=_("Сопоставленная категория"),
    )
    category_mapping_status = models.CharField(
        _("Статус сопоставления категории"),
        max_length=24,
        choices=CATEGORY_MAPPING_STATUS_CHOICES,
        default=CATEGORY_MAPPING_STATUS_UNMAPPED,
        db_index=True,
    )
    category_mapping_reason = models.CharField(
        _("Причина сопоставления категории"),
        max_length=64,
        choices=CATEGORY_MAPPING_REASON_CHOICES,
        blank=True,
        default="",
        db_index=True,
    )
    category_mapping_confidence = models.DecimalField(
        _("Уверенность сопоставления категории"),
        max_digits=4,
        decimal_places=3,
        blank=True,
        null=True,
    )
    category_mapped_at = models.DateTimeField(_("Когда сопоставлена категория"), blank=True, null=True)
    category_mapped_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        related_name="category_mapped_raw_offers",
        blank=True,
        null=True,
        verbose_name=_("Кем сопоставлена категория"),
    )
    match_status = models.CharField(_("Статус сопоставления"), max_length=32, choices=MATCH_STATUS_CHOICES, default=MATCH_STATUS_UNMATCHED, db_index=True)
    match_reason = models.CharField(_("Причина сопоставления"), max_length=64, choices=MATCH_REASON_CHOICES, blank=True, db_index=True)
    match_candidate_product_ids = models.JSONField(_("Кандидаты сопоставления"), default=list, blank=True)
    matching_attempts = models.PositiveSmallIntegerField(_("Попытки сопоставления"), default=0)
    last_matched_at = models.DateTimeField(_("Последнее сопоставление"), blank=True, null=True)
    matched_manually_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        related_name="manually_matched_raw_offers",
        blank=True,
        null=True,
        verbose_name=_("Кем сопоставлено вручную"),
    )
    matched_manually_at = models.DateTimeField(_("Когда сопоставлено вручную"), blank=True, null=True)
    ignored_at = models.DateTimeField(_("Когда проигнорировано"), blank=True, null=True)
    article_normalization_trace = models.JSONField(_("Трейс нормализации артикула"), default=list, blank=True)
    brand_normalization_trace = models.JSONField(_("Трейс нормализации бренда"), default=list, blank=True)
    is_valid = models.BooleanField(_("Валиден"), default=True)
    skip_reason = models.CharField(_("Причина пропуска"), max_length=255, blank=True)
    raw_payload = models.JSONField(_("Сырой payload"), default=dict, blank=True)

    class Meta:
        ordering = ("source__code", "external_sku")
        verbose_name = _("Сырой оффер поставщика")
        verbose_name_plural = _("Сырые офферы поставщиков")

    def __str__(self) -> str:
        return f"{self.source.code}:{self.external_sku}"
