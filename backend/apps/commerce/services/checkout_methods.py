from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from apps.commerce.models import CheckoutMethodSettings, Order


@dataclass(frozen=True)
class CheckoutMethodsPayload:
    delivery_methods: list[str]
    payment_methods: list[str]


DELIVERY_METHOD_FLAGS: tuple[tuple[str, str], ...] = (
    (Order.DELIVERY_PICKUP, "pickup_enabled"),
    (Order.DELIVERY_NOVA_POSHTA, "nova_poshta_enabled"),
    (Order.DELIVERY_COURIER, "courier_enabled"),
)
PAYMENT_METHOD_FLAGS: tuple[tuple[str, str], ...] = (
    (Order.PAYMENT_CASH_ON_DELIVERY, "cash_on_delivery_enabled"),
    (Order.PAYMENT_MONOBANK, "monobank_enabled"),
    (Order.PAYMENT_NOVAPAY, "novapay_enabled"),
    (Order.PAYMENT_LIQPAY, "liqpay_enabled"),
)


def get_checkout_method_settings() -> CheckoutMethodSettings:
    settings, _ = CheckoutMethodSettings.objects.get_or_create(code=CheckoutMethodSettings.DEFAULT_CODE)
    return settings


def serialize_checkout_methods(*, settings: CheckoutMethodSettings | None = None) -> CheckoutMethodsPayload:
    settings = settings or get_checkout_method_settings()
    return CheckoutMethodsPayload(
        delivery_methods=[method for method, field in DELIVERY_METHOD_FLAGS if bool(getattr(settings, field))],
        payment_methods=[method for method, field in PAYMENT_METHOD_FLAGS if bool(getattr(settings, field))],
    )


def validate_checkout_method_availability(*, delivery_method: str, payment_method: str) -> None:
    payload = serialize_checkout_methods()
    errors: dict[str, str] = {}
    if delivery_method not in payload.delivery_methods:
        errors["delivery_method"] = _("Selected delivery method is disabled.")
    if payment_method not in payload.payment_methods:
        errors["payment_method"] = _("Selected payment method is disabled.")
    if errors:
        raise ValidationError(errors)


def validate_checkout_delivery_method_availability(*, delivery_method: str) -> None:
    payload = serialize_checkout_methods()
    if delivery_method not in payload.delivery_methods:
        raise ValidationError({"delivery_method": _("Selected delivery method is disabled.")})
