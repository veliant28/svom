from __future__ import annotations

from django.utils import timezone

from apps.supplier_imports.models import SupplierPriceList
from apps.supplier_imports.services.integrations.exceptions import SupplierClientError

from ..status import extract_remote_status, is_failed_status, is_ready_status


def refresh_generating_state(service, *, row: SupplierPriceList, supplier_code: str, integration) -> None:
    if row.status != SupplierPriceList.STATUS_GENERATING:
        return

    changed_fields: set[str] = set()
    now = timezone.now()

    if (
        supplier_code == "utr"
        and row.request_mode == "utr_api"
        and row.remote_id
        and integration.access_token
    ):
        try:
            status_payload = service.utr_client.get_pricelist_status(
                access_token=integration.access_token,
                pricelist_id=row.remote_id,
            )
            remote_status = extract_remote_status(status_payload)
            if remote_status and row.remote_status != remote_status:
                row.remote_status = remote_status
                changed_fields.add("remote_status")
            if is_ready_status(remote_status):
                row.status = SupplierPriceList.STATUS_READY
                row.generated_at = row.generated_at or now
                changed_fields.update({"status", "generated_at"})
            elif is_failed_status(remote_status):
                row.status = SupplierPriceList.STATUS_FAILED
                row.last_error_at = now
                row.last_error_message = "Поставщик вернул ошибочный статус прайса."
                changed_fields.update({"status", "last_error_at", "last_error_message"})
        except SupplierClientError:
            # Keep local ETA-driven state; do not fail listing on transient API errors.
            pass

    if row.status == SupplierPriceList.STATUS_GENERATING and row.expected_ready_at and row.expected_ready_at <= now:
        row.status = SupplierPriceList.STATUS_READY
        row.generated_at = row.generated_at or now
        changed_fields.update({"status", "generated_at"})

    if changed_fields:
        row.save(update_fields=tuple(sorted({*changed_fields, "updated_at"})))
