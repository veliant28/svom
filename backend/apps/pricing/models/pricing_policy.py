from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import PublishableMixin, TimestampedMixin, UUIDPrimaryKeyMixin


class PricingPolicy(UUIDPrimaryKeyMixin, TimestampedMixin, PublishableMixin):
    SCOPE_GLOBAL = "global"
    SCOPE_SUPPLIER = "supplier"
    SCOPE_BRAND = "brand"
    SCOPE_CATEGORY = "category"
    SCOPE_BRAND_CATEGORY = "brand_category"

    SCOPE_CHOICES = (
        (SCOPE_GLOBAL, _("Глобально")),
        (SCOPE_SUPPLIER, _("Поставщик")),
        (SCOPE_BRAND, _("Бренд")),
        (SCOPE_CATEGORY, _("Категория")),
        (SCOPE_BRAND_CATEGORY, _("Бренд + категория")),
    )

    name = models.CharField(_("Название"), max_length=180, unique=True)
    scope = models.CharField(_("Область действия"), max_length=32, choices=SCOPE_CHOICES, default=SCOPE_GLOBAL)
    priority = models.PositiveIntegerField(_("Приоритет"), default=100)

    supplier = models.ForeignKey(
        "pricing.Supplier",
        on_delete=models.PROTECT,
        related_name="pricing_policies",
        blank=True,
        null=True,
        verbose_name=_("Поставщик"),
    )
    brand = models.ForeignKey(
        "catalog.Brand",
        on_delete=models.PROTECT,
        related_name="pricing_policies",
        blank=True,
        null=True,
        verbose_name=_("Бренд"),
    )
    category = models.ForeignKey(
        "catalog.Category",
        on_delete=models.PROTECT,
        related_name="pricing_policies",
        blank=True,
        null=True,
        verbose_name=_("Категория"),
    )

    percent_markup = models.DecimalField(_("Процент наценки"), max_digits=7, decimal_places=2, default=0)
    fixed_markup = models.DecimalField(_("Фиксированная наценка"), max_digits=12, decimal_places=2, default=0)
    min_margin_percent = models.DecimalField(_("Минимальная маржа, %"), max_digits=6, decimal_places=2, default=0)
    min_price = models.DecimalField(_("Минимальная цена"), max_digits=12, decimal_places=2, blank=True, null=True)
    rounding_step = models.DecimalField(_("Шаг округления"), max_digits=7, decimal_places=2, default=1)
    psychological_rounding = models.BooleanField(_("Психологическое округление"), default=False)
    lock_auto_recalc = models.BooleanField(_("Запретить авто-перерасчет"), default=False)

    class Meta:
        ordering = ("priority", "name")
        verbose_name = _("Политика ценообразования")
        verbose_name_plural = _("Политики ценообразования")

    def __str__(self) -> str:
        return self.name
