from __future__ import annotations

import json
from typing import Any

from django.core.exceptions import ValidationError

from apps.commerce.models import OrderPayment

from .client import MonobankApiClient, MonobankApiError
from .invoice_service import apply_invoice_status_payload, get_monobank_settings
from .signature_service import verify_signature


class MonobankWebhookService:
    def handle(self, *, body: bytes, x_sign: str) -> tuple[OrderPayment, bool]:
        settings = get_monobank_settings()
        token = (settings.merchant_token or "").strip()
        if not token:
            raise ValidationError({"detail": "Monobank merchant token is not configured."})

        payload = self._parse_payload(body)
        invoice_id = str(payload.get("invoiceId") or "").strip()
        if not invoice_id:
            raise ValidationError({"detail": "Monobank webhook payload does not include invoiceId."})

        public_key = (settings.webhook_public_key or "").strip()
        if not public_key:
            try:
                public_key = MonobankApiClient(token=token).get_webhook_pubkey()
                settings.webhook_public_key = public_key
                settings.save(update_fields=("webhook_public_key", "updated_at"))
            except MonobankApiError as exc:
                raise ValidationError({"detail": f"Monobank public key fetch failed: {exc}"}) from exc

        if not verify_signature(payload=body, signature_base64=x_sign, public_key=public_key):
            raise ValidationError({"detail": "Monobank webhook signature verification failed."})

        payment = OrderPayment.objects.select_related("order").filter(monobank_invoice_id=invoice_id).first()
        if not payment:
            raise ValidationError({"detail": "Monobank webhook references unknown invoice."})

        is_applied = apply_invoice_status_payload(payment=payment, payload=payload, source="webhook")
        return payment, is_applied

    @staticmethod
    def _parse_payload(body: bytes) -> dict[str, Any]:
        try:
            parsed = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValidationError({"detail": "Invalid Monobank webhook payload."}) from exc

        if not isinstance(parsed, dict):
            raise ValidationError({"detail": "Invalid Monobank webhook payload."})

        return parsed
