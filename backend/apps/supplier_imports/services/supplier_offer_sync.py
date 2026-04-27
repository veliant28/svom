from __future__ import annotations

from decimal import Decimal

from apps.pricing.models import SupplierOffer
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.parsers.gpl_parser import extract_gpl_price_levels


class SupplierOfferSyncService:
    def upsert_from_raw_offer(self, raw_offer: SupplierRawOffer) -> tuple[SupplierOffer, bool]:
        if raw_offer.matched_product is None:
            raise ValueError("Raw offer has no matched product.")
        if raw_offer.price is None:
            raise ValueError("Raw offer has no price.")

        supplier_sku = (raw_offer.external_sku or raw_offer.article)[:128]
        price_levels = _extract_price_levels(raw_offer=raw_offer)

        offer, created = SupplierOffer.objects.update_or_create(
            supplier=raw_offer.supplier,
            product=raw_offer.matched_product,
            supplier_sku=supplier_sku,
            defaults={
                "currency": raw_offer.currency,
                "purchase_price": raw_offer.price,
                "price_levels": price_levels,
                "stock_qty": max(raw_offer.stock_qty, 0),
                "lead_time_days": max(raw_offer.lead_time_days, 0),
                "is_available": raw_offer.stock_qty > 0 and raw_offer.price > Decimal("0"),
            },
        )
        return offer, created


def _extract_price_levels(*, raw_offer: SupplierRawOffer) -> list[dict]:
    source_code = str(getattr(raw_offer.source, "code", "") or "").lower()
    if source_code != "gpl":
        return []
    return extract_gpl_price_levels(item=raw_offer.raw_payload or {}, default_currency=raw_offer.currency)
