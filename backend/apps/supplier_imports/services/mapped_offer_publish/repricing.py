from __future__ import annotations

from apps.catalog.models import Product
from apps.pricing.models import PriceHistory
from apps.pricing.services import ProductRepricer


def reprice_products(*, affected_product_ids: set[str], supplier_code: str) -> dict[str, int]:
    return ProductRepricer().recalculate_products(
        Product.objects.filter(id__in=affected_product_ids),
        source=PriceHistory.SOURCE_IMPORT,
        trigger_note=f"publish_mapped:{supplier_code}",
    )
