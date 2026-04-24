from __future__ import annotations

from functools import lru_cache
from typing import Any

from django.db import DatabaseError, IntegrityError, OperationalError, ProgrammingError, connection
from django.utils import timezone

from apps.commerce.models import Order, OrderReceipt, VchasnoKasaSettings

from .client import VchasnoKasaApiClient
from .exceptions import VchasnoKasaConfigError, VchasnoKasaDisabledError, VchasnoKasaError
from .payloads import build_vchasno_order_payload, build_vchasno_sync_payload

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
        raise VchasnoKasaConfigError("Токен Вчасно.Каса не задан.", code="VCHASNO_KASA_TOKEN_MISSING")
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
    receipt = _get_or_create_sale_receipt(order=order, actor=actor)
    if receipt.receipt_url and receipt.fiscal_status_code == 11:
        return receipt
    if receipt.response_payload:
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
    if receipt is None:
        can_issue = bool(settings.is_enabled and (settings.api_token or "").strip() and (settings.rro_fn or "").strip())
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
    status_key = (receipt.fiscal_status_key or "").strip() or _status_key_from_code(status_code)
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
    status_key = (receipt.fiscal_status_key or "").strip() or _status_key_from_code(receipt.fiscal_status_code)
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


@lru_cache(maxsize=1)
def _introspected_table_names() -> frozenset[str]:
    return frozenset(connection.introspection.table_names())


def _table_exists(table_name: str) -> bool:
    try:
        return table_name in _introspected_table_names()
    except (DatabaseError, OperationalError, ProgrammingError):
        return False
