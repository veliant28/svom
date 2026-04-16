from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class PricingRule(UUIDPrimaryKeyMixin, TimestampedMixin):
    policy = models.ForeignKey(
        "pricing.PricingPolicy",
        on_delete=models.CASCADE,
        related_name="rules",
        verbose_name=_("Политика"),
    )
    priority = models.PositiveIntegerField(_("Приоритет"), default=100)
    cost_from = models.DecimalField(_("Себестоимость от"), max_digits=12, decimal_places=2, blank=True, null=True)
    cost_to = models.DecimalField(_("Себестоимость до"), max_digits=12, decimal_places=2, blank=True, null=True)
    percent_markup = models.DecimalField(_("Процент наценки"), max_digits=7, decimal_places=2, default=0)
    fixed_markup = models.DecimalField(_("Фиксированная наценка"), max_digits=12, decimal_places=2, default=0)

    class Meta:
        ordering = ("policy", "priority", "cost_from")
        verbose_name = _("Правило ценообразования")
        verbose_name_plural = _("Правила ценообразования")

    def __str__(self) -> str:
        return f"{self.policy} / правило #{self.priority}"
