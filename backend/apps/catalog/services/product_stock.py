from __future__ import annotations

from django.db.models import Sum

from apps.catalog.models import Product
from apps.pricing.models import SupplierOffer


def get_available_supplier_offer_stock_sum(product: Product) -> int:
    offers = getattr(product, "backoffice_supplier_offers", None)
    if offers is None:
        prefetched = getattr(product, "_prefetched_objects_cache", {})
        offers = prefetched.get("supplier_offers")

    if offers is None:
        aggregated = (
            SupplierOffer.objects.filter(
                product=product,
                is_available=True,
                stock_qty__gt=0,
            ).aggregate(total=Sum("stock_qty"))
        )["total"]
        return int(aggregated or 0)

    total = 0
    for offer in offers:
        if not offer.is_available:
            continue
        total += max(int(offer.stock_qty or 0), 0)
    return total


def resolve_display_stock_qty(product: Product) -> int:
    cached_qty = int(getattr(product, "available_stock_qty_cached", 0) or 0)
    if cached_qty > 0:
        return cached_qty
    return get_available_supplier_offer_stock_sum(product)
