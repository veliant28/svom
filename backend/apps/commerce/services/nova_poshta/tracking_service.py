from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.commerce.models import OrderNovaPoshtaWaybill, OrderNovaPoshtaWaybillEvent

from .client import NovaPoshtaApiClient
from .constants import FINAL_STATUS_CODES
from .normalizers import first_data_item
from .tracking_status_catalog import resolve_tracking_status_text


@dataclass(frozen=True)
class TrackingSyncResult:
    status_code: str
    status_text: str
    raw_payload: dict[str, Any]


class NovaPoshtaTrackingService:
    def sync_waybill_status(self, *, waybill: OrderNovaPoshtaWaybill, actor=None) -> TrackingSyncResult:
        if not waybill.np_number:
            raise ValueError("Waybill number is empty.")

        client = NovaPoshtaApiClient(api_token=waybill.sender_profile.api_token)
        response = client.get_tracking_status(document_number=waybill.np_number, phone=waybill.recipient_phone or "")
        status_data = first_data_item(response.payload)

        status_code = str(status_data.get("StatusCode") or "").strip()
        status_text = resolve_tracking_status_text(
            status_code=status_code,
            status_text=status_data.get("Status"),
        )

        with transaction.atomic():
            waybill.status_code = status_code
            waybill.status_text = status_text
            waybill.status_synced_at = timezone.now()
            waybill.raw_last_tracking_json = response.payload
            waybill.error_codes = response.context.error_codes
            waybill.warning_codes = response.context.warning_codes
            waybill.info_codes = response.context.info_codes
            waybill.last_sync_error = ""
            if status_code in FINAL_STATUS_CODES:
                waybill.can_edit = False
            waybill.save(
                update_fields=(
                    "status_code",
                    "status_text",
                    "status_synced_at",
                    "raw_last_tracking_json",
                    "error_codes",
                    "warning_codes",
                    "info_codes",
                    "last_sync_error",
                    "can_edit",
                    "updated_at",
                )
            )
            OrderNovaPoshtaWaybillEvent.objects.create(
                waybill=waybill,
                order=waybill.order,
                event_type=OrderNovaPoshtaWaybillEvent.EVENT_SYNC,
                message=f"Status synced: {status_text or status_code or '-'}",
                status_code=status_code,
                status_text=status_text,
                payload={"status": status_data},
                raw_response=response.payload,
                errors=response.context.errors,
                warnings=response.context.warnings,
                info=response.context.info,
                error_codes=response.context.error_codes,
                warning_codes=response.context.warning_codes,
                info_codes=response.context.info_codes,
                created_by=actor,
            )

        return TrackingSyncResult(status_code=status_code, status_text=status_text, raw_payload=response.payload)
