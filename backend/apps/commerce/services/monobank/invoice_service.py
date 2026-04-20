from __future__ import annotations

import base64
import json
import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.commerce.models import MonobankSettings, Order, OrderPayment
from apps.users.models import User

from .client import MonobankApiClient, MonobankApiError
from .mapper import build_invoice_create_payload, resolve_ccy
from .signature_service import MonobankSignatureError, sign_payload
from .types import MonobankConnectionCheckResult, MonobankInvoiceResult, MonobankWidgetInitPayload


def get_monobank_settings() -> MonobankSettings:
    settings, _ = MonobankSettings.objects.get_or_create(code=MonobankSettings.DEFAULT_CODE)
    return settings


def get_order_payment(order: Order) -> OrderPayment:
    try:
        payment = order.payment
    except OrderPayment.DoesNotExist:
        payment = None
    if payment is not None:
        return payment

    provider = OrderPayment.PROVIDER_COD
    method = OrderPayment.METHOD_CASH_ON_DELIVERY
    if order.payment_method == Order.PAYMENT_MONOBANK:
        provider = OrderPayment.PROVIDER_MONOBANK
        method = OrderPayment.METHOD_MONOBANK

    payment, _ = OrderPayment.objects.get_or_create(
        order=order,
        defaults={
            "provider": provider,
            "method": method,
            "status": OrderPayment.STATUS_PENDING,
            "amount": order.total,
            "currency": order.currency,
        },
    )
    return payment


def create_invoice_for_order(*, order: Order, webhook_url: str, redirect_url: str = "") -> MonobankInvoiceResult:
    settings = get_monobank_settings()
    if not settings.is_enabled:
        raise ValidationError({"payment_method": "Monobank payments are disabled in settings."})

    token = (settings.merchant_token or "").strip()
    if not token:
        raise ValidationError({"payment_method": "Monobank merchant token is not configured."})

    payment = get_order_payment(order)
    payment.provider = OrderPayment.PROVIDER_MONOBANK
    payment.method = OrderPayment.METHOD_MONOBANK
    payment.amount = order.total
    payment.currency = order.currency

    payload = build_invoice_create_payload(order=order, webhook_url=webhook_url, redirect_url=redirect_url)

    try:
        response = MonobankApiClient(token=token).create_invoice(payload)
    except MonobankApiError as exc:
        payment.status = OrderPayment.STATUS_FAILURE
        payment.failure_reason = str(exc)
        payment.raw_create_payload = payload
        payment.raw_create_response = _as_json_dict(exc.payload)
        payment.last_sync_at = timezone.now()
        payment.save(
            update_fields=(
                "provider",
                "method",
                "amount",
                "currency",
                "status",
                "failure_reason",
                "raw_create_payload",
                "raw_create_response",
                "last_sync_at",
                "updated_at",
            )
        )
        raise

    invoice_id = str(response.get("invoiceId") or "").strip()
    page_url = str(response.get("pageUrl") or "").strip()

    if not invoice_id:
        raise ValidationError({"payment_method": "Monobank invoiceId is missing in create invoice response."})

    payment.monobank_invoice_id = invoice_id
    payment.monobank_page_url = page_url
    payment.monobank_reference = str(payload.get("merchantPaymInfo", {}).get("reference") or order.order_number)
    payment.status = OrderPayment.STATUS_CREATED
    payment.failure_reason = ""
    payment.provider_created_at = timezone.now()
    payment.provider_modified_at = timezone.now()
    payment.last_sync_at = timezone.now()
    payment.raw_create_payload = payload
    payment.raw_create_response = response
    payment.save(
        update_fields=(
            "provider",
            "method",
            "amount",
            "currency",
            "monobank_invoice_id",
            "monobank_page_url",
            "monobank_reference",
            "status",
            "failure_reason",
            "provider_created_at",
            "provider_modified_at",
            "last_sync_at",
            "raw_create_payload",
            "raw_create_response",
            "updated_at",
        )
    )

    return MonobankInvoiceResult(invoice_id=invoice_id, page_url=page_url, raw_response=response)


def refresh_invoice_status(*, payment: OrderPayment) -> OrderPayment:
    invoice_id = _require_monobank_invoice(payment=payment)
    client = _build_monobank_client()
    payload = client.get_invoice_status(invoice_id=invoice_id)
    apply_invoice_status_payload(payment=payment, payload=payload, source="sync")
    return payment


def cancel_invoice_payment(*, payment: OrderPayment, amount_minor: int | None = None) -> dict[str, Any]:
    invoice_id = _require_monobank_invoice(payment=payment)
    client = _build_monobank_client()

    payload: dict[str, Any] = {"invoiceId": invoice_id}
    if amount_minor is not None:
        payload["amount"] = int(amount_minor)

    result = client.cancel_invoice(payload)
    try:
        refresh_invoice_status(payment=payment)
    except Exception:
        payment.last_sync_at = timezone.now()
        payment.raw_status_payload = _as_json_dict(result)
        payment.save(update_fields=("last_sync_at", "raw_status_payload", "updated_at"))
    return result


def remove_invoice(*, payment: OrderPayment) -> dict[str, Any]:
    invoice_id = _require_monobank_invoice(payment=payment)
    client = _build_monobank_client()

    result = client.remove_invoice(invoice_id=invoice_id)
    payment.status = OrderPayment.STATUS_EXPIRED
    payment.failure_reason = "Invoice invalidated by operator."
    payment.provider_modified_at = timezone.now()
    payment.last_sync_at = timezone.now()
    payment.raw_status_payload = _as_json_dict(result)
    payment.save(
        update_fields=(
            "status",
            "failure_reason",
            "provider_modified_at",
            "last_sync_at",
            "raw_status_payload",
            "updated_at",
        )
    )
    return result


def finalize_invoice_hold(*, payment: OrderPayment, amount_minor: int | None = None) -> dict[str, Any]:
    invoice_id = _require_monobank_invoice(payment=payment)
    client = _build_monobank_client()

    payload: dict[str, Any] = {"invoiceId": invoice_id}
    if amount_minor is not None:
        payload["amount"] = int(amount_minor)

    result = client.finalize_invoice(payload)
    try:
        refresh_invoice_status(payment=payment)
    except Exception:
        payment.last_sync_at = timezone.now()
        payment.raw_status_payload = _as_json_dict(result)
        payment.save(update_fields=("last_sync_at", "raw_status_payload", "updated_at"))
    return result


def get_invoice_fiscal_checks(*, payment: OrderPayment) -> list[dict[str, Any]]:
    invoice_id = _require_monobank_invoice(payment=payment)
    client = _build_monobank_client()
    payload = client.get_invoice_fiscal_checks(invoice_id=invoice_id)
    checks = payload.get("checks")
    if isinstance(checks, list):
        return [item for item in checks if isinstance(item, dict)]
    return []


def apply_invoice_status_payload(*, payment: OrderPayment, payload: dict[str, Any], source: str) -> bool:
    incoming_modified = parse_datetime(str(payload.get("modifiedDate") or ""))
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

    incoming_status = str(payload.get("status") or "").strip().lower()
    payment.status = _resolve_payment_status(incoming_status)
    payment.failure_reason = str(payload.get("failureReason") or "").strip()
    payment.monobank_reference = str(payload.get("reference") or payment.monobank_reference or "")

    amount_minor = payload.get("amount")
    ccy_value = payload.get("ccy")
    if isinstance(amount_minor, int):
        payment.amount = Decimal(amount_minor) / Decimal("100")
    if isinstance(ccy_value, int):
        payment.currency = _resolve_currency(ccy_value)

    created_date = parse_datetime(str(payload.get("createdDate") or ""))
    modified_date = incoming_modified
    if created_date:
        payment.provider_created_at = created_date
    if modified_date:
        payment.provider_modified_at = modified_date

    payment.save(
        update_fields=(
            "status",
            "failure_reason",
            "monobank_reference",
            "amount",
            "currency",
            "provider_created_at",
            "provider_modified_at",
            "last_webhook_received_at",
            "last_sync_at",
            "raw_last_webhook_payload",
            "raw_status_payload",
            "updated_at",
        )
    )
    return True


def build_widget_init_payload(*, payment: OrderPayment) -> MonobankWidgetInitPayload | None:
    settings = get_monobank_settings()
    key_id = (settings.widget_key_id or "").strip()
    private_key = (settings.widget_private_key or "").strip()

    if not key_id or not private_key:
        return None

    order_payload = dict(payment.raw_create_payload or {})
    if not order_payload:
        order_payload = {
            "amount": int(payment.amount * 100),
            "ccy": resolve_ccy(payment.currency),
            "merchantPaymInfo": {
                "reference": payment.monobank_reference or payment.order.order_number,
                "destination": f"Order {payment.order.order_number}",
                "comment": f"Order {payment.order.order_number}",
            },
            "webHookUrl": "",
            "paymentType": "debit",
        }

    request_id = uuid.uuid4().hex
    json_string = json.dumps(order_payload, ensure_ascii=False, separators=(",", ":"))
    data_to_sign = f"{json_string}{request_id}".encode("utf-8")

    try:
        signature = sign_payload(payload=data_to_sign, private_key=private_key)
    except MonobankSignatureError:
        return None

    payload_base64 = base64.b64encode(json_string.encode("utf-8")).decode("ascii")

    return MonobankWidgetInitPayload(
        key_id=key_id,
        request_id=request_id,
        signature=signature,
        payload_base64=payload_base64,
    )


def build_selector_widget_init_payload(*, user: User) -> MonobankWidgetInitPayload | None:
    settings = get_monobank_settings()
    key_id = (settings.widget_key_id or "").strip()
    private_key = (settings.widget_private_key or "").strip()

    if not key_id or not private_key:
        return None

    # Build a signed payload only for official MonoPay button rendering in checkout selector.
    from apps.commerce.services.cart_calculations import calculate_cart_totals
    from apps.commerce.services.cart_service import get_or_create_user_cart

    cart = get_or_create_user_cart(user)
    cart_items = list(cart.items.select_related("product", "product__product_price"))
    totals = calculate_cart_totals(cart_items)
    amount_major = totals.subtotal if totals.subtotal > Decimal("0.00") else Decimal("1.00")

    payload = {
        "amount": int(amount_major * 100),
        "ccy": resolve_ccy("UAH"),
        "merchantPaymInfo": {
            "reference": f"checkout-selector-{uuid.uuid4().hex[:12]}",
            "destination": "Checkout payment method selector",
            "comment": "Checkout payment method selector",
        },
        "webHookUrl": "",
        "paymentType": "debit",
    }

    request_id = uuid.uuid4().hex
    json_string = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    data_to_sign = f"{json_string}{request_id}".encode("utf-8")

    try:
        signature = sign_payload(payload=data_to_sign, private_key=private_key)
    except MonobankSignatureError:
        return None

    payload_base64 = base64.b64encode(json_string.encode("utf-8")).decode("ascii")

    return MonobankWidgetInitPayload(
        key_id=key_id,
        request_id=request_id,
        signature=signature,
        payload_base64=payload_base64,
    )


def test_monobank_connection() -> MonobankConnectionCheckResult:
    settings = get_monobank_settings()
    token = (settings.merchant_token or "").strip()
    if not token:
        return MonobankConnectionCheckResult(ok=False, message="Monobank merchant token is not configured.", public_key="")

    now = timezone.now()
    try:
        public_key = MonobankApiClient(token=token).get_webhook_pubkey()
        settings.webhook_public_key = public_key
        settings.last_connection_checked_at = now
        settings.last_connection_ok = True
        settings.last_connection_message = "Connection successful."
        settings.save(update_fields=(
            "webhook_public_key",
            "last_connection_checked_at",
            "last_connection_ok",
            "last_connection_message",
            "updated_at",
        ))
        return MonobankConnectionCheckResult(ok=True, message=settings.last_connection_message, public_key=public_key)
    except MonobankApiError as exc:
        settings.last_connection_checked_at = now
        settings.last_connection_ok = False
        settings.last_connection_message = str(exc)
        settings.save(update_fields=(
            "last_connection_checked_at",
            "last_connection_ok",
            "last_connection_message",
            "updated_at",
        ))
        return MonobankConnectionCheckResult(ok=False, message=str(exc), public_key="")


def get_urls_for_request(*, request) -> dict[str, str]:
    webhook_url = request.build_absolute_uri("/api/commerce/payments/monobank/webhook/")
    redirect_url = request.build_absolute_uri("/checkout")
    return {
        "webhook_url": webhook_url,
        "redirect_url": redirect_url,
    }


def is_currency_snapshot_fresh(settings: MonobankSettings) -> bool:
    if not settings.last_currency_sync_at:
        return False
    return timezone.now() - settings.last_currency_sync_at < timedelta(minutes=5)


def _resolve_currency(ccy: int) -> str:
    if ccy == 980:
        return "UAH"
    if ccy == 840:
        return "USD"
    if ccy == 978:
        return "EUR"
    return "UAH"


def _resolve_payment_status(status: str) -> str:
    normalized = (status or "").strip().lower()
    if normalized in {
        OrderPayment.STATUS_PENDING,
        OrderPayment.STATUS_CREATED,
        OrderPayment.STATUS_PROCESSING,
        OrderPayment.STATUS_HOLD,
        OrderPayment.STATUS_SUCCESS,
        OrderPayment.STATUS_FAILURE,
        OrderPayment.STATUS_REVERSED,
        OrderPayment.STATUS_EXPIRED,
    }:
        return normalized

    if normalized in {"failure", "error", "declined"}:
        return OrderPayment.STATUS_FAILURE

    return OrderPayment.STATUS_PENDING


def _as_json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        return {"detail": value}
    return {}


def _build_monobank_client() -> MonobankApiClient:
    settings = get_monobank_settings()
    token = (settings.merchant_token or "").strip()
    if not token:
        raise ValidationError({"detail": "Monobank merchant token is not configured."})
    return MonobankApiClient(token=token)


def _require_monobank_invoice(*, payment: OrderPayment) -> str:
    if payment.provider != OrderPayment.PROVIDER_MONOBANK:
        raise ValidationError({"detail": "This order does not use Monobank payment."})

    invoice_id = (payment.monobank_invoice_id or "").strip()
    if not invoice_id:
        raise ValidationError({"detail": "Monobank invoice is not linked to this order."})
    return invoice_id
