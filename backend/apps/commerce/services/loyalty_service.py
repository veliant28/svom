from __future__ import annotations

import secrets
import string
from dataclasses import dataclass
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.commerce.models import LoyaltyPromoCode, LoyaltyPromoEvent, LoyaltyPromoRedemption
from apps.commerce.services.cart_calculations import get_line_total, quantize_money
from apps.commerce.services.sellable_state import get_cart_item_sellable_snapshot

CODE_ALPHABET = string.ascii_uppercase + string.digits
CODE_PREFIX = "SV"


class LoyaltyPromoValidationError(Exception):
    def __init__(self, *, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class LoyaltyDiscountComputation:
    promo: LoyaltyPromoCode
    discount_type: str
    requested_percent: Decimal
    applied_percent: Decimal
    subtotal_before_discount: Decimal
    delivery_fee_before_discount: Decimal
    total_before_discount: Decimal
    product_markup_total: Decimal
    requested_discount_amount: Decimal
    product_discount: Decimal
    delivery_discount: Decimal
    total_discount: Decimal
    total_after_discount: Decimal
    currency: str

    def to_payload(self) -> dict[str, object]:
        return {
            "code": self.promo.code,
            "discount_type": self.discount_type,
            "requested_percent": str(self.requested_percent),
            "applied_percent": str(self.applied_percent),
            "subtotal_before_discount": str(self.subtotal_before_discount),
            "delivery_fee_before_discount": str(self.delivery_fee_before_discount),
            "total_before_discount": str(self.total_before_discount),
            "product_markup_cap": {
                "available_markup_total": str(self.product_markup_total),
                "requested_discount_amount": str(self.requested_discount_amount),
                "applied_discount_amount": str(self.product_discount),
            },
            "delivery_discount": str(self.delivery_discount),
            "product_discount": str(self.product_discount),
            "total_discount": str(self.total_discount),
            "total_after_discount": str(self.total_after_discount),
            "currency": self.currency,
        }


def normalize_promo_code(value: str) -> str:
    normalized = "".join(ch for ch in str(value or "").upper() if ch.isalnum())
    return normalized[:64]


def generate_unique_promo_code(*, length: int = 8) -> str:
    safe_length = max(4, min(length, 24))
    for _ in range(30):
        suffix = "".join(secrets.choice(CODE_ALPHABET) for _ in range(safe_length))
        candidate = f"{CODE_PREFIX}{suffix}"
        if not LoyaltyPromoCode.objects.filter(code=candidate).exists():
            return candidate
    raise RuntimeError("Unable to generate unique promo code.")


@transaction.atomic
def issue_loyalty_promo(
    *,
    customer,
    issued_by,
    reason: str,
    discount_type: str,
    discount_percent: Decimal,
    expires_at,
    usage_limit: int = 1,
) -> LoyaltyPromoCode:
    normalized_reason = str(reason or "").strip()
    if not normalized_reason:
        raise ValidationError({"reason": "Reason is required."})

    safe_limit = max(int(usage_limit or 1), 1)
    safe_percent = Decimal(str(discount_percent or 0)).quantize(Decimal("0.01"))
    if safe_percent < Decimal("0") or safe_percent > Decimal("100"):
        raise ValidationError({"discount_percent": "Discount percent must be between 0 and 100."})

    if discount_type not in {
        LoyaltyPromoCode.DISCOUNT_DELIVERY_FEE,
        LoyaltyPromoCode.DISCOUNT_PRODUCT_MARKUP,
    }:
        raise ValidationError({"discount_type": "Unsupported discount type."})

    promo = LoyaltyPromoCode.objects.create(
        code=generate_unique_promo_code(),
        customer=customer,
        issued_by=issued_by,
        reason=normalized_reason,
        discount_type=discount_type,
        discount_percent=safe_percent,
        usage_limit=safe_limit,
        expires_at=expires_at,
    )
    LoyaltyPromoEvent.objects.create(
        promo_code=promo,
        actor=issued_by,
        event_type=LoyaltyPromoEvent.EVENT_ISSUED,
        payload={
            "reason": normalized_reason,
            "discount_type": discount_type,
            "discount_percent": str(safe_percent),
            "usage_limit": safe_limit,
            "expires_at": expires_at.isoformat() if expires_at else None,
        },
    )
    return promo


def compute_loyalty_discount_for_checkout(
    *,
    user,
    promo_code_value: str,
    items: list,
    delivery_fee: Decimal,
    currency: str,
) -> LoyaltyDiscountComputation:
    normalized_code = normalize_promo_code(promo_code_value)
    if not normalized_code:
        raise LoyaltyPromoValidationError(code="empty", message="Promo code is required.")

    promo = LoyaltyPromoCode.objects.select_related("customer", "issued_by").filter(code__iexact=normalized_code).first()
    if promo is None:
        raise LoyaltyPromoValidationError(code="not_found", message="Promo code not found.")

    _ensure_promo_is_applicable(promo=promo, user=user)

    subtotal_before_discount = quantize_money(sum((get_line_total(item) for item in items), Decimal("0.00")))
    delivery_before_discount = quantize_money(Decimal(delivery_fee or 0))
    total_before_discount = quantize_money(subtotal_before_discount + delivery_before_discount)

    requested_percent = Decimal(promo.discount_percent).quantize(Decimal("0.01"))
    product_markup_total = Decimal("0.00")
    requested_discount_amount = Decimal("0.00")
    product_discount = Decimal("0.00")
    delivery_discount = Decimal("0.00")

    if promo.discount_type == LoyaltyPromoCode.DISCOUNT_DELIVERY_FEE:
        if delivery_before_discount <= Decimal("0"):
            raise LoyaltyPromoValidationError(
                code="delivery_zero",
                message="Promo code cannot be applied because delivery fee is zero.",
            )
        requested_discount_amount = quantize_money(delivery_before_discount * requested_percent / Decimal("100"))
        delivery_discount = min(requested_discount_amount, delivery_before_discount)
        applied_percent = (delivery_discount / delivery_before_discount * Decimal("100")).quantize(Decimal("0.01"))
    else:
        product_markup_total = _calculate_product_markup_total(items)
        if product_markup_total <= Decimal("0"):
            raise LoyaltyPromoValidationError(
                code="no_markup",
                message="Promo code cannot be applied because there is no available markup discount.",
            )
        requested_discount_amount = quantize_money(product_markup_total * requested_percent / Decimal("100"))
        product_discount = min(requested_discount_amount, product_markup_total)
        applied_percent = (product_discount / product_markup_total * Decimal("100")).quantize(Decimal("0.01"))

    total_discount = quantize_money(product_discount + delivery_discount)
    total_after_discount = quantize_money(max(total_before_discount - total_discount, Decimal("0.00")))

    return LoyaltyDiscountComputation(
        promo=promo,
        discount_type=promo.discount_type,
        requested_percent=requested_percent,
        applied_percent=applied_percent,
        subtotal_before_discount=subtotal_before_discount,
        delivery_fee_before_discount=delivery_before_discount,
        total_before_discount=total_before_discount,
        product_markup_total=product_markup_total,
        requested_discount_amount=requested_discount_amount,
        product_discount=product_discount,
        delivery_discount=delivery_discount,
        total_discount=total_discount,
        total_after_discount=total_after_discount,
        currency=currency,
    )


@transaction.atomic
def register_promo_redemption(*, user, order, computation: LoyaltyDiscountComputation) -> LoyaltyPromoRedemption:
    promo = LoyaltyPromoCode.objects.select_for_update().get(id=computation.promo.id)
    _ensure_promo_is_applicable(promo=promo, user=user)

    now = timezone.now()
    promo.usage_count = int(promo.usage_count) + 1
    promo.last_redeemed_at = now
    promo.last_redeemed_order = order
    promo.save(update_fields=("usage_count", "last_redeemed_at", "last_redeemed_order", "updated_at"))

    redemption = LoyaltyPromoRedemption.objects.create(
        promo_code=promo,
        customer=user,
        order=order,
        requested_percent=computation.requested_percent,
        applied_percent=computation.applied_percent,
        delivery_discount=computation.delivery_discount,
        product_discount=computation.product_discount,
        total_discount=computation.total_discount,
        currency=computation.currency,
        discount_payload=computation.to_payload(),
    )
    LoyaltyPromoEvent.objects.create(
        promo_code=promo,
        actor=user,
        event_type=LoyaltyPromoEvent.EVENT_REDEEMED,
        payload={
            "order_id": str(order.id),
            "order_number": order.order_number,
            **computation.to_payload(),
        },
    )
    return redemption


def serialize_loyalty_promo_status(*, promo: LoyaltyPromoCode, now=None) -> dict[str, object]:
    active_now = now or timezone.now()
    is_expired = bool(promo.expires_at and promo.expires_at <= active_now)
    is_used_up = int(promo.usage_count) >= int(promo.usage_limit)

    if promo.status == LoyaltyPromoCode.STATUS_DISABLED:
        state = "disabled"
    elif is_expired:
        state = "expired"
    elif is_used_up:
        state = "used"
    else:
        state = "active"

    return {
        "state": state,
        "is_expired": is_expired,
        "is_used": bool(int(promo.usage_count) > 0),
        "is_used_up": is_used_up,
        "is_active": state == "active",
    }


def serialize_loyalty_promo_for_ui(*, promo: LoyaltyPromoCode, now=None) -> dict[str, object]:
    status = serialize_loyalty_promo_status(promo=promo, now=now)
    return {
        "id": str(promo.id),
        "code": promo.code,
        "discount_type": promo.discount_type,
        "discount_percent": str(Decimal(promo.discount_percent).quantize(Decimal("0.01"))),
        "usage_limit": int(promo.usage_limit),
        "usage_count": int(promo.usage_count),
        "reason": promo.reason,
        "status": promo.status,
        "expires_at": promo.expires_at,
        "issued_at": promo.created_at,
        "issued_by": {
            "id": str(promo.issued_by_id) if promo.issued_by_id else None,
            "email": promo.issued_by.email if promo.issued_by_id else "",
            "name": promo.issued_by.get_full_name().strip() if promo.issued_by_id else "",
        },
        "customer": {
            "id": str(promo.customer_id),
            "email": promo.customer.email,
            "name": promo.customer.get_full_name().strip(),
        },
        "last_redeemed_at": promo.last_redeemed_at,
        "last_redeemed_order_id": str(promo.last_redeemed_order_id) if promo.last_redeemed_order_id else None,
        **status,
    }


def _ensure_promo_is_applicable(*, promo: LoyaltyPromoCode, user) -> None:
    if promo.customer_id != user.id:
        raise LoyaltyPromoValidationError(code="not_owned", message="Promo code does not belong to this user.")

    if promo.status != LoyaltyPromoCode.STATUS_ACTIVE:
        raise LoyaltyPromoValidationError(code="disabled", message="Promo code is disabled.")

    if promo.expires_at and promo.expires_at <= timezone.now():
        raise LoyaltyPromoValidationError(code="expired", message="Promo code is expired.")

    if int(promo.usage_count) >= int(promo.usage_limit):
        raise LoyaltyPromoValidationError(code="used", message="Promo code has reached usage limit.")


def _calculate_product_markup_total(items: list) -> Decimal:
    total = Decimal("0.00")
    for item in items:
        snapshot = get_cart_item_sellable_snapshot(item)
        unit_price = quantize_money(Decimal(snapshot.current_sell_price))
        safe_floor = _resolve_safe_floor_unit_price(item=item, snapshot=snapshot, unit_price=unit_price)
        markup_unit = quantize_money(max(unit_price - safe_floor, Decimal("0.00")))
        line_markup = quantize_money(markup_unit * Decimal(max(int(item.quantity), 0)))
        total = quantize_money(total + line_markup)
    return total


def _resolve_safe_floor_unit_price(*, item, snapshot, unit_price: Decimal) -> Decimal:
    product_price = getattr(item.product, "product_price", None)
    landed_cost = Decimal(str(getattr(product_price, "landed_cost", 0) or 0))
    if landed_cost > Decimal("0"):
        return min(quantize_money(landed_cost), unit_price)

    selected_offer_id = str(getattr(snapshot, "selected_offer_id", "") or "").strip()
    if selected_offer_id:
        for offer in getattr(item.product, "supplier_offers", []).all() if hasattr(getattr(item.product, "supplier_offers", None), "all") else []:
            if str(offer.id) != selected_offer_id:
                continue
            candidate = Decimal(offer.purchase_price) + Decimal(offer.logistics_cost) + Decimal(offer.extra_cost)
            if candidate > Decimal("0"):
                return min(quantize_money(candidate), unit_price)

    return unit_price
