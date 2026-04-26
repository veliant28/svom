from __future__ import annotations

from functools import lru_cache
from typing import Any

from django.db import DatabaseError, IntegrityError, OperationalError, ProgrammingError, connection
from django.utils import timezone

from apps.commerce.models import Order, OrderReceipt, VchasnoKasaSettings

from .client import VchasnoKasaApiClient
from .exceptions import VchasnoKasaApiError, VchasnoKasaConfigError, VchasnoKasaDisabledError, VchasnoKasaError
from .payloads import (
    build_vchasno_order_payload,
    build_vchasno_sync_payload,
    get_selected_payment_methods,
    get_selected_tax_groups,
)

STATUS_CODE_TO_KEY = {
    0: "created",
    10: "delivered",
    11: "fiscalized",
    101: "cancelled",
    2000: "error",
    2001: "error",
    2002: "error",
}
STATUS_KEY_TO_LABEL = {
    "created": "Created",
    "delivered": "Delivered",
    "fiscalized": "Fiscalized",
    "cancelled": "Cancelled",
    "error": "Error",
    "pending": "Pending",
}


def has_vchasno_kasa_settings_table() -> bool:
    return _table_exists(VchasnoKasaSettings._meta.db_table)


def has_order_receipt_table() -> bool:
    return _table_exists(OrderReceipt._meta.db_table)


def get_vchasno_kasa_settings() -> VchasnoKasaSettings:
    if not has_vchasno_kasa_settings_table():
        return VchasnoKasaSettings(code=VchasnoKasaSettings.DEFAULT_CODE)
    settings, _ = VchasnoKasaSettings.objects.get_or_create(code=VchasnoKasaSettings.DEFAULT_CODE)
    return settings


def test_vchasno_kasa_connection() -> dict[str, Any]:
    settings = get_vchasno_kasa_settings()
    try:
        ensure_vchasno_kasa_settings_ready(settings=settings)
        client = VchasnoKasaApiClient(token=settings.api_token)
        client.list_orders({})
    except VchasnoKasaError as exc:
        return _save_check_result(settings=settings, ok=False, message=str(exc))
    return _save_check_result(settings=settings, ok=True, message="Connection successful.")


def get_vchasno_shift_status() -> dict[str, Any]:
    settings = get_vchasno_kasa_settings()
    if not settings.is_enabled:
        return _build_shift_status_payload(status_key="disabled", message="Інтеграцію Вчасно.Каса вимкнено.", response_code=None)

    token = _resolve_fiscal_api_token(settings=settings)
    if not token:
        return _build_shift_status_payload(
            status_key="error",
            message="API токен каси Вчасно не задан (Налаштування каси -> Токен).",
            response_code=None,
        )

    try:
        response = VchasnoKasaApiClient(token=token).execute_fiscal({"fiscal": {"task": 18}})
    except VchasnoKasaError as exc:
        return _build_shift_status_payload(status_key="error", message=str(exc), response_code=getattr(exc, "status_code", None))
    return _serialize_shift_status_from_response(response=response)


def open_vchasno_shift(*, actor=None) -> dict[str, Any]:
    settings = get_vchasno_kasa_settings()
    if not settings.is_enabled:
        raise VchasnoKasaDisabledError("Інтеграцію Вчасно.Каса вимкнено.")

    token = _resolve_fiscal_api_token(settings=settings)
    if not token:
        raise VchasnoKasaConfigError(
            "API токен каси Вчасно не задан (Налаштування каси -> Токен).",
            code="VCHASNO_KASA_FISCAL_TOKEN_MISSING",
        )

    response = VchasnoKasaApiClient(token=token).execute_fiscal({"fiscal": {"task": 0, "cashier": "SVOM"}})
    payload = _serialize_shift_status_from_response(response=response)
    if payload["status_key"] == "error":
        message = payload["message"] or "Не вдалося відкрити зміну."
        if _looks_like_shift_already_open(message):
            payload["status_key"] = "open"
            payload["is_open"] = True
            payload["can_open"] = False
            return payload
        raise VchasnoKasaApiError(message, status_code=422, details={"response": response})
    payload["status_key"] = "open"
    payload["is_open"] = True
    payload["can_open"] = False
    if not payload["message"]:
        payload["message"] = "Зміну відкрито."
    return payload


def close_vchasno_shift(*, actor=None) -> dict[str, Any]:
    settings = get_vchasno_kasa_settings()
    if not settings.is_enabled:
        raise VchasnoKasaDisabledError("Інтеграцію Вчасно.Каса вимкнено.")

    token = _resolve_fiscal_api_token(settings=settings)
    if not token:
        raise VchasnoKasaConfigError(
            "API токен каси Вчасно не задан (Налаштування каси -> Токен).",
            code="VCHASNO_KASA_FISCAL_TOKEN_MISSING",
        )

    response = VchasnoKasaApiClient(token=token).execute_fiscal({"fiscal": {"task": 11, "cashier": "SVOM"}})
    payload = _serialize_shift_status_from_response(response=response)
    if payload["status_key"] == "error":
        message = payload["message"] or "Не вдалося закрити зміну."
        if payload.get("response_code") == 2007 or _looks_like_shift_already_closed(message):
            payload["status_key"] = "closed"
            payload["is_open"] = False
            payload["can_open"] = True
            payload["message"] = "Зміну закрито."
            return payload
        raise VchasnoKasaApiError(message, status_code=422, details={"response": response})
    payload["status_key"] = "closed"
    payload["is_open"] = False
    payload["can_open"] = True
    payload["message"] = "Зміну закрито."
    return payload


def ensure_vchasno_kasa_settings_ready(*, settings: VchasnoKasaSettings | None = None) -> VchasnoKasaSettings:
    settings = settings or get_vchasno_kasa_settings()
    if not has_vchasno_kasa_settings_table() or not has_order_receipt_table():
        raise VchasnoKasaConfigError(
            "Интеграция Вчасно.Каса еще не подготовлена. Примените миграции.",
            code="VCHASNO_KASA_SCHEMA_NOT_READY",
        )
    if not settings.is_enabled:
        raise VchasnoKasaDisabledError()
    if not (settings.api_token or "").strip():
        raise VchasnoKasaConfigError(
            "API токен замовлень Вчасно не задан (Налаштування компанії -> Інтеграція замовлень -> API).",
            code="VCHASNO_KASA_TOKEN_MISSING",
        )
    if not (settings.rro_fn or "").strip():
        raise VchasnoKasaConfigError("Фискальный номер РРО/ПРРО не задан.", code="VCHASNO_KASA_RRO_FN_MISSING")
    return settings


def is_vchasno_auto_issue_enabled() -> bool:
    if not has_vchasno_kasa_settings_table():
        return False
    settings = get_vchasno_kasa_settings()
    return bool(settings.is_enabled and settings.auto_issue_on_completed)


def get_order_sale_receipt(order: Order) -> OrderReceipt | None:
    if not has_order_receipt_table():
        return None
    prefetched = getattr(order, "vchasno_receipts", None)
    if isinstance(prefetched, list):
        return prefetched[0] if prefetched else None
    return (
        OrderReceipt.objects
        .filter(order=order, provider=OrderReceipt.PROVIDER_VCHASNO_KASA, receipt_type=OrderReceipt.TYPE_SALE)
        .order_by("-updated_at", "-created_at")
        .first()
    )


def issue_order_receipt(*, order: Order, actor=None) -> OrderReceipt:
    settings = ensure_vchasno_kasa_settings_ready()
    _auto_open_shift_for_receipt_if_closed(settings=settings)
    receipt = _get_or_create_sale_receipt(order=order, actor=actor)
    if receipt.receipt_url and receipt.fiscal_status_code == 11:
        return receipt
    if _should_sync_existing_receipt(receipt=receipt):
        return sync_order_receipt(order=order, actor=actor)

    payload = build_vchasno_order_payload(order=order, receipt=receipt, settings=settings)
    client = VchasnoKasaApiClient(token=settings.api_token)
    try:
        response = client.create_order(payload)
    except VchasnoKasaError as exc:
        _store_receipt_error(receipt=receipt, error=exc, request_payload=payload, actor=actor)
        raise

    _apply_provider_payload(receipt=receipt, response=response, request_payload=payload, actor=actor)
    return receipt


def sync_order_receipt(*, order: Order, actor=None) -> OrderReceipt:
    settings = ensure_vchasno_kasa_settings_ready()
    receipt = get_order_sale_receipt(order)
    if receipt is None:
        raise VchasnoKasaError("Чек еще не создан.", code="VCHASNO_KASA_RECEIPT_MISSING", status_code=409)

    payload = build_vchasno_sync_payload(receipt=receipt)
    client = VchasnoKasaApiClient(token=settings.api_token)
    try:
        response = client.list_orders(payload)
    except VchasnoKasaError as exc:
        _store_receipt_error(receipt=receipt, error=exc, request_payload=payload, actor=actor)
        raise

    resolved = _match_receipt_payload(response=response, receipt=receipt)
    if resolved is None:
        error = VchasnoKasaError(
            "Чек еще не найден или не синхронизирован во Вчасно.Каса.",
            code="VCHASNO_KASA_RECEIPT_NOT_READY",
            status_code=409,
        )
        _store_receipt_error(receipt=receipt, error=error, request_payload=payload, actor=actor)
        raise error

    _apply_provider_payload(receipt=receipt, response=resolved, request_payload=payload, actor=actor)
    return receipt


def issue_or_sync_order_receipt(*, order: Order, actor=None) -> OrderReceipt:
    receipt = get_order_sale_receipt(order)
    if receipt is None:
        return issue_order_receipt(order=order, actor=actor)
    if receipt.receipt_url and receipt.fiscal_status_code == 11:
        return receipt
    return sync_order_receipt(order=order, actor=actor)


def get_open_receipt_url(*, order: Order) -> str:
    receipt = get_order_sale_receipt(order)
    if receipt is None:
        raise VchasnoKasaError("Чек еще не создан.", code="VCHASNO_KASA_RECEIPT_MISSING", status_code=409)
    receipt_url = (receipt.receipt_url or "").strip()
    if not receipt_url:
        raise VchasnoKasaError("Ссылка на чек недоступна.", code="VCHASNO_KASA_RECEIPT_URL_MISSING", status_code=409)
    return receipt_url


def serialize_receipt_summary(*, order: Order) -> dict[str, Any]:
    receipt = get_order_sale_receipt(order)
    settings = get_vchasno_kasa_settings()
    has_payment_methods = bool(get_selected_payment_methods(settings=settings))
    has_tax_groups = bool(get_selected_tax_groups(settings=settings))
    if receipt is None:
        can_issue = bool(
            settings.is_enabled
            and (settings.api_token or "").strip()
            and (settings.rro_fn or "").strip()
            and has_payment_methods
            and has_tax_groups
        )
        return {
            "provider": OrderReceipt.PROVIDER_VCHASNO_KASA,
            "available": bool(settings.is_enabled),
            "status_code": None,
            "status_key": "pending",
            "status_label": STATUS_KEY_TO_LABEL["pending"],
            "check_fn": "",
            "can_issue": can_issue,
            "can_open": False,
            "can_sync": False,
            "error_message": "",
        }

    status_code = receipt.fiscal_status_code
    status_key = _resolve_receipt_status_key(receipt=receipt)
    return {
        "provider": receipt.provider,
        "available": True,
        "status_code": status_code,
        "status_key": status_key,
        "status_label": receipt.fiscal_status_label or STATUS_KEY_TO_LABEL.get(status_key, STATUS_KEY_TO_LABEL["pending"]),
        "check_fn": receipt.check_fn or "",
        "can_issue": not bool(receipt.receipt_url and status_code == 11),
        "can_open": bool((receipt.receipt_url or "").strip()),
        "can_sync": True,
        "error_message": receipt.error_message or "",
    }


def serialize_receipt_row(receipt: OrderReceipt) -> dict[str, Any]:
    order = receipt.order
    status_key = _resolve_receipt_status_key(receipt=receipt)
    return {
        "id": str(receipt.id),
        "order_id": str(order.id),
        "order_number": order.order_number,
        "customer_name": order.contact_full_name,
        "amount": order.total,
        "currency": order.currency,
        "status_code": receipt.fiscal_status_code,
        "status_key": status_key,
        "status_label": receipt.fiscal_status_label or STATUS_KEY_TO_LABEL.get(status_key, STATUS_KEY_TO_LABEL["pending"]),
        "check_fn": receipt.check_fn or "",
        "receipt_url": receipt.receipt_url or "",
        "pdf_url": receipt.pdf_url or "",
        "created_at": receipt.created_at,
        "updated_at": receipt.updated_at,
    }


def _get_or_create_sale_receipt(*, order: Order, actor=None) -> OrderReceipt:
    defaults = {
        "provider": OrderReceipt.PROVIDER_VCHASNO_KASA,
        "receipt_type": OrderReceipt.TYPE_SALE,
        "vchasno_order_number": order.order_number,
        "email": order.contact_email or "",
        "created_by": actor,
        "updated_by": actor,
    }
    try:
        receipt, created = OrderReceipt.objects.get_or_create(
            order=order,
            provider=OrderReceipt.PROVIDER_VCHASNO_KASA,
            receipt_type=OrderReceipt.TYPE_SALE,
            defaults=defaults,
        )
    except IntegrityError:
        receipt = OrderReceipt.objects.get(
            order=order,
            provider=OrderReceipt.PROVIDER_VCHASNO_KASA,
            receipt_type=OrderReceipt.TYPE_SALE,
        )
        created = False
    if not created:
        updated_fields = []
        if not receipt.vchasno_order_number:
            receipt.vchasno_order_number = order.order_number
            updated_fields.append("vchasno_order_number")
        if actor is not None and receipt.updated_by_id != getattr(actor, "id", None):
            receipt.updated_by = actor
            updated_fields.append("updated_by")
        if updated_fields:
            updated_fields.append("updated_at")
            receipt.save(update_fields=tuple(updated_fields))
    return receipt


def _apply_provider_payload(*, receipt: OrderReceipt, response: dict[str, Any], request_payload: dict[str, Any], actor=None) -> None:
    status_code = _resolve_status_code(response)
    status_key = _status_key_from_code(status_code)
    receipt.check_fn = _first_string(response, "check_fn", "checkFn", "fn", "fiscal_number", "fiscalNumber") or receipt.check_fn
    receipt.fiscal_status_code = status_code
    receipt.fiscal_status_key = status_key
    receipt.fiscal_status_label = _first_string(response, "status_label", "statusLabel", "status", "state") or STATUS_KEY_TO_LABEL.get(status_key, "")
    receipt.receipt_url = _resolve_url(response, ("receipt_url", "receiptUrl", "url", "tax_url", "taxUrl")) or receipt.receipt_url
    receipt.pdf_url = _resolve_url(response, ("pdf_url", "pdfUrl", "file", "pdf")) or receipt.pdf_url
    receipt.email = _resolve_email(response) or receipt.email
    receipt.email_sent_at = _resolve_datetime(response, ("email_sent_at", "emailSentAt")) or receipt.email_sent_at
    receipt.fiscalized_at = _resolve_datetime(response, ("fiscalized_at", "fiscalizedAt", "date", "created_at", "createdAt")) if status_code == 11 else receipt.fiscalized_at
    receipt.error_code = ""
    receipt.error_message = ""
    receipt.request_payload = request_payload
    receipt.response_payload = response
    if actor is not None:
        receipt.updated_by = actor
    receipt.save(
        update_fields=(
            "check_fn",
            "fiscal_status_code",
            "fiscal_status_key",
            "fiscal_status_label",
            "receipt_url",
            "pdf_url",
            "email",
            "email_sent_at",
            "fiscalized_at",
            "error_code",
            "error_message",
            "request_payload",
            "response_payload",
            "updated_by",
            "updated_at",
        )
    )


def _store_receipt_error(*, receipt: OrderReceipt, error: VchasnoKasaError, request_payload: dict[str, Any], actor=None) -> None:
    receipt.error_code = error.code
    receipt.error_message = str(error)
    receipt.request_payload = request_payload
    if error.details:
        receipt.response_payload = error.details
    if actor is not None:
        receipt.updated_by = actor
    receipt.save(update_fields=("error_code", "error_message", "request_payload", "response_payload", "updated_by", "updated_at"))


def _save_check_result(*, settings: VchasnoKasaSettings, ok: bool, message: str) -> dict[str, Any]:
    if not has_vchasno_kasa_settings_table():
        return {
            "ok": bool(ok),
            "message": str(message or "").strip(),
        }
    now = timezone.now()
    settings.last_connection_checked_at = now
    settings.last_connection_ok = bool(ok)
    settings.last_connection_message = str(message or "").strip()
    settings.save(update_fields=("last_connection_checked_at", "last_connection_ok", "last_connection_message", "updated_at"))
    return {
        "ok": bool(ok),
        "message": settings.last_connection_message,
    }


def _status_key_from_code(status_code: int | None) -> str:
    if status_code is None:
        return "pending"
    return STATUS_CODE_TO_KEY.get(int(status_code), "pending")


def _resolve_receipt_status_key(*, receipt: OrderReceipt) -> str:
    explicit = str(getattr(receipt, "fiscal_status_key", "") or "").strip()
    if explicit:
        return explicit
    if str(getattr(receipt, "error_code", "") or "").strip() or str(getattr(receipt, "error_message", "") or "").strip():
        return "error"
    return _status_key_from_code(getattr(receipt, "fiscal_status_code", None))


def _resolve_status_code(payload: dict[str, Any]) -> int | None:
    for key in ("status_code", "statusCode", "fiscal_status_code", "fiscalStatusCode", "status"):
        value = payload.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
    fiscal = payload.get("fiscal")
    if isinstance(fiscal, dict):
        return _resolve_status_code(fiscal)
    data = payload.get("data")
    if isinstance(data, dict):
        return _resolve_status_code(data)
    return None


def _match_receipt_payload(*, response: dict[str, Any], receipt: OrderReceipt) -> dict[str, Any] | None:
    if _payload_matches_receipt(response, receipt):
        return response
    for candidate in _iter_nested_dicts(response):
        if _payload_matches_receipt(candidate, receipt):
            return candidate
    return None


def _payload_matches_receipt(payload: dict[str, Any], receipt: OrderReceipt) -> bool:
    order_number = _first_string(payload, "order_number", "orderNumber", "number")
    external_order_id = _first_string(payload, "external_order_id", "externalOrderId")
    if order_number and order_number == receipt.vchasno_order_number:
        return True
    if external_order_id and external_order_id == str(receipt.external_order_id):
        return True
    return False


def _iter_nested_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _iter_nested_dicts(nested)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_nested_dicts(item)


def _first_string(payload: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _resolve_url(payload: dict[str, Any], keys: tuple[str, ...]) -> str:
    value = _first_string(payload, *keys)
    if value:
        return value
    for nested in _iter_nested_dicts(payload):
        value = _first_string(nested, *keys)
        if value:
            return value
    return ""


def _resolve_email(payload: dict[str, Any]) -> str:
    return _first_string(payload, "email")


def _resolve_datetime(payload: dict[str, Any], keys: tuple[str, ...]):
    value = _first_string(payload, *keys)
    if not value:
        return None
    parsed = timezone.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _build_shift_status_payload(*, status_key: str, message: str, response_code: int | None, shift_id: str = "", shift_link: str = "") -> dict[str, Any]:
    return {
        "status_key": status_key,
        "is_open": True if status_key == "open" else False if status_key == "closed" else None,
        "shift_id": shift_id,
        "shift_link": shift_link,
        "message": str(message or "").strip(),
        "checked_at": timezone.now(),
        "can_open": status_key == "closed",
        "response_code": response_code,
    }


def _serialize_shift_status_from_response(*, response: dict[str, Any]) -> dict[str, Any]:
    response_code = _resolve_int(response.get("res"))
    info = response.get("info")
    if not isinstance(info, dict):
        info = {}
    shift_status = _resolve_int(info.get("shift_status"))
    shift_id = _first_string(info, "shift_id", "shiftId")
    shift_link_raw = info.get("shift_link", info.get("shiftLink"))
    shift_link = str(shift_link_raw).strip() if shift_link_raw is not None else ""
    raw_message = _first_string(response, "errortxt", "error", "message")
    message = _normalize_shift_message(raw_message=raw_message, response_code=response_code)
    status_key = _resolve_shift_status_key(
        response_code=response_code,
        shift_status=shift_status,
        shift_id=shift_id,
        shift_link=shift_link,
        message=message,
    )
    if not message:
        message = _default_shift_message(status_key=status_key)
    return _build_shift_status_payload(
        status_key=status_key,
        message=message,
        response_code=response_code,
        shift_id=shift_id,
        shift_link=shift_link,
    )


def _resolve_shift_status_key(
    *,
    response_code: int | None,
    shift_status: int | None,
    shift_id: str,
    shift_link: str,
    message: str,
) -> str:
    if response_code == 0:
        if shift_status == 1:
            return "open"
        if shift_status == 0:
            return "closed"
        if shift_id or shift_link:
            return "open"
        return "unknown"
    if response_code == 2007 or "відкрити зміну" in message.lower():
        return "closed"
    if response_code == 2008 or "закрити зміну" in message.lower():
        return "open"
    return "error"


def _default_shift_message(*, status_key: str) -> str:
    if status_key == "open":
        return "Зміну відкрито."
    if status_key == "closed":
        return "Зміну закрито."
    if status_key == "disabled":
        return "Інтеграцію Вчасно.Каса вимкнено."
    if status_key == "unknown":
        return "Не вдалося визначити стан зміни."
    return "Помилка перевірки стану зміни."


def _normalize_shift_message(*, raw_message: str, response_code: int | None) -> str:
    message = str(raw_message or "").strip()
    if response_code in {401, 403}:
        return (
            "Неавторизовано у Вчасно.Каса. Перевірте API токен каси "
            "(Налаштування каси → API → Згенерувати) і права токена на фіскальні операції."
        )
    if message.lower() in {"unauthorized", "forbidden"}:
        return (
            "Неавторизовано у Вчасно.Каса. Перевірте API токен каси "
            "(Налаштування каси → API → Згенерувати) і права токена на фіскальні операції."
        )
    return message


def _resolve_fiscal_api_token(*, settings: VchasnoKasaSettings) -> str:
    fiscal_token = str(getattr(settings, "fiscal_api_token", "") or "").strip()
    if fiscal_token:
        return fiscal_token
    return str(settings.api_token or "").strip()


def _auto_open_shift_for_receipt_if_closed(*, settings: VchasnoKasaSettings) -> None:
    token = _resolve_fiscal_api_token(settings=settings)
    if not token:
        return
    try:
        response = VchasnoKasaApiClient(token=token).execute_fiscal({"fiscal": {"task": 18}})
    except VchasnoKasaError:
        return
    status_payload = _serialize_shift_status_from_response(response=response)
    if status_payload.get("status_key") != "closed":
        return
    try:
        open_vchasno_shift()
    except VchasnoKasaError:
        return


def _should_sync_existing_receipt(*, receipt: OrderReceipt) -> bool:
    if not getattr(receipt, "response_payload", {}):
        return False
    if str(getattr(receipt, "error_code", "") or "").strip() or str(getattr(receipt, "error_message", "") or "").strip():
        return False
    return True


def _looks_like_shift_already_open(message: str) -> bool:
    normalized = str(message or "").lower()
    return "вже" in normalized and "відкр" in normalized and "змін" in normalized


def _looks_like_shift_already_closed(message: str) -> bool:
    normalized = str(message or "").lower()
    return (
        ("вже" in normalized and "закр" in normalized and "змін" in normalized)
        or ("немає" in normalized and "відкрит" in normalized and "змін" in normalized)
    )


def _resolve_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


@lru_cache(maxsize=1)
def _introspected_table_names() -> frozenset[str]:
    return frozenset(connection.introspection.table_names())


def _table_exists(table_name: str) -> bool:
    try:
        return table_name in _introspected_table_names()
    except (DatabaseError, OperationalError, ProgrammingError):
        return False
