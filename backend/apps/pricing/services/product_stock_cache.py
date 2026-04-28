from __future__ import annotations

from collections.abc import Iterable

from django.db.models import Sum

from apps.catalog.models import Product
from apps.pricing.models import SupplierOffer


def refresh_available_stock_qty_cache(*, product_ids: Iterable[str]) -> int:
    normalized_ids = [str(product_id) for product_id in product_ids if product_id]
    if not normalized_ids:
        return 0

    totals = {
        str(row["product_id"]): int(row["total"] or 0)
        for row in (
            SupplierOffer.objects.filter(
                product_id__in=normalized_ids,
                is_available=True,
                stock_qty__gt=0,
            )
            .values("product_id")
            .annotate(total=Sum("stock_qty"))
        )
    }

    products = list(Product.objects.filter(id__in=normalized_ids).only("id", "available_stock_qty_cached"))
    changed = 0
    for product in products:
        next_value = totals.get(str(product.id), 0)
        if product.available_stock_qty_cached != next_value:
            product.available_stock_qty_cached = next_value
            changed += 1

    if changed == 0:
        return 0

    Product.objects.bulk_update(products, fields=["available_stock_qty_cached"], batch_size=1000)
    return changed
