from __future__ import annotations

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.db.mixins import TimestampedMixin, UUIDPrimaryKeyMixin


class LoyaltyPromoCode(UUIDPrimaryKeyMixin, TimestampedMixin):
    DISCOUNT_DELIVERY_FEE = "delivery_fee"
    DISCOUNT_PRODUCT_MARKUP = "product_markup"
    DISCOUNT_TYPE_CHOICES = (
        (DISCOUNT_DELIVERY_FEE, _("Скидка на доставку")),
        (DISCOUNT_PRODUCT_MARKUP, _("Скидка на товарную наценку")),
    )

    STATUS_ACTIVE = "active"
    STATUS_DISABLED = "disabled"
    STATUS_CHOICES = (
        (STATUS_ACTIVE, _("Активен")),
        (STATUS_DISABLED, _("Отключен")),
    )

    code = models.CharField(_("Промокод"), max_length=64, unique=True)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="loyalty_promo_codes",
        verbose_name=_("Клиент"),
    )
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="issued_loyalty_promo_codes",
        verbose_name=_("Кто выдал"),
    )
    reason = models.CharField(_("Причина выдачи"), max_length=255)
    discount_type = models.CharField(_("Тип скидки"), max_length=32, choices=DISCOUNT_TYPE_CHOICES)
    discount_percent = models.DecimalField(
        _("Процент скидки"),
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    usage_limit = models.PositiveIntegerField(_("Лимит использований"), default=1)
    usage_count = models.PositiveIntegerField(_("Использований"), default=0)
    status = models.CharField(_("Статус"), max_length=16, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    expires_at = models.DateTimeField(_("Срок действия"), blank=True, null=True)
    last_redeemed_at = models.DateTimeField(_("Последнее применение"), blank=True, null=True)
    last_redeemed_order = models.ForeignKey(
        "commerce.Order",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="redeemed_loyalty_promo_codes",
        verbose_name=_("Заказ последнего применения"),
    )

    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("Лояльность: промокод")
        verbose_name_plural = _("Лояльность: промокоды")
        indexes = [
            models.Index(fields=("code",), name="commerce_loyalty_code_idx"),
            models.Index(fields=("customer", "status"), name="com_loyl_customer_status_idx"),
            models.Index(fields=("expires_at",), name="commerce_loyalty_expires_idx"),
        ]

    def __str__(self) -> str:
        return self.code


class LoyaltyPromoRedemption(UUIDPrimaryKeyMixin, TimestampedMixin):
    promo_code = models.ForeignKey(
        "commerce.LoyaltyPromoCode",
        on_delete=models.CASCADE,
        related_name="redemptions",
        verbose_name=_("Промокод"),
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="loyalty_promo_redemptions",
        verbose_name=_("Клиент"),
    )
    order = models.ForeignKey(
        "commerce.Order",
        on_delete=models.CASCADE,
        related_name="loyalty_redemptions",
        verbose_name=_("Заказ"),
    )
    requested_percent = models.DecimalField(_("Запрошенный процент"), max_digits=5, decimal_places=2, default=0)
    applied_percent = models.DecimalField(_("Фактический процент"), max_digits=5, decimal_places=2, default=0)
    delivery_discount = models.DecimalField(_("Скидка на доставку"), max_digits=12, decimal_places=2, default=0)
    product_discount = models.DecimalField(_("Скидка на товар"), max_digits=12, decimal_places=2, default=0)
    total_discount = models.DecimalField(_("Общая скидка"), max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(_("Валюта"), max_length=3, default="UAH")
    discount_payload = models.JSONField(_("Детали скидки"), default=dict, blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("Лояльность: применение промокода")
        verbose_name_plural = _("Лояльность: применения промокодов")
        constraints = [
            models.UniqueConstraint(fields=("promo_code", "order"), name="commerce_loyalty_redemption_order_unique"),
        ]

    def __str__(self) -> str:
        return f"{self.promo_code.code} -> {self.order.order_number}"


class LoyaltyPromoEvent(UUIDPrimaryKeyMixin, TimestampedMixin):
    EVENT_ISSUED = "issued"
    EVENT_REDEEMED = "redeemed"
    EVENT_DISABLED = "disabled"
    EVENT_CHOICES = (
        (EVENT_ISSUED, _("Выдача")),
        (EVENT_REDEEMED, _("Применение")),
        (EVENT_DISABLED, _("Отключение")),
    )

    promo_code = models.ForeignKey(
        "commerce.LoyaltyPromoCode",
        on_delete=models.CASCADE,
        related_name="events",
        verbose_name=_("Промокод"),
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="loyalty_promo_events",
        verbose_name=_("Пользователь"),
    )
    event_type = models.CharField(_("Событие"), max_length=32, choices=EVENT_CHOICES)
    payload = models.JSONField(_("Данные события"), default=dict, blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("Лояльность: событие промокода")
        verbose_name_plural = _("Лояльность: события промокода")

    def __str__(self) -> str:
        return f"{self.promo_code.code} [{self.event_type}]"
