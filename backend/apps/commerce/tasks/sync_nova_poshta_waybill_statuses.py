from __future__ import annotations

from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from apps.commerce.models import OrderNovaPoshtaWaybill
from apps.commerce.services.nova_poshta import NovaPoshtaWaybillService
from apps.commerce.services.nova_poshta.constants import FINAL_STATUS_CODES


@shared_task(name="commerce.sync_nova_poshta_waybill_statuses")
def sync_nova_poshta_waybill_statuses_task(*, batch_size: int = 100) -> dict:
    now = timezone.now()
    boundary = now - timedelta(days=45)

    queryset = (
        OrderNovaPoshtaWaybill.objects
        .select_related("sender_profile", "order")
        .filter(is_deleted=False, created_at__gte=boundary)
        .exclude(np_number="")
        .exclude(status_code__in=FINAL_STATUS_CODES)
        .order_by("status_synced_at", "created_at")[: max(1, min(batch_size, 500))]
    )

    service = NovaPoshtaWaybillService()
    synced = 0
    failed = 0
    for waybill in queryset:
        try:
            service.sync_waybill(waybill=waybill)
            synced += 1
        except Exception as exc:  # noqa: BLE001
            waybill.last_sync_error = str(exc)
            waybill.save(update_fields=("last_sync_error", "updated_at"))
            failed += 1

    return {
        "processed": synced + failed,
        "synced": synced,
        "failed": failed,
    }
