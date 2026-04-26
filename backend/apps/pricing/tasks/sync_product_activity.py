from celery import shared_task

from apps.pricing.services import (
    DEFAULT_PRICE_FRESHNESS_HOURS,
    sync_products_activity_by_price_freshness,
)


@shared_task(name="pricing.sync_products_activity_by_price_freshness")
def sync_products_activity_by_price_freshness_task(
    freshness_hours: int = DEFAULT_PRICE_FRESHNESS_HOURS,
) -> dict[str, int | str]:
    result = sync_products_activity_by_price_freshness(freshness_hours=freshness_hours)
    return {
        "activated": int(result.activated),
        "deactivated": int(result.deactivated),
        "supplier_offers_zeroed": int(result.supplier_offers_zeroed),
        "freshness_hours": int(result.freshness_hours),
        "cutoff_at": result.cutoff_at.isoformat(),
    }
