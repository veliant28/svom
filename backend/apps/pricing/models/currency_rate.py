from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class CurrencyRate(UUIDPrimaryKeyMixin, TimestampedMixin):
    base_currency = models.CharField(_("Базовая валюта"), max_length=3)
    quote_currency = models.CharField(_("Котируемая валюта"), max_length=3)
    rate = models.DecimalField(_("Курс"), max_digits=14, decimal_places=6)
    effective_at = models.DateTimeField(_("Действует с"))
    source = models.CharField(_("Источник"), max_length=64, blank=True)

    class Meta:
        ordering = ("-effective_at",)
        verbose_name = _("Курс валюты")
        verbose_name_plural = _("Курсы валют")
        constraints = [
            models.UniqueConstraint(
                fields=("base_currency", "quote_currency", "effective_at"),
                name="pricing_currencyrate_unique_pair_moment",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.base_currency}/{self.quote_currency} {self.rate}"
