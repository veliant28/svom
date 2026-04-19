from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable

from .errors import NovaPoshtaBusinessRuleError


@dataclass(frozen=True)
class PaymentRuleResolution:
    payer_type: str
    payment_method: str
    afterpayment_amount: Decimal | None


def resolve_payment_rule(
    *,
    sender_type: str,
    requested_afterpayment: Decimal | None,
    order_total: Decimal,
    requested_payer_type: str | None = None,
    requested_payment_method: str | None = None,
) -> PaymentRuleResolution:
    normalized_sender_type = resolve_effective_sender_type(sender_type=sender_type)
    payer_type = _resolve_payer_type(requested_payer_type)
    payment_method = _resolve_payment_method(normalized_sender_type, requested_payment_method)

    if payer_type == "ThirdPerson" and payment_method != "NonCash":
        raise NovaPoshtaBusinessRuleError(
            "Для платника типу 'Третя особа' доступний лише безготівковий розрахунок (NonCash).",
        )

    if normalized_sender_type == "private_person":
        # Для физлица допускаем обычную логику наложенного платежа.
        amount = requested_afterpayment if requested_afterpayment is not None else order_total
        if amount <= 0:
            amount = None
        return PaymentRuleResolution(
            payer_type=payer_type,
            payment_method=payment_method,
            afterpayment_amount=amount,
        )

    if normalized_sender_type in {"fop", "business"}:
        if requested_afterpayment is None or requested_afterpayment <= 0:
            raise NovaPoshtaBusinessRuleError(
                "Для отправителя типа ФОП/Организация требуется сумма контроля оплаты больше 0.",
            )
        return PaymentRuleResolution(
            payer_type=payer_type,
            payment_method=payment_method,
            afterpayment_amount=requested_afterpayment,
        )

    raise NovaPoshtaBusinessRuleError("Неизвестный тип отправителя Новой Почты.")


def validate_sender_capabilities(*, sender_type: str, options: dict[str, Any]) -> None:
    normalized_sender_type = resolve_effective_sender_type(sender_type=sender_type)
    if normalized_sender_type not in {"fop", "business"}:
        return

    can_control_payment = bool(options.get("CanAfterpaymentOnGoodsCost"))
    if not can_control_payment:
        raise NovaPoshtaBusinessRuleError(
            "Для выбранного отправителя не подключена услуга 'Контроль оплаты' в Новой Почте.",
        )

def _resolve_payer_type(requested_payer_type: str | None) -> str:
    normalized_requested = (requested_payer_type or "").strip()
    if not normalized_requested:
        return "Recipient"
    if normalized_requested in {"Sender", "Recipient", "ThirdPerson"}:
        return normalized_requested
    raise NovaPoshtaBusinessRuleError("Недопустимый тип плательщика. Разрешено: Sender, Recipient, ThirdPerson.")


def _resolve_payment_method(normalized_sender_type: str, requested_payment_method: str | None) -> str:
    normalized_requested = (requested_payment_method or "").strip()
    if not normalized_requested:
        return "Cash"
    if normalized_requested in {"Cash", "NonCash"}:
        return normalized_requested
    raise NovaPoshtaBusinessRuleError("Недопустимый метод оплаты. Разрешено: Cash, NonCash.")


def resolve_effective_sender_type(*, sender_type: str, hints: Iterable[str] | None = None) -> str:
    normalized_candidates: list[str] = []
    normalized_candidates.append(_normalize_sender_type(sender_type))
    for value in hints or ():
        normalized_candidates.append(_normalize_sender_type(value))

    for normalized in normalized_candidates:
        if normalized in {"fop", "business"}:
            return normalized
    for normalized in normalized_candidates:
        if normalized == "private_person":
            return normalized
    return normalized_candidates[0] if normalized_candidates else ""


def _normalize_sender_type(value: str) -> str:
    normalized = (value or "").strip().lower()
    if not normalized:
        return ""

    if normalized in {"organization", "org", "company"}:
        return "business"
    if normalized in {"privateperson", "private_person", "privatperson", "physicalperson"}:
        return "private_person"

    compact = "".join(ch for ch in normalized if ch.isalnum())
    if compact in {"privateperson", "privatperson", "physicalperson"}:
        return "private_person"
    if compact in {"business", "organization", "company", "legalentity", "org"}:
        return "business"

    if "фоп" in normalized or "флп" in normalized or "fop" in compact:
        return "fop"
    if "organization" in compact or "company" in compact or "business" in compact or "legalentity" in compact:
        return "business"
    if "privateperson" in compact or "privatperson" in compact:
        return "private_person"

    return normalized
