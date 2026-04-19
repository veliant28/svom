from __future__ import annotations

from typing import Any

from .errors import NovaPoshtaBusinessRuleError, NovaPoshtaErrorContext, NovaPoshtaIntegrationError, format_context_message
from .normalizers import extract_error_context

_KNOWN_RULE_MESSAGES = (
    (
        ("контроль", "оплат"),
        "Для выбранного отправителя недоступна услуга 'Контроль оплаты'.",
    ),
    (
        ("api", "ключ"),
        "Невалидный API токен Новой Почты для выбранного отправителя.",
    ),
    (
        ("recipientaddress",),
        "Не удалось определить адрес/отделение получателя. Проверьте выбранный город и отделение.",
    ),
    (
        ("cityrecipient",),
        "Не удалось определить город получателя. Выберите город заново через онлайн-справочник.",
    ),
    (
        ("contactrecipient",),
        "Не удалось определить контакт получателя. Проверьте ФИО и телефон получателя.",
    ),
    (
        ("contactsender",),
        "Некорректные данные контактного лица отправителя. Проверьте профиль отправителя.",
    ),
    (
        ("already", "deleted"),
        "ТТН уже удалена в Новой Почте.",
    ),
)


def _flatten_messages(context: NovaPoshtaErrorContext) -> str:
    parts = [*context.errors, *context.warnings, *context.info]
    return " ".join(parts).strip().lower()


def map_error_from_payload(
    *,
    payload: dict[str, Any] | None,
    default_message: str,
    status_code: int | None = None,
) -> NovaPoshtaIntegrationError:
    context = extract_error_context(payload)
    if not context.errors and not context.warnings and not context.info:
        return NovaPoshtaIntegrationError(default_message, status_code=status_code, context=context)

    haystack = _flatten_messages(context)
    for needles, mapped_message in _KNOWN_RULE_MESSAGES:
        if all(needle in haystack for needle in needles):
            return NovaPoshtaBusinessRuleError(
                format_context_message(mapped_message, context=context),
                status_code=status_code,
                context=context,
            )

    return NovaPoshtaIntegrationError(
        format_context_message(default_message, context=context),
        status_code=status_code,
        context=context,
    )
