from celery import shared_task

from apps.catalog.models import Product
from apps.pricing.models import PriceHistory
from apps.pricing.services import ProductRepricer


@shared_task(name="pricing.recalculate_supplier_prices")
def recalculate_supplier_prices_task(
    supplier_ids: list[str],
    source: str = PriceHistory.SOURCE_AUTO,
    trigger_note: str = "task:recalculate_supplier_prices",
) -> dict[str, int]:
    queryset = (
        Product.objects.filter(is_active=True, supplier_offers__supplier_id__in=supplier_ids)
        .select_related("brand", "category")
        .distinct()
    )

    return ProductRepricer().recalculate_products(
        queryset,
        source=source,
        trigger_note=trigger_note,
    )
