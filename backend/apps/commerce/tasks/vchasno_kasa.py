from __future__ import annotations

from celery import shared_task

from apps.commerce.models import Order
from apps.commerce.services.vchasno_kasa import VchasnoKasaError, issue_or_sync_order_receipt


@shared_task(name="commerce.issue_vchasno_kasa_receipt")
def issue_vchasno_kasa_receipt_task(*, order_id: str) -> dict[str, str]:
    order = Order.objects.prefetch_related("items").get(id=order_id)
    try:
        receipt = issue_or_sync_order_receipt(order=order)
    except VchasnoKasaError as exc:
        return {
            "status": "error",
            "code": exc.code,
            "message": str(exc),
        }
    return {
        "status": "ok",
        "receipt_id": str(receipt.id),
    }
