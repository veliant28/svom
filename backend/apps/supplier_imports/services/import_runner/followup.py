from __future__ import annotations

from apps.catalog.models import Product
from apps.pricing.models import PriceHistory
from apps.pricing.services import ProductRepricer
from apps.search.services import ProductIndexer


def reprice_products(*, affected_product_ids: list[str], source, run) -> dict[str, int]:
    queryset = Product.objects.filter(id__in=affected_product_ids).select_related("brand", "category")
    stats = ProductRepricer().recalculate_products(
        queryset,
        source=PriceHistory.SOURCE_IMPORT,
        trigger_note=f"import:{source.code}:run:{run.id}",
    )
    run.summary["repricing"] = stats
    return stats


def reindex_products(*, affected_product_ids: list[str]) -> dict[str, int]:
    return ProductIndexer().reindex_products(product_ids=affected_product_ids)
