from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class CheckoutMethodSettings(UUIDPrimaryKeyMixin, TimestampedMixin):
    DEFAULT_CODE = "default"

    code = models.CharField(_("Код профиля"), max_length=32, unique=True, default=DEFAULT_CODE)

    pickup_enabled = models.BooleanField(_("Самовывоз включен"), default=True)
    nova_poshta_enabled = models.BooleanField(_("Новая Почта включена"), default=True)
    courier_enabled = models.BooleanField(_("Курьер включен"), default=True)

    cash_on_delivery_enabled = models.BooleanField(_("Наложенный платеж включен"), default=True)
    monobank_enabled = models.BooleanField(_("Monobank включен в checkout"), default=True)
    novapay_enabled = models.BooleanField(_("Nova Pay включен в checkout"), default=True)
    liqpay_enabled = models.BooleanField(_("LiqPay включен в checkout"), default=True)

    class Meta:
        verbose_name = _("Настройки способов оформления заказа")
        verbose_name_plural = _("Настройки способов оформления заказа")

    def __str__(self) -> str:
        return f"CheckoutMethodSettings:{self.code}"
