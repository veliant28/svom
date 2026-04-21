from __future__ import annotations

import base64
import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.commerce.models import LiqPaySettings, Order, OrderPayment


LIQPAY_CHECKOUT_URL = "https://www.liqpay.ua/api/3/checkout"
LIQPAY_API_REQUEST_URL = "https://www.liqpay.ua/api/request"


class LiqPayApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class LiqPayCheckoutData:
    order_id: str
    data: str
    signature: str
    checkout_url: str


def get_liqpay_settings() -> LiqPaySettings:
    settings, _ = LiqPaySettings.objects.get_or_create(code=LiqPaySettings.DEFAULT_CODE)
    return settings


def get_urls_for_request(*, request) -> dict[str, str]:
    return {
        "server_url": request.build_absolute_uri("/api/commerce/payments/liqpay/webhook/"),
        "result_url": request.build_absolute_uri("/checkout"),
    }


def build_checkout_data(*, order: Order, server_url: str, result_url: str) -> LiqPayCheckoutData:
    settings = get_liqpay_settings()
    if not settings.is_enabled:
        raise ValidationError({"payment_method": "LiqPay payments are disabled in settings."})

    public_key = (settings.public_key or "").strip()
    private_key = (settings.private_key or "").strip()
    if not public_key:
        raise ValidationError({"payment_method": "LiqPay public key is not configured."})
    if not private_key:
        raise ValidationError({"payment_method": "LiqPay private key is not configured."})

    liqpay_order_id = str(order.order_number or order.id)
    payload: dict[str, Any] = {
        "version": 3,
        "public_key": public_key,
        "action": "pay",
        "amount": str(order.total),
        "currency": (order.currency or "UAH").upper(),
        "description": f"Order {order.order_number}",
        "order_id": liqpay_order_id,
        "result_url": result_url,
        "server_url": server_url,
        "language": "uk",
    }
    if public_key.startswith("sandbox_"):
        payload["sandbox"] = "1"

    data = _encode_data(payload)
    signature = _build_signature(data=data, private_key=private_key)
    checkout_url = f"{LIQPAY_CHECKOUT_URL}?data={urllib_parse.quote(data)}&signature={urllib_parse.quote(signature)}"
    return LiqPayCheckoutData(
        order_id=liqpay_order_id,
        data=data,
        signature=signature,
        checkout_url=checkout_url,
    )


def refresh_liqpay_payment_status(*, payment: OrderPayment) -> OrderPayment:
    if payment.provider != OrderPayment.PROVIDER_LIQPAY:
        raise ValidationError({"payment_method": "Payment provider is not LiqPay."})

    liqpay_order_id = (payment.liqpay_order_id or "").strip()
    if not liqpay_order_id:
        raise ValidationError({"payment_method": "LiqPay order ID is missing."})

    settings = get_liqpay_settings()
    public_key = (settings.public_key or "").strip()
    private_key = (settings.private_key or "").strip()
    if not public_key or not private_key:
        raise ValidationError({"payment_method": "LiqPay keys are not configured."})

    request_payload: dict[str, Any] = {
        "version": 3,
        "public_key": public_key,
        "action": "status",
        "order_id": liqpay_order_id,
    }
    response = _request_api(payload=request_payload, private_key=private_key)
    apply_payment_payload(payment=payment, payload=response, source="sync")
    return payment


def test_liqpay_connection() -> dict[str, Any]:
    settings = get_liqpay_settings()
    public_key = (settings.public_key or "").strip()
    private_key = (settings.private_key or "").strip()
    if not public_key:
        return _save_check_result(settings=settings, ok=False, message="LiqPay public key is not configured.")
    if not private_key:
        return _save_check_result(settings=settings, ok=False, message="LiqPay private key is not configured.")

    request_payload: dict[str, Any] = {
        "version": 3,
        "public_key": public_key,
        "action": "status",
        "order_id": f"connect-check-{uuid.uuid4().hex}",
    }
    try:
        response = _request_api(payload=request_payload, private_key=private_key)
    except LiqPayApiError as exc:
        return _save_check_result(settings=settings, ok=False, message=str(exc))

    ok, message = _resolve_connection_result(response)
    return _save_check_result(settings=settings, ok=ok, message=message)


def handle_webhook(*, data: str, signature: str) -> tuple[OrderPayment, bool]:
    raw_data = (data or "").strip()
    raw_signature = (signature or "").strip()
    if not raw_data or not raw_signature:
        raise ValidationError({"detail": "Missing LiqPay callback payload."})

    settings = get_liqpay_settings()
    private_key = (settings.private_key or "").strip()
    if not private_key:
        raise ValidationError({"detail": "LiqPay private key is not configured."})

    expected_signature = _build_signature(data=raw_data, private_key=private_key)
    if not hmac.compare_digest(expected_signature, raw_signature):
        raise ValidationError({"detail": "LiqPay callback signature is invalid."})

    try:
        decoded = base64.b64decode(raw_data)
        payload = json.loads(decoded.decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValidationError({"detail": "LiqPay callback payload is invalid."}) from exc

    liqpay_order_id = str(payload.get("order_id") or "").strip()
    if not liqpay_order_id:
        raise ValidationError({"detail": "LiqPay callback order_id is missing."})

    payment = (
        OrderPayment.objects.select_related("order")
        .filter(provider=OrderPayment.PROVIDER_LIQPAY, liqpay_order_id=liqpay_order_id)
        .first()
    )
    if payment is None:
        raise ValidationError({"detail": "LiqPay payment not found."})

    applied = apply_payment_payload(payment=payment, payload=payload, source="webhook")
    return payment, applied


def apply_payment_payload(*, payment: OrderPayment, payload: dict[str, Any], source: str) -> bool:
    incoming_modified = _parse_provider_datetime(payload.get("create_date")) or _parse_provider_datetime(payload.get("transaction_id"))
    existing_modified = payment.provider_modified_at

    payment.last_sync_at = timezone.now()
    if source == "webhook":
        payment.last_webhook_received_at = timezone.now()
        payment.raw_last_webhook_payload = payload
    else:
        payment.raw_status_payload = payload

    if incoming_modified and existing_modified and incoming_modified <= existing_modified:
        payment.save(
            update_fields=(
                "last_sync_at",
                "last_webhook_received_at",
                "raw_last_webhook_payload",
                "raw_status_payload",
                "updated_at",
            )
        )
        return False

    liqpay_payment_id = str(payload.get("payment_id") or "").strip()
    liqpay_order_id = str(payload.get("order_id") or "").strip()
    liqpay_status = str(payload.get("status") or "").strip().lower()
    failure_reason = str(payload.get("err_description") or payload.get("err_code") or "").strip()
    amount = _parse_amount(payload.get("amount"))
    currency = str(payload.get("currency") or "").strip().upper()

    if liqpay_payment_id:
        payment.liqpay_payment_id = liqpay_payment_id
    if liqpay_order_id:
        payment.liqpay_order_id = liqpay_order_id
    if amount is not None:
        payment.amount = amount
    if currency:
        payment.currency = currency

    payment.status = _resolve_status(liqpay_status)
    payment.failure_reason = failure_reason

    created_at = _parse_provider_datetime(payload.get("create_date"))
    modified_at = _parse_provider_datetime(payload.get("end_date")) or incoming_modified
    if created_at:
        payment.provider_created_at = created_at
    if modified_at:
        payment.provider_modified_at = modified_at

    payment.save(
        update_fields=(
            "status",
            "failure_reason",
            "amount",
            "currency",
            "liqpay_payment_id",
            "liqpay_order_id",
            "provider_created_at",
            "provider_modified_at",
            "last_sync_at",
            "last_webhook_received_at",
            "raw_last_webhook_payload",
            "raw_status_payload",
            "updated_at",
        )
    )
    return True


def _request_api(*, payload: dict[str, Any], private_key: str) -> dict[str, Any]:
    data = _encode_data(payload)
    signature = _build_signature(data=data, private_key=private_key)
    post_payload = urllib_parse.urlencode({"data": data, "signature": signature}).encode("utf-8")

    request = urllib_request.Request(
        url=LIQPAY_API_REQUEST_URL,
        data=post_payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    try:
        with urllib_request.urlopen(request, timeout=20) as response:
            raw = response.read()
    except urllib_error.HTTPError as exc:
        raw = exc.read() if hasattr(exc, "read") else b""
        raise LiqPayApiError(f"LiqPay API request failed: HTTP {exc.code}. {raw.decode('utf-8', errors='ignore')}") from exc
    except urllib_error.URLError as exc:
        raise LiqPayApiError("Failed to reach LiqPay API.") from exc

    text = raw.decode("utf-8", errors="replace").strip()
    if not text:
        raise LiqPayApiError("LiqPay API returned an empty response.")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LiqPayApiError("LiqPay API returned an unsupported payload.") from exc
    if not isinstance(parsed, dict):
        raise LiqPayApiError("LiqPay API returned an unsupported payload.")
    return parsed


def _resolve_connection_result(payload: dict[str, Any]) -> tuple[bool, str]:
    status = str(payload.get("status") or "").strip().lower()
    err_code = str(payload.get("err_code") or payload.get("err") or "").strip()
    err_description = str(payload.get("err_description") or payload.get("description") or "").strip()
    combined = f"{err_code} {err_description}".lower()

    auth_markers = ("signature", "public_key", "merchant", "auth", "token", "key", "unauthorized", "forbidden")
    not_found_markers = ("not found", "not exist", "order", "invoice")

    if any(marker in combined for marker in auth_markers):
        return False, err_description or err_code or "LiqPay credentials are invalid."
    if status in {"error", "failure"} and err_code and not any(marker in combined for marker in not_found_markers):
        return False, err_description or err_code

    if err_description:
        return True, f"Connection successful ({err_description})."
    return True, "Connection successful."


def _save_check_result(*, settings: LiqPaySettings, ok: bool, message: str) -> dict[str, Any]:
    now = timezone.now()
    settings.last_connection_checked_at = now
    settings.last_connection_ok = bool(ok)
    settings.last_connection_message = str(message or "").strip()
    settings.save(
        update_fields=(
            "last_connection_checked_at",
            "last_connection_ok",
            "last_connection_message",
            "updated_at",
        )
    )
    return {
        "ok": bool(ok),
        "message": settings.last_connection_message,
    }


def _encode_data(payload: dict[str, Any]) -> str:
    json_string = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return base64.b64encode(json_string.encode("utf-8")).decode("ascii")


def _build_signature(*, data: str, private_key: str) -> str:
    source = f"{private_key}{data}{private_key}".encode("utf-8")
    digest = hashlib.sha3_256(source).digest()
    return base64.b64encode(digest).decode("ascii")


def _resolve_status(status: str) -> str:
    normalized = (status or "").strip().lower()
    if normalized in {"success", "subscribed", "unsubscribed"}:
        return OrderPayment.STATUS_SUCCESS
    if normalized in {"error", "failure"}:
        return OrderPayment.STATUS_FAILURE
    if normalized in {"reversed"}:
        return OrderPayment.STATUS_REVERSED
    if normalized in {"expired"}:
        return OrderPayment.STATUS_EXPIRED
    if normalized in {"hold_wait", "hold", "wait_reserve"}:
        return OrderPayment.STATUS_HOLD
    if normalized in {"created"}:
        return OrderPayment.STATUS_CREATED
    return OrderPayment.STATUS_PROCESSING


def _parse_amount(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _parse_provider_datetime(value: Any):
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=dt_timezone.utc)
        except (ValueError, OSError):
            return None
    if isinstance(value, str):
        numeric = value.strip()
        if numeric.isdigit():
            try:
                return datetime.fromtimestamp(float(numeric), tz=dt_timezone.utc)
            except (ValueError, OSError):
                return None
        parsed = parse_datetime(value)
        if parsed is not None:
            if timezone.is_naive(parsed):
                return timezone.make_aware(parsed, dt_timezone.utc)
            return parsed
    return None
