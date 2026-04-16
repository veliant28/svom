from celery import shared_task

from apps.catalog.models import Product
from apps.pricing.models import PriceHistory
from apps.pricing.services import ProductRepricer


@shared_task(name="pricing.recalculate_product_prices")
def recalculate_product_prices_task(
    product_ids: list[str] | None = None,
    source: str = PriceHistory.SOURCE_AUTO,
    trigger_note: str = "task:recalculate_product_prices",
) -> dict[str, int]:
    queryset = Product.objects.filter(is_active=True).select_related("brand", "category")
    if product_ids:
        queryset = queryset.filter(id__in=product_ids)

    return ProductRepricer().recalculate_products(
        queryset,
        source=source,
        trigger_note=trigger_note,
    )
